#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从一份已有审查的板级数据出一致性基准题包。

题包 = 板级数据（db/intent/资料）+ 用被测 SR 重新生成的计划 + 选定行的完整规格 + 固定指令。
计划里已没有的行（原审查者手工加的行）沿用原计划的规格，并标明来源。
只拷贝审查输入，不拷贝 review-results / report / calculations / review-gate；资料目录中混入的前次审查产出
（结果表、计划、质量筛查）自动排除，无法自动识别的（如原审查者的计算笔记）用 --exclude 指名。
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
INPUTS = ('db.json', 'intent.json', 'datasheet-resolution.json', 'lint-cold.json', 'lint-hot.json')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reviewer_output(path):
    """资料目录里混入的前次审查产出（结果表、计划、质量筛查）；返回原因或 None。"""
    head = path.read_bytes()[:4096].decode('utf-8', 'replace')
    first = head.splitlines()[0].lower() if head else ''
    if path.suffix.lower() in ('.tsv', '.csv') and 'result' in first:
        return 'results table'
    if '"quality_screening"' in head:
        return 'quality screening of results'
    if '"generated_by": "check-catalog planner"' in head or '"review_result"' in head:
        return 'review plan/results'
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True, help='含 db.json、intent.json、review-plan.json、materials/ 的目录')
    ap.add_argument('--rows', type=Path, required=True, help='JSON：{"rows": [检查 ID, ...]}')
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--sut', type=Path, default=HERE.parents[1], help='被测 SR 根目录')
    ap.add_argument('--exclude', action='append', default=[],
                    help='资料目录中另行排除的文件名（如原审查者的计算笔记）；可重复')
    args = ap.parse_args()
    sys.path.insert(0, str(args.sut / 'scripts'))
    import board_intent
    from plan_review import build_review_plan

    board = args.out / 'board'
    if args.out.exists():
        sys.exit(f'{args.out} 已存在；题包冻结后不覆盖')
    board.mkdir(parents=True)
    for name in INPUTS:
        if (args.source / name).exists():
            shutil.copyfile(args.source / name, board / name)
    excluded = {}
    if (args.source / 'materials').is_dir():
        (board / 'materials').mkdir()
        for item in sorted((args.source / 'materials').iterdir()):
            reason = 'listed by --exclude' if item.name in args.exclude else (
                reviewer_output(item) if item.is_file() else 'not a file')
            if reason:
                excluded[item.name] = reason
            else:
                shutil.copyfile(item, board / 'materials' / item.name)
    missing = set(args.exclude) - set(excluded)
    if missing:
        sys.exit(f'--exclude 未找到：{sorted(missing)}')
    db = json.loads((board / 'db.json').read_text())
    intent = json.loads((board / 'intent.json').read_text())
    # 旧 intent 的指纹按旧算法生成；只刷新指纹，不改任何声明。
    refreshed = intent.get('input_sha256') != board_intent.input_fingerprint(db)
    intent['input_sha256'] = board_intent.input_fingerprint(db)
    (board / 'intent.json').write_text(json.dumps(intent, ensure_ascii=False, indent=1) + '\n')
    plan = build_review_plan(db, intent)
    (board / 'review-plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=1) + '\n')

    original = {c['id']: c for c in json.loads((args.source / 'review-plan.json').read_text())['checks']}
    current = {c['id']: c for c in plan['checks']}
    rows = []
    for rid in json.loads(args.rows.read_text())['rows']:
        if rid in current:
            rows.append({'id': rid, 'source': 'regenerated', 'spec': current[rid]})
        elif rid in original:
            rows.append({'id': rid, 'source': 'original-plan', 'spec': original[rid]})
        else:
            sys.exit(f'{rid} 不在新旧计划中')
    (args.out / 'rows.json').write_text(json.dumps({'rows': rows}, ensure_ascii=False, indent=1) + '\n')
    shutil.copyfile(HERE / 'prompt.md', args.out / 'prompt.md')
    commit = subprocess.run(['git', '-C', str(args.sut), 'rev-parse', 'HEAD'],
                            capture_output=True, text=True).stdout.strip() or None
    files = sorted(p for p in args.out.rglob('*') if p.is_file())
    manifest = {'sr_commit': commit, 'source': str(args.source), 'intent_fingerprint_refreshed': refreshed,
                'excluded_materials': excluded,
                'rows': len(rows), 'regenerated_rows': sum(r['source'] == 'regenerated' for r in rows),
                'files': {str(p.relative_to(args.out)): sha(p) for p in files}}
    (args.out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + '\n')
    print(f'题包 {args.out}：{len(rows)} 行（重新生成 {manifest["regenerated_rows"]}），SR {commit}')


if __name__ == '__main__':
    main()

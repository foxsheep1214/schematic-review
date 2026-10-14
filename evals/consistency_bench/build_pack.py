#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从一份已有审查的板级数据出一致性基准题包。

题包 = 板级数据（db/intent/资料）+ 用被测 SR 重新生成的计划 + 选定行的完整规格 + 固定指令。
计划里已没有的行（原审查者手工加的行）沿用原计划的规格，并标明来源。
只拷贝审查输入，不拷贝 review-results / report / calculations / review-gate，避免先入为主。
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


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True, help='含 db.json、intent.json、review-plan.json、materials/ 的目录')
    ap.add_argument('--rows', type=Path, required=True, help='JSON：{"rows": [检查 ID, ...]}')
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--sut', type=Path, default=HERE.parents[1], help='被测 SR 根目录')
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
    if (args.source / 'materials').is_dir():
        shutil.copytree(args.source / 'materials', board / 'materials')
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
                'rows': len(rows), 'regenerated_rows': sum(r['source'] == 'regenerated' for r in rows),
                'files': {str(p.relative_to(args.out)): sha(p) for p in files}}
    (args.out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + '\n')
    print(f'题包 {args.out}：{len(rows)} 行（重新生成 {manifest["regenerated_rows"]}），SR {commit}')


if __name__ == '__main__':
    main()

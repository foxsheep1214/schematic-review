#!/usr/bin/env python3
"""Seeded-defect bench: does lint/plan notice netlist defects planted in real boards?

For every board in the prepared cache and every applicable mutation site, run the
SR cold pass (lint + plan) on the original and on the mutant and record:
  auto     - a NEW lint finding of a target rule that names the mutated site
  other    - a NEW lint finding of any other rule that names the site
  pointed  - a per-object plan check (any rule) whose object names the site, i.e.
             expert review is at least directed to the mutated part
This measures the automatic tier only; it says nothing about expert review.
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mutators  # noqa: E402


def lint(sut, db, work):
    dbp, lp, pp = work / 'db.json', work / 'lint.json', work / 'plan.json'
    dbp.write_text(json.dumps(db), encoding='utf-8')
    for p in (lp, pp):
        p.unlink(missing_ok=True)
    proc = subprocess.run([sys.executable, '-B', str(sut / 'scripts' / 'lint.py'), str(dbp),
                           '--json', str(lp), '--plan-json', str(pp)],
                          capture_output=True, text=True, timeout=120)
    if not lp.exists():
        return None, None, proc.stderr[-400:]
    plan = json.loads(pp.read_text(encoding='utf-8')) if pp.exists() else {'checks': []}
    return json.loads(lp.read_text(encoding='utf-8'))['findings'], plan['checks'], None


def located(text, tokens):
    return any(re.search(r'(?<![\w.])' + re.escape(t) + r'(?![\w])', text) for t in tokens)


def evaluate(sut, boards):
    records, baselines = [], {}
    with tempfile.TemporaryDirectory(prefix='seeded-bench-') as tmp:
        work = Path(tmp)
        for board in boards:
            db = json.loads(Path(board['db']).read_text(encoding='utf-8'))
            base, _, err = lint(sut, db, work)
            if base is None:
                baselines[board['id']] = {'error': err}
                continue
            seen = {(f['rule'], f['detail']) for f in base}
            baselines[board['id']] = {'findings': len(base),
                                      'by_rule': dict(sorted(_count(f['rule'] for f in base).items()))}
            for m in mutators.mutations(db):
                findings, checks, err = lint(sut, m.db, work)
                rec = {'board': board['id'], 'defect': m.defect, 'site': m.site, 'note': m.note,
                       'targets': list(m.targets)}
                if findings is None:
                    rec['error'] = err
                    records.append(rec)
                    continue
                tokens = m.refs + m.nets
                new = [f for f in findings if (f['rule'], f['detail']) not in seen and located(f['detail'], tokens)]
                rec['auto'] = sorted({f['rule'] for f in new if f['rule'] in m.targets})
                rec['other'] = sorted({f['rule'] for f in new if f['rule'] not in m.targets})
                rec['pointed'] = sorted({c['rule'] for c in checks if 'board' not in c.get('object', {})
                                         and located(json.dumps(c.get('object', {}), ensure_ascii=False), tokens)})
                records.append(rec)
    return records, baselines


def _count(items):
    out = defaultdict(int)
    for item in items:
        out[item] += 1
    return out


def summarize(records):
    table = {}
    for rec in records:
        row = table.setdefault(rec['defect'], {'sites': 0, 'boards': set(), 'auto': 0, 'any': 0,
                                               'pointed': 0, 'errors': 0})
        row['sites'] += 1
        row['boards'].add(rec['board'])
        if 'error' in rec:
            row['errors'] += 1
            continue
        row['auto'] += bool(rec['auto'])
        row['any'] += bool(rec['auto'] or rec['other'])
        row['pointed'] += bool(rec['pointed'])
    for row in table.values():
        row['boards'] = len(row['boards'])
    return dict(sorted(table.items()))


def report(summary, baselines, compare=None):
    lines = ['| 缺陷类型 | 电路数 | 位点 | 自动检出(目标规则) | 位点有任意新发现 | 计划有逐对象检查指向 | 运行错误 |',
             '|---|---|---|---|---|---|---|']
    for defect, row in summary.items():
        delta = ''
        if compare and defect in compare:
            delta = ' (前 %d)' % compare[defect]['auto']
        lines.append('| %s | %d | %d | %d%s | %d | %d | %d |' % (
            defect, row['boards'], row['sites'], row['auto'], delta, row['any'], row['pointed'], row['errors']))
    total = sum(r['sites'] for r in summary.values())
    auto = sum(r['auto'] for r in summary.values())
    lines += ['', '合计：%d 个位点，自动检出 %d（%.0f%%）。' % (total, auto, 100.0 * auto / max(total, 1)), '',
              '基线（未植入）发现数：' + '，'.join('%s %s' % (k, v.get('findings', 'ERR')) for k, v in baselines.items())]
    return '\n'.join(lines) + '\n'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cache', type=Path, required=True, help='directory written by prepare.py')
    ap.add_argument('--sut', type=Path, default=HERE.parents[1], help='SR checkout under test')
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--compare', type=Path, help='earlier results.json to show auto-detection deltas')
    args = ap.parse_args()
    boards = json.loads((args.cache / 'manifest.json').read_text(encoding='utf-8'))
    start = time.time()
    records, baselines = evaluate(args.sut.resolve(), boards)
    summary = summarize(records)
    compare = json.loads(args.compare.read_text(encoding='utf-8'))['summary'] if args.compare else None
    args.out.mkdir(parents=True, exist_ok=True)
    result = {'sut': str(args.sut), 'seconds': round(time.time() - start, 1), 'boards': boards,
              'baselines': baselines, 'summary': summary, 'records': records}
    (args.out / 'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding='utf-8')
    text = report(summary, baselines, compare)
    (args.out / 'report.md').write_text(text, encoding='utf-8')
    print(text + '用时 %.0f 秒' % result['seconds'])


if __name__ == '__main__':
    main()

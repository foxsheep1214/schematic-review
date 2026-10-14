#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一致性基准评分：同一题包、多个 agent、每个 agent 多次运行的结论一致性。

不判对错，只量分歧：同 agent 两次之间（模型自身波动）、不同 agent 之间（读法差异）、
PASS↔FAIL 互翻、按规则的分歧分布，以及预判 PASS 被无理由改判（门禁会拒绝的行）。
"""
import argparse
from collections import Counter, defaultdict
from itertools import combinations
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from checkers.passive_stress import OVERRIDE_CODES
from validate_review import requirement_clause_errors

VERDICTS = ('PASS', 'FAIL', 'INSUFFICIENT', 'NA')


def load_run(path, ids):
    rows = {r['id']: r for r in json.loads(Path(path).read_text())['rows']}
    errors = []
    if set(rows) != set(ids):
        errors.append(f'ID 不符：缺 {sorted(set(ids) - set(rows))}，多 {sorted(set(rows) - set(ids))}')
    errors += [f'{k}: 结论 {r.get("verdict")!r} 无效' for k, r in rows.items() if r.get('verdict') not in VERDICTS]
    return rows, errors


def agreement(a, b, ids):
    same = sum(a[i]['verdict'] == b[i]['verdict'] for i in ids)
    flips = [i for i in ids if {a[i]['verdict'], b[i]['verdict']} == {'PASS', 'FAIL'}]
    return same, flips


def gate_violations(run, specs):
    bad = []
    for rid, spec in specs.items():
        proposal = spec.get('proposal') or {}
        row = run[rid]
        override = row.get('proposal_override') or {}
        if (proposal.get('result') == 'PASS' and row['verdict'] in ('FAIL', 'INSUFFICIENT')
                and (override.get('code') not in OVERRIDE_CODES or not str(override.get('reason') or '').strip())):
            bad.append(rid)
        if spec.get('rule') == 'REQ-D01' and row['verdict'] != 'NA' and (spec.get('object') or {}).get(
                'requirement_status') not in ('OPEN', 'DEFERRED'):
            if requirement_clause_errors(rid, dict(row, review_result=row['verdict']), spec.get('criterion')):
                bad.append(rid)
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pack', type=Path, required=True)
    ap.add_argument('--run', action='append', required=True, metavar='AGENT/RUN=answers.json',
                    help='如 claude/1=out/claude-1/answers.json；同一 agent 用相同前缀')
    ap.add_argument('--out', type=Path, help='写 score.json 与 score.md 的目录')
    args = ap.parse_args()
    specs = {r['id']: r['spec'] for r in json.loads((args.pack / 'rows.json').read_text())['rows']}
    ids = sorted(specs)
    runs, problems = {}, []
    for item in args.run:
        label, _, path = item.partition('=')
        runs[label], errors = load_run(path, ids)
        problems += [f'{label}: {e}' for e in errors]
    if problems:
        sys.exit('\n'.join(problems))

    result = {'rows': len(ids), 'runs': {}, 'pairs': [], 'within_agent': None, 'between_agent': None,
              'flips': [], 'disagreement_by_rule': {}, 'disputed_rows': []}
    for label, run in runs.items():
        counts = Counter(run[i]['verdict'] for i in ids)
        result['runs'][label] = {'counts': {v: counts.get(v, 0) for v in VERDICTS},
                                 'ins_rate': round(counts.get('INSUFFICIENT', 0) / len(ids), 4),
                                 'gate_violations': gate_violations(run, specs)}
    within, between = [], []
    for (la, a), (lb, b) in combinations(runs.items(), 2):
        same, flips = agreement(a, b, ids)
        kind = 'within' if la.split('/')[0] == lb.split('/')[0] else 'between'
        (within if kind == 'within' else between).append(same / len(ids))
        result['pairs'].append({'a': la, 'b': lb, 'kind': kind, 'agree': same, 'rate': round(same / len(ids), 4),
                                'pass_fail_flips': flips})
        result['flips'] += [{'id': i, 'a': la, 'b': lb} for i in flips]
    result['within_agent'] = round(sum(within) / len(within), 4) if within else None
    result['between_agent'] = round(sum(between) / len(between), 4) if between else None
    by_rule = defaultdict(lambda: [0, 0])
    for i in ids:
        verdicts = {label: run[i]['verdict'] for label, run in runs.items()}
        rule = specs[i].get('rule') or i.split('.')[0]
        by_rule[rule][1] += 1
        if len(set(verdicts.values())) > 1:
            by_rule[rule][0] += 1
            result['disputed_rows'].append({'id': i, 'rule': rule, 'verdicts': verdicts,
                                            'proposal': (specs[i].get('proposal') or {}).get('result')})
    result['disagreement_by_rule'] = {r: {'disputed': d, 'rows': n} for r, (d, n) in
                                      sorted(by_rule.items(), key=lambda kv: (-kv[1][0], kv[0]))}

    lines = [f'# 一致性基准：{args.pack.name}', '', f'行数 {len(ids)}；运行 {", ".join(runs)}', '',
             '| 运行 | PASS | FAIL | INS | NA | INS 率 | 门禁违规 |', '|---|---|---|---|---|---|---|']
    for label, r in result['runs'].items():
        c = r['counts']
        lines.append(f"| {label} | {c['PASS']} | {c['FAIL']} | {c['INSUFFICIENT']} | {c['NA']} | "
                     f"{r['ins_rate']:.0%} | {len(r['gate_violations'])} |")
    lines += ['', '| 对比 | 类型 | 一致 | 一致率 | PASS↔FAIL |', '|---|---|---|---|---|']
    for p in result['pairs']:
        lines.append(f"| {p['a']} vs {p['b']} | {p['kind']} | {p['agree']}/{len(ids)} | {p['rate']:.0%} | "
                     f"{len(p['pass_fail_flips'])} |")
    lines += ['', f"同 agent 平均一致率：{result['within_agent']}；跨 agent 平均一致率：{result['between_agent']}",
              '', '| 规则 | 有分歧行 / 行数 |', '|---|---|']
    lines += [f'| {r} | {v["disputed"]}/{v["rows"]} |' for r, v in result['disagreement_by_rule'].items()]
    lines += ['', '## 有分歧的行', '']
    lines += [f"- {d['id']}（预判 {d['proposal']}）：" + '，'.join(f'{k}={v}' for k, v in d['verdicts'].items())
              for d in result['disputed_rows']]
    report = '\n'.join(lines) + '\n'
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / 'score.json').write_text(json.dumps(result, ensure_ascii=False, indent=1) + '\n')
        (args.out / 'score.md').write_text(report)
    print(report)


if __name__ == '__main__':
    main()

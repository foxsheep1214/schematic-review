"""Which A/E rules have a real-board positive in which bench, and which have none.

    python3 evals/bench_coverage.py [--seeded <seeded_bench results.json>] [--json out.json]

Real-board positives:
  typical   evals/typical_circuits: a frozen `expected` finding of the rule on an open board
  hot       evals/hot_bench: an evidence check of the rule frozen as FAIL (base case or numeric mutation)
  seeded    evals/seeded_bench: an injected site the rule detected (needs a results.json from run.py --out)
Synthetic only:
  contract  evals/rule_contracts: a trigger board, written for the rule, not a real circuit
A rule whose only positive is its contract has never been shown to fire on a real circuit.
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'scripts'))
import catalog  # noqa: E402

COLUMNS = ('typical', 'hot', 'seeded', 'contract')


def coverage(seeded=None):
    hits = defaultdict(lambda: defaultdict(set))
    for case in json.loads((HERE / 'typical_circuits' / 'cases.json').read_text(encoding='utf-8'))['cases']:
        for item in case.get('expected') or []:
            hits[item['rule']]['typical'].add(case['id'])
    for case in json.loads((HERE / 'hot_bench' / 'cases.json').read_text(encoding='utf-8'))['cases']:
        rule = {c['id']: c['rule'] for c in case.get('checks') or []}
        verdicts = [case.get('expected') or {}] + [m.get('expected') or {} for m in case.get('mutations') or []]
        for verdict in verdicts:
            for check, result in verdict.items():
                if result == 'FAIL' and check in rule:
                    hits[rule[check]]['hot'].add(case['id'])
    if seeded is not None:
        for rec in seeded.get('records') or []:
            for rule in rec.get('auto') or []:
                hits[rule]['seeded'].add(rec['board'])
    for path in (HERE / 'rule_contracts' / 'boards').glob('*.json'):
        hits[json.loads(path.read_text(encoding='utf-8'))['rule']]['contract'].add(path.stem)
    rules = [r.id for r in catalog.RULES if r.id[4] in 'AE']
    return {rule: {c: sorted(hits[rule][c]) for c in COLUMNS} for rule in rules}


def report(table, seeded_given):
    lines = ['| 规则 | 典型板 | 热证据板 | 注入位点 | 合同板（合成） |', '|---|---|---|---|---|']
    for rule, row in table.items():
        cell = lambda c: str(len(row[c])) if row[c] else ('—' if c != 'seeded' or seeded_given else '?')
        lines.append('| %s | %s |' % (rule, ' | '.join(cell(c) for c in COLUMNS)))
    gaps = [r for r, row in table.items() if not any(row[c] for c in COLUMNS[:3])]
    lines += ['', '无真实板正例（%d 条）：%s' % (len(gaps), '、'.join(gaps) or '无')]
    if not seeded_given:
        lines.append('未提供注入基准结果（--seeded），注入列记为“?”，缺口可能多算。')
    return '\n'.join(lines) + '\n'


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--seeded', type=Path, help='results.json written by evals/seeded_bench/run.py --out')
    ap.add_argument('--json', type=Path)
    args = ap.parse_args()
    seeded = json.loads(args.seeded.read_text(encoding='utf-8')) if args.seeded else None
    table = coverage(seeded)
    print(report(table, seeded is not None), end='')
    if args.json:
        args.json.write_text(json.dumps(table, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()

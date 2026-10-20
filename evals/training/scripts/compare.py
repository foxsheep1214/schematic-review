#!/usr/bin/env python3
"""对比两轮 metrics.json（README 第 4 节末）：↑ 指标下降、↓ 指标上升或门指标非 0 → 退出码 1。"""
import json, sys

UP = ('fix_pair_recall_cold', 'fix_pair_recall_plan', 'fix_pair_recall_hot', 'seeded_recall', 'p0_precision', 'lookup_honesty')
DOWN = ('mature_cold_false_alarms', 'misfile_rate')


def main(a_path, b_path):
    a, b = json.load(open(a_path, encoding='utf-8')), json.load(open(b_path, encoding='utf-8'))
    bad = []
    print(f'{"metric":28s} {"A":>8s} {"B":>8s}  verdict')
    for k in UP + DOWN:
        x, y = a.get(k), b.get(k)
        verdict = 'n/a'
        if x is not None and y is not None:
            worse = y < x if k in UP else y > x
            verdict = 'REGRESSION' if worse else ('same' if x == y else 'better')
            if worse:
                bad.append(k)
        print(f'{k:28s} {str(x):>8s} {str(y):>8s}  {verdict}')
    gate_t = sum((b.get('typical_gate') or {}).values()); gate_r = b.get('replay_gate')
    print(f'typical_gate(B)={gate_t} replay_gate(B)={gate_r}')
    if gate_t or gate_r:
        bad.append('gates')
    if b.get('fix_pair_recall_cold') is not None and a.get('fix_pair_recall_cold') is not None and \
            (b['fix_pair_recall_cold'] < a['fix_pair_recall_cold'] or (b.get('seeded_recall') or 0) < (a.get('seeded_recall') or 0)):
        print('召回下降：本轮按失败处理，不论过严率如何')
    print('RESULT', 'REGRESSION: ' + ', '.join(bad) if bad else 'no regression')
    return 1 if bad else 0


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit('usage: compare.py A/metrics.json B/metrics.json')
    sys.exit(main(sys.argv[1], sys.argv[2]))

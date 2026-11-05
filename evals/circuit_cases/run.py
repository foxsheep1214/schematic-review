#!/usr/bin/env python3
"""SR 跑电路评测集。

自动层（auto）：对每个有网表的案例版本解析、出计划、冷扫，记两件能机械判定的事：测试点引用的准则进没进计划；
`no_false_alarm` 测试点点名的规则有没有在该位号上报出。其余测试点要审查员判定，记 not_run，不算通过。
判定层（judged）：审查员把每个测试点的结论写成 run.json（evalset.py score 能读），再打分。

    python3 evals/circuit_cases/run.py auto --out <目录> [--case iio-can]
    python3 evals/circuit_cases/run.py score <run.json>
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'evals'))
import eval_set  # noqa: E402


def tool():
    if not eval_set.available():
        sys.exit(f'电路评测集不在 {eval_set.root()}；设 CIRCUIT_EVAL_SET 指向它')
    sys.path.insert(0, str(eval_set.root() / '工具'))
    import evalset
    return evalset


def rules_of(point):
    return [r for r in re.split(r'[/、,，\s]+', point.get('sr_rule', '')) if r]


def raised(plan, hits, rules, refs):
    """Where a named rule fired on one of the point's refs: a cold finding, or a plan question on that object."""
    wanted, seen = set(refs), []
    for hit in hits:
        if hit.get('rule') in rules and hit.get('kind') != 'INFO' and (not wanted or hit.get('ref') in wanted):
            seen.append(f"finding {hit['rule']} {hit.get('ref')}")
    for check in plan.get('checks', []):
        target = check.get('object') or {}
        members = set(target.get('refs') or [])
        # A board-wide question names every part on a small fragment; it says nothing about these refs.
        if check.get('rule') in rules and 'board' not in target and (not wanted or members & wanted):
            seen.append(f"plan {check['id']}")
    return seen


def run_variant(case, name, variant, directory, commit):
    source = eval_set.root() / '案例' / case['family'] / case['id'] / variant['netlist']
    work = Path(directory)
    db, plan_path, hits_path = work / 'db.json', work / 'plan.json', work / 'hits.json'
    subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/parse_kicad.py'), str(source), '-o', str(db)],
                   check=True, capture_output=True)
    subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/lint.py'), str(db), '--plan-json', str(plan_path),
                    '--json', str(hits_path)], check=False, capture_output=True)
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    hits = json.loads(hits_path.read_text(encoding='utf-8')).get('findings', [])
    text = plan_path.read_text(encoding='utf-8')
    results, missing = [], {}
    for point in case['test_points']:
        if name not in point['expected']:
            continue
        absent = [c for c in point.get('criteria', []) if c not in text]
        if absent:
            missing[point['id']] = absent
        if point['kind'] == 'no_false_alarm' and rules_of(point):
            refs = point.get('where', {}).get(name, {}).get('refs', [])
            seen = raised(plan, hits, rules_of(point), refs)
            results.append({'tp': point['id'], 'verdict': 'fail' if seen else 'pass', 'evidence': '；'.join(seen[:4])})
    return {'case': case['id'], 'variant': name, 'skill': 'SR', 'skill_commit': commit, 'mode': 'auto', 'results': results,
            'criteria_not_in_plan': missing}


def cmd_auto(args):
    evalset = tool()
    commit = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip()
    args.out.mkdir(parents=True, exist_ok=True)
    totals, rows = {}, []
    for _, case in evalset.load_cases():
        if args.case and case['id'] != args.case or 'SR' not in case['skills']:
            continue
        for name, variant in case['variants'].items():
            if 'netlist' not in variant:
                continue
            with tempfile.TemporaryDirectory(prefix='sr-case-') as work:
                run = run_variant(case, name, variant, work, commit)
            report = evalset.score(run, case)
            report['criteria_not_in_plan'] = run['criteria_not_in_plan']
            (args.out / f"{case['id']}.{name}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            rows.append(report)
            for key, value in report['counts'].items():
                totals[key] = totals.get(key, 0) + value
            print(case['id'], name, report['counts'], 'criteria_not_in_plan=', sum(map(len, run['criteria_not_in_plan'].values())))
    print('total', totals, 'variants', len(rows))
    (args.out / 'summary.json').write_text(json.dumps(dict(skill_commit=commit, totals=totals, variants=len(rows)), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def cmd_score(args):
    return tool().main(['score', str(args.run), '--json'])


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('auto')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--case')
    p = sub.add_parser('score')
    p.add_argument('run')
    args = parser.parse_args()
    return (cmd_auto if args.command == 'auto' else cmd_score)(args) or 0


if __name__ == '__main__':
    sys.exit(main())

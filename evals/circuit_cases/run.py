#!/usr/bin/env python3
"""SR 跑电路评测集。

自动层（auto）：对每个有网表的案例版本解析、出计划、冷扫，记两件能机械判定的事：测试点引用的准则进没进计划；
`no_false_alarm` 测试点点名的规则有没有在该位号上报出。其余测试点要审查员判定，记 not_run，不算通过。
判定层（judged）：审查员把每个测试点的结论写成 run.json（evalset.py score 能读），再打分。

    python3 evals/circuit_cases/run.py auto --out <目录> --guideline-release <发布包> [--case iio-can]
    python3 evals/circuit_cases/run.py score <run.json> --guideline-release <发布包>
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'evals'))
import eval_set  # noqa: E402


def tool():
    return eval_set.tool()

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


def run_variant(case, name, variant, directory, commit, evaluation):
    source = eval_set.root() / '案例' / case['family'] / case['id'] / variant['netlist']
    work = Path(directory)
    env = dict(os.environ)
    env.pop('GUIDELINE_CRITERIA', None)
    env.pop('GUIDELINE_CRITERIA_TESTING', None)
    db, plan_path, hits_path = work / 'db.json', work / 'plan.json', work / 'hits.json'
    subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/parse_kicad.py'), str(source), '-o', str(db)],
                   check=True, capture_output=True, env=env)
    subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/lint.py'), str(db), '--plan-json', str(plan_path),
                    '--json', str(hits_path)], check=False, capture_output=True, env=env)
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    for key in ('library_version', 'shared_sha256', 'fingerprint_format'):
        if plan.get('guidelines', {}).get(key) != evaluation['guidelines'][key]:
            raise ValueError('plan did not use selected guideline release: ' + key)
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
            'criteria_not_in_plan': missing, 'evaluation': evaluation}


def cmd_auto(args):
    evalset = tool()
    context = eval_set.context(args.guideline_release, ROOT)
    criteria, _ = evalset.binding.release_context(args.guideline_release)
    commit = context['skill']['head']
    if args.out.exists() and any(args.out.iterdir()):
        raise ValueError('evaluation output must be empty: ' + str(args.out))
    args.out.mkdir(parents=True, exist_ok=True)
    totals, rows = {}, []
    found = list(evalset.load_cases())
    if args.case and not any(c['id'] == args.case and 'SR' in c['skills'] for _, c in found):
        raise ValueError('unknown SR case: ' + args.case)
    for path, case in found:
        if args.case and case['id'] != args.case or 'SR' not in case['skills']:
            continue
        errors = evalset.check_case(path, case, criteria)
        if errors:
            raise ValueError('; '.join(errors))
        evaluation = dict(context, case_inputs=evalset.binding.case_inputs(path))
        for name, variant in case['variants'].items():
            if 'netlist' not in variant:
                continue
            with tempfile.TemporaryDirectory(prefix='sr-case-') as work:
                run = run_variant(case, name, variant, work, commit, evaluation)
            (args.out / f"{case['id']}.{name}.run.json").write_text(json.dumps(run, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            report = evalset.score(run, case)
            report['criteria_not_in_plan'] = run['criteria_not_in_plan']
            (args.out / f"{case['id']}.{name}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            rows.append(report)
            for key, value in report['counts'].items():
                totals[key] = totals.get(key, 0) + value
            print(case['id'], name, report['counts'], 'criteria_not_in_plan=', sum(map(len, run['criteria_not_in_plan'].values())))
    print('total', totals, 'variants', len(rows))
    (args.out / 'summary.json').write_text(json.dumps(dict(status='completed' if rows else 'not_run', skill_commit=commit, evaluation=context, totals=totals, variants=len(rows)), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def cmd_score(args):
    return tool().main(['score', str(args.run), '--json', '--guideline-release', str(args.guideline_release), '--skill-root', str(ROOT)])


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('auto')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--case')
    p.add_argument('--guideline-release', type=Path, required=True)
    p = sub.add_parser('score')
    p.add_argument('run')
    p.add_argument('--guideline-release', type=Path, required=True)
    args = parser.parse_args()
    return (cmd_auto if args.command == 'auto' else cmd_score)(args) or 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)

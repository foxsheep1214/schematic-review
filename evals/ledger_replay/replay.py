"""Ledger replay: real R3 review ledgers (schema 3) through the validator, quality screening and report.

    python3 evals/ledger_replay/replay.py [--json out.json] [--freeze-baseline]

`answer` fields were computed by the SR each reviewer ran (make_records.py) and are the frozen truth for
grading: summary counts, causes, every INSUFFICIENT row's potential severity, each work item's level and due
stage. `known_deviations` holds fields where the current SR is expected to differ, with the reason.
`baseline` is the current SR's quality-screening codes and report headings, frozen so a change shows up;
it is not independent truth, and --freeze-baseline rewrites it after the change has been read.
Every original gate was valid, so `grading_errors` must stay empty. The fixtures replace the project path
prefix, which changes the db's input fingerprint; the errors that follow from that (PATH_BOUND) say
nothing about grading and are left out. The report then opens with a record-error banner; its conclusion
section is still rendered from the ledger and is what the baseline keeps.
"""
import argparse
import gzip
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'scripts'))
import results_model  # noqa: E402
from render_report import render  # noqa: E402
from validate_review import validate_review  # noqa: E402

PATH_BOUND = ('stale input_sha256', 'revision input snapshot db digest mismatch')


def load(tag, name):
    with gzip.open(HERE / 'records' / tag / (name + '.json.gz'), 'rt', encoding='utf-8') as f:
        return json.load(f)


def observe(tag):
    plan, results, db = load(tag, 'review-plan'), load(tag, 'review-results'), load(tag, 'db')
    shape = results_model.shape_errors(results)
    gate = validate_review(plan, results, db)
    rows = results_model.expand(results)['checks']
    obs = {k: gate.get(k) for k in ('summary', 'insufficient_by_cause', 'categorized_summary',
                                     'requirement_clarification_summary')}
    obs['shape_errors'] = shape
    obs['grading_errors'] = [e for e in gate['errors'] if not e.endswith(PATH_BOUND)]
    obs['potential_severity'] = {r['id']: r.get('potential_severity') for r in rows if r.get('review_result') == 'INSUFFICIENT'}
    obs['work_items'] = {t['id']: [t.get('level'), t.get('due_stage')]
                         for t in (gate.get('workflow') or {}).get('work_items') or []}
    obs['quality_codes'] = dict(sorted(Counter(c['code'] for c in gate['quality_screening'].get('candidates', [])).items()))
    report = render(plan, results, gate)
    obs['report_headings'] = [line for line in report.splitlines() if line.startswith('## ') or line.startswith('### ')]
    obs['report_conclusion'] = report.split('\n## 结论\n', 1)[1].split('\n## ', 1)[0].strip().splitlines()
    return obs


def judge(obs, record):
    wanted = dict(record['answer'], shape_errors=[], **record.get('baseline', {}))
    out = {}
    for field, value in wanted.items():
        deviation = record.get('known_deviations', {}).get(field)
        if obs.get(field) == value:
            out[field] = 'MATCH'
        elif deviation is not None and obs.get(field) == deviation['value']:
            out[field] = 'KNOWN'
        else:
            out[field] = 'MISMATCH'
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--json', type=Path)
    ap.add_argument('--freeze-baseline', action='store_true')
    args = ap.parse_args()
    expected = json.loads((HERE / 'expected.json').read_text(encoding='utf-8'))
    observed, verdicts = {}, {}
    for tag, record in expected['records'].items():
        observed[tag] = observe(tag)
        if args.freeze_baseline:
            record['baseline'] = {k: observed[tag][k] for k in ('quality_codes', 'report_headings', 'report_conclusion')}
        verdicts[tag] = judge(observed[tag], record)
    if args.freeze_baseline:
        (HERE / 'expected.json').write_text(json.dumps(expected, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    bad = 0
    for tag, v in verdicts.items():
        counts = Counter(v.values())
        print('%s: 一致 %d，已知偏差 %d，不一致 %d' % (tag, counts['MATCH'], counts['KNOWN'], counts['MISMATCH']))
        for field, verdict in v.items():
            if verdict == 'MISMATCH':
                bad += 1
                print('  不一致 %s' % field)
    if args.json:
        args.json.write_text(json.dumps({'observed': observed, 'verdicts': verdicts}, ensure_ascii=False, indent=1))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())

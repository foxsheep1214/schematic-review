#!/usr/bin/env python3
"""Re-run the ledger validation on real review records and compare with a baseline.

Protects every review delivered so far from a validator change made for the
next one: a record whose validation errors grow or whose release gets worse
fails the run. Records live outside the skill (tests/regression/boards.json);
a missing folder is skipped, not failed. Nothing in a record is written.

Per record: validation errors from a fresh validate_review run with the
SKILL.md step 7 flags, the count of each review_result (PASS / FAIL /
INSUFFICIENT / NA) in review-results.json, the release of the fresh run and
the release written in record/review-gate.json.

  run_regression.py                      # compare with tests/regression/baseline.json
  run_regression.py --update-baseline    # accept the current numbers
"""

import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from electrical_contract import load_json  # noqa: E402
from validate_review import RESULTS, validate_review  # noqa: E402

REG = HERE.parent / 'tests' / 'regression'
RELEASE_RANK = {'GO': 0, 'CONDITIONAL_GO': 1, 'NO_GO': 3}
LINTS = ('lint-cold.json', 'lint-hot.json')


def rank(release):
    return RELEASE_RANK.get(release, 2)


def measure(board):
    record = Path(board['path']).expanduser() / 'record'
    if not (record / 'review-results.json').is_file():
        return {'status': 'SKIPPED', 'reason': 'not on this machine: %s' % record}
    try:
        plan, results = load_json(str(record / 'review-plan.json')), load_json(str(record / 'review-results.json'))
        db = load_json(str(record / 'db.json')) if (record / 'db.json').is_file() else None
        lint = [load_json(str(record / x)) for x in LINTS if (record / x).is_file()] or None
        verdict = validate_review(plan, results, db, lint, require_actionable=True, require_bindings=True,
                                  require_current_engine=True)
    except (ValueError, OSError, TypeError) as exc:
        verdict = {'valid': False, 'release': 'NO_GO', 'errors': [str(exc)]}
        results = {}
    counts = Counter(c.get('review_result') for c in results.get('checks') or [] if isinstance(c, dict))
    gate_path = record / 'review-gate.json'
    recorded = load_json(str(gate_path)).get('release') if gate_path.is_file() else None
    return {'status': 'MEASURED', 'validation_errors': len(verdict['errors']),
            'results': {k: counts.get(k, 0) for k in sorted(RESULTS)},
            'release': verdict['release'], 'recorded_release': recorded, 'error_lines': verdict['errors']}


def compare(current, base):
    reasons = []
    if current['validation_errors'] > base.get('validation_errors', 0):
        reasons.append('validation errors %d -> %d' % (base.get('validation_errors', 0), current['validation_errors']))
    before = base.get('release')
    if before is not None and rank(current['release']) > rank(before):
        reasons.append('release %s -> %s' % (before, current['release']))
    return reasons


def run(boards_path=REG / 'boards.json', baseline_path=REG / 'baseline.json', update=False):
    boards = json.loads(Path(boards_path).read_text(encoding='utf-8'))['boards']
    baseline = json.loads(Path(baseline_path).read_text(encoding='utf-8')) if Path(baseline_path).is_file() else {'boards': {}}
    results, new_base, overall = {}, {}, 'PASS'
    for board in boards:
        m = measure(board)
        if m['status'] == 'SKIPPED':
            results[board['id']] = m
            if board['id'] in baseline['boards']:
                new_base[board['id']] = baseline['boards'][board['id']]
            continue
        slim = {k: m[k] for k in ('validation_errors', 'results', 'release', 'recorded_release')}
        base = baseline['boards'].get(board['id'])
        if base is None:
            m['status'], m['reasons'] = 'NEW', ['no baseline yet; run with --update-baseline']
        else:
            reasons = compare(slim, base)
            m['status'], m['reasons'] = ('FAIL' if reasons else 'PASS'), reasons
            if not reasons and slim['validation_errors'] < base.get('validation_errors', 0):
                m['reasons'] = ['improved; run with --update-baseline to lower the bar']
        if m['status'] == 'FAIL' or (m['status'] == 'NEW' and overall != 'FAIL'):
            overall = m['status']
        results[board['id']] = m
        new_base[board['id']] = slim
    if update:
        Path(baseline_path).write_text(json.dumps({'generated': date.today().isoformat(), 'boards': new_base},
                                                  ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        overall = 'UPDATED'
    return {'status': overall, 'boards': results}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--boards', type=Path, default=REG / 'boards.json')
    ap.add_argument('--baseline', type=Path, default=REG / 'baseline.json')
    ap.add_argument('--update-baseline', action='store_true')
    ap.add_argument('--verbose', action='store_true', help='print every validation error')
    args = ap.parse_args(argv)
    report = run(args.boards, args.baseline, args.update_baseline)
    for board_id, m in report['boards'].items():
        line = '%-12s %s' % (board_id, m['status'])
        if m['status'] != 'SKIPPED':
            line += '  errors %d, results %s, release %s (recorded %s)' % (
                m['validation_errors'], ','.join('%s=%d' % kv for kv in m['results'].items()),
                m['release'], m['recorded_release'])
        print(line)
        for r in m.get('reasons') or ([m['reason']] if m.get('reason') else []):
            print('    ' + r)
        if args.verbose:
            for e in m.get('error_lines') or []:
                print('    error: ' + e)
    print(report['status'])
    return 1 if report['status'] == 'FAIL' else 0


if __name__ == '__main__':
    sys.exit(main())

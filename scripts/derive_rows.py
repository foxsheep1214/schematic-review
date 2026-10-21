#!/usr/bin/env python3
"""Rows follow their function verdict (docs/2026-10-20-function-verdicts-design.md §5).

    python3 scripts/derive_rows.py review-plan.json review-results.json -o review-results.json

Every plan row bound to a function (`function_id`, set by the planner for circuit members or by the
reviewer) gets its result from that function: a fail item whose `decides` covers the row's aspect
and state makes it FAIL, an open item makes it INSUFFICIENT with `open_ref`, otherwise it is PASS
with a rationale that points at the verdict. Rows the reviewer filled by hand are left alone and
only compared; a disagreement is reported, never overwritten. Rows outside any function stay manual.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from electrical_contract import load_json
from results_model import text
from review_functions import decides_row, judged, unjudged_message

DERIVED_FIELDS = ('review_result', 'open_ref', 'fail_ref', 'finding_id', 'severity')


def _handoff(fn, planned):
    """A planned handoff is carried by the function's first handoff; the function must have one."""
    if not (planned.get('handoff') or {}).get('required'):
        return {'required': False}, None
    handoffs = fn.get('handoffs') or []
    if not handoffs or not isinstance(handoffs[0], dict):
        return None, '%s: the plan requires a handoff and function %s lists none' % (planned['id'], fn['id'])
    first = handoffs[0]
    return {'required': True, 'state': 'OPEN', 'receivers': list(first.get('receivers') or []),
            'constraint': first.get('constraint'), 'verification': first.get('verification')}, None


def derive_row(fn, planned, aspect, findings):
    """The row `planned` takes from function `fn` for `aspect`; returns (row, error)."""
    state = (planned.get('object') or {}).get('state')
    where = '%s（%s%s）' % (fn['id'], aspect, ('，' + state) if state else '')
    row = {'id': planned['id'], 'applicability': 'APPLICABLE',
           'binding': {'object': planned.get('object'), 'criterion': planned.get('criterion')},
           'function_id': fn['id'], 'aspect': aspect, 'evidence': fn.get('evidence'), 'derived': True}
    handoff, error = _handoff(fn, planned)
    if error:
        return None, error
    row['handoff'] = handoff
    for item in fn.get('fails') or []:
        if isinstance(item, dict) and decides_row(item, aspect, state):
            finding = findings.get(item.get('finding_id'))
            if finding is None:
                return None, '%s: fail item %s names finding %s, which the results do not list' % (
                    planned['id'], item.get('key'), item.get('finding_id'))
            row.update(review_result='FAIL', fail_ref='%s/%s' % (fn['id'], item['key']),
                       finding_id=item['finding_id'], severity=finding.get('severity'),
                       rationale='见功能判定 %s：发现项 %s——%s' % (where, item['finding_id'], item.get('what') or ''))
            return row, None
    for item in fn.get('open') or []:
        if isinstance(item, dict) and decides_row(item, aspect, state):
            row.update(review_result='INSUFFICIENT', open_ref='%s/%s' % (fn['id'], item['key']),
                       rationale='见功能判定 %s：开放项 %s——%s' % (where, item['key'], item.get('what') or ''))
            return row, None
    basis = judged(fn, aspect, state)
    if basis is None:
        return None, unjudged_message(planned['id'], fn['id'], aspect, state)
    row.update(review_result='PASS', rationale='见功能判定 %s：%s' % (where, basis))
    return row, None


def derive(plan, results):
    """Derive or check every bound row; returns (results, summary, errors). `results` is updated in place."""
    functions = {fn['id']: fn for fn in results.get('functions') or [] if isinstance(fn, dict) and text(fn.get('id'))}
    findings = {f['id']: f for f in results.get('findings') or [] if isinstance(f, dict) and text(f.get('id'))}
    rows = {r['id']: r for r in results.get('checks') or [] if isinstance(r, dict) and text(r.get('id'))}
    summary = {'derived': 0, 'kept': 0, 'PASS': 0, 'FAIL': 0, 'INSUFFICIENT': 0}
    errors = []
    for planned in plan.get('checks') or []:
        if not isinstance(planned, dict) or planned.get('applicability') != 'APPLICABLE':
            continue
        existing = rows.get(planned.get('id'))
        fid = (existing or {}).get('function_id') or planned.get('function_id')
        if fid is None:
            continue
        fn = functions.get(fid)
        if fn is None:
            errors.append('%s: function_id %s names no function verdict' % (planned['id'], fid))
            continue
        aspect = (existing or {}).get('aspect') or planned.get('aspect')
        if not text(aspect):
            errors.append('%s: a bound row names the aspect it covers' % planned['id'])
            continue
        row, error = derive_row(fn, planned, aspect, findings)
        if error:
            errors.append(error)
            continue
        if existing is not None and existing.get('review_result') and not existing.get('derived'):
            summary['kept'] += 1
            for field in DERIVED_FIELDS:
                if existing.get(field) != row.get(field):
                    errors.append('%s: hand-filled %s %r disagrees with function %s (%r)'
                                  % (planned['id'], field, existing.get(field), fid, row.get(field)))
            continue
        if existing is not None:
            for field in ('manual_verification', 'notes', 'handoff_evidence', 'applicability_evidence'):
                if field in existing:
                    row[field] = existing[field]
            existing.clear()
            existing.update(row)
        else:
            results.setdefault('checks', []).append(row)
            rows[row['id']] = row
        summary['derived'] += 1
        summary[row['review_result']] += 1
    return results, summary, errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('plan')
    parser.add_argument('results')
    parser.add_argument('-o', '--out', help='where to write the results (default: print the summary only)')
    args = parser.parse_args(argv)
    plan, results = load_json(args.plan), load_json(args.results)
    results, summary, errors = derive(plan, results)
    if args.out and not errors:
        Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('派生 %d 行（PASS %d、FAIL %d、INSUFFICIENT %d），手填保留 %d 行' % (
        summary['derived'], summary['PASS'], summary['FAIL'], summary['INSUFFICIENT'], summary['kept']))
    for error in errors:
        print('ERROR ' + error)
    if errors and args.out:
        print('有错误，未写出 ' + args.out)
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())

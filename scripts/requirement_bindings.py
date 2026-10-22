#!/usr/bin/env python3
"""Requirement rows bound to the tree checks that carry their aspect (fixed requirements, step 4).

An aspect names the tree rules that carry it (catalog.ASPECT_RULES). A requirement row is bound to the rows of those
rules owned by the circuits, interfaces or system functions the requirement names (`owners`); with no owners, an
aspect of the whole board (catalog.BOARD_ASPECTS) is bound to every row of its rules and any other aspect to none.
A bound requirement row is not judged again: its result is the worst result of its bound rows that are not NA, and
it is judged on its own (with clauses) only when no bound row is. The planner writes `bound_checks`, the validator
recomputes them, and derive_rows.py writes the bound requirement rows.
"""
import catalog

ORDER = {'PASS': 1, 'INSUFFICIENT': 2, 'FAIL': 3}
COPIED = ('review_result', 'open_ref', 'fail_ref', 'finding_id', 'severity', 'evidence')


def bound(checks, row):
    """The ids of the rows a requirement row is bound to."""
    aspect = (row.get('object') or {}).get('aspect')
    rules = catalog.ASPECT_RULES.get(aspect, ())
    owners = row.get('requirement_owners') or []
    if not rules or not (owners or aspect in catalog.BOARD_ASPECTS):
        return []
    return sorted(c['id'] for c in checks if c.get('rule') in rules and c.get('applicability') == 'APPLICABLE'
                  and (not owners or (c.get('owner') or {}).get('id') in owners))


def attach(checks):
    for row in checks:
        if row.get('rule') == 'REQ-D01':
            row['bound_checks'] = bound(checks, row)


def errors(plan):
    checks = [c for c in plan.get('checks') or [] if isinstance(c, dict)]
    owned = {(c.get('owner') or {}).get('id') for c in checks} - {None}
    out = []
    for row in checks:
        if row.get('rule') != 'REQ-D01':
            continue
        for owner in row.get('requirement_owners') or []:
            if owner not in owned:
                out.append('%s: requirement owner %s owns no row of the plan (name a circuit, interface or system function)'
                           % (row.get('id'), owner))
        if (row.get('bound_checks') or []) != bound(checks, row):
            out.append('%s: bound_checks differ from the rows of %s its owners carry; rebuild the plan'
                       % (row.get('id'), '、'.join(catalog.ASPECT_RULES.get((row.get('object') or {}).get('aspect'), ())) or '—'))
    return out


def _judged(planned, rows):
    found = [rows[cid] for cid in planned.get('bound_checks') or [] if isinstance(rows.get(cid), dict)]
    return [r for r in found if r.get('review_result') in ORDER]


def derived_result(planned, rows):
    """The worst result of the bound rows that are not NA; None when no bound row is judged."""
    judged = _judged(planned, rows)
    return max((r['review_result'] for r in judged), key=ORDER.get) if judged else None


def derive(plan, results):
    """Write or check every bound requirement row; returns (count, errors). `results` is updated in place."""
    rows = {r.get('id'): r for r in results.get('checks') or [] if isinstance(r, dict)}
    findings = {f.get('id'): f for f in results.get('findings') or [] if isinstance(f, dict)}
    count, errors = 0, []
    for planned in plan.get('checks') or []:
        if planned.get('rule') != 'REQ-D01' or (planned.get('object') or {}).get('requirement_status') in ('OPEN', 'DEFERRED'):
            continue
        result = derived_result(planned, rows)
        if result is None:
            continue
        worst = next(r for r in _judged(planned, rows) if r['review_result'] == result)
        row = {'id': planned['id'], 'applicability': 'APPLICABLE', 'derived': True,
               'binding': {'object': planned.get('object'), 'criterion': planned.get('criterion')},
               'derived_from': [r['id'] for r in _judged(planned, rows)],
               'rationale': '需求方面由绑定行承担：%s；结论取其中最差者（%s）' % ('、'.join(planned['bound_checks']), worst['id'])}
        row.update({k: worst[k] for k in COPIED if k in worst})
        existing = rows.get(planned['id'])
        if existing is not None and existing.get('review_result') and not existing.get('derived'):
            if existing['review_result'] != result:
                errors.append('%s: hand-filled review_result %r disagrees with its bound rows (%r)'
                              % (planned['id'], existing['review_result'], result))
            continue
        if existing is not None:
            existing.clear()
            existing.update(row)
        else:
            results.setdefault('checks', []).append(row)
            rows[row['id']] = row
        if result == 'FAIL' and row.get('finding_id') in findings:
            ids = findings[row['finding_id']].setdefault('check_ids', [])
            if planned['id'] not in ids:
                ids.append(planned['id'])
        count += 1
    return count, errors

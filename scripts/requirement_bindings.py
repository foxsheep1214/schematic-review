#!/usr/bin/env python3
"""Requirement rows bound to the tree checks that carry their aspect (fixed requirements, step 4).

An aspect names the tree rules that carry it (catalog.ASPECT_RULES). A requirement row is bound to the rows of those
rules owned by the circuits, interfaces or system functions the requirement names (`owners`); with no owners, an
aspect of the whole board (catalog.BOARD_ASPECTS) is bound to every row of its rules and any other aspect to none.
A bound requirement row is not judged again: its result is the worst result of its bound rows that are not NA, and
it is judged on its own (with clauses) only when no bound row is. The planner writes `bound_checks`, the validator
recomputes them, and derive_rows.py writes the bound requirement rows.

A circuit-type coverage row (REQ-Q07) is bound the same way to the applicable rows of its circuit type (consistency
proposals of 2026-10-23, 5b). It answers coverage only: once every bound row has a result it passes, and it copies no
member's result, so a defect stays on the row whose margin proves it and the reviewer does not pick one for it.
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


def _interface_kinds(interfaces):
    items = interfaces.get('interfaces') if isinstance(interfaces, dict) else interfaces
    return {i['id']: i.get('kind') for i in items or () if isinstance(i, dict) and i.get('id')}


def candidates(checks, row, owners_table, interfaces=None):
    """The owners a requirement row could name (可承接的电路): the circuits of the aspect's types, the system functions
    and the interface kinds its cell of catalog.ASPECT_OWNER_TYPES lists, that own an applicable row of the aspect's
    rules. Owners outside the cell are not candidates; board aspects have none."""
    aspect = (row.get('object') or {}).get('aspect')
    rules = catalog.ASPECT_RULES.get(aspect, ())
    cell = catalog.ASPECT_OWNER_TYPES.get(aspect)
    if not rules or aspect in catalog.BOARD_ASPECTS or cell is None:
        return []
    types = {e['id']: e.get('type') for e in owners_table or () if e.get('kind') == 'CIRCUIT'}
    kinds = _interface_kinds(interfaces)
    found = {}
    for c in checks:
        owner = c.get('owner') or {}
        if c.get('rule') not in rules or c.get('applicability') != 'APPLICABLE' or not owner.get('id'):
            continue
        label = {'CIRCUIT': types.get(owner['id']), 'SYSTEM': owner['id'], 'INTERFACE': kinds.get(owner['id'])}.get(owner['kind'])
        allowed = {'CIRCUIT': cell.circuits, 'SYSTEM': cell.systems, 'INTERFACE': cell.interfaces}.get(owner['kind'], ())
        if label not in allowed:
            continue
        entry = {'id': owner['id'], 'kind': owner['kind']}
        if owner['kind'] != 'SYSTEM':
            entry['type'] = label
        found[owner['id']] = entry
    return [found[k] for k in sorted(found)]


def self_judged(row):
    """Why a requirement row with carrying rules is judged on its own: NO_OWNER_CANDIDATE, DECLARED (owners: []), or
    None when it is bound (or has no carrying rule)."""
    aspect = (row.get('object') or {}).get('aspect')
    if not catalog.ASPECT_RULES.get(aspect) or aspect in catalog.BOARD_ASPECTS:
        return None
    if row.get('requirement_owners'):
        return None
    if row.get('requirement_owners') == []:
        return 'DECLARED'
    return None if row.get('owner_candidates') else 'NO_OWNER_CANDIDATE'


def missing_owner_errors(checks):
    """Requirement rows with candidate owners and no `owners` written (not even `[]`); OPEN and DEFERRED requirements
    are exempt, their rows are never derived."""
    by_requirement = {}
    for row in checks:
        if row.get('rule') != 'REQ-D01' or 'requirement_owners' in row or not row.get('owner_candidates'):
            continue
        if row['object'].get('requirement_status') in ('OPEN', 'DEFERRED'):
            continue   # its rows stay INSUFFICIENT + REQUIREMENT_OPEN and are never derived
        rid = row['object']['requirement_id']
        by_requirement.setdefault(rid, ([], {}))
        by_requirement[rid][0].append(row['object']['aspect'])
        for c in row['owner_candidates']:
            by_requirement[rid][1][c['id']] = c
    out = []
    for rid, (aspects, found) in sorted(by_requirement.items()):
        named = '、'.join('%s（%s）' % (c['id'], c.get('type') or c['kind']) for c in found.values())
        out.append('requirement.%s.owners 缺：方面 %s 可承接的电路是 %s（它们拥有承担该方面的检查项）；写上承接电路后需求检查项由这些检查项派生。'
                   '认定没有承接电路的写 owners: [] 并给能定位的 no_owner_reason' % (rid, '/'.join(aspects), named))
    return out


def outside_candidates(checks):
    """Diagnostics: requirement rows whose owners are not among their candidates (allowed; the reviewer may know better)."""
    out = []
    for row in checks:
        if row.get('rule') != 'REQ-D01' or not row.get('requirement_owners') or not row.get('owner_candidates'):
            continue
        ids = {c['id'] for c in row['owner_candidates']}
        outside = [o for o in row['requirement_owners'] if o not in ids]
        if outside:
            out.append({'code': 'REQUIREMENT_OWNER_OUTSIDE_CANDIDATES', 'requirement': row['object']['requirement_id'],
                        'aspect': row['object']['aspect'], 'owners': outside, 'candidates': sorted(ids),
                        'detail': '需求 %s 的方面 %s 的承接电路 %s 不在计划找到的可承接电路里（%s）；确认它们确实承接这条需求' % (
                            row['object']['requirement_id'], row['object']['aspect'], '、'.join(outside), '、'.join(sorted(ids)))})
    return out


def circuit_type(row):
    obj = row.get('object') if isinstance(row.get('object'), dict) else {}
    return row.get('circuit_type') or obj.get('circuit_type')


def coverage_bound(checks, row):
    """The ids of the applicable rows of a coverage row's circuit type."""
    package = circuit_type(row)
    return sorted(c['id'] for c in checks if c.get('rule') != COVERAGE and c.get('applicability') == 'APPLICABLE'
                  and package and circuit_type(c) == package)


COVERAGE = 'REQ-Q07'
BINDERS = {'REQ-D01': bound, COVERAGE: coverage_bound}


def attach(checks, owners_table=None, interfaces=None):
    for row in checks:
        if row.get('rule') in BINDERS:
            row['bound_checks'] = BINDERS[row['rule']](checks, row)
        if row.get('rule') == 'REQ-D01':
            row['owner_candidates'] = candidates(checks, row, owners_table, interfaces)
            reason = self_judged(row)
            if reason:
                row['self_judged'] = reason
            else:
                row.pop('self_judged', None)


def errors(plan):
    checks = [c for c in plan.get('checks') or [] if isinstance(c, dict)]
    owned = {(c.get('owner') or {}).get('id') for c in checks} - {None}
    out = []
    for row in checks:
        if row.get('rule') == COVERAGE and (row.get('bound_checks') or []) != coverage_bound(checks, row):
            out.append('%s: bound_checks differ from the applicable rows of circuit type %s; rebuild the plan'
                       % (row.get('id'), circuit_type(row)))
        if row.get('rule') != 'REQ-D01':
            continue
        for owner in row.get('requirement_owners') or []:
            if owner not in owned:
                out.append('%s: requirement owner %s owns no row of the plan (name a circuit, interface or system function)'
                           % (row.get('id'), owner))
        if (row.get('bound_checks') or []) != bound(checks, row):
            out.append('%s: bound_checks differ from the rows of %s its owners carry; rebuild the plan'
                       % (row.get('id'), '、'.join(catalog.ASPECT_RULES.get((row.get('object') or {}).get('aspect'), ())) or '—'))
        if (row.get('owner_candidates') or []) != candidates(checks, row, plan.get('owners'), plan.get('interfaces')):
            out.append('%s: owner_candidates differ from the owners of the applicable rows its aspect\'s rules have; rebuild the plan'
                       % row.get('id'))
        if row.get('self_judged') != self_judged(row):
            out.append('%s: self_judged must be %s' % (row.get('id'), self_judged(row) or 'absent'))
    out.extend(missing_owner_errors(checks))
    return out


def _judged(planned, rows):
    found = [rows[cid] for cid in planned.get('bound_checks') or [] if isinstance(rows.get(cid), dict)]
    return [r for r in found if r.get('review_result') in ORDER]


def units_of(aspect):
    """The unit spellings of the aspect's requirement parameters (µ and u alike); empty for an aspect without them."""
    out = set()
    for name in catalog.REQUIREMENT_ASPECTS[aspect].parameters if aspect in catalog.REQUIREMENT_ASPECTS else ():
        parameter = catalog.REQUIREMENT_PARAMETERS[name]
        out |= {u.replace('µ', 'u') for u in (parameter.unit, *parameter.units)}
    return out


def _counted(planned, rows, counts=None):
    """The judged bound rows whose result reaches the requirement row: `counts(planned, row)` says whether a FAIL on
    another quantity of the same part is kept out (function_reading.fail_counts); without it every judged row counts."""
    return [r for r in _judged(planned, rows) if counts is None or counts(planned, r)]


def derived_result(planned, rows, counts=None):
    """The worst result of the bound rows that are not NA and whose failure concerns this aspect (`counts`, see
    _counted); PASS when every judged row is a failure on another quantity; None when no bound row is judged."""
    judged = _judged(planned, rows)
    if not judged:
        return None
    counted = _counted(planned, rows, counts)
    return max((r['review_result'] for r in counted), key=ORDER.get) if counted else 'PASS'


def coverage_result(planned, rows):
    """PASS once every bound row has a result and one of them is not NA; None before that (or with no bound row)."""
    found = [rows.get(cid) for cid in planned.get('bound_checks') or []]
    if not found or not all(isinstance(r, dict) and r.get('review_result') in (*ORDER, 'NA') for r in found):
        return None
    return 'PASS' if any(r['review_result'] != 'NA' for r in found) else None


def coverage_errors(expected, rows):
    """A hand-filled coverage row agrees with its coverage result."""
    out = []
    for cid, planned in expected.items():
        if planned.get('rule') != COVERAGE or not isinstance(rows.get(cid), dict):
            continue
        derived = coverage_result(planned, rows)
        result = rows[cid].get('review_result')
        if derived is not None and result != derived:
            out.append('%s: 功能电路覆盖只答同类电路各检查项（%s）是否都已审，各检查项都有结论即为 %s，不复制子项结论，不是 %s；'
                       '用 derive_rows.py 写出' % (cid, '、'.join(planned.get('bound_checks') or []), derived, result))
    return out


def derive(plan, results, counts=None):
    """Write or check every bound requirement row; returns (count, errors). `results` is updated in place; `counts`
    is the fail filter (function_reading.fail_filter), None keeps every bound result."""
    rows = {r['id']: r for r in results.get('checks') or [] if isinstance(r, dict) and isinstance(r.get('id'), str)}
    findings = {f['id']: f for f in results.get('findings') or [] if isinstance(f, dict) and isinstance(f.get('id'), str)}
    count, errors = 0, []
    for planned in plan.get('checks') or []:
        if planned.get('rule') not in BINDERS or (planned.get('object') or {}).get('requirement_status') in ('OPEN', 'DEFERRED'):
            continue
        coverage = planned['rule'] == COVERAGE
        result = coverage_result(planned, rows) if coverage else derived_result(planned, rows, counts)
        if result is None:
            continue
        row = {'id': planned['id'], 'applicability': 'APPLICABLE', 'derived': True,
               'binding': {'object': planned.get('object'), 'criterion': planned.get('criterion')},
               'derived_from': [r['id'] for r in _judged(planned, rows)]}
        if coverage:
            row.update(review_result=result, rationale='功能电路覆盖：同类电路各检查项（%s）都已审，结论留在各检查项，不复制'
                                                       % '、'.join(planned['bound_checks']),
                       evidence=[{'source': 'review-results.json', 'locator': 'checks ' + ', '.join(planned['bound_checks'])}])
        else:
            counted = _counted(planned, rows, counts)
            left_out = [r['id'] for r in _judged(planned, rows) if r not in counted]
            worst = next((r for r in counted if r['review_result'] == result), None)
            if worst is None:   # every judged row failed on another quantity
                row.update(review_result=result,
                           rationale='需求方面由绑定检查项承担：%s；失败检查项 %s 的失败边不在本方面的量上（单位 %s），不继承，本方面无失败'
                                     % ('、'.join(planned['bound_checks']), '、'.join(left_out),
                                        '/'.join(sorted(units_of(planned['object'].get('aspect'))))))
            else:
                row['rationale'] = '需求方面由绑定检查项承担：%s；结论取其中最差者（%s）' % ('、'.join(planned['bound_checks']), worst['id'])
                if left_out:
                    row['rationale'] += '；%s 的失败边不在本方面的量上，不继承' % '、'.join(left_out)
                row.update({k: worst[k] for k in COPIED if k in worst})
        existing = rows.get(planned['id'])
        if (existing is not None and existing.get('derived') and existing.get('function_id')
                and ORDER.get(existing.get('review_result'), 0) > ORDER[result]):
            # a function's gap or failure on the requirement row itself is worse than the bound rows: it stands
            # (R8 codex1: a function's open item on the requirement row was overwritten by two passing bound rows)
            continue
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

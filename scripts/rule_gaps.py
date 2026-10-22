"""A row the reviewer adds is a rule gap (fixed requirements, step 7).

A reviewer who thinks something is to be checked that the plan does not ask registers it in intent.rule_gaps: the
object, the catalog rule it is judged under, the criterion, what rule or derivation the tool lacks and the basis. The
planner writes it as a REVIEWER_ADDED row, judged like any other row, counted apart and left out of the pairing rate
of two records; the gate lists the gaps for the improvement ledger, where each becomes a rule the tool writes. A row
the planner did not write (outside the automatic-scan rows and the revision records) is refused.
"""
from copy import deepcopy

import catalog
import revision_impact

ORIGIN = 'REVIEWER_ADDED'
FIELDS = ('id', 'rule', 'object', 'criterion', 'missing', 'basis')


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def errors(intent, db=None):
    gaps = intent.get('rule_gaps', [])
    if not isinstance(gaps, list):
        return ['rule_gaps 必须为数组：每项写 id、rule、object、criterion、missing、basis']
    out, seen = [], set()
    parts = (db or {}).get('parts') if isinstance(db, dict) else None
    for index, item in enumerate(gaps):
        label = 'rule_gaps[%d]' % index
        if not isinstance(item, dict):
            out.append(label + ' 必须为 object')
            continue
        for field in ('id', 'rule', 'criterion', 'missing', 'basis'):
            if not _text(item.get(field)):
                out.append('%s.%s 缺失' % (label, field))
        for field in sorted(set(item) - set(FIELDS)):
            out.append('%s.%s 不认识：只写 %s' % (label, field, '、'.join(FIELDS)))
        if _text(item.get('id')):
            if item['id'] in seen:
                out.append('%s.id %s 重复' % (label, item['id']))
            seen.add(item['id'])
        rule = item.get('rule')
        if _text(rule) and not catalog.known(rule):
            out.append('%s.rule %s 不在规则总表里：写按哪条规则判' % (label, rule))
        elif rule == 'REQ-D01':
            out.append('%s.rule REQ-D01 不写：需求行由 requirement_source 的需求与类别生成；缺的方面登记成别的规则' % label)
        obj = item.get('object')
        if not isinstance(obj, dict) or not obj:
            out.append('%s.object 必须为非空 object（位号、网或功能）' % label)
        elif isinstance(parts, dict):
            refs = ([obj['ref']] if 'ref' in obj else []) + list(obj.get('refs') or [])
            for ref in refs:
                if ref not in parts:
                    out.append('%s.object 的位号 %s 不在网表里' % (label, ref))
    return out


def plan(planner):
    """Write one REVIEWER_ADDED row per registered gap."""
    for item in planner.intent.get('rule_gaps') or []:
        row = planner.add_check(item['rule'], deepcopy(item['object']), key='GAP-' + item['id'],
                                criterion=item['criterion'], trigger=['rule_gap:' + item['id']])
        row['origin'] = ORIGIN
        row['rule_gap'] = {'id': item['id'], 'missing': item['missing'], 'basis': item['basis']}


def added(checks):
    return [c for c in checks if isinstance(c, dict) and c.get('origin') == ORIGIN]


def unwritten(row):
    """A row outside what the planner writes may stand only as an automatic-scan row or a revision record."""
    return not ('lint_kind' in row or revision_impact.is_revision_check(row) or 'prior_check' in row
                or 'prior_checks' in row)


def message(cid):
    return ('%s: 这一行不是计划工具写的；要补的检查登记到 intent.rule_gaps（对象、按哪条规则判、判据、缺什么规则、依据），'
            '重新生成计划' % cid)


def listing(plan, results):
    """The gaps of this review with their results, for the improvement ledger."""
    rows = results.get('checks') if isinstance(results.get('checks'), list) else []
    answered = {c['id']: c for c in rows if isinstance(c, dict) and isinstance(c.get('id'), str)}
    return [dict(check_id=row['id'], rule=row['rule'], **row['rule_gap'],
                 result=(answered.get(row['id']) or {}).get('review_result'))
            for row in added(plan.get('checks') or []) if isinstance(row.get('rule_gap'), dict)]

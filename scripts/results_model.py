"""review-results.json (schema 6): what the reviewer writes, and the view the validators read.

The unit of judgement is a function verdict (`functions[]`): the question one circuit block must
answer, the datasheet clauses that bear on it, the calculation and its margin, the verdict and the
open items that remain. Check rows are the coverage ledger: a row bound to a function carries
`function_id`, `aspect` and, when it is INSUFFICIENT or FAIL, `open_ref` / `fail_ref` naming the
function item that decides it. Fields of a function verdict are validated by review_functions.py.

Derived here (never written):
  blocking             true for FAIL/INSUFFICIENT, false otherwise; write false only on a FAIL/INSUFFICIENT
                       that does not block (a P2/P3 the phase allows to stay open)
  evidence_confidence  B for PASS/FAIL, C for INSUFFICIENT; write it only to claim A
  disposition          OPEN; write it only for FIXED_VERIFIED / ACCEPTED / RETRACTED
  gap_cause, gaps, missing_inputs, input_requests, potential_severity, impact_assessment
                       from the open item the row's open_ref names
  work_items           one per open/fail item of every function (ids keep the W- prefix)
"""
import copy
from collections import Counter

SCHEMA_VERSION = 6
LEVELS = ('P0', 'P1', 'P2', 'P3')
REQUEST_CAUSES = ('EXTERNAL_DATA', 'DESIGN_OPEN')
# Fields schema 3 derives; a record that still writes them would carry two answers to one question.
RETIRED_ROW_FIELDS = {
    'missing_inputs': 'functions[].open[].what', 'input_requests': 'functions[].open', 'potential_severity': 'functions[].open[].severity.level',
    'impact_assessment': 'functions[].open[].severity',
    # schema 4: the gap lives once, on the function's open item; the row names it with open_ref
    'gaps': 'open_ref', 'gap_cause': 'functions[].open[].kind',
    'obligations': 'functions[].open[].decides', 'qualification_members': 'functions[].conditions',
}
RETIRED_TOP_FIELDS = ('binding_version', 'remediation_version', 'workflow_version', 'impact_class_version',
                      'requirement_clauses_version', 'requirement_clarification_version',
                      # lint findings are plan checks with their own result rows
                      'lint_reviews',
                      # schema 4: work items are derived from the functions' open/fail items
                      'work_items')
OPEN_KINDS = ('DESIGN_VALUE', 'VENDOR_DATUM', 'DELIVERABLE_PENDING', 'REQUIREMENT', 'REVIEW_INCOMPLETE', 'USER_DEFERRED')
KIND_CAUSE = {'DESIGN_VALUE': 'DESIGN_OPEN', 'VENDOR_DATUM': 'EXTERNAL_DATA', 'DELIVERABLE_PENDING': 'DELIVERABLE_PENDING',
              'REQUIREMENT': 'REQUIREMENT_OPEN', 'REVIEW_INCOMPLETE': 'REVIEW_INCOMPLETE', 'USER_DEFERRED': 'USER_DEFERRED'}
VERDICTS = ('PASS', 'FAIL', 'OPEN')
PHASES = ('design_iteration', 'schematic_freeze', 'prototype_verification')
# Schema 3 always means the newest contract of each retired switch: consequence classes v2,
# REQ-D01 clauses, staged work items. Bindings and actionable instructions are required by
# validate_review's --require-bindings/--require-actionable.
IMPACT_CLASS_VERSION = 2
GAP_TEXT = ('what', 'scope', 'how_to_close', 'closure_criterion')
SEVERITY_TEXT = ('affects', 'consequence')


def text(value):
    return isinstance(value, str) and bool(value.strip())


def margins(calculation):
    """calculation.margin as a list: one {value, unit, against[, aspect]} or one per aspect."""
    margin = calculation.get('margin') if isinstance(calculation, dict) else None
    items = margin if isinstance(margin, list) else [margin] if margin is not None else []
    return [m for m in items if isinstance(m, dict) and m.get('value') is not None]


def shape_errors(report, history_ids=()):
    """Errors in the record as written, named in the current format's terms. `history_ids` are REQ-H02 rows,
    which carry history dispositions instead of open items."""
    if not isinstance(report, dict):
        return ['results must be an object']
    if report.get('schema_version') != SCHEMA_VERSION:
        return ['results.schema_version must be %d; an older ledger is not read, review again with this SR'
                % SCHEMA_VERSION]
    errors = ['results.%s is retired in schema 4 (the newest meaning always applies)' % k
              for k in RETIRED_TOP_FIELDS if k in report]
    if not isinstance(report.get('functions'), list):
        errors.append('results.functions must be a list of function verdicts (empty when the review has none)')
    refs = function_refs(report)
    for row in report.get('checks') or []:
        if not isinstance(row, dict):
            continue
        key = str(row.get('id', '?'))
        for field, instead in RETIRED_ROW_FIELDS.items():
            if field in row:
                errors.append('%s: %s is retired in schema 4; write %s' % (key, field, instead))
        if 'blocking' in row and not (row['blocking'] is False and row.get('review_result') in ('FAIL', 'INSUFFICIENT')):
            errors.append(key + (': on an NA row (stage NA included) omit blocking, it is derived false' if row.get('review_result') == 'NA'
                                 else ': blocking is derived; write it only as false on a FAIL/INSUFFICIENT that does not block'))
        if row.get('evidence_confidence') in ('B', 'C'):
            errors.append(key + ': evidence_confidence is derived; write it only to claim A')
        if row.get('disposition') == 'OPEN':
            errors.append(key + ': disposition OPEN is the default; omit it')
        result = row.get('review_result')
        for field in ('open_ref', 'fail_ref'):
            if field in row and not (isinstance(row[field], str) and row[field] in refs[field]):
                errors.append('%s: %s must name an existing functions[].%s item as "FN-ID/KEY"'
                              % (key, field, 'open' if field == 'open_ref' else 'fails'))
        if 'function_id' in row and not text(row.get('aspect')):
            errors.append(key + ': a row bound to a function names the aspect it covers')
        if result == 'INSUFFICIENT' and key not in history_ids and 'open_ref' not in row:
            errors.append(key + ': INSUFFICIENT names the function open item that decides it (open_ref)')
        if result != 'INSUFFICIENT' and 'open_ref' in row:
            errors.append(key + ': open_ref only belongs to INSUFFICIENT')
        if result != 'FAIL' and 'fail_ref' in row:
            errors.append(key + ': fail_ref only belongs to FAIL')
        for field in ('open_ref', 'fail_ref'):
            if field in row and row[field] in refs[field] and 'function_id' in row \
                    and row['function_id'] != row[field].split('/', 1)[0]:
                errors.append('%s: %s belongs to another function than function_id' % (key, field))
    return errors


def function_refs(report):
    """'FN-ID/KEY' for every open and fail item, as rows name them."""
    out = {'open_ref': set(), 'fail_ref': set()}
    for fn in report.get('functions') or []:
        if not isinstance(fn, dict) or not text(fn.get('id')):
            continue
        for field, items in (('open_ref', fn.get('open')), ('fail_ref', fn.get('fails'))):
            for item in items or []:
                if isinstance(item, dict) and text(item.get('key')):
                    out[field].add(fn['id'] + '/' + item['key'])
    return out


def open_items(report):
    """{'FN-ID/KEY': (function, item, 'open'|'fails')}."""
    out = {}
    for fn in report.get('functions') or []:
        if not isinstance(fn, dict) or not text(fn.get('id')):
            continue
        for field in ('open', 'fails'):
            for item in fn.get(field) or []:
                if isinstance(item, dict) and text(item.get('key')):
                    out[fn['id'] + '/' + item['key']] = (fn, item, field)
    return out


def work_item_id(key):
    return key if key.startswith('W-') else 'W-' + key


# What kind of gap an open item is, for the reader (commodity-floors / P10): who closes it, and for a vendor datum
# which way the public bound leans. Requirement, review-incomplete and deferred items keep their cause words.
GAP_SUBCLASSES = {'DESIGN_DECISION': '设计还要定', 'CONFIGURATION': '等配置表', 'PART_DRAWING': '等定制件图纸',
                  'PUBLIC_BOUND_SHORT': '按公开资料界限算不够', 'PUBLIC_BOUND_UNGUARANTEED': '按公开资料界限算够，但不是保证值',
                  'NOT_BOUNDABLE': '公开资料定不出界限'}


def gap_subclass(item):
    kind = item.get('kind')
    if kind == 'DESIGN_VALUE':
        return 'DESIGN_DECISION'
    if kind == 'DELIVERABLE_PENDING':
        return 'PART_DRAWING' if item.get('deliverable_kind') == 'CUSTOM_PART_DRAWING' else 'CONFIGURATION'
    if kind == 'VENDOR_DATUM':
        worst = item.get('worst_case') if isinstance(item.get('worst_case'), dict) else {}
        if text(worst.get('not_boundable_reason')):
            return 'NOT_BOUNDABLE'
        margin = worst.get('margin') if isinstance(worst.get('margin'), dict) else {}
        value = margin.get('value')
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return 'PUBLIC_BOUND_SHORT' if value < 0 else 'PUBLIC_BOUND_UNGUARANTEED'
    return None   # a datum with neither a margin nor an unboundable reason is not classed


def condition_place(fn, cid):
    """Where a condition of `fn` stands, for the reader (file name and locator); its id when the function lacks it."""
    condition = next((c for c in fn.get('conditions') or [] if isinstance(c, dict) and c.get('id') == cid), None)
    if not condition:
        return cid
    return ' '.join(x for x in (str(condition.get('source') or '').rsplit('/', 1)[-1], condition.get('locator')) if text(x)) or cid


def blocked_judgements(item, fn):
    """What a gap holds open, for the reader: aspects blocked for the same reason share one line listing their entry
    points (the condition's source and locator, not its internal id). The item's heading already names the gap, so
    a reason that restates it is cut back to what it adds, and a sentence that only swaps in the aspect name
    ("<gap>; this datum enters <aspect>") adds nothing and is not printed."""
    def entry(via):
        if via.get('condition'):
            return condition_place(fn, via['condition'])
        return '/'.join(x for x in (via.get('claim'), via.get('input')) if x)

    what = (item.get('what') or '').strip()
    punct = ' ；;，,。.：:'

    def reason(d):
        r = d['rationale'].strip()
        return r.replace(what, '').strip(punct) if what and what in r else r

    edges = [d for d in item.get('decides') or []
             if isinstance(d, dict) and d.get('effect', 'BLOCKS_PROOF') == 'BLOCKS_PROOF' and text(d.get('rationale'))]
    # A reason that reads the same once its own aspect is masked out is one template filled per aspect.
    masked = Counter(reason(d).replace(str(d.get('aspect') or ''), '\0') for d in edges
                     if what and what in d['rationale'] and str(d.get('aspect') or '') in reason(d))
    groups = {}
    for d in edges:
        why = reason(d)
        if what and what in d['rationale'] and masked.get(why.replace(str(d.get('aspect') or ''), '\0'), 0) > 1:
            why = ''
        states = '、'.join(d['states']) if isinstance(d.get('states'), list) else ''
        aspects, throughs = groups.setdefault(why, ([], []))
        aspects.append('%s%s' % (d.get('aspect'), '（%s）' % states if states else ''))
        throughs.append(entry(d.get('via') if isinstance(d.get('via'), dict) else {}))
    out = []
    for why, (aspects, throughs) in groups.items():
        through = '、'.join(t for t in dict.fromkeys(throughs) if t)
        out.append('%s%s%s' % ('、'.join(dict.fromkeys(aspects)), '，经 %s' % through if through else '',
                               '：' + why if why else ''))
    return out


def effective_verdicts(functions, plan, checks):
    """{function id: (verdict, work ids)} as the report counts it. A plan frame's function follows its member rows:
    a member left open or failed under another function (delegated) makes the frame OPEN or FAIL, naming the work
    item that holds the row, so moving a row out cannot make the circuit read as passed."""
    rows = {c['id']: c for c in checks or [] if isinstance(c, dict) and text(c.get('id'))}
    frames = {f['id']: f for f in (plan or {}).get('functions') or [] if isinstance(f, dict) and text(f.get('id'))}
    out = {}
    for fn in functions or []:
        if not isinstance(fn, dict) or not text(fn.get('id')):
            continue
        verdict, ids = fn.get('verdict'), []
        for member in (frames.get(fn['id']) or {}).get('members') or []:
            row = rows.get(member.get('check_id')) if isinstance(member, dict) else None
            if not isinstance(row, dict) or row.get('function_id') in (None, fn['id']):
                continue
            result = row.get('review_result')
            if result == 'FAIL':
                verdict, ref = 'FAIL', row.get('fail_ref')
            elif result == 'INSUFFICIENT':
                verdict, ref = ('OPEN' if verdict == 'PASS' else verdict), row.get('open_ref')
            else:
                continue
            if text(ref) and work_item_id(ref.split('/', 1)[-1]) not in ids:   # a ref is '<function id>/<key>'
                ids.append(work_item_id(ref.split('/', 1)[-1]))
        out[fn['id']] = (verdict, ids)
    return out


def how_to_close(item):
    if item.get('kind') == 'DESIGN_VALUE':
        return '由%s确定：%s' % (item.get('owner') or '设计', item.get('spec') or '')
    if item.get('kind') == 'DELIVERABLE_PENDING':
        return '由%s交付：%s' % (item.get('owner') or '设计', item.get('deliverable') or '')
    return item.get('acquisition')


def gap_of(item):
    """The row-level gap an open item stands for (the row shape the validators and the report read)."""
    gap = {'what': item.get('what'), 'scope': item.get('scope')}
    if item.get('kind') in ('DESIGN_VALUE', 'VENDOR_DATUM', 'DELIVERABLE_PENDING'):
        gap['how_to_close'] = how_to_close(item)
        gap['closure_criterion'] = item.get('closure')
    if isinstance(item.get('severity'), dict):
        gap['severity'] = item['severity']
    return {k: v for k, v in gap.items() if v is not None}


def lead_ref(items, ref):
    """The open item whose rows these are: a design value that hangs on another open item (depends_on) is counted
    there (bounding consistency proposals, item 3)."""
    found = items.get(ref)
    target = found[1].get('depends_on') if found and found[2] == 'open' else None
    for other, (_, item, field) in items.items():
        if target and field == 'open' and item.get('key') == target:
            return other
    return ref


def derived_work_items(report):
    """One work item per open/fail item; rows that name the item are its check_ids."""
    items = open_items(report)
    owners = {}
    for row in report.get('checks') or []:
        if isinstance(row, dict):
            for field in ('open_ref', 'fail_ref'):
                if isinstance(row.get(field), str):
                    owners.setdefault(lead_ref(items, row[field]), []).append(row.get('id'))
    out = []
    for ref, (fn, item, field) in items.items():
        if field == 'open' and item.get('kind') == 'REQUIREMENT':
            continue  # requirement gaps are managed by clarification records
        if lead_ref(items, ref) != ref:
            continue  # hung on another item, which carries its rows
        severity = item.get('severity') if isinstance(item.get('severity'), dict) else {}
        if field == 'open':
            next_action = how_to_close(item) or item.get('what')
        else:
            next_action = '按发现项 %s 的改法处理' % item.get('finding_id')
        task = {'id': work_item_id(item['key']), 'function_id': fn['id'], 'key': item['key'],
                'title': item.get('title') or item.get('what'), 'root_cause': item.get('what'),
                'reason': item.get('why') or severity.get('consequence') or item.get('what'),
                'next_action': next_action, 'due_stage': item.get('due_stage', 'design_iteration'),
                'check_ids': owners.get(ref, []), 'evidence': fn.get('evidence')}
        if 'design_option' in item:
            task['design_option'] = item['design_option']
        if gap_subclass(item):
            task['subclass'] = gap_subclass(item)
        if item.get('kind') == 'DELIVERABLE_PENDING':   # no input request carries these into the report
            task.update(assumed=item.get('assumed'), required_scope=item.get('scope'), closure_criterion=item.get('closure'))
        # Every exit from a margin reaches the reader: the worst case under the public bound, and why it did not decide.
        worst = item.get('worst_case') if isinstance(item.get('worst_case'), dict) else {}
        bound = worst.get('bound') if isinstance(worst.get('bound'), dict) else {}
        if text(worst.get('result')):
            task['worst_case'] = worst['result'] + (
                '（界：%s，%s）' % (bound.get('value'), condition_place(fn, bound.get('condition'))) if bound.get('value') else '')
        reached = blocked_judgements(item, fn)
        if reached:
            task['blocks'] = reached
        out.append(task)
    out.extend(document_work_items(report))
    return out


def document_work_items(report):
    """A document FAIL stands on its own row, not in a function (functions answer circuits): its finding is the
    work item, holding every unbound document row that names it."""
    findings = {f['id']: f for f in report.get('findings') or [] if isinstance(f, dict) and text(f.get('id'))}
    rows = {}
    for row in report.get('checks') or []:
        if (isinstance(row, dict) and row.get('review_result') == 'FAIL' and str(row.get('id', '')).startswith('DOC-')
                and row.get('function_id') is None and row.get('finding_id') in findings):
            rows.setdefault(row['finding_id'], []).append(row)
    out = []
    for fid, linked in rows.items():
        finding = findings[fid]
        evidence = [e for row in linked for e in row.get('evidence') or []]
        out.append({'id': work_item_id(fid), 'title': finding.get('title'), 'root_cause': finding.get('root_cause'),
                    'reason': finding.get('impact') or finding.get('severity_reason'),
                    'next_action': '按发现项 %s 的改法处理' % fid, 'due_stage': 'design_iteration',
                    'check_ids': [row['id'] for row in linked], 'evidence': evidence or finding.get('evidence')})
    return out


def _impact(gap):
    s = gap.get('severity') or {}
    out = {'affected_function': s.get('affects'), 'operating_condition': gap.get('scope'),
           'consequence': s.get('consequence'),
           # Retired prose fields: the consequence is the reason for the level, the criterion the reason it blocks.
           'severity_reason': s.get('consequence'),
           'blocking_reason': gap.get('closure_criterion') or s.get('consequence'),
           'consequence_class': s.get('class')}
    for key in ('hazard_path', 'exclusion'):
        if key in s:
            out[key] = s[key]
    return out


def _worst(gaps):
    graded = [g for g in gaps if isinstance(g.get('severity'), dict) and g['severity'].get('level') in LEVELS]
    return min(graded, key=lambda g: LEVELS.index(g['severity']['level'])) if graded else None


def expand(report):
    """The validators' view of a record (call after shape_errors is clean)."""
    out = copy.deepcopy(report)
    out.setdefault('requirement_clarifications', [])
    items = open_items(out)
    if 'functions' in out or 'work_items' not in out:   # written work items are refused; a bare dict keeps its own
        out['work_items'] = derived_work_items(out)
    for row in out.get('checks') or []:
        if not isinstance(row, dict):
            continue
        result = row.get('review_result')
        ref = items.get(lead_ref(items, row['open_ref'])) if isinstance(row.get('open_ref'), str) else None
        if result == 'INSUFFICIENT' and ref is not None:
            row['gap_cause'] = KIND_CAUSE.get(ref[1].get('kind'))
            row['gaps'] = [gap_of(ref[1])]
        row.setdefault('blocking', result in ('FAIL', 'INSUFFICIENT'))
        if result in ('PASS', 'FAIL'):
            row.setdefault('evidence_confidence', 'B')
        elif result == 'INSUFFICIENT':
            row.setdefault('evidence_confidence', 'C')
        row.setdefault('disposition', 'OPEN')
        gaps = row.pop('gaps', None)
        if result != 'INSUFFICIENT' or not isinstance(gaps, list):
            continue
        gaps = [g for g in gaps if isinstance(g, dict)]
        row['missing_inputs'] = [g.get('what') for g in gaps]
        if row.get('gap_cause') in REQUEST_CAUSES:
            row['input_requests'] = {g.get('what'): {
                'why_decisive': row.get('rationale'), 'required_scope': g.get('scope'),
                'acquisition': g.get('how_to_close'), 'closure_criterion': g.get('closure_criterion'),
                'potential_severity': (g.get('severity') or {}).get('level'),
                'impact_assessment': _impact(g),
                **({'closure_domain': g['closure_domain']} if 'closure_domain' in g else {})} for g in gaps}
        worst = _worst(gaps)
        if worst is not None:
            row['potential_severity'] = worst['severity']['level']
            row['impact_assessment'] = _impact(worst)
    return out

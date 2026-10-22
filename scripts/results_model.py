"""review-results.json schema 4: what the reviewer writes, and the view the validators read.

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

SCHEMA_VERSION = 4
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
    """Errors in the record as written, named in schema 4 terms. `history_ids` are REQ-H02 rows,
    which carry history dispositions instead of open items."""
    if not isinstance(report, dict):
        return ['results must be an object']
    if report.get('schema_version') != SCHEMA_VERSION:
        return ['results.schema_version must be 4; an older ledger is not read, review again with this SR']
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
            errors.append(key + ': blocking is derived; write it only as false on a FAIL/INSUFFICIENT that does not block')
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


def how_to_close(item):
    if item.get('kind') == 'DESIGN_VALUE':
        return '由%s确定：%s' % (item.get('owner') or '设计', item.get('spec') or '')
    if item.get('kind') == 'DELIVERABLE_PENDING':
        return '由%s交付：%s' % (item.get('owner') or '设计', item.get('deliverable') or '')
    return item.get('acquisition')


def gap_of(item):
    """The row-level gap an open item stands for (schema 3 shape, for the validators and the report)."""
    gap = {'what': item.get('what'), 'scope': item.get('scope')}
    if item.get('kind') in ('DESIGN_VALUE', 'VENDOR_DATUM', 'DELIVERABLE_PENDING'):
        gap['how_to_close'] = how_to_close(item)
        gap['closure_criterion'] = item.get('closure')
    if isinstance(item.get('severity'), dict):
        gap['severity'] = item['severity']
    return {k: v for k, v in gap.items() if v is not None}


def derived_work_items(report):
    """One work item per open/fail item; rows that name the item are its check_ids."""
    owners = {}
    for row in report.get('checks') or []:
        if isinstance(row, dict):
            for field in ('open_ref', 'fail_ref'):
                if isinstance(row.get(field), str):
                    owners.setdefault(row[field], []).append(row.get('id'))
    out = []
    for ref, (fn, item, field) in open_items(report).items():
        if field == 'open' and item.get('kind') == 'REQUIREMENT':
            continue  # requirement gaps are managed by clarification records
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
        if item.get('kind') == 'DELIVERABLE_PENDING':   # no input request carries these into the report
            task.update(assumed=item.get('assumed'), required_scope=item.get('scope'), closure_criterion=item.get('closure'))
        # Every exit from a margin reaches the reader: the worst case under the public bound, and why it did not decide.
        worst = item.get('worst_case') if isinstance(item.get('worst_case'), dict) else {}
        bound = worst.get('bound') if isinstance(worst.get('bound'), dict) else {}
        if text(worst.get('result')):
            task['worst_case'] = worst['result'] + (
                '（界：%s，%s）' % (bound.get('value'), bound.get('condition')) if bound.get('value') else '')
        reached = []
        for d in item.get('decides') or []:
            if isinstance(d, dict) and d.get('effect', 'BLOCKS_PROOF') == 'BLOCKS_PROOF' and text(d.get('rationale')):
                via = d.get('via') if isinstance(d.get('via'), dict) else {}
                through = via.get('condition') or '/'.join(x for x in (via.get('claim'), via.get('input')) if x)
                states = '、'.join(d['states']) if isinstance(d.get('states'), list) else ''
                reached.append('%s%s%s：%s' % (d.get('aspect'), '（%s）' % states if states else '',
                                              '，经 %s' % through if through else '', d['rationale']))
        if reached:
            task['blocks'] = reached
        out.append(task)
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
    """The validators' view of a schema 4 record (call after shape_errors is clean)."""
    out = copy.deepcopy(report)
    out.setdefault('requirement_clarifications', [])
    items = open_items(out)
    if 'functions' in out or 'work_items' not in out:   # written work items are refused; a bare dict keeps its own
        out['work_items'] = derived_work_items(out)
    for row in out.get('checks') or []:
        if not isinstance(row, dict):
            continue
        result = row.get('review_result')
        ref = items.get(row.get('open_ref')) if isinstance(row.get('open_ref'), str) else None
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

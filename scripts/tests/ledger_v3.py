"""Test-side bridge: the older test builders write rows in the expanded (validator) view; the
validator reads schema 4. `record` writes such a ledger the way a reviewer writes schema 4 — the
gaps and work items the builder stated become function verdicts with open/fail items, and the rows
name them — so a test still states its case in the fields it is about. Not used by SR itself."""
import copy
import re

import catalog
import results_model
import validate_review as _validate_review

SYNTHETIC = [{'source': 'synthetic-fixture.json', 'locator': 'all values stipulated for tests'}]
CAUSE_KIND = {v: k for k, v in results_model.KIND_CAUSE.items()}

DEFAULTS = {'PASS': 'B', 'FAIL': 'B', 'INSUFFICIENT': 'C'}


# Older builders predate consequence classes; give them the class their level already implies,
# so a test that is not about classes still states a consistent row. Tests about classes set one.
LEVEL_CLASS = {'P0': 'CORE_LINK_LOSS', 'P1': 'REQUIRED_FUNCTION', 'P2': 'LOCAL_OR_DATA', 'P3': 'OPTIMIZATION'}


def _severity(level, assessment):
    assessment = assessment if isinstance(assessment, dict) else {}
    if 'consequence_class' not in assessment and level in LEVEL_CLASS:
        assessment = dict(assessment, consequence_class=LEVEL_CLASS[level])
        if level == 'P0':
            assessment.setdefault('hazard_path', 'PROTECTION_LOSS')
    out = {'level': level, 'class': assessment.get('consequence_class'),
           'affects': assessment.get('affected_function'), 'consequence': assessment.get('consequence')}
    for key in ('hazard_path', 'exclusion'):
        if key in assessment:
            out[key] = assessment[key]
    return {k: v for k, v in out.items() if v is not None}


def _gaps(row):
    requests, missing = row.get('input_requests'), row.get('missing_inputs')
    if isinstance(requests, dict) and requests:
        keys = [k for k in missing if k in requests] if isinstance(missing, list) else list(requests)
        keys += [k for k in requests if k not in keys]
        gaps = []
        for key in keys:
            req = requests[key] if isinstance(requests[key], dict) else {}
            gap = {'what': key, 'scope': req.get('required_scope'), 'how_to_close': req.get('acquisition'),
                   'closure_criterion': req.get('closure_criterion'), 'closure_domain': req.get('closure_domain')}
            level = req.get('potential_severity', row.get('potential_severity'))
            assessment = req.get('impact_assessment', row.get('impact_assessment'))
            if level is not None or assessment is not None:
                gap['severity'] = _severity(level, assessment)
            gaps.append({k: v for k, v in gap.items() if v is not None})
        return gaps
    if not isinstance(missing, list):
        return None
    gaps = []
    for key in missing:
        gap = {'what': key}
        assessment = row.get('impact_assessment')
        if isinstance(assessment, dict) and assessment.get('operating_condition'):
            gap['scope'] = assessment['operating_condition']
        if row.get('potential_severity') is not None or isinstance(assessment, dict):
            gap['severity'] = _severity(row.get('potential_severity'), assessment)
        gaps.append(gap)
    return gaps


def _slug(value):
    return re.sub(r'[^A-Za-z0-9_.-]+', '-', str(value)).strip('-') or 'X'


def _aspect(plan, row):
    rule = str(row.get('id', '')).split('.')[0]
    try:
        return catalog.title(rule)
    except Exception:  # unknown synthetic rule
        return 'general'


def _objects(plan, cids):
    refs, nets = [], []
    for c in (plan or {}).get('checks') or []:
        if isinstance(c, dict) and c.get('id') in cids and isinstance(c.get('object'), dict):
            o = c['object']
            refs += [x for x in ([o.get('ref')] if isinstance(o.get('ref'), str) else []) + list(o.get('refs') or []) if isinstance(x, str)]
            nets += [x for x in ([o.get('net')] if isinstance(o.get('net'), str) else []) + list(o.get('nets') or []) if isinstance(x, str)]
    return {'refs': list(dict.fromkeys(refs)) or ['SYNTHETIC']} if not nets or refs else {'nets': list(dict.fromkeys(nets))}


def _open_item(key, rows, task):
    """One open item for the gaps a task (or an orphan row) owns; the row gaps were written in schema 3 shape."""
    gaps = [g for row in rows for g in row.get('gaps') or []]
    cause = rows[0].get('gap_cause')
    kind = CAUSE_KIND.get(cause, 'REVIEW_INCOMPLETE')
    whats = list(dict.fromkeys(g.get('what') for g in gaps if g.get('what')))
    first = gaps[0] if gaps else {}
    item = {'key': key, 'kind': kind, 'what': '；'.join(whats) or (task or {}).get('root_cause') or 'Synthetic gap',
            'decides': [{'aspect': a} for a in dict.fromkeys(r['aspect'] for r in rows)]}
    if task:
        item['title'] = task.get('title')
        if task.get('reason'):
            item['why'] = task['reason']
        if task.get('due_stage'):
            item['due_stage'] = task['due_stage']
        if 'design_option' in task:
            item['design_option'] = task['design_option']
    if kind != 'REQUIREMENT':
        sev = first.get('severity') or {}
        item['severity'] = {'level': sev.get('level'), 'class': sev.get('class'),
                            'affects': sev.get('affects'), 'consequence': sev.get('consequence') or 'Synthetic consequence'}
        for k in ('hazard_path', 'exclusion'):
            if k in sev:
                item['severity'][k] = sev[k]
        item['severity'] = {k: v for k, v in item['severity'].items() if v is not None}
    if first.get('scope'):
        item['scope'] = first['scope']
    if kind in ('DESIGN_VALUE', 'VENDOR_DATUM'):
        item['closure'] = first.get('closure_criterion')
        if kind == 'DESIGN_VALUE':
            item['spec'] = first.get('how_to_close')
            item['owner'] = 'Synthetic designer'
        else:
            item['acquisition'] = first.get('how_to_close')
            item['checked'] = ['c1']
            item['why_insufficient'] = 'Synthetic: the stipulated clause does not give the datum'
            item['worst_case'] = {'result': 'Synthetic worst case stated by the fixture'}
    if kind == 'USER_DEFERRED':
        item['instruction'] = SYNTHETIC
    return {k: v for k, v in item.items() if v is not None}


def _functions(out, plan):
    """Function verdicts from the legacy work_items and the INSUFFICIENT/FAIL rows they own."""
    rows = {r['id']: r for r in out.get('checks') or [] if isinstance(r, dict) and isinstance(r.get('id'), str)}
    tasks = [t for t in out.get('work_items') or [] if isinstance(t, dict) and isinstance(t.get('id'), str)]
    for row in rows.values():
        if row.get('review_result') in ('INSUFFICIENT', 'FAIL'):
            row.setdefault('aspect', _aspect(plan, row))
    functions, owned = [], set()
    for task in tasks:
        cids = [c for c in task.get('check_ids') or [] if c in rows and rows[c].get('review_result') in ('INSUFFICIENT', 'FAIL')]
        if not cids or any(c in owned for c in cids):
            continue   # a malformed or shared task stays as the builder wrote it: the validator names it
        owned.update(cids)
        fid = 'FN-' + _slug(task['id'])
        fn = {'id': fid, 'question': task.get('title') or 'Synthetic question', 'objects': _objects(plan, cids),
              'conditions': [{'id': 'c1', 'source': 'synthetic-fixture.json', 'locator': 'stipulated clause',
                              'says': 'stipulated', 'use': 'stipulated'}],
              'no_calculation_reason': 'synthetic fixture', 'evidence': task.get('evidence') or SYNTHETIC,
              'open': [], 'fails': []}
        ins = [rows[c] for c in cids if rows[c].get('review_result') == 'INSUFFICIENT']
        fails = [rows[c] for c in cids if rows[c].get('review_result') == 'FAIL']
        if ins:
            fn['open'].append(_open_item(task['id'], ins, task))
            for r in ins:
                r['function_id'], r['open_ref'] = fid, fid + '/' + task['id']
        for r in fails:
            key = task['id'] if not ins and len(fails) == 1 else task['id'] + '-' + _slug(r['id'])
            fn['fails'].append({'key': key, 'finding_id': r.get('finding_id'), 'what': task.get('root_cause') or 'Synthetic defect',
                                'title': task.get('title'), 'decides': [{'aspect': r['aspect']}],
                                **{k: task[k] for k in ('due_stage', 'design_option') if k in task},
                                **({'why': task['reason']} if task.get('reason') else {})})
            r['function_id'], r['fail_ref'] = fid, fid + '/' + key
        fn['verdict'] = 'FAIL' if fn['fails'] else 'OPEN'
        functions.append(fn)
    orphans = [cid for cid, row in rows.items()
               if row.get('review_result') == 'INSUFFICIENT' and cid not in owned and row.get('gaps') is not None]
    for cid, row in rows.items():
        if row.get('review_result') == 'FAIL' and cid not in owned and (functions or orphans) and row.get('finding_id'):
            # Legacy builders left FAIL rows outside any task while the workflow was disabled; the
            # functions above enable it, so the defect gets the function the reviewer would write.
            fid = 'FN-' + _slug(cid)
            functions.append({'id': fid, 'question': 'Synthetic question for ' + cid, 'objects': _objects(plan, [cid]),
                              'conditions': [{'id': 'c1', 'source': 'synthetic-fixture.json', 'locator': 'stipulated clause',
                                              'says': 'stipulated', 'use': 'stipulated'}],
                              'no_calculation_reason': 'synthetic fixture', 'evidence': SYNTHETIC, 'open': [],
                              'fails': [{'key': _slug(cid), 'finding_id': row['finding_id'], 'what': 'Synthetic defect',
                                         'decides': [{'aspect': row['aspect']}]}], 'verdict': 'FAIL'})
            row['function_id'], row['fail_ref'] = fid, fid + '/' + _slug(cid)
        if row.get('review_result') == 'INSUFFICIENT' and cid not in owned and row.get('gaps') is not None:
            fid = 'FN-' + _slug(cid)
            functions.append({'id': fid, 'question': 'Synthetic question for ' + cid, 'objects': _objects(plan, [cid]),
                              'conditions': [{'id': 'c1', 'source': 'synthetic-fixture.json', 'locator': 'stipulated clause',
                                              'says': 'stipulated', 'use': 'stipulated'}],
                              'no_calculation_reason': 'synthetic fixture', 'evidence': SYNTHETIC,
                              'open': [_open_item(_slug(cid), [row], None)], 'fails': [], 'verdict': 'OPEN'})
            row['function_id'], row['open_ref'] = fid, fid + '/' + _slug(cid)
    return functions


def record(report, plan=None):
    if not isinstance(report, dict) or report.get('schema_version') == results_model.SCHEMA_VERSION:
        return report
    out = copy.deepcopy(report)
    if out.get('schema_version') in (2, 3):
        out['schema_version'] = results_model.SCHEMA_VERSION
    for key in results_model.RETIRED_TOP_FIELDS:
        if key != 'work_items':
            out.pop(key, None)
    for row in out.get('checks') or []:
        if not isinstance(row, dict):
            continue
        result = row.get('review_result')
        if row.get('blocking') is True or (row.get('blocking') is False and result not in ('FAIL', 'INSUFFICIENT')):
            row.pop('blocking')
        if row.get('evidence_confidence') == DEFAULTS.get(result if isinstance(result, str) else None) or (
                result == 'NA' and row.get('evidence_confidence') in (None, 'B', 'C')):
            row.pop('evidence_confidence', None)
        if row.get('disposition') == 'OPEN':
            row.pop('disposition')
        if result == 'INSUFFICIENT':
            gaps = _gaps(row)
            if gaps is not None:
                row['gaps'] = gaps
            for key in ('missing_inputs', 'input_requests', 'potential_severity', 'impact_assessment'):
                row.pop(key, None)
    if 'functions' not in out:
        out['functions'] = _functions(out, plan)
    out.pop('work_items', None)
    for row in out.get('checks') or []:
        if isinstance(row, dict):
            for key in ('gaps', 'gap_cause', 'obligations', 'qualification_members'):
                row.pop(key, None)
    return out


def _whole_clauses(plan, report):
    """Older builders predate requirement_clauses. A REQ-D01 row that never mentions them gets the
    requirement as one obligation with the row's own result; tests about clauses always set the key."""
    rules = {c.get('id'): c for c in (plan or {}).get('checks') or [] if isinstance(c, dict) and isinstance(c.get('id'), str)}
    for row in report.get('checks') or []:
        planned = rules.get(row.get('id')) if isinstance(row, dict) and isinstance(row.get('id'), str) else None
        if (planned and planned.get('rule') == 'REQ-D01' and 'requirement_clauses' not in row
                and row.get('review_result') in ('PASS', 'FAIL', 'INSUFFICIENT')):
            row['requirement_clauses'] = [{'text': planned.get('criterion'), 'kind': 'OBLIGATION',
                                           'result': row['review_result']}]


def as_sent(plan, report):
    """The schema 4 ledger these test helpers hand to validate_review."""
    report = record(report, plan)
    if isinstance(report, dict):
        report = copy.deepcopy(report)
        _whole_clauses(plan, report)
    return report


def validate_review(plan, report, *args, **kwargs):
    return _validate_review.validate_review(plan, as_sent(plan, report), *args, **kwargs)

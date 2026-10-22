"""Test-side bridge: the older test builders write rows in the expanded (validator) view; the
validator reads schema 4. `record` writes such a ledger the way a reviewer writes schema 4 — the
gaps and work items the builder stated become function verdicts with open/fail items, and the rows
name them — so a test still states its case in the fields it is about. Not used by SR itself."""
import copy
import re

import catalog
import results_model
import validate_review as _validate_review
from review_functions import document_row

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


def _objects(plan, cids, rows=None):
    """The parts and nets of the rows a synthetic function answers, from the plan or, without one, from the
    rows' own binding objects (a reviewer lists what the function is about; F11 holds the rows to it)."""
    refs, nets = [], []
    planned = [c for c in (plan or {}).get('checks') or [] if isinstance(c, dict) and c.get('id') in cids]
    objects = [c.get('object') for c in planned] or [((rows or {}).get(cid) or {}).get('binding', {}).get('object') for cid in cids]
    for o in objects:
        if isinstance(o, dict):
            refs += [x for x in ([o.get('ref')] if isinstance(o.get('ref'), str) else []) + list(o.get('refs') or []) if isinstance(x, str)]
            if isinstance(o.get('node'), str):   # a pin row is about its part, as row_anchors reads it
                refs.append(o['node'].partition('.')[0])
            nets += [x for x in ([o.get('net')] if isinstance(o.get('net'), str) else []) + list(o.get('nets') or []) if isinstance(x, str)]
    objects = {}
    if refs or not nets:
        objects['refs'] = list(dict.fromkeys(refs)) or ['SYNTHETIC']
    if nets:
        objects['nets'] = list(dict.fromkeys(nets))
    return objects


def _edges(rows, states, key):
    """One edge per aspect the rows have, scoped to their states (none: the rows have no state); a gap in a quantity
    enters the stipulated limit c1."""
    out = {}
    for r in rows:
        edge = out.setdefault(r['aspect'], {'aspect': r['aspect'], 'via': {'condition': 'c1'},
                                            'rationale': 'Synthetic: %s leaves %s undecided' % (key, r['aspect'])})
        state = states.get(r.get('id'))
        if state:
            edge.setdefault('states', [])
            if state not in edge['states']:
                edge['states'].append(state)
    return list(out.values())


def _open_item(key, rows, task, states=None):
    """One open item for the gaps a task (or an orphan row) owns; the row gaps were written in schema 3 shape."""
    gaps = [g for row in rows for g in row.get('gaps') or []]
    cause = rows[0].get('gap_cause')
    kind = CAUSE_KIND.get(cause, 'REVIEW_INCOMPLETE')
    whats = list(dict.fromkeys(g.get('what') for g in gaps if g.get('what')))
    first = gaps[0] if gaps else {}
    item = {'key': key, 'kind': kind, 'what': '；'.join(whats) or (task or {}).get('root_cause') or 'Synthetic gap',
            'decides': _edges(rows, states or {}, key)}
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
            item['why_insufficient'] = 'Synthetic: the stipulated clause does not give the datum of %s' % key
            item['worst_case'] = {'not_boundable_reason': 'Synthetic: the fixture stipulates no public curve bounds it',
                                  'curves_checked': [{'source': 'synthetic', 'locator': 'stipulated'}],
                                  'operating_point_specified': True}
    if kind == 'USER_DEFERRED':
        item['instruction'] = SYNTHETIC
    return {k: v for k, v in item.items() if v is not None}


def _fail_edge(row, states):
    state = states.get(row.get('id'))
    return {'aspect': row['aspect'], **({'states': [state]} if state else {})}


def _stipulated(fid, question, objects, verdict):
    return {'id': fid, 'question': question, 'objects': objects,
            'conditions': [{'id': 'c1', 'kind': 'NUMERIC_LIMIT', 'source': 'synthetic-fixture.json',
                            'locator': 'p1 Table 1 (stipulated clause)', 'says': 'stipulated limit 1 V',
                            'limit': {'max': 1, 'unit': 'V'}, 'regime': 'stipulated', 'use': 'stipulated'},
                           {'id': 'c2', 'kind': 'MANDATORY_CLAUSE', 'source': 'synthetic-fixture.json',
                            'locator': 'p1 §1 (stipulated clause)', 'says': 'the stipulated connection must hold',
                            'applies': 'stipulated', 'use': 'stipulated'}],
            'no_calculation_reason': 'synthetic fixture', 'evidence': SYNTHETIC, 'open': [], 'fails': [], 'verdict': verdict}


def _functions(out, plan):
    """Function verdicts from the legacy work_items and the INSUFFICIENT/FAIL rows they own. A row that
    belongs to a plan frame (intent circuit) binds to that frame's function, as a reviewer would."""
    rows = {r['id']: r for r in out.get('checks') or [] if isinstance(r, dict) and isinstance(r.get('id'), str)}
    tasks = [t for t in out.get('work_items') or [] if isinstance(t, dict) and isinstance(t.get('id'), str)]
    frames = {f['id']: f for f in (plan or {}).get('functions') or [] if isinstance(f, dict) and isinstance(f.get('id'), str)}
    frame_of = {m['check_id']: f['id'] for f in frames.values() for m in f.get('members') or [] if isinstance(m, dict)}
    states = {c['id']: (c.get('object') or {}).get('state') for c in (plan or {}).get('checks') or []
              if isinstance(c, dict) and isinstance(c.get('id'), str) and isinstance(c.get('object'), dict)}
    for cid, row in rows.items():   # without a plan, the row's own binding says its state
        obj = (row.get('binding') or {}).get('object') if isinstance(row.get('binding'), dict) else None
        if cid not in states and isinstance(obj, dict):
            states[cid] = obj.get('state')
    for row in rows.values():
        if row.get('review_result') in ('INSUFFICIENT', 'FAIL'):
            row.setdefault('aspect', _aspect(plan, row))
    functions, owned = {}, set()

    def function(fid, cids, fallback_question):
        if fid not in functions:
            frame = frames.get(fid)
            fn = _stipulated(fid, frame['question'] if frame else fallback_question,
                             frame['objects'] if frame else _objects(plan, cids, rows), 'PASS')
            fn['evidence'] = SYNTHETIC
            functions[fid] = fn
        return functions[fid]

    for task in tasks:
        cids = [c for c in task.get('check_ids') or [] if c in rows and rows[c].get('review_result') in ('INSUFFICIENT', 'FAIL')
                and not (rows[c]['review_result'] == 'FAIL' and document_row(c))]   # a document defect stays on its row
        if not cids or any(c in owned for c in cids):
            continue   # a malformed or shared task stays as the builder wrote it: the validator names it
        owned.update(cids)
        groups = {}
        for c in cids:
            groups.setdefault(frame_of.get(c) or 'FN-' + _slug(task['id']), []).append(c)
        for fid, members in groups.items():
            fn = function(fid, members, task.get('title') or 'Synthetic question')
            if task.get('evidence'):
                fn['evidence'] = task['evidence']
            ins = [rows[c] for c in members if rows[c].get('review_result') == 'INSUFFICIENT']
            fails = [rows[c] for c in members if rows[c].get('review_result') == 'FAIL']
            if ins:
                fn['open'].append(_open_item(task['id'], ins, task, states))
                for r in ins:
                    r['function_id'], r['open_ref'] = fid, fid + '/' + task['id']
            for r in fails:
                key = task['id'] if not ins and len(fails) == 1 else task['id'] + '-' + _slug(r['id'])
                fn['fails'].append({'key': key, 'finding_id': r.get('finding_id'), 'what': task.get('root_cause') or 'Synthetic defect',
                                    'title': task.get('title'), 'decides': [_fail_edge(r, states)], 'conditions': ['c2'],
                                    **{k: task[k] for k in ('due_stage', 'design_option') if k in task},
                                    **({'why': task['reason']} if task.get('reason') else {})})
                r['function_id'], r['fail_ref'] = fid, fid + '/' + key
    aspect_of = {m['check_id']: m.get('aspect') for f in frames.values() for m in f.get('members') or [] if isinstance(m, dict)}
    for cid, fid in frame_of.items():   # a passed frame row binds to its frame and rests on a judgement there
        row = rows.get(cid)
        if row and row.get('review_result') == 'PASS' and 'function_id' not in row and aspect_of.get(cid):
            fn = function(fid, [cid], 'Synthetic question for ' + cid)
            row['function_id'] = fid
            row.setdefault('aspect', aspect_of[cid])
            judged = fn.setdefault('judgements', [])
            if row['aspect'] not in {j['aspect'] for j in judged}:
                judged.append({'aspect': row['aspect'], 'conditions': ['c2'],
                               'says': 'Synthetic: the stipulated connection holds for %s' % row['aspect']})
    orphans = [cid for cid, row in rows.items()
               if row.get('review_result') == 'INSUFFICIENT' and cid not in owned and row.get('gaps') is not None]
    for cid, row in rows.items():
        if (row.get('review_result') == 'FAIL' and cid not in owned and not document_row(cid)
                and (functions or orphans or cid in frame_of) and row.get('finding_id')):
            # Legacy builders left FAIL rows outside any task while the workflow was disabled; the
            # functions above enable it, so the defect gets the function the reviewer would write.
            fid = frame_of.get(cid) or 'FN-' + _slug(cid)
            fn = function(fid, [cid], 'Synthetic question for ' + cid)
            fn['fails'].append({'key': _slug(cid), 'finding_id': row['finding_id'], 'what': 'Synthetic defect',
                                'decides': [_fail_edge(row, states)], 'conditions': ['c2']})
            row['function_id'], row['fail_ref'] = fid, fid + '/' + _slug(cid)
        if row.get('review_result') == 'INSUFFICIENT' and cid not in owned and row.get('gaps') is not None:
            fid = frame_of.get(cid) or 'FN-' + _slug(cid)
            fn = function(fid, [cid], 'Synthetic question for ' + cid)
            fn['open'].append(_open_item(_slug(cid), [row], None, states))
            row['function_id'], row['open_ref'] = fid, fid + '/' + _slug(cid)
    for cid, fid in frame_of.items():
        row = rows.get(cid)
        if row and row.get('review_result') in ('PASS', 'FAIL', 'INSUFFICIENT') and 'function_id' not in row:
            function(fid, [cid], 'Synthetic question for ' + cid)
            row['function_id'] = fid
    for fn in functions.values():
        fn['verdict'] = 'FAIL' if fn['fails'] else 'OPEN' if fn['open'] else 'PASS'
    return list(functions.values())


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

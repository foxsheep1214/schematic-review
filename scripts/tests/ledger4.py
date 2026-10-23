"""Schema 4 test ledgers written the way a reviewer writes them: a row that is not a plain PASS names the
function verdict that decides it, and the open or fail item there. Each helper writes one such item and
binds the rows to it, so a test states its gap or defect in the fields it is about. Not used by SR itself."""
import re

import catalog

SYNTHETIC = [{'source': 'synthetic-fixture.json', 'locator': 'all values stipulated for tests'}]
# a level already implies a consequence class; tests about classes pass their own
LEVEL_CLASS = {'P0': 'CORE_LINK_LOSS', 'P1': 'REQUIRED_FUNCTION', 'P2': 'LOCAL_OR_DATA', 'P3': 'OPTIMIZATION'}


def slug(value):
    return re.sub(r'[^A-Za-z0-9_.-]+', '-', str(value)).strip('-') or 'X'


def aspect_of(cid):
    try:
        return catalog.title(str(cid).split('.')[0])
    except Exception:  # unknown synthetic rule
        return 'general'


def severity(level='P2', cls=None, consequence='Synthetic consequence', affects='Synthetic affected function', **extra):
    out = {'level': level, 'class': cls or LEVEL_CLASS.get(level), 'affects': affects, 'consequence': consequence}
    if level == 'P0' and cls is None:
        out['hazard_path'] = 'PROTECTION_LOSS'
    out.update(extra)
    return {k: v for k, v in out.items() if v is not None}


def stipulated(fid, objects, question=None, verdict='PASS'):
    """A function on two stipulated conditions: c1 a numeric limit, c2 a mandatory connection clause."""
    return {'id': fid, 'question': question or 'Synthetic question for ' + fid, 'objects': objects,
            'conditions': [{'id': 'c1', 'kind': 'NUMERIC_LIMIT', 'source': 'synthetic-fixture.json',
                            'locator': 'p1 Table 1 (stipulated clause)', 'says': 'stipulated limit 1 V',
                            'limit': {'max': 1, 'unit': 'V'}, 'regime': 'stipulated', 'use': 'stipulated'},
                           {'id': 'c2', 'kind': 'MANDATORY_CLAUSE', 'source': 'synthetic-fixture.json',
                            'locator': 'p1 §1 (stipulated clause)', 'says': 'the stipulated connection must hold',
                            'applies': 'stipulated', 'use': 'stipulated'}],
            'no_calculation_reason': 'synthetic fixture', 'evidence': SYNTHETIC, 'open': [], 'fails': [],
            'verdict': verdict}


def _planned(plan):
    return {c['id']: c for c in (plan or {}).get('checks') or [] if isinstance(c, dict) and isinstance(c.get('id'), str)}


def _objects(plan, report, cids):
    """The parts and nets the rows are about, from the plan or, without one, from the rows' own bindings."""
    planned, rows = _planned(plan), {r.get('id'): r for r in report.get('checks') or [] if isinstance(r, dict)}
    refs, nets = [], []
    for cid in cids:
        o = (planned.get(cid) or {}).get('object') or ((rows.get(cid) or {}).get('binding') or {}).get('object')
        if isinstance(o, dict):
            refs += [x for x in ([o.get('ref')] if isinstance(o.get('ref'), str) else []) + list(o.get('refs') or [])
                     if isinstance(x, str)]
            if isinstance(o.get('node'), str):
                refs.append(o['node'].partition('.')[0])
            nets += [x for x in ([o.get('net')] if isinstance(o.get('net'), str) else []) + list(o.get('nets') or [])
                     if isinstance(x, str)]
    out = {}
    if refs or not nets:
        out['refs'] = list(dict.fromkeys(refs)) or ['SYNTHETIC']
    if nets:
        out['nets'] = list(dict.fromkeys(nets))
    return out


def _state(plan, report, cid):
    o = (_planned(plan).get(cid) or {}).get('object')
    if not isinstance(o, dict):
        row = next((r for r in report.get('checks') or [] if isinstance(r, dict) and r.get('id') == cid), {})
        o = (row.get('binding') or {}).get('object')
    return o.get('state') if isinstance(o, dict) else None


def frame_of(plan, cid):
    """(frame id, member aspect) of the plan frame that holds `cid`, else (None, None)."""
    for frame in (plan or {}).get('functions') or []:
        for member in frame.get('members') or [] if isinstance(frame, dict) else []:
            if isinstance(member, dict) and member.get('check_id') == cid:
                return frame.get('id'), member.get('aspect')
    return None, None


def function(report, fid, cids=(), plan=None, question=None):
    """The function `fid` of the report, written on stipulated conditions when it is not there yet; a plan frame
    of that id gives its question and objects."""
    functions = report.setdefault('functions', [])
    fn = next((f for f in functions if isinstance(f, dict) and f.get('id') == fid), None)
    if fn is None:
        frame = next((f for f in (plan or {}).get('functions') or [] if isinstance(f, dict) and f.get('id') == fid), None)
        fn = stipulated(fid, frame['objects'] if frame else _objects(plan, report, cids),
                        frame['question'] if frame else question)
        functions.append(fn)
    return fn


def _verdict(fn):
    fn['verdict'] = 'FAIL' if fn['fails'] else 'OPEN' if fn['open'] else 'PASS'


def _rows(report, cids):
    rows = {r.get('id'): r for r in report.get('checks') or [] if isinstance(r, dict)}
    return [rows[c] for c in cids]


def gap(report, cids, key, kind='REVIEW_INCOMPLETE', fid=None, plan=None, what=None, level='P2', cls=None,
        consequence='Synthetic consequence', scope='Synthetic bounded scope', **item):
    """Rows `cids` INSUFFICIENT on open item `key` of function `fid` (default FN-<key>). `item` adds or overrides
    open item fields (title, why, scope, due_stage, design_option, severity, ...)."""
    cids = [cids] if isinstance(cids, str) else list(cids)
    fid = fid or frame_of(plan, cids[0])[0] or 'FN-' + slug(key)
    fn = function(report, fid, cids, plan, item.get('title'))
    edges = {}
    for cid in cids:
        aspect = aspect_of(cid)
        edge = edges.setdefault(aspect, {'aspect': aspect, 'via': {'condition': 'c1'},
                                         'rationale': 'Synthetic: %s leaves %s undecided' % (key, aspect)})
        state = _state(plan, report, cid)
        if state and state not in edge.setdefault('states', []):
            edge['states'].append(state)
    out = {'key': key, 'kind': kind, 'what': what or 'Synthetic gap ' + key, 'decides': list(edges.values())}
    if kind != 'REQUIREMENT':
        out['scope'] = scope
        out['severity'] = severity(level, cls, consequence)
    if kind == 'DESIGN_VALUE':
        out.update(spec='Synthetic specification', owner='Synthetic designer', closure='Synthetic recheck')
    elif kind == 'VENDOR_DATUM':
        out.update(acquisition='Synthetic source', closure='Synthetic recheck', checked=['c1'],
                   why_insufficient='Synthetic: the stipulated clause does not give the datum of %s' % key,
                   worst_case={'not_boundable_reason': 'Synthetic: the fixture stipulates no public curve bounds it',
                               'curves_checked': [{'source': 'synthetic-fixture.json', 'locator': 'stipulated'}],
                               'operating_point_specified': True, 'specified_by': 'c1',
                               'monotonic_tried': {'unfavorable_side': 'Synthetic: the stipulated side',
                                                   'why_not': 'Synthetic: the fixture stipulates no monotonic curve'}})
    elif kind == 'USER_DEFERRED':
        out['instruction'] = SYNTHETIC
    out.update(item)
    fn['open'].append({k: v for k, v in out.items() if v is not None})
    for row in _rows(report, cids):
        row.update(review_result='INSUFFICIENT', function_id=fid, open_ref=fid + '/' + key, aspect=aspect_of(row['id']))
        row.pop('evidence_confidence', None)   # an open row is C
    _verdict(fn)
    return fn['open'][-1]


def defect(report, cids, key, finding_id=None, fid=None, plan=None, what='Synthetic defect', **item):
    """Rows `cids` FAIL on fail item `key` of function `fid` (default FN-<key>), on the stipulated clause c2."""
    cids = [cids] if isinstance(cids, str) else list(cids)
    fid = fid or frame_of(plan, cids[0])[0] or 'FN-' + slug(key)
    fn = function(report, fid, cids, plan, item.get('title'))
    decides = []
    for cid in cids:
        state = _state(plan, report, cid)
        decides.append({'aspect': aspect_of(cid), **({'states': [state]} if state else {})})
    out = {'key': key, 'what': what, 'decides': decides, 'conditions': ['c2'], 'finding_id': finding_id}
    out.update(item)
    fn['fails'].append({k: v for k, v in out.items() if v is not None})
    for row in _rows(report, cids):
        row.update(review_result='FAIL', function_id=fid, fail_ref=fid + '/' + key, aspect=aspect_of(row['id']))
        if finding_id:
            row['finding_id'] = finding_id
    _verdict(fn)
    return fn['fails'][-1]


def judged(report, cid, fid, aspect, plan=None):
    """A passed frame row resting on a judgement of its function."""
    fn = function(report, fid, [cid], plan)
    row = _rows(report, [cid])[0]
    row.update(function_id=fid, aspect=aspect)
    judgements = fn.setdefault('judgements', [])
    if aspect not in {j['aspect'] for j in judgements}:
        judgements.append({'aspect': aspect, 'conditions': ['c2'], 'says': 'Synthetic: the stipulated connection holds for ' + aspect})
    return fn


def whole_clause(plan, row):
    """A REQ-D01 row's requirement as one obligation carrying the row's result."""
    planned = _planned(plan).get(row['id']) or {}
    text = ''.join(c.get('text') or '' for c in (planned.get('source_text') or {}).get('columns') or [])
    row['requirement_clauses'] = [{'text': text or planned.get('criterion'), 'kind': 'OBLIGATION',
                                   'result': row['review_result']}]
    return row


def passed(report, cid, plan=None, **fields):
    """Row `cid` now PASS: its open or fail item leaves its function (a function left with nothing goes), and a
    frame member rests on a judgement of its frame."""
    row = _rows(report, [cid])[0]
    ref = row.get('open_ref') or row.get('fail_ref')
    if ref:
        fid, key = ref.split('/', 1)
        fn = next(f for f in report['functions'] if f['id'] == fid)
        for field in ('open', 'fails'):
            fn[field] = [i for i in fn[field] if i.get('key') != key]
        _verdict(fn)
        bound = [r for r in report['checks'] if isinstance(r, dict) and r.get('function_id') == fid and r is not row]
        if not (bound or fn['open'] or fn['fails'] or fn.get('judgements')):
            report['functions'].remove(fn)
    for key in ('function_id', 'open_ref', 'fail_ref', 'aspect', 'finding_id', 'blocking'):
        row.pop(key, None)
    row.update(review_result='PASS', **fields)
    fid, aspect = frame_of(plan, cid)
    if fid and aspect:
        judged(report, cid, fid, aspect, plan)
    return row

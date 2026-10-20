"""Function verdicts: the unit of judgement (docs/2026-10-20-function-verdicts-design.md, §4 and §7).

A function verdict answers one question about one circuit block. Before it may leave anything open
it must have listed the datasheet clauses that bear on the question (F1), kept a design value as a
specification instead of a vendor request (F2), named what was checked and the worst case before
asking a vendor (F3), and drawn the conclusion a computed margin already gives (F4). Rows only
follow the verdict (F5); a changed verdict cites a clause or a number (F6); one open item does not
spread over a whole block without saying why (F7). None of this proves the electrical judgement.
"""
import re

import results_model
from results_model import LEVELS, OPEN_KINDS, PHASES, VERDICTS, text

CONDITION_FIELDS = ('id', 'source', 'locator', 'says', 'use')
REQUEST_KINDS = ('DESIGN_VALUE', 'VENDOR_DATUM')
VENDOR_ASK_RE = re.compile(r'向[^，,；;。]{0,16}(?:原厂|厂商|厂家|供应商|[A-Z][A-Za-z]{2,})[^，,；;。]{0,8}(?:索取|取得|索要|要)'
                           r'|ask(?:ing)? (?:the )?(?:vendor|supplier|manufacturer)|request(?:ed)? from (?:the )?(?:vendor|supplier)', re.I)
MANY_ASPECTS = 3
ID_RE = re.compile(r'^FN-[A-Za-z0-9][A-Za-z0-9_.-]*$')
KEY_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]*$')


def evidence(value):
    return isinstance(value, list) and bool(value) and all(
        isinstance(x, dict) and text(x.get('source')) and text(x.get('locator')) for x in value)


def _decides(item):
    out = []
    for d in item.get('decides') or []:
        if isinstance(d, dict) and text(d.get('aspect')):
            states = d.get('states')
            out.append((d['aspect'], set(states) if isinstance(states, list) and states else None))
    return out


def decides_row(item, aspect, state):
    """Whether an open/fail item decides the row covering `aspect` in `state`."""
    for item_aspect, states in _decides(item):
        if item_aspect == aspect and (states is None or state is None or state in states):
            return True
    return False


def worst_verdict(fn):
    if fn.get('fails'):
        return 'FAIL'
    if fn.get('open'):
        return 'OPEN'
    return 'PASS'


def _margin_value(calculation):
    margin = calculation.get('margin') if isinstance(calculation, dict) else None
    if isinstance(margin, dict) and type(margin.get('value')) in (int, float):
        return margin['value']
    return None


def _item_errors(label, item, kind_field, condition_ids, finding_ids):
    """One open or fail item: F2, F3 and the shared shape (key, decides, severity)."""
    errors = []
    if not (text(item.get('key')) and KEY_RE.match(item['key'])):
        errors.append(label + ': item needs a key (letters, digits, - _ .)')
    if not text(item.get('what')):
        errors.append(label + ': item needs what (the one thing missing or wrong)')
    if not _decides(item):
        errors.append(label + ': decides lists the aspects (and states) this item leaves undecided')
    else:
        aspects = {a for a, _ in _decides(item)}
        if len(aspects) > MANY_ASPECTS and not text(item.get('decides_reason')):   # F7
            errors.append('%s: decides covers %d aspects; say in decides_reason why one item undoes that much'
                          % (label, len(aspects)))
    if 'due_stage' in item and item['due_stage'] not in PHASES:
        errors.append(label + ': due_stage is one of ' + '/'.join(PHASES))
    if 'blocking' in item and item['blocking'] is not False:
        errors.append(label + ': blocking is derived; write it only as false')
    if kind_field == 'fails':
        if item.get('finding_id') not in finding_ids:
            errors.append(label + ': a fail item names the finding (finding_id) that records the defect')
        return errors
    kind = item.get('kind')
    if kind not in OPEN_KINDS:
        errors.append(label + ': kind is one of ' + '/'.join(OPEN_KINDS))
        return errors
    severity = item.get('severity')
    if kind == 'REQUIREMENT':
        if severity is not None:
            errors.append(label + ': a requirement the owner has not decided is not graded; omit severity')
    elif not isinstance(severity, dict):
        errors.append(label + ': severity {level, class, consequence} required')
    else:
        if severity.get('level') not in LEVELS:
            errors.append(label + ': severity.level is one of ' + '/'.join(LEVELS))
        for field in ('class', 'consequence'):
            if not text(severity.get(field)):
                errors.append(label + ': severity.' + field + ' required')
    if kind not in REQUEST_KINDS:
        stray = [f for f in ('spec', 'owner', 'acquisition', 'closure', 'checked', 'worst_case') if f in item]
        if stray:
            errors.append('%s: %s only belong to DESIGN_VALUE/VENDOR_DATUM' % (label, '/'.join(stray)))
    if kind in REQUEST_KINDS:
        for field in ('scope', 'closure'):
            if not text(item.get(field)):
                errors.append(label + ': ' + field + ' required (the conditions it must cover; what counts as closed)')
    if kind == 'DESIGN_VALUE':   # F2
        for field in ('spec', 'owner'):
            if not text(item.get(field)):
                errors.append(label + ': a design value is back-calculated into spec and given an owner, not requested')
        asked = ' '.join(str(item.get(f) or '') for f in ('what', 'why', 'spec', 'owner', 'closure'))
        if VENDOR_ASK_RE.search(asked):
            errors.append(label + ': a design value is not asked of a vendor (%s); write the allowed range as spec'
                          % VENDOR_ASK_RE.search(asked).group(0))
    if kind == 'VENDOR_DATUM':   # F3
        checked = item.get('checked')
        if not (isinstance(checked, list) and checked and all(c in condition_ids for c in checked)):
            errors.append(label + ': checked lists the condition ids read before asking the vendor')
        if not text(item.get('why_insufficient')):
            errors.append(label + ': why_insufficient says why the clauses read do not answer the question')
        if not text(item.get('acquisition')):
            errors.append(label + ': acquisition says who provides the datum')
        worst = item.get('worst_case')
        if not (isinstance(worst, dict) and (text(worst.get('result')) or text(worst.get('not_boundable_reason')))):
            errors.append(label + ': worst_case gives the result under the datasheet worst case, or why it cannot be bounded')
    if kind == 'USER_DEFERRED' and not evidence(item.get('instruction')):
        errors.append(label + ': a deferral cites the user instruction (instruction evidence)')
    return errors


def function_errors(report):
    """F1–F4, F6, F7 and the shape of every function verdict; no plan needed."""
    errors = []
    functions = report.get('functions')
    if not isinstance(functions, list):
        return errors   # results_model.shape_errors names this
    finding_ids = {f.get('id') for f in report.get('findings') or [] if isinstance(f, dict)}
    seen_ids, seen_keys = set(), {}
    for fn in functions:
        if not isinstance(fn, dict) or not (text(fn.get('id')) and ID_RE.match(fn['id'])):
            errors.append('functions[]: each verdict has an id like FN-BIAS-VCC')
            continue
        fid = fn['id']
        if fid in seen_ids:
            errors.append(fid + ': duplicate function id')
        seen_ids.add(fid)
        if not text(fn.get('question')):
            errors.append(fid + ': question — what this block must do, under which conditions')
        obj = fn.get('objects')
        if not (isinstance(obj, dict) and any(
                isinstance(obj.get(k), list) and obj[k] and all(text(x) for x in obj[k]) for k in ('refs', 'nets'))):
            errors.append(fid + ': objects names the refs and/or nets the question is about')
        conditions = fn.get('conditions')
        condition_ids = set()
        if not (isinstance(conditions, list) and conditions):   # F1
            errors.append(fid + ': conditions lists the datasheet/standard clauses that bear on the question (at least one)')
        else:
            for i, c in enumerate(conditions):
                if not isinstance(c, dict) or not all(text(c.get(f)) for f in CONDITION_FIELDS):
                    errors.append('%s/conditions[%d]: needs %s' % (fid, i, '/'.join(CONDITION_FIELDS)))
                    continue
                if c['id'] in condition_ids:
                    errors.append('%s/conditions: duplicate id %s' % (fid, c['id']))
                condition_ids.add(c['id'])
        calculation = fn.get('calculation')
        claim_ids = set()
        if calculation is None:
            if not text(fn.get('no_calculation_reason')):
                errors.append(fid + ': calculation {result[, margin, claim_ids, assumptions, aspect]} or no_calculation_reason')
        elif not isinstance(calculation, dict) or not text(calculation.get('result')):
            errors.append(fid + ': calculation needs result')
        else:
            claim_ids = {c for c in calculation.get('claim_ids') or [] if isinstance(c, str)}
            margin = calculation.get('margin')
            if margin is not None and not (isinstance(margin, dict) and type(margin.get('value')) in (int, float)
                                           and text(margin.get('unit')) and text(margin.get('against'))):
                errors.append(fid + ': calculation.margin is {value: number, unit, against}')
        if not evidence(fn.get('evidence')):
            errors.append(fid + ': evidence locates the analysis (engineering record, calculation file)')
        if fn.get('verdict') not in VERDICTS:
            errors.append(fid + ': verdict is one of ' + '/'.join(VERDICTS))
        elif fn['verdict'] != worst_verdict(fn):
            errors.append('%s: verdict %s does not follow its items (fails → FAIL, open → OPEN, else PASS)'
                          % (fid, fn['verdict']))
        for field in ('open', 'fails'):
            items = fn.get(field)
            if items is None:
                continue
            if not isinstance(items, list):
                errors.append('%s: %s must be a list' % (fid, field))
                continue
            for item in items:
                if not isinstance(item, dict):
                    errors.append('%s/%s: items are objects' % (fid, field))
                    continue
                label = '%s/%s' % (fid, item.get('key', '?'))
                key = item.get('key')
                if text(key):
                    if key in seen_keys:
                        errors.append('%s: key %s already used by %s (keys are unique across functions)' % (label, key, seen_keys[key]))
                    seen_keys[key] = fid
                errors.extend(_item_errors(label, item, field, condition_ids, finding_ids))
        # F4: a positive computed margin decides; an open item on the same aspect needs a reason.
        value = _margin_value(calculation)
        if value is not None and value > 0 and isinstance(fn.get('open'), list):
            aspect = calculation.get('aspect')
            for item in fn['open']:
                if not isinstance(item, dict) or text(item.get('margin_not_decisive_reason')):
                    continue
                if aspect is None or any(a == aspect for a, _ in _decides(item)):
                    errors.append('%s/%s: calculation shows %s %s margin against %s, yet this stays open; conclude, '
                                  'or say in margin_not_decisive_reason why the margin does not decide it'
                                  % (fid, item.get('key', '?'), value, calculation['margin'].get('unit'),
                                     calculation['margin'].get('against')))
        # F6: a verdict change cites a clause or a number.
        history = fn.get('verdict_history')
        if history is not None:
            if not isinstance(history, list):
                errors.append(fid + ': verdict_history must be a list')
            else:
                for i, h in enumerate(history):
                    basis = h.get('basis') if isinstance(h, dict) else None
                    ok = (isinstance(h, dict) and h.get('from') in VERDICTS and h.get('to') in VERDICTS
                          and isinstance(basis, list) and basis
                          and all(b in condition_ids or b in claim_ids for b in basis))
                    if not ok:
                        errors.append('%s/verdict_history[%d]: a changed verdict cites condition or claim ids in basis'
                                      % (fid, i))
    return errors


def binding_errors(expected, checks, functions, history_ids=()):
    """F5: rows follow their function. `expected` is the plan index, `checks` the rows as written."""
    errors = []
    functions = {fn['id']: fn for fn in functions or [] if isinstance(fn, dict) and text(fn.get('id'))}
    items = results_model.open_items({'functions': list(functions.values())})
    for cid, row in checks.items():
        if not isinstance(row, dict):
            continue
        result = row.get('review_result')
        fid = row.get('function_id')
        if fid is not None and fid not in functions:
            errors.append(cid + ': function_id names no function verdict')
            continue
        state = ((expected.get(cid) or {}).get('object') or {}).get('state')
        for field in ('open_ref', 'fail_ref'):
            ref = row.get(field)
            if ref is None or ref not in items or not text(row.get('aspect')):
                continue   # shape_errors names a missing ref or aspect
            fn, item, _ = items[ref]
            if not decides_row(item, row['aspect'], state):
                errors.append('%s: %s %s does not decide aspect %s%s; extend its decides or bind the row elsewhere'
                              % (cid, field, ref, row['aspect'], (' in state ' + state) if state else ''))
        if result == 'FAIL' and fid is not None and cid not in history_ids and 'fail_ref' not in row:
            errors.append(cid + ': a FAIL row bound to a function names the fail item that records it (fail_ref)')
        if result == 'FAIL' and 'fail_ref' in row and row['fail_ref'] in items:
            finding = items[row['fail_ref']][1].get('finding_id')
            if row.get('finding_id') not in (None, finding):
                errors.append('%s: finding_id %s differs from the fail item\'s %s' % (cid, row.get('finding_id'), finding))
    return errors


REVIEWED = ('PASS', 'FAIL', 'INSUFFICIENT')


def frame_errors(plan, checks, functions):
    """Plan frames (one per intent circuit) are answered: a reviewed member row binds to its frame's
    function and keeps the frame's aspect; a frame with a reviewed member has a function verdict."""
    errors = []
    ids = {fn['id'] for fn in functions or [] if isinstance(fn, dict) and text(fn.get('id'))}
    for frame in (plan or {}).get('functions') or []:
        if not isinstance(frame, dict) or not text(frame.get('id')):
            continue
        answered = False
        for member in frame.get('members') or []:
            row = checks.get(member.get('check_id')) if isinstance(member, dict) else None
            if not isinstance(row, dict) or row.get('review_result') not in REVIEWED:
                continue
            answered = True
            if row.get('function_id') != frame['id']:
                errors.append('%s: a member of frame %s binds to it (function_id), not to %s'
                              % (member['check_id'], frame['id'], row.get('function_id')))
            if 'aspect' in row and row['aspect'] != member.get('aspect'):
                errors.append('%s: aspect %r differs from the frame member aspect %r'
                              % (member['check_id'], row['aspect'], member.get('aspect')))
        if answered and frame['id'] not in ids:
            errors.append('functions: frame %s has reviewed member rows but no function verdict' % frame['id'])
    return errors


def validate_functions(plan, report, checks, history_ids=()):
    """All function-verdict errors for validate_review. `report` is the record as written."""
    expected = {c['id']: c for c in (plan or {}).get('checks') or [] if isinstance(c, dict) and isinstance(c.get('id'), str)}
    return (function_errors(report) + binding_errors(expected, checks, report.get('functions'), history_ids)
            + frame_errors(plan, checks, report.get('functions')))

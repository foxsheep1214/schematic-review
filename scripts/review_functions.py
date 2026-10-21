"""Function verdicts: the unit of judgement (docs/2026-10-20-function-verdicts-design.md, §4 and §7).

A function verdict answers one question about one circuit block. Before it may leave anything open
it must have listed the datasheet clauses that bear on the question (F1), kept a design value as a
specification instead of a vendor request (F2), named what was checked and the worst case before
asking a vendor (F3: the worst case under the public bound, its margin deciding like any other, or the
curves and tables searched before calling it unboundable), and drawn the conclusion a computed margin
already gives (F4: a positive margin passes, a margin at or below zero is a fail item whose finding carries
the change, or stays open only naming the loose bound). Rows only follow the verdict (F5); a changed verdict
cites a clause or a number (F6); one open item does not spread over a whole block without saying why
(F7); a design value left open beside a calculation states its margin (F8); a deliverable another stage owes
(DELIVERABLE_PENDING) names the deliverable, its owner and what the verdict assumed. Document checks are not
functions: a document defect is not bound to one, and a function of document rows only is not counted.
None of this proves the electrical judgement.
"""
import re

import results_model
from results_model import LEVELS, OPEN_KINDS, PHASES, VERDICTS, text
from validate_remediation import READINESS

CONDITION_FIELDS = ('id', 'source', 'locator', 'says', 'use')
REQUEST_KINDS = ('DESIGN_VALUE', 'VENDOR_DATUM')
# How a public number bounds the quantity at the design's operating point (F3).
BOUND_BASES = ('GUARANTEED_LIMIT', 'ADJACENT_TEST_POINT', 'TYPICAL_CURVE', 'PUBLISHED_TABLE', 'APPLICATION_NOTE')
DELIVERABLE_FIELDS = ('deliverable', 'owner', 'assumed', 'closure')
# What another stage owes; a parameter of a catalog part is none of these (it is a VENDOR_DATUM with its public bound).
DELIVERABLE_KINDS = ('CUSTOM_PART_DRAWING', 'FIRMWARE_CAPABILITY', 'CONFIGURATION_TABLE')
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


def judged(fn, aspect, state=None):
    """What settles `aspect` (in `state`) in favour of the design: a positive margin on that aspect, or a
    judgements entry citing the clauses. None when nothing does — a row never passes on another aspect's result."""
    calc = fn.get('calculation') if isinstance(fn.get('calculation'), dict) else {}
    for m in results_model.margins(calc):
        if (m.get('aspect') or calc.get('aspect')) == aspect and type(m['value']) in (int, float) and m['value'] > 0:
            return '%s；余量 %s%s 对 %s' % (calc.get('result') or '', m['value'], m.get('unit') or '', m.get('against') or '')
    for j in fn.get('judgements') or []:
        if not (isinstance(j, dict) and j.get('aspect') == aspect and text(j.get('says'))):
            continue
        states = j.get('states')
        if not states or state is None or state in states:
            return '%s（依据 %s）' % (j['says'], '、'.join(c for c in j.get('conditions') or [] if isinstance(c, str)))
    return None


def unjudged_message(cid, fid, aspect, state):
    return ('%s: function %s judges no %s%s — give that aspect its margin in calculation.margin or a judgements '
            'entry {aspect, conditions, says}; a row does not pass on another aspect\'s result'
            % (cid, fid, aspect, (' in state ' + state) if state else ''))


def _judgement_errors(fid, fn, condition_ids):
    errors = []
    judgements = fn.get('judgements')
    if judgements is None:
        return errors
    if not isinstance(judgements, list):
        return [fid + ': judgements is a list of {aspect, conditions, says[, states]}']
    for i, j in enumerate(judgements):
        conditions = j.get('conditions') if isinstance(j, dict) else None
        if not (isinstance(j, dict) and text(j.get('aspect')) and text(j.get('says'))
                and isinstance(conditions, list) and conditions and all(c in condition_ids for c in conditions)):
            errors.append('%s/judgements[%d]: names the aspect, the condition ids it rests on and what they settle (says)'
                          % (fid, i))
    return errors


def document_row(check_id):
    return isinstance(check_id, str) and check_id.split('.')[0].startswith('DOC-')


def circuit_functions(functions, checks):
    """Function verdicts that answer a circuit: one whose bound rows are all document checks only
    carries their open items and is not counted or listed as a function."""
    rows = {}
    for row in checks or []:
        if isinstance(row, dict) and row.get('function_id') is not None:
            rows.setdefault(row['function_id'], []).append(row.get('id'))
    return [fn for fn in functions or [] if isinstance(fn, dict)
            and not (rows.get(fn.get('id')) and all(document_row(c) for c in rows[fn['id']]))]


def worst_verdict(fn):
    if fn.get('fails'):
        return 'FAIL'
    if fn.get('open'):
        return 'OPEN'
    return 'PASS'


def _covers(item, aspect):
    """A margin without aspect speaks for the whole function."""
    return aspect is None or any(a == aspect for a, _ in _decides(item))


def _loose_bound_errors(fid, items, condition_ids):
    """An open item that keeps a shortfall open names the clause whose bound it took loose."""
    errors = []
    for item in items:
        if not text(item.get('margin_not_decisive_reason')):
            continue
        if item.get('loose_bound') not in condition_ids:
            errors.append('%s/%s: a shortfall kept open names in loose_bound the condition id whose bound was taken '
                          'loose (the one whose tightening could clear it)' % (fid, item.get('key', '?')))
    return errors


def _shortfall_fix_errors(fid, fails, findings):
    """A fail item recording a computed shortfall points at a finding that carries the change clearing it."""
    errors = []
    for item in fails:
        finding = findings.get(item.get('finding_id')) or {}
        remediation = finding.get('remediation')
        if not (isinstance(remediation, dict) and remediation.get('readiness') in READINESS):
            errors.append('%s/%s: a computed shortfall is cleared by a change; finding %s needs remediation '
                          '(readiness %s and what it changes)'
                          % (fid, item.get('key', '?'), item.get('finding_id'), '/'.join(READINESS)))
    return errors


def _margin_errors(fid, fn, calculation, condition_ids=frozenset(), findings=None):
    """F4 both ways, and F8: a design value left open beside a calculation states its margin."""
    errors = []
    findings = findings or {}
    found = [(m['value'], m.get('aspect') or calculation.get('aspect'), m)
             for m in results_model.margins(calculation) if type(m['value']) in (int, float)]
    opens = [i for i in fn.get('open') or [] if isinstance(i, dict)]
    fails = [i for i in fn.get('fails') or [] if isinstance(i, dict)]
    for value, aspect, m in found:
        if value > 0:   # a positive margin decides; an open item on the same aspect needs a reason
            for item in opens:
                if _covers(item, aspect) and not text(item.get('margin_not_decisive_reason')):
                    errors.append('%s/%s: calculation shows %s %s margin against %s, yet this stays open; conclude, '
                                  'or say in margin_not_decisive_reason why the margin does not decide it'
                                  % (fid, item.get('key', '?'), value, m.get('unit'), m.get('against')))
            continue
        # no headroom against the limit: the guarantee is not met, which is a fail item, not an open one
        covering_fails = [i for i in fails if _covers(i, aspect)]
        if covering_fails:
            errors.extend(_shortfall_fix_errors(fid, covering_fails, findings))
            continue
        kept = [i for i in opens if _covers(i, aspect) and text(i.get('margin_not_decisive_reason'))]
        if kept:
            errors.extend(_loose_bound_errors(fid, kept, condition_ids))
            continue
        errors.append('%s: calculation shows %s %s against %s%s — the worst case misses the limit; record a fail item '
                      'with its finding (保证要求未满足), or keep it open only with margin_not_decisive_reason naming the '
                      'loose bound whose tightening could clear it'
                      % (fid, value, m.get('unit'), m.get('against'), (' (' + aspect + ')') if aspect else ''))
    if calculation.get('claim_ids'):   # F8
        for item in opens:
            if item.get('kind') != 'DESIGN_VALUE' or text(item.get('no_margin_reason')):
                continue
            if not any(_covers(item, aspect) for _, aspect, _ in found):
                errors.append('%s/%s: the function computed %s but gives no margin on the aspects this design value '
                              'leaves open; write calculation.margin for them (worst case against the limit, project '
                              'derating included), or say in no_margin_reason what the design has not chosen yet'
                              % (fid, item.get('key', '?'), '/'.join(calculation['claim_ids'])))
    return errors


def _worst_case_errors(label, item, condition_ids):
    """F3: the worst case under the public bound (which clause, what value, how it bounds) and its margin,
    or the curves and tables searched before calling the quantity unboundable."""
    worst = item.get('worst_case')
    if not isinstance(worst, dict):
        return [label + ': worst_case gives the result under the public bound, or why it cannot be bounded']
    if text(worst.get('not_boundable_reason')):
        if not evidence(worst.get('curves_checked')):
            return [label + ': worst_case.curves_checked lists the datasheet figures, published tables and application '
                            'notes searched for a bound (source, locator) before the quantity is called unboundable']
        specified = worst.get('operating_point_specified')
        if not isinstance(specified, bool):
            return [label + ': worst_case.operating_point_specified says whether the datasheet specifies the part at '
                            'this operating point at all (true: only the parameter is missing)']
        if not specified:
            return [label + ': the datasheet does not specify the part at this operating point; relying on it is a design '
                            'risk — record a fail item whose finding moves the design into the specified region, '
                            'not a vendor request']
        return []
    errors = []
    bound = worst.get('bound')
    if not (isinstance(bound, dict) and bound.get('condition') in condition_ids and text(bound.get('value'))
            and bound.get('basis') in BOUND_BASES):
        errors.append('%s: worst_case.bound names the public bound used before asking the vendor: condition (a clause '
                      'id), value, basis one of %s' % (label, '/'.join(BOUND_BASES)))
    if not text(worst.get('result')):
        errors.append(label + ': worst_case.result states the outcome under the public bound')
    margin = worst.get('margin')
    if not (isinstance(margin, dict) and type(margin.get('value')) in (int, float) and text(margin.get('unit'))
            and text(margin.get('against'))):
        errors.append(label + ': worst_case.margin {value: number, unit, against} under the public bound')
    return errors


def _datum_margin_errors(fid, fn, item, condition_ids, findings):
    """The margin under the public bound decides like a computed one (F4): positive concludes, a shortfall is a
    fail item on the aspect or stays open naming the loose bound."""
    worst = item.get('worst_case') if isinstance(item.get('worst_case'), dict) else {}
    margin = worst.get('margin') if isinstance(worst.get('margin'), dict) else {}
    if type(margin.get('value')) not in (int, float):
        return []
    value = margin['value']
    label = '%s/%s' % (fid, item.get('key', '?'))
    if value > 0:
        if text(item.get('margin_not_decisive_reason')):
            return []
        return ['%s: the worst case under the public bound (%s) shows %s %s margin against %s — the public bound '
                'already decides; conclude PASS(B) with the bound in conditions, or say in margin_not_decisive_reason '
                'what the bound misses' % (label, (worst.get('bound') or {}).get('value'), value, margin.get('unit'),
                                          margin.get('against'))]
    aspects = {a for a, _ in _decides(item)}
    fails = [i for i in fn.get('fails') or [] if isinstance(i, dict) and any(_covers(i, a) for a in aspects)]
    if fails:
        return _shortfall_fix_errors(fid, fails, findings)
    if text(item.get('margin_not_decisive_reason')):
        return _loose_bound_errors(fid, [item], condition_ids)
    return ['%s: the worst case under the public bound shows %s %s against %s — the worst case misses the limit; '
            'record a fail item with its finding (保证要求未满足), or keep it open only with margin_not_decisive_reason '
            'and loose_bound naming the clause whose bound was taken loose'
            % (label, value, margin.get('unit'), margin.get('against'))]


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
    if kind == 'DELIVERABLE_PENDING':
        stray = [f for f in ('spec', 'acquisition', 'checked', 'worst_case') if f in item]
        if stray:
            errors.append('%s: %s only belong to DESIGN_VALUE/VENDOR_DATUM' % (label, '/'.join(stray)))
        for field in DELIVERABLE_FIELDS:
            if not text(item.get(field)):
                errors.append('%s: a pending deliverable names %s (what another stage owes, who owes it, what this '
                              'verdict assumed from it, what closes it)' % (label, '/'.join(DELIVERABLE_FIELDS)))
                break
        if not text(item.get('scope')):
            errors.append(label + ': scope required (the conditions the deliverable must cover)')
        if item.get('deliverable_kind') not in DELIVERABLE_KINDS:
            errors.append('%s: deliverable_kind is one of %s; a parameter of a catalog part is a VENDOR_DATUM with its '
                          'public bound' % (label, '/'.join(DELIVERABLE_KINDS)))
    elif kind not in REQUEST_KINDS:
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
        errors.extend(_worst_case_errors(label, item, condition_ids))
    if kind == 'USER_DEFERRED' and not evidence(item.get('instruction')):
        errors.append(label + ': a deferral cites the user instruction (instruction evidence)')
    return errors


def function_errors(report):
    """F1–F4, F6, F7 and the shape of every function verdict; no plan needed."""
    errors = []
    functions = report.get('functions')
    if not isinstance(functions, list):
        return errors   # results_model.shape_errors names this
    findings = {f.get('id'): f for f in report.get('findings') or [] if isinstance(f, dict)}
    finding_ids = set(findings)
    seen_ids, seen_keys = set(), {}
    for fn in functions:
        if not isinstance(fn, dict) or not (text(fn.get('id')) and ID_RE.match(fn['id'])):
            errors.append('functions[]: each verdict has an id like FN-BIAS')
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
            items = margin if isinstance(margin, list) else [margin]
            if margin is not None and not (items and all(
                    isinstance(m, dict) and type(m.get('value')) in (int, float) and text(m.get('unit'))
                    and text(m.get('against')) and ('aspect' not in m or text(m['aspect'])) for m in items)):
                errors.append(fid + ': calculation.margin is {value: number, unit, against[, aspect]} or a list of them')
        errors.extend(_judgement_errors(fid, fn, condition_ids))
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
                if field == 'open' and item.get('kind') == 'VENDOR_DATUM':
                    errors.extend(_datum_margin_errors(fid, fn, item, condition_ids, findings))
        if isinstance(calculation, dict):   # F4, F8
            errors.extend(_margin_errors(fid, fn, calculation, condition_ids, findings))
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
    errors.extend(_shared_assumption_errors(functions))
    return errors


def _shared_assumption_errors(functions):
    """An assumption says what that calculation assumed; one sentence copied into several functions assumes nothing."""
    owners = {}
    for fn in functions:
        calc = fn.get('calculation') if isinstance(fn, dict) and isinstance(fn.get('calculation'), dict) else {}
        for a in calc.get('assumptions') or []:
            if text(a):
                owners.setdefault(a.strip(), []).append(fn['id'])
    return ['%s: the same assumption in every one of these calculations (%s); write what each calculation assumed, '
            'and put a shared operating condition in intent once' % (', '.join(sorted(set(ids))), a[:40])
            for a, ids in owners.items() if len(set(ids)) > 1]


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
        if fid is not None and result == 'FAIL' and document_row(cid):
            errors.append('%s: a document defect stands on its own row with its finding, not bound to %s; '
                          'functions answer circuits' % (cid, fid))
        state = ((expected.get(cid) or {}).get('object') or {}).get('state')
        for field in ('open_ref', 'fail_ref'):
            ref = row.get(field)
            if ref is None or ref not in items or not text(row.get('aspect')):
                continue   # shape_errors names a missing ref or aspect
            fn, item, _ = items[ref]
            if not decides_row(item, row['aspect'], state):
                errors.append('%s: %s %s does not decide aspect %s%s; extend its decides or bind the row elsewhere'
                              % (cid, field, ref, row['aspect'], (' in state ' + state) if state else ''))
        if (result == 'PASS' and fid is not None and cid not in history_ids and text(row.get('aspect'))
                and judged(functions[fid], row['aspect'], state) is None):
            errors.append(unjudged_message(cid, fid, row['aspect'], state))
        if result == 'FAIL' and fid is not None and cid not in history_ids and 'fail_ref' not in row:
            errors.append(cid + ': a FAIL row bound to a function names the fail item that records it (fail_ref)')
        if result == 'FAIL' and 'fail_ref' in row and row['fail_ref'] in items:
            finding = items[row['fail_ref']][1].get('finding_id')
            if row.get('finding_id') not in (None, finding):
                errors.append('%s: finding_id %s differs from the fail item\'s %s' % (cid, row.get('finding_id'), finding))
    return errors


REVIEWED = ('PASS', 'FAIL', 'INSUFFICIENT')


def row_anchors(planned):
    """(refs, nets) a plan row is about, from its object."""
    obj = (planned or {}).get('object') if isinstance(planned, dict) else None
    if not isinstance(obj, dict):
        return set(), set()
    refs = {obj.get('ref')} | set(obj.get('refs') or [])
    if isinstance(obj.get('node'), str):
        refs.add(obj['node'].partition('.')[0])
    nets = {obj.get('net')} | set(obj.get('nets') or [])
    return {r for r in refs if text(r)}, {n for n in nets if text(n)}


def delegated(row, planned, functions_by_id):
    """A member row bound to another frame's function: allowed when that function's objects cover
    every ref and net the row is about (two circuits declared over the same parts, e.g. a UART link
    and its level interface), so the shared subject is judged once instead of duplicating open items."""
    fn = functions_by_id.get(row.get('function_id'))
    if not isinstance(fn, dict):
        return False
    objects = fn.get('objects') if isinstance(fn.get('objects'), dict) else {}
    refs, nets = row_anchors(planned)
    return bool(refs or nets) and refs <= set(objects.get('refs') or []) and nets <= set(objects.get('nets') or [])


def frame_errors(plan, checks, functions):
    """Plan frames (one per intent circuit) are answered: a reviewed member row binds to its frame's
    function (or to another frame's function whose objects cover the row) and keeps the frame's aspect;
    a frame with a reviewed member of its own has a function verdict."""
    errors = []
    by_id = {fn['id']: fn for fn in functions or [] if isinstance(fn, dict) and text(fn.get('id'))}
    ids = set(by_id)
    planned_rows = {c['id']: c for c in (plan or {}).get('checks') or [] if isinstance(c, dict) and text(c.get('id'))}
    for frame in (plan or {}).get('functions') or []:
        if not isinstance(frame, dict) or not text(frame.get('id')):
            continue
        answered = False
        for member in frame.get('members') or []:
            row = checks.get(member.get('check_id')) if isinstance(member, dict) else None
            if not isinstance(row, dict) or row.get('review_result') not in REVIEWED:
                continue
            if row.get('function_id') != frame['id']:
                if delegated(row, planned_rows.get(member['check_id']), by_id):
                    continue
                errors.append('%s: a member of frame %s binds to it (function_id), not to %s'
                              ' (another function may take the row only when its objects cover the row)'
                              % (member['check_id'], frame['id'], row.get('function_id')))
                continue
            answered = True
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

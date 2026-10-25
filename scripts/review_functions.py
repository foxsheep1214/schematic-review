"""Function verdicts: the unit of judgement (docs/2026-10-20-function-verdicts-design.md, §4 and §7).

A function verdict answers one question about one circuit block. Before it may leave anything open
it must have listed the datasheet clauses that bear on the question (F1), kept a design value as a
specification instead of a vendor request (F2), named what was checked and the worst case before
asking a vendor (F3: the worst case under the public bound, its margin deciding like any other, or the
curves and tables searched before calling it unboundable), and drawn the conclusion a computed margin
already gives (F4). Rows only follow the verdict (F5); a changed verdict cites a clause or a number (F6);
a gap names, for every row it blocks, what it enters (F7); a design value left open beside a
calculation states its margin (F8); a deliverable another stage owes (DELIVERABLE_PENDING) names the
deliverable, its owner and what the verdict assumed. Document checks are not functions: a document defect
is not bound to one, and a function of document rows only is not counted.

Evidence has three layers (merge plan of 2026-10-21, §3–§4). Where it comes from: every condition is located
(page, table, section, a datasheet section title, a requirement or record id, a designator, named nets or
pins). What kind it is: a NUMERIC_LIMIT (min/max with unit and the regime it holds in, the number quoted), a
MANDATORY_CLAUSE (a normative sentence and the precondition it applies under; no number needed; a typical
application is not one), a NETLIST_FACT (named nets/pins the netlist has), a TYPICAL_REFERENCE or an
ENGINEERING_ASSUMPTION. What it proves: a margin states its basis — GUARANTEED_BOUND (a lower bound of the
margin over the required range: satisfied, it passes; missed, it only fails to prove), REACHABLE_CASE (a case
shown to occur: missed, it fails; met, it proves nothing over the range), EXACT_ENVELOPE (the full worst-case
envelope: decides both ways) or ESTIMATE (decides nothing) — with GE/GT saying whether a zero margin passes.
A numeric limit is compared in a margin, never asserted in a judgement sentence; a fail rests on a shortfall
a margin proves or on a violated mandatory clause; PASS and FAIL evidence over the same scope is a conflict.
Scope is explicit: evidence without `states` covers only rows without a state (STATELESS), never all states.
A gap blocks a row through an edge (`decides[]` entry) that says what the missing quantity enters
(`via`: a condition, or a calculation claim and its input) and why the available bound does not decide it;
how many rows one gap blocks is a diagnostic, not a limit.

Two reviewers of the same board diverged most where the record let a judgement rest on nothing a reader can
open, so a circuit function cites at least one clause (F1), every judgement rests on a mandatory clause or a
netlist fact (F9), the same unlocated condition in several functions is a template (F10), a frame's function
judges the frame's objects and a row the reviewer binds to a function names an object of that function (F11),
and a connector row with clamp parts is judged in a function (F12). None of this proves the electrical judgement.
"""
import re

import bound_formulas
import catalog
import function_reading
import results_model
from electrical_contract import LOCATOR_IDS_RE, LOCATOR_WORDS_RE, PHASES, finite, squeeze, text
from function_reading import (requirement_document as _requirement_document, requirement_rows,
                              ESTIMATE_PASS_CLASSES, covers, decides_row, edges, estimate_handoff,
    estimate_passes, judged, life_estimate, life_row, margin_proves, margin_verdict, overlaps,
    prototype_estimate, reference_circuit, reference_judged, scope, unjudged_message)
from results_model import LEVELS, OPEN_KINDS, VERDICTS
from validate_remediation import READINESS

CONDITION_FIELDS = ('id', 'source', 'locator', 'says', 'use')
REQUEST_KINDS = ('DESIGN_VALUE', 'VENDOR_DATUM')
# How a public number bounds the quantity at the design's operating point (F3).
BOUND_BASES = ('GUARANTEED_LIMIT', 'ADJACENT_TEST_POINT', 'TYPICAL_CURVE', 'PUBLISHED_TABLE', 'APPLICATION_NOTE')
# An unboundable quantity leaves one bound open (results format 6) and says how the other one is settled.
OPEN_SIDES = ('UPPER', 'LOWER')
OTHER_SIDES = ('DECIDED', 'NOT_DECISIVE')
FORMULA_TOLERANCE = 0.005   # a rerun bounding formula may differ from the written value by rounding only
DELIVERABLE_FIELDS = ('deliverable', 'owner', 'assumed', 'closure')
# What another stage owes; a parameter of a catalog part is none of these (it is a VENDOR_DATUM with its public bound).
DELIVERABLE_KINDS = ('CUSTOM_PART_DRAWING', 'FIRMWARE_CAPABILITY', 'CONFIGURATION_TABLE')
VENDOR_ASK_RE = re.compile(r'向[^，,；;。]{0,16}(?:原厂|厂商|厂家|供应商|[A-Z][A-Za-z]{2,})[^，,；;。]{0,8}(?:索取|取得|索要|要)'
                           r'|ask(?:ing)? (?:the )?(?:vendor|supplier|manufacturer)|request(?:ed)? from (?:the )?(?:vendor|supplier)', re.I)
CONDITION_KINDS = ('NUMERIC_LIMIT', 'MANDATORY_CLAUSE', 'NETLIST_FACT', 'TYPICAL_REFERENCE', 'ENGINEERING_ASSUMPTION')
CLAUSE_KINDS = ('NUMERIC_LIMIT', 'MANDATORY_CLAUSE')       # what a vendor, a standard or a requirement says
WEAK_KINDS = ('TYPICAL_REFERENCE', 'ENGINEERING_ASSUMPTION')
BASIS_KINDS = ('GUARANTEED_BOUND', 'REACHABLE_CASE', 'EXACT_ENVELOPE', 'ESTIMATE')
COMPARISONS = ('GE', 'GT')       # GE: a zero margin passes; GT: it does not
# How a decisive bound was obtained (results 5, consistency proposals 2026-10-23 1a): a limit holding at this point, a
# test point carried over a monotonic curve, a temperature coefficient, a published table; a typical curve only estimates.
DERIVATIONS = ('GUARANTEED_LIMIT', 'ADJACENT_TEST_POINT', 'MONOTONIC', 'TEMPCO', 'PUBLISHED_TABLE', 'TYPICAL_CURVE')
CORNER_ENDS = ('min', 'max')
EDGE_EFFECTS = ('BLOCKS_PROOF', 'INFORMATION_ONLY')
EDGE_KINDS = ('DESIGN_VALUE', 'VENDOR_DATUM', 'DELIVERABLE_PENDING')   # gaps in a quantity: each edge says what it enters
WIDE_GAP = 3                     # more blocked aspects than this is reported for a second look, never refused
LIFE_ASPECTS = ('电容有效容量与寿命', '耗损件寿命')   # catalog titles of DEV-C02 and DEV-C06
RETIRED_ITEM_FIELDS = {
    'margin_not_decisive_reason': "the margin's basis says whether it decides (an ESTIMATE or a missed GUARANTEED_BOUND "
                                  "does not); the open item's edges say what it blocks and why",
    'loose_bound': 'the basis names the limit and conditions the bound was taken from',
    'decides_reason': 'every edge in decides names its via and rationale; the count is no longer limited',
}
NORMATIVE_RE = re.compile(r'\b(?:must|shall|required|do not|never|not (?:be )?(?:allowed|permitted|exceed)|is prohibited)\b'
                          r'|必须|(?<!无)须|应当|应该|不得|不能|不可|不要|禁止|不允许|务必|严禁', re.I)
TYPICAL_PLACE_RE = re.compile(r'典型应用|应用电路|应用说明|参考设计|typical application|reference design|application (?:note|circuit)', re.I)
NUMBER_RE = re.compile(r'[-+]?\d+(?:\.\d+)?')
PIN_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_]*\.[A-Za-z0-9_+-]+$')
# A judgement that only says the aspect does not apply (proposals of 2026-10-23, item 2c).
NOT_APPLIES_RE = re.compile(r'不适用|无此问题|按拓扑(无|不)|不涉及')
TEMPLATE_FIELDS = ('no_margin_reason', 'why_insufficient')
ID_RE = re.compile(r'^FN-[A-Za-z0-9][A-Za-z0-9_.-]*$')
KEY_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]*$')


def evidence(value):
    return isinstance(value, list) and bool(value) and all(
        isinstance(x, dict) and text(x.get('source')) and text(x.get('locator')) for x in value)


def located(condition):
    """The condition's locator names a place a reader can open in its source."""
    locator = condition.get('locator') if isinstance(condition, dict) else None
    return text(locator) and bool(LOCATOR_WORDS_RE.search(locator) or LOCATOR_IDS_RE.search(locator))


def _numbers(says):
    return [float(x) for x in NUMBER_RE.findall(str(says or '').replace('−', '-').replace(',', ''))]


_finite = finite


def quotes(condition, value):
    """The condition's own text says this number."""
    return any(abs(n - value) <= 1e-9 * max(1.0, abs(value)) or abs(abs(n) - abs(value)) <= 1e-9 * max(1.0, abs(value))
               for n in _numbers(condition.get('says')))


PIN_SECTION_RE = re.compile(r'引脚说明|引脚定义|引脚功能|管脚|pin (?:description|function|assignment|configuration)s?', re.I)
OPERATING_SECTION_RE = re.compile(r'推荐工作|recommended operating|电气特性|电气参数|electrical characteristics'
                                  r'|绝对最大|absolute maximum', re.I)
PIN_POINT_RE = re.compile(r'引脚|脚|\bpins?\b', re.I)


def clause(condition):
    """A located numeric limit or mandatory clause: what a datasheet, standard or requirement says."""
    if not (isinstance(condition, dict) and condition.get('kind') in CLAUSE_KINDS and located(condition)):
        return False
    if condition['kind'] == 'MANDATORY_CLAUSE':
        return bool(NORMATIVE_RE.search(condition.get('says') or '')) and not TYPICAL_PLACE_RE.search(condition.get('locator') or '')
    limit = condition.get('limit') if isinstance(condition.get('limit'), dict) else {}
    values = [limit[k] for k in ('min', 'max') if _finite(limit.get(k))]
    return bool(values) and all(quotes(condition, v) for v in values)


def net_name(net):
    """A net without its sheet path: /07_PD/TEMP and TEMP are the same net."""
    return net.rsplit('/', 1)[-1] if isinstance(net, str) else net


def _decides(item):
    """(aspect, states or None) per blocking edge, for the shape checks that only need the aspects."""
    return [(d['aspect'], set(d['states']) if isinstance(d.get('states'), list) and d['states'] else None)
            for d in edges(item)]


def _condition_errors(label, c, db=None):
    """The second evidence layer: what kind of statement a condition is, and the fields that kind needs."""
    kind = c.get('kind')
    if kind not in CONDITION_KINDS:
        return ['%s: kind is one of %s' % (label, '/'.join(CONDITION_KINDS))]
    errors = []
    if kind in ('NUMERIC_LIMIT', 'MANDATORY_CLAUSE', 'TYPICAL_REFERENCE') and not located(c):
        errors.append('%s: a %s is located — a page, table or section, a datasheet section title, a requirement id; '
                      '"%s" locates nothing' % (label, kind, c.get('locator')))
    if kind == 'NUMERIC_LIMIT':
        limit = c.get('limit') if isinstance(c.get('limit'), dict) else {}
        values = [limit[k] for k in ('min', 'max') if k in limit]
        if not (values and all(_finite(v) for v in values) and text(limit.get('unit'))):
            errors.append(label + ': a NUMERIC_LIMIT gives limit {min and/or max (finite numbers), unit}; a typical value '
                                  'alone is a TYPICAL_REFERENCE')
        elif not all(quotes(c, v) for v in values):
            errors.append('%s: says does not quote the limit %s; quote the clause that gives it'
                          % (label, '/'.join(str(v) for v in values)))
        if re.search(r'bom', c.get('source') or '', re.I) and bom_parts(db):
            errors.extend(_bom_quote_errors(label, c, bom_parts(db)))
        if not text(c.get('regime')):
            errors.append(label + ': regime says where the limit holds (temperature, waveform or pulse width, mode, variant)')
    elif kind == 'MANDATORY_CLAUSE':
        if not NORMATIVE_RE.search(c.get('says') or ''):
            errors.append(label + ': a MANDATORY_CLAUSE quotes the normative sentence (must/shall/required/须/不得…); a '
                                  'description is a TYPICAL_REFERENCE or a NETLIST_FACT')
        if TYPICAL_PLACE_RE.search(c.get('locator') or ''):
            errors.append(label + ': a typical application is a TYPICAL_REFERENCE, not a mandatory clause')
        if not text(c.get('applies')):
            errors.append(label + ': applies says the precondition under which the clause binds this design')
    elif kind == 'TYPICAL_REFERENCE' and 'reference_circuit' in c and not reference_circuit(c):
        errors.append(label + ': reference_circuit is {figure (the figure or page of the vendor circuit), connection '
                              '(how this board connects the same way), load (its values against this board: no heavier)}')
    if kind == 'TYPICAL_REFERENCE' and 'curve' in c and not isinstance(c['curve'], bool):
        errors.append(label + ': curve is true when the reference is a typical curve or characteristic plot, false or '
                              'absent for application text')
    if 'setting' in c and not (isinstance(c['setting'], dict) and set(c['setting']) == {'ref', 'group', 'value'}
                               and all(text(v) for v in c['setting'].values())):
        errors.append(label + ': setting is {ref, group, value}: the device, its configuration group and the value the '
                              'condition holds at')
    if kind == 'NETLIST_FACT':
        nets = [n for n in c.get('nets') or [] if text(n)] if isinstance(c.get('nets'), list) else []
        pins = [n for n in c.get('pins') or [] if text(n)] if isinstance(c.get('pins'), list) else []
        if not (nets or pins) or any(not PIN_RE.match(n) for n in pins):
            errors.append(label + ': a NETLIST_FACT names the nets and/or pins (REF.PIN) it is about')
        elif isinstance(db, dict):
            errors.extend(_netlist_name_errors(label, nets, pins, db))
    return errors


def bom_parts(db):
    """The BOM rows by designator, each with its Value column (read_bom keeps that one in db.parts)."""
    bom = db.get('bom') if isinstance(db, dict) else None
    parts = bom.get('parts') if isinstance(bom, dict) else None
    if not isinstance(parts, dict):
        return {}
    values = db.get('parts') if isinstance(db.get('parts'), dict) else {}
    return {ref: dict(row, Value=(values.get(ref) or {}).get('value')) if isinstance(row, dict)
            and isinstance(values.get(ref), dict) and (values.get(ref) or {}).get('value') else row
            for ref, row in parts.items()}


_squeeze = squeeze   # BOM text compared without spacing


def _bom_text(parts, ref):
    row = parts.get(ref)
    return _squeeze(' '.join(str(v) for v in row.values())) if isinstance(row, dict) else ''


def _bom_quote_errors(label, c, parts):
    """A limit taken from the BOM (a custom part bought to its specification) quotes that part's BOM row."""
    refs = [r for r in DESIGNATOR_RE.findall(c.get('locator') or '') if r in parts]
    if not refs:
        return ['%s: a limit from the BOM names, in locator, the part whose BOM row it quotes' % label]
    if not any(_squeeze(c.get('says')) in _bom_text(parts, r) for r in refs):
        return ['%s: says is not in the BOM row of %s; quote the specification as the BOM writes it'
                % (label, '/'.join(refs))]
    return []


def _stated_in_bom(text_, name, unit):
    """The BOM text gives the parameter a value: its name, then a number in its unit."""
    return bool(re.search(re.escape(_squeeze(name)) + r'[^0-9]{0,6}?[-+]?\d+(?:\.\d+)?' + re.escape(_squeeze(unit)),
                          text_, re.I))


def _missing_parameter_errors(label, item, db):
    """A pending custom-part drawing lists the parameters the verdict needs and the BOM does not state."""
    missing = item.get('missing_parameters')
    if not (isinstance(missing, list) and missing and all(isinstance(m, dict) and text(m.get('name')) for m in missing)):
        return ['%s: a custom part drawing lists missing_parameters [{name[, unit]}] — the parameters the verdict needs '
                'that the BOM specification does not state; what the BOM states is a design value, cite it as a '
                'NUMERIC_LIMIT from the BOM row' % label]
    parts = bom_parts(db)
    refs = [r for r in DESIGNATOR_RE.findall(' '.join(str(item.get(f) or '') for f in ('deliverable', 'what')))
            if r in parts]
    errors = []
    for m in missing:
        if not text(m.get('unit')):
            continue   # a qualification or an insulation approval has no value to find
        for ref in refs:
            if _stated_in_bom(_bom_text(parts, ref), m['name'], m['unit']):
                errors.append('%s: the BOM row of %s already states %s; it is a design value — cite it as a '
                              'NUMERIC_LIMIT from the BOM row, not a missing parameter' % (label, ref, m['name']))
    return errors


def _undecided_errors(label, item, db):
    """Consistency item 3: a design value lists the part parameters the design has not chosen, or hangs on the open
    item that decides it (depends_on, checked across the review). A parameter its part's BOM row states is set by the
    board."""
    if 'depends_on' in item:
        if not text(item['depends_on']):
            return [label + ': depends_on is the key of the open item of this review that decides this quantity']
        return []
    undecided = item.get('undecided')
    if not (isinstance(undecided, list) and undecided and all(
            isinstance(u, dict) and text(u.get('parameter')) and ('ref' not in u or text(u['ref'])) for u in undecided)):
        return ['%s: a design value lists undecided [{ref, parameter[, unit]}] — the part parameters the design has not '
                'chosen — or names in depends_on the open item of this review that decides it' % label]
    parts = bom_parts(db)
    return ['%s: this quantity is set by %s on the board — its BOM row states %s; compute it from the BOM row (a '
            'NUMERIC_LIMIT), or hang the item on the open item that decides it (depends_on)'
            % (label, u['ref'], u['parameter']) for u in undecided
            if u.get('ref') in parts and text(u.get('unit'))
            and _stated_in_bom(_bom_text(parts, u['ref']), u['parameter'], u['unit'])]


def _dependency_errors(functions):
    """A design value hangs on an open item of this review, not on itself, one level deep."""
    items = results_model.open_items({'functions': [fn for fn in functions if isinstance(fn, dict)]})
    leads = {item['key']: item for item, field in ((v[1], v[2]) for v in items.values()) if field == 'open'}
    errors = []
    for ref, (_, item, field) in items.items():
        target = item.get('depends_on')
        if field != 'open' or not text(target):
            continue
        if target not in leads:
            errors.append('%s: depends_on names %s, which is not another open item of this review' % (ref, target))
        elif 'depends_on' in leads[target]:
            errors.append('%s: depends_on names %s, which itself hangs on %s; hang it on the item that decides it'
                          % (ref, target, leads[target]['depends_on']))
    return errors


def _netlist_name_errors(label, nets, pins, db):
    errors = []
    known = db.get('nets') if isinstance(db.get('nets'), dict) else {}
    for net in nets:
        if net in known:
            continue
        leaf = [n for n in known if net_name(n) == net]
        if len(leaf) > 1:
            errors.append('%s: net %s is ambiguous (%s); name its full path' % (label, net, ', '.join(sorted(leaf))))
        elif not leaf:
            errors.append('%s: net %s is not in the netlist' % (label, net))
    pin2net = db.get('pin2net') if isinstance(db.get('pin2net'), dict) else {}
    errors += ['%s: pin %s is not in the netlist' % (label, pin) for pin in pins if pin not in pin2net]
    return errors


def netlist_evidence_errors(label, entries, db):
    """An NA where the plan found the mechanism (consistency proposals item 2d): some entry names the nets and/or pins
    (REF.PIN) that rule it out, and the netlist has them."""
    named = [e for e in entries or [] if isinstance(e, dict) and (e.get('nets') or e.get('pins'))]
    if not named:
        return [label + ': the plan found this rule\'s mechanism; an NA names the netlist fact that rules it out: an '
                        'applicability_evidence entry with nets and/or pins (REF.PIN) the netlist has']
    errors = []
    for e in named:
        nets = [n for n in e.get('nets') or [] if text(n)] if isinstance(e.get('nets'), list) else []
        pins = [n for n in e.get('pins') or [] if text(n)] if isinstance(e.get('pins'), list) else []
        if any(not PIN_RE.match(n) for n in pins) or not (nets or pins):
            errors.append(label + ': applicability_evidence nets and pins are lists of names (pins as REF.PIN)')
        elif isinstance(db, dict):
            errors.extend(_netlist_name_errors(label, nets, pins, db))
    return errors


def _basis_errors(label, m, conditions, claim_ids):
    """The third layer: what a margin proves. Decisive kinds name the limit compared against, a numeric limit, and the
    regime the computed quantity holds at; a different regime from the limit's needs a conversion."""
    basis = m.get('basis')
    if not (isinstance(basis, dict) and basis.get('kind') in BASIS_KINDS and basis.get('comparison') in COMPARISONS
            and text(basis.get('scope'))):
        return ['%s: margin basis {kind %s, comparison GE/GT, scope, conditions[, limit, regime]} says what the number '
                'proves' % (label, '/'.join(BASIS_KINDS))]
    errors = []
    ids = basis.get('conditions') if isinstance(basis.get('conditions'), list) else []
    if any(c not in conditions for c in ids):
        errors.append('%s: basis.conditions names condition ids of this function (%s)' % (
            label, ', '.join(str(c) for c in ids if c not in conditions)))
    errors.extend(_formula_errors(label, basis))
    kind = basis['kind']
    if kind == 'ESTIMATE':
        if 'consequence_class' in basis and basis['consequence_class'] not in ESTIMATE_PASS_CLASSES:
            errors.append('%s: an estimate passes only a required function or a performance (consequence_class %s); '
                          'damage, overheating and protection need a guaranteed bound' % (label, '/'.join(ESTIMATE_PASS_CLASSES)))
        if ('consequence_class' in basis) != ('handoff' in basis):
            errors.append(label + ': an estimate that passes names both its consequence_class and the prototype handoff '
                                  '(handoff: index into the function\'s handoffs)')
        return errors
    limit = conditions.get(basis.get('limit'))
    if not (limit and limit.get('kind') == 'NUMERIC_LIMIT'):
        errors.append('%s: a %s names in basis.limit the NUMERIC_LIMIT it is compared against' % (label, kind))
    used = [conditions[c] for c in ids if c in conditions] + ([limit] if limit else [])
    weak = sorted({c['id'] for c in used if c.get('kind') in WEAK_KINDS
                   and (kind != 'REACHABLE_CASE' or c['kind'] == 'ENGINEERING_ASSUMPTION')})
    if weak:
        errors.append('%s: a %s does not rest on %s (%s); a bound built on them is an ESTIMATE'
                      % (label, kind, 'an assumption' if kind == 'REACHABLE_CASE' else 'typical values or assumptions',
                         ', '.join(weak)))
    errors.extend(_derivation_errors(label, basis, conditions))
    if kind == 'EXACT_ENVELOPE' and not all(text(basis.get(f)) for f in ('model', 'domain', 'extremum')):
        errors.append(label + ': an EXACT_ENVELOPE names the model, the domain it covers and why the extremum is in it '
                              '(model, domain, extremum)')
    if kind == 'REACHABLE_CASE' and not text(basis.get('joint')):
        errors.append(label + ': a REACHABLE_CASE says in joint why its parameter values occur together')
    if limit and text(limit.get('regime')):
        if not text(basis.get('regime')):
            errors.append('%s: basis.regime says where the computed quantity holds, to compare with the limit\'s (%s)'
                          % (label, limit['regime']))
        elif (_norm(basis['regime']) != _norm(limit['regime'])
              and not (basis.get('conversion') in conditions or basis.get('conversion') in claim_ids)):
            errors.append('%s: the quantity holds at %s and the limit %s at %s; a decisive comparison across regimes names '
                          'the conversion or envelope (basis.conversion: a condition or claim id)'
                          % (label, basis['regime'], limit['id'], limit['regime']))
    return errors


def _derivation_errors(label, basis, conditions):
    """1a–1b: how a decisive bound was derived, and which end of each toleranced input it took."""
    derivation = basis.get('derivation')
    if derivation not in DERIVATIONS:
        return ['%s: basis.derivation says how the bound was obtained, one of %s' % (label, '/'.join(DERIVATIONS))]
    errors = []
    if derivation == 'TYPICAL_CURVE' and basis.get('kind') != 'REACHABLE_CASE':   # a typical part is reachable (2-A)
        errors.append(label + ': a bound read off a TYPICAL_CURVE proves nothing for every part; mark the margin ESTIMATE, '
                              'or REACHABLE_CASE when the typical part already falls short')
    if derivation in ('ADJACENT_TEST_POINT', 'MONOTONIC'):
        mono = basis.get('monotonic')
        if not (isinstance(mono, dict) and mono.get('curve') in conditions):
            errors.append('%s: a bound carried from a test point gives basis.monotonic{curve: the condition of this '
                          'function showing the monotonic shape, side: FAVORABLE}' % label)
        elif mono.get('side') != 'FAVORABLE':
            errors.append('%s: the operating point lies on the unfavourable side of the test point, which bounds nothing '
                          'there; only side FAVORABLE carries the bound over' % label)
    if derivation == 'TEMPCO' and (conditions.get(basis.get('tempco')) or {}).get('kind') != 'NUMERIC_LIMIT':
        errors.append(label + ': a bound through a temperature coefficient names in basis.tempco the NUMERIC_LIMIT giving '
                              'its min/max')
    corners = basis.get('corners')
    if not isinstance(corners, list) or (not corners and not text(basis.get('no_corners_reason'))):
        errors.append(label + ': basis.corners[{input, condition, picked: min|max, why}] lists each toleranced input and '
                              'the end of its condition taken (no_corners_reason when no input has a tolerance)')
        return errors
    for i, corner in enumerate(corners):
        condition = conditions.get(corner.get('condition')) if isinstance(corner, dict) else None
        if not (isinstance(corner, dict) and text(corner.get('input')) and text(corner.get('why'))
                and corner.get('picked') in CORNER_ENDS and condition and condition.get('kind') == 'NUMERIC_LIMIT'):
            errors.append('%s: basis.corners[%d] is {input, condition (a NUMERIC_LIMIT of this function), picked min|max, '
                          'why}' % (label, i))
        elif not _finite((condition.get('limit') or {}).get(corner['picked'])):
            errors.append('%s: basis.corners[%d] takes the %s of %s, which gives no %s; take the end the condition gives'
                          % (label, i, corner['picked'], condition['id'], corner['picked']))
    return errors


def _norm(value):
    return re.sub(r'\s+', '', str(value)).lower()


def _edge_errors(label, item, conditions, calculation):
    """F7: every edge of a gap in a quantity says what the quantity enters and why the available bound does not decide
    the row; the target exists. One gap may block many rows, each through its own edge."""
    errors = []
    claim_ids = {c for c in (calculation or {}).get('claim_ids') or [] if isinstance(c, str)}
    inputs = (calculation or {}).get('inputs')
    for i, d in enumerate(item.get('decides') or []):
        if not isinstance(d, dict):
            continue
        where = '%s/decides[%d]' % (label, i)
        if d.get('effect', 'BLOCKS_PROOF') not in EDGE_EFFECTS:
            errors.append(where + ': effect is ' + '/'.join(EDGE_EFFECTS))
        for field in ('states', 'check_ids'):
            if field in d and not (isinstance(d[field], list) and d[field] and all(text(x) for x in d[field])):
                errors.append('%s: %s is a non-empty list' % (where, field))
        if item.get('kind') not in EDGE_KINDS:
            continue   # a fail item rests on its basis; a requirement or a deferral is the row itself
        via = d.get('via')
        if not isinstance(via, dict) or not (via.get('condition') in conditions or via.get('claim') in claim_ids):
            errors.append('%s (%s): via names what the missing quantity enters — {condition: id} of this function or '
                          '{claim: id[, input]} of its calculation' % (where, d.get('aspect')))
        elif 'input' in via and not (isinstance(inputs, list) and via['input'] in inputs):
            errors.append('%s: via.input %s is not among calculation.inputs' % (where, via['input']))
        if not text(d.get('rationale')):
            errors.append('%s (%s): rationale says why the available bound does not decide this row'
                          % (where, d.get('aspect')))
    return errors


def _judgement_errors(fid, fn, conditions_by_id):
    errors = []
    judgements = fn.get('judgements')
    if judgements is None:
        return errors
    if not isinstance(judgements, list):
        return [fid + ': judgements is a list of {aspect, conditions, says[, states]}']
    for i, j in enumerate(judgements):
        conditions = j.get('conditions') if isinstance(j, dict) else None
        if not (isinstance(j, dict) and text(j.get('aspect')) and text(j.get('says'))
                and isinstance(conditions, list) and conditions and all(c in conditions_by_id for c in conditions)):
            errors.append('%s/judgements[%d]: names the aspect, the condition ids it rests on and what they settle (says)'
                          % (fid, i))
            continue
        kinds = {conditions_by_id[c].get('kind') for c in conditions}
        if 'NUMERIC_LIMIT' in kinds:
            errors.append('%s/judgements[%d] (%s): cites a numeric limit (%s); a number is compared in calculation.margin '
                          'with its basis, not settled in a sentence' % (
                              fid, i, j['aspect'], ', '.join(c for c in conditions
                                                             if conditions_by_id[c].get('kind') == 'NUMERIC_LIMIT')))
        elif not (kinds & {'MANDATORY_CLAUSE', 'NETLIST_FACT'}
                  or any(reference_circuit(conditions_by_id[c]) for c in conditions)):   # F9
            errors.append('%s/judgements[%d] (%s): rests on no mandatory clause or netlist fact (%s); a typical value, an '
                          'application circuit or an assumption does not settle a row — a vendor reference circuit does '
                          'when its condition states reference_circuit{figure, connection, load}' % (
                              fid, i, j['aspect'], ', '.join(conditions)))
        if NOT_APPLIES_RE.search(j['says']) and 'NETLIST_FACT' not in kinds:   # consistency proposals item 2c
            errors.append('%s/judgements[%d] (%s): says only that the aspect does not apply, with no netlist fact; record '
                          'the rows NA with applicability_evidence naming the nets or pins that rule the mechanism out'
                          % (fid, i, j['aspect']))
        if 'states' in j and not (isinstance(j['states'], list) and j['states'] and all(text(x) for x in j['states'])):
            errors.append('%s/judgements[%d]: states is a non-empty list' % (fid, i))
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


def _decision_errors(fid, fn, calculation, conditions, findings):
    """F4 and the evidence-conflict rule. Within one aspect and state scope: a margin that proves PASS leaves no gap
    blocking the same proof; a margin that proves FAIL is a fail item with its change; PASS and FAIL evidence over one
    scope is EVIDENCE_CONFLICT; a margin that proves nothing leaves the open item it cannot close; a fail item rests on a
    proven shortfall or a violated mandatory clause, never on a typical circuit alone."""
    errors = []
    default = calculation.get('aspect') if isinstance(calculation, dict) else None
    margins = [(m, scope(m, default), margin_verdict(m)) for m in function_reading.margins(calculation or {})
               if _finite(m.get('value'))]
    judgements = [(j, scope(j)) for j in fn.get('judgements') or [] if isinstance(j, dict) and text(j.get('aspect'))]
    opens = [(i, scope(d)) for i in fn.get('open') or [] if isinstance(i, dict) for d in edges(i)]
    fails = [(i, scope(d)) for i in fn.get('fails') or [] if isinstance(i, dict) for d in edges(i)]

    def name(m):
        return '%s %s against %s' % (m['value'], m.get('unit'), m.get('against'))

    passes = [(m, sc) for m, sc, v in margins if v == 'PASS'] + [(j, sc) for j, sc in judgements]
    for m, sc, verdict in margins:
        if verdict == 'PASS':
            for item, isc in opens:
                if overlaps(sc, isc):
                    errors.append('%s/%s: margin %s is a %s that proves this aspect, yet the item blocks it; mark the edge '
                                  'INFORMATION_ONLY, or call the margin an ESTIMATE if it rests on the undecided value'
                                  % (fid, item.get('key', '?'), name(m), m['basis']['kind']))
        elif verdict == 'FAIL':
            covering = sorted({id(i): i for i, isc in fails if overlaps(sc, isc)}.values(), key=lambda i: str(i.get('key')))
            if covering:
                errors.extend(_shortfall_fix_errors(fid, covering, findings))
            else:
                errors.append('%s: margin %s (%s) proves the worst case misses the limit; record a fail item with its '
                              'finding (保证要求未满足)' % (fid, name(m), m['basis']['kind']))
            for other, osc in passes:
                if overlaps(sc, osc):
                    errors.append('%s: EVIDENCE_CONFLICT — margin %s proves FAIL where %s proves PASS over the same '
                                  'scope; settle which evidence applies' % (fid, name(m), _evidence_name(other)))
        else:
            deciding = ([sc2 for m2, sc2, v2 in margins if v2 != 'OPEN'] + [jsc for _, jsc in judgements]
                        + [isc for _, isc in opens] + [isc for _, isc in fails])
            if (not any(overlaps(sc, other) for other in deciding)
                    and not ((m.get('basis') or {}).get('kind') == 'ESTIMATE' and sc[0] in LIFE_ASPECTS)
                    and not estimate_passes(fn, m)):
                errors.append('%s: margin %s (basis %s) decides nothing; record the open item it leaves, whose edge names '
                              'the bound still missing' % (fid, name(m), (m.get('basis') or {}).get('kind')))
    for j, jsc in judgements:
        for item, isc in opens:
            if overlaps(jsc, isc):
                errors.append('%s/%s: judgement on %s settles what this item says is not proven; one of them is wrong'
                              % (fid, item.get('key', '?'), j['aspect']))
    seen = set()
    for item, isc in fails:
        for other, osc in passes:
            if overlaps(isc, osc):
                errors.append('%s/%s: EVIDENCE_CONFLICT — this fail and %s cover the same scope; settle which evidence '
                              'applies' % (fid, item.get('key', '?'), _evidence_name(other)))
        if id(item) in seen:
            continue
        seen.add(id(item))
        proven = any(v == 'FAIL' and any(overlaps(sc, scope(d)) for d in edges(item)) for _, sc, v in margins)
        cited = [conditions.get(c) for c in item.get('conditions') or [] if c in conditions]
        if any(c not in conditions for c in item.get('conditions') or []):
            errors.append('%s/%s: conditions names condition ids of this function' % (fid, item.get('key', '?')))
        outside = item.get('outside_specified')
        if outside is not None:
            errors.extend(_outside_errors('%s/%s' % (fid, item.get('key', '?')), outside, conditions))
        elif not proven and not any(c.get('kind') == 'MANDATORY_CLAUSE' for c in cited):
            errors.append('%s/%s: a fail rests on a shortfall a margin proves (REACHABLE_CASE or EXACT_ENVELOPE), on a '
                          'violated MANDATORY_CLAUSE in its conditions, or on an operating point outside the region the '
                          'datasheet specifies (outside_specified); a difference from a typical circuit alone is not '
                          'a defect' % (fid, item.get('key', '?')))
    return errors


def _outside_errors(label, outside, conditions):
    """A fail on a point the datasheet does not specify: the clause giving the region it does specify, this board's
    point, and the figures and tables searched for any coverage of that point."""
    if not isinstance(outside, dict):
        return [label + ': outside_specified is {condition, operating_point, curves_checked}']
    errors = []
    if (conditions.get(outside.get('condition')) or {}).get('kind') not in CLAUSE_KINDS:
        errors.append(label + ': outside_specified.condition names the NUMERIC_LIMIT or MANDATORY_CLAUSE of this function '
                              'that gives the region the datasheet does specify')
    if not text(outside.get('operating_point')):
        errors.append(label + ': outside_specified.operating_point states where this board runs the part')
    if not evidence(outside.get('curves_checked')):
        errors.append(label + ': outside_specified.curves_checked lists the figures and tables searched (source, locator) '
                              'for any coverage of this point')
        return errors
    searched = ' '.join(c['locator'] for c in outside['curves_checked'])
    if not OPERATING_SECTION_RE.search(searched):
        errors.append(label + ': outside_specified.curves_checked includes the recommended operating conditions or '
                              'electrical characteristics section — where the datasheet would specify this point')
    if PIN_POINT_RE.search(outside.get('operating_point') or '') and not PIN_SECTION_RE.search(searched):
        errors.append(label + ': the point is a pin\'s; outside_specified.curves_checked includes the pin description '
                              'section — where the datasheet would describe this usage')
    return errors


def _evidence_name(entry):
    if 'value' in entry:
        return 'margin %s %s' % (entry['value'], entry.get('unit') or '')
    return 'judgement on %s' % entry.get('aspect')


def _f8_errors(fid, fn, calculation):
    """F8: a design value left open beside a calculation states its margin."""
    errors = []
    found = [m.get('aspect') or calculation.get('aspect') for m in function_reading.margins(calculation)]
    if calculation.get('claim_ids'):
        for item in fn.get('open') or []:
            if not isinstance(item, dict) or item.get('kind') != 'DESIGN_VALUE' or text(item.get('no_margin_reason')):
                continue
            if not any(_covers(item, aspect) for aspect in found):
                errors.append('%s/%s: the function computed %s but gives no margin on the aspects this design value '
                              'leaves open; write calculation.margin for them (worst case against the limit, project '
                              'derating included), or say in no_margin_reason what the design has not chosen yet'
                              % (fid, item.get('key', '?'), '/'.join(calculation['claim_ids'])))
    return errors


def _worst_case_errors(label, item, conditions, calculation=None):
    """F3: the worst case under the public bound (which clause, what value, how it bounds) and its margin,
    or the curves and tables searched before calling the quantity unboundable."""
    worst = item.get('worst_case')
    if not isinstance(worst, dict):
        return [label + ': worst_case gives the result under the public bound, or why it cannot be bounded']
    if text(worst.get('not_boundable_reason')):
        if not evidence(worst.get('curves_checked')):
            return [label + ': worst_case.curves_checked lists the datasheet figures, published tables and application '
                            'notes searched for a bound (source, locator) before the quantity is called unboundable']
        found = _monotonic_errors(label, item, worst, calculation, conditions)   # 1c
        if found:
            return found
        specified = worst.get('operating_point_specified')
        if not isinstance(specified, bool):
            return [label + ': worst_case.operating_point_specified says whether the datasheet specifies the part at '
                            'this operating point at all (true: only the parameter is missing)']
        if not specified:
            return [label + ': the datasheet does not specify the part at this operating point; relying on it is a design '
                            'risk — record a fail item (outside_specified) whose finding moves the design into the '
                            'specified region, not a vendor request']
        named = worst.get('specified_by')
        if (conditions.get(named) or {}).get('kind') not in CLAUSE_KINDS + ('TYPICAL_REFERENCE',):
            return [label + ': worst_case.specified_by names the condition of this function where the datasheet describes '
                            'this usage (a limit, a clause or its application text); a usage it does not describe is '
                            'outside the specified region']
        points = worst['monotonic_tried'].get('test_points') or []
        if named in {p.get('condition') for p in points if isinstance(p, dict)}:
            return [label + ': worst_case.specified_by names %s, a test point that does not reach the operating point; '
                            'name where the datasheet describes this usage: a clause, its application text, or a curve '
                            'whose regime covers the point' % named]
        if conditions[named]['kind'] == 'TYPICAL_REFERENCE' and conditions[named].get('curve') is True:
            return _typical_estimate_errors(label, worst, conditions)   # application text needs no estimate (2.4)
        return []
    errors = []
    bound = worst.get('bound')
    if not (isinstance(bound, dict) and bound.get('condition') in conditions and text(bound.get('value'))
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


def _typical_estimate_errors(label, worst, conditions):
    """Decision 2-A: a typical curve covering the operating point describes the usage; the item gives the estimate read
    off it, and an estimate already short is a fail, since a typical part is a reachable case."""
    curve = conditions[worst['specified_by']]
    if not text(curve.get('regime')):
        return [label + ': the curve named in specified_by (%s) says in regime the range it covers, which includes the '
                        'operating point' % curve['id']]
    estimate = worst.get('typical_estimate')
    head = label + '/worst_case.typical_estimate'
    if not (isinstance(estimate, dict) and _finite(estimate.get('value')) and text(estimate.get('unit'))
            and text(estimate.get('against'))):
        return [head + ' {value, unit, against, basis} is the margin read off the curve in specified_by at the '
                       'operating point']
    errors = _basis_errors(head, estimate, conditions, ())
    basis = estimate.get('basis') if isinstance(estimate.get('basis'), dict) else {}
    if errors:
        return errors
    if basis.get('kind') != 'ESTIMATE' or curve['id'] not in (basis.get('conditions') or []):
        return [head + ': the basis is an ESTIMATE whose conditions include the curve %s' % curve['id']]
    if not (estimate['value'] >= 0 if basis.get('comparison') == 'GE' else estimate['value'] > 0):
        return [head + ': the typical estimate already falls short (%s %s against %s); a typical part is a reachable '
                       'case, so this is a fail item whose margin is that estimate as a REACHABLE_CASE (derivation '
                       'TYPICAL_CURVE), not a vendor request' % (estimate['value'], estimate['unit'], estimate['against'])]
    return []


def _unit(unit):
    """A unit as compared: squeezed, and a micro sign spelt u is µ."""
    unit = _squeeze(unit) if isinstance(unit, str) else ''
    return '\u00b5' + unit[1:] if len(unit) > 1 and unit[0] == 'u' else unit


def _span(value):
    if isinstance(value, dict) and _finite(value.get('min')) and _finite(value.get('max')) and value['min'] <= value['max']:
        return value['min'], value['max']
    return None


def _monotonic_errors(label, item, worst, calculation, conditions):
    """1c in numbers (bounding consistency proposals, item 1): the open side, the quantity, this board's range of the
    variable and the datasheet test points with their values. A range inside two test points is bounded from them; a
    range partly outside opens only the part outside (open_range) and the part inside is a margin. Each edge names
    the open side; the other side is a margin of this function or is not decisive, with why."""
    head = label + ': worst_case.monotonic_tried'
    tried = worst.get('monotonic_tried')
    if not isinstance(tried, dict):
        return [head + '{side, quantity, operating_point, test_points, why_not, other_side} says which bound the test '
                       'points leave open and why; a bound they do give is decided, only the other stays open']
    errors, at = [], []
    if tried.get('side') not in OPEN_SIDES:
        errors.append(head + '.side is UPPER or LOWER: the bound left open')
    if not text(tried.get('quantity')):
        errors.append(head + '.quantity names the quantity whose bound is open')
    point = tried.get('operating_point') if isinstance(tried.get('operating_point'), dict) else {}
    span = _span(point) if text(point.get('unit')) else None
    if span is None:
        errors.append(head + '.operating_point{min, max, unit} is this board\'s range of the variable the test points '
                             'are given at')
    points = tried.get('test_points')
    read = item.get('checked') if isinstance(item.get('checked'), list) else []
    # A datasheet with no numeric point of the quantity at all (R6 acceptance 2026-10-24, codex1 SR-03) records an
    # empty list and says where it looked; the whole operating range then stays open.
    no_points = isinstance(points, list) and not points and text(tried.get('no_test_points_reason'))
    if no_points and not located({'locator': tried['no_test_points_reason']}):
        errors.append(head + '.no_test_points_reason names the datasheet pages or tables searched for a numeric point of '
                             'the quantity; none found is the reason, "the datasheet gives none" alone is not')
    elif not (isinstance(points, list) and points) and not no_points:
        errors.append(head + '.test_points lists the datasheet test points of the quantity or of its slope: '
                             '{condition (in checked), at{value, unit}}; a datasheet with none gives [] and '
                             'no_test_points_reason (where it was looked for)')
    elif points:
        for p in points:
            where = p.get('at') if isinstance(p, dict) and isinstance(p.get('at'), dict) else {}
            if (isinstance(p, dict) and p.get('condition') in read and _finite(where.get('value'))
                    and span and _unit(where.get('unit')) == _unit(point.get('unit'))):
                at.append(where['value'])
            else:
                errors.append(head + '.test_points: %s is a condition in checked with at{value, unit} in the unit of '
                                     'operating_point' % (p.get('condition') if isinstance(p, dict) else p))
    if not text(tried.get('why_not')) or _squeeze(tried['why_not']) == _squeeze(worst.get('not_boundable_reason')):
        errors.append(head + '.why_not says why these test points do not give the open bound, not the '
                             'not_boundable_reason again')
    aspects = {a for a, _ in _decides(item)}
    calc = calculation if isinstance(calculation, dict) else {}
    margined = any((m.get('aspect') or calc.get('aspect')) in aspects for m in function_reading.margins(calc))
    other = tried.get('other_side')
    if other not in OTHER_SIDES:
        errors.append(head + '.other_side is DECIDED (a margin of this function settles the other bound) or NOT_DECISIVE '
                             '(with other_side_reason)')
    elif other == 'NOT_DECISIVE' and not text(tried.get('other_side_reason')):
        errors.append(head + '.other_side_reason says why the other bound decides nothing here')
    elif other == 'DECIDED' and not margined:
        errors.append(head + '.other_side is DECIDED but no margin of this function is on %s' % '/'.join(sorted(aspects)))
    if any(d.get('side') != tried.get('side') for d in edges(item)):
        errors.append(label + ': each decides edge names side, the bound left open (monotonic_tried.side)')
    cell = tried.get('cell')
    if cell != 'NONE' and cell not in catalog.BOUNDS:
        errors.append(head + '.cell names the cell of the bounding table (references/bounding-table.md) for this '
                             'parameter, or NONE when the table has none')
    if errors:
        return errors
    if cell != 'NONE':
        found = _cell_errors(head, catalog.BOUNDS[cell], tried, span, conditions)
        if found:
            return found
    if not at:
        return []   # no test point anywhere: nothing bounds the range, it is open as a whole
    low, high = min(at), max(at)
    if low <= span[0] and span[1] <= high:
        return [head + ': operating_point %g–%g %s lies within the test points %g–%g; bound it from them '
                       '(ADJACENT_TEST_POINT) instead of opening it' % (span[0], span[1], point['unit'], low, high)]
    if min(span[1], high) - max(span[0], low) > 0:
        opened = _span(tried.get('open_range'))
        if not (opened and span[0] <= opened[0] and opened[1] <= span[1] and (opened[1] <= low or opened[0] >= high)):
            return [head + '.open_range{min, max} is the part of operating_point outside the test points %g–%g; only '
                           'that part stays open' % (low, high)]
        if not margined:
            return [head + ': the part of operating_point inside the test points %g–%g is decided by a margin of this '
                           'function on %s' % (low, high, '/'.join(sorted(aspects)))]
    return []


def _cell_errors(head, bound, tried, span, conditions):
    """Decision A: the table cell, not the reviewer, says whether this parameter can be left unbounded."""
    if bound.side and bound.side != tried['side']:
        return ['%s: cell %s bounds the %s side, not %s' % (head, bound.id, bound.side, tried['side'])]
    if bound.fallback == 'BOUNDED':
        return ['%s: cell %s always bounds (%s); compute the bound, do not open it'
                % (head, bound.id, '/'.join(code for code, _ in bound.methods))]
    if bound.fallback == 'OUTSIDE_SPECIFIED':
        return ['%s: cell %s has no bound outside the specified region; this is a fail item (fails[] with '
                'outside_specified), not a vendor request' % (head, bound.id)]
    if bound.direction not in ('INCREASING', 'DECREASING'):
        return []
    upper = tried['side'] == 'UPPER'
    above = upper == (bound.direction == 'INCREASING')   # the favourable test point lies above the range
    for p in tried['test_points']:
        limit = (conditions.get(p['condition']) or {}).get('limit')
        value = p['at']['value']
        if (isinstance(limit, dict) and _finite(limit.get('max' if upper else 'min'))
                and (value >= span[1] if above else value <= span[0])):
            return ['%s: per cell %s the parameter is %s in %s, so the %s at %s (%g %s) bounds the %s side over '
                    '%g–%g (G2); decide it' % (head, bound.id, bound.direction, bound.varies_with,
                                              'maximum' if upper else 'minimum', p['condition'], value, p['at']['unit'],
                                              tried['side'], span[0], span[1])]
    return []


def _formula_errors(label, basis):
    """Decision A: a margin that names its table cell uses one of the cell's methods, and a formula it names is
    rerun on its inputs."""
    formulas = None
    if 'cell' in basis:
        bound = catalog.BOUNDS.get(basis['cell'])
        if bound is None:
            return ['%s: basis.cell names a cell of the bounding table (references/bounding-table.md)' % label]
        methods = dict(bound.methods)
        if basis.get('method') not in methods:
            return ['%s: basis.method is one of the methods of %s (%s)' % (label, bound.id, '/'.join(methods))]
        formulas = methods[basis['method']]
        if formulas and 'formula' not in basis:
            return ['%s: %s by %s is computed; write basis.formula{name: %s, inputs, value}'
                    % (label, bound.id, basis['method'], ' or '.join(formulas))]
    if 'formula' not in basis:
        return []
    formula = basis['formula']
    if not (isinstance(formula, dict) and formula.get('name') in bound_formulas.FORMULAS
            and isinstance(formula.get('inputs'), dict) and _finite(formula.get('value'))):
        return ['%s: basis.formula is {name: a bound_formulas function, inputs{...}, value}' % label]
    if formulas is not None and formula['name'] not in formulas:
        return ['%s: %s by %s uses %s, not %s' % (label, basis['cell'], basis['method'], ' or '.join(formulas),
                                                  formula['name'])]
    try:
        value = bound_formulas.FORMULAS[formula['name']](**formula['inputs'])
    except (TypeError, ValueError) as error:
        return ['%s: basis.formula %s does not run on its inputs: %s' % (label, formula['name'], error)]
    if abs(value - formula['value']) > FORMULA_TOLERANCE * max(abs(value), 1e-12):
        return ['%s: basis.formula %s gives %.4g on its inputs, not %s' % (label, formula['name'], value,
                                                                           formula['value'])]
    return []


def _datum_margin_errors(fid, fn, item, conditions, claim_ids, findings):
    """The margin under the public bound decides like a computed one (F4): proved, the bound already answers; a proven
    shortfall is a fail item on the aspect; a bound that proves neither is why the datum is asked."""
    worst = item.get('worst_case') if isinstance(item.get('worst_case'), dict) else {}
    margin = worst.get('margin') if isinstance(worst.get('margin'), dict) else {}
    if not _finite(margin.get('value')):
        return []
    label = '%s/%s' % (fid, item.get('key', '?'))
    errors = _basis_errors(label + '/worst_case.margin', margin, conditions, claim_ids)
    if errors:
        return errors
    verdict = margin_verdict(margin)
    if verdict == 'PASS':
        return ['%s: the worst case under the public bound (%s) shows %s %s against %s as a %s — the public bound already '
                'decides; conclude it with the bound in conditions' % (label, (worst.get('bound') or {}).get('value'),
                                                                       margin['value'], margin.get('unit'),
                                                                       margin.get('against'), margin['basis']['kind'])]
    if verdict == 'FAIL':
        aspects = {a for a, _ in _decides(item)}
        fails = [i for i in fn.get('fails') or [] if isinstance(i, dict) and any(_covers(i, a) for a in aspects)]
        if fails:
            return _shortfall_fix_errors(fid, fails, findings)
        return ['%s: the worst case under the public bound shows %s %s against %s as a %s — the shortfall is proven; '
                'record a fail item with its finding (保证要求未满足)'
                % (label, margin['value'], margin.get('unit'), margin.get('against'), margin['basis']['kind'])]
    return []


def _item_errors(label, item, kind_field, conditions, finding_ids, calculation=None, db=None):
    """One open or fail item: F2, F3, F7 and the shared shape (key, decides, severity)."""
    condition_ids = set(conditions)
    errors = ['%s: %s is retired; %s' % (label, field, why) for field, why in RETIRED_ITEM_FIELDS.items() if field in item]
    if not (text(item.get('key')) and KEY_RE.match(item['key'])):
        errors.append(label + ': item needs a key (letters, digits, - _ .)')
    if not text(item.get('what')):
        errors.append(label + ': item needs what (the one thing missing or wrong)')
    if not _decides(item):
        errors.append(label + ': decides lists the aspects (and states) this item leaves undecided — at least one edge '
                              'that blocks a proof')
    errors.extend(_edge_errors(label, item, conditions, calculation))   # F7
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
        elif item['deliverable_kind'] == 'CUSTOM_PART_DRAWING':
            errors.extend(_missing_parameter_errors(label, item, db))
    elif kind not in REQUEST_KINDS:
        stray = [f for f in ('spec', 'owner', 'acquisition', 'closure', 'checked', 'worst_case') if f in item]
        if stray:
            errors.append('%s: %s only belong to DESIGN_VALUE/VENDOR_DATUM' % (label, '/'.join(stray)))
    if kind in REQUEST_KINDS:
        for field in ('scope', 'closure'):
            if not text(item.get(field)):
                errors.append(label + ': ' + field + ' required (the conditions it must cover; what counts as closed)')
    if kind != 'DESIGN_VALUE' and ('undecided' in item or 'depends_on' in item):
        errors.append(label + ': undecided/depends_on only belong to DESIGN_VALUE')
    if kind == 'DESIGN_VALUE':   # F2
        errors.extend(_undecided_errors(label, item, db))
        for field in ('spec', 'owner'):
            if not text(item.get(field)):
                errors.append(label + ': a design value is back-calculated into spec and given an owner, not requested')
        asked = ' '.join(str(item.get(f) or '') for f in ('what', 'why', 'spec', 'owner', 'closure'))
        if VENDOR_ASK_RE.search(asked):
            errors.append(label + ': a design value is not asked of a vendor (%s); write the allowed range as spec'
                          % VENDOR_ASK_RE.search(asked).group(0))
    if kind == 'VENDOR_DATUM':   # F3
        checked = item.get('checked')
        if not (isinstance(checked, list) and checked and all(isinstance(c, str) and c in condition_ids for c in checked)):
            errors.append(label + ': checked lists the condition ids read before asking the vendor')
        if not text(item.get('why_insufficient')):
            errors.append(label + ': why_insufficient says why the clauses read do not answer the question')
        if not text(item.get('acquisition')):
            errors.append(label + ': acquisition says who provides the datum')
        errors.extend(_worst_case_errors(label, item, conditions, calculation))
    if kind == 'USER_DEFERRED' and not evidence(item.get('instruction')):
        errors.append(label + ': a deferral cites the user instruction (instruction evidence)')
    return errors


def cited_conditions(fn):
    """Condition ids the verdict actually uses: margin bases, the public bound and what was read before asking a vendor,
    judgements, fail items and gap edges. A clause nobody cites proves nothing (F1)."""
    out = set()
    calc = fn.get('calculation') if isinstance(fn.get('calculation'), dict) else {}
    bases = [m.get('basis') for m in function_reading.margins(calc)]
    for item in fn.get('open') or []:
        if not isinstance(item, dict):
            continue
        worst = item.get('worst_case') if isinstance(item.get('worst_case'), dict) else {}
        bases.append((worst.get('margin') or {}).get('basis') if isinstance(worst.get('margin'), dict) else None)
        out.add((worst.get('bound') or {}).get('condition') if isinstance(worst.get('bound'), dict) else None)
        out.update(c for c in (item['checked'] if isinstance(item.get('checked'), list) else []) if isinstance(c, str))
        out.update((d.get('via') or {}).get('condition') for d in item.get('decides') or []
                   if isinstance(d, dict) and isinstance(d.get('via'), dict))
    for basis in bases:
        if isinstance(basis, dict):
            out.update(c for c in basis.get('conditions') or [] if isinstance(c, str))
            out.update(basis.get(k) for k in ('limit', 'conversion') if isinstance(basis.get(k), str))
    for entry in list(fn.get('judgements') or []) + list(fn.get('fails') or []):
        if isinstance(entry, dict):
            out.update(c for c in entry.get('conditions') or [] if isinstance(c, str))
            if isinstance(entry.get('outside_specified'), dict):
                out.add(entry['outside_specified'].get('condition'))
    out.discard(None)
    return out


def function_errors(report, document_only=(), db=None):
    """F1–F10 and the shape of every function verdict; no plan needed. `document_only` names the functions that carry
    document rows only (validate_functions finds them); they need no clause. With `db`, netlist facts name real nets."""
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
        conditions_by_id = {}
        if not (isinstance(conditions, list) and conditions):   # F1
            errors.append(fid + ': conditions lists the datasheet/standard clauses that bear on the question (at least one)')
        else:
            for i, c in enumerate(conditions):
                if not isinstance(c, dict) or not all(text(c.get(f)) for f in CONDITION_FIELDS):
                    errors.append('%s/conditions[%d]: needs %s' % (fid, i, '/'.join(CONDITION_FIELDS)))
                    continue
                if c['id'] in conditions_by_id:
                    errors.append('%s/conditions: duplicate id %s' % (fid, c['id']))
                conditions_by_id[c['id']] = c
                errors.extend(_condition_errors('%s/conditions[%s]' % (fid, c['id']), c, db))
            cited = cited_conditions(fn)
            if conditions_by_id and fid not in document_only and not any(
                    clause(c) and c['id'] in cited for c in conditions_by_id.values()):
                errors.append('%s: no clause carries the verdict — cite at least one NUMERIC_LIMIT or MANDATORY_CLAUSE, '
                              'located (page, table or section, a datasheet section title, a requirement id), in a margin '
                              'basis, a judgement, a fail item or a gap edge; a listed clause nobody uses proves nothing'
                              % fid)
        calculation = fn.get('calculation')
        claim_ids = set()
        if calculation is None:
            if not text(fn.get('no_calculation_reason')):
                errors.append(fid + ': calculation {result[, margin, claim_ids, inputs, assumptions, aspect]} or no_calculation_reason')
        elif not isinstance(calculation, dict) or not text(calculation.get('result')):
            errors.append(fid + ': calculation needs result')
        else:
            claim_ids = {c for c in calculation.get('claim_ids') or [] if isinstance(c, str)}
            margin = calculation.get('margin')
            items = margin if isinstance(margin, list) else [margin]
            if margin is not None and not (items and all(
                    isinstance(m, dict) and _finite(m.get('value')) and text(m.get('unit'))
                    and text(m.get('against')) and ('aspect' not in m or text(m['aspect'])) for m in items)):
                errors.append(fid + ': calculation.margin is {value: finite number, unit, against, basis[, aspect, states]} '
                                    'or a list of them')
            elif margin is not None:
                stated = {}
                for k, m in enumerate(items):
                    errors.extend(_basis_errors('%s/margin[%d]' % (fid, k), m, conditions_by_id, claim_ids))
                    basis = m.get('basis') if isinstance(m.get('basis'), dict) else {}
                    if basis.get('kind') == 'ESTIMATE' and 'handoff' in basis and not estimate_handoff(fn, basis):
                        errors.append('%s/margin[%d]: basis.handoff is the index of a complete entry of the function\'s '
                                      'handoffs {receivers, constraint, verification}: the prototype test that confirms '
                                      'the estimate' % (fid, k))
                    same = (m['value'], m['unit'].strip(), m['against'].strip())
                    if same in stated:
                        errors.append('%s/margin[%d]: the same margin as margin[%d] (%s %s against %s); a defect lands on '
                                      'the aspect its margin proves — another aspect needs another quantity'
                                      % (fid, k, stated[same], m['value'], m['unit'], m['against']))
                    stated.setdefault(same, k)
                    for field in ('states', 'check_ids'):
                        if field in m and not (isinstance(m[field], list) and m[field] and all(text(x) for x in m[field])):
                            errors.append('%s/margin[%d]: %s is a non-empty list' % (fid, k, field))
            if 'inputs' in calculation and not (isinstance(calculation['inputs'], list)
                                                and all(text(x) for x in calculation['inputs'])):
                errors.append(fid + ': calculation.inputs lists the input names its claims take')
        errors.extend(_judgement_errors(fid, fn, conditions_by_id))
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
                errors.extend(_item_errors(label, item, field, conditions_by_id, finding_ids,
                                           calculation if isinstance(calculation, dict) else None, db))
                if field == 'open' and item.get('kind') == 'VENDOR_DATUM':
                    errors.extend(_datum_margin_errors(fid, fn, item, conditions_by_id, claim_ids, findings))
        errors.extend(_decision_errors(fid, fn, calculation if isinstance(calculation, dict) else {}, conditions_by_id,
                                       findings))   # F4
        if isinstance(calculation, dict):   # F8
            errors.extend(_f8_errors(fid, fn, calculation))
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
                          and all(b in conditions_by_id or b in claim_ids for b in basis))
                    if not ok:
                        errors.append('%s/verdict_history[%d]: a changed verdict cites condition or claim ids in basis'
                                      % (fid, i))
    errors.extend(_dependency_errors(functions))
    errors.extend(_shared_assumption_errors(functions))
    errors.extend(_shared_result_errors(functions))
    errors.extend(_template_errors(functions))
    return errors


def _template_errors(functions):
    """F10: one unlocated condition in several functions is a template; each function quotes what bears on its own
    question. (The same reason sentence on several items is only a hint: see template_hints.)"""
    notes = {}
    for fn in functions:
        if not isinstance(fn, dict) or not text(fn.get('id')):
            continue
        for c in fn.get('conditions') or []:
            if isinstance(c, dict) and text(c.get('says')) and not located(c) and c.get('kind') != 'NETLIST_FACT':
                notes.setdefault(c['says'].strip(), set()).add(fn['id'])
    return ['%s: the same unlocated condition in every one of these functions (%s); quote, with its place, what bears '
            'on each question' % (', '.join(sorted(ids)), sentence[:40]) for sentence, ids in notes.items() if len(ids) > 1]


DESIGNATOR_RE = re.compile(r'(?<![A-Za-z0-9])([A-Z]{1,3}\d+[A-Z]?)(?![A-Za-z0-9])')


def template_hints(functions, known_refs=None):
    """Quality hints, never errors: one reason sentence on several gaps (if it is one gap, keep one item and let its edges
    reach every row; rewording does not make two gaps), and a gap blocking more than WIDE_GAP aspects."""
    reasons, hints = {}, []
    for fn in functions or []:
        if not isinstance(fn, dict) or not text(fn.get('id')):
            continue
        for item in fn.get('open') or []:
            if not isinstance(item, dict):
                continue
            ref = '%s/%s' % (fn['id'], item.get('key', '?'))
            for field in TEMPLATE_FIELDS:
                if text(item.get(field)):
                    reasons.setdefault((field, item[field].strip()), []).append(ref)
            for d in edges(item):
                if text(d.get('rationale')):
                    reasons.setdefault(('rationale', d['rationale'].strip()), []).append(ref)
            aspects = {d['aspect'] for d in edges(item)}
            if len(aspects) > WIDE_GAP:
                hints.append({'code': 'WIDE_GAP', 'function_id': fn['id'], 'key': item.get('key'),
                              'aspects': sorted(aspects),
                              'message': 'One gap blocks %d aspects; read each edge: does the missing quantity really '
                                         'enter every one of them?' % len(aspects)})
    awaited = {}
    for fn in functions or []:
        if isinstance(fn, dict) and text(fn.get('id')):
            for item in fn.get('open') or []:
                if isinstance(item, dict) and item.get('kind') == 'DELIVERABLE_PENDING' and text(item.get('deliverable')):
                    for part in set(DESIGNATOR_RE.findall(item['deliverable'])) & (known_refs or set(DESIGNATOR_RE.findall(item['deliverable']))):
                        awaited.setdefault((item.get('deliverable_kind'), part), []).append(
                            '%s/%s' % (fn['id'], item.get('key', '?')))
    for (kind, part), refs in sorted(awaited.items()):
        if len(set(refs)) > 1:
            hints.append({'code': 'SAME_DELIVERABLE', 'refs': [part], 'deliverable_kind': kind, 'items': sorted(set(refs)),
                          'message': '%d gaps await %s of %s; if one document closes them, keep one item whose edges '
                                     'carry each consequence' % (len(set(refs)), kind, part)})
    for (field, sentence), refs in sorted(reasons.items()):
        if len(set(refs)) > 1:
            hints.append({'code': 'TEMPLATE_REASON', 'field': field, 'items': sorted(set(refs)),
                          'message': 'The same %s on several gaps (%s); if they are one gap keep one item, otherwise say '
                                     'why each is undecided' % (field, sentence[:40])})
    return hints


def _shared_result_errors(functions):
    """A calculation result is what that function computed; one text in two functions puts borrowed numbers beside
    a function that never computed them (the report's margin column reads it as that function's basis)."""
    owners = {}
    for fn in functions:
        calc = fn.get('calculation') if isinstance(fn, dict) and isinstance(fn.get('calculation'), dict) else {}
        if text(calc.get('result')):
            owners.setdefault(calc['result'].strip(), []).append(fn['id'])
    return ['%s: one calculation.result in several functions (%s); write what each function computed, or give '
            'no_calculation_reason where it computed nothing' % (', '.join(sorted(set(ids))), r[:40])
            for r, ids in owners.items() if len(set(ids)) > 1]


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
        if fid is not None and fid not in functions and result != 'NA':   # an all-NA frame needs no verdict
            errors.append(cid + ': function_id names no function verdict')
            continue
        if fid is not None and fid not in functions:
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
            if not decides_row(item, row['aspect'], state, cid):
                errors.append('%s: %s %s does not decide aspect %s%s; extend its decides or bind the row elsewhere'
                              % (cid, field, ref, row['aspect'], (' in state ' + state) if state else ''))
        if (result == 'PASS' and fid is not None and cid not in history_ids and text(row.get('aspect'))
                and judged(functions[fid], row['aspect'], state, cid) is None):
            errors.append(unjudged_message(cid, fid, row['aspect'], state))
        elif (result == 'PASS' and fid is not None and cid not in history_ids and text(row.get('aspect'))
              and (expected.get(cid) or {}).get('method') == 'C'
              and not margin_proves(functions[fid], row['aspect'], state, cid)
              and not reference_judged(functions[fid], row['aspect'], state, cid)
              and not life_estimate(functions[fid], row['aspect'], state, cid)
              and not prototype_estimate(functions[fid], row['aspect'], state, cid)):   # 1e
            errors.append('%s: aspect %s is an engineering calculation (method C); it passes on a margin of %s that '
                          'proves it, not on a sentence (a vendor reference circuit with reference_circuit also settles '
                          'it); a sentence closes connection tracing and clause checks' % (cid, row['aspect'], fid))
        if result == 'PASS' and fid is not None and cid not in history_ids and text(row.get('aspect')):
            fn = functions[fid]
            blocking = [i.get('key') for f in ('fails', 'open') for i in fn.get(f) or []
                        if isinstance(i, dict) and decides_row(i, row['aspect'], state, cid)]
            if blocking:
                errors.append('%s: PASS although %s/%s decides this row; a row follows its function'
                              % (cid, fid, blocking[0]))
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
    if 'inductive_load' in obj:   # the loop's other parts and nets are context: the row is about the inductor's node
        return {r for r in (obj.get('ref'),) if text(r)}, {n for n in (obj.get('net'),) if text(n)}
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


def _objects(fn):
    objects = fn.get('objects') if isinstance(fn.get('objects'), dict) else {}
    return ({r for r in objects.get('refs') or [] if text(r)},
            {net_name(n) for n in objects.get('nets') or [] if text(n)})


def scope_errors(plan, checks, by_id, members):
    """F11: a frame's function judges the frame's objects (the intent circuit; add a part there and regenerate the
    plan, do not widen the verdict), and a row the reviewer binds to a function is about an object of that
    function — a gap of one block does not reach into another through a binding. F12: a connector row whose plan
    lists clamp parts (clamp_refs) is judged in a function, where the clamp voltage meets the pin limit as clauses."""
    errors = []
    for frame in (plan or {}).get('functions') or []:
        fn = by_id.get(frame.get('id')) if isinstance(frame, dict) else None
        if fn is None:
            continue
        refs, nets = _objects(fn)
        frame_refs, frame_nets = _objects(frame)
        extra = sorted(refs - frame_refs) + sorted(nets - frame_nets)
        if extra and (frame_refs or frame_nets):
            errors.append('%s: objects name %s, which intent circuit %s does not list; declare them in intent.circuits and '
                          'regenerate the plan, or judge them in their own function'
                          % (fn['id'], ', '.join(extra), frame.get('circuit') or frame['id']))
    planned_rows = {c['id']: c for c in (plan or {}).get('checks') or [] if isinstance(c, dict) and text(c.get('id'))}
    for cid, row in checks.items():
        if not isinstance(row, dict) or row.get('review_result') not in REVIEWED:
            continue
        planned = planned_rows.get(cid) or {}
        clamps = planned.get('clamp_refs')
        if clamps and row.get('function_id') is None:
            errors.append('%s: the plan lists clamp parts %s on this connector; their clamp voltage against the protected '
                          'pin limit is a function judgement — bind the row to the port\'s function and quote both as '
                          'clauses' % (cid, ', '.join(clamps)))
        fn = by_id.get(row.get('function_id'))
        if fn is None or cid in members:
            continue
        refs, nets = row_anchors(planned)
        fn_refs, fn_nets = _objects(fn)
        if refs and not refs <= fn_refs:
            errors.append('%s: bound to %s, which is not about %s; a row names an object of its function — bind it to the '
                          'function that judges %s, or declare that part in that circuit'
                          % (cid, fn['id'], ', '.join(sorted(refs - fn_refs)), ', '.join(sorted(refs))))
        elif not refs and nets and not {net_name(n) for n in nets} <= fn_nets:
            errors.append('%s: bound to %s, which is not about net %s; a row names an object of its function'
                          % (cid, fn['id'], ', '.join(sorted(nets))))
    return errors


def _names_frame(question, frame):
    """A reviewer may sharpen a frame's question; the sharpened one still names the circuit, a part or a net of it."""
    refs, nets = _objects(frame)
    if not refs and not nets:
        return True   # a frame without objects gives nothing to name
    names = refs | nets | {n.rsplit('/', 1)[-1] for n in nets} | {frame.get('circuit') or ''}
    return any(name and name in question for name in names)


OWNING_FRAME = "write it in the owning frame, let other frames' rows use open_ref"


def own_function_errors(plan, checks, functions):
    """A planned circuit's gap is an item of a planned function: a member row of a frame takes its open_ref/fail_ref
    from a planned function, never from one the reviewer made to hold that gap (the report then listed every work item
    a second time as a function and the circuit read as passed). Rows outside every frame (device, checker, board
    rows) may still be judged in functions of the reviewer's own, but such a function takes only parts no circuit
    frame fully holds: over a circuit's own parts it only restates that circuit's question (decision 3, 2026-10-23)."""
    frames = [f for f in (plan or {}).get('functions') or [] if isinstance(f, dict) and text(f.get('id'))]
    ids = {f['id'] for f in frames}
    errors = []
    for frame in frames:
        for member in frame.get('members') or []:
            row = checks.get(member.get('check_id')) if isinstance(member, dict) else None
            if not isinstance(row, dict):
                continue
            for field in ('open_ref', 'fail_ref'):
                ref = row.get(field)
                owner = ref.split('/', 1)[0] if isinstance(ref, str) else None
                if owner and owner not in ids:
                    errors.append('%s: a member of frame %s takes its %s from %s, a function of your own; %s'
                                  % (member['check_id'], frame['id'], field, owner, OWNING_FRAME))
    circuits = [f for f in frames if text(f.get('circuit'))]
    for fn in functions or []:   # a function of your own takes only objects no circuit frame fully holds
        if not isinstance(fn, dict) or not text(fn.get('id')) or fn['id'] in ids:
            continue
        refs, _ = _objects(fn)
        holders = [f['id'] for f in circuits if refs and refs <= _objects(f)[0]]
        if holders:
            errors.append('%s: a function of your own over parts frame %s already holds; write it into frame %s (its '
                          'open or fail item; %s). A circuit the plan missed is declared as an add decision in '
                          'intent.circuit_decisions and the plan regenerated' % (fn['id'], holders[0], holders[0],
                                                                                 OWNING_FRAME))
    return errors


def frame_errors(plan, checks, functions):
    """Plan frames (one per intent circuit) are answered: a reviewed member row binds to its frame's
    function (or to another frame's function whose objects cover the row) and keeps the frame's aspect;
    a frame with a reviewed member of its own has a function verdict."""
    errors = []
    by_id = {fn['id']: fn for fn in functions or [] if isinstance(fn, dict) and text(fn.get('id'))}
    ids = set(by_id)
    planned_rows = {c['id']: c for c in (plan or {}).get('checks') or [] if isinstance(c, dict) and text(c.get('id'))}
    frame_ids = {f['id'] for f in (plan or {}).get('functions') or [] if isinstance(f, dict) and text(f.get('id'))}
    members = {m.get('check_id') for f in (plan or {}).get('functions') or [] if isinstance(f, dict)
               for m in f.get('members') or [] if isinstance(m, dict)}
    errors.extend(scope_errors(plan, checks, by_id, members))
    errors.extend(own_function_errors(plan, checks, functions))
    for frame in (plan or {}).get('functions') or []:
        if not isinstance(frame, dict) or not text(frame.get('id')):
            continue
        written = (by_id.get(frame['id']) or {}).get('question')
        if text(written) and text(frame.get('question')) and written != frame['question'] and not _names_frame(written, frame):
            errors.append('%s: a rewritten question names none of the circuit, its parts or its nets; sharpen the planned '
                          'question about this circuit, do not replace it with a scope note' % frame['id'])
        answered = False
        for member in frame.get('members') or []:
            row = checks.get(member.get('check_id')) if isinstance(member, dict) else None
            if not isinstance(row, dict) or row.get('review_result') not in REVIEWED:
                continue
            if row.get('function_id') != frame['id']:
                if row.get('function_id') in frame_ids and delegated(row, planned_rows.get(member['check_id']), by_id):
                    continue
                errors.append('%s: a member of frame %s binds to it (function_id), not to %s (only another plan frame '
                              'whose objects cover the row may take it, never a function of your own; a gap that spans '
                              'circuits: %s)' % (member['check_id'], frame['id'], row.get('function_id'), OWNING_FRAME))
                continue
            answered = True
            if 'aspect' in row and row['aspect'] != member.get('aspect'):
                errors.append('%s: aspect %r differs from the frame member aspect %r'
                              % (member['check_id'], row['aspect'], member.get('aspect')))
        if answered and frame['id'] not in ids:
            errors.append('functions: frame %s has reviewed member rows but no function verdict' % frame['id'])
    return errors


def requirement_edge_errors(plan, checks, functions):
    """1d (consistency proposals of 2026-10-23): an edge through a clause of the requirement document blocks only the
    rows bound to that requirement; any other row is blocked through the number the missing quantity enters."""
    documents, bound = requirement_rows(plan)
    if not documents:
        return []
    planned = {c['id']: c for c in (plan or {}).get('checks') or [] if isinstance(c, dict) and text(c.get('id'))}
    errors = []
    for fn in functions or []:
        if not isinstance(fn, dict) or not text(fn.get('id')):
            continue
        conditions = {c.get('id'): c for c in fn.get('conditions') or [] if isinstance(c, dict)}
        for field in ('open', 'fails'):
            for item in fn.get(field) or []:
                if not isinstance(item, dict):
                    continue
                ref = '%s/%s' % (fn['id'], item.get('key'))
                for edge in edges(item):
                    via = edge.get('via') if isinstance(edge.get('via'), dict) else {}
                    clause_ = conditions.get(via.get('condition'))
                    if not clause_ or not _requirement_document(clause_.get('source'), documents):
                        continue
                    said = '%s %s' % (clause_.get('locator') or '', clause_.get('says') or '')
                    named = [rid for rid in bound if rid in said] or list(bound)
                    allowed = set().union(*(bound[rid] for rid in named))
                    blocked = sorted(cid for cid, row in checks.items() if isinstance(row, dict)
                                     and ref in (row.get('open_ref'), row.get('fail_ref')) and cid not in allowed
                                     and covers(scope(edge), row.get('aspect'),
                                                ((planned.get(cid) or {}).get('object') or {}).get('state'), cid))
                    if blocked:
                        errors.append('%s: the edge on %s goes through requirement clause %s (%s), which blocks only the '
                                      'rows bound to that requirement, not %s; answer those rows, or write which number '
                                      'the missing quantity enters (a numeric limit, a calculation input, a datasheet or '
                                      'standard clause)' % (ref, edge['aspect'], clause_['id'], '、'.join(named),
                                                            '、'.join(blocked)))
    return errors


CONFIG_ROWS = ('CFG-D01', 'REQ-D01')


def life_errors(checks, functions):
    """Item 6a: a life row passing on an estimate states its BOM constraint as an estimate, and no life row is blocked
    by a vendor-data item."""
    errors, by_id = [], {fn.get('id'): fn for fn in functions or [] if isinstance(fn, dict)}
    for cid, row in sorted(checks.items()):
        fn = by_id.get(row.get('function_id')) if isinstance(row, dict) else None
        if not (fn and life_row(cid) and row.get('review_result') == 'PASS' and text(row.get('aspect'))):
            continue
        if margin_proves(fn, row['aspect'], None, cid) or not life_estimate(fn, row['aspect'], None, cid):
            continue
        constraint = row.get('bom_constraint')
        if not isinstance(constraint, dict):
            errors.append('%s: a life row passing on an estimate writes the endurance it needs as a bom_constraint '
                          '(“耐久 ≥ X h @T（估算，热点 ≤ Y °C）”)' % cid)
        elif '估算' not in str(constraint.get('requirement') or ''):
            errors.append('%s: the bom_constraint of a life estimate says it is one (估算) and the hot spot it assumes' % cid)
    for fn in by_id.values():
        for item in fn.get('open') or []:
            if not (isinstance(item, dict) and item.get('kind') == 'VENDOR_DATUM'):
                continue
            ref = '%s/%s' % (fn.get('id'), item.get('key'))
            rows = [cid for cid, row in checks.items() if isinstance(row, dict) and row.get('open_ref') == ref]
            if rows and all(life_row(cid) for cid in rows):
                errors.append('%s: a life row opens no VENDOR_DATUM; estimate on the mission profile with the vendor life '
                              'formula or the 10 °C doubling rule (ESTIMATE), write the result as a bom_constraint and hand '
                              'the hot spot to thermal design (%s)' % (ref, ', '.join(sorted(rows))))
    return errors


def estimate_pass_errors(expected, checks, functions):
    """2.1: a row passing on an estimate carries the prototype handoff its margin names."""
    errors, by_id = [], {fn.get('id'): fn for fn in functions or [] if isinstance(fn, dict)}
    for cid, row in sorted(checks.items()):
        fn = by_id.get(row.get('function_id')) if isinstance(row, dict) else None
        if not (fn and row.get('review_result') == 'PASS' and text(row.get('aspect'))):
            continue
        state = ((expected.get(cid) or {}).get('object') or {}).get('state')
        estimate = prototype_estimate(fn, row['aspect'], state, cid)
        if estimate and judged(fn, row['aspect'], state, cid) == estimate[0] \
                and not (isinstance(row.get('handoff'), dict) and row['handoff'].get('required')):
            errors.append('%s: a row passing on an estimate hands the prototype test on: handoff.required with the '
                          'function\'s handoff (%s)' % (cid, estimate[1]['verification']))
    return errors


def configuration_errors(expected, checks, functions):
    """Consistency proposals of 2026-10-23, item 3: a condition that holds only at one setting of a programmable device
    names it (setting{ref, group, value}) and the configuration row CFG-D01.<group>.<ref> lists it (3c); a missing
    configuration table blocks only the configuration rows and the requirement rows (3d)."""
    errors = []
    rows = {((c.get('object') or {}).get('ref'), (c.get('object') or {}).get('config_group')): cid
            for cid, c in expected.items() if c.get('rule') == 'CFG-D01'}
    for fn in functions or []:
        if not isinstance(fn, dict) or not text(fn.get('id')):
            continue
        for c in fn.get('conditions') or []:
            setting = c.get('setting') if isinstance(c, dict) else None
            if not (isinstance(setting, dict) and all(text(setting.get(k)) for k in ('ref', 'group', 'value'))):
                continue
            cid = rows.get((setting['ref'], setting['group']), 'CFG-D01.%s.%s' % (setting['group'], setting['ref']))
            if cid not in expected:
                errors.append('%s/%s: holds at a setting of %s group %s, which the plan has no row %s for; declare the '
                              'group in intent.devices.%s.configurable' % (fn['id'], c.get('id'), setting['ref'],
                                                                           setting['group'], cid, setting['ref']))
                continue
            listed = (checks.get(cid) or {}).get('settings')
            if not any(isinstance(x, dict) and x.get('value') == setting['value'] for x in listed or []):
                errors.append('%s/%s: holds at setting %r of %s; list it in %s settings[{value, function}] so the '
                              'configuration row checks it' % (fn['id'], c.get('id'), setting['value'], setting['ref'], cid))
        for item in fn.get('open') or []:
            if not (isinstance(item, dict) and item.get('deliverable_kind') == 'CONFIGURATION_TABLE'):
                continue
            ref = '%s/%s' % (fn['id'], item.get('key'))
            blocked = sorted(cid for cid, row in checks.items() if isinstance(row, dict) and row.get('open_ref') == ref
                             and (expected.get(cid) or {}).get('rule') not in CONFIG_ROWS)
            if blocked:
                errors.append('%s: a configuration table blocks only its configuration rows (CFG-D01) and the requirement '
                              'rows, not %s; judge those over the configuration range the datasheet allows, and mark a '
                              'condition that holds at one setting with setting{ref, group, value}' % (ref, '、'.join(blocked)))
    return errors


def validate_functions(plan, report, checks, history_ids=(), db=None):
    """All function-verdict errors for validate_review. `report` is the record as written."""
    expected = {c['id']: c for c in (plan or {}).get('checks') or [] if isinstance(c, dict) and isinstance(c.get('id'), str)}
    functions = report.get('functions') if isinstance(report.get('functions'), list) else []
    circuits = {fn.get('id') for fn in circuit_functions(functions, list(checks.values()))}
    document_only = {fn.get('id') for fn in functions if isinstance(fn, dict) and fn.get('id') not in circuits}
    errors = (function_errors(report, document_only, db) + binding_errors(expected, checks, report.get('functions'), history_ids)
              + frame_errors(plan, checks, report.get('functions'))
              + requirement_edge_errors(plan, checks, report.get('functions'))
              + configuration_errors(expected, checks, functions) + life_errors(checks, functions)
              + estimate_pass_errors(expected, checks, functions))
    if isinstance(db, dict):   # a commodity part's rating is a BOM constraint, not an open item
        import bom_constraints
        from checkers.netgraph import NetGraph
        errors += bom_constraints.rating_gap_errors(expected, checks, functions, NetGraph(db), row_anchors)
    return errors

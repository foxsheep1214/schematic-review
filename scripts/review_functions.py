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
import math
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
CONDITION_KINDS = ('NUMERIC_LIMIT', 'MANDATORY_CLAUSE', 'NETLIST_FACT', 'TYPICAL_REFERENCE', 'ENGINEERING_ASSUMPTION')
CLAUSE_KINDS = ('NUMERIC_LIMIT', 'MANDATORY_CLAUSE')       # what a vendor, a standard or a requirement says
WEAK_KINDS = ('TYPICAL_REFERENCE', 'ENGINEERING_ASSUMPTION')
BASIS_KINDS = ('GUARANTEED_BOUND', 'REACHABLE_CASE', 'EXACT_ENVELOPE', 'ESTIMATE')
COMPARISONS = ('GE', 'GT')       # GE: a zero margin passes; GT: it does not
EDGE_EFFECTS = ('BLOCKS_PROOF', 'INFORMATION_ONLY')
EDGE_KINDS = ('DESIGN_VALUE', 'VENDOR_DATUM', 'DELIVERABLE_PENDING')   # gaps in a quantity: each edge says what it enters
STATELESS = 'STATELESS'
WIDE_GAP = 3                     # more blocked aspects than this is reported for a second look, never refused
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
# A located condition names a place in its source a reader can open: a page, table, figure, section or chapter,
# a datasheet section title, a requirement or record id, a designator, or named nets/pins. "相关位号所有物理脚"
# and "## BIAS" locate nothing. Words are matched without case, ids with it.
LOCATOR_WORDS_RE = re.compile(
    r'(?<![a-z])pp?\.?\s*\d|第\s*\d+\s*[页节条章]'
    r'|\b(?:table|tab|fig(?:ure)?|section|sec|chapter|clause|note|eq(?:uation)?)\.?\s*[a-z]?\d'
    r'|[表图]\s*\d|§\s*\d'
    r'|电气特性|绝对最大|推荐工作|引脚说明|引脚定义|订货|功能框图|特性曲线|热阻|应用说明|典型应用|电气参数'
    r'|electrical characteristics|absolute maximum|recommended operating|pin description|pin assignment|ordering'
    r'|block diagram|typical (?:characteristics|application)|thermal'
    r'|(?:\bnets?\b|\bpins?\b|\bnodes?\b|网络|引脚|位号|节点)\s*[:：]?\s*/?[a-z][a-z0-9_/.-]+', re.I)
LOCATOR_IDS_RE = re.compile(r'\b[A-Z]{1,4}\d{1,4}\b|\b[A-Z]+(?:-[A-Z0-9]+)*-[A-Z]*\d[A-Z0-9]*\b')
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


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def quotes(condition, value):
    """The condition's own text says this number."""
    return any(abs(n - value) <= 1e-9 * max(1.0, abs(value)) or abs(abs(n) - abs(value)) <= 1e-9 * max(1.0, abs(value))
               for n in _numbers(condition.get('says')))


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


def scope(entry, default_aspect=None):
    """(aspect or None, states, check_ids or None) an entry speaks for. No states is STATELESS, never every state."""
    states = entry.get('states')
    states = frozenset(s for s in states if text(s)) if isinstance(states, list) and states else frozenset([STATELESS])
    ids = entry.get('check_ids')
    ids = frozenset(c for c in ids if text(c)) if isinstance(ids, list) and ids else None
    return (entry.get('aspect') or default_aspect, states, ids)


def overlaps(a, b):
    return ((a[0] is None or b[0] is None or a[0] == b[0]) and bool(a[1] & b[1])
            and (a[2] is None or b[2] is None or bool(a[2] & b[2])))


def covers(entry_scope, aspect, state, check_id=None):
    return overlaps(entry_scope, (aspect, frozenset([state if text(state) else STATELESS]),
                                  frozenset([check_id]) if check_id else None))


def edges(item, effect='BLOCKS_PROOF'):
    return [d for d in item.get('decides') or [] if isinstance(d, dict) and text(d.get('aspect'))
            and d.get('effect', 'BLOCKS_PROOF') == effect]


def _decides(item):
    """(aspect, states or None) per blocking edge, for the shape checks that only need the aspects."""
    return [(d['aspect'], set(d['states']) if isinstance(d.get('states'), list) and d['states'] else None)
            for d in edges(item)]


def decides_row(item, aspect, state, check_id=None):
    """Whether an open/fail item blocks (or fails) the row covering `aspect` in `state`."""
    return any(covers(scope(d), aspect, state, check_id) for d in edges(item))


def margin_verdict(m):
    """PASS, FAIL or OPEN: what a margin proves under its basis. A guaranteed lower bound proves acceptance, a reachable
    case proves rejection, the exact envelope proves both, an estimate proves neither."""
    basis = m.get('basis') if isinstance(m, dict) else None
    if not (isinstance(basis, dict) and _finite(m.get('value'))):
        return 'OPEN'
    met = m['value'] >= 0 if basis.get('comparison') == 'GE' else m['value'] > 0
    kind = basis.get('kind')
    if met and kind in ('GUARANTEED_BOUND', 'EXACT_ENVELOPE'):
        return 'PASS'
    if not met and kind in ('REACHABLE_CASE', 'EXACT_ENVELOPE'):
        return 'FAIL'
    return 'OPEN'


def judged(fn, aspect, state=None, check_id=None):
    """What settles `aspect` (in `state`) in favour of the design: a margin whose basis proves it, or a judgements entry
    citing the clauses. None when nothing does — a row never passes on another aspect's or another state's result."""
    calc = fn.get('calculation') if isinstance(fn.get('calculation'), dict) else {}
    for m in results_model.margins(calc):
        if margin_verdict(m) == 'PASS' and covers(scope(m, calc.get('aspect')), aspect, state, check_id):
            return '%s；余量 %s%s 对 %s' % (calc.get('result') or '', m['value'], m.get('unit') or '', m.get('against') or '')
    for j in fn.get('judgements') or []:
        if isinstance(j, dict) and text(j.get('says')) and j.get('aspect') == aspect and covers(scope(j), aspect, state, check_id):
            return '%s（依据 %s）' % (j['says'], '、'.join(c for c in j.get('conditions') or [] if isinstance(c, str)))
    return None


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
    elif kind == 'NETLIST_FACT':
        nets = [n for n in c.get('nets') or [] if text(n)] if isinstance(c.get('nets'), list) else []
        pins = [n for n in c.get('pins') or [] if text(n)] if isinstance(c.get('pins'), list) else []
        if not (nets or pins) or any(not PIN_RE.match(n) for n in pins):
            errors.append(label + ': a NETLIST_FACT names the nets and/or pins (REF.PIN) it is about')
        elif isinstance(db, dict):
            errors.extend(_netlist_name_errors(label, nets, pins, db))
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
    kind = basis['kind']
    if kind == 'ESTIMATE':
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


def unjudged_message(cid, fid, aspect, state):
    return ('%s: function %s judges no %s%s — give that aspect its margin in calculation.margin or a judgements '
            'entry {aspect, conditions, says}; a row does not pass on another aspect\'s result'
            % (cid, fid, aspect, (' in state ' + state) if state else ''))


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
        elif not kinds & {'MANDATORY_CLAUSE', 'NETLIST_FACT'}:   # F9
            errors.append('%s/judgements[%d] (%s): rests on no mandatory clause or netlist fact (%s); a typical value, an '
                          'application circuit or an assumption does not settle a row' % (
                              fid, i, j['aspect'], ', '.join(conditions)))
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
    margins = [(m, scope(m, default), margin_verdict(m)) for m in results_model.margins(calculation or {})
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
            if not any(overlaps(sc, other) for other in deciding):
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
        if not proven and not any(c.get('kind') == 'MANDATORY_CLAUSE' for c in cited):
            errors.append('%s/%s: a fail rests on a shortfall a margin proves (REACHABLE_CASE or EXACT_ENVELOPE) or on a '
                          'violated MANDATORY_CLAUSE in its conditions; a difference from a typical circuit alone is not '
                          'a defect' % (fid, item.get('key', '?')))
    return errors


def _evidence_name(entry):
    if 'value' in entry:
        return 'margin %s %s' % (entry['value'], entry.get('unit') or '')
    return 'judgement on %s' % entry.get('aspect')


def _f8_errors(fid, fn, calculation):
    """F8: a design value left open beside a calculation states its margin."""
    errors = []
    found = [m.get('aspect') or calculation.get('aspect') for m in results_model.margins(calculation)]
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


def _item_errors(label, item, kind_field, conditions, finding_ids, calculation=None):
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


def cited_conditions(fn):
    """Condition ids the verdict actually uses: margin bases, the public bound and what was read before asking a vendor,
    judgements, fail items and gap edges. A clause nobody cites proves nothing (F1)."""
    out = set()
    calc = fn.get('calculation') if isinstance(fn.get('calculation'), dict) else {}
    bases = [m.get('basis') for m in results_model.margins(calc)]
    for item in fn.get('open') or []:
        if not isinstance(item, dict):
            continue
        worst = item.get('worst_case') if isinstance(item.get('worst_case'), dict) else {}
        bases.append((worst.get('margin') or {}).get('basis') if isinstance(worst.get('margin'), dict) else None)
        out.add((worst.get('bound') or {}).get('condition') if isinstance(worst.get('bound'), dict) else None)
        out.update(c for c in item.get('checked') or [] if isinstance(c, str))
        out.update((d.get('via') or {}).get('condition') for d in item.get('decides') or []
                   if isinstance(d, dict) and isinstance(d.get('via'), dict))
    for basis in bases:
        if isinstance(basis, dict):
            out.update(c for c in basis.get('conditions') or [] if isinstance(c, str))
            out.update(basis.get(k) for k in ('limit', 'conversion') if isinstance(basis.get(k), str))
    for entry in list(fn.get('judgements') or []) + list(fn.get('fails') or []):
        if isinstance(entry, dict):
            out.update(c for c in entry.get('conditions') or [] if isinstance(c, str))
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
                for k, m in enumerate(items):
                    errors.extend(_basis_errors('%s/margin[%d]' % (fid, k), m, conditions_by_id, claim_ids))
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
                                           calculation if isinstance(calculation, dict) else None))
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
    errors.extend(_shared_assumption_errors(functions))
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


def template_hints(functions):
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
    for (field, sentence), refs in sorted(reasons.items()):
        if len(set(refs)) > 1:
            hints.append({'code': 'TEMPLATE_REASON', 'field': field, 'items': sorted(set(refs)),
                          'message': 'The same %s on several gaps (%s); if they are one gap keep one item, otherwise say '
                                     'why each is undecided' % (field, sentence[:40])})
    return hints


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
            if not decides_row(item, row['aspect'], state, cid):
                errors.append('%s: %s %s does not decide aspect %s%s; extend its decides or bind the row elsewhere'
                              % (cid, field, ref, row['aspect'], (' in state ' + state) if state else ''))
        if (result == 'PASS' and fid is not None and cid not in history_ids and text(row.get('aspect'))
                and judged(functions[fid], row['aspect'], state, cid) is None):
            errors.append(unjudged_message(cid, fid, row['aspect'], state))
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


def frame_errors(plan, checks, functions):
    """Plan frames (one per intent circuit) are answered: a reviewed member row binds to its frame's
    function (or to another frame's function whose objects cover the row) and keeps the frame's aspect;
    a frame with a reviewed member of its own has a function verdict."""
    errors = []
    by_id = {fn['id']: fn for fn in functions or [] if isinstance(fn, dict) and text(fn.get('id'))}
    ids = set(by_id)
    planned_rows = {c['id']: c for c in (plan or {}).get('checks') or [] if isinstance(c, dict) and text(c.get('id'))}
    members = {m.get('check_id') for f in (plan or {}).get('functions') or [] if isinstance(f, dict)
               for m in f.get('members') or [] if isinstance(m, dict)}
    errors.extend(scope_errors(plan, checks, by_id, members))
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


def validate_functions(plan, report, checks, history_ids=(), db=None):
    """All function-verdict errors for validate_review. `report` is the record as written."""
    expected = {c['id']: c for c in (plan or {}).get('checks') or [] if isinstance(c, dict) and isinstance(c.get('id'), str)}
    functions = report.get('functions') if isinstance(report.get('functions'), list) else []
    circuits = {fn.get('id') for fn in circuit_functions(functions, list(checks.values()))}
    document_only = {fn.get('id') for fn in functions if isinstance(fn, dict) and fn.get('id') not in circuits}
    return (function_errors(report, document_only, db) + binding_errors(expected, checks, report.get('functions'), history_ids)
            + frame_errors(plan, checks, report.get('functions')))

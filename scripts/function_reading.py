"""What a function verdict says (SR self-check 5.8, user: 单列新库): which rows an item decides, which margin or
judgement settles an aspect, when an estimate passes. The row derivation (③ derive_rows.py) and the gate
(④ review_functions.py) both read a verdict this way; the gate's own checks stay in review_functions.py.
"""
import re

import catalog
import requirement_bindings
from electrical_contract import LOCATOR_WORDS_RE, finite, text


STATELESS = 'STATELESS'
# Life rows (consistency proposals of 2026-10-23, item 6): an endurance or wear-out life rests on an estimate on the
# mission profile, written as a BOM constraint; no vendor-data item is opened for it.
LIFE_ROW_RE = re.compile(r'^(DEV-C02\.LIFE|DEV-C06)\.')
# An estimate passes a required function or a performance when a prototype test is handed on (SR self-check 2.1, user:
# 估算 + 样机移交可判通过). Which estimate may pass which consequence class is decided by the bounding-table cell the
# margin names (2026-10-26, user: 判决的边界按器件类型来 — `catalog.estimate_rule`); the two constants below are the default
# for a margin whose cell is NONE: damage, overheating and protection rules (stress and rating, connector current,
# converter current stress, protection thresholds, clamps, all of PRO) take no estimate outside the table.
ESTIMATE_PASS_CLASSES = ('REQUIRED_FUNCTION', 'PERFORMANCE_OR_LIFE')
NO_ESTIMATE_PASS_RE = re.compile(r'^(?:(?:DEV-C01|DEV-C04|PWR-C03|PWR-C06|PWR-C10|DRV-C01)\.|PRO-)')
REFERENCE_FIELDS = ('figure', 'connection', 'load')


def margins(calculation):
    """calculation.margin as a list: one {value, unit, against[, aspect]} or one per aspect."""
    margin = calculation.get('margin') if isinstance(calculation, dict) else None
    items = margin if isinstance(margin, list) else [margin] if margin is not None else []
    return [m for m in items if isinstance(m, dict) and m.get('value') is not None]


def reference_circuit(condition):
    """A vendor reference circuit stated against this board: the figure, the same connection and a load no heavier
    (proposals of 2026-10-23, 5c tier 2). Only this kind of typical reference settles a judgement."""
    rc = condition.get('reference_circuit') if isinstance(condition, dict) else None
    return (condition.get('kind') == 'TYPICAL_REFERENCE' and isinstance(rc, dict)
            and all(text(rc.get(f)) for f in REFERENCE_FIELDS) and bool(LOCATOR_WORDS_RE.search(rc['figure'])))


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


def decides_row(item, aspect, state, check_id=None):
    """Whether an open/fail item blocks (or fails) the row covering `aspect` in `state`."""
    return any(covers(scope(d), aspect, state, check_id) for d in edges(item))


def margin_verdict(m):
    """PASS, FAIL or OPEN: what a margin proves under its basis. A guaranteed lower bound proves acceptance, a reachable
    case proves rejection, the exact envelope proves both, an estimate proves neither."""
    basis = m.get('basis') if isinstance(m, dict) else None
    if not (isinstance(basis, dict) and finite(m.get('value'))):
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
    for m in margins(calc):
        if margin_verdict(m) == 'PASS' and covers(scope(m, calc.get('aspect')), aspect, state, check_id):
            return '%s；余量 %s%s 对 %s' % (calc.get('result') or '', m['value'], m.get('unit') or '', m.get('against') or '')
    for j in fn.get('judgements') or []:
        if isinstance(j, dict) and text(j.get('says')) and j.get('aspect') == aspect and covers(scope(j), aspect, state, check_id):
            by_id = {c.get('id'): c for c in fn.get('conditions') or [] if isinstance(c, dict)}
            names = ['厂家参考电路 ' + by_id[c]['reference_circuit']['figure'] if reference_circuit(by_id.get(c)) else c
                     for c in j.get('conditions') or [] if isinstance(c, str)]
            return '%s（依据 %s）' % (j['says'], '、'.join(names))
    life = life_estimate(fn, aspect, state, check_id)
    if life is not None:
        return life
    estimate = prototype_estimate(fn, aspect, state, check_id)
    return estimate[0] if estimate else None


def life_row(check_id):
    return isinstance(check_id, str) and bool(LIFE_ROW_RE.match(check_id))


def life_estimate(fn, aspect, state=None, check_id=None):
    """On a life row, an ESTIMATE margin that meets its target: the row passes as a BOM constraint (item 6a)."""
    if not life_row(check_id):
        return None
    calc = fn.get('calculation') if isinstance(fn.get('calculation'), dict) else {}
    for m in margins(calc):
        basis = m.get('basis') if isinstance(m.get('basis'), dict) else {}
        met = finite(m.get('value')) and (m['value'] >= 0 if basis.get('comparison') == 'GE' else m['value'] > 0)
        if basis.get('kind') == 'ESTIMATE' and met and covers(scope(m, calc.get('aspect')), aspect, state, check_id):
            return '%s；估算余量 %s%s 对 %s' % (calc.get('result') or '', m['value'], m.get('unit') or '',
                                          m.get('against') or '')
    return None


def estimate_handoff(fn, basis):
    """The function handoff an ESTIMATE basis names in `handoff` (an index into fn.handoffs), when it is complete."""
    k, handoffs = basis.get('handoff'), fn.get('handoffs')
    if not (type(k) is int and isinstance(handoffs, list) and 0 <= k < len(handoffs)):
        return None
    h = handoffs[k]
    if not (isinstance(h, dict) and isinstance(h.get('receivers'), list) and h['receivers']
            and text(h.get('constraint')) and text(h.get('verification'))):
        return None
    return h


def estimate_in_table(basis):
    """The margin names a cell of the bounding table (not NONE, not absent): the cell decides its estimate."""
    return isinstance(basis, dict) and basis.get('cell') in catalog.BOUNDS


def estimate_passes(fn, m, check_id=None):
    """An ESTIMATE margin written to pass on a prototype handoff (2.1). With a table cell the cell's boundary decides
    (`catalog.estimate_rule`: the consequence class it applies to, whatever the row's rule); with cell NONE the default
    holds: a required function or a performance, not on a damage, overheating or protection rule."""
    basis = m.get('basis') if isinstance(m.get('basis'), dict) else {}
    if basis.get('kind') != 'ESTIMATE' or estimate_handoff(fn, basis) is None:
        return False
    cls = basis.get('consequence_class')
    if estimate_in_table(basis):
        return catalog.estimate_rule(basis['cell'], cls) is not None
    return cls in ESTIMATE_PASS_CLASSES and not (isinstance(check_id, str) and NO_ESTIMATE_PASS_RE.match(check_id))


def prototype_estimate(fn, aspect, state=None, check_id=None):
    """An ESTIMATE margin that meets its target and is handed to the prototype test it names (2.1): (rationale, handoff)
    or None. Its cell's boundary says which consequence class it may pass; with cell NONE, not a rule about damage,
    overheating or protection."""
    calc = fn.get('calculation') if isinstance(fn.get('calculation'), dict) else {}
    for m in margins(calc):
        basis = m.get('basis') if isinstance(m.get('basis'), dict) else {}
        met = finite(m.get('value')) and (m['value'] >= 0 if basis.get('comparison') == 'GE' else m['value'] > 0)
        if met and estimate_passes(fn, m, check_id) and covers(scope(m, calc.get('aspect')), aspect, state, check_id):
            handoff = estimate_handoff(fn, basis)
            return ('%s；估算余量 %s%s 对 %s，样机实测移交：%s' % (calc.get('result') or '', m['value'], m.get('unit') or '',
                                                     m.get('against') or '', handoff['verification']), handoff, m)
    return None


def design_constraint(fn, aspect, state=None, check_id=None):
    """乙 (2026-10-26, user: 乙判合格并附设计约束): the handoff of the DESIGN_CONSTRAINT a proving margin of this aspect
    takes as input or limit — the row passes on it and hands it to the design file that owns the value. None otherwise."""
    calc = fn.get('calculation') if isinstance(fn.get('calculation'), dict) else {}
    by_id = {c.get('id'): c for c in fn.get('conditions') or [] if isinstance(c, dict)}
    for m in margins(calc):
        basis = m.get('basis') if isinstance(m.get('basis'), dict) else {}
        if margin_verdict(m) != 'PASS' or not covers(scope(m, calc.get('aspect')), aspect, state, check_id):
            continue
        for cid in list(basis.get('conditions') or []) + [basis.get('limit')]:
            c = by_id.get(cid) if isinstance(cid, str) else None
            if c and c.get('kind') == 'DESIGN_CONSTRAINT' and estimate_handoff(fn, c):
                return estimate_handoff(fn, c), c
    return None


def unjudged_message(cid, fid, aspect, state):
    return ('%s: function %s judges no %s%s — give that aspect its margin in calculation.margin or a judgements '
            'entry {aspect, conditions, says}; a row does not pass on another aspect\'s result'
            % (cid, fid, aspect, (' in state ' + state) if state else ''))


def margin_proves(fn, aspect, state=None, check_id=None):
    """A margin of the function whose basis proves `aspect` in `state`."""
    calc = fn.get('calculation') if isinstance(fn.get('calculation'), dict) else {}
    return any(margin_verdict(m) == 'PASS' and covers(scope(m, calc.get('aspect')), aspect, state, check_id)
               for m in margins(calc))


def reference_judged(fn, aspect, state=None, check_id=None):
    """A judgement of `aspect` resting on a vendor reference circuit stated against this board (5c, tier 2)."""
    by_id = {c.get('id'): c for c in fn.get('conditions') or [] if isinstance(c, dict)}
    return any(isinstance(j, dict) and j.get('aspect') == aspect and covers(scope(j), aspect, state, check_id)
               and any(reference_circuit(by_id.get(c)) for c in j.get('conditions') or [])
               for j in fn.get('judgements') or [])


def requirement_rows(plan):
    """(requirement document paths, {requirement id: the rows bound to it}) from the plan's REQ-D01 rows."""
    documents, rows = set(), {}
    for c in (plan or {}).get('checks') or []:
        if not (isinstance(c, dict) and c.get('rule') == 'REQ-D01'):
            continue
        locator = ((c.get('source_text') or {}).get('locator') or '') if isinstance(c.get('source_text'), dict) else ''
        if locator:
            documents.add(re.sub(r':\d+$', '', locator).replace('\\', '/'))
        rid = (c.get('object') or {}).get('requirement_id')
        if text(rid):
            rows.setdefault(rid, set()).update([c['id']] + list(c.get('bound_checks') or []))
    return documents, rows


def requirement_document(source, documents):
    """A file of the requirement folder: the requirement source itself or another document beside it (an engineering
    specification), written with its full path or a path relative to that folder's parent."""
    source = str(source or '').replace('\\', '/')
    folder, _, name = source.rpartition('/')
    for document in documents:
        home, _, own = document.rpartition('/')
        if name == own or (folder and home and (home == folder or home.endswith('/' + folder))):
            return True
    return False


def fail_counts(planned, row, functions, documents):
    """Whether a bound row's FAIL reaches the requirement row: a requirement aspect with parameters takes a failure
    only through a condition that is a clause of the requirement documents or a limit in the unit of one of its
    parameters; a failure on another quantity of the same part stays on the tree row (R6 acceptance 2026-10-24,
    claude2: a zener's low-current VZ failed TEMPERATURE_GRADE). PASS, INSUFFICIENT, a fail with no function item
    behind it and an item naming no condition always count."""
    if row.get('review_result') != 'FAIL' or not functions:
        return True
    units = requirement_bindings.units_of((planned.get('object') or {}).get('aspect'))
    if not units:
        return True
    fid, _, key = str(row.get('fail_ref') or '').partition('/')
    fn = functions.get(fid)
    item = next((i for i in (fn or {}).get('fails') or [] if isinstance(i, dict) and i.get('key') == key), None)
    if item is None:
        return True
    conditions = {c.get('id'): c for c in fn.get('conditions') or [] if isinstance(c, dict)}
    named = [(e.get('via') or {}).get('condition') for e in edges(item) if isinstance(e.get('via'), dict)]
    named += [c for c in item.get('conditions') or [] if isinstance(c, str)]
    if not named:
        return True
    for condition in (conditions.get(n) for n in named):
        if not condition:
            continue
        if requirement_document(condition.get('source'), documents or set()):
            return True
        unit = (condition.get('limit') or {}).get('unit') if isinstance(condition.get('limit'), dict) else None
        if isinstance(unit, str) and unit.replace('µ', 'u') in units:
            return True
    return False


def fail_filter(plan, results):
    """The `counts` predicate for requirement_bindings.derive / derived_result, read off a record."""
    functions = {fn.get('id'): fn for fn in (results or {}).get('functions') or [] if isinstance(fn, dict)}
    documents, _ = requirement_rows(plan)
    return lambda planned, row: fail_counts(planned, row, functions, documents)

"""BOM constraints: the minimum rating or the specification a commodity part must be bought to (commodity-floors.md).

A resistor, capacitor, inductor or diode is specified by its value and tolerance, not by a brand. Its stress is
bounded on the weakest commodity tier; beyond that tier, or where a requirement (life, precision, wide temperature)
falls on the part, the review writes what the BOM must state as a constraint on a PASS row, graded by what the
credible wrong pick (the weakest part matching every field the BOM already writes) would do. Such a rating is not an
open item: a gap whose rows are all part-stress rows of commodity parts is refused, and written as a constraint.
"""
import re

import part_words as pw
from electrical_contract import HAZARD_PATHS, IMPACT_CLASSES

COMMODITY_KINDS = {pw.RESISTOR, pw.CAPACITOR, pw.INDUCTOR, pw.FERRITE, pw.DIODE, pw.ZENER}
SAFETY_RE = re.compile(r'(^|[/\s])(X1|X2|Y1|Y2)([/\s]|$)', re.I)
CUSTOM_RE = re.compile(r'CUSTOM', re.I)
STATUSES = ('TO_WRITE', 'WRITTEN')
PART_STRESS_RULES = ('DEV-C01', 'DEV-C02')
BOM_RULES = ('DEV-D04',)    # the board-wide BOM row: its gap is about the parts its text names
FOLLOWING_RULES = ('REQ-D01',)
REF_RE = re.compile(r'(?<![A-Za-z0-9])([A-Z]{1,3}\d+[A-Z]?)(?![A-Za-z0-9])')
RATING_RE = re.compile(r'(≥|>=)\s*\d')


def text(value):
    return isinstance(value, str) and bool(value.strip())


def is_commodity(graph, ref):
    """A value-and-tolerance part: not a safety capacitor, not a custom part, not a protection or active part."""
    part = graph.parts.get(ref) or {}
    identity = ' '.join(str(part.get(k) or '') for k in ('value', 'part', 'prim'))
    return (graph.kind(ref) in COMMODITY_KINDS and not SAFETY_RE.search(str(part.get('value') or ''))
            and not CUSTOM_RE.search(identity) and not re.match(r'C[XY]\d', ref, re.I))


def constraint_errors(key, row):
    """Shape of one row's bom_constraint: what the BOM must state, from which calculation or requirement, and the
    level the credible wrong pick earns by its consequence class."""
    constraint = row.get('bom_constraint')
    if constraint is None:
        return []
    if not isinstance(constraint, dict):
        return [key + ': bom_constraint is {refs, requirement, basis, consequence_class, level, status}']
    errors = []
    if row.get('review_result') != 'PASS':
        errors.append(key + ': a bom_constraint stands on a PASS row (the part is judged; the BOM must state the rating)')
    if not (isinstance(constraint.get('refs'), list) and constraint['refs'] and all(text(r) for r in constraint['refs'])):
        errors.append(key + ': bom_constraint.refs names the parts')
    if not (text(constraint.get('requirement')) and RATING_RE.search(constraint['requirement'])):
        errors.append(key + ': bom_constraint.requirement states the minimum (“额定功率 ≥ 0.09 W”, “耐久 ≥ 10000 h @105 ℃”)')
    if not text(constraint.get('basis')):
        errors.append(key + ': bom_constraint.basis names the calculation or requirement the minimum comes from')
    cls = constraint.get('consequence_class')
    if cls not in IMPACT_CLASSES:
        errors.append(key + ': bom_constraint.consequence_class is one of ' + '/'.join(IMPACT_CLASSES))
    elif constraint.get('level') != IMPACT_CLASSES[cls]:
        errors.append('%s: bom_constraint.level for %s is %s (what the wrong pick would do decides the level)'
                      % (key, cls, IMPACT_CLASSES[cls]))
    elif IMPACT_CLASSES[cls] == 'P0' and constraint.get('hazard_path') not in HAZARD_PATHS:
        errors.append(key + ': a P0 bom_constraint names its hazard_path')
    if constraint.get('status') not in STATUSES:
        errors.append(key + ': bom_constraint.status is TO_WRITE or WRITTEN')
    elif constraint['status'] == 'WRITTEN' and not text(constraint.get('written_at')):
        errors.append(key + ': a WRITTEN bom_constraint locates the BOM line that states it (written_at)')
    return errors


def constraints(checks):
    """[(check id, constraint)] of every row's bom_constraint, in check order."""
    return [(cid, row['bom_constraint']) for cid, row in sorted(checks.items())
            if isinstance(row, dict) and isinstance(row.get('bom_constraint'), dict)]


def freeze_blockers(checks):
    pending = [cid for cid, c in constraints(checks) if c.get('status') != 'WRITTEN']
    if not pending:
        return []
    return ['BOM_CONSTRAINT_TO_WRITE: %d BOM constraints are not yet in the BOM (%s)' % (len(pending), ', '.join(pending))]


def named_parts(item, graph):
    """Designators of this board that an open item's text names."""
    words = ' '.join(str(item.get(k) or '') for k in ('what', 'spec', 'scope'))
    return {r for r in REF_RE.findall(words) if r in graph.parts}


def rating_gap_errors(expected, checks, functions, graph, anchors):
    """A DESIGN_VALUE or VENDOR_DATUM whose rows are all part-stress rows of commodity parts, or the BOM row with a text
    naming only commodity parts, is a BOM constraint."""
    errors = []
    for fn in functions or []:
        if not isinstance(fn, dict):
            continue
        for item in fn.get('open') or []:
            if not isinstance(item, dict) or item.get('kind') not in ('DESIGN_VALUE', 'VENDOR_DATUM'):
                continue
            ref = '%s/%s' % (fn.get('id'), item.get('key'))
            rows = [cid for cid, row in checks.items() if isinstance(row, dict) and row.get('open_ref') == ref]
            if not rows:
                continue
            parts = set()
            for cid in rows:
                row = checks[cid]
                planned = expected.get(cid) or {'object': (row.get('binding') or {}).get('object')}
                rule = (expected.get(cid) or {}).get('rule') or cid.split('.', 1)[0]
                if rule in FOLLOWING_RULES:
                    continue   # a requirement aspect row follows the part rows the gap is about
                refs, _ = anchors(planned)
                if rule in BOM_RULES and not refs:
                    refs = named_parts(item, graph)
                elif rule not in PART_STRESS_RULES:
                    break
                if not refs:
                    break
                parts |= refs
            else:
                if parts and all(p in graph.parts and is_commodity(graph, p) for p in parts):
                    errors.append('%s: %s is a rating of commodity parts (%s); write it as a bom_constraint on the PASS '
                                  'row, not an open item (commodity-floors.md)' % (ref, item.get('kind'), ', '.join(sorted(parts))))
    return errors

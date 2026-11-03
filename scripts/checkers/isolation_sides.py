"""Reference sides of isolating parts, independently of their single catalog role.

Groups describe voltage references, never shorts or insulation certification. Unmapped pins remain unknown.
Exact model pin rules cite manufacturer tables; otherwise use the reviewer-cited physical pin table, pin
names or winding declaration. A common external reference does not remove the isolation object.
"""
import re
import part_words as pw

# pattern, mechanism, side pin groups, manufacturer pin-table locator
MODEL_RULES = (
    (r'AMC3311[A-Z0-9/-]*', 'isolated_amplifier', (tuple(map(str, range(1, 9))), tuple(map(str, range(9, 17)))),
     'TI AMC3311 SBASAQ5A p3 Table 5-1 (HGND 2/7/8; GND 9/15)'),
    (r'REC15E-[A-Z0-9/-]+', 'isolated_dcdc', (('1', '2', '3'), ('4', '5', '6')),
     'RECOM REC15E-Z Rev3/2026 p7 Pinning information (single output)'),
    (r'DP5305', 'isolated_dcdc', (('1', '2', '3'), ('5', '6', '7', '8')),
     'SDAPO DP5300/5400/5500 2025 p3 section 1.2 Pin Description'),
    (r'HY931147C', 'ethernet_magnetics', (('P$1', 'P$2', 'P$3', 'P$4', 'P$5', 'P$6'), ('P$9', 'P$10')),
     'HanRun HY931147C REV.A/1 p1 schematic: PHY windings and cable-side rectified PoE (V+/V-); shield/LED pins unmapped'),
)


# Isolated DC/DC modules of the common families (MORNSUN B_S/B_XT/URB, CUI PEM/PDQE, muRata ULT, RECOM R/REC, Traco
# TMA/TME, XP IA/IE): sides read from the module's own pin names, input VIN/GND/CTRL against output VOUT/0V/TRIM.
# Each side keeps its own return; the two grounds are never merged (boards-merge4, PEM1-S/PDQE30/ULT-12/B0505S).
ISOLATED_MODULE_RE = re.compile(r'(?:MORNSUN[-_ ]?)?(?:B\d{4}[A-Z]{1,3}|IB\d{4}[A-Z]*|UR[AB]\d{4}[A-Z]*|PEM\d|PDQE\d+|ULT-|'
                                r'REC\d|R\d?[A-Z]{1,3}-\d{4}|TM[AE]\s?\d{4}|I[AE]\d{4})', re.I)
MODULE_INPUT_RE = re.compile(r'^(?:[+-]?VIN[+-]?|V_?IN|-?VI|CTRL|ON/?OFF|REM(?:OTE)?|RC)$', re.I)
MODULE_OUTPUT_RE = re.compile(r'^(?:[+-]?VO(?:UT)?[+-]?|0V|COM|TRIM|SENSE[+-]?|[+-]SENSE)$', re.I)
MODULE_POSITIVE_OUT_RE = re.compile(r'^(?:\+VO(?:UT)?|VO(?:UT)?\+?)$', re.I)
MODULE_NEGATIVE_OUT_RE = re.compile(r'^(?:-VO(?:UT)?|VO(?:UT)?-)$', re.I)


def _module_sides(names, actual):
    """(input pins, output pins, power output pins) of an isolated module from its pin names (any spelling pin_aliases
    gives: V_{IN} is VIN), or None."""
    spelled = {p: pw.pin_aliases(names[p]) or (names[p],) for p in actual}

    def named(pattern, p):
        return any(pattern.match(a) for a in spelled[p])
    inputs = [p for p in actual if named(MODULE_INPUT_RE, p) or 'GND' in spelled[p]]   # GND: the input return
    outputs = [p for p in actual if named(MODULE_OUTPUT_RE, p)]
    if not inputs or not outputs or not any(re.search(r'VIN|VI$', a, re.I) for p in inputs for a in spelled[p]):
        return None
    common = any(a in ('0V', 'COM') for p in outputs for a in spelled[p])
    power = [p for p in outputs if named(MODULE_POSITIVE_OUT_RE, p)
             or (common and named(MODULE_NEGATIVE_OUT_RE, p))]   # -Vo is an output only beside a 0V/COM pin
    return (inputs, outputs, power) if power else None


def model(graph, ref, intent=None):
    """A two-sided object (possibly unresolved), or None. Pin membership always refers to physical pins."""
    part = graph.parts.get(ref, {})
    actual = graph.pins_of(ref)
    official = ((intent or {}).get('devices') or graph.db.get('devices') or {}).get(ref, {})
    names = {p: (graph.pinname.get(ref + '.' + p, '') or official.get('pins', {}).get(p, {}).get('name'))
             for p in actual}
    names = {p: str(n or '') for p, n in names.items()}
    mpn = str(official.get('mpn') or part.get('part') or part.get('value') or '').upper()
    kind = graph.kind(ref)
    groups, mechanism, citation, basis = None, None, '', 'pin-names'
    for pattern, mech, pins, source in MODEL_RULES:
        if re.fullmatch(pattern, mpn, re.I):
            mechanism, groups, citation, basis = mech, pins, source, 'model-pin-rule'
            break
    module_power = set()
    if groups is None and ISOLATED_MODULE_RE.match(mpn) and (sides := _module_sides(names, actual)):
        mechanism, groups, module_power = 'isolated_dcdc', sides[:2], set(sides[2])
        citation = official.get('citation') or ('isolated DC/DC module %s: sides from its native pin names (VIN/GND input, '
                                                'VOUT/0V output); confirm against the module datasheet pin table' % mpn)
    if groups is None and kind == pw.OPTO:
        mechanism = 'optocoupler'
        led = [p for p in actual if graph.role(ref + '.' + p) in ('anode', 'cathode')
               or re.fullmatch(r'(?:LED[_ -]?)?(?:ANODE|CATHODE|A|K)', names[p], re.I)]
        if len(led) == 2:
            groups = (led, [p for p in actual if p not in led])
        elif re.fullmatch(r'(?:PC(?:357|817)|EL817|LTV-?817)[A-Z0-9_-]*', mpn):
            groups = (['1', '2'], ['3', '4'])
            basis = 'model-pin-rule'
            citation = 'Sharp PC357 D2-A00102FEN p2 Internal Connection Diagram / PC817 family pin diagram'
    elif groups is None and kind == pw.RELAY:
        mechanism = 'relay'
        declared = next((x for x in ((intent or {}).get('inductive_loads') or {}).get('loads', [])
                         if x.get('ref') == ref and x.get('kind') == 'relay' and x.get('citation')), {})
        coil_nets = {declared.get('switch_net'), declared.get('rail_net')} - {None}
        coil = [p for p in actual if (coil_nets and actual[p] in coil_nets) or re.match(r'^(COIL|A[12]$)', names[p], re.I)]
        if len(coil) == 2:
            groups = (coil, [p for p in actual if p not in coil])
            citation = declared.get('citation', '')
            basis = 'cited-coil-nets' if declared else 'pin-names'
    elif groups is None and kind == pw.TRANSFORMER:
        mechanism = 'transformer'
        declaration = next((x for x in ((intent or {}).get('inductive_loads') or {}).get('loads', [])
                            if x.get('ref') == ref and x.get('kind') == 'flyback_transformer' and x.get('citation')), {})
        windings = declaration.get('windings', [])
        if windings:
            groups = ([p for w in windings if w.get('role') != 'secondary' for p in w['pins']],
                      [p for w in windings if w.get('role') == 'secondary' for p in w['pins']])
            citation, basis = declaration['citation'], 'cited-windings'
        else:
            primary = [p for p in actual if re.match(r'^(PRI|PRIMARY)', names[p], re.I)]
            secondary = [p for p in actual if re.match(r'^(SEC|SECONDARY)', names[p], re.I)]
            if primary and secondary:
                groups = (primary, secondary)
    elif groups is None and (graph.role_kind(ref) == 'isolator' or re.match(r'^(ADUM\d|ISO\d|SI8[46]\d|CA-IS\d)', mpn)):
        mechanism = 'digital_isolator'
        groups = tuple([p for p in actual if re.fullmatch(r'.*(?:[12]|[AB])', names[p], re.I)
                        and names[p].upper().endswith(suffix)] for suffix in ('1', '2'))
        if not all(groups):
            groups = tuple([p for p in actual if names[p].upper().endswith(suffix)] for suffix in ('A', 'B'))
    if mechanism is None:
        return None
    groups = groups or ([], [])
    groups = [sorted(set(g) & set(actual)) for g in groups]
    # A table's NC pins do not become conductive by belonging to one package side.
    groups = [[p for p in g if names[p].upper() not in ('NC', 'DNC')] for g in groups]
    citation = citation or official.get('citation') or 'netlist physical pin names; side pinout needs datasheet confirmation'
    return {'ref': ref, 'mechanism': mechanism, 'basis': basis, 'citation': citation,
            'sides': [{'id': str(i + 1), 'pins': pins,
                       'nets': sorted({actual[p] for p in pins} - graph.pseudo)} for i, pins in enumerate(groups)],
            'power_outputs': sorted({p for g in groups for p in g} & ({'1', '5', '13'} if mechanism == 'isolated_amplifier' and re.fullmatch(r'AMC3311[A-Z0-9/-]*', mpn)
                                                   else module_power if module_power
                                                   else {'6'} if mechanism == 'isolated_dcdc' else set())),
            'unmapped_pins': sorted(set(actual) - {p for g in groups for p in g}),
            'resolved': all(bool(g) for g in groups)}


def inventory(graph, intent=None):
    return {ref: m for ref in sorted(graph.parts) if graph.is_fitted(ref) and (m := model(graph, ref, intent))}

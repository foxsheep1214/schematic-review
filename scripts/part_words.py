# -*- coding: utf-8 -*-
"""What kind of part this is, read from its own text: refdes prefix, value, symbol, part number and pin names
(SR self-check 5.8, user: 做). The netlist parser (① parse_netlist.py) and every checker classify parts this way, so the
vocabulary is a reading library; checkers/netgraph.py asks it and keeps only net names and connections.
"""
import re

import catalog
import device_kinds
from device_kinds import JST_CONNECTOR_RE, SI_FET_WORDS, USB_CONNECTOR_RE   # noqa: F401  (classify checks these patterns by identity)


# Part words read from a part's text (value, symbol, part number), one vocabulary for every module.
# An electrolytic, solid or super capacitor by its words (an endurance rating "12000h@105°C" names one too; EEE/EEU are
# aluminium part-number series); a tantalum is polarized but not an electrolytic that wears out.
POLARIZED_SYMBOL_RE = re.compile(r'(^|[:\s])(C_Polarized|CP)(_|\b)', re.I)
ELECTROLYTIC_RE = re.compile(r'电解|固态|铝|ELECTROLYTIC|\bELEC\b|\bALUM|\bE-?CAP\b|POLYMER|OS-?CON|SUPER ?CAP|EDLC|超级电容'
                             r'|\bEE[EU]|\d\s*h\s*@\s*\d+\s*°?C', re.I)
TANTALUM_RE = re.compile(r'TANTAL|钽|\bTPS[A-Z]', re.I)
NTC_RE = re.compile(device_kinds.NTC_WORDS, re.I)
VARISTOR_RE = re.compile(device_kinds.VARISTOR_WORDS, re.I)
LED_RE = re.compile(r'(^|[^A-Z])LED(S|[^A-Z]|$)', re.I)
# a controller's high-voltage start-up pin, fed from the bus through its start-up resistor by design
STARTUP_PIN_RE = re.compile(r'^(HV|HVIN|HV_?IN|HV_?START\w*|VSTART\w*|VSTR|STARTUP)$', re.I)
LED_VF_MAX_V = 4.0   # a forward-biased LED's drop, every colour included; a datasheet value replaces it in the review


def is_polarized_capacitor(text):
    """A capacitor whose polarity matters: a polarized symbol, an electrolytic or a tantalum."""
    text = str(text or '')
    return bool(POLARIZED_SYMBOL_RE.search(text) or ELECTROLYTIC_RE.search(text) or TANTALUM_RE.search(text))


RESISTOR, CAPACITOR, INDUCTOR, FERRITE = 'resistor', 'capacitor', 'inductor', 'ferrite'
DIODE, TVS, ZENER, MOSFET, BJT = 'diode', 'tvs', 'zener', 'mosfet', 'bjt'
RELAY, OPTO, CRYSTAL, TRANSFORMER = 'relay', 'opto', 'crystal', 'transformer'
FUSE, JUMPER, TESTPOINT, SWITCH = 'fuse', 'jumper', 'testpoint', 'switch'
IC, CONNECTOR, UNKNOWN = 'ic', 'connector', 'unknown'
BATTERY, BRIDGE_RECTIFIER = 'battery', 'bridge_rectifier'
NTC, VARISTOR = 'ntc', 'varistor'   # 2026-10-26 table extension: the R7 board's TH101/TH601 and RV101 had no kind
COMMON_MODE_CHOKE, COUPLED_INDUCTOR = 'common_mode_choke', 'coupled_inductor'   # 2026-10-27 A1b: magnetics by function
# The registry (device_kinds.KINDS) is the one list of kinds; the constants above are its names for identity checks.
KIND_CONSTANTS = {k: k for k in device_kinds.KINDS}
# A datasheet-declared IC role (catalog.DEVICE_ROLES) classifies as IC; the role itself is read with
# NetGraph.role_kind. ANCHOR_ROLES are the roles a circuit candidate is built around (registry rows with circuits).
IC_ROLES = frozenset(catalog.DEVICE_ROLES)
ANCHOR_ROLES = frozenset(name for name, role in catalog.DEVICE_ROLES.items() if role.circuits)

PREFIX_KINDS = device_kinds.prefix_table()   # refdes prefix → kind, the weakest evidence (registry order)

# NC suppression needs complete physical-family tokens, not the broad
# discovery keywords above. Unknown model suffixes retain a review candidate.
CONNECTOR_CONTACT_RE = (
    r'(?:[^\s:]+:)?(?:'
    r'(?:MICRO|MINI)[-_](?:AB|A|B)[-_]USB|'
    r'USB[_-](?:A|B|C)(?:_Receptacle_USB[23](?:\.[0-9])?(?:_MountingPin)?)?|'
    r'CONN_\d+X\d+|PINHEADER[_-]\d+X\d+|'
    r'HEADER_(?:MALE|FEMALE)[_-]\d+X\d+|HEADER[-_]\d+X\d+|'
    r'JST[-_](?:SH|GH|ZH|PH|XH))')

KEYWORD_KINDS = device_kinds.keyword_table()   # part/value/symbol words → kind, in registry precedence

TWO_TERMINAL = set(device_kinds.with_flag('two_terminal'))
# Magnetics whose windings are coupled but not joined (a winding net is a converter's output, the parts split domains),
# and the one whose windings each pass the line through (a filter's series element) (2026-10-27 A1b).
WINDING_PAIRS = frozenset({TRANSFORMER, COUPLED_INDUCTOR})
SERIES_WINDINGS = frozenset({COMMON_MODE_CHOKE})
PASSIVE_LINKS = set(device_kinds.with_flag('passive_link'))

GATE_NAMES = {'G', 'GATE', 'GT'}
# 斯拉夫语库（如 e-radionica/Soldered）写作 ANODA/KATODA/KOLEKTOR/EMITER/BAZA
DRAIN_NAMES = {'D', 'DRAIN', 'C', 'COLLECTOR', 'COL', 'KOLEKTOR'}
SOURCE_NAMES = {'S', 'SOURCE', 'SRC', 'E', 'EMITTER', 'EMIT', 'EMITER'}
ANODE_NAMES = {'A', 'ANODE', 'AN', '+', 'P', 'ANODA'}
CATHODE_NAMES = {'K', 'C', 'CATHODE', 'CATH', '-', 'N', 'KATODA'}
COIL_NAMES = {'COIL', 'COIL1', 'COIL2', 'A1', 'A2', 'L1', 'L2', '+', '-'}
LED_ANODE_NAMES = {'A', 'ANODE', 'LED+', 'LEDA', 'ANODA'}
LED_CATHODE_NAMES = {'K', 'CATHODE', 'LED-', 'LEDK', 'KATODA'}


def normalize(value):
    return str(value).strip().upper() if value is not None else ''


def copper_tie(ref, part):
    """A fabricated net tie, distinct from a removable zero-ohm resistor."""
    text = ' '.join(str(part.get(k) or '') for k in ('prim', 'jedec', 'part'))
    return bool(re.match(r'^NT\d', ref, re.I) or re.search(r'(?:^|[:\s])NET[-_ ]?TIE(?:[-_\s]|$)', text, re.I))


def board_copper(ref, part):
    """Copper remains when excluded from procurement; a component test pin does not."""
    return copper_tie(ref, part) or bool(re.search(r'(?:^|:)TestPoint_Pad(?:_|$)', str(part.get('jedec') or ''), re.I))


OVERBAR_RE = re.compile(r'^~\{(.+)\}$')
INDEX_SUFFIX_RE = re.compile(r'^(.*?[A-Z])[_-]?(\d+)$')


def pin_aliases(name, pin=None):
    """引脚名的等价写法，原文在前。

    库与导出器对同一个功能名写法不一：`~{RESET}` 的上划线、`EN_12` 的脚号装饰、
    `G1`/`VDD_1` 的序号、`SDA/A4` 的多功能合写。这里只还原**写法**，不改含义——
    低有效标记（N 前缀、_N/_B 后缀）一律保留，极性是判据不是噪声。
    """
    raw = normalize(name)
    if not raw:
        return ()
    found = []

    def add(value):
        value = value.strip()
        if value and value not in found:
            found.append(value)

    add(raw)
    if raw == '+VO':
        add('VO')  # positive DC/DC module output; the original signed pin name is preserved
    for candidate in list(found):
        add(re.sub(r'_\{([A-Za-z0-9]+)\}', r'\1', candidate))  # KiCad inline subscripts: P_{GOOD} -> PGOOD
    for candidate in list(found):
        # 上划线与等价的低有效写法前缀只影响写法，不影响功能名本身
        match = OVERBAR_RE.match(candidate)
        if match:
            add(match.group(1))
        elif candidate[:1] in ('~', '#', '!'):
            add(candidate[1:])
    for candidate in list(found):
        if '/' in candidate:                       # SDA/A4、PB6/SCL 之类合写
            for piece in candidate.split('/'):
                add(piece)
    for candidate in list(found):
        if pin and candidate.endswith('_' + normalize(pin)):
            add(candidate[:-(len(str(pin)) + 1)])  # 导出器附加的脚号装饰
    for candidate in list(found):
        match = INDEX_SUFFIX_RE.match(candidate) if '/' not in candidate else None
        if match:
            add(match.group(1))                    # G1/VDD_1 的序号
    return tuple(found)


def name_matches(pattern, name, pin=None):
    """引脚名的任一等价写法命中即算命中。"""
    return any(pattern.match(alias) for alias in pin_aliases(name, pin))


HEURISTIC_BASES = ('pin-names', 'refdes-prefix')   # no datasheet or part-number evidence behind the kind


def db_kinds(db):
    """{ref: {kind, basis, settlement}} for every fitted part as the classifier reads the netlist alone, without any
    declaration (the reading NetGraph.kind gives a db without device_kinds; step ① tools may not import the checkers).
    settlement is what settles the kind (device_kinds.settlement, 2026-10-27 A2/A5)."""
    pins = {}
    for node, net in (db.get('pin2net') or {}).items():
        ref, _, pin = node.partition('.')
        pins.setdefault(ref, {})[pin] = net
    names = db.get('pinname') or {}
    out = {}
    for ref, part in sorted((db.get('parts') or {}).items()):
        if part.get('nc'):
            continue
        own = pins.get(ref, {})
        kind, basis = classify(ref, part, len(own) or None, [(names.get(ref + '.' + pin), pin) for pin in own])
        out[ref] = {'kind': kind, 'basis': basis,
                    'settlement': device_kinds.settlement(kind, len(own), len(set(own.values())))}
    return out


def kind_gap(graph, ref):
    """Gap text when a transistor/diode kind rests only on pin names or refdes prefix, or on part words for a kind only
    a datasheet declaration settles (2026-10-27 B1: a keyword is a guess too)."""
    basis = graph.basis(ref)
    if basis in HEURISTIC_BASES or (basis == 'part-keyword' and device_kinds.needs_datasheet(
            graph.kind(ref), len(graph.pins_of(ref)))):
        return 'datasheet-kind:' + ref
    return None


def pin_signature(pin_names):
    """Transistor family implied by the placed symbol's own pin names.

    Require the complete B/C/E or G/D/S role set. A lone B or G can be a
    connector/jumper contact name, not transistor evidence. Numbered or
    mixed names give None; datasheet and explicit library evidence remain
    independent of this pin-name heuristic.
    """
    pins = list(pin_names)
    # B01/C01/E01 are matrix contacts, not three transistor terminals.
    if len(pins) > 8 or any(re.fullmatch(r'[BCEGDS]0\d+', normalize(name)) for name, pin in pins):
        return None
    aliases = {a for name, pin in pins for a in pin_aliases(name, pin)}
    base = (bool(aliases & {'B', 'BASE'})
            and bool(aliases & {'C', 'COLLECTOR', 'COL'})
            and bool(aliases & {'E', 'EMITTER', 'EMIT'}))
    gate = (bool(aliases & GATE_NAMES)
            and bool(aliases & {'D', 'DRAIN'})
            and bool(aliases & {'S', 'SOURCE', 'SRC'}))
    if base != gate:
        return BJT if base else MOSFET
    return None


def classify(ref, part, pin_count=None, pin_names=(), declared=None):
    """返回 (kind, basis)。basis 说明结论的依据：datasheet / part-keyword / pin-names / refdes-prefix。

    declared 是审查者按原厂手册记录的器件类型（intent.devices.kind + kind_citation），为权威依据；
    符号引脚名与手册矛盾时返回未知（选错符号）；型号/符号库关键字与手册矛盾时以手册为准（2026-10-27 B3，
    关键词表可能不准，矛盾由资料审计提示）。
    没有手册声明时才退回启发式：关键字 → 引脚名 → 位号前缀。调用方对 pin-names / refdes-prefix
    依据须登记“缺手册器件类型”缺口，不能只凭引脚名或位号前缀下结论。
    pin_names 为 (引脚名, 脚号) 序列。
    """
    if declared:
        # Declared kinds come from JSON; return the module constant so identity checks agree.
        kind = IC if declared in IC_ROLES else KIND_CONSTANTS.get(declared, declared)
        sig = pin_signature(pin_names)
        if kind in (MOSFET, BJT) and sig and sig != kind:
            return UNKNOWN, f'datasheet says {kind} but symbol pin names say {sig}'
        return kind, 'datasheet'
    signature = pin_signature(pin_names)
    primitive = normalize(part.get('prim'))
    if copper_tie(ref, part):
        return JUMPER, 'part-keyword'
    if normalize(part.get('part')) == 'HY931147C':
        return CONNECTOR, 'part-keyword'  # HanRun integrated magnetics RJ45, Rev.A/1 p1; not an active IC
    if pin_count == 2 and re.match(r'^(?:L|FB)\d', ref, re.I) and normalize(part.get('value')) == 'FB':
        return FERRITE, 'part-keyword'
    if re.fullmatch(r'SM\d+B-GHS-TB(?:\(LF\))?(?:\(SN\))?', normalize(part.get('part'))):
        return CONNECTOR, 'part-keyword'  # JST GH physical header MPN; no package-brand inference
    # Placed functional symbols outrank a port label (a terminal named "Relay") or a package category.
    if re.search(r'(?:^|:)MOUNTINGHOLE(?:_PAD)?$|(?:^|:)FIDUCIAL(?:_|$)', primitive):
        return TESTPOINT, 'part-keyword'
    if primitive.startswith('OSCILLATOR:') or re.fullmatch(r'TCXO|VCTCXO|OCXO', normalize(part.get('value'))):
        return IC, 'part-keyword'
    if re.search(r'(?:^|:)SW_DIP_SPSTX?\d*', normalize(part.get('jedec'))):
        return SWITCH, 'part-keyword'
    if re.fullmatch(r'(?:[^:]+:)?NOVA_PROGRAMMER_HEADER', primitive):
        return CONNECTOR, 'part-keyword'
    if re.search(r'(?:^|:)CONN_\d+(?:X\d+)?(?:_|$)|(?:^|:)EASYC(?:[-_]|$)', primitive):
        return CONNECTOR, 'part-keyword'
    blob = ' '.join(normalize(part.get(key)) for key in ('part', 'value', 'prim'))
    ic_ref = re.match(r'^(U|M|IC)\d', ref, re.I)
    controller_pins = {a for name, pin in pin_names for a in pin_aliases(name, pin)}
    if ic_ref and pin_count is not None and pin_count >= 4 and {'GATE', 'SENSE', 'IN'} <= controller_pins:
        return IC, 'pin-names'  # an ideal-diode controller is not a two-terminal diode
    transistor = {kind for pattern, kind in KEYWORD_KINDS if kind in (MOSFET, BJT)
                  and not (pattern == SI_FET_WORDS and ic_ref) and re.search(pattern, blob, re.I)}
    # Optical libraries also contain emitters and integrated RGB controllers.
    # Only the OPTO heuristic uses the symbol identity without its namespace;
    # other explicit library categories (e.g. Transistor_BJT:) stay intact.
    opto_identity = ' '.join(normalize(part.get(key)) for key in ('part', 'value'))
    prim_identity = normalize(part.get('prim'))
    opto_identity += ' ' + prim_identity.split(':', 1)[-1]
    for pattern, kind in KEYWORD_KINDS:
        keyword_blob = opto_identity if kind == OPTO else blob
        if pattern == USB_CONNECTOR_RE:
            # Free-form value text cannot turn a PHY/controller into a contact.
            # Require a physical identity field and agreement of every supplied
            # part/symbol/value identity; conflicts retain the ordinary checks.
            identities = [normalize(part.get(key)) for key in ('part', 'prim', 'value')
                          if normalize(part.get(key))]
            if (not any(normalize(part.get(key)) for key in ('part', 'prim'))
                    or not all(re.fullmatch(USB_CONNECTOR_RE, item, re.I)
                               for item in identities)):
                continue
        if pattern in (JST_CONNECTOR_RE, SI_FET_WORDS) and ic_ref:
            continue
        if kind in (NTC, VARISTOR) and (ic_ref or (pin_count is not None and pin_count > 3)):
            continue
        if re.search(pattern, keyword_blob, re.I):
            if kind in (MOSFET, BJT) and pin_count is not None and pin_count < 3:
                continue
            if kind in (MOSFET, BJT):
                if len(transistor) > 1:
                    return UNKNOWN, 'part keywords name both mosfet and bjt'
                if signature and signature != kind:
                    return UNKNOWN, f'part keyword says {kind} but symbol pin names say {signature}'
            return kind, 'part-keyword'
    if signature and (pin_count is None or pin_count >= 3):
        return signature, 'pin-names'
    names = {normalize(name) for name, _ in pin_names}
    if {'VBUS', 'CC1', 'CC2'} <= names and not ({'VCONN', 'VDD', 'SCL', 'SDA'} & names):
        return CONNECTOR, 'pin-names'   # USB-C receptacle contact set; controllers carry supply/I2C pins
    for pattern, kind in PREFIX_KINDS:
        if re.match(pattern, ref, re.I):
            if kind == MOSFET and pin_count is not None and pin_count < 3:
                return UNKNOWN, 'refdes-prefix conflicts with pin count'
            # 只有两脚的 K 位号不可能同时有线圈和触点（部分库把连接器编为 K）；
            # 三脚以上名称不明的 K 仍按继电器保留，不掩盖真继电器
            if kind == RELAY and pin_count is not None and pin_count < 3:
                return UNKNOWN, 'refdes-prefix conflicts with pin count'
            # Some libraries number every connector K; more than 8 pins is not a relay package
            # (USB-C receptacles, headers). Without a keyword the part stays unknown, never a relay.
            if kind == RELAY and pin_count is not None and pin_count > 8:
                return UNKNOWN, 'refdes-prefix conflicts with pin count'
            return kind, 'refdes-prefix'
    return UNKNOWN, 'no classification evidence'


def unused_input_permission(db, node):
    """A physically unused pin explicitly permitted open by an exact model's own pin table.

    No permission propagates to connected nets, related families or unknown packages.
    These citations are manufacturer clauses from the adjudicated board evidence.
    """
    ref, _, pin = node.partition('.')
    part = (db.get('parts') or {}).get(ref, {})
    model = str(part.get('part') or part.get('value') or '')
    aliases = {a.rstrip('#') for a in pin_aliases((db.get('pinname') or {}).get(node), pin)}
    net = (db.get('pin2net') or {}).get(node)
    if net is not None and len((db.get('nets') or {}).get(net, [])) > 1:
        return None
    if re.fullmatch(r'CH340[CG]', model, re.I):
        pins = {'3': 'RXD', '9': 'CTS', '10': 'DSR', '11': 'RI', '12': 'DCD', '15': 'R232'}
        if pin in pins and pins[pin] in aliases:
            return 'WCH CH340DS1 V3C pp3–4 pin table / p4 unused I/O note (CH340C/G)'
    if re.fullmatch(r'TPS709(?:\d{2})?(?:DBV[RT])?', model, re.I) and pin == '3' and 'EN' in aliases:
        return 'TI TPS709 SBVS186H p3 Table5-1 / p13 §7.4: EN may float, internal 300nA pull-up'
    if re.fullmatch(r'TPS5430(?:DDA[RT]?)?', model, re.I) and pin == '5' and 'ENA' in aliases:
        return 'TI TPS5430 SLVS632L p3 Table4-1 / p9 §6.3.3: ENA may float, internal 1.5Mohm pull-up'
    return None


def usb_connector_type(part):
    """Physical USB family from its own symbol/model, never from VBUS or a CC-less controller."""
    text = ' '.join(str(part.get(k) or '') for k in ('part', 'prim', 'value'))
    if re.fullmatch(r'U262-161N-4BVC11', str(part.get('part') or ''), re.I):
        return 'Type-C'
    if re.search(r'(?:USB[_ -]?C(?:_|\b)|TYPE[_ -]?C(?:_|\b))', text, re.I):
        return 'Type-C'
    if re.search(r'MICRO[_ -]?B[_ -]?USB|USB[_ -]?B[_ -]?MICRO', text, re.I):
        return 'Micro-B'
    if re.search(r'(?:^|[:\s])USB[_ -]?A(?:_|\b)', text, re.I):
        return 'Type-A'
    if re.search(r'(?:^|[:\s])USB[_ -]?B(?:_|\b)', text, re.I):
        return 'Type-B'
    return None


def supply_pin_routes(part, pins):
    """Backward source-search routes of exact multi-terminal identities; never short all terminals.

    C_Feedthrough's placed symbol has through pins 1/2 and shunt pin 3. BAT54C (Nexperia 2022-07-01
    p1 Table2, https://assets.nexperia.com/documents/data-sheet/BAT54C.pdf) is 1/2 anodes, 3 common cathode.
    Caller still verifies population, grounds and the presence of each actual physical pin.
    """
    primitive = str(part.get('prim') or '').rsplit(':', 1)[-1]
    if re.fullmatch(r'C_Feedthrough(?:_Small)?', primitive, re.I) and set(pins) == {'1', '2', '3'}:
        return (('1', '2', 'feedthrough-symbol'), ('2', '1', 'feedthrough-symbol'))
    if str(part.get('part') or '').upper() == 'BAT54C' and set(pins) == {'1', '2', '3'}:
        return (('3', '1', 'BAT54C-p1-Table2'), ('3', '2', 'BAT54C-p1-Table2'))
    return ()

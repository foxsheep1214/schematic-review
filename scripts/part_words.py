# -*- coding: utf-8 -*-
"""What kind of part this is, read from its own text: refdes prefix, value, symbol, part number and pin names
(SR self-check 5.8, user: 做). The netlist parser (① parse_netlist.py) and every checker classify parts this way, so the
vocabulary is a reading library; checkers/netgraph.py asks it and keeps only net names and connections.
"""
import re

import catalog


# Part words read from a part's text (value, symbol, part number), one vocabulary for every module.
# An electrolytic, solid or super capacitor by its words (an endurance rating "12000h@105°C" names one too; EEE/EEU are
# aluminium part-number series); a tantalum is polarized but not an electrolytic that wears out.
POLARIZED_SYMBOL_RE = re.compile(r'(^|[:\s])(C_Polarized|CP)(_|\b)', re.I)
ELECTROLYTIC_RE = re.compile(r'电解|固态|铝|ELECTROLYTIC|\bELEC\b|\bALUM|\bE-?CAP\b|POLYMER|OS-?CON|SUPER ?CAP|EDLC|超级电容'
                             r'|\bEE[EU]|\d\s*h\s*@\s*\d+\s*°?C', re.I)
TANTALUM_RE = re.compile(r'TANTAL|钽|\bTPS[A-Z]', re.I)
NTC_RE = re.compile(r'NTC', re.I)
VARISTOR_RE = re.compile(r'VARISTOR|\bMOV\b|压敏', re.I)
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
KIND_CONSTANTS = {k: k for k in (RESISTOR, CAPACITOR, INDUCTOR, FERRITE, DIODE, TVS, ZENER, MOSFET, BJT,
                                 RELAY, OPTO, CRYSTAL, TRANSFORMER, FUSE, JUMPER, TESTPOINT, SWITCH,
                                 IC, CONNECTOR, BATTERY, BRIDGE_RECTIFIER, UNKNOWN)}
# A datasheet-declared IC role (catalog.DEVICE_ROLES) classifies as IC; the role itself is read with
# NetGraph.role_kind. ANCHOR_ROLES are the roles a circuit candidate is built around (registry rows with circuits).
IC_ROLES = frozenset(catalog.DEVICE_ROLES)
ANCHOR_ROLES = frozenset(name for name, role in catalog.DEVICE_ROLES.items() if role.circuits)

PREFIX_KINDS = (
    (r'^JP\d', JUMPER), (r'^TP\d', TESTPOINT), (r'^FB\d', FERRITE),
    (r'^R\d', RESISTOR), (r'^RN\d', RESISTOR), (r'^C\d', CAPACITOR), (r'^C[XY]\d', CAPACITOR),
    (r'^L\d', INDUCTOR), (r'^D\d', DIODE), (r'^Q\d', MOSFET),
    (r'^K\d', RELAY), (r'^Y\d', CRYSTAL), (r'^X\d', CRYSTAL),
    (r'^T\d', TRANSFORMER), (r'^F\d', FUSE), (r'^SW\d', SWITCH),
    (r'^S\d', SWITCH), (r'^[UM]\d', IC), (r'^(J|P|CN)\d', CONNECTOR), (r'^BT\d', BATTERY),
    (r'^BR\d', BRIDGE_RECTIFIER),
)

JST_CONNECTOR_RE = r'(?:^|[\s:])JST[-_]'
USB_CONNECTOR_RE = r'(?:[^\s:]+:)?(?:MICRO|MINI)[-_](?:AB|A|B)[-_]USB'
# NC suppression needs complete physical-family tokens, not the broad
# discovery keywords above. Unknown model suffixes retain a review candidate.
CONNECTOR_CONTACT_RE = (
    r'(?:[^\s:]+:)?(?:'
    r'(?:MICRO|MINI)[-_](?:AB|A|B)[-_]USB|'
    r'USB[_-](?:A|B|C)(?:_Receptacle_USB[23](?:\.[0-9])?(?:_MountingPin)?)?|'
    r'CONN_\d+X\d+|PINHEADER[_-]\d+X\d+|'
    r'HEADER_(?:MALE|FEMALE)[_-]\d+X\d+|HEADER[-_]\d+X\d+|'
    r'JST[-_](?:SH|GH|ZH|PH|XH))')

KEYWORD_KINDS = (
    (r'RELAY|继电器', RELAY),
    (r'OPTO|PC81[07]|LTV\d|TLP\d|6N13[57]|HCPL|ACPL|FOD\d|CNY17|VO6\d|SFH6\d{2,3}|EL8\d\d|PS2[5-9]\d\d|TCMT\d|KPC\d|H11[A-Z]\d|光耦', OPTO),
    (r'\bTVS\b|SMAJ|SMBJ|SMCJ|P6KE|1\.5KE|ESD\d|PESD|SM712', TVS),
    (r'ZENER|BZX|BZT5\d|MMSZ|1N47\d|稳压二极管', ZENER),
    # KiCad symbol-library category of the symbol actually placed.
    (r'TRANSISTOR_BJT:', BJT),
    (r'TRANSISTOR_FET:|TRANSISTOR_IGBT:', MOSFET),
    (r'MOSFET|\bFET\b|NMOS|PMOS|[NP]-MOS|IRF|IRLML|AO\d{4}|SI\d{4}|BSS\d|2N7002|IGBT', MOSFET),
    (r'\bNPN\b|\bPNP\b|BC[PXW]?\d{2,3}|2N\d{4}|MMBT|PBSS|S8050|S8550|三极管', BJT),
    (r'SCHOTTKY|DIODE|SS\d{2}|BAT\d|1N4\d{3}|1N58\d|二极管', DIODE),
    (r'FERRITE|BEAD|BLM\d|MPZ\d|磁珠', FERRITE),
    (r'INDUCTOR|CHOKE|电感', INDUCTOR),
    # OSC only as a whole word: footprint names like Bosch_LGA-8 contain the letters.
    (r'CRYSTAL|XTAL|\bOSC(?:ILLATOR)?\b|晶振|晶体', CRYSTAL),
    (r'TRANSFORMER|变压器', TRANSFORMER),
    (r'FUSE|PTC|保险', FUSE),
    (r'(?:^|[\s:_])BATTERY\b|电池', BATTERY),
    # Explicit connector symbol/part families can use arbitrary refdes (e.g. K).
    # Keep stronger device keywords above and do not treat a bare "terminal" or
    # "header" in an IC description as a connector. This is role evidence only,
    # never a connector pinout/current-rating guarantee.
    # KiCad places test pads as Connector:TestPoint*; the library entry, not the
    # namespace, decides that this is a probe/fixture pad rather than a connector.
    (r'(?:^|[\s:])TEST_?POINT(?:_|\b)', TESTPOINT),
    (r'(?:\b|_)CONNECTORS?(?:_[A-Z0-9]+)*:|\bCONN_\d+X\d+\b|'
     r'\bUSB[-_ ]?(?:2\.0[-_ ]?)?TYPE[-_ ]?C\b|\bTYPE-C-\d+-M\b|\bBARREL[-_ ]?JACK\b|\bPWR[-_ ]?JA[C]?K|'
     r'\bPINHEADER[_:-]|\bTERMINAL_?BLOCK[_:-]|'
     r'\bHEADER_(?:MALE|FEMALE)[_:-]|\bHEADER[-_]\d+X\d+(?:\b|[_:-])|'
     r'\bTERMINAL_KF\d', CONNECTOR),
    # Legacy physical USB connector symbols can have a U refdes. Match the
    # complete connector-family token, not USB controller/PHY descriptions.
    (USB_CONNECTOR_RE, CONNECTOR),
    # A bare vendor name: never re-identify an IC/module refdes by it.
    (JST_CONNECTOR_RE, CONNECTOR),
)

TWO_TERMINAL = {RESISTOR, CAPACITOR, INDUCTOR, FERRITE, DIODE, TVS, ZENER,
                FUSE, JUMPER}
PASSIVE_LINKS = {RESISTOR, INDUCTOR, FERRITE, JUMPER, FUSE}

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


def kind_gap(graph, ref):
    """Gap text when a transistor/diode kind rests only on pin names or refdes prefix."""
    if graph.basis(ref) in HEURISTIC_BASES:
        return 'datasheet-kind:' + ref
    return None


def pin_signature(pin_names):
    """Transistor family implied by the placed symbol's own pin names.

    Require the complete B/C/E or G/D/S role set. A lone B or G can be a
    connector/jumper contact name, not transistor evidence. Numbered or
    mixed names give None; datasheet and explicit library evidence remain
    independent of this pin-name heuristic.
    """
    aliases = {a for name, pin in pin_names for a in pin_aliases(name, pin)}
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
    型号/符号库关键字与符号引脚名只作交叉核对，与手册矛盾时返回未知（选错符号或填错型号）。
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
        blob = ' '.join(normalize(part.get(key)) for key in ('part', 'value', 'prim', 'jedec'))
        named = {k for pattern, k in KEYWORD_KINDS if k in (MOSFET, BJT) and re.search(pattern, blob, re.I)}
        if kind in (MOSFET, BJT) and named and kind not in named:
            return UNKNOWN, f'datasheet says {kind} but part/library keywords say {"/".join(sorted(named))}'
        return kind, 'datasheet'
    signature = pin_signature(pin_names)
    blob = ' '.join(normalize(part.get(key)) for key in ('part', 'value', 'prim', 'jedec'))
    transistor = {kind for pattern, kind in KEYWORD_KINDS
                  if kind in (MOSFET, BJT) and re.search(pattern, blob, re.I)}
    # Optical libraries also contain emitters and integrated RGB controllers.
    # Only the OPTO heuristic uses the symbol identity without its namespace;
    # other explicit library categories (e.g. Transistor_BJT:) stay intact.
    opto_identity = ' '.join(normalize(part.get(key)) for key in ('part', 'value', 'jedec'))
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
        if pattern == JST_CONNECTOR_RE and re.match(r'^(U|M|IC)\d', ref, re.I):
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

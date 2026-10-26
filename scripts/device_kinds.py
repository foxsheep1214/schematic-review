# -*- coding: utf-8 -*-
"""One registry of device kinds (item 6 of the 2026-10-26 SR review): what a kind is called, how a part's text names
it (refdes prefix — the weakest evidence —, part/value/symbol words in classifier precedence, datasheet-title cues
with spaces removed), and what the reviewers' tools read off the kind (two terminals, a series link in the power path,
a protective part, the wearout class the kind alone decides, whether the reviewer may declare it in intent.devices).

`part_words` builds its prefix and keyword tables from this registry, `board_intent` its declarable kinds,
`datasheet_kinds` its cues, `plan_circuits` its wearout classes and `circuit_candidates` its protective parts — so a
new kind is one row here (plus a bounding-table cell when it has guaranteed parameters), never five lists. Integrated
circuits are the roles of `catalog.DEVICE_ROLES`; this registry carries them as the single kind `ic`.
"""
import re
from collections import OrderedDict, namedtuple

import catalog

DeviceKind = namedtuple('DeviceKind', 'title prefixes words cues two_terminal passive_link protective wearout declarable',
                        defaults=((), (), (), False, False, False, None, True))

# Connector families: whole physical-family tokens the classifier checks with extra care (part_words.classify).
USB_CONNECTOR_RE = r'(?:[^\s:]+:)?(?:MICRO|MINI)[-_](?:AB|A|B)[-_]USB'
JST_CONNECTOR_RE = r'(?:^|[\s:])JST[-_]'
NTC_WORDS = r'NTC'
VARISTOR_WORDS = r'VARISTOR|\bMOV\b|压敏'

# Registry order is the classifier's keyword precedence (the first kind whose word matches wins); kinds without words
# follow. Transistor order between bjt and mosfet does not matter: both matching is UNKNOWN whatever comes first.
KINDS = OrderedDict([
    ('relay', DeviceKind('继电器', (r'^K\d',), (r'RELAY|继电器',), wearout='RELAY')),
    # Thermistors and varistors by the shared words; an IC refdes or a part with more than three pins never becomes one
    # by a word in its description ("charger with NTC input"). RV is also KiCad's potentiometer prefix: no prefix rule.
    ('varistor', DeviceKind('压敏电阻', (), (VARISTOR_WORDS,), ('varistor', 'siov'), two_terminal=True, protective=True,
                            wearout='VARISTOR')),
    ('ntc', DeviceKind('热敏电阻', (r'^(TH|RT|NTC)\d',), (NTC_WORDS,), ('ntcthermistor', 'thermistor', 'inrushcurrentlimiter'),
                       two_terminal=True, passive_link=True, protective=True)),   # INRUSH_NTC only in the power path
    ('opto', DeviceKind('光耦', (), (r'OPTO|PC81[07]|LTV\d|TLP\d|6N13[57]|HCPL|ACPL|FOD\d|CNY17|VO6\d|SFH6\d{2,3}|EL8\d\d|PS2[5-9]\d\d|TCMT\d|KPC\d|H11[A-Z]\d|光耦',),
                        ('optocoupler', 'photocoupler', 'optoisolator', 'opticallycoupled', 'opticalisolator', 'opticalcoupler'),
                        wearout='OPTO')),
    ('tvs', DeviceKind('TVS', (), (r'\bTVS\b|SMAJ|SMBJ|SMCJ|P6KE|1\.5KE|ESD\d|PESD|SM712',),
                       ('tvs', 'esdprotection', 'transientvoltagesuppress', 'transientsuppress'), two_terminal=True, protective=True)),
    ('zener', DeviceKind('齐纳', (), (r'ZENER|BZX|BZT5\d|MMSZ|1N47\d|稳压二极管',), ('zener',), two_terminal=True)),
    # KiCad symbol-library category of the symbol actually placed, then the part words.
    ('bjt', DeviceKind('双极晶体管', (), (r'TRANSISTOR_BJT:', r'\bNPN\b|\bPNP\b|BC[PXW]?\d{2,3}|2N\d{4}|MMBT|PBSS|S8050|S8550|三极管'),
                       ('npn', 'pnp', 'bipolar'))),
    ('mosfet', DeviceKind('MOSFET', (r'^Q\d',), (r'TRANSISTOR_FET:|TRANSISTOR_IGBT:',
                                                 r'MOSFET|\bFET\b|NMOS|PMOS|[NP]-MOS|IRF|IRLML|AO\d{4}|SI\d{4}|BSS\d|2N7002|IGBT'),
                          ('mosfet', 'nchannel', 'pchannel', 'superjunction'))),
    ('diode', DeviceKind('二极管', (r'^D\d',), (r'SCHOTTKY|DIODE|SS\d{2}|BAT\d|1N4\d{3}|1N58\d|二极管',), ('rectifier', 'diode', 'schottky'),
                         two_terminal=True)),
    ('ferrite', DeviceKind('磁珠', (r'^FB\d',), (r'FERRITE|BEAD|BLM\d|MPZ\d|磁珠',), two_terminal=True, passive_link=True)),
    ('inductor', DeviceKind('电感', (r'^L\d',), (r'INDUCTOR|CHOKE|电感',), two_terminal=True, passive_link=True)),
    # OSC only as a whole word: footprint names like Bosch_LGA-8 contain the letters.
    ('crystal', DeviceKind('晶体', (r'^Y\d', r'^X\d'), (r'CRYSTAL|XTAL|\bOSC(?:ILLATOR)?\b|晶振|晶体',))),
    ('transformer', DeviceKind('变压器', (r'^T\d',), (r'TRANSFORMER|变压器',), ('transformer',))),
    ('fuse', DeviceKind('保险', (r'^F\d',), (r'FUSE|PTC|保险',), two_terminal=True, passive_link=True, protective=True)),  # PTC or FUSE by its words
    ('battery', DeviceKind('电池', (r'^BT\d',), (r'(?:^|[\s:_])BATTERY\b|电池',), wearout='BATTERY', declarable=False)),
    # KiCad places test pads as Connector:TestPoint*; the library entry, not the namespace, decides that this is a
    # probe/fixture pad rather than a connector.
    ('testpoint', DeviceKind('测试点', (r'^TP\d',), (r'(?:^|[\s:])TEST_?POINT(?:_|\b)',), declarable=False)),
    # Explicit connector symbol/part families can use arbitrary refdes (e.g. K). Stronger device keywords stay above;
    # a bare "terminal" or "header" in an IC description is not a connector. Role evidence only, never a pinout or
    # current-rating guarantee. Legacy physical USB connector symbols can have a U refdes (USB_CONNECTOR_RE matches the
    # complete family token, never a controller/PHY description); a bare vendor name never re-identifies an IC (JST).
    ('connector', DeviceKind('连接器', (r'^(J|P|CN)\d',), (
        r'(?:\b|_)CONNECTORS?(?:_[A-Z0-9]+)*:|\bCONN_\d+X\d+\b|'
        r'\bUSB[-_ ]?(?:2\.0[-_ ]?)?TYPE[-_ ]?C\b|\bTYPE-C-\d+-M\b|\bBARREL[-_ ]?JACK\b|\bPWR[-_ ]?JA[C]?K|'
        r'\bPINHEADER[_:-]|\bTERMINAL_?BLOCK[_:-]|'
        r'\bHEADER_(?:MALE|FEMALE)[_:-]|\bHEADER[-_]\d+X\d+(?:\b|[_:-])|'
        r'\bTERMINAL_KF\d', USB_CONNECTOR_RE, JST_CONNECTOR_RE), ('connector', 'receptacle', 'terminalblock'), wearout='CONNECTOR')),
    # Kinds a part's text names only by its refdes prefix.
    ('resistor', DeviceKind('电阻', (r'^R\d', r'^RN\d'), two_terminal=True, passive_link=True)),
    ('capacitor', DeviceKind('电容', (r'^C\d', r'^C[XY]\d'), two_terminal=True)),
    ('jumper', DeviceKind('跳线', (r'^JP\d',), two_terminal=True, passive_link=True)),
    ('switch', DeviceKind('开关', (r'^SW\d', r'^S\d'), wearout='SWITCH')),
    ('bridge_rectifier', DeviceKind('整流桥', (r'^BR\d',), cues=('bridgerectifier',), protective=True)),
    ('ic', DeviceKind('集成电路', (r'^[UM]\d',), declarable=False)),   # declared by role (catalog.DEVICE_ROLES)
    ('unknown', DeviceKind('未知', declarable=False)),
])


def prefix_table(kinds=KINDS):
    """[(refdes regex, kind)] — the weakest evidence; the regexes are mutually exclusive so order does not matter."""
    return tuple((pattern, name) for name, kind in kinds.items() for pattern in kind.prefixes)


def keyword_table(kinds=KINDS):
    """[(word regex, kind)] in classifier precedence: registry order, each kind's words in their listed order."""
    return tuple((pattern, name) for name, kind in kinds.items() for pattern in kind.words)


def cue_table(kinds=KINDS):
    """[(kind, datasheet-title cues)] for the discrete kinds; the IC roles' cues come from catalog.DEVICE_ROLES."""
    return tuple((name, kind.cues) for name, kind in kinds.items() if kind.cues)


def declarable(kinds=KINDS):
    """The kinds a reviewer may write in intent.devices.<ref>.kind, before the IC roles."""
    return tuple(name for name, kind in kinds.items() if kind.declarable)


def with_flag(flag, kinds=KINDS):
    """The kinds whose boolean `flag` (two_terminal, passive_link, protective) is set."""
    return frozenset(name for name, kind in kinds.items() if getattr(kind, flag))


def wearout_of(name, kinds=KINDS):
    """The catalog.WEAROUT_CLASSES entry the kind alone decides, or None when the circuit or the words decide."""
    kind = kinds.get(name)
    return kind.wearout if kind is not None else None


def errors(kinds=KINDS):
    """Self-check of the registry: anchored prefixes, compiling words, squashed cues, known wearout classes, a series
    link is two-terminal, the IC roles are not also discrete kinds."""
    out = []
    for name, kind in kinds.items():
        for pattern in kind.prefixes:
            if not (pattern.startswith('^') and pattern.endswith(r'\d')):
                out.append('%s: prefix %r must be anchored as ^…\\d' % (name, pattern))
        for pattern in kind.prefixes + kind.words:
            try:
                re.compile(pattern, re.I)
            except re.error as exc:
                out.append('%s: %r does not compile (%s)' % (name, pattern, exc))
        for cue in kind.cues:
            if not re.fullmatch(r'[a-z0-9]+', cue):
                out.append('%s: cue %r must be lowercase alphanumerics with spaces removed' % (name, cue))
        if kind.wearout is not None and kind.wearout not in catalog.WEAROUT_CLASSES:
            out.append('%s: wearout %r is not a catalog.WEAROUT_CLASSES entry' % (name, kind.wearout))
        if kind.passive_link and not kind.two_terminal:
            out.append('%s: a passive link must be two-terminal' % name)
        if name in catalog.DEVICE_ROLES and name != 'ic':   # the registry's `ic` is the roles' generic entry
            out.append('%s: an IC role is not a discrete kind' % name)
    return out

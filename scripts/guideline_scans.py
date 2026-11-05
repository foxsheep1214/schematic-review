#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cold scans that turn machine-decidable design criteria into candidates (user 2026-11-04: 提高 SR 对设计准则的自动扫描覆盖).

Each scan judges one structure a criterion names from the netlist, the BOM fields or an exact-identity table, and says
nothing where the evidence is missing: an unread part, an unnamed pin or a rail with no voltage is no hit. What needs a
datasheet number or a declared requirement stays with the reviewer's check the criterion already maps to. Rail voltages
read from names are hints; the wording of every row says what would close it.
"""
import re

import part_words as pw
import protective_clamps
from checkers import netgraph as ng
from checkers.netgraph import is_ground, rail_voltage
from checkers.passive_stress import rated_voltage
from decoupling import parse_capacitance
from latch_criteria import Model as LatchModel, _protection_status
from solve_dividers import parse_resistor

ORDERING_FIELD_RE = re.compile(r'^(?:MPN|MFR?_?PN|MFG_?PN|MANUFACTURER_?PART(?:_?NUMBER)?|PART_?NUMBER|P/?N|LCSC(?:_?PART)?(?:_?#)?|料号|订货号)$', re.I)
# G02-038: library default names and bare categories, per kind, of the parts whose value decides a calculation.
DEFAULT_VALUES = {
    pw.RESISTOR: {'R', 'R_SMALL', 'R_US', 'R_SMALL_US', 'RES', 'RESISTOR'},
    pw.CAPACITOR: {'C', 'C_SMALL', 'CAP', 'CAPACITOR', 'C_POLARIZED', 'C_POLARIZED_SMALL', 'CP', 'CP_SMALL'},
    pw.INDUCTOR: {'L', 'L_SMALL', 'IND', 'INDUCTOR'},
    pw.FERRITE: {'FB', 'FERRITE_BEAD', 'FERRITE_BEAD_SMALL', 'FERRITEBEAD'},
    pw.DIODE: {'D', 'D_SMALL', 'DIODE', 'D_SCHOTTKY', 'D_SCHOTTKY_SMALL', 'SCHOTTKY'},
    pw.ZENER: {'D_ZENER', 'D_ZENER_SMALL', 'ZENER'},
    pw.TVS: {'D_TVS', 'D_TVS_SMALL', 'TVS', 'ESD'},
    pw.MOSFET: {'Q_NMOS_GSD', 'Q_NMOS_GDS', 'Q_NMOS_DGS', 'Q_NMOS_SGD', 'Q_PMOS_GSD', 'Q_PMOS_GDS', 'Q_PMOS_DGS', 'Q_PMOS_SGD',
                'NMOS', 'PMOS', 'MOSFET'},
    pw.BJT: {'Q_NPN_BCE', 'Q_NPN_BEC', 'Q_NPN_CBE', 'Q_NPN_EBC', 'Q_PNP_BCE', 'Q_PNP_BEC', 'Q_PNP_CBE', 'Q_PNP_EBC', 'NPN', 'PNP'},
    pw.FUSE: {'F', 'FUSE', 'FUSE_SMALL', 'POLYFUSE', 'POLYFUSE_SMALL', 'PPTC'},
    pw.CRYSTAL: {'Y', 'XTAL', 'CRYSTAL', 'CRYSTAL_SMALL', 'CRYSTAL_GND24', 'CRYSTAL_GND23', 'CRYSTAL_GND24_SMALL'},
}
FUSE_DC_RATING_RE = re.compile(r'(?:^|[/\s,])(\d+(?:\.\d+)?)\s*V(?:DC)(?:$|[/\s,])', re.I)
UNDECIDED_RE = re.compile(r'(?:^|[^A-Z0-9])(?:TBD|TBC|TBR)(?:$|[^A-Z0-9])|待定|占位', re.I)
ACTIVE_KINDS = (pw.IC, pw.DIODE, pw.ZENER, pw.TVS, pw.MOSFET, pw.BJT, pw.OPTO)
# BZT52Bxx, BQ769x2, LM2596?-5.0: a wildcard where an ordering code has a digit or letter
WILDCARD_RE = re.compile(r'\?|\*|[Xx]{2,}|\dx\d')
BARE_SERIES_RE = re.compile(r'SM[ABCF]J', re.I)
MODEL_RE = re.compile(r'^[A-Z]{1,6}\d[A-Z0-9/+#.-]{2,}$|^\d[A-Z]{1,2}\d{3,}[A-Z0-9/+#-]*$')
# the F is required: 300µ and 1m on a resistor are milli- and micro-ohm shunts
CAP_WRITTEN_RE = re.compile(r'^\s*\d+(?:[.,]\d+)?\s*(?:[pnuµμ]|m)\s*F(?:[\d/\s,]|$)', re.I)
# not 225K: three digits and a tolerance letter is a capacitor's own code (2.2 µF ±10 %)
RES_WRITTEN_RE = re.compile(r'^\s*(?!\d{3}[KMkm])\d+(?:[.,]\d+)?\s*(?:[kKM]\s*(?:Ω|OHM)?|[RΩ]|OHM)\s*(?:[/\s,]|$)', re.I)

LDO_RE = re.compile(r'REGULATOR_LINEAR|\bLDO|LOW.?DROPOUT|AMS1117|L[MD]1117|AP2112|AP2210|MCP170\d|XC62\d\d|RT9013|RT9193|'
                    r'LP298\d|LP5907|TLV7\d{4}|TPS7[\dA]|SPX3819|HT7\d33|ME6211', re.I)
REGULATOR_IN_RE = re.compile(r'^V?IN\d*$|^VI$', re.I)
REGULATOR_OUT_RE = re.compile(r'^V?OUT\d*$|^VO$', re.I)
SOFT_DIELECTRIC_RE = re.compile(r'(?<![A-Z0-9])(?:Y5V|Y5U|Z5U)(?![A-Z0-9])', re.I)
SPEC_FIELD_RE = re.compile(r'^(?:SPEC|SPECIFICATION|SELECTEDSPEC|DESCRIPTION|DIELECTRIC|介质|规格)$', re.I)
# Stand-off read off a part number only where the family's number IS VRWM: SMBJ15A = 15 V, SMF5.0A, PESD5V0L2BT = 5.0 V.
VRWM_FAMILY_RE = re.compile(r'(?:^|[^A-Z0-9])SM[ABCF]J?(\d{1,3}(?:\.\d)?)C?A?(?:[^0-9.]|$)', re.I)
VRWM_PESD_RE = re.compile(r'(?:^|[^A-Z0-9])PESD(\d{1,2})V(\d)', re.I)
UNIDIRECTIONAL_RE = re.compile(r'^(?:SM[ABCF]J?\d{1,3}(?:\.\d)?A|30KPA\d+A|SM15T\d+A)(?:[-/#].*)?$', re.I)
REVERSE_CONTROLLER_RE = re.compile(r'^(?:LTC435\d|LTC4365|LTC4367|LM7[34]\d\d\d?|LM5050|TPS2410|TPS2412|LM66100|MAX1661\d|NIS5420)', re.I)
CONTROLLER_INPUT_RE = re.compile(r'^(?:V?IN\d*|ANODE)$', re.I)
PMOS_WORD_RE = re.compile(r'PMOS|P[-_ ]?MOS|P[-_ ]?CH(?:AN)?|P[-_ ]?FET', re.I)
NMOS_WORD_RE = re.compile(r'NMOS|N[-_ ]?MOS|N[-_ ]?CH(?:AN)?|N[-_ ]?FET', re.I)
LATCH_OUT_RE = re.compile(r'^(?:V?OUT\d*|SOURCE)$', re.I)
AUTO_DIRECTION_RE = re.compile(r'(?:^|[^A-Z0-9])(?:SN74)?TXB0\w*', re.I)
OPEN_DRAIN_NET_RE = re.compile(r'(?:^|[^A-Z0-9])(?:SDA|SCL)\d*(?:$|[^A-Z0-9])|ONE_?WIRE|1_?WIRE|(?:^|[^A-Z0-9])OWI(?:$|[^A-Z0-9])', re.I)
SPI_PIN_RE = re.compile(r'^(?:MOSI|MISO|SCK|SCLK|SDI|SDO|CS|SS|DC|RS)$', re.I)
TXB_PULL_MIN_KOHM = 50.0
CC_PIN_RE = re.compile(r'^CC([12])$', re.I)
RD_MIN_KOHM, RD_MAX_KOHM = 5.1 * 0.8, 5.1 * 1.2   # G04-104: 5.1 kΩ ±20 %, the default-power tolerance
RESISTOR_PACK_RE = re.compile(r'R_?PACK|R_?ARRAY|R_?NETWORK', re.I)
RS485_COMMON_MODE_V = 12.0   # G04-025: a symmetric TVS below 12 V narrows the −7…+12 V common mode
CAN_PIN_RE = re.compile(r'^CAN_?([HL])$', re.I)
OPAMP_RE = re.compile(r'AMPLIFIER_OPERATIONAL|(?:^|[^A-Z0-9])(?:OPA\d|LM358|LM324|LM2904|LM2902|LM321|LMV3\d\d|TL07\d|TL08\d|TLV9\d|'
                      r'MCP60\d\d|MCP6\d{2}(?!S)|ADA4\d|NE5532|RC4558|TSV\d|TS91\d)', re.I)
NOT_VOLTAGE_AMP_RE = re.compile(r'AMPLIFIER_(?:CURRENT|INSTRUMENTATION|DIFFERENCE|AUDIO|VIDEO)|OPA\d*(?:CURRENT)', re.I)
OPAMP_INPUT_RE = re.compile(r'^(?:IN)?([A-D1-4])?(?:_?IN)?_?([+-])$|^([+-])(?:IN)?_?([A-D1-4])?$|^([1-4A-D])?IN([+-])$|^V?IN([+-])_?([A-D1-4])?$', re.I)
OPAMP_OUTPUT_RE = re.compile(r'^(?:V?OUT|O)_?([A-D1-4])?$|^([A-D1-4])_?(?:OUT|O)$', re.I)
SUPPLY_PIN_RE = re.compile(r'^(?:VCC\w*|VDD\w*|V\+|\+V|VS\+?|\+VS|AVDD\w*|DVDD\w*|VIO|VCCIO)$', re.I)
ADC_PIN_RE = re.compile(r'(?:^|[^A-Z])(?:ADC|AIN)\d*(?:$|[^A-Z])', re.I)
CT_PIN_RE = re.compile(r'^(?:T[DX]?CT|R[DX]?CT|CT\d?|TX_?CT|RX_?CT)$', re.I)
COMPARATOR_RE = re.compile(r'COMPARATOR|(?:^|[^A-Z0-9])(?:LM339|LM393|LM2901|LM2903|TLV170\d|TLV370\d|LMV33\d|LMV39\d|MAX9\d{2,3})', re.I)
RJ45_RE = re.compile(r'RJ-?45|MAG-?JACK|\bHR91\d|\bHFJ11|\bJ0G|\bARJ|TRJ\d', re.I)
LOGIC_LEVEL_GAP_V = 0.5   # beyond VDD + 0.3 V of a common CMOS absolute maximum, with margin for the name-read rails


def _text(part):
    return ' '.join(str(part.get(k) or '') for k in ('part', 'value', 'prim'))


def _fitted(lint, ref):
    return lint.graph.is_fitted(ref) and not lint.parts.get(ref, {}).get('nc')


def _ordering_code(part):
    for key, value in (part.get('fields') or {}).items():
        if ORDERING_FIELD_RE.match(str(key).strip()) and str(value or '').strip():
            return str(value).strip()
    return ''


def _maker_code(part):
    """The maker's ordering code: a distributor's stock number (LCSC C8734) names no model to compare a value with."""
    for key, value in (part.get('fields') or {}).items():
        if (ORDERING_FIELD_RE.match(str(key).strip()) and not str(key).strip().upper().startswith('LCSC')
                and str(value or '').strip()):
            return str(value).strip()
    return ''


def _nodes(lint, ref):
    return sorted(ref + '.' + pin for pin in lint.graph.pins_of(ref))


def _names(lint, node):
    return pw.pin_aliases(lint.graph.pinname.get(node), node.partition('.')[2])


def _pin_match(lint, node, pattern):
    return pw.name_matches(pattern, lint.graph.pinname.get(node), node.partition('.')[2])


def _net(lint, node):
    net = lint.pin2net.get(node)
    return None if net is None or net in lint.pseudo else net


def _named_rail(net):
    return bool(net) and not is_ground(net) and (ng.is_rail(net) or ng.is_rail(str(net).lstrip('/').lstrip('+')))


def _volts(lint, net):
    """(the net's highest voltage, how it is known), declared first, the name as a hint; (None, '') when neither says."""
    window = ((lint.intent or {}).get('power_rails') or {}).get(net)
    volts = window.get('voltage_v') if isinstance(window, dict) else None
    if isinstance(volts, dict) and isinstance(volts.get('max'), (int, float)):
        return float(volts['max']), 'intent.power_rails'
    if isinstance(volts, (int, float)):
        return float(volts), 'intent.power_rails'
    if _named_rail(net) and rail_voltage(net) is not None:
        return rail_voltage(net), '按网名推定，标称'
    return None, ''


def _supply_volts(lint, ref):
    """The one positive supply voltage of an IC, or None: no supply pin, an unread one, or two different rails."""
    volts = set()
    for node in _nodes(lint, ref):
        if not _pin_match(lint, node, SUPPLY_PIN_RE):
            continue
        net = _net(lint, node)
        if net is None or is_ground(net):
            continue
        voltage = _volts(lint, net)[0]
        if voltage is None or voltage <= 0:
            return None
        volts.add(voltage)
    return volts.pop() if len(volts) == 1 else None


# --- G02: identity and documents ---------------------------------------------------------------------------------
def _bom_code(lint, ref):
    columns = ((lint.db.get('bom') or {}).get('parts') or {}).get(ref) or {}
    return next((str(v).strip() for k, v in columns.items() if ORDERING_FIELD_RE.match(str(k).strip()) and str(v).strip()), '')


def placeholder_values(lint):
    """DEV-A04 (G02-038): library default names, bare categories, wildcards, series with no grade, TBD words."""
    found = {}
    for ref, part in sorted(lint.parts.items()):
        if not _fitted(lint, ref):
            continue
        value, kind = str(part.get('value') or '').strip(), lint.graph.kind(ref)
        code = _ordering_code(part) or _bom_code(lint, ref)
        if UNDECIDED_RE.search(value) or UNDECIDED_RE.search(code):
            found.setdefault('未定词', []).append(ref)
        elif kind in DEFAULT_VALUES and value.upper() in DEFAULT_VALUES[kind] and not code:
            found.setdefault('库默认名或只写类别', []).append(ref)
        elif kind in ACTIVE_KINDS and WILDCARD_RE.search(code or value):
            found.setdefault('通配后缀', []).append(ref)
        elif kind == pw.TVS and BARE_SERIES_RE.fullmatch(code or value):
            found.setdefault('系列名缺电压档', []).append(ref)
    for reason, refs in sorted(found.items()):
        lint.add('DEV-A04', '器件值为占位值或未定档',
                 '%s（%d 个）：%s（如 %s）；决定电压、时序或钳位的判不成立，其余判风险，有 TBR 登记的按输入缺口关闭（G02-038）' % (
                     reason, len(refs), '、'.join(refs), str(lint.parts[refs[0]].get('value'))), refs[0], kind='CANDIDATE')


def _values_differ(kind, first, second):
    parse = {pw.RESISTOR: lambda v: (parse_resistor(v) or {}).get('kohm'), pw.CAPACITOR: parse_capacitance}.get(kind)
    if not parse:
        return False
    one, other = parse(first), parse(second)
    return one is not None and other is not None and abs(one - other) > 1e-3 * max(abs(one), abs(other), 1e-15)


def _different_models(value, code):
    """Neither contains the other, no shared opening, and the value's main number is not in the code: LM62440-Q1 and
    LMQ62440BPPQ are one part, LM358 and TL072 are not."""
    wanted, ordered = (re.sub(r'[^A-Z0-9]', '', text.upper()) for text in (value, code))
    if not wanted or not ordered or wanted in ordered or ordered in wanted or wanted[:4] == ordered[:4]:
        return False
    numbers = re.findall(r'\d{3,}', wanted)
    return not (numbers and max(numbers, key=len) in ordered)


def identity_fields(lint):
    """DEV-A05 (G02-036): a value of another kind's unit, one ordering code on different values, value and code of different models."""
    by_code = {}
    for ref, part in sorted(lint.parts.items()):
        if not _fitted(lint, ref):
            continue
        value, kind, code = str(part.get('value') or '').strip(), lint.graph.kind(ref), _ordering_code(part)
        if kind == pw.RESISTOR and CAP_WRITTEN_RE.match(value) and not parse_resistor(value):
            lint.add('DEV-A05', '器件字段指向不同器件', '%s: 电阻的值写成容值 %s；按原厂订货信息定哪一处对（G02-036）' % (ref, value), ref, kind='CANDIDATE')
        elif kind == pw.CAPACITOR and RES_WRITTEN_RE.match(value) and parse_capacitance(value) is None:
            lint.add('DEV-A05', '器件字段指向不同器件', '%s: 电容的值写成阻值 %s；按原厂订货信息定哪一处对（G02-036）' % (ref, value), ref, kind='CANDIDATE')
        if not code:
            continue
        by_code.setdefault(code.upper(), []).append(ref)
        maker = _maker_code(part)
        if kind in ACTIVE_KINDS and maker and MODEL_RE.match(value.upper()) and _different_models(value, maker):
            lint.add('DEV-A05', '器件字段指向不同器件', '%s: 值 %s 与料号 %s 看不出是同一型号；后缀、封装与手册须指向同一订货型号（G02-036）' % (ref, value, maker),
                     ref, kind='CANDIDATE')
    for code, refs in sorted(by_code.items()):
        kind = lint.graph.kind(refs[0])
        values = {ref: str(lint.parts[ref].get('value') or '') for ref in refs}
        common = max(sorted(set(values.values())), key=list(values.values()).count)
        odd = [ref for ref in refs if _values_differ(kind, common, values[ref])]
        if odd:
            lint.add('DEV-A05', '器件字段指向不同器件', '同一料号 %s 多数是 %s，%s 的值不同；料号与值只能有一个对（G02-036）' % (
                code, common, '、'.join('%s=%s' % (ref, values[ref]) for ref in odd)), odd[0], kind='CANDIDATE')


def bom_schematic_sets(lint):
    """DOC-A05 (G02-037): the BOM read in beside the netlist differs by reference, ordering code or fitting state."""
    bom = lint.db.get('bom')
    if not isinstance(bom, dict) or not bom.get('parts'):
        return
    fitted_missing = [ref for ref in bom.get('not_in_bom') or [] if _fitted(lint, ref) and lint.graph.kind(ref) not in (pw.TESTPOINT, pw.JUMPER)
                      and not pw.mechanical_part(lint.parts.get(ref, {})) and not pw.board_copper(ref, lint.parts.get(ref, {}))]
    if fitted_missing:
        lint.add('DOC-A05', '原理图与 BOM 不一致', 'BOM 漏列图上贴装件：%s（G02-037）' % '、'.join(fitted_missing), fitted_missing[0], kind='CANDIDATE')
    extra = [ref for ref in bom.get('not_in_netlist') or [] if re.fullmatch(r'[A-Za-z]+\d+', str(ref))]   # REF**, G***: PCB graphics in a PCB BOM
    if extra:
        lint.add('DOC-A05', '原理图与 BOM 不一致', 'BOM 列了图上没有的位号：%s（G02-037）' % '、'.join(extra), extra[0], kind='CANDIDATE')
    differ = []
    for ref, columns in sorted(bom['parts'].items()):
        fields = {str(k).strip().upper(): str(v).strip() for k, v in (lint.parts.get(ref, {}).get('fields') or {}).items()}
        for column, written in sorted(columns.items()):
            name = str(column).strip().upper()
            if (ORDERING_FIELD_RE.match(name) and fields.get(name) and str(written).strip()
                    and re.sub(r'\W', '', str(written).upper()) != re.sub(r'\W', '', fields[name].upper())):
                differ.append('%s（图上 %s，BOM %s）' % (ref, fields[name], str(written).strip()))
                break
    if differ:
        lint.add('DOC-A05', '原理图与 BOM 不一致', '同一列 BOM 与图上料号不同：%s（G02-037）' % '、'.join(differ), differ[0].partition('（')[0], kind='CANDIDATE')


# --- G03: power --------------------------------------------------------------------------------------------------
def ldo_input_not_above_output(lint):
    """PWR-A09 (G03-034): a linear regulator whose input rail reads no higher than its output rail cannot regulate."""
    for ref, part in sorted(lint.parts.items()):
        if not _fitted(lint, ref) or lint.graph.kind(ref) != pw.IC or not LDO_RE.search(_text(part)):
            continue
        inputs = {_net(lint, n) for n in _nodes(lint, ref) if _pin_match(lint, n, REGULATOR_IN_RE)} - {None}
        outputs = {_net(lint, n) for n in _nodes(lint, ref) if _pin_match(lint, n, REGULATOR_OUT_RE)} - {None}
        if len(inputs) != 1 or len(outputs) != 1 or inputs == outputs:
            continue
        net_in, net_out = inputs.pop(), outputs.pop()
        volts_in, volts_out = _volts(lint, net_in)[0], _volts(lint, net_out)[0]
        if volts_in is not None and volts_out is not None and volts_in <= volts_out:
            lint.add('PWR-A09', 'LDO 输入轨不高于输出轨',
                     '%s: 输入 %s（%g V）不高于输出 %s（%g V），压差为 %g V，出不了调整区（G03-034）；轨压按网名或声明读取，改轨名或接线后关闭，'
                     '最低输入与保证压差归 PWR-E02' % (ref, net_in, volts_in, net_out, volts_out, volts_in - volts_out), ref, kind='CANDIDATE')


def _polarity_nets(lint, ref):
    """(net of +, net of -) of a polarized capacitor, by pin names or KiCad's pin 1 convention; None when unread."""
    part = lint.parts[ref]
    if not pw.is_polarized_capacitor(_text(part)):
        return None
    plus, minus = None, None
    for node in _nodes(lint, ref):
        name = str(lint.graph.pinname.get(node) or '').strip().upper()
        if name in ('+', 'P', 'POS'):
            plus = _net(lint, node)
        elif name in ('-', 'N', 'NEG'):
            minus = _net(lint, node)
    if plus is None and minus is None and set(lint.graph.pins_of(ref)) == {'1', '2'}:
        pins = lint.graph.pins_of(ref)
        plus, minus = pins['1'], pins['2']
    return (plus, minus) if plus and minus else None


def series_electrolytics(lint):
    """PWR-A10 (G03-040): two polarized capacitors in series across a voltage with no balancing resistors at the midpoint."""
    tops = {}
    for ref in sorted(lint.parts):
        if _fitted(lint, ref) and lint.graph.kind(ref) == pw.CAPACITOR:
            nets = _polarity_nets(lint, ref)
            if nets:
                tops[ref] = nets
    for upper, (u_plus, u_minus) in sorted(tops.items()):
        for lower, (l_plus, l_minus) in sorted(tops.items()):
            if upper == lower or u_minus != l_plus or is_ground(u_minus) or u_plus == l_minus:
                continue
            refs_on_mid = {node.partition('.')[0] for node in lint.nets.get(u_minus, [])}
            if refs_on_mid - {upper, lower} - {r for r in refs_on_mid if lint.graph.kind(r) == pw.RESISTOR}:
                continue   # something else hangs on the midpoint: a split-supply node or a driven node
            resistors = {r for r in refs_on_mid if lint.graph.kind(r) == pw.RESISTOR}
            reach = {other for r in resistors for other in lint.graph.nets_of(r) if other != u_minus}
            if u_plus in reach and l_minus in reach:
                continue
            lint.add('PWR-A10', '串联电解电容无均压',
                     '%s、%s 串联跨 %s/%s，中点 %s 没有到两端的均压电阻（G03-040）；均压后每只的电压在降额内才关闭' % (upper, lower, u_plus, l_minus, u_minus),
                     upper, kind='CANDIDATE')


def soft_dielectric_decoupling(lint):
    """PWR-A11 (G03-036): a Y5V/Z5U capacitor is the decoupling on a rail that feeds an IC supply pin."""
    for ref, part in sorted(lint.parts.items()):
        if not _fitted(lint, ref) or lint.graph.kind(ref) != pw.CAPACITOR:
            continue
        said = [str(part.get('value') or '')] + [str(v) for k, v in (part.get('fields') or {}).items() if SPEC_FIELD_RE.match(str(k).strip())]
        said += [str(v) for k, v in (((lint.db.get('bom') or {}).get('parts') or {}).get(ref) or {}).items() if SPEC_FIELD_RE.match(str(k).strip())]
        if not any(SOFT_DIELECTRIC_RE.search(text) for text in said):
            continue
        nets = lint.graph.nets_of(ref)
        grounds = [net for net in nets if is_ground(net)]
        rails = [net for net in nets if not is_ground(net)]
        if len(grounds) != 1 or len(rails) != 1:
            continue
        fed = [node for node in lint.graph.nodes_on(rails[0]) if lint.graph.kind(node.partition('.')[0]) == pw.IC
               and _pin_match(lint, node, SUPPLY_PIN_RE)]
        if fed:
            lint.add('PWR-A11', '去耦电容用 Y5V 类介质',
                     '%s (%s): 接 %s 的 IC 电源脚 %s；Y5V/Z5U 随偏压与温度丢失大部分容量，高频去耦用 C0G、X7R 类（G03-036）；旁路另有稳定介质且本颗不算有效值时关闭' % (
                         ref, part.get('value'), rails[0], '、'.join(fed[:3])), ref, kind='CANDIDATE')


# --- G05: protection ---------------------------------------------------------------------------------------------
def _standoff(part):
    """(VRWM, how) of a clamp by exact table or a family whose number is VRWM; (None, '') otherwise."""
    data = protective_clamps.clamp_data(part)
    if data:
        return data[1], data[4]
    for field in (part.get('part'), part.get('value')):
        match = VRWM_FAMILY_RE.search(str(field or ''))
        if match:
            return float(match.group(1)), '型号解码（SMxJ 数字即 VRWM）'
        match = VRWM_PESD_RE.search(str(field or ''))
        if match:
            return float(match.group(1)) + float(match.group(2)) / 10, '型号解码（PESD 电压段即 VRWM）'
    return None, ''


def _clamp_channels(lint):
    for ref, part in sorted(lint.parts.items()):
        if _fitted(lint, ref) and lint.graph.kind(ref) == pw.TVS:
            for channel in protective_clamps.channels(ref, part, lint.graph, lint.intent):
                yield ref, part, channel


def tvs_standoff(lint):
    """PRO-A07 (G05-030): the clamp's stand-off is below the voltage the net normally carries."""
    for ref, part, channel in _clamp_channels(lint):
        vrwm, how = _standoff(part)
        if vrwm is None:
            continue
        for net in channel['nets']:
            voltage, source = _volts(lint, net)
            if voltage is not None and vrwm < voltage:
                lint.add('PRO-A07', 'TVS 工作电压低于被钳网',
                         '%s (%s): VRWM %g V（%s）< %s %g V（%s），正常工作即漏电或导通（G05-030）；按手册 VRWM 与该网最高工作电压复核' % (
                             ref, part.get('value'), vrwm, how, net, voltage, source), ref, kind='CANDIDATE')


def fuse_voltage(lint):
    """PRO-A08 (G05-045, G05-051): a fuse or PPTC whose written voltage is below the rail it interrupts."""
    for ref, part in sorted(lint.parts.items()):
        if not _fitted(lint, ref) or lint.graph.kind(ref) != pw.FUSE:
            continue
        rated = rated_voltage(part.get('value'))
        if rated is None:
            match = FUSE_DC_RATING_RE.search(str(part.get('value') or ''))   # 4A/T/125VDC
            rated = float(match.group(1)) if match else None
        if rated is None:
            continue
        for net in lint.graph.nets_of(ref):
            voltage, source = _volts(lint, net)
            if voltage is not None and rated < voltage:
                lint.add('PRO-A08', '熔断器或 PPTC 额定电压低于回路电压',
                         '%s (%s): 额定 %g V < %s %g V（%s）；分断或动作时不保证灭弧（G05-045、G05-051），AC 额定不能直接用于 DC，按手册复核' % (
                             ref, part.get('value'), rated, net, voltage, source), ref, kind='CANDIDATE')
                break


def clamp_above_pin_maximum(lint):
    """PRO-A09 (G05-031): at its rated point an exactly tabled clamp exceeds the maximum of an exactly tabled pin on its net."""
    for ref, part, channel in _clamp_channels(lint):
        data = protective_clamps.clamp_data(part)
        if not data:
            continue
        wave, ipp, vcl = sorted(data[3], key=lambda point: point[1])[-1]
        for net in channel['nets']:
            for node in lint.graph.nodes_on(net):
                owner = node.partition('.')[0]
                if owner == ref or lint.graph.kind(owner) != pw.IC or not _fitted(lint, owner):
                    continue
                limit = protective_clamps.pin_maximum(lint.parts[owner], _names(lint, node))
                if limit and vcl > limit[0]:
                    lint.add('PRO-A09', 'TVS 钳位电压超过同网 IC 脚绝限',
                             '%s (%s): 额定点 VC %g V @ %g A（%s，%s）> %s 绝限 %g V（%s），两者同网无串联阻抗；'
                             '按需求的浪涌电流定界，低于额定点的电流钳位更低，到不了绝限时可关闭（G05-031）' % (
                                 ref, part.get('value'), vcl, ipp, wave, data[4], node, limit[0], limit[1]), ref, kind='CANDIDATE')


def _entry_nets(lint, net):
    """The nets a connector contact reaches this net by: itself or through fuses, ferrites, inductors and chokes."""
    return lint.graph.series_path(net, {pw.FUSE, pw.FERRITE, pw.INDUCTOR}, max_hops=2)


def _on_connector(lint, nets):
    out = set()
    for net in nets:
        for node in lint.graph.nodes_on(net):
            ref = node.partition('.')[0]
            if lint.graph.kind(ref) == pw.CONNECTOR and _fitted(lint, ref) and not pw.usb_connector_type(lint.parts.get(ref, {})):
                out.add(ref)
    return out


def _series_blockers(lint, net):
    """Reverse-blocking elements entered from this net: a diode's anode, a P-channel drain, a reverse controller's input."""
    found = []
    for node in lint.graph.nodes_on(net):
        ref = node.partition('.')[0]
        if not _fitted(lint, ref):
            continue
        kind, part = lint.graph.kind(ref), lint.parts[ref]
        if kind == pw.DIODE and lint.graph.role(node) == 'anode':
            cathode = lint.graph.node_named(ref, 'cathode')
            far = lint.pin2net.get(cathode) if cathode else None
            if far and far != net and not is_ground(far):
                found.append(ref)
        elif kind == pw.MOSFET and PMOS_WORD_RE.search(_text(part)) and lint.graph.role(node) == 'drain':
            found.append(ref)
        elif (kind == pw.IC and any(REVERSE_CONTROLLER_RE.match(str(part.get(k) or '')) for k in ('part', 'value'))
              and _pin_match(lint, node, CONTROLLER_INPUT_RE)):   # resonare-lcc: a clamp at the LM74700 cathode is behind the block
            found.append(ref)
    return found


def unidirectional_before_block(lint):
    """PRO-A10 (G05-057): the input has a reverse block, and a unidirectional TVS sits ahead of it."""
    for ref, part, channel in _clamp_channels(lint):
        identity = next((str(part.get(k)) for k in ('part', 'value') if UNIDIRECTIONAL_RE.match(str(part.get(k) or ''))), None)
        if not identity or not all(is_ground(net) for net in channel['return_nets']):
            continue
        for net in channel['nets']:
            reach = _entry_nets(lint, net)
            ports = _on_connector(lint, reach)
            blockers = sorted({b for n in reach for b in _series_blockers(lint, n)})
            if ports and blockers:
                lint.add('PRO-A10', '单向 TVS 在反接阻断之前',
                         '%s (%s): 跨 %s，接连接器 %s，反接阻断 %s 在它之后；反接时 TVS 正向导通，把防反接变成短路（G05-057）。'
                         '放到阻断之后或换双向后关闭；需求不要求耐受反接、连接器有防呆的写明后关闭' % (
                             ref, identity, net, '、'.join(sorted(ports)), '、'.join(blockers)), ref, kind='CANDIDATE')


def _gate_tie(lint, ref, gate_net, source_net):
    """'ground' / 'rail' when the gate is held statically by a resistor, a direct tie or a gate-source zener and nothing
    drives it; None when anything else (an IC pin, a transistor, a connector) can drive it."""
    if is_ground(gate_net):
        return 'ground'
    if _named_rail(gate_net):
        return 'rail'
    tie = None
    for node in lint.graph.nodes_on(gate_net):
        owner = node.partition('.')[0]
        if owner == ref or not _fitted(lint, owner):
            continue
        kind = lint.graph.kind(owner)
        ends = lint.graph.nets_of(owner)
        if kind == pw.RESISTOR and len(ends) == 2:
            far = next((net for net in ends if net != gate_net), None)
            if far is not None and is_ground(far):
                tie = tie or 'ground'
            elif far is not None and _named_rail(far):
                tie = tie or 'rail'
            elif far != source_net:
                return None
        elif kind not in (pw.ZENER, pw.CAPACITOR, pw.TVS):
            return None
    return tie


def reverse_fet_direction(lint):
    """PRO-A11 (G05-087): a statically gated series MOSFET at an input whose body diode conducts when the input is reversed."""
    for ref, part in sorted(lint.parts.items()):
        if not _fitted(lint, ref) or lint.graph.kind(ref) != pw.MOSFET:
            continue
        text = _text(part)
        pmos, nmos = bool(PMOS_WORD_RE.search(text)), bool(NMOS_WORD_RE.search(text))
        nodes = {role: lint.graph.node_named(ref, role) for role in ('gate', 'drain', 'source')}
        if pmos == nmos or not all(nodes.values()):
            continue
        gate, drain, source = (lint.pin2net.get(nodes[role]) for role in ('gate', 'drain', 'source'))
        if None in (gate, drain, source) or drain == source:
            continue
        tie = _gate_tie(lint, ref, gate, source)
        if pmos and tie == 'ground' and not is_ground(source) and not is_ground(drain) and _on_connector(lint, _entry_nets(lint, source)):
            lint.add('PRO-A11', '防反接 MOSFET 体二极管方向接反',
                     '%s (P 沟道): 栅极静态接地，源极在连接器 %s 一侧、漏极 %s 接负载；反接时体二极管导通，保护不起作用。'
                     '防反接应漏极朝输入、源极朝负载（G05-087）；另有控制用途的写明后关闭' % (ref, '、'.join(sorted(_on_connector(lint, _entry_nets(lint, source)))), drain),
                     ref, kind='CANDIDATE')
        elif nmos and tie == 'rail' and is_ground(drain) and not is_ground(source) and _on_connector(lint, _entry_nets(lint, source)):
            lint.add('PRO-A11', '防反接 MOSFET 体二极管方向接反',
                     '%s (N 沟道): 栅极静态接正轨，漏极在地 %s、源极接连接器回线 %s；反接时体二极管导通，保护不起作用。'
                     '防反接应漏极朝回线、源极朝地（G05-087）；另有控制用途的写明后关闭' % (ref, drain, source), ref, kind='CANDIDATE')


def _static_net(lint, net):
    """A net nothing drives: a rail or ground by name, or held by a resistor to one with no active pin on it."""
    if net is None or net in lint.pseudo:
        return False
    if is_ground(net) or _named_rail(net):
        return True
    held = False
    for node in lint.graph.nodes_on(net):
        owner = node.partition('.')[0]
        kind = lint.graph.kind(owner)
        if kind in (pw.CAPACITOR,):
            continue
        if kind == pw.RESISTOR:
            held = held or any(is_ground(o) or _named_rail(o) for o in lint.graph.nets_of(owner) if o != net)
            continue
        if str(lint.pintype.get(node, '')).upper() in ('IN', 'INPUT'):
            continue
        return False
    return held


def latch_without_reset(lint):
    """PRO-A12 (G05-060): a status-pin latch whose opposite asynchronous input and clock are static: only a power cycle clears it."""
    model = LatchModel(lint)
    for ref, unit, pins in model.latches:
        for key, other in (('PRE', 'CLR'), ('CLR', 'PRE')):
            node, opposite = pins.get(key), pins.get(other)
            if not node or not opposite:
                continue
            tree = model.tree(model.graph.pin2net.get(node))
            if tree[0] == 'LEAF':
                continue
            devices = sorted({n.partition('.')[0] for leaf in model.leaves(tree) for n in model.graph.nodes_on(leaf)
                              if _protection_status(model, n)})
            clock = pins.get('CLK') or pins.get('CK')
            if devices and _static_net(lint, model.graph.pin2net.get(opposite)) and (clock is None or _static_net(lint, clock)):
                lint.add('PRO-A12', '状态脚锁存没有复位路径',
                         '%s%s: %s 由 %s 的状态脚驱动，%s 与时钟都是静态电平，只有断电能清锁（G05-060）；'
                         '需求不要求远程复位的写明后按风险关闭' % (ref, unit, key, '、'.join(devices), other), ref, kind='CANDIDATE')


def indicator_pull_up_own_output(lint):
    """PRO-A13 (G05-064): a protection IC's open-drain status pulled up from the output that same IC cuts, with a receiver on it."""
    model = LatchModel(lint)
    for ref in sorted(lint.parts):
        if not _fitted(lint, ref) or lint.graph.kind(ref) != pw.IC:
            continue
        outputs = {_net(lint, n) for n in _nodes(lint, ref) if _pin_match(lint, n, LATCH_OUT_RE)} - {None}
        if not outputs:
            continue
        for node in _nodes(lint, ref):
            if not _protection_status(model, node):
                continue
            net = _net(lint, node)
            if net is None:
                continue
            pull = sorted(r for r, far in lint.graph.neighbors(net, {pw.RESISTOR}) if far in outputs)
            receivers = [n for n in lint.graph.nodes_on(net) if n != node and lint.graph.kind(n.partition('.')[0]) == pw.IC
                         and not outputs & set(lint.graph.nets_of(n.partition('.')[0]))]   # one fed from that output goes down with it
            if pull and receivers:
                lint.add('PRO-A13', '故障指示上拉取自被切断的输出',
                         '%s: 状态脚 %s 经 %s 上拉到自己的输出，接收 %s；通道切断后上拉失电，指示不再由上拉确定（G05-064）；'
                         '掉电本身就是指示的写明后关闭' % (ref, node, '、'.join(pull), '、'.join(receivers[:3])), ref, kind='CANDIDATE')


# --- G04: interfaces and analog ----------------------------------------------------------------------------------
def _data_pins(lint, ref):
    return [node for node in _nodes(lint, ref) if re.fullmatch(r'[AB]\d+', str(lint.graph.pinname.get(node) or ''), re.I)]


def auto_direction_shifter(lint):
    """SIG-A07 (G04-012, G04-013): a TXB-class shifter on an open-drain bus, or a data pull below its limit."""
    for ref, part in sorted(lint.parts.items()):
        if not _fitted(lint, ref) or lint.graph.kind(ref) != pw.IC or not AUTO_DIRECTION_RE.search(_text(part)):
            continue
        for node in _data_pins(lint, ref):
            net = _net(lint, node)
            if net is None:
                continue
            spi = any(_pin_match(lint, other, SPI_PIN_RE) for other in lint.graph.nodes_on(net) if other != node)
            if OPEN_DRAIN_NET_RE.search(str(net)) and not spi:
                lint.add('SIG-A07', '推挽自动方向转换器用在开漏总线或上下拉过小',
                         '%s.%s 接开漏总线网 %s：TXB 类只转换推挽信号，开漏总线改用 TXS 类或 FET 转换（G04-012）' % (ref, lint.graph.pinname.get(node), net), ref, kind='CANDIDATE')
                continue
            for resistor, far in lint.graph.neighbors(net, {pw.RESISTOR}):
                value = parse_resistor(lint.parts[resistor].get('value'))
                if value and 0 < value['kohm'] < TXB_PULL_MIN_KOHM and (is_ground(far) or _named_rail(far)):
                    lint.add('SIG-A07', '推挽自动方向转换器用在开漏总线或上下拉过小',
                             '%s.%s 的 %s 经 %s (%s) 接 %s，低于 50 kΩ 会让输出单稳与弱驱动拉不动（G04-013）；按型号手册的上下拉限制核' % (
                                 ref, lint.graph.pinname.get(node), net, resistor, lint.parts[resistor].get('value'), far), ref, kind='CANDIDATE')


def type_c_cc(lint):
    """SIG-A08 (G04-104): resistor-declared Type-C CC pins shared, floating or with an Rd out of value. A CC controller answers for its own."""
    for ref, part in sorted(lint.parts.items()):
        if not _fitted(lint, ref) or pw.usb_connector_type(part) != 'Type-C':
            continue
        pins = {}
        for node in _nodes(lint, ref):
            match = next((m for m in (CC_PIN_RE.match(n) for n in _names(lint, node)) if m), None)
            if match:
                pins[match.group(1)] = node
        if set(pins) != {'1', '2'}:
            continue
        nets = {key: lint.pin2net.get(node) for key, node in pins.items()}
        real = {key: net if net not in lint.pseudo else None for key, net in nets.items()}
        if any(real[key] and any(n.partition('.')[0] != ref and lint.graph.kind(n.partition('.')[0]) not in (pw.RESISTOR, pw.CAPACITOR, pw.TVS, pw.TESTPOINT)
                                 for n in lint.graph.nodes_on(real[key])) for key in real):
            continue   # a controller or a module answers for its CC pins
        if real['1'] and real['1'] == real['2']:
            lint.add('SIG-A08', 'Type-C CC 端接不符合角色',
                     '%s: CC1、CC2 同在 %s，两 CC 共用一只电阻，翻转与线缆检测失效；各接一只 Rd/Rp（G04-104）' % (ref, real['1']), ref, kind='FINDING')
            continue
        for key in sorted(real):
            net = real[key]
            links = lint.graph.neighbors(net, {pw.RESISTOR}) if net else []
            if not net or len(lint.nets.get(net, [])) < 2 or not links:
                lint.add('SIG-A08', 'Type-C CC 端接不符合角色',
                         '%s: CC%s 悬空或没有电阻（%s），端口不声明角色，Source 不给 VBUS（G04-104）；只有 USB2 适配线的旧口按接口说明关闭' % (ref, key, nets[key]), ref, kind='CANDIDATE')
                continue
            for resistor, far in links:
                value = parse_resistor(lint.parts[resistor].get('value'))
                if is_ground(far) and value and not RD_MIN_KOHM <= value['kohm'] <= RD_MAX_KOHM:
                    lint.add('SIG-A08', 'Type-C CC 端接不符合角色',
                             '%s: CC%s 的下拉 %s = %s，超出 Rd 5.1 kΩ ±20%%（G04-104）' % (ref, key, resistor, lint.parts[resistor].get('value')), ref, kind='CANDIDATE')


def _rs485_transceivers(lint):
    """(ref, {A/B/DE/... nodes}) of ICs with DE and a bus pair: a pin signature, not a family list."""
    for ref in sorted(lint.parts):
        if not _fitted(lint, ref) or lint.graph.kind(ref) != pw.IC:
            continue
        names = {}
        for node in _nodes(lint, ref):
            for name in _names(lint, node):
                upper = name.upper()
                if upper in ('A', 'B', 'DE', 'RE', 'RO', 'R', 'DI', 'D', 'Y', 'Z'):
                    names[upper] = node
        if {'A', 'B', 'DE'} <= set(names) and {'RO', 'R'} & set(names) and {'DI', 'D'} & set(names):
            yield ref, names


def _active_pin_on(lint, net, excluding):
    return [node for node in lint.graph.nodes_on(net) if node != excluding and _fitted(lint, node.partition('.')[0])
            and (lint.graph.kind(node.partition('.')[0]) not in (pw.RESISTOR, pw.CAPACITOR, pw.TESTPOINT, pw.TVS, pw.ZENER)
                 or len(lint.graph.nets_of(node.partition('.')[0])) > 2)]   # a connector, a module, a resistor pack can drive it


def rs485_driver_enable(lint):
    """SIG-A09 (G04-030, G04-066): DE floating, fixed or pulled active; driven with no pull-down is a human call on the IC's default."""
    for ref, names in _rs485_transceivers(lint):
        node = names['DE']
        net = lint.pin2net.get(node)
        if net is None or net in lint.pseudo or len(lint.nets.get(net, [])) < 2:
            lint.add('SIG-A09', 'RS-485 DE 默认可能占用总线', '%s: DE 脚 %s 悬空，上电默认状态未定，可能占用多点总线（G04-030）；手册写明内部下拉的按手册关闭' % (ref, node), ref, kind='CANDIDATE')
            continue
        if _named_rail(net):
            lint.add('SIG-A09', 'RS-485 DE 默认可能占用总线', '%s: DE 脚 %s 直接接 %s，驱动器固定有效；半双工多点总线不能关断（G04-066），点对点全双工写明后关闭' % (ref, node, net), ref, kind='CANDIDATE')
            continue
        if is_ground(net):
            continue
        downs = [r for r, far in lint.graph.neighbors(net, {pw.RESISTOR}) if is_ground(far)]
        ups = [r for r, far in lint.graph.neighbors(net, {pw.RESISTOR}) if _named_rail(far)]
        through = [peer for peer in lint.graph.signal_source_peers(net) if peer != net]   # a GPIO behind a series resistor drives it too
        drivers = [n for peer in [net] + through for n in _active_pin_on(lint, peer, node)]
        others = [n for n in drivers if n.partition('.')[0] != ref]
        if any(lint.graph.kind(n.partition('.')[0]) == pw.RESISTOR or RESISTOR_PACK_RE.search(_text(lint.parts[n.partition('.')[0]])) for n in others):
            continue   # a resistor pack hides what the net is pulled to
        if ups and not downs:
            lint.add('SIG-A09', 'RS-485 DE 默认可能占用总线', '%s: DE 网 %s 经 %s 上拉，复位期间驱动器默认有效，占用多点总线（G04-030）；改下拉' % (ref, net, '、'.join(ups)), ref, kind='CANDIDATE')
        elif not downs and not others:
            lint.add('SIG-A09', 'RS-485 DE 默认可能占用总线', '%s: DE 网 %s 没有驱动也没有下拉（G04-030）' % (ref, net), ref, kind='CANDIDATE')
        elif not downs:
            lint.add('SIG-A09', 'RS-485 DE 默认可能占用总线',
                     '%s: DE 网 %s 由 %s 驱动，没有下拉；控制器复位期间引脚高阻时 DE 的默认态取决于手册内部下拉，需人判（G04-030）' % (ref, net, '、'.join(others[:3])),
                     ref, kind='CANDIDATE', needs_human=['RS-485 DE 复位期间默认态'])


def i2c_same_address(lint):
    """SIG-A10 (G04-023): two ICs of one exact model on one bus segment with nothing strapped differently between them."""
    from board_scans import _i2c_segment, _is_i2c_net
    done = set()
    for net in sorted(lint.nets):
        if net in lint.pseudo or net in done or not _is_i2c_net(net) or 'SDA' not in str(net).upper():
            continue
        segment = _i2c_segment(lint, net)
        done |= segment
        by_model = {}
        for member in segment:
            for node in lint.graph.nodes_on(member):
                ref = node.partition('.')[0]
                if lint.graph.kind(ref) == pw.IC and _fitted(lint, ref) and any(n.upper().startswith('SDA') for n in _names(lint, node)):
                    model = str(_ordering_code(lint.parts[ref]) or lint.parts[ref].get('value') or '').upper()
                    if MODEL_RE.match(model):
                        by_model.setdefault(model, set()).add(ref)
        for model, refs in sorted(by_model.items()):
            refs = sorted(refs)
            for index, first in enumerate(refs):
                for second in refs[index + 1:]:
                    if _strapped_alike(lint, first, second):
                        lint.add('SIG-A10', 'I²C 同型号同地址配置',
                                 '%s、%s (%s) 在 %s 同一总线段，地址配置脚的接法没有差别（G04-023）；手册缺地址的记资料不足，不同出厂地址后缀的按料号关闭' % (first, second, model, net),
                                 first, kind='CANDIDATE')


def _strapped_alike(lint, first, second):
    """False as soon as a pin differs in a way that can set an address: a static strap, or a pin named like an address."""
    one, other = lint.graph.pins_of(first), lint.graph.pins_of(second)
    if set(one) != set(other):
        return False
    for pin in one:
        a, b = one[pin], other[pin]
        if a == b:
            continue
        node = first + '.' + pin
        name_hits = any(re.fullmatch(r'(?:[AE]\d?|AD\d?|ADD\d?|ADDR\d?|SA\d?|ASEL|AS|ALT|SDO)', n, re.I) for n in _names(lint, node))
        static = any(is_ground(n) or _named_rail(n) or lint.graph.neighbors(n, {pw.RESISTOR}) for n in (a, b) if n)
        if name_hits or static:
            return False
    return True


def rs485_tvs_range(lint):
    """SIG-A11 (G04-025): a clamp on an RS-485 bus line whose stand-off narrows the common-mode range."""
    bus = {}
    for ref, names in _rs485_transceivers(lint):
        for key in ('A', 'B'):
            net = _net(lint, names[key])
            if net:
                for member in lint.graph.series_path(net, {pw.RESISTOR, pw.FERRITE, pw.COMMON_MODE_CHOKE}, max_hops=1):
                    bus[member] = ref
    for ref, part, channel in _clamp_channels(lint):
        vrwm, how = _standoff(part)
        if vrwm is None or vrwm >= RS485_COMMON_MODE_V:
            continue
        for net in channel['nets']:
            if net in bus:
                lint.add('SIG-A11', 'RS-485 总线 TVS 窄于共模范围',
                         '%s (%s): 接 %s 总线 %s，VRWM %g V（%s）< 12 V，缩小 −7…+12 V 共模范围（G04-025）；按需求的地电位差复核，非对称型（如 SM712）按手册' % (
                             ref, part.get('value'), bus[net], net, vrwm, how), ref, kind='CANDIDATE')
                break


def split_termination(lint):
    """SIG-A12 (G04-064, G04-076): the two resistors of a split termination differ, or one writes a wide tolerance."""
    pairs = []
    for ref in sorted(lint.parts):
        if not _fitted(lint, ref) or lint.graph.kind(ref) != pw.IC:
            continue
        can = {}
        for node in _nodes(lint, ref):
            match = next((m for m in (CAN_PIN_RE.match(n) for n in _names(lint, node)) if m), None)
            if match:
                can[match.group(1).upper()] = _net(lint, node)
        if can.get('H') and can.get('L'):
            pairs.append((ref, can['H'], can['L'], 'G04-076'))
    for ref, names in _rs485_transceivers(lint):
        high, low = _net(lint, names['A']), _net(lint, names['B'])
        if high and low:
            pairs.append((ref, high, low, 'G04-064'))
    for ref, high, low, criterion in pairs:
        for r_high, mid in lint.graph.neighbors(high, {pw.RESISTOR}):
            for r_low, far in lint.graph.neighbors(low, {pw.RESISTOR}):
                if far != mid or r_high == r_low or is_ground(mid) or _named_rail(mid):
                    continue
                if not any(is_ground(other) for _, other in lint.graph.neighbors(mid, {pw.CAPACITOR})):
                    continue
                values = [str(lint.parts[r].get('value') or '') for r in (r_high, r_low)]
                parsed = [parse_resistor(v) for v in values]
                tolerances = [float(m.group(1)) for m in (re.search(r'(\d+(?:\.\d+)?)\s*%', v) for v in values) if m]
                if all(parsed) and abs(parsed[0]['kohm'] - parsed[1]['kohm']) > 0.001 * parsed[0]['kohm']:
                    words = '两只电阻 %s=%s、%s=%s 不相等' % (r_high, values[0], r_low, values[1])
                elif tolerances and max(tolerances) >= 5:
                    words = '%s、%s 写明容差 %g%%，明显宽于 1%%' % (r_high, r_low, max(tolerances))
                else:
                    continue
                lint.add('SIG-A12', '分裂端接电阻不匹配',
                         '%s: %s/%s 分裂端接中点 %s，%s，共模噪声转成差模（%s）' % (ref, high, low, mid, words, criterion), ref, kind='CANDIDATE')


# KiCad's Amplifier_Operational units name inputs + and - and leave the output unnamed: the industry pinouts pair them,
# used only when the pin names at those numbers confirm the signs.
OPAMP_LAYOUTS = {8: (('1', '3', '2'), ('7', '5', '6')),
                 14: (('1', '3', '2'), ('7', '5', '6'), ('8', '10', '9'), ('14', '12', '13'))}


def _opamp_inputs(lint, ref):
    """Every input pin an amplifier's names show: [(sign, node)]."""
    found = []
    for node in _nodes(lint, ref):
        for name in _names(lint, node):
            match = OPAMP_INPUT_RE.match(name)
            if match:
                found.append((next(g for g in match.groups() if g and g in '+-'), node))
                break
    return found


def _opamp_pins(lint, ref):
    """{unit: {'+': node, '-': node, 'out': node}} by pin names, the industry pinout, or a lone output; {} when unread."""
    units = {}
    for sign, node in _opamp_inputs(lint, ref):
        name = str(lint.graph.pinname.get(node) or '')
        unit = re.sub(r'[+-]|IN|_', '', name.upper()) or None
        units.setdefault(unit, {}).setdefault(sign, []).append(node)
    outputs = {}
    for node in _nodes(lint, ref):
        for name in _names(lint, node):
            match = OPAMP_OUTPUT_RE.match(name)
            if match:
                outputs[(match.group(1) or match.group(2) or '').upper() or None] = node
                break
    named = {unit: {'+': pins['+'][0], '-': pins['-'][0], 'out': outputs[unit]} for unit, pins in units.items()
             if unit in outputs and len(pins.get('+', ())) == 1 and len(pins.get('-', ())) == 1}
    if named:
        return named
    pins = lint.graph.pins_of(ref)
    layout = OPAMP_LAYOUTS.get(len([p for p in pins if p.isdigit()]))
    if layout:
        paired = {}
        for index, (out, plus, minus) in enumerate(layout):
            nodes = {'+': ref + '.' + plus, '-': ref + '.' + minus, 'out': ref + '.' + out}
            if (str(lint.graph.pinname.get(nodes['+']) or '').strip() == '+' and str(lint.graph.pinname.get(nodes['-']) or '').strip() == '-'
                    and str(lint.graph.native_pintype.get(nodes['out']) or '').lower() == 'output'):
                paired[str(index)] = nodes
        if paired:
            return paired
    drives = [node for node in _nodes(lint, ref) if str(lint.graph.native_pintype.get(node) or '').lower() == 'output']
    signs = _opamp_inputs(lint, ref)
    if len(drives) == 1 and sorted(sign for sign, _ in signs) == ['+', '-']:
        return {'': dict({sign: node for sign, node in signs}, out=drives[0])}
    return {}


def _opamps(lint):
    for ref, part in sorted(lint.parts.items()):
        if (_fitted(lint, ref) and lint.graph.kind(ref) == pw.IC and OPAMP_RE.search(_text(part))
                and not NOT_VOLTAGE_AMP_RE.search(_text(part))):
            yield ref, _opamp_pins(lint, ref)


def _dc_reach_from_pin(lint, node):
    """The island seen from an amplifier input, the pin itself not counting as a DC path."""
    net = _net(lint, node)
    if net is None:
        return False, True
    seen, queue, capacitor = {net}, [net], False
    while queue:
        current = queue.pop()
        if is_ground(current) or _named_rail(current):
            return capacitor, True
        for other in lint.graph.nodes_on(current):
            if other == node:
                continue
            owner = other.partition('.')[0]
            if not _fitted(lint, owner):
                continue
            kind = lint.graph.kind(owner)
            if kind == pw.CAPACITOR:
                capacitor = True
            elif kind in (pw.RESISTOR, pw.INDUCTOR, pw.FERRITE, pw.JUMPER):
                for far in lint.graph.nets_of(owner):
                    if far not in seen and far not in lint.pseudo:
                        seen.add(far)
                        queue.append(far)
            else:
                return capacitor, True
    return capacitor, False


def opamp_input_no_dc(lint):
    """ANA-A01 (G04-048): an amplifier input that reaches only capacitors: its bias current has no path."""
    for ref, _ in _opamps(lint):
        for sign, node in _opamp_inputs(lint, ref):
            capacitor, path = _dc_reach_from_pin(lint, node)
            if capacitor and not path:
                lint.add('ANA-A01', '运放输入没有直流通路',
                         '%s: 输入 %s 所在节点只经电容对外，偏置电流没有直流通路（G04-048）；加到偏置点的电阻，Ib 压降计入误差预算' % (ref, node), ref)


def _feedback_reach(lint, out_node, stop_refs):
    """Nets a signal from an amplifier output reaches through two-terminal parts, never across a rail or ground;
    also says whether a transistor or another amplifier is on the way (a composite stage this scan does not read)."""
    start = _net(lint, out_node)
    seen, queue, active = {start}, [start], False
    while queue:
        current = queue.pop()
        for node in lint.graph.nodes_on(current):
            owner = node.partition('.')[0]
            if not _fitted(lint, owner) or owner in stop_refs:
                continue
            kind = lint.graph.kind(owner)
            if kind in (pw.MOSFET, pw.BJT, pw.OPTO) or (kind == pw.IC and OPAMP_RE.search(_text(lint.parts[owner]))):
                active = True
            elif kind in (pw.RESISTOR, pw.CAPACITOR, pw.INDUCTOR, pw.FERRITE, pw.DIODE, pw.ZENER, pw.JUMPER):
                for far in lint.graph.nets_of(owner):
                    if far not in seen and far not in lint.pseudo and not is_ground(far) and not _named_rail(far):
                        seen.add(far)
                        queue.append(far)
    return seen, active


def opamp_open_loop(lint):
    """ANA-A02 (G04-049): no path from an amplifier's output back to either input of that amplifier."""
    for ref, units in _opamps(lint):
        for unit, pins in sorted(units.items(), key=lambda item: str(item[0])):
            out = _net(lint, pins['out'])
            inputs = {sign: _net(lint, pins[sign]) for sign in '+-'}
            if out is None or None in inputs.values() or len(lint.nets.get(out, [])) < 2:
                continue
            if out in inputs.values():
                continue
            reached, active = _feedback_reach(lint, pins['out'], {ref})
            if active or reached & set(inputs.values()):
                continue
            if any(is_ground(net) or _named_rail(net) for net in inputs.values()) and all(is_ground(net) or _named_rail(net) for net in inputs.values()):
                continue   # an unused unit parked on fixed levels
            lint.add('ANA-A02', '运放开环当比较器用',
                     '%s: 输出 %s 没有到本单元输入的反馈通路（G04-049）；比较功能宜用比较器，确需时核差分输入额定、饱和恢复与相位反转并写明理由' % (ref, pins['out']),
                     ref, kind='CANDIDATE')


def amplifier_above_adc(lint):
    """ANA-A03 (G04-054): an amplifier on a higher rail drives an ADC pin through nothing but series resistance."""
    for ref, units in _opamps(lint):
        supply = _supply_volts(lint, ref)
        if supply is None:
            continue
        for unit, pins in sorted(units.items(), key=lambda item: str(item[0])):
            out = _net(lint, pins['out'])
            if out is None:
                continue
            series = lint.graph.series_path(out, {pw.RESISTOR, pw.FERRITE}, max_hops=1)
            for member in series:
                if _named_rail(member) or is_ground(member):
                    continue
                for node in lint.graph.nodes_on(member):
                    owner = node.partition('.')[0]
                    if owner == ref or lint.graph.kind(owner) != pw.IC or not _fitted(lint, owner):
                        continue
                    if not any(ADC_PIN_RE.search(n) for n in _names(lint, node)):
                        continue
                    limit = _supply_volts(lint, owner)
                    if limit is None or supply <= limit:
                        continue
                    if _clamped_or_divided(lint, series, {ref, owner}):
                        continue
                    lint.add('ANA-A03', '运放电源高于 ADC 且无钳位',
                             '%s（电源 %g V）的输出 %s 经串阻到 %s（电源 %g V）；饱和或故障时超 ADC 绝限，路径上没有钳位或分压（G04-054）' % (ref, supply, pins['out'], node, limit),
                             ref, kind='CANDIDATE')


def _clamped_or_divided(lint, nets, owners):
    for net in nets:
        for node in lint.graph.nodes_on(net):
            owner = node.partition('.')[0]
            if owner in owners or not _fitted(lint, owner):
                continue
            kind = lint.graph.kind(owner)
            if kind in (pw.DIODE, pw.ZENER, pw.TVS):
                return True
            if kind == pw.RESISTOR and any(is_ground(far) or _named_rail(far) for far in lint.graph.nets_of(owner)):
                return True
    return False


def _single_rail_ic(lint, ref):
    return lint.graph.kind(ref) == pw.IC and _fitted(lint, ref) and _supply_volts(lint, ref)


def _push_pull_driver(lint, node):
    """A digital push-pull output by the symbol: not an amplifier or comparator (its level is not its supply; open-collector
    comparators are drawn as output), not on a net with a pull resistor to a rail (the mark of an open-drain)."""
    ref = node.partition('.')[0]
    if str(lint.graph.native_pintype.get(node) or '').lower() != 'output' or not _single_rail_ic(lint, ref):
        return False
    if OPAMP_RE.search(_text(lint.parts[ref])) or COMPARATOR_RE.search(_text(lint.parts[ref])) or lint.graph.role_kind(ref) == 'opamp_comparator':
        return False
    return not any(_named_rail(far) for _, far in lint.graph.neighbors(lint.pin2net.get(node), {pw.RESISTOR}))


def cross_domain_drive(lint):
    """SIG-A13 (G04-005): a push-pull output of one supply domain wired straight to a declared input of a lower one."""
    for net, nodes in sorted(lint.nets.items()):
        if net in lint.pseudo or _named_rail(net) or is_ground(net):
            continue
        drivers = [n for n in nodes if _push_pull_driver(lint, n)]
        inputs = [n for n in nodes if str(lint.graph.native_pintype.get(n) or '').lower() == 'input'
                  and _single_rail_ic(lint, n.partition('.')[0])]
        for driver in drivers:
            high = _supply_volts(lint, driver.partition('.')[0])
            for receiver in inputs:
                low = _supply_volts(lint, receiver.partition('.')[0])
                if receiver.partition('.')[0] != driver.partition('.')[0] and high >= low + LOGIC_LEVEL_GAP_V:
                    lint.add('SIG-A13', '跨电源域输出直连低压输入',
                             '%s（%g V 域）直连 %s（%g V 域），网 %s 上没有转换或限流（G04-005）；接收脚手册容许此电压（如 5 V 耐受）时关闭' % (driver, high, receiver, low, net),
                             receiver.partition('.')[0], kind='CANDIDATE')


def can_rxd_level(lint):
    """SIG-A13 (G04-033): a CAN transceiver with no VIO pin, on 5 V, its RXD straight to an IC of a lower supply."""
    for ref in sorted(lint.parts):
        if not _fitted(lint, ref) or lint.graph.kind(ref) != pw.IC:
            continue
        names = {name.upper(): node for node in _nodes(lint, ref) for name in _names(lint, node)}
        if not ({'CANH', 'CANL', 'RXD'} <= set(names) or {'CANH', 'CANL', 'R'} <= set(names)) or 'VIO' in names or 'VCCIO' in names:
            continue
        supply = _supply_volts(lint, ref)
        rxd = names.get('RXD') or names.get('R')
        net = _net(lint, rxd)
        if supply is None or supply < 4.5 or net is None:
            continue
        for node in lint.graph.nodes_on(net):
            owner = node.partition('.')[0]
            low = _supply_volts(lint, owner) if owner != ref and lint.graph.kind(owner) == pw.IC and _fitted(lint, owner) else None
            if low is not None and low < supply - LOGIC_LEVEL_GAP_V:
                lint.add('SIG-A13', '跨电源域输出直连低压输入',
                         '%s（无 VIO，%g V）RXD 直连 %s（%g V 域）；RXD 高电平到 VCC，接收脚不耐压时判不成立（G04-033）；手册写明 5 V 耐受或收发器实际为 3.3 V 输出时关闭' % (ref, supply, node, low),
                         ref, kind='CANDIDATE', needs_human=['接收脚 5 V 耐受'])


def ethernet_center_tap(lint):
    """SIG-A14 (G04-087): a named centre tap of an RJ45 or discrete magnetics floats or sits directly on signal ground."""
    for ref, part in sorted(lint.parts.items()):
        if not _fitted(lint, ref) or lint.graph.kind(ref) not in (pw.CONNECTOR, pw.TRANSFORMER) or not RJ45_RE.search(_text(part)):
            continue
        for node in _nodes(lint, ref):
            if not any(CT_PIN_RE.fullmatch(n) for n in _names(lint, node)):
                continue
            net = lint.pin2net.get(node)
            alone = net is None or net in lint.pseudo or (len(lint.nets.get(net, [])) < 2 and not is_ground(net))
            if alone or is_ground(net):
                lint.add('SIG-A14', '以太网中心抽头悬空或直接接地',
                         '%s: 中心抽头 %s %s（G04-087）；线缆侧应经 75 Ω 与高压电容到机壳，PHY 侧按所选 PHY 手册；集成磁件内部已端接的按其手册关闭' % (
                             ref, node, '悬空' if alone else '直接接 %s' % net), ref, kind='CANDIDATE')


def run(lint):
    placeholder_values(lint)
    identity_fields(lint)
    bom_schematic_sets(lint)
    ldo_input_not_above_output(lint)
    series_electrolytics(lint)
    soft_dielectric_decoupling(lint)
    tvs_standoff(lint)
    fuse_voltage(lint)
    clamp_above_pin_maximum(lint)
    unidirectional_before_block(lint)
    reverse_fet_direction(lint)
    latch_without_reset(lint)
    indicator_pull_up_own_output(lint)
    auto_direction_shifter(lint)
    type_c_cc(lint)
    rs485_driver_enable(lint)
    i2c_same_address(lint)
    rs485_tvs_range(lint)
    split_termination(lint)
    opamp_input_no_dc(lint)
    opamp_open_loop(lint)
    amplifier_above_adc(lint)
    cross_domain_drive(lint)
    can_rxd_level(lint)
    ethernet_center_tap(lint)

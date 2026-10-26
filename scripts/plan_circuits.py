#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""电路级与器件检查项（功能树设计 §3.8）：功能电路类型的发现与逐电路展开、电路功能框架、器件与引脚的保证值核对、
阈值窗口，以及每块电路对它拥有的器件问的应力、电容和精度。ReviewPlanner 混入这里的方法。"""
import re

import board_intent
import catalog
import circuit_decisions
import device_kinds
import row_owner
from audit_datasheets import datasheet_entry_for_ref
from checkers import powertree
from checkers.netgraph import RAIL_RE, NetGraph, is_analog_sense_pair, is_ground
from part_words import (BJT, BRIDGE_RECTIFIER, CAPACITOR, CONNECTOR, DIODE, FUSE, IC, INDUCTOR, MOSFET, OPTO,
                        PASSIVE_LINKS, RESISTOR, SWITCH, TESTPOINT, TRANSFORMER, TVS, UNKNOWN, ZENER, ELECTROLYTIC_RE,
                        LED_RE, NTC, NTC_RE, POLARIZED_SYMBOL_RE, TANTALUM_RE, VARISTOR, VARISTOR_RE, name_matches,
                        normalize)
from checkers.netgraph import is_ground as netgraph_ground
from checkers.planutil import slug as _slug
from electrical_contract import bounded, finite
from interfaces import CONNECTOR_RE
from page_inventory import LIMITED
from plan_board import _material_available, _text
import requirement_parameters
from solve_dividers import parse_resistor_noted

EN_RE = re.compile(
    r'(^|_)(EN|ENABLE|SHDN|SHUTDOWN|PWREN|PWR_EN)(_|\d|$)', re.I)

STRAP_RE = re.compile(
    r'(^|_)(BOOT\w*|STRAP\w*|TEST_MODE\w*|CFG\w*|CONFIG\w*|MODE\d*)(_|$)',
    re.I)

I2C_RE = re.compile(r'(^|_)(I2C\w*|SCL\d*|SDA\d*)(_|$)', re.I)

FB_NAMES = {'FB', 'ADJ', 'VFB', 'FBX', 'VSENSE', 'VOSNS', 'VOUT_SENSE'}

DEVICE_RE = re.compile(r'^[UM]\d', re.I)

# 保护门限脚与传感器只作发现线索：命中即生成计算项，不据名称判定门限或传感器类型。
PROTECT_PIN_RE = re.compile(
    r'^(FAULT\w*|FLT\w*|OVP\w*|UVP\w*|OV|UV|OVLO|UVLO|OCP\w*|OTP\w*|ILIM\w*|PROT\w*|TRIP\w*)$', re.I)

SENSOR_RE = re.compile(r'THERMISTOR|PTC|\bRTD\b|PT100|THERMOCOUPLE|热敏', re.I)   # with netgraph's NTC word

GROUND_PIN_RE = re.compile(r'^([A-Z]{0,2}GND[A-Z0-9]{0,3}|[AD]?VSS[A-Z0-9]{0,3}|EP|PAD)$', re.I)   # a pin name, not a net

# 阈值型保护两侧分别成项，避免只核一侧即通过。
WINDOW_SIDES = (
    ('NOTRIP', '不误动作侧：正常工况被测量最大值（全部输出档位、瞬态与上电/掉电、公差、温度、漏电，'
               '含峰值整流或滤波捕获的尖峰）低于门限最小值并留裕量，门限脚计入接收端内部钳位/上下拉的吸流；'
               '也可用有据的滤波/消隐及波形证明不形成有效触发'),
    ('TRIP', '动作有效侧：按受控故障及可接受终态核检测、执行、剩余能量和适用的保持/复位；正常及要求无损恢复的工况满足额定，允许破坏性安全失效的工况按其安全判据关闭'),
)

# 栅源稳压管/TVS 在正常驱动中允许限幅：不误动作侧改核“不妨碍规定导通”。
GATE_CLAMP_NOTRIP = ('不误动作侧（栅源限幅，正常驱动中允许钳位）：正常驱动窗口内钳位不妨碍所需导通栅压，'
                     '钳位电流与功耗（含驱动源限流）在器件额定内；不要求正常工作永不导通')

INTERFACE_MATERIALS = {'DEV-C04': ('datasheets', 'requirements')}

OWNED_PART_MATERIALS = {'DEV-C01': ('datasheets', 'requirements'), 'DEV-C02': ('datasheets', 'requirements'),
                        'DEV-C03': ('requirements',)}

# 逐电路自有器件的检查项取哪些器件（第 5 步）：应力不含连接器（载流归 DEV-C04）与测试点。
OWNED_PART_KINDS = {'DEV-C01': lambda kind: kind not in (CONNECTOR, TESTPOINT),
                    'DEV-C02': lambda kind: kind == CAPACITOR, 'DEV-C03': lambda kind: kind == RESISTOR}

def _database_blobs(db):
    blobs = []
    for net in db.get('nets', {}):
        blobs.append(f'NET:{net}')
    for node, pin in db.get('pinname', {}).items():
        blobs.append(f'PIN:{node}:{pin}')
    for ref, part in db.get('parts', {}).items():
        blobs.append('PART:' + ':'.join([
            ref, str(part.get('part', '')), str(part.get('value', '')),
            str(part.get('prim', '')), str(part.get('jedec', ''))]))
    return blobs

def _feature_hits(db, pattern):
    regex = re.compile(pattern, re.I)
    return sorted(blob for blob in _database_blobs(db) if regex.search(blob))[:12]

def _differential_pairs(db):
    nets = set(db.get('nets', {}))
    found = set()
    for net in sorted(nets):
        candidates = []
        if net.endswith('_P'):
            candidates.append(net[:-2] + '_N')
        if net.endswith('-P'):
            candidates.append(net[:-2] + '-N')
        if net.endswith('+'):
            candidates.append(net[:-1] + '-')
        if net.upper().endswith('_DP'):
            candidates.append(net[:-3] + '_DM')
        for other in candidates:
            if other in nets and not is_analog_sense_pair(net):
                found.add((net, other))
    return sorted(found)


# An electrolytic capacitor (the part a lifetime falls on) by its symbol (Device:C_Polarized, CP, CP_Small) or, 6c, by
# its BOM words (netgraph.ELECTROLYTIC_RE), or an aluminium package with a stated voltage holding at least 1 µF;
# tantalum is none.
ALUMINIUM_PACKAGE_RE = re.compile(r'(^|[:_])CP_|_Elec|Radial', re.I)
VOLTAGE_RE = re.compile(r'\d\s*V(\b|$)', re.I)
SUPERCAP_FARAD = 0.1
LIFE_CRITERION = ('%s；电解、固态与超级电容按此剖面估算所需耐久等级：厂家有寿命公式（含厂家通用技术说明）用公式，没有就按 10 °C '
                  '翻倍，两种都标估算（ESTIMATE）；写成 bom_constraint“耐久 ≥ X h @T（估算，热点 ≤ Y °C）”，热点温度和纹波自热'
                  '移交热设计实测后复算，不开厂家数据缺口（VENDOR_DATUM）%s')
LIFE_HANDOFF = {'required': True, 'state': 'OPEN', 'receivers': ['热设计'],
                'constraint': '电解电容热点温度不超过寿命约束写的 Y °C', 'verification': '样机热点与纹波自热实测后按同一剖面复算'}
WEAROUT_CRITERION = '%s %s（%s）：核%s；依据%s；%s'
WEAROUT_NA_CRITERION = '%s %s（%s）：需求与任务剖面都没给%s，按次数核的寿命记 NA（写明这一原因），不开缺口项；单次应力由各自的应力检查项核'
PTC_RE = re.compile(r'POLY ?FUSE|POLYSWITCH|PPTC|\bPTC\b|RESETTABLE|自恢复|MF-[A-Z]', re.I)
SWITCHLIKE_RE = re.compile(r'POTENTIOMETER|\bPOT\b|TRIM|ENCODER|电位器|编码器', re.I)
MEMORY_RE = re.compile(r'EEPROM|FLASH|\bFRAM\b|24(LC|AA|C)\d|25(LC|AA|Q)\d|W25Q|AT2[45]|M24C|M95', re.I)
# Parts whose identity, pin disposition and operating conditions get rows of their own: transistors, optocouplers,
# threshold and clamp diodes, bridge rectifiers and custom magnetics — the parts whose datasheet specifies an operating
# region the circuit rows do not cover. A plain diode or an ordinary inductor is a commodity part (commodity-floors.md)
# and gets no device rows, declared in intent.devices or not: the rows follow the verified device kind, never the
# declaration (R6 acceptance 2026-10-24, user: 按照 a; 7 declared diodes made 21 rows in two records of four).
# Verified kinds that make a part an active device with rows of its own whatever its refdes; two-terminal kinds
# (diode, zener, tvs, resistor, capacitor …) never do — the fixed kinds above cover the zener/TVS rows.
ACTIVE_VERIFIED_KINDS = tuple(board_intent.IC_KINDS) + ('opto', 'relay')
FIXED_DEVICE_KINDS = (MOSFET, BJT, OPTO, ZENER, TVS, TRANSFORMER)
BRIDGE_RE = re.compile(r'^(BR|DB)\d', re.I)
CUSTOM_PART_RE = re.compile(r'CUSTOM', re.I)
FEEDBACK_PIN_RE = re.compile(r'(V?FB|COMP|FEEDBACK)([/_-](V?FB|COMP))?', re.I)
FEEDBACK_OPEN_CRITERION = ('反馈环单一故障：光耦 %s 或它的串阻开路、副边控制失效时，%s 按开环送能；按控制器手册的保护检测延时'
                           '与开环最大送能，算到保护动作为止输出侧电压的上界，对照输出侧器件（输出电容、同步整流、端口开关、'
                           '副边控制器）的耐压；保护来得及时判 PASS，来不及时记失败项')

# Common single faults asked on netlist features (consistency proposals of 2026-10-23, item 7): each row only asks.
# A net holds charge when a capacitor of at least 1 µF ties it to ground: enough to mark a supply or a boost output.
# The candidate input walk stops at the first 10 µF instead (circuit_candidates.STORAGE_FARAD): there a 1 µF filter
# capacitor is still the input, the bulk capacitor ends it.
BULK_FARAD = 1e-6
# Pins that start or stop a controller: enable and its disable, inhibit and standby forms.
ENABLE_LINK_PIN_RE = re.compile(r'(^|_)(EN|ENABLE|SHDN|SHUTDOWN|PWREN|PWR_EN|DIS|DISABLE|INH|INHIBIT|STBY|STANDBY'
                                r'|ON_?OFF|RUN)(_|\d|$)', re.I)
PORT_SHORT_CRITERION = ('端口硬短路：%s 把 %s 接到连接器 %s；端口对地短路时，输出电容储能和变换器电流经它释放，按短路检测与关断'
                        '时间核它的 SOA 与 I²t，并核关断时的电压尖峰')
NTC_HOT_CRITERION = ('热态重接入：%s 限制输入浪涌；断电后 NTC 还没冷却就重新上电时，浪涌只受线路与器件阻抗限制，核整流桥 '
                     'IFSM/I²t、保险 I²t 与输入电容承受的浪涌')
RCD_CRITERION = ('RCD 钳位：%s 与 %s、%s 在开关节点上吸收漏感能量；电阻功率按 ½·Llk·Ipk²·fsw·Vc/(Vc−Vor) 核降额，电阻两端电压'
                 '（钳位电压减母线）对其耐压')
PIN_LED_CRITERION = ('%s 直接驱动 %s 的 LED：按该脚手册的电流限值核；手册没给限值时，厂家参考电路有同样接法且负载不更重可判通过，'
                     '手册写了这种用法但没给数值记缺厂家数据，手册没写这种用法记失败项（超出规定区）')
# The criterion names only the device and the group; the declaration's citation, allowed range, affected aspects and
# requirement ride on the row as `configuration` (R6 acceptance 2026-10-24: 7 CFG-D01 rows per pair unpaired on the
# reviewer's wording of them).
CONFIG_CRITERION = ('%s 的%s：配置值须落在手册允许范围内（出处、允许范围与这一组决定的方面见本检查项 configuration）、满足需求，并包含'
                    '硬件判定写下的设置（setting）；配置表未交付记 DELIVERABLE_PENDING（CONFIGURATION_TABLE）')
CONFIG_UNDECLARED_CRITERION = ('%s 的%s：先在 intent.devices.%s.configurable 按手册寄存器或配置章节写出处、允许范围和它决定的方面；'
                               '这一组对该器件不存在时本检查项记 NA 并引手册条款')
CONFIG_DECLARE_CRITERION = ('%s 是可编程器件（%s）：在 intent.devices.%s.configurable 按手册寄存器、OTP/NVM 或配置章节声明配置组，'
                            '或在本检查项说明它为什么没有可配置项')
SET_POINT_CRITERION = ('%s 经%s设定输出（设定点 %s）：逐个设定点按基准或 DAC 的保证误差、分压公差与温漂核输出窗口，对照需求；'
                       '中间档不由两端档推出')
ENABLE_LINK_CRITERION = ('光耦 %s 使能或关断 %s（%s 脚）：核上电时两侧供电建立的先后、使能门限与光耦传输延时，以及掉电后再上电能否'
                         '恢复工作')


# Circuit-rule preconditions (consistency proposals of 2026-10-23, item 2; catalog.SUBJECT_REQUIRES): the pins and
# parts each one looks for. A regulator output pin of an IC in the circuit stands for an internal loop and its
# output-capacitor condition; a feedback or drive pin also counts on an IC outside the circuit wired to it.
FEEDBACK_NAME_RE = re.compile(r'(V?FB\w*|COMP\w*|VCTRL|VC|ITH|ADJ|VSENSE|VOSNS|FEEDBACK)$', re.I)
DRIVE_NAME_RE = re.compile(r'(GATE\w*|G?DRV\w*|GD\w*|HO|LO|HG|LG|OUT[AB]?|SW\d*|LX\d*|PH|PHASE\d*)$', re.I)
REGULATOR_OUT_RE = re.compile(r'(V?OUT\d*|VO|VREG\w*)$', re.I)
PROTECT_NAME_RE = re.compile(r'(UV\w*|OV\w*|ILIM\w*|OCP\w*|OTP\w*|FAULT\w*|EN|ENABLE|SHDN|SHUTDOWN)$', re.I)
ANALOG_NAME_RE = re.compile(r'(AIN\w*|ADC\w*|VREF\w*|REF(IN|OUT)?|[+-]IN\w*|IN[+-PN]\w*|V?IN[AB]?[+-]|OPA\w*|CS[PN+-]\w*'
                            r'|ISENSE\w*|ISNS\w*|NTC\w*|THERM\w*|TEMP\w*|VTEMP|TS)$', re.I)
START_NAME_RE = re.compile(r'(N?RST\w*|N?RESET\w*|MR|POR\w*|BOOT\w*|STRAP\w*|EN|CHIP_EN|CHIP_PU|PWRON\w*|MODE\d*|CFG\w*)$',
                           re.I)
SENSE_NAME_RE = re.compile(r'(CS\w*|CS[+-]|ISENSE\w*|ISNS\w*|I?SENSE[+-PN]?|VSENSE\w*|IMON\w*|ISET)$', re.I)
IC_OR_SWITCH = ('POWER_SWITCH', 'SUPPLY_SWITCH', 'FEEDBACK_PIN', 'SWITCH_PIN', 'ANALOG_PIN', 'START_PIN')
PROTECTION_TEXT_RE = re.compile(r'PTC|SMBJ|SMAJ|SMCJ|TVS', re.I)


def protection_text(text):
    """A protection part by its words: an NTC, a PTC, a varistor or a TVS."""
    return bool(PROTECTION_TEXT_RE.search(text) or NTC_RE.search(text) or VARISTOR_RE.search(text))
SHUNT_OHM = 1.0


def subject_precondition(graph, names, requires, refs, nets, grounds=()):
    """(found, unread) for one precondition over a circuit: the parts on the netlist that hold it, and the parts the
    netlist cannot tell about (not in the netlist, of unknown kind, an IC without pin names); empty both means the
    mechanism is absent and the rule is not asked. `grounds` are the reference grounds of the board's domains."""
    grounds = set(grounds)

    def is_ground(net):
        return netgraph_ground(net) or net in grounds

    fitted = [ref for ref in refs if ref in graph.parts and graph.is_fitted(ref)]
    members = set(fitted)
    def text_of(ref):
        part = graph.parts.get(ref) or {}
        return ' '.join(str(part.get(k) or '') for k in ('value', 'prim', 'part'))

    def identified(ref):   # a thermistor or varistor symbol names the part though no kind is classified
        return bool(NTC_RE.search(text_of(ref)) or protection_text(text_of(ref)))

    # A part of unknown kind keeps the rule unless it cannot be what the precondition looks for: a bridge rectifier
    # or a part its symbol names is none of them, a two-terminal part is no transistor and no IC.
    unread = sorted(ref for ref in refs if ref not in graph.parts
                    or (graph.kind(ref) == UNKNOWN and not BRIDGE_RE.match(ref) and not identified(ref)
                        and not (requires in IC_OR_SWITCH and len(graph.pins_of(ref)) <= 2))
                    or (graph.kind(ref) == IC and not any(names.get(ref + '.' + pin) for pin in graph.pins_of(ref))))
    ics = [ref for ref in fitted if graph.kind(ref) == IC]
    around = {n for n in {n for ref in fitted for n in graph.nets_of(ref)} | set(nets) if not is_ground(n)}

    def ic_pins(adjacent):
        """(ref, pin) of the circuit's ICs; with `adjacent`, also of the ICs outside it whose pin is on a circuit net or
        one circuit resistor away (a controller driving the circuit's switch through a gate resistor)."""
        found = [(ref, pin) for ref in ics for pin in sorted(graph.pins_of(ref))]
        if adjacent:
            near = around | {other for net in around for r, other in graph.neighbors(net, {RESISTOR})
                             if r in members and not is_ground(other)}
            for net in sorted(near):
                for node in graph.nodes_on(net):
                    ref, _, pin = node.partition('.')
                    if ref not in members and graph.is_fitted(ref) and graph.kind(ref) == IC:
                        found.append((ref, pin))
        return found

    def with_pin(patterns, adjacent=False):
        hits = [ref for ref, pin in ic_pins(adjacent) if normalize(names.get(ref + '.' + pin))
                and any(name_matches(p, names.get(ref + '.' + pin), pin) for p in patterns)]
        return list(dict.fromkeys(hits))

    def dividers():
        """ICs with a signal pin on a circuit net that two circuit resistors divide (to two different nets)."""
        hits = []
        for net in sorted(around):
            legs = {other for r, other in graph.neighbors(net, {RESISTOR}) if r in members}
            if len(legs) < 2:
                continue
            for node in graph.nodes_on(net):
                ref, _, pin = node.partition('.')
                name = str(names.get(node) or '')
                if (graph.is_fitted(ref) and graph.kind(ref) == IC and not powertree.SUPPLY_IN_PIN_RE.match(name)
                        and not is_ground(name) and ref not in hits):
                    hits.append(ref)
        return hits

    def sensing_ntcs():
        """Thermistors an IC reads (a pin on one of its nets); one in series with the supply limits inrush."""
        return [ref for ref in fitted if NTC_RE.search(text_of(ref)) and any(
            graph.kind(node.partition('.')[0]) == IC for net in graph.nets_of(ref) if not is_ground(net)
            for node in graph.nodes_on(net))]

    if requires == 'POWER_SWITCH':
        found = [ref for ref in fitted if graph.kind(ref) in (MOSFET, BJT)]
    elif requires == 'SUPPLY_SWITCH':
        found = []
        for ref in fitted:
            ends = [graph.pin2net.get(graph.node_named(ref, role) or '') for role in ('drain', 'source')]
            if graph.kind(ref) == MOSFET and all(ends) and not any(is_ground(n) for n in ends):
                found.append(ref)
    elif requires == 'FEEDBACK_PIN':   # a loop: a feedback pin, an output sensed through a divider or an optocoupler
        found = list(dict.fromkeys(with_pin((FEEDBACK_NAME_RE,), adjacent=True) + with_pin((REGULATOR_OUT_RE,)) + dividers()
                                   + [ref for ref in fitted if graph.kind(ref) == OPTO]))
    elif requires == 'SWITCH_PIN':
        found = list(dict.fromkeys(with_pin((DRIVE_NAME_RE,), adjacent=True) + with_pin((REGULATOR_OUT_RE,))))
    elif requires == 'CONNECTOR_INPUT':   # the power path: an IC's signal pin on a connector is no input path
        reach = set()
        for net in {n for ref in fitted if graph.kind(ref) != IC for n in graph.nets_of(ref) if not is_ground(n)} | (
                around & set(nets)):
            reach |= {n for n in graph.series_path(net, PASSIVE_LINKS | {DIODE}) if not is_ground(n)}
        found = sorted({ref for ref in fitted if graph.kind(ref) == CONNECTOR}
                       | {ref for net in reach for ref in graph.refs_on(net) if graph.kind(ref) == CONNECTOR})
    elif requires == 'PROTECTION_PART':
        found = sorted({ref for ref in fitted if graph.kind(ref) in (FUSE, TVS, ZENER)
                        or protection_text(text_of(ref))} | set(with_pin((PROTECT_NAME_RE, PROTECT_PIN_RE))))
    elif requires == 'SENSE_ELEMENT':
        found = []
        for ref in fitted:
            parsed = parse_resistor_noted((graph.parts.get(ref) or {}).get('value')) if graph.kind(ref) == RESISTOR else None
            if parsed and 0 < parsed['kohm'] * 1000 < SHUNT_OHM:
                found.append(ref)
        found = list(dict.fromkeys(found + sensing_ntcs() + dividers() + with_pin((PROTECT_PIN_RE, SENSE_NAME_RE))))
    elif requires == 'ANALOG_PIN':
        found = sorted(set(with_pin((ANALOG_NAME_RE,))) | set(sensing_ntcs())
                       | {ref for ref in ics if graph.role_kind(ref) == 'opamp_comparator'})
    elif requires == 'START_PIN':
        found = sorted(set(with_pin((START_NAME_RE,))) | {ref for ref in ics if graph.role_kind(ref) == 'mcu'})
    else:
        raise ValueError('unknown precondition ' + requires)
    return found, [ref for ref in unread if ref not in found]


class CircuitPlanning:
    """功能电路与器件的检查项。"""

    def plan_circuit_types(self):
        """功能电路：名称仅生成待确认汇总项；声明/拓扑确认后展开成员，未发现的由 REQ-Q08 覆盖。"""
        declared = {str(key).upper(): value for key, value in self.intent.get('features', {}).items()}
        circuits = {}
        for circuit in self.intent.get('circuits', []):
            circuits.setdefault(circuit['type'], []).append(circuit)
        custom = [catalog.CircuitType(name, name, 'REQ', r'(?!x)x', (), ('requirements',))
                  for name in sorted(set(declared) - set(catalog.CIRCUIT_TYPE_BY_NAME))]
        undetected, declared_na = [], {}
        for kind in catalog.CIRCUIT_TYPES + tuple(custom):
            name = kind.name
            hits = _feature_hits(self.db, kind.pattern)
            topology_confirmed = name == 'I2C' and any(b['origin'] != 'name-hint'
                    for s in self.i2c_topology['states'] for b in s['buses'])
            if topology_confirmed:
                hits.append('declared I2C physical bus/port mapping')
            declared_circuits = circuits.get(name, [])
            found = hits + [f'intent.circuits:{c["id"]}' for c in declared_circuits]
            confirmed = bool(declared_circuits) or topology_confirmed
            item = declared.get(name)
            requested = item.get('applicability') if item else None
            trigger = [f'netlist:{x}' for x in hits]
            trigger += [f'intent.circuits:{c["citation"]}' for c in declared_circuits]
            if item and item.get('citation'):
                trigger.append(f'intent:{item["citation"]}')

            if requested == 'NOT_APPLICABLE' and confirmed:
                applicability = 'UNDETERMINED'
                self.diagnostics.append({
                    'code': 'INTENT_NETLIST_CONFLICT',
                    'feature': name,
                    'detail': '不适用声明与已确认拓扑或电路声明冲突；纯名称命中不构成冲突',
                    'hits': found,
                })
            elif requested in ('APPLICABLE', 'NOT_APPLICABLE'):
                applicability = requested
            elif confirmed:
                applicability = 'APPLICABLE'
            elif found:
                applicability = 'UNDETERMINED'
            elif item:
                applicability = 'UNDETERMINED'
            else:
                undetected.append(name)
                continue

            if applicability == 'NOT_APPLICABLE':
                # The declaration is the basis of the REQ-Q08 summary row, not a row of its own (R6 acceptance
                # 2026-10-24, user: a): two records wrote 13 such declarations, two none, and the rows did not pair.
                undetected.append(name)
                declared_na[name] = item.get('citation')
                continue
            if applicability == 'UNDETERMINED':
                missing = [f'intent.features.{name}']
                if requested == 'NOT_APPLICABLE' and confirmed:
                    missing.append('resolve intent/netlist conflict')
            else:
                missing = self._materials_gap(kind.materials)
            if applicability == 'APPLICABLE' and requested == 'APPLICABLE' and not found:
                self.diagnostics.append({
                    'code': 'REQUIRED_FEATURE_NOT_DETECTED',
                    'feature': name,
                    'detail': '需求要求该功能，但网表未检测到对应特征',
                })
            summary = self.add_check(
                'REQ-Q07', {'circuit_type': name}, criterion=catalog.circuit_type_criterion(name),
                applicability=applicability, readiness='WAITING_EVIDENCE' if missing else 'READY',
                required_inputs=missing, trigger=trigger)
            summary['circuit_type'] = name
            if applicability == 'APPLICABLE' and requested == 'APPLICABLE' and not found:
                self.add_check('REQ-A02', {'circuit_type': name}, readiness='READY',
                               trigger=[f'intent:{item["citation"]}'])
            if applicability == 'APPLICABLE':
                self.plan_subjects(kind, declared_circuits, missing)
        unassigned = []
        if self.candidates:
            unassigned = circuit_decisions.discovery_refs(self.candidates, self.intent.get('circuit_decisions') or [])
            owned = row_owner.part_owners(self.intent.get('circuits', []))   # function tree, step 6: every fitted part
            unassigned = sorted(set(unassigned) | {ref for ref, part in self.db.get('parts', {}).items()
                                                   if not part.get('nc') and ref not in owned})
        if undetected or unassigned:
            titles = [(name, catalog.circuit_type(name).title) for name in undetected]
            criterion = catalog.criterion('REQ-Q08')
            if undetected:
                criterion += '：' + '、'.join(name if title == name else f'{name}（{title}）' for name, title in titles)
            if declared_na:
                criterion += '；已声明不适用（features）的：' + '、'.join(sorted(declared_na))
            if unassigned:
                criterion += '；候选生成没有归属的器件，逐颗确认属于哪个功能或为何不审：' + '、'.join(unassigned)
            self.add_check(
                'REQ-Q08', {'board': 'BOARD', 'circuit_types': undetected, 'unassigned': unassigned},
                criterion=criterion,
                readiness='WAITING_EVIDENCE',
                required_inputs=[f'intent.features.{name}' for name in undetected if name not in declared_na]
                + [f'intent.circuit_decisions: add/reject for {ref}' for ref in unassigned],
                trigger=['circuit-type-discovery'] + (['circuit-candidates:unassigned'] if unassigned else [])
                + [f'intent:{c}' for c in declared_na.values() if c])

    def _rail_window(self, nets):
        """电路网络里 intent.power_rails 给了电压窗口的轨；没有就 None（问题写 catalog.NO_WINDOW）。"""
        rails = self.intent.get('power_rails') or {}
        parts = []
        for net in nets:
            window = (rails.get(net) or {}).get('voltage_v') if isinstance(rails.get(net), dict) else None
            if isinstance(window, dict) and finite(window.get('min')) and finite(window.get('max')):
                parts.append(f'{net} {window["min"]}–{window["max"]} V')
        return '、'.join(parts) or None

    def plan_subjects(self, kind, circuits, missing):
        """声明了电路则逐电路×工况展开电路检查项并建功能框架（答案不随工作态变化的规则每电路一项），
        否则按功能电路展开一次；已有 I²C 区域时由检查器逐区域展开。"""
        members, not_asked, requirements = [], {}, {}
        graph = NetGraph(board_intent.graph_db(self.db, self.kind_intent)) if circuits else None
        names = dict(self.db.get('declared_pinname') or {}, **(self.db.get('pinname') or {}))
        for circuit in circuits:
            refs = circuit['refs']
            gaps = [f'datasheet:{ref}' for ref in refs
                    if not (datasheet_entry_for_ref(self.datasheet_audit, ref) or {}).get('status') == 'AVAILABLE']
            gaps += [f'unknown ref:{ref}' for ref in refs if ref not in self.db.get('parts', {})]
            trigger = f'intent.circuits:{circuit["citation"]}'
            asked = {}   # rule -> (object ref, requires) for the rules whose precondition holds
            not_asked[circuit['id']] = []
            for rule in kind.subjects:
                requires = catalog.SUBJECT_REQUIRES.get((kind.name, rule))
                if requires is None:
                    asked[rule] = (refs[0], None)
                    continue
                found, unread = subject_precondition(graph, names, requires, refs, circuit.get('nets', []),
                                                     self.domains['grounds'])
                if found or unread:
                    asked[rule] = ((found or unread)[0], dict({'id': requires, 'found': found},
                                                              **({'unread': unread} if unread else {})))
                else:
                    not_asked[circuit['id']].append({'rule': rule, 'aspect': catalog.title(rule), 'requires': requires,
                                                     'why': catalog.SUBJECT_PRECONDITIONS[requires]})
            requirements[circuit['id']] = asked
            for index, state in enumerate(circuit['states']):
                for rule in kind.subjects:
                    invariant = rule in catalog.STATE_INVARIANT
                    if rule not in asked or (invariant and index):
                        continue   # an invariant rule is asked once per circuit, with the first state's rows
                    obj = {'circuit': circuit['id'], 'circuit_key': '+'.join(sorted(circuit.get('candidate_ids') or [circuit['id']])),
                           'ref': asked[rule][0], 'refs': refs, 'nets': circuit.get('nets', [])}
                    if not invariant:
                        obj['state'] = state
                    key = circuit['id'] if invariant else f'{circuit["id"]}-{state}'
                    members.append((rule, obj, key, gaps, trigger))
        regions = any(state['regions'] for state in self.i2c_topology['states'])
        if not circuits and not (kind.name == 'I2C' and regions):
            for rule in kind.subjects:
                members.append((rule, {'circuit_type': kind.name}, None, missing, f'circuit-type:{kind.name}'))
        frames = {}
        for circuit in circuits:
            window = self._rail_window(circuit.get('nets', []))
            frames[circuit['id']] = {
                'id': 'FN-' + _slug(circuit['id']),
                'circuit': circuit['id'],
                'circuit_type': kind.name,
                'question': catalog.frame_question(kind.name, circuit['id'], circuit['refs'], circuit['states'], window),
                'objects': {'refs': list(circuit['refs']), 'nets': list(circuit.get('nets', []))},
                'states': list(circuit['states']),
                'members': [],
                'blind_spots': {rule: catalog.explanation(rule)['risk_if_omitted'] for rule in kind.subjects
                                if rule in requirements[circuit['id']]},
                'not_asked': not_asked[circuit['id']],
                'checklist': list(catalog.BOUNDING_STEPS),
                'bounds': self._frame_bounds(graph, circuit['refs']),
            }
            asked = [rule for rule in kind.subjects if rule in requirements[circuit['id']]]
            if 2 * len(asked) < len(kind.subjects):   # proposals item 2b: the type asks almost nothing of this circuit
                self.diagnostics.append({
                    'code': 'CIRCUIT_TYPE_MISFIT', 'circuit': circuit['id'], 'circuit_type': kind.name, 'asked': asked,
                    'detail': '%s 按 %s 只问到 %d/%d 条电路规则：换一个类型，或不建这块电路、让器件走器件检查项' % (
                        circuit['id'], kind.name, len(asked), len(kind.subjects))})
        for rule, obj, key, gaps, trigger in members:
            frame = frames.get(obj.get('circuit'))
            item = self._ready_check(rule, dict(obj), gaps, [trigger], key=key)
            item['circuit_type'] = kind.name
            requires = requirements.get(obj.get('circuit'), {}).get(rule, (None, None))[1]
            if requires:
                item['requires'] = requires
            item['analysis_required'] = True
            item['scope'] = '原理图电气条件；PCB/实测验证另建 HANDOFF'
            if frame is not None:
                item['question'] = catalog.question(rule, obj.get('state'), obj['circuit'], obj['refs'],
                                                    self._rail_window(obj['nets']))
                item['function_id'] = frame['id']
                item['aspect'] = catalog.title(rule)
                frame['members'].append({'check_id': item['id'], 'rule': rule, 'aspect': item['aspect'],
                                         'state': obj.get('state')})
        self.functions.extend(frames.values())

    def plan_concrete_checks(self):
        db = self.db
        nets = db.get('nets', {})
        pinname = db.get('pinname', {})
        pin2net = db.get('pin2net', {})
        pseudo = set(db.get('pseudo_nets', []))

        # 反馈分压、使能、strap 与 I2C 上拉：审查者按手册保证值核。
        for node, pin in sorted(pinname.items()):
            net = pin2net.get(node)
            upper_pin = str(pin).strip().upper()
            ref = node.split('.')[0]
            if upper_pin in FB_NAMES and net:
                obj = {'node': node, 'net': net, 'ref': ref}
                self.add_check(
                    'PWR-E01', obj, readiness='WAITING_EVIDENCE',
                    required_inputs=['datasheet:Vref/目标窗口'],
                    trigger=[f'pinname:{pin}'])
            if net and (EN_RE.search(upper_pin) or (
                    EN_RE.search(net) and re.match(r'^[UMQ]\d', ref, re.I))):
                obj = {'node': node, 'net': net, 'ref': ref}
                self.add_check(
                    'RST-E01', obj, readiness='WAITING_EVIDENCE',
                    required_inputs=['datasheet:pin function/Abs Max'],
                    trigger=[f'pinname:{pin}', f'net:{net}'])
            if net and (STRAP_RE.search(upper_pin) or (
                    STRAP_RE.search(net) and re.match(r'^[UMQ]\d', ref, re.I))):
                obj = {'node': node, 'net': net, 'ref': ref}
                self.add_check(
                    'RST-E02', obj, readiness='WAITING_EVIDENCE',
                    required_inputs=['datasheet:strap table/mandatory wording'],
                    trigger=[f'pinname:{pin}', f'net:{net}'])

        i2c_nets = set()
        for net, nodes in nets.items():
            if I2C_RE.search(net) or any(
                    I2C_RE.search(str(pinname.get(node, ''))) for node in nodes):
                i2c_nets.add(net)
        for net in sorted(i2c_nets - pseudo):
            obj = {'net': net}
            self.add_check(
                'SIG-E01', obj, readiness='WAITING_EVIDENCE',
                required_inputs=['datasheet/platform:I2C pull requirement'],
                trigger=[f'net:{net}'])

        # 连接器：pin map、对端定义、未用针处置与对外防护逐个一项。
        connector_graph = NetGraph(board_intent.graph_db(db, self.kind_intent))
        for ref, part in sorted(db.get('parts', {}).items()):
            if part.get('nc') or not (CONNECTOR_RE.match(ref) or connector_graph.kind(ref) == CONNECTOR):
                continue
            connector_trigger = [f'refdes:{ref}',
                                 f'connector-kind:{connector_graph.basis(ref)}']
            obj = {'ref': ref}
            self.add_check(
                'DEV-E01', obj, readiness='WAITING_EVIDENCE',
                required_inputs=['connector drawing/opposite-side pinout'],
                trigger=connector_trigger)
            gaps, audit_trigger = self._datasheet_readiness(ref, part)
            port = {'interface': 'EXT-' + ref, 'ref': ref}   # the connector's interface (function tree, step 4)
            self._ready_check('DEV-D03', dict(port), self._materials_gap(['requirements']), connector_trigger)
            self._ready_check('DEV-C04', dict(port), self._materials_gap(INTERFACE_MATERIALS['DEV-C04']), connector_trigger)
            self._disposition_check(ref, gaps, connector_trigger + audit_trigger)
            self.add_check('PRO-D03', dict(port), trigger=connector_trigger)

        # 每条电源轨分别检查拓扑（连接追踪）和功耗预算（工程计算）。
        # 轨名不像电源（BULK、HVDC、PRI_AUX）但 intent.power_rails 已声明且确实供电的网同样是轨。
        declared_rails = powertree.declared_supply_nets(connector_graph, self.intent)
        for net in sorted(nets):
            if net in pseudo or is_ground(net) or not (RAIL_RE.match(net) or net in declared_rails):
                continue
            self.add_check('PWR-T01', {'net': net},
                           trigger=[f'rail-name:{net}' if RAIL_RE.match(net) else f'declared-rail:{net}'])
            budget = self.intent.get('power_rails', {}).get(net, {})
            missing = []
            for field in ('voltage_v', 'load_a'):
                if not bounded(budget.get(field)):
                    missing.append(f'power_rails.{net}.{field}.min/max')
            if not finite(budget.get('available_a_min')):
                missing.append(f'power_rails.{net}.available_a_min')
            for field in ('state', 'citation'):
                if not _text(budget.get(field)):
                    missing.append(f'power_rails.{net}.{field}')
            if not budget.get('refs'):
                missing.append(f'power_rails.{net}.refs')
            for ref in budget.get('refs', []):
                entry = datasheet_entry_for_ref(self.datasheet_audit, ref)
                if not entry or entry.get('status') != 'AVAILABLE':
                    missing.append(f'datasheet:{ref}')
            self.add_check(
                'PWR-C01', {'net': net},
                readiness='WAITING_EVIDENCE' if missing else 'READY',
                required_inputs=missing, trigger=[f'rail-name:{net}'])

        # 差分连通（连接追踪）。
        for positive, negative in _differential_pairs(db):
            self.add_check(
                'SIG-T01', {'net_p': positive, 'net_n': negative, 'net': positive},
                trigger=[f'pair:{positive}/{negative}'])

        # 原生声明的页面独立于器件；旧格式只能覆盖已定位器件所在页。
        pdf_ready = _material_available(self.intent, 'schematic_pdf')
        for row in self.document_inventory['pages']:
            page = row['page']
            obj = {'page': page}
            if 'sheet_path' in row:
                obj['sheet_path'] = row['sheet_path']
            self.add_check(
                'DOC-V01', obj,
                readiness='READY' if pdf_ready else 'WAITING_EVIDENCE',
                required_inputs=[] if pdf_ready else ['schematic_pdf'],
                trigger=[f"{self.document_inventory['source']}:{page}"])
        if self.document_inventory['scope'] == LIMITED:
            self.diagnostics.append({'code': 'LIMITED_PAGE_INVENTORY',
                'message': 'Only component pages are known; native empty/root pages cannot be inferred.'})

        # 每颗 IC/模组和意图显式列出的关键器件逐颗核身份、引脚处置与工况。
        # 位号并非器件身份；连接器已有独立覆盖，不重复未用脚处置。
        # 位号不是 U/M 的有源器件（如 Reg1 稳压器）按原生电源脚识别：三脚以上、有 power_in/out、
        # 未归为分立器件或连接器。
        native = db.get('native_pintype') or {}
        powered = {node.split('.')[0] for node, kind in native.items() if kind in ('power_in', 'power_out')}

        verified = board_intent.declared_kinds(self.kind_intent)   # datasheet-verified kinds, by ref

        def active_by_function(ref):
            # native power pins on a three-pin-or-more IC, or a datasheet-verified active kind (a shunt reference or
            # opto with a D refdes): the kind decides which parts have rows, a `devices` declaration alone never does
            # (R6 fix list B2, user: 按照 a)
            if (verified.get(ref) or {}).get('kind') in ACTIVE_VERIFIED_KINDS:
                return True
            return (ref in powered and len(connector_graph.pins_of(ref)) >= 3
                    and connector_graph.kind(ref) in (IC, UNKNOWN))

        for ref, part in sorted(db.get('parts', {}).items()):
            connector = CONNECTOR_RE.match(ref) or connector_graph.kind(ref) == CONNECTOR
            by_function = not DEVICE_RE.match(ref) and active_by_function(ref)
            kind = connector_graph.kind(ref)
            fixed = (kind in FIXED_DEVICE_KINDS or BRIDGE_RE.match(ref) or (kind == INDUCTOR and CUSTOM_PART_RE.search(
                ' '.join(str(part.get(k) or '') for k in ('part', 'value')))))
            if part.get('nc') or not (DEVICE_RE.match(ref) or by_function or (fixed and not connector)):
                continue
            gaps, audit_trigger = self._datasheet_readiness(ref, part)
            trigger = ([f'refdes:{ref}', f'part:{part.get("part", "")}'] + audit_trigger
                       + (['native-power-pins:active-device'] if by_function else []))
            item = self._ready_check('DEV-D01', {'ref': ref}, gaps, trigger)
            if self._bom_fields(ref):
                item['bom_fields'] = self._bom_fields(ref)
            self._disposition_check(ref, gaps, trigger)
            self._ready_check('DEV-C05', {'ref': ref}, gaps + self._materials_gap(['requirements']), trigger)

        self.plan_threshold_checks(connector_graph)

    def _bom_fields(self, ref):
        """The part's own BOM columns (read_bom.py), or {} without a BOM."""
        return dict(((self.db.get('bom') or {}).get('parts') or {}).get(ref) or {})

    def _with_bom_specs(self, frame):
        """A function frame with what the BOM writes about its parts, beside their values."""
        refs = (frame.get('objects') or {}).get('refs') or []
        specs = {ref: self._bom_fields(ref) for ref in refs if self._bom_fields(ref)}
        return dict(frame, bom_specs=specs) if specs else frame

    def plan_threshold_checks(self, graph):
        """阈值型保护器件/门限脚两侧窗口（PRO-C02）与传感器开短路判别（ANA-C04），逐对象一项。"""
        db = self.db
        nets, pin2net = db.get('nets', {}), db.get('pin2net', {})
        names = dict(db.get('declared_pinname') or {}, **(db.get('pinname') or {}))
        parts = db.get('parts', {})
        requirements = self._materials_gap(['requirements'])

        def grounded(net):
            return is_ground(net)

        def window(obj, gaps, trigger, gate_clamp=False):
            for side, criterion in WINDOW_SIDES:
                if gate_clamp and side == 'NOTRIP':
                    criterion = GATE_CLAMP_NOTRIP
                self._ready_check('PRO-C02', obj, gaps + requirements, trigger, key=side, criterion=criterion)

        def gate_source_clamp(ref):
            """两端分别在某只 MOS 的栅极网和源极网上。"""
            pins = set(graph.pins_of(ref).values())
            for other in parts:
                gate, source = (graph.node_named(other, role) for role in ('gate', 'source'))
                if (other != ref and graph.kind(other) == MOSFET and gate and source
                        and pins == {pin2net.get(gate), pin2net.get(source)}):
                    return other
            return None

        def follower_bias_zener(ref):
            """A zener from a MOSFET's gate to ground whose source is not ground: the follower's bias reference, conducting by
            design, not a threshold protection (R7 acceptance 2026-10-25, claude1: D404 on Q401)."""
            ends = set(graph.pins_of(ref).values())
            live = [net for net in ends if net and not grounded(net)]
            if len(ends) != 2 or len(live) != 1:
                return None
            for other in parts:
                gate, source = (graph.node_named(other, role) for role in ('gate', 'source'))
                if (other != ref and graph.kind(other) == MOSFET and gate and source and pin2net.get(gate) == live[0]
                        and pin2net.get(source) and not grounded(pin2net[source]) and pin2net[source] != live[0]):
                    return other
            return None

        rails = powertree.PowerTree(graph)

        def connectors_on(net):
            return {node.split('.')[0] for node in nets.get(net, [])
                    if CONNECTOR_RE.match(node.split('.')[0]) or graph.kind(node.split('.')[0]) == CONNECTOR}

        def io_clamp_connectors(ref):
            """对外信号线 ESD 钳位：一端接地，其余端都是信号网（非轨、非开关节点）且直达连接器；
            由 PRO-D03 逐针覆盖。跨开关节点或浮地回流的 TVS 是能量钳位，仍按 PRO-C02 两侧核。"""
            pins = set(graph.pins_of(ref).values())
            live = [net for net in pins
                    if net and not grounded(net) and net not in db.get('pseudo_nets', [])]
            if (not live or len(live) == len(pins)
                    or any(rails.is_rail(net) or rails.is_switch_node(net) for net in live)):
                return set()
            return set().union(*(connectors_on(net) for net in live))

        for ref, part in sorted(parts.items()):
            if part.get('nc'):
                continue
            kind = graph.kind(ref)
            covering = [check for check in self.checks if check['rule'] == 'PRO-D03'
                        and check['object'].get('ref') in io_clamp_connectors(ref)] if kind == TVS else []
            if covering:
                for check in covering:
                    check['clamp_refs'] = sorted(set(check.get('clamp_refs', [])) | {ref})
                continue
            if kind == ZENER and follower_bias_zener(ref):
                self.diagnostics.append({'code': 'GATE_BIAS_ZENER', 'ref': ref, 'switch': follower_bias_zener(ref),
                                         'message': '%s 是 %s 源跟随器的栅极偏置基准，正常就导通：不派 PRO-C02 两侧窗口，由器件检查项和电路判定核它'
                                                    % (ref, follower_bias_zener(ref))})
                continue
            if kind in (ZENER, TVS):
                gaps, audit = self._datasheet_readiness(ref, part)
                switch = gate_source_clamp(ref)
                window({'ref': ref}, gaps, [f'refdes:{ref}', f'device-kind:{kind}:{graph.basis(ref)}'] + audit
                       + ([f'gate-source-clamp:{switch}'] if switch else []), gate_clamp=bool(switch))
                continue
            words = ' '.join(str(part.get(k, '')) for k in ('part', 'value', 'prim'))
            if not (SENSOR_RE.search(words) or NTC_RE.search(words)):
                continue
            # 传感器接电源轨的一端只是偏置，不是检测脚；轨上 IC 的供电脚也不判别开短路。
            for net in sorted(set(graph.pins_of(ref).values())):
                if (not net or grounded(net) or net in db.get('pseudo_nets', [])
                        or rails.is_rail(net)):
                    continue
                for node in sorted(nets.get(net, [])):
                    owner = node.split('.')[0]
                    if (owner == ref or graph.kind(owner) != IC or GROUND_PIN_RE.match(normalize(names.get(node)))
                            or (db.get('native_pintype') or {}).get(node) in ('power_in', 'power_out')):
                        continue
                    sensor_gaps, audit = self._datasheet_readiness(ref, part)
                    ic_gaps, ic_audit = self._datasheet_readiness(owner, parts.get(owner, {}))
                    self._ready_check(
                        'ANA-C04', {'ref': ref, 'node': node, 'net': net}, sensor_gaps + ic_gaps + requirements,
                        [f'sensor:{ref}', f'pinname:{names.get(node, "")}', f'net:{net}'] + audit + ic_audit,
                        key=ref)

        for node, pin in sorted(names.items()):
            ref, net = node.split('.')[0], pin2net.get(node)
            part = parts.get(ref) or {}
            if (not net or part.get('nc') or grounded(net) or graph.kind(ref) != IC
                    or not PROTECT_PIN_RE.match(normalize(pin))):
                continue
            gaps, audit = self._datasheet_readiness(ref, part)
            window({'node': node, 'net': net, 'ref': ref}, gaps, [f'pinname:{pin}', f'net:{net}'] + audit)

    def plan_owned_parts(self):
        """DEV-C01/C02/C03 每块电路对它拥有的器件一项（按 OWNED_PART_KINDS 取器件），没有电路拥有的器件全板一项。"""
        graph = NetGraph(board_intent.graph_db(self.db, self.kind_intent))
        circuits = self.intent.get('circuits', [])
        owners = row_owner.part_owners(circuits)
        fitted = [ref for ref in sorted(graph.parts) if graph.is_fitted(ref)]
        for rule in catalog.OWNED_PART_RULES:
            wanted = [ref for ref in fitted if OWNED_PART_KINDS[rule](graph.kind(ref))]
            gaps = self._materials_gap(OWNED_PART_MATERIALS[rule])
            for circuit in circuits:
                refs = [ref for ref in wanted if owners.get(ref) == circuit['id']]
                if refs:
                    key = '+'.join(sorted(circuit.get('candidate_ids') or [circuit['id']]))
                    self._ready_check(rule, {'circuit': circuit['id'], 'circuit_key': key, 'refs': refs}, gaps,
                                      [f'intent.circuits:{circuit["id"]}'])
            residual = [ref for ref in wanted if ref not in owners]
            if residual:
                self._ready_check(rule, {'board': 'BOARD', 'refs': residual}, gaps, ['board', 'unowned-parts'])
        self.plan_life_rows(graph, fitted)
        self.plan_feedback_open_rows(graph)
        self.plan_single_fault_rows(graph, fitted)
        self.plan_configuration_rows(graph, fitted)

    def plan_configuration_rows(self, graph, fitted):
        """CFG-D01 per programmable device and configuration group (consistency proposals of 2026-10-23, item 3): the
        fixed groups of its role and the groups intent.devices.<ref>.configurable declares; a programmable role with
        neither gets a row asking for them. A group that selects output levels also asks each set point's accuracy."""
        devices = self.intent.get('devices') or {}
        for ref in fitted:
            role = graph.role_kind(ref)
            declared = {g['group']: g for g in (devices.get(ref) or {}).get('configurable') or []
                        if isinstance(g, dict) and isinstance(g.get('group'), str)}
            fixed = [group for group, _ in catalog.CONFIG_GROUPS.get(role, ())]
            groups = fixed + [g for g in declared if g not in fixed]
            undeclared = [g for g in groups if g not in declared] if role in catalog.PROGRAMMABLE_ROLES else []
            if undeclared or (not groups and role in catalog.PROGRAMMABLE_ROLES):
                # the CFG-D01 criterion and key follow the declaration, so two reviewers pair only when both declared
                # (R7 acceptance 2026-10-25, list A8): a programmable part without its configurable groups is a 2.1 gap
                self.diagnostics.append({'code': 'CONFIGURABLE_UNDECLARED', 'ref': ref, 'role': role, 'groups': undeclared,
                                         'message': '%s 是可编程器件（%s）：在 intent.devices.%s.configurable 按手册写出 %s 组的出处、允许范围与影响的方面，'
                                                    '再重生成计划；没有声明时 CFG-D01 项只能等资料' % (ref, role, ref, '、'.join(undeclared) or '配置')})
            if not groups:
                if role in catalog.PROGRAMMABLE_ROLES:
                    self.add_check('CFG-D01', {'ref': ref, 'config_group': 'DECLARE'}, key='DECLARE',
                                   criterion=CONFIG_DECLARE_CRITERION % (ref, role, ref), readiness='WAITING_EVIDENCE',
                                   required_inputs=['intent.devices.%s.configurable' % ref], trigger=['role:%s' % role])
                continue
            for group in groups:
                item = declared.get(group)
                title = catalog.CONFIG_GROUP_TITLES.get(group) or (item or {}).get('title') or group
                if item is None:
                    self.add_check('CFG-D01', {'ref': ref, 'config_group': group}, key=group,
                                   criterion=CONFIG_UNDECLARED_CRITERION % (ref, title, ref), readiness='WAITING_EVIDENCE',
                                   required_inputs=['intent.devices.%s.configurable.%s' % (ref, group)],
                                   trigger=['role:%s' % role])
                    continue
                row = self.add_check('CFG-D01', {'ref': ref, 'config_group': group}, key=group,
                                     criterion=CONFIG_CRITERION % (ref, title),
                                     readiness='READY', trigger=['intent.devices.%s.configurable.%s' % (ref, group)])
                row['configuration'] = {'citation': item['citation'], 'allowed': item['allowed'],
                                        'affects': list(item['affects'])}
                if item.get('required'):
                    row['configuration']['required'] = item['required']
                if item.get('set_points'):   # proposals item 7, sixth trigger
                    self.add_check('PWR-C02', {'ref': ref, 'config_group': group, 'set_points': list(item['set_points'])},
                                   key='SET-POINT-' + group,
                                   criterion=SET_POINT_CRITERION % (ref, title, '、'.join(item['set_points'])),
                                   readiness='READY', trigger=['intent.devices.%s.configurable.%s.set_points' % (ref, group)])

    def plan_single_fault_rows(self, graph, fitted):
        """The single faults one reviewer asks and another does not, asked wherever their feature is on the netlist."""
        names = dict(self.db.get('declared_pinname') or {}, **(self.db.get('pinname') or {}))
        native = self.db.get('native_pintype') or {}
        from decoupling import parse_capacitance
        tree = powertree.PowerTree(graph, self.intent)
        # A declared rail is a supply checked against its declared returns too; it stands for a converter output the
        # trace cannot reach (a transformer secondary).
        declared = powertree.declared_supply_nets(graph, self.intent)

        def text_of(ref):
            part = graph.parts.get(ref) or {}
            return ' '.join(str(part.get(k) or '') for k in ('value', 'prim', 'part'))

        def bulk(net):
            return any(graph.kind(c) == CAPACITOR and any(is_ground(n) for n in graph.nets_of(c) if n != net)
                       and (parse_capacitance((graph.parts.get(c) or {}).get('value')) or 0) >= BULK_FARAD
                       for c in graph.refs_on(net))

        def connectors_on(net):
            return [c for c in graph.refs_on(net) if graph.kind(c) == CONNECTOR]

        def feeds_ic(net):
            return any(graph.kind(n.split('.')[0]) == IC and (native.get(n) == 'power_in'
                       or powertree.SUPPLY_IN_PIN_RE.match(str(names.get(n) or ''))) for n in graph.nodes_on(net))

        def signal_pins(net):
            for node in graph.nodes_on(net):
                ref, name = node.split('.')[0], str(names.get(node) or '')
                if (graph.is_fitted(ref) and graph.kind(ref) == IC and not is_ground(name)
                        and native.get(node) not in ('power_in', 'power_out')
                        and not powertree.SUPPLY_IN_PIN_RE.match(name)):
                    yield ref, node

        for ref in fitted:
            kind = graph.kind(ref)
            if kind == MOSFET:
                ends = [graph.pin2net.get(graph.node_named(ref, role) or '') for role in ('drain', 'source')]
                # A dedicated output port: the switch's far net reaches a connector and feeds no IC, and the near net is
                # a converter or regulator output with bulk storage, not itself a connector rail (a battery or
                # power-path switch) nor a rail the switch itself feeds.
                for supply, port in (ends, ends[::-1]):
                    connectors = connectors_on(port) if port else []
                    if (supply and port and not is_ground(port) and connectors and not feeds_ic(port)
                            and not connectors_on(supply)
                            and (supply in declared or (bulk(supply) and tree.driven(supply)))):
                        self.add_check('DRV-C02', {'ref': ref, 'net': port, 'connector': connectors[0]}, key='PORT-SHORT',
                                       criterion=PORT_SHORT_CRITERION % (ref, supply, connectors[0]),
                                       trigger=['switch:%s' % ref, 'connector:%s' % connectors[0], 'bulk:%s' % supply])
            ends = graph.terminals(ref)
            if NTC_RE.search(text_of(ref)) and ends and not any(is_ground(n) for n in ends):
                touching = {graph.kind(r) for n in ends for r in graph.refs_on(n) if r != ref}
                bridge = any(BRIDGE_RE.match(r) for n in ends for r in graph.refs_on(n))
                if IC not in touching and (touching & {BRIDGE_RECTIFIER, DIODE, FUSE, CONNECTOR} or bridge):
                    self.add_check('PWR-C13', {'ref': ref}, key='NTC-HOT', criterion=NTC_HOT_CRITERION % ref,
                                   trigger=['thermistor:%s' % ref])
            if kind == DIODE and len(ends) == 2:
                for switch, clamp in (ends, ends[::-1]):
                    on_switch = {graph.kind(r) for r in graph.refs_on(switch)}
                    drains = [n for n in graph.nodes_on(switch) if graph.kind(n.split('.')[0]) == MOSFET
                              and graph.role(n) == 'drain']
                    if not (drains and on_switch & {TRANSFORMER, INDUCTOR}):
                        continue
                    if bulk(clamp):   # a rail with storage to ground (a boost output) is not a clamp node
                        continue
                    caps = {other: c for c, other in graph.neighbors(clamp, {CAPACITOR}) if other != switch}
                    for resistor, other in graph.neighbors(clamp, {RESISTOR}):
                        if other in caps:
                            self.add_check('DRV-C01', {'ref': resistor, 'diode': ref, 'net': clamp}, key='RCD',
                                           criterion=RCD_CRITERION % (resistor, ref, caps[other]),
                                           trigger=['clamp-diode:%s' % ref, 'switch-node:%s' % switch])
        led_nets = {}
        for ref in fitted:
            if graph.kind(ref) == OPTO or (graph.kind(ref) == DIODE and (LED_RE.search(text_of(ref))
                                                                           or re.match(r'^LED\d', ref, re.I))):
                for role in ('led_anode', 'led_cathode', 'anode', 'cathode'):
                    node = graph.node_named(ref, role)
                    if node and graph.pin2net.get(node) and not is_ground(graph.pin2net[node]):
                        led_nets.setdefault(graph.pin2net[node], ref)
        for net, led in sorted(led_nets.items()):
            for ref, node in signal_pins(net):
                self.add_check('DEV-C05', {'ref': ref, 'node': node, 'net': net, 'led': led}, key='PIN-LED',
                               criterion=PIN_LED_CRITERION % (node, led), trigger=['led:%s' % led, 'pin:%s' % node])
        optocouplers = self.inventories.get('optocoupler') or {}
        seen = set()
        for state in optocouplers.get('states') or []:
            for opto in state.get('optocouplers') or []:
                for net in (opto.get('collector_net'), opto.get('emitter_net')):
                    for ref, node in signal_pins(net) if net else ():
                        if not ENABLE_LINK_PIN_RE.search(str(names.get(node) or '')) or (opto['ref'], node) in seen:
                            continue
                        seen.add((opto['ref'], node))
                        self.add_check('SIG-C09', {'ref': ref, 'node': node, 'net': net, 'optocoupler': opto['id'],
                                                   'optocoupler_digest': optocouplers['digest']},
                                       key='ENABLE-LINK', criterion=ENABLE_LINK_CRITERION % (opto['ref'], ref, node),
                                       trigger=['optocoupler:%s' % opto['ref'], 'enable-pin:%s' % node])

    def plan_feedback_open_rows(self, graph):
        """A controller regulated through an optocoupler on its feedback pin: one row for the feedback opening, the
        single fault whose output overshoot only the protection delay bounds."""
        names = dict(self.db.get('declared_pinname') or {}, **(self.db.get('pinname') or {}))
        seen = set()
        optocouplers = self.inventories.get('optocoupler') or {}
        for state in optocouplers.get('states') or []:
            for opto in state.get('optocouplers') or []:
                for net in (opto.get('collector_net'), opto.get('emitter_net')):
                    for node in sorted((self.db.get('nets') or {}).get(net) or []):
                        ref = node.split('.')[0]
                        if (ref == opto['ref'] or graph.kind(ref) != IC
                                or not FEEDBACK_PIN_RE.fullmatch(str(names.get(node) or '')) or (opto['ref'], node) in seen):
                            continue
                        seen.add((opto['ref'], node))
                        self.add_check('PRO-C01', {'ref': ref, 'node': node, 'net': net, 'optocoupler': opto['id'],
                                                   'optocoupler_digest': optocouplers['digest']},
                                       key='FEEDBACK-OPEN', criterion=FEEDBACK_OPEN_CRITERION % (opto['ref'], ref),
                                       trigger=['optocoupler:%s' % opto['ref'], 'feedback-pin:%s' % node])

    def _part_text(self, graph, ref):
        part = graph.parts.get(ref) or {}
        bom = self._bom_fields(ref)
        return ' '.join(str(v or '') for v in [part.get(k) for k in ('value', 'prim', 'part', 'footprint')]
                        + [bom.get(k) for k in ('MPN', 'Electrical specification', 'Footprint', 'Value')])

    def bound_kinds(self, graph, ref):
        """The device classes of the bounding table (catalog.BOUNDS) a part falls in: an NTC is an NTC, an
        electrolytic is not an MLCC, and an IC also has its verified role."""
        kind = graph.kind(ref)
        if kind in (RESISTOR, FUSE) and NTC_RE.search(self._part_text(graph, ref)):
            return {'ntc'}
        if kind == CAPACITOR and self.electrolytic(graph, ref):
            return {'electrolytic'}
        return {kind, graph.role_kind(ref)} - {None}

    def _frame_bounds(self, graph, refs):
        """The bounding-table cells for the parts of a frame, in table order, so the reviewer follows the table
        (decision A) without reading it."""
        kinds = {ref: self.bound_kinds(graph, ref) for ref in refs}
        out = []
        for bound in catalog.BOUNDS.values():
            hit = [ref for ref in refs if kinds[ref] & set(bound.kinds)]
            if hit:
                out.append({'cell': bound.id, 'refs': hit, 'parameter': bound.parameter, 'side': bound.side,
                            'methods': [code for code, _ in bound.methods],
                            'formulas': [name for _, names in bound.methods for name in names],
                            'fallback': bound.fallback})
        return out

    def electrolytic(self, graph, ref):
        """'super', 'electrolytic' or None for a fitted capacitor (6c)."""
        if graph.kind(ref) != CAPACITOR:
            return None
        from decoupling import parse_capacitance
        part, text = graph.parts.get(ref) or {}, self._part_text(graph, ref)
        if TANTALUM_RE.search(text):
            return None
        farads = parse_capacitance(part.get('value'))
        if farads is not None and farads >= SUPERCAP_FARAD:
            return 'super'
        symbol = ' '.join(str(part.get(k) or '') for k in ('prim', 'part'))
        if POLARIZED_SYMBOL_RE.search(symbol) or ELECTROLYTIC_RE.search(text):
            return 'electrolytic'
        if (ALUMINIUM_PACKAGE_RE.search(text) and VOLTAGE_RE.search(str(part.get('value') or ''))
                and (farads or 0) >= BULK_FARAD):
            return 'electrolytic'
        return None

    def wearout_class(self, graph, ref):
        """The catalog.WEAROUT_CLASSES entry a fitted part falls in, or None (6e)."""
        kind, text = graph.kind(ref), self._part_text(graph, ref)
        if device_kinds.wearout_of(kind):          # the kind alone decides: battery, opto, varistor, relay, connector, switch
            return device_kinds.wearout_of(kind)
        if kind == DIODE and (LED_RE.search(text) or re.match(r'^LED\d', ref, re.I)):
            return 'LED'
        if VARISTOR_RE.search(text):
            return 'VARISTOR'
        if kind == FUSE:
            return 'PTC' if PTC_RE.search(text) else 'FUSE'
        if kind == NTC or NTC_RE.search(text):
            ends = graph.terminals(ref)
            on_ends = {graph.kind(r) for n in ends for r in graph.refs_on(n) if r != ref}
            return 'INRUSH_NTC' if ends and not any(is_ground(n) for n in ends) and IC not in on_ends else None
        if SWITCHLIKE_RE.search(text):
            return 'SWITCH'
        if kind == IC and (MEMORY_RE.search(text) or graph.role_kind(ref) == 'mcu'):
            return 'MEMORY'
        return None

    def plan_life_rows(self, graph, fitted):
        """A lifetime requirement falls on every electrolytic, solid or super capacitor (DEV-C02 life row, 6a/6c) and on
        every part of a wear-out class (DEV-C06, 6e), all planned on the one intent.mission_profile (6d); without it
        the rows wait for it. A wear-out class judged on a count the profile does not give is NA with that reason."""
        lives = requirement_parameters.windows(self.intent, 'lifetime')
        if not lives:
            return
        profile = requirement_parameters.mission_profile(self.intent)
        trigger = ['requirement:' + w['requirement'] for w in lives]
        wait = {} if profile else {'readiness': 'WAITING_EVIDENCE', 'required_inputs': ['intent.mission_profile']}
        # The criterion carries the profile's numbers without the phase names (the names are the reviewer's, the
        # numbers are the requirement's); the named profile rides on the row as `mission_profile` for reading.
        basis = (requirement_parameters.profile_criterion_text(profile) if profile else
                 '需求 %s 给了设计寿命，intent.mission_profile 还没写任务剖面' % '、'.join(sorted({w['requirement'] for w in lives})))
        named = requirement_parameters.profile_text(profile) if profile else None
        for ref in fitted:
            cap = self.electrolytic(graph, ref)
            if cap:
                extra = '；超级电容另核电压降额' if cap == 'super' else ''
                row = self.add_check('DEV-C02', {'ref': ref}, key='LIFE', criterion=LIFE_CRITERION % (basis, extra),
                                     trigger=trigger, handoff=dict(LIFE_HANDOFF), **wait)
                if named:
                    row['mission_profile'] = named
                continue
            name = self.wearout_class(graph, ref)
            if name is None:
                continue
            entry = catalog.WEAROUT_CLASSES[name]
            count = requirement_parameters.profile_count(profile, entry.event, ref) if entry.event else None
            if profile and entry.event and count is None:
                row = self.add_check('DEV-C06', {'ref': ref, 'wearout': name}, key=name, applicability='NOT_APPLICABLE',
                                     criterion=WEAROUT_NA_CRITERION % (entry.title, ref, basis,
                                                                       catalog.LIFE_EVENTS[entry.event]),
                                     trigger=trigger)
                row['mission_profile'] = named
                continue
            counted = ('%s %g 次' % (catalog.LIFE_EVENTS[entry.event], count)) if count is not None else ''
            row = self.add_check('DEV-C06', {'ref': ref, 'wearout': name}, key=name,
                                 criterion=WEAROUT_CRITERION % (entry.title, ref, basis, entry.checks, entry.basis,
                                                                counted or '结论写成选型或 bom_constraint'),
                                 trigger=trigger, **wait)
            if named:
                row['mission_profile'] = named

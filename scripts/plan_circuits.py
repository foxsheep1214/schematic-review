#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""电路级与器件检查项（功能树设计 §3.8）：功能电路类型的发现与逐电路展开、电路功能框架、器件与引脚的证据计算、
阈值窗口，以及每块电路对它拥有的器件问的应力、电容和精度。ReviewPlanner 混入这里的方法。"""
import re

import board_intent
import catalog
import circuit_decisions
import row_owner
from audit_datasheets import datasheet_entry_for_ref
from checkers import powertree
from checkers.netgraph import (CAPACITOR, CONNECTOR, IC, MOSFET, RAIL_RE, RESISTOR, TESTPOINT, TVS, UNKNOWN, ZENER,
                               NetGraph, is_analog_sense_pair, is_ground, normalize)
from checkers.planutil import slug as _slug
from electrical_contract import bounded, finite
from interfaces import CONNECTOR_RE
from page_inventory import LIMITED
from plan_board import _material_available, _text

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

SENSOR_RE = re.compile(r'THERMISTOR|NTC|PTC|\bRTD\b|PT100|THERMOCOUPLE|热敏', re.I)

GROUND_RE = re.compile(r'^([A-Z]{0,2}GND[A-Z0-9]{0,3}|[AD]?VSS[A-Z0-9]{0,3}|EP|PAD)$', re.I)

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
        undetected = []
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
                missing = []
            elif applicability == 'UNDETERMINED':
                missing = [f'intent.features.{name}']
                if requested == 'NOT_APPLICABLE' and confirmed:
                    missing.append('resolve intent/netlist conflict')
            else:
                missing = self._materials_gap(kind.materials)
            if applicability == 'APPLICABLE' and requested == 'APPLICABLE' and not found:
                self.diagnostics.append({
                    'code': 'REQUIRED_FEATURE_NOT_DETECTED',
                    'feature': name,
                    'detail': '设计意图要求该功能，但网表未检测到对应特征',
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
            if unassigned:
                criterion += '；候选生成没有归属的器件，逐颗确认属于哪个功能或为何不审：' + '、'.join(unassigned)
            self.add_check(
                'REQ-Q08', {'board': 'BOARD', 'circuit_types': undetected, 'unassigned': unassigned},
                criterion=criterion,
                readiness='WAITING_EVIDENCE',
                required_inputs=[f'intent.features.{name}' for name in undetected]
                + [f'intent.circuit_decisions: add/reject for {ref}' for ref in unassigned],
                trigger=['circuit-type-discovery'] + (['circuit-candidates:unassigned'] if unassigned else []))

    def _rail_window(self, nets):
        """电路网络里 intent.power_rails 给了电压窗口的轨；没有就 None（问题写“需求未给窗口”）。"""
        rails = self.intent.get('power_rails') or {}
        parts = []
        for net in nets:
            window = (rails.get(net) or {}).get('voltage_v') if isinstance(rails.get(net), dict) else None
            if isinstance(window, dict) and finite(window.get('min')) and finite(window.get('max')):
                parts.append(f'{net} {window["min"]}–{window["max"]} V')
        return '、'.join(parts) or None

    def plan_subjects(self, kind, circuits, missing):
        """声明了电路则逐电路×工况展开电路检查项并建功能框架（答案不随工作态变化的规则每电路一行），
        否则按功能电路展开一次；已有 I²C 区域时由检查器逐区域展开。"""
        members = []
        for circuit in circuits:
            refs = circuit['refs']
            gaps = [f'datasheet:{ref}' for ref in refs
                    if not (datasheet_entry_for_ref(self.datasheet_audit, ref) or {}).get('status') == 'AVAILABLE']
            gaps += [f'unknown ref:{ref}' for ref in refs if ref not in self.db.get('parts', {})]
            trigger = f'intent.circuits:{circuit["citation"]}'
            for index, state in enumerate(circuit['states']):
                for rule in kind.subjects:
                    invariant = rule in catalog.STATE_INVARIANT
                    if invariant and index:
                        continue   # asked once per circuit, with the first state's rows
                    obj = {'circuit': circuit['id'], 'circuit_key': '+'.join(sorted(circuit.get('candidate_ids') or [circuit['id']])),
                           'ref': refs[0], 'refs': refs, 'nets': circuit.get('nets', [])}
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
                'blind_spots': {rule: catalog.explanation(rule)['risk_if_omitted'] for rule in kind.subjects},
                'checklist': list(catalog.BOUNDING_STEPS),
            }
        for rule, obj, key, gaps, trigger in members:
            frame = frames.get(obj.get('circuit'))
            item = self._ready_check(rule, dict(obj), gaps, [trigger], key=key)
            item['circuit_type'] = kind.name
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

        # 证据计算：反馈分压、使能、strap 与 I2C 上拉。
        for node, pin in sorted(pinname.items()):
            net = pin2net.get(node)
            upper_pin = str(pin).strip().upper()
            ref = node.split('.')[0]
            if upper_pin in FB_NAMES and net:
                obj = {'node': node, 'net': net, 'ref': ref}
                ready = self.evidence_ready('PWR-E01', obj)
                self.add_check(
                    'PWR-E01', obj, readiness='READY' if ready else 'WAITING_EVIDENCE',
                    required_inputs=[] if ready else ['datasheet:Vref/目标窗口'],
                    trigger=[f'pinname:{pin}'])
            if net and (EN_RE.search(upper_pin) or (
                    EN_RE.search(net) and re.match(r'^[UMQ]\d', ref, re.I))):
                obj = {'node': node, 'net': net, 'ref': ref}
                ready = self.evidence_ready('RST-E01', obj)
                self.add_check(
                    'RST-E01', obj, readiness='READY' if ready else 'WAITING_EVIDENCE',
                    required_inputs=[] if ready else ['datasheet:pin function/Abs Max'],
                    trigger=[f'pinname:{pin}', f'net:{net}'])
            if net and (STRAP_RE.search(upper_pin) or (
                    STRAP_RE.search(net) and re.match(r'^[UMQ]\d', ref, re.I))):
                obj = {'node': node, 'net': net, 'ref': ref}
                ready = self.evidence_ready('RST-E02', obj)
                self.add_check(
                    'RST-E02', obj, readiness='READY' if ready else 'WAITING_EVIDENCE',
                    required_inputs=[] if ready else ['datasheet:strap table/mandatory wording'],
                    trigger=[f'pinname:{pin}', f'net:{net}'])

        i2c_nets = set()
        for net, nodes in nets.items():
            if I2C_RE.search(net) or any(
                    I2C_RE.search(str(pinname.get(node, ''))) for node in nodes):
                i2c_nets.add(net)
        for net in sorted(i2c_nets - pseudo):
            obj = {'net': net}
            ready = self.evidence_ready('SIG-E01', obj)
            self.add_check(
                'SIG-E01', obj, readiness='READY' if ready else 'WAITING_EVIDENCE',
                required_inputs=[] if ready else ['datasheet/platform:I2C pull requirement'],
                trigger=[f'net:{net}'])

        # 连接器：pin map（证据计算）、对端定义、未用针处置与对外防护逐个一项。
        connector_graph = NetGraph(board_intent.graph_db(db, self.kind_intent))
        for ref, part in sorted(db.get('parts', {}).items()):
            if part.get('nc') or not (CONNECTOR_RE.match(ref) or connector_graph.kind(ref) == CONNECTOR):
                continue
            connector_trigger = [f'refdes:{ref}',
                                 f'connector-kind:{connector_graph.basis(ref)}']
            obj = {'ref': ref}
            ready = self.evidence_ready('DEV-E01', obj)
            self.add_check(
                'DEV-E01', obj, readiness='READY' if ready else 'WAITING_EVIDENCE',
                required_inputs=[] if ready else ['connector drawing/opposite-side pinout'],
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

        def active_by_function(ref):
            return (ref in powered and len(connector_graph.pins_of(ref)) >= 3
                    and connector_graph.kind(ref) in (IC, UNKNOWN))

        for ref, part in sorted(db.get('parts', {}).items()):
            declared = ref in (self.intent.get('devices') or {})
            connector = CONNECTOR_RE.match(ref) or connector_graph.kind(ref) == CONNECTOR
            by_function = not DEVICE_RE.match(ref) and active_by_function(ref)
            if part.get('nc') or not (DEVICE_RE.match(ref) or by_function or (declared and not connector)):
                continue
            gaps, audit_trigger = self._datasheet_readiness(ref, part)
            trigger = ([f'refdes:{ref}', f'part:{part.get("part", "")}'] + audit_trigger
                       + (['native-power-pins:active-device'] if by_function else []))
            self._ready_check('DEV-D01', {'ref': ref}, gaps, trigger)
            self._disposition_check(ref, gaps, trigger)
            self._ready_check('DEV-C05', {'ref': ref}, gaps + self._materials_gap(['requirements']), trigger)

        self.plan_threshold_checks(connector_graph)

    def plan_threshold_checks(self, graph):
        """阈值型保护器件/门限脚两侧窗口（PRO-C02）与传感器开短路判别（ANA-C04），逐对象一项。"""
        db = self.db
        nets, pin2net = db.get('nets', {}), db.get('pin2net', {})
        names = dict(db.get('declared_pinname') or {}, **(db.get('pinname') or {}))
        parts = db.get('parts', {})
        requirements = self._materials_gap(['requirements'])

        def grounded(net):
            return is_ground(net) or bool(GROUND_RE.match(str(net).rsplit('/', 1)[-1]))

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
            if kind in (ZENER, TVS):
                gaps, audit = self._datasheet_readiness(ref, part)
                switch = gate_source_clamp(ref)
                window({'ref': ref}, gaps, [f'refdes:{ref}', f'device-kind:{kind}:{graph.basis(ref)}'] + audit
                       + ([f'gate-source-clamp:{switch}'] if switch else []), gate_clamp=bool(switch))
                continue
            if not SENSOR_RE.search(' '.join(str(part.get(k, '')) for k in ('part', 'value', 'prim'))):
                continue
            # 传感器接电源轨的一端只是偏置，不是检测脚；轨上 IC 的供电脚也不判别开短路。
            for net in sorted(set(graph.pins_of(ref).values())):
                if (not net or grounded(net) or net in db.get('pseudo_nets', [])
                        or rails.is_rail(net)):
                    continue
                for node in sorted(nets.get(net, [])):
                    owner = node.split('.')[0]
                    if (owner == ref or graph.kind(owner) != IC or GROUND_RE.match(normalize(names.get(node)))
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
        """DEV-C01/C02/C03 每块电路对它拥有的器件一行（按 OWNED_PART_KINDS 取器件），没有电路拥有的器件全板一行。"""
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

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""感性负载续流与钳位检查器。

识别继电器线圈、由开关驱动的电感/绕组以及经连接器外接的感性负载，登记每个
装配状态下的钳位路径。只回答"有没有、接法对不对、缺什么证据"；额定值是否
足够由工程计算（DRV-C01）按器件资料判定。外置升压及有出处的反激绕组按各自用途
建项；其他集成开关电源储能电感不套普通线圈模型。
"""
import re

import catalog
from . import inventory as inv
from . import netgraph as ng
from . import powertree
from . import states as state_lib
from .base import Checker
from .planutil import slug

SWITCH_KINDS = {ng.MOSFET, ng.BJT}
CLAMP_KINDS = {ng.DIODE, ng.TVS, ng.ZENER}
LOAD_KINDS = {ng.RELAY, ng.INDUCTOR, ng.TRANSFORMER}
DRIVER_PIN_RE = re.compile(r'^(OUT\w*|DRV\w*|O\d+|HO|LO|SOURCE\d*|SINK\d*)$', re.I)
INTEGRATED_CLAMP_RE = re.compile(r'^(COM|CLAMP\w*|VS|FREEWHEEL\w*)$', re.I)
LOAD_NAME_RE = re.compile(r'(^|_)(MOTOR|SOLENOID|VALVE|COIL|RELAY|PUMP|BRAKE|FAN|ACTUATOR)\w*(_|$)', re.I)
MAX_LOADS = 256
COMMON_MODE_INPUT_FILTER = 'common_mode_input_filter'
FLYBACK_TRANSFORMER = 'flyback_transformer'


def _flyback_winding_errors(item, db):
    """A cited physical winding map; never infer isolation or pair from names."""
    if item.get('kind') != FLYBACK_TRANSFORMER:
        return []
    if not isinstance(item.get('citation'), str) or not item['citation'].strip():
        return ['flyback_transformer needs a winding/polarity citation']
    ws = item.get('windings')
    if not isinstance(ws, list) or len(ws) < 2:
        return ['flyback_transformer needs primary and secondary winding maps']
    pins, roles = [], []
    for winding in ws:
        if not isinstance(winding, dict) or set(winding) != {'role', 'pins', 'dot'}:
            return ['flyback winding needs exactly role/pins/dot']
        pair = winding['pins']
        if (winding['role'] not in ('primary', 'secondary', 'auxiliary')
                or not isinstance(pair, list) or len(pair) != 2
                or any(not isinstance(pin, str) or not pin.strip() for pin in pair)
                or winding['dot'] not in pair):
            return ['flyback winding needs a known role, two physical pins and one dot pin']
        pins.extend(pair)
        roles.append(winding['role'])
    if roles.count('primary') != 1 or 'secondary' not in roles or len(set(pins)) != len(pins):
        return ['flyback needs exactly one primary, a secondary and disjoint winding pins']
    if db is None:
        return []
    ref = item.get('ref')
    if not isinstance(ref, str) or ref not in db.get('parts', {}):
        return ['flyback winding map has an unknown transformer reference']
    graph = ng.NetGraph(db)
    actual = graph.pins_of(ref)
    # Unmapped pins are allowed only when they connect to nothing (NC or a single-pin net).
    unmapped = [pin for pin in actual if pin not in pins]
    if (graph.kind(ref) != ng.TRANSFORMER or not set(pins) <= set(actual)
            or any(ref + '.' + pin not in db.get('no_connect_nodes', [])
                   and actual[pin] not in graph.pseudo
                   and len(graph.nodes_on(actual[pin])) > 1 for pin in unmapped)):
        return ['flyback winding map must cover every connected transformer pin exactly once']
    primary = next(w for w in ws if w['role'] == 'primary')
    primary_nets = {graph.pin2net[ref + '.' + pin] for pin in primary['pins']}
    supply = graph.pin2net[ref + '.' + primary['dot']]
    switched = next(net for net in primary_nets if net != supply) if len(primary_nets) == 2 else None
    if ((item.get('rail_net') is not None and item['rail_net'] != supply)
            or (item.get('switch_net') is not None and item['switch_net'] != switched)):
        return ['flyback declared switch/supply nets conflict with winding map']
    for winding in ws:
        nodes = [ref + '.' + pin for pin in winding['pins']]
        nets = {graph.pin2net[node] for node in nodes}
        if (len(nets) != 2 or nets & graph.pseudo
                or any(n in db.get('no_connect_nodes', []) for n in nodes)):
            return ['flyback winding contains shorted, pseudo or NC terminals']
        if winding['role'] == 'secondary' and nets & primary_nets:
            return ['flyback primary and secondary share a net; isolation cannot be assumed']
        for node in nodes:
            for field in ('native_pintype', 'declared_native_pintype'):
                role = db.get(field, {}).get(node)
                if role and role != 'passive':
                    return ['flyback winding contains a non-passive pin: ' + node]
    return []


def _filter_winding_errors(item, db):
    """Validate an explicit two-winding declaration, never infer pin pairing."""
    if item.get('kind') != COMMON_MODE_INPUT_FILTER:
        if item.get('kind') == FLYBACK_TRANSFORMER:
            return []
        return ['windings only applies to common_mode_input_filter'] if 'windings' in item else []
    if not isinstance(item.get('citation'), str) or not item['citation'].strip():
        return ['common_mode_input_filter needs a classification citation']
    if item.get('switch_net') is not None or item.get('rail_net') is not None:
        return ['common_mode_input_filter conflicts with switched-load net declarations']
    windings = item.get('windings')
    if (not isinstance(windings, list) or len(windings) != 2
            or any(not isinstance(pair, list) or len(pair) != 2
                   or any(not isinstance(pin, str) or not pin.strip() for pin in pair)
                   for pair in windings)):
        return ['common_mode_input_filter needs two explicit winding pin pairs']
    pins = [pin for pair in windings for pin in pair]
    if len(set(pins)) != 4:
        return ['common_mode_input_filter winding pins must be distinct']
    if db is None:
        return []
    ref = item.get('ref')
    if ng.NetGraph(db).kind(ref) not in (ng.INDUCTOR, ng.TRANSFORMER):
        return ['common_mode_input_filter requires an inductor/transformer component']
    actual = {node.partition('.')[2] for node in db.get('pin2net', {})
              if node.partition('.')[0] == ref}
    if set(pins) != actual:
        return ['common_mode_input_filter windings must cover all four actual physical pins']
    nodes = [ref + '.' + pin for pin in pins]
    nets = [db['pin2net'][node] for node in nodes]
    if (len(set(nets)) != 4 or any(net in db.get('pseudo_nets', []) or ng.is_ground(net)
                                 for net in nets)
            or any(node in db.get('no_connect_nodes', []) for node in nodes)):
        return ['common_mode_input_filter needs four distinct connected, non-ground nets']
    for node in nodes:
        for field in ('native_pintype', 'declared_native_pintype'):
            role = db.get(field, {}).get(node)
            if role and role != 'passive':
                return ['common_mode_input_filter has a non-passive physical pin: ' + node]
    return []


def validate_inductive_intent(intent, db=None):
    """校验可选的 inductive_loads 配置段。"""
    errors = state_lib.section_errors(
        intent, db, 'inductive_loads', item_field='loads', item_key='load',
        fields=('id', 'ref', 'kind', 'switch_net', 'rail_net', 'citation', 'windings'),
        net_fields=('switch_net', 'rail_net'))
    cfg = intent.get('inductive_loads') if isinstance(intent, dict) else None
    items = cfg.get('loads', []) if isinstance(cfg, dict) else []
    for item in items if isinstance(items, list) else []:
        if isinstance(item, dict):
            errors.extend('inductive_loads: ' + message
                          for message in _filter_winding_errors(item, db))
            errors.extend('inductive_loads: ' + message
                          for message in _flyback_winding_errors(item, db))
            if item.get('kind') in (COMMON_MODE_INPUT_FILTER, FLYBACK_TRANSFORMER) and sum(
                    isinstance(other, dict) and other.get('ref') == item.get('ref')
                    for other in items) != 1:
                errors.append('inductive_loads: winding-map ref has duplicate declarations')
    return errors


class _Scan:
    """单一装配状态下的识别过程。"""

    def __init__(self, db, state, declared, excluded, filters=None, flybacks=None):
        self.db = db
        self.graph = ng.NetGraph(db, fitted=set(state['fitted']))
        self.tree = powertree.PowerTree(self.graph)
        self.state = state
        self.declared = declared
        self.excluded = excluded
        self.filters = filters or {}
        self.flybacks = flybacks or {}

    def _flyback(self, ref, kind):
        declaration = self.flybacks.get(ref)
        if declaration is None or kind != ng.TRANSFORMER:
            return None
        graph = self.graph
        gaps = _flyback_winding_errors(declaration, self.db)
        if gaps:
            return self._entry(ref, kind, None, None, None, 'declared', gaps)
        windings = [{**w, 'nodes': [ref + '.' + p for p in w['pins']],
                     'nets': [graph.pin2net[ref + '.' + p] for p in w['pins']]}
                    for w in declaration['windings']]
        primary = next(w for w in windings if w['role'] == 'primary')
        switched = [(net, self._switch_on(net)[0]) for net in primary['nets']]
        switched = [(net, sw) for net, sw in switched if sw is not None]
        if len(switched) != 1:
            return self._entry(ref, kind, None, None, None, 'declared',
                               ['flyback-primary:need-one-identified-switch'])
        switch_net, switch_ref = switched[0]
        switches = [sw for sw in graph.refs_on(switch_net) if graph.kind(sw) in SWITCH_KINDS
                    and graph.node_named(sw, 'drain')
                    and graph.pin2net[graph.node_named(sw, 'drain')] == switch_net]
        if len(switches) > 1:
            return self._entry(ref, kind, None, None, None, 'declared',
                               ['flyback-primary:ambiguous-parallel-switches'])
        rail_net = next(net for net in primary['nets'] if net != switch_net)
        if graph.pin2net[ref + '.' + primary['dot']] != rail_net:
            gaps.append('flyback-primary-dot:verify-switched-winding-polarity')
        entry = self._entry(ref, kind, switch_net, rail_net, switch_ref, 'declared', gaps)
        rcd = []
        for diode, middle in graph.neighbors(switch_net, {ng.DIODE}):
            if middle == rail_net:
                continue
            capacitors = graph.between(middle, rail_net, {ng.CAPACITOR})
            resistors = graph.between(middle, rail_net, {ng.RESISTOR})
            if not capacitors or not resistors:
                continue
            anode, cathode = (graph.node_named(diode, role) for role in ('anode', 'cathode'))
            orientation = ('unknown' if not anode or not cathode else
                           'forward' if graph.pin2net[anode] == switch_net else 'reversed')
            rcd.append({'ref': diode, 'type': 'flyback-rcd', 'orientation': orientation,
                        'across': 'primary', 'capacitors': capacitors, 'resistors': resistors,
                        'clamp_net': middle, 'return_net': rail_net})
        # Without an RCD, a TVS/zener across the switch or the primary is the leakage clamp;
        # its clamp voltage must exceed Vin + reflected voltage (rated in DRV-C01).
        leakage = rcd or [dict(c, leakage_clamp=True) for c in entry['clamps']
                          if c['type'].endswith(('-' + ng.TVS, '-' + ng.ZENER))]
        if rcd:
            entry['clamps'] = rcd
            entry['gaps'] = [gap for gap in entry['gaps'] if gap != 'clamp:none-found']
        elif leakage:
            entry['clamps'] = leakage
            entry['gaps'] = [gap for gap in entry['gaps'] if gap != 'clamp:none-found']
            entry['gaps'] += ['flyback-tvs-clamp-polarity:unknown:' + c['ref'] for c in leakage
                              if c['orientation'] == 'unknown']
        else:
            entry['gaps'].append('flyback-rcd:not-recognised')
        if len(rcd) > 1:
            entry['gaps'].append('flyback-rcd:ambiguous-multiple-branches')
        for branch in rcd:
            if branch['orientation'] != 'forward':
                entry['gaps'].append('flyback-rcd-diode:' + branch['orientation'])
        entry.update(application=FLYBACK_TRANSFORMER, windings=windings,
                     classification_citation=declaration['citation'],
                     energy_paths={
                         'on': {'winding_nodes': primary['nodes'], 'switch_ref': switch_ref,
                                'switch_channel': 'conducting', 'action': 'magnetizing-energy-storage'},
                         'off_main': {'switch_channel': 'open', 'blocked_refs': [switch_ref],
                                      'to_windings': [w['nodes'] for w in windings if w['role'] != 'primary'],
                                      'action': 'coupled-energy-transfer; rectifiers/polarity/returns need review'},
                         'off_leakage': {'from': switch_net, 'to': rail_net, 'branches': leakage,
                                         'action': 'leakage-clamp; not the entire magnetizing energy'},
                         'isolation': 'winding maps are local evidence only; no conductive graph edges added'})
        entry['gaps'] = sorted(set(entry['gaps']))
        return entry

    def _input_filter(self, ref, kind):
        """Return a traceable scope decision, not a component-performance PASS.

        The reviewer supplies the use and physical winding map with a citation.
        Known series passive paths are inspected for contradictory active drive;
        this never adds winding edges to the shared graph or joins L/N.
        """
        declaration = self.filters.get(ref)
        if declaration is None or kind not in (ng.INDUCTOR, ng.TRANSFORMER):
            return None
        gaps = _filter_winding_errors(declaration, self.db)
        nets = self.graph.nets_of(ref)
        if not gaps:
            # Do not let an exclusion of another device hide a real switch.
            pending, seen = list(nets), set()
            while pending:
                net = pending.pop()
                if net in seen:
                    continue
                seen.add(net)
                for other in self.graph.refs_on(net):
                    if self.graph.kind(other) in SWITCH_KINDS:
                        gaps.append('common-mode-filter-active-node:' + net)
                for node in self.graph.nodes_on(net):
                    other, _, pin = node.partition('.')
                    if self.graph.is_fitted(other) and self.graph.kind(other) == ng.IC and (
                            ng.name_matches(DRIVER_PIN_RE, self.graph.pinname.get(node), pin)
                            or ng.name_matches(powertree.SWITCH_NODE_PIN_RE,
                                               self.graph.pinname.get(node), pin)):
                        gaps.append('common-mode-filter-active-node:' + net)
                pending.extend(other for _, other in self.graph.neighbors(net, ng.PASSIVE_LINKS)
                               if other not in seen)
        entry = self._entry(ref, kind, None, None, None, 'declared', gaps)
        entry['classification_citation'] = declaration.get('citation')
        if not _filter_winding_errors(declaration, self.db):
            entry['windings'] = [
                {'pins': list(pair), 'nodes': [ref + '.' + pin for pin in pair],
                 'nets': [self.graph.pin2net[ref + '.' + pin] for pin in pair]}
                for pair in declaration['windings']]
        if not entry['gaps']:
            entry.update(id=slug(ref + '-common-mode-input-filter'),
                         application=COMMON_MODE_INPUT_FILTER,
                         applicability='NOT_APPLICABLE',
                         scope_reason='有出处的两绕组共模输入滤波用途，未发现相连的开关驱动；'
                                      '普通被切换线圈续流/钳位检查不适用。'
                                      '载流、绝缘、温升与滤波效果仍需按实际用途审查。')
        return entry

    def _switch_on(self, net):
        """返回 (switch_ref, evidence) —— 该网上的开关器件或驱动输出脚。"""
        graph = self.graph
        for ref in graph.refs_on(net):
            if ref in self.excluded:
                continue
            if graph.kind(ref) in SWITCH_KINDS:
                node = graph.node_named(ref, 'drain')
                if node and graph.pin2net.get(node) == net:
                    return ref, 'switch-drain:' + node
                if node is None:
                    return ref, 'switch:' + ref + '(pin roles unknown)'
        for node in graph.nodes_on(net):
            ref = node.partition('.')[0]
            if graph.kind(ref) != ng.IC or ref in self.excluded:
                continue
            if ng.name_matches(DRIVER_PIN_RE, graph.pinname.get(node), node.partition('.')[2]):
                return ref, 'driver-pin:' + node
        return None, None

    def _inferred_coil(self, ref):
        """符号无脚名的继电器：恰好一个脚网是开关节点，且其余脚网中恰好一个是电源轨或经单个
        二端无源件接到电源轨（线圈串联电阻），才把这两网当线圈端；否则不猜。"""
        graph = self.graph
        pins = graph.pins_of(ref)
        if any(graph.pinname.get(ref + '.' + pin) for pin in pins):
            return None
        nets = set(pins.values())
        switched = sorted(net for net in nets if self._switch_on(net)[0] is not None)
        if len(switched) != 1:
            return None
        high = {net for net in nets - set(switched)
                if self.tree.is_rail(net)
                or any(self.tree.is_rail(other) for _, other in graph.neighbors(net, ng.PASSIVE_LINKS))}
        return sorted(switched + sorted(high)) if len(high) == 1 else None

    def _is_converter_node(self, net):
        for node in self.graph.nodes_on(net):
            if ng.name_matches(powertree.SWITCH_NODE_PIN_RE, self.graph.pinname.get(node),
                               node.partition('.')[2]):
                return True
        return False

    def _resistive_return(self, start, target):
        """A bounded fitted resistor/jumper return, never through a capacitor or MOS."""
        queue, seen = [(start, [])], set()
        while queue:
            net, path = queue.pop(0)
            if net == target:
                return path
            if net in seen or len(path) >= 3:
                continue
            seen.add(net)
            queue.extend((other, path + [ref]) for ref, other in self.graph.neighbors(
                net, {ng.RESISTOR, ng.JUMPER}) if other not in seen)
        return None

    def _boost(self, ref, kind, switch_net, input_net, switch_ref, basis, gaps):
        """Recognise a discrete low-side boost shape, not its electrical fitness.

        Require physical D/S/G, an input capacitor and output capacitor sharing
        a return, and a diode between switch/output. Record reversed diodes too.
        MOS channel polarity, voltages, ratings and operating mode need review.
        """
        graph = self.graph
        if kind != ng.INDUCTOR or graph.kind(switch_ref) != ng.MOSFET:
            return None
        drain, source, gate = (graph.node_named(switch_ref, role)
                               for role in ('drain', 'source', 'gate'))
        if not all((drain, source, gate)) or graph.pin2net[drain] != switch_net:
            return None
        switches = [other for other in graph.refs_on(switch_net)
                    if graph.kind(other) in SWITCH_KINDS
                    and graph.node_named(other, 'drain')
                    and graph.pin2net[graph.node_named(other, 'drain')] == switch_net]
        if switches != [switch_ref]:
            return None
        candidates = []
        for diode, output in graph.neighbors(switch_net, {ng.DIODE}):
            if output in (input_net, switch_net) or ng.is_ground(output) or output in graph.pseudo:
                continue
            anode, cathode = (graph.node_named(diode, role) for role in ('anode', 'cathode'))
            if not anode or not cathode:
                continue
            for cap, ret in graph.neighbors(output, {ng.CAPACITOR}):
                if not ng.is_ground(ret):
                    continue
                inputs = graph.between(input_net, ret, {ng.CAPACITOR})
                path = self._resistive_return(graph.pin2net[source], ret)
                if inputs and path is not None:
                    candidates.append((diode, output, ret, inputs, path, anode, cathode))
        # Parallel output capacitors describe one topology, not ambiguity.
        unique = {(row[0], row[1], row[2]): row for row in candidates}
        if len(unique) != 1:
            return None
        diode, output, ret, inputs, path, anode, cathode = next(iter(unique.values()))
        orientation = 'forward' if graph.pin2net[anode] == switch_net else 'reversed'
        entry = self._entry(ref, kind, switch_net, input_net, switch_ref, basis, gaps)
        entry['gaps'] = [gap for gap in entry['gaps'] if gap != 'clamp:none-found']
        if orientation == 'reversed':
            entry['gaps'].append('boost-transfer-diode:reversed')
        caps = graph.between(output, ret, {ng.CAPACITOR})
        entry.update(application='boost_converter', output_net=output, return_net=ret,
                     input_capacitors=inputs, output_capacitors=caps,
                     switch_nodes={'drain': drain, 'source': source, 'gate': gate},
                     clamps=[{'ref': diode, 'type': 'boost-transfer-diode',
                              'orientation': orientation, 'across': 'converter',
                              'nodes': [anode, cathode]}],
                     switching_paths={
                         'on': {'from': input_net, 'to': ret,
                                'refs': [ref, switch_ref] + path,
                                'switch_channel': 'conducting', 'transfer_diode': 'blocking'},
                         'off': {'from': input_net, 'to': output,
                                 'refs': [ref, diode], 'switch_channel': 'open',
                                 'blocked_refs': [switch_ref],
                                 'return_branches': [{'refs': [cap], 'to': ret} for cap in caps]},
                         'boundary': '上游供电闭合输入/返回回路；这里只记录局部连接。'
                                     '路径按正常升压状态定义，方向、器件极性及工况须独立审查。'})
        return entry

    def _clamps(self, switch_net, rail_net):
        graph, found = self.graph, []
        for ref in graph.between(switch_net, rail_net, CLAMP_KINDS):
            anode = graph.node_named(ref, 'anode')
            cathode = graph.node_named(ref, 'cathode')
            if anode and cathode:
                orientation = ('forward' if graph.pin2net.get(anode) == switch_net
                               and graph.pin2net.get(cathode) == rail_net else 'reversed')
            else:
                orientation = 'unknown'
            found.append({'ref': ref, 'type': 'freewheel-' + graph.kind(ref),
                          'orientation': orientation, 'across': 'load'})
        for net in sorted({n for n in (self._grounds() | {rail_net}) if n != switch_net}):
            for ref in graph.between(switch_net, net, CLAMP_KINDS):
                if any(item['ref'] == ref for item in found):
                    continue
                found.append({'ref': ref, 'type': 'switch-clamp-' + graph.kind(ref),
                              'orientation': 'unknown', 'across': 'switch'})
        for ref, middle in graph.neighbors(switch_net, {ng.RESISTOR}):
            for cap in graph.between(middle, rail_net, {ng.CAPACITOR}):
                found.append({'ref': ref + '+' + cap, 'type': 'rc-snubber',
                              'orientation': 'n/a', 'across': 'load'})
            for ground in sorted(self._grounds()):
                for cap in graph.between(middle, ground, {ng.CAPACITOR}):
                    found.append({'ref': ref + '+' + cap, 'type': 'rc-snubber',
                                  'orientation': 'n/a', 'across': 'switch'})
        return sorted(found, key=lambda item: (item['ref'], item['type']))

    def _grounds(self):
        return {net for net in self.graph.nets if ng.is_ground(net)}

    def _integrated_clamp(self, switch_ref, rail_net):
        graph = self.graph
        if switch_ref is None or graph.kind(switch_ref) != ng.IC:
            return []
        for node, net in graph.pins_of(switch_ref).items():
            if net == rail_net and ng.name_matches(
                    INTEGRATED_CLAMP_RE, graph.pinname.get(switch_ref + '.' + node), node):
                return [{'ref': switch_ref, 'type': 'integrated-clamp-candidate',
                         'orientation': 'unknown', 'across': 'driver',
                         'node': switch_ref + '.' + node}]
        return []

    def loads(self):
        graph, found = self.graph, []
        for ref in sorted(graph.parts):
            if ref in self.excluded or not graph.is_fitted(ref):
                continue
            kind = graph.kind(ref)
            passive_filter = self._input_filter(ref, kind)
            if passive_filter is not None:
                found.append(passive_filter)
                continue
            flyback = self._flyback(ref, kind)
            if flyback is not None:
                found.append(flyback)
                continue
            if kind not in LOAD_KINDS:
                continue
            terminals = graph.terminals(ref)
            gaps = []
            if len(terminals) != 2:
                if kind == ng.RELAY:
                    coil = [graph.pin2net[node] for node in sorted(graph.pin2net)
                            if node.startswith(ref + '.') and graph.role(node) == 'coil']
                    terminals = sorted(set(coil))
                    if len(terminals) != 2:
                        terminals = self._inferred_coil(ref) or terminals
                        if len(terminals) == 2:
                            gaps.append('pin-roles-inferred:' + ref + '（符号无脚名，线圈脚按拓扑推断，按手册核对）')
                if len(terminals) != 2:
                    gaps.append('pin-roles:' + ref)
                    found.append(self._entry(ref, kind, None, None, None, 'topology', gaps))
                    continue
            switch_net = rail_net = switch_ref = None
            for candidate in terminals:
                sw, evidence = self._switch_on(candidate)
                if sw is not None:
                    switch_net, switch_ref = candidate, sw
                    rail_net = terminals[0] if terminals[1] == candidate else terminals[1]
                    break
            if switch_net is None:
                continue
            basis = 'declared' if ref in self.declared else 'topology'
            boost = self._boost(ref, kind, switch_net, rail_net, switch_ref, basis, gaps)
            if boost is not None:
                found.append(boost)
                continue
            if kind != ng.RELAY and self._is_converter_node(switch_net):
                continue
            found.append(self._entry(ref, kind, switch_net, rail_net, switch_ref, basis, gaps))
        found.extend(self._external_loads())
        return sorted(found, key=lambda item: item['id'])[:MAX_LOADS]

    def _external_loads(self):
        """经连接器外接、仅有网名线索的负载：只作候选，需 intent 确认。"""
        graph, found = self.graph, []
        for net in sorted(graph.nets):
            if not LOAD_NAME_RE.search(net) or net in graph.pseudo:
                continue
            switch_ref, _ = self._switch_on(net)
            connectors = [ref for ref in graph.refs_on(net) if graph.kind(ref) == ng.CONNECTOR]
            if switch_ref is None or not connectors:
                continue
            if any(item['switch_net'] == net for item in found):
                continue
            rails = [other for _, other in graph.neighbors(net) if self.tree.is_rail(other)]
            found.append(self._entry(connectors[0], 'external', net, rails[0] if rails else None,
                                     switch_ref, 'name-hint',
                                     ['intent.inductive_loads.loads: 外接负载需声明'],
                                     load_net=net))
        return found

    def _entry(self, ref, kind, switch_net, rail_net, switch_ref, basis, gaps, load_net=None):
        clamps = []
        if switch_net and rail_net:
            clamps = self._clamps(switch_net, rail_net) + self._integrated_clamp(switch_ref, rail_net)
        entry_gaps = list(gaps)
        if switch_net and rail_net and not clamps:
            entry_gaps.append('clamp:none-found')
        if any(item['orientation'] == 'unknown' and item['across'] == 'load' for item in clamps):
            entry_gaps.append('clamp-orientation:pin roles unknown')
        return {
            'id': slug(ref + '-' + (switch_net or 'unresolved')),
            'ref': ref,
            'kind': kind if isinstance(kind, str) else str(kind),
            'basis': basis,
            'switch_net': switch_net,
            'switch_ref': switch_ref,
            'rail_net': rail_net,
            'load_net': load_net,
            'clamps': clamps,
            'gaps': sorted(set(entry_gaps + self.state['gaps'])),
        }


def build_inventory(db, intent=None):
    """生成逐状态的感性负载与钳位清单。"""
    cfg = (intent or {}).get('inductive_loads') if isinstance(intent, dict) else None
    declared = state_lib.declared_refs(cfg, 'loads')
    excluded = state_lib.excluded_refs(cfg)
    filters = {item['ref']: item for item in (cfg or {}).get('loads', [])
               if isinstance(item, dict) and isinstance(item.get('ref'), str)
               and item.get('kind') == COMMON_MODE_INPUT_FILTER
               and sum(isinstance(other, dict) and other.get('ref') == item['ref']
                       for other in cfg.get('loads', [])) == 1}
    flybacks = {item['ref']: item for item in (cfg or {}).get('loads', [])
                if isinstance(item, dict) and isinstance(item.get('ref'), str)
                and item.get('kind') == FLYBACK_TRANSFORMER
                and sum(isinstance(other, dict) and other.get('ref') == item['ref']
                        for other in cfg.get('loads', [])) == 1}
    gaps = [] if cfg else ['intent.inductive_loads: 未声明感性负载']
    return inv.build(db, intent, 'inductive_loads', 'loads',
                     lambda state: _Scan(db, state, declared, excluded, filters, flybacks).loads(), gaps)


class InductiveLoadChecker(Checker):
    id = 'inductive_load'
    title = '感性负载续流与钳位'
    plan_key = 'inductive_load'
    version_key = 'inductive_load_version'
    version = 1
    intent_key = 'inductive_loads'
    cold_rules = catalog.titles(method='A', source='inductive_load')

    missing_inventory_message = 'inductive load checks require their inventory'
    inventory_type_message = 'inductive load inventory must be an object'
    requires_db_message = 'inductive load inventory validation requires --db'
    stale_message = 'inductive load inventory/binding is stale or modified'
    invalid_message = 'invalid inductive load inventory: '

    def incomplete_message(self, key):
        return key + ': incomplete inductive load planned coverage'

    def changed_message(self, key):
        return key + ': inductive load generated criterion/object changed'

    def validate_intent(self, intent, db):
        return validate_inductive_intent(intent, db)

    def build(self, db, intent):
        return build_inventory(db, intent)

    def plan(self, planner, inventory):
        for state, load, same in inv.walk_distinct(inventory, 'loads'):
            obj = {'ref': load['ref'], **inv.state_fields(same),
                   'inductive_load': load['id'],
                   'inductive_load_digest': inventory['digest']}
            if load['switch_net']:
                obj['net'] = load['switch_net']
                obj['nets'] = sorted({x for x in (load['switch_net'], load['rail_net']) if x})
            applicability = 'UNDETERMINED' if load['basis'] == 'name-hint' else 'APPLICABLE'
            passive_filter = load.get('applicability') == 'NOT_APPLICABLE'
            boost = load.get('application') == 'boost_converter'
            flyback = load.get('application') == FLYBACK_TRANSFORMER
            if boost:
                obj.update(application='boost_converter', refs=sorted({load['ref'], load['switch_ref']}
                           | set(load['input_capacitors'] + load['output_capacitors'])
                           | set(load['switching_paths']['on']['refs'])
                           | {clamp['ref'] for clamp in load['clamps']}),
                           nets=sorted({load['rail_net'], load['switch_net'],
                                        load['output_net'], load['return_net']}))
            if flyback:
                refs = {load['ref'], load['switch_ref']}
                for branch in load['clamps']:
                    refs.update([branch['ref']] + branch.get('capacitors', []) + branch.get('resistors', []))
                obj.update(application=FLYBACK_TRANSFORMER, refs=sorted(refs),
                           nodes=sorted(n for w in load['windings'] for n in w['nodes']),
                           nets=sorted({n for w in load['windings'] for n in w['nets']}
                                       | {b['clamp_net'] for b in load['clamps'] if b['type'] == 'flyback-rcd'}))
            if passive_filter:
                applicability = 'NOT_APPLICABLE'
            trigger = ['inductive-load:' + load['id'], 'basis:' + load['basis']]
            if passive_filter:
                trigger.extend([load['scope_reason'], load['classification_citation']])
            if boost:
                trigger.append('topology:boost-converter; switching paths in inventory; ratings not assessed')
            if flyback:
                trigger.extend(['topology:flyback-transformer; winding/energy paths in inventory',
                                load['classification_citation']])
            item = planner.add_check(
                'DRV-T01', dict(obj), key=load['id'], applicability=applicability,
                criterion=('按升压用途逐物理脚核导通储能、关断经升压二极管送能及输出返回路径；'
                           '关断路径不得经过已关断MOS主通道，核二极管方向、贴装和真实工作模式；'
                           '路径存在不等于额定通过' if boost else
                           '按有出处的绕组/同名端核反激储能和关断次级送能，独立核漏感RCD吸收（或跨开关/初级的TVS钳位）的方向、'
                           '贴装及返回路径；不得把全部磁化能量算进RCD或将绕组并成导电网络'
                           if flyback else None),
                readiness='WAITING_EVIDENCE' if load['gaps'] else 'READY',
                required_inputs=load['gaps'],
                trigger=trigger)
            item['inventory_gaps'] = load['gaps']
            item = planner.add_check(
                'DRV-C01', dict(obj), key=load['id'], applicability=applicability,
                criterion=('按升压实际工况分别核二极管反向耐压、重复峰值/平均/RMS电流与损耗，'
                           'MOS耐压/电流、储能电感饱和及母线电容应力；'
                           '非重复浪涌额定不能代替重复工作保证，拓扑识别不自动通过额定' if boost else
                           '按反激漏感、关断峰流、反射电压和重复频率计算RCD钳位电压及纹波（TVS钳位则核钳位电压高于输入+反射电压且低于MOS耐压）、MOS峰压、'
                           '电阻平均/脉冲损耗和二极管/电容应力；区分磁化与漏感能量、正常与保护状态，'
                           '受控假设不当作已保证边界' if flyback else None),
                readiness='READY' if passive_filter else 'WAITING_EVIDENCE',
                required_inputs=[] if passive_filter else sorted(set(load['gaps'] + ([
                    'datasheet:升压二极管适用温区的反压/重复工作电流与损耗',
                    'intent:输入/母线电压、限流及CrM/DCM工作包络',
                    'datasheet:MOS、电感与母线电容额定及对应工况'] if boost else [
                    'intent:磁化电感/漏感、变比、峰流/频率及正常/保护包络',
                    'datasheet:RCD阻容公差、平均/脉冲与温度额定，二极管动态条件',
                    'calculation:钳位电压与纹波、反射电压、MOS/二极管/电容应力'] if flyback else [
                    'datasheet:钳位器件额定值', 'datasheet:开关器件耐压',
                    'intent:线圈电阻/电感与电源最高电压']))),
                trigger=trigger if passive_filter or boost or flyback else ['inductive-load:' + load['id']])
            item['analysis_required'] = not passive_filter
            item['inventory_gaps'] = load['gaps']

    def cold_findings(self, lint, inventory):
        for state in inventory['states']:
            for load in state['loads']:
                if load['basis'] == 'name-hint' or not load['switch_net']:
                    continue
                detail_head = '%s（%s，状态 %s）: 开关节点 %s' % (
                    load['ref'], load['kind'], state['id'], load['switch_net'])
                if not load['clamps']:
                    lint.add('DRV-A01', self.cold_rules['DRV-A01'],
                             detail_head + ' 与 ' + str(load['rail_net'])
                             + ' 之间未见续流二极管、钳位器件或 RC 吸收；'
                               '若由驱动器内部钳位需给出资料证据',
                             load['ref'])
                for clamp in load['clamps']:
                    if clamp['orientation'] == 'reversed':
                        description = ('升压二极管阴极接开关节点、阳极接输出母线，方向与关断送能相反'
                                       if clamp['type'] == 'boost-transfer-diode' else
                                       '反激RCD二极管方向与漏极向吸收电容充电相反'
                                       if clamp['type'] == 'flyback-rcd'
                                       else '阴极接在开关节点、阳极接电源，导通方向与续流相反')
                        lint.add('DRV-A02', self.cold_rules['DRV-A02'],
                                 detail_head + '：' + clamp['ref']
                                 + ' ' + description,
                                 load['ref'])

    def rule_instances(self, rule, inventory):
        return sorted({load['id'] for state in inventory['states'] for load in state['loads']
                       if load['basis'] != 'name-hint' and load['switch_net']})

    def binds(self, item):
        obj = item.get('object')
        return isinstance(obj, dict) and bool(obj.get('inductive_load'))

    def object_errors(self, key, obj, inventory):
        known = {load['id'] for state in inventory['states'] for load in state['loads']}
        if obj.get('inductive_load') not in known or obj.get('inductive_load_digest') != inventory['digest']:
            return [key + ': stale inductive load object binding']
        return []

    def pass_blockers(self, key, planned, generated, inventory):
        if generated and generated.get('inventory_gaps'):
            return [key + ': inductive load gaps must be resolved in a regenerated plan before PASS']
        return []

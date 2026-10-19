#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""功率开关：栅极驱动、开关节点吸收与安全工作区检查器。

按引脚角色识别分立开关管，登记每个装配状态下的栅极驱动源、栅源下拉、
开关节点上的感性元件与吸收网络。栅源驱动窗口由证据计算（DRV-E01）按资料保证值判定；
安全工作区、死区、自举欠压及热相关电气前提由专家按器件资料判定；实际热实现移交下游。
"""
import re

import catalog
from . import inventory as inv
from . import netgraph as ng
from . import powertree
from . import states as state_lib
from . import hotmath
from solve_dividers import parse_resistor
from decoupling import parse_capacitance
from .base import Checker
from .planutil import slug

SWITCH_KINDS = {ng.MOSFET, ng.BJT}
CLAMP_KINDS = {ng.DIODE, ng.TVS, ng.ZENER}
INDUCTIVE_KINDS = {ng.INDUCTOR, ng.TRANSFORMER, ng.RELAY}
DRIVER_PIN_RE = re.compile(r'^(HO|LO|HB|OUT\w*|DRV\w*|GATE\w*|SRC|SINK|O\d+)$', re.I)
OUT_PINTYPES = {'OUT', 'OUTPUT', 'BI', 'BIDI', 'BIDIR', 'BIDIRECTIONAL', 'IO', 'I/O',
                'TRISTATE', '3STATE'}
MAX_SWITCHES = 256
LINEAR_ROLES = {'linear', 'source_follower', 'emitter_follower'}
# 栅极接低侧轨的双向开漏电平转换管：不是功率开关，按所属电平转换电路（SIG-C07/C08/C09/T04）审查。
LEVEL_SHIFTER_ROLE = 'level_shifter'
SYNC_RECTIFIER_ROLE = 'synchronous_rectifier'
SR_PIN_NAMES = {'sense_node': re.compile(r'^(VD|VDS|DRAIN|D|DS|VDET|SENSE|CS)$', re.I),
                'return_node': re.compile(r'^(VS|VSS|SOURCE|SRC|S|GND|PGND|SGND)$', re.I)}


def validate_power_switch_intent(intent, db=None):
    """校验可选的 power_switches 配置段。"""
    errors = state_lib.section_errors(
        intent, db, 'power_switches', item_field='switches', item_key='switch',
        fields=('id', 'ref', 'role', 'gate_net', 'citation', 'source_return', 'synchronous_rectifier'),
        net_fields=('gate_net',))
    if errors or not isinstance(intent, dict) or 'power_switches' not in intent:
        return errors
    for item in intent['power_switches'].get('switches', []):
        if 'role' in item and (not isinstance(item['role'], str) or not item['role'].strip()):
            errors.append('power_switches: role must be a non-empty string when supplied')
        sync = item.get('synchronous_rectifier')
        if sync is not None or item.get('role') == SYNC_RECTIFIER_ROLE:
            required = {'controller_ref', 'channel', 'citation'}
            optional = {'sense_node', 'return_node', 'output_net', 'winding_nodes'}
            given = (lambda k: isinstance(sync, dict) and sync.get(k) is not None)
            wn = sync.get('winding_nodes') if isinstance(sync, dict) else None
            valid = (isinstance(sync, dict) and required <= set(sync) <= required | optional
                     and all(isinstance(sync[k], str) and sync[k].strip()
                             for k in (required | optional) - {'winding_nodes'} if given(k))
                     and sync['channel'] == 'n'
                     and (wn is None or (isinstance(wn, list) and len(wn) == 2
                          and all(isinstance(n, str) and n.strip() for n in wn)
                          and len(set(wn)) == 2)))
            if item.get('role') != SYNC_RECTIFIER_ROLE or not valid:
                errors.append('power_switches: synchronous_rectifier needs cited N-channel physical map')
            elif db is not None and (sync['controller_ref'] not in db.get('parts', {})
                    or any(n not in db.get('pin2net', {}) for n in
                           [sync.get(k) for k in ('sense_node', 'return_node') if given(k)] + (wn or []))
                    or (given('output_net') and sync['output_net'] not in db.get('nets', {}))):
                errors.append('power_switches: synchronous_rectifier has unknown ref/node/net')
        ret = item.get('source_return')
        if ret is not None:
            valid = (isinstance(ret, dict) and set(ret) == {'ref', 'ground_net', 'citation'}
                     and all(isinstance(ret.get(k), str) and ret[k].strip() for k in ret))
            if not valid:
                errors.append('power_switches: source_return requires ref/ground_net/citation')
            elif (not ng.is_ground(ret['ground_net']) or (db is not None and
                  (ret['ref'] not in db.get('parts', {}) or ret['ground_net'] not in db.get('nets', {})))):
                errors.append('power_switches: source_return ref/ground_net unknown or not ground')
    return errors


class _Scan:
    """单一装配状态下的开关识别。"""

    def __init__(self, db, state, declared, excluded, winding_maps=None):
        self.graph = ng.NetGraph(db, fitted=set(state['fitted']))
        self.state = state
        self.declared = declared if isinstance(declared, dict) else {ref: {} for ref in declared}
        self.excluded = excluded
        self.winding_maps = winding_maps or []
        self.grounds = {net for net in self.graph.nets if ng.is_ground(net)}
        self.tree = powertree.PowerTree(self.graph)

    def _driver_pins(self, net, via):
        """网上的驱动输出脚；引脚名或引脚类型成立才算，名字本身不构成结论。"""
        found = []
        for node in self.graph.nodes_on(net):
            ref = node.partition('.')[0]
            if ref in self.excluded or not self.graph.is_fitted(ref):
                continue
            kind = self.graph.kind(ref)
            pin = node.partition('.')[2]
            pintype = ng.normalize(self.graph.pintype.get(node))
            if kind == ng.IC and (ng.name_matches(DRIVER_PIN_RE, self.graph.pinname.get(node), pin)
                                  or pintype in OUT_PINTYPES):
                found.append({'node': node, 'via': via, 'source': 'driver-pin'})
            elif kind in SWITCH_KINDS and self.graph.role(node) == 'drain':
                found.append({'node': node, 'via': via, 'source': 'discrete-stage'})
            elif kind == ng.CONNECTOR:
                found.append({'node': node, 'via': via, 'source': 'external'})
            elif kind == ng.OPTO and self.graph.role(node) not in ('anode', 'cathode'):
                found.append({'node': node, 'via': via, 'source': 'opto-output'})
        return found

    def drivers(self, gate_net):
        found = self._driver_pins(gate_net, 'direct')
        for ref, other in self.graph.neighbors(gate_net, ng.PASSIVE_LINKS):
            found.extend(self._driver_pins(other, 'series:' + ref))
        unique = {item['node'] + '|' + item['via']: item for item in found}
        return [unique[key] for key in sorted(unique)]

    def pulls(self, gate_net, source_net, gate_node=None):
        found = self._pulls_on(gate_net, source_net)
        if not found and gate_node:
            # A gate reached only through its own series resistor (parallel power MOSFETs each
            # with 47 R to a common drive node): the pull sits on the far side. One hop, <= 1 kR.
            series = self._lone_gate_resistor(gate_net, gate_node)
            if series:
                ref, other = series
                found = [dict(item, via='series:' + ref) for item in self._pulls_on(other, source_net)]
        return found

    def _pulls_on(self, net, source_net):
        found = []
        for ref, other in self.graph.neighbors(net, {ng.RESISTOR}):
            if other == source_net or other in self.grounds or self.tree.is_rail(other):
                found.append({'ref': ref, 'to': other,
                              'value': self.graph.parts.get(ref, {}).get('value')})
        return found

    def _lone_gate_resistor(self, gate_net, gate_node):
        graph = self.graph
        nodes = [n for n in graph.nodes_on(gate_net) if graph.is_fitted(n.partition('.')[0])]
        others = [n for n in nodes if n != gate_node]
        if len(others) != 1 or len(nodes) != 2:
            return None
        ref = others[0].partition('.')[0]
        if graph.kind(ref) != ng.RESISTOR:
            return None
        parsed = parse_resistor(str(graph.parts.get(ref, {}).get('value', '')).split('/')[0])
        if parsed is None or not 0 <= parsed['kohm'] <= 1.0:
            return None
        far = [n for n in graph.nets_of(ref) if n != gate_net]
        return (ref, far[0]) if len(far) == 1 else None

    def snubbers(self, drain_net, source_net, topology='unknown'):
        """开关节点到地/源/电源轨的吸收或钳位路径。

        跨负载接到电源轨的续流二极管也是钳位路径，不能只看漏源之间。
        """
        graph, found = self.graph, []
        targets = set(self.grounds)
        if source_net:
            targets.add(source_net)
        targets |= {other for _, other in graph.neighbors(drain_net)
                    if self.tree.is_rail(other) or other in self.grounds}
        # The far end of the inductor/primary winding is the supply side even when it is not a
        # recognised rail (e.g. a PFC bulk named BULK); RCD clamps return there.
        targets |= self._winding_supply_nets(drain_net)
        for target in sorted(targets):
            if target == drain_net:
                continue
            for ref in graph.between(drain_net, target, {ng.CAPACITOR}):
                found.append({'ref': ref, 'type': 'capacitor', 'to': target})
            for ref in graph.between(drain_net, target, CLAMP_KINDS):
                if graph.kind(ref) == ng.DIODE and not self._clamp_diode(ref, drain_net, target, topology):
                    continue
                found.append({'ref': ref, 'type': 'clamp-' + graph.kind(ref), 'to': target})
        for ref, middle in graph.neighbors(drain_net, {ng.RESISTOR}):
            for target in sorted(targets):
                for cap in graph.between(middle, target, {ng.CAPACITOR}):
                    found.append({'ref': ref + '+' + cap, 'type': 'rc-snubber', 'to': target})
        # RCD: switch node -> diode -> clamp node returned through a capacitor to a rail/ground
        # (the same branch the inductive-load inventory reports for a flyback primary).
        for diode, middle in graph.neighbors(drain_net, {ng.DIODE}):
            if not self._clamp_diode(diode, drain_net, middle, topology):
                continue
            if middle in targets:
                continue
            if self._boost_transfer(diode, drain_net, middle):
                found.append({'ref': diode, 'type': 'boost-transfer-diode', 'to': middle})
                continue
            for target in sorted(targets - {drain_net}):
                caps = graph.between(middle, target, {ng.CAPACITOR})
                if caps:
                    found.append({'ref': '+'.join([diode] + caps + graph.between(middle, target, {ng.RESISTOR})),
                                  'type': 'rcd-clamp', 'to': target})
        for item in found:
            # Boost: anode on the switch node, cathode on a rail fed from another rail through an
            # inductor on the same node. This is the main power path, not a parasitic snubber.
            if item['type'] == 'clamp-' + ng.DIODE and self._boost_transfer(item['ref'], drain_net, item['to']):
                item['type'] = 'boost-transfer-diode'
        return sorted(found, key=lambda item: (item['ref'], item['type']))

    def _forward_diode(self, diode, source, target):
        graph = self.graph
        anode, cathode = graph.node_named(diode, 'anode'), graph.node_named(diode, 'cathode')
        return bool(anode and cathode and graph.pin2net.get(anode) == source
                    and graph.pin2net.get(cathode) == target)

    def _clamp_diode(self, diode, drain, target, topology):
        # Low-side/Boost releases positive SW voltage toward the supply/output.
        # A high-side buck instead freewheels from ground into a negative-going SW; its supply
        # need not be a recognised rail (e.g. a PFC bulk named BULK), so only a low-side switch
        # rejects the ground-anode diode (there it merely parallels the body diode).
        return (self._forward_diode(diode, drain, target)
                or (target in self.grounds and not topology.startswith('low-side')
                    and self._forward_diode(diode, target, drain)))

    def _boost_transfer(self, diode, drain_net, target):
        """Forward rectifier into an output rail/storage, with an input inductor."""
        graph = self.graph
        if not self._forward_diode(diode, drain_net, target):
            return False
        if not (self.tree.is_rail(target) or self._has_storage(target)):
            return False
        return any(other != target for _, other in graph.neighbors(drain_net, {ng.INDUCTOR}))

    def _has_storage(self, net):
        for cap in self.graph.refs_on(net):
            if self.graph.kind(cap) == ng.CAPACITOR:
                value = parse_capacitance(self.graph.parts.get(cap, {}).get('value'))
                if (value is not None and value >= 1e-6
                        and any(n in self.grounds for n in self.graph.nets_of(cap))):
                    return True
        return False

    def _winding_supply_nets(self, drain_net):
        nets = {other for _, other in self.graph.neighbors(drain_net, {ng.INDUCTOR})}
        # An undeclared transformer on the switch node: its terminal that carries bulk storage
        # or is a rail is the primary supply the RCD clamp returns to. Other terminals
        # (secondary, auxiliary) are not supply candidates without a winding declaration.
        for ref in self.graph.refs_on(drain_net):
            if self.graph.kind(ref) == ng.TRANSFORMER and self.graph.is_fitted(ref):
                nets.update(n for n in self.graph.nets_of(ref)
                            if n != drain_net and n not in self.grounds
                            and (self.tree.is_rail(n) or self._has_storage(n)))
        # A relay coil may reach its supply through a resistor; a diode across the coil (switch node
        # to the coil's other terminal) is still its freewheel clamp.
        for ref in self.graph.refs_on(drain_net):
            if self.graph.kind(ref) == ng.RELAY:
                nets.update(n for n in self.graph.nets_of(ref) if n != drain_net)
        for declaration in self.winding_maps:
            if declaration.get('kind') != 'flyback_transformer':
                continue
            ref = declaration.get('ref')
            primary = next((w for w in declaration.get('windings', []) if w.get('role') == 'primary'), None)
            if not primary:
                continue
            pnets = [self.graph.pin2net.get(ref + '.' + p) for p in primary['pins']]
            if drain_net in pnets:
                nets.update(n for n in pnets if n and n != drain_net)
        return nets

    def _switch_node_evidence(self, drain_net, ref, source_net=None, topology='unknown'):
        """开关节点上是否有感性负载或半桥对管。"""
        reasons = []
        for other in self.graph.refs_on(drain_net):
            if other == ref or other in self.excluded:
                continue
            kind = self.graph.kind(other)
            if kind in INDUCTIVE_KINDS and not self._other_flyback_winding(other, drain_net):
                reasons.append('inductive:' + other)
            elif kind == ng.MOSFET and self._bridge_partner(other, drain_net, source_net, topology):
                reasons.append('half-bridge:' + other)
        for node in self.graph.nodes_on(drain_net):
            if ng.name_matches(powertree.SWITCH_NODE_PIN_RE, self.graph.pinname.get(node),
                               node.partition('.')[2]):
                reasons.append('converter-node:' + node)
        return sorted(set(reasons))

    def _bridge_partner(self, other, drain_net, source_net, topology):
        """Series arm in the same direction: the other MOSFET's source is this node and its drain
        goes on to a supply (rail or bulk storage). A PMOS hanging its source on a high-side
        switch's drain (BMS charge-detect) or a BJT pair is not a half-bridge."""
        if topology == 'high-side':
            return False
        graph = self.graph
        src, drn = graph.node_named(other, 'source'), graph.node_named(other, 'drain')
        if not (src and drn) or graph.pin2net.get(src) != drain_net:
            return False
        far = graph.pin2net.get(drn)
        if not far or far in (drain_net, source_net) or far in self.grounds:
            return False
        return self.tree.is_rail(far) or self._has_storage(far)

    def _other_flyback_winding(self, ref, net):
        """A declared flyback transformer's winding on a DC net (the rectified output: a rail or a
        net with direct uF-class storage capacitance) is not a switching node; the primary switch
        net and an SR drain on a secondary still are."""
        if not any(d.get('kind') == 'flyback_transformer' and d.get('ref') == ref for d in self.winding_maps):
            return False
        return self.tree.is_rail(net) or self._has_storage(net)

    def source_return(self, ref, source_net):
        """Cited single fitted sense resistor; never merge the source with ground."""
        cfg = self.declared.get(ref, {}).get('source_return')
        if cfg is None:
            return None, []
        graph = self.graph
        if not isinstance(cfg, dict) or not all(isinstance(cfg.get(k), str) and cfg[k].strip()
                                                for k in ('ref', 'ground_net', 'citation')):
            return None, ['source-return:' + ref]
        resistor, ground = cfg['ref'], cfg['ground_net']
        # A resistor hanging off a rail/high-side output is not a source reference.
        if (source_net in self.grounds or not ng.is_ground(ground) or
                self.tree.is_rail(source_net) or
                resistor not in graph.between(source_net, ground, {ng.RESISTOR})):
            return None, ['source-return:' + ref]
        value = str(graph.parts.get(resistor, {}).get('value', '')).split('/')[0]
        parsed = parse_resistor(value)
        if parsed is None or parsed['kohm'] < 0:
            return None, ['source-return-resistance:' + ref]
        return {'ref': resistor, 'ground_net': ground, 'source_net': source_net,
                'resistance_ohm': parsed['kohm'] * 1000,
                'citation': cfg['citation'], 'basis': 'cited-fitted-resistor-path',
                'source_offset_model': 'Vsource - Vground = Isource * Rreturn'}, []

    def synchronous_rectifier(self, ref, nets, drivers):
        """Cited low-side N-MOS flyback SR map; electrical timing remains unproved.

        Controller sense/return pins, the secondary winding and the output net
        may be omitted when the netlist gives exactly one candidate for each.
        """
        declared = self.declared.get(ref, {})
        if declared.get('role') != SYNC_RECTIFIER_ROLE:
            return None, []
        cfg, graph = declared.get('synchronous_rectifier'), self.graph
        gap = ['synchronous-rectifier-map:' + ref]
        if not isinstance(cfg, dict) or cfg.get('channel') != 'n' or not cfg.get('citation'):
            return None, gap
        controller = cfg.get('controller_ref')
        if (not graph.is_fitted(controller) or graph.kind(controller) != ng.IC
                or graph.kind(ref) != ng.MOSFET or not all(nets.values())
                or len(set(nets.values())) != 3):
            return None, gap
        derived = []

        def controller_pin(field, net):
            if cfg.get(field) is not None:
                return cfg[field]
            found = [controller + '.' + pin for pin, n in graph.pins_of(controller).items() if n == net]
            derived.append(field)
            if len(found) > 1:
                # Several pins on one net (e.g. VS and TRIG both on the source): the official
                # sense/return name decides; still ambiguous means no guess.
                named = [n for n in found if SR_PIN_NAMES[field].match(ng.normalize(graph.pinname.get(n)) or '')]
                found = named
            return found[0] if len(found) == 1 else None

        from .inductive_load import _flyback_winding_errors, FLYBACK_TRANSFORMER
        secondaries = []
        for declaration in self.winding_maps:
            tr = declaration.get('ref')
            if (declaration.get('kind') != FLYBACK_TRANSFORMER or not graph.is_fitted(tr)
                    or _flyback_winding_errors(declaration, graph.db)):
                continue
            secondaries += [(declaration, w) for w in declaration['windings'] if w['role'] == 'secondary']
        wn = cfg.get('winding_nodes')
        if wn is None:
            derived.append('winding_nodes')
            matches = [(d, w) for d, w in secondaries
                       if graph.pin2net.get(d['ref'] + '.' + w['dot']) == nets['drain']]
        else:
            matches = [(d, w) for d, w in secondaries if isinstance(wn, list)
                       and {d['ref'] + '.' + pin for pin in w['pins']} == set(wn)]
        if len(matches) != 1:
            return None, gap
        declaration, winding = matches[0]
        tr = declaration['ref']
        wn = [tr + '.' + pin for pin in winding['pins']]
        nodes = [controller_pin('sense_node', nets['drain']),
                 controller_pin('return_node', nets['source'])] + wn
        if (any(n not in graph.pin2net or n in graph.db.get('no_connect_nodes', [])
                or graph.pin2net.get(n) in graph.pseudo for n in nodes)):
            return None, gap
        if (any(n.partition('.')[0] != controller for n in nodes[:2])
                or graph.pin2net[nodes[0]] != nets['drain']
                or graph.pin2net[nodes[1]] != nets['source']
                or not any(d['node'].partition('.')[0] == controller for d in drivers)):
            return None, gap
        # Every parallel physical S/D/G pin must agree, not just the first pin.
        for pin in graph.pins_of(ref):
            node = ref + '.' + pin
            role = graph.role(node)
            if (role not in nets or graph.pin2net.get(node) != nets[role]
                    or node in graph.db.get('no_connect_nodes', [])):
                return None, gap
        dot = tr + '.' + winding['dot']
        other = next(n for n in wn if n != dot)
        output = cfg.get('output_net')
        if output is None:
            derived.append('output_net')
            output = graph.pin2net[other]
        nonsecondary = {graph.pin2net[tr + '.' + pin] for w in declaration['windings']
                        if w['role'] != 'secondary' for pin in w['pins']}
        if (graph.pin2net[dot] != nets['drain'] or graph.pin2net[other] != output
                or nets['source'] in nonsecondary or nets['source'] == output
                or not graph.between(output, nets['source'], {ng.CAPACITOR})):
            return None, gap
        return {'controller_ref': controller, 'sense_node': nodes[0], 'return_node': nodes[1],
                'return_net': nets['source'], 'output_net': output, 'winding_nodes': wn,
                'derived_fields': sorted(derived),
                'secondary_dot_node': dot, 'winding_citation': declaration['citation'],
                'citation': cfg['citation'], 'basis': 'cited-fitted-secondary-controller-map',
                'output_capacitors': graph.between(output, nets['source'], {ng.CAPACITOR}),
                'rectifying_path': [nets['source'], ref + ':body-diode/S-to-D-channel',
                                    nets['drain'], wn, output, 'load/capacitor', nets['source']],
                'primary_on_duty': 'reverse blocking; channel must be off',
                'dynamic_status': 'not verified: diode intervals, turn-off overlap/reverse current, repetition and thermal duty'}, []

    def switches(self):
        graph, found = self.graph, []
        for ref in sorted(graph.parts):
            if ref in self.excluded or not graph.is_fitted(ref):
                continue
            if graph.kind(ref) not in SWITCH_KINDS:
                continue
            nodes = {role: graph.node_named(ref, role)
                     for role in ('gate', 'drain', 'source')}
            gaps = list(self.state['gaps'])
            if not all(nodes.values()):
                gaps.append('pin-roles:' + ref)
            if ng.kind_gap(graph, ref):
                gaps.append(ng.kind_gap(graph, ref))
            nets = {role: graph.pin2net.get(node) if node else None
                    for role, node in nodes.items()}
            source_return, return_gaps = self.source_return(ref, nets['source'])
            gaps.extend(return_gaps)
            topology, source_basis = 'unknown', None
            if nets['source'] in self.grounds:
                topology = 'low-side'
            elif source_return:
                topology = 'low-side'
            elif nets['source'] and self.tree.is_rail(nets['source']):
                topology = 'high-side'
                source_basis = self.tree.rail_basis(nets['source'])
            elif nets['source']:
                topology = 'floating'
            drivers = self.drivers(nets['gate']) if nets['gate'] else []
            sync, sync_gaps = self.synchronous_rectifier(ref, nets, drivers)
            gaps.extend(sync_gaps)
            if sync:
                topology = 'low-side-local-return'
            pulls = self.pulls(nets['gate'], nets['source'], nodes['gate']) if nets['gate'] else []
            snubbers = self.snubbers(nets['drain'], nets['source'], topology) if nets['drain'] else []
            switch_node = (self._switch_node_evidence(nets['drain'], ref, nets['source'], topology)
                           if nets['drain'] else [])
            found.append({
                'id': slug(ref + '-' + (nets['gate'] or 'unresolved')),
                'ref': ref,
                'kind': graph.kind(ref),
                'kind_basis': graph.basis(ref),
                'kind_citation': (graph.db.get('device_kinds') or {}).get(ref, {}).get('citation')
                                 if graph.basis(ref) == 'datasheet' else None,
                'basis': 'declared' if ref in self.declared else 'topology',
                'role': self.declared.get(ref, {}).get('role'),
                'role_citation': self.declared.get(ref, {}).get('citation'),
                'topology': topology,
                'source_rail_basis': source_basis,
                'source_return': source_return,
                'synchronous_rectifier': sync,
                'gate_node': nodes['gate'],
                'gate_net': nets['gate'],
                'drain_net': nets['drain'],
                'source_net': nets['source'],
                'drivers': drivers,
                'gate_pulls': pulls,
                'snubbers': snubbers,
                'switch_node_evidence': switch_node,
                'gaps': sorted(set(gaps)),
            })
        return sorted(found, key=lambda item: item['id'])[:MAX_SWITCHES]


def build_inventory(db, intent=None):
    """生成逐状态的功率开关清单。"""
    cfg = (intent or {}).get('power_switches') if isinstance(intent, dict) else None
    declared = {item['ref']: item for item in (cfg or {}).get('switches', [])
                if isinstance(item, dict) and isinstance(item.get('ref'), str)}
    excluded = state_lib.excluded_refs(cfg)
    gaps = [] if cfg else ['intent.power_switches: 未声明开关角色']
    inventory = inv.build(db, intent, 'power_switches', 'switches',
                     lambda state: _Scan(db, state, declared, excluded,
                                        ((intent or {}).get('inductive_loads') or {}).get('loads', [])).switches(), gaps)
    # The scan reads the winding maps for every switch, so the inventory digest
    # must cover them whenever they were supplied, not only once a sync-rectifier
    # role is declared; otherwise generation and validation see different inputs.
    if (intent or {}).get('inductive_loads'):
        inventory['context']['inductive_loads'] = intent['inductive_loads']
        inventory['digest'] = inv.digest({k: v for k, v in inventory.items() if k != 'digest'})
    return inventory


class PowerSwitchChecker(Checker):
    id = 'power_switch'
    title = '功率开关栅驱动与吸收'
    plan_key = 'power_switch'
    version_key = 'power_switch_version'
    version = 1
    intent_key = 'power_switches'
    cold_rules = catalog.titles(method='A', source='power_switch')
    hot_rules = catalog.titles(method='E', source='power_switch')
    evidence_kinds = {'DRV-E01': {'gate_drive'}}

    missing_inventory_message = 'power switch checks require their inventory'
    inventory_type_message = 'power switch inventory must be an object'
    requires_db_message = 'power switch inventory validation requires --db'
    stale_message = 'power switch inventory/binding is stale or modified'
    invalid_message = 'invalid power switch inventory: '

    def incomplete_message(self, key):
        return key + ': incomplete power switch planned coverage'

    def changed_message(self, key):
        return key + ': power switch generated criterion/object changed'

    def validate_intent(self, intent, db):
        return validate_power_switch_intent(intent, db)

    def build(self, db, intent):
        return build_inventory(db, intent)

    def plan(self, planner, inventory):
        for state, switch, same in inv.walk_distinct(inventory, 'switches'):
            if switch.get('role') == LEVEL_SHIFTER_ROLE:
                continue
            obj = {'ref': switch['ref'], **inv.state_fields(same),
                   'power_switch': switch['id'],
                   'power_switch_digest': inventory['digest']}
            if switch['gate_net']:
                obj['net'] = switch['gate_net']
            if switch['gate_node']:
                obj['node'] = switch['gate_node']
            gaps = switch['gaps']
            linear = switch.get('role') in LINEAR_ROLES
            # MOS on-resistance evidence is meaningless for BJT/linear stages.
            # DRV-C02 retains the device and its actual drive/operating-point duty.
            if switch['kind'] == ng.MOSFET and not linear:
                ready = planner.evidence_ready('DRV-E01', obj)
                item = planner.add_check(
                    'DRV-E01', dict(obj), key=switch['id'],
                    readiness='READY' if ready else 'WAITING_EVIDENCE',
                    required_inputs=sorted(set(gaps + ([] if ready else [
                        'evidence: DRV-E01 栅源驱动/绝限/RDS(on) 条件保证值']))),
                    trigger=['power-switch:' + switch['id'], 'topology:' + switch['topology']])
                item['inventory_gaps'] = gaps
            item = planner.add_check(
                'DRV-C02', dict(obj), key=switch['id'], readiness='WAITING_EVIDENCE',
                required_inputs=sorted(set(gaps + (
                    ['datasheet:实际驱动与 VGS/VBE/VCE 额定', 'intent:输出范围/负载/损耗及适用 SOA']
                    if linear or switch['kind'] == ng.BJT else
                    ['datasheet:SOA 温度/脉宽/单次或重复条件及 Zth',
                     'intent:正常/启动/故障 VDS(t)-ID(t) 轨迹与重复率',
                     'evidence:实际 VGS 下导通与开关损耗、温度边界及允许散热条件']))),
                trigger=['power-switch:' + switch['id']],)
            if switch['kind'] == ng.MOSFET and not linear:
                item['criterion'] += ('；MOS开关分别核关断峰压、导通电流/损耗和转换期间VDS-ID重叠轨迹；'
                                      '不把整个导通周期当高压线性脉冲，不以单脉冲SOA或典型开关时间'
                                      '证明重复安全；按实际栅源驱动、温度及Zth/散热边界核重复损耗。')
            if switch.get('role') == SYNC_RECTIFIER_ROLE:
                item['criterion'] += ('；同步整流另核次级峰值/RMS及S到D导通、体二极管区间、'
                                      '初级导通时反向阻断、CS/触发/消隐/最小导通时间与栅极关断关联；'
                                      '按电流/电压象限选适用SOA，不能用输出平均电流、门极电荷或驱动连接替代重复损耗证明。')
                item['required_inputs'] = sorted(set(item['required_inputs'] + [
                    'intent:同步整流绕组/控制器物理映射及次级模式、关联电流和频率',
                    'evidence:体二极管/反向电流与初次级换流时序、故障反压和热态重复损耗']))
            item['analysis_required'] = True
            item['inventory_gaps'] = gaps
            if switch['switch_node_evidence']:
                item = planner.add_check(
                    'DRV-D01', dict(obj), key=switch['id'], readiness='WAITING_EVIDENCE',
                    required_inputs=sorted(set(gaps + [
                        'datasheet:开关器件耐压与驱动器条款', 'evidence:开关节点波形或仿真'])),
                    trigger=['power-switch:' + switch['id']] + switch['switch_node_evidence']
                            + ['clamp:%s:%s' % (s['type'], s['ref']) for s in switch['snubbers']],)
                item['inventory_gaps'] = gaps

    @staticmethod
    def _untyped_ic_pins(graph, gate_net):
        """IC pins on the gate net (directly or through a series passive) whose direction the
        netlist does not give: no pin type, or a library that types every pin passive/unspecified."""
        native = graph.db.get('native_pintype') or {}
        nets = [gate_net] + [other for _, other in graph.neighbors(gate_net, ng.PASSIVE_LINKS)]
        return sorted({node for net in nets for node in graph.nodes_on(net)
                       if graph.kind(node.partition('.')[0]) == ng.IC
                       and graph.is_fitted(node.partition('.')[0])
                       and native.get(node, '') in ('', 'passive', 'unspecified', 'free')
                       and ng.normalize(graph.pintype.get(node)) in ('', 'UNSPEC', 'PASSIVE')})

    def cold_findings(self, lint, inventory):
        for state, switch in inv.walk(inventory, 'switches'):
            if not switch['gate_net'] or switch.get('role') == LEVEL_SHIFTER_ROLE:
                continue
            head = '%s（%s，状态 %s）' % (switch['ref'], switch['kind'], state['id'])
            if not switch['drivers'] and not switch['gate_pulls']:
                untyped = self._untyped_ic_pins(lint.graph, switch['gate_net'])
                if untyped:
                    # Netlists without pin types (OrCAD, hand-drawn libraries): an MCU GPIO may drive the gate.
                    lint.add('DRV-A03', self.cold_rules['DRV-A03'],
                             head + '：栅极网 ' + switch['gate_net'] + ' 由 ' + '、'.join(untyped[:3])
                             + ' 驱动，但网表没有引脚方向，且无下拉/上拉；按手册确认该脚是输出，'
                               '并核上电、复位与驱动高阻时栅极状态',
                             switch['ref'], kind='CANDIDATE')
                else:
                    lint.add('DRV-A03', self.cold_rules['DRV-A03'],
                             head + '：栅极网 ' + switch['gate_net']
                             + ' 上既无驱动输出脚也无下拉/上拉电阻，上电与驱动高阻时开关状态不确定',
                             switch['ref'])
            if switch['switch_node_evidence'] and not [s for s in switch['snubbers']
                    if s['type'] != 'boost-transfer-diode' or switch['topology'] != 'high-side']:
                lint.add('DRV-A04', self.cold_rules['DRV-A04'],
                         head + '：开关节点 ' + str(switch['drain_net'])
                         + ' 上有 ' + '、'.join(switch['switch_node_evidence'])
                         + '，但未见 RC/RCD 吸收或钳位；关断尖峰与振铃需按器件耐压核实',
                         switch['ref'], kind='CANDIDATE')

    def hot_check(self, lint, check):
        drive = hotmath.span(check['vgs_drive_v'])
        limits = hotmath.span(check['vgs_abs_v'])
        spec = hotmath.number(check['vgs_rds_on_v'])
        if check.get('channel') == 'p':
            drive, limits, spec = hotmath.negate(drive), hotmath.negate(limits), -spec
        problems = []
        if drive[0] < spec:
            problems.append('最小栅源驱动 %s 低于所需导通栅压 %s（RDS(on) 条件或有据曲线点）'
                            % (hotmath.fmt(drive[0], 'V'), hotmath.fmt(spec, 'V')))
        if drive[1] > limits[1] or drive[0] < limits[0]:
            problems.append('栅源驱动窗口 [%s, %s] 超出绝对最大范围 [%s, %s]'
                            % (hotmath.fmt(drive[0]), hotmath.fmt(drive[1]),
                               hotmath.fmt(limits[0]), hotmath.fmt(limits[1])))
        calculation = {'channel': check.get('channel'),
                       'vgs_drive_v': {'min': drive[0], 'max': drive[1]},
                       'vgs_rds_on_v': spec,
                       'vgs_abs_v': {'min': limits[0], 'max': limits[1]},
                       'normalized': check.get('channel') == 'p'}
        target = check.get('node') or check.get('net') or check.get('ref')
        detail = '%s: 栅源驱动 [%s, %s]V，RDS(on) 条件 %sV，绝限 [%s, %s]V；%s' % (
            target, hotmath.fmt(drive[0]), hotmath.fmt(drive[1]), hotmath.fmt(spec),
            hotmath.fmt(limits[0]), hotmath.fmt(limits[1]), lint._citation(check))
        if problems:
            lint.add('DRV-E01', '栅源驱动窗口不满足保证条件', detail + '；' + '；'.join(problems),
                     str(check.get('ref') or '').split('.')[0] or None,
                     check_id=check['id'], citation=check['citation'], calculation=calculation)
        else:
            lint.record_pass('DRV-E01', check, detail,
                             scope='所给保证值下的栅源驱动窗口；开关速度、米勒导通、SOA 与热未判定',
                             calculation=calculation)

    def evidence_errors(self, check, label):
        return hotmath.structure_errors(
            check, label, spans=('vgs_drive_v', 'vgs_abs_v'),
            numbers=('vgs_rds_on_v',), choices=(('channel', {'n', 'p'}),))

    def model_gaps(self, check):
        return hotmath.missing_gaps(
            check, spans=('vgs_drive_v', 'vgs_abs_v'), numbers=('vgs_rds_on_v',),
            texts=('channel',))

    def rule_instances(self, rule, inventory):
        return sorted({switch['id'] for _, switch in inv.walk(inventory, 'switches')
                       if switch['gate_net'] and switch.get('role') != LEVEL_SHIFTER_ROLE and (rule != 'DRV-E01' or (
                           switch['kind'] == ng.MOSFET and switch.get('role') not in LINEAR_ROLES))})

    def binds(self, item):
        obj = item.get('object')
        return isinstance(obj, dict) and bool(obj.get('power_switch'))

    def object_errors(self, key, obj, inventory):
        known = {switch['id'] for _, switch in inv.walk(inventory, 'switches')}
        if (obj.get('power_switch') not in known
                or obj.get('power_switch_digest') != inventory['digest']):
            return [key + ': stale power switch object binding']
        return []

    def pass_blockers(self, key, planned, generated, inventory):
        if generated and generated.get('inventory_gaps'):
            return [key + ': power switch gaps must be resolved in a regenerated plan before PASS']
        return []

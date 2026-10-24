#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""电路候选：从网表、核验过的器件类别和检查器库存生成，审查员不画电路。

候选 = 类型 + 核心器件（核验角色的 IC，或没人驱动的分立开关，或板级对象）。成员带 `via`：走到它的路径
或库存来源。路径是**归属关系**，不是导通断言——走线经过两端器件不分方向，参考地分区另由 checkers/domains
推导。走线停在截止网络（地、IC 输出脚驱动的网、两个以上核心器件到达的声明轨、该变换器电感负载的输入/输出网）、
别的核心器件、跨域器件（变压器、光耦、Y 电容、隔离器：隔离候选的成员，别的候选不穿过）。

页面与名字只作展示，不决定归属。两个候选在同一距离走到的器件两边都列；走线更短的候选赢得器件。
每颗被持有的器件恰好由一个候选拥有（成员的 `owned`），其余持有它的候选只引用它：电路的核心器件 > 电路成员 >
电路里的端点类角色 > 链路成员 > 隔离带 > 链路的核心器件与端点（`claim_rank`）。同一级打平的器件谁也不拥有，
记入 shared，由审查员的 own 决定裁定。没有候选走到的器件列在 unassigned（REQ-Q08 的复核对象），没有核验角色的
IC 和 pin-roles 缺口列在 gaps。相同输入与规则版本得到相同文件。
"""
import argparse
import json
import re
import sys
from collections import deque

import board_intent
import catalog
from electrical_contract import db_fingerprint, load_json
from checkers import REGISTRY, domains as domains_lib, netgraph as ng, powertree
import part_words as pw

SCHEMA_VERSION = 2
RULES_VERSION = '2026-10-24.1'   # shared part words and grounds (SR self-check 3.1–3.3)
MAX_HOPS = 4
ANALOG_HOPS = 2
INPUT_HOPS = 6
STORAGE_FARAD = 10e-6     # the input ends at its bulk capacitor; a 1 µF filter capacitor (plan_circuits.BULK_FARAD) does not end it
CONVERTER_ROLES = frozenset({'pwm_controller', 'sr_controller', 'regulator', 'gate_driver'})
ANALOG_ROLES = frozenset({'pd_controller', 'supervisor', 'opamp_comparator', 'shunt_reference', 'mcu', 'transceiver'})
ALL_PIN_ROLES = frozenset({'opamp_comparator', 'shunt_reference'})     # every signal pin is a sense pin
FEEDBACK_PIN_RE = re.compile(r'^(FB|VFB|COMP|FB/\w+|\w+/FB)$', re.I)
PROTECTION_PIN_RE = re.compile(r'^(OVP|UVP|OCP|OTP|OLP|LATCH|FAULT|FLT|BO|BROWNOUT|PROT|SCP|OVLO)$', re.I)
STARTUP_PIN_RE = re.compile(r'^(HV|VSTART|HVS|EN|ENABLE|INH|INHIBIT|UVLO|SS|SOFT_?START|RUN|DELAY|DIS|DISABLE|TRIG/DIS|PG|PGOOD|RESET|NRST|RST)$', re.I)
SENSE_PIN_RE = re.compile(r'^(CS|CS[+-]|CS_?[PN]|ISNS|ISENSE|ISEN|VSNS|VSENSE|FB|NTC|TEMP|RT|ZCD|ZCD/OPP|CS/ZCD|AIN\d*|VIN_?SNS)$', re.I)
USB_PIN_RE = re.compile(r'^(CC[12]|D[+-]|DP|DN|DM|D_P|D_N|SBU[12])$', re.I)
DEBUG_PIN_RE = re.compile(r'^(SWDIO|SWCLK|SWO|TCK|TMS|TDI|TDO|NTRST|JTAG\w*)$', re.I)
PROTECTIVE_RE = re.compile(r'THERMISTOR|FUSE|BRIDGE|\bGDT\b|SPARK', re.I)   # with netgraph's NTC and varistor words
PASS_THROUGH = frozenset({pw.BRIDGE_RECTIFIER})      # multi-pin parts the input walk passes
WALK, STOP = 'walk', 'stop'
IDENTITY_ROLES = ('anchor', 'endpoint', 'connector', 'pd_controller')   # a part's identity in a candidate, not its body


def claim_rank(candidate, member):
    """How strongly a candidate claims a member; the lowest rank owns the part. A circuit's anchor (0), a circuit member
    (1), a circuit's endpoint-type role such as the port's PD controller (2), a chain member (3), the isolation band (4),
    a chain's anchor or endpoint (5)."""
    identity = member.get('role') in IDENTITY_ROLES
    if not candidate.get('cross_cutting'):
        if member['ref'] == candidate.get('anchor'):
            return 0
        return 2 if identity else 1
    if identity:
        return 5
    return 4 if candidate.get('type') == 'ISOLATION' else 3


def best_claims(holders):
    """{ref: [holder ids with the best claim]} from {holder id: [(ref, rank)]}."""
    ranks = {}
    for hid, claims in holders.items():
        for ref, rank in claims:
            ranks.setdefault(ref, []).append((rank, hid))
    return {ref: sorted({hid for rank, hid in entries if rank == min(r for r, _ in entries)})
            for ref, entries in ranks.items()}


def _blob(part):
    return ' '.join(pw.normalize(part.get(k)) for k in ('part', 'value', 'prim', 'jedec'))


class Generator:
    def __init__(self, db, intent=None, datasheet_audit=None):
        self.db = db
        self.kind_intent = board_intent.with_verified_kinds(intent or {}, datasheet_audit)
        analysis_db = board_intent.graph_db(db, self.kind_intent)
        self.graph = ng.NetGraph(analysis_db)
        self.domains = domains_lib.derive(self.graph, self.kind_intent)
        self.tree = powertree.PowerTree(self.graph, self.kind_intent)
        checkers = {c.plan_key: c for c in REGISTRY}
        self.switches = self._first_state(checkers['power_switch'].build(analysis_db, self.kind_intent), 'switches')
        self.loads = self._first_state(checkers['inductive_load'].build(analysis_db, self.kind_intent), 'loads')
        self.optos = self._first_state(checkers['optocoupler'].build(analysis_db, self.kind_intent), 'optocouplers')
        self.winding_nets = {net for load in self.loads for net in self.graph.nets_of(load['ref'])}
        self.anchors = dict(self.domains['anchors'])
        self.barriers = {b['ref'] for b in self.domains['barriers']}
        self.grounds = set(self.domains['grounds'])
        self.stops = set(self.domains['rail_stops'])
        for load in self.loads:
            for key in ('rail_net', 'output_net', 'return_net'):
                if load.get(key):
                    self.stops.add(load[key])
        self.candidates = {}
        self.analog_members = set()

    @staticmethod
    def _first_state(inventory, key):
        states = inventory.get('states') or []
        return list(states[0].get(key, [])) if states else []

    # -- helpers -------------------------------------------------------------
    def fitted(self, ref):
        return self.graph.is_fitted(ref)

    def two_terminal(self, ref):
        return len(self.graph.pins_of(ref)) == 2 and len(self.graph.nets_of(ref)) == 2

    def pin_name(self, node):
        return self.graph.pinname.get(node) or ''

    def matches(self, pattern, node):
        return pw.name_matches(pattern, self.pin_name(node), node.partition('.')[2])

    def domain_of(self, ref):
        found = sorted({self.domains['nets'].get(n) for n in self.graph.nets_of(ref)} - {None})
        return found[0] if len(found) == 1 else ('/'.join(found) if found else None)

    def ground_caps(self, net):
        """Capacitors between a net and any ground."""
        return sorted(ref for ref in self.graph.refs_on(net)
                      if self.graph.kind(ref) == pw.CAPACITOR and self.two_terminal(ref)
                      and any(n in self.grounds for n in self.graph.nets_of(ref) if n != net))

    def add(self, cid, ref, role, via, hops):
        """Record a member; a shorter path replaces a longer one, an explicit (hops 0) assignment wins."""
        members = self.candidates[cid]['members']
        if ref in members and members[ref]['hops'] <= hops:
            return
        members[ref] = {'ref': ref, 'role': role, 'via': via, 'hops': hops}

    def walk(self, cid, seeds, stops, max_hops, blocked=(), expand_seeds=False):
        """Breadth-first over nets from (node, net) seeds through two-terminal parts; records members with their path.

        A seed on a stop net is not expanded (a controller's supply rail is shared with other circuits) unless
        expand_seeds says the seeds are the candidate's own nets (a connector's contacts)."""
        owner = self.candidates[cid]['anchor']
        seen = {}
        queue = deque()
        for node, net in seeds:
            if net in self.graph.pseudo:
                continue
            queue.append((net, 0, f'{WALK} {node}', net in stops and not expand_seeds))
        while queue:
            net, hops, path, halt = queue.popleft()
            if seen.get(net, 99) <= hops:
                continue
            seen[net] = hops
            if halt or hops >= max_hops:
                continue
            for ref in self.graph.refs_on(net):
                if ref == owner or ref in blocked or ref in self.anchors or ref in self.barriers:
                    continue
                if not self.two_terminal(ref):
                    continue
                other = next(n for n in self.graph.nets_of(ref) if n != net)
                via = f'{path} -> {net} -> {ref}'
                self.add(cid, ref, self.graph.kind(ref), via, hops + 1)
                queue.append((other, hops + 1, via, other in stops))

    def new(self, cid, ctype, anchor, domain, nets=None, cross_cutting=False):
        """A cross-cutting candidate (the isolation barrier, a startup or protection chain) may share parts with
        one circuit candidate; two circuit candidates compete for a part."""
        self.candidates[cid] = {'id': cid, 'type': ctype, 'anchor': anchor, 'domain': domain,
                                'cross_cutting': cross_cutting, 'members': {}, 'nets': dict(nets or {}),
                                'states': list(catalog.CANDIDATE_STATES.get(ctype, ()))}
        return self.candidates[cid]

    def chain_pin(self, node):
        return self.matches(PROTECTION_PIN_RE, node) or self.matches(STARTUP_PIN_RE, node)

    def anchor_seeds(self, ref, exclude=None):
        return [(ref + '.' + pin, net) for pin, net in sorted(self.graph.pins_of(ref).items())
                if net not in self.grounds and not (exclude and self.matches(exclude, ref + '.' + pin))]

    def driven_output_caps(self, cid, anchor):
        """Capacitors on a rail this anchor's own output pin drives (its regulator output)."""
        for pin, net in sorted(self.graph.pins_of(anchor).items()):
            if self.domains['rail_stops'].get(net) != domains_lib.DRIVER or net in self.winding_nets:
                continue          # a transformer winding's net is the converter's output, whatever pin name sits on it
            found = self.tree.source_of(net)
            if not found or found['source'].partition('.')[0] != anchor:
                continue
            for cap in self.ground_caps(net):
                self.add(cid, cap, 'output_capacitor', f'output_capacitor: on {net} driven by {anchor}.{pin}', 0)

    # -- type rules ----------------------------------------------------------
    def switch_anchor(self, switch):
        """The IC anchor that drives a switch, or None when nobody with a role does."""
        for driver in switch.get('drivers', []):
            ref = str(driver.get('node', '')).partition('.')[0]
            if ref in self.anchors:
                return ref
        return None

    @staticmethod
    def snubber_hops(snubber):
        """A plain capacitor on a switch node is weaker evidence than an RC/RCD network: a rectifier output or a
        walk of one hop claims it first."""
        return 1 if 'capacitor' in str(snubber.get('type', '')) else 0

    def self_anchored(self, switch):
        """A switch nobody with a verified role drives anchors itself when nothing drives it, when only its own
        pins do, or when the reviewer declared its role (power_switches, cited): the converter then exists on the
        declaration and the unverified driver stays a device-kind gap outside it."""
        if switch.get('basis') == 'declared' and switch.get('role'):
            return True
        drivers = switch.get('drivers', [])
        return not any(d.get('source') in ('driver-pin', 'opto-output') for d in drivers) or (
            all(str(d.get('node', '')).partition('.')[0] == switch['ref'] for d in drivers))

    def prepare(self):
        """Which anchor owns which switch, which switches anchor themselves, and the nets every walk treats as
        circuit boundaries besides the rail stops (switch nodes, converter inputs, winding nets)."""
        self.by_anchor = {}
        for switch in self.switches:
            if not self.fitted(switch['ref']):
                continue
            owner = self.switch_anchor(switch)
            if owner and self.anchors[owner] == 'pd_controller':
                continue          # a port's VBUS switch belongs to the port
            if owner is None and self.self_anchored(switch):
                owner = switch['ref']
            if owner:
                self.by_anchor.setdefault(owner, []).append(switch)
        self.discrete_anchors = {a for a in self.by_anchor if a not in self.anchors}
        if self.discrete_anchors:
            # a rail two anchors reach is a boundary; discrete switch anchors count like role ICs
            stops = domains_lib.rail_stops(self.graph, self.kind_intent, self.domains['grounds'],
                                           dict(self.anchors, **{a: 'discrete switch' for a in self.discrete_anchors}))
            self.stops |= set(stops)
            self.domains['rail_stops'] = stops
        self.switch_nets = set()
        for switch in self.switches:
            for key in ('drain_net', 'source_net'):
                if switch.get(key) and switch[key] not in self.grounds:
                    self.switch_nets.add(switch[key])
        self.switch_nets |= self.winding_nets
        self.chain_members = set()

    def converters(self):
        anchors = {ref for ref, role in self.anchors.items() if role in CONVERTER_ROLES}
        by_anchor = self.by_anchor
        self.converter_anchors = sorted(anchors | set(by_anchor))
        for anchor in self.converter_anchors:
            self.new('POWER_CONVERTER-' + anchor, 'POWER_CONVERTER', anchor, self.domain_of(anchor))
        owned = {s['ref'] for switches in by_anchor.values() for s in switches}
        for anchor in self.converter_anchors:
            cid = 'POWER_CONVERTER-' + anchor
            cand = self.candidates[cid]
            self.add(cid, anchor, 'anchor', 'anchor:' + (self.anchors.get(anchor) or 'discrete switch nobody drives'), 0)
            stops = set(self.stops)
            seeds = [(node, net) for node, net in self.anchor_seeds(anchor) if not self.chain_pin(node)]
            inductive = []
            sync_rectifier = self.anchors.get(anchor) == 'sr_controller' or any(
                s['ref'] == anchor and s.get('role') == 'synchronous_rectifier' for s in by_anchor.get(anchor, []))
            for switch in by_anchor.get(anchor, []):
                sid = switch['id']
                if switch['ref'] != anchor:
                    self.add(cid, switch['ref'], 'switch', f'power_switch:{sid} driver {self.switch_anchor(switch) or anchor}', 0)
                    for pin, net in sorted(self.graph.pins_of(switch['ref']).items()):
                        seeds.append((switch['ref'] + '.' + pin, net))
                elif switch.get('source_net') and switch['source_net'] not in self.grounds:
                    # a pass element nobody drives: its source is the rail it produces
                    cand['nets']['output'] = switch['source_net']
                    cand['nets']['input'] = switch.get('drain_net')
                    for cap in self.ground_caps(switch['source_net']):
                        self.add(cid, cap, 'output_capacitor', f'output_capacitor: on {switch["source_net"]} produced by {anchor}', 0)
                    self.walk(cid, [(anchor + '.' + pin, net) for pin, net in sorted(self.graph.pins_of(anchor).items())
                                    if net == switch['source_net']], stops, 1, expand_seeds=True)
                for pull in switch.get('gate_pulls', []):
                    self.add(cid, pull['ref'], 'gate_pull', f'power_switch:{sid} gate_pull', 0)
                for snubber in switch.get('snubbers', []):
                    for ref in str(snubber.get('ref', '')).split('+'):
                        if ref and ref not in self.barriers:     # a Y capacitor on the switch node is the isolation's
                            self.add(cid, ref, 'snubber', f'power_switch:{sid} snubber {snubber.get("type", "")}',
                                     self.snubber_hops(snubber))
                for evidence in switch.get('switch_node_evidence', []):
                    if str(evidence).startswith('inductive:') and not sync_rectifier:
                        ref = evidence.split(':', 1)[1]
                        self.add(cid, ref, 'inductive', f'power_switch:{sid} switch_node_evidence {evidence}', 0)
                        inductive.append(ref)
                if switch.get('drain_net'):
                    cand['nets']['switch'] = switch['drain_net']
            for load in self.loads:
                if sync_rectifier:
                    break             # the SR controller keeps its own MOSFET and passives; the transformer is the converter's
                if load['ref'] in inductive or load.get('switch_ref') in {s['ref'] for s in by_anchor.get(anchor, [])}:
                    if load['ref'] not in inductive:
                        self.add(cid, load['ref'], 'inductive', f'inductive_load:{load["id"]}', 0)
                        inductive.append(load['ref'])
                    for key, role in (('output_capacitors', 'output_capacitor'), ('input_capacitors', 'input_capacitor')):
                        for cap in load.get(key) or []:
                            if role == 'output_capacitor':
                                self.add(cid, cap, role, f'output_capacitor:inductive_load {load["id"]}', 0)
                    for key, name in (('rail_net', 'input'), ('output_net', 'output'), ('return_net', 'return')):
                        if load.get(key):
                            cand['nets'][name] = load[key]
                            stops.add(load[key])
            # the inductive element's other windings are seeds too: the rectifiers on them belong to the converter,
            # and a winding that ends on a non-ground stop (a synchronously rectified output) is an output net
            for ref in inductive:
                for pin, net in sorted(self.graph.pins_of(ref).items()):
                    seeds.append((ref + '.' + pin, net))
                    produced_elsewhere = any(net in (c['nets'].get('output'), c['nets'].get('storage'))
                                             for k, c in self.candidates.items() if k != cid)
                    if net in stops and net not in self.grounds and net != cand['nets'].get('input') and not produced_elsewhere:
                        cand['nets'].setdefault('output', net)
                        for cap in self.ground_caps(net):
                            self.add(cid, cap, 'output_capacitor', f'output_capacitor: on {net}, a winding of {ref}', 0)
            self.walk(cid, seeds, stops, MAX_HOPS, blocked=self.chain_members)
            self.rectifier_outputs(cid, inductive, stops)
            self.regulator_outputs(cid, anchor, stops)
            self.driven_output_caps(cid, anchor)
            self.feedback_opto(cid, anchor)
            # a switch nobody with a role drives, sitting on one of this anchor's pin nets, is this circuit's (a latch, a level stage)
            pin_nets = set(self.graph.pins_of(anchor).values()) - self.grounds
            for switch in self.switches:
                if switch['ref'] in owned or switch['ref'] == anchor or not self.fitted(switch['ref']):
                    continue
                touched = sorted(pin_nets & set(self.graph.nets_of(switch['ref'])))
                if touched:
                    self.add(cid, switch['ref'], 'switch', f'power_switch:{switch["id"]} on anchor pin net {touched[0]}', 1)

    def feedback_opto(self, cid, anchor):
        """An optocoupler on the controller's feedback pin closes its loop: the opto and the LED-side series
        parts are the converter's, up to the anchor that drives the LED."""
        for pin, net in sorted(self.graph.pins_of(anchor).items()):
            if not self.matches(FEEDBACK_PIN_RE, anchor + '.' + pin):
                continue
            for ref in self.graph.refs_on(net):
                if self.graph.kind(ref) != pw.OPTO or ref not in self.barriers:
                    continue
                self.add(cid, ref, 'feedback_opto', f'feedback: optocoupler on {anchor}.{pin} net {net}', 0)
                led = [n for n in self.graph.nets_of(ref) if n != net and n not in self.grounds
                       and self.domains['nets'].get(n) != self.domains['nets'].get(net)]
                for other in led:
                    for part in self.graph.refs_on(other):
                        if self.two_terminal(part) and part not in self.anchors:
                            self.add(cid, part, 'feedback_led_resistor', f'feedback: {part} on the LED side of {ref}', 0)

    def rectifier_outputs(self, cid, inductive, stops):
        """A diode from a winding net to a stop net marks that net as an output: its capacitors to ground are members."""
        cand = self.candidates[cid]
        for ref in inductive:
            for net in self.graph.nets_of(ref):
                for diode in self.graph.refs_on(net):
                    if diode not in cand['members'] or self.graph.kind(diode) not in (pw.DIODE, pw.TVS, pw.ZENER):
                        continue
                    other = next((n for n in self.graph.nets_of(diode) if n != net), None)
                    if other is None or other in self.grounds:
                        continue
                    cand['members'][diode]['role'] = 'rectifier'
                    fed = [a for a in self.converter_anchors if a != cand['anchor']
                           and other == self.candidates['POWER_CONVERTER-' + a]['nets'].get('input')]
                    if fed:
                        # an auxiliary winding rectified into another converter's input (a bias pass element): the
                        # rectifier and its capacitors are that converter's, not this one's
                        target = 'POWER_CONVERTER-' + fed[0]
                        del cand['members'][diode]
                        self.add(target, diode, 'rectifier', f'rectifier: {ref} winding {net} into {other}, the input of {fed[0]}', 0)
                        for cap in self.ground_caps(other):
                            self.add(target, cap, 'input_capacitor', f'input_capacitor: on {other} rectified by {diode}', 0)
                        continue
                    if other in stops or other not in cand['nets'].values():
                        cand['nets'].setdefault('output', other)
                    for cap in self.ground_caps(other):
                        self.add(cid, cap, 'output_capacitor', f'output_capacitor: on {other} reached by {diode} from {ref}', 0)

    def regulator_outputs(self, cid, anchor, stops):
        """An inductor from the anchor's switch pin leads to its output; the capacitors there are members."""
        cand = self.candidates[cid]
        for pin, net in sorted(self.graph.pins_of(anchor).items()):
            if not self.matches(powertree.SWITCH_OUTPUT_PIN_RE, anchor + '.' + pin):
                continue
            for ref in self.graph.refs_on(net):
                if ref in cand['members'] and self.graph.kind(ref) == pw.INDUCTOR and self.two_terminal(ref):
                    cand['members'][ref]['role'] = 'inductive'
                    other = next(n for n in self.graph.nets_of(ref) if n != net)
                    cand['nets'].setdefault('switch', net)
                    cand['nets'].setdefault('output', other)
                    for cap in self.ground_caps(other):
                        self.add(cid, cap, 'output_capacitor', f'output_capacitor: on {other} reached by {ref} from {anchor}.{pin}', 0)

    def usb_connector(self, ref):
        return self.graph.kind(ref) == pw.CONNECTOR and any(
            self.matches(USB_PIN_RE, ref + '.' + pin) for pin in self.graph.pins_of(ref))

    def inputs(self):
        for ref in sorted(self.graph.parts):
            if not self.fitted(ref) or self.graph.kind(ref) != pw.CONNECTOR or self.usb_connector(ref):
                continue
            cid = 'POWER_PROTECTION-' + ref
            found = self.input_walk(ref)
            if not found:
                continue
            members, storage = found
            cand = self.new(cid, 'POWER_PROTECTION', ref, self.domain_of(ref), {'storage': storage})
            if storage:
                self.stops.add(storage)
            self.add(cid, ref, 'connector', 'anchor:input connector', 0)
            for part, (hops, via, role) in members.items():
                self.add(cid, part, role, via, hops)

    def input_walk(self, connector):
        """From the connector through series parts (two-terminal, bridges, chokes) to the first storage capacitor."""
        members, seen, storage = {}, {}, None
        queue = deque((net, 0, f'{WALK} {connector}.{pin}') for pin, net in sorted(self.graph.pins_of(connector).items())
                      if net not in self.graph.pseudo)
        protective = False
        while queue:
            net, hops, path = queue.popleft()
            if seen.get(net, 99) <= hops or net in self.grounds:
                continue
            seen[net] = hops
            caps = [c for c in self.ground_caps(net) if (parse_capacitance(self.graph.parts[c].get('value')) or 0) >= STORAGE_FARAD]
            if hops and net in self.stops:
                caps = self.ground_caps(net)      # a converter's input rail ends the input: its capacitors are the input's, whatever their value
            if caps or (hops and net in self.stops):
                for cap in caps:
                    members[cap] = (hops + 1, f'{path} -> {net} -> {cap}', 'storage_capacitor')
                storage = storage or net
                continue
            if hops >= INPUT_HOPS:
                continue
            for ref in self.graph.refs_on(net):
                if ref == connector or ref in self.anchors or ref in self.barriers or ref in members:
                    continue
                kind = self.graph.kind(ref)
                blob = _blob(self.graph.parts.get(ref, {}))
                is_protective = kind in (pw.FUSE, pw.TVS, pw.BRIDGE_RECTIFIER) or bool(PROTECTIVE_RE.search(blob) or pw.NTC_RE.search(blob) or pw.VARISTOR_RE.search(blob))
                if self.two_terminal(ref):
                    members[ref] = (hops + 1, f'{path} -> {net} -> {ref}', 'protective' if is_protective else kind)
                    protective |= is_protective
                    queue.append((next(n for n in self.graph.nets_of(ref) if n != net), hops + 1, f'{path} -> {net} -> {ref}'))
                elif kind in PASS_THROUGH or (kind == pw.INDUCTOR and len(self.graph.pins_of(ref)) == 4):
                    members[ref] = (hops + 1, f'{path} -> {net} -> {ref}', 'protective' if is_protective else kind)
                    protective |= is_protective
                    for other in self.graph.nets_of(ref):
                        if other != net:
                            queue.append((other, hops + 1, f'{path} -> {net} -> {ref}'))
        return (members, storage) if protective else None

    def isolation(self):
        pairs = {}
        for barrier in self.domains['barriers']:
            pairs.setdefault('/'.join(barrier['domains']), []).append(barrier)
        for pair, barriers in sorted(pairs.items()):
            cid = 'ISOLATION-' + pair
            self.new(cid, 'ISOLATION', pair, pair, cross_cutting=True)
            for barrier in barriers:
                self.add(cid, barrier['ref'], 'barrier', f'barrier:{barrier["kind"]} spans {pair}', 0)

    def chains(self):
        """Startup and protection chains: from an anchor's startup or protection pin outward, through two-terminal
        parts and through optocouplers (both sides), to a stop or to another anchor's pin, which joins as endpoint."""
        for anchor in sorted(self.anchors):
            for pin, net in sorted(self.graph.pins_of(anchor).items()):
                node = anchor + '.' + pin
                if net in self.grounds or net in self.graph.pseudo:
                    continue
                if self.matches(PROTECTION_PIN_RE, node):
                    ctype, label = 'POWER_PROTECTION', 'protection'
                elif self.matches(STARTUP_PIN_RE, node):
                    ctype, label = 'STARTUP', 'startup'
                else:
                    continue
                if net in self.stops:
                    continue          # a pin tied straight to a rail is no chain
                name = re.sub(r'[^A-Z0-9]+', '_', pw.normalize(self.pin_name(node)) or pin).strip('_')
                cid = f'{ctype}-{anchor}.{name}'
                cand = self.new(cid, ctype, anchor, self.domain_of(anchor), {'pin': node, 'net': net}, cross_cutting=True)
                self.add(cid, anchor, 'anchor', f'anchor:{label} pin {node}', 0)
                self.chain_walk(cid, node, net)
                if len(cand['members']) < 2:
                    del self.candidates[cid]       # a pin tied straight to a rail is no chain

    def chain_walk(self, cid, node, start):
        owner = self.candidates[cid]['anchor']
        seen = {}
        queue = deque([(start, 0, f'{WALK} {node}')])
        while queue:
            net, hops, path = queue.popleft()
            if seen.get(net, 99) <= hops or net in self.grounds or net in self.graph.pseudo:
                continue
            seen[net] = hops
            if hops and (net in self.stops or net in self.switch_nets):
                continue          # a rail, a switch node or a converter's input: the chain ends there
            if hops >= MAX_HOPS:
                continue
            for ref in self.graph.refs_on(net):
                if ref == owner:
                    continue
                via = f'{path} -> {net} -> {ref}'
                if ref in self.anchors or ref in self.discrete_anchors:
                    self.add(cid, ref, 'endpoint', via, hops + 1)
                    continue
                if self.graph.kind(ref) == pw.OPTO and ref in self.barriers:
                    self.add(cid, ref, 'optocoupler', via, hops + 1)
                    for other in self.graph.nets_of(ref):
                        if other != net:
                            queue.append((other, hops + 1, via))
                    continue
                if ref in self.barriers or not self.two_terminal(ref):
                    continue
                self.add(cid, ref, self.graph.kind(ref), via, hops + 1)
                queue.append((next(n for n in self.graph.nets_of(ref) if n != net), hops + 1, via))

    def ports(self):
        for ref in sorted(self.graph.parts):
            if not self.fitted(ref) or not self.usb_connector(ref):
                continue
            cid = 'USB-' + ref
            cand = self.new(cid, 'USB', ref, self.domain_of(ref))
            self.add(cid, ref, 'connector', 'anchor:USB connector', 0)
            nets = {net for net in self.graph.nets_of(ref) if net not in self.grounds and net not in self.graph.pseudo}
            # one hop from the contacts: clamps and port capacitors; sense networks were claimed by ANALOG first
            self.walk(cid, self.anchor_seeds(ref), self.stops, 1, blocked=self.analog_members, expand_seeds=True)
            controllers = []
            for anchor, role in sorted(self.anchors.items()):
                if role != 'pd_controller':
                    continue
                near = {n for n in self.graph.nets_of(anchor)}
                near |= {other for net in self.graph.nets_of(anchor) for part in self.graph.refs_on(net)
                         if self.two_terminal(part) for other in self.graph.nets_of(part)}
                if near & nets:
                    controllers.append(anchor)
            for anchor in controllers:
                self.add(cid, anchor, 'pd_controller', f'anchor:pd_controller on the port nets', 0)
                self.walk(cid, self.anchor_seeds(anchor, exclude=SENSE_PIN_RE), self.stops, MAX_HOPS, blocked=self.analog_members)
                self.driven_output_caps(cid, anchor)
                for switch in self.switches:
                    if self.fitted(switch['ref']) and self.switch_anchor(switch) == anchor:
                        sid = switch['id']
                        self.add(cid, switch['ref'], 'vbus_switch', f'power_switch:{sid} driver {anchor}', 0)
                        for pull in switch.get('gate_pulls', []):
                            self.add(cid, pull['ref'], 'gate_pull', f'power_switch:{sid} gate_pull', 0)
                        for snubber in switch.get('snubbers', []):
                            for part in str(snubber.get('ref', '')).split('+'):
                                if part and part not in self.barriers:
                                    self.add(cid, part, 'snubber', f'power_switch:{sid} snubber {snubber.get("type", "")}',
                                             self.snubber_hops(snubber))
                        if switch.get('source_net'):
                            cand['nets'].setdefault('vbus', switch['source_net'])
            if controllers:
                cand['nets']['pd_controllers'] = ','.join(controllers)

    def analog(self):
        for anchor, role in sorted(self.anchors.items()):
            if role not in ANALOG_ROLES:
                continue
            seeds = []
            for pin, net in sorted(self.graph.pins_of(anchor).items()):
                node = anchor + '.' + pin
                if net in self.grounds or net in self.graph.pseudo:
                    continue
                if role in ALL_PIN_ROLES:
                    if net in self.stops:
                        continue
                    seeds.append((node, net))
                elif self.matches(SENSE_PIN_RE, node):
                    seeds.append((node, net))
            if not seeds:
                continue
            cid = 'ANALOG-' + anchor
            self.new(cid, 'ANALOG', anchor, self.domain_of(anchor), {'sense_pins': ','.join(n for n, _ in seeds)})
            self.add(cid, anchor, 'anchor', 'anchor:' + role, 0)
            self.walk(cid, seeds, self.stops, ANALOG_HOPS)
            # a Kelvin-sensed shunt sits between two ground nets: the sense walk ends on a ground, the shunt joins it
            grounds_reached = {n for ref, m in self.candidates[cid]['members'].items() if m['hops'] == 1
                               for n in self.graph.nets_of(ref) if n in self.grounds}
            for ground in sorted(grounds_reached):
                for ref in self.graph.refs_on(ground):
                    if self.two_terminal(ref) and self.graph.kind(ref) == pw.RESISTOR and all(
                            n in self.grounds for n in self.graph.nets_of(ref)):
                        self.add(cid, ref, 'shunt', f'shunt between grounds {"/".join(self.graph.nets_of(ref))} reached from {anchor}', 1)

    def debug(self):
        found = []
        for ref in sorted(self.graph.parts):
            if not self.fitted(ref):
                continue
            kind = self.graph.kind(ref)
            if kind == pw.TESTPOINT:
                nets = [n for n in self.graph.nets_of(ref) if n not in self.graph.pseudo]
                found.append((ref, 'testpoint', f'testpoint on {",".join(nets) or "no net"}'))
            elif kind == pw.CONNECTOR and any(self.matches(DEBUG_PIN_RE, ref + '.' + pin) for pin in self.graph.pins_of(ref)):
                found.append((ref, 'debug_connector', 'debug connector: ' + ','.join(
                    sorted(self.pin_name(ref + '.' + pin) for pin in self.graph.pins_of(ref) if self.matches(DEBUG_PIN_RE, ref + '.' + pin)))))
        if not found:
            return
        cid = 'DEBUG-BOARD'
        self.new(cid, 'DEBUG', 'BOARD', None)
        for ref, role, via in found:
            self.add(cid, ref, role, via, 0)

    # -- assembly --------------------------------------------------------------
    def adjudicate(self):
        """A part two circuit candidates reach: the shorter path wins; equal paths keep it in both (ownership decides)."""
        owners = {}
        for cid, cand in self.candidates.items():
            if cand['cross_cutting']:
                continue
            for ref, member in cand['members'].items():
                if ref == cand['anchor']:
                    continue          # a candidate's own anchor is its identity, never shared away
                owners.setdefault(ref, []).append((member['hops'], cid))
        for ref, entries in sorted(owners.items()):
            best = min(h for h, _ in entries)
            for h, cid in entries:
                if h != best:
                    del self.candidates[cid]['members'][ref]

    def ownership(self):
        """Mark each member owned or referenced; a part whose best claims tie is owned by no candidate and listed shared."""
        winners = best_claims({cid: [(ref, claim_rank(cand, m)) for ref, m in cand['members'].items()]
                               for cid, cand in self.candidates.items()})
        shared = []
        for ref, cids in sorted(winners.items()):
            for cid, cand in self.candidates.items():
                if ref in cand['members']:
                    cand['members'][ref]['owned'] = cids == [cid]
            if len(cids) > 1:
                shared.append({'ref': ref, 'candidates': cids,
                               'via': {cid: self.candidates[cid]['members'][ref]['via'] for cid in cids}})
        return shared

    def build(self):
        self.prepare()
        self.inputs()            # first: the storage net it reaches is the input rail, a stop for every other walk
        self.chains()            # chains claim their parts before the converter walks, which are blocked from them
        self.chain_members = {ref for cand in self.candidates.values() if cand['cross_cutting']
                              for ref, m in cand['members'].items() if m['role'] not in ('anchor', 'endpoint', 'optocoupler')}
        self.converters()
        self.isolation()
        self.analog()
        self.analog_members = {ref for cand in self.candidates.values() if cand['type'] == 'ANALOG'
                               for ref, m in cand['members'].items() if ref != cand['anchor'] and m['hops'] <= 1}
        self.ports()
        self.debug()
        self.adjudicate()
        shared = self.ownership()
        assigned = {ref for cand in self.candidates.values() for ref in cand['members']}
        unassigned = []
        for ref in sorted(self.graph.parts):
            if not self.fitted(ref) or ref in assigned:
                continue
            nets = [n for n in self.graph.nets_of(ref) if n not in self.graph.pseudo]
            unassigned.append({'ref': ref, 'kind': self.graph.kind(ref), 'nets': nets,
                               'reason': 'no candidate walk reached it'})
        gaps = [{'kind': 'device-kind', 'ref': ref, 'need': f'intent.device_kinds.{ref}: datasheet page + verbatim quote stating the role'}
                for ref in self.domains['undeclared_ics']]
        for load in self.loads:
            if load.get('id', '').endswith('UNRESOLVED'):
                gaps.append({'kind': 'pin-roles', 'ref': load['ref'],
                             'need': f'intent.devices.{load["ref"]}: winding/pin roles from the datasheet'})
        pages = self.db.get('ref2page') or {}
        candidates = []
        for cid in sorted(self.candidates):
            cand = self.candidates[cid]
            members = [dict(m) for _, m in sorted(cand['members'].items())]
            for m in members:
                m.pop('hops', None)
            candidates.append({**{k: v for k, v in cand.items() if k != 'members'}, 'members': members,
                               'pages': sorted({pages[m['ref']] for m in members if m['ref'] in pages})})
        return {
            'schema_version': SCHEMA_VERSION,
            'rules_version': RULES_VERSION,
            'db_sha256': db_fingerprint(self.db),
            'input_sha256': board_intent.input_fingerprint(self.db),
            'domains': {k: self.domains[k] for k in ('grounds', 'barriers', 'anchors', 'rail_stops', 'conflicts')},
            'stops': sorted(self.stops),
            'candidates': candidates,
            'shared': shared,
            'unassigned': unassigned,
            'gaps': gaps,
        }


def parse_capacitance(value):
    from decoupling import parse_capacitance as parse
    return parse(value)


def build(db, intent=None, datasheet_audit=None):
    return Generator(db, intent, datasheet_audit).build()


def summary(result):
    lines = [f"候选 {len(result['candidates'])} 个，共享 {len(result['shared'])} 件，未归属 {len(result['unassigned'])} 件，缺口 {len(result['gaps'])} 条"]
    for cand in result['candidates']:
        lines.append(f"  {cand['id']:<28} {len(cand['members']):>3} 件  " + ' '.join(
            m['ref'] if m.get('owned') else '(' + m['ref'] + ')' for m in cand['members']))
    for item in result['unassigned']:
        lines.append(f"  未归属 {item['ref']} ({item['kind']}) {','.join(item['nets'])}")
    for gap in result['gaps']:
        lines.append(f"  缺口 {gap['kind']} {gap['ref']}: {gap['need']}")
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description='从网表与器件类别生成电路候选')
    parser.add_argument('db')
    parser.add_argument('--intent')
    parser.add_argument('--datasheet-audit')
    parser.add_argument('--json', help='写出 circuit-candidates.json')
    args = parser.parse_args(argv)
    db = load_json(args.db)
    intent = load_json(args.intent) if args.intent else {}
    audit = load_json(args.datasheet_audit) if args.datasheet_audit else None
    result = build(db, intent, audit)
    if args.json:
        with open(args.json, 'w', encoding='utf-8') as stream:
            json.dump(result, stream, ensure_ascii=False, indent=1)
            stream.write('\n')
    print(summary(result))
    return 0


if __name__ == '__main__':
    sys.exit(main())

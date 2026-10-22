#!/usr/bin/env python3
"""Interfaces between the board's owners (function-tree design §3.3, step 3).

A net joining pins of two owners is an interface net between them, and the nets between one pair make one
interface. Ground nets are never interface nets (they belong to the system's grounds); a connector's pinout lists
them. Four kinds:

- CIRCUIT_PAIR `IF-<A>~<B>`: nets between two ordinary circuits (A, B in key order);
- LINK `LINK-<chain>`: a cross-cutting chain with the parts it owns and every net that reaches one of them;
- SUPPLY `RAIL-<net>`: a rail that reaches parts of two or more owners, with its source's owner; a rail is a net the
  power tree finds a source for or one intent.power_rails declares that behaves as a supply (a name alone is not).
  The source is the power tree's when its pin sits on the rail itself and its library type is not an input, else the one owner of the rectifiers (a diode's cathode, a bridge's + pin) on the
  rail; a rail with none is a gap;
- EXTERNAL `EXT-<connector>`: every pin of a fitted connector (a J/P/CN designator or a part classified as one).

A supply interface lists its `loads` (the owners other than the source). An interface net is `cross_supply` when its
IC endpoints draw from different rails or sit on different reference domains; SIG-C08 is asked only there.

Circuits are named in ids by their candidate ids (`circuit_key`), so renaming a circuit keeps its interfaces; the
display names are in `owners`. Every endpoint is `{owner, pin, role, basis, domain, supply}`: the role comes from the
pin's library type, the part kind, the power tree or the pin name, and a pin none of them gives is listed in `gaps`
(the interface is still made). The domain is the part's reference (the net its ground pin sits on, else the pin's
own net); the supply is the rails the part draws from. Only what the netlist joins, never whether it is right.
"""
import re

import board_intent
import catalog
import row_owner
from audit_datasheets import datasheet_entry_for_ref
from checkers import domains as domains_lib, netgraph as ng, powertree
from checkers.planutil import slug as _slug

SCHEMA_VERSION = 1
CONNECTOR_RE = re.compile(r'^(J|P|CN)\d', re.I)
DRIVER, RECEIVER, BIDIRECTIONAL, PASSIVE = 'DRIVER', 'RECEIVER', 'BIDIRECTIONAL', 'PASSIVE'
NATIVE_ROLES = {'output': DRIVER, 'open_collector': DRIVER, 'open_emitter': DRIVER, 'tri_state': DRIVER,
                'power_out': DRIVER, 'input': RECEIVER, 'power_in': RECEIVER, 'bidirectional': BIDIRECTIONAL}
PINTYPE_ROLES = {'OUT': DRIVER, 'OCL': DRIVER, 'OEM': DRIVER, 'TRI': DRIVER, 'IN': RECEIVER, 'BI': BIDIRECTIONAL}
PART_ROLES = {'gate': RECEIVER, 'drain': DRIVER, 'source': PASSIVE, 'anode': PASSIVE, 'cathode': PASSIVE,
              'led_anode': RECEIVER, 'led_cathode': RECEIVER, 'out_collector': DRIVER, 'out_emitter': PASSIVE,
              'coil': RECEIVER, 'contact': PASSIVE}
PASSIVE_KINDS = ng.TWO_TERMINAL | {ng.CONNECTOR, ng.TESTPOINT, ng.TRANSFORMER, ng.CRYSTAL, ng.BRIDGE_RECTIFIER,
                                   ng.FUSE, ng.JUMPER, ng.SWITCH, ng.BATTERY}
# IC pin names whose direction is conventional; anything else needs the library type or the datasheet.
NAME_ROLES = (
    (re.compile(r'^(V?OUT\d*|VO|DRV\w*|GATE\w*|G?DRV|PWM\w*|TX\w*|DO|SDO|MOSI|INT\w*|PG|PGOOD|FLT_?OUT)$', re.I), DRIVER),
    (re.compile(r'^(FB\w*|CS[+-]?|ISNS\w*|EN\w*|IN\d*|\w+_IN|VBUS\w*|RX\w*|DI|SDI|MISO|HV|VSENSE|SENSE\w*|COMP|SS|RT|ADC\w*)$', re.I), RECEIVER),
    (re.compile(r'^(CC\d*|SDA|SCL|D[+-]|DP|DN|GPIO\w*|IO\d*|P\d+_?\d*)$', re.I), BIDIRECTIONAL),
)


class Deriver:
    def __init__(self, db, intent, datasheet_audit=None):
        kind_intent = board_intent.with_verified_kinds(intent or {}, datasheet_audit)
        self.graph = ng.NetGraph(board_intent.graph_db(db, kind_intent))
        self.domains = domains_lib.derive(self.graph, kind_intent)
        self.tree = powertree.PowerTree(self.graph, kind_intent)
        self.native = db.get('native_pintype') or {}
        self.circuits = {c['id']: c for c in (intent or {}).get('circuits', [])}
        self.key = {cid: '+'.join(sorted(c.get('candidate_ids') or [cid])) for cid, c in self.circuits.items()}
        self.owner_of = row_owner.part_owners(list(self.circuits.values()))
        self.grounds = set(self.domains['grounds']) | {n for n in self.graph.nets if ng.is_ground(n)}
        self.declared_rails = powertree.declared_supply_nets(self.graph, kind_intent)
        self.gaps = []

    def typed_role(self, node):
        if self.native.get(node) in NATIVE_ROLES:
            return NATIVE_ROLES[self.native[node]]
        return PINTYPE_ROLES.get(self.graph.pintype.get(node))

    def role(self, node):
        ref = node.partition('.')[0]
        kind = self.graph.kind(ref)
        if self.typed_role(node):
            return self.typed_role(node), 'pin-type'
        part_role = self.graph.role(node)
        if part_role in PART_ROLES:
            return PART_ROLES[part_role], 'part-kind'
        if kind in PASSIVE_KINDS:
            return PASSIVE, 'part-kind'
        found = self.tree.source_of(self.graph.pin2net.get(node))
        if found and found['source'] == node:
            return DRIVER, 'power-source'
        name, pin = self.graph.pinname.get(node), node.partition('.')[2]
        if ng.name_matches(powertree.SUPPLY_IN_PIN_RE, name, pin):
            return RECEIVER, 'pin-name'
        for pattern, role in NAME_ROLES:
            if ng.name_matches(pattern, name, pin):
                return role, 'pin-name'
        return None, None

    def reference(self, ref, net):
        for node, other in sorted(self.graph.pins_of(ref).items()):
            if other in self.grounds and ng.is_ground(self.graph.pinname.get(ref + '.' + node) or ''):
                return self.domains['nets'].get(other)
        return self.domains['nets'].get(net)

    def supply(self, ref):
        if self.graph.kind(ref) != ng.IC:
            return []
        return sorted({net for pin, net in self.graph.pins_of(ref).items() if net not in self.grounds
                       and (self.native.get(ref + '.' + pin) == 'power_in'
                            or ng.name_matches(powertree.SUPPLY_IN_PIN_RE, self.graph.pinname.get(ref + '.' + pin), pin))})

    def source(self, net):
        found = self.tree.source_of(net)
        # a source reached through a series part may be another rail's; a pin the library calls an input is a load
        if found and not found['path'] and self.typed_role(found['source']) != RECEIVER:
            return self.owner_of.get(found['source'].partition('.')[0])
        owners = set()
        for node in self.graph.nodes_on(net):
            ref = node.partition('.')[0]
            kind = self.graph.kind(ref)
            if not self.graph.is_fitted(ref):
                continue
            if (kind == ng.DIODE and self.graph.role(node) == 'cathode') or (
                    kind == ng.BRIDGE_RECTIFIER and self.graph.pinname.get(node) == '+'):
                owners.add(self.owner_of.get(ref))
        return owners.pop() if len(owners) == 1 else None

    def endpoints(self, net, interface, only=None):
        out = []
        for node in self.graph.nodes_on(net):
            ref = node.partition('.')[0]
            if not self.graph.is_fitted(ref) or (only and ref != only):
                continue
            role, basis = self.role(node)
            if role is None:
                self.gaps.append({'interface': interface, 'pin': node, 'reason': 'role'})
            out.append({'owner': self.owner_of.get(ref), 'pin': node, 'role': role, 'basis': basis,
                        'domain': self.reference(ref, net), 'supply': self.supply(ref)})
        return out

    def is_connector(self, ref):
        return CONNECTOR_RE.match(ref) is not None or self.graph.kind(ref) == ng.CONNECTOR

    def cross_supply(self, endpoints):
        ics = [e for e in endpoints if self.graph.kind(e['pin'].partition('.')[0]) == ng.IC]
        return (len({tuple(e['supply']) for e in ics if e['supply']}) > 1
                or len({e['domain'] for e in ics if e['domain']}) > 1)

    def owners_on(self, net):
        return {self.owner_of[ref] for ref in self.graph.refs_on(net) if ref in self.owner_of}

    def signal_nets(self):
        return [n for n in sorted(self.graph.nets) if n not in self.grounds and n not in self.graph.pseudo]

    def derive(self):
        found = {}

        def add(iid, kind, owners, net, **extra):
            item = found.setdefault(iid, dict({'id': iid, 'kind': kind, 'owners': [], 'nets': []}, **extra))
            item['owners'] = sorted(set(item['owners']) | set(owners))
            if net is not None and net not in {n['net'] for n in item['nets']}:
                ends = self.endpoints(net, iid)
                item['nets'].append({'net': net, 'endpoints': ends, 'cross_supply': self.cross_supply(ends)})

        links = {cid for cid, c in self.circuits.items() if c.get('cross_cutting')}
        for cid in sorted(links):
            add('LINK-' + self.key[cid], 'LINK', [cid], None,
                parts=sorted(ref for ref, owner in self.owner_of.items() if owner == cid))
        for net in self.signal_nets():
            owners = self.owners_on(net)
            if len(owners) < 2:
                continue
            basis = self.tree.rail_basis(net)
            basis = basis if basis in (powertree.DECLARED, powertree.DRIVER) else (
                powertree.DECLARED if net in self.declared_rails else None)
            if basis is not None:
                source = self.source(net)
                if source is None:
                    self.gaps.append({'interface': 'RAIL-' + net, 'pin': None, 'reason': 'source'})
                add('RAIL-' + net, 'SUPPLY', owners, net, basis=basis, source=source,
                    loads=sorted(owners - {source}))
            touched = owners & links
            for cid in sorted(touched):
                add('LINK-' + self.key[cid], 'LINK', owners, net)
            if basis is not None or touched:
                continue
            ordinary = sorted(owners, key=lambda o: self.key[o])
            for i, a in enumerate(ordinary):
                for b in ordinary[i + 1:]:
                    add('IF-%s~%s' % (self.key[a], self.key[b]), 'CIRCUIT_PAIR', [a, b], net)
        for ref in sorted(self.graph.parts):
            if not self.graph.is_fitted(ref) or not self.is_connector(ref):
                continue
            iid = 'EXT-' + ref
            owner = self.owner_of.get(ref)
            add(iid, 'EXTERNAL', [owner] if owner else [], None)
            for pin, net in sorted(self.graph.pins_of(ref).items()):
                if net in self.graph.pseudo or net in {n['net'] for n in found[iid]['nets']}:
                    continue
                if net in self.grounds:   # the pinout names the return, the ground net itself is the system's
                    found[iid]['nets'].append({'net': net, 'endpoints': self.endpoints(net, iid, only=ref),
                                               'cross_supply': False})
                else:
                    found[iid]['owners'] = sorted(set(found[iid]['owners']) | self.owners_on(net))
                    ends = self.endpoints(net, iid)
                    found[iid]['nets'].append({'net': net, 'endpoints': ends, 'cross_supply': self.cross_supply(ends)})
        items = sorted(found.values(), key=lambda i: i['id'])
        for item in items:
            item['nets'].sort(key=lambda n: n['net'])
        gaps = sorted({(g['interface'], g['pin'] or '', g['reason']) for g in self.gaps})
        return {'schema_version': SCHEMA_VERSION, 'interfaces': items,
                'gaps': [{'interface': i, 'pin': p or None, 'reason': r} for i, p, r in gaps]}


def coverage_errors(plan):
    """Interface coverage (REQ-Q07 extended, function-tree step 6): every interface carries the rows its kind asks
    (catalog.INTERFACE_SUBJECTS, SIG-C08 on each cross-supply net, PWR-C14 on a rail a sensitive circuit draws from)
    and, unless it is a rail, a frame."""
    import catalog
    section = plan.get('interfaces')
    if not isinstance(section, dict):
        return ['plan.interfaces missing: plans before schema 6 carry no interfaces; regenerate the plan']
    asked = {tuple(v if isinstance(v, str) else None for v in ((c.get('object') or {}).get('interface'), c.get('rule'),
                                                              (c.get('object') or {}).get('net')))
             for c in plan.get('checks') or [] if isinstance(c, dict) and isinstance(c.get('object') or {}, dict)}
    asked_any = {(i, r) for i, r, _ in asked}
    framed = {f.get('interface') for f in plan.get('functions') or [] if isinstance(f, dict)}
    types = {f.get('circuit'): f.get('circuit_type') for f in plan.get('functions') or [] if isinstance(f, dict)}
    out = []
    for item in section.get('interfaces') or []:
        iid, kind, nets = item['id'], item['kind'], item.get('nets') or []
        if kind == 'SUPPLY':
            if any(types.get(o) in catalog.NOISE_SENSITIVE_TYPES for o in item.get('loads') or []) \
                    and (iid, 'PWR-C14') not in asked_any:
                out.append(f'{iid}: PWR-C14 row missing (a noise-sensitive circuit draws from this rail)')
            continue
        if kind != 'EXTERNAL' and not nets:
            continue
        for rule in catalog.INTERFACE_SUBJECTS.get(kind, ()):
            if (iid, rule) not in asked_any:
                out.append(f'{iid}: {rule} row missing')
        for rule in catalog.INTERFACE_NET_SUBJECTS.get(kind, ()):
            for entry in nets:
                if entry.get('cross_supply') and (iid, rule, entry['net']) not in asked:
                    out.append(f'{iid}: {rule} row missing on {entry["net"]} (its ends draw from different supplies)')
        if iid not in framed:
            out.append(f'{iid}: interface frame missing')
    return out


def derive(db, intent, datasheet_audit=None):
    """The plan's `interfaces` section."""
    return Deriver(db, intent, datasheet_audit).derive()


class InterfacePlanning:
    """接口检查项与接口框架（功能树设计 §3.3、§3.8）；ReviewPlanner 混入。"""

    def plan_interfaces(self):
        """接口检查项（功能树设计第 4 步）：电路对、链路逐接口问 catalog.INTERFACE_SUBJECTS，两端供电或参考地不同的
        网络问 SIG-C08，敏感电路取电的轨问 PWR-C14；连接器的三行在连接器循环里生成。电路对、链路和连接器各建一个框架。"""
        circuit_types = {c['id']: c.get('type') for c in self.intent.get('circuits', [])}
        role_gaps = {}
        for gap in self.interfaces['gaps']:
            role_gaps.setdefault(gap['interface'], []).append(
                f'interface-role:{gap["pin"]}' if gap['reason'] == 'role' else f'rail-source:{gap["interface"]}')
        for item in self.interfaces['interfaces']:
            iid, kind = item['id'], item['kind']
            nets = [n['net'] for n in item['nets']]
            parts = sorted({e['pin'].partition('.')[0] for n in item['nets'] for e in n['endpoints'] if e['owner']})
            gaps = role_gaps.get(iid, []) + [
                f'datasheet:{ref}' for ref in parts if self.db.get('parts', {}).get(ref) and powertree.IC_REF_RE.match(ref)
                and not (datasheet_entry_for_ref(self.datasheet_audit, ref) or {}).get('status') == 'AVAILABLE']
            trigger = [f'interface:{iid}']
            if kind == 'SUPPLY':
                loads = [o for o in item.get('loads', []) if circuit_types.get(o) in catalog.NOISE_SENSITIVE_TYPES]
                if loads:
                    row = self._ready_check('PWR-C14', {'interface': iid, 'net': nets[0], 'loads': loads}, gaps, trigger)
                    row['question'] = catalog.interface_question('PWR-C14', iid, nets, loads=loads)
                continue
            if kind != 'EXTERNAL' and not nets:
                continue
            for rule in catalog.INTERFACE_SUBJECTS.get(kind, ()) if kind != 'EXTERNAL' else ():
                row = self._ready_check(rule, {'interface': iid, 'nets': nets}, gaps, trigger)
                row['question'] = catalog.interface_question(rule, iid, nets, parts)
            for rule in catalog.INTERFACE_NET_SUBJECTS.get(kind, ()):
                for entry in item['nets']:
                    if entry['cross_supply']:
                        row = self._ready_check(rule, {'interface': iid, 'net': entry['net']}, gaps, trigger, key=iid)
                        row['question'] = catalog.interface_question(rule, iid, [entry['net']])
            members = [c for c in self.checks if (c.get('object') or {}).get('interface') == iid]
            if not members:
                continue
            frame = {'id': 'FN-' + _slug(iid), 'interface': iid, 'interface_kind': kind,
                     'question': catalog.interface_frame_question(kind, iid, item['owners'], nets, parts),
                     'objects': {'refs': parts, 'nets': nets}, 'states': ['run'], 'members': [],
                     'blind_spots': {}, 'checklist': list(catalog.BOUNDING_STEPS)}
            for row in members:
                if kind == 'EXTERNAL':
                    row['question'] = catalog.interface_question(row['rule'], iid, nets, [row['object']['ref']])
                row['function_id'] = frame['id']
                row['aspect'] = catalog.title(row['rule'])
                frame['members'].append({'check_id': row['id'], 'rule': row['rule'], 'aspect': row['aspect'], 'state': None})
                frame['blind_spots'][row['rule']] = catalog.explanation(row['rule'])['risk_if_omitted']
            self.functions.append(frame)

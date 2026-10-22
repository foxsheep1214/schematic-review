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
- EXTERNAL `EXT-<connector>`: every pin of a fitted connector.

Circuits are named in ids by their candidate ids (`circuit_key`), so renaming a circuit keeps its interfaces; the
display names are in `owners`. Every endpoint is `{owner, pin, role, basis, domain, supply}`: the role comes from the
pin's library type, the part kind, the power tree or the pin name, and a pin none of them gives is listed in `gaps`
(the interface is still made). The domain is the part's reference (the net its ground pin sits on, else the pin's
own net); the supply is the rails the part draws from. Only what the netlist joins, never whether it is right.
"""
import re

import board_intent
import row_owner
from checkers import domains as domains_lib, netgraph as ng, powertree

SCHEMA_VERSION = 1
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
                item['nets'].append({'net': net, 'endpoints': self.endpoints(net, iid)})

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
                add('RAIL-' + net, 'SUPPLY', owners, net, basis=basis, source=source)
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
            if not self.graph.is_fitted(ref) or self.graph.kind(ref) != ng.CONNECTOR:
                continue
            iid = 'EXT-' + ref
            owner = self.owner_of.get(ref)
            add(iid, 'EXTERNAL', [owner] if owner else [], None)
            for pin, net in sorted(self.graph.pins_of(ref).items()):
                if net in self.graph.pseudo or net in {n['net'] for n in found[iid]['nets']}:
                    continue
                if net in self.grounds:   # the pinout names the return, the ground net itself is the system's
                    found[iid]['nets'].append({'net': net, 'endpoints': self.endpoints(net, iid, only=ref)})
                else:
                    found[iid]['owners'] = sorted(set(found[iid]['owners']) | self.owners_on(net))
                    found[iid]['nets'].append({'net': net, 'endpoints': self.endpoints(net, iid)})
        items = sorted(found.values(), key=lambda i: i['id'])
        for item in items:
            item['nets'].sort(key=lambda n: n['net'])
        gaps = sorted({(g['interface'], g['pin'] or '', g['reason']) for g in self.gaps})
        return {'schema_version': SCHEMA_VERSION, 'interfaces': items,
                'gaps': [{'interface': i, 'pin': p or None, 'reason': r} for i, p, r in gaps]}


def derive(db, intent, datasheet_audit=None):
    """The plan's `interfaces` section."""
    return Deriver(db, intent, datasheet_audit).derive()

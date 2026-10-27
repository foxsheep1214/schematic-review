#!/usr/bin/env python3
"""State-bound decoupling inventory and review inputs, never a PDN solver.

Only direct supply/return pairs are matched. No series component is shorted,
no package/ESR/DC-bias estimate is invented, and no electrical verdict is made.
"""
import argparse
from collections import defaultdict
from copy import deepcopy
from decimal import Decimal, DecimalException
import json
import re

import board_intent
from board_intent import input_fingerprint
from electrical_contract import db_fingerprint, finite, load_json
from part_words import CONNECTOR, classify
from i2c_topology import digest, validate_db_shape

KINDS = {'capacitor', 'resistor', 'ferrite', 'inductor', 'jumper', 'switch', 'other',
         'bridge_rectifier', 'transformer'}
# 3: a group no longer lists its return pins (every official return pin of the part, `return_net` only where they
# sit on several nets) and states at most one datasheet clause per requirement kind, without an id.
# 4: groups come from the official pin map, one per declared device and supply net; a group entry names its
# (ref, net) and gives only the purpose, the clauses and the return net (fixed requirements, step 6).
SECTION_SCHEMA_VERSION = 4
# Datasheet-verified device kinds (intent.device_kinds) that have no IC supply pins to bypass.
NO_SUPPLY_KINDS = {'bridge_rectifier', 'transformer', 'connector'}
# Netlist kinds that carry no IC supply pin (checkers.netgraph kinds).
NO_SUPPLY_PARTS = {'inductor', 'transformer', 'ferrite', 'resistor', 'capacitor', 'fuse', 'bridge_rectifier'}
REQUIREMENT_KINDS = {'connection', 'capacitance', 'rating'}
# 组用途：普通旁路；按原厂条款不需要直接电容（如高压启动/检测脚）；片内稳压器输出电容（如 V5/VCAP）。
# 后两类必须有对应的 connection 条款作出处。
GROUP_PURPOSES = {'bypass', 'no_direct_capacitor', 'regulator_output'}
NATIVE_SYMBOL_KINDS = {
    'Device:C': 'capacitor', 'Device:C_Polarized': 'capacitor',
    'Device:C_Small': 'capacitor', 'Device:C_Polarized_Small': 'capacitor',
    'Device:R': 'resistor', 'Device:R_Small': 'resistor',
    'Device:L': 'inductor', 'Device:L_Small': 'inductor',
    'Device:Ferrite_Bead': 'ferrite', 'Device:Ferrite_Bead_Small': 'ferrite',
}
POWER = re.compile(r'(^|[_/.-])(VDD\w*|VCC\w*|AVDD\w*|AVCC\w*|DVDD\w*|DVCC\w*|VIN|VOUT|VBAT|VBUS)(?=$|[_/.-])', re.I)
RETURN_PIN_RE = re.compile(r'(^|[_/.-])(?:GND\w*|[APD]?VSS\w*|[APD]GND\w*)(?=$|[_/.-])', re.I)   # a pin name
PASSIVE_PREFIX = re.compile(r'^(?:R|C|L|FB|F|JP|TP|J|P|CN|Y)\d', re.I)
CAP_TOKEN = re.compile(r'^(?:(\d+(?:\.\d*)?|\.\d+)([eE][+-]?\d+)?\s*([pPnNuUµμm]?)[fF]|'
                       r'(\d+(?:\.\d*)?|\.\d+)\s*([pPnNuUµμm])|'
                       r'(\d+)([pPnNuUµμm])(\d+))(?:$|(?=[/;,\s]))')


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def parse_capacitance(value):
    """Parse a leading explicit capacitance token; never infer a unit/code.

    Examples: 100nF, 4.7u/10%/16V, 4n7, 1e-6F. Bare 104 is ambiguous.
    Remaining BOM fields are not interpreted as tolerance, rating or DC bias.
    """
    if not isinstance(value, str):
        return None
    match = CAP_TOKEN.match(value.strip())
    if not match:
        return None
    a, exponent, unit, b, unit_b, c, unit_c, fraction = match.groups()
    number = a + (exponent or '') if a is not None else b if b is not None else c + '.' + fraction
    unit = unit if a is not None else unit_b if b is not None else unit_c
    scales = {'': '1', 'p': '1e-12', 'n': '1e-9', 'u': '1e-6', 'µ': '1e-6', 'μ': '1e-6', 'm': '1e-3'}
    try:
        result = float(Decimal(number) * Decimal(scales[unit.lower()]))
        return result if finite(result) and result > 0 else None
    except (DecimalException, OverflowError, ValueError):
        return None


def _db_errors(db):
    errors = validate_db_shape(db)
    if errors:
        return errors
    for field in ('declared_pinname', 'declared_pintype'):
        values = db.get(field, {})
        if not isinstance(values, dict) or not all(_text(n) and isinstance(v, str) for n, v in values.items()):
            errors.append('db.' + field + ' must map physical nodes to strings')
    return errors


def validate_decoupling_intent(intent, db=None):
    from reviewed_declarations import resolve
    try:
        intent = resolve(intent, db)
    except ValueError as error:
        return [str(error)]
    if db is not None:
        errors = _db_errors(db)
        if errors:
            return errors
    if intent is None or isinstance(intent, dict) and 'decoupling' not in intent:
        return []
    if not isinstance(intent, dict) or not isinstance(intent.get('decoupling'), dict):
        return ['decoupling must be an object']
    cfg, errors = intent['decoupling'], board_intent.requires_assemblies(intent, 'decoupling')

    def require(ok, message):
        if not ok:
            errors.append('decoupling: ' + message)

    def fields(obj, allowed, label):
        require(not set(obj) - set(allowed), label + ' has unsupported fields')

    def ref_ok(ref):
        return _text(ref) and (db is None or ref in db.get('parts', {}))

    moved = {'states', 'input_sha256', 'devices'} & set(cfg)
    require(not moved, ', '.join(sorted(moved)) + ' moved to intent.assemblies/intent.input_sha256/intent.devices')
    fields({k: v for k, v in cfg.items() if k not in moved}, ('schema_version', 'groups', 'components'), 'root')
    require(type(cfg.get('schema_version')) is int and cfg['schema_version'] == SECTION_SCHEMA_VERSION,
            'schema_version must be %d' % SECTION_SCHEMA_VERSION)
    devices = intent.get('devices', {})
    devices = devices if isinstance(devices, dict) else {}
    components = cfg.get('components', {})
    require(isinstance(components, dict), 'components must be an object')
    for ref, comp in components.items() if isinstance(components, dict) else []:
        require(ref_ok(ref), 'unknown component ' + str(ref))
        require(ref not in devices, 'device cannot also be a passive/excluded component')
        if not isinstance(comp, dict):
            require(False, 'component must be an object')
            continue
        fields(comp, ('kind', 'citation'), 'component')
        require(isinstance(comp.get('kind'), str) and comp['kind'] in KINDS, 'unsupported component kind')
        require(_text(comp.get('citation')), 'component kind needs citation')
    groups = cfg.get('groups', [])
    require(isinstance(groups, list), 'groups must be an array')
    seen = set()
    for group in groups if isinstance(groups, list) else []:
        if not isinstance(group, dict):
            require(False, 'group must be an object')
            continue
        derived = {'id', 'supply_nodes'} & set(group)
        require(not derived, '%s are derived from the official pin map (one group per device and supply net); '
                'name the group by ref and net' % ', '.join(sorted(derived)))
        fields({k: v for k, v in group.items() if k not in derived},
               ('ref', 'net', 'return_net', 'citation', 'requirements', 'purpose'), 'group')
        purpose = group.get('purpose', 'bypass')
        require(purpose in GROUP_PURPOSES, 'unsupported group purpose')
        if purpose != 'bypass':
            reqs = group.get('requirements') if isinstance(group.get('requirements'), list) else []
            require(any(isinstance(r, dict) and r.get('kind') == 'connection' and _text(r.get('citation'))
                        for r in reqs), purpose + ' group needs a cited connection requirement')
        ref, net = group.get('ref'), group.get('net')
        gid = '%s:%s' % (ref, net)
        require(_text(ref) and _text(net), 'a group entry names its ref and supply net')
        require(gid not in seen, 'group %s is given twice' % gid)
        seen.add(gid)
        require(ref_ok(ref), 'group ref missing/unknown')
        device = devices.get(ref) if _text(ref) else None
        require(isinstance(device, dict), 'group ref needs an exact device pin map in intent.devices')
        pins = device.get('pins', {}) if isinstance(device, dict) else {}
        pins = pins if isinstance(pins, dict) else {}
        if db is not None and _text(ref) and _text(net):
            supply = {db.get('pin2net', {}).get(n) or 'UNCONNECTED:' + n for n in supply_pins(ref, pins)}
            require(net in supply, '%s: no official power pin of %s sits on %s (its supply nets: %s)'
                    % (gid, ref, net, ', '.join(sorted(supply)) or 'none'))
        if db is not None and _text(ref):
            nets = sorted({db.get('pin2net', {}).get(n) for n in return_pins(ref, pins)} - {None})
            if len(nets) > 1:
                require(group.get('return_net') in nets and _text(group.get('citation')),
                        '%s: the return pins of %s sit on %s; name the group\'s return_net (one of them) with the '
                        'grouping citation' % (gid, ref, ', '.join(nets)))
            else:
                require('return_net' not in group, '%s: return_net is only for a part whose return pins sit on '
                        'more than one net' % gid)
        elif 'return_net' in group:
            require(_text(group['return_net']), 'return_net must be a net name')
        requirements = group.get('requirements', [])
        require(isinstance(requirements, list), 'requirements must be an array')
        kinds = set()
        for req in requirements if isinstance(requirements, list) else []:
            if not isinstance(req, dict):
                require(False, 'requirement must be an object')
                continue
            fields(req, ('kind', 'criterion', 'citation'), 'requirement')
            require(isinstance(req.get('kind'), str) and req['kind'] in REQUIREMENT_KINDS, 'unsupported requirement kind')
            require(req.get('kind') not in kinds, 'one clause per kind: %s states %s twice' % (gid, req.get('kind')))
            kinds.add(req.get('kind'))
            require(_text(req.get('criterion')) and _text(req.get('citation')), 'requirement needs criterion/citation')
    return errors


def supply_pins(ref, pins):
    """Every pin of `ref` the official pin map gives the power role."""
    return sorted(ref + '.' + number for number, spec in (pins or {}).items()
                  if isinstance(spec, dict) and spec.get('role') == 'power')


def return_pins(ref, pins):
    """Every pin of `ref` the official pin map gives the return role."""
    return sorted(ref + '.' + number for number, spec in (pins or {}).items()
                  if isinstance(spec, dict) and spec.get('role') == 'return')


class Inventory:
    def __init__(self, db, cfg, devices=None, verified_kinds=None):
        self.db, self.cfg = db, cfg or {}
        self.parts, self.nets = db.get('parts', {}), db.get('nets', {})
        self.pin2net = db.get('pin2net', {})
        self.names = dict(db.get('declared_pinname', {}), **db.get('pinname', {}))
        self.declares_pins = 'declared_pinname' in db   # parser listed every symbol pin, so 0 pins is real
        self.types = dict(db.get('declared_pintype', {}), **db.get('pintype', {}))
        self.devices, self.components = devices or {}, self.cfg.get('components', {})
        self.verified_kinds = verified_kinds or {}
        self.non_decoupling_connectors = []
        self.pseudo = set(db.get('pseudo_nets', []))
        self.nodes, self.input_gaps = defaultdict(set), set()
        for node in set(self.names) | set(self.types) | set(self.pin2net):
            ref, dot, number = node.partition('.')
            if not dot or not number or ref not in self.parts:
                self.input_gaps.add('invalid-physical-node:' + node)
            self.nodes[ref].add(node)
        seen = set()
        for net, nodes in self.nets.items():
            for node in nodes:
                ref = node.partition('.')[0]
                self.nodes[ref].add(node)
                if node in seen or self.pin2net.get(node) != net or ref not in self.parts:
                    self.input_gaps.add('inconsistent-index:' + node)
                seen.add(node)
        for node, net in self.pin2net.items():
            if node not in self.nets.get(net, []):
                self.input_gaps.add('inconsistent-index:' + node)
        self.names_resolved_by_official_pinout, self.unresolved_pin_names = [], []
        if db.get('export_errors'):
            self.input_gaps.add('netlist-integrity/export')
        elif db.get('integrity', {}).get('self_check_passed') is False:
            split = self.official_name_gap(db)
            if split is None:
                self.input_gaps.add('netlist-integrity/export')
            else:
                self.names_resolved_by_official_pinout, self.unresolved_pin_names = split

    def official_name_gap(self, db):
        """(resolved, unresolved) unnamed functional pins, or None for any other problem.

        Decoupling reads a pin's role from intent.devices before its name, so a
        pin in a complete official pin map is resolved. A missing name only
        changes the role of that device's own pins, never net connectivity, so
        an unresolved name stays a gap of its own device (and of discovery),
        not of every group. Any other self-check problem keeps the
        whole-netlist gap. DOC-Q01 still reports the missing names.
        """
        from parse_netlist import MISSING_PIN_NAMES, integrity_problems  # parse_netlist imports checkers
        copy = dict(db)
        try:
            problems = integrity_problems(copy)
        except (KeyError, TypeError, AttributeError):
            return None  # Not a full parser db: keep the whole-netlist gap.
        if not problems or any(not p.startswith(MISSING_PIN_NAMES) for p in problems):
            return None
        missing = copy.get('pin_name_coverage', {}).get('missing_functional_pins', [])
        if not missing:
            return None
        resolved, unresolved = [], []
        for node in sorted(missing):
            ref, _, pin = node.partition('.')
            device = self.devices.get(ref, {})
            known = device.get('pinout_complete') is True and device.get('pins', {}).get(pin, {}).get('role')
            (resolved if known else unresolved).append(node)
        return resolved, unresolved

    def kind(self, ref):
        if ref in self.components:
            return self.components[ref]['kind']
        native = NATIVE_SYMBOL_KINDS.get(self.parts.get(ref, {}).get('prim'))
        if native:
            return native
        for pattern, kind in ((r'^C\d', 'capacitor'), (r'^R\d', 'resistor'), (r'^FB\d', 'ferrite'),
                              (r'^L\d', 'inductor'), (r'^JP\d', 'jumper')):
            if re.match(pattern, ref, re.I):
                return kind
        return 'unmodeled'

    def two_terminal(self, ref):
        """A two-pin part (diode/TVS/LED/thermistor/varistor/fuse...) or a pinless symbol (mounting hole,
        fiducial; only when the parser declares symbol pins) has no supply/return pair to decouple; two-pin parts are checked for polarity and
        orientation by other rules. A one-pin part stays unverified: it may be a fragment of a larger device."""
        count = len(self.nodes.get(ref, set()))
        return count == 2 or (count == 0 and self.declares_pins)

    def supply_pin(self, node):
        """Only power/return pins matter to decoupling; other pin-map differences are DEV-D02's job."""
        return self.role(node) in ('power', 'return')

    def kind_basis(self, ref):
        if ref in self.components:
            return 'declared'
        if self.parts.get(ref, {}).get('prim') in NATIVE_SYMBOL_KINDS:
            return 'native-symbol'
        return 'refdes-hint'

    def role(self, node):
        ref, _, pin = node.partition('.')
        spec = self.devices.get(ref, {}).get('pins', {}).get(pin)
        if spec:
            return spec['role']
        name, kind = self.names.get(node, ''), self.types.get(node, '').upper()
        if RETURN_PIN_RE.search(name) or kind in ('GROUND', 'GND'):
            return 'return'
        if POWER.search(name) or kind in ('POWER', 'POWER_IN', 'POWER_OUT'):
            return 'power'
        return 'other'

    @staticmethod
    def locally_cited(group, device):
        """Declared group whose own supply/return pins carry cited roles: an incomplete map of
        the rest of the device stays a discovery gap (PWR-D01), not this group's gate."""
        pins = device.get('pins', {})
        return (group['origin'] == 'declared' and bool(device.get('citation'))
                and all(pins.get(n.partition('.')[2], {}).get('role') == role
                        for field, role in (('supply_nodes', 'power'), ('return_nodes', 'return'))
                        for n in group[field]) and bool(group['supply_nodes']) and bool(group['return_nodes']))

    def groups(self):
        """One group per declared device and supply net from the official pin map (origin 'declared': the pin map is
        the declaration), with the reviewer's entry for that (ref, net); candidate groups for parts without a map."""
        entries = {(g.get('ref'), g.get('net')): g for g in self.cfg.get('groups', [])}
        groups = []
        for ref, device in sorted(self.devices.items()):
            # A verified connector, bridge or transformer has no IC supply to bypass; an explicit entry still wins.
            explicit_only = self.verified_kinds.get(ref, {}).get('kind') in NO_SUPPLY_KINDS
            by_net = defaultdict(list)
            for node in supply_pins(ref, device.get('pins')):
                by_net[self.pin2net.get(node) or 'UNCONNECTED:' + node].append(node)
            for net, supplies in sorted(by_net.items()):
                if explicit_only and (ref, net) not in entries:
                    continue
                entry = entries.get((ref, net), {})
                group = {'id': ref + ':' + net, 'ref': ref, 'supply_nodes': supplies, 'origin': 'declared',
                         'requirements': deepcopy(entry.get('requirements', [])),
                         'purpose': entry.get('purpose', 'bypass'),
                         'citation': entry.get('citation') or device.get('citation')}
                returns = return_pins(ref, device.get('pins'))
                if entry.get('return_net'):
                    group['return_net'] = entry['return_net']
                    returns = [n for n in returns if self.pin2net.get(n) == entry['return_net']]
                group['return_nodes'] = returns
                groups.append(group)
        assigned = {n for g in groups for n in g['supply_nodes']}
        for ref, device in self.devices.items():
            self.nodes[ref].update(ref + '.' + pin for pin, spec in device['pins'].items()
                                   if not (isinstance(spec, dict) and spec.get('role') == 'absent'))
        for ref, nodes in sorted(self.nodes.items()):
            if self.kind(ref) != 'unmodeled':
                continue
            # A verified passive connector transmits power; that alone is not
            # an IC bypass requirement. Explicit source-bound groups still win.
            kind = self.verified_kinds.get(ref, {})
            if kind.get('kind') == CONNECTOR and not any(g['ref'] == ref for g in groups):
                self.non_decoupling_connectors.append({'ref': ref,
                    'citation': kind['citation'], 'basis': 'datasheet-verified',
                    'supply_nodes': sorted(n for n in nodes if self.role(n) == 'power'),
                    'return_nodes': sorted(n for n in nodes if self.role(n) == 'return'),
                    'scope': 'No implicit IC bypass obligation; connector pinout, ratings and port protection remain separate checks.'})
                continue
            by_net = defaultdict(list)
            for node in sorted(nodes - assigned):
                if self.role(node) == 'power':
                    by_net[self.pin2net.get(node) or 'UNCONNECTED:' + node].append(node)
            returns = sorted(n for n in nodes if self.role(n) == 'return')
            for net, supplies in sorted(by_net.items()):
                groups.append({'id': 'candidate:' + ref + ':' + net, 'ref': ref,
                               'supply_nodes': supplies, 'return_nodes': returns,
                               'origin': 'candidate', 'requirements': []})
        return groups

    def device_inventory(self):
        output = []
        for ref, device in sorted(self.devices.items()):
            official_only, symbol_only = board_intent.pin_sets(self.db, ref, device)
            output.append({'ref': ref, **deepcopy(device), 'official_only_nodes': official_only,
                           'symbol_only_nodes': symbol_only})
        return output

    def state_inventory(self, state, groups, device_records):
        population, sid = state.get('population', {}), state['id']
        caps, by_net = {}, defaultdict(set)
        for ref in sorted(self.parts):
            if self.kind(ref) != 'capacitor':
                continue
            nodes = sorted(self.nodes[ref])
            nets = [self.pin2net.get(n) for n in nodes]
            gaps = []
            if self.kind_basis(ref) == 'refdes-hint':
                gaps.append('component-kind:' + ref)
            if len(nodes) != 2 or any(n is None or n in self.pseudo for n in nets):
                gaps.append('capacitor-two-pin-connection:' + ref)
            if len(nodes) == 2 and nets[0] == nets[1]:
                gaps.append('capacitor-same-net:' + ref)
            if ref not in population:
                gaps.append('population:' + ref)
            caps[ref] = {'ref': ref, 'nodes': nodes, 'nets': nets, 'value': self.parts[ref].get('value'),
                         'nominal_f': parse_capacitance(self.parts[ref].get('value')),
                         'populated': population.get(ref), 'parsed_nc': self.parts[ref].get('nc'),
                         'kind_basis': self.kind_basis(ref),
                         'kind_source': self.components[ref]['citation'] if ref in self.components
                             else 'db.parts.' + ref + '.prim=' + str(self.parts[ref].get('prim')),
                         'gaps': gaps, 'matched_groups': []}
            for net in set(nets) - {None}:
                by_net[net].add(ref)
        output = []
        devices = {d['ref']: d for d in device_records}
        for group in sorted(groups, key=lambda g: (g['ref'], g['id'], g['origin'])):
            ref = group['ref']
            gaps, value_gaps = set(self.input_gaps), set()
            gaps.update('pin-name-unresolved:' + n for n in self.unresolved_pin_names if n.partition('.')[0] == ref)
            if ref not in population:
                gaps.add('population:' + ref)
            device = devices.get(ref)
            if not device or not (device['pinout_complete'] or self.locally_cited(group, device)):
                gaps.add('official-full-pinout:' + ref)
            if device:
                gaps.update('official-pin-absent:' + n for n in device['official_only_nodes'] if self.supply_pin(n))
                gaps.update('pin-not-in-official-map:' + n for n in device['symbol_only_nodes'] if self.supply_pin(n))
            if group['origin'] != 'declared':
                gaps.add('confirm-group-and-return:' + group['id'])
            supply_nets, return_nets = set(), set()
            for field, target in (('supply_nodes', supply_nets), ('return_nodes', return_nets)):
                for node in group[field]:
                    net = self.pin2net.get(node)
                    if net is None or net in self.pseudo:
                        gaps.add('unconnected-or-pseudo-pin:' + node)
                    elif node not in self.nets.get(net, []):
                        gaps.add('inconsistent-index:' + node)
                    else:
                        target.add(net)
            if len(supply_nets) != 1:
                gaps.add('need-one-direct-supply-net')
            if len(return_nets) != 1:
                gaps.add('need-one-explicit-return-net')
            if supply_nets & return_nets:
                gaps.add('supply-return-same-net')
            gid = 'DECAP-' + digest([sid, group['origin'], group['id'], ref])[:20]
            matches, rejected, fitted, boundaries = [], [], [], []
            touched = sorted(set().union(*(by_net[n] for n in supply_nets)))
            for cap_ref in touched:
                cap = caps[cap_ref]
                pair = len(cap['nodes']) == 2 and len(supply_nets) == len(return_nets) == 1 and (
                    supply_nets != return_nets and set(cap['nets']) == supply_nets | return_nets)
                if not pair:
                    rejected.append({'ref': cap_ref, 'nets': cap['nets'], 'reason': 'not-direct-supply-return-pair'})
                    # A malformed/unknown component cannot silently disappear.
                    if cap['populated'] is not False and (len(cap['nodes']) != 2 or None in cap['nets']):
                        gaps.update(cap['gaps'])
                    continue
                matches.append(cap_ref)
                cap['matched_groups'].append(gid)
                if cap['populated'] is not False:
                    gaps.update(cap['gaps'])
                if cap['populated'] is True and not cap['gaps']:
                    fitted.append(cap_ref)
                    if cap['nominal_f'] is None:
                        value_gaps.add('capacitance-unparsed:' + cap_ref)
            # Boundaries are listed, never crossed -- including 0R and closed jumpers.
            refs = {n.partition('.')[0] for net in supply_nets for n in self.nets.get(net, [])}
            for other_ref in sorted(refs - {ref} - set(caps)):
                nodes = sorted(self.nodes[other_ref])
                kind = self.kind(other_ref)
                if kind in ('resistor', 'ferrite', 'inductor', 'jumper', 'switch'):
                    boundaries.append({'ref': other_ref, 'kind': kind, 'nodes': nodes,
                                       'nets': [self.pin2net.get(n) for n in nodes],
                                       'populated': population.get(other_ref), 'crossed': False})
            known = [caps[c]['nominal_f'] for c in fitted if caps[c]['nominal_f'] is not None]
            subtotal = float(sum((Decimal(str(v)) for v in known), Decimal(0)))
            if not finite(subtotal):
                value_gaps.add('nominal-sum-overflow')
                subtotal = None
            output.append({'id': gid, 'declared_id': group['id'], 'origin': group['origin'],
                'ref': ref, 'state': sid, 'populated': population.get(ref),
                'supply_nodes': sorted(group['supply_nodes']), 'return_nodes': sorted(group['return_nodes']),
                'supply_nets': sorted(supply_nets), 'return_nets': sorted(return_nets),
                'capacitors': matches, 'fitted_capacitors': fitted, 'fitted_count': len(fitted),
                'known_nominal_subtotal_f': subtotal,
                'nominal_total_f': subtotal if not gaps and not value_gaps else None,
                'rejected_capacitors': rejected, 'boundaries': boundaries,
                'gaps': sorted(gaps), 'capacitance_gaps': sorted(value_gaps),
                'coverage': 'INCOMPLETE' if gaps else 'DISCOVERED',
                'observations': [] if fitted else ['no-confirmed-fitted-matching-capacitor'],
                'requirements': deepcopy(group.get('requirements', [])), 'citation': group.get('citation'),
                'purpose': group.get('purpose', 'bypass')})
        return {'id': sid, 'citation': state.get('citation'), 'groups': output,
                'capacitors': list(caps.values())}


def build_decoupling_inventory(db, intent=None):
    errors = _db_errors(db) or board_intent.validate(intent, db) or validate_decoupling_intent(intent, db)
    if errors:
        raise ValueError('; '.join(errors))
    from reviewed_declarations import resolve, KEY
    source_intent = intent
    intent = resolve(intent, db)
    cfg = (intent or {}).get('decoupling')
    inv = Inventory(db, cfg, (intent or {}).get('devices'), board_intent.declared_kinds(intent))
    groups, device_records = inv.groups(), inv.device_inventory()
    candidates = [ref for ref in inv.parts if ref not in inv.devices and
                  inv.kind(ref) == 'unmodeled' and not PASSIVE_PREFIX.match(ref)
                  and classify(ref, inv.parts[ref])[0] != CONNECTOR   # keyword-identified headers/terminals
                  # a transformer, inductor or other part classify reads as having no supply pin needs no pin table
                  # for decoupling even when undeclared (R7 acceptance 2026-10-25, codex1 SR-04: T301)
                  and classify(ref, inv.parts[ref])[0] not in NO_SUPPLY_PARTS
                  and inv.verified_kinds.get(ref, {}).get('kind') not in NO_SUPPLY_KINDS]
    two_terminal = sorted(ref for ref in candidates if inv.two_terminal(ref))
    unknown = sorted(set(candidates) - set(two_terminal))
    discovery_gaps = set(inv.input_gaps) | {'unverified-device-pinout:' + r for r in unknown}
    discovery_gaps.update('pin-name-unresolved:' + n for n in inv.unresolved_pin_names)
    for device in device_records:
        # An inductor, transformer or other part without a supply pin has no IC supply to bypass: its incomplete pin
        # table is not a decoupling gap (its terminals and ratings are checked elsewhere).
        passive = (classify(device['ref'], inv.parts.get(device['ref']) or {})[0] in NO_SUPPLY_PARTS
                   or inv.verified_kinds.get(device['ref'], {}).get('kind') in NO_SUPPLY_KINDS)
        if not device['pinout_complete'] and not (passive and not supply_pins(device['ref'], device.get('pins'))):
            discovery_gaps.add('official-full-pinout:' + device['ref'])
        discovery_gaps.update('official-pin-absent:' + n for n in device['official_only_nodes'] if inv.supply_pin(n))
        discovery_gaps.update('pin-not-in-official-map:' + n for n in device['symbol_only_nodes'] if inv.supply_pin(n))
    # Without declared assemblies every part's population is unknown (netlist nc is not assembly proof, as in
    # i2c_topology); the other checkers use the as-built state with one gap instead (checker-conventions.md 装配状态).
    states = (intent or {}).get('assemblies') or [{'id': 'UNSPECIFIED', 'population': {}}]
    result = {'schema_version': 1, 'db_sha256': db_fingerprint(db), 'input_sha256': input_fingerprint(db),
              # power_rails: the PWR-C10 rating proposal reads the passive-stress pre-judgement, which needs the rails
              'context': deepcopy(board_intent.context(intent, 'decoupling', extra=('devices', 'power_rails'))), 'scope': 'direct-net schematic inventory only; nominal is not effective capacitance; no electrical or PCB PASS',
              'devices': device_records, 'unverified_device_refs': unknown,
              'pin_names_resolved_by_official_pinout': inv.names_resolved_by_official_pinout,
              'non_decoupling_connectors': inv.non_decoupling_connectors,
              'two_terminal_no_supply_refs': two_terminal, 'discovery_gaps': sorted(discovery_gaps),
              'states': [inv.state_inventory(s, groups, device_records) for s in sorted(states, key=lambda s: s['id'])]}
    if isinstance(source_intent, dict) and KEY in source_intent:
        # Revalidation needs the original review context, not a flattened copy
        # that loses the provenance or silently refreshes its hashes.
        result['context'] = deepcopy(source_intent)
        result['reviewed_declarations'] = {
            'digest': source_intent[KEY]['digest'], 'reviewer': deepcopy(source_intent[KEY]['reviewer']),
            'status': 'CURRENT', 'scope': 'roles/grouping only; no electrical verdict',
            'non_ic_roles': {ref: deepcopy(c) for ref, c in inv.components.items()
                             if c.get('kind') in ('bridge_rectifier', 'transformer')}}
    result['digest'] = digest(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('db')
    parser.add_argument('--intent')
    parser.add_argument('--json', required=True)
    args = parser.parse_args()
    try:
        intent = load_json(args.intent) if args.intent else None
        if args.intent and not isinstance(intent, dict):
            raise ValueError('explicit intent.json root must be an object')
        result = build_decoupling_inventory(load_json(args.db), intent)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    with open(args.json, 'w', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
    groups = [g for s in result['states'] for g in s['groups']]
    print(f'Decoupling inventory: {len(groups)} groups; no electrical verdict; input_sha256={result["input_sha256"]}')


if __name__ == '__main__':
    main()

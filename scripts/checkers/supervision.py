#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""监控与看门狗检查器：复位链、喂狗输入与逐电源域监控覆盖。

识别监控器/看门狗器件、被监测的轨、复位输出到复位输入的路径与喂狗来源。
哪些轨必须监测由需求裁定，本检查器只登记覆盖与缺口；脉宽是否足够由保证值核对（RST-E03）按保证值判定。
"""
import re
import hashlib
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
import subprocess
import unicodedata
import copy

from solve_dividers import parse_resistor

import catalog
import board_intent
from datasheet_kinds import pdf_page_texts
from . import inventory as inv
from . import netgraph as ng
from . import powertree
from . import states as state_lib
from .base import Checker
from .planutil import slug

WATCHDOG_IN_RE = re.compile(r'^(WDI|WDT_IN|WD_IN|WATCHDOG_IN|SET\d?)$', re.I)
RESET_OUT_RE = re.compile(r'^(N?RESET\w*|N?RST\w*|WDO|POR|PFO|RESETB|RESET_N)$', re.I)
RESET_IN_RE = re.compile(r'^(N?RESET\w*|N?RST\w*|MR|POR|XRES|RESETN|NRST)$', re.I)
SENSE_RE = re.compile(r'^(SENSE\d*|VMON\d*|VSENSE\d*|PFI|IN\d*_MON|MON\d*)$', re.I)
MANUAL_RESET_RE = re.compile(r'^(MR|MRESET|PB_RST)$', re.I)
SUPPLY_PIN_RE = re.compile(r'^(VDD\w*|VCC\w*|AVDD\w*|AVCC\w*|DVDD\w*|VIN\d*|PVIN\d*|VBAT)$', re.I)
OUT_PINTYPES = {'OUT', 'OUTPUT', 'TRISTATE', '3STATE', 'BI', 'BIDI', 'BIDIR', 'IO', 'I/O'}
MAX_RAILS = 64

# Only physical roles confirmed by the manufacturer are model-specific.
# TI SNAS651A (Sep 2018), p4: DONE4 input, RST6 open-drain output.
# ESP32-C3-MINI-1 datasheet v2.2, Table 3-1/section 4.3: EN8 input/reset.
MODEL_WATCHDOG = 'TPL5010'
MODEL_RESET_RECEIVER = 'ESP32-C3-MINI-1-N4'
PIN_DIRECTIONS = {
    'input': {'IN', 'INPUT'},
    'bidirectional': {'BI', 'BIDI', 'BIDIR', 'BIDIRECTIONAL', 'IO', 'I/O'},
    'output': {'OUT', 'OUTPUT'},
    'open_collector': {'OCL', 'OPEN_COLLECTOR'},
    'open_emitter': {'OCA', 'OPEN_EMITTER'},
    'tri_state': {'TRISTATE', '3STATE', 'TRI_STATE'},
}


def _exact_model(part, model):
    """Placed part AND value must prove the MPN; prim only cross-checks it."""
    identities = {key: ng.normalize(part.get(key)) for key in ('part', 'value', 'prim')}
    pattern = r'(?:[^:\s]+:)?' + re.escape(ng.normalize(model))
    return (bool(identities['part'] and identities['value']) and all(
        re.fullmatch(pattern, value) for value in identities.values() if value))


def _pin_direction(graph, node):
    """Unknown or conflicting native/normalized/declaration semantics stay unknown."""
    if node in graph.db.get('no_connect_nodes', []):
        return None
    directions = set()
    for field in ('pintype', 'native_pintype', 'declared_pintype', 'declared_native_pintype'):
        if node not in graph.db.get(field, {}):
            continue
        value = ng.normalize(graph.db[field][node])
        direction = next((key for key, aliases in PIN_DIRECTIONS.items() if value in aliases), None)
        if direction is None:
            return None
        directions.add(direction)
    return next(iter(directions)) if len(directions) == 1 else None


def _physical_pin(graph, ref, pin, names, directions):
    node = ref + '.' + pin
    aliases = set(ng.pin_aliases(graph.pinname.get(node), pin))
    declared = graph.db.get('declared_pinname', {}).get(node)
    return (node in graph.pin2net and bool(aliases & names)
            and (declared is None or bool(set(ng.pin_aliases(declared, pin)) & names))
            and _pin_direction(graph, node) in directions)


RAIL_REQUIREMENT_FIELDS = {'net', 'state', 'required', 'criterion', 'citation', 'identity'}
# 可选：负载 IC 片内监测（UVLO/欠压/掉电检测）作为本轨的监控，须有出处；门限与动作仍另审。
NATIVE_NON_OUTPUTS = {'input', 'power_in', 'power_out', 'no_connect'}   # passive/unspecified libraries stay open
INTERNAL_MONITOR_FIELDS = {'node', 'function', 'citation'}
SOURCE_IDENTITY_FIELDS = {'source_node', 'source_role', 'part', 'pin_name', 'native_pintypes', 'citation'}
PART_IDENTITY_FIELDS = {'part', 'prim', 'value', 'jedec'}
SHUNT_FEED_FIELDS = {'upstream_node', 'upstream_part', 'upstream_pins', 'receiver_pins',
                     'feed', 'receiver_source', 'citation'}
FEED_FIELDS = {'ref', 'from_node', 'to_node', 'part', 'pins', 'resistance_ohm_exact'}
RECEIVER_SOURCE_FIELDS = {'path', 'sha256', 'format', 'publisher', 'source_url',
                         'document_model', 'document_version', 'role_page', 'pin_page',
                         'identity_quote', 'role_quote', 'pin_quote', 'citation'}


def _physical_snapshot(graph, ref):
    """Snapshot every observed physical node, including declaration-only nodes."""
    fields = ('pin2net', 'pinname', 'native_pintype', 'declared_native_pintype',
              'pintype', 'declared_pintype', 'declared_pinname')
    nodes = {n for field in fields for n in graph.db.get(field, {})
             if n.partition('.')[0] == ref}
    return {n: {**{field: graph.db.get(field, {}).get(n) for field in fields},
                'no_connect': n in graph.db.get('no_connect_nodes', [])}
            for n in sorted(nodes)}


def _snapshot_complete(graph, ref):
    snapshot = _physical_snapshot(graph, ref)
    return bool(snapshot) and all(
        node in graph.pin2net and node in graph.nodes_on(graph.pin2net[node])
        and data['pinname'] is not None and data['native_pintype'] is not None
        and data['declared_native_pintype'] == data['native_pintype']
        and data['declared_pinname'] == data['pinname']
        and data['declared_pintype'] == data['pintype']
        for node, data in snapshot.items())


def _shunt_upstream_contact(graph, node):
    """Only this role admits unused passive pads with actual isolated NC marks."""
    ref = node.partition('.')[0]
    if (not _snapshot_complete(graph, ref) or graph.kind(ref) not in (ng.CONNECTOR, ng.UNKNOWN)
            or graph.db['native_pintype'].get(node) != 'passive'
            or node in graph.db.get('no_connect_nodes', [])
            or ng.is_ground(graph.pin2net.get(node)) or graph.pin2net.get(node) in graph.pseudo):
        return False
    for pad, data in _physical_snapshot(graph, ref).items():
        net = data['pin2net']
        if data['native_pintype'] not in ('passive', 'no_connect'):
            return False
        expected = ('UNSPEC', 'UNSPECIFIED', 'PASSIVE') if data['native_pintype'] == 'passive' else ('NC',)
        if any(ng.normalize(data[field]) not in expected for field in ('pintype', 'declared_pintype')):
            return False
        if data['no_connect']:
            if (net not in graph.pseudo or graph.nodes_on(net) != [pad]
                    or ng.is_ground(net) or ng.is_rail(net)):
                return False
        elif data['native_pintype'] != 'passive' or net in graph.pseudo:
            return False
    return True


def _quote_key(text):
    return ''.join(c for c in unicodedata.normalize('NFKC', text).casefold() if c.isalnum())


def _identifier_in(identifier, text):
    """Literal identifier boundaries survive punctuation; 1 != 11, MPN != MPN-42."""
    identifier = unicodedata.normalize('NFKC', identifier).casefold()
    text = unicodedata.normalize('NFKC', text).casefold()
    return bool(identifier) and re.search(
        r'(?<![a-z0-9_.+\-])' + re.escape(identifier) + r'(?![a-z0-9_.+\-])', text) is not None


def _literal_identifier_bound(identifier, quote, page):
    """Exact token must occur at the actual literal quote location on the page.

    Keep an offset map when ignoring whitespace/punctuation: callers cannot cut
    '1' out of '11', or an MPN prefix out of an extended variant on the raw page.
    A correct token elsewhere on the page cannot rescue the wrong quoted span.
    """
    page = unicodedata.normalize('NFKC', page).casefold()
    identifier = unicodedata.normalize('NFKC', identifier).casefold()
    offsets = [i for i, c in enumerate(page) if c.isalnum()]
    normalized, literal = ''.join(page[i] for i in offsets), _quote_key(quote)
    if not identifier or not literal:
        return False
    tokens = list(re.finditer(r'(?<![a-z0-9_.+\-])' + re.escape(identifier)
                             + r'(?![a-z0-9_.+\-])', page))
    start = normalized.find(literal)
    while start >= 0:
        lo, hi = offsets[start], offsets[start + len(literal) - 1] + 1
        if any(lo <= token.start() and token.end() <= hi for token in tokens):
            return True
        start = normalized.find(literal, start + 1)
    return False


def _feed_edges(graph, omitted=()):
    """Conservative possible DC conduction, local to this strict provenance role.

    No voltage/current/drive guarantee, no equivalent-net links. Unknown switch
    control never proves off; MOS gates and IC signal pins are not conduction pairs.
    Connectors alone do not create an independently energized source.
    """
    edges = {}
    def edge(a, b, bidirectional=True):
        if a == b or any(n is None or ng.is_ground(n) or n in graph.pseudo for n in (a, b)):
            return
        edges.setdefault(a, set()).add(b)
        if bidirectional:
            edges.setdefault(b, set()).add(a)
    for ref in graph.parts:
        if ref in omitted or not graph.is_fitted(ref):
            continue
        kind = graph.kind(ref)
        nodes = [ref + '.' + p for p in graph.pins_of(ref)
                 if ref + '.' + p not in graph.db.get('no_connect_nodes', [])]
        if kind in (ng.MOSFET, ng.BJT):
            # All duplicate physical S/D (or E/C) pads participate; gate/base do not.
            left = [n for n in nodes if graph.role(n) == 'source']
            right = [n for n in nodes if graph.role(n) == 'drain']
            if left and right:
                for a in left:
                    for b in right:
                        edge(graph.pin2net[a], graph.pin2net[b])
            else:
                # An unresolved transistor mapping cannot establish isolation.
                contacts = [n for n in nodes if graph.role(n) != 'gate'
                            and graph.db.get('native_pintype', {}).get(n) == 'passive']
                for a in contacts:
                    for b in contacts:
                        edge(graph.pin2net[a], graph.pin2net[b])
        elif kind in (ng.SWITCH, ng.RELAY) or (kind == ng.UNKNOWN and len(nodes) > 2):
            # Unknown multi-terminal passive devices may conduct between contacts;
            # controls/coils are excluded. This is rejection coverage, not a model.
            contacts = [n for n in nodes if graph.role(n) != 'coil'
                        and graph.db.get('native_pintype', {}).get(n) == 'passive']
            for a in contacts:
                for b in contacts:
                    edge(graph.pin2net[a], graph.pin2net[b])
        elif kind == ng.DIODE:
            a, b = graph.node_named(ref, 'anode'), graph.node_named(ref, 'cathode')
            if a in nodes and b in nodes:
                edge(graph.pin2net[a], graph.pin2net[b], False)
            elif len(nodes) == 2:
                # Missing polarity is uncertainty, not evidence of reverse blocking.
                edge(graph.pin2net[nodes[0]], graph.pin2net[nodes[1]])
        elif len(nodes) == 2 and kind in (ng.RESISTOR, ng.INDUCTOR, ng.FERRITE,
                                         ng.FUSE, ng.JUMPER, ng.UNKNOWN):
            edge(graph.pin2net[nodes[0]], graph.pin2net[nodes[1]])
    return edges


def _feed_reaches(edges, start, target):
    pending, visited = [start], set()
    while pending:
        current = pending.pop()
        if current == target:
            return True
        if current not in visited:
            visited.add(current)
            pending.extend(edges.get(current, set()) - visited)
    return False


def _feed_resistance(value):
    """Keep native text intact; allow one explicit trailing watt rating as metadata."""
    parsed = parse_resistor(value, exact=True)
    if parsed is None and isinstance(value, str):
        match = re.fullmatch(r'(.+?)\s+\d+(?:\.\d+)?(?:mW|W)', value)
        if match:
            parsed = parse_resistor(match[1], exact=True)
    return parsed


@lru_cache(maxsize=64)
def _source_page(raw, fmt, page):
    """Cache by actual bytes, never timestamp; no writes or network acquisition."""
    if fmt == 'text':
        return raw.decode('utf-8') if page == 1 and not raw.startswith(b'%PDF') else ''
    if fmt != 'pdf' or not raw.startswith(b'%PDF'):
        return ''
    texts = pdf_page_texts(raw, page)
    return texts[1] if texts else ''


def _receiver_source_errors(source, graph, node):
    """Bind literal OEM evidence; meaning/applicability remain expert obligations."""
    if not isinstance(source, dict) or set(source) != RECEIVER_SOURCE_FIELDS:
        return ['internal shunt receiver source fields missing/unsupported']
    errors = []
    texts = RECEIVER_SOURCE_FIELDS - {'role_page', 'pin_page'}
    if not all(state_lib._text(source.get(k)) for k in texts):
        return ['internal shunt receiver source metadata/quotes/citation missing']
    if (source['format'] not in ('pdf', 'text')
            or any(type(source.get(k)) is not int or source[k] < 1
                   for k in ('role_page', 'pin_page'))):
        return ['internal shunt receiver source format/page invalid']
    try:
        path = Path(source['path'])
        if not path.is_absolute() or not path.is_file() or path.stat().st_size > 10 * 1024 * 1024:
            return ['internal shunt receiver source file unavailable/nonabsolute/too large']
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != source['sha256']:
            return ['internal shunt receiver source hash mismatch']
        role_page = _source_page(raw, source['format'], source['role_page'])
        pin_page = _source_page(raw, source['format'], source['pin_page'])
        role_text, pin_text = _quote_key(role_page), _quote_key(pin_page)
    except (OSError, UnicodeError, subprocess.SubprocessError):
        return ['internal shunt receiver source unreadable']
    ref, _, pin = node.partition('.')
    mpn = ng.normalize(graph.parts[ref].get('part', '')).rsplit(':', 1)[-1]
    name = graph.pinname.get(node, '')
    identity_quote, role_quote, pin_quote = (
        _quote_key(source[k]) for k in ('identity_quote', 'role_quote', 'pin_quote'))
    if (not _identifier_in(mpn, source['identity_quote'])
            or not _literal_identifier_bound(mpn, source['identity_quote'], role_page)):
        errors.append('internal shunt receiver identity quote does not match source/actual MPN')
    if (not _identifier_in(name, source['role_quote'])
            or not _literal_identifier_bound(name, source['role_quote'], role_page)
            or not any(word in role_quote for word in ('shunt', '并联稳压'))):
        errors.append('internal shunt receiver role quote does not match source/pin/shunt role')
    if (not _identifier_in(pin, source['pin_quote']) or not _identifier_in(name, source['pin_quote'])
            or not _literal_identifier_bound(pin, source['pin_quote'], pin_page)
            or not _literal_identifier_bound(name, source['pin_quote'], pin_page)):
        errors.append('internal shunt receiver physical pin quote does not match source')
    return errors


def _internal_shunt_feed(scan, item, intent):
    """Finite resistive feed provenance only; never a PowerTree link or ideal driver."""
    graph = scan.graph
    identity = item['identity']
    receiver, net = identity['source_node'], item['net']
    proof = identity.get('feed_provenance')
    if not isinstance(proof, dict) or set(proof) != SHUNT_FEED_FIELDS:
        return ['internal shunt feed provenance fields missing/unsupported'], None
    if not state_lib._text(proof.get('citation')):
        return ['internal shunt feed provenance citation missing'], None
    source, feed = proof.get('upstream_node'), proof.get('feed')
    if not isinstance(source, str) or not isinstance(feed, dict) or set(feed) != FEED_FIELDS:
        return ['internal shunt upstream/feed declaration malformed'], None
    if not all(state_lib._text(feed.get(k)) for k in ('ref', 'from_node', 'to_node', 'resistance_ohm_exact')):
        return ['internal shunt feed physical nodes/resistance missing'], None
    errors = []
    upstream_ref, receiver_ref = source.partition('.')[0], receiver.partition('.')[0]
    feed_ref = feed['ref']
    if not all(ref in graph.parts and graph.is_fitted(ref)
               for ref in (upstream_ref, receiver_ref, feed_ref)):
        return ['internal shunt source/receiver/feed absent or DNP'], None
    receiver_part = graph.parts[receiver_ref]
    receiver_model = ng.normalize(receiver_part.get('part', '')).rsplit(':', 1)[-1]
    if not _exact_model(receiver_part, receiver_model):
        errors.append('internal shunt receiver part/value/symbol identity conflict')
    expected_part = {k: graph.parts[upstream_ref].get(k, '') for k in PART_IDENTITY_FIELDS}
    if proof['upstream_part'] != expected_part:
        errors.append('internal shunt upstream part identity mismatch')
    if (proof['upstream_pins'] != _physical_snapshot(graph, upstream_ref)
            or not _snapshot_complete(graph, upstream_ref)
            or not _shunt_upstream_contact(graph, source)):
        errors.append('internal shunt upstream physical pin/NC/contact qualification mismatch')
    if (proof['receiver_pins'] != _physical_snapshot(graph, receiver_ref)
            or not _snapshot_complete(graph, receiver_ref)
            or graph.db.get('native_pintype', {}).get(receiver) != 'power_in'
            or any(ng.normalize(graph.db.get(field, {}).get(receiver)) not in ('POWER', 'PWR', 'POWER_IN', 'POWER_INPUT')
                   for field in ('pintype', 'declared_pintype'))
            or receiver in graph.db.get('no_connect_nodes', [])
            or graph.pin2net.get(receiver) != net or net in graph.pseudo or ng.is_ground(net)):
        errors.append('internal shunt receiver is not the actual complete power_in rail pin')
    expected_feed_part = {k: graph.parts[feed_ref].get(k, '') for k in PART_IDENTITY_FIELDS}
    if (feed['part'] != expected_feed_part or feed['pins'] != _physical_snapshot(graph, feed_ref)
            or not _snapshot_complete(graph, feed_ref) or not _native_contacts(graph, feed_ref)
            or graph.kind(feed_ref) != ng.RESISTOR):
        errors.append('internal shunt feed is not the actual complete passive resistor')
    try:
        resistance = _feed_resistance(graph.parts[feed_ref].get('value'))
        exact = Fraction(resistance['ohm_exact']) if resistance else None
        if (exact is None or exact <= 0 or resistance.get('kohm', 0) <= 0
                or feed['resistance_ohm_exact'] != str(exact)):
            errors.append('internal shunt feed resistance is not exact finite positive nonzero')
    except (ValueError, OverflowError, TypeError, KeyError, ZeroDivisionError):
        errors.append('internal shunt feed resistance is not exact finite positive nonzero')
    start, end = feed['from_node'], feed['to_node']
    upstream_net = graph.pin2net.get(source)
    if (start.partition('.')[0] != feed_ref or end.partition('.')[0] != feed_ref
            or start == end or set((start, end)) != set(_physical_snapshot(graph, feed_ref))
            or graph.pin2net.get(start) != upstream_net or graph.pin2net.get(end) != net
            or upstream_net == net or upstream_net in graph.pseudo or ng.is_ground(upstream_net)):
        errors.append('internal shunt feed is not a single direct upstream-to-receiver path')
    declarations = intent.get('power_sources', [])
    if not isinstance(declarations, list) or any(
            not isinstance(x, dict) or not state_lib._text(x.get('node'))
            or not state_lib._text(x.get('citation')) or not isinstance(x.get('states'), list)
            or not x['states'] or not all(state_lib._text(s) for s in x['states'])
            or x['node'] not in graph.pin2net for x in declarations):
        return ['internal shunt upstream state/source declarations malformed'], None
    active_sources = [x for x in declarations if scan.state['id'] in x['states']
                      and graph.is_fitted(x['node'].partition('.')[0])]
    if not any(x.get('node') == source and state_lib._text(x.get('citation')) for x in active_sources):
        errors.append('internal shunt upstream source is not declared in this state')
    edges = _feed_edges(graph)
    if any(_feed_reaches(edges, graph.pin2net[x['node']], net)
           and (x['node'].partition('.')[0] != upstream_ref
                or graph.pin2net[x['node']] != upstream_net) for x in active_sources):
        errors.append('internal shunt feed has another independently declared source')
    # A connector without an external-source state declaration can be a load port;
    # physical contacts alone do not prove an independently energized source.
    if any(graph.is_fitted(n.partition('.')[0])
           and n not in graph.db.get('no_connect_nodes', [])
           and t in ('power_out', 'output') and _feed_reaches(edges, graph.pin2net.get(n), net)
           for n, t in graph.db.get('native_pintype', {}).items()) or scan.tree.source_of(net) is not None:
        errors.append('internal shunt receiver rail has another supported source')
    # A second fitted DC passive supply path, including a serial bypass, cannot be
    # silently omitted. Ground and capacitors are not alternative DC supply paths.
    if _feed_reaches(_feed_edges(graph, (feed_ref,)), upstream_net, net):
        errors.append('internal shunt feed has an additional parallel/serial/bypass path; unknown control is not off')
    errors.extend(_receiver_source_errors(proof['receiver_source'], graph, receiver))
    if errors:
        return errors, None
    path = {'ref': feed_ref, 'from_node': start, 'from_net': upstream_net,
            'to_node': end, 'to_net': net, 'resistance_ohm_exact': feed['resistance_ohm_exact'],
            'native_value': graph.parts[feed_ref].get('value'),
            'receiver_node': receiver, 'receiver_native_type': 'power_in',
            'receiver_source_sha256': proof['receiver_source'].get('sha256'),
            'source_role': 'internal_shunt_feed', 'electrical_equivalence': False,
            'performance_guarantee': False}
    return [], [path]


def _section_errors(intent, db):
    # The shared schema stays v2; the optional per-rail array belongs to this checker.
    source = intent
    if isinstance(intent, dict) and isinstance(intent.get('supervision'), dict):
        source = dict(intent, supervision={k: v for k, v in intent['supervision'].items()
                                          if k != 'rail_requirements'})
    return state_lib.section_errors(
        source, db, 'supervision', item_field='supervisors', item_key='supervisor',
        fields=('id', 'ref', 'monitored_nets', 'citation'))


def _native_contacts(graph, ref, *, allow_nc=False):
    """Full native/declaration agreement; NC is never a supply contact."""
    db = graph.db
    observed = {n for field in ('pin2net', 'pinname', 'pintype', 'declared_pinname',
                                'declared_pintype', 'native_pintype', 'declared_native_pintype')
                for n in db.get(field, {}) if n.partition('.')[0] == ref}
    native = {n: t for n, t in db.get('native_pintype', {}).items() if n.partition('.')[0] == ref}
    declared = {n: t for n, t in db.get('declared_native_pintype', {}).items()
                if n.partition('.')[0] == ref}
    if not observed or set(native) != observed:
        return False
    if 'declared_native_pintype' in db and declared != native:
        return False
    for node, pintype in native.items():
        net = graph.pin2net.get(node)
        if net is None or node not in graph.nodes_on(net):
            return False
        if node in db.get('declared_pinname', {}) and db['declared_pinname'][node] != graph.pinname.get(node):
            return False
        if pintype == 'passive':
            if (node in db.get('no_connect_nodes', []) or net in graph.pseudo
                    or any(ng.normalize(db.get(field, {}).get(node)) not in ('UNSPEC', 'UNSPECIFIED', 'PASSIVE')
                           for field in ('pintype', 'declared_pintype') if node in db.get(field, {}))):
                return False
        elif (not allow_nc or pintype != 'no_connect' or declared.get(node) != 'no_connect'
              or node not in db.get('no_connect_nodes', []) or net not in graph.pseudo
              or ng.is_ground(net) or ng.is_rail(net)
              or graph.nodes_on(net) != [node]
              or any(ng.normalize(db.get(field, {}).get(node)) != 'NC'
                     for field in ('pintype', 'declared_pintype') if node in db.get(field, {}))):
            return False
    return True


def _external_source_qualified(graph, node):
    ref = node.partition('.')[0]
    net = graph.pin2net.get(node)
    # A connector may have isolated mechanical NC pads, but the selected supply
    # node itself must be a real native passive contact, never a load/output/NC.
    return (graph.db.get('native_pintype', {}).get(node) == 'passive'
            and node not in graph.db.get('no_connect_nodes', [])
            and net is not None and not ng.is_ground(net) and net not in graph.pseudo
            and node in graph.nodes_on(net) and _native_contacts(graph, ref, allow_nc=True)
            and (graph.qualified_connector_contact(ref)
                 or graph.kind(ref) in (ng.CONNECTOR, ng.UNKNOWN)))


def _upstream_external_path(scan, node, net, citation):
    """Use PowerTree for discovery, then constrain its path to actual passive links."""
    graph = scan.graph
    state_id = scan.state['id']
    tree = powertree.PowerTree(graph, {'active_state': state_id, 'power_sources': [
        {'node': node, 'states': [state_id], 'citation': citation}]})
    found = tree.source_of(net)
    if (not found or found['source'] != node or not found['path']
            or not _external_source_qualified(graph, node)):
        return None
    current, path = graph.pin2net[node], []
    for ref in found['path']:
        ends = graph.nets_of(ref)
        nodes = [ref + '.' + pin for pin in graph.pins_of(ref)]
        kind = graph.kind(ref)
        if (not graph.is_fitted(ref) or len(ends) != 2 or current not in ends
                or len(nodes) != 2 or not _native_contacts(graph, ref)
                or kind not in (ng.DIODE, ng.RESISTOR, ng.INDUCTOR, ng.FERRITE, ng.FUSE)):
            return None
        other = ends[0] if ends[1] == current else ends[1]
        if any(ng.is_ground(n) or n in graph.pseudo for n in (current, other)):
            return None
        if kind == ng.RESISTOR:
            try:
                resistance = parse_resistor(graph.parts[ref].get('value'), exact=True)
            except (ValueError, OverflowError):
                return None
            if resistance is None or resistance.get('ohm_exact') != '0':
                return None
        if kind == ng.DIODE:
            anode, cathode = graph.node_named(ref, 'anode'), graph.node_named(ref, 'cathode')
            if (ng.kind_gap(graph, ref) or not anode or not cathode
                    or graph.pin2net.get(anode) != current or graph.pin2net.get(cathode) != other):
                return None
        start = next((n for n in nodes if graph.pin2net[n] == current), None)
        end = next((n for n in nodes if graph.pin2net[n] == other), None)
        if not start or not end or start not in graph.nodes_on(current) or end not in graph.nodes_on(other):
            return None
        path.append({'ref': ref, 'from_node': start, 'from_net': current,
                     'to_node': end, 'to_net': other})
        current = other
    return path if current == net else None


def _requirement_errors(item, db, intent, state=None, scan=None, rails=()):
    errors = []

    def require(ok, message):
        if not ok:
            errors.append(message)

    if not isinstance(item, dict):
        return ['rail requirement must be an object']
    monitor = item.get('internal_monitor')
    # A rail its own load monitors (cited UVLO on that load's supply pin) needs no
    # source identity: source followers, self-supply and series-R feeds stay expressible.
    self_monitored = 'identity' not in item and 'internal_monitor' in item
    require(set(item) - {'internal_monitor'} == RAIL_REQUIREMENT_FIELDS - ({'identity'} if self_monitored else set()),
            'rail requirement needs exact net/state/required/criterion/citation/identity')
    if 'internal_monitor' in item:
        require(isinstance(monitor, dict) and set(monitor) == INTERNAL_MONITOR_FIELDS
                and all(state_lib._text(monitor.get(k)) for k in INTERNAL_MONITOR_FIELDS),
                'internal_monitor needs node/function/citation')
    for key in ('net', 'state', 'criterion', 'citation'):
        require(state_lib._text(item.get(key)), 'rail requirement needs ' + key)
    require(type(item.get('required')) is bool, 'rail requirement required must be boolean (unknown remains undeclared)')
    identity = item.get('identity')
    if self_monitored:
        return errors + _self_monitor_errors(item, db, intent, state, scan, rails)
    if not isinstance(identity, dict):
        return errors + ['rail requirement needs source identity']
    shunt = identity.get('source_role') == 'internal_shunt_feed'
    require(set(identity) == SOURCE_IDENTITY_FIELDS | ({'feed_provenance'} if shunt else set()),
            'source identity has missing/unsupported fields')
    for key in ('source_node', 'source_role', 'pin_name', 'citation'):
        require(state_lib._text(identity.get(key)), 'source identity needs ' + key)
    require(identity.get('source_role') in ('external_supply', 'upstream_external_supply', 'rail_driver',
                                           'internal_shunt_feed'), 'unknown source role')
    part = identity.get('part')
    require(isinstance(part, dict) and set(part) == PART_IDENTITY_FIELDS
            and all(isinstance(v, str) for v in part.values()) and state_lib._text(part.get('part')),
            'source identity needs full part/prim/value/jedec snapshot')
    require(isinstance(identity.get('native_pintypes'), dict), 'source identity needs native_pintypes snapshot')
    if db is None or errors:
        return errors
    require(intent.get('input_sha256') == board_intent.input_fingerprint(db), 'stale/missing input_sha256')
    require(state is not None and state.get('declared') and state_lib._text(state.get('citation')),
            'unknown/unverified assembly state')
    if scan is None:
        return errors
    graph = scan.graph
    net, node = item.get('net'), identity.get('source_node')
    require(net in {rail['net'] for rail in rails}, 'net is not an actual supply rail')
    if not isinstance(node, str):
        return errors
    ref = node.partition('.')[0]
    actual_part = {k: db.get('parts', {}).get(ref, {}).get(k, '') for k in PART_IDENTITY_FIELDS}
    require(ref in graph.parts and graph.is_fitted(ref), 'source is absent/DNP in this assembly')
    if identity.get('source_role') != 'upstream_external_supply':
        require(graph.pin2net.get(node) == net and node in graph.nodes_on(net), 'source node does not belong to actual net')
    require(part == actual_part, 'source part identity differs from native input')
    require(identity.get('pin_name') == graph.pinname.get(node), 'source pin name differs from native input')
    actual_types = {n: t for n, t in db.get('native_pintype', {}).items() if n.partition('.')[0] == ref}
    require(identity.get('native_pintypes') == actual_types, 'source native type snapshot differs from input')
    if identity.get('source_role') == 'rail_driver':
        source = scan.tree.source_of(net)
        require(source is not None and source['source'] == node, 'source is not the actual PowerTree driver')
        # Where native semantics are available, a load/input cannot be promoted to a driver.
        require(not actual_types or actual_types.get(node) in ('power_out', 'output', 'bidirectional', 'tri_state'),
                'native source pin is not an output')
    elif identity.get('source_role') in ('external_supply', 'upstream_external_supply'):
        require(_external_source_qualified(graph, node),
                'external source lacks complete native passive contacts with isolated, declaration-matched NC pads')
        if identity.get('source_role') == 'upstream_external_supply':
            require(_upstream_external_path(scan, node, net, identity['citation']) is not None,
                    'upstream external source lacks a nonempty fitted forward passive supply path')
    elif shunt:
        feed_errors, _ = _internal_shunt_feed(scan, item, intent)
        errors.extend(feed_errors)
    if isinstance(monitor, dict) and isinstance(monitor.get('node'), str):
        mref = monitor['node'].partition('.')[0]
        require(graph.pin2net.get(monitor['node']) == net and graph.is_fitted(mref)
                and graph.kind(mref) == ng.IC,
                'internal_monitor node must be a fitted IC pin on this rail')
    return errors


def _self_monitor_errors(item, db, intent, state, scan, rails):
    """Requirement without source identity: the monitor must sit on a load supply pin of the rail."""
    if db is None:
        return []
    errors = []
    if intent.get('input_sha256') != board_intent.input_fingerprint(db):
        errors.append('stale/missing input_sha256')
    if not (state is not None and state.get('declared') and state_lib._text(state.get('citation'))):
        errors.append('unknown/unverified assembly state')
    if scan is None or errors:
        return errors
    graph, net, node = scan.graph, item.get('net'), item['internal_monitor'].get('node')
    rail = next((r for r in rails if r['net'] == net), None)
    if rail is None:
        return ['net is not an actual supply rail']
    ref = node.partition('.')[0] if isinstance(node, str) else None
    if not (ref in rail['loads'] and graph.pin2net.get(node) == net and graph.is_fitted(ref)
            and SUPPLY_PIN_RE.match(ng.normalize(graph.pinname.get(node)) or '')):
        errors.append('internal_monitor without identity must be a fitted load supply pin on this rail')
    return errors


def validate_supervision_intent(intent, db=None):
    """校验可选的 supervision 配置与精确绑定的逐轨×装配状态书面范围。"""
    errors = _section_errors(intent, db)
    cfg = (intent or {}).get('supervision') if isinstance(intent, dict) else None
    if not isinstance(cfg, dict) or 'rail_requirements' not in cfg:
        return errors
    items = cfg['rail_requirements']
    if not isinstance(items, list):
        return errors + ['supervision: rail_requirements must be an array']
    states = {s['id']: s for s in state_lib.resolve(db, intent.get('assemblies'))} if db is not None else {}
    seen = set()
    for item in items:
        state = states.get(item.get('state')) if isinstance(item, dict) and isinstance(item.get('state'), str) else None
        scan = _Scan(board_intent.graph_db(db, intent), state, set(), set()) if state else None
        rails = scan.rails(scan.supervisors()) if scan else []
        errors.extend('supervision: ' + error for error in _requirement_errors(item, db, intent, state, scan, rails))
        if isinstance(item, dict) and isinstance(item.get('state'), str) and isinstance(item.get('net'), str):
            key = (item['state'], item['net'])
            if key in seen:
                errors.append('supervision: duplicate rail requirement for ' + str(key))
            seen.add(key)
    return errors


class _Scan:
    def __init__(self, db, state, declared, excluded):
        self.graph = ng.NetGraph(db, fitted=set(state['fitted']))
        self.state = state
        self.declared = declared
        self.excluded = excluded
        self.grounds = {net for net in self.graph.nets if ng.is_ground(net)}
        self.tree = powertree.PowerTree(self.graph)

    def _reset_destinations(self, net, source_ref):
        found = []
        for node in self.graph.nodes_on(net):
            ref = node.partition('.')[0]
            if ref == source_ref or not self.graph.is_fitted(ref):
                continue
            kind = self.graph.kind(ref)
            pin = node.partition('.')[2]
            named_reset = ng.name_matches(RESET_IN_RE, self.graph.pinname.get(node), pin)
            model_reset = (_exact_model(self.graph.parts[ref], MODEL_RESET_RECEIVER)
                           and _physical_pin(self.graph, ref, '8', {'EN'}, {'input'})
                           and pin == '8')
            if (kind == ng.IC and _pin_direction(self.graph, node) in ('input', 'bidirectional')
                    and (named_reset or model_reset)):
                found.append({'node': node, 'role': 'reset-input'})
            elif kind == ng.IC:
                found.append({'node': node, 'role': 'other-pin'})
            elif kind == ng.CONNECTOR:
                found.append({'node': node, 'role': 'external'})
        return sorted(found, key=lambda item: item['node'])

    def _watchdog_input(self, net, source_ref):
        drivers = []
        for node in self.graph.nodes_on(net):
            ref = node.partition('.')[0]
            if ref == source_ref or not self.graph.is_fitted(ref):
                continue
            if self.graph.kind(ref) in (ng.IC, ng.CONNECTOR):
                drivers.append(node)
        if ng.is_rail(net) or net in self.grounds:
            state = 'tied'          # 直接坐在电源/地上，喂狗不可能翻转
        elif drivers:
            state = 'driven'
        elif any(ng.is_rail(other) or other in self.grounds
                 for _, other in self.graph.neighbors(net, {ng.RESISTOR})):
            state = 'pulled-only'
        else:
            state = 'floating'
        return {'net': net, 'state': state, 'drivers': sorted(drivers)}

    def supervisors(self):
        graph, found = self.graph, []
        for ref in sorted(graph.parts):
            if ref in self.excluded or not graph.is_fitted(ref) or graph.kind(ref) != ng.IC:
                continue
            watchdogs = self.graph.named_pins(ref, WATCHDOG_IN_RE)
            senses = self.graph.named_pins(ref, SENSE_RE)
            manual = self.graph.named_pins(ref, MANUAL_RESET_RE)
            native = graph.db.get('native_pintype') or {}
            # A library pin typed input/power is a reset INPUT (e.g. an LED driver's RESET), never a
            # supervisor output, whatever SENSE/MR pins the part also has.
            outputs = {node: net for node, net in self.graph.named_pins(ref, RESET_OUT_RE).items()
                       if native.get(node) not in NATIVE_NON_OUTPUTS
                       and (ng.normalize(graph.pintype.get(node)) in OUT_PINTYPES
                            or ng.normalize(graph.pinname.get(node)) in {'WDO', 'PFO'}
                            or watchdogs or senses or manual)}
            if (_exact_model(graph.parts[ref], MODEL_WATCHDOG)
                    and _physical_pin(graph, ref, '4', {'DONE'}, {'input'})
                    and _physical_pin(graph, ref, '6', {'RST', 'RSTN'}, {'open_collector', 'output'})):
                watchdogs[ref + '.4'] = graph.pin2net[ref + '.4']
                outputs[ref + '.6'] = graph.pin2net[ref + '.6']
            if not (watchdogs or senses or manual) or not outputs:
                continue
            supplies = sorted(set(self.graph.named_pins(ref, SUPPLY_PIN_RE).values()))
            found.append({
                'id': slug(ref),
                'ref': ref,
                'basis': 'declared' if ref in self.declared else 'topology',
                'watchdog_inputs': [self._watchdog_input(net, ref)
                                    for net in sorted(set(watchdogs.values()))],
                'monitored_nets': sorted(set(senses.values())),
                'supply_nets': supplies,
                'reset_outputs': [
                    {'node': node, 'net': net,
                     'destinations': self._reset_destinations(net, ref),
                     'pulls': sorted({other for _, other in graph.neighbors(net, {ng.RESISTOR})
                                      if self.tree.is_rail(other)})}
                    for node, net in sorted(outputs.items())],
                'gaps': sorted(set(self.state['gaps'])),
            })
        return sorted(found, key=lambda item: item['id'])

    def rails(self, supervisors):
        """给 IC 供电的电源轨及其监测覆盖；哪些必须监测由需求裁定。"""
        graph = self.graph
        sensed = {net for item in supervisors for net in item['monitored_nets']}
        supplied = {net for item in supervisors for net in item['supply_nets']}
        found = []
        for net in sorted(graph.nets):
            basis = self.tree.rail_basis(net)
            if basis is None:
                continue
            loads = [node for node in graph.nodes_on(net)
                     if graph.kind(node.partition('.')[0]) == ng.IC
                     and SUPPLY_PIN_RE.match(ng.normalize(graph.pinname.get(node)) or '')]
            if not loads:
                continue
            divided = [other for _, other in graph.neighbors(net, {ng.RESISTOR})
                       if other in sensed]
            monitor = ('sense-pin' if net in sensed else
                       'divider' if divided else
                       'supervisor-supply' if net in supplied else None)
            found.append({'net': net, 'basis': basis, 'monitor': monitor,
                          'loads': sorted({node.partition('.')[0] for node in loads}),
                          'gaps': ([] if basis != powertree.NAME_HINT
                                   else ['rail-identity:' + net])})
        return found[:MAX_RAILS]


def build_inventory(db, intent=None):
    """生成逐状态的监控清单。"""
    cfg = (intent or {}).get('supervision') if isinstance(intent, dict) else None
    declared = state_lib.declared_refs(cfg, 'supervisors')
    excluded = state_lib.excluded_refs(cfg)
    gaps = [] if cfg else ['intent.supervision: 未声明必须监测的电源域与喂狗策略']
    scans = {}
    source = intent if isinstance(intent, dict) else {}
    requirement_mode = isinstance(cfg, dict) and 'rail_requirements' in cfg
    graph_db = board_intent.graph_db(db, source) if requirement_mode else db
    items = cfg.get('rail_requirements', []) if requirement_mode else []
    items = items if isinstance(items, list) else []
    section_valid = not _section_errors(intent, db)

    def scanner(state):
        scan = scans.setdefault(state['id'], _Scan(graph_db, state, declared, excluded))
        return scan.supervisors()

    def extra(state):
        scan = scans.setdefault(state['id'], _Scan(graph_db, state, declared, excluded))
        rails = scan.rails(scan.supervisors())
        if requirement_mode:
            for rail in rails:
                rail['observation_gaps'] = sorted(rail['gaps'] + (
                    ['rail-unmonitored:' + rail['net']] if not rail['monitor'] else []))
                matches = [item for item in items if isinstance(item, dict)
                           and item.get('state') == state['id'] and item.get('net') == rail['net']]
                valid = (section_valid and len(matches) == 1
                         and not _requirement_errors(matches[0], db, source, state, scan, rails))
                rail['scope_qualified'] = bool(valid)
                rail['requirement'] = matches[0] if valid else None
                if valid and 'identity' not in matches[0]:
                    monitor = matches[0]['internal_monitor']
                    rail['monitor'] = rail['monitor'] or 'internal:' + monitor['node']
                    rail['internal_monitor'] = monitor
                    rail['observation_gaps'] = [g for g in rail['observation_gaps']
                                                if g != 'rail-unmonitored:' + rail['net']]
                    rail['source_path'] = []
                    rail['gaps'] = [gap for gap in rail['gaps'] if gap != 'rail-identity:' + rail['net']]
                elif valid:
                    identity = matches[0]['identity']
                    if matches[0].get('internal_monitor') and not rail['monitor']:
                        rail['monitor'] = 'internal:' + matches[0]['internal_monitor']['node']
                        rail['internal_monitor'] = matches[0]['internal_monitor']
                        rail['observation_gaps'] = [g for g in rail['observation_gaps']
                                                    if g != 'rail-unmonitored:' + rail['net']]
                    rail['source_path'] = (_upstream_external_path(
                        scan, identity['source_node'], rail['net'], identity['citation'])
                        if identity['source_role'] == 'upstream_external_supply'
                        else _internal_shunt_feed(scan, matches[0], source)[1]
                        if identity['source_role'] == 'internal_shunt_feed' else [])
                    rail['gaps'] = [gap for gap in rail['gaps'] if gap != 'rail-identity:' + rail['net']]
                else:
                    rail['gaps'] = sorted(set(rail['gaps'] + ['rail-requirement:' + rail['net']]))
            return {'rails': rails, 'rail_requirements_declared': True}
        return {'rails': rails}

    result = inv.build(db, intent, 'supervision', 'supervisors', scanner, gaps, extra=extra)
    if any(isinstance(item, dict) and isinstance(item.get('identity'), dict)
           and item['identity'].get('source_role') == 'internal_shunt_feed' for item in items):
        # This new role consumes upstream state declarations; preserve them for
        # deterministic validation/rebuild without changing legacy contexts.
        result['context']['power_sources'] = copy.deepcopy(source.get('power_sources', []))
        result.pop('digest')
        result['digest'] = inv.digest(result)
    return result


class SupervisionChecker(Checker):
    id = 'supervision'
    title = '监控与看门狗'
    plan_key = 'supervision'
    version_key = 'supervision_version'
    version = 1
    intent_key = 'supervision'
    cold_rules = catalog.titles(stage='cold', source='supervision')
    e_rules = catalog.titles(method='E', source='supervision')

    missing_inventory_message = 'supervision checks require their inventory'
    inventory_type_message = 'supervision inventory must be an object'
    requires_db_message = 'supervision inventory validation requires --db'
    stale_message = 'supervision inventory/binding is stale or modified'
    invalid_message = 'invalid supervision inventory: '

    def incomplete_message(self, key):
        return key + ': incomplete supervision planned coverage'

    def changed_message(self, key):
        return key + ': supervision generated criterion/object changed'

    def validate_intent(self, intent, db):
        return validate_supervision_intent(intent, db)

    def build(self, db, intent):
        return build_inventory(db, intent)

    def plan(self, planner, inventory):
        for state, item in inv.walk(inventory, 'supervisors'):
            obj = {'ref': item['ref'], 'state': state['id'], 'supervision': item['id'],
                   'supervision_digest': inventory['digest']}
            if item['reset_outputs']:
                obj['net'] = item['reset_outputs'][0]['net']
            gaps = item['gaps']
            check = planner.add_check(
                'RST-T02', dict(obj), key=item['id'], readiness='WAITING_EVIDENCE',
                required_inputs=sorted(set(gaps + [
                    'datasheet:监控器阈值/脉宽/输出类型', 'firmware:启动期喂狗与超时窗口'])),
                trigger=['supervision:' + item['id']])
            check['inventory_gaps'] = gaps
            check = planner.add_check(
                'RST-E03', dict(obj), key=item['id'],
                readiness='WAITING_EVIDENCE',
                required_inputs=sorted(set(gaps + [
                    'datasheet: RST-E03 复位脉宽保证值与目标器件要求'])),
                trigger=['supervision:' + item['id']])
            check['inventory_gaps'] = gaps
        for state in inventory['states']:
            rails = state.get('rails', [])
            if not rails:
                continue
            obj = {'feature': 'supervision-rails', 'state': state['id'],
                   'supervision': 'rails-' + slug(state['id']),
                   'supervision_digest': inventory['digest']}
            check = planner.add_check(
                'PWR-T04', obj, key=slug(state['id']), readiness='WAITING_EVIDENCE',
                required_inputs=sorted(set(list(state['gaps']) + [
                    'requirements:必须监测的电源域与动作要求',
                    'intent:supervision.rail_requirements 逐轨声明 required=false 或 internal_monitor（片内 UVLO/复位，附出处）'])),
                trigger=['supervision-rails:' + state['id']],)
            check['inventory_gaps'] = sorted(
                {'rail-unmonitored:' + rail['net'] for rail in rails if not rail['monitor']
                 and not (rail.get('scope_qualified') and rail['requirement']['required'] is False)}
                | {gap for rail in rails for gap in rail['gaps']}
                | (set(state['gaps']) if state.get('rail_requirements_declared') else set()))

    def cold_findings(self, lint, inventory):
        for state in inventory['states']:
            for item in state['supervisors']:
                head = '%s（状态 %s）' % (item['ref'], state['id'])
                for watchdog in item['watchdog_inputs']:
                    if watchdog['state'] in ('floating', 'tied'):
                        lint.add('RST-A05', self.cold_rules['RST-A05'],
                                 head + '：喂狗输入网 ' + watchdog['net'] + ' 为 '
                                 + watchdog['state'] + '，看门狗可能被有意禁用，需书面确认',
                                 item['ref'], kind='CANDIDATE')
                for output in item['reset_outputs']:
                    targets = [x for x in output['destinations'] if x['role'] == 'reset-input']
                    if targets:
                        continue
                    detail = (head + '：复位/看门狗输出 ' + output['node'] + ' 所在网 '
                              + output['net'] + ' 未接到任何复位输入')
                    if output['destinations']:
                        lint.add('RST-A06', self.cold_rules['RST-A06'],
                                 detail + '（仅接到 '
                                 + '、'.join(x['node'] for x in output['destinations'])
                                 + '），需确认由该路径完成复位', item['ref'], kind='CANDIDATE')
                    else:
                        lint.add('RST-A06', self.cold_rules['RST-A06'],
                                 detail + '，复位链在此中断', item['ref'])
            if not state['supervisors']:
                continue
            unmonitored = [rail['net'] for rail in state.get('rails', []) if not rail['monitor']]
            if unmonitored:
                lint.add('PWR-A06', self.cold_rules['PWR-A06'],
                         '状态 %s：%s 未见监测点（sense 脚或到 sense 的分压）；'
                         '哪些轨必须监测由需求裁定'
                         % (state['id'], '、'.join(unmonitored)), kind='CANDIDATE')

    def rule_instances(self, rule, inventory):
        if rule == 'PWR-A06':
            return sorted({rail['net'] for state in inventory['states']
                           for rail in state.get('rails', []) if not rail['monitor']})
        return sorted({item['id'] for _, item in inv.walk(inventory, 'supervisors')})

    def binds(self, item):
        obj = item.get('object')
        return isinstance(obj, dict) and bool(obj.get('supervision'))

    def object_errors(self, key, obj, inventory):
        known = {item['id'] for _, item in inv.walk(inventory, 'supervisors')}
        known |= {'rails-' + slug(state['id']) for state in inventory['states']}
        if (obj.get('supervision') not in known
                or obj.get('supervision_digest') != inventory['digest']):
            return [key + ': stale supervision object binding']
        return []

    def pass_blockers(self, key, planned, generated, inventory):
        if generated and generated.get('inventory_gaps'):
            gaps = [g for g in generated['inventory_gaps'] if isinstance(g, str)]
            return [key + ': supervision gaps must be resolved in a regenerated plan before PASS'
                    + ('; gaps: ' + '; '.join(gaps[:4]) if gaps else '')
                    + '; a rail watched only by on-chip UVLO/reset is declared in intent '
                      'supervision.rail_requirements (required=false or internal_monitor with its source), '
                      'then the plan is regenerated: that is a declaration, not a tool limitation']
        return []

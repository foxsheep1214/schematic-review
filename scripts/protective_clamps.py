# -*- coding: utf-8 -*-
"""Which clamp parts are protective: the one test the clamp scan (lint, PRO-E02) and the plan (PRO-C02) share.

A protective clamp sits between a rail or IC pin net and ground and is judged once, per part, in PRO-E02: working
voltage against the net's normal maximum, clamp voltage at the required surge current against the lowest limit of
every part on the net, pulse energy (2026-10-26, user: 按方案 B 改). The plan gives such a part no PRO-C02 window;
PRO-C02 keeps threshold-pin windows, reference or level zeners and energy clamps across switch nodes.
"""
import re

import part_words as pw
from checkers import netgraph as ng
from checkers.netgraph import rail_voltage
from checkers.powertree import SWITCH_NODE_PIN_RE

CLAMP_RE = re.compile(r'ZENER|TVS|BZT|BZX|SMBJ|SMAJ|SMCJ|MMSZ|1SMB|ESDA|PESD', re.I)   # BZX55/BZX84/BZX585 zeners too


def part_text(part):
    return ' '.join(str(part.get(k, '')) for k in ('part', 'value', 'prim'))


def functional_clamp(graph, net, intent):
    """A zener to ground whose other end is an internal signal node — no connector contact, not a rail by name or
    declaration, and an IC pin or a transistor gate/base on it — is a reference or level clamp, not a protective
    device (R6 acceptance 2026-10-24: D303 ZCD clamp and D404 gate reference asked for surge data). A node that
    also reaches a connector is protective and keeps the PRO-E02 line; a TVS part is protective wherever it sits."""
    if is_rail(net, intent):
        return False
    if port_connectors(graph, net):
        return False
    inside = False
    for node in graph.nodes_on(net):
        ref = node.partition('.')[0]
        kind = graph.kind(ref)
        if kind == pw.TESTPOINT:
            return False
        if kind == pw.IC or (kind in (pw.MOSFET, pw.BJT) and graph.role(node) == 'gate'):
            inside = True
    return inside


# Exact manufacturer physical-pin rules. Each tuple is one protected electrical
# channel, not a short between channels or across NC feed-through layout pads.
CHANNEL_RULES = (
    (r'SP1001-04[JX]TG', (('1',), ('3',), ('4',), ('5',)), ('2',), (),
     'Littelfuse SP1001 Rev GD 2024-07-10 p1 pinout / functional block diagram'),
    (r'(?:PESD2USB5UV(?:-TR?)?|PESD5V0L2BT(?:,215)?|(?:SZ)?NUP2105L(?:T1G)?)',
     (('1',), ('2',)), ('3',), (),
     'Nexperia PESD2USB5UV-T 2020-09-09 p2; PESD5V0L2BT 2023-06-27 p2 Table2; onsemi NUP2105L/D p1'),
    (r'(?:TPD4E05U06(?:QDQARQ1|-Q1)|CDDFN10-3324P)',
     (('1',), ('2',), ('4',), ('5',)), ('3', '8'), ('6', '7', '9', '10'),
     'TI SLVSCO7C p3 DQA pin functions; Bourns CDDFN10-3324P p2 Device Pinout'),
    (r'TPD8S009(?:DSMR)?', tuple((str(p),) for p in (1, 3, 4, 6, 7, 9, 10, 12)),
     ('2', '5', '8', '11'), ('14',), 'TI TPD8S009 SLVS816B p3 pin functions; p6 VCC is optional supply'),
    (r'USBLC6-2SC6Y?', (('1', '6'), ('3', '4'), ('5',)), ('2',), (),
     'ST USBLC6-2SC6 DocID11265 / USBLC6-2SC6Y DocID023201 Rev2 p1 Fig1; VBUS also protected'),
    (r'SM3\.3H(?:-TP)?', (('1',), ('2',)), ('3',), (), 'MCC SM3.3H Rev3-3-12012020 p1 internal structure'),
    (r'RESD1CANYFH(?:T116)?', (('1',), ('2',)), ('3',), (), 'ROHM RESD1CANYFH p1 internal circuit'),
    (r'SP3003-02[JX]TG', (('4',), ('5',), ('3',)), ('2',), ('1',),
     'Littelfuse SP3003 Rev GD 2022-11-30 p1 pinout/block diagram: 3=VCC clamp, 1=NC'),
)


def channels(ref, part, graph, intent=None):
    """Protected channels with physical pins, returns and source. Unknown arrays stay unresolved.

    An official complete table resolves arbitrary TVS arrays. A model rule only
    applies to its exact identity; it never guesses from a generic package.
    """
    if not graph.is_fitted(ref):
        return []
    device = ((intent or {}).get('devices') or graph.db.get('devices') or {}).get(ref, {})
    actual = graph.pins_of(ref)
    identities = [device.get('mpn')] + [part.get(k) for k in ('part', 'value')]
    rule = next((r for r in CHANNEL_RULES if any(re.fullmatch(r[0], str(i or ''), re.I) for i in identities)), None)
    protective = graph.kind(ref) == pw.TVS or rule is not None
    if not protective and not CLAMP_RE.search(part_text(part)):
        return []
    groups, returns, ignored, citation = None, (), (), ''
    if rule:
        _, groups, returns, ignored, citation = rule
    elif protective and device.get('pinout_complete') and device.get('citation'):
        pins = device.get('pins', {})
        returns = tuple(p for p,s in pins.items() if s.get('role') == 'return')
        ignored = tuple(p for p,s in pins.items() if s.get('role') in ('nc', 'absent'))
        grouped = {}
        for p,s in pins.items():
            if p not in returns + ignored:
                grouped.setdefault(s['name'], []).append(p)
        if returns:
            groups = tuple(tuple(ps) for ps in grouped.values())
            citation = device['citation']
    # Native physical I/O names can discover a TVS channel question; this is
    # not manufacturer verification of an unconfirmed identity or parameters.
    if groups is None and protective:
        returns = tuple(p for p in actual if ng.is_ground(actual[p]))
        grouped = {}
        for p in actual:
            name = graph.pinname.get(ref + '.' + p, '')
            if p not in returns and re.fullmatch(r'(?:I/?O|D)\d+(?:[+-])?|K\d*|A\d+', name, re.I):
                # boards-merge6 F06: bare K pins on one net (TVS3300 K on 4/5/6) are one cathode, one channel;
                # bare K pins on different nets (NUP2105L CAN_H/CAN_L) stay separate channels
                key = name if re.match(r'(?:I/?O|D)', name, re.I) else 'K:' + actual[p] if name.upper() == 'K' else p
                grouped.setdefault(key, []).append(p)
        if returns and grouped:
            groups = tuple(tuple(ps) for ps in grouped.values())
            source = (graph.db.get('device_kinds') or {}).get(ref, {}).get('citation', '')
            citation = f'native physical I/O names; TVS basis={graph.basis(ref)}; {source}; channel parameters require datasheet'
    if groups is None:
        ends = sorted(set(actual.values()) - graph.pseudo)
        if len(ends) != 2:
            return []
        grounded = [e for e in ends if ng.is_ground(e)]
        if not grounded and not protective:
            return []
        # A floating two-terminal TVS still has a differential working window;
        # do not turn a rectifier's local negative rail into a trip threshold.
        ret = grounded[0] if grounded else ends[0]
        live = next(e for e in ends if e != ret)
        if graph.kind(ref) == pw.ZENER and functional_clamp(graph, live, intent):
            return []
        returns = tuple(p for p in actual if actual[p] == ret)
        groups = (tuple(p for p in actual if actual[p] == live),)
        citation = 'native two-terminal clamp; differential return' if not grounded else 'native two-terminal clamp to ground'
    out = []
    for group in groups:
        pins = sorted(set(group) & set(actual))
        nets = sorted({actual[p] for p in pins} - graph.pseudo)
        window_nets = nets + [actual[p] for p in returns if p in actual and not ng.is_ground(actual[p])]
        if any(switch_node(graph, n, intent) for n in window_nets):
            continue   # an energy clamp remains in the two-sided engineering window
        # An unused channel with only a single open/NC endpoint is no live port.
        nets = [n for n in nets if not (ng.is_auto_named(n) and str(n).rsplit('/', 1)[-1].startswith('unconnected-'))]
        if not nets:
            continue
        return_pins = sorted(set(returns) & set(actual))
        out.append({'channel': '-'.join(group), 'pins': pins, 'nets': nets,
                    'return_pins': return_pins, 'return_nets': sorted({actual[p] for p in return_pins} - graph.pseudo),
                    'nc_pins': sorted(set(ignored) & set(actual)), 'citation': citation,
                    'gaps': [] if return_pins else ['clamp-return-pinout:' + ref]})
    return out


def protected_net(ref, part, pin2net, graph, intent):
    """Compatibility query for callers deciding whether PRO-C02 applies.

    Enumeration uses channels(); a multi-channel package has no single net.
    """
    found = channels(ref, part, graph, intent)
    return found[0]['nets'][0] if found else None


def port_connectors(graph, net):
    """Connectors on the clamp's net or one series resistor, ferrite or inductor away: where a port surge or ESD
    arrives (2026-10-27, user: 按你的建议改 C5 — an internal node sees only what reaches it)."""
    found = set()
    for node in graph.nodes_on(net):
        ref = node.partition('.')[0]
        kind = graph.kind(ref)
        if not graph.is_fitted(ref):
            continue
        if kind == pw.CONNECTOR:
            found.add(ref)
        elif kind in (pw.RESISTOR, pw.FERRITE, pw.INDUCTOR) and len(graph.nets_of(ref)) == 2:
            far = next(n for n in graph.nets_of(ref) if n != net)
            found.update(r for r in (x.partition('.')[0] for x in graph.nodes_on(far))
                         if graph.kind(r) == pw.CONNECTOR and graph.is_fitted(r))
    return sorted(found)


def transient_source_text(graph, net):
    """Which transient the clamp is judged against: one event, the one that reaches this node."""
    ports = port_connectors(graph, net)
    if ports:
        return ('该网接连接器 %s：对外端口按需求的浪涌或 ESD 波形取钳位电流（板内互连按能到达的瞬态）；'
                % '、'.join(ports))
    return ('该网不接连接器（内部节点）：瞬态按前级钳位后的残压或本地源（热插拔、感性关断）取，'
            '没有瞬态源时只核工作电压与稳态功耗；')


def is_rail(net, intent):
    return bool(ng.RAIL_RE.match(net) or rail_voltage(net) is not None or net in ((intent or {}).get('power_rails') or {}))


def switch_node(graph, net, intent=None):
    """A switch node: an SW/LX/PH/BOOT-type pin on the net (PowerTree.is_switch_node), or a fitted transformer winding
    on a net that is no rail by name or declaration (a discrete switch's drain carries no such pin name; the winding's
    other end on the input rail is DC, so a clamp there protects the rail)."""
    winding = not is_rail(net, intent)

    def power_winding(ref):
        # Ethernet/signal magnetics are not power-switch evidence. Require an
        # actual switching pin or transistor switch terminal on this magnetic.
        return any(pw.name_matches(SWITCH_NODE_PIN_RE, graph.pinname.get(n), n.partition('.')[2])
                   or (graph.kind(n.partition('.')[0]) == pw.MOSFET and graph.role(n) == 'drain')
                   or (graph.kind(n.partition('.')[0]) == pw.BJT and graph.role(n) == 'collector')
                   for other in graph.nets_of(ref) if not ng.is_ground(other) and not is_rail(other, intent)
                   for n in graph.nodes_on(other) if graph.is_fitted(n.partition('.')[0]))

    return any(pw.name_matches(SWITCH_NODE_PIN_RE, graph.pinname.get(node), node.partition('.')[2])
               or (winding and graph.kind(node.partition('.')[0]) in pw.WINDING_PAIRS
                   and graph.is_fitted(node.partition('.')[0]) and power_winding(node.partition('.')[0]))
               for node in graph.nodes_on(net))

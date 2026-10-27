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
    inside = False
    for node in graph.nodes_on(net):
        ref = node.partition('.')[0]
        kind = graph.kind(ref)
        if kind in (pw.CONNECTOR, pw.TESTPOINT):
            return False
        if kind == pw.IC or (kind in (pw.MOSFET, pw.BJT) and graph.role(node) == 'gate'):
            inside = True
    return inside


def protected_net(ref, part, pin2net, graph, intent):
    """The non-ground net a protective clamp guards, or None: a clamp part (by its own text) fitted, with exactly two
    nets of which one is ground, the other no switch node, and not a reference or level zener on an internal node."""
    if part.get('nc') or not CLAMP_RE.search(part_text(part)):
        return None
    ends = sorted({net for pin, net in pin2net.items() if pin.partition('.')[0] == ref})
    if len(ends) != 2 or not any(ng.is_ground(e) for e in ends):
        return None
    rails = [e for e in ends if not ng.is_ground(e)]
    if not rails:
        return None
    if switch_node(graph, rails[0], intent):
        return None   # an energy clamp across a switch node: PRO-C02 two-sided rows judge it
    if graph.kind(ref) == pw.ZENER and functional_clamp(graph, rails[0], intent):
        return None
    return rails[0]


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
    return any(pw.name_matches(SWITCH_NODE_PIN_RE, graph.pinname.get(node), node.partition('.')[2])
               or (winding and graph.kind(node.partition('.')[0]) in pw.WINDING_PAIRS
                   and graph.is_fitted(node.partition('.')[0]))
               for node in graph.nodes_on(net))

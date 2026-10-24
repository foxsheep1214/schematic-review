#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""参考地分区、跨域器件与走线截止网络：按连接关系推导，审查员不画。

域 = 经直流导通的器件能到达同一个地的网络集合。电容、变压器、光耦、继电器、晶振、连接器和
手册核验为 isolator 的器件不导通；其余器件在它的全部引脚之间导通。跨域器件 = 引脚跨两个域的器件。
截止网络 = 电路候选从核心器件向外走时停下的网络：地、IC 输出脚驱动的网、或声明轨中被两个以上核心器件
在一跳两端件之内到达的网；只被一个核心器件用的声明轨是那个电路的内部节点。

只回答"网表里连成了什么"，不回答电气是否合格；与 intent.power_rails 的 domain 声明不一致时
记冲突，不改声明。
"""
from . import netgraph as ng
import part_words as pw
from . import passive_stress
from . import powertree

SCHEMA_VERSION = 1
GROUND = 'ground'
DRIVER = 'driver'
# Parts that do not conduct DC between their pins for the purpose of ground reference.
NON_CONDUCTING = frozenset({pw.CAPACITOR, pw.TRANSFORMER, pw.OPTO, pw.RELAY, pw.CRYSTAL, pw.CONNECTOR,
                            pw.TESTPOINT, pw.BATTERY, pw.UNKNOWN})   # an unclassified part merges nothing
ISOLATOR = 'isolator'


def _window(rail):
    v = rail.get('voltage_v') if isinstance(rail, dict) else None
    return v if isinstance(v, dict) and all(isinstance(v.get(k), (int, float)) for k in ('min', 'max')) else None


def ground_labels(graph, intent):
    """{地网: 域标签}。标签取 power_rails.<网>.domain，未声明的地按网名各成一域。

    地 = 名字是地或回流（passive_stress.ground_name：GND 族、_RTN/_RETURN）或声明窗口 min = max = 0 的网；
    只把上界压到 0 V 的检测线不是地。
    """
    rails = (intent or {}).get('power_rails') or {}
    rails = rails if isinstance(rails, dict) else {}
    labels = {}
    for net in graph.nets:
        if net in graph.pseudo:
            continue
        rail = rails.get(net) if isinstance(rails.get(net), dict) else {}
        window = _window(rail)
        zero = window is not None and window['min'] == 0 and window['max'] == 0
        if not (passive_stress.ground_name(net) or zero):
            continue
        domain = rail.get('domain') if isinstance(rail.get('domain'), str) and rail['domain'].strip() else None
        labels[net] = domain or pw.normalize(net).rsplit('/', 1)[-1]
    return labels


def conducts(graph, ref):
    """器件引脚之间是否直流导通（参考地分区意义上）。"""
    if graph.kind(ref) in NON_CONDUCTING:
        return False
    if graph.role_kind(ref) == ISOLATOR:
        return False
    return True


def _components(graph, grounds):
    """并查集：经导通器件相连的网络分量。

    返回 {net: root} 和把两个不同标签的地连到一起的器件 [(ref, [标签, 标签])]。
    """
    parent = {net: net for net in graph.nets if net not in graph.pseudo}
    labels = {net: {label} for net, label in grounds.items() if net in parent}

    def find(net):
        while parent[net] != net:
            parent[net] = parent[parent[net]]
            net = parent[net]
        return net

    bridges = []
    for ref in sorted(graph.parts):
        if not graph.is_fitted(ref) or not conducts(graph, ref):
            continue
        nets = [n for n in graph.nets_of(ref) if n in parent]
        for other in nets[1:]:
            a, b = find(nets[0]), find(other)
            if a == b:
                continue
            la, lb = labels.get(a, set()), labels.get(b, set())
            if la and lb and la != lb:
                bridges.append((ref, sorted(la | lb)))
            parent[b] = a
            labels[a] = la | lb
            labels.pop(b, None)
    return {net: find(net) for net in parent}, bridges


def derive(graph, intent=None):
    """参考地分区、跨域器件、核心器件与截止网络；冲突只记录。"""
    grounds = ground_labels(graph, intent)
    roots, bridges = _components(graph, grounds)
    root_domain, conflicts = {}, []
    for net, label in sorted(grounds.items()):
        root_domain.setdefault(roots[net], label)   # a merged component keeps its first label; the bridge is the conflict
    merged = {}
    for ref, pair in bridges:
        merged.setdefault(tuple(pair), []).append(ref)
    for pair, refs in sorted(merged.items()):
        conflicts.append({'code': 'DOMAIN_MERGED', 'domains': list(pair), 'via': sorted(set(refs))})
    nets = {net: root_domain.get(roots[net]) for net in roots}
    domains = {}
    for net, label in nets.items():
        if label is not None:
            domains.setdefault(label, []).append(net)
    domains = {label: sorted(members) for label, members in sorted(domains.items())}
    unreferenced = sorted(net for net, label in nets.items() if label is None)

    rails = (intent or {}).get('power_rails') or {}
    rails = rails if isinstance(rails, dict) else {}
    for net, rail in sorted(rails.items()):
        declared = rail.get('domain') if isinstance(rail, dict) and isinstance(rail.get('domain'), str) else None
        derived = nets.get(net)
        if declared and net not in grounds and derived is not None and derived != declared:
            conflicts.append({'code': 'DOMAIN_CONFLICT', 'net': net, 'declared': declared, 'derived': derived})

    barriers = []
    for ref in sorted(graph.parts):
        if not graph.is_fitted(ref):
            continue
        touched = sorted({nets.get(n) for n in graph.nets_of(ref)} - {None})
        if len(touched) > 1:
            barriers.append({'ref': ref, 'kind': graph.kind(ref), 'domains': touched})

    anchors = {ref: graph.role_kind(ref) for ref in sorted(graph.parts) if graph.is_anchor(ref)}
    undeclared = sorted(ref for ref in graph.parts if graph.is_fitted(ref) and graph.kind(ref) == pw.IC
                        and graph.role_kind(ref) is None)
    return {
        'schema_version': SCHEMA_VERSION,
        'grounds': grounds,
        'domains': domains,
        'nets': nets,
        'unreferenced': unreferenced,
        'barriers': barriers,
        'anchors': anchors,
        'undeclared_ics': undeclared,
        'rail_stops': rail_stops(graph, intent, grounds, anchors),
        'conflicts': conflicts,
    }


def rail_stops(graph, intent, grounds, anchors):
    """{网: 依据}：地（ground）、IC 输出脚驱动的网（driver）、两个以上核心器件在一跳内到达的声明轨（anchors:...）。"""
    stops = {net: GROUND for net in grounds}
    tree = powertree.PowerTree(graph, intent)
    rails = (intent or {}).get('power_rails') or {}
    rails = rails if isinstance(rails, dict) else {}
    for net in sorted(graph.nets):
        if net in stops or net in graph.pseudo or tree.is_switch_node(net):
            continue
        if tree.rail_basis(net) == powertree.DRIVER:
            stops[net] = DRIVER
            continue
        if net not in rails:
            continue
        reached = set()
        for ref in graph.refs_on(net):
            if ref in anchors:
                reached.add(ref)
            elif graph.kind(ref) in pw.TWO_TERMINAL and len(graph.nets_of(ref)) == 2:
                other = next(n for n in graph.nets_of(ref) if n != net)
                # one two-terminal hop, but never through a ground or another stop: a bypass capacitor to
                # ground does not make every IC on that ground reach the net
                if other not in grounds and other not in graph.pseudo:
                    reached.update(ref2 for ref2 in graph.refs_on(other) if ref2 in anchors)
        if len(reached) >= 2:
            stops[net] = 'anchors:' + ','.join(sorted(reached))
    return dict(sorted(stops.items()))


def build_section(db, intent=None):
    return derive(ng.NetGraph(db), intent)

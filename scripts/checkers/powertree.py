#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""电源来源与电源轨身份的共享推导。

只回答"这个网有没有可信的来源候选"和"它算不算电源轨、依据是什么"，不回答
"这条轨够不够、稳不稳"。来源候选按连接关系推导：从稳压器输出脚沿已装配的
串联无源件和正向二极管（阴极→阳极）回溯到稳压器输出脚、POWER 类型的输出名脚或
经储能电感的开关脚，或用设计意图里带出处的声明来源；轨名只能作为最弱的一级依据。
"""
import re

from solve_dividers import parse_resistor

from . import netgraph as ng

# 输出脚候选：型号/脚名提示，仍需资料取证核功能与上游供电
SOURCE_PIN_RE = re.compile(r'^(VOUT|VREG|VDD_EXT|VO)(?:$|[_+\d])', re.I)
# 裸 OUT 脚只在同器件另有 IN/VIN 脚时算候选（LDO、负载开关的形状），运放/逻辑门不算
PLAIN_OUT_PIN_RE = re.compile(r'^OUT$', re.I)
PLAIN_IN_PIN_RE = re.compile(r'^V?IN$', re.I)
SERIES_REF_RE = re.compile(r'^(L|FB|F)\d', re.I)
# 开关节点：经储能电感能回溯到输出脚，但它本身不是直流轨
SWITCH_NODE_PIN_RE = re.compile(r'^(SW\d*|LX\d*|PH\d*|VSW|SWITCH|HS|LS|BOOT\w*|BST\w*)$', re.I)
IC_REF_RE = re.compile(r'^[UM]\d', re.I)
# 经储能电感输出的开关脚；自举脚不输出电流，不算
SWITCH_OUTPUT_PIN_RE = re.compile(r'^(SW\d*|LX\d*|PH\d*|VSW|SWITCH)$', re.I)
# 同一器件上这些脚落在电感远端网时，电感是输入侧（升压类），不作来源
SUPPLY_IN_PIN_RE = re.compile(r'^(P?VIN\w*|VCC\w*|VDD\w*|VBAT\w*|VSUP\w*)$', re.I)

DECLARED = 'declared'      # intent 中带出处的来源
DRIVER = 'driver'          # 网上有输出脚候选（拓扑依据）
NAME_HINT = 'name-hint'    # 只有轨名像


class PowerTree:
    """按某一装配状态推导来源与轨身份；结果带依据级别，不带电气结论。"""

    def __init__(self, graph, intent=None):
        self.graph = graph
        intent = intent or {}
        self.state = intent.get('active_state')
        self.sources = {x.get('node'): x for x in intent.get('power_sources', [])
                        if x.get('citation') and self.state in x.get('states', [])}
        self.directed = [x for x in intent.get('power_paths', [])
                         if x.get('citation') and x.get('state') == self.state]
        self._cache = {}

    def source_of(self, net):
        """来源候选与到达路径；找不到返回 None。不是电源轨准出。"""
        if net not in self._cache:
            self._cache[net] = self._search(net)
        return self._cache[net]

    def driven(self, net):
        return self.source_of(net) is not None

    def is_switch_node(self, net):
        """网上有 SW/LX/PH/BOOT 类引脚：开关节点，不按直流轨处理。"""
        return any(ng.name_matches(SWITCH_NODE_PIN_RE, self.graph.pinname.get(node),
                                   node.partition('.')[2])
                   for node in self.graph.nodes_on(net))

    def rail_basis(self, net):
        """电源轨身份依据：declared / driver / name-hint / None。"""
        if not net or ng.is_ground(net) or net in self.graph.pseudo:
            return None
        if self.is_switch_node(net):
            return None
        found = self.source_of(net)
        if found:
            return DECLARED if found['basis'] == 'declared source' else DRIVER
        return NAME_HINT if ng.is_rail(net) else None

    def is_rail(self, net):
        return self.rail_basis(net) is not None

    def _search(self, net):
        graph = self.graph
        queue, seen = [(net, [])], set()
        while queue:
            current, path = queue.pop(0)
            if current in seen or ng.is_ground(current) or current in graph.pseudo:
                continue
            seen.add(current)
            for node in graph.nodes_on(current):
                ref = node.partition('.')[0]
                part = graph.parts.get(ref, {})
                if not part or not graph.is_fitted(ref):
                    continue
                if node in self.sources:
                    return {'source': node, 'path': list(reversed(path)),
                            'basis': 'declared source', 'state': self.state}
                pin = node.partition('.')[2]
                output_name = ng.name_matches(SOURCE_PIN_RE, graph.pinname.get(node), pin)
                if IC_REF_RE.match(ref) and output_name:
                    return {'source': node, 'path': list(reversed(path)),
                            'basis': 'pin-name candidate; verify function and upstream power'}
                if (IC_REF_RE.match(ref)
                        and ng.name_matches(PLAIN_OUT_PIN_RE, graph.pinname.get(node), pin)
                        and set(graph.named_pins(ref, PLAIN_IN_PIN_RE).values()) - {current}):
                    return {'source': node, 'path': list(reversed(path)),
                            'basis': 'OUT pin beside IN pin (regulator/load-switch shape); '
                                     'verify function and upstream power'}
                if output_name and graph.pintype.get(node) == 'POWER':
                    return {'source': node, 'path': list(reversed(path)),
                            'basis': 'power-type output pin name on non-IC refdes; '
                                     'verify module function and upstream power'}
                if (IC_REF_RE.match(ref) and path and self._via_storage_inductor(ref, path)
                        and ng.name_matches(SWITCH_OUTPUT_PIN_RE, graph.pinname.get(node), pin)):
                    return {'source': node, 'path': list(reversed(path)),
                            'basis': 'switch node via storage inductor; verify converter '
                                     'topology, FB target and upstream power'}
                ends = graph.nets_of(ref)
                if len(ends) != 2 or current not in ends:
                    continue
                other = ends[0] if ends[1] == current else ends[1]
                # 二极管 OR：只从阴极侧回溯到阳极侧
                if graph.kind(ref) == ng.DIODE:
                    cathode = graph.node_named(ref, 'cathode')
                    if (graph.node_named(ref, 'anode') and cathode
                            and graph.pin2net.get(cathode) == current):
                        queue.append((other, path + [ref]))
                    continue
                resistor = parse_resistor(part.get('value')) if re.match(r'^R\d', ref) else None
                if SERIES_REF_RE.match(ref) or (resistor and resistor['kohm'] == 0):
                    queue.append((other, path + [ref]))
            # 多脚 MOS 模型按端点精确匹配验证
            for edge in self.directed:
                ref = edge.get('ref')
                part = graph.parts.get(ref, {})
                ends = graph.nets_of(ref) if ref else []
                if (part and graph.is_fitted(ref) and edge.get('to') == current
                        and edge.get('from') in ends and current in ends):
                    queue.append((edge['from'], path + [ref]))
        return None

    def _via_storage_inductor(self, ref, path):
        """最后一跳是电感，且该器件的供电输入脚不在电感远端网（排除升压输入侧）。"""
        graph = self.graph
        inductor = path[-1]
        if graph.kind(inductor) != ng.INDUCTOR:
            return False
        far = set(graph.nets_of(inductor))
        own = set(graph.named_pins(ref, SWITCH_OUTPUT_PIN_RE).values())
        far -= own
        supply = set(graph.named_pins(ref, SUPPLY_IN_PIN_RE).values())
        return bool(far) and not (far & supply)

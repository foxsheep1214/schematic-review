#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""物料与引脚层面的自动扫描（方式 A）：耐压、极性、限流、悬空输入与位号。

只用网表、BOM 值字段和引脚名/类型做确定性判别，输出仍是疑似清单：轨压来自网名推断、
降额规则来自项目，都由审查者按对应的工程计算规则定判。装配选项（不贴/跳线）按解析器
的 nc 标记排除，其余状态差异由审查者排除。
"""
import re

from checkers.netgraph import is_ground, is_rail, rail_voltage

# BOM 值字段里写明的耐压：100nF/16V、10uF 25V、4.7u/X5R/50V
RATING_RE = re.compile(r'(?<![\d.])(\d+(?:\.\d+)?)\s*V(?![\dA-Z])', re.I)
LED_RE = re.compile(r'(^|[^A-Z])LED(S|[^A-Z]|$)', re.I)
POLARITY = {'+': 'plus', 'P': 'plus', 'POS': 'plus', '-': 'minus', 'N': 'minus', 'NEG': 'minus'}
REFDES_RE = re.compile(r'^[A-Za-z]+\d+[A-Za-z]?$')


def _rated_v(value):
    """BOM 值里写明的耐压；写了多个取最小，写不明返回 None。"""
    ratings = [float(x) for x in RATING_RE.findall(str(value or ''))]
    return min(ratings) if ratings else None


def _nodes(lint, ref):
    return sorted(node for node in lint.pin2net if node.rpartition('.')[0] == ref)


def _is_capacitor(ref, part):
    blob = (str(part.get('part', '')) + ' ' + str(part.get('prim', ''))).upper()
    return bool(re.match(r'^C\d', ref, re.I) or re.search(r'\bCAP\b|CAPACITOR', blob))


def capacitor_ratings(lint):
    """DEV-A01：BOM 写明的耐压低于按网名推断的电压。"""
    for ref, part in sorted(lint.parts.items()):
        if part.get('nc') or not _is_capacitor(ref, part):
            continue
        rated = _rated_v(part.get('value'))
        if rated is None:
            continue
        for node in _nodes(lint, ref):
            net = lint.pin2net.get(node)
            voltage = rail_voltage(net) if net and net not in lint.pseudo else None
            if voltage is not None and rated < voltage:
                lint.add('DEV-A01', '电容耐压低于轨名电压',
                         f'{ref} {part.get("value")}: 耐压 {rated:g}V < {net} 推断 {voltage:g}V；'
                         '轨压按网名推断，降额规则按项目定（DEV-C01/DEV-C02）',
                         ref, kind='CANDIDATE')
                break


def capacitor_polarity(lint):
    """DEV-A02：按 +/- 脚名判别的极性电容反接。"""
    for ref, part in sorted(lint.parts.items()):
        if part.get('nc') or not _is_capacitor(ref, part):
            continue
        marked = {}
        for node in _nodes(lint, ref):
            side = POLARITY.get(str(lint.pinname.get(node, '')).strip().upper())
            if side:
                marked[side] = node
        if len(marked) != 2:
            continue
        plus, minus = lint.pin2net.get(marked['plus']), lint.pin2net.get(marked['minus'])
        if is_ground(plus) and is_rail(minus):
            lint.add('DEV-A02', '极性电容方向反接',
                     f'{ref}: + 脚 {marked["plus"]} 接 {plus}，- 脚 {marked["minus"]} 接 {minus}',
                     ref)


def led_current_limit(lint):
    """DEV-A03：LED 直接跨接命名电源轨与已知地。"""
    for ref, part in sorted(lint.parts.items()):
        blob = ' '.join(str(part.get(key, '')) for key in ('part', 'value', 'prim'))
        if part.get('nc') or not (LED_RE.search(blob) or re.match(r'^(LED|DS)\d', ref, re.I)):
            continue
        nets = [lint.pin2net.get(node) for node in _nodes(lint, ref)]
        if len(nets) != 2 or any(net is None or net in lint.pseudo for net in nets):
            continue
        grounds = [net for net in nets if is_ground(net)]
        rails = [net for net in nets if is_rail(net)]
        if len(grounds) == 1 and len(rails) == 1:
            lint.add('DEV-A03', 'LED 无限流元件',
                     f'{ref}: {rails[0]} 与 {grounds[0]} 之间直接跨接，通路上没有串联电阻；'
                     '恒流驱动须有资料或声明证据', ref)


def floating_inputs(lint):
    """NET-A07：声明为输入的引脚悬空或只在单节点网上。"""
    from lint import _pin_class      # 延迟取用：lint 导入本模块
    types = dict(lint.db.get('declared_pintype', {}), **lint.pintype)
    no_connect = set(lint.db.get('no_connect_nodes', []))
    for node in sorted(types):
        if _pin_class(types[node]) != 'IN':
            continue
        ref = node.rpartition('.')[0]
        if lint.parts.get(ref, {}).get('nc'):
            continue
        net = lint.pin2net.get(node)
        declared_nc = node in no_connect or (net is not None and net in lint.pseudo)
        if net is None:
            lint.add('NET-A07', '声明输入脚无网络', f'{node}: 引脚类型为输入，网表中没有网络', ref)
        elif declared_nc:
            lint.add('NET-A07', '声明输入脚标为 No-Connect',
                     f'{node} -> {net}: 输入脚被标为 No-Connect，需确认内部上下拉或有意悬空',
                     ref, kind='CANDIDATE')
        elif len(lint.nets.get(net, [])) < 2:
            lint.add('NET-A07', '声明输入脚悬空', f'{node} -> {net}: 输入脚所在网只有该节点', ref)


def refdes_annotation(lint):
    """DOC-A04：位号未标注或格式无法定位。"""
    for ref in sorted(lint.parts):
        if not REFDES_RE.match(ref):
            lint.add('DOC-A04', '位号未标注', f'{ref}: 位号含 ? 或缺序号，无法定位与对账', ref)


def run(lint):
    """按规则总表顺序执行本模块的自动扫描。"""
    refdes_annotation(lint)
    capacitor_ratings(lint)
    capacitor_polarity(lint)
    led_current_limit(lint)
    floating_inputs(lint)

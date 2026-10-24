#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""物料与引脚层面的自动扫描（方式 A）：耐压、极性、限流、悬空输入与位号。

只用网表、BOM 值字段和引脚名/类型做确定性判别，输出仍是疑似清单：轨压来自网名推断、
降额规则来自项目，都由审查者按对应的工程计算规则定判。装配选项（不贴/跳线）按解析器
的 nc 标记排除，其余状态差异由审查者排除。
"""
import re

from checkers.netgraph import CONNECTOR, IC, LED_RE, RESISTOR, TESTPOINT, is_ground, is_rail, rail_voltage
from checkers.passive_stress import rated_voltage   # BOM 值字段里写明的耐压：100nF/16V、10uF 25V、4.7u/X5R/50V

POLARITY = {'+': 'plus', 'P': 'plus', 'POS': 'plus', '-': 'minus', 'N': 'minus', 'NEG': 'minus'}
REFDES_RE = re.compile(r'^(?!.*\?)[A-Za-z][A-Za-z0-9_/+-]*?\d+[A-Za-z]?$')   # USB-C1, PS2_KBD1, PGM/DBG1 are annotated
I2C_LINE_RE = re.compile(r'^(SDA|SCL)\d*$')


def _named_rail(net):
    """KiCad 电源符号常写成 +5V、+3V3 或带层次前缀；只用于“轨对地”的器件级扫描，不推导来源。"""
    return bool(net) and (is_rail(net) or is_rail(str(net).lstrip('/').lstrip('+')))


KICAD_POLARIZED_RE = re.compile(r'^Device:(?:C_Polarized|CP)(?:\w*)$', re.I)
NEGATIVE_NET_RE = re.compile(r'(^-|NEG|VEE|VSS|(?:^|[_/])-?\d+V\d*N\b|[_-]N$)', re.I)


def _positive_supply(lint, net):
    """A named rail, or a net SR traces to an on-board source or an off-board contact,
    unless its name marks it negative (inverting outputs keep + on ground correctly)."""
    if not net or is_ground(net) or NEGATIVE_NET_RE.search(str(net)):
        return False
    return _named_rail(net) or lint.driven(net) or bool(lint._external_entry(net))


def _nodes(lint, ref):
    return sorted(node for node in lint.pin2net if node.partition('.')[0] == ref)


def _is_capacitor(ref, part):
    blob = (str(part.get('part', '')) + ' ' + str(part.get('prim', ''))).upper()
    return bool(re.match(r'^C\d', ref, re.I) or re.search(r'\bCAP\b|CAPACITOR', blob))


def capacitor_ratings(lint):
    """DEV-A01：BOM 写明的耐压低于按网名推断的电压。"""
    for ref, part in sorted(lint.parts.items()):
        if part.get('nc') or not _is_capacitor(ref, part):
            continue
        rated = rated_voltage(part.get('value'))
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
        if not marked and KICAD_POLARIZED_RE.match(str(part.get('prim') or '')):
            # KiCad's own polarized-capacitor symbols leave pins unnamed; pin 1 is + by library convention.
            nodes = {node.partition('.')[2]: node for node in _nodes(lint, ref)}
            if set(nodes) == {'1', '2'}:
                marked = {'plus': nodes['1'], 'minus': nodes['2']}
        if len(marked) != 2:
            continue
        plus, minus = lint.pin2net.get(marked['plus']), lint.pin2net.get(marked['minus'])
        if is_ground(plus) and _positive_supply(lint, minus):
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
        rails = [net for net in nets if _named_rail(net)]
        if len(grounds) == 1 and len(rails) == 1:
            lint.add('DEV-A03', 'LED 无限流元件',
                     f'{ref}: {rails[0]} 与 {grounds[0]} 之间直接跨接，通路上没有串联电阻；'
                     '恒流驱动须有资料或声明证据', ref)


def _i2c_segment(lint, net):
    """The bus segment around an SDA/SCL net: nets joined by series resistors of at most 1 kOhm
    (a sensor behind 120 Ohm, PiicoDev style). Larger resistors are pull-ups, not series links."""
    from solve_dividers import parse_resistor
    segment, queue = {net}, [net]
    while queue:
        current = queue.pop()
        for ref, other in lint.graph.neighbors(current, {RESISTOR}):
            value = parse_resistor(lint.parts.get(ref, {}).get('value'))
            if (value and value['kohm'] <= 1.0 and other not in segment and not is_ground(other)
                    and not is_rail(other) and other not in lint.pseudo):
                segment.add(other)
                queue.append(other)
    return segment


def _switched_pullups(lint, segment):
    """(switch, resistor) pairs: a DIP switch or solder jumper on the segment whose other contact
    reaches a resistor to a non-ground net, i.e. a pull-up the user can select."""
    from checkers.netgraph import JUMPER, SWITCH
    found = []
    for n in sorted(segment):
        for ref in lint.graph.refs_on(n):
            if lint.graph.kind(ref) not in (SWITCH, JUMPER):
                continue
            for other in lint.graph.nets_of(ref):
                if other in segment or is_ground(other):
                    continue
                for res, far in lint.graph.neighbors(other, {RESISTOR}):
                    if not is_ground(far) and far not in segment:
                        found.append((ref, res))
    return sorted(set(found))


def i2c_pullups(lint):
    """SIG-A03：SDA/SCL 所在总线段上没有任何接到非地网的已装配电阻（段内串阻不算上拉）。"""
    done = set()
    for net, nodes in sorted(lint.nets.items()):
        tokens = re.split(r'[^A-Z0-9]+', str(net).upper())
        if net in lint.pseudo or net in done or not any(I2C_LINE_RE.match(t) for t in tokens) or len(nodes) < 2:
            continue
        segment = _i2c_segment(lint, net)
        done |= segment
        refs = sorted({node.partition('.')[0] for n in segment for node in lint.nets.get(n, [])})
        if not any(lint.graph.kind(ref) == IC for ref in refs):
            continue
        resistors = [ref for ref in refs if lint.graph.kind(ref) == RESISTOR
                     and not lint.parts.get(ref, {}).get('nc')
                     and any(other not in segment and not is_ground(other) for other in lint.graph.nets_of(ref))]
        ics = [ref for ref in refs if lint.graph.kind(ref) == IC]
        access = [ref for ref in refs if lint.graph.kind(ref) == TESTPOINT]
        series = [ref for ref in refs if lint.graph.kind(ref) == RESISTOR and ref not in resistors]
        if not resistors and len(ics) == 1 and len(ics) + len(access) + len(series) == len(refs):
            # 只有一颗 IC，其余是测试点：对端和上拉在生产/调试夹具上（连接器仍按候选，板外主机未必有上拉）。
            lint.add('SIG-A03', 'I²C 线无上拉',
                     f'{net}: 只有 {ics[0]} 和测试点 {access[:6]}，对端与上拉在生产/调试夹具；'
                     '按接口条款核外部上拉与电平，不为此补板载上拉', ics[0], kind='INFO')
            continue
        switched = _switched_pullups(lint, segment) if not resistors else []
        if switched:
            lint.add('SIG-A03', 'I²C 上拉经开关/跳线可选',
                     f'{net}: 上拉 {switched[0][1]} 经 {switched[0][0]} 接入；核出厂/装配时开关或跳线状态',
                     switched[0][0], kind='INFO')
            continue
        if not resistors:
            where = net if segment == {net} else f'{net}（含经串阻相连的 {sorted(segment - {net})[:3]}）'
            lint.add('SIG-A03', 'I²C 线无上拉',
                     f'{where}: {refs[:8]} 上没有接到非地网的电阻；确认上拉由主机侧、片内或其他段提供，'
                     '否则补上拉（阻值按 SIG-C01）', refs[0], kind='CANDIDATE')


def floating_inputs(lint):
    """NET-A07：声明为输入的引脚悬空或只在单节点网上。"""
    from lint import _pin_class      # 延迟取用：lint 导入本模块
    types = dict(lint.db.get('declared_pintype', {}), **lint.pintype)
    no_connect = set(lint.db.get('no_connect_nodes', []))
    for node in sorted(types):
        if _pin_class(types[node]) != 'IN':
            continue
        ref = node.partition('.')[0]
        if lint.parts.get(ref, {}).get('nc'):
            continue
        net = lint.pin2net.get(node)
        declared_nc = node in no_connect or (net is not None and net in lint.pseudo)
        # A deliberately unused passive contact has no internal input-bias
        # obligation. Require role evidence stronger than the refdes alone;
        # unknown parts, IC inputs and unmarked dangling nets still get checked.
        if declared_nc and lint.graph.qualified_connector_contact(ref):
            continue
        # A datasheet NC pin typed input has no input to bias.
        from lint import DATASHEET_NC_PIN_RE
        if DATASHEET_NC_PIN_RE.match(lint.pinname.get(node, '')):
            continue
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
    i2c_pullups(lint)
    floating_inputs(lint)

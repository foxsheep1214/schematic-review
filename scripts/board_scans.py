#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""物料与引脚层面的自动扫描（方式 A）：耐压、极性、限流、悬空输入与位号。

只用网表、BOM 值字段和引脚名/类型做确定性判别，输出仍是疑似清单：轨压来自网名推断、
降额规则来自项目，都由审查者按对应的工程计算规则定判。装配选项（不贴/跳线）按解析器
的 nc 标记排除，其余状态差异由审查者排除。
"""
import re

from checkers.netgraph import is_ground, is_rail, rail_voltage
from decoupling import parse_capacitance
from part_words import CAPACITOR, CONNECTOR, CRYSTAL, FERRITE, IC, INDUCTOR, JUMPER, LED_RE, RESISTOR, SWITCH, TESTPOINT
from checkers.passive_stress import rated_voltage   # BOM 值字段里写明的耐压：100nF/16V、10uF 25V、4.7u/X5R/50V

POLARITY = {'+': 'plus', 'P': 'plus', 'POS': 'plus', '-': 'minus', 'N': 'minus', 'NEG': 'minus'}
REFDES_RE = re.compile(r'^(?!.*\?)[A-Za-z][A-Za-z0-9_/+-]*?\d+[A-Za-z]?$')   # USB-C1, PS2_KBD1, PGM/DBG1 are annotated
I2C_LINE_RE = re.compile(r'^(SDA|SCL)\d*$')
# UM10204 §7.1：Rp_max = tr/(0.8473·Cb)，Rp_min = (Vpullup-VOL)/IOL。取最宽松的一端，超出就没有哪种模式能成立：
# 标准模式 tr 1 µs（表 11）、Cb 只算一个脚的 10 pF；增强快速模式 IOL 20 mA、VOL 0.4 V（表 10）。
I2C_RP_MAX_OHM = 1e-6 / (0.8473 * 10e-12)
I2C_IOL_MAX_A = 20e-3
I2C_VOL_V = 0.4
I2C_DEFAULT_PULLUP_V = 1.8   # 网名读不出电压时取常用的最低总线电压，算出的下限只会偏宽
# 只认端口本身的 VBUS；限流器之后的网（VBUS_SW 等）不累加。
USB_VBUS_NET_RE = re.compile(r'(^|[/_.:-])(VBUS|VUSB)\d*$', re.I)
USB_SINK_BULK_MAX_F = 100e-6
# 只认名字明确的隔离器；光耦的两侧没有地脚名，归 PRO-D01。
ISOLATOR_IDENTITY_RE = re.compile(r'ISOLATOR|ADUM\d|ADM2\d{3}|ADM3\d{3}|CA-?IS\d|\bISOW?\d{3}|\bSI8[4-9]\d|\bNSI\d', re.I)
ISOLATOR_GROUND_PIN_RE = re.compile(r'^(?:GND|VSS)_?([12AB])$', re.I)
CRYSTAL_LOAD_MAX_F = 100e-12
# 多功能脚写成 PF0-OSC_IN 或 PB6/XTAL1 时只看其中的振荡功能名。
OSCILLATOR_PIN_RE = re.compile(r'(?:^|[/\\\s,_-])(?:X(?:TAL)?_?(?:I|O|IN|OUT|1|2|P|N)|OSC_?(?:I|O|IN|OUT|1|2|P|N))(?:$|[/\\\s,_-])', re.I)
CAN_PIN_RE = re.compile(r'^CAN_?([HL])$', re.I)
CAN_SHORT_KOHM = 0.001
USB_PIN_RE = re.compile(r'^(VBUS|CC[12]|D[+-])$', re.I)
# 身份只作线索，判据是“输出网上没有电容”；无需 Cout 的型号由审查者按手册关闭。
LDO_IDENTITY_RE = re.compile(r'REGULATOR_LINEAR|\bLDO|LOW.?DROPOUT|LINEAR.?REG|AMS1117|L[MD]1117|AP2112|AP2210|'
                             r'MCP170\d|XC62\d\d|RT9013|RT9193|LP298\d|LP5907|TLV7\d{4}|TPS7[\dA]|SPX3819|HT7\d33|ME6211|'
                             r'LM317|LM78\d\d|\bL?78\d\d\b', re.I)
REGULATOR_OUT_PIN_RE = re.compile(r'^V?OUT\d*$|^VO$', re.I)


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


def _is_i2c_net(net):
    return any(I2C_LINE_RE.match(token) for token in re.split(r'[^A-Z0-9]+', str(net).upper()))


def _pull_rail(lint, net):
    """上拉电阻远端接到的电源轨：该网本身是命名轨，或经一只跳线/开关到命名轨；否则 None。"""
    if _named_rail(net):
        return net
    for ref in lint.graph.refs_on(net):
        if lint.graph.kind(ref) in (SWITCH, JUMPER):
            for other in lint.graph.nets_of(ref):
                if other != net and _named_rail(other):
                    return other
    return None


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
                    and not _pull_rail(lint, other) and other not in lint.pseudo):
                segment.add(other)
                queue.append(other)
    return segment


def _switched_pullups(lint, segment):
    """(switch, resistor) pairs: a DIP switch or solder jumper on the segment whose other contact
    reaches a resistor to a non-ground net, i.e. a pull-up the user can select."""
    from part_words import JUMPER, SWITCH
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
        if net in lint.pseudo or net in done or not _is_i2c_net(net) or len(nodes) < 2:
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


def i2c_pullup_window(lint):
    """SIG-A04：一段总线上全部上拉的并联值超出任何模式都成立不了的外包络（G04-017/018）。"""
    from solve_dividers import parse_resistor
    done = set()
    for net, nodes in sorted(lint.nets.items()):
        if net in lint.pseudo or net in done or not _is_i2c_net(net) or len(nodes) < 2 or _pull_rail(lint, net):
            continue
        segment = _i2c_segment(lint, net)
        done |= segment
        pulls = {}
        for member in segment:
            for ref, other in lint.graph.neighbors(member, {RESISTOR}):
                rail = _pull_rail(lint, other) if other not in segment else None
                if rail:
                    pulls[ref] = rail
        parsed = {ref: parse_resistor(lint.parts[ref].get('value')) for ref in pulls}
        if not pulls or not all(parsed.values()):
            continue
        ohms = [value['kohm'] * 1000 for value in parsed.values()]
        rp = 0.0 if 0 in ohms else 1 / sum(1 / value for value in ohms)
        refs = ','.join(sorted(pulls))
        volts = max(rail_voltage(rail) or I2C_DEFAULT_PULLUP_V for rail in pulls.values())
        low = (volts - I2C_VOL_V) / I2C_IOL_MAX_A
        if rp > I2C_RP_MAX_OHM:
            lint.add('SIG-A04', 'I²C 上拉阻值超出任何模式的窗口',
                     f'{net}: 上拉 {refs} 并联 {rp:g}Ω > {I2C_RP_MAX_OHM:.0f}Ω：Cb 只算 10pF、标准模式 tr 1µs 也不够'
                     '（UM10204 §7.1 式 (1)、表 11；G04-017）；实际模式与总线电容按 SIG-C01 算',
                     sorted(pulls)[0], kind='CANDIDATE')
        elif rp < low:
            lint.add('SIG-A04', 'I²C 上拉阻值超出任何模式的窗口',
                     f'{net}: 上拉 {refs} 并联 {rp:g}Ω < ({volts:g}V-{I2C_VOL_V}V)/20mA={low:g}Ω：'
                     '增强快速模式的 IOL 也拉不低（UM10204 §7.1 式 (2)、表 10；G04-018）；最弱器件 IOL 按 SIG-C01 算',
                     sorted(pulls)[0], kind='CANDIDATE')


def _caps_to_ground(lint, net):
    """[(位号, 法拉或 None)]：直接从该网接到地的已装配电容。"""
    return [(ref, parse_capacitance(lint.parts[ref].get('value')))
            for ref, other in lint.graph.neighbors(net, {CAPACITOR}) if is_ground(other)]


def _has_usb_port(lint):
    """板上有 USB 器件或 USB 脚名。逆变器、电机板也把直流母线叫 VBUS，只凭网名不算 USB。"""
    return (any(USB_PIN_RE.match(str(name).strip()) for name in lint.pinname.values())
            or any('USB' in ' '.join(str(part.get(key, '')) for key in ('part', 'value', 'prim')).upper()
                   for part in lint.parts.values() if not part.get('nc')))


def usb_vbus_bulk(lint):
    """SIG-A05：VBUS/VUSB 网直挂对地电容的 BOM 值合计超过 Sink 上限（G01-029）。"""
    if not _has_usb_port(lint):
        return
    for net in sorted(lint.nets):
        if net in lint.pseudo or not USB_VBUS_NET_RE.search(str(net)):
            continue
        caps = [(ref, farads) for ref, farads in _caps_to_ground(lint, net) if farads]
        total = sum(farads for _, farads in caps)
        if total > USB_SINK_BULK_MAX_F:
            refs = [ref for ref, _ in caps]
            lint.add('SIG-A05', 'VBUS 直挂体电容超过 Sink 上限',
                     f'{net}: {",".join(refs)} 直挂合计 {total * 1e6:g}µF > 100µF（USB PD 表 4.7 注 1、Type-C 表 4-3）；'
                     '端口作 Source 按表 4-2，有限浪涌电路可关闭，角色与限流按 SIG-C05/PWR-C13 核', refs[0], kind='CANDIDATE')


def can_bus_short(lint):
    """SIG-A06：收发器 CANH/CANL 同网，或两网间跨接 ≤1 Ω 电阻（G04-032）；120 Ω 端接不算。"""
    from solve_dividers import parse_resistor
    for ref, part in sorted(lint.parts.items()):
        if part.get('nc') or lint.graph.kind(ref) != IC:
            continue
        nodes = {CAN_PIN_RE.match(str(lint.pinname.get(node, '')).strip()).group(1).upper(): node
                 for node in _nodes(lint, ref) if CAN_PIN_RE.match(str(lint.pinname.get(node, '')).strip())}
        if len(nodes) != 2:
            continue
        high, low = lint.pin2net.get(nodes['H']), lint.pin2net.get(nodes['L'])
        if high == low:
            shorted = f'同在网 {high}'
        else:
            links = [other for other in lint.graph.between(high, low, {RESISTOR})
                     if (parse_resistor(lint.parts[other].get('value')) or {'kohm': 1})['kohm'] <= CAN_SHORT_KOHM]
            if not links:
                continue
            shorted = f'在 {high}/{low} 之间被 {",".join(links)} 跨接'
        lint.add('SIG-A06', 'CAN 总线 H/L 被短接',
                 f'{ref}: {nodes["H"]} 与 {nodes["L"]} {shorted}，无法建立显性差分电平（G04-032；TI TCAN1042 §10.2.2.1）；'
                 '端接应为约 120 Ω，总负载按 SIG-C03 算', ref)


def isolator_ground_bridge(lint):
    """PRO-A05：数字隔离器两侧地同网，或两地间有 ≤1 Ω 电阻、磁珠、电感（G04-040）。"""
    from solve_dividers import parse_resistor
    for ref, part in sorted(lint.parts.items()):
        identity = ' '.join(str(part.get(key, '')) for key in ('part', 'value', 'prim'))
        if (part.get('nc') or lint.graph.kind(ref) != IC
                or not (lint.graph.role_kind(ref) == 'isolator' or ISOLATOR_IDENTITY_RE.search(identity))):
            continue
        sides = {}
        for node in _nodes(lint, ref):
            match = ISOLATOR_GROUND_PIN_RE.match(str(lint.pinname.get(node, '')).strip())
            if match:
                sides.setdefault(match.group(1).upper(), set()).add(lint.pin2net.get(node))
        if len(sides) != 2:
            continue
        one, other = (sorted(nets) for _, nets in sorted(sides.items()))
        if set(one) & set(other):
            bridged = f'同在网 {sorted(set(one) & set(other))[0]}'
        else:
            links = [link for a in one for b in other
                     for link in lint.graph.between(a, b, {RESISTOR, FERRITE, INDUCTOR})
                     if lint.graph.kind(link) != RESISTOR
                     or (parse_resistor(lint.parts[link].get('value')) or {'kohm': 1})['kohm'] <= CAN_SHORT_KOHM]
            if not links:
                continue
            bridged = f'{one[0]}/{other[0]} 之间被 {",".join(sorted(links))} 连通'
        lint.add('PRO-A05', '隔离器两侧地被合并',
                 f'{ref}: 两侧地脚{bridged}，隔离被直流旁路（G04-040；TI SLLA284G §1）；'
                 '确无隔离需求时写明用途后关闭，工作资格归 PRO-C03', ref, kind='CANDIDATE')


def _passive_crystals(lint):
    """[(位号, 两端网)]：已装配、恰有两个非地网且都不是电源轨的晶体；有源振荡器有供电脚，不在内。"""
    found = []
    for ref, part in sorted(lint.parts.items()):
        if part.get('nc') or lint.graph.kind(ref) != CRYSTAL:
            continue
        nets = sorted({net for net in lint.graph.nets_of(ref) if not is_ground(net) and net not in lint.pseudo})
        if len(nets) == 2 and not any(_named_rail(net) for net in nets):
            found.append((ref, nets))
    return found


def crystal_load(lint):
    """CLK-A01：两端负载电容的串联等效远超任何晶体规定的 CL（G04-078）。"""
    for ref, nets in _passive_crystals(lint):
        sides = [_caps_to_ground(lint, net) for net in nets]
        if not all(sides) or not all(farads for side in sides for _, farads in side):
            continue
        one, other = (sum(farads for _, farads in side) for side in sides)
        load = one * other / (one + other)
        if load > CRYSTAL_LOAD_MAX_F:
            refs = ','.join(capacitor for side in sides for capacitor, _ in side)
            lint.add('CLK-A01', '晶体负载电容远超 CL',
                     f'{ref}: 负载电容 {refs} 串联等效 {load * 1e12:g}pF > 100pF（CL=C1·C2/(C1+C2)+Cs，G04-078；ST AN2867 §3.3）；'
                     '按晶体准确料号的 CL 核，起振与频偏归 CLK-C01', ref, kind='CANDIDATE')


def crystal_shared(lint):
    """CLK-A02：晶体两端都接到两颗以上 IC 的振荡脚（G04-082）。"""
    for ref, nets in _passive_crystals(lint):
        on_both = []
        for ic in sorted(lint.parts):
            if lint.parts[ic].get('nc') or lint.graph.kind(ic) != IC:
                continue
            reached = {lint.pin2net.get(node) for node in _nodes(lint, ic)
                       if OSCILLATOR_PIN_RE.search(str(lint.pinname.get(node, '')).strip())}
            if set(nets) <= reached:
                on_both.append(ic)
        if len(on_both) >= 2:
            lint.add('CLK-A02', '一颗晶体接两个振荡器',
                     f'{ref}: 两端 {nets[0]}/{nets[1]} 都接 {",".join(on_both)} 的振荡脚，一颗无源晶体只能接一个振荡器'
                     '（G04-082；TI SNLA387 Clock Source）；多器件共用时钟用有源振荡器或缓冲', ref)


def ldo_output_capacitor(lint):
    """PWR-A07：线性稳压器的输出网上没有接地电容，经磁珠或电感也到不了（G03-003）。"""
    for ref, part in sorted(lint.parts.items()):
        identity = ' '.join(str(part.get(key, '')) for key in ('part', 'value', 'prim'))
        if part.get('nc') or lint.graph.kind(ref) != IC or not LDO_IDENTITY_RE.search(identity):
            continue
        for node in _nodes(lint, ref):
            net = lint.pin2net.get(node)
            if (not REGULATOR_OUT_PIN_RE.match(str(lint.pinname.get(node, '')).strip()) or net in lint.pseudo
                    or len(lint.nets.get(net, [])) < 2):
                continue
            if not any(_caps_to_ground(lint, reached)
                       for reached in lint.graph.series_path(net, {FERRITE, INDUCTOR}, max_hops=2)):
                lint.add('PWR-A07', 'LDO 输出无电容',
                         f'{ref}: 输出脚 {node} 所在网 {net} 上没有接地的已装配电容（G03-003；TI SLVA115A）；'
                         '稳定性依赖输出电容，手册明确不要求时可关闭，容量与 ESR 归 PWR-C04', ref, kind='CANDIDATE')


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
    i2c_pullup_window(lint)
    usb_vbus_bulk(lint)
    ldo_output_capacitor(lint)
    can_bus_short(lint)
    isolator_ground_bridge(lint)
    crystal_load(lint)
    crystal_shared(lint)
    floating_inputs(lint)

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


# boards-merge7 F11: exact-identity ratings the PRO-E02 line compares through a series resistor. Only parts whose
# datasheet was read are listed; any other part keeps the line without numbers.
#   (identity regex, clamp voltage VCL max [V], at IPP [A], waveform, citation)
CLAMP_RATINGS = (
    (r'SMAJ30C?A(?:-TR)?', 48.4, 8.3, '10/1000 µs', 'ST SMAJ DS1251 Rev 15 p2 Table 2'),
    (r'SMAJ33C?A(?:-TR)?', 53.3, 7.5, '10/1000 µs', 'ST SMAJ DS1251 Rev 15 p2 Table 2'),
)
#   (identity regex, pin-name regex, absolute maximum [V], input current limit max [A] or None, citation)
PIN_LIMITS = (
    (r'SN65HVS883(?:PWPR?)?', r'IP\d', 36.0, 4e-3,
     'TI SLASEE6 p4 §6.1 VIPx max 36 V; p5 §6.5 IIP-LIM max 4 mA (10 V < VIPx < 34 V, RLIM 25 kΩ)'),
    (r'SN65HVS883(?:PWPR?)?', r'V24', 36.0, None, 'TI SLASEE6 p4 §6.1 V24 max 36 V'),
)


# 2026-11-04 (SR 不足 4.2): datasheet points of the clamps the initial-calculation table uses. Each part: stand-off
# VRWM, breakdown (min, max), rated points (waveform, IPP [A], VC max [V]); a linear clamp VC(I) = VBR max + Rd·I with Rd
# from the shortest-waveform point is the estimate the table extrapolates with.
CLAMP_DATA = (
    (r'30KPA28C?A', 28.0, (31.28, 34.41), (('10/1000 µs', 606.0, 50.0),),
     'Littelfuse 30KPA Rev GD 2026-06-10 p2 电气特性表'),
    (r'SMBJ15C?A', 15.0, (16.7, 18.5), (('10/1000 µs', 24.6, 24.4),), 'Vishay SMBJ 88392 2024-01-09 p2'),
    (r'SMBJ28C?A', 28.0, (31.1, 34.4), (('10/1000 µs', 13.2, 45.4),), 'Vishay SMBJ 88392 2024-01-09 p2'),
    (r'SMBJ58C?A', 58.0, (64.4, 71.2), (('10/1000 µs', 6.4, 93.6),), 'Vishay SMBJ 88392 2024-01-09 p2'),
    (r'SM15T33C?A', 28.2, (31.4, 34.7), (('10/1000 µs', 33.0, 45.7), ('8/20 µs', 169.0, 59.0)),
     'ST SM15T DS0683 Rev 8 p3 Table 2'),
    (r'TVS3300\w*', 33.0, (34.0, 39.0), (('8/20 µs', 35.0, 40.0),),
     'TI TVS3300 SLVSDO2C p5 §7.1 IPP 35 A（8/20 µs）；p6 §7.5 VBR、VCLAMP'),
)
# Voltage-only absolute maxima of IC pins the initial-calculation table compares (no input-current clause).
PIN_MAXIMA = (
    (r'TPS2663[0-7]\w*', r'IN_SYS|IN|OUT|PGTH', 67.0, 'TI TPS2663x SLVSE94G p5 §7.1 IN_SYS/IN/OUT 67 V'),
    (r'TPS25981\w*', r'IN|OUT', 20.0, 'TI TPS25981x SLVSGG6D p6 §7.1 IN 20 V，OUT ≤ VIN + 0.3 V'),
    (r'LTC4359\w*(?:#\w+)?', r'IN|SOURCE|SHDN', 100.0, 'ADI LTC4359 Rev F p2 IN、SOURCE、SHDN 100 V'),
    (r'LM5069\w*(?:-\d)?', r'VIN|OUT|SENSE|PGD', 100.0, 'TI LM5069 SNVS452G p4 §6.1 VIN/OUT 100 V'),
    (r'LM70880\w*', r'VIN\d*', 87.5, 'TI LM70880-Q1 SNVSBX7A p5 §6.1 VIN 87.5 V'),
    (r'LMR6043\w*', r'VIN', 42.0, 'TI LMR60430-Q1 SNAS875B p5 §6.1 VIN 42 V'),
)
# IEC 61000-4-5 / GB/T 17626.5 combination-wave effective source impedance: line–line 2 Ω, line–earth 12 Ω.
SURGE_IMPEDANCE = ((r'差模|线.?线|line.?(?:to.?)?line|differential|\bDM\b', 2.0), (r'共模|线.?地|line.?(?:to.?)?(?:earth|ground)|common|\bCM\b', 12.0))
EXPOSURES = {'in_box': '箱内', 'via_box_connector': '经航插出箱', 'exposed': '直接暴露'}


def clamp_data(part):
    identities = [str(part.get(k) or '') for k in ('part', 'value')]
    return next((row for row in CLAMP_DATA if any(re.fullmatch(row[0], i, re.I) for i in identities)), None)


def pin_maximum(part, pin_names):
    identities = [str(part.get(k) or '') for k in ('part', 'value')]
    for row in PIN_MAXIMA:
        if any(re.fullmatch(row[0], i, re.I) for i in identities) and any(re.fullmatch(row[1], n or '', re.I) for n in pin_names):
            return row[2], row[3]
    return None


def surge_cases(intent):
    """[(requirement id, condition, open-circuit volts, source ohms)] from CONFIRMED surge_voltage parameters."""
    cases = []
    for req in (intent or {}).get('requirements') or []:
        if req.get('status', 'CONFIRMED') != 'CONFIRMED':
            continue
        for p in req.get('parameters') or []:
            if p.get('name') != 'surge_voltage':
                continue
            scale = {'V': 1.0, 'kV': 1e3, 'mV': 1e-3}.get(p.get('unit'))
            peak = max((abs(p[k]) for k in ('min', 'max', 'value') if isinstance(p.get(k), (int, float))), default=None)
            if not scale or not peak:
                continue
            text = str(p.get('condition') or '')
            ohm = next((z for pattern, z in SURGE_IMPEDANCE if re.search(pattern, text, re.I)), None)
            cases.append((req.get('id', '?'), text or '未写耦合方式', peak * scale, ohm))
    return cases


def exposure_text(ports, exposures, cases):
    """Which surge reaches the clamp by the declared port exposure (SR 不足 4.1): (words, out-of-box cases,
    undeclared ports). An undeclared port keeps the original wording and is named for a human decision."""
    words, out, undeclared = [], [], []
    for port in ports:
        level = exposures.get(port)
        if level is None:
            undeclared.append(port)
        elif level == 'in_box':
            words.append('%s 声明箱内：外部浪涌需求不到达，按板内互连能到达的瞬态' % port)
        elif not cases:
            words.append('%s 声明%s，需求没有浪涌参数（surge_voltage），记需求缺口' % (port, EXPOSURES[level]))
        else:
            for rid, cond, voc, ohm in cases:
                out.append((port, level, rid, cond, voc, ohm))
                words.append('%s 声明%s：%s %s %g V，源阻抗 %s' % (
                    port, EXPOSURES[level], rid, cond, voc, '%g Ω' % ohm if ohm is not None else '未写耦合方式，按 2 Ω'))
    if undeclared:
        words.append('需人判：端口暴露等级（intent.interfaces 未声明 %s，按需求波形取）' % '、'.join(undeclared))
    return ('；'.join(words) + '；') if words else '', out, undeclared


def initial_table(data, net_max, pins, out_cases):
    """The initial-calculation words of one tabled clamp (SR 不足 4.2): working voltage, rated point against the
    lowest protected-pin maximum, and per out-of-box surge case the current and clamp voltage on the linear model.
    A table for the reviewer to check, never a verdict."""
    _, vrwm, (vbr_lo, vbr_hi), points, cite = data
    out = []
    if net_max:
        v, how = net_max
        out.append('VRWM %g V 对该网持续最高 %g V（%s）%s' % (vrwm, v, how, '' if vrwm >= v else '：低于，正常工作即导通'))
    else:
        out.append('VRWM %g V，该网持续最高电压未声明' % vrwm)
    lowest = min(pins, key=lambda x: x[1]) if pins else None
    wave, ipp, vcl = sorted(points, key=lambda x: x[1])[-1]
    rd = (vcl - vbr_hi) / ipp
    rated = 'VBR %g–%g V，VC %g V @ IPP %g A（%s）' % (vbr_lo, vbr_hi, vcl, ipp, wave)
    if lowest:
        rated += ' 对 %s 绝限 %g V%s' % (lowest[0], lowest[1], '：已超' if vcl > lowest[1] else '')
    out.append(rated)
    for port, level, rid, cond, voc, ohm in out_cases:
        z = ohm if ohm is not None else 2.0
        i = max(voc - vbr_hi, 0.0) / (z + rd)
        vc = vbr_hi + rd * i
        text = '%s %g V / %g Ω：IPP 约 %.0f A，钳位约 %.1f V（线性外推）' % (rid, voc, z, i, vc)
        if i > ipp:
            text += '，超过 %s 额定 %g A%s' % (wave, ipp, '（手册只给 10/1000 µs，8/20 µs 允许值读脉宽曲线）'
                                              if wave.startswith('10/1000') else '')
        if lowest and vc > lowest[1]:
            text += '，高于 %s 绝限 %g V' % (lowest[0], lowest[1])
        out.append(text)
    return '初算（%s）：%s；' % (cite, '；'.join(out))


def clamp_rating(part):
    """(VCL max, IPP, waveform, citation) of an exactly tabled clamp, else None."""
    identities = [str(part.get(k) or '') for k in ('part', 'value')]
    return next((rule[1:] for rule in CLAMP_RATINGS if any(re.fullmatch(rule[0], i, re.I) for i in identities)), None)


def pin_limit(part, pin_name):
    """(absolute maximum, input current limit or None, citation) of an exactly tabled IC pin, else None."""
    identities = [str(part.get(k) or '') for k in ('part', 'value')]
    return next((rule[2:] for rule in PIN_LIMITS if any(re.fullmatch(rule[0], i, re.I) for i in identities)
                 and re.fullmatch(rule[1], str(pin_name or ''), re.I)), None)


def drop_check(clamp_v, ohm, limit):
    """The resistor-drop comparison of one protected pin, in words: the clamp voltage less what the series resistor
    drops at the pin's guaranteed input current limit, against the pin's absolute maximum. Series diodes are not
    credited (their drop only helps). A word for the reviewer, never a verdict."""
    vmax, ilim, _ = limit
    over = clamp_v - vmax
    if over <= 0:
        return '钳位不高于脚绝限'
    text = '钳位高出脚绝限 %.1f V，需注入 ≥ %.1f mA 才在电阻上降掉' % (over, over / ohm * 1e3) if ohm else '钳位高出脚绝限 %.1f V' % over
    if ilim and ohm:
        pin_v = clamp_v - ilim * ohm
        text += '；手册输入限流 ≤ %.0f mA 时电阻压降 ≤ %.1f V，脚电压约 %.1f V%s' % (
            ilim * 1e3, ilim * ohm, pin_v, '，仍高于绝限' if pin_v > vmax else '，不高于绝限')
    return text


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

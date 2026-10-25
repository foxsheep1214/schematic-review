#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用阻容应力预判检查器（DEV-C01 逐颗行）。

对已装配的两端片式电阻与贴片 MLCC，用 intent.power_rails 声明的轨压窗口给两端电压定保守上界，
按 references/commodity-floors.md 的最弱档表与可订购档表给出建议结论。只在上界能算出且明显满足时
建议 PASS；否则只给计算事实，不给建议，由审查者判定。审查者把建议 PASS 改判为 FAIL/INSUFFICIENT 时，
须给出 OVERRIDE_CODES 中的理由（validate_review 校验），“采购范围/料号未定”不是改判理由——
该项由 DEV-D04 汇总。建议不替代审查：脉冲、精密检流、安规等用途仍由审查者按改判码排除。
"""
import re

from decoupling import parse_capacitance
from solve_dividers import parse_resistor, parse_resistor_noted

from . import inventory as inv
from . import netgraph as ng
import part_words as pw
from .base import Checker

# commodity-floors「片式电阻」表：封装 -> (70 ℃ 最弱档功率 W, 最弱档最高工作电压 V)
RESISTOR_FLOORS = {
    '0201': (0.05, 15.0), '0402': (1 / 16, 25.0), '0603': (1 / 16, 50.0), '0805': (0.1, 100.0),
    '1206': (0.125, 150.0), '1210': (0.25, 200.0), '2010': (0.5, 200.0), '2512': (1.0, 200.0),
}
# 采购范围未受控时的边界：功率 ≤ 最弱档 50%、电压 ≤ 50% 判 PASS。功率超过 25%（RG1005 0.032 W 反例的 50%）时，
# 封装最弱档不足以覆盖全部可采购档，PASS 附带“额定 ≥ 2×应力”的采购约束，由 DEV-D04 汇总，不记证据不足。
POWER_LIMIT, VOLTAGE_LIMIT, CATEGORY_SAFE_POWER = 0.5, 0.5, 0.25
DEFAULT_TOL = 0.05
# commodity-floors「陶瓷电容」可订购档：(封装, 最大容值 F, 耐压 V, 依据料号)。
# 同封装同耐压下更小容值视为同样可订购。
MLCC_ORDERABLE = (
    ('0402', 100e-9, 50.0, 'Murata GRM155R71H104KE14'),
    ('0402', 1e-6, 25.0, 'Murata GRM155R61E105KA12'),
    ('0402', 10e-6, 10.0, 'Murata GRM155R61A106ME11'),
    ('0603', 10e-6, 25.0, 'Murata GRM188R61E106MA73'),
    ('0805', 22e-6, 25.0, 'Murata GRM21BR61E226ME44'),
)
OVERRIDE_CODES = {
    'NON_COMMODITY_USE': '脉冲/浪涌、精密检流、安规/隔离或功能依赖额定以外的参数',
    'STRESS_ABOVE_BOUND': '有证据表明实际应力超出预判上界（外部/故障/瞬态电压或未建模的源）',
    'SELECTED_PART_RATING': 'BOM 已给具体料号，其手册额定低于预判所用档位',
    'TEMPERATURE_ABOVE_ASSUMPTION': '环境或局部温度超出预判假设',
}
CRITERION = ('按 intent.power_rails 声明的轨压给两端电压定上界，对照 commodity-floors 最弱档/可订购档；'
             '建议 PASS 时改判须给 proposal_override（封闭理由码），采购字段未定由 DEV-D04 汇总，不作改判理由')
PIN_CRITERION = ('源轨最高电压经串联电阻最小阻值流入该 IC 脚的电流不超过手册对该脚的电流上限（放电、泄放、启动、检测等经电阻'
                 '接到高于本 IC 最低供电的轨的脚），该脚电压在手册绝对最大额定内，串联电阻承受的功耗与脉冲在额定内')
# A schematic without footprints (drawn before the PCB) has no package; the smallest package commonly used in power
# and control boards bounds it, and a rating written in the value replaces the package floor.
ASSUMED_PACKAGE = '0402'
WRITTEN_V_RE = re.compile(r'^(\d+(?:\.\d+)?)\s*V$', re.I)
WRITTEN_W_RE = re.compile(r'^(\d+(?:\.\d+)?)\s*W$', re.I)
PACKAGE_RE = re.compile(r'^(Resistor|Capacitor)_SMD:[RC]_(0201|0402|0603|0805|1206|1210|2010|2512)_', re.I)
# 电荷泵、自举、开关、高边驱动等节点可超出所接器件的供电轨。
UNBOUNDED_PIN_RE = re.compile(
    r'^(SW\d*|LX\d*|PH\d*|VSW|SWITCH|BOOT\w*|BST\w*|VCP|CP\w*|VGH|VBOOST|HO|HG|GH\w*|HB|HS)$', re.I)
LINK_KINDS = {pw.RESISTOR, pw.CAPACITOR, pw.FERRITE, pw.DIODE, pw.ZENER, pw.TVS,
              pw.JUMPER, pw.FUSE, pw.SWITCH, pw.CRYSTAL, pw.TESTPOINT}
POWER_PINTYPES = {'power_in', 'power_out'}
# 分类器未识别、但两脚且不升压的 LED/热敏电阻：只作定界连通件，本身不生成预判行。
TWO_TERMINAL_LINK_RE = re.compile(r'^(LED|TH|NTC|RT)\d', re.I)


def _package(part, prefix):
    match = PACKAGE_RE.match(str(part.get('jedec') or ''))
    return match.group(2) if match and match.group(1)[0].upper() == prefix else None


# 隔离电源常见的分域地/回流网：PORT_GND、P_GND、SR_RETURN、GND_ISO。只在本预判里当 0 V，
# 并按名字各成一个参考地分区；跨域（Y 电容、隔离电阻）的两端件不给上界。
GROUND_TOKENS = {'GND', 'PGND', 'AGND', 'DGND', 'SGND', 'EGND', 'RTN', 'RETURN'}


def ground_name(net):
    """地或回流网的名字：GND 族、以 RTN/RETURN 结尾、或 GND_<域>；domains 与本预判共用。"""
    tokens = pw.normalize(net).split('_')
    return ng.is_ground(net) or tokens[-1] in GROUND_TOKENS or (len(tokens) == 2 and tokens[0] in GROUND_TOKENS)


_ground_name = ground_name


def _declared_rails(intent):
    """{net: ((min, max), domain)}；domain 取 power_rails.<net>.domain，未声明为 None。"""
    rails = {}
    for net, rail in ((intent or {}).get('power_rails') or {}).items():
        window = rail.get('voltage_v') if isinstance(rail, dict) else None
        if isinstance(window, dict) and all(isinstance(window.get(k), (int, float)) for k in ('min', 'max')):
            domain = rail.get('domain') if isinstance(rail.get('domain'), str) and rail['domain'].strip() else None
            rails[net] = ((float(window['min']), float(window['max'])), domain)
    return rails


class _Bounds:
    """网的电压窗口上界：地、声明轨，或经无源件连通的同一簇内最高声明供电。"""

    def __init__(self, graph, rails):
        self.graph, self.rails = graph, rails
        self._cluster, self._ic = {}, {}

    def _fixed(self, net):
        if net in self.rails:
            return self.rails[net][0]
        if _ground_name(net):
            return (0.0, 0.0)
        return None

    def domain(self, net):
        """参考地分区：声明的 domain 优先；GND/AGND 等通用地名同属 GND 域，其余地名（P_GND、PORT_GND）
        各成一域；其他为 None（不参与跨域判断）。"""
        if net in self.rails:
            declared = self.rails[net][1]
            if declared or self.rails[net][0] != (0.0, 0.0):
                return declared
        if ng.is_ground(net):
            return 'GND'          # 通用地名沿用旧行为：视为同一参考
        return pw.normalize(net) if _ground_name(net) else None

    def ic_supply(self, ref):
        if ref not in self._ic:
            graph, top = self.graph, None
            for pin, net in graph.pins_of(ref).items():
                fixed = self._fixed(net)
                if fixed is not None:
                    top = fixed[1] if top is None else max(top, fixed[1])
                elif graph.pintype.get(ref + '.' + pin) in POWER_PINTYPES or ng.is_rail(net):
                    top = 'power_rails.%s.voltage_v' % net
                    break
            self._ic[ref] = top
        return self._ic[ref]

    def window(self, net):
        """返回 ((lo, hi), 依据, 参考地分区集合) 或 (None, 缺口, 参考地分区集合)。"""
        fixed = self._fixed(net)
        if fixed is not None:
            domain = self.domain(net)
            return fixed, ('ground' if net not in self.rails else 'declared-rail:' + net), {domain} - {None}
        if net in self._cluster:
            return self._cluster[net]
        graph = self.graph
        seen, queue, tops, ac, gap, domains = {net}, [net], [], False, None, set()
        while queue and gap is None:
            current = queue.pop()
            if current in graph.pseudo or not current:
                gap = 'unconnected-net'
                break
            for node in graph.nodes_on(current):
                ref, _, pin = node.partition('.')
                if not graph.is_fitted(ref):
                    continue
                kind = graph.kind(ref)
                if kind == pw.UNKNOWN and TWO_TERMINAL_LINK_RE.match(ref) and len(graph.pins_of(ref)) == 2:
                    kind = pw.RESISTOR
                if pw.name_matches(UNBOUNDED_PIN_RE, graph.pinname.get(node), pin):
                    gap = 'unbounded-pin:' + node
                    break
                if kind == pw.IC:
                    supply = self.ic_supply(ref)
                    if supply is None or isinstance(supply, str):
                        gap = 'undeclared-supply:%s(%s)' % (ref, supply or 'no-declared-rail')
                        break
                    tops.append(supply)
                    domains |= {self.domain(n) for n in graph.pins_of(ref).values()
                                if self._fixed(n) is not None} - {None}
                elif kind in LINK_KINDS:
                    for other in graph.nets_of(ref):
                        if other == current or other in seen:
                            continue
                        fixed = self._fixed(other)
                        if fixed is not None:
                            tops.append(fixed[1])
                            domains |= {self.domain(other)} - {None}
                            continue
                        ac = ac or kind == pw.CAPACITOR
                        seen.add(other)
                        queue.append(other)
                else:
                    gap = 'unbounded-%s:%s' % (kind, ref)
                    break
        if gap is None and not tops:
            gap = 'no-declared-source'
        if gap is None:
            hi = max(tops)
            result = ((-hi if ac else 0.0, hi), 'cluster-of-declared-supplies', domains)
        else:
            result = (None, gap, domains)
        for item in seen:
            self._cluster[item] = self._clamped(item, result)
        return self._cluster[net]

    def _clamped(self, net, result):
        """A net with a zener or TVS straight to a fixed node (ground or a declared rail) is bounded by that clamp
        when it reads lower than the cluster's supply (R6 acceptance 2026-10-24, user: a); the clamp value is read
        off the part text, a pin's internal clamp inside an IC is not one, and an unreadable clamp changes nothing."""
        window, basis, domains = result
        if window is None:
            return result
        clamps = []
        for node in self.graph.nodes_on(net):
            ref = node.partition('.')[0]
            if self.graph.kind(ref) not in (pw.ZENER, pw.TVS) or not self.graph.is_fitted(ref):
                continue
            others = [n for n in self.graph.nets_of(ref) if n != net]
            fixed = self._fixed(others[0]) if len(others) == 1 else None
            part = self.graph.parts.get(ref) or {}
            volts = ng.clamp_voltage(' '.join(str(part.get(k) or '') for k in ('part', 'value', 'prim')))
            if fixed is not None and volts is not None:
                clamps.append((fixed[1] + volts, ref))
        if not clamps:
            return result
        top, ref = min(clamps)
        if top >= window[1]:
            return result
        return ((max(window[0], -top), top), 'clamped-by:%s (%s)' % (ref, basis), domains)


def _signal_series(graph, nets):
    """一端只接连接器触点、另一端接 IC 非电源脚的串阻（USB/高速线串阻）。"""
    def ends(net):
        found = set()
        for node in graph.nodes_on(net):
            ref = node.partition('.')[0]
            kind = graph.kind(ref) if graph.is_fitted(ref) else None
            if kind == pw.CONNECTOR:
                found.add('connector')
            elif kind == pw.IC and graph.pintype.get(node) not in POWER_PINTYPES:
                found.add('ic-signal')
        return frozenset(found)
    if any(ng.is_rail(net) for net in nets):
        return False
    a, b = (ends(net) for net in nets)
    return {a, b} == {frozenset({'connector'}), frozenset({'ic-signal'})}


def _supply_nets(graph, ref, pins):
    """该 IC 的供电网：官方脚表的 power 脚所在网；没有脚表时取符号的电源输入脚。"""
    if pins:
        return {graph.pin2net.get(ref + '.' + n) for n, spec in pins.items()
                if isinstance(spec, dict) and spec.get('role') == 'power'} - {None}
    return {net for pin, net in graph.pins_of(ref).items() if graph.pintype.get(ref + '.' + pin) == 'power_in'}


def _pin_feeds(db, intent, state):
    """经串联电阻接到高于本 IC 最低供电的声明轨的 IC 脚（fixed requirements 补加行的缺口：逐脚核脚电流）。

    脚不是 power/return 脚，所在网只有这一个脚、串联电阻和电容，没有电阻到地（分压另按窗口核），至少一颗电阻的
    另一端是声明了窗口的轨，且该轨上限高于本 IC 各供电网中最低的上限。"""
    graph = ng.NetGraph(db, fitted=set(state['fitted']))
    rails = _declared_rails(intent)
    devices = (intent or {}).get('devices') or {}
    found = []
    for ref in sorted(graph.fitted):
        if graph.kind(ref) != pw.IC:
            continue
        pins = (devices.get(ref) or {}).get('pins') if isinstance(devices.get(ref), dict) else None
        supplies = [rails[net][0][1] for net in _supply_nets(graph, ref, pins) if net in rails]
        if not supplies:
            continue
        lowest = min(supplies)
        for pin, net in sorted(graph.pins_of(ref).items()):
            node = ref + '.' + pin
            role = ((pins or {}).get(pin) or {}).get('role') if isinstance((pins or {}).get(pin), dict) else None
            if (role in ('power', 'return') or graph.pintype.get(node) in POWER_PINTYPES or not net
                    or net in rails or _ground_name(net) or net in graph.pseudo):
                continue
            others = [n for n in graph.nodes_on(net) if n != node and graph.is_fitted(n.partition('.')[0])]
            kinds = {n: graph.kind(n.partition('.')[0]) for n in others}
            if not others or any(k not in (pw.RESISTOR, pw.CAPACITOR) for k in kinds.values()):
                continue
            feeds, divider = [], False
            for other, kind in sorted(kinds.items()):
                resistor = other.partition('.')[0]
                far = [n for n in graph.nets_of(resistor) if n != net] if kind == pw.RESISTOR else []
                if len(far) != 1:
                    continue
                if _ground_name(far[0]):
                    divider = True
                elif far[0] in rails and rails[far[0]][0][1] > lowest:
                    feeds.append((resistor, far[0]))
            if feeds and not divider:
                found.append({'ref': ref, 'node': node, 'net': net, 'lowest_supply_max_v': lowest,
                              'feeds': [{'ref': r, 'net': n, 'source_max_v': rails[n][0][1],
                                         'value': graph.parts.get(r, {}).get('value')} for r, n in feeds]})
    return found


def _pin_calculation(entry):
    feeds = []
    for feed in entry['feeds']:
        parsed = parse_resistor_noted(feed['value'], default_tol=DEFAULT_TOL)
        r_min = round(parsed['kohm'] * 1000 * (1 - parsed['tol']), 6) if parsed else None
        feeds.append({'ref': feed['ref'], 'net': feed['net'], 'source_max_v': feed['source_max_v'], 'r_min_ohm': r_min,
                      'i_max_a': round(feed['source_max_v'] / r_min, 9) if r_min else None})
    return {'feeds': feeds, 'lowest_supply_max_v': entry['lowest_supply_max_v']}


def _uncomputed_feeds(generated):
    """Feed resistors of a pin row whose current the tool could not compute (value unreadable)."""
    calc = ((generated or {}).get('proposal') or {}).get('calculation') or {}
    return [f['ref'] for f in calc.get('feeds') or [] if f.get('i_max_a') is None]


def _series_chains(graph, bounds):
    """Pure series resistor strings between two fixed nets (a declared rail or ground): {ref: (bound V, basis)} for
    each resistor, and {net: (lo, hi)} for each filtered tap (a node with a capacitor to ground).

    A tap carries only the two string resistors, capacitors to ground and IC input pins (their current neglected);
    anything else on a tap leaves the string to the cluster bound. Between taps the resistors divide the voltage
    across the segment; a capacitor-held tap stays within its divider ratio of the end windows (an RC ladder with
    grounded capacitors never overshoots its DC gain), so a segment spans at most the difference of its ends' ranges."""
    native = graph.db.get('native_pintype') or {}

    def ohms(ref):
        parsed = parse_resistor_noted(graph.parts.get(ref, {}).get('value'), default_tol=DEFAULT_TOL)
        if not parsed or parsed['kohm'] <= 0:
            return None
        r = parsed['kohm'] * 1000
        return r * (1 - parsed['tol']), r * (1 + parsed['tol'])

    def step(net, came):
        """(next resistor, held by a capacitor) leaving tap `net`; None when the tap is not pure."""
        nxt, held = [], False
        for node in graph.nodes_on(net):
            ref = node.partition('.')[0]
            if ref == came or not graph.is_fitted(ref):
                continue
            kind = graph.kind(ref)
            if kind == pw.RESISTOR and len(graph.pins_of(ref)) == 2:
                nxt.append(ref)
            elif kind == pw.CAPACITOR and len(graph.pins_of(ref)) == 2 and all(
                    bounds._fixed(n) == (0.0, 0.0) for n in graph.nets_of(ref) if n != net):
                held = True
            elif not (kind == pw.IC and native.get(node) == 'input'):
                return None
        return (nxt[0], held) if len(nxt) == 1 else None

    bounds_by_ref, taps, done = {}, {}, set()
    for ref in sorted(graph.fitted):
        if ref in done or graph.kind(ref) != pw.RESISTOR or len(graph.nets_of(ref)) != 2:
            continue
        a, b = graph.nets_of(ref)
        sides = []
        for start in (a, b):   # walk from ref through each end to a fixed net
            nets, refs, held, net, came = [], [], [], start, ref
            while bounds._fixed(net) is None and net not in nets:
                found = step(net, came) if net not in graph.pseudo else None
                if found is None:
                    break
                came, is_held = found
                nets.append(net); held.append(is_held); refs.append(came)
                others = [n for n in graph.nets_of(came) if n != net]
                if len(others) != 1:
                    break
                net = others[0]
            sides.append((nets, refs, held, net))
        (na, ra, ha, end_a), (nb, rb, hb, end_b) = sides
        if bounds._fixed(end_a) is None or bounds._fixed(end_b) is None or end_a == end_b:
            continue
        chain_refs = list(reversed(ra)) + [ref] + rb      # from end_a to end_b
        chain_nets = [end_a] + list(reversed(na)) + nb + [end_b]
        chain_held = [True] + list(reversed(ha)) + hb + [True]   # the ends are anchors too
        values = [ohms(r) for r in chain_refs]
        if None in values or len(set(chain_refs)) != len(chain_refs):
            continue
        done |= set(chain_refs)
        (lo_a, hi_a), (lo_b, hi_b) = bounds._fixed(end_a), bounds._fixed(end_b)
        ranges = {0: (lo_a, hi_a), len(chain_nets) - 1: (lo_b, hi_b)}
        for j in range(1, len(chain_nets) - 1):
            if not chain_held[j]:
                continue
            before, after = values[:j], values[j:]
            # v_j = g·v_a + (1 - g)·v_b with g the share of the string after the tap, over the tolerances
            gains = (sum(v[0] for v in after) / (sum(v[0] for v in after) + sum(v[1] for v in before)),
                     sum(v[1] for v in after) / (sum(v[1] for v in after) + sum(v[0] for v in before)))
            corners = [g * va + (1 - g) * vb for g in gains for va, vb in ((lo_a, lo_b), (hi_a, hi_b))]
            ranges[j] = (min(corners), max(corners))
            taps[chain_nets[j]] = ranges[j]
        anchors = sorted(ranges)
        basis = 'series-chain:' + '+'.join(chain_refs if hi_a >= hi_b else reversed(chain_refs))   # from the rail
        for p, q in zip(anchors, anchors[1:]):
            span = max(ranges[p][1] - ranges[q][0], ranges[q][1] - ranges[p][0])
            segment = list(range(p, q))   # resistors chain_refs[p..q-1] sit between nets p and q
            for i in segment:
                rest = sum(values[k][0] for k in segment if k != i)
                bounds_by_ref[chain_refs[i]] = (round(span * values[i][1] / (values[i][1] + rest), 6), basis)
    return bounds_by_ref, taps


def _scan(db, intent, state):
    graph = ng.NetGraph(db, fitted=set(state['fitted']))
    bounds = _Bounds(graph, _declared_rails(intent))
    chains, taps = _series_chains(graph, bounds)
    parts = []
    for ref in sorted(graph.fitted):
        part, kind = graph.parts.get(ref, {}), graph.kind(ref)
        prefix = {pw.RESISTOR: 'R', pw.CAPACITOR: 'C'}.get(kind)
        package = _package(part, prefix) if prefix else None
        assumed = bool(prefix and not package and not str(part.get('jedec') or '').strip()
                       and not identified(db, ref))
        if assumed:   # no footprint at all (a schematic before the PCB): the smallest common package bounds it
            package = ASSUMED_PACKAGE
        pins = graph.pins_of(ref)
        if not package or len(pins) != 2:
            continue
        entry = {'ref': ref, 'kind': kind, 'package': package, 'value': part.get('value'),
                 'nets': sorted(pins.values())}
        if assumed:
            entry['package_assumed'] = True
        written = bom_ratings(((db.get('bom') or {}).get('parts') or {}).get(ref))
        if written:
            entry['bom_ratings'] = written
        if kind == pw.RESISTOR and not any(_ground_name(net) for net in entry['nets']):
            entry['signal_series'] = _signal_series(graph, entry['nets'])
        windows, domains = [], set()
        for net in entry['nets']:
            window, basis, found = bounds.window(net)
            windows.append(window)
            domains |= found
            entry.setdefault('bases', []).append(basis)
        if len(domains) > 1:
            entry['bases'].append('cross-domain:' + '|'.join(sorted(domains)))
        elif None not in windows:
            (lo_a, hi_a), (lo_b, hi_b) = windows
            entry['v_across_max'] = round(max(hi_a - lo_b, hi_b - lo_a), 6)
            # a resistor of a series string shares the string's voltage; a capacitor on a filtered tap sees the tap
            shared = chains.get(ref) if kind == pw.RESISTOR else None
            tap = next((taps[n] for n in entry['nets'] if n in taps), None) if kind == pw.CAPACITOR else None
            if tap is not None and all(bounds._fixed(n) == (0.0, 0.0) for n in entry['nets'] if n not in taps):
                shared = (round(max(abs(tap[0]), abs(tap[1])), 6), 'series-chain-tap')
            if shared and shared[0] < entry['v_across_max']:
                entry['v_across_max'] = shared[0]
                entry['bases'].append(shared[1])
        parts.append(entry)
    return parts


# BOM columns that name the part, its place or its count; any other non-empty column states a specification.
IDENTITY_COLUMNS = {'mpn', 'manufacturer', 'mfr', 'mfg', 'part number', 'part_number', 'partnumber', 'footprint',
                    'package', 'datasheet', 'circuit', 'sheet', 'page', 'qty', 'quantity', 'status',
                    'selection status'}


def _bom_fields(db, ref):
    fields = ((db.get('bom') or {}).get('parts') or {}).get(ref)
    return fields if isinstance(fields, dict) else {}


def identified(db, ref):
    """A part named by a BOM part number or a datasheet link: its own datasheet rates it, not an assumed package."""
    part = (db.get('parts') or {}).get(ref) or {}
    return bool(str(part.get('datasheet') or '').strip() or any(
        str(v or '').strip() for k, v in _bom_fields(db, ref).items()
        if k.strip().lower() in ('mpn', 'part number', 'part_number', 'partnumber')))


def states_specification(db, ref):
    """The BOM row says something about the part beyond naming, placing or counting it."""
    return any(str(v or '').strip() for k, v in _bom_fields(db, ref).items()
               if k.strip().lower() not in IDENTITY_COLUMNS)


def _proposal(entry):
    """返回 (建议结论或 None, 计算, 说明)。"""
    v = entry.get('v_across_max')
    if v is None:
        note = '两端电压上界算不出：' + '；'.join(entry['bases'])
        if entry.get('signal_series'):
            note += ('。信号串阻：按 wca-formulas.md“信号串联电阻”行定界（直流 I²R 加动态 ½·C·ΔV²·N_tr），'
                     '不用跨轨 V²/R，也不只算稳态电流')
        return None, {}, note
    if entry['kind'] == pw.RESISTOR:
        parsed = parse_resistor_noted(entry['value'], default_tol=DEFAULT_TOL)
        if not parsed or parsed['kohm'] * 1000 < 1:
            return None, {'v_across_max': v}, '阻值不可解析或 <1 Ω（跳线/检流不适用最弱档表）'
        r_min = parsed['kohm'] * 1000 * (1 - parsed['tol'])
        p_floor, v_floor = RESISTOR_FLOORS[entry['package']]
        bom = entry.get('bom_ratings') or {}
        power_w, voltage_v = parsed.get('power_w') or bom.get('power_w'), parsed.get('voltage_v') or bom.get('voltage_v')
        p_floor, v_floor = power_w or p_floor, voltage_v or v_floor   # a written rating is the floor
        calc = {'v_across_max': v, 'r_min_ohm': round(r_min, 6), 'p_max_w': round(v * v / r_min, 9),
                'p_floor_w': p_floor, 'v_floor_v': v_floor,
                'power_ratio': round(v * v / r_min / p_floor, 6), 'voltage_ratio': round(v / v_floor, 6)}
        basis = _floor_basis(entry, power_w, voltage_v)
        if basis:
            calc['floor_basis'] = basis
        ok = calc['power_ratio'] <= POWER_LIMIT and calc['voltage_ratio'] <= VOLTAGE_LIMIT
        if not ok:
            return None, calc, '超出未受控采购范围的预判边界，按 commodity-floors 判定表由审查者判定'
        note = '功率 ≤ 最弱档 %d%%、电压 ≤ %d%%' % (POWER_LIMIT * 100, VOLTAGE_LIMIT * 100)
        if calc['power_ratio'] > CATEGORY_SAFE_POWER:
            calc['procurement_min_power_w'] = round(2 * calc['p_max_w'], 9)
            note += '；采购约束：额定功率 ≥ %.4g W（应力 2 倍），记 DEV-D04' % calc['procurement_min_power_w']
        return 'PASS', calc, note
    farads = parse_capacitance(entry['value'])
    if farads is None:
        return None, {'v_across_max': v}, '容值不可解析'
    if entry.get('package_assumed'):   # no footprint: only a voltage written in the value bounds it
        written = rated_voltage(entry['value']) or (entry.get('bom_ratings') or {}).get('voltage_v')
        calc = {'v_across_max': v, 'capacitance_f': farads, 'written_v': written}
        if written is None:
            return None, calc, '没有封装也没写耐压：耐压 ≥%gV 写进 BOM 约束（DEV-D04），由审查者按 commodity-floors 判定' % v
        if v <= written:
            return 'PASS', calc, '两端电压 ≤ 值里所写耐压 %gV' % written
        return None, calc, '两端电压超过值里所写耐压 %gV，由审查者判定' % written
    tiers = [t for t in MLCC_ORDERABLE if t[0] == entry['package'] and farads <= t[1] * (1 + 1e-9)]
    best = max(tiers, key=lambda t: t[2], default=None)
    calc = {'v_across_max': v, 'capacitance_f': farads,
            'orderable_v': best[2] if best else None, 'orderable_basis': best[3] if best else None}
    if best and v <= best[2]:
        return 'PASS', calc, '所需耐压 ≥%gV 在该封装/容值可订购档内（%s %gV）；耐压约束记 DEV-D04' % (v, best[3], best[2])
    return None, calc, '可订购档表未覆盖该封装/容值/耐压，由审查者按目录判定'


def _beyond_prejudgement(result, calc):
    """A computed stress that the pre-judgement did not pass: a resistor's ratios, a capacitor's written voltage."""
    return result != 'PASS' and ('power_ratio' in calc or calc.get('written_v') is not None)


def _floor_basis(entry, power_w, voltage_v):
    """Where the rating floor came from, when not the footprint's package: the value, or the assumed package."""
    if power_w and voltage_v:
        return 'written'
    assumed = 'assumed ' + entry['package'] if entry.get('package_assumed') else 'package ' + entry['package']
    if not power_w and not voltage_v:
        return assumed if entry.get('package_assumed') else None
    return 'power %s, voltage %s' % ('written' if power_w else assumed, 'written' if voltage_v else assumed)


SEGMENT_SPLIT_RE = re.compile(r'[/，,；;、\s]+')


def rated_voltage(value):
    """The rated voltage a value writes as a segment of its own (100n/10V, 47u/35V/X7R, 4.7uF 10V); None without one,
    or when two different voltages are written (10uF/16V/25V is not read). Every module reads a rating here."""
    found = {float(m.group(1)) for m in (WRITTEN_V_RE.match(seg) for seg in SEGMENT_SPLIT_RE.split(str(value or ''))) if m}
    return found.pop() if len(found) == 1 else None


def bom_ratings(fields):
    """Ratings the BOM writes as segments of their own (`…/160V/…`, `…，2W，…`); a voltage or power written twice, or
    inside a sentence, is not read."""
    found = {'voltage_v': set(), 'power_w': set()}
    for text in (fields or {}).values():
        for segment in SEGMENT_SPLIT_RE.split(str(text or '')):
            v, w = WRITTEN_V_RE.match(segment), WRITTEN_W_RE.match(segment)
            if v:
                found['voltage_v'].add(float(v.group(1)))
            if w:
                found['power_w'].add(float(w.group(1)))
    return {k: next(iter(vals)) for k, vals in found.items() if len(vals) == 1}


def assumed_package_refs(inventory):
    """Parts judged on the assumed package, over every assembly state."""
    return sorted({p['ref'] for state in (inventory or {}).get('states', []) for p in state.get('parts', [])
                   if p.get('package_assumed')})


def proposal_for(inventory, state_id, ref):
    """供其他检查器复用：该状态下某位号的 (建议结论, 计算, 说明)；不在本检查器范围返回 None。"""
    for state in (inventory or {}).get('states', []):
        if state['id'] == state_id:
            entry = next((p for p in state['parts'] if p['ref'] == ref), None)
            if entry is None:
                return None
            return (None, {}, '装配状态未核实') if state['gaps'] else _proposal(entry)
    return None


def _resistor_values(db):
    graph = ng.NetGraph(db)
    for ref, part in sorted((db.get('parts') or {}).items()):
        value = part.get('value') if isinstance(part, dict) else None
        if (isinstance(part, dict) and not part.get('nc') and isinstance(value, str) and value.strip()
                and graph.kind(ref) == pw.RESISTOR):
            yield ref, value, parse_resistor_noted(value)


def unread_values(db):
    """{位号: 原值}：未标 NC、值不为空而阻值读不出的电阻；计划诊断与计划命令列出，由审查员当场告诉用户。"""
    return {ref: value for ref, value, parsed in _resistor_values(db) if parsed is None}


def word_values(db):
    """{位号: 原值}：阻值读得出、后面另有读不出的词（如 pulse）的电阻；词说的要求写成 BOM 规格。BOM 那一行已写规格的
    不列（规格由审查员按 BOM 原文核）。"""
    return {ref: value for ref, value, parsed in _resistor_values(db)
            if parsed and parsed.get('notes') and not states_specification(db, ref)}


def unread_lines(plan):
    """计划命令打印的“阻值读不出”提示行。"""
    found = next((d for d in plan.get('diagnostics') or [] if d.get('code') == 'RESISTOR_VALUE_UNREAD'), None)
    if not found:
        return []
    return ['  阻值读不出的电阻（%d 颗，阻容预判与脚电流算不出）：%s' % (
                len(found['values']), '、'.join('%s「%s」' % item for item in found['values'].items())),
            '    请当场告诉用户：BOM 值改成 阻值[/公差][/额定功率][/额定电压][/封装] 的写法（如 47R/1%/2W），或确认阻值后重跑']


def rail_gaps(plan):
    """统计因轨电压未声明而没有预判的行：{轨: 行数}，供计划命令提示补 intent。"""
    counts = {}
    for check in plan.get('checks', []):
        note = (check.get('proposal') or {}).get('note') or ''
        for rail in set(re.findall(r'power_rails\.(.+?)\.voltage_v', note)):
            counts[rail] = counts.get(rail, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def ground_domains(db, intent):
    """{参考地分区: [地网]}：本预判按 0 V 处理的全部网及其参考地分区，供审查者核对与改正 domain。"""
    nets = set((db or {}).get('nets') or {})
    bounds = _Bounds(None, _declared_rails(intent))
    found = {}
    for net in sorted(nets):
        if bounds._fixed(net) == (0.0, 0.0):
            found.setdefault(bounds.domain(net) or '(未声明域)', []).append(net)
    return dict(sorted(found.items()))


def node_gaps(plan):
    """统计因多端件/连接器/跨域而无界的行：{缺口: 行数}，供计划命令提示补节点电压窗口或参考地分区。"""
    counts = {}
    for check in plan.get('checks', []):
        for basis in (check.get('proposal') or {}).get('bases') or []:
            if basis.startswith(('unbounded-', 'cross-domain:')):
                counts[basis] = counts.get(basis, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def override_errors(key, item):
    """建议 PASS 被改判为 FAIL/INSUFFICIENT 时的理由检查。"""
    override = item.get('proposal_override')
    if not isinstance(override, dict) or override.get('code') not in OVERRIDE_CODES:
        return [f'{key}: 预判 PASS 被改判，proposal_override.code 须为 {"/".join(OVERRIDE_CODES)} 之一'
                '（采购范围/料号未定不是改判理由，记 DEV-D04）']
    if not isinstance(override.get('reason'), str) or not override['reason'].strip():
        return [f'{key}: proposal_override.reason 须写明证据']
    return []


class PassiveStressChecker(Checker):
    id = 'passive_stress'
    title = '通用阻容应力预判'
    plan_key = 'passive_stress'
    version_key = 'passive_stress_version'
    version = 5   # 5: identified parts take no assumed package; series strings share the rail voltage
    allow_manual_bound_objects = False
    generated_fields = ('rule', 'method', 'domain', 'object', 'criterion', 'readiness',
                        'inventory_gaps', 'proposal')

    def build(self, db, intent):
        return inv.build(db, intent, 'power_rails', 'parts', lambda state: _scan(db, intent, state),
                         extra=lambda state: {'pins': _pin_feeds(db, intent, state)}, context_keys=('devices',))

    def plan(self, planner, inventory):
        for state, entry, state_ids in inv.walk_distinct(inventory, 'parts'):
            obj = dict({'ref': entry['ref'], 'passive_stress_digest': inventory['digest']},
                       **inv.state_fields(state_ids))
            result, calc, note = _proposal(entry)
            if entry.get('package_assumed') and not _beyond_prejudgement(result, calc):
                continue   # no footprint: only a computed stress beyond the pre-judgement gets its own row
            if state['gaps']:
                result, note = None, '装配状态未核实：' + '；'.join(state['gaps'])
            item = planner.add_check('DEV-C01', obj, criterion=CRITERION)
            item['inventory_gaps'] = list(state['gaps'])
            item['proposal'] = {'result': result, 'calculation': calc, 'note': note,
                                'nets': entry['nets'], 'bases': entry['bases'],
                                'assumptions': ['环境 ≤70 ℃（未声明时的假设）',
                                                '非轨网电压不超出同簇所接器件的最高声明供电'],
                                'override_codes': sorted(OVERRIDE_CODES)}
        for state, entry, state_ids in inv.walk_distinct(inventory, 'pins'):
            obj = dict({'ref': entry['ref'], 'node': entry['node'], 'net': entry['net'],
                        'feeds': [f['ref'] for f in entry['feeds']], 'passive_stress_digest': inventory['digest']},
                       **inv.state_fields(state_ids))
            note = '最大脚电流按源轨上限除以串联电阻最小阻值估计（脚端电压按 0 V），与手册该脚电流上限比较由审查者判定'
            if state['gaps']:
                note = '装配状态未核实：' + '；'.join(state['gaps'])
            item = planner.add_check('DEV-C01', obj, key='PIN', criterion=PIN_CRITERION)
            item['inventory_gaps'] = list(state['gaps'])
            item['proposal'] = {'result': None, 'calculation': _pin_calculation(entry), 'note': note,
                                'nets': [entry['net']] + [f['net'] for f in entry['feeds']], 'bases': ['declared-rails'],
                                'assumptions': [], 'override_codes': sorted(OVERRIDE_CODES)}

    def binds(self, item):
        obj = item.get('object')
        return isinstance(obj, dict) and 'passive_stress_digest' in obj

    def extra_presence_trigger(self, plan):
        return self.version_key in plan

    def pass_blockers(self, key, planned, generated, inventory):
        if generated and generated.get('inventory_gaps'):
            return [key + ': passive_stress gaps must be resolved in a regenerated plan before PASS']
        unread = _uncomputed_feeds(generated)
        if unread:
            return [key + ': pin current not computed (feed resistor value unreadable: %s); a PASS records the '
                    'reviewer calculation' % ', '.join(unread)]
        return []

    def blocking_gaps(self, key, planned, generated, inventory):
        return super().blocking_gaps(key, planned, generated, inventory) + [
            'resistor-value-unread:' + ref for ref in _uncomputed_feeds(generated)]

    def object_errors(self, key, obj, inventory):
        if obj.get('passive_stress_digest') != inventory['digest']:
            return [key + ': stale passive_stress object binding']
        return []

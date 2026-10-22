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
from solve_dividers import parse_resistor

from . import inventory as inv
from . import netgraph as ng
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
PACKAGE_RE = re.compile(r'^(Resistor|Capacitor)_SMD:[RC]_(0201|0402|0603|0805|1206|1210|2010|2512)_', re.I)
# 电荷泵、自举、开关、高边驱动等节点可超出所接器件的供电轨。
UNBOUNDED_PIN_RE = re.compile(
    r'^(SW\d*|LX\d*|PH\d*|VSW|SWITCH|BOOT\w*|BST\w*|VCP|CP\w*|VGH|VBOOST|HO|HG|GH\w*|HB|HS)$', re.I)
LINK_KINDS = {ng.RESISTOR, ng.CAPACITOR, ng.FERRITE, ng.DIODE, ng.ZENER, ng.TVS,
              ng.JUMPER, ng.FUSE, ng.SWITCH, ng.CRYSTAL, ng.TESTPOINT}
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
    tokens = ng.normalize(net).split('_')
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
        return ng.normalize(net) if _ground_name(net) else None

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
                if kind == ng.UNKNOWN and TWO_TERMINAL_LINK_RE.match(ref) and len(graph.pins_of(ref)) == 2:
                    kind = ng.RESISTOR
                if ng.name_matches(UNBOUNDED_PIN_RE, graph.pinname.get(node), pin):
                    gap = 'unbounded-pin:' + node
                    break
                if kind == ng.IC:
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
                        ac = ac or kind == ng.CAPACITOR
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
            self._cluster[item] = result
        return result


def _signal_series(graph, nets):
    """一端只接连接器触点、另一端接 IC 非电源脚的串阻（USB/高速线串阻）。"""
    def ends(net):
        found = set()
        for node in graph.nodes_on(net):
            ref = node.partition('.')[0]
            kind = graph.kind(ref) if graph.is_fitted(ref) else None
            if kind == ng.CONNECTOR:
                found.add('connector')
            elif kind == ng.IC and graph.pintype.get(node) not in POWER_PINTYPES:
                found.add('ic-signal')
        return frozenset(found)
    if any(ng.is_rail(net) for net in nets):
        return False
    a, b = (ends(net) for net in nets)
    return {a, b} == {frozenset({'connector'}), frozenset({'ic-signal'})}


def _scan(db, intent, state):
    graph = ng.NetGraph(db, fitted=set(state['fitted']))
    bounds = _Bounds(graph, _declared_rails(intent))
    parts = []
    for ref in sorted(graph.fitted):
        part, kind = graph.parts.get(ref, {}), graph.kind(ref)
        prefix = {ng.RESISTOR: 'R', ng.CAPACITOR: 'C'}.get(kind)
        package = _package(part, prefix) if prefix else None
        pins = graph.pins_of(ref)
        if not package or len(pins) != 2:
            continue
        entry = {'ref': ref, 'kind': kind, 'package': package, 'value': part.get('value'),
                 'nets': sorted(pins.values())}
        if kind == ng.RESISTOR and not any(_ground_name(net) for net in entry['nets']):
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
        parts.append(entry)
    return parts


def _proposal(entry):
    """返回 (建议结论或 None, 计算, 说明)。"""
    v = entry.get('v_across_max')
    if v is None:
        note = '两端电压上界算不出：' + '；'.join(entry['bases'])
        if entry.get('signal_series'):
            note += ('。信号串阻：按 wca-formulas.md“信号串联电阻”行定界（直流 I²R 加动态 ½·C·ΔV²·N_tr），'
                     '不用跨轨 V²/R，也不只算稳态电流')
        return None, {}, note
    if entry['kind'] == ng.RESISTOR:
        parsed = parse_resistor(entry['value'], default_tol=DEFAULT_TOL)
        if not parsed or parsed['kohm'] * 1000 < 1:
            return None, {'v_across_max': v}, '阻值不可解析或 <1 Ω（跳线/检流不适用最弱档表）'
        r_min = parsed['kohm'] * 1000 * (1 - parsed['tol'])
        p_floor, v_floor = RESISTOR_FLOORS[entry['package']]
        calc = {'v_across_max': v, 'r_min_ohm': round(r_min, 6), 'p_max_w': round(v * v / r_min, 9),
                'p_floor_w': p_floor, 'v_floor_v': v_floor,
                'power_ratio': round(v * v / r_min / p_floor, 6), 'voltage_ratio': round(v / v_floor, 6)}
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
    tiers = [t for t in MLCC_ORDERABLE if t[0] == entry['package'] and farads <= t[1] * (1 + 1e-9)]
    best = max(tiers, key=lambda t: t[2], default=None)
    calc = {'v_across_max': v, 'capacitance_f': farads,
            'orderable_v': best[2] if best else None, 'orderable_basis': best[3] if best else None}
    if best and v <= best[2]:
        return 'PASS', calc, '所需耐压 ≥%gV 在该封装/容值可订购档内（%s %gV）；耐压约束记 DEV-D04' % (v, best[3], best[2])
    return None, calc, '可订购档表未覆盖该封装/容值/耐压，由审查者按目录判定'


def proposal_for(inventory, state_id, ref):
    """供其他检查器复用：该状态下某位号的 (建议结论, 计算, 说明)；不在本检查器范围返回 None。"""
    for state in (inventory or {}).get('states', []):
        if state['id'] == state_id:
            entry = next((p for p in state['parts'] if p['ref'] == ref), None)
            if entry is None:
                return None
            return (None, {}, '装配状态未核实') if state['gaps'] else _proposal(entry)
    return None


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
    version = 2
    allow_manual_bound_objects = False
    generated_fields = ('rule', 'method', 'domain', 'object', 'criterion', 'readiness',
                        'inventory_gaps', 'proposal')

    def build(self, db, intent):
        return inv.build(db, intent, 'power_rails', 'parts', lambda state: _scan(db, intent, state))

    def plan(self, planner, inventory):
        for state, entry, state_ids in inv.walk_distinct(inventory, 'parts'):
            obj = dict({'ref': entry['ref'], 'passive_stress_digest': inventory['digest']},
                       **inv.state_fields(state_ids))
            result, calc, note = _proposal(entry)
            if state['gaps']:
                result, note = None, '装配状态未核实：' + '；'.join(state['gaps'])
            item = planner.add_check('DEV-C01', obj, criterion=CRITERION)
            item['inventory_gaps'] = list(state['gaps'])
            item['proposal'] = {'result': result, 'calculation': calc, 'note': note,
                                'nets': entry['nets'], 'bases': entry['bases'],
                                'assumptions': ['环境 ≤70 ℃（未声明时的假设）',
                                                '非轨网电压不超出同簇所接器件的最高声明供电'],
                                'override_codes': sorted(OVERRIDE_CODES)}

    def binds(self, item):
        obj = item.get('object')
        return isinstance(obj, dict) and 'passive_stress_digest' in obj

    def extra_presence_trigger(self, plan):
        return self.version_key in plan

    def pass_blockers(self, key, planned, generated, inventory):
        if generated and generated.get('inventory_gaps'):
            return [key + ': passive_stress gaps must be resolved in a regenerated plan before PASS']
        return []

    def object_errors(self, key, obj, inventory):
        if obj.get('passive_stress_digest') != inventory['digest']:
            return [key + ': stale passive_stress object binding']
        return []

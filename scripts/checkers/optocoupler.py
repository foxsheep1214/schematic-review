#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""光耦隔离传输检查器。

识别光耦的 LED 回路（限流电阻与驱动源）与输出侧（上拉电阻与参考），登记逐状态
清单。电流传输比（初始保证值）下的驱动能力由保证值核对（PRO-E01）按资料保证值判定；寿命末所需的
CTR 保留比例由寿命行 DEV-C06 算出并写成选型约束，SR 不自编衰减系数。隔离耐压与爬电距离不在本检查器。
"""
import catalog
from . import hotmath
from . import inventory as inv
from . import netgraph as ng
import part_words as pw
from . import powertree
from . import states as state_lib
from .base import Checker
from .planutil import slug

MAX_OPTOS = 128


def validate_optocoupler_intent(intent, db=None):
    """校验可选的 optocouplers 配置段。"""
    errors = state_lib.section_errors(
        intent, db, 'optocouplers', item_field='optocouplers', item_key='optocoupler',
        fields=('id', 'ref', 'drive', 'citation', 'internal_pullup'))
    if errors:
        return errors
    cfg = (intent or {}).get('optocouplers', {}) if isinstance(intent, dict) else {}
    for item in cfg.get('optocouplers', []) if isinstance(cfg, dict) else []:
        if isinstance(item, dict) and 'internal_pullup' in item:
            errors += internal_pullup_errors(item['internal_pullup'], db)
    return errors


def internal_pullup_errors(pull, db=None):
    """Only a cited, bounded receiver pin model can explain an absent external resistor."""
    required = {'node', 'resistance_ohm', 'states', 'citation'}
    if not isinstance(pull, dict) or not required <= set(pull) <= required | {'bias_v'}:
        return ['internal_pullup needs node, resistance_ohm, states and citation; optional bias_v']
    errors = []
    for field in ('node', 'citation'):
        if not isinstance(pull[field], str) or not pull[field].strip():
            errors.append('internal_pullup.' + field + ' must be non-empty text')
    for field, floor in (('resistance_ohm', 0), ('bias_v', None)):
        if field not in pull:
            continue
        bounds = hotmath.span(pull[field])
        if bounds is None or (floor is not None and bounds[0] <= floor) or bounds[0] < 0:
            # a pull-up to the receiver's own ground (bias_v min 0) is a bias; the resistance itself must be positive
            errors.append('internal_pullup.' + field + (' needs positive min/max' if floor is not None
                                                        else ' needs min/max ≥ 0'))
    states = pull['states']
    if not isinstance(states, list) or not states or not all(isinstance(s, str) and s.strip() for s in states):
        errors.append('internal_pullup.states needs explicit applicable state IDs')
    if db is not None and (not isinstance(pull['node'], str) or pull['node'] not in db.get('pin2net', {})):
        errors.append('internal_pullup.node must be a physical receiver pin in the netlist')
    return errors


class _Scan:
    def __init__(self, db, state, declared, excluded):
        self.graph = ng.NetGraph(db, fitted=set(state['fitted']))
        self.state = state
        self.declared = declared
        self.excluded = excluded
        self.grounds = {net for net in self.graph.nets if ng.is_ground(net)}
        self.tree = powertree.PowerTree(self.graph)

    def _series_resistors(self, nets):
        found = []
        for net in nets:
            for ref, other in self.graph.neighbors(net, {pw.RESISTOR}):
                found.append({'ref': ref, 'from': net, 'to': other,
                              'value': self.graph.parts.get(ref, {}).get('value')})
        return sorted(found, key=lambda item: item['ref'])

    def _drivers(self, nets, opto_ref):
        found = []
        for net in nets:
            for node in self.graph.nodes_on(net):
                ref = node.partition('.')[0]
                if ref == opto_ref or not self.graph.is_fitted(ref):
                    continue
                if self.graph.kind(ref) in (pw.IC, pw.CONNECTOR, pw.MOSFET, pw.BJT):
                    found.append({'node': node, 'kind': self.graph.kind(ref)})
        return sorted(found, key=lambda item: item['node'])

    def _pullups(self, net):
        return sorted({ref for ref, other in self.graph.neighbors(net, {pw.RESISTOR})
                       if self.tree.is_rail(other)})

    def _internal_pullup(self, ref, collector):
        pull = self.declared.get(ref, {}).get('internal_pullup')
        if pull is None or internal_pullup_errors(pull, self.graph.db):
            return None
        receiver = pull['node'].partition('.')[0]
        if (receiver != ref and self.graph.kind(receiver) == pw.IC
                and self.graph.is_fitted(receiver) and self.state['id'] in pull['states']
                and self.graph.pin2net.get(pull['node']) == collector):
            return pull
        return None

    def optocouplers(self):
        graph, found = self.graph, []
        for ref in sorted(graph.parts):
            if ref in self.excluded or not graph.is_fitted(ref):
                continue
            if graph.kind(ref) != pw.OPTO:
                continue
            nodes = {role: graph.node_named(ref, role)
                     for role in ('led_anode', 'led_cathode', 'out_collector', 'out_emitter')}
            gaps = list(self.state['gaps'])
            if not nodes['led_anode'] or not nodes['led_cathode']:
                gaps.append('pin-roles:' + ref)
            nets = {role: graph.pin2net.get(node) if node else None
                    for role, node in nodes.items()}
            led_nets = [net for net in (nets['led_anode'], nets['led_cathode']) if net]
            collector = nets['out_collector']
            found.append({
                'id': slug(ref),
                'ref': ref,
                'basis': 'declared' if ref in self.declared else 'topology',
                'drive': self.declared.get(ref, {}).get('drive', 'unknown'),
                'led_nets': led_nets,
                'led_resistors': self._series_resistors(led_nets),
                'led_drivers': self._drivers(led_nets, ref),
                'collector_net': collector,
                'emitter_net': nets['out_emitter'],
                'output_pullups': self._pullups(collector) if collector else [],
                'internal_pullup': self._internal_pullup(ref, collector) if collector else None,
                'gaps': sorted(set(gaps)),
            })
        return sorted(found, key=lambda item: item['id'])[:MAX_OPTOS]


def build_inventory(db, intent=None):
    """生成逐状态的光耦清单。"""
    cfg = (intent or {}).get('optocouplers') if isinstance(intent, dict) else None
    declared = {}
    for item in (cfg or {}).get('optocouplers', []) if isinstance(cfg, dict) else []:
        if isinstance(item, dict) and isinstance(item.get('ref'), str):
            declared[item['ref']] = item
    excluded = state_lib.excluded_refs(cfg)
    gaps = [] if cfg else ['intent.optocouplers: 未声明驱动方式']
    return inv.build(db, intent, 'optocouplers', 'optocouplers',
                     lambda state: _Scan(db, state, declared, excluded).optocouplers(), gaps)


class OptocouplerChecker(Checker):
    id = 'optocoupler'
    title = '光耦隔离传输'
    plan_key = 'optocoupler'
    version_key = 'optocoupler_version'
    version = 1
    intent_key = 'optocouplers'
    cold_rules = catalog.titles(stage='cold', source='optocoupler')
    e_rules = catalog.titles(method='E', source='optocoupler')

    missing_inventory_message = 'optocoupler checks require their inventory'
    inventory_type_message = 'optocoupler inventory must be an object'
    requires_db_message = 'optocoupler inventory validation requires --db'
    stale_message = 'optocoupler inventory/binding is stale or modified'
    invalid_message = 'invalid optocoupler inventory: '

    def incomplete_message(self, key):
        return key + ': incomplete optocoupler planned coverage'

    def changed_message(self, key):
        return key + ': optocoupler generated criterion/object changed'

    def validate_intent(self, intent, db):
        return validate_optocoupler_intent(intent, db)

    def build(self, db, intent):
        return build_inventory(db, intent)

    def plan(self, planner, inventory):
        for state, item, same in inv.walk_distinct(inventory, 'optocouplers'):
            obj = {'ref': item['ref'], **inv.state_fields(same), 'optocoupler': item['id'],
                   'optocoupler_digest': inventory['digest']}
            if item['collector_net']:
                obj['net'] = item['collector_net']
            gaps = item['gaps']
            check = planner.add_check(
                'PRO-E01', dict(obj), key=item['id'],
                readiness='WAITING_EVIDENCE',
                required_inputs=sorted(set(gaps + [
                    'datasheet: PRO-E01 VF/CTR/电阻与上拉保证值'])),
                trigger=['optocoupler:' + item['id']])
            check['inventory_gaps'] = gaps
            check = planner.add_check(
                'PRO-D01', dict(obj), key=item['id'], readiness='WAITING_EVIDENCE',
                required_inputs=sorted(set(gaps + [
                    'datasheet:隔离耐压与爬电要求', 'requirements:隔离等级与安规标准'])),
                trigger=['optocoupler:' + item['id']],)
            check['inventory_gaps'] = gaps

    def cold_findings(self, lint, inventory):
        for state, item in inv.walk(inventory, 'optocouplers'):
            head = '%s（状态 %s）' % (item['ref'], state['id'])
            if item['led_nets'] and not item['led_resistors'] and item['drive'] != 'constant-current':
                lint.add('PRO-A03', self.cold_rules['PRO-A03'],
                         head + '：LED 回路 ' + '、'.join(item['led_nets'])
                         + ' 上未见限流电阻；若为恒流驱动需在 intent 中声明并给出出处',
                         item['ref'])
            if item['collector_net'] and not item['output_pullups'] and not item.get('internal_pullup'):
                lint.add('PRO-A04', self.cold_rules['PRO-A04'],
                         head + '：输出集电极网 ' + item['collector_net']
                         + ' 上未见到电源轨的上拉电阻；若由接收端内部上拉或有源负载（控制器 FB/COMP/DIS 一类脚常见），'
                         '在 intent optocouplers[].internal_pullup 写明接收脚、阻值范围与出处即关闭',
                         item['ref'], kind='CANDIDATE')

    def rule_instances(self, rule, inventory):
        return sorted({item['id'] for _, item in inv.walk(inventory, 'optocouplers')})

    def binds(self, item):
        obj = item.get('object')
        return isinstance(obj, dict) and bool(obj.get('optocoupler'))

    def object_errors(self, key, obj, inventory):
        known = {item['id'] for _, item in inv.walk(inventory, 'optocouplers')}
        if (obj.get('optocoupler') not in known
                or obj.get('optocoupler_digest') != inventory['digest']):
            return [key + ': stale optocoupler object binding']
        return []

    def pass_blockers(self, key, planned, generated, inventory):
        if generated and generated.get('inventory_gaps'):
            return [key + ': optocoupler gaps must be resolved in a regenerated plan before PASS']
        return []

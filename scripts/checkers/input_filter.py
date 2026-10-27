#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""开关稳压器输入滤波与阻尼检查器。

识别开关稳压器输入网上的串联电感/磁珠、两侧电容与阻尼支路，登记逐状态清单。
负输入阻抗判据由保证值核对（PWR-E03）按资料保证值判定，并声明其为一阶判据：全频阻抗裕量、
阶跃响应与温度角仍需仿真或实测。
"""
import re

import catalog
from decoupling import parse_capacitance

from . import inventory as inv
from . import netgraph as ng
import part_words as pw
from . import powertree
from . import states as state_lib
from .base import Checker
from .planutil import slug

VIN_PIN_RE = re.compile(r'^(VIN|PVIN|VINA|VCC_IN|VDD_IN|VBUS_IN)\d*$', re.I)
SERIES_KINDS = {pw.INDUCTOR, pw.FERRITE} | pw.SERIES_WINDINGS
MAX_INPUTS = 128


def validate_input_filter_intent(intent, db=None):
    """校验可选的 input_filters 配置段。"""
    return state_lib.section_errors(
        intent, db, 'input_filters', item_field='converters', item_key='converter',
        fields=('id', 'ref', 'input_net', 'citation'), net_fields=('input_net',))


class _Scan:
    def __init__(self, db, state, declared, excluded):
        self.graph = ng.NetGraph(db, fitted=set(state['fitted']))
        self.state = state
        self.declared = declared
        self.excluded = excluded
        self.grounds = {net for net in self.graph.nets if ng.is_ground(net)}

    def _pin_nets(self, ref, pattern):
        return sorted(set(self.graph.named_pins(ref, pattern).values()))

    def _caps_to_ground(self, net):
        found = []
        for ground in sorted(self.grounds):
            for ref in self.graph.between(net, ground, {pw.CAPACITOR}):
                value = self.graph.parts.get(ref, {}).get('value')
                found.append({'ref': ref, 'to': ground, 'farads': parse_capacitance(value),
                              'bulk_candidate': pw.is_polarized_capacitor(str(value or '') + ' '
                                                                       + str(self.graph.parts.get(ref, {}).get('part') or ''))})
        return sorted(found, key=lambda item: item['ref'])

    def _series(self, net):
        """输入网上游的串联滤波元件；多于两端的共模扼流需另行声明。"""
        found, gaps = [], []
        for ref, other in self.graph.neighbors(net, SERIES_KINDS):
            found.append({'ref': ref, 'kind': self.graph.kind(ref), 'upstream_net': other})
        for ref in self.graph.refs_on(net):
            if self.graph.kind(ref) in SERIES_KINDS and not self.graph.terminals(ref):
                gaps.append('series-element-topology:' + ref)
        return sorted(found, key=lambda item: item['ref']), sorted(set(gaps))

    def _dampers(self, net):
        """串联 RC 阻尼支路：输入网 → 电阻 → 中间节点 → 电容 → 地。"""
        found = []
        for ref, middle in self.graph.neighbors(net, {pw.RESISTOR}):
            for ground in sorted(self.grounds):
                for cap in self.graph.between(middle, ground, {pw.CAPACITOR}):
                    found.append({'ref': ref + '+' + cap, 'resistor': ref, 'capacitor': cap,
                                  'farads': parse_capacitance(
                                      self.graph.parts.get(cap, {}).get('value'))})
        return sorted(found, key=lambda item: item['ref'])

    def converters(self):
        graph, found = self.graph, []
        for ref in sorted(graph.parts):
            if ref in self.excluded or not graph.is_fitted(ref) or graph.kind(ref) != pw.IC:
                continue
            input_nets = self._pin_nets(ref, VIN_PIN_RE)
            if not input_nets or not self._pin_nets(ref, powertree.SWITCH_NODE_PIN_RE):
                continue
            for net in input_nets:
                series, gaps = self._series(net)
                caps = self._caps_to_ground(net)
                dampers = self._dampers(net)
                upstream = {item['upstream_net'] for item in series}
                found.append({
                    'id': slug(ref + '-' + net),
                    'ref': ref,
                    'basis': 'declared' if ref in self.declared else 'topology',
                    'input_net': net,
                    'series_elements': series,
                    'upstream_caps': sorted(
                        (cap for other in sorted(upstream) for cap in self._caps_to_ground(other)),
                        key=lambda item: item['ref']),
                    'input_caps': caps,
                    'dampers': dampers,
                    'bulk_candidates': [cap['ref'] for cap in caps if cap['bulk_candidate']],
                    'gaps': sorted(set(list(self.state['gaps']) + gaps)),
                })
        return sorted(found, key=lambda item: item['id'])[:MAX_INPUTS]


def build_inventory(db, intent=None):
    """生成逐状态的输入滤波清单。"""
    cfg = (intent or {}).get('input_filters') if isinstance(intent, dict) else None
    declared = state_lib.declared_refs(cfg, 'converters')
    excluded = state_lib.excluded_refs(cfg)
    gaps = [] if cfg else ['intent.input_filters: 未声明变换器输入']
    return inv.build(db, intent, 'input_filters', 'converters',
                     lambda state: _Scan(db, state, declared, excluded).converters(), gaps)


class InputFilterChecker(Checker):
    id = 'input_filter'
    title = '开关电源输入滤波与阻尼'
    plan_key = 'input_filter'
    version_key = 'input_filter_version'
    version = 1
    intent_key = 'input_filters'
    cold_rules = catalog.titles(stage='cold', source='input_filter')
    e_rules = catalog.titles(method='E', source='input_filter')

    missing_inventory_message = 'input filter checks require their inventory'
    inventory_type_message = 'input filter inventory must be an object'
    requires_db_message = 'input filter inventory validation requires --db'
    stale_message = 'input filter inventory/binding is stale or modified'
    invalid_message = 'invalid input filter inventory: '

    def incomplete_message(self, key):
        return key + ': incomplete input filter planned coverage'

    def changed_message(self, key):
        return key + ': input filter generated criterion/object changed'

    def validate_intent(self, intent, db):
        return validate_input_filter_intent(intent, db)

    def build(self, db, intent):
        return build_inventory(db, intent)

    def plan(self, planner, inventory):
        for state, item in inv.walk(inventory, 'converters'):
            obj = {'ref': item['ref'], 'net': item['input_net'], 'state': state['id'],
                   'input_filter': item['id'], 'input_filter_digest': inventory['digest']}
            gaps = item['gaps']
            check = planner.add_check(
                'PWR-E03', dict(obj), key=item['id'],
                readiness='WAITING_EVIDENCE',
                required_inputs=sorted(set(gaps + [
                    'datasheet: PWR-E03 输入电压/功率、ESR、电感与电容保证值',
                    'intent: 体电容与输入电容比值的项目规定'])),
                trigger=['input-filter:' + item['id']])
            check['inventory_gaps'] = gaps
            check = planner.add_check(
                'PWR-C11', dict(obj), key=item['id'], readiness='WAITING_EVIDENCE',
                required_inputs=sorted(set(gaps + [
                    'datasheet:滤波元件阻抗/饱和曲线、DCR、温升电流额定及适用条件',
                    'intent:滤波元件峰值/RMS 电流与温度工况', 'requirements:传导发射限值与裕量'])),
                trigger=['input-filter:' + item['id']],)
            check['inventory_gaps'] = gaps

    def cold_findings(self, lint, inventory):
        for state, item in inv.walk(inventory, 'converters'):
            if not item['series_elements'] or item['dampers'] or item['bulk_candidates']:
                continue
            lint.add('PWR-A05', self.cold_rules['PWR-A05'],
                     '%s（状态 %s）：输入网 %s 经 %s 串联滤波，但未见 RC 阻尼支路或带 ESR 的'
                     '体电容；负输入阻抗与滤波谐振的配合需按保证值核算'
                     % (item['ref'], state['id'], item['input_net'],
                        '、'.join(x['ref'] for x in item['series_elements'])),
                     item['ref'], kind='CANDIDATE')

    def rule_instances(self, rule, inventory):
        return sorted({item['id'] for _, item in inv.walk(inventory, 'converters')})

    def binds(self, item):
        obj = item.get('object')
        return isinstance(obj, dict) and bool(obj.get('input_filter'))

    def object_errors(self, key, obj, inventory):
        known = {item['id'] for _, item in inv.walk(inventory, 'converters')}
        if (obj.get('input_filter') not in known
                or obj.get('input_filter_digest') != inventory['digest']):
            return [key + ': stale input filter object binding']
        return []

    def pass_blockers(self, key, planned, generated, inventory):
        if generated and generated.get('inventory_gaps'):
            return [key + ': input filter gaps must be resolved in a regenerated plan before PASS']
        return []

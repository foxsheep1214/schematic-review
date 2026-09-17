#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查计划生成：按规则总表（scripts/catalog.py）把审查展开为逐项计划。

这个脚本只回答“哪些检查需要执行、按什么规则和方式执行、还缺什么证据”，
不提前给 PASS/FAIL。每个计划项带规则编号、检查方式与内容域，检查 ID 以
规则编号开头。HANDOFF 是独立下游动作，可以与后续 PASS/FAIL/INSUFFICIENT 并存。

用法：
    python3 plan_review.py db.json --intent intent.json \
        --datasheet-audit datasheet-audit.json \
        --evidence evidence.json --json review-plan.json
"""
import argparse
from copy import deepcopy
import board_intent
import catalog
from electrical_contract import PLAN_SCHEMA_VERSION, db_fingerprint, check_matches, readiness_gaps, validate_evidence, bounded, finite, load_json
import io
import json
import os
import re
import sys
from collections import Counter
from checkers import (REGISTRY, REGISTRY_BY_ID, registry_cold_rules,
                      registry_hot_rules)
from checkers.netgraph import GNDS, RAIL_RE
from checkers.planutil import empty_handoff as _empty_handoff, handoff as _handoff, slug as _slug
from revision_impact import attach_metadata, digest as revision_digest, validate_declarations

from audit_datasheets import (
    datasheet_audit_all_available,
    datasheet_entry_for_ref,
    validate_datasheet_audit,
)


INTENT_SCHEMA_VERSION = 3
APPLICABILITY = ('APPLICABLE', 'NOT_APPLICABLE', 'UNDETERMINED')
READINESS = ('READY', 'WAITING_EVIDENCE', 'NOT_SCHEDULED')
RESULT_STATUSES = ('PASS', 'FAIL', 'INSUFFICIENT', 'NA')
HANDOFF_STATES = ('OPEN', 'ACCEPTED', 'VERIFIED')

EN_RE = re.compile(
    r'(^|_)(EN|ENABLE|SHDN|SHUTDOWN|PWREN|PWR_EN)(_|\d|$)', re.I)
STRAP_RE = re.compile(
    r'(^|_)(BOOT\w*|STRAP\w*|TEST_MODE\w*|CFG\w*|CONFIG\w*|MODE\d*)(_|$)',
    re.I)
I2C_RE = re.compile(r'(^|_)(I2C\w*|SCL\d*|SDA\d*)(_|$)', re.I)
FB_NAMES = {'FB', 'ADJ', 'VFB', 'FBX', 'VSENSE', 'VOSNS', 'VOUT_SENSE'}
DEVICE_RE = re.compile(r'^[UM]\d', re.I)
CONNECTOR_RE = re.compile(r'^(J|P|CN)\d', re.I)
# 旧版意图里改了名的功能与电路类型。
RENAMED_PACKAGES = {'RESET': 'STARTUP', 'USB_C': 'USB', 'CAN_RS485': 'CAN 或 RS485'}
# 全板规则执行前需要的资料；未列出的规则只需网表。
BOARD_MATERIALS = {
    'DOC-D02': ('requirements',), 'DOC-V02': ('schematic_pdf',),
    'DEV-C01': ('datasheets', 'requirements'), 'DEV-C02': ('datasheets', 'requirements'),
    'DEV-C03': ('requirements',), 'DEV-C04': ('datasheets', 'requirements'),
    'PWR-T06': ('datasheets', 'platform_checklist'),
    'SIG-D13': ('datasheets', 'platform_checklist'), 'REQ-D02': ('requirements',),
}


# 冷跑规则所需的 db 索引；规则名称与判据在 catalog 中。
COLD_RULE_INDEXES = {
    'NET-A01': ['nets'], 'NET-A02': ['nets'],
    'NET-A03': ['nets', 'parts'], 'PWR-A01': ['nets', 'parts'],
    'PWR-A02': ['pinname'], 'PWR-A03': ['pinname'],
    'PRO-A01': ['nets', 'parts'], 'PRO-A02': ['nets', 'parts'],
    'NET-A04': ['nets'], 'PWR-A04': ['nets'], 'DOC-A03': ['parts'],
}
# 由网表实例化的内置证据计算规则。
BUILTIN_EVIDENCE_RULES = tuple(rule.id for rule in catalog.rules(method='E', source='lint'))


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def validate_intent(intent, db=None):
    """验证扩展 intent；兼容旧版仅含 expect 的输入。给出 db 时同时核对网表绑定。"""
    if intent is None:
        return []
    if not isinstance(intent, dict):
        return ['intent 根对象必须为 object']
    errors = []
    if 'schema_version' in intent and intent['schema_version'] != INTENT_SCHEMA_VERSION:
        errors.append('schema_version 必须为 %d（旧版意图请按 check-catalog.md 迁移）' % INTENT_SCHEMA_VERSION)
    if intent.get('review_mode') not in (None, 'first', 'revision'):
        errors.append('review_mode 必须为 first/revision')
    expect = intent.get('expect', {})
    if not isinstance(expect, dict):
        errors.append('expect 必须为 object')
    else:
        for key, value in expect.items():
            if not _text(key) or isinstance(value, bool) or not isinstance(value, int):
                errors.append(f'expect.{key!r} 必须为非空名称和整数数量')
            elif value < 0:
                errors.append(f'expect.{key} 不得小于 0')
    features = intent.get('features', {})
    if not isinstance(features, dict):
        errors.append('features 必须为 object')
    else:
        for key, item in features.items():
            label = f'features.{key}'
            if str(key).upper() in RENAMED_PACKAGES:
                errors.append(f'{label} 已改名为 {RENAMED_PACKAGES[str(key).upper()]}')
                continue
            if not _text(key) or not isinstance(item, dict):
                errors.append(f'{label} 必须为 object')
                continue
            state = item.get('applicability')
            if state not in APPLICABILITY:
                errors.append(f'{label}.applicability 不支持: {state!r}')
            if state in ('APPLICABLE', 'NOT_APPLICABLE') and not _text(
                    item.get('citation')):
                errors.append(f'{label}.citation 缺失')
    materials = intent.get('materials', {})
    if not isinstance(materials, dict):
        errors.append('materials 必须为 object')
    else:
        for key, item in materials.items():
            label = f'materials.{key}'
            if not _text(key) or not isinstance(item, dict):
                errors.append(f'{label} 必须为 object')
                continue
            if not isinstance(item.get('available'), bool):
                errors.append(f'{label}.available 必须为 boolean')
            if item.get('available') and not _text(item.get('citation')):
                errors.append(f'{label}.citation 缺失')
    rails = intent.get('power_rails', {})
    if not isinstance(rails, dict):
        errors.append('power_rails 必须为按网络名索引的 object')
    else:
        for net, budget in rails.items():
            if not _text(net) or not isinstance(budget, dict):
                errors.append('power_rails 每轨必须为 object')
                continue
            for field in ('voltage_v', 'load_a'):
                value = budget.get(field)
                if field in budget and (not bounded(value) or (field == 'load_a' and value['min'] < 0)):
                    errors.append(f'power_rails.{net}.{field} 需要有效 min/max；负载电流用非负幅值')
            if 'available_a_min' in budget and (not finite(budget['available_a_min']) or budget['available_a_min'] < 0):
                errors.append(f'power_rails.{net}.available_a_min 需要非负有限数')
            if 'refs' in budget and (not isinstance(budget['refs'], list) or not budget['refs']
                    or not all(_text(x) for x in budget['refs'])):
                errors.append(f'power_rails.{net}.refs 需要非空位号数组')
    for field in ('power_sources', 'power_paths', 'circuits'):
        if field in intent and (not isinstance(intent[field], list)
                or not all(isinstance(x, dict) for x in intent[field])):
            errors.append(f'{field} 必须为 object 数组')
    for source in intent.get('power_sources', []) if isinstance(intent.get('power_sources', []), list) else []:
        if not isinstance(source, dict):
            continue
        if not _text(source.get('node')) or not _text(source.get('citation')) or not (
                isinstance(source.get('states'), list) and source['states']
                and all(_text(x) for x in source['states'])):
            errors.append('power_sources 需要 node/states/citation')
    for edge in intent.get('power_paths', []) if isinstance(intent.get('power_paths', []), list) else []:
        if isinstance(edge, dict) and not all(_text(edge.get(k)) for k in ('ref', 'from', 'to', 'state', 'citation')):
            errors.append('power_paths 需要 ref/from/to/state/citation')
    if (intent.get('power_sources') or intent.get('power_paths')) and not _text(intent.get('active_state')):
        errors.append('电源路径需要 active_state')
    seen_circuits = set()
    for circuit in intent.get('circuits', []) if isinstance(intent.get('circuits', []), list) else []:
        if not isinstance(circuit, dict):
            continue
        cid = circuit.get('id')
        if not _text(cid) or cid in seen_circuits:
            errors.append('circuits.id 缺失或重复')
        else:
            seen_circuits.add(cid)
        if 'domain' in circuit:
            errors.append('circuits.domain 已改名为 circuits.type')
        kind = circuit.get('type')
        if not isinstance(kind, str) or kind not in catalog.PACKAGE_BY_NAME:
            hint = RENAMED_PACKAGES.get(kind) if isinstance(kind, str) else None
            errors.append('circuits.type 不支持: %r（%s）' % (
                kind, '已改名为 ' + hint if hint else '取 check-catalog.md 中的功能包名'))
        for field in ('refs', 'states'):
            values = circuit.get(field)
            if not isinstance(values, list) or not values or not all(_text(x) for x in values):
                errors.append(f'circuits.{field} 必须为非空字符串数组')
        if not _text(circuit.get('citation')):
            errors.append('circuits.citation 缺失')
    requirements = intent.get('requirements', [])
    if not isinstance(requirements, list):
        errors.append('requirements 必须为数组')
    else:
        seen = set()
        for item in requirements:
            if not isinstance(item, dict):
                errors.append('requirement 必须为 object')
                continue
            for key in ('id', 'text', 'citation', 'criterion'):
                if not _text(item.get(key)):
                    errors.append(f'requirement.{key} 缺失')
            rid = item.get('id')
            if _text(rid):
                if rid in seen:
                    errors.append(f'requirement id 重复: {rid}')
                seen.add(rid)
    errors.extend(board_intent.validate(intent, db))
    for checker in REGISTRY:
        errors.extend(checker.validate_intent(intent, db))
    errors.extend(validate_declarations(intent))
    return errors


def _material_available(intent, key, datasheet_audit=None):
    if key == 'datasheets' and datasheet_audit is not None:
        return datasheet_audit_all_available(datasheet_audit)
    item = (intent or {}).get('materials', {}).get(key, {})
    return isinstance(item, dict) and item.get('available') is True


def _database_blobs(db):
    blobs = []
    for net in db.get('nets', {}):
        blobs.append(f'NET:{net}')
    for node, pin in db.get('pinname', {}).items():
        blobs.append(f'PIN:{node}:{pin}')
    for ref, part in db.get('parts', {}).items():
        blobs.append('PART:' + ':'.join([
            ref, str(part.get('part', '')), str(part.get('value', '')),
            str(part.get('prim', '')), str(part.get('jedec', ''))]))
    return blobs


def _feature_hits(db, pattern):
    regex = re.compile(pattern, re.I)
    return sorted(blob for blob in _database_blobs(db) if regex.search(blob))[:12]


def _differential_pairs(db):
    nets = set(db.get('nets', {}))
    found = set()
    for net in sorted(nets):
        candidates = []
        if net.endswith('_P'):
            candidates.append(net[:-2] + '_N')
        if net.endswith('-P'):
            candidates.append(net[:-2] + '-N')
        if net.endswith('+'):
            candidates.append(net[:-1] + '-')
        if net.upper().endswith('_DP'):
            candidates.append(net[:-3] + '_DM')
        for other in candidates:
            if other in nets:
                found.add((net, other))
    return sorted(found)


class ReviewPlanner:
    def __init__(self, db, intent=None, evidence=None, review_mode=None,
                 old_db_available=False, claims_available=False,
                 datasheet_audit=None, previous_plan=None, old_db=None, old_plan=None):
        self.db = db
        self.inventories = {checker.id: checker.build(db, intent) for checker in REGISTRY}
        self.i2c_topology = self.inventories['i2c_topology']
        self.decoupling = self.inventories['decoupling']
        self.db_sha256 = db_fingerprint(db)
        self.intent = intent or {}
        self.evidence = evidence or {}
        self.datasheet_audit = datasheet_audit
        self.previous_plan = previous_plan
        self.old_db, self.old_plan = old_db, old_plan
        self.review_mode = (
            review_mode or self.intent.get('review_mode') or
            ('revision' if old_db is not None or old_plan is not None else 'first'))
        self.old_db_available = old_db_available or old_db is not None
        self.claims_available = claims_available
        self.checks = []
        self.rule_plan = []
        self.diagnostics = []
        self._ids = set()

    def matching_evidence(self, rule, obj):
        return [check for check in self.evidence.get('checks', [])
                if check_matches(self.db, check, rule, obj)]

    def evidence_ready(self, rule, obj):
        matches = self.matching_evidence(rule, obj)
        return bool(matches) and all(not readiness_gaps(self.db, x, self.datasheet_audit, self.db_sha256)
                                     for x in matches)

    def add_check(self, rule, obj, key=None, criterion=None,
                  applicability='APPLICABLE', readiness='READY',
                  required_inputs=None, trigger=None, handoff=None):
        """按规则总表生成一个计划项；ID = 规则编号[.实例键].锚点。"""
        entry = catalog.get(rule)
        anchor = (obj.get('node') or obj.get('net') or obj.get('ref') or obj.get('feature')
                  or obj.get('package') or obj.get('assembly') or obj.get('page')
                  or obj.get('board') or 'GLOBAL')
        base = '.'.join([rule] + ([_slug(key)] if key else []) + [_slug(anchor)])
        check_id, suffix = base, 2
        while check_id in self._ids:
            check_id = f'{base}-{suffix}'
            suffix += 1
        self._ids.add(check_id)
        if applicability != 'APPLICABLE':
            readiness = 'NOT_SCHEDULED'
        item = {
            'id': check_id,
            'rule': rule,
            'method': catalog.method_of(rule),
            'domain': catalog.domain_of(rule),
            'object': obj,
            'criterion': entry.criterion if criterion is None else criterion,
            'applicability': applicability,
            'readiness': readiness,
            'required_inputs': sorted(set(required_inputs or [])),
            'trigger': sorted(set(trigger or [])),
            'review_result': 'NA' if applicability == 'NOT_APPLICABLE' else None,
            'evidence_confidence': None,
            'handoff': handoff or _empty_handoff(),
        }
        matches = self.matching_evidence(rule, obj) if item['method'] == 'E' else []
        if matches:
            # Retain the cold check as a coverage parent; state children carry the individual verdicts.
            item['role'] = 'coverage_parent'
            item['aggregation'] = '逐状态子检查完成后汇总，不能替代子项结果'
            self.checks.append(item)
            for evidence in matches:
                child = deepcopy(item)
                child_base = child['id'] + '.' + _slug(evidence['id'])
                child_id, child_suffix = child_base, 2
                while child_id in self._ids:
                    child_id = f'{child_base}-{child_suffix}'
                    child_suffix += 1
                child['id'] = child_id
                self._ids.add(child_id)
                child['evidence_check_id'] = evidence['id']
                child['parent_check_id'] = item['id']
                child.pop('role', None)
                child.pop('aggregation', None)
                child['object']['state'] = (evidence.get('basis') or {}).get('state')
                gaps = readiness_gaps(self.db, evidence, self.datasheet_audit, self.db_sha256)
                child['readiness'] = 'WAITING_EVIDENCE' if gaps else 'READY'
                child['required_inputs'] = gaps
                self.checks.append(child)
            return self.checks[-1]
        if rule == 'REQ-Q07':
            item['role'] = 'coverage_parent'
            item['aggregation'] = '逐电路/状态成员检查完成后汇总，禁止整包一次性 PASS'
        self.checks.append(item)
        return item

    def add_rule(self, rule, name, applicability, readiness, instances=None,
                 required_inputs=None, reason=''):
        if applicability != 'APPLICABLE':
            readiness = 'NOT_SCHEDULED'
        self.rule_plan.append({
            'rule': rule,
            'name': name,
            'applicability': applicability,
            'readiness': readiness,
            'instances': sorted(instances or []),
            'required_inputs': sorted(set(required_inputs or [])),
            'reason': reason,
        })

    def _materials_gap(self, materials):
        return [x for x in materials if not _material_available(self.intent, x, self.datasheet_audit)]

    def _datasheet_readiness(self, ref, part):
        """逐位号的资料缺口：有资料审计时按审计条目，否则按 materials.datasheets。"""
        if self.datasheet_audit is None:
            return self._materials_gap(['datasheets']), []
        entry = datasheet_entry_for_ref(self.datasheet_audit, ref)
        if entry and entry.get('status') == 'AVAILABLE':
            gaps = []
        else:
            identity = entry.get('identity') if entry else part.get('value') or part.get('part') or ref
            gaps = [f'datasheet:{identity}']
        return gaps, ['datasheet-audit:' + (entry.get('status') if entry else 'UNLISTED')]

    def _ready_check(self, rule, obj, gaps, trigger, **extra):
        return self.add_check(rule, obj, readiness='WAITING_EVIDENCE' if gaps else 'READY',
                              required_inputs=gaps, trigger=trigger, **extra)

    def _disposition_check(self, ref, gaps, trigger):
        """引脚处置逐位号一项；声明了脚表时附上未接网脚与接了网的 NC 脚，供逐脚核对。"""
        item = self._ready_check('DEV-D05', {'ref': ref}, gaps, trigger)
        device = (self.intent.get('devices') or {}).get(ref)
        if device:
            unconnected, nc_connected = board_intent.pin_disposition(self.db, ref, device)
            item['pin_disposition'] = {'unconnected': unconnected, 'nc_connected': nc_connected}

    def plan_board(self):
        """全板通用规则每块板一项；装配选项逐个声明的装配状态核对。"""
        for rule in catalog.rules(source='board'):
            self._ready_check(rule.id, {'board': 'BOARD'},
                              self._materials_gap(BOARD_MATERIALS.get(rule.id, ())), ['board'])
        assemblies = self.intent.get('assemblies') or []
        for state in assemblies:
            self.add_check('DOC-T01', {'assembly': state['id']},
                           trigger=[f'intent.assemblies:{state["citation"]}'])
        if not assemblies:
            self.add_check('DOC-T01', {'board': 'BOARD'}, readiness='WAITING_EVIDENCE',
                           required_inputs=['intent.assemblies'], trigger=['assembly-options'])

    def plan_packages(self):
        """功能包：检出或声明即生成 REQ-Q07 汇总项与全部成员规则；未检出也未声明的汇总到一项 REQ-Q08。"""
        declared = {str(key).upper(): value for key, value in self.intent.get('features', {}).items()}
        circuits = {}
        for circuit in self.intent.get('circuits', []):
            circuits.setdefault(circuit['type'], []).append(circuit)
        custom = [catalog.Package(name, name, 'REQ', r'(?!x)x', (), ('requirements',), {'required': False})
                  for name in sorted(set(declared) - set(catalog.PACKAGE_BY_NAME))]
        undetected = []
        for package in catalog.PACKAGES + tuple(custom):
            name = package.name
            hits = _feature_hits(self.db, package.pattern)
            if name == 'I2C' and any(b['origin'] != 'name-hint'
                    for s in self.i2c_topology['states'] for b in s['buses']):
                hits.append('declared I2C physical bus/port mapping')
            declared_circuits = circuits.get(name, [])
            found = hits + [f'intent.circuits:{c["id"]}' for c in declared_circuits]
            item = declared.get(name)
            requested = item.get('applicability') if item else None
            trigger = [f'netlist:{x}' for x in hits]
            trigger += [f'intent.circuits:{c["citation"]}' for c in declared_circuits]
            if item and item.get('citation'):
                trigger.append(f'intent:{item["citation"]}')

            if requested == 'NOT_APPLICABLE' and found:
                applicability = 'UNDETERMINED'
                self.diagnostics.append({
                    'code': 'INTENT_NETLIST_CONFLICT',
                    'feature': name,
                    'detail': '意图声明不适用，但网表或电路声明中有该功能包',
                    'hits': found,
                })
            elif requested in ('APPLICABLE', 'NOT_APPLICABLE'):
                applicability = requested
            elif found:
                applicability = 'APPLICABLE'
            elif item:
                applicability = 'UNDETERMINED'
            else:
                undetected.append(name)
                continue

            if applicability == 'NOT_APPLICABLE':
                missing = []
            elif applicability == 'UNDETERMINED':
                missing = [f'intent.features.{name}']
                if requested == 'NOT_APPLICABLE' and found:
                    missing.append('resolve intent/netlist conflict')
            else:
                missing = self._materials_gap(package.materials)
            if applicability == 'APPLICABLE' and requested == 'APPLICABLE' and not found:
                self.diagnostics.append({
                    'code': 'REQUIRED_FEATURE_NOT_DETECTED',
                    'feature': name,
                    'detail': '设计意图要求该功能，但网表未检测到对应特征',
                })
            summary = self.add_check(
                'REQ-Q07', {'package': name}, criterion=catalog.package_criterion(name),
                applicability=applicability, readiness='WAITING_EVIDENCE' if missing else 'READY',
                required_inputs=missing, trigger=trigger,
                handoff=_handoff(package.handoff, applicability))
            summary['package'] = name
            if applicability == 'APPLICABLE' and requested == 'APPLICABLE' and not found:
                self.add_check('REQ-A02', {'package': name}, readiness='READY',
                               trigger=[f'intent:{item["citation"]}'])
            if applicability == 'APPLICABLE':
                self.plan_package_members(package, declared_circuits, missing)
        if undetected:
            titles = [(name, catalog.package(name).title) for name in undetected]
            self.add_check(
                'REQ-Q08', {'board': 'BOARD', 'packages': undetected},
                criterion=catalog.criterion('REQ-Q08') + '：' + '、'.join(
                    name if title == name else f'{name}（{title}）' for name, title in titles),
                readiness='WAITING_EVIDENCE',
                required_inputs=[f'intent.features.{name}' for name in undetected],
                trigger=['package-discovery'])

    def plan_package_members(self, package, circuits, missing):
        """声明了电路则逐电路×工况展开成员规则，否则按功能包展开一次；已有 I²C 区域时由检查器逐区域展开。"""
        members = []
        for circuit in circuits:
            refs = circuit['refs']
            gaps = [f'datasheet:{ref}' for ref in refs
                    if not (datasheet_entry_for_ref(self.datasheet_audit, ref) or {}).get('status') == 'AVAILABLE']
            gaps += [f'unknown ref:{ref}' for ref in refs if ref not in self.db.get('parts', {})]
            for state in circuit['states']:
                obj = {'circuit': circuit['id'], 'ref': refs[0], 'refs': refs,
                       'nets': circuit.get('nets', []), 'state': state}
                members.append((obj, f'{circuit["id"]}-{state}', gaps, f'intent.circuits:{circuit["citation"]}'))
        regions = any(state['regions'] for state in self.i2c_topology['states'])
        if not circuits and not (package.name == 'I2C' and regions):
            members.append(({'package': package.name}, None, missing, f'package:{package.name}'))
        for obj, key, gaps, trigger in members:
            for rule in package.rules:
                item = self._ready_check(rule, dict(obj), gaps, [trigger], key=key)
                item['package'] = package.name
                item['analysis_required'] = True
                item['scope'] = '原理图电气条件；PCB/实测验证另建 HANDOFF'

    def plan_checkers(self):
        """遍历检查器注册表；每个检查器只生成自己的计划项。"""
        for checker in REGISTRY:
            inventory = self.inventories.get(checker.id)
            if inventory is not None:
                checker.plan(self, inventory)

    def plan_i2c_topology(self):
        """兼容入口：单独生成 I²C 连接覆盖计划项。"""
        REGISTRY_BY_ID['i2c_topology'].plan(self, self.inventories['i2c_topology'])

    def plan_decoupling(self):
        """兼容入口：单独生成去耦计划项。"""
        REGISTRY_BY_ID['decoupling'].plan(self, self.inventories['decoupling'])

    def plan_concrete_checks(self):
        db = self.db
        nets = db.get('nets', {})
        pinname = db.get('pinname', {})
        pin2net = db.get('pin2net', {})
        pseudo = set(db.get('pseudo_nets', []))

        # 证据计算：反馈分压、使能、strap 与 I2C 上拉。
        for node, pin in sorted(pinname.items()):
            net = pin2net.get(node)
            upper_pin = str(pin).strip().upper()
            ref = node.split('.')[0]
            if upper_pin in FB_NAMES and net:
                obj = {'node': node, 'net': net, 'ref': ref}
                ready = self.evidence_ready('PWR-E01', obj)
                self.add_check(
                    'PWR-E01', obj, readiness='READY' if ready else 'WAITING_EVIDENCE',
                    required_inputs=[] if ready else ['datasheet:Vref/目标窗口'],
                    trigger=[f'pinname:{pin}'])
            if net and (EN_RE.search(upper_pin) or (
                    EN_RE.search(net) and re.match(r'^[UMQ]\d', ref, re.I))):
                obj = {'node': node, 'net': net, 'ref': ref}
                ready = self.evidence_ready('RST-E01', obj)
                self.add_check(
                    'RST-E01', obj, readiness='READY' if ready else 'WAITING_EVIDENCE',
                    required_inputs=[] if ready else ['datasheet:pin function/Abs Max'],
                    trigger=[f'pinname:{pin}', f'net:{net}'])
            if net and (STRAP_RE.search(upper_pin) or (
                    STRAP_RE.search(net) and re.match(r'^[UMQ]\d', ref, re.I))):
                obj = {'node': node, 'net': net, 'ref': ref}
                ready = self.evidence_ready('RST-E02', obj)
                self.add_check(
                    'RST-E02', obj, readiness='READY' if ready else 'WAITING_EVIDENCE',
                    required_inputs=[] if ready else ['datasheet:strap table/mandatory wording'],
                    trigger=[f'pinname:{pin}', f'net:{net}'])

        i2c_nets = set()
        for net, nodes in nets.items():
            if I2C_RE.search(net) or any(
                    I2C_RE.search(str(pinname.get(node, ''))) for node in nodes):
                i2c_nets.add(net)
        for net in sorted(i2c_nets - pseudo):
            obj = {'net': net}
            ready = self.evidence_ready('SIG-E01', obj)
            self.add_check(
                'SIG-E01', obj, readiness='READY' if ready else 'WAITING_EVIDENCE',
                required_inputs=[] if ready else ['datasheet/platform:I2C pull requirement'],
                trigger=[f'net:{net}'])

        # 连接器：pin map（证据计算）、对端定义、未用针处置与对外防护逐个一项。
        for ref, part in sorted(db.get('parts', {}).items()):
            if not CONNECTOR_RE.match(ref) or part.get('nc'):
                continue
            obj = {'ref': ref}
            ready = self.evidence_ready('DEV-E01', obj)
            self.add_check(
                'DEV-E01', obj, readiness='READY' if ready else 'WAITING_EVIDENCE',
                required_inputs=[] if ready else ['connector drawing/opposite-side pinout'],
                trigger=[f'refdes:{ref}'])
            gaps, audit_trigger = self._datasheet_readiness(ref, part)
            self._ready_check('DEV-D03', {'ref': ref}, self._materials_gap(['requirements']), [f'refdes:{ref}'])
            self._disposition_check(ref, gaps, [f'refdes:{ref}'] + audit_trigger)
            self.add_check('PRO-D03', {'ref': ref}, trigger=[f'refdes:{ref}'])

        # 每条电源轨分别检查拓扑（连接追踪）和功耗预算（工程计算）。
        for net in sorted(nets):
            if net in pseudo or net in GNDS or not RAIL_RE.match(net):
                continue
            self.add_check('PWR-T01', {'net': net}, trigger=[f'rail-name:{net}'])
            budget = self.intent.get('power_rails', {}).get(net, {})
            missing = []
            for field in ('voltage_v', 'load_a'):
                if not bounded(budget.get(field)):
                    missing.append(f'power_rails.{net}.{field}.min/max')
            if not finite(budget.get('available_a_min')):
                missing.append(f'power_rails.{net}.available_a_min')
            for field in ('state', 'citation'):
                if not _text(budget.get(field)):
                    missing.append(f'power_rails.{net}.{field}')
            if not budget.get('refs'):
                missing.append(f'power_rails.{net}.refs')
            for ref in budget.get('refs', []):
                entry = datasheet_entry_for_ref(self.datasheet_audit, ref)
                if not entry or entry.get('status') != 'AVAILABLE':
                    missing.append(f'datasheet:{ref}')
            self.add_check(
                'PWR-C01', {'net': net},
                readiness='WAITING_EVIDENCE' if missing else 'READY',
                required_inputs=missing, trigger=[f'rail-name:{net}'],
                handoff={
                    'required': True, 'state': 'OPEN',
                    'receivers': ['PCB Layout', 'Thermal/Test'],
                    'constraint': '大电流载流、压降、去耦与散热要求',
                    'verification': 'PCB 复核与温升/压降验证',
                })

        # 差分连通（连接追踪）：PASS/FAIL 与 PCB HANDOFF 可以并存。
        for positive, negative in _differential_pairs(db):
            self.add_check(
                'SIG-T01', {'net_p': positive, 'net_n': negative, 'net': positive},
                trigger=[f'pair:{positive}/{negative}'],
                handoff={
                    'required': True, 'state': 'OPEN',
                    'receivers': ['PCB Layout'],
                    'constraint': '按接口规范落实差分阻抗、等长、间距与回流',
                    'verification': 'PCB 约束与版图复核',
                })

        # 图面目检：每张实际出现器件的页面独立一项。
        pages = sorted(
            {page for page in db.get('ref2page', {}).values()
             if page not in (None, '')}, key=lambda value: str(value))
        pdf_ready = _material_available(self.intent, 'schematic_pdf')
        for page in pages:
            self.add_check(
                'DOC-V01', {'page': page},
                readiness='READY' if pdf_ready else 'WAITING_EVIDENCE',
                required_inputs=[] if pdf_ready else ['schematic_pdf'],
                trigger=[f'ref2page:{page}'])

        # 每颗 IC/模组独立核对身份与封装、引脚处置和推荐工作条件。
        for ref, part in sorted(db.get('parts', {}).items()):
            if not DEVICE_RE.match(ref) or part.get('nc'):
                continue
            gaps, audit_trigger = self._datasheet_readiness(ref, part)
            trigger = [f'refdes:{ref}', f'part:{part.get("part", "")}'] + audit_trigger
            self._ready_check('DEV-D01', {'ref': ref}, gaps, trigger)
            self._disposition_check(ref, gaps, trigger)
            self._ready_check('DEV-C05', {'ref': ref}, gaps + self._materials_gap(['requirements']), trigger)

    def plan_rules(self):
        """规则级台账：自动扫描、证据计算、版本比对及按实例汇总的检测点规则。"""
        for rule, indexes in sorted(COLD_RULE_INDEXES.items()):
            missing = [key for key in indexes if not self.db.get(key)]
            self.add_rule(
                rule, catalog.title(rule), 'APPLICABLE',
                'WAITING_EVIDENCE' if missing else 'READY',
                required_inputs=missing, reason='纯网表冷跑规则')

        for rule, (name, checker) in sorted(registry_cold_rules().items()):
            inventory = self.inventories.get(checker.id)
            gaps = list(inventory.get('discovery_gaps', [])) if inventory else ['inventory unavailable']
            self.add_rule(
                rule, name, 'APPLICABLE',
                'WAITING_EVIDENCE' if gaps else 'READY',
                instances=checker.rule_instances(rule, inventory) if inventory else [],
                required_inputs=gaps, reason='检查器冷跑规则')

        by_rule = {}
        for check in self.checks:
            if check.get('rule'):
                by_rule.setdefault(check['rule'], []).append(check['id'])
        expect = self.intent.get('expect') or {}
        self.add_rule(
            'REQ-A01', catalog.title('REQ-A01'),
            'APPLICABLE' if expect else 'UNDETERMINED',
            'READY' if expect else 'WAITING_EVIDENCE',
            required_inputs=[] if expect else ['intent.expect'],
            reason='必须由设计意图定义“该有/该删”')
        for rule in BUILTIN_EVIDENCE_RULES:
            name = catalog.title(rule)
            instances = by_rule.get(rule, [])
            if instances:
                ready = all(next(x for x in self.checks if x['id'] == cid)[
                            'readiness'] == 'READY' for cid in instances)
                self.add_rule(
                    rule, name, 'APPLICABLE',
                    'READY' if ready else 'WAITING_EVIDENCE', instances=instances,
                    required_inputs=[] if ready else ['structured evidence'],
                    reason='由网表中的具体位号/网络实例化')
            else:
                self.add_rule(
                    rule, name, 'UNDETERMINED', 'WAITING_EVIDENCE',
                    required_inputs=['design intent/platform applicability'],
                    reason='网表未检测到实例，但不能据此直接判 NA')

        for rule, (name, checker) in sorted(registry_hot_rules().items()):
            instances = by_rule.get(rule, [])
            planned = [x for x in self.checks if x['id'] in instances]
            ready = bool(planned) and all(x['readiness'] == 'READY' for x in planned)
            self.add_rule(
                rule, name, 'APPLICABLE' if instances else 'UNDETERMINED',
                'READY' if ready else 'WAITING_EVIDENCE', instances=instances,
                required_inputs=[] if ready else ['structured evidence'],
                reason='检查器热跑规则；未检测到实例也不得直接判 NA')

        pintype = self.db.get('pintype', {})
        self.add_rule(
            'NET-A06', catalog.title('NET-A06'), 'APPLICABLE',
            'READY' if pintype else 'WAITING_EVIDENCE',
            required_inputs=[] if pintype else ['pintype/PINUSE'],
            reason='所有原理图均适用；输入缺失只影响准备度')

        if self.review_mode == 'first':
            self.add_rule(
                'REQ-H01', catalog.title('REQ-H01'),
                'NOT_APPLICABLE', 'NOT_SCHEDULED',
                reason='首审没有旧版对比基线')
        else:
            missing = []
            if not self.old_db_available:
                missing.append('old_db')
            if not self.claims_available:
                missing.append('review_claims')
            self.add_rule(
                'REQ-H01', catalog.title('REQ-H01'),
                'APPLICABLE', 'WAITING_EVIDENCE' if missing else 'READY',
                required_inputs=missing,
                reason='复审必须验证新旧网表与历史意见断言')

    def plan_coverage(self):
        for name, rule in catalog.COVERAGE_RULES.items():
            self.add_check(rule, {'feature': name}, trigger=['coverage-protocol'])
        for item in self.intent.get('requirements', []):
            self.add_check('REQ-D01', {'requirement_id': item['id'], 'feature': item['id']},
                           criterion=item['criterion'],
                           trigger=[item['citation'], item['text']])
        # The declared inventory includes symbol pins omitted from connected nets.
        devices = self.intent.get('devices') or {}
        for ref, part in sorted(self.db.get('parts', {}).items()):
            if not re.match(r'^(U|M|Q|D|J|P|CN)\d', ref, re.I) or part.get('nc'):
                continue
            device = devices.get(ref)
            gaps = [] if device and device['pinout_complete'] else [
                f'intent.devices.{ref}: official full pinout + exact MPN/package']
            trigger = [f'refdes:{ref}'] + ([f'intent.devices:{device["citation"]}'] if device else [])
            item = self._ready_check('DEV-D02', {'ref': ref}, gaps, trigger)
            if device:
                official_only, symbol_only = board_intent.pin_sets(self.db, ref, device)
                item['pin_difference'] = {'official_only': official_only, 'symbol_only': symbol_only}

    def plan_explicit_evidence(self):
        # Explicit targets must not disappear because their nets/pins lack a familiar name.
        for evidence in self.evidence.get('checks', []):
            if any(x.get('evidence_check_id') == evidence['id'] for x in self.checks):
                continue
            obj = {k: evidence[k] for k in ('node', 'net', 'ref') if evidence.get(k)}
            gaps = readiness_gaps(self.db, evidence, self.datasheet_audit, self.db_sha256)
            item = self.add_check(evidence['rule'], obj, key='PROVIDED',
                criterion='按对应 evidence_check_id 的条款核对显式目标与状态',
                readiness='WAITING_EVIDENCE' if gaps else 'READY',
                required_inputs=gaps)
            if not item.get('evidence_check_id'):
                # Invalid coordinates remain visible as waiting work, not fabricated matches.
                item['evidence_check_id'] = evidence['id']
                item['object']['state'] = (evidence.get('basis') or {}).get('state')

    def merge_previous_checks(self):
        """Carry manual checks forward on the same electrical baseline, never carry results."""
        previous = self.previous_plan
        if previous is None:
            return
        if not isinstance(previous, dict) or previous.get('schema_version') != PLAN_SCHEMA_VERSION:
            raise ValueError('merge plan schema_version must be %d; plans with retired check IDs must be regenerated'
                             % PLAN_SCHEMA_VERSION)
        if previous.get('db_sha256') != self.db_sha256:
            raise ValueError('merge plan must be bound to the current db_sha256; regenerate/review stale plans')
        for checker in REGISTRY:
            key = checker.plan_key
            if key in previous and previous[key] != self.inventories.get(checker.id):
                raise ValueError(key + ' inventory/state/assembly changed; regenerate and explicitly '
                                 'review/migrate prior checks')
        if previous.get('revision_impact_version') == 1:
            baseline = {'db_digest': revision_digest(self.old_db) if self.old_db is not None else None,
                        'plan_digest': revision_digest(self.old_plan) if self.old_plan is not None else None}
            if self.review_mode != 'revision' or previous.get('revision_impact', {}).get('baseline') != baseline:
                raise ValueError('merge plan revision baseline changed; supply the same old_db/old_plan')
        checks = previous.get('checks')
        if not isinstance(checks, list):
            raise ValueError('merge plan checks must be an array')
        current = {item['id']: item for item in self.checks}
        seen = set()
        identity = ('rule', 'method', 'domain', 'object', 'criterion', 'evidence_check_id', 'parent_check_id')
        for item in checks:
            if not isinstance(item, dict) or not _text(item.get('id')) or item['id'] in seen:
                raise ValueError('merge plan contains an invalid or duplicate check id')
            key = item['id']
            seen.add(key)
            if item.get('rule') == 'REQ-Q05' and previous.get('revision_impact_version') == 1:
                # Coverage is regenerated. Keep cold provisional removal records
                # even if hot evidence later restores the prior state check.
                continue
            if (not all(_text(item.get(k)) for k in ('rule', 'method', 'domain', 'criterion'))
                    or not isinstance(item.get('object'), dict)
                    or item.get('applicability') not in APPLICABILITY
                    or item.get('readiness') not in READINESS
                    or not isinstance(item.get('handoff'), dict)
                    or not isinstance(item['handoff'].get('required'), bool)):
                raise ValueError(f'{key}: incomplete merged check definition')
            spec_errors = catalog.spec_errors(item)
            if spec_errors:
                raise ValueError(f'{key}: ' + '; '.join(spec_errors))
            if key in current:
                if item['handoff'] != current[key]['handoff']:
                    raise ValueError(f'{key}: handoff details changed; resolve the plan explicitly')
                if any(item.get(field) != current[key].get(field) for field in identity):
                    raise ValueError(f'{key}: check identity/criterion changed; resolve the plan explicitly')
                continue
            # Final results live in review-results.json. Do not turn old plan annotations into verdicts.
            retained = deepcopy(item)
            retained['review_result'] = 'NA' if retained.get('applicability') == 'NOT_APPLICABLE' else None
            retained['evidence_confidence'] = None
            self.checks.append(retained)

    def generate(self):
        """生成全部自动计划项；计划构建与结果校验共用同一顺序。"""
        self.plan_coverage()
        self.plan_board()
        self.plan_packages()
        self.plan_concrete_checks()
        self.plan_checkers()
        self.plan_explicit_evidence()

    def build(self):
        self.generate()
        self.merge_previous_checks()
        for material in (self.datasheet_audit or {}).get('materials', []):
            if material.get('status') == 'NOT_FOUND':
                self.diagnostics.append({
                    'code': 'DATASHEET_NOT_FOUND',
                    'identity': material.get('identity'),
                    'refdes': material.get('refdes', []),
                    'message': material.get('message'),
                })
        self.checks.sort(key=lambda x: x['id'])
        self.plan_rules()
        self.rule_plan.sort(key=lambda x: x['rule'])
        applicability = Counter(x['applicability'] for x in self.checks)
        readiness = Counter(x['readiness'] for x in self.checks)
        plan = {
            'schema_version': PLAN_SCHEMA_VERSION,
            'generated_by': 'check-catalog planner',
            'db_sha256': self.db_sha256,
            'review_mode': self.review_mode,
            'result_model': {
                'review_result': list(RESULT_STATUSES),
                'handoff_is_independent': True,
                'handoff_states': list(HANDOFF_STATES),
            },
            'aggregate_release_gate': {
                'evaluate_after_per_check_review': True,
                'requirements': [
                    'no_unresolved_blocking_fail',
                    'no_unresolved_blocking_insufficient',
                    'all_applicable_checks_have_reviewed_results',
                    'p0_requires_verified_repair',
                    'risk_acceptance_preserves_fail_or_insufficient_with_authorized_record',
                    'required_handoffs_accepted_with_receiver_constraint_verification_and_evidence',
                    'revision_diff_and_claims_pass_when_applicable',
                ],
            },
            'summary': {
                'checks_total': len(self.checks),
                'applicability': dict(sorted(applicability.items())),
                'readiness': dict(sorted(readiness.items())),
                'handoff_required': sum(
                    1 for x in self.checks if x['handoff']['required']),
                'diagnostics': len(self.diagnostics),
                'datasheet_unresolved': (
                    (self.datasheet_audit or {}).get(
                        'summary', {}).get('unresolved')),
            },
            'datasheet_audit': {
                'provided': self.datasheet_audit is not None,
                'summary': (
                    (self.datasheet_audit or {}).get('summary')
                    if self.datasheet_audit is not None else None),
                'agent_requests': (
                    (self.datasheet_audit or {}).get('agent_requests', [])
                    if self.datasheet_audit is not None else []),
                'user_messages': (
                    (self.datasheet_audit or {}).get('user_messages', [])
                    if self.datasheet_audit is not None else []),
            },
            'rule_plan': self.rule_plan,
            'checks': self.checks,
            'diagnostics': self.diagnostics,
        }
        for checker in REGISTRY:
            inventory = self.inventories.get(checker.id)
            if inventory is None or checker.plan_key is None:
                continue
            plan[checker.plan_key] = inventory
            if checker.version_key is not None:
                plan[checker.version_key] = checker.version
        attach_metadata(plan, self.db, self.intent, self.evidence, self.datasheet_audit,
                        self.old_db, self.old_plan)
        plan['summary'].update(
            checks_total=len(plan['checks']),
            applicability=dict(sorted(Counter(c['applicability'] for c in plan['checks']).items())),
            readiness=dict(sorted(Counter(c['readiness'] for c in plan['checks']).items())))
        if plan.get('revision_impact'):
            history = next(r for r in plan['rule_plan'] if r['rule'] == 'REQ-H01')
            history['instances'] = sorted(set(history['instances']) |
                {e['check_id'] for e in plan['revision_impact']['entries'] if e['required']})
            if plan['revision_impact']['blocking_gaps']:
                history['readiness'] = 'WAITING_EVIDENCE'
                history['required_inputs'] = sorted(set(history['required_inputs']) |
                    set(plan['revision_impact']['blocking_gaps']))
        return plan


def build_review_plan(db, intent=None, evidence=None, review_mode=None,
                      old_db_available=False, claims_available=False,
                      datasheet_audit=None, previous_plan=None, old_db=None, old_plan=None):
    if evidence is not None:
        errors = validate_evidence(evidence)
        if errors:
            raise ValueError('evidence.json 无效: ' + '; '.join(errors))
    return ReviewPlanner(
        db, intent, evidence, review_mode, old_db_available,
        claims_available, datasheet_audit, previous_plan, old_db, old_plan).build()


def main():
    parser = argparse.ArgumentParser(
        description='按规则总表生成逐项检查计划（适用性、准备度与证据缺口）')
    parser.add_argument('db', help='parse_netlist.py 产出的 db.json')
    parser.add_argument('--intent', help='设计意图 JSON')
    parser.add_argument('--evidence', help='资料取证形成的结构化证据 JSON')
    parser.add_argument(
        '--datasheet-audit',
        help='audit_datasheets.py 产出的逐物料覆盖审计 JSON')
    parser.add_argument('--review-mode', choices=('first', 'revision'))
    parser.add_argument('--old-db', help='实际读取复审旧版 db.json 并生成变化清单')
    parser.add_argument('--old-plan', help='上一设计版本最终计划；不是本版冷跑 merge-plan')
    parser.add_argument('--revision-impact-json', help='另存本次改版影响与必需复验清单')
    parser.add_argument('--claims', help='历史意见断言 JSON（只判定可用性）')
    parser.add_argument('--json', required=True, help='写出 review-plan.json')
    parser.add_argument('--i2c-topology-json', help='另存本次生成的 I2C 连接覆盖清单')
    parser.add_argument('--decoupling-json', help='另存去耦连接/装配/标称容量清单；不是电气判决')
    args = parser.parse_args()

    for label, path in (('--old-db', args.old_db), ('--claims', args.claims)):
        if path and not os.path.isfile(path):
            sys.exit(f'[FATAL] {label} 文件不存在: {path}')

    try:
        db = load_json(args.db)
        intent = load_json(args.intent) if args.intent else None
        evidence = load_json(args.evidence) if args.evidence else None
        datasheet_audit = load_json(args.datasheet_audit) if args.datasheet_audit else None
        old_db = load_json(args.old_db) if args.old_db else None
        old_plan = load_json(args.old_plan) if args.old_plan else None
    except (OSError, ValueError) as error:
        parser.error(str(error))
    if args.intent and not isinstance(intent, dict):
        parser.error('explicit intent.json root must be an object')
    for supplied, value, label in ((args.old_db, old_db, '--old-db'), (args.old_plan, old_plan, '--old-plan')):
        if supplied and not isinstance(value, dict):
            parser.error(label + ' JSON root must be an object')
    errors = validate_intent(intent, db)
    if errors:
        sys.exit('[FATAL] intent.json 无效:\n  - ' + '\n  - '.join(errors))
    if evidence is not None:
        errors = validate_evidence(evidence)
        if errors:
            sys.exit('[FATAL] evidence.json 无效: ' + '; '.join(errors))
    if datasheet_audit is not None:
        errors = validate_datasheet_audit(datasheet_audit, db)
        if errors:
            sys.exit('[FATAL] datasheet-audit.json 无效:\n  - '
                     + '\n  - '.join(errors))
    try:
        plan = build_review_plan(
            db, intent, evidence, args.review_mode,
            old_db_available=bool(args.old_db), claims_available=bool(args.claims),
            datasheet_audit=datasheet_audit, old_db=old_db, old_plan=old_plan)
    except ValueError as error:
        parser.error(str(error))
    if args.revision_impact_json:
        if 'revision_impact' not in plan:
            parser.error('--revision-impact-json requires revision mode')
        with open(args.revision_impact_json, 'w', encoding='utf-8') as stream:
            json.dump(plan['revision_impact'], stream, ensure_ascii=False, indent=2, allow_nan=False)
    if args.i2c_topology_json:
        with open(args.i2c_topology_json, 'w', encoding='utf-8') as stream:
            json.dump(plan['i2c_topology'], stream, ensure_ascii=False, indent=2)
    if args.decoupling_json:
        with open(args.decoupling_json, 'w', encoding='utf-8') as stream:
            json.dump(plan['decoupling'], stream, ensure_ascii=False, indent=2, allow_nan=False)
    json.dump(plan, io.open(args.json, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)
    summary = plan['summary']
    print('=== 检查计划（规则总表展开） ===')
    print(f"  checks={summary['checks_total']}  "
          f"applicability={summary['applicability']}")
    print(f"  readiness={summary['readiness']}  "
          f"handoff_required={summary['handoff_required']}")
    print(f'  -> {args.json}')


if __name__ == '__main__':
    main()

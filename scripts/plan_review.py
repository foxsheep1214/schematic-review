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
from review_engine import engine_identity
from electrical_contract import PLAN_SCHEMA_VERSION, db_fingerprint, check_matches, readiness_gaps, validate_evidence, bounded, finite, load_json
from page_inventory import inventory as document_inventory, LIMITED
import io
import json
import os
import hashlib
import re
import sys
from collections import Counter
from checkers import REGISTRY, domains as domains_lib, passive_stress, registry_cold_rules, registry_hot_rules
import circuit_decisions
import check_key
import row_owner
import interfaces
from checkers import powertree
from checkers.netgraph import ANODE_NAMES, CATHODE_NAMES, RAIL_RE, is_ground, CAPACITOR, CONNECTOR, IC, MOSFET, RESISTOR, TESTPOINT, TVS, UNKNOWN, ZENER, NetGraph, is_analog_sense_pair, normalize
from checkers.planutil import empty_handoff as _empty_handoff, slug as _slug
from revision_impact import attach_metadata, digest as revision_digest, validate_declarations

from audit_datasheets import (
    datasheet_audit_all_available,
    datasheet_entry_for_ref,
    validate_datasheet_audit,
)


from review_workflow import PHASES

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
CONNECTOR_RE = interfaces.CONNECTOR_RE
# 保护门限脚与传感器只作发现线索：命中即生成计算项，不据名称判定门限或传感器类型。
PROTECT_PIN_RE = re.compile(
    r'^(FAULT\w*|FLT\w*|OVP\w*|UVP\w*|OV|UV|OVLO|UVLO|OCP\w*|OTP\w*|ILIM\w*|PROT\w*|TRIP\w*)$', re.I)
SENSOR_RE = re.compile(r'THERMISTOR|NTC|PTC|\bRTD\b|PT100|THERMOCOUPLE|热敏', re.I)
GROUND_RE = re.compile(r'^([A-Z]{0,2}GND[A-Z0-9]{0,3}|[AD]?VSS[A-Z0-9]{0,3}|EP|PAD)$', re.I)
# 阈值型保护两侧分别成项，避免只核一侧即通过。
WINDOW_SIDES = (
    ('NOTRIP', '不误动作侧：正常工况被测量最大值（全部输出档位、瞬态与上电/掉电、公差、温度、漏电，'
               '含峰值整流或滤波捕获的尖峰）低于门限最小值并留裕量，门限脚计入接收端内部钳位/上下拉的吸流；'
               '也可用有据的滤波/消隐及波形证明不形成有效触发'),
    ('TRIP', '动作有效侧：按受控故障及可接受终态核检测、执行、剩余能量和适用的保持/复位；正常及要求无损恢复的工况满足额定，允许破坏性安全失效的工况按其安全判据关闭'),
)
# 栅源稳压管/TVS 在正常驱动中允许限幅：不误动作侧改核“不妨碍规定导通”。
GATE_CLAMP_NOTRIP = ('不误动作侧（栅源限幅，正常驱动中允许钳位）：正常驱动窗口内钳位不妨碍所需导通栅压，'
                     '钳位电流与功耗（含驱动源限流）在器件额定内；不要求正常工作永不导通')
# 全板规则执行前需要的资料；未列出的规则只需网表。
BOARD_MATERIALS = {
    'DOC-D02': ('requirements',), 'DOC-V02': ('schematic_pdf',), 'REQ-D02': ('requirements',),
}
INTERFACE_MATERIALS = {'DEV-C04': ('datasheets', 'requirements')}
SYSTEM_MATERIALS = {'PWR-T06': ('datasheets', 'platform_checklist'), 'SIG-D13': ('datasheets', 'platform_checklist'),
                    'RST-T03': ('requirements', 'datasheets')}
OWNED_PART_MATERIALS = {'DEV-C01': ('datasheets', 'requirements'), 'DEV-C02': ('datasheets', 'requirements'),
                        'DEV-C03': ('requirements',)}
# 逐电路自有器件的检查项取哪些器件（第 5 步）：应力不含连接器（载流归 DEV-C04）与测试点。
OWNED_PART_KINDS = {'DEV-C01': lambda kind: kind not in (CONNECTOR, TESTPOINT),
                    'DEV-C02': lambda kind: kind == CAPACITOR, 'DEV-C03': lambda kind: kind == RESISTOR}


# 网表扫描规则所需的 db 索引；规则名称与判据在 catalog 中。
COLD_RULE_INDEXES = {
    'NET-A01': ['nets'], 'NET-A02': ['nets'],
    'NET-A03': ['nets', 'parts'], 'PWR-A01': ['nets', 'parts'],
    'PWR-A02': ['pinname'], 'PWR-A03': ['pinname'],
    'PRO-A01': ['nets', 'parts'], 'PRO-A02': ['nets', 'parts'],
    'NET-A04': ['nets'], 'PWR-A04': ['nets'], 'DOC-A03': ['parts'],
    'DOC-A04': ['parts'], 'DEV-A01': ['parts'], 'DEV-A02': ['parts', 'pinname'],
    'DEV-A03': ['parts', 'nets'], 'NET-A07': ['pintype'], 'SIG-A03': ['nets', 'parts'],
}
# 由网表实例化的内置证据计算规则。
BUILTIN_EVIDENCE_RULES = tuple(rule.id for rule in catalog.rules(stage='hot', source='lint'))


# Confirmation state of an intent requirement: 已确认（CONFIRMED）、提案（PROPOSED）、
# 未定（OPEN，判据依赖的数值未决定）、暂缓（DEFERRED，需求方明确暂缓）。 Both stay INSUFFICIENT with the matching gap_cause.
REQUIREMENT_STATUSES = ('CONFIRMED', 'PROPOSED', 'OPEN', 'DEFERRED')


def _text(value):
    return isinstance(value, str) and bool(value.strip())


_SQUEEZE_RE = re.compile(r'[\s，。；;,.、：:（）()]')


def _squeeze(value):
    return _SQUEEZE_RE.sub('', value)


def validate_intent(intent, db=None, candidates=None, require_candidates=False):
    """验证 intent；给出 db 时同时核对网表绑定。"""
    if intent is None:
        return []
    if not isinstance(intent, dict):
        return ['intent 根对象必须为 object']
    errors = []
    if 'schema_version' in intent and intent['schema_version'] != INTENT_SCHEMA_VERSION:
        errors.append('schema_version 必须为 %d' % INTENT_SCHEMA_VERSION)
    if intent.get('review_mode') not in (None, 'first', 'revision'):
        errors.append('review_mode 必须为 first/revision')
    if 'review_phase' in intent and intent['review_phase'] not in PHASES:
        errors.append('review_phase 必须为 ' + '/'.join(PHASES))
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
            if str(key).upper() not in catalog.CIRCUIT_TYPE_BY_NAME:
                errors.append(f'{label} 不是功能电路名（取 check-catalog.md 中的功能电路名）')
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
        kind = circuit.get('type')
        if not isinstance(kind, str) or kind not in catalog.CIRCUIT_TYPE_BY_NAME:
            errors.append('circuits.type 不支持: %r（取 check-catalog.md 中的功能电路名）' % (kind,))
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
            if _text(item.get('text')) and _text(item.get('criterion')) and \
                    _squeeze(item['criterion']) == _squeeze(item['text']):
                errors.append('requirement.%s.criterion 抄了需求原文；写本次在原理图上判什么、对照什么（优化目标或范围说明写明'
                              '没有原理图判据）' % item.get('id'))
            if 'status' in item and item['status'] not in REQUIREMENT_STATUSES:
                errors.append('requirement.status 须为 已确认（CONFIRMED）/提案（PROPOSED）/未定（OPEN）/暂缓（DEFERRED）之一，字段值写英文')
            rid = item.get('id')
            if _text(rid):
                if rid in seen:
                    errors.append(f'requirement id 重复: {rid}')
                seen.add(rid)
    if isinstance(intent, dict) and board_intent.VERIFIED_KEY in intent:
        # Only the datasheet audit may mark a device kind as verified.
        errors.append(board_intent.VERIFIED_KEY + ' 由手册核验生成，不能在 intent 中声明')
    errors.extend(board_intent.validate(intent, db))
    for checker in REGISTRY:
        errors.extend(checker.validate_intent(intent, db))
    errors.extend(validate_declarations(intent))
    candidate_based = 'circuit_decisions' in intent or 'circuit_candidates_sha256' in intent
    if candidates is None and (candidate_based or (require_candidates and intent.get('circuits'))):
        errors.append('intent.circuits come from record/circuit-candidates.json and intent.circuit_decisions; pass the '
                      'candidate file (--candidates) generated by circuit_candidates.py; a hand-drawn circuit list is not accepted')
    elif candidates is not None:
        errors.extend(circuit_decisions.validate(intent, candidates, db))
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
            if other in nets and not is_analog_sense_pair(net):
                found.add((net, other))
    return sorted(found)


# Two-terminal SMD/THT package names (chip sizes, SOD/SMA/DO/MELF, 2-lead THT LEDs); multi-pad LED
# packages (PLCC, RGB, thermal pad, numbered pin counts) never qualify.
TWO_TERMINAL_PACKAGE_RE = re.compile(
    r'(?<![0-9])(0201|0402|0603|0805|1206|1210|1812|2010|2512)(?![0-9])|SOD-?\d|(?<![A-Z])SM[ABCF](?![A-Z])|'
    r'DO-?\d{2,3}|MELF|(?<![A-Z])LED_D\d(\.\d+)?MM', re.I)
MULTI_PAD_PACKAGE_RE = re.compile(
    r'PLCC|RGB|XHP|THERMAL|(?<![A-Z])EP(?![A-Z])|[-_]\d(?:[-_]|$)|5050|3535|2835|WS28|SK68|APA1', re.I)
TWO_TERMINAL_REFDES_RE = re.compile(r'^(D|ZD|TVS|LED)\d', re.I)
NONPOLAR_PIN_NAMES = ({'A1', 'A2'}, {'1', '2'})
# Single-row 1/2-position connector footprints (pin header, screw terminal, wire-to-board);
# mounting/shield pads add physical pins the symbol may not show, so they never qualify.
SINGLE_ROW_CONNECTOR_RE = re.compile(r'(?<![0-9X])1X0?([12])(?![0-9])', re.I)
CONNECTOR_EXTRA_PAD_RE = re.compile(r'MOUNT|SHIELD|(?<![A-Z])MP(?![A-Z])|THERMAL|(?<![A-Z])EP(?![A-Z])', re.I)

class ReviewPlanner:
    def __init__(self, db, intent=None, evidence=None, review_mode=None,
                 old_db_available=False, claims_available=False,
                 datasheet_audit=None, previous_plan=None, old_db=None, old_plan=None, lint_findings=None,
                 candidates=None):
        self.db = db
        self.candidates = candidates
        self.lint_findings = lint_findings or []
        self.document_inventory = document_inventory(db)
        self.kind_intent = board_intent.with_verified_kinds(intent, datasheet_audit)
        analysis_db = board_intent.graph_db(db, self.kind_intent)
        self.inventories = {checker.id: checker.build(analysis_db, self.kind_intent) for checker in REGISTRY}
        self.domains = domains_lib.build_section(analysis_db, self.kind_intent)
        self.interfaces = interfaces.derive(db, intent or {}, datasheet_audit)
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
        self.functions = []
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
        """按规则总表生成一个计划项；ID = 规则编号[.实例键].对象。"""
        entry = catalog.get(rule)
        anchor = (obj.get('node') or obj.get('net') or obj.get('ref') or obj.get('feature')
                  or obj.get('circuit_type') or obj.get('assembly') or obj.get('page')
                  or obj.get('circuit') or obj.get('interface') or obj.get('system') or obj.get('board') or 'GLOBAL')
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
            item['aggregation'] = '逐电路/状态电路检查项完成后汇总，禁止整类电路一次性 PASS'
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

    def plan_circuit_types(self):
        """功能电路：名称仅生成待确认汇总项；声明/拓扑确认后展开成员，未发现的由 REQ-Q08 覆盖。"""
        declared = {str(key).upper(): value for key, value in self.intent.get('features', {}).items()}
        circuits = {}
        for circuit in self.intent.get('circuits', []):
            circuits.setdefault(circuit['type'], []).append(circuit)
        custom = [catalog.CircuitType(name, name, 'REQ', r'(?!x)x', (), ('requirements',))
                  for name in sorted(set(declared) - set(catalog.CIRCUIT_TYPE_BY_NAME))]
        undetected = []
        for kind in catalog.CIRCUIT_TYPES + tuple(custom):
            name = kind.name
            hits = _feature_hits(self.db, kind.pattern)
            topology_confirmed = name == 'I2C' and any(b['origin'] != 'name-hint'
                    for s in self.i2c_topology['states'] for b in s['buses'])
            if topology_confirmed:
                hits.append('declared I2C physical bus/port mapping')
            declared_circuits = circuits.get(name, [])
            found = hits + [f'intent.circuits:{c["id"]}' for c in declared_circuits]
            confirmed = bool(declared_circuits) or topology_confirmed
            item = declared.get(name)
            requested = item.get('applicability') if item else None
            trigger = [f'netlist:{x}' for x in hits]
            trigger += [f'intent.circuits:{c["citation"]}' for c in declared_circuits]
            if item and item.get('citation'):
                trigger.append(f'intent:{item["citation"]}')

            if requested == 'NOT_APPLICABLE' and confirmed:
                applicability = 'UNDETERMINED'
                self.diagnostics.append({
                    'code': 'INTENT_NETLIST_CONFLICT',
                    'feature': name,
                    'detail': '不适用声明与已确认拓扑或电路声明冲突；纯名称命中不构成冲突',
                    'hits': found,
                })
            elif requested in ('APPLICABLE', 'NOT_APPLICABLE'):
                applicability = requested
            elif confirmed:
                applicability = 'APPLICABLE'
            elif found:
                applicability = 'UNDETERMINED'
            elif item:
                applicability = 'UNDETERMINED'
            else:
                undetected.append(name)
                continue

            if applicability == 'NOT_APPLICABLE':
                missing = []
            elif applicability == 'UNDETERMINED':
                missing = [f'intent.features.{name}']
                if requested == 'NOT_APPLICABLE' and confirmed:
                    missing.append('resolve intent/netlist conflict')
            else:
                missing = self._materials_gap(kind.materials)
            if applicability == 'APPLICABLE' and requested == 'APPLICABLE' and not found:
                self.diagnostics.append({
                    'code': 'REQUIRED_FEATURE_NOT_DETECTED',
                    'feature': name,
                    'detail': '设计意图要求该功能，但网表未检测到对应特征',
                })
            summary = self.add_check(
                'REQ-Q07', {'circuit_type': name}, criterion=catalog.circuit_type_criterion(name),
                applicability=applicability, readiness='WAITING_EVIDENCE' if missing else 'READY',
                required_inputs=missing, trigger=trigger)
            summary['circuit_type'] = name
            if applicability == 'APPLICABLE' and requested == 'APPLICABLE' and not found:
                self.add_check('REQ-A02', {'circuit_type': name}, readiness='READY',
                               trigger=[f'intent:{item["citation"]}'])
            if applicability == 'APPLICABLE':
                self.plan_subjects(kind, declared_circuits, missing)
        unassigned = []
        if self.candidates:
            unassigned = circuit_decisions.discovery_refs(self.candidates, self.intent.get('circuit_decisions') or [])
        if undetected or unassigned:
            titles = [(name, catalog.circuit_type(name).title) for name in undetected]
            criterion = catalog.criterion('REQ-Q08')
            if undetected:
                criterion += '：' + '、'.join(name if title == name else f'{name}（{title}）' for name, title in titles)
            if unassigned:
                criterion += '；候选生成没有归属的器件，逐颗确认属于哪个功能或为何不审：' + '、'.join(unassigned)
            self.add_check(
                'REQ-Q08', {'board': 'BOARD', 'circuit_types': undetected, 'unassigned': unassigned},
                criterion=criterion,
                readiness='WAITING_EVIDENCE',
                required_inputs=[f'intent.features.{name}' for name in undetected]
                + [f'intent.circuit_decisions: add/reject for {ref}' for ref in unassigned],
                trigger=['circuit-type-discovery'] + (['circuit-candidates:unassigned'] if unassigned else []))

    def _rail_window(self, nets):
        """电路网络里 intent.power_rails 给了电压窗口的轨；没有就 None（问题写“需求未给窗口”）。"""
        rails = self.intent.get('power_rails') or {}
        parts = []
        for net in nets:
            window = (rails.get(net) or {}).get('voltage_v') if isinstance(rails.get(net), dict) else None
            if isinstance(window, dict) and finite(window.get('min')) and finite(window.get('max')):
                parts.append(f'{net} {window["min"]}–{window["max"]} V')
        return '、'.join(parts) or None

    def plan_subjects(self, kind, circuits, missing):
        """声明了电路则逐电路×工况展开电路检查项并建功能框架（答案不随工作态变化的规则每电路一行），
        否则按功能电路展开一次；已有 I²C 区域时由检查器逐区域展开。"""
        members = []
        for circuit in circuits:
            refs = circuit['refs']
            gaps = [f'datasheet:{ref}' for ref in refs
                    if not (datasheet_entry_for_ref(self.datasheet_audit, ref) or {}).get('status') == 'AVAILABLE']
            gaps += [f'unknown ref:{ref}' for ref in refs if ref not in self.db.get('parts', {})]
            trigger = f'intent.circuits:{circuit["citation"]}'
            for index, state in enumerate(circuit['states']):
                for rule in kind.subjects:
                    invariant = rule in catalog.STATE_INVARIANT
                    if invariant and index:
                        continue   # asked once per circuit, with the first state's rows
                    obj = {'circuit': circuit['id'], 'circuit_key': '+'.join(sorted(circuit.get('candidate_ids') or [circuit['id']])),
                           'ref': refs[0], 'refs': refs, 'nets': circuit.get('nets', [])}
                    if not invariant:
                        obj['state'] = state
                    key = circuit['id'] if invariant else f'{circuit["id"]}-{state}'
                    members.append((rule, obj, key, gaps, trigger))
        regions = any(state['regions'] for state in self.i2c_topology['states'])
        if not circuits and not (kind.name == 'I2C' and regions):
            for rule in kind.subjects:
                members.append((rule, {'circuit_type': kind.name}, None, missing, f'circuit-type:{kind.name}'))
        frames = {}
        for circuit in circuits:
            window = self._rail_window(circuit.get('nets', []))
            frames[circuit['id']] = {
                'id': 'FN-' + _slug(circuit['id']),
                'circuit': circuit['id'],
                'circuit_type': kind.name,
                'question': catalog.frame_question(kind.name, circuit['id'], circuit['refs'], circuit['states'], window),
                'objects': {'refs': list(circuit['refs']), 'nets': list(circuit.get('nets', []))},
                'states': list(circuit['states']),
                'members': [],
                'blind_spots': {rule: catalog.explanation(rule)['risk_if_omitted'] for rule in kind.subjects},
                'checklist': list(catalog.BOUNDING_STEPS),
            }
        for rule, obj, key, gaps, trigger in members:
            frame = frames.get(obj.get('circuit'))
            item = self._ready_check(rule, dict(obj), gaps, [trigger], key=key)
            item['circuit_type'] = kind.name
            item['analysis_required'] = True
            item['scope'] = '原理图电气条件；PCB/实测验证另建 HANDOFF'
            if frame is not None:
                item['question'] = catalog.question(rule, obj.get('state'), obj['circuit'], obj['refs'],
                                                    self._rail_window(obj['nets']))
                item['function_id'] = frame['id']
                item['aspect'] = catalog.title(rule)
                frame['members'].append({'check_id': item['id'], 'rule': rule, 'aspect': item['aspect'],
                                         'state': obj.get('state')})
        self.functions.extend(frames.values())

    def plan_checkers(self):
        """遍历检查器注册表；每个检查器只生成自己的计划项。"""
        for checker in REGISTRY:
            inventory = self.inventories.get(checker.id)
            if inventory is not None:
                checker.plan(self, inventory)

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
        connector_graph = NetGraph(board_intent.graph_db(db, self.kind_intent))
        for ref, part in sorted(db.get('parts', {}).items()):
            if part.get('nc') or not (CONNECTOR_RE.match(ref) or connector_graph.kind(ref) == CONNECTOR):
                continue
            connector_trigger = [f'refdes:{ref}',
                                 f'connector-kind:{connector_graph.basis(ref)}']
            obj = {'ref': ref}
            ready = self.evidence_ready('DEV-E01', obj)
            self.add_check(
                'DEV-E01', obj, readiness='READY' if ready else 'WAITING_EVIDENCE',
                required_inputs=[] if ready else ['connector drawing/opposite-side pinout'],
                trigger=connector_trigger)
            gaps, audit_trigger = self._datasheet_readiness(ref, part)
            port = {'interface': 'EXT-' + ref, 'ref': ref}   # the connector's interface (function tree, step 4)
            self._ready_check('DEV-D03', dict(port), self._materials_gap(['requirements']), connector_trigger)
            self._ready_check('DEV-C04', dict(port), self._materials_gap(INTERFACE_MATERIALS['DEV-C04']), connector_trigger)
            self._disposition_check(ref, gaps, connector_trigger + audit_trigger)
            self.add_check('PRO-D03', dict(port), trigger=connector_trigger)

        # 每条电源轨分别检查拓扑（连接追踪）和功耗预算（工程计算）。
        # 轨名不像电源（BULK、HVDC、PRI_AUX）但 intent.power_rails 已声明且确实供电的网同样是轨。
        declared_rails = powertree.declared_supply_nets(connector_graph, self.intent)
        for net in sorted(nets):
            if net in pseudo or is_ground(net) or not (RAIL_RE.match(net) or net in declared_rails):
                continue
            self.add_check('PWR-T01', {'net': net},
                           trigger=[f'rail-name:{net}' if RAIL_RE.match(net) else f'declared-rail:{net}'])
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
                required_inputs=missing, trigger=[f'rail-name:{net}'])

        # 差分连通（连接追踪）。
        for positive, negative in _differential_pairs(db):
            self.add_check(
                'SIG-T01', {'net_p': positive, 'net_n': negative, 'net': positive},
                trigger=[f'pair:{positive}/{negative}'])

        # 原生声明的页面独立于器件；旧格式只能覆盖已定位器件所在页。
        pdf_ready = _material_available(self.intent, 'schematic_pdf')
        for row in self.document_inventory['pages']:
            page = row['page']
            obj = {'page': page}
            if 'sheet_path' in row:
                obj['sheet_path'] = row['sheet_path']
            self.add_check(
                'DOC-V01', obj,
                readiness='READY' if pdf_ready else 'WAITING_EVIDENCE',
                required_inputs=[] if pdf_ready else ['schematic_pdf'],
                trigger=[f"{self.document_inventory['source']}:{page}"])
        if self.document_inventory['scope'] == LIMITED:
            self.diagnostics.append({'code': 'LIMITED_PAGE_INVENTORY',
                'message': 'Only component pages are known; native empty/root pages cannot be inferred.'})

        # 每颗 IC/模组和意图显式列出的关键器件逐颗核身份、引脚处置与工况。
        # 位号并非器件身份；连接器已有独立覆盖，不重复未用脚处置。
        # 位号不是 U/M 的有源器件（如 Reg1 稳压器）按原生电源脚识别：三脚以上、有 power_in/out、
        # 未归为分立器件或连接器。
        native = db.get('native_pintype') or {}
        powered = {node.split('.')[0] for node, kind in native.items() if kind in ('power_in', 'power_out')}

        def active_by_function(ref):
            return (ref in powered and len(connector_graph.pins_of(ref)) >= 3
                    and connector_graph.kind(ref) in (IC, UNKNOWN))

        for ref, part in sorted(db.get('parts', {}).items()):
            declared = ref in (self.intent.get('devices') or {})
            connector = CONNECTOR_RE.match(ref) or connector_graph.kind(ref) == CONNECTOR
            by_function = not DEVICE_RE.match(ref) and active_by_function(ref)
            if part.get('nc') or not (DEVICE_RE.match(ref) or by_function or (declared and not connector)):
                continue
            gaps, audit_trigger = self._datasheet_readiness(ref, part)
            trigger = ([f'refdes:{ref}', f'part:{part.get("part", "")}'] + audit_trigger
                       + (['native-power-pins:active-device'] if by_function else []))
            self._ready_check('DEV-D01', {'ref': ref}, gaps, trigger)
            self._disposition_check(ref, gaps, trigger)
            self._ready_check('DEV-C05', {'ref': ref}, gaps + self._materials_gap(['requirements']), trigger)

        self.plan_threshold_checks(connector_graph)

    def plan_threshold_checks(self, graph):
        """阈值型保护器件/门限脚两侧窗口（PRO-C02）与传感器开短路判别（ANA-C04），逐对象一项。"""
        db = self.db
        nets, pin2net = db.get('nets', {}), db.get('pin2net', {})
        names = dict(db.get('declared_pinname') or {}, **(db.get('pinname') or {}))
        parts = db.get('parts', {})
        requirements = self._materials_gap(['requirements'])

        def grounded(net):
            return is_ground(net) or bool(GROUND_RE.match(str(net).rsplit('/', 1)[-1]))

        def window(obj, gaps, trigger, gate_clamp=False):
            for side, criterion in WINDOW_SIDES:
                if gate_clamp and side == 'NOTRIP':
                    criterion = GATE_CLAMP_NOTRIP
                self._ready_check('PRO-C02', obj, gaps + requirements, trigger, key=side, criterion=criterion)

        def gate_source_clamp(ref):
            """两端分别在某只 MOS 的栅极网和源极网上。"""
            pins = set(graph.pins_of(ref).values())
            for other in parts:
                gate, source = (graph.node_named(other, role) for role in ('gate', 'source'))
                if (other != ref and graph.kind(other) == MOSFET and gate and source
                        and pins == {pin2net.get(gate), pin2net.get(source)}):
                    return other
            return None

        rails = powertree.PowerTree(graph)

        def connectors_on(net):
            return {node.split('.')[0] for node in nets.get(net, [])
                    if CONNECTOR_RE.match(node.split('.')[0]) or graph.kind(node.split('.')[0]) == CONNECTOR}

        def io_clamp_connectors(ref):
            """对外信号线 ESD 钳位：一端接地，其余端都是信号网（非轨、非开关节点）且直达连接器；
            由 PRO-D03 逐针覆盖。跨开关节点或浮地回流的 TVS 是能量钳位，仍按 PRO-C02 两侧核。"""
            pins = set(graph.pins_of(ref).values())
            live = [net for net in pins
                    if net and not grounded(net) and net not in db.get('pseudo_nets', [])]
            if (not live or len(live) == len(pins)
                    or any(rails.is_rail(net) or rails.is_switch_node(net) for net in live)):
                return set()
            return set().union(*(connectors_on(net) for net in live))

        for ref, part in sorted(parts.items()):
            if part.get('nc'):
                continue
            kind = graph.kind(ref)
            covering = [check for check in self.checks if check['rule'] == 'PRO-D03'
                        and check['object'].get('ref') in io_clamp_connectors(ref)] if kind == TVS else []
            if covering:
                for check in covering:
                    check['clamp_refs'] = sorted(set(check.get('clamp_refs', [])) | {ref})
                continue
            if kind in (ZENER, TVS):
                gaps, audit = self._datasheet_readiness(ref, part)
                switch = gate_source_clamp(ref)
                window({'ref': ref}, gaps, [f'refdes:{ref}', f'device-kind:{kind}:{graph.basis(ref)}'] + audit
                       + ([f'gate-source-clamp:{switch}'] if switch else []), gate_clamp=bool(switch))
                continue
            if not SENSOR_RE.search(' '.join(str(part.get(k, '')) for k in ('part', 'value', 'prim'))):
                continue
            # 传感器接电源轨的一端只是偏置，不是检测脚；轨上 IC 的供电脚也不判别开短路。
            for net in sorted(set(graph.pins_of(ref).values())):
                if (not net or grounded(net) or net in db.get('pseudo_nets', [])
                        or rails.is_rail(net)):
                    continue
                for node in sorted(nets.get(net, [])):
                    owner = node.split('.')[0]
                    if (owner == ref or graph.kind(owner) != IC or GROUND_RE.match(normalize(names.get(node)))
                            or (db.get('native_pintype') or {}).get(node) in ('power_in', 'power_out')):
                        continue
                    sensor_gaps, audit = self._datasheet_readiness(ref, part)
                    ic_gaps, ic_audit = self._datasheet_readiness(owner, parts.get(owner, {}))
                    self._ready_check(
                        'ANA-C04', {'ref': ref, 'node': node, 'net': net}, sensor_gaps + ic_gaps + requirements,
                        [f'sensor:{ref}', f'pinname:{names.get(node, "")}', f'net:{net}'] + audit + ic_audit,
                        key=ref)

        for node, pin in sorted(names.items()):
            ref, net = node.split('.')[0], pin2net.get(node)
            part = parts.get(ref) or {}
            if (not net or part.get('nc') or grounded(net) or graph.kind(ref) != IC
                    or not PROTECT_PIN_RE.match(normalize(pin))):
                continue
            gaps, audit = self._datasheet_readiness(ref, part)
            window({'node': node, 'net': net, 'ref': ref}, gaps, [f'pinname:{pin}', f'net:{net}'] + audit)

    def plan_rules(self):
        """规则级台账：自动扫描、证据计算、版本比对及按实例汇总的检测点规则。"""
        for rule, indexes in sorted(COLD_RULE_INDEXES.items()):
            missing = [key for key in indexes if not self.db.get(key)]
            self.add_rule(
                rule, catalog.title(rule), 'APPLICABLE',
                'WAITING_EVIDENCE' if missing else 'READY',
                required_inputs=missing, reason='只用网表的扫描规则')

        for rule, (name, checker) in sorted(registry_cold_rules().items()):
            inventory = self.inventories.get(checker.id)
            gaps = list(inventory.get('discovery_gaps', [])) if inventory else ['inventory unavailable']
            self.add_rule(
                rule, name, 'APPLICABLE',
                'WAITING_EVIDENCE' if gaps else 'READY',
                instances=checker.rule_instances(rule, inventory) if inventory else [],
                required_inputs=gaps, reason='检查器网表扫描规则')

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
                reason='检查器证据扫描规则；未检测到实例也不得直接判 NA')

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

    def _two_terminal_package(self, ref):
        """两脚符号（一阳一阴）配两端封装时返回封装名：脚集合由封装决定，无需原厂全脚表；
        焊盘与阴/阳极标记的对应属于 PCB 阶段。三脚及以上或封装名看不出两端时返回 None。"""
        names = dict(self.db.get('declared_pinname') or {}, **(self.db.get('pinname') or {}))
        nodes = {n for n in set(names) | set(self.db.get('pin2net') or {}) if n.partition('.')[0] == ref}
        if len(nodes) != 2:
            return None
        roles = sorted('A' if normalize(names.get(n)) in ANODE_NAMES else
                       'K' if normalize(names.get(n)) in CATHODE_NAMES else '?' for n in nodes)
        footprint = str((self.db.get('parts', {}).get(ref) or {}).get('jedec', ''))
        if (not TWO_TERMINAL_REFDES_RE.match(ref) or not TWO_TERMINAL_PACKAGE_RE.search(footprint)
                or MULTI_PAD_PACKAGE_RE.search(footprint)):
            return None
        if roles == ['A', 'K']:
            return footprint, ('two-pin anode/cathode symbol on a two-terminal package; '
                               'pad-to-polarity marking is a PCB-stage HANDOFF')
        if {normalize(names.get(n)) for n in nodes} in NONPOLAR_PIN_NAMES:
            return footprint, ('two-pin non-polar symbol (bidirectional) on a two-terminal package; '
                               'type and ratings are judged by their own checks')
        return None

    def _single_row_connector(self, ref):
        """1/2 位单排连接器：封装位数与符号脚号 1..N 一致、无安装/屏蔽焊盘时，脚集合由封装决定。"""
        footprint = str((self.db.get('parts', {}).get(ref) or {}).get('jedec', ''))
        match = SINGLE_ROW_CONNECTOR_RE.search(footprint)
        if not CONNECTOR_RE.match(ref) or not match or CONNECTOR_EXTRA_PAD_RE.search(footprint):
            return None
        names = dict(self.db.get('declared_pinname') or {}, **(self.db.get('pinname') or {}))
        pins = {n.partition('.')[2] for n in set(names) | set(self.db.get('pin2net') or {})
                if n.partition('.')[0] == ref}
        if pins != {str(i) for i in range(1, int(match.group(1)) + 1)}:
            return None
        return footprint, ('%s-position single-row connector footprint; symbol pins 1..%s match its '
                           'positions; signal meaning is judged by DEV-D03/DEV-E01' % (match.group(1), match.group(1)))

    def _kind_gap(self, ref):
        entry = ((self.datasheet_audit or {}).get('device_kinds') or {}).get(ref) or {}
        status = entry.get('status', 'NOT_AUDITED')
        hint = '; '.join(f"{c['kind']} p{c['page']} \"{c['snippet']}\"" for c in entry.get('candidates', [])[:3])
        return (f'intent.device_kinds.{ref}: datasheet page + verbatim quote stating the device type '
                f'(audit {status}' + (f'; candidates: {hint}' if hint else '') + (f'; {entry["detail"]}' if entry.get('detail') else '') + ')')

    def plan_coverage(self):
        for name, rule in catalog.COVERAGE_RULES.items():
            self.add_check(rule, {'feature': name}, trigger=['coverage-protocol'])
        for item in self.intent.get('requirements', []):
            obj = {'requirement_id': item['id'], 'feature': item['id']}
            if 'status' in item:
                obj['requirement_status'] = item['status']
            self.add_check('REQ-D01', obj,
                           criterion=item['criterion'],
                           trigger=[item['citation'], item['text']])
        # The declared inventory includes symbol pins omitted from connected nets.
        devices = self.intent.get('devices') or {}
        for ref, part in sorted(self.db.get('parts', {}).items()):
            if (not re.match(r'^(U|M|Q|D|J|P|CN)\d', ref, re.I)
                    and ref not in devices) or part.get('nc'):
                continue
            device = devices.get(ref)
            package = None if device else (self._two_terminal_package(ref) or self._single_row_connector(ref))
            if package:
                footprint, basis = package
                item = self._ready_check('DEV-D02', {'ref': ref}, [], [f'refdes:{ref}', f'two-terminal-package:{footprint}'])
                item['pin_difference'] = {'official_only': [], 'symbol_only': [], 'basis': basis}
                continue
            gaps = [] if device and device['pinout_complete'] else [
                f'intent.devices.{ref}: official full pinout + exact MPN/package']
            if re.match(r'^(Q|D|ZD|TVS|U|M)\d', ref, re.I) and ref not in board_intent.declared_kinds(self.kind_intent):
                # Discrete semiconductor type and integrated-circuit role come from the datasheet, not pin names
                # or the refdes prefix; the role decides which ICs anchor circuit candidates.
                gaps.append(self._kind_gap(ref))
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
        if previous.get('review_engine') != engine_identity():
            raise ValueError('merge plan uses changed/unknown SR rules; regenerate current checks, use old_plan only for history')
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
            retained.pop('check_explanation', None)
            retained['review_result'] = 'NA' if retained.get('applicability') == 'NOT_APPLICABLE' else None
            retained['evidence_confidence'] = None
            self.checks.append(retained)

    def attach_lint_findings(self):
        """Every A-rule FINDING/CANDIDATE becomes its own check; INFO becomes a plan diagnostic."""
        present = {c['id'] for c in self.checks}
        for finding in self.lint_findings:
            if not isinstance(finding, dict) or finding.get('check_id'):
                continue  # evidence (E) results are answered by their planned evidence checks
            if finding.get('kind') == 'INFO':
                self.diagnostics.append({'code': 'LINT_INFO', 'rule': finding.get('rule'),
                                         'detail': finding.get('detail')})
            elif finding.get('kind') in LINT_REVIEW_KINDS:
                check = lint_check(finding)
                if check['id'] not in present:
                    self.checks.append(check)
                    present.add(check['id'])

    def generate(self):
        """生成全部自动计划项；计划构建与结果校验共用同一顺序。"""
        self.plan_coverage()
        self.plan_board()
        self.plan_circuit_types()
        self.plan_concrete_checks()
        self.plan_checkers()
        self.plan_explicit_evidence()
        self.plan_interfaces()
        self.plan_system()
        self.plan_owned_parts()

    def plan_system(self):
        """系统功能的行（功能树设计第 5 步），有对象才生成：两个以上地网问 PWR-T06，两条以上电源轨问 RST-T03（全板一次），
        有可能是主控的 IC（核验为 mcu 或通用 ic，或没核验）问 SIG-D13。电源树和监控的行由逐轨展开和监控检查器生成。"""
        graph = NetGraph(board_intent.graph_db(self.db, self.kind_intent))
        grounds = sorted(self.domains['grounds'])
        rails = sorted(c['object']['net'] for c in self.checks if c['rule'] == 'PWR-T01' and (c.get('object') or {}).get('net'))
        if len(grounds) >= 2:
            self._ready_check('PWR-T06', {'system': 'SYS-GROUND', 'nets': grounds},
                              self._materials_gap(SYSTEM_MATERIALS['PWR-T06']), [f'grounds:{len(grounds)}'])
        if len(rails) >= 2:
            self._ready_check('RST-T03', {'system': 'SYS-SEQUENCE', 'rails': rails},
                              self._materials_gap(SYSTEM_MATERIALS['RST-T03']), [f'rails:{len(rails)}'])
        controllers = sorted(ref for ref in graph.parts if graph.is_fitted(ref) and graph.kind(ref) == IC
                             and graph.role_kind(ref) in (None, 'mcu', 'ic'))
        if controllers:
            self._ready_check('SIG-D13', {'system': 'SYS-PINMAP', 'refs': controllers},
                              self._materials_gap(SYSTEM_MATERIALS['SIG-D13']), [f'controller-candidates:{len(controllers)}'])

    def plan_owned_parts(self):
        """DEV-C01/C02/C03 每块电路对它拥有的器件一行（按 OWNED_PART_KINDS 取器件），没有电路拥有的器件全板一行。"""
        graph = NetGraph(board_intent.graph_db(self.db, self.kind_intent))
        circuits = self.intent.get('circuits', [])
        owners = row_owner.part_owners(circuits)
        fitted = [ref for ref in sorted(graph.parts) if graph.is_fitted(ref)]
        for rule in catalog.OWNED_PART_RULES:
            wanted = [ref for ref in fitted if OWNED_PART_KINDS[rule](graph.kind(ref))]
            gaps = self._materials_gap(OWNED_PART_MATERIALS[rule])
            for circuit in circuits:
                refs = [ref for ref in wanted if owners.get(ref) == circuit['id']]
                if refs:
                    key = '+'.join(sorted(circuit.get('candidate_ids') or [circuit['id']]))
                    self._ready_check(rule, {'circuit': circuit['id'], 'circuit_key': key, 'refs': refs}, gaps,
                                      [f'intent.circuits:{circuit["id"]}'])
            residual = [ref for ref in wanted if ref not in owners]
            if residual:
                self._ready_check(rule, {'board': 'BOARD', 'refs': residual}, gaps, ['board', 'unowned-parts'])

    def plan_system_frames(self):
        """每个有行的系统功能一个框架；成员是归它的行（按电路或接口展开的不算）。行没有点名网络或器件的
        （如逐电源域监控覆盖），框架的对象取全板电源轨。"""
        rails = sorted(c['object']['net'] for c in self.checks if c['rule'] == 'PWR-T01' and (c.get('object') or {}).get('net'))
        for sid in catalog.SYSTEM_FUNCTIONS:
            members = [c for c in self.checks if catalog.SYSTEM_OF_RULE.get(c['rule']) == sid
                       and not (c.get('object') or {}).get('circuit') and not (c.get('object') or {}).get('interface')]
            if not members:
                continue
            nets, refs = set(), set()
            for row in members:
                obj = row.get('object') or {}
                nets.update(n for key in ('nets', 'rails') for n in obj.get(key) or [])
                nets.update([obj['net']] if obj.get('net') else [])
                refs.update(obj.get('refs') or [])
            if not nets and not refs:
                nets.update(rails)
            frame = {'id': 'FN-' + sid, 'system': sid,
                     'question': catalog.system_frame_question(sid, sorted(nets), sorted(refs)),
                     'objects': {'refs': sorted(refs), 'nets': sorted(nets)}, 'states': ['run'], 'members': [],
                     'blind_spots': {}, 'checklist': list(catalog.BOUNDING_STEPS)}
            for row in sorted(members, key=lambda c: c['id']):
                row['function_id'] = frame['id']
                row['aspect'] = catalog.title(row['rule'])
                frame['members'].append({'check_id': row['id'], 'rule': row['rule'], 'aspect': row['aspect'], 'state': None})
                frame['blind_spots'][row['rule']] = catalog.explanation(row['rule'])['risk_if_omitted']
            self.functions.append(frame)

    def plan_interfaces(self):
        """接口检查项（功能树设计第 4 步）：电路对、链路逐接口问 catalog.INTERFACE_SUBJECTS，两端供电或参考地不同的
        网络问 SIG-C08，敏感电路取电的轨问 PWR-C14；连接器的三行在连接器循环里生成。电路对、链路和连接器各建一个框架。"""
        circuit_types = {c['id']: c.get('type') for c in self.intent.get('circuits', [])}
        role_gaps = {}
        for gap in self.interfaces['gaps']:
            role_gaps.setdefault(gap['interface'], []).append(
                f'interface-role:{gap["pin"]}' if gap['reason'] == 'role' else f'rail-source:{gap["interface"]}')
        for item in self.interfaces['interfaces']:
            iid, kind = item['id'], item['kind']
            nets = [n['net'] for n in item['nets']]
            parts = sorted({e['pin'].partition('.')[0] for n in item['nets'] for e in n['endpoints'] if e['owner']})
            gaps = role_gaps.get(iid, []) + [
                f'datasheet:{ref}' for ref in parts if self.db.get('parts', {}).get(ref) and powertree.IC_REF_RE.match(ref)
                and not (datasheet_entry_for_ref(self.datasheet_audit, ref) or {}).get('status') == 'AVAILABLE']
            trigger = [f'interface:{iid}']
            if kind == 'SUPPLY':
                loads = [o for o in item.get('loads', []) if circuit_types.get(o) in catalog.NOISE_SENSITIVE_TYPES]
                if loads:
                    row = self._ready_check('PWR-C14', {'interface': iid, 'net': nets[0], 'loads': loads}, gaps, trigger)
                    row['question'] = catalog.interface_question('PWR-C14', iid, nets, loads=loads)
                continue
            if kind != 'EXTERNAL' and not nets:
                continue
            for rule in catalog.INTERFACE_SUBJECTS.get(kind, ()) if kind != 'EXTERNAL' else ():
                row = self._ready_check(rule, {'interface': iid, 'nets': nets}, gaps, trigger)
                row['question'] = catalog.interface_question(rule, iid, nets, parts)
            for rule in catalog.INTERFACE_NET_SUBJECTS.get(kind, ()):
                for entry in item['nets']:
                    if entry['cross_supply']:
                        row = self._ready_check(rule, {'interface': iid, 'net': entry['net']}, gaps, trigger, key=iid)
                        row['question'] = catalog.interface_question(rule, iid, [entry['net']])
            members = [c for c in self.checks if (c.get('object') or {}).get('interface') == iid]
            if not members:
                continue
            frame = {'id': 'FN-' + _slug(iid), 'interface': iid, 'interface_kind': kind,
                     'question': catalog.interface_frame_question(kind, iid, item['owners'], nets, parts),
                     'objects': {'refs': parts, 'nets': nets}, 'states': ['run'], 'members': [],
                     'blind_spots': {}, 'checklist': list(catalog.BOUNDING_STEPS)}
            for row in members:
                if kind == 'EXTERNAL':
                    row['question'] = catalog.interface_question(row['rule'], iid, nets, [row['object']['ref']])
                row['function_id'] = frame['id']
                row['aspect'] = catalog.title(row['rule'])
                frame['members'].append({'check_id': row['id'], 'rule': row['rule'], 'aspect': row['aspect'], 'state': None})
                frame['blind_spots'][row['rule']] = catalog.explanation(row['rule'])['risk_if_omitted']
            self.functions.append(frame)

    def build(self):
        self.generate()
        self.merge_previous_checks()
        self.attach_lint_findings()
        self.plan_system_frames()
        for material in (self.datasheet_audit or {}).get('materials', []):
            if material.get('status') == 'NOT_FOUND':
                self.diagnostics.append({
                    'code': 'DATASHEET_NOT_FOUND',
                    'identity': material.get('identity'),
                    'refdes': material.get('refdes', []),
                    'message': material.get('message'),
                })
        for conflict in self.domains['conflicts']:
            self.diagnostics.append(dict(conflict, detail='参考地分区按地的直流连通推导；与 power_rails.<网>.domain 的声明不一致，改声明或改网表'))
        self.checks.sort(key=lambda x: x['id'])
        self.plan_rules()
        self.rule_plan.sort(key=lambda x: x['rule'])
        applicability = Counter(x['applicability'] for x in self.checks)
        readiness = Counter(x['readiness'] for x in self.checks)
        plan = {
            'schema_version': PLAN_SCHEMA_VERSION,
            'generated_by': 'check-catalog planner',
            'db_sha256': self.db_sha256,
            'page_inventory': self.document_inventory,
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
            'functions': sorted(self.functions, key=lambda x: x['id']),
            'diagnostics': self.diagnostics,
            'domains': self.domains,
        }
        if self.candidates:
            plan['circuit_candidates'] = {
                'db_sha256': self.candidates.get('db_sha256'), 'rules_version': self.candidates.get('rules_version'),
                'candidates': [c['id'] for c in self.candidates.get('candidates', [])],
                'decisions': len(self.intent.get('circuit_decisions') or []),
                'unassigned': circuit_decisions.discovery_refs(self.candidates, self.intent.get('circuit_decisions') or []),
            }
        if 'review_phase' in self.intent:
            plan['review_phase'] = self.intent['review_phase']
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
        # 规则说明每条规则存一份；对象化说明写在结果行。
        for check in plan['checks']:
            check.pop('check_explanation', None)
        plan['check_explanations'] = catalog.explanations_for(c['rule'] for c in plan['checks'])
        plan['check_explanations_version'] = catalog.EXPLANATION_VERSION
        circuits = self.intent.get('circuits', [])
        parts = row_owner.part_owners(circuits)
        nets = row_owner.interface_nets(self.interfaces)
        for check in plan['checks']:   # merge plan §5: rows are compared by what they ask, not by their ids or names
            check['check_key'] = check_key.key(check)
            check['owner'] = row_owner.owner(check, parts, nets)
        plan['owners'] = row_owner.table(circuits, parts)
        plan['interfaces'] = self.interfaces
        plan['summary']['owners'] = row_owner.counts(plan['checks'])
        return plan


LINT_REVIEW_KINDS = ('FINDING', 'CANDIDATE')


def lint_check_id(finding):
    """Stable check ID for one automatic-scan finding: rule, the object the detail names first, and a
    short digest of the detail so two findings on one object stay apart."""
    detail = str(finding.get('detail') or '')
    head = re.split(r'[\s:：(（\[,，;；<]', detail.strip(), maxsplit=1)[0] or 'BOARD'
    slug = re.sub(r'[^A-Z0-9]+', '-', head.upper()).strip('-')[:24] or 'BOARD'
    digest = hashlib.sha1((finding.get('rule', '') + '\n' + detail).encode('utf-8')).hexdigest()[:6]
    return '%s.%s-%s' % (finding.get('rule'), slug, digest)


def lint_check(finding):
    """The plan row that answers one A-rule finding. The reviewer gives it a normal result:
    FAIL when the finding holds, PASS with the reason it does not (naming the check that settles it),
    INSUFFICIENT when it cannot be settled yet."""
    rule = finding['rule']
    obj = {'lint_detail': str(finding.get('detail') or '')}
    if isinstance(finding.get('ref'), str) and finding['ref'].strip():
        obj['ref'] = finding['ref']
    return {'id': lint_check_id(finding), 'rule': rule, 'method': catalog.method_of(rule),
            'domain': catalog.domain_of(rule), 'object': obj,
            'criterion': '%s：%s' % (finding.get('name') or catalog.title(rule), finding.get('detail') or ''),
            'applicability': 'APPLICABLE', 'readiness': 'READY', 'required_inputs': [],
            'trigger': ['lint:' + finding.get('kind', 'FINDING')], 'lint_kind': finding.get('kind'),
            'handoff': {'required': False, 'state': None}, 'review_result': None, 'evidence_confidence': None}


def build_review_plan(db, intent=None, evidence=None, review_mode=None,
                      old_db_available=False, claims_available=False,
                      datasheet_audit=None, previous_plan=None, old_db=None, old_plan=None, lint_findings=None,
                      candidates=None):
    if evidence is not None:
        errors = validate_evidence(evidence)
        if errors:
            raise ValueError('evidence.json 无效: ' + '; '.join(errors))
    return ReviewPlanner(
        db, intent, evidence, review_mode, old_db_available,
        claims_available, datasheet_audit, previous_plan, old_db, old_plan, lint_findings, candidates=candidates).build()


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
    parser.add_argument('--old-plan', help='上一设计版本最终计划；不是本版网表扫描 merge-plan')
    parser.add_argument('--revision-impact-json', help='另存本次改版影响与必需复验清单')
    parser.add_argument('--claims', help='历史意见断言 JSON（只判定可用性）')
    parser.add_argument('--json', required=True, help='写出 review-plan.json')
    parser.add_argument('--candidates', help='circuit_candidates.py 生成的 record/circuit-candidates.json；intent 声明电路时必需')
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
        candidates = load_json(args.candidates) if args.candidates else None
    except (OSError, ValueError) as error:
        parser.error(str(error))
    if args.intent and not isinstance(intent, dict):
        parser.error('explicit intent.json root must be an object')
    for supplied, value, label in ((args.old_db, old_db, '--old-db'), (args.old_plan, old_plan, '--old-plan')):
        if supplied and not isinstance(value, dict):
            parser.error(label + ' JSON root must be an object')
    errors = validate_intent(intent, db, candidates=candidates, require_candidates=True)
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
    from lint import Lint  # the scan findings are part of the plan; lint imports this module
    try:
        plan = build_review_plan(
            db, intent, evidence, args.review_mode,
            old_db_available=bool(args.old_db), claims_available=bool(args.claims),
            datasheet_audit=datasheet_audit, old_db=old_db, old_plan=old_plan,
            lint_findings=Lint(db, None, intent, evidence, datasheet_audit).run(), candidates=candidates)
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
    gaps = passive_stress.rail_gaps(plan)
    if gaps:
        print('  未声明电压的轨（阻塞阻容预判的行数）：' + '、'.join('%s(%d)' % item for item in gaps.items()))
        print('    能从稳压器手册或需求定出时补 intent.power_rails.<轨>.voltage_v 后重跑')
    grounds = passive_stress.ground_domains(db, intent)
    if grounds:
        print('  按 0 V 处理的地网及参考地分区：' + '；'.join('%s=%s' % (k, '/'.join(v)) for k, v in grounds.items()))
        if len(grounds) > 1:
            print('    不同域之间的两端件不出预判；实为同一参考的地在 power_rails.<网> 写相同 domain')
    nodes = passive_stress.node_gaps(plan)
    if nodes:
        print('  无界节点/跨域（阻塞阻容预判的行数）：' + '、'.join('%s(%d)' % item for item in list(nodes.items())[:12]))
        print('    栅极/检测/开关节点可按计算给 power_rails.<网>.voltage_v；隔离地给 domain；不能定界的留审查者计算')
    print(f'  -> {args.json}')


if __name__ == '__main__':
    main()

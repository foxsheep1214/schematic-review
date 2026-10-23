#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查计划生成：按规则总表（scripts/catalog.py）把审查展开为逐项计划。

这个脚本只回答“哪些检查需要执行、按什么规则和方式执行、还缺什么证据”，
不提前给 PASS/FAIL。每个计划项带规则编号、检查方式与内容域，检查 ID 以
规则编号开头。HANDOFF 是独立下游动作，可以与后续 PASS/FAIL/INSUFFICIENT 并存。

用法：
    python3 plan_review.py db.json --intent intent.json \
        --datasheet-audit datasheet-audit.json --json review-plan.json
"""
import argparse
from copy import deepcopy
import board_intent
import catalog
from review_engine import engine_identity
from electrical_contract import PLAN_SCHEMA_VERSION, db_fingerprint, bounded, finite, load_json
from page_inventory import inventory as document_inventory
import io
import json
import os
import hashlib
import re
import sys
from collections import Counter
from checkers import REGISTRY, domains as domains_lib, passive_stress, powertree
from checkers.netgraph import NetGraph, RAIL_RE
import circuit_decisions
import check_key
import row_owner
import interfaces
import requirement_bindings
import requirement_parameters
import independence
import requirements_extract
import rule_gaps
import plan_board
import plan_circuits
import plan_system
from checkers.planutil import empty_handoff as _empty_handoff, slug as _slug
from revision_impact import attach_metadata, digest as revision_digest, validate_declarations

from audit_datasheets import (
    datasheet_entry_for_ref,
    validate_datasheet_audit,
)


from review_workflow import PHASES
from plan_board import BOARD_MATERIALS, COLD_RULE_INDEXES, _material_available, _text  # noqa: F401 (re-exported)
from plan_circuits import OWNED_PART_MATERIALS, _differential_pairs  # noqa: F401
from plan_system import SYSTEM_MATERIALS  # noqa: F401

INTENT_SCHEMA_VERSION = 4
APPLICABILITY = ('APPLICABLE', 'NOT_APPLICABLE', 'UNDETERMINED')
READINESS = ('READY', 'WAITING_EVIDENCE', 'NOT_SCHEDULED')
RESULT_STATUSES = ('PASS', 'FAIL', 'INSUFFICIENT', 'NA')
HANDOFF_STATES = ('OPEN', 'ACCEPTED', 'VERIFIED')

# Confirmation state of an intent requirement: 已确认（CONFIRMED）、提案（PROPOSED）、
# 未定（OPEN，判据依赖的数值未决定）、暂缓（DEFERRED，需求方明确暂缓）。 Both stay INSUFFICIENT with the matching gap_cause.
REQUIREMENT_STATUSES = ('CONFIRMED', 'PROPOSED', 'OPEN', 'DEFERRED')


_SQUEEZE_RE = re.compile(r'[\s，。；;,.、：:（）()]')


def _squeeze(value):
    return _SQUEEZE_RE.sub('', value)


def rail_candidates(db, intent):
    """{net: 'name' | 'declared' | 'excluded' | 'unconfirmed'} for every net that behaves as a supply on the netlist
    (fixed requirements, step 5): a net without a rail name is a rail only when power_rails declares it."""
    rails = intent.get('power_rails') if isinstance(intent.get('power_rails'), dict) else {}
    excluded = intent.get('rail_exclusions') if isinstance(intent.get('rail_exclusions'), dict) else {}
    out = {}
    for net in sorted(powertree.supply_candidates(NetGraph(board_intent.graph_db(db, intent)), intent)):
        out[net] = ('name' if RAIL_RE.match(net) else 'declared' if net in rails
                    else 'excluded' if net in excluded else 'unconfirmed')
    return out


def _rail_errors(intent, db):
    excluded = intent.get('rail_exclusions', {})
    if not isinstance(excluded, dict):
        return ['rail_exclusions 必须为按网络名索引的 object（值写不是电源轨的依据）']
    if not isinstance(db, dict) or not isinstance(db.get('nets'), dict):
        return []   # the netlist is checked on its own
    found, rails, errors = rail_candidates(db, intent), intent.get('power_rails') or {}, []
    for net, status in found.items():
        if status == 'unconfirmed':
            errors.append('power_rails: 网 %s 在网表上像电源（有 IC 从它取电或大电容到地），名字不像轨；'
                          '声明成轨（power_rails）或在 rail_exclusions 写它不是轨的依据' % net)
    for net, reason in excluded.items():
        if found.get(net) not in ('excluded', 'declared'):
            errors.append('rail_exclusions.%s 不是待确认的电源网；只排除网表上像电源、名字不像轨的网' % net)
        if net in rails:
            errors.append('rail_exclusions.%s 已在 power_rails 声明成轨，二者只取一个' % net)
        if not _text(reason):
            errors.append('rail_exclusions.%s 须写依据' % net)
    return errors


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
    candidate_based = 'circuit_decisions' in intent or 'circuit_candidates_sha256' in intent
    circuit_types = {c.get('type') for c in intent.get('circuits') or [] if isinstance(c, dict)}
    if not isinstance(features, dict):
        errors.append('features 必须为 object')
    else:
        for key, item in features.items():
            label = f'features.{key}'
            if str(key).upper() not in catalog.CIRCUIT_TYPE_BY_NAME:
                errors.append(f'{label} 不是功能电路名（取 check-catalog.md 中的功能电路名）')
                continue
            if candidate_based and str(key).upper() in circuit_types:
                errors.append(f'{label} 不写：这类电路由候选与电路决定推出（intent.circuits 已有）')
                continue
            if candidate_based and isinstance(item, dict) and item.get('applicability') == 'APPLICABLE':
                errors.append(f'{label} 不写 APPLICABLE：候选没检出这类电路；要审就在 circuit_decisions 里补电路，'
                              '只对规则总表有、候选没检出的类别写不适用（NOT_APPLICABLE）依据')
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
            if 'available' in item:
                errors.append(f'{label}.available 不写：资料是否可用由 path 指向的文件是否存在推出')
            if not _text(item.get('path')):
                errors.append(f'{label}.path 缺失：写资料文件或目录的路径')
            elif not os.path.exists(item['path']):
                errors.append(f'{label}.path {item["path"]} 不存在')
            if item.get('available') and not _text(item.get('citation')):
                errors.append(f'{label}.citation 缺失')
    errors.extend(requirement_parameters.rail_errors(intent))
    errors.extend(_rail_errors(intent, db))
    rails = requirement_parameters.resolve(intent).get('power_rails', {})
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
        source, source_errors = (requirements_extract.load(intent.get('requirement_source'))
                                 if requirements or 'requirement_source' in intent else (None, []))
        errors.extend(source_errors)
        originals = {i['id']: requirements_extract.text(i) for i in (source or {}).get('items', [])}
        for item in requirements:
            if not isinstance(item, dict):
                errors.append('requirement 必须为 object')
                continue
            for key in ('text', 'citation'):
                if key in item:
                    errors.append('requirement.%s.%s 不写：原文与出处由 requirements_extract.py 从 requirement_source 抄录'
                                  % (item.get('id'), key))
            if 'criterion' in item:
                errors.append('requirement.%s.criterion 不写：判据由类别的审查方面模板生成；对需求的理解写 interpretation'
                              % item.get('id'))
            for key in ('id', 'interpretation'):
                if not _text(item.get(key)):
                    errors.append(f'requirement.{key} 缺失')
            categories = item.get('categories')
            if not isinstance(categories, list) or not categories:
                errors.append('requirement.%s.categories 须为非空数组，取 check-catalog.md 需求类别表的类别' % item.get('id'))
            else:
                for category in categories:
                    if category not in catalog.REQUIREMENT_CATEGORIES:
                        errors.append('requirement.%s.categories 不支持: %r（取需求类别表的类别）' % (item.get('id'), category))
                if len(set(map(str, categories))) != len(categories):
                    errors.append('requirement.%s.categories 重复' % item.get('id'))
            if source is not None and _text(item.get('id')) and item['id'] not in originals:
                errors.append('requirement.%s 不在 requirement_source 里；需求只取自需求文档' % item['id'])
            original = originals.get(item.get('id'))
            if 'parameters' in item:
                errors.extend(requirement_parameters.errors(item.get('id'), item['parameters'], original))
            if 'owners' in item and (not isinstance(item['owners'], list) or not item['owners']
                                     or not all(_text(x) for x in item['owners'])):
                errors.append('requirement.%s.owners 须为非空字符串数组（电路、接口或系统功能的 id）' % item.get('id'))
            if original and _text(item.get('interpretation')) and _squeeze(item['interpretation']) == _squeeze(original):
                errors.append('requirement.%s.interpretation 抄了需求原文；写这条需求要在原理图上落实什么' % item.get('id'))
            if 'status' in item and item['status'] not in REQUIREMENT_STATUSES:
                errors.append('requirement.status 须为 已确认（CONFIRMED）/提案（PROPOSED）/未定（OPEN）/暂缓（DEFERRED）之一，字段值写英文')
            rid = item.get('id')
            if _text(rid):
                if rid in seen:
                    errors.append(f'requirement id 重复: {rid}')
                seen.add(rid)
        for rid in sorted(set(originals) - seen):
            errors.append('requirement %s 在需求文档里却不在 intent.requirements：每条需求都要有一项（优化目标、明确排除也一样）' % rid)
        parts = db.get('parts') if isinstance(db, dict) and isinstance(db.get('parts'), dict) else None
        errors.extend(requirement_parameters.mission_profile_errors(intent, originals, parts))
    if isinstance(intent, dict) and board_intent.VERIFIED_KEY in intent:
        # Only the datasheet audit may mark a device kind as verified.
        errors.append(board_intent.VERIFIED_KEY + ' 由手册核验生成，不能在 intent 中声明')
    errors.extend(board_intent.validate(intent, db))
    for checker in REGISTRY:
        errors.extend(checker.validate_intent(intent, db))
    errors.extend(validate_declarations(intent))
    errors.extend(rule_gaps.errors(intent, db))
    errors.extend(independence.intent_errors(intent))
    candidate_based = 'circuit_decisions' in intent or 'circuit_candidates_sha256' in intent
    if candidates is None and (candidate_based or (require_candidates and intent.get('circuits'))):
        errors.append('intent.circuits come from record/circuit-candidates.json and intent.circuit_decisions; pass the '
                      'candidate file (--candidates) generated by circuit_candidates.py; a hand-drawn circuit list is not accepted')
    elif candidates is not None:
        errors.extend(circuit_decisions.validate(intent, candidates, db))
    return errors


class ReviewPlanner(plan_circuits.CircuitPlanning, interfaces.InterfacePlanning, plan_system.SystemPlanning,
                    plan_board.BoardPlanning):
    """计划的主流程：加行、合并上一份计划、挂接扫描发现、汇总成计划；按功能树的各层（电路、接口、系统功能、全板）
    在各自模块里展开。"""
    def __init__(self, db, intent=None, review_mode=None,
                 old_db_available=False, claims_available=False,
                 datasheet_audit=None, previous_plan=None, old_db=None, old_plan=None, lint_findings=None,
                 candidates=None):
        self.db = db
        self.candidates = candidates
        self.lint_findings = lint_findings or []
        self.document_inventory = document_inventory(db)
        # The checkers read the windows a requirement gives (fixed requirements, step 3), like the netlist scan does.
        self.kind_intent = board_intent.with_verified_kinds(
            requirement_parameters.resolve(intent) if isinstance(intent, dict) else intent, datasheet_audit)
        analysis_db = board_intent.graph_db(db, self.kind_intent)
        self.inventories = {checker.id: checker.build(analysis_db, self.kind_intent) for checker in REGISTRY}
        self.domains = domains_lib.build_section(analysis_db, self.kind_intent)
        self.interfaces = interfaces.derive(db, intent or {}, datasheet_audit)
        self.i2c_topology = self.inventories['i2c_topology']
        self.decoupling = self.inventories['decoupling']
        self.db_sha256 = db_fingerprint(db)
        self.intent = requirement_parameters.resolve(intent or {})
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


    def plan_checkers(self):
        """遍历检查器注册表；每个检查器只生成自己的计划项。"""
        for checker in REGISTRY:
            inventory = self.inventories.get(checker.id)
            if inventory is not None:
                checker.plan(self, inventory)


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
        identity = ('rule', 'method', 'domain', 'object', 'criterion')
        for item in checks:
            if not isinstance(item, dict) or not _text(item.get('id')) or item['id'] in seen:
                raise ValueError('merge plan contains an invalid or duplicate check id')
            key = item['id']
            seen.add(key)
            if item.get('rule') == 'REQ-Q05' and previous.get('revision_impact_version') == 1:
                continue   # coverage is regenerated
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
            if rule_gaps.unwritten(item):   # fixed requirements, step 7: an added row is a registered rule gap
                raise ValueError(rule_gaps.message(key))
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
            if not isinstance(finding, dict):
                continue
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
        self.plan_interfaces()
        self.plan_system()
        self.plan_owned_parts()
        rule_gaps.plan(self)
        self.plan_stress_conditions()


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
        unread = passive_stress.unread_values(self.db)
        if unread:   # a value the parser cannot read is reported, not dropped in silence
            self.diagnostics.append({'code': 'RESISTOR_VALUE_UNREAD', 'values': unread,
                                     'message': '阻值读不出；改成 阻值[/公差][/额定功率][/额定电压][/封装] 的写法或确认阻值后重跑'})
        worded = passive_stress.word_values(self.db)
        if worded:   # the value is read; the word after it is a requirement the BOM has to state
            self.diagnostics.append({'code': 'RESISTOR_VALUE_WORD', 'values': worded,
                                     'message': '阻值照读；值后面的词（如 pulse）说不清要求，写成 BOM 规格（抗脉冲能量、额定电压等）'})
        assumed = passive_stress.assumed_package_refs(self.inventories.get('passive_stress'))
        if assumed:   # judged on an assumed package, said where the designer reads it
            self.diagnostics.append({'code': 'PASSIVE_PACKAGE_UNKNOWN', 'refs': assumed,
                                     'message': '没有封装：按 %s 的额定预判，值里写了额定的按所写' % passive_stress.ASSUMED_PACKAGE})
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
            'functions': sorted((self._with_bom_specs(f) for f in self.functions), key=lambda x: x['id']),
            'conditions': {name: requirement_parameters.windows(self.intent, name) for name in sorted(
                {n for names in requirement_parameters.STRESS_CONDITIONS.values() for n in names})
                if requirement_parameters.windows(self.intent, name)},
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
        attach_metadata(plan, self.db, self.intent, self.datasheet_audit,
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
        plan['assemblies'] = check_key.assembly_map(self.intent.get('assemblies'))
        for check in plan['checks']:   # merge plan §5: rows are compared by what they ask, not by their ids or names
            check['check_key'] = check_key.key(check, plan['assemblies'])
            check['owner'] = row_owner.owner(check, parts, nets)
        plan['owners'] = row_owner.table(circuits, parts)
        plan['interfaces'] = self.interfaces
        requirement_bindings.attach(plan['checks'])
        plan['rail_candidates'] = rail_candidates(self.db, self.intent)
        plan['summary']['owners'] = row_owner.counts(plan['checks'])
        plan['summary']['reviewer_added'] = len(rule_gaps.added(plan['checks']))
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


def build_review_plan(db, intent=None, review_mode=None,
                      old_db_available=False, claims_available=False,
                      datasheet_audit=None, previous_plan=None, old_db=None, old_plan=None, lint_findings=None,
                      candidates=None):
    return ReviewPlanner(
        db, intent, review_mode, old_db_available,
        claims_available, datasheet_audit, previous_plan, old_db, old_plan, lint_findings, candidates=candidates).build()


def main():
    parser = argparse.ArgumentParser(
        description='按规则总表生成逐项检查计划（适用性、准备度与证据缺口）')
    parser.add_argument('db', help='parse_netlist.py 产出的 db.json')
    parser.add_argument('--intent', help='审查意图 JSON')
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
    if datasheet_audit is not None:
        errors = validate_datasheet_audit(datasheet_audit, db)
        if errors:
            sys.exit('[FATAL] datasheet-audit.json 无效:\n  - '
                     + '\n  - '.join(errors))
    from lint import Lint  # the scan findings are part of the plan; lint imports this module
    try:
        plan = build_review_plan(
            db, intent, args.review_mode,
            old_db_available=bool(args.old_db), claims_available=bool(args.claims),
            datasheet_audit=datasheet_audit, old_db=old_db, old_plan=old_plan,
            lint_findings=Lint(db, None, intent, datasheet_audit).run(), candidates=candidates)
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
    for line in passive_stress.unread_lines(plan):
        print(line)
    for diagnostic in plan['diagnostics']:
        if diagnostic.get('code') == 'CIRCUIT_TYPE_MISFIT':
            print('  ' + diagnostic['detail'])
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

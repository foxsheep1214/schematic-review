#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全板与文档、需求、覆盖（功能树设计 §3.5、§3.8）：全板规则、装配状态、需求条款、覆盖审计项、逐器件身份与引脚表，
以及规则级台账。ReviewPlanner 混入这里的方法。"""
import re

import board_intent
import catalog
import requirement_parameters
import requirements_extract
from audit_datasheets import datasheet_audit_all_available
from checkers import registry_cold_rules, registry_hot_rules
from checkers.netgraph import ANODE_NAMES, CATHODE_NAMES, normalize
from interfaces import CONNECTOR_RE

# 全板规则执行前需要的资料；未列出的规则只需网表。
BOARD_MATERIALS = {
    'DOC-D02': ('requirements',), 'DOC-V02': ('schematic_pdf',), 'REQ-D02': ('requirements',),
}

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

def _material_available(intent, key, datasheet_audit=None):
    if key == 'datasheets' and datasheet_audit is not None:
        return datasheet_audit_all_available(datasheet_audit)
    item = (intent or {}).get('materials', {}).get(key, {})
    return isinstance(item, dict) and item.get('available') is True

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

def _text(value):
    return isinstance(value, str) and bool(value.strip())


class BoardPlanning:
    """全板、文档、需求与覆盖的检查项。"""

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

    def plan_coverage(self):
        for name, rule in catalog.COVERAGE_RULES.items():
            self.add_check(rule, {'feature': name}, trigger=['coverage-protocol'])
        source, _ = requirements_extract.load(self.intent.get('requirement_source')) if self.intent.get('requirements') else (None, [])
        originals = {i['id']: i for i in (source or {}).get('items', [])}
        for item in self.intent.get('requirements', []):
            obj = {'requirement_id': item['id'], 'feature': item['id']}
            if 'status' in item:
                obj['requirement_status'] = item['status']
            original = originals[item['id']]
            # One row per (requirement, aspect); the reviewer's reading rides on the row, outside the check identity.
            for aspect in catalog.requirement_aspects(item['categories']):
                row = self.add_check('REQ-D01', dict(obj, aspect=aspect), key=aspect,
                                     criterion=catalog.requirement_criterion(aspect), trigger=[original['locator']])
                row['interpretation'] = item['interpretation']
                row['parameters'] = [requirement_parameters.normalized(p) for p in item.get('parameters') or []]
                row['requirement_owners'] = list(item.get('owners') or [])
                row['source_text'] = {'locator': original['locator'], 'section': original['section'],
                                      'columns': [dict(c) for c in original['columns']]}
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

    def plan_stress_conditions(self):
        """Part stress rows are judged under the requirement numbers they depend on (fixed requirements, step 3)."""
        for row in self.checks:
            names = requirement_parameters.STRESS_CONDITIONS.get(row['rule'], ())
            conditions = {name: requirement_parameters.envelope(found) for name in names
                          for found in [requirement_parameters.windows(self.intent, name)] if found}
            if conditions:
                row['conditions'] = conditions

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

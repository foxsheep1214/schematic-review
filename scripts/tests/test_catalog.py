"""规则总表的一致性：文档、代码引用与生成的计划项。"""
import copy
import pathlib
import re
import sys
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

import catalog
from checkers import REGISTRY_BY_ID
from lint import Lint
from plan_review import BOARD_MATERIALS, build_review_plan
from revision_impact import _global_scope
from test_checkers_framework import whole_board

RULE_TOKEN = re.compile(r'(?<![A-Za-z0-9])[A-Z]{3}-[AETCDVQH]\d{2}(?![0-9])')
SOURCE_FILES = {
    'lint': ['lint.py', 'board_scans.py'],
    'plan': ['plan_review.py', 'catalog.py'],
    'revision': ['revision_impact.py', 'diff_netlists.py', 'plan_review.py'],
}
GENERIC_SOURCES = {'package', 'board'}


def source_text(source):
    if source in REGISTRY_BY_ID:
        module = sys.modules[type(REGISTRY_BY_ID[source]).__module__]
        return pathlib.Path(module.__file__).read_text(encoding='utf-8')
    return ''.join((SCRIPTS / name).read_text(encoding='utf-8') for name in SOURCE_FILES[source])


class CatalogTest(unittest.TestCase):
    def test_every_source_is_a_known_generator(self):
        generators = set(REGISTRY_BY_ID) | set(SOURCE_FILES) | GENERIC_SOURCES
        self.assertEqual(set(catalog.SOURCES), generators)

    def test_rules_are_implemented_where_the_catalog_says(self):
        tables = set(catalog.COVERAGE_RULES.values())
        for rule in catalog.RULES:
            if rule.source in GENERIC_SOURCES or (rule.source == 'plan' and rule.id in tables):
                continue
            with self.subTest(rule.id):
                self.assertRegex(source_text(rule.source), re.escape("'%s'" % rule.id))

    def test_scope_matches_how_rules_are_generated(self):
        for rule in catalog.RULES:
            with self.subTest(rule.id):
                if rule.source == 'board':
                    self.assertEqual(rule.scope, 'board')
                if rule.source == 'package':
                    self.assertIn(rule.scope, ('circuit', 'link'))
        self.assertTrue(set(BOARD_MATERIALS) <= {r.id for r in catalog.rules()
                                                  if r.scope == 'board' and r.id[4] != 'Q'})

    def test_packages_list_reviewer_rules_only(self):
        for package in catalog.PACKAGES:
            with self.subTest(package.name):
                self.assertTrue(package.rules)
                self.assertEqual(len(package.rules), len(set(package.rules)))
                self.assertTrue(all(catalog.method_of(rule) in 'TCDV' for rule in package.rules))
                self.assertTrue(set(package.materials) <= {'requirements', 'datasheets', 'platform_checklist'})
        members = {rule for package in catalog.PACKAGES for rule in package.rules}
        self.assertEqual({r.id for r in catalog.rules(source='package')} - members, set())

    def test_every_rule_token_in_code_and_docs_is_registered(self):
        paths = sorted(SCRIPTS.glob('*.py')) + sorted((SCRIPTS / 'checkers').glob('*.py'))
        paths += sorted((ROOT / 'references').glob('*.md')) + [ROOT / 'SKILL.md', ROOT / 'README.md']
        for path in paths:
            with self.subTest(path.name):
                unknown = set(RULE_TOKEN.findall(path.read_text(encoding='utf-8'))) - set(catalog.BY_ID)
                self.assertEqual(unknown, set())

    def test_reference_document_matches_catalog(self):
        path = ROOT / 'references' / 'check-catalog.md'
        text = path.read_text(encoding='utf-8')
        self.assertEqual(catalog.render_doc(text), text,
                         'run: python3 scripts/catalog.py --write-doc references/check-catalog.md')

    def test_summary_and_coverage_rules_are_coverage_audits(self):
        rules = ['REQ-Q07', 'REQ-Q08'] + list(catalog.COVERAGE_RULES.values())
        self.assertEqual({catalog.method_of(rule) for rule in rules}, {'Q'})

    def test_spec_errors_detect_mismatches(self):
        item = {'id': 'PWR-E01.U1-1', 'rule': 'PWR-E01', 'method': 'E', 'domain': 'PWR'}
        self.assertEqual(catalog.spec_errors(item), [])
        self.assertTrue(catalog.spec_errors(dict(item, method='C')))
        self.assertTrue(catalog.spec_errors(dict(item, id='U1-1')))
        self.assertTrue(catalog.spec_errors(dict(item, rule='Rule-08')))


class GeneratedOutputTest(unittest.TestCase):
    def board(self):
        db = whole_board()
        db['parts']['J9'] = {'value': 'HEADER', 'part': 'HEADER', 'nc': False}
        db['nets']['EXT_IO'] = ['J9.1', 'U4.9']
        db['pin2net'].update({'J9.1': 'EXT_IO', 'U4.9': 'EXT_IO'})
        db['pinname'].update({'J9.1': '1', 'U4.9': 'GPIO2'})
        # 阈值型保护与传感器：齐纳经电阻到 FAULT 门限脚，NTC 接控制器测温脚。
        db['parts'].update({ref: {'value': v, 'part': v, 'nc': False} for ref, v in
                            (('D9', 'BZT52H-B68'), ('TH9', 'NTC-100K'))})
        db['nets'].update({'FAULT_IN': ['D9.1', 'U4.10'], 'TEMP_SENSE': ['TH9.1', 'U4.11']})
        db['nets']['GND'] += ['D9.2', 'TH9.2']
        db['pin2net'].update({'D9.1': 'FAULT_IN', 'U4.10': 'FAULT_IN', 'TH9.1': 'TEMP_SENSE',
                              'U4.11': 'TEMP_SENSE', 'D9.2': 'GND', 'TH9.2': 'GND'})
        db['pinname'].update({'D9.1': 'K', 'D9.2': 'A', 'U4.10': 'FAULT', 'U4.11': 'ADC0'})
        db['ref2page'] = {ref: 1 for ref in db['parts']}
        return db

    def test_every_generated_rule_is_registered_and_every_planned_rule_is_reachable(self):
        db = self.board()
        intent = {'schema_version': 3, 'expect': {'SOC': 1},
                  'features': {'CUSTOM': {'applicability': 'APPLICABLE', 'citation': 'synthetic requirement'}},
                  'requirements': [{'id': 'REQ-1', 'text': 'synthetic', 'citation': 'synthetic',
                                    'criterion': 'synthetic criterion'}],
                  'circuits': [{'id': 'C-' + p.name, 'type': p.name, 'refs': ['U1'], 'states': ['run'],
                                'citation': 'synthetic'} for p in catalog.PACKAGES]}
        plans = [build_review_plan(db, intent), build_review_plan(self.board())]
        generated = set()
        for plan in plans:
            for item in plan['checks']:
                with self.subTest(item['id']):
                    self.assertEqual(catalog.spec_errors(item), [])
                    if item.get('package') and item['rule'] != 'REQ-Q07':
                        self.assertIn(item['rule'], catalog.package(item['package']).rules)
                generated.add(item['rule'])
            for row in plan['rule_plan']:
                self.assertTrue(catalog.known(row['rule']), row['rule'])
                self.assertEqual(row['name'], catalog.title(row['rule']))
        expected = {r.id for r in catalog.rules() if r.source in ('plan', 'package', 'board')}
        self.assertEqual(expected - generated, set())
        custom = next(x for x in plans[0]['checks'] if x['rule'] == 'REQ-Q07' and x['package'] == 'CUSTOM')
        self.assertIn('自定义功能 CUSTOM', custom['criterion'])
        log = 'ERROR (ORCAP-1): export stopped\n"No_connect" property on Pin "U4.6" ignored ... net "WDI_NET"'
        lint = Lint(db, log, intent)
        for finding in lint.run():
            with self.subTest(finding['rule']):
                self.assertIn(catalog.method_of(finding['rule']), 'AE')
        self.assertTrue(all(catalog.known(rule) for rule, _, _ in lint.skipped))

    def test_board_and_package_items_are_revision_global(self):
        plan = build_review_plan(self.board())
        for item in plan['checks']:
            obj = item['object']
            if obj.get('board') or obj.get('package'):
                with self.subTest(item['id']):
                    self.assertTrue(_global_scope(copy.deepcopy(item)))
        self.assertFalse(_global_scope(next(x for x in plan['checks'] if x['id'] == 'DEV-C05.U1')))

    def test_generated_stress_criteria_expose_estimate_and_scope_limits(self):
        # Reviewers receive actual generated criteria, including each circuit
        # state, rather than discovering decisive limits in a separate reference.
        intent = {'schema_version': 3, 'circuits': [
            {'id': 'C-REG', 'type': 'POWER_CONVERTER', 'refs': ['U1'],
             'states': ['run', 'startup'], 'citation': 'synthetic'},
            {'id': 'C-DRIVE', 'type': 'POWER_PROTECTION', 'refs': ['U1'],
             'states': ['run', 'fault'], 'citation': 'synthetic'}]}
        checks = build_review_plan(self.board(), intent)['checks']
        for rule in ('DEV-C05', 'DRV-C02'):
            generated = [item for item in checks if item['rule'] == rule]
            self.assertTrue(generated, rule)
            for item in generated:
                with self.subTest(check=item['id']):
                    self.assertIn('典型±30%', item['criterion'])
                    self.assertIn('后果不超过P2', item['criterion'])
                    self.assertIn('P1核心反馈', item['criterion'])
                    self.assertIn('受控身份全分支均适用的保证边界', item['criterion'])
        stability = [item for item in checks if item['rule'] == 'PWR-C04']
        self.assertEqual(len(stability), 2)
        for item in stability:
            self.assertIn('原厂明确不要求Cout', item['criterion'])
            self.assertIn('独立电容额定或反向能量', item['criterion'])
            self.assertIn('仅凭典型应用等效', item['criterion'])
            self.assertIn('后果不超过P2', item['criterion'])
        passive = next(item for item in checks if item['rule'] == 'DEV-C01')
        self.assertIn('活动轨段、滑臂与端点', passive['criterion'])
        self.assertIn('不能把整轨功率额定用于任意局部轨段', passive['criterion'])
        # A connector library name naming a vendor series is design intent, not a missing MPN.
        self.assertIn('连接器库名/封装名指向具体原厂系列或料号', passive['criterion'])
        self.assertIn('不因无 MPN 记 INSUFFICIENT', passive['criterion'])
        self.assertIn('泛称排针/间距不适用', passive['criterion'])

    def test_timing_accepts_vendor_qualified_pairing_but_not_deviations(self):
        # A host datasheet without interface timing is not a gap when the host vendor names the part and wiring.
        criterion = catalog.get('SIG-C09').criterion
        self.assertIn('主控厂商设计指南明确指定该器件型号、接法与时钟配置', criterion)
        self.assertIn('不因主控手册缺接口时序记 INSUFFICIENT', criterion)
        self.assertIn('换型号/改接法/提高时钟时仍按两端保证值计算', criterion)


class ObjectiveAlignmentTest(unittest.TestCase):
    def test_every_active_rule_has_one_primary_objective(self):
        index = catalog.build_objective_index(catalog.BY_ID, catalog.OBJECTIVE_RULES)
        self.assertEqual(set(index), set(catalog.BY_ID))
        self.assertEqual(index, catalog.OBJECTIVE_BY_RULE)
        for package in catalog.PACKAGES:
            self.assertTrue(set(package.rules) <= set(index))

    def test_new_rule_without_alignment_is_rejected(self):
        with self.assertRaises(ValueError):
            catalog.build_objective_index(set(catalog.BY_ID) | {'NEW-RULE'}, catalog.OBJECTIVE_RULES)

    def test_duplicate_alignment_is_rejected(self):
        groups = copy.deepcopy(catalog.OBJECTIVE_RULES)
        groups['G2'] += (groups['G1'][0],)
        with self.assertRaises(ValueError):
            catalog.build_objective_index(catalog.BY_ID, groups)

    def test_unknown_alignment_is_rejected(self):
        groups = copy.deepcopy(catalog.OBJECTIVE_RULES)
        groups['G2'] += ('NET-A05',)
        with self.assertRaises(ValueError):
            catalog.build_objective_index(catalog.BY_ID, groups)

    def test_undefined_objective_is_rejected(self):
        groups = copy.deepcopy(catalog.OBJECTIVE_RULES)
        groups['UNDEFINED'] = groups.pop('G1')
        with self.assertRaises(ValueError):
            catalog.build_objective_index(catalog.BY_ID, groups)

    def test_empty_objective_cannot_hide_unassigned_rules(self):
        groups = copy.deepcopy(catalog.OBJECTIVE_RULES)
        groups['G2'] += groups['G1']
        groups['G1'] = ()
        with self.assertRaises(ValueError):
            catalog.build_objective_index(catalog.BY_ID, groups)


class QuestionTemplateTest(unittest.TestCase):
    """功能包成员规则的问题模板：每条都有、都能填空、都不含禁止句；五步核对单抄自参考文档。"""

    def test_every_package_member_rule_has_a_question_free_of_prohibitions(self):
        members = {rule for package in catalog.PACKAGES for rule in package.rules}
        self.assertEqual(members, set(catalog.QUESTIONS))
        for rule, template in catalog.QUESTIONS.items():
            with self.subTest(rule):
                self.assertIsNone(catalog.QUESTION_BAN_RE.search(template), template)
                filled = catalog.question(rule, 'RUN', 'BIAS', ['Q2', 'D4'], 'VCC 9–18 V')
                if rule in catalog.STATE_INVARIANT:   # asked once per circuit: no state in the question
                    self.assertTrue(filled.startswith('BIAS（Q2、D4）'), filled)
                    self.assertNotIn('RUN', filled)
                else:
                    self.assertIn('RUN 时 BIAS（Q2、D4）', filled)
        self.assertLessEqual(catalog.STATE_INVARIANT, set(catalog.QUESTIONS))
        self.assertEqual({p.name for p in catalog.PACKAGES}, set(catalog.FRAME_QUESTIONS))
        for name, body in catalog.FRAME_QUESTIONS.items():
            with self.subTest(name):
                self.assertIsNone(catalog.QUESTION_BAN_RE.search(body), body)
        self.assertIn(catalog.NO_WINDOW, catalog.question('PWR-C02', 'RUN', 'BIAS', ['Q2']))
        self.assertIsNone(catalog.question('DOC-V01', 'RUN', 'BIAS', ['Q2']))

    def test_bounding_steps_are_copied_from_the_reference(self):
        doc = (pathlib.Path(__file__).resolve().parents[2] / 'references' / 'evidence-proportionality.md').read_text(
            encoding='utf-8').replace('**', '')
        self.assertEqual(len(catalog.BOUNDING_STEPS), 5)
        for step in catalog.BOUNDING_STEPS:
            self.assertIn(step, doc)

    def test_question_errors_reject_prohibition_phrasing_in_rows_and_frames(self):
        plan = {'checks': [{'id': 'PWR-C02.X', 'question': '输出是否落在窗口内'},
                           {'id': 'PWR-C03.X', 'question': '不把测试条件外推为使用范围'}],
                'functions': [{'id': 'FN-X', 'question': '不得以典型值放行'}]}
        errors = catalog.question_errors(plan)
        self.assertEqual(len(errors), 2, errors)
        self.assertTrue(errors[0].startswith('PWR-C03.X'))
        self.assertTrue(errors[1].startswith('functions.FN-X'))
        self.assertEqual(catalog.question_errors({'checks': [{'id': 'A'}]}), [])


if __name__ == '__main__':
    unittest.main()

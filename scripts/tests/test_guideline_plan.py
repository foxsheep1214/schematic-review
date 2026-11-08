"""The plan lists the shared guideline rules this board triggers and which planned SR rules cover them
(references/shared/guideline-criteria.md; user 2026-10-31: 请开始执行这个方案). An empty rule library leaves the plan as it was.
"""
import sys
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import catalog
import guideline_criteria
import independence
import plan_review
import render_report
from test_guideline_criteria import bundle, rule
from test_interface_rows import fx, plan_for
from test_validate_review import fixture
import validate_review as validate_review_module
from validate_review import fingerprint, validate_review

STALE = 'plan guidelines were built on another shared rule library'
STALE_LAYER = 'plan guidelines were built on another shared layer'


def identity(library):
    with mock.patch.dict(os.environ, {'GUIDELINE_CRITERIA': ''}):
        return guideline_criteria.shared_versions(bundle=library)


class GuidelinePlanTests(unittest.TestCase):
    def library(self):
        return bundle(rule('G01-001', applies_when={'board': True}),
                      rule('G02-001', applies_when={'device_kinds': ['capacitor']}, closing_stage='prototype'),
                      rule('G04-001', applies_when={'circuit_types': ['RS485']}),
                      rule('G06-001', nature='project', applies_when={'board': True, 'baselines': ['aerospace']}))

    def plan(self, basis=None):
        library = self.library()
        with mock.patch.dict(os.environ, {'GUIDELINE_CRITERIA': ''}), mock.patch.object(guideline_criteria, 'load', lambda *args: library), \
                mock.patch.object(catalog, 'BASIS', basis or {}):
            return plan_for()

    def test_the_plan_lists_applicable_rules_and_their_coverage(self):
        plan = self.plan({'DOC-Q01': ('G01-001',)})
        section = plan['guidelines']
        self.assertEqual(section['fingerprint_format'], 'shared-paths-sha256-v2')
        self.assertEqual(section['shared_sha256'], identity(self.library())['shared_sha256'])
        self.assertEqual(section['baseline'], 'industrial_telecom')
        self.assertIn('capacitor', section['device_kinds'])
        self.assertEqual(section['circuit_types'], sorted({c['circuit_type'] for c in plan['checks']
                                                           if c.get('circuit_type')}))
        self.assertEqual(section['applicable'][:2], ['G01-001', 'G02-001'])
        self.assertNotIn('G06-001', section['applicable'])
        self.assertEqual(section['covered'], {'G01-001': ['DOC-Q01']})
        self.assertIn('G02-001', section['uncovered'])
        self.assertEqual(section['downstream'], ['G02-001'])
        self.assertEqual(section['content_sha256'], self.library()['content_sha256'])

    def test_a_mapped_check_with_no_row_is_not_triggered_rather_than_uncovered(self):
        section = self.plan({'DOC-Q01': ('G01-001',), 'REQ-Q05': ('G02-001',)})['guidelines']
        self.assertEqual(section['not_triggered'], {'G02-001': ['REQ-Q05']})
        self.assertNotIn('G02-001', section['uncovered'])

    def batch_library(self):
        return bundle(rule('G01-001', applies_when={'board': True}),
                      rule('G08-001', applies_when={'board': True}, coverage='project_input'),
                      rule('G08-002', applies_when={'board': True}, coverage='project_input'),
                      rule('G07-001', applies_when={'board': True}, coverage='handoff', closing_stage='pcb'))

    def batch_plan(self, materials=None):
        library, intent_for = self.batch_library(), fx.intent_for

        def with_materials(db):
            intent, audit = intent_for(db)
            intent.setdefault('materials', {}).update(materials or {})
            return intent, audit
        with mock.patch.dict(os.environ, {'GUIDELINE_CRITERIA': ''}), mock.patch.object(guideline_criteria, 'load', lambda *args: library), mock.patch.object(catalog, 'BASIS', {}), \
                mock.patch.object(fx, 'intent_for', with_materials):
            return plan_for()

    def test_batch_rules_get_one_row_per_class_and_leave_the_item_lists(self):
        plan = self.batch_plan()
        section = plan['guidelines']
        self.assertEqual(section['project_input'], ['G08-001', 'G08-002'])
        self.assertEqual(section['handoff'], ['G07-001'])
        self.assertEqual(section['uncovered'], ['G01-001'])
        self.assertEqual(section['not_triggered'], {})
        self.assertEqual(section['downstream'], ['G07-001'])
        rows = {c['id']: c for c in plan['checks'] if c['rule'] == 'REQ-Q09'}
        self.assertEqual(sorted(rows), ['REQ-Q09.HANDOFF.BOARD', 'REQ-Q09.PROJECT-INPUT.BOARD'])
        self.assertEqual(rows['REQ-Q09.PROJECT-INPUT.BOARD']['object']['criteria'], ['G08-001', 'G08-002'])
        self.assertTrue(rows['REQ-Q09.PROJECT-INPUT.BOARD']['criterion'].endswith('G08-001、G08-002'))
        self.assertIn('不核 PCB、EMC、热设计验收', rows['REQ-Q09.HANDOFF.BOARD']['criterion'])

    def test_the_handoff_row_waits_for_the_list_and_the_baseline_row_for_the_requirements(self):
        rows = {c['object']['coverage']: c for c in self.batch_plan()['checks'] if c['rule'] == 'REQ-Q09'}
        self.assertEqual(rows['handoff']['readiness'], 'WAITING_EVIDENCE')
        self.assertEqual(rows['handoff']['required_inputs'], ['handoff_list'])
        self.assertEqual(rows['project_input']['required_inputs'], ['requirements'])
        with tempfile.NamedTemporaryFile(suffix='设计报告.md') as listed:
            plan = self.batch_plan({'handoff_list': {'path': listed.name}})
        row = next(c for c in plan['checks'] if c['id'] == 'REQ-Q09.HANDOFF.BOARD')
        self.assertEqual(row['readiness'], 'READY')

    def test_the_gate_rebuild_writes_the_same_batch_rows(self):
        # PoE node 2026-11-07: the rows were written after generate(), so the gate's rebuild lacked them and called
        # them reviewer additions; the rebuild has to write them, unchanged
        from revision_impact import check_spec
        library = self.batch_library()
        with mock.patch.dict(os.environ, {'GUIDELINE_CRITERIA': ''}), mock.patch.object(guideline_criteria, 'load', lambda *args: library), \
                mock.patch.object(catalog, 'BASIS', {}):
            plan = plan_for()
            inputs, summary = plan['review_inputs'], plan.get('circuit_candidates')
            candidates = ({'candidates': [], 'unassigned': [{'ref': r} for r in summary.get('unassigned') or []]}
                          if isinstance(summary, dict) else None)
            planner = plan_review.ReviewPlanner(fx.board(), inputs['intent'], plan.get('review_mode'),
                                                datasheet_audit=inputs['datasheet_audit'], candidates=candidates)
            planner.generate()
        planned = {c['id']: check_spec(c) for c in plan['checks'] if c['rule'] == 'REQ-Q09'}
        rebuilt = {c['id']: check_spec(c) for c in planner.checks if c['rule'] == 'REQ-Q09'}
        self.assertEqual(sorted(planned), ['REQ-Q09.HANDOFF.BOARD', 'REQ-Q09.PROJECT-INPUT.BOARD'])
        self.assertEqual(planned, rebuilt)

    def test_a_library_without_batch_rules_adds_no_row_and_no_keys(self):
        plan = self.plan({'DOC-Q01': ('G01-001',)})
        self.assertFalse([c for c in plan['checks'] if c['rule'] == 'REQ-Q09'])
        self.assertNotIn('project_input', plan['guidelines'])
        self.assertNotIn('handoff', plan['guidelines'])

    def test_the_plan_names_the_external_interfaces_it_found(self):
        section = self.plan()['guidelines']   # the fixture board has a VAC net
        self.assertEqual(section['external_interfaces'], ['AC_MAINS'])

    def test_an_empty_library_adds_nothing(self):
        self.assertNotIn('guidelines', plan_for())

    def test_the_baseline_is_one_of_the_librarys(self):
        intent = {'schema_version': plan_review.INTENT_SCHEMA_VERSION, 'guideline_baseline': 'space'}
        self.assertTrue(any('guideline_baseline' in e for e in plan_review.validate_intent(intent)))
        intent['guideline_baseline'] = 'aerospace'
        self.assertFalse(any('guideline_baseline' in e for e in plan_review.validate_intent(intent)))

    def test_basis_names_registered_rules_and_library_rules(self):
        library = guideline_criteria.load(guideline_criteria.BUNDLE_PATH)
        self.assertEqual(catalog.basis_errors({r['id'] for r in library['criteria']}), [])
        self.assertEqual(len(catalog.basis_errors({'G01-001'}, {'NO-X01': ('G01-001',), 'DOC-Q01': ('G09-001',)})), 2)


class GuidelineGateAndReportTests(unittest.TestCase):
    def setUp(self):
        self.library = GuidelinePlanTests.library(None)
        self.section = {**identity(self.library),
                        'baseline': 'industrial_telecom', 'circuit_types': [], 'device_kinds': ['capacitor'],
                        'applicable': ['G01-001', 'G02-001'], 'covered': {'G01-001': ['DOC-Q01']},
                        'uncovered': ['G02-001'], 'downstream': ['G02-001']}

    def gate(self, section):
        plan, report, db = fixture()
        if section is not None:
            plan['guidelines'] = section
        report['plan_digest'] = fingerprint(plan)
        with mock.patch.dict(os.environ, {'GUIDELINE_CRITERIA': ''}), mock.patch.object(guideline_criteria, 'load', lambda *args: self.library):
            return validate_review(plan, report, db)

    def test_the_gate_wants_the_plan_built_on_the_installed_library(self):
        self.assertFalse(any(STALE in e for e in self.gate(self.section)['errors']))
        self.assertEqual(self.gate(self.section)['guideline_coverage'], self.section)
        self.assertTrue(any(STALE in e for e in self.gate(None)['errors']))
        self.assertTrue(any(STALE in e for e in self.gate(dict(self.section, content_sha256='0' * 64))['errors']))
        # 2026-11-02 (user: 目录制): the whole shared layer is bound, not only the rule library
        self.assertFalse(any(STALE_LAYER in e for e in self.gate(self.section)['errors']))
        self.assertTrue(any(STALE_LAYER in e for e in self.gate(dict(self.section, shared_sha256='0' * 64))['errors']))
        self.assertTrue(any(STALE_LAYER in e for e in self.gate({k: v for k, v in self.section.items() if k != 'shared_sha256'})['errors']))

    def batch_gate(self, row_changes=None, section_changes=None, rows=None):
        library = bundle(rule('G01-001', applies_when={'board': True}),
                         rule('G08-001', applies_when={'board': True}, coverage='project_input'),
                         rule('G07-001', applies_when={'board': True}, coverage='handoff', closing_stage='pcb'))
        section = dict(self.section, content_sha256=library['content_sha256'], project_input=['G08-001'], handoff=['G07-001'])
        section.update(section_changes or {})
        expected = rows if rows is not None else {
            'REQ-Q09.PROJECT-INPUT.BOARD': {'rule': 'REQ-Q09', 'object': {'coverage': 'project_input', 'criteria': ['G08-001']}},
            'REQ-Q09.HANDOFF.BOARD': {'rule': 'REQ-Q09', 'object': {'coverage': 'handoff', 'criteria': ['G07-001']}}}
        checks = {'REQ-Q09.PROJECT-INPUT.BOARD': {'review_result': 'PASS', 'batch_answers': {'G08-001': 'REQ-3'}},
                  'REQ-Q09.HANDOFF.BOARD': {'review_result': 'PASS', 'batch_answers': {'G07-001': '交接表 第2行'}}}
        for key, changes in (row_changes or {}).items():
            checks[key].update(changes)
        return validate_review_module.guideline_batch_errors(section, expected, checks, library)

    def test_the_gate_takes_a_batch_row_that_says_where_each_rule_is(self):
        self.assertEqual(self.batch_gate(), [])
        self.assertEqual(self.batch_gate({'REQ-Q09.PROJECT-INPUT.BOARD': {'batch_answers': {'G08-001': 'TBR'}}}), [])
        self.assertEqual(self.batch_gate({'REQ-Q09.HANDOFF.BOARD': {'review_result': 'FAIL', 'batch_answers': None}}), [])

    def test_the_gate_refuses_a_pass_with_no_answers_or_other_rules_or_a_tbr_handoff(self):
        for changes in ({'batch_answers': None}, {'batch_answers': {}}, {'batch_answers': {'G07-001': ' '}},
                        {'batch_answers': {'G07-001': '第2行', 'G01-001': '第2行'}}, {'batch_answers': {'G07-001': 'TBR'}}):
            with self.subTest(changes):
                self.assertTrue(any('REQ-Q09.HANDOFF.BOARD' in e for e in self.batch_gate({'REQ-Q09.HANDOFF.BOARD': changes})))

    def test_the_gate_refuses_an_item_rule_in_a_batch(self):
        rows = {'REQ-Q09.HANDOFF.BOARD': {'rule': 'REQ-Q09', 'object': {'coverage': 'handoff', 'criteria': ['G07-001', 'G01-001']}},
                'REQ-Q09.PROJECT-INPUT.BOARD': {'rule': 'REQ-Q09', 'object': {'coverage': 'project_input', 'criteria': ['G08-001']}}}
        errors = self.batch_gate({'REQ-Q09.HANDOFF.BOARD': {'batch_answers': {'G07-001': 'x', 'G01-001': 'x'}}},
                                 {'handoff': ['G07-001', 'G01-001']}, rows)
        self.assertTrue(any('G01-001 are not handoff' in e and 'item rule' in e for e in errors), errors)

    def test_the_gate_refuses_a_row_that_lists_other_rules_than_the_section(self):
        self.assertTrue(any('list different rules' in e for e in self.batch_gate(section_changes={'handoff': []})))
        self.assertTrue(any('list different rules' in e for e in self.batch_gate(rows={})))

    def test_a_plan_without_batch_rules_has_nothing_for_the_batch_gate(self):
        self.assertEqual(validate_review_module.guideline_batch_errors(self.section, {}, {}, self.library), [])
        self.assertEqual(validate_review_module.guideline_batch_errors(None, {}, {}, self.library), [])

    def test_the_report_folds_each_batch_class_into_one_table(self):
        library = bundle(rule('G01-001', applies_when={'board': True}),
                         rule('G08-001', applies_when={'board': True}, coverage='project_input'),
                         rule('G07-001', applies_when={'board': True}, coverage='handoff', closing_stage='pcb'))
        section = dict(self.section, applicable=['G01-001', 'G07-001', 'G08-001'], project_input=['G08-001'], handoff=['G07-001'])
        with mock.patch.dict(os.environ, {'GUIDELINE_CRITERIA': ''}), mock.patch.object(guideline_criteria, 'load', lambda *args: library):
            lines = render_report.render_guidelines({'guidelines': section})
        self.assertEqual(lines.count('### 由需求基线回答的设计准则'), 1)
        self.assertEqual(lines.count('### 要列进交接清单的设计准则'), 1)
        # PoE node 2026-11-07: the heading said 下游 and pack_review refused the report's own wording
        self.assertEqual([w for title, intro in render_report.BATCH_TABLES.values() for w in render_report.jargon_in(title + intro)], [])
        self.assertIn('| G08-001 | RS-485 共模范围 | 原理图 |', lines)
        self.assertIn('| G07-001 | RS-485 共模范围 | PCB |', lines)
        self.assertEqual([l for l in lines if l.startswith('| G08-001') or l.startswith('| G07-001')],
                         ['| G08-001 | RS-485 共模范围 | 原理图 |', '| G07-001 | RS-485 共模范围 | PCB |'])

    def test_only_the_handoff_list_may_name_a_designer_document(self):
        self.assertEqual(independence.intent_errors({'materials': {'handoff_list': {'path': '/x/设计报告.md'}}}), [])
        self.assertTrue(independence.intent_errors({'materials': {'other': {'path': '/x/设计报告.md'}}}))
        evidence = [{'source': '设计报告.md'}]
        self.assertEqual(independence.evidence_errors([{'id': 'REQ-Q09.HANDOFF.BOARD', 'evidence': evidence}]), [])
        self.assertTrue(independence.evidence_errors([{'id': 'REQ-Q09.PROJECT-INPUT.BOARD', 'evidence': evidence}]))

    def test_an_empty_library_asks_nothing_of_the_plan(self):
        plan, report, db = fixture()
        result = validate_review(plan, report, db)
        self.assertFalse(any(STALE in e for e in result['errors']))
        self.assertIsNone(result['guideline_coverage'])

    def test_the_report_lists_applicable_rules_and_sr_lists_the_uncovered(self):
        with mock.patch.dict(os.environ, {'GUIDELINE_CRITERIA': ''}), mock.patch.object(guideline_criteria, 'load', lambda *args: self.library):
            lines = render_report.render_guidelines({'guidelines': self.section})
        text = '\n'.join(lines)
        self.assertIn(guideline_criteria.shared_label(identity=self.section) + '，产品基线 industrial_telecom。', text)   # one label binds library and derating
        self.assertIn('| G01-001 | RS-485 共模范围 | TI SLLA272 C §2 第3页 | DOC-Q01 | 原理图 |', text)
        self.assertIn('| G02-001 | RS-485 共模范围 | TI SLLA272 C §2 第3页 | 未覆盖 | 样机 |', text)
        self.assertEqual(render_report.render_guidelines({}), [])

    def test_an_undeclared_external_interface_is_said_once_any_is_declared_it_is_not(self):
        with mock.patch.dict(os.environ, {'GUIDELINE_CRITERIA': ''}), mock.patch.object(guideline_criteria, 'load', lambda *args: self.library):
            bare = '\n'.join(render_report.render_guidelines({'guidelines': self.section}))
            named = '\n'.join(render_report.render_guidelines(
                {'guidelines': dict(self.section, external_interfaces=['POE_PD'])}))
        self.assertIn('未声明对外接口', bare)
        self.assertIn('intent.circuits', bare)
        self.assertNotIn('未声明对外接口', named)

    def test_the_whole_report_carries_both_sections(self):
        plan, report, db = fixture()
        plan['guidelines'] = self.section
        report['plan_digest'] = fingerprint(plan)
        with mock.patch.dict(os.environ, {'GUIDELINE_CRITERIA': ''}), mock.patch.object(guideline_criteria, 'load', lambda *args: self.library):
            text = render_report.render(plan, report, validate_review(plan, report, db))
        self.assertIn('<summary>共用设计准则覆盖</summary>', text)
        uncovered = text[text.index('### 适用但还没有检查的共用设计准则'):]
        self.assertIn('| G02-001 | RS-485 共模范围 | 核对收发器共模范围覆盖工况 |', uncovered)
        self.assertNotIn('| G01-001 |', uncovered.split('</details>')[0])


if __name__ == '__main__':
    unittest.main()

class M4IdentityTests(unittest.TestCase):
    setUp = GuidelineGateAndReportTests.setUp
    gate = GuidelineGateAndReportTests.gate
    def test_missing_or_unknown_format_does_not_promote_an_old_plan(self):
        import copy
        for value in (None, 'unknown', 'shared-files-sha256-lines-v1'):
            section = copy.deepcopy(self.section)
            if value is None:
                section.pop('fingerprint_format')
            else:
                section['fingerprint_format'] = value
            original = copy.deepcopy(section)
            gate = self.gate(section)
            self.assertTrue(any('fingerprint format' in e for e in gate['errors']), gate['errors'])
            self.assertEqual(original, section)

    def test_version_change_requires_reverification_even_with_same_digest(self):
        gate = self.gate(dict(self.section, library_version='different-release'))
        self.assertTrue(any('shared library_version changed' in e for e in gate['errors']), gate['errors'])

    def test_old_plan_schema_is_rejected_before_new_identity_is_accepted(self):
        plan, report, db = fixture()
        plan['schema_version'] = 7
        report['plan_digest'] = fingerprint(plan)
        gate = validate_review(plan, report, db)
        self.assertTrue(any('plan.schema_version must be 8' in e for e in gate['errors']))

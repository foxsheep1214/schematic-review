"""The plan lists the shared guideline rules this board triggers and which planned SR rules cover them
(references/guideline-rules.md; user 2026-10-31: 请开始执行这个方案). An empty rule library leaves the plan as it was.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import catalog
import guideline_rules
import plan_review
import render_report
from test_guideline_rules import bundle, rule
from test_interface_rows import plan_for
from test_validate_review import fixture
from validate_review import fingerprint, validate_review

STALE = 'plan guidelines were built on another shared rule library'


class GuidelinePlanTests(unittest.TestCase):
    def library(self):
        return bundle(rule('G01-001', applies_when={'board': True}),
                      rule('G02-001', applies_when={'device_kinds': ['capacitor']}, closing_stage='prototype'),
                      rule('G04-001', applies_when={'circuit_types': ['RS485']}),
                      rule('G06-001', nature='project', applies_when={'board': True, 'baselines': ['aerospace']}))

    def plan(self, basis=None):
        library = self.library()
        with mock.patch.object(guideline_rules, 'load', lambda *args: library), \
                mock.patch.object(catalog, 'BASIS', basis or {}):
            return plan_for()

    def test_the_plan_lists_applicable_rules_and_their_coverage(self):
        plan = self.plan({'DOC-Q01': ('G01-001',)})
        section = plan['guidelines']
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

    def test_an_empty_library_adds_nothing(self):
        self.assertNotIn('guidelines', plan_for())

    def test_the_baseline_is_one_of_the_librarys(self):
        intent = {'schema_version': plan_review.INTENT_SCHEMA_VERSION, 'guideline_baseline': 'space'}
        self.assertTrue(any('guideline_baseline' in e for e in plan_review.validate_intent(intent)))
        intent['guideline_baseline'] = 'aerospace'
        self.assertFalse(any('guideline_baseline' in e for e in plan_review.validate_intent(intent)))

    def test_basis_names_registered_rules_and_library_rules(self):
        library = guideline_rules.load()
        self.assertEqual(catalog.basis_errors({r['id'] for r in library['rules']}), [])
        self.assertEqual(len(catalog.basis_errors({'G01-001'}, {'NO-X01': ('G01-001',), 'DOC-Q01': ('G09-001',)})), 2)


class GuidelineGateAndReportTests(unittest.TestCase):
    def setUp(self):
        self.library = GuidelinePlanTests.library(None)
        self.section = {'library_version': '0.0.0', 'content_sha256': self.library['content_sha256'],
                        'baseline': 'industrial_telecom', 'circuit_types': [], 'device_kinds': ['capacitor'],
                        'applicable': ['G01-001', 'G02-001'], 'covered': {'G01-001': ['DOC-Q01']},
                        'uncovered': ['G02-001'], 'downstream': ['G02-001']}

    def gate(self, section):
        plan, report, db = fixture()
        if section is not None:
            plan['guidelines'] = section
        report['plan_digest'] = fingerprint(plan)
        with mock.patch.object(guideline_rules, 'load', lambda *args: self.library):
            return validate_review(plan, report, db)

    def test_the_gate_wants_the_plan_built_on_the_installed_library(self):
        self.assertFalse(any(STALE in e for e in self.gate(self.section)['errors']))
        self.assertEqual(self.gate(self.section)['guideline_coverage'], self.section)
        self.assertTrue(any(STALE in e for e in self.gate(None)['errors']))
        self.assertTrue(any(STALE in e for e in self.gate(dict(self.section, content_sha256='0' * 64))['errors']))

    def test_an_empty_library_asks_nothing_of_the_plan(self):
        plan, report, db = fixture()
        result = validate_review(plan, report, db)
        self.assertFalse(any(STALE in e for e in result['errors']))
        self.assertIsNone(result['guideline_coverage'])

    def test_the_report_lists_applicable_rules_and_sr_lists_the_uncovered(self):
        with mock.patch.object(guideline_rules, 'load', lambda *args: self.library):
            lines = render_report.render_guidelines({'guidelines': self.section})
        text = '\n'.join(lines)
        self.assertIn('| G01-001 | RS-485 共模范围 | TI SLLA272 C §2 第3页 | DOC-Q01 | 原理图 |', text)
        self.assertIn('| G02-001 | RS-485 共模范围 | TI SLLA272 C §2 第3页 | 未覆盖 | 样机 |', text)
        self.assertEqual(render_report.render_guidelines({}), [])

    def test_the_whole_report_carries_both_sections(self):
        plan, report, db = fixture()
        plan['guidelines'] = self.section
        report['plan_digest'] = fingerprint(plan)
        with mock.patch.object(guideline_rules, 'load', lambda *args: self.library):
            text = render_report.render(plan, report, validate_review(plan, report, db))
        self.assertIn('<summary>共用规范规则覆盖</summary>', text)
        uncovered = text[text.index('### 适用但还没有检查的共用规范规则'):]
        self.assertIn('| G02-001 | RS-485 共模范围 | 核对收发器共模范围覆盖工况 |', uncovered)
        self.assertNotIn('| G01-001 |', uncovered.split('</details>')[0])


if __name__ == '__main__':
    unittest.main()

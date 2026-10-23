"""SR reviews from scratch and does not take the designer's documents as reference (2026-10-22).

Recomputing the numbers a design report or calculation file states lets those documents set the review: which
states, inputs and figures are looked at follow the designer's framing. SR derives every value from the schematic,
the requirements and the manufacturer datasheets. It has no tool that recomputes designer claims, audits the
designer's derived summaries or re-judges the designer's selection record, its pack asks for none of them, and its
rail windows do not come from design calculations.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))

import catalog
import independence
from plan_review import validate_intent
from validate_review import validate_review
from test_validate_review import fixture

REMOVED = ('calc_claims', 'audit_document_summaries', 'review_selection', 'asg_summary_adapter')
TOKENS = REMOVED + ('selection-review', 'document-summaries', '派生摘要', '设计计算书', 'preflight-delivery')


def sr_files():
    yield ROOT / 'SKILL.md'
    yield from sorted((ROOT / 'references').glob('*.md'))
    yield from sorted((ROOT / 'scripts').glob('*.py'))
    yield from sorted((ROOT / 'scripts' / 'checkers').glob('*.py'))


class IndependentReviewTests(unittest.TestCase):
    def test_the_designer_document_tools_are_gone(self):
        for name in REMOVED:
            self.assertFalse((ROOT / 'scripts' / (name + '.py')).exists(), name)
        for name in ('selection-review.md', 'document-summaries.md'):
            self.assertFalse((ROOT / 'references' / name).exists(), name)

    def test_no_sr_script_or_doc_names_them(self):
        found = {(path.name, token) for path in sr_files() for token in TOKENS
                 if token in path.read_text(encoding='utf-8')}
        self.assertEqual(found, set())

    def test_input_consistency_does_not_audit_designer_summaries(self):
        criterion = catalog.get('DOC-Q01').criterion
        for token in ('claim', '派生', '摘要'):
            self.assertNotIn(token, criterion)


class DesignerDocumentTests(unittest.TestCase):
    """SR reads the requirements, the design results (schematic, netlist, BOM, PDF), manufacturer and standards
    documents and its own calculations. On R5 one record cited the design report for a not-applicable reason and drew
    60-odd row evidences from the designer's calculations, self-checks, report and replies; nothing refused them."""

    DESIGNER = ['/proj/ASG-1/设计报告.md', '/proj/ASG-1/record/calculations/results.json',
                '/proj/ASG-1/record/design-preflight.json', '/proj/ASG-1/record/review-responses.json',
                '/proj/ASG-1/electrical-intent.json', '/proj/ASG-1/requirement-trace.md',
                '/proj/ASG-1/device-contracts.json', '/proj/ASG-1/delivery-evidence.json',
                '原理图 p7 TP601；设计报告 H-19', 'design report section 4', '计算书 R5-NOLOAD', '/proj/设计方案.md 3.2 节']
    ALLOWED = ['/proj/ASG-1/原理图/BOM.csv', '/proj/ASG-1/原理图/schematic.pdf', '/proj/需求/用户需求.md',
               '/data/原厂资料/onsemi-NCP1623.pdf p4 Table 1', 'evidence/calculations.json', 'db.json',
               'references/calculation-preflight.md', 'USB Power Delivery 3.2 规范 6.4 节',
               '/proj/设计方案/ASG-1/原理图/BOM.csv']

    def test_designer_documents_are_named_and_design_results_are_not(self):
        for text in self.DESIGNER:
            self.assertTrue(independence.designer_document(text), text)
        for text in self.ALLOWED:
            self.assertFalse(independence.designer_document(text), text)

    def test_an_intent_citing_a_designer_document_is_refused(self):
        intent = {'schema_version': 3, 'features': {'I2C': {'applicability': 'NOT_APPLICABLE',
                                                           'citation': '原理图 p7 TP601；设计报告 H-19'}}}
        errors = [e for e in validate_intent(intent) if '设计方文档' in e]
        self.assertEqual(len(errors), 1)
        self.assertIn('features.I2C.citation', errors[0])
        intent['features']['I2C']['citation'] = '原理图 p7 TP601 只是编程测试点；需求无 I2C 接口'
        self.assertEqual([e for e in validate_intent(intent) if '设计方文档' in e], [])
        intent['assemblies'] = [{'id': 'run', 'citation': '设计报告 2.1 装配说明', 'population': {}}]
        self.assertTrue(any('assemblies[0].citation' in e for e in validate_intent(intent) if '设计方文档' in e))

    def test_row_evidence_from_a_designer_document_is_refused(self):
        plan, report, db = fixture()
        self.assertTrue(validate_review(plan, report, db)['valid'])
        report['checks'][0]['evidence'] = [{'source': '/proj/ASG-1/record/calculations/results.json', 'locator': 'R5'}]
        errors = validate_review(plan, report, db)['errors']
        self.assertTrue(any('设计方文档' in e and report['checks'][0]['id'] in e for e in errors), errors)

    def test_sr_calls_its_intent_the_review_intent_and_takes_expectations_from_requirements(self):
        found = {path.name for path in sr_files() if '设计意图' in path.read_text(encoding='utf-8')}
        self.assertEqual(found, set())
        for rule in ('REQ-A01', 'REQ-A02'):
            self.assertIn('需求', catalog.get(rule).criterion, rule)


if __name__ == '__main__':
    unittest.main()

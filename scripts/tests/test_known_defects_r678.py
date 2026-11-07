"""Regression guard for the R6 known defect R6-source-omission (2026-10-24): the brief named two requirement documents
and one reviewer transcribed only one into intent.requirement_source (195 rows in that record only). The pack now
refuses a declared `requirements` input holding a text document that requirement_source leaves out.
"""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pack_review import requirement_omission_errors


class RequirementOmissionTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.req = self.dir / '需求'
        self.req.mkdir()
        self.a = self.req / '用户需求.md'
        self.b = self.req / '工程规格.md'
        self.a.write_text('| ID | 需求 |\n|---|---|\n| R1 | 24 V 输入 |\n', encoding='utf-8')
        self.b.write_text('| 工程ID | 规格 |\n|---|---|\n| E1 | 效率 90 % |\n', encoding='utf-8')
        (self.req / 'figure.png').write_bytes(b'\x89PNG')

    def ledger(self, *docs):
        intent = self.dir / 'intent.json'
        source = [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in docs]
        intent.write_text(json.dumps({'requirement_source': source[0] if len(source) == 1 else source}), encoding='utf-8')
        return {'intent.json': str(intent)}

    def test_a_document_of_the_brief_left_out_of_the_requirement_source_is_refused(self):
        errors = requirement_omission_errors({'requirements': str(self.req)}, self.ledger(self.a))
        self.assertEqual(len(errors), 1)
        self.assertIn('工程规格.md', errors[0])

    def test_every_document_transcribed_passes_and_non_text_files_are_ignored(self):
        self.assertEqual(requirement_omission_errors({'requirements': str(self.req)}, self.ledger(self.a, self.b)), [])

    def test_no_declared_requirements_input_is_not_checked(self):
        self.assertEqual(requirement_omission_errors({}, self.ledger(self.a)), [])

    def test_an_intent_without_a_requirement_source_is_left_to_the_plan(self):
        intent = self.dir / 'bare.json'
        intent.write_text('{}', encoding='utf-8')
        self.assertEqual(requirement_omission_errors({'requirements': str(self.req)}, {'intent.json': str(intent)}), [])


if __name__ == '__main__':
    unittest.main()

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


if __name__ == '__main__':
    unittest.main()

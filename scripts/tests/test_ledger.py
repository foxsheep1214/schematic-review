"""The newest improvement-ledger entry cites its event, counts its causes and lists existing files."""
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import check_ledger  # noqa: E402

GOOD = """# ledger

## Thing (2026-10-19)

Prose about it.

- Event: review:SR-20260101-示例审查-0000000/W-1, user:2026-10-19
- Causes: rule_missing 1, knowledge_missing 2
- Changed: SKILL.md, scripts/review_selection.py

## Older entry

no fields at all
"""


class LedgerTests(unittest.TestCase):
    def test_real_ledger_latest_entry_passes(self):
        text = check_ledger.LEDGER.read_text(encoding='utf-8')
        self.assertEqual([], check_ledger.check_entry(check_ledger.latest_entry(text)))

    def test_fields_are_required_and_files_must_exist(self):
        self.assertEqual([], check_ledger.check_entry(check_ledger.latest_entry(GOOD)))
        bad = GOOD.replace('review:SR-20260101-示例审查-0000000/W-1, user:2026-10-19', 'the last review') \
                  .replace('rule_missing 1, knowledge_missing 2', 'various') \
                  .replace('scripts/review_selection.py', 'scripts/nope.py')
        problems = check_ledger.check_entry(check_ledger.latest_entry(bad))
        self.assertEqual(3, len(problems), problems)
        self.assertTrue(any('Event:' in p for p in problems))
        self.assertTrue(any('Causes:' in p for p in problems))
        self.assertTrue(any('scripts/nope.py does not exist' in p for p in problems))

    def test_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'l.md'
            p.write_text(GOOD, encoding='utf-8')
            self.assertEqual(0, check_ledger.main([str(p)]))
            p.write_text(GOOD.replace('- Changed: SKILL.md, scripts/review_selection.py', ''), encoding='utf-8')
            self.assertEqual(1, check_ledger.main([str(p)]))


if __name__ == '__main__':
    unittest.main()

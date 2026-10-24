"""intent.json is read as strictly as the plan and the results (SR self-check of 2026-10-24, 2.8, user: 字段白名单 + 版本必填).

A misspelt top-level key (`power_rail` for `power_rails`) used to pass silently and leave every rail undeclared; an
intent without `schema_version` passed too.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import checkers
from plan_review import INTENT_FIELDS, validate_intent


class IntentFieldTests(unittest.TestCase):
    def test_a_misspelt_key_is_refused(self):
        errors = validate_intent({'schema_version': 4, 'power_rail': {}})
        self.assertTrue(any('power_rail' in e and 'power_rails' in e for e in errors), errors)

    def test_the_version_is_required(self):
        self.assertTrue(any('schema_version' in e for e in validate_intent({'review_mode': 'first'})))
        self.assertEqual(validate_intent({'schema_version': 4, 'review_mode': 'first'}), [])

    def test_every_checker_section_is_a_field(self):
        self.assertTrue({c.intent_key for c in checkers.REGISTRY if c.intent_key} <= INTENT_FIELDS)


if __name__ == '__main__':
    unittest.main()

"""Input dependency, derived stages and question groups in the rule catalog."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import catalog


class CatalogInputTests(unittest.TestCase):
    def test_every_rule_has_known_inputs_and_one_stage(self):
        for rule in catalog.RULES:
            self.assertTrue(set(catalog.inputs_of(rule.id)) <= set(catalog.INPUTS), rule.id)
            self.assertIn(catalog.stage_of(rule.id), catalog.STAGES, rule.id)

    def test_scripts_never_need_reviewer_inputs(self):
        # A script rule that needed requirements or drawings could not run unattended.
        for rule in catalog.RULES:
            if catalog.executor_of(rule.id) == 'script':
                self.assertFalse({'requirement', 'drawing', 'ledger'} & set(catalog.inputs_of(rule.id)), rule.id)

    def test_cold_needs_no_datasheet_and_hot_does(self):
        for rule in catalog.rules(stage='cold'):
            self.assertNotIn('datasheet', catalog.inputs_of(rule.id), rule.id)
        for rule in catalog.rules(stage='hot'):
            self.assertIn('datasheet', catalog.inputs_of(rule.id), rule.id)
        self.assertEqual({r.id for r in catalog.rules(stage='hot')},
                         {r.id for r in catalog.rules(needs='datasheet') if catalog.executor_of(r.id) == 'script'})

    def test_question_groups_join_parts_of_one_question(self):
        for key, (name, members) in catalog.QUESTIONS.items():
            self.assertGreaterEqual(len(members), 2, key)
            self.assertEqual(1, len({catalog.domain_of(r) for r in members}), key)
            for rule_id in members:
                self.assertEqual(key, catalog.question_of(rule_id)[0])
        self.assertIsNone(catalog.question_of('NET-A01'))


if __name__ == '__main__':
    unittest.main()

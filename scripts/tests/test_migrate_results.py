"""A results file is carried to the current format where the change was only a renaming (2026-10-27, user: 按照你推荐的
三种方式进行修改): format 14's basis.derivation and worst_case.bound.basis become the bounding table's method; a step
that needs the reviewer (format 13 → 14 rewrote the findings) is named and not migrated."""
import copy
import json
import os
import tempfile
import unittest

from test_review_functions import bias_function, with_datum
import migrate_results
import results_model
from review_functions import function_errors


def format_14():
    fn = bias_function('PASS')
    basis = fn['calculation']['margin']['basis']
    basis['derivation'] = {'G1': 'GUARANTEED_LIMIT'}[basis.pop('method')]
    datum = with_datum()
    bound = datum['open'][0]['worst_case']['bound']
    bound['basis'] = {'G2': 'ADJACENT_TEST_POINT'}[bound.pop('method')]
    return {'schema_version': 14, 'functions': [fn, dict(datum, id='FN-HV')]}


class MigrateTests(unittest.TestCase):
    def test_format_14_is_renamed_to_the_current_format(self):
        old = format_14()
        self.assertTrue(any('derivation' in e for e in function_errors({'functions': old['functions'][:1]})))
        report, done = migrate_results.migrate(copy.deepcopy(old))
        self.assertEqual(report['schema_version'], results_model.SCHEMA_VERSION)
        for fn in report['functions']:   # each fixture function stands alone
            self.assertEqual(function_errors({'functions': [fn]}), [])
        self.assertEqual(report['functions'][0]['calculation']['margin']['basis']['method'], 'G1')
        self.assertEqual(report['functions'][1]['open'][0]['worst_case']['bound']['method'], 'G2')
        self.assertEqual(len(done), 3, done)

    def test_running_it_twice_changes_nothing(self):
        report, _ = migrate_results.migrate(format_14())
        again, done = migrate_results.migrate(copy.deepcopy(report))
        self.assertEqual(again, report)
        self.assertEqual(done, [])

    def test_a_method_the_cell_already_names_wins(self):
        report = format_14()
        report['functions'][0]['calculation']['margin']['basis']['method'] = 'G3'
        migrated, _ = migrate_results.migrate(report)
        self.assertEqual(migrated['functions'][0]['calculation']['margin']['basis']['method'], 'G3')

    def test_a_step_that_needs_the_reviewer_is_named_not_migrated(self):
        report = dict(format_14(), schema_version=13)
        with self.assertRaises(ValueError) as caught:
            migrate_results.migrate(report)
        self.assertIn('14: a finding says root_cause', str(caught.exception))
        with self.assertRaises(ValueError) as caught:
            migrate_results.migrate(dict(report, schema_version=5))
        self.assertIn('a step before format 7', str(caught.exception))

    def test_the_gate_names_the_script(self):
        found = results_model.shape_errors({'schema_version': 14, 'functions': []})
        self.assertTrue(any('migrate_results.py' in e for e in found), found)

    def test_the_command_rewrites_the_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'review-results.json')
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(format_14(), f, ensure_ascii=False)
            self.assertEqual(migrate_results.main([path]), 0)
            with open(path, encoding='utf-8') as f:
                self.assertEqual(json.load(f)['schema_version'], results_model.SCHEMA_VERSION)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(dict(format_14(), schema_version=12), f)
            self.assertEqual(migrate_results.main([path]), 1)


if __name__ == '__main__':
    unittest.main()

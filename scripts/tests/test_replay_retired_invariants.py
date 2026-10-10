"""Forward contract: database retention and provided-log scanning may not regress."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import unittest

ROOT = Path(os.environ.get('SR_RUNTIME', str(Path(__file__).resolve().parents[2])))
BENCH = ROOT / 'evals/kicad_replay_bench'
spec = importlib.util.spec_from_file_location('retired_invariant_runner', BENCH / 'run.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class RetiredInvariantTests(unittest.TestCase):
    def setUp(self):
        self.expected = json.loads((BENCH / 'expected.json').read_text())

    def assert_required_execution_cannot_be_waived(self, field):
        checked = 0
        for case, answer in self.expected['cases'].items():
            if answer['fields'].get(field) is not True:
                continue
            with self.subTest(case=case, field=field):
                observed = copy.deepcopy(answer['fields'])
                observed[field] = False
                row = next(r for r in runner.judge(case, observed, self.expected) if r['field'] == field)
                self.assertEqual(row['status'], 'MISMATCH', 'Already-fixed mandatory behavior must reject regression')
            checked += 1
        self.assertGreater(checked, 0)

    def test_strict_database_retention_regression_is_rejected(self):
        self.assert_required_execution_cannot_be_waived('parse.strict_db_written')

    def test_provided_log_scan_regression_is_rejected(self):
        for field in ('lint.DOC-A01_executed', 'lint.DOC-A02_executed'):
            self.assert_required_execution_cannot_be_waived(field)

    def test_frozen_expected_values_still_match(self):
        for case, answer in self.expected['cases'].items():
            self.assertTrue(all(r['status'] == 'MATCH' for r in runner.judge(case, answer['fields'], self.expected)))


if __name__ == '__main__':
    unittest.main()

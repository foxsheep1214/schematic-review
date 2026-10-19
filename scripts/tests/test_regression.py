"""run_regression re-validates registered review records read-only and fails only when they get worse."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import run_regression  # noqa: E402


def write_record(root, results):
    record = root / 'record'
    record.mkdir(parents=True)
    (record / 'review-plan.json').write_text(json.dumps({'schema_version': 1, 'checks': []}), encoding='utf-8')
    (record / 'review-results.json').write_text(json.dumps(results), encoding='utf-8')
    (record / 'review-gate.json').write_text(json.dumps({'valid': False, 'release': 'NO_GO'}), encoding='utf-8')
    return record


class RegressionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        # a schema-2 ledger: the validator refuses it with one error and never reads the checks
        self.record = write_record(self.tmp / 'SR-old', {'schema_version': 2, 'checks': [
            {'id': 'A', 'review_result': 'PASS'}, {'id': 'B', 'review_result': 'INSUFFICIENT'},
            {'id': 'C', 'review_result': 'INSUFFICIENT'}]})
        self.boards = self.tmp / 'boards.json'
        self.boards.write_text(json.dumps({'schema_version': 1, 'boards': [
            {'id': 'old', 'path': str(self.tmp / 'SR-old')},
            {'id': 'gone', 'path': str(self.tmp / 'SR-missing')}]}), encoding='utf-8')
        self.baseline = self.tmp / 'baseline.json'

    def snapshot(self):
        return sorted((p, p.stat().st_mtime_ns) for p in self.record.rglob('*'))

    def test_measure_counts_errors_results_and_releases(self):
        before = self.snapshot()
        m = run_regression.measure({'path': str(self.tmp / 'SR-old')})
        self.assertEqual('MEASURED', m['status'])
        self.assertEqual(1, m['validation_errors'])
        self.assertEqual({'FAIL': 0, 'INSUFFICIENT': 2, 'NA': 0, 'PASS': 1}, m['results'])
        self.assertEqual(('NO_GO', 'NO_GO'), (m['release'], m['recorded_release']))
        self.assertEqual(before, self.snapshot(), 'the record must not be written')
        self.assertEqual('SKIPPED', run_regression.measure({'path': str(self.tmp / 'SR-missing')})['status'])

    def test_new_then_baseline_then_pass(self):
        report = run_regression.run(self.boards, self.baseline)
        self.assertEqual('NEW', report['status'])
        self.assertEqual('SKIPPED', report['boards']['gone']['status'])
        self.assertEqual('UPDATED', run_regression.run(self.boards, self.baseline, update=True)['status'])
        base = json.loads(self.baseline.read_text(encoding='utf-8'))['boards']
        self.assertEqual(['old'], list(base))
        self.assertEqual(1, base['old']['validation_errors'])
        self.assertEqual('PASS', run_regression.run(self.boards, self.baseline)['status'])

    def test_more_errors_or_worse_release_fail(self):
        run_regression.run(self.boards, self.baseline, update=True)
        base = json.loads(self.baseline.read_text(encoding='utf-8'))
        base['boards']['old']['validation_errors'] = 0
        base['boards']['old']['release'] = 'GO'
        self.baseline.write_text(json.dumps(base), encoding='utf-8')
        report = run_regression.run(self.boards, self.baseline)
        self.assertEqual('FAIL', report['status'])
        reasons = report['boards']['old']['reasons']
        self.assertTrue(any('validation errors 0 -> 1' in r for r in reasons), reasons)
        self.assertTrue(any('release GO -> NO_GO' in r for r in reasons), reasons)
        self.assertEqual(1, run_regression.main(['--boards', str(self.boards), '--baseline', str(self.baseline)]))

    def test_fewer_errors_pass_and_suggest_lowering_the_bar(self):
        run_regression.run(self.boards, self.baseline, update=True)
        base = json.loads(self.baseline.read_text(encoding='utf-8'))
        base['boards']['old']['validation_errors'] = 5
        self.baseline.write_text(json.dumps(base), encoding='utf-8')
        report = run_regression.run(self.boards, self.baseline)
        self.assertEqual('PASS', report['status'])
        self.assertIn('improved', report['boards']['old']['reasons'][0])

    def test_registered_records_are_real_review_folders(self):
        boards = json.loads((run_regression.REG / 'boards.json').read_text(encoding='utf-8'))['boards']
        self.assertTrue(boards)
        for b in boards:
            self.assertTrue(b['id'] and Path(b['path']).name.startswith('SR-'), b)


if __name__ == '__main__':
    unittest.main()

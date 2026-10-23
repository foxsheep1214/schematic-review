"""A circuit-type coverage row (REQ-Q07) follows the rows of its circuit type (consistency proposals 2026-10-23, 5b).

Two reviews of one board hung the same defect on different rows, one of them on the coverage row it picked by hand.
The coverage row is bound to the applicable rows of its circuit type and answers coverage only: once every bound row
has a result it passes and copies no member's result (execution-consistency.md); a hand-filled result that differs is
refused.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requirement_bindings as rb


def plan():
    return {'checks': [
        {'id': 'REQ-Q07.PWR', 'rule': 'REQ-Q07', 'applicability': 'APPLICABLE', 'circuit_type': 'PWR',
         'object': {'circuit_type': 'PWR'}},
        {'id': 'PWR-C04.A', 'rule': 'PWR-C04', 'applicability': 'APPLICABLE', 'circuit_type': 'PWR'},
        {'id': 'PWR-C05.A', 'rule': 'PWR-C05', 'applicability': 'APPLICABLE', 'object': {'circuit_type': 'PWR'}},
        {'id': 'PWR-C06.A', 'rule': 'PWR-C06', 'applicability': 'NOT_APPLICABLE', 'circuit_type': 'PWR'},
        {'id': 'ANA-C01.A', 'rule': 'ANA-C01', 'applicability': 'APPLICABLE', 'circuit_type': 'ANALOG'},
        {'id': 'DEV-C05.U1', 'rule': 'DEV-C05', 'applicability': 'APPLICABLE'}]}


class CoverageBindingTests(unittest.TestCase):
    def test_the_coverage_row_is_bound_to_the_applicable_rows_of_its_type(self):
        p = plan()
        rb.attach(p['checks'])
        self.assertEqual(p['checks'][0]['bound_checks'], ['PWR-C04.A', 'PWR-C05.A'])
        self.assertEqual(rb.errors(p), [])
        p['checks'][0]['bound_checks'] = ['PWR-C04.A']
        self.assertTrue(any('REQ-Q07.PWR' in e for e in rb.errors(p)))

    def test_derive_writes_coverage_without_copying_the_defect(self):
        p = plan()
        rb.attach(p['checks'])
        results = {'checks': [
            {'id': 'PWR-C04.A', 'review_result': 'PASS'},
            {'id': 'PWR-C05.A', 'review_result': 'FAIL', 'fail_ref': 'FN-PWR/TON', 'finding_id': 'F-1', 'severity': 'P1'}],
            'findings': [{'id': 'F-1', 'check_ids': ['PWR-C05.A']}]}
        _, errors = rb.derive(p, results)
        self.assertEqual(errors, [])
        row = next(r for r in results['checks'] if r['id'] == 'REQ-Q07.PWR')
        self.assertEqual((row['review_result'], row['derived_from']), ('PASS', ['PWR-C04.A', 'PWR-C05.A']))
        self.assertNotIn('fail_ref', row)
        self.assertNotIn('finding_id', row)
        self.assertEqual(results['findings'][0]['check_ids'], ['PWR-C05.A'])   # the defect stays on its own row
        self.assertEqual(rb.coverage_errors({c['id']: c for c in p['checks']},
                                            {r['id']: r for r in results['checks']}), [])

    def test_a_hand_filled_coverage_result_that_differs_is_refused(self):
        p = plan()
        rb.attach(p['checks'])
        rows = {'PWR-C04.A': {'review_result': 'PASS'}, 'PWR-C05.A': {'review_result': 'INSUFFICIENT'},
                'REQ-Q07.PWR': {'review_result': 'FAIL'}}
        errors = rb.coverage_errors({c['id']: c for c in p['checks']}, rows)
        self.assertTrue(any('REQ-Q07.PWR' in e and '不复制' in e for e in errors), errors)
        rows['REQ-Q07.PWR']['review_result'] = 'PASS'
        self.assertEqual(rb.coverage_errors({c['id']: c for c in p['checks']}, rows), [])

    def test_before_every_row_is_reviewed_the_coverage_row_is_not_derived(self):
        p = plan()
        rb.attach(p['checks'])
        rows = {'PWR-C04.A': {'review_result': 'PASS'}, 'REQ-Q07.PWR': {'review_result': 'INSUFFICIENT'}}
        self.assertEqual(rb.coverage_errors({c['id']: c for c in p['checks']}, rows), [])
        results = {'checks': [{'id': 'PWR-C04.A', 'review_result': 'PASS'}]}
        rb.derive(p, results)
        self.assertNotIn('REQ-Q07.PWR', [r['id'] for r in results['checks']])


if __name__ == '__main__':
    unittest.main()

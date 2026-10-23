"""An engineering-calculation aspect passes on a margin (consistency proposals of 2026-10-23, 1e).

One review of R5 wrote 3 margins in its whole record and the other 43: the first passed calculation rows on a sentence.
A row whose rule is an engineering calculation (method C) passes only on a margin that proves its aspect; a sentence
closes only connection tracing (T) and clause checks (D). The vendor reference circuit with the same connection and a
load no heavier (5c, tier 2) is the one judgement that also closes a calculation aspect. A fail keeps its own grounds
(a shortfall, a violated clause, a point outside the specified region).
"""
import copy
import unittest

from test_review_functions import ASPECT, STATES, bias_function, ledger
from test_operating_point_tiers import REFERENCE
import validate_review as vr


def judged_only():
    fn = bias_function('PASS')
    del fn['calculation']['margin']
    fn['judgements'] = [{'aspect': ASPECT, 'conditions': ['c4', 'c5'], 'says': '偏置路径按 U1 的连接要求接到 VCC',
                         'states': list(STATES)}]
    return fn


class CalculationAspectTests(unittest.TestCase):
    def test_a_calculation_row_does_not_pass_on_a_sentence(self):
        out = vr.validate_review(*ledger(judged_only()))
        self.assertTrue(any('engineering calculation' in e for e in out['errors']), out['errors'])

    def test_a_margin_passes_it(self):
        out = vr.validate_review(*ledger(bias_function('PASS')))
        self.assertTrue(out['valid'], out['errors'])

    def test_the_vendor_reference_circuit_passes_it(self):
        fn = judged_only()
        fn['conditions'].append(copy.deepcopy(REFERENCE))
        fn['judgements'][0]['conditions'] = ['c6']
        out = vr.validate_review(*ledger(fn))
        self.assertFalse([e for e in out['errors'] if 'engineering calculation' in e], out['errors'])

    def test_a_tracing_row_still_passes_on_a_sentence(self):
        p, r, db = ledger(judged_only())
        for row in p['checks']:
            if row['id'].startswith('PWR-C02.'):
                row['method'] = 'T'
        out = vr.validate_review(p, r, db)
        self.assertFalse([e for e in out['errors'] if 'engineering calculation' in e], out['errors'])


if __name__ == '__main__':
    unittest.main()

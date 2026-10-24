"""A decisive margin says how its bound was derived and which end of each toleranced input it took; an unboundable
quantity says why the adjacent test point does not bound it (consistency proposals of 2026-10-23, 1a–1c; results 5).

On R5 one review left an over-voltage chain open although below the zener's test current VZ only falls, so the trip's
upper bound followed from the test point; the other marked a trip lower bound on the unfavourable side as guaranteed,
and took an NTC's nominal 5 Ω for a cold inrush that the 4 Ω tolerance end decides. The basis now carries
`derivation` (how the bound was obtained) and `corners` (each toleranced input, the condition it came from and the end
taken), and an unboundable quantity carries `monotonic_tried`.
"""
import copy
import unittest

from test_review_functions import HV_TRIED, bias_function, guaranteed, with_datum
import results_model
from review_functions import function_errors

CORNERS = [{'input': 'vf_d2', 'condition': 'c1', 'picked': 'max', 'why': 'VF 越大 VCC 越低'},
           {'input': 'vgs_q2', 'condition': 'c2', 'picked': 'max', 'why': 'VGS(th) 越大 VCC 越低'}]


def margin_errors(**basis):
    fn = bias_function('PASS')
    base = {k: v for k, v in guaranteed().items() if k not in ('derivation', 'corners', 'no_corners_reason')}
    fn['calculation']['margin']['basis'] = dict(base, **basis)
    for k in [k for k, v in basis.items() if v is None]:
        del fn['calculation']['margin']['basis'][k]
    return function_errors({'functions': [fn]})


class DerivationTests(unittest.TestCase):
    def test_a_decisive_margin_names_its_derivation(self):
        self.assertEqual(margin_errors(derivation='GUARANTEED_LIMIT', corners=CORNERS), [])
        self.assertTrue(any('derivation' in e for e in margin_errors(derivation=None, corners=CORNERS)))
        self.assertTrue(any('derivation' in e for e in margin_errors(derivation='GUESS', corners=CORNERS)))

    def test_a_bound_from_a_typical_curve_is_an_estimate(self):
        found = margin_errors(derivation='TYPICAL_CURVE', corners=CORNERS)
        self.assertTrue(any('TYPICAL_CURVE' in e and 'ESTIMATE' in e for e in found), found)
        found = margin_errors(kind='ESTIMATE', derivation='TYPICAL_CURVE', corners=None)
        self.assertFalse([e for e in found if 'TYPICAL_CURVE' in e or 'derivation' in e or 'corners' in e], found)

    def test_a_bound_from_a_test_point_says_the_point_is_on_the_favourable_side(self):
        for derivation in ('ADJACENT_TEST_POINT', 'MONOTONIC'):
            self.assertTrue(any('monotonic' in e for e in margin_errors(derivation=derivation, corners=CORNERS)))
            ok = margin_errors(derivation=derivation, corners=CORNERS, monotonic={'curve': 'c1', 'side': 'FAVORABLE'})
            self.assertEqual(ok, [], derivation)
            bad = margin_errors(derivation=derivation, corners=CORNERS, monotonic={'curve': 'c1', 'side': 'UNFAVORABLE'})
            self.assertTrue(any('FAVORABLE' in e for e in bad), derivation)
            bad = margin_errors(derivation=derivation, corners=CORNERS, monotonic={'curve': 'c9', 'side': 'FAVORABLE'})
            self.assertTrue(any('monotonic' in e for e in bad), derivation)

    def test_a_bound_through_a_temperature_coefficient_cites_it(self):
        self.assertTrue(any('tempco' in e for e in margin_errors(derivation='TEMPCO', corners=CORNERS)))
        self.assertEqual(margin_errors(derivation='TEMPCO', corners=CORNERS, tempco='c2'), [])
        self.assertTrue(any('tempco' in e for e in margin_errors(derivation='TEMPCO', corners=CORNERS, tempco='c5')))


class CornerTests(unittest.TestCase):
    def test_each_toleranced_input_names_the_end_its_condition_gives(self):
        self.assertTrue(any('corners' in e for e in margin_errors(derivation='GUARANTEED_LIMIT', corners=None)))
        self.assertTrue(any('corners' in e for e in margin_errors(derivation='GUARANTEED_LIMIT', corners=[])))
        self.assertEqual(margin_errors(derivation='GUARANTEED_LIMIT', corners=[],
                                       no_corners_reason='输入都是网表上的定值，无公差'), [])
        wrong = copy.deepcopy(CORNERS)
        wrong[0]['picked'] = 'min'   # c1 gives only a maximum
        found = margin_errors(derivation='GUARANTEED_LIMIT', corners=wrong)
        self.assertTrue(any('c1' in e and 'min' in e for e in found), found)
        for broken in ({'condition': 'c9'}, {'condition': 'c5'}, {'picked': 'typ'}, {'why': ''}, {'input': ''}):
            bad = copy.deepcopy(CORNERS)
            bad[0].update(broken)
            self.assertTrue(any('corners' in e for e in margin_errors(derivation='GUARANTEED_LIMIT', corners=bad)), broken)


class MonotonicTriedTests(unittest.TestCase):
    def test_an_unboundable_quantity_says_why_the_test_point_does_not_bound_it(self):
        worst = {'not_boundable_reason': '手册没有 40 V 以下的测试点', 'operating_point_specified': True, 'specified_by': 'c4',
                 'curves_checked': [{'source': 'evidence/ds/U1.txt', 'locator': 'Fig. 12 IHV vs VHV'}]}
        fn = with_datum(**worst)
        self.assertTrue(any('monotonic_tried' in e for e in function_errors({'functions': [fn]})))
        fn['open'][0]['worst_case']['monotonic_tried'] = dict(HV_TRIED)
        self.assertEqual(function_errors({'functions': [fn]}), [])
        # format 5 wrote the side as a sentence; format 6 writes it in numbers (test_one_sided_bounds.py)
        fn['open'][0]['worst_case']['monotonic_tried'] = {'unfavorable_side': '低于测试点', 'why_not': '手册没说单调'}
        self.assertTrue(any('monotonic_tried' in e for e in function_errors({'functions': [fn]})))


class FormatTests(unittest.TestCase):
    def test_an_older_results_format_is_not_read(self):
        self.assertEqual(results_model.SCHEMA_VERSION, 6)
        errors = results_model.shape_errors({'schema_version': 4, 'functions': [], 'checks': []})
        self.assertTrue(any('schema_version must be 6' in e for e in errors), errors)


if __name__ == '__main__':
    unittest.main()

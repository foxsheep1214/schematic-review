"""Where the datasheet describes the usage, not the test point that misses it (bounding consistency proposals of
2026-10-23, item 2 and decision 2-A).

On the R5 acceptance re-review all 19 vendor-data items of one review named, as the clause where the datasheet
describes this usage, the very test-point limit that does not reach the operating point (a zener's VZ at 5 mA for a
part run at 0.06-1.3 mA); the other review judged the same point outside the specified region. `specified_by` may not
be one of the item's test points. It names a clause or application text, or a typical curve whose regime covers the
point; with a curve the item gives the estimate read off it (`worst_case.typical_estimate`, an ESTIMATE citing the
curve), and an estimate already short is a fail: a typical part is a reachable case, so the fail item's margin is a
REACHABLE_CASE read off the typical curve.
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from review_functions import function_errors
from test_one_sided_bounds import unboundable
from test_review_functions import bias_function

CURVE = {'id': 'k1', 'kind': 'TYPICAL_REFERENCE', 'source': 'evidence/ds/D2.txt', 'locator': 'p9 Fig. 4 IZ-VZ',
         'says': 'IZ-VZ 典型曲线画到 10 µA', 'regime': 'IZ 10 µA..10 mA，25 °C', 'use': '低电流的 VZ', 'curve': True}
# An application note's text describing the usage is a typical reference but not a curve (SR self-check 2.4).
NOTE = {'id': 'k2', 'kind': 'TYPICAL_REFERENCE', 'source': 'evidence/ds/D2.txt', 'locator': 'p12 §9 Application',
        'says': '应用说明：齐纳管可作偏置钳位，低电流下工作', 'use': '这种用法写在应用说明里'}


def estimate(value=0.3):
    return {'value': value, 'unit': 'V', 'against': 'BIAS 下限 11.25 V',
            'basis': {'kind': 'ESTIMATE', 'comparison': 'GE', 'conditions': ['k1'], 'scope': '按 IZ-VZ 典型曲线读 0.06 mA'}}


def on_curve(**worst):
    fn = unboundable()
    fn['conditions'].append(copy.deepcopy(CURVE))
    fn['open'][0]['checked'].append('k1')
    fn['open'][0]['worst_case'].update(dict({'specified_by': 'k1', 'typical_estimate': estimate()}, **worst))
    return fn


def errors(fn):
    return function_errors({'functions': [fn]})


def about(found, word):
    return [e for e in found if word in e]


class TestPointTests(unittest.TestCase):
    def test_a_clause_describing_the_usage_passes(self):
        self.assertEqual(errors(unboundable()), [])

    def test_the_test_point_that_misses_the_point_is_not_where_the_usage_is_described(self):
        fn = unboundable()
        fn['open'][0]['worst_case']['specified_by'] = 'z1'
        self.assertTrue(about(errors(fn), 'test point'), errors(fn))


class ApplicationTextTests(unittest.TestCase):
    def test_application_text_needs_no_regime_or_estimate(self):
        fn = unboundable()
        fn['conditions'].append(copy.deepcopy(NOTE))
        fn['open'][0]['checked'].append('k2')
        fn['open'][0]['worst_case']['specified_by'] = 'k2'
        self.assertEqual(errors(fn), [])

    def test_curve_is_a_boolean(self):
        fn = on_curve()
        next(c for c in fn['conditions'] if c['id'] == 'k1')['curve'] = 'yes'
        self.assertTrue(about(errors(fn), 'curve'))


class TypicalCurveTests(unittest.TestCase):
    def test_a_curve_covering_the_point_with_its_estimate_passes(self):
        self.assertEqual(errors(on_curve()), [])

    def test_the_curve_says_the_range_it_covers(self):
        fn = on_curve()
        next(c for c in fn['conditions'] if c['id'] == 'k1').pop('regime')
        self.assertTrue(about(errors(fn), 'regime'))

    def test_the_estimate_off_the_curve_is_given(self):
        fn = on_curve()
        del fn['open'][0]['worst_case']['typical_estimate']
        self.assertTrue(about(errors(fn), 'typical_estimate'))
        for broken in ({'value': None}, {'unit': ''}, {'against': ''}):
            fn = on_curve(typical_estimate=dict(estimate(), **broken))
            self.assertTrue(about(errors(fn), 'typical_estimate'), broken)

    def test_the_estimate_is_an_estimate_read_off_that_curve(self):
        fn = on_curve(typical_estimate=dict(estimate(), basis=dict(estimate()['basis'], conditions=['z1'])))
        self.assertTrue(about(errors(fn), 'k1'))
        reachable = dict(estimate()['basis'], kind='REACHABLE_CASE', limit='z1', derivation='TYPICAL_CURVE',
                         regime='IZ 5 mA', corners=[], no_corners_reason='典型件只读一个点',
                         joint='典型件在 0.06 mA 时的 VZ 与同一温度下的 VCC(off) 同时出现')
        found = errors(on_curve(typical_estimate=dict(estimate(), basis=reachable)))
        self.assertEqual(found, [e for e in found if 'an ESTIMATE whose conditions include' in e])
        self.assertTrue(found)   # a well-formed reachable case is still not the estimate this item gives

    def test_an_estimate_already_short_is_a_fail_not_a_vendor_request(self):
        found = errors(on_curve(typical_estimate=estimate(-0.4)))
        self.assertTrue(about(found, 'REACHABLE_CASE'), found)
        found = errors(on_curve(typical_estimate=dict(estimate(0), basis=dict(estimate()['basis'], comparison='GT'))))
        self.assertTrue(about(found, 'REACHABLE_CASE'), found)


class ReachableTypicalTests(unittest.TestCase):
    """The fail that follows: a typical part is reachable, so a REACHABLE_CASE may be read off a typical curve."""

    def margin(self, kind):
        fn = bias_function('FAIL')
        fn['conditions'].append(dict(copy.deepcopy(CURVE), id='c6'))
        basis = dict(fn['calculation']['margin']['basis'], kind=kind, derivation='TYPICAL_CURVE', conditions=['c6'],
                     joint='典型件在 0.06 mA 时的 VZ 与同一温度下的 VCC(off) 同时出现')
        fn['calculation']['margin'].update(value=-0.4, basis=basis)
        return [e for e in errors(fn) if 'TYPICAL_CURVE' in e]

    def test_a_reachable_case_may_rest_on_a_typical_curve(self):
        self.assertEqual(self.margin('REACHABLE_CASE'), [])

    def test_a_guaranteed_bound_still_may_not(self):
        self.assertTrue(self.margin('GUARANTEED_BOUND'))


if __name__ == '__main__':
    unittest.main()

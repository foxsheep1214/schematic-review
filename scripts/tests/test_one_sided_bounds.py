"""An unboundable quantity is written as numbers the gate can check (bounding consistency proposals of 2026-10-23,
item 1; results format 6).

On the R5 acceptance re-review one review called 19 quantities unboundable, 16 of them with one sentence as the
unfavourable side and the not-boundable reason copied as why_not; one of them sat between two test points the
datasheet gives (a zener at 1-1.56 mA, VZ at 2 mA and rdif at 1 mA and 0.5 mA), which the other review bounded.
`monotonic_tried` now names the side (UPPER or LOWER), the quantity, this board's operating range and the datasheet
test points with their values, and why_not may not repeat the reason. A range inside two test points is bounded, not
opened; a range only partly outside opens only the part outside (`open_range`) and the part inside is a margin. Each
edge of the item names the open side, and the other side is either decided by a margin or not decisive, with why.
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import results_model
from review_functions import function_errors
from test_review_functions import ASPECT, STATES, with_datum

REASON = '手册只在 5 mA 给 VZ，低电流下界推不出'


def tried(**extra):
    out = {'side': 'LOWER', 'cell': 'ZENER-VZ-LOWER', 'quantity': 'D2 稳压值 VZ', 'operating_point': {'min': 0.06, 'max': 1.3, 'unit': 'mA'},
           'test_points': [{'condition': 'z1', 'at': {'value': 5, 'unit': 'mA'}}],
           'why_not': '0.06–1.3 mA 全在 5 mA 测试点以下，手册没有更低电流的 VZ 或 rdif 保证值',
           'other_side': 'NOT_DECISIVE', 'other_side_reason': '上界只决定 Q2 栅压不超额定，已在别的方面算过'}
    out.update(extra)
    return {k: v for k, v in out.items() if v is not None}


Z1 = {'id': 'z1', 'kind': 'NUMERIC_LIMIT', 'source': 'evidence/ds/D2.txt', 'locator': 'p5 Table 8',
      'says': 'VZ 15.68..16.32 V @ IZ 5 mA', 'limit': {'min': 15.68, 'max': 16.32, 'unit': 'V'}, 'regime': 'IZ 5 mA', 'use': 'VZ 测试点'}
R1 = {'id': 'r1', 'kind': 'NUMERIC_LIMIT', 'source': 'evidence/ds/D2.txt', 'locator': 'p5 Table 8',
      'says': 'rdif ≤ 170 Ω @ IZ 1 mA', 'limit': {'max': 170, 'unit': 'Ω'}, 'regime': 'IZ 1 mA', 'use': 'rdif 测试点'}


def unboundable(**monotonic):
    fn = with_datum(not_boundable_reason=REASON, operating_point_specified=True, specified_by='c4',
                    curves_checked=[{'source': 'evidence/ds/D2.txt', 'locator': 'p9 Fig. 4 IZ-VZ'}],
                    monotonic_tried=tried(**monotonic))
    fn['conditions'] += [copy.deepcopy(Z1), copy.deepcopy(R1)]
    item = fn['open'][0]
    item['checked'] = ['c3', 'z1', 'r1']
    for edge in item['decides']:
        edge['side'] = 'LOWER'
    return fn


def errors(fn):
    return function_errors({'functions': [fn]})


def about(found, word):
    return [e for e in found if word in e]


class ShapeTests(unittest.TestCase):
    def test_a_written_one_sided_bound_passes(self):
        self.assertEqual(errors(unboundable()), [])

    def test_the_side_is_upper_or_lower(self):
        for bad in ('缺少的最不利一侧', 'BOTH', None):
            fn = unboundable(side=bad)
            for edge in fn['open'][0]['decides']:
                edge['side'] = bad   # the edges agree, so only the side's own value can be refused
            self.assertTrue(about(errors(fn), 'UPPER or LOWER'), bad)

    def test_the_quantity_and_the_operating_range_are_given(self):
        self.assertTrue(about(errors(unboundable(quantity='')), 'quantity'))
        for bad in ({'min': 1.3, 'max': 0.06, 'unit': 'mA'}, {'min': 0.06, 'unit': 'mA'}, {'min': 0.06, 'max': 1.3}):
            self.assertTrue(about(errors(unboundable(operating_point=bad)), 'operating_point'), bad)

    def test_each_test_point_is_a_condition_read_with_a_value_in_the_unit_of_the_range(self):
        self.assertTrue(about(errors(unboundable(test_points=[])), 'test_points'))
        for bad in ({'condition': 'z9', 'at': {'value': 5, 'unit': 'mA'}},     # not a condition read
                    {'condition': 'z1', 'at': {'value': 5, 'unit': 'V'}},      # another unit
                    {'condition': 'z1', 'at': {'unit': 'mA'}}):
            self.assertTrue(about(errors(unboundable(test_points=[bad])), 'test_points'), bad)

    def test_a_micro_sign_spelt_u_is_the_same_unit(self):
        self.assertEqual(errors(unboundable(operating_point={'min': 60, 'max': 1300, 'unit': 'uA'},
                                            test_points=[{'condition': 'z1', 'at': {'value': 5000, 'unit': 'µA'}}])), [])

    def test_why_not_does_not_repeat_the_reason(self):
        self.assertTrue(about(errors(unboundable(why_not=REASON)), 'why_not'))
        self.assertTrue(about(errors(unboundable(why_not=' ' + REASON + ' ')), 'why_not'))


class BetweenTestPointsTests(unittest.TestCase):
    POINTS = [{'condition': 'z1', 'at': {'value': 2, 'unit': 'mA'}}, {'condition': 'r1', 'at': {'value': 0.5, 'unit': 'mA'}}]

    def test_a_range_inside_two_test_points_is_bounded_not_opened(self):
        found = errors(unboundable(operating_point={'min': 1, 'max': 1.56, 'unit': 'mA'}, test_points=self.POINTS))
        self.assertTrue(about(found, 'ADJACENT_TEST_POINT'), found)

    def test_one_test_point_bounds_nothing_on_its_own(self):
        self.assertEqual(errors(unboundable(operating_point={'min': 1, 'max': 1.56, 'unit': 'mA'},
                                            test_points=self.POINTS[:1])), [])

    def test_a_range_partly_outside_opens_only_the_part_outside(self):
        points = [{'condition': 'z1', 'at': {'value': 5, 'unit': 'mA'}}, {'condition': 'r1', 'at': {'value': 1, 'unit': 'mA'}}]
        fn = unboundable(test_points=points)
        self.assertTrue(about(errors(fn), 'open_range'))
        fn['open'][0]['worst_case']['monotonic_tried']['open_range'] = {'min': 0.06, 'max': 1}
        found = errors(fn)
        self.assertTrue(about(found, 'margin'), found)   # the part inside the test points is decided
        fn['calculation']['margin'] = {'value': 0.4, 'unit': 'V', 'against': 'VCC(off)', 'aspect': ASPECT, 'states': list(STATES),
                                       'basis': {'kind': 'ESTIMATE', 'comparison': 'GE', 'conditions': ['z1', 'r1'],
                                                 'scope': '1–1.3 mA 段'}}
        self.assertEqual(errors(fn), [])
        for bad in ({'min': 0.06, 'max': 1.2}, {'min': 0.01, 'max': 1}, {'min': 1, 'max': 0.06}):
            broken = copy.deepcopy(fn)
            broken['open'][0]['worst_case']['monotonic_tried']['open_range'] = bad
            self.assertTrue(about(errors(broken), 'open_range'), bad)


class SideTests(unittest.TestCase):
    def test_each_edge_names_the_open_side(self):
        fn = unboundable()
        del fn['open'][0]['decides'][0]['side']
        self.assertTrue(about(errors(fn), 'side'))
        fn['open'][0]['decides'][0]['side'] = 'UPPER'
        self.assertTrue(about(errors(fn), 'side'))

    def test_the_other_side_is_decided_by_a_margin_or_not_decisive_with_why(self):
        self.assertTrue(about(errors(unboundable(other_side=None)), 'other_side'))
        self.assertTrue(about(errors(unboundable(other_side_reason='')), 'other_side_reason'))
        fn = unboundable(other_side='DECIDED', other_side_reason=None)
        self.assertTrue(about(errors(fn), 'other_side'))
        fn['calculation']['margin'] = {'value': 1.1, 'unit': 'V', 'against': 'VGS 额定', 'aspect': ASPECT, 'states': list(STATES),
                                       'basis': {'kind': 'ESTIMATE', 'comparison': 'GE', 'conditions': ['z1'],
                                                 'scope': 'VZ 上界'}}
        self.assertEqual(errors(fn), [])


class FormatTests(unittest.TestCase):
    def test_the_results_format_is_6_and_format_5_is_not_read(self):
        self.assertEqual(results_model.SCHEMA_VERSION, 6)
        found = results_model.shape_errors({'schema_version': 5, 'functions': [], 'checks': []})
        self.assertTrue(any('schema_version must be 6' in e for e in found), found)


if __name__ == '__main__':
    unittest.main()


class NoTestPointTests(unittest.TestCase):
    """R6 acceptance 2026-10-24, codex1 SR-03: a datasheet with no numeric point of the quantity at all could not be
    recorded; an empty list with where it was looked for leaves the whole range open."""

    def test_an_empty_list_needs_where_the_datasheet_was_searched(self):
        self.assertTrue(about(errors(unboundable(test_points=[])), 'no_test_points_reason'))
        self.assertTrue(about(errors(unboundable(test_points=[], no_test_points_reason='手册没给')), 'no_test_points_reason'))
        self.assertEqual(errors(unboundable(test_points=[], no_test_points_reason='p5 Table 8 与 p9 Fig. 4 都没有 VZ 对 IZ 的数值点')), [])

"""The comparison counts how one datasheet bound was used in two ways (bounding consistency proposals of 2026-10-23,
item 4).

On the R5 acceptance re-review 92 rows were left open by one review and passed by the other. Of the 19 vendor-data
items of the opening review, 16 wrote the same sentence as the unfavourable side and copied the not-boundable reason
as why_not, and all 19 named the test-point limit that does not reach the operating point as the clause describing
the usage. The tool now counts both on each side, and lists each disagreeing row where the opening item read a
datasheet the other review used in a margin or a fail that decided the row. Rows are paired by check key, so the
datasheet is matched by file: one review's locators carried pages, the other's mostly sections and tables.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import compare_reviews as cr
from test_compare_reviews import ASPECT, side

LIMIT = {'id': 'z1', 'kind': 'NUMERIC_LIMIT', 'source': 'evidence/ds/D1.txt', 'locator': 'p5 Table 8',
         'says': 'VZ 15.68..16.32 V @ IZ 5 mA', 'limit': {'min': 15.68, 'max': 16.32, 'unit': 'V'}, 'regime': 'IZ 5 mA'}
CURVE = {'id': 'k1', 'kind': 'TYPICAL_REFERENCE', 'source': 'evidence/ds/D1.txt', 'locator': 'p9 Fig. 4',
         'says': 'IZ-VZ 曲线画到 10 µA', 'regime': '10 µA..10 mA'}
OTHER = dict(LIMIT, id='w1', source='evidence/ds/U9.txt')
REASON = '只在 5 mA 给保证，低电流下界推不出'


def vendor(key, why_not=REASON, side_text='VZ 下界', specified_by='z1', checked=('z1',)):
    return {'key': key, 'kind': 'VENDOR_DATUM', 'what': '低电流 VZ 下界', 'checked': list(checked),
            'decides': [{'aspect': ASPECT, 'states': ['RUN'], 'via': {'condition': 'z1'}}],
            'severity': {'level': 'P2'},
            'worst_case': {'not_boundable_reason': REASON, 'curves_checked': [{'source': 'evidence/ds/D1.txt',
                                                                               'locator': 'p9'}],
                           'monotonic_tried': {'unfavorable_side': side_text, 'why_not': why_not},
                           'operating_point_specified': True, 'specified_by': specified_by}}


def opening(items, conditions=(LIMIT, CURVE)):
    s = side('BIAS', ['RUN'], 'INSUFFICIENT')
    fn = s['results']['functions'][0]
    fn['conditions'] = [dict(c) for c in conditions]
    fn['open'] = items
    return s


def passing(condition=LIMIT):
    s = side('BIAS', ['RUN'], 'PASS')
    fn = s['results']['functions'][0]
    fn['conditions'] = [dict(condition)]
    fn['calculation'] = {'result': 'x', 'margin': [{'value': 0.4, 'unit': 'V', 'against': 'VCC(on)', 'aspect': ASPECT,
                                                    'states': ['RUN'],
                                                    'basis': {'kind': 'GUARANTEED_BOUND', 'comparison': 'GE',
                                                              'limit': condition['id'],
                                                              'conditions': [condition['id']]}}]}
    return s


def failing(condition=LIMIT):
    s = side('BIAS', ['RUN'], 'PASS')
    fn = s['results']['functions'][0]
    fn['conditions'] = [dict(condition)]
    fn['fails'] = [{'key': 'F', 'what': '工作点超出规定区', 'outside_specified': {'condition': condition['id']},
                    'decides': [{'aspect': ASPECT, 'states': ['RUN']}]}]
    row = next(r for r in s['results']['checks'] if r['id'] == 'PWR-C02.BIAS-RUN.Q2')
    row.update(review_result='FAIL', fail_ref='FN-BIAS/F')
    return s


class BoilerplateTests(unittest.TestCase):
    def test_a_copied_why_not_and_one_side_sentence_for_many_items_are_boilerplate(self):
        s = opening([vendor('A1'), vendor('A2', why_not='另写的理由', side_text='缺少的最不利一侧'),
                     vendor('A3', why_not='又一条理由', side_text='缺少的最不利一侧'),
                     vendor('A4', why_not='rdif 只到 1 mA，0.06 mA 处没有斜率保证', side_text='0.06–1 mA 的 VZ 下界')])
        self.assertEqual(cr.signals(s)['boilerplate_bounding'], 3)

    def test_written_bounding_is_not_boilerplate(self):
        s = opening([vendor('A1', why_not='rdif 只到 1 mA，0.06 mA 处没有斜率保证')])
        self.assertEqual(cr.signals(s)['boilerplate_bounding'], 0)

    def test_whitespace_does_not_hide_a_copy(self):
        s = opening([vendor('A1', why_not=' 只在 5 mA 给保证，低电流下界推不出 ')])
        self.assertEqual(cr.signals(s)['boilerplate_bounding'], 1)


class TestPointAsUsageTests(unittest.TestCase):
    def test_the_test_point_limit_named_as_the_usage_clause_is_counted(self):
        self.assertEqual(cr.signals(opening([vendor('A1')]))['test_point_as_usage'], 1)

    def test_a_curve_covering_the_point_is_not(self):
        s = opening([vendor('A1', specified_by='k1', checked=('z1', 'k1'))])
        self.assertEqual(cr.signals(s)['test_point_as_usage'], 0)

    def test_a_limit_not_among_the_conditions_read_is_not(self):
        s = opening([vendor('A1', specified_by='z1', checked=('k1',))])
        self.assertEqual(cr.signals(s)['test_point_as_usage'], 0)

    def test_both_signals_are_in_the_markdown(self):
        text = cr.markdown(cr.compare(passing(), opening([vendor('A1')])))
        self.assertIn('定界套话', text)
        self.assertIn('测试点限值当用法依据', text)


class SameSourceTests(unittest.TestCase):
    def splits(self, a, b):
        return cr.compare(a, b)['strict']['same_source_splits']

    def test_a_datasheet_read_by_the_open_item_and_used_by_the_passing_margin(self):
        got = self.splits(passing(), opening([vendor('AUX')]))
        self.assertEqual(len(got), 1)
        self.assertEqual({k: got[0][k] for k in ('A', 'B', 'open_side', 'open_ref', 'decided', 'sources')},
                         {'A': 'PWR-C02.BIAS-RUN.Q2', 'B': 'PWR-C02.BIAS-RUN.Q2', 'open_side': 'B',
                          'open_ref': 'FN-BIAS/AUX', 'decided': 'PASS', 'sources': ['evidence/ds/D1.txt']})

    def test_either_side_may_open(self):
        got = self.splits(opening([vendor('AUX')]), passing())
        self.assertEqual([g['open_side'] for g in got], ['A'])

    def test_a_fail_on_the_same_datasheet_counts_too(self):
        got = self.splits(failing(), opening([vendor('AUX')]))
        self.assertEqual([(g['decided'], g['sources']) for g in got], [('FAIL', ['evidence/ds/D1.txt'])])

    def test_another_datasheet_is_no_split(self):
        self.assertEqual(self.splits(passing(OTHER), opening([vendor('AUX')])), [])

    def test_a_requirement_document_is_no_datasheet(self):
        clause = dict(LIMIT, source='requirements/用户需求.md')
        self.assertEqual(self.splits(passing(clause), opening([vendor('AUX')], conditions=(clause, CURVE))), [])

    def test_a_margin_on_another_aspect_does_not_decide_the_row(self):
        a = passing()
        a['results']['functions'][0]['calculation']['margin'][0]['aspect'] = '损耗与反向电流'
        self.assertEqual(self.splits(a, opening([vendor('AUX')])), [])

    def test_an_estimate_decides_nothing(self):
        a = passing()
        a['results']['functions'][0]['calculation']['margin'][0]['basis']['kind'] = 'ESTIMATE'
        self.assertEqual(self.splits(a, opening([vendor('AUX')])), [])

    def test_the_markdown_lists_each_split(self):
        text = cr.markdown(cr.compare(passing(), opening([vendor('AUX')])))
        self.assertIn('同一份资料一边开项、一边定结论', text)
        self.assertIn('FN-BIAS/AUX', text)
        self.assertIn('evidence/ds/D1.txt', text)


if __name__ == '__main__':
    unittest.main()

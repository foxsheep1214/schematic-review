"""The comparison names why each exact pair disagrees and counts the strict and loose signals on each side
(consistency proposals of 2026-10-23, item 9).

On R5 most of 169 disagreements came from a few causes found by hand: an open item blocking rows through a
requirement clause instead of a number, NA against "PASS, not applicable", one defect on different rows. The tool now
groups them, so a later run shows whether a change moved agreement for the right reason and whether both sides
merely became looser together.
"""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import compare_reviews as cr
from test_compare_reviews import ASPECT, side


def with_edge(s, via, condition=None):
    fn = s['results']['functions'][0]
    fn['conditions'] = [condition] if condition else []
    fn['open'][0]['decides'][0]['via'] = via
    return s


REQUIREMENT_CLAUSE = {'id': 'r1', 'kind': 'MANDATORY_CLAUSE', 'source': 'requirements/需求文档.md', 'locator': 'REQ-PWR-01',
                      'says': '输出必须在 5 V ± 5%', 'applies': '全负载'}
DATASHEET_LIMIT = {'id': 'c1', 'kind': 'NUMERIC_LIMIT', 'source': 'evidence/ds/U1.txt', 'locator': 'p7 Table 7', 'refs': ['U1'],
                   'says': 'VCC(off) max 8.8 V', 'limit': {'max': 8.8, 'unit': 'V'}, 'regime': '全温'}


class CauseTests(unittest.TestCase):
    def causes(self, a, b):
        return cr.compare(a, b)['strict']['causes']

    def test_an_open_item_through_a_requirement_clause_is_named_so(self):
        a = side('BIAS', ['RUN'], 'PASS')
        b = with_edge(side('BIAS', ['RUN'], 'INSUFFICIENT'), {'condition': 'r1'}, REQUIREMENT_CLAUSE)
        causes = self.causes(a, b)
        self.assertEqual([(c['cause'], c['via']) for c in causes], [('INSUFFICIENT_VS_PASS', 'REQUIREMENT_CLAUSE')])
        self.assertEqual(causes[0]['open_ref'], 'FN-BIAS/AUX')

    def test_an_open_item_through_a_number_is_kept_apart(self):
        a = side('BIAS', ['RUN'], 'PASS')
        b = with_edge(side('BIAS', ['RUN'], 'INSUFFICIENT'), {'condition': 'c1'}, DATASHEET_LIMIT)
        self.assertEqual([c['via'] for c in self.causes(a, b)], ['NUMERIC_LIMIT'])
        b = with_edge(side('BIAS', ['RUN'], 'INSUFFICIENT'), {'claim': 'BIAS-VCCMIN', 'input': 'v_aux'})
        self.assertEqual([c['via'] for c in self.causes(a, b)], ['CALCULATION'])

    def test_na_against_pass_and_a_fail_against_anything_else(self):
        a = side('BIAS', ['RUN'], 'PASS', finding=True)
        b = side('BIAS', ['RUN'], 'PASS', stage_na=True)
        b['results']['checks'][-1].pop('na_reason')
        causes = {c['A']: c['cause'] for c in self.causes(a, b)}
        self.assertEqual(causes, {'DEV-C05.U1': 'FAIL_VS_OTHER', 'REQ-D01.REQ-TEMP': 'NA_VS_PASS'})

    def test_the_cause_table_counts_each_group(self):
        a = side('BIAS', ['RUN'], 'PASS', finding=True)
        b = with_edge(side('BIAS', ['RUN'], 'INSUFFICIENT'), {'condition': 'r1'}, REQUIREMENT_CLAUSE)
        table = cr.compare(a, b)['strict']['cause_counts']
        self.assertEqual(table, [{'cause': 'FAIL_VS_OTHER', 'via': None, 'rows': 1},
                                 {'cause': 'INSUFFICIENT_VS_PASS', 'via': 'REQUIREMENT_CLAUSE', 'rows': 1}])


class SignalTests(unittest.TestCase):
    def signals(self, s):
        return cr.signals(s)

    def test_requirement_clause_edges_and_not_applicable_passes_are_counted(self):
        s = with_edge(side('BIAS', ['RUN'], 'INSUFFICIENT'), {'condition': 'r1'}, REQUIREMENT_CLAUSE)
        next(r for r in s['results']['checks'] if r['id'] == 'DEV-C05.U1')['rationale'] = '按拓扑不适用'
        got = self.signals(s)
        self.assertEqual((got['requirement_clause_edges'], got['not_applicable_passes']), (1, 1))
        s = with_edge(side('BIAS', ['RUN'], 'INSUFFICIENT'), {'condition': 'c1'}, DATASHEET_LIMIT)
        self.assertEqual(self.signals(s)['requirement_clause_edges'], 0)

    def test_decisive_margins_without_corners_unspecified_fails_and_measurement_only_passes(self):
        s = side('BIAS', ['RUN'], 'PASS')
        fn = s['results']['functions'][0]
        fn['calculation'] = {'result': 'x', 'margin': [
            {'value': 0.8, 'unit': 'V', 'against': 'a', 'basis': {'kind': 'GUARANTEED_BOUND'}},
            {'value': 0.1, 'unit': 'V', 'against': 'b', 'basis': {'kind': 'ESTIMATE'}},
            {'value': 0.5, 'unit': 'V', 'against': 'c', 'basis': {'kind': 'GUARANTEED_BOUND', 'corners': [{'input': 'v'}]}}]}
        fn['fails'] = [{'key': 'F', 'outside_specified': {'condition': 'c1'}}]
        s['results']['checks'][0]['rationale'] = '以实测为准'
        got = self.signals(s)
        self.assertEqual((got['decisive_margins'], got['decisive_margins_without_corners'], got['outside_specified_fails'],
                          got['measurement_only_passes']), (2, 1, 1, 1))

    def test_both_sides_are_in_the_report_and_the_markdown(self):
        a = side('BIAS', ['RUN'], 'PASS')
        b = with_edge(side('BIAS', ['RUN'], 'INSUFFICIENT'), {'condition': 'r1'}, REQUIREMENT_CLAUSE)
        report = cr.compare(a, b)
        self.assertEqual(report['signals']['B']['requirement_clause_edges'], 1)
        text = cr.markdown(report)
        self.assertIn('## 差异原因', text)
        self.assertIn('## 过严与过松信号', text)
        self.assertLess(text.index('## 差异原因'), text.index('## 建议配对'))


if __name__ == '__main__':
    unittest.main()

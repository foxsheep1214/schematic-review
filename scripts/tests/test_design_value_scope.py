"""A design value names what the design has not chosen (bounding consistency proposals of 2026-10-23, item 3).

On the R5 acceptance re-review one review opened a design value for a fault clamp the board's own protection chain
sets, while it held the protection threshold open as a vendor datum; the other review computed the clamp and found a
P1. A design value now lists the part parameters the design has not chosen (`undecided[{ref, parameter[, unit]}]`);
a parameter the part's BOM row already states is set by the board and is computed with. A quantity another open item
of the review decides hangs on that item (`depends_on: <key>`), one level deep, and its rows are counted there.
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import render_report
import results_model
from review_functions import function_errors
from test_custom_part_spec import bom_db
from test_review_functions import aux_open, bias_function, with_datum


def design_value(**extra):
    fn = bias_function()
    fn['open'] = [dict(aux_open(), **extra)]
    return fn


def errors(*functions, db=None):
    return function_errors({'functions': list(functions)}, (), db)


def about(found, word):
    return [e for e in found if word in e]


class UndecidedTests(unittest.TestCase):
    def test_a_design_value_names_the_parameter_not_chosen(self):
        self.assertEqual(errors(design_value()), [])
        fn = design_value()
        del fn['open'][0]['undecided']
        self.assertTrue(about(errors(fn), 'undecided'))
        for bad in ([], [{'ref': 'T1'}], [{'parameter': ''}], ['T1 峰值'], [{'ref': '', 'parameter': '匝比'}]):
            self.assertTrue(about(errors(design_value(undecided=bad)), 'undecided'), bad)

    def test_a_parameter_the_bom_row_states_is_set_by_the_board(self):
        found = errors(design_value(undecided=[{'ref': 'T1', 'parameter': 'Lp', 'unit': 'µH'}]), db=bom_db())
        self.assertTrue(about(found, 'T1') and about(found, 'BOM'), found)
        self.assertTrue(about(found, 'depends_on'), found)

    def test_a_parameter_the_bom_does_not_state_stays_undecided(self):
        for entry in ({'ref': 'T1', 'parameter': '辅助绕组峰值', 'unit': 'V'},   # not in the row
                      {'ref': 'T1', 'parameter': 'Lp'},                         # no unit: nothing to match
                      {'ref': 'T9', 'parameter': 'Lp', 'unit': 'µH'},           # not a BOM row
                      {'parameter': 'Lp', 'unit': 'µH'}):                       # no part named
            self.assertEqual(errors(design_value(undecided=[entry]), db=bom_db()), [], entry)

    def test_only_a_design_value_names_undecided_parameters_or_hangs_on_another_item(self):
        fn = with_datum()
        fn['open'][0]['undecided'] = [{'parameter': 'VZ'}]
        self.assertTrue(about(errors(fn), 'DESIGN_VALUE'))
        fn = with_datum()
        fn['open'][0]['depends_on'] = 'AUX-5V-MIN'
        self.assertTrue(about(errors(fn), 'DESIGN_VALUE'))


def hung(target='HV-IV'):
    """A design value of FN-CLAMP that the vendor datum HV-IV of the bias function decides."""
    lead = with_datum()
    clamp = design_value(depends_on=target)
    clamp['id'] = 'FN-CLAMP'
    clamp['calculation']['result'] = '反馈开路时 VRAW 在保护动作前的最高值取决于 HV-IV 的过压窗口'
    del clamp['open'][0]['undecided']
    clamp['open'][0]['key'] = 'CLAMP-MAX'
    return lead, clamp


class DependsOnTests(unittest.TestCase):
    def test_a_quantity_another_item_decides_hangs_on_it(self):
        lead, clamp = hung()
        self.assertEqual(lead['open'][0]['key'], 'HV-IV')
        self.assertEqual(errors(lead, clamp), [])

    def test_it_hangs_on_an_open_item_of_this_review(self):
        for target in ('NO-SUCH-KEY', 'CLAMP-MAX', ''):
            self.assertTrue(about(errors(*hung(target)), 'depends_on'), target)

    def test_one_level_deep(self):
        lead, clamp = hung()
        lead['open'].append(dict(aux_open(), key='SECOND', depends_on='CLAMP-MAX'))
        del lead['open'][1]['undecided']
        found = errors(lead, clamp)
        self.assertTrue(about(found, 'SECOND') and about(found, 'depends_on'), found)


class CountedOnceTests(unittest.TestCase):
    def report(self):
        lead, clamp = hung()
        rows = [{'id': 'PWR-C02.BIAS-RUN.Q2', 'review_result': 'INSUFFICIENT', 'open_ref': 'FN-BIAS/HV-IV'},
                {'id': 'PWR-C11.CLAMP.U1', 'review_result': 'INSUFFICIENT', 'open_ref': 'FN-CLAMP/CLAMP-MAX'}]
        return {'functions': [lead, clamp], 'checks': rows}

    def test_its_rows_are_the_work_item_of_the_item_it_hangs_on(self):
        items = {w['key']: w for w in results_model.derived_work_items(self.report())}
        self.assertNotIn('CLAMP-MAX', items)
        self.assertEqual(items['HV-IV']['check_ids'], ['PWR-C02.BIAS-RUN.Q2', 'PWR-C11.CLAMP.U1'])

    def test_its_rows_carry_the_cause_of_that_item(self):
        report = self.report()
        report['functions'][0]['id'] = 'FN-BIAS'
        rows = {r['id']: r for r in results_model.expand(report)['checks']}
        self.assertEqual(rows['PWR-C11.CLAMP.U1']['gap_cause'], 'EXTERNAL_DATA')

    def test_the_report_counts_its_rows_under_that_item(self):
        report = self.report()
        line = render_report.gap_subclass_counts(report, report['checks'])
        self.assertTrue(line and line[0].endswith('| 0 / 0 / 0 / 2 / 0 / 0 |'), line)


if __name__ == '__main__':
    unittest.main()

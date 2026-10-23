"""A custom part's BOM specification is a design value (consistency proposals of 2026-10-23, item 4).

A parameter the BOM states for a custom part bounds the judgement as a NUMERIC_LIMIT sourced from the BOM row,
and the quoted text must be in that row. A pending drawing lists only the parameters the BOM does not state.
"""
import copy
import unittest

from test_review_functions import bias_function
from test_validate_review import fixture
from review_functions import function_errors

BOM_T1 = {'规格': '定制变压器 Lp=600µH±10% Np:Ns=48:6 漏感≤12µH 加强绝缘'}


def bom_db():
    _, _, db = fixture()
    db = copy.deepcopy(db)
    db['bom'] = {'source': 'BOM.csv', 'parts': {'T1': dict(BOM_T1)}}
    return db


def drawing(missing):
    item = {'key': 'T1-DRAWING', 'kind': 'DELIVERABLE_PENDING', 'deliverable_kind': 'CUSTOM_PART_DRAWING',
            'what': 'T1 的饱和电流没有写在 BOM 里', 'scope': '最低输入满载峰值电流',
            'deliverable': 'T1 磁件规格书', 'owner': '磁件设计', 'assumed': '按 BOM 写的电感量计算',
            'closure': '规格书给出 Isat ≥ 2.5 A',
            'decides': [{'aspect': '变换器电压裕量', 'states': ['STARTUP', 'RUN'],
                         'via': {'claim': 'BIAS-VCCMIN', 'input': 'v_aux_min'}, 'rationale': '峰值电流下电感是否饱和未知'}],
            'severity': {'level': 'P1', 'class': 'REQUIRED_FUNCTION', 'affects': 'T1', 'consequence': '饱和时过流'}}
    if missing is not None:
        item['missing_parameters'] = missing
    fn = bias_function()
    fn['open'] = [item]
    return {'functions': [fn]}


def errors_with(report, db=None):
    return function_errors(report, (), db if db is not None else bom_db())


class MissingParametersTests(unittest.TestCase):
    def test_a_custom_part_drawing_names_the_parameters_the_bom_does_not_state(self):
        self.assertEqual(errors_with(drawing([{'name': 'Isat', 'unit': 'A'}])), [])
        self.assertTrue(any('missing_parameters' in e for e in errors_with(drawing(None))))
        self.assertTrue(any('missing_parameters' in e for e in errors_with(drawing([]))))
        self.assertTrue(any('missing_parameters' in e for e in errors_with(drawing([{'unit': 'A'}]))))

    def test_a_parameter_the_bom_states_is_not_missing(self):
        errors = errors_with(drawing([{'name': 'Lp', 'unit': 'µH'}]))
        self.assertTrue(any('Lp' in e and 'BOM' in e for e in errors), errors)
        errors = errors_with(drawing([{'name': '漏感', 'unit': 'µH'}]))
        self.assertTrue(any('漏感' in e for e in errors), errors)
        # the name without a number in the unit is not a stated value
        self.assertEqual(errors_with(drawing([{'name': 'Isat', 'unit': 'A'}, {'name': '加强绝缘'}])), [])

    def test_a_qualification_has_no_unit_and_is_not_matched(self):
        self.assertEqual(errors_with(drawing([{'name': '绝缘资格认可'}])), [])

    def test_without_a_bom_only_the_shape_is_checked(self):
        _, _, db = fixture()
        self.assertEqual(errors_with(drawing([{'name': 'Lp', 'unit': 'µH'}]), db), [])

    def test_other_deliverable_kinds_need_no_parameter_list(self):
        report = drawing(None)
        report['functions'][0]['open'][0]['deliverable_kind'] = 'FIRMWARE_CAPABILITY'
        self.assertEqual(errors_with(report), [])


class BomConditionTests(unittest.TestCase):
    def condition(self, says, locator='BOM T1 规格列'):
        report = drawing([{'name': 'Isat', 'unit': 'A'}])
        report['functions'][0]['conditions'].append(
            {'id': 'b1', 'kind': 'NUMERIC_LIMIT', 'source': 'BOM.csv', 'locator': locator, 'says': says,
             'limit': {'max': 12, 'unit': 'µH'}, 'regime': '按此规格采购', 'use': '漏感上界'})
        return report

    def test_a_bom_limit_quotes_the_bom_row(self):
        self.assertEqual(errors_with(self.condition('漏感≤12µH')), [])
        self.assertEqual(errors_with(self.condition('漏感 ≤ 12 µH')), [])   # spacing is not content

    def test_the_value_column_is_part_of_the_bom_row(self):
        # read_bom keeps the Value column out of db.bom (it is the part's value in the netlist); a quote of it stands
        db = bom_db()
        db['parts']['T1'] = {'value': '12µH/2A'}
        report = self.condition('12µH/2A')
        self.assertEqual(errors_with(report, db), [])

    def test_text_not_in_the_bom_row_is_refused(self):
        errors = errors_with(self.condition('漏感≤12µH（实测）'))
        self.assertTrue(any('b1' in e and 'BOM' in e for e in errors), errors)

    def test_the_locator_names_a_part_the_bom_lists(self):
        errors = errors_with(self.condition('漏感≤12µH', locator='BOM table 7'))
        self.assertTrue(any('b1' in e and 'BOM' in e for e in errors), errors)


if __name__ == '__main__':
    unittest.main()

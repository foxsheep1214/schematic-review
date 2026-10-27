"""A custom part's BOM specification is a design value (consistency proposals of 2026-10-23, item 4).

A parameter the BOM states for a custom part bounds the judgement as a NUMERIC_LIMIT sourced from the BOM row,
and the quoted text must be in that row. (A pending drawing is no open item since 2026-10-26: what the drawing must
meet is a design constraint handed on.)
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


def drawing():
    """FN-BIAS citing T1's BOM row; the bias function's own gap stays (a vendor datum)."""
    return {'functions': [bias_function()]}


def errors_with(report, db=None):
    return function_errors(report, (), db if db is not None else bom_db())


class BomConditionTests(unittest.TestCase):
    def condition(self, says, locator='BOM T1 规格列'):
        report = drawing()
        report['functions'][0]['conditions'].append(
            {'id': 'b1', 'kind': 'NUMERIC_LIMIT', 'source': 'BOM.csv', 'locator': locator, 'refs': ['T1'], 'says': says,
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

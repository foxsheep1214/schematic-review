"""An undecided design value is judged, not held open (2026-10-26, user: 按甲乙分开改：甲判不合格并给改法，乙判合格并附设计约束).

甲: a value the schematic or BOM should state (a part value, a rating, a part number) and does not is a fail item; its
finding gives the back-calculated value as the fix. 乙: a value another design file owns (a magnetics spec, a firmware
setting, the PCB) enters the margin as a DESIGN_CONSTRAINT condition — the bound SR back-calculated — and the rows
pass on it, handing the constraint on to that file's owner. The DESIGN_VALUE open item is gone (results format 10).
All evidence is synthetic.
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import derive_rows
import validate_review as vr
from render_report import render
from review_functions import function_errors
from test_review_functions import ASPECT, STATES, aux_open, bias_function, guaranteed, ledger

CONSTRAINT = {'id': 'aux-min', 'kind': 'DESIGN_CONSTRAINT', 'source': 'evidence/engineering.md', 'locator': 'claim BIAS-VCCMIN',
              'says': '辅助绕组峰值 ≥ 13.5 V（5 V 空载）', 'limit': {'min': 13.5, 'unit': 'V'},
              'regime': '5 V 空载、−10..105 °C', 'owner': '磁件设计', 'handoff': 0, 'use': '辅助绕组最低峰值取约束下限'}
HANDOFF = {'receivers': ['磁件设计'], 'constraint': 'T1 辅助绕组 5 V 空载最低峰值 ≥ 13.5 V',
           'verification': '磁件规格写明 5 V 空载最低峰值电压且 ≥ 13.5 V'}


def constrained():
    """乙: FN-BIAS with the auxiliary minimum as a design constraint handed to the magnetics design."""
    fn = bias_function('PASS')
    fn['conditions'].append(dict(CONSTRAINT))
    fn['handoffs'] = [dict(HANDOFF)]
    fn['calculation']['margin']['basis'] = guaranteed(
        conditions=['c1', 'c2', 'aux-min'],
        corners=guaranteed()['corners'] + [{'input': 'v_aux_min', 'condition': 'aux-min', 'picked': 'min',
                                            'why': '辅助电压越低 VCC 越低'}])
    return fn


def gated(fn):
    p, r, db = ledger(fn)
    for row in r['checks']:
        if row['id'].startswith('PWR-C02'):   # what derive writes on a row passing on a constraint
            row['handoff'] = dict(HANDOFF, required=True, state='OPEN')
    out = vr.validate_review(p, r, db)
    return p, r, out


class ConstraintTests(unittest.TestCase):
    def test_a_constraint_another_file_owns_passes_the_rows_and_is_handed_on(self):
        p, r, out = gated(constrained())
        self.assertTrue(out['valid'], out['errors'])
        self.assertEqual([(e['condition'], e['owner'], len(e['check_ids'])) for e in out['design_constraints']],
                         [('aux-min', '磁件设计', 3)])
        text = render(p, r, out)
        self.assertIn('有 1 条设计约束由 SR 算出、交给磁件设计，按约束判合格', text)
        self.assertIn('T1 辅助绕组 5 V 空载最低峰值 ≥ 13.5 V', text)

    def test_derive_passes_the_row_and_writes_the_handoff(self):
        planned = {'id': 'PWR-C02.BIAS-RUN.Q2', 'object': {'circuit': 'BIAS', 'ref': 'Q2', 'state': 'RUN'}}
        row, error = derive_rows.derive_row(constrained(), planned, ASPECT, {})
        self.assertIsNone(error)
        self.assertEqual((row['review_result'], row['handoff']),
                         ('PASS', dict(HANDOFF, required=True, state='OPEN')))

    def test_the_constraint_names_its_limit_owner_and_handoff(self):
        for field in ('limit', 'regime', 'owner', 'handoff'):
            fn = constrained()
            del fn['conditions'][-1][field]
            self.assertTrue(any('conditions[aux-min]' in e for e in function_errors({'functions': [fn]})), field)
        fn = constrained(); fn['handoffs'] = []
        self.assertTrue(any('handoff is the index' in e for e in function_errors({'functions': [fn]})))

    def test_a_value_the_schematic_should_state_is_no_constraint(self):
        for owner in ('原理图设计', 'BOM 选型'):
            fn = constrained(); fn['conditions'][-1]['owner'] = owner
            self.assertTrue(any('is a fail item' in e for e in function_errors({'functions': [fn]})), owner)

    def test_a_hand_filled_pass_on_a_constraint_carries_the_handoff(self):
        p, r, db = ledger(constrained())
        out = vr.validate_review(p, r, db)   # ledger() writes the rows by hand with handoff.required false
        self.assertTrue(any('design constraint aux-min' in e and '磁件设计' in e for e in out['errors']), out['errors'])


class NoDesignValueTests(unittest.TestCase):
    def test_a_design_value_open_item_is_refused_with_both_ways_out(self):
        fn = bias_function()
        fn['open'][0] = dict(aux_open(), kind='DESIGN_VALUE', spec='辅助绕组峰值 ≥ 13.5 V', owner='磁件设计')
        errors = function_errors({'functions': [fn]})
        self.assertTrue(any('no open item' in e and 'fail item' in e and 'DESIGN_CONSTRAINT' in e for e in errors), errors)


if __name__ == '__main__':
    unittest.main()

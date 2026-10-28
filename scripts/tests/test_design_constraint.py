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
        for field in ('regime', 'owner', 'handoff'):
            fn = constrained()
            del fn['conditions'][-1][field]
            self.assertTrue(any('conditions[aux-min]' in e for e in function_errors({'functions': [fn]})), field)
        fn = constrained(); fn['conditions'][-1]['limit'] = {'min': 13.5}
        self.assertTrue(any('back-calculated limit' in e for e in function_errors({'functions': [fn]})))
        fn = constrained(); fn['handoffs'] = []
        self.assertTrue(any('handoff is the index' in e for e in function_errors({'functions': [fn]})))

    def test_a_zero_margin_on_a_constraint_alone_is_refused(self):
        # results 13: R8 wrote "余量 0 V 对 光耦 890 V 按隔离设计约束核对" eleven times; the constraint is no margin
        fn = constrained()
        fn['calculation']['margin'].update(value=0, against='光耦 890 V 按隔离设计约束核对')
        fn['calculation']['margin']['basis']['conditions'] = ['aux-min']
        self.assertTrue(any('margin[0]: a margin of 0 whose stress is only a handed-on design constraint' in e
                            for e in function_errors({'functions': [fn]})))
        fn['calculation']['margin']['value'] = 0.8      # a computed margin on the constraint stays
        self.assertFalse(any('handed-on design constraint' in e for e in function_errors({'functions': [fn]})))
        fn = constrained()
        fn['calculation']['margin']['value'] = 0        # zero on a guaranteed input as well is a real zero margin
        self.assertFalse(any('handed-on design constraint' in e for e in function_errors({'functions': [fn]})))

    def test_a_value_the_schematic_should_state_is_no_constraint(self):
        for owner in ('原理图设计', 'BOM 选型'):
            fn = constrained(); fn['conditions'][-1]['owner'] = owner
            self.assertTrue(any('is a fail item' in e for e in function_errors({'functions': [fn]})), owner)

    def test_a_hand_filled_pass_on_a_constraint_carries_the_handoff(self):
        p, r, db = ledger(constrained())
        out = vr.validate_review(p, r, db)   # ledger() writes the rows by hand with handoff.required false
        self.assertTrue(any('design constraint aux-min' in e and '磁件设计' in e for e in out['errors']), out['errors'])


INSULATION = {'id': 't1-insulation', 'kind': 'DESIGN_CONSTRAINT', 'source': 'evidence/engineering.md',
              'locator': 'IEC 62368-1 §5.4 计算', 'says': 'T1 初次级加强绝缘：三重绝缘线次级，爬电 ≥ 6.4 mm，耐压 3000 Vac/60 s',
              'regime': '300 Vrms 工作电压、污染等级 2、海拔 ≤ 2000 m', 'owner': '磁件设计', 'handoff': 0,
              'use': '定制变压器图纸要满足的绝缘结构'}
CLAUSE_HANDOFF = {'receivers': ['磁件设计'], 'constraint': INSULATION['says'],
                  'verification': '磁件规格书写明绝缘结构、爬电距离和耐压试验值且满足约束'}


def clause_constrained():
    """并入乙: what the custom transformer's drawing must meet, as a clause the judgement rests on."""
    fn = bias_function('PASS')
    fn['conditions'].append(dict(INSULATION))
    fn['handoffs'] = [dict(CLAUSE_HANDOFF)]
    fn['judgements'] = [{'aspect': '偏置路径连接', 'conditions': ['c5', 't1-insulation'],
                         'says': 'AUX 绕组在初级侧，按约束的加强绝缘与次级隔开'}]
    return fn


class ClauseConstraintTests(unittest.TestCase):
    """2026-10-26 (user: 并入乙): what another stage owes (a custom part drawing, a firmware capability) is a design
    constraint — a clause when it has no single number — and the row passes on it, handed on."""

    def test_a_clause_constraint_settles_a_judgement_and_is_handed_on(self):
        fn = clause_constrained()
        self.assertEqual(function_errors({'functions': [fn]}), [])
        planned = {'id': 'DEV-D01.T1', 'object': {'ref': 'T1'}}
        row, error = derive_rows.derive_row(fn, planned, '偏置路径连接', {})
        self.assertIsNone(error)
        self.assertEqual((row['review_result'], row['handoff']), ('PASS', dict(CLAUSE_HANDOFF, required=True, state='OPEN')))

    def test_the_clause_alone_settles_the_custom_parts_own_row(self):
        fn = clause_constrained()
        fn['judgements'] = [{'aspect': '器件身份', 'conditions': ['t1-insulation'],
                             'says': 'T1 是定制变压器，身份与绝缘结构按约束由磁件规格书给出'}]
        self.assertEqual(function_errors({'functions': [fn]}), [])

    def test_a_numeric_constraint_is_still_compared_in_a_margin(self):
        fn = clause_constrained()
        fn['conditions'][-1]['limit'] = {'min': 6.4, 'unit': 'mm'}
        self.assertTrue(any('cites a numeric limit' in e for e in function_errors({'functions': [fn]})))

    def test_a_pending_deliverable_is_refused_and_points_at_the_constraint(self):
        fn = bias_function()
        fn['open'][0] = dict(aux_open(), kind='DELIVERABLE_PENDING', deliverable_kind='CUSTOM_PART_DRAWING',
                             deliverable='T1 磁件规格书', owner='磁件设计', assumed='按加强绝缘')
        errors = function_errors({'functions': [fn]})
        self.assertTrue(any('no open item' in e and 'DESIGN_CONSTRAINT' in e and 'clause' in e for e in errors), errors)

    def test_a_constraint_does_not_cap_the_release(self):
        self.assertEqual(vr.release_for([], [], False), 'GO')


class NoDesignValueTests(unittest.TestCase):
    def test_a_design_value_open_item_is_refused_with_both_ways_out(self):
        fn = bias_function()
        fn['open'][0] = dict(aux_open(), kind='DESIGN_VALUE', spec='辅助绕组峰值 ≥ 13.5 V', owner='磁件设计')
        errors = function_errors({'functions': [fn]})
        self.assertTrue(any('no open item' in e and 'fail item' in e and 'DESIGN_CONSTRAINT' in e for e in errors), errors)


if __name__ == '__main__':
    unittest.main()

"""A commodity part's rating beyond the weakest tier is a BOM constraint on a PASS row, not an open item.

On the R5 bench resistors and electrolytic capacitors specified only by value were left open as design values ("the
power rating is not stated"), counted as missing data. Commodity parts are screened for risk: the review writes the
minimum the BOM must state, graded by what the credible wrong pick would do (commodity-floors.md).
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import bom_constraints
import render_report
from checkers.netgraph import NetGraph
from ledger_v3 import validate_review
from render_report import render
import review_functions
from review_functions import row_anchors
from test_decoupling import ledger, mark_pass
from test_passive_stress import board, proposals

CONSTRAINT = {'refs': ['R1'], 'requirement': '额定功率 ≥ 0.09 W', 'basis': 'DEV-C01.R1 计算：44 mW',
              'consequence_class': 'OPTIMIZATION', 'level': 'P3', 'status': 'TO_WRITE'}


class ConstraintTests(unittest.TestCase):
    def gate(self, phase=None, **constraint):
        db, intent = board()
        plan, rows = proposals(db, intent)
        if phase:
            plan['review_phase'] = phase
        report = ledger(plan, db)
        row = next(c for c in report['checks'] if c['id'] == rows['R1']['id'])
        mark_pass(row)
        row['bom_constraint'] = dict(CONSTRAINT, **constraint)
        return plan, report, validate_review(plan, report, db)

    def errors(self, **constraint):
        return [e for e in self.gate(**constraint)[2]['errors'] if 'bom_constraint' in e]

    def test_a_constraint_graded_by_its_consequence_class_is_accepted(self):
        self.assertEqual(self.errors(), [])

    def test_the_level_follows_the_class_and_the_minimum_is_a_number(self):
        self.assertTrue(any('level' in e for e in self.errors(level='P1')))
        self.assertTrue(any('requirement' in e for e in self.errors(requirement='写明额定功率')))
        self.assertTrue(any('hazard_path' in e for e in self.errors(consequence_class='DAMAGE_OR_HAZARD', level='P0')))
        self.assertTrue(any('written_at' in e for e in self.errors(status='WRITTEN')))

    def test_a_constraint_stands_only_on_a_pass_row(self):
        for result, refused in (('PASS', False), ('INSUFFICIENT', True), ('FAIL', True)):
            errors = bom_constraints.constraint_errors('K', {'review_result': result, 'bom_constraint': CONSTRAINT})
            self.assertEqual(any('PASS row' in e for e in errors), refused, result)

    def test_a_constraint_not_yet_in_the_bom_holds_the_freeze(self):
        gate = self.gate(phase='schematic_freeze')[2]
        self.assertTrue(any('BOM_CONSTRAINT_TO_WRITE' in b for b in gate['blockers']))
        gate = self.gate(phase='schematic_freeze', status='WRITTEN', written_at='BOM.csv R1 行')[2]
        self.assertFalse(any('BOM_CONSTRAINT_TO_WRITE' in b for b in gate['blockers']))

    def test_the_report_lists_what_the_bom_must_state(self):
        plan, report, gate = self.gate()
        section = render(plan, report, gate).split('## BOM 要写明的额定与规格')[1].split('\n## ')[0]
        self.assertIn('| R1 | 额定功率 ≥ 0.09 W | DEV-C01.R1 计算：44 mW | 误选件仍在额定内，只缺降额余量（P3） | 待写入 |', section)


class RatingGapTests(unittest.TestCase):
    def refused(self, rule='DEV-C01', ref='R1', kind='DESIGN_VALUE'):
        db, _ = board()
        expected = {rule + '.' + ref: {'rule': rule, 'object': {'ref': ref}}}
        checks = {rule + '.' + ref: {'review_result': 'INSUFFICIENT', 'open_ref': 'FN-X/RATING'}}
        functions = [{'id': 'FN-X', 'open': [{'key': 'RATING', 'kind': kind}]}]
        return bom_constraints.rating_gap_errors(expected, checks, functions, NetGraph(db), row_anchors)

    def test_a_commodity_part_rating_left_open_is_refused(self):
        for kind in ('DESIGN_VALUE', 'VENDOR_DATUM'):
            self.assertTrue(self.refused(kind=kind), kind)

    def test_a_requirement_row_following_the_part_row_does_not_keep_it_open(self):
        db, _ = board()
        expected = {'DEV-C01.R1': {'rule': 'DEV-C01', 'object': {'ref': 'R1'}},
                    'REQ-D01.DERATING.REQ-1': {'rule': 'REQ-D01', 'object': {'requirement_id': 'REQ-1'}}}
        checks = {cid: {'review_result': 'INSUFFICIENT', 'open_ref': 'FN-X/RATING'} for cid in expected}
        functions = [{'id': 'FN-X', 'open': [{'key': 'RATING', 'kind': 'DESIGN_VALUE'}]}]
        self.assertTrue(bom_constraints.rating_gap_errors(expected, checks, functions, NetGraph(db), row_anchors))
        del expected['DEV-C01.R1'], checks['DEV-C01.R1']
        self.assertEqual(bom_constraints.rating_gap_errors(expected, checks, functions, NetGraph(db), row_anchors), [])

    def test_an_ic_or_another_rule_stays_an_open_item(self):
        self.assertEqual(self.refused(ref='U1'), [])
        self.assertEqual(self.refused(rule='PWR-C02'), [])
        self.assertEqual(self.refused(kind='DELIVERABLE_PENDING'), [])

    def test_a_safety_capacitor_is_not_a_commodity_part(self):
        db, _ = board()
        self.assertTrue(bom_constraints.is_commodity(NetGraph(db), 'C1'))
        db['parts']['C1']['value'] = '100nF/X2/275V'
        self.assertFalse(bom_constraints.is_commodity(NetGraph(db), 'C1'))

    def test_the_review_gate_refuses_a_commodity_rating_left_open(self):
        db, intent = board()
        plan, rows = proposals(db, intent)
        report = ledger(plan, db)
        row = next(c for c in report['checks'] if c['id'] == rows['R1']['id'])
        row.update(review_result='INSUFFICIENT', open_ref='FN-X/RATING')
        report['functions'] = [{'id': 'FN-X', 'open': [{'key': 'RATING', 'kind': 'DESIGN_VALUE'}]}]
        checks = {c['id']: c for c in report['checks']}
        errors = review_functions.validate_functions(plan, report, checks, db=db)
        self.assertTrue(any('commodity parts' in e for e in errors), errors)


    def test_a_bom_row_gap_naming_only_commodity_parts_is_refused(self):
        # A gap on the board-wide BOM row naming 27 resistors and capacitors stayed an open item: the part rows were
        # checked, the BOM row was not.
        db, _ = board()
        expected = {'DEV-D04.BOARD': {'rule': 'DEV-D04', 'object': {}}}
        checks = {'DEV-D04.BOARD': {'review_result': 'INSUFFICIENT', 'open_ref': 'FN-X/RATINGS'}}
        for what, refused in (('R1、C1 没有额定电压/功率（X7R）', True), ('U1 与 R1 没写订货码', False), ('BOM 没写额定', False)):
            functions = [{'id': 'FN-X', 'open': [{'key': 'RATINGS', 'kind': 'DESIGN_VALUE', 'what': what}]}]
            with self.subTest(what=what):
                errors = bom_constraints.rating_gap_errors(expected, checks, functions, NetGraph(db), row_anchors)
                self.assertEqual(bool(errors), refused, errors)


class LifeRowTests(unittest.TestCase):
    """A lifetime requirement falls on every electrolytic capacitor: each gets its own DEV-C02 life row."""

    def plan(self, prim='Device:C_Polarized', lifetime=True):
        from plan_review import build_review_plan
        from test_decoupling import rebind
        from test_requirement_bindings import board as req_board
        from test_requirement_source import DOC, source, write
        db, intent = req_board()
        db['parts']['C1']['prim'] = prim
        if lifetime:
            doc = DOC.replace('| REQ-TEMP-01 |', '| REQ-LIFE-9 | 设计寿命 10 年 | 每天充电 8 h |\n| REQ-TEMP-01 |', 1)
            intent['requirement_source'] = source(write(doc))
            intent['requirements'].append({'id': 'REQ-LIFE-9', 'categories': ['LIFETIME'], 'status': 'CONFIRMED',
                                           'interpretation': '设计寿命 10 年',
                                           'parameters': [{'name': 'lifetime', 'unit': '年', 'max': 10}]})
        rebind(db, intent)
        return build_review_plan(db, intent)

    def life_rows(self, plan):
        return [c for c in plan['checks'] if c['rule'] == 'DEV-C02' and c['id'].startswith('DEV-C02.LIFE.')]

    def test_an_electrolytic_capacitor_gets_a_life_row_under_a_lifetime_requirement(self):
        rows = self.life_rows(self.plan())
        self.assertEqual([(r['id'], r['object']['ref']) for r in rows], [('DEV-C02.LIFE.C1', 'C1')])
        self.assertIn('REQ-LIFE-9', rows[0]['criterion'])
        self.assertIn('bom_constraint', rows[0]['criterion'])

    def test_no_lifetime_requirement_or_a_ceramic_capacitor_gets_none(self):
        self.assertEqual(self.life_rows(self.plan(lifetime=False)), [])
        self.assertEqual(self.life_rows(self.plan(prim='Device:C')), [])


if __name__ == '__main__':
    unittest.main()

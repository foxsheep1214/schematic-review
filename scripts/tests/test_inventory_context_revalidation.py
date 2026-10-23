"""A generated row must survive the per-checker revalidation unchanged.

On one board the validator refused rows the planner itself had written: the feedback-open row named an optocoupler
without the optocoupler inventory digest, and the decoupling rating proposal, which reads the passive-stress
pre-judgement and so the declared rail voltages, was rebuilt from a context that did not keep those rails.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plan_review import build_review_plan
from test_checkers_framework import run_validation
from test_optocoupler import opto_board
from test_passive_stress import board


class InventoryContextRevalidationTests(unittest.TestCase):
    def test_feedback_open_row_carries_the_optocoupler_binding(self):
        db = opto_board()
        db['pinname']['U2.1'] = 'FB'
        plan = build_review_plan(db)
        row = next(c for c in plan['checks'] if c['id'].startswith('PRO-C01.FEEDBACK-OPEN'))
        self.assertEqual(row['object']['optocoupler_digest'], plan['optocoupler']['digest'])
        self.assertEqual(run_validation(plan, db)[0], [])

    def test_decoupling_rating_proposal_is_rebuilt_with_the_rails(self):
        db, intent = board()
        group = intent['decoupling']['groups'][0]
        group['requirements'] = [r for r in group['requirements'] if r['kind'] != 'rating']
        plan = build_review_plan(db, intent)
        row = next(c for c in plan['checks'] if c['rule'] == 'PWR-C10')
        self.assertEqual(row['proposal']['result'], 'PASS')
        self.assertEqual(run_validation(plan, db)[0], [])

    def test_a_changed_rail_makes_the_decoupling_inventory_stale(self):
        db, intent = board()
        plan = build_review_plan(db, intent)
        intent['power_rails']['VCC_3V3']['voltage_v']['max'] = 60
        self.assertNotEqual(build_review_plan(db, intent)['decoupling'], plan['decoupling'])


if __name__ == '__main__':
    unittest.main()

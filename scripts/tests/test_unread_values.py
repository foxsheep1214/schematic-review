"""A resistor value the parser cannot read is reported at once, never dropped in silence.

On the R5 bench the resistor values carried a rated power and a word (47R/1%/2W/pulse, 1k5/1%/1W); the parser refused
them, so the pin-current and passive-stress calculations had no resistance, and nothing said why. The rated power is
now read; any value still unreadable is a plan diagnostic (RESISTOR_VALUE_UNREAD, with each part and its value as
written) that the plan command prints, for the reviewer to pass to the user.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from checkers.passive_stress import unread_lines, unread_values
from plan_review import build_review_plan
from test_decoupling import rebind
from test_passive_stress import board


class UnreadValueTests(unittest.TestCase):
    def test_an_unreadable_resistor_value_is_a_plan_diagnostic_with_the_value_as_written(self):
        db, intent = board()
        db['parts']['R1']['value'] = '47R/1%/2W/pulse'
        rebind(db, intent)
        self.assertEqual(unread_values(db), {'R1': '47R/1%/2W/pulse'})
        found = [d for d in build_review_plan(db, intent)['diagnostics'] if d['code'] == 'RESISTOR_VALUE_UNREAD']
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['values'], {'R1': '47R/1%/2W/pulse'})
        lines = unread_lines(build_review_plan(db, intent))
        self.assertIn('R1「47R/1%/2W/pulse」', lines[0])
        self.assertIn('当场告诉用户', lines[1])
        self.assertEqual(unread_lines({'diagnostics': []}), [])

    def test_a_readable_value_an_empty_one_and_a_part_not_fitted_are_not_reported(self):
        db, intent = board()
        db['parts']['R1']['value'] = '1k5/1%/1W'
        rebind(db, intent)
        self.assertEqual(unread_values(db), {})
        plan = build_review_plan(db, intent)
        self.assertFalse([d for d in plan['diagnostics'] if d['code'] == 'RESISTOR_VALUE_UNREAD'])
        db['parts']['R1']['value'] = ''
        self.assertEqual(unread_values(db), {})
        db['parts']['R1'].update(value='47R/pulse', nc=True)
        self.assertEqual(unread_values(db), {})


if __name__ == '__main__':
    unittest.main()

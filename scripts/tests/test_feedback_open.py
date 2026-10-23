"""A converter regulated through an optocoupler gets a fixed single-fault row: the feedback opens.

On one board a reviewer found that with the feedback optocoupler open the controller delivers full power for the whole
OVP detection delay (22.5 ms minimum) and the output rises past its capacitors' rating; the other reviewer, on the same
plan, never asked. Whether that fault is examined no longer depends on the reviewer: the plan asks it.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plan_review import build_review_plan
from test_optocoupler import opto_board


def rows(db):
    return [c for c in build_review_plan(db)['checks'] if c['id'].startswith('PRO-C01.FEEDBACK-OPEN')]


class FeedbackOpenTests(unittest.TestCase):
    def test_an_optocoupler_on_a_controller_feedback_pin_gets_the_row(self):
        db = opto_board()
        db['pinname']['U2.1'] = 'FB'
        found = rows(db)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['object']['node'], 'U2.1')
        self.assertEqual(found[0]['object']['optocoupler'], 'OK1')
        self.assertIn('保护', found[0]['criterion'])

    def test_compensation_pin_names_count_and_a_plain_input_does_not(self):
        for name, expected in (('COMP', 1), ('VFB', 1), ('IN', 0), ('FBK_EN', 0)):
            with self.subTest(name=name):
                db = opto_board()
                db['pinname']['U2.1'] = name
                self.assertEqual(len(rows(db)), expected)


if __name__ == '__main__':
    unittest.main()

"""G2/G3 calibration from a public boost board's first-pass false candidates.

SparkFun Qwiic 5V Boost v10, commit 2150213414cbaf2031fed3081900049d023473f1:
three-contact solder jumpers use A/B/C names and the supply is named 3.3V.
These synthetic fixtures retain those generic conventions, not board identity
or acceptance limits. They check recognition and defect preservation only;
recognising a rail/pull never proves enable voltage, converter capacity or I2C.
"""
import pathlib
import sys
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from checkers import netgraph as ng
from checkers.power_switch import build_inventory as switches
from checkers.power_up import build_inventory as regulators
from electrical_fixtures import bound_intent
from lint import Lint
from test_inductive_load import add


def board():
    db = {'parts': {}, 'nets': {}, 'pin2net': {}, 'pinname': {}, 'pintype': {},
          'pseudo_nets': [], 'ref2page': {}}
    add(db, 'JP1', 'SolderJumper_3_Bridged12',
        [('1', 'A', '5V'), ('2', 'B', 'VCC'), ('3', 'C', '3.3V')])
    add(db, 'U1', 'TEST-BOOST', [('1', 'SW', 'SW_NODE'), ('2', 'GND', 'GND'),
        ('3', 'FB', 'FB_NODE'), ('4', 'SHDN', 'ENABLE'), ('5', 'VIN', '3.3V')])
    add(db, 'R1', '100k', [('1', '1', '3.3V'), ('2', '2', 'ENABLE')])
    return db


class PublicBoostCalibrationTests(unittest.TestCase):
    def test_abc_jumper_is_not_a_bjt_or_a_power_switch(self):
        db = board()
        self.assertEqual(ng.NetGraph(db).kind('JP1'), ng.JUMPER)
        inv = switches(db, bound_intent(db))
        self.assertEqual(inv['states'][0]['switches'], [])
        self.assertFalse(any(f['rule'] == 'DRV-A03' for f in Lint(db).run()))

    def test_decimal_voltage_name_discovers_existing_enable_pull_without_verdict(self):
        db = board()
        for name in ('3.3V', '1.8V', '5V', '3V3', 'VCC_3V3'):
            self.assertTrue(ng.is_rail(name), name)
        for name in ('SDA', '3.3', 'GND'):
            self.assertFalse(ng.is_rail(name), name)
        item = regulators(db)['states'][0]['regulators'][0]
        self.assertEqual(item['enable_source'], 'pulled')
        self.assertEqual(item['enable_evidence'], ['R1'])
        self.assertNotIn('review_result', item)
        self.assertFalse(any(f['rule'] == 'RST-A04' for f in Lint(db).run()))

    def test_real_bce_transistor_with_floating_base_is_still_detected(self):
        db = board()
        add(db, 'Q2', 'UNLISTED-PART', [('1', 'B', 'FLOAT_BASE'),
            ('2', 'C', 'LOAD'), ('3', 'E', 'GND')])
        graph = ng.NetGraph(db)
        self.assertEqual(graph.kind('Q2'), ng.BJT)
        hits = [f for f in Lint(db).run() if f['rule'] == 'DRV-A03']
        self.assertEqual(len(hits), 1)
        self.assertIn('Q2', hits[0]['detail'])
        self.assertNotIn('JP1', hits[0]['detail'])

    def test_removing_enable_pull_preserves_missing_source_candidate(self):
        db = board()
        db['parts']['R1']['nc'] = True
        hits = [f for f in Lint(db).run() if f['rule'] == 'RST-A04']
        self.assertEqual(len(hits), 1)
        self.assertIn('U1.4', hits[0]['detail'])


if __name__ == '__main__':
    unittest.main()

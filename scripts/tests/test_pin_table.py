"""The hand-typed official pin table (intent.devices) gets machine guards: a table declared complete must hold every
pin its package name promises, and an IC table without supply pins is listed, since decoupling groups come from them."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import board_intent
from plan_review import build_review_plan, diagnostic_lines
import test_inductive_load as fixture


def device(package, pins, complete=True):
    return {'mpn': 'X', 'package': package, 'identity_citation': 'BOM row', 'citation': 'ds p1', 'pinout_complete': complete,
            'pins': {str(p): {'name': n, 'role': r} for p, n, r in pins}}


class PackagePinCountTests(unittest.TestCase):
    def test_counted_families_read_the_trailing_number(self):
        for name, count in (('QFN-16', 16), ('MSOP-8 (RM-8)', 8), ('SOT-23-3 (DBZ)', 3), ('SOT23-5', 5), ('TSSOP-20', 20),
                            ('LQFP-48', 48), ('SOIC-8', 8), ('SO-4', 4), ('DFN-10', 10), ('BGA-256', 256), ('TO-220-3', 3),
                            ('WQFN-24', 24), ('PDIP-8', 8)):
            self.assertEqual(board_intent.package_pin_count(name), count, name)

    def test_names_without_a_count_give_none(self):
        for name in ('SOT-23', 'TO-220', 'SOT-223', 'BGA', 'QFN', 'custom', 'TEST', 'Synthetic exact package', '', None, 'DBZ'):
            self.assertIsNone(board_intent.package_pin_count(name), name)


class CompletenessGuardTests(unittest.TestCase):
    def test_missing_package_pins_are_refused_and_named(self):
        errors = board_intent.device_errors({'U1': device('QFN-6', [(1, 'FB', 'other'), (2, 'EN', 'other'), (5, 'VOUT', 'power'), (6, 'GND', 'return')])}, None)
        self.assertEqual([e for e in errors if 'pins 3/4 are not in the table' in e],
                         ['devices: device U1 pinout_complete but package QFN-6 pins 3/4 are not in the table'])

    def test_extra_pins_and_partial_tables_pass(self):
        full = [(i, 'P%d' % i, 'other') for i in range(1, 17)]
        self.assertEqual(board_intent.device_errors({'U1': device('QFN-16', full + [(17, 'EP', 'return')])}, None), [])
        self.assertEqual(board_intent.device_errors({'U1': device('QFN-16', full[:2], complete=False)}, None), [])
        self.assertEqual(board_intent.device_errors({'U1': device('BGA', full[:2])}, None), [])
        self.assertEqual(board_intent.device_errors({'U1': device('SOT-23', [(1, 'A', 'other')])}, None), [])
        self.assertEqual(board_intent.device_errors({'U1': device('SOT-23-3 (DBZ)', [(1, 'IN', 'other'), (2, 'GND', 'return'), (3, 'OUT', 'other')])}, None), [])


class SupplyPinDiagnosticTests(unittest.TestCase):
    def board(self):
        db = {'nets': {}, 'parts': {}, 'pin2net': {}, 'pinname': {}, 'pintype': {}, 'pseudo_nets': [], 'ref2page': {}}
        fixture.add(db, 'U1', 'REF-3', [('1', 'IN', 'VIN'), ('2', 'GND', 'GND'), ('3', 'OUT', 'VREF')])
        fixture.add(db, 'J1', 'CONN-2', [('1', 'A', 'VIN'), ('2', 'B', 'GND')])
        fixture.add(db, 'C1', '1uF', [('1', '1', 'VREF'), ('2', '2', 'GND')])
        return db

    def plan(self, pins, ref='U1'):
        db = self.board()
        intent = {'schema_version': 4, 'input_sha256': board_intent.input_fingerprint(db),
                  'devices': {ref: device('SOT-23-3', pins)}}
        return build_review_plan(db, intent), db, intent

    def test_an_ic_table_without_power_or_return_is_a_printed_diagnostic_not_a_refusal(self):
        plan, db, intent = self.plan([(1, 'IN', 'other'), (2, 'GND', 'other'), (3, 'OUT', 'other')])
        found = [d for d in plan['diagnostics'] if d['code'] == 'DEVICE_PINS_NO_SUPPLY']
        self.assertEqual([(d['ref'], d['roles']) for d in found], [('U1', ['other'])])
        self.assertIn('power、return', found[0]['detail'])
        self.assertTrue(any('U1 的脚表声明抄全却没有' in line for line in diagnostic_lines(plan, db, intent)))

    def test_a_table_with_power_and_return_or_a_connector_is_silent(self):
        plan, _, _ = self.plan([(1, 'IN', 'power'), (2, 'GND', 'return'), (3, 'OUT', 'power')])
        self.assertEqual([d for d in plan['diagnostics'] if d['code'] == 'DEVICE_PINS_NO_SUPPLY'], [])
        db = self.board()
        intent = {'schema_version': 4, 'input_sha256': board_intent.input_fingerprint(db),
                  'devices': {'J1': device('SO-2', [(1, 'A', 'other'), (2, 'B', 'other')])}}
        plan = build_review_plan(db, intent)
        self.assertEqual([d for d in plan['diagnostics'] if d['code'] == 'DEVICE_PINS_NO_SUPPLY'], [])


if __name__ == '__main__':
    unittest.main()

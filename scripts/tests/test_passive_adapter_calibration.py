"""Synthetic calibration: connector exclusions must not hide powered ICs."""
import unittest
from test_decoupling import fixture, add, rebind, state, group
from decoupling import build_decoupling_inventory


class PassiveAdapterCalibrationTests(unittest.TestCase):
    def make_board(self):
        db, intent = fixture(values=())
        add(db, 'J1', 'CONNECTOR-4', [('1', '1', 'GND'), ('2', '2', 'VCC_3V3'),
                                     ('3', '3', 'SDA'), ('4', '4', 'SCL')])
        db['pintype'] = {'J1.1': 'POWER', 'J1.2': 'POWER',
                         'J1.3': 'UNSPEC', 'J1.4': 'UNSPEC'}
        intent['assemblies'][0]['population']['J1'] = True
        rebind(db, intent)
        return db, intent

    def test_power_typed_connector_is_candidate_until_role_is_reviewed(self):
        db, intent = self.make_board()
        inv = build_decoupling_inventory(db, intent)
        self.assertTrue(any(g['ref'] == 'J1' for g in state(inv)['groups']))

    def test_cited_passive_connector_exclusion_preserves_missing_ic_capacitor(self):
        db, intent = self.make_board()
        intent['decoupling']['components']['J1'] = {
            'kind': 'other', 'citation': 'synthetic reviewed four-contact passive connector drawing'}
        inv = build_decoupling_inventory(db, intent)
        self.assertFalse(any(g['ref'] == 'J1' for g in state(inv)['groups']))
        self.assertEqual(group(inv, 'U1')['fitted_count'], 0)
        self.assertIn('no-confirmed-fitted-matching-capacitor', group(inv, 'U1')['observations'])
        self.assertTrue(group(inv, 'U1')['requirements'])

    def test_excluding_connector_does_not_exclude_unknown_three_pin_device(self):
        db, intent = self.make_board()
        intent['decoupling']['components']['J1'] = {
            'kind': 'other', 'citation': 'synthetic reviewed passive connector drawing'}
        add(db, 'MODULE_A', 'UNKNOWN', [('1', 'VDD', 'VCC_3V3'),
                                      ('2', 'GND', 'GND'), ('3', 'IO', 'SDA')])
        rebind(db, intent)
        inv = build_decoupling_inventory(db, intent)
        self.assertIn('MODULE_A', inv['unverified_device_refs'])
        self.assertTrue(any(g['ref'] == 'MODULE_A' for g in state(inv)['groups']))


if __name__ == '__main__':
    unittest.main()

"""System functions and the parts each circuit owns (function-tree design §3.4, step 5).

The board's system functions are made only when their object exists: the power tree (SYS-POWER) when there are
rails, grounds (SYS-GROUND, PWR-T06) when there are two or more ground nets, power-on order and recovery
(SYS-SEQUENCE, RST-T03, once for the board) when two or more rails exist, monitoring (SYS-MONITOR) when the monitoring
checker asks for per-domain coverage, and the controller's pin map (SYS-PINMAP, SIG-D13) unless every IC is verified as a kind that is no controller.
Each has a frame over its rows. Stress, capacitance and precision (DEV-C01/C02/C03) are asked once per circuit over the
parts it owns, and once for the board over the parts no circuit owns.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import catalog
import check_key
from test_interface_rows import plan_for, rows
import test_circuit_candidates as fx


class SystemFunctionTests(unittest.TestCase):
    def setUp(self):
        self.plan = plan_for()
        self.frames = {f['system']: f for f in self.plan['functions'] if f.get('system')}

    def test_power_on_order_is_asked_once_for_the_board_not_per_startup_circuit(self):
        seq = rows(self.plan, 'RST-T03')
        self.assertEqual([c['object']['system'] for c in seq], ['SYS-SEQUENCE'])
        self.assertEqual(seq[0]['owner'], {'kind': 'SYSTEM', 'id': 'SYS-SEQUENCE'})
        self.assertGreaterEqual(len(seq[0]['object']['rails']), 2)
        self.assertNotIn('RST-T03', catalog.CIRCUIT_TYPE_BY_NAME['STARTUP'].subjects)

    def test_each_system_function_with_rows_has_a_frame_over_them(self):
        self.assertEqual(set(self.frames), {'SYS-POWER', 'SYS-GROUND', 'SYS-MONITOR', 'SYS-SEQUENCE'})
        for sid, frame in self.frames.items():
            owned = {c['id'] for c in self.plan['checks'] if c['owner'] == {'kind': 'SYSTEM', 'id': sid}}
            self.assertEqual({m['check_id'] for m in frame['members']}, owned, sid)
            self.assertTrue(frame['question'], sid)
        self.assertEqual(set(self.frames['SYS-GROUND']['objects']['nets']), {'PGND', 'SGND'})
        self.assertIn('VOUT', self.frames['SYS-POWER']['objects']['nets'])
        self.assertEqual(catalog.question_errors(self.plan), [])

    def test_a_board_with_one_ground_has_no_ground_function_and_one_rail_has_no_sequence(self):
        db = {'nets': {}, 'parts': {}, 'pin2net': {}, 'pinname': {}, 'pintype': {}, 'pseudo_nets': [], 'ref2page': {}}
        fx.fixture.add(db, 'U1', 'IC:LDO', [('1', 'VIN', 'LDO_IN'), ('2', 'GND', 'GND'), ('3', 'VOUT', 'V3V3')])
        fx.fixture.add(db, 'C1', 'C:10u', [('1', '1', 'V3V3'), ('2', '2', 'GND')])
        intent, audit = fx.intent_for(db, kinds={'U1': 'regulator'}, rails={})
        from plan_review import build_review_plan
        plan = build_review_plan(db, intent, datasheet_audit=audit)
        self.assertEqual(rows(plan, 'PWR-T06'), [])
        self.assertEqual(rows(plan, 'RST-T03'), [])
        self.assertEqual(rows(plan, 'SIG-D13'), [])   # the only IC is verified as a regulator
        self.assertNotIn('SYS-GROUND', {f.get('system') for f in plan['functions']})

    def test_the_pin_map_is_asked_while_an_ic_could_be_a_controller(self):
        self.assertEqual(rows(self.plan, 'SIG-D13'), [])   # every IC on the synthetic board is a verified non-controller
        db = fx.board()
        fx.fixture.add(db, 'U8', 'IC:LOGIC', [('1', 'IO', 'FLT_DRV'), ('2', 'VDD', 'V3V3'), ('3', 'GND', 'SGND')])
        plan = plan_for(db)
        self.assertEqual([c['owner'] for c in rows(plan, 'SIG-D13')], [{'kind': 'SYSTEM', 'id': 'SYS-PINMAP'}])


class OwnedPartRowTests(unittest.TestCase):
    def setUp(self):
        self.plan = plan_for()

    def by_owner(self, rule):
        return {(c['owner']['kind'], c['owner'].get('id')): c['object']['refs'] for c in rows(self.plan, rule)}

    def test_stress_capacitance_and_precision_are_asked_per_circuit_over_its_own_parts(self):
        owned = {e['id']: set(e['parts']) for e in self.plan['owners']}
        stress = self.by_owner('DEV-C01')
        self.assertEqual(set(stress[('CIRCUIT', 'POWER_CONVERTER-U1')]), owned['POWER_CONVERTER-U1'])
        self.assertNotIn(('CIRCUIT', 'DEBUG-BOARD'), stress)                   # a test point carries no stress
        self.assertNotIn('J1', stress[('CIRCUIT', 'POWER_PROTECTION-J1')])      # a connector's current is DEV-C04
        caps = self.by_owner('DEV-C02')
        self.assertEqual(caps[('CIRCUIT', 'POWER_CONVERTER-U1')], ['C3', 'C4'])
        precision = self.by_owner('DEV-C03')
        self.assertEqual(precision[('CIRCUIT', 'ANALOG-U4')], ['R5', 'R6'])

    def test_parts_no_circuit_owns_are_asked_once_for_the_board(self):
        self.assertEqual(self.by_owner('DEV-C01')[('BOARD', None)], ['R99'])
        self.assertEqual(self.by_owner('DEV-C03')[('BOARD', None)], ['R99'])
        self.assertNotIn(('BOARD', None), self.by_owner('DEV-C02'))

    def test_a_circuit_part_row_is_identified_by_the_circuit_not_its_part_list(self):
        row = next(c for c in rows(self.plan, 'DEV-C02') if c['owner'].get('id') == 'POWER_CONVERTER-U1')
        moved = dict(row, object=dict(row['object'], refs=['C3']))
        self.assertEqual(check_key.key(moved), check_key.key(row))


if __name__ == '__main__':
    unittest.main()

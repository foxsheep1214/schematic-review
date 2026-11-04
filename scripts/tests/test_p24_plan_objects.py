"""p24 (Matrix power and protection R2 first review, 2026-11-04): the plan asked the wrong object and asked of
mechanisms the netlist does not have.

1.7/1.12  a precondition-gated row took the first part the precondition found anywhere: three channels' hot-plug rows
          named J1001 (channel 3's connector), the comparator's sensing chain named U402 (a 3.3 V buck). The object
          is now the circuit's own part when the precondition found one.
1.8       PWR-C23 (switching between two sources) was asked of every eFuse channel: it needs a second source now.
1.9       PRO-C08 (fuses and PPTCs, part by part) was asked of every protection circuit: it needs a fuse or PPTC now.
1.10      ANA-D01 (temperature sensor) was asked of a comparator: it needs a temperature sensor now.
1.11      LTC4367 ("... Protection Controller") was planned PWR-E02 (linear regulator dropout): the title now names
          a load switch, which no dropout row is planned for.
6.3       the candidates read the symbol `Circuit` field (ASG's typical circuit id): a part labelled as another
          circuit's (R203 on 02_Input) is not walked into a circuit candidate (the 13_FaultMain comparator's).
The decision interface (3.4, 3.5) is in test_circuit_decisions.py.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import circuit_candidates as cc
import datasheet_kinds
from plan_circuits import subject_ref
from test_inductive_load import add
from test_subject_requires import asked, empty, not_asked, plan_of
import test_circuit_candidates as fx


def channel_board():
    """Two output channels on one bus: each connector is reachable from the other channel through the bus beads."""
    db = empty()
    for n in ('1', '2'):
        add(db, 'U' + n, 'EFUSE', [('1', 'IN', 'BUS'), ('2', 'OUT', 'OUT' + n), ('3', 'GND', 'GND'), ('4', 'EN', 'EN' + n)])
        add(db, 'J' + n, 'Conn_01x02', [('1', '1', 'OUT' + n), ('2', '2', 'GND')])
        add(db, 'C' + n, '10uF', [('1', '1', 'OUT' + n), ('2', '2', 'GND')])
        add(db, 'FB' + n, 'Ferrite', [('1', '1', 'BUS'), ('2', '2', 'OUT' + n)])
    return db


class ObjectTests(unittest.TestCase):
    def test_the_object_is_the_circuits_own_part(self):
        self.assertEqual(subject_ref(['J1001', 'J901'], [], ['U901', 'J901']), 'J901')
        self.assertEqual(subject_ref(['U402', 'U1305'], [], ['U1305', 'R1301']), 'U1305')
        self.assertEqual(subject_ref(['J1', 'J2'], [], ['U9']), 'J1')            # none of its own: the first found
        self.assertEqual(subject_ref([], ['U7'], ['U8']), 'U7')

    def test_a_channels_hot_plug_row_names_its_own_connector(self):
        plan = plan_of(channel_board(), 'POWER_PROTECTION', ['U2', 'C2', 'J2', 'FB2'])
        rows = asked(plan, 'PWR-C13')
        self.assertTrue(rows)
        self.assertEqual({r['object']['ref'] for r in rows}, {'J2'})
        self.assertIn('J1', rows[0]['requires']['found'])   # the other channel's connector is still reached


class MechanismTests(unittest.TestCase):
    def test_an_efuse_channel_is_not_asked_dual_source_or_fuse_rows(self):
        plan = plan_of(channel_board(), 'POWER_PROTECTION', ['U1', 'C1', 'J1', 'FB1'])
        self.assertEqual(asked(plan, 'PWR-C23'), [])
        self.assertEqual(asked(plan, 'PRO-C08'), [])
        self.assertEqual((not_asked(plan)['PWR-C23'], not_asked(plan)['PRO-C08']), ('SECOND_SOURCE', 'FUSE_PART'))

    def test_two_sources_ored_into_one_rail_are_asked_dual_source(self):
        db = empty()
        add(db, 'D1', 'SS34', [('1', 'K', 'VSYS'), ('2', 'A', 'VIN_USB')])
        add(db, 'D2', 'SS34', [('1', 'K', 'VSYS'), ('2', 'A', 'VIN_DC')])
        add(db, 'U1', 'LDO', [('1', 'VIN', 'VSYS'), ('2', 'VOUT', '+3V3'), ('3', 'GND', 'GND')])
        add(db, 'U2', 'MCU', [('1', 'VDD', 'VIN_USB'), ('2', 'GND', 'GND')])
        add(db, 'U3', 'MCU', [('1', 'VDD', 'VIN_DC'), ('2', 'GND', 'GND')])
        plan = plan_of(db, 'POWER_PROTECTION', ['D1', 'D2'])
        self.assertEqual([r['object']['ref'] for r in asked(plan, 'PWR-C23')], ['D1'])
        one = empty()
        add(one, 'D1', 'SS34', [('1', 'K', 'VSYS'), ('2', 'A', 'VIN_USB')])
        add(one, 'U1', 'LDO', [('1', 'VIN', 'VSYS'), ('2', 'VOUT', '+3V3'), ('3', 'GND', 'GND')])
        self.assertEqual(asked(plan_of(one, 'POWER_PROTECTION', ['D1']), 'PWR-C23'), [])

    def test_a_power_mux_or_a_battery_is_a_second_source(self):
        db = empty()
        add(db, 'U1', 'TPS2121', [('1', 'IN1', 'VIN_A'), ('2', 'IN2', 'VIN_B'), ('3', 'OUT', 'VSYS'), ('4', 'GND', 'GND')])
        self.assertEqual([r['object']['ref'] for r in asked(plan_of(db, 'POWER_PROTECTION', ['U1']), 'PWR-C23')], ['U1'])
        bat = empty()
        add(bat, 'BT1', 'Battery', [('1', '+', 'VBAT'), ('2', '-', 'GND')])
        self.assertEqual([r['object']['ref'] for r in asked(plan_of(bat, 'POWER_PROTECTION', ['BT1']), 'PWR-C23')], ['BT1'])

    def test_a_usb_battery_power_path_is_a_second_source(self):
        # teapot feather-rak3172 POWERPATH: VBUS through D3, +BATT through Q1 whose gate VBUS turns it off
        db = empty()
        add(db, 'D3', 'B5819W', [('1', 'K', 'VSYS'), ('2', 'A', 'VBUS')])
        add(db, 'Q1', 'DMG3415', [('1', 'G', 'VBUS'), ('2', 'S', 'VSYS'), ('3', 'D', '+BATT')])
        self.assertEqual([r['object']['ref'] for r in asked(plan_of(db, 'POWER_PROTECTION', ['D3', 'Q1']), 'PWR-C23')], ['Q1'])
        # a series switch its controller drives is no second source
        sw = empty()
        add(sw, 'Q1', 'AO3401', [('1', 'G', 'DRV'), ('2', 'S', 'VIN'), ('3', 'D', 'VOUT')])
        self.assertEqual(asked(plan_of(sw, 'POWER_PROTECTION', ['Q1']), 'PWR-C23'), [])

    def test_a_fuse_is_asked_the_fuse_row(self):
        db = channel_board()
        add(db, 'F1', 'Fuse 2A', [('1', '1', 'BUS'), ('2', '2', 'BUS_F')])
        self.assertEqual([r['object']['ref'] for r in asked(plan_of(db, 'POWER_PROTECTION', ['U1', 'F1']), 'PRO-C08')], ['F1'])

    def test_only_a_temperature_sensor_is_asked_the_temperature_row(self):
        db = empty()
        add(db, 'U1', 'TLV1704', [('1', 'IN+', 'INP'), ('2', 'IN-', 'INN'), ('3', 'OUT', 'CMP'), ('4', 'VCC', 'V3'),
                                  ('5', 'GND', 'GND')])
        self.assertEqual(not_asked(plan_of(db, 'ANALOG', ['U1']))['ANA-D01'], 'TEMP_SENSOR')
        # a thermistor an IC reads, even when its value is a placeholder name (greenmobi TH1 'MOS_Temp')
        add(db, 'TH1', 'MOS_Temp', [('1', '1', 'INP'), ('2', '2', 'GND')])
        self.assertEqual([r['object']['ref'] for r in asked(plan_of(db, 'ANALOG', ['U1', 'TH1']), 'ANA-D01')], ['TH1'])
        sensor = empty()
        add(sensor, 'U5', 'TMP117', [('1', 'VCC', 'V3'), ('2', 'SDA', 'SDA'), ('3', 'GND', 'GND')])
        self.assertEqual([r['object']['ref'] for r in asked(plan_of(sensor, 'ANALOG', ['U5']), 'ANA-D01')], ['U5'])
        charger = empty()
        add(charger, 'U6', 'CHG', [('1', 'TS', 'TS'), ('2', 'VBAT', 'VBAT'), ('3', 'GND', 'GND')])
        self.assertEqual([r['object']['ref'] for r in asked(plan_of(charger, 'ANALOG', ['U6']), 'ANA-D01')], ['U6'])


class ProtectionControllerTests(unittest.TestCase):
    def test_a_protection_controller_title_names_a_load_switch(self):
        self.assertEqual(datasheet_kinds.cues('Undervoltage and Reverse Supply Protection Controller'), {'load_switch'})
        self.assertEqual(datasheet_kinds.cues('High Voltage Surge Stopper'), {'load_switch'})

    def test_a_load_switch_with_shdn_and_vout_is_planned_no_dropout_row(self):
        db = empty()
        add(db, 'U801', 'LTC4367', [('1', 'VIN', 'BUCK_12V'), ('2', 'UV', 'UV_O'), ('3', 'OV', 'OV_O'), ('4', 'GND', 'GND'),
                                    ('5', '~{SHDN}', 'SHDN_O'), ('6', '~{FAULT}', 'FLT_O'), ('7', 'VOUT', 'V12_P'),
                                    ('8', 'GATE', 'GATE_O')])
        add(db, 'R1', '100k', [('1', '1', 'BUCK_12V'), ('2', '2', 'SHDN_O')])
        generic = plan_of(db, 'POWER_PROTECTION', ['U801', 'R1'], roles={'U801': 'ic'})
        self.assertTrue([c for c in generic['checks'] if c['rule'] == 'PWR-E02'])     # what R2 was asked
        switch = plan_of(db, 'POWER_PROTECTION', ['U801', 'R1'], roles={'U801': 'load_switch'})
        self.assertEqual([c for c in switch['checks'] if c['rule'] == 'PWR-E02'], [])


class CircuitFieldTests(unittest.TestCase):
    def candidates(self, fields):
        db = fx.board()
        for ref, value in fields.items():
            db['parts'][ref].setdefault('fields', {})['Circuit'] = value
        intent, audit = fx.intent_for(db)
        return {c['id']: {m['ref'] for m in c['members']} for c in cc.build(db, intent, audit)['candidates']}

    def test_a_part_labelled_as_another_circuits_is_not_walked_into_a_circuit_candidate(self):
        plain = self.candidates({})
        self.assertIn('R6', plain['ANALOG-U4'])
        labelled = self.candidates({'U4': '05_Sense', 'R6': '02_Flyback', 'U1': '02_Flyback'})
        self.assertNotIn('R6', labelled['ANALOG-U4'])
        # the same label as the core device, or a page with no core device of its own, is walked as before
        self.assertIn('R6', self.candidates({'U4': '05_Sense', 'R6': '05_Sense'})['ANALOG-U4'])
        self.assertIn('R6', self.candidates({'U4': '05_Sense', 'R6': '09_Connectors'})['ANALOG-U4'])

    def test_a_chain_still_runs_between_circuits(self):
        plain = self.candidates({})
        labelled = self.candidates({ref: '04_Start' for ref in ('U1',)} | {ref: '03_Other' for ref in ('R41', 'U5')})
        self.assertEqual(labelled['STARTUP-U1.HV'], plain['STARTUP-U1.HV'])


if __name__ == '__main__':
    unittest.main()

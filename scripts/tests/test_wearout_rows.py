"""Parts that wear out get a fixed life row under a lifetime requirement (consistency proposals of 2026-10-23,
items 6b and 6e).

Two reviews of one board asked life only of electrolytic capacitors, and only one of them asked the optocouplers, one
as a vendor-data item for "the project's CTR decay factor". With a lifetime requirement each part of a wear-out class
on the netlist now gets DEV-C06.<class>.<ref>, asked by the table of the proposals: battery and optocoupler on the
mission profile's time (an LED left the table on 2026-10-28: an indicator's light decay only costs visibility); varistor, fuse, inrush NTC, resettable fuse, relay, connector, switch and memory on a
count (surges, power cycles, trips, actuations, matings, writes) that the mission profile states. A count neither the
requirement nor the profile gives leaves the row NA with that reason, not a gap. The optocoupler row writes the CTR
fraction the chain needs at end of life as a selection constraint; SR invents no decay factor, and the transfer and
level rows no longer count life (OPTO-CTR's ÷2 is the typical-curve factor).
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import catalog
import requirement_bindings as rb
from plan_review import build_review_plan
from test_life_rows import life_board, profile

PARTS = [
    ('U2', 'Isolator:PC817', 'PC817', None, [('1', 'A', 'LED_A'), ('2', 'K', 'GND'), ('3', 'E', 'GND'), ('4', 'C', 'FB')]),
    ('D2', 'Device:LED', 'LED_GREEN', None),
    ('RV1', 'Device:Varistor', 'S14K300', None, [('1', '1', 'AC_L'), ('2', '2', 'AC_N')]),
    ('F1', 'Device:Fuse', 'T3.15A', None, [('1', '1', 'AC_IN'), ('2', '2', 'AC_L')]),
    ('F2', 'Device:Polyfuse', 'MF-R050', None),
    ('TH1', 'Device:Thermistor_NTC', '5R/3A', None, [('1', '1', 'AC_L'), ('2', '2', 'AC_NTC')]),
    ('TH2', 'Device:Thermistor_NTC', '10k', None, [('1', '1', 'NTC_SENSE'), ('2', '2', 'GND')]),
    ('U4', 'MCU', 'MCU', None, [('1', 'VDD', 'VCC_3V3'), ('2', 'NTC', 'NTC_SENSE'), ('3', 'GND', 'GND')]),
    ('K1', 'Relay:G5V-1', 'G5V-1', None, [('1', 'COIL1', 'RLY'), ('2', 'COIL2', 'VCC_3V3')]),
    ('J2', 'Connector:USB_C_Receptacle', 'USB-C', None),
    ('RV2', 'Device:R_Potentiometer', '10k', None, [('1', '1', 'VCC_3V3'), ('2', '2', 'WIPER'), ('3', '3', 'GND')]),
    ('SW1', 'Switch:SW_Push', 'SW_Push', None),
    ('BT1', 'Device:Battery_Cell', 'CR2032', None),
    ('U3', 'Memory_EEPROM:24LC02', '24LC02', None, [('1', 'VCC', 'VCC_3V3'), ('2', 'GND', 'GND'), ('3', 'SDA', 'SDA')]),
]
CLASSES = {'U2': 'OPTO', 'RV1': 'VARISTOR', 'F1': 'FUSE', 'F2': 'PTC', 'TH1': 'INRUSH_NTC', 'K1': 'RELAY',
           'J2': 'CONNECTOR', 'RV2': 'SWITCH', 'SW1': 'SWITCH', 'BT1': 'BATTERY', 'U3': 'MEMORY'}


def plan(events=None, mission=True, lifetime=True):
    mission = profile(events=events) if mission and events else mission
    return build_review_plan(*life_board(mission=mission, parts=PARTS, lifetime=lifetime))


def wearout(p):
    return {c['object']['ref']: c for c in p['checks'] if c['rule'] == 'DEV-C06'}


class CatalogTests(unittest.TestCase):
    def test_the_rule_and_its_classes(self):
        self.assertIn('DEV-C06', catalog.OBJECTIVE_RULES['G4'])
        for aspect in ('LIFETIME_BASIS', 'MISSION_PROFILE'):
            self.assertIn('DEV-C06', catalog.ASPECT_RULES[aspect])
        self.assertEqual(set(CLASSES.values()) | {'BATTERY'}, set(catalog.WEAROUT_CLASSES))
        for name, entry in catalog.WEAROUT_CLASSES.items():
            self.assertTrue(entry.event is None or entry.event in catalog.LIFE_EVENTS, name)
        self.assertIn('DEV-C06', catalog.render_markdown())

    def test_the_optocoupler_transfer_row_asks_no_project_decay_factor(self):
        criterion = catalog.BY_ID['PRO-E01'].criterion
        self.assertNotIn('寿命衰减系数', criterion)
        self.assertIn('DEV-C06', criterion)

    def test_an_opto_ctr_estimate_stands_for_no_lifetime_risk(self):
        # 2026-10-28: end-of-life CTR is asked once, on DEV-C06; the ÷2 is the typical-curve factor
        self.assertNotIn('LIFETIME', catalog.cell_risks('OPTO-CTR'))


class ClassTests(unittest.TestCase):
    def test_each_wearout_part_gets_one_row_of_its_class(self):
        rows = wearout(plan())
        self.assertEqual({ref: r['object']['wearout'] for ref, r in rows.items()}, CLASSES)
        self.assertEqual(rows['TH1']['id'], 'DEV-C06.INRUSH-NTC.TH1')

    def test_a_sensing_ntc_an_ordinary_ic_a_ceramic_capacitor_and_an_led_get_none(self):
        rows = wearout(plan())
        for ref in ('TH2', 'U1', 'U4', 'C1', 'D2'):
            self.assertNotIn(ref, rows)

    def test_no_lifetime_requirement_no_row(self):
        self.assertEqual(wearout(plan(lifetime=False)), {})

    def test_the_optocoupler_row_writes_the_end_of_life_ctr_as_a_constraint(self):
        row = wearout(plan())['U2']
        for piece in ('CTR', '保留比例', 'bom_constraint', '87600 h'):
            self.assertIn(piece, row['criterion'])
        self.assertIn('不自编', row['criterion'])


class CountTests(unittest.TestCase):
    """A count neither the requirement nor the mission profile gives leaves the row NA with that reason."""

    def test_time_classes_are_asked_and_count_classes_wait_for_their_count(self):
        rows = wearout(plan())
        for ref in ('U2', 'BT1'):
            self.assertEqual(rows[ref]['applicability'], 'APPLICABLE', ref)
        for ref in ('RV1', 'F1', 'F2', 'TH1', 'K1', 'J2', 'RV2', 'SW1', 'U3'):
            self.assertEqual(rows[ref]['applicability'], 'NOT_APPLICABLE', ref)
            self.assertEqual(rows[ref]['review_result'], 'NA', ref)
        self.assertIn(catalog.LIFE_EVENTS['mating_cycles'], rows['J2']['criterion'])

    def test_a_count_in_the_profile_asks_the_row(self):
        rows = wearout(plan([{'event': 'power_cycles', 'count': 3650, 'citation': '每天充电 8 h'}]))
        for ref in ('F1', 'TH1'):
            self.assertEqual(rows[ref]['applicability'], 'APPLICABLE', ref)
            self.assertIn('3650', rows[ref]['criterion'])
        self.assertEqual(rows['K1']['applicability'], 'NOT_APPLICABLE')

    def test_a_count_for_named_parts_asks_only_those(self):
        rows = wearout(plan([{'event': 'actuations', 'count': 20000, 'refs': ['SW1'], 'citation': '每天充电 8 h'}]))
        self.assertEqual(rows['SW1']['applicability'], 'APPLICABLE')
        self.assertEqual(rows['RV2']['applicability'], 'NOT_APPLICABLE')
        self.assertEqual(rows['K1']['applicability'], 'NOT_APPLICABLE')

    def test_without_a_profile_every_row_waits_for_it(self):
        rows = wearout(plan(mission=False))
        self.assertEqual(set(rows), set(CLASSES))
        for ref, row in rows.items():
            self.assertEqual((row['applicability'], row['readiness']), ('APPLICABLE', 'WAITING_EVIDENCE'), ref)
            self.assertIn('intent.mission_profile', row['required_inputs'])


class BindingTests(unittest.TestCase):
    def test_the_lifetime_requirement_binds_the_wearout_rows(self):
        p = plan()
        row = next(c for c in p['checks'] if c['rule'] == 'REQ-D01' and c['object']['requirement_id'] == 'REQ-LIFE-9'
                   and c['object']['aspect'] == 'LIFETIME_BASIS')
        self.assertIn('DEV-C06.OPTO.U2', row['bound_checks'])
        self.assertEqual(rb.errors(p), [])


if __name__ == '__main__':
    unittest.main()

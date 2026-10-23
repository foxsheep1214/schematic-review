"""Common single faults get fixed rows on netlist features (consistency proposals of 2026-10-23, item 7).

Two reviews of one board each raised single faults the other never asked: a hard short at the output port, a hot
restart through the inrush thermistor, the power in a clamp resistor, a controller pin driving an optocoupler LED,
an enable passed across an optocoupler. Like the feedback-open row, the plan now asks each one where its feature is
on the netlist, and asks nothing where it is not. A row only asks; it proposes no result.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plan_review import build_review_plan
from test_optocoupler import add, opto_board


def rows(db, prefix):
    return [c for c in build_review_plan(db)['checks'] if c['id'].startswith(prefix)]


def empty():
    return {'nets': {}, 'parts': {}, 'pin2net': {}, 'pinname': {}, 'pintype': {}, 'pseudo_nets': [], 'ref2page': {}}


def port_board(connector=True):
    db = empty()
    add(db, 'U1', 'BUCK', [('1', 'VIN', 'VIN'), ('2', 'SW', 'SW'), ('3', 'GND', 'GND')])
    add(db, 'L1', '10uH', [('1', '1', 'SW'), ('2', '2', 'VOUT')])
    add(db, 'C1', '100uF', [('1', '1', 'VOUT'), ('2', '2', 'GND')])
    add(db, 'Q1', 'NMOS', [('1', 'G', 'GATE'), ('2', 'D', 'VOUT'), ('3', 'S', 'VPORT')])
    if connector:
        add(db, 'J1', 'Connector:Conn_01x02', [('1', '1', 'VPORT'), ('2', '2', 'GND')])
    else:
        add(db, 'U2', 'LOAD', [('1', 'VDD', 'VPORT'), ('2', 'GND', 'GND')])
    return db


def inrush_board(sensor=False):
    db = empty()
    add(db, 'J1', 'Connector:Conn_01x02', [('1', '1', 'AC_L'), ('2', '2', 'AC_N')])
    add(db, 'F1', 'FUSE 2A', [('1', '1', 'AC_L'), ('2', '2', 'L_F')])
    add(db, 'TH1', 'NTC 5R', [('1', '1', 'L_F'), ('2', '2', 'L_NTC')])
    db['parts']['TH1']['prim'] = 'Device:Thermistor_NTC'
    add(db, 'BR1', 'Bridge', [('1', 'AC1', 'L_NTC'), ('2', 'AC2', 'AC_N'), ('3', '+', 'HV'), ('4', '-', 'GND')])
    if sensor:
        add(db, 'U1', 'MCU', [('1', 'ADC', 'L_NTC'), ('2', 'VDD', 'V3'), ('3', 'GND', 'GND')])
    return db


def clamp_board(capacitor=True):
    db = empty()
    add(db, 'T1', 'Transformer', [('1', '1', 'HV'), ('2', '2', 'DRAIN'), ('3', '3', 'SEC'), ('4', '4', 'SEC_RTN')])
    add(db, 'Q1', 'NMOS', [('1', 'G', 'GATE'), ('2', 'D', 'DRAIN'), ('3', 'S', 'GND')])
    add(db, 'D1', 'DIODE', [('1', 'A', 'DRAIN'), ('2', 'K', 'CLAMP')])
    add(db, 'R1', '100k', [('1', '1', 'CLAMP'), ('2', '2', 'HV')])
    if capacitor:
        add(db, 'C1', '2.2nF', [('1', '1', 'CLAMP'), ('2', '2', 'HV')])
    return db


class PortShortTests(unittest.TestCase):
    def test_a_series_switch_between_a_supply_and_a_connector_gets_the_row(self):
        found = rows(port_board(), 'DRV-C02.PORT-SHORT')
        self.assertEqual([(r['object']['ref'], r['object']['connector']) for r in found], [('Q1', 'J1')])
        self.assertIn('SOA', found[0]['criterion'])

    def test_a_switch_feeding_an_on_board_load_does_not(self):
        self.assertEqual(rows(port_board(connector=False), 'DRV-C02.PORT-SHORT'), [])

    def test_an_output_the_trace_cannot_reach_counts_when_declared(self):
        db = port_board()
        del db['parts']['L1']   # e.g. a transformer secondary: no traceable source
        for node in ('L1.1', 'L1.2'):
            net = db['pin2net'].pop(node)
            db['nets'][net].remove(node)
        self.assertEqual(rows(db, 'DRV-C02.PORT-SHORT'), [])
        intent = {'power_rails': {'VOUT': {'voltage_v': {'min': 4.75, 'max': 5.25}, 'citation': 'requirement'}}}
        found = [c for c in build_review_plan(db, intent)['checks'] if c['id'].startswith('DRV-C02.PORT-SHORT')]
        self.assertEqual(len(found), 1)

    def test_a_power_path_switch_between_two_connector_rails_does_not(self):
        db = port_board()
        add(db, 'J2', 'Connector:Conn_01x02', [('1', '1', 'VOUT'), ('2', '2', 'GND')])   # a battery or header rail
        self.assertEqual(rows(db, 'DRV-C02.PORT-SHORT'), [])
        db = port_board()
        add(db, 'U3', 'MCU', [('1', 'VDD', 'VPORT'), ('2', 'GND', 'GND')])   # the far net is a board rail on a header
        self.assertEqual(rows(db, 'DRV-C02.PORT-SHORT'), [])


class InrushThermistorTests(unittest.TestCase):
    def test_an_inrush_thermistor_on_the_input_path_gets_the_row(self):
        found = rows(inrush_board(), 'PWR-C13.NTC-HOT')
        self.assertEqual([r['object']['ref'] for r in found], ['TH1'])
        self.assertIn('I²t', found[0]['criterion'])

    def test_a_sensing_thermistor_read_by_an_ic_does_not(self):
        self.assertEqual(rows(inrush_board(sensor=True), 'PWR-C13.NTC-HOT'), [])


class ClampResistorTests(unittest.TestCase):
    def test_an_rcd_clamp_on_a_switch_node_gets_a_row_for_its_resistor(self):
        found = rows(clamp_board(), 'DRV-C01.RCD')
        self.assertEqual([(r['object']['ref'], r['object']['diode']) for r in found], [('R1', 'D1')])
        self.assertIn('功率', found[0]['criterion'])

    def test_a_diode_and_resistor_without_the_capacitor_is_not_an_rcd_clamp(self):
        self.assertEqual(rows(clamp_board(capacitor=False), 'DRV-C01.RCD'), [])

    def test_a_boost_diode_into_a_bulk_rail_is_not_a_clamp(self):
        db = clamp_board()
        add(db, 'C9', '100uF', [('1', '1', 'CLAMP'), ('2', '2', 'GND')])
        self.assertEqual(rows(db, 'DRV-C01.RCD'), [])


class PinDrivesLedTests(unittest.TestCase):
    def test_an_ic_pin_sinking_an_optocoupler_led_gets_the_row(self):
        found = rows(opto_board(), 'DEV-C05.PIN-LED')
        self.assertEqual([(r['object']['node'], r['object']['led']) for r in found], [('U1.1', 'OK1')])
        self.assertIn('参考电路', found[0]['criterion'])

    def test_a_led_returned_to_ground_is_not_driven_by_a_ground_pin(self):
        db = opto_board()
        add(db, 'D1', 'Device:LED', [('1', 'K', 'GND'), ('2', 'A', 'LED_B')])
        add(db, 'U3', 'GAUGE', [('1', 'GND', 'GND'), ('2', 'CELL', 'GND')])
        self.assertEqual([r['object']['led'] for r in rows(db, 'DEV-C05.PIN-LED')], ['OK1'])

    def test_a_led_driven_through_a_transistor_does_not(self):
        db = opto_board()
        add(db, 'Q1', 'NMOS', [('1', 'G', 'DRV_G'), ('2', 'D', 'OPTO_DRV'), ('3', 'S', 'GND')])
        db['nets']['OPTO_DRV'].remove('U1.1')
        db['pin2net']['U1.1'] = 'DRV_G'
        db['nets']['DRV_G'].append('U1.1')
        self.assertEqual(rows(db, 'DEV-C05.PIN-LED'), [])


class EnableAcrossOptocouplerTests(unittest.TestCase):
    def test_an_optocoupler_output_on_an_enable_pin_gets_the_row(self):
        db = opto_board()
        db['pinname']['U2.1'] = 'EN'
        found = rows(db, 'SIG-C09.ENABLE-LINK')
        self.assertEqual([(r['object']['node'], r['object']['optocoupler']) for r in found], [('U2.1', 'OK1')])
        self.assertIn('掉电', found[0]['criterion'])

    def test_a_disable_pin_counts(self):
        for name, expected in (('DIS', 1), ('PFC_DIS', 1), ('STBY', 1), ('DISCHARGE', 0), ('FAULT', 0)):
            with self.subTest(name=name):
                db = opto_board()
                db['pinname']['U2.1'] = name
                self.assertEqual(len(rows(db, 'SIG-C09.ENABLE-LINK')), expected)

    def test_a_plain_input_does_not(self):
        self.assertEqual(rows(opto_board(), 'SIG-C09.ENABLE-LINK'), [])


if __name__ == '__main__':
    unittest.main()

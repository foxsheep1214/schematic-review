"""物料与引脚层面的自动扫描：只按网表、BOM 值和引脚名判别，输出仍是疑似清单。"""
import pathlib
import sys
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import board_scans
from lint import Lint
from plan_review import COLD_RULE_INDEXES, build_review_plan


def board(parts, nets, pinname=None, pintype=None, **extra):
    db = {'parts': {ref: dict({'value': value, 'part': value, 'prim': value, 'nc': False})
                    for ref, value in parts.items()},
          'nets': nets, 'pinname': pinname or {}, 'pintype': pintype or {},
          'ref2page': {}, 'pseudo_nets': []}
    db['pin2net'] = {node: net for net, nodes in nets.items() for node in nodes}
    db.update(extra)
    return db


def scans(db, rule=None):
    lint = Lint(db)
    lint.run()
    return [f for f in lint.F if rule is None or f['rule'] == rule]


def subjects(hits):
    """每条命中的定位对象：detail 以“位号/节点: 说明”开头。"""
    return [hit['detail'].split(':')[0].split(' ')[0] for hit in hits]


class CapacitorTest(unittest.TestCase):
    def test_rating_below_the_rail_name_is_a_candidate(self):
        db = board({'C1': '10uF/16V', 'C2': '100nF/50V', 'C3': '1uF'},
                   {'VCC_24V': ['C1.1', 'C2.1', 'C3.1'], 'GND': ['C1.2', 'C2.2', 'C3.2']})
        hits = scans(db, 'DEV-A01')
        self.assertEqual(subjects(hits), ['C1'])
        self.assertEqual(hits[0]['kind'], 'CANDIDATE')
        self.assertIn('耐压 16V < VCC_24V 推断 24V', hits[0]['detail'])

    def test_unfitted_and_unnamed_rails_are_not_reported(self):
        db = board({'C1': '10uF/16V'}, {'VCC_24V': ['C1.1'], 'GND': ['C1.2']})
        db['parts']['C1']['nc'] = True
        self.assertEqual(scans(db, 'DEV-A01'), [])
        db = board({'C1': '10uF/16V'}, {'ANALOG_IN': ['C1.1'], 'GND': ['C1.2']})
        self.assertEqual(scans(db, 'DEV-A01'), [])

    def test_reversed_polarity_marking_is_a_finding(self):
        db = board({'C1': '100uF/35V'}, {'GND': ['C1.1'], 'VCC_24V': ['C1.2']},
                   pinname={'C1.1': '+', 'C1.2': '-'})
        hits = scans(db, 'DEV-A02')
        self.assertEqual([f['kind'] for f in hits], ['FINDING'])
        correct = board({'C1': '100uF/35V'}, {'VCC_24V': ['C1.1'], 'GND': ['C1.2']},
                        pinname={'C1.1': '+', 'C1.2': '-'})
        self.assertEqual(scans(correct, 'DEV-A02'), [])

    def test_kicad_power_symbol_names_count_as_rails(self):
        db = board({'C1': '100uF/16V'}, {'GND': ['C1.1'], '/+5V': ['C1.2']},
                   pinname={'C1.1': '+', 'C1.2': '-'})
        self.assertEqual(subjects(scans(db, 'DEV-A02')), ['C1'])

    def test_unmarked_capacitor_stays_for_visual_review(self):
        db = board({'C1': '100uF/35V'}, {'GND': ['C1.1'], 'VCC_24V': ['C1.2']},
                   pinname={'C1.1': '1', 'C1.2': '2'})
        self.assertEqual(scans(db, 'DEV-A02'), [])


class LedTest(unittest.TestCase):
    def test_led_directly_across_rail_and_ground_is_a_finding(self):
        db = board({'D1': 'LED-RED', 'R1': '1K'},
                   {'VCC_3V3': ['D1.1'], 'GND': ['D1.2', 'R1.2'], 'NET1': ['R1.1']})
        self.assertEqual(subjects(scans(db, 'DEV-A03')), ['D1'])

    def test_led_across_kicad_power_symbol_and_ground(self):
        db = board({'D1': 'LED-RED'}, {'+3V3': ['D1.1'], 'GND': ['D1.2']})
        self.assertEqual(subjects(scans(db, 'DEV-A03')), ['D1'])

    def test_series_resistor_or_driver_net_is_not_reported(self):
        db = board({'D1': 'LED-RED', 'R1': '1K'},
                   {'VCC_3V3': ['R1.1'], 'LED_A': ['R1.2', 'D1.1'], 'GND': ['D1.2']})
        self.assertEqual(scans(db, 'DEV-A03'), [])


class I2cPullupTest(unittest.TestCase):
    def bus(self, extra_parts=None, extra_nets=None):
        parts = {'U1': 'SENSOR', 'J1': 'CONN'}
        parts.update(extra_parts or {})
        nets = {'SDA': ['U1.1', 'J1.1'], 'SCL': ['U1.2', 'J1.2'], 'GND': ['U1.3', 'J1.3'], 'VCC': ['U1.4', 'J1.4']}
        for net, nodes in (extra_nets or {}).items():
            nets.setdefault(net, []).extend(nodes)
        return board(parts, nets)

    def test_bus_line_without_any_pullup_is_a_candidate(self):
        hits = scans(self.bus(), 'SIG-A03')
        self.assertEqual(sorted(subjects(hits)), ['SCL', 'SDA'])
        self.assertEqual({f['kind'] for f in hits}, {'CANDIDATE'})

    def test_pullups_series_resistors_and_jumper_fed_pullups_are_not_reported(self):
        pulled = self.bus({'R1': '4K7', 'R2': '4K7'},
                          {'SDA': ['R1.1'], 'SCL': ['R2.1'], 'VCC': ['R1.2', 'R2.2']})
        self.assertEqual(scans(pulled, 'SIG-A03'), [])
        jumper = self.bus({'R1': '4K7', 'R2': '4K7'},
                          {'SDA': ['R1.1'], 'SCL': ['R2.1'], 'PULL': ['R1.2', 'R2.2']})
        self.assertEqual(scans(jumper, 'SIG-A03'), [])

    def test_single_ic_with_test_points_only_is_fixture_access(self):
        # 真实反例：配置 I2C 脚只接一颗控制器和测试点，对端与上拉在生产夹具。
        db = board({'U1': 'PD-CTRL', 'TP1': 'TESTPOINT', 'TP2': 'TESTPOINT'},
                   {'CFG_SDA': ['U1.1', 'TP1.1'], 'CFG_SCL': ['U1.2', 'TP2.1'], 'GND': ['U1.3']})
        hits = scans(db, 'SIG-A03')
        self.assertEqual({f['kind'] for f in hits}, {'INFO'})
        self.assertIn('夹具', hits[0]['detail'])

    def test_kicad_library_test_point_counts_as_a_test_point(self):
        # Connector:TestPoint 不能因库名空间被当作连接器。
        db = board({'U1': 'PD-CTRL', 'X1': 'Connector:TestPoint'},
                   {'CFG_SDA': ['U1.1', 'X1.1'], 'GND': ['U1.3']})
        self.assertEqual({f['kind'] for f in scans(db, 'SIG-A03')}, {'INFO'})

    def test_resistor_to_ground_is_not_a_pullup(self):
        db = self.bus({'R1': '10K'}, {'SDA': ['R1.1'], 'GND': ['R1.2']})
        self.assertEqual(subjects(scans(db, 'SIG-A03')), ['SCL', 'SDA'])


class I2cPullupWindowTest(unittest.TestCase):
    def bus(self, rail='VCC_3V3', **pulls):
        nets = {'SDA': ['U1.3', 'U2.3'], 'SCL': ['U1.4', 'U2.4'], rail: ['U1.1', 'U2.1'], 'GND': ['U1.2', 'U2.2']}
        for ref in pulls:
            nets['SDA'].append(ref + '.1')
            nets[rail].append(ref + '.2')
        return board(dict({'U1': 'MCU', 'U2': 'SENSOR'}, **pulls), nets,
                     {'U1.3': 'SDA', 'U2.3': 'SDA', 'U1.4': 'SCL', 'U2.4': 'SCL'})

    def test_a_typical_pullup_passes(self):
        self.assertEqual(scans(self.bus(R1='4k7'), 'SIG-A04'), [])

    def test_ten_megaohm_is_too_weak_for_any_mode(self):
        hits = scans(self.bus(R1='10Meg'), 'SIG-A04')
        self.assertEqual([hit['kind'] for hit in hits], ['CANDIDATE'])
        self.assertIn('G04-017', hits[0]['detail'])

    def test_upper_bound_is_the_widest_window(self):
        self.assertEqual(scans(self.bus(R1='100k'), 'SIG-A04'), [])
        self.assertEqual(len(scans(self.bus(R1='120k'), 'SIG-A04')), 1)

    def test_one_ohm_cannot_be_pulled_low(self):
        hits = scans(self.bus(R1='1R'), 'SIG-A04')
        self.assertEqual(len(hits), 1)
        self.assertIn('G04-018', hits[0]['detail'])

    def test_lower_bound_scales_with_the_rail(self):
        self.assertEqual(scans(self.bus(R1='150'), 'SIG-A04'), [])              # (3.3-0.4)/20mA = 145
        self.assertEqual(len(scans(self.bus(R1='140'), 'SIG-A04')), 1)
        self.assertEqual(len(scans(self.bus(rail='VCC_5V', R1='220'), 'SIG-A04')), 1)   # 230

    def test_parallel_pullups_are_combined(self):
        self.assertEqual(scans(self.bus(R1='10Meg', R2='4k7'), 'SIG-A04'), [])  # strong one sets the bus
        self.assertEqual(len(scans(self.bus(R1='270', R2='270'), 'SIG-A04')), 1)  # 135 < 145

    def test_unknown_rail_voltage_uses_the_lowest_common_bus(self):
        self.assertEqual(scans(self.bus(rail='VCC', R1='100'), 'SIG-A04'), [])  # (1.8-0.4)/20mA = 70
        self.assertEqual(len(scans(self.bus(rail='VCC', R1='47'), 'SIG-A04')), 1)

    def test_a_series_resistor_is_not_a_pullup(self):
        db = board({'U1': 'MCU', 'U2': 'S', 'R1': '1R', 'R2': '4k7'},
                   {'SDA': ['U1.3', 'R1.1', 'R2.1'], 'SDA_S': ['U2.3', 'R1.2'], 'VCC_3V3': ['R2.2', 'U1.1', 'U2.1'],
                    'GND': ['U1.2', 'U2.2']})
        self.assertEqual(scans(db, 'SIG-A04'), [])

    def test_pullup_reached_through_a_jumper_counts(self):
        db = board({'U1': 'MCU', 'U2': 'S', 'R1': '10Meg', 'JP1': 'SolderJumper'},
                   {'SDA': ['U1.3', 'U2.3', 'R1.1'], 'PU': ['R1.2', 'JP1.1'], 'VCC_3V3': ['JP1.2', 'U1.1', 'U2.1'],
                    'GND': ['U1.2', 'U2.2']})
        self.assertEqual(len(scans(db, 'SIG-A04')), 1)

    def test_a_resistor_to_a_plain_signal_is_not_judged(self):
        db = board({'U1': 'MCU', 'U2': 'S', 'R1': '10Meg'},
                   {'SDA': ['U1.3', 'U2.3', 'R1.1'], 'SENSE': ['R1.2', 'U2.5'], 'GND': ['U1.2', 'U2.2']})
        self.assertEqual(scans(db, 'SIG-A04'), [])

    def test_an_unreadable_value_stops_the_judgement(self):
        self.assertEqual(scans(self.bus(R1='10Meg', R2='fixme'), 'SIG-A04'), [])

    def test_low_value_pullup_behind_a_jumper_is_a_pullup_for_sig_a03(self):
        db = board({'U1': 'MCU', 'U2': 'S', 'R1': '1k', 'JP1': 'SolderJumper'},
                   {'SDA': ['U1.3', 'U2.3', 'R1.1'], 'PU': ['R1.2', 'JP1.1'], 'VCC_3V3': ['JP1.2', 'U1.1', 'U2.1'],
                    'GND': ['U1.2', 'U2.2']})
        self.assertEqual(scans(db, 'SIG-A03'), [])


class CanBusShortTest(unittest.TestCase):
    NAMES = {'U1.3': 'CANH', 'U1.4': 'CANL'}

    def test_h_and_l_on_one_net_is_a_finding(self):
        db = board({'U1': 'TCAN1042'}, {'CANH': ['U1.3', 'U1.4']}, self.NAMES)
        hits = scans(db, 'SIG-A06')
        self.assertEqual([hit['kind'] for hit in hits], ['FINDING'])
        self.assertIn('U1', hits[0]['detail'])

    def test_separate_nets_pass(self):
        self.assertEqual(scans(board({'U1': 'TCAN1042'}, {'CANH': ['U1.3'], 'CANL': ['U1.4']}, self.NAMES), 'SIG-A06'), [])

    def across(self, value):
        return board({'U1': 'TCAN1042', 'R1': value}, {'CANH': ['U1.3', 'R1.1'], 'CANL': ['U1.4', 'R1.2']}, self.NAMES)

    def test_zero_ohm_across_the_bus_is_a_short(self):
        self.assertEqual(len(scans(self.across('0R'), 'SIG-A06')), 1)
        self.assertEqual(len(scans(self.across('1R'), 'SIG-A06')), 1)

    def test_a_termination_resistor_is_not_a_short(self):
        self.assertEqual(scans(self.across('120R'), 'SIG-A06'), [])
        self.assertEqual(scans(self.across('fixme'), 'SIG-A06'), [])

    def test_alternate_pin_spelling(self):
        db = board({'U1': 'X'}, {'BUS': ['U1.3', 'U1.4']}, {'U1.3': 'CAN_H', 'U1.4': 'CAN_L'})
        self.assertEqual(len(scans(db, 'SIG-A06')), 1)

    def test_an_unfitted_transceiver_is_not_reported(self):
        db = board({'U1': 'TCAN1042'}, {'CANH': ['U1.3', 'U1.4']}, self.NAMES)
        db['parts']['U1']['nc'] = True
        self.assertEqual(scans(db, 'SIG-A06'), [])


class IsolatorGroundBridgeTest(unittest.TestCase):
    NAMES = {'U1.2': 'GND1', 'U1.7': 'GND2'}

    def isolator(self, value='ADuM1201', parts=None, nets=None):
        all_nets = {'GND': ['U1.2'], 'GND_ISO': ['U1.7']}
        all_nets.update(nets or {})
        return board(dict({'U1': value}, **(parts or {})), all_nets, dict(self.NAMES))

    def test_grounds_on_one_net_is_a_candidate(self):
        db = board({'U1': 'ADuM1201'}, {'GND': ['U1.2', 'U1.7']}, dict(self.NAMES))
        hits = scans(db, 'PRO-A05')
        self.assertEqual([hit['kind'] for hit in hits], ['CANDIDATE'])
        self.assertIn('U1', hits[0]['detail'])

    def test_separate_grounds_pass(self):
        self.assertEqual(scans(self.isolator(), 'PRO-A05'), [])

    def bridge(self, value):
        return self.isolator(parts={'R1': value}, nets={'GND': ['U1.2', 'R1.1'], 'GND_ISO': ['U1.7', 'R1.2']})

    def test_a_zero_ohm_link_or_ferrite_bridges(self):
        self.assertEqual(len(scans(self.bridge('0R'), 'PRO-A05')), 1)
        db = self.isolator(parts={'FB1': 'BLM18'}, nets={'GND': ['U1.2', 'FB1.1'], 'GND_ISO': ['U1.7', 'FB1.2']})
        self.assertEqual(len(scans(db, 'PRO-A05')), 1)

    def test_a_bleed_resistor_or_y_capacitor_is_left_to_the_barrier_rules(self):
        self.assertEqual(scans(self.bridge('1M'), 'PRO-A05'), [])
        self.assertEqual(scans(self.bridge('fixme'), 'PRO-A05'), [])
        db = self.isolator(parts={'CY1': '1nF'}, nets={'GND': ['U1.2', 'CY1.1'], 'GND_ISO': ['U1.7', 'CY1.2']})
        self.assertEqual(scans(db, 'PRO-A05'), [])

    def test_a_multi_ground_ic_that_is_not_an_isolator_is_not_judged(self):
        db = board({'U1': 'STM32F4'}, {'GND': ['U1.2', 'U1.7']}, dict(self.NAMES))
        self.assertEqual(scans(db, 'PRO-A05'), [])

    def test_a_verified_isolator_role_is_enough(self):
        db = board({'U1': 'XYZ123'}, {'GND': ['U1.2', 'U1.7']}, dict(self.NAMES),
                   device_kinds={'U1': {'kind': 'isolator', 'basis': 'datasheet'}})
        self.assertEqual(len(scans(db, 'PRO-A05')), 1)

    def test_an_isolator_with_one_ground_name_is_not_judged(self):
        db = board({'U1': 'ADuM1201'}, {'GND': ['U1.2', 'U1.7']}, {'U1.2': 'GND', 'U1.7': 'GND'})
        self.assertEqual(scans(db, 'PRO-A05'), [])


class CrystalLoadTest(unittest.TestCase):
    def crystal(self, c1='18pF', c2='18pF', ref='Y1'):
        return board({ref: '16MHz', 'C1': c1, 'C2': c2, 'U1': 'MCU'},
                     {'XI': [ref + '.1', 'C1.1', 'U1.3'], 'XO': [ref + '.2', 'C2.1', 'U1.4'], 'GND': ['C1.2', 'C2.2', 'U1.2']},
                     {'U1.3': 'XIN', 'U1.4': 'XOUT'})

    def test_typical_load_passes(self):
        self.assertEqual(scans(self.crystal(), 'CLK-A01'), [])

    def test_one_microfarad_is_a_candidate(self):
        hits = scans(self.crystal('1uF', '1uF'), 'CLK-A01')
        self.assertEqual([hit['kind'] for hit in hits], ['CANDIDATE'])
        self.assertIn('Y1', hits[0]['detail'])

    def test_the_bound_is_on_the_series_equivalent(self):
        self.assertEqual(scans(self.crystal('180pF', '180pF'), 'CLK-A01'), [])   # 90 pF
        self.assertEqual(len(scans(self.crystal('220pF', '220pF'), 'CLK-A01')), 1)   # 110 pF
        self.assertEqual(scans(self.crystal('1uF', '18pF'), 'CLK-A01'), [])      # about 18 pF

    def test_load_on_one_side_only_or_unreadable_is_not_judged(self):
        db = self.crystal('1uF', '1uF')
        db['parts']['C2']['nc'] = True
        self.assertEqual(scans(db, 'CLK-A01'), [])
        self.assertEqual(scans(self.crystal('1uF', '105'), 'CLK-A01'), [])

    def test_an_active_oscillator_decoupling_capacitor_is_not_a_load(self):
        db = board({'Y1': 'Oscillator', 'C1': '1uF', 'C2': '1uF'},
                   {'VCC_3V3': ['Y1.1', 'C1.1'], 'CLK': ['Y1.2', 'C2.1'], 'GND': ['C1.2', 'C2.2']})
        self.assertEqual(scans(db, 'CLK-A01'), [])


class CrystalSharedTest(unittest.TestCase):
    def shared(self, u2=('XIN', 'XOUT'), u2_value='MCU'):
        return board({'Y1': '16MHz', 'U1': 'MCU', 'U2': u2_value},
                     {'XI': ['Y1.1', 'U1.3', 'U2.3'], 'XO': ['Y1.2', 'U1.4', 'U2.4'], 'GND': ['U1.2', 'U2.2']},
                     {'U1.3': 'XIN', 'U1.4': 'XOUT', 'U2.3': u2[0], 'U2.4': u2[1]})

    def test_two_oscillators_on_one_crystal_is_a_finding(self):
        hits = scans(self.shared(), 'CLK-A02')
        self.assertEqual([hit['kind'] for hit in hits], ['FINDING'])
        self.assertIn('U1,U2', hits[0]['detail'])

    def test_one_oscillator_passes(self):
        db = board({'Y1': '16MHz', 'U1': 'MCU'}, {'XI': ['Y1.1', 'U1.3'], 'XO': ['Y1.2', 'U1.4']},
                   {'U1.3': 'XIN', 'U1.4': 'XOUT'})
        self.assertEqual(scans(db, 'CLK-A02'), [])

    def test_a_clock_input_on_one_end_is_not_a_second_oscillator(self):
        db = board({'Y1': '16MHz', 'U1': 'MCU', 'U2': 'MCU'},
                   {'XI': ['Y1.1', 'U1.3'], 'XO': ['Y1.2', 'U1.4', 'U2.3']},
                   {'U1.3': 'XIN', 'U1.4': 'XOUT', 'U2.3': 'XIN'})
        self.assertEqual(scans(db, 'CLK-A02'), [])

    def test_ordinary_pins_on_the_crystal_nets_are_not_oscillator_pins(self):
        self.assertEqual(scans(self.shared(u2=('PA0', 'PA1')), 'CLK-A02'), [])

    def test_pin_name_spellings(self):
        for names in (('XTAL1', 'XTAL2'), ('XI', 'XO'), ('OSC_IN', 'OSC_OUT'), ('PF0-OSC_IN', 'PF1-OSC_OUT'), ('OSC1', 'OSC2')):
            self.assertEqual(len(scans(self.shared(u2=names), 'CLK-A02')), 1, names)

    def test_an_unfitted_second_ic_does_not_count(self):
        db = self.shared()
        db['parts']['U2']['nc'] = True
        self.assertEqual(scans(db, 'CLK-A02'), [])


class UsbVbusBulkTest(unittest.TestCase):
    def vbus(self, net='VBUS', **caps):
        return board(dict({'J1': 'USB_C'}, **caps),
                     {net: ['J1.1'] + [ref + '.1' for ref in caps], 'GND': ['J1.2'] + [ref + '.2' for ref in caps]},
                     {'J1.1': 'VBUS', 'J1.2': 'GND'})

    def test_direct_bulk_over_100uf_is_a_candidate_with_the_sum(self):
        hits = scans(self.vbus(C1='220uF'), 'SIG-A05')
        self.assertEqual([hit['kind'] for hit in hits], ['CANDIDATE'])
        self.assertIn('220', hits[0]['detail'])

    def test_capacitors_add_up_on_the_net(self):
        self.assertEqual(len(scans(self.vbus(C1='47uF', C2='47uF', C3='10uF'), 'SIG-A05')), 1)
        self.assertEqual(scans(self.vbus(C1='47uF', C2='47uF'), 'SIG-A05'), [])

    def test_exactly_100uf_passes(self):
        self.assertEqual(scans(self.vbus(C1='100uF'), 'SIG-A05'), [])

    def test_a_net_behind_a_limiter_is_not_summed(self):
        self.assertEqual(scans(self.vbus('VBUS_SW', C1='220uF'), 'SIG-A05'), [])

    def test_prefixed_port_net_counts(self):
        self.assertEqual(len(scans(self.vbus('/USB/VUSB', C1='220uF'), 'SIG-A05')), 1)

    def test_a_dc_bus_called_vbus_on_a_board_without_usb_is_not_usb(self):
        db = board({'Q1': 'IRF540', 'C1': '220uF'}, {'VBUS': ['Q1.1', 'C1.1'], 'GND': ['Q1.2', 'C1.2']})
        self.assertEqual(scans(db, 'SIG-A05'), [])

    def test_usb_part_identity_is_enough_without_usb_pin_names(self):
        db = board({'J1': 'USB_B', 'C1': '220uF'}, {'VBUS': ['J1.1', 'C1.1'], 'GND': ['J1.2', 'C1.2']})
        self.assertEqual(len(scans(db, 'SIG-A05')), 1)

    def test_unfitted_and_unreadable_capacitors_do_not_count(self):
        db = self.vbus(C1='220uF', C2='fixme')
        db['parts']['C1']['nc'] = True
        self.assertEqual(scans(db, 'SIG-A05'), [])


class LdoOutputCapacitorTest(unittest.TestCase):
    def ldo(self, parts=None, nets=None, value='AP2112K-3.3'):
        all_nets = {'VIN': ['U1.1'], 'VCC_3V3': ['U1.5', 'U2.1'], 'GND': ['U1.2', 'U2.2']}
        for net, nodes in (nets or {}).items():
            all_nets[net] = all_nets.get(net, []) + nodes
        return board(dict({'U1': value, 'U2': 'MCU'}, **(parts or {})), all_nets,
                     {'U1.1': 'VIN', 'U1.2': 'GND', 'U1.5': 'VOUT', 'U2.1': 'VDD', 'U2.2': 'GND'})

    def test_no_output_capacitor_is_a_candidate(self):
        hits = scans(self.ldo(), 'PWR-A07')
        self.assertEqual([hit['kind'] for hit in hits], ['CANDIDATE'])
        self.assertIn('U1.5', hits[0]['detail'])

    def test_an_output_capacitor_closes_it(self):
        db = self.ldo({'C1': '1uF'}, {'VCC_3V3': ['C1.1'], 'GND': ['C1.2']})
        self.assertEqual(scans(db, 'PWR-A07'), [])

    def test_a_capacitor_behind_a_ferrite_counts(self):
        db = self.ldo({'FB1': 'BLM18', 'C1': '1uF'},
                      {'VCC_3V3': ['FB1.1'], 'VDD_F': ['FB1.2', 'C1.1'], 'GND': ['C1.2']})
        self.assertEqual(scans(db, 'PWR-A07'), [])

    def test_a_capacitor_to_another_signal_does_not_count(self):
        db = self.ldo({'C1': '1uF'}, {'VCC_3V3': ['C1.1'], 'FB': ['C1.2']})
        self.assertEqual(len(scans(db, 'PWR-A07')), 1)

    def test_an_unfitted_capacitor_does_not_count(self):
        db = self.ldo({'C1': '1uF'}, {'VCC_3V3': ['C1.1'], 'GND': ['C1.2']})
        db['parts']['C1']['nc'] = True
        self.assertEqual(len(scans(db, 'PWR-A07')), 1)

    def test_an_ic_without_a_linear_regulator_identity_is_not_judged(self):
        for value in ('TPS22918', 'TLV7031', 'STM32F7802'):
            self.assertEqual(scans(self.ldo(value=value), 'PWR-A07'), [], value)

    def test_common_linear_regulator_families_are_recognised(self):
        for value in ('AMS1117-3.3', 'LD1117S33', 'MCP1700T-3302', 'TLV75533', 'TPS7A4700', '7805', 'L7805', 'my LDO'):
            self.assertEqual(len(scans(self.ldo(value=value), 'PWR-A07')), 1, value)

    def test_an_unused_output_pin_is_left_to_the_floating_net_rules(self):
        db = self.ldo()
        db['pin2net']['U1.5'] = 'LONE'
        db['nets'] = {'VIN': ['U1.1'], 'LONE': ['U1.5'], 'VCC_3V3': ['U2.1'], 'GND': ['U1.2', 'U2.2']}
        self.assertEqual(scans(db, 'PWR-A07'), [])


class FloatingInputTest(unittest.TestCase):
    def test_declared_input_pins_without_a_real_net(self):
        db = board({'U1': 'SOC'}, {'GND': ['U1.4'], 'LONE': ['U1.2'], 'BUS': ['U1.3', 'U1.5']},
                   pinname={'U1.1': 'IN1', 'U1.2': 'IN2', 'U1.3': 'IN3'},
                   pintype={'U1.1': 'IN', 'U1.2': 'IN', 'U1.3': 'IN', 'U1.5': 'OUT'})
        hits = dict(zip(subjects(scans(db, 'NET-A07')),
                        [f['kind'] for f in scans(db, 'NET-A07')]))
        self.assertEqual(hits, {'U1.1': 'FINDING', 'U1.2': 'FINDING'})

    def test_declared_no_connect_input_stays_a_candidate(self):
        db = board({'U1': 'SOC'}, {'NC_1': ['U1.1']}, pintype={'U1.1': 'INPUT'},
                   pseudo_nets=['NC_1'], no_connect_nodes=['U1.1'])
        hits = scans(db, 'NET-A07')
        self.assertEqual([f['kind'] for f in hits], ['CANDIDATE'])

    def test_symbol_declared_types_are_used_when_the_netlist_has_none(self):
        db = board({'U1': 'SOC'}, {'BUS': ['U1.3', 'U1.5']},
                   declared_pintype={'U1.9': 'IN'})
        self.assertEqual(subjects(scans(db, 'NET-A07')), ['U1.9'])


class RefdesTest(unittest.TestCase):
    def test_unannotated_refdes_is_a_finding(self):
        db = board({'R?': '10K', 'R1': '10K', 'U1A': 'SOC'}, {'NET1': ['R1.1']})
        self.assertEqual(subjects(scans(db, 'DOC-A04')), ['R?'])


class RulePlanTest(unittest.TestCase):
    def test_new_scans_are_listed_in_the_rule_ledger(self):
        rules = {row['rule'] for row in build_review_plan(board({}, {}))['rule_plan']}
        self.assertTrue({'DEV-A01', 'DEV-A02', 'DEV-A03', 'NET-A07', 'DOC-A04'} <= rules)
        self.assertTrue({'DEV-A01', 'DEV-A02', 'DEV-A03', 'NET-A07', 'DOC-A04'} <= set(COLD_RULE_INDEXES))

    def test_module_only_reports_registered_rules(self):
        db = board({'C1': '10uF/16V', 'D1': 'LED', 'R?': '0R'},
                   {'VCC_24V': ['C1.1', 'D1.1'], 'GND': ['C1.2', 'D1.2']})
        lint = Lint(db)
        board_scans.run(lint)
        self.assertEqual({f['rule'] for f in lint.F},
                         {'DEV-A01', 'DEV-A03', 'DOC-A04'})



class PowerNameHeuristicTest(unittest.TestCase):
    """名称启发式审计：只凭网名/脚名报出的电源问题要先看原生脚类型、连接器与统一的地名判定。"""

    def rules(self, db, rule):
        return [f for f in scans(db, rule)]

    def test_connector_fed_rail_is_info_not_a_finding(self):
        db = board({'J1': 'Connector:Conn_01x02', 'U1': 'SENSOR'},
                   {'VCC': ['J1.1', 'U1.1'], 'GND': ['J1.2', 'U1.2']},
                   pinname={'U1.1': 'VDD', 'U1.2': 'GND', 'J1.1': '1', 'J1.2': '2'})
        self.assertEqual({f['kind'] for f in scans(db, 'PWR-A01')}, {'INFO'})
        self.assertEqual(scans(db, 'PWR-A02'), [])

    def test_native_power_out_drives_a_rail_on_any_refdes(self):
        db = board({'VR1': 'REG', 'U1': 'SENSOR'},
                   {'VDD_3V3': ['VR1.2', 'U1.1'], 'GND': ['VR1.3', 'U1.2'], 'VIN_RAW': ['VR1.1']},
                   pinname={'VR1.1': 'IN', 'VR1.2': 'OUTPUT', 'VR1.3': 'GND', 'U1.1': 'VDD', 'U1.2': 'GND'},
                   native_pintype={'VR1.2': 'power_out', 'VR1.1': 'power_in', 'U1.1': 'power_in'})
        self.assertNotIn('VDD_3V3', ' '.join(f['detail'] for f in scans(db, 'PWR-A01')))
        self.assertEqual([f for f in scans(db, 'PWR-A02') if 'U1.1' in f['detail']], [])

    def test_supply_pin_name_is_anchored(self):
        db = board({'U1': 'MCU', 'U2': 'LDO'},
                   {'DET': ['U1.1'], 'V3': ['U1.2', 'U2.2'], 'VIN': ['U2.1'], 'GND': ['U1.3', 'U2.3']},
                   pinname={'U1.1': 'VDDIO_DET', 'U1.2': 'VDD', 'U1.3': 'GND',
                            'U2.1': 'IN', 'U2.2': 'OUT', 'U2.3': 'GND'})
        self.assertEqual([f['detail'] for f in scans(db, 'PWR-A02') if 'U1.1' in f['detail']], [])

    def test_named_signal_grounds_are_grounds(self):
        db = board({'U1': 'OPAMP'}, {'SGND': ['U1.1'], 'V5': ['U1.2']},
                   pinname={'U1.1': 'VSS', 'U1.2': 'VDD'})
        self.assertEqual(scans(db, 'PWR-A03'), [])



class TypicalBoardPowerTest(unittest.TestCase):
    """典型电路基准（33 块开源板）中电源规则的误报，按结构而不是名字判断。"""

    def test_rail_fed_from_usb_connector_through_fuse_and_diode(self):
        db = board({'USB-C1': 'OLIMEX_Connectors:USB2.0_TYPE-C', 'F1': 'Device:Polyfuse', 'D1': 'D_Schottky',
                    'U1': 'LDO', 'C1': '10uF'},
                   {'VBUS_IN': ['USB-C1.1', 'F1.1'], 'V_FUSED': ['F1.2', 'D1.2'], '+5V': ['D1.1', 'U1.1', 'C1.1'],
                    'GND': ['USB-C1.2', 'U1.2', 'C1.2']},
                   pinname={'D1.1': 'K', 'D1.2': 'A', 'U1.1': 'VIN', 'U1.2': 'GND'})
        self.assertEqual({f['kind'] for f in scans(db, 'PWR-A01')}, {'INFO'})
        self.assertEqual(scans(db, 'PWR-A02'), [])

    def test_battery_and_rc_filtered_supply_pin(self):
        db = board({'BT1': 'BATTERY', 'U1': 'DW01', 'R1': '100', 'C1': '100nF'},
                   {'VBAT_P': ['BT1.1', 'R1.1'], 'DW_VCC': ['R1.2', 'U1.5', 'C1.1'], 'GND': ['BT1.2', 'U1.6', 'C1.2']},
                   pinname={'U1.5': 'VCC', 'U1.6': 'GND'})
        self.assertEqual(scans(db, 'PWR-A02'), [])

    def test_internal_regulator_pin_with_only_its_capacitor(self):
        db = board({'U1': 'LAN8720A', 'C1': '470nF', 'J1': 'Connector:Conn_01x02'},
                   {'VDDCR': ['U1.6', 'C1.1'], 'V3': ['J1.1', 'U1.19'], 'GND': ['C1.2', 'J1.2', 'U1.20']},
                   pinname={'U1.6': 'VDDCR', 'U1.19': 'VDD', 'U1.20': 'GND'})
        self.assertEqual(scans(db, 'PWR-A02'), [])

    def test_supply_through_solder_jumper_is_a_candidate(self):
        db = board({'J1': 'Connector:Conn_01x02', 'JP1': 'Jumper', 'D3': 'WS2812B'},
                   {'+3V3': ['J1.1', 'JP1.2'], 'LED_VDD': ['JP1.1', 'D3.4'], 'GND': ['J1.2', 'D3.2']},
                   pinname={'D3.4': 'VDD', 'D3.2': 'GND'})
        hits = scans(db, 'PWR-A02')
        self.assertEqual([f['kind'] for f in hits], ['CANDIDATE'])
        self.assertIn('JP1', hits[0]['detail'])

    def test_open_datasheet_nc_pin_is_not_reported(self):
        db = board({'U1': 'W5500', 'J1': 'Connector:Conn_01x02'},
                   {'unconnected-(U1-NC-Pad12)': ['U1.12'], 'unconnected-(U1-INTn-Pad3)': ['U1.3'],
                    'V3': ['J1.1', 'U1.1'], 'GND': ['J1.2', 'U1.2']},
                   pinname={'U1.12': 'NC', 'U1.3': 'INTn', 'U1.1': 'VDD', 'U1.2': 'GND'})
        hits = scans(db, 'NET-A01')
        self.assertEqual([(f['kind'], 'U1.3' in f['detail']) for f in hits], [('CANDIDATE', True)])



class TypicalBoardClassificationTest(unittest.TestCase):
    """典型电路基准：Soldered 库把连接器编为 K、手画继电器没有脚名、Olimex 位号带下划线。"""

    def test_sixteen_pin_k_part_is_not_a_relay_and_usb_c_pins_make_a_connector(self):
        import part_words as pw
        self.assertEqual(pw.classify('K9', {'value': 'HDR'}, 16)[0], pw.UNKNOWN)
        names = [('VBUS', 'A4'), ('CC1', 'A5'), ('CC2', 'B5'), ('GND', 'A1'), ('SBU1', 'A8')]
        self.assertEqual(pw.classify('K1', {'value': 'U262-161N'}, 16, names)[0], pw.CONNECTOR)
        controller = names + [('VDD', '1'), ('SCL', '2')]
        self.assertNotEqual(pw.classify('U1', {'value': 'FUSB302'}, 14, controller)[0], pw.CONNECTOR)

    def test_relay_without_pin_names_takes_contact_roles_from_net_names(self):
        db = board({'K1': 'SRD_RELAY_5V', 'K3': 'TERMINAL_KF235-5.0-3P'},
                   {'NC': ['K1.5', 'K3.1'], 'NO': ['K1.3', 'K3.3'], 'COM': ['K1.4', 'K3.2'],
                    'COIL_A': ['K1.1'], 'COIL_B': ['K1.2']})
        # a relay read from its words alone: a candidate until its datasheet declaration is verified (2026-10-27 B2a)
        self.assertEqual([f['kind'] for f in scans(db, 'NET-A04')], ['CANDIDATE'])

    def test_vendor_refdes_formats_are_annotated(self):
        db = board({'USB-C1': 'Connector:USB_C', 'PS2_KBD1': 'Connector:MiniDIN', 'PGM/DBG1': 'Connector:Conn',
                    'R?': '10k'}, {'A': ['USB-C1.1', 'PS2_KBD1.1', 'PGM/DBG1.1', 'R?.1']})
        self.assertEqual([f['detail'].split(':')[0] for f in scans(db, 'DOC-A04')], ['R?'])

    def test_header_contacts_typed_input_are_driven_off_board(self):
        db = board({'J1': 'HEADER_2x05', 'U2': 'FT232'}, {'CTS': ['J1.5', 'U2.6']},
                   pintype={'J1.5': 'IN', 'U2.6': 'IN'})
        self.assertEqual([f for f in scans(db, 'NET-A06') if 'CTS' in f['detail']], [])



class SeededDetectionTest(unittest.TestCase):
    """种子基准（39 块真实板）漏检的两类：KiCad 极性电容无脚名、传感器经串阻挂在 I²C 上。"""

    def test_kicad_polarized_cap_pin_one_is_plus(self):
        db = board({'C4': 'Device:C_Polarized_Small', 'J1': 'Connector:Conn_01x02'},
                   {'GND': ['C4.1', 'J1.2'], 'SUPPLY_IN': ['C4.2', 'J1.1']})
        db['parts']['C4']['value'] = '100uF'
        self.assertEqual([f['detail'].split(':')[0] for f in scans(db, 'DEV-A02')], ['C4'])
        db['nets'] = {'GND': ['C4.2', 'J1.2'], 'SUPPLY_IN': ['C4.1', 'J1.1']}
        db['pin2net'] = {n: net for net, nodes in db['nets'].items() for n in nodes}
        self.assertEqual(scans(db, 'DEV-A02'), [])

    def test_negative_named_supply_keeps_plus_on_ground(self):
        db = board({'C1': 'Device:CP', 'J1': 'Connector:Conn_01x02'},
                   {'GND': ['C1.1', 'J1.2'], 'VEE': ['C1.2', 'J1.1']})
        self.assertEqual(scans(db, 'DEV-A02'), [])

    def test_sensor_behind_series_resistor_without_pullup(self):
        db = board({'U1': 'TMP117', 'R6': '120R', 'J1': 'Connector:Conn_01x04'},
                   {'/SDA': ['J1.3', 'R6.2'], 'U1_SDA': ['R6.1', 'U1.3'], 'GND': ['U1.1', 'J1.1']})
        hits = scans(db, 'SIG-A03')
        self.assertEqual([f['kind'] for f in hits], ['CANDIDATE'])
        db['parts']['R4'] = {'value': '10k', 'part': '10k', 'prim': '10k', 'nc': False}
        db['nets']['/SDA'].append('R4.1'); db['nets']['V3'] = ['R4.2', 'J1.2']
        db['pin2net'].update({'R4.1': '/SDA', 'R4.2': 'V3', 'J1.2': 'V3'})
        self.assertEqual(scans(db, 'SIG-A03'), [])

    def test_pullups_selected_by_dip_switch_are_info(self):
        db = board({'U1': 'BME280', 'SW1': 'SW_DIP_x02', 'R1': '4.7K', 'J1': 'Connector:Conn_01x04'},
                   {'/SCL': ['U1.4', 'SW1.4', 'J1.3'], 'PU1': ['SW1.1', 'R1.2'], '+3V3': ['R1.1', 'J1.1']})
        self.assertEqual({f['kind'] for f in scans(db, 'SIG-A03')}, {'INFO'})

    def test_bosch_footprint_is_not_an_oscillator(self):
        import part_words as pw
        self.assertEqual(pw.classify('U1', {'prim': 'DS-sensors:BME280',
                                            'jedec': 'DS-sensors:Bosch_LGA-8_2.5x2.5mm'}, 8)[0], pw.IC)


if __name__ == '__main__':
    unittest.main()


class DeclaredRailTest(unittest.TestCase):
    """intent.power_rails names supplies whose net names carry no hint (SRCTL_SUP, BULK, RAWOUT)."""

    def board(self):
        nets = {'SRCTL_SUP': ['U1.1', 'C1.1'], 'GND': ['U1.2', 'C1.2', 'R1.2', 'C2.2'],
                'ZCD': ['U1.3', 'R1.1'], 'RAWOUT': ['C3.1'], 'SEC_RTN': ['C3.2', 'C2.1'],
                'BULK': ['C4.1', 'D1.2'], 'PGND': ['C4.2'], 'RECT': ['D1.1']}
        db = board({'U1': 'SR-CONTROLLER', 'C1': '1u', 'C2': '100n', 'C3': '330u', 'C4': '68u', 'R1': '10k', 'D1': 'US1M'},
                   nets, pinname={'U1.1': 'VCCL', 'U1.2': 'GND', 'U1.3': 'CS',
                                  'D1.1': 'A', 'D1.2': 'K'})
        rails = {'SRCTL_SUP': {'min': 0, 'max': 13}, 'ZCD': {'min': -0.3, 'max': 5}, 'RAWOUT': {'min': 0, 'max': 22},
                 'SEC_RTN': {'min': -0.06, 'max': 0}, 'BULK': {'min': 0, 'max': 445}}
        intent = {'power_rails': {net: {'domain': 'SEC', 'voltage_v': v, 'state': 'run', 'citation': 'fixture'}
                                  for net, v in rails.items()}}
        return db, intent

    def test_declared_supplies_get_rail_checks_and_undriven_scan(self):
        db, intent = self.board()
        plan = build_review_plan(db, intent=intent)
        t01 = {c['object']['net']: c for c in plan['checks'] if c['rule'] == 'PWR-T01'}
        self.assertEqual(sorted(t01), ['BULK', 'RAWOUT', 'SRCTL_SUP'])
        self.assertIn('declared-rail:SRCTL_SUP', t01['SRCTL_SUP']['trigger'])
        lint = Lint(db, '', intent); lint.run()
        undriven = {f['detail'].split(' ')[0] for f in lint.F if f['rule'] == 'PWR-A01'}
        self.assertEqual(undriven, {'BULK', 'SRCTL_SUP', 'RAWOUT'})

    def test_signal_windows_and_returns_are_not_rails(self):
        db, intent = self.board()
        del intent['power_rails']['SRCTL_SUP'], intent['power_rails']['RAWOUT'], intent['power_rails']['BULK']
        plan = build_review_plan(db, intent=intent)
        self.assertEqual([c for c in plan['checks'] if c['rule'] == 'PWR-T01'], [])



class NetNameSplitTest(unittest.TestCase):
    """NET-A02：相似网名只在真正拼写分裂时报，命名惯例里的兄弟/收发/差分对不报。"""

    @staticmethod
    def names(nets):
        db = board({'U1': 'MCU'}, {net: ['U1.' + str(i + 1)] for i, net in enumerate(nets)})
        return [f['detail'] for f in scans(db, 'NET-A02')]

    def test_sheet_path_does_not_inflate_similarity(self):
        # bms-c1：/ESP32-C3 MCU/CAN_STB 与 /ESP32-C3 MCU/CAN_TX 只因共享层次路径而“相似”
        self.assertEqual(self.names(['/ESP32-C3 MCU/CAN_STB', '/ESP32-C3 MCU/CAN_TX']), [])
        self.assertEqual(self.names(['/Current Sense/CUR3', '/Current Sense/FCUR1']), [])
        self.assertEqual(self.names(['/Charge-IC/FBG', '/Charge-IC/OFB']), [])

    def test_real_split_is_still_reported(self):
        self.assertEqual(len(self.names(['/power/VCC_3V3_MCU', '/power/VCC_3V3_MCU_1'])), 1)
        self.assertEqual(len(self.names(['VBUS_5V0_SYS', 'VBUS5V0_SYS'])), 1)

    def test_plus_minus_differential_pair_is_exempt(self):
        self.assertEqual(self.names(['/usb/USB_DATA_D+', '/usb/USB_DATA_D-']), [])
        self.assertEqual(self.names(['TMDS_DATA0+', 'TMDS_DATA0-']), [])

    def test_numbered_siblings_across_sheets_are_exempt(self):
        # moteus-c1：/aux2/AUX2_I2C_PULLUP 与 /stm32g4/AUX1_I2C_PULLUP 只差中间一个序号
        self.assertEqual(self.names(['/aux2/AUX2_I2C_PULLUP', '/stm32g4/AUX1_I2C_PULLUP']), [])

    def test_alphabetical_siblings_are_exempt(self):
        self.assertEqual(self.names(['/Gate Driver/GATE_HIGH_A', '/Gate Driver/GATE_HIGH_B',
                                     '/Gate Driver/GATE_HIGH_C']), [])
        self.assertEqual(self.names(['/aux2/AUX2P_CHANNEL_A', '/aux2/AUX2P_CHANNEL_B']), [])

    def test_transceiver_pairs_are_exempt(self):
        self.assertEqual(self.names(['/TX_MCU/UART_DEBUG_RX', '/TX_MCU/UART_DEBUG_TX']), [])
        self.assertEqual(self.names(['/RX_MCU/ISP_SERIAL_RXD', '/RX_MCU/ISP_SERIAL_TXD']), [])
        self.assertEqual(self.names(['DRV8323_SPI_MISO', 'DRV8323_SPI_MOSI']), [])
        self.assertEqual(self.names(['SENSOR_I2C_SCL', 'SENSOR_I2C_SDA']), [])

    def test_same_named_dual_regulator_nets_are_exempt(self):
        self.assertEqual(self.names(['/TX_AuxPower/BUCK_FB_12V_RAIL', '/TX_AuxPower/BUCK_FB_5V_RAIL']), [])
        self.assertEqual(self.names(['/TX_AuxPower/BUCK_SW_12V_RAIL', '/TX_AuxPower/BUCK_SW_5V_RAIL']), [])


class SupplyPinOnGroundTest(unittest.TestCase):
    """PWR-A02：器件自己的供电脚（原生 power_in）落在地网上。"""

    @staticmethod
    def viper(vdd_net, native='power_in', pinname='VDD'):
        # flyback-viper22a：U1.4 VDD（native power_in）直接落在 GND1。
        db = board({'U1': 'VIPer22ADIP-E', 'C1': '10uF'},
                   {'GND1': ['U1.1', 'C1.2'] + (['U1.4'] if vdd_net == 'GND1' else []),
                    **({vdd_net: ['U1.4', 'C1.1']} if vdd_net != 'GND1' else {'VDD_AUX': ['C1.1']})},
                   pinname={'U1.1': 'S', 'U1.4': pinname},
                   native_pintype={'U1.1': 'passive', 'U1.4': native})
        return db

    def test_power_in_pin_on_ground_is_a_finding(self):
        hits = scans(self.viper('GND1'), 'PWR-A02')
        self.assertEqual([f['kind'] for f in hits], ['FINDING'])
        self.assertIn('U1.4', hits[0]['detail'])
        self.assertIn('GND1', hits[0]['detail'])

    def test_ground_named_passive_and_output_pins_are_not_reported(self):
        self.assertEqual(scans(self.viper('GND1', native='power_in', pinname='VSS'), 'PWR-A02'), [])
        self.assertEqual(scans(self.viper('GND1', native='power_in', pinname='PGND'), 'PWR-A02'), [])
        self.assertEqual(scans(self.viper('GND1', native='power_in', pinname='V_{SS}'), 'PWR-A02'), [])
        self.assertEqual(scans(self.viper('GND1', native='power_in', pinname='PAD'), 'PWR-A02'), [])
        self.assertEqual(scans(self.viper('GND1', native='power_in', pinname='PADGND'), 'PWR-A02'), [])
        # isolated-serial-adapter：隔离 DC-DC 模块的 -Vin 就是输入回流端
        self.assertEqual(scans(self.viper('GND1', native='power_in', pinname='-Vin'), 'PWR-A02'), [])
        self.assertEqual(scans(self.viper('GND1', native='power_in', pinname='VIN-'), 'PWR-A02'), [])
        self.assertEqual(scans(self.viper('GND1', native='passive'), 'PWR-A02'), [])
        self.assertEqual(scans(self.viper('GND1', native='power_out'), 'PWR-A02'), [])

    def test_other_power_in_names_on_ground_are_candidates(self):
        # bms-c1：BQ76952 REGIN（内部 LDO 输入）接地，手册允许未用时接 VSS，只作候选
        hits = scans(self.viper('GND1', native='power_in', pinname='REGIN'), 'PWR-A02')
        self.assertEqual([f['kind'] for f in hits], ['CANDIDATE'])
        # makerverse-motor-driver-2ch：库里脚名只有 "A"，没有供电含义，不报
        self.assertEqual(scans(self.viper('GND1', native='power_in', pinname='A'), 'PWR-A02'), [])

    def test_power_in_pin_on_its_own_rail_is_silent(self):
        db = self.viper('VDD_AUX')
        self.assertEqual([f for f in scans(db, 'PWR-A02') if '地' in f['title']], [])


class SingleNodeNetTest(unittest.TestCase):
    def test_bidirectional_ic_pin_with_only_a_label_is_a_candidate(self):
        # 2026-10-20 第 1 轮裁决：UART 桥未用的调制解调/GPIO 线只挂层次标签 → OVER_STRICT，降 CANDIDATE；
        # 同样只挂一个标签的输入脚（PHY nRST）是真缺陷，仍是 FINDING。
        db = board({'U1': 'CH344Q', 'J1': 'Connector:Conn_01x02'},
                   {'/USB/CTS0': ['U1.41'], '/RST': ['U1.15'], 'V3': ['J1.1', 'U1.1'], 'GND': ['J1.2', 'U1.2']},
                   pinname={'U1.41': 'CTS0/GPIO0', 'U1.15': 'nRST', 'U1.1': 'VDD', 'U1.2': 'GND'},
                   pintype={'U1.41': 'BI', 'U1.15': 'IN', 'U1.1': 'power_in', 'U1.2': 'power_in'})
        hits = scans(db, 'NET-A01')
        self.assertEqual(sorted((f['detail'].split(' <- ')[0], f['kind']) for f in hits),
                         [('/RST', 'FINDING'), ('/USB/CTS0', 'CANDIDATE')])


class FedRailTest(unittest.TestCase):
    """R6 acceptance 2026-10-24 (claude1 false alarms): rails made by a converter are fed — a winding through its
    rectifier, the bridge output through a start-up resistor into an HV pin, a return pin on a return net."""

    def test_a_winding_fed_rail_and_a_gnd_pin_on_a_return_net_are_not_undriven(self):
        db = board({'T1': 'TRANSFORMER', 'D1': 'D_Schottky', 'C1': '47u/35V', 'U1': 'NCP1343', 'U2': 'NCP4306', 'R1': '10m'},
                   {'AUX': ['T1.5', 'D1.2'], 'VCC': ['D1.1', 'C1.1', 'U1.8'], 'PGND': ['T1.6', 'C1.2', 'U1.3'],
                    'SEC_RTN': ['U2.7', 'U2.EP', 'R1.1'], 'SGND': ['R1.2']},
                   pinname={'D1.1': 'K', 'D1.2': 'A', 'U1.8': 'VCC', 'U1.3': 'GND', 'U2.7': 'GND', 'U2.EP': 'EP'},
                   native_pintype={'U2.7': 'power_in', 'U2.EP': 'power_in', 'U1.8': 'power_in'})
        self.assertEqual(scans(db, 'PWR-A02'), [])

    def test_an_hv_pin_through_its_startup_resistor_from_the_bridge_is_fed(self):
        db = board({'BR1': 'GBU4M', 'C1': '470n/450V', 'R1': '4.7k/0.5W', 'U1': 'NCP1343', 'J1': 'Connector:Conn_01x02'},
                   {'L': ['J1.1', 'BR1.3'], 'N': ['J1.2', 'BR1.4'], 'RECT': ['BR1.1', 'C1.1', 'R1.1'],
                    'PGND': ['BR1.2', 'C1.2', 'U1.3'], 'HV': ['R1.2', 'U1.10']},
                   pinname={'BR1.1': '+', 'BR1.2': '-', 'BR1.3': '~', 'BR1.4': '~', 'U1.10': 'HV', 'U1.3': 'GND'},
                   native_pintype={'U1.10': 'power_in'})
        self.assertEqual(scans(db, 'PWR-A02'), [])
        # the same pin with its resistor going nowhere is still undriven
        db['nets']['RECT'].remove('R1.1'); db['nets']['FLOAT'] = ['R1.1']; db['pin2net']['R1.1'] = 'FLOAT'
        self.assertEqual([f['detail'] for f in scans(db, 'PWR-A02')], ['U1.10 (HV) <- HV'])

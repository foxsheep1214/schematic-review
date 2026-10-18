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
        # 100W PD 复审：CFG_SDA 只接 U601 和测试点，对端与上拉在生产夹具。
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
        from checkers import netgraph as ng
        self.assertEqual(ng.classify('K9', {'value': 'HDR'}, 16)[0], ng.UNKNOWN)
        names = [('VBUS', 'A4'), ('CC1', 'A5'), ('CC2', 'B5'), ('GND', 'A1'), ('SBU1', 'A8')]
        self.assertEqual(ng.classify('K1', {'value': 'U262-161N'}, 16, names)[0], ng.CONNECTOR)
        controller = names + [('VDD', '1'), ('SCL', '2')]
        self.assertNotEqual(ng.classify('U1', {'value': 'FUSB302'}, 14, controller)[0], ng.CONNECTOR)

    def test_relay_without_pin_names_takes_contact_roles_from_net_names(self):
        db = board({'K1': 'SRD_RELAY_5V', 'K3': 'TERMINAL_KF235-5.0-3P'},
                   {'NC': ['K1.5', 'K3.1'], 'NO': ['K1.3', 'K3.3'], 'COM': ['K1.4', 'K3.2'],
                    'COIL_A': ['K1.1'], 'COIL_B': ['K1.2']})
        self.assertEqual(scans(db, 'NET-A04'), [])

    def test_vendor_refdes_formats_are_annotated(self):
        db = board({'USB-C1': 'Connector:USB_C', 'PS2_KBD1': 'Connector:MiniDIN', 'PGM/DBG1': 'Connector:Conn',
                    'R?': '10k'}, {'A': ['USB-C1.1', 'PS2_KBD1.1', 'PGM/DBG1.1', 'R?.1']})
        self.assertEqual([f['detail'].split(':')[0] for f in scans(db, 'DOC-A04')], ['R?'])

    def test_header_contacts_typed_input_are_driven_off_board(self):
        db = board({'J1': 'HEADER_2x05', 'U2': 'FT232'}, {'CTS': ['J1.5', 'U2.6']},
                   pintype={'J1.5': 'IN', 'U2.6': 'IN'})
        self.assertEqual([f for f in scans(db, 'NET-A06') if 'CTS' in f['detail']], [])


if __name__ == '__main__':
    unittest.main()

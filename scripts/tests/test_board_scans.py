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
        from checkers import netgraph as ng
        self.assertEqual(ng.classify('U1', {'prim': 'DS-sensors:BME280',
                                            'jedec': 'DS-sensors:Bosch_LGA-8_2.5x2.5mm'}, 8)[0], ng.IC)


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

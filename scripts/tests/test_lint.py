import pathlib
import sys
import unittest
import tempfile

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from lint import Lint, _pin_class, validate_evidence
from electrical_fixtures import bind_evidence, pin_analysis, divider_model


def sample_db():
    nets = {
        'BUS': ['U1.1', 'U2.1'],
        'EN_NET': ['U3.1', 'R1.1'],
        'VCC_12V': ['R1.2'],
        'I2C_SCL': ['U4.1'],
        'BOOT0': ['U5.1', 'R2.1'],
        'VCC_3V3': ['R2.2'],
        'JMAP': ['J1.1'],
    }
    parts = {
        'U1': {'value': 'A', 'part': 'A', 'prim': 'A', 'nc': False},
        'U2': {'value': 'B', 'part': 'B', 'prim': 'B', 'nc': False},
        'U3': {'value': 'C', 'part': 'C', 'prim': 'C', 'nc': False},
        'U4': {'value': 'D', 'part': 'D', 'prim': 'D', 'nc': False},
        'U5': {'value': 'E', 'part': 'E', 'prim': 'E', 'nc': False},
        'R1': {'value': '10K/1%', 'part': 'R', 'prim': 'R', 'nc': False},
        'R2': {'value': '10K/1%', 'part': 'R', 'prim': 'R', 'nc': False},
        'J1': {'value': 'CONN', 'part': 'CONN', 'prim': 'CONN', 'nc': False},
    }
    pin2net = {node: net for net, nodes in nets.items() for node in nodes}
    return {
        'nets': nets,
        'parts': parts,
        'pin2net': pin2net,
        'pinname': {
            'U1.1': 'OUTA', 'U2.1': 'OUTB', 'U3.1': 'EN',
            'U4.1': 'SCL', 'U5.1': 'BOOT0', 'J1.1': 'VBUS_WRONG',
        },
        'pintype': {'U1.1': 'OUT', 'U2.1': 'OUT'},
        'ref2page': {},
        'pseudo_nets': [],
    }


def hot_evidence():
    return {
        'schema_version': 2,
        'checks': [
            {
                'id': 'EN-ABS',
                'rule': 'RST-E01',
                'kind': 'pin_bias',
                'node': 'U3.1',
                'required_default': 'high',
                'abs_max_v': 5.5,
                'citation': 'U3 datasheet Rev.A p.4',
            },
            {
                'id': 'SCL-PULL',
                'rule': 'SIG-E01',
                'kind': 'required_pull',
                'net': 'I2C_SCL',
                'direction': 'up',
                'to': 'VCC_3V3',
                'resistance_ohm': {'min': 1000, 'max': 4700},
                'citation': 'U4 HDG v1 p.8',
            },
            {
                'id': 'J1-MAP',
                'rule': 'DEV-E01',
                'kind': 'pin_map',
                'ref': 'J1',
                'expected': {'1': 'VBUS'},
                'citation': 'J1 drawing Rev.B p.2',
            },
            {
                'id': 'BOOT-LOW',
                'rule': 'RST-E02',
                'kind': 'strap',
                'node': 'U5.1',
                'required': 'low',
                'citation': 'U5 datasheet Rev.C Table 3',
            },
        ],
    }


def divider_db():
    nets = {
        'VOUT_2V4': ['R10.1'],
        'FB': ['U10.1', 'R10.2', 'R11.1'],
        'GND': ['R11.2'],
    }
    parts = {
        'U10': {'value': 'REG', 'part': 'REG', 'prim': 'REG', 'nc': False},
        'R10': {'value': '20K/1%', 'part': 'R', 'prim': 'R', 'nc': False},
        'R11': {'value': '10K/1%', 'part': 'R', 'prim': 'R', 'nc': False},
    }
    return {
        'nets': nets,
        'parts': parts,
        'pin2net': {node: net for net, nodes in nets.items() for node in nodes},
        'pinname': {'U10.1': 'FB'},
        'pintype': {},
        'ref2page': {},
        'pseudo_nets': [],
    }


class LintTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def bound_lint(self, database, evidence):
        audit = bind_evidence(database, evidence, self.directory.name)
        return Lint(database, intent={'expect': {}}, evidence=evidence, datasheet_audit=audit)

    def test_cadence_bi_pinuse_maps_to_bidirectional(self):
        self.assertEqual(_pin_class('BI'), 'BIDI')

    def test_evidence_validation_requires_citation(self):
        evidence = hot_evidence()
        del evidence['checks'][0]['citation']
        self.assertTrue(validate_evidence(evidence))

    def test_evidence_validation_rejects_duplicate_and_bad_ranges(self):
        evidence = {
            'schema_version': 2,
            'checks': [
                {
                    'id': 'DUP', 'rule': 'PWR-E01', 'kind': 'divider',
                    'net': 'FB',
                    'vref': {'min': 0.81, 'typ': 0.8, 'max': 0.79},
                    'resistor_tolerance': 1.2,
                    'expected': {'min': 3.4, 'max': 3.3},
                    'citation': 'REG datasheet Rev.A p.9',
                },
                {
                    'id': 'DUP', 'rule': 'RST-E01', 'kind': 'pin_bias',
                    'node': 'U1.1', 'required_default': 'high',
                    'citation': 'REG datasheet Rev.A p.4',
                },
            ],
        }
        errors = validate_evidence(evidence)
        self.assertTrue(any('重复' in error for error in errors))
        self.assertTrue(any('min <= typ <= max' in error for error in errors))
        self.assertTrue(any('resistor_tolerance' in error for error in errors))
        self.assertTrue(any('expected.min 不得大于 max' in error
                            for error in errors))

    def test_evidence_validation_handles_non_string_schema_values(self):
        evidence = {
            'schema_version': 2,
            'checks': [{
                'id': ['bad'], 'rule': ['RST-E01'], 'kind': ['pin_bias'],
                'node': ['U1.1'], 'required_default': ['high'],
                'citation': ['not text'],
            }],
        }
        errors = validate_evidence(evidence)
        self.assertGreaterEqual(len(errors), 4)

    def test_pinuse_and_hot_rules_execute(self):
        evidence = hot_evidence()
        self.assertEqual(validate_evidence(evidence), [])
        evidence['checks'][0].update(vih_min_v=2.0, abs_min_v=-.3, voltage_analysis=pin_analysis(12, 12))
        evidence['checks'][3].update(vil_max_v=0.8, voltage_analysis=pin_analysis(3.3, 3.3))
        lint = self.bound_lint(sample_db(), evidence)
        findings = lint.run()
        rules = {item['rule'] for item in findings
                 if item['kind'] == 'FINDING'}
        self.assertIn('NET-A06', rules)
        self.assertIn('RST-E01', rules)
        self.assertIn('SIG-E01', rules)
        self.assertIn('DEV-E01', rules)
        self.assertIn('RST-E02', rules)
        self.assertEqual(
            lint.hot_executed, {'SIG-E01', 'RST-E01', 'DEV-E01', 'RST-E02'})
        self.assertTrue(any(item[0] == 'NET-A06' for item in lint.skipped))

    def test_hot_divider_uses_worst_case_window(self):
        evidence = {
            'schema_version': 2,
            'checks': [
                {
                    'id': 'FB-WCA',
                    'rule': 'PWR-E01',
                    'kind': 'divider',
                    'net': 'FB',
                    'vref': {'typ': 0.8, 'min': 0.792, 'max': 0.808},
                    'expected': {'min': 2.39, 'max': 2.41},
                    'citation': 'REG datasheet Rev.A p.9',
                }
            ],
        }
        self.assertEqual(validate_evidence(evidence), [])
        model = divider_model('VOUT_2V4')
        model['ignored_nodes'] = {'U10.1': 'Synthetic FB input current included in model'}
        evidence['checks'][0]['divider_model'] = model
        lint = self.bound_lint(divider_db(), evidence)
        findings = lint.run()
        self.assertTrue(any(x['rule'] == 'PWR-E01' for x in findings))
        self.assertIn('PWR-E01', lint.hot_executed)

    def test_conflicting_pulls_remain_candidate(self):
        database = sample_db()
        database['nets']['GND'] = ['R3.2']
        database['nets']['EN_NET'].append('R3.1')
        database['parts']['R3'] = {
            'value': '10K/1%', 'part': 'R', 'prim': 'R', 'nc': False}
        database['pin2net']['R3.1'] = 'EN_NET'
        database['pin2net']['R3.2'] = 'GND'
        evidence = {
            'schema_version': 2,
            'checks': [{
                'id': 'EN-BIAS', 'rule': 'RST-E01', 'kind': 'pin_bias',
                'node': 'U3.1', 'required_default': 'high',
                'citation': 'U3 datasheet Rev.A p.4',
            }],
        }
        lint = self.bound_lint(database, evidence)
        findings = lint.run()
        self.assertTrue(any(
            item['rule'] == 'RST-E01' and item['kind'] == 'CANDIDATE'
            and item.get('review_result') == 'INSUFFICIENT'
            for item in findings))
        self.assertFalse(any(
            item['rule'] == 'RST-E01' and item['check_id'] == 'EN-BIAS'
            for item in lint.passes))

    def test_required_series_honors_explicit_rail_target(self):
        database = sample_db()
        evidence = {
            'schema_version': 2,
            'checks': [{
                'id': 'EN-SERIES', 'rule': 'SIG-E01',
                'kind': 'required_series', 'net': 'EN_NET',
                'to': 'VCC_12V',
                'resistance_ohm': {'min': 9000, 'max': 11000},
                'citation': 'U3 datasheet Rev.A p.4',
            }],
        }
        self.assertEqual(validate_evidence(evidence), [])
        lint = self.bound_lint(database, evidence)
        lint.run()
        self.assertTrue(any(
            item['rule'] == 'SIG-E01' and item['check_id'] == 'EN-SERIES'
            for item in lint.passes))

    def test_export_log_rules_are_listed_as_not_executed_without_a_log(self):
        lint = Lint(sample_db(), intent={'expect': {}})
        lint.run()
        self.assertTrue({'DOC-A01', 'DOC-A02'} <= {item[0] for item in lint.skipped})
        lint = Lint(sample_db(), log_text='Netlist export completed', intent={'expect': {}})
        lint.run()
        self.assertFalse({'DOC-A01', 'DOC-A02'} & {item[0] for item in lint.skipped})

    @staticmethod
    def ground_island_db():
        """精简自 SolderedElectronics MPPT-Li-Ion-CN3791 V1.2.1（TAPR OHL）的盲植变体：
        CN3791 地脚 U1.2 与补偿电容 C5.1 被改到 GNDA，GNDA 与 GND 之间没有任何连接。"""
        nets = {
            'GND': ['K1.1', 'K3.2', 'K6.2', 'D4.1', 'C1.2', 'C2.2', 'C4.2', 'R4.2', 'R7.2'],
            'GNDA': ['U1.2', 'C5.1'],
            'VCC': ['K1.2', 'U1.9', 'C1.1'],
            'COM': ['U1.5', 'C5.2'],
            'BAT': ['U1.7', 'K3.1', 'K6.1', 'C2.1', 'C4.1'],
            'MPPT': ['U1.4', 'R4.1', 'R7.1'],
        }
        parts = {ref: {'value': ref, 'part': ref, 'prim': ref, 'nc': False}
                 for ref in {node.split('.')[0] for nodes in nets.values() for node in nodes}}
        for ref in ('K1', 'K3', 'K6'):
            parts[ref]['prim'] = 'Connector:Screw_Terminal_01x02'
        parts['U1'].update(value='CN3791', part='CN3791', prim='Battery_Management:CN3791')
        pinname = {'U1.2': 'GND', 'U1.9': 'VCC', 'U1.5': 'COM', 'U1.7': 'BAT', 'U1.4': 'MPPT'}
        return {'nets': nets, 'parts': parts,
                'pin2net': {node: net for net, nodes in nets.items() for node in nodes},
                'pinname': pinname, 'pintype': {}, 'ref2page': {}, 'pseudo_nets': []}

    def island_findings(self, database):
        return [x for x in Lint(database, intent={'expect': {}}).run()
                if x['rule'] == 'PWR-A03' and '孤岛' in x['name']]

    def link(self, database, ref, a, b, prim):
        database['parts'][ref] = {'value': ref, 'part': ref, 'prim': prim, 'nc': False}
        for pin, net in (('1', a), ('2', b)):
            database['nets'][net].append(f'{ref}.{pin}')
            database['pin2net'][f'{ref}.{pin}'] = net

    def test_ground_island_with_ic_ground_pin_is_flagged(self):
        findings = self.island_findings(self.ground_island_db())
        self.assertEqual(len(findings), 1)
        self.assertIn('GNDA', findings[0]['detail'])
        self.assertIn('U1.2', findings[0]['detail'])

    def test_capacitor_is_not_a_ground_link(self):
        database = self.ground_island_db()
        self.link(database, 'C9', 'GNDA', 'GND', 'Device:C')
        self.assertEqual(len(self.island_findings(database)), 1)

    def test_resistive_link_connector_or_bridge_device_clears_island(self):
        cases = {
            'zero-ohm': lambda d: self.link(d, 'R9', 'GNDA', 'GND', 'Device:R'),
            'connector': lambda d: (d['nets']['GNDA'].append('J9.1'), d['pin2net'].update({'J9.1': 'GNDA'}),
                                    d['parts'].update({'J9': {'value': 'J9', 'part': 'J9',
                                                              'prim': 'Connector:Conn_01x01', 'nc': False}})),
            'isolator': lambda d: (d['nets']['GNDA'].append('U9.8'), d['nets']['GND'].append('U9.4'),
                                   d['pin2net'].update({'U9.8': 'GNDA', 'U9.4': 'GND'}),
                                   d['parts'].update({'U9': {'value': 'ISO1050', 'part': 'ISO1050', 'prim': 'Interface_CAN_LIN:ISO1050DUB', 'nc': False}})),
        }
        for name, change in cases.items():
            with self.subTest(case=name):
                database = self.ground_island_db()
                change(database)
                self.assertEqual(self.island_findings(database), [])

    def test_dnp_link_does_not_clear_island(self):
        database = self.ground_island_db()
        self.link(database, 'R9', 'GNDA', 'GND', 'Device:R')
        database['parts']['R9']['nc'] = True
        self.assertEqual(len(self.island_findings(database)), 1)

    def add_part(self, database, ref, prim, pins):
        database['parts'][ref] = {'value': ref, 'part': ref, 'prim': prim, 'nc': False}
        for pin, net, name in pins:
            database['nets'].setdefault(net, []).append(f'{ref}.{pin}')
            database['pin2net'][f'{ref}.{pin}'] = net
            if name:
                database['pinname'][f'{ref}.{pin}'] = name

    def test_every_dc_link_kind_clears_island(self):
        for ref, prim in (('FB9', 'Device:FerriteBead'), ('L9', 'Device:L'),
                          ('JP9', 'Jumper:SolderJumper_2_Bridged'), ('F9', 'Device:Fuse'),
                          ('NT1', 'Device:NetTie_2')):
            with self.subTest(ref=ref):
                database = self.ground_island_db()
                self.link(database, ref, 'GNDA', 'GND', prim)
                self.assertEqual(self.island_findings(database), [])

    def test_series_chain_and_common_mode_choke_clear_island(self):
        database = self.ground_island_db()
        database['nets']['Net-(R9-Pad2)'] = []
        self.link(database, 'R9', 'GNDA', 'Net-(R9-Pad2)', 'Device:R')
        self.link(database, 'FB9', 'Net-(R9-Pad2)', 'GND', 'Device:FerriteBead')
        self.assertEqual(self.island_findings(database), [])
        database = self.ground_island_db()
        self.add_part(database, 'L9', 'Device:L_CommonMode', [('1', 'GNDA', None), ('2', 'GND', None),
                                                              ('3', 'VCC', None), ('4', 'BAT', None)])
        self.assertEqual(self.island_findings(database), [])

    def test_same_ic_spanning_both_grounds_is_a_candidate(self):
        database = self.ground_island_db()
        self.add_part(database, 'U9', 'Analog:ADC', [('1', 'AGND', 'AGND'), ('2', 'GND', 'PGND'),
                                                    ('3', 'VCC', 'VDD')])
        found = [x for x in self.island_findings(database) if 'AGND' in x['detail']]
        self.assertEqual([x['kind'] for x in found], ['CANDIDATE'])
        self.assertIn('U9', found[0]['detail'])

    def test_isolator_sense_line_and_signal_net_are_not_islands(self):
        cases = {
            'isolator': ('U9', 'Isolator:ISO7721', [('1', 'GNDA', 'GND2'), ('2', 'GND', 'GND1')]),
            'sense': ('U9', 'Regulator:BUCK', [('1', 'VSS_SENSE', 'VSS_SENSE'), ('2', 'GND', 'GND')]),
            'signal': ('U9', 'Sensor:DET', [('1', 'GND_DET', 'DET'), ('2', 'GND', 'GND')]),
        }
        for name, (ref, prim, pins) in cases.items():
            with self.subTest(case=name):
                database = self.ground_island_db()
                if name != 'isolator':
                    database['nets'].pop('GNDA')
                    for node in ('U1.2', 'C5.1'):
                        database['pin2net'][node] = 'GND'
                        database['nets']['GND'].append(node)
                self.add_part(database, ref, prim, pins)
                self.assertEqual(self.island_findings(database), [])

    def test_transformer_secondary_island_is_not_reported(self):
        database = self.ground_island_db()
        self.add_part(database, 'T1', 'Transformer:SN6505_XFMR', [('1', 'GNDA', None), ('2', 'SEC_HI', None),
                                                                 ('3', 'PRI_A', None), ('4', 'PRI_B', None)])
        self.assertEqual(self.island_findings(database), [])

    def test_ic_prefix_and_vssa_pin_are_recognized(self):
        database = self.ground_island_db()
        self.add_part(database, 'IC1', 'MCU:STM32', [('1', 'VSSA', 'VSSA'), ('2', 'VCC', 'VDDA')])
        found = [x for x in self.island_findings(database) if 'VSSA' in x['detail']]
        self.assertEqual(len(found), 1)
        self.assertIn('IC1.1', found[0]['detail'])

    def test_no_ic_island_or_single_ground_is_not_reported(self):
        database = self.ground_island_db()
        self.add_part(database, 'H1', 'Mechanical:MountingHole_Pad', [('1', 'CHASSIS_GND', None)])
        self.link(database, 'C9', 'CHASSIS_GND', 'GND', 'Device:C')
        self.assertEqual([x for x in self.island_findings(database) if 'CHASSIS' in x['detail']], [])
        database = self.ground_island_db()
        database['nets'].pop('GNDA')
        for node in ('U1.2', 'C5.1'):
            database['pin2net'][node] = 'GND'
            database['nets']['GND'].append(node)
        self.assertEqual(self.island_findings(database), [])

    def test_pseudo_ground_net_is_ignored(self):
        database = self.ground_island_db()
        database['pseudo_nets'] = ['GNDA']
        self.assertEqual(self.island_findings(database), [])

    def test_tool_generated_net_names_are_not_spelling_splits(self):
        database = sample_db()
        for net in ('/power/Net-(U1-Pad5)', '/power/Net-(U1-Pad9)', 'unconnected-(J1-NC-PadNC1)', 'unconnected-(J1-NC-PadNC2)',
                    'VBUS_5V0_SYS', 'VBUS5V0_SYS'):
            database['nets'][net] = ['U1.' + str(len(database['nets']) + 10)]
            database['pin2net'][database['nets'][net][0]] = net
        found = [x['detail'] for x in Lint(database, intent={'expect': {}}).run() if x['rule'] == 'NET-A02']
        self.assertEqual(len(found), 1)
        self.assertIn('VBUS5V0_SYS', found[0])

    def test_nc_nets_split_into_short_finding_and_tool_info(self):
        database = sample_db()
        for net, nodes in (('NC', ['U1.2', 'U2.2']), ('NC_1', ['U3.2', 'U4.2'])):
            database['nets'][net] = nodes
            database['pin2net'].update({node: net for node in nodes})
        database['pseudo_nets'] = ['NC']
        findings = [x for x in Lint(database, intent={'expect': {}}).run() if x['rule'] == 'NET-A04']
        self.assertEqual({x['detail'].split(':')[0]: x['kind'] for x in findings},
                         {'NC': 'INFO', 'NC_1': 'FINDING'})

    def test_bom_field_hygiene_checks_all_identity_fields(self):
        database = sample_db()
        database['parts']['U1']['jedec'] = ' QFN32'
        lint = Lint(database, intent={'expect': {}})
        findings = lint.run()
        self.assertTrue(any(
            item['rule'] == 'DOC-A03' and 'U1.jedec' in item['detail']
            for item in findings))


if __name__ == '__main__':
    unittest.main()

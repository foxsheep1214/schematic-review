"""Synthetic node-owner and explicit physical branch invariants."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest
import tempfile
import subprocess

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import board_intent
import board_scans
from decoupling import build_decoupling_inventory
from i2c_topology import build_i2c_topology, validate_i2c_intent
from revision_impact import _coordinates
from validate_review import primary_anchors
from lint import Lint
from simulate_rc import prepare


def db():
    nets = {'SDA': ['RM1.1.1', 'U1.1'], 'SCL': ['RM1.2.1', 'U1.2'],
            'V3': ['RM1.1.2', 'RM1.2.2', 'U1.3'], 'GND': ['U1.4']}
    return {'parts': {'RM1': {'part': 'SYNTHETIC-ARRAY', 'value': '4k7', 'nc': False},
                      'U1': {'part': 'SYNTHETIC-I2C', 'value': 'SYNTHETIC-I2C', 'nc': False}},
            'nets': nets, 'pin2net': {n: net for net, nodes in nets.items() for n in nodes},
            'pinname': {'RM1.1.1': 'A1', 'RM1.1.2': 'B1', 'RM1.2.1': 'A2', 'RM1.2.2': 'B2',
                        'U1.1': 'SDA', 'U1.2': 'SCL', 'U1.3': 'VDD', 'U1.4': 'VSS'},
            'pseudo_nets': []}


def intent(board):
    return {'input_sha256': board_intent.input_fingerprint(board),
            'assemblies': [{'id': 'RUN', 'citation': 'Synthetic exact population',
                            'population': {'RM1': True, 'U1': True}}],
            'i2c_topology': {'schema_version': 2,
                'buses': [{'id': 'B', 'sda': ['U1.1'], 'scl': ['U1.2'], 'citation': 'Synthetic physical map'}],
                'components': {'U1': {'kind': 'endpoint', 'citation': 'Synthetic physical map'},
                               'RM1': {'kind': 'resistor', 'citation': 'Synthetic two source-proven independent branches',
                                       'links': [['RM1.1.1', 'RM1.1.2'], ['RM1.2.1', 'RM1.2.2']]}},
                'rails': {'V3': 'Synthetic supply'}}}


class DottedPhysicalPinTests(unittest.TestCase):
    def test_default_strict_native_xml_preserves_complete_pin_ids(self):
        xml = '<export><components><comp ref="RM1"><value>SYNTHETIC-ARRAY</value>\n<libsource lib="Synthetic" part="Array"/></comp><comp ref="J1"><value>Connector</value>\n<libsource lib="Synthetic" part="Connector"/></comp></components>\n<libparts><libpart lib="Synthetic" part="Array"><pins>\n<pin num="1.1" name="A" type="passive"/><pin num="1.2" name="B" type="passive"/>\n</pins></libpart><libpart lib="Synthetic" part="Connector"><pins>\n<pin num="1" name="1" type="passive"/><pin num="2" name="2" type="passive"/>\n</pins></libpart></libparts><nets>\n<net code="1" name="SIGNAL"><node ref="RM1" pin="1.1" pinfunction="A" pintype="passive"/>\n<node ref="J1" pin="1" pinfunction="1" pintype="passive"/></net>\n<net code="2" name="V3"><node ref="RM1" pin="1.2" pinfunction="B" pintype="passive"/>\n<node ref="J1" pin="2" pinfunction="2" pintype="passive"/></net></nets></export>'
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / 'native.xml'; source.write_text(xml)
            output = folder / 'db.json'
            result = subprocess.run([sys.executable, '-B', str(ROOT / 'parse_kicad.py'),
                                     str(source), '-o', str(output)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            board = json.loads(output.read_text())
            self.assertTrue(board['integrity']['self_check_passed'])
            self.assertEqual(board['pin2net']['RM1.1.1'], 'SIGNAL')
            self.assertEqual(board['pin2net']['RM1.1.2'], 'V3')
            device = {'mpn': 'SYNTHETIC-ARRAY', 'package': 'Synthetic native exact package',
                      'identity_citation': 'Synthetic native identity',
                      'citation': 'Synthetic explicit source labels, not a real manufacturer claim',
                      'pinout_complete': True,
                      'pins': {pin: {'name': name, 'role': 'other'}
                               for pin, name in [('1.1', 'A'), ('1.2', 'B')]}}
            self.assertEqual(board_intent.device_errors({'RM1': device}, board), [])
            self.assertEqual(board_intent.pin_sets(board, 'RM1', device), ([], []))
            self.assertEqual(primary_anchors({'node': 'RM1.1.1'}, board), ({'RM1'}, {'SIGNAL'}))

    def test_capacitor_rating_scan_keeps_complete_source_pin_ids(self):
        board = {'parts': {'C1': {'part': 'C', 'value': '10uF/16V', 'nc': False}},
                 'nets': {'VCC_24V': ['C1.1.1'], 'GND': ['C1.1.2']},
                 'pin2net': {'C1.1.1': 'VCC_24V', 'C1.1.2': 'GND'},
                 'pinname': {}, 'pintype': {}}
        scanner = Lint(board); board_scans.run(scanner)
        self.assertEqual(len([f for f in scanner.F if f['rule'] == 'DEV-A01']), 1)

    def test_unfitted_dotted_input_is_not_falsely_reported_floating(self):
        board = {'parts': {'U1': {'part': 'SOC', 'value': 'SOC', 'nc': True}},
                 'nets': {'LONE': ['U1.1.1']}, 'pin2net': {'U1.1.1': 'LONE'},
                 'pinname': {'U1.1.1': 'INPUT'}, 'pintype': {'U1.1.1': 'IN'}}
        scanner = Lint(board); board_scans.run(scanner)
        self.assertEqual([f for f in scanner.F if f['rule'] == 'NET-A07'], [])

    def test_two_terminal_simulation_does_not_hide_additional_dotted_pin(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            board = {'parts': {'R1': {'prim': 'Device:R', 'value': '1k'},
                               'R2': {'prim': 'Device:R', 'value': '1k'}},
                     'pin2net': {'R1.1': 'VIN', 'R1.2': 'OUT', 'R1.3.1': 'OUT',
                                 'R2.1': 'OUT', 'R2.2': 'GND'},
                     'nets': {'VIN': ['R1.1'], 'OUT': ['R1.2', 'R1.3.1', 'R2.1'], 'GND': ['R2.2']}}
            source = folder / 'bounds.txt'; source.write_text('Synthetic ideal resistor bounds')
            input_file = folder / 'db.json'; input_file.write_text(json.dumps(board))
            spec = {'schema_version': 1, 'db_sha256': hashlib.sha256(input_file.read_bytes()).hexdigest(),
                    'check_id': 'SYNTHETIC', 'state': 'RUN', 'model': 'ideal_linear_RC',
                    'components': {r: {'kind': 'R', 'min_si': 990, 'max_si': 1010} for r in ['R1', 'R2']},
                    'ground': 'GND', 'source': {'net': 'VIN', 'min_v': 5, 'max_v': 5},
                    'analysis': {'kind': 'op', 'net': 'OUT'}, 'window': {'min_v': 2.47, 'max_v': 2.53},
                    'excluded_nodes': {'R1.3.1': 'This belongs to modeled R1 and must not be hidden as external'},
                    'assumptions': ['Synthetic ideal test'],
                    'basis': [{'path': 'bounds.txt', 'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                               'locator': 'Synthetic bounds line1'}]}
            spec_file = folder / 'spec.json'; spec_file.write_text(json.dumps(spec))
            with self.assertRaisesRegex(ValueError, 'two mutually consistent physical pins'):
                prepare(input_file, spec_file)

    def test_explicit_pin_map_matches_without_truncating_any_identifier(self):
        board = db()
        device = {'mpn': 'SYNTHETIC-ARRAY', 'package': 'Synthetic exact package',
                  'identity_citation': 'Synthetic exact BOM', 'citation': 'Synthetic complete native physical pin labels',
                  'pinout_complete': True,
                  'pins': {pin: {'name': pin, 'role': 'other'} for pin in ['1.1', '1.2', '2.1', '2.2']}}
        self.assertEqual(board_intent.device_errors({'RM1': device}, board), [])
        self.assertEqual(board_intent.pin_sets(board, 'RM1', device), ([], []))
        device['pins']['9.1'] = {'name': 'MISSING', 'role': 'other'}
        self.assertEqual(board_intent.pin_sets(board, 'RM1', device)[0], ['RM1.9.1'])
        self.assertEqual(board['pin2net']['RM1.1.1'], 'SDA')

    def test_primary_and_revision_anchors_use_true_owner_and_complete_pin(self):
        board = db()
        self.assertEqual(primary_anchors({'node': 'RM1.1.1'}, board), ({'RM1'}, {'SDA'}))
        result = _coordinates(board, board, refs=['RM1'])
        self.assertTrue({'RM1.1.1', 'RM1.1.2', 'RM1.2.1', 'RM1.2.2'} <= result['nodes'])
        self.assertEqual(result['refs'], {'RM1', 'U1'})
        self.assertNotIn('RM1.1', result['refs'])

    def test_explicit_i2c_branches_keep_both_resistors_and_values(self):
        board = db(); spec = intent(board)
        self.assertEqual(validate_i2c_intent(spec, board), [])
        inventory = build_i2c_topology(board, spec)
        regions = inventory['states'][0]['regions']
        self.assertEqual(len(regions), 2)
        self.assertEqual({tuple(r['nets']) for r in regions}, {('SDA',), ('SCL',)})
        for row in regions:
            self.assertEqual(len(row['pullups']), 1)
            self.assertEqual(row['pullups'][0]['ohms'], 4700)
            self.assertEqual(row['pullups'][0]['rail'], 'V3')
            self.assertFalse([g for g in row['gaps'] if 'inconsistent-index' in g])

    def test_missing_foreign_or_truncated_array_endpoint_remains_rejected(self):
        board = db(); original = intent(board)
        for bad in [[], [['RM1.1.1', 'U1.3']], [['RM1.1', 'RM1.1.2']]]:
            spec = copy.deepcopy(original); spec['i2c_topology']['components']['RM1']['links'] = bad
            self.assertTrue(validate_i2c_intent(spec, board), bad)

    def test_unfitted_or_unknown_array_is_not_inferred_to_supply_pullups(self):
        board = db(); original = intent(board)
        for population in [{'RM1': False, 'U1': True}, {'U1': True}]:
            spec = copy.deepcopy(original); spec['assemblies'][0]['population'] = population
            rows = build_i2c_topology(board, spec)['states'][0]['regions']
            self.assertTrue(all(not row['pullups'] for row in rows))

    def test_decoupling_does_not_invent_foreign_refs_from_array_pins(self):
        board = db()
        inventory = build_decoupling_inventory(board, None)
        self.assertFalse([g for g in inventory['discovery_gaps']
                          if ('invalid-physical-node' in g or 'inconsistent-index' in g) and 'RM1' in g])
        self.assertEqual(set(board['parts']), {'RM1', 'U1'})


if __name__ == '__main__':
    unittest.main()

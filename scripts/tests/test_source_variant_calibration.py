"""G2/G3/G7: current-source pin differences survive a working stale export.

Synthetic roles and pin numbers; no vendor exemption or electrical threshold.
Source: public BB-CH340T Rev.B calibration, current schematic vs older export.
These tests cover discovery/integrity, not the physical board's qualification.
"""
import contextlib
import io
import pathlib
import sys
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
# External frozen replay may pass an installed engine root explicitly.
if len(sys.argv) > 1 and sys.argv[1].startswith('--engine='):
    SCRIPTS = pathlib.Path(sys.argv.pop(1).split('=', 1)[1]) / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from board_intent import input_fingerprint
from plan_review import build_review_plan, validate_intent
from parse_kicad import parse
from parse_netlist import self_check


def fixture(current_bad=False):
    mode = '11' if current_bad else '12'
    names = {'U1.1': 'VCC', 'U1.2': 'GND', 'U1.' + mode: 'MODE',
             'U1.11': 'MODE' if current_bad else 'NC',
             'SJ1.1': '1', 'SJ1.2': '2', 'JP1.1': 'A', 'JP1.2': 'B', 'JP1.3': 'C'}
    db = {'parts': {'U1': {'value': 'BRIDGE-T', 'part': 'BRIDGE-T', 'nc': False},
                    'JP1': {'value': 'Jumper_3', 'part': 'Jumper_3', 'nc': False},
                    'SJ1': {'value': 'SolderJumper_2', 'part': 'SolderJumper_2', 'nc': False}},
          'nets': {'VBUS': ['U1.1', 'JP1.3'], 'GND': ['U1.2', 'SJ1.2'],
                   'MODE': ['U1.' + mode, 'SJ1.1'], 'INTERNAL_3V3': ['JP1.1'],
                   'HEADER_VDD': ['JP1.2']},
          'pinname': names, 'declared_pinname': names.copy(), 'pintype': {},
          'declared_pintype': {}, 'pseudo_nets': [], 'ref2page': {'U1': 1, 'JP1': 1}}
    db['pin2net'] = {n: net for net, nodes in db['nets'].items() for n in nodes}
    intent = {'schema_version': 3, 'input_sha256': input_fingerprint(db),
              'assemblies': [{'id': 'base', 'population': {'U1': True, 'JP1': True, 'SJ1': True},
                             'citation': 'synthetic controlled assembly'}],
              'devices': {'U1': {'mpn': 'BRIDGE-T', 'package': 'TEST',
                                'identity_citation': 'synthetic exact T variant BOM',
                                'citation': 'synthetic official full physical pin table',
                                'pinout_complete': True,
                                'pins': {'1': {'name': 'VCC', 'role': 'power'},
                                         '2': {'name': 'GND', 'role': 'return'},
                                         '11': {'name': 'NC', 'role': 'nc'},
                                         '12': {'name': 'MODE', 'role': 'other'}}}}}
    return db, intent


def check(db, intent, rule):
    return next(c for c in build_review_plan(db, intent)['checks']
                if c['id'] == rule + '.U1')


class SourceVariantCalibrationTests(unittest.TestCase):
    def test_current_bad_source_exposes_omitted_function_pin(self):
        db, intent = fixture(current_bad=True)
        self.assertEqual(check(db, intent, 'DEV-D02')['pin_difference'],
                         {'official_only': ['U1.12'], 'symbol_only': []})

    def test_current_source_nc_mapping_remains_a_disposition_object(self):
        db, intent = fixture(current_bad=True)
        self.assertIn('U1.11', check(db, intent, 'DEV-D05')['pin_disposition']['nc_connected'])

    def test_correct_export_does_not_disprove_different_current_source(self):
        old_db, old_intent = fixture()
        current_db, current_intent = fixture(current_bad=True)
        self.assertEqual(check(old_db, old_intent, 'DEV-D02')['pin_difference']['official_only'], [])
        self.assertEqual(check(current_db, current_intent, 'DEV-D02')['pin_difference']['official_only'], ['U1.12'])
        self.assertNotEqual(input_fingerprint(old_db), input_fingerprint(current_db))
        self.assertNotIn('review_result', check(current_db, current_intent, 'DEV-D02')['pin_difference'])

    def test_corrected_full_variant_keeps_nc_unconnected(self):
        db, intent = fixture()
        self.assertEqual(check(db, intent, 'DEV-D02')['pin_difference'],
                         {'official_only': [], 'symbol_only': []})
        self.assertEqual(check(db, intent, 'DEV-D05')['pin_disposition']['nc_connected'], [])
        self.assertIn('U1.11', check(db, intent, 'DEV-D05')['pin_disposition']['unconnected'])

    def test_old_pinout_context_cannot_be_reused_for_changed_source(self):
        old_db, old_intent = fixture()
        current_db, current_intent = fixture(current_bad=True)
        self.assertTrue(validate_intent(old_intent, current_db))
        self.assertEqual(validate_intent(current_intent, current_db), [])

    def test_success_exit_metadata_does_not_make_empty_export_valid(self):
        source = ('<export version="E"><design><source>legacy.sch</source>'
                               '<tool>successful export</tool></design><components/>'
                               '<libparts/><nets/></export>')
        # The import boundary now rejects the empty export before a DB exists.
        with self.assertRaisesRegex(ValueError, '空网表'):
            parse(source)
        # The downstream guard remains useful for other adapters.
        empty = {'pseudo_nets': [], 'parts': {}, 'nets': {}, 'pin2net': {}, 'pinname': {}, 'pintype': {}, 'ref2page': {}}
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as failure:
            self_check(empty)
        self.assertEqual(failure.exception.code, 2)


if __name__ == '__main__':
    unittest.main()

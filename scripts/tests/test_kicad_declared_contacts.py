"""Public frozen import boundary + adversarial synthetic declaration tests."""
import copy
import hashlib
import json
import pathlib
import sys
import unittest
import xml.etree.ElementTree as ET

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from parse_kicad import parse
from parse_netlist import self_check
from test_parse_kicad import board, comp, net, netlist

FIXTURE = pathlib.Path(__file__).parent / 'fixtures/public-jumper-import'


def jumper(symbol='SMD_JUMPER_3_PAD_TRACE', declared_types=('input',) * 3,
           native_types=('input',) * 3, names=('',) * 3, ref='JP1'):
    pins = ''.join('<pin num="%s" name="%s" type="%s"/>' % (i, name, kind)
                   for i, (name, kind) in enumerate(zip(names, declared_types), 1))
    library = '<libparts><libpart lib="Custom" part="%s"><pins>%s</pins></libpart></libparts>' % (symbol, pins)
    nodes = tuple((ref, str(i), '', kind) for i, kind in enumerate(native_types, 1))
    return parse(netlist(comp(ref, 'Custom', symbol, symbol),
                         net('SIG', *nodes), libparts=library))


class QualifiedIdentityTest(unittest.TestCase):
    def test_exact_qualified_identity_restores_declared_pin_names(self):
        xml = board().replace('lib="Regulator_Linear" part="LDO"/>',
                              'lib="" part="Regulator_Linear:LDO"/>')
        db = parse(xml)
        self.assertEqual(db['missing_primitives'], [])
        self.assertEqual(db['pinname']['U1.4'], 'EN')
        self.assertEqual(db['parts']['U1']['part'], 'SYN-LDO-3V3')
        self.assertEqual(db['export_meta']['libsource_normalizations']['U1']['original_lib'], '')

    def test_no_bare_name_guess_or_explicit_library_override(self):
        for before, after in [('lib="Device" part="R"/>', 'lib="" part="R"/>'),
                              ('lib="Device" part="R"/>', 'lib="Wrong" part="Device:R"/>')]:
            db = parse(board().replace(before, after))
            self.assertTrue(db['missing_primitives'])
            self.assertEqual(db['export_meta']['libsource_normalizations'], {})

    def test_literal_empty_library_identity_takes_priority(self):
        root = ET.fromstring(board())
        root.find('./components/comp/libsource').attrib.update(lib='', part='Regulator_Linear:LDO')
        item = ET.SubElement(root.find('./libparts'), 'libpart', lib='', part='Regulator_Linear:LDO')
        ET.SubElement(ET.SubElement(item, 'pins'), 'pin', num='4', name='LITERAL_EN', type='input')
        db = parse(ET.tostring(root, encoding='unicode'))
        self.assertEqual(db['export_meta']['libsource_normalizations'], {})
        self.assertEqual(db['declared_pinname']['U1.4'], 'LITERAL_EN')

    def test_conflicting_declarations_rejected_identical_ones_accepted(self):
        root = ET.fromstring(board())
        original = root.find('./libparts/libpart')
        root.find('./libparts').append(copy.deepcopy(original))
        self.assertTrue(parse(ET.tostring(root, encoding='unicode'))['parts'])
        root.findall('./libparts/libpart')[-1].find('./pins/pin').set('name', 'WRONG')
        with self.assertRaises(ValueError):
            parse(ET.tostring(root, encoding='unicode'))


class NumberedContactsTest(unittest.TestCase):
    def test_declared_anonymous_jumper_inputs_use_numbers_without_fake_names(self):
        db = jumper()
        self.assertTrue(self_check(db, strict=False))
        self.assertEqual(db['pin_name_coverage']['unnamed_jumper_contact_pins'], ['JP1.1', 'JP1.2', 'JP1.3'])
        self.assertEqual(db['pinname'], {})
        self.assertEqual(set(db['native_pintype'].values()), {'input'})

    def test_active_power_named_or_undeclared_contacts_stay_blocked(self):
        cases = [jumper(declared_types=('input', 'power_in', 'output')),
                 jumper(native_types=('input', 'power_in', 'output')),
                 jumper(names=('CONTROL', '', '')),
                 jumper(symbol='MYSTERY_IC', ref='U9'),
                 jumper(symbol='MYSTERY', ref='JP9'),
                 jumper(symbol='CRYSTAL_4_PAD', declared_types=('input',) * 4,
                        native_types=('input',) * 4, names=('',) * 4)]
        no_declaration = jumper()
        del no_declaration['declared_native_pintype']
        cases.append(no_declaration)
        for db in cases:
            with self.subTest(part=db['parts']):
                self.assertFalse(self_check(db, strict=False))
                self.assertEqual(db['pin_name_coverage']['unnamed_jumper_contact_pins'], [])

    def test_structural_faults_not_hidden_by_contact_scope(self):
        db = jumper()
        db['nets']['OTHER'] = ['JP1.1']
        self.assertFalse(self_check(db, strict=False))
        db = jumper()
        db['native_pintype']['JP1.1'] = 'future_type'
        self.assertFalse(self_check(db, strict=False))
        db = jumper()
        del db['native_pintype']['JP1.1']
        self.assertFalse(self_check(db, strict=False))


class FrozenPublicImportTest(unittest.TestCase):
    def test_frozen_graph_and_real_remaining_clock_gap(self):
        raw = (FIXTURE / 'board.xml').read_bytes()
        manifest = json.loads((FIXTURE / 'source.json').read_text())
        self.assertEqual(hashlib.sha256(raw).hexdigest(), manifest['fixture_xml_sha256'])
        db = parse(raw)
        self.assertEqual((len(db['parts']), len(db['pin2net']), len(db['nets'])), (59, 214, 66))
        self.assertEqual(sorted(db['export_meta']['libsource_normalizations']), ['R10', 'R7'])
        self.assertEqual(db['missing_primitives'], [])
        self.assertFalse(self_check(db, strict=False))
        self.assertEqual(db['pin_name_coverage']['missing_functional_pins'], ['X1.2', 'X1.3', 'X1.4'])
        self.assertEqual(len(db['pin_name_coverage']['unnamed_jumper_contact_pins']), 6)
        self.assertEqual(db['declared_native_pintype']['X1.3'], 'output')
        self.assertEqual(db['native_pintype']['X1.3'], 'output')
        self.assertEqual(db['native_pintype']['X1.2'], 'power_in')
        # Seeded electrical defects are retained, not converted into a golden board.
        self.assertEqual(db['nets']['/EN_3V3'], ['U3.4'])
        self.assertEqual(db['pin2net']['U1.5'], 'D-')
        self.assertEqual(db['pin2net']['U1.6'], 'D+')


if __name__ == '__main__':
    unittest.main()

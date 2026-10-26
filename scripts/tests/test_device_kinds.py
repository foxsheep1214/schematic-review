"""Item 6 of the 2026-10-26 SR review: one registry of device kinds (device_kinds.KINDS). The classifier's prefix and
keyword tables, the declarable kinds, the datasheet cues, the wearout classes and the protective parts are views of it:
a new kind is one row, never five lists (the ntc/varistor extension of the same day touched five modules).
"""
import re
import sys
import unittest
from collections import OrderedDict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import board_intent
import catalog
import circuit_candidates
import datasheet_kinds
import device_kinds
import part_words as pw


class RegistryTests(unittest.TestCase):
    def test_the_registry_passes_its_own_checks_and_names_every_constant(self):
        self.assertEqual(device_kinds.errors(), [])
        self.assertEqual(set(pw.KIND_CONSTANTS), set(device_kinds.KINDS))
        for name in ('resistor', 'capacitor', 'mosfet', 'ic', 'connector', 'ntc', 'varistor', 'unknown'):
            self.assertEqual(pw.KIND_CONSTANTS[name], name)

    def test_the_classifier_tables_are_views_of_the_registry(self):
        self.assertEqual(pw.PREFIX_KINDS, device_kinds.prefix_table())
        self.assertEqual(pw.KEYWORD_KINDS, device_kinds.keyword_table())
        self.assertEqual(dict(pw.PREFIX_KINDS)[r'^(TH|RT|NTC)\d'], pw.NTC)
        self.assertEqual([k for _, k in pw.KEYWORD_KINDS][:6], ['relay', 'varistor', 'ntc', 'opto', 'tvs', 'zener'])
        self.assertEqual(pw.KEYWORD_KINDS[-2:], ((device_kinds.USB_CONNECTOR_RE, 'connector'), (device_kinds.JST_CONNECTOR_RE, 'connector')))
        self.assertEqual((pw.NTC_RE.pattern, pw.VARISTOR_RE.pattern), (device_kinds.NTC_WORDS, device_kinds.VARISTOR_WORDS))
        self.assertEqual(pw.TWO_TERMINAL, set(device_kinds.with_flag('two_terminal')))
        self.assertEqual(pw.PASSIVE_LINKS, set(device_kinds.with_flag('passive_link')))
        self.assertTrue(pw.PASSIVE_LINKS < pw.TWO_TERMINAL)

    def test_declared_kinds_cues_wearout_and_protective_parts_read_the_registry(self):
        self.assertEqual(board_intent.DEVICE_KINDS, device_kinds.declarable() + board_intent.IC_KINDS)
        self.assertNotIn('testpoint', board_intent.DEVICE_KINDS)
        self.assertNotIn('unknown', board_intent.DEVICE_KINDS)
        self.assertEqual(dict(datasheet_kinds.KIND_CUES)['varistor'], device_kinds.KINDS['varistor'].cues)
        self.assertEqual(dict(datasheet_kinds.KIND_CUES)['load_switch'], catalog.DEVICE_ROLES['load_switch'].cues)
        self.assertEqual(device_kinds.wearout_of('relay'), 'RELAY')
        self.assertIsNone(device_kinds.wearout_of('ntc'))       # INRUSH_NTC only in the power path: the circuit decides
        self.assertIsNone(device_kinds.wearout_of('nothing'))
        self.assertEqual(circuit_candidates.PROTECTIVE_KINDS, frozenset({'fuse', 'tvs', 'bridge_rectifier', 'ntc', 'varistor'}))

    def test_a_new_kind_is_one_row(self):
        kinds = OrderedDict(device_kinds.KINDS)
        kinds['gdt'] = device_kinds.DeviceKind('气体放电管', (r'^GDT\d',), (r'\bGDT\b|气体放电管',), ('gasdischargetube',),
                                               two_terminal=True, protective=True)
        self.assertEqual(device_kinds.errors(kinds), [])
        self.assertIn((r'^GDT\d', 'gdt'), device_kinds.prefix_table(kinds))
        self.assertIn((r'\bGDT\b|气体放电管', 'gdt'), device_kinds.keyword_table(kinds))
        self.assertEqual(dict(device_kinds.cue_table(kinds))['gdt'], ('gasdischargetube',))
        self.assertIn('gdt', device_kinds.declarable(kinds))
        self.assertIn('gdt', device_kinds.with_flag('protective', kinds))
        self.assertIn('gdt', device_kinds.with_flag('two_terminal', kinds))

    def test_the_self_check_names_a_bad_row(self):
        kinds = OrderedDict(device_kinds.KINDS)
        kinds['bad'] = device_kinds.DeviceKind('坏行', ('BAD',), (r'[',), ('Gas Tube',), passive_link=True, wearout='NOPE')
        found = device_kinds.errors(kinds)
        for word in ('anchored', 'does not compile', 'spaces removed', 'WEAROUT_CLASSES', 'two-terminal'):
            self.assertTrue(any('bad' in e and word in e for e in found), (word, found))
        kinds = OrderedDict(device_kinds.KINDS)
        kinds['regulator'] = device_kinds.DeviceKind('稳压器')
        self.assertTrue(any('IC role' in e for e in device_kinds.errors(kinds)))


class ClassifierUnchangedTests(unittest.TestCase):
    """The views keep the classifier's answers (the ntc/varistor, kind and interface tests cover the rest)."""

    def test_prefix_keyword_and_declared_answers(self):
        two = [('1', '1'), ('2', '2')]
        self.assertEqual(pw.classify('R12', {'value': '10k'}, 2, two), (pw.RESISTOR, 'refdes-prefix'))
        self.assertEqual(pw.classify('K2', {'value': 'RELAY G5V'}, 4, [(str(i), str(i)) for i in range(1, 5)]), (pw.RELAY, 'part-keyword'))
        self.assertEqual(pw.classify('Q7', {'prim': 'Transistor_FET:IRF540'}, 3, [('G', '1'), ('D', '2'), ('S', '3')]), (pw.MOSFET, 'part-keyword'))
        self.assertEqual(pw.classify('Q7', {'value': 'BC847 IRF'}, 3, [('B', '1'), ('C', '2'), ('E', '3')])[0], pw.UNKNOWN)
        self.assertEqual(pw.classify('J3', {'prim': 'Connector:Conn_01x04'}, 4, [(str(i), str(i)) for i in range(1, 5)])[0], pw.CONNECTOR)
        self.assertEqual(pw.classify('U9', {'prim': 'Connector_USB:USB_Micro-B', 'part': 'Micro-B_USB'}, 5, [])[0], pw.CONNECTOR)
        self.assertEqual(pw.classify('U9', {'value': 'JST-PH module'}, 8, [])[0], pw.IC)
        self.assertEqual(pw.classify('BT1', {'value': 'CR2032'}, 2, two), (pw.BATTERY, 'part-keyword' if re.search(r'BATTERY', 'CR2032', re.I) else 'refdes-prefix'))
        self.assertEqual(pw.classify('X1', {'value': 'x'}, 2, two, declared='zener'), (pw.ZENER, 'datasheet'))


if __name__ == '__main__':
    unittest.main()

"""What settles a part's kind (decisions 2026-10-27, docs/2026-10-26-part-kind-evidence.md).

A1/A1b: twelve kinds, every IC role and every multi-winding magnetic need a verified datasheet declaration; magnetics
are told apart by what they do (common-mode choke, coupled inductor, transformer). A2/A3: the classifier's final kind
pulls a part in, never the refdes alone. A4: relay/fuse/pptc and the magnetics' cues, fuse read as a word, two
suppressions. A5: a part the classifier cannot read on two or more nets is placed by the reviewer. B1: part words are a
guess for those kinds. B3: the datasheet beats part words, not pin names. C1–C3: the datasheet title is compared with the
classifier's guess (a hint) and with a verified declaration (a mismatch needs a reason that is not the part's make-up).
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import board_intent
import catalog
import datasheet_kinds as dk
import device_kinds
import part_words as pw
from checkers import netgraph as ng
from plan_review import build_review_plan
from validate_review import extension_signals
import test_inductive_load as fixture

MUST_DECLARE = ('mosfet', 'bjt', 'diode', 'tvs', 'zener', 'bridge_rectifier', 'opto', 'relay', 'transformer', 'fuse',
                'ntc', 'varistor', 'common_mode_choke', 'coupled_inductor')


def board():
    db = {'nets': {}, 'parts': {}, 'pin2net': {}, 'pinname': {}, 'pintype': {}, 'pseudo_nets': [], 'ref2page': {}}
    fixture.add(db, 'F1', '1206FUSE-500mA', [('1', '1', 'VIN'), ('2', '2', 'VFUSED')])
    fixture.add(db, 'BZ1', 'HX-77', [('1', 'A', 'VFUSED'), ('2', 'B', 'GND'), ('3', 'C', 'SENSE')])
    fixture.add(db, 'U4', 'Connector:USB_C_Receptacle', [('A4', 'VBUS', 'VIN'), ('A1', 'GND', 'GND')])
    fixture.add(db, 'R1', '10k', [('1', '1', 'SENSE'), ('2', '2', 'GND')])
    db['parts']['F1']['footprint'] = 'Fuse:Fuse_1206_3216Metric'
    return db


def plan_row(db, ref, intent=None, audit=None):
    plan = build_review_plan(db, intent, datasheet_audit=audit)
    return next((x for x in plan['checks'] if x['id'] == 'DEV-D02.' + ref), None)


def kind_gaps(row, ref):
    return [g for g in row['required_inputs'] if g.startswith('intent.device_kinds.' + ref + ':')]


class RegistryTests(unittest.TestCase):
    def test_the_must_declare_set_is_twelve_kinds_the_magnetics_and_the_ic_roles(self):
        self.assertEqual({k for k in device_kinds.KINDS if device_kinds.needs_datasheet(k, 2)} - {'ic'}, set(MUST_DECLARE))
        self.assertTrue(all(device_kinds.needs_datasheet(role) for role in catalog.DEVICE_ROLES))
        for kind in ('resistor', 'capacitor', 'connector', 'jumper', 'switch', 'crystal', 'testpoint'):
            self.assertFalse(device_kinds.needs_datasheet(kind, 2), kind)

    def test_a_winding_with_three_or_more_pins_needs_its_datasheet(self):
        self.assertFalse(device_kinds.needs_datasheet('inductor', 2))
        self.assertTrue(device_kinds.needs_datasheet('inductor', 4))
        self.assertTrue(device_kinds.needs_datasheet('ferrite', 3))

    def test_settlement_by_kind_and_nets(self):
        self.assertEqual(device_kinds.settlement('fuse', 2, 2), 'datasheet')
        self.assertEqual(device_kinds.settlement('unknown', 3, 2), 'classify')
        self.assertIsNone(device_kinds.settlement('unknown', 1, 1))
        self.assertIsNone(device_kinds.settlement('resistor', 2, 2))

    def test_a_datasheet_kind_without_cues_is_a_registry_error(self):
        self.assertEqual(device_kinds.errors(), [])
        kinds = dict(device_kinds.KINDS, relay=device_kinds.KINDS['relay']._replace(cues=()))
        self.assertTrue(any(e.startswith('relay: a datasheet kind needs cues') for e in device_kinds.errors(kinds)))

    def test_magnetics_by_function(self):
        self.assertEqual(pw.classify('L1', {'part': 'Common Mode Choke 90R'}, 4)[0], pw.COMMON_MODE_CHOKE)
        self.assertEqual(pw.classify('L2', {'part': 'Coupled Inductor 2x10uH'}, 4)[0], pw.COUPLED_INDUCTOR)
        self.assertEqual(pw.classify('L3', {'part': '10uH'}, 2)[0], pw.INDUCTOR)


class CueTests(unittest.TestCase):
    def test_relay_fuse_and_magnetics_cues(self):
        self.assertEqual(dk.cues('Miniature Power Relay'), {'relay'})
        self.assertEqual(dk.cues('Surface Mount Fuses'), {'fuse'})
        self.assertEqual(dk.cues('PPTC resettable device'), {'fuse'})
        self.assertEqual(dk.cues('SMD Common Mode Filter'), {'common_mode_choke'})
        self.assertEqual(dk.cues('Coupled Inductor'), {'coupled_inductor'})

    def test_fuse_is_read_as_a_word(self):
        self.assertEqual(dk.cues('Littelfuse Inc. surface mount'), set())

    def test_an_ic_role_or_a_thermistor_suppresses_its_load(self):
        self.assertEqual(dk.cues('2.7 V to 19 V Industrial eFuse'), {'load_switch'})
        self.assertNotIn('relay', dk.cues('Relay driver with integrated flyback diodes'))
        self.assertEqual(dk.cues('NTC thermistors ThermoFuse'), {'ntc'})


def reader(pages):
    return lambda path, page: pages.get(page)


EFUSE = {1: 'XEF-1\n2.7 V to 19 V Industrial eFuse\n1 Features\nAdjustable current limit\nOvervoltage protection\n'
            'Reverse current blocking\n2 Applications\nServers',
         2: 'The device integrates a 30 mOhm N-channel MOSFET.'}


class TitleTests(unittest.TestCase):
    def test_the_title_area_first_then_page_one(self):
        self.assertTrue(dk.title_text('x.pdf', reader(EFUSE)).startswith('XEF-1 2.7 V to 19 V Industrial eFuse'))
        late = {1: 'XQ-2\nRev B\nPage 1\nOrdering\nPackage\nMarking\nLater: Dual N-channel MOSFET'}
        self.assertIn('MOSFET', dk.title_text('x.pdf', reader(late)))
        self.assertEqual(dk.title_text('x.pdf', reader({2: 'Optocoupler'})), '')

    def test_the_classifier_against_the_title_is_a_hint(self):
        conflict = dk.kind_conflict('opto', 'x.pdf', reader(EFUSE))
        self.assertEqual((conflict['code'], conflict['classifier_kind'], conflict['title_kinds']),
                         ('KIND_CONFLICT', 'opto', ['load_switch']))
        self.assertIsNone(dk.kind_conflict('load_switch', 'x.pdf', reader(EFUSE)))
        self.assertIsNone(dk.kind_conflict('ic', 'x.pdf', reader(EFUSE)))

    def test_a_declaration_the_title_contradicts_needs_a_reason_not_its_make_up(self):
        mosfet = {'kind': 'mosfet', 'page': 2, 'quote': 'N-channel MOSFET'}
        self.assertEqual(dk.verify(mosfet, 'x.pdf', reader(EFUSE))['status'], 'TITLE_MISMATCH')
        made_of = dict(mosfet, kind_reason='the part has an internal N-channel MOSFET')
        self.assertEqual(dk.verify(made_of, 'x.pdf', reader(EFUSE))['status'], 'TITLE_MISMATCH')
        made_of_zh = dict(mosfet, kind_reason='内部集成 MOSFET')
        self.assertEqual(dk.verify(made_of_zh, 'x.pdf', reader(EFUSE))['status'], 'TITLE_MISMATCH')
        reason = dict(mosfet, kind_reason='combined datasheet; the title names the sibling part of the series')
        result = dk.verify(reason, 'x.pdf', reader(EFUSE))
        self.assertEqual((result['status'], result['title_mismatch']['title_kinds']), ('VERIFIED', ['load_switch']))
        title = {'kind': 'load_switch', 'page': 1, 'quote': 'Industrial eFuse'}
        self.assertEqual(dk.verify(title, 'x.pdf', reader(EFUSE))['status'], 'VERIFIED')


class AuditTests(unittest.TestCase):
    def audit(self, declared, heuristic):
        bound = [ref for ref in heuristic if ref != 'R1']   # a resistor bound to an eFuse datasheet would conflict too
        orig = dk.page_text
        dk.page_text = reader(EFUSE)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'x.pdf')
            Path(path).write_bytes(b'%PDF-1.4 synthetic')      # hashed when a declaration verifies
            materials = [{'status': 'AVAILABLE', 'refdes': bound, 'document': {'path': path}}]
            try:
                return dk.audit_kinds(materials, declared, heuristic), dk.kind_conflicts(materials, heuristic)
            finally:
                dk.page_text = orig

    def test_statuses_by_settlement(self):
        heuristic = {'U9': {'kind': 'opto', 'basis': 'part-keyword', 'settlement': 'datasheet'},
                     'BZ1': {'kind': 'unknown', 'basis': 'no classification evidence', 'settlement': 'classify'},
                     'R1': {'kind': 'resistor', 'basis': 'refdes-prefix', 'settlement': None}}
        section, conflicts = self.audit({}, heuristic)
        self.assertEqual({ref: e['status'] for ref, e in section.items()}, {'U9': 'UNDECLARED', 'BZ1': 'UNCLASSIFIED'})
        self.assertEqual(section['U9']['kind_conflict']['title_kinds'], ['load_switch'])
        self.assertEqual(list(conflicts), ['U9'])
        section, _ = self.audit({'BZ1': {'kind': 'jumper', 'reason': 'solder bridge between two pads'}}, heuristic)
        self.assertEqual(section['BZ1'], {'status': 'CLASSIFIED', 'kind': 'jumper', 'reason': 'solder bridge between two pads'})

    def test_the_datasheet_beats_part_words_and_says_so(self):
        heuristic = {'U9': {'kind': 'opto', 'basis': 'part-keyword', 'settlement': 'datasheet'}}
        declared = {'U9': {'kind': 'load_switch', 'page': 1, 'quote': 'Industrial eFuse'}}
        section, _ = self.audit(declared, heuristic)
        self.assertEqual((section['U9']['status'], section['U9']['keyword_conflict']), ('VERIFIED', {'keyword_kind': 'opto'}))
        signals = extension_signals({}, {'parts': {'U9': {'part': 'X'}}}, {'device_kinds': section})
        self.assertEqual([(s['kind'], s['refs']) for s in signals], [('KEYWORD_KIND_CONFLICT', ['U9'])])
        heuristic['U9']['basis'] = 'refdes-prefix'
        section, _ = self.audit(declared, heuristic)
        self.assertNotIn('keyword_conflict', section['U9'])


class ClassifierTests(unittest.TestCase):
    def test_pin_names_still_veto_a_declaration_but_part_words_do_not(self):
        pins = [('G', '1'), ('D', '2'), ('S', '3')]
        self.assertEqual(pw.classify('Q1', {'part': 'MMBT3904'}, 3, pins, declared='mosfet'), ('mosfet', 'datasheet'))
        self.assertEqual(pw.classify('Q1', {'part': 'X'}, 3, [('B', '1'), ('C', '2'), ('E', '3')], declared='mosfet')[0],
                         pw.UNKNOWN)

    def test_part_words_are_a_guess_for_a_datasheet_kind(self):
        db = {'nets': {}, 'parts': {}, 'pin2net': {}, 'pinname': {}, 'pseudo_nets': []}
        fixture.add(db, 'D9', 'SS14', [('1', 'K', 'VOUT'), ('2', 'A', 'SW')])
        fixture.add(db, 'L9', 'INDUCTOR 10uH', [('1', '1', 'VOUT'), ('2', '2', 'SW')])
        graph = ng.NetGraph(db)
        self.assertEqual((graph.basis('D9'), pw.kind_gap(graph, 'D9')), ('part-keyword', 'datasheet-kind:D9'))
        self.assertIsNone(pw.kind_gap(graph, 'L9'))             # a single winding needs no datasheet


class PlannerTests(unittest.TestCase):
    def test_the_final_kind_not_the_refdes_asks_for_a_declaration(self):
        db = board()
        self.assertEqual(len(kind_gaps(plan_row(db, 'F1'), 'F1')), 1)       # a fuse, two-terminal package or not
        self.assertEqual(kind_gaps(plan_row(db, 'U4'), 'U4'), [])            # a U-numbered USB-C receptacle
        self.assertIsNone(plan_row(db, 'R1'))

    def test_a_part_the_classifier_cannot_read_is_placed_by_the_reviewer(self):
        db = board()
        [gap] = kind_gaps(plan_row(db, 'BZ1'), 'BZ1')
        self.assertIn('cannot read', gap)
        intent = {'schema_version': 4, 'input_sha256': board_intent.input_fingerprint(db),
                  'device_kinds': {'BZ1': {'kind': 'other', 'reason': 'piezo buzzer; the BOM line says so'}}}
        self.assertEqual(board_intent.device_kind_errors(intent['device_kinds'], db), [])
        self.assertEqual(kind_gaps(plan_row(db, 'BZ1', intent), 'BZ1'), [])

    def test_the_title_conflict_is_written_into_the_gap(self):
        db = board()
        audit = {'device_kinds': {'F1': {'status': 'UNDECLARED', 'kind_conflict': {
            'code': 'KIND_CONFLICT', 'classifier_kind': 'fuse', 'title_kinds': ['load_switch'], 'title': 'Industrial eFuse'}}}}
        [gap] = kind_gaps(plan_row(db, 'F1', None, audit), 'F1')
        self.assertIn('KIND_CONFLICT: classifier fuse, datasheet title load_switch', gap)


class IntentFormTests(unittest.TestCase):
    def test_a_reason_places_only_an_unreadable_part_in_a_kind_without_a_datasheet(self):
        db = board()
        errors = board_intent.device_kind_errors
        self.assertTrue(any('needs no datasheet' in e for e in errors({'BZ1': {'kind': 'mosfet', 'reason': 'looks like one'}}, db)))
        self.assertTrue(any('cannot read' in e for e in errors({'R1': {'kind': 'jumper', 'reason': '0R link'}}, db)))
        self.assertTrue(any('multi-winding' in e for e in errors({'BZ1': {'kind': 'inductor', 'reason': 'three-pin choke'}}, db)))
        self.assertTrue(any('reason must say' in e for e in errors({'BZ1': {'kind': 'jumper', 'reason': ' '}}, db)))

    def test_kind_reason_is_optional_but_not_empty(self):
        db = board()
        declaration = {'kind': 'fuse', 'page': 1, 'quote': 'Surface Mount Fuses'}
        self.assertEqual(board_intent.device_kind_errors({'F1': declaration}, db), [])
        self.assertEqual(board_intent.device_kind_errors({'F1': dict(declaration, kind_reason='combined datasheet')}, db), [])
        self.assertTrue(board_intent.device_kind_errors({'F1': dict(declaration, kind_reason='')}, db))


if __name__ == '__main__':
    unittest.main()

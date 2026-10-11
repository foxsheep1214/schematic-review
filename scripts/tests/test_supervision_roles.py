"""RST-A05/A06 physical roles, direction evidence, and attributed native train fixture."""
import copy
import hashlib
import json
import pathlib
import sys
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from checkers.supervision import build_inventory
from parse_kicad import parse
from test_supervision import findings, supervised_board, supervisors_of

FIXTURE = pathlib.Path(__file__).parent / 'fixtures' / 'openair-supervision'
TYPE_FIELDS = ('pintype', 'native_pintype', 'declared_pintype', 'declared_native_pintype')


def native_board():
    return parse((FIXTURE / 'native-mini.xml').read_text())


def isolate(db, node):
    old = db['pin2net'][node]
    db['nets'][old].remove(node)
    net = 'TEST_ISOLATED_' + node
    db['pin2net'][node] = net
    db['nets'][net] = [node]


def rules(db):
    return [f['rule'] for f in findings(db) if f['rule'] in ('RST-A05', 'RST-A06')]


class ResetDirectionTest(unittest.TestCase):
    def test_receiver_direction_matrix(self):
        accepted = ('IN', 'INPUT', 'BI', 'BIDI', 'BIDIR', 'IO', 'I/O', 'bidirectional')
        rejected = ('OUT', 'OUTPUT', 'OCL', 'open_collector', 'OCA', 'TRISTATE',
                    'tri_state', '3STATE', 'UNSPEC', 'UNKNOWN', 'POWER', 'NC', '', None)
        for value in accepted + rejected:
            with self.subTest(value=value):
                db = supervised_board()
                if value is None:
                    db['pintype'].pop('U4.2')
                else:
                    db['pintype']['U4.2'] = value
                self.assertEqual(rules(db), [] if value in accepted else ['RST-A06'])

    def test_each_native_or_normalized_field_can_prove_known_direction(self):
        for field in TYPE_FIELDS:
            with self.subTest(field=field):
                db = supervised_board()
                db['pintype'].pop('U4.2')
                db.setdefault(field, {})['U4.2'] = 'input' if 'native' in field else 'IN'
                self.assertEqual(rules(db), [])

    def test_conflicting_or_unknown_metadata_cannot_clear_reset_gap(self):
        for field in TYPE_FIELDS:
            for value in ('output', 'open_collector', 'tri_state', 'bidirectional', 'unknown', ''):
                with self.subTest(field=field, value=value):
                    db = supervised_board()
                    # A separately provided IN claim cannot override another role.
                    db['native_pintype'] = {'U4.2': 'input'}
                    db.setdefault(field, {})['U4.2'] = value
                    self.assertEqual(rules(db), ['RST-A06'])

    def test_overbar_reset_name_is_accepted_with_direction(self):
        db = supervised_board()
        db['pinname']['U4.2'] = '~{RST}'
        self.assertEqual(rules(db), [])
        db['pintype']['U4.2'] = 'OUT'
        self.assertEqual(rules(db), ['RST-A06'])

    def test_dnp_or_no_connect_receiver_does_not_clear_gap(self):
        db = supervised_board()
        db['parts']['U4']['nc'] = True
        self.assertEqual(rules(db), ['RST-A06'])
        db = supervised_board()
        db['no_connect_nodes'] = ['U4.2']
        self.assertEqual(rules(db), ['RST-A06'])


class PhysicalModelTest(unittest.TestCase):
    def test_native_provenance_and_size(self):
        provenance = json.loads((FIXTURE / 'provenance.json').read_text())
        self.assertEqual(provenance['commit'], '999e77c939f75e3b221c081043ae044904f089cd')
        self.assertEqual(provenance['license'], 'CC BY-SA 4.0')
        self.assertEqual(provenance['fixture_sha256'],
                         hashlib.sha256((FIXTURE / 'native-mini.xml').read_bytes()).hexdigest())
        self.assertLess(sum(p.stat().st_size for p in FIXTURE.iterdir()), 200_000)

    def test_native_normal_and_isolated_physical_pins(self):
        db = native_board()
        item = supervisors_of(build_inventory(db))['U1']
        self.assertEqual(item['watchdog_inputs'][0]['state'], 'driven')
        self.assertEqual(item['reset_outputs'][0]['node'], 'U1.6')
        self.assertEqual(item['reset_outputs'][0]['destinations'],
                         [{'node': 'U2.8', 'role': 'reset-input'}])
        self.assertEqual(rules(db), [])
        watchdog = copy.deepcopy(db)
        isolate(watchdog, 'U1.4')
        self.assertEqual(rules(watchdog), ['RST-A05'])
        reset = copy.deepcopy(db)
        isolate(reset, 'U1.6')
        self.assertEqual(rules(reset), ['RST-A06'])

    def test_ordinary_done_or_enable_is_not_model_specific(self):
        for ref, model in (('U1', 'MCU'), ('U1', 'LDO'), ('U2', 'MCU'), ('U2', 'LDO')):
            with self.subTest(ref=ref, model=model):
                db = native_board()
                for key in ('part', 'prim', 'value'):
                    db['parts'][ref][key] = model
                if ref == 'U1':
                    self.assertNotIn('U1', supervisors_of(build_inventory(db)))
                else:
                    self.assertEqual(rules(db), ['RST-A06'])

    def test_identity_conflicts_and_inexact_models_are_not_promoted(self):
        for ref, wrong in (('U1', 'TPL5010_FAKE'), ('U2', 'ESP32-C3-MINI-1-N4_FAKE')):
            for field in ('part', 'prim', 'value'):
                with self.subTest(ref=ref, field=field):
                    db = native_board()
                    db['parts'][ref][field] = wrong
                    if ref == 'U1':
                        self.assertNotIn(ref, supervisors_of(build_inventory(db)))
                    else:
                        self.assertEqual(rules(db), ['RST-A06'])
        db = native_board()
        for field in ('part', 'prim', 'value'):
            db['parts']['U1'][field] = 'MCU'
        db['parts']['U1']['jedec'] = 'TPL5010'
        db['parts']['U1']['datasheet'] = 'https://www.ti.com/lit/ds/symlink/tpl5010.pdf'
        self.assertNotIn('U1', supervisors_of(build_inventory(db)))

    def test_model_physical_names_and_numbers_must_agree(self):
        for node, wrong_name in (('U1.4', 'GPIO'), ('U1.6', 'GPIO'), ('U2.8', 'GPIO')):
            for field in ('pinname', 'declared_pinname'):
                with self.subTest(node=node, field=field):
                    db = native_board()
                    db[field][node] = wrong_name
                    if node.startswith('U1'):
                        self.assertNotIn('U1', supervisors_of(build_inventory(db)))
                    else:
                        self.assertEqual(rules(db), ['RST-A06'])
        for ref, wrong_number in (('U1', '40'), ('U2', '80')):
            with self.subTest(ref=ref):
                db = native_board()
                node = ref + ('.4' if ref == 'U1' else '.8')
                replacement = ref + '.' + wrong_number
                for field in ('pin2net', 'pinname') + TYPE_FIELDS + ('declared_pinname',):
                    if node in db.get(field, {}):
                        db[field][replacement] = db[field].pop(node)
                db['nets'][db['pin2net'][replacement]] = [replacement if n == node else n
                                                        for n in db['nets'][db['pin2net'][replacement]]]
                if ref == 'U1':
                    self.assertNotIn('U1', supervisors_of(build_inventory(db)))
                else:
                    self.assertEqual(rules(db), ['RST-A06'])

    def test_model_pin_direction_missing_conflicting_or_wrong(self):
        for node in ('U1.4', 'U1.6', 'U2.8'):
            for value in (('UNKNOWN', None, 'TRISTATE', 'BI', 'IN') if node == 'U1.6'
                          else ('UNKNOWN', None, 'TRISTATE', 'BI', 'OUT', 'OUTPUT', 'OCL')):
                with self.subTest(node=node, value=value):
                    db = native_board()
                    for field in TYPE_FIELDS:
                        db[field].pop(node, None)
                    if value is not None:
                        db['pintype'][node] = value
                    if node.startswith('U1'):
                        self.assertNotIn('U1', supervisors_of(build_inventory(db)))
                    else:
                        self.assertEqual(rules(db), ['RST-A06'])
            db = native_board()
            db['pintype'][node] = 'OUT' if node != 'U1.6' else 'IN'
            if node.startswith('U1'):
                self.assertNotIn('U1', supervisors_of(build_inventory(db)))
            else:
                self.assertEqual(rules(db), ['RST-A06'])

    def test_dnp_model_parts_do_not_supply_roles(self):
        for ref in ('U1', 'U2'):
            db = native_board()
            db['parts'][ref]['nc'] = True
            if ref == 'U1':
                self.assertNotIn('U1', supervisors_of(build_inventory(db)))
            else:
                self.assertEqual(rules(db), ['RST-A05', 'RST-A06'])


if __name__ == '__main__':
    unittest.main()

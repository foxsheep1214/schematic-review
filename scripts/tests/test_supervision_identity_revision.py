"""audit-01 closure: installed identity cannot be inferred from symbol hints."""
import hashlib
import json
import unittest

from test_supervision_roles import FIXTURE, native_board, rules
from test_supervision import supervisors_of
from checkers.supervision import build_inventory


class InstalledModelIdentityTest(unittest.TestCase):
    def assert_qualified(self, db, ref, qualified):
        items = supervisors_of(build_inventory(db))
        if ref == 'U1':
            self.assertEqual('U1' in items, qualified)
        else:
            destinations = items['U1']['reset_outputs'][0]['destinations']
            self.assertEqual(any(d['node'] == 'U2.8' and d['role'] == 'reset-input'
                                 for d in destinations), qualified)

    def test_frozen_real_audit_counterexamples(self):
        provenance = json.loads((FIXTURE / 'provenance.json').read_text())
        for ref in ('U1', 'U2'):
            with self.subTest(ref=ref):
                name = 'prim-only-' + ref + '.json'
                data = (FIXTURE / name).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(),
                                 provenance['independent_identity_counterexamples'][name]['sha256'])
                db = json.loads(data)
                self.assertTrue(db['parts'][ref]['prim'])
                self.assertEqual(db['parts'][ref]['part'], '')
                self.assertEqual(db['parts'][ref]['value'], '')
                self.assert_qualified(db, ref, False)
                self.assertEqual(rules(db), [] if ref == 'U1' else ['RST-A06'])

    def test_part_value_prim_presence_combinations(self):
        for ref in ('U1', 'U2'):
            for mask in range(8):
                with self.subTest(ref=ref, mask=mask):
                    db = native_board()
                    for index, field in enumerate(('part', 'value', 'prim')):
                        if not mask & (1 << index):
                            db['parts'][ref][field] = ''
                    # Both actual fields are required; the library field is optional.
                    self.assert_qualified(db, ref, (mask & 3) == 3)

    def test_installed_identity_missing_or_blank_cannot_be_completed(self):
        for ref in ('U1', 'U2'):
            for field in ('part', 'value'):
                for value in ('', ' \t ', None, 'ABSENT'):
                    with self.subTest(ref=ref, field=field, value=value):
                        db = native_board()
                        if value == 'ABSENT':
                            db['parts'][ref].pop(field)
                        else:
                            db['parts'][ref][field] = value
                        self.assert_qualified(db, ref, False)

    def test_equivalent_correct_installed_identity(self):
        for ref in ('U1', 'U2'):
            source = native_board()['parts'][ref]
            model = source['part']
            cases = (
                {'part': '  ' + model.lower() + ' ', 'value': '\t' + model.lower(),
                 'prim': ' library:' + model.lower() + ' '},
                {'part': 'Library:' + model, 'value': model, 'prim': source['prim']},
                {'part': model, 'value': 'Library:' + model, 'prim': source['prim']},
                {'part': model, 'value': model, 'prim': ''},
                {'part': model, 'value': model, 'prim': ' \t '},
                {'part': model, 'value': model, 'prim': None},
                {'part': model, 'value': model},
            )
            for index, identity in enumerate(cases):
                with self.subTest(ref=ref, case=index):
                    db = native_board()
                    for field in ('part', 'value', 'prim'):
                        db['parts'][ref].pop(field, None)
                    db['parts'][ref].update(identity)
                    self.assert_qualified(db, ref, True)

    def test_present_identity_conflict_and_invalid_namespaces(self):
        for ref in ('U1', 'U2'):
            for field in ('part', 'value', 'prim'):
                with self.subTest(ref=ref, field=field):
                    db = native_board()
                    db['parts'][ref][field] = 'OTHER_MPN'
                    self.assert_qualified(db, ref, False)
            for identity in (':' + native_board()['parts'][ref]['part'],
                             'a:b:' + native_board()['parts'][ref]['part']):
                with self.subTest(ref=ref, identity=identity):
                    db = native_board()
                    db['parts'][ref]['part'] = identity
                    self.assert_qualified(db, ref, False)


if __name__ == '__main__':
    unittest.main()

"""Original synthetic native XML and independent ledger boundary tests."""
import copy
import json
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from electrical_contract import db_fingerprint
from page_inventory import inventory, NATIVE, LIMITED
from parse_kicad import parse
from parse_netlist import self_check
from plan_review import build_review_plan
from test_validate_review import fixture, planned, E
from validate_review import fingerprint
from ledger_v3 import validate_review

XML = (Path(__file__).parent / 'fixtures/page_inventory/empty-root.xml').read_text()


def mutate(change):
    root = ET.fromstring(XML)
    change(root)
    return ET.tostring(root, encoding='unicode')


def ledger():
    p, r, db = fixture()
    db['ref2page'] = {'R1': 42}
    db['page_inventory'] = parse(XML)['page_inventory']
    p['page_inventory'] = inventory(db)
    for row in p['page_inventory']['pages']:
        key = 'DOC-V01.' + str(row['page'])
        item = planned(key)
        item['object'] = {'page': row['page'], 'sheet_path': row['sheet_path']}
        p['checks'].append(item)
        r['checks'].append({'id': key, 'applicability': 'APPLICABLE', 'review_result': 'PASS',
            'evidence_confidence': 'A', 'evidence': E, 'rationale': 'Synthetic page independently viewed',
            'blocking': False, 'handoff': {'required': False}})
    r['coverage']['pages'] = {str(x['page']): ['DOC-V01.' + str(x['page'])] for x in p['page_inventory']['pages']}
    return bind(p, r, db)


def bind(p, r, db):
    r['plan_digest'], r['db_digest'] = fingerprint(p), fingerprint(db)
    return p, r, db


class NativePageInventoryTests(unittest.TestCase):
    def test_empty_root_and_noncontinuous_identifiers_survive(self):
        db = parse(XML)
        self.assertTrue(self_check(db, strict=False))
        self.assertEqual([x['page'] for x in db['page_inventory']['pages']], [7, 42, 99])
        self.assertEqual(db['ref2page'], {'R1': 42, 'R2': 99})
        self.assertNotIn('/Other/', [x['sheet_path'] for x in db['page_inventory']['pages']])
        p = build_review_plan(db, intent={'materials': {'schematic_pdf': 'synthetic.pdf'}})
        docs = [x for x in p['checks'] if x['rule'] == 'DOC-V01']
        self.assertEqual([x['id'] for x in docs], ['DOC-V01.42', 'DOC-V01.7', 'DOC-V01.99'])
        root = next(x for x in docs if x['object']['page'] == 7)
        self.assertEqual(root['object'], {'page': 7, 'sheet_path': '/'})
        self.assertEqual(root['method'], 'V')
        self.assertEqual(set(db['parts']), {'R1', 'R2'})
        self.assertFalse(any(x['method'] == 'E' and x['object'].get('page') == 7 for x in p['checks']))

    def test_missing_metadata_has_explicit_limited_scope_and_no_guessed_pages(self):
        def remove(root):
            for sheet in root.findall('./design/sheet'):
                root.find('design').remove(sheet)
        db = parse(mutate(remove))
        self.assertEqual(db['page_inventory']['scope'], LIMITED)
        self.assertEqual(db['page_inventory']['pages'], [])
        self.assertEqual(db['ref2page'], {})
        p = build_review_plan(db)
        self.assertFalse(any(x['rule'] == 'DOC-V01' for x in p['checks']))
        self.assertTrue(any(x['code'] == 'LIMITED_PAGE_INVENTORY' for x in p['diagnostics']))

    def test_legacy_fallback_only_observes_known_component_pages(self):
        db = parse(XML)
        del db['page_inventory']
        p = build_review_plan(db)
        self.assertEqual(p['page_inventory']['scope'], LIMITED)
        self.assertEqual({x['object']['page'] for x in p['checks'] if x['rule'] == 'DOC-V01'}, {42, 99})

    def test_ambiguous_native_declarations_are_rejected(self):
        for attr, value in [('number', '7'), ('number', '0'), ('number', 'x'), ('number', ''),
                            ('name', '/'), ('name', ''), ('name', '/a/../b/'), ('name', '/a//b/'),
                            ('tstamps', '/')]:
            with self.subTest(attr=attr, value=value):
                with self.assertRaises(ValueError):
                    parse(mutate(lambda root: root.findall('./design/sheet')[1].set(attr, value)))

    def test_component_must_resolve_exact_declared_scope(self):
        for value in ('/Other/', '/Power α/Invented/', '', 'Power α'):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, 'sheetpath'):
                    parse(mutate(lambda root: root.find('./components/comp/sheetpath').set('names', value)))
        with self.assertRaisesRegex(ValueError, 'tstamps conflicts'):
            parse(mutate(lambda root: root.find('./components/comp/sheetpath').set('tstamps', '/wrong-uuid/')))

    def test_metadata_db_cannot_be_edited_into_a_different_scope(self):
        db = parse(XML)
        for edit in (lambda x: x['page_inventory'].update(scope=LIMITED),
                     lambda x: x['ref2page'].update(R1=1),
                     lambda x: x.update(ref2page=[]),
                     lambda x: x['page_inventory']['pages'].append(copy.deepcopy(x['page_inventory']['pages'][0]))):
            bad = copy.deepcopy(db)
            edit(bad)
            with self.assertRaises(ValueError):
                build_review_plan(bad)

    def test_inventory_changes_bind_plan_and_reject_stale_merge(self):
        old = parse(XML)
        new = parse(mutate(lambda root: root.findall('./design/sheet')[0].set('number', '8')))
        self.assertEqual(old['parts'], new['parts'])
        self.assertEqual(old['pin2net'], new['pin2net'])
        self.assertNotEqual(db_fingerprint(old), db_fingerprint(new))
        with self.assertRaisesRegex(ValueError, 'current db_sha256'):
            build_review_plan(new, previous_plan=build_review_plan(old))


class PageLedgerTests(unittest.TestCase):
    def test_all_inventory_pages_have_independent_view_and_coverage(self):
        p, r, db = ledger()
        self.assertTrue(validate_review(p, r, db)['valid'])

    def test_root_coverage_omission_is_explicit_even_without_generated_check_version(self):
        p, r, db = ledger()
        del r['coverage']['pages']['7']
        out = validate_review(p, r, db)
        self.assertFalse(out['valid'])
        self.assertTrue(any("coverage.pages: missing=['7']" in x for x in out['errors']))

    def test_root_view_cannot_be_removed_or_duplicated(self):
        for duplicate in (False, True):
            p, r, db = ledger()
            if duplicate:
                x = copy.deepcopy(next(x for x in p['checks'] if x['id'] == 'DOC-V01.7'))
                x['id'] = 'DOC-V01.EXTRA-ROOT'
                p['checks'].append(x)
            else:
                p['checks'] = [x for x in p['checks'] if x['id'] != 'DOC-V01.7']
                r['checks'] = [x for x in r['checks'] if x['id'] != 'DOC-V01.7']
                r['coverage']['pages']['7'] = [p['checks'][0]['id']]
            bind(p, r, db)
            out = validate_review(p, r, db)
            self.assertFalse(out['valid'])
            self.assertTrue(any('DOC-V01 page 7: missing/duplicate' in x for x in out['errors']))

    def test_another_page_or_electrical_pass_cannot_claim_root_view(self):
        for linked in ('DOC-V01.42', 'RST-E01.C1'):
            p, r, db = ledger()
            r['coverage']['pages']['7'] = [linked]
            out = validate_review(p, r, db)
            self.assertFalse(out['valid'])
            self.assertIn('coverage.pages.7: must link its own DOC-V01 page view', out['errors'])

    def test_unreviewed_root_remains_review_incomplete(self):
        p, r, db = ledger()
        root = next(x for x in r['checks'] if x['id'] == 'DOC-V01.7')
        root.update(review_result='REVIEW_INCOMPLETE', evidence_confidence='C',
                    missing_inputs=['Root page graphics not yet inspected'])
        out = validate_review(p, r, db)
        self.assertEqual(out['release'], 'NO_GO')
        self.assertTrue(any('DOC-V01.7' in x for x in out['blockers'] + out['errors']))

    def test_identity_and_plan_inventory_tampering_cannot_escape(self):
        for edit in (lambda p: p['page_inventory']['pages'].pop(0),
                     lambda p: next(x for x in p['checks'] if x['id'] == 'DOC-V01.7')['object'].update(sheet_path='/Fake/')):
            p, r, db = ledger()
            edit(p)
            bind(p, r, db)
            self.assertFalse(validate_review(p, r, db)['valid'])


if __name__ == '__main__':
    unittest.main()

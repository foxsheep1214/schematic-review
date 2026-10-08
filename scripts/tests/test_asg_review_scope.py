"""Synthetic applicability and field-level review counterexamples; no board fixtures."""
import json
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_decoupling import fixture, add_device, rebind
from plan_review import build_review_plan
from review_quality import screen_quality


def connector_fixture(kind='connector'):
    db, intent = fixture()
    add_device(db, intent, 'Z7')
    intent['decoupling']['groups'] = [g for g in intent['decoupling']['groups'] if g['ref'] != 'Z7']
    intent['assemblies'][0]['population']['Z7'] = True
    declaration = {'kind': kind, 'page': 1, 'quote': 'Synthetic passive connector' if kind == 'connector' else 'Synthetic integrated circuit'}
    intent['device_kinds'] = {'Z7': declaration}
    audit = {'device_kinds': {'Z7': dict(declaration, status='VERIFIED', document='synthetic.pdf', document_sha256='a' * 64)}}
    rebind(db, intent)
    return db, intent, audit


class VerifiedConnectorScopeTests(unittest.TestCase):
    def test_verified_connector_stops_implicit_ic_decoupling_but_retains_pinout(self):
        db, intent, audit = connector_fixture()
        plan = build_review_plan(db, intent=intent, datasheet_audit=audit)
        inv = plan['decoupling']
        self.assertEqual([r['ref'] for r in inv['non_decoupling_connectors']], ['Z7'])
        self.assertTrue(inv['non_decoupling_connectors'][0]['citation'])
        self.assertIn('Z7', [d['ref'] for d in inv['devices']])
        self.assertNotIn('Z7', [g['ref'] for s in inv['states'] for g in s['groups']])
        self.assertTrue(any(g['ref'] == 'U1' for s in inv['states'] for g in s['groups']))
        self.assertTrue(any(c['rule'] == 'PRO-D03' and c['object'].get('ref') == 'Z7' for c in plan['checks']))

    def test_unverified_or_rejected_declaration_never_excludes_power_candidate(self):
        db, intent, audit = connector_fixture()
        for source in (None, {'device_kinds': {'Z7': dict(audit['device_kinds']['Z7'], status='QUOTE_NOT_FOUND')}}):
            with self.subTest(source=source):
                inv = build_review_plan(db, intent=intent, datasheet_audit=source)['decoupling']
                self.assertIn('Z7', [g['ref'] for s in inv['states'] for g in s['groups']])
                self.assertEqual(inv['non_decoupling_connectors'], [])

    def test_verified_ic_still_gets_decoupling_obligations(self):
        db, intent, audit = connector_fixture('ic')
        inv = build_review_plan(db, intent=intent, datasheet_audit=audit)['decoupling']
        self.assertIn('Z7', [g['ref'] for s in inv['states'] for g in s['groups']])
        self.assertEqual(inv['non_decoupling_connectors'], [])

    def test_explicit_connector_requirements_remain_enforced(self):
        db, intent, audit = connector_fixture()
        intent['decoupling']['groups'].append({'id': 'PORT-INPUT', 'ref': 'Z7',
            'supply_nodes': ['Z7.1'], 'return_nodes': ['Z7.2'], 'citation': 'Synthetic port input requirement',
            'requirements': [{'id': 'CAP', 'kind': 'capacitance', 'criterion': 'Explicit input capacitance limit', 'citation': 'Synthetic interface clause'}]})
        plan = build_review_plan(db, intent=intent, datasheet_audit=audit)
        self.assertTrue(any(c['rule'] == 'PWR-C09' and c['object'].get('ref') == 'Z7' and c['criterion'] == 'Explicit input capacitance limit' for c in plan['checks']))
        self.assertEqual(plan['decoupling']['non_decoupling_connectors'], [])

    def test_capacitor_rating_targets_are_fitted_caps_not_the_supplied_ic(self):
        db, intent = fixture()
        plan = build_review_plan(db, intent=intent)
        check = next(c for c in plan['checks'] if c['rule'] == 'PWR-C10')
        self.assertEqual(check['qualification_refs'], ['C1', 'C2'])
        self.assertTrue(all('capacitor-qualification:' + ref in check['required_inputs'] for ref in ['C1', 'C2']))

    def test_removing_verification_changes_inventory_binding(self):
        db, intent, audit = connector_fixture()
        yes = build_review_plan(db, intent=intent, datasheet_audit=audit)['decoupling']
        no = build_review_plan(db, intent=intent)['decoupling']
        self.assertNotEqual(yes['digest'], no['digest'])


def one(rule='RST-T01', obj=None, package=None):
    obj = obj or {'ref': 'U1', 'node': 'U1.3', 'net': 'EN', 'state': 'startup'}
    c = {'id': rule + '.PROBE', 'rule': rule, 'method': 'T' if rule == 'RST-T01' else 'C',
         'object': obj, 'criterion': 'Synthetic independently bound criterion'}
    if package:
        c['package'] = package
    row = {'id': c['id'], 'review_result': 'INSUFFICIENT', 'rationale': 'U1 source is correctly traced.',
           'evidence': [{'source': 'synthetic.json', 'locator': 'U1 input'}], 'missing_inputs': ['Unknown bounded input']}
    return {'checks': [c]}, {'checks': [row]}, {'parts': {k: {} for k in ['U1', 'U2', 'R1', 'C1', 'J1']}}


def codes(p, r, db):
    return {c['code'] for c in screen_quality(p, r, db)['candidates']}


class ReviewFieldScopeTests(unittest.TestCase):
    def test_correct_rationale_and_locator_do_not_hide_wrong_impact(self):
        p, r, db = one()
        r['checks'][0]['impact_assessment'] = {'consequence': 'R1/C1 form a different reset circuit.'}
        out = screen_quality(p, r, db)
        flag = next(c for c in out['candidates'] if c['code'] == 'IMPACT_REFERENCES_OUTSIDE_SCOPE')
        self.assertEqual(flag['field'], 'consequence')
        self.assertEqual(flag['observed_refs'], ['C1', 'R1'])
        self.assertNotIn('release', out)

    def test_explicit_shared_dependency_is_not_a_field_mismatch(self):
        p, r, db = one(obj={'ref': 'U1', 'refs': ['U1', 'R1', 'C1']})
        r['checks'][0]['impact_assessment'] = {'consequence': 'R1/C1 determine this enable signal.'}
        self.assertNotIn('IMPACT_REFERENCES_OUTSIDE_SCOPE', codes(p, r, db))

    def test_scope_echo_in_json_does_not_launder_wrong_prose(self):
        p, r, db = one()
        r['checks'][0]['impact_assessment'] = {'consequence': 'R1/C1 reset path. Bound object: ' + json.dumps(p['checks'][0]['object'])}
        self.assertIn('IMPACT_REFERENCES_OUTSIDE_SCOPE', codes(p, r, db))

    def test_usb_scope_echo_does_not_validate_uart_spi_reasoning(self):
        p, r, db = one('SIG-T04', {'ref': 'U1', 'nets': ['D+', 'D-'], 'circuit': 'USB-LINK'}, 'USB')
        r['checks'][0]['rationale'] = 'TXD0 output and RXD0 input; PICO/POCI mapping remains unknown. Object: ' + json.dumps(p['checks'][0]['object'])
        self.assertIn('INTERFACE_ANALYSIS_MODE_MISMATCH', codes(p, r, db))

    def test_usb_analysis_can_legitimately_compare_uart_or_spi(self):
        p, r, db = one('SIG-T04', {'ref': 'U1'}, 'USB')
        r['checks'][0]['rationale'] = 'USB D+/D- device direction is traced; UART/SPI are unrelated alternatives.'
        self.assertNotIn('INTERFACE_ANALYSIS_MODE_MISMATCH', codes(p, r, db))

    def test_capacitor_rating_missing_input_cannot_only_ask_for_connector_identity(self):
        p, r, db = one('PWR-C10', {'ref': 'J1'})
        p['checks'][0]['qualification_refs'] = ['C1']
        r['checks'][0]['missing_inputs'] = ['J1 exact MPN and connector view']
        self.assertIn('QUALIFICATION_INPUT_TARGET_MISMATCH', codes(p, r, db))

    def test_legacy_material_refs_still_expose_wrong_rating_target(self):
        p, r, db = one('PWR-C10', {'ref': 'J1'})
        p['checks'][0]['required_material_refs'] = ['J1', 'C1']
        r['checks'][0]['missing_inputs'] = ['J1 exact MPN']
        self.assertIn('QUALIFICATION_INPUT_TARGET_MISMATCH', codes(p, r, db))

    def test_correct_capacitor_qualification_and_unknown_refs_are_not_invented(self):
        p, r, db = one('PWR-C10', {'ref': 'J1'})
        p['checks'][0]['qualification_refs'] = ['C1']
        r['checks'][0]['missing_inputs'] = ['C1 minimum voltage rating and ESR']
        self.assertNotIn('QUALIFICATION_INPUT_TARGET_MISMATCH', codes(p, r, db))
        r['checks'][0]['missing_inputs'] = ['UNKNOWN_999 documentation']
        self.assertNotIn('QUALIFICATION_INPUT_TARGET_MISMATCH', codes(p, r, db))

    def test_malformed_legacy_material_refs_do_not_crash_advisory_screening(self):
        p, r, db = one('PWR-C10', {'ref': 'J1'})
        r['checks'][0]['missing_inputs'] = ['J1 exact MPN']
        for value in (None, {'ref': 'C1'}, [None, {'ref': 'C1'}]):
            with self.subTest(value=value):
                p['checks'][0]['required_material_refs'] = value
                self.assertNotIn('QUALIFICATION_INPUT_TARGET_MISMATCH', codes(p, r, db))


if __name__ == '__main__':
    unittest.main()

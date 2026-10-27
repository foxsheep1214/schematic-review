import contextlib
import copy
import io
import pathlib
import sys
import unittest
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from parse_netlist import parse_pstxnet, self_check, is_not_populated, build
from plan_review import build_review_plan, validate_intent
from lint import Lint
from diff_netlists import connected, evaluate_claims, validate_claims
from test_lint import sample_db
from test_requirement_source import doc_for


def network(parts, nets, pinname=None):
    return {'parts': parts, 'nets': nets, 'pinname': pinname or {},
            'pin2net': {n: net for net, nodes in nets.items() for n in nodes},
            'pseudo_nets': [], 'ref2page': {}, 'pintype': {}}


class V2Regressions(unittest.TestCase):
    def test_normal_flat_net_is_not_suppressed_as_pseudo(self):
        nets, pins, pseudo = parse_pstxnet("NET_NAME\n'VCC'\nC_SIGNAL='VCC';\nNODE_NAME U1 1\n'VDD':;\n")
        self.assertEqual(nets, {'VCC': ['U1.1']})
        self.assertEqual(pins, {'U1.1': 'VDD'})
        self.assertEqual(pseudo, [])

    def test_dnp_markers_do_not_match_inside_part_number(self):
        for marker in ('DNP', 'DNI', 'DNF', 'NC'):
            self.assertTrue(is_not_populated('R_10K_' + marker, '10K'))
        self.assertFalse(is_not_populated('NCP1117', 'NCP1117'))

    def test_duplicate_pin_networks_fail_integrity(self):
        db = network({'R1': {}}, {'A': ['R1.1'], 'B': ['R1.1']}, {'R1.1': '1'})
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertFalse(self_check(db, strict=False))

    def test_zero_ohm_between_two_floating_rails_is_not_source(self):
        db = network({'R1': {'value': '0R'}, 'U1': {}},
                     {'VDD_A': ['R1.1', 'U1.1'], 'VDD_B': ['R1.2']}, {'U1.1': 'VDD'})
        lint = Lint(db)
        self.assertFalse(lint.driven('VDD_A'))
        self.assertTrue(any(x['rule'] == 'PWR-A02' for x in lint.run()))

    def test_trace_through_bead_and_fitted_resistor_to_source(self):
        db = network({'R1': {'value': '0.1R'}, 'FB1': {'value': 'FERRITE'}, 'U1': {'value': 'REG'}},
                     {'VDD_A': ['R1.1'], 'MID': ['R1.2', 'FB1.1'],
                      'SOURCE': ['FB1.2', 'U1.1']}, {'U1.1': 'VOUT'})
        self.assertFalse(Lint(db).driven('VDD_A'))
        intent = {'active_state': 'RUN', 'power_paths': [
            {'ref': 'R1', 'from': 'MID', 'to': 'VDD_A', 'state': 'RUN',
             'citation': 'Synthetic fitted 0.1 ohm sense resistor; conducting in RUN'}]}
        self.assertTrue(Lint(db, intent=intent).driven('VDD_A'))
        db['parts']['R1']['nc'] = True
        self.assertFalse(Lint(db, intent=intent).driven('VDD_A'))

    def test_pseudo_net_cannot_bridge_to_a_source(self):
        db = network({'U1': {'value': 'REG'}}, {'NC': ['U1.1']}, {'U1.1': 'VOUT'})
        db['pseudo_nets'] = ['NC']
        self.assertFalse(Lint(db).driven('NC'))

    def test_lint_preserves_export_abort_as_input_finding(self):
        findings = Lint(sample_db(), log_text='ERROR(ORCAP-1): invalid\nAborting Netlisting').run()
        self.assertEqual(len([x for x in findings if x['rule'] == 'DOC-A01']), 2)

    def test_requirement_validation_and_state_expansion_coexist(self):
        intent = {'schema_version': 5,
            'requirement_source': doc_for({'REQ-01': 'Startup guaranteed'}),
            'requirements': [{'id': 'REQ-01', 'categories': ['PROTOCOL'], 'interpretation': 'Defined state throughout sampling',
                              'owners': ['EXT-J1']}],
            'circuits': [{'id': 'BOOT', 'type': 'STARTUP', 'refs': ['U5'],   # U5 has the BOOT0 strap
                          'states': ['cold-start', 'brownout'], 'citation': 'SYNTHETIC states'}]}
        self.assertEqual(validate_intent(intent), [])
        plan = build_review_plan(sample_db(), intent)
        states = {x['object']['state'] for x in plan['checks'] if x['object'].get('circuit') == 'BOOT' and x.get('circuit_type')}
        self.assertEqual(states, {'cold-start', 'brownout'})
        self.assertTrue(any(x['object'].get('requirement_id') == 'REQ-01' for x in plan['checks']))
        del intent['requirements'][0]['categories']
        self.assertTrue(validate_intent(intent))

    def test_tvs_is_not_power_source(self):
        db = network({'D1': {'value': 'TVS'}}, {'VDD_A': ['D1.1'], 'GND': ['D1.2']})
        self.assertFalse(Lint(db).driven('VDD_A'))

    def test_requirement_and_full_pin_audits_are_planned(self):
        intent = {'schema_version': 5,'requirement_source': doc_for({'REQ-USB': 'USB port required'}),
                  'requirements': [{'id': 'REQ-USB', 'categories': ['PROTOCOL'], 'interpretation': 'end-to-end connectivity',
                                    'owners': ['EXT-J1']}]}
        self.assertEqual(validate_intent(intent), [])
        plan = build_review_plan(sample_db(), intent)
        self.assertTrue(any(x['object'].get('requirement_id') == 'REQ-USB' for x in plan['checks']))
        self.assertTrue(any(x['rule'] == 'DEV-D02' and x['object']['ref'] == 'U1'
                            for x in plan['checks']))

    def test_a_deferred_requirement_gets_no_checks(self):
        intent = {'schema_version': 5,'requirement_source': doc_for({'REQ-T': 'derate by temperature'}),
                  'requirements': [{'id': 'REQ-T', 'status': 'DEFERRED', 'categories': ['ENVIRONMENT'],
                                    'interpretation': 'derating points'}]}
        self.assertEqual(validate_intent(intent), [])
        plan = build_review_plan(sample_db(), intent)
        self.assertFalse([x for x in plan['checks'] if x['object'].get('requirement_id') == 'REQ-T'])
        self.assertEqual(plan['deferred_requirements'], ['REQ-T'])
        intent['requirements'][0]['status'] = 'MAYBE'
        self.assertTrue(validate_intent(intent))

    def test_only_audit_verified_device_kinds_reach_analysis(self):
        import board_intent
        decl = {'Q1': {'kind': 'bjt', 'page': 1, 'quote': 'NPN power bipolar transistor'}}
        self.assertEqual(board_intent.device_kind_errors(decl, None), [])
        self.assertTrue(board_intent.device_kind_errors({'Q1': {'kind': 'bjt', 'page': 1}}, None))
        self.assertTrue(board_intent.device_kind_errors({'Q1': dict(decl['Q1'], page='1')}, None))
        intent = {'device_kinds': decl}
        audit = {'device_kinds': {'Q1': dict(decl['Q1'], status='VERIFIED', document='/x/BCX56.pdf',
                                             document_sha256='a' * 64)}}
        self.assertEqual(board_intent.with_verified_kinds(intent, None), intent)        # no audit -> not used
        failed = {'device_kinds': {'Q1': dict(audit['device_kinds']['Q1'], status='QUOTE_NOT_FOUND')}}
        self.assertEqual(board_intent.verified_kinds(intent, failed), {})
        analysis = board_intent.with_verified_kinds(intent, audit)
        self.assertEqual(board_intent.declared_kinds(analysis)['Q1']['kind'], 'bjt')
        ctx = board_intent.context(analysis, 'power_switches')
        self.assertEqual(board_intent.declared_kinds(ctx), board_intent.declared_kinds(analysis))
        self.assertEqual(board_intent.graph_db({'parts': {}}, ctx)['device_kinds']['Q1']['kind'], 'bjt')
        self.assertTrue(validate_intent(dict(intent, device_kinds_verified={})))

    def test_changed_only_claim_does_not_close_repair(self):
        old, new = sample_db(), sample_db()
        new['pin2net']['U1.1'] = 'STILL_WRONG'
        claims = {'schema_version': 1, 'claims': [{'id': 'F1', 'expect': [
                  {'kind': 'pin_net_changed', 'node': 'U1.1'}]}]}
        result, findings = evaluate_claims(old, new, claims)
        self.assertEqual(result[0]['status'], 'INSUFFICIENT')
        self.assertTrue(findings)

    def test_connectivity_assertion_respects_dnp_and_pseudo(self):
        db = network({'R1': {'value': '0R'}}, {'A': ['U1.1', 'R1.1'], 'B': ['R1.2', 'U2.1']})
        self.assertTrue(connected(db, 'U1.1', 'U2.1'))
        db['parts']['R1']['nc'] = True
        self.assertFalse(connected(db, 'U1.1', 'U2.1'))
        db['pseudo_nets'] = ['A']
        self.assertIsNone(connected(db, 'U1.1', 'U2.1'))
        self.assertTrue(validate_claims({'schema_version': 1, 'claims': [
            {'id': 'F1', 'expect': [{'kind': 'pins_connected', 'nodes': ['U1.1']}]}]}))

    def test_parser_keeps_symbol_pin_omitted_from_netlist(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root/'pstxnet.dat').write_text("NET_NAME\n'VCC'\nC_SIGNAL='@D:VCC';\nNODE_NAME U1 1\n'VDD':;\n")
            (root/'pstxprt.dat').write_text(" U1 'IC':;\nP_PATH='@D:page1_main';\n")
            (root/'pstchip.dat').write_text("primitive 'IC';\nPART_NAME='SYNTHETIC';\nVALUE='IC';\n"
                " 'VDD':\nPIN_NUMBER='(1)';\nPINUSE='POWER';\n"
                " 'RESERVED':\nPIN_NUMBER='(2)';\nPINUSE='IN';\nend_primitive;\n")
            db = build(directory)
            self.assertEqual(db['declared_pinname']['U1.2'], 'RESERVED')
            self.assertNotIn('U1.2', db['pin2net'])
            self.assertEqual(db['missing_primitives'], [])
            (root/'netlist.log').write_text('ERROR(ORCAP-36041): invalid export\nAborting Netlisting')
            db = build(directory)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertFalse(self_check(db, strict=False))

    def test_missing_part_and_null_value_cannot_close_claim(self):
        claim = {'schema_version': 1, 'claims': [{'id': 'F', 'expect': [
            {'kind': 'part_field_equals', 'ref': 'MISSING', 'field': 'value', 'value': None}]}]}
        self.assertTrue(validate_claims(claim))
        result, _ = evaluate_claims(sample_db(), sample_db(), claim)
        self.assertEqual(result[0]['status'], 'FAIL')


if __name__ == '__main__':
    unittest.main()

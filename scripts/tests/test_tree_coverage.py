"""Coverage over the tree and a report in tree order (function-tree design §3.5 and §3.7, step 6).

Two machine-countable audits: every fitted part belongs to exactly one circuit or is listed for REQ-Q08 review
(ownership coverage), and every interface carries the rows its kind asks and, unless it is a rail, a frame (REQ-Q07
extended to interfaces). The report's function table runs system functions, then circuits, then interfaces, and
every finding names the owners of its checks.
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import circuit_candidates as cc
import circuit_decisions as cd
import interfaces
import render_report
import results_model
import review_functions
import row_owner
import rule_gaps
from plan_review import build_review_plan
from test_interface_rows import plan_for
from test_render_and_pack import body, report
from test_validate_review import fail, fixture
import test_circuit_candidates as fx
import test_circuit_decisions as dfx


class OwnershipCoverageTests(unittest.TestCase):
    def setUp(self):
        self.db = fx.board()
        self.plan = plan_for(self.db)

    def test_every_fitted_part_is_owned_or_listed_for_review(self):
        self.assertEqual(row_owner.coverage_errors(self.plan, self.db), [])
        q08 = next(c for c in self.plan['checks'] if c['rule'] == 'REQ-Q08')
        self.assertIn('R99', q08['object']['unassigned'])

    def test_the_review_list_row_is_a_planner_row_the_gate_cannot_regenerate(self):
        # The gate regenerates the plan from the saved inputs, which do not hold the candidate file; the REQ-Q08 row
        # listing the parts no circuit owns comes from that file, so the gate does not take it for a row added by hand.
        q08 = next(c for c in self.plan['checks'] if c['rule'] == 'REQ-Q08')
        self.assertFalse(rule_gaps.unwritten(q08))
        self.assertTrue(rule_gaps.unwritten(dict(q08, trigger=['reviewer'])))   # another REQ-Q08 row is still hand-added

    def test_the_gate_regenerates_the_review_list_row_with_its_unassigned_parts(self):
        # The row lists both circuit types nobody declared and parts the candidates left unassigned; the gate rebuilds
        # it from the candidate summary the plan keeps, so it is not taken for a changed automatic row.
        import validate_review as vr
        q08 = next(c for c in self.plan['checks'] if c['rule'] == 'REQ-Q08')
        self.assertTrue(q08['object']['circuit_types'] and q08['object']['unassigned'])
        errors = vr.validate_review(self.plan, {'checks': [], 'schema_version': results_model.SCHEMA_VERSION}, self.db)['errors']
        self.assertFalse([e for e in errors if e.startswith('REQ-Q08.BOARD: automatic check')], errors[:3])

    def test_a_part_dropped_from_both_lists_is_refused(self):
        plan = copy.deepcopy(self.plan)
        q08 = next(c for c in plan['checks'] if c['rule'] == 'REQ-Q08')
        q08['object']['unassigned'] = [r for r in q08['object']['unassigned'] if r != 'R99']
        errors = row_owner.coverage_errors(plan, self.db)
        self.assertTrue(any('R99' in e for e in errors), errors)
        plan = copy.deepcopy(self.plan)
        for entry in plan['owners']:
            entry['parts'] = [r for r in entry['parts'] if r != 'U1']
        self.assertTrue(any('U1' in e for e in row_owner.coverage_errors(plan, self.db)))

    def test_a_part_two_circuits_own_is_refused(self):
        plan = copy.deepcopy(self.plan)
        plan['owners'][1]['parts'].append(plan['owners'][0]['parts'][0])
        errors = row_owner.coverage_errors(plan, self.db)
        self.assertTrue(any(plan['owners'][0]['parts'][0] in e and 'owned by 2' in e for e in errors), errors)

    def test_the_review_list_takes_every_unowned_part_not_only_the_candidate_file_list(self):
        intent, audit = fx.intent_for(self.db)
        candidates = cc.build(self.db, intent, audit)
        candidates['unassigned'] = [u for u in candidates['unassigned'] if u['ref'] != 'R99']
        intent['circuit_decisions'] = dfx.accept_all(candidates)
        plan = build_review_plan(self.db, cd.write_circuits(intent, candidates), datasheet_audit=audit, candidates=candidates)
        q08 = next(c for c in plan['checks'] if c['rule'] == 'REQ-Q08')
        self.assertIn('R99', q08['object']['unassigned'])

    def test_a_plan_without_candidate_circuits_claims_no_ownership(self):
        plan = dict(self.plan)
        plan.pop('circuit_candidates')
        self.assertEqual(row_owner.coverage_errors(plan, self.db), [])


class InterfaceCoverageTests(unittest.TestCase):
    def setUp(self):
        self.plan = plan_for()

    def test_every_interface_has_its_rows_and_frame(self):
        self.assertEqual(interfaces.coverage_errors(self.plan), [])

    def test_a_missing_interface_row_or_frame_is_refused(self):
        plan = copy.deepcopy(self.plan)
        plan['checks'] = [c for c in plan['checks'] if not (c['rule'] == 'SIG-T04' and c['object'].get('interface') == 'IF-ANALOG-U5~USB-J2')]
        self.assertTrue(any('IF-ANALOG-U5~USB-J2' in e and 'SIG-T04' in e for e in interfaces.coverage_errors(plan)))
        plan = copy.deepcopy(self.plan)
        plan['functions'] = [f for f in plan['functions'] if f.get('interface') != 'EXT-J1']
        self.assertTrue(any('EXT-J1' in e and 'frame' in e for e in interfaces.coverage_errors(plan)))
        plan = copy.deepcopy(self.plan)
        plan['checks'] = [c for c in plan['checks'] if c['rule'] != 'PWR-C14']
        self.assertTrue(any('RAIL-VOUT' in e for e in interfaces.coverage_errors(plan)))


class TreeReportTests(unittest.TestCase):
    def test_the_function_table_runs_system_then_circuits_then_interfaces(self):
        plan = plan_for()
        functions = [{'id': f['id'], 'question': f['question'], 'verdict': 'PASS', 'no_calculation_reason': 'synthetic'}
                     for f in sorted(plan['functions'], key=lambda f: f['id'], reverse=True)]
        lines = render_report.render_functions(functions, plan)
        heads = [l for l in lines if l.startswith('### ')]
        self.assertEqual(heads, ['### 系统功能', '### 功能电路', '### 接口'])
        text = '\n'.join(lines)
        converter = next(f['id'] for f in plan['functions'] if f.get('circuit') == 'POWER_CONVERTER-U1')
        self.assertLess(text.index('FN-SYS-POWER'), text.index(converter))
        self.assertLess(text.index(converter), text.index('FN-EXT-J1'))

    def delegated(self):
        """A circuit frame whose member row is left open under another (reviewer-built) function."""
        plan = plan_for()
        frame = next(f for f in plan['functions'] if f.get('circuit') == 'POWER_CONVERTER-U1')
        member = frame['members'][0]['check_id']
        functions = [{'id': frame['id'], 'question': frame['question'], 'verdict': 'PASS', 'no_calculation_reason': 'synthetic'},
                     {'id': 'FN-OWN', 'question': 'reviewer-built', 'verdict': 'OPEN', 'open': [{'key': 'GAP-X', 'kind': 'VENDOR_DATUM'}]}]
        checks = [{'id': member, 'review_result': 'INSUFFICIENT', 'function_id': 'FN-OWN', 'open_ref': 'FN-OWN/GAP-X'}]
        return plan, frame, functions, checks

    def test_a_frame_with_a_member_left_open_elsewhere_counts_as_open(self):
        # Rows moved to a reviewer-built function let the circuit read "PASS" while its own rows stayed open; the
        # count and the table now follow the member rows, naming the work item that holds them.
        plan, frame, functions, checks = self.delegated()
        self.assertEqual(results_model.effective_verdicts(functions, plan, checks)[frame['id']], ('OPEN', ['W-GAP-X']))
        row = next(l for l in render_report.render_functions(functions, plan, checks) if l.startswith('| ' + frame['id']))
        self.assertIn('未定', row)
        self.assertIn('W-GAP-X', row)
        text = render_report.render(plan, {'functions': functions, 'checks': checks}, {})
        self.assertIn('| 功能判定 合格 / 不合格 / 未定 | 0 / 0 / 2 |', text)

    def test_a_frame_with_a_member_failed_elsewhere_counts_as_failed(self):
        plan, frame, functions, checks = self.delegated()
        checks[0].update(review_result='FAIL', fail_ref='FN-OWN/BAD-X')
        checks[0].pop('open_ref')
        self.assertEqual(results_model.effective_verdicts(functions, plan, checks)[frame['id']], ('FAIL', ['W-BAD-X']))

    def test_a_frames_own_row_pointing_at_another_functions_item_counts_as_open(self):
        # FN-SYS-SEQUENCE read PASS while RST-T03.SYS-SEQUENCE, its own row, was INSUFFICIENT through an open_ref into
        # another function (R7 acceptance 2026-10-25, codex1 SR-05)
        plan, frame, functions, checks = self.delegated()
        checks[0]['function_id'] = frame['id']
        self.assertEqual(results_model.effective_verdicts(functions, plan, checks)[frame['id']], ('OPEN', ['W-GAP-X']))
        checks[0]['open_ref'] = frame['id'] + '/GAP-OWN'   # its own item: the function's verdict already says so
        self.assertEqual(results_model.effective_verdicts(functions, plan, checks)[frame['id']], ('PASS', []))

    def test_a_frame_whose_members_all_pass_keeps_its_verdict(self):
        plan, frame, functions, checks = self.delegated()
        checks[0]['review_result'] = 'PASS'
        self.assertEqual(results_model.effective_verdicts(functions, plan, checks)[frame['id']], ('PASS', []))

    def test_a_rewritten_frame_question_still_names_the_circuit(self):
        plan, frame, functions, checks = self.delegated()
        functions[0]['question'] = 'only the connections kept in this section'
        rows = {c['id']: c for c in checks}
        self.assertTrue(any('question' in e and frame['id'] in e for e in review_functions.frame_errors(plan, rows, functions)))
        for question in (frame['question'], 'U1 output at 5 V and 3 A stays in the 4.75-5.25 V window'):
            functions[0]['question'] = question
            self.assertFalse(any('question' in e for e in review_functions.frame_errors(plan, rows, functions)))

    def test_a_finding_names_the_owners_of_its_checks(self):
        plan = plan_for()
        row = next(c for c in plan['checks'] if c['rule'] == 'PRO-D03' and c['object']['ref'] == 'J2')
        self.assertEqual(render_report.finding_owners({'check_ids': [row['id']]}, plan), '接口 EXT-J2')
        circuit = next(c for c in plan['checks'] if c['owner'] == {'kind': 'CIRCUIT', 'id': 'POWER_CONVERTER-U1'})
        self.assertEqual(render_report.finding_owners({'check_ids': [circuit['id'], row['id']]}, plan),
                         '功能电路 POWER_CONVERTER-U1、接口 EXT-J2')
        self.assertIsNone(render_report.finding_owners({'check_ids': ['X.1']}, {}))   # a plan without owners

    def test_the_report_writes_the_owner_line_under_each_finding(self):
        p, r, db = fixture()
        fail(r)
        key = r['checks'][0]['id']
        r['findings'][0]['check_ids'] = [key]
        next(c for c in p['checks'] if c['id'] == key)['owner'] = {'kind': 'CIRCUIT', 'id': 'BUCK'}
        text, _ = report(p, r, db)
        self.assertIn('- **所属**：功能电路 BUCK', body(text).split('## 发现的错误')[1])


if __name__ == '__main__':
    unittest.main()

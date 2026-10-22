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
import row_owner
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

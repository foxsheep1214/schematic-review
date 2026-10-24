"""A requirement aspect a tree check already asks is bound to that check (fixed requirements, step 4).

After step 2 every (requirement, aspect) had its own REQ-D01 row, so a temperature requirement's "parts' temperature
grade" was judged twice: once by the parts' recommended-operating-condition rows and once in requirement prose that
could disagree with them. Each aspect now names the tree rules that carry it (catalog.ASPECT_RULES). The planner binds
the requirement row to the rows of those rules: the rows of the circuits, interfaces or system functions the
requirement names in `owners`, or, for an aspect of the whole board (temperature grade and derating, lifetime), every
row of those rules when it names none. A bound requirement row is not judged again: its result is the worst result
of its bound rows (derive_rows.py writes it), and only an aspect no tree row carries is judged on the requirement row.
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import catalog
import derive_rows
import requirement_bindings as rb
from validate_review import validate_review
from plan_review import build_review_plan, validate_intent
from test_decoupling import fixture, ledger, mark_pass, rebind
from ledger4 import defect
from test_requirement_source import requirement_intent, write


def board(owners=None, categories=None):
    db, value = fixture(('100nF',))
    value.update(dict({'schema_version': 4}, **requirement_intent(write(), categories=categories)))
    for item in value['requirements']:
        if owners and item['id'] in owners:
            item['owners'] = owners[item['id']]
    rebind(db, value)
    return db, value


def req_row(plan, rid, aspect):
    return next(c for c in plan['checks'] if c['rule'] == 'REQ-D01' and c['object']['requirement_id'] == rid
                and c['object']['aspect'] == aspect)


class TableTests(unittest.TestCase):
    def test_every_bound_aspect_names_catalog_rules_and_board_aspects_are_bound(self):
        for aspect, rules in catalog.ASPECT_RULES.items():
            self.assertIn(aspect, catalog.REQUIREMENT_ASPECTS)
            self.assertTrue(rules and all(r in catalog.BY_ID for r in rules), aspect)
        self.assertTrue(set(catalog.BOARD_ASPECTS) <= set(catalog.ASPECT_RULES))
        text = catalog.render_markdown()
        self.assertIn('、'.join(catalog.ASPECT_RULES['TEMPERATURE_GRADE']), text)


class PlanTests(unittest.TestCase):
    def test_a_board_aspect_binds_every_row_of_its_rules(self):
        plan = build_review_plan(*board())
        self.assertEqual(req_row(plan, 'REQ-TEMP-01', 'TEMPERATURE_GRADE')['bound_checks'], ['DEV-C05.U1'])
        self.assertEqual(req_row(plan, 'REQ-TEMP-01', 'TEMPERATURE_DERATING')['bound_checks'], ['DEV-C01.BOARD'])
        # An aspect of particular circuits binds nothing without owners; an aspect no rule carries never binds.
        self.assertEqual(req_row(plan, 'REQ-TEMP-01', 'TEMPERATURE_DRIFT')['bound_checks'], [])
        self.assertEqual(req_row(plan, 'REQ-TEMP-01', 'ALTITUDE_HUMIDITY')['bound_checks'], [])
        self.assertEqual(rb.errors(plan), [])

    def test_isolation_is_an_aspect_of_the_whole_board(self):
        # A gap may block a row through a requirement clause only when the row is bound to that requirement
        # (consistency proposals 2026-10-23, 1d): an insulation requirement binds every isolation row.
        checks = [{'id': 'PRO-D01.U2', 'rule': 'PRO-D01', 'applicability': 'APPLICABLE'},
                  {'id': 'PRO-C03.U2', 'rule': 'PRO-C03', 'applicability': 'APPLICABLE'},
                  {'id': 'PRO-D02.BOARD', 'rule': 'PRO-D02', 'applicability': 'APPLICABLE'}]
        parts = {'id': 'R', 'rule': 'REQ-D01', 'object': {'aspect': 'ISOLATION_PARTS'}}
        paths = {'id': 'P', 'rule': 'REQ-D01', 'object': {'aspect': 'ISOLATION_PATHS'}}
        self.assertEqual(rb.bound(checks, parts), ['PRO-C03.U2', 'PRO-D01.U2'])
        self.assertEqual(rb.bound(checks, paths), ['PRO-D02.BOARD'])

    def test_owners_bind_the_rows_they_own(self):
        plan = build_review_plan(*board({'REQ-OPEN-01': ['SYS-POWER']}))
        row = req_row(plan, 'REQ-OPEN-01', 'OUTPUT_LIMITS')
        self.assertEqual(row['requirement_owners'], ['SYS-POWER'])
        self.assertEqual(row['bound_checks'], ['PWR-C01.VCC-3V3'])
        plan = build_review_plan(*board({'REQ-OPEN-01': ['SYS-MONITOR']}))
        self.assertEqual(req_row(plan, 'REQ-OPEN-01', 'OUTPUT_LIMITS')['bound_checks'], [])

    def test_bindings_stay_out_of_the_check_identity(self):
        a = build_review_plan(*board())
        b = build_review_plan(*board({'REQ-OPEN-01': ['SYS-POWER']}))
        keys = lambda p: sorted(c['check_key'] for c in p['checks'])
        self.assertEqual(keys(a), keys(b))

    def test_owners_must_be_a_list_and_own_rows_and_bindings_must_match(self):
        db, value = board({'REQ-OPEN-01': 'SYS-POWER'})
        self.assertTrue(any('owners' in e for e in validate_intent(value)))
        plan = build_review_plan(*board({'REQ-OPEN-01': ['C-NONE']}))
        self.assertTrue(any('C-NONE' in e for e in rb.errors(plan)))
        plan = build_review_plan(*board())
        req_row(plan, 'REQ-TEMP-01', 'TEMPERATURE_GRADE')['bound_checks'] = []
        self.assertTrue(any('bound_checks' in e for e in rb.errors(plan)))


class ResultTests(unittest.TestCase):
    def setUp(self):
        self.db, value = board()
        self.plan = build_review_plan(self.db, value)
        self.key = req_row(self.plan, 'REQ-TEMP-01', 'TEMPERATURE_GRADE')['id']

    def report(self, bound_result):
        report = ledger(self.plan, self.db)
        for row in report['checks']:
            mark_pass(report, self.plan, row)
        bound = next(r for r in report['checks'] if r['id'] == 'DEV-C05.U1')
        if bound_result == 'FAIL':
            bound['severity'] = 'P2'
            defect(report, 'DEV-C05.U1', 'F-1', 'F-1', plan=self.plan)
            report.setdefault('findings', []).append({'id': 'F-1', 'severity': 'P2', 'check_ids': ['DEV-C05.U1'],
                                                      'title': 'x', 'evidence': bound['evidence']})
        return report

    def errors(self, report):
        return [e for e in validate_review(self.plan, report, self.db)['errors'] if self.key in e]

    def test_the_worst_bound_result_is_the_requirement_result(self):
        rows = {'DEV-C05.U1': {'review_result': 'FAIL'}, 'X': {'review_result': 'PASS'}}
        self.assertEqual(rb.derived_result({'bound_checks': ['DEV-C05.U1', 'X']}, rows), 'FAIL')
        self.assertEqual(rb.derived_result({'bound_checks': ['X']}, rows), 'PASS')
        self.assertIsNone(rb.derived_result({'bound_checks': []}, rows))
        self.assertIsNone(rb.derived_result({'bound_checks': ['N']}, {'N': {'review_result': 'NA'}}))

    def test_a_bound_requirement_row_that_disagrees_with_its_bound_rows_is_refused(self):
        self.assertEqual(self.errors(self.report('PASS')), [])
        self.assertTrue(any('绑定' in e for e in self.errors(self.report('FAIL'))))

    def test_derive_rows_writes_the_bound_requirement_rows(self):
        report = self.report('FAIL')
        report['checks'] = [r for r in report['checks'] if r['id'] != self.key]
        out, summary, errors = derive_rows.derive(self.plan, report)
        self.assertEqual([e for e in errors if 'REQ-D01' in e], [])   # rows bound to function verdicts are not set up here
        row = next(r for r in out['checks'] if r['id'] == self.key)
        self.assertEqual((row['review_result'], row['finding_id'], row['severity']), ('FAIL', 'F-1', 'P2'))
        self.assertEqual(row['derived_from'], ['DEV-C05.U1'])
        self.assertIn(self.key, next(f for f in out['findings'] if f['id'] == 'F-1')['check_ids'])
        self.assertEqual(self.errors(out), [])
        self.assertGreaterEqual(summary['requirements'], 1)

    def test_a_hand_filled_requirement_row_is_kept_and_compared(self):
        report = self.report('FAIL')
        out, _, errors = derive_rows.derive(self.plan, copy.deepcopy(report))
        self.assertTrue(any(self.key in e and 'disagrees' in e for e in errors))


class OwnerCandidateTests(unittest.TestCase):
    """owners are recommended by the plan and required when there is a candidate (requirement owners, 2026-10-24):
    a candidate is a circuit of the aspect's types, or any system function or interface, that owns an applicable row
    of the aspect's rules; a requirement with a candidate and no `owners` is refused, `owners: []` needs a located
    reason, and a requirement with no candidate is judged on its row (`self_judged: NO_OWNER_CANDIDATE`)."""

    def confirmed(self, owners=None, **fields):
        db, value = board(owners)
        for item in value['requirements']:
            if item['id'] == 'REQ-OPEN-01':
                item['status'] = 'CONFIRMED'
                item.update(fields)
        return db, value

    def test_candidates_are_circuits_of_the_aspect_types_and_every_system_function_or_interface(self):
        checks = [{'id': 'a', 'rule': 'PWR-E01', 'applicability': 'APPLICABLE', 'owner': {'kind': 'CIRCUIT', 'id': 'C1'}},
                  {'id': 'b', 'rule': 'PWR-E01', 'applicability': 'APPLICABLE', 'owner': {'kind': 'CIRCUIT', 'id': 'C2'}},
                  {'id': 'c', 'rule': 'PWR-C15', 'applicability': 'NOT_APPLICABLE', 'owner': {'kind': 'CIRCUIT', 'id': 'C3'}},
                  {'id': 'd', 'rule': 'PWR-E01', 'applicability': 'APPLICABLE', 'owner': {'kind': 'SYSTEM', 'id': 'SYS-POWER'}},
                  {'id': 'e', 'rule': 'DEV-C01', 'applicability': 'APPLICABLE', 'owner': {'kind': 'CIRCUIT', 'id': 'C1'}}]
        table = [{'kind': 'CIRCUIT', 'id': 'C1', 'type': 'POWER_CONVERTER'}, {'kind': 'CIRCUIT', 'id': 'C2', 'type': 'I2C'},
                 {'kind': 'CIRCUIT', 'id': 'C3', 'type': 'POWER_CONVERTER'}]
        row = {'rule': 'REQ-D01', 'object': {'aspect': 'OUTPUT_LEVELS'}}
        self.assertEqual(rb.candidates(checks, row, table), [{'id': 'C1', 'kind': 'CIRCUIT', 'type': 'POWER_CONVERTER'},
                                                              {'id': 'SYS-POWER', 'kind': 'SYSTEM'}])
        self.assertEqual(rb.candidates(checks, {'rule': 'REQ-D01', 'object': {'aspect': 'TEMPERATURE_GRADE'}}, table), [])
        self.assertEqual(rb.candidates(checks, {'rule': 'REQ-D01', 'object': {'aspect': 'FUNCTION_PRESENT'}}, table), [])
        for aspect, types in catalog.ASPECT_OWNER_TYPES.items():
            self.assertIn(aspect, catalog.ASPECT_RULES)
            self.assertNotIn(aspect, catalog.BOARD_ASPECTS)
            self.assertTrue(all(any(c.name == t for c in catalog.CIRCUIT_TYPES) for t in types), aspect)

    def test_the_plan_writes_candidates_and_an_open_requirement_needs_no_owners(self):
        plan = build_review_plan(*board())
        row = req_row(plan, 'REQ-OPEN-01', 'OUTPUT_LIMITS')
        self.assertEqual(row['owner_candidates'], [{'id': 'SYS-POWER', 'kind': 'SYSTEM'}])
        self.assertNotIn('requirement_owners', row)
        self.assertNotIn('self_judged', row)
        self.assertEqual(rb.errors(plan), [])

    def test_a_requirement_with_a_candidate_and_no_owners_is_refused_naming_the_candidate(self):
        with self.assertRaises(ValueError) as caught:
            build_review_plan(*self.confirmed())
        self.assertIn('REQ-OPEN-01.owners 缺', str(caught.exception))
        self.assertIn('SYS-POWER（SYSTEM）', str(caught.exception))
        self.assertIn('OUTPUT_LIMITS', str(caught.exception))

    def test_owners_empty_needs_a_located_reason_and_leaves_the_row_to_itself(self):
        db, value = self.confirmed(owners=None, owners_=None)
        value['requirements'][2]['owners'] = []
        self.assertTrue(any('no_owner_reason' in e for e in validate_intent(value)))
        value['requirements'][2]['no_owner_reason'] = '输出纹波由板外滤波决定'
        self.assertTrue(any('no_owner_reason' in e for e in validate_intent(value)))
        value['requirements'][2]['no_owner_reason'] = 'VCC_3V3 由 J1 直接供入，板上没有变换器电路（第 2 页）'
        self.assertFalse(any('owners' in e for e in validate_intent(value)))
        plan = build_review_plan(db, value)
        row = req_row(plan, 'REQ-OPEN-01', 'OUTPUT_LIMITS')
        self.assertEqual(row['requirement_owners'], [])
        self.assertEqual(row['bound_checks'], [])
        self.assertEqual(row['self_judged'], 'DECLARED')
        self.assertEqual(rb.errors(plan), [])
        value['requirements'][2]['owners'] = ['SYS-POWER']
        self.assertTrue(any('no_owner_reason 只在' in e for e in validate_intent(value)))

    def test_no_candidate_means_the_row_is_judged_on_itself(self):
        plan = build_review_plan(*board())
        row = req_row(plan, 'REQ-IN-01', 'INPUT_THRESHOLDS')
        self.assertEqual(row['owner_candidates'], [])
        self.assertEqual(row['self_judged'], 'NO_OWNER_CANDIDATE')
        self.assertNotIn('self_judged', req_row(plan, 'REQ-TEMP-01', 'TEMPERATURE_GRADE'))

    def test_owners_outside_the_candidates_are_a_printed_diagnostic_not_a_refusal(self):
        from plan_review import diagnostic_lines
        db, value = self.confirmed({'REQ-OPEN-01': ['SYS-MONITOR']})
        plan = build_review_plan(db, value)
        found = [d for d in plan['diagnostics'] if d['code'] == 'REQUIREMENT_OWNER_OUTSIDE_CANDIDATES']
        self.assertEqual([(d['requirement'], d['owners'], d['candidates']) for d in found],
                         [('REQ-OPEN-01', ['SYS-MONITOR'], ['SYS-POWER'])])
        self.assertTrue(any('SYS-MONITOR' in line for line in diagnostic_lines(plan, db, value)))
        plan = build_review_plan(*self.confirmed({'REQ-OPEN-01': ['SYS-POWER']}))
        self.assertEqual([d for d in plan['diagnostics'] if d['code'] == 'REQUIREMENT_OWNER_OUTSIDE_CANDIDATES'], [])
        self.assertEqual(req_row(plan, 'REQ-OPEN-01', 'OUTPUT_LIMITS')['bound_checks'], ['PWR-C01.VCC-3V3'])

    def test_the_validator_recomputes_candidates_and_self_judged(self):
        plan = build_review_plan(*board())
        req_row(plan, 'REQ-OPEN-01', 'OUTPUT_LIMITS')['owner_candidates'] = []
        self.assertTrue(any('owner_candidates' in e for e in rb.errors(plan)))
        plan = build_review_plan(*board())
        req_row(plan, 'REQ-IN-01', 'INPUT_THRESHOLDS').pop('self_judged')
        self.assertTrue(any('self_judged' in e for e in rb.errors(plan)))
        plan = build_review_plan(*board())
        row = req_row(plan, 'REQ-OPEN-01', 'OUTPUT_LIMITS')
        row['object']['requirement_status'] = 'CONFIRMED'
        self.assertTrue(any('owners 缺' in e for e in rb.errors(plan)))

    def test_compare_reports_owners_and_judging_differences_per_requirement(self):
        import compare_reviews
        a = {'where': 'A', 'plan': build_review_plan(*self.confirmed({'REQ-OPEN-01': ['SYS-POWER']})), 'results': {}}
        db, value = self.confirmed()
        value['requirements'][2].update(owners=[], no_owner_reason='VCC_3V3 由 J1 直接供入')
        b = {'where': 'B', 'plan': build_review_plan(db, value), 'results': {}}
        report = compare_reviews.requirement_owners(a, b)
        diff = {r['requirement']: r for r in report['rows'] if not r['same']}
        self.assertEqual(list(diff), ['REQ-OPEN-01'])
        self.assertEqual(diff['REQ-OPEN-01']['A']['owners'], ['SYS-POWER'])
        self.assertEqual(diff['REQ-OPEN-01']['A']['judged']['OUTPUT_LIMITS'], 'DERIVED')
        self.assertEqual(diff['REQ-OPEN-01']['B']['owners'], [])
        self.assertEqual(diff['REQ-OPEN-01']['B']['judged']['OUTPUT_LIMITS'], 'SELF')
        self.assertEqual(report['different'], 1)
        text = compare_reviews.markdown(compare_reviews.compare(a, b))
        self.assertIn('## 需求的 owners 与判法', text)
        self.assertIn('| REQ-OPEN-01 | SYS-POWER |', text)


if __name__ == '__main__':
    unittest.main()

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
from ledger_v3 import validate_review
from plan_review import build_review_plan, validate_intent
from test_decoupling import fixture, ledger, mark_pass, rebind
from test_requirement_source import requirement_intent, write


def board(owners=None, categories=None):
    db, value = fixture(('100nF',))
    value.update(dict({'schema_version': 3}, **requirement_intent(write(), categories=categories)))
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
            mark_pass(row)
        bound = next(r for r in report['checks'] if r['id'] == 'DEV-C05.U1')
        if bound_result == 'FAIL':
            bound.update(review_result='FAIL', severity='P2', finding_id='F-1')
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


if __name__ == '__main__':
    unittest.main()

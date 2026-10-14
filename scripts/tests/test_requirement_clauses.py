"""REQ-D01 rows: clause split, obligation-only verdicts and worst-clause aggregation."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plan_review import build_review_plan
from validate_review import validate_review
from test_decoupling import fixture, ledger, mark_pass, rebind

TEXT = '+3V3=3.3V±5%，环境0～50°C。电阻采购公差1%；元件按实际物料额定审查。'
OBLIGATION = '+3V3=3.3V±5%，环境0～50°C。'
PREMISES = ('电阻采购公差1%；', '元件按实际物料额定审查。')


class RequirementClauseTests(unittest.TestCase):
    def setUp(self):
        self.db, intent = fixture(('100nF',))
        intent['requirements'] = [{'id': 'REQ-02', 'text': TEXT, 'criterion': TEXT,
                                   'status': 'CONFIRMED', 'citation': 'synthetic requirements REQ-02'}]
        rebind(self.db, intent)
        self.plan = build_review_plan(self.db, intent)
        self.key = next(c['id'] for c in self.plan['checks'] if c['rule'] == 'REQ-D01')

    def errors(self, result, clauses, versioned=True):
        report = ledger(self.plan, self.db)
        if versioned:
            report['requirement_clauses_version'] = 1
        row = next(c for c in report['checks'] if c['id'] == self.key)
        mark_pass(row)
        if result == 'FAIL':
            row.update(review_result='FAIL', severity='P2', finding_id='F-1')
            report.setdefault('findings', []).append({'id': 'F-1', 'severity': 'P2', 'check_ids': [self.key],
                                                      'title': 'x', 'evidence': row['evidence']})
        if clauses is not None:
            row['requirement_clauses'] = clauses
        return [e for e in validate_review(self.plan, report, self.db)['errors']
                if self.key in e and ('条款' in e or 'clauses' in e)]

    def clauses(self, verdict='PASS', premise_result=None):
        return ([{'text': OBLIGATION, 'kind': 'OBLIGATION', 'result': verdict}] +
                [{'text': t, 'kind': 'PREMISE', 'result': premise_result} for t in PREMISES])

    def test_premise_clauses_do_not_carry_other_rows_defects(self):
        self.assertEqual(self.errors('PASS', self.clauses()), [])
        # A method sentence ("按实际物料额定审查") cannot turn this row into FAIL.
        self.assertTrue(self.errors('FAIL', self.clauses()))
        self.assertTrue(self.errors('PASS', self.clauses(premise_result='FAIL')))

    def test_row_result_is_worst_obligation(self):
        self.assertTrue(self.errors('PASS', self.clauses('INSUFFICIENT')))

    def test_clauses_must_cover_the_text_in_order(self):
        self.assertTrue(self.errors('PASS', self.clauses()[:2]))
        self.assertTrue(self.errors('PASS', list(reversed(self.clauses()))))
        self.assertTrue(self.errors('PASS', None))

    def test_unversioned_reports_are_not_checked(self):
        self.assertEqual(self.errors('PASS', None, versioned=False), [])


if __name__ == '__main__':
    unittest.main()

"""REQ-D01 rows: clause split, obligation-only verdicts and worst-clause aggregation."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plan_review import build_review_plan
from validate_review import validate_review
from test_decoupling import fixture, ledger, mark_pass, rebind
from ledger4 import defect
from test_requirement_source import source, write

TEXT = '+3V3=3.3V±5%，环境0～50°C。电阻采购公差1%；元件按实际物料额定审查。'
OBLIGATION = '+3V3=3.3V±5%，环境0～50°C。'
PREMISES = ('电阻采购公差1%；', '元件按实际物料额定审查。')


class RequirementClauseTests(unittest.TestCase):
    def setUp(self):
        self.db, intent = fixture(('100nF',))
        doc = write('# 需求\n\n| ID | 当前要求 | 适用边界 |\n|---|---|---|\n| REQ-02 | %s | %s |\n'
                    % (OBLIGATION, ''.join(PREMISES)))
        intent['requirement_source'] = source(doc)
        intent['requirements'] = [{'id': 'REQ-02', 'categories': ['OUTPUT_SPEC'],
                                   'interpretation': '+3V3 轨稳压器输出精度与环境温度范围在图上的实现', 'status': 'CONFIRMED',
                                   'owners': [], 'no_owner_reason': '+3V3 由板外供入，U1 所在轨上没有变换器电路，需求行自判'}]
        rebind(self.db, intent)
        self.plan = build_review_plan(self.db, intent)
        # Every aspect row of the requirement splits the same original text.
        self.key = [c['id'] for c in self.plan['checks'] if c['rule'] == 'REQ-D01'][-1]

    def errors(self, result, clauses):
        report = ledger(self.plan, self.db)
        row = mark_pass(report, self.plan, self.key)
        if result == 'FAIL':
            row['severity'] = 'P2'
            defect(report, self.key, 'F-1', 'F-1', plan=self.plan)
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
        self.assertTrue(self.errors('PASS', []))

    def test_clauses_split_the_original_text_not_the_criterion(self):
        planned = next(c for c in self.plan['checks'] if c['id'] == self.key)
        self.assertTrue(self.errors('PASS', [{'text': planned['criterion'], 'kind': 'OBLIGATION', 'result': 'PASS'}]))

if __name__ == '__main__':
    unittest.main()

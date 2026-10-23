"""A gap blocks a row through a requirement clause only when the row is bound to that requirement (consistency
proposals of 2026-10-23, 1d).

On R5 one review blocked 163 rows through clauses of the requirement document: a configuration gap held open "CC
level matching", a magnetics gap held open "input thresholds", rows whose own question did not need the missing
number. A requirement clause now blocks only the requirement's own rows (REQ-D01 for it and the rows the plan bound
to it); any other row is blocked through the number the missing quantity enters: a numeric limit, a calculation
input, or a clause of a datasheet or standard.
"""
import copy
import unittest

from test_review_functions import ASPECT, aux_open, bias_function, ledger
from review_functions import requirement_edge_errors

REQ_DOC = '/project/需求/用户需求.md'
CLAUSE = {'id': 'r1', 'kind': 'MANDATORY_CLAUSE', 'source': '需求/用户需求.md', 'locator': 'REQ-PWR-01',
          'says': '辅助供电必须在全输入范围内维持控制器工作', 'applies': '全输入范围', 'use': '需求'}


def requirement_row(bound=()):
    return {'id': 'REQ-D01.FUNCTION.REQ-PWR-01', 'rule': 'REQ-D01', 'method': 'D', 'applicability': 'APPLICABLE',
            'object': {'requirement_id': 'REQ-PWR-01', 'aspect': 'FUNCTION'}, 'bound_checks': list(bound),
            'source_text': {'locator': REQ_DOC + ':12', 'columns': []}}


def setup(via, bound=()):
    fn = bias_function()
    fn['conditions'].append(copy.deepcopy(CLAUSE))
    fn['open'][0]['decides'][0]['via'] = via
    p, r, db = ledger(fn)
    p['checks'].append(requirement_row(bound))
    checks = {c['id']: c for c in r['checks']}
    return p, checks, r['functions']


class RequirementEdgeTests(unittest.TestCase):
    def test_a_requirement_clause_does_not_block_a_row_of_another_question(self):
        p, checks, functions = setup({'condition': 'r1'})
        errors = requirement_edge_errors(p, checks, functions)
        self.assertTrue(errors)
        self.assertTrue(all('REQ-PWR-01' in e and 'r1' in e for e in errors), errors)
        self.assertTrue(any('PWR-C02.BIAS-STARTUP.Q2' in e for e in errors), errors)

    def test_the_rows_bound_to_the_requirement_may_be_blocked_through_it(self):
        bound = ['PWR-C02.BIAS-STARTUP.Q2', 'PWR-C02.BIAS-RUN.Q2']
        p, checks, functions = setup({'condition': 'r1'}, bound)
        self.assertEqual(requirement_edge_errors(p, checks, functions), [])

    def test_a_number_blocks_any_row(self):
        p, checks, functions = setup({'condition': 'c3'})
        self.assertEqual(requirement_edge_errors(p, checks, functions), [])
        p, checks, functions = setup({'claim': 'BIAS-VCCMIN', 'input': 'v_aux_min'})
        self.assertEqual(requirement_edge_errors(p, checks, functions), [])

    def test_another_document_of_the_requirement_folder_is_a_requirement_document(self):
        for source in ('需求/工程规格.md', '/project/需求/工程规格.md'):
            p, checks, functions = setup({'condition': 'r1'})
            functions[0]['conditions'][-1]['source'] = source
            self.assertTrue(requirement_edge_errors(p, checks, functions), source)

    def test_a_clause_of_another_document_is_not_a_requirement_clause(self):
        p, checks, functions = setup({'condition': 'r1'})
        functions[0]['conditions'][-1]['source'] = 'evidence/ds/U1.txt'
        self.assertEqual(requirement_edge_errors(p, checks, functions), [])

    def test_validation_refuses_it(self):
        import validate_review as vr
        fn = bias_function()
        fn['conditions'].append(copy.deepcopy(CLAUSE))
        fn['open'][0]['decides'][0]['via'] = {'condition': 'r1'}
        p, r, db = ledger(fn)
        p['checks'].append(requirement_row())
        out = vr.validate_review(p, r, db)
        self.assertTrue(any('requirement clause' in e for e in out['errors']), out['errors'])


if __name__ == '__main__':
    unittest.main()

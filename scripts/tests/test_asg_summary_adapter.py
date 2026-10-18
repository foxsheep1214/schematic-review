"""Synthetic ASG parent/child inventories; no private design data."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from audit_document_summaries import audit


class AsgSummaryTest(unittest.TestCase):
    def setUp(self):
        root = Path('/tmp/codex-work/sr-source-fixes-tests')
        root.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.rows = [{'id': 'GROUP-A', 'conclusion': 'conditional', 'coverage': 'partial',
                      'assumptions': ['bounded model'], 'omitted_terms': ['dynamic term'],
                      'checks': [{'name': 'voltage'}, {'name': 'current'}]}]
        self.contract = {'schema_version': 1, 'calculations': [
            {'id': cid, 'claim': 'CONDITIONAL', 'inputs': {'x': {'evidence': [
                {'source': 'results.json', 'locator': 'GROUP-A / ' + name}]}}}
            for cid, name in [('CHECK-X', 'voltage'), ('CHECK-Y', 'current')]]}
        self.preflight = {'status': 'CONDITIONAL', 'errors': [], 'calculations': {
            cid: {'status': 'CONDITIONAL'} for cid in ['CHECK-X', 'CHECK-Y']}}
        self.text = '| 计算：上下界完整 / 只算了一部分 | 0 / 1 |\n| 计算结论：满足 / 有条件满足 / 不满足 | 0 / 1 / 0 |'

    def run_case(self, contract=True):
        for name, data in [('results.json', self.rows), ('contract.json', self.contract), ('preflight.json', self.preflight)]:
            (self.root / name).write_text(json.dumps(data))
        (self.root / 'report.md').write_text(self.text)
        return audit(self.root / 'results.json', self.root / 'preflight.json', [self.root / 'report.md'],
                     self.root / 'contract.json' if contract else None)

    def codes(self, r):
        return {f['code'] for f in r['findings']}

    def test_parent_count_not_child_count_and_citation_not_id_suffix(self):
        r = self.run_case()
        self.assertEqual(r['review_result'], 'PASS', r['findings'])
        self.assertEqual(r['actual']['claims']['total'], 1)
        self.assertEqual(r['adapter']['child_count'], 2)
        self.assertEqual(r['adapter']['links']['CHECK-X']['parent'], 'GROUP-A')

    def test_missing_contract_cannot_guess_relationship(self):
        r = self.run_case(False)
        self.assertEqual(r['review_result'], 'INSUFFICIENT')
        self.assertIn('ASG_MAPPING_REQUIRED', self.codes(r))
        self.assertNotIn('ID_SET_MISMATCH', self.codes(r))

    def test_condition_not_promoted_to_supported(self):
        for row in self.preflight['calculations'].values():
            row['status'] = 'SUPPORTED'
        for row in self.contract['calculations']:
            row['claim'] = 'SUPPORTED'
        self.assertEqual(self.run_case()['review_result'], 'PASS')
        self.rows[0]['conclusion'] = 'supported'
        self.assertIn('ROW_STATUS_MISMATCH', self.codes(self.run_case()))

    def test_child_failure_and_summary_typo_visible(self):
        self.preflight['calculations']['CHECK-X']['status'] = 'FAIL'
        r = self.run_case()
        self.assertIn('CHILD_STATUS_MISMATCH', self.codes(r))
        self.assertIn('ROW_STATUS_MISMATCH', self.codes(r))
        self.text = self.text.replace('0 / 1 / 0', '0 / 2 / 0')
        self.assertIn('SUMMARY_COUNT_MISMATCH', self.codes(self.run_case()))

    def test_coverage_count_is_separate_from_conclusion_count(self):
        self.text = self.text.replace('| 0 / 1 |', '| 1 / 0 |')
        self.assertIn('COVERAGE_COUNT_MISMATCH', self.codes(self.run_case()))

    def test_unmapped_wrong_source_and_missing_child_do_not_pass(self):
        for mutate in ('source', 'locator', 'missing'):
            with self.subTest(mutate=mutate):
                original = copy.deepcopy(self.contract)
                if mutate == 'missing':
                    self.contract['calculations'].pop()
                else:
                    self.contract['calculations'][0]['inputs']['x']['evidence'][0][mutate] = 'unknown'
                r = self.run_case()
                self.assertNotEqual(r['review_result'], 'PASS')
                self.assertIn('CHILD_COVERAGE_GAP', self.codes(r))
                self.contract = original

    def test_duplicate_parent_and_child_are_not_silently_collapsed(self):
        self.rows.append(copy.deepcopy(self.rows[0]))
        self.assertIn('DUPLICATE_ID', self.codes(self.run_case()))
        self.rows.pop()
        self.contract['calculations'].append(copy.deepcopy(self.contract['calculations'][0]))
        self.assertIn('DUPLICATE_ID', self.codes(self.run_case()))

    def test_unknown_child_status_keeps_gap(self):
        self.preflight['calculations']['CHECK-X']['status'] = 'UNKNOWN'
        self.assertEqual(self.run_case()['review_result'], 'INSUFFICIENT')

    def test_contract_is_not_executed_result(self):
        self.preflight = self.contract
        self.assertEqual(self.run_case()['review_result'], 'INSUFFICIENT')

    def test_malformed_row_state_or_evidence_cannot_crash_or_pass(self):
        self.rows[0]['conclusion'] = {'not': 'a state'}
        self.assertNotEqual(self.run_case()['review_result'], 'PASS')
        self.rows[0]['conclusion'] = 'conditional'
        self.contract['calculations'][0]['inputs']['x']['evidence'] = None
        self.assertNotEqual(self.run_case()['review_result'], 'PASS')

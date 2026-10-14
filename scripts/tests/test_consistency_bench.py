"""Consistency bench scoring: agreement, PASS/FAIL flips and override-gate violations."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCORE = Path(__file__).resolve().parents[2] / 'evals' / 'consistency_bench' / 'score.py'
sys.path.insert(0, str(SCORE.parent))
from build_pack import reviewer_output


class ScoreTests(unittest.TestCase):
    def run_score(self, runs, extra_specs=()):
        extra_specs = list(extra_specs)
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / 'pack').mkdir()
            specs = [{'id': 'DEV-C01.R1', 'spec': {'rule': 'DEV-C01', 'proposal': {'result': 'PASS'}}},
                     {'id': 'DEV-C03.U1', 'spec': {'rule': 'DEV-C03'}}] + extra_specs
            (tmp / 'pack' / 'rows.json').write_text(json.dumps({'rows': specs}))
            args = [sys.executable, '-B', str(SCORE), '--pack', str(tmp / 'pack'), '--out', str(tmp / 'out')]
            for label, verdicts in runs.items():
                path = tmp / (label.replace('/', '-') + '.json')
                path.write_text(json.dumps({'rows': [dict(id=k, **v) for k, v in verdicts.items()]}))
                args += ['--run', f'{label}={path}']
            subprocess.run(args, check=True, capture_output=True)
            return json.loads((tmp / 'out' / 'score.json').read_text())

    def test_agreement_flips_and_gate(self):
        result = self.run_score({
            'a/1': {'DEV-C01.R1': {'verdict': 'PASS'}, 'DEV-C03.U1': {'verdict': 'FAIL'}},
            'a/2': {'DEV-C01.R1': {'verdict': 'PASS'}, 'DEV-C03.U1': {'verdict': 'FAIL'}},
            'b/1': {'DEV-C01.R1': {'verdict': 'INSUFFICIENT'}, 'DEV-C03.U1': {'verdict': 'PASS'}},
        })
        self.assertEqual(result['within_agent'], 1.0)
        self.assertEqual(result['between_agent'], 0.0)
        self.assertEqual({f['id'] for f in result['flips']}, {'DEV-C03.U1'})
        self.assertEqual(result['runs']['b/1']['gate_violations'], ['DEV-C01.R1'])
        self.assertEqual(result['runs']['a/1']['gate_violations'], [])

    def test_coded_override_is_not_a_violation(self):
        result = self.run_score({'b/1': {
            'DEV-C01.R1': {'verdict': 'FAIL', 'proposal_override': {'code': 'STRESS_ABOVE_BOUND', 'reason': '12 V 外部输入'}},
            'DEV-C03.U1': {'verdict': 'PASS'}}})
        self.assertEqual(result['runs']['b/1']['gate_violations'], [])

    def test_requirement_rows_need_clause_aggregation(self):
        spec = {'id': 'REQ-D01.REQ-1', 'spec': {'rule': 'REQ-D01', 'criterion': 'A须≤1V。按手册审查。',
                                                'object': {'requirement_status': 'CONFIRMED'}}}
        good = [{'text': 'A须≤1V。', 'kind': 'OBLIGATION', 'result': 'PASS'}, {'text': '按手册审查。', 'kind': 'PREMISE'}]
        result = self.run_score({'a/1': {'DEV-C01.R1': {'verdict': 'PASS'}, 'DEV-C03.U1': {'verdict': 'PASS'},
                                         'REQ-D01.REQ-1': {'verdict': 'PASS', 'requirement_clauses': good}},
                                 'b/1': {'DEV-C01.R1': {'verdict': 'PASS'}, 'DEV-C03.U1': {'verdict': 'PASS'},
                                         'REQ-D01.REQ-1': {'verdict': 'FAIL', 'requirement_clauses': good}}}, [spec])
        self.assertEqual(result['runs']['a/1']['gate_violations'], [])
        self.assertEqual(result['runs']['b/1']['gate_violations'], ['REQ-D01.REQ-1'])


class PackHygieneTests(unittest.TestCase):
    def test_prior_review_outputs_are_detected(self):
        samples = {'a.tsv': 'id\tobject\tresult\n', 'b.log': '{"quality_screening": {}}',
                   'c.json': '{"generated_by": "check-catalog planner"}', 'd.json': '{"checks": [{"review_result": "PASS"}]}',
                   'ds.json': '{"file": "DRV8874.pdf", "title": "DRV8874"}', 'e.tsv': 'ref\tvalue\n'}
        with tempfile.TemporaryDirectory() as tmp:
            found = {}
            for name, text in samples.items():
                path = Path(tmp) / name
                path.write_text(text)
                found[name] = reviewer_output(path) is not None
        self.assertEqual(found, {'a.tsv': True, 'b.log': True, 'c.json': True, 'd.json': True,
                                 'ds.json': False, 'e.tsv': False})


if __name__ == '__main__':
    unittest.main()

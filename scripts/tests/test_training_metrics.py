"""训练指标（evals/training/scripts/metrics.py）：fix pair 召回按缺陷位置点名判定，门指标按基准结果计数。"""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('training_metrics', ROOT / 'evals/training/scripts/metrics.py')
metrics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metrics)


def pair(pid, refs, nets):
    return {'id': pid, 'defect_location': {'refs': refs, 'nets': nets}}


def write_board(rd, board, findings, objects):
    bdir = rd / 'reviews' / board
    bdir.mkdir(parents=True)
    json.dump({'findings': findings}, open(bdir / 'lint.json', 'w'))
    json.dump({'checks': [{'id': 'X.%d' % i, 'object': o} for i, o in enumerate(objects)]}, open(bdir / 'plan.json', 'w'))


class FixPairRecallTests(unittest.TestCase):
    def test_recall_counts_only_findings_and_rows_that_name_the_defect_location(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            write_board(rd, 'hit.before', [{'rule': 'RST-A01', 'kind': 'CANDIDATE', 'detail': '/EN: R4 上拉'}], [{'ref': 'R4'}])
            write_board(rd, 'miss.before', [{'rule': 'RST-A01', 'kind': 'CANDIDATE', 'detail': '/EN: R44 上拉'},
                                             {'rule': 'NET-A01', 'kind': 'INFO', 'detail': 'R4 挂残网'}], [{'ref': 'R44'}])
            m = metrics.fix_pair_recall(rd, [pair('hit', ['R4'], ['/EN']), pair('miss', ['R4'], []), pair('unreviewed', ['R9'], [])])
        self.assertEqual((m['pairs_total'], m['pairs_reviewed']), (3, 2))
        self.assertEqual(m['fix_pair_recall_cold'], 0.5)      # R44 不算 R4；INFO 不算检出
        self.assertEqual(m['fix_pair_recall_plan'], 0.5)
        self.assertIsNone(m['fix_pair_recall_hot'])

    def test_gates_count_failing_typical_rows_and_replay_mismatches(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp)
            json.dump({'b1': {'rows': [{'status': 'DETECTED'}, {'status': 'MISSED'}, {'status': 'UNCLASSIFIED'}]}}, open(rd / 'typical.json', 'w'))
            (rd / 'replay').mkdir()
            json.dump({'totals': {'MATCH': 3, 'MISMATCH': 2}}, open(rd / 'replay' / 'results.json', 'w'))
            g = metrics.gates(rd)
        self.assertEqual(g['typical_gate']['MISSED'], 1)
        self.assertEqual(g['typical_gate']['UNCLASSIFIED'], 1)
        self.assertEqual(g['replay_gate'], 2)


if __name__ == '__main__':
    unittest.main()

"""Ledger replay: real R3 ledgers still grade as the reviewers' own SR graded them."""
import gzip
import importlib.util
import re
import unittest
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2] / 'evals' / 'ledger_replay'
_spec = importlib.util.spec_from_file_location('ledger_replay', BENCH / 'replay.py')
replay = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(replay)


class LedgerReplayTests(unittest.TestCase):
    def test_every_record_matches_its_frozen_answer(self):
        expected = replay.json.loads((BENCH / 'expected.json').read_text(encoding='utf-8'))
        self.assertEqual(sorted(expected['records']), ['3924cd7', '4b3b406', 'd32855c'])
        for tag, record in expected['records'].items():
            verdict = replay.judge(replay.observe(tag), record)
            self.assertEqual({k: v for k, v in verdict.items() if v == 'MISMATCH'}, {}, tag)
            for field, deviation in record['known_deviations'].items():
                self.assertTrue(deviation['reason'].strip(), (tag, field))

    def test_fixtures_carry_no_machine_paths(self):
        for path in (BENCH / 'records').glob('*/*.json.gz'):
            text = gzip.decompress(path.read_bytes()).decode('utf-8')
            self.assertIsNone(re.search(r'/Users/|/home/|/private/|"/tmp/', text), path)


if __name__ == '__main__':
    unittest.main()

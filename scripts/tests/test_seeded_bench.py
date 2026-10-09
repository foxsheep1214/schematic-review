"""Seeded-bench mutators keep db.json internally consistent and hit their targets."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'evals' / 'seeded_bench'))
import mutators  # noqa: E402
from lint import Lint  # noqa: E402

BOARD = ROOT / 'scripts/tests/fixtures/esp32-poe-iso-revn-calibration/variant-db.json'


class SeededBenchTests(unittest.TestCase):
    def setUp(self):
        self.db = json.loads(BOARD.read_text())

    def test_mutants_keep_nets_and_pin_index_in_agreement(self):
        found = list(mutators.mutations(self.db))
        self.assertTrue({'D-GND-PIN', 'D-TVS-STUB', 'D-REF-ANNO'} <= {m.defect for m in found})
        for m in found:
            rebuilt = {}
            for node, net in m.db['pin2net'].items():
                rebuilt.setdefault(net, []).append(node)
            self.assertEqual({k: sorted(v) for k, v in rebuilt.items()}, m.db['nets'], m.note)
        self.assertEqual(json.loads(BOARD.read_text()), self.db)   # original untouched

    def test_tvs_stub_mutant_is_reported_at_the_site(self):
        stub = next(m for m in mutators.mutations(self.db) if m.defect == 'D-TVS-STUB')
        findings = Lint(stub.db).run()
        self.assertTrue([f for f in findings if f['rule'] == 'PRO-A01' and stub.refs[0] in f['detail']])


if __name__ == '__main__':
    unittest.main()

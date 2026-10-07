"""Reproducible author-net syntax adapter and external-input benchmark guards."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from parse_kicad import parse


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result


adapter = load('input_adapter', ROOT / 'evals/input_bench/adapt_author_net.py')
bench = load('input_benchmark', ROOT / 'evals/input_bench/run.py')
RAW = b'''(export (version D) (components (comp (ref R1) (value "1k"))) (nets (net (code 1) (name "Net-(R1-Pad1)") (node (ref R1) (pin 1))) (net (code 2) (name "GND") (node (ref R1) (pin 2)))))'''


class InputBenchmark(unittest.TestCase):
    def test_conversion_retains_exact_values_partitions_and_names(self):
        raw = adapter.adapt(RAW); db = parse(raw)
        self.assertEqual(db['parts']['R1']['value'], '1k')
        self.assertEqual(db['pin2net'], {'R1.1': 'Net-(R1-Pad1)', 'R1.2': 'GND'})
        self.assertEqual(raw, adapter.adapt(RAW))

    def test_truncated_multiple_root_duplicate_attributes_rejected(self):
        for raw in [RAW[:-1], RAW + RAW, RAW.replace(b'(ref R1) (value', b'(ref R1) (ref R2) (value')]:
            with self.assertRaises(ValueError): adapter.adapt(raw)

    def test_frozen_input_and_all_structural_mutations(self):
        raw = adapter.adapt(RAW)
        manifest = {'input_sha256': hashlib.sha256(raw).hexdigest(), 'source': {'kind': 'synthetic'}, 'graph': bench.graph(parse(raw))}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.xml'; path.write_bytes(raw)
            report = bench.run(path, manifest, ROOT / 'scripts')
            self.assertEqual(report['passed'], 4)
            path.write_bytes(raw + b'\n')
            with self.assertRaisesRegex(ValueError, 'frozen'): bench.run(path, manifest, ROOT / 'scripts')


if __name__ == '__main__':
    unittest.main()

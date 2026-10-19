import pathlib
import unittest

import importlib.util

ROOT = pathlib.Path(__file__).resolve().parents[2]
# Loaded under its own name: other benches also ship a module called run.py.
_spec = importlib.util.spec_from_file_location('hot_bench_run', ROOT / 'evals' / 'hot_bench' / 'run.py')
hot_bench = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hot_bench)


class HotBenchTest(unittest.TestCase):
    """Real boards with datasheet facts: each hot rule keeps its hand-classified answer on the board as
    published, and each single value or connection mutation flips the checks it names."""

    def test_every_case_and_mutation_matches_its_classified_answer(self):
        result = hot_bench.run(ROOT)
        wrong = ['%(case)s/%(variant)s %(check)s expected=%(expected)s actual=%(actual)s' % r
                 for r in result['rows'] if r['status'] != 'MATCH']
        self.assertEqual(wrong, [])

    def test_each_case_carries_a_mutation_that_must_fail(self):
        import json
        cases = json.loads((ROOT / 'evals' / 'hot_bench' / 'cases.json').read_text(encoding='utf-8'))['cases']
        sources = json.loads((ROOT / 'evals' / 'hot_bench' / 'sources.json').read_text(encoding='utf-8'))['documents']
        for case in cases:
            self.assertTrue(any('FAIL' in m['expected'].values() for m in case.get('mutations', [])), case['id'])
            for check in case['checks']:
                self.assertIn(check['source'], sources, check['id'])
                self.assertRegex(check['citation'], r'p\.\s?\d+', check['id'])


if __name__ == '__main__':
    unittest.main()

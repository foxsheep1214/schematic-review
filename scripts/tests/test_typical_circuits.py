"""Typical-circuit bench: every report on 33 real open boards is classified and still holds."""
from pathlib import Path
import contextlib
import importlib.util
import io
import json
import unittest

BENCH = Path(__file__).resolve().parents[2] / 'evals' / 'typical_circuits'
# Another bench also has run.py; load this one under its own name.
_spec = importlib.util.spec_from_file_location('typical_circuits_run', BENCH / 'run.py')
typical = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(typical)


class TypicalCircuitTests(unittest.TestCase):
    def test_cases_are_complete_and_sourced(self):
        cases = json.loads((BENCH / 'cases.json').read_text(encoding='utf-8'))['cases']
        sources = {s['id']: s for s in json.loads((BENCH / 'sources.json').read_text(encoding='utf-8'))['boards']}
        self.assertEqual({c['id'] for c in cases}, set(sources))
        for case in cases:
            self.assertTrue((BENCH / case['fixture']).is_file(), case['id'])
            self.assertTrue(sources[case['id']]['license'] and len(sources[case['id']]['commit']) == 40)
            for entry in case['known_false_alarms'] + case['fixed_false_alarms'] + case['expected']:
                self.assertTrue(entry['rule'] and entry['why'], (case['id'], entry))

    def test_current_sr_meets_every_classification(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = typical.main([])
        self.assertEqual(code, 0, out.getvalue()[-3000:])


if __name__ == '__main__':
    unittest.main()

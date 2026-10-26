"""The JSON examples of the intent, plan and results format references pass the gates they illustrate (SR self-check of 2026-10-24, 1.4).

A reviewer copies the examples; one the gate refuses teaches the wrong format. Placeholder paths and digests are the
only errors the intent example may raise, and its circuit decisions derive against a candidate file.
"""
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import circuit_decisions as cd
from plan_review import validate_intent
from review_functions import function_errors
from review_workflow import design_option
from test_circuit_decisions import accept_all, setup

REFERENCES = Path(__file__).resolve().parents[2] / 'references'
DOCS = [REFERENCES / name for name in ('intent-format.md', 'plan-format.md', 'results-format.md', 'gate-and-rerun.md')]
PLACEHOLDERS = ('不存在', 'is not readable', 'input_sha256 is required', 'pass the candidate file')


def examples():
    found = []
    for block in re.findall(r'```json\n(.*?)```', '\n'.join(d.read_text(encoding='utf-8') for d in DOCS), re.S):
        try:
            found.append(json.loads(block))
        except ValueError:
            pass
    return found


def functions():
    return [fn for d in examples() if isinstance(d, dict)
            for fn in (d['functions'] if 'functions' in d else [d] if str(d.get('id', '')).startswith('FN-') else [])]


class DocExampleTests(unittest.TestCase):
    def test_the_intent_example_passes_but_for_its_placeholders(self):
        intent = next(d for d in examples() if isinstance(d, dict) and 'schema_version' in d)
        errors = [e for e in validate_intent(intent) if not any(p in e for p in PLACEHOLDERS)]
        self.assertEqual(errors, [])
        self.assertNotIn('circuits', intent)

    def test_the_intent_examples_decisions_derive(self):
        intent = next(d for d in examples() if isinstance(d, dict) and 'circuit_decisions' in d)
        _, _, _, candidates = setup()
        named = {d['candidate']: d for d in intent['circuit_decisions'] if 'candidate' in d}
        added = [d for d in intent['circuit_decisions'] if 'candidate' not in d]
        _, errors = cd.derive(candidates, accept_all(candidates, **named) + added)
        self.assertEqual(errors, [])

    def test_the_function_examples_pass(self):
        found = functions()
        self.assertEqual(sorted(fn['id'] for fn in found), ['FN-BIAS', 'FN-QR'])
        for fn in found:
            self.assertEqual(function_errors({'functions': [fn]}), [], fn['id'])
            for item in fn['open']:
                self.assertEqual(design_option(item['key'], item['design_option'], set(), set()), [], item['key'])


if __name__ == '__main__':
    unittest.main()

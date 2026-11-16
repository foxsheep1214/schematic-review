"""Evolution, model dependencies and migration tests use synthetic review records."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plan_review import build_review_plan
from review_summary import categorized_summary
from validate_remediation import validate_remediation
from test_revision_impact import database, focused, entries, check
from test_remediation import ready, actionable
from validate_review import fingerprint
from validate_review import validate_review
from test_calculation_preflight import calculation
from test_validate_review import fixture


class EvolutionTests(unittest.TestCase):
    def test_model_source_reopens_unchanged_upstream_and_dependent_parts(self):
        db = database()
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'bias-model.txt'; path.write_text('supply bound 7V')
            checks = [check('A', 'R10'), check('B', 'R10'), check('C', 'R10')]
            intent = {'review_sources': [{'id': 'BIAS_MODEL', 'path': str(path), 'citation': 'calculation', 'refs': ['R1']}],
                      'review_dependencies': {'A': {'complete': True, 'citation': 'supply model', 'source_ids': ['BIAS_MODEL']},
                                              'B': {'complete': True, 'citation': 'gate charge budget', 'check_ids': ['A']}}}
            base = focused(db, checks, intent=intent)
            path.write_text('supply bound 5V')
            plan = focused(db, checks, intent=intent, old_db=db, old_plan=base)
            self.assertTrue(entries(plan)['A']['required'])
            self.assertIn('dependent-check:A', entries(plan)['B']['reasons'])
            self.assertFalse(entries(plan)['C']['required'])

    def test_unknown_model_source_stays_partial(self):
        plan = focused(database(), intent={'review_dependencies': {'DEV-C01.R1': {
            'complete': True, 'citation': 'model scope', 'source_ids': ['MISSING']}}})
        self.assertIn('unknown-source:MISSING', plan['check_dependencies']['DEV-C01.R1']['gaps'])

    def test_ready_cannot_hide_conditional_remediation(self):
        remediation = ready(); calc = remediation['calculation_preflight']['calculations'][0]
        calc['inputs']['vz']['basis'] = 'TYPICAL'
        calc.update(claim='CONDITIONAL', closure='Obtain guaranteed limit')
        self.assertTrue(validate_remediation('F', remediation, {'F'}, True))
        remediation['readiness'] = 'CONDITIONAL'
        remediation['prerequisites'] = [{'input': 'limit', 'reason': 'guarantee', 'how_to_obtain': 'vendor', 'acceptance': 'bounded'}]
        self.assertEqual(validate_remediation('F', remediation, {'F'}, True), [])

    def test_history_counts_do_not_inflate_current_passes(self):
        checks = {'A': {'review_result': 'PASS'}, 'H': {'review_result': 'NA'}}
        expected = {'A': {'rule': 'DEV-C01'}, 'H': {'rule': 'REQ-H02'}}
        result = categorized_summary(checks, expected, {}, {'tasks': []})
        self.assertEqual(result['current'], {'checks': 1, 'results': {'PASS': 1}})
        self.assertEqual(result['history']['checks'], 1)

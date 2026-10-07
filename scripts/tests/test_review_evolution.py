"""Evolution, model dependencies and migration tests use synthetic review records."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from review_engine import engine_identity, validate_engine
from revision_impact import validate_reverification
from plan_review import build_review_plan
from review_summary import categorized_summary
from validate_remediation import validate_remediation
from test_revision_impact import database, focused, entries, reviewed_records, check
from test_remediation import ready, actionable
from validate_review import validate_review, fingerprint
from test_calculation_preflight import calculation
from test_validate_review import fixture


class EvolutionTests(unittest.TestCase):
    def test_interface_explanations_and_metadata_do_not_change_rules(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); (root/'references').mkdir()
            (root/'SKILL.md').write_text('---\nname: sr\ndescription: before\n---\n## 审查纪律\nRespect limits\n## 与 ASG 的有状态工作流交接\nOld interface\n')
            (root/'references/workflow-handoff.md').write_text('old interface')
            before = engine_identity(root)
            (root/'SKILL.md').write_text('---\nname: sr\ndescription: clearer\n---\n## 审查纪律\nRespect limits\n## 与 ASG 的有状态工作流交接\nClearer interface\n')
            (root/'references/workflow-handoff.md').write_text('clearer interface')
            (root/'README.md').write_text('better explanation')
            self.assertEqual(before, engine_identity(root))
            (root/'SKILL.md').write_text('## 审查纪律\nIgnore limits\n')
            self.assertNotEqual(before['digest'], engine_identity(root)['digest'])

    def test_code_comments_and_docstrings_are_not_algorithm_changes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); (root/'scripts').mkdir(); (root/'SKILL.md').write_text('Rules')
            code=root/'scripts/check.py'
            code.write_text('"""old explanation"""\nLIMIT=5\n')
            before=engine_identity(root)
            code.write_text('# clearer explanation\n"""new docs"""\nLIMIT = 5\n')
            self.assertEqual(before, engine_identity(root))
            code.write_text('LIMIT=6\n')
            self.assertNotEqual(before['digest'], engine_identity(root)['digest'])

    def test_legacy_identity_cannot_claim_current_rule_equivalence(self):
        plan=focused(database())
        plan['review_engine']['schema_version']=1
        self.assertTrue(validate_engine(plan, True))

    def test_rule_bytes_not_git_head_and_tests_excluded(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); (root/'references').mkdir(); (root/'scripts/tests').mkdir(parents=True)
            (root/'SKILL.md').write_text('v1'); (root/'references/rule.md').write_text('limit1')
            before = engine_identity(root)
            (root/'scripts/tests/test.py').write_text('test-only')
            self.assertEqual(before, engine_identity(root))
            (root/'references/.DS_Store').write_bytes(b'finder')
            (root/'scripts/.pytest_cache').mkdir(); (root/'scripts/.pytest_cache/x').write_text('cache')
            (root/'scripts/rule.pyc').write_bytes(b'bytecode'); (root/'references/rule.md~').write_text('backup')
            self.assertEqual(before, engine_identity(root))  # OS/editor byproducts are not rules
            (root/'references/rule.md').write_text('limit2')
            self.assertNotEqual(before['digest'], engine_identity(root)['digest'])

    def test_changed_or_missing_old_engine_forces_full_current_review(self):
        db = database()
        for missing in (False, True):
            base = focused(db)
            if missing:
                del base['review_engine']
            else:
                base['review_engine']['digest'] = '0'*64
            plan = focused(db, old_db=db, old_plan=base)
            impact = plan['revision_impact']
            self.assertEqual(impact['strategy'], 'FULL_REVIEW')
            self.assertTrue(all(e['required'] for e in impact['entries']))
            self.assertFalse(impact['blocking_gaps'])  # evolution isn't an electrical evidence gap
            report = reviewed_records(plan, {'checks': [{'id': c['id']} for c in plan['checks']]})
            self.assertTrue(validate_reverification(plan, report, impact))
            for c in report['checks']:
                c['reverification'].update(evaluation_origin='CURRENT_REVIEW', engine_digest=plan['review_engine']['digest'])
            self.assertEqual(validate_reverification(plan, report, impact), [])
            report['checks'][0]['reverification']['evaluation_origin'] = 'PRIOR_RESULT_REUSE'
            self.assertTrue(validate_reverification(plan, report, impact))

    def test_old_manual_checks_cannot_sneak_through_same_revision_merge(self):
        db = database(); old = build_review_plan(db)
        old['review_engine']['digest'] = 'obsolete'
        with self.assertRaisesRegex(ValueError, 'changed/unknown SR rules'):
            build_review_plan(db, previous_plan=old)

    def test_saved_plan_must_match_live_rules(self):
        plan = focused(database())
        self.assertEqual(validate_engine(plan, True), [])
        plan['review_engine']['digest'] = 'obsolete'
        self.assertTrue(validate_engine(plan, True))
        self.assertTrue(validate_engine({}, True))

    def test_library_default_checks_shape_but_cli_requires_current(self):
        plan = focused(database()); plan['review_engine']['digest'] = 'obsolete'
        self.assertEqual(validate_engine(plan, False), [])
        self.assertTrue(validate_engine(plan, True))
        self.assertTrue(validate_engine({'review_engine': 'tampered'}, False))

    def test_actionable_results_require_remediation_version_2(self):
        p, r, db = actionable()
        p['review_engine'] = engine_identity(); r['plan_digest'] = fingerprint(p)
        self.assertEqual(validate_review(p, r, db, require_actionable=True)['errors'], [])
        r['remediation_version'] = 1
        errors = validate_review(p, r, db, require_actionable=True)['errors']
        self.assertTrue(any('remediation_version must be 2' in e for e in errors), errors)

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

    def test_cli_requires_current_engine(self):
        p, r, db = fixture()
        script = Path(__file__).resolve().parents[1]/'validate_review.py'
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for name, value in [('p', p), ('r', r)]:
                (root/name).write_text(json.dumps(value))
            command = [sys.executable, '-B', str(script), str(root/'p'), str(root/'r')]
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 2)

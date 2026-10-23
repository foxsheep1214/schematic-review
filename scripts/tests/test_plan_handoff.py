"""Two-run CLI handoff regressions (the second scan merges the first plan) on explicitly synthetic circuit conditions."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import catalog
from board_intent import input_fingerprint
from lint import Lint
from plan_review import build_review_plan
from validate_review import fingerprint, SCOPE
from validate_review import validate_review
import results_model
from ledger4 import defect as defect_item, frame_of, judged
from test_validate_review import E
from test_remediation import ready


class PlanHandoffTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.db = {'parts': {'U1': {'value': 'SYNTHETIC-IC', 'nc': False}},
            'nets': {'CONTROL': ['U1.1']}, 'pin2net': {'U1.1': 'CONTROL'},
            'pinname': {'U1.1': 'EN'}, 'pintype': {}, 'ref2page': {'U1': 1}, 'pseudo_nets': []}
        self.cold = build_review_plan(self.db, self.inventory_context(),
                                      lint_findings=Lint(self.db, None, self.inventory_context()).run())
        self.parent = next(c['id'] for c in self.cold['checks'] if c.get('rule') == 'RST-E01')

    def inventory_context(self):
        # These fixtures deliberately model only a signal input, not IC supply pins.
        # Declare that limited synthetic model instead of automatically passing a
        # new unresolved physical-device inventory. Frozen circuit data is untouched.
        return {'input_sha256': input_fingerprint(self.db),
                'assemblies': [{'id': 'synthetic-signal-only', 'citation': 'Stipulated input-only test model',
                                'population': {r: True for r in self.db['parts']}}],
                'decoupling': {'schema_version': 4, 'components': {'U1': {'kind': 'other',
                    'citation': 'Synthetic one-pin input stub; no supply terminal modeled in this ledger-handoff test'}}}}

    def merged(self, previous=None):
        return build_review_plan(self.db, self.inventory_context(),
                                 previous_plan=previous if previous is not None else self.cold)

    def write(self, name, value):
        path = self.root/name
        path.write_text(json.dumps(value))
        return path

    def cli(self, script, *args):
        result = subprocess.run([sys.executable, '-B', str(SCRIPTS/script), *map(str, args)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def runs(self, previous=None):
        db = self.write('db.json', self.db)
        intent = self.write('intent.json', self.inventory_context())
        self.cli('lint.py', db, '--intent', intent, '--plan-json', self.root/'cold.json', '--json', self.root/'lint-cold.json')
        if previous is not None:
            self.write('cold.json', previous)
        self.cli('lint.py', db, '--intent', intent,
                 '--merge-plan', self.root/'cold.json', '--plan-json', self.root/'final.json',
                 '--json', self.root/'lint-hot.json')
        read = lambda name: json.loads((self.root/name).read_text())
        return read('final.json'), [read('lint-cold.json'), read('lint-hot.json')]

    def report(self, plan, runs, defect=False):
        # Stipulated ledger fixture only; these records are not actual engineering conclusions.
        checks = []
        for p in plan['checks']:
            app = p['applicability']
            item = {'id': p['id'], 'applicability': app, 'review_result': 'PASS',
                'evidence_confidence': 'A', 'evidence': E, 'rationale': 'Stipulated synthetic review',
                'handoff': deepcopy(p['handoff'])}
            if app != 'APPLICABLE':
                item.update(applicability='NOT_APPLICABLE', review_result='NA', applicability_evidence=E)
            if item['handoff']['required']:
                item['handoff'].update(state='ACCEPTED', evidence=E)
            checks.append(item)
        report = {'requirement_clarifications': [], 'schema_version': results_model.SCHEMA_VERSION, 'functions': [],
            'plan_digest': fingerprint(plan), 'db_digest': fingerprint(self.db),
            'checks': checks, 'findings': [],
            'scope_checks': {d: next(p['id'] for p in plan['checks'] if p['rule'] == catalog.COVERAGE_RULES[d]) for d in SCOPE},
            'coverage': {'requirements': {},
                'components': {k: [self.parent] for k in self.db['parts']},
                'pins': {k: [self.parent] for k in self.db['pin2net']},
                'nets': {k: [self.parent] for k in self.db['nets']},
                'pages': {str(k): [self.parent] for k in self.db['ref2page'].values()}}}
        for item in checks:   # a passed frame member rests on a judgement of its frame
            fid, aspect = frame_of(plan, item['id'])
            if fid and item['review_result'] == 'PASS':
                judged(report, item['id'], fid, aspect, plan)
        if defect:
            target = self.parent
            next(x for x in checks if x['id'] == target)['severity'] = 'P1'
            defect_item(report, target, 'F1', 'F1', plan=plan)
            report['findings'] = [{'id': 'F1', 'kind': 'DEFECT', 'severity': 'P1', 'check_ids': [target],
                'location': {'pages': ['1'], 'refs': ['U1'], 'nets': ['CONTROL']},
                **{k: 'Synthetic condition' for k in ('title', 'observed', 'criterion', 'impact', 'scenario',
                      'root_cause', 'recommendation', 'verification', 'severity_reason')}, 'remediation': ready(),
                'figures': [{'kind': 'ACTUAL', 'source': 'figures/F1-actual.png', 'locator': 'p1 U1 area', 'caption': 'Synthetic actual circuit'}]}]
        return report

    def test_combined_cold_cli_preserves_standalone_plan(self):
        _, runs = self.runs()
        self.assertEqual(runs[0]['review_plan'], self.cold)

    def test_complete_passing_state_ledger_can_release(self):
        final, runs = self.runs()
        report = self.report(final, runs)
        result = validate_review(final, report, self.db, runs, require_actionable=True)
        self.assertTrue(result['valid'], result)
        self.assertEqual(result['release'], 'GO')

    def test_manual_check_retained_and_old_plan_not_mutated(self):
        context = self.inventory_context()   # a reviewer-added row is a registered rule gap
        context['rule_gaps'] = [{'id': 'MANUAL-RETURN-PATH', 'rule': 'PWR-T01', 'object': {'ref': 'U1'}, 'criterion': 'Review return path', 'missing': 'synthetic: no generated rule', 'basis': 'synthetic review note'}]
        self.inventory_context = lambda: deepcopy(context)
        previous = build_review_plan(self.db, context, lint_findings=Lint(self.db, None, context).run())
        manual = next(c for c in previous['checks'] if c.get('origin') == 'REVIEWER_ADDED')
        manual.update(review_result='PASS', evidence_confidence='A')
        manual['check_explanation'] = catalog.explanation('PWR-T01')
        snapshot = deepcopy(previous)
        final, runs = self.runs(previous)
        retained = next(c for c in final['checks'] if c['id'] == manual['id'])
        self.assertIsNone(retained['review_result'])
        self.assertEqual(previous, snapshot)
        report = self.report(final, runs, defect=True)
        report['checks'] = [c for c in report['checks'] if c['id'] != manual['id']]
        self.assertFalse(validate_review(final, report, self.db, runs)['valid'])

    def test_changed_netlist_or_criterion_cannot_merge_silently(self):
        previous = deepcopy(self.cold)
        previous['db_sha256'] = 'old-revision'
        with self.assertRaisesRegex(ValueError, 'db_sha256'):
            self.merged(previous)
        previous = deepcopy(self.cold)
        previous['checks'][0]['criterion'] = 'Changed requirement'
        with self.assertRaisesRegex(ValueError, 'criterion changed'):
            self.merged(previous)

    def test_duplicate_or_incomplete_manual_check_rejected(self):
        previous = deepcopy(self.cold)
        previous['checks'].append(deepcopy(previous['checks'][0]))
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.merged(previous)
        previous['checks'][-1] = {'id': 'MANUAL'}
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            self.merged(previous)
        previous['checks'][-1] = dict(deepcopy(previous['checks'][0]), id='NOT-A-RULE.MANUAL')
        with self.assertRaisesRegex(ValueError, 'ID 必须以'):
            self.merged(previous)
        previous['checks'][-1] = dict(deepcopy(previous['checks'][0]), id='CLK-Q01.MANUAL', method='T')
        with self.assertRaisesRegex(ValueError, 'method/domain'):
            self.merged(previous)

    def test_manual_handoff_refinement_is_not_silently_overwritten(self):
        previous = deepcopy(self.cold)
        previous['checks'][0]['handoff'].update(required=True, receivers=['Power owner'],
            constraint='Synthetic voltage drop below 20 mV', verification='Synthetic four-wire measurement')
        with self.assertRaisesRegex(ValueError, 'handoff details changed'):
            self.merged(previous)

    def test_lint_from_another_baseline_rejected(self):
        final, runs = self.runs()
        runs[0]['review_plan']['db_sha256'] = 'old-revision'
        report = self.report(final, runs, defect=True)
        self.assertFalse(validate_review(final, report, self.db, runs)['valid'])


if __name__ == '__main__':
    unittest.main()

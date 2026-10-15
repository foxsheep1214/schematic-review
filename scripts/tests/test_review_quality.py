"""Synthetic counterexamples: ledger consistency is not semantic correctness."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_validate_review import fixture, E
from validate_review import validate_review, fingerprint
from review_workflow import workflow


def unfinished():
    p, r, db = fixture()
    r['checks'][0].update(review_result='INSUFFICIENT', evidence_confidence='C',
                         missing_inputs=['Synthetic calculation not performed'],
                         potential_severity='P2', gap_cause='REVIEW_INCOMPLETE')
    return p, r, db


def staged(cause='REVIEW_INCOMPLETE', due='design_iteration'):
    p, r, db = unfinished()
    p['review_phase'] = 'design_iteration'
    r['plan_digest'] = fingerprint(p)
    r['checks'][0]['gap_cause'] = cause
    r.update(workflow_version=1, work_items=[{
        'id': 'W-1', 'title': 'Synthetic task', 'root_cause': 'Unfinished calculation',
        'reason': 'Synthetic independent input', 'next_action': 'Evaluate the local bound',
        'due_stage': due, 'check_ids': [r['checks'][0]['id']], 'evidence': E}])
    return p, r, db


def accepted_handoff(cause):
    p, r, db = staged(cause, 'prototype_verification')
    p['checks'][0]['handoff'] = {'required': True}
    r['plan_digest'] = fingerprint(p)
    r['checks'][0].update(potential_severity='P1', handoff={
        'required': True, 'state': 'ACCEPTED', 'scope': 'downstream_verification',
        'receivers': ['Synthetic PCB owner'], 'constraint': 'Controlled layout bound',
        'verification': 'Prototype measurement', 'evidence': E,
        'schematic_prerequisites': [r['checks'][1]['id']]})
    if cause is None:
        r['checks'][0].pop('gap_cause')
    return p, r, db


class CompletionGuardTests(unittest.TestCase):
    def test_unfinished_p2_never_releases(self):
        p, r, db = unfinished()
        out = validate_review(p, r, db)
        self.assertTrue(out['valid'], out)  # an honest partial ledger is valid
        self.assertEqual(out['release'], 'NO_GO')
        self.assertTrue(any('review work not completed' in s for s in out['blockers']))

    def test_unfinished_is_not_risk_acceptance_at_any_severity(self):
        for severity in ('P0', 'P1', 'P2', 'P3'):
            with self.subTest(severity=severity):
                p, r, db = unfinished()
                r['checks'][0].update(potential_severity=severity, disposition='ACCEPTED',
                    acceptance={k: 'synthetic record' for k in ('by', 'date', 'scope', 'reason', 'record')})
                self.assertEqual(validate_review(p, r, db)['release'], 'NO_GO')

    def test_unfinished_task_stays_in_current_round(self):
        p, r, db = staged()
        out = validate_review(p, r, db)
        self.assertTrue(out['valid'], out)
        self.assertEqual(out['workflow']['current_work_items'], ['W-1'])
        self.assertEqual(out['release'], 'NO_GO')

    def test_unfinished_task_cannot_be_deferred_to_freeze(self):
        p, r, db = staged(due='schematic_freeze')
        out = validate_review(p, r, db)
        self.assertFalse(out['valid'])
        self.assertTrue(any('unfinished review' in e for e in out['errors']))

    def test_explicit_electrical_gap_cannot_use_downstream_shortcut(self):
        for cause in ('EXTERNAL_DATA', 'DESIGN_OPEN', 'REVIEW_INCOMPLETE', 'USER_DEFERRED', None):
            with self.subTest(cause=cause):
                p, r, db = accepted_handoff(cause)
                out = validate_review(p, r, db)
                self.assertEqual(out['release'], 'NO_GO')

    def test_retired_downstream_gap_cause_is_rejected(self):
        # Pure downstream tests are stage NA (test_review_stage_scope); there is no INSUFFICIENT shortcut.
        p, r, db = accepted_handoff('DOWNSTREAM_VERIFICATION')
        self.assertFalse(validate_review(p, r, db)['valid'])

    def test_screening_is_integrated_without_changing_release(self):
        p, r, db = fixture()
        out = validate_review(p, r, db)
        self.assertTrue(out['valid'], out)
        self.assertEqual(out['quality_screening']['status'], 'NO_PATTERN_DETECTED')
        self.assertEqual(out['release'], 'GO')

    def test_incomplete_remains_visible_in_existing_cause_counts(self):
        p, r, db = unfinished()
        out = validate_review(p, r, db)
        self.assertEqual(out['insufficient_by_cause']['REVIEW_INCOMPLETE'], 1)
        bad = validate_review(None, {})
        self.assertFalse(bad['valid'])
        self.assertEqual(bad['release'], 'NO_GO')


def quality_fixture():
    p = {'checks': [
        {'id': 'DEV-C01.C1', 'rule': 'DEV-C01', 'method': 'C',
         'object': {'ref': 'C1'}, 'criterion': 'C1 voltage rating'},
        {'id': 'DEV-C02.C2', 'rule': 'DEV-C02', 'method': 'C',
         'object': {'ref': 'C2'}, 'criterion': 'C2 ripple qualification'}]}
    r = {'checks': [
        {'id': c['id'], 'review_result': 'INSUFFICIENT',
         'rationale': 'A shared generic paragraph; prototype thermal data absent.',
         'evidence': E} for c in p['checks']]}
    return p, r, {'parts': {'C1': {}, 'C2': {}, 'R1': {}}}


class QualityScreeningTests(unittest.TestCase):
    def setUp(self):
        from review_quality import screen_quality
        self.screen = screen_quality

    def test_cross_criterion_copy_is_visible_without_electrical_verdict(self):
        p, r, db = quality_fixture(); before = deepcopy((p, r, db))
        out = self.screen(p, r, db)
        self.assertEqual(out['status'], 'NEEDS_SEMANTIC_REVIEW')
        self.assertEqual(out['candidates'][0]['code'], 'REUSED_RATIONALE_ACROSS_SCOPES')
        self.assertEqual(set(out['candidates'][0]['check_ids']), {c['id'] for c in p['checks']})
        self.assertEqual((p, r, db), before)
        self.assertNotIn('release', out)

    def test_same_shared_source_with_distinct_reasons_is_not_flagged(self):
        p, r, db = quality_fixture()
        r['checks'][0]['rationale'] = 'C1 rating exceeds its bounded DC voltage.'
        r['checks'][1]['rationale'] = 'C2 ripple requires the measured frequency spectrum.'
        self.assertEqual(self.screen(p, r, db)['status'], 'NO_PATTERN_DETECTED')

    def test_wrong_explicit_ref_in_rationale_is_candidate(self):
        p, r, db = quality_fixture(); r['checks'] = r['checks'][:1]
        r['checks'][0]['rationale'] = 'C2 ripple specification proves this result.'
        self.assertIn('REFERENCED_OBJECT_OUTSIDE_SCOPE', [x['code'] for x in self.screen(p, r, db)['candidates']])

    def test_wrong_explicit_ref_in_evidence_locator_is_candidate(self):
        p, r, db = quality_fixture(); r['checks'] = r['checks'][:1]
        r['checks'][0].update(rationale='The component has the required rating.',
                             evidence=[{'source': 'synthetic-ledger.json', 'locator': 'refs.C2'}])
        self.assertEqual(self.screen(p, r, db)['candidates'][0]['observed_refs'], ['C2'])

    def test_dependency_refs_are_not_assumed_wrong(self):
        p, r, db = quality_fixture(); r['checks'] = r['checks'][:1]
        p['checks'][0]['object']['refs'] = ['C1', 'R1']
        r['checks'][0]['rationale'] = 'R1 bounds the charging current.'
        self.assertEqual(self.screen(p, r, db)['status'], 'NO_PATTERN_DETECTED')

    def test_requirement_criterion_can_supply_scope(self):
        p, r, db = quality_fixture(); r['checks'] = r['checks'][:1]
        p['checks'][0]['object'] = {'requirement_id': 'REQ-LIFE'}
        p['checks'][0]['criterion'] = 'C1寿命须覆盖任务剖面'
        r['checks'][0]['rationale'] = 'C2满足所需寿命。'
        self.assertEqual(self.screen(p, r, db)['candidates'][0]['expected_refs'], ['C1'])

    def test_ref_prefix_and_units_do_not_create_false_matches(self):
        p, r, db = quality_fixture(); r['checks'] = r['checks'][:1]
        r['checks'][0]['rationale'] = '100V; Rev.C2X, model_C2, C20 are not C2 references.'
        # Remove the deliberate final reference; partial tokens must not match C2.
        r['checks'][0]['rationale'] = r['checks'][0]['rationale'].split(' are not')[0]
        self.assertEqual(self.screen(p, r, db)['status'], 'NO_PATTERN_DETECTED')

    def test_q_and_history_boilerplate_are_excluded(self):
        p, r, db = quality_fixture()
        for i, c in enumerate(p['checks']):
            c['method'] = ('Q', 'H')[i]
        self.assertEqual(self.screen(p, r, db)['candidates'], [])

    def test_unknown_db_refs_are_not_invented(self):
        p, r, _ = quality_fixture(); r['checks'] = r['checks'][:1]
        r['checks'][0]['rationale'] = 'C2 data are cited.'
        self.assertEqual(self.screen(p, r, None)['status'], 'NO_PATTERN_DETECTED')

    def test_stable_output_and_malformed_rows_are_safe(self):
        p, r, db = quality_fixture()
        out = self.screen(p, r, db)
        p['checks'].reverse(); r['checks'].reverse()
        self.assertEqual(out, self.screen(p, r, db))
        self.assertEqual(self.screen(None, None)['status'], 'NOT_RUN')
        self.assertEqual(self.screen({'checks': [None]}, {'checks': [None]}, {})['candidates'], [])


def impact_fixture(n=12, grade='P1', text='Shared consequence for every row'):
    keys = [f'PWR-C02.N{i}' for i in range(n)]
    p = {'checks': [{'id': k, 'rule': 'PWR-C02', 'method': 'C', 'object': {'net': f'N{i}'},
                     'criterion': 'output window'} for i, k in enumerate(keys)]}
    r = {'checks': [{'id': k, 'review_result': 'INSUFFICIENT', 'gap_cause': 'EXTERNAL_DATA',
                     'potential_severity': grade, 'rationale': f'net N{i} lacks a bound',
                     'impact_assessment': {'consequence': text, 'severity_reason': f'path for N{i}'},
                     'evidence': E} for i, k in enumerate(keys)]}
    return p, r


class ImpactScreeningTests(unittest.TestCase):
    def setUp(self):
        from review_quality import screen_quality
        self.screen = screen_quality

    def codes(self, p, r):
        return {x['code'] for x in self.screen(p, r)['candidates']}

    def test_copied_consequence_and_uniform_grade_are_flagged(self):
        p, r = impact_fixture()
        self.assertEqual({'REUSED_IMPACT_ACROSS_SCOPES', 'UNIFORM_POTENTIAL_SEVERITY',
                          'UNIFORM_SEVERITY_WITHIN_RULE'}, self.codes(p, r))

    def test_templated_grade_sentence_across_rules_is_flagged(self):
        p, r = impact_fixture()
        rules = ('DEV-C01', 'PWR-C10', 'DRV-C02')
        for i, (c, row) in enumerate(zip(p['checks'], r['checks'])):
            c['rule'] = rules[i % 3]
            row['impact_assessment']['consequence'] = f'N{i} consequence'
            row['potential_severity'] = ('P1', 'P2')[i % 2]
            row['impact_assessment']['severity_reason'] = f'N{i} path。本行未建立独立损坏路径，按必需性能P1。'
        found = [x for x in self.screen(p, r)['candidates'] if x['code'] == 'TEMPLATED_SEVERITY_REASON']
        self.assertEqual(1, len(found))
        self.assertEqual(12, len(found[0]['check_ids']))
        for i, row in enumerate(r['checks']):
            row['impact_assessment']['severity_reason'] = f'N{i} 漏电经R{i}使门限偏移，按P1。'
        self.assertNotIn('TEMPLATED_SEVERITY_REASON', self.codes(p, r))

    def test_distinct_paths_and_mixed_grades_are_not_flagged(self):
        p, r = impact_fixture()
        for i, row in enumerate(r['checks']):
            row['impact_assessment']['consequence'] = f'N{i} consequence'
            row['potential_severity'] = ('P1', 'P2')[i % 2]
        self.assertEqual(set(), self.codes(p, r))

    def test_small_ledgers_and_history_rows_are_ignored(self):
        p, r = impact_fixture(n=5, text='x')
        for i, row in enumerate(r['checks']):
            row['impact_assessment']['consequence'] = f'N{i}'
        self.assertEqual(set(), self.codes(p, r))
        p, r = impact_fixture()
        for c in p['checks']:
            c['rule'] = 'REQ-H02'
        self.assertNotIn('UNIFORM_POTENTIAL_SEVERITY', self.codes(p, r))

class DownstreamTriageTests(unittest.TestCase):
    def codes(self, p, r):
        from review_quality import screen_quality
        return {x['code']: x for x in screen_quality(p, r)['candidates']}

    def test_test_only_gap_recorded_as_design_open_is_flagged(self):
        p, r = impact_fixture(n=2)
        r['checks'][0]['gap_cause'] = 'DESIGN_OPEN'
        r['checks'][0]['missing_inputs'] = ['闭壳温升与EMC传导实测结果']
        r['checks'][1]['gap_cause'] = 'DESIGN_OPEN'
        r['checks'][1]['missing_inputs'] = ['U1 偏置电阻未选，需样机前确定']
        found = self.codes(p, r)['DOWNSTREAM_RECORDED_AS_DESIGN_GAP']
        self.assertEqual([r['checks'][0]['id']], found['check_ids'])

    def test_optimization_goal_graded_p1_is_flagged(self):
        p, r = impact_fixture(n=2)
        p['checks'][0]['criterion'] = '万台物料成本优化目标60元'
        self.assertEqual([r['checks'][0]['id']], self.codes(p, r)['OPTIMIZATION_TARGET_AS_BLOCKING_GAP']['check_ids'])
        r['checks'][0]['potential_severity'] = 'P3'
        self.assertNotIn('OPTIMIZATION_TARGET_AS_BLOCKING_GAP', self.codes(p, r))


class FreezeGradingGateTests(unittest.TestCase):
    """Templated grading blocks release only in schematic_freeze; valid is unaffected."""

    def gate(self, phase):
        from unittest import mock
        import validate_review as vr
        from test_passive_stress import board, proposals
        from test_decoupling import ledger
        db, intent = board()
        if phase:
            intent['review_phase'] = phase
        plan, _ = proposals(db, intent)
        flagged = {'code': 'TEMPLATED_SEVERITY_REASON', 'check_ids': ['X'] * 12}
        fake = lambda *a, **k: {'candidates': [flagged]}
        with mock.patch.object(vr, 'screen_quality', fake):
            return vr.validate_review(plan, ledger(plan, db), db)

    def test_freeze_blocks_and_iteration_does_not(self):
        freeze = self.gate('schematic_freeze')
        self.assertTrue(any(b.startswith('TEMPLATED_SEVERITY_REASON') for b in freeze['blockers']))
        iteration = self.gate('design_iteration')
        self.assertFalse(any(b.startswith('TEMPLATED_SEVERITY_REASON') for b in iteration['blockers']))


if __name__ == '__main__':
    unittest.main()

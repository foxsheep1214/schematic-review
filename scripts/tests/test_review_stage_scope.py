"""Stage exclusions retain product obligations; unknown inputs stay actionable."""
import unittest
from test_validate_review import fixture, E
from test_review_quality import staged
from validate_review import validate_review
from review_stage_scope import OUTSIDE_STAGE, REQUEST_FIELDS, validate_stage_scope

INPUT = 'startup load current envelope'


def downstream():
    p, r, db = staged('EXTERNAL_DATA', 'prototype_verification')
    row = r['checks'][0]
    for field in ('missing_inputs', 'potential_severity', 'gap_cause'):
        row.pop(field, None)
    r['work_items'] = []
    row.update(review_result='NA', applicability='APPLICABLE', na_reason=OUTSIDE_STAGE, blocking=False, handoff={
        'required': True, 'state': 'OPEN', 'scope': 'downstream_verification',
        'receivers': ['Synthetic test engineer'], 'constraint': 'Retain controlled product test criterion',
        'verification': 'Measure prototype under controlled test configuration',
        'product_requirement_status': 'PENDING_VERIFICATION',
        'schematic_prerequisites': [r['checks'][1]['id']]})
    return p, r, db


def request():
    return {'why_decisive': 'Current and duration determine whether regulator current limit prevents startup',
            'required_scope': 'Peak amperes, pulse seconds and repetition at the specified supply limits',
            'acquisition': 'System engineer derives controlled bound from installed loads and their startup data',
            'closure_criterion': 'Recompute current-limit margin and startup voltage; compare with required rails'}


IMPACT = {k: 'Synthetic' for k in ('affected_function', 'operating_condition', 'consequence',
                                     'severity_reason', 'blocking_reason')}


def decisive():
    p, r, db = staged('EXTERNAL_DATA')
    r['checks'][0].update(missing_inputs=[INPUT], potential_severity='P1', blocking=True,
                          input_requests={INPUT: request()}, impact_assessment=dict(IMPACT))
    return p, r, db


def gate(p, r, db):
    # The gap contract rides on the impact contract used by every new review.
    r['impact_version'] = 1
    return validate_review(p, r, db, require_impact=True)


class StageScopeTests(unittest.TestCase):
    def test_stage_na_keeps_open_product_obligation_and_handoff(self):
        p, r, db = downstream()
        out = gate(p, r, db)
        self.assertTrue(out['valid'], out['errors'])
        self.assertEqual(out['stage_scope']['outside_schematic_stage'], [r['checks'][0]['id']])
        self.assertNotIn('INSUFFICIENT', out['summary']['results'])
        self.assertEqual(out['categorized_summary']['current']['results'].get('NA_OUTSIDE_STAGE'), 1)
        self.assertNotIn('NA', out['categorized_summary']['current']['results'])
        self.assertEqual(out['workflow']['current_work_items'], [])
        self.assertEqual(out['release'], 'NO_GO')  # handoff has not been accepted
        self.assertTrue(any('handoff not accepted' in b for b in out['blockers']))

    def test_accepted_handoff_can_release_schematic_not_product(self):
        p, r, db = downstream()
        r['checks'][0]['handoff'].update(state='ACCEPTED', evidence=E)
        out = gate(p, r, db)
        self.assertTrue(out['valid'], out['errors'])
        self.assertEqual(out['release'], 'GO')
        self.assertEqual(r['checks'][0]['handoff']['product_requirement_status'], 'PENDING_VERIFICATION')

    def test_stage_na_keeps_product_applicability(self):
        p, r, db = downstream()
        r['checks'][0].update(applicability='NOT_APPLICABLE', applicability_evidence=E)
        self.assertFalse(gate(p, r, db)['valid'])

    def test_prerequisite_is_graded_on_its_own_not_escalated_by_stage_na(self):
        for severity, blocking, expect in (('P3', False, 'GO'), ('P1', True, 'NO_GO')):
            with self.subTest(severity=severity):
                p, r, db = downstream()
                row = r['checks'][1]
                gap = decisive()[1]['checks'][0]
                row.update({k: v for k, v in gap.items() if k != 'id'})
                row.update(potential_severity=severity, blocking=blocking)
                r['work_items'] = [dict(gap_task(r), check_ids=[row['id']])]
                r['checks'][0]['handoff'].update(state='ACCEPTED', evidence=E)
                out = gate(p, r, db)
                self.assertTrue(out['valid'], out['errors'])
                self.assertFalse([b for b in out['blockers'] if r['checks'][0]['id'] in b], out['blockers'])
                self.assertEqual(any(row['id'] + ': unresolved blocking' in b for b in out['blockers']),
                                 expect == 'NO_GO', out['blockers'])

    def test_stage_na_requires_product_handoff_and_separate_prerequisites(self):
        for field in ('required', 'scope', 'product_requirement_status', 'schematic_prerequisites'):
            p, r, db = downstream()
            del r['checks'][0]['handoff'][field]
            self.assertFalse(gate(p, r, db)['valid'], field)
        p, r, db = downstream()
        r['checks'][0]['handoff']['schematic_prerequisites'] = [r['checks'][0]['id']]
        self.assertFalse(gate(p, r, db)['valid'])

    def test_truly_independent_test_may_have_justified_empty_prerequisites(self):
        p, r, db = downstream()
        h = r['checks'][0]['handoff']
        h['schematic_prerequisites'] = []
        self.assertFalse(gate(p, r, db)['valid'])
        h['no_schematic_prerequisites_reason'] = 'Independent enclosure cosmetic finish test has no electrical premise'
        self.assertTrue(gate(p, r, db)['valid'])

    def test_stage_na_cannot_keep_hidden_electrical_gap(self):
        for field, value in [('missing_inputs', ['unknown load']), ('potential_severity', 'P1'),
                             ('gap_cause', 'EXTERNAL_DATA'), ('blocking', True)]:
            p, r, db = downstream(); r['checks'][0][field] = value
            self.assertFalse(gate(p, r, db)['valid'], field)

    def test_stage_na_is_tracked_by_handoff_not_work_item(self):
        p, r, db = downstream()
        r['work_items'] = [dict(gap_task(r), due_stage='prototype_verification', check_ids=[r['checks'][0]['id']])]
        self.assertFalse(gate(p, r, db)['valid'])

    def test_decisive_gap_stays_insufficient_with_usable_request(self):
        p, r, db = decisive()
        out = gate(p, r, db)
        self.assertTrue(out['valid'], out['errors'])
        self.assertEqual(out['release'], 'NO_GO')
        self.assertEqual(out['stage_scope']['input_request_count'], 1)

    def test_request_must_have_each_actionable_field(self):
        for field in REQUEST_FIELDS:
            p, r, db = decisive()
            del r['checks'][0]['input_requests'][INPUT][field]
            self.assertFalse(gate(p, r, db)['valid'], field)

    def test_each_missing_input_has_exactly_one_request(self):
        p, r, db = decisive(); r['checks'][0]['missing_inputs'].append('fault restart duty cycle')
        self.assertFalse(gate(p, r, db)['valid'])
        p, r, db = decisive(); r['checks'][0]['input_requests']['unrelated input'] = request()
        self.assertFalse(gate(p, r, db)['valid'])

    def test_requests_only_for_real_input_or_design_gaps(self):
        for cause in ('REVIEW_INCOMPLETE', 'USER_DEFERRED'):
            with self.subTest(cause=cause):
                p, r, db = decisive(); r['checks'][0]['gap_cause'] = cause
                self.assertFalse(gate(p, r, db)['valid'])
                del r['checks'][0]['input_requests']
                self.assertTrue(gate(p, r, db)['valid'], gate(p, r, db)['errors'])

    def test_gap_cause_is_mandatory_under_contract_and_downstream_cause_is_retired(self):
        p, r, db = decisive(); del r['checks'][0]['gap_cause']
        self.assertFalse(gate(p, r, db)['valid'])
        p, r, db = decisive(); r['checks'][0]['gap_cause'] = 'DOWNSTREAM_VERIFICATION'
        self.assertFalse(validate_review(p, r, db)['valid'])

    def test_without_contract_requests_are_not_required(self):
        p, r, db = decisive(); del r['checks'][0]['input_requests']
        self.assertTrue(validate_review(p, r, db)['valid'], validate_review(p, r, db)['errors'])
        self.assertFalse(gate(p, r, db)['valid'])

    def test_malformed_requests_report_errors_without_crashing(self):
        for value in (None, {}, [None], [{}], {INPUT: None}, {INPUT: []}):
            p, r, db = decisive(); r['checks'][0]['input_requests'] = value
            self.assertFalse(gate(p, r, db)['valid'])

    def test_downstream_clause_requires_separate_handoff_check(self):
        p, r, db = downstream()
        parent = r['checks'][1]
        clause = {'text': 'prototype temperature test', 'kind': 'OBLIGATION', 'result': 'NA',
                  'na_reason': OUTSIDE_STAGE, 'check_ids': [r['checks'][0]['id']]}
        parent['requirement_clauses'] = [clause]
        rows = {x['id']: x for x in r['checks']}
        expected = {x['id']: x for x in p['checks']}
        errors, summary = validate_stage_scope(rows, expected)
        self.assertEqual(errors, [])
        self.assertEqual(summary['requirements_pending_downstream'], [parent['id']])
        clause['check_ids'] = []
        self.assertTrue(validate_stage_scope(rows, expected)[0])

    def test_ordinary_na_still_needs_not_applicable(self):
        p, r, db = fixture()
        r['checks'][0].update(review_result='NA', applicability='NOT_APPLICABLE',
                             na_reason='Controlled fixture excludes this function', applicability_evidence=E)
        out = validate_review(p, r, db)
        self.assertTrue(out['valid'], out['errors'])
        self.assertEqual(out['stage_scope']['not_applicable'], [r['checks'][0]['id']])
        r['checks'][0]['applicability'] = 'APPLICABLE'
        self.assertFalse(validate_review(p, r, db)['valid'])


def gap_task(r):
    return {'id': 'W-GAP', 'title': 'Synthetic task', 'root_cause': 'Synthetic input gap',
            'reason': 'Synthetic independent input', 'next_action': 'Obtain the bound',
            'due_stage': 'design_iteration', 'check_ids': [], 'evidence': E}


if __name__ == '__main__':
    unittest.main()

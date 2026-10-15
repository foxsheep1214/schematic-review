"""Stage exclusions retain product obligations; unknown inputs stay actionable."""
import unittest
from test_validate_review import fixture, fingerprint, E
from test_review_quality import staged
from validate_review import validate_review
from review_stage_scope import OUTSIDE_STAGE, REQUEST_FIELDS


def downstream():
    p, r, db = staged('DOWNSTREAM_VERIFICATION', 'prototype_verification')
    r['stage_scope_version'] = 1
    row = r['checks'][0]
    for field in ('missing_inputs', 'potential_severity', 'gap_cause'):
        row.pop(field, None)
    row.update(review_result='NA', applicability='NOT_APPLICABLE', na_reason=OUTSIDE_STAGE,
               applicability_evidence=E, blocking=False, handoff={
        'required': True, 'state': 'OPEN', 'scope': 'downstream_verification',
        'receivers': ['Synthetic test engineer'], 'constraint': 'Retain controlled product test criterion',
        'verification': 'Measure prototype under controlled test configuration',
        'product_requirement_status': 'PENDING_VERIFICATION',
        'schematic_prerequisites': [r['checks'][1]['id']]})
    return p, r, db


def decisive():
    p, r, db = staged('EXTERNAL_DATA')
    r['stage_scope_version'] = 1
    row = r['checks'][0]
    row.update(missing_inputs=['startup load current envelope'], potential_severity='P1', blocking=True,
               input_requests=[{
        'missing_input': 'startup load current envelope',
        'why_decisive': 'Current and duration determine whether regulator current limit prevents startup',
        'required_scope': 'Peak amperes, pulse seconds and repetition at the specified supply limits',
        'acquisition': 'System engineer derives controlled bound from installed loads and their startup data',
        'closure_criterion': 'Recompute current-limit margin and startup voltage; compare with required rails'}])
    return p, r, db


class StageScopeTests(unittest.TestCase):
    def test_stage_na_keeps_open_product_obligation_and_handoff(self):
        p, r, db = downstream()
        out = validate_review(p, r, db, require_stage_scope=True)
        self.assertTrue(out['valid'], out['errors'])
        self.assertEqual(out['stage_scope']['outside_schematic_stage'], [r['checks'][0]['id']])
        self.assertNotIn('INSUFFICIENT', out['summary']['results'])
        self.assertEqual(out['workflow']['current_work_items'], [])
        self.assertEqual(out['release'], 'NO_GO')  # handoff has not been accepted
        self.assertTrue(any('handoff not accepted' in b for b in out['blockers']))

    def test_accepted_handoff_can_release_schematic_not_product(self):
        p, r, db = downstream()
        r['checks'][0]['handoff'].update(state='ACCEPTED', evidence=E)
        out = validate_review(p, r, db)
        self.assertTrue(out['valid'], out['errors'])
        self.assertEqual(out['release'], 'GO')
        self.assertEqual(r['checks'][0]['handoff']['product_requirement_status'], 'PENDING_VERIFICATION')

    def test_na_does_not_hide_unknown_prerequisite(self):
        p, r, db = downstream()
        row = r['checks'][1]
        _, gap_report, _ = decisive()
        gap = gap_report['checks'][0]
        row.update({k: v for k, v in gap.items() if k != 'id'})
        r['work_items'].append(dict(r['work_items'][0], id='W-INPUT',
                                  due_stage='design_iteration', check_ids=[row['id']]))
        r['checks'][0]['handoff'].update(state='ACCEPTED', evidence=E)
        out = validate_review(p, r, db)
        self.assertTrue(out['valid'], out['errors'])
        self.assertEqual(out['release'], 'NO_GO')
        self.assertTrue(any('schematic prerequisite unresolved' in b for b in out['blockers']))

    def test_stage_na_requires_product_handoff_and_separate_prerequisites(self):
        for field in ('required', 'scope', 'product_requirement_status', 'schematic_prerequisites'):
            p, r, db = downstream()
            del r['checks'][0]['handoff'][field]
            self.assertFalse(validate_review(p, r, db)['valid'], field)
        p, r, db = downstream()
        r['checks'][0]['handoff']['schematic_prerequisites'] = [r['checks'][0]['id']]
        self.assertFalse(validate_review(p, r, db)['valid'])

    def test_truly_independent_test_may_have_justified_empty_prerequisites(self):
        p, r, db = downstream()
        h = r['checks'][0]['handoff']
        h['schematic_prerequisites'] = []
        self.assertFalse(validate_review(p, r, db)['valid'])
        h['no_schematic_prerequisites_reason'] = 'Independent enclosure cosmetic finish test has no electrical premise'
        self.assertTrue(validate_review(p, r, db)['valid'])

    def test_stage_na_cannot_keep_hidden_electrical_gap(self):
        for field, value in [('missing_inputs', ['unknown load']), ('potential_severity', 'P1'),
                             ('gap_cause', 'EXTERNAL_DATA'), ('blocking', True)]:
            p, r, db = downstream(); r['checks'][0][field] = value
            self.assertFalse(validate_review(p, r, db)['valid'], field)

    def test_na_requires_tracked_later_task(self):
        p, r, db = downstream(); r['work_items'] = []
        self.assertFalse(validate_review(p, r, db)['valid'])
        p, r, db = downstream(); r['work_items'][0]['due_stage'] = 'design_iteration'
        self.assertFalse(validate_review(p, r, db)['valid'])

    def test_decisive_gap_stays_insufficient_with_usable_request(self):
        p, r, db = decisive()
        out = validate_review(p, r, db)
        self.assertTrue(out['valid'], out['errors'])
        self.assertEqual(out['release'], 'NO_GO')
        self.assertEqual(out['stage_scope']['input_request_count'], 1)

    def test_request_must_have_each_actionable_field(self):
        for field in REQUEST_FIELDS:
            p, r, db = decisive()
            del r['checks'][0]['input_requests'][0][field]
            self.assertFalse(validate_review(p, r, db)['valid'], field)

    def test_no_missing_input_can_be_left_unaddressed(self):
        p, r, db = decisive(); r['checks'][0]['missing_inputs'].append('fault restart duty cycle')
        self.assertFalse(validate_review(p, r, db)['valid'])
        p, r, db = decisive(); r['checks'][0]['input_requests'] *= 2
        self.assertFalse(validate_review(p, r, db)['valid'])

    def test_new_reports_reject_old_downstream_insufficient(self):
        p, r, db = decisive(); r['checks'][0]['gap_cause'] = 'DOWNSTREAM_VERIFICATION'
        self.assertFalse(validate_review(p, r, db)['valid'])

    def test_legacy_readable_but_not_new_contract_complete(self):
        p, r, db = staged()
        self.assertTrue(validate_review(p, r, db)['valid'])
        self.assertFalse(validate_review(p, r, db, require_stage_scope=True)['valid'])
        p, r, db = fixture()
        self.assertFalse(validate_review(p, r, db, require_stage_scope=True)['valid'])

    def test_na_marker_cannot_be_used_without_contract_version(self):
        p, r, db = downstream(); del r['stage_scope_version']
        self.assertFalse(validate_review(p, r, db)['valid'])

    def test_malformed_requests_report_errors_without_crashing(self):
        for value in (None, {}, [None], [{}], [{'missing_input': []}]):
            p, r, db = decisive(); r['checks'][0]['input_requests'] = value
            self.assertFalse(validate_review(p, r, db)['valid'])

    def test_downstream_clause_requires_separate_handoff_check(self):
        from review_stage_scope import validate_stage_scope
        p, r, db = downstream()
        parent = r['checks'][1]
        clause = {'text': 'prototype temperature test', 'kind': 'OBLIGATION', 'result': 'NA',
                  'na_reason': OUTSIDE_STAGE, 'check_ids': [r['checks'][0]['id']]}
        parent['requirement_clauses'] = [clause]
        rows = {x['id']: x for x in r['checks']}
        expected = {x['id']: x for x in p['checks']}
        self.assertEqual(validate_stage_scope(r, rows, expected)[0], [])
        clause['check_ids'] = []
        self.assertTrue(validate_stage_scope(r, rows, expected)[0])

    def test_ordinary_na_reason_does_not_trigger_new_contract(self):
        p, r, db = fixture()
        r['checks'][0].update(review_result='NA', applicability='NOT_APPLICABLE',
                             na_reason='Controlled fixture excludes this function', applicability_evidence=E)
        self.assertTrue(validate_review(p, r, db)['valid'])


if __name__ == '__main__':
    unittest.main()

"""Stage exclusions retain product obligations; unknown inputs stay actionable."""
import unittest
from test_validate_review import fixture, E
from test_review_quality import staged
from validate_review import fingerprint, validate_review
from ledger4 import gap
from results_model import expand
from review_stage_scope import OUTSIDE_STAGE, REQUEST_FIELDS, validate_stage_scope

INPUT = 'startup load current envelope'


def downstream():
    p, r, db = fixture()
    p['review_phase'] = 'design_iteration'
    r['plan_digest'] = fingerprint(p)
    row = r['checks'][0]
    row.pop('evidence_confidence')
    row.update(review_result='NA', applicability='APPLICABLE', na_reason=OUTSIDE_STAGE, handoff={
        'required': True, 'state': 'OPEN', 'scope': 'downstream_verification',
        'receivers': ['Synthetic test engineer'], 'constraint': 'Retain controlled product test criterion',
        'verification': 'Measure prototype under controlled test configuration',
        'product_requirement_status': 'PENDING_VERIFICATION',
        'schematic_prerequisites': [r['checks'][1]['id']]})
    return p, r, db


REQUEST = {'scope': 'Peak amperes, pulse seconds and repetition at the specified supply limits',
           'acquisition': 'System engineer derives controlled bound from installed loads and their startup data',
           'closure': 'Recompute current-limit margin and startup voltage; compare with required rails'}


def decisive():
    p, r, db = staged('VENDOR_DATUM', level='P1', what=INPUT, **REQUEST)
    r['checks'][0]['rationale'] = 'Current and duration determine whether regulator current limit prevents startup'
    return p, r, db


def gate(p, r, db):
    return validate_review(p, r, db)


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
        self.assertEqual(out['release'], 'GO')  # an open handoff travels with the schematic, it does not block
        self.assertEqual(out['blockers'], [])

    def test_accepted_handoff_can_release_schematic_not_product(self):
        p, r, db = downstream()
        r['checks'][0]['handoff'].update(state='ACCEPTED', evidence=E)
        out = gate(p, r, db)
        self.assertTrue(out['valid'], out['errors'])
        self.assertEqual(out['release'], 'GO')
        self.assertEqual(r['checks'][0]['handoff']['product_requirement_status'], 'PENDING_VERIFICATION')

    def test_a_requirement_row_is_not_stage_na_as_a_whole(self):
        # 2026-10-21: one reviewer made REQ-D01.REQ-TEMP-001 and REQ-LIFE-001 stage NA whole, the other judged their
        # design obligations (temperature grades, life calculations) and passed them; the test clause alone is NA.
        p, r, db = downstream()
        p['checks'][0]['object'] = {'requirement_id': 'REQ-TEMP', 'feature': 'REQ-TEMP'}
        r['plan_digest'] = fingerprint(p)
        rows = {c['id']: c for c in expand(r)['checks']}
        errors, _ = validate_stage_scope(rows, {c['id']: c for c in p['checks']})
        self.assertTrue(any('a requirement row judges its design obligations' in e for e in errors), errors)
        p['checks'][0]['object'] = {'ref': 'U1'}
        errors, _ = validate_stage_scope(rows, {c['id']: c for c in p['checks']})
        self.assertFalse(any('requirement row' in e for e in errors), errors)

    def test_stage_na_keeps_product_applicability(self):
        p, r, db = downstream()
        r['checks'][0].update(applicability='NOT_APPLICABLE', applicability_evidence=E)
        self.assertFalse(gate(p, r, db)['valid'])

    def test_prerequisite_is_graded_on_its_own_not_escalated_by_stage_na(self):
        for level, blocking, expect in (('P3', False, 'GO'), ('P1', True, 'NO_GO')):
            with self.subTest(level=level):
                p, r, db = downstream()
                row = r['checks'][1]
                gap(r, row['id'], 'W-GAP', 'VENDOR_DATUM', plan=p, level=level, what=INPUT, title='Synthetic task',
                    why='Synthetic independent input', due_stage='design_iteration', **REQUEST)
                if not blocking:
                    row['blocking'] = False
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
                             ('gap_cause', 'EXTERNAL_DATA'), ('gaps', [{'what': 'unknown load'}]), ('blocking', True)]:
            p, r, db = downstream(); r['checks'][0][field] = value
            self.assertFalse(gate(p, r, db)['valid'], field)

    def test_stage_na_is_tracked_by_handoff_not_work_item(self):
        p, r, db = decisive()
        r['checks'][1].update(review_result='NA', applicability='APPLICABLE', na_reason=OUTSIDE_STAGE,
                              open_ref=r['checks'][0]['open_ref'])
        self.assertFalse(gate(p, r, db)['valid'])

    def test_decisive_gap_stays_insufficient_with_usable_request(self):
        p, r, db = decisive()
        out = gate(p, r, db)
        self.assertTrue(out['valid'], out['errors'])
        self.assertEqual(out['release'], 'NO_GO')
        self.assertEqual(out['stage_scope']['input_request_count'], 1)

    def test_a_request_gap_needs_each_actionable_field(self):
        for field in ('scope', 'acquisition', 'closure', 'checked', 'why_insufficient', 'worst_case'):
            p, r, db = decisive()
            del r['functions'][0]['open'][0][field]
            self.assertFalse(gate(p, r, db)['valid'], field)

    def test_each_open_item_key_is_unique_across_functions(self):
        p, r, db = decisive()
        twin = dict(r['functions'][0], id='FN-TWIN')
        r['functions'].append(twin)
        self.assertFalse(gate(p, r, db)['valid'])

    def test_requests_only_for_real_input_or_design_gaps(self):
        for kind in ('REVIEW_INCOMPLETE', 'USER_DEFERRED'):
            with self.subTest(kind=kind):
                p, r, db = decisive()
                item = r['functions'][0]['open'][0]
                item['kind'] = kind
                if kind == 'USER_DEFERRED':
                    item['instruction'] = E
                self.assertFalse(gate(p, r, db)['valid'])
                for field in ('acquisition', 'closure', 'checked', 'why_insufficient', 'worst_case'):
                    item.pop(field, None)
                self.assertTrue(gate(p, r, db)['valid'], gate(p, r, db)['errors'])

    def test_kind_is_mandatory_and_downstream_kind_is_retired(self):
        p, r, db = decisive(); del r['functions'][0]['open'][0]['kind']
        self.assertFalse(gate(p, r, db)['valid'])
        p, r, db = decisive(); r['functions'][0]['open'][0]['kind'] = 'DOWNSTREAM_VERIFICATION'
        self.assertFalse(validate_review(p, r, db)['valid'])

    def test_malformed_requests_report_errors_without_crashing(self):
        for field in ('scope', 'acquisition', 'closure', 'checked', 'worst_case'):
            for value in (None, {}, [None], [{}], 3):
                with self.subTest(field=field, value=value):
                    p, r, db = decisive(); r['functions'][0]['open'][0][field] = value
                    self.assertFalse(gate(p, r, db)['valid'])

    def test_downstream_clause_requires_separate_handoff_check(self):
        p, r, db = downstream()
        parent = r['checks'][1]
        clause = {'text': 'prototype temperature test', 'kind': 'OBLIGATION', 'result': 'NA',
                  'na_reason': OUTSIDE_STAGE, 'check_ids': [r['checks'][0]['id']]}
        parent['requirement_clauses'] = [clause]
        rows = {x['id']: x for x in expand(r)['checks']}
        expected = {x['id']: x for x in p['checks']}
        errors, summary = validate_stage_scope(rows, expected)
        self.assertEqual(errors, [])
        self.assertEqual(summary['requirements_pending_downstream'], [parent['id']])
        rows[parent['id']]['requirement_clauses'][0]['check_ids'] = []
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


if __name__ == '__main__':
    unittest.main()

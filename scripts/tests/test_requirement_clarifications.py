"""Requirement decision reporting and freeze gates; all evidence is synthetic."""
import copy
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from validate_review import validate_review, fingerprint
from test_validate_review import fixture, planned, E

REQ = 'REQ-D01.REQ-LOAD'
POWER = 'PWR-C05.U1'
PROOF = 'PWR-C01.VOUT'


def sample():
    p, r, db = fixture(REQ)
    p['review_phase'] = 'design_iteration'
    p['checks'][0]['object'] = {'requirement_id': 'REQ-LOAD', 'requirement_status': 'OPEN'}
    p['checks'].append(planned(POWER))
    r['checks'].append(copy.deepcopy(r['checks'][0]))
    r['checks'][-1]['id'] = POWER
    for row in (r['checks'][0], r['checks'][-1]):
        row.update(review_result='INSUFFICIENT', gap_cause='REQUIREMENT_OPEN',
                   evidence_confidence='C', missing_inputs=['maximum load current'], blocking=True)
    r['plan_digest'] = fingerprint(p)
    r['coverage']['requirements'] = {'REQ-LOAD': [REQ]}
    r.update(workflow_version=1, work_items=[], requirement_clarification_version=1,
             requirement_clarifications=[{
                 'id': 'CL-LOAD', 'title': 'Decide maximum load', 'kind': 'MISSING', 'status': 'OPEN',
                 'question': 'Controlled requirement leaves maximum load undecided',
                 'decision_needed': 'Select and confirm the supported load range',
                 'owner': 'System requirements owner', 'decision_due': 'BEFORE_DESIGN',
                 'closure_criteria': 'Confirmed requirement revision and re-review of affected checks',
                 'requirement_ids': ['REQ-LOAD'], 'check_ids': [REQ, POWER], 'evidence': E,
                 'freeze_impact': 'BLOCKING', 'impact_reason': 'Load determines loss and current rating'}])
    return p, r, db


def covered(p, r):
    p['checks'].append(planned(PROOF))
    r['checks'].append(dict(copy.deepcopy(r['checks'][1]), id=PROOF))
    issue = r['requirement_clarifications'][0]
    issue.update(freeze_impact='COVERED', decision_due='FOLLOW_UP',
                 coverage={'candidate_scope': 'Only 1 A or 2 A, stipulated by synthetic requirement owner',
                           'rationale': 'Separate electrical check covers the whole 1 to 2 A range',
                           'check_ids': [PROOF], 'evidence': E})
    for row in r['checks']:
        if row['id'] in (REQ, POWER):
            row['blocking'] = False
    r['plan_digest'] = fingerprint(p)


class RequirementClarificationTests(unittest.TestCase):
    def test_one_question_two_checks_one_current_task_not_two_defects(self):
        p, r, db = sample()
        out = validate_review(p, r, db)
        self.assertTrue(out['valid'], out)
        self.assertEqual(out['release'], 'NO_GO')
        self.assertEqual(out['summary']['confirmed_defects'], 0)
        self.assertEqual(out['requirement_clarification_summary']['open'], 1)
        self.assertEqual(out['requirement_clarification_summary']['affected_checks'], 2)
        self.assertEqual(out['workflow']['current_work_items'], ['CL-LOAD'])
        self.assertEqual(out['workflow']['unique_work_items'], 1)
        self.assertEqual(len(out['blockers']), 1)

    def test_covered_candidates_allow_freeze_but_do_not_confirm_requirement(self):
        p, r, db = sample(); covered(p, r)
        out = validate_review(p, r, db)
        self.assertTrue(out['valid'], out)
        self.assertEqual(out['release'], 'GO')
        self.assertEqual(out['requirement_clarification_summary']['covered_open'], 1)
        self.assertEqual(r['checks'][0]['review_result'], 'INSUFFICIENT')
        self.assertEqual(out['workflow']['current_work_items'], ['CL-LOAD'])

    def test_unsubstantiated_nonblocking_decision_is_rejected(self):
        for field in ('check_ids', 'candidate_scope', 'evidence', 'rationale'):
            with self.subTest(field=field):
                p, r, db = sample(); covered(p, r)
                del r['requirement_clarifications'][0]['coverage'][field]
                self.assertFalse(validate_review(p, r, db)['valid'])
        p, r, db = sample(); covered(p, r)
        r['requirement_clarifications'][0]['coverage']['check_ids'] = [REQ]
        self.assertFalse(validate_review(p, r, db)['valid'])

    def test_link_coverage_and_duplicate_ids_are_enforced(self):
        for mutate in (
            lambda r: r['requirement_clarifications'].clear(),
            lambda r: r['requirement_clarifications'][0].update(check_ids=[REQ]),
            lambda r: r['requirement_clarifications'][0].update(check_ids=[REQ, REQ]),
            lambda r: r['requirement_clarifications'][0].update(check_ids=['UNKNOWN']),
            lambda r: r['requirement_clarifications'].append(copy.deepcopy(r['requirement_clarifications'][0])),
        ):
            p, r, db = sample(); mutate(r)
            self.assertFalse(validate_review(p, r, db)['valid'])

    def test_requirement_is_not_given_a_defect_grade_or_waived_as_risk(self):
        for extra in ({'potential_severity': 'P1'}, {'blocking': False},
                      {'disposition': 'ACCEPTED', 'acceptance': {k: 'synthetic' for k in ('by', 'date', 'scope', 'reason', 'record')}}):
            p, r, db = sample(); r['checks'][0].update(extra)
            self.assertFalse(validate_review(p, r, db)['valid'])
        p, r, db = sample(); r['requirement_clarifications'][0]['severity'] = 'P3'
        self.assertFalse(validate_review(p, r, db)['valid'])

    def test_clarification_cannot_absorb_an_electrical_evidence_gap(self):
        p, r, db = sample()
        r['checks'][-1].update(gap_cause='EXTERNAL_DATA', potential_severity='P1')
        self.assertFalse(validate_review(p, r, db)['valid'])

    def test_two_decisions_on_one_check_combine_blocking_effect(self):
        p, r, db = sample(); covered(p, r)
        second = copy.deepcopy(r['requirement_clarifications'][0])
        second.update(id='CL-TRANSIENT', title='Confirm transient load duration', check_ids=[POWER],
                      freeze_impact='BLOCKING', decision_due='BEFORE_DESIGN')
        second.pop('coverage')
        r['requirement_clarifications'].append(second)
        r['checks'][-2]['blocking'] = True  # POWER precedes appended proof
        out = validate_review(p, r, db)
        self.assertTrue(out['valid'], out)
        self.assertEqual(out['release'], 'NO_GO')
        self.assertEqual(out['requirement_clarification_summary']['open'], 2)
        self.assertEqual(out['requirement_clarification_summary']['affected_checks'], 2)

    def test_no_duplicate_work_item_for_a_requirement_question(self):
        p, r, db = sample()
        r['work_items'] = [{'id': 'W-DUP', 'title': 'same question', 'root_cause': 'same load',
                            'check_ids': [REQ], 'due_stage': 'design_iteration', 'reason': 'same reason',
                            'next_action': 'same decision', 'evidence': E}]
        self.assertFalse(validate_review(p, r, db)['valid'])

    def test_resolution_requires_decision_record_and_current_reverification(self):
        p, r, db = sample()
        issue = r['requirement_clarifications'][0]
        issue['status'] = 'RESOLVED'
        self.assertFalse(validate_review(p, r, db)['valid'])
        issue['closure'] = {'by': 'Synthetic owner', 'date': '2026-10-06', 'decision': 'Maximum 2 A',
                            'requirement_revision': 'Synthetic Rev B', 'evidence': E, 'reverification': E}
        p['checks'][0]['object']['requirement_status'] = 'CONFIRMED'
        r['plan_digest'] = fingerprint(p)
        for row in (r['checks'][0], r['checks'][-1]):
            row.update(review_result='PASS', evidence_confidence='A', blocking=False)
            row.pop('gap_cause'); row.pop('missing_inputs')
        out = validate_review(p, r, db)
        self.assertTrue(out['valid'], out)
        self.assertEqual(out['release'], 'GO')
        self.assertEqual(out['requirement_clarification_summary']['resolved'], 1)
        self.assertEqual(out['workflow']['current_work_items'], [])
        del issue['closure']['reverification']
        self.assertFalse(validate_review(p, r, db)['valid'])

    def test_independent_electrical_failure_still_blocks_covered_requirements(self):
        p, r, db = sample(); covered(p, r)
        fid, key = 'F1', 'DEV-C01.BOARD'
        p['checks'].append(planned(key)); r['plan_digest'] = fingerprint(p)
        row = copy.deepcopy(r['checks'][1])
        row.update(id=key, review_result='FAIL', severity='P1', finding_id=fid, blocking=True)
        r['checks'].append(row)
        r['findings'] = [{'id': fid, 'kind': 'DEFECT', 'severity': 'P1', 'check_ids': [key],
                          'location': {'pages': ['1'], 'refs': ['R1'], 'nets': ['A']},
                          **{k: 'synthetic exceeded rating' for k in ('title','observed','criterion','impact','scenario','root_cause',
                                                                     'recommendation','verification','severity_reason')}}]
        r['work_items'] = [{'id': 'W-F1', 'title': 'Repair rating', 'root_cause': 'undersized part', 'check_ids': [key],
                            'due_stage': 'design_iteration', 'reason': 'exceeded rating', 'next_action': 'replace', 'evidence': E}]
        out = validate_review(p, r, db)
        self.assertTrue(out['valid'], out)
        self.assertEqual(out['release'], 'NO_GO')
        self.assertEqual(out['summary']['confirmed_defects'], 1)

    def test_old_reports_and_missing_contract_fields_are_rejected(self):
        p, r, db = sample(); del r['requirement_clarification_version']
        self.assertFalse(validate_review(p, r, db)['valid'])
        p, r, db = fixture()
        self.assertTrue(validate_review(p, r, db)['valid'])
        del r['requirement_clarification_version']; del r['requirement_clarifications']
        self.assertFalse(validate_review(p, r, db)['valid'])

    def test_new_report_with_no_questions_has_zero_summary(self):
        p, r, db = fixture()
        r.update(requirement_clarification_version=1, requirement_clarifications=[],
                 workflow_version=1, work_items=[])
        out = validate_review(p, r, db)
        self.assertTrue(out['valid'], out)
        self.assertEqual(out['release'], 'GO')
        self.assertEqual(out['requirement_clarification_summary']['total'], 0)

    def test_candidate_coverage_cannot_reference_unresolved_or_unknown_check(self):
        for proof_id in ('UNKNOWN', POWER):
            p, r, db = sample(); covered(p, r)
            r['requirement_clarifications'][0]['coverage']['check_ids'] = [proof_id]
            self.assertFalse(validate_review(p, r, db)['valid'])

    def test_resolved_question_does_not_clear_new_electrical_evidence_gap(self):
        p, r, db = sample()
        p['checks'][0]['object']['requirement_status'] = 'CONFIRMED'
        r['plan_digest'] = fingerprint(p)
        r['checks'][0].update(review_result='PASS', evidence_confidence='A', blocking=False)
        r['checks'][0].pop('gap_cause'); r['checks'][0].pop('missing_inputs')
        r['checks'][-1].update(gap_cause='EXTERNAL_DATA', potential_severity='P1', missing_inputs=['applicable part rating'])
        issue = r['requirement_clarifications'][0]
        issue.update(status='RESOLVED', closure={'by': 'Synthetic owner', 'date': '2026-10-06',
                     'decision': 'Confirmed 2 A', 'requirement_revision': 'Rev B', 'evidence': E, 'reverification': E})
        r['work_items'] = [{'id': 'W-DATA', 'title': 'Get rating', 'root_cause': 'datasheet absent',
                            'check_ids': [POWER], 'due_stage': 'design_iteration', 'reason': 'required rating unknown',
                            'next_action': 'read applicable datasheet', 'evidence': E}]
        out = validate_review(p, r, db)
        self.assertTrue(out['valid'], out)
        self.assertEqual(out['release'], 'NO_GO')
        self.assertEqual(out['workflow']['current_work_items'], ['W-DATA'])

    def test_retraction_needs_correction_and_current_plan(self):
        p, r, db = sample()
        issue = r['requirement_clarifications'][0]
        issue.update(status='RETRACTED', closure={'by': 'Synthetic reviewer', 'date': '2026-10-06',
                     'decision': 'Previously overlooked Rev A already states 2 A', 'requirement_revision': 'Rev A',
                     'evidence': E, 'reverification': E})
        for row in (r['checks'][0], r['checks'][-1]):
            row.update(review_result='PASS', evidence_confidence='A', blocking=False)
            row.pop('gap_cause'); row.pop('missing_inputs')
        self.assertFalse(validate_review(p, r, db)['valid'])
        p['checks'][0]['object']['requirement_status'] = 'CONFIRMED'
        r['plan_digest'] = fingerprint(p)
        self.assertTrue(validate_review(p, r, db)['valid'])

    def test_malformed_question_fields_return_validation_errors(self):
        for field in ('id', 'kind', 'status', 'owner', 'evidence', 'check_ids', 'requirement_ids', 'decision_due', 'freeze_impact'):
            for value in (None, 3, {}, [None]):
                with self.subTest(field=field, value=value):
                    p, r, db = sample()
                    r['requirement_clarifications'][0][field] = value
                    self.assertFalse(validate_review(p, r, db)['valid'])

    def test_cli_enforces_new_contract(self):
        p, r, db = sample()
        script = pathlib.Path(__file__).resolve().parents[1] / 'validate_review.py'
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            for name, data in (('plan', p), ('report', r)):
                (root/name).write_text(json.dumps(data))
            args = [sys.executable, '-B', str(script), str(root/'plan'), str(root/'report')]
            run = subprocess.run(args, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertEqual(json.loads(run.stdout)['requirement_clarification_summary']['open'], 1)
            run = subprocess.run(args + ['--require-release'], capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)


if __name__ == '__main__':
    unittest.main()

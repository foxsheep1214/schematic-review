import copy
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import catalog
from electrical_contract import PLAN_SCHEMA_VERSION
from validate_review import validate_review, fingerprint, SCOPE

E = [{'source': 'synthetic-fixture.json', 'locator': 'all values stipulated for tests'}]
C1, C2 = 'RST-E01.C1', 'RST-E01.C2'


def scope_id(dimension):
    return catalog.COVERAGE_RULES[dimension] + '.' + dimension.upper()


def planned(key):
    rule = key.split('.')[0]
    return {'id': key, 'rule': rule, 'method': catalog.method_of(rule),
            'domain': catalog.domain_of(rule), 'applicability': 'APPLICABLE', 'object': {}}


def fixture(first_key=C1):
    keys = [first_key] + [scope_id(k) for k in sorted(SCOPE)]
    plan = {'schema_version': PLAN_SCHEMA_VERSION, 'checks': [planned(k) for k in keys]}
    db = {'parts': {'R1': {}}, 'pin2net': {'R1.1': 'A'}, 'nets': {'A': ['R1.1']},
          'ref2page': {'R1': 1}, 'declared_pinname': {'R1.1': '1', 'R1.2': '2'}}
    report = {'requirement_clarification_version': 1, 'requirement_clarifications': [],
        'schema_version': 2, 'plan_digest': fingerprint(plan), 'db_digest': fingerprint(db),
        'checks': [{'id': k, 'applicability': 'APPLICABLE', 'review_result': 'PASS',
                    'evidence_confidence': 'A', 'evidence': E, 'rationale': 'stipulated compliant fixture',
                    'blocking': False, 'handoff': {'required': False}} for k in keys],
        'findings': [], 'scope_checks': {k: scope_id(k) for k in SCOPE},
        'coverage': {'components': {'R1': [first_key]}, 'pins': {'R1.1': [first_key], 'R1.2': [first_key]},
                     'nets': {'A': [first_key]}, 'pages': {'1': [first_key]}, 'requirements': {}}}
    return plan, report, db


def clarification(check_ids=None):
    return {'id': 'CL-INPUT', 'title': 'Define input range', 'kind': 'MISSING', 'status': 'OPEN',
            'question': 'Synthetic input range is not decided', 'decision_needed': 'Confirm operating input range',
            'owner': 'Synthetic requirement owner', 'decision_due': 'BEFORE_DESIGN',
            'closure_criteria': 'Controlled requirement and affected check re-review', 'evidence': E,
            'freeze_impact': 'BLOCKING', 'impact_reason': 'Input range affects electrical rating',
            'check_ids': check_ids or [C1]}


def fail(report, severity='P1'):
    c = report['checks'][0]
    c.update(review_result='FAIL', severity=severity, finding_id='F1')
    report['findings'] = [{'id': 'F1', 'kind': 'DEFECT', 'severity': severity, 'check_ids': [C1],
        'location': {'pages': ['1'], 'refs': ['R1'], 'nets': ['A']},
        **{key: 'synthetic evidence' for key in ('title', 'observed', 'criterion', 'impact', 'scenario',
              'root_cause', 'recommendation', 'verification', 'severity_reason')}}]
    return c


class ReviewGateTests(unittest.TestCase):
    def test_retired_plan_schema_and_unknown_rules_are_rejected(self):
        p, r, db = fixture(); del p['schema_version']; r['plan_digest'] = fingerprint(p)
        self.assertFalse(validate_review(p, r, db)['valid'])
        p, r, db = fixture(); p['checks'][0]['method'] = 'D'; r['plan_digest'] = fingerprint(p)
        out = validate_review(p, r, db)
        self.assertFalse(out['valid'])
        self.assertTrue(any('method/domain' in x for x in out['errors']), out)

    def test_complete_ledger_can_release(self):
        p, r, db = fixture()
        result = validate_review(p, r, db)
        self.assertTrue(result['valid'], result)
        self.assertEqual(result['release'], 'GO')

    def test_omitted_check_rejected(self):
        p, r, db = fixture(); r['checks'].pop()
        self.assertFalse(validate_review(p, r, db)['valid'])

    def test_declared_but_absent_pin_cannot_disappear_from_coverage(self):
        p, r, db = fixture(); del r['coverage']['pins']['R1.2']
        self.assertFalse(validate_review(p, r, db)['valid'])

    def test_one_part_missing_from_coverage_rejected(self):
        p, r, db = fixture(); r['coverage']['components'] = {}
        self.assertFalse(validate_review(p, r, db)['valid'])

    def test_c_confidence_cannot_pass(self):
        p, r, db = fixture(); r['checks'][0]['evidence_confidence'] = 'C'
        self.assertFalse(validate_review(p, r, db)['valid'])

    def test_na_requires_applicability_change_evidence(self):
        p, r, db = fixture(); r['checks'][0]['review_result'] = 'NA'
        self.assertFalse(validate_review(p, r, db)['valid'])
        r['checks'][0].update(applicability='NOT_APPLICABLE', applicability_evidence=E)
        self.assertTrue(validate_review(p, r, db)['valid'])

    def test_unknown_is_separate_and_blocks_for_potential_p0(self):
        p, r, db = fixture()
        r['checks'][0].update(review_result='INSUFFICIENT', evidence_confidence='C',
                              missing_inputs=['assembly BOM'], potential_severity='P0')
        result = validate_review(p, r, db)
        self.assertTrue(result['valid'], result)
        self.assertEqual(result['release'], 'NO_GO')
        self.assertEqual(result['summary']['confirmed_defects'], 0)

    def test_gap_cause_is_counted_and_limited_to_insufficient(self):
        p, r, db = fixture()
        r['checks'][0].update(review_result='INSUFFICIENT', evidence_confidence='C', missing_inputs=['firmware OVP table'],
                              potential_severity='P2', gap_cause='EXTERNAL_DATA')
        result = validate_review(p, r, db)
        self.assertTrue(result['valid'], result)
        self.assertEqual(result['insufficient_by_cause'], {'EXTERNAL_DATA': 1})
        r['checks'][0]['gap_cause'] = 'TOO_STRICT'
        self.assertFalse(validate_review(p, r, db)['valid'])
        p, r, db = fixture()
        r['checks'][0]['gap_cause'] = 'EXTERNAL_DATA'
        self.assertFalse(validate_review(p, r, db)['valid'])

    def test_untagged_insufficient_reported_as_unspecified(self):
        p, r, db = fixture()
        r['checks'][0].update(review_result='INSUFFICIENT', evidence_confidence='C', missing_inputs=['magnetics Isat'],
                              potential_severity='P2')
        self.assertEqual(validate_review(p, r, db)['insufficient_by_cause'], {'UNSPECIFIED': 1})

    def test_open_or_deferred_requirement_cannot_be_judged(self):
        def run(status, **row):
            p, r, db = fixture()
            p['checks'][0]['object'] = dict(p['checks'][0].get('object') or {}, requirement_status=status)
            r['plan_digest'] = fingerprint(p)
            r['checks'][0].update(row)
            if row.get('gap_cause') == 'REQUIREMENT_OPEN':
                r['checks'][0].pop('potential_severity', None)
                r['checks'][0]['blocking'] = True
                r.update(workflow_version=1, work_items=[], requirement_clarifications=[clarification()])
            return validate_review(p, r, db)
        gap = dict(review_result='INSUFFICIENT', evidence_confidence='C', potential_severity='P2',
                   missing_inputs=['derating temperature points'])
        self.assertFalse(run('OPEN')['valid'])                                   # PASS on an undecided requirement
        self.assertFalse(run('OPEN', **gap, gap_cause='EXTERNAL_DATA')['valid'])  # filed as missing data
        self.assertTrue(run('OPEN', **gap, gap_cause='REQUIREMENT_OPEN')['valid'])
        self.assertTrue(run('DEFERRED', **gap, gap_cause='USER_DEFERRED')['valid'])
        out = run('PROPOSED')
        self.assertTrue(out['valid'], out)
        self.assertEqual(out['requirements_by_status'], {'PROPOSED': {'PASS': 1}})

    def test_requirement_open_is_listed_as_unique_current_decision(self):
        p, r, db = fixture()
        p['review_phase'] = 'design_iteration'; r['plan_digest'] = fingerprint(p)
        r['checks'][0].update(review_result='INSUFFICIENT', evidence_confidence='C', blocking=True,
                              missing_inputs=['operating input voltage range'], gap_cause='REQUIREMENT_OPEN')
        r.update(workflow_version=1, work_items=[], requirement_clarifications=[clarification()])
        current = validate_review(p, r, db)
        self.assertTrue(current['valid'], current)
        self.assertEqual(current['requirement_clarification_summary']['open'], 1)
        self.assertEqual(current['workflow']['current_work_items'], ['CL-INPUT'])
        self.assertNotIn('requirement_questions', current)

    def test_p1_blocks_even_if_agent_sets_nonblocking(self):
        p, r, db = fixture(); fail(r)
        result = validate_review(p, r, db)
        self.assertTrue(result['valid'], result)
        self.assertEqual(result['release'], 'NO_GO')

    def test_acceptance_preserves_fail_and_conditional_release(self):
        p, r, db = fixture(); c = fail(r)
        c.update(disposition='ACCEPTED', acceptance={key: 'synthetic approval only' for key in
                 ('by', 'date', 'scope', 'reason', 'record')})
        self.assertEqual(validate_review(p, r, db)['release'], 'CONDITIONAL_GO')
        c['severity'] = r['findings'][0]['severity'] = 'P0'
        self.assertEqual(validate_review(p, r, db)['release'], 'NO_GO')

    def test_fake_acceptance_rejected(self):
        p, r, db = fixture(); fail(r).update(disposition='ACCEPTED')
        self.assertFalse(validate_review(p, r, db)['valid'])

    def test_handoff_open_does_not_change_pass_but_blocks_release(self):
        p, r, db = fixture()
        r['checks'][0]['handoff'] = {'required': True, 'state': 'OPEN', 'receivers': ['Layout'],
                                    'constraint': 'specified impedance', 'verification': 'layout check'}
        result = validate_review(p, r, db)
        self.assertTrue(result['valid'], result)
        self.assertEqual(result['release'], 'NO_GO')

    def thermal_handoff_fixture(self):
        # Synthetic resistor power-rating review; no board thermal model or test result.
        p, r, db = fixture('DEV-C01.BOARD')
        p['checks'][0].update(object={'board': 'BOARD'}, criterion=catalog.criterion('DEV-C01'),
                              handoff={'required': True})
        r['plan_digest'] = fingerprint(p)
        r['checks'][0].update(
            rationale='Synthetic stipulated load and rating satisfy the electrical criterion; actual temperature unverified',
            handoff={'required': True, 'state': 'ACCEPTED', 'receivers': ['Thermal/Test'],
                     'constraint': 'Synthetic R1 loss <= 0.1 W, ambient <= 50 C, body <= 85 C',
                     'verification': 'Prototype temperature test at specified load and ambient',
                     'evidence': [{'source': 'synthetic-handoff.json', 'locator': 'thermal owner accepted constraints only'}]})
        return p, r, db

    def test_electrical_pass_with_accepted_thermal_constraints_needs_no_thermal_test(self):
        p, r, db = self.thermal_handoff_fixture()
        result = validate_review(p, r, db)
        self.assertTrue(result['valid'], result)
        self.assertEqual(result['release'], 'GO')
        self.assertEqual(result['summary']['confirmed_defects'], 0)
        self.assertEqual(r['checks'][0]['handoff']['state'], 'ACCEPTED')

    def test_unreceived_thermal_constraints_block_handoff_without_electrical_defect(self):
        p, r, db = self.thermal_handoff_fixture()
        r['checks'][0]['handoff']['state'] = 'OPEN'
        del r['checks'][0]['handoff']['evidence']
        result = validate_review(p, r, db)
        self.assertTrue(result['valid'], result)
        self.assertEqual(result['release'], 'NO_GO')
        self.assertEqual(result['summary']['confirmed_defects'], 0)
        self.assertEqual(r['checks'][0]['review_result'], 'PASS')

    def test_accepted_thermal_handoff_does_not_clear_missing_electrical_load(self):
        p, r, db = self.thermal_handoff_fixture()
        r['checks'][0].update(review_result='INSUFFICIENT', evidence_confidence='C',
                              rationale='Load is unknown, so loss and rating cannot be compared',
                              potential_severity='P1', blocking=True,
                              missing_inputs=['Maximum continuous current through R1'])
        result = validate_review(p, r, db)
        self.assertTrue(result['valid'], result)
        self.assertEqual(result['release'], 'NO_GO')

    def test_same_defect_multiple_checks_counted_once(self):
        p, r, db = fixture(); fail(r)
        second = copy.deepcopy(r['checks'][0]); second['id'] = C2
        p['checks'].append(planned(C2))
        r['plan_digest'] = fingerprint(p); r['checks'].append(second)
        r['findings'][0]['check_ids'].append(C2)
        result = validate_review(p, r, db)
        self.assertTrue(result['valid'], result)
        self.assertEqual(result['summary']['results']['FAIL'], 2)
        self.assertEqual(result['summary']['confirmed_defects'], 1)

    def test_summary_and_claimed_release_cannot_hide_failure(self):
        p, r, db = fixture(); fail(r); r['release'] = 'GO'
        self.assertFalse(validate_review(p, r, db)['valid'])
        del r['release']; r['summary'] = {'confirmed_defects': 0}
        self.assertFalse(validate_review(p, r, db)['valid'])

    def test_changed_baseline_invalidates_ledger(self):
        p, r, db = fixture(); db['parts']['R1']['value'] = 'NEW'
        self.assertFalse(validate_review(p, r, db)['valid'])

    def test_export_failure_cannot_release(self):
        p, r, db = fixture(); db['export_errors'] = ['Aborting Netlisting']
        r['db_digest'] = fingerprint(db)
        self.assertEqual(validate_review(p, r, db)['release'], 'NO_GO')

    def test_unreviewed_lint_candidate_rejected(self):
        p, r, db = fixture()
        run = {'findings': [{'rule': 'PWR-A01', 'detail': 'candidate 1'},
                            {'rule': 'PWR-A01', 'detail': 'candidate 2'}]}
        r['lint_reviews'] = [{'run_digest': fingerprint(run), 'items': {'0': [C1]}}]
        self.assertFalse(validate_review(p, r, db, [run])['valid'])
        r['lint_reviews'][0]['items']['1'] = [C1]
        self.assertTrue(validate_review(p, r, db, [run])['valid'])

    def test_malformed_result_cannot_release(self):
        p, r, db = fixture()
        r['checks'][0]['review_result'] = ['PASS']
        self.assertFalse(validate_review(p, r, db)['valid'])

    def test_required_planned_handoff_cannot_be_silently_removed(self):
        p, r, db = fixture()
        p['checks'][0]['handoff'] = {'required': True}
        r['plan_digest'] = fingerprint(p)
        self.assertFalse(validate_review(p, r, db)['valid'])
        r['checks'][0]['handoff_evidence'] = E
        self.assertTrue(validate_review(p, r, db)['valid'])


def bound_fixture():
    p, r, _ = fixture()
    for check in p['checks']:
        check.update(object={'audit': check['id']}, criterion='enumerate the declared audit scope')
    p['checks'][0].update(object={'ref': 'U10', 'node': 'U10.4', 'net': 'EN',
                                  'state': 'RUN', 'configuration': 'A'}, criterion='EN >= 2.0 V')
    r['plan_digest'] = fingerprint(p)
    r['binding_version'] = 1
    for planned, result in zip(p['checks'], r['checks']):
        result['binding'] = {k: copy.deepcopy(planned[k]) for k in ('object', 'criterion')}
    return p, r


def bound_fail(report, severity='P1'):
    item = fail(report, severity)
    report['findings'][0]['location'].update(refs=['R10', 'U10'], nets=['VIN', 'EN'])
    return item


class ReviewBindingTests(unittest.TestCase):
    def test_complete_bound_ledger_can_release(self):
        p, r = bound_fixture()
        out = validate_review(p, r)
        self.assertTrue(out['valid'], out)
        self.assertEqual(out['release'], 'GO')
        self.assertTrue(out['binding_validation']['enforced'])
        self.assertEqual(out['binding_validation']['bound_checks'], len(p['checks']))

    def test_legacy_report_remains_explicitly_unbound(self):
        p, r, db = fixture()
        out = validate_review(p, r, db)
        self.assertTrue(out['valid'], out)
        self.assertFalse(out['binding_validation']['enforced'])

    def test_required_binding_cannot_be_disabled_by_omitting_version(self):
        p, r, _ = fixture()
        out = validate_review(p, r, require_bindings=True)
        self.assertFalse(out['valid'])
        self.assertEqual(out['release'], 'NO_GO')

    def test_partial_binding_without_version_is_rejected(self):
        p, r = bound_fixture(); del r['binding_version']
        self.assertFalse(validate_review(p, r)['valid'])

    def test_invalid_binding_versions_are_rejected(self):
        for version in (True, False, 0, 2, '1', None, []):
            with self.subTest(version=version):
                p, r = bound_fixture(); r['binding_version'] = version
                self.assertFalse(validate_review(p, r)['valid'])

    def test_missing_binding_is_rejected(self):
        p, r = bound_fixture(); del r['checks'][0]['binding']
        self.assertFalse(validate_review(p, r)['valid'])

    def test_object_ref_pin_net_state_and_configuration_must_match(self):
        for field, value in [('ref', 'U11'), ('node', 'U10.5'), ('net', 'STRAP'),
                             ('state', 'OFF'), ('configuration', 'B')]:
            with self.subTest(field=field):
                p, r = bound_fixture(); r['checks'][0]['binding']['object'][field] = value
                self.assertFalse(validate_review(p, r)['valid'])

    def test_criterion_mismatch_is_rejected_even_if_result_is_pass(self):
        p, r = bound_fixture(); r['checks'][0]['binding']['criterion'] = 'STRAP <= 0.8 V'
        self.assertFalse(validate_review(p, r)['valid'])

    def test_malformed_binding_fails_closed(self):
        for binding in (None, [], 'EN', {}, {'object': [], 'criterion': 'EN >= 2.0 V'},
                        {'object': {}, 'criterion': None}):
            with self.subTest(binding=binding):
                p, r = bound_fixture(); r['checks'][0]['binding'] = binding
                self.assertFalse(validate_review(p, r)['valid'])

    def test_malformed_primary_coordinates_cannot_disable_anchors(self):
        for field in ('ref', 'node', 'net'):
            for value in ([], {}, 1, None, ''):
                with self.subTest(field=field, value=value):
                    p, r = bound_fixture(); bound_fail(r)
                    p['checks'][0]['object'][field] = value
                    r['checks'][0]['binding']['object'] = copy.deepcopy(p['checks'][0]['object'])
                    r['plan_digest'] = fingerprint(p)
                    self.assertFalse(validate_review(p, r)['valid'])

    def test_changed_plan_cannot_reuse_old_binding_after_rehash(self):
        p, r = bound_fixture(); p['checks'][0]['criterion'] = 'EN >= 2.2 V'
        r['plan_digest'] = fingerprint(p)
        self.assertFalse(validate_review(p, r)['valid'])

    def test_unbound_plan_criterion_cannot_be_invented_by_result(self):
        p, r = bound_fixture(); del p['checks'][0]['criterion']
        r['plan_digest'] = fingerprint(p)
        self.assertFalse(validate_review(p, r)['valid'])

    def test_en_cannot_be_failed_by_strap_finding(self):
        p, r = bound_fixture(); bound_fail(r)
        r['findings'][0]['location'].update(refs=['U11', 'R12', 'R13'], nets=['VDD', 'STRAP'])
        r['findings'][0]['criterion'] = 'STRAP <= 0.8 V'
        r['checks'][0]['rationale'] = 'STRAP 0.845..0.910 V violates guaranteed LOW'
        out = validate_review(p, r)
        self.assertFalse(out['valid'])
        self.assertTrue(any('U10' in x for x in out['errors']), out)
        self.assertEqual(out['release'], 'NO_GO')

    def test_primary_net_must_be_in_finding_location(self):
        p, r = bound_fixture(); bound_fail(r)
        r['findings'][0]['location']['nets'] = ['STRAP']
        self.assertFalse(validate_review(p, r)['valid'])

    def test_primary_node_owner_is_checked_without_ref(self):
        p, r = bound_fixture(); del p['checks'][0]['object']['ref']
        r['checks'][0]['binding']['object'] = copy.deepcopy(p['checks'][0]['object'])
        r['plan_digest'] = fingerprint(p); bound_fail(r)
        r['findings'][0]['location']['refs'] = ['U11']
        self.assertFalse(validate_review(p, r)['valid'])

    def test_upstream_cause_with_affected_target_is_allowed(self):
        p, r = bound_fixture(); bound_fail(r)
        p['checks'][0]['object']['refs'] = ['U10', 'U11', 'R10', 'J1']
        r['checks'][0]['binding']['object'] = copy.deepcopy(p['checks'][0]['object'])
        r['plan_digest'] = fingerprint(p)
        out = validate_review(p, r)
        self.assertTrue(out['valid'], out)
        self.assertEqual(out['release'], 'NO_GO')

    def test_requirement_aggregate_has_no_invented_physical_anchor(self):
        p, r = bound_fixture(); bound_fail(r)
        p['checks'][0]['object'] = {'requirement_id': 'REQ-EN'}
        r['checks'][0]['binding']['object'] = copy.deepcopy(p['checks'][0]['object'])
        r['plan_digest'] = fingerprint(p); r['coverage']['requirements'] = {'REQ-EN': [C1]}
        self.assertTrue(validate_review(p, r)['valid'])

    def test_defect_cannot_link_a_pass_check(self):
        p, r = bound_fixture(); bound_fail(r)
        r['findings'][0]['check_ids'].append(r['checks'][1]['id'])
        self.assertFalse(validate_review(p, r)['valid'])

    def test_true_p0_is_not_removed_by_binding_validation(self):
        p, r = bound_fixture(); bound_fail(r, 'P0')
        out = validate_review(p, r)
        self.assertTrue(out['valid'], out)
        self.assertEqual(out['release'], 'NO_GO')
        self.assertEqual(out['summary']['by_severity']['P0'], 1)

    def test_insufficient_and_na_keep_existing_semantics(self):
        p, r = bound_fixture()
        r['checks'][0].update(review_result='INSUFFICIENT', evidence_confidence='C',
                              missing_inputs=['guaranteed startup peak'], potential_severity='P1')
        out = validate_review(p, r)
        self.assertTrue(out['valid'], out); self.assertEqual(out['release'], 'NO_GO')
        p, r = bound_fixture()
        r['checks'][0].update(review_result='NA', applicability='NOT_APPLICABLE', applicability_evidence=E)
        self.assertTrue(validate_review(p, r)['valid'])


def gap_with_task(design_option=None, cause='EXTERNAL_DATA'):
    p, r, db = fixture()
    p['review_phase'] = 'design_iteration'; r['plan_digest'] = fingerprint(p)
    r['checks'][0].update(review_result='INSUFFICIENT', evidence_confidence='C', potential_severity='P2',
                          missing_inputs=['zener voltage below its 5 mA test current'], gap_cause=cause)
    item = {'id': 'W-BIAS', 'title': 'Bias reference outside its guaranteed current', 'check_ids': [C1],
            'root_cause': 'Reference runs below the vendor test current', 'due_stage': 'design_iteration',
            'reason': 'Affects minimum supply', 'next_action': 'Apply the proposed circuit change', 'evidence': E}
    if design_option is not None:
        item['design_option'] = design_option
    r.update(workflow_version=1, work_items=[item], remediation_version=2)
    return p, r, db


def proposed_option(**overrides):
    option = {
        'status': 'PROPOSED',
        'summary': 'Feed the supply from the regulated rail through a Schottky so no sub-test-current zener sets it.',
        'preference': 'DESIGN_FIRST',
        'preference_reason': 'Vendors do not characterise the zener below its test current, so the evidence path is unlikely to close.',
        'remediation': {
            'readiness': 'CONDITIONAL', 'purpose': 'Supply stays above UVLO with guaranteed parameters only.',
            'prerequisites': [{'input': 'Diode VF at the load current', 'reason': 'Sets the minimum supply',
                               'how_to_obtain': 'Vendor table at 10 mA', 'acceptance': 'VF max listed'}],
            'steps': [{'kind': 'COMPONENT', 'target': 'R1', 'before': 'zener bias network',
                       'after': 'Schottky from the regulated rail', 'instruction': 'Replace the bias network.'}],
            'parameters': [{'target': 'D_new', 'specification': '30 V Schottky, VF<=0.4 V at 10 mA',
                            'status': 'CANDIDATE', 'basis': E, 'needed_input': 'exact MPN',
                            'selection_method': 'Pick a part with VF max at 10 mA'}],
            'related_findings': [], 'impact_review': 'Minimum supply now set by rail minus VF max.',
            'verification': [{'stage': 'CALCULATION', 'method': 'Rail min minus VF max', 'expected': '>= UVLO + margin'}],
            'calculation_preflight': {'applicable': False, 'reason': 'synthetic structure test', 'evidence': E}},
        'avoids': [{'problem': 'Minimum supply depends on an unguaranteed zener voltage',
                    'after_change': 'Only datasheet maxima set the minimum supply', 'check_ids': [C1]}],
        'tradeoffs': ['Controller dissipates more at the highest rail voltage; thermal limit handed to PCB']}
    option.update(overrides)
    return option


class DesignOptionTests(unittest.TestCase):
    def test_designable_gap_needs_a_design_option_when_actionable(self):
        p, r, db = gap_with_task()
        out = validate_review(p, r, db, require_actionable=True)
        self.assertFalse(out['valid'])
        self.assertTrue(any('design_option' in e for e in out['errors']), out['errors'])

    def test_none_with_reason_is_accepted(self):
        p, r, db = gap_with_task({'status': 'NONE', 'evidence': E,
                                  'reason': 'Only the supplier can certify the winding; no schematic change removes it'})
        out = validate_review(p, r, db, require_actionable=True)
        self.assertTrue(out['valid'], out['errors'])
        self.assertEqual({'PROPOSED': 0, 'NONE': 1}, out['workflow']['design_options'])

    def test_proposed_option_states_what_it_avoids(self):
        p, r, db = gap_with_task(proposed_option())
        out = validate_review(p, r, db, require_actionable=True)
        self.assertTrue(out['valid'], out['errors'])
        self.assertEqual({'PROPOSED': 1, 'NONE': 0}, out['workflow']['design_options'])
        self.assertEqual('PROPOSED', out['workflow']['work_items'][0]['design_option']['status'])

    def test_incomplete_proposals_are_rejected(self):
        bad = [proposed_option(avoids=[]), proposed_option(tradeoffs=[]),
               proposed_option(preference='LATER'),
               proposed_option(avoids=[{'problem': 'x', 'after_change': 'y', 'check_ids': ['PWR-C01.NOPE']}]),
               proposed_option(remediation={'readiness': 'READY'}),
               {'status': 'NONE', 'reason': 'no evidence given'}]
        for option in bad:
            p, r, db = gap_with_task(option)
            self.assertFalse(validate_review(p, r, db, require_actionable=True)['valid'], option)

    def test_other_gap_causes_and_legacy_results_need_no_option(self):
        p, r, db = gap_with_task(cause='DOWNSTREAM_VERIFICATION')
        self.assertTrue(validate_review(p, r, db, require_actionable=True)['valid'])
        p, r, db = gap_with_task()
        del r['remediation_version']
        self.assertTrue(validate_review(p, r, db)['valid'])

if __name__ == '__main__':
    unittest.main()

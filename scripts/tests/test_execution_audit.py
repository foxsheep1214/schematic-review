"""Controlled counterexamples: structural validity is not execution consistency."""
import copy
import json
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from execution_audit import digest, validate_execution_audit
from validate_review import validate_review

FIXTURE = Path(__file__).parent / 'fixtures/execution-audit/synthetic.json'


def fixture():
    data = json.loads(FIXTURE.read_text())
    return data['plan'], data['results'], data['db'], data['audit']


def rebind(p, r, db, a):
    r['plan_digest'], r['db_digest'] = digest(p), digest(db)
    a.update(plan_digest=digest(p), results_digest=digest(r), db_digest=digest(db))


def row(report, check_id):
    return next(x for x in report['checks'] if x['id'] == check_id)


def without_execution_contract(p, r, db):
    p, r = copy.deepcopy(p), copy.deepcopy(r)
    p.pop('execution_contract')
    r['plan_digest'] = digest(p)
    return validate_review(p, r, db)


def honest_numeric_gap(p, r, a, cid, missing):
    row = next(x for x in r['checks'] if x['id'] == cid)
    row.update(review_result='INSUFFICIENT', evidence_confidence='C', missing_inputs=[missing],
               potential_severity='P2', gap_cause='EXTERNAL_DATA')
    p['execution_inputs']['own_missing_' + missing] = {
        'required_inputs': [missing], 'available_inputs': []}
    p['execution_contract']['gaps'].append({'id': 'G-' + missing, 'check_id': cid,
        'basis': {'root': 'plan', 'pointer': '/execution_inputs/own_missing_' + missing}})
    a['gaps'].append({'id': 'G-' + missing, 'missing_inputs': [missing]})
    # Coverage remains complete while the functional aggregate stays unresolved.
    for record in a['aggregates']:
        if cid in record['member_results']:
            record['member_results'][cid] = 'INSUFFICIENT'
    parent = next(x for x in r['checks'] if x['id'] == 'REQ-D01.BOOT-FUNCTION')
    parent.update(review_result='INSUFFICIENT', evidence_confidence='C', missing_inputs=[missing],
                  potential_severity='P2', gap_cause='EXTERNAL_DATA')
    p['execution_contract']['gaps'].append({'id': 'P-' + missing, 'check_id': parent['id'],
        'basis': {'root': 'plan', 'pointer': '/execution_inputs/own_missing_' + missing}})
    a['gaps'].append({'id': 'P-' + missing, 'missing_inputs': [missing]})


class ExecutionAuditTests(unittest.TestCase):
    def test_controlled_positive_integration(self):
        p, r, db, a = fixture()
        result = validate_review(p, r, db, execution_audit=a, require_execution_audit=True)
        self.assertTrue(result['valid'], result['errors'])
        self.assertFalse(result['execution_audit']['electrical_approval'])
        self.assertEqual(result['execution_audit']['checked']['networks'], 1)

    def assert_rejected(self, p, r, db, a, code, differential=False):
        rebind(p, r, db, a)
        if differential:
            self.assertTrue(without_execution_contract(p, r, db)['valid'], without_execution_contract(p, r, db)['errors'])
        result = validate_execution_audit(p, r, db, a, True)
        self.assertTrue(any(e.startswith(code + ':') for e in result['errors']), result)
        integrated = validate_review(p, r, db, execution_audit=a)
        self.assertFalse(integrated['valid'])

    def test_second_native_receiver_cannot_be_omitted(self):
        p, r, db, a = fixture()
        a['networks'][0]['calculations'] = [c for c in a['networks'][0]['calculations'] if c['receiver'] != 'U3.1']
        self.assert_rejected(p, r, db, a, 'CASE_COVERAGE', True)

    def test_contract_cannot_shrink_native_receiver_set(self):
        p, r, db, a = fixture()
        del p['execution_inputs']['network']['receivers']['U3.1']
        self.assert_rejected(p, r, db, a, 'RECEIVER_COVERAGE', True)

    def test_normal_output_driver_is_not_a_receiver(self):
        p, r, db, a = fixture()
        db['native_pintype'] = {'U1.1':'output','U2.1':'input','U3.1':'input'}
        rebind(p, r, db, a)
        self.assertFalse(validate_execution_audit(p, r, db, a)['errors'])

    def test_input_cannot_be_labeled_driver_to_escape_receiver_coverage(self):
        p,r,db,a=fixture()
        p['execution_inputs']['network']['drivers'].append('U3.1')
        del p['execution_inputs']['network']['receivers']['U3.1']
        self.assert_rejected(p,r,db,a,'DRIVER_ROLE',True)

    def test_external_3v3_power_case_cannot_be_omitted(self):
        p, r, db, a = fixture()
        a['power'][0]['calculations'].pop()
        self.assert_rejected(p, r, db, a, 'CASE_COVERAGE', True)

    def test_external_case_cannot_reuse_internal_numeric_value(self):
        p, r, db, a = fixture()
        a['power'][0]['calculations'][1]['value'] = a['power'][0]['calculations'][0]['value']
        self.assert_rejected(p, r, db, a, 'NUMERIC_VALUE', True)

    def test_real_fast_receiver_fails_guarantee_without_waiving_it(self):
        p, r, db, a = fixture()
        receiver = p['execution_inputs']['network']['receivers']['U3.1']
        receiver['threshold']['min'] = receiver['threshold']['max'] = .5
        for c in a['networks'][0]['calculations']:
            if c['receiver'] == 'U3.1':
                c.update(value=-.0081 * math.log((3.3-.5)/3.3), claim='FAIL')
        r['checks'][0]['review_result'] = 'FAIL'
        a['aggregates'][0]['member_results']['RST-E01.C1'] = 'FAIL'
        a['aggregates'][1]['member_results']['RST-E01.C1'] = 'FAIL'
        row(r, 'REQ-D01.BOOT-FUNCTION')['review_result'] = 'FAIL'
        rebind(p, r, db, a)
        self.assertFalse(validate_execution_audit(p, r, db, a)['errors'])

    def test_guarantee_conditions_cannot_be_omitted(self):
        p, r, db, a = fixture()
        del p['execution_inputs']['network']['cases'][0]['capacitance']['conditions']
        self.assert_rejected(p, r, db, a, 'INTERVAL_SOURCE', True)

    def test_out_of_condition_inputs_cannot_support_pass_or_fail(self):
        for false_result in ('PASS','FAIL'):
            with self.subTest(false_result=false_result):
                p, r, db, a = fixture()
                v = p['execution_inputs']['network']['cases'][0]['resistance']
                v['conditions'] = {'temperature':{'min':0,'max':40,'unit':'C'}}
                v['operating_conditions'] = {'temperature':{'min':-10,'max':60,'unit':'C'}}
                r['checks'][0]['review_result'] = false_result
                self.assert_rejected(p, r, db, a, 'NUMERIC_VERDICT')

    def test_unknown_active_branch_is_insufficient_not_curve_pass(self):
        p, r, db, a = fixture()
        p['execution_inputs']['network']['model_support']['excluded_branches'] = ['unresolved clamp']
        self.assert_rejected(p, r, db, a, 'NUMERIC_VERDICT', True)
        for c in a['networks'][0]['calculations']:
            c['claim'] = 'INSUFFICIENT'
        r['checks'][0]['review_result'] = 'INSUFFICIENT'
        # Audit alone: preserve the truthful unresolved model and own missing input.
        p['execution_inputs']['model_gap'] = {'required_inputs':['clamp_model'],'available_inputs':[]}
        p['execution_contract']['gaps'].append({'id':'MODEL','check_id':'RST-E01.C1','basis':{'root':'plan','pointer':'/execution_inputs/model_gap'}})
        a['gaps'].append({'id':'MODEL','missing_inputs':['clamp_model']})
        r['checks'][0]['missing_inputs'] = ['clamp_model']
        a['aggregates'][0]['member_results']['RST-E01.C1'] = 'INSUFFICIENT'
        a['aggregates'][1]['member_results']['RST-E01.C1'] = 'INSUFFICIENT'
        row(r, 'REQ-D01.BOOT-FUNCTION')['review_result'] = 'INSUFFICIENT'
        p['execution_inputs']['aggregate_gap'] = {'required_inputs':['clamp_model'],'available_inputs':[]}
        p['execution_contract']['gaps'].append({'id':'AGG','check_id':'REQ-D01.BOOT-FUNCTION','basis':{'root':'plan','pointer':'/execution_inputs/aggregate_gap'}})
        a['gaps'].append({'id':'AGG','missing_inputs':['clamp_model']})
        row(r, 'REQ-D01.BOOT-FUNCTION')['missing_inputs'] = ['clamp_model']
        rebind(p, r, db, a)
        self.assertFalse(validate_execution_audit(p, r, db, a)['errors'])

    def test_required_fail_member_cannot_be_summarized_as_pass(self):
        p, r, db, a = fixture()
        p['execution_inputs']['aggregate']['members'].append('REQ-D01.NAME')
        a['aggregates'][0]['member_results']['REQ-D01.NAME'] = 'FAIL'
        self.assert_rejected(p, r, db, a, 'AGGREGATE_VERDICT', True)

    def test_member_result_cannot_be_laundered_in_summary(self):
        p, r, db, a = fixture()
        a['aggregates'][0]['member_results']['RST-E01.C1'] = 'INSUFFICIENT'
        self.assert_rejected(p, r, db, a, 'AGGREGATE_STATUS', True)

    def test_completed_coverage_does_not_inherit_electrical_fail(self):
        p, r, db, a = fixture()
        p['execution_inputs']['coverage']['members'].append('REQ-D01.NAME')
        a['aggregates'][1]['member_results']['REQ-D01.NAME'] = 'FAIL'
        rebind(p, r, db, a)
        self.assertFalse(validate_execution_audit(p, r, db, a)['errors'])
        row(r, 'REQ-Q07.BOOT')['review_result'] = 'FAIL'
        self.assert_rejected(p, r, db, a, 'AGGREGATE_VERDICT')

    def test_q07_cannot_be_retagged_as_electrical(self):
        p, r, db, a = fixture()
        p['execution_inputs']['coverage']['kind'] = 'ELECTRICAL'
        self.assert_rejected(p,r,db,a,'AGGREGATE_KIND',True)

    def test_na_requires_controlled_member_applicability(self):
        p, r, db, a = fixture()
        r['checks'][0]['review_result'] = 'NA'
        a['aggregates'][0]['member_results']['RST-E01.C1'] = 'NA'
        self.assert_rejected(p, r, db, a, 'AGGREGATE_NA')

    def test_identity_repair_cannot_acquire_supplier_rating_prerequisite(self):
        p, r, db, a = fixture()
        rem = r['findings'][0]['remediation']
        rem['parameters'].append({'target':'U2','specification':'Supplier MPN and V/I/P ratings','status':'TBD','basis':[{'source':'fixture','locator':'unresolved procurement'}],'needed_input':'Supplier ratings','selection_method':'Choose full electrical replacement'})
        p['execution_inputs']['supplier'] = {'obligation':'PROCUREMENT_RATING','check_id':'PWR-C01.POWER'}
        a['repairs'][0]['dependencies'].append({'id':'parameters/0','obligation':'PROCUREMENT_RATING','origin_check_id':'PWR-C01.POWER','basis':{'root':'plan','pointer':'/execution_inputs/supplier'}})
        self.assert_rejected(p, r, db, a, 'UNRELATED_REPAIR_DEPENDENCY', True)
        # A real original electrical task can retain this requirement.
        p['execution_inputs']['repair']['obligations'].append('PROCUREMENT_RATING')
        p['execution_inputs']['repair']['physical_dependencies'].append('PWR-C01.POWER')
        rebind(p, r, db, a)
        self.assertFalse(validate_execution_audit(p, r, db, a)['errors'])

    def test_unrelated_requirement_cannot_hide_in_step_or_verification(self):
        for locator in ('steps/0','verification/0'):
            with self.subTest(locator=locator):
                p, r, db, a = fixture()
                p['execution_inputs']['system'] = {'obligation':'SYSTEM_EMC','check_id':'PWR-C01.POWER'}
                dependency = next(x for x in a['repairs'][0]['dependencies'] if x['id'] == locator)
                dependency.update(obligation='SYSTEM_EMC',origin_check_id='PWR-C01.POWER',basis={'root':'plan','pointer':'/execution_inputs/system'})
                self.assert_rejected(p, r, db, a, 'UNRELATED_REPAIR_DEPENDENCY', True)

    def test_independently_available_local_inputs_cannot_inherit_pinname_gap(self):
        p, r, db, a = fixture()
        p['execution_inputs']['gap'] = {'required_inputs':['cap_connectivity'],'available_inputs':['cap_connectivity']}
        r['checks'][-1]['missing_inputs'] = ['U7_missing_function_name']
        a['gaps'][0]['missing_inputs'] = ['U7_missing_function_name']
        self.assert_rejected(p, r, db, a, 'UNRELATED_GAP', True)

    def test_real_missing_ceff_stays_insufficient(self):
        p, r, db, a = fixture()
        self.assertFalse(validate_execution_audit(p, r, db, a)['errors'])
        self.assertEqual(r['checks'][-1]['review_result'],'INSUFFICIENT')

    def test_work_item_design_option_is_checked_in_full_validator(self):
        p,r,db,a=fixture()
        evidence=r['checks'][0]['evidence']
        repair=copy.deepcopy(r['findings'][0]['remediation'])
        r['workflow_version']=1
        r['work_items']=[{'id':'W-INPUT-NAME','title':'Correct name','root_cause':'Missing exact identity',
            'check_ids':['REQ-D01.NAME'],'due_stage':'design_iteration','reason':'Exact source map',
            'next_action':'Update record only','evidence':evidence,'design_option':{
                'status':'PROPOSED','summary':'Correct identity only','preference':'DESIGN_FIRST',
                'preference_reason':'No electrical change','remediation':repair,
                'avoids':[{'problem':'Wrong name','after_change':'Matches source','check_ids':['REQ-D01.NAME']}],
                'tradeoffs':['No electrical change']}},
            {'id':'W-CAP','title':'Obtain curve','root_cause':'No effective capacitance curve',
             'check_ids':['PWR-C01.CEFF'],'due_stage':'design_iteration','reason':'Real material gap',
             'next_action':'Obtain material curve','evidence':evidence}]
        p['execution_contract']['repairs'].append({'id':'WORK-NAME','target_kind':'work_item',
            'target_id':'W-INPUT-NAME','basis':{'root':'plan','pointer':'/execution_inputs/repair'}})
        copy_record=copy.deepcopy(a['repairs'][0]);copy_record['id']='WORK-NAME';a['repairs'].append(copy_record)
        rebind(p,r,db,a)
        self.assertTrue(validate_review(p,r,db,execution_audit=a)['valid'])
        repair['parameters'].append({'target':'U2','specification':'Electrical supplier replacement','status':'TBD',
            'basis':evidence,'needed_input':'V/I/P from supplier','selection_method':'Electrical selection'})
        p['execution_inputs']['supplier']={'obligation':'PROCUREMENT_RATING','check_id':'PWR-C01.POWER'}
        a['repairs'][-1]['dependencies'].append({'id':'parameters/0','obligation':'PROCUREMENT_RATING',
            'origin_check_id':'PWR-C01.POWER','basis':{'root':'plan','pointer':'/execution_inputs/supplier'}})
        self.assert_rejected(p,r,db,a,'UNRELATED_REPAIR_DEPENDENCY',True)
        # Correct actual work-item instructions and readiness, rather than merely
        # retagging the audit metadata as compliant.
        repair['parameters']=[];repair['prerequisites']=[];repair['readiness']='READY'
        r['findings'][0]['remediation']['prerequisites']=[]
        r['findings'][0]['remediation']['readiness']='READY'
        p['execution_inputs']['repair']['unresolved_obligations']=[]
        for record in a['repairs']:
            record['dependencies']=[d for d in record['dependencies'] if d['id'] in ('steps/0','verification/0')]
        rebind(p,r,db,a)
        self.assertTrue(validate_review(p,r,db,execution_audit=a)['valid'])

    def test_ready_cannot_be_replaced_by_unrelated_pending_obligation(self):
        p,r,db,a=fixture()
        p['execution_inputs']['repair']['unresolved_obligations']=[]
        self.assert_rejected(p,r,db,a,'REPAIR_READINESS',True)

    def test_handoff_binds_object_receivers_and_real_constraint(self):
        p,r,db,a=fixture()
        source={'object':{'net':'EN'},'receivers':['bench-owner'],
                'constraint':'Measure minimum delay for every receiver','verification':'Capture receiver thresholds'}
        p['execution_inputs']['handoff']=source
        r['checks'][0]['handoff']={'required':True,'state':'ACCEPTED','evidence':r['checks'][0]['evidence'],
            **{k:v for k,v in source.items() if k!='object'}}
        p['execution_contract']['handoffs']=[{'id':'EN-HANDOFF','check_id':'RST-E01.C1',
            'basis':{'root':'plan','pointer':'/execution_inputs/handoff'}}]
        a['handoffs']=[{'id':'EN-HANDOFF','object':source['object'],'receivers':source['receivers']}]
        rebind(p,r,db,a)
        self.assertTrue(validate_review(p,r,db,execution_audit=a)['valid'])
        r['checks'][0]['handoff']['receivers']=['pcb-owner']
        self.assert_rejected(p,r,db,a,'HANDOFF_RECEIVERS',True)

    def test_empty_contract_cannot_drop_known_obligations(self):
        p, r, db, a = fixture()
        for s in ('networks','power','aggregates','repairs','gaps'):
            p['execution_contract'][s] = []; a[s] = []
        self.assert_rejected(p, r, db, a, 'NUMERIC_SCOPE')

    def test_stale_results_digest_rejected(self):
        p, r, db, a = fixture()
        r['checks'][0]['rationale'] += ' Changed'
        self.assertTrue(any(e.startswith('STALE_AUDIT:') for e in validate_execution_audit(p,r,db,a)['errors']))

    def test_nonfinite_and_malformed_inputs_fail_closed(self):
        for value in (float('nan'),float('inf'),True,[],{'min':0}):
            with self.subTest(value=value):
                p,r,db,a=fixture();p['execution_inputs']['network']['cases'][0]['resistance']['min']=value
                rebind(p,r,db,a)
                self.assertTrue(validate_execution_audit(p,r,db,a)['errors'])

    def test_contract_self_reference_is_not_source_evidence(self):
        p,r,db,a=fixture()
        p['execution_contract']['power'][0]['basis']={'root':'plan','pointer':'/execution_contract/power/0'}
        self.assert_rejected(p,r,db,a,'SOURCE_BINDING')

    def test_missing_capacitance_allows_honest_ins_without_fake_numeric_values(self):
        p,r,db,a=fixture()
        honest_numeric_gap(p,r,a,'RST-E01.C1','effective_capacitance')
        for case in p['execution_inputs']['network']['cases']:
            case['capacitance']=None
        for cell in a['networks'][0]['calculations']:
            cell.update(claim='INSUFFICIENT',value=None)
        rebind(p,r,db,a)
        self.assertTrue(validate_review(p,r,db,execution_audit=a)['valid'])
        # An actually available input must not be hidden by an invented gap.
        p['execution_inputs']['own_missing_effective_capacitance']['available_inputs']=['effective_capacitance']
        self.assert_rejected(p,r,db,a,'INTERVAL')

    def test_missing_threshold_preserves_known_receiver_computation(self):
        p,r,db,a=fixture()
        honest_numeric_gap(p,r,a,'RST-E01.C1','U3_threshold')
        receiver=p['execution_inputs']['network']['receivers']['U3.1']
        receiver.update(threshold=None,basis='UNAVAILABLE')
        for cell in a['networks'][0]['calculations']:
            if cell['receiver']=='U3.1':cell.update(claim='INSUFFICIENT',value=None)
        rebind(p,r,db,a)
        self.assertTrue(validate_review(p,r,db,execution_audit=a)['valid'])
        self.assertTrue(all(c['claim']=='PASS' and c['value'] is not None
            for c in a['networks'][0]['calculations'] if c['receiver']=='U2.1'))

    def test_missing_rating_keeps_known_stress_without_inventing_rating(self):
        p,r,db,a=fixture()
        honest_numeric_gap(p,r,a,'PWR-C01.POWER','resistor_rating')
        p['execution_inputs']['power'].update(power_rating=None,rating_basis='UNAVAILABLE')
        for cell in a['power'][0]['calculations']:cell['claim']='INSUFFICIENT'
        rebind(p,r,db,a)
        self.assertTrue(validate_review(p,r,db,execution_audit=a)['valid'])
        self.assertTrue(all(c['value'] is not None for c in a['power'][0]['calculations']))
        a['power'][0]['calculations'][0]['value']*=2
        self.assert_rejected(p,r,db,a,'NUMERIC_VALUE')

    def test_unresolved_model_needs_no_fabricated_single_pole_estimate(self):
        p,r,db,a=fixture()
        honest_numeric_gap(p,r,a,'RST-E01.C1','clamp_model')
        p['execution_inputs']['network']['model_support'].update(
            qualification='UNRESOLVED',excluded_branches=['clamp'])
        for cell in a['networks'][0]['calculations']:
            cell.update(value=None,claim='INSUFFICIENT')
        rebind(p,r,db,a)
        self.assertTrue(validate_review(p,r,db,execution_audit=a)['valid'])
        cell=a['networks'][0]['calculations'][0];cell['claim']='PASS'
        self.assert_rejected(p,r,db,a,'NUMERIC_CLAIM')

    def test_passive_rc_source_can_be_upstream_without_driver_on_rc_net(self):
        p,r,db,a=fixture()
        db.update(parts={**db['parts'],'R2':{},'C2':{}},
            nets={'EN':['R2.2','C2.1','U2.1','U3.1'],'SUPPLY':['U1.1','R2.1'],'GND':['C2.2']},
            pin2net={'R2.2':'EN','C2.1':'EN','U2.1':'EN','U3.1':'EN',
                     'U1.1':'SUPPLY','R2.1':'SUPPLY','C2.2':'GND'},
            pintype={'U1.1':'OUT','U2.1':'IN','U3.1':'IN',
                     'R2.2':'PASSIVE','R2.1':'PASSIVE','C2.1':'PASSIVE','C2.2':'PASSIVE'})
        network=p['execution_inputs']['network'];network['drivers']=[]
        network['model_support']['endpoint_roles']={'R2.2':'PASSIVE_RC','C2.1':'PASSIVE_RC',
            'U2.1':'HIGH_IMPEDANCE_RECEIVER','U3.1':'HIGH_IMPEDANCE_RECEIVER'}
        rebind(p,r,db,a)
        self.assertFalse(validate_execution_audit(p,r,db,a)['errors'])
        db['pintype']['U1.1']='IN'
        self.assert_rejected(p,r,db,a,'MODEL_SOURCE')

    def test_receiver_cannot_be_hidden_by_falsely_declaring_it_a_driver(self):
        p,r,db,a=fixture()
        network=p['execution_inputs']['network'];network['drivers'].append('U3.1')
        network['model_support']['endpoint_roles']['U3.1']='DRIVER'
        del network['receivers']['U3.1']
        a['networks'][0]['calculations']=[c for c in a['networks'][0]['calculations'] if c['receiver']!='U3.1']
        self.assert_rejected(p,r,db,a,'DRIVER_ROLE')

    def test_missing_rating_cannot_hide_known_power_as_null(self):
        p,r,db,a=fixture()
        honest_numeric_gap(p,r,a,'PWR-C01.POWER','resistor_rating')
        p['execution_inputs']['power'].update(power_rating=None,rating_basis='UNAVAILABLE')
        for cell in a['power'][0]['calculations']:cell.update(claim='INSUFFICIENT',value=None)
        self.assert_rejected(p,r,db,a,'NUMERIC_VALUE')

    def test_model_label_cannot_hide_given_voltage_resistance_arithmetic(self):
        p,r,db,a=fixture()
        honest_numeric_gap(p,r,a,'PWR-C01.POWER','resistor_rating')
        p['execution_inputs']['power'].update(power_rating=None,rating_basis='UNAVAILABLE')
        p['execution_inputs']['power']['model_support']['qualification']='UNRESOLVED'
        for cell in a['power'][0]['calculations']:cell.update(claim='INSUFFICIENT',value=None)
        self.assert_rejected(p,r,db,a,'NUMERIC_VALUE')

    def test_multihop_declared_passive_source_and_reciprocal_indices(self):
        p,r,db,a=fixture()
        db.update(parts={**db['parts'],'R2':{},'R3':{},'C2':{}},
            nets={'EN':['R2.2','C2.1','U2.1','U3.1'], 'MID':['R3.2','R2.1'],
                  'SUPPLY':['U1.1','R3.1'],'GND':['C2.2']},
            pin2net={'R2.2':'EN','C2.1':'EN','U2.1':'EN','U3.1':'EN',
                     'R2.1':'MID','R3.2':'MID','R3.1':'SUPPLY','U1.1':'SUPPLY','C2.2':'GND'},
            pintype={'U1.1':'OUT','U2.1':'IN','U3.1':'IN','R2.2':'PASSIVE','R2.1':'PASSIVE',
                     'R3.1':'PASSIVE','R3.2':'PASSIVE','C2.1':'PASSIVE','C2.2':'PASSIVE'})
        network=p['execution_inputs']['network'];network['drivers']=[]
        model=network['model_support']
        model['endpoint_roles']={'R2.2':'PASSIVE_RC','C2.1':'PASSIVE_RC',
            'U2.1':'HIGH_IMPEDANCE_RECEIVER','U3.1':'HIGH_IMPEDANCE_RECEIVER'}
        model['source_branches']=[['R2.1','R2.2'],['R3.1','R3.2']]
        rebind(p,r,db,a)
        self.assertFalse(validate_execution_audit(p,r,db,a)['errors'])
        db['pin2net']['U1.1']='GND';db['nets']['GND'].append('U1.1')
        self.assert_rejected(p,r,db,a,'SOURCE_NATIVE_INDEX')

    def test_declared_source_branch_cannot_join_unrelated_components(self):
        p,r,db,a=fixture()
        # Trigger passive-path reconciliation without inventing a driver on EN.
        db['pin2net']['U1.1']='SUPPLY';db['nets']['EN'].remove('U1.1')
        db['nets']['SUPPLY']=['U1.1']
        network=p['execution_inputs']['network'];network['drivers']=[]
        network['model_support']['endpoint_roles'].pop('U1.1')
        network['model_support']['source_branches']=[['U2.1','U3.1']]
        self.assert_rejected(p,r,db,a,'SOURCE_BRANCH')

    def test_absent_package_can_remain_na_without_inventing_members(self):
        p,r,db,a=fixture()
        scope=p['execution_inputs']['coverage']
        scope.update(applicability='NOT_APPLICABLE',members=[],evidence=r['checks'][0]['evidence'])
        c=next(x for x in p['checks'] if x['id']=='REQ-Q07.BOOT')
        c['applicability']='NOT_APPLICABLE'
        row=next(x for x in r['checks'] if x['id']==c['id'])
        row.update(applicability='NOT_APPLICABLE',review_result='NA',na_reason='Controlled fixture excludes this package')
        record=next(x for x in a['aggregates'] if x['id']=='BOOT-COVERAGE')
        record['member_results']={}
        rebind(p,r,db,a)
        self.assertTrue(validate_review(p,r,db,execution_audit=a)['valid'])
        scope.pop('evidence')
        self.assert_rejected(p,r,db,a,'AGGREGATE_APPLICABILITY')

    def test_undetermined_package_remains_insufficient_without_inventing_members(self):
        p,r,db,a=fixture()
        scope=p['execution_inputs']['coverage']
        scope.update(applicability='UNDETERMINED',members=[],evidence=r['checks'][0]['evidence'])
        c=next(x for x in p['checks'] if x['id']=='REQ-Q07.BOOT')
        c['applicability']='UNDETERMINED'
        row=next(x for x in r['checks'] if x['id']==c['id'])
        row.update(applicability='UNDETERMINED',review_result='INSUFFICIENT',evidence_confidence='C',
            missing_inputs=['feature_scope'],potential_severity='P2',gap_cause='EXTERNAL_DATA')
        next(x for x in a['aggregates'] if x['id']=='BOOT-COVERAGE')['member_results']={}
        p['execution_inputs']['feature_gap']={'required_inputs':['feature_scope'],'available_inputs':[]}
        p['execution_contract']['gaps'].append({'id':'FEATURE','check_id':c['id'],
            'basis':{'root':'plan','pointer':'/execution_inputs/feature_gap'}})
        a['gaps'].append({'id':'FEATURE','missing_inputs':['feature_scope']})
        rebind(p,r,db,a)
        self.assertTrue(validate_review(p,r,db,execution_audit=a)['valid'])
        row['review_result']='PASS'
        self.assert_rejected(p,r,db,a,'AGGREGATE_VERDICT')

    def test_required_audit_missing_is_rejected_without_breaking_old_api(self):
        p,r,db,a=fixture()
        self.assertTrue(without_execution_contract(p,r,db)['valid'])
        self.assertFalse(validate_review(p,r,db,require_execution_audit=True)['valid'])


if __name__ == '__main__':
    unittest.main()

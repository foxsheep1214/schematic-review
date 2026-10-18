"""Coverage contracts prevent stage deferral and compound-task regressions."""
import unittest
from copy import deepcopy
from review_obligations import contract, validate_obligations
from render_report import render_item
from test_review_stage_scope import request, IMPACT

E = [{'source': 'vendor.pdf', 'locator': 'working limits table, exact variant'}]


def fixture(rule='PRO-C03', result='INSUFFICIENT'):
    cid = rule + '.CONVERTER'; spec = contract(rule)
    p = {cid: {'id': cid, 'rule': rule, 'object': {'refs': ['T1', 'U1']}}}
    r = {'id': cid, 'review_result': result, 'rationale': 'Working waveform checked independently.',
         'obligations': {}, 'input_requests': {}, 'missing_inputs': [],
         'gap_cause': 'EXTERNAL_DATA', 'potential_severity': 'P1', 'blocking': True}
    for name in spec['obligations']:
        r['obligations'][name] = {'review_result': result, 'rationale': name + ' actual condition checked', 'evidence': deepcopy(E)}
        if result == 'INSUFFICIENT':
            req = dict(request(), closure_domain=spec['closure_domain'], potential_severity='P1',
                       impact_assessment=dict(IMPACT, consequence_class='REQUIRED_FUNCTION'))
            r['input_requests'][name] = req; r['missing_inputs'].append(name)
            r['obligations'][name]['request_keys'] = [name]
    if rule == 'PRO-C03':
        r['qualification_members'] = {ref: dict(review_result=result, working_basis='waveform range',
            qualification_basis='applicable rating conditions', comparison='missing repetitive rating' if result=='INSUFFICIENT' else 'working range within qualified conditions', evidence=deepcopy(E)) for ref in ['T1','U1']}
    t = {'id': 'W1', 'title': 'qualification', 'root_cause': 'working bounds', 'reason': 'actual scope',
         'check_ids': [cid], 'closure_domain': spec['closure_domain'], 'request_keys': {cid:list(r['input_requests'])}}
    return p, {cid:r}, [t]


class ObligationTests(unittest.TestCase):
    def test_complete_scoped_gap_and_explicit_pass_are_accepted(self):
        for rule in ['PRO-C03','PWR-C15']:
            for state in ['INSUFFICIENT','PASS']:
                self.assertEqual(validate_obligations(*fixture(rule,state)), [])

    def test_connectivity_pass_cannot_close_missing_working_qualification(self):
        p,r,t=fixture();r[next(iter(r))]['review_result']='PASS'
        self.assertTrue(any('worst obligation' in e for e in validate_obligations(p,r,t)))
        p,r,t=fixture(result='PASS');r[next(iter(r))].pop('obligations')
        self.assertTrue(validate_obligations(p,r,t))

    def test_each_barrier_member_is_required(self):
        for mutation in ['omit','empty_basis','pending_member']:
            p,r,t=fixture(result='PASS');members=r[next(iter(r))]['qualification_members']
            if mutation=='omit':members.pop('T1')
            if mutation=='empty_basis':members['T1']['working_basis']=''
            if mutation=='pending_member':members['T1']['review_result']='INSUFFICIENT'
            self.assertTrue(validate_obligations(p,r,t),mutation)

    def test_electrical_qualification_cannot_be_stage_na(self):
        for rule in ['PRO-C03','PWR-C15']:
            p,r,t=fixture(rule);row=r[next(iter(r))];row.update(review_result='NA',na_reason='OUTSIDE_SCHEMATIC_STAGE')
            self.assertTrue(any('stage NA' in e for e in validate_obligations(p,r,t)))

    def test_no_loop_topology_can_be_na_with_source(self):
        p,r,t=fixture('PWR-C15','NA');row=r[next(iter(r))]
        for v in row['obligations'].values():v['inapplicability_basis']='Passive feedthrough without a regulation feedback loop; nodes traced in schematic.'
        self.assertEqual(validate_obligations(p,r,t),[])
        next(iter(row['obligations'].values())).pop('inapplicability_basis')
        self.assertTrue(validate_obligations(p,r,t))

    def test_loop_cannot_be_replaced_by_a_clamp_request(self):
        p,r,t=fixture('PWR-C15');row=r[next(iter(r))]
        row['input_requests']['loop_model']['closure_domain']='switch_stress'
        self.assertTrue(validate_obligations(p,r,t))

    def test_unrelated_task_merge_rejected_even_with_valid_ownership(self):
        p,r,t=fixture('PWR-C15');cid='DRV-C02.Q1';p[cid]={'id':cid,'rule':'DRV-C02'}
        q=dict(request(),closure_domain='switch_stress');r[cid]={'id':cid,'review_result':'INSUFFICIENT','input_requests':{'short':q},'potential_severity':'P0'}
        t[0]['check_ids'].append(cid);t[0]['request_keys'][cid]=['short']
        self.assertTrue(any('unrelated request' in e for e in validate_obligations(p,r,t)))
        t[0]['check_ids'].remove(cid);t[0]['request_keys'].pop(cid)
        t.append({'id':'W2','check_ids':[cid],'request_keys':{cid:['short']}})
        self.assertEqual(validate_obligations(p,r,t),[])

    def test_owning_loop_branch_of_shared_check_is_allowed(self):
        p,r,t=fixture('PWR-C15');cid='DEV-C05.U1'
        p[cid]={'id':cid,'rule':'DEV-C05'}
        requests={}
        for key,domain,level,cls in [('loop','loop_stability','P1','REQUIRED_FUNCTION'),('stress','switch_stress','P0','DAMAGE_OR_HAZARD')]:
            requests[key]=dict(request(),closure_domain=domain,potential_severity=level,impact_assessment=dict(IMPACT,consequence_class=cls))
        r[cid]={'id':cid,'review_result':'INSUFFICIENT','input_requests':requests,'potential_severity':'P0','gap_cause':'EXTERNAL_DATA','blocking':True}
        t[0]['check_ids'].append(cid);t[0]['request_keys'][cid]=['loop'];t.append({'id':'W2','check_ids':[cid],'request_keys':{cid:['stress']}})
        self.assertEqual(validate_obligations(p,r,t),[])

    def test_plan_contract_cannot_be_weakened(self):
        p,r,t=fixture('PWR-C15');p[next(iter(p))]['closure_contract']={'obligations':{}}
        r[next(iter(r))]['obligations'].pop('loop_model')
        self.assertTrue(validate_obligations(p,r,t))

    def test_distinct_loops_cannot_merge_just_because_domain_matches(self):
        p,r,t=fixture('PWR-C15'); first=next(iter(p)); second='PWR-C15.OTHER'
        p[first]['object']['circuit']='PFC'
        p[second]=deepcopy(p[first]);p[second]['id']=second;p[second]['object']['circuit']='FLYBACK'
        r[second]=deepcopy(r[first]);r[second]['id']=second
        t[0]['check_ids'].append(second);t[0]['request_keys'][second]=list(r[second]['input_requests'])
        self.assertTrue(any('distinct converter loops' in e for e in validate_obligations(p,r,t)))
        p[second]['object']['circuit']='PFC'
        self.assertEqual(validate_obligations(p,r,t),[])

    def test_compact_task_keeps_specific_requests_without_generic_checklist(self):
        p,r,t=fixture('PWR-C15');before=deepcopy(r)
        text='\n'.join(render_item(t[0],r,{}))
        for req in r[next(iter(r))]['input_requests'].values():
            for key in ['required_scope', 'acquisition', 'closure_criterion']:
                self.assertIn(req[key], text)
        self.assertNotIn('必须核清',text)
        self.assertEqual(r,before)
        self.assertEqual(validate_obligations(p,r,t),[])

    def test_malformed_records_report_errors(self):
        for bad in [None,[],{'working_stress':None},'PASS']:
            p,r,t=fixture();r[next(iter(r))]['obligations']=bad
            self.assertTrue(validate_obligations(p,r,t))

    def test_unhashable_states_are_validation_errors(self):
        for bad in [[], {}]:
            p,r,t=fixture(); row=r[next(iter(r))]
            row['obligations']['working_stress']['review_result']=bad
            row['qualification_members']['T1']['review_result']=bad
            self.assertTrue(validate_obligations(p,r,t))

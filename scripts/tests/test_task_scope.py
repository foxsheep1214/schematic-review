"""Synthetic shared hazards must not leak between unrelated repair tasks."""
from copy import deepcopy
import unittest
from test_review_stage_scope import decisive, request, IMPACT
from task_scope import ownership, task_view
from ledger_v3 import validate_review
from render_report import render, render_item


def shared():
    p, r, db = decisive()
    r['workflow_version'] = 2
    row = r['checks'][0]; cid = row['id']
    row.update(potential_severity='P0', missing_inputs=['short waveform', 'loop model'])
    row['impact_assessment'].update(consequence_class='DAMAGE_OR_HAZARD', hazard_path='PROTECTION_LOSS')
    row['input_requests'] = {}
    for key, severity, cls in [('short waveform','P0','DAMAGE_OR_HAZARD'),
                                ('loop model','P1','PERFORMANCE_OR_LIFE')]:
        q = request(); q.update(potential_severity=severity,
            impact_assessment=dict(IMPACT, consequence_class=cls,
                                   **({'hazard_path': 'PROTECTION_LOSS'} if severity == 'P0' else {})))
        q.update(acquisition='Acquire '+key, closure_criterion='Close '+key, required_scope=key)
        row['input_requests'][key]=q
    t=r['work_items'][0]
    r['work_items']=[dict(deepcopy(t),id='W-SHORT',title='short',request_keys={cid:['short waveform']}),
                     dict(deepcopy(t),id='W-LOOP',title='loop',request_keys={cid:['loop model']})]
    return p,r,db


class TaskScopeTests(unittest.TestCase):
    def test_shared_row_preserves_hazard_without_contaminating_other_task(self):
        p,r,db=shared(); g=validate_review(p,r,db)
        self.assertTrue(g['valid'],g['errors']); self.assertEqual(g['release'],'NO_GO')
        rows={x['id']:x for x in r['checks']}; owners=ownership(r['work_items'])
        self.assertEqual([task_view(t,rows,owners)['level'] for t in r['work_items']],['P0','P1'])
        text=render(p,r,g)
        self.assertIn('2 件事项，其中 1 件',text)
        section=text.split('### W-LOOP')[1].split('## ',1)[0]
        self.assertIn('（P1）',section); self.assertIn('Acquire loop model',section)
        self.assertNotIn('Acquire short waveform',section); self.assertNotIn('Close short waveform',section)
        self.assertEqual(g['workflow']['work_items'][1]['request_keys'],r['work_items'][1]['request_keys'])

    def test_wrong_omitted_duplicate_and_unknown_request_keys_are_rejected(self):
        for keys in [[],['not a key'],['loop model','loop model'],['short waveform']]:
            p,r,db=shared();cid=r['checks'][0]['id']
            r['work_items'][1]['request_keys'][cid]=keys
            g=validate_review(p,r,db);self.assertFalse(g['valid'],keys)
        p,r,db=shared();r['work_items'][1].pop('request_keys')
        self.assertFalse(validate_review(p,r,db)['valid'])

    def test_shared_row_without_requests_keeps_its_level_for_every_owner(self):
        cid='PWR-C15.X';rows={cid:{'id':cid,'review_result':'INSUFFICIENT','potential_severity':'P0',
                                 'gap_cause':'REQUIREMENT_OPEN','input_requests':{}}}
        tasks=[{'id':'W1','check_ids':[cid]},{'id':'W2','check_ids':[cid]}];owners=ownership(tasks)
        for t in tasks:
            view=task_view(t,rows,owners)
            self.assertEqual((view['level'],view['ambiguous_checks'],view['requests']),('P0',[],[]))

    def test_only_the_hazard_owner_must_be_scheduled_now(self):
        p,r,db=shared();r['work_items'][1]['due_stage']='schematic_freeze'
        g=validate_review(p,r,db);self.assertTrue(g['valid'],g['errors'])
        r['work_items'][0]['due_stage']='schematic_freeze'
        self.assertFalse(validate_review(p,r,db)['valid'])

    def test_one_owner_needs_no_duplicate_branch_metadata(self):
        p,r,db=decisive();r['workflow_version']=2
        g=validate_review(p,r,db);self.assertTrue(g['valid'],g['errors'])
        self.assertIn('（P1）',render(p,r,g))

    def test_compact_keeps_action_and_links_full_preserves_every_detail(self):
        from test_check_explanations import synthetic
        p,r=synthetic(['FAIL','INSUFFICIENT']);g={'valid':True}
        snapshot=deepcopy((p,r,g));compact=render(p,r,g);full=render(p,r,g,detail='full')
        self.assertNotIn('## 逐项检查说明',compact)
        self.assertIn('(record/review-results.json)',compact)
        self.assertIn('## 逐项检查说明',full)
        self.assertIn('本次结论依据',full)
        self.assertLess(len(compact),len(full))
        self.assertEqual((p,r,g),snapshot)
        self.assertEqual(full.count('<details>'),full.count('</details>'))

    def test_board_gap_gets_localization_advice_not_an_automatic_pass(self):
        from review_quality import screen_quality
        p={'checks':[{'id':'DEV-C01.BOARD','rule':'DEV-C01','method':'C','object':{'board':'BOARD'}}]}
        r={'checks':[{'id':'DEV-C01.BOARD','review_result':'INSUFFICIENT'}]}
        before=deepcopy(r)
        self.assertTrue(any(c['code']=='BROAD_CHECK_NEEDS_LOCALIZATION' for c in screen_quality(p,r)['candidates']))
        self.assertEqual(r,before)
        r['checks'][0]['split_out']=['DEV-C01.Q1']
        self.assertFalse(any(c['code']=='BROAD_CHECK_NEEDS_LOCALIZATION' for c in screen_quality(p,r)['candidates']))

    def test_localization_screen_survives_malformed_task_records(self):
        from review_quality import screen_quality
        p={'checks':[{'id':'DEV-C01.BOARD','rule':'DEV-C01','method':'C','object':{'board':'BOARD'}}]}
        r={'checks':[{'id':'DEV-C01.BOARD','review_result':'INSUFFICIENT'}],
           'work_items':[{'check_ids':['DEV-C01.BOARD']},
                         {'id':'bad','check_ids':[{}]},
                         {'id':'good','check_ids':['DEV-C01.BOARD']}]}
        c=next(c for c in screen_quality(p,r)['candidates'] if c['code']=='BROAD_CHECK_NEEDS_LOCALIZATION')
        self.assertEqual(c['task_ids'],['good'])

    def test_v2_component_damage_branch_is_graded_not_ambiguous(self):
        p,r,db=shared(); r['impact_class_version']=2
        row=r['checks'][0]; cid=row['id']
        for a in (row['impact_assessment'], row['input_requests']['short waveform']['impact_assessment']):
            a['hazard_path']='FIRE'
        row['input_requests']['loop model']['impact_assessment']['consequence_class']='COMPONENT_DAMAGE'
        g=validate_review(p,r,db); self.assertTrue(g['valid'], g['errors'])
        owners=ownership(r['work_items']); loop=r['work_items'][1]
        self.assertEqual(task_view(loop,{cid:row},owners,2)['ambiguous_checks'],[])
        self.assertEqual(task_view(loop,{cid:row},owners,2)['level'],'P1')
        # The same record read with the v1 class table cannot grade that branch.
        self.assertEqual(task_view(loop,{cid:row},owners,1)['ambiguous_checks'],[cid])
        self.assertNotIn('ambiguous', render(p,r,g))

if __name__=='__main__':unittest.main()

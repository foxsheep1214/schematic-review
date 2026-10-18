"""Synthetic shared hazards must not leak between unrelated repair tasks."""
from copy import deepcopy
import unittest
from test_review_stage_scope import decisive, request, IMPACT
from task_scope import ownership, task_view
from validate_review import validate_review
from render_report import render, render_item


def shared():
    p, r, db = decisive()
    r['workflow_version'] = 2
    row = r['checks'][0]; cid = row['id']
    row.update(potential_severity='P0', missing_inputs=['short waveform', 'loop model'])
    row['impact_assessment'].update(consequence_class='DAMAGE_OR_HAZARD')
    row['input_requests'] = {}
    for key, severity, cls in [('short waveform','P0','DAMAGE_OR_HAZARD'),
                                ('loop model','P1','PERFORMANCE_OR_LIFE')]:
        q = request(); q.update(potential_severity=severity,
            impact_assessment=dict(IMPACT, consequence_class=cls))
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

    def test_declared_branch_cannot_hide_the_aggregate_hazard(self):
        p,r,db=shared(); q=r['checks'][0]['input_requests']['short waveform']
        q['potential_severity']='P1';q['impact_assessment']['consequence_class']='PERFORMANCE_OR_LIFE'
        g=validate_review(p,r,db);self.assertFalse(g['valid'])
        self.assertTrue(any('preserve the aggregate' in x for x in g['errors']))
        p,r,db=shared();r['checks'][0]['input_requests']['short waveform'].pop('impact_assessment')
        self.assertFalse(validate_review(p,r,db)['valid'])

    def test_legacy_ambiguous_ownership_is_visible_not_assigned_by_text(self):
        p,r,db=shared();r['workflow_version']=1
        for t in r['work_items']:t.pop('request_keys')
        g=validate_review(p,r,db);self.assertTrue(g['valid'],g['errors'])
        text=render(p,r,g);self.assertIn('任务归属待整理',text)
        self.assertNotIn('其中 2 件可能涉及',text)
        self.assertNotIn('Acquire short waveform',text)
        self.assertEqual(g['release'],'NO_GO')
        self.assertIn('2 件尚不能独立定级',text)

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

if __name__=='__main__':unittest.main()

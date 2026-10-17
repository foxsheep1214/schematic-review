"""Check purpose survives generation, review and rendering without inventing defects."""
import copy
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import unittest
from unittest.mock import patch
import catalog
from plan_review import build_review_plan
from render_report import render, render_check_explanations
from validate_review import validate_review, fingerprint
from test_plan_review import sample_db
from test_validate_review import fixture


class CheckExplanationTests(unittest.TestCase):
    def test_catalog_coverage_and_independent_snapshots(self):
        self.assertEqual(set(catalog.EXPLANATIONS), set(catalog.BY_ID))
        for rule in catalog.RULES:
            value = catalog.explanation(rule.id)
            self.assertEqual(catalog.explanation_errors(value), [])
            self.assertNotEqual(value['purpose'], rule.title)
            value['purpose'] = 'changed'
            self.assertNotEqual(catalog.explanation(rule.id)['purpose'], 'changed')

    def test_new_plans_explain_every_check_without_setting_verdicts(self):
        plan = build_review_plan(sample_db())
        self.assertEqual(sorted(plan['check_explanations']), sorted({c['rule'] for c in plan['checks']}))
        for check in plan['checks']:
            self.assertNotIn('check_explanation', check)  # 每条规则只存一份
            self.assertEqual(plan['check_explanations'][check['rule']], catalog.explanation(check['rule']))
            if check['applicability'] != 'NOT_APPLICABLE':
                self.assertIsNone(check['review_result'])
            self.assertNotIn('potential_severity', check)

    def test_merged_manual_checks_get_current_rule_explanation(self):
        db = sample_db()
        old = build_review_plan(db)
        row = copy.deepcopy(next(c for c in old['checks'] if c['rule'] == 'DEV-C01'))
        row['id'] = 'DEV-C01.MANUAL_EXTRA'
        row['check_explanation'] = catalog.explanation('DEV-C01')  # 旧版逐行说明
        old['checks'].append(row)
        new = build_review_plan(db, previous_plan=old)
        retained = next(c for c in new['checks'] if c['id'] == row['id'])
        self.assertNotIn('check_explanation', retained)
        self.assertEqual(new['check_explanations']['DEV-C01'], catalog.explanation('DEV-C01'))

    def test_shared_plan_explanation_cannot_be_changed_or_dropped(self):
        p, r, db = fixture()
        p['check_explanations'] = catalog.explanations_for(c['rule'] for c in p['checks'])
        r['plan_digest'] = fingerprint(p)
        self.assertTrue(validate_review(p, r, db)['valid'])
        rule = p['checks'][0]['rule']
        p['check_explanations'][rule] = dict(p['check_explanations'][rule], risk_if_omitted='nothing')
        r['plan_digest'] = fingerprint(p)
        self.assertTrue(any('check_explanations' in e for e in validate_review(p, r, db)['errors']))
        del p['check_explanations'][rule]
        r['plan_digest'] = fingerprint(p)
        self.assertTrue(any('缺少规则' in e for e in validate_review(p, r, db)['errors']))

    def test_shared_explanation_renders_per_check(self):
        p, r, db = fixture()
        p['check_explanations'] = catalog.explanations_for(c['rule'] for c in p['checks'])
        text = '\n'.join(render_check_explanations(p, r))
        for check in p['checks']:
            self.assertIn(check['id'], text)
        self.assertIn(catalog.explanation(p['checks'][0]['rule'])['purpose'], text)
        self.assertNotIn('记录未提供', text)

    def test_plan_explanation_cannot_be_changed_to_hide_risk(self):
        p, r, db = fixture()
        c = p['checks'][0]
        c['check_explanation'] = catalog.explanation(c['rule'])
        r['plan_digest'] = fingerprint(p)
        self.assertTrue(validate_review(p, r, db)['valid'])
        c['check_explanation']['risk_if_omitted'] = 'nothing to review'
        r['plan_digest'] = fingerprint(p)
        self.assertTrue(any('check_explanation' in e for e in validate_review(p, r, db)['errors']))

    def test_object_specific_result_does_not_change_verdict_or_bound_criterion(self):
        p, r, db = fixture()
        before = validate_review(p, r, db)
        r['checks'][0]['check_explanation'] = {
            'purpose': '核 U1 使能高低电平。',
            'risk_if_omitted': '可能漏掉 U1 无法关闭的情况。',
            'connections': '复用上游轨范围；具体源和状态见本项证据。'}
        after = validate_review(p, r, db)
        self.assertTrue(after['valid'], after['errors'])
        self.assertEqual(after['release'], before['release'])
        self.assertEqual(after['blockers'], before['blockers'])
        r['checks'][0]['check_explanation']['purpose'] = '  '
        self.assertTrue(any('check_explanation' in e for e in validate_review(p, r, db)['errors']))

    def test_all_results_are_explained_and_specific_text_wins(self):
        plan, result = {'checks': []}, {'checks': []}
        for status in ['PASS', 'FAIL', 'INSUFFICIENT', 'NA']:
            key = 'DRV-C01.' + status
            plan['checks'].append({'id': key, 'object': {'ref': key},
                                   'check_explanation': catalog.explanation('DRV-C01')})
            result['checks'].append({'id': key, 'review_result': status, 'rationale': 'reason ' + status})
        result['checks'][0]['check_explanation'] = {
            'purpose': '核反激漏感吸收的应力。', 'risk_if_omitted': '吸收支路可能超额。',
            'connections': '复用实际反激路径及停能窗口。'}
        text = '\n'.join(render_check_explanations(plan, result))
        for row in result['checks']:
            self.assertIn(row['id'], text)
            self.assertIn(row['rationale'], text)
        self.assertIn('核反激漏感吸收的应力。', text)
        self.assertIn('计划中的规则通用说明', text)
        self.assertNotIn('P0', text)

    def test_legacy_render_does_not_borrow_current_rule_explanations(self):
        p, r, db = fixture()
        before = render(p, r, validate_review(p, r, db))
        with patch.dict(catalog.EXPLANATIONS, {'RST-E01': ('new purpose', 'new risk', 'new connection')}):
            after = render(p, r, validate_review(p, r, db))
        self.assertEqual(before, after)
        self.assertNotIn('new purpose', after)
        self.assertEqual(render_check_explanations(p, r), [])

    def test_missing_legacy_explanation_in_mixed_record_is_visible(self):
        p, r, db = fixture()
        p['checks'][0]['check_explanation'] = catalog.explanation(p['checks'][0]['rule'])
        text = '\n'.join(render_check_explanations(p, r))
        self.assertIn('记录未提供', text)
        for check in p['checks']:
            self.assertIn(check['id'], text)

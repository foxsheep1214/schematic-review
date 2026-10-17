"""Check explanations survive generation, review and rendering without inventing defects."""
import copy
import re
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

V2 = {'risk_if_omitted': '吸收支路额定够，关断峰压仍可能超过 MOS 耐压', 'closes_when': '钳位电压与功耗有界即关闭',
      'false_alarms': '跨开关的 TVS 也是吸收路径'}


def synthetic(statuses, explanation=None):
    plan, result = {'checks': [], 'check_explanations': {'DRV-C01': explanation or dict(V2)}}, {'checks': []}
    for status in statuses:
        key = 'DRV-C01.' + status
        plan['checks'].append({'id': key, 'rule': 'DRV-C01', 'object': {'ref': key}})
        result['checks'].append({'id': key, 'review_result': status, 'rationale': 'reason ' + status})
    return plan, result


class CatalogExplanationTests(unittest.TestCase):
    def test_every_rule_is_explained_and_snapshots_are_independent(self):
        self.assertEqual(set(catalog.EXPLANATIONS), set(catalog.BY_ID))
        for rule in catalog.RULES:
            self.assertEqual(catalog.catalog_explanation_errors(rule.id), [], rule.id)
            value = catalog.explanation(rule.id)
            value['risk_if_omitted'] = 'changed'
            self.assertNotEqual(catalog.explanation(rule.id)['risk_if_omitted'], 'changed')

    def test_rewritten_entries_follow_the_writing_rules(self):
        for rule, value in catalog.EXPLANATIONS.items():
            if isinstance(value, tuple):
                continue
            with self.subTest(rule=rule):
                self.assertLessEqual(set(value), set(catalog.EXPLANATION_FIELDS))
                for field in catalog.REQUIRED_EXPLANATION_FIELDS:
                    self.assertTrue(value.get(field, '').strip())
                for field, limit in catalog.EXPLANATION_LIMITS.items():
                    self.assertLessEqual(len(value.get(field, '')), limit, field)
                if catalog.method_of(rule) == 'A':
                    self.assertTrue(value.get('false_alarms'))
                for ref in re.findall(r'[A-Z]{3}-[A-Z]\d{2}', ' '.join(value.values())):
                    self.assertTrue(catalog.known(ref), ref)

    def test_catalog_rejects_missing_closing_condition_and_overlong_text(self):
        with patch.dict(catalog.EXPLANATIONS, {'DRV-C01': {'risk_if_omitted': '漏'}}):
            self.assertTrue(catalog.catalog_explanation_errors('DRV-C01'))
        with patch.dict(catalog.EXPLANATIONS, {'DRV-C01': dict(V2, closes_when='长' * 51)}):
            self.assertTrue(any('超过' in e for e in catalog.catalog_explanation_errors('DRV-C01')))
        with patch.dict(catalog.EXPLANATIONS, {'DRV-A01': {'risk_if_omitted': '漏', 'closes_when': '关'}}):
            self.assertTrue(any('false_alarms' in e for e in catalog.catalog_explanation_errors('DRV-A01')))

    def test_override_may_change_a_single_field(self):
        self.assertEqual(catalog.explanation_errors({'closes_when': '本板只需核 D1'}, partial=True), [])
        self.assertTrue(catalog.explanation_errors({'closes_when': ' '}, partial=True))
        self.assertTrue(catalog.explanation_errors({}, partial=True))
        self.assertTrue(catalog.explanation_errors({'severity': 'P0'}, partial=True))


class PlanExplanationTests(unittest.TestCase):
    def test_new_plans_store_one_versioned_explanation_per_rule(self):
        plan = build_review_plan(sample_db())
        self.assertEqual(plan['check_explanations_version'], catalog.EXPLANATION_VERSION)
        self.assertEqual(sorted(plan['check_explanations']), sorted({c['rule'] for c in plan['checks']}))
        for check in plan['checks']:
            self.assertNotIn('check_explanation', check)
            self.assertEqual(plan['check_explanations'][check['rule']], catalog.explanation(check['rule']))
            if check['applicability'] != 'NOT_APPLICABLE':
                self.assertIsNone(check['review_result'])

    def test_merged_rows_drop_legacy_per_row_copies(self):
        db = sample_db()
        old = build_review_plan(db)
        row = copy.deepcopy(next(c for c in old['checks'] if c['rule'] == 'DEV-C01'))
        row['id'] = 'DEV-C01.MANUAL_EXTRA'
        row['check_explanation'] = {'purpose': '旧', 'risk_if_omitted': '旧', 'connections': '旧'}
        old['checks'].append(row)
        new = build_review_plan(db, previous_plan=old)
        self.assertNotIn('check_explanation', next(c for c in new['checks'] if c['id'] == row['id']))

    def test_current_plan_explanation_cannot_be_changed_or_dropped(self):
        p, r, db = fixture()
        p['check_explanations'] = catalog.explanations_for(c['rule'] for c in p['checks'])
        p['check_explanations_version'] = catalog.EXPLANATION_VERSION
        r['plan_digest'] = fingerprint(p)
        self.assertTrue(validate_review(p, r, db)['valid'])
        rule = p['checks'][0]['rule']
        p['check_explanations'][rule] = dict(p['check_explanations'][rule], risk_if_omitted='nothing')
        r['plan_digest'] = fingerprint(p)
        self.assertTrue(any('check_explanations' in e for e in validate_review(p, r, db)['errors']))
        del p['check_explanations'][rule]
        r['plan_digest'] = fingerprint(p)
        self.assertTrue(any('缺少规则' in e for e in validate_review(p, r, db)['errors']))

    def test_older_plan_versions_are_checked_for_structure_not_rewritten(self):
        p, r, db = fixture()
        p['check_explanations'] = {c['rule']: {'purpose': '旧目的', 'risk_if_omitted': '旧风险', 'connections': '旧衔接'}
                                   for c in p['checks']}
        r['plan_digest'] = fingerprint(p)
        self.assertTrue(validate_review(p, r, db)['valid'], validate_review(p, r, db)['errors'])
        p['check_explanations'][p['checks'][0]['rule']]['purpose'] = ' '
        r['plan_digest'] = fingerprint(p)
        self.assertTrue(any('check_explanations' in e for e in validate_review(p, r, db)['errors']))

    def test_object_override_does_not_change_verdict(self):
        p, r, db = fixture()
        before = validate_review(p, r, db)
        r['checks'][0]['check_explanation'] = {'closes_when': '本板只需核 U1 使能脚的高低电平。'}
        after = validate_review(p, r, db)
        self.assertTrue(after['valid'], after['errors'])
        self.assertEqual((after['release'], after['blockers']), (before['release'], before['blockers']))
        r['checks'][0]['check_explanation'] = {'closes_when': '  '}
        self.assertTrue(any('check_explanation' in e for e in validate_review(p, r, db)['errors']))


class RenderExplanationTests(unittest.TestCase):
    def test_only_open_checks_are_expanded_and_na_gets_one_line(self):
        text = '\n'.join(render_check_explanations(*synthetic(['PASS', 'FAIL', 'INSUFFICIENT', 'NA'])))
        for status in ('FAIL', 'INSUFFICIENT'):
            self.assertIn('### DRV-C01.%s' % status, text)
            self.assertIn('reason ' + status, text)
        self.assertNotIn('DRV-C01.PASS', text)
        self.assertIn('- DRV-C01.NA：reason NA', text)
        self.assertIn('其余 1 项通过或未审结', text)
        self.assertEqual(text.count(V2['closes_when']), 2)
        self.assertNotIn('P0', text)

    def test_single_field_override_wins_and_is_labelled(self):
        plan, result = synthetic(['FAIL'])
        result['checks'][0]['check_explanation'] = {'closes_when': '本板 D1 钳位电压有界即关闭'}
        text = '\n'.join(render_check_explanations(plan, result))
        self.assertIn('关闭条件**（本次对象说明）：本板 D1 钳位电压有界即关闭', text)
        self.assertIn(V2['risk_if_omitted'], text)
        self.assertNotIn(V2['closes_when'], text)

    def test_legacy_explanations_still_render(self):
        legacy = {'purpose': '旧目的', 'risk_if_omitted': '旧风险', 'connections': '旧衔接'}
        text = '\n'.join(render_check_explanations(*synthetic(['FAIL'], legacy)))
        for value in legacy.values():
            self.assertIn(value, text)

    def test_records_without_explanations_do_not_borrow_the_live_catalog(self):
        p, r, db = fixture()
        before = render(p, r, validate_review(p, r, db))
        with patch.dict(catalog.EXPLANATIONS, {'RST-E01': dict(V2, risk_if_omitted='new risk')}):
            after = render(p, r, validate_review(p, r, db))
        self.assertEqual(before, after)
        self.assertNotIn('new risk', after)
        self.assertEqual(render_check_explanations(p, r), [])


if __name__ == '__main__':
    unittest.main()

"""SR independently re-judges ASG's part selection and the attribution of last round's comments."""
import json
import pathlib
import sys
import tempfile
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import review_selection as rs


def asg_record(tmp):
    rec = pathlib.Path(tmp) / 'v1' / 'record'
    rec.mkdir(parents=True)
    (rec / 'selection.json').write_text(json.dumps({'schema_version': 1, 'roles': [
        {'role': 'PFC 控制器', 'refs': ['U201'], 'decisive': [{'param': '输入电压范围', 'op': 'covers', 'limit': [90, 264], 'unit': 'Vac'}],
         'sources': ['x'], 'candidates': [
             {'mpn': 'PFC-A', 'status': 'selected', 'datasheet': 'a.pdf', 'reason': 'r'},
             {'mpn': 'PFC-B', 'status': 'rejected', 'datasheet': 'b.pdf', 'reason': 'r'}]}]}), encoding='utf-8')
    (rec / 'review-responses.json').write_text(json.dumps({'schema_version': 1, 'sources': [], 'items': [
        {'id': 'W-AC', 'comment': 'c', 'response': 'DESIGN', 'cause': 'rule_not_enforced'},
        {'id': 'W-X', 'comment': 'c', 'response': 'DECLINE'}]}), encoding='utf-8')
    return rec.parent


class ReviewSelectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.asg = asg_record(self.tmp.name)
        self.review = rs.worksheet(self.asg)

    def tearDown(self):
        self.tmp.cleanup()

    def test_worksheet_lists_roles_and_attributed_items_without_verdicts(self):
        role = self.review['roles'][0]
        self.assertEqual(('PFC 控制器', 'PFC-A', None), (role['role'], role['asg_selected'], role['verdict']))
        self.assertEqual([{'mpn': 'PFC-A', 'status': 'selected', 'reject_kind': None}, {'mpn': 'PFC-B', 'status': 'rejected', 'reject_kind': None}], role['asg_candidates'])
        self.assertEqual(['W-AC', 'W-X'], [a['id'] for a in self.review['attribution']])

    def test_blank_worksheet_fails_validation(self):
        errors = rs.validate(self.review, self.asg)
        self.assertIn('角色“PFC 控制器”的 verdict 必须是 AGREE/DISAGREE/INSUFFICIENT 之一', errors)
        self.assertIn('意见 W-AC：agree 要写 true/false', errors)
        self.assertFalse(any('W-X' in e for e in errors), errors)

    def test_agree_needs_basis_with_page_and_condition_completeness(self):
        role = self.review['roles'][0]
        role.update(verdict='AGREE', basis='同意', conditions_complete=False)
        self.review['attribution'][0]['agree'] = True
        errors = rs.validate(self.review, self.asg)
        self.assertIn('角色“PFC 控制器”判决定性条件不完整，要写出缺的条件（missing_condition）', errors)
        self.assertIn('角色“PFC 控制器”的结论要有依据和页码（basis/pages）', errors)
        role.update(basis='p.1 输入范围与多模特性与需求一致', conditions_complete=True)
        self.assertEqual([], rs.validate(self.review, self.asg))

    def test_disagree_needs_an_alternative_or_a_named_asg_error(self):
        role = self.review['roles'][0]
        role.update(verdict='DISAGREE', basis='p.3 待机功耗超预算', conditions_complete=True)
        self.review['attribution'][0]['agree'] = True
        errors = rs.validate(self.review, self.asg)
        self.assertIn('角色“PFC 控制器”不同意时要给 ASG 候选之外的型号（alternative_mpn）或指出 ASG 淘汰理由的错误（asg_error）', errors)
        role['alternative_mpn'] = 'PFC-A'
        self.assertIn('角色“PFC 控制器”不同意却给出 ASG 已选定的 PFC-A', rs.validate(self.review, self.asg))
        role['alternative_mpn'] = ''
        role['asg_error'] = '淘汰理由写错了'
        self.assertIn('角色“PFC 控制器”的 asg_error 要点名 ASG 候选里的哪个型号被错误淘汰或错误选中', rs.validate(self.review, self.asg))
        role['asg_error'] = 'PFC-B 的轻载模式判断错误：p.1 有跳周期'
        self.assertEqual([], rs.validate(self.review, self.asg))
        self.assertIn('淘汰理由有误：PFC-B', rs.summary(self.review))

    def test_attribution_disagreement_needs_another_cause_and_reason(self):
        role = self.review['roles'][0]
        role.update(verdict='AGREE', basis='p.1 ok', conditions_complete=True)
        a = self.review['attribution'][0]
        a.update(agree=False, cause='rule_not_enforced')
        errors = rs.validate(self.review, self.asg)
        self.assertIn('意见 W-AC：不同意 ASG 的归因 rule_not_enforced 时要给出另一类归因（rule_missing/rule_not_enforced/knowledge_missing/knowledge_wrong/judgment/none）', errors)
        self.assertIn('意见 W-AC：不同意归因要写理由', errors)
        a.update(cause='rule_missing', reason='没有任何规则要求分断能力与浪涌配合')
        self.assertEqual([], rs.validate(self.review, self.asg))
        self.assertIn('W-AC：ASG 归因 rule_not_enforced，应为 rule_missing', rs.summary(self.review))

    def test_cli_roundtrip(self):
        out = pathlib.Path(self.tmp.name) / 'review.json'
        self.assertEqual(0, rs.main(['worksheet', str(self.asg), '--out', str(out)]))
        self.assertEqual(1, rs.main(['validate', str(out), '--asg', str(self.asg)]))


if __name__ == '__main__':
    unittest.main()

"""Item 3 of the 2026-10-26 review of SR (user: 第三第四项也做): a deliverable another stage owes (custom-part drawing,
configuration table, firmware capability) is a condition of the freeze, not a review finding. R7 claude1: 52 of 72
INSUFFICIENT rows waited for deliverables and dominated 待办 and 最先要解决的 3 件事. It now caps the release at
CONDITIONAL_GO instead of blocking, leaves 待办 and the first-three list, and is listed for the project manager under
等交付物 with owner, artifact, assumption and what counts as delivered.
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_review as vr
from render_report import render
import test_review_functions as trf   # the class is not imported by name: pytest would collect it twice
from test_review_functions import bias_function, ledger


def pending_ledger(**item):
    fn = bias_function()
    fn['open'] = [dict(trf.DeliverablePendingTests('pending').pending(), **item)]
    return ledger(fn)


class DeliverableReleaseTests(unittest.TestCase):
    def test_a_pending_deliverable_caps_the_release_and_blocks_nothing(self):
        p, r, db = pending_ledger()
        out = vr.validate_review(p, r, db)
        self.assertTrue(out['valid'], out['errors'])
        self.assertEqual((out['release'], out['blockers']), ('CONDITIONAL_GO', []))
        self.assertEqual(len(out['pending_deliverables']), 2)
        self.assertFalse(any('unresolved blocking' in b for b in out['blockers']))

    def test_a_p0_deliverable_is_still_only_conditional(self):
        p, r, db = pending_ledger(severity={'level': 'P0', 'class': 'DAMAGE_OR_HAZARD', 'affects': 'T1',
                                            'hazard_path': 'INSULATION', 'consequence': '绝缘不足时初次级击穿'})
        out = vr.validate_review(p, r, db)
        self.assertEqual(out['release'], 'CONDITIONAL_GO', out['blockers'])

    def test_a_vendor_datum_of_the_same_severity_still_blocks(self):
        fn = bias_function()
        p, r, db = ledger(fn)                       # the fixture's own VENDOR_DATUM item, P1
        out = vr.validate_review(p, r, db)
        self.assertEqual(out['release'], 'NO_GO')
        self.assertTrue(any('unresolved blocking INSUFFICIENT' in b for b in out['blockers']), out['blockers'])

    def test_release_for_counts_pending_deliverables(self):
        self.assertEqual(vr.release_for([], [], False, ['A.1']), 'CONDITIONAL_GO')
        self.assertEqual(vr.release_for([], [], False, []), 'GO')
        self.assertEqual(vr.release_for([], ['b'], False, ['A.1']), 'NO_GO')


class DeliverableReportTests(unittest.TestCase):
    def setUp(self):
        self.p, self.r, self.db = pending_ledger()
        self.out = vr.validate_review(self.p, self.r, self.db)
        self.text = render(self.p, self.r, self.out)

    def test_the_section_lists_owner_artifact_assumption_and_closure(self):
        section = self.text.split('## 等交付物')[1].split('\n## ')[0]
        self.assertIn('| W-T1-DRAWING | T1 磁件规格书：三重线型号、绕组顺序、边距、耐压试验值 | 磁件设计 | 定制件图纸 | 必需功能可能不达标（P1） |', section)
        self.assertIn('按 intent 的 48:6:21 匝比和三重线次级计算', section)
        self.assertIn('规格书给出上述项且耐压 ≥ 3000 Vac', section)
        self.assertIn('| 2 条 |', section)

    def test_the_deliverable_leaves_the_work_list_the_first_three_and_the_blockers(self):
        self.assertNotIn('## 待办', self.text)
        self.assertNotIn('最先要解决', self.text)
        self.assertNotIn('还没归入待办', self.text)
        self.assertIn('**可以有条件定稿。**', self.text)
        self.assertIn('| 待办（同一原因合并） | 0 件 |', self.text)
        self.assertIn('| 等交付物（不算审查发现，准出最高有条件定稿） | 1 项 |', self.text)

    def test_without_deliverables_the_section_and_the_count_line_do_not_appear(self):
        from render_report import render_deliverables
        self.assertEqual(render_deliverables([], {}), [])
        p, r, db = ledger(bias_function())
        text = render(p, r, vr.validate_review(p, r, db))
        self.assertNotIn('等交付物（不算审查发现', text)
        self.assertNotIn('## 等交付物', text)


if __name__ == '__main__':
    unittest.main()

"""2026-10-19 对 ASG 100W PD 适配器 R5 的审查报告（SR-20261019-R5-独立审查-b00f8e2）暴露的报告与筛查缺口。"""
import unittest

from test_render_and_pack import body, report
from test_review_stage_scope import decisive
from render_report import notes_errors, render_item
from review_quality import templated_task_text, text_hygiene


class HowToCloseShownOnceTest(unittest.TestCase):
    """R5 W-ESD：待办 next_action 与缺口 how_to_close 只差页码，“怎么补”把两句都印了出来。"""

    def test_next_action_that_restates_the_gap_is_not_printed_twice(self):
        p, r, db = decisive()
        acquisition = r['checks'][0]['input_requests']['startup load current envelope']['acquisition']
        r['work_items'][0]['next_action'] = 'System engineer derives controlled bound (p3–5) from installed loads'
        text = body(report(p, r, db)[0])
        line = next(l for l in text.splitlines() if l.startswith('- **怎么补**'))
        self.assertEqual(line, '- **怎么补**：' + acquisition)

    def test_a_different_next_action_stays(self):
        p, r, db = decisive()
        r['work_items'][0]['next_action'] = 'Ask the PSU vendor for the hiccup timing table'
        line = next(l for l in body(report(p, r, db)[0]).splitlines() if l.startswith('- **怎么补**'))
        self.assertIn('Ask the PSU vendor for the hiccup timing table', line)


class SharedReasonTest(unittest.TestCase):
    """R5：15 件待办的 reason 都是“该资料决定当前电路能否满足所列功能，应在定稿前解决。”，逐件印进“缺什么”。"""
    REASON = '该资料决定当前电路能否满足所列功能，应在定稿前解决。'

    def tasks(self):
        return [{'id': 'W-%d' % i, 'title': 'T%d' % i, 'root_cause': '根因 %d' % i, 'reason': self.REASON,
                 'next_action': '动作 %d' % i, 'check_ids': ['C.%d' % i]} for i in range(3)]

    def test_screen_names_the_shared_reason(self):
        hit = [c for c in templated_task_text({'work_items': self.tasks(), 'checks': []}, {})
               if c['code'] == 'TEMPLATED_WORK_ITEM_REASON']
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0]['task_ids'], ['W-0', 'W-1', 'W-2'])
        self.assertFalse([c for c in templated_task_text({'work_items': self.tasks()[:2], 'checks': []}, {})
                          if c['code'] == 'TEMPLATED_WORK_ITEM_REASON'])

    def test_report_leaves_a_shared_reason_out(self):
        task = self.tasks()[0]
        lines = render_item(task, {}, {}, shared_reasons={self.REASON})
        self.assertFalse(any(self.REASON in l for l in lines))
        self.assertTrue(any(self.REASON in l for l in render_item(task, {}, {})))


class GluedTextOutsideRequestsTest(unittest.TestCase):
    """R5：“Q4011.50W”在移交要求、“U60111/TP602/U2022”在手工核对说明里，粘连筛查只看待办和资料请求。"""

    def test_handoff_and_manual_verification_text_are_scanned(self):
        report_ = {'checks': [
            {'id': 'PWR-C05.X', 'review_result': 'NA', 'handoff': {'constraint': 'Q4011.50W 对应总热阻≤40K/W'}},
            {'id': 'DRV-E01.Y', 'review_result': 'PASS', 'manual_verification': {'method': '逐端追 U60111/TP602'}}]}
        hits = {(c['check_ids'][0], c['field']) for c in text_hygiene(report_, {'PWR-C05.X': {}, 'DRV-E01.Y': {}},
                                                                       {'Q401', 'U601', 'TP602'})
                if c['code'] == 'REF_GLUED_TO_VALUE'}
        self.assertEqual(hits, {('PWR-C05.X', 'handoff.constraint'), ('DRV-E01.Y', 'manual_verification.method')})


class RecordTalkInSummaryTest(unittest.TestCase):
    """R5 结论段：“已逐条复核104条记录质量提示；43条位号与数值粘连已修复……history-handling.json……first”。"""

    def test_summary_about_keeping_the_record_is_refused(self):
        for text in ('已逐条复核104条记录质量提示；43条位号与数值粘连已修复。',
                     '历史处理完整表见record/evidence/evidence/history-handling.json。',
                     '当前工具禁止first模式加入REQ-H02。'):
            self.assertTrue(notes_errors({'summary': text}), text)
        self.assertEqual(notes_errors({'summary': 'R5未发现新的错连；先确定T301跨隔离件的工作电压。'}), [])


if __name__ == '__main__':
    unittest.main()

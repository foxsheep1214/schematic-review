"""一份真实审查报告（2026-10-19）暴露的报告与筛查缺口；每个用例用合成数据复现。"""
import unittest

from test_render_and_pack import body, report
from test_review_stage_scope import decisive
from render_report import notes_errors, render, render_item
from review_quality import templated_task_text, text_hygiene


class HowToCloseShownOnceTest(unittest.TestCase):
    """真实反例：待办 next_action 与缺口 how_to_close 只差页码，“怎么补”把两句都印了出来。"""

    def test_next_action_that_restates_the_gap_is_not_printed_twice(self):
        p, r, db = decisive()
        acquisition = r['functions'][0]['open'][0]['acquisition']
        text = body(report(p, r, db)[0])
        line = next(l for l in text.splitlines() if l.startswith('- **还要做**'))
        self.assertEqual(line, '- **还要做**：' + acquisition)

    def test_a_different_next_action_stays(self):
        p, r, db = decisive()
        r['functions'][0]['open'][0]['acquisition'] = 'Ask the PSU vendor for the hiccup timing table'
        line = next(l for l in body(report(p, r, db)[0]).splitlines() if l.startswith('- **还要做**'))
        self.assertIn('Ask the PSU vendor for the hiccup timing table', line)


class SharedReasonTest(unittest.TestCase):
    """真实反例：十几件待办的 reason 都是“该资料决定当前电路能否满足所列功能，应在定稿前解决。”，逐件印进“缺什么”。"""
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
    """真实反例：“Q21.50W”在移交要求、“U111/TP2/U322”在手工核对说明里，粘连筛查只看待办和资料请求。"""

    def test_handoff_and_manual_verification_text_are_scanned(self):
        report_ = {'checks': [
            {'id': 'PWR-C05.X', 'review_result': 'NA', 'handoff': {'constraint': 'Q21.50W 对应总热阻≤40K/W'}},
            {'id': 'DRV-E01.Y', 'review_result': 'PASS', 'manual_verification': {'method': '逐端追 U111/TP2'}}]}
        hits = {(c['check_ids'][0], c['field']) for c in text_hygiene(report_, {'PWR-C05.X': {}, 'DRV-E01.Y': {}},
                                                                       {'Q2', 'U1', 'TP2'})
                if c['code'] == 'REF_GLUED_TO_VALUE'}
        self.assertEqual(hits, {('PWR-C05.X', 'handoff.constraint'), ('DRV-E01.Y', 'manual_verification.method')})


class RecordTalkInSummaryTest(unittest.TestCase):
    """真实结论段：“已逐条复核104条记录质量提示；43条位号与数值粘连已修复……history-handling.json……first”。"""

    def test_summary_about_keeping_the_record_is_refused(self):
        for text in ('已逐条复核104条记录质量提示；43条位号与数值粘连已修复。',
                     '历史处理完整表见record/evidence/evidence/history-handling.json。',
                     '当前工具禁止first模式加入REQ-H02。'):
            self.assertTrue(notes_errors({'summary': text}), text)
        self.assertEqual(notes_errors({'summary': '本轮未发现新的错连；先确定T1跨隔离件的工作电压。'}), [])


class FixedTodoLinesTest(unittest.TestCase):
    """真实反例：“怎么补”里两句都以“已读Q2的MOSFET手册 p3–7、D2手册 p2–5…”开头；“缺什么”第二句复述第一句。
    待办固定分行：缺什么 / 为什么要紧 / 已查过 / 还要做 / 怎样算通过，读过的资料只写一次。"""

    def lines(self, task, acquisition):
        checks = {'C': {'input_requests': {'x': {'acquisition': acquisition}}}}
        return {l.split('**')[1]: l.split('：', 1)[1] for l in render_item(dict(task, check_ids=['C']), checks, {})
                if l.startswith('- **')}

    def test_what_was_read_is_said_once_apart_from_what_is_left(self):
        got = self.lines({'id': 'W', 'title': 'Q2', 'root_cause': 'Q2小电流VGS仍是假设',
                          'next_action': '已读Q2的MOSFET手册 p3–7与磁件单；先取得Q2低电流界限'},
                         '已读Q2的MOSFET手册 p3–7和磁件设计单：现有曲线未给20mA下的VGS界限；取得该工作点曲线包络')
        self.assertEqual(got['已查过'], 'Q2的MOSFET手册 p3–7和磁件设计单：现有曲线未给20mA下的VGS界限')
        self.assertEqual(got['还要做'], '先取得Q2低电流界限；取得该工作点曲线包络')

    def test_why_it_matters_that_restates_the_gap_is_dropped(self):
        got = self.lines({'id': 'W', 'title': 'TH1', 'root_cause': 'TH1全温阻值范围未知',
                          'reason': 'TH1的全温阻值范围未知。', 'next_action': '向厂家取得R(T)'}, '')
        self.assertNotIn('为什么要紧', got)
        got = self.lines({'id': 'W', 'title': 'TH1', 'root_cause': 'TH1全温阻值范围未知',
                          'reason': '开短路判别要靠它定阈值。', 'next_action': '向厂家取得R(T)'}, '')
        self.assertEqual(got['为什么要紧'], '开短路判别要靠它定阈值。')


class SummaryAddsWhatTheFirstLineCannotTest(unittest.TestCase):
    """真实结论第二段：“本次使用SR <版本>重新审查当前版本……已重新导出、逐页读图和复算。当前仍不能定稿……”。"""

    def test_verdict_and_review_process_are_refused(self):
        for text in ('本次使用SR abc1234重新审查当前版本。', '已重新导出、逐页读图和复算。', '当前仍不能定稿：T1材料未定。'):
            self.assertTrue(notes_errors({'summary': text}), text)
        self.assertEqual(notes_errors({'summary': '与上一版相比三项旧错误已改；先确定T1各绝缘路径的工作电压。'}), [])


class SameHandoffOneRowTest(unittest.TestCase):
    """真实反例：三只输出电容的交接要求只差位号，表里印成三行。"""

    def test_requirements_differing_only_in_the_part_share_a_row(self):
        refs = ['C5', 'C6', 'C7', 'C9']
        plan = {'checks': [{'id': 'DEV-C04.' + r, 'object': {'ref': r}} for r in refs]}
        rows = [{'id': 'DEV-C04.' + r, 'review_result': 'NA_OUTSIDE_STAGE',
                 'handoff': {'required': True, 'receivers': ['热设计'], 'constraint': 'C5–C7热点≤105°C',
                             'verification': '测量%s本体热点' % r}} for r in refs[:3]]
        rows.append({'id': 'DEV-C04.C9', 'review_result': 'NA_OUTSIDE_STAGE',
                     'handoff': {'required': True, 'receivers': ['热设计'], 'constraint': 'C9热点≤75°C',
                                 'verification': '测量C9本体热点'}})
        text = render(plan, {'checks': rows}, {'valid': True, 'release': 'NO_GO', 'blockers': []})
        table = [l for l in text.split('## 交给后续环节的要求')[1].splitlines() if l.startswith('| 热设计')]
        self.assertEqual(len(table), 2)
        self.assertIn('| 热设计 | DEV-C04.C5、DEV-C04.C6、DEV-C04.C7 | C5、C6、C7 | C5–C7热点≤105°C | '
                      '测量每只本体热点 |', table)
        self.assertIn('| 热设计 | DEV-C04.C9 | C9 | C9热点≤75°C | 测量C9本体热点 |', table)


if __name__ == '__main__':
    unittest.main()

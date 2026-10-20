"""2026-10-19 对 ASG 100W PD 适配器 R5 的审查报告（SR-20261019-R5-独立审查-b00f8e2）暴露的报告与筛查缺口。"""
import unittest

from test_render_and_pack import body, report
from test_review_stage_scope import decisive
from render_report import notes_errors, render, render_item
from review_quality import open_despite_bounds, templated_task_text, text_hygiene


class HowToCloseShownOnceTest(unittest.TestCase):
    """R5 W-ESD：待办 next_action 与缺口 how_to_close 只差页码，“怎么补”把两句都印了出来。"""

    def test_next_action_that_restates_the_gap_is_not_printed_twice(self):
        p, r, db = decisive()
        acquisition = r['checks'][0]['input_requests']['startup load current envelope']['acquisition']
        r['work_items'][0]['next_action'] = 'System engineer derives controlled bound (p3–5) from installed loads'
        text = body(report(p, r, db)[0])
        line = next(l for l in text.splitlines() if l.startswith('- **还要做**'))
        self.assertEqual(line, '- **还要做**：' + acquisition)

    def test_a_different_next_action_stays(self):
        p, r, db = decisive()
        r['work_items'][0]['next_action'] = 'Ask the PSU vendor for the hiccup timing table'
        line = next(l for l in body(report(p, r, db)[0]).splitlines() if l.startswith('- **还要做**'))
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


class FixedTodoLinesTest(unittest.TestCase):
    """R5 新版复审：“怎么补”里两句都以“已读ISC032N12LM6 p3–7、PMEG6010 p2–5…”开头；“缺什么”第二句复述第一句。
    待办固定分行：缺什么 / 为什么要紧 / 已查过 / 还要做 / 怎样算通过，读过的资料只写一次。"""

    def lines(self, task, acquisition):
        checks = {'C': {'input_requests': {'x': {'acquisition': acquisition}}}}
        return {l.split('**')[1]: l.split('：', 1)[1] for l in render_item(dict(task, check_ids=['C']), checks, {})
                if l.startswith('- **')}

    def test_what_was_read_is_said_once_apart_from_what_is_left(self):
        got = self.lines({'id': 'W', 'title': 'Q401', 'root_cause': 'Q401小电流VGS仍是假设',
                          'next_action': '已读ISC032N12LM6 p3–7与磁件单；先取得Q401低电流界限'},
                         '已读ISC032N12LM6 p3–7和磁件设计单：现有曲线未给20mA下的VGS界限；取得该工作点曲线包络')
        self.assertEqual(got['已查过'], 'ISC032N12LM6 p3–7和磁件设计单：现有曲线未给20mA下的VGS界限')
        self.assertEqual(got['还要做'], '先取得Q401低电流界限；取得该工作点曲线包络')

    def test_why_it_matters_that_restates_the_gap_is_dropped(self):
        got = self.lines({'id': 'W', 'title': 'TH601', 'root_cause': 'TH601全温阻值范围未知',
                          'reason': 'TH601的全温阻值范围未知。', 'next_action': '向Murata取得R(T)'}, '')
        self.assertNotIn('为什么要紧', got)
        got = self.lines({'id': 'W', 'title': 'TH601', 'root_cause': 'TH601全温阻值范围未知',
                          'reason': '开短路判别要靠它定阈值。', 'next_action': '向Murata取得R(T)'}, '')
        self.assertEqual(got['为什么要紧'], '开短路判别要靠它定阈值。')


class SummaryAddsWhatTheFirstLineCannotTest(unittest.TestCase):
    """R5 新版复审结论第二段：“本次使用SR 2692b08重新审查当前R5……已重新导出、逐页读图和复算。当前仍不能定稿……”。"""

    def test_verdict_and_review_process_are_refused(self):
        for text in ('本次使用SR 2692b08重新审查当前R5。', '已重新导出、逐页读图和复算。', '当前仍不能定稿：T301材料未定。'):
            self.assertTrue(notes_errors({'summary': text}), text)
        self.assertEqual(notes_errors({'summary': '与R4相比三项旧错误已改；先确定T301各绝缘路径的工作电压。'}), [])


class SameHandoffOneRowTest(unittest.TestCase):
    """R5 新版复审：C503、C504、C505 的交接要求只差位号，表里印成三行。"""

    def test_requirements_differing_only_in_the_part_share_a_row(self):
        refs = ['C503', 'C504', 'C505', 'C201']
        plan = {'checks': [{'id': 'DEV-C04.' + r, 'object': {'ref': r}} for r in refs]}
        rows = [{'id': 'DEV-C04.' + r, 'review_result': 'NA_OUTSIDE_STAGE',
                 'handoff': {'required': True, 'receivers': ['热设计'], 'constraint': 'C503–C505热点≤105°C',
                             'verification': '测量%s本体热点' % r}} for r in refs[:3]]
        rows.append({'id': 'DEV-C04.C201', 'review_result': 'NA_OUTSIDE_STAGE',
                     'handoff': {'required': True, 'receivers': ['热设计'], 'constraint': 'C201热点≤75°C',
                                 'verification': '测量C201本体热点'}})
        text = render(plan, {'checks': rows}, {'valid': True, 'release': 'NO_GO', 'blockers': []})
        table = [l for l in text.split('## 交给后续环节的要求')[1].splitlines() if l.startswith('| 热设计')]
        self.assertEqual(len(table), 2)
        self.assertIn('| 热设计 | DEV-C04.C503、DEV-C04.C504、DEV-C04.C505 | C503、C504、C505 | C503–C505热点≤105°C | '
                      '测量每只本体热点 |', table)
        self.assertIn('| 热设计 | DEV-C04.C201 | C201 | C201热点≤75°C | 测量C201本体热点 |', table)


class OpenDespiteBoundsTest(unittest.TestCase):
    """R5 W-BIAS：engineering.md 已算出“VCCmin10.2375V>U402停机9.5V”，检查仍等“全温小电流保证”；
    W-APP：设计没定的配置写成“向Richtek索取”。"""

    def rows(self, rationale, cause='EXTERNAL_DATA', acquisition='已读p6；向onsemi取得下界'):
        report = {'checks': [{'id': 'PWR-C01.VCC', 'review_result': 'INSUFFICIENT', 'gap_cause': cause,
                              'rationale': rationale, 'input_requests': {'k': {'acquisition': acquisition}}}]}
        return {c['code']: c for c in open_despite_bounds(report, {'PWR-C01.VCC': {'object': {'net': 'VCC'}}})}

    def test_a_computed_margin_left_open_is_named(self):
        hit = self.rows('VGS2.74、VF0.6的条件给VCCmin10.2375V>U402停机9.5V；全温保证未取得')
        self.assertEqual(hit['MARGIN_COMPUTED_BUT_OPEN']['margins'], ['10.2375V>U402停机9.5V'])

    def test_conditions_negations_and_page_numbers_are_not_margins(self):
        for text in ('V5原表6V<VDD保证不覆盖本机4.75V', '已读p11 V5保证仅在VDD>6V', '4.41V、GPIO低电平≤0.4V',
                     '10mA时0.31V，100mA时0.40V'):
            self.assertNotIn('MARGIN_COMPUTED_BUT_OPEN', self.rows(text), text)

    def test_cited_evidence_sentences_about_the_part_count(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / 'evidence').mkdir()
            (Path(root) / 'evidence' / 'engineering.md').write_text(
                '## BIAS\n辅助−10%时VCC最低10.24V>停机9.5V。U201另核13.3V>11.25V。\n## OTHER\nVCC 1V>0.5V\n', encoding='utf-8')
            report = {'checks': [{'id': 'PWR-C01.VCC', 'review_result': 'INSUFFICIENT', 'gap_cause': 'EXTERNAL_DATA',
                                  'rationale': '资料不足', 'evidence': [{'source': 'evidence/engineering.md', 'locator': '## BIAS'}]}]}
            hit = [c for c in open_despite_bounds(report, {'PWR-C01.VCC': {'object': {'net': 'VCC'}}}, root)
                   if c['code'] == 'MARGIN_COMPUTED_BUT_OPEN']
        self.assertEqual(hit[0]['margins'], ['10.24V>停机9.5V'])

    def test_design_value_asked_of_a_vendor(self):
        self.assertIn('DESIGN_VALUE_ASKED_OF_VENDOR', self.rows('配置未定', 'DESIGN_OPEN', '已读p35；向Richtek索取寄存器'))
        self.assertNotIn('DESIGN_VALUE_ASKED_OF_VENDOR', self.rows('配置未定', 'DESIGN_OPEN', '由设计者确定补偿码'))


if __name__ == '__main__':
    unittest.main()

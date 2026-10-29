"""5.1 渲染报告 strict audit (2026-10-26, user: 5.1 的 A–G 全部执行): the report shows the reader's quantities and
nothing twice. Measured on the four R7 reports: a 2419-character 余量或依据 cell, one margin said three times, 每只、每只
in merged handoffs, 图：现状。现状：…, 第p5 05_Bias_Control页, 11 check ids on one finding, 180-character work-item
titles, a 1486-character 影响哪些判断 line, a summary restating the check counts, 500 characters of template reasons
under 未问.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import render_report as rr
from review_quality import screen_quality


class FunctionTableTests(unittest.TestCase):
    def test_each_aspect_shows_its_decisive_margin_once(self):
        calc = {'margin': [
            {'aspect': 'A', 'value': 136, 'unit': 'Vac', 'against': 'CY301 Y1 400 Vac'},
            {'aspect': 'A', 'value': 136, 'unit': 'Vac', 'against': 'CY301 Y1 400 Vac（应力）'},
            {'aspect': 'B', 'value': 136, 'unit': 'Vac', 'against': 'CY301 Y1 400 Vac（用途）'},
            {'aspect': 'C', 'value': 57.3, 'unit': 'V', 'against': 'U202 VIORM'},
            {'aspect': 'C', 'value': 446, 'unit': 'V', 'against': 'U202 VIORM 890 Vpeak'}]}
        self.assertEqual(rr.decisive_margins(calc), ['余量 136 Vac 对 CY301 Y1 400 Vac', '余量 57.3 V 对 U202 VIORM'])
        # the function table shows the first and counts the rest (user 2026-10-27: 报告太冗长)
        self.assertEqual(rr.function_basis({'calculation': calc}), '余量 136 Vac 对 CY301 Y1 400 Vac（另 1 项见台账）')

    def test_a_passing_function_shows_its_tightest_margin_over_its_limit(self):
        # R8 (2026-10-28): 余量 0.125 W 对 R602 (101 pW of 0.125 W) stood for a function whose sensor threshold had 6 %
        fn = {'conditions': [{'id': 'c-p', 'limit': {'max': 0.125, 'unit': 'W'}},
                             {'id': 'c-v', 'limit': {'max': 1.47, 'unit': 'V'}},
                             {'id': 'c-i', 'limit': {'min': 48.9, 'unit': 'µA'}}],
              'calculation': {'margin': [
                  {'aspect': 'A', 'value': 0.125, 'unit': 'W', 'against': 'R602 0.125 W', 'basis': {'limit': 'c-p'}},
                  {'aspect': 'B', 'value': 0.0886, 'unit': 'V', 'against': 'NTC 开短路判别', 'basis': {'limit': 'c-v'}},
                  {'aspect': 'C', 'value': 0.000378, 'unit': 'A', 'against': 'U202 所需电流', 'basis': {'limit': 'c-i'}},
                  {'aspect': 'D', 'value': 3, 'unit': 'h', 'against': '没有数值限值'}]}}
        self.assertEqual(rr.decisive_margins(fn['calculation'], fn),
                         ['余量 0.0886 V 对 NTC 开短路判别', '余量 0.125 W 对 R602 0.125 W', '余量 378 µA 对 U202 所需电流',
                          '余量 3 h 对 没有数值限值'])
        self.assertEqual(rr.function_basis(fn, 'PASS'), '余量 0.0886 V 对 NTC 开短路判别（另 3 项见台账）')

    def test_a_pass_without_a_margin_shows_its_judgement_not_why_nothing_was_computed(self):
        fn = {'no_calculation_reason': '本功能的数值推导已在独立计算记录逐条给出，不另造一份数值副本。',
              'judgements': [{'aspect': '地网', 'says': 'PGND 是一次参考；SEC_RTN 经 R503 接 SGND。本方面的实际对象为…'},
                             {'aspect': '回流', 'says': 'Y1 不是直流共地'}]}
        self.assertEqual(rr.function_basis(fn, 'PASS'), 'PGND 是一次参考；SEC_RTN 经 R503 接 SGND（另 1 项见台账）')

    def test_small_quantities_take_their_prefix_and_a_trailing_clause_is_the_same_comparison(self):
        # R8: 2e-07 s, 2.1e-06 F in the table; Q501 120 V printed twice, once with "；非线性热SOA另见…"
        self.assertEqual([rr._quantity(v, u) for v, u in ((2e-07, 's'), (2.1e-06, 'F'), (0.001212, 'A'), (0.05, 'A'),
                                                           (0, 'V'), (21.06, 'V'), (0.0005, 'mA'), (400, 'h'))],
                         ['200 ns', '2.1 µF', '1.212 mA', '0.05 A', '0 V', '21.06 V', '0.0005 mA', '400 h'])
        calc = {'margin': [
            {'aspect': 'A', 'value': 20, 'unit': 'V', 'against': 'Q501 120 V 额定对 PCB 峰值 ≤100 V'},
            {'aspect': 'B', 'value': 20, 'unit': 'V', 'against': 'Q501 120 V 额定对 PCB 峰值 ≤100 V；非线性热 SOA 另见后续要求'},
            {'aspect': 'C', 'value': 2e-07, 'unit': 's', 'against': '偏置切换等待 2 ms 减 5τ'}]}
        self.assertEqual(rr.decisive_margins(calc),
                         ['余量 20 V 对 Q501 120 V 额定对 PCB 峰值 ≤100 V', '余量 200 ns 对 偏置切换等待 2 ms 减 5τ'])

    def test_a_range_two_requirements_state_is_one_entry(self):
        import requirement_parameters as rp
        windows = [{'min': 90, 'max': 264, 'unit': 'V', 'requirement': 'E-IN-01'},
                   {'min': 100, 'max': 240, 'unit': 'V', 'requirement': 'E-IN-01'},
                   {'min': 90, 'max': 264, 'unit': 'V', 'requirement': 'REQ-IN-001'},
                   {'min': 100, 'max': 240, 'unit': 'V', 'requirement': 'REQ-IN-001'}]
        self.assertEqual(rp.texts(windows), ['90–264 V（E-IN-01、REQ-IN-001）', '100–240 V（E-IN-01、REQ-IN-001）'])

    def test_a_failing_function_whose_result_says_it_holds_is_hinted(self):
        plan = {'checks': [{'id': 'A.1', 'rule': 'A'}]}
        def hints(result):
            report = {'checks': [{'id': 'A.1', 'review_result': 'PASS', 'rationale': 'ok'}],
                      'functions': [{'id': 'FN-J101', 'fails': [{'key': 'BOM-RV101'}], 'calculation': {'result': result}}]}
            return [c for c in screen_quality(plan, report)['candidates'] if c['code'] == 'FAILING_RESULT_SAYS_HOLDS']
        self.assertEqual(len(hints('数值比较按已知器件额定、实际网络成立。')), 1)
        self.assertEqual(hints('RV101 的 BOM 规格与订货码矛盾；其余额定比较成立。'), [])
        self.assertEqual(hints('漏极取样分压不能保证高线模式。'), [])

    def test_a_long_result_shows_its_first_sentence_and_points_at_the_ledger(self):
        long = '正常同步整流关断反压为 Vbulk/8 + VRAW，最高 78 V。' + '然后' * 200
        basis = rr.function_basis({'calculation': {'result': long}})
        self.assertEqual(basis, '正常同步整流关断反压为 Vbulk/8 + VRAW，最高 78 V。（其余见台账）')
        short = '余量 2 V 对 U1 VCC 绝限'
        self.assertEqual(rr.function_basis({'calculation': {'result': short}}), short)

    def test_a_long_designator_list_in_the_question_is_a_count(self):
        refs = '、'.join('C%d' % i for i in range(301, 313))
        q = 'POWER_CONVERTER-U402（%s）在 run 下输出是否落在窗口内（电路连接网络上已声明的轨：BULK 0–447.5 V）' % refs
        self.assertEqual(rr.short_question(q), 'POWER_CONVERTER-U402（12 个器件）在 run 下输出是否落在窗口内（电路连接网络上已声明的轨：BULK 0–447.5 V）')
        self.assertEqual(rr.short_question('X（C1、C2、R1）'), 'X（C1、C2、R1）')

    def test_the_not_asked_lines_list_the_aspects_only(self):
        plan = {'functions': [{'id': 'FN-A', 'not_asked': [
            {'aspect': '功率管 SOA 与降额', 'why': '电路里没有 MOSFET 或 BJT'},
            {'aspect': '防反接与理想二极管', 'why': '电路里没有 D、S 都不接地的 MOSFET'},
            {'aspect': '功率管 SOA 与降额', 'why': '重复'}]}]}
        lines = rr.not_asked_lines(plan)
        self.assertIn('- FN-A 未问：功率管 SOA 与降额、防反接与理想二极管', lines)
        self.assertFalse(any('没有 MOSFET' in l for l in lines))
        self.assertTrue(lines[0].endswith('（理由见计划；漏问的经 intent.rule_gaps 补回）：'))


def handoff_row(cid, ref, constraint, verification):
    return ({'id': cid, 'review_result': 'NA_OUTSIDE_STAGE', 'handoff': {
                'required': True, 'receivers': ['热设计'], 'constraint': constraint, 'verification': verification}},
            {'id': cid, 'object': {'ref': ref}})


class HandoffTableTests(unittest.TestCase):
    def render(self, rows):
        checks, planned = zip(*rows)
        return rr.render({'checks': list(planned)}, {'checks': list(checks)},
                         {'valid': True, 'release': 'GO', 'blockers': []}).split('<summary>交给后续环节的要求</summary>')[1]

    def test_requirements_differing_only_by_one_part_merge_into_a_每只_row(self):
        text = self.render([handoff_row('PWR-C05.X.C1', 'C1', 'C1 热点 ≤ 75 °C', '闭壳热测 C1 壳温'),
                            handoff_row('PWR-C05.X.C2', 'C2', 'C2 热点 ≤ 75 °C', '闭壳热测 C2 壳温')])
        self.assertIn('#### 热设计（1 条）', text)
        self.assertIn('| C1、C2 | 每只 热点 ≤ 75 °C | 闭壳热测 每只 壳温 |', text)

    def test_a_requirement_naming_several_parts_keeps_its_own_row(self):
        text = self.render([handoff_row('PWR-C05.X.C1', 'C1', 'C1、Q1、R1 在 90 Vac 100 W 时温度在降额内；C1/Q1 热点 ≤ 75 °C', '闭壳满载热测'),
                            handoff_row('PWR-C05.X.C2', 'C2', 'C2、Q1、R1 在 90 Vac 100 W 时温度在降额内；C2/Q1 热点 ≤ 75 °C', '闭壳满载热测')])
        self.assertNotIn('每只、每只', text)
        self.assertNotIn('每只/每只', text)
        self.assertIn('C1、Q1、R1 在 90 Vac 100 W', text)
        self.assertIn('C2、Q1、R1 在 90 Vac 100 W', text)


class FindingTests(unittest.TestCase):
    def test_a_caption_that_names_its_kind_is_not_prefixed_again(self):
        lines = rr.render_figures([{'kind': 'ACTUAL', 'source': 'f/a.png', 'caption': '现状：U402 FB 只由 U404 下拉'},
                                   {'kind': 'AFTER', 'source': 'f/b.svg', 'caption': 'VRAW 经 D406 驱动 U405'}])
        self.assertIn('图：现状：U402 FB 只由 U404 下拉', lines)
        self.assertIn('图：改后。VRAW 经 D406 驱动 U405', lines)
        self.assertFalse(any('现状。现状' in l for l in lines))

    def test_a_named_page_is_printed_as_written_and_a_number_as_第n页(self):
        self.assertEqual(rr.page_word(5), '第5页')
        self.assertEqual(rr.page_word('5'), '第5页')
        self.assertEqual(rr.page_word('p5 05_Bias_Control'), 'p5 05_Bias_Control')

    def test_more_than_six_items_are_listed_as_six_and_a_count(self):
        self.assertEqual(rr.listed(['a', 'b'], '条检查'), 'a、b')
        self.assertEqual(rr.listed([str(i) for i in range(11)], '条检查'), '0、1、2、3、4、5等 11 条检查')


class WorkItemTests(unittest.TestCase):
    def test_blocks_name_each_conclusion_once_and_fold_past_six(self):
        # R8: three blocked conclusions explained in 900 characters; the card names them, the ledger explains
        blocks = ['方面%d（run），经 BOM.csv T301：缺 %d' % (i, i) for i in range(8)]
        self.assertEqual(rr.fold_blocks(blocks), ['方面0（run）、方面1（run）、方面2（run）、方面3（run）、方面4（run）、'
                                                  '方面5（run）等 8 项'])
        self.assertEqual(rr.fold_blocks(['变换器电压裕量（run）：缺 a', '变换器电压裕量（run）：缺 b', '时序（fault）']),
                         ['变换器电压裕量（run）、时序（fault）'])
        self.assertEqual(rr.fold_blocks([]), [])

    def test_a_long_title_is_hinted_and_a_short_one_is_not(self):
        plan = {'checks': [{'id': 'A.1', 'rule': 'A'}]}
        long_title = 'T301 初次级加强绝缘结构与资格未承认（BOM 原文“加强绝缘及整体资格未承认”），无绕组结构、挡墙/三层绝缘线、耐压与认证资料；其余跨隔离件已核'
        report = {'checks': [{'id': 'A.1', 'review_result': 'PASS', 'rationale': 'ok'}],
                  'work_items': [{'id': 'W-LONG', 'title': long_title, 'check_ids': ['A.1']},
                                 {'id': 'W-OK', 'title': 'T301 加强绝缘结构与资格缺图纸', 'check_ids': ['A.1']}]}
        hints = [c for c in screen_quality(plan, report)['candidates'] if c['code'] == 'TASK_TITLE_LONG']
        self.assertEqual([(h['task_id'], h['length'] > 60) for h in hints], [('W-LONG', True)])


class SummaryTests(unittest.TestCase):
    def test_a_summary_restating_the_check_counts_is_refused(self):
        bad = {'summary': 'R6 板 515 项检查中 438 项通过、6 项不通过、42 项资料不够判定、29 项不适用。唯一确认缺陷是 USB-C 口 ESD。'}
        [err] = rr.notes_errors(bad)
        self.assertIn('check counts', err)
        good = {'summary': '最要紧的两处：反馈断开后 VRAW 冲到 38 V；USB 口 ESD 残压超过 6.5 V。其余待办主要是定制件图纸。'}
        self.assertEqual(rr.notes_errors(good), [])


if __name__ == '__main__':
    unittest.main()

"""The delivery is one generated report plus a small record; numbers come only from the ledger."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from test_review_stage_scope import decisive, downstream
from test_validate_review import fixture, fail
from gap_fixture import complete_gaps
import validate_review as vr
from validate_review import validate_review
from render_report import render
from pack_review import pack, REPORT, RECORD, LEDGER

INTERNAL_CODES = ('EXTERNAL_DATA', 'DESIGN_OPEN', 'REQUIREMENT_OPEN', 'REVIEW_INCOMPLETE',
                  'NA_OUTSIDE_STAGE', 'documented', 'gap_cause')


def report(p, r, db, notes=None):
    gate = json.loads(json.dumps(validate_review(p, r, db), default=sorted))
    return render(p, r, gate, notes), gate


def body(text):
    """Report text above the count table, where readers look first."""
    return text.split('## 数字一览')[0]


class RenderReportTests(unittest.TestCase):
    def test_conclusion_and_gate_come_first_and_gap_task_is_actionable(self):
        p, r, db = decisive()
        text, gate = report(p, r, db)
        self.assertTrue(gate['valid'], gate['errors'])
        lines = [l for l in text.splitlines() if l.strip()]
        self.assertEqual(lines[1], '## 结论')
        self.assertEqual(lines[2], '- **发现的错误**：0 处。')
        self.assertIn('仍待确认**：1 件事项', lines[3])
        self.assertNotIn('**检查结果**', body(text))
        self.assertTrue(lines[4].startswith('- **能否定稿**：还不能定稿。还差：'))
        self.assertIn('1 件待办阻塞定稿（同一原因合并，涉及 1 条缺资料或设计依据的阻塞检查；不阻塞的待办不计在内）', lines[5])
        section = text.split('## 待办')[1]
        self.assertIn('W-1', section)
        self.assertIn('类型：缺资料　可能后果：必需功能可能不达标（P1）　涉及 1 条检查', section)
        for phrase in ('Recompute current-limit margin', 'System engineer derives', 'Peak amperes'):
            self.assertIn(phrase, section)

    def test_counts_are_at_the_end_with_plain_labels(self):
        p, r, db = decisive()
        text, _ = report(p, r, db)
        self.assertLess(text.index('## 待办'), text.index('## 数字一览'))
        self.assertIn('| 资料不足的原因：缺资料 / 设计没定 / 需求没定 / 审查没做完 / 已暂缓 | 1 / 0 / 0 / 0 / 0 |', text)
        for jargon in ('冻结', '闸门', '移交', '接收方', '证据不足'):
            self.assertNotIn(jargon, text)
        for code in INTERNAL_CODES:
            self.assertNotIn(code, text)

    def test_one_todo_list_ordered_by_potential_consequence(self):
        rows = [{'id': 'C%d' % i, 'review_result': 'INSUFFICIENT', 'gap_cause': 'EXTERNAL_DATA',
                 'potential_severity': sev} for i, sev in enumerate(('P2', 'P0', 'P1'))]
        tasks = [{'id': 'W-%d' % i, 'title': 'task %d' % i, 'check_ids': ['C%d' % i]} for i in range(3)]
        gate = {'valid': True, 'release': 'NO_GO', 'blockers': [],
                'workflow': {'work_items': tasks, 'current_work_items': ['W-0']}}
        text = render({}, {'checks': rows}, gate)
        self.assertNotIn('现在先做', text)
        self.assertNotIn('定稿前还要做', text)
        self.assertIn('- **待办**：3 件', text)
        section = text.split('## 待办')[1]
        self.assertLess(section.index('W-1'), section.index('W-2'))
        self.assertLess(section.index('W-2'), section.index('W-0'))

    def test_notes_add_plain_text_but_not_numbers(self):
        p, r, db = decisive()
        notes = {'summary': '先确认启动电流。', 'items': {'W-1': '电源启动时可能被限流卡住。'},
                 'highlights': ['第 %d 条' % i for i in range(12)]}
        text, _ = report(p, r, db, notes)
        plain, _ = report(p, r, db)
        self.assertIn('先确认启动电流。', text)
        self.assertIn('电源启动时可能被限流卡住。', text)
        self.assertIn('第 7 条', text)
        self.assertNotIn('第 8 条', text)  # highlights are capped
        self.assertEqual(text.split('## 数字一览')[1], plain.split('## 数字一览')[1])

    def test_mixed_level_item_shows_its_breakdown_and_note_is_a_bullet(self):
        from render_report import render_item
        checks = {'A.1': {'id': 'A.1', 'review_result': 'INSUFFICIENT', 'gap_cause': 'EXTERNAL_DATA',
                          'potential_severity': 'P0'},
                  'A.2': {'id': 'A.2', 'review_result': 'INSUFFICIENT', 'gap_cause': 'EXTERNAL_DATA',
                          'potential_severity': 'P1'}}
        task = {'id': 'W-1', 'title': 't', 'root_cause': 'x', 'check_ids': ['A.1', 'A.2'], 'next_action': 'y'}
        lines = render_item(task, checks, {'W-1': '审查员的话。'})
        self.assertIn('涉及 2 条检查（P0 1、P1 1）', lines[2])
        self.assertIn('- **审查员补充**：审查员的话。', lines)
        self.assertNotIn('审查员的话。', lines)   # not a floating paragraph
        checks['A.2']['potential_severity'] = 'P0'
        self.assertIn('涉及 2 条检查\n', render_item(task, checks, {})[2] + '\n')

    def test_plain_language_scan_stops_before_sr_feedback_even_without_tool_gaps(self):
        from pack_review import plain_language_errors
        report = ('# t\n\n## 结论\n\n- ok\n\n## 对 SR 技能的反馈（设计者不用处理）\n\n'
                  '1. **DEV-E01**：技能误报。\n\n## 数字一览\n\n| 项目 | 数量 |\n')
        self.assertEqual([], plain_language_errors(report))
        self.assertTrue(plain_language_errors(report.replace('- ok', '- 技能 ok')))

    def test_item_drops_scope_and_action_that_only_echo_the_task(self):
        from render_report import render_item
        req = {'why_decisive': 'x', 'required_scope': 'F101 分断；100A 与故障电流尚未配对',
               'acquisition': '已读 Littelfuse p1。 核 GB4943.1 条款再确认 F101', 'closure_criterion': 'c'}
        checks = {'A.1': {'id': 'A.1', 'review_result': 'INSUFFICIENT', 'gap_cause': 'EXTERNAL_DATA',
                          'potential_severity': 'P0', 'input_requests': {'k': req}}}
        task = {'id': 'W-1', 'title': 'F101 分断', 'root_cause': '100A 与故障电流尚未配对',
                'check_ids': ['A.1'], 'next_action': '核 GB4943.1 条款再确认 F101'}
        text = '\n'.join(render_item(task, checks, {}))
        self.assertNotIn('适用范围', text)
        self.assertEqual(1, text.count('核 GB4943.1 条款再确认 F101'))
        req['required_scope'] = '90–264Vac、冷/热重插'
        self.assertIn('适用范围：90–264Vac、冷/热重插', '\n'.join(render_item(task, checks, {})))

    def test_notes_about_sr_itself_are_refused_outside_sr_feedback(self):
        from render_report import notes_errors
        self.assertEqual([], notes_errors({'summary': '先核 F101。', 'items': {'W-1': '补磁件资料。'}}))
        self.assertTrue(notes_errors({'summary': 'SR改进部分有效，真实BR101误报仍未解决。'}))
        self.assertTrue(notes_errors({'highlights': ['质量提示仍有 17 条']}))

    def test_stage_na_is_handed_over_without_blocking(self):
        p, r, db = downstream()
        text, gate = report(p, r, db)
        self.assertEqual(gate['release'], 'GO')
        self.assertIn('- **能否定稿**：可以定稿', text)
        section = text.split('## 交给后续环节的要求')[1]
        self.assertIn('| Synthetic test engineer | RST-E01.C1 | 整板 |', section)
        self.assertIn('不影响原理图定稿', section)
        self.assertIn('| 与本产品无关（NA） | 0 |', text)
        self.assertIn('| 原理图阶段不判、交给后续环节 | 1 |', text)
        self.assertIn('| 原理图阶段不判、交给后续环节 | 1 |', text)
        self.assertNotIn('NA，', text)
        self.assertNotIn('## 待办', text)

    def tool_gate(self, row_update):
        p, r, db = fixture()
        key = r['checks'][0]['id']
        r['checks'][0].update(row_update)
        real = vr.validate_inventories

        def gated(*args):
            gates = real(*args)
            gates.setdefault(key, []).append(key + ': synthetic tool gap before PASS')
            return gates
        with mock.patch.object(vr, 'validate_inventories', gated):
            return key, report(p, r, db)

    def test_tool_gap_still_blocks_pass_without_manual_verification(self):
        key, (_, gate) = self.tool_gate({})
        self.assertFalse(gate['valid'])
        self.assertIn(key + ': synthetic tool gap before PASS (or record manual_verification with an independent evidenced review)',
                      gate['errors'])

    def test_manual_verification_keeps_pass_and_lists_tool_gap_apart(self):
        manual = {'tool_limitation': 'Kelvin source pins not mapped', 'method': 'Traced pins on the vendor drawing',
                  'sr_improvement': 'Accept S1_KELVIN/S2_POWER as source aliases backed by the pin map',
                  'evidence': [{'source': 'synthetic-fixture.json', 'locator': 'Q1'}]}
        key, (text, gate) = self.tool_gate({'manual_verification': manual})
        self.assertTrue(gate['valid'], gate['errors'])
        self.assertEqual(gate['release'], 'GO')
        self.assertEqual(gate['sr_improvements'][0]['check_id'], key)
        section = text.split('## 审查工具的不足（设计者不用处理）')[1]
        for phrase in ('**SR 为什么做不到**：Kelvin source pins not mapped',
                       '**建议怎么改进 SR**：Accept S1_KELVIN/S2_POWER',
                       '**这次怎么核对的**：Traced pins on the vendor drawing'):
            self.assertIn(phrase, section)
        self.assertNotIn('## 待办', text)

    def test_manual_verification_needs_a_tool_gap_and_evidence(self):
        p, r, db = fixture()
        r['checks'][0]['manual_verification'] = {'tool_limitation': 'x', 'method': 'y', 'evidence': []}
        _, gate = report(p, r, db)
        key = r['checks'][0]['id']
        self.assertIn(key + ': manual_verification only applies to a PASS/FAIL that the tool cannot confirm', gate['errors'])
        self.assertIn(key + ': manual_verification needs tool_limitation, sr_improvement, method and evidence', gate['errors'])

    def test_review_actor_is_explicit_and_not_inferred_from_legacy_field_name(self):
        manual = {'tool_limitation': 'Missing grouping', 'method': 'Read the pin table and traced returns',
                  'sr_improvement': 'Save source-bound grouping',
                  'evidence': [{'source': 'synthetic.json', 'locator': 'pin table'}]}
        _, (legacy, _) = self.tool_gate({'manual_verification': manual})
        self.assertNotIn('人员核对：', legacy)
        for kind, label in [('AI', 'AI 核对：'), ('HUMAN', '人员核对：')]:
            _, (text, gate) = self.tool_gate({'manual_verification': dict(manual, reviewer_kind=kind)})
            self.assertTrue(gate['valid'], gate['errors'])
            self.assertEqual(gate['sr_improvements'][0]['reviewer_kind'], kind)
            self.assertIn(label + manual['method'], text)
        _, (_, bad) = self.tool_gate({'manual_verification': dict(manual, reviewer_kind='inferred')})
        self.assertFalse(bad['valid'])

    def test_confirmed_defect_is_listed_with_fix(self):
        p, r, db = fixture()
        fail(r)
        text, _ = report(p, r, db)
        section = body(text).split('## 发现的错误')[1]
        self.assertIn('F1', section)
        self.assertIn('（P1：必需功能可能不达标）', section)
        self.assertIn('**怎么改**', section)
        self.assertIn('- **发现的错误**：电路错误 1 处，文档错误 0 处（P1 1 处）', text)
        self.assertIn('类型：电路错误', section)

    def test_failed_checks_are_named_with_their_problem(self):
        p, r, db = fixture()
        fail(r)
        key = r['checks'][0]['id']
        r['findings'][0]['check_ids'] = [key]
        text, _ = report(p, r, db)
        self.assertIn('### F1', text)
        self.assertIn('| 通过 / 没通过 / 资料不足无法判断 | 6 / 1 / 0 |', text)
        self.assertIn('- **涉及的检查**：%s（没通过）' % key, text)

    def test_invalid_records_are_flagged_before_anything_else(self):
        p, r, db = decisive()
        del r['checks'][0]['input_requests']
        text, gate = report(p, r, db)
        self.assertFalse(gate['valid'])
        self.assertIn('审查记录本身有错', text.splitlines()[2])


class ReportWordingTests(unittest.TestCase):
    """Problems readers hit in the v0.17 report, fixed in the skill rather than by hand."""

    def test_document_only_defect_is_not_called_a_circuit_error(self):
        from render_report import is_document, item_kind
        self.assertTrue(is_document(['DOC-T01.AS-DRAWN', 'DEV-D04.BOARD']))
        self.assertFalse(is_document(['DOC-T01.AS-DRAWN', 'PWR-C01.U1']))
        self.assertEqual(item_kind([{'id': 'DEV-D04.BOARD', 'review_result': 'FAIL'}]), '文档错误')
        p, r, db = fixture()
        fail(r)
        r['findings'][0]['check_ids'] = [r['checks'][0]['id']]
        with mock.patch('render_report.is_document', return_value=True):
            text, _ = report(p, r, db)
        self.assertIn('电路错误 0 处，文档错误 1 处', text)
        self.assertIn('类型：文档错误', text)

    def test_scope_blocker_names_the_check_and_finding(self):
        from render_report import blocker_reasons
        results = {'scope_checks': {'input_consistency': 'DOC-Q01.X'},
                   'checks': [{'id': 'DOC-Q01.X', 'review_result': 'FAIL', 'finding_id': 'F-DOC-01'}]}
        reasons = blocker_reasons(['scope input_consistency: coverage audit not PASS'], results)
        self.assertEqual(reasons, ['输入资料一致性核对没通过（检查 DOC-Q01.X，问题见 F-DOC-01）'])
        self.assertNotIn('其他定稿条件', '；'.join(reasons))

    def test_history_materials_are_stated_in_the_conclusion(self):
        p, r, db = decisive()
        r['history_inputs'] = ['reviews/R1']
        text, gate = report(p, r, db)
        self.assertIn('- **上一版审查材料**：本轮可见 `reviews/R1`', body(text))
        self.assertNotIn('上一版问题未逐条复验', text)
        r['history_inputs'] = []
        self.assertIn('- **上一版审查材料**：本轮没有使用。', body(report(p, r, db)[0]))
        # 100W PD R3 复审：上一版 2 条问题只在旁路文件里对照，报告却显示 0 条处理记录。
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'record').mkdir()
            (Path(tmp) / 'record' / 'review-results.json').write_text(
                json.dumps({'findings': [{'id': 'F-OLD-1'}, {'id': 'F-OLD-2'}]}), encoding='utf-8')
            r['history_inputs'] = [tmp]
            text, gate = report(p, r, db)
        self.assertIn('- **上一版问题未逐条复验**：上一版记录的 2 条问题（F-OLD-1、F-OLD-2）没有历史复验行', body(text))
        self.assertIn('| 上一版问题的处理记录（不计入上面各行） | 0（已声明上一版材料，但没有逐条复验行） |', text)

    def test_gap_blockers_are_counted_by_work_item(self):
        from render_report import blocker_reasons
        blockers = ['A.%d: unresolved blocking INSUFFICIENT' % i for i in range(5)]
        tasks = [{'id': 'W1', 'check_ids': ['A.0', 'A.1', 'A.2']}, {'id': 'W2', 'check_ids': ['A.3', 'A.4']}]
        self.assertEqual(blocker_reasons(blockers, {}, tasks),
                         ['2 件待办阻塞定稿（同一原因合并，涉及 5 条缺资料或设计依据的阻塞检查；不阻塞的待办不计在内）'])
        # A gap no work item owns keeps the per-check wording.
        self.assertEqual(blocker_reasons(blockers, {}, tasks[:1]),
                         ['5 条检查缺资料或设计依据，对应下面列出的待办'])

    def test_handoffs_list_where_they_apply_and_tool_gaps_merge(self):
        p, r, db = downstream()
        key = r['checks'][0]['id']
        next(c for c in p['checks'] if c['id'] == key)['object']['ref'] = 'U7'
        text, _ = report(p, r, db)
        self.assertIn('| 负责方 | 检查 | 涉及位号/网络 | 要落实的要求 | 怎么验证 |', text)
        self.assertIn('| U7 |', text.split('## 交给后续环节的要求')[1])
        from render_report import render
        gate = {'valid': True, 'release': 'GO', 'blockers': [], 'sr_improvements': [
            {'check_id': 'A.1', 'tool_limitation': 'x', 'sr_improvement': 'y', 'method': 'z'},
            {'check_id': 'B.1', 'tool_limitation': 'x', 'sr_improvement': 'y', 'method': 'z'}]}
        merged = render({}, {'checks': []}, gate)
        self.assertIn('### A.1、B.1', merged)
        self.assertEqual(merged.count('**SR 为什么做不到**'), 1)
        self.assertNotIn('人工', merged)

    def test_merged_todo_keeps_every_distinct_request_and_acceptance(self):
        from render_report import render_item
        checks = {'C%d' % i: {'input_requests': {'x': {
            'required_scope': 'scope %d' % i, 'acquisition': 'shared source',
            'closure_criterion': 'limit %d' % i}}} for i in range(6)}
        task = {'id': 'W-X', 'title': 'U1', 'check_ids': list(checks),
                'next_action': 'calculate U1'}
        text = '\n'.join(render_item(task, checks, {}))
        for i in range(6):
            self.assertIn('scope %d' % i, text)
            self.assertIn('limit %d' % i, text)
        self.assertEqual(text.count('shared source'), 1)
        self.assertIn('calculate U1', text)

    def test_duplicate_scope_and_acceptance_are_not_repeated(self):
        from render_report import render_item
        checks = {'C': {'input_requests': {'x': {'required_scope': 'range',
            'closure_criterion': 'limit', 'acquisition': 'vendor curve'}}}}
        task = {'id': 'W', 'check_ids': ['C'], 'reason': '本任务只关闭：range',
                'next_action': 'calculate；limit'}
        text = '\n'.join(render_item(task, checks, {}))
        self.assertEqual(text.count('range'), 1)
        self.assertEqual(text.count('limit'), 1)
        self.assertIn('calculate', text)
        task['reason'] = 'range includes hazardous restart'
        self.assertIn(task['reason'], '\n'.join(render_item(task, checks, {})))

    def test_todo_that_only_fixes_a_listed_problem_points_to_it(self):
        from render_report import covered_by_findings, same_text
        checks = {'A': {'review_result': 'FAIL'}, 'B': {'review_result': 'INSUFFICIENT'}}
        findings = [{'id': 'F-1', 'check_ids': ['A']}]
        self.assertEqual(covered_by_findings({'check_ids': ['A']}, checks, findings), ['F-1'])
        self.assertEqual(covered_by_findings({'check_ids': ['A', 'B']}, checks, findings), [])
        self.assertTrue(same_text('改正13个PWR_FLAG的编号', '改正13个PWR_FLAG的编号'))
        self.assertFalse(same_text('使分段积分与实际限流一致', '修正计算记录'))

    def test_sr_feedback_is_grouped_by_kind_and_malformed_items_are_rejected(self):
        from render_report import render_sr_feedback, sr_feedback_errors, main
        items = [{'kind': 'false_alarm', 'rules': ['SIG-T01'], 'instance': 'CS_P/CS_N 被当成差分对',
                  'suggestion': '按采样对排除'},
                 {'kind': 'unclear', 'rules': ['DRV-E01'], 'instance': '关闭条件与证据尺度矛盾',
                  'suggestion': '改成实际栅压下导通有保证'}]
        text = '\n'.join(render_sr_feedback(items))
        self.assertIn('### 误报', text)
        self.assertIn('### 说明不清或互相矛盾', text)
        self.assertIn('**SIG-T01**', text)
        self.assertEqual(sr_feedback_errors(items), [])
        self.assertTrue(sr_feedback_errors([{'kind': 'other', 'rules': ['X'], 'instance': 'a', 'suggestion': 'b'}]))
        self.assertTrue(sr_feedback_errors([{'kind': 'missed', 'rules': [], 'instance': 'a', 'suggestion': 'b'}]))
        with tempfile.TemporaryDirectory() as tmp:
            notes = Path(tmp) / 'notes.json'
            notes.write_text(json.dumps({'sr_feedback': [{'kind': 'missed'}]}), encoding='utf-8')
            for name in ('plan', 'results', 'gate'):
                (Path(tmp) / name).write_text('{}', encoding='utf-8')
            with contextlib.redirect_stderr(io.StringIO()):
                code = main([str(Path(tmp) / 'plan'), str(Path(tmp) / 'results'), str(Path(tmp) / 'gate'),
                             '--notes', str(notes), '-o', str(Path(tmp) / 'out.md')])
            self.assertEqual(code, 2)

    def test_jargon_is_detected_only_as_whole_ascii_words(self):
        from render_report import jargon_in
        self.assertEqual(jargon_in('按remediation同步fit清单，交下游'), ['下游', 'remediation', 'fit'])
        self.assertEqual(jargon_in('Q201 栅极经 R203 到 PFC_GATE，fitted 状态'), [])

    def test_root_gap_count_not_check_count_and_details_preserve_evidence(self):
        from test_check_explanations import synthetic
        p, r = synthetic(['FAIL', 'INSUFFICIENT'])
        gap = next(c for c in r['checks'] if c['review_result'] == 'INSUFFICIENT')
        gap['potential_severity'] = 'P0'
        task = {'id': 'W1', 'title': 'single cause', 'check_ids': [gap['id']]}
        text = render(p, r, {'valid': True, 'workflow': {'work_items': [task]}},
                      {'sr_feedback': [{'kind': 'software_bug', 'rules': ['DOC-Q01'],
                                        'instance': 'path error', 'suggestion': 'verify archive'}]}, detail='full')
        self.assertIn('仍待确认**：1 件事项，其中 1 件', text)
        self.assertIn('<summary>展开逐项依据与通过标准（完整保留）</summary>', text)
        self.assertIn('本次结论依据', text)
        self.assertEqual(text.count('<details>'), text.count('</details>'))
        self.assertIn('已复现的程序错误', text)


class PackReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.work, self.out = self.tmp / 'work', self.tmp / 'review'
        self.work.mkdir(); self.out.mkdir()
        p, r, db = decisive()
        complete_gaps(r)
        r['checks'][0]['evidence'] = [{'source': 'calc/startup.md', 'locator': 'section 1'},
                                      {'source': 'spec.md', 'locator': 'REQ-1'}]
        gate = json.loads(json.dumps(validate_review(p, r, db), default=sorted))
        (self.work / 'calc').mkdir()
        (self.work / 'calc' / 'startup.md').write_text('startup current bound')
        (self.work / 'synthetic-fixture.json').write_text('{}')  # cited by the fixture's other rows
        (self.work / 'debug.log').write_text('not delivered')
        self.inputs = self.tmp / 'inputs'; self.inputs.mkdir()
        (self.inputs / 'spec.md').write_text('requirement')
        data = {'review-plan.json': p, 'review-results.json': r, 'review-gate.json': gate, 'db.json': db,
                'intent.json': {}, 'lint-cold.json': {}, 'lint-hot.json': {}}
        self.ledger = {}
        for name, value in data.items():
            (self.work / name).write_text(json.dumps(value))
            self.ledger[name] = str(self.work / name)
        (self.out / REPORT).write_text('# report')

    def run_pack(self):
        return pack(self.out, self.ledger, str(self.work), {'requirements': str(self.inputs)})

    def cite(self, source):
        path = self.work / 'review-results.json'
        data = json.loads(path.read_text())
        data['checks'][0]['evidence'].append({'source': str(source), 'locator': 'test'})
        path.write_text(json.dumps(data))

    def test_absolute_declared_input_is_not_a_packed_member(self):
        self.cite(self.inputs / 'spec.md')
        errors, manifest = self.run_pack()
        self.assertEqual(errors, [])
        self.assertFalse(any('spec.md' in k for k in manifest['packed']))
        from pack_review import packed_errors
        self.assertEqual(packed_errors(self.out, manifest['packed']), [])

    def test_absolute_undeclared_input_cannot_hide_inside_input_directory(self):
        self.cite(self.work / 'debug.log')
        errors, _ = self.run_pack()
        self.assertTrue(any('debug.log' in e for e in errors), errors)

    def test_parent_traversal_and_source_symlink_are_rejected(self):
        self.cite('../inputs/spec.md')
        (self.work / 'escape.md').symlink_to(self.inputs / 'spec.md')
        self.cite('escape.md')
        errors, _ = self.run_pack()
        self.assertTrue(any('unsafe evidence path' in e for e in errors), errors)
        self.assertTrue(any('escapes work directory' in e for e in errors), errors)

    def test_target_symlink_does_not_overwrite_original(self):
        target = self.out / RECORD / 'evidence' / 'calc'
        target.mkdir(parents=True)
        (target / 'startup.md').symlink_to(self.inputs / 'spec.md')
        errors, _ = self.run_pack()
        self.assertTrue(any('escapes archive' in e for e in errors), errors)
        self.assertEqual((self.inputs / 'spec.md').read_text(), 'requirement')

    def test_manifest_verifier_rejects_missing_tampered_and_escaping_entries(self):
        from pack_review import packed_errors
        _, manifest = self.run_pack()
        p = self.out / RECORD / 'evidence' / 'calc' / 'startup.md'
        p.write_text('tampered')
        self.assertTrue(any('hash mismatch' in e for e in packed_errors(self.out, manifest['packed'])))
        p.unlink()
        self.assertTrue(any('file missing' in e for e in packed_errors(self.out, manifest['packed'])))
        self.assertTrue(packed_errors(self.out, {'../inputs/spec.md': 'unused'}))

    def test_record_holds_ledger_and_cited_evidence_only(self):
        errors, manifest = self.run_pack()
        self.assertEqual(errors, [])
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), sorted([REPORT, RECORD]))
        packed = {Path(k).relative_to(RECORD).as_posix() for k in manifest['packed']}
        self.assertEqual(packed, set(LEDGER) | {'evidence/calc/startup.md', 'evidence/synthetic-fixture.json'})
        self.assertFalse((self.out / RECORD / 'evidence' / 'debug.log').exists())
        self.assertEqual(manifest['inputs']['requirements']['kind'], 'directory')
        self.assertEqual(len(manifest['inputs']['requirements']['tree_sha256']), 64)

    def test_unfinished_review_cannot_be_packed(self):
        results = json.loads((self.work / 'review-results.json').read_text())
        row = results['checks'][0]
        row['gap_cause'] = 'REVIEW_INCOMPLETE'
        row.pop('input_requests', None)
        (self.work / 'review-results.json').write_text(json.dumps(results))
        errors, _ = self.run_pack()
        self.assertTrue(any('review not finished' in e and row['id'] in e for e in errors), errors)

    def test_jargon_in_report_body_fails_the_pack(self):
        (self.out / REPORT).write_text('# r\n\n## 结论\n\n- 还不能冻结，见本行。\n\n## 审查工具的不足（设计者不用处理）\n\n- 原生映射\n')
        errors, _ = self.run_pack()
        hits = [e for e in errors if 'plain words' in e]
        self.assertEqual(len(hits), 1, errors)
        self.assertIn('冻结/本行', hits[0])

    def test_packed_review_can_be_repacked_in_place(self):
        errors, _ = self.run_pack()
        self.assertEqual(errors, [])
        record = self.out / RECORD
        ledger = {name: str(record / name) for name in LEDGER}
        errors, manifest = pack(self.out, ledger, str(record / 'evidence'), {'requirements': str(self.inputs)})
        self.assertEqual(errors, [])
        self.assertIn(RECORD + '/evidence/calc/startup.md', manifest['packed'])

    def test_same_named_file_in_an_input_does_not_hide_new_evidence(self):
        # 100W PD 复审：旧审查目录作输入时，同名的本轮 page-1.png 被当成输入而漏装。
        results = json.loads((self.work / 'review-results.json').read_text())
        results['checks'][0]['evidence'].append({'source': 'page-1.png', 'locator': 'U601'})
        results['checks'][0]['evidence'].append({'source': 'shots/page-2.png', 'locator': 'Q401'})
        (self.work / 'review-results.json').write_text(json.dumps(results))
        (self.work / 'page-1.png').write_bytes(b'new')
        (self.inputs / 'page-1.png').write_bytes(b'old')
        (self.inputs / 'page-2.png').write_bytes(b'old')
        errors, manifest = self.run_pack()
        self.assertIn(RECORD + '/evidence/page-1.png', manifest['packed'])
        self.assertEqual((self.out / RECORD / 'evidence' / 'page-1.png').read_bytes(), b'new')
        self.assertTrue(any('shots/page-2.png' in e for e in errors), errors)

    def test_report_links_must_resolve_after_packing(self):
        (self.out / REPORT).write_text('# report\n\n[算式](record/evidence/calc/startup.md) '
                                       '[图](record/evidence/missing.png) [外链](https://example.com/x)\n')
        errors, _ = self.run_pack()
        self.assertEqual([e for e in errors if 'links to files missing' in e],
                         [REPORT + ' links to files missing from the packed review: record/evidence/missing.png'])

    def test_extra_top_level_files_fail(self):
        (self.out / 'README.md').write_text('extra')
        errors, _ = self.run_pack()
        self.assertTrue(any('README.md' in e for e in errors))

    def test_missing_report_or_cited_evidence_fails(self):
        (self.work / 'calc' / 'startup.md').unlink()
        errors, _ = self.run_pack()
        self.assertTrue(any('calc/startup.md' in e for e in errors))
        (self.out / REPORT).unlink()
        errors, _ = self.run_pack()
        self.assertTrue(any('render_report' in e for e in errors))


if __name__ == '__main__':
    unittest.main()

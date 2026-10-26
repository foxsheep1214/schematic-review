"""The delivery is one generated report plus a small record; numbers come only from the ledger."""
import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from test_review_stage_scope import decisive, downstream
from test_validate_review import fixture, fail
import validate_review as vr
from validate_review import validate_review
from render_report import render
from pack_review import pack, REPORT, REPORT_HTML, RECORD, LEDGER
from report_html import to_html

INTERNAL_CODES = ('EXTERNAL_DATA', 'DESIGN_OPEN', 'DELIVERABLE_PENDING', 'REQUIREMENT_OPEN', 'REVIEW_INCOMPLETE',
                  'NA_OUTSIDE_STAGE', 'documented', 'gap_cause')


def report(p, r, db, notes=None):
    gate = json.loads(json.dumps(validate_review(p, r, db), default=sorted))
    return render(p, r, gate, notes), gate


def write_report(out, text):
    (out / REPORT).write_text(text, encoding='utf-8')
    (out / REPORT_HTML).write_text(to_html(text), encoding='utf-8')


def body(text):
    """Report text the designer reads: without the count table, and stopping at the SR section."""
    text = text.split('\n## 对 SR 的反馈')[0].split('\n## 索引')[0]
    if '## 数字一览' in text:
        head, rest = text.split('## 数字一览', 1)
        text = head + ('## ' + rest.split('\n## ', 1)[1] if '\n## ' in rest else '')
    return text


class RenderReportTests(unittest.TestCase):
    def test_conclusion_and_gate_come_first_and_gap_task_is_actionable(self):
        # The wording is in the golden snapshot (decisive.md); this keeps the order and the named work item.
        p, r, db = decisive()
        text, gate = report(p, r, db)
        self.assertTrue(gate['valid'], gate['errors'])
        lines = [l for l in text.splitlines() if l.strip()]
        self.assertEqual(lines[1], '## 数字一览')   # the numbers first, then the conclusion
        conclusion = text.split('## 结论')[1].split('\n## ')[0]
        self.assertIn('W-1', conclusion)
        self.assertIn('W-1', text.split('## 待办')[1])

    def test_counts_come_first_with_plain_labels(self):
        p, r, db = decisive()
        text, _ = report(p, r, db)
        self.assertLess(text.index('## 数字一览'), text.index('## 结论'))
        self.assertTrue(text.rstrip().split('\n## ')[-1].startswith('索引'))   # the file index closes the report
        for jargon in ('冻结', '闸门', '移交', '接收方', '证据不足'):
            self.assertNotIn(jargon, text)
        for code in INTERNAL_CODES:
            self.assertNotIn(code, text)

    def test_counts_split_the_checks_by_owner_when_the_plan_records_owners(self):
        p, r, db = decisive()
        text, gate = report(p, r, db)
        self.assertNotIn('检查按所属', text)   # a plan without owners shows no owner row
        p.setdefault('summary', {})['owners'] = [{'kind': 'SYSTEM', 'id': 'SYS-POWER', 'rows': 2},
                                  {'kind': 'CIRCUIT', 'id': 'A', 'rows': 5}, {'kind': 'CIRCUIT', 'id': 'B', 'rows': 1},
                                  {'kind': 'BOARD', 'rows': 7}]
        text = render(p, r, gate)
        self.assertIn('| 检查按所属：系统功能 / 功能电路 / 全板与文档 | 2 / 6（2 块电路） / 7 |', text)

    def test_one_todo_list_ordered_by_potential_consequence(self):
        rows = [{'id': 'C%d' % i, 'review_result': 'INSUFFICIENT', 'gap_cause': 'EXTERNAL_DATA',
                 'potential_severity': sev} for i, sev in enumerate(('P2', 'P0', 'P1'))]
        tasks = [{'id': 'W-%d' % i, 'title': 'task %d' % i, 'check_ids': ['C%d' % i]} for i in range(3)]
        gate = {'valid': True, 'release': 'NO_GO', 'blockers': [],
                'workflow': {'work_items': tasks, 'current_work_items': ['W-0']}}
        text = render({}, {'checks': rows}, gate)
        self.assertNotIn('现在先做', text)
        self.assertNotIn('定稿前还要做', text)
        self.assertNotIn('全部 3 件待办', text)   # all three are already in the first-things list
        top = text.split('**最先要解决的')[1].split('## 待办')[0]
        self.assertLess(top.index('W-1'), top.index('W-2'))
        section = text.split('## 待办')[1]
        self.assertLess(section.index('W-1'), section.index('W-2'))
        self.assertLess(section.index('W-2'), section.index('W-0'))

    def test_notes_add_plain_text_but_not_numbers(self):
        p, r, db = decisive()
        notes = {'summary': '先确认启动电流。', 'items': {'W-1': '电源启动时可能被限流卡住。'}}
        text, _ = report(p, r, db, notes)
        plain, _ = report(p, r, db)
        self.assertIn('先确认启动电流。', text)
        self.assertIn('电源启动时可能被限流卡住。', text)
        self.assertNotIn('已核对的重点', text)
        counts = lambda t: t.split('## 数字一览')[1].split('\n## ')[0]
        self.assertEqual(counts(text), counts(plain))

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
        report = ('# t\n\n## 数字一览\n\n| 项目 | 数量 |\n| NA 检查 | 1 |\n\n## 结论\n\n- ok\n\n'
                  '## 对 SR 的反馈（设计者不用处理）\n\n1. **DEV-E01**：技能误报。\n\n## 索引\n\n| a | b.json |\n')
        self.assertEqual([], plain_language_errors(report))
        self.assertTrue(plain_language_errors(report.replace('- ok', '- 技能 ok')))

    def test_item_drops_scope_and_action_that_only_echo_the_task(self):
        from render_report import render_item
        req = {'why_decisive': 'x', 'required_scope': 'F1 分断；100A 与故障电流尚未配对',
               'acquisition': '已读保险丝手册 p1。 核 GB4943.1 条款再确认 F1', 'closure_criterion': 'c'}
        checks = {'A.1': {'id': 'A.1', 'review_result': 'INSUFFICIENT', 'gap_cause': 'EXTERNAL_DATA',
                          'potential_severity': 'P0', 'input_requests': {'k': req}}}
        task = {'id': 'W-1', 'title': 'F1 分断', 'root_cause': '100A 与故障电流尚未配对',
                'check_ids': ['A.1'], 'next_action': '核 GB4943.1 条款再确认 F1'}
        text = '\n'.join(render_item(task, checks, {}))
        self.assertNotIn('适用范围', text)
        self.assertEqual(1, text.count('核 GB4943.1 条款再确认 F1'))
        req['required_scope'] = '90–264Vac、冷/热重插'
        self.assertIn('适用范围：90–264Vac、冷/热重插', '\n'.join(render_item(task, checks, {})))

    def test_notes_about_sr_itself_are_refused_outside_sr_feedback(self):
        from render_report import notes_errors
        self.assertEqual([], notes_errors({'summary': '先核 F1。', 'items': {'W-1': '补磁件资料。'}}))
        self.assertTrue(notes_errors({'summary': 'SR改进部分有效，真实BR1误报仍未解决。'}))
        self.assertTrue(notes_errors({'items': {'W-1': '质量提示仍有 17 条'}}))

    def test_stage_na_is_handed_over_without_blocking(self):
        # The wording is in the golden snapshot (downstream.md); the handoff does not block and opens no work item.
        p, r, db = downstream()
        text, gate = report(p, r, db)
        self.assertEqual((gate['release'], gate['blockers']), ('GO', []))
        self.assertIn('RST-E01.C1', text.split('## 交给后续环节的要求')[1])
        self.assertNotIn('## 待办', text)

    def tool_gate(self, row_update, codes=(), rows=1, objects=None):
        p, r, db = fixture()
        keys = [c['id'] for c in r['checks'][:rows]]
        for key, obj in zip(keys, objects or []):
            next(c for c in p['checks'] if c['id'] == key)['object'] = obj
        if objects:
            r['plan_digest'] = vr.fingerprint(p)
        for row in r['checks'][:rows]:
            row.update(copy.deepcopy(row_update))
        real = vr.validate_inventories

        def gated(*args, gaps=None):
            gates = real(*args, gaps=gaps)
            for key in keys:
                gates.setdefault(key, []).append(key + ': synthetic tool gap before PASS')
                if gaps is not None:
                    gaps.setdefault(key, []).extend(codes)
            return gates
        with mock.patch.object(vr, 'validate_inventories', gated):
            return keys[0], report(p, r, db)

    MANUAL = {'tool_limitation': 'Kelvin source pins not mapped', 'method': 'Traced pins on the vendor drawing',
              'sr_improvement': 'Accept S1_KELVIN/S2_POWER as source aliases backed by the pin map',
              'evidence': [{'source': 'synthetic-fixture.json', 'locator': 'Q1'}]}

    def test_manual_verification_does_not_override_a_missing_input(self):
        """A gap the reviewer closes by declaring an input (datasheet requirement, intent, evidence) is supplied and
        the plan regenerated; only a model the tool lacks is verified by hand."""
        key, (_, gate) = self.tool_gate({'manual_verification': self.MANUAL}, codes=['datasheet-requirement:capacitance'])
        self.assertFalse(gate['valid'])
        self.assertTrue(any(key in e and 'datasheet-requirement:capacitance' in e and 'regenerate' in e
                            for e in gate['errors']), gate['errors'])
        _, (text, gate) = self.tool_gate({'manual_verification': self.MANUAL}, codes=['pin-role-or-model:U2'])
        self.assertTrue(gate['valid'], gate['errors'])
        self.assertEqual(gate['sr_improvements'][0]['tool_gaps'], ['pin-role-or-model:U2'])
        self.assertIn('pin-role-or-model:U2', text.split('## 对 SR 的反馈（设计者不用处理）')[1])

    def test_one_manual_method_over_different_objects_is_refused(self):
        _, (_, gate) = self.tool_gate({'manual_verification': self.MANUAL}, rows=2,
                                      objects=[{'ref': 'Q1'}, {'ref': 'Q2'}])
        self.assertTrue(any('manual_verification.method' in e for e in gate['errors']), gate['errors'])
        _, (_, gate) = self.tool_gate({'manual_verification': self.MANUAL}, rows=2,
                                      objects=[{'ref': 'Q1'}, {'ref': 'Q1'}])
        self.assertFalse(any('manual_verification.method' in e for e in gate['errors']), gate['errors'])

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
        section = text.split('## 对 SR 的反馈（设计者不用处理）')[1].split('### 工具判断不了、已逐项手工核对的检查')[1]
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

    def test_invalid_records_are_flagged_before_anything_else(self):
        p, r, db = decisive()
        del r['functions'][0]['open'][0]['acquisition']
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
        rows = [{'id': 'A.%d' % i, 'review_result': 'INSUFFICIENT', 'gap_cause': 'EXTERNAL_DATA'} for i in range(13)]
        rows.append({'id': 'A.13', 'review_result': 'INSUFFICIENT', 'gap_cause': 'DESIGN_OPEN'})
        self.assertEqual(item_kind(rows), '缺资料（另 设计没定 1 条）')
        self.assertEqual(item_kind(rows[:13]), '缺资料')
        p, r, db = fixture()
        fail(r)
        r['findings'][0]['check_ids'] = [r['checks'][0]['id']]
        with mock.patch('render_report.is_document', return_value=True):
            text, _ = report(p, r, db)
        self.assertIn('电路没有发现错误，文档有 1 处错误（P1，必需功能可能不达标）', text)
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
        p['review_mode'] = 'revision'
        r['history_inputs'] = ['reviews/R1']
        text, gate = report(p, r, db)
        self.assertIn('上一版审查（`R1`）的问题已逐条复验，其余结论按现在的图纸和资料重新判断。', body(text))
        self.assertNotIn('上一版问题未逐条复验', text)
        r['history_inputs'] = []
        self.assertNotIn('上一版审查', body(report(p, r, db)[0]))   # nothing to say when none was seen
        # 真实反例：上一版 2 条问题只在旁路文件里对照，报告却显示 0 条处理记录。
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'record').mkdir()
            (Path(tmp) / 'record' / 'review-results.json').write_text(
                json.dumps({'findings': [{'id': 'F-OLD-1'}, {'id': 'F-OLD-2'}]}), encoding='utf-8')
            r['history_inputs'] = [tmp]
            text, gate = report(p, r, db)
        self.assertIn('但它记录的 2 个问题（F-OLD-1、F-OLD-2）还没有逐条写明已改、保留还是撤回。', body(text))
        self.assertIn('| 上一版问题的处理记录（不计入上面各行） | 0（已声明上一版材料，但没有逐条复验检查项） |', text)
        self.assertNotIn(tmp, text)

    def test_first_review_that_saw_history_says_it_does_not_reverify(self):
        # 真实反例：首审可见上一版审查，报告却写“只用于上一版问题的复验”并印出本机绝对路径，
        # 而首审模式根本加不了 REQ-H02 复验行。
        p, r, db = decisive()
        p['review_mode'] = 'first'
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'record').mkdir()
            (Path(tmp) / 'record' / 'review-results.json').write_text(
                json.dumps({'findings': [{'id': 'F-OLD-1'}]}), encoding='utf-8')
            r['history_inputs'] = [tmp]
            text, gate = report(p, r, db)
        self.assertIn('审查时看过上一版审查（`%s`），但结论都按现在的图纸和资料重新判断；上一版的问题没有逐条对照列出。'
                      % Path(tmp).name, body(text))
        self.assertNotIn('已逐条复验', text)
        self.assertNotIn('还没有逐条写明', text)
        self.assertNotIn(tmp, text)
        self.assertIn('| 上一版问题的处理记录（不计入上面各行） | 0（首审不逐条登记） |', text)

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

    def test_a_check_id_the_plan_generated_is_not_jargon(self):
        from render_report import jargon_in
        self.assertEqual(jargon_in('| 整机试验 | REQ-D01.DOWNSTREAM-HANDOFF.REQ-MARKET-001 | 整板 |'), [])
        self.assertEqual(jargon_in('REQ-D01.DOWNSTREAM-HANDOFF.REQ-FORM-001 交给 handoff'), ['handoff'])

    def test_root_gap_count_not_check_count_and_details_preserve_evidence(self):
        from test_check_explanations import synthetic
        p, r = synthetic(['FAIL', 'INSUFFICIENT'])
        gap = next(c for c in r['checks'] if c['review_result'] == 'INSUFFICIENT')
        gap['potential_severity'] = 'P0'
        task = {'id': 'W1', 'title': 'single cause', 'check_ids': [gap['id']]}
        text = render(p, r, {'valid': True, 'workflow': {'work_items': [task]}},
                      {'sr_feedback': [{'kind': 'software_bug', 'rules': ['DOC-Q01'],
                                        'instance': 'path error', 'suggestion': 'verify archive'}]}, detail='full')
        self.assertIn('现在还判断不了，其中 1 件可能损坏器件或危及安全（P0）', text)
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
        self.render_current()

    def render_current(self, notes=None, title=None, detail='compact'):
        """The report as render_report.py writes it from the work ledger (the pack renders it again, 2.3)."""
        load = lambda name: json.loads((self.work / name).read_text())
        write_report(self.out, render(load('review-plan.json'), load('review-results.json'), load('review-gate.json'),
                                      notes, title, detail))

    def run_pack(self):
        return pack(self.out, self.ledger, str(self.work), {'requirements': str(self.inputs)})

    def cite(self, source):
        path = self.work / 'review-results.json'
        data = json.loads(path.read_text())
        data['checks'][0]['evidence'].append({'source': str(source), 'locator': 'test'})
        path.write_text(json.dumps(data))
        self.render_current()

    def test_hand_drawn_circuits_are_not_packed_without_their_candidate_file(self):
        path = self.work / 'intent.json'
        path.write_text(json.dumps({'schema_version': 4, 'circuits': [
            {'id': 'BIAS', 'type': 'POWER_CONVERTER', 'refs': ['Q2'], 'states': ['run'], 'citation': 'p1'}]}))
        errors, _ = self.run_pack()
        self.assertTrue(any('circuit-candidates.json' in e for e in errors), errors)
        import circuit_candidates
        db = json.loads((self.work / 'db.json').read_text())
        candidates = circuit_candidates.build(db, {})
        (self.work / 'circuit-candidates.json').write_text(json.dumps(candidates))
        self.ledger['circuit-candidates.json'] = str(self.work / 'circuit-candidates.json')
        errors, _ = self.run_pack()
        self.assertTrue(any('circuit_decisions missing' in e for e in errors), errors)
        # the fixture's active parts outside every candidate (U1 since results 7) are rejected on purpose; passives may stay
        intent = {'schema_version': 4, 'circuit_decisions': [{'candidate': c['id'], 'decision': 'accept'} for c in candidates['candidates']]
                  + [{'decision': 'reject', 'ref': u['ref'], 'reason': 'OUTSIDE_SCOPE', 'citation': 'p1'}
                     for u in candidates['unassigned'] if u.get('kind') == 'ic']}
        import circuit_decisions
        path.write_text(json.dumps(circuit_decisions.write_circuits(intent, candidates)))
        errors, _ = self.run_pack()
        self.assertFalse(any('circuit' in e for e in errors), errors)
        stale = dict(candidates, db_sha256='0' * 64)
        (self.work / 'circuit-candidates.json').write_text(json.dumps(stale))
        errors, _ = self.run_pack()
        self.assertTrue(any('db_sha256' in e for e in errors), errors)

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
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), sorted([REPORT, REPORT_HTML, RECORD]))
        packed = {Path(k).relative_to(RECORD).as_posix() for k in manifest['packed']}
        self.assertEqual(packed, set(LEDGER) | {'evidence/calc/startup.md', 'evidence/synthetic-fixture.json'})
        self.assertFalse((self.out / RECORD / 'evidence' / 'debug.log').exists())
        self.assertEqual(manifest['inputs']['requirements']['kind'], 'directory')
        self.assertEqual(len(manifest['inputs']['requirements']['tree_sha256']), 64)

    def test_unfinished_review_cannot_be_packed(self):
        results = json.loads((self.work / 'review-results.json').read_text())
        row = results['checks'][0]
        item = results['functions'][0]['open'][0]
        item['kind'] = 'REVIEW_INCOMPLETE'
        for field in ('acquisition', 'closure', 'checked', 'why_insufficient', 'worst_case'):
            item.pop(field)
        (self.work / 'review-results.json').write_text(json.dumps(results))
        errors, _ = self.run_pack()
        self.assertTrue(any('review not finished' in e and row['id'] in e for e in errors), errors)

    def test_jargon_in_report_body_fails_the_pack(self):
        write_report(self.out, '# r\n\n## 结论\n\n- 还不能冻结，见本检查项。\n\n## 对 SR 的反馈（设计者不用处理）\n\n- 原生映射\n')
        errors, _ = self.run_pack()
        hits = [e for e in errors if 'plain words' in e]
        self.assertEqual(len(hits), 1, errors)
        self.assertIn('冻结/本检查项', hits[0])

    def test_packed_review_can_be_repacked_in_place(self):
        errors, _ = self.run_pack()
        self.assertEqual(errors, [])
        record = self.out / RECORD
        ledger = {name: str(record / name) for name in LEDGER}
        errors, manifest = pack(self.out, ledger, str(record / 'evidence'), {'requirements': str(self.inputs)})
        self.assertEqual(errors, [])
        self.assertIn(RECORD + '/evidence/calc/startup.md', manifest['packed'])

    def test_same_named_file_in_an_input_does_not_hide_new_evidence(self):
        # 真实反例：旧审查目录作输入时，同名的本轮 page-1.png 被当成输入而漏装。
        results = json.loads((self.work / 'review-results.json').read_text())
        results['checks'][0]['evidence'].append({'source': 'page-1.png', 'locator': 'U1'})
        results['checks'][0]['evidence'].append({'source': 'shots/page-2.png', 'locator': 'Q2'})
        (self.work / 'review-results.json').write_text(json.dumps(results))
        (self.work / 'page-1.png').write_bytes(b'new')
        (self.inputs / 'page-1.png').write_bytes(b'old')
        (self.inputs / 'page-2.png').write_bytes(b'old')
        errors, manifest = self.run_pack()
        self.assertIn(RECORD + '/evidence/page-1.png', manifest['packed'])
        self.assertEqual((self.out / RECORD / 'evidence' / 'page-1.png').read_bytes(), b'new')
        self.assertTrue(any('shots/page-2.png' in e for e in errors), errors)

    def test_report_links_must_resolve_after_packing(self):
        write_report(self.out, '# report\n\n[算式](record/evidence/calc/startup.md) '
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


class DeliveryReviewTests(unittest.TestCase):
    """An ASG delivery carries its own selection, calculation inventory and preflight result. SR reviews the
    schematic from scratch and does not re-judge those records, so a review that declares the delivery packs without
    them (2026-10-22: SR is independent of the designer's documents)."""

    render_current = PackReviewTests.render_current

    def setUp(self):
        PackReviewTests.setUp(self)
        self.asg = self.tmp / 'asg'
        rec = self.asg / 'record'
        (rec / 'calculations').mkdir(parents=True)
        (self.asg / '原理图').mkdir()
        (rec / 'selection.json').write_text(json.dumps({'schema_version': 1, 'roles': []}))
        (rec / 'calculations' / 'results.json').write_text(json.dumps(
            {'schema_version': 1, 'calculations': [{'id': 'PFC-1', 'claim': 'SUPPORTED'}]}))
        (rec / 'preflight-delivery.json').write_text(json.dumps(
            {'schema_version': 1, 'status': 'PASS', 'results': {'PFC-1': {'status': 'PASS'}}}))

    def test_a_delivery_packs_without_reviewing_its_own_records(self):
        errors, _ = pack(self.out, self.ledger, str(self.work),
                         {'requirements': str(self.inputs), 'schematic': str(self.asg / '原理图')})
        self.assertEqual(errors, [])

    def test_plain_input_folders_ask_for_nothing(self):
        errors, _ = pack(self.out, self.ledger, str(self.work), {'requirements': str(self.inputs)})
        self.assertEqual(errors, [])


if __name__ == '__main__':
    unittest.main()

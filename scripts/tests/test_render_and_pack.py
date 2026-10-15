"""The delivery is one generated report plus a small record; numbers come only from the ledger."""
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
        self.assertTrue(lines[2].startswith('- **检查结果**：共 %d 条。通过（PASS） ' % len(r['checks'])))
        self.assertIn('资料不足无法判断（INSUFFICIENT） 1 条', lines[2])
        self.assertEqual(lines[3], '- **发现的错误**：0 处。')
        self.assertTrue(lines[4].startswith('- **能否定稿**：还不能定稿。还差：'))
        self.assertIn('1 条检查缺资料或设计依据', lines[5])
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

    def test_stage_na_is_handed_over_without_blocking(self):
        p, r, db = downstream()
        text, gate = report(p, r, db)
        self.assertEqual(gate['release'], 'GO')
        self.assertIn('- **能否定稿**：可以定稿', text)
        section = text.split('## 交给后续环节的要求')[1]
        self.assertIn('| Synthetic test engineer | 1 |', section)
        self.assertIn('不影响原理图定稿', section)
        self.assertIn('| 与本产品无关（NA） | 0 |', text)
        self.assertIn('| 原理图阶段不判、交给后续环节 | 1 |', text)
        self.assertIn('原理图阶段不判、交给后续环节 1 条', text)
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
        self.assertIn(key + ': synthetic tool gap before PASS (or record manual_verification if a reviewer verified it by hand)',
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

    def test_handoffs_list_where_they_apply_and_tool_gaps_merge(self):
        p, r, db = downstream()
        key = r['checks'][0]['id']
        next(c for c in p['checks'] if c['id'] == key)['object']['ref'] = 'U7'
        text, _ = report(p, r, db)
        self.assertIn('| 负责方 | 条数 | 涉及位号/网络 |', text)
        self.assertIn('| U7 |', text.split('## 交给后续环节的要求')[1])
        from render_report import render
        gate = {'valid': True, 'release': 'GO', 'blockers': [], 'sr_improvements': [
            {'check_id': 'A.1', 'tool_limitation': 'x', 'sr_improvement': 'y', 'method': 'z'},
            {'check_id': 'B.1', 'tool_limitation': 'x', 'sr_improvement': 'y', 'method': 'z'}]}
        merged = render({}, {'checks': []}, gate)
        self.assertIn('### A.1、B.1', merged)
        self.assertEqual(merged.count('**SR 为什么做不到**'), 1)
        self.assertNotIn('人工', merged)

    def test_jargon_is_detected_only_as_whole_ascii_words(self):
        from render_report import jargon_in
        self.assertEqual(jargon_in('按remediation同步fit清单，交下游'), ['下游', 'remediation', 'fit'])
        self.assertEqual(jargon_in('Q201 栅极经 R203 到 PFC_GATE，fitted 状态'), [])


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

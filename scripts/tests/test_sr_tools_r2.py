"""Matrix 电源与保护 R2 首审的工具与交接问题（SR技能不足.md 3.1–3.3、3.6–3.9、4.3、6.1、6.2、6.4；user 2026-11-04：
修改SR不足）：多文档需求抽取与 …ID 表头、资料链接自动解析、ASG 规格列作 BOM 额定、承接电路诊断不刷屏、开放项派生错误合并、
准则库引文豁免写法检查、kicad-cli 批注告警带位号、同料号资料请求合并、ASG 设计记录的对账清单。"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import audit_datasheets
import design_checklist
import gap_inventory
import guideline_criteria
import independence
import pack_review
import parse_kicad
import read_bom
import render_report
import requirement_bindings
import requirements_extract
import validate_review
from checkers.passive_stress import bom_ratings


# 3.1 / 3.2 requirements
USER_DOC = '''# 用户需求
## 1 决定
| 决定 ID | 已确认内容 | 影响 |
|---|---|---|
| D-PWR-001 | 只保留一路 12 V | 原 11 A 不沿用 |
## 2 协议
| 用户需求 ID | 协议要求 | 来源 |
|---|---|---|
| REQ-IF-003 | C 口 Pin1/2 GND | 协议 3.2 |
## 3 批注
| 原件批注 ID | 锚定接口 | 批注原文 |
|---|---|---|
| 19 | C 主电源输入表头 | 1/2是GND |
## 4 版本
| 版本 | 日期 |
|---|---|
| V-1 | 2026 |
'''
SPEC_DOC = '''# 工程规格
| 工程 ID | 要求 |
|---|---|
| E-IN-01 | 24 V±5% |
'''


def write_docs(folder):
    user, spec = Path(folder) / '用户需求.md', Path(folder) / '工程规格.md'
    user.write_text(USER_DOC, encoding='utf-8')
    spec.write_text(SPEC_DOC, encoding='utf-8')
    return user, spec


def test_a_header_ending_in_id_is_an_id_column_and_numbered_rows_are_not_requirements():
    with tempfile.TemporaryDirectory() as folder:
        user, _ = write_docs(folder)
        out = requirements_extract.extract(user)
    assert [i['id'] for i in out['items']] == ['D-PWR-001', 'REQ-IF-003']
    assert requirements_extract.is_id_header('用户需求 ID') and requirements_extract.is_id_header('决定ID')
    assert not requirements_extract.is_id_header('版本') and not requirements_extract.is_id_header('IDLE')


def test_several_documents_are_transcribed_in_one_run_with_the_source_list_to_paste():
    with tempfile.TemporaryDirectory() as folder:
        user, spec = write_docs(folder)
        target = Path(folder) / 'requirements.json'
        done = subprocess.run([sys.executable, str(SCRIPTS / 'requirements_extract.py'), str(user), str(spec),
                               '--json', str(target)], capture_output=True, text=True)
        assert done.returncode == 0, done.stdout + done.stderr
        out = json.loads(target.read_text(encoding='utf-8'))
        assert [i['id'] for i in out['items']] == ['D-PWR-001', 'REQ-IF-003', 'E-IN-01']
        assert [s['path'] for s in out['requirement_source']] == [str(user), str(spec)]
        loaded, errors = requirements_extract.load(out['requirement_source'])
        assert errors == [] and [i['id'] for i in loaded['items']] == ['D-PWR-001', 'REQ-IF-003', 'E-IN-01']


# 3.3 / 6.2 datasheet links
def linked_db(path, other=None):
    return {'parts': {
        'U1': {'part': 'TPS26630RGER', 'value': 'TPS26630RGER', 'prim': 'X', 'jedec': '', 'nc': False,
               'datasheet': str(path), 'fields': {'MPN': 'TPS26630RGER'}},
        'U2': {'part': 'TPS26630RGER', 'value': 'TPS26630RGER', 'prim': 'X', 'jedec': '', 'nc': False,
               'datasheet': str(other or path), 'fields': {'MPN': 'TPS26630RGER'}},
        'Q1': {'part': 'IPT015N10N5ATMA1', 'value': 'IPT015N10N5ATMA1', 'prim': 'Q', 'jedec': '', 'nc': False,
               'datasheet': '', 'fields': {'MPN': 'IPT015N10N5ATMA1'}}},
        'bom': {'parts': {'Q1': {'Datasheet': 'raw/Datasheet/ipt.txt'}}}}


def test_the_design_datasheet_link_resolves_a_material_whose_document_names_it(monkeypatch):
    with tempfile.TemporaryDirectory() as folder:
        doc = Path(folder) / 'TI - TPS2663.txt'
        doc.write_text('Ordering: TPS26630RGER, TPS26631RGER\n', encoding='utf-8')
        wiki = Path(folder) / 'wiki'
        (wiki / 'raw' / 'Datasheet').mkdir(parents=True)
        (wiki / 'raw' / 'Datasheet' / 'ipt.txt').write_text('IPT015N10N5 OptiMOS 5\n', encoding='utf-8')
        monkeypatch.setattr(audit_datasheets, 'WIKI_ROOT', str(wiki))
        db = linked_db(doc)
        audit = audit_datasheets.build_datasheet_audit(db, required_refs=['Q1'])
        materials = {m['identity']: m for m in audit['materials']}
        tps, ipt = materials['TPS26630RGER'], materials['IPT015N10N5ATMA1']
        assert tps['status'] == 'AVAILABLE' and tps['document']['resolved_by'] == 'design_link'
        assert tps['document']['identity_match'] == 'exact' and tps['document']['path'] == str(doc)
        assert ipt['status'] == 'AVAILABLE' and ipt['document']['identity_match'] == 'ordering_suffix'
        assert ipt['document']['document_model'] == 'IPT015N10N5'
        assert [d['identity'] for d in audit['diagnostics'] if d['code'] == 'DATASHEET_ORDERING_SUFFIX'] == ['IPT015N10N5ATMA1']
        assert audit_datasheets.validate_datasheet_audit(audit, db) == []
        # a hand-written resolution comes first
        resolution = {'schema_version': 1, 'entries': [{'identity': 'TPS26630RGER', 'status': 'NOT_FOUND',
                      'searched_sources': ['LCSC 立创', 'TI 原厂官网'], 'searched_at': '2026-11-04'}]}
        audit = audit_datasheets.build_datasheet_audit(db, resolution=resolution, required_refs=['Q1'])
        assert {m['identity']: m['status'] for m in audit['materials']}['TPS26630RGER'] == 'NOT_FOUND'


def test_a_link_that_does_not_name_the_part_or_two_different_links_are_not_proof():
    with tempfile.TemporaryDirectory() as folder:
        doc = Path(folder) / 'a.txt'
        doc.write_text('LM5069 hot swap\n', encoding='utf-8')
        other = Path(folder) / 'b.txt'
        other.write_text('TPS26630RGER\n', encoding='utf-8')
        audit = audit_datasheets.build_datasheet_audit(linked_db(doc))
        tps = {m['identity']: m for m in audit['materials']}['TPS26630RGER']
        assert tps['status'] == 'NEEDS_VERIFICATION' and tps['local_candidates'] == [str(doc)]
        assert any(d['code'] == 'DATASHEET_LINK_UNVERIFIED' for d in audit['diagnostics'])
        assert audit_datasheets.linked_path(linked_db(doc, other), ['U1', 'U2']) is None
        # a variant digit is not an ordering suffix
        assert audit_datasheets.identity_in_document('TPS26631RGER', str(other)) is None


# 6.1 ASG specification columns
SPEC = ('容量要求: capacitance=220 uF @ 温度=−40～+70 ℃ 工作 | rated_voltage要求: rated_voltage>=50 V @ 温度=85 ℃ 额定 | '
        'ripple_current要求: ripple_current>=1.68 A @ 温度=125 ℃，100 kHz | esr要求: esr<=0.03 ohm @ 温度=20 ℃')


def test_asg_specification_columns_are_read_as_minimums():
    specs = read_bom.spec_constraints({'RequirementSpec': SPEC, 'Performance': 'rated_voltage>=99 V'})
    assert [(s['name'], s['op'], s['value'], s['unit']) for s in specs] == [
        ('capacitance', '=', 220.0, 'uF'), ('rated_voltage', '>=', 50.0, 'V'), ('ripple_current', '>=', 1.68, 'A'),
        ('esr', '<=', 0.03, 'ohm')]
    assert specs[1]['condition'] == '温度=85 ℃ 额定'
    assert bom_ratings({'RequirementSpec': SPEC}) == {'voltage_v': 50.0}
    assert bom_ratings({'SelectedSpec': '连续额定功率要求: power>=2 W @ 温度=70 ℃ 额定'}) == {'power_w': 2.0}
    assert bom_ratings({'RequirementSpec': 'esr要求: esr<=0.03 ohm'}) == {}
    assert bom_ratings({'RequirementSpec': 'x: rated_voltage<=60 V | y: power<=1 W'}) == {}   # a maximum is no rating


# 3.6 owners outside the candidates
def test_owners_outside_candidates_are_one_line_per_requirement_with_a_short_list():
    rows = [{'rule': 'REQ-D01', 'object': {'requirement_id': 'E-IN-02', 'aspect': aspect},
             'requirement_owners': ['SYS-MONITOR', 'CH1'], 'owner_candidates': [{'id': 'CH%d' % i} for i in range(1, 11)]}
            for aspect in ('CONVERTER_INPUT_RANGE', 'PROTECTION_THRESHOLDS')]
    found = requirement_bindings.outside_candidates(rows)
    assert len(found) == 1
    assert found[0]['owners'] == ['SYS-MONITOR'] and found[0]['aspect'] == 'CONVERTER_INPUT_RANGE/PROTECTION_THRESHOLDS'
    assert len(found[0]['candidates']) == 10
    assert 'CH5 等 10 个' in found[0]['detail'] and 'CH6' not in found[0]['detail']


# 3.7 one open item's fault said once
def test_errors_rows_share_through_one_open_item_are_said_once():
    checks = {'A.1': {'open_ref': 'FN/K'}, 'A.2': {'open_ref': 'FN/K'}, 'A.3': {'open_ref': 'FN/K'}, 'B.1': {}}
    errors = ['A.1: kind is bad', 'A.2: kind is bad', 'A.3: kind is bad', 'A.2: only mine', 'B.1: x', 'plain', 'plain']
    out = validate_review.collapse_open_cascade(errors, checks)
    assert out == ['FN/K（3 条检查项同错，如 A.1、A.2、A.3）: kind is bad', 'A.2: only mine', 'B.1: x', 'plain', 'plain']
    assert validate_review.collapse_open_cascade([], checks) == []


# 3.8 quotations of the rule library
def test_a_quoted_rule_library_title_is_not_the_reports_wording(monkeypatch):
    library = guideline_criteria.load(guideline_criteria.BUNDLE_PATH)
    monkeypatch.setattr(guideline_criteria, 'load', lambda *a, **k: library)
    card = next(c for c in library['criteria'] if '下游' in c['title'])
    report = '# 报告\n| %s | %s |\n这一行说下游。\n' % (card['id'], render_report.cell(card['title']))
    errors = pack_review.plain_language_errors(report)
    assert len(errors) == 1 and 'line 3' in errors[0]
    assert render_report.without_quotes('x %s y' % render_report.cell(card['title']), render_report.guideline_quotes()) == 'x   y'


# 3.9 annotation warning
def sheet(symbols, sheets=()):
    body = ''.join('(sheet (property "Sheetname" "%s") (property "Sheetfile" "%s"))' % (s, s) for s in sheets)
    body += ''.join('(symbol (lib_id "power:PWR_FLAG") (unit %s) (property "Reference" "%s") (instances (project "P" '
                    '(path "/a" (reference "%s") (unit %s)))))' % (unit, ref, ref, unit) for ref, unit in symbols)
    return '(kicad_sch (version 20250114) %s)' % body


def test_annotation_issues_name_the_symbols_kicad_cli_does_not():
    with tempfile.TemporaryDirectory() as folder:
        root, child = Path(folder) / 'top.kicad_sch', Path(folder) / 'child.kicad_sch'
        root.write_text(sheet([('R1', 1), ('#FLG1820aa', 1)], ['child.kicad_sch']), encoding='utf-8')
        child.write_text(sheet([('R1', 1), ('U2?', 1), ('U3', 1), ('U3', 2), ('#FLG01', 1)]), encoding='utf-8')
        issues = parse_kicad.annotation_issues(root)
        assert [(i['ref'], i['issue'], i['sheet']) for i in issues] == [
            ('#FLG1820aa', 'no_number', 'top.kicad_sch'), ('R1', 'duplicate', 'child.kicad_sch'),
            ('U2?', 'unannotated', 'child.kicad_sch')]
        lines = parse_kicad.annotation_lines(issues)
        assert any('#FLG1820aa（top.kicad_sch）' in line and '电源/标志符号' in line for line in lines)
        child.write_text(sheet([('R2', 1)]), encoding='utf-8')
        root.write_text(sheet([('R1', 1)], ['child.kicad_sch']), encoding='utf-8')
        assert parse_kicad.annotation_issues(root) == []
        assert '没有找到位号级问题' in parse_kicad.annotation_lines([])[0]


def test_the_lint_annotation_candidate_carries_the_symbols():
    import lint
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder) / 'top.kicad_sch'
        root.write_text(sheet([('#FLGab', 1)]), encoding='utf-8')
        db = {'parts': {}, 'nets': {}, 'pin2net': {}, 'export_meta': {'source': str(root)}}
        linter = lint.Lint.__new__(lint.Lint)
        linter.db = db
        assert any('#FLGab' in line for line in linter._annotation_detail())
        linter.db = {'export_meta': {'source': str(Path(folder) / 'gone.kicad_sch')}}
        assert linter._annotation_detail() == []


# 4.3 one request per part number
def test_parts_of_one_part_number_are_one_datasheet_request():
    db = {'parts': {ref: {'part': 'A2012WR-S-4P-LCP', 'value': 'A2012WR-S-4P-LCP', 'fields': {'MPN': 'A2012WR-S-4P-LCP'}}
                    for ref in ('J901', 'J941')}}
    db['parts']['J1'] = {'part': 'Conn_01x02', 'value': 'Conn_01x02'}
    db['parts']['J2'] = {'part': 'Conn_01x02', 'value': 'Conn_01x02'}
    plan = {'checks': [
        {'id': 'DEV-D02.J901', 'rule': 'DEV-D02', 'readiness': 'WAITING_EVIDENCE', 'required_inputs': ['intent.devices.J901']},
        {'id': 'DEV-D02.J941', 'rule': 'DEV-D02', 'readiness': 'WAITING_EVIDENCE', 'required_inputs': ['intent.devices.J941']},
        {'id': 'DEV-D05.J901', 'rule': 'DEV-D05', 'readiness': 'WAITING_EVIDENCE', 'required_inputs': ['datasheet:A2012WR-S-4P-LCP']},
        {'id': 'DEV-D02.J1', 'rule': 'DEV-D02', 'readiness': 'WAITING_EVIDENCE', 'required_inputs': ['intent.devices.J1']},
        {'id': 'DEV-D02.J2', 'rule': 'DEV-D02', 'readiness': 'WAITING_EVIDENCE', 'required_inputs': ['intent.devices.J2']}]}
    rows = gap_inventory.build(plan, db=db)['by_owner']['part_data']
    assert sorted((r['input'], tuple(r['refs']), r['unblocks']) for r in rows) == [
        ('A2012WR-S-4P-LCP 的器件资料', ('J901', 'J941'), 3), ('J1 的器件资料', ('J1',), 1), ('J2 的器件资料', ('J2',), 1)]
    assert len(gap_inventory.build(plan)['by_owner']['part_data']) == 5   # without the db nothing is merged


def test_the_db_beside_the_plan_is_used_only_when_it_built_the_plan():
    from electrical_contract import db_fingerprint
    db = {'parts': {'J1': {'part': 'X'}}, 'nets': {}, 'pin2net': {}}
    with tempfile.TemporaryDirectory() as folder:
        (Path(folder) / 'db.json').write_text(json.dumps(db), encoding='utf-8')
        plan_path = str(Path(folder) / 'plan.json')
        assert gap_inventory.beside_db(plan_path, {'db_sha256': db_fingerprint(db)}) == db
        assert gap_inventory.beside_db(plan_path, {'db_sha256': 'other'}) is None


# 6.4 reconciliation list
CLOSURE = {'calculations': [{'id': 'CALC-REV', 'kind': 'threshold', 'refs': ['Q201', 'U201'], 'requirements': ['REQ-PROT-001'],
                             'coverage': 'bounded', 'conclusion': 'supported',
                             'parameters': [{'name': 'x', 'value': 125}],
                             'checks': [{'name': '反接时 LTC4359 IN 对 VSS 幅值 vs 绝对最大 40 V', 'value': 23.7, 'limit': 40},
                                        {'name': 'U201 温度 −40～+70 ℃ 下 10 %', 'value': 1}]}]}
REFERENCE = {'pin_maps': {'Q201': {'identity': {'mpn': 'IPT015N10N5ATMA1'}, 'pins': {'10': {}, '2': {}, '1': {}}}}}


def test_the_reconciliation_list_keeps_objects_and_names_never_values():
    out = design_checklist.build(CLOSURE, REFERENCE, results={'functions': [{'conditions': [{'refs': ['U201']}]}]})
    calc = out['calculations'][0]
    assert calc == {'id': 'CALC-REV', 'kind': 'threshold', 'refs': ['Q201', 'U201'], 'requirements': ['REQ-PROT-001'],
                    'checks': ['反接时 LTC4359 IN 对 VSS 幅值 vs 绝对最大 〈值〉', 'U201 温度 〈值〉 下 〈值〉'],
                    'refs_not_in_ledger': ['Q201']}
    text = json.dumps(out, ensure_ascii=False)
    for word in ('23.7', 'supported', 'bounded', '"value"', '"limit"', '125'):
        assert word not in text, word
    assert out['pin_maps'] == [{'ref': 'Q201', 'mpn': 'IPT015N10N5ATMA1', 'pins': ['1', '2', '10'], 'in_ledger': False}]


def test_the_asg_design_records_and_the_list_are_refused_as_citations():
    for path in ('record/design-closure.json', 'record/reference-input.json', 'design-checklist.json'):
        assert independence.designer_document(path), path
    assert independence.evidence_errors([{'id': 'X', 'evidence': [{'source': 'record/design-closure.json#CALC-REV'}]}])


def test_a_capacitor_without_footprint_passes_on_the_voltage_the_bom_specification_requires():
    import part_words as pw
    from checkers.passive_stress import _proposal
    entry = {'ref': 'C305', 'kind': pw.CAPACITOR, 'package': '0402', 'package_assumed': True, 'value': '100uF',
             'nets': ['24V_BUS', 'GND'], 'v_across_max': 25.2, 'bom_ratings': {'voltage_v': 50.0}, 'bases': []}
    result, calc, note = _proposal(entry)
    assert (result, calc['written_v']) == ('PASS', 50.0) and 'BOM 规格所写耐压 50V' in note
    entry['v_across_max'] = 60.0
    assert _proposal(entry)[0] is None
    entry.pop('bom_ratings')
    assert '没有封装也没写耐压' in _proposal(entry)[2]

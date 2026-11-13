"""真实缺口：OUT 正负浪涌及现场直流口必须进入现有审查问题。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import os
from unittest import mock
import catalog
import guideline_criteria as g
import plan_review
import render_report
from framework_fixtures import real_library


def test_output_and_field_surge_reach_plan_and_report(tmp_path):
    checks = [{'rule': 'PRO-D03', 'circuit_type': 'DC_24V'},
              {'rule': 'PRO-D04', 'circuit_type': 'POWER_PROTECTION'}]
    with mock.patch.dict(os.environ, {'GUIDELINE_CRITERIA': ''}):
        library = real_library()
        section = plan_review.guideline_section(checks, {'parts': {'R1': {'value': '10k', 'part': 'Device:R'}}}, {}, {}, library)
    path = tmp_path / 'criteria.json'
    path.write_text(g.dump(library), encoding='utf-8')
    for rid in ('G07-004', 'G07-022', 'G07-023', 'G07-024', 'G07-032'):
        assert rid in section['covered'], rid
    with mock.patch.dict(os.environ, {'GUIDELINE_CRITERIA': str(path)}):
        report = '\n'.join(render_report.render_guidelines({'guidelines': section}))
    assert 'G07-023' in report
    assert 'G07-032' in report


def test_surge_questions_require_both_states_and_dc_port_path():
    out = catalog.BY_ID['PRO-D04'].criterion
    field = catalog.BY_ID['PRO-D03'].criterion
    for phrase in ('正负极性', '开、关', '体二极管', '输出脚'):
        assert phrase in out
    for phrase in ('直流电源口', '并联电容', '串联元件'):
        assert phrase in field


def test_generated_interface_questions_carry_surge_requirements():
    from test_interface_rows import plan_for
    plan = plan_for()
    for check in plan['checks']:
        if check['rule'] == 'PRO-D04':
            assert '正负极性' in check['question']
            assert '开、关' in check['question']
        if check['rule'] == 'PRO-D03':
            assert '直流电源口' in check['question']
            assert '串联元件' in check['question']
    assert {'PRO-D03', 'PRO-D04'} <= {c['rule'] for c in plan['checks']}


def test_the_plan_and_report_record_the_knowledge_framework_identity():
    import knowledge_source
    with mock.patch.dict(os.environ, {'GUIDELINE_CRITERIA': ''}):
        section = plan_review.guideline_section([], {'parts': {}}, {}, {}, real_library())
        report = '\n'.join(render_report.render_guidelines({'guidelines': section}))
    ident = knowledge_source.identity()
    assert section['knowledge_fingerprint'] == ident['fingerprint'] and section['knowledge_read_date'] == ident['read_date']
    assert '知识框架 %s（%s 读取）' % (ident['fingerprint'][:12], ident['read_date']) in report

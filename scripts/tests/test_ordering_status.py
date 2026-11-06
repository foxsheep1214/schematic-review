"""订货表：先复现 ISOW3080，再防止量产误报、跨型号串列和假替代。"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ordering_status as order


def sheet(tmp_path, text, name='part.txt'):
    p = tmp_path / name
    p.write_text(text)
    return str(p)


def test_isow_preproduction_overrides_active_material_type(tmp_path):
    p = sheet(tmp_path, 'ISOW3080\nADVANCE INFORMATION\fOrderable part number Status Material type\n'
              'XISOW3080PDWER Active Preproduction SOIC 16\n')
    s = order.scan_ordering('ISOW3080', p)
    assert s['status'] == 'RISK'
    assert s['evidence'][1]['page'] == 2
    assert s['evidence'][1]['orderable'] == 'XISOW3080PDWER'
    assert 'Preproduction' in s['evidence'][1]['quote']
    assert s['path'] == p
    assert order.notice(s)['kind'] == 'RISK'


@pytest.mark.parametrize('status', ['Preview', 'Pre-Production', 'ADVANCE INFORMATION', 'Product Preview',
                                   'NRND', 'Not Recommended', 'Obsolete', 'Discontinued', 'Last Time Buy'])
def test_risk_statuses(tmp_path, status):
    s = order.scan_ordering('ABC123', sheet(tmp_path, f'Ordering Information\nABC123R {status}\n'))
    assert s['status'] == 'RISK'


def test_production_and_other_model_do_not_report_risk(tmp_path):
    s = order.scan_ordering('ABC123', sheet(tmp_path, 'Ordering Information\nABC123R Active\nABC124R Obsolete\n'))
    assert s['status'] == 'PRODUCTION'
    assert order.notice(s) is None


def test_acceptance_is_specific_and_requires_owner_action_and_source(tmp_path):
    s = order.scan_ordering('ABC123', sheet(tmp_path, 'Ordering Information\nABC123R Preview\n'))
    accepted = dict(identity='ABC123', accepted_by='采购负责人张某', action='投产前换料', source='技术转交表#采购')
    assert order.notice(s, accepted)['kind'] == 'REGISTERED'
    assert order.notice(s, dict(accepted, identity='OTHER'))['kind'] == 'RISK'
    assert order.notice(s, dict(accepted, accepted_by=''))['kind'] == 'RISK'
    assert order.notice(s, dict(accepted, action='继续研究'))['kind'] == 'RISK'


@pytest.mark.parametrize('text', ['', 'ABC123 Active', 'Ordering Guide\nABC123R SOIC 16',
                                  'Ordering Information\nABC124R Active\n(1) Obsolete: discontinued'])
def test_unreadable_or_no_status_is_insufficient(tmp_path, text):
    s = order.scan_ordering('ABC123', sheet(tmp_path, text))
    assert s['status'] == 'INSUFFICIENT'
    assert order.notice(s)['kind'] == 'INSUFFICIENT'
    assert order.scan_ordering('ABC123', str(tmp_path/'absent.pdf'))['status'] == 'INSUFFICIENT'


@pytest.mark.parametrize('prefix', ['X', 'P'])
def test_prefix_alone_never_proves_production(tmp_path, prefix):
    s = order.scan_ordering('ABC123', sheet(tmp_path, f'Ordering Information\n{prefix}ABC123R Active\n'))
    assert s['status'] == 'RISK'
    assert '前缀' in order.notice(s)['message']


def test_candidates_only_real_library_and_checked_status(tmp_path):
    for model, state in [('ABC123', 'Preview'), ('ALT1', 'Active'), ('ALT2', ''), ('ALT3', 'NRND')]:
        sheet(tmp_path, f'Ordering Information\n{model}R {state}\n', model+'.txt')
    rows = [dict(model=m, path=m+'.txt', category='15', subcategory=sub)
            for m, sub in [('ABC123','RS485'), ('ALT1','RS485'), ('ALT2','RS485'), ('ALT3','OTHER')]]
    catalog = tmp_path/'catalog.json'; catalog.write_text(json.dumps({'rows': rows}))
    selection = {'roles':[{'candidates':[{'mpn':'ABC123', 'status':'selected'},
                  {'mpn':'ALT3', 'status':'rejected'}, {'mpn':'FAKE', 'status':'rejected'}]}]}
    pool = order.candidate_pool('ABC123', catalog, selection)
    assert {x['model'] for x in pool} == {'ALT1','ALT2','ALT3'}
    assessments = {m:dict(suitable=True, why='同功能和电压范围，须独立核引脚', pending=['封装不兼容，重画 PCB'])
                   for m in ['ALT1','ALT2','ALT3','FAKE']}
    rec = order.recommend_candidates(pool, assessments)
    assert [x['model'] for x in rec] == ['ALT1','ALT3']
    assert rec[1]['ordering']['status'] == 'RISK'
    assert all(x['tentative'] and x['pending'] for x in rec)
    assert order.recommend_candidates(pool, {}) == []


def test_existing_datasheet_audit_prompts_ordering_review(tmp_path):
    import audit_datasheets
    p = sheet(tmp_path, 'ISOW3080 isolated RS-485\nOrdering Information\nXISOW3080PDWER Pre-Production\n')
    db = {'parts': {'U401': {'value': 'ISOW3080', 'part': 'ISOW3080', 'datasheet': p}},
          'pin2net': {}, 'pinname': {}, 'nets': {}}
    audit = audit_datasheets.build_datasheet_audit(db, required_refs=['U401'])
    tasks = [r for r in audit['agent_requests'] if r['action'] == 'REVIEW_ORDERING_STATUS']
    assert len(tasks) == 1
    assert tasks[0]['ordering']['status'] == 'RISK'
    assert tasks[0]['refdes'] == ['U401']


def test_adjacent_numeric_variant_is_not_ordering_suffix(tmp_path):
    s = order.scan_ordering('ABC123', sheet(tmp_path, 'Ordering Information\nABC1234R Obsolete\n'))
    assert s['status'] == 'INSUFFICIENT'


def test_audit_production_and_missing_material(tmp_path):
    import audit_datasheets
    p = sheet(tmp_path, 'Ordering Information\nABC123R Active\n')
    db = {'parts': {'U1': {'value': 'ABC123', 'part': 'ABC123', 'datasheet': p}}}
    a = audit_datasheets.build_datasheet_audit(db, required_refs=['U1'])
    assert a['agent_requests'] == []
    assert audit_datasheets.validate_datasheet_audit(a, db) == []
    db['parts']['U1']['datasheet'] = ''
    a = audit_datasheets.build_datasheet_audit(db, required_refs=['U1'])
    assert a['materials'][0]['ordering']['status'] == 'INSUFFICIENT'
    assert audit_datasheets.validate_datasheet_audit(a, db) == []


def test_advance_banner_is_not_overridden_by_active(tmp_path):
    s = order.scan_ordering('ABC123', sheet(tmp_path, 'ABC123\nADVANCE INFORMATION\fOrdering Guide\nABC123R Active\n'))
    assert s['status'] == 'RISK'
    assert s['evidence'][0]['page'] == 1
    s = order.scan_ordering('ABC123', sheet(tmp_path, 'OTHER456\nADVANCE INFORMATION\fOrdering Guide\nABC123R Active\n'))
    assert s['status'] == 'PRODUCTION'


def test_unknown_status_cannot_be_accepted_away(tmp_path):
    s = order.scan_ordering('ABC123', str(tmp_path/'missing.pdf'))
    a = dict(identity='ABC123', accepted_by='采购负责人', action='投产前换料', source='技术转交表#采购')
    assert order.notice(s, a)['kind'] == 'INSUFFICIENT'


def test_prefix_without_status_is_still_a_risk_hint(tmp_path):
    s = order.scan_ordering('ABC123', sheet(tmp_path, 'Ordering Information\nPABC123R SOIC 16\n'))
    assert s['status'] == 'RISK'
    assert s['evidence'][0]['explicit'] is False


def test_recommendations_limit_and_independent_rejection(tmp_path):
    pool = []
    assessments = {}
    for n in range(5):
        m = f'ALT{n}'
        pool.append(dict(model=m, ordering=order.scan_ordering(m, sheet(tmp_path, f'Ordering Guide\n{m}R Active', m+'.txt'))))
        assessments[m] = dict(suitable=n != 0, why='功能/电压匹配（原表 p1）；引脚须重核', pending=['引脚'])
    rec = order.recommend_candidates(pool, assessments)
    assert [r['model'] for r in rec] == ['ALT1', 'ALT2', 'ALT3']

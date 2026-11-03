"""boards-merge5 item 3 (spot-check feedback): doc/ordering defects graded by electrical consequence, voltages read only
off a net name marked 按网名推定, and a relaxed connection gate that still leaves a crystal's missing data requested."""
import copy
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gap_inventory
import plan_circuits
import review_functions
from validate_review import doc_consistency_errors
from test_decoupling import add, fixture, rebind
from test_passive_stress import board, proposals


# (a) document / ordering consistency
def finding(severity, consequence, reason='订货码与 Value 冲突'):
    return {'kind': 'DEFECT', 'severity': severity, 'consequence': consequence, 'severity_reason': reason}


def test_field_mismatch_without_electrical_consequence_drops_to_p3():
    rules = {'DEV-D01'}
    assert doc_consistency_errors('F1', finding('P2', '无电气后果：Value 写 10nF、订货码 104'), rules)
    assert doc_consistency_errors('F1', finding('P3', '无电气后果：Value 写 10nF、订货码 104'), rules) == []


def test_wrong_pin_meaning_keeps_its_level_and_silence_is_refused():
    assert doc_consistency_errors('F2', finding('P1', '电气后果：符号把 HOLD# 标成 RESET#，复位线被当作保持'), {'DEV-D02'}) == []
    assert doc_consistency_errors('F3', finding('P2', 'BOM 与图不一致'), {'DOC-Q01'})
    assert doc_consistency_errors('F4', finding('P1', '输出电容不足'), {'DEV-D04', 'PWR-C04'}) == []
    assert doc_consistency_errors('F5', dict(finding('P3', 'x'), kind='IMPROVEMENT'), {'DEV-D01'}) == []


# (b) a voltage read only off a net name
def test_point_window_equal_to_the_net_name_is_name_inferred_and_confirms_no_pass():
    _, rows = proposals(*board(rails={'VCC_3V3': {'voltage_v': {'min': 3.3, 'max': 3.3}, 'citation': '原图网名 VCC_3V3'}}))
    for ref in ('R1', 'C1'):
        proposal = rows[ref]['proposal']
        assert proposal['result'] is None
        assert proposal['calculation']['rail_basis'] == '按网名推定'
        assert '按网名推定' in proposal['note'] and 'name-inferred:VCC_3V3' in proposal['bases']


def test_toleranced_or_requirement_window_is_not_name_inferred():
    _, rows = proposals(*board())
    assert rows['R1']['proposal']['result'] == 'PASS' and 'rail_basis' not in rows['R1']['proposal']['calculation']
    from checkers.passive_stress import name_inferred_rails
    assert name_inferred_rails({'power_rails': {'+36V': {'voltage_v': {'min': 36, 'max': 36}},
                                                '+5V': {'voltage_v': {'min': 4.75, 'max': 5.25}},
                                                'VBUS': {'voltage_v': {'min': 5, 'max': 5}},
                                                '+12V': {'voltage_v': {'requirement': 'REQ-1', 'min': 12, 'max': 12}}}}) == {'+36V'}


# (c) relaxed connection gate vs. the crystal's own data
def crystal_board(value):
    db, intent = fixture(('100nF',))
    add(db, 'Y1', value, [('1', '1', 'XI'), ('2', '2', 'XO')])
    db['parts']['Y1']['prim'] = 'Device:Crystal'
    for ref, net in (('C8', 'XI'), ('C9', 'XO')):
        add(db, ref, '10pf', [('1', '1', net), ('2', '2', 'GND')])
    intent['assemblies'][0]['population'] = {r: True for r in db['parts']}
    rebind(db, intent)
    return db, intent


def crystal_rows(value):
    from plan_review import build_review_plan
    plan = build_review_plan(*crystal_board(value))
    return plan, [c for c in plan['checks'] if c['rule'] == 'CLK-C01' and 'Y1' in json_refs(c)]


def json_refs(c):
    obj = c.get('object', {})
    return [obj.get('ref')] + list(obj.get('refs') or [])


def test_crystal_data_gaps_read_the_value_fields_and_ordering_code():
    assert len(plan_circuits.crystal_data_gaps('Y1', {'value': 'Crystal_GND24'})) == 2
    assert [g for g in plan_circuits.crystal_data_gaps('Y1', {'value': '16MHz'}) if 'CL' in g]
    assert plan_circuits.crystal_data_gaps('Y1', {'value': '16MHz', 'fields': {'MPN': 'ABM8-16.000MHZ-B2-T'}}) == []
    assert plan_circuits.crystal_data_gaps('Y1', {'value': '32.768kHz 12.5pF'}) == []


def connection_function():
    """FN-IF-CLOCK-Y1 traced only: a netlist fact and the MCU pin table, no numeric clause."""
    return {'functions': [{'id': 'FN-IF-CLOCK-Y1', 'question': 'Y1 两端接到 U1 的 XI/XO 吗',
                           'objects': {'refs': ['Y1', 'U1'], 'nets': ['XI', 'XO']},
                           'conditions': [{'id': 'N1', 'kind': 'NETLIST_FACT', 'source': 'db.json', 'locator': 'nets XI/XO',
                                           'says': 'Y1.1=XI=U1.XI，Y1.2=XO=U1.XO', 'use': '方向', 'nets': ['XI', 'XO']},
                                          {'id': 'P1', 'kind': 'TYPICAL_REFERENCE', 'source': 'ds/U1.pdf',
                                           'locator': 'p12 pin description', 'says': 'XI 晶振输入，XO 晶振输出',
                                           'use': '方向'}],
                           'judgements': [{'aspect': '接口方向语义', 'says': '两端按官方语义对应', 'conditions': ['N1', 'P1']}],
                           'no_calculation_reason': '只核连接'}]}


def f1(report, **kw):
    return [e for e in review_functions.function_errors(report, **kw) if 'no clause carries the verdict' in e]


def test_relaxed_gate_passes_a_traced_crystal_interface_but_its_missing_data_is_still_requested():
    report = connection_function()
    assert f1(copy.deepcopy(report))                                     # not a connection-only function: F1 holds
    assert f1(copy.deepcopy(report), connection_only={'FN-IF-CLOCK-Y1'}) == []   # T-only: netlist + pin table carry it
    plan, rows = crystal_rows('Crystal_GND24')
    assert rows and all(r['readiness'] == 'WAITING_EVIDENCE' for r in rows)
    needs = {k for r in rows for k in r['required_inputs']}
    assert any('标称频率' in k for k in needs) and any('负载电容' in k for k in needs)
    asked = [e for e in gap_inventory.build(plan)['by_owner']['part_data'] if 'Y1' in e['refs']]
    inputs = {k for e in asked for k in e['inputs']}
    assert any('Y1 晶体标称频率' in k for k in inputs) and any('Y1 晶体负载电容' in k for k in inputs)


def test_relaxed_gate_needs_both_the_netlist_fact_and_the_pin_table():
    report = connection_function()
    report['functions'][0]['conditions'][1]['locator'] = 'p3 features'
    assert f1(report, connection_only={'FN-IF-CLOCK-Y1'})

"""Real-board failure patterns, with small synthetic counterexamples."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
from solve_dividers import parse_resistor
from parse_kicad import parse
from test_parse_kicad import comp, net, netlist

@pytest.mark.parametrize('text,ohm', [('0R',0),('0R01',.01),('0R001',.001),('4K7',4700),('10R',10),('1M',1e6),('R_0R001_0805',.001),('R_0R_22.4A_0603',0),('R_4K7_0402',4700)])
def test_board_resistance(text, ohm):
    assert parse_resistor(text)['kohm'] * 1000 == pytest.approx(ohm)

@pytest.mark.parametrize('text', ['R_unknown_0402','R_0R_bad_0402','CR1206-J/-000ELF','R_0R001_9999'])
def test_unknown_resistance_stays_unknown(text):
    assert parse_resistor(text) is None

def test_native_val_and_all_fields_retained():
    xml=netlist(comp('R1','Device','R','R_0R_0402', fields='<field name="Val">0R01</field><field name="Voltage">50V</field><field name="Tolerance">1%</field><field name="MPN">X123</field>'),net('A',('R1','1','','passive'))+net('B',('R1','2','','passive')))
    part=parse(xml)['parts']['R1']
    assert part['value']=='0R01' and part['original_value']=='R_0R_0402'
    assert part['fields']=={'Val':'0R01','Voltage':'50V','Tolerance':'1%','MPN':'X123'}
    assert part['part']=='X123'
    assert part['value_provenance']=={'field':'Val','raw':'0R01','method':'literal-RKM','ohm':.01}
    unknown=parse(xml.replace('0R01','undecided'))['parts']['R1']
    assert unknown['value']=='undecided' and unknown['value_provenance']['ohm'] is None

from checkers.netgraph import NetGraph
from checkers.powertree import PowerTree

def supply_chain(resistance='0R01', dnp=False):
    components=(comp('U1','Regulator_Linear','LDO','LDO')
      + comp('R1','Device','R',resistance,properties='<property name="dnp"/>' if dnp else '')
      + comp('L1','Device','L','1uH')+comp('F1','Device','Fuse','Fuse')
      + comp('U2','Device','IC','IC'))
    nets=(net('SOURCE',('U1','3','VOUT','power_out'),('R1','1','','passive'))
      +net('MID',('R1','2','','passive'),('L1','1','','passive'))
      +net('FUSED',('L1','2','','passive'),('F1','1','','passive'))
      +net('VDD',('F1','2','','passive'),('U2','1','VDD','power_in')))
    return parse(netlist(components,nets))

@pytest.mark.parametrize('value',['0R','0R001','0R01','1R'])
def test_supply_trace_crosses_small_resistors_and_keeps_refs(value):
    found=PowerTree(NetGraph(supply_chain(value))).source_of('VDD')
    assert found['source']=='U1.3'
    assert found['path']==['R1','L1','F1']

@pytest.mark.parametrize('value',['1R01','10R','unknown'])
def test_supply_trace_does_not_assume_large_or_unknown_resistor_is_wire(value):
    assert PowerTree(NetGraph(supply_chain(value))).source_of('VDD') is None

def test_supply_trace_stops_at_unfitted_shunt():
    assert PowerTree(NetGraph(supply_chain(dnp=True))).source_of('VDD') is None

from lint import Lint
from plan_review import build_review_plan
from render_report import render_input_notes

@pytest.mark.parametrize('fields,properties,expected',[
 ('<field name="DNP">DNP</field>','',True),('<field name="DNP">yes</field>','',True),
 ('<field name="不贴">不贴</field>','',True),('<field name="DNP">no</field>','',False),
 ('<field name="DNP"></field>','',False),('', '<property name="DNP"/>',True),
 ('','<property name="dnp" value="false"/>',False)])
def test_native_dnp_marks(fields, properties, expected):
    db=parse(netlist(comp('R1','Device','R','10k',fields=fields,properties=properties),net('LONE',('R1','1','','input'))))
    assert db['parts']['R1']['nc'] is expected
    if expected:
        assert not [f for f in Lint(db).run() if f['rule'] in ('NET-A01','NET-A06','NET-A07','PWR-A02')]

def test_dnp_series_resistor_not_a_clamp_path_or_input_node():
    db=supply_chain(dnp=True)
    db['pintype']['R1.1']='IN'
    lint=Lint(db)
    assert 'R1.1' not in lint.pin2net
    assert '经 R1' not in lint._protected_pins_text('MID')
    assert not lint.resistor_links('SOURCE')
    assert not [f for f in lint.run() if f.get('ref')=='R1' and f['rule'].startswith(('NET-','PWR-'))]
    plan=build_review_plan(db)
    assert '未贴装器件 1 个，已排除。' in render_input_notes(plan)

import catalog
import circuit_candidates
import circuit_decisions

@pytest.mark.parametrize('kind',['I2C','SPI','UART','HSSERIAL','LEVEL_SHIFT','ETHERNET','CLOCK','CAN','RS485','DDR','STORAGE','RF','AV'])
def test_interface_candidate_states_are_nonempty(kind):
    assert catalog.CANDIDATE_STATES[kind] == ('idle','active')

def test_default_states_are_marked_unconfirmed_in_plan():
    from plan_review import ReviewPlanner
    planner=ReviewPlanner(supply_chain())
    circuit={'id':'UART1','type':'UART','refs':['U1'],'nets':[],
             'states':list(catalog.CANDIDATE_STATES['UART']), 'citation':'synthetic netlist.xml p1'}
    planner.plan_subjects(catalog.CIRCUIT_TYPE_BY_NAME['UART'],[circuit],[])
    notes=[d for d in planner.diagnostics if d['code']=='DEFAULT_CIRCUIT_STATES']
    assert notes and all('未经需求确认' in d['detail'] for d in notes)

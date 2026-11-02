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


def test_crystal_load_check_is_not_hidden_by_usb_ownership():
    db=parse(netlist(comp('Y2','Device','Crystal','ABM8G-12.000MHZ-18-D2Y-T')
                    +comp('U7','Device','IC','USB-controller'),
                    net('XI',('Y2','1','','passive'),('U7','1','OSCI','input'))
                    +net('XO',('Y2','2','','passive'),('U7','2','OSCO','output'))))
    intent={'schema_version':5,'circuits':[{'id':'USB7','type':'USB','refs':['U7','Y2'],'owned':['U7','Y2'],
             'nets':['XI','XO'],'states':['attached'],'citation':'synthetic netlist.xml p1', 'candidate_ids':['USB-U7']}]}
    checks=build_review_plan(db,intent)['checks']
    crystal=[c for c in checks if c['rule']=='CLK-C01' and c.get('object',{}).get('ref')=='Y2']
    assert len(crystal)==1 and crystal[0]['owner']['id']=='USB7'
    db['parts']['Y2']['nc']=True
    assert not any(c['rule']=='CLK-C01' and c.get('object',{}).get('ref')=='Y2' for c in build_review_plan(db)['checks'])

def test_active_oscillator_does_not_get_passive_load_check():
    db=parse(netlist(comp('Y1','Oscillator','Oscillator','MEMS-CLOCK'),
                    net('CLK',('Y1','1','OUT','output'))+net('VDD',('Y1','2','VDD','power_in'))))
    assert not any(c['rule']=='CLK-C01' and c.get('object',{}).get('ref')=='Y1' for c in build_review_plan(db)['checks'])
from lint import net_name_split
from part_words import pin_signature, classify, IC

@pytest.mark.parametrize('a,b',[('SDRAM_A0_R','SDRAM_A10_R'),('TC_JTAG_TDI','TC_JTAG_TDO'),
 ('SFP_LEDG_1V8','SFP_LEDY_1V8'),('HDMI_Audio.BCLK','HDMI_Audio.LRCLK'),('VCCOEN_PL_M2C','VCCOEN_PS_M2C')])
def test_semantic_siblings_are_not_name_splits(a,b):
    assert not net_name_split(a,b)

def test_unrelated_near_name_typo_is_still_reviewed():
    assert net_name_split('VERY_LONG_ENABLE','VERY_LONG_ENABEL')

def test_numbered_connector_contacts_are_not_a_bjt():
    assert pin_signature([('B01','1'),('C01','2'),('E01','3')]) is None
    assert classify('U1',{'part':'LTC4412','prim':'Power_Management:Ideal_Diode'},6,
                    [('GATE','5'),('SENSE','6'),('IN','1'),('CTL','3')])[0] == IC

def test_reference_starting_with_voltage_is_valid_but_question_mark_is_not():
    from board_scans import REFDES_RE
    assert REFDES_RE.fullmatch('0V6') and REFDES_RE.fullmatch('TP_VREF_1V2')
    assert not REFDES_RE.fullmatch('R?') and not REFDES_RE.fullmatch('')

def test_supply_shunt_and_signal_with_embedded_voltage_are_not_pullups():
    db=supply_chain('0R001')
    assert Lint(db).pulls('MID') == []
    db['parts']['R2']={'prim':'Device:R','part':'R','value':'10k','nc':False}
    db['pin2net'].update({'R2.1':'VDD','R2.2':'GND'})
    db['nets']['VDD'].append('R2.1');db['nets']['GND']=['R2.2']
    assert Lint(db).pulls('VDD') == []

def test_unknown_supply_resistance_is_a_dependency_not_an_open_circuit():
    f=[f for f in Lint(supply_chain('unknown')).run() if f['rule'] in ('PWR-A01','PWR-A02')]
    assert f and all(x['kind']=='CANDIDATE' and '未知阻值' in x['detail'] for x in f)

def test_enable_source_crosses_a_fitted_zero_ohm_link_only():
    from checkers.power_up import _Scan
    from checkers.states import as_built
    db=parse(netlist(comp('U1','Device','IC','REG')+comp('U2','Device','IC','LOAD')
                    +comp('R1','Device','R','0R')+comp('R2','Device','R','10k'),
                    net('EN_A',('U2','1','EN','input'),('R1','1','','passive'))
                    +net('EN_B',('R1','2','','passive'),('R2','1','','passive'))
                    +net('VDD',('R2','2','','passive'),('U1','3','VOUT','power_out'))))
    scan=_Scan(db,as_built(db)[0],{},set())
    assert scan._enable_source('EN_A',set())[0]=='pulled'
    db['parts']['R1']['nc']=True
    scan=_Scan(db,as_built(db)[0],{},set())
    assert scan._enable_source('EN_A',set())[0]=='unknown'

@pytest.mark.parametrize('model,pin',[('MAX3421EETJ+','GPIN0'),('MAX3421EETJ+','GPIN7'),('TPS2372-3RGWR','AUTCLS')])
def test_only_qualified_unused_inputs_get_internal_bias_exemption(model,pin):
    db=parse(netlist(comp('U1','Device','IC',model,fields='<field name="MPN">'+model+'</field>'),
                    net('unconnected-(U1-Pad1)',('U1','1',pin,'input+no_connect'))))
    assert not [f for f in Lint(db).run() if f['rule']=='NET-A07' and f['kind']!='INFO']
    db['parts']['U1']['part']='UNKNOWN_GPIO_IC'
    assert [f for f in Lint(db).run() if f['rule']=='NET-A07' and f['kind']=='CANDIDATE']

def test_internal_supply_provenance_precedes_a_connector_on_the_load_net():
    db=supply_chain('100R')
    db['parts']['J1']={'part':'Connector:Conn_01x01','prim':'Connector:Conn_01x01','value':'CONN','nc':False}
    db['pin2net']['J1.1']='VDD';db['nets']['VDD'].append('J1.1')
    assert PowerTree(NetGraph(db),feed=True).source_of('VDD')['source']=='U1.3'

def test_connector_and_parallel_package_terminals_are_not_two_active_outputs():
    db=parse(netlist(comp('J1','Connector','Conn_01x01','CONN')+comp('U1','Device','IC','IC'),
                    net('CLK',('J1','1','','output'),('U1','1','CLK','output'))))
    assert not [f for f in Lint(db).run() if f['rule']=='NET-A06']
    db=parse(netlist(comp('U1','Device','IC','IC'),net('RTN',('U1','1','RTN','output'),('U1','2','RTN','output'))))
    assert not [f for f in Lint(db).run() if f['rule']=='NET-A06']
    db['pinname']['U1.2']='OUT2'
    assert [f for f in Lint(db).run() if f['rule']=='NET-A06']

def test_diode_return_keeps_separate_domains_and_demotes_the_hard_ground_claim():
    from test_lint import LintTests
    db=LintTests.ground_island_db()
    db['parts']['D9']={'part':'1N4148','prim':'Device:D','value':'1N4148','nc':False}
    db['pin2net'].update({'D9.1':'GNDA','D9.2':'GND'})
    db['nets']['GNDA'].append('D9.1');db['nets']['GND'].append('D9.2')
    fs=[f for f in Lint(db).run() if f['rule']=='PWR-A03' and '孤岛' in f['name']]
    assert fs and all(f['kind']=='CANDIDATE' for f in fs)
    assert 'GNDA' in db['nets'] and 'GND' in db['nets']

def test_only_the_verified_flag_pins_form_a_wired_open_drain_net():
    db=parse(netlist(comp('U1','Device','IC','AP22615AW6-7',fields='<field name="MPN">AP22615AW6-7</field>')+comp('U2','Device','IC','SiC437AED',fields='<field name="MPN">SiC437AED</field>'),
                    net('PG',('U1','1','FLG','output'),('U2','1','PGOOD','output'))))
    assert not [f for f in Lint(db).run() if f['rule']=='NET-A06' and f['kind']!='INFO']
    db['pinname']['U1.1']='OUT'
    assert [f for f in Lint(db).run() if f['rule']=='NET-A06' and f['kind']=='FINDING']

def test_sic437_output_sense_is_not_a_power_source():
    db=parse(netlist(comp('U1','Device','IC','SIC437AED-T1-GE3',fields='<field name="MPN">SIC437AED-T1-GE3</field>')+comp('L1','Device','L','1u'),
                    net('VOUT',('U1','18','Vout','passive'),('L1','2','','passive'))
                    +net('SW',('U1','5','SW','passive'),('L1','1','','passive'))))
    found=PowerTree(NetGraph(db)).source_of('VOUT')
    assert found['source']=='U1.5' and found['path']==['L1']
    db['parts']['L1']['nc']=True
    assert PowerTree(NetGraph(db)).source_of('VOUT') is None

def test_transistor_bias_can_come_from_a_traced_supply():
    from checkers.power_switch import _Scan
    from checkers.states import as_built
    db=supply_chain('0R01')
    scan=_Scan(db,as_built(db)[0],{},set())
    assert any(d['source']=='supply-bias' and d['node']=='U1.3' for d in scan.drivers('VDD'))

def test_reset_control_stage_is_recorded_as_a_path():
    from checkers.supervision import _Scan
    from checkers.states import as_built
    db=parse(netlist(comp('U1','Device','IC','reset-controller')+comp('Q1','Transistor_BJT','NPN','NPN'),
                    net('RESET',('U1','1','RESET','output'),('Q1','1','B','input'))
                    +net('GND',('Q1','2','E','passive'))+net('LOAD',('Q1','3','C','output'))))
    scan=_Scan(db,as_built(db)[0],{},set())
    assert scan._reset_destinations('RESET','U1')==[{'node':'Q1.1','role':'control-stage'}]


def test_hyphenated_native_net_tie_carries_supply_and_enable_connectivity():
    db=supply_chain('0R005')
    db['parts']['NT1']={'prim':'antmicro:Net-Tie_2','part':'Net-Tie_2','value':'Net-Tie_2','nc':False}
    db['pin2net'].update({'R1.2':'SHUNT','NT1.1':'SHUNT','NT1.2':'MID'})
    db['nets']['MID'].remove('R1.2');db['nets']['MID'].append('NT1.2')
    db['nets']['SHUNT']=['R1.2','NT1.1']
    graph=NetGraph(db)
    assert PowerTree(graph).source_of('VDD')['path']==['R1','NT1','L1','F1']
    assert 'MID' in graph.low_resistance_peers('SHUNT')
    db['parts']['NT1']['nc']=True
    assert PowerTree(NetGraph(db)).source_of('VDD') is None


@pytest.mark.parametrize('switch_name',['SW','SW_VPP'])
def test_output_sense_feedback_does_not_make_a_buck_inductor_an_input_choke(switch_name):
    db=parse(netlist(comp('U1','Device','IC','DDR-PMIC')+comp('L1','Device','L','680n'),
                    net('VDDQ',('U1','2','VDDQSNS','input'),('L1','2','','passive'))
                    +net('SWNET',('U1','1',switch_name,'input'),('L1','1','','passive'))))
    assert PowerTree(NetGraph(db)).source_of('VDDQ')['source']=='U1.1'
    db['pinname']['U1.2']='VIN'
    assert PowerTree(NetGraph(db)).source_of('VDDQ') is None  # genuine boost input choke remains excluded


@pytest.mark.parametrize('raw,expected',[('P_{GOOD}','PGOOD'),('V_{IN}','VIN'),('~{P_{GOOD}}','PGOOD')])
def test_native_subscript_styling_does_not_change_pin_function(raw,expected):
    from part_words import pin_aliases
    aliases=pin_aliases(raw)
    assert aliases[0]==raw.upper() and expected in aliases

@pytest.mark.parametrize('model,pin',[('TPS2372-3RGWR','~{AUTCLS}'),('TXU0204BQAR','A1'),('TXU0204BQAR','B4')])
def test_native_unused_input_permissions_survive_styling(model,pin):
    db=parse(netlist(comp('U1','Device','IC',model,fields='<field name="MPN">'+model+'</field>'),
                    net('unconnected-(U1-Pad1)',('U1','1',pin,'input+no_connect'))))
    assert not [f for f in Lint(db).run() if f['rule']=='NET-A07' and f['kind']!='INFO']

def test_eeprom_org_exemption_is_only_for_the_fixed_b_variant():
    db=parse(netlist(comp('U1','Device','IC','93LC66BT-I/MC',fields='<field name="MPN">93LC66BT-I/MC</field>'),
                    net('unconnected-(U1-Pad6)',('U1','6','ORG','input+no_connect'))))
    assert not [f for f in Lint(db).run() if f['rule']=='NET-A07' and f['kind']!='INFO']
    db['parts']['U1']['part']='93LC66CT-I/MC'
    assert [f for f in Lint(db).run() if f['rule']=='NET-A07' and f['kind']=='CANDIDATE']

def test_phy_ldo_output_needs_an_actual_external_low_voltage_source():
    db=parse(netlist(comp('U1','Device','IC','KSZ9031RNXIC',fields='<field name="MPN">KSZ9031RNXIC</field>')
                    +comp('U2','Device','IC','REG'),
                    net('unconnected-(U1-Pad43)',('U1','43','LDO_O','input+no_connect'))
                    +net('LOW_SUPPLY',('U1','7','DVDDL','power_in'),('U2','1','VOUT','power_out'))))
    assert not [f for f in Lint(db).run() if f['rule']=='NET-A07' and f['kind']!='INFO']
    db['parts']['U2']['nc']=True
    assert [f for f in Lint(db).run() if f['rule']=='NET-A07' and f['kind']=='CANDIDATE']

def test_fixed_push_pull_mpsse_segment_is_not_declared_an_open_drain_bus_by_its_name():
    db=parse(netlist(comp('U26','Device','IC','FT4232HL-REEL',fields='<field name="MPN">FT4232HL-REEL</field>')
                    +comp('U30','Device','IC','TXU0304APWR',fields='<field name="MPN">TXU0304APWR</field>'),
                    net('/Debug/I2C_SDA_OUT',('U26','1','ADBUS1','bidirectional'),('U30','2','A1','input'))))
    assert not [f for f in Lint(db).run() if f['rule']=='SIG-A03' and f['kind']!='INFO']
    db['parts']['U30']['part']='UNKNOWN_BUFFER'
    assert [f for f in Lint(db).run() if f['rule']=='SIG-A03' and f['kind']=='CANDIDATE']

def test_poe_vss_rtn_are_separate_return_domains_not_an_instruction_to_short_them():
    db=parse(netlist(comp('IC1','Device','IC','TPS2378DDAR',fields='<field name="MPN">TPS2378DDAR</field>')
                    +comp('J1','Connector','Conn_01x03','CONN'),
                    net('VSS_POE_IN',('IC1','4','VSS','power_in'))
                    +net('GNDD',('IC1','5','RTN','power_out'))
                    +net('GND',('J1','1','','passive'),('J1','2','','passive'),('J1','3','','passive'))))
    findings=[f for f in Lint(db).run() if f['rule']=='PWR-A03']
    assert not [f for f in findings if 'VSS 球未入地'==f['name']]
    assert findings and all(f['kind']=='CANDIDATE' for f in findings)
    assert 'VSS_POE_IN' in db['nets'] and 'GNDD' in db['nets']

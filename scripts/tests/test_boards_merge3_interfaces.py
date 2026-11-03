"""Passive crystal case pads and actual IC endpoints beyond series resistors."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_intent
from interfaces import derive, Deriver
from plan_review import build_review_plan
from test_boards_merge2b_roles import empty
from test_inductive_load import add


def series_board():
    db=empty()
    add(db,'U1','MCU',[('1','TX','TX'),('2','VCCIO','IO_A'),('3','VCORE','CORE_A'),('4','GND','GND')])
    add(db,'R1','100R',[('1','','TX'),('2','','RX')]);add(db,'U2','MCU',[('1','RX','RX'),('2','VDD','IO_B'),('3','DEC1','CORE_B'),('4','GND','GND')])
    db['native_pintype']={'U1.2':'power_in','U1.3':'power_in','U2.2':'power_in','U2.3':'power_in'}
    db['pintype'].update({'U1.1':'OUT','U2.1':'IN'})
    i={'circuits':[{'id':'A','type':'UART','refs':['U1','R1'],'citation':'fixture boundary','states':['run'],'nets':[]},{'id':'B','type':'UART','refs':['U2'],'citation':'fixture boundary','states':['run'],'nets':[]}],
       'power_rails':{n:{'citation':'fixture source'} for n in ['IO_A','IO_B','CORE_A','CORE_B']}}
    return db,i


def test_series_endpoints_carry_actual_supply_and_path_and_get_cross_domain_question():
    db,i=series_board();d=Deriver(db,i);e=d.net_entry('TX',d.endpoints('TX','TEST'))
    assert e['cross_supply'] and e['series_endpoints'][0]['pin']=='U2.1'
    assert e['series_endpoints'][0]['supply']==['IO_B'] and e['series_endpoints'][0]['series_parts']==['R1']
    assert next(x for x in e['endpoints'] if x['pin']=='U1.1')['supply']==['IO_A']
    p=build_review_plan(db,dict(i,input_sha256=board_intent.input_fingerprint(db)))
    rows=[x for x in p['checks'] if x['rule']=='SIG-C08' and x['object'].get('net')=='TX']
    assert rows and any(x['pin']=='U2.1' for x in rows[0]['object']['series_endpoints'])


def test_core_voltage_difference_does_not_manufacture_an_io_domain_difference():
    db,i=series_board();db['pin2net']['U2.2']='IO_A';db['nets']['IO_B'].remove('U2.2');db['nets']['IO_A'].append('U2.2')
    d=Deriver(db,i);e=d.net_entry('TX',d.endpoints('TX','TEST'))
    assert not e['cross_supply']
    assert d.signal_supply('U1')==d.signal_supply('U2')==['IO_A']


def test_declared_rail_and_dnp_resistor_stop_signal_walk():
    db,i=series_board();i['power_rails']['RX']={'citation':'this net is a supplied bias rail'}
    assert not Deriver(db,i).series_ends('TX')
    db,i=series_board();db['parts']['R1']['nc']=True
    assert not Deriver(db,i).series_ends('TX')


def test_grounded_crystal_case_power_in_is_not_an_active_oscillator_supply():
    db=empty();add(db,'Y1','Crystal_GND24',[('1','1','XTAL1'),('2','GND','GND'),('3','3','XTAL2'),('4','CASE','GND')])
    db['native_pintype']={'Y1.2':'power_in','Y1.4':'power_in'}
    assert any(c['rule']=='CLK-C01' and c['object'].get('ref')=='Y1' for c in build_review_plan(db)['checks'])
    db['pinname']['Y1.4']='VDD';db['pin2net']['Y1.4']='3V3';db['nets']['GND'].remove('Y1.4');db['nets']['3V3']=['Y1.4']
    assert not any(c['rule']=='CLK-C01' and c['object'].get('ref')=='Y1' for c in build_review_plan(db)['checks'])

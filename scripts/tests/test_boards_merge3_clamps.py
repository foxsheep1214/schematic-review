"""Array channels and floating returns never turn into trip thresholds."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_inductive_load import add
from test_boards_merge2b_roles import empty
import protective_clamps as pc
from checkers.netgraph import NetGraph
from lint import Lint
from plan_review import build_review_plan


def board(model, nets):
    db=empty(); add(db,'D1',model,[(str(i),'',n) for i,n in enumerate(nets,1)])
    for i,n in enumerate(sorted(set(nets)-{'GND'}),1):
        add(db,f'J{i}','CONN_01X01',[('1','',n)])
    return db


def test_tpd4_nc_layout_pads_do_not_create_extra_channels():
    db=board('TPD4E05U06QDQARQ1',['A','B','GND','C','D','D','C','GND','B','A'])
    cs=pc.channels('D1',db['parts']['D1'],NetGraph(db))
    assert len(cs)==4 and {tuple(c['nets']) for c in cs}=={('A',),('B',),('C',),('D',)}
    assert all(c['nc_pins']==['10','6','7','9'] and c['return_pins']==['3','8'] for c in cs)
    fs=[f for f in Lint(db).run() if f['rule']=='PRO-E02']
    assert len(fs)==4
    plan=build_review_plan(db,lint_findings=fs)
    rows=[r for r in plan['checks'] if r['rule']=='PRO-E02']
    assert len(rows)==4 and len({r['id'] for r in rows})==4
    assert {tuple(r['object']['nets']) for r in rows}=={('A',),('B',),('C',),('D',)}
    assert not [r for r in plan['checks'] if r['rule']=='PRO-C02' and r['object'].get('ref')=='D1']


def test_usb_flow_through_has_one_object_with_both_physical_line_ends():
    db=board('USBLC6-2SC6',['USB_DM','GND','USB_DP','HOST_DP','VBUS','HOST_DM'])
    cs=pc.channels('D1',db['parts']['D1'],NetGraph(db))
    assert len(cs)==3
    assert next(c for c in cs if c['channel']=='1-6')['nets']==['HOST_DM','USB_DM']
    assert next(c for c in cs if c['channel']=='3-4')['pins']==['3','4']
    assert next(c for c in cs if c['channel']=='5')['nets']==['VBUS']


def test_sp1001_unused_channel_not_counted_and_low_vrwm_contract_is_per_line():
    db=board('SP1001-04XTG',['+5V','GND','unconnected-(D1-Pad3)','DP','DM'])
    cs=pc.channels('D1',db['parts']['D1'],NetGraph(db))
    assert len(cs)==3
    # The model pin table supplies topology only. A low VRWM scenario remains
    # a per-line question, never an invented numeric PASS.
    intent={'power_rails':{'+5V':{'voltage_v':{'min':4.75,'max':5.25},'citation':'synthetic source contract'}}}
    fs=[f for f in Lint(db,intent=intent).run() if f['rule']=='PRO-E02']
    assert len(fs)==3 and all('VRWM' in f['detail'] for f in fs)


def test_verified_tvs_kind_is_sufficient_even_when_symbol_words_are_generic():
    db=board('SM3.3H-TP',['A','B','GND']);db['parts']['D1']['part']='2BZX84Cxx'
    db['device_kinds']={'D1':{'kind':'tvs','citation':'MCC p1'}}
    assert len(pc.channels('D1',db['parts']['D1'],NetGraph(db)))==2
    db['parts']['D1']['nc']=True
    assert pc.channels('D1',db['parts']['D1'],NetGraph(db))==[]


def test_floating_rail_tvs_is_differential_but_switch_energy_clamp_stays_threshold():
    db=board('SMAJ58A',['LOCAL_PLUS','LOCAL_MINUS'])
    assert len(pc.channels('D1',db['parts']['D1'],NetGraph(db)))==1
    add(db,'U1','CONTROLLER',[('1','SW','LOCAL_PLUS'),('2','GND','LOCAL_MINUS')])
    assert not pc.channels('D1',db['parts']['D1'],NetGraph(db))


def test_unknown_array_pinout_keeps_port_review_without_inventing_trip_thresholds():
    db=board('TVS array unknown',['A','B','C','D','GND'])
    assert not pc.channels('D1',db['parts']['D1'],NetGraph(db))
    plan=build_review_plan(db)
    assert any(r['rule']=='PRO-D03' for r in plan['checks'])
    assert any(r['rule']=='DEV-D02' and r['object'].get('ref')=='D1' for r in plan['checks'])
    assert not [r for r in plan['checks'] if r['rule']=='PRO-C02' and r['object'].get('ref')=='D1']


def test_signal_transformer_does_not_suppress_a_verified_port_tvs_channel():
    db=board('GBLC03C',['GND','ETH_LINE']);db['device_kinds']={'D1':{'kind':'tvs','citation':'GBLC03 manufacturer p1'}}
    add(db,'T1','TRANSFORMER',[('1','AA','ETH_LINE'),('2','AB','ETH_OTHER'),('3','BA','PORT_A'),('4','BB','PORT_B')])
    assert len(pc.channels('D1',db['parts']['D1'],NetGraph(db)))==1
    # A real switch on the winding restores the energy-clamp window.
    add(db,'Q1','NMOS',[('1','G','GATE'),('2','D','ETH_LINE'),('3','S','GND')])
    assert not pc.channels('D1',db['parts']['D1'],NetGraph(db))

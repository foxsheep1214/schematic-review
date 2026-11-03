"""Mechanical artifacts and one exact logic pin table do not become active circuits."""
import sys,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
import part_words as pw
import circuit_candidates as cc
import board_intent
from checkers.netgraph import NetGraph
from checkers.powertree import PowerTree
from test_boards_merge2b_roles import empty
from test_inductive_load import add
from plan_review import build_review_plan
from plan_circuits import _feature_hits
import interfaces


@pytest.mark.parametrize('foot',['MountingHole:MountingHole_3.2mm_M3_DIN965_Pad','Fiducial:Fiducial_1mm','Graphic:Logo_ABC'])
def test_mechanical_footprint_does_not_trigger_industrial_di_or_debug(foot):
    db=empty();db['parts']['H1']={'part':'DIN965','value':'DIN965','prim':'custom:MARK','jedec':foot,'nc':False}
    c=cc.build(db)
    assert not [x for x in c['candidates'] if x['type']=='DEBUG']
    assert not _feature_hits(db,r'DIN|INDUSTRIAL')
    p=build_review_plan(db)
    assert not [x for x in p['checks'] if x['rule']=='DEV-C01' and 'H1' in str(x['object'])]


def test_plated_mounting_pad_keeps_ground_but_is_not_a_debug_probe():
    db=empty();add(db,'H1','DIN965',[('1','','GND')]);db['parts']['H1']['jedec']='MountingHole:MountingHole_3.2mm_M3_DIN965_Pad'
    assert NetGraph(db).is_fitted('H1') and NetGraph(db).kind('H1')==pw.TESTPOINT
    assert not [x for x in cc.build(db)['candidates'] if x['type']=='DEBUG']
    add(db,'TP1','TestPoint',[('1','','SIG')]);db['parts']['TP1']['jedec']='TestPoint:TestPoint_Pad_D1.0mm'
    assert any('TP1' in [m['ref'] for m in x['members']] for x in cc.build(db)['candidates'] if x['type']=='DEBUG')


def test_real_industrial_port_survives_and_resistor_din_package_is_only_a_standard():
    db=empty();add(db,'J1','CONN_01X02',[('1','DI','DI_24V'),('2','GND','GND')]);add(db,'R1','10k',[('1','','DI_24V'),('2','','IN')]);db['parts']['R1']['jedec']='Resistor_THT:R_Axial_DIN0309_L9.0mm'
    hits=_feature_hits(db,r'DIN|DI_24V')
    assert any('DI_24V' in h for h in hits) and not any('DIN0309' in h for h in hits)


@pytest.mark.parametrize('model',['HYC77-TF09-200','FH34SRJ-34S-0.5SH(50)'])
def test_k_socket_identity_is_not_a_relay(model):
    db=empty();add(db,'K23',model,[(str(i),'',f'S{i}') for i in range(1,9)])
    assert NetGraph(db).kind('K23')==pw.CONNECTOR
    db['parts']['K23'].update(part='RELAY',value='RELAY',prim='RELAY')
    assert NetGraph(db).kind('K23')==pw.RELAY


def mc_board():
    db=empty();outs={3,4,10,11};names={i:('VSS' if i==7 else 'VDD' if i==14 else f'OUT{i}' if i in outs else f'IN{i}') for i in range(1,15)}
    add(db,'U9','MC14093BDTR2G',[(str(i),names[i],'GND' if i==7 else '3V3' if i==14 else f'N{i}') for i in range(1,15)])
    db['native_pintype']={f'U9.{i}':'output' for i in range(1,15)};db['pintype']={f'U9.{i}':'OUT' for i in range(1,15)}
    return db


def test_exact_mc14093_official_directions_keep_native_data_and_evidence():
    db=mc_board();original=copy.deepcopy(db);g=NetGraph(db)
    assert g.pintype['U9.1']=='IN' and g.pintype['U9.3']=='OUT'
    assert g.native_pintype['U9.7']=='power_in' and g.native_pintype['U9.14']=='power_in'
    assert 'MC14093B/D' in g.pin_type_sources['U9.1']['citation']
    assert db==original
    d=interfaces.Deriver(db,{})
    assert d.role('U9.1')[0]==interfaces.RECEIVER and d.role('U9.3')[0]==interfaces.DRIVER
    p=build_review_plan(db)
    assert any(x['code']=='MANUFACTURER_PIN_DIRECTIONS' for x in p['diagnostics'])
    db['parts']['U9']['part']='UNKNOWN'
    assert NetGraph(db).pintype['U9.1']=='OUT'


def test_official_direction_does_not_hide_vdd_wired_to_ground():
    db=mc_board();db['nets']['3V3'].remove('U9.14');db['nets']['GND'].append('U9.14');db['pin2net']['U9.14']='GND'
    from lint import Lint
    assert any(f['rule']=='PWR-A02' and 'U9.14' in f['detail'] for f in Lint(db).run())


def test_nt_only_and_footprint_only_copper_ties_carry_power_and_gate_sources():
    for ref,prim,foot in [('NT1','Device:UNKNOWN',''),('X1','Device:UNKNOWN','NetTie:NetTie-2_SMD_Pad0.5mm')]:
        db=empty();add(db,'U1','DRIVER',[('1','VOUT','SOURCE')]);add(db,ref,'UNKNOWN',[('1','','SOURCE'),('2','','LOAD')]);db['parts'][ref].update(prim=prim,jedec=foot,nc=True)
        g=NetGraph(db)
        assert PowerTree(g).source_of('LOAD')['source']=='U1.1'
        assert 'SOURCE' in g.signal_source_peers('LOAD')


def test_memory_card_socket_does_not_supply_its_own_power_rail():
    db=empty();add(db,'K8','HYC77-TF09-200',[('4','VDD','CARD_POWER'),('6','GND','GND')]);add(db,'U1','IC',[('1','VDD','CARD_POWER')])
    assert PowerTree(NetGraph(db),feed=True).source_of('CARD_POWER') is None


def test_zero_electrical_pin_active_placeholder_gets_no_passive_stress_object():
    db=empty();db['parts']['U7']={'part':'MCU','value':'MCU','prim':'IC','nc':False}
    p=build_review_plan(db)
    assert not [c for c in p['checks'] if c['rule']=='DEV-C01' and 'U7' in str(c['object'])]

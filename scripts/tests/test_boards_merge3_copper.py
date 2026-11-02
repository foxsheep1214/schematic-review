"""DNP procurement marks cannot remove fabricated net ties or probe copper."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_boards_merge2b_roles import empty
from test_inductive_load import add
from checkers.netgraph import NetGraph
from checkers import states
from lint import Lint
import board_intent
from i2c_topology import build_i2c_topology


def board():
    db=empty();add(db,'U1','MCU',[('1','INPUT','ADDR'),('2','INPUT','PROBE')])
    add(db,'NT901','NetTie_2',[('1','','ADDR'),('2','','+3V3')])
    db['parts']['NT901'].update(nc=True,prim='Device:NetTie_2',jedec='NetTie:NetTie-2_SMD_Pad0.5mm')
    add(db,'TP1','TEST-POINT',[('1','','PROBE')]);db['parts']['TP1'].update(nc=True,jedec='TestPoint:TestPoint_Pad_D1.0mm')
    add(db,'R1','0R',[('1','','REAL_DNP'),('2','','+3V3')]);db['parts']['R1'].update(nc=True,jedec='Resistor_SMD:R_0402_1005Metric')
    return db


def test_copper_survives_dnp_but_a_removable_zero_ohm_resistor_does_not():
    db=board();graph=NetGraph(db)
    assert graph.is_fitted('NT901') and graph.is_fitted('TP1') and not graph.is_fitted('R1')
    assert graph.kind('NT901')=='jumper'
    assert graph.low_resistance_peers('ADDR')['+3V3']==['NT901']
    assert db['parts']['NT901']['nc'] is True
    fs=Lint(db).run()
    assert not [f for f in fs if f['rule']=='NET-A01' and any(n in f['detail'] for n in ['ADDR','PROBE'])]


def test_copper_population_is_separate_from_explicit_cut_state():
    db=board();assembly={'id':'run','citation':'schematic p1','population':{r:False for r in db['parts']},'jumpers':{}}
    resolved=states.resolve(db,[assembly])[0]
    assert set(resolved['fitted'])=={'NT901','TP1'}
    assembly['jumpers']['NT901']='open'
    assert states.resolve(db,[assembly])[0]['fitted']==['TP1']


def test_i2c_copper_edge_and_rail_context_rebuild_identically():
    db=empty();add(db,'U1','MCU',[('1','SDA','SDA_A'),('2','SCL','SCL_A')]);add(db,'U2','SENSOR',[('1','SDA','SDA_B'),('2','SCL','SCL_B')])
    for ref,signal in [('NT1','SDA'),('NT2','SCL')]:
        add(db,ref,'NetTie_2',[('1','',signal+'_A'),('2','',signal+'_B')]);db['parts'][ref].update(nc=True,jedec='NetTie:NetTie-2_SMD_Pad0.5mm')
    add(db,'R1','4k7',[('1','','SDA_A'),('2','','VCC')]);add(db,'R2','4k7',[('1','','SCL_A'),('2','','VCC')])
    intent={'input_sha256':board_intent.input_fingerprint(db),'power_rails':{'VCC':{'citation':'schematic p1 rail'}},
            'assemblies':[{'id':'run','citation':'schematic p1','population':{r:not p.get('nc') for r,p in db['parts'].items()},'jumpers':{}}]}
    inv=build_i2c_topology(db,intent)
    assert inv['context']['power_rails']==intent['power_rails']
    rebuilt=build_i2c_topology(db,inv['context'])
    assert inv==rebuilt
    regions=inv['states'][0]['regions']
    assert any({'SDA_A','SDA_B'} <= set(r['nets']) for r in regions)
    assert any({'SCL_A','SCL_B'} <= set(r['nets']) for r in regions)

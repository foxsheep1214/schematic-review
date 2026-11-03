"""U refdes cannot turn a multi-winding magnetic into an all-pin short."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import board_intent
from checkers import domains,isolation_sides
from checkers.netgraph import NetGraph
from test_isolation_sides import empty
from test_inductive_load import add
from plan_review import build_review_plan


def test_u_trafo_is_a_magnetic_with_unknown_sides_not_an_ic_short():
    db=empty();add(db,'U1','Trafo_1',[('1','','PRI'),('2','','AUX'),('4','','GND'),('5','','SW'),('6','','SEC'),('7','','GND2')])
    graph=NetGraph(db);assert graph.kind('U1')=='transformer'
    d=domains.derive(graph)
    assert not d['conflicts'] and d['nets']['GND'] != d['nets']['GND2']
    m=next(m for m in d['barriers'] if m['ref']=='U1')
    assert m['mechanism']=='transformer' and not m['resolved'] and m['unmapped_pins']==['1','2','4','5','6','7']


def transformer():
    db=empty();add(db,'TR1','TRANSFORMER',[('1','','GND1'),('3','','SW'),('7','','VIN'),('12','','SEC')])
    intent={'devices':{'TR1':{'mpn':'DA2032-ALD','package':'custom','identity_citation':'schematic p1','citation':'Coilcraft Doc510-1 p1 winding diagram','pinout_complete':True,
        'pins':{'1':{'name':'SECONDARY_1','role':'other'},'3':{'name':'PRIMARY_3','role':'other'},'7':{'name':'PRIMARY_7','role':'other'},'12':{'name':'SECONDARY_12','role':'other'}}}}}
    return db,intent


def test_official_windings_are_available_even_to_graph_only_consumers():
    db,intent=transformer();g=NetGraph(board_intent.graph_db(db,intent));m=isolation_sides.model(g,'TR1')
    assert m['resolved'] and m['sides'][0]['pins']==['3','7'] and m['sides'][1]['pins']==['1','12']
    assert 'Doc510-1' in m['citation']


def test_passive_barrier_remains_passive_when_a_connector_spans_both_sides():
    db,intent=transformer();add(db,'J1','CONN_01X04',[('1','','VIN'),('2','','GND1'),('3','','SW'),('4','','SEC')])
    intent['circuits']=[{'id':'ISO','type':'ISOLATION','refs':['TR1','J1'],'states':['run'],'nets':[],'citation':'schematic p1'}]
    intent['input_sha256']=board_intent.input_fingerprint(db)
    plan=build_review_plan(db,intent)
    asked={c['rule'] for c in plan['checks'] if c['object'].get('circuit')=='ISO'}
    assert {'PRO-D02','PRO-C03'} <= asked
    assert not {'RST-T04','SIG-C09','SIG-C13','SIG-C17','PRO-C01'} & asked


def test_native_pin_name_conflict_does_not_get_silently_replaced_in_side_model():
    db,intent=transformer();db['pinname']['TR1.1']='PRIMARY_1'
    g=NetGraph(board_intent.graph_db(db,intent));m=isolation_sides.model(g,'TR1',intent)
    assert '1' in m['sides'][0]['pins'] and '1' not in m['sides'][1]['pins']
    assert g.pin_conflicts

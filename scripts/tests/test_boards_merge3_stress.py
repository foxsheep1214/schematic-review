"""Ground is a reference, never evidence of an unknown IC supply being zero."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import board_intent
from checkers.netgraph import NetGraph
from checkers.passive_stress import _Bounds, _declared_rails
from test_boards_merge2b_roles import empty
from test_inductive_load import add
from plan_review import build_review_plan
from test_derive_rows import bias_plan
import derive_rows
import results_model


def test_native_power_input_and_official_power_require_a_voltage_not_just_returns():
    db=empty();add(db,'U1','CONTROLLER',[('1','AGND','GND'),('3','VIN','/VIN'),('6','SS','SS'),('9','VCC','LOCAL_VCC')])
    db['native_pintype']={'U1.1':'power_in','U1.3':'power_in','U1.9':'output'}
    add(db,'C12','100nF',[('1','','LOCAL_VCC'),('2','','GND')]);add(db,'C13','82nF',[('1','','SS'),('2','','GND')])
    for ref in ['C12','C13']:db['parts'][ref]['jedec']='Capacitor_SMD:C_0402_1005Metric'
    intent={'power_rails':{'/VIN':{'citation':'source unknown'},'LOCAL_VCC':{'citation':'internal rail unknown'},'GND':{'citation':'return','voltage_v':{'min':0,'max':0}}}}
    intent['devices']={'U1':{'mpn':'CONTROLLER','package':'custom','identity_citation':'fixture p1','citation':'manufacturer p1 pin table',
        'pinout_complete':True,'pins':{p:{'name':n,'role':role} for p,n,role in [('1','AGND','return'),('3','VIN','power'),('6','SS','other'),('9','VCC','power')]}}}
    intent['assemblies']=[{'id':'run','citation':'fixture p1 assembly','population':{ref:True for ref in db['parts']},'jumpers':{}}]
    intent['input_sha256']=board_intent.input_fingerprint(db)
    bounds=_Bounds(NetGraph(board_intent.graph_db(db,intent)),_declared_rails(intent))
    for net in ['SS','LOCAL_VCC']:
        value,gap,_=bounds.window(net)
        assert value is None and 'power_rails.' in gap
    plan=build_review_plan(db,intent)
    for row in plan['checks']:
        if row['rule']=='DEV-C01' and row['object'].get('ref') in ['C12','C13']:
            assert row['proposal']['result'] is None
            assert 'power_rails.' in row['proposal']['note']
    group_rows=[c for c in plan['checks'] if c['rule']=='PWR-C10' and c['object'].get('net')=='LOCAL_VCC']
    assert group_rows and all(c.get('proposal',{}).get('result') is None for c in group_rows)
    intent['power_rails']['/VIN']['voltage_v']={'min':18,'max':24}
    # VCC is still unknown even when VIN is known: don't use VIN as a zero or
    # assumed internal-regulator model.
    assert _Bounds(NetGraph(db),_declared_rails(intent)).window('SS')[0] is None


def test_an_rc_island_connected_only_to_ground_has_no_source_bound():
    db=empty();add(db,'C1','100nF',[('1','','FLOAT'),('2','','GND')])
    assert _Bounds(NetGraph(db),{}).window('FLOAT')[0] is None


def test_proposal_override_survives_derive_materialize_strip_and_readback():
    p,r,_=bias_plan();key='PWR-C03.BIAS-RUN.Q2'
    override={'code':'STRESS_ABOVE_BOUND','reason':'independently bounded source exceeds provisional cluster'}
    r['checks'].append({'id':key,'proposal_override':override})
    view,errors=results_model.materialize(p,r)
    assert errors==[]
    row=next(c for c in view['checks'] if c['id']==key)
    assert row['proposal_override']==override
    stripped,_,_=results_model.strip_derived(view)
    assert next(c for c in stripped['checks'] if c['id']==key)=={'id':key,'proposal_override':override}
    again,errors=results_model.materialize(p,stripped)
    assert not errors and next(c for c in again['checks'] if c['id']==key)['proposal_override']==override

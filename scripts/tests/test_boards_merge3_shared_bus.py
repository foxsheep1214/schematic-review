"""Recovered MOS roles must not make a common bus capacitor exclusive to three phases."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_inductive_load import add
from test_boards_merge2b_roles import empty
from circuit_candidates import Generator, shared_supply_refs


def test_three_phases_reference_shared_bus_caps_without_owning_the_voltage_divider_as_snubbers():
    db=empty();add(db,'C1','470uF',[('1','','VBAT'),('2','','GND')]);add(db,'R1','10k',[('1','','VBAT'),('2','','SENSE')]);add(db,'C2','3.3nF',[('1','','SENSE'),('2','','GND')])
    g=Generator(db)
    assert 'VBAT' in g.supplies
    for phase in ['A','B','C']:
        g.new(phase,'POWER_CONVERTER','U'+phase,None)
        bus=g.switch_passives(phase,{'id':phase,'drain_net':'VBAT','snubbers':[{'ref':'C1','type':'capacitor'},{'ref':'R1+C2','type':'rc-snubber'}]})
        assert bus=='VBAT'
        g.walk(phase,[('QA1.2','VBAT')],{bus},4)
        members=g.candidates[phase]['members']
        assert members['C1']['role']=='input_capacitor'
        assert 'C2' not in members and 'R1' not in members
    public=[dict(c,members=list(c['members'].values())) for c in g.candidates.values()]
    assert shared_supply_refs(public)=={'C1'}
    # Real switching-node evidence must keep the snubber, even on a stop net.
    g.new('SW','POWER_CONVERTER','U4',None)
    g.switch_passives('SW',{'id':'SW','drain_net':'VBAT','switch_node_evidence':['inductive:L1'],
                          'snubbers':[{'ref':'R1+C2','type':'rc-snubber'}]})
    assert g.candidates['SW']['members']['C2']['role']=='snubber'


def test_external_high_side_switches_keep_the_second_common_bus_as_a_boundary():
    import circuit_candidates as cc
    import circuit_decisions as cd
    from test_boards_merge2a import three_bucks
    db,(intent,audit)=three_bucks()
    for i in range(1,4):
        node=f'U{i}.3';db['pinname'][node]='HVG';db['pintype'][node]='OUT'
        add(db,f'Q{i}','NMOS',[('1','G',f'SW{i}'),('2','D','VBAT'),('3','S',f'PHASE{i}')])
        db['pin2net'][f'L{i}.1']=f'PHASE{i}';db['nets'][f'SW{i}'].remove(f'L{i}.1');db['nets'][f'PHASE{i}'].append(f'L{i}.1')
    add(db,'C88','470uF',[('1','','VBAT'),('2','','GND')]);add(db,'R88','10k',[('1','','VBAT'),('2','','SENSE')]);add(db,'C89','3.3nF',[('1','','SENSE'),('2','','GND')])
    from board_intent import input_fingerprint
    intent['input_sha256']=input_fingerprint(db)
    c=cc.build(db,intent,audit);converters=[x for x in c['candidates'] if x['type']=='POWER_CONVERTER']
    assert len(converters)==3
    for x in converters:
        members={m['ref']:m for m in x['members']}
        assert members['C88']['role']=='input_capacitor'
        assert 'R88' not in members and 'C89' not in members
        assert x['nets'].get('switch')!='VBAT'
    _,errors=cd.derive(c,[{'decision':'accept','candidate':x['id']} for x in c['candidates']])
    assert not errors

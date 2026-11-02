"""Adjudicated seeds use corrected paired baselines and retain their source contracts."""
import copy
import importlib.util
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'evals/seeded_bench')]
import mutators
import pytest


def board():
    db={'parts':{},'nets':{},'pin2net':{},'pinname':{},'pintype':{},'native_pintype':{},
        'pseudo_nets':['unconnected-(U36-Pad13)'],'no_connect_nodes':['U36.13']}
    def part(ref,model,value,pins,prim=None):
        db['parts'][ref]={'prim':prim or 'Device:'+model,'part':model,'value':value,'nc':False}
        for pin,name,net in pins:
            node=ref+'.'+pin;db['pin2net'][node]=net;db['pinname'][node]=name
            db['pintype'][node]='IN' if ref=='U36' else 'UNSPEC'
    part('D54','TPD1E0B04DPYR','TPD1E0B04',[('1','K','5V'),('2','A','GND')])
    part('D22','PTVS9V0S1UR,115','PTVS9V0S1UR',[('1','K','USB_VBUS'),('2','A','GND')])
    for ref in ('C139','C140'):
        part(ref,'C1005X6S1A105K050BC','1u',[('1','','GND'),('2','','USB_VBUS')], 'Device:C')
    part('R199','CR1206-J/-000ELF','0R005',[('1','','SHUNT_IN'),('2','','SHUNT_OUT')], 'Device:R')
    for ref in ('U19','U20'):
        part(ref,'PAC1954T-E/4MX','PAC1954',[('4','SCL','SCL_3V3'),('5','SDA','SDA_3V3'),('6','ADDRSEL','3V3_SYS')])
    part('U36','74LCX07BQX','74LCX07',[('13','A5','unconnected-(U36-Pad13)'),('12','O5','NC_OUT')])
    part('Y2','ABM8G-12.000MHZ-18-D2Y-T','12MHz',[('1','','XI'),('2','','XO')],'Device:Crystal')
    for ref,net in [('C190','XI'),('C193','XO')]:
        part(ref,'C','18p',[('1','','GND'),('2','',net)],'Device:C')
    return mutators.rebuild(db)


def test_every_adjudicated_seed_is_present_with_a_contract_and_input_is_unchanged():
    db=board();original=copy.deepcopy(db);found=list(mutators.board_mutations(db))
    assert len(found)==7
    assert {m.defect for m in found}=={'D-TVS-VRWM','D-MLCC-RATING-BELOW-PD','D-SHUNT-MPN-CONFLICT',
                                     'D-I2C-ADDRESS-COLLISION','D-CMOS-UNUSED-IN-FLOAT','D-XTAL-LOAD'}
    assert all(m.contract.get('source') for m in found)
    assert all(m.baseline is not None for m in found if m.defect!='D-XTAL-LOAD')
    assert db==original
    for m in found:
        for case in [m.db]+([m.baseline] if m.baseline is not None else []):
            assert mutators.rebuild(copy.deepcopy(case))['nets']==case['nets']


def test_pair_edits_preserve_address_and_nc_control_points():
    found={m.defect:m for m in mutators.board_mutations(board())}
    address=found['D-I2C-ADDRESS-COLLISION']
    assert address.baseline['pin2net']['U20.6']=='GND'
    assert address.db['pin2net']['U20.6']=='3V3_SYS'
    nc=found['D-CMOS-UNUSED-IN-FLOAT']
    assert nc.baseline['pin2net']['U36.13']=='GND'
    assert nc.db['pin2net']['U36.12']==nc.baseline['pin2net']['U36.12']
    assert 'U36.13' not in nc.baseline['no_connect_nodes']
    assert 'U36.13' in nc.db['no_connect_nodes']


def test_absent_unfitted_and_separate_bus_parts_are_not_seed_sites():
    assert list(mutators.board_mutations({'parts':{},'pin2net':{},'nets':{}}))==[]
    db=board()
    for p in db['parts'].values():p['nc']=True
    assert list(mutators.board_mutations(db))==[]
    db=board();db['pin2net']['U20.4']='OTHER_SCL';mutators.rebuild(db)
    assert not [m for m in mutators.board_mutations(db) if m.defect=='D-I2C-ADDRESS-COLLISION']
    db=board();db['parts']['R199']['value']='0R'
    assert not [m for m in mutators.board_mutations(db) if m.defect=='D-SHUNT-MPN-CONFLICT']


def test_evaluator_compares_against_the_corrected_pair_with_the_same_voltage_contract(monkeypatch):
    spec=importlib.util.spec_from_file_location('seeded_merge_run',ROOT/'evals/seeded_bench/run.py')
    runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
    calls=[]
    mutant=next(m for m in mutators.board_mutations(board()) if m.defect=='D-MLCC-RATING-BELOW-PD')
    def lint(sut,db,work,intent=None):
        calls.append((db,intent))
        detail='C139 paired clean baseline' if db is mutant.baseline else 'C139 wrong rating'
        return [{'rule':'DEV-A01','detail':detail}],[],None
    monkeypatch.setattr(runner,'lint',lint)
    monkeypatch.setattr(mutators,'board_mutations',lambda db:iter([mutant]))
    import tempfile,json
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)/'db.json';p.write_text(json.dumps(board()))
        rows,_=runner.evaluate(ROOT,[{'id':'fixture','db':str(p),'board_seeds_only':True}])
    assert calls[-2][0] is mutant.baseline and calls[-1][0] is mutant.db
    assert calls[-2][1]==calls[-1][1]==mutant.intent
    assert mutant.intent['power_rails']['USB_VBUS']['voltage_v']['max']==15
    assert mutant.contract['rating_v']==10
    assert rows[0]['auto']==['DEV-A01'] and rows[0]['paired_baseline']


def test_pair_intent_keeps_unrelated_rail_voltages_unknown(monkeypatch,tmp_path):
    spec=importlib.util.spec_from_file_location('seeded_pair_rail_run',ROOT/'evals/seeded_bench/run.py')
    runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
    db=board();db['pin2net']['U19.8']='OTHER_SUPPLY';db['pinname']['U19.8']='VDD'
    db['native_pintype']['U19.8']='power_in';mutators.rebuild(db)
    intent={'schema_version':5,'power_rails':{'USB_VBUS':{'voltage_v':{'min':15,'max':15}}}}
    original=copy.deepcopy(intent);captured={}
    def run(command,**kwargs):
        import json
        captured.update(json.loads((tmp_path/'intent.json').read_text()))
        (tmp_path/'lint.json').write_text('{"findings":[]}')
        (tmp_path/'plan.json').write_text('{"checks":[]}')
        return type('Completed',(),{'stderr':'','returncode':0})()
    monkeypatch.setattr(runner.subprocess,'run',run)
    runner.lint(ROOT,db,tmp_path,intent)
    assert captured['power_rails']['USB_VBUS']['voltage_v']['max']==15
    assert 'OTHER_SUPPLY' in captured['power_rails']
    assert 'voltage_v' not in captured['power_rails']['OTHER_SUPPLY']
    assert intent==original

def test_runtime_errors_fail_the_seed_bench(monkeypatch,tmp_path):
    spec=importlib.util.spec_from_file_location('seeded_pair_error_run',ROOT/'evals/seeded_bench/run.py')
    runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
    monkeypatch.setattr(sys,'argv',['run.py','--offline','--out',str(tmp_path/'results')])
    monkeypatch.setattr(runner,'offline_boards',lambda d:[])
    monkeypatch.setattr(runner,'evaluate',lambda sut,boards:([{'board':'fixture','defect':'D-XTAL-LOAD','site':'Y2','targets':['CLK-C01'],'error':'fixture failed'}],{}))
    assert runner.main()==1

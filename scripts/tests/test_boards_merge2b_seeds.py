"""Controlled coverage probes preserve topology and distinguish plan targets from auto findings."""
import copy
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'evals/seeded_bench')]
import mutators
from test_inductive_load import add
from test_boards_merge2b_roles import empty
from plan_review import build_review_plan


def probes():
    db=empty();add(db,'U1','AT86RF215IQ-ZU',[('43','MOSI','/PICO')]);add(db,'J1','CONN_01X01',[('28','','/PICO')]);yield db,'D-EXTERNAL-INJECTION-BYPASS'
    db=empty();add(db,'U1','CH340C',[('16','VCC','+3V3')]);add(db,'U2','SE5218',[('1','VIN','VUSB'),('5','VOUT','+3V3')]);add(db,'K1','U262-161N-4BVC11',[('A4','VBUS','PORT')]);db['parts']['K1']['prim']='Connector:USB_C';add(db,'F1','FUSE',[('1','','VUSB'),('2','','PORT')]);yield db,'D-POWER-BRANCH-BYPASS'
    db=empty();add(db,'U1','BQ27441',[('6','BAT','VCC'),('8','SRP','VCC'),('7','SRN','VSYS')]);add(db,'R6','0R01',[('1','','VCC'),('2','','VSYS')]);yield db,'D-ADC-SHUNT-RANGE'
    db=empty();add(db,'U4','BD71847AMWV-E2',[('55','MUXSW_VOUT','NVCC_SD2')]);add(db,'C113','1uF',[('2','','NVCC_SD2'),('1','','GND')]);add(db,'C54','0.22uF',[('1','','NVCC_SD2'),('2','','GND')]);yield db,'D-PMIC-OUTPUT-COUT'


def test_each_controlled_probe_has_a_paired_baseline_without_changing_its_source():
    for db,kind in probes():
        before=copy.deepcopy(db);found=list(mutators.merge2b_mutations(db))
        assert len(found)==1 and found[0].defect==kind
        m=found[0];assert m.baseline is not None and m.contract and db==before
        for candidate in (m.db,m.baseline):
            assert mutators.rebuild(copy.deepcopy(candidate))['nets']=={k:sorted(v) for k,v in candidate['nets'].items()}
        if kind=='D-POWER-BRANCH-BYPASS':assert 'R90002' in m.db['parts'] and 'R90002' not in m.baseline['parts']
        if kind=='D-ADC-SHUNT-RANGE':assert m.db['parts']['R6']['value']=='1R'
        if kind=='D-PMIC-OUTPUT-COUT':
            from decoupling import parse_capacitance
            nominal=lambda board: sum(parse_capacitance(board['parts'][r]['value']) for r in ('C113','C54'))*1e6
            assert 11 <= nominal(m.baseline) <= 33 and nominal(m.db) < 11
        plan=build_review_plan(m.db)
        assert set(m.targets) & {r['rule'] for r in plan['checks'] if any(ref in str(r['object']) for ref in m.refs)}


def test_runner_reports_a_planned_c_rule_without_counting_it_as_automatic(tmp_path,monkeypatch):
    import importlib.util,json
    spec=importlib.util.spec_from_file_location('merge2b_seed_runner',ROOT/'evals/seeded_bench/run.py')
    runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
    db,_=next(probes());m=next(mutators.merge2b_mutations(db));path=tmp_path/'board.json';path.write_text(json.dumps(db))
    monkeypatch.setattr(runner.mutators,'board_mutations',lambda _: [m])
    monkeypatch.setattr(runner,'lint',lambda *args,**kwargs: ([],[{'rule':'SIG-C08','object':{'ref':'J1'}}],None))
    records,_=runner.evaluate(ROOT,[{'id':'probe','db':str(path),'board_seeds_only':True}])
    assert records[0]['auto']==[] and records[0]['planned_targets']==['SIG-C08']

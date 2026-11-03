"""Physical merge-3 probe pairs and guards reject lost channels, zero/PASS and compensated regressions."""
import copy, importlib.util, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'evals/seeded_bench')]
import mutators
import board_intent
from test_inductive_load import add
from test_boards_merge2b_roles import empty
from plan_review import build_review_plan,rail_candidates
from lint import Lint
spec=importlib.util.spec_from_file_location('merge3_seed_runner',ROOT/'evals/seeded_bench/run.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)


def probes():
    db=empty();add(db,'U7','CDDFN10-3324P',[(str(i),'GND' if i in (3,8) else 'IO'+str(i),'GND' if i in (3,8) else 'S'+str(i)) for i in range(1,11)]);db['parts']['U7']['prim']='Device:D_TVS';yield db,'D-ARRAY-TVS-LOW-VRWM'
    db=empty();add(db,'QA1','MDP10N027',[('1','','GATE'),('2','','VBAT'),('3','','LOAD')]);db['parts']['QA1']['value']='CRST030N10N';add(db,'R1','10k',[('1','','GATE'),('2','','LOAD')]);yield db,'D-OFFICIAL-MOS-GATE-OPEN'
    db=empty();add(db,'U1','VIPer22ADIP-E',[('3','FB','FB')]);add(db,'U3','EL817',[('1','','LED'),('2','','KA'),('3','','FB'),('4','','GND')]);add(db,'R4','2.2k',[('1','','LED'),('2','','VOUT')]);yield db,'D-OFFICIAL-OPTO-FEEDBACK-OPEN'
    db=empty();add(db,'U1','LM5160DNT',[('1','GND','GND'),('3','VIN','VIN'),('9','VCC','VCC')]);add(db,'C12','1uF',[('1','','VCC'),('2','','GND')]);db['parts']['C12']['jedec']='Capacitor_SMD:C_0603_1608Metric';yield db,'D-UNKNOWN-SUPPLY-NO-PASS'


def test_all_four_probes_are_wired_to_board_runner_and_preserve_the_source():
    for db,kind in probes():
        before=copy.deepcopy(db);found=[m for m in mutators.board_mutations(db) if m.defect==kind]
        assert len(found)==1 and db==before
        m=found[0];assert m.baseline is not None and m.contract
        for candidate in [m.db,m.baseline]:
            assert mutators.rebuild(copy.deepcopy(candidate))['nets']=={k:sorted(v) for k,v in candidate['nets'].items()}
        intent=copy.deepcopy(m.intent)
        for net in rail_candidates(m.db,intent):
            intent.setdefault('power_rails',{}).setdefault(net,{'citation':'fixture supply identity; voltage deliberately withheld'})
        intent['input_sha256']=board_intent.input_fingerprint(m.db)
        plan=build_review_plan(m.db,intent,lint_findings=Lint(m.db,intent=intent).run())
        _,errors=runner.contract_guards(m.contract,plan['checks']);assert not errors
        if kind=='D-UNKNOWN-SUPPLY-NO-PASS':
            rows=[c for c in plan['checks'] if c['rule']=='DEV-C01' and c['object'].get('ref')=='C12']
            assert rows and all(not c.get('inventory_gaps') for c in rows)  # voltage unknown, assembly is confirmed
        if kind=='D-OFFICIAL-MOS-GATE-OPEN':
            assert any(f['rule']=='DRV-A03' and f.get('ref')=='QA1' for f in Lint(m.db,intent=intent).run())


def test_unknown_supply_guard_rejects_pass_and_requires_a_dependency():
    c={'guard_no_proposal_pass':['C12']}
    assert runner.contract_guards(c,[])[1]
    row={'rule':'DEV-C01','object':{'ref':'C12'},'proposal':{'result':'PASS','note':'power_rails.VIN.voltage_v'}}
    assert runner.contract_guards(c,[row])[1]
    row['proposal']['result']=None;row['proposal']['note']='0V'
    assert runner.contract_guards(c,[row])[1]
    row['proposal']['note']='missing power_rails.VIN.voltage_v'
    assert not runner.contract_guards(c,[row])[1]


def test_channel_guard_rejects_whole_package_collapsing_to_one_row():
    c={'min_channel_rows':{'ref':'U7','rule':'PRO-E02','count':4}}
    assert runner.contract_guards(c,[{'rule':'PRO-E02','object':{'ref':'U7'}}])[1]


def test_compare_is_per_site_so_a_new_hit_cannot_mask_an_old_loss():
    old={'board':'A','defect':'D','site':'U1','auto':['PRO-E02']};new=dict(old,auto=[])
    assert runner.compare_sites([new,dict(old,site='U2')],{'records':[old]})
    assert runner.compare_sites([],{'records':[old]})
    assert not runner.compare_sites([old],{'records':[old]})


def test_feedback_open_guard_requires_the_located_fault_question():
    c={'required_plan_prefix':'PRO-C01.FEEDBACK-OPEN'}
    assert runner.contract_guards(c,[])[1]
    assert not runner.contract_guards(c,[{'id':'PRO-C01.FEEDBACK-OPEN.U1-3'}])[1]

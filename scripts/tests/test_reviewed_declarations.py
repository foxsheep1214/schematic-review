"""Persist AI-derived facts; invalidate reuse on every relevant input change."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_decoupling import fixture, move_pin, rebind, ledger, mark_pass
from test_i2c_topology import add
from reviewed_declarations import capture, resolve, KEY, digest
from decoupling import build_decoupling_inventory
from plan_review import build_review_plan, validate_intent
from validate_review import validate_review


class ReviewedDeclarationsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=self.enterContext(tempfile.TemporaryDirectory())
        self.source=Path(self.tmp)/'source.txt'
        self.source.write_text('Synthetic IC pin table and bypass requirement; bridge/transformer roles.')
        self.db, complete=fixture()
        self.intent=copy.deepcopy(complete);self.intent.pop('decoupling')
        self.draft={'reviewer':{'kind':'AI','method':'Read source pin table and trace exact netlist endpoints.'},
            'sources':[{'path':str(self.source),'locator':'pin table and application'}],
            'declarations':{'decoupling':complete['decoupling']}}

    def applied(self):
        return dict(copy.deepcopy(self.intent),**{KEY:capture(self.db,self.intent,self.draft)})

    def test_round_trip_reuses_group_without_inventing_pass(self):
        bound=self.applied(); before=copy.deepcopy(bound)
        inv=build_decoupling_inventory(self.db,bound)
        self.assertEqual(inv['states'][0]['groups'][0]['fitted_capacitors'],['C1','C2'])
        self.assertEqual(inv['reviewed_declarations']['reviewer']['kind'],'AI')
        again=build_decoupling_inventory(self.db,inv['context'])
        self.assertEqual(inv,again);self.assertEqual(bound,before)
        plan=build_review_plan(self.db,bound)
        electrical=[c for c in plan['checks'] if c['rule']=='PWR-C09']
        self.assertTrue(electrical);self.assertTrue(all(c['analysis_required'] for c in electrical))
        self.assertFalse(any(c.get('review_result') == 'PASS' for c in plan['checks']))

    def test_rewiring_stays_stale_even_after_generic_input_hash_is_refreshed(self):
        bound=self.applied();move_pin(self.db,'C1.2','IO');rebind(self.db,bound)
        with self.assertRaisesRegex(ValueError,'changed'):
            build_decoupling_inventory(self.db,bound)
        self.assertTrue(validate_intent(bound,self.db))

    def test_bom_assembly_pinmap_rail_and_requirements_changes_invalidate(self):
        for kind in ['bom','assembly','pins','rail','requirement','export']:
            with self.subTest(kind=kind):
                db=copy.deepcopy(self.db);bound=self.applied()
                if kind=='bom':db['parts']['C1']['value']='10uF'
                if kind=='assembly':bound['assemblies'][0]['population']['C1']=False
                if kind=='pins':bound['devices']['U1']['pins']['1']['role']='other'
                if kind=='rail':bound['power_rails']={'VCC_3V3':{'v_max':5.0}}
                if kind=='requirement':bound['requirements']=[{'id':'R1','text':'new output'}]
                if kind=='export':db['export_errors']=['incomplete']
                rebind(db,bound)
                with self.assertRaisesRegex(ValueError,'changed'):resolve(bound,db)

    def test_source_change_and_missing_file_invalidate_even_saved_plan(self):
        bound=self.applied();plan=build_review_plan(self.db,bound);report=ledger(plan,self.db)
        self.source.write_text('Changed official pin table')
        with self.assertRaisesRegex(ValueError,'source bytes changed'):resolve(bound,self.db)
        gate=validate_review(plan,report,self.db)
        self.assertFalse(gate['valid']);self.assertTrue(any('source bytes changed' in e for e in gate['errors']))
        self.source.unlink()
        with self.assertRaisesRegex(ValueError,'readable file'):resolve(bound,self.db)

    def test_payload_tampering_and_conflicting_pin_map_rejected(self):
        bound=self.applied();bound[KEY]['declarations']['decoupling']['groups'][0]['return_nodes']=['U1.3']
        with self.assertRaisesRegex(ValueError,'modified'):resolve(bound,self.db)
        self.draft['declarations']['devices']={'U1':copy.deepcopy(self.intent['devices']['U1'])}
        self.draft['declarations']['devices']['U1']['pins']['1']['role']='other'
        with self.assertRaisesRegex(ValueError,'conflicting official'):self.applied()

    def test_new_device_pin_map_can_be_saved_but_not_conflict(self):
        self.draft['declarations']['devices']=self.intent.pop('devices')
        bound=self.applied();inv=build_decoupling_inventory(self.db,bound)
        self.assertEqual(inv['states'][0]['groups'][0]['gaps'],[])
        self.assertEqual(inv['devices'][0]['ref'],'U1')

    def test_non_ic_roles_remove_only_their_decoupling_candidates(self):
        for ref,kind in [('BR1','bridge_rectifier'),('T1','transformer')]:
            add(self.db,ref,'synthetic '+kind,[('1','VCC','RECT'),('2','GND','GND'),('3','AC','A'),('4','AC','B')])
            self.intent['assemblies'][0]['population'][ref]=True
            self.draft['declarations']['decoupling']['components'][ref]={'kind':kind,'citation':'synthetic source role table'}
        rebind(self.db,self.intent)
        cold=build_decoupling_inventory(self.db,self.intent)
        self.assertEqual(cold['unverified_device_refs'],['BR1','T1'])
        bound=self.applied();inv=build_decoupling_inventory(self.db,bound)
        self.assertEqual(inv['unverified_device_refs'],[])
        self.assertEqual([g['ref'] for g in inv['states'][0]['groups']],['U1'])
        self.assertEqual(set(inv['reviewed_declarations']['non_ic_roles']),{'BR1','T1'})
        plan=build_review_plan(self.db,bound)
        self.assertTrue(any('T1' in json.dumps(c['object']) and not c['rule'].startswith('PWR-') for c in plan['checks']))

    def test_recheck_then_capture_changed_input_recomputes_caps(self):
        old=self.applied();move_pin(self.db,'C1.2','IO');rebind(self.db,self.intent)
        with self.assertRaises(ValueError):resolve(old,self.db)
        # The test's reviewer explicitly checked the new return; capture does not infer a PASS.
        self.draft['reviewer']['method']='AI rechecked moved C1 return; no longer a local bypass.'
        new=self.applied();g=build_decoupling_inventory(self.db,new)['states'][0]['groups'][0]
        self.assertEqual(g['fitted_capacitors'],['C2'])

    def test_missing_provenance_and_verdict_fields_rejected(self):
        for field in ['sources','reviewer','verdict']:
            d=copy.deepcopy(self.draft)
            if field=='sources':d['sources']=[]
            elif field=='reviewer':d['reviewer']={'method':'no actor'}
            else:d['declarations']['verdict']='PASS'
            with self.assertRaises(ValueError):capture(self.db,self.intent,d)

    def test_cli_capture_apply_status_and_stale_do_not_write_over_inputs(self):
        root=Path(self.tmp);script=Path(__file__).resolve().parents[1]/'reviewed_declarations.py'
        for name,data in [('db',self.db),('intent',self.intent),('draft',self.draft)]:
            (root/(name+'.json')).write_text(json.dumps(data))
        def run(*args):return subprocess.run([sys.executable,'-B',str(script),*map(str,args)],capture_output=True,text=True)
        d,i,f=[root/(x+'.json') for x in ['db','intent','draft']];rec=root/'record.json';applied=root/'applied.json'
        self.assertEqual(run('capture',d,i,f,'-o',rec).returncode,0)
        self.assertEqual(run('apply',d,i,rec,'-o',applied).returncode,0)
        self.assertEqual(run('status',d,applied).returncode,0)
        before=i.read_bytes()
        self.assertEqual(run('apply',d,i,rec,'-o',i).returncode,2)
        self.assertEqual(i.read_bytes(),before)
        self.source.write_text('changed')
        self.assertEqual(run('status',d,applied).returncode,2)
        self.assertNotIn(KEY,json.loads(i.read_text()))

if __name__=='__main__':unittest.main()

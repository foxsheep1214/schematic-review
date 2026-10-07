"""Trace-jumper population and physical topology, never an electrical verdict."""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from parse_netlist import is_not_populated
from i2c_topology import build_i2c_topology,validate_i2c_intent
from test_i2c_topology import fixture,add,rebind,at
class TraceJumperTests(unittest.TestCase):
 def test_normally_closed_trace_not_dnp(self):
  self.assertFalse(is_not_populated('SparkFun-Jumpers:JUMPER-SMT_3_2-NC_TRACE:_SILK','JUMPER-SMT_3_2-NC_TRACE'))
 def test_other_nc_and_explicit_population_markers_preserved(self):
  for marker in ['NC','DNP','DNI','DNF']:
   self.assertTrue(is_not_populated('JUMPER-SMT_3_2-NC_TRACE','JUMPER-SMT_3_2-NC_TRACE/'+marker))
  self.assertTrue(is_not_populated('RES_NC_TRACE','10k'))
 def model(self):
  db,i=fixture(('33R',))
  add(db,'JP7','JUMPER-SMT_3_2-NC_TRACE',[('1','1','EXT_SDA_0'),('2','2','VCC_3V3'),('3','3','EXT_SCL_0')])
  i['i2c_topology']['components']['JP7']={'kind':'jumper','citation':'Fixture physical copper pair drawing, not source-name inference','links':[['JP7.1','JP7.2'],['JP7.2','JP7.3']]}
  i['assemblies'][0]['population']['JP7']=True;i['assemblies'][0]['jumpers']['JP7']='closed';rebind(db,i);return db,i
 def test_three_pad_links_keep_signals_separate_at_shared_rail(self):
  db,i=self.model();self.assertEqual(validate_i2c_intent(i,db),[]);out=build_i2c_topology(db,i);r=at(out)
  self.assertNotIn('EXT_SCL_0',r['nets']);self.assertNotIn('pin-role-or-model:JP7',r['gaps'])
  edge=next(e for e in r['boundaries'] if e['ref']=='JP7');self.assertEqual(edge['nodes'],['JP7.1','JP7.2']);self.assertTrue(edge['conductive'])
  self.assertNotIn('review_result',r)
 def test_open_unknown_and_missing_population_do_not_close(self):
  for state,expected in [('open','open'),(None,'jumper-state-unverified')]:
   db,i=self.model();
   if state is None: del i['assemblies'][0]['jumpers']['JP7']
   else: i['assemblies'][0]['jumpers']['JP7']=state
   edge=next(e for e in at(build_i2c_topology(db,i))['boundaries'] if e['ref']=='JP7');self.assertFalse(edge['conductive']);self.assertEqual(edge['stop_reason'],expected)
  db,i=self.model();del i['assemblies'][0]['population']['JP7'];r=at(build_i2c_topology(db,i));self.assertIn('population:JP7',r['gaps']);self.assertIn('population-unverified:JP7',r['gaps'])
 def test_no_pair_model_cannot_be_inferred_from_name(self):
  db,i=self.model();del i['i2c_topology']['components']['JP7'];self.assertIn('pin-role-or-model:JP7',at(build_i2c_topology(db,i))['gaps'])
 def test_wrong_incomplete_repeated_pair_rejected(self):
  for links in [[['JP7.1','JP7.2']],[['JP7.1','U1.1'],['JP7.2','JP7.3']],[['JP7.1','JP7.2'],['JP7.2','JP7.1'],['JP7.2','JP7.3']],[['JP7.1','JP7.1'],['JP7.2','JP7.3']]]:
   db,i=self.model();i['i2c_topology']['components']['JP7']['links']=links;self.assertTrue(validate_i2c_intent(i,db))
 def test_multiple_links_between_signal_nodes_can_expose_real_short(self):
  db,i=self.model();db['nets']['VCC_3V3'].remove('JP7.2');db['nets']['MID']=['JP7.2'];db['pin2net']['JP7.2']='MID';rebind(db,i);r=at(build_i2c_topology(db,i));self.assertIn('I2C_SCL',r['nets']);self.assertTrue(any(x.startswith('sda-scl-connected:') for x in r['gaps']))
 def test_fitted_false_remains_open_even_with_closed_state(self):
  db,i=self.model();i['assemblies'][0]['population']['JP7']=False;e=next(e for e in at(build_i2c_topology(db,i))['boundaries'] if e['ref']=='JP7');self.assertFalse(e['conductive']);self.assertEqual(e['stop_reason'],'not-fitted')
if __name__=='__main__':unittest.main()

"""Declared critical device coverage, including public D-ref bandgap reference case."""
import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from plan_review import build_review_plan
from board_intent import input_fingerprint

class DeclaredDeviceCoverageTests(unittest.TestCase):
    def db(self):
        parts={'D1':{'part':'VREF_SHUNT','value':'LM4040AIM3-2.0/NOPB','jedec':'SOT23','nc':False},'D2':{'part':'DIODE','value':'DIODE','jedec':'SOT23','nc':False},'JP1':{'part':'HEADER-1X4','value':'HEADER-1X4','jedec':'1X04','nc':False}}
        nets={'REF':['D1.1','JP1.3'],'GND':['D1.2','JP1.2'],'NC':['D1.3']}
        pins={n:net for net,ns in nets.items() for n in ns};names={'D1.1':'+','D1.2':'-','D1.3':'NC'}
        return {'parts':parts,'nets':nets,'pin2net':pins,'pinname':names,'declared_pinname':names,'pintype':{},'ref2page':{'D1':1,'JP1':1},'pseudo_nets':[]}
    def intent(self):
        return {'input_sha256':input_fingerprint(self.db()),'devices':{'D1':{'mpn':'LM4040AIM3-2.0/NOPB','package':'DBZ','identity_citation':'Exact source and manufacturer orderable','citation':'Manufacturer full physical pinout','pinout_complete':True,'pins':{str(n):{'name':name,'role':'other'} for n,name in [(1,'+'),(2,'-'),(3,'NC')]}}}}
    def test_declared_non_u_ref_gets_identity_conditions_and_disposition(self):
        plan=build_review_plan(self.db(),self.intent());ids={c['id'] for c in plan['checks']}
        self.assertTrue({'DEV-D01.D1','DEV-C05.D1','DEV-D05.D1'}<=ids)
        for cid in ['DEV-D01.D1','DEV-C05.D1','DEV-D05.D1']:
            c=next(c for c in plan['checks'] if c['id']==cid)
            self.assertEqual(c['readiness'],'WAITING_EVIDENCE');self.assertIsNone(c['review_result'])
    def test_undeclared_d_ref_not_promoted_by_reference_name(self):
        ids={c['id'] for c in build_review_plan(self.db())['checks']}
        self.assertFalse({'DEV-D01.D1','DEV-C05.D1','DEV-D05.D1','DEV-C05.D2'} & ids)
    def test_connector_declaration_does_not_duplicate_disposition(self):
        i=self.intent();i['devices']['JP1']={'mpn':'HEADER-1X4','package':'1X04','identity_citation':'Actualheaderdrawing','citation':'All4physicalpins','pinout_complete':True,'pins':{str(n):{'name':str(n),'role':'other'} for n in range(1,5)}}
        plan=build_review_plan(self.db(),i)
        self.assertEqual(len([c for c in plan['checks'] if c['rule']=='DEV-D05' and c['object'].get('ref')=='JP1']),1)
        self.assertFalse([c for c in plan['checks'] if c['rule']=='DEV-C05' and c['object'].get('ref')=='JP1'])
if __name__=='__main__':unittest.main()

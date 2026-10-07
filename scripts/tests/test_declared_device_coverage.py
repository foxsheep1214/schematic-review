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

    def critical_fixture(self, missing_symbol_pin=False):
        db=self.db();db['parts']['R7']={'part':'TRIMMER','value':'200ohm','jedec':'THREE_TERMINAL','nc':False}
        db['nets']['VIN']=['R7.2'];db['nets']['BIAS']=['R7.3'];db['nets']['unconnected-(R7-1)']=['R7.1']
        db['pin2net'].update({'R7.2':'VIN','R7.3':'BIAS','R7.1':'unconnected-(R7-1)'})
        db['declared_pinname'].update({'R7.1':'CCW','R7.2':'WIPER','R7.3':'CW'})
        db['pinname']=dict(db['declared_pinname']);db['ref2page']['R7']=1
        if missing_symbol_pin:
            db['declared_pinname'].pop('R7.1');db['pinname'].pop('R7.1');db['pin2net'].pop('R7.1');db['nets'].pop('unconnected-(R7-1)')
        intent=self.intent();intent['input_sha256']=input_fingerprint(db)
        intent['devices']['R7']={'mpn':'synthetic-critical-trimmer','package':'THREE_TERMINAL','identity_citation':'Synthetic functional current adjustment element','citation':'Synthetic full three-terminal physical definition','pinout_complete':True,'pins':{str(n):{'name':name,'role':'other'} for n,name in [(1,'CCW'),(2,'WIPER'),(3,'CW')]}}
        return db,intent

    def test_declared_off_prefix_device_includes_unconnected_physical_terminal(self):
        db,intent=self.critical_fixture();plan=build_review_plan(db,intent)
        matches=[c for c in plan['checks'] if c['id']=='DEV-D02.R7']
        self.assertEqual(len(matches),1)
        self.assertEqual(matches[0]['pin_difference'],{'official_only':[],'symbol_only':[]})
        self.assertIsNone(matches[0]['review_result'])

    def test_declared_off_prefix_missing_physical_terminal_is_not_hidden(self):
        db,intent=self.critical_fixture(missing_symbol_pin=True);plan=build_review_plan(db,intent)
        check=next(c for c in plan['checks'] if c['id']=='DEV-D02.R7')
        self.assertEqual(check['pin_difference']['official_only'],['R7.1'])
        self.assertEqual(check['pin_difference']['symbol_only'],[])

    def test_unclassified_ordinary_off_prefix_part_not_automatically_promoted(self):
        db,intent=self.critical_fixture();intent['devices'].pop('R7')
        ids={c['id'] for c in build_review_plan(db,intent)['checks']}
        self.assertNotIn('DEV-D02.R7',ids)
if __name__=='__main__':unittest.main()

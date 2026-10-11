"""Quantity grouping and qualified document boundaries, without any MPN assumption."""
import os,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(os.environ.get('SR_ROOT',Path(__file__).resolve().parents[2]))
sys.path.insert(0,str(ROOT/'scripts'))
from audit_datasheets import _identity_for, _material_groups, normalize_identity, build_datasheet_audit

class QuantityIdentityExtensions(unittest.TestCase):
    def test_bare_engineering_suffix_uses_explicit_ordering_identity(self):
        for value in ('4.7u','47u','100n','2.2µ','4.7μ'):
            with self.subTest(value=value):
                self.assertEqual(_identity_for('C1',{'value':value,'part':'CAP-ORDER-X'}),('CAP-ORDER-X','part'))
    def test_different_bare_quantities_with_exact_parts_do_not_merge(self):
        db={'parts':{'C1':{'value':'4.7u','part':'CAP-ORDER-X'},'C2':{'value':'47u','part':'CAP-ORDER-Y'}}}
        groups,_=_material_groups(db,['C1','C2'])
        self.assertEqual(len(groups),2)
        self.assertEqual({g['identity'] for g in groups},{'CAP-ORDER-X','CAP-ORDER-Y'})
    def test_generic_decimal_quantities_remain_distinct_and_unresolved(self):
        db={'parts':{'C1':{'value':'1.0uF','part':'C'},'C2':{'value':'10uF','part':'C'}}}
        with tempfile.TemporaryDirectory() as tmp:
            audit=build_datasheet_audit(db,[tmp],required_refs=['C1','C2'])
        self.assertEqual(len(audit['materials']),2)
        self.assertTrue(all(m['status']!='AVAILABLE' for m in audit['materials']))
        self.assertEqual({m['identity_source'] for m in audit['materials']},{'value'})
    def test_quantity_sign_and_exponent_are_not_removed_as_mpn_punctuation(self):
        for a,b in [('1.0uF','10uF'),('1e-3F','1e3F'),('-1V','1V')]:
            with self.subTest(a=a,b=b):self.assertNotEqual(normalize_identity(a),normalize_identity(b))
    def test_preserved_quantity_distinctions_have_distinct_material_ids(self):
        values=['1.0uF','10uF','1e-3F','1e3F','-1V','1V','1mF','1MF']
        db={'parts':{f'C{i}':{'value':v,'part':'C'} for i,v in enumerate(values,1)}}
        groups,_=_material_groups(db,list(db['parts']))
        self.assertEqual(len(groups),len(values))
        self.assertEqual(len({g['material_id'] for g in groups}),len(values))
    def test_mpn_normalization_and_conflicting_identity_remain_compatible(self):
        self.assertEqual(normalize_identity('IC-ORDER_A'),'ICORDERA')
        self.assertEqual(_identity_for('U1',{'value':'IC-ORDER-A','part':'IC-ORDER-B'}),('IC-ORDER-A','value'))
        self.assertEqual(_identity_for('L1',{'value':'12345678901','part':'OTHER-ORDER'}),('12345678901','value'))
    def test_bare_quantity_does_not_promote_generic_or_unknown_part(self):
        for part in ('C','C_0603','CAPACITOR','TBD','UNKNOWN'):
            with self.subTest(part=part):
                self.assertEqual(_identity_for('C1',{'value':'4.7u','part':part}),('4.7u','value'))
    def test_bare_quantity_filename_is_still_only_a_candidate(self):
        db={'parts':{'C1':{'value':'4.7u','part':'CAP-ORDER-X'}}}
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'CAP-ORDER-X.pdf').write_bytes(b'%PDF-1.4\n')
            audit=build_datasheet_audit(db,[tmp],required_refs=['C1'])
        self.assertEqual(audit['materials'][0]['status'],'NEEDS_VERIFICATION')

if __name__=='__main__':unittest.main()

"""Advisory aggregate membership checks against explicit plan package scope."""
import os,sys,unittest,copy
from pathlib import Path
ROOT=Path(os.environ.get('SR_ROOT',Path(__file__).resolve().parents[2]))
sys.path.insert(0,str(ROOT/'scripts'))
from review_quality import screen_quality
def inputs(text,extra=None):
    checks=[{'id':'REQ-Q07.I2C','rule':'REQ-Q07','method':'Q','object':{'circuit_type':'I2C'},'criterion':'I2C members','circuit_type':'I2C'},
            {'id':'SIG-C07.I2C-RUN','rule':'SIG-C07','method':'C','object':{'circuit':'I2C'},'criterion':'level','circuit_type':'I2C'},
            {'id':'SIG-C07.I2C-OFF','rule':'SIG-C07','method':'C','object':{'circuit':'I2C'},'criterion':'level off','circuit_type':'I2C'},
            {'id':'SIG-C07.SPI-RUN','rule':'SIG-C07','method':'C','object':{'circuit':'SPI'},'criterion':'level','circuit_type':'SPI'}]
    if extra:checks.extend(extra)
    rows=[{'id':c['id'],'review_result':'PASS','rationale':text if c['rule']=='REQ-Q07' else c['id']} for c in checks]
    return {'checks':checks},{'checks':rows}
def codes(plan,report):return {c['code'] for c in screen_quality(plan,report)['candidates']}
class AggregatePackageQuality(unittest.TestCase):
    def test_shared_rule_does_not_make_another_bus_a_member(self):
        p,r=inputs('Members SIG-C07.I2C-RUN=PASS SIG-C07.I2C-OFF=PASS SIG-C07.SPI-RUN=PASS')
        self.assertIn('AGGREGATE_CHILD_CIRCUIT_TYPE_MISMATCH',codes(p,r))
    def test_explicit_member_list_missing_same_package_child_is_flagged(self):
        p,r=inputs('Members SIG-C07.I2C-RUN=PASS')
        self.assertIn('AGGREGATE_SUBJECTS_MISSING',codes(p,r))
    def test_complete_matching_members_are_not_flagged(self):
        p,r=inputs('Members SIG-C07.I2C-RUN=PASS SIG-C07.I2C-OFF=PASS')
        self.assertFalse(codes(p,r)&{'AGGREGATE_CHILD_CIRCUIT_TYPE_MISMATCH','AGGREGATE_SUBJECTS_MISSING'})
    def test_no_explicit_list_does_not_infer_missing_members(self):
        p,r=inputs('See separately reviewed source and dependencies.')
        self.assertFalse(codes(p,r)&{'AGGREGATE_CHILD_CIRCUIT_TYPE_MISMATCH','AGGREGATE_SUBJECTS_MISSING'})
    def test_unbound_physical_check_not_guessed_as_a_package_member(self):
        p,r=inputs('Members SIG-C07.I2C-RUN=PASS SIG-C07.I2C-OFF=PASS',[
            {'id':'SIG-E02.NET-X','rule':'SIG-E02','method':'E','object':{'net':'X'},'criterion':'electrical'}])
        self.assertNotIn('AGGREGATE_SUBJECTS_MISSING',codes(p,r))
    def test_unknown_package_is_not_imputed(self):
        p,r=inputs('Members SIG-C07.I2C-RUN=PASS SIG-C07.I2C-OFF=PASS SIG-C07.SPI-RUN=PASS')
        del p['checks'][-1]['circuit_type']
        self.assertNotIn('AGGREGATE_CHILD_CIRCUIT_TYPE_MISMATCH',codes(p,r))
    def test_explained_cross_package_dependency_still_requires_review_without_mutation(self):
        p,r=inputs('Members SIG-C07.I2C-RUN=PASS SIG-C07.I2C-OFF=PASS; SIG-C07.SPI-RUN=PASS is an explicit shared-rail dependency, not an I2C member.')
        before=copy.deepcopy((p,r));output=screen_quality(p,r)
        self.assertEqual((p,r),before)
        self.assertEqual(output['scope'],'ADVISORY_PATTERN_SCREENING_ONLY')
        self.assertIn('AGGREGATE_CHILD_CIRCUIT_TYPE_MISMATCH',{x['code']for x in output['candidates']})

if __name__=='__main__':unittest.main()

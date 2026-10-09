"""Advisory exact source locator/aggregate consistency, not semantic certification."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from review_quality import screen_quality

class ContextLocatorTests(unittest.TestCase):
    def screen(self,text):
        plan={'checks':[{'id':'PWR-C14.RF','rule':'PWR-C14','method':'C','object':{'ref':'U1'},'criterion':'Supply noise budget'},
                        {'id':'PWR-C14.RAIL','rule':'PWR-C14','method':'C','object':{'ref':'U2'},'criterion':'Supply noise budget'},
                        {'id':'REQ-Q07.POWER','rule':'REQ-Q07','method':'Q','object':{'package':'POWER'},'criterion':'Member coverage'}]}
        report={'checks':[{'id':'PWR-C14.RF','review_result':'INSUFFICIENT','rationale':text},
                          {'id':'PWR-C14.RAIL','review_result':'PASS','rationale':'Confirmed bounded supply'},
                          {'id':'REQ-Q07.POWER','review_result':'INSUFFICIENT','rationale':text}]}
        db={'parts':{'U1':{},'U2':{}},'pinname':{'U1.1':'VCC','U1.2':'VEN','U2.1':'VOUT'}}
        return screen_quality(plan,report,db)['candidates']
    def test_unknown_explicit_pin_name_is_advisory_candidate(self):
        out=self.screen('U1.VCC2 supply noise remains unknown')
        self.assertTrue(any(x['code']=='PIN_NAME_LOCATOR_NOT_IN_SOURCE' for x in out),out)
    def test_known_exact_pin_name_has_no_locator_candidate(self):
        out=self.screen('U1.VCC and U1.VEN have distinct supply/enable roles')
        self.assertFalse(any(x['code']=='PIN_NAME_LOCATOR_NOT_IN_SOURCE' for x in out),out)
    def test_name_with_correct_physical_pin_suffix_is_not_flagged(self):
        out=self.screen('U1.VCC1 and U1.VEN2 are exact name plus physical pin locators')
        self.assertFalse(any(x['code']=='PIN_NAME_LOCATOR_NOT_IN_SOURCE' for x in out),out)
    def test_absent_arbitrary_alias_is_not_claimed_as_a_defect(self):
        out=self.screen('U1.SUPPLY has a documented alias requiring human mapping')
        self.assertFalse(any(x['code']=='PIN_NAME_LOCATOR_NOT_IN_SOURCE' for x in out),out)

    def test_explicit_child_status_uses_final_result(self):
        out=self.screen('PWR-C14.RAIL INSUFFICIENT remains unresolved')
        self.assertTrue(any(x['code']=='AGGREGATE_CHILD_STATUS_MISMATCH' for x in out),out)
    def test_current_child_status_is_not_flagged(self):
        out=self.screen('PWR-C14.RAIL PASS; RF noise remains INSUFFICIENT')
        self.assertFalse(any(x['code']=='AGGREGATE_CHILD_STATUS_MISMATCH' for x in out),out)

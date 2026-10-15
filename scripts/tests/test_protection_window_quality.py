"""Regression for over-strict timing flags; no automated electrical verdicts."""
from copy import deepcopy
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from review_quality import screen_quality


def case(text, result='INSUFFICIENT', blocking=True, grade='P1'):
    plan={'checks':[{'id':'PRO-X1','rule':'ANA-T01','method':'T',
                    'object':{'ref':'U1'},'criterion':'Trace protection path'}]}
    row={'id':'PRO-X1','review_result':result,'blocking':blocking,
         'rationale':text,'potential_severity':grade,'evidence':[]}
    return plan, {'checks':[row]}, row


def has_warning(plan, report):
    return any(c['code']=='TIMING_BLOCK_WITHOUT_WINDOW'
               for c in screen_quality(plan,report)['candidates'])


class ProtectionWindowQualityTests(unittest.TestCase):
    def test_temperature_maximum_alone_prompts_review_not_automatic_downgrade(self):
        p,r,row=case('USB关断缺全温最大时间，不能冻结。');before=deepcopy(r)
        self.assertTrue(has_warning(p,r));self.assertEqual(r,before)

    def test_real_unknown_fault_window_can_remain_blocking(self):
        p,r,row=case('全温最大关断时间尚不能建立。')
        row['timing_assessment']={
            'scenario':'Feedback open while sourcing',
            'consequence':'Port voltage can exceed the protected load envelope',
            'allowed_window':'UNKNOWN: available fault current is not bounded',
            'response_bound':'UNKNOWN: actual detection configuration missing',
            'margin':'Not calculable; do not equate 650ms discharge to OVP latency',
            'temperature_scope':'Product ambient and justified component junction range',
            'closure_stage':'schematic_freeze: establish fault source and coordination'}
        self.assertFalse(has_warning(p,r));self.assertTrue(row['blocking'])
        self.assertEqual(row['review_result'],'INSUFFICIENT')

    def test_shared_analysis_is_not_copied_to_every_component(self):
        p,r,row=case('全温关断响应需核定。')
        row['timing_assessment']={'evidence':[{'source':'fault-window.md','locator':'OVP-1'}]}
        self.assertFalse(has_warning(p,r))

    def test_empty_reference_does_not_hide_a_flag(self):
        p,r,row=case('full-temperature turn-off maximum is unavailable')
        row['timing_assessment']={'evidence':[{'source':'fault-window.md','locator':''}]}
        self.assertTrue(has_warning(p,r))

    def test_positive_margin_and_prototype_handoff_are_not_new_blockers(self):
        p,r,row=case('关断的全温设计上界已小于协议窗口；PCB波形样机复核。','PASS',False,None)
        row['handoff']={'required':True,'state':'OPEN'}
        self.assertFalse(has_warning(p,r));self.assertEqual(row['handoff']['state'],'OPEN')

    def test_thermal_rating_without_dynamic_claim_is_outside_this_screen(self):
        p,r,row=case('C1缺全温纹波电流额定，影响电容温升。')
        self.assertFalse(has_warning(p,r))

    def test_actual_fail_is_never_waived_by_window_metadata(self):
        p,r,row=case('turn-off delay exceeds the maximum 20us deadline','FAIL',True,'P0')
        row['timing_assessment']={'evidence':[{'source':'analysis.md','locator':'Measured 50us vs20us'}]}
        before=deepcopy(r);self.assertFalse(has_warning(p,r));self.assertEqual(r,before)

    def test_p1_implicit_blocker_is_screened_even_when_boolean_is_false(self):
        p,r,row=case('未提供全温关断最大时间。',blocking=False)
        self.assertTrue(has_warning(p,r))

if __name__=='__main__':unittest.main()

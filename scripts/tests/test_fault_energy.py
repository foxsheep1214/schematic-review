import math
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fault_energy import packet_bound, capacitor_energy_window

class FaultEnergyTests(unittest.TestCase):
    def args(self):
        return dict(inductance_h=300e-6,peak_current_a=4,frequency_hz=150e3,
                    duration_s=40e-6,capacitance_f=800e-6,initial_voltage_v=30,
                    initial_stored_j=.0024)
    def test_energy_conservation_and_initial_packet(self):
        x=packet_bound(**self.args())
        self.assertEqual(x['cycles'],6)
        self.assertAlmostEqual(x['energy_j'],7*.0024)
        self.assertAlmostEqual(.5*.0008*(x['final_voltage_v']**2-900),x['energy_j'])
    def test_zero_duration_keeps_stored_energy(self):
        a=self.args();a['duration_s']=0
        x=packet_bound(**a)
        self.assertEqual(x['cycles'],0)
        self.assertGreater(x['final_voltage_v'],30)
    def test_fractional_cycle_rounds_up(self):
        a=self.args();a['duration_s']=40.1e-6
        self.assertEqual(packet_bound(**a)['cycles'],7)
    def test_more_time_never_lowers_stress(self):
        a=self.args();x=packet_bound(**a);a['duration_s']*=2
        self.assertGreater(packet_bound(**a)['final_voltage_v'],x['final_voltage_v'])
    def test_window_reserves_existing_packet(self):
        a=dict(capacitance_f=.0008,initial_voltage_v=30,limit_voltage_v=32,
               initial_stored_j=.0024,packet_j=.0024,frequency_hz=150e3)
        x=capacitor_energy_window(**a)
        self.assertLessEqual(x['allowed_full_packets']*.0024,x['remaining_energy_j'])
        self.assertGreater((x['allowed_full_packets']+1)*.0024,x['remaining_energy_j'])
    def test_already_exceeded_has_no_time_budget(self):
        x=capacitor_energy_window(capacitance_f=.001,initial_voltage_v=36,limit_voltage_v=35,
             initial_stored_j=.0024,packet_j=.0024,frequency_hz=150e3)
        self.assertEqual(x['duration_budget_s'],0)
    def test_reject_invalid_physical_inputs(self):
        for key,value in [('duration_s',-1),('capacitance_f',0),('frequency_hz',math.inf),
                          ('peak_current_a',math.nan),('initial_stored_j',True)]:
            with self.subTest(key=key):
                a=self.args();a[key]=value
                with self.assertRaises(ValueError):packet_bound(**a)
    def test_no_automatic_acceptance_or_severity(self):
        x=packet_bound(**self.args())
        self.assertEqual(x['basis'],'CONDITIONAL_ON_CALLER_BOUNDS')
        self.assertNotIn('review_result',x)
        self.assertNotIn('potential_severity',x)

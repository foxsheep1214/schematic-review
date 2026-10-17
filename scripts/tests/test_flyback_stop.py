import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from flyback_stop import post_stop_capacitor_bound, primary_on_sr_platform


class FlybackStopTests(unittest.TestCase):
    # Synthetic physics examples; these values are not a reviewed design.
    def bound(self, v=10, c=.001, e=.05):
        return post_stop_capacitor_bound(voltage_at_stop_v=v,capacitance_f=c,remaining_energy_j=e)

    def test_energy_conservation(self):
        r=self.bound()
        self.assertAlmostEqual(.5*.001*(r['capacitor_voltage_bound_v']**2-100),.05)

    def test_no_stored_energy_no_rise(self):
        self.assertEqual(self.bound(e=0)['capacitor_voltage_bound_v'],10)

    def test_monotone_energy_and_capacitance(self):
        base=self.bound()['capacitor_voltage_bound_v']
        self.assertGreater(self.bound(e=.1)['capacitor_voltage_bound_v'],base)
        self.assertLess(self.bound(c=.002)['capacitor_voltage_bound_v'],base)

    def test_unknown_not_silently_zero(self):
        for args in [{'v':None},{'c':None},{'e':None}]:
            with self.assertRaises(ValueError):self.bound(**args)

    def test_invalid_physics(self):
        for args in [{'v':-1},{'c':0},{'e':-1},{'v':float('nan')},{'e':True}]:
            with self.assertRaises(ValueError):self.bound(**args)

    def test_primary_on_platform(self):
        r=primary_on_sr_platform(output_v_at_event=10,primary_bus_v_at_event=200,primary_secondary_ratio=5,phase='PRIMARY_ON')
        self.assertEqual(r['platform_v'],50)
        self.assertFalse(r['spikes_included'])

    def test_reject_after_stop_phase_for_primary_on_formula(self):
        for phase in ['AFTER_LAST_PRIMARY_SWITCHING','DEMAGNETIZING','SETTLED',None]:
            with self.assertRaises(ValueError):
                primary_on_sr_platform(output_v_at_event=10,primary_bus_v_at_event=200,primary_secondary_ratio=5,phase=phase)

    def test_no_automatic_maximum_stress_or_grade(self):
        r=self.bound()
        self.assertFalse(r['terminal_spikes_included'])
        self.assertNotIn('Q501_peak_v',r)
        self.assertNotIn('verdict',r)

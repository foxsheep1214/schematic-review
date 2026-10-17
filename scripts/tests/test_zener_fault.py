import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from zener_fault import trip_drive,no_trip_budget,hold_charge

class DetectorBounds(unittest.TestCase):
    def drive(self,**kw):
        a=dict(zener_max_v=76.5,test_current_a=.002,series_max_ohm=1010,threshold_max_v=3.21,clamp_min_v=1.15,clamp_r_min_ohm=1320,extra_sink_max_a=0,helpful_source_min_a=0);a.update(kw);return trip_drive(**a)
    def test_receiver_load_not_ignored(self):
        r=self.drive();self.assertAlmostEqual(r['supply_sufficient_v'],81.73);self.assertAlmostEqual(r['charging_current_min_a'],.0004393939393939395)
    def test_extra_load_removes_guarantee(self):
        self.assertLess(self.drive(extra_sink_max_a=.001)['charging_current_min_a'],0)
    def test_minimum_source_monotone(self):
        self.assertGreater(self.drive(helpful_source_min_a=.00004)['charging_current_min_a'],self.drive()['charging_current_min_a'])
    def test_series_resistance_changes_voltage_not_receiver_load(self):
        a=self.drive();b=self.drive(series_max_ohm=2020);self.assertAlmostEqual(b['supply_sufficient_v']-a['supply_sufficient_v'],2.02);self.assertEqual(a['charging_current_min_a'],b['charging_current_min_a'])
    def test_no_trip_with_parallel_source(self):
        a=no_trip_budget(threshold_min_v=2.79,clamp_max_v=2.25,clamp_r_max_ohm=1780,other_source_max_a=46.25e-6)
        self.assertAlmostEqual(a['external_current_budget_a'],.000257120786516854)
    def test_no_trip_unavailable_not_clipped_to_pass(self):
        a=no_trip_budget(threshold_min_v=2,clamp_max_v=2.25,clamp_r_max_ohm=1780,other_source_max_a=.001);self.assertLess(a['external_current_budget_a'],0)
    def test_charge_conservation(self):
        r=hold_charge(capacitance_min_f=10e-6,start_min_v=8.5,reset_max_v=7.5,deficit_charge_c=5e-6);self.assertAlmostEqual(r['voltage_lower_bound_v'],8);self.assertAlmostEqual(r['charge_margin_c'],5e-6)
    def test_equal_reset_not_positive_margin(self):
        r=hold_charge(capacitance_min_f=10e-6,start_min_v=8.5,reset_max_v=7.5,deficit_charge_c=10e-6);self.assertAlmostEqual(r['charge_margin_c'],0)
    def test_capacity_monotone(self):
        a=dict(start_min_v=8.5,reset_max_v=7.5,deficit_charge_c=10e-6)
        self.assertGreater(hold_charge(capacitance_min_f=20e-6,**a)['voltage_lower_bound_v'],hold_charge(capacitance_min_f=10e-6,**a)['voltage_lower_bound_v'])
    def test_invalid_or_unknown_input_rejected(self):
        for v in [None,True,float('inf'),float('nan'),-1]:
            with self.subTest(v=v), self.assertRaises(ValueError):self.drive(test_current_a=v)
        with self.assertRaises(ValueError):self.drive(clamp_r_min_ohm=0)
        with self.assertRaises(ValueError):hold_charge(capacitance_min_f=0,start_min_v=8.5,reset_max_v=7.5,deficit_charge_c=0)

if __name__=='__main__':unittest.main()

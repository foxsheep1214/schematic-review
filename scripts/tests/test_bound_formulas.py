"""The bounding formulas of the operating-point table (bounding table proposal of 2026-10-23, sections 二 and 五)."""
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bound_formulas as bf
import calc


class GenericMethodTests(unittest.TestCase):
    def test_g3_moves_the_test_point_by_the_largest_slope_against_the_side(self):
        # VZ min 15.68 V at 2 mA, rdif max 170 Ω at the lower point: at 1 mA, 15.68 − 0.17 V (1-A)
        self.assertAlmostEqual(bf.slope_bound(p0=15.68, x0=2e-3, x=1e-3, slope_max=170, side='LOWER'), 15.51)
        self.assertAlmostEqual(bf.slope_bound(p0=16.32, x0=2e-3, x=3e-3, slope_max=170, side='UPPER'), 16.49)
        for bad in ({'slope_max': -1}, {'side': 'BOTH'}, {'p0': float('nan')}):
            with self.assertRaises(ValueError):
                bf.slope_bound(**dict({'p0': 15.68, 'x0': 2e-3, 'x': 1e-3, 'slope_max': 170, 'side': 'LOWER'}, **bad))

    def test_g4_takes_the_unfavourable_end_of_the_temperature_coefficient(self):
        args = {'p0': 16.0, 't0': 25, 't': 105, 's_min': 0.008, 's_max': 0.013}
        self.assertAlmostEqual(bf.tempco_bound(side='UPPER', **args), 17.04)
        self.assertAlmostEqual(bf.tempco_bound(side='LOWER', **args), 16.64)
        self.assertAlmostEqual(bf.tempco_bound(side='LOWER', **dict(args, t=-10)), 16.0 - 0.013 * 35)
        with self.assertRaises(ValueError):
            bf.tempco_bound(side='LOWER', **dict(args, s_min=0.02))

    def test_g5_interpolates_the_published_table_and_stays_inside_it(self):
        table = [[0, 1.0, 2.0], [10, 3.0, 4.0]]
        self.assertAlmostEqual(bf.table_interpolate(table=table, x=5, side='LOWER'), 2.0)
        self.assertAlmostEqual(bf.table_interpolate(table=table, x=5, side='UPPER'), 3.0)
        with self.assertRaises(ValueError):
            bf.table_interpolate(table=table, x=11, side='UPPER')
        with self.assertRaises(ValueError):
            bf.table_interpolate(table=[[0, 2.0, 1.0], [10, 3.0, 4.0]], x=5, side='UPPER')

    def test_g7_scales_the_typical_curve_by_the_guaranteed_ratio(self):
        self.assertAlmostEqual(bf.ratio_extrapolation(typ_at_x=50e-6, max_at_x0=5e-6, typ_at_x0=0.5e-6), 500e-6)

    def test_g9_is_thirty_percent_either_way(self):
        self.assertAlmostEqual(bf.typical_band(typ=1.0, side='UPPER'), 1.3)
        self.assertAlmostEqual(bf.typical_band(typ=1.0, side='LOWER'), 0.7)


class NtcTests(unittest.TestCase):
    def test_c_a_published_table_is_interpolated_with_ln_r_against_one_over_t(self):
        table = [[25, 9900, 10100], [50, 3500, 3700]]
        low = bf.ntc_table_bound(table=table, temp_c=37.5, side='LOWER')
        x = (1 / (37.5 + 273.15) - 1 / 298.15) / (1 / 323.15 - 1 / 298.15)
        self.assertAlmostEqual(low, math.exp(math.log(9900) + (math.log(3500) - math.log(9900)) * x))

    def test_c_without_a_table_the_beta_model_with_its_tolerances_bounds(self):
        args = {'r25_ohm': 10000, 'r25_tol': 0.01, 'beta_k': 3950, 'beta_tol': 0.01, 'temp_c': 125}
        self.assertLess(bf.ntc_beta_bound(side='LOWER', **args), bf.ntc_beta_bound(side='UPPER', **args))

    def test_e_a_hot_inrush_limiter_is_zero_ohm(self):
        self.assertAlmostEqual(bf.inrush_peak_current(v_peak_v=373, r_other_ohm=2), 186.5)
        self.assertAlmostEqual(bf.inrush_i2t(v_peak_v=373, r_other_ohm=2, c_f=100e-6), 373 ** 2 * 100e-6 / 4)


class SoaTests(unittest.TestCase):
    def test_b_the_curve_is_derated_to_the_starting_case_temperature(self):
        args = {'p_curve_w': 100, 'tj_max_c': 150, 'tc_start_c': 100}
        self.assertAlmostEqual(bf.soa_allowed_power(segment='CONSTANT_POWER', **args), 40)
        self.assertAlmostEqual(bf.soa_allowed_power(segment='THERMAL_INSTABILITY', **args), 32)
        self.assertEqual(bf.soa_allowed_power(segment='CONSTANT_POWER', **dict(args, tc_start_c=160)), 0)
        with self.assertRaises(ValueError):
            bf.soa_allowed_power(segment='LINEAR', **args)

    def test_b_the_allowed_case_temperature_and_the_heatsink_go_to_thermal_design(self):
        tc = bf.soa_case_temperature(p_w=40, p_curve_w=100, tj_max_c=150, segment='CONSTANT_POWER')
        self.assertAlmostEqual(tc, 100)
        self.assertAlmostEqual(bf.soa_case_temperature(p_w=32, p_curve_w=100, tj_max_c=150,
                                                       segment='THERMAL_INSTABILITY'), 100)
        self.assertAlmostEqual(bf.heatsink_requirement(tc_allowed_c=100, ta_max_c=60, p_w=2), 20)

    def test_b_repeated_transients_use_the_transient_thermal_impedance(self):
        self.assertAlmostEqual(bf.zth_junction_temperature(tc_c=90, p_pk_w=50, zth_k_per_w=0.8), 130)


class SwitchAndSurgeTests(unittest.TestCase):
    def test_d_a_saturated_bjt_is_driven_with_forced_beta_two(self):
        self.assertAlmostEqual(bf.forced_beta_base_current(ic_a=0.1, hfe_min=100), 2e-3)

    def test_a_surge_rating_moves_to_a_shorter_pulse_at_constant_i2t(self):
        self.assertAlmostEqual(bf.half_sine_i2t(ifsm_a=30, t_s=10e-3), 4.5)
        self.assertAlmostEqual(bf.surge_current_at_width(ifsm_a=30, t_rated_s=8.3e-3, t_s=8.3e-3 / 4), 60)
        with self.assertRaises(ValueError):
            bf.surge_current_at_width(ifsm_a=30, t_rated_s=8.3e-3, t_s=20e-3)


class RegistryTests(unittest.TestCase):
    def test_every_formula_is_a_calculation_of_the_library(self):
        for name, fn in bf.FORMULAS.items():
            self.assertIs(calc.FUNCTIONS['bound_formulas.' + name], fn)


if __name__ == '__main__':
    unittest.main()

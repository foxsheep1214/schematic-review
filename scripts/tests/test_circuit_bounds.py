"""circuit_bounds picks every worst-case corner itself; calc_claims flags stated numbers that disagree."""
import contextlib
import io
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import calc_claims
from circuit_bounds import (capacitor_ripple_capability, divider_bounds, linear_regulator_thermal,
                            logic_level_margins, rc_crossing_time, resistor_power, series_resistor_current)


class DividerTest(unittest.TestCase):
    def test_feedback_window_matches_hand_corners(self):
        out = divider_bounds(r_top_ohm=100e3, r_bottom_ohm=22e3, r_tol=0.01, vref_min_v=0.788, vref_max_v=0.812)
        self.assertAlmostEqual(out['vout_min_v'], 0.788 * (1 + 99e3 / 22.22e3))
        self.assertEqual(out['vout_max_corner'], 'Vmax+Rtmax+Rbmin')
        self.assertEqual(out['mode'], 'feedback')

    def test_plain_divider_and_mode_errors(self):
        out = divider_bounds(r_top_ohm=10e3, r_bottom_ohm=10e3, r_tol=0.05, vin_min_v=4.5, vin_max_v=5.5)
        self.assertAlmostEqual(out['vout_min_v'], 4.5 * 9.5e3 / (10.5e3 + 9.5e3))
        self.assertAlmostEqual(out['r_top_power_max_w'], 5.5 ** 2 * 9.5e3 / 19e3 ** 2)   # Rtmin+Rbmin
        with self.assertRaises(ValueError):
            divider_bounds(r_top_ohm=1, r_bottom_ohm=1, r_tol=0.01, vin_min_v=1, vin_max_v=2, vref_min_v=1, vref_max_v=1)
        with self.assertRaises(ValueError):
            divider_bounds(r_top_ohm=1, r_bottom_ohm=1, r_tol=0.01)


class RcTest(unittest.TestCase):
    def test_rising_and_falling_crossings(self):
        rise = rc_crossing_time(r_ohm=10e3, r_tol=0.01, c_f=1e-6, c_tol_minus=0.1, c_tol_plus=0.1,
                                v_start_v=0, v_final_v=3.3, v_threshold_min_v=1.0, v_threshold_max_v=2.0)
        self.assertAlmostEqual(rise['t_min_s'], 9.9e3 * 0.9e-6 * math.log(3.3 / 2.3))
        self.assertAlmostEqual(rise['t_max_s'], 10.1e3 * 1.1e-6 * math.log(3.3 / 1.3))
        fall = rc_crossing_time(r_ohm=10e3, r_tol=0, c_f=1e-6, c_tol_minus=0, c_tol_plus=0,
                                v_start_v=5, v_final_v=0, v_threshold_min_v=1, v_threshold_max_v=1)
        self.assertEqual(fall['direction'], 'falling')
        self.assertAlmostEqual(fall['t_min_s'], 10e-3 * math.log(5))

    def test_unreached_threshold_is_an_error(self):
        with self.assertRaises(ValueError):
            rc_crossing_time(r_ohm=1, r_tol=0, c_f=1, c_tol_minus=0, c_tol_plus=0,
                             v_start_v=0, v_final_v=3.3, v_threshold_min_v=1, v_threshold_max_v=3.5)


class LogicLevelTest(unittest.TestCase):
    def test_fractional_vih_uses_the_receiver_supply_maximum(self):
        # 100W PD 复审：高电平窗口推导方向写反；VIH=0.7*VDD 要用 VDD 最大值。
        out = logic_level_margins(voh_drop_v=0.4, driver_supply_min_v=3.135, vih_fraction=0.7,
                                  receiver_supply_min_v=3.135, receiver_supply_max_v=3.465,
                                  vol_max_v=0.4, vil_fraction=0.3)
        self.assertAlmostEqual(out['vih_worst_v'], 0.7 * 3.465)
        self.assertAlmostEqual(out['high_margin_v'], 2.735 - 0.7 * 3.465)
        self.assertAlmostEqual(out['low_margin_v'], 0.3 * 3.135 - 0.4)

    def test_ambiguous_levels_are_rejected(self):
        with self.assertRaises(ValueError):
            logic_level_margins(voh_min_v=2.4, vih_min_v=2.0, vih_fraction=0.7, receiver_supply_max_v=3.3)
        with self.assertRaises(ValueError):
            logic_level_margins(voh_min_v=2.4, vih_fraction=0.7)


class RippleTest(unittest.TestCase):
    FREQ = [[120, 0.6], [1e3, 0.8], [10e3, 0.95], [100e3, 1.0]]
    TEMP = [[85, 1.73], [95, 1.41], [105, 1.0]]

    def test_lower_bracketing_factor_and_no_extrapolation(self):
        # 100W PD 复审：105°C 额定 4.256 Arms 被写成 90°C 的 5.09 Arms。
        out = capacitor_ripple_capability(rated_arms=4.256, freq_factors=self.FREQ, freq_hz=65e3,
                                          temp_factors=self.TEMP, temp_c=100)
        self.assertEqual((out['freq_factor'], out['temp_factor']), (0.95, 1.0))
        self.assertAlmostEqual(out['allowed_arms'], 4.256 * 0.95)
        hot = capacitor_ripple_capability(rated_arms=4.256, freq_factors=self.FREQ, freq_hz=65e3,
                                          temp_factors=self.TEMP, temp_c=110)
        self.assertIsNone(hot['allowed_arms'])
        self.assertEqual(hot['applicability_flags'], ['outside-temp-table'])


class MiscTest(unittest.TestCase):
    def test_ldo_resistor_and_series_current(self):
        ldo = linear_regulator_thermal(vin_max_v=5.5, vout_min_v=3.2, iout_max_a=0.3, iq_max_a=1e-3,
                                       theta_ja_c_per_w=150, ambient_max_c=60, tj_max_c=125)
        self.assertAlmostEqual(ldo['dissipation_w'], 2.3 * 0.3 + 5.5e-3)
        self.assertAlmostEqual(ldo['tj_margin_c'], 125 - 60 - ldo['dissipation_w'] * 150)
        self.assertAlmostEqual(resistor_power(v_max_v=10, r_ohm=100, r_tol=0.05, rated_w=1.25, derating=0.8)
                               ['power_max_w'], 100 / 95)
        led = series_resistor_current(v_supply_min_v=4.75, v_supply_max_v=5.25, v_drop_min_v=1.8,
                                      v_drop_max_v=2.2, r_ohm=330, r_tol=0.05)
        self.assertAlmostEqual(led['i_min_a'], (4.75 - 2.2) / (330 * 1.05))
        self.assertAlmostEqual(led['i_max_a'], (5.25 - 1.8) / (330 * 0.95))


class ClaimsTest(unittest.TestCase):
    def claim(self, **over):
        base = {'id': 'NTC-150', 'source': 'design/calc.md', 'locator': 'table 3',
                'calculation': 'model_bounds.ntc_resistance_bounds',
                'inputs': {'r25_ohm': 10e3, 'r25_tol': 0.01, 'beta_k': 3435, 'beta_tol': 0.01, 'temp_c': 150},
                'claimed': {'r_min_ohm': 1.0}}
        base.update(over)
        return base

    def test_wrong_corner_is_a_mismatch_and_right_one_matches(self):
        from model_bounds import ntc_resistance_bounds
        right = ntc_resistance_bounds(r25_ohm=10e3, r25_tol=0.01, beta_k=3435, beta_tol=0.01, temp_c=150)['r_min_ohm']
        wrong = 9900 * math.exp(3435 * 0.99 * (1 / 423.15 - 1 / 298.15))   # Bmin, as the design script did
        rows, errors = calc_claims.check([self.claim(claimed={'r_min_ohm': wrong}),
                                          self.claim(id='NTC-OK', claimed={'r_min_ohm': right})])
        self.assertEqual(errors, [])
        self.assertEqual([r['status'] for r in rows], ['MISMATCH', 'MATCH'])

    def test_bad_inputs_and_malformed_claims(self):
        rows, errors = calc_claims.check([self.claim(inputs={'r25_ohm': -1})])
        self.assertEqual(rows[0]['status'], 'ERROR')
        self.assertTrue(calc_claims.check([self.claim(claimed={})])[1])
        self.assertTrue(calc_claims.check([self.claim(), self.claim()])[1])
        self.assertTrue(calc_claims.check([])[1])

    def test_cli_exit_codes_and_evidence_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, out = Path(tmp) / 'claims.json', Path(tmp) / 'out.json'
            path.write_text(json.dumps([self.claim()]))
            with contextlib.redirect_stdout(io.StringIO()):
                code = calc_claims.main([str(path), '--json', str(out)])
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(out.read_text())['summary']['MISMATCH'], 1)
            path.write_text('{}')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(calc_claims.main([str(path)]), 2)


if __name__ == '__main__':
    unittest.main()

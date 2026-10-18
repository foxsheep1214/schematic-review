"""model_bounds picks tolerance corners and model phases itself."""
import math
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model_bounds import cc_discharge_with_tail, ntc_resistance_bounds


class NtcBoundsTest(unittest.TestCase):
    ARGS = dict(r25_ohm=10e3, r25_tol=0.01, beta_k=3435, beta_tol=0.01)

    def test_hot_minimum_uses_r25min_and_bmax(self):
        # 100W PD 复审：设计脚本用 Bmin 算 150°C 最小阻值，得到的其实是较大阻值。
        hot = ntc_resistance_bounds(temp_c=150, **self.ARGS)
        self.assertEqual(hot['r_min_corner'], 'R25min+Bmax')
        x = 1 / (150 + 273.15) - 1 / 298.15
        self.assertAlmostEqual(hot['r_min_ohm'], 9900 * math.exp(3435 * 1.01 * x))
        self.assertLess(hot['r_min_ohm'], 9900 * math.exp(3435 * 0.99 * x))
        cold = ntc_resistance_bounds(temp_c=-20, **self.ARGS)
        self.assertEqual(cold['r_min_corner'], 'R25min+Bmin')
        self.assertEqual(cold['r_max_corner'], 'R25max+Bmax')

    def test_out_of_range_temperatures_are_flagged_not_extended(self):
        out = ntc_resistance_bounds(temp_c=150, beta_range_c=[25, 85], rated_range_c=[-40, 125], **self.ARGS)
        self.assertEqual(out['applicability_flags'], ['outside-beta-fit-range', 'outside-rated-range'])
        self.assertEqual(ntc_resistance_bounds(temp_c=50, beta_range_c=[25, 85], **self.ARGS)['applicability_flags'], [])

    def test_bad_inputs_are_rejected(self):
        for bad in (dict(r25_tol=1.5), dict(beta_range_c=[85, 25]), dict(temp_c=True)):
            with self.assertRaises(ValueError):
                ntc_resistance_bounds(**dict(dict(self.ARGS, temp_c=25), **bad))


class DischargeTest(unittest.TestCase):
    def test_constant_current_stops_at_the_compliance_boundary(self):
        # 100W PD 复审：105 mA 恒流不能一路积分到 5.5 V，合规交界以下是 RC 尾段。
        out = cc_discharge_with_tail(capacitance_f=1e-3, start_v=26, end_v=5.5, sink_current_a=0.105,
                                     series_r_max_ohm=49.35, tail_r_ohm=30)
        self.assertAlmostEqual(out['compliance_boundary_v'], 0.105 * 79.35)
        self.assertAlmostEqual(out['constant_current_s'], 1e-3 * (26 - 0.105 * 79.35) / 0.105)
        self.assertAlmostEqual(out['tail_s'], 79.35e-3 * math.log(0.105 * 79.35 / 5.5))
        self.assertEqual(out['phase_at_end'], 'resistive-tail')
        naive = 1e-3 * (26 - 5.5) / 0.105
        self.assertGreater(out['total_s'], naive)

    def test_end_above_compliance_has_no_tail_and_start_below_has_no_cc(self):
        above = cc_discharge_with_tail(capacitance_f=1e-3, start_v=26, end_v=10, sink_current_a=0.105,
                                       series_r_max_ohm=49.35, tail_r_ohm=30)
        self.assertEqual((above['tail_s'], above['phase_at_end']), (0.0, 'constant-current'))
        below = cc_discharge_with_tail(capacitance_f=1e-3, start_v=5, end_v=1, sink_current_a=0.105,
                                       series_r_max_ohm=49.35, tail_r_ohm=30)
        self.assertEqual(below['constant_current_s'], 0.0)
        self.assertAlmostEqual(below['tail_s'], 79.35e-3 * math.log(5))
        with self.assertRaises(ValueError):
            cc_discharge_with_tail(capacitance_f=1e-3, start_v=5, end_v=6, sink_current_a=0.1,
                                   series_r_max_ohm=1, tail_r_ohm=1)


if __name__ == '__main__':
    unittest.main()

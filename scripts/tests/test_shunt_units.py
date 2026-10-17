"""Synthetic regression for explicit milliohm shunts and overload discrimination.

Source trigger: SparkFun INA2XX v10 at 313d3e2c, R2='15mR', Power=1W.
No test encodes that board identity or grants a device-specific exemption.
"""
import unittest
from fractions import Fraction
from solve_dividers import parse_resistor

class ShuntUnitTests(unittest.TestCase):
    def test_explicit_milliohm_spellings_are_equivalent(self):
        for value in ('15mR', '15 mΩ', '15mohm', '15 milliohms'):
            with self.subTest(value=value):
                result = parse_resistor(value, exact=True)
                self.assertIsNotNone(result)
                self.assertEqual(Fraction(result['ohm_exact']), Fraction(15, 1000))
                self.assertAlmostEqual(result['kohm'], 0.000015)
                self.assertIsNone(result['tol'])

    def test_lowercase_m_is_milli_in_rkm_and_bare_forms(self):
        # rf1 公开板 R19='7m5'（7.5 mΩ 采样电阻）曾被读成 7.5 MΩ。
        for value, ohm in (('7m5', Fraction(15, 2000)), ('10m', Fraction(1, 100)), ('4m7 1%', Fraction(47, 10000))):
            with self.subTest(value=value):
                self.assertEqual(Fraction(parse_resistor(value, exact=True)['ohm_exact']), ohm)
        self.assertEqual(Fraction(parse_resistor('4M7', exact=True)['ohm_exact']), 4700000)

    def test_milliohm_tolerance_remains_explicit(self):
        result = parse_resistor('15mR/1%', exact=True)
        self.assertIsNotNone(result)
        self.assertEqual(Fraction(result['tol_exact']), Fraction(1, 100))
        self.assertEqual(Fraction(result['ohm_exact']), Fraction(3, 200))

    def test_shunt_power_distinguishes_loads_without_relaxing_rating(self):
        result = parse_resistor('15mR', exact=True)
        self.assertIsNotNone(result)
        resistance = Fraction(result['ohm_exact'])
        self.assertEqual(10 ** 2 * resistance, Fraction(3, 2))
        self.assertGreater(10 ** 2 * resistance, 1)
        self.assertEqual(5 ** 2 * resistance, Fraction(3, 8))
        self.assertLess(5 ** 2 * resistance, 1)

    def test_unknown_suffix_and_invalid_tolerance_are_not_truncated(self):
        for value in ('15mRwrong', '15mR/100%', '15mR/-1%'):
            self.assertIsNone(parse_resistor(value), value)

    def test_entire_suffix_must_be_valid(self):
        for unit in ('15mR', '15mohm', '4K7', '20Kohm'):
            for suffix in (' garbage', '/1%junk', '/-1% 5%', '/1% 5%'):
                value = unit + suffix
                with self.subTest(value=value):
                    self.assertIsNone(parse_resistor(value))

    def test_single_tolerance_separators_and_missing_tolerance(self):
        for suffix in ('/1%', ' ± 1%', ' +/- 1%', ' 1%'):
            with self.subTest(suffix=suffix):
                result = parse_resistor('15mR' + suffix, exact=True)
                self.assertEqual(Fraction(result['ohm_exact']), Fraction(3, 200))
                self.assertEqual(Fraction(result['tol_exact']), Fraction(1, 100))
        self.assertIsNone(parse_resistor('15mR')['tol'])
        self.assertIsNone(parse_resistor('15mR', exact=True)['tol_exact'])

    def test_existing_mega_and_decimal_notation_keep_scale(self):
        for value in ('15M', '15MOhm'):
            self.assertEqual(parse_resistor(value)['kohm'], 15000)
        self.assertAlmostEqual(parse_resistor('R015')['kohm'], 0.000015)
        self.assertEqual(parse_resistor('4K7')['kohm'], 4.7)

if __name__ == '__main__':
    unittest.main()

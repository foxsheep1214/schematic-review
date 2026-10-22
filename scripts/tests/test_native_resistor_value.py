"""Bounded value/tolerance/package grammar, not physical package qualification."""
from fractions import Fraction
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from solve_dividers import parse_resistor


class NativeResistorValueTests(unittest.TestCase):
    def test_nominal_and_tolerance_are_not_taken_from_package_digits(self):
        row = parse_resistor('330k/1%/R0402', exact=True)
        self.assertIsNotNone(row)
        self.assertEqual(row['kohm'], 330)
        self.assertEqual(Fraction(row['ohm_exact']), 330000)
        self.assertEqual(Fraction(row['tol_exact']), Fraction(1, 100))

    def test_value_spellings_and_packaging_keep_exact_decimals(self):
        for value, ohms in [('4k7/0.5%/R0603', Fraction(4700)),
                            ('R015/1%/R2512', Fraction(15, 1000)),
                            ('15mOhm/1%/R1206', Fraction(15, 1000)),
                            ('15MOhm/1%/R0201', Fraction(15000000)),
                            ('49.9k / 1% / R0402', Fraction(49900))]:
            with self.subTest(value=value):
                row = parse_resistor(value, exact=True)
                self.assertIsNotNone(row)
                self.assertEqual(Fraction(row['ohm_exact']), ohms)

    def test_missing_tolerance_stays_unknown_without_explicit_source(self):
        row = parse_resistor('2.2k/R0402', exact=True)
        self.assertIsNotNone(row)
        self.assertIsNone(row['tol'])
        self.assertIsNone(row['tol_exact'])
        self.assertEqual(parse_resistor('2.2k/R0402', default_tol=.02, exact=True)['tol_exact'], '1/50')

    def test_conflicting_or_junk_suffixes_are_not_silently_dropped(self):
        for value in ['330k/1%/R0402/5%', '330k/1% 5%/R0402',
                      '330k/1%junk/R0402', '330k/R0402/R0603',
                      '330k/1%/C0402', '330k/1%/NC', '330k/1%/R8',
                      '330k/1%/R9999', '330k/R0402/1%', '330k/1%/R0402junk']:
            with self.subTest(value=value):
                self.assertIsNone(parse_resistor(value))

    def test_a_power_rating_after_the_tolerance_is_read(self):
        # BOM values often carry the rated power: 1k5/1%/1W. It is read, never taken as resistance or tolerance.
        for value, ohms, tol, watts in [('1k5/1%/1W', Fraction(1500), Fraction(1, 100), 1.0),
                                        ('2R2/5%/0.25W', Fraction(22, 10), Fraction(5, 100), 0.25),
                                        ('100k/1%/250mW', Fraction(100000), Fraction(1, 100), 0.25),
                                        ('47R/1%/2W/R2512', Fraction(47), Fraction(1, 100), 2.0),
                                        ('10k/1W', Fraction(10000), None, 1.0)]:
            with self.subTest(value=value):
                row = parse_resistor(value, exact=True)
                self.assertIsNotNone(row)
                self.assertEqual(Fraction(row['ohm_exact']), ohms)
                self.assertEqual(Fraction(row['tol_exact']) if row['tol_exact'] else None, tol)
                self.assertEqual(row['power_w'], watts)
        self.assertNotIn('power_w', parse_resistor('1k5/1%'))

    def test_a_rated_voltage_is_read_like_the_rated_power(self):
        for value, ohms, watts, volts in [('1M/1%/250V', Fraction(1000000), None, 250.0),
                                          ('1M/250V', Fraction(1000000), None, 250.0),
                                          ('1k/1%/0.25W/200V', Fraction(1000), 0.25, 200.0),
                                          ('1k/1%/200V/0.25W/R1206', Fraction(1000), 0.25, 200.0)]:
            with self.subTest(value=value):
                row = parse_resistor(value, exact=True)
                self.assertEqual(Fraction(row['ohm_exact']), ohms)
                self.assertEqual((row.get('power_w'), row.get('voltage_v')), (watts, volts))

    def test_an_unknown_word_or_a_rating_out_of_place_still_fails_closed(self):
        for value in ['47R/1%/2W/pulse', '1k5/1W/1%', '1k5/1%/1W/2W', '1k5/1%/0W', '1k5/1%/R0603/1W', '1k5/1%/1Wjunk',
                      '1M/1%/250V/300V', '1M/250V/1%', '1k/1%/0V']:
            with self.subTest(value=value):
                self.assertIsNone(parse_resistor(value))

    def test_invalid_tolerance_and_units_still_fail_closed(self):
        for value in ['330k/100%/R0402', '330k/-1%/R0402',
                      '330kx/1%/R0402', '330k/NaN%/R0402', 'junk/1%/R0402']:
            self.assertIsNone(parse_resistor(value), value)


if __name__ == '__main__':
    unittest.main()

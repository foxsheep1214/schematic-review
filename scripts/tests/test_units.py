"""The unit table (item 2 of the 2026-10-26 SR review): spellings the review writes, scales, plausible spans."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import units


class UnitTableTests(unittest.TestCase):
    def test_spellings_the_reviews_write_are_known(self):
        for spelling, dimension in (('V', 'voltage'), ('Vac', 'voltage'), ('kV', 'voltage'), ('mA', 'current'), ('Arms', 'current'),
                                    ('kΩ', 'resistance'), ('kohm', 'resistance'), ('mΩ', 'resistance'), ('µF', 'capacitance'),
                                    ('uF', 'capacitance'), ('nF', 'capacitance'), ('µH', 'inductance'), ('kHz', 'frequency'),
                                    ('µs', 'time'), ('ms', 'time'), ('h', 'time'), ('°C', 'temperature'), ('K', 'temperature'),
                                    ('%', 'ratio'), ('ratio', 'ratio'), ('x', 'ratio'), ('V/V', 'ratio'), ('A²s', 'i2t'),
                                    ('A2s', 'i2t'), ('mV/K', 'tempco'), ('°C/W', 'thermal_resistance'), ('J', 'energy'),
                                    ('nC', 'charge'), ('mT', 'flux_density'), ('mm', 'length'), ('degree', 'angle'), ('kB', 'data')):
            self.assertEqual((units.parse(spelling) or (None,))[0], dimension, spelling)
        self.assertEqual(units.parse('kohm')[1], 1e3)
        self.assertEqual(units.parse('µs')[1], units.parse('us')[1])
        self.assertIsNone(units.parse('foo'))
        self.assertIsNone(units.parse(None))

    def test_case_tells_seconds_from_siemens_and_milli_from_mega(self):
        self.assertEqual(units.parse('ms')[0], 'time')
        self.assertEqual(units.parse('mS')[0], 'conductance')
        self.assertEqual(units.parse('MΩ')[1], 1e6)
        self.assertEqual(units.parse('mΩ')[1], 1e-3)

    def test_plausibility_catches_a_prefix_slip_and_leaves_ordinary_values_alone(self):
        self.assertTrue(units.plausible(22, 'µF'))
        self.assertFalse(units.plausible(22, 'kF'))        # 22 kF: a prefix slip
        self.assertFalse(units.plausible(5e6, 'A'))
        self.assertTrue(units.plausible(1e11, 'ohm'))      # insulation resistance
        self.assertFalse(units.plausible(-300, '°C'))
        self.assertTrue(units.plausible(-40, '°C'))
        self.assertFalse(units.plausible(1e-9, 'V'))       # a limit of 1 nV
        self.assertTrue(units.plausible(1e-9, 'V', lower=False))   # a margin may be tiny
        self.assertTrue(units.plausible(0, 'V'))
        self.assertIsNone(units.plausible(3, 'ratio'))     # no span for a ratio
        self.assertIsNone(units.plausible(3, 'foo'))
        self.assertIsNone(units.plausible('3', 'V'))

    def test_quantities_in_prose(self):
        found = units.quantities('VRAW 4.75 V 时 ≥ 14.9 V；≤ 160 kHz，36 nC，1.2x，p7 Table 7，−10..105 °C，R2 的 4.7 kΩ')
        self.assertEqual(found, [(4.75, 'V'), (14.9, 'V'), (160.0, 'kHz'), (36.0, 'nC'), (1.2, 'x'), (105.0, '°C'), (4.7, 'kΩ')])
        self.assertEqual(units.quantities(None), [])


if __name__ == '__main__':
    unittest.main()

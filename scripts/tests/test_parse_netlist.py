import pathlib
import sys
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from parse_netlist import is_not_populated, parse_pstchip


class ParsePstchipTests(unittest.TestCase):
    def test_pinuse_accepts_alphanumeric_pin_and_intervening_property(self):
        text = """
primitive 'SOC_BGA';
  PART_NAME='SOC-X';
  JEDEC_TYPE='BGA';
  VALUE='SOC-X';
  'GPIO0':
    PIN_NUMBER='(A12)';
    PIN_GROUP='IOBANK0';
    PINUSE='BI';
  'VSS':
    PIN_NUMBER='(B2)';
    PINUSE='GROUND';
end_primitive;
"""
        primitive = parse_pstchip(text)['SOC_BGA']
        self.assertEqual(primitive['pins'], {'GPIO0': 'A12', 'VSS': 'B2'})
        self.assertEqual(
            primitive['pinuse'], {'GPIO0': 'BI', 'VSS': 'GROUND'})


class NotPopulatedTests(unittest.TestCase):
    def test_slash_nc_suffix_marks_instance_as_not_populated(self):
        self.assertTrue(is_not_populated('CAP_C0402_0.1UF/NC', '0.1uF/50V'))
        self.assertTrue(is_not_populated('RES_R0402_1K', '1K/1%/NC'))

    def test_underscore_nc_suffix_marks_instance_as_not_populated(self):
        self.assertTrue(is_not_populated('RES_R0402_1K/1%_NC', '1K/1%_NC'))
        self.assertTrue(is_not_populated('BEAD_FB0402_120OHM/1A_NC', '120ohm/1A'))

    def test_populated_parts_are_not_flagged(self):
        self.assertFalse(is_not_populated('RES_R0402_10K/1%', '10K/1%'))
        self.assertFalse(is_not_populated('', ''))
        self.assertFalse(is_not_populated(None, None))

    def test_nc_inside_a_word_is_not_an_nc_marker(self):
        self.assertFalse(is_not_populated('NCP1117_SOT223', 'NCP1117ST33T3G'))
        self.assertFalse(is_not_populated('CONN_INCLUDE_1', 'INCLUDE'))


if __name__ == '__main__':
    unittest.main()

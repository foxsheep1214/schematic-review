import pathlib
import sys
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from parse_netlist import parse_pstchip


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


if __name__ == '__main__':
    unittest.main()

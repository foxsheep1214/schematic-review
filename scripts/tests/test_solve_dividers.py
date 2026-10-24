import pathlib
import sys
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from solve_dividers import parse_resistor


def divider_db(parallel=False, series_lower=False):
    parts = {
        'U1': {'value': 'REG', 'nc': False},
        'R1': {'value': '20K/1%', 'nc': False},
        'R2': {'value': '10K/1%', 'nc': False},
    }
    nets = {
        'VOUT_3V3': ['R1.1'],
        'FB_NET': ['U1.1', 'R1.2', 'R2.1'],
        'GND': ['R2.2'],
    }
    if parallel:
        parts['R3'] = {'value': '20K/1%', 'nc': False}
        nets['VOUT_3V3'].append('R3.1')
        nets['FB_NET'].append('R3.2')
    if series_lower:
        parts['R2']['value'] = '5K/1%'
        parts['R4'] = {'value': '5K/1%', 'nc': False}
        nets['FB_NET'] = ['U1.1', 'R1.2', 'R2.1']
        nets['MID'] = ['R2.2', 'R4.1']
        nets['GND'] = ['R4.2']
    pin2net = {
        node: net for net, nodes in nets.items() for node in nodes
    }
    return {
        'nets': nets,
        'parts': parts,
        'pin2net': pin2net,
        'pinname': {'U1.1': 'FB'},
        'pintype': {},
        'ref2page': {},
        'pseudo_nets': [],
    }


class ResistorParserTests(unittest.TestCase):
    def test_embedded_unit_and_tolerance(self):
        parsed = parse_resistor('4K7/0.5%')
        self.assertAlmostEqual(parsed['kohm'], 4.7)
        self.assertAlmostEqual(parsed['tol'], 0.005)

    def test_leading_r_notation(self):
        self.assertAlmostEqual(parse_resistor('R010/1%')['kohm'], 0.00001)


if __name__ == '__main__':
    unittest.main()

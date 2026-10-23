"""A net counts as a supply by what is on it; a tool-generated net name does not become a rail through a capacitor alone.

On one board an indicator LED's anode node (named by the tool after the LED pin) had a 2.2 µF smoothing capacitor to
ground and a declared voltage window, so it was listed as a power domain to monitor and budget. A capacitor to ground
makes a named net a supply; a tool-generated name needs an IC supply pin on it.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from checkers import powertree
from checkers.netgraph import NetGraph, is_auto_named


def board(net, with_ic=False):
    nodes = {'C1.1': net, 'C1.2': 'GND', 'D1.1': net, 'D1.2': 'GND'}
    parts = {'C1': {'value': '2.2u/10V'}, 'D1': {'value': 'LED'}}
    if with_ic:
        nodes['U1.1'], nodes['U1.2'] = net, 'GND'
        parts['U1'] = {'value': 'REG'}
    nets = {}
    for node, n in nodes.items():
        nets.setdefault(n, []).append(node)
    db = {'parts': parts, 'nets': nets, 'pin2net': nodes, 'pinname': {'U1.1': 'VCC', 'U1.2': 'GND'},
          'pintype': {}, 'native_pintype': {'U1.1': 'power_in'}}
    intent = {'power_rails': {net: {'voltage_v': {'min': 0, 'max': 4}}}}
    return NetGraph(db), intent


class SupplyNetNameTests(unittest.TestCase):
    def test_a_tool_named_node_with_only_a_capacitor_is_not_a_rail(self):
        self.assertEqual(powertree.declared_supply_nets(*board('Net-(D1-A)')), set())
        self.assertEqual(powertree.declared_supply_nets(*board('/Sheet1/Net-(D1-A)')), set())
        self.assertEqual(powertree.declared_supply_nets(*board('VLED')), {'VLED'})

    def test_an_ic_supply_pin_still_makes_a_tool_named_net_a_rail(self):
        self.assertEqual(powertree.declared_supply_nets(*board('Net-(U1-VCC)', with_ic=True)), {'Net-(U1-VCC)'})

    def test_tool_generated_names(self):
        for net in ('Net-(R1-Pad2)', 'unconnected-(U1-NC-Pad5)', '/PSU/Net-(D1-K)'):
            self.assertTrue(is_auto_named(net), net)
        for net in ('VCC_3V3', 'NET_A', 'Network'):
            self.assertFalse(is_auto_named(net), net)


if __name__ == '__main__':
    unittest.main()

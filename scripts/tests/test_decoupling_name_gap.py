"""A missing function name on a pin fixed by the official pin map must not block decoupling.

KiCad op-amp symbols (LM358, AD8494) leave the output unnamed. The parser's
self-check then fails on that name alone; decoupling reads pin roles from
intent.devices first, so a complete official map already settles the pin.
"""
import pathlib
import sys
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import checkers  # noqa: E402,F401  (load order used by the other decoupling tests)
from decoupling import Inventory  # noqa: E402
from parse_kicad import parse  # noqa: E402
from parse_netlist import self_check  # noqa: E402
from test_parse_kicad import LIBPARTS, comp, net, netlist  # noqa: E402

GAP = 'netlist-integrity/export'
AMP = LIBPARTS.replace('</libparts>', """
    <libpart lib="Device" part="C">
      <pins>
        <pin num="1" name="~" type="passive"/>
        <pin num="2" name="~" type="passive"/>
      </pins>
    </libpart>
    <libpart lib="Amplifier" part="AMP">
      <pins>
        <pin num="1" name="~" type="output"/>
        <pin num="2" name="IN" type="input"/>
        <pin num="3" name="VCC" type="power_in"/>
        <pin num="4" name="GND" type="power_in"/>
      </pins>
    </libpart>
    <libpart lib="Amplifier" part="AMPN">
      <pins>
        <pin num="1" name="OUT" type="output"/>
        <pin num="2" name="IN" type="input"/>
        <pin num="3" name="VCC" type="power_in"/>
        <pin num="4" name="GND" type="power_in"/>
      </pins>
    </libpart>
  </libparts>""")


def parsed_db(second=False):
    parts = comp('U9', 'Amplifier', 'AMP', 'AMP') + comp('C1', 'Device', 'C', '100nF')
    nets = (net('OUT', ('U9', '1', '', 'output')) + net('A', ('U9', '2', 'IN', 'input'))
            + net('VCC', ('U9', '3', 'VCC', 'power_in'), ('C1', '1', '', 'passive')))
    gnd = [('U9', '4', 'GND', 'power_in'), ('C1', '2', '', 'passive')]
    if second:  # a fully named device on its own rail
        parts += comp('U2', 'Amplifier', 'AMPN', 'AMPN') + comp('C2', 'Device', 'C', '100nF')
        nets += (net('OUT2', ('U2', '1', 'OUT', 'output')) + net('B', ('U2', '2', 'IN', 'input'))
                 + net('VDD', ('U2', '3', 'VCC', 'power_in'), ('C2', '1', '', 'passive')))
        gnd += [('U2', '4', 'GND', 'power_in'), ('C2', '2', '', 'passive')]
    xml = netlist(parts, nets + net('GND', *gnd), libparts=AMP)
    db = parse(xml)
    db['integrity'] = {'self_check_passed': self_check(db, strict=False)}
    return db


def devices(complete=True, out_role='other'):
    pins = {'1': {'name': 'OUT', 'role': out_role}, '2': {'name': 'IN', 'role': 'other'},
            '3': {'name': 'VCC', 'role': 'power'}, '4': {'name': 'GND', 'role': 'return'}}
    if out_role is None:
        del pins['1']
    return {'U9': {'mpn': 'AMP', 'package': 'SO-4', 'identity_citation': 'synthetic', 'citation': 'synthetic p1',
                   'pinout_complete': complete, 'pins': pins}}


def state_groups(inv, fitted=('C1',)):
    """Groups of one fully populated state, keyed by device ref."""
    state = {'id': 'S', 'population': {ref: True for ref in ('U9', 'U2') + tuple(fitted)}}
    out = {}
    for group in inv.state_inventory(state, inv.groups(), inv.device_inventory())['groups']:
        out.setdefault(group['ref'], []).append(group)
    return out


class NameGapTests(unittest.TestCase):
    def test_fixture_fails_self_check_only_on_the_unnamed_output(self):
        db = parsed_db()
        self.assertIs(db['integrity']['self_check_passed'], False)
        self.assertEqual(db['pin_name_coverage']['missing_functional_pins'], ['U9.1'])
        from parse_netlist import integrity_problems
        self.assertEqual(len(integrity_problems(dict(db))), 1)

    def test_complete_official_map_resolves_the_name_gap(self):
        inv = Inventory(parsed_db(), {}, devices())
        self.assertNotIn(GAP, inv.input_gaps)
        self.assertEqual(inv.names_resolved_by_official_pinout, ['U9.1'])

    def test_unresolved_name_stays_a_gap_of_its_own_device(self):
        for devs in ({}, devices(complete=False), devices(out_role=None)):
            with self.subTest(devices=devs):
                inv = Inventory(parsed_db(), {}, devs)
                self.assertNotIn(GAP, inv.input_gaps)
                self.assertEqual(inv.names_resolved_by_official_pinout, [])
                self.assertEqual(inv.unresolved_pin_names, ['U9.1'])
                groups = state_groups(inv)
                self.assertTrue(groups['U9'])
                for group in groups['U9']:
                    self.assertIn('pin-name-unresolved:U9.1', group['gaps'])

    def test_unresolved_name_does_not_spread_to_other_devices(self):
        db = parsed_db(second=True)
        self.assertEqual(db['pin_name_coverage']['missing_functional_pins'], ['U9.1'])
        inv = Inventory(db, {}, {})
        groups = state_groups(inv, ('C1', 'C2'))
        self.assertTrue(groups['U2'])
        for group in groups['U2']:
            self.assertFalse([g for g in group['gaps'] if g.startswith('pin-name') or g == GAP])
            self.assertEqual(group['fitted_capacitors'], ['C2'])
        for group in groups['U9']:
            self.assertIn('pin-name-unresolved:U9.1', group['gaps'])

    def test_discovery_keeps_the_unresolved_name(self):
        from decoupling import build_decoupling_inventory
        inventory = build_decoupling_inventory(parsed_db(second=True), {})
        self.assertIn('pin-name-unresolved:U9.1', inventory['discovery_gaps'])
        self.assertNotIn(GAP, inventory['discovery_gaps'])

    def test_any_other_self_check_problem_keeps_the_gap(self):
        db = parsed_db()
        db['ref2page'] = {}  # an IC without page mapping is a second, unrelated integrity problem
        self.assertIn(GAP, Inventory(db, {}, devices()).input_gaps)
        db = parsed_db()
        db['export_errors'] = ['ERROR (1): aborting']
        self.assertIn(GAP, Inventory(db, {}, devices()).input_gaps)


if __name__ == '__main__':
    unittest.main()

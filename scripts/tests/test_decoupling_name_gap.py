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
  </libparts>""")


def parsed_db():
    xml = netlist(
        comp('U9', 'Amplifier', 'AMP', 'AMP') + comp('C1', 'Device', 'C', '100nF'),
        net('OUT', ('U9', '1', '', 'output')) + net('A', ('U9', '2', 'IN', 'input'))
        + net('VCC', ('U9', '3', 'VCC', 'power_in'), ('C1', '1', '', 'passive'))
        + net('GND', ('U9', '4', 'GND', 'power_in'), ('C1', '2', '', 'passive')),
        libparts=AMP)
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

    def test_gap_stays_without_a_complete_official_map(self):
        for devs in ({}, devices(complete=False), devices(out_role=None)):
            with self.subTest(devices=devs):
                inv = Inventory(parsed_db(), {}, devs)
                self.assertIn(GAP, inv.input_gaps)
                self.assertEqual(inv.names_resolved_by_official_pinout, [])

    def test_any_other_self_check_problem_keeps_the_gap(self):
        db = parsed_db()
        db['ref2page'] = {}  # an IC without page mapping is a second, unrelated integrity problem
        self.assertIn(GAP, Inventory(db, {}, devices()).input_gaps)
        db = parsed_db()
        db['export_errors'] = ['ERROR (1): aborting']
        self.assertIn(GAP, Inventory(db, {}, devices()).input_gaps)


if __name__ == '__main__':
    unittest.main()

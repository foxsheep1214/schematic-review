"""Interfaces between the board's owners, derived from part ownership and the netlist (function-tree design §3.3, step 3).

A net that joins pins of two owners is an interface net between them; the nets between one pair make one interface.
Ground nets are never interface nets. Four kinds: a pair of ordinary circuits (IF-), a cross-cutting chain with the
parts it owns (LINK-), a rail from its source to its loads (RAIL-) and a connector's pins (EXT-). Every endpoint
names its owner, pin, role, reference domain and supply; a pin whose role the pin type, the part kind, the pin name
or the power tree cannot give is a gap, and the interface is still made. Interface ids use the circuits' candidate
ids, so a renamed circuit keeps its interfaces.
"""
import copy
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import circuit_decisions as cd
import interfaces
from plan_review import build_review_plan
import test_circuit_decisions as dfx

GOLDEN = Path(__file__).resolve().parent / 'fixtures' / 'interfaces-flyback-usb.json'
GROUNDS = {'PGND', 'SGND'}


def derived(decisions=None):
    db, intent, audit, candidates = dfx.setup()
    intent['circuit_decisions'] = decisions or dfx.accept_all(candidates)
    intent = cd.write_circuits(intent, candidates)
    return interfaces.derive(db, intent, audit), (db, intent, audit, candidates)


def nets(item):
    return {n['net'] for n in item['nets']}


class InterfaceTests(unittest.TestCase):
    def setUp(self):
        self.section, self.inputs = derived()
        self.by_id = {i['id']: i for i in self.section['interfaces']}

    def test_two_circuits_share_one_interface_holding_every_net_between_them(self):
        self.assertEqual(nets(self.by_id['IF-ANALOG-U4~POWER_CONVERTER-U1']), {'FB_LED'})
        self.assertEqual(nets(self.by_id['IF-ANALOG-U5~USB-J2']) & {'CC1', 'FLT_DRV', 'PORT_G'}, {'CC1', 'FLT_DRV', 'PORT_G'})
        self.assertEqual(self.by_id['IF-ANALOG-U5~USB-J2']['kind'], 'CIRCUIT_PAIR')
        self.assertEqual(self.by_id['IF-ANALOG-U5~USB-J2']['owners'], ['ANALOG-U5', 'USB-J2'])

    def test_a_ground_net_is_never_an_interface_net_outside_a_connector_pinout(self):
        for item in self.section['interfaces']:
            if item['kind'] != 'EXTERNAL':
                self.assertFalse(nets(item) & GROUNDS, item['id'])

    def test_a_chain_is_a_link_interface_with_its_own_parts_and_takes_the_nets_it_touches(self):
        fault = self.by_id['LINK-POWER_PROTECTION-U1.FAULT']
        self.assertEqual((fault['kind'], fault['parts'], nets(fault)), ('LINK', ['C41', 'R42', 'U9'], {'FLT', 'FLT_A'}))
        self.assertEqual(nets(self.by_id['LINK-STARTUP-U1.HV']), {'HV_IN', 'RECT'})
        self.assertEqual(self.by_id['LINK-ISOLATION-PRI/SEC']['parts'], ['CY1'])
        pair_nets = set().union(*(nets(i) for i in self.section['interfaces'] if i['kind'] == 'CIRCUIT_PAIR'))
        self.assertFalse(pair_nets & {'FLT', 'FLT_A', 'HV_IN'})   # a net reaching a chain's own part is the chain's

    def test_a_rail_feeding_several_owners_is_a_supply_interface(self):
        vout = self.by_id['RAIL-VOUT']
        self.assertEqual(vout['kind'], 'SUPPLY')
        self.assertLessEqual({'ANALOG-U4', 'ANALOG-U5', 'POWER_CONVERTER-U1', 'POWER_CONVERTER-U7', 'USB-J2'}, set(vout['owners']))
        self.assertEqual(vout['source'], 'POWER_CONVERTER-U1')        # its rectifier's owner
        self.assertEqual(self.by_id['RAIL-RECT']['source'], 'POWER_PROTECTION-J1')   # the bridge's + pin
        self.assertEqual(self.by_id['RAIL-V5']['source'], 'ANALOG-U5')               # the power tree's output pin
        self.assertNotIn('RAIL-V3V3', self.by_id)   # one owner only: an internal node of the buck
        self.assertNotIn('RAIL-HV_IN', self.by_id)  # a rail-like name with no source and no declaration
        self.assertNotIn('RAIL-VBUS', self.by_id)

    def test_a_rail_whose_only_source_pin_the_library_calls_an_input_has_no_source_and_a_gap(self):
        db, intent, audit, _ = self.inputs
        db = copy.deepcopy(db)
        db['pintype']['U5.4'] = 'IN'
        section = interfaces.derive(db, intent, audit)
        v5 = next(i for i in section['interfaces'] if i['id'] == 'RAIL-V5')
        self.assertIsNone(v5['source'])
        self.assertIn({'interface': 'RAIL-V5', 'pin': None, 'reason': 'source'}, section['gaps'])

    def test_a_connector_is_an_external_interface_over_all_its_pins(self):
        self.assertEqual(nets(self.by_id['EXT-J1']), {'AC_L', 'AC_N'})
        self.assertLessEqual({'VBUS', 'CC1', 'DP', 'DN', 'SGND'}, nets(self.by_id['EXT-J2']))
        self.assertNotIn('EXT-TP1', self.by_id)   # a test point is not a connector

    def test_endpoints_carry_role_domain_and_supply_and_an_unknown_role_is_a_gap(self):
        ends = {e['pin']: e for i in self.section['interfaces'] for n in i['nets'] for e in n['endpoints']}
        self.assertEqual(ends['U5.5']['role'], 'DRIVER')            # GATE
        self.assertEqual(ends['U5.3']['role'], 'BIDIRECTIONAL')     # CC1
        self.assertEqual(ends['R8.1']['role'], 'PASSIVE')
        self.assertEqual(ends['U3.1']['role'], 'RECEIVER')          # the optocoupler's LED anode
        self.assertEqual(ends['U7.1']['role'], 'RECEIVER')          # VIN
        self.assertEqual(ends['U7.1']['supply'], ['VOUT'])
        self.assertEqual(ends['U5.3']['owner'], 'ANALOG-U5')
        self.assertEqual(ends['U3.1']['domain'], 'SEC')            # the secondary's reference
        self.assertIsNone(ends['U1.7']['role'])                     # FAULT: no pin type, no name the rules know
        gaps = {(g['interface'], g['pin']) for g in self.section['gaps']}
        self.assertIn(('LINK-POWER_PROTECTION-U1.FAULT', 'U1.7'), gaps)
        self.assertIn(('IF-ANALOG-U4~POWER_CONVERTER-U1', 'U4.3'), gaps)
        self.assertNotIn('U5.3', {pin for _, pin in gaps})
        self.assertEqual({pin for i, pin in gaps if i == 'EXT-J2'}, set())   # the pinout's return pin alone, not every ground pin

    def test_a_renamed_circuit_keeps_its_interfaces_and_shows_its_new_name(self):
        db, intent, audit, candidates = self.inputs
        renamed, _ = derived(dfx.accept_all(candidates, **{'ANALOG-U5': {
            'candidate': 'ANALOG-U5', 'decision': 'accept', 'id': 'PD'}}))
        strip = lambda s: {i['id']: sorted(nets(i)) for i in s['interfaces']}
        self.assertEqual(strip(renamed), strip(self.section))
        pair = next(i for i in renamed['interfaces'] if i['id'] == 'IF-ANALOG-U5~USB-J2')
        self.assertEqual(pair['owners'], ['PD', 'USB-J2'])

    def test_the_plan_carries_the_interfaces(self):
        db, intent, audit, candidates = self.inputs
        plan = build_review_plan(db, intent, datasheet_audit=audit, candidates=candidates)
        self.assertEqual(plan['interfaces'], self.section)

    def test_the_synthetic_board_matches_its_golden_file(self):
        if os.environ.get('SR_WRITE_GOLDEN'):
            GOLDEN.write_text(json.dumps(self.section, ensure_ascii=False, indent=1, sort_keys=True) + '\n', encoding='utf-8')
        self.assertEqual(self.section, json.loads(GOLDEN.read_text(encoding='utf-8')))


if __name__ == '__main__':
    unittest.main()

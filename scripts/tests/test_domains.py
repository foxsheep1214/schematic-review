"""Ground domains, barrier parts and rail stops are derived from the netlist, not drawn by the reviewer.

A domain is the set of nets that reach one ground through DC-conducting parts (capacitors, transformers,
optocouplers, relays, crystals, connectors and declared isolators do not conduct). A barrier is a part whose
pins touch two domains. A rail stop is where a circuit-candidate walk ends: a ground, a net an IC output pin
drives, or a declared rail that two or more anchors reach within one two-terminal hop. The synthetic board
is an isolated flyback with a shunt-reference feedback loop and a PD controller on the secondary.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import board_intent
from checkers import domains
from checkers import netgraph as ng
from plan_review import build_review_plan
import test_inductive_load as fixture


def flyback():
    db = {'nets': {}, 'parts': {}, 'pin2net': {}, 'pinname': {}, 'pintype': {}, 'pseudo_nets': [], 'ref2page': {}}
    add = fixture.add
    add(db, 'J1', 'Connector:AC_IN', [('1', 'L', 'AC_L'), ('2', 'N', 'AC_N')])
    add(db, 'F1', 'FUSE-2A', [('1', '1', 'AC_L'), ('2', '2', 'L_F')])
    add(db, 'BR1', 'BRIDGE', [('1', 'AC1', 'L_F'), ('2', 'AC2', 'AC_N'), ('3', '+', 'RECT'), ('4', '-', 'PGND')])
    add(db, 'C1', '82uF', [('1', '1', 'RECT'), ('2', '2', 'PGND')])
    add(db, 'U1', 'PWM-CTRL', [('1', 'VCC', 'VCC'), ('2', 'GND', 'PGND'), ('3', 'DRV', 'GATE'),
                               ('4', 'FB', 'FB'), ('5', 'HV', 'RECT'), ('6', 'CS', 'CS')])
    add(db, 'Q1', 'MOSFET-N', [('1', 'G', 'GATE'), ('2', 'D', 'SW'), ('3', 'S', 'CS')])
    add(db, 'R2', '0R33', [('1', '1', 'CS'), ('2', '2', 'PGND')])
    add(db, 'T1', 'XFMR', [('1', '1', 'RECT'), ('2', '2', 'SW'), ('3', '3', 'AUX'), ('4', '4', 'PGND'),
                           ('5', '5', 'SEC_SW'), ('6', '6', 'SGND')])
    add(db, 'D3', 'DIODE', [('1', 'A', 'AUX'), ('2', 'K', 'VCC')])
    add(db, 'C4', '22uF', [('1', '1', 'VCC'), ('2', '2', 'PGND')])
    add(db, 'D2', 'SCHOTTKY', [('1', 'A', 'SEC_SW'), ('2', 'K', 'VOUT')])
    add(db, 'C3', '470uF', [('1', '1', 'VOUT'), ('2', '2', 'SGND')])
    add(db, 'U3', 'PC817', [('1', 'A', 'FB_LED'), ('2', 'K', 'SGND'), ('3', 'C', 'FB'), ('4', 'E', 'PGND')])
    add(db, 'R7', '1K', [('1', '1', 'VOUT'), ('2', '2', 'FB_LED')])
    add(db, 'U4', 'TL431', [('1', 'REF', 'FB_DIV'), ('2', 'A', 'SGND'), ('3', 'K', 'FB_LED')])
    add(db, 'R5', '47K', [('1', '1', 'VOUT'), ('2', '2', 'FB_DIV')])
    add(db, 'R6', '10K', [('1', '1', 'FB_DIV'), ('2', '2', 'SGND')])
    add(db, 'CY1', '2.2nF', [('1', '1', 'PGND'), ('2', '2', 'SGND')])
    add(db, 'U5', 'PD-CTRL', [('1', 'VBUS_IN', 'VOUT'), ('2', 'GND', 'SGND'), ('3', 'CC1', 'CC1'),
                              ('4', 'VOUT', 'V5'), ('5', 'GATE', 'VBUS_G')])
    add(db, 'C6', '1uF', [('1', '1', 'V5'), ('2', '2', 'SGND')])
    add(db, 'C7', '100nF', [('1', '1', 'FLOAT_A'), ('2', '2', 'FLOAT_B')])
    return db


KINDS = {'U1': 'pwm_controller', 'U3': 'opto', 'U4': 'shunt_reference', 'U5': 'pd_controller', 'BR1': 'bridge_rectifier'}


def intent_for(db, kinds=KINDS, rails=None):
    intent = {'schema_version': 5, 'input_sha256': board_intent.input_fingerprint(db), 'device_kinds': {},
              'power_rails': rails if rails is not None else {
                  'PGND': {'voltage_v': {'min': 0, 'max': 0}, 'domain': 'PRI'},
                  'SGND': {'voltage_v': {'min': 0, 'max': 0}, 'domain': 'SEC'},
                  'VOUT': {'voltage_v': {'min': 19, 'max': 21}},
                  'VCC': {'voltage_v': {'min': 10, 'max': 16}},
                  'RECT': {'voltage_v': {'min': 120, 'max': 375}}}}
    audit = {'device_kinds': {}}
    for ref, kind in kinds.items():
        declaration = {'kind': kind, 'page': 1, 'quote': 'synthetic ' + kind}
        intent['device_kinds'][ref] = declaration
        audit['device_kinds'][ref] = dict(declaration, status='VERIFIED', document='synthetic.pdf',
                                          document_sha256='a' * 64)
    return board_intent.with_verified_kinds(intent, audit)


def derive(db=None, **kw):
    db = db or flyback()
    intent = intent_for(db, **kw)
    return domains.derive(ng.NetGraph(board_intent.graph_db(db, intent)), intent)


class DomainTests(unittest.TestCase):
    def test_nets_take_the_domain_of_the_ground_they_conduct_to(self):
        section = derive()
        self.assertEqual(section['grounds'], {'PGND': 'PRI', 'SGND': 'SEC'})
        nets = section['nets']
        for net in ('RECT', 'L_F', 'AC_N', 'VCC', 'AUX', 'GATE', 'SW', 'CS', 'FB'):
            self.assertEqual(nets[net], 'PRI', net)
        for net in ('VOUT', 'SEC_SW', 'FB_LED', 'FB_DIV', 'V5', 'CC1', 'VBUS_G'):
            self.assertEqual(nets[net], 'SEC', net)
        self.assertEqual(sorted(section['domains']), ['PRI', 'SEC'])

    def test_capacitors_transformers_optocouplers_and_connectors_do_not_conduct(self):
        section = derive()
        # AC_L reaches L_F only through the connector J1 and the fuse: the fuse conducts, so AC_L is PRI
        self.assertEqual(section['nets']['AC_L'], 'PRI')
        # a net only capacitors touch reaches no ground
        self.assertIsNone(section['nets']['FLOAT_A'])
        self.assertEqual(section['unreferenced'], ['FLOAT_A', 'FLOAT_B'])
        self.assertEqual(section['conflicts'], [])

    def test_parts_spanning_two_domains_are_barriers(self):
        section = derive()
        barriers = {b['ref']: b for b in section['barriers']}
        self.assertEqual(sorted(barriers), ['CY1', 'T1', 'U3'])
        self.assertEqual(barriers['T1']['domains'], ['PRI', 'SEC'])
        self.assertEqual(barriers['U3']['kind'], 'opto')
        self.assertEqual(barriers['CY1']['kind'], 'capacitor')

    def test_undeclared_ground_is_its_own_domain_named_after_the_net(self):
        section = derive(rails={})
        self.assertEqual(section['grounds'], {'PGND': 'PGND', 'SGND': 'SGND'})
        self.assertEqual(section['nets']['VOUT'], 'SGND')

    def test_two_grounds_declared_in_one_domain_form_one_domain(self):
        db = flyback()
        fixture.add(db, 'R9', '0R', [('1', '1', 'PGND'), ('2', '2', 'SGND')])
        section = derive(db, rails={'PGND': {'voltage_v': {'min': 0, 'max': 0}, 'domain': 'LV'},
                                    'SGND': {'voltage_v': {'min': 0, 'max': 0}, 'domain': 'LV'}})
        self.assertEqual(section['grounds'], {'PGND': 'LV', 'SGND': 'LV'})
        self.assertEqual(section['conflicts'], [])
        self.assertEqual(section['barriers'], [])

    def test_a_conducting_part_across_two_declared_domains_is_a_conflict(self):
        db = flyback()
        fixture.add(db, 'R9', '1M', [('1', '1', 'PGND'), ('2', '2', 'SGND')])
        section = derive(db)
        self.assertEqual([c['code'] for c in section['conflicts']], ['DOMAIN_MERGED'])
        self.assertEqual(section['conflicts'][0]['via'], ['R9'])
        self.assertEqual(section['conflicts'][0]['domains'], ['PRI', 'SEC'])

    def test_a_declared_net_domain_that_disagrees_with_the_netlist_is_a_conflict(self):
        db = flyback()
        section = derive(db, rails={'PGND': {'voltage_v': {'min': 0, 'max': 0}, 'domain': 'PRI'},
                                    'SGND': {'voltage_v': {'min': 0, 'max': 0}, 'domain': 'SEC'},
                                    'VOUT': {'voltage_v': {'min': 19, 'max': 21}, 'domain': 'PRI'}})
        self.assertEqual(section['conflicts'], [{'code': 'DOMAIN_CONFLICT', 'net': 'VOUT', 'declared': 'PRI', 'derived': 'SEC'}])

    def test_a_declared_return_window_is_a_ground_too(self):
        db = flyback()
        section = derive(db, rails={'PGND': {'voltage_v': {'min': 0, 'max': 0}, 'domain': 'PRI'},
                                    'SGND': {'voltage_v': {'min': 0, 'max': 0}, 'domain': 'SEC'},
                                    'CS': {'voltage_v': {'min': -1, 'max': 0}}})
        self.assertNotIn('CS', section['grounds'])      # a sense net bounded at 0 V is still a signal, PRI by conduction
        self.assertEqual(section['nets']['CS'], 'PRI')


class RailStopTests(unittest.TestCase):
    def test_grounds_driver_outputs_and_shared_declared_rails_are_stops(self):
        section = derive()
        stops = section['rail_stops']
        self.assertEqual(stops['PGND'], 'ground')
        self.assertEqual(stops['SGND'], 'ground')
        self.assertEqual(stops['V5'], 'driver')                # U5.VOUT output pin drives it
        self.assertEqual(stops['VOUT'], 'anchors:U4,U5')      # declared; U5 directly, U4 through R5
        self.assertNotIn('VCC', stops)                        # declared but only U1 reaches it
        self.assertNotIn('RECT', stops)                       # declared; U1.HV only
        self.assertNotIn('SW', stops)
        self.assertNotIn('GATE', stops)

    def test_a_bypass_capacitor_to_ground_does_not_let_the_grounds_anchors_reach_the_net(self):
        db = flyback()
        fixture.add(db, 'U6', 'GATE-DRV', [('1', 'VDD', 'VDRV'), ('2', 'GND', 'PGND'), ('3', 'IN', 'GATE'), ('4', 'OUT', 'GATE2')])
        fixture.add(db, 'C8', '1uF', [('1', '1', 'VDRV'), ('2', '2', 'PGND')])
        section = derive(db, kinds=dict(KINDS, U6='gate_driver'))
        stops = section['rail_stops']
        self.assertNotIn('VCC', stops)       # U6 sits on PGND with U1, which C4 bypasses: that is not reaching VCC
        self.assertNotIn('RECT', stops)
        self.assertNotIn('GATE', stops)      # two anchors reach it, but it is not a declared rail

    def test_a_return_named_net_is_a_ground(self):
        db = flyback()
        fixture.add(db, 'R10', '0R', [('1', '1', 'SGND'), ('2', '2', 'SEC_RTN')])
        fixture.add(db, 'C9', '10uF', [('1', '1', 'VOUT'), ('2', '2', 'SEC_RTN')])
        section = derive(db, rails={'PGND': {'voltage_v': {'min': 0, 'max': 0}, 'domain': 'PRI'},
                                    'SGND': {'voltage_v': {'min': 0, 'max': 0}, 'domain': 'SEC'},
                                    'SEC_RTN': {'domain': 'SEC'}})
        self.assertEqual(section['grounds'], {'PGND': 'PRI', 'SEC_RTN': 'SEC', 'SGND': 'SEC'})
        self.assertEqual(section['rail_stops']['SEC_RTN'], 'ground')
        self.assertEqual(section['conflicts'], [])

    def test_anchors_are_the_verified_role_kinds(self):
        section = derive()
        self.assertEqual(section['anchors'], {'U1': 'pwm_controller', 'U4': 'shunt_reference', 'U5': 'pd_controller'})
        self.assertEqual(section['undeclared_ics'], [])

    def test_undeclared_ics_are_listed_and_anchor_nothing(self):
        section = derive(kinds={'U3': 'opto', 'BR1': 'bridge_rectifier'})
        self.assertEqual(section['anchors'], {})
        self.assertEqual(section['undeclared_ics'], ['U1', 'U4', 'U5'])
        self.assertNotIn('VOUT', section['rail_stops'])
        self.assertEqual(section['rail_stops']['V5'], 'driver')


class PlanSectionTests(unittest.TestCase):
    def test_plan_carries_the_derived_domains(self):
        db = flyback()
        plan = build_review_plan(db, intent_for(db))
        section = plan['domains']
        self.assertEqual(section['schema_version'], 1)
        self.assertEqual(section['grounds'], {'PGND': 'PRI', 'SGND': 'SEC'})
        self.assertEqual([b['ref'] for b in section['barriers']], ['CY1', 'T1', 'U3'])
        self.assertIn('VOUT', section['rail_stops'])
        self.assertEqual(section['conflicts'], [])

    def test_domain_conflicts_become_plan_diagnostics(self):
        db = flyback()
        fixture.add(db, 'R9', '1M', [('1', '1', 'PGND'), ('2', '2', 'SGND')])
        plan = build_review_plan(db, intent_for(db))
        codes = [d['code'] for d in plan['diagnostics']]
        self.assertIn('DOMAIN_MERGED', codes)


if __name__ == '__main__':
    unittest.main()

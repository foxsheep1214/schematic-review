"""Interface rules are asked once per interface (function-tree design §3.3, step 4).

A pair of circuits is asked for direction semantics (SIG-T04) and levels (SIG-C07), a chain for the levels at its
ends, and each net whose endpoints draw from different supplies or sit on different references for injection on
power-down (SIG-C08). A connector is asked for its mating pinout (DEV-D03), its current (DEV-C04) and its outward
protection (PRO-D03). A rail is asked for its ripple and noise (PWR-C14) when a noise-sensitive circuit draws from
it. These rows belong to their interface; the circuit-pair, chain and connector interfaces get a frame each, a rail
does not. A scan or checker row of an interface rule on an interface net belongs to that interface too.
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import catalog
import circuit_candidates as cc
import circuit_decisions as cd
import row_owner
from plan_review import build_review_plan
import test_circuit_candidates as fx
import test_circuit_decisions as dfx


def plan_for(db=None):
    db = db or fx.board()
    intent, audit = fx.intent_for(db)
    candidates = cc.build(db, intent, audit)
    intent['circuit_decisions'] = dfx.accept_all(candidates)
    intent = cd.write_circuits(intent, candidates)
    return build_review_plan(db, intent, datasheet_audit=audit, candidates=candidates)


def rows(plan, rule):
    return [c for c in plan['checks'] if c['rule'] == rule]


class InterfaceRowTests(unittest.TestCase):
    def setUp(self):
        self.plan = plan_for()
        self.kinds = {i['id']: i['kind'] for i in self.plan['interfaces']['interfaces']}

    def test_each_circuit_pair_is_asked_direction_and_levels_once(self):
        pairs = sorted(i for i, k in self.kinds.items() if k == 'CIRCUIT_PAIR')
        for rule in ('SIG-T04', 'SIG-C07'):
            asked = sorted(c['object']['interface'] for c in rows(self.plan, rule) if 'interface' in c['object'])
            want = pairs + (sorted(i for i, k in self.kinds.items() if k == 'LINK' and self._nets(i)) if rule == 'SIG-C07' else [])
            self.assertEqual(asked, sorted(want), rule)

    def _nets(self, iid):
        return next(i['nets'] for i in self.plan['interfaces']['interfaces'] if i['id'] == iid)

    def test_a_connector_is_asked_pinout_current_and_protection_and_the_board_row_is_gone(self):
        for rule in ('DEV-D03', 'DEV-C04', 'PRO-D03'):
            self.assertEqual(sorted((c['object'].get('interface'), c['object'].get('ref')) for c in rows(self.plan, rule)),
                             [('EXT-J1', 'J1'), ('EXT-J2', 'J2')], rule)

    def test_a_rail_feeding_a_noise_sensitive_circuit_is_asked_its_noise_and_circuits_no_longer_are(self):
        noise = rows(self.plan, 'PWR-C14')
        self.assertEqual([(c['object']['interface'], c['object']['loads']) for c in noise],
                         [('RAIL-VOUT', ['ANALOG-U4', 'ANALOG-U5'])])
        self.assertNotIn('PWR-C14', catalog.CIRCUIT_TYPE_BY_NAME['ANALOG'].subjects)

    def test_interface_rows_belong_to_their_interface_and_have_a_question(self):
        for c in self.plan['checks']:
            if 'interface' in (c.get('object') or {}):
                self.assertEqual(c['owner'], {'kind': 'INTERFACE', 'id': c['object']['interface']}, c['id'])
                self.assertTrue(c.get('question'), c['id'])
        self.assertEqual(catalog.question_errors(self.plan), [])
        self.assertEqual(row_owner.errors(self.plan), [])

    def test_pair_chain_and_connector_interfaces_get_a_frame_and_a_rail_does_not(self):
        frames = {f['interface']: f for f in self.plan['functions'] if f.get('interface')}
        self.assertEqual(set(frames), {i for i, k in self.kinds.items() if k in ('CIRCUIT_PAIR', 'EXTERNAL')}
                         | {i for i, k in self.kinds.items() if k == 'LINK' and self._nets(i)})
        ext = frames['EXT-J2']
        members = {m['check_id'] for m in ext['members']}
        self.assertEqual(members, {c['id'] for c in self.plan['checks'] if c['object'].get('interface') == 'EXT-J2'})
        self.assertIn('J2', ext['objects']['refs'])
        for c in self.plan['checks']:
            if c['object'].get('interface') in frames:
                self.assertEqual(c['function_id'], frames[c['object']['interface']]['id'], c['id'])

    def test_a_scan_row_of_an_interface_rule_on_an_interface_net_belongs_to_that_interface(self):
        parts = {ref: e['id'] for e in self.plan['owners'] for ref in e['parts']}
        nets = row_owner.interface_nets(self.plan['interfaces'])
        scan = {'id': 'SIG-A01.CC1', 'rule': 'SIG-A01', 'object': {'net': 'CC1'}}
        self.assertEqual(row_owner.owner(scan, parts, nets), {'kind': 'INTERFACE', 'id': 'EXT-J2'})   # a connector end wins
        enable = {'id': 'RST-T01.FLT_DRV', 'rule': 'RST-T01', 'object': {'net': 'FLT_DRV', 'ref': 'U5'}}
        self.assertEqual(row_owner.owner(enable, parts, nets), {'kind': 'INTERFACE', 'id': 'IF-ANALOG-U5~USB-J2'})
        inside = {'id': 'SIG-A01.GATE', 'rule': 'SIG-A01', 'object': {'net': 'GATE'}}
        self.assertEqual(row_owner.owner(inside, parts, nets), {'kind': 'BOARD'})   # not an interface net


class CrossDomainNetTests(unittest.TestCase):
    """SIG-C08 is asked on an interface net only where its endpoints draw from different supplies."""

    def test_two_ics_on_different_supplies_make_one_injection_row_on_their_net(self):
        db = fx.board()
        fx.fixture.add(db, 'U8', 'IC:LOGIC', [('1', 'IO', 'FLT_DRV'), ('2', 'VDD', 'V3V3'), ('3', 'GND', 'SGND')])
        fx.fixture.add(db, 'C99', 'C:100n', [('1', '1', 'V3V3'), ('2', '2', 'SGND')])
        db['pinname']['U5.9'] = 'VDD'
        db['pin2net']['U5.9'] = 'V5'
        db['nets']['V5'].append('U5.9')
        plan = plan_for(db)
        injection = [(c['object']['interface'], c['object']['net']) for c in rows(plan, 'SIG-C08') if 'interface' in c['object']]
        self.assertEqual(injection, [('IF-ANALOG-U5~USB-J2', 'FLT_DRV')])
        self.assertEqual(rows(plan_for(), 'SIG-C08'), [])   # the plain board has no such net


if __name__ == '__main__':
    unittest.main()

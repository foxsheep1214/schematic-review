"""A check is named by what the assembly is, not by what the reviewer called it (pairing follow-up of the function tree).

On the R5 bench the two intents declared one assembly, all 125 parts fitted and no jumpers, as "R5-BOM" and "R5";
every checker row carried that name as its state, plus the digest of a checker inventory built from it and an
inventory handle (a decoupling group hash, `rails-<state>`), so 28 rows that asked the same thing of the same parts
did not pair. The plan maps each assembly name to a key from its population and jumpers and the check key uses that
key; inventory digests and handles are pointers into a checker's inventory, so they stay out of the identity while
the parts, nets, nodes, state, rule and criterion say what is asked.
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import check_key
import circuit_candidates as cc
import circuit_decisions as cd
import compare_reviews as cr
from plan_review import build_review_plan
import test_circuit_candidates as fx
import test_circuit_decisions as dfx
from test_validate_review import fixture
from ledger_v3 import validate_review
from validate_review import fingerprint


def plan_named(name, dnp=()):
    db = fx.board()
    intent, audit = fx.intent_for(db)
    intent['assemblies'] = [{'id': name, 'citation': 'synthetic BOM rev A',
                             'population': {ref: ref not in dnp for ref in sorted(db['parts'])}}]
    candidates = cc.build(db, intent, audit)
    intent['circuit_decisions'] = dfx.accept_all(candidates)
    intent = cd.write_circuits(intent, candidates)
    return build_review_plan(db, intent, datasheet_audit=audit, candidates=candidates)


def keyed(plan):
    return {check_key.key(c, plan['assemblies']): c for c in plan['checks']}


class AssemblyKeyTests(unittest.TestCase):
    def setUp(self):
        self.a, self.b = plan_named('BOM-A'), plan_named('PROTO')

    def test_the_plan_maps_each_assembly_name_to_a_content_key(self):
        self.assertEqual([e['id'] for e in self.a['assemblies']], ['BOM-A'])
        self.assertEqual([e['key'] for e in self.a['assemblies']], [e['key'] for e in self.b['assemblies']])
        self.assertNotEqual(self.a['assemblies'][0]['key'], plan_named('BOM-A', dnp=('R99',))['assemblies'][0]['key'])
        open_jumper = check_key.assembly_map([{'id': 'J', 'population': {'JP1': True}, 'jumpers': {'JP1': 'open'}}])
        closed_jumper = check_key.assembly_map([{'id': 'J', 'population': {'JP1': True}, 'jumpers': {'JP1': 'closed'}}])
        self.assertNotEqual(open_jumper[0]['key'], closed_jumper[0]['key'])

    def test_one_assembly_under_two_names_asks_the_same_checks(self):
        named = [c for c in self.a['checks'] if 'BOM-A' in (c['object'].get('state'), c['object'].get('assembly'))]
        self.assertGreater(len(named), 1)          # checker rows and the assembly check carry the name
        self.assertEqual({c['check_key'] for c in self.a['checks']}, {c['check_key'] for c in self.b['checks']})
        self.assertEqual(set(keyed(self.a)), {c['check_key'] for c in self.a['checks']})

    def test_a_different_population_asks_different_checks(self):
        other = plan_named('BOM-A', dnp=('R99',))
        rows = [c for c in self.a['checks'] if c['object'].get('assembly') == 'BOM-A']
        self.assertTrue(rows)
        self.assertFalse({c['check_key'] for c in rows} & {c['check_key'] for c in other['checks']})

    def test_a_working_state_is_not_read_as_an_assembly(self):
        plan = plan_named('run')
        row = next(c for c in plan['checks'] if c['object'].get('circuit_key') and c['object'].get('state') == 'run')
        renamed = copy.deepcopy(row)
        renamed['object']['state'] = 'fault'
        self.assertNotEqual(check_key.key(row, plan['assemblies']), check_key.key(renamed, plan['assemblies']))
        self.assertEqual(check_key.key(row, plan['assemblies']), check_key.key(row))

    def test_compare_reviews_pairs_the_renamed_assembly(self):
        sides = [{'plan': p, 'results': {'checks': []}} for p in (self.a, self.b)]
        report = cr.strict(*sides)
        self.assertEqual(report['counts']['exact'], len(self.a['checks']))
        self.assertEqual(report['stale_keys'], {'A': [], 'B': []})


class InventoryFieldTests(unittest.TestCase):
    ROW = {'rule': 'PWR-T03', 'criterion': 'synthetic', 'object': {
        'ref': 'U1', 'nodes': ['U1.2'], 'nets': ['VCC'], 'state': 'AS-DRAWN', 'decoupling_group': 'DECAP-0123456789abcdef0123',
        'decoupling_inventory_digest': 'a' * 64}}

    def test_inventory_digests_and_handles_do_not_enter_the_identity(self):
        other = copy.deepcopy(self.ROW)
        other['object'].update(decoupling_group='DECAP-fedcba9876543210fedc', decoupling_inventory_digest='b' * 64)
        self.assertEqual(check_key.key(other), check_key.key(self.ROW))
        for field, value in (('nodes', ['U1.3']), ('ref', 'U2'), ('state', 'STANDBY')):
            moved = copy.deepcopy(self.ROW)
            moved['object'][field] = value
            self.assertNotEqual(check_key.key(moved), check_key.key(self.ROW), field)

    def test_every_checker_handle_is_left_out(self):
        for field in check_key.INVENTORY_FIELDS:
            row = copy.deepcopy(self.ROW)
            row['object'][field] = 'handle-1'
            self.assertEqual(check_key.key(row), check_key.key(self.ROW), field)


class AssemblyMapTests(unittest.TestCase):
    def test_a_plan_without_its_assembly_map_is_refused(self):
        plan, report, db = fixture()
        del plan['assemblies']
        report['plan_digest'] = fingerprint(plan)
        gate = validate_review(plan, report, db)
        self.assertFalse(gate['valid'])
        self.assertTrue(any('plan.assemblies' in e for e in gate['errors']), gate['errors'])


if __name__ == '__main__':
    unittest.main()

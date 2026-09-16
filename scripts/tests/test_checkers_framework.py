import copy
import pathlib
import sys
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import test_inductive_load as relay_fixture
from checkers import REGISTRY, REGISTRY_BY_ID, registry_cold_rules, validate_inventories
from checkers import netgraph as ng
from checkers import states as state_lib
from plan_review import ReviewPlanner, build_review_plan


def run_validation(plan, db, items=None):
    errors = []
    expected = {item['id']: item for item in (items if items is not None else plan['checks'])}
    gates = validate_inventories(REGISTRY, plan, expected, db, lambda ok, msg: None if ok else errors.append(msg),
                                 lambda context: ReviewPlanner(db, context))
    return errors, gates


class RegistryTest(unittest.TestCase):
    def test_ids_and_plan_keys_are_unique(self):
        ids = [checker.id for checker in REGISTRY]
        keys = [checker.plan_key for checker in REGISTRY if checker.plan_key]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(set(ids), set(REGISTRY_BY_ID))

    def test_cold_rule_numbers_do_not_collide_with_legacy_rules(self):
        for rule in registry_cold_rules():
            self.assertFalse(rule.startswith('Rule-'), rule)

    def test_every_checker_writes_its_inventory_into_the_plan(self):
        plan = build_review_plan(relay_fixture.relay_board())
        for checker in REGISTRY:
            self.assertIn(checker.plan_key, plan)
            if checker.version_key:
                self.assertEqual(plan[checker.version_key], checker.version)


class GenericValidationTest(unittest.TestCase):
    def setUp(self):
        self.db = relay_fixture.relay_board()
        self.plan = build_review_plan(self.db)
        self.bound = [x for x in self.plan['checks'] if x['object'].get('inductive_load')]

    def test_clean_plan_validates(self):
        errors, _ = run_validation(self.plan, self.db)
        self.assertEqual(errors, [])

    def test_missing_inventory_is_rejected_when_items_are_bound(self):
        plan = copy.deepcopy(self.plan)
        del plan['inductive_load']
        errors, _ = run_validation(plan, self.db)
        self.assertIn('inductive load checks require their inventory', errors)

    def test_modified_inventory_is_detected(self):
        plan = copy.deepcopy(self.plan)
        plan['inductive_load']['digest'] = '0' * 64
        errors, _ = run_validation(plan, self.db)
        self.assertIn('inductive load inventory/binding is stale or modified', errors)

    def test_edited_criterion_is_detected(self):
        plan = copy.deepcopy(self.plan)
        target = next(x for x in plan['checks'] if x['object'].get('inductive_load'))
        target['criterion'] = '改写过的判据'
        errors, _ = run_validation(plan, self.db)
        self.assertIn(target['id'] + ': inductive load generated criterion/object changed', errors)

    def test_dropped_generated_check_is_detected(self):
        plan = copy.deepcopy(self.plan)
        dropped = next(x for x in plan['checks'] if x['object'].get('inductive_load'))
        remaining = [x for x in plan['checks'] if x['id'] != dropped['id']]
        errors, _ = run_validation(plan, self.db, items=remaining)
        self.assertIn(dropped['id'] + ': incomplete inductive load planned coverage', errors)

    def test_open_gaps_block_pass(self):
        _, gates = run_validation(self.plan, self.db)
        blocked = gates[self.bound[0]['id']]
        self.assertEqual(blocked, [self.bound[0]['id'] +
                                   ': inductive load gaps must be resolved in a regenerated plan before PASS'])

    def test_version_mismatch_is_rejected(self):
        plan = copy.deepcopy(self.plan)
        plan['decoupling_version'] = 2
        errors, _ = run_validation(plan, self.db)
        self.assertIn('decoupling_version must be 1', errors)


class DecouplingBindingTest(unittest.TestCase):
    def test_manual_item_may_not_reuse_a_generated_decoupling_object(self):
        import test_decoupling
        db, intent = test_decoupling.fixture()
        plan = build_review_plan(db, intent)
        generated = next(x for x in plan['checks'] if x['object'].get('decoupling_group'))
        manual = copy.deepcopy(generated)
        manual['id'] = generated['id'] + '.manual'
        errors, _ = run_validation(plan, db, items=plan['checks'] + [manual])
        self.assertIn(manual['id'] + ': use an independent object for manual decoupling additions', errors)


class NetGraphTest(unittest.TestCase):
    def setUp(self):
        self.graph = ng.NetGraph(relay_fixture.relay_board())

    def test_classification_prefers_part_keyword_over_prefix(self):
        self.assertEqual(self.graph.kind('Q1'), ng.MOSFET)
        self.assertEqual(self.graph.basis('Q1'), 'part-keyword')
        self.assertEqual(self.graph.kind('K1'), ng.RELAY)

    def test_two_pin_part_is_not_classified_as_a_transistor(self):
        kind, basis = ng.classify('Q9', {'part': 'AO3400', 'value': '', 'prim': '', 'jedec': ''}, 2)
        self.assertEqual(kind, ng.UNKNOWN)
        self.assertIn('pin count', basis)

    def test_roles_come_from_pin_names_only(self):
        self.assertEqual(self.graph.role('Q1.2'), 'drain')
        self.assertEqual(self.graph.role('D1.1'), 'anode')
        graph = ng.NetGraph(relay_fixture.relay_board(clamp='unknown-roles'))
        self.assertIsNone(graph.role('D1.1'))

    def test_between_and_neighbors_respect_population(self):
        self.assertEqual(self.graph.between('RELAY_DRV', 'V24', {ng.DIODE}), ['D1'])
        unfitted = ng.NetGraph(relay_fixture.relay_board(clamp_nc=True))
        self.assertEqual(unfitted.between('RELAY_DRV', 'V24', {ng.DIODE}), [])
        self.assertEqual([ref for ref, _ in self.graph.neighbors('RELAY_DRV', {ng.DIODE})], ['D1'])

    def test_rail_and_ground_naming(self):
        self.assertTrue(ng.is_rail('VCC_3V3'))
        self.assertTrue(ng.is_ground('GND'))
        self.assertFalse(ng.is_rail('GND'))


class StatesTest(unittest.TestCase):
    def test_as_built_keeps_an_explicit_gap(self):
        db = relay_fixture.relay_board()
        state = state_lib.as_built(db)[0]
        self.assertEqual(state['gaps'], ['assembly state unverified: netlist nc only'])
        self.assertNotIn('D1', state['fitted'] if 'D1' not in db['parts'] else [])

    def test_declared_population_and_open_jumper(self):
        db = relay_fixture.relay_board()
        db['parts']['JP1'] = {'part': 'JUMPER', 'value': '', 'prim': '', 'jedec': '', 'nc': False}
        cfg = {'states': [{'id': 'run', 'citation': 'x',
                           'population': {ref: True for ref in db['parts']},
                           'jumpers': {'JP1': 'open'}}]}
        state = state_lib.resolve(db, cfg)[0]
        self.assertNotIn('JP1', state['fitted'])
        self.assertEqual(state['gaps'], [])

    def test_unknown_jumper_and_undeclared_part_are_gaps(self):
        db = relay_fixture.relay_board()
        cfg = {'states': [{'id': 'run', 'citation': 'x',
                           'population': {'K1': True}, 'jumpers': {'Q1': 'unknown'}}]}
        state = state_lib.resolve(db, cfg)[0]
        self.assertIn('jumper:Q1', state['gaps'])
        self.assertIn('population:D1', state['gaps'])

    def test_state_errors_reject_malformed_declarations(self):
        db = relay_fixture.relay_board()
        errors = state_lib.state_errors({'states': [{'id': 'run', 'citation': 'x',
                                                     'population': {'NOPE': True}}]}, db, 'demo')
        self.assertIn('demo: population: unknown ref NOPE', errors)
        self.assertIn('demo: states must contain 1..32 states',
                      state_lib.state_errors({'states': []}, db, 'demo'))


if __name__ == '__main__':
    unittest.main()

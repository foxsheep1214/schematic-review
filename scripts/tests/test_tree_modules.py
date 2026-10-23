"""The planner is laid out along the function tree and old records are refused (function-tree design §3.8, step 7).

`plan_review.py` keeps the flow (add rows, merge, attach findings, assemble the plan); circuit and part rows come
from plan_circuits, interface rows and frames from interfaces, system functions from plan_system, board, document,
requirement and coverage rows from plan_board. Plan schema 6 carries the owner table and the interfaces; a plan
without them, or of an earlier schema, is refused, never read through a compatibility layer.
"""
import copy
import inspect
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import interfaces
import plan_board
import plan_circuits
import plan_review
import plan_system
import revision_impact
import row_owner
from validate_review import validate_review
from electrical_contract import PLAN_SCHEMA_VERSION
from test_interface_rows import plan_for
from test_validate_review import fixture
from validate_review import fingerprint


class ModuleLayoutTests(unittest.TestCase):
    PLACES = {
        plan_circuits: ('plan_circuit_types', 'plan_subjects', 'plan_concrete_checks', 'plan_threshold_checks',
                        'plan_owned_parts'),
        interfaces: ('plan_interfaces',),
        plan_system: ('plan_system', 'plan_system_frames'),
        plan_board: ('plan_board', 'plan_coverage', 'plan_rules'),
    }

    def test_each_tree_level_is_planned_in_its_own_module(self):
        for module, methods in self.PLACES.items():
            for name in methods:
                self.assertEqual(inspect.getmodule(getattr(plan_review.ReviewPlanner, name)), module, name)

    def test_the_flow_module_keeps_no_tree_level(self):
        own = {name for name, value in vars(plan_review.ReviewPlanner).items() if inspect.isfunction(value)}
        self.assertFalse(own & {m for methods in self.PLACES.values() for m in methods}, own)


class OldRecordTests(unittest.TestCase):
    def setUp(self):
        self.plan = plan_for()

    def test_a_plan_carries_schema_6_with_its_owner_table_and_interfaces(self):
        self.assertEqual(PLAN_SCHEMA_VERSION, 6)
        self.assertEqual(self.plan['schema_version'], 6)
        self.assertIsInstance(self.plan['owners'], list)
        self.assertIsInstance(self.plan['interfaces'], dict)

    def test_a_plan_without_its_owner_table_or_interfaces_is_refused(self):
        for section in ('owners', 'interfaces'):
            plan = copy.deepcopy(self.plan)
            del plan[section]
            errors = row_owner.errors(plan) + interfaces.coverage_errors(plan)
            self.assertTrue(any(section in e for e in errors), (section, errors))

    def test_the_validator_refuses_a_schema_5_record(self):
        plan, report, db = fixture()
        plan['schema_version'] = 5
        report['plan_digest'] = fingerprint(plan)
        gate = validate_review(plan, report, db)
        self.assertFalse(gate['valid'])
        self.assertTrue(any('schema_version must be 6' in e for e in gate['errors']), gate['errors'])

    def test_a_schema_5_plan_is_not_merged_or_compared(self):
        old = copy.deepcopy(self.plan)
        old['schema_version'] = 5
        with self.assertRaisesRegex(ValueError, 'schema_version must be 6'):
            planner = plan_review.ReviewPlanner({'parts': {}, 'nets': {}}, {'schema_version': 3})
            planner.previous_plan = old
            planner.merge_previous_checks()
        with self.assertRaisesRegex(ValueError, 'schema_version != 6'):
            revision_impact._baseline({'parts': {}, 'nets': {}}, old)


if __name__ == '__main__':
    unittest.main()

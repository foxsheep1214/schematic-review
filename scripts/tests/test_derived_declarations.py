"""What decides which rows exist is derived, and the reviewer only confirms (fixed requirements, step 5).

On the R5 bench one reviewer declared a platform checklist available and the other did not, which set a batch of rows
waiting or ready; one listed circuit types as applicable that the candidates had already found and the other did not;
both reached the same nine rails only because both happened to declare the same name-unlike supply nets. Now a
material is available when the file it names exists (requirements from the requirement source, datasheets from the
datasheet audit), and `available` is not written; with circuits from candidates, `features` only says why a circuit
type the candidates did not find does not apply; and every net that behaves as a supply on the netlist without a rail
name is either declared in power_rails or excluded with a reason in `rail_exclusions`.
"""
import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from plan_review import build_review_plan, validate_intent
from test_decoupling import fixture, rebind
from test_i2c_topology import add
from test_requirement_source import requirement_intent, write


def existing_file():
    path = Path(tempfile.mkdtemp(prefix='sr-mat-')) / 'schematic.pdf'
    path.write_bytes(b'%PDF-1.4 synthetic')
    return str(path)


class MaterialTests(unittest.TestCase):
    def errors(self, intent):
        return [e for e in validate_intent(dict({'schema_version': 4}, **intent)) if 'materials' in e]

    def test_a_material_is_available_when_its_file_exists(self):
        db = {'parts': {}, 'nets': {}, 'pin2net': {}}
        row = lambda plan: next(c for c in plan['checks'] if c['rule'] == 'DOC-V02')
        self.assertEqual(row(build_review_plan(db, {}))['required_inputs'], ['schematic_pdf'])
        intent = {'materials': {'schematic_pdf': {'path': existing_file()}}}
        self.assertEqual(self.errors(intent), [])
        self.assertEqual(row(build_review_plan(db, intent))['readiness'], 'READY')
        missing = {'materials': {'schematic_pdf': {'path': '/nonexistent/schematic.pdf'}}}
        self.assertEqual(row(build_review_plan(db, missing))['required_inputs'], ['schematic_pdf'])

    def test_available_is_not_written_and_a_missing_file_is_refused(self):
        self.assertTrue(any('available' in e for e in self.errors(
            {'materials': {'schematic_pdf': {'available': True, 'citation': 'x'}}})))
        self.assertTrue(any('path' in e for e in self.errors({'materials': {'schematic_pdf': {'citation': 'x'}}})))
        self.assertTrue(any('不存在' in e for e in self.errors(
            {'materials': {'schematic_pdf': {'path': '/nonexistent/schematic.pdf'}}})))

    def test_requirements_are_available_from_the_requirement_source(self):
        db = {'parts': {}, 'nets': {}, 'pin2net': {}}
        row = lambda plan: next(c for c in plan['checks'] if c['rule'] == 'REQ-D02')
        self.assertEqual(row(build_review_plan(db, {}))['required_inputs'], ['requirements'])
        intent = dict({'schema_version': 4}, **requirement_intent(write()))
        self.assertEqual(row(build_review_plan(db, intent))['required_inputs'], [])


class FeatureTests(unittest.TestCase):
    def errors(self, features):
        intent = {'schema_version': 4, 'circuit_decisions': [],
                  'circuits': [{'id': 'C1', 'type': 'POWER_CONVERTER', 'refs': ['U1'], 'states': ['run'],
                                'citation': 'synthetic'}], 'features': features}
        return [e for e in validate_intent(intent) if 'features' in e]

    def test_with_candidates_features_only_explain_types_the_candidates_did_not_find(self):
        self.assertEqual(self.errors({'CLOCK': {'applicability': 'NOT_APPLICABLE', 'citation': 'no clock on the board'}}), [])
        self.assertTrue(any('POWER_CONVERTER' in e and '候选' in e for e in self.errors(
            {'POWER_CONVERTER': {'applicability': 'NOT_APPLICABLE', 'citation': 'x'}})))
        self.assertTrue(any('CLOCK' in e and 'APPLICABLE' in e for e in self.errors(
            {'CLOCK': {'applicability': 'APPLICABLE', 'citation': 'x'}})))


class RailTests(unittest.TestCase):
    def board(self, declared=None, excluded=None):
        db, intent = fixture(('100nF',))
        add(db, 'C9', '10uF', [('1', '1', 'BULK'), ('2', '2', 'GND')])
        intent['assemblies'][0]['population']['C9'] = True
        if declared is not None:
            intent['power_rails'] = declared
        if excluded is not None:
            intent['rail_exclusions'] = excluded
        rebind(db, intent)
        return db, intent

    def errors(self, db, intent):
        return [e for e in validate_intent(intent, db) if 'rail' in e]

    def test_a_supply_net_without_a_rail_name_is_declared_or_excluded(self):
        db, intent = self.board()
        self.assertTrue(any('BULK' in e for e in self.errors(db, intent)))
        db, intent = self.board(declared={'BULK': {'voltage_v': {'min': 0, 'max': 400}, 'citation': 'synthetic'}})
        self.assertEqual(self.errors(db, intent), [])
        db, intent = self.board(excluded={'BULK': 'synthetic hold-up node, not a supply'})
        self.assertEqual(self.errors(db, intent), [])

    def test_an_exclusion_is_a_candidate_with_a_reason_and_not_also_declared(self):
        for declared, excluded in (({'BULK': {'citation': 'x'}}, {'GND': 'x'}), ({}, {'BULK': ''}),
                                   ({'BULK': {'citation': 'x'}}, {'BULK': 'x'})):
            db, intent = self.board(declared, excluded)
            self.assertTrue(self.errors(db, intent), (declared, excluded))

    def test_the_plan_lists_the_rail_candidates_and_how_each_was_confirmed(self):
        db, intent = self.board(excluded={'BULK': 'synthetic hold-up node'})
        plan = build_review_plan(db, intent)
        self.assertEqual(plan['rail_candidates'], {'BULK': 'excluded', 'VCC_3V3': 'name'})
        db, intent = self.board(declared={'BULK': {'citation': 'synthetic'}})
        self.assertEqual(build_review_plan(db, intent)['rail_candidates'], {'BULK': 'declared', 'VCC_3V3': 'name'})


if __name__ == '__main__':
    unittest.main()

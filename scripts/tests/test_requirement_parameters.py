"""A requirement's numbers are read into fixed parameters that the plan uses (fixed requirements, step 3).

On the R5 bench one reviewer's rail windows and the other's differed on 10 of 13 shared rails, and the requirement
numbers (input range, output levels, ambient temperature) stayed in requirement-row prose that no calculation read.
The reviewer now reads each requirement's numbers into `parameters` {name, min, max, unit, condition}: the name and
unit come from a fixed table, every number must appear in that requirement's original text and a condition must be a
piece of it. The parameters ride on the requirement rows outside the check identity; a rail's voltage window can name
the requirement it comes from, the input range reaches the power-tree frame and the ambient temperature reaches the
part stress rows.
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import catalog
import requirement_parameters as rp
from lint import Lint
from plan_review import ReviewPlanner, build_review_plan, validate_intent
from test_decoupling import fixture, rebind
from test_requirement_source import doc_for, requirement_intent, write

PARAMETERS = {'REQ-IN-01': [{'name': 'input_voltage', 'min': 9, 'max': 36, 'unit': 'V'},
                            {'name': 'surge_voltage', 'max': 40, 'unit': 'V', 'condition': '持续 100 ms'}],
              'REQ-TEMP-01': [{'name': 'ambient_temperature', 'min': -20, 'max': 60, 'unit': '°C'}]}


def intent(parameters=PARAMETERS):
    value = dict({'schema_version': 4}, **requirement_intent(write()))
    for item in value['requirements']:
        if item['id'] in parameters:
            item['parameters'] = copy.deepcopy(parameters[item['id']])
    return value


def errors(value):
    return [e for e in validate_intent(value) if 'parameter' in e or 'power_rails' in e]


class TableTests(unittest.TestCase):
    def test_every_parameter_has_a_title_and_its_canonical_unit_among_its_units(self):
        for name, entry in catalog.REQUIREMENT_PARAMETERS.items():
            self.assertTrue(entry.title, name)
            self.assertEqual(entry.units[entry.unit], 1, name)
        text = catalog.render_markdown()
        for entry in catalog.REQUIREMENT_PARAMETERS.values():
            self.assertIn(entry.title, text)


class IntentTests(unittest.TestCase):
    def test_parameters_read_from_the_text_are_accepted(self):
        self.assertEqual(errors(intent()), [])

    def test_a_number_not_in_the_original_text_is_refused(self):
        for value in (48, 36.5):
            changed = copy.deepcopy(PARAMETERS)
            changed['REQ-IN-01'][0]['max'] = value
            self.assertTrue(any(str(value) in e and '原文' in e for e in errors(intent(changed))), value)
        changed = copy.deepcopy(PARAMETERS)
        changed['REQ-TEMP-01'][0]['min'] = 20   # the text says −20
        self.assertTrue(any('20' in e and '原文' in e for e in errors(intent(changed))))

    def test_a_plus_minus_number_gives_both_signs(self):
        value = {'schema_version': 4, 'requirement_source': doc_for({'REQ-ACC': '+3V3 输出精度 ±5%'}),
                 'requirements': [{'id': 'REQ-ACC', 'categories': ['OUTPUT_SPEC'], 'interpretation': 'x',
                                   'parameters': [{'name': 'accuracy', 'min': -5, 'max': 5, 'unit': '%'}]}]}
        self.assertEqual(errors(value), [])

    def test_name_unit_condition_and_bounds_are_checked(self):
        cases = (({'name': 'input_volts'}, 'input_volts'), ({'unit': 'volt'}, 'volt'), ({'unit': '°C'}, '°C'),
                 ({'condition': '强制风冷'}, 'condition'), ({'min': 36, 'max': 9}, 'min'))
        for change, word in cases:
            changed = copy.deepcopy(PARAMETERS)
            changed['REQ-IN-01'][0].update(change)
            self.assertTrue(any(word in e for e in errors(intent(changed))), (change, errors(intent(changed))))
        changed = copy.deepcopy(PARAMETERS)
        del changed['REQ-IN-01'][0]['min'], changed['REQ-IN-01'][0]['max']
        self.assertTrue(errors(intent(changed)))

    def test_a_dash_after_a_digit_is_a_range_not_a_minus(self):
        self.assertEqual(rp.numbers('9-36 V，−20～+60°C，±5%'), {9, 36, -20, 60, 5, -5})

    def test_the_envelope_of_several_windows_takes_the_widest_bounds(self):
        found = [{'requirement': 'R-2', 'min': -10, 'max': 50, 'unit': '°C'},
                 {'requirement': 'R-1', 'min': -20, 'max': 40, 'unit': '°C'}]
        self.assertEqual(rp.envelope(found), {'min': -20, 'max': 50, 'unit': '°C', 'requirements': ['R-1', 'R-2']})

    def test_a_scaled_unit_is_normalized_to_the_canonical_unit(self):
        item = rp.normalized({'name': 'esd_voltage', 'min': -8, 'max': 8, 'unit': 'kV'})
        self.assertEqual((item['min'], item['max'], item['unit']), (-8000, 8000, 'V'))
        self.assertEqual(item['written'], {'min': -8, 'max': 8, 'unit': 'kV'})


class PlanTests(unittest.TestCase):
    def board(self, parameters=PARAMETERS, rails=None):
        db, value = fixture(('100nF',))
        value.update(intent(parameters))
        if rails:
            value['power_rails'] = rails
        rebind(db, value)
        return db, value

    def test_requirement_rows_carry_their_parameters_outside_the_identity(self):
        db, value = self.board()
        plan = build_review_plan(db, value)
        rows = [c for c in plan['checks'] if c['rule'] == 'REQ-D01' and c['object']['requirement_id'] == 'REQ-IN-01']
        self.assertTrue(rows)
        for row in rows:
            self.assertEqual([p['name'] for p in row['parameters']], ['input_voltage', 'surge_voltage'])
        changed = copy.deepcopy(PARAMETERS)
        changed['REQ-IN-01'][0]['min'] = 36
        db2, value2 = self.board(changed)
        other = build_review_plan(db2, value2)
        key = lambda p: sorted(c['check_key'] for c in p['checks'] if c['rule'] == 'REQ-D01')
        self.assertEqual(key(plan), key(other))

    def test_a_rail_window_can_come_from_a_requirement(self):
        rails = {'VCC_3V3': {'voltage_v': {'requirement': 'REQ-IN-01'}}}
        db, value = self.board(rails=rails)
        self.assertEqual(errors(value), [])
        window = {'min': 9, 'max': 36, 'requirement': 'REQ-IN-01'}
        self.assertEqual(rp.resolve(value)['power_rails']['VCC_3V3']['voltage_v'], window)
        self.assertEqual(ReviewPlanner(db, value).intent['power_rails']['VCC_3V3']['voltage_v'], window)
        self.assertEqual(Lint(db, intent=value).intent['power_rails']['VCC_3V3']['voltage_v'], window)
        self.assertEqual(value['power_rails']['VCC_3V3']['voltage_v'], {'requirement': 'REQ-IN-01'})
        for bad in ('REQ-TEMP-01', 'REQ-NONE'):
            db, value = self.board(rails={'VCC_3V3': {'voltage_v': {'requirement': bad}}})
            self.assertTrue(any('power_rails' in e and bad in e for e in errors(value)), bad)

    def test_a_rail_window_from_a_requirement_reaches_the_checkers(self):
        # The checkers read the same resolved windows as the planner and the netlist scan: a pull-up on a rail whose
        # window comes from a requirement gets its stress bound from that window.
        db, value = self.board(rails={'VCC_3V3': {'voltage_v': {'requirement': 'REQ-IN-01'}}})
        planner = ReviewPlanner(db, value)
        self.assertEqual(planner.kind_intent['power_rails']['VCC_3V3']['voltage_v']['max'], 36)
        rails = planner.inventories['passive_stress']['context']['power_rails']
        self.assertEqual(rails['VCC_3V3']['voltage_v']['max'], 36)

    def test_the_input_range_reaches_the_power_tree_frame(self):
        db, value = self.board()
        frame = next(f for f in build_review_plan(db, value)['functions'] if f['id'] == 'FN-SYS-POWER')
        self.assertEqual(frame['requirement_windows'],
                         [{'name': 'input_voltage', 'requirement': 'REQ-IN-01', 'min': 9, 'max': 36, 'unit': 'V',
                           'condition': None}])
        self.assertIn('需求输入 9–36 V（REQ-IN-01）', frame['question'])

    def test_the_ambient_temperature_reaches_the_part_stress_rows(self):
        db, value = self.board()
        plan = build_review_plan(db, value)
        window = {'name': 'ambient_temperature', 'requirement': 'REQ-TEMP-01', 'min': -20, 'max': 60, 'unit': '°C',
                  'condition': None}
        self.assertEqual(plan['conditions']['ambient_temperature'], [window])
        for rule in ('DEV-C01', 'DEV-C02', 'DEV-C05'):
            row = next(c for c in plan['checks'] if c['rule'] == rule)
            self.assertEqual(row['conditions'], {'ambient_temperature': {'min': -20, 'max': 60, 'unit': '°C',
                                                                         'requirements': ['REQ-TEMP-01']}}, rule)
        db, value = self.board({})
        plan = build_review_plan(db, value)
        self.assertEqual(plan['conditions'], {})
        self.assertNotIn('conditions', next(c for c in plan['checks'] if c['rule'] == 'DEV-C01'))


if __name__ == '__main__':
    unittest.main()

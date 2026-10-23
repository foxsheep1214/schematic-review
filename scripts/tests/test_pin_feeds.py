"""An IC pin fed through a resistor from a rail above the IC's lowest supply gets its own DEV-C01 row.

On the R5 bench both reviewers added a row by hand for the same controller pins: a discharge pin and a bus-sense pin,
each fed through one resistor from a rail that is higher than the controller's lowest supply, where the resistor is
the only thing that limits the current into the pin. The plan had one DEV-C01 row for the whole circuit, although the
DEV-C01 criterion asks for these pins one by one. The passive-stress inventory now finds them on the netlist: a pin
that is not a power or return pin, on a net that holds only that pin, series resistors and capacitors, with a resistor
whose far end is a declared rail above the lowest declared supply of the IC and no resistor to ground (a divider).
Each such pin gets one row with the worst current through the resistor as a calculation, no proposed result.
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import check_key
from checkers import passive_stress
from checkers.passive_stress import PIN_CRITERION
from validate_review import validate_review
import render_report
from render_report import render
from plan_review import REGISTRY, ReviewPlanner, build_review_plan
from test_decoupling import add, ledger, mark_pass, rebind
from test_passive_stress import board

HIGH = {'VHIGH': {'voltage_v': {'min': 0, 'max': 25}}}


def fed(source='VHIGH', rails=HIGH, value='1k/1%'):
    """U1 (supply VCC_3V3) with its GPIO fed through R1 from `source`."""
    db, intent = board()
    intent['power_rails'].update(copy.deepcopy(rails))
    db['nets']['VCC_3V3'].remove('R1.1')
    db['nets'].setdefault(source, []).append('R1.1')
    db['pin2net']['R1.1'] = source
    db['parts']['R1']['value'] = value
    rebind(db, intent)
    return db, intent


def pin_rows(db, intent):
    return [c for c in build_review_plan(db, intent)['checks'] if c.get('criterion') == PIN_CRITERION]


class PinFeedTests(unittest.TestCase):
    def test_a_pin_fed_from_a_rail_above_the_ic_lowest_supply_gets_its_own_row(self):
        rows = pin_rows(*fed())
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual((row['rule'], row['object']['ref'], row['object']['node'], row['object']['feeds']),
                         ('DEV-C01', 'U1', 'U1.3', ['R1']))
        self.assertIsNone(row['proposal']['result'])

    def test_the_row_carries_the_worst_current_through_the_resistor(self):
        calc = pin_rows(*fed())[0]['proposal']['calculation']
        self.assertEqual(calc['feeds'], [{'ref': 'R1', 'net': 'VHIGH', 'source_max_v': 25.0, 'r_min_ohm': 990.0,
                                          'i_max_a': round(25 / 990, 9)}])
        self.assertEqual(calc['lowest_supply_max_v'], 3.465)
        calc = pin_rows(*fed(value='47R/2W/5%/1%'))[0]['proposal']['calculation']
        self.assertIsNone(calc['feeds'][0]['i_max_a'])

    def test_a_pull_up_to_the_ic_own_supply_gets_no_pin_row(self):
        self.assertEqual(pin_rows(*board()), [])

    def test_a_divider_another_ic_pin_or_a_power_pin_gets_no_pin_row(self):
        db, intent = fed()
        add(db, 'R2', '1k', [('1', '1', 'U1_IO'), ('2', '2', 'GND')])
        intent['assemblies'][0]['population']['R2'] = True
        rebind(db, intent)
        self.assertEqual(pin_rows(db, intent), [], 'divider')
        db, intent = fed()
        add(db, 'U2', 'TEST-IC', [('1', 'IN', 'U1_IO')])
        intent['assemblies'][0]['population']['U2'] = True
        rebind(db, intent)
        self.assertEqual(pin_rows(db, intent), [], 'another IC pin')
        db, intent = fed()
        intent['devices']['U1']['pins']['3']['role'] = 'power'
        rebind(db, intent)
        self.assertEqual(pin_rows(db, intent), [], 'power pin')

    def test_an_undeclared_source_gets_no_pin_row(self):
        self.assertEqual(pin_rows(*fed(rails={})), [])

    def test_a_multi_supply_ic_counts_its_lowest_supply(self):
        db, intent = fed(source='VMID', rails={'VMID': {'voltage_v': {'min': 0, 'max': 12}},
                                               'VHIGH': {'voltage_v': {'min': 0, 'max': 25}}})
        add(db, 'U1', 'TEST-IC', [('4', 'VHV', 'VHIGH')])
        intent['devices']['U1']['pins']['4'] = {'name': 'VHV', 'role': 'power'}
        rebind(db, intent)
        rows = pin_rows(db, intent)
        self.assertEqual([r['object']['node'] for r in rows], ['U1.3'])
        self.assertEqual(rows[0]['proposal']['calculation']['lowest_supply_max_v'], 3.465)

    def test_the_gate_rebuilds_the_pin_rows_from_the_saved_context(self):
        # The gate rebuilds each checker inventory from the context saved with it; the pin rows read the IC supply
        # pins from intent.devices, so the context carries the devices or the rebuilt inventory has no pins.
        db, intent = fed()
        plan = build_review_plan(db, intent)
        checker = next(c for c in REGISTRY if c.id == 'passive_stress')
        saved = plan[checker.plan_key]
        self.assertEqual(ReviewPlanner(db, checker.context_intent(saved)).inventories[checker.id], saved)

    def pass_errors(self, value, **fields):
        """Gate errors on the pin row when it is marked PASS with `fields`."""
        db, intent = fed(value=value)
        plan = build_review_plan(db, intent)
        report = ledger(plan, db)
        key = pin_rows(db, intent)[0]['id']
        row = next(c for c in report['checks'] if c['id'] == key)
        mark_pass(report, plan, row)
        row.update(fields)
        return [e for e in validate_review(plan, report, db)['errors'] if key in e]

    def test_a_pin_row_whose_current_the_tool_could_not_compute_needs_the_reviewer_calculation_to_pass(self):
        # A feed resistor whose value is unreadable leaves the pin current empty; a PASS on such a row rested on a
        # rationale about another circuit. The PASS now carries the reviewer's own calculation (manual_verification).
        self.assertTrue(any('pin current' in e for e in self.pass_errors('47R/2W/5%/1%')))
        manual = {'tool_limitation': 'R1 value unreadable', 'sr_improvement': 'read the pulse qualifier',
                  'method': '25 V / (47 ohm x 0.99) = 0.537 A against the pin limit',
                  'evidence': [{'source': 'synthetic-fixture.json', 'locator': 'U1 pin 3 limit'}]}
        self.assertFalse(any('pin current' in e for e in self.pass_errors('47R/2W/5%/1%', manual_verification=manual)))
        self.assertFalse(any('pin current' in e for e in self.pass_errors('1k/1%')))

    def test_the_report_tells_the_designer_which_values_to_rewrite(self):
        # The plan listed the unreadable values, but nothing put them in front of the designer, who writes them.
        db, intent = fed(value='47R/2W/5%/1%')
        plan = build_review_plan(db, intent)
        report = ledger(plan, db)
        text = render(plan, report, validate_review(plan, report, db))
        section = text.split('## 设计输入要改的写法')[1].split('\n## ')[0]
        self.assertIn('R1：`47R/2W/5%/1%`', section)
        self.assertEqual(render_report.render_input_notes({'diagnostics': []}), [])

    def test_a_word_after_a_readable_value_keeps_the_value_and_is_reported_alone(self):
        # "4.7k/1%/0.5W/pulse" made the whole value unreadable: reviewers wrote "阻值无法确定" for a 4.7 kΩ resistor and
        # opened one gap per resistor plus one for the word. The value is read; only the word goes to the designer.
        db, intent = fed(value='47R/2W/pulse')
        calc = pin_rows(db, intent)[0]['proposal']['calculation']
        self.assertAlmostEqual(calc['feeds'][0]['r_min_ohm'], 47 * (1 - passive_stress.DEFAULT_TOL))
        plan = build_review_plan(db, intent)
        codes = {d['code']: d for d in plan['diagnostics']}
        self.assertNotIn('RESISTOR_VALUE_UNREAD', codes)
        self.assertEqual(codes['RESISTOR_VALUE_WORD']['values'], {'R1': '47R/2W/pulse'})
        self.assertIn('R1：`47R/2W/pulse`', '\n'.join(render_report.render_input_notes(plan)))
        for value in ('47R/2W/NC', '47R/2W/DNP'):   # a not-fitted mark is never a note
            with self.subTest(value=value):
                self.assertIn('RESISTOR_VALUE_UNREAD', {d['code'] for d in build_review_plan(*fed(value=value))['diagnostics']})

    def test_a_word_the_bom_specification_already_states_is_not_asked_again(self):
        # The report asked the designer to spell out "pulse" for resistors whose BOM specification column already
        # gave the pulse energy; a column that only names the part or its place says nothing about the word.
        db, intent = fed(value='47R/2W/pulse')
        db['bom'] = {'parts': {'R1': {'MPN': 'RX-47R', 'Circuit': 'Output', 'Electrical specification': '单次脉冲 0.4 J'}}}
        codes = {d['code'] for d in build_review_plan(db, intent)['diagnostics']}
        self.assertNotIn('RESISTOR_VALUE_WORD', codes)
        db['bom']['parts']['R1'] = {'MPN': 'RX-47R', 'Circuit': 'Output', 'Footprint': 'R_2512', 'Qty': '1'}
        codes = {d['code']: d for d in build_review_plan(db, intent)['diagnostics']}
        self.assertEqual(codes['RESISTOR_VALUE_WORD']['values'], {'R1': '47R/2W/pulse'})

    def test_two_reviewers_with_different_windows_ask_the_same_pin_row(self):
        a = pin_rows(*fed())[0]
        b = pin_rows(*fed(rails={'VHIGH': {'voltage_v': {'min': 0, 'max': 30}}}))[0]
        self.assertEqual(check_key.key(a, []), check_key.key(b, []))


if __name__ == '__main__':
    unittest.main()

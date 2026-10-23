"""A circuit rule is asked only where its mechanism is on the netlist (consistency proposals of 2026-10-23, item 2;
plan format 7).

Two reviews of one board wrote 42 rows NA on one side and PASS on the other: the plan asked every rule of a circuit
type of every circuit of that type, a power-switch SOA of an AC input with no switch, a compensation of a follower
with no loop, a reset strap of a start-up circuit with no processor. Each circuit-type rule now carries a
precondition (`catalog.SUBJECT_REQUIRES`) judged on the netlist; a rule whose precondition fails is not asked, the
frame lists it under `not_asked` and the report says so. The row object is the part the precondition found, not the
circuit's first part. Where the netlist cannot tell (a part of unknown kind, an IC without pin names) the rule is
asked. A PASS that only says the aspect does not apply is refused, and an NA where the precondition holds names the
netlist fact that rules it out.
"""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import catalog
from electrical_contract import PLAN_SCHEMA_VERSION
from plan_review import build_review_plan
from render_report import render_functions
from review_functions import function_errors
from test_inductive_load import add
from test_review_functions import ASPECT, STATES, bias_function, ledger
from test_validate_review import E, planned
from validate_review import fingerprint
import validate_review as vr


def empty():
    return {'nets': {}, 'parts': {}, 'pin2net': {}, 'pinname': {}, 'pintype': {}, 'pseudo_nets': [], 'ref2page': {}}


def plan_of(db, kind, refs, states=('RUN',)):
    circuit = {'id': 'CKT', 'type': kind, 'refs': list(refs), 'states': list(states), 'citation': 'synthetic circuit'}
    return build_review_plan(db, {'schema_version': 4, 'circuits': [circuit]})


def asked(plan, rule):
    return [c for c in plan['checks'] if c['rule'] == rule and (c.get('object') or {}).get('circuit') == 'CKT'
            and c.get('circuit_type')]


def frame(plan):
    return next(f for f in plan['functions'] if f.get('circuit') == 'CKT')


def not_asked(plan):
    return {item['rule']: item['requires'] for item in frame(plan).get('not_asked') or []}


def input_board(switch=None, connector=True):
    """J1 -> F1 -> D1 into VIN with C1; `switch` adds Q1 as 'low' (source on ground) or 'series' (between VIN_RAW and VIN)."""
    db = empty()
    if connector:
        add(db, 'J1', 'Connector:Conn_01x02', [('1', '1', 'VIN_IN'), ('2', '2', 'GND')])
    add(db, 'F1', 'FUSE 2A', [('1', '1', 'VIN_IN'), ('2', '2', 'VIN_RAW')])
    add(db, 'D1', 'DIODE', [('1', 'A', 'VIN_RAW'), ('2', 'K', 'VIN')])
    add(db, 'C1', '10uF', [('1', '1', 'VIN'), ('2', '2', 'GND')])
    if switch == 'low':
        add(db, 'Q1', 'NMOS', [('1', 'G', 'GATE'), ('2', 'D', 'LOAD_N'), ('3', 'S', 'GND')])
    elif switch == 'series':
        add(db, 'Q1', 'PMOS', [('1', 'G', 'GATE'), ('2', 'D', 'VIN_RAW'), ('3', 'S', 'VIN')])
    return db


def converter_board(pins):
    db = empty()
    add(db, 'U1', 'CTRL', [(str(i + 1), name, net) for i, (name, net) in enumerate(pins)])
    add(db, 'C1', '10uF', [('1', '1', 'VOUT'), ('2', '2', 'GND')])
    return db


def follower_board():
    """A source follower held by a zener: no IC, no loop."""
    db = empty()
    add(db, 'Q1', 'NMOS', [('1', 'G', 'BIAS_G'), ('2', 'D', 'AUX'), ('3', 'S', 'VCC')])
    add(db, 'D1', 'ZENER', [('1', 'A', 'GND'), ('2', 'K', 'BIAS_G')])
    add(db, 'R1', '100k', [('1', '1', 'AUX'), ('2', '2', 'BIAS_G')])
    return db


class PreconditionTableTests(unittest.TestCase):
    def test_every_precondition_names_a_rule_of_its_type_and_a_reason(self):
        for (kind, rule), requires in catalog.SUBJECT_REQUIRES.items():
            self.assertIn(rule, catalog.circuit_type(kind).subjects, (kind, rule))
            self.assertTrue(catalog.SUBJECT_PRECONDITIONS[requires].startswith('电路里没有'), requires)

    def test_the_plan_format_is_7(self):
        self.assertEqual(PLAN_SCHEMA_VERSION, 7)


class PowerSwitchTests(unittest.TestCase):
    def test_no_transistor_no_soa_row(self):
        plan = plan_of(input_board(), 'POWER_PROTECTION', ['F1', 'D1', 'C1'])
        self.assertEqual(asked(plan, 'DRV-C02'), [])
        self.assertEqual(not_asked(plan)['DRV-C02'], 'POWER_SWITCH')

    def test_a_transistor_is_the_row_object(self):
        plan = plan_of(input_board('low'), 'POWER_PROTECTION', ['F1', 'D1', 'C1', 'Q1'])
        rows = asked(plan, 'DRV-C02')
        self.assertEqual([r['object']['ref'] for r in rows], ['Q1'])
        self.assertEqual(rows[0]['requires'], {'id': 'POWER_SWITCH', 'found': ['Q1']})
        self.assertNotIn('DRV-C02', not_asked(plan))


class SupplySwitchTests(unittest.TestCase):
    def test_a_low_side_switch_is_no_reverse_polarity_switch(self):
        plan = plan_of(input_board('low'), 'POWER_PROTECTION', ['F1', 'D1', 'Q1'])
        self.assertEqual(asked(plan, 'PWR-T05'), [])
        self.assertEqual(not_asked(plan)['PWR-T05'], 'SUPPLY_SWITCH')

    def test_a_series_switch_in_the_supply_is(self):
        plan = plan_of(input_board('series'), 'POWER_PROTECTION', ['F1', 'D1', 'Q1'])
        self.assertEqual([r['object']['ref'] for r in asked(plan, 'PWR-T05')], ['Q1'])


class FeedbackAndSwitchPinTests(unittest.TestCase):
    def test_a_follower_without_a_loop_is_asked_no_compensation_or_timing(self):
        plan = plan_of(follower_board(), 'POWER_CONVERTER', ['Q1', 'D1', 'R1'])
        self.assertEqual(asked(plan, 'PWR-C15'), [])
        self.assertEqual(asked(plan, 'PWR-C04'), [])
        self.assertEqual(not_asked(plan), {'PWR-C15': 'FEEDBACK_PIN', 'PWR-C04': 'SWITCH_PIN'})
        for rule in ('PWR-C02', 'PWR-C03', 'PWR-C05'):   # asked of every converter
            self.assertEqual(len(asked(plan, rule)), 1, rule)
        self.assertEqual(set(frame(plan)['blind_spots']), {'PWR-C02', 'PWR-C03', 'PWR-C05'})

    def test_a_controller_with_feedback_and_gate_pins_is_asked_both_on_itself(self):
        db = converter_board([('VCC', 'VCC'), ('FB', 'FB'), ('GATE', 'GATE'), ('GND', 'GND')])
        plan = plan_of(db, 'POWER_CONVERTER', ['C1', 'U1'])
        for rule in ('PWR-C15', 'PWR-C04'):
            self.assertEqual([r['object']['ref'] for r in asked(plan, rule)], ['U1'], rule)

    def test_a_fixed_output_regulator_has_an_internal_loop_and_an_output_capacitor_condition(self):
        db = converter_board([('VIN', 'VIN'), ('VOUT', 'VOUT'), ('GND', 'GND')])
        plan = plan_of(db, 'POWER_CONVERTER', ['U1', 'C1'])
        self.assertEqual(len(asked(plan, 'PWR-C15')), 1)
        self.assertEqual(len(asked(plan, 'PWR-C04')), 1)

    def test_a_power_stage_whose_controller_sits_outside_it_is_asked_both(self):
        """A power stage driven through its gate resistor by a driver outside the circuit, its output divided into an
        amplifier outside it: the loop closes outside the circuit's parts and is still asked."""
        db = empty()
        add(db, 'T1', 'XFMR', [('1', '1', 'VIN'), ('2', '2', 'SW_PRI'), ('3', '3', 'SW_SEC'), ('4', '4', 'VOUT_P')])
        add(db, 'Q1', 'NMOS', [('1', 'G', 'GATE_Q1'), ('2', 'D', 'SW_PRI'), ('3', 'S', 'GND')])
        add(db, 'R1', '1', [('1', '1', 'DRV_OUT'), ('2', '2', 'GATE_Q1')])
        add(db, 'U1', 'DRIVER', [('1', 'IN', 'PWM'), ('2', 'OUT', 'DRV_OUT'), ('3', 'VDD', 'V12'), ('4', 'GND', 'GND')])
        add(db, 'R2', '51k', [('1', '1', 'VOUT_P'), ('2', '2', 'VOUT_SENSE')])
        add(db, 'R3', '10k', [('1', '1', 'VOUT_SENSE'), ('2', '2', 'VOUT_N')])
        add(db, 'U2', 'ISO-AMP', [('1', 'INP', 'VOUT_SENSE'), ('2', 'VDD1', 'V3'), ('3', 'GND1', 'VOUT_N')])
        plan = plan_of(db, 'POWER_CONVERTER', ['T1', 'Q1', 'R1', 'R2', 'R3'])
        self.assertEqual([r['object']['ref'] for r in asked(plan, 'PWR-C04')], ['U1'])
        self.assertEqual([r['object']['ref'] for r in asked(plan, 'PWR-C15')], ['U2'])
        del db['parts']['R3']   # no divider: the output reaches no IC
        for node in ('R3.1', 'R3.2'):
            db['nets'][db['pin2net'].pop(node)].remove(node)
        self.assertEqual(asked(plan_of(db, 'POWER_CONVERTER', ['T1', 'Q1', 'R1', 'R2']), 'PWR-C15'), [])

    def test_a_compensation_pin_of_a_controller_outside_the_circuit_is_a_loop(self):
        db = follower_board()
        add(db, 'C2', '10nF', [('1', '1', 'COMP_NET'), ('2', '2', 'GND')])
        add(db, 'U3', 'CTRL', [('1', 'COMP', 'COMP_NET'), ('2', 'VCC', 'VCC'), ('3', 'GND', 'GND')])
        plan = plan_of(db, 'POWER_CONVERTER', ['Q1', 'D1', 'R1', 'C2'])
        self.assertEqual([r['object']['ref'] for r in asked(plan, 'PWR-C15')], ['U3'])

    def test_a_synchronous_rectifier_has_a_switch_and_no_loop(self):
        """Its resistors all return to a named return (a reference ground of its domain), which divides nothing."""
        db = empty()
        add(db, 'U1', 'SR-CTRL', [('1', 'DRV', 'SR_DRV'), ('2', 'CS', 'SR_D'), ('3', 'TRIG', 'OUT_RTN'),
                                  ('4', 'GND', 'OUT_RTN'), ('5', 'TON', 'SR_ON'), ('6', 'VCC', 'VOUT_P')])
        add(db, 'Q1', 'NMOS', [('1', 'G', 'SR_G'), ('2', 'D', 'SR_D'), ('3', 'S', 'OUT_RTN')])
        add(db, 'R1', '2R2', [('1', '1', 'SR_DRV'), ('2', '2', 'SR_G')])
        add(db, 'R2', '10k', [('1', '1', 'SR_G'), ('2', '2', 'OUT_RTN')])
        add(db, 'R3', '20k', [('1', '1', 'SR_ON'), ('2', '2', 'OUT_RTN')])
        plan = plan_of(db, 'POWER_CONVERTER', ['U1', 'Q1', 'R1', 'R2', 'R3'])
        self.assertEqual([r['object']['ref'] for r in asked(plan, 'PWR-C04')], ['U1'])
        self.assertEqual(asked(plan, 'PWR-C15'), [])

    def test_a_feedback_pin_without_a_switch_pin_is_asked_compensation_only(self):
        db = converter_board([('VIN', 'VIN'), ('FB', 'FB'), ('GND', 'GND')])
        plan = plan_of(db, 'POWER_CONVERTER', ['U1', 'C1'])
        self.assertEqual(len(asked(plan, 'PWR-C15')), 1)
        self.assertEqual(asked(plan, 'PWR-C04'), [])


class ConnectorInputTests(unittest.TestCase):
    def test_a_circuit_behind_a_connector_is_asked_inrush(self):
        plan = plan_of(input_board(), 'POWER_PROTECTION', ['F1', 'D1', 'C1'])
        self.assertEqual([r['object']['ref'] for r in asked(plan, 'PWR-C13')], ['J1'])

    def test_a_circuit_fed_from_a_board_rail_is_not(self):
        plan = plan_of(input_board(connector=False), 'POWER_PROTECTION', ['F1', 'D1', 'C1'])
        self.assertEqual(asked(plan, 'PWR-C13'), [])
        self.assertEqual(not_asked(plan)['PWR-C13'], 'CONNECTOR_INPUT')

    def test_a_shared_ground_pin_is_no_input_path(self):
        db = input_board(connector=False)
        add(db, 'J2', 'Connector:Conn_01x02', [('1', '1', 'SIG'), ('2', '2', 'GND')])
        add(db, 'R9', '100k', [('1', '1', 'VIN'), ('2', '2', 'GND')])   # a bleeder: the power path reaches ground
        plan = plan_of(db, 'POWER_PROTECTION', ['F1', 'D1', 'C1'])
        self.assertEqual(asked(plan, 'PWR-C13'), [])


class ProtectionPartTests(unittest.TestCase):
    def test_a_fuse_is_a_protection_part(self):
        plan = plan_of(input_board(), 'POWER_PROTECTION', ['F1', 'D1', 'C1'])
        for rule in ('PWR-C06', 'PRO-C01'):
            self.assertEqual([r['object']['ref'] for r in asked(plan, rule)], ['F1'], rule)

    def test_a_threshold_pin_is_one(self):
        db = input_board('series', connector=False)
        add(db, 'U1', 'CTRL', [('1', 'GATE', 'GATE'), ('2', 'UV', 'UV_SET'), ('3', 'GND', 'GND')])
        plan = plan_of(db, 'POWER_PROTECTION', ['Q1', 'U1'])
        self.assertEqual([r['object']['ref'] for r in asked(plan, 'PWR-C06')], ['U1'])

    def test_a_bare_switch_has_none(self):
        plan = plan_of(input_board('series', connector=False), 'POWER_PROTECTION', ['Q1'])
        self.assertEqual(asked(plan, 'PWR-C06'), [])
        self.assertEqual(not_asked(plan)['PRO-C01'], 'PROTECTION_PART')


def led_board():
    db = empty()
    add(db, 'D1', 'LED', [('1', 'A', 'LED_A'), ('2', 'K', 'GND')])
    add(db, 'R1', '1k', [('1', '1', 'V5'), ('2', '2', 'LED_A')])
    return db


class SenseAndAnalogTests(unittest.TestCase):
    def test_an_led_branch_is_asked_nothing_analog_and_the_plan_says_change_the_type(self):
        plan = plan_of(led_board(), 'ANALOG', ['D1', 'R1'])
        self.assertEqual([c for c in plan['checks'] if (c.get('object') or {}).get('circuit') == 'CKT'
                          and c.get('circuit_type')], [])
        self.assertEqual(set(not_asked(plan)), set(catalog.circuit_type('ANALOG').subjects))
        misfit = [d for d in plan['diagnostics'] if d['code'] == 'CIRCUIT_TYPE_MISFIT']
        self.assertEqual([(d['circuit'], d['circuit_type'], d['asked']) for d in misfit], [('CKT', 'ANALOG', [])])

    def test_a_shunt_or_thermistor_is_a_sense_element(self):
        db = led_board()
        add(db, 'R2', '0.05', [('1', '1', 'V5'), ('2', '2', 'V5_S')])
        plan = plan_of(db, 'ANALOG', ['D1', 'R1', 'R2'])
        self.assertEqual([r['object']['ref'] for r in asked(plan, 'ANA-T01')], ['R2'])
        db = led_board()
        add(db, 'R2', 'NTC 10k', [('1', '1', 'TEMP'), ('2', '2', 'GND')])
        add(db, 'U1', 'MCU', [('1', 'GPIO3', 'TEMP'), ('2', 'VDD', 'V3'), ('3', 'GND', 'GND')])
        plan = plan_of(db, 'ANALOG', ['R2'])
        self.assertEqual([r['object']['ref'] for r in asked(plan, 'ANA-T01')], ['R2'])
        self.assertEqual([r['object']['ref'] for r in asked(plan, 'ANA-D01')], ['R2'])   # a temperature sensor

    def test_an_inrush_thermistor_in_the_supply_is_no_sensor(self):
        db = input_board(connector=False)
        add(db, 'TH1', 'NTC 5R', [('1', '1', 'VIN'), ('2', '2', 'VIN_B')])
        plan = plan_of(db, 'POWER_PROTECTION', ['F1', 'TH1'])
        self.assertEqual(asked(plan, 'ANA-T01'), [])
        self.assertEqual([r['object']['ref'] for r in asked(plan, 'PWR-C06')], ['F1'])

    def test_a_divider_into_an_ic_pin_is_one(self):
        db = empty()
        add(db, 'R1', '100k', [('1', '1', 'VIN'), ('2', '2', 'SENSE')])
        add(db, 'R2', '10k', [('1', '1', 'SENSE'), ('2', '2', 'GND')])
        add(db, 'U1', 'SUP', [('1', 'VDD', 'V3'), ('2', 'SENSE', 'SENSE'), ('3', 'GND', 'GND')])
        plan = plan_of(db, 'ANALOG', ['R1', 'R2', 'U1'])
        self.assertEqual([r['object']['ref'] for r in asked(plan, 'ANA-T01')], ['U1'])

    def test_amplifier_pins_are_asked_the_analog_rules(self):
        db = empty()
        add(db, 'U1', 'OPAMP', [('1', 'IN+', 'INP'), ('2', 'IN-', 'INN'), ('3', 'OUT', 'AOUT'), ('4', 'V+', 'V5'),
                                ('5', 'V-', 'GND')])
        plan = plan_of(db, 'ANALOG', ['U1'])
        for rule in ('ANA-C01', 'ANA-C02', 'ANA-C03', 'ANA-D01'):
            self.assertEqual([r['object']['ref'] for r in asked(plan, rule)], ['U1'], rule)


class StartupPinTests(unittest.TestCase):
    def test_a_start_up_circuit_without_reset_enable_or_strap_pins_is_asked_no_reset_rows(self):
        db = empty()
        add(db, 'U1', 'PWM', [('1', 'HV', 'BULK'), ('2', 'VCC', 'VCC'), ('3', 'GATE', 'GATE'), ('4', 'GND', 'GND')])
        add(db, 'C1', '22uF', [('1', '1', 'VCC'), ('2', '2', 'GND')])
        plan = plan_of(db, 'STARTUP', ['U1', 'C1'])
        self.assertEqual(set(not_asked(plan)), set(catalog.circuit_type('STARTUP').subjects))
        self.assertTrue(any(d['code'] == 'CIRCUIT_TYPE_MISFIT' for d in plan['diagnostics']))

    def test_a_reset_pin_is_asked_on_its_ic(self):
        db = empty()
        add(db, 'U1', 'MCU', [('1', 'NRST', 'NRST'), ('2', 'VDD', 'V3'), ('3', 'GND', 'GND')])
        add(db, 'C1', '100nF', [('1', '1', 'NRST'), ('2', '2', 'GND')])
        plan = plan_of(db, 'STARTUP', ['C1', 'U1'])
        for rule in catalog.circuit_type('STARTUP').subjects:
            self.assertEqual([r['object']['ref'] for r in asked(plan, rule)], ['U1'], rule)


class UnreadNetlistTests(unittest.TestCase):
    def test_a_part_of_unknown_kind_or_an_ic_without_pin_names_keeps_the_rule(self):
        db = input_board(connector=False)
        add(db, 'Z1', 'X', [('1', '1', 'VIN'), ('2', '2', 'GND'), ('3', '3', 'VIN_RAW')])   # nothing tells its kind
        add(db, 'Z2', 'X', [('1', '1', 'VIN'), ('2', '2', 'GND')])
        plan = plan_of(db, 'POWER_PROTECTION', ['D1', 'Z1'])
        rows = asked(plan, 'DRV-C02')
        self.assertEqual([r['object']['ref'] for r in rows], ['Z1'])
        self.assertEqual(rows[0]['requires'], {'id': 'POWER_SWITCH', 'found': [], 'unread': ['Z1']})
        plan = plan_of(db, 'POWER_PROTECTION', ['D1', 'Z2'])   # two terminals: no transistor, maybe a varistor
        self.assertEqual(asked(plan, 'DRV-C02'), [])
        self.assertEqual([r['object']['ref'] for r in asked(plan, 'PWR-C06')], ['Z2'])
        db = empty()
        add(db, 'U1', 'CTRL', [('1', None, 'A'), ('2', None, 'B')])
        plan = plan_of(db, 'STARTUP', ['U1'])
        self.assertEqual(len(asked(plan, 'RST-C01')), 1)
        self.assertEqual(plan['diagnostics'] and [d for d in plan['diagnostics'] if d['code'] == 'CIRCUIT_TYPE_MISFIT'], [])

    def test_a_rule_not_asked_is_listed_once_for_all_states(self):
        plan = plan_of(input_board(), 'POWER_PROTECTION', ['F1', 'D1', 'C1'], states=('RUN', 'SURGE'))
        self.assertEqual([i['rule'] for i in frame(plan)['not_asked']].count('DRV-C02'), 1)
        self.assertEqual(frame(plan)['not_asked'][0].keys(), {'rule', 'aspect', 'requires', 'why'})


class ReportTests(unittest.TestCase):
    def test_the_report_says_what_was_not_asked_and_why(self):
        plan = plan_of(input_board(), 'POWER_PROTECTION', ['F1', 'D1', 'C1'])
        fn = {'id': frame(plan)['id'], 'question': 'q', 'verdict': 'PASS'}
        text = '\n'.join(render_functions([fn], plan, []))
        self.assertIn('未问：', text)
        self.assertIn('%s（%s）' % (catalog.title('DRV-C02'), catalog.SUBJECT_PRECONDITIONS['POWER_SWITCH']), text)


class NotApplicablePassTests(unittest.TestCase):
    """2c: a PASS that only says the aspect does not apply, with no netlist fact, is an NA."""

    def judged(self, conditions, says='按拓扑不适用'):
        fn = bias_function('PASS')
        fn['judgements'] = [{'aspect': '启动与关断时序', 'conditions': conditions, 'says': says, 'states': list(STATES)}]
        return function_errors({'functions': [fn]})

    def test_a_pass_saying_does_not_apply_on_a_clause_alone_is_refused(self):
        found = self.judged(['c4'])
        self.assertTrue(any('does not apply' in e and 'NA' in e for e in found), found)
        for says in ('无此问题', '按拓扑无反接问题', '不涉及'):
            self.assertTrue(any('does not apply' in e for e in self.judged(['c4'], says)), says)

    def test_a_netlist_fact_or_a_real_judgement_stands(self):
        self.assertFalse([e for e in self.judged(['c4', 'c5']) if 'does not apply' in e])
        self.assertFalse([e for e in self.judged(['c4'], '手册要求 EN 上拉到 VIN，本板经 R3 上拉') if 'does not apply' in e])


class NotApplicableEvidenceTests(unittest.TestCase):
    """2d: where the precondition holds, an NA names the netlist fact that rules the mechanism out."""

    def na(self, evidence, requires=True):
        p, r, db = ledger(bias_function('PASS'))
        cid = 'DRV-C02.BIAS-RUN.R1'
        row = dict(planned(cid), object={'circuit': 'BIAS', 'ref': 'R1', 'state': 'RUN'}, criterion='soa')
        if requires:
            row['requires'] = {'id': 'POWER_SWITCH', 'found': ['R1']}
        p['checks'].append(row)
        r['checks'].append({'id': cid, 'applicability': 'NOT_APPLICABLE', 'review_result': 'NA', 'evidence': E,
                            'rationale': 'R1 不是功率管', 'handoff': {'required': False},
                            'applicability_evidence': evidence})
        r['plan_digest'] = fingerprint(p)
        return [e for e in vr.validate_review(p, r, db)['errors'] if e.startswith(cid)]

    def test_a_located_sentence_is_not_enough(self):
        found = self.na([{'source': 'db.json', 'locator': 'pin2net/nets/parts 实际物理端点'}])
        self.assertTrue(any('netlist fact' in e for e in found), found)

    def test_named_nets_or_pins_the_netlist_has_are(self):
        self.assertEqual(self.na([{'source': 'db.json', 'locator': 'R1 两端', 'nets': ['A']}]), [])
        self.assertEqual(self.na([{'source': 'db.json', 'locator': 'R1.1', 'pins': ['R1.1']}]), [])
        found = self.na([{'source': 'db.json', 'locator': 'Q9', 'pins': ['Q9.1']}])
        self.assertTrue(any('Q9.1' in e for e in found), found)

    def test_a_row_without_a_precondition_keeps_the_located_evidence_rule(self):
        self.assertEqual(self.na(copy.deepcopy(E), requires=False), [])


if __name__ == '__main__':
    unittest.main()

"""Three machine checks over judgement conclusions: coverage, consistency, traceability (design §4).

A valid synthetic board is checked clean; each of the ten injected errors of design §8.4 is caught by the
check that owns it."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import conclusions_check as cc


def db():
    return {
        'parts': {'R3': {'value': '1k/0603'}, 'R4': {'value': '10k 1%'}, 'C5': {'value': '100nF/50V'},
                  'U2': {'value': 'BRIDGE'}, 'U3': {'value': 'MCU'}, 'D2': {'value': 'LED'}},
        'nets': {'TXD': ['U2.8', 'U3.34'], 'RXD': ['U3.35', 'U2.9'], 'V5': ['U2.1', 'R3.1'], 'LED_A': ['R3.2', 'D2.1'],
                 'GND': ['D2.2', 'U2.2', 'U3.1']},
        'pin2net': {'U2.8': 'TXD', 'U3.34': 'TXD', 'U3.35': 'RXD', 'U2.9': 'RXD', 'U2.1': 'V5', 'R3.1': 'V5',
                    'R3.2': 'LED_A', 'D2.1': 'LED_A', 'D2.2': 'GND', 'U2.2': 'GND', 'U3.1': 'GND'},
        'no_connect_nodes': [], 'pseudo_nets': []}


def questions():
    def q(qid, observations=(), undetermined=False, states=()):
        return {'id': qid, 'rules': ['X-' + qid], 'check_ids': [qid + '.row'], 'undetermined': undetermined,
                'observations': list(observations), 'conditions': {'states': list(states)}}
    return {'questions': [
        q('Q-LED'), q('Q-LED-CALC'),
        q('Q-UART', [{'id': 'O-1', 'kind': 'SUSPECT', 'says': 'TXD 与 RXD 可能交叉接反', 'input': False}]),
        q('Q-GATE', [{'id': 'O-1', 'kind': 'SUSPECT', 'says': 'Q1 栅极无下拉', 'input': False}]),
        q('Q-VF'), q('Q-ESR')]}


def clauses():
    return [{'id': 'K-LED', 'kind': 'DATASHEET', 'source': 'ds/D2.txt', 'locator': 'p2 Table 1', 'says': 'IF ≥ 2 mA 时亮度达标'},
            {'id': 'K-VF', 'kind': 'DATASHEET', 'source': 'ds/D2.txt', 'locator': 'p2 Table 1', 'says': 'VF 1.8–2.1 V @ 2 mA, 25 °C'},
            {'id': 'K-VF-COLD', 'kind': 'DATASHEET', 'source': 'ds/D2.txt', 'locator': 'p3 Fig 4 典型温度曲线',
             'says': '−20 °C 下 VF 最高约 2.9 V（典型曲线外推，无保证值）'},
            {'id': 'K-V5', 'kind': 'DATASHEET', 'source': 'ds/U2.txt', 'locator': 'p5 V5', 'says': 'V5 4.75–5.25 V'},
            {'id': 'K-PINS', 'kind': 'DATASHEET', 'source': 'ds/U2.txt', 'locator': 'p3 pin table', 'says': 'pin 8 TXD, pin 9 RXD'},
            {'id': 'K-C5', 'kind': 'DATASHEET', 'source': 'ds/C5.txt', 'locator': 'p1', 'says': 'ESR 20 °C only'},
            {'id': 'K-ASSUME', 'kind': 'ASSUMPTION', 'source': 'notes.md', 'locator': '## 假定',
             'says': '指示电流取 ≥ 2.5 mA；VF 取 3.0–3.5 V'}]


def led_inputs():
    return {'v5': {'min': 4.75, 'max': 5.25, 'unit': 'V', 'from': {'clause': 'K-V5'}},
            'vf': {'min': 1.8, 'max': 2.1, 'unit': 'V', 'from': {'clause': 'K-VF'}},
            'r': {'value': 1, 'unit': 'kΩ', 'from': {'db': {'ref': 'R3', 'parse': 'resistance'}}}}


def numeric(inputs, result, limit=2.0, clause='K-LED', calc='(v5 - vf) / r'):
    return {'kind': 'NUMERIC', 'calc': calc, 'inputs': inputs, 'result': result,
            'criterion': {'limit': limit, 'unit': 'mA', 'direction': 'value_above_limit', 'clause': clause}}


def conclusions():
    return [
        {'question': 'Q-LED', 'outcome': 'PASS', 'basis': numeric(led_inputs(), {'min': 2.65, 'max': 3.45})},
        {'question': 'Q-LED-CALC', 'outcome': 'PASS', 'basis': {
            'kind': 'NUMERIC',
            'criterion': {'limit': 0.002, 'unit': 'A', 'direction': 'value_above_limit', 'clause': 'K-LED'},
            'calc': 'circuit_bounds.series_resistor_current', 'output': 'i_min_a', 'result': {'min': 0.00265, 'max': 0.00265},
            'inputs': {'v_supply_min_v': {'value': 4.75, 'unit': 'V', 'from': {'clause': 'K-V5'}},
                       'v_supply_max_v': {'value': 5.25, 'unit': 'V', 'from': {'clause': 'K-V5'}},
                       'v_drop_min_v': {'value': 1.8, 'unit': 'V', 'from': {'clause': 'K-VF'}},
                       'v_drop_max_v': {'value': 2.1, 'unit': 'V', 'from': {'clause': 'K-VF'}},
                       'r_ohm': {'value': 1000, 'unit': 'Ω', 'from': {'db': {'ref': 'R3', 'parse': 'resistance'}}},
                       'r_tol': {'value': 0, 'unit': '', 'from': {'clause': 'K-LED'}}}}},
        {'question': 'Q-UART', 'outcome': 'PASS', 'basis': {
            'kind': 'FACT', 'clauses': ['K-PINS'],
            'facts': [{'node': 'U2.8', 'net_same_as': 'U3.34', 'means': 'U2 TXD 接 U3 RXD'},
                      {'node': 'U3.35', 'net_same_as': 'U2.9', 'means': 'U3 TXD 接 U2 RXD'}]},
         'disagrees': [{'observation': 'O-1', 'why': 'U3.34 是 RXD，交叉正确'}]},
        {'question': 'Q-GATE', 'outcome': 'FAIL', 'basis': {
            'kind': 'FACT', 'clauses': ['K-PINS'], 'facts': [{'node': 'U2.1', 'net_is': 'V5', 'means': '栅极只接驱动'}]},
         'fix': {'change': '加 100 k 栅极下拉', 'readiness': 'READY', 'recheck': '上电时栅极 < 0.5 V'},
         'severity': {'level': 'P2', 'class': 'LOCAL_OR_DATA', 'consequence': '上电瞬间误导通'}},
        {'question': 'Q-VF', 'outcome': 'UNDECIDED',
         'missing': {'what': 'D2 在 −20 °C 的 VF 上限', 'from': 'VENDOR', 'closes_when': 'VF ≤ 2.6 V @ 2 mA, −20 °C'},
         'basis': numeric(dict(led_inputs(), vf={'min': 1.8, 'max': 2.9, 'unit': 'V', 'from': {'clause': 'K-VF-COLD'}}),
                          {'min': 1.85, 'max': 3.45}),
         'loose_input': 'vf',
         'failure_path': {'mechanism': '−20 °C 时 VF 升高，IF 低于 2 mA，指示偏暗'},
         'severity': {'level': 'P2', 'class': 'LOCAL_OR_DATA', 'consequence': '低温指示偏暗'}},
        {'question': 'Q-ESR', 'outcome': 'UNDECIDED',
         'missing': {'what': 'C5 在 −20 °C 的 ESR', 'from': 'VENDOR', 'closes_when': 'ESR ≤ 120 mΩ'},
         'searched': [{'source': 'ds/C5.txt', 'locator': 'p1 特性表'}],
         'failure_path': {'mechanism': '低温 ESR 升高，输出纹波超出下游输入窗口'},
         'severity': {'level': 'P3', 'class': 'OPTIMIZATION', 'consequence': '低温纹波略大'}},
    ]


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / 'ds').mkdir()
        for name in ('ds/D2.txt', 'ds/U2.txt', 'ds/C5.txt', 'notes.md'):
            (root / name).write_text('stub', encoding='utf-8')
        self.root = root

    def tearDown(self):
        self.tmp.cleanup()

    def run_check(self, qs=None, ks=None, cs=None, d=None):
        return cc.check(qs or questions(), ks or clauses(), cs if cs is not None else conclusions(), d or db(), self.root)

    def codes(self, out):
        return [(e['check'], e['code']) for e in out['errors']]


class CleanTests(Fixture):
    def test_the_synthetic_board_is_clean_and_every_number_is_recomputed(self):
        out = self.run_check()
        self.assertEqual(out['errors'], [])
        self.assertTrue(out['valid'])
        self.assertEqual(out['summary']['recomputed'], 3)
        self.assertEqual(out['summary']['facts_checked'], 3)
        self.assertEqual(out['summary']['outcomes'], {'PASS': 3, 'FAIL': 1, 'UNDECIDED': 2})
        self.assertEqual(out['summary']['release'], 'CAN_FREEZE')
        self.assertEqual(out['summary']['defects'], 1)
        self.assertEqual(out['summary']['gaps'], 2)
        self.assertEqual(out['summary']['constraints'], [])


class InjectedErrorTests(Fixture):
    """Design §8.4: the same ten errors are injected into both arms of the comparison."""

    def conclusion(self, cs, qid):
        return next(c for c in cs if c['question'] == qid)

    def assert_caught(self, check, code, cs=None, qs=None, d=None):
        out = self.run_check(qs=qs, cs=cs, d=d)
        self.assertFalse(out['valid'])
        self.assertIn((check, code), self.codes(out), out['errors'])

    def test_01_negative_margin_judged_pass(self):
        cs = conclusions(); c = self.conclusion(cs, 'Q-VF')
        c['outcome'] = 'PASS'
        for k in ('missing', 'loose_input', 'severity'):
            c.pop(k)
        self.assert_caught('CONSISTENCY', 'PASS_NOT_PROVEN', cs)

    def test_02_question_nobody_answered(self):
        cs = [c for c in conclusions() if c['question'] != 'Q-ESR']
        self.assert_caught('COVERAGE', 'UNANSWERED', cs)

    def test_03_schematic_value_written_differently(self):
        cs = conclusions(); self.conclusion(cs, 'Q-LED')['basis']['inputs']['r']['value'] = 0.82
        self.assert_caught('TRACE', 'DB_VALUE_MISMATCH', cs)

    def test_04_clause_that_does_not_exist(self):
        cs = conclusions(); self.conclusion(cs, 'Q-LED')['basis']['criterion']['clause'] = 'K-NONE'
        self.assert_caught('TRACE', 'UNKNOWN_CLAUSE', cs)

    def test_05_stated_worst_case_does_not_follow_from_the_inputs(self):
        cs = conclusions(); self.conclusion(cs, 'Q-LED')['basis']['result']['max'] = 3.6
        self.assert_caught('TRACE', 'RECOMPUTE_MISMATCH', cs)

    def test_06_public_bound_already_decides_but_left_open(self):
        cs = conclusions(); b = self.conclusion(cs, 'Q-VF')['basis']
        b['inputs']['vf']['max'] = 2.1; b['result']['min'] = 2.65
        self.assert_caught('CONSISTENCY', 'ALREADY_DECIDED', cs)

    def test_07_undecided_without_what_or_from_whom(self):
        cs = conclusions(); del self.conclusion(cs, 'Q-ESR')['missing']['from']
        self.assert_caught('CONSISTENCY', 'MISSING_INCOMPLETE', cs)

    def test_08_tool_suspicion_nobody_answered(self):
        cs = conclusions(); del self.conclusion(cs, 'Q-UART')['disagrees']
        self.assert_caught('COVERAGE', 'SUSPECT_UNANSWERED', cs)

    def test_09_fail_without_a_fix(self):
        cs = conclusions(); del self.conclusion(cs, 'Q-GATE')['fix']
        self.assert_caught('CONSISTENCY', 'FAIL_WITHOUT_FIX', cs)

    def test_10_connection_stated_against_the_netlist(self):
        cs = conclusions(); self.conclusion(cs, 'Q-UART')['basis']['facts'][0]['net_same_as'] = 'U3.35'
        self.assert_caught('TRACE', 'FACT_FALSE', cs)


class RuleTests(Fixture):
    def test_a_missing_input_cannot_sit_under_a_pass_unless_answered(self):
        qs = questions()
        qs['questions'][0]['observations'] = [{'id': 'O-1', 'kind': 'MISSING_INPUT', 'says': 'intent.x', 'input': True}]
        out = self.run_check(qs=qs)
        self.assertIn(('COVERAGE', 'MISSING_INPUT_UNDER_PASS'), self.codes(out))
        cs = conclusions(); cs[0]['disagrees'] = [{'observation': 'O-1', 'why': '该输入不进本题的算式'}]
        self.assertTrue(self.run_check(qs=qs, cs=cs)['valid'])

    def test_disagreement_must_name_an_observation_of_its_question(self):
        cs = conclusions(); cs[0]['disagrees'] = [{'observation': 'O-9', 'why': 'x'}]
        self.assertIn(('COVERAGE', 'UNKNOWN_OBSERVATION'), self.codes(self.run_check(cs=cs)))

    def test_a_shortfall_kept_open_names_an_input_of_the_bound(self):
        for name in ('temperature', 'r'):   # not an input; an input given as one value
            cs = conclusions(); next(c for c in cs if c['question'] == 'Q-VF')['loose_input'] = name
            self.assertIn(('CONSISTENCY', 'LOOSE_INPUT_UNKNOWN'), self.codes(self.run_check(cs=cs)), name)

    def test_no_bound_from_a_vendor_lists_what_was_searched(self):
        cs = conclusions(); del next(c for c in cs if c['question'] == 'Q-ESR')['searched']
        self.assertIn(('CONSISTENCY', 'NO_BOUND_NOT_SEARCHED'), self.codes(self.run_check(cs=cs)))
        cs = conclusions(); c = next(c for c in cs if c['question'] == 'Q-ESR'); del c['searched']
        c['missing']['from'] = 'DESIGN'
        self.assertTrue(self.run_check(cs=cs)['valid'])

    def test_unspecified_operating_point_is_a_fail_not_undecided(self):
        cs = conclusions(); c = next(c for c in cs if c['question'] == 'Q-ESR')
        c.update(basis={'kind': 'UNSPECIFIED', 'clause': 'K-V5', 'specified': 'V5 只在 VDD > 6 V 时规定', 'operating': 'VDD 4.75 V'})
        self.assertIn(('CONSISTENCY', 'UNSPECIFIED_NOT_FAIL'), self.codes(self.run_check(cs=cs)))
        c.update(outcome='FAIL', fix={'change': 'LED 改由 VDD 供电', 'readiness': 'READY'})
        for k in ('missing', 'searched'):
            c.pop(k)
        self.assertTrue(self.run_check(cs=cs)['valid'], self.run_check(cs=cs)['errors'])

    def test_not_applicable_only_where_the_plan_left_applicability_open(self):
        cs = conclusions(); c = cs[0]
        c['outcome'] = 'NA'
        self.assertIn(('CONSISTENCY', 'NA_NOT_OPEN'), self.codes(self.run_check(cs=cs)))
        qs = questions(); qs['questions'][0]['undetermined'] = True
        c['basis'] = {'kind': 'FACT', 'clauses': ['K-PINS'], 'facts': [{'node': 'U2.8', 'net_is': 'TXD', 'means': '不是差分对'}]}
        self.assertTrue(self.run_check(qs=qs, cs=cs)['valid'])

    def test_release_is_blocked_by_a_p1_fail_or_a_p0_undecided(self):
        cs = conclusions()
        next(c for c in cs if c['question'] == 'Q-GATE')['severity'].update(level='P1', **{'class': 'COMPONENT_DAMAGE'})
        self.assertEqual(self.run_check(cs=cs)['summary']['release'], 'CANNOT_FREEZE')
        cs = conclusions()
        next(c for c in cs if c['question'] == 'Q-ESR')['severity'].update(level='P0', **{'class': 'DAMAGE_OR_HAZARD'})
        out = self.run_check(cs=cs)
        self.assertTrue(out['valid'], out['errors'])
        self.assertEqual(out['summary']['release'], 'CANNOT_FREEZE')

    def test_clause_source_must_exist(self):
        ks = clauses(); ks[0]['source'] = 'ds/missing.txt'
        out = self.run_check(ks=ks)
        self.assertIn(('TRACE', 'CLAUSE_SOURCE_MISSING'), self.codes(out))

    def test_fact_on_a_node_the_netlist_does_not_have(self):
        cs = conclusions(); next(c for c in cs if c['question'] == 'Q-UART')['basis']['facts'][0]['node'] = 'U2.99'
        self.assertIn(('TRACE', 'UNKNOWN_NODE'), self.codes(self.run_check(cs=cs)))


class OutcomeFromIntervalTests(Fixture):
    """A numeric conclusion's outcome follows from its inputs' ranges: pass when the worst corner passes,
    fail when even the most favourable corner fails, undecided in between."""

    def vf(self, cs, lo, hi, result):
        c = next(c for c in cs if c['question'] == 'Q-VF')
        c['basis']['inputs']['vf'].update(min=lo, max=hi)
        c['basis']['result'] = result
        return c

    def as_fail(self, c):
        for k in ('missing', 'loose_input'):
            c.pop(k)
        c.update(outcome='FAIL', fix={'change': 'R3 改 680 Ω', 'readiness': 'READY'})

    def test_corners_give_the_range_and_the_derived_margins(self):
        out = self.run_check()
        derived = {d['question']: d for d in out['derived']}
        self.assertEqual(derived['Q-LED']['outcome'], 'PASS')
        self.assertAlmostEqual(derived['Q-LED']['worst_margin'], 0.65)
        self.assertAlmostEqual(derived['Q-LED']['best_margin'], 1.45)
        self.assertEqual(derived['Q-VF']['outcome'], 'UNDECIDED')

    def test_a_fail_holds_at_the_most_favourable_corner(self):
        cs = conclusions(); c = self.vf(cs, 3.3, 3.5, {'min': 1.25, 'max': 1.95}); self.as_fail(c)
        out = self.run_check(cs=cs)
        self.assertTrue(out['valid'], out['errors'])

    def test_a_fail_the_favourable_corner_passes_is_too_strict(self):
        cs = conclusions(); c = self.vf(cs, 1.8, 2.9, {'min': 1.85, 'max': 3.45}); self.as_fail(c)
        self.assertIn(('STRICTNESS', 'FAIL_NOT_PROVEN'), self.codes(self.run_check(cs=cs)))

    def test_a_limit_given_as_a_range_is_taken_at_its_lenient_end_for_a_fail(self):
        cs = conclusions(); c = self.vf(cs, 3.3, 3.5, {'min': 1.25, 'max': 1.95}); self.as_fail(c)
        c['basis']['criterion']['limit'] = {'min': 1.9, 'max': 2.0}
        self.assertIn(('STRICTNESS', 'FAIL_NOT_PROVEN'), self.codes(self.run_check(cs=cs)))


class StrictnessTests(Fixture):
    """Four guards against an over-strict review."""

    def fail_on(self, cs, clause='K-LED', vf_from='K-VF-COLD', vf=(3.3, 3.5)):
        c = next(c for c in cs if c['question'] == 'Q-VF')
        b = c['basis']
        b['criterion']['clause'] = clause
        b['inputs']['vf'] = {'min': vf[0], 'max': vf[1], 'unit': 'V', 'from': {'clause': vf_from}}
        b['result'] = {'min': 4.75 - vf[1], 'max': 5.25 - vf[0]}
        for k in ('missing', 'loose_input'):
            c.pop(k)
        c.update(outcome='FAIL', fix={'change': 'R3 改 680 Ω', 'readiness': 'READY'})
        return c

    def test_clauses_say_where_they_come_from(self):
        ks = clauses(); del ks[0]['kind']
        self.assertIn(('TRACE', 'CLAUSE_INCOMPLETE'), self.codes(self.run_check(ks=ks)))

    def test_no_fail_against_a_limit_the_reviewer_assumed(self):
        cs = conclusions(); self.fail_on(cs, clause='K-ASSUME')
        self.assertIn(('STRICTNESS', 'FAIL_ON_ASSUMED_LIMIT'), self.codes(self.run_check(cs=cs)))
        cs = conclusions(); g = next(c for c in cs if c['question'] == 'Q-GATE'); g['basis']['clauses'] = ['K-ASSUME']
        self.assertIn(('STRICTNESS', 'FAIL_ON_ASSUMED_LIMIT'), self.codes(self.run_check(cs=cs)))

    def test_an_assumed_input_supports_a_fail_only_as_a_range(self):
        cs = conclusions(); self.fail_on(cs, vf_from='K-ASSUME', vf=(3.3, 3.5))
        self.assertTrue(self.run_check(cs=cs)['valid'], self.run_check(cs=cs)['errors'])
        cs = conclusions(); self.fail_on(cs, vf_from='K-ASSUME', vf=(3.3, 3.3))
        self.assertIn(('STRICTNESS', 'FAIL_ON_ASSUMED_POINT'), self.codes(self.run_check(cs=cs)))

    def test_one_change_is_one_defect(self):
        cs = conclusions(); c = self.fail_on(cs); c['fix'] = {'change': '加 100 k 栅极下拉', 'readiness': 'READY'}
        self.assertIn(('STRICTNESS', 'DUPLICATE_DEFECT'), self.codes(self.run_check(cs=cs)))
        c['fix'] = {'same_as': 'Q-GATE'}
        out = self.run_check(cs=cs)
        self.assertTrue(out['valid'], out['errors'])
        self.assertEqual(out['summary']['defects'], 1)
        c['fix'] = {'same_as': 'Q-LED'}
        self.assertIn(('CONSISTENCY', 'FIX_SAME_AS_UNKNOWN'), self.codes(self.run_check(cs=cs)))

    def test_severity_no_higher_than_its_consequence_class(self):
        cs = conclusions(); g = next(c for c in cs if c['question'] == 'Q-GATE')
        g['severity']['level'] = 'P1'
        self.assertIn(('STRICTNESS', 'SEVERITY_ABOVE_CLASS'), self.codes(self.run_check(cs=cs)))
        g['severity']['level'] = 'P3'
        self.assertTrue(self.run_check(cs=cs)['valid'])
        del g['severity']['class']
        self.assertIn(('CONSISTENCY', 'SEVERITY_MISSING'), self.codes(self.run_check(cs=cs)))

    def test_an_undecided_requirement_is_not_graded_and_does_not_block(self):
        cs = conclusions(); e = next(c for c in cs if c['question'] == 'Q-ESR')
        e['missing']['from'] = 'REQUIREMENT'; e.pop('searched')
        e['severity'].update(level='P0', **{'class': 'DAMAGE_OR_HAZARD'})
        self.assertIn(('STRICTNESS', 'REQUIREMENT_GRADED'), self.codes(self.run_check(cs=cs)))
        e.pop('severity')
        out = self.run_check(cs=cs)
        self.assertTrue(out['valid'], out['errors'])
        self.assertEqual(out['summary']['release'], 'CAN_FREEZE')


class UndecidedTests(Fixture):
    """Five guards against undecided conclusions that need not be: an engineering bound from public values,
    a failure path, procurement as a constraint, a recommended configuration, one gap counted once."""

    def c(self, cs, qid):
        return next(c for c in cs if c['question'] == qid)

    def vf_as(self, cs, item, result, outcome='UNDECIDED'):
        c = self.c(cs, 'Q-VF')
        c['basis']['inputs']['vf'] = dict(item, unit='V', **{'from': {'clause': 'K-VF'}})
        c['basis']['result'] = result
        c['outcome'] = outcome
        if outcome == 'PASS':
            for k in ('missing', 'loose_input', 'failure_path', 'severity'):
                c.pop(k)
        return c

    def test_a_25c_guarantee_widened_by_the_floor_decides(self):
        cs = conclusions(); self.vf_as(cs, {'at_25c': {'min': 1.8, 'max': 2.1}}, {'min': 2.23, 'max': 3.81})
        self.assertIn(('CONSISTENCY', 'ALREADY_DECIDED'), self.codes(self.run_check(cs=cs)))
        cs = conclusions(); self.vf_as(cs, {'at_25c': {'min': 1.8, 'max': 2.1}}, {'min': 2.23, 'max': 3.81}, 'PASS')
        out = self.run_check(cs=cs)
        self.assertTrue(out['valid'], out['errors'])
        d = next(x for x in out['derived'] if x['question'] == 'Q-VF')
        self.assertEqual(d['outcome'], 'PASS')

    def test_a_typical_value_is_widened_threefold_both_ways(self):
        cs = conclusions(); self.vf_as(cs, {'typical': 1.95}, {'min': 4.75 - 5.85, 'max': 5.25 - 0.65})
        out = self.run_check(cs=cs)
        self.assertTrue(out['valid'], out['errors'])
        cs = conclusions(); self.vf_as(cs, {'typical': 1.95, 'widen': 2}, {'min': 4.75 - 3.9, 'max': 5.25 - 0.975})
        self.assertIn(('TRACE', 'ENGINEERING_TOO_NARROW'), self.codes(self.run_check(cs=cs)))
        cs = conclusions(); self.vf_as(cs, {'at_25c': 2.0, 'widen': 0.1}, {'min': 2.55, 'max': 3.45})
        self.assertIn(('TRACE', 'ENGINEERING_TOO_NARROW'), self.codes(self.run_check(cs=cs)))

    def test_a_named_quantity_takes_its_own_typical_floor(self):
        cs = conclusions(); self.vf_as(cs, {'typical': 1.95, 'quantity': 'forward_voltage'},
                                       {'min': 4.75 - 3.9, 'max': 5.25 - 0.975})
        out = self.run_check(cs=cs)
        self.assertTrue(out['valid'], out['errors'])
        cs = conclusions(); self.vf_as(cs, {'typical': 1.95, 'quantity': 'forward_voltage', 'widen': 1.5},
                                       {'min': 4.75 - 2.925, 'max': 5.25 - 1.3})
        self.assertIn(('TRACE', 'ENGINEERING_TOO_NARROW'), self.codes(self.run_check(cs=cs)))
        cs = conclusions(); self.vf_as(cs, {'typical': 1.95, 'quantity': 'volts'}, {'min': 4.75 - 5.85, 'max': 5.25 - 0.65})
        self.assertIn(('TRACE', 'QUANTITY_UNKNOWN'), self.codes(self.run_check(cs=cs)))

    def test_a_leakage_current_is_widened_more_than_the_default(self):
        cs = conclusions(); self.vf_as(cs, {'typical': 1.95, 'quantity': 'leakage_current'},
                                       {'min': 4.75 - 1950, 'max': 5.25 - 0.00195})
        out = self.run_check(cs=cs)
        self.assertTrue(out['valid'], out['errors'])
        cs = conclusions(); self.vf_as(cs, {'typical': 1.95, 'quantity': 'leakage_current', 'widen': 3},
                                       {'min': 4.75 - 5.85, 'max': 5.25 - 0.65})
        self.assertIn(('TRACE', 'ENGINEERING_TOO_NARROW'), self.codes(self.run_check(cs=cs)))

    def test_a_25c_leakage_grows_to_the_hot_corner_and_not_below_zero(self):
        cs = conclusions(); self.vf_as(cs, {'at_25c': 2.0, 'quantity': 'leakage_current'}, {'min': 4.75 - 128, 'max': 5.25})
        out = self.run_check(cs=cs)
        self.assertTrue(out['valid'], out['errors'])
        cs = conclusions(); self.vf_as(cs, {'at_25c': 2.0, 'quantity': 'leakage_current', 'widen': 0.2},
                                       {'min': 4.75 - 2.4, 'max': 5.25})
        self.assertIn(('TRACE', 'ENGINEERING_TOO_NARROW'), self.codes(self.run_check(cs=cs)))

    def test_an_engineering_bound_widens_a_datasheet_value_only(self):
        cs = conclusions(); c = self.vf_as(cs, {'at_25c': {'min': 1.8, 'max': 2.1}}, {'min': 2.23, 'max': 3.81}, 'PASS')
        c['basis']['inputs']['vf']['from'] = {'clause': 'K-ASSUME'}
        self.assertIn(('TRACE', 'ENGINEERING_NOT_DATASHEET'), self.codes(self.run_check(cs=cs)))

    def test_a_searched_value_left_unused_is_refused(self):
        cs = conclusions(); self.c(cs, 'Q-ESR')['searched'][0]['value'] = '45 mΩ @ 20 °C'
        self.assertIn(('CONSISTENCY', 'BOUND_NOT_USED'), self.codes(self.run_check(cs=cs)))

    def test_an_undecided_conclusion_names_its_failure_path(self):
        cs = conclusions(); del self.c(cs, 'Q-ESR')['failure_path']
        self.assertIn(('CONSISTENCY', 'NO_FAILURE_PATH'), self.codes(self.run_check(cs=cs)))
        cs = conclusions(); self.c(cs, 'Q-ESR')['failure_path']['mechanism'] = ' '
        self.assertIn(('CONSISTENCY', 'NO_FAILURE_PATH'), self.codes(self.run_check(cs=cs)))
        qs = questions(); next(q for q in qs['questions'] if q['id'] == 'Q-ESR')['conditions']['states'] = ['RUN', 'OFF']
        cs = conclusions(); self.c(cs, 'Q-ESR')['failure_path']['state'] = 'SLEEP'
        self.assertIn(('CONSISTENCY', 'NO_FAILURE_PATH'), self.codes(self.run_check(qs=qs, cs=cs)))
        self.c(cs, 'Q-ESR')['failure_path']['state'] = 'RUN'
        self.assertTrue(self.run_check(qs=qs, cs=cs)['valid'])

    def test_procurement_is_a_constraint_not_an_open_question(self):
        cs = conclusions(); self.c(cs, 'Q-ESR')['missing']['from'] = 'PROCUREMENT'
        self.assertIn(('STRICTNESS', 'UNDECIDED_ON_PROCUREMENT'), self.codes(self.run_check(cs=cs)))
        cs = conclusions(); c = self.c(cs, 'Q-LED')
        c['basis'] = {'kind': 'CONSTRAINT', 'refs': ['R3'], 'requires': 'R3 额定功率 ≥ 0.1 W', 'clause': 'K-LED'}
        out = self.run_check(cs=cs)
        self.assertTrue(out['valid'], out['errors'])
        self.assertEqual(out['summary']['constraints'],
                         [{'question': 'Q-LED', 'refs': ['R3'], 'requires': 'R3 额定功率 ≥ 0.1 W'}])
        c['basis']['refs'] = ['R9']
        self.assertIn(('TRACE', 'UNKNOWN_REF'), self.codes(self.run_check(cs=cs)))
        c['basis'].update(refs=['R3'], requires='')
        self.assertIn(('TRACE', 'CONSTRAINT_INCOMPLETE'), self.codes(self.run_check(cs=cs)))
        c['basis']['requires'] = 'x'; c['outcome'] = 'FAIL'; c['fix'] = {'change': 'y', 'readiness': 'READY'}
        c['severity'] = {'level': 'P3', 'class': 'OPTIMIZATION', 'consequence': 'z'}
        self.assertIn(('CONSISTENCY', 'FAIL_WITHOUT_BASIS'), self.codes(self.run_check(cs=cs)))

    def recommended(self, clause='K-C5', deviations=()):
        return {'kind': 'RECOMMENDED', 'clause': clause, 'deviations': list(deviations),
                'facts': [{'ref': 'C5', 'ref_value_is': '100nF/50V', 'means': '按推荐值'}]}

    def test_a_recommended_configuration_without_deviation_passes(self):
        cs = conclusions(); e = self.c(cs, 'Q-ESR')
        for k in ('missing', 'searched', 'failure_path', 'severity'):
            e.pop(k)
        e.update(outcome='PASS', basis=self.recommended())
        out = self.run_check(cs=cs)
        self.assertTrue(out['valid'], out['errors'])
        self.assertEqual(out['summary']['facts_checked'], 4)
        e['basis'] = self.recommended(deviations=['C5 换成 47 nF'])
        self.assertIn(('CONSISTENCY', 'RECOMMENDED_WITH_DEVIATION'), self.codes(self.run_check(cs=cs)))
        e['basis'] = self.recommended(clause='K-ASSUME')
        self.assertIn(('STRICTNESS', 'RECOMMENDED_NOT_VENDOR'), self.codes(self.run_check(cs=cs)))
        e['basis'] = dict(self.recommended(), facts=[{'ref': 'C5', 'ref_value_is': '1uF', 'means': 'x'}])
        self.assertIn(('TRACE', 'FACT_FALSE'), self.codes(self.run_check(cs=cs)))
        cs = conclusions(); e = self.c(cs, 'Q-ESR'); e.pop('searched'); e['basis'] = self.recommended()
        self.assertIn(('STRICTNESS', 'ALREADY_RECOMMENDED'), self.codes(self.run_check(cs=cs)))

    def test_one_gap_is_counted_once(self):
        cs = conclusions(); e = self.c(cs, 'Q-ESR'); v = self.c(cs, 'Q-VF')
        e['missing']['what'] = '  ' + v['missing']['what'].replace(' ', '  ')
        self.assertIn(('STRICTNESS', 'DUPLICATE_GAP'), self.codes(self.run_check(cs=cs)))
        for k in ('searched', 'severity'):
            e.pop(k)
        e['missing'] = {'same_as': 'Q-VF'}
        out = self.run_check(cs=cs)
        self.assertTrue(out['valid'], out['errors'])
        self.assertEqual(out['summary']['gaps'], 1)
        self.assertEqual(out['summary']['outcomes']['UNDECIDED'], 2)
        e['missing'] = {'same_as': 'Q-LED'}
        self.assertIn(('CONSISTENCY', 'MISSING_SAME_AS_UNKNOWN'), self.codes(self.run_check(cs=cs)))

    def test_a_shared_gap_still_names_its_own_failure_path(self):
        cs = conclusions(); e = self.c(cs, 'Q-ESR')
        for k in ('searched', 'severity', 'failure_path'):
            e.pop(k)
        e['missing'] = {'same_as': 'Q-VF'}
        self.assertIn(('CONSISTENCY', 'NO_FAILURE_PATH'), self.codes(self.run_check(cs=cs)))


class StateSplitTests(Fixture):
    """A question over several states may be answered by one conclusion, or by conclusions that each take some of its
    states when the conclusions differ; together they cover every state once."""

    def gate_over_states(self):
        qs = questions()
        next(q for q in qs['questions'] if q['id'] == 'Q-GATE')['conditions']['states'] = ['RESET', 'RUN']
        return qs

    def split(self, run_states=('RUN',), reset_states=('RESET',)):
        cs = conclusions()
        reset = next(c for c in cs if c['question'] == 'Q-GATE')
        reset['states'] = list(reset_states)
        run = {'question': 'Q-GATE', 'states': list(run_states), 'outcome': 'PASS', 'basis': {
            'kind': 'FACT', 'clauses': ['K-PINS'], 'facts': [{'node': 'U2.1', 'net_is': 'V5', 'means': '运行时驱动保持低'}]}}
        return cs + [run]

    def test_one_conclusion_still_answers_every_state(self):
        self.assertTrue(self.run_check(qs=self.gate_over_states())['valid'])

    def test_conclusions_split_by_state_when_conclusions_differ(self):
        out = self.run_check(qs=self.gate_over_states(), cs=self.split())
        self.assertTrue(out['valid'], out['errors'])
        self.assertEqual(out['summary']['outcomes'], {'PASS': 4, 'FAIL': 1, 'UNDECIDED': 2})
        self.assertEqual(out['summary']['defects'], 1)

    def test_a_state_answered_twice_is_a_duplicate(self):
        out = self.run_check(qs=self.gate_over_states(), cs=self.split(run_states=('RUN', 'RESET')))
        self.assertIn(('COVERAGE', 'DUPLICATE_CONCLUSION'), self.codes(out))

    def test_a_state_no_conclusion_takes_is_unanswered(self):
        cs = [c for c in self.split() if c.get('states') != ['RUN']]
        out = self.run_check(qs=self.gate_over_states(), cs=cs)
        self.assertIn(('COVERAGE', 'UNANSWERED'), self.codes(out))

    def test_a_state_the_question_does_not_have(self):
        out = self.run_check(qs=self.gate_over_states(), cs=self.split(run_states=('IDLE',)))
        self.assertIn(('COVERAGE', 'UNKNOWN_STATE'), self.codes(out))
        cs = conclusions(); cs[0]['states'] = ['RUN']
        self.assertIn(('COVERAGE', 'UNKNOWN_STATE'), self.codes(self.run_check(cs=cs)))

    def test_a_suspicion_is_answered_once_per_question(self):
        out = self.run_check(qs=self.gate_over_states(), cs=self.split())
        self.assertNotIn(('COVERAGE', 'SUSPECT_UNANSWERED'), self.codes(out))
        cs = self.split()
        fail = next(c for c in cs if c['question'] == 'Q-GATE' and c['outcome'] == 'FAIL')
        fail.update(outcome='PASS'); fail.pop('fix'); fail.pop('severity')
        out = self.run_check(qs=self.gate_over_states(), cs=cs)
        self.assertEqual(self.codes(out).count(('COVERAGE', 'SUSPECT_UNANSWERED')), 1)


class UnitTests(Fixture):
    """Inputs are taken to SI by their units, the result back to the criterion's unit; the expression's
    dimension must be the criterion's."""

    def led(self, cs):
        return next(c for c in cs if c['question'] == 'Q-LED')

    def test_units_parse_to_scale_and_dimension(self):
        self.assertEqual(cc.parse_unit('kΩ'), (1e3, cc.dims('Ω')))
        self.assertEqual(cc.parse_unit('pF'), (1e-12, cc.dims('F')))
        self.assertEqual(cc.parse_unit('µs'), (1e-6, cc.dims('s')))
        self.assertEqual(cc.parse_unit(''), (1.0, cc.dims('')))
        self.assertIsNone(cc.parse_unit('furlong'))

    def test_dimension_of_an_expression(self):
        d = {'r': cc.dims('Ω'), 'c': cc.dims('F'), 'v': cc.dims('V')}
        self.assertEqual(cc.dimension('2.2 * r * c', d), cc.dims('s'))
        self.assertEqual(cc.dimension('v / r', d), cc.dims('A'))
        self.assertEqual(cc.dimension('v ** 2 / r', d), cc.dims('W'))
        self.assertEqual(cc.dimension('max(0, v - v) / r', d), cc.dims('A'))   # a literal 0 takes any dimension
        for bad in ('v - r', 'max(v, r)', 'sqrt(v)', 'v ** r'):
            with self.assertRaises(ValueError, msg=bad):
                cc.dimension(bad, d)

    def test_prefixes_are_resolved_not_trusted(self):
        cs = conclusions(); b = self.led(cs)['basis']   # (V − V) / kΩ is mA: 2.65…3.45 mA
        b['criterion'].update(unit='A', limit=0.002)
        self.assertIn(('TRACE', 'RECOMPUTE_MISMATCH'), self.codes(self.run_check(cs=cs)))
        b['result'] = {'min': 0.00265, 'max': 0.00345}
        self.assertTrue(self.run_check(cs=cs)['valid'], self.run_check(cs=cs)['errors'])

    def test_the_result_has_the_criterion_dimension(self):
        cs = conclusions(); self.led(cs)['basis']['criterion']['unit'] = 'mV'
        self.assertIn(('TRACE', 'DIMENSION_MISMATCH'), self.codes(self.run_check(cs=cs)))
        cs = conclusions(); self.led(cs)['basis']['calc'] = '(v5 - vf) * r'
        self.assertIn(('TRACE', 'DIMENSION_MISMATCH'), self.codes(self.run_check(cs=cs)))
        cs = conclusions(); self.led(cs)['basis']['calc'] = 'v5 - r'
        self.assertIn(('TRACE', 'DIMENSION_MISMATCH'), self.codes(self.run_check(cs=cs)))

    def test_an_unknown_unit_is_refused(self):
        cs = conclusions(); self.led(cs)['basis']['inputs']['vf']['unit'] = 'volts'
        self.assertIn(('TRACE', 'UNIT_UNKNOWN'), self.codes(self.run_check(cs=cs)))


class MonotonicTests(Fixture):
    """Corners give the range only for an expression monotone in each input; points inside the ranges are
    sampled and a value outside the corner range is refused."""

    def test_a_turning_expression_is_refused(self):
        cs = conclusions(); c = next(c for c in cs if c['question'] == 'Q-LED')
        c['basis'] = {'kind': 'NUMERIC', 'calc': 'x * (1 - x)',
                      'inputs': {'x': {'min': 0, 'max': 1, 'unit': '', 'from': {'clause': 'K-LED'}}},
                      'result': {'min': 0, 'max': 0},
                      'criterion': {'limit': 0.3, 'unit': '', 'direction': 'value_below_limit', 'clause': 'K-LED'}}
        self.assertIn(('TRACE', 'NON_MONOTONIC'), self.codes(self.run_check(cs=cs)))

    def test_monotone_expressions_pass_the_sampling(self):
        out = self.run_check()
        self.assertNotIn(('TRACE', 'NON_MONOTONIC'), self.codes(out))


class ExpressionTests(unittest.TestCase):
    def test_arithmetic_and_whitelisted_functions(self):
        self.assertAlmostEqual(cc.evaluate('max(a, b) * sqrt(c) - abs(-d) ** 2', {'a': 1, 'b': 2, 'c': 9, 'd': 1}), 5)

    def test_anything_else_is_refused(self):
        for expr in ('__import__("os")', 'a.real', 'a if a else b', '[a]', 'open("x")', 'zz + 1', 'max(a, key=b)'):
            with self.assertRaises(ValueError, msg=expr):
                cc.evaluate(expr, {'a': 1, 'b': 2})


class CliTests(Fixture):
    def test_exit_codes_and_output(self):
        files = {'questions': questions(), 'clauses': clauses(), 'conclusions': conclusions(), 'db': db()}
        for name, data in files.items():
            (self.root / (name + '.json')).write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        args = [str(self.root / n) for n in ('questions.json', 'clauses.json', 'conclusions.json')]
        out = self.root / 'out.json'
        self.assertEqual(cc.main(args + ['--db', str(self.root / 'db.json'), '-o', str(out)]), 0)
        self.assertTrue(json.loads(out.read_text(encoding='utf-8'))['valid'])
        bad = conclusions()[1:]
        (self.root / 'conclusions.json').write_text(json.dumps(bad), encoding='utf-8')
        self.assertEqual(cc.main(args + ['--db', str(self.root / 'db.json'), '-o', str(out)]), 1)
        (self.root / 'conclusions.json').write_text('{not json', encoding='utf-8')
        self.assertEqual(cc.main(args + ['--db', str(self.root / 'db.json'), '-o', str(out)]), 2)


if __name__ == '__main__':
    unittest.main()

"""Questions from a review plan: one per (subject, concern), states merged, every applicable row traced once."""
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import plan_to_questions as ptq

BOARD_PLAN = (HERE.parents[2] / 'evals/training/runs/2026-10-20-29b9856/hot'
              / 'olimex-esp32-poe-iso-revN-revN1.before/plan.json')


def row(cid, obj, applicability='APPLICABLE', **extra):
    return dict({'id': cid, 'rule': cid.split('.')[0], 'object': obj, 'applicability': applicability,
                 'criterion': 'criterion of ' + cid.split('.')[0]}, **extra)


def synthetic_plan():
    checks = []
    for group, ref in (('DECAP-A', 'U1'), ('DECAP-B', 'U2')):
        for rule in ('PWR-C09', 'PWR-C10', 'PWR-D02', 'PWR-T03'):
            checks.append(row('%s.%s.%s' % (rule, group, ref),
                              {'ref': ref, 'nodes': [ref + '.1'], 'nets': ['V3'], 'decoupling_group': group,
                               'state': 'UNSPECIFIED'},
                              inventory_gaps=['datasheet-requirement:capacitance'] if group == 'DECAP-B' else None))
    for rule in ('PWR-C02', 'PWR-C03'):
        for state in ('STARTUP', 'RUN', 'LATCH'):
            checks.append(row('%s.BIAS-%s.Q1' % (rule, state),
                              {'circuit': 'BIAS', 'ref': 'Q1', 'refs': ['Q1', 'D2'], 'nets': ['AUX', 'VCC'], 'state': state},
                              function_id='FN-BIAS', question='偏置能否保持 VCC（%s）' % state))
    link = {'refs': ['U5', 'U6'], 'nets': ['TX', 'RX'], 'ref': 'U5'}
    checks.append(row('SIG-C07.LINK-A-RUN.U5', dict(link, circuit='LINK-A', state='RUN')))
    checks.append(row('SIG-C07.LINK-B-RUN.U5', dict(link, circuit='LINK-B', state='RUN')))
    checks.append(row('SIG-C07.LINK-B-RESET.U5', dict(link, circuit='LINK-B', state='RESET')))
    checks.append(row('SIG-C07.LINK-C.U7', {'circuit': 'LINK-C', 'ref': 'U7', 'refs': ['U7'], 'nets': ['TX']}))
    checks.append(row('DEV-D02.U3', {'ref': 'U3'}))
    checks.append(row('DEV-D05.U3', {'ref': 'U3'}))
    checks.append(row('DEV-D01.U3', {'ref': 'U3'}))
    checks.append(row('SIG-E02.RD', {'net': '/RD+', 'diff_pair': 'RD'}, applicability='UNDETERMINED'))
    checks.append(row('DRV-A01.L1', {'ref': 'L1', 'lint_detail': 'L1 开关节点未见续流或钳位'}, lint_kind='A'))
    checks.append(row('SIG-C07.I2C-R1.SDA', {'net': '/SDA', 'i2c_region': 'I2C-R1', 'state': 'UNSPECIFIED'}))
    checks.append(row('DOC-D01.BOARD', {'board': 'BOARD'}, applicability='NA'))
    plan = {'checks': checks,
            'i2c_topology': {'states': [{'id': 'UNSPECIFIED', 'regions': [
                {'id': 'I2C-R1', 'gaps': ['pin-role-or-model:U9', 'external-port:J1']}]}]}}
    return plan


class QuestionTests(unittest.TestCase):
    def setUp(self):
        self.out = ptq.build(synthetic_plan())
        self.by_rules = {tuple(q['rules']): q for q in self.out['questions']}

    def test_every_applicable_row_is_traced_by_exactly_one_question(self):
        traced = [cid for q in self.out['questions'] for cid in q['check_ids']]
        applicable = [c['id'] for c in synthetic_plan()['checks'] if c['applicability'] != 'NA']
        self.assertEqual(sorted(traced), sorted(applicable))
        self.assertEqual(len(traced), len(set(traced)))
        self.assertNotIn('DOC-D01.BOARD', traced)

    def test_decoupling_rules_on_one_group_are_one_question(self):
        decap = [q for q in self.out['questions'] if q['concern'] == 'DECOUPLING']
        self.assertEqual(len(decap), 2)
        self.assertEqual(decap[0]['rules'], ['PWR-C09', 'PWR-C10', 'PWR-D02', 'PWR-T03'])
        self.assertEqual(decap[0]['subject']['refs'], ['U1'])
        self.assertTrue(decap[0]['ask'].startswith('U1 V3：去耦容量'), decap[0]['ask'])

    def test_states_of_a_circuit_merge_into_one_question_per_rule(self):
        bias = [q for q in self.out['questions'] if q['subject'].get('circuit') == 'BIAS']
        self.assertEqual([q['rules'] for q in bias], [['PWR-C02'], ['PWR-C03']])
        self.assertEqual(bias[0]['conditions']['states'], ['LATCH', 'RUN', 'STARTUP'])
        self.assertEqual(len(bias[0]['check_ids']), 3)
        self.assertIn('偏置能否保持 VCC', bias[0]['ask'])

    def test_one_rule_on_the_same_parts_and_nets_is_one_question_across_circuits(self):
        links = [q for q in self.out['questions'] if q['subject']['name'].startswith('LINK')]
        self.assertEqual([q['subject']['circuits'] for q in links], [['LINK-A', 'LINK-B'], ['LINK-C']])
        self.assertEqual(links[0]['subject']['name'], 'LINK-A+LINK-B')
        self.assertEqual(links[0]['check_ids'], ['SIG-C07.LINK-A-RUN.U5', 'SIG-C07.LINK-B-RUN.U5', 'SIG-C07.LINK-B-RESET.U5'])
        self.assertEqual(links[0]['conditions']['states'], ['RESET', 'RUN'])

    def test_pin_rules_of_one_device_are_one_question_identity_stays_apart(self):
        u3 = [q['rules'] for q in self.out['questions'] if q['subject'].get('refs') == ['U3']]
        self.assertEqual(sorted(u3), [['DEV-D01'], ['DEV-D02', 'DEV-D05']])

    def test_tool_observations_reach_the_question(self):
        decap_b = next(q for q in self.out['questions'] if q['concern'] == 'DECOUPLING' and q['subject']['refs'] == ['U2'])
        self.assertEqual([(o['kind'], o['says'], o['input']) for o in decap_b['observations']],
                         [('MISSING_INPUT', 'datasheet-requirement:capacitance', True)])
        i2c = self.by_rules[('SIG-C07',)]
        self.assertEqual(sorted(o['says'] for o in i2c['observations']), ['external-port:J1', 'pin-role-or-model:U9'])
        self.assertFalse(any(o['input'] for o in i2c['observations']))
        lint = self.by_rules[('DRV-A01',)]
        self.assertEqual(lint['observations'][0]['kind'], 'SUSPECT')
        self.assertEqual([o['id'] for o in decap_b['observations']], ['O-1'])

    def test_undetermined_rows_ask_for_applicability_first(self):
        self.assertTrue(self.by_rules[('SIG-E02',)]['undetermined'])
        self.assertFalse(self.by_rules[('SIG-C07',)]['undetermined'])

    def test_ids_are_unique_and_stable(self):
        ids = [q['id'] for q in self.out['questions']]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids, [q['id'] for q in ptq.build(synthetic_plan())['questions']])
        self.assertEqual(self.out['summary']['rows'], 24)
        self.assertEqual(self.out['summary']['questions'], len(ids))
        self.assertEqual(self.out['summary']['inputs_to_supply'], ['datasheet-requirement:capacitance'])


class BoardPlanTests(unittest.TestCase):
    @unittest.skipUnless(BOARD_PLAN.exists(), 'prototype board plan not present')
    def test_the_prototype_board_plan_converts_with_full_trace(self):
        plan = json.loads(BOARD_PLAN.read_text(encoding='utf-8'))
        out = ptq.build(plan)
        traced = [cid for q in out['questions'] for cid in q['check_ids']]
        applicable = [c['id'] for c in plan['checks'] if c.get('applicability') != 'NA']
        self.assertEqual(sorted(traced), sorted(applicable))
        self.assertLess(len(out['questions']), len(applicable))


if __name__ == '__main__':
    unittest.main()

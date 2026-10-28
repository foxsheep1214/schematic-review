"""The stress spec (2026-10-27, user: 将共用规范R6和ASG统一到现在的“应力”规范下来，制定单独的应力规范; 统一到余量审核规则上来).

The derating level comes from a requirement or an answered clarification and rides on the plan. A margin that names a
derating rule is checked at that level: within the rating but over the derated value it carries the stress risk, within
the derated value it carries none; the rule must fit the part. A stress margin of a covered kind naming no rule is a
hint, never a refusal. All values are synthetic.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import derating
from review_functions import derating_errors
from review_quality import screen_quality

INTENT = {'requirements': [{'id': 'REQ-REL-01', 'text': '商用电源，II 级降额'}],
          'clarifications': [{'id': 'CL-DERATE', 'answer': {'decision': 'ADOPTED_PROPOSAL'}},
                             {'id': 'CL-OPEN', 'answer': {'decision': 'DEFERRED'}}]}
DB = {'parts': {'C1': {'value': '10u'}, 'Q1': {'value': 'MOS', 'prim': 'Device:Q_NMOS_GDS'}}, 'pin2net': {}, 'nets': {}}
RATING = {'id': 'c-rated', 'kind': 'NUMERIC_LIMIT', 'refs': ['C1'], 'limit': {'max': 50, 'unit': 'V'}}


def margin(value, rule='CAP-MLCC-CHIP-V', **risk):
    basis = {'kind': 'GUARANTEED_BOUND', 'limit': 'c-rated', 'method': 'G1'}
    if rule:
        basis['derating_rule'] = rule
    if risk:
        basis['risk'] = risk
    return {'value': value, 'unit': 'V', 'against': 'C1 50 V 额定', 'aspect': '器件应力与降额', 'basis': basis}


def fn(*margins):
    return {'id': 'FN-X', 'conditions': [dict(RATING)], 'calculation': {'result': 'r', 'margin': list(margins)}}


def gate(level, *margins):
    return derating_errors({'derating': {'level': level, 'source': 'req:REQ-REL-01'}} if level else {}, [fn(*margins)], DB)


class LevelTests(unittest.TestCase):
    def test_the_level_names_a_requirement_or_an_answered_clarification(self):
        for source in ('req:REQ-REL-01', 'clarification:CL-DERATE'):
            self.assertEqual(derating.intent_errors(dict(INTENT, derating={'level': 'II', 'source': source})), [], source)
        for bad in ({'level': 'IV', 'source': 'req:REQ-REL-01'}, {'level': 'II', 'source': 'req:REQ-NONE'},
                    {'level': 'II', 'source': 'clarification:CL-OPEN'}, {'level': 'II', 'source': 'user'}, {'level': 'II'}):
            self.assertTrue(derating.intent_errors(dict(INTENT, derating=bad)), bad)
        self.assertEqual(derating.intent_errors(INTENT), [])   # optional until a margin names a rule

    def test_the_plan_carries_the_level(self):
        from plan_review import build_review_plan, validate_intent
        from test_optocoupler import opto_board
        from electrical_fixtures import bound_intent
        db = opto_board()
        intent = dict(bound_intent(db, {}), derating={'level': 'II', 'source': 'req:REQ-REL-01'})
        self.assertTrue([e for e in validate_intent(intent, db) if 'derating.source' in e])   # no such requirement here
        self.assertEqual(build_review_plan(db, intent=intent)['derating'], {'level': 'II', 'source': 'req:REQ-REL-01'})
        self.assertNotIn('derating', build_review_plan(db, intent=bound_intent(db, {})))


class MarginTests(unittest.TestCase):
    # CAP-MLCC-CHIP-V: I 0.8, II 0.9, III 0.95 of the rating; 50 V rating, so 40 / 45 / 47.5 V
    def test_over_the_derated_value_within_the_rating_is_a_stress_risk(self):
        self.assertEqual(gate('II', margin(10)), [])                              # 40 V ≤ 45 V
        [e] = gate('I', margin(8))                                                # 42 V > 40 V, no risk written
        self.assertIn('write basis.risk{types: [STRESS]', e)
        self.assertEqual(gate('I', margin(8, types=['STRESS'], corner='c', improvement='i')), [])
        [e] = gate('III', margin(8, types=['STRESS'], corner='c', improvement='i'))   # 42 V ≤ 47.5 V
        self.assertIn('no stress risk', e)
        self.assertEqual(gate('I', margin(-2)), [])                               # over the rating: an ordinary failing margin

    def test_a_negative_rating_is_compared_by_magnitude(self):
        # R8 (Codex review 2026-10-27): GaN turn-off gate −10 V at 50 % allows −5 V; −8 V is short of the derating,
        # although −8 ≤ −5 read with its sign. The margin is the distance to the −10 V limit: 2 V.
        gate_min = {'id': 'c-rated', 'kind': 'NUMERIC_LIMIT', 'refs': ['Q1'], 'limit': {'min': -10, 'unit': 'V'}}
        kinds = lambda refs: ['mosfet']
        m = dict(margin(2, rule='GAN-VGS-OFF'), against='Q1 −10 V 关断负压额定')
        [e] = derating.margin_errors('FN-X', m, {'c-rated': gate_min}, 'II', kinds)
        self.assertIn('stress 8 V is within the rating 10 but over the level II derated value 5', e)
        m['basis']['risk'] = {'types': ['STRESS'], 'corner': 'c', 'improvement': 'i'}
        self.assertEqual(derating.margin_errors('FN-X', m, {'c-rated': gate_min}, 'II', kinds), [])
        m = dict(margin(6, rule='GAN-VGS-OFF'))   # −4 V: within the 5 V allowed magnitude
        self.assertEqual(derating.margin_errors('FN-X', m, {'c-rated': gate_min}, 'II', kinds), [])

    def test_the_rule_exists_fits_the_part_and_needs_a_level(self):
        self.assertIn('not in references/derating-rules.json', gate('II', margin(10, rule='NO-SUCH'))[0])
        self.assertIn('is for mosfet', gate('II', margin(10, rule='MOS-VDS-S'))[0])
        self.assertIn('no derating level', gate(None, margin(10))[0])
        self.assertEqual(gate(None, margin(10, rule=None)), [])

    def test_a_stress_margin_naming_no_rule_is_a_hint_only(self):
        plan = {'checks': [{'id': 'A.1', 'rule': 'A'}]}
        report = {'checks': [{'id': 'A.1', 'review_result': 'PASS', 'rationale': 'ok'}], 'functions': [fn(margin(10, rule=None))]}
        hints = [c for c in screen_quality(plan, report, DB)['candidates'] if c['code'] == 'DERATING_RULE_AVAILABLE']
        self.assertEqual([h['kinds'] for h in hints], [['capacitor']])
        report['functions'] = [fn(margin(10))]
        self.assertFalse([c for c in screen_quality(plan, report, DB)['candidates'] if c['code'] == 'DERATING_RULE_AVAILABLE'])


if __name__ == '__main__':
    unittest.main()

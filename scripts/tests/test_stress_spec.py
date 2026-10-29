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



class RuleFitTests(unittest.TestCase):
    """SR-FIX-05 (Codex review 2026-10-27): a VGS rule on a VDS margin, or a GaN rule on a silicon part, was accepted."""

    def q1(self, rule, says='Q1 VDS max 100 V', value='Si MOSFET', unit='V'):
        db = {'parts': {'Q1': {'part': 'IRF540N', 'value': value, 'prim': 'Device:Q_NMOS_GDS'}}, 'pin2net': {}, 'nets': {}}
        rated = {'id': 'c-rated', 'kind': 'NUMERIC_LIMIT', 'refs': ['Q1'], 'says': says, 'limit': {'max': 100, 'unit': unit}}
        m = {'value': 50, 'unit': unit, 'against': 'Q1 额定', 'aspect': '器件应力与降额',
             'basis': {'kind': 'GUARANTEED_BOUND', 'limit': 'c-rated', 'method': 'G1', 'derating_rule': rule}}
        f = {'id': 'FN-Q1', 'conditions': [rated], 'calculation': {'result': 'r', 'margin': [m]}}
        return derating_errors({'derating': {'level': 'II', 'source': 'req:REQ-REL-01'}}, [f], db), f, db

    def test_the_right_rule_still_takes_the_stress_risk_only(self):
        self.assertEqual(self.q1('MOS-VDS-S')[0], [])

    def test_a_rule_for_another_terminal_pair_is_refused(self):
        self.assertTrue(any('is for VGS' in e for e in self.q1('MOS-VGS-T')[0]))

    def test_a_rule_for_another_quantity_is_refused(self):
        self.assertTrue(any('rates 漏极电流' in e for e in self.q1('MOS-IDM')[0]))

    def test_a_rule_for_another_technology_is_refused_when_the_identity_names_one(self):
        found = self.q1('GAN-VGS-ON', says='Q1 VGS max 100 V')[0]
        self.assertTrue(any('is for gan parts' in e for e in found), found)
        self.assertEqual(self.q1('GAN-VGS-ON', says='Q1 VGS max 100 V', value='GaN HEMT')[0], [])

    def test_a_silent_identity_and_a_transient_wording_are_hints(self):
        _, f, db = self.q1('GAN-VGS-ON', says='Q1 VGS max 100 V', value='MOS')
        identity = lambda refs: ' '.join(str(db['parts'][r].get(k) or '') for r in refs for k in ('part', 'value'))
        conditions = {c['id']: c for c in f['conditions']}
        self.assertEqual(self.q1('GAN-VGS-ON', says='Q1 VGS max 100 V', value='MOS')[0], [])
        hints = derating.fit_hints(f['calculation']['margin'][0], conditions, identity)
        self.assertTrue(any('does not say which technology' in h for h in hints), hints)
        _, f, _ = self.q1('MOS-VDS-S', says='Q1 VDS 关断尖峰 max 100 V')
        hints = derating.fit_hints(f['calculation']['margin'][0], {c['id']: c for c in f['conditions']}, identity)
        self.assertTrue(any('reads as a transient' in h for h in hints), hints)


if __name__ == '__main__':
    unittest.main()


class ImpliedRuleTests(unittest.TestCase):
    """2026-10-28 (user: 按推荐都做): a margin on a guaranteed rating naming no rule is checked by the gate itself when
    exactly one ratio rule fits the part and the margin's dimension. R8: VBUS 5 A on a 5 A connector, zero margin."""

    DB = {'parts': {'J1': {'value': 'USB-C', 'prim': 'Connector:USB_C_Receptacle'}}, 'pin2net': {}, 'nets': {}}
    LIMIT = {'id': 'c-rated', 'kind': 'NUMERIC_LIMIT', 'refs': ['J1'], 'limit': {'max': 5, 'unit': 'A'}}

    def risks(self, value, level='III', **basis):
        import review_functions
        m = {'value': value, 'unit': 'A', 'against': 'VBUS 接点额定 5 A', 'aspect': '连接器载流',
             'basis': dict({'kind': 'GUARANTEED_BOUND', 'comparison': 'GE', 'limit': 'c-rated', 'method': 'G1'}, **basis)}
        function = {'id': 'FN-J', 'conditions': [dict(self.LIMIT)], 'calculation': {'result': 'r', 'margin': [m]}}
        checks = {'X.J1': {'function_id': 'FN-J', 'aspect': '连接器载流', 'review_result': 'PASS'}}
        plan = {'derating': {'level': level, 'source': 'req:R'}} if level else {}
        return review_functions.implied_stress_risks({}, checks, [function], plan, self.DB)

    def test_a_zero_margin_on_the_rating_is_a_stress_risk_at_the_level(self):
        [entry] = self.risks(0)
        self.assertEqual((entry['source'], entry['types'], entry['derating_rule']), ('STRESS', ['STRESS'], 'USB-I'))
        self.assertIn('4.5', entry['corner'])                            # a USB receptacle: 90 % at level III

    def test_a_connector_its_identity_does_not_name_takes_the_other_connectors_rule(self):
        self.DB = {'parts': {'J1': {'value': 'TERMINAL 2P', 'prim': 'Connector:Conn_01x02'}}, 'pin2net': {}, 'nets': {}}
        [entry] = self.risks(0.5)                                        # 4.5 A > 4.25 A
        self.assertEqual(entry['derating_rule'], 'CONN-I')

    def test_within_the_derated_value_or_without_a_level_or_naming_a_rule_it_is_not(self):
        self.assertEqual(self.risks(0.5), [])                            # 4.5 A ≤ 4.5 A
        self.assertEqual(self.risks(0, level=None), [])
        self.assertEqual(self.risks(0, derating_rule='CONN-I'), [])      # a named rule is checked by margin_errors
        self.assertEqual(self.risks(0, method='G7'), [])                 # only a guaranteed rating comparison


class BoundRecordedAsUnboundableTests(unittest.TestCase):
    """R8 (2026-10-28): a datasheet leakage limit written as typical, then the gap marked 公开资料定不出界限."""

    def hints(self, says):
        cond = {'id': 'c-leak', 'kind': 'TYPICAL_REFERENCE', 'refs': ['C1'], 'says': says}
        item = {'key': 'LEAK', 'kind': 'VENDOR_DATUM', 'checked': ['c-leak'],
                'worst_case': {'not_boundable_reason': '按该上界约 396 mW，证明不了 150 mW'}}
        report = {'checks': [{'id': 'A.1', 'review_result': 'INSUFFICIENT', 'rationale': 'x'}],
                  'functions': [{'id': 'FN-X', 'conditions': [cond], 'open': [item]}]}
        return [c for c in screen_quality({'checks': [{'id': 'A.1', 'rule': 'A'}]}, report, DB)['candidates']
                if c['code'] == 'BOUND_RECORDED_AS_UNBOUNDABLE']

    def test_a_limit_written_as_typical_behind_an_unboundable_item_is_flagged(self):
        self.assertEqual([h['open'] for h in self.hints('泄漏上界 I ≤ 3√(CV) µA')], ['LEAK'])
        self.assertEqual(self.hints('漏电典型 20 µA'), [])

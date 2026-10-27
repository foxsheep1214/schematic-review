"""A row the reviewer adds is a rule gap (fixed requirements, step 7).

On the R5 bench one reviewer added 6 rows to the plan by hand and the other 16, one object in common: stress rows on
pins the tool did not reach, recalculations of design-report claims, requirement rows for requirements written as
tests. Each appeared in one record only and the next review would add others. A reviewer who thinks something is to be
checked that the plan does not ask now registers a rule gap in intent.rule_gaps: the object, the rule it is judged
under, the criterion, what rule or derivation the tool lacks and the basis. The planner writes it as a REVIEWER_ADDED
row, judged like any other, counted apart and left out of the pairing rate of two records; the gate lists the gaps
for the improvement ledger, where each becomes a rule the tool writes. A row the planner did not write is refused.
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import compare_reviews as cr
from plan_review import build_review_plan, validate_intent
from test_i2c_topology import pending_report
from test_revision_impact import database
from validate_review import validate_review


def gap(**changes):
    item = {'id': 'R1-SURGE', 'rule': 'DEV-C01', 'object': {'ref': 'R1'},
            'criterion': 'R1 承受启动浪涌的脉冲功率在手册脉冲负荷曲线以内',
            'missing': '启动通路串联电阻的脉冲负荷没有生成规则',
            'basis': 'synthetic requirement 2.1 startup inrush and resistor datasheet pulse-load curve'}
    item.update(changes)
    return item


def added(plan):
    return [c for c in plan['checks'] if c.get('origin') == 'REVIEWER_ADDED']


class IntentTests(unittest.TestCase):
    def errors(self, gaps, db=None):
        return [e for e in validate_intent({'schema_version': 5, 'rule_gaps': gaps}, db) if 'rule_gaps' in e]

    def test_a_gap_names_object_rule_criterion_what_is_missing_and_the_basis(self):
        self.assertEqual(self.errors([gap()], database()), [])
        for field in ('id', 'rule', 'object', 'criterion', 'missing', 'basis'):
            item = gap()
            item.pop(field)
            self.assertTrue(any(field in e for e in self.errors([item])), field)
        self.assertTrue(any('rule_gaps 必须' in e for e in self.errors({'R1': gap()})))

    def test_an_unknown_rule_a_requirement_row_a_repeated_id_and_an_unknown_part_are_refused(self):
        self.assertTrue(any('DEV-Z99' in e for e in self.errors([gap(rule='DEV-Z99')])))
        self.assertTrue(any('REQ-D01' in e and 'requirement_source' in e for e in self.errors([gap(rule='REQ-D01')])))
        self.assertTrue(any('重复' in e for e in self.errors([gap(), gap()])))
        self.assertTrue(any('R7' in e for e in self.errors([gap(object={'ref': 'R7'})], database())))
        self.assertTrue(any('R7' in e for e in self.errors([gap(object={'refs': ['R1', 'R7']})], database())))
        self.assertTrue(any('object' in e for e in self.errors([gap(object={})])))


class PlanTests(unittest.TestCase):
    def test_the_planner_writes_one_reviewer_added_row_per_gap_counted_apart(self):
        db = database()
        plain = build_review_plan(db)
        plan = build_review_plan(db, {'rule_gaps': [gap()]})
        rows = added(plan)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual((row['rule'], row['object'], row['criterion']), ('DEV-C01', {'ref': 'R1'}, gap()['criterion']))
        self.assertEqual(row['rule_gap'], {'id': 'R1-SURGE', 'missing': gap()['missing'], 'basis': gap()['basis']})
        self.assertIn('rule_gap:R1-SURGE', row['trigger'])
        self.assertEqual(plan['summary']['reviewer_added'], 1)
        self.assertEqual(plain['summary']['reviewer_added'], 0)
        self.assertEqual(sorted(c['id'] for c in plan['checks'] if c is not row), sorted(c['id'] for c in plain['checks']))

    def test_a_row_carried_from_a_previous_plan_must_be_a_rule_gap(self):
        db = database()
        cold = build_review_plan(db)
        hand = copy.deepcopy(next(c for c in cold['checks'] if c['rule'] == 'DEV-C01'))
        hand.update(id='DEV-C01.HAND', criterion='hand-written check')
        cold['checks'].append(hand)
        with self.assertRaisesRegex(ValueError, 'rule_gaps'):
            build_review_plan(db, previous_plan=cold)
        noted = build_review_plan(db, {'rule_gaps': [gap()]})
        again = build_review_plan(db, {'rule_gaps': [gap()]}, previous_plan=noted)
        self.assertEqual(len(added(again)), 1)


class GateTests(unittest.TestCase):
    def validate(self, plan, db):
        return validate_review(plan, pending_report(plan, db), db)

    def test_a_hand_added_row_is_refused_and_a_gap_row_is_listed_for_the_ledger(self):
        db = database()
        plan = build_review_plan(db, {'rule_gaps': [gap()]})
        result = self.validate(plan, db)
        self.assertEqual([e for e in result['errors'] if 'rule_gaps' in e], [])
        self.assertEqual(result['rule_gaps'], [{'check_id': added(plan)[0]['id'], 'rule': 'DEV-C01', 'id': 'R1-SURGE',
                                                'missing': gap()['missing'], 'basis': gap()['basis'],
                                                'result': 'INSUFFICIENT'}])
        hand = build_review_plan(db)
        row = copy.deepcopy(added(plan)[0])
        row.pop('origin')
        row.pop('rule_gap')
        hand['checks'].append(dict(row, id='DEV-C01.HAND'))
        result = self.validate(hand, db)
        self.assertTrue(any('DEV-C01.HAND' in e and 'rule_gaps' in e for e in result['errors']), result['errors'])


class ReportTests(unittest.TestCase):
    def test_the_report_lists_each_gap_for_the_sr_maintainers(self):
        from render_report import render
        gate = {'valid': True, 'release': 'NO_GO', 'blockers': [], 'rule_gaps': [
            {'check_id': 'DEV-C01.GAP-R1-SURGE.R1', 'rule': 'DEV-C01', 'id': 'R1-SURGE', 'missing': gap()['missing'],
             'basis': gap()['basis'], 'result': 'FAIL'}]}
        text = render({}, {'checks': []}, gate)
        section = text.split('## 对 SR 的反馈（设计者不用处理）')[1].split('### 审查员补加的检查（规则缺口）')[1]
        for piece in ('DEV-C01.GAP-R1-SURGE.R1', gap()['missing'], gap()['basis'], 'FAIL'):
            self.assertIn(piece, section)


class CompareTests(unittest.TestCase):
    def test_reviewer_added_rows_are_counted_apart_and_left_out_of_the_pairing_rate(self):
        db = database()
        plain = build_review_plan(db)
        plan = build_review_plan(db, {'rule_gaps': [gap()]})
        side = lambda p: {'where': 'x', 'plan': p, 'results': pending_report(p, db)}
        strict = cr.compare(side(plan), side(plain))['strict']
        self.assertEqual(strict['counts']['N_A'], strict['counts']['N_B'])
        self.assertEqual(strict['metrics']['alignment_coverage'], 1.0)
        self.assertEqual(strict['reviewer_added'], {'A': [added(plan)[0]['id']], 'B': []})
        self.assertIn('审查员补加（规则缺口，不计入配对）：A 1 项，B 0 项', cr.markdown(cr.compare(side(plan), side(plain))))


if __name__ == '__main__':
    unittest.main()

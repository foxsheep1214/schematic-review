"""Rows follow their function verdict (design §5): the bias example derives 15 rows, 2 open and 13 PASS."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import catalog
import derive_rows
import validate_review as vr
from test_review_functions import bias_function, aux_open, guaranteed, ASPECT
from test_validate_review import fixture, planned, E
from validate_review import fingerprint

RULES = catalog.circuit_type('POWER_CONVERTER').subjects   # PWR-C02/C03/C04/C05/C15
STATES = ('STARTUP', 'RUN', 'LATCH')


def bias_plan():
    """The validator fixture plus the 15 BIAS member rows and their frame; results hold only the function."""
    p, r, db = fixture()
    for item in p['checks']:   # bindings are all-or-nothing: the base rows get one too
        item['criterion'] = 'stipulated'
    for row in r['checks']:
        row['binding'] = {'object': {}, 'criterion': 'stipulated'}
    members = []
    for rule in RULES:
        for state in STATES:
            cid = '%s.BIAS-%s.Q2' % (rule, state)
            p['checks'].append(dict(planned(cid), object={'circuit': 'BIAS', 'ref': 'Q2', 'state': state},
                                    criterion=catalog.criterion(rule), function_id='FN-BIAS',
                                    aspect=catalog.title(rule), handoff={'required': False}))
            members.append({'check_id': cid, 'rule': rule, 'aspect': catalog.title(rule), 'state': state})
    p['functions'] = [{'id': 'FN-BIAS', 'circuit': 'BIAS', 'question': 'bias frame', 'members': members}]
    r['plan_digest'] = fingerprint(p)
    r['functions'] = [bias_function()]
    calc = r['functions'][0]['calculation']
    calc['margin'] = [dict(calc['margin'], aspect=ASPECT)] + other_margins()
    return p, r, db


def other_margins():
    """The aspects other than the bias voltage are engineering calculations too (1e): each has its own margin."""
    against = {'PWR-C03': 'Q2 ID 额定 0.5 A', 'PWR-C04': 'C3 保持时间需求 2 ms', 'PWR-C05': 'Q2 耗散额定 0.3 W',
               'PWR-C15': '源极跟随相位裕度需求 45°'}
    return [{'value': (0.1, 0.2, 0.3, 0.4)[i], 'unit': 'A' if rule == 'PWR-C03' else 'x', 'against': against[rule],
             'aspect': catalog.title(rule), 'states': list(STATES), 'basis': guaranteed()}
            for i, rule in enumerate(r for r in RULES if r != 'PWR-C02')]


def bias_rows(r):
    return {c['id']: c for c in r['checks'] if '.BIAS-' in c['id']}


OTHER_ROW = 'PWR-C02.OTHER-RUN.Q9'


def two_frames():
    """A second circuit frame with one row whose gap is the bias frame's open item (SR self-check 2.6): the item's
    decides names that row in check_ids, so the row points at it instead of a copy of the gap."""
    p, r, db = bias_plan()
    p['checks'].append(dict(planned(OTHER_ROW), object={'circuit': 'OTHER', 'ref': 'Q9', 'state': 'RUN'},
                            criterion=catalog.criterion('PWR-C02'), function_id='FN-OTHER',
                            aspect=catalog.title('PWR-C02'), handoff={'required': False}))
    p['functions'].append({'id': 'FN-OTHER', 'circuit': 'OTHER', 'question': 'other frame',
                           'members': [{'check_id': OTHER_ROW, 'rule': 'PWR-C02', 'aspect': catalog.title('PWR-C02'),
                                        'state': 'RUN'}]})
    other = copy.deepcopy(r['functions'][0])
    other.update(id='FN-OTHER', circuit='OTHER', open=[], verdict='PASS')   # its own items: none
    other['calculation']['result'] = 'VCC_min(OTHER) = 9.7 V'
    r['functions'].append(other)
    r['functions'][0]['open'][0]['decides'].append(
        {'aspect': ASPECT, 'states': ['RUN'], 'check_ids': [OTHER_ROW], 'via': {'condition': 'c3'},
         'rationale': 'OTHER 的 Q9 也由同一辅助绕组供电，最低峰值未定'})
    r['plan_digest'] = fingerprint(p)
    return p, r, db


class CrossFunctionTests(unittest.TestCase):
    def test_a_row_takes_another_functions_open_item_that_names_it(self):
        p, r, db = two_frames()
        r, summary, errors = derive_rows.derive(p, r)
        self.assertEqual(errors, [])
        row = next(c for c in r['checks'] if c['id'] == OTHER_ROW)
        self.assertEqual((row['review_result'], row['function_id'], row['open_ref']),
                         ('INSUFFICIENT', 'FN-OTHER', 'FN-BIAS/AUX-5V-MIN'))
        out = vr.validate_review(p, r, db)
        self.assertTrue(out['valid'], out['errors'])
        work = next(t for t in out['workflow']['work_items'] if t['id'] == 'W-AUX-5V-MIN')
        self.assertIn(OTHER_ROW, work['check_ids'])

    def test_an_item_that_does_not_name_the_row_is_not_taken(self):
        p, r, db = two_frames()
        unnamed = copy.deepcopy(r)
        unnamed['functions'][0]['open'][0]['decides'].pop()
        unnamed, _, _ = derive_rows.derive(p, unnamed)
        row = next((c for c in unnamed['checks'] if c['id'] == OTHER_ROW), {})
        self.assertNotEqual(row.get('open_ref'), 'FN-BIAS/AUX-5V-MIN')
        r, _, _ = derive_rows.derive(p, r)
        row = next(c for c in r['checks'] if c['id'] == OTHER_ROW)
        row.update(review_result='INSUFFICIENT', open_ref='FN-BIAS/AUX-5V-MIN')
        r['functions'][0]['open'][0]['decides'].pop()
        out = vr.validate_review(p, r, db)
        self.assertTrue(any(OTHER_ROW in e and 'check_ids' in e for e in out['errors']), out['errors'])


class DeriveTests(unittest.TestCase):
    def test_the_bias_example_derives_two_open_rows_and_thirteen_pass(self):
        p, r, db = bias_plan()
        r, summary, errors = derive_rows.derive(p, r)
        self.assertEqual(errors, [])
        self.assertEqual(summary, {'derived': 15, 'kept': 0, 'PASS': 13, 'FAIL': 0, 'INSUFFICIENT': 2, 'requirements': 0})
        rows = bias_rows(r)
        self.assertEqual(len(rows), 15)
        open_rows = {k for k, v in rows.items() if v['review_result'] == 'INSUFFICIENT'}
        self.assertEqual(open_rows, {'PWR-C02.BIAS-STARTUP.Q2', 'PWR-C02.BIAS-RUN.Q2'})
        self.assertEqual(rows['PWR-C02.BIAS-RUN.Q2']['open_ref'], 'FN-BIAS/AUX-5V-MIN')
        self.assertIn('开放项 AUX-5V-MIN', rows['PWR-C02.BIAS-RUN.Q2']['rationale'])
        latch = rows['PWR-C02.BIAS-LATCH.Q2']
        self.assertEqual(latch['rationale'], '见功能判定 FN-BIAS（%s，LATCH）：VCC_min = 9.6 V；余量 0.8V 对 VCC(off) max 8.8 V' % ASPECT)
        self.assertEqual(latch['binding'], {'object': {'circuit': 'BIAS', 'ref': 'Q2', 'state': 'LATCH'},
                                            'criterion': catalog.criterion('PWR-C02')})
        self.assertTrue(all(v['evidence'] == bias_function()['evidence'] and v['derived'] for v in rows.values()))
        out = vr.validate_review(p, r, db)
        self.assertTrue(out['valid'], out['errors'])
        self.assertEqual([t['id'] for t in out['workflow']['work_items']], ['W-AUX-5V-MIN'])

    def test_an_aspect_nobody_judged_does_not_pass_by_default(self):
        """A row passes only on its own aspect's margin or judgement, never on another aspect's result."""
        p, r, db = bias_plan()
        r['functions'][0]['calculation']['margin'] = r['functions'][0]['calculation']['margin'][:1]
        _, summary, errors = derive_rows.derive(p, r)
        self.assertEqual(len(errors), 12, errors)
        self.assertTrue(all('judges no' in e for e in errors), errors)
        self.assertEqual(summary['PASS'], 1)   # PWR-C02 LATCH on its own margin
        p, r, db = bias_plan()
        r, _, errors = derive_rows.derive(p, r)
        self.assertEqual(errors, [])
        self.assertEqual(bias_rows(r)['PWR-C15.BIAS-RUN.Q2']['rationale'],
                         '见功能判定 FN-BIAS（%s，RUN）：VCC_min = 9.6 V；余量 0.4x 对 源极跟随相位裕度需求 45°'
                         % catalog.title('PWR-C15'))
        r['functions'][0]['calculation']['margin'] = r['functions'][0]['calculation']['margin'][:-1]
        out = vr.validate_review(p, r, db)
        self.assertFalse(out['valid'])
        self.assertTrue(any('PWR-C15.BIAS-RUN.Q2' in e and 'judges no' in e for e in out['errors']), out['errors'])

    def test_deriving_twice_changes_nothing_and_follows_a_changed_verdict(self):
        p, r, db = bias_plan()
        derive_rows.derive(p, r)
        once = copy.deepcopy(r)
        derive_rows.derive(p, r)
        self.assertEqual(r, once)
        r['functions'][0].update(verdict='PASS', open=[])
        r['functions'][0]['calculation']['margin'][0]['states'] = list(STATES)   # the bound now covers every state
        _, summary, errors = derive_rows.derive(p, r)
        self.assertEqual((errors, summary['INSUFFICIENT'], summary['PASS']), ([], 0, 15))
        self.assertTrue(vr.validate_review(p, r, db)['valid'])

    def test_a_hand_filled_row_is_kept_and_a_disagreement_is_named(self):
        p, r, db = bias_plan()
        r['checks'].append({'id': 'PWR-C03.BIAS-RUN.Q2', 'applicability': 'APPLICABLE', 'review_result': 'PASS',
                            'rationale': 'checked by hand', 'evidence': E, 'handoff': {'required': False},
                            'function_id': 'FN-BIAS', 'aspect': catalog.title('PWR-C03'),
                            'binding': {'object': {'circuit': 'BIAS', 'ref': 'Q2', 'state': 'RUN'},
                                        'criterion': catalog.criterion('PWR-C03')}})
        r, summary, errors = derive_rows.derive(p, r)
        self.assertEqual((errors, summary['kept'], summary['derived']), ([], 1, 14))
        self.assertEqual(bias_rows(r)['PWR-C03.BIAS-RUN.Q2']['rationale'], 'checked by hand')
        r['functions'][0]['open'][0]['decides'] = [dict(aux_open()['decides'][0], aspect=catalog.title('PWR-C03'), states=['RUN'])]
        r['functions'][0]['calculation']['margin'][0]['states'] = list(STATES)
        _, _, errors = derive_rows.derive(p, r)
        self.assertEqual(len(errors), 2, errors)   # review_result and open_ref disagree
        self.assertIn("hand-filled review_result 'PASS' disagrees", errors[0])

    def test_a_row_the_reviewer_judged_na_is_kept(self):
        # an ordinary or stage NA on a planned member row is the reviewer's disposition; derivation does not ask the
        # function for a PASS, FAIL or INSUFFICIENT on it
        p, r, db = bias_plan()
        r['functions'][0]['calculation']['margin'] = r['functions'][0]['calculation']['margin'][:-1]   # no PWR-C15 margin
        for state in STATES:
            r['checks'].append({'id': 'PWR-C15.BIAS-%s.Q2' % state, 'applicability': 'APPLICABLE', 'review_result': 'NA',
                                'na_reason': 'OUTSIDE_SCHEMATIC_STAGE', 'rationale': 'loop gain is measured on the prototype',
                                'evidence': E, 'handoff': {'required': False}, 'function_id': 'FN-BIAS',
                                'aspect': catalog.title('PWR-C15')})
        r, summary, errors = derive_rows.derive(p, r)
        self.assertEqual((errors, summary['kept'], summary['derived']), ([], 3, 12))
        self.assertEqual(bias_rows(r)['PWR-C15.BIAS-RUN.Q2']['review_result'], 'NA')

    def test_an_na_row_of_a_frame_without_a_function_verdict_is_kept(self):
        # every member of a frame judged NA: the frame needs no function verdict for its rows to stand
        p, r, db = bias_plan()
        r['functions'] = []
        for row in [c for c in p['checks'] if '.BIAS-' in c['id']]:
            r['checks'].append({'id': row['id'], 'applicability': 'NOT_APPLICABLE', 'review_result': 'NA',
                                'rationale': 'no such mechanism', 'evidence': E, 'handoff': {'required': False},
                                'function_id': 'FN-BIAS', 'aspect': row['aspect'], 'applicability_evidence': E,
                                'binding': {'object': row['object'], 'criterion': row['criterion']}})
        r, summary, errors = derive_rows.derive(p, r)
        self.assertEqual((errors, summary['kept']), ([], 15))
        out = vr.validate_review(p, r, db)
        self.assertTrue(out['valid'], out['errors'][:3])

    def test_deriving_again_keeps_the_bom_constraint_and_requirement_clauses(self):
        p, r, db = bias_plan()
        derive_rows.derive(p, r)
        row = bias_rows(r)['PWR-C03.BIAS-RUN.Q2']
        row['bom_constraint'] = {'refs': ['Q2'], 'requirement': 'ID ≥ 0.6 A'}
        row['requirement_clauses'] = [{'text': 'clause'}]
        derive_rows.derive(p, r)
        row = bias_rows(r)['PWR-C03.BIAS-RUN.Q2']
        self.assertEqual(row['bom_constraint'], {'refs': ['Q2'], 'requirement': 'ID ≥ 0.6 A'})
        self.assertEqual(row['requirement_clauses'], [{'text': 'clause'}])

    def test_a_fail_item_makes_its_rows_fail_with_the_finding(self):
        p, r, db = bias_plan()
        fn = r['functions'][0]
        fn.update(verdict='FAIL', open=[], fails=[{'key': 'D3-REV', 'finding_id': 'F1', 'what': 'D3 reversed',
                                                   'decides': [{'aspect': ASPECT, 'states': ['LATCH']}], 'conditions': ['c4']}])
        fn['calculation']['margin'][0]['states'] = ['STARTUP', 'RUN']   # LATCH is the reversed-diode fail, not a pass
        r['findings'] = [{'id': 'F1', 'kind': 'DEFECT', 'severity': 'P1', 'check_ids': ['PWR-C02.BIAS-LATCH.Q2'],
                          'location': {'pages': ['1'], 'refs': ['Q2'], 'nets': ['A']},
                          **{k: 'synthetic evidence' for k in ('title', 'observed', 'criterion', 'impact', 'scenario',
                                                               'fix', 'verification')}, 'evidence': E}]
        _, summary, errors = derive_rows.derive(p, r)
        self.assertEqual((errors, summary['FAIL'], summary['PASS']), ([], 1, 14))
        row = bias_rows(r)['PWR-C02.BIAS-LATCH.Q2']
        self.assertEqual((row['review_result'], row['fail_ref'], row['finding_id'], row['severity']),
                         ('FAIL', 'FN-BIAS/D3-REV', 'F1', 'P1'))
        r['findings'] = []
        _, _, errors = derive_rows.derive(p, r)
        self.assertTrue(any('names finding F1' in e for e in errors), errors)

    def test_unknown_function_and_missing_handoff_are_errors(self):
        p, r, db = bias_plan()
        r['functions'] = []
        _, _, errors = derive_rows.derive(p, r)
        self.assertEqual(len(errors), 15)
        p, r, db = bias_plan()
        p['checks'][-1]['handoff'] = {'required': True}
        _, _, errors = derive_rows.derive(p, r)
        self.assertTrue(any('requires a handoff' in e for e in errors), errors)
        r['functions'][0]['handoffs'] = [{'receivers': ['样机试验'], 'constraint': '5 V 空载 VCC ≥ 8.8 V',
                                          'verification': '实测 C3 电压'}]
        _, _, errors = derive_rows.derive(p, r)
        self.assertEqual(errors, [])
        self.assertEqual(bias_rows(r)[p['checks'][-1]['id']]['handoff']['state'], 'OPEN')

    def test_cli_writes_only_when_clean(self):
        p, r, db = bias_plan()
        with tempfile.TemporaryDirectory() as tmp:
            plan, results, out = Path(tmp, 'plan.json'), Path(tmp, 'results.json'), Path(tmp, 'out.json')
            plan.write_text(json.dumps(p), encoding='utf-8')
            results.write_text(json.dumps(r), encoding='utf-8')
            self.assertEqual(derive_rows.main([str(plan), str(results), '-o', str(out)]), 0)
            self.assertEqual(len(bias_rows(json.loads(out.read_text(encoding='utf-8')))), 15)
            r['functions'] = []
            results.write_text(json.dumps(r), encoding='utf-8')
            out.unlink()
            self.assertEqual(derive_rows.main([str(plan), str(results), '-o', str(out)]), 1)
            self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main()

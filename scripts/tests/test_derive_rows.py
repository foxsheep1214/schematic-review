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
from test_review_functions import bias_function, aux_open, ASPECT
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
    r['functions'][0]['judgements'] = judgements()
    return p, r, db


def judgements():
    """The aspects other than the computed one, each judged against a clause of the function."""
    says = {'PWR-C03': 'Q2 源极跟随输出经 C3 储能，负载阶跃由 C3 承担', 'PWR-C04': 'VCC 掉电由 U1 UVLO 处理，无外部放电要求',
            'PWR-C05': 'Q2 VGS 由 D2 钳位，不超过手册绝限', 'PWR-C15': '源极跟随无外置反馈补偿网络'}
    return [{'aspect': catalog.title(rule), 'conditions': ['c4', 'c5'], 'says': says[rule], 'states': list(STATES)}
            for rule in RULES if rule != 'PWR-C02']


def bias_rows(r):
    return {c['id']: c for c in r['checks'] if '.BIAS-' in c['id']}


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
        del r['functions'][0]['judgements']
        _, summary, errors = derive_rows.derive(p, r)
        self.assertEqual(len(errors), 12, errors)
        self.assertTrue(all('judges no' in e for e in errors), errors)
        self.assertEqual(summary['PASS'], 1)   # PWR-C02 LATCH on its own margin
        p, r, db = bias_plan()
        r, _, errors = derive_rows.derive(p, r)
        self.assertEqual(errors, [])
        self.assertEqual(bias_rows(r)['PWR-C15.BIAS-RUN.Q2']['rationale'],
                         '见功能判定 FN-BIAS（%s，RUN）：源极跟随无外置反馈补偿网络（依据 c4、c5）' % catalog.title('PWR-C15'))
        r['functions'][0]['judgements'] = r['functions'][0]['judgements'][:-1]
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
        r['functions'][0]['calculation']['margin']['states'] = list(STATES)   # the bound now covers every state
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
        r['functions'][0]['calculation']['margin']['states'] = list(STATES)
        _, _, errors = derive_rows.derive(p, r)
        self.assertEqual(len(errors), 2, errors)   # review_result and open_ref disagree
        self.assertIn("hand-filled review_result 'PASS' disagrees", errors[0])

    def test_a_fail_item_makes_its_rows_fail_with_the_finding(self):
        p, r, db = bias_plan()
        fn = r['functions'][0]
        fn.update(verdict='FAIL', open=[], fails=[{'key': 'D3-REV', 'finding_id': 'F1', 'what': 'D3 reversed',
                                                   'decides': [{'aspect': ASPECT, 'states': ['LATCH']}], 'conditions': ['c4']}])
        fn['calculation']['margin']['states'] = ['STARTUP', 'RUN']   # LATCH is the reversed-diode fail, not a pass
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

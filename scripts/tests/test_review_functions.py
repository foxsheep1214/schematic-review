"""Function verdicts (design §4/§7): F1–F7 on a bias-supply example, and the rows that follow it.

The example is the 100W PD R5 bias path (Q401 source follower feeding U402 VCC): the record had
computed VCC_min 10.24 V > 9.5 V and still kept 19 rows INSUFFICIENT waiting for "全温小电流保证".
"""
import copy
import unittest

from test_validate_review import fixture, planned, E, C1
from validate_review import fingerprint
from ledger_v3 import record, validate_review as bridged_validate
import validate_review as vr
from review_functions import function_errors, binding_errors, frame_errors, validate_functions
from render_report import render

ASPECT = '变换器电压裕量'   # catalog title of PWR-C02


def bias_function(verdict='OPEN'):
    fn = {
        'id': 'FN-BIAS-VCC', 'circuit': 'BIAS',
        'question': '默认 5 V 输出、−10..105 °C、辅助绕组取最低电压时，Q401 偏置路径能否让 U402 VCC 保持在 9.5 V 以上',
        'objects': {'refs': ['Q401', 'D401', 'D402', 'C403'], 'nets': ['AUX_DC', 'BIAS15', 'VCC']},
        'states': ['STARTUP', 'RUN', 'LATCH'],
        'conditions': [
            {'id': 'c1', 'source': 'Nexperia-PMEG6010CEH.pdf', 'locator': 'p3 Table 7',
             'says': 'VF ≤ 0.31 V @10 mA, ≤ 0.40 V @100 mA (25 °C)', 'use': '20 mA 在两点之间，单调，取 0.40 V 上界'},
            {'id': 'c2', 'source': 'Infineon-ISC032N12LM6.pdf', 'locator': 'p4 Table 4',
             'says': 'VGS(th) 1.2–2.2 V @110 µA', 'use': '20 mA 取 2.2 V + 0.5 V 余量'},
            {'id': 'c3', 'source': 'NCP1343.pdf', 'locator': 'p7 Table 7', 'says': 'VCC(off) max 9.5 V', 'use': '判据'}],
        'calculation': {'claim_ids': ['BIAS-VCCMIN'], 'result': 'VCC_min = 10.24 V',
                        'margin': {'value': 0.74, 'unit': 'V', 'against': 'VCC(off) max 9.5 V'}, 'aspect': ASPECT},
        'verdict': verdict, 'fails': [], 'open': [], 'evidence': [{'source': 'evidence/engineering.md', 'locator': '## BIAS'}]}
    if verdict == 'OPEN':
        fn['open'] = [aux_open()]
    return fn


def aux_open():
    return {'key': 'AUX-5V-MIN', 'kind': 'DESIGN_VALUE',
            'what': 'T301 辅助绕组在 5 V 空载时的最低峰值电压还没有定',
            'scope': '5 V 空载、−10..105 °C', 'spec': 'AUX_AC 峰值 ≥ 14.5 V', 'owner': 'ASG 磁件设计',
            'closure': '磁件规格写明 5 V 空载最低峰值电压且 ≥ 14.5 V',
            'decides': [{'aspect': ASPECT, 'states': ['STARTUP', 'RUN']}],
            'margin_not_decisive_reason': '余量按标称辅助电压算，辅助电压本身是待定的设计值',
            'severity': {'level': 'P1', 'class': 'REQUIRED_FUNCTION', 'affects': 'U402 供电',
                         'consequence': '辅助电压低于规格时 U402 在 5 V 待机掉电重启'}}


def ledger(fn):
    """A plan with PWR-C02 BIAS rows in three states, and the rows that follow `fn`."""
    p, r, db = fixture()
    rows = []
    for state in ('STARTUP', 'RUN', 'LATCH'):
        cid = 'PWR-C02.BIAS-%s.Q401' % state
        p['checks'].append(dict(planned(cid), object={'circuit': 'BIAS', 'ref': 'Q401', 'state': state},
                                criterion='bias output window'))
        row = {'id': cid, 'applicability': 'APPLICABLE', 'review_result': 'PASS', 'evidence': E,
               'rationale': 'see FN-BIAS-VCC', 'handoff': {'required': False},
               'function_id': fn['id'], 'aspect': ASPECT}
        rows.append(row)
    r['checks'] += rows
    r['plan_digest'] = fingerprint(p)
    r = record(r, p)
    r['functions'] = [fn]
    for row in r['checks'][-3:]:
        state = row['id'].split('.')[1].split('-')[1]
        for item in fn.get('open') or []:
            if state in item['decides'][0].get('states', [state]):
                row.update(review_result='INSUFFICIENT', open_ref=fn['id'] + '/' + item['key'])
    return p, r, db


class FunctionShapeTests(unittest.TestCase):
    def test_the_bias_example_validates_and_decides_only_its_states(self):
        p, r, db = ledger(bias_function())
        out = vr.validate_review(p, r, db)
        self.assertTrue(out['valid'], out['errors'])
        results = {c['id']: c['review_result'] for c in r['checks'] if c['id'].startswith('PWR-C02')}
        self.assertEqual(results, {'PWR-C02.BIAS-STARTUP.Q401': 'INSUFFICIENT', 'PWR-C02.BIAS-RUN.Q401': 'INSUFFICIENT',
                                   'PWR-C02.BIAS-LATCH.Q401': 'PASS'})
        self.assertEqual(out['insufficient_by_cause'], {'DESIGN_OPEN': 2})
        self.assertEqual([t['id'] for t in out['workflow']['work_items']], ['W-AUX-5V-MIN'])

    def test_f1_conditions_question_objects_evidence_verdict(self):
        for mutate in (lambda f: f.pop('conditions'), lambda f: f.__setitem__('conditions', []),
                       lambda f: f['conditions'][0].pop('use'), lambda f: f.pop('question'),
                       lambda f: f.__setitem__('objects', {}), lambda f: f.pop('evidence'),
                       lambda f: f.__setitem__('verdict', 'MAYBE'), lambda f: f.pop('calculation')):
            fn = bias_function(); mutate(fn)
            self.assertTrue(function_errors({'functions': [fn]}), fn)
        fn = bias_function(); fn.pop('calculation'); fn['no_calculation_reason'] = '连接性检查，无数值'
        self.assertEqual(function_errors({'functions': [fn]}), [])

    def test_verdict_follows_the_items(self):
        fn = bias_function('PASS'); fn['open'] = [aux_open()]
        self.assertTrue(any('verdict PASS does not follow' in e for e in function_errors({'functions': [fn]})))
        fn = bias_function('OPEN'); fn['open'] = []
        self.assertTrue(function_errors({'functions': [fn]}))

    def test_f2_design_value_is_specified_not_requested(self):
        fn = bias_function(); del fn['open'][0]['spec']
        self.assertTrue(any('spec' in e for e in function_errors({'functions': [fn]})))
        fn = bias_function(); fn['open'][0]['what'] = '向磁件厂家索取辅助绕组调整率'
        self.assertTrue(any('not asked of a vendor' in e for e in function_errors({'functions': [fn]})))

    def test_f3_vendor_datum_names_what_was_checked_and_the_worst_case(self):
        item = {'key': 'HV-IV', 'kind': 'VENDOR_DATUM', 'what': 'NCP1343 HV 恒流源在 40–120 V 的电流下限',
                'scope': '90 Vac、R403 压降后', 'closure': '40..120 V 启动电流下界 ≥ 2 mA',
                'acquisition': 'onsemi 应用支持', 'checked': ['c3'], 'why_insufficient': '表头只给 120 V 测试点',
                'worst_case': {'result': '按 VHV(MIN) 40 V 仍工作，门限 116 V 以上充电'},
                'decides': [{'aspect': ASPECT}],
                'severity': {'level': 'P1', 'class': 'REQUIRED_FUNCTION', 'consequence': '低线不能启动'}}
        fn = bias_function(); fn['open'] = [item]; del fn['calculation']['margin']   # the HV question has no bias margin
        self.assertEqual(function_errors({'functions': [fn]}), [])
        for field in ('checked', 'why_insufficient', 'worst_case', 'acquisition'):
            broken = copy.deepcopy(fn); del broken['open'][0][field]
            self.assertTrue(function_errors({'functions': [broken]}), field)
        broken = copy.deepcopy(fn); broken['open'][0]['checked'] = ['c9']
        self.assertTrue(function_errors({'functions': [broken]}))

    def test_f4_a_positive_margin_decides_unless_a_reason_says_why_not(self):
        fn = bias_function(); del fn['open'][0]['margin_not_decisive_reason']
        errors = function_errors({'functions': [fn]})
        self.assertTrue(any('0.74 V margin' in e for e in errors), errors)
        fn['open'][0]['decides'] = [{'aspect': '变换器电流应力'}]   # another aspect: the margin says nothing about it
        self.assertEqual(function_errors({'functions': [fn]}), [])
        fn = bias_function(); del fn['open'][0]['margin_not_decisive_reason']; del fn['calculation']['aspect']
        self.assertTrue(function_errors({'functions': [fn]}))   # a margin without aspect speaks for the whole function

    def test_f6_a_changed_verdict_cites_a_clause_or_number(self):
        fn = bias_function()
        fn['verdict_history'] = [{'from': 'PASS', 'to': 'OPEN', 'basis': [], 'note': '原句过强'}]
        self.assertTrue(any('verdict_history' in e for e in function_errors({'functions': [fn]})))
        fn['verdict_history'] = [{'from': 'PASS', 'to': 'OPEN', 'basis': ['c2'], 'note': 'VGS(th) 只在 110 µA 保证'}]
        self.assertEqual(function_errors({'functions': [fn]}), [])
        fn['verdict_history'] = [{'from': 'PASS', 'to': 'OPEN', 'basis': ['BIAS-VCCMIN'], 'note': '算例假设'}]
        self.assertEqual(function_errors({'functions': [fn]}), [])

    def test_f7_an_item_over_many_aspects_needs_a_reason(self):
        fn = bias_function()
        fn['open'][0]['decides'] = [{'aspect': a} for a in ('A', 'B', 'C', 'D')]
        self.assertTrue(any('decides covers 4 aspects' in e for e in function_errors({'functions': [fn]})))
        fn['open'][0]['decides_reason'] = '四个方面都依赖同一个辅助电压'
        self.assertFalse(any('decides covers' in e for e in function_errors({'functions': [fn]})))

    def test_keys_are_unique_and_stray_request_fields_are_refused(self):
        fn = bias_function(); fn['open'].append(dict(aux_open(), decides=[{'aspect': 'X'}]))
        self.assertTrue(any('already used' in e for e in function_errors({'functions': [fn]})))
        fn = bias_function(); fn['open'][0].update(kind='REVIEW_INCOMPLETE')
        self.assertTrue(any('only belong to DESIGN_VALUE/VENDOR_DATUM' in e for e in function_errors({'functions': [fn]})))


class RowBindingTests(unittest.TestCase):
    def test_f5_a_row_outside_the_items_decides_is_refused(self):
        p, r, db = ledger(bias_function())
        latch = next(c for c in r['checks'] if c['id'].endswith('LATCH.Q401'))
        latch.update(review_result='INSUFFICIENT', open_ref='FN-BIAS-VCC/AUX-5V-MIN')
        out = vr.validate_review(p, r, db)
        self.assertTrue(any('does not decide aspect' in e and 'LATCH' in e for e in out['errors']), out['errors'])

    def test_f5_a_fail_row_bound_to_a_function_names_its_fail_item(self):
        p, r, db = ledger(bias_function('PASS'))
        run = next(c for c in r['checks'] if c['id'].endswith('RUN.Q401'))
        run.update(review_result='FAIL', severity='P1', finding_id='F1')
        r['findings'] = [{'id': 'F1', 'kind': 'DEFECT', 'severity': 'P1', 'check_ids': [run['id']],
                          'location': {'pages': ['1'], 'refs': ['Q401'], 'nets': ['VCC']},
                          **{k: 'synthetic' for k in ('title', 'observed', 'criterion', 'impact', 'scenario',
                                                      'root_cause', 'recommendation', 'verification', 'severity_reason')}}]
        self.assertTrue(any('fail_ref' in e for e in vr.validate_review(p, r, db)['errors']))
        fn = r['functions'][0]
        fn.update(verdict='FAIL', fails=[{'key': 'VCC-LOW', 'finding_id': 'F1', 'what': 'VCC below 9.5 V',
                                          'decides': [{'aspect': ASPECT, 'states': ['RUN']}]}])
        run['fail_ref'] = 'FN-BIAS-VCC/VCC-LOW'
        out = vr.validate_review(p, r, db)
        self.assertTrue(out['valid'], out['errors'])
        self.assertEqual([t['id'] for t in out['workflow']['work_items']], ['W-VCC-LOW'])

    def test_binding_errors_name_an_unknown_function(self):
        rows = {'X': {'id': 'X', 'review_result': 'PASS', 'function_id': 'FN-NOPE', 'aspect': 'a'}}
        self.assertTrue(binding_errors({}, rows, [bias_function()]))


class DerivedLevelsTests(unittest.TestCase):
    """Two open items with different consequences: each work item keeps its own level in the report."""

    def test_report_counts_p0_and_p1_items_separately(self):
        p, r, db = ledger(bias_function())
        fn = r['functions'][0]
        short = {'key': 'SHORT-SOA', 'kind': 'VENDOR_DATUM', 'what': 'Q701 短路关断轨迹', 'scope': '22.1 V 热态短路',
                 'closure': 'Q701 重复短路 SOA 内', 'acquisition': 'Richtek 应用支持', 'checked': ['c3'],
                 'why_insufficient': '手册无 USBP 关断轨迹', 'worst_case': {'not_boundable_reason': '无驱动电流上限'},
                 'decides': [{'aspect': ASPECT, 'states': ['LATCH']}], 'margin_not_decisive_reason': '余量是偏置电压的，不是 Q701 的',
                 'severity': {'level': 'P0', 'class': 'DAMAGE_OR_HAZARD', 'hazard_path': 'FIRE', 'affects': 'Q701',
                              'consequence': 'Q701 烧毁起火'}}
        fn['open'].append(short)
        latch = next(c for c in r['checks'] if c['id'].endswith('LATCH.Q401'))
        latch.update(review_result='INSUFFICIENT', open_ref='FN-BIAS-VCC/SHORT-SOA')
        out = vr.validate_review(p, r, db)
        self.assertTrue(out['valid'], out['errors'])
        text = render(p, r, out)
        self.assertIn('另有 2 件事因为缺资料或设计还没定，现在还判断不了，其中 1 件可能损坏器件或危及安全（P0）', text)
        section = text.split('### W-AUX-5V-MIN')[1].split('### ', 1)[0]
        self.assertIn('（P1）', section)
        self.assertNotIn('Richtek', section)


class BridgeTests(unittest.TestCase):
    def test_legacy_builders_still_validate_through_the_bridge(self):
        p, r, db = fixture()
        self.assertTrue(bridged_validate(p, r, db)['valid'])


class FrameTests(unittest.TestCase):
    """Plan frames are answered: reviewed member rows bind to the frame's function; the frame has a verdict."""

    def framed(self, frame_id='FN-BIAS-VCC'):
        p, r, db = ledger(bias_function())
        p['functions'] = [{'id': frame_id, 'circuit': 'BIAS', 'question': 'bias frame',
                           'members': [{'check_id': 'PWR-C02.BIAS-%s.Q401' % s, 'rule': 'PWR-C02', 'aspect': ASPECT, 'state': s}
                                       for s in ('STARTUP', 'RUN', 'LATCH')]}]
        r['plan_digest'] = fingerprint(p)
        return p, r, db

    def test_rows_bound_to_their_frame_validate(self):
        p, r, db = self.framed()
        out = vr.validate_review(p, r, db)
        self.assertTrue(out['valid'], out['errors'])

    def test_a_member_row_bound_elsewhere_is_named(self):
        p, r, db = self.framed('FN-BIAS')
        errors = vr.validate_review(p, r, db)['errors']
        self.assertTrue(any('member of frame FN-BIAS' in e for e in errors), errors)
        self.assertTrue(any('no function verdict' in e for e in errors), errors)

    def test_frame_errors_check_aspect_and_skip_unreviewed_frames(self):
        plan = {'functions': [{'id': 'FN-X', 'members': [{'check_id': 'A', 'aspect': 'x'}, {'check_id': 'B', 'aspect': 'y'}]}]}
        rows = {'A': {'review_result': 'PASS', 'function_id': 'FN-X', 'aspect': 'wrong'}, 'B': {'review_result': 'NA'}}
        errors = frame_errors(plan, rows, [{'id': 'FN-X'}])
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("aspect 'wrong'", errors[0])
        self.assertEqual(frame_errors(plan, {'A': {'review_result': 'NA'}}, []), [])


if __name__ == '__main__':
    unittest.main()

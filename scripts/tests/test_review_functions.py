"""Function verdicts (design §4/§7): F1–F7 on a bias-supply example, and the rows that follow it.

The example is a synthetic bias path (Q2 source follower feeding U1 VCC), shaped like a real record that
had computed VCC_min above VCC(off) max and still kept its rows INSUFFICIENT waiting for "全温小电流保证".
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
        'id': 'FN-BIAS', 'circuit': 'BIAS',
        'question': '默认 5 V 输出、−10..105 °C、辅助绕组取最低电压时，Q2 偏置路径能否让 U1 VCC 保持在 8.8 V 以上',
        'objects': {'refs': ['Q2', 'D2', 'D3', 'C3'], 'nets': ['AUX', 'BIAS', 'VCC']},
        'states': ['STARTUP', 'RUN', 'LATCH'],
        'conditions': [
            {'id': 'c1', 'source': 'evidence/ds/D2.txt', 'locator': 'p3 Table 7',
             'says': 'VF ≤ 0.35 V @10 mA, ≤ 0.45 V @100 mA (25 °C)', 'use': '20 mA 在两点之间，单调，取 0.45 V 上界'},
            {'id': 'c2', 'source': 'evidence/ds/Q2.txt', 'locator': 'p4 Table 4',
             'says': 'VGS(th) 1.0–2.0 V @250 µA', 'use': '20 mA 取 2.0 V + 0.5 V 余量'},
            {'id': 'c3', 'source': 'evidence/ds/U1.txt', 'locator': 'p7 Table 7', 'says': 'VCC(off) max 8.8 V', 'use': '判据'}],
        'calculation': {'claim_ids': ['BIAS-VCCMIN'], 'result': 'VCC_min = 9.6 V',
                        'margin': {'value': 0.8, 'unit': 'V', 'against': 'VCC(off) max 8.8 V'}, 'aspect': ASPECT},
        'verdict': verdict, 'fails': [], 'open': [], 'evidence': [{'source': 'evidence/engineering.md', 'locator': '## BIAS'}]}
    if verdict == 'OPEN':
        fn['open'] = [aux_open()]
    return fn


def aux_open():
    return {'key': 'AUX-5V-MIN', 'kind': 'DESIGN_VALUE',
            'what': 'T1 辅助绕组在 5 V 空载时的最低峰值电压还没有定',
            'scope': '5 V 空载、−10..105 °C', 'spec': '辅助绕组峰值 ≥ 13.5 V', 'owner': '磁件设计',
            'closure': '磁件规格写明 5 V 空载最低峰值电压且 ≥ 13.5 V',
            'decides': [{'aspect': ASPECT, 'states': ['STARTUP', 'RUN']}],
            'margin_not_decisive_reason': '余量按标称辅助电压算，辅助电压本身是待定的设计值',
            'severity': {'level': 'P1', 'class': 'REQUIRED_FUNCTION', 'affects': 'U1 供电',
                         'consequence': '辅助电压低于规格时 U1 在 5 V 待机掉电重启'}}


def ledger(fn):
    """A plan with PWR-C02 BIAS rows in three states, and the rows that follow `fn`."""
    p, r, db = fixture()
    rows = []
    for state in ('STARTUP', 'RUN', 'LATCH'):
        cid = 'PWR-C02.BIAS-%s.Q2' % state
        p['checks'].append(dict(planned(cid), object={'circuit': 'BIAS', 'ref': 'Q2', 'state': state},
                                criterion='bias output window'))
        row = {'id': cid, 'applicability': 'APPLICABLE', 'review_result': 'PASS', 'evidence': E,
               'rationale': 'see FN-BIAS', 'handoff': {'required': False},
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
        self.assertEqual(results, {'PWR-C02.BIAS-STARTUP.Q2': 'INSUFFICIENT', 'PWR-C02.BIAS-RUN.Q2': 'INSUFFICIENT',
                                   'PWR-C02.BIAS-LATCH.Q2': 'PASS'})
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
        fn = with_datum(); fn['open'][0].update(margin_not_decisive_reason='120 V 点的斜率不保证 40 V', loose_bound='c3')
        self.assertEqual(function_errors({'functions': [fn]}), [])
        for field in ('checked', 'why_insufficient', 'worst_case', 'acquisition'):
            broken = copy.deepcopy(fn); del broken['open'][0][field]
            self.assertTrue(function_errors({'functions': [broken]}), field)
        broken = copy.deepcopy(fn); broken['open'][0]['checked'] = ['c9']
        self.assertTrue(function_errors({'functions': [broken]}))

    def test_f4_a_positive_margin_decides_unless_a_reason_says_why_not(self):
        fn = bias_function(); del fn['open'][0]['margin_not_decisive_reason']
        errors = function_errors({'functions': [fn]})
        self.assertTrue(any('0.8 V margin' in e for e in errors), errors)
        fn['open'][0]['decides'] = [{'aspect': '变换器电流应力'}]   # another aspect: the margin says nothing about it
        fn['open'][0]['no_margin_reason'] = '电流应力取决于尚未选定的 Q2 封装'
        self.assertEqual(function_errors({'functions': [fn]}), [])
        fn = bias_function(); del fn['open'][0]['margin_not_decisive_reason']; del fn['calculation']['aspect']
        self.assertTrue(function_errors({'functions': [fn]}))   # a margin without aspect speaks for the whole function

    def test_f4_no_headroom_is_a_fail_item_not_an_open_one(self):
        """A computed shortfall against the limit kept open as "design not settled" is refused."""
        fn = bias_function(); del fn['open'][0]['margin_not_decisive_reason']
        fn['calculation'].update(result='VCC_min = 8.6 V', margin={'value': -0.2, 'unit': 'V', 'against': 'VCC(off) max 8.8 V'})
        errors = function_errors({'functions': [fn]})
        self.assertTrue(any('misses the limit' in e for e in errors), errors)
        fn['open'][0].update(margin_not_decisive_reason='VF 取 1 A 测试点，20 mA 下的曲线可把界收紧 0.3 V', loose_bound='c1')
        self.assertEqual(function_errors({'functions': [fn]}), [])
        fn = bias_function('PASS'); fn['calculation']['margin']['value'] = 0
        self.assertTrue(any('misses the limit' in e for e in function_errors({'functions': [fn]})))
        fn.update(verdict='FAIL', fails=[{'key': 'VCC-LOW', 'finding_id': 'F1', 'what': 'VCC 无余量',
                                          'decides': [{'aspect': ASPECT}]}])
        finding = {'id': 'F1', 'remediation': {'readiness': 'READY', 'purpose': 'R3 改 100 Ω'}}
        self.assertEqual(function_errors({'functions': [fn], 'findings': [finding]}), [])

    def test_f4_margins_per_aspect(self):
        fn = bias_function(); del fn['open'][0]['margin_not_decisive_reason']; del fn['calculation']['aspect']
        fn['calculation']['margin'] = [{'value': 0.8, 'unit': 'V', 'against': 'VCC(off) max 8.8 V', 'aspect': '反馈驱动'},
                                       {'value': -3, 'unit': '°C', 'against': 'Tj 115 °C（项目降额）', 'aspect': ASPECT}]
        errors = function_errors({'functions': [fn]})
        self.assertEqual(len(errors), 1, errors)
        self.assertIn('-3 °C against Tj 115 °C', errors[0])
        fn['calculation']['margin'][1]['aspect'] = ''
        self.assertTrue(any('or a list of them' in e for e in function_errors({'functions': [fn]})))

    def test_f8_a_design_value_open_beside_a_calculation_states_its_margin(self):
        fn = bias_function(); del fn['calculation']['margin']
        errors = function_errors({'functions': [fn]})
        self.assertTrue(any('gives no margin' in e and 'BIAS-VCCMIN' in e for e in errors), errors)
        fn['open'][0]['no_margin_reason'] = '辅助绕组匝数尚未选定，没有可比的设计值'
        self.assertEqual(function_errors({'functions': [fn]}), [])
        fn = bias_function(); del fn['calculation']['margin']; fn['calculation']['claim_ids'] = []
        self.assertEqual(function_errors({'functions': [fn]}), [])   # nothing computed: F8 has nothing to ask

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


def hv_datum(**worst):
    """A vendor datum: the clauses read, and a worst case under the public bound."""
    item = {'key': 'HV-IV', 'kind': 'VENDOR_DATUM', 'what': 'U1 HV 恒流源在 40–120 V 的电流下限',
            'scope': '90 Vac、R4 压降后', 'closure': '40..120 V 启动电流下界 ≥ 2 mA',
            'acquisition': '原厂应用支持', 'checked': ['c3'], 'why_insufficient': '表头只给 120 V 测试点',
            'decides': [{'aspect': ASPECT}],
            'severity': {'level': 'P1', 'class': 'REQUIRED_FUNCTION', 'consequence': '低线不能启动'}}
    item['worst_case'] = worst or {
        'bound': {'condition': 'c3', 'value': 'IHV ≥ 2.4 mA @120 V', 'basis': 'ADJACENT_TEST_POINT'},
        'result': '按 120 V 测试点下界，40 V 时按线性外推 0.8 mA', 'margin': {'value': -1.2, 'unit': 'mA', 'against': '启动需求 2 mA'}}
    return item


def with_datum(**worst):
    fn = bias_function(); fn['open'] = [hv_datum(**worst)]; del fn['calculation']['margin']
    return fn


class PublicBoundTests(unittest.TestCase):
    """A vendor datum is asked for only after the public bound has been used: worst_case names the bound
    (clause, value, how it bounds) and the margin under it, and that margin decides like any other (F4)."""

    def test_f3_worst_case_names_the_public_bound_and_its_margin(self):
        fn = with_datum(result='按 VHV(MIN) 40 V 仍工作')   # prose only, no bound or margin
        errors = function_errors({'functions': [fn]})
        self.assertTrue(any('public bound' in e for e in errors), errors)
        fn = with_datum(); fn['open'][0].update(margin_not_decisive_reason='120 V 点的斜率不保证 40 V', loose_bound='c3')
        self.assertEqual(function_errors({'functions': [fn]}), [])
        for bad in ({'condition': 'c9', 'value': 'x', 'basis': 'ADJACENT_TEST_POINT'},
                    {'condition': 'c3', 'value': 'x', 'basis': 'GUESS'}, {'condition': 'c3', 'basis': 'TYPICAL_CURVE'}):
            broken = copy.deepcopy(fn); broken['open'][0]['worst_case']['bound'] = bad
            self.assertTrue(any('public bound' in e for e in function_errors({'functions': [broken]})), bad)

    def test_a_positive_margin_under_the_public_bound_decides(self):
        fn = with_datum(); fn['open'][0]['worst_case']['margin'] = {'value': 0.4, 'unit': 'mA', 'against': '启动需求 2 mA'}
        errors = function_errors({'functions': [fn]})
        self.assertTrue(any('already decides' in e for e in errors), errors)
        fn['open'][0]['margin_not_decisive_reason'] = '外推用的是典型斜率，保证值可能更陡'
        self.assertEqual(function_errors({'functions': [fn]}), [])

    def test_a_shortfall_under_the_public_bound_is_a_fail_item_unless_the_loose_bound_is_named(self):
        fn = with_datum()
        errors = function_errors({'functions': [fn]})
        self.assertTrue(any('misses the limit' in e for e in errors), errors)
        fn['open'][0]['margin_not_decisive_reason'] = '120 V 测试点外推到 40 V 的斜率不是保证值'
        errors = function_errors({'functions': [fn]})
        self.assertTrue(any('loose_bound' in e for e in errors), errors)
        fn['open'][0]['loose_bound'] = 'c9'
        self.assertTrue(any('loose_bound' in e for e in function_errors({'functions': [fn]})))
        fn['open'][0]['loose_bound'] = 'c3'
        self.assertEqual(function_errors({'functions': [fn]}), [])

    def test_f4_a_shortfall_kept_open_in_the_calculation_also_names_the_loose_bound(self):
        fn = bias_function(); del fn['open'][0]['margin_not_decisive_reason']
        fn['calculation'].update(result='VCC_min = 8.6 V', margin={'value': -0.2, 'unit': 'V', 'against': 'VCC(off) max 8.8 V'})
        fn['open'][0]['margin_not_decisive_reason'] = 'VF 取 1 A 测试点，20 mA 下的曲线可把界收紧 0.3 V'
        self.assertTrue(any('loose_bound' in e for e in function_errors({'functions': [fn]})))
        fn['open'][0]['loose_bound'] = 'c1'
        self.assertEqual(function_errors({'functions': [fn]}), [])

    def test_a_shortfall_fail_item_carries_the_change_that_clears_it(self):
        fn = bias_function('FAIL'); fn['calculation']['margin']['value'] = -0.2
        fn['fails'] = [{'key': 'VCC-LOW', 'finding_id': 'F1', 'what': 'VCC 无余量', 'decides': [{'aspect': ASPECT}]}]
        errors = function_errors({'functions': [fn], 'findings': [{'id': 'F1'}]})
        self.assertTrue(any('remediation' in e for e in errors), errors)
        fixed = {'id': 'F1', 'remediation': {'readiness': 'READY', 'purpose': 'R3 改 100 Ω，VF 降 0.3 V'}}
        self.assertEqual(function_errors({'functions': [fn], 'findings': [fixed]}), [])
        fn['calculation']['margin']['value'] = 0.5   # no shortfall: the finding may still be in design
        fn.update(verdict='FAIL')
        self.assertEqual(function_errors({'functions': [fn], 'findings': [{'id': 'F1'}]}), [])

    def test_not_boundable_names_the_curves_and_tables_searched(self):
        fn = with_datum(not_boundable_reason='手册没有 40 V 以下的任何测试点或曲线')
        errors = function_errors({'functions': [fn]})
        self.assertTrue(any('curves_checked' in e for e in errors), errors)
        fn['open'][0]['worst_case']['curves_checked'] = [{'source': 'evidence/ds/U1.txt', 'locator': 'Fig. 12 IHV vs VHV'}]
        fn['open'][0]['worst_case']['operating_point_specified'] = True
        self.assertEqual(function_errors({'functions': [fn]}), [])
        fn['open'][0]['worst_case']['curves_checked'] = ['looked']
        self.assertTrue(any('curves_checked' in e for e in function_errors({'functions': [fn]})))

    def test_an_operating_point_the_datasheet_does_not_specify_is_a_design_risk_not_a_vendor_request(self):
        """Unboundable because the design runs where the datasheet specifies nothing (an output given only above
        some supply): the answer is a fail item whose finding moves the design into the specified region."""
        fn = with_datum(not_boundable_reason='V5 只在 VDD>6 V 时规定，本机 VDD 4.75 V',
                        curves_checked=[{'source': 'evidence/ds/U1.txt', 'locator': 'p11 V5'}])
        self.assertTrue(any('operating_point_specified' in e for e in function_errors({'functions': [fn]})))
        fn['open'][0]['worst_case']['operating_point_specified'] = False
        errors = function_errors({'functions': [fn]})
        self.assertTrue(any('does not specify' in e and 'fail item' in e for e in errors), errors)


class TemplateTextTests(unittest.TestCase):
    def test_one_assumption_copied_into_every_function_is_refused(self):
        """An assumption says what that calculation assumed; a sentence shared by every function assumes nothing."""
        a, b = bias_function('PASS'), bias_function('PASS')
        b['id'] = 'FN-BIAS2'
        for i, fn in enumerate((a, b)):
            fn['calculation']['assumptions'] = ['详见工程记录；条件预算不称原厂保证。', 'Ta = %d °C' % (50 + i)]
        errors = function_errors({'functions': [a, b]})
        self.assertTrue(any('FN-BIAS, FN-BIAS2' in e and 'assumption' in e for e in errors), errors)
        b['calculation']['assumptions'] = ['Ta = 51 °C']
        self.assertFalse(any('assumption' in e for e in function_errors({'functions': [a, b]})))


class AspectJudgementTests(unittest.TestCase):
    """A judgement for an aspect without a number cites the clauses it rests on."""

    def test_a_judgement_names_its_aspect_clauses_and_what_they_settle(self):
        fn = bias_function('PASS')
        fn['judgements'] = [{'aspect': '启动与关断时序', 'conditions': ['c3'], 'says': 'U1 UVLO 处理掉电'}]
        self.assertEqual(function_errors({'functions': [fn]}), [])
        for broken in ({'conditions': ['c9']}, {'conditions': []}, {'says': ''}, {'aspect': ''}):
            bad = copy.deepcopy(fn); bad['judgements'][0].update(broken)
            self.assertTrue(any('judgements' in e for e in function_errors({'functions': [bad]})), broken)

    def test_a_pass_row_needs_its_aspect_judged(self):
        fn = bias_function('PASS')
        del fn['calculation']['margin']
        p, r, db = ledger(fn)
        out = vr.validate_review(p, r, db)
        self.assertTrue(any('judges no' in e for e in out['errors']), out['errors'])
        fn['judgements'] = [{'aspect': ASPECT, 'conditions': ['c3'], 'says': 'VCC_min 9.6 V 高于 VCC(off) max'}]
        p, r, db = ledger(fn)
        self.assertTrue(vr.validate_review(p, r, db)['valid'])


class DeliverablePendingTests(unittest.TestCase):
    """A deliverable another stage owes (magnetics drawing, firmware application capability) is neither a
    vendor datum nor an undecided design value: the item names it, its owner and what the verdict assumed."""

    def pending(self):
        return {'key': 'T1-DRAWING', 'kind': 'DELIVERABLE_PENDING', 'what': 'T1 带绝缘体系的磁件图纸还没有交付',
                'scope': '加强绝缘、5000 m', 'deliverable': 'T1 磁件规格书：三重线型号、绕组顺序、边距、耐压试验值',
                'owner': '磁件设计', 'assumed': '按 intent 的 48:6:21 匝比和三重线次级计算',
                'deliverable_kind': 'CUSTOM_PART_DRAWING',
                'closure': '规格书给出上述项且耐压 ≥ 3000 Vac',
                'decides': [{'aspect': ASPECT, 'states': ['STARTUP', 'RUN']}],
                'margin_not_decisive_reason': '余量按假定的匝比算，匝比在待交付的图纸上',
                'severity': {'level': 'P1', 'class': 'REQUIRED_FUNCTION', 'affects': 'T1', 'consequence': '图纸与假定不符时偏置电压不足'}}

    def test_the_item_names_the_deliverable_its_owner_and_the_assumption(self):
        fn = bias_function(); fn['open'] = [self.pending()]
        self.assertEqual(function_errors({'functions': [fn]}), [])
        for field in ('deliverable', 'owner', 'assumed', 'closure'):
            broken = copy.deepcopy(fn); del broken['open'][0][field]
            self.assertTrue(function_errors({'functions': [broken]}), field)
        broken = copy.deepcopy(fn); broken['open'][0]['acquisition'] = '向厂家索取'
        self.assertTrue(any('only belong' in e for e in function_errors({'functions': [broken]})))
        broken = copy.deepcopy(fn); del broken['open'][0]['scope']
        self.assertTrue(any('scope' in e for e in function_errors({'functions': [broken]})))

    def test_a_deliverable_says_what_kind_of_artifact_is_owed(self):
        """Kind is decided by what is owed, not by who owes it: a firmware capability statement from the chip vendor is a
        deliverable; a parameter of a catalog part is a VENDOR_DATUM with its public bound, and no deliverable kind fits it."""
        fn = bias_function(); fn['open'] = [self.pending()]
        del fn['open'][0]['deliverable_kind']
        self.assertTrue(any('deliverable_kind' in e for e in function_errors({'functions': [fn]})))
        fn['open'][0]['deliverable_kind'] = 'PART_PARAMETER'
        self.assertTrue(any('deliverable_kind' in e for e in function_errors({'functions': [fn]})))
        fn['open'][0].update(deliverable_kind='FIRMWARE_CAPABILITY', owner='芯片原厂应用支持',
                             deliverable='向原厂取得所用 OTP 应用支持的控制接口与状态机说明')
        self.assertEqual(function_errors({'functions': [fn]}), [])

    def test_rows_count_the_deliverable_apart_from_data_and_design_gaps(self):
        fn = bias_function(); fn['open'] = [self.pending()]
        p, r, db = ledger(fn)
        out = vr.validate_review(p, r, db)
        self.assertTrue(out['valid'], out['errors'])
        self.assertEqual(out['insufficient_by_cause'], {'DELIVERABLE_PENDING': 2})
        text = render(p, r, out)
        self.assertIn('因为等交付物，现在还判断不了', text)
        task = next(t for t in out['workflow']['work_items'] if t['id'] == 'W-T1-DRAWING')
        self.assertEqual(task['next_action'], '由磁件设计交付：T1 磁件规格书：三重线型号、绕组顺序、边距、耐压试验值')

    def test_the_report_shows_why_a_computed_margin_did_not_decide(self):
        """Every exit from a margin is shown to the reader, with the clause taken loose."""
        fn = bias_function()
        p, r, db = ledger(fn)
        out = vr.validate_review(p, r, db)
        section = render(p, r, out).split('### W-AUX-5V-MIN')[1].split('\n## ')[0]
        self.assertIn('- **为什么不按余量下结论**：余量按标称辅助电压算，辅助电压本身是待定的设计值', section)

    def test_the_report_shows_the_worst_case_under_the_public_bound(self):
        fn = with_datum()
        fn['open'][0].update(margin_not_decisive_reason='40 V 外推取了线性，过松', loose_bound='c3')
        p, r, db = ledger(fn)
        out = vr.validate_review(p, r, db)
        section = render(p, r, out).split('### W-HV-IV')[1].split('\n## ')[0]
        self.assertIn('- **公开界下的最坏情况**：按 120 V 测试点下界，40 V 时按线性外推 0.8 mA（界：IHV ≥ 2.4 mA @120 V，c3）', section)
        self.assertIn('- **为什么不按余量下结论**：40 V 外推取了线性，过松（取松的条款 c3）', section)

    def test_the_report_shows_what_the_verdict_assumed_and_what_closes_it(self):
        fn = bias_function(); fn['open'] = [self.pending()]
        p, r, db = ledger(fn)
        out = vr.validate_review(p, r, db)
        section = render(p, r, out).split('### W-T1-DRAWING')[1].split('\n## ')[0]
        self.assertIn('- **按什么假定判的**：按 intent 的 48:6:21 匝比和三重线次级计算', section)
        self.assertIn('适用范围：加强绝缘、5000 m', section)
        self.assertIn('- **怎样算通过**：规格书给出上述项且耐压 ≥ 3000 Vac', section)


class RowBindingTests(unittest.TestCase):
    def test_f5_a_row_outside_the_items_decides_is_refused(self):
        p, r, db = ledger(bias_function())
        latch = next(c for c in r['checks'] if c['id'].endswith('LATCH.Q2'))
        latch.update(review_result='INSUFFICIENT', open_ref='FN-BIAS/AUX-5V-MIN')
        out = vr.validate_review(p, r, db)
        self.assertTrue(any('does not decide aspect' in e and 'LATCH' in e for e in out['errors']), out['errors'])

    def test_f5_a_fail_row_bound_to_a_function_names_its_fail_item(self):
        p, r, db = ledger(bias_function('PASS'))
        run = next(c for c in r['checks'] if c['id'].endswith('RUN.Q2'))
        run.update(review_result='FAIL', severity='P1', finding_id='F1')
        r['findings'] = [{'id': 'F1', 'kind': 'DEFECT', 'severity': 'P1', 'check_ids': [run['id']],
                          'location': {'pages': ['1'], 'refs': ['Q2'], 'nets': ['VCC']},
                          **{k: 'synthetic' for k in ('title', 'observed', 'criterion', 'impact', 'scenario',
                                                      'root_cause', 'recommendation', 'verification', 'severity_reason')}}]
        self.assertTrue(any('fail_ref' in e for e in vr.validate_review(p, r, db)['errors']))
        fn = r['functions'][0]
        fn.update(verdict='FAIL', fails=[{'key': 'VCC-LOW', 'finding_id': 'F1', 'what': 'VCC below 8.8 V',
                                          'decides': [{'aspect': ASPECT, 'states': ['RUN']}]}])
        run['fail_ref'] = 'FN-BIAS/VCC-LOW'
        out = vr.validate_review(p, r, db)
        self.assertTrue(out['valid'], out['errors'])
        self.assertEqual([t['id'] for t in out['workflow']['work_items']], ['W-VCC-LOW'])

    def test_a_document_defect_is_not_bound_to_a_function(self):
        rows = {'DOC-Q01.SUMMARY': {'id': 'DOC-Q01.SUMMARY', 'review_result': 'FAIL', 'function_id': 'FN-BIAS',
                                    'aspect': ASPECT, 'fail_ref': 'FN-BIAS/X'}}
        self.assertTrue(any('document defect' in e for e in binding_errors({}, rows, [bias_function()])))
        rows['DOC-Q01.SUMMARY'].update(review_result='INSUFFICIENT', open_ref='FN-BIAS/AUX-5V-MIN')
        rows['DOC-Q01.SUMMARY'].pop('fail_ref')
        self.assertFalse(any('document defect' in e for e in binding_errors({}, rows, [bias_function()])))

    def test_binding_errors_name_an_unknown_function(self):
        rows = {'X': {'id': 'X', 'review_result': 'PASS', 'function_id': 'FN-NOPE', 'aspect': 'a'}}
        self.assertTrue(binding_errors({}, rows, [bias_function()]))


class DerivedLevelsTests(unittest.TestCase):
    """Two open items with different consequences: each work item keeps its own level in the report."""

    def test_report_counts_p0_and_p1_items_separately(self):
        p, r, db = ledger(bias_function())
        fn = r['functions'][0]
        short = {'key': 'SHORT-SOA', 'kind': 'VENDOR_DATUM', 'what': 'Q5 短路关断轨迹', 'scope': '22.1 V 热态短路',
                 'closure': 'Q5 重复短路 SOA 内', 'acquisition': '原厂应用支持', 'checked': ['c3'],
                 'why_insufficient': '手册无 VBUS 关断轨迹',
                 'worst_case': {'not_boundable_reason': '无驱动电流上限', 'operating_point_specified': True,
                                'curves_checked': [{'source': 'evidence/ds/U5.txt', 'locator': 'Fig. 3 SOA'}]},
                 'decides': [{'aspect': ASPECT, 'states': ['LATCH']}], 'margin_not_decisive_reason': '余量是偏置电压的，不是 Q5 的',
                 'severity': {'level': 'P0', 'class': 'DAMAGE_OR_HAZARD', 'hazard_path': 'FIRE', 'affects': 'Q5',
                              'consequence': 'Q5 烧毁起火'}}
        fn['open'].append(short)
        latch = next(c for c in r['checks'] if c['id'].endswith('LATCH.Q2'))
        latch.update(review_result='INSUFFICIENT', open_ref='FN-BIAS/SHORT-SOA')
        out = vr.validate_review(p, r, db)
        self.assertTrue(out['valid'], out['errors'])
        text = render(p, r, out)
        self.assertIn('另有 2 件事因为缺资料或设计还没定，现在还判断不了，其中 1 件可能损坏器件或危及安全（P0）', text)
        section = text.split('### W-AUX-5V-MIN')[1].split('### ', 1)[0]
        self.assertIn('（P1）', section)
        self.assertNotIn('原厂应用支持', section)


class ReportTests(unittest.TestCase):
    """The report answers per function (design §9): a verdict table after the conclusion and a first count row."""

    def test_function_table_and_counts(self):
        p, r, db = ledger(bias_function())
        out = vr.validate_review(p, r, db)
        self.assertTrue(out['valid'], out['errors'])
        text = render(p, r, out)
        self.assertIn('| 功能判定 通过 / 没通过 / 未定 | 0 / 0 / 1 |\n| 检查总数 |', text)
        table = text.split('## 各功能的判断')[1].split('## 待办')[0]
        self.assertIn('| FN-BIAS | %s | 未定 | VCC_min = 9.6 V；余量 0.8 V 对 VCC(off) max 8.8 V | W-AUX-5V-MIN |'
                      % bias_function()['question'], table)
        self.assertLess(text.index('## 结论'), text.index('## 各功能的判断'))
        codes = [c.get('code') for c in (out.get('quality_screening') or {}).get('candidates') or []]
        self.assertNotIn('REUSED_RATIONALE_ACROSS_SCOPES', codes)   # three rows citing one verdict is the proof
        r['functions'][0].update(verdict='PASS', open=[])
        for row in r['checks']:
            if row['id'].startswith('PWR-C02'):
                row.update(review_result='PASS'); row.pop('open_ref', None)
        text = render(p, r, vr.validate_review(p, r, db))
        self.assertIn('| 功能判定 通过 / 没通过 / 未定 | 1 / 0 / 0 |', text)
        self.assertIn('| 通过 | VCC_min = 9.6 V；余量 0.8 V 对 VCC(off) max 8.8 V | — |', text)
        fn = r['functions'][0]; fn.pop('calculation'); fn['no_calculation_reason'] = '连接性检查，无数值'
        self.assertIn('| 通过 | 连接性检查，无数值 | — |', render(p, r, vr.validate_review(p, r, db)))

    def test_a_function_of_document_rows_is_not_counted(self):
        p, r, db = ledger(bias_function('PASS'))
        doc = copy.deepcopy(bias_function('PASS')); doc.update(id='FN-SUMMARIES', circuit='SUMMARIES', question='摘要是否一致')
        r['functions'].append(doc)
        r['checks'].append({'id': 'DOC-Q01.SUMMARY', 'review_result': 'PASS', 'function_id': 'FN-SUMMARIES'})
        text = render(p, r, vr.validate_review(p, r, db))
        self.assertIn('| 功能判定 通过 / 没通过 / 未定 | 1 / 0 / 0 |', text)
        self.assertNotIn('FN-SUMMARIES', text.split('## 各功能的判断')[1].split('\n## ')[0])


class BridgeTests(unittest.TestCase):
    def test_legacy_builders_still_validate_through_the_bridge(self):
        p, r, db = fixture()
        self.assertTrue(bridged_validate(p, r, db)['valid'])


class FrameTests(unittest.TestCase):
    """Plan frames are answered: reviewed member rows bind to the frame's function; the frame has a verdict."""

    def framed(self, frame_id='FN-BIAS'):
        p, r, db = ledger(bias_function())
        p['functions'] = [{'id': frame_id, 'circuit': 'BIAS', 'question': 'bias frame',
                           'members': [{'check_id': 'PWR-C02.BIAS-%s.Q2' % s, 'rule': 'PWR-C02', 'aspect': ASPECT, 'state': s}
                                       for s in ('STARTUP', 'RUN', 'LATCH')]}]
        r['plan_digest'] = fingerprint(p)
        return p, r, db

    def test_rows_bound_to_their_frame_validate(self):
        p, r, db = self.framed()
        out = vr.validate_review(p, r, db)
        self.assertTrue(out['valid'], out['errors'])

    def test_a_member_row_bound_to_a_function_that_does_not_cover_it_is_named(self):
        p, r, db = self.framed('FN-AUX')
        for row in p['checks']:
            if row['id'].startswith('PWR-C02'):
                row['object'] = dict(row['object'], ref='Q9')   # FN-BIAS is about Q2, not Q9
        r['plan_digest'] = fingerprint(p)
        errors = vr.validate_review(p, r, db)['errors']
        self.assertTrue(any('member of frame FN-AUX' in e for e in errors), errors)

    def test_frame_errors_check_aspect_and_skip_unreviewed_frames(self):
        plan = {'functions': [{'id': 'FN-X', 'members': [{'check_id': 'A', 'aspect': 'x'}, {'check_id': 'B', 'aspect': 'y'}]}]}
        rows = {'A': {'review_result': 'PASS', 'function_id': 'FN-X', 'aspect': 'wrong'}, 'B': {'review_result': 'NA'}}
        errors = frame_errors(plan, rows, [{'id': 'FN-X'}])
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("aspect 'wrong'", errors[0])
        self.assertEqual(frame_errors(plan, {'A': {'review_result': 'NA'}}, []), [])


class SharedObjectFrameTests(unittest.TestCase):
    """2026-10-20 热审试点：同一组对象声明了两个功能电路（如 UART 与 LEVEL_SHIFT）时，重复的科目行可以绑到
    另一框架的功能，不必复制开放项；对象不同的框架仍各自作答。"""

    def two_frames(self, other_refs=('Q2',)):
        p, r, db = ledger(bias_function())
        cid = 'PWR-C02.AUX-RUN.Q2'
        p['checks'].append(dict(planned(cid), object={'circuit': 'AUX', 'ref': 'Q2', 'state': 'RUN'}, criterion='aux window'))
        members = lambda circuit, states: [{'check_id': 'PWR-C02.%s-%s.Q2' % (circuit, s), 'rule': 'PWR-C02', 'aspect': ASPECT, 'state': s} for s in states]
        p['functions'] = [{'id': 'FN-BIAS', 'circuit': 'BIAS', 'question': 'bias', 'objects': {'refs': ['Q2'], 'nets': []},
                           'members': members('BIAS', ('STARTUP', 'RUN', 'LATCH'))},
                          {'id': 'FN-AUX', 'circuit': 'AUX', 'question': 'aux', 'objects': {'refs': list(other_refs), 'nets': []},
                           'members': members('AUX', ('RUN',))}]
        r['checks'].append({'id': cid, 'applicability': 'APPLICABLE', 'review_result': 'PASS', 'evidence': E,
                            'rationale': 'see FN-BIAS', 'handoff': {'required': False}, 'function_id': 'FN-BIAS', 'aspect': ASPECT})
        r['plan_digest'] = fingerprint(p)
        return p, r, db

    def test_a_row_of_a_frame_over_the_same_objects_may_bind_to_the_other_function(self):
        p, r, db = self.two_frames()
        out = vr.validate_review(p, r, db)
        self.assertFalse([e for e in out['errors'] if 'FN-AUX' in e], out['errors'])

    def test_delegation_needs_the_function_to_cover_the_row_objects(self):
        p, r, db = self.two_frames()
        p['checks'][-1]['object'] = {'circuit': 'AUX', 'ref': 'Q9', 'state': 'RUN'}
        r['plan_digest'] = fingerprint(p)
        errors = vr.validate_review(p, r, db)['errors']
        self.assertTrue(any('PWR-C02.AUX-RUN.Q2' in e and 'FN-BIAS' in e for e in errors), errors)


class ScopedReviewTests(unittest.TestCase):
    """2026-10-20 热审试点：只审声明的功能电路时，台账声明 review_scope，覆盖类校验只对范围内的行，
    gate 有效但带"不是整板结论"的阻断。"""

    def scoped(self):
        p, r, db = ledger(bias_function())
        p['checks'].append(dict(planned('RST-E01.C9'), object={'ref': 'C9'}))   # outside the scope, no result row
        p['functions'] = [{'id': 'FN-BIAS', 'circuit': 'BIAS', 'question': 'bias', 'objects': {'refs': ['Q2'], 'nets': []},
                           'members': [{'check_id': 'PWR-C02.BIAS-%s.Q2' % s, 'rule': 'PWR-C02', 'aspect': ASPECT, 'state': s}
                                       for s in ('STARTUP', 'RUN', 'LATCH')]}]
        r['checks'] = [c for c in r['checks'] if c['id'].startswith('PWR-C02')]
        r.pop('scope_checks', None); r.pop('coverage', None)
        r['plan_digest'] = fingerprint(p)
        return p, r, db

    def test_a_scoped_ledger_reconciles_only_its_frames_and_is_not_a_board_verdict(self):
        p, r, db = self.scoped()
        r['review_scope'] = {'functions': ['FN-BIAS'], 'reason': 'training hot-review pilot of one circuit'}
        out = vr.validate_review(p, r, db)
        self.assertTrue(out['valid'], out['errors'])
        self.assertEqual(out['release'], 'NO_GO')
        self.assertTrue(any('review_scope' in b for b in out['blockers']), out['blockers'])
        self.assertEqual(out['scope']['functions'], ['FN-BIAS'])

    def test_without_the_declaration_the_missing_rows_still_fail(self):
        p, r, db = self.scoped()
        errors = vr.validate_review(p, r, db)['errors']
        self.assertTrue(any('check coverage mismatch' in e for e in errors), errors)

    def test_scope_names_plan_frames_and_a_reason(self):
        p, r, db = self.scoped()
        r['review_scope'] = {'functions': ['FN-NOPE'], 'reason': ''}
        errors = vr.validate_review(p, r, db)['errors']
        self.assertTrue(any('review_scope' in e for e in errors), errors)


if __name__ == '__main__':
    unittest.main()

"""Function verdicts (design §4/§7): F1–F7 on a bias-supply example, and the rows that follow it.

The example is a synthetic bias path (Q2 source follower feeding U1 VCC), shaped like a real record that
had computed VCC_min above VCC(off) max and still kept its rows INSUFFICIENT waiting for "全温小电流保证".
"""
import copy
import unittest

from test_validate_review import fixture, planned, E, C1
from validate_review import fingerprint
import results_model
import validate_review as vr
from review_functions import function_errors, binding_errors, frame_errors, validate_functions
from render_report import render

ASPECT = '变换器电压裕量'   # catalog title of PWR-C02


STATES = ['STARTUP', 'RUN', 'LATCH']


def bias_function(verdict='OPEN'):
    """The bias example: three numeric limits, a mandatory clause and a netlist fact; a guaranteed-bound margin over the
    states it covers (all three when nothing is open, LATCH beside the open auxiliary-voltage gap)."""
    fn = {
        'id': 'FN-BIAS', 'circuit': 'BIAS',
        'question': '默认 5 V 输出、−10..105 °C、辅助绕组取最低电压时，Q2 偏置路径能否让 U1 VCC 保持在 8.8 V 以上',
        'objects': {'refs': ['Q2', 'D2', 'D3', 'C3'], 'nets': ['AUX', 'BIAS', 'VCC']},
        'states': list(STATES),
        'conditions': [
            {'id': 'c1', 'kind': 'NUMERIC_LIMIT', 'source': 'evidence/ds/D2.txt', 'locator': 'p3 Table 7',
             'says': 'VF ≤ 0.35 V @10 mA, ≤ 0.45 V @100 mA (25 °C)', 'limit': {'max': 0.45, 'unit': 'V'},
             'regime': '25 °C, 10–100 mA', 'use': '20 mA 在两点之间，单调，取 0.45 V 上界'},
            {'id': 'c2', 'kind': 'NUMERIC_LIMIT', 'source': 'evidence/ds/Q2.txt', 'locator': 'p4 Table 4',
             'says': 'VGS(th) 1.0–2.0 V @250 µA', 'limit': {'min': 1.0, 'max': 2.0, 'unit': 'V'},
             'regime': '25 °C, 250 µA', 'use': '20 mA 取 2.0 V + 0.5 V 余量'},
            {'id': 'c3', 'kind': 'NUMERIC_LIMIT', 'source': 'evidence/ds/U1.txt', 'locator': 'p7 Table 7',
             'says': 'VCC(off) max 8.8 V', 'limit': {'max': 8.8, 'unit': 'V'}, 'regime': '−10..105 °C', 'use': '判据'},
            {'id': 'c4', 'kind': 'MANDATORY_CLAUSE', 'source': 'evidence/ds/U1.txt', 'locator': 'p9 §7.3',
             'says': 'VCC 引脚必须经外部电容去耦，UVLO 释放前不得由 HV 脚以外的路径反灌', 'applies': 'U1 由外部偏置供电时',
             'use': '偏置路径的连接要求'},
            # the validator fixture's netlist has one net, A: the fact names it, so it is checked against a real netlist
            {'id': 'c5', 'kind': 'NETLIST_FACT', 'source': 'db.json', 'locator': 'net A', 'nets': ['A'],
             'says': 'A 网把辅助绕组整流接到 Q2 栅极', 'use': '路径'}],
        'calculation': {'claim_ids': ['BIAS-VCCMIN'], 'inputs': ['v_aux_min', 'vf_d2', 'vgs_q2'], 'result': 'VCC_min = 9.6 V',
                        'margin': {'value': 0.8, 'unit': 'V', 'against': 'VCC(off) max 8.8 V',
                                   'states': list(STATES) if verdict == 'PASS' else ['LATCH'], 'basis': guaranteed()},
                        'aspect': ASPECT},
        'verdict': verdict, 'fails': [], 'open': [], 'evidence': [{'source': 'evidence/engineering.md', 'locator': '## BIAS'}]}
    if verdict == 'OPEN':
        fn['open'] = [aux_open()]
    return fn


def guaranteed(**extra):
    return dict({'kind': 'GUARANTEED_BOUND', 'comparison': 'GT', 'limit': 'c3', 'conditions': ['c1', 'c2'],
                 'scope': '−10..105 °C，VF 与 VGS(th) 取保证上界', 'regime': '−10..105 °C',
                 'derivation': 'GUARANTEED_LIMIT',
                 'corners': [{'input': 'vf_d2', 'condition': 'c1', 'picked': 'max', 'why': 'VF 越大 VCC 越低'},
                             {'input': 'vgs_q2', 'condition': 'c2', 'picked': 'max', 'why': 'VGS(th) 越大 VCC 越低'}]},
                **extra)


def aux_open():
    return {'key': 'AUX-5V-MIN', 'kind': 'DESIGN_VALUE',
            'what': 'T1 辅助绕组在 5 V 空载时的最低峰值电压还没有定',
            'scope': '5 V 空载、−10..105 °C', 'spec': '辅助绕组峰值 ≥ 13.5 V', 'owner': '磁件设计',
            'undecided': [{'ref': 'T1', 'parameter': '辅助绕组峰值', 'unit': 'V'}],
            'closure': '磁件规格写明 5 V 空载最低峰值电压且 ≥ 13.5 V',
            'decides': [{'aspect': ASPECT, 'states': ['STARTUP', 'RUN'], 'via': {'condition': 'c3'},
                         'rationale': '启动和运行态 VCC 由辅助绕组经 Q2 供给，最低峰值未定，与 VCC(off) 的比较缺这一项'}],
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
        self.assertEqual(function_errors({'functions': [fn]}), [])   # the gap's edge still cites the VCC(off) limit

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
        fn = with_datum()
        self.assertEqual(function_errors({'functions': [fn]}), [])
        for field in ('checked', 'why_insufficient', 'worst_case', 'acquisition'):
            broken = copy.deepcopy(fn); del broken['open'][0][field]
            self.assertTrue(function_errors({'functions': [broken]}), field)
        broken = copy.deepcopy(fn); broken['open'][0]['checked'] = ['c9']
        self.assertTrue(function_errors({'functions': [broken]}))

    def test_f4_a_margin_that_proves_the_aspect_leaves_no_gap_over_the_same_states(self):
        """A guaranteed bound over STARTUP and RUN proves them; the auxiliary-voltage gap may not block them too. If the bound
        rests on the undecided value it is an estimate, and then the gap is what decides."""
        fn = bias_function(); fn['calculation']['margin']['states'] = list(STATES)
        errors = function_errors({'functions': [fn]})
        self.assertTrue(any('proves this aspect, yet the item blocks it' in e for e in errors), errors)
        fn['calculation']['margin']['basis'] = {'kind': 'ESTIMATE', 'comparison': 'GT', 'conditions': ['c1', 'c2'],
                                                'scope': '按标称辅助电压'}
        self.assertEqual(function_errors({'functions': [fn]}), [])
        fn['open'][0]['decides'][0]['effect'] = 'INFORMATION_ONLY'   # the gap only informs: nothing decides STARTUP/RUN now
        errors = function_errors({'functions': [fn]})
        self.assertTrue(any('decides nothing' in e for e in errors), errors)

    def test_f4_a_proven_shortfall_is_a_fail_item_a_missed_bound_only_fails_to_prove(self):
        """A missed guaranteed bound proves nothing either way (E2); a reachable case that misses proves the fail (E3)."""
        fn = bias_function()
        fn['calculation'].update(result='VCC_min = 8.6 V', margin={'value': -0.2, 'unit': 'V', 'against': 'VCC(off) max 8.8 V',
                                                                   'states': ['STARTUP', 'RUN'], 'basis': guaranteed()})
        self.assertEqual(function_errors({'functions': [fn]}), [])   # the open gap decides; no fail is proven
        fn['calculation']['margin']['basis'] = guaranteed(kind='REACHABLE_CASE', joint='满载与 105 °C 同时出现于额定工况')
        errors = function_errors({'functions': [fn]})
        self.assertTrue(any('proves the worst case misses the limit' in e for e in errors), errors)
        fn.update(verdict='FAIL', open=[], fails=[{'key': 'VCC-LOW', 'finding_id': 'F1', 'what': 'VCC 无余量',
                                                   'decides': [{'aspect': ASPECT, 'states': ['STARTUP', 'RUN']}]}])
        finding = {'id': 'F1', 'remediation': {'readiness': 'READY', 'purpose': 'R3 改 100 Ω'}}
        self.assertEqual(function_errors({'functions': [fn], 'findings': [finding]}), [])
        fn['calculation']['margin']['basis'] = guaranteed()   # the same fail over a merely missed bound rests on nothing
        errors = function_errors({'functions': [fn], 'findings': [finding]})
        self.assertTrue(any('a fail rests on a shortfall a margin proves' in e for e in errors), errors)

    def test_f4_margins_per_aspect(self):
        fn = bias_function()
        fn['conditions'].append({'id': 'c6', 'kind': 'NUMERIC_LIMIT', 'source': 'project-derating.md', 'locator': '§2 表 1',
                                 'says': 'Tj ≤ 115 °C（项目降额）', 'limit': {'max': 115, 'unit': '°C'}, 'regime': 'Ta 50 °C',
                                 'use': '降额判据'})
        fn['calculation']['margin'] = [
            dict(fn['calculation']['margin'], aspect=ASPECT),
            {'value': -3, 'unit': '°C', 'against': 'Tj 115 °C（项目降额）', 'aspect': '变换器电流应力', 'states': ['RUN'],
             'basis': {'kind': 'REACHABLE_CASE', 'comparison': 'GE', 'limit': 'c6', 'conditions': [], 'scope': '满载 RUN',
                       'regime': 'Ta 50 °C', 'joint': '满载与 Ta 50 °C 是同一额定工况', 'derivation': 'GUARANTEED_LIMIT',
                       'corners': [], 'no_corners_reason': '满载电流按需求取定值'}}]
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
        fn['open'][0]['decides'][0]['states'] = list(STATES)
        self.assertEqual(function_errors({'functions': [fn]}), [])
        fn = bias_function(); del fn['calculation']['margin']; fn['calculation']['claim_ids'] = []
        fn['open'][0]['decides'][0]['states'] = list(STATES)
        self.assertEqual(function_errors({'functions': [fn]}), [])   # nothing computed: F8 has nothing to ask

    def test_f6_a_changed_verdict_cites_a_clause_or_number(self):
        fn = bias_function()
        fn['verdict_history'] = [{'from': 'PASS', 'to': 'OPEN', 'basis': [], 'note': '原句过强'}]
        self.assertTrue(any('verdict_history' in e for e in function_errors({'functions': [fn]})))
        fn['verdict_history'] = [{'from': 'PASS', 'to': 'OPEN', 'basis': ['c2'], 'note': 'VGS(th) 只在 110 µA 保证'}]
        self.assertEqual(function_errors({'functions': [fn]}), [])
        fn['verdict_history'] = [{'from': 'PASS', 'to': 'OPEN', 'basis': ['BIAS-VCCMIN'], 'note': '算例假设'}]
        self.assertEqual(function_errors({'functions': [fn]}), [])

    def test_f7_every_edge_of_a_gap_says_what_the_quantity_enters_however_many_there_are(self):
        """Merge plan §3 (D1): one reference value legitimately entering five calculations is one gap with five edges; a
        single edge with no path into the calculation is refused. The count is a hint, never a limit."""
        from review_functions import template_hints
        fn = bias_function()
        fn['open'][0]['decides'] = [{'aspect': a, 'states': ['RUN'], 'via': {'claim': 'BIAS-VCCMIN', 'input': 'v_aux_min'},
                                     'rationale': '%s 的比较取辅助绕组最低峰值，它还没定' % a} for a in ('A', 'B', 'C', 'D', 'E')]
        fn['open'][0]['no_margin_reason'] = '这五个方面的设计值都还没选定'
        self.assertEqual(function_errors({'functions': [fn]}), [])
        self.assertEqual([h['code'] for h in template_hints([fn])], ['WIDE_GAP'])
        broken = copy.deepcopy(fn); broken['open'][0]['decides'] = [{'aspect': 'A', 'states': ['RUN']}]
        errors = function_errors({'functions': [broken]})
        self.assertTrue(any('via names what the missing quantity enters' in e for e in errors), errors)
        self.assertTrue(any('rationale says why' in e for e in errors), errors)
        for via in ({'claim': 'NOPE'}, {'condition': 'c9'}, {'claim': 'BIAS-VCCMIN', 'input': 'v_nope'}):
            broken = copy.deepcopy(fn); broken['open'][0]['decides'][0]['via'] = via
            self.assertTrue(function_errors({'functions': [broken]}), via)
        broken = copy.deepcopy(fn); broken['open'][0]['decides_reason'] = '都依赖同一个辅助电压'
        self.assertTrue(any('decides_reason is retired' in e for e in function_errors({'functions': [broken]})))

    def test_keys_are_unique_and_stray_request_fields_are_refused(self):
        fn = bias_function(); fn['open'].append(dict(aux_open(), decides=[{'aspect': 'X'}]))
        self.assertTrue(any('already used' in e for e in function_errors({'functions': [fn]})))
        fn = bias_function(); fn['open'][0].update(kind='REVIEW_INCOMPLETE')
        self.assertTrue(any('only belong to DESIGN_VALUE/VENDOR_DATUM' in e for e in function_errors({'functions': [fn]})))


# results format 6: the HV current below the 120 V test point, written in numbers (bounding consistency item 1)
HV_TRIED = {'side': 'LOWER', 'quantity': 'U1 HV 恒流源电流下限', 'operating_point': {'min': 40, 'max': 120, 'unit': 'V'},
            'test_points': [{'condition': 'c3', 'at': {'value': 120, 'unit': 'V'}}],
            'why_not': '手册只给 120 V 测试点，没说 IHV 随 VHV 单调', 'other_side': 'NOT_DECISIVE',
            'other_side_reason': '电流上限不决定 VCC 能否升过 UVLO'}


def hv_datum(**worst):
    """A vendor datum: the clauses read, and a worst case under the public bound (an extrapolation: an estimate)."""
    item = {'key': 'HV-IV', 'kind': 'VENDOR_DATUM', 'what': 'U1 HV 恒流源在 40–120 V 的电流下限',
            'scope': '90 Vac、R4 压降后', 'closure': '40..120 V 启动电流下界 ≥ 2 mA',
            'acquisition': '原厂应用支持', 'checked': ['c3'], 'why_insufficient': '表头只给 120 V 测试点',
            'decides': [{'aspect': ASPECT, 'states': list(STATES), 'via': {'condition': 'c3'}, 'side': 'LOWER',
                         'rationale': '启动电流决定 VCC 能否在 HV 供电下升过 UVLO，40 V 处没有保证值'}],
            'severity': {'level': 'P1', 'class': 'REQUIRED_FUNCTION', 'affects': 'U1 启动', 'consequence': '低线不能启动'}}
    item['worst_case'] = worst or {
        'bound': {'condition': 'c3', 'value': 'IHV ≥ 2.4 mA @120 V', 'basis': 'ADJACENT_TEST_POINT'},
        'result': '按 120 V 测试点下界，40 V 时按线性外推 0.8 mA',
        'margin': {'value': -1.2, 'unit': 'mA', 'against': '启动需求 2 mA',
                   'basis': {'kind': 'ESTIMATE', 'comparison': 'GE', 'conditions': ['c3'], 'scope': '40 V，线性外推'}}}
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
        fn = with_datum()
        self.assertEqual(function_errors({'functions': [fn]}), [])
        for bad in ({'condition': 'c9', 'value': 'x', 'basis': 'ADJACENT_TEST_POINT'},
                    {'condition': 'c3', 'value': 'x', 'basis': 'GUESS'}, {'condition': 'c3', 'basis': 'TYPICAL_CURVE'}):
            broken = copy.deepcopy(fn); broken['open'][0]['worst_case']['bound'] = bad
            self.assertTrue(any('public bound' in e for e in function_errors({'functions': [broken]})), bad)
        broken = copy.deepcopy(fn); del broken['open'][0]['worst_case']['margin']['basis']
        self.assertTrue(any('worst_case.margin: margin basis' in e for e in function_errors({'functions': [broken]})))

    def test_a_proving_margin_under_the_public_bound_decides(self):
        fn = with_datum()
        fn['open'][0]['worst_case']['margin'].update(value=0.4, basis=guaranteed(conditions=['c3'], comparison='GE'))
        errors = function_errors({'functions': [fn]})
        self.assertTrue(any('already decides' in e for e in errors), errors)
        fn['open'][0]['worst_case']['margin']['basis'] = {'kind': 'ESTIMATE', 'comparison': 'GE', 'conditions': ['c3'],
                                                          'scope': '外推用的是典型斜率'}
        self.assertEqual(function_errors({'functions': [fn]}), [])

    def test_a_proven_shortfall_under_the_public_bound_is_a_fail_item(self):
        fn = with_datum()
        self.assertEqual(function_errors({'functions': [fn]}), [])   # an extrapolation proves nothing: the datum is asked
        fn['open'][0]['worst_case']['margin']['basis'] = guaranteed(kind='REACHABLE_CASE', conditions=['c3'],
                                                                    joint='90 Vac 低线与 R4 压降同时出现')
        errors = function_errors({'functions': [fn]})
        self.assertTrue(any('the shortfall is proven' in e for e in errors), errors)


    def test_a_shortfall_fail_item_carries_the_change_that_clears_it(self):
        fn = bias_function('FAIL'); fn['calculation']['margin'].update(
            value=-0.2, basis=guaranteed(kind='REACHABLE_CASE', joint='满载与 105 °C 同时出现于额定工况'))
        fn['fails'] = [{'key': 'VCC-LOW', 'finding_id': 'F1', 'what': 'VCC 无余量',
                        'decides': [{'aspect': ASPECT, 'states': ['LATCH']}]}]
        errors = function_errors({'functions': [fn], 'findings': [{'id': 'F1'}]})
        self.assertTrue(any('remediation' in e for e in errors), errors)
        fixed = {'id': 'F1', 'remediation': {'readiness': 'READY', 'purpose': 'R3 改 100 Ω，VF 降 0.3 V'}}
        self.assertEqual(function_errors({'functions': [fn], 'findings': [fixed]}), [])
        fn['calculation']['margin']['value'] = 0.5   # the reachable case meets the limit: it proves nothing about the fail
        errors = function_errors({'functions': [fn], 'findings': [{'id': 'F1'}]})
        self.assertTrue(any('a fail rests on a shortfall a margin proves' in e for e in errors), errors)
        fn['fails'][0]['conditions'] = ['c4']   # a violated mandatory clause carries the fail on its own
        self.assertEqual(function_errors({'functions': [fn], 'findings': [{'id': 'F1'}]}), [])

    def test_not_boundable_names_the_curves_and_tables_searched(self):
        fn = with_datum(not_boundable_reason='手册没有 40 V 以下的任何测试点或曲线', monotonic_tried=HV_TRIED)
        errors = function_errors({'functions': [fn]})
        self.assertTrue(any('curves_checked' in e for e in errors), errors)
        fn['open'][0]['worst_case']['curves_checked'] = [{'source': 'evidence/ds/U1.txt', 'locator': 'Fig. 12 IHV vs VHV'}]
        fn['open'][0]['worst_case'].update(operating_point_specified=True, specified_by='c4')
        self.assertEqual(function_errors({'functions': [fn]}), [])
        fn['open'][0]['worst_case']['curves_checked'] = ['looked']
        self.assertTrue(any('curves_checked' in e for e in function_errors({'functions': [fn]})))

    def test_an_operating_point_the_datasheet_does_not_specify_is_a_design_risk_not_a_vendor_request(self):
        """Unboundable because the design runs where the datasheet specifies nothing (an output given only above
        some supply): the answer is a fail item whose finding moves the design into the specified region."""
        fn = with_datum(not_boundable_reason='V5 只在 VDD>6 V 时规定，本机 VDD 4.75 V', monotonic_tried=HV_TRIED,
                        curves_checked=[{'source': 'evidence/ds/U1.txt', 'locator': 'p11 V5'}])
        self.assertTrue(any('operating_point_specified' in e for e in function_errors({'functions': [fn]})))
        fn['open'][0]['worst_case']['operating_point_specified'] = False
        errors = function_errors({'functions': [fn]})
        self.assertTrue(any('does not specify' in e and 'fail item' in e for e in errors), errors)


    def test_a_fail_may_rest_on_an_operating_point_outside_the_specified_region(self):
        # The rule above sends such a design to a fail item, but a fail item took only a margin or a mandatory clause,
        # so a reviewer wrote the unspecified point as a limit of 0 mA to compare against.
        fn = bias_function('FAIL'); fn['open'] = []; fn['calculation'].pop('margin')
        fn['fails'] = [{'key': 'D2-LOW-I', 'finding_id': 'F1', 'what': 'D2 工作在 20 µA，手册只规定 10–100 mA',
                        'decides': [{'aspect': ASPECT, 'states': ['LATCH']}],
                        'outside_specified': {'condition': 'c1', 'operating_point': 'D2 正向电流 20 µA',
                                              'curves_checked': [{'source': 'evidence/ds/D2.txt', 'locator': 'Fig. 2 IF-VF'},
                                                                 {'source': 'evidence/ds/D2.txt', 'locator': 'p3 电气特性'}]}}]
        finding = {'id': 'F1', 'remediation': {'readiness': 'READY', 'purpose': 'R3 改 1 kΩ，使 D2 回到 10 mA 以上'}}
        self.assertEqual(function_errors({'functions': [fn], 'findings': [finding]}), [])
        del fn['fails'][0]['outside_specified']['curves_checked']
        errors = function_errors({'functions': [fn], 'findings': [finding]})
        self.assertTrue(any('outside_specified' in e and 'curves_checked' in e for e in errors), errors)
        fn['fails'][0]['outside_specified'].update(condition='c5', curves_checked=[{'source': 'x', 'locator': 'y'}])
        errors = function_errors({'functions': [fn], 'findings': [finding]})
        self.assertTrue(any('outside_specified.condition' in e for e in errors), errors)

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


    def test_one_calculation_result_copied_into_another_function_is_refused(self):
        """The report's margin column showed a sense-chain calculation beside a firmware and an optocoupler function: the
        reviewer had pasted one result into several functions, so each borrowed numbers it never computed."""
        a, b = bias_function('PASS'), bias_function('PASS')
        b['id'] = 'FN-BIAS2'
        b['calculation']['result'] = a['calculation']['result']
        errors = function_errors({'functions': [a, b]})
        self.assertTrue(any('FN-BIAS, FN-BIAS2' in e and 'calculation.result' in e for e in errors), errors)
        b['calculation']['result'] = a['calculation']['result'] + '；本功能另算 0.8 V'
        self.assertFalse(any('calculation.result' in e for e in function_errors({'functions': [a, b]})))


class AspectJudgementTests(unittest.TestCase):
    """A judgement for an aspect without a number cites the clauses it rests on."""

    def test_a_judgement_names_its_aspect_clauses_and_what_they_settle(self):
        fn = bias_function('PASS')
        fn['judgements'] = [{'aspect': '启动与关断时序', 'conditions': ['c4'], 'says': 'U1 UVLO 处理掉电', 'states': list(STATES)}]
        self.assertEqual(function_errors({'functions': [fn]}), [])
        for broken in ({'conditions': ['c9']}, {'conditions': []}, {'says': ''}, {'aspect': ''}, {'states': []}):
            bad = copy.deepcopy(fn); bad['judgements'][0].update(broken)
            self.assertTrue(any('judgements' in e for e in function_errors({'functions': [bad]})), broken)

    def test_a_number_is_compared_in_a_margin_not_settled_in_a_sentence(self):
        """Merge plan §4 (E6): a judgement citing a numeric limit is a calculation written as prose."""
        fn = bias_function('PASS')
        fn['judgements'] = [{'aspect': '启动与关断时序', 'conditions': ['c3', 'c5'], 'says': 'VCC 高于 VCC(off)'}]
        errors = function_errors({'functions': [fn]})
        self.assertTrue(any('cites a numeric limit (c3)' in e for e in errors), errors)

    def test_a_pass_row_needs_its_aspect_judged(self):
        fn = bias_function('PASS')
        del fn['calculation']['margin']
        p, r, db = ledger(fn)
        out = vr.validate_review(p, r, db)
        self.assertTrue(any('judges no' in e for e in out['errors']), out['errors'])
        # PWR-C02 is an engineering calculation: its margin judges it (a sentence would not, test_calculation_aspects)
        p, r, db = ledger(bias_function('PASS'))
        out = vr.validate_review(p, r, db)
        self.assertTrue(out['valid'], out['errors'])

    def test_evidence_without_states_covers_only_stateless_rows(self):
        """Merge plan §3 (D3): RUN evidence does not close STARTUP, and evidence that names no state covers no row that has one."""
        fn = bias_function('PASS'); fn['calculation']['margin']['states'] = ['RUN']
        p, r, db = ledger(fn)
        errors = vr.validate_review(p, r, db)['errors']
        self.assertTrue(any('PWR-C02.BIAS-STARTUP.Q2' in e and 'judges no' in e for e in errors), errors)
        self.assertFalse(any('PWR-C02.BIAS-RUN.Q2' in e for e in errors), errors)
        del fn['calculation']['margin']['states']
        p, r, db = ledger(fn)
        errors = vr.validate_review(p, r, db)['errors']
        self.assertEqual(len([e for e in errors if 'judges no' in e]), 3, errors)


class DeliverablePendingTests(unittest.TestCase):
    """A deliverable another stage owes (magnetics drawing, firmware application capability) is neither a
    vendor datum nor an undecided design value: the item names it, its owner and what the verdict assumed."""

    def pending(self):
        return {'key': 'T1-DRAWING', 'kind': 'DELIVERABLE_PENDING', 'what': 'T1 带绝缘体系的磁件图纸还没有交付',
                'scope': '加强绝缘、5000 m', 'deliverable': 'T1 磁件规格书：三重线型号、绕组顺序、边距、耐压试验值',
                'owner': '磁件设计', 'assumed': '按 intent 的 48:6:21 匝比和三重线次级计算',
                'deliverable_kind': 'CUSTOM_PART_DRAWING',
                'missing_parameters': [{'name': '绕组顺序'}, {'name': '耐压试验值', 'unit': 'Vac'}],
                'closure': '规格书给出上述项且耐压 ≥ 3000 Vac',
                'decides': [{'aspect': ASPECT, 'states': ['STARTUP', 'RUN'], 'via': {'claim': 'BIAS-VCCMIN', 'input': 'v_aux_min'},
                             'rationale': '辅助电压按假定的匝比算，匝比在待交付的图纸上'}],
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

    def test_the_report_shows_which_judgements_the_gap_holds_open(self):
        """Every row a gap blocks reaches the reader, with what the missing quantity enters and why."""
        fn = bias_function()
        p, r, db = ledger(fn)
        out = vr.validate_review(p, r, db)
        section = render(p, r, out).split('### W-AUX-5V-MIN')[1].split('\n## ')[0]
        self.assertIn('- **这个缺口影响哪些判断**：%s（STARTUP、RUN），经 U1.txt p7 Table 7：启动和运行态 VCC 由辅助绕组经 Q2 供给' % ASPECT, section)

    def test_the_kind_of_missing_data_is_named(self):
        # Five vendor-data gaps on the R5 bench all had a negative margin under the public bound and read "missing
        # data", as if a file were missing; the type line now says what kind of gap it is.
        fn = with_datum()
        p, r, db = ledger(fn)
        out = vr.validate_review(p, r, db)
        section = render(p, r, out).split('### W-HV-IV')[1].split('\n## ')[0]
        self.assertIn('类型：缺资料（按公开资料界限算不够）', section)
        self.assertIn('| 资料不足细分：设计还要定 / 等配置表 / 等定制件图纸 / 按公开资料界限算不够 / '
                      '按公开资料界限算够，但不是保证值 / 公开资料定不出界限 | 0 / 0 / 0 / 3 / 0 / 0 |', render(p, r, out))
        sub = results_model.gap_subclass
        self.assertEqual(sub({'kind': 'VENDOR_DATUM', 'worst_case': {'margin': {'value': 0.3}}}), 'PUBLIC_BOUND_UNGUARANTEED')
        self.assertEqual(sub({'kind': 'VENDOR_DATUM', 'worst_case': {'not_boundable_reason': 'x'}}), 'NOT_BOUNDABLE')
        self.assertEqual(sub({'kind': 'DESIGN_VALUE'}), 'DESIGN_DECISION')
        self.assertEqual(sub({'kind': 'DELIVERABLE_PENDING', 'deliverable_kind': 'CUSTOM_PART_DRAWING'}), 'PART_DRAWING')
        self.assertEqual(sub({'kind': 'DELIVERABLE_PENDING', 'deliverable_kind': 'CONFIGURATION_TABLE'}), 'CONFIGURATION')
        self.assertIsNone(sub({'kind': 'REQUIREMENT'}))

    def test_aspects_one_gap_blocks_for_the_same_reason_share_one_line(self):
        # One gap blocking 22 aspects printed the same sentence 22 times, each after an internal condition id
        # ("经 requirement"); aspects with the same entry point and reason now share one line, and the entry point is
        # the condition's source and locator.
        fn = bias_function()
        item = fn['open'][0]
        why = item['decides'][0]['rationale']
        item['decides'] = [{'aspect': 'A', 'states': ['RUN'], 'via': {'condition': 'c3'}, 'rationale': why},
                           {'aspect': 'B', 'states': ['STARTUP', 'RUN'], 'via': {'condition': 'c3'}, 'rationale': why},
                           {'aspect': 'C', 'via': {'condition': 'c3'}, 'rationale': 'another reason'}]
        self.assertEqual(results_model.blocked_judgements(item, fn),
                         ['A（RUN）、B（STARTUP、RUN），经 U1.txt p7 Table 7：' + why,
                          'C，经 U1.txt p7 Table 7：another reason'])

    def test_a_reason_that_only_restates_the_gap_is_not_printed_per_aspect(self):
        # One gap printed its own title once per blocked aspect ("<gap>；this datum enters <aspect>"), through
        # several entry points, so the list could not be read; the aspects now share one line and the restated
        # title is left to the item's heading.
        fn = bias_function()
        item = fn['open'][0]
        what = item['what']
        item['decides'] = [{'aspect': a, 'via': {'condition': c}, 'rationale': '%s；这一数据进入%s的比较' % (what, a)}
                           for a, c in (('A', 'c3'), ('B', 'c3'), ('C', 'c4'))]
        item['decides'].append({'aspect': 'D', 'via': {'condition': 'c3'}, 'rationale': 'D 由另一条款单独决定'})
        lines = results_model.blocked_judgements(item, fn)
        self.assertEqual(len(lines), 2, lines)
        self.assertTrue(lines[0].startswith('A、B、C，经 U1.txt p7 Table 7、'), lines)
        self.assertNotIn(what, '\n'.join(lines))
        self.assertEqual(lines[1], 'D，经 U1.txt p7 Table 7：D 由另一条款单独决定')

    def test_the_report_shows_the_worst_case_under_the_public_bound(self):
        fn = with_datum()
        p, r, db = ledger(fn)
        out = vr.validate_review(p, r, db)
        self.assertTrue(out['valid'], out['errors'])
        section = render(p, r, out).split('### W-HV-IV')[1].split('\n## ')[0]
        self.assertIn('- **公开资料界限下的最坏情况**：按 120 V 测试点下界，40 V 时按线性外推 0.8 mA（界：IHV ≥ 2.4 mA @120 V，U1.txt p7 Table 7）', section)
        self.assertIn('经 U1.txt p7 Table 7：启动电流决定 VCC 能否在 HV 供电下升过 UVLO', section)

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
                                          'decides': [{'aspect': ASPECT, 'states': ['RUN']}], 'conditions': ['c4']}])
        fn['calculation']['margin']['states'] = ['STARTUP', 'LATCH']
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
                                'monotonic_tried': dict(HV_TRIED, quantity='Q5 关断轨迹电流', why_not='手册无短路轨迹曲线'),
                                'specified_by': 'c4',
                                'curves_checked': [{'source': 'evidence/ds/U5.txt', 'locator': 'Fig. 3 SOA'}]},
                 'decides': [{'aspect': ASPECT, 'states': ['LATCH'], 'via': {'condition': 'c3'}, 'side': 'LOWER',
                              'rationale': '短路时 VCC 是否保持取决于 Q5 关断前的轨迹，手册没有'}],
                 'severity': {'level': 'P0', 'class': 'DAMAGE_OR_HAZARD', 'hazard_path': 'FIRE', 'affects': 'Q5',
                              'consequence': 'Q5 烧毁起火'}}
        fn['open'].append(short)
        fn['calculation']['margin']['basis'] = {'kind': 'ESTIMATE', 'comparison': 'GT', 'conditions': ['c1', 'c2', 'c3'],
                                                'scope': '不含短路轨迹'}
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

    def test_the_basis_column_states_each_margin_once_and_rounded(self):
        """One margin written for three aspects showed three times, each as -0.0612103174603175 us."""
        from render_report import function_basis
        margin = {'value': -0.0612103174603175, 'unit': 'us', 'against': 'demag ≥ min on-time'}
        fn = {'calculation': {'result': 'demag 0.839 us', 'margin': [dict(margin, aspect=a) for a in ('t', 'loss', 'drive')]}}
        self.assertEqual(function_basis(fn), 'demag 0.839 us；余量 -0.06121 us 对 demag ≥ min on-time')
        fn['calculation']['margin'][1]['value'] = 12.3456789
        self.assertEqual(function_basis(fn).count('余量'), 2)
        self.assertIn('余量 12.35 us', function_basis(fn))
        fn['calculation']['margin'] = [{'value': 0.8, 'unit': 'V', 'against': 'x'}, {'value': 150000, 'unit': 'Hz', 'against': 'y'}]
        self.assertIn('余量 0.8 V', function_basis(fn))
        self.assertIn('余量 150000 Hz', function_basis(fn))

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
    """2026-10-20 热审试点：同一组对象声明了两个功能电路（如 UART 与 LEVEL_SHIFT）时，重复的检查行可以绑到
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


    def test_a_member_row_is_not_delegated_to_a_function_of_the_reviewers_own(self):
        # On one board each gap of a circuit went into a function the reviewer made for it, its rows moved there
        # and the circuit's own function said PASS: the report listed every work item a second time as a function.
        p, r, db = self.two_frames()
        own = bias_function(); own['id'] = 'FN-GAP'
        r['functions'].append(own)
        r['checks'][-1]['function_id'] = 'FN-GAP'
        errors = vr.validate_review(p, r, db)['errors']
        self.assertTrue(any('PWR-C02.AUX-RUN.Q2' in e and 'FN-GAP' in e and
                            "write it in the owning frame, let other frames' rows use open_ref" in e for e in errors), errors)

    def test_a_planned_circuits_row_takes_its_gap_from_a_planned_function(self):
        # The same pattern with the rows left in place: the circuit's rows pointed their open_ref at a function the
        # reviewer made to hold the gap. A planned circuit's gap is an item of a planned function.
        p, r, db = ledger(bias_function())
        p['functions'] = [{'id': 'FN-BIAS', 'circuit': 'BIAS', 'question': 'bias', 'objects': bias_function()['objects'],
                           'members': [{'check_id': 'PWR-C02.BIAS-%s.Q2' % s, 'rule': 'PWR-C02', 'aspect': ASPECT, 'state': s}
                                       for s in ('STARTUP', 'RUN', 'LATCH')]}]
        own = bias_function(); own['id'] = 'FN-GAP'
        own['objects'] = {'refs': ['Q2', 'Q9'], 'nets': []}   # Q9 outside the circuit: only the open_ref is at issue
        r['functions'].append(own)
        r['plan_digest'] = fingerprint(p)
        message = lambda errors: [e for e in errors if 'takes its open_ref' in e]
        self.assertFalse(message(vr.validate_review(p, r, db)['errors']))
        for row in r['checks']:
            if row.get('open_ref') == 'FN-BIAS/AUX-5V-MIN':
                row['open_ref'] = 'FN-GAP/AUX-5V-MIN'
        found = message(vr.validate_review(p, r, db)['errors'])
        self.assertTrue(found and all('FN-GAP' in e and "write it in the owning frame, let other frames' rows use open_ref" in e
                                      for e in found), found)


    def test_a_function_of_the_reviewers_own_takes_only_objects_no_circuit_holds(self):
        # A function the reviewer made over parts one circuit already holds restates that circuit's question; a function
        # over parts outside every circuit (a circuit the plan missed) is allowed, with the hint to declare it.
        p, r, db = self.two_frames()
        p['functions'].append({'id': 'FN-SYS-PINMAP', 'system': 'SYS-PINMAP', 'question': 'pins',
                               'objects': {'refs': ['Q2', 'Q7'], 'nets': []}, 'members': []})
        r['plan_digest'] = fingerprint(p)
        own = bias_function(); own['id'] = 'FN-GAP'
        own['objects'] = {'refs': ['Q2'], 'nets': []}
        r['functions'].append(own)
        found = [e for e in vr.validate_review(p, r, db)['errors'] if e.startswith('FN-GAP:')]
        self.assertTrue(any('write it into frame FN-BIAS' in e and 'circuit_decisions' in e for e in found), found)
        own['objects'] = {'refs': ['Q2', 'Q7'], 'nets': []}   # Q7 is in no circuit (only in a system frame)
        found = [e for e in vr.validate_review(p, r, db)['errors'] if e.startswith('FN-GAP:')]
        self.assertFalse([e for e in found if 'write it into frame' in e], found)


class ScopedReviewTests(unittest.TestCase):
    """2026-10-20 热审试点：只审声明的功能电路时，台账声明 review_scope，覆盖类校验只对范围内的行，
    gate 有效但带"不是整板结论"的阻断。"""

    def scoped(self):
        p, r, db = ledger(bias_function())
        p['checks'].append(dict(planned('RST-E01.C9'), object={'ref': 'C9'}))   # outside the scope, no result row
        p['functions'] = [{'id': 'FN-BIAS', 'circuit': 'BIAS', 'question': 'bias', 'objects': bias_function()['objects'],
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


class ReviewerAgreementTests(unittest.TestCase):
    """2026-10-21: two reviewers of the same board (SR-20261021-R5-claude / -codex) agreed on 184 of 287 shared rows
    and on no finding. The record let the divergence through: conditions that located nothing ("相关位号所有物理脚",
    "## BIAS") copied into every function, judgements resting only on them, one reason sentence on ten open items,
    a design value deciding twelve aspects, function objects widened past the intent circuit so a bias gap reached
    the PFC gate driver, a connector row with four clamp parts passed by hand, and a requirement row made stage NA
    whole. Each is now refused; the other reviewer's record passes every one of these unchanged."""

    def test_f1_a_function_needs_a_clause_that_carries_the_verdict(self):
        fn = bias_function('PASS')
        fn['conditions'] = [
            {'id': 'CONN', 'kind': 'ENGINEERING_ASSUMPTION', 'source': 'evidence/component-connections.txt',
             'locator': '相关位号所有物理脚', 'says': '本轮新导出R5的实际连接', 'use': '核对供电、信号及回流'},
            {'id': 'ENG', 'kind': 'ENGINEERING_ASSUMPTION', 'source': 'evidence/engineering.md', 'locator': '## BIAS',
             'says': '本轮原厂条款摘录、独立推导和适用边界', 'use': '依据所列原厂页码逐项判断'}]
        fn['calculation']['margin']['basis'] = {'kind': 'ESTIMATE', 'comparison': 'GT', 'conditions': ['ENG'], 'scope': '笔记'}
        errors = function_errors({'functions': [fn]})
        self.assertTrue(any('no clause carries the verdict' in e for e in errors), errors)
        fn['conditions'].append(bias_function()['conditions'][2])   # c3 listed but cited by nothing: still no clause
        self.assertTrue(any('no clause carries the verdict' in e for e in function_errors({'functions': [fn]})))
        fn['calculation']['margin']['basis'] = guaranteed(conditions=[])   # cited as the limit of a guaranteed bound
        self.assertFalse(any('no clause carries the verdict' in e for e in function_errors({'functions': [fn]})))

    def test_located_means_a_page_table_section_id_or_named_nets(self):
        from review_functions import located, clause
        for locator in ('p4 订货表', 'Table 4-5（p154）', '电气特性 MIN_TON', 'nets PGND/SGND', 'R5-BIAS value.AUXmax_V',
                        'REQ-LIFE-001', 'E-ENERGY-01、§6.1', '第 3 页', '引脚说明 VCC'):
            self.assertTrue(located({'locator': locator}), locator)
        for locator in ('相关位号所有物理脚', '## BIAS', 'BIAS实际位号/物理节点', 'MONITOR', 'stipulated clause'):
            self.assertFalse(located({'locator': locator}), locator)
        limit = {'kind': 'NUMERIC_LIMIT', 'locator': 'p3 Table 7', 'says': 'VF ≤ 0.35 V', 'limit': {'max': 0.35, 'unit': 'V'}}
        self.assertTrue(clause(limit))
        self.assertFalse(clause(dict(limit, says='见表 3 第 7 行')))   # a number in the text that is not the limit (E1)
        self.assertFalse(clause({'kind': 'TYPICAL_REFERENCE', 'locator': 'p4 功能框图', 'says': '电压环为内部跨导放大器'}))
        # merge plan §4 (E1): a qualitative mandatory clause is a clause without any number; a typical application is not
        unused = {'kind': 'MANDATORY_CLAUSE', 'locator': 'p12 §8.2', 'says': '未用的 EN 输入必须接地', 'applies': 'EN 不用时'}
        self.assertTrue(clause(unused))
        self.assertFalse(clause(dict(unused, locator='p20 典型应用')))
        self.assertFalse(clause(dict(unused, says='EN 输入通常接地')))

    def test_a_document_function_needs_no_clause(self):
        p, r, db = ledger(bias_function('PASS'))
        fn = {'id': 'FN-DOC', 'question': '计算书数值是否按实际工作点算', 'objects': {'refs': ['R1']},
              'conditions': [{'id': 'c1', 'kind': 'ENGINEERING_ASSUMPTION', 'source': 'evidence/calc-claims.json',
                              'locator': 'NOLOAD-R209-R211', 'says': '复算 70.4 mW，所称 35 mW', 'use': '文档数值判据'}],
              'no_calculation_reason': 'claims 已复算', 'verdict': 'PASS', 'open': [], 'fails': [], 'evidence': E}
        r['functions'].append(fn)
        r['checks'].append({'id': 'DOC-Q01.X', 'applicability': 'APPLICABLE', 'review_result': 'PASS', 'evidence': E,
                            'rationale': 'see FN-DOC', 'handoff': {'required': False}, 'function_id': 'FN-DOC', 'aspect': 'a'})
        fn['judgements'] = [{'aspect': 'a', 'conditions': ['c1'], 'says': '复算一致'}]
        p['checks'].append(planned('DOC-Q01.X'))
        r['plan_digest'] = fingerprint(p)
        errors = validate_functions(p, r, {c['id']: c for c in r['checks']})
        self.assertFalse(any('no clause carries' in e for e in errors), errors)
        self.assertTrue(any('rests on no mandatory clause or netlist fact' in e for e in errors), errors)   # F9 still

    def test_f9_a_judgement_rests_on_a_mandatory_clause_or_a_netlist_fact(self):
        fn = bias_function('PASS')
        fn['conditions'].append({'id': 'ENG', 'kind': 'ENGINEERING_ASSUMPTION', 'source': 'evidence/engineering.md',
                                 'locator': '## BIAS', 'says': '本轮推导', 'use': '见笔记'})
        fn['judgements'] = [{'aspect': 'X', 'conditions': ['ENG'], 'says': 'Q2 为源跟随'}]
        errors = function_errors({'functions': [fn]})
        self.assertTrue(any('judgements[0] (X): rests on no mandatory clause or netlist fact (ENG)' in e for e in errors), errors)
        fn['judgements'][0]['conditions'] = ['ENG', 'c5']   # the netlist fact with named nets carries it
        self.assertFalse(any('rests on no' in e for e in function_errors({'functions': [fn]})))
        fn['conditions'][4]['nets'] = []
        self.assertTrue(any('names the nets and/or pins' in e for e in function_errors({'functions': [fn]})))

    def test_f10_one_reason_sentence_on_several_items_is_a_hint_not_an_error(self):
        """Merge plan §3: the same reason on several gaps is a quality hint (they may be one gap); rewording passes no more
        than repeating does, because what is checked is each edge's path into the calculation."""
        from review_functions import template_hints
        fn = bias_function()
        fn['open'][0]['no_margin_reason'] = '该项实际配置或工作包络尚未确定'
        other = bias_function(); other['id'] = 'FN-HV'
        other['open'][0].update(key='HV-X', no_margin_reason='该项实际配置或工作包络尚未确定')
        self.assertFalse(any('the same no_margin_reason' in e for e in function_errors({'functions': [fn, other]})))
        hints = template_hints([fn, other])
        self.assertTrue(any(h['code'] == 'TEMPLATE_REASON' and h['field'] == 'no_margin_reason'
                            and h['items'] == ['FN-BIAS/AUX-5V-MIN', 'FN-HV/HV-X'] for h in hints), hints)
        self.assertTrue(any(h['code'] == 'TEMPLATE_REASON' and h['field'] == 'rationale' for h in hints), hints)
        other['open'][0]['no_margin_reason'] = 'HV 启动电流还没有定'
        other['open'][0]['decides'][0]['rationale'] = 'HV 启动电流进入 VCC 上升的计算'
        self.assertEqual(template_hints([fn, other]), [])

    def test_several_gaps_awaiting_one_document_of_one_part_are_a_hint(self):
        # Three items awaited the same coupling figure of one transformer, from one magnetics drawing, at P1, P1 and P3.
        from review_functions import template_hints

        def pending(fid, key, deliverable):
            fn = bias_function(); fn['id'] = fid
            fn['open'][0] = {'key': key, 'kind': 'DELIVERABLE_PENDING', 'deliverable_kind': 'CUSTOM_PART_DRAWING',
                             'deliverable': deliverable, 'decides': [{'aspect': ASPECT}]}
            return fn
        fns = [pending('FN-BIAS', 'T1-AUX', 'T1 辅助绕组对副边的漏感'), pending('FN-OVP', 'AUX-COUPLING', 'T1 辅助绕组耦合实测曲线')]
        hints = [h for h in template_hints(fns) if h['code'] == 'SAME_DELIVERABLE']
        self.assertEqual([(h['refs'], h['items']) for h in hints], [(['T1'], ['FN-BIAS/T1-AUX', 'FN-OVP/AUX-COUPLING'])])
        fns[1]['open'][0]['deliverable'] = 'L2 饱和电流'
        self.assertFalse([h for h in template_hints(fns) if h['code'] == 'SAME_DELIVERABLE'])
        fns[1]['open'][0]['deliverable'] = 'T1 辅助绕组耦合实测曲线'
        fns[0]['open'][0]['deliverable'] = fns[1]['open'][0]['deliverable'] = 'RT7209 配置表'   # a part number, not a part
        self.assertFalse([h for h in template_hints(fns, {'T1', 'U1'}) if h['code'] == 'SAME_DELIVERABLE'])

    def test_f10_one_unlocated_condition_in_several_functions_is_a_template(self):
        note = {'id': 'ENG', 'source': 'evidence/engineering.md', 'locator': '## X', 'says': '本轮原厂条款摘录', 'use': '依据'}
        fn = bias_function('PASS'); fn['conditions'].append(dict(note))
        other = bias_function('PASS'); other['id'] = 'FN-HV'; other['conditions'].append(dict(note))
        errors = function_errors({'functions': [fn, other]})
        self.assertTrue(any('FN-BIAS, FN-HV: the same unlocated condition' in e for e in errors), errors)
        # a located clause may be cited by two functions (the same VCC(off) limit bears on bias and start-up)
        fn['conditions'][-1] = dict(fn['conditions'][2]); other['conditions'][-1] = dict(fn['conditions'][2])
        self.assertFalse(any('unlocated condition' in e for e in function_errors({'functions': [fn, other]})))

    def test_f11_a_frame_function_judges_the_frame_objects(self):
        from test_derive_rows import bias_plan
        p, r, db = bias_plan()
        p['functions'][0]['objects'] = {'refs': ['Q2', 'D2', 'D3', 'C3'], 'nets': ['AUX', 'BIAS', 'VCC']}
        r['plan_digest'] = fingerprint(p)
        self.assertEqual([e for e in frame_errors(p, {c['id']: c for c in r['checks']}, r['functions']) if 'objects name' in e], [])
        r['functions'][0]['objects']['refs'].append('Q7')
        errors = frame_errors(p, {c['id']: c for c in r['checks']}, r['functions'])
        self.assertTrue(any('FN-BIAS: objects name Q7, which intent circuit BIAS does not list' in e for e in errors), errors)
        r['functions'][0]['objects']['refs'].pop()
        r['functions'][0]['objects']['nets'] = ['/05_Bias/AUX', 'BIAS', 'VCC']   # a sheet path is the same net
        self.assertEqual([e for e in frame_errors(p, {c['id']: c for c in r['checks']}, r['functions']) if 'objects name' in e], [])

    def test_f11_a_row_the_reviewer_binds_names_an_object_of_the_function(self):
        p, r, db = ledger(bias_function())
        p['checks'].append(dict(planned('DEV-C05.Q7'), object={'ref': 'Q7'}))
        r['checks'].append({'id': 'DEV-C05.Q7', 'applicability': 'APPLICABLE', 'review_result': 'INSUFFICIENT', 'evidence': E,
                            'rationale': 'see FN-BIAS', 'handoff': {'required': False}, 'function_id': 'FN-BIAS',
                            'aspect': ASPECT, 'open_ref': 'FN-BIAS/AUX-5V-MIN'})
        errors = frame_errors(p, {c['id']: c for c in r['checks']}, r['functions'])
        self.assertTrue(any('DEV-C05.Q7: bound to FN-BIAS, which is not about Q7' in e for e in errors), errors)
        p['checks'][-1]['object'] = {'ref': 'Q2'}
        self.assertFalse(any('bound to' in e for e in frame_errors(p, {c['id']: c for c in r['checks']}, r['functions'])))
        p['checks'][-1]['object'] = {'net': '/05_Bias/VCC'}   # a net row: the net, path stripped
        self.assertFalse(any('bound to' in e for e in frame_errors(p, {c['id']: c for c in r['checks']}, r['functions'])))
        p['checks'][-1]['object'] = {'net': 'VBUS'}
        self.assertTrue(any('not about net VBUS' in e for e in frame_errors(p, {c['id']: c for c in r['checks']}, r['functions'])))
        p['checks'][-1]['object'] = {'requirement_id': 'REQ-1'}   # no anchor: a requirement may lean on any function
        self.assertFalse(any('bound to' in e for e in frame_errors(p, {c['id']: c for c in r['checks']}, r['functions'])))

    def test_f11_an_inductive_load_row_belongs_where_its_inductor_is(self):
        # The freewheel loop of a boost inductor runs through the input and bulk capacitors of other blocks; binding
        # the row to the inductor's block was refused, so a reviewer made a second function and a duplicate gap.
        p, r, db = ledger(bias_function())
        loop = {'ref': 'D2', 'net': 'AUX', 'inductive_load': 'D2-AUX', 'inductive_load_digest': 'x',
                'application': 'boost_converter', 'refs': ['C9', 'D2', 'Q2'], 'nets': ['AUX', 'RECT', 'PGND']}
        p['checks'].append(dict(planned('DRV-C01.D2-AUX.AUX'), object=loop))
        r['checks'].append({'id': 'DRV-C01.D2-AUX.AUX', 'applicability': 'APPLICABLE', 'review_result': 'INSUFFICIENT',
                            'evidence': E, 'rationale': 'see FN-BIAS', 'handoff': {'required': False},
                            'function_id': 'FN-BIAS', 'aspect': ASPECT, 'open_ref': 'FN-BIAS/AUX-5V-MIN'})
        self.assertFalse(any('bound to' in e for e in frame_errors(p, {c['id']: c for c in r['checks']}, r['functions'])))
        p['checks'][-1]['object'] = dict(loop, ref='L9')
        self.assertTrue(any('not about L9' in e for e in frame_errors(p, {c['id']: c for c in r['checks']}, r['functions'])))

    def test_f12_a_connector_row_with_clamp_parts_is_judged_in_a_function(self):
        p, r, db = ledger(bias_function('PASS'))
        p['checks'].append(dict(planned('PRO-D03.J1'), object={'ref': 'J1'}, clamp_refs=['D7', 'D8']))
        row = {'id': 'PRO-D03.J1', 'applicability': 'APPLICABLE', 'review_result': 'PASS', 'evidence': E,
               'rationale': 'J1 CC/D± 各有一颗 TVS', 'handoff': {'required': False}}
        r['checks'].append(row)
        errors = frame_errors(p, {c['id']: c for c in r['checks']}, r['functions'])
        self.assertTrue(any('PRO-D03.J1: the plan lists clamp parts D7, D8' in e for e in errors), errors)
        row.update(review_result='NA', applicability='NOT_APPLICABLE')   # not reviewed: nothing to judge
        self.assertFalse(any('clamp parts' in e for e in frame_errors(p, {c['id']: c for c in r['checks']}, r['functions'])))



class EvidenceBasisTests(unittest.TestCase):
    """Merge plan of 2026-10-21 §4: what a margin proves comes from its basis, a comparison across regimes needs a
    conversion, and PASS and FAIL evidence over one scope is a conflict, not a choice by order."""

    def test_e4_ge_passes_at_zero_gt_does_not_and_a_margin_is_finite(self):
        from review_functions import margin_verdict
        m = {'value': 0, 'basis': guaranteed(comparison='GE')}
        self.assertEqual(margin_verdict(m), 'PASS')
        self.assertEqual(margin_verdict(dict(m, basis=guaranteed(comparison='GT'))), 'OPEN')
        self.assertEqual(margin_verdict(dict(m, basis=guaranteed(kind='EXACT_ENVELOPE', comparison='GT'))), 'FAIL')
        self.assertEqual(margin_verdict({'value': 5, 'basis': {'kind': 'ESTIMATE', 'comparison': 'GE'}}), 'OPEN')
        self.assertEqual(margin_verdict({'value': -5, 'basis': guaranteed(kind='REACHABLE_CASE')}), 'FAIL')
        self.assertEqual(margin_verdict({'value': 5, 'basis': guaranteed(kind='REACHABLE_CASE')}), 'OPEN')
        fn = bias_function('PASS'); fn['calculation']['margin']['value'] = float('nan')
        self.assertTrue(any('finite number' in e for e in function_errors({'functions': [fn]})))
        fn = bias_function('PASS'); fn['calculation']['margin']['basis']['comparison'] = 'GTE'
        self.assertTrue(any('comparison GE/GT' in e for e in function_errors({'functions': [fn]})))

    def test_kind_specific_fields_are_required(self):
        fn = bias_function('PASS'); fn['calculation']['margin']['basis']['kind'] = 'EXACT_ENVELOPE'
        self.assertTrue(any('model, domain' in e for e in function_errors({'functions': [fn]})))
        fn['calculation']['margin']['basis'].update(model='源跟随线性模型', domain='−10..105 °C、VF 与 VGS(th) 全范围',
                                                    extremum='VCC 随 VF、VGS(th) 单调下降，极值在两者上界')
        self.assertEqual(function_errors({'functions': [fn]}), [])
        fn = bias_function('PASS'); fn['calculation']['margin']['basis']['limit'] = 'c4'   # a clause, not a numeric limit
        self.assertTrue(any('names in basis.limit the NUMERIC_LIMIT' in e for e in function_errors({'functions': [fn]})))

    def test_a_guaranteed_bound_does_not_rest_on_typical_values_or_assumptions(self):
        fn = bias_function('PASS')
        fn['conditions'].append({'id': 'c6', 'kind': 'TYPICAL_REFERENCE', 'source': 'evidence/ds/Q2.txt', 'locator': 'Fig. 5',
                                 'says': 'VGS 典型 1.6 V', 'use': '典型'})
        fn['calculation']['margin']['basis']['conditions'].append('c6')
        errors = function_errors({'functions': [fn]})
        self.assertTrue(any('does not rest on typical values or assumptions (c6)' in e for e in errors), errors)

    def test_e5_a_comparison_across_regimes_needs_a_conversion(self):
        """An 8/20 µs clamp voltage against a static pin limit is not a decisive comparison by itself."""
        fn = bias_function('PASS'); fn['calculation']['margin']['basis']['regime'] = '8/20 µs 浪涌'
        errors = function_errors({'functions': [fn]})
        self.assertTrue(any('a decisive comparison across regimes names the conversion' in e for e in errors), errors)
        fn['calculation']['margin']['basis']['conversion'] = 'BIAS-VCCMIN'
        self.assertEqual(function_errors({'functions': [fn]}), [])
        fn = bias_function('PASS'); fn['calculation']['margin']['basis'].pop('regime')
        self.assertTrue(any('basis.regime says where' in e for e in function_errors({'functions': [fn]})))
        fn = bias_function('PASS'); fn['calculation']['margin']['basis'] = {'kind': 'ESTIMATE', 'comparison': 'GT',
                                                                           'conditions': ['c3'], 'scope': '浪涌'}
        fn['judgements'] = [{'aspect': ASPECT, 'conditions': ['c4'], 'says': '按连接要求', 'states': list(STATES)}]
        self.assertEqual(function_errors({'functions': [fn]}), [])   # an estimate claims nothing, so no conversion is asked

    def test_e7_pass_and_fail_over_one_scope_conflict_over_two_scopes_they_stand(self):
        fn = bias_function('FAIL')
        fn['fails'] = [{'key': 'VCC-LOW', 'finding_id': 'F1', 'what': 'VCC 低', 'conditions': ['c4'],
                        'decides': [{'aspect': ASPECT, 'states': ['RUN']}]}]
        fn['calculation']['margin']['states'] = list(STATES)
        errors = function_errors({'functions': [fn], 'findings': [{'id': 'F1'}]})
        self.assertTrue(any('EVIDENCE_CONFLICT' in e for e in errors), errors)
        fn['calculation']['margin']['states'] = ['STARTUP', 'LATCH']
        self.assertEqual(function_errors({'functions': [fn], 'findings': [{'id': 'F1'}]}), [])
        fn['calculation']['margin'] = [dict(fn['calculation']['margin'], states=['RUN']),
                                       dict(fn['calculation']['margin'], value=-0.3, states=['RUN'],
                                            basis=guaranteed(kind='REACHABLE_CASE', joint='满载高温同时出现'))]
        errors = function_errors({'functions': [fn], 'findings': [{'id': 'F1', 'remediation': {'readiness': 'READY'}}]})
        self.assertTrue(any('EVIDENCE_CONFLICT — margin -0.3 V' in e for e in errors), errors)

    def test_check_ids_narrow_an_entry_to_named_rows(self):
        fn = bias_function('PASS')
        fn['calculation']['margin']['check_ids'] = ['PWR-C02.BIAS-RUN.Q2']
        p, r, db = ledger(fn)
        errors = vr.validate_review(p, r, db)['errors']
        self.assertTrue(any('PWR-C02.BIAS-LATCH.Q2' in e and 'judges no' in e for e in errors), errors)
        self.assertFalse(any('PWR-C02.BIAS-RUN.Q2' in e for e in errors), errors)

    def test_a_netlist_fact_names_nets_the_netlist_has_by_their_full_path(self):
        from review_functions import _condition_errors
        fact = {'id': 'n1', 'kind': 'NETLIST_FACT', 'nets': ['TEMP'], 'pins': ['U1.3'], 'locator': 'net TEMP', 'says': 'x'}
        db = {'nets': {'/A/TEMP': ['U1.3'], '/B/TEMP': ['U2.3'], 'VCC': []}, 'pin2net': {'U1.3': '/A/TEMP'}}
        self.assertTrue(any('ambiguous' in e for e in _condition_errors('n1', fact, db)))
        self.assertEqual(_condition_errors('n1', dict(fact, nets=['/A/TEMP']), db), [])
        self.assertTrue(any('not in the netlist' in e for e in _condition_errors('n1', dict(fact, pins=['U9.1'], nets=['VCC']), db)))
        self.assertEqual(_condition_errors('n1', dict(fact, nets=['VCC'], pins=[]), {'nets': {'/P/VCC': []}}), [])

    def test_retired_fields_name_what_replaced_them(self):
        fn = bias_function(); fn['open'][0]['margin_not_decisive_reason'] = '按标称值算'
        self.assertTrue(any("margin_not_decisive_reason is retired; the margin's basis" in e
                            for e in function_errors({'functions': [fn]})))


if __name__ == '__main__':
    unittest.main()

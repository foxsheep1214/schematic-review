"""Synthetic counterexamples: ledger consistency is not semantic correctness."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_validate_review import fixture, planned, E
from validate_review import fingerprint, validate_review
from ledger4 import gap, severity
from review_workflow import workflow


def unfinished():
    p, r, db = fixture()
    gap(r, r['checks'][0]['id'], 'CALC', plan=p, what='Synthetic calculation not performed')
    return p, r, db


def staged(kind='REVIEW_INCOMPLETE', due='design_iteration', level='P2', **item):
    """One row open on task W-1 of `kind`, due at `due`."""
    p, r, db = fixture()
    p['review_phase'] = 'design_iteration'
    r['plan_digest'] = fingerprint(p)
    gap(r, r['checks'][0]['id'], 'W-1', kind, plan=p, level=level, title='Synthetic task',
        why='Synthetic independent input', due_stage=due, **dict({'what': 'Synthetic calculation not performed'}, **item))
    r['functions'][0]['evidence'] = E
    return p, r, db


def accepted_handoff(kind):
    p, r, db = staged(kind, 'prototype_verification', level='P1')
    p['checks'][0]['handoff'] = {'required': True}
    r['plan_digest'] = fingerprint(p)
    r['checks'][0]['handoff'] = {
        'required': True, 'state': 'ACCEPTED', 'scope': 'downstream_verification',
        'receivers': ['Synthetic PCB owner'], 'constraint': 'Controlled layout bound',
        'verification': 'Prototype measurement', 'evidence': E,
        'schematic_prerequisites': [r['checks'][1]['id']]}
    return p, r, db


class CompletionGuardTests(unittest.TestCase):
    def test_unfinished_p2_never_releases(self):
        p, r, db = unfinished()
        out = validate_review(p, r, db)
        self.assertTrue(out['valid'], out)  # an honest partial ledger is valid
        self.assertEqual(out['release'], 'NO_GO')
        self.assertTrue(any('review work not completed' in s for s in out['blockers']))

    def test_unfinished_is_not_risk_acceptance_at_any_severity(self):
        for level in ('P0', 'P1', 'P2', 'P3'):
            with self.subTest(level=level):
                p, r, db = unfinished()
                r['functions'][0]['open'][0]['severity'] = severity(level)
                r['checks'][0].update(disposition='ACCEPTED',
                    acceptance={k: 'synthetic record' for k in ('by', 'date', 'scope', 'reason', 'record')})
                self.assertEqual(validate_review(p, r, db)['release'], 'NO_GO')

    def test_unfinished_task_stays_in_current_round(self):
        p, r, db = staged()
        out = validate_review(p, r, db)
        self.assertTrue(out['valid'], out)
        self.assertEqual(out['workflow']['current_work_items'], ['W-1'])
        self.assertEqual(out['release'], 'NO_GO')

    def test_unfinished_task_cannot_be_deferred_to_freeze(self):
        p, r, db = staged(due='schematic_freeze')
        out = validate_review(p, r, db)
        self.assertFalse(out['valid'])
        self.assertTrue(any('unfinished review' in e for e in out['errors']))

    def test_explicit_electrical_gap_cannot_use_downstream_shortcut(self):
        for kind in ('VENDOR_DATUM', 'DESIGN_VALUE', 'REVIEW_INCOMPLETE', 'USER_DEFERRED'):
            with self.subTest(kind=kind):
                p, r, db = accepted_handoff(kind)
                out = validate_review(p, r, db)
                self.assertEqual(out['release'], 'NO_GO')

    def test_retired_downstream_gap_cause_is_rejected(self):
        # Pure downstream tests are stage NA (test_review_stage_scope); there is no INSUFFICIENT shortcut.
        p, r, db = accepted_handoff('REVIEW_INCOMPLETE')
        r['functions'][0]['open'][0]['kind'] = 'DOWNSTREAM_VERIFICATION'
        self.assertFalse(validate_review(p, r, db)['valid'])

    def test_screening_is_integrated_without_changing_release(self):
        p, r, db = fixture()
        out = validate_review(p, r, db)
        self.assertTrue(out['valid'], out)
        self.assertEqual(out['quality_screening']['status'], 'NO_PATTERN_DETECTED')
        self.assertEqual(out['release'], 'GO')

    def test_incomplete_remains_visible_in_existing_cause_counts(self):
        p, r, db = unfinished()
        out = validate_review(p, r, db)
        self.assertEqual(out['insufficient_by_cause']['REVIEW_INCOMPLETE'], 1)
        bad = validate_review(None, {})
        self.assertFalse(bad['valid'])
        self.assertEqual(bad['release'], 'NO_GO')


def quality_fixture():
    p = {'checks': [
        {'id': 'DEV-C01.C1', 'rule': 'DEV-C01', 'method': 'C',
         'object': {'ref': 'C1'}, 'criterion': 'C1 voltage rating'},
        {'id': 'DEV-C02.C2', 'rule': 'DEV-C02', 'method': 'C',
         'object': {'ref': 'C2'}, 'criterion': 'C2 ripple qualification'}]}
    r = {'checks': [
        {'id': c['id'], 'review_result': 'INSUFFICIENT',
         'rationale': 'A shared generic paragraph; prototype thermal data absent.',
         'evidence': E} for c in p['checks']]}
    return p, r, {'parts': {'C1': {}, 'C2': {}, 'R1': {}}}


class QualityScreeningTests(unittest.TestCase):
    def setUp(self):
        from review_quality import screen_quality
        self.screen = screen_quality

    def test_rows_bound_to_one_function_may_share_its_rationale(self):
        p, r, db = quality_fixture()
        for row in r['checks']:
            row.update(function_id='FN-CAPS', aspect='rating')
        self.assertNotIn('REUSED_RATIONALE_ACROSS_SCOPES', [c['code'] for c in self.screen(p, r, db)['candidates']])

    def test_cross_criterion_copy_is_visible_without_electrical_verdict(self):
        p, r, db = quality_fixture(); before = deepcopy((p, r, db))
        out = self.screen(p, r, db)
        self.assertEqual(out['status'], 'NEEDS_SEMANTIC_REVIEW')
        self.assertEqual(out['candidates'][0]['code'], 'REUSED_RATIONALE_ACROSS_SCOPES')
        self.assertEqual(set(out['candidates'][0]['check_ids']), {c['id'] for c in p['checks']})
        self.assertEqual((p, r, db), before)
        self.assertNotIn('release', out)

    def test_same_shared_source_with_distinct_reasons_is_not_flagged(self):
        p, r, db = quality_fixture()
        r['checks'][0]['rationale'] = 'C1 rating exceeds its bounded DC voltage.'
        r['checks'][1]['rationale'] = 'C2 ripple requires the measured frequency spectrum.'
        self.assertEqual(self.screen(p, r, db)['status'], 'NO_PATTERN_DETECTED')

    def test_wrong_explicit_ref_in_rationale_is_candidate(self):
        p, r, db = quality_fixture(); r['checks'] = r['checks'][:1]
        r['checks'][0]['rationale'] = 'C2 ripple specification proves this result.'
        self.assertIn('REFERENCED_OBJECT_OUTSIDE_SCOPE', [x['code'] for x in self.screen(p, r, db)['candidates']])

    def test_a_function_bound_row_may_name_the_functions_other_parts(self):
        # R7 acceptance 2026-10-25: after the pre-binding a device row judged in its circuit's function cites the
        # circuit's other parts; the function's objects are its scope
        p, r, db = quality_fixture(); r['checks'] = r['checks'][:1]
        p['functions'] = [{'id': 'FN-CAPS', 'objects': {'refs': ['C1', 'C2']}}]
        r['checks'][0].update(function_id='FN-CAPS', rationale='C2 ripple specification proves this result.')
        self.assertNotIn('REFERENCED_OBJECT_OUTSIDE_SCOPE', [x['code'] for x in self.screen(p, r, db)['candidates']])
        r['checks'][0]['rationale'] = 'R1 ripple specification proves this result.'
        self.assertIn('REFERENCED_OBJECT_OUTSIDE_SCOPE', [x['code'] for x in self.screen(p, r, db)['candidates']])

    def test_wrong_explicit_ref_in_evidence_locator_is_candidate(self):
        p, r, db = quality_fixture(); r['checks'] = r['checks'][:1]
        r['checks'][0].update(rationale='The component has the required rating.',
                             evidence=[{'source': 'synthetic-ledger.json', 'locator': 'refs.C2'}])
        self.assertEqual(self.screen(p, r, db)['candidates'][0]['observed_refs'], ['C2'])

    def test_dependency_refs_are_not_assumed_wrong(self):
        p, r, db = quality_fixture(); r['checks'] = r['checks'][:1]
        p['checks'][0]['object']['refs'] = ['C1', 'R1']
        r['checks'][0]['rationale'] = 'R1 bounds the charging current.'
        self.assertEqual(self.screen(p, r, db)['status'], 'NO_PATTERN_DETECTED')

    def test_requirement_criterion_can_supply_scope(self):
        p, r, db = quality_fixture(); r['checks'] = r['checks'][:1]
        p['checks'][0]['object'] = {'requirement_id': 'REQ-LIFE'}
        p['checks'][0]['criterion'] = 'C1寿命须覆盖任务剖面'
        r['checks'][0]['rationale'] = 'C2满足所需寿命。'
        self.assertEqual(self.screen(p, r, db)['candidates'][0]['expected_refs'], ['C1'])

    def test_ref_prefix_and_units_do_not_create_false_matches(self):
        p, r, db = quality_fixture(); r['checks'] = r['checks'][:1]
        r['checks'][0]['rationale'] = '100V; Rev.C2X, model_C2, C20 are not C2 references.'
        # Remove the deliberate final reference; partial tokens must not match C2.
        r['checks'][0]['rationale'] = r['checks'][0]['rationale'].split(' are not')[0]
        self.assertEqual(self.screen(p, r, db)['status'], 'NO_PATTERN_DETECTED')

    def test_q_and_history_boilerplate_are_excluded(self):
        p, r, db = quality_fixture()
        for i, c in enumerate(p['checks']):
            c['method'] = ('Q', 'H')[i]
        self.assertEqual(self.screen(p, r, db)['candidates'], [])

    def test_unknown_db_refs_are_not_invented(self):
        p, r, _ = quality_fixture(); r['checks'] = r['checks'][:1]
        r['checks'][0]['rationale'] = 'C2 data are cited.'
        self.assertEqual(self.screen(p, r, None)['status'], 'NO_PATTERN_DETECTED')

    def test_stable_output_and_malformed_rows_are_safe(self):
        p, r, db = quality_fixture()
        out = self.screen(p, r, db)
        p['checks'].reverse(); r['checks'].reverse()
        self.assertEqual(out, self.screen(p, r, db))
        self.assertEqual(self.screen(None, None)['status'], 'NOT_RUN')
        self.assertEqual(self.screen({'checks': [None]}, {'checks': [None]}, {})['candidates'], [])


def impact_fixture(n=12, grade='P1', text='Shared consequence for every row'):
    keys = [f'PWR-C02.N{i}' for i in range(n)]
    p = {'checks': [{'id': k, 'rule': 'PWR-C02', 'method': 'C', 'object': {'net': f'N{i}'},
                     'criterion': 'output window'} for i, k in enumerate(keys)]}
    r = {'checks': [{'id': k, 'review_result': 'INSUFFICIENT', 'gap_cause': 'EXTERNAL_DATA',
                     'potential_severity': grade, 'rationale': f'net N{i} lacks a bound',
                     'impact_assessment': {'consequence': text, 'severity_reason': f'path for N{i}'},
                     'evidence': E} for i, k in enumerate(keys)]}
    return p, r


class ImpactScreeningTests(unittest.TestCase):
    def setUp(self):
        from review_quality import screen_quality
        self.screen = screen_quality

    def codes(self, p, r):
        return {x['code'] for x in self.screen(p, r)['candidates']}

    def test_copied_consequence_and_uniform_grade_are_flagged(self):
        p, r = impact_fixture()
        self.assertEqual({'REUSED_IMPACT_ACROSS_SCOPES', 'UNIFORM_POTENTIAL_SEVERITY',
                          'UNIFORM_SEVERITY_WITHIN_RULE'}, self.codes(p, r))

    def test_templated_grade_sentence_across_rules_is_flagged(self):
        p, r = impact_fixture()
        rules = ('DEV-C01', 'PWR-C10', 'DRV-C02')
        for i, (c, row) in enumerate(zip(p['checks'], r['checks'])):
            c['rule'] = rules[i % 3]
            row['potential_severity'] = ('P1', 'P2')[i % 2]
            # schema 3: the consequence is also the grade's reason
            row['impact_assessment']['consequence'] = f'N{i} path。本行未建立独立损坏路径，按必需性能P1。'
        found = [x for x in self.screen(p, r)['candidates'] if x['code'] == 'TEMPLATED_SEVERITY_REASON']
        self.assertEqual(1, len(found))
        self.assertEqual(12, len(found[0]['check_ids']))
        for i, row in enumerate(r['checks']):
            row['impact_assessment']['consequence'] = f'N{i} 漏电经R{i}使门限偏移，按P1。'
        self.assertNotIn('TEMPLATED_SEVERITY_REASON', self.codes(p, r))

    def test_distinct_paths_and_mixed_grades_are_not_flagged(self):
        p, r = impact_fixture()
        for i, row in enumerate(r['checks']):
            row['impact_assessment']['consequence'] = f'N{i} consequence'
            row['potential_severity'] = ('P1', 'P2')[i % 2]
        self.assertEqual(set(), self.codes(p, r))

    def test_small_ledgers_and_history_rows_are_ignored(self):
        p, r = impact_fixture(n=5, text='x')
        for i, row in enumerate(r['checks']):
            row['impact_assessment']['consequence'] = f'N{i}'
        self.assertEqual(set(), self.codes(p, r))
        p, r = impact_fixture()
        for c in p['checks']:
            c['rule'] = 'REQ-H02'
        self.assertNotIn('UNIFORM_POTENTIAL_SEVERITY', self.codes(p, r))

class WorkItemAndTextHygieneTests(unittest.TestCase):
    def setUp(self):
        from review_quality import screen_quality
        self.screen = screen_quality

    def codes(self, p, r, db=None):
        return {x['code'] for x in self.screen(p, r, db)['candidates']}

    def p0_item(self):
        p, r = impact_fixture(n=3)
        for i, row in enumerate(r['checks']):
            row['impact_assessment'].update(consequence=f'N{i} consequence', hazard_path='FIRE')
            row['potential_severity'] = 'P0'
        r['work_items'] = [{'id': 'W-1', 'check_ids': [c['id'] for c in p['checks']]}]
        return p, r

    def test_shared_consequence_inside_one_work_item_is_the_task_not_a_copy(self):
        p, r = impact_fixture()
        ids = [c['id'] for c in p['checks']]
        r['work_items'] = [{'id': 'W-1', 'check_ids': ids}]
        self.assertNotIn('REUSED_IMPACT_ACROSS_SCOPES', self.codes(p, r))
        r['work_items'] = [{'id': 'W-1', 'check_ids': ids[:6]}, {'id': 'W-2', 'check_ids': ids[6:]}]
        self.assertIn('REUSED_IMPACT_ACROSS_SCOPES', self.codes(p, r))

    def test_glued_refs_sample_values_and_unlooked_requests_are_flagged(self):
        p, r = impact_fixture(n=3)
        for i, row in enumerate(r['checks']):
            row['impact_assessment']['consequence'] = f'N{i} consequence'
        db = {'parts': {'R12': {}, 'U11': {}, 'R1': {}}}
        row = r['checks'][0]
        row['input_requests'] = {'fuse clearing': {
            'why_decisive': 'x', 'required_scope': 'R12100°C',
            'acquisition': '向保险丝厂家取得所选料号总清除能力', 'closure_criterion': '注入预算257.121uA以下'}}
        r['work_items'] = [{'id': 'W-1', 'check_ids': [row['id']], 'reason': 'U116.5V直流额定'}]
        out = {x['code']: x for x in self.screen(p, r, db)['candidates']}
        self.assertEqual({'REF_GLUED_TO_VALUE', 'OVERPRECISE_CLOSURE_VALUE'}, set(out))
        glued = [x for x in self.screen(p, r, db)['candidates'] if x['code'] == 'REF_GLUED_TO_VALUE']
        self.assertEqual({('W-1', 'U11'), ('', 'R12')},
                         {((x['task_ids'] or [''])[0], x['refs'][0]) for x in glued})
        self.assertEqual(['257.121'], out['OVERPRECISE_CLOSURE_VALUE']['values'])
        q = row['input_requests']['fuse clearing']
        q.update(required_scope='R12 100°C', closure_criterion='注入预算低于手册上限',
                 acquisition='保险丝规格书 p.2 只给额定分断电流，向厂家取得总清除 I²t')
        r['work_items'][0]['reason'] = 'U11 6.5V 直流额定；R12 与 R1 各自标注'
        self.assertEqual(set(), self.codes(p, r, db))


    def test_glued_refs_in_function_text_are_flagged(self):
        # The report's function table and work items read "R4034.7k", "C40347u": the reviewer wrote them in the function
        # verdicts, which the screen did not read.
        p, r = impact_fixture(n=1)
        db = {'parts': {'R12': {}, 'C3': {}, 'U1': {}}}
        r['functions'] = [{'id': 'FN-A', 'question': 'U1 偏置', 'calculation': {'result': 'R124.7k 时 0.1 W'},
                           'open': [{'key': 'K', 'what': 'C347u 的寿命', 'decides': [{'rationale': 'U1 停止'}]}],
                           'fails': [{'key': 'F', 'what': 'U1 门限'}]}]
        glued = [x for x in self.screen(p, r, db)['candidates'] if x['code'] == 'REF_GLUED_TO_VALUE' and x['function_ids']]
        self.assertEqual({('FN-A', 'calculation.result', 'R12'), ('FN-A', 'open[K].what', 'C3')},
                         {(x['function_ids'][0], x['field'], x['refs'][0]) for x in glued})
        r['functions'][0]['calculation']['result'] = 'R12 4.7k 时 0.1 W'
        r['functions'][0]['open'][0]['what'] = 'C3 47u 的寿命'
        self.assertFalse([x for x in self.screen(p, r, db)['candidates'] if x['code'] == 'REF_GLUED_TO_VALUE'])


class RequestOwnershipAndWordingTests(unittest.TestCase):
    def setUp(self):
        from review_quality import screen_quality
        self.screen = screen_quality

    def found(self, p, r, code):
        return [x for x in self.screen(p, r)['candidates'] if x['code'] == code]

    def test_port_overvoltage_text_graded_as_component_damage_is_flagged(self):
        p, r = impact_fixture(n=3)
        for i, row in enumerate(r['checks']):
            row['impact_assessment']['consequence'] = f'N{i} consequence'
        row = r['checks'][0]
        row['impact_assessment'].update(consequence='约定过压可使端口负载损坏', consequence_class='COMPONENT_DAMAGE')
        self.assertEqual([row['id']], self.found(p, r, 'PORT_OVERVOLTAGE_GRADED_BELOW_P0')[0]['check_ids'])
        row['impact_assessment'].update(consequence_class='DAMAGE_OR_HAZARD', hazard_path='PORT_OVERVOLTAGE',
                                        exclusion='U11 锁定式 OVP，门限见 DS01 p12')
        self.assertEqual([], self.found(p, r, 'PORT_OVERVOLTAGE_GRADED_BELOW_P0'))
        # A negated or hand-over sentence is not an assertion of the path.
        row['impact_assessment'].update(consequence_class='COMPONENT_DAMAGE', hazard_path=None,
                                        consequence='Q5 可能损坏；未据此推断火灾、触电或端口过压')
        self.assertEqual([], self.found(p, r, 'PORT_OVERVOLTAGE_GRADED_BELOW_P0'))
        row['impact_assessment']['consequence'] = 'Q5 可能损坏；端口过压另由 W-PORT-OV 单独核'
        self.assertEqual([], self.found(p, r, 'PORT_OVERVOLTAGE_GRADED_BELOW_P0'))

    def test_scope_echoing_the_task_and_templated_handoffs_are_flagged(self):
        p, r = impact_fixture(n=4)
        for i, row in enumerate(r['checks']):
            row['impact_assessment']['consequence'] = f'N{i} consequence'
        row = r['checks'][0]
        row['input_requests'] = {'k': {'why_decisive': 'w', 'required_scope': 'F1 分断；100A 尚未配对',
                                       'acquisition': 'a', 'closure_criterion': 'c'}}
        r['work_items'] = [{'id': 'W-1', 'title': 'F1 分断', 'root_cause': '100A 尚未配对', 'check_ids': [row['id']]}]
        self.assertEqual([row['id']], self.found(p, r, 'REQUEST_SCOPE_ECHOES_TASK')[0]['check_ids'])
        row['input_requests']['k']['required_scope'] = '90–264Vac、冷/热重插'
        self.assertEqual([], self.found(p, r, 'REQUEST_SCOPE_ECHOES_TASK'))
        for c in r['checks'][1:]:
            c['handoff'] = {'required': True, 'receivers': ['样机验证'],
                            'constraint': f"执行{c['id']}原文及其全部工况。", 'verification': f'按 {c["id"]} 验收'}
        hit = self.found(p, r, 'TEMPLATED_HANDOFF')
        self.assertEqual({'constraint', 'verification'}, {x['field'] for x in hit})
        self.assertEqual(3, len(hit[0]['check_ids']))
        for i, c in enumerate(r['checks'][1:]):
            c['handoff']['constraint'] = f'闭壳 {40 + i}°C 测热点'
            c['handoff']['verification'] = f'记录第 {i} 组数据'
        self.assertEqual([], self.found(p, r, 'TEMPLATED_HANDOFF'))


class StageCauseAndDuplicateTests(unittest.TestCase):
    def setUp(self):
        from review_quality import screen_quality
        self.screen = screen_quality

    def found(self, p, r, code, db=None):
        return [x for x in self.screen(p, r, db)['candidates'] if x['code'] == code]

    def rows(self, n=3):
        p, r = impact_fixture(n=n)
        for i, row in enumerate(r['checks']):
            row['impact_assessment']['consequence'] = f'N{i} consequence'
        return p, r

    def test_burned_image_gap_is_a_firmware_handoff_lead(self):
        p, r = self.rows()
        row = r['checks'][0]
        row.update(gap_cause='EXTERNAL_DATA', missing_inputs=['准确应用版本的烧录镜像与读回 hash'])
        self.assertEqual([row['id']], self.found(p, r, 'FIRMWARE_IMAGE_RECORDED_AS_DESIGN_GAP')[0]['check_ids'])
        row['missing_inputs'] = ['TP602 与 PFC_EN_N 共脚的编程接口电平与上拉']
        self.assertEqual([], self.found(p, r, 'FIRMWARE_IMAGE_RECORDED_AS_DESIGN_GAP'))

    def test_read_then_calculate_is_not_an_external_data_gap(self):
        p, r = self.rows()
        row = r['checks'][0]
        row['input_requests'] = {'C201 全模式纹波': {
            'why_decisive': 'w', 'required_scope': '90–264Vac',
            'acquisition': '已读 Rubycon BXW p1,p5；按低线跟随模式复算频谱并折算到 120Hz', 'closure_criterion': 'c'}}
        hit = self.found(p, r, 'CALCULATION_RECORDED_AS_DATA_GAP')
        self.assertEqual([row['id']], hit[0]['check_ids'])
        row['input_requests']['C201 全模式纹波']['acquisition'] = '已读 Rubycon BXW p1,p5，只给 120Hz 系数，缺 100kHz 以上折算；向 Rubycon 索取'
        self.assertEqual([], self.found(p, r, 'CALCULATION_RECORDED_AS_DATA_GAP'))

    def test_same_method_on_three_optocouplers_is_one_item(self):
        p, r = self.rows()
        db = {'parts': {'U2': {}, 'U3': {}, 'U4': {}}}
        r['work_items'] = [
            {'id': f'W-{ref}', 'check_ids': [c['id']],
             'next_action': f'按 {ref} 的实际 LED 电流取厂家适用 CTR 与退化界限，并算接收端最大负载 {n}µA'}
            for ref, n, c in zip(('U2', 'U3', 'U4'), (47, 1520, 277), r['checks'])]
        hit = self.found(p, r, 'DUPLICATE_WORK_ITEMS', db)
        self.assertEqual(['W-U2', 'W-U3', 'W-U4'], hit[0]['task_ids'])
        r['work_items'][0]['next_action'] = '改用 U2 的另一路 GPIO 直驱 DIS，去掉光耦'
        self.assertEqual(['W-U3', 'W-U4'], self.found(p, r, 'DUPLICATE_WORK_ITEMS', db)[0]['task_ids'])


class DownstreamTriageTests(unittest.TestCase):
    def codes(self, p, r):
        return self.by_code(p, r)

    def by_code(self, p, r, db=None):
        from review_quality import screen_quality
        return {x['code']: x for x in screen_quality(p, r, db)['candidates']}

    def test_test_only_gap_recorded_as_a_data_gap_is_flagged(self):
        p, r = impact_fixture(n=2)
        r['checks'][0]['gap_cause'] = 'EXTERNAL_DATA'
        r['checks'][0]['missing_inputs'] = ['闭壳温升与EMC传导实测结果']
        r['checks'][1]['gap_cause'] = 'EXTERNAL_DATA'
        r['checks'][1]['missing_inputs'] = ['U1 厂家给出偏置电流的保证值']
        found = self.codes(p, r)['DOWNSTREAM_RECORDED_AS_DESIGN_GAP']
        self.assertEqual([r['checks'][0]['id']], found['check_ids'])
        r['checks'][0].update(derived=True, open_ref='FN-X/GAP')     # its gap is the open item's: downstream_closures reads it
        self.assertNotIn('DOWNSTREAM_RECORDED_AS_DESIGN_GAP', self.codes(p, r))

    def test_an_open_item_and_its_derived_rows_grade_once(self):
        # 4.3: derived rows inherit the open item's grade, so twelve rows of one item are one graded gap
        p, r = impact_fixture(n=12)
        self.assertIn('UNIFORM_POTENTIAL_SEVERITY', self.codes(p, r))
        self.assertIn('UNIFORM_SEVERITY_WITHIN_RULE', self.codes(p, r))
        for row in r['checks']:
            row.update(derived=True, open_ref='FN-X/GAP')
        self.assertNotIn('UNIFORM_POTENTIAL_SEVERITY', self.codes(p, r))
        self.assertNotIn('UNIFORM_SEVERITY_WITHIN_RULE', self.codes(p, r))
        for i, row in enumerate(r['checks']):
            row['open_ref'] = 'FN-X/GAP-%d' % i                       # twelve items, one grade each
        found = self.by_code(p, r)['UNIFORM_POTENTIAL_SEVERITY']
        self.assertEqual(len(found['check_ids']), 12)
        self.assertIn('count once', found['message'])

    def test_the_uniform_share_counts_gaps_not_rows(self):
        p, r = impact_fixture(n=30)
        for i, row in enumerate(r['checks']):
            if i < 20:
                row.update(derived=True, open_ref='FN-X/BIG', potential_severity='P1')   # one gap behind twenty rows
            else:
                row.update(derived=True, open_ref='FN-X/GAP-%d' % i, potential_severity='P2' if i < 25 else 'P3')
        self.assertNotIn('UNIFORM_POTENTIAL_SEVERITY', self.codes(p, r))   # 1 / 5 / 5 of 11 gaps: no grade dominates

    def test_derived_rows_skip_the_row_text_screens(self):
        p, r = impact_fixture(n=2)
        p['checks'][0]['object'] = {'ref': 'C1'}
        row = r['checks'][0]
        row['evidence'] = [{'source': 'review-results.json', 'locator': 'checks'}]
        row['rationale'] = 'R1 limits the current'                   # R1 is known but outside C1's scope
        row['impact_assessment']['consequence'] = 'R1 overheats'
        db = {'parts': {'R1': {}, 'C1': {}}}
        codes = self.by_code(p, r, db)
        for code in ('CURRENT_CHECK_CITES_REVIEW_RECORD', 'REFERENCED_OBJECT_OUTSIDE_SCOPE', 'IMPACT_REFERENCES_OUTSIDE_SCOPE'):
            self.assertIn(code, codes, code)
        row.update(derived=True, open_ref='FN-X/GAP')                 # tool text written from the open item
        codes = self.by_code(p, r, db)
        for code in ('CURRENT_CHECK_CITES_REVIEW_RECORD', 'REFERENCED_OBJECT_OUTSIDE_SCOPE', 'IMPACT_REFERENCES_OUTSIDE_SCOPE'):
            self.assertNotIn(code, codes, code)

    def test_a_derived_timing_block_is_judged_on_its_open_item_once(self):
        p, r = impact_fixture(n=3)
        for row in r['checks']:
            row.update(rationale='关断响应在全温下未定', derived=True, open_ref='FN-X/T-OFF', blocking=True)
        found = self.by_code(p, r)['TIMING_BLOCK_WITHOUT_WINDOW']
        self.assertEqual((found['function_id'], found['key'], len(found['check_ids'])), ('FN-X', 'T-OFF', 3))
        r['functions'] = [{'id': 'FN-X', 'open': [{'key': 'T-OFF', 'kind': 'VENDOR_DATUM', 'scenario': '输出短路',
                                                     'allowed_window': '≤ 10 ms', 'response_bound': '≤ 2 ms'}]}]
        self.assertNotIn('TIMING_BLOCK_WITHOUT_WINDOW', self.codes(p, r))

    def test_optimization_goal_graded_p1_is_flagged(self):
        p, r = impact_fixture(n=2)
        p['checks'][0]['criterion'] = '万台物料成本优化目标60元'
        self.assertEqual([r['checks'][0]['id']], self.codes(p, r)['OPTIMIZATION_TARGET_AS_BLOCKING_GAP']['check_ids'])
        r['checks'][0]['potential_severity'] = 'P3'
        self.assertNotIn('OPTIMIZATION_TARGET_AS_BLOCKING_GAP', self.codes(p, r))


class FreezeGradingGateTests(unittest.TestCase):
    """Templated grading blocks release only in schematic_freeze; valid is unaffected."""

    def gate(self, phase, code='TEMPLATED_SEVERITY_REASON'):
        from unittest import mock
        import validate_review as vr
        from test_passive_stress import board, proposals
        from test_decoupling import ledger
        db, intent = board()
        if phase:
            intent['review_phase'] = phase
        plan, _ = proposals(db, intent)
        flagged = {'code': code, 'check_ids': ['X'] * 12}
        fake = lambda *a, **k: {'candidates': [flagged]}
        with mock.patch.object(vr, 'screen_quality', fake):
            return vr.validate_review(plan, ledger(plan, db), db)

    def test_freeze_blocks_and_iteration_does_not(self):
        freeze = self.gate('schematic_freeze')
        self.assertTrue(any(b.startswith('TEMPLATED_SEVERITY_REASON') for b in freeze['blockers']))
        iteration = self.gate('design_iteration')
        self.assertFalse(any(b.startswith('TEMPLATED_SEVERITY_REASON') for b in iteration['blockers']))

    def test_a_templated_pass_blocks_freeze_and_says_what_to_write(self):
        freeze = self.gate('schematic_freeze', 'TEMPLATED_PASS_RATIONALE')
        blocker = next(b for b in freeze['blockers'] if b.startswith('TEMPLATED_PASS_RATIONALE'))
        self.assertIn('PASS rows', blocker)
        self.assertFalse(any(b.startswith('TEMPLATED_PASS_RATIONALE')
                             for b in self.gate('design_iteration', 'TEMPLATED_PASS_RATIONALE')['blockers']))



def task_text_fixture(shared=True):
    """Four single-check tasks whose requests and NONE reasons are one template."""
    p = {'checks': [{'id': f'DEV-C01.R{i}', 'rule': 'DEV-C01', 'method': 'C', 'object': {'ref': f'R{i}'},
                     'criterion': f'R{i} rating'} for i in range(1, 5)]}
    rows, tasks = [], []
    for i in range(1, 5):
        key = f'R{i} pulse rating table'
        acquisition = '设计方结合原厂技术支持建立受控范围。' if shared else f'向R{i}供应商索取脉冲曲线第{i}页。'
        reason = f'当前缺口是{key}；未取得该范围前无法证明某个替换值能关闭此条件。' if shared else \
            f'R{i}换更大功率封装会超出板位{i}mm，改值会使门限偏移；先取得曲线。'
        rows.append({'id': f'DEV-C01.R{i}', 'review_result': 'INSUFFICIENT', 'rationale': f'R{i} pulse data missing.',
                     'missing_inputs': [key], 'input_requests': {key: {'acquisition': acquisition}}})
        tasks.append({'id': f'W{i}', 'check_ids': [f'DEV-C01.R{i}'],
                      'design_option': {'status': 'NONE', 'reason': reason, 'evidence': E}})
    return p, {'checks': rows, 'work_items': tasks}


class TaskTextTemplateTests(unittest.TestCase):
    def codes(self, p, r):
        from review_quality import screen_quality
        return {c['code']: c for c in screen_quality(p, r)['candidates']}

    def test_shared_acquisition_and_none_reason_are_flagged_with_their_tasks(self):
        found = self.codes(*task_text_fixture())
        self.assertEqual(found['BOILERPLATE_ACQUISITION']['task_ids'], ['W1', 'W2', 'W3', 'W4'])
        self.assertEqual(len(found['BOILERPLATE_ACQUISITION']['check_ids']), 4)
        templated = found['TEMPLATED_DESIGN_OPTION_REASON']
        self.assertEqual(templated['task_ids'], ['W1', 'W2', 'W3', 'W4'])
        self.assertNotIn('R1 pulse rating table', templated['template'])

    def test_task_specific_text_is_not_flagged(self):
        found = self.codes(*task_text_fixture(shared=False))
        self.assertNotIn('BOILERPLATE_ACQUISITION', found)
        self.assertNotIn('TEMPLATED_DESIGN_OPTION_REASON', found)

    def test_two_tasks_sharing_text_stay_below_threshold(self):
        p, r = task_text_fixture()
        r['work_items'] = r['work_items'][:2]; r['checks'] = r['checks'][:2]; p['checks'] = p['checks'][:2]
        self.assertNotIn('TEMPLATED_DESIGN_OPTION_REASON', self.codes(p, r))

    def test_report_conclusion_names_the_screen_without_changing_counts(self):
        from test_render_and_pack import body
        from test_check_explanations import synthetic
        from render_report import render
        p, r = synthetic(['FAIL', 'INSUFFICIENT'])
        plain = render(p, r, {'valid': True})
        self.assertNotIn('审查记录自检有', plain)
        self.assertIn('| 审查记录自检提示（不计入结论，分类见“对 SR 的反馈”） | 0 |', plain)
        gate = {'valid': True, 'quality_screening': {'candidates': [
            {'code': 'REUSED_RATIONALE_ACROSS_SCOPES', 'check_ids': ['a', 'b']},
            {'code': 'BOILERPLATE_ACQUISITION', 'check_ids': ['b']}]}}
        text = render(p, r, gate)
        # The reader's part does not mention the prompts; the count table counts them, the SR section names them.
        self.assertNotIn('审查记录自检', body(text).split('## 发现的错误')[0])
        self.assertNotIn('REUSED_RATIONALE_ACROSS_SCOPES', body(text))
        self.assertIn('| 审查记录自检提示（不计入结论，分类见“对 SR 的反馈”） | 2 |', text)
        self.assertIn('2 条，只要求复核写法和依据，不改变结论：REUSED_RATIONALE_ACROSS_SCOPES 1、BOILERPLATE_ACQUISITION 1。',
                      text.split('## 对 SR 的反馈')[1])
        self.assertEqual(body(plain).replace('| 0 |', ''), body(text).replace('| 2 |', ''))   # prompts change no count



class HistoryReconciliationTests(unittest.TestCase):
    """真实反例：声明了上一版审查，报告却显示 0 条处理记录，2 条旧问题的对照只在旁路文件里。"""

    def codes(self, p, r):
        from review_quality import screen_quality
        return {x['code']: x for x in screen_quality(p, r)['candidates']}

    def test_declared_earlier_findings_without_history_rows_are_flagged(self):
        import json
        import tempfile
        p, r, db = fixture()
        p['review_mode'] = 'revision'
        with tempfile.TemporaryDirectory() as tmp:
            record = Path(tmp) / 'record'
            record.mkdir()
            results = record / 'review-results.json'
            results.write_text(json.dumps({'findings': [{'id': 'F-OLD', 'kind': 'DEFECT'}]}), encoding='utf-8')
            r['history_inputs'] = [tmp]
            p['review_mode'] = 'first'   # a first review cannot hold REQ-H02 rows, so nothing to ask for
            self.assertNotIn('HISTORY_FINDINGS_UNRECONCILED', self.codes(p, r))
            p['review_mode'] = 'revision'
            hit = self.codes(p, r)['HISTORY_FINDINGS_UNRECONCILED']
            self.assertEqual((hit['finding_ids'], hit['source']), (['F-OLD'], str(results)))
            p['checks'].append(planned('REQ-H02.F-OLD'))
            r['checks'].append({**r['checks'][0], 'id': 'REQ-H02.F-OLD'})
            self.assertNotIn('HISTORY_FINDINGS_UNRECONCILED', self.codes(p, r))
            p['checks'].pop()
            r['checks'].pop()
            results.write_text('{"findings": []}', encoding='utf-8')
            self.assertNotIn('HISTORY_FINDINGS_UNRECONCILED', self.codes(p, r))
            r['history_inputs'] = [tmp + '/missing']
            self.assertNotIn('HISTORY_FINDINGS_UNRECONCILED', self.codes(p, r))


class TemplatedPassTests(unittest.TestCase):
    """A PASS whose reasoning is a paragraph about something else: on one board a drawing-consistency paragraph closed
    50 rows of different rules, the GPIO sink-current row among them, behind a "see function" prefix and an object echo
    that kept the reuse screen from seeing it."""

    BOILER = '图纸 p1 系统框图与 p2..p8 实电路相符；图框均 R5，所有器件和物理端点另见逐脚表，未发现图面重叠导致功能脚混读。'

    def rows(self, *specs):
        report = {'checks': [{'id': cid, 'review_result': result, 'rationale': text} for cid, result, text in specs]}
        expected = {cid: {'rule': cid.split('.')[0]} for cid, _, _ in specs}
        from review_quality import templated_pass_rationale
        return templated_pass_rationale(report, expected)

    def test_one_paragraph_passing_rows_of_different_rules_is_a_template(self):
        found = self.rows(
            ('SIG-C07.LINK', 'PASS', '见功能判定 FN-LINK（逻辑电平与驱动匹配）：' + self.BOILER + '；对象 {"nets": ["LATCH_N"]} 的本方面按以上核对'),
            ('DOC-D01.BOARD', 'PASS', self.BOILER + '（依据 path、requirement）'),
            ('DEV-D05.U1', 'PASS', self.BOILER))
        self.assertEqual([(c['code'], c['check_ids']) for c in found],
                         [('TEMPLATED_PASS_RATIONALE', ['DEV-D05.U1', 'DOC-D01.BOARD', 'SIG-C07.LINK'])])

    def test_one_judgement_shared_by_the_states_of_one_rule_is_not(self):
        text = '见功能判定 FN-BIAS（变换器电压裕量）：VCC 最低 9.6 V 高于 VCC(off) 上限 8.8 V，余量 0.8 V。'
        self.assertEqual(self.rows(('PWR-C02.BIAS-RUN.Q2', 'PASS', text), ('PWR-C02.BIAS-FAULT.Q2', 'PASS', text)), [])
        self.assertEqual(self.rows(('PWR-C02.X', 'PASS', '短'), ('PWR-C03.X', 'PASS', '短')), [])   # too short to judge
        self.assertEqual(self.rows(('PWR-C02.X', 'INSUFFICIENT', self.BOILER), ('PWR-C03.X', 'INSUFFICIENT', self.BOILER)), [])

    def test_a_part_identity_paragraph_answers_its_device_rows_and_requirement_aspects_are_separate_questions(self):
        ident = 'D1 实际型号 BZT52H-C5V1；物理端点 {"1": {"name": "K", "net": "ZBASE"}, "2": {"name": "A", "net": "PGND"}}'
        self.assertEqual(self.rows(('DEV-D01.D1', 'PASS', ident), ('DEV-D02.D1', 'PASS', ident), ('DEV-D05.D1', 'PASS', ident)), [])
        generic = 'REQ-LED-001：当前原理图能判的器件等级、路径/指示及条件计算已按独立记录核对；实际整机试验待后续执行。'
        found = self.rows(('REQ-D01.INDICATOR-PRESENT.REQ-LED-001', 'PASS', generic),
                          ('REQ-D01.TEMPERATURE-GRADE.REQ-TEMP-001', 'PASS', generic.replace('REQ-LED-001', 'REQ-TEMP-001')))
        self.assertEqual(len(found), 1)


if __name__ == '__main__':
    unittest.main()


class DerivedRowScreeningTests(unittest.TestCase):
    """SR task loop 2026-10-25 (④): rows derived from a function verdict carry the tool's sentence and the function's
    handoff by construction; the templated-text screens look only at reviewer-written rows (R6: 179 of 189 flagged
    rows in one record were derived)."""

    def setUp(self):
        from review_quality import screen_quality, templated_pass_rationale, templated_handoffs
        self.screen, self.templated_pass, self.templated_handoffs = screen_quality, templated_pass_rationale, templated_handoffs

    def test_derived_rows_do_not_count_as_reused_rationale(self):
        p, r, db = quality_fixture()
        self.assertIn('REUSED_RATIONALE_ACROSS_SCOPES', [c['code'] for c in self.screen(p, r, db)['candidates']])
        for row in r['checks']:
            row['derived'] = True
        self.assertNotIn('REUSED_RATIONALE_ACROSS_SCOPES', [c['code'] for c in self.screen(p, r, db)['candidates']])

    def test_derived_pass_rows_are_not_a_template(self):
        expected = {'PWR-C01.X': {'rule': 'PWR-C01'}, 'DEV-C05.Y': {'rule': 'DEV-C05'}}
        text = '见功能判定 FN-A（rating）：按手册推荐工作条件核对后每个量都在窗口内，最小裕量 20 %，无开放项'
        report = {'checks': [{'id': cid, 'review_result': 'PASS', 'rationale': text} for cid in expected]}
        self.assertEqual(len(self.templated_pass(report, expected)), 1)
        for row in report['checks']:
            row['derived'] = True
        self.assertEqual(self.templated_pass(report, expected), [])

    def test_derived_handoffs_are_not_a_template(self):
        report = {'checks': [{'id': 'PWR-C02.C%d' % i, 'handoff': {'required': True, 'receivers': ['样机验证'],
                                                                   'constraint': '闭壳 40 °C 测热点', 'verification': '记录数据'}}
                             for i in range(3)]}
        self.assertEqual({x['field'] for x in self.templated_handoffs(report)}, {'constraint', 'verification'})
        for row in report['checks']:
            row['derived'] = True
        self.assertEqual(self.templated_handoffs(report), [])

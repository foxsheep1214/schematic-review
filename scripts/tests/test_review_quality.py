"""Synthetic counterexamples: ledger consistency is not semantic correctness."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_validate_review import fixture, planned, E
from validate_review import fingerprint
from ledger_v3 import validate_review
from gap_fixture import complete_gap
from review_workflow import workflow


def unfinished():
    p, r, db = fixture()
    r['checks'][0].update(review_result='INSUFFICIENT', evidence_confidence='C',
                         missing_inputs=['Synthetic calculation not performed'],
                         potential_severity='P2', gap_cause='REVIEW_INCOMPLETE')
    complete_gap(r['checks'][0])
    return p, r, db


def staged(cause='REVIEW_INCOMPLETE', due='design_iteration'):
    p, r, db = unfinished()
    p['review_phase'] = 'design_iteration'
    r['plan_digest'] = fingerprint(p)
    r['checks'][0]['gap_cause'] = cause
    r.update(workflow_version=1, work_items=[{
        'id': 'W-1', 'title': 'Synthetic task', 'root_cause': 'Unfinished calculation',
        'reason': 'Synthetic independent input', 'next_action': 'Evaluate the local bound',
        'due_stage': due, 'check_ids': [r['checks'][0]['id']], 'evidence': E}])
    return p, r, db


def accepted_handoff(cause):
    p, r, db = staged(cause, 'prototype_verification')
    p['checks'][0]['handoff'] = {'required': True}
    r['plan_digest'] = fingerprint(p)
    r['checks'][0].update(potential_severity='P1', handoff={
        'required': True, 'state': 'ACCEPTED', 'scope': 'downstream_verification',
        'receivers': ['Synthetic PCB owner'], 'constraint': 'Controlled layout bound',
        'verification': 'Prototype measurement', 'evidence': E,
        'schematic_prerequisites': [r['checks'][1]['id']]})
    if cause is None:
        r['checks'][0].pop('gap_cause')
    return p, r, db


class CompletionGuardTests(unittest.TestCase):
    def test_unfinished_p2_never_releases(self):
        p, r, db = unfinished()
        out = validate_review(p, r, db)
        self.assertTrue(out['valid'], out)  # an honest partial ledger is valid
        self.assertEqual(out['release'], 'NO_GO')
        self.assertTrue(any('review work not completed' in s for s in out['blockers']))

    def test_unfinished_is_not_risk_acceptance_at_any_severity(self):
        for severity in ('P0', 'P1', 'P2', 'P3'):
            with self.subTest(severity=severity):
                p, r, db = unfinished()
                r['checks'][0].update(potential_severity=severity, disposition='ACCEPTED',
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
        for cause in ('EXTERNAL_DATA', 'DESIGN_OPEN', 'REVIEW_INCOMPLETE', 'USER_DEFERRED', None):
            with self.subTest(cause=cause):
                p, r, db = accepted_handoff(cause)
                out = validate_review(p, r, db)
                self.assertEqual(out['release'], 'NO_GO')

    def test_retired_downstream_gap_cause_is_rejected(self):
        # Pure downstream tests are stage NA (test_review_stage_scope); there is no INSUFFICIENT shortcut.
        p, r, db = accepted_handoff('DOWNSTREAM_VERIFICATION')
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

    def test_p0_item_owning_a_lower_branch_or_two_paths_is_flagged(self):
        p, r = self.p0_item()
        self.assertEqual(set(), self.codes(p, r))
        r['checks'][2]['potential_severity'] = 'P1'
        found = [x for x in self.screen(p, r)['candidates'] if x['code'] == 'WORK_ITEM_MIXES_LEVELS']
        self.assertEqual([r['checks'][2]['id']], found[0]['check_ids'])
        p, r = self.p0_item()
        r['checks'][2]['impact_assessment']['hazard_path'] = 'INSULATION'
        found = [x for x in self.screen(p, r)['candidates'] if x['code'] == 'WORK_ITEM_MIXES_HAZARD_PATHS']
        self.assertEqual(['FIRE', 'INSULATION'], found[0]['hazard_paths'])

    def test_request_keys_limit_the_branches_an_item_answers_for(self):
        p, r = self.p0_item()
        row = r['checks'][2]
        row['input_requests'] = {
            'short': {'potential_severity': 'P0', 'impact_assessment': {'hazard_path': 'FIRE'}},
            'loop': {'potential_severity': 'P1', 'impact_assessment': {}}}
        r['work_items'][0]['request_keys'] = {row['id']: ['short']}
        r['work_items'].append({'id': 'W-2', 'check_ids': [row['id']], 'request_keys': {row['id']: ['loop']}})
        self.assertEqual(set(), self.codes(p, r))

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
        db = {'parts': {'R604': {}, 'U601': {}, 'R60': {}}}
        row = r['checks'][0]
        row['input_requests'] = {'fuse clearing': {
            'why_decisive': 'x', 'required_scope': 'R604100°C',
            'acquisition': '向Littelfuse取得所选料号总清除能力', 'closure_criterion': '注入预算257.121uA以下'}}
        r['work_items'] = [{'id': 'W-1', 'check_ids': [row['id']], 'reason': 'U6016.5V直流额定'}]
        out = {x['code']: x for x in self.screen(p, r, db)['candidates']}
        self.assertEqual({'REF_GLUED_TO_VALUE', 'OVERPRECISE_CLOSURE_VALUE', 'ACQUISITION_WITHOUT_LOOKUP'}, set(out))
        glued = [x for x in self.screen(p, r, db)['candidates'] if x['code'] == 'REF_GLUED_TO_VALUE']
        self.assertEqual({('W-1', 'U601'), ('', 'R604')},
                         {((x['task_ids'] or [''])[0], x['refs'][0]) for x in glued})
        self.assertEqual(['257.121'], out['OVERPRECISE_CLOSURE_VALUE']['values'])
        self.assertEqual([row['id']], out['ACQUISITION_WITHOUT_LOOKUP']['check_ids'])
        q = row['input_requests']['fuse clearing']
        q.update(required_scope='R604 100°C', closure_criterion='注入预算低于手册上限',
                 acquisition='Littelfuse 规格书 p.2 只给额定分断电流，向 Littelfuse 取得总清除 I²t')
        r['work_items'][0]['reason'] = 'U601 6.5V 直流额定；R604 与 R60 各自标注'
        self.assertEqual(set(), self.codes(p, r, db))


class RequestOwnershipAndWordingTests(unittest.TestCase):
    def setUp(self):
        from review_quality import screen_quality
        self.screen = screen_quality

    def found(self, p, r, code):
        return [x for x in self.screen(p, r)['candidates'] if x['code'] == code]

    def test_acquisition_is_counted_for_the_tasks_naming_its_request_key(self):
        p, r = impact_fixture(n=3)
        row = r['checks'][0]
        for i, other in enumerate(r['checks']):
            other['impact_assessment']['consequence'] = f'N{i} consequence'
        shared = {'why_decisive': 'w', 'required_scope': 's', 'acquisition': '向原厂取得', 'closure_criterion': 'c'}
        row['input_requests'] = {k: dict(shared) for k in ('k1', 'k2', 'k3', 'k4')}
        # One task names k1; six other tasks own the remaining keys of the same row.
        r['work_items'] = [{'id': 'W-1', 'check_ids': [row['id']], 'request_keys': {row['id']: ['k1']}}] + [
            {'id': f'W-{n}', 'check_ids': [row['id']], 'request_keys': {row['id']: [f'k{n}']}} for n in (2, 3, 4)]
        for n in (2, 3, 4):
            row['input_requests'][f'k{n}']['acquisition'] = f'查 DS p{n}'
        # Before request_keys were honoured, k1's sentence was charged to all four owners.
        self.assertEqual([], self.found(p, r, 'BOILERPLATE_ACQUISITION'))
        # The same sentence genuinely owned by every task is still boilerplate.
        for n in (2, 3, 4):
            row['input_requests'][f'k{n}']['acquisition'] = '向原厂取得'
        hit = self.found(p, r, 'BOILERPLATE_ACQUISITION')
        self.assertEqual(['W-1', 'W-2', 'W-3', 'W-4'], hit[0]['task_ids'])

    def test_port_overvoltage_text_graded_as_component_damage_is_flagged(self):
        p, r = impact_fixture(n=3)
        for i, row in enumerate(r['checks']):
            row['impact_assessment']['consequence'] = f'N{i} consequence'
        row = r['checks'][0]
        row['impact_assessment'].update(consequence='合同过压可使端口负载损坏', consequence_class='COMPONENT_DAMAGE')
        self.assertEqual([row['id']], self.found(p, r, 'PORT_OVERVOLTAGE_GRADED_BELOW_P0')[0]['check_ids'])
        row['impact_assessment'].update(consequence_class='DAMAGE_OR_HAZARD', hazard_path='PORT_OVERVOLTAGE',
                                        exclusion='U601 锁定式 OVP，门限见 DS01 p12')
        self.assertEqual([], self.found(p, r, 'PORT_OVERVOLTAGE_GRADED_BELOW_P0'))
        # A negated or hand-over sentence is not an assertion of the path.
        row['impact_assessment'].update(consequence_class='COMPONENT_DAMAGE', hazard_path=None,
                                        consequence='Q701 可能损坏；未据此推断火灾、触电或端口过压')
        self.assertEqual([], self.found(p, r, 'PORT_OVERVOLTAGE_GRADED_BELOW_P0'))
        row['impact_assessment']['consequence'] = 'Q701 可能损坏；端口过压另由 W-OVP 单独核'
        self.assertEqual([], self.found(p, r, 'PORT_OVERVOLTAGE_GRADED_BELOW_P0'))

    def test_scope_echoing_the_task_and_templated_handoffs_are_flagged(self):
        p, r = impact_fixture(n=4)
        for i, row in enumerate(r['checks']):
            row['impact_assessment']['consequence'] = f'N{i} consequence'
        row = r['checks'][0]
        row['input_requests'] = {'k': {'why_decisive': 'w', 'required_scope': 'F101 分断；100A 尚未配对',
                                       'acquisition': 'a', 'closure_criterion': 'c'}}
        r['work_items'] = [{'id': 'W-1', 'title': 'F101 分断', 'root_cause': '100A 尚未配对', 'check_ids': [row['id']]}]
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
        row.update(gap_cause='DESIGN_OPEN', missing_inputs=['准确应用版本的烧录镜像与读回 hash'])
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
        db = {'parts': {'U202': {}, 'U403': {}, 'U404': {}}}
        r['work_items'] = [
            {'id': f'W-{ref}', 'check_ids': [c['id']],
             'next_action': f'按 {ref} 的实际 LED 电流取厂家适用 CTR 与退化界限，并算接收端最大负载 {n}µA'}
            for ref, n, c in zip(('U202', 'U403', 'U404'), (47, 1520, 277), r['checks'])]
        hit = self.found(p, r, 'DUPLICATE_WORK_ITEMS', db)
        self.assertEqual(['W-U202', 'W-U403', 'W-U404'], hit[0]['task_ids'])
        r['work_items'][0]['next_action'] = '改用 U202 的另一路 GPIO 直驱 DIS，去掉光耦'
        self.assertEqual(['W-U403', 'W-U404'], self.found(p, r, 'DUPLICATE_WORK_ITEMS', db)[0]['task_ids'])


class DownstreamTriageTests(unittest.TestCase):
    def codes(self, p, r):
        from review_quality import screen_quality
        return {x['code']: x for x in screen_quality(p, r)['candidates']}

    def test_test_only_gap_recorded_as_design_open_is_flagged(self):
        p, r = impact_fixture(n=2)
        r['checks'][0]['gap_cause'] = 'DESIGN_OPEN'
        r['checks'][0]['missing_inputs'] = ['闭壳温升与EMC传导实测结果']
        r['checks'][1]['gap_cause'] = 'DESIGN_OPEN'
        r['checks'][1]['missing_inputs'] = ['U1 偏置电阻未选，需样机前确定']
        found = self.codes(p, r)['DOWNSTREAM_RECORDED_AS_DESIGN_GAP']
        self.assertEqual([r['checks'][0]['id']], found['check_ids'])

    def test_optimization_goal_graded_p1_is_flagged(self):
        p, r = impact_fixture(n=2)
        p['checks'][0]['criterion'] = '万台物料成本优化目标60元'
        self.assertEqual([r['checks'][0]['id']], self.codes(p, r)['OPTIMIZATION_TARGET_AS_BLOCKING_GAP']['check_ids'])
        r['checks'][0]['potential_severity'] = 'P3'
        self.assertNotIn('OPTIMIZATION_TARGET_AS_BLOCKING_GAP', self.codes(p, r))


class FreezeGradingGateTests(unittest.TestCase):
    """Templated grading blocks release only in schematic_freeze; valid is unaffected."""

    def gate(self, phase):
        from unittest import mock
        import validate_review as vr
        from test_passive_stress import board, proposals
        from test_decoupling import ledger
        db, intent = board()
        if phase:
            intent['review_phase'] = phase
        plan, _ = proposals(db, intent)
        flagged = {'code': 'TEMPLATED_SEVERITY_REASON', 'check_ids': ['X'] * 12}
        fake = lambda *a, **k: {'candidates': [flagged]}
        with mock.patch.object(vr, 'screen_quality', fake):
            from ledger_v3 import record
            return vr.validate_review(plan, record(ledger(plan, db)), db)

    def test_freeze_blocks_and_iteration_does_not(self):
        freeze = self.gate('schematic_freeze')
        self.assertTrue(any(b.startswith('TEMPLATED_SEVERITY_REASON') for b in freeze['blockers']))
        iteration = self.gate('design_iteration')
        self.assertFalse(any(b.startswith('TEMPLATED_SEVERITY_REASON') for b in iteration['blockers']))


if __name__ == '__main__':
    unittest.main()


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
        from test_check_explanations import synthetic
        from render_report import render
        p, r = synthetic(['FAIL', 'INSUFFICIENT'])
        plain = render(p, r, {'valid': True})
        self.assertNotIn('- **审查记录自检**', plain)
        self.assertIn('| 审查记录自检提示（不计入结论） | 0 |', plain)
        gate = {'valid': True, 'quality_screening': {'candidates': [
            {'code': 'REUSED_RATIONALE_ACROSS_SCOPES', 'check_ids': ['a', 'b']},
            {'code': 'BOILERPLATE_ACQUISITION', 'check_ids': ['b']}]}}
        text = render(p, r, gate)
        self.assertIn('- **审查记录自检**：2 条提示涉及 2 条检查（REUSED_RATIONALE_ACROSS_SCOPES 1、BOILERPLATE_ACQUISITION 1）', text)
        self.assertIn('| 审查记录自检提示（不计入结论） | 2 |', text)
        strip = lambda t: [l for l in t.splitlines() if '审查记录自检' not in l]
        self.assertEqual(strip(plain), strip(text))



class HistoryReconciliationTests(unittest.TestCase):
    """100W PD R3 复审：声明了上一版审查，报告却显示 0 条处理记录，2 条旧问题的对照只在旁路文件里。"""

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

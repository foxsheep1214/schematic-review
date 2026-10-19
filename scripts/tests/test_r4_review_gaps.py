"""2026-10-19 对 ASG 100W PD 适配器 R4 的全新独立审查暴露的规则缺口（SR-20261019-R4-全新独立审查-ab53178）。"""
import pathlib
import sys
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import catalog


class FuseBreakingCapacityTest(unittest.TestCase):
    """R4 F101：Littelfuse 383 T3.15A 只保证 100 A@300 VAC，插墙一次侧短路分断不足（P0，审查者自查）。"""

    def test_pro_c01_asks_for_breaking_capacity_against_prospective_fault_current(self):
        criterion = catalog.criterion('PRO-C01')
        self.assertIn('分断能力', criterion)
        self.assertIn('预期短路电流', criterion)
        self.assertIn('1500 A', criterion)


class PinResistorCurrentLimitTest(unittest.TestCase):
    """R4 R605：100 Ω 接 RT7209B VBUS 脚，片内放电开关电流 57–110 mA，超 IDISCHG_VBUS 40 mA 上限（P1，审查者自查）。"""

    def test_dev_c01_limits_pin_current_into_an_internal_switch(self):
        criterion = catalog.criterion('DEV-C01')
        self.assertIn('外接电阻', criterion)
        self.assertIn('内部开关', criterion)
        self.assertIn('DEV-C01.<IC位号>-<脚名>', criterion)

    def test_sig_c05_hands_the_discharge_resistor_limit_to_dev_c01(self):
        self.assertIn('DEV-C01', catalog.criterion('SIG-C05'))

    def test_localization_advice_names_how_to_add_the_child(self):
        from review_quality import screen_quality
        plan = {'checks': [{'id': 'DEV-C01.BOARD', 'rule': 'DEV-C01', 'method': 'C', 'object': {'board': 'BOARD'}}]}
        results = {'checks': [{'id': 'DEV-C01.BOARD', 'review_result': 'FAIL'}]}
        advice = next(c for c in screen_quality(plan, results)['candidates']
                      if c['code'] == 'BROAD_CHECK_NEEDS_LOCALIZATION')
        self.assertIn('DEV-C01.<ref>', advice['message'])
        self.assertIn('plan', advice['message'])


def plan_rules(circuits):
    from plan_review import build_review_plan
    from test_checkers_framework import whole_board
    intent = {'schema_version': 3, 'circuits': [
        {'id': cid, 'type': kind, 'refs': ['U1'], 'states': ['run'], 'citation': 'synthetic'}
        for cid, kind in circuits]}
    return {(c['rule'], (c.get('object') or {}).get('circuit'))
            for c in build_review_plan(whole_board(), intent)['checks']}


class ChannelAndNoiseScopeTest(unittest.TestCase):
    """R4：R503 经 RT7209B 片内放大器进 ADC，板上无运放；PWR-C14 却对 PFC、反激、辅助供电各出一行。"""

    def test_analog_criteria_branch_for_an_on_chip_amplifier_and_adc(self):
        for rule in ('ANA-C01', 'ANA-C02'):
            with self.subTest(rule):
                criterion = catalog.criterion(rule)
                self.assertIn('片内放大器', criterion)
                self.assertIn('不另列运放子判据', criterion)

    def test_noise_budget_is_not_generated_for_a_converter_alone(self):
        self.assertNotIn(('PWR-C14', 'BUCK'), plan_rules([('BUCK', 'POWER_CONVERTER')]))

    def test_noise_budget_follows_sensitive_load_circuits(self):
        rules = plan_rules([('BUCK', 'POWER_CONVERTER'), ('ADC-IN', 'ANALOG'), ('PLL', 'CLOCK'), ('ANT', 'RF')])
        self.assertNotIn(('PWR-C14', 'BUCK'), rules)
        for circuit in ('ADC-IN', 'PLL', 'ANT'):
            self.assertIn(('PWR-C14', circuit), rules)


class NonIcDeviceKindTest(unittest.TestCase):
    """R4：BR101（GBU4M 桥堆）、T301（定制变压器）留在 PWR-D01 的 unverified-device-pinout，device_kinds 无法登记。"""

    @staticmethod
    def page(text):
        return lambda path, page: text if page == 1 else None

    def test_bridge_transformer_and_connector_quotes_verify(self):
        import datasheet_kinds as dk
        for kind, quote in (('bridge_rectifier', 'Glass Passivated Single-Phase Bridge Rectifier'),
                            ('transformer', 'For SMPS transformers with optimum'),
                            ('connector', 'USB Type C Receptacle for USB2.0, SMT Type')):
            with self.subTest(kind):
                self.assertEqual(dk.cues(quote), {kind})
                self.assertEqual(dk.verify({'kind': kind, 'page': 1, 'quote': quote}, 'x.pdf',
                                           self.page('header\n' + quote))['status'], 'VERIFIED')
        bridge = 'Glass Passivated Single-Phase Bridge Rectifier'
        self.assertEqual(dk.verify({'kind': 'diode', 'page': 1, 'quote': bridge}, 'x.pdf',
                                   self.page(bridge))['status'], 'QUOTE_CONFLICT')

    def test_bridge_rectifier_is_a_declarable_kind(self):
        import board_intent
        self.assertIn('bridge_rectifier', board_intent.DEVICE_KINDS)

    def test_verified_non_ic_kind_closes_the_inventory_gap(self):
        from decoupling import build_decoupling_inventory
        from test_decoupling import add, fixture, rebind
        import board_intent
        parts = {'BR9': ('Lib:GBU', [('1', '+', 'RECT'), ('2', '~', 'AC_L'), ('3', '~', 'AC_N'), ('4', '-', 'PRI_RTN')]),
                 'T9': ('Lib:ETD39', [('1', '1', 'BULK'), ('2', '2', 'DRAIN'), ('3', '3', 'AUX'), ('4', '4', 'PRI_RTN')])}
        quotes = {'BR9': ('bridge_rectifier', 'Glass Passivated Single-Phase Bridge Rectifier'),
                  'T9': ('transformer', 'For SMPS transformers with optimum')}
        for ref, (symbol, pins) in parts.items():
            with self.subTest(ref):
                db, intent = fixture()
                add(db, ref, 'TEST-PART', pins)
                db['parts'][ref]['prim'] = symbol
                intent['assemblies'][0]['population'][ref] = True
                kind, quote = quotes[ref]
                intent['device_kinds'] = {ref: {'kind': kind, 'page': 1, 'quote': quote}}
                rebind(db, intent)
                self.assertIn('unverified-device-pinout:' + ref, build_decoupling_inventory(db, intent)['discovery_gaps'])
                audit = {'device_kinds': {ref: dict(intent['device_kinds'][ref], status='VERIFIED',
                                                    document='synthetic.pdf', document_sha256='a' * 64)}}
                inv = build_decoupling_inventory(db, board_intent.with_verified_kinds(intent, audit))
                self.assertNotIn('unverified-device-pinout:' + ref, inv['discovery_gaps'])
                self.assertNotIn(ref, inv['unverified_device_refs'])


SHARED_GAP_HEADING = '### 示例：一个缺口被多条检查共享'


def shared_gap_example():
    """The JSON block right after the shared-gap heading in plan-and-results.md."""
    import json
    import re
    text = (SCRIPTS.parent / 'references' / 'plan-and-results.md').read_text(encoding='utf-8')
    _, found, rest = text.partition(SHARED_GAP_HEADING)
    match = re.search(r'```json\n(.*?)\n```', rest, re.S) if found else None
    return json.loads(match.group(1)) if match else None


class SharedGapExampleTest(unittest.TestCase):
    """R4 审查者要找一个缺口被多条检查共享时 request_keys、closure_domain、obligations 怎样接线的完整写法。"""

    def test_documented_example_passes_the_validators(self):
        import results_model
        from review_obligations import validate_obligations
        from review_workflow import workflow
        example = shared_gap_example()
        self.assertIsNotNone(example, 'plan-and-results.md lacks the shared-gap example')
        report = dict(example, schema_version=3)
        self.assertEqual(results_model.shape_errors(report), [])
        expanded = results_model.expand(report)
        checks = {row['id']: row for row in expanded['checks']}
        expected = {cid: {'id': cid, 'rule': cid.split('.')[0], 'object': {'circuit': cid.split('.')[1].rsplit('-', 1)[0]}}
                    for cid in checks}
        state = workflow({'review_phase': 'schematic_freeze'}, expanded, checks, require_design_options=True)
        self.assertEqual(state['errors'], [])
        self.assertEqual(validate_obligations(expected, checks, expanded['work_items']), [])
        shared = [cid for cid in checks if sum(cid in t['check_ids'] for t in expanded['work_items']) > 1]
        self.assertTrue(shared, 'the example must show one check split between two work items')
        whats = [set(r.get('input_requests', {})) for r in checks.values()]
        self.assertTrue(set.intersection(*whats), 'the example must show one gap shared by several checks')


class DownstreamScreenCounterexampleTest(unittest.TestCase):
    """真实反例：三份 R3 台账（3924cd7、41f4ad3 及其复审）把 F101 分断缺口因“插墙”标成下游项，R4 证实它是 P0 缺陷；
    435c0fc 的资料缺口只在附带分句里说“实际寄生波形随后验证”“OTP温度映射留给闭壳标定”。"""

    @staticmethod
    def flagged(whats):
        from review_quality import screen_quality
        from test_review_quality import impact_fixture
        p, r = impact_fixture(n=len(whats))
        for row, what in zip(r['checks'], whats):
            row.update(gap_cause='EXTERNAL_DATA', missing_inputs=[what])
        hit = {c['code']: c for c in screen_quality(p, r)['candidates']}.get('DOWNSTREAM_RECORDED_AS_DESIGN_GAP')
        ids = [row['id'] for row in r['checks']]
        return [ids.index(cid) for cid in (hit or {}).get('check_ids', [])]

    def test_application_context_and_deferred_side_clauses_are_not_downstream_gaps(self):
        self.assertEqual(self.flagged([
            '383 系列 100A 分断条件尚未与插墙应用的故障和后备保护对应',
            '同步整流自供电和关断时序适用范围：按准确NCP4307FBS的自供电、最小导通及关断条款和准确QR周期求SR_VCC、'
            '驱动电荷/反向时序，核正常反压及R504重复耗散；实际寄生波形随后验证。',
            '双偏置NTC判别的温度边界：取得NCU18WF104F60RB全范围R(T)容差或保证端点包络，结合准确RT7209两档电流、'
            'ADC满量程和等待状态复算不重叠；OTP温度映射留给闭壳标定。']), [])

    def test_test_only_gaps_are_still_flagged(self):
        self.assertEqual(self.flagged(['闭壳温升与EMC传导实测结果', '插墙实测温升随后验证', '安规认证报告']), [0, 1, 2])


if __name__ == '__main__':
    unittest.main()

"""一次真实独立审查（2026-10-19）暴露的规则缺口；每个用例用合成数据复现。"""
import pathlib
import sys
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import catalog


class FuseBreakingCapacityTest(unittest.TestCase):
    """真实反例：一只 T3.15A 保险丝只保证 100 A@300 VAC 分断，插墙一次侧短路分断不足（P0，审查者自查）。"""

    def test_pro_c01_asks_for_breaking_capacity_against_prospective_fault_current(self):
        criterion = catalog.criterion('PRO-C01')
        self.assertIn('分断能力', criterion)
        self.assertIn('预期短路电流', criterion)
        self.assertIn('1500 A', criterion)


class PinResistorCurrentLimitTest(unittest.TestCase):
    """真实反例：100 Ω 外接电阻接控制器 VBUS 放电脚，片内放电开关电流超出手册上限（P1，审查者自查）。"""

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
    intent = {'schema_version': 5, 'circuits': [
        {'id': cid, 'type': kind, 'refs': ['U1'], 'states': ['run'], 'citation': 'synthetic'}
        for cid, kind in circuits]}
    return {(c['rule'], (c.get('object') or {}).get('circuit'))
            for c in build_review_plan(whole_board(), intent)['checks']}


class ChannelAndNoiseScopeTest(unittest.TestCase):
    """真实反例：采样电阻经控制器片内放大器进 ADC，板上无运放；PWR-C14 却对每个变换器各出一行。"""

    def test_analog_criteria_branch_for_an_on_chip_amplifier_and_adc(self):
        for rule in ('ANA-C01', 'ANA-C02'):
            with self.subTest(rule):
                criterion = catalog.criterion(rule)
                self.assertIn('片内放大器', criterion)
                self.assertIn('不另列运放子判据', criterion)

    def test_noise_budget_is_not_generated_for_a_converter_alone(self):
        self.assertNotIn(('PWR-C14', 'BUCK'), plan_rules([('BUCK', 'POWER_CONVERTER')]))

    def test_noise_budget_is_asked_on_the_rail_not_on_each_sensitive_circuit(self):
        # function tree, step 4: one row per rail feeding a sensitive circuit (test_interface_rows)
        rules = plan_rules([('BUCK', 'POWER_CONVERTER'), ('ADC-IN', 'ANALOG'), ('PLL', 'CLOCK'), ('ANT', 'RF')])
        self.assertEqual({circuit for rule, circuit in rules if rule == 'PWR-C14'} - {None}, set())


class NonIcDeviceKindTest(unittest.TestCase):
    """真实反例：桥堆和定制变压器留在 PWR-D01 的 unverified-device-pinout，device_kinds 无法登记。"""

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
                # classify already reads BR/T refdes as bridge/transformer: no pin table is asked even before the kind is
                # verified (R7 acceptance 2026-10-25, A4); the verified kind keeps it closed
                self.assertNotIn('unverified-device-pinout:' + ref, build_decoupling_inventory(db, intent)['discovery_gaps'])
                audit = {'device_kinds': {ref: dict(intent['device_kinds'][ref], status='VERIFIED',
                                                    document='synthetic.pdf', document_sha256='a' * 64)}}
                inv = build_decoupling_inventory(db, board_intent.with_verified_kinds(intent, audit))
                self.assertNotIn('unverified-device-pinout:' + ref, inv['discovery_gaps'])
                self.assertNotIn(ref, inv['unverified_device_refs'])


SHARED_GAP_HEADING = '### 示例：一个缺口被多条检查共享'


def shared_gap_example():
    """The JSON block right after the shared-gap heading in results-format.md."""
    import json
    import re
    text = (SCRIPTS.parent / 'references' / 'results-format.md').read_text(encoding='utf-8')
    _, found, rest = text.partition(SHARED_GAP_HEADING)
    match = re.search(r'```json\n(.*?)\n```', rest, re.S) if found else None
    return json.loads(match.group(1)) if match else None


class DownstreamScreenCounterexampleTest(unittest.TestCase):
    """真实反例：三份台账把保险丝分断缺口因“插墙”标成下游项，下一轮证实它是 P0 缺陷；
    另一份的资料缺口只在附带分句里说“实际寄生波形随后验证”“OTP温度映射留给闭壳标定”。"""

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
            '保险丝 100A 分断条件尚未与插墙应用的故障和后备保护对应',
            '同步整流自供电和关断时序适用范围：按准确同步整流控制器的自供电、最小导通及关断条款和准确QR周期求自供电压、'
            '驱动电荷/反向时序，核正常反压及R9重复耗散；实际寄生波形随后验证。',
            '双偏置NTC判别的温度边界：取得NTC全范围R(T)容差或保证端点包络，结合准确控制器两档电流、'
            'ADC满量程和等待状态复算不重叠；OTP温度映射留给闭壳标定。']), [])

    def test_test_only_gaps_are_still_flagged(self):
        self.assertEqual(self.flagged(['闭壳温升与EMC传导实测结果', '插墙实测温升随后验证', '安规认证报告']), [0, 1, 2])


if __name__ == '__main__':
    unittest.main()

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


if __name__ == '__main__':
    unittest.main()

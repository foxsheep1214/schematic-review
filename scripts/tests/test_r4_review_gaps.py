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


if __name__ == '__main__':
    unittest.main()

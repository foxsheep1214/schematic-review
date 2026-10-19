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


if __name__ == '__main__':
    unittest.main()

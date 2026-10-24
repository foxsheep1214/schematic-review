"""The planning entry prints what the plan asks the reviewer to fix (SR self-check of 2026-10-24, item 1.2).

SKILL.md tells the reviewer to read the plan's prompts after a scan (a circuit type that asks almost nothing, rails
without a voltage, unbounded nodes, unread resistor values); `lint.py` is the entry that makes the plan, so it prints
them, from the same lines `plan_review.diagnostic_lines` gives.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from plan_review import build_review_plan, diagnostic_lines
from test_plan_review import sample_db


class DiagnosticLineTests(unittest.TestCase):
    def test_a_misfit_circuit_type_is_a_line(self):
        plan = {'diagnostics': [{'code': 'CIRCUIT_TYPE_MISFIT', 'detail': 'X1 按 STARTUP 只问到 0/4 条电路规则'}]}
        self.assertIn('  X1 按 STARTUP 只问到 0/4 条电路规则', diagnostic_lines(plan, sample_db(), None))

    def test_a_rail_without_a_voltage_is_a_line(self):
        plan = {'diagnostics': [], 'checks': [{'proposal': {'note': '补 power_rails.VBUS.voltage_v 后重跑'}}]}
        lines = diagnostic_lines(plan, sample_db(), None)
        self.assertTrue(any(line.startswith('  未声明电压的轨') and 'VBUS(1)' in line for line in lines), lines)

    def test_the_ground_domains_are_a_line(self):
        lines = diagnostic_lines(build_review_plan(sample_db(), None), sample_db(), None)
        self.assertIn('  按 0 V 处理的地网及参考地分区：GND=GND', lines)

    def test_lint_prints_them(self):
        with tempfile.TemporaryDirectory() as root:
            db = Path(root) / 'db.json'
            db.write_text(json.dumps(sample_db()), encoding='utf-8')
            out = subprocess.run([sys.executable, '-B', str(SCRIPTS / 'lint.py'), str(db), '--plan-json',
                                  str(Path(root) / 'plan.json'), '--json', str(Path(root) / 'lint.json')],
                                 capture_output=True, text=True, check=True).stdout
        self.assertIn('按 0 V 处理的地网及参考地分区：GND=GND', out)


if __name__ == '__main__':
    unittest.main()

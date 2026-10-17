"""calc.py 只转发到登记的条件计算，错误输入不补值。"""
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import calc
import zener_fault


class CalcCliTest(unittest.TestCase):
    def call(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = calc.main(list(argv))
        return code, out.getvalue()

    def test_forwards_keyword_arguments_and_echoes_inputs(self):
        kwargs = {'threshold_min_v': 2.4, 'clamp_max_v': 0, 'clamp_r_max_ohm': 1e5, 'other_source_max_a': 0}
        code, text = self.call('zener_fault.no_trip_budget', json.dumps(kwargs))
        self.assertEqual(code, 0)
        data = json.loads(text)
        self.assertEqual(data['inputs'], kwargs)
        self.assertEqual(data['result'], zener_fault.no_trip_budget(**kwargs))

    def test_missing_wrong_phase_and_unknown_calculation_exit_2(self):
        self.assertEqual(self.call('zener_fault.no_trip_budget', '{}')[0], 2)
        code, text = self.call('flyback_stop.primary_on_sr_platform', json.dumps(
            {'output_v_at_event': 20, 'primary_bus_v_at_event': 375,
             'primary_secondary_ratio': 5, 'phase': 'AFTER_STOP'}))
        self.assertEqual(code, 2)
        self.assertIn('primary-on', json.loads(text)['error'])
        self.assertEqual(self.call('os.system', '{}')[0], 2)
        self.assertEqual(self.call('fault_energy.packet_bound', '[1, 2]')[0], 2)
        self.assertEqual(self.call('fault_energy.packet_bound', 'not json')[0], 2)

    def test_every_listed_calculation_has_a_summary(self):
        code, text = self.call('--list')
        self.assertEqual(code, 0)
        self.assertEqual(len(text.splitlines()), len(calc.FUNCTIONS))
        self.assertNotIn('无说明', text)


if __name__ == '__main__':
    unittest.main()

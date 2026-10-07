"""Physical model binding, analytical cross-checks, and stale evidence rejection."""
import copy
import json
import math
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from simulate_rc import prepare, run, verify, sha, deck, measured

BINARY = shutil.which('ngspice') or '/opt/homebrew/bin/ngspice'


class SimulationEvidence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name); self.db_path = self.base / 'db.json'; self.spec_path = self.base / 'spec.json'
        self.db = {'parts': {'R1': {'prim': 'Device:R', 'value': '1k'}, 'R2': {'prim': 'Device:R', 'value': '1k'}},
                   'pin2net': {'R1.1': 'VIN', 'R1.2': 'OUT', 'R2.1': 'OUT', 'R2.2': 'GND', 'U1.1': 'OUT'},
                   'nets': {'VIN': ['R1.1'], 'OUT': ['R1.2', 'R2.1', 'U1.1'], 'GND': ['R2.2']}}
        basis = self.base / 'bounds.txt'; basis.write_text('Synthetic test: R1/R2 +/-1%; ideal source=5V; receiver load omitted.')
        self.spec = {'schema_version': 1, 'db_sha256': '', 'check_id': 'SYN-DIVIDER', 'state': 'run', 'model': 'ideal_linear_RC',
                     'components': {r: {'kind': 'R', 'min_si': 990, 'max_si': 1010} for r in ('R1', 'R2')},
                     'ground': 'GND', 'source': {'net': 'VIN', 'min_v': 5, 'max_v': 5},
                     'analysis': {'kind': 'op', 'net': 'OUT'}, 'window': {'min_v': 2.47, 'max_v': 2.53},
                     'excluded_nodes': {'U1.1': 'Explicit ideal high-impedance receiver; input loading not qualified'},
                     'assumptions': ['Ideal linear resistors and voltage source; test bounds only'],
                     'basis': [{'path': 'bounds.txt', 'sha256': sha(basis), 'locator': 'line 1 synthetic bounds'}]}
        self.write()

    def write(self):
        self.db_path.write_text(json.dumps(self.db)); self.spec['db_sha256'] = sha(self.db_path)
        self.spec_path.write_text(json.dumps(self.spec))

    def rejects(self, mutation):
        mutation(); self.write()
        with self.assertRaises((ValueError, KeyError, TypeError)):
            prepare(self.db_path, self.spec_path)

    def test_unmodeled_load_cannot_disappear_silently(self):
        self.rejects(lambda: self.spec['excluded_nodes'].clear())

    def test_wrong_primitive_or_dnp_rejected(self):
        for part in [{'prim': 'Device:L', 'value': '1k'}, {'prim': 'Device:R', 'value': '1k', 'nc': True}]:
            with self.subTest(part=part):
                self.db['parts']['R1'] = part; self.write()
                with self.assertRaises(ValueError): prepare(self.db_path, self.spec_path)

    def test_si_bounds_must_cover_real_nominal(self):
        self.rejects(lambda: self.spec['components']['R1'].update(min_si=1, max_si=2))

    def test_missing_pin_or_wrong_partition_rejected(self):
        self.rejects(lambda: self.db['pin2net'].pop('R1.2'))

    def test_no_nan_negative_or_reversed_bounds(self):
        for bounds in [(-1, 1000), (1010, 990), (float('nan'), 1010), (True, 1010)]:
            self.spec['components']['R1'].update(min_si=bounds[0], max_si=bounds[1]); self.write()
            with self.assertRaises(ValueError): prepare(self.db_path, self.spec_path)

    def test_stale_db_and_source_rejected(self):
        self.db_path.write_text(self.db_path.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'Stale'): prepare(self.db_path, self.spec_path)
        self.write(); (self.base / 'bounds.txt').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'source hash'): prepare(self.db_path, self.spec_path)

    def test_floating_or_ground_source_rejected(self):
        self.rejects(lambda: self.spec['source'].update(net='GND'))

    def test_solver_error_or_nonfinite_output_rejected(self):
        for stdout, stderr, code in [('actual = 2.5\n', 'singular matrix', 0), ('actual = 2.5\n', '', 1), ('actual = 1e999\n', '', 0), ('actual = 1\nactual = 2\n', '', 0)]:
            with self.assertRaises(ValueError): measured(stdout, stderr, code)

    def test_missing_tool_produces_no_evidence(self):
        with self.assertRaises(ValueError): run(self.db_path, self.spec_path, self.base / 'missing', '/missing/ngspice')
        self.assertFalse((self.base / 'missing').exists())

    def test_concurrent_input_edit_cannot_publish_valid_report(self):
        count = 0
        def solver(*args, **kwargs):
            nonlocal count
            count += 1
            if count == 2:
                self.db_path.write_text(self.db_path.read_text() + '\n')
            return SimpleNamespace(returncode=0, stdout='fake-version' if count == 1 else 'actual = 2.5\n', stderr='')
        with patch('simulate_rc.subprocess.run', side_effect=solver):
            with self.assertRaisesRegex(ValueError, 'Stale'):
                run(self.db_path, self.spec_path, self.base / 'concurrent', sys.executable)
        self.assertFalse((self.base / 'concurrent/simulation.json').exists())

    def test_net_reverse_index_inconsistency_rejected(self):
        self.rejects(lambda: self.db['pin2net'].update({'U1.1': 'GND'}))

    @unittest.skipUnless(Path(BINARY).is_file(), 'ngspice unavailable')
    def test_real_divider_matches_independent_formula_at_every_corner(self):
        report = run(self.db_path, self.spec_path, self.base / 'simulation', BINARY)
        self.assertEqual(report['status'], 'WITHIN_SAMPLED_WINDOW')
        self.assertEqual(len(report['corners']), 4)
        for c in report['corners']:
            r1, r2, vin = c['corner']; expected = vin * r2 / (r1 + r2)
            self.assertAlmostEqual(c['value_v'], expected, places=10)
        self.assertTrue(verify(self.db_path, self.spec_path, self.base / 'simulation/simulation.json')['valid'])

    @unittest.skipUnless(Path(BINARY).is_file(), 'ngspice unavailable')
    def test_rc_transient_and_report_tampering(self):
        self.db['parts']['R2'] = {'prim': 'Device:C', 'value': '100nF'}
        self.spec['components']['R2'] = {'kind': 'C', 'min_si': 90e-9, 'max_si': 110e-9}
        self.spec['analysis'] = {'kind': 'tran', 'net': 'OUT', 'at_s': 100e-6, 'max_step_s': 50e-9, 'initial_v': 0}
        self.spec['window'] = {'min_v': 0, 'max_v': 5}; self.write()
        report = run(self.db_path, self.spec_path, self.base / 'rc', BINARY)
        for c in report['corners']:
            r, cap, vin = c['corner']; expected = vin * (1 - math.exp(-100e-6 / (r * cap)))
            self.assertAlmostEqual(c['value_v'], expected, delta=2e-5)
        path = self.base / 'rc/simulation.json'
        self.assertTrue(verify(self.db_path, self.spec_path, path)['valid'])
        original = copy.deepcopy(report)
        for mutate in [lambda r: r.update(status='OUTSIDE_SAMPLED_WINDOW'), lambda r: r['corners'][0].update(value_v=0), lambda r: r['corners'].pop(), lambda r: r['artifacts'].pop('corner-00.cir')]:
            report = copy.deepcopy(original); mutate(report); path.write_text(json.dumps(report))
            with self.assertRaises(ValueError): verify(self.db_path, self.spec_path, path)
        path.write_text(json.dumps(original)); (self.base / 'rc/corner-00.stdout').write_text('actual = 0\n')
        with self.assertRaisesRegex(ValueError, 'artifact changed'): verify(self.db_path, self.spec_path, path)

    @unittest.skipUnless(Path(BINARY).is_file(), 'ngspice unavailable')
    def test_outside_window_is_not_relabelled_pass(self):
        self.spec['window'] = {'min_v': 2.499, 'max_v': 2.501}; self.write()
        r = run(self.db_path, self.spec_path, self.base / 'fail', BINARY)
        self.assertEqual(r['status'], 'OUTSIDE_SAMPLED_WINDOW')


if __name__ == '__main__':
    unittest.main()

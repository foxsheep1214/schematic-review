"""Licensed frozen public graph with explicit regression-only numerical contract.

Synthetic document bindings exercise the hot calculation contract, not the truth
of a manufacturer's datasheet or completion of the real board review.
"""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from lint import Lint
from electrical_fixtures import bind_evidence

FIXTURE = Path(__file__).parent / 'fixtures/esp32-poe-iso-revn-calibration'


def frozen_database():
    return json.loads((FIXTURE / 'variant-db.json').read_text())


def test_contract():
    return {'schema_version': 2, 'checks': [json.loads((FIXTURE / 'u7-test-contract.json').read_text())]}


class PublicCalibrationTests(unittest.TestCase):
    def test_tvs_orphan_candidate_tracks_the_real_endpoint_and_reconnection(self):
        board = frozen_database()
        self.assertEqual(board['nets']['/RD'], ['TVS1.1'])
        self.assertTrue({'U4.31', 'LAN_CON1.3'} <= set(board['nets']['/RD+']))
        findings = Lint(board).run()
        target = [f for f in findings if f['rule'] == 'PRO-A01' and 'TVS1.1' in f['detail']]
        self.assertEqual(len(target), 1)
        self.assertEqual(target[0]['kind'], 'FINDING')
        repaired = copy.deepcopy(board)
        repaired['nets']['/RD'].remove('TVS1.1')
        repaired['nets']['/RD+'].append('TVS1.1')
        repaired['pin2net']['TVS1.1'] = '/RD+'
        revised = Lint(repaired).run()
        self.assertFalse([f for f in revised if f['rule'] == 'PRO-A01' and 'TVS1.1' in f['detail']])
        self.assertEqual(repaired['parts'], board['parts'])

    def test_tvs_identified_by_series_keyword_is_checked_for_orphan_nets(self):
        # D11 is an SMBJ part with no "TVS"/"ESD" text; the device classifier
        # already calls it a TVS, so the orphan-net scan must cover it too.
        board = frozen_database()
        self.assertFalse([f for f in Lint(copy.deepcopy(board)).run()
                          if f['rule'] == 'PRO-A01' and 'D11' in f['detail']])
        board['nets']['/5V_DCDC'].remove('D11.1')
        board['nets']['SEED_ORPHAN'] = ['D11.1']
        board['pin2net']['D11.1'] = 'SEED_ORPHAN'
        target = [f for f in Lint(board).run() if f['rule'] == 'PRO-A01' and 'D11.1' in f['detail']]
        self.assertEqual(len(target), 1)

    def bound_results(self, board, evidence, directory):
        audit = bind_evidence(board, evidence, directory)
        findings = Lint(board, evidence=evidence, datasheet_audit=audit).run()
        return [f for f in findings if f['rule'] == 'PWR-E01' and f.get('check_id') == 'U7-FB-INITIAL25C']

    def test_packaged_feedback_value_reproduces_the_actual_overvoltage_window(self):
        board = frozen_database()
        self.assertEqual(board['parts']['R29']['value'], '330k/1%/R0402')
        self.assertEqual(board['parts']['R30']['value'], '49.9k/1%/R0402')
        with tempfile.TemporaryDirectory() as directory:
            rows = self.bound_results(board, test_contract(), directory)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['kind'], 'FINDING')
        self.assertEqual(rows[0]['review_result'], 'FAIL')
        self.assertAlmostEqual(rows[0]['calculation']['min'], 4.389352440921447)
        self.assertAlmostEqual(rows[0]['calculation']['max'], 4.7511476352705415)
        self.assertGreater(rows[0]['calculation']['min'], 3.6)

    def test_repaired_divider_control_only_checks_declared_static_window(self):
        board = frozen_database()
        board['parts']['R29']['value'] = '226k/1%/R0402'
        with tempfile.TemporaryDirectory() as directory:
            audit = bind_evidence(board, evidence := test_contract(), directory)
            scan = Lint(board, evidence=evidence, datasheet_audit=audit)
            findings = scan.run()
        self.assertFalse([f for f in findings if f['rule'] == 'PWR-E01' and f.get('check_id') == 'U7-FB-INITIAL25C'])
        passes = [f for f in scan.passes if f['rule'] == 'PWR-E01' and f.get('check_id') == 'U7-FB-INITIAL25C']
        self.assertEqual(len(passes), 1)
        self.assertGreaterEqual(passes[0]['calculation']['min'], 3)
        self.assertLessEqual(passes[0]['calculation']['max'], 3.6)

    def test_missing_bias_and_unavailable_source_remain_not_ready(self):
        for missing in ('bias', 'document'):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as directory:
                board = frozen_database(); evidence = test_contract()
                audit = bind_evidence(board, evidence, directory)
                if missing == 'bias':
                    del evidence['checks'][0]['divider_model']['bias_current_a']
                else:
                    for material in audit['materials']:
                        material['status'] = 'NEED_REVIEW'
                rows = [f for f in Lint(board, evidence=evidence, datasheet_audit=audit).run()
                        if f['rule'] == 'PWR-E01' and f.get('check_id') == 'U7-FB-INITIAL25C']
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]['review_result'], 'INSUFFICIENT')
                self.assertEqual(rows[0]['kind'], 'CANDIDATE')


if __name__ == '__main__':
    unittest.main()

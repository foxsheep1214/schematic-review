"""Licensed frozen public graph: automatic-scan regressions on a real board's netlist, not completion of its review."""
import copy
import json
from pathlib import Path
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from lint import Lint

FIXTURE = Path(__file__).parent / 'fixtures/esp32-poe-iso-revn-calibration'


def frozen_database():
    return json.loads((FIXTURE / 'variant-db.json').read_text())


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

if __name__ == '__main__':
    unittest.main()

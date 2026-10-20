"""Golden reports: one rendered report per ledger fixture, compared whole.

A wording change updates the snapshot files, not scattered asserts:
    SR_UPDATE_GOLDEN=1 python3 -m unittest scripts/tests/test_golden_reports.py
then read the diff of scripts/tests/fixtures/golden_reports/ before committing.
"""
import difflib
import json
import os
from pathlib import Path
import unittest

from test_review_stage_scope import decisive, downstream
from test_validate_review import fixture, fail
from ledger_v3 import as_sent, validate_review
from render_report import render

GOLDEN = Path(__file__).resolve().parent / 'fixtures' / 'golden_reports'


def defect():
    p, r, db = fixture()
    fail(r)
    return p, r, db


FIXTURES = {
    'clean': fixture,           # every check PASS
    'defect': defect,           # one P1 finding
    'decisive': decisive,       # blocking INSUFFICIENT with an input request and work item
    'downstream': downstream,   # NA outside stage with an open downstream handoff
}


def rendered(name):
    p, r, db = FIXTURES[name]()
    gate = json.loads(json.dumps(validate_review(p, r, db), default=sorted))
    assert gate['valid'], gate['errors']
    return render(p, as_sent(p, r), gate)   # the record the validator saw: schema 4 with its functions


class GoldenReportTests(unittest.TestCase):
    def test_reports_match_golden_snapshots(self):
        update = os.environ.get('SR_UPDATE_GOLDEN') == '1'
        for name in FIXTURES:
            with self.subTest(name):
                path = GOLDEN / (name + '.md')
                text = rendered(name)
                if update:
                    GOLDEN.mkdir(parents=True, exist_ok=True)
                    path.write_text(text, encoding='utf-8')
                    continue
                expected = path.read_text(encoding='utf-8')
                if text != expected:
                    diff = ''.join(difflib.unified_diff(expected.splitlines(True), text.splitlines(True),
                                                        str(path), 'rendered'))
                    self.fail('report wording changed; review and rerun with SR_UPDATE_GOLDEN=1\n' + diff)


if __name__ == '__main__':
    unittest.main()

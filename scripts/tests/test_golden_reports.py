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
from validate_review import fingerprint, validate_review
from render_report import render

GOLDEN = Path(__file__).resolve().parent / 'fixtures' / 'golden_reports'


def defect():
    p, r, db = fixture()
    fail(r)
    return p, r, db


def functions():
    """A function verdict whose 15 bound rows the tools derive at read time (none written), two of them open."""
    from test_derive_rows import bias_plan
    return bias_plan()


def estimate():
    """A PASS on a typical-value estimate: C-grade evidence, the prototype test handed on, release capped."""
    from test_estimate_pass import estimated
    return estimated(cell='ZENER-VZ-LOWER', method='G8', estimate_factor=1.2)


def constraint():
    """乙 (2026-10-26): a value the magnetics design owns, passed on the constraint SR back-calculated and handed on."""
    from test_design_constraint import HANDOFF, constrained
    from test_review_functions import ledger
    p, r, db = ledger(constrained())
    for row in r['checks']:
        if row['id'].startswith('PWR-C02'):
            row['handoff'] = dict(HANDOFF, required=True, state='OPEN')
    return p, r, db


def extension():
    """A fitted part the kind vocabulary does not know: a NEW_DEVICE_KIND signal under 对 SR 的反馈."""
    from test_derive_rows import bias_plan
    p, r, db = bias_plan()
    db['parts']['GDT1'] = {'part': 'B88069X2320S102', 'value': 'GDT 350V'}
    db['ref2page']['GDT1'] = 1
    r['coverage']['components']['GDT1'] = [r['checks'][0]['id']]   # covered by the fixture's first row, like R1
    r['db_digest'] = fingerprint(db)
    return p, r, db


FIXTURES = {
    'clean': fixture,           # every check PASS
    'defect': defect,           # one P1 finding
    'decisive': decisive,       # blocking INSUFFICIENT with an input request and work item
    'downstream': downstream,   # NA outside stage with an open downstream handoff
    # Item 7 of the 2026-10-26 SR review: the newer architecture end to end on synthetic ledgers
    'functions': functions,     # derived rows from a function verdict, work item with blocked judgements
    'estimate': estimate,       # 按典型值估算的结论, grade C, CONDITIONAL_GO
    'constraint': constraint,   # 设计约束 handed to the magnetics design, rows PASS
    'extension': extension,     # 器件类别与定界表要扩的 under 对 SR 的反馈
}


def rendered(name):
    p, r, db = FIXTURES[name]()
    gate = json.loads(json.dumps(validate_review(p, r, db), default=sorted))
    assert gate['valid'], gate['errors']
    return render(p, r, gate)


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

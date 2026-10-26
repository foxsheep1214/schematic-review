"""Item 4 of the 2026-10-26 review of SR (user: 第三第四项也做): derived rows are not persisted. The ledger holds the
function verdicts and the hand-filled rows; the gate, the report, the packer and the comparison derive the bound rows
when they read it (results_model.materialize), so no written copy of a verdict can disagree with it. R7: 453/436/634/582
of 525/515/777/690 rows were derived copies, 0.45–1.7 MB of each record.
"""
import copy
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import compare_reviews
import derive_rows
import pack_review
import results_model
import validate_review as vr
from render_report import render
from test_render_and_pack import write_report
from test_derive_rows import bias_plan, bias_rows


class MaterializeTests(unittest.TestCase):
    def test_a_record_without_derived_rows_validates_and_renders_the_rows(self):
        p, r, db = bias_plan()                      # results hold only the function
        self.assertEqual(bias_rows(r), {})
        out = vr.validate_review(p, r, db)
        self.assertTrue(out['valid'], out['errors'])
        self.assertEqual(out['summary']['results']['INSUFFICIENT'], 2)
        self.assertEqual(bias_rows(r), {}, 'the gate derives on its own copy')
        text = render(p, r, out)
        self.assertIn('| 检查总数 | 22 |', text)           # 7 fixture rows + the 15 derived ones, none in the ledger
        self.assertIn('涉及 2 条检查', text)

    def test_a_written_derived_row_never_outvotes_the_function(self):
        p, r, db = bias_plan()
        r, _, _ = derive_rows.derive(p, r)
        stale = bias_rows(r)['PWR-C03.BIAS-RUN.Q2']
        self.assertEqual(stale['review_result'], 'PASS')
        stale.update(review_result='FAIL', fail_ref='FN-BIAS/NOPE')   # a stale copy of a verdict that changed
        view, errors = results_model.materialize(p, r)
        self.assertEqual(errors, [])
        row = next(c for c in view['checks'] if c['id'] == 'PWR-C03.BIAS-RUN.Q2')
        self.assertEqual((row['review_result'], 'fail_ref' in row), ('PASS', False))

    def test_a_stub_with_an_annotation_keeps_it_on_the_derived_row(self):
        p, r, db = bias_plan()
        r['checks'].append({'id': 'PWR-C03.BIAS-RUN.Q2', 'notes': '审查员补充：按 Q2 实际型号的额定'})
        view, errors = results_model.materialize(p, r)
        self.assertEqual(errors, [])
        row = next(c for c in view['checks'] if c['id'] == 'PWR-C03.BIAS-RUN.Q2')
        self.assertEqual((row['review_result'], row['notes'], row['derived']),
                         ('PASS', '审查员补充：按 Q2 实际型号的额定', True))

    def test_derive_errors_reach_the_gate(self):
        p, r, db = bias_plan()
        r['functions'][0]['calculation']['margin'] = r['functions'][0]['calculation']['margin'][:1]   # other aspects unjudged
        out = vr.validate_review(p, r, db)
        self.assertFalse(out['valid'])
        self.assertTrue(any('judges no' in e for e in out['errors']), out['errors'][:3])

    def test_a_stub_no_function_derives_is_an_error_with_its_name(self):
        p, r, db = bias_plan()
        r['checks'].append({'id': 'PWR-C02.NOWHERE.Q9', 'notes': 'left over'})    # not in the plan
        _, errors = results_model.materialize(p, r)
        self.assertEqual(errors, ['PWR-C02.NOWHERE.Q9: a stub row (binding or annotation only) that no function derives; '
                                  'judge the row by hand or remove the stub'])
        out = vr.validate_review(p, r, db)
        self.assertTrue(any('stub row' in e for e in out['errors']), out['errors'][:3])

    def test_without_a_plan_materialize_only_expands(self):
        p, r, db = bias_plan()
        view, errors = results_model.materialize(None, r)
        self.assertEqual((errors, bias_rows(view)), ([], {}))


class StripDerivedTests(unittest.TestCase):
    def test_derived_rows_leave_and_an_annotated_one_leaves_a_stub(self):
        p, r, db = bias_plan()
        r, _, _ = derive_rows.derive(p, r)
        bias_rows(r)['PWR-C03.BIAS-RUN.Q2']['manual_verification'] = {'method': 'read the BOM line'}
        hand = [c['id'] for c in r['checks'] if not c.get('derived')]
        stripped, removed, stubs = results_model.strip_derived(copy.deepcopy(r))
        self.assertEqual((removed, stubs), (15, 1))
        self.assertEqual([c['id'] for c in stripped['checks'] if 'manual_verification' in c], ['PWR-C03.BIAS-RUN.Q2'])
        stub = next(c for c in stripped['checks'] if c['id'] == 'PWR-C03.BIAS-RUN.Q2')
        self.assertEqual(stub, {'id': 'PWR-C03.BIAS-RUN.Q2', 'manual_verification': {'method': 'read the BOM line'}})
        self.assertEqual([c['id'] for c in stripped['checks'] if c['id'] != 'PWR-C03.BIAS-RUN.Q2'], hand)
        self.assertFalse(any(c.get('derived') for c in stripped['checks']))

    def test_the_reviewers_own_binding_survives_as_a_stub(self):
        p, r, db = bias_plan()
        mine = next(c for c in p['checks'] if c['id'] == 'PWR-C03.BIAS-RUN.Q2')
        del mine['function_id']                     # the planner did not bind this row; the reviewer did, on the row
        r['checks'].append({'id': 'PWR-C03.BIAS-RUN.Q2', 'function_id': 'FN-BIAS', 'aspect': mine['aspect']})
        r['plan_digest'] = vr.fingerprint(p)
        derived, _, errors = derive_rows.derive(p, copy.deepcopy(r))
        self.assertEqual(errors, [])
        stripped, removed, stubs = results_model.strip_derived(derived, p)
        stub = next(c for c in stripped['checks'] if c['id'] == 'PWR-C03.BIAS-RUN.Q2')
        self.assertEqual(stub, {'id': 'PWR-C03.BIAS-RUN.Q2', 'function_id': 'FN-BIAS', 'aspect': mine['aspect']})
        view, errors = results_model.materialize(p, stripped)
        self.assertEqual(errors, [])
        self.assertEqual(next(c for c in view['checks'] if c['id'] == 'PWR-C03.BIAS-RUN.Q2')['review_result'], 'PASS')
        self.assertFalse(any('function_id' in c for c in results_model.strip_derived(derive_rows.derive(p, copy.deepcopy(r))[0])[0]['checks']
                             if c['id'] == 'PWR-C03.BIAS-RUN.Q2'), 'without the plan the binding is not known to be the reviewer\'s')


class PackAndCompareTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.work, self.out = self.tmp / 'work', self.tmp / 'review'
        self.work.mkdir(); self.out.mkdir()
        p, r, db = bias_plan()
        r, _, _ = derive_rows.derive(p, r)          # a reviewer who still ran the old -o form
        bias_rows(r)['PWR-C03.BIAS-RUN.Q2']['notes'] = '审查员补充'
        gate = json.loads(json.dumps(vr.validate_review(p, r, db), default=sorted))
        self.assertTrue(gate['valid'], gate['errors'][:5])
        for source in pack_review.cited_sources(r) - {'db.json'}:   # the fixture's citations; ds/ texts need a PDF input
            (self.work / source).parent.mkdir(parents=True, exist_ok=True)
            (self.work / source).write_text('{}')
        self.inputs = self.tmp / 'inputs'; self.inputs.mkdir()
        (self.inputs / 'U1.pdf').write_bytes(b'%PDF-1.4')
        data = {'review-plan.json': p, 'review-results.json': r, 'review-gate.json': gate, 'db.json': db,
                'intent.json': {}, 'lint-cold.json': {}, 'lint-hot.json': {}}
        self.ledger = {}
        for name, value in data.items():
            (self.work / name).write_text(json.dumps(value))
            self.ledger[name] = str(self.work / name)
        write_report(self.out, render(p, r, gate))

    def test_the_packed_ledger_holds_no_derived_rows_and_the_report_still_matches(self):
        errors, manifest = pack_review.pack(self.out, self.ledger, str(self.work), {'requirements': str(self.inputs)})
        self.assertEqual(errors, [])
        packed = json.loads((self.out / pack_review.RECORD / 'review-results.json').read_text(encoding='utf-8'))
        self.assertEqual(bias_rows(packed), {'PWR-C03.BIAS-RUN.Q2': {'id': 'PWR-C03.BIAS-RUN.Q2', 'notes': '审查员补充'}})
        self.assertFalse(any(c.get('derived') for c in packed['checks']))
        [note] = [n for n in manifest['notes'] if 'derived rows' in n]
        self.assertIn('15 derived rows are not packed', note)
        self.assertIn('1 kept a stub', note)
        self.assertEqual(json.loads(Path(self.ledger['review-results.json']).read_text())['checks'][-1].get('derived'), True,
                         'the work copy is not touched')

    def test_compare_reviews_sees_the_derived_rows_of_a_stripped_record(self):
        pack_review.pack(self.out, self.ledger, str(self.work), {'requirements': str(self.inputs)})
        side = compare_reviews.load(self.out)
        self.assertEqual(len(bias_rows(side['results'])), 15)
        self.assertEqual(bias_rows(side['results'])['PWR-C03.BIAS-RUN.Q2']['notes'], '审查员补充')


if __name__ == '__main__':
    unittest.main()

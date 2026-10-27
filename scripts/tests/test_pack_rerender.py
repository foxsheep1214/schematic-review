"""The pack re-renders the report from the ledger and packs only a valid board verdict (SR self-check 2.3, user:
重新渲染比对 + 要求 valid).

The documents said a hand-edited report fails the pack and a scoped hot review is not packed, but the pack only checked
that the HTML copy matched the Markdown, read no gate result and no review_scope. It now renders the report again from
the packed plan, results, gate and notes (with the title and detail it was rendered with) and refuses any difference,
refuses a gate that is not valid and a ledger that answers only some frames.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pack_review import pack, REPORT, RECORD
from render_report import render
import test_render_and_pack as packing
from test_render_and_pack import write_report

NOTES = {'summary': '总体可用，先改两处。'}


class RerenderTests(unittest.TestCase):
    setUp = packing.PackReviewTests.setUp
    render_current = packing.PackReviewTests.render_current

    def load(self, name):
        return json.loads((self.work / name).read_text())

    def run_pack(self, **options):
        return pack(self.out, self.ledger, str(self.work), {'requirements': str(self.inputs)}, **options)

    def rerender_errors(self, errors):
        return [e for e in errors if 're-render' in e and REPORT in e and 'HTML' not in e]

    def test_a_report_rendered_from_the_ledger_packs(self):
        errors, _ = self.run_pack()
        self.assertEqual(errors, [])

    def test_a_hand_edited_report_is_refused(self):
        text = (self.out / REPORT).read_text(encoding='utf-8')
        write_report(self.out, text.replace('\n', '\n\n补一句手写的话。\n', 1))
        errors, _ = self.run_pack()
        self.assertEqual(len(self.rerender_errors(errors)), 1, errors)

    def test_a_report_of_an_older_ledger_is_refused(self):
        results = self.load('review-results.json')
        results['functions'][0]['question'] = '启动时稳压器限流会不会挡住上电'   # the function table shows it
        (self.work / 'review-results.json').write_text(json.dumps(results))
        packing.stamp_gate(self.ledger)
        errors, _ = self.run_pack()
        self.assertEqual(len(self.rerender_errors(errors)), 1, errors)

    def test_notes_title_and_detail_are_those_it_was_rendered_with(self):
        (self.work / 'notes.json').write_text(json.dumps(NOTES, ensure_ascii=False))
        self.render_current(notes=NOTES, title='整板审查', detail='full')
        errors, _ = self.run_pack()
        self.assertEqual(len(self.rerender_errors(errors)), 1, errors)       # rendered with notes the pack lacks
        self.ledger['notes.json'] = str(self.work / 'notes.json')
        errors, _ = self.run_pack()
        self.assertEqual(len(self.rerender_errors(errors)), 1, errors)       # and with a title and detail
        errors, manifest = self.run_pack(title='整板审查', detail='full')
        self.assertEqual(errors, [])
        self.assertIn(RECORD + '/notes.json', manifest['packed'])

    def test_a_gate_that_is_not_valid_is_not_packed(self):
        gate = self.load('review-gate.json')
        gate['valid'] = False
        (self.work / 'review-gate.json').write_text(json.dumps(gate))
        self.render_current()
        errors, _ = self.run_pack()
        self.assertTrue(any('valid' in e and 'validate_review' in e for e in errors), errors)

    def test_results_edited_after_the_gate_are_not_packed(self):
        # 2026-10-27 (Codex review of SR): the pack read the old gate's valid and never ran the gate again
        results = self.load('review-results.json')
        results['plan_digest'] = '0' * 64
        (self.work / 'review-results.json').write_text(json.dumps(results))
        self.render_current()
        errors, _ = self.run_pack()
        self.assertEqual(errors, ['review-gate.json was written for other files than these (results); run '
                                  'validate_review.py again on the files being packed'])

    def test_a_gate_without_its_file_fingerprints_is_not_packed(self):
        gate = self.load('review-gate.json')
        del gate['validated_files']
        (self.work / 'review-gate.json').write_text(json.dumps(gate))
        self.render_current()
        errors, _ = self.run_pack()
        self.assertEqual(errors, ['review-gate.json names no validated_files; write it with validate_review.py --json'])

    def test_the_gate_command_writes_the_fingerprints_the_pack_reads(self):
        import subprocess
        gate_path = self.work / 'review-gate.json'
        subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'validate_review.py'),
                        self.ledger['review-plan.json'], self.ledger['review-results.json'], '--db', self.ledger['db.json'],
                        '--lint', self.ledger['lint-cold.json'], '--lint', self.ledger['lint-hot.json'],
                        '--json', str(gate_path)], capture_output=True)
        written = json.loads(gate_path.read_text())['validated_files']
        self.assertEqual(set(written), {'plan', 'results', 'db', 'lint'})
        packing.stamp_gate(self.ledger)
        self.assertEqual(written, json.loads(gate_path.read_text())['validated_files'])

    def test_a_scoped_review_is_not_packed(self):
        results = self.load('review-results.json')
        results['review_scope'] = {'functions': ['FN-X'], 'reason': '单电路热审'}
        (self.work / 'review-results.json').write_text(json.dumps(results))
        packing.stamp_gate(self.ledger)
        self.render_current()
        errors, _ = self.run_pack()
        self.assertTrue(any('review_scope' in e for e in errors), errors)


if __name__ == '__main__':
    unittest.main()

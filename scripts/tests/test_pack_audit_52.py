"""5.2 打包与交付 strict audit (2026-10-26, user: 5.2 的 A–F 全部执行). Measured on the four R7 deliveries: the record's
own files copied into record/evidence (codex1 7 MB: SR's derive cites review-results.json, the plan cites db.json),
whole datasheets and standards as text extracts (1.3–1.5 MB each), SR's own references declared as inputs, and no
datasheet input declared by the two Claude runs.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pack_review
from pack_review import RECORD, SKILL_ROOT
from test_render_and_pack import PackReviewTests


class PackAuditTests(unittest.TestCase):
    def setUp(self):
        self.base = PackReviewTests('setUp')
        self.base.setUp()

    def pack(self, inputs=None):
        b = self.base
        return pack_review.pack(b.out, b.ledger, str(b.work), inputs if inputs is not None else {'requirements': str(b.inputs)})

    def test_a_cited_ledger_file_is_read_in_record_and_not_copied(self):
        self.base.cite('db.json')
        self.base.cite('record/review-results.json')
        errors, manifest = self.pack()
        self.assertEqual(errors, [])
        evidence = {k for k in manifest['packed'] if k.startswith(RECORD + '/evidence/')}
        self.assertFalse(any(k.endswith(('db.json', 'review-results.json')) for k in evidence), evidence)
        self.assertFalse((self.base.out / RECORD / 'evidence' / 'db.json').exists())

    def test_a_cited_ledger_file_that_is_not_packed_is_unresolved(self):
        self.base.cite('record/notes.json')          # no notes.json in this pack
        errors, _ = self.pack()
        self.assertTrue(any('record/notes.json' in e and 'neither' in e for e in errors), errors)

    def test_a_large_evidence_file_is_packed_with_a_note_and_the_total_is_recorded(self):
        (self.base.work / 'big.md').write_text('x' * (pack_review.EVIDENCE_NOTE_BYTES + 1))
        self.base.cite('big.md')
        errors, manifest = self.pack()
        self.assertEqual(errors, [])
        self.assertIn(RECORD + '/evidence/big.md', manifest['packed'])
        [note] = [n for n in manifest['notes'] if 'big.md' in n]
        self.assertIn('whole document is an input', note)
        self.assertGreater(manifest['evidence_bytes'], pack_review.EVIDENCE_NOTE_BYTES)
        self.assertEqual([n for n in manifest['notes'] if 'startup.md' in n], [])

    def test_a_datasheet_text_without_a_pdf_input_is_refused_and_with_its_pdf_is_noted(self):
        (self.base.work / 'ds').mkdir()
        (self.base.work / 'ds' / 'U9.txt').write_text('Electrical characteristics p7')
        self.base.cite('ds/U9.txt')
        errors, _ = self.pack()
        self.assertTrue(any('no declared input holds a PDF' in e and 'ds/U9.txt' in e for e in errors), errors)
        pdfs = self.base.tmp / 'pdfs'; pdfs.mkdir()
        (pdfs / 'U9.pdf').write_bytes(b'%PDF-1.4')
        errors, manifest = self.pack({'requirements': str(self.base.inputs), 'datasheets': str(pdfs)})
        self.assertEqual(errors, [])
        self.assertTrue(any('ds/U9.txt' in n and 'U9.pdf' in n and 'by path and page' in n for n in manifest['notes']), manifest['notes'])
        (pdfs / 'U9.pdf').rename(pdfs / 'other.pdf')
        errors, manifest = self.pack({'requirements': str(self.base.inputs), 'datasheets': str(pdfs)})
        self.assertEqual((errors, [n for n in manifest['notes'] if 'U9' in n]), ([], []))

    def test_a_citation_into_the_skill_resolves_by_version_and_a_skill_input_is_not_needed(self):
        doc = SKILL_ROOT / 'references' / 'commodity-floors.md'
        self.base.cite(str(doc))
        errors, manifest = self.pack()
        self.assertEqual(errors, [])
        self.assertEqual(manifest['inputs']['skill']['kind'], 'skill')
        self.assertEqual(manifest['inputs']['skill']['path'], str(SKILL_ROOT))
        errors, manifest = self.pack({'requirements': str(self.base.inputs), 'sr-references': str(SKILL_ROOT / 'references')})
        self.assertEqual(errors, [])
        self.assertNotIn('sr-references', manifest['inputs'])
        self.assertTrue(any('sr-references' in n and 'skill_version' in n for n in manifest['notes']), manifest['notes'])

    def test_main_prints_the_notes(self):
        import contextlib, io
        (self.base.work / 'big.md').write_text('x' * (pack_review.EVIDENCE_NOTE_BYTES + 1))
        self.base.cite('big.md')
        argv = [str(self.base.out)] + [a for n, p in self.base.ledger.items() for a in ('--' + n.split('.')[0], p)] + \
               ['--evidence-root', str(self.base.work), '--input', 'requirements=' + str(self.base.inputs)]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = pack_review.main(argv)
        self.assertEqual(code, 0)
        self.assertIn('NOTE: evidence record/evidence/big.md', buf.getvalue())
        self.assertIn('PASS', buf.getvalue())


if __name__ == '__main__':
    unittest.main()

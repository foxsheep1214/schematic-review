import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import datasheet_kinds as dk


def minimal_pdf(path, lines):
    """One-page PDF with a text layer (enough for pdftotext)."""
    stream = 'BT /F1 12 Tf 72 720 Td ' + ' '.join(f'({t}) Tj 0 -16 Td' for t in lines) + ' ET'
    objs = ['<< /Type /Catalog /Pages 2 0 R >>', '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
            '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R '
            '/Resources << /Font << /F1 5 0 R >> >> >>',
            f'<< /Length {len(stream)} >>\nstream\n{stream}\nendstream',
            '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    out, offsets = '%PDF-1.4\n', []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f'{i} 0 obj\n{body}\nendobj\n'
    xref = len(out)
    out += f'xref\n0 {len(objs) + 1}\n0000000000 65535 f \n' + ''.join(f'{o:010d} 00000 n \n' for o in offsets)
    out += f'trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'
    with open(path, 'w', encoding='latin-1') as f:
        f.write(out)


class KindVerificationTests(unittest.TestCase):
    def page(self, text):
        return lambda path, page: text if page == 1 else None

    def test_quote_must_be_on_the_page_and_name_the_kind(self):
        read = self.page('BCX56T series\n80 V, 1 A NPN power bipolar transistors')
        ok = dk.verify({'kind': 'bjt', 'page': 1, 'quote': '80 V, 1 A NPN power bipolar transistors'}, 'x.pdf', read)
        self.assertEqual(ok['status'], 'VERIFIED')
        self.assertEqual(dk.verify({'kind': 'bjt', 'page': 1, 'quote': 'NPN switching transistor'}, 'x.pdf', read)['status'],
                         'QUOTE_NOT_FOUND')
        self.assertEqual(dk.verify({'kind': 'mosfet', 'page': 1, 'quote': 'NPN power bipolar'}, 'x.pdf', read)['status'],
                         'QUOTE_LACKS_TYPE')
        self.assertEqual(dk.verify({'kind': 'bjt', 'page': 2, 'quote': 'NPN'}, 'x.pdf', read)['status'], 'NO_TEXT')
        self.assertEqual(dk.verify({'kind': 'bjt', 'page': 1, 'quote': 'NPN'}, None, read)['status'], 'NO_DOCUMENT')

    def test_spacing_lost_by_extraction_still_matches(self):
        read = self.page('MOSFET\n800VCoolMOS\u00aaP7PowerTransistor  DPAK')
        self.assertEqual(dk.verify({'kind': 'mosfet', 'page': 1, 'quote': 'MOSFET 800V CoolMOS P7 Power Transistor'},
                                   'x.pdf', read)['status'], 'VERIFIED')

    def test_specific_diode_kind_beats_generic_word(self):
        self.assertEqual(dk.cues('ESD Protection Diode'), {'tvs'})
        self.assertEqual(dk.cues('General-purpose Zener diodes'), {'zener'})
        read = self.page('ESD Protection Diode')
        self.assertEqual(dk.verify({'kind': 'diode', 'page': 1, 'quote': 'ESD Protection Diode'}, 'x.pdf', read)['status'],
                         'QUOTE_CONFLICT')

    def test_audit_section_covers_semiconductors_and_suggests_candidates(self):
        materials = [{'status': 'AVAILABLE', 'refdes': ['Q7', 'R1'], 'document': {'path': 'q.pdf'}}]
        orig = dk.page_text
        dk.page_text = lambda path, page: 'General Purpose Transistor NPN Silicon' if page == 1 else None
        try:
            section = dk.audit_kinds(materials, {})
        finally:
            dk.page_text = orig
        self.assertEqual(list(section), ['Q7'])
        self.assertEqual(section['Q7']['status'], 'UNDECLARED')
        self.assertEqual(section['Q7']['candidates'][0]['kind'], 'bjt')

    @unittest.skipUnless(shutil.which('pdftotext'), 'pdftotext not installed')
    def test_real_pdf_text_layer(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'ds.pdf')
            minimal_pdf(path, ['SD05T1 Series', 'ESD Protection Diode'])
            self.assertEqual(dk.verify({'kind': 'tvs', 'page': 1, 'quote': 'ESD Protection Diode'}, path)['status'],
                             'VERIFIED')
            self.assertEqual(len(dk.file_sha256(path)), 64)


if __name__ == '__main__':
    unittest.main()

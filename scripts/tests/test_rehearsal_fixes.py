"""2026-10-10 ASG 演练暴露的 SR 执行问题：严格失败不留 db、空导出日志、文本摘录资料。"""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from audit_datasheets import build_datasheet_audit, validate_datasheet_audit, document_format  # noqa: E402
from lint import Lint  # noqa: E402
from parse_kicad import parse  # noqa: E402
from test_audit_datasheets import sample_db  # noqa: E402
from test_parse_kicad import LIBPARTS, board, comp, net, netlist  # noqa: E402

AMP = LIBPARTS.replace('</libparts>', """
    <libpart lib="Amplifier" part="AMP">
      <pins>
        <pin num="1" name="IN" type="input"/>
        <pin num="2" name="~" type="output"/>
      </pins>
    </libpart>
  </libparts>""")


class StrictParseWritesDb(unittest.TestCase):
    """KiCad 官方运放符号输出脚可无名；严格失败仍须留下可定位的 db。"""

    def run_parser(self, *extra):
        xml = netlist(comp('U9', 'Amplifier', 'AMP', 'AMP'),
                      net('A', ('U9', '1', 'IN', 'input')) + net('B', ('U9', '2', '', 'output')),
                      libparts=AMP)
        with tempfile.TemporaryDirectory() as tmp:
            src, out = pathlib.Path(tmp) / 'n.xml', pathlib.Path(tmp) / 'db.json'
            src.write_text(xml, encoding='utf-8')
            r = subprocess.run([sys.executable, '-B', str(SCRIPTS / 'parse_kicad.py'), str(src),
                                '-o', str(out), *extra], capture_output=True, text=True)
            db = json.loads(out.read_text(encoding='utf-8')) if out.is_file() else None
        return r.returncode, db

    def test_strict_failure_writes_db_marked_failed_and_exits_2(self):
        code, db = self.run_parser()
        self.assertEqual(code, 2)
        self.assertIsNotNone(db)
        self.assertIs(db['integrity']['self_check_passed'], False)
        self.assertEqual(db['pin_name_coverage']['missing_functional_pins'], ['U9.2'])

    def test_no_strict_only_changes_the_exit_code(self):
        code, db = self.run_parser('--no-strict')
        self.assertEqual(code, 0)
        self.assertIs(db['integrity']['self_check_passed'], False)


class ExportLog(unittest.TestCase):
    def skipped(self, *args):
        lint = Lint(parse(board()), *args)
        lint.run()
        return {rule for rule, _, _ in lint.skipped}

    def test_missing_log_skips_doc_a_rules(self):
        self.assertTrue({'DOC-A01', 'DOC-A02'} <= self.skipped())

    def test_empty_log_from_successful_kicad_export_is_scanned(self):
        self.assertFalse({'DOC-A01', 'DOC-A02'} & self.skipped(''))


class TextOnlyDatasheet(unittest.TestCase):
    def audit(self, suffix):
        with tempfile.TemporaryDirectory() as tmp:
            doc = pathlib.Path(tmp) / ('reg-x' + suffix)
            doc.write_bytes(b'%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\n%%EOF\n') if suffix == '.pdf' else doc.write_text('REG-X datasheet text', encoding='utf-8')
            resolution = {'schema_version': 1, 'entries': [{
                'identity': 'REG-X', 'status': 'FOUND', 'identity_verified': True,
                'source_kind': 'network', 'path': str(doc),
                'source_url': 'https://example.test/reg-x.pdf', 'document_model': 'REG-X',
                'document_version': 'Rev.A', 'retrieved_at': '2026-10-10'}]}
            return build_datasheet_audit(sample_db(), resolution=resolution, resolution_base=tmp)

    def material(self, audit):
        return next(m for m in audit['materials'] if m['identity'] == 'REG-X')

    def test_text_extract_is_available_but_labelled(self):
        audit = self.audit('.md')
        material = self.material(audit)
        self.assertEqual(material['status'], 'AVAILABLE')
        self.assertEqual(material['document']['document_format'], 'text_extract')
        self.assertEqual(audit['summary']['available_text_only'], 1)
        self.assertIn('DATASHEET_TEXT_ONLY', {d['code'] for d in audit['diagnostics']})
        self.assertEqual(validate_datasheet_audit(audit), [])

    def test_pdf_original_is_not_flagged(self):
        audit = self.audit('.pdf')
        self.assertEqual(self.material(audit)['document']['document_format'], 'pdf')
        self.assertEqual(audit['summary']['available_text_only'], 0)
        self.assertNotIn('DATASHEET_TEXT_ONLY', {d['code'] for d in audit['diagnostics']})

    def test_relabelling_a_text_extract_as_pdf_is_rejected(self):
        audit = self.audit('.md')
        self.material(audit)['document']['document_format'] = 'pdf'
        self.assertTrue(any('document_format' in e for e in validate_datasheet_audit(audit)))
        with tempfile.TemporaryDirectory() as tmp:
            renamed = pathlib.Path(tmp) / 'text-renamed.pdf'
            renamed.write_text('REG-X text; no original PDF bytes', encoding='utf-8')
            self.assertEqual(document_format(renamed), 'text_extract')
            self.material(audit)['document']['path'] = str(renamed)
            self.assertTrue(any('document_format' in e for e in validate_datasheet_audit(audit)))


if __name__ == '__main__':
    unittest.main()

"""gap_inventory groups waiting inputs by who supplies them and ranks by checks unblocked."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gap_inventory


def plan():
    rows = [('PWR-C09.A', ['population:C1', 'component-kind:C1', 'official-full-pinout:U1']),
            ('PWR-C09.B', ['population:C2', 'intent.devices.U1: official full pinout + exact MPN/package']),
            ('PWR-C01.V', ['power_rails.3.3V.citation', 'power_rails.3.3V.load_a.min/max']),
            ('SIG-E01.I2C', ['datasheet/platform:I2C pull requirement']),
            ('DEV-C01.BOARD', ['datasheets', 'requirements'])]
    checks = [{'id': i, 'rule': i.split('.')[0], 'readiness': 'WAITING_EVIDENCE', 'required_inputs': r}
              for i, r in rows]
    checks.append({'id': 'NET-A01.X', 'rule': 'NET-A01', 'readiness': 'READY', 'required_inputs': []})
    return {'checks': checks}


class GapInventoryTest(unittest.TestCase):
    def test_one_bom_and_one_datasheet_per_part(self):
        inv = gap_inventory.build(plan())
        assembly = inv['by_owner']['assembly']
        self.assertEqual(len(assembly), 1)
        self.assertEqual((assembly[0]['input'], assembly[0]['refs'], assembly[0]['unblocks']),
                         ('population', ['C1', 'C2'], 2))
        part = next(r for r in inv['by_owner']['part_data'] if r['refs'] == ['U1'])
        self.assertEqual((part['input'], part['unblocks']), ('U1 的器件资料', 2))
        rails = inv['by_owner']['requirements']
        self.assertIn('power_rails.3.3V', [r['input'] for r in rails])
        self.assertEqual(inv['by_owner']['reviewer'][0]['input'], 'component-kind')
        self.assertFalse(any(r['refs'] == ['I2C'] for rows in inv['by_owner'].values() for r in rows))
        self.assertEqual(inv['summary']['waiting_checks'], 5)

    def test_audit_missing_material_is_a_part_data_request(self):
        audit = {'materials': [{'identity': 'CTRL-1', 'refdes': ['U1'], 'status': 'NOT_FOUND'}]}
        rows = gap_inventory.build(plan(), audit)['by_owner']['part_data']
        self.assertIn('U1 的器件资料', [r['input'] for r in rows])

    def test_cli_writes_markdown_and_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, js, md = (Path(tmp) / n for n in ('plan.json', 'gap.json', 'gap.md'))
            src.write_text(json.dumps(plan()))
            self.assertEqual(gap_inventory.main([str(src), '--json', str(js), '--md', str(md)]), 0)
            self.assertIn('| population（2 个位号） | C1、C2 | 2 |', md.read_text())
            self.assertEqual(json.loads(js.read_text())['schema_version'], 1)
            src.write_text('[]')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(gap_inventory.main([str(src)]), 2)


if __name__ == '__main__':
    unittest.main()


class CommodityTest(unittest.TestCase):
    """R6 acceptance 2026-10-24, codex1 SR-01: plain resistors and capacitors are judged on conservative floors; their
    datasheets are the reviewer's own tracking, one line, never a request per part to the designer."""

    def test_plain_rc_datasheets_are_one_reviewer_line_not_part_requests(self):
        checks = [{'id': 'DEV-C01.X', 'rule': 'DEV-C01', 'readiness': 'WAITING_EVIDENCE',
                   'required_inputs': ['datasheet:C603', 'datasheet:R503', 'datasheet:U601', 'datasheet:CX101']}]
        audit = {'materials': [{'identity': 'R-0603-10K', 'refdes': ['R12', 'R13'], 'status': 'NOT_FOUND'},
                               {'identity': 'TH-NTC', 'refdes': ['TH101'], 'status': 'NOT_FOUND'}]}
        inv = gap_inventory.build({'checks': checks}, audit)
        parts = [r['refs'] for r in inv['by_owner']['part_data']]
        self.assertEqual(sorted(map(tuple, parts)), [('CX101',), ('TH101',), ('U601',)])
        reviewer = [r for r in inv['by_owner']['reviewer'] if r['input'] == gap_inventory.COMMODITY_INPUT]
        self.assertEqual(len(reviewer), 1)
        self.assertEqual(reviewer[0]['refs'], ['C603', 'R12', 'R13', 'R503'])
        self.assertNotIn('C603', inv['by_ref'])

"""The BOM's own columns reach the plan: a part's specification written beside its value was read by one reviewer and
missed by another, who then called a custom magnetic part unspecified."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import read_bom

BOM = '''Reference,Value,MPN,Footprint,Electrical specification,Selection status
T1,300uH 48:6:21,CUSTOM-T1,,Lp±10%，漏感≤1.2µH,candidate
"R1, R2",10k,,,,candidate
C1,10u/160V,,,10µF±20%/160V/105°C,candidate
X9,1k,,,,candidate
'''


def db():
    return {'parts': {ref: {'value': '', 'part': ''} for ref in ('T1', 'R1', 'R2', 'C1', 'U1')}}


def read(text=BOM):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'BOM.csv'
        path.write_text(text, encoding='utf-8')
        return read_bom.read(path, db())


class ReadBomTests(unittest.TestCase):
    def test_each_part_keeps_its_own_non_empty_columns(self):
        bom = read()
        self.assertEqual(bom['parts']['T1'], {'MPN': 'CUSTOM-T1', 'Electrical specification': 'Lp±10%，漏感≤1.2µH'})
        self.assertEqual(bom['parts']['C1']['Electrical specification'], '10µF±20%/160V/105°C')

    def test_one_line_may_name_several_parts(self):
        bom = read()
        self.assertIn('R1', bom['parts'])
        self.assertIn('R2', bom['parts'])

    def test_a_column_written_the_same_on_every_line_says_nothing_about_a_part(self):
        bom = read()
        self.assertNotIn('Selection status', bom['parts']['T1'])
        self.assertEqual(bom['uniform_columns'], ['Selection status'])

    def test_parts_on_one_side_only_are_listed(self):
        bom = read()
        self.assertEqual((bom['not_in_netlist'], bom['not_in_bom']), (['X9'], ['U1']))

    def test_a_bom_without_a_reference_column_is_refused(self):
        with self.assertRaises(ValueError):
            read('Part,Value\nR1,10k\n')

    def test_the_command_writes_the_bom_into_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            bom_path, db_path = Path(tmp) / 'BOM.csv', Path(tmp) / 'db.json'
            bom_path.write_text(BOM, encoding='utf-8')
            db_path.write_text(json.dumps(db()), encoding='utf-8')
            read_bom.main([str(db_path), str(bom_path)])
            written = json.loads(db_path.read_text(encoding='utf-8'))
            self.assertEqual(written['bom']['parts']['T1']['MPN'], 'CUSTOM-T1')
            self.assertEqual(len(written['bom']['sha256']), 64)


class PlanTests(unittest.TestCase):
    def test_a_frame_and_a_device_row_carry_their_parts_bom_text(self):
        from test_interface_rows import fx, plan_for
        board = fx.board()
        board['bom'] = {'parts': {'F1': {'Electrical specification': 'T2A 250Vac'}, 'U1': {'MPN': 'U1-EXACT'}}}
        plan = plan_for(board)
        frame = next(f for f in plan['functions'] if 'F1' in f['objects']['refs'])
        self.assertEqual(frame['bom_specs'], {'F1': {'Electrical specification': 'T2A 250Vac'}})
        row = next(c for c in plan['checks'] if c['id'] == 'DEV-D01.U1')
        self.assertEqual(row['bom_fields'], {'MPN': 'U1-EXACT'})
        self.assertNotIn('bom_specs', next(f for f in plan['functions'] if 'F1' not in f['objects']['refs']
                                           and f.get('circuit')))


if __name__ == '__main__':
    unittest.main()

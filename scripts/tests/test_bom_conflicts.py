"""A BOM line that says one thing twice and differently is a DEV-D04 row of its own part (R8: R604's tolerance column
1 % against its specification 5 %; RV101, a varistor, filed under a thick-film resistor category). The R8 reviewer found
both by hand and added them as rule gaps; the planner now finds them."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import read_bom as bc
import part_words as pw
from plan_review import build_review_plan
from test_optocoupler import opto_board


def spec(**fields):
    return {'规格与约束': json.dumps(fields, ensure_ascii=False)}


class BomConflictTests(unittest.TestCase):
    def test_a_tolerance_written_twice_differently_is_a_conflict(self):
        [c] = bc.bom_conflicts(spec(容差='1%', Specification='75ohm 5% 3W；100°C起始脉冲≥0.8J'), pw.RESISTOR)
        self.assertEqual((c['field'], c['says']), ('tolerance', ['容差：1%', 'Specification：5%']))
        self.assertEqual(bc.bom_conflicts(spec(容差='1%', Specification='容差 1%；额定 0.125W'), pw.RESISTOR), [])
        self.assertEqual(bc.bom_conflicts({'容差': '5%', 'Note': '降额 ≤50% 额定功率'}, pw.RESISTOR), [])

    def test_a_category_of_another_family_is_a_conflict(self):
        [c] = bc.bom_conflicts(spec(Kind='varistor', Category='22_电阻器/厚膜贴片电阻 (通用)'), pw.VARISTOR)
        self.assertEqual(c['field'], 'category')
        for kind, category in ((pw.VARISTOR, '28_保护器件/压敏电阻 (MOV)'), (pw.NTC, '22_电阻器/热敏电阻'),
                               (pw.RESISTOR, '22_电阻器/功率电阻'), (pw.CAPACITOR, '20_电容器/铝电解电容'),
                               (pw.IC, '30_集成电路/LDO'), (pw.UNKNOWN, '22_电阻器')):
            self.assertEqual(bc.bom_conflicts(spec(Category=category), kind), [], (kind, category))

    def test_the_plan_has_a_row_for_the_conflicting_part_only(self):
        db = opto_board()
        db['bom'] = {'parts': {'R1': spec(容差='1%', Specification='1k 5%'), 'R2': spec(容差='1%', Specification='10k 1%')}}
        rows = [c for c in build_review_plan(db)['checks'] if c['rule'] == 'DEV-D04']
        self.assertEqual(sorted(c['id'] for c in rows), ['DEV-D04.BOARD', 'DEV-D04.BOM.R1'])
        row = next(c for c in rows if c['id'] == 'DEV-D04.BOM.R1')
        self.assertIn('容差：1%', row['criterion'])
        self.assertEqual(row['object']['ref'], 'R1')


if __name__ == '__main__':
    unittest.main()

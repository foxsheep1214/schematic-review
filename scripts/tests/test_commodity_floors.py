"""The commodity floors (chip-resistor floors, orderable MLCC rows, contact floors) live once, in the framework's
常规件最弱档.json, which passive_stress reads; references/commodity-floors.md keeps only the review method and points
to the framework's 常规件最弱档.md for the numbers."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))

import guideline_criteria
from checkers import passive_stress

FLOORS = guideline_criteria.commodity_floors()
DOC = (ROOT / 'references' / 'commodity-floors.md').read_text(encoding='utf-8')


class CommodityFloorsTests(unittest.TestCase):
    def test_passive_stress_reads_the_shared_floors(self):
        packages = FLOORS['chip_resistor']['packages']
        self.assertEqual(passive_stress.RESISTOR_FLOORS, {p: (v['power_w_70c'], v['voltage_v']) for p, v in packages.items()})
        self.assertEqual(passive_stress.MLCC_ORDERABLE,
                         tuple((r['package'], r['max_f'], r['voltage_v'], r['part']) for r in FLOORS['mlcc_orderable']['rows']))
        self.assertEqual(passive_stress.WEAKEST_SHARE, guideline_criteria.engineering_value('weakest_share'))

    def test_the_method_doc_points_to_the_framework_and_carries_no_floor_table(self):
        self.assertIn('G10_元器件降额与应力规范/常规件最弱档.md', DOC)
        for key in ('chip_resistor', 'mlcc_orderable', 'contacts'):
            self.assertIn('`%s`' % key, DOC)
        self.assertNotRegex(DOC, r'(?m)^\| (?:0\d{3}|1\d{3}|2\d{3}) \|')          # no package rows
        for row in FLOORS['mlcc_orderable']['rows'] + FLOORS['contacts']['rows']:
            self.assertNotIn(row.get('part') or row['category'], DOC)


if __name__ == '__main__':
    unittest.main()

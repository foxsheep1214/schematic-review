"""The commodity floors (chip-resistor floors, orderable MLCC rows, contact floors) live once, in the shared layer's
commodity-floors.json, which passive_stress reads; references/commodity-floors.md shows the same numbers and this test
keeps the tables and the file equal (user 2026-11-02: 最弱档收进共用层)."""
import re
import sys
import unittest
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))

import guideline_criteria
from checkers import passive_stress

FLOORS = guideline_criteria.commodity_floors()
DOC = (ROOT / 'references' / 'commodity-floors.md').read_text(encoding='utf-8')
EXPONENT = {'p': -12, 'n': -9, 'µ': -6, 'u': -6, 'm': -3, '': 0}


def watts(text):
    m = re.fullmatch(r'(\d+)/(\d+) W|(\d+(?:\.\d+)?) W', text)
    return float(Fraction(int(m.group(1)), int(m.group(2)))) if m.group(1) else float(m.group(3))


class CommodityFloorsTests(unittest.TestCase):
    def test_passive_stress_reads_the_shared_floors(self):
        packages = FLOORS['chip_resistor']['packages']
        self.assertEqual(passive_stress.RESISTOR_FLOORS, {p: (v['power_w_70c'], v['voltage_v']) for p, v in packages.items()})
        self.assertEqual(passive_stress.MLCC_ORDERABLE,
                         tuple((r['package'], r['max_f'], r['voltage_v'], r['part']) for r in FLOORS['mlcc_orderable']['rows']))
        self.assertEqual(passive_stress.WEAKEST_SHARE, guideline_criteria.engineering_value('weakest_share'))

    def test_the_chip_resistor_table_is_the_file(self):
        rows = re.findall(r'^\| (0\d{3}|1\d{3}|2\d{3}) \| (\S+ W) \| (\d+) V \|$', DOC, flags=re.M)
        self.assertEqual({p: (watts(w), float(v)) for p, w, v in rows},
                         {p: (v['power_w_70c'], v['voltage_v']) for p, v in FLOORS['chip_resistor']['packages'].items()})

    def test_the_mlcc_table_is_the_file(self):
        rows = re.findall(r'^\| (0\d{3}) \| (\d+) ([pnµum]?)F \| (\d+) V \| (.+?)（', DOC, flags=re.M)
        self.assertEqual([(p, float('%se%d' % (c, EXPONENT[u])), float(v), part)
                          for p, c, u, v, part in rows],
                         [(r['package'], r['max_f'], r['voltage_v'], r['part']) for r in FLOORS['mlcc_orderable']['rows']])

    def test_the_contact_table_is_the_file(self):
        rows = re.findall(r'^\| (.+?) \| (\d+(?:\.\d+)?) (m?)A / (?:(\d+) VDC（阻性）|触点) \| (.+) \|$', DOC, flags=re.M)
        got = []
        for category, current, milli, volts, basis in rows:
            v = volts or (re.search(r'，(\d+) V', basis) or [None, None])[1]
            got.append((category, float(current) / 1000 if milli else float(current), float(v) if v else None))
        self.assertEqual(got, [(r['category'], r['current_a'], r.get('voltage_v')) for r in FLOORS['contacts']['rows']])
        self.assertEqual(len(got), 7)


class GeneratedTablesTests(unittest.TestCase):
    def test_regeneration_has_no_difference(self):
        from render_commodity_floors import render_doc
        self.assertEqual(render_doc(DOC), DOC)

    def test_modified_json_changes_each_numeric_table_and_keeps_explanation(self):
        import copy
        from render_commodity_floors import render_doc
        data = copy.deepcopy(FLOORS)
        data['chip_resistor']['packages']['0402']['voltage_v'] = 23
        data['mlcc_orderable']['rows'][0]['voltage_v'] = 49
        data['contacts']['rows'][0]['current_a'] = 0.049
        rendered = render_doc(DOC, data)
        self.assertIn('| 0402 | 1/16 W | 23 V |', rendered)
        self.assertIn('| 0402 | 100 nF | 49 V |', rendered)
        self.assertIn('| 轻触开关：Omron B3U | 49 mA / 12 VDC（阻性） |', rendered)
        self.assertEqual(render_doc(rendered, data), rendered)
        self.assertIn('LED 的光度测试电流不能用于证明', rendered)


if __name__ == '__main__':
    unittest.main()

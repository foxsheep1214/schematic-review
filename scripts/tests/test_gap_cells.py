"""A vendor-datum gap names the cell of its parameter (2026-10-26, user: 四类格子兜底改为超出规定区……堵住选 NONE 绕过格子的口子).

R7/R8 held design risks as vendor data: a pin driven past its absolute maximum with no injection rating (four times),
a switch past its SOA chart, a capacitor past its rated voltage with no surge rating. Their cells (the new
IC-PIN-ABSMAX, MOS-DISCHARGE-I2T, CAP-SURGE-V, also IC-IO-CURRENT and DIODE-SURGE) now fall back to
OUTSIDE_SPECIFIED: past the specified region the item is a fail, not a request. Six of the 22 gaps wrote cell NONE and
thirteen none at all, which skipped every cell rule; a gap whose words name a cell now names it or says why not.
"""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import catalog
from review_functions import function_errors
from test_review_functions import with_datum
from test_one_sided_bounds import unboundable


def errors(fn):
    return function_errors({'functions': [fn]})


def gap(what, cell='NONE', against='HV 脚下限', **extra):
    fn = with_datum()
    item = fn['open'][0]
    item['what'] = what
    item['worst_case']['margin']['against'] = against
    item['worst_case']['margin']['basis']['cell'] = cell
    item.update(extra)
    return fn


class CellTests(unittest.TestCase):
    def test_the_four_cells_and_the_new_pin_cell_fall_back_to_outside_specified(self):
        for cell in ('IC-PIN-ABSMAX', 'MOS-DISCHARGE-I2T', 'CAP-SURGE-V', 'IC-IO-CURRENT', 'DIODE-SURGE', 'ZENER-VZ-LOWER'):
            self.assertEqual(catalog.BOUNDS[cell].fallback, 'OUTSIDE_SPECIFIED', cell)
        self.assertEqual(catalog.cells_named_by('U601 6.5 V 脚绝限'), ['IC-PIN-ABSMAX'])

    def test_a_public_bound_on_an_outside_specified_cell_is_a_fail_item(self):
        found = errors(gap('输入电压短时超过 HV 额定', cell='CAP-SURGE-V'))
        self.assertTrue(any('has no vendor gap' in e and 'CAP-SURGE-V' in e for e in found), found)


class NamedCellTests(unittest.TestCase):
    def test_a_baseline_gap_whose_words_name_no_cell_passes(self):
        self.assertEqual(errors(gap('HV 脚启动电流下限只在 25 °C 给出')), [])

    def test_cell_none_while_the_words_name_a_cell_is_refused(self):
        found = errors(gap('光耦 CTR 全温下限没有给出'))
        self.assertTrue(any('OPTO-CTR' in e and 'cell_reason' in e for e in found), found)
        fn = gap('光耦 CTR 全温下限没有给出')
        del fn['open'][0]['worst_case']['margin']['basis']['cell']
        self.assertTrue(any('missing' in e and 'OPTO-CTR' in e for e in errors(fn)))

    def test_another_cell_while_the_words_name_an_outside_specified_parameter_is_refused(self):
        # R8 codex1: cell TVS-VC, margin against the controller pin's absolute maximum
        fn = gap('单级 TVS 钳位与控制器脚的脉冲耐受未能配合', cell='TVS-VC', against='U601 6.5 V 脚绝限')
        found = errors(fn)
        self.assertTrue(any('IC-PIN-ABSMAX' in e and 'no vendor gap' in e for e in found), found)

    def test_the_unboundable_reason_is_read_too(self):
        # R7 codex1 CS-SHORT-INJECTION: cell NONE, "负向注入", the reason says "−0.3V直流绝限"
        fn = unboundable()
        item = fn['open'][0]
        del item['cell_reason']
        item['what'], item['why_insufficient'] = '短路储能释放把检流脚拉低', '差分滤波不约束共模负脉冲'
        item['worst_case']['monotonic_tried']['quantity'] = '检流脚可承受的负向脉冲'
        item['worst_case']['not_boundable_reason'] = 'CS±只有−0.3V直流绝限，没有允许脉冲包络'
        self.assertTrue(any('IC-PIN-ABSMAX' in e for e in errors(fn)), errors(fn))

    def test_a_gap_already_on_an_outside_specified_cell_is_not_sent_to_another(self):
        # R8 codex3 FAULT-ZENER-WINDOW: cell ZENER-VZ-LOWER, words "外部注入"; the cell rule refuses it, not this one
        fn = unboundable()
        item = fn['open'][0]
        del item['cell_reason']
        item['what'] = '故障脚外部注入电流低于齐纳最低测试电流'
        item['worst_case']['monotonic_tried']['cell'] = 'ZENER-VZ-LOWER'
        found = errors(fn)
        self.assertFalse([e for e in found if 'name that cell' in e], found)
        self.assertTrue(any('ZENER-VZ-LOWER' in e for e in found), found)

    def test_a_reason_why_the_named_cells_do_not_apply_lets_it_stand(self):
        fn = gap('光耦 CTR 全温下限没有给出', cell_reason='这里缺的是 HV 脚启动电流，CTR 只是描述链路')
        self.assertFalse([e for e in errors(fn) if 'cell_reason' in e or 'no vendor gap' in e], errors(fn))


if __name__ == '__main__':
    unittest.main()

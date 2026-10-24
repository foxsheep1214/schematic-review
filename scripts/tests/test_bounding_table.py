"""The operating-point bounding table (bounding table proposal of 2026-10-23; decision A: "必须按表").

Each cell of `catalog.BOUNDS` says, for one parameter of one device class, what it varies with and which way, the
bounding methods allowed in order with their formulas (`bound_formulas`), and where it falls when they all fail. A
vendor datum called unboundable names its cell (`monotonic_tried.cell`, or NONE outside the table): a cell that always
bounds, or whose fallback is the region outside the datasheet, is not opened as unboundable, and a test point on the
favourable side of a monotonic parameter bounds it. A margin that names its cell follows the cell's methods, and the
gate reruns the formula it names.
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bound_formulas
import catalog
from review_functions import function_errors
from test_one_sided_bounds import unboundable
from test_review_functions import bias_function

ROOT = Path(__file__).resolve().parents[2]


def errors(fn):
    return function_errors({'functions': [fn]})


def about(found, word):
    return [e for e in found if word in e]


class TableTests(unittest.TestCase):
    def test_every_cell_is_written_in_the_table_vocabulary(self):
        for b in catalog.BOUNDS.values():
            self.assertTrue(b.kinds and b.parameter and b.varies_with and b.source, b.id)
            self.assertIn(b.side, ('UPPER', 'LOWER', None), b.id)
            self.assertIn(b.direction, catalog.BOUND_DIRECTIONS + (None,), b.id)
            self.assertIn(b.fallback, catalog.BOUND_FALLBACKS, b.id)
            for code, formulas in b.methods:
                self.assertIn(code, catalog.BOUND_METHODS, b.id)
                for name in formulas:
                    self.assertIn(name, bound_formulas.FORMULAS, b.id)

    def test_a_monotonic_cell_the_gate_bounds_by_g2_allows_g2(self):
        # the gate refuses to open such a cell when a favourable test point exists (G2), so a margin by G2 is allowed
        for b in catalog.BOUNDS.values():
            if b.direction in ('INCREASING', 'DECREASING') and b.fallback == 'VENDOR_DATUM':
                self.assertIn('G2', dict(b.methods), b.id)

    def test_a_reference_circuit_covers_a_board_load_no_heavier_than_its_own(self):
        self.assertIn('本板负载不重于参考电路', catalog.BOUND_METHODS['G10'].name)

    def test_the_decided_cells(self):
        cell = catalog.BOUNDS
        self.assertEqual(dict(cell['ZENER-VZ-LOWER'].methods)['G3'], ('slope_bound',))   # 1-A
        self.assertIn('G8', dict(cell['ZENER-VZ-LOWER'].methods))   # 2-A
        self.assertEqual(cell['MOS-SOA-HOT'].fallback, 'BOUNDED')   # B
        self.assertIn('heatsink_requirement', dict(cell['MOS-SOA-HOT'].methods)['SOA'])
        self.assertEqual(dict(cell['NTC-SENSE'].methods)['G5'], ('ntc_table_bound', 'ntc_beta_bound'))   # C
        self.assertEqual(cell['NTC-SENSE'].fallback, 'BOUNDED')
        self.assertEqual(dict(cell['BJT-SAT'].methods)['FORCED_BETA'], ('forced_beta_base_current',))   # D
        self.assertEqual(cell['NTC-INRUSH-HOT'].fallback, 'BOUNDED')   # E

    def test_the_cells_of_a_device_class(self):
        self.assertEqual([b.id for b in catalog.bounds_for(['zener'])],
                         ['ZENER-VZ-UPPER', 'ZENER-VZ-LOWER', 'ZENER-VZ-TEMP', 'DIODE-IR-HOT'])
        self.assertEqual(catalog.bounds_for(['connector']), [])

    def test_the_reference_document_is_generated_from_the_table(self):
        path = ROOT / 'references' / 'bounding-table.md'
        text = path.read_text(encoding='utf-8')
        self.assertEqual(text, catalog.render_doc(text),
                         'run: python3 scripts/catalog.py --write-doc references/bounding-table.md')


def open_with(cell, **monotonic):
    fn = unboundable(cell=cell, **monotonic)
    for edge in fn['open'][0]['decides']:
        edge['side'] = monotonic.get('side', 'LOWER')
    return fn


class UnboundableTests(unittest.TestCase):
    def test_an_unboundable_datum_names_its_cell(self):
        self.assertEqual(errors(open_with('ZENER-VZ-LOWER')), [])
        self.assertEqual(errors(open_with('NONE')), [])
        self.assertTrue(about(errors(open_with(None)), 'cell'))
        self.assertTrue(about(errors(open_with('ZENER-VZ-LOW')), 'bounding table'))

    def test_the_cell_says_which_side_it_bounds(self):
        found = errors(open_with('ZENER-VZ-UPPER'))
        self.assertTrue(about(found, 'ZENER-VZ-UPPER') and about(found, 'UPPER'), found)

    def test_a_cell_that_always_bounds_is_not_opened(self):
        found = errors(open_with('NTC-SENSE'))
        self.assertTrue(about(found, 'always bounds'), found)

    def test_a_cell_falling_outside_the_specified_region_is_a_fail(self):
        found = errors(open_with('REF-IKA-MIN'))
        self.assertTrue(about(found, 'outside_specified'), found)

    def test_a_test_point_on_the_favourable_side_bounds_a_monotonic_parameter(self):
        # VZ grows with IZ: the 5 mA maximum bounds VZ from above at every lower current
        found = errors(open_with('ZENER-VZ-UPPER', side='UPPER'))
        self.assertTrue(about(found, 'G2'), found)
        below = [{'condition': 'z1', 'at': {'value': 1, 'unit': 'mA'}}]
        self.assertEqual(errors(open_with('ZENER-VZ-UPPER', side='UPPER', test_points=below)), [])
        # the 5 mA minimum does not bound VZ from below at lower currents; a point below the range would
        self.assertEqual(errors(open_with('ZENER-VZ-LOWER')), [])
        under = [{'condition': 'z1', 'at': {'value': 0.05, 'unit': 'mA'}}]
        self.assertTrue(about(errors(open_with('ZENER-VZ-LOWER', test_points=under)), 'G2'))

    def test_the_favourable_side_needs_the_limit_on_that_side(self):
        # r1 gives rdif only as a maximum: no minimum to bound from below
        under = [{'condition': 'r1', 'at': {'value': 0.05, 'unit': 'mA'}}]
        self.assertEqual(errors(open_with('ZENER-VZ-LOWER', test_points=under)), [])

    def test_a_decreasing_parameter_is_bounded_from_the_other_end(self):
        hot = {'operating_point': {'min': 25, 'max': 105, 'unit': '°C'}}
        cold = [{'condition': 'z1', 'at': {'value': -40, 'unit': '°C'}}]
        found = errors(open_with('DIODE-VF-COLD', side='UPPER', test_points=cold, **hot))
        self.assertTrue(about(found, 'G2'), found)
        warm = [{'condition': 'z1', 'at': {'value': 125, 'unit': '°C'}}]
        self.assertEqual(errors(open_with('DIODE-VF-COLD', side='UPPER', test_points=warm, **hot)), [])
        self.assertTrue(about(errors(open_with('MLCC-EFFECTIVE-C', test_points=warm, **hot)), 'G2'))

    def test_a_parameter_that_is_not_monotonic_is_not_bounded_by_one_test_point(self):
        self.assertEqual(errors(open_with('ZENER-VZ-TEMP')), [])


SLOPE = {'name': 'slope_bound', 'inputs': {'p0': 15.68, 'x0': 2e-3, 'x': 1e-3, 'slope_max': 170, 'side': 'LOWER'},
         'value': 15.51}


def computed(**basis):
    fn = bias_function('PASS')
    fn['calculation']['margin']['basis'].update(basis)
    return fn


class FormulaTests(unittest.TestCase):
    def test_a_margin_by_a_cell_and_its_formula_passes(self):
        self.assertEqual(errors(bias_function('PASS')), [])
        self.assertEqual(errors(computed(cell='ZENER-VZ-LOWER', method='G3', formula=dict(SLOPE))), [])
        self.assertEqual(errors(computed(cell='ZENER-VZ-LOWER', method='G1')), [])   # a limit read directly

    def test_the_method_is_one_of_the_cell(self):
        self.assertTrue(about(errors(computed(cell='ZENER-VZ-LOWER', method='G4')), 'method'))
        self.assertTrue(about(errors(computed(cell='ZENER-VZ', method='G1')), 'bounding table'))

    def test_a_computed_method_writes_its_formula(self):
        self.assertTrue(about(errors(computed(cell='ZENER-VZ-LOWER', method='G3')), 'formula'))
        other = dict(SLOPE, name='tempco_bound')
        self.assertTrue(about(errors(computed(cell='ZENER-VZ-LOWER', method='G3', formula=other)), 'slope_bound'))

    def test_the_gate_reruns_the_formula(self):
        self.assertEqual(errors(computed(formula=dict(SLOPE, value=15.52))), [])   # within rounding
        found = errors(computed(formula=dict(SLOPE, value=15.6)))
        self.assertTrue(about(found, '15.51'), found)
        broken = copy.deepcopy(SLOPE)
        broken['inputs']['side'] = 'BOTH'
        self.assertTrue(about(errors(computed(formula=broken)), 'does not run'))
        for bad in ({'name': 'guess', 'inputs': {}, 'value': 1}, {'name': 'slope_bound', 'value': 1}, 'slope_bound'):
            self.assertTrue(about(errors(computed(formula=bad)), 'basis.formula'), bad)


if __name__ == '__main__':
    unittest.main()

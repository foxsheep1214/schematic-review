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
import unittest.mock
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

    def test_every_cell_carries_its_decision_boundary(self):
        # 2026-10-26 (user: 判决的边界按器件类型来): availability, the estimates that may pass and their factor,
        # the physical consequence, prototype verifiability and a boundary sentence, in the table's vocabulary
        from electrical_contract import IMPACT_CLASSES
        for b in catalog.BOUNDS.values():
            self.assertIn(b.availability, catalog.BOUND_AVAILABILITY, b.id)
            self.assertTrue(b.consequence and set(b.consequence) <= set(IMPACT_CLASSES), b.id)
            self.assertTrue(b.prototype and set(b.prototype) <= set(catalog.BOUND_PROTOTYPE), b.id)
            self.assertTrue(b.boundary, b.id)
            seen = set()
            for e in b.estimates:
                self.assertGreater(e.factor, 1, b.id)
                self.assertTrue(e.applies and e.applies <= set(IMPACT_CLASSES) - catalog.ESTIMATE_NEVER, b.id)
                self.assertFalse(seen & e.applies, (b.id, 'two estimate rules for one consequence class'))
                seen |= e.applies
                self.assertTrue(e.how, b.id)
                if e.floor is not None:
                    self.assertEqual((len(e.floor), type(e.floor[1])), (2, str), b.id)

    def test_every_cell_that_estimates_names_the_risks_an_estimate_stands_for(self):
        # 2026-10-26 (user: 关键参数表在定界表上扩): a corner passed on an estimate is a pass with a risk of these types
        for bound in catalog.BOUNDS.values():
            risks = catalog.cell_risks(bound.id)
            self.assertEqual(bool(risks), bool(bound.estimates), bound.id)
            self.assertTrue(set(risks) <= set(catalog.ESTIMATE_RISKS), bound.id)
        self.assertEqual(catalog.cell_risks(catalog.NO_CELL), catalog.ESTIMATE_RISKS)
        self.assertEqual(catalog.cell_risks('OPTO-CTR'), ('ENVIRONMENT', 'LIFETIME', 'CONSISTENCY'))

    def test_the_estimate_rule_is_read_by_cell_and_consequence_class(self):
        rule = catalog.estimate_rule
        self.assertEqual(rule('OPTO-CTR', 'REQUIRED_FUNCTION').factor, 2)                 # decision 2026-10-26
        self.assertIsNone(rule('OPTO-CTR', 'COMPONENT_DAMAGE'))                            # a datum, never a damage path
        self.assertEqual(rule('MOS-RDS-HOT', 'COMPONENT_DAMAGE').floor, (20, '°C'))        # decision 2
        self.assertEqual(rule('IND-ISAT', 'COMPONENT_DAMAGE').factor, 1.3)
        self.assertEqual((rule('ZENER-VZ-UPPER', 'REQUIRED_FUNCTION').factor, rule('ZENER-VZ-UPPER', 'COMPONENT_DAMAGE')), (1.5, None))
        # 2026-10-27 (user: 放开第一组（器件自身发热）三格): a part that heats itself passes a damage class on an estimate
        for cell, factor, floor in (('MOS-VGS-ON', 2, (20, '°C')), ('DIODE-IR-HOT', 2, (20, '°C')), ('ECAP-ESR-RIPPLE', 1.3, (10, '°C'))):
            self.assertEqual((rule(cell, 'COMPONENT_DAMAGE').factor, rule(cell, 'COMPONENT_DAMAGE').floor), (factor, floor), cell)
        for cell in ('ZENER-VZ-UPPER', 'IC-THRESHOLD', 'IC-TIMING'):   # protection: unchanged
            self.assertIsNone(rule(cell, 'COMPONENT_DAMAGE'), cell)
        self.assertEqual((rule('IC-QUIESCENT', 'REQUIRED_FUNCTION').factor, rule('IC-QUIESCENT', 'COMPONENT_DAMAGE').factor), (1.3, 1.5))
        for cell in ('FUSE-I2T', 'TVS-VC', 'DIODE-SURGE', 'CAP-SURGE-V', 'MOS-DISCHARGE-I2T', 'REF-IKA-MIN'):
            self.assertIsNone(rule(cell, 'REQUIRED_FUNCTION'), cell)
        for cls in catalog.ESTIMATE_NEVER:
            self.assertIsNone(rule('OPTO-CTR', cls), cls)
        self.assertIsNone(rule('NONE', 'REQUIRED_FUNCTION'))
        self.assertIsNone(rule('NO-SUCH-CELL', 'REQUIRED_FUNCTION'))

    def test_a_hazard_or_core_link_class_is_refused_even_if_a_cell_lists_it(self):
        # the never-estimate classes are a guarantee of estimate_rule itself, not of the table's authoring
        lax = catalog.BOUNDS['OPTO-CTR']._replace(estimates=(catalog.Estimate(2, ('DAMAGE_OR_HAZARD', 'CORE_LINK_LOSS'), None, 'x'),))
        with unittest.mock.patch.dict(catalog.BOUNDS, {'OPTO-CTR': lax}):
            self.assertIsNone(catalog.estimate_rule('OPTO-CTR', 'DAMAGE_OR_HAZARD'))
            self.assertIsNone(catalog.estimate_rule('OPTO-CTR', 'CORE_LINK_LOSS'))

    def test_the_cells_added_for_the_r7_quantities(self):
        for cell, kinds in (('CAP-SURGE-V', ('capacitor', 'electrolytic')), ('MOS-DISCHARGE-I2T', ('mosfet',)),
                            ('IC-GATE-DRIVE-I', ('mosfet',))):
            self.assertEqual(catalog.BOUNDS[cell].kinds, kinds)
            self.assertTrue(catalog.cells_named_by({'CAP-SURGE-V': 'BULK 浪涌电压抬升', 'MOS-DISCHARGE-I2T': 'Q701 短路放电峰流',
                                                    'IC-GATE-DRIVE-I': 'Qg × f 驱动电流'}[cell]).count(cell), cell)

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

    def test_a_zener_below_its_lowest_test_current_is_a_fail_not_a_vendor_request(self):
        # 2026-10-26 (user: 记设计问题): with no curve covering the point, the part is used where the datasheet says
        # nothing; the fix is to raise the current, not to ask the vendor
        found = errors(open_with('ZENER-VZ-LOWER'))
        self.assertTrue(about(found, 'outside_specified') and about(found, 'ZENER-VZ-LOWER'), found)

    def test_a_test_point_on_the_favourable_side_bounds_a_monotonic_parameter(self):
        # VZ grows with IZ: the 5 mA maximum bounds VZ from above at every lower current
        found = errors(open_with('ZENER-VZ-UPPER', side='UPPER'))
        self.assertTrue(about(found, 'G2'), found)
        below = [{'condition': 'z1', 'at': {'value': 1, 'unit': 'mA'}}]
        self.assertEqual(errors(open_with('ZENER-VZ-UPPER', side='UPPER', test_points=below)), [])

    def test_the_favourable_side_needs_the_limit_on_that_side(self):
        # a test point above the range bounds VZ from above only with a maximum there; one with a minimum only does not
        fn = open_with('ZENER-VZ-UPPER', side='UPPER', test_points=[{'condition': 'm1', 'at': {'value': 5, 'unit': 'mA'}}])
        fn['conditions'].append({'id': 'm1', 'kind': 'NUMERIC_LIMIT', 'source': 'evidence/ds/D2.txt', 'refs': ['D2'],
                                 'locator': 'p5 Table 8', 'says': 'VZ ≥ 15.68 V @ IZ 5 mA', 'limit': {'min': 15.68, 'unit': 'V'},
                                 'regime': 'IZ 5 mA', 'use': 'VZ 测试点'})
        fn['open'][0]['checked'].append('m1')
        self.assertFalse(about(errors(fn), 'G2'), errors(fn))

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


class CellRequiredTests(unittest.TestCase):
    """Every decisive margin names its table cell, or NONE: the reviewer looks the parameter up in the table for each
    bound, and a cell with a computing method brings the formula the gate reruns (user decision 2026-10-25)."""

    def test_a_decisive_margin_without_a_cell_is_refused(self):
        fn = bias_function('PASS')
        del fn['calculation']['margin']['basis']['cell']
        self.assertTrue(about(errors(fn), 'names basis.cell'), errors(fn))
        for kind in ('REACHABLE_CASE', 'EXACT_ENVELOPE'):
            fn['calculation']['margin']['basis']['kind'] = kind
            self.assertTrue(about(errors(fn), 'names basis.cell'), kind)

    def test_none_is_a_cell_and_an_estimate_needs_none(self):
        self.assertEqual(errors(bias_function('PASS')), [])     # the fixture writes NONE
        self.assertTrue(about(errors(computed(cell='NONE', method='G1')), 'has no methods'))
        self.assertEqual(errors(computed(cell='NONE', formula=dict(SLOPE))), [])   # a formula may still be rerun
        fn = bias_function('PASS')
        fn['calculation']['margin']['basis'] = {'kind': 'ESTIMATE', 'comparison': 'GE', 'scope': '按典型值估', 'conditions': ['c1']}
        self.assertFalse(about(errors(fn), 'names basis.cell'))

    def test_cells_named_by_parameter_words(self):
        self.assertEqual(catalog.cells_named_by('Q2 VGS(th) 上界 2.0 V'), ['MOS-VGS-ON'])
        self.assertEqual(catalog.cells_named_by('D1 VF 0.45 V @100 mA')[0], 'DIODE-VF')
        self.assertIn('OPTO-CTR', catalog.cells_named_by('U4 CTR 寿命末 34 %'))
        self.assertIn('IC-TIMING', catalog.cells_named_by('tON_MIN 最大 1.10 µs'))
        self.assertEqual(catalog.cells_named_by('VCC(off) max 8.8 V'), [])
        self.assertEqual(catalog.cells_named_by(None), [])


if __name__ == '__main__':
    unittest.main()

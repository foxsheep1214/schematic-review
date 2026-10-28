"""One defect lands on the aspect its margin proves, and how a datasheet's silence is judged (consistency proposals
of 2026-10-23, 5a and 5c).

Two reviews of one board copied one shortfall into three identical margins on three aspects, and judged a pin
sinking an LED current the datasheet gives no number for once as a design defect and once not at all. The four tiers:
a limit exceeded fails on its margin; the vendor's reference circuit with the same connection and a load no heavier
passes on that circuit; a usage the datasheet describes without the number is a vendor datum; a usage it does not
describe, or a point outside its ratings, fails as outside the specified region.
"""
import copy
import unittest

from test_review_functions import ASPECT, HV_TRIED, STATES, bias_function, guaranteed, with_datum
from function_reading import judged
from review_functions import function_errors

REFERENCE = {'id': 'c6', 'kind': 'TYPICAL_REFERENCE', 'source': 'evidence/ds/U1.txt', 'locator': 'p21 Figure 20 典型应用电路', 'refs': ['U1'],
             'says': '光耦 LED 经 1 kΩ 接 OPTO 脚', 'use': '同样的接法',
             'reference_circuit': {'figure': 'p21 Figure 20', 'connection': '本板 OPTO 脚同样经电阻接光耦 LED 阴极',
                                   'load': '参考图 1 kΩ，本板 2.2 kΩ，LED 电流更小'}}


def errors(fn, findings=()):
    return function_errors({'functions': [fn], 'findings': list(findings)})


class DuplicateMarginTests(unittest.TestCase):
    def test_one_margin_copied_onto_another_aspect_is_refused(self):
        fn = bias_function('PASS')
        margin = fn['calculation']['margin']
        fn['calculation']['margin'] = [margin, dict(copy.deepcopy(margin), aspect='启动与关断时序')]
        found = errors(fn)
        self.assertTrue(any('same margin' in e for e in found), found)

    def test_different_quantities_on_two_aspects_are_kept(self):
        fn = bias_function('PASS')
        margin = fn['calculation']['margin']
        fn['calculation']['margin'] = [margin, dict(copy.deepcopy(margin), aspect='启动与关断时序', value=1.3)]
        self.assertFalse([e for e in errors(fn) if 'same margin' in e])


class ReferenceCircuitTests(unittest.TestCase):
    """Tier 2: a judgement may rest on the vendor's reference circuit when it states the same connection and the load."""

    def judged_by(self, reference):
        fn = bias_function('PASS')
        fn['conditions'].append(reference)
        fn['judgements'] = [{'aspect': '启动与关断时序', 'conditions': ['c6'], 'says': '与原厂典型电路接法相同、负载更轻',
                             'states': list(STATES)}]
        return fn

    def test_the_reference_circuit_settles_the_aspect(self):
        fn = self.judged_by(copy.deepcopy(REFERENCE))
        self.assertEqual(errors(fn), [])
        self.assertIn('厂家参考电路', judged(fn, '启动与关断时序', 'RUN'))

    def test_a_typical_circuit_without_the_comparison_settles_nothing(self):
        bare = copy.deepcopy(REFERENCE); del bare['reference_circuit']
        self.assertTrue(any('rests on no mandatory clause' in e for e in errors(self.judged_by(bare))))
        for field in ('figure', 'connection', 'load'):
            broken = copy.deepcopy(REFERENCE); del broken['reference_circuit'][field]
            self.assertTrue(any('reference_circuit' in e for e in errors(self.judged_by(broken))), field)
        broken = copy.deepcopy(REFERENCE); broken['reference_circuit']['figure'] = '典型电路'
        self.assertTrue(any('reference_circuit' in e for e in errors(self.judged_by(broken))))


class DescribedUsageTests(unittest.TestCase):
    """Tier 3: a usage the datasheet describes without the number is a vendor datum; say where it is described."""

    def unboundable(self, **worst):
        fn = with_datum(not_boundable_reason='手册写了这种用法，没给灌电流', operating_point_specified=True,
                        monotonic_tried=HV_TRIED,
                        curves_checked=[{'source': 'evidence/ds/U1.txt', 'locator': 'p11 电气特性'}], **worst)
        fn['open'][0]['cell_reason'] = '夹具只测第三档的 specified_by；HV 启动电流不是逻辑脚灌电流'
        return fn

    def test_specified_names_the_clause_that_describes_the_usage(self):
        found = errors(self.unboundable())
        self.assertTrue(any('specified_by' in e for e in found), found)
        self.assertEqual(errors(self.unboundable(specified_by='c4')), [])
        self.assertTrue(any('specified_by' in e for e in errors(self.unboundable(specified_by='c5'))))   # a netlist fact
        self.assertTrue(any('specified_by' in e for e in errors(self.unboundable(specified_by='c9'))))


class OutsideSpecifiedTests(unittest.TestCase):
    """Tier 4: a fail outside the specified region lists the operating-condition sections searched, and the pin
    description when the point is a pin's."""

    def failing(self, point, searched):
        fn = bias_function('FAIL'); fn['open'] = []; fn['calculation'].pop('margin')
        fn['fails'] = [{'key': 'PIN-SINK', 'finding_id': 'F1', 'what': 'U1 引脚灌 LED 电流，手册没写',
                        'decides': [{'aspect': ASPECT, 'states': ['LATCH']}],
                        'outside_specified': {'condition': 'c3', 'operating_point': point,
                                              'curves_checked': [{'source': 'evidence/ds/U1.txt', 'locator': l}
                                                                 for l in searched]}}]
        return fn

    FINDING = {'id': 'F1', 'remediation': {'readiness': 'READY'}}

    def test_the_operating_condition_sections_are_searched(self):
        found = errors(self.failing('D2 正向电流 20 µA', ['Fig. 2 IF-VF']), [self.FINDING])
        self.assertTrue(any('recommended operating' in e for e in found), found)
        self.assertEqual(errors(self.failing('D2 正向电流 20 µA', ['Fig. 2 IF-VF', 'p3 推荐工作条件']), [self.FINDING]), [])

    def test_a_pin_point_also_searches_the_pin_description(self):
        found = errors(self.failing('U1 GPIO2 脚灌 4 mA', ['p5 电气特性']), [self.FINDING])
        self.assertTrue(any('pin description' in e for e in found), found)
        self.assertEqual(errors(self.failing('U1 GPIO2 脚灌 4 mA', ['p5 电气特性', 'p4 引脚说明']), [self.FINDING]), [])


if __name__ == '__main__':
    unittest.main()

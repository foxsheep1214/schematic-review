"""The device-kind vocabulary grows with the boards SR meets (2026-10-26, user: 先把 ntc 和压敏电阻两个器件类别补进
part_words 词表和定界表): the R7 board's inrush and sensing thermistors (TH101, TH601) and its varistor (RV101) were
NEW_DEVICE_KIND signals. ntc and varistor are kinds now — by the shared words, by refdes prefix, declared from the
datasheet — the wearout classes and protective-part reading use the kind, and the varistor has its bounding-table cells
with the five boundary columns.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import board_intent
import catalog
import datasheet_kinds
import part_words as pw
from checkers.netgraph import NetGraph


class KindTests(unittest.TestCase):
    def test_the_r7_parts_classify_by_their_words(self):
        two = [('1', '1'), ('2', '2')]
        self.assertEqual(pw.classify('RV101', {'prim': 'Device:Varistor', 'part': 'B72214S0301K101', 'value': 'S14K300'}, 2, two),
                         (pw.VARISTOR, 'part-keyword'))
        self.assertEqual(pw.classify('TH101', {'prim': 'Device:Thermistor_NTC', 'part': 'B57237S0509M000', 'value': '5R/3A'}, 2, two),
                         (pw.NTC, 'part-keyword'))
        self.assertEqual(pw.classify('R9', {'value': 'NTC 10K'}, 2, two), (pw.NTC, 'part-keyword'))
        self.assertEqual(pw.classify('RV9', {'value': '压敏电阻 14D471K'}, 2, two), (pw.VARISTOR, 'part-keyword'))

    def test_a_bare_prefix_is_the_weakest_evidence_and_rv_is_none(self):
        # RV is KiCad's potentiometer prefix too (R_Potentiometer): without the word a bare RV stays unknown
        self.assertEqual(pw.classify('RV3', {'value': '471'}, 2, [('1', '1'), ('2', '2')])[0], pw.UNKNOWN)
        self.assertEqual(pw.classify('RV3', {'prim': 'Device:R_Potentiometer', 'value': '10k'}, 3, [('1', '1'), ('2', '2'), ('3', '3')])[0], pw.UNKNOWN)
        self.assertEqual(pw.classify('TH3', {'value': '10k'}, 2, [('1', '1'), ('2', '2')]), (pw.NTC, 'refdes-prefix'))
        self.assertEqual(pw.classify('RT3', {'value': '10k'}, 2, [('1', '1'), ('2', '2')]), (pw.NTC, 'refdes-prefix'))

    def test_an_ic_or_a_many_pin_part_is_not_an_ntc_by_a_word_in_its_description(self):
        pins = [(str(i), str(i)) for i in range(1, 9)]
        self.assertEqual(pw.classify('U3', {'value': 'BQ24075 charger with NTC input'}, 8, pins), (pw.IC, 'refdes-prefix'))
        self.assertNotEqual(pw.classify('X3', {'value': 'module with NTC and MOV'}, 8, pins)[0], pw.NTC)
        self.assertNotEqual(pw.classify('X3', {'value': 'module with NTC and MOV'}, 8, pins)[0], pw.VARISTOR)

    def test_the_kinds_are_declared_two_terminal_and_the_ntc_is_a_series_link(self):
        self.assertIn('ntc', board_intent.DEVICE_KINDS)
        self.assertIn('varistor', board_intent.DEVICE_KINDS)
        self.assertEqual(pw.classify('TH1', {'value': '10k'}, 2, [], declared='ntc'), (pw.NTC, 'datasheet'))
        self.assertTrue({pw.NTC, pw.VARISTOR} <= pw.TWO_TERMINAL)
        self.assertIn(pw.NTC, pw.PASSIVE_LINKS)          # an inrush limiter sits in the power path
        self.assertNotIn(pw.VARISTOR, pw.PASSIVE_LINKS)  # a varistor shunts, it never carries the path

    def test_the_datasheet_titles_give_the_cues(self):
        self.assertEqual(datasheet_kinds.cues('NTC thermistors for inrush current limiting'), {'ntc'})
        self.assertEqual(datasheet_kinds.cues('SIOV metal oxide varistors, leaded'), {'varistor'})

    def test_the_wearout_classes_read_the_kind_not_only_the_words(self):
        import plan_circuits

        class Planner(plan_circuits.CircuitPlanning):
            def __init__(self):
                pass

            def _bom_fields(self, ref):
                return {}

        # the thermistor's text has no NTC word: the refdes prefix gives the kind, the kind gives the wearout class
        db = {'parts': {'RV1': {'prim': 'Device:Varistor', 'value': '471'}, 'TH1': {'value': '5R/3A'}},
              'pin2net': {'RV1.1': 'L', 'RV1.2': 'N', 'TH1.1': 'L', 'TH1.2': 'L_NTC'},
              'nets': {'L': ['RV1.1', 'TH1.1'], 'N': ['RV1.2'], 'L_NTC': ['TH1.2']},
              'declared_pinname': {'RV1.1': '1', 'RV1.2': '2', 'TH1.1': '1', 'TH1.2': '2'}}
        graph = NetGraph(db)
        self.assertEqual((graph.kind('RV1'), graph.kind('TH1')), (pw.VARISTOR, pw.NTC))
        self.assertEqual((Planner().wearout_class(graph, 'RV1'), Planner().wearout_class(graph, 'TH1')), ('VARISTOR', 'INRUSH_NTC'))

class VaristorCellTests(unittest.TestCase):
    def test_the_three_cells_with_the_five_boundary_columns(self):
        cells = [b for b in catalog.BOUNDS.values() if 'varistor' in b.kinds]
        self.assertEqual([b.id for b in cells], ['VAR-UC', 'VAR-VC', 'VAR-SURGE'])
        for b in cells:
            self.assertIn(b.availability, catalog.BOUND_AVAILABILITY, b.id)
            self.assertEqual(b.estimates, (), b.id)                       # a safety part: no typical-value pass
            self.assertTrue(b.consequence and b.prototype and b.boundary, b.id)
            self.assertIsNone(catalog.estimate_rule(b.id, 'REQUIRED_FUNCTION'), b.id)
        self.assertEqual(catalog.BOUNDS['VAR-UC'].consequence, ('DAMAGE_OR_HAZARD',))
        self.assertEqual(catalog.cells_named_by('RV101 最大持续工作电压 Uc 300 Vrms 对母线 265 Vrms'), ['VAR-UC'])
        self.assertEqual(catalog.cells_named_by('压敏残压 775 V 对整流桥 VRRM'), ['VAR-VC'])
        self.assertIn('VAR-SURGE', catalog.cells_named_by('压敏 8/20 µs 浪涌 4.5 kA 与次数'))

    def test_the_r7_varistor_is_no_longer_a_new_device_kind(self):
        import validate_review as vr
        db = {'parts': {'RV101': {'prim': 'Device:Varistor', 'part': 'B72214S0301K101', 'value': 'S14K300'},
                        'TH101': {'prim': 'Device:Thermistor_NTC', 'part': 'B57237S0509M000', 'value': '5R/3A'}},
              'pin2net': {}, 'nets': {}}
        self.assertEqual(vr.extension_signals({'functions': []}, db), [])


if __name__ == '__main__':
    unittest.main()

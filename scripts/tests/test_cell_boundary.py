"""The estimate-pass boundary is the bounding-table cell's (2026-10-26, user: 判决的边界应该按照器件类型来).

A margin that names a table cell passes on an estimate when the cell's boundary allows that consequence class,
after the value is derated by the cell's factor, with the cell's margin floor; the rule id of the row no longer
decides. Cell NONE keeps the former default (a required function or a performance, not on a damage, overheating or
protection rule). A hazard or core-link class never passes on an estimate.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import derive_rows
import function_reading
import validate_review as vr
from test_estimate_pass import estimated, other_row
from test_review_functions import ASPECT


def margin_of(r):
    return next(m for m in r['functions'][1]['calculation']['margin'] if m.get('aspect') == ASPECT)


def gate(**extra):
    p, r, db = estimated(**extra)
    out = vr.validate_review(p, r, db)
    return [e for e in out['errors'] if 'FN-OTHER/margin' in e], (p, r, db)


class CellBoundaryTests(unittest.TestCase):
    def test_a_cell_that_allows_the_class_passes_whatever_the_rule(self):
        # a zener's low-current VZ (industry gives no guaranteed value) passes a required function derated ÷1.2
        errors, (p, r, db) = gate(cell='ZENER-VZ-LOWER', method='G8', estimate_factor=1.2)
        self.assertEqual(errors, [])
        r, _, derive_errors = derive_rows.derive(p, r)
        self.assertEqual((derive_errors, other_row(r)['review_result']), ([], 'PASS'))
        fn = r['functions'][1]
        for cid in ('PRO-C02.NOTRIP.D403', 'PWR-C03.OTHER-RUN.Q9', 'DEV-C01.Q9'):   # the former rule list does not apply
            self.assertIsNotNone(function_reading.prototype_estimate(fn, ASPECT, 'RUN', cid), cid)

    def test_a_cell_that_never_estimates_refuses_every_class(self):
        for cls in ('REQUIRED_FUNCTION', 'COMPONENT_DAMAGE'):
            errors, _ = gate(cell='FUSE-I2T', method='G5', consequence_class=cls, estimate_factor=1)
            self.assertTrue(any('FUSE-I2T takes no estimate' in e and 'never estimates' in e for e in errors), (cls, errors))

    def test_a_cell_split_by_use_passes_one_class_and_refuses_the_other(self):
        errors, _ = gate(cell='MOS-VGS-ON', method='G7', consequence_class='REQUIRED_FUNCTION', estimate_factor=2)
        self.assertEqual(errors, [])
        errors, _ = gate(cell='MOS-VGS-ON', method='G7', consequence_class='COMPONENT_DAMAGE', estimate_factor=2)
        self.assertTrue(any('takes no estimate for consequence_class COMPONENT_DAMAGE' in e and 'it allows' in e
                            for e in errors), errors)

    def test_the_factor_is_the_cells(self):
        for factor in (None, 1, 1.5, '1.2', True):
            errors, _ = gate(cell='ZENER-VZ-LOWER', method='G8', **({} if factor is None else {'estimate_factor': factor}))
            self.assertTrue(any('estimate_factor: 1.2' in e for e in errors), (factor, errors))

    def test_the_margin_floor_is_the_cells(self):
        # a diode's VF used for a heating (damage) judgement: ×1.15 and a junction margin of at least 20 °C
        errors, (p, r, db) = gate(cell='DIODE-VF', method='G8', consequence_class='COMPONENT_DAMAGE', estimate_factor=1.15)
        self.assertTrue(any('express this margin in °C' in e for e in errors), errors)
        m = margin_of(r); m.update(unit='°C', value=25)
        self.assertEqual([e for e in vr.validate_review(p, r, db)['errors'] if 'FN-OTHER/margin' in e], [])
        m['value'] = 10
        self.assertTrue(any('at least 20 °C' in e for e in vr.validate_review(p, r, db)['errors']))

    def test_a_hazard_or_core_link_class_never_passes(self):
        for cls in ('DAMAGE_OR_HAZARD', 'CORE_LINK_LOSS'):
            errors, _ = gate(cell='ZENER-VZ-LOWER', method='G8', consequence_class=cls, estimate_factor=1.2)
            self.assertTrue(any('no estimate passes it in any cell' in e for e in errors), (cls, errors))

    def test_an_estimate_by_a_guaranteed_method_is_asked_to_be_a_bound(self):
        errors, _ = gate(cell='ZENER-VZ-LOWER', method='G1', estimate_factor=1.2)
        self.assertTrue(any('write the margin as GUARANTEED_BOUND' in e for e in errors), errors)

    def test_without_a_cell_an_estimate_that_passes_is_refused(self):
        p, r, db = estimated()
        del margin_of(r)['basis']['cell']
        errors = [e for e in vr.validate_review(p, r, db)['errors'] if 'FN-OTHER/margin' in e]
        self.assertTrue(any('names basis.cell' in e for e in errors), errors)

    def test_cell_none_keeps_the_former_default(self):
        _, r, _ = estimated()   # cell NONE
        fn = r['functions'][1]
        self.assertIsNotNone(function_reading.prototype_estimate(fn, ASPECT, 'RUN', 'PWR-C02.OTHER-RUN.Q9'))
        self.assertIsNone(function_reading.prototype_estimate(fn, ASPECT, 'RUN', 'PRO-C02.NOTRIP.D403'))


class EstimateGradeAndReleaseTests(unittest.TestCase):
    """Decision 4 (2026-10-26): an estimate pass is C-grade evidence, caps the release at CONDITIONAL_GO and is listed
    apart in the report."""

    def passing(self, **extra):
        p, r, db = estimated(cell='ZENER-VZ-LOWER', method='G8', estimate_factor=1.2, **extra)
        r, _, errors = derive_rows.derive(p, r)
        self.assertEqual(errors, [])
        return p, r, db, vr.validate_review(p, r, db)

    def test_the_gate_lists_the_estimate_pass_with_its_cell_factor_and_prototype_test(self):
        p, r, db, out = self.passing()
        self.assertTrue(out['valid'], out['errors'])
        [e] = out['estimated_passes']
        self.assertEqual((e['check_id'], e['cell'], e['estimate_factor'], e['consequence_class']),
                         ('PWR-C02.OTHER-RUN.Q9', 'ZENER-VZ-LOWER', 1.2, 'REQUIRED_FUNCTION'))
        self.assertEqual(e['verification'], '样机实测 Q9 偏置电压')
        self.assertIn('÷1.2', e['how'])

    def test_derive_writes_grade_c_on_the_row_and_the_gate_refuses_another_grade(self):
        p, r, db, out = self.passing()
        self.assertEqual(other_row(r)['evidence_confidence'], 'C')   # written by derive, kept by expand, accepted by the gate
        self.assertTrue(out['valid'], out['errors'])
        p, r, db, _ = self.passing()
        del other_row(r)['evidence_confidence']                        # expand would grade a bare PASS B
        out = vr.validate_review(p, r, db)
        self.assertTrue(any('C-grade evidence' in e and 'claim B' in e for e in out['errors']), out['errors'])

    def test_an_estimate_pass_cannot_claim_a_grade_evidence(self):
        p, r, db, _ = self.passing()
        other_row(r)['evidence_confidence'] = 'A'
        out = vr.validate_review(p, r, db)
        self.assertTrue(any('C-grade evidence' in e for e in out['errors']), out['errors'])

    def test_the_release_is_capped_at_conditional_go(self):
        self.assertEqual(vr.release_for([], [], False, []), 'GO')
        self.assertEqual(vr.release_for([], [], False, [{'check_id': 'X'}]), 'CONDITIONAL_GO')
        self.assertEqual(vr.release_for([], [], True, []), 'CONDITIONAL_GO')
        self.assertEqual(vr.release_for([], ['b'], False, [{'check_id': 'X'}]), 'NO_GO')
        self.assertEqual(vr.release_for(['e'], [], False, []), 'NO_GO')

    def test_the_report_lists_estimate_passes_apart_and_counts_them(self):
        import render_report
        p, r, db, out = self.passing()
        md = render_report.render(p, r, out, {})
        self.assertIn('## 按典型值估算的结论', md)
        self.assertIn('| 按典型值估算判通过、样机实测后才算定 | 1 项 |', md)
        self.assertIn('有 1 项结论是按典型值估算的', md)
        row = next(l for l in md.split('\n') if l.startswith('| FN-OTHER |') and 'ZENER-VZ-LOWER' in l)
        for word in ('÷1.2', '×1.2', '样机实测 Q9 偏置电压', 'PWR-C02.OTHER-RUN.Q9'):
            self.assertIn(word, row)
        self.assertEqual(render_report.render_estimated_passes([]), [])   # no estimates: no section, no count line


class ExtensionSignalTests(unittest.TestCase):
    """Decision 0 (2026-10-26, user: 器件类别是可以增长的): a device kind the vocabulary lacks, or a known kind whose
    parameter has no cell, is reported under 对 SR 的反馈 and blocks nothing."""

    VARISTOR = {'parts': {'RV1': {'part': 'B72214S0301K101', 'value': 'S14K300'}, 'R1': {'value': '10k'},
                          'RV2': {'part': 'S14K300', 'nc': True}}, 'pin2net': {}, 'nets': {}}

    def gated(self, **extra):
        p, r, db = estimated(**extra)
        margin_of(r).update(against='R1 额定功率 0.25 W')                            # R1: a known kind (resistor)
        r, _, errors = derive_rows.derive(p, r)
        self.assertEqual(errors, [])
        out = vr.validate_review(p, r, db)
        return out, [s for s in out['sr_improvements'] if s.get('kind')], (p, r, db)

    def test_a_part_the_classifier_cannot_place_is_a_new_device_kind(self):
        [signal] = vr.extension_signals({'functions': []}, self.VARISTOR)       # the unfitted RV2 and the resistor are not
        self.assertEqual((signal['kind'], signal['refs'], signal['clue']), ('NEW_DEVICE_KIND', ['RV1'], 'B72214S0301K101 / S14K300'))
        self.assertIn('part_words', signal['suggestion'])

    def test_a_known_kind_without_a_cell_is_a_new_bound_cell_and_blocks_nothing(self):
        out, signals, _ = self.gated()                                              # cell NONE on R1's power
        self.assertTrue(out['valid'], out['errors'])
        [cell] = signals
        self.assertEqual((cell['kind'], cell['function_id'], cell['margin'], cell['device_kinds'], cell['refs']),
                         ('NEW_BOUND_CELL', 'FN-OTHER', 0, ['resistor'], ['R1']))
        self.assertFalse(any('NEW_BOUND_CELL' in b for b in out['blockers']))

    def test_a_margin_with_a_table_cell_is_not_signalled(self):
        _, signals, _ = self.gated(cell='ZENER-VZ-LOWER', method='G8', estimate_factor=1.2)
        self.assertEqual(signals, [])

    def test_an_unboundable_datum_outside_the_table_is_signalled_too(self):
        report = {'functions': [{'id': 'FN-X', 'objects': {'refs': ['R1']}, 'open': [
            {'key': 'K', 'what': 'R1 的脉冲功率', 'worst_case': {'monotonic_tried': {'cell': 'NONE', 'side': 'UPPER'}}}]}]}
        [signal] = [s for s in vr.extension_signals(report, self.VARISTOR) if s['kind'] == 'NEW_BOUND_CELL']
        self.assertEqual((signal['function_id'], signal['open'], signal['device_kinds']), ('FN-X', 'K', ['resistor']))

    def test_the_report_lists_the_signals_under_the_sr_feedback_section(self):
        import render_report
        out, _, (p, r, db) = self.gated()
        out['sr_improvements'].extend(vr.extension_signals({'functions': []}, self.VARISTOR))
        md = render_report.render(p, r, out, {})
        section = md[md.find('### 器件类别与定界表要扩的'):]
        self.assertIn('| 词表里没有的器件类别 | RV1 | B72214S0301K101 / S14K300 |', section)
        self.assertIn('| 有类别、没有格的参数 | R1 | resistor | FN-OTHER 余量[0]：R1 额定功率 0.25 W', section)
        self.assertLess(md.find('## 对 SR 的反馈'), md.find('### 器件类别与定界表要扩的'))

    def test_a_cell_boundary_feedback_names_its_cell(self):
        import render_report
        item = {'kind': 'cell_boundary', 'rules': ['PRO-E01'], 'instance': 'U403 CTR 按 ÷2 判，手册给了 −40..105 °C 的 min',
                'suggestion': 'OPTO-CTR 的可得性对这个系列是全保证', 'cell': 'OPTO-CTR'}
        self.assertEqual(render_report.sr_feedback_errors([item]), [])
        self.assertIn('（格 OPTO-CTR）', '\n'.join(render_report.render_sr_feedback([item])))
        for bad in ({**item, 'cell': 'NO-SUCH'}, {k: v for k, v in item.items() if k != 'cell'}):
            self.assertTrue(render_report.sr_feedback_errors([bad]))
        plain = {k: v for k, v in item.items() if k != 'cell'} | {'kind': 'over_strict'}
        self.assertEqual(render_report.sr_feedback_errors([plain]), [])


class UnobtainableDatumTests(unittest.TestCase):
    """A VENDOR_DATUM item asking the vendor for a parameter whose cell says the industry does not publish it (full
    temperature CTR, low-current VZ) is hinted: use the cell's estimate or change the kind (2026-10-26 general rule)."""

    def hints(self, **item):
        from review_functions import template_hints
        fn = {'id': 'FN-X', 'open': [dict({'key': 'K', 'kind': 'VENDOR_DATUM', 'what': 'U403 的 CTR 全温保证下界',
                                             'acquisition': '向 Vishay 索取全温 CTR 下界'}, **item)]}
        return [h for h in template_hints([fn]) if h['code'] == 'UNOBTAINABLE_DATUM']

    def test_asking_the_vendor_for_an_industry_none_datum_is_hinted(self):
        [h] = self.hints()
        self.assertEqual((h['function_id'], h['key'], h['cell']), ('FN-X', 'K', 'OPTO-CTR'))
        self.assertIn('÷2', h['message'])
        [h] = self.hints(worst_case={'monotonic_tried': {'cell': 'ZENER-VZ-LOWER', 'side': 'LOWER'}})   # the named cell wins
        self.assertEqual(h['cell'], 'ZENER-VZ-LOWER')

    def test_a_published_datum_or_a_closable_acquisition_is_not(self):
        self.assertEqual(self.hints(what='F101 的 I²t 曲线', acquisition='向 Littelfuse 索取 I²t 曲线'), [])   # FUSE-I2T: guaranteed
        self.assertEqual(self.hints(acquisition='已读 p5 的 25 °C 分档，按典型曲线估算'), [])
        self.assertEqual(self.hints(kind='DESIGN_VALUE'), [])


if __name__ == '__main__':
    unittest.main()

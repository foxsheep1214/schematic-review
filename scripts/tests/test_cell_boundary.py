"""The estimate-pass boundary is the bounding-table cell's (2026-10-26, user: 判决的边界应该按照器件类型来).

A margin that names a table cell passes on an estimate when the cell's boundary allows that consequence class,
after the value is derated by the cell's factor, with the cell's margin floor; the rule id of the row no longer
decides. Cell NONE keeps the former default (a required function or a performance, not on a damage, overheating or
protection rule). A hazard or core-link class never passes on an estimate.
"""
import copy
import sys
import unittest
from unittest import mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import derive_rows
import function_reading
import render_report
import validate_review as vr
from test_estimate_pass import estimated, other_row
from test_review_functions import ASPECT


STRESS_RISK = {'types': ['STRESS', 'CONSISTENCY'], 'corner': '满载高温，导通压降只有典型曲线',
               'improvement': '换给出热态保证值的型号，或样机测结温'}


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
        # a zener's VZ upper bound: a bias use passes on an estimate, a clamp protecting a pin (damage) does not
        errors, _ = gate(cell='ZENER-VZ-UPPER', method='G9', consequence_class='REQUIRED_FUNCTION', estimate_factor=1.5)
        self.assertEqual(errors, [])
        errors, _ = gate(cell='ZENER-VZ-UPPER', method='G9', consequence_class='COMPONENT_DAMAGE', estimate_factor=1.5)
        self.assertTrue(any('takes no estimate for consequence_class COMPONENT_DAMAGE' in e and 'it allows' in e
                            for e in errors), errors)

    def test_the_factor_is_the_cells(self):
        for factor in (None, 1, 1.5, '1.2', True):
            errors, _ = gate(cell='ZENER-VZ-LOWER', method='G8', **({} if factor is None else {'estimate_factor': factor}))
            self.assertTrue(any('estimate_factor: 1.2' in e for e in errors), (factor, errors))

    def test_the_margin_floor_is_the_cells(self):
        # a diode's VF used for a heating (damage) judgement: ×1.15 and a junction margin of at least 20 °C
        errors, (p, r, db) = gate(cell='DIODE-VF', method='G8', consequence_class='COMPONENT_DAMAGE', estimate_factor=1.15,
                                  risk=dict(STRESS_RISK))
        self.assertTrue(any('express this margin in °C' in e for e in errors), errors)
        m = margin_of(r); m.update(unit='°C', value=25)
        self.assertEqual([e for e in vr.validate_review(p, r, db)['errors'] if 'FN-OTHER/margin' in e], [])
        m['value'] = 10
        self.assertTrue(any('at least 20 °C' in e for e in vr.validate_review(p, r, db)['errors']))

    def test_a_damage_estimate_is_a_stress_risk(self):
        # 2026-10-27 (user: 损坏类估算判“合格但有应力风险”)
        kw = dict(cell='MOS-VGS-ON', method='G7', consequence_class='COMPONENT_DAMAGE', estimate_factor=2)
        errors, (p, r, db) = gate(**kw)
        self.assertTrue(any('is a stress risk' in e for e in errors), errors)
        errors, (p, r, db) = gate(risk=dict(STRESS_RISK), **kw)
        margin_of(r).update(unit='°C', value=25)
        self.assertEqual([e for e in vr.validate_review(p, r, db)['errors'] if 'FN-OTHER/margin' in e], [])
        risks = vr.validate_review(p, r, db)['risks']
        self.assertTrue(any('STRESS' in x['types'] and x['source'] == 'ESTIMATE' for x in risks), risks)
        errors, _ = gate(cell='ZENER-VZ-LOWER', method='G8', estimate_factor=1.2, risk=dict(STRESS_RISK))
        self.assertTrue(any('STRESS' in e and 'is not a risk' in e for e in errors), errors)

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


class EveryRiskCornerTests(unittest.TestCase):
    """SR-FIX-03 (Codex review 2026-10-27): two estimated corners of one aspect listed only the one written first."""

    def corners(self, swap=False):
        p, r, db = estimated(cell='ZENER-VZ-LOWER', method='G8', estimate_factor=1.2)
        a = margin_of(r)
        a['basis']['risk']['corner'] = 'corner A'
        b = copy.deepcopy(a)
        b['value'] += 0.2
        b['against'] = 'second required voltage window'
        b['basis']['risk']['corner'] = 'corner B'
        ms = r['functions'][1]['calculation']['margin']
        ms.append(b)
        if swap:
            i, j = ms.index(a), ms.index(b)
            ms[i], ms[j] = ms[j], ms[i]
        rows, _, _ = derive_rows.derive(p, r)
        g = vr.validate_review(p, rows, db)
        self.assertTrue(g['valid'], g['errors'])
        return g

    def test_both_corners_are_listed_in_either_order(self):
        for swap in (False, True):
            g = self.corners(swap)
            self.assertEqual(sorted(x['corner'] for x in g['risks'] if x['function_id'] == 'FN-OTHER'),
                             ['corner A', 'corner B'])
            shown = render_report.risk_rows(g['risks'])
            self.assertEqual(sorted(x['corner'] for x in shown if x['function_id'] == 'FN-OTHER'),
                             ['corner A', 'corner B'])


    def test_every_stress_margin_is_listed(self):
        import review_functions
        def stressed(value, corner):
            return {'aspect': ASPECT, 'value': value, 'unit': 'V', 'against': corner,
                    'basis': {'kind': 'GUARANTEED_BOUND', 'comparison': 'GE',
                              'risk': {'types': ['STRESS'], 'corner': corner, 'improvement': '换额定更高的件'}}}
        fn = {'id': 'FN-Q', 'calculation': {'margin': [stressed(5, 'VDS 稳态'), stressed(3, 'VDS 关断尖峰')]}}
        found = review_functions.risks({}, {'DEV-C01.Q1': {'function_id': 'FN-Q', 'review_result': 'PASS',
                                                            'aspect': ASPECT}}, [fn])
        self.assertEqual(sorted(x['corner'] for x in found), ['VDS 关断尖峰', 'VDS 稳态'])


class EstimateGradeAndReleaseTests(unittest.TestCase):
    """Decision 4 (2026-10-26): an estimate pass is C-grade evidence. Since the risk tags (2026-10-26, user: 三档结论加
    四类风险标签，只靠估算过关的角点标风险，风险不限制定稿只单列) it is a pass with a risk: the gate lists it under risks
    with the risk types its cell stands for, the release is not capped, the report lists it by risk type."""

    def passing(self, **extra):
        p, r, db = estimated(cell='ZENER-VZ-LOWER', method='G8', estimate_factor=1.2, **extra)
        r, _, errors = derive_rows.derive(p, r)
        self.assertEqual(errors, [])
        return p, r, db, vr.validate_review(p, r, db)

    def test_the_gate_lists_the_risk_with_its_cell_factor_and_prototype_test(self):
        p, r, db, out = self.passing()
        self.assertTrue(out['valid'], out['errors'])
        [e] = out['risks']
        self.assertEqual((e['check_id'], e['source'], e['types'], e['cell'], e['estimate_factor'], e['consequence_class']),
                         ('PWR-C02.OTHER-RUN.Q9', 'ESTIMATE', ['CONSISTENCY'], 'ZENER-VZ-LOWER', 1.2, 'REQUIRED_FUNCTION'))
        self.assertEqual(e['verification'], '样机实测 Q9 偏置电压')
        self.assertIn('÷1.2', e['how'])
        self.assertTrue(e['corner'] and e['improvement'])

    def test_an_estimate_pass_names_its_risk_within_the_cells_types(self):
        p, r, db = estimated(cell='ZENER-VZ-LOWER', method='G8', estimate_factor=1.2)
        del margin_of(r)['basis']['risk']
        self.assertTrue(any('names its risk' in e for e in vr.validate_review(p, r, db)['errors']))
        margin_of(r)['basis']['risk'] = {'types': ['LIFETIME'], 'corner': 'x', 'improvement': 'y'}
        errors = vr.validate_review(p, r, db)['errors']
        self.assertTrue(any('LIFETIME is not a risk an estimate in cell ZENER-VZ-LOWER stands for' in e and 'CONSISTENCY' in e
                            for e in errors), errors)
        margin_of(r)['basis']['risk'] = {'types': ['CONSISTENCY'], 'corner': '', 'improvement': 'y'}
        self.assertTrue(any('basis.risk is {types' in e for e in vr.validate_review(p, r, db)['errors']))

    def test_cell_none_allows_any_estimate_risk_but_not_stress(self):
        for types, ok in ((['ENVIRONMENT', 'LIFETIME'], True), (['STRESS'], False)):
            p, r, db = estimated(risk={'types': types, 'corner': '−40 °C', 'improvement': '选宽温型号'})
            errors = [e for e in vr.validate_review(p, r, db)['errors'] if 'FN-OTHER/margin' in e]
            self.assertEqual(errors == [], ok, (types, errors))

    def test_derive_writes_grade_c_on_the_row_and_the_gate_refuses_another_grade(self):
        p, r, db, out = self.passing()
        self.assertEqual(other_row(r)['evidence_confidence'], 'C')   # written by derive, kept by expand, accepted by the gate
        self.assertTrue(out['valid'], out['errors'])
        p, r, db, _ = self.passing()
        row = other_row(r); row.pop('derived')                         # a hand-filled copy of the row (item 4: a written
        del row['evidence_confidence']                                 # derived row is re-derived, so only a hand-filled
        out = vr.validate_review(p, r, db)                             # row can claim a grade); expand grades a bare PASS B
        self.assertTrue(any('C-grade evidence' in e and 'claim B' in e for e in out['errors']), out['errors'])

    def test_an_estimate_pass_cannot_claim_a_grade_evidence(self):
        p, r, db, _ = self.passing()
        row = other_row(r); row.pop('derived')
        row['evidence_confidence'] = 'A'
        out = vr.validate_review(p, r, db)
        self.assertTrue(any('C-grade evidence' in e for e in out['errors']), out['errors'])

    def test_a_risk_does_not_cap_the_release(self):
        self.assertEqual(vr.release_for([], [], False), 'GO')
        self.assertEqual(vr.release_for([], [], True), 'CONDITIONAL_GO')
        self.assertEqual(vr.release_for([], ['b'], False), 'NO_GO')
        self.assertEqual(vr.release_for(['e'], [], False), 'NO_GO')
        _, _, _, out = self.passing()
        self.assertTrue(out['risks'])
        self.assertFalse(any('estimate' in b for b in out['blockers']), out['blockers'])
        p, r, db, _ = self.passing()
        with mock.patch.object(vr, 'release_for', wraps=vr.release_for) as release:
            vr.validate_review(p, r, db)
        self.assertIs(release.call_args[0][2], False)   # nothing accepted: the risk is not an acceptance

    def test_a_decisive_margin_may_carry_only_a_stress_risk(self):
        from test_estimate_pass import other_row as row_of
        p, r, db = estimated()
        m = margin_of(r)
        m['basis'] = copy.deepcopy(next(x for x in r['functions'][0]['calculation']['margin']
                                        if x.get('aspect') == ASPECT)['basis'])
        m['basis']['risk'] = {'types': ['STRESS'], 'corner': '105 °C 时 80 % 降额', 'improvement': '换高一档耐压'}
        r, _, errors = derive_rows.derive(p, r)
        self.assertEqual((errors, row_of(r)['review_result']), ([], 'PASS'))
        out = vr.validate_review(p, r, db)
        self.assertEqual([(e['check_id'], e['source'], e['types']) for e in out['risks']],
                         [('PWR-C02.OTHER-RUN.Q9', 'STRESS', ['STRESS'])])
        margin_of(r)['basis']['risk']['types'] = ['ENVIRONMENT']
        self.assertTrue(any('goes with an estimate' in e for e in vr.validate_review(p, r, db)['errors']))

    def test_the_report_lists_risks_by_type_and_counts_them(self):
        import render_report
        p, r, db, out = self.passing()
        md = render_report.render(p, r, out, {})
        self.assertIn('<summary>风险清单</summary>', md)   # in the appendix, folded
        self.assertIn('#### 一致性风险（1 项）', md)
        self.assertIn('| 合格但有风险（不影响定稿，见“风险清单”） | 1 项 |', md)
        self.assertIn('有 1 项合格但有风险（一致性 1）', md)
        row = next(l for l in md.split('\n') if l.startswith('| FN-OTHER |') and 'ZENER-VZ-LOWER' in l)
        for word in ('÷1.2', '×1.2', '样机实测 Q9 偏置电压', 'PWR-C02.OTHER-RUN.Q9', '低电流分档下限', '换在该电流下给保证值'):
            self.assertIn(word, row)
        self.assertEqual(render_report.render_risks([]), [])   # no risk: no section, no count line

    def test_a_life_row_passed_on_a_cell_estimate_is_no_risk(self):
        # 2026-10-28 (user: 按三条建议改): R8 listed DEV-C06.OPTO rows passed on an OPTO-CTR estimate as risks; a life
        # row's estimate is its BOM constraint, the same margin on another row stays a risk
        import review_functions
        p, r, _ = estimated(cell='ZENER-VZ-LOWER', method='G8', estimate_factor=1.2)
        r, _, _ = derive_rows.derive(p, r)
        expected, checks = {c['id']: c for c in p['checks']}, {c['id']: c for c in r['checks']}
        listed = lambda: [e['check_id'] for e in review_functions.risks(expected, checks, r['functions'])]
        self.assertEqual(listed(), ['PWR-C02.OTHER-RUN.Q9'])
        checks['DEV-C06.OPTO.Q9'], expected['DEV-C06.OPTO.Q9'] = (checks.pop('PWR-C02.OTHER-RUN.Q9'),
                                                                  expected.pop('PWR-C02.OTHER-RUN.Q9'))
        self.assertEqual(listed(), [])

    def test_one_margin_reached_by_two_estimate_rows_is_one_risk(self):
        import render_report
        margin = {'value': 74.4, 'unit': 'µA', 'against': 'U3 所需最小集电极电流 87.6 µA'}
        loose = {'check_id': 'PRO-E01.FN-B', 'function_id': 'FN-B', 'aspect': '光耦传输能力', 'source': 'ESTIMATE',
                 'cell': 'NONE', 'types': ['CONSISTENCY'], 'margin': margin, 'estimate_factor': 1}
        celled = dict(loose, check_id='SIG-C07.FN-B', cell='OPTO-CTR', types=['ENVIRONMENT'], margin=dict(margin),
                      estimate_factor=2)
        other = dict(celled, check_id='SIG-C07.FN-C', margin=dict(margin, value=10, against='U4 另一个余量'))
        [shown, second] = render_report.risk_rows([loose, celled, other])
        self.assertEqual((shown['cell'], shown['check_ids'], shown['types'], second['check_ids']),
                         ('OPTO-CTR', ['PRO-E01.FN-B', 'SIG-C07.FN-B'], ['CONSISTENCY', 'ENVIRONMENT'], ['SIG-C07.FN-C']))
        md = '\n'.join(render_report.render_risks([loose, celled, other]))
        self.assertIn('### 环境适应性风险（2 项）', md)
        self.assertNotIn('（NONE）', md)


class ExtensionSignalTests(unittest.TestCase):
    """Decision 0 (2026-10-26, user: 器件类别是可以增长的): a device kind the vocabulary lacks, or a known kind whose
    parameter has no cell, is reported under 对 SR 的反馈 and blocks nothing."""

    # a gas discharge tube: no refdes prefix, keyword or pin-name rule knows it (varistors and NTCs do since 2026-10-26)
    UNKNOWN_PART = {'parts': {'GDT1': {'part': 'B88069X2320S102', 'value': 'GDT 350V'}, 'R1': {'value': '10k'},
                              'GDT2': {'part': 'B88069X2320S102', 'nc': True}}, 'pin2net': {}, 'nets': {}}

    def gated(self, **extra):
        p, r, db = estimated(**extra)
        margin_of(r).update(against='R1 额定功率 0.25 W')                            # R1: a known kind (resistor)
        r, _, errors = derive_rows.derive(p, r)
        self.assertEqual(errors, [])
        out = vr.validate_review(p, r, db)
        # the fixture's other parts (netlist parts since results 7) carry cell NONE margins too; only R1's margin is asked here
        return out, [s for s in out['sr_improvements'] if s.get('kind') and 'R1' in (s.get('refs') or [])], (p, r, db)

    def test_a_part_the_classifier_cannot_place_is_a_new_device_kind(self):
        [signal] = vr.extension_signals({'functions': []}, self.UNKNOWN_PART)       # the unfitted GDT2 and the resistor are not
        self.assertEqual((signal['kind'], signal['refs'], signal['clue']), ('NEW_DEVICE_KIND', ['GDT1'], 'B88069X2320S102 / GDT 350V'))
        self.assertIn('device_kinds', signal['suggestion'])

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
        [signal] = [s for s in vr.extension_signals(report, self.UNKNOWN_PART) if s['kind'] == 'NEW_BOUND_CELL']
        self.assertEqual((signal['function_id'], signal['open'], signal['device_kinds']), ('FN-X', 'K', ['resistor']))

    def test_a_handbook_limit_holding_at_the_working_point_needs_no_cell(self):
        # R8: 113 of 115 rows were guaranteed ratings against computed stress (Q201 650 V against 550 V)
        _, signals, _ = self.gated(method='G1')
        self.assertEqual(signals, [])

    def test_a_ref_glued_to_its_value_names_that_part_not_the_whole_function(self):
        db = {'parts': {'Q20': {}, 'Q201': {'value': 'IRF'}, 'C206': {'value': '4u7'}, 'R1': {'value': '10k'}},
              'pin2net': {}, 'nets': {}}
        self.assertEqual(vr.refs_named('Q201650V额定对550V，对C206', set(db['parts'])), {'Q201', 'C206'})
        margin = {'value': 1, 'unit': 'V', 'against': 'C206耐压减需求', 'check_ids': ['DEV-D04.BOM.C206'],
                  'basis': {'kind': 'ESTIMATE', 'cell': 'NONE'}}
        report = {'functions': [{'id': 'FN-X', 'objects': {'refs': ['Q201', 'C206', 'R1']}, 'calculation': {'margin': [
            margin, dict(margin, against='偏置窗口减需求', check_ids=['DEV-C02.FN-X'])]}}]}
        [signal] = [s for s in vr.extension_signals(report, db) if s['kind'] == 'NEW_BOUND_CELL']
        self.assertEqual((signal['refs'], signal['margin']), (['C206'], 0))   # the second names no part: not spread

    def test_a_life_row_estimate_asks_for_no_cell(self):
        # R8 (2026-10-28): nine electrolytic life estimates asked for a capacitor cell; life has its own path
        db = {'parts': {'C206': {'value': '47u/450V'}, 'U3': {'value': 'SFH6186'}}, 'pin2net': {}, 'nets': {}}
        life = {'value': 400, 'unit': 'h', 'against': 'C206 估算寿命减 87600 h', 'check_ids': ['DEV-C02.LIFE.C206'],
                'basis': {'kind': 'ESTIMATE', 'cell': 'NONE'}}
        shared = dict(life, check_ids=['DEV-C02.LIFE.C206', 'DEV-C02.FN-X'])
        signals = lambda m: [s for s in vr.extension_signals({'functions': [
            {'id': 'FN-X', 'objects': {'refs': ['C206']}, 'calculation': {'margin': [m]}}]}, db) if s['kind'] == 'NEW_BOUND_CELL']
        self.assertEqual(signals(life), [])
        self.assertEqual(signals(dict(life, check_ids=['DEV-C06.OPTO.U3'], against='U3 寿命末 CTR')), [])
        self.assertEqual(signals(shared)[0]['refs'], ['C206'])   # also another row's margin: that row still asks

    def test_a_cell_word_for_another_kind_does_not_hide_the_gap(self):
        db = {'parts': {'Q1': {'value': 'MOS'}, 'R1': {'value': '10k'}}, 'pin2net': {}, 'nets': {}}
        fn = lambda against: {'id': 'FN-X', 'objects': {'refs': ['Q1', 'R1']}, 'calculation': {'margin': [
            {'value': 1, 'unit': 'W', 'against': against, 'basis': {'kind': 'ESTIMATE', 'cell': 'NONE'}}]}}
        gaps = lambda against: [s for s in vr.extension_signals({'functions': [fn(against)]}, db) if s['kind'] == 'NEW_BOUND_CELL']
        self.assertEqual(gaps('Q1 的 SOA 脉冲功率'), [])                  # mosfet: MOS-SOA-HOT is there
        self.assertEqual(gaps('R1 的脉冲功率')[0]['refs'], ['R1'])         # resistor: no cell for it

    def test_the_report_lists_the_signals_under_the_sr_feedback_section(self):
        import render_report
        out, _, (p, r, db) = self.gated()
        out['sr_improvements'].extend(vr.extension_signals({'functions': []}, self.UNKNOWN_PART))
        md = render_report.render(p, r, out, {})
        section = md[md.find('### 器件类别与定界表要扩的'):]
        self.assertIn('| SR 认不出的器件（能力不足，待补） | GDT1 | B88069X2320S102 / GDT 350V |', section)
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

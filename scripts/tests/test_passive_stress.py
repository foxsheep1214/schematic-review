"""Per-part DEV-C01 proposals for commodity chip resistors/MLCCs and the override gate."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from checkers import passive_stress
from checkers.passive_stress import OVERRIDE_CODES
from plan_review import build_review_plan
import render_report
from validate_review import validate_review
from test_decoupling import add, fixture, ledger, mark_pass, rebind
from ledger4 import gap

R0402 = 'Resistor_SMD:R_0402_1005Metric'
C0402 = 'Capacitor_SMD:C_0402_1005Metric'
RAIL = {'VCC_3V3': {'voltage_v': {'min': 3.135, 'max': 3.465}}}


def board(rails=RAIL):
    """U1 on VCC_3V3; C1 100nF bypass; R1 pull-up on U1's GPIO."""
    db, intent = fixture(('100nF',))
    db['parts']['C1']['jedec'] = C0402
    add(db, 'R1', '10k', [('1', '1', 'VCC_3V3'), ('2', '2', 'U1_IO')])
    db['parts']['R1']['jedec'] = R0402
    intent['assemblies'][0]['population']['R1'] = True
    if rails is not None:
        intent['power_rails'] = copy.deepcopy(rails)
    rebind(db, intent)
    return db, intent


def proposals(db, intent):
    plan = build_review_plan(db, intent)
    return plan, {c['object']['ref']: c for c in plan['checks'] if 'proposal' in c}


class ProposalTests(unittest.TestCase):
    def test_pull_up_and_bypass_on_declared_rail_are_proposed_pass(self):
        _, rows = proposals(*board())
        self.assertEqual(rows['R1']['id'], 'DEV-C01.R1')
        calc = rows['R1']['proposal']['calculation']
        self.assertEqual(calc['v_across_max'], 3.465)
        self.assertAlmostEqual(calc['p_max_w'], 3.465 ** 2 / 9500, places=6)
        self.assertEqual(rows['R1']['proposal']['result'], 'PASS')
        self.assertEqual(rows['C1']['proposal']['result'], 'PASS')

    def test_undeclared_rail_gives_no_proposal_and_names_the_rail(self):
        _, rows = proposals(*board(rails=None))
        for ref in ('R1', 'C1'):
            self.assertIsNone(rows[ref]['proposal']['result'])
        self.assertIn('power_rails.VCC_3V3.voltage_v', rows['R1']['proposal']['note'])

    def test_overstressed_resistor_is_not_proposed(self):
        db, intent = board()
        db['parts']['R1']['value'] = '27'
        rebind(db, intent)
        _, rows = proposals(db, intent)
        self.assertIsNone(rows['R1']['proposal']['result'])
        self.assertGreater(rows['R1']['proposal']['calculation']['power_ratio'], 1)

    def test_untracked_resistor_up_to_half_floor_passes_with_procurement_constraint(self):
        # 3.465 V across: 10k is under 25% of the 0402 floor, 620R is 33%, 330R is 61%.
        for value, result, constraint in (('10k', 'PASS', False), ('620', 'PASS', True), ('330', None, False)):
            with self.subTest(value=value):
                db, intent = board()
                db['parts']['R1']['value'] = value
                rebind(db, intent)
                proposal = proposals(db, intent)[1]['R1']['proposal']
                self.assertEqual(proposal['result'], result)
                calc = proposal['calculation']
                self.assertEqual('procurement_min_power_w' in calc, constraint)
                if constraint:
                    self.assertAlmostEqual(calc['procurement_min_power_w'], 2 * calc['p_max_w'], places=9)
                    self.assertIn('DEV-D04', proposal['note'])

    def unpackaged(self, r1='10k', c1='100nF'):
        """The board with no footprints at all, as a schematic drawn before the PCB has none."""
        db, intent = board()
        for ref, value in (('R1', r1), ('C1', c1)):
            db['parts'][ref].update(jedec='', value=value)
        rebind(db, intent)
        return db, intent

    def test_a_part_without_a_footprint_gets_a_row_only_beyond_the_prejudgement(self):
        # A schematic without footprints left every resistor and capacitor out of the inventory, with nothing said;
        # judged on the smallest common package, a pre-judged pass or an unbounded stress stays in the circuit row.
        _, rows = proposals(*self.unpackaged())
        self.assertNotIn('R1', rows)
        self.assertNotIn('C1', rows)
        _, rows = proposals(*self.unpackaged(r1='22R'))   # 3.465² / 20.9 Ω = 0.57 W on an assumed 0402
        calc = rows['R1']['proposal']['calculation']
        self.assertIsNone(rows['R1']['proposal']['result'])
        self.assertEqual((calc['p_floor_w'], calc['v_floor_v'], calc['floor_basis']), (1 / 16, 25.0, 'assumed 0402'))

    def test_a_rating_written_in_the_value_is_the_floor(self):
        _, rows = proposals(*self.unpackaged(r1='22R/1%/0.25W/50V'))
        calc = rows['R1']['proposal']['calculation']
        self.assertEqual((calc['p_floor_w'], calc['v_floor_v'], calc['floor_basis']), (0.25, 50.0, 'written'))
        _, rows = proposals(*self.unpackaged(r1='22R/1%/2W'))
        self.assertNotIn('R1', rows)

    def test_a_capacitor_without_a_footprint_is_judged_on_its_written_voltage(self):
        for value in ('100n/2.5V', '100nF 2.5V'):
            _, rows = proposals(*self.unpackaged(c1=value))
            self.assertEqual(rows['C1']['proposal']['calculation']['written_v'], 2.5)
            self.assertIsNone(rows['C1']['proposal']['result'])
        for value in ('100n/10V', '100n'):
            _, rows = proposals(*self.unpackaged(c1=value))
            self.assertNotIn('C1', rows)
        self.assertEqual(passive_stress.rated_voltage('4.7uF 10V'), 10.0)

    def test_a_rating_the_bom_writes_as_its_own_segment_is_the_floor(self):
        # The BOM's specification column states ratings the value leaves out; read as written, never from a sentence.
        db, intent = self.unpackaged(r1='22R', c1='100n')
        db['bom'] = {'parts': {'R1': {'Electrical specification': '22Ω±1%，2W，工作耐压≥50V'},
                               'C1': {'Electrical specification': '100nF±10%/2.5V/X7R'}}}
        _, rows = proposals(db, intent)
        self.assertNotIn('R1', rows)   # 0.57 W on a written 2 W stays within the pre-judgement
        self.assertEqual(rows['C1']['proposal']['calculation']['written_v'], 2.5)
        db['bom']['parts']['C1'] = {'Electrical specification': '启动时 18V，额定 50V'}   # two voltages in a sentence
        _, rows = proposals(db, intent)
        self.assertNotIn('C1', rows)
        # Two voltages leave the rating unread; one, written as its own segment, is read.
        self.assertEqual(passive_stress.bom_ratings({'Spec': '启动时 18V，额定 50V'}), {})
        self.assertEqual(passive_stress.bom_ratings({'Spec': '10µF±20%/160V/105°C', 'Note': '2W'}),
                         {'voltage_v': 160.0, 'power_w': 2.0})

    def test_parts_judged_on_an_assumed_package_are_reported(self):
        plan, _ = proposals(*self.unpackaged())
        diagnostic = next(d for d in plan['diagnostics'] if d['code'] == 'PASSIVE_PACKAGE_UNKNOWN')
        self.assertEqual(diagnostic['refs'], ['C1', 'R1'])
        self.assertIn('C1、R1', '\n'.join(render_report.render_input_notes(plan)))

    def test_a_part_with_a_part_number_or_datasheet_is_not_judged_on_the_assumed_package(self):
        # A bulk electrolytic and a safety capacitor with their part numbers were listed as "no package, judged as
        # 0402": a part with an identity is judged against its own datasheet, only an anonymous one on the assumption.
        db, intent = self.unpackaged(r1='22R')
        db['bom'] = {'parts': {'R1': {'MPN': 'RX-22R-2W'}}}
        db['parts']['C1']['datasheet'] = 'vendor-c1.pdf'
        rebind(db, intent)
        plan, rows = proposals(db, intent)
        self.assertNotIn('R1', rows)   # 0.57 W on an assumed 0402 is no longer a row: R1's datasheet answers it
        self.assertFalse(any(d['code'] == 'PASSIVE_PACKAGE_UNKNOWN' for d in plan['diagnostics']))
        db['bom'] = {'parts': {'R1': {'Circuit': 'Input'}}}   # a column that names no part leaves R1 anonymous
        rebind(db, intent)
        plan, rows = proposals(db, intent)
        self.assertIn('R1', rows)
        self.assertEqual(next(d for d in plan['diagnostics'] if d['code'] == 'PASSIVE_PACKAGE_UNKNOWN')['refs'], ['R1'])
        self.assertIn('料号或原厂资料', '\n'.join(render_report.render_input_notes(plan)))

    def divider(self, break_chain=False):
        """VHV (0..400 V) - R2 1M - N1 - R3 1M - U1_IO (U1 input, C2 100p) - R4 10k - GND."""
        db, intent = fixture(('100nF',))
        db['parts']['C1']['jedec'] = C0402
        for ref, value, a, b, fp in (('R2', '1M', 'VHV', 'N1', R0402), ('R3', '1M', 'N1', 'U1_IO', R0402),
                                     ('R4', '10k', 'U1_IO', 'GND', R0402), ('C2', '100p', 'U1_IO', 'GND', C0402)):
            add(db, ref, value, [('1', '1', a), ('2', '2', b)])
            db['parts'][ref]['jedec'] = fp
        if break_chain:
            add(db, 'D1', 'DIODE', [('1', 'A', 'N1'), ('2', 'K', 'GND')])
        db['native_pintype'] = {'U1.3': 'input'}
        intent['assemblies'][0]['population'] = {r: True for r in db['parts']}
        intent['power_rails'] = dict(copy.deepcopy(RAIL), VHV={'voltage_v': {'min': 0, 'max': 400}})
        rebind(db, intent)
        return proposals(db, intent)[1]

    def test_a_series_divider_shares_the_rail_voltage(self):
        # Every resistor of a high-voltage sense string and the feedback node's capacitor were bounded by the full
        # 400 V of the rail; a pure series string divides it, and the filtered tap is bounded by its divider ratio.
        rows = self.divider()
        v = {ref: rows[ref]['proposal']['calculation']['v_across_max'] for ref in ('R2', 'R3', 'R4', 'C2')}
        top = 400 * 1.05e6 / (1.05e6 + 0.95e6)   # the held tap may sit at 0 V while the rail is at 400 V
        self.assertAlmostEqual(v['R2'], top, places=3)
        self.assertAlmostEqual(v['R3'], top, places=3)
        tap = 400 * 10.5e3 / (10.5e3 + 1.9e6)
        self.assertAlmostEqual(v['R4'], tap, places=4)
        self.assertAlmostEqual(v['C2'], tap, places=4)
        self.assertIn('series-chain:R2+R3+R4', rows['R2']['proposal']['bases'])
        self.assertIn('series-chain-tap', rows['C2']['proposal']['bases'])

    def test_a_string_with_another_part_on_a_tap_keeps_the_rail_bound(self):
        rows = self.divider(break_chain=True)
        self.assertEqual(rows['R2']['proposal']['calculation']['v_across_max'], 400)

    def test_rating_beyond_orderable_tier_is_not_proposed(self):
        _, rows = proposals(*board({'VCC_3V3': {'voltage_v': {'min': 55, 'max': 60}}}))
        self.assertIsNone(rows['C1']['proposal']['result'])

    def test_pump_pin_and_connector_nets_are_unbounded(self):
        for pin_name, ref in (('VCP', 'U1'), (None, 'J1')):
            with self.subTest(ref=ref):
                db, intent = board()
                if ref == 'U1':
                    db['pinname']['U1.3'] = pin_name
                else:
                    add(db, 'J1', 'Conn_01x01', [('1', '1', 'U1_IO')])
                    intent['assemblies'][0]['population']['J1'] = True
                rebind(db, intent)
                _, rows = proposals(db, intent)
                self.assertIsNone(rows['R1']['proposal']['result'])

    def test_ac_coupled_net_swings_both_ways(self):
        db, intent = board()
        add(db, 'C2', '100nF', [('1', '1', 'U1_IO'), ('2', '2', 'AC_NODE')])
        add(db, 'R2', '10k', [('1', '1', 'AC_NODE'), ('2', '2', 'GND')])
        db['parts']['R2']['jedec'] = R0402
        intent['assemblies'][0]['population'].update(C2=True, R2=True)
        rebind(db, intent)
        _, rows = proposals(db, intent)
        self.assertEqual(rows['R2']['proposal']['calculation']['v_across_max'], 3.465)
        self.assertEqual(rows['R1']['proposal']['calculation']['v_across_max'], 6.93)

    def test_signal_series_resistor_points_to_dynamic_model(self):
        db, intent = board()
        add(db, 'R2', '27', [('1', '1', 'U1_IO'), ('2', '2', 'USB_DP')])
        add(db, 'J1', 'USB_B_Micro', [('1', '1', 'USB_DP'), ('2', '2', 'GND')])
        db['parts']['R2']['jedec'] = R0402
        intent['assemblies'][0]['population'].update(R2=True, J1=True)
        rebind(db, intent)
        _, rows = proposals(db, intent)
        self.assertIsNone(rows['R2']['proposal']['result'])
        self.assertIn('信号串阻', rows['R2']['proposal']['note'])
        self.assertNotIn('信号串阻', rows['R1']['proposal']['note'])

    def test_split_return_nets_bound_like_ground(self):
        # 隔离电源的分域地（PORT_GND/SR_RETURN）经连接器外引，不能让地网本身成为“无界”
        db, intent = board()
        add(db, 'C2', '100nF', [('1', '1', 'VCC_3V3'), ('2', '2', 'PORT_GND')])
        add(db, 'J1', 'USB_C', [('1', '1', 'PORT_GND'), ('2', '2', 'SR_RETURN')])
        db['parts']['C2']['jedec'] = C0402
        intent['assemblies'][0]['population'].update(C2=True, J1=True)
        intent['power_rails']['PORT_GND'] = {'voltage_v': {'min': 0, 'max': 0}, 'domain': 'GND'}
        rebind(db, intent)
        _, rows = proposals(db, intent)
        self.assertEqual(rows['C2']['proposal']['result'], 'PASS')
        self.assertEqual(rows['C2']['proposal']['calculation']['v_across_max'], 3.465)

    def test_part_across_two_ground_domains_gets_no_proposal(self):
        db, intent = board()
        add(db, 'C2', '1nF', [('1', '1', 'P_GND'), ('2', '2', 'GND')])
        add(db, 'R2', '10M', [('1', '1', 'PRI_RTN'), ('2', '2', 'GND')])
        db['parts']['C2']['jedec'] = C0402
        db['parts']['R2']['jedec'] = R0402
        intent['assemblies'][0]['population'].update(C2=True, R2=True)
        rebind(db, intent)
        _, rows = proposals(db, intent)
        for ref in ('C2', 'R2'):
            self.assertIsNone(rows[ref]['proposal']['result'])
            self.assertIn('cross-domain', rows[ref]['proposal']['note'])

    def test_ground_domains_are_listed_for_review(self):
        from checkers.passive_stress import ground_domains
        db, intent = board()
        add(db, 'C2', '1nF', [('1', '1', 'P_GND'), ('2', '2', 'SR_RETURN')])
        intent['power_rails']['SR_RETURN'] = {'voltage_v': {'min': 0, 'max': 0}, 'domain': 'SEC'}
        self.assertEqual({'GND': ['GND'], 'P_GND': ['P_GND'], 'SEC': ['SR_RETURN']}, ground_domains(db, intent))

    def test_declared_shared_domain_joins_ground_names(self):
        db, intent = board()
        add(db, 'R2', '0R', [('1', '1', 'AGND'), ('2', '2', 'GND')])
        add(db, 'R3', '10k', [('1', '1', 'VCC_3V3'), ('2', '2', 'AGND')])
        db['parts']['R3']['jedec'] = R0402
        intent['assemblies'][0]['population'].update(R2=True, R3=True)
        intent['power_rails'].update({'AGND': {'voltage_v': {'min': 0, 'max': 0}, 'domain': 'LV'},
                                      'GND': {'voltage_v': {'min': 0, 'max': 0}, 'domain': 'LV'}})
        rebind(db, intent)
        _, rows = proposals(db, intent)
        self.assertEqual(rows['R3']['proposal']['result'], 'PASS')


class OverrideGateTests(unittest.TestCase):
    def setUp(self):
        self.db, intent = board()
        self.plan, rows = proposals(self.db, intent)
        self.key = rows['R1']['id']

    def report_with(self, **fields):
        report = ledger(self.plan, self.db)
        mark_pass(report, self.plan, self.key).update(fields)
        return report

    def errors(self, report):
        return [e for e in validate_review(self.plan, report, self.db)['errors'] if self.key in e]

    def insufficient(self, **extra):
        report = self.report_with(**extra)
        gap(report, self.key, 'R1-PART', 'DESIGN_VALUE', plan=self.plan, what='R1 实际料号', level='P3')
        return report

    def test_procurement_insufficient_without_override_is_rejected(self):
        self.assertTrue(any('proposal_override' in e for e in self.errors(self.insufficient())))

    def test_coded_override_is_accepted(self):
        report = self.insufficient(proposal_override={
            'code': 'STRESS_ABOVE_BOUND', 'reason': 'U1_IO 经外部线缆可接 12 V（需求 REQ-9）'})
        self.assertFalse(any('proposal_override' in e for e in self.errors(report)))

    def test_unknown_code_or_empty_reason_is_rejected(self):
        for override in ({'code': 'PROCUREMENT_OPEN', 'reason': 'x'},
                         {'code': sorted(OVERRIDE_CODES)[0], 'reason': ' '}):
            with self.subTest(override=override):
                errors = self.errors(self.insufficient(proposal_override=override))
                self.assertTrue(any('proposal_override' in e for e in errors))

    def test_tampered_proposal_is_detected(self):
        plan = copy.deepcopy(self.plan)
        row = next(c for c in plan['checks'] if c['id'] == self.key)
        row['proposal']['result'] = None
        self.plan = plan
        report = self.insufficient()
        gate = validate_review(plan, report, self.db)
        self.assertTrue(any('passive_stress' in e or 'changed' in e for e in gate['errors']), gate['errors'])


class DecouplingRatingProposalTests(unittest.TestCase):
    def rating_row(self, footprint=C0402):
        db, intent = board()
        db['parts']['C1']['jedec'] = footprint
        group = intent['decoupling']['groups'][0]
        group['requirements'] = [r for r in group['requirements'] if r['kind'] != 'rating']
        rebind(db, intent)
        plan = build_review_plan(db, intent)
        return db, plan, next(c for c in plan['checks'] if c['rule'] == 'PWR-C10')

    def test_rating_row_reuses_capacitor_proposals(self):
        _, _, row = self.rating_row()
        self.assertEqual(row['proposal']['result'], 'PASS')
        self.assertEqual(row['proposal']['basis'], {'C1': 'PASS'})

    def test_capacitor_outside_proposal_scope_gives_no_rating_proposal(self):
        _, _, row = self.rating_row('Capacitor_THT:CP_Radial_D8.0mm_P3.50mm')
        self.assertIsNone(row['proposal']['result'])

    def test_rating_override_needs_a_code(self):
        db, plan, row = self.rating_row()
        report = ledger(plan, db)
        mark_pass(report, plan, row['id'])
        gap(report, row['id'], 'C1-RATING', 'DESIGN_VALUE', plan=plan, what='C1 受控耐压', level='P3')
        errors = validate_review(plan, report, db)['errors']
        self.assertTrue(any(row['id'] in e and 'proposal_override' in e for e in errors))


if __name__ == '__main__':
    unittest.main()

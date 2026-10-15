"""Per-part DEV-C01 proposals for commodity chip resistors/MLCCs and the override gate."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from checkers.passive_stress import OVERRIDE_CODES
from plan_review import build_review_plan
from validate_review import validate_review
from test_decoupling import add, fixture, ledger, mark_pass, rebind

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
        row = next(c for c in report['checks'] if c['id'] == self.key)
        mark_pass(row)
        row.update(fields)
        return report

    def errors(self, report):
        return [e for e in validate_review(self.plan, report, self.db)['errors'] if self.key in e]

    def insufficient(self, **extra):
        return self.report_with(review_result='INSUFFICIENT', evidence_confidence='C',
                                missing_inputs=['R1 实际料号'], potential_severity='P3',
                                gap_cause='DESIGN_OPEN', **extra)

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
        entry = next(c for c in report['checks'] if c['id'] == row['id'])
        mark_pass(entry)
        entry.update(review_result='INSUFFICIENT', evidence_confidence='C', missing_inputs=['C1 受控耐压'],
                     potential_severity='P3', gap_cause='DESIGN_OPEN')
        errors = validate_review(plan, report, db)['errors']
        self.assertTrue(any(row['id'] in e and 'proposal_override' in e for e in errors))


if __name__ == '__main__':
    unittest.main()

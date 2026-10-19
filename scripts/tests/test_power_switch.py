import pathlib
import sys
import tempfile
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import catalog

from checkers.power_switch import PowerSwitchChecker, build_inventory, validate_power_switch_intent
from electrical_contract import validate_evidence
from electrical_fixtures import bind_evidence, bound_intent
from lint import Lint
from plan_review import build_review_plan
from test_inductive_load import add


def switch_board(driver='ic', pull=True, snubber=None, load='inductor'):
    """U2 驱动 Q1 低边开关，负载与吸收网络按参数变化。"""
    db = {'nets': {}, 'parts': {}, 'pin2net': {}, 'pinname': {}, 'pintype': {},
          'pseudo_nets': [], 'ref2page': {}}
    add(db, 'Q1', 'AO3400', [('1', 'G', 'GATE'), ('2', 'D', 'SW_OUT'), ('3', 'S', 'GND')])
    if driver == 'ic':
        add(db, 'U2', 'GATE-DRIVER', [('1', 'LO', 'DRV_OUT'), ('2', 'VDD', 'V12'),
                                      ('3', 'GND', 'GND')])
        add(db, 'R1', '10R', [('1', '1', 'DRV_OUT'), ('2', '2', 'GATE')])
    elif driver == 'connector':
        add(db, 'J3', 'HEADER-2', [('1', '1', 'GATE'), ('2', '2', 'GND')])
    if pull:
        add(db, 'R2', '100K', [('1', '1', 'GATE'), ('2', '2', 'GND')])
    if load == 'inductor':
        add(db, 'L2', 'IND-100UH', [('1', '1', 'SW_OUT'), ('2', '2', 'V12')])
    if snubber == 'rc':
        add(db, 'R3', '10R', [('1', '1', 'SW_OUT'), ('2', '2', 'SNUB')])
        add(db, 'C3', '1nF', [('1', '1', 'SNUB'), ('2', '2', 'GND')])
    elif snubber == 'tvs':
        add(db, 'D3', 'SMBJ30A', [('1', 'K', 'SW_OUT'), ('2', 'A', 'GND')])
    elif snubber == 'rcd':
        add(db, 'D3', 'US1M', [('1', 'A', 'SW_OUT'), ('2', 'K', 'CLAMP')])
        add(db, 'C3', '2.2nF', [('1', '1', 'CLAMP'), ('2', '2', 'V12')])
        add(db, 'R3', '100K', [('1', '1', 'CLAMP'), ('2', '2', 'V12')])
    elif snubber == 'boost':
        add(db, 'D3', 'US1M', [('1', 'A', 'SW_OUT'), ('2', 'K', 'VOUT')])
        add(db, 'C3', '100uF', [('1', '1', 'VOUT'), ('2', '2', 'GND')])
        add(db, 'U3', 'LOAD', [('1', 'VDD', 'VOUT'), ('2', 'GND', 'GND')])
    return db


def switches_of(inventory, state='as-built'):
    entry = next(x for x in inventory['states'] if x['id'] == state)
    return {item['ref']: item for item in entry['switches']}


CHECKER_RULES = {rule.id for rule in catalog.rules(source='power_switch')}


def findings(db, intent=None):
    return [f for f in Lint(db, '', intent).run() if f['rule'] in CHECKER_RULES]


def gate_check(**overrides):
    check = {'id': 'GATE-DRIVE', 'rule': 'DRV-E01', 'kind': 'gate_drive', 'node': 'Q1.1',
             'channel': 'n', 'vgs_drive_v': {'min': 9.0, 'max': 12.6},
             'vgs_rds_on_v': 4.5, 'vgs_abs_v': {'min': -20.0, 'max': 20.0},
             'citation': 'Synthetic driver supply window and MOSFET guaranteed conditions'}
    check.update(overrides)
    return check


class RecognitionTest(unittest.TestCase):
    def test_driven_switch_with_pull_and_snubber_has_no_findings(self):
        db = switch_board(snubber='rc')
        switch = switches_of(build_inventory(db))['Q1']
        self.assertEqual(switch['topology'], 'low-side')
        self.assertEqual(switch['gate_net'], 'GATE')
        self.assertEqual([d['via'] for d in switch['drivers']], ['series:R1'])
        self.assertEqual([p['to'] for p in switch['gate_pulls']], ['GND'])
        self.assertEqual([s['type'] for s in switch['snubbers']], ['rc-snubber'])
        self.assertEqual(switch['switch_node_evidence'], ['inductive:L2'])
        self.assertEqual(findings(db), [])

    def test_floating_gate_reports_ps01(self):
        db = switch_board(driver=None, pull=False, snubber='rc')
        switch = switches_of(build_inventory(db))['Q1']
        self.assertEqual(switch['drivers'], [])
        hits = findings(db)
        self.assertEqual([f['rule'] for f in hits], ['DRV-A03'])
        self.assertIn('GATE', hits[0]['detail'])

    def test_untyped_ic_pin_on_the_gate_is_a_candidate(self):
        # 名称启发式审计：没有引脚方向的网表里 MCU 的 PB3 直接驱动栅极，曾报“栅极悬空”。
        db = switch_board(driver=None, pull=False)
        add(db, 'U1', 'MCU', [('1', 'PB3', 'GATE'), ('2', 'VDD', 'V12'), ('3', 'GND', 'GND')])
        hits = [f for f in findings(db) if f['rule'] == 'DRV-A03']
        self.assertEqual([f['kind'] for f in hits], ['CANDIDATE'])
        self.assertIn('U1.1', hits[0]['detail'])

    def test_optocoupler_output_drives_a_bjt_base(self):
        # 典型电路基准：继电器板 PC357 发射极驱动 Q1 基极，曾报“基极悬空”。
        db = switch_board(driver=None, pull=False)
        add(db, 'U1', 'PC357_OPTO', [('1', 'anoda', 'IN_A'), ('2', 'katoda', 'GND'),
                                     ('3', 'emiter', 'GATE'), ('4', 'kolektor', 'V12')])
        self.assertEqual([f for f in findings(db) if f['rule'] == 'DRV-A03'], [])

    def test_relay_flyback_diode_counts_when_coil_is_fed_through_a_resistor(self):
        db = switch_board(load=None)
        add(db, 'K1', 'SRD_RELAY_5V', [('1', '1', 'COIL_TOP'), ('2', '2', 'SW_OUT'), ('3', '3', 'NO'),
                                       ('4', '4', 'COM'), ('5', '5', 'NC')])
        add(db, 'R4', '10R', [('1', '1', 'COIL_TOP'), ('2', '2', 'V12')])
        add(db, 'D2', '1N4148', [('1', 'A', 'SW_OUT'), ('2', 'K', 'COIL_TOP')])
        self.assertNotIn('DRV-A04', [f['rule'] for f in findings(db)])

    def test_gate_pull_alone_is_not_a_finding(self):
        self.assertEqual(findings(switch_board(driver=None, snubber='rc')), [])

    def test_connector_driven_gate_counts_as_a_driver(self):
        switch = switches_of(build_inventory(switch_board(driver='connector', pull=False,
                                                          snubber='rc')))['Q1']
        self.assertEqual([d['source'] for d in switch['drivers']], ['external'])

    def test_switch_node_without_damping_reports_ps02_candidate(self):
        hits = findings(switch_board())
        self.assertEqual([f['rule'] for f in hits], ['DRV-A04'])
        self.assertEqual(hits[0]['kind'], 'CANDIDATE')
        self.assertIn('inductive:L2', hits[0]['detail'])

    def test_clamp_counts_as_damping(self):
        self.assertEqual(findings(switch_board(snubber='tvs')), [])

    def test_freewheel_diode_across_the_load_counts_as_a_clamp(self):
        db = switch_board()
        add(db, 'D9', '1N4148', [('1', 'A', 'SW_OUT'), ('2', 'K', 'V12')])
        switch = switches_of(build_inventory(db))['Q1']
        self.assertEqual([s['ref'] for s in switch['snubbers']], ['D9'])
        self.assertEqual(findings(db), [])

    def test_resistive_load_without_damping_is_silent(self):
        self.assertEqual(findings(switch_board(load=None)), [])

    def test_high_side_buck_negative_freewheel_is_not_a_reversed_boost_diode(self):
        db = switch_board()
        db['pin2net']['Q1.3'] = 'V12'
        db['nets']['GND'].remove('Q1.3')
        db['nets']['V12'].append('Q1.3')
        add(db, 'D9', '1N4148', [('1', 'A', 'GND'), ('2', 'K', 'SW_OUT')])
        self.assertNotIn('DRV-A04', [f['rule'] for f in findings(db)])

    def test_high_side_switch_fed_from_unrecognised_bulk_keeps_its_freewheel_diode(self):
        db = switch_board()
        db['pin2net']['Q1.3'] = 'BULK'
        db['nets']['GND'].remove('Q1.3')
        db['nets']['BULK'] = ['Q1.3']
        add(db, 'D9', '1N4148', [('1', 'A', 'GND'), ('2', 'K', 'SW_OUT')])
        switch = switches_of(build_inventory(db))['Q1']
        self.assertEqual(switch['topology'], 'floating')
        self.assertEqual([s['ref'] for s in switch['snubbers']], ['D9'])
        self.assertNotIn('DRV-A04', [f['rule'] for f in findings(db)])

    def test_low_side_reverse_diode_to_ground_is_not_a_clamp(self):
        db = switch_board()
        add(db, 'D9', '1N4148', [('1', 'A', 'GND'), ('2', 'K', 'SW_OUT')])
        self.assertIn('DRV-A04', [f['rule'] for f in findings(db)])

    def test_rcd_clamp_returning_to_an_undeclared_transformer_bulk_is_found(self):
        from test_inductive_load import flyback_board
        db = flyback_board()
        add(db, 'C9', '68uF', [('1', '1', 'BUS'), ('2', '2', 'GND')])
        switch = switches_of(build_inventory(db))['Q1']
        self.assertEqual([(s['type'], s['to']) for s in switch['snubbers']], [('rcd-clamp', 'BUS')])
        self.assertNotIn('DRV-A04', [f['rule'] for f in findings(db)])
        db['parts']['C9']['nc'] = True   # a transformer terminal without storage is not a supply
        self.assertIn('DRV-A04', [f['rule'] for f in findings(db)])

    def test_boost_rectifier_counts_for_a_sensed_low_side_switch(self):
        db = switch_board(load=None)
        db['pin2net']['Q1.3'] = 'SENSE'
        db['nets']['GND'].remove('Q1.3')
        db['nets']['SENSE'] = ['Q1.3']
        add(db, 'R9', '0R1', [('1', '1', 'SENSE'), ('2', '2', 'GND')])
        add(db, 'L9', 'IND-200UH', [('1', '1', 'VIN'), ('2', '2', 'SW_OUT')])
        add(db, 'D9', 'MUR550', [('1', 'A', 'SW_OUT'), ('2', 'K', 'V12')])
        switch = switches_of(build_inventory(db))['Q1']
        self.assertEqual(switch['topology'], 'floating')
        self.assertEqual([s['type'] for s in switch['snubbers']], ['boost-transfer-diode'])
        self.assertNotIn('DRV-A04', [f['rule'] for f in findings(db)])

    def test_half_bridge_midpoint_is_recognised(self):
        db = switch_board(load=None)
        add(db, 'Q2', 'AO3400', [('1', 'G', 'GATE_H'), ('2', 'D', 'V12'), ('3', 'S', 'SW_OUT')])
        add(db, 'R4', '100K', [('1', '1', 'GATE_H'), ('2', '2', 'SW_OUT')])
        switch = switches_of(build_inventory(db))['Q1']
        self.assertEqual(switch['switch_node_evidence'], ['half-bridge:Q2'])
        self.assertIn('DRV-A04', [f['rule'] for f in findings(db)])

    def test_unpopulated_switch_is_skipped(self):
        db = switch_board(snubber='rc')
        db['parts']['Q1']['nc'] = True
        self.assertEqual(switches_of(build_inventory(db)), {})

    def test_unknown_pin_roles_keep_a_gap_without_findings(self):
        db = switch_board(snubber='rc')
        for pin in ('1', '2', '3'):
            db['pinname'].pop('Q1.' + pin)
        switch = switches_of(build_inventory(db))['Q1']
        self.assertIn('pin-roles:Q1', switch['gaps'])
        self.assertIsNone(switch['gate_net'])
        self.assertEqual(findings(db), [])


class PlanTest(unittest.TestCase):
    def test_plan_items_bind_to_the_inventory_digest(self):
        db = switch_board()
        plan = build_review_plan(db)
        items = [x for x in plan['checks'] if x['object'].get('power_switch')]
        self.assertEqual({(x['rule'], x['object']['power_switch']) for x in items},
                         {('DRV-E01', 'Q1-GATE'), ('DRV-C02', 'Q1-GATE'), ('DRV-D01', 'Q1-GATE')})
        for item in items:
            self.assertEqual(item['object']['power_switch_digest'], plan['power_switch']['digest'])
        self.assertEqual(plan['power_switch_version'], 1)
        rules = {row['rule']: row for row in plan['rule_plan']}
        self.assertEqual(rules['DRV-A03']['instances'], ['Q1-GATE'])
        self.assertEqual(rules['DRV-E01']['applicability'], 'APPLICABLE')
        self.assertEqual(rules['DRV-E01']['readiness'], 'WAITING_EVIDENCE')

    def test_bjt_base_is_traced_without_mos_on_resistance_requirements(self):
        db = switch_board(load=None)
        db['parts']['Q1'].update(part='MMBT3904', value='MMBT3904',
                                prim='Transistor_BJT:MMBT3904')
        db['pinname'].update({'Q1.1': 'B', 'Q1.2': 'C', 'Q1.3': 'E'})
        inventory = build_inventory(db)
        switch = switches_of(inventory)['Q1']
        self.assertEqual(switch['kind'], 'bjt')
        self.assertEqual(switch['gate_node'], 'Q1.1')
        self.assertNotIn('pin-roles:Q1', switch['gaps'])
        plan = build_review_plan(db)
        items = [x for x in plan['checks'] if x['object'].get('power_switch')]
        self.assertEqual({x['rule'] for x in items}, {'DRV-C02'})
        self.assertFalse(any('RDS(on)' in p for x in items for p in x['required_inputs']))
        self.assertTrue(any('VBE/VCE' in p for x in items for p in x['required_inputs']))

    def test_declared_linear_mos_retains_stress_and_clamp_checks(self):
        for role in ('linear', 'source_follower'):
            with self.subTest(role=role):
                db = switch_board()
                intent = bound_intent(db, {'power_switches': {'schema_version': 2,
                    'switches': [{'id': 'Q1-LINEAR', 'ref': 'Q1', 'role': role,
                                  'citation': 'synthetic linear-stage mode map'}]}})
                self.assertEqual(validate_power_switch_intent(intent, db), [])
                switch = switches_of(build_inventory(db, intent), 'run')['Q1']
                self.assertEqual(switch['role'], role)
                self.assertEqual(switch['role_citation'], 'synthetic linear-stage mode map')
                plan = build_review_plan(db, intent)
                items = [x for x in plan['checks'] if x['object'].get('power_switch')]
                self.assertEqual({x['rule'] for x in items}, {'DRV-C02', 'DRV-D01'})
                self.assertIn('DRV-A04', [f['rule'] for f in findings(db, intent)])

    def test_declared_level_shifter_leaves_drive_checks_to_the_level_shift_circuit(self):
        db = {'nets': {}, 'parts': {}, 'pin2net': {}, 'pinname': {}, 'pintype': {},
              'pseudo_nets': [], 'ref2page': {}}
        add(db, 'Q1', 'BSS138', [('1', 'G', 'VCC_3V3'), ('2', 'S', 'SDA_LV'), ('3', 'D', 'SDA_HV')])
        add(db, 'R1', '10K', [('1', '1', 'VCC_3V3'), ('2', '2', 'SDA_LV')])
        add(db, 'R2', '10K', [('1', '1', 'VCC_5V'), ('2', '2', 'SDA_HV')])
        undeclared = build_review_plan(db)
        self.assertTrue([x for x in undeclared['checks'] if x['object'].get('power_switch')])
        intent = bound_intent(db, {'power_switches': {'schema_version': 2,
            'switches': [{'id': 'Q1-XLAT', 'ref': 'Q1', 'role': 'level_shifter',
                          'citation': 'synthetic bidirectional open-drain translator'}]}})
        self.assertEqual(validate_power_switch_intent(intent, db), [])
        self.assertEqual(switches_of(build_inventory(db, intent), 'run')['Q1']['role'], 'level_shifter')
        plan = build_review_plan(db, intent)
        self.assertEqual([x for x in plan['checks'] if x['object'].get('power_switch')], [])
        self.assertFalse([f for f in findings(db, intent) if f['rule'].startswith('DRV')])

    def test_floating_source_without_declared_role_keeps_mos_drive_check(self):
        db = switch_board(load=None)
        db['nets']['GND'].remove('Q1.3')
        db['nets']['FLOAT_SOURCE'] = ['Q1.3']
        db['pin2net']['Q1.3'] = 'FLOAT_SOURCE'
        self.assertEqual(switches_of(build_inventory(db))['Q1']['topology'], 'floating')
        plan = build_review_plan(db)
        items = [x for x in plan['checks'] if x['object'].get('power_switch')]
        self.assertIn('DRV-E01', {x['rule'] for x in items})

    def test_invalid_role_is_rejected_before_membership_checks(self):
        db = switch_board()
        for role in (None, [], {}, True, ''):
            with self.subTest(role=role):
                intent = bound_intent(db, {'power_switches': {'schema_version': 2,
                    'switches': [{'id': 'Q1', 'ref': 'Q1', 'role': role,
                                  'citation': 'synthetic role-input record'}]}})
                errors = validate_power_switch_intent(intent, db)
                self.assertTrue(any('role must be a non-empty string' in e for e in errors))

    def test_damping_item_only_exists_with_a_switch_node(self):
        plan = build_review_plan(switch_board(load=None))
        self.assertNotIn('DRV-D01', {x['rule'] for x in plan['checks']})

    def test_stale_object_binding_is_reported(self):
        db = switch_board()
        plan = build_review_plan(db)
        item = next(x for x in plan['checks'] if x['object'].get('power_switch'))
        stale = dict(item['object'], power_switch_digest='0' * 64)
        self.assertEqual(PowerSwitchChecker().object_errors('X', stale, plan['power_switch']),
                         ['X: stale power switch object binding'])

    def test_intent_validation_rejects_unsound_configuration(self):
        db = switch_board()
        base = {'schema_version': 2,
                'switches': [{'id': 'q1', 'ref': 'Q1', 'citation': 'driver schematic'}]}
        cases = {
            'schema_version must be 2': {'schema_version': 1},
            'switch ref unknown: QX': {'switches': [{'id': 'x', 'ref': 'QX', 'citation': 'y'}]},
            'switch needs a citation': {'switches': [{'id': 'x', 'ref': 'Q1'}]},
            'gate_net unknown: NOPE': {'switches': [{'id': 'x', 'ref': 'Q1', 'citation': 'y',
                                                     'gate_net': 'NOPE'}]},
        }
        self.assertEqual(validate_power_switch_intent(bound_intent(db, {'power_switches': base}), db), [])
        for message, override in cases.items():
            errors = validate_power_switch_intent(
                bound_intent(db, {'power_switches': dict(base, **override)}), db)
            self.assertTrue(any(message in error for error in errors), (message, errors))


class HotRuleTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def run_check(self, check, db=None):
        db = db or switch_board(snubber='rc')
        evidence = {'schema_version': 2, 'checks': [check]}
        audit = bind_evidence(db, evidence, self.directory.name)
        self.assertEqual(validate_evidence(evidence), [])
        lint = Lint(db, evidence=evidence, datasheet_audit=audit)
        lint.run()
        results = [x for x in lint.results if x['check_id'] == check['id']]
        self.assertEqual(len(results), 1)
        return results[0]

    def test_sufficient_drive_passes(self):
        result = self.run_check(gate_check())
        self.assertEqual(result['review_result'], 'PASS')
        self.assertEqual(result['rule'], 'DRV-E01')
        self.assertIn('SOA', result['scope'])

    def test_drive_below_rds_on_condition_fails(self):
        result = self.run_check(gate_check(vgs_drive_v={'min': 3.0, 'max': 5.0}))
        self.assertEqual(result['review_result'], 'FAIL')
        self.assertIn('低于所需导通栅压', result['detail'])

    def test_drive_above_absolute_maximum_fails(self):
        result = self.run_check(gate_check(vgs_drive_v={'min': 9.0, 'max': 25.0}))
        self.assertEqual(result['review_result'], 'FAIL')
        self.assertIn('超出绝对最大范围', result['detail'])

    def test_p_channel_is_compared_on_magnitude(self):
        result = self.run_check(gate_check(channel='p', vgs_drive_v={'min': -12.6, 'max': -9.0},
                                           vgs_rds_on_v=-4.5))
        self.assertEqual(result['review_result'], 'PASS')
        result = self.run_check(gate_check(channel='p', vgs_drive_v={'min': -3.0, 'max': -1.0},
                                           vgs_rds_on_v=-4.5))
        self.assertEqual(result['review_result'], 'FAIL')

    def test_missing_guaranteed_values_stay_insufficient(self):
        check = gate_check()
        check.pop('vgs_abs_v')
        result = self.run_check(check)
        self.assertEqual(result['review_result'], 'INSUFFICIENT')
        self.assertIn('vgs_abs_v 缺少保证 min/max', result['detail'])

    def test_malformed_evidence_is_rejected_by_the_contract(self):
        evidence = {'schema_version': 2, 'checks': [gate_check(channel='x')]}
        self.assertTrue(any('channel' in error for error in validate_evidence(evidence)))
        evidence = {'schema_version': 2, 'checks': [gate_check(kind='divider')]}
        self.assertTrue(any('kind' in error for error in validate_evidence(evidence)))


if __name__ == '__main__':
    unittest.main()


class SourceReturnTest(unittest.TestCase):
    def fixture(self, value='0.11/1%/1W'):
        db = switch_board()
        db['parts']['Q1'].update(part='HVFET', value='HVFET', prim='Custom:HVFET')
        db['nets']['GND'].remove('Q1.3')
        db['nets']['SENSE'] = ['Q1.3']
        db['pin2net']['Q1.3'] = 'SENSE'
        add(db, 'R9', value, [('1', '1', 'SENSE'), ('2', '2', 'GND')])
        intent = bound_intent(db, {'power_switches': {'schema_version': 2, 'switches': [
            {'id': 'Q1-SW', 'ref': 'Q1', 'role': 'switching', 'citation': 'fixture switching map',
             'source_return': {'ref': 'R9', 'ground_net': 'GND', 'citation': 'fixture current sense'}}]}})
        return db, intent

    def test_cited_fitted_return_retains_resistance_and_source_offset(self):
        db, intent = self.fixture()
        self.assertEqual(validate_power_switch_intent(intent, db), [])
        q = switches_of(build_inventory(db, intent), 'run')['Q1']
        self.assertEqual(q['topology'], 'low-side')
        self.assertEqual(q['source_net'], 'SENSE')
        self.assertAlmostEqual(q['source_return']['resistance_ohm'], .11)
        self.assertIn('Isource', q['source_return']['source_offset_model'])
        self.assertEqual(db['pin2net']['Q1.3'], 'SENSE')

    def test_no_declaration_does_not_infer_from_any_ground_resistor(self):
        db, intent = self.fixture('100K')
        intent['power_switches']['switches'][0].pop('source_return')
        self.assertEqual(switches_of(build_inventory(db, intent), 'run')['Q1']['topology'], 'floating')

    def test_unfitted_or_open_return_keeps_gap(self):
        for mode in ('dnp', 'open'):
            db, intent = self.fixture()
            if mode == 'dnp':
                intent['assemblies'][0]['population']['R9'] = False
            else:
                intent['assemblies'][0].setdefault('jumpers', {})['R9'] = 'open'
            q = switches_of(build_inventory(db, intent), 'run')['Q1']
            self.assertEqual(q['topology'], 'floating')
            self.assertIn('source-return:Q1', q['gaps'])

    def test_wrong_resistor_or_return_is_not_accepted(self):
        db, intent = self.fixture()
        intent['power_switches']['switches'][0]['source_return']['ref'] = 'R1'
        q = switches_of(build_inventory(db, intent), 'run')['Q1']
        self.assertIsNone(q['source_return'])
        self.assertIn('source-return:Q1', q['gaps'])
        intent['power_switches']['switches'][0]['source_return']['ground_net'] = 'V12'
        self.assertTrue(validate_power_switch_intent(intent, db))

    def test_missing_citation_and_unsupported_shape_rejected(self):
        db, intent = self.fixture()
        ret = intent['power_switches']['switches'][0]['source_return']
        ret['citation'] = ''
        self.assertTrue(validate_power_switch_intent(intent, db))
        ret['citation'] = 'fixture'; ret['via'] = ['R9']
        self.assertTrue(validate_power_switch_intent(intent, db))

    def test_unparseable_resistance_keeps_gap(self):
        db, intent = self.fixture('unknown')
        q = switches_of(build_inventory(db, intent), 'run')['Q1']
        self.assertIn('source-return-resistance:Q1', q['gaps'])

    def test_high_side_rail_with_load_resistor_is_not_low_side(self):
        db, intent = self.fixture()
        add(db, 'U9', 'REGULATOR', [('1', 'VOUT', 'SENSE'), ('2', 'VIN', 'V12'), ('3', 'GND', 'GND')])
        intent['assemblies'][0]['population']['U9'] = True
        q = switches_of(build_inventory(db, intent), 'run')['Q1']
        self.assertEqual(q['topology'], 'high-side')
        self.assertIsNone(q['source_return'])

    def test_switching_soa_requires_trajectory_and_repetition_not_auto_pass(self):
        db, intent = self.fixture()
        plan = build_review_plan(db, intent)
        row = next(x for x in plan['checks'] if x['rule'] == 'DRV-C02')
        self.assertEqual(row['readiness'], 'WAITING_EVIDENCE')
        self.assertTrue(row['analysis_required'])
        self.assertIn('单脉冲SOA', row['criterion'])
        self.assertTrue(any('VDS(t)-ID(t)' in x for x in row['required_inputs']))
        self.assertIsNone(row['review_result'])

    def test_raw_kind_declaration_cannot_remove_datasheet_gap(self):
        db, intent = self.fixture()
        intent['device_kinds'] = {'Q1': {'kind': 'mosfet', 'page': 1, 'quote': 'MOSFET'}}
        plan = build_review_plan(db, intent)
        q = switches_of(plan['power_switch'], 'run')['Q1']
        self.assertIn('datasheet-kind:Q1', q['gaps'])
        self.assertNotEqual(q['kind_basis'], 'datasheet')
        self.assertIsNone(q['kind_citation'])


class SharedClampTopologyTest(unittest.TestCase):
    """100W PD 复审：功率开关检查器要认得感性负载清单已认出的吸收，并把升压主二极管单列。"""

    def test_rcd_clamp_returned_to_the_supply_counts_as_snubber(self):
        db = switch_board(snubber='rcd')
        q1 = switches_of(build_inventory(db))['Q1']
        self.assertEqual([s['type'] for s in q1['snubbers']], ['rcd-clamp'])
        self.assertNotIn('DRV-A04', [f['rule'] for f in findings(db)])
        row = next(c for c in build_review_plan(db)['checks'] if c['rule'] == 'DRV-D01')
        self.assertIn('clamp:rcd-clamp:D3+C3+R3', row['trigger'])

    def test_boost_transfer_diode_is_not_a_snubber(self):
        db = switch_board(snubber='boost')
        q1 = switches_of(build_inventory(db))['Q1']
        self.assertIn('boost-transfer-diode', [s['type'] for s in q1['snubbers']])
        self.assertNotIn('DRV-A04', [f['rule'] for f in findings(db)])
        self.assertIn('DRV-D01', {c['rule'] for c in build_review_plan(db)['checks']})

    @staticmethod
    def rename(db, old, new):
        for node, net in list(db['pin2net'].items()):
            if net == old:
                db['pin2net'][node] = new
        db['nets'][new] = db['nets'].pop(old)
        return db

    def test_rcd_clamp_to_an_unnamed_bulk_bus_counts_as_snubber(self):
        db = self.rename(switch_board(snubber='rcd'), 'V12', 'BULK')
        add(db, 'C9', '47uF', [('1', '1', 'BULK'), ('2', '2', 'GND')])
        q1 = switches_of(build_inventory(db))['Q1']
        self.assertEqual([s['type'] for s in q1['snubbers']], ['rcd-clamp'])
        self.assertNotIn('DRV-A04', [f['rule'] for f in findings(db)])

    def test_boost_diode_into_an_unnamed_storage_bus_is_not_an_rcd(self):
        db = self.rename(switch_board(snubber='boost'), 'VOUT', 'BULK')
        db = self.rename(db, 'V12', 'RECT')
        q1 = switches_of(build_inventory(db))['Q1']
        types = [s['type'] for s in q1['snubbers']]
        self.assertIn('boost-transfer-diode', types)
        self.assertNotIn('rcd-clamp', types)
        self.assertNotIn('DRV-A04', [f['rule'] for f in findings(db)])

    def test_boost_reversed_or_unpopulated_diode_keeps_candidate(self):
        for reverse in (True, False):
            db = switch_board(snubber='boost')
            if reverse:
                db['pinname']['D3.1'], db['pinname']['D3.2'] = 'K', 'A'
            else:
                db['parts']['D3']['nc'] = True
            self.assertIn('DRV-A04', [f['rule'] for f in findings(db)])

    def test_flyback_secondary_net_is_not_the_switch_node_of_another_mosfet(self):
        from test_inductive_load import flyback_board, flyback_intent
        db = flyback_board()
        add(db, 'Q7', 'NMOS', [('1', 'G', 'PORT_G'), ('2', 'D', 'OUT'), ('3', 'S', 'VBUS')])
        add(db, 'C7', '470uF', [('1', '1', 'OUT'), ('2', '2', 'GND')])
        intent = flyback_intent(db)
        q7 = switches_of(build_inventory(db, intent), 'run')['Q7']
        self.assertNotIn('inductive:T1', q7['switch_node_evidence'])
        q1 = switches_of(build_inventory(db, intent), 'run')['Q1']
        self.assertIn('inductive:T1', q1['switch_node_evidence'])


class SynchronousRectifierTest(unittest.TestCase):
    def fixture(self):
        from test_inductive_load import flyback_board, flyback_intent
        db = flyback_board()
        add(db, 'Q8', 'NMOS', [('1','S','SEC_RTN'),('2','S','SEC_RTN'),('3','S','SEC_RTN'),
            ('4','G','SR_G'),('5','D','SR_D'),('6','D','SR_D'),('7','D','SR_D'),('8','D','SR_D')])
        add(db, 'U8', 'SR-CONTROLLER', [('1','DRV','SR_DRV'),('2','GND','SEC_RTN'),
             ('3','CS','SR_D'),('4','VCC','SR_VCC')])
        add(db, 'R8', '2R2', [('1','1','SR_DRV'),('2','2','SR_G')])
        add(db, 'R9', '100K', [('1','1','SR_G'),('2','2','SEC_RTN')])
        add(db, 'C8', '330uF', [('1','1','OUT'),('2','2','SEC_RTN')])
        intent = flyback_intent(db)
        intent['power_switches'] = {'schema_version':2,'switches':[
            {'id':'SR8','ref':'Q8','role':'synchronous_rectifier','citation':'fixture SR usage',
             'synchronous_rectifier': {'controller_ref':'U8','sense_node':'U8.3','return_node':'U8.2',
                'winding_nodes':['T1.3','T1.4'],'output_net':'OUT','channel':'n','citation':'fixture physical map'}}]}
        return db, intent

    def item(self, db, intent):
        return switches_of(build_inventory(db, intent), 'run')['Q8']

    def move(self, db, node, net):
        db['nets'][db['pin2net'][node]].remove(node)
        db['nets'].setdefault(net, []).append(node)
        db['pin2net'][node] = net

    def test_physical_sr_map_preserves_local_return_and_intervals(self):
        db, intent = self.fixture()
        self.assertEqual(validate_power_switch_intent(intent, db), [])
        q = self.item(db, intent)
        self.assertEqual(q['topology'], 'low-side-local-return')
        sr = q['synchronous_rectifier']
        self.assertEqual(sr['return_net'], 'SEC_RTN')
        self.assertEqual(sr['secondary_dot_node'], 'T1.4')
        self.assertEqual(sr['output_capacitors'], ['C8'])
        self.assertIn('not verified', sr['dynamic_status'])
        self.assertEqual(db['pin2net']['Q8.1'], 'SEC_RTN')

    def test_minimal_declaration_derives_unique_pins_winding_and_output(self):
        db, intent = self.fixture()
        cfg = intent['power_switches']['switches'][0]['synchronous_rectifier']
        for key in ('sense_node', 'return_node', 'winding_nodes', 'output_net'):
            cfg.pop(key)
        self.assertEqual(validate_power_switch_intent(intent, db), [])
        sr = self.item(db, intent)['synchronous_rectifier']
        self.assertEqual((sr['sense_node'], sr['return_node'], sr['output_net']), ('U8.3', 'U8.2', 'OUT'))
        self.assertEqual(sorted(sr['winding_nodes']), ['T1.3', 'T1.4'])
        self.assertEqual(sr['derived_fields'], ['output_net', 'return_node', 'sense_node', 'winding_nodes'])

    def test_official_pin_name_picks_return_when_trigger_shares_the_source_net(self):
        # 100W PD 复审：U501 的 VS(.2) 与 TRIG(.4) 都在源极网，最小声明曾因两个候选失败。
        db, intent = self.fixture()
        cfg = intent['power_switches']['switches'][0]['synchronous_rectifier']
        for key in ('sense_node', 'return_node', 'winding_nodes', 'output_net'):
            cfg.pop(key)
        db['nets']['SEC_RTN'].append('U8.5'); db['pin2net']['U8.5'] = 'SEC_RTN'; db['pinname']['U8.5'] = 'TRIG'
        sr = self.item(db, intent)['synchronous_rectifier']
        self.assertEqual(sr['return_node'], 'U8.2')

    def test_ambiguous_controller_pin_is_not_guessed(self):
        db, intent = self.fixture()
        cfg = intent['power_switches']['switches'][0]['synchronous_rectifier']
        cfg.pop('return_node')
        db['nets']['SEC_RTN'].append('U8.5'); db['pin2net']['U8.5'] = 'SEC_RTN'; db['pinname']['U8.5'] = 'VS'
        q = self.item(db, intent)
        self.assertIsNone(q['synchronous_rectifier'])
        self.assertIn('synchronous-rectifier-map:Q8', q['gaps'])

    def test_name_alone_does_not_classify_secondary_return(self):
        db, intent = self.fixture()
        intent.pop('power_switches')
        q = self.item(db, intent)
        self.assertEqual(q['topology'], 'floating')
        self.assertIsNone(q['synchronous_rectifier'])

    def test_controller_sense_or_reference_wrong_net_is_rejected(self):
        for node in ('U8.3','U8.2'):
            db, intent = self.fixture();self.move(db,node,'GND')
            q = self.item(db, intent)
            self.assertIsNone(q['synchronous_rectifier'])
            self.assertIn('synchronous-rectifier-map:Q8',q['gaps'])

    def test_every_parallel_terminal_is_checked(self):
        for node in ('Q8.2','Q8.8'):
            db, intent = self.fixture();self.move(db,node,'WRONG')
            self.assertIsNone(self.item(db,intent)['synchronous_rectifier'])

    def test_unfitted_controller_transformer_or_gate_resistor_breaks_map(self):
        for ref in ('U8','T1','R8'):
            db, intent = self.fixture();intent['assemblies'][0]['population'][ref]=False
            self.assertIsNone(self.item(db,intent)['synchronous_rectifier'])

    def test_missing_or_wrong_winding_mapping_is_not_guessed(self):
        for mode in ('missing','wrong-dot','primary-pair','duplicate'):
            db, intent = self.fixture()
            if mode=='missing':intent.pop('inductive_loads')
            elif mode=='wrong-dot':intent['inductive_loads']['loads'][0]['windings'][1]['dot']='3'
            elif mode=='duplicate':
                import copy
                intent['inductive_loads']['loads'].append(copy.deepcopy(intent['inductive_loads']['loads'][0]))
            else:intent['power_switches']['switches'][0]['synchronous_rectifier']['winding_nodes']=['T1.1','T1.2']
            self.assertIsNone(self.item(db,intent)['synchronous_rectifier'])

    def test_dnp_output_capacitor_does_not_prove_rectification_loop(self):
        db, intent = self.fixture();intent['assemblies'][0]['population']['C8']=False
        self.assertIsNone(self.item(db,intent)['synchronous_rectifier'])

    def test_nc_sense_or_power_pin_cannot_be_accepted(self):
        for node in ('U8.3','Q8.3'):
            db,intent=self.fixture();db['no_connect_nodes']=[node]
            self.assertIsNone(self.item(db,intent)['synchronous_rectifier'])

    def test_unsupported_channel_or_incomplete_declaration_is_invalid(self):
        db,intent=self.fixture();cfg=intent['power_switches']['switches'][0]['synchronous_rectifier']
        cfg['channel']='p'
        self.assertTrue(validate_power_switch_intent(intent,db))
        cfg['channel']='n';cfg.pop('citation')
        self.assertTrue(validate_power_switch_intent(intent,db))

    def test_local_return_cannot_be_primary_return(self):
        db,intent=self.fixture()
        for node in ('Q8.1','Q8.2','Q8.3','U8.2','R9.2','C8.2'):self.move(db,node,'GND')
        self.assertIsNone(self.item(db,intent)['synchronous_rectifier'])

    def test_plan_keeps_timing_thermal_and_soa_pending(self):
        db,intent=self.fixture();p=build_review_plan(db,intent)
        row=next(x for x in p['checks'] if x['rule']=='DRV-C02' and x['object'].get('ref')=='Q8')
        self.assertIsNone(row['review_result'])
        self.assertEqual(row['readiness'],'WAITING_EVIDENCE')
        self.assertTrue(row['analysis_required'])
        self.assertTrue(any('次级模式' in x for x in row['required_inputs']))
        self.assertTrue(any('反向电流' in x for x in row['required_inputs']))
        self.assertIn('体二极管区间',row['criterion'])


    def test_winding_dependency_is_bound_and_inventory_reconstructs(self):
        import copy
        db,intent=self.fixture();inventory=build_inventory(db,intent)
        self.assertEqual(build_inventory(db,inventory['context']),inventory)
        changed=copy.deepcopy(intent)
        changed['inductive_loads']['loads'][0]['windings'][1]['dot']='3'
        self.assertNotEqual(build_inventory(db,changed)['digest'],inventory['digest'])
        self.assertIn('inductive_loads',inventory['context'])

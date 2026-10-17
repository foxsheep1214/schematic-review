import copy
import pathlib
import sys
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import board_intent
import catalog

from checkers.inductive_load import InductiveLoadChecker, build_inventory, validate_inductive_intent
from electrical_fixtures import bound_intent
from lint import Lint
from plan_review import build_review_plan


def add(db, ref, part, pins, nc=False):
    db['parts'][ref] = {'part': part, 'value': part, 'prim': part, 'jedec': 'X', 'nc': nc}
    for pin, name, net in pins:
        node = ref + '.' + pin
        db['nets'].setdefault(net, []).append(node)
        db['pin2net'][node] = net
        if name:
            db['pinname'][node] = name


def relay_board(clamp='forward', clamp_nc=False):
    """K1 线圈由 Q1 低边驱动，按参数决定钳位形态。"""
    db = {'nets': {}, 'parts': {}, 'pin2net': {}, 'pinname': {}, 'pseudo_nets': []}
    add(db, 'K1', 'RELAY-5V', [('1', 'COIL1', 'RELAY_DRV'), ('2', 'COIL2', 'V24')])
    add(db, 'Q1', 'AO3400', [('1', 'G', 'RELAY_EN'), ('2', 'D', 'RELAY_DRV'), ('3', 'S', 'GND')])
    if clamp == 'forward':
        add(db, 'D1', '1N4148', [('1', 'A', 'RELAY_DRV'), ('2', 'K', 'V24')], nc=clamp_nc)
    elif clamp == 'reversed':
        add(db, 'D1', '1N4148', [('1', 'K', 'RELAY_DRV'), ('2', 'A', 'V24')], nc=clamp_nc)
    elif clamp == 'rc':
        add(db, 'R9', 'RES', [('1', '1', 'RELAY_DRV'), ('2', '2', 'SNUB_MID')])
        add(db, 'C9', 'CAP', [('1', '1', 'SNUB_MID'), ('2', '2', 'V24')])
    elif clamp == 'unknown-roles':
        add(db, 'D1', '1N4148', [('1', '1', 'RELAY_DRV'), ('2', '2', 'V24')])
    return db


def converter_board():
    """开关电源储能电感：SW 引脚命中，不属于感性负载。"""
    db = {'nets': {}, 'parts': {}, 'pin2net': {}, 'pinname': {}, 'pseudo_nets': []}
    add(db, 'U5', 'BUCK-X', [('1', 'SW', 'SW_NODE'), ('2', 'VIN', 'V12'), ('3', 'GND', 'GND')])
    add(db, 'L1', 'IND-10UH', [('1', '1', 'SW_NODE'), ('2', '2', 'VCC_3V3')])
    add(db, 'Q2', 'AO3400', [('1', 'G', 'PWM'), ('2', 'D', 'SW_NODE'), ('3', 'S', 'GND')])
    return db


def loads_of(inventory, state='as-built'):
    entry = next(x for x in inventory['states'] if x['id'] == state)
    return {load['ref']: load for load in entry['loads']}


CHECKER_RULES = {rule.id for rule in catalog.rules(source='inductive_load')}


def findings(db, intent=None):
    return [f for f in Lint(db, '', intent).run() if f['rule'] in CHECKER_RULES]


class RecognitionTest(unittest.TestCase):
    def test_relay_with_flyback_diode_is_recognised_without_finding(self):
        db = relay_board()
        load = loads_of(build_inventory(db))['K1']
        self.assertEqual(load['basis'], 'topology')
        self.assertEqual(load['switch_net'], 'RELAY_DRV')
        self.assertEqual(load['rail_net'], 'V24')
        self.assertEqual(load['switch_ref'], 'Q1')
        self.assertEqual([c['type'] for c in load['clamps']], ['freewheel-diode'])
        self.assertEqual(load['clamps'][0]['orientation'], 'forward')
        self.assertEqual(findings(db), [])

    def test_missing_clamp_reports_il01(self):
        db = relay_board(clamp=None)
        load = loads_of(build_inventory(db))['K1']
        self.assertEqual(load['clamps'], [])
        self.assertIn('clamp:none-found', load['gaps'])
        hits = findings(db)
        self.assertEqual([f['rule'] for f in hits], ['DRV-A01'])
        self.assertIn('RELAY_DRV', hits[0]['detail'])

    def test_reversed_diode_reports_il02(self):
        hits = findings(relay_board(clamp='reversed'))
        self.assertEqual([f['rule'] for f in hits], ['DRV-A02'])

    def test_rc_snubber_counts_as_clamp(self):
        db = relay_board(clamp='rc')
        load = loads_of(build_inventory(db))['K1']
        self.assertEqual([c['type'] for c in load['clamps']], ['rc-snubber'])
        self.assertEqual(findings(db), [])

    def test_unplaced_clamp_is_reported_for_that_state(self):
        db = relay_board(clamp_nc=True)
        load = loads_of(build_inventory(db))['K1']
        self.assertEqual(load['clamps'], [])
        self.assertEqual([f['rule'] for f in findings(db)], ['DRV-A01'])

    def test_unknown_pin_roles_do_not_manufacture_orientation(self):
        db = relay_board(clamp='unknown-roles')
        load = loads_of(build_inventory(db))['K1']
        self.assertEqual(load['clamps'][0]['orientation'], 'unknown')
        self.assertIn('clamp-orientation:pin roles unknown', load['gaps'])
        self.assertEqual(findings(db), [])

    def test_converter_inductor_is_not_an_inductive_load(self):
        db = converter_board()
        self.assertEqual(loads_of(build_inventory(db)), {})
        self.assertEqual(findings(db), [])

    def test_external_load_stays_a_candidate_without_intent(self):
        db = relay_board(clamp=None)
        db['parts'].pop('K1')
        for node in ('K1.1', 'K1.2'):
            net = db['pin2net'].pop(node)
            db['nets'][net].remove(node)
            db['pinname'].pop(node, None)
        add(db, 'J7', 'CONN-2P', [('1', 'MOTOR+', 'MOTOR_DRV'), ('2', 'RTN', 'V24')])
        db['nets']['MOTOR_DRV'] = db['nets'].pop('RELAY_DRV') + db['nets']['MOTOR_DRV']
        for node in list(db['pin2net']):
            if db['pin2net'][node] == 'RELAY_DRV':
                db['pin2net'][node] = 'MOTOR_DRV'
        inventory = build_inventory(db)
        load = loads_of(inventory)['J7']
        self.assertEqual(load['basis'], 'name-hint')
        self.assertEqual(findings(db), [])
        plan = build_review_plan(db)
        item = next(x for x in plan['checks'] if x['rule'] == 'DRV-T01')
        self.assertEqual(item['applicability'], 'UNDETERMINED')


class IntentTest(unittest.TestCase):
    def intent(self, db, **overrides):
        cfg = {'schema_version': 2,
               'loads': [{'id': 'K1-COIL', 'ref': 'K1', 'kind': 'relay',
                          'citation': 'synthetic relay coil spec'}]}
        cfg.update(overrides)
        return bound_intent(db, {'inductive_loads': cfg})

    def test_declared_state_and_load_upgrade_basis(self):
        db = relay_board()
        inventory = build_inventory(db, self.intent(db))
        load = loads_of(inventory, 'run')['K1']
        self.assertEqual(load['basis'], 'declared')
        self.assertEqual(load['gaps'], [])

    def test_undeclared_population_stays_a_gap(self):
        db = relay_board()
        intent = self.intent(db)
        del intent['assemblies'][0]['population']['D1']
        load = loads_of(build_inventory(db, intent), 'run')['K1']
        self.assertIn('population:D1', load['gaps'])
        self.assertIn('clamp:none-found', load['gaps'])

    def test_exclusion_removes_the_candidate(self):
        db = relay_board(clamp=None)
        intent = self.intent(db)
        intent['inductive_loads']['exclusions'] = [
            {'ref': 'K1', 'citation': 'synthetic: coil driven externally, reviewed separately'}]
        self.assertEqual(loads_of(build_inventory(db, intent), 'run'), {})

    def test_intent_validation_rejects_unsound_configuration(self):
        db = relay_board()
        cases = {
            'schema_version must be 2': {'schema_version': 1},
            'load ref unknown: QX': {'loads': [{'id': 'x', 'ref': 'QX', 'citation': 'y'}]},
            'load needs a citation': {'loads': [{'id': 'x', 'ref': 'K1'}]},
        }
        for message, override in cases.items():
            errors = validate_inductive_intent(self.intent(db, **override), db)
            self.assertTrue(any(message in error for error in errors), (message, errors))

    def test_assembly_states_must_live_in_the_shared_section(self):
        db = relay_board()
        moved = self.intent(db)
        moved['inductive_loads']['states'] = moved.pop('assemblies')
        errors = validate_inductive_intent(moved, db)
        self.assertTrue(any('moved to intent.assemblies' in error for error in errors), errors)
        self.assertTrue(any('requires intent.assemblies' in error for error in errors), errors)
        self.assertIn('assemblies: state needs assembly/configuration citation',
                      board_intent.validate(bound_intent(
                          db, {}, assemblies=[{'id': 'run', 'population': {}}]), db))

    def test_stale_fingerprint_is_rejected(self):
        db = relay_board()
        intent = self.intent(db)
        intent['input_sha256'] = '0' * 64
        self.assertIn('stale input_sha256', board_intent.validate(intent, db))


class PlanBindingTest(unittest.TestCase):
    def test_plan_items_bind_to_the_inventory_digest(self):
        db = relay_board()
        plan = build_review_plan(db)
        items = [x for x in plan['checks'] if x['object'].get('inductive_load')]
        self.assertEqual(len(items), 2)
        for item in items:
            self.assertEqual(item['object']['inductive_load_digest'], plan['inductive_load']['digest'])
        self.assertEqual(plan['inductive_load_version'], 1)

    def test_checker_reports_stale_object_binding(self):
        db = relay_board()
        plan = build_review_plan(db)
        checker = InductiveLoadChecker()
        item = next(x for x in plan['checks'] if x['object'].get('inductive_load'))
        stale = copy.deepcopy(item['object'])
        stale['inductive_load_digest'] = '0' * 64
        self.assertEqual(checker.object_errors('X', stale, plan['inductive_load']),
                         ['X: stale inductive load object binding'])

    def test_states_that_do_not_touch_the_load_share_one_check(self):
        db = relay_board()
        add(db, 'D9', 'LED', [('1', 'A', 'LED_A'), ('2', 'K', 'GND')])
        intent = bound_intent(db, {'inductive_loads': {'schema_version': 2, 'loads': [
            {'id': 'K1-COIL', 'ref': 'K1', 'kind': 'relay', 'citation': 'synthetic relay coil spec'}]}})
        base = intent['assemblies'][0]
        intent['assemblies'] = [base, dict(base, id='no-led', population=dict(base['population'], D9=False)),
                                dict(base, id='no-clamp', population=dict(base['population'], D1=False))]
        plan = build_review_plan(db, intent)
        items = [x for x in plan['checks'] if x['rule'] == 'DRV-C01']
        merged = [x for x in items if x['object'].get('states')]
        self.assertEqual(len(items), 2, [x['object'] for x in items])
        self.assertEqual(merged[0]['object']['states'], ['run', 'no-led'])
        self.assertEqual(merged[0]['object']['state'], 'run')
        alone = [x for x in items if not x['object'].get('states')]
        self.assertEqual(alone[0]['object']['state'], 'no-clamp')

    def test_rule_plan_lists_both_cold_rules(self):
        plan = build_review_plan(relay_board())
        rules = {row['rule']: row for row in plan['rule_plan']}
        self.assertIn('DRV-A01', rules)
        self.assertIn('DRV-A02', rules)
        self.assertEqual(rules['DRV-A01']['instances'], ['K1-RELAY-DRV'])


def boost_board(diode='forward', diode_nc=False):
    db = {'nets': {}, 'parts': {}, 'pin2net': {}, 'pinname': {}, 'pseudo_nets': []}
    add(db, 'L8', 'L', [('1', '1', 'INPUT'), ('2', '2', 'DRAIN_NODE')])
    add(db, 'Q8', 'NMOS', [('1', 'G', 'GATE'), ('2', 'D', 'DRAIN_NODE'), ('3', 'S', 'SENSE')])
    add(db, 'R8', 'RES', [('1', '1', 'SENSE'), ('2', '2', 'GND')])
    add(db, 'C8', 'CAP', [('1', '1', 'INPUT'), ('2', '2', 'GND')])
    add(db, 'C9', 'CAP', [('1', '1', 'OUTPUT'), ('2', '2', 'GND')])
    if diode:
        pins = [('1', 'A', 'DRAIN_NODE'), ('2', 'K', 'OUTPUT')]
        if diode == 'reversed':
            pins = [('1', 'K', 'DRAIN_NODE'), ('2', 'A', 'OUTPUT')]
        add(db, 'D8', 'DIODE', pins, nc=diode_nc)
    return db


class DiscreteBoostTest(unittest.TestCase):
    def test_off_path_goes_to_output_without_switch_channel(self):
        db = boost_board()
        load = loads_of(build_inventory(db))['L8']
        self.assertEqual(load['application'], 'boost_converter')
        self.assertEqual(load['clamps'][0]['ref'], 'D8')
        self.assertNotIn('clamp:none-found', load['gaps'])
        self.assertEqual(load['switching_paths']['on']['refs'], ['L8', 'Q8', 'R8'])
        off = load['switching_paths']['off']
        self.assertEqual(off['refs'], ['L8', 'D8'])
        self.assertEqual(off['to'], 'OUTPUT')
        self.assertEqual(off['blocked_refs'], ['Q8'])
        self.assertNotIn('Q8', off['refs'])
        self.assertNotIn('R8', off['refs'])
        self.assertEqual(off['return_branches'], [{'refs': ['C9'], 'to': 'GND'}])
        self.assertEqual(findings(db), [])

    def test_topology_does_not_pass_or_remove_rating_review(self):
        checks = [x for x in build_review_plan(boost_board())['checks']
                  if x['object'].get('inductive_load')]
        self.assertEqual(len(checks), 2)
        for check in checks:
            self.assertEqual(check['applicability'], 'APPLICABLE')
            self.assertIsNone(check['review_result'])
            self.assertEqual(check['object']['application'], 'boost_converter')
            self.assertIn('D8', check['object']['refs'])
            self.assertIn('R8', check['object']['refs'])
            self.assertIn('OUTPUT', check['object']['nets'])
        rated = next(x for x in checks if x['rule'] == 'DRV-C01')
        self.assertEqual(rated['readiness'], 'WAITING_EVIDENCE')
        self.assertTrue(rated['analysis_required'])
        self.assertTrue(any('重复工作电流' in x for x in rated['required_inputs']))
        self.assertFalse(any('线圈电阻' in x for x in rated['required_inputs']))

    def test_reversed_transfer_diode_is_not_a_successful_path(self):
        db = boost_board('reversed')
        load = loads_of(build_inventory(db))['L8']
        self.assertIn('boost-transfer-diode:reversed', load['gaps'])
        self.assertEqual([x['rule'] for x in findings(db)], ['DRV-A02'])
        self.assertTrue(InductiveLoadChecker().pass_blockers('X', None,
                        {'inventory_gaps': load['gaps']}, None))

    def test_missing_or_unfitted_transfer_diode_still_reports_missing_path(self):
        for db in (boost_board(None), boost_board(diode_nc=True)):
            with self.subTest(parts=list(db['parts'])):
                self.assertNotEqual(loads_of(build_inventory(db))['L8'].get('application'), 'boost_converter')
                self.assertEqual([x['rule'] for x in findings(db)], ['DRV-A01'])

    def test_no_input_return_unknown_diode_roles_and_parallel_switches_stay_unresolved(self):
        for mutation in ('input-cap-dnp', 'output-cap-dnp', 'sense-dnp', 'diode-roles', 'parallel'):
            with self.subTest(mutation=mutation):
                db = boost_board()
                if mutation in ('input-cap-dnp', 'output-cap-dnp', 'sense-dnp'):
                    db['parts'][{'input-cap-dnp': 'C8', 'output-cap-dnp': 'C9', 'sense-dnp': 'R8'}[mutation]]['nc'] = True
                elif mutation == 'diode-roles':
                    db['pinname']['D8.1'] = '1'
                    db['pinname']['D8.2'] = '2'
                else:
                    add(db, 'Q9', 'NMOS', [('1', 'G', 'GATE'), ('2', 'D', 'DRAIN_NODE'), ('3', 'S', 'SENSE')])
                self.assertNotEqual(loads_of(build_inventory(db))['L8'].get('application'), 'boost_converter')
                self.assertTrue(any(x['rule'] == 'DRV-A01' for x in findings(db)))

    def test_parallel_capacitors_are_not_connected_in_series_or_ambiguous(self):
        db = boost_board()
        add(db, 'C10', 'CAP', [('1', '1', 'OUTPUT'), ('2', '2', 'GND')])
        load = loads_of(build_inventory(db))['L8']
        self.assertEqual(load['application'], 'boost_converter')
        self.assertEqual(len(load['switching_paths']['off']['return_branches']), 2)

    def test_winding_or_supply_name_is_not_used_as_an_exemption(self):
        db = boost_board(None)
        db['parts']['L8']['value'] = 'PFC-BOOST'
        self.assertEqual([x['rule'] for x in findings(db)], ['DRV-A01'])
        # Ordinary relay suppression and reversed-clamp protection remain intact.
        self.assertEqual([x['rule'] for x in findings(relay_board(None))], ['DRV-A01'])
        self.assertEqual([x['rule'] for x in findings(relay_board('reversed'))], ['DRV-A02'])


def flyback_board(diode='forward', diode_nc=False):
    db = {'nets': {}, 'parts': {}, 'pin2net': {}, 'pinname': {}, 'pseudo_nets': []}
    add(db, 'T1', 'TRANSFORMER', [('1', 'P_DOT', 'BUS'), ('2', 'P', 'DRAIN'),
        ('3', 'S', 'OUT'), ('4', 'S_DOT', 'SR_D'), ('5', 'AUX', 'AUX'), ('6', 'AUX_DOT', 'GND')])
    add(db, 'Q1', 'NMOS', [('1', 'G', 'GATE'), ('2', 'D', 'DRAIN'), ('3', 'S', 'SENSE')])
    add(db, 'R1', 'RES', [('1', '1', 'SENSE'), ('2', '2', 'GND')])
    add(db, 'C1', 'CAP', [('1', '1', 'CLAMP'), ('2', '2', 'BUS')])
    add(db, 'R2', 'RES', [('1', '1', 'CLAMP'), ('2', '2', 'BUS')])
    add(db, 'R3', 'RES', [('1', '1', 'CLAMP'), ('2', '2', 'BUS')])
    if diode:
        pins = [('1', 'A', 'DRAIN'), ('2', 'K', 'CLAMP')]
        if diode == 'reversed':pins = [('1', 'K', 'DRAIN'), ('2', 'A', 'CLAMP')]
        add(db, 'D1', 'DIODE', pins, nc=diode_nc)
    return db


def flyback_intent(db, **overrides):
    declaration = {'id': 'FLY', 'ref': 'T1', 'kind': 'flyback_transformer',
        'citation': 'synthetic controlled transformer winding/polarity drawing', 'windings': [
        {'role': 'primary', 'pins': ['1', '2'], 'dot': '1'},
        {'role': 'secondary', 'pins': ['3', '4'], 'dot': '4'},
        {'role': 'auxiliary', 'pins': ['5', '6'], 'dot': '6'}]}
    declaration.update(overrides)
    return bound_intent(db, {'inductive_loads': {'schema_version': 2, 'loads': [declaration]}})


class FlybackWindingTest(unittest.TestCase):
    def load(self, db, intent=None):
        return loads_of(build_inventory(db, intent or flyback_intent(db)), 'run')['T1']

    def test_unconnected_extra_pin_may_stay_unmapped(self):
        db = flyback_board()
        db['nets']['NC_T1_7'] = ['T1.7']; db['pin2net']['T1.7'] = 'NC_T1_7'
        self.assertEqual(validate_inductive_intent(flyback_intent(db), db), [])
        db['nets']['GND'].append('T1.7'); db['nets'].pop('NC_T1_7'); db['pin2net']['T1.7'] = 'GND'
        # 接了网的未映射脚可能是绕组或屏蔽，不能忽略。
        self.assertTrue(validate_inductive_intent(flyback_intent(db), db))

    def test_cited_map_recognises_primary_rcd_without_joining_windings(self):
        db = flyback_board()
        intent = flyback_intent(db)
        self.assertEqual(validate_inductive_intent(intent, db), [])
        self.assertEqual(board_intent.validate(intent, db), [])
        load = self.load(db, intent)
        self.assertEqual(load['application'], 'flyback_transformer')
        self.assertEqual(load['switch_net'], 'DRAIN')
        self.assertEqual(load['rail_net'], 'BUS')
        self.assertEqual(load['gaps'], [])
        self.assertEqual(load['clamps'][0]['capacitors'], ['C1'])
        self.assertEqual(load['clamps'][0]['resistors'], ['R2', 'R3'])
        self.assertEqual(load['clamps'][0]['return_net'], 'BUS')
        self.assertEqual(load['clamps'][0]['orientation'], 'forward')
        self.assertEqual(load['energy_paths']['off_main']['blocked_refs'], ['Q1'])
        self.assertEqual(load['energy_paths']['off_main']['to_windings'],
                         [['T1.3', 'T1.4'], ['T1.5', 'T1.6']])
        from checkers.netgraph import NetGraph
        graph = NetGraph(db)
        self.assertFalse(any(ref == 'T1' for ref, _ in graph.neighbors('BUS')))
        self.assertFalse(any(net in ('OUT', 'SR_D') for _, net in graph.neighbors('BUS')))
        self.assertEqual(findings(db, intent), [])

    def test_name_or_dot_labels_alone_do_not_guess_winding_pairs(self):
        load = loads_of(build_inventory(flyback_board()))['T1']
        self.assertIn('pin-roles:T1', load['gaps'])
        self.assertNotEqual(load.get('application'), 'flyback_transformer')

    def test_ratings_are_separate_and_never_auto_pass(self):
        db = flyback_board(); plan = build_review_plan(db, flyback_intent(db))
        checks = [x for x in plan['checks'] if x['object'].get('inductive_load')]
        self.assertEqual(len(checks), 2)
        for check in checks:
            self.assertIsNone(check['review_result'])
            self.assertIn('T1.4', check['object']['nodes'])
            self.assertIn('R3', check['object']['refs'])
        rated = next(x for x in checks if x['rule'] == 'DRV-C01')
        self.assertTrue(rated['analysis_required'])
        self.assertEqual(rated['readiness'], 'WAITING_EVIDENCE')
        self.assertTrue(any('漏感' in x for x in rated['required_inputs']))
        self.assertFalse(any('线圈电阻' in x for x in rated['required_inputs']))

    def test_reversed_rcd_stays_blocked_and_reports_direction(self):
        db = flyback_board('reversed'); intent = flyback_intent(db)
        load = self.load(db, intent)
        self.assertIn('flyback-rcd-diode:reversed', load['gaps'])
        self.assertEqual([x['rule'] for x in findings(db, intent)], ['DRV-A02'])
        self.assertTrue(InductiveLoadChecker().pass_blockers('X', None,
                        {'inventory_gaps': load['gaps']}, None))

    def test_tvs_across_switch_is_the_leakage_clamp_without_rcd(self):
        # rf1 公开板：无 RCD，SMCJ43A 跨漏极到地钳位漏感；双向符号画单向管，极性待核。
        db = flyback_board(None)
        add(db, 'D9', 'SMCJ43A TVS', [('1', 'A1', 'DRAIN'), ('2', 'A2', 'GND')])
        load = self.load(db)
        self.assertNotIn('flyback-rcd:not-recognised', load['gaps'])
        self.assertIn('flyback-tvs-clamp-polarity:unknown:D9', load['gaps'])
        self.assertEqual([(c['ref'], c['leakage_clamp']) for c in load['clamps']], [('D9', True)])
        self.assertEqual(load['energy_paths']['off_leakage']['branches'][0]['ref'], 'D9')

    def test_missing_or_dnp_rcd_parts_cannot_be_counted_as_a_path(self):
        for mutation in ('diode-missing', 'diode-dnp', 'capacitor-dnp', 'all-resistors-dnp'):
            with self.subTest(mutation=mutation):
                db = flyback_board(None if mutation == 'diode-missing' else 'forward', mutation == 'diode-dnp')
                if mutation == 'capacitor-dnp':db['parts']['C1']['nc'] = True
                if mutation == 'all-resistors-dnp':
                    db['parts']['R2']['nc'] = db['parts']['R3']['nc'] = True
                intent = flyback_intent(db)
                intent['assemblies'][0]['population'].update(
                    {ref: False for ref, part in db['parts'].items() if part.get('nc')})
                self.assertTrue(self.load(db, intent)['gaps'])
                self.assertEqual([x['rule'] for x in findings(db, intent)], ['DRV-A01'])

    def test_one_parallel_resistor_dnp_changes_rating_inventory(self):
        db = flyback_board(); intent = flyback_intent(db)
        intent['assemblies'][0]['population']['R3'] = False
        self.assertEqual(self.load(db, intent)['clamps'][0]['resistors'], ['R2'])

    def test_bad_map_missing_citation_or_shared_primary_secondary_nets_are_rejected(self):
        for mutation in ('duplicate-pin', 'missing-pin', 'bad-dot', 'no-secondary', 'no-citation', 'shared-net', 'nc', 'output-pin', 'wrong-declared-net', 'bad-ref'):
            with self.subTest(mutation=mutation):
                db = flyback_board(); intent = flyback_intent(db)
                d = intent['inductive_loads']['loads'][0]
                if mutation == 'duplicate-pin':d['windings'][1]['pins'][0] = '2'
                elif mutation == 'missing-pin':d['windings'].pop()
                elif mutation == 'bad-dot':d['windings'][0]['dot'] = '6'
                elif mutation == 'no-secondary':d['windings'][1]['role'] = 'auxiliary'
                elif mutation == 'no-citation':d['citation'] = ''
                elif mutation == 'shared-net':db['pin2net']['T1.3'] = 'BUS'
                elif mutation == 'nc':db['no_connect_nodes'] = ['T1.4']
                elif mutation == 'wrong-declared-net':d['rail_net'] = 'CLAMP'
                elif mutation == 'bad-ref':d['ref'] = []
                else:db['native_pintype'] = {'T1.4': 'output'}
                self.assertTrue(validate_inductive_intent(intent, db))
                self.assertTrue(self.load(db, intent)['gaps'])

    def test_primary_dot_conflict_and_unknown_diode_roles_remain_gaps(self):
        db = flyback_board(); intent = flyback_intent(db)
        intent['inductive_loads']['loads'][0]['windings'][0]['dot'] = '2'
        self.assertIn('flyback-primary-dot:verify-switched-winding-polarity', self.load(db, intent)['gaps'])
        db = flyback_board(); db['pinname']['D1.1'] = '1'; db['pinname']['D1.2'] = '2'
        self.assertIn('flyback-rcd-diode:unknown', self.load(db)['gaps'])

    def test_duplicate_declarations_and_parallel_switches_do_not_hide_ambiguity(self):
        db = flyback_board(); intent = flyback_intent(db)
        intent['inductive_loads']['loads'].append(
            {'id': 'CONFLICT', 'ref': 'T1', 'kind': 'coil', 'citation': 'conflicting purpose'})
        self.assertTrue(validate_inductive_intent(intent, db))
        self.assertIn('pin-roles:T1', self.load(db, intent)['gaps'])
        db = flyback_board()
        add(db, 'Q2', 'NMOS', [('1', 'G', 'GATE'), ('2', 'D', 'DRAIN'), ('3', 'S', 'SENSE')])
        self.assertIn('flyback-primary:ambiguous-parallel-switches', self.load(db)['gaps'])


class CommonModeInputFilterTest(unittest.TestCase):
    def board(self):
        db = {'nets': {}, 'parts': {}, 'pin2net': {}, 'pinname': {}, 'pseudo_nets': []}
        add(db, 'L1', 'COMMON_MODE_CHOKE', [
            ('1', '1', 'AC_L_IN'), ('2', '2', 'AC_L_OUT'),
            ('3', '3', 'AC_N_IN'), ('4', '4', 'AC_N_OUT')])
        return db

    def intent(self, db, **overrides):
        item = {'id': 'AC-CMC', 'ref': 'L1', 'kind': 'common_mode_input_filter',
                'windings': [['1', '2'], ['3', '4']],
                'citation': 'synthetic controlled input-filter purpose and winding map'}
        item.update(overrides)
        return bound_intent(db, {'inductive_loads': {'schema_version': 2, 'loads': [item]}})

    def load(self, db, intent):
        return loads_of(build_inventory(db, intent), 'run')['L1']

    def test_name_alone_is_not_a_scope_exemption(self):
        load = loads_of(build_inventory(self.board()))['L1']
        self.assertIn('pin-roles:L1', load['gaps'])
        self.assertNotEqual(load.get('applicability'), 'NOT_APPLICABLE')

    def test_controlled_map_produces_traceable_na_checks(self):
        db = self.board()
        intent = self.intent(db)
        self.assertEqual(validate_inductive_intent(intent, db), [])
        self.assertEqual(board_intent.validate(intent, db), [])
        load = self.load(db, intent)
        self.assertEqual(load['applicability'], 'NOT_APPLICABLE')
        self.assertEqual(load['gaps'], [])
        self.assertEqual(load['clamps'], [])
        self.assertEqual(load['windings'][0]['nodes'], ['L1.1', 'L1.2'])
        self.assertEqual(load['windings'][1]['nets'], ['AC_N_IN', 'AC_N_OUT'])
        self.assertIn('载流、绝缘、温升', load['scope_reason'])
        checks = [item for item in build_review_plan(db, intent)['checks']
                  if item['object'].get('inductive_load')]
        self.assertEqual({item['rule'] for item in checks}, {'DRV-C01', 'DRV-T01'})
        for item in checks:
            self.assertEqual(item['applicability'], 'NOT_APPLICABLE')
            self.assertEqual(item['readiness'], 'NOT_SCHEDULED')
            self.assertEqual(item['required_inputs'], [])
            self.assertIn(load['classification_citation'], item['trigger'])
        calculation = next(item for item in checks if item['rule'] == 'DRV-C01')
        self.assertFalse(calculation['analysis_required'])
        self.assertEqual(findings(db, intent), [])
        # The declaration is local to this checker; do not invent graph winding edges.
        from checkers.netgraph import NetGraph
        self.assertEqual(NetGraph(db).neighbors('AC_L_IN'), [])

    def test_bad_or_missing_declarations_cannot_suppress_candidates(self):
        cases = [
            {'windings': None}, {'windings': [['1', '2']]},
            {'windings': [['1', '2'], ['2', '4']]},
            {'windings': [['1', '2'], ['3', '9']]},
            {'citation': ''}, {'switch_net': 'AC_L_OUT'}, {'rail_net': 'AC_L_IN'},
        ]
        for overrides in cases:
            with self.subTest(overrides=overrides):
                db = self.board()
                intent = self.intent(db, **overrides)
                self.assertTrue(validate_inductive_intent(intent, db))
                load = self.load(db, intent)
                self.assertTrue(load['gaps'])
                self.assertNotEqual(load.get('applicability'), 'NOT_APPLICABLE')

    def test_invalid_physical_connections_or_roles_are_not_exempt(self):
        for mutation in ('extra-pin', 'short', 'ground', 'pseudo', 'nc', 'output'):
            with self.subTest(mutation=mutation):
                db = self.board()
                if mutation == 'extra-pin':
                    add(db, 'L1', 'COMMON_MODE_CHOKE', [('5', '5', 'EXTRA')])
                elif mutation == 'short':
                    db['pin2net']['L1.4'] = 'AC_L_IN'
                elif mutation == 'ground':
                    db['pin2net']['L1.4'] = 'GND'
                elif mutation == 'pseudo':
                    db['pseudo_nets'] = ['AC_N_OUT']
                elif mutation == 'nc':
                    db['no_connect_nodes'] = ['L1.4']
                else:
                    db['native_pintype'] = {'L1.1': 'output'}
                intent = self.intent(db)
                self.assertTrue(validate_inductive_intent(intent, db))
                self.assertNotEqual(self.load(db, intent).get('applicability'), 'NOT_APPLICABLE')

    def test_active_drive_direct_or_through_series_resistor_blocks_na(self):
        for active in ('mosfet', 'bjt', 'driver', 'converter', 'series-driver'):
            with self.subTest(active=active):
                db = self.board()
                net = 'AC_L_OUT'
                if active == 'series-driver':
                    add(db, 'R1', 'RES', [('1', '1', net), ('2', '2', 'DRIVE')])
                    net = 'DRIVE'
                if active == 'mosfet':
                    add(db, 'Q1', 'AO3400', [('1', 'G', 'EN'), ('2', 'D', net), ('3', 'S', 'GND')])
                elif active == 'bjt':
                    add(db, 'Q1', 'NPN', [('1', 'B', 'EN'), ('2', 'C', net), ('3', 'E', 'GND')])
                else:
                    pin = 'SW' if active == 'converter' else 'OUT'
                    add(db, 'U1', 'DRIVER', [('1', pin, net), ('2', 'VCC', 'V12'), ('3', 'GND', 'GND')])
                intent = self.intent(db)
                load = self.load(db, intent)
                self.assertTrue(any('active-node:' in gap for gap in load['gaps']), load)
                self.assertNotEqual(load.get('applicability'), 'NOT_APPLICABLE')

    def test_excluded_switch_cannot_hide_drive_but_dnp_switch_is_ignored(self):
        for fitted in (True, False):
            with self.subTest(fitted=fitted):
                db = self.board()
                add(db, 'U1', 'DRIVER', [('1', 'OUT', 'AC_L_OUT'), ('2', 'VCC', 'V12')])
                intent = self.intent(db)
                intent['assemblies'][0]['population']['U1'] = fitted
                intent['inductive_loads']['exclusions'] = [{'ref': 'U1', 'citation': 'other scope'}]
                load = self.load(db, intent)
                self.assertEqual(load.get('applicability') == 'NOT_APPLICABLE', not fitted)

    def test_unknown_population_prevents_na(self):
        db = self.board()
        add(db, 'R1', 'RES', [('1', '1', 'AC_L_OUT'), ('2', '2', 'OTHER')])
        intent = self.intent(db)
        del intent['assemblies'][0]['population']['R1']
        load = self.load(db, intent)
        self.assertIn('population:R1', load['gaps'])
        self.assertNotEqual(load.get('applicability'), 'NOT_APPLICABLE')

    def test_duplicate_declarations_cannot_hide_ambiguity(self):
        db = self.board()
        intent = self.intent(db)
        intent['inductive_loads']['loads'].append(
            {'id': 'ALSO-LOAD', 'ref': 'L1', 'kind': 'coil', 'citation': 'conflicting use'})
        self.assertTrue(validate_inductive_intent(intent, db))
        load = self.load(db, intent)
        self.assertIn('pin-roles:L1', load['gaps'])
        self.assertNotEqual(load.get('applicability'), 'NOT_APPLICABLE')

    def test_false_filter_declaration_does_not_hide_missing_relay_clamp(self):
        db = relay_board(clamp=None)
        intent = self.intent(db, ref='K1')
        self.assertTrue(validate_inductive_intent(intent, db))
        self.assertEqual([item['rule'] for item in findings(db, intent)], ['DRV-A01'])


if __name__ == '__main__':
    unittest.main()

"""Synthetic rail × assembly declarations; no third-party board fixture."""
import copy
import pathlib
import sys
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import board_intent
from checkers.supervision import SupervisionChecker, build_inventory, validate_supervision_intent
from plan_review import build_review_plan
from parse_kicad import parse
from test_parse_kicad import netlist, comp, net
from electrical_fixtures import bound_intent
from test_inductive_load import add


def board():
    db = {'parts': {}, 'nets': {}, 'pin2net': {}, 'pinname': {}, 'pintype': {},
          'pseudo_nets': []}
    add(db, 'U1', 'IC', [('1', 'VDD', 'VCC_A'), ('2', 'VCC', 'VCC_B'), ('3', 'GND', 'GND')])
    add(db, 'P1', 'Connector:Conn_01x02', [('1', '1', 'VCC_A'), ('2', '2', 'GND')])
    add(db, 'P2', 'Connector:Conn_01x02', [('1', '1', 'VCC_B'), ('2', '2', 'GND')])
    db['native_pintype'] = {n: 'power_in' if n.startswith('U1.') else 'passive'
                            for n in db['pin2net']}
    db['declared_native_pintype'] = dict(db['native_pintype'])
    return db


def requirement(db, net, state, source, required=False, role='external_supply'):
    return {'net': net, 'state': state, 'required': required,
            'criterion': 'No board monitor required; external system supervises this supply.',
            'citation': 'Synthetic controlled requirements REV-B section 4 scope',
            'identity': {'source_node': source, 'source_role': role,
                         'part': {k: db['parts'][source.split('.')[0]].get(k, '')
                                  for k in ('part', 'prim', 'value', 'jedec')},
                         'native_pintypes': {n: t for n, t in db.get('native_pintype', {}).items()
                                             if n.split('.')[0] == source.split('.')[0]},
                         'pin_name': db['pinname'][source],
                         'citation': 'Synthetic native source role and physical pin map REV-B'}}


def intent_for(db):
    intent = bound_intent(db, state='A')
    intent['assemblies'].append(dict(copy.deepcopy(intent['assemblies'][0]), id='B'))
    intent['supervision'] = {'schema_version': 2, 'supervisors': [], 'rail_requirements': [
        requirement(db, net, state, source) for state in ('A', 'B')
        for net, source in (('VCC_A', 'P1.1'), ('VCC_B', 'P2.1'))]}
    return intent


def coverage(db, intent):
    plan = build_review_plan(db, intent)
    checks = {x['object']['state']: x for x in plan['checks'] if x['rule'] == 'PWR-T04'}
    return plan, checks


class RailRequirementsTest(unittest.TestCase):
    def setUp(self):
        self.db = board()
        self.intent = intent_for(self.db)

    def test_bound_dual_rail_dual_state_manual_scope_is_expressible(self):
        self.assertEqual(validate_supervision_intent(self.intent, self.db), [])
        plan, checks = coverage(self.db, self.intent)
        self.assertEqual(set(checks), {'A', 'B'})
        for check in checks.values():
            self.assertEqual(check['inventory_gaps'], [])
            self.assertEqual(SupervisionChecker().pass_blockers(check['id'], check, check,
                                                              plan['supervision']), [])
            self.assertEqual(check['applicability'], 'APPLICABLE')
        for state in plan['supervision']['states']:
            for rail in state['rails']:
                self.assertIsNone(rail['monitor'])
                self.assertIn('rail-unmonitored:' + rail['net'], rail['observation_gaps'])
                self.assertIn('rail-identity:' + rail['net'], rail['observation_gaps'])
                self.assertTrue(rail['scope_qualified'])

    def test_required_true_without_monitor_still_blocks(self):
        self.intent['supervision']['rail_requirements'][0]['required'] = True
        _, checks = coverage(self.db, self.intent)
        self.assertEqual(checks['A']['inventory_gaps'], ['rail-unmonitored:VCC_A'])
        self.assertEqual(checks['B']['inventory_gaps'], [])

    def test_one_declaration_does_not_cover_other_rail_or_state(self):
        self.intent['supervision']['rail_requirements'] = self.intent['supervision']['rail_requirements'][:1]
        _, checks = coverage(self.db, self.intent)
        self.assertNotIn('rail-unmonitored:VCC_A', checks['A']['inventory_gaps'])
        self.assertIn('rail-unmonitored:VCC_B', checks['A']['inventory_gaps'])
        self.assertIn('rail-unmonitored:VCC_A', checks['B']['inventory_gaps'])

    def test_missing_or_unknown_required_cannot_qualify(self):
        for value in (None, 'UNKNOWN', 0, ''):
            with self.subTest(value=value):
                intent = copy.deepcopy(self.intent)
                intent['supervision']['rail_requirements'][0]['required'] = value
                self.assertTrue(validate_supervision_intent(intent, self.db))
                _, checks = coverage(self.db, intent)
                self.assertIn('rail-unmonitored:VCC_A', checks['A']['inventory_gaps'])

    def test_missing_written_scope_or_identity_cannot_qualify(self):
        for field in ('criterion', 'citation', 'identity', 'state', 'net'):
            with self.subTest(field=field):
                intent = copy.deepcopy(self.intent)
                intent['supervision']['rail_requirements'][0].pop(field)
                self.assertTrue(validate_supervision_intent(intent, self.db))
                _, checks = coverage(self.db, intent)
                self.assertIn('rail-unmonitored:VCC_A', checks['A']['inventory_gaps'])

    def test_incomplete_identity_cannot_qualify(self):
        for field in ('source_node', 'source_role', 'part', 'pin_name', 'native_pintypes', 'citation'):
            with self.subTest(field=field):
                intent = copy.deepcopy(self.intent)
                intent['supervision']['rail_requirements'][0]['identity'].pop(field)
                self.assertTrue(validate_supervision_intent(intent, self.db))
                _, checks = coverage(self.db, intent)
                self.assertIn('rail-unmonitored:VCC_A', checks['A']['inventory_gaps'])

    def test_nonactual_net_source_pin_and_identity_rejected(self):
        mutations = [('net', 'VCC_X'), ('state', 'C'), ('source_node', 'P9.1'),
                     ('source_node', 'P1.2'), ('source_node', 'U1.1'),
                     ('part', 'Wrong MPN'), ('pin_name', '2'), ('source_role', 'unknown')]
        for field, value in mutations:
            with self.subTest(field=field, value=value):
                intent = copy.deepcopy(self.intent)
                item = intent['supervision']['rail_requirements'][0]
                (item if field in ('net', 'state') else item['identity'])[field] = value
                self.assertTrue(validate_supervision_intent(intent, self.db))
                _, checks = coverage(self.db, intent)
                self.assertIn('rail-unmonitored:VCC_A', checks['A']['inventory_gaps'])

    def test_dnp_source_in_one_state_is_not_inherited(self):
        self.intent['assemblies'][0]['population']['P1'] = False
        self.assertTrue(validate_supervision_intent(self.intent, self.db))
        _, checks = coverage(self.db, self.intent)
        self.assertIn('rail-unmonitored:VCC_A', checks['A']['inventory_gaps'])
        self.assertEqual(checks['B']['inventory_gaps'], [])

    def test_stale_native_input_binding_cannot_qualify(self):
        self.db['pinname']['U1.1'] = 'VDD_NEW'
        self.assertTrue(validate_supervision_intent(self.intent, self.db))
        self.assertTrue(all(not rail.get('scope_qualified') for state in build_inventory(self.db, self.intent)['states'] for rail in state['rails']))
        with self.assertRaisesRegex(ValueError, 'stale input_sha256'):
            coverage(self.db, self.intent)

    def test_symbol_only_input_change_stales_binding(self):
        self.db['declared_pinname'] = {'U1.1': 'ALTERED'}
        self.assertTrue(all(not rail.get('scope_qualified') for state in build_inventory(self.db, self.intent)['states'] for rail in state['rails']))
        with self.assertRaisesRegex(ValueError, 'stale input_sha256'):
            coverage(self.db, self.intent)

    def test_other_assembly_gap_cannot_pass(self):
        self.intent['assemblies'][0]['population'].pop('U1')
        _, checks = coverage(self.db, self.intent)
        self.assertIn('population:U1', checks['A']['inventory_gaps'])
        self.assertTrue(SupervisionChecker().pass_blockers('X', checks['A'], checks['A'], {}))

    def test_duplicate_requirement_not_first_wins(self):
        self.intent['supervision']['rail_requirements'].append(copy.deepcopy(
            self.intent['supervision']['rail_requirements'][0]))
        self.assertTrue(validate_supervision_intent(self.intent, self.db))
        _, checks = coverage(self.db, self.intent)
        self.assertIn('rail-unmonitored:VCC_A', checks['A']['inventory_gaps'])

    def test_schema_v2_and_array_shape_still_required(self):
        for value in (None, {}, 'bad'):
            intent = copy.deepcopy(self.intent)
            intent['supervision']['rail_requirements'] = value
            self.assertTrue(validate_supervision_intent(intent, self.db))
            _, checks = coverage(self.db, intent)
            self.assertIn('rail-unmonitored:VCC_A', checks['A']['inventory_gaps'])
        self.intent['supervision']['schema_version'] = 1
        self.assertTrue(validate_supervision_intent(self.intent, self.db))
        _, checks = coverage(self.db, self.intent)
        self.assertIn('rail-unmonitored:VCC_A', checks['A']['inventory_gaps'])

    def test_legacy_section_and_exclusion_do_not_exempt_rails(self):
        self.intent['supervision'].pop('rail_requirements')
        self.intent['supervision']['exclusions'] = [{'ref': 'U1', 'citation': 'internal UVLO'}]
        self.assertEqual(validate_supervision_intent(self.intent, self.db), [])
        _, checks = coverage(self.db, self.intent)
        self.assertIn('rail-unmonitored:VCC_A', checks['A']['inventory_gaps'])

    def test_context_rebuild_and_digest_cover_scope_declaration(self):
        before = build_inventory(self.db, self.intent)
        rebuilt = build_inventory(self.db, before['context'])
        self.assertEqual(before, rebuilt)
        self.intent['supervision']['rail_requirements'][0]['required'] = True
        after = build_inventory(self.db, self.intent)
        self.assertNotEqual(before['digest'], after['digest'])
        plan, checks = coverage(self.db, self.intent)
        stale = dict(checks['A']['object'], supervision_digest=before['digest'])
        self.assertTrue(SupervisionChecker().object_errors('X', stale, plan['supervision']))

    def test_single_monitor_does_not_exempt_other_rail(self):
        add(self.db, 'U2', 'SUPERVISOR', [('1', 'SENSE', 'VCC_A'),
            ('2', 'RESET', 'RESET'), ('3', 'VDD', 'VCC_A')])
        self.db['pintype']['U2.2'] = 'OUT'
        self.intent = intent_for(self.db)
        self.intent['supervision']['rail_requirements'] = [x for x in
            self.intent['supervision']['rail_requirements'] if x['net'] == 'VCC_A']
        _, checks = coverage(self.db, self.intent)
        for check in checks.values():
            self.assertIn('rail-unmonitored:VCC_B', check['inventory_gaps'])

    def test_regulator_driver_identity_with_monitored_required_rail(self):
        add(self.db, 'U8', 'LDO', [('1', 'VOUT', 'VCC_A'), ('2', 'VIN', 'V12')])
        add(self.db, 'U9', 'SUPERVISOR', [('1', 'SENSE', 'VCC_A'), ('2', 'RESET', 'RESET')])
        self.db['pintype']['U9.2'] = 'OUT'
        self.intent = intent_for(self.db)
        for item in self.intent['supervision']['rail_requirements']:
            if item['net'] == 'VCC_A':
                item.update(requirement(self.db, 'VCC_A', item['state'], 'U8.1', True, 'rail_driver'))
        self.assertEqual(validate_supervision_intent(self.intent, self.db), [])
        _, checks = coverage(self.db, self.intent)
        for check in checks.values():
            self.assertNotIn('rail-unmonitored:VCC_A', check['inventory_gaps'])
            self.assertNotIn('rail-identity:VCC_A', check['inventory_gaps'])
            self.assertIn('rail-unmonitored:V12', check['inventory_gaps'])

    def test_custom_non_j_native_connector_is_supported(self):
        for field in ('parts',):
            self.db[field]['HEADER'] = self.db[field].pop('P1')
        for field in ('pin2net', 'pinname', 'native_pintype', 'declared_native_pintype'):
            for node in list(self.db[field]):
                if node.startswith('P1.'):
                    self.db[field]['HEADER.' + node.split('.')[1]] = self.db[field].pop(node)
        for net, nodes in self.db['nets'].items():
            self.db['nets'][net] = [n.replace('P1.', 'HEADER.') for n in nodes]
        for field in ('part', 'prim', 'value'):
            self.db['parts']['HEADER'][field] = 'CUSTOM_HEADER'
        self.intent = bound_intent(self.db, state='A')
        self.intent['supervision'] = {'schema_version': 2, 'supervisors': [],
            'rail_requirements': [requirement(self.db, 'VCC_A', 'A', 'HEADER.1'),
                                  requirement(self.db, 'VCC_B', 'A', 'P2.1')]}
        self.assertEqual(validate_supervision_intent(self.intent, self.db), [])
        _, checks = coverage(self.db, self.intent)
        self.assertEqual(checks['A']['inventory_gaps'], [])

    def test_ic_input_cannot_be_declared_external_supply(self):
        for pin_type in ('power_in', 'input', 'output'):
            intent = copy.deepcopy(self.intent)
            self.db['native_pintype']['U1.1'] = pin_type
            self.db['declared_native_pintype']['U1.1'] = pin_type
            intent['supervision']['rail_requirements'][0] = requirement(self.db, 'VCC_A', 'A', 'U1.1')
            intent['input_sha256'] = board_intent.input_fingerprint(self.db)
            self.assertTrue(validate_supervision_intent(intent, self.db))
            _, checks = coverage(self.db, intent)
            self.assertIn('rail-unmonitored:VCC_A', checks['A']['inventory_gaps'])

    def test_native_contact_role_and_identity_conflict_rejected(self):
        for key in ('part', 'prim', 'value', 'jedec', 'native_pintype', 'declared_native_pintype'):
            with self.subTest(key=key):
                db = copy.deepcopy(self.db)
                if key in ('native_pintype', 'declared_native_pintype'):
                    db[key]['P1.1'] = 'input'
                else:
                    db['parts']['P1'][key] = 'ALTERED'
                intent = copy.deepcopy(self.intent)
                intent['input_sha256'] = board_intent.input_fingerprint(db)
                self.assertTrue(validate_supervision_intent(intent, db))
                _, checks = coverage(db, intent)
                self.assertIn('rail-unmonitored:VCC_A', checks['A']['inventory_gaps'])

    def test_missing_native_contact_and_false_refdes_only_source_block(self):
        self.db['native_pintype'].pop('P1.2')
        self.intent = intent_for(self.db)
        self.assertTrue(validate_supervision_intent(self.intent, self.db))
        _, checks = coverage(self.db, self.intent)
        self.assertIn('rail-unmonitored:VCC_A', checks['A']['inventory_gaps'])

    def test_kicad_native_export_source_contract_and_type_mismatch(self):
        libparts = '<libparts><libpart lib="Calib" part="CustomHeader"><pins>' + ''.join(
            f'<pin num="{n}" name="{n}" type="passive"/>' for n in (1, 2)) + '</pins></libpart>' + \
            '<libpart lib="Calib" part="Chip"><pins><pin num="1" name="VDD" type="power_in"/>' + \
            '<pin num="2" name="GND" type="power_in"/></pins></libpart></libparts>'
        xml = netlist(comp('CUSTOM', 'Calib', 'CustomHeader', 'CustomHeader') +
                      comp('U1', 'Calib', 'Chip', 'Chip'),
                      net('VCC', ('CUSTOM', '1', '1', 'passive'), ('U1', '1', 'VDD', 'power_in')) +
                      net('GND', ('CUSTOM', '2', '2', 'passive'), ('U1', '2', 'GND', 'power_in')),
                      libparts=libparts)
        db = parse(xml)
        intent = bound_intent(db, state='RUN')
        intent['supervision'] = {'schema_version': 2, 'supervisors': [],
            'rail_requirements': [requirement(db, 'VCC', 'RUN', 'CUSTOM.1')]}
        self.assertEqual(validate_supervision_intent(intent, db), [])
        _, checks = coverage(db, intent)
        self.assertEqual(checks['RUN']['inventory_gaps'], [])
        mutated = parse(xml.replace('pinfunction="1" pintype="passive"',
                                    'pinfunction="1" pintype="input"'))
        intent['input_sha256'] = board_intent.input_fingerprint(mutated)
        intent['supervision']['rail_requirements'][0] = requirement(mutated, 'VCC', 'RUN', 'CUSTOM.1')
        self.assertTrue(validate_supervision_intent(intent, mutated))
        _, checks = coverage(mutated, intent)
        self.assertIn('rail-unmonitored:VCC', checks['RUN']['inventory_gaps'])

    def test_malformed_items_report_errors_without_crashing(self):
        for value in (None, [], 'bad', {'net': []}, {'net': {}, 'state': []}):
            intent = copy.deepcopy(self.intent)
            intent['supervision']['rail_requirements'] = [value]
            self.assertTrue(validate_supervision_intent(intent, self.db))
            _, checks = coverage(self.db, intent)
            self.assertIn('rail-unmonitored:VCC_A', checks['A']['inventory_gaps'])

    def test_legacy_verified_kind_does_not_change_raw_inventory_coverage(self):
        db = {'parts': {}, 'nets': {}, 'pin2net': {}, 'pinname': {}, 'pintype': {}, 'pseudo_nets': []}
        add(db, 'U1', 'CustomPart', [('1', 'VDD', 'VCC'), ('2', 'GND', 'GND')])
        add(db, 'P1', 'Connector:Conn_01x02', [('1', '1', 'VCC'), ('2', '2', 'GND')])
        intent = bound_intent(db, state='RUN')
        intent['supervision'] = {'schema_version': 2, 'supervisors': []}
        original = build_inventory(db, intent)
        intent[board_intent.VERIFIED_KEY] = {'U1': {'kind': 'connector',
            'citation': 'Synthetic audit-verified custom source labelled VDD'}}
        legacy = build_inventory(db, intent)
        self.assertEqual(original['states'], legacy['states'])
        self.assertEqual(original['discovery_gaps'], legacy['discovery_gaps'])
        self.assertEqual(legacy['states'][0]['rails'], [{'net': 'VCC', 'basis': 'name-hint',
            'monitor': None, 'loads': ['U1'], 'gaps': ['rail-identity:VCC']}])
        self.assertEqual(SupervisionChecker().rule_instances('PWR-A06', legacy), ['VCC'])
        self.assertEqual(build_inventory(db, legacy['context']), legacy)

    def test_requirement_mode_retains_verified_custom_source_qualification(self):
        db = {'parts': {}, 'nets': {}, 'pin2net': {}, 'pinname': {}, 'pintype': {}, 'pseudo_nets': []}
        add(db, 'U1', 'Chip', [('1', 'VDD', 'VCC'), ('2', 'GND', 'GND')])
        add(db, 'U8', 'CustomHeader', [('1', '1', 'VCC'), ('2', '2', 'GND')])
        db['native_pintype'] = {'U1.1': 'power_in', 'U1.2': 'power_in',
                               'U8.1': 'passive', 'U8.2': 'passive'}
        db['declared_native_pintype'] = dict(db['native_pintype'])
        intent = bound_intent(db, state='RUN')
        intent[board_intent.VERIFIED_KEY] = {'U8': {'kind': 'connector',
            'citation': 'Synthetic audit-verified custom source, IC-style reference only'}}
        intent['supervision'] = {'schema_version': 2, 'supervisors': [],
            'rail_requirements': [requirement(db, 'VCC', 'RUN', 'U8.1')]}
        self.assertEqual(validate_supervision_intent(intent, db), [])
        inventory = build_inventory(db, intent)
        rail = inventory['states'][0]['rails'][0]
        self.assertEqual(rail['loads'], ['U1'])
        self.assertTrue(rail['scope_qualified'])
        self.assertEqual(rail['gaps'], [])
        self.assertEqual(build_inventory(db, inventory['context']), inventory)

    def test_non_connector_j_prefix_is_not_source_identity(self):
        self.db['parts']['P1']['part'] = 'IC'
        self.db['parts']['P1']['prim'] = 'IC'
        self.db['parts']['P1']['value'] = 'IC'
        self.db['pinname']['P1.1'] = 'VIN'
        self.db['native_pintype']['P1.1'] = 'power_in'
        self.db['declared_native_pintype']['P1.1'] = 'power_in'
        self.intent = intent_for(self.db)
        self.assertTrue(validate_supervision_intent(self.intent, self.db))
        _, checks = coverage(self.db, self.intent)
        self.assertIn('rail-unmonitored:VCC_A', checks['A']['inventory_gaps'])


if __name__ == '__main__':
    unittest.main()

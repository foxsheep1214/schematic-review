import pathlib
import sys
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import catalog
from plan_review import BOARD_MATERIALS, build_review_plan, validate_intent


def sample_db():
    nets = {
        'VCC_3V3': ['R1.1', 'U1.5'],
        'REG_FB': ['U1.1', 'R1.2', 'R2.1'],
        'GND': ['R2.2', 'R3.2', 'R4.2'],
        'REG_EN': ['U1.2', 'R3.1'],
        'BOOT0': ['U2.1', 'R4.1'],
        'I2C_SCL': ['U2.2', 'J1.1'],
        'I2C_SDA': ['U2.3', 'J1.2'],
        'USB_TX_P': ['U2.4', 'J1.3'],
        'USB_TX_N': ['U2.5', 'J1.4'],
    }
    parts = {
        'U1': {'part': 'REG-X', 'value': 'REG-X', 'prim': 'REG-X',
               'jedec': 'QFN', 'nc': False},
        'U2': {'part': 'SOC-X', 'value': 'SOC-X', 'prim': 'SOC-X',
               'jedec': 'BGA', 'nc': False},
        'J1': {'part': 'CONN', 'value': 'CONN', 'prim': 'CONN',
               'jedec': 'CONN', 'nc': False},
        'R1': {'part': 'R', 'value': '20K', 'prim': 'R',
               'jedec': '0402', 'nc': False},
        'R2': {'part': 'R', 'value': '10K', 'prim': 'R',
               'jedec': '0402', 'nc': False},
        'R3': {'part': 'R', 'value': '10K', 'prim': 'R',
               'jedec': '0402', 'nc': False},
        'R4': {'part': 'R', 'value': '10K', 'prim': 'R',
               'jedec': '0402', 'nc': False},
    }
    return {
        'nets': nets,
        'parts': parts,
        'pin2net': {node: net for net, nodes in nets.items() for node in nodes},
        'pinname': {
            'U1.1': 'FB', 'U1.2': 'EN', 'U1.5': 'VOUT',
            'U2.1': 'BOOT0', 'U2.2': 'SCL', 'U2.3': 'SDA',
            'U2.4': 'USB_TX_P', 'U2.5': 'USB_TX_N',
            'J1.1': 'SCL', 'J1.2': 'SDA',
            'J1.3': 'USB_TX_P', 'J1.4': 'USB_TX_N',
        },
        'pintype': {'U1.1': 'IN', 'U1.2': 'IN', 'U1.5': 'OUT'},
        'ref2page': {'U1': 1, 'U2': 2, 'J1': 2},
        'pseudo_nets': [],
    }


def get_feature(plan, name):
    return next(item for item in plan['checks']
                if item['rule'] == 'REQ-Q07' and item['object'].get('package') == name)


def undetected(plan):
    return next(item for item in plan['checks'] if item['rule'] == 'REQ-Q08')


class ReviewPlanTests(unittest.TestCase):
    def test_first_pass_discovers_instances_without_inventing_na(self):
        plan = build_review_plan(sample_db())
        confirm = undetected(plan)
        self.assertIn('DDR', confirm['object']['packages'])
        self.assertIn('intent.features.DDR', confirm['required_inputs'])
        self.assertEqual(confirm['applicability'], 'APPLICABLE')
        self.assertIsNone(confirm['review_result'])
        self.assertFalse(any(item['object'].get('package') == 'DDR' for item in plan['checks']))
        self.assertEqual(get_feature(plan, 'USB')['applicability'],
                         'APPLICABLE')
        pair = next(item for item in plan['checks']
                    if item['rule'] == 'SIG-T01')
        self.assertTrue(pair['handoff']['required'])
        self.assertIsNone(pair['review_result'])
        self.assertNotIn('HANDOFF', plan['result_model']['review_result'])
        self.assertNotIn('C', plan['result_model']['review_result'])
        self.assertEqual(
            plan['result_model']['review_result'],
            ['PASS', 'FAIL', 'INSUFFICIENT', 'NA'])
        self.assertTrue(
            plan['aggregate_release_gate'][
                'evaluate_after_per_check_review'])
        self.assertEqual(
            len({item['id'] for item in plan['checks']}),
            len(plan['checks']))
        history = next(item for item in plan['rule_plan']
                       if item['rule'] == 'REQ-H01')
        self.assertEqual(history['applicability'], 'NOT_APPLICABLE')
        self.assertFalse(any(item['rule'] == 'PWR-T02' for item in plan['rule_plan']))

    def test_explicit_na_requires_intent_and_citation(self):
        intent = {
            'schema_version': 3,
            'features': {
                'DDR': {
                    'applicability': 'NOT_APPLICABLE',
                    'citation': 'Requirements v1 section 2',
                }
            },
        }
        self.assertEqual(validate_intent(intent), [])
        plan = build_review_plan(sample_db(), intent)
        item = get_feature(plan, 'DDR')
        self.assertEqual(item['applicability'], 'NOT_APPLICABLE')
        self.assertEqual(item['review_result'], 'NA')
        self.assertFalse(item['handoff']['required'])
        self.assertNotIn('DDR', undetected(plan)['object']['packages'])
        self.assertEqual([x['rule'] for x in plan['checks'] if x.get('package') == 'DDR'], ['REQ-Q07'])

    def test_required_but_missing_feature_creates_ready_presence_check(self):
        intent = {
            'schema_version': 3,
            'features': {
                'BLUETOOTH': {
                    'applicability': 'APPLICABLE',
                    'citation': 'Requirements v2 section 5',
                }
            },
        }
        plan = build_review_plan(sample_db(), intent)
        presence = next(item for item in plan['checks']
                        if item['rule'] == 'REQ-A02'
                        and item['object']['package'] == 'BLUETOOTH')
        self.assertEqual(presence['readiness'], 'READY')
        custom = get_feature(plan, 'BLUETOOTH')
        self.assertEqual(custom['applicability'], 'APPLICABLE')
        self.assertIn('自定义功能 BLUETOOTH', custom['criterion'])
        self.assertTrue(any(x['code'] == 'REQUIRED_FEATURE_NOT_DETECTED'
                            for x in plan['diagnostics']))

    def test_intent_netlist_conflict_is_not_na(self):
        intent = {
            'schema_version': 3,
            'features': {
                'USB': {
                    'applicability': 'NOT_APPLICABLE',
                    'citation': 'Requirements v2 section 7',
                }
            },
        }
        plan = build_review_plan(sample_db(), intent)
        self.assertEqual(get_feature(plan, 'USB')['applicability'],
                         'UNDETERMINED')
        self.assertTrue(any(x['code'] == 'INTENT_NETLIST_CONFLICT'
                            for x in plan['diagnostics']))

    def test_unbound_structured_evidence_does_not_make_hot_instance_ready(self):
        evidence = {
            'schema_version': 2,
            'checks': [{
                'id': 'U1-FB', 'rule': 'PWR-E01', 'kind': 'divider',
                'net': 'REG_FB', 'vref': 0.8,
                'expected': {'min': 2.9, 'max': 3.4},
                'citation': 'REG-X datasheet Rev.A p.10',
            }],
        }
        plan = build_review_plan(sample_db(), evidence=evidence)
        item = next(x for x in plan['checks']
                    if x['rule'] == 'PWR-E01')
        self.assertEqual(item['readiness'], 'WAITING_EVIDENCE')
        self.assertTrue(item['required_inputs'])

    def test_enable_net_does_not_turn_passive_pins_into_checks(self):
        db = sample_db()
        db['pinname'].update({'R3.1': '1', 'R3.2': '2'})
        checks = [item for item in build_review_plan(db)['checks']
                  if item['rule'] == 'RST-E01']
        self.assertEqual([item['object']['node'] for item in checks],
                         ['U1.2'])

    def test_intent_validation_rejects_unproven_na(self):
        errors = validate_intent({
            'schema_version': 3,
            'features': {'DDR': {'applicability': 'NOT_APPLICABLE'}},
        })
        self.assertTrue(any('citation' in error for error in errors))

    def test_spi_clock_does_not_create_i2c_pull_check(self):
        db = sample_db()
        db['nets'] = {'SCLK': ['U2.6', 'J1.6']}
        db['pin2net'] = {'U2.6': 'SCLK', 'J1.6': 'SCLK'}
        db['pinname'] = {'U2.6': 'SCLK', 'J1.6': 'SCLK'}
        db['pintype'] = {'U2.6': 'OUT', 'J1.6': 'IN'}
        plan = build_review_plan(db)
        self.assertEqual(get_feature(plan, 'SPI')['applicability'],
                         'APPLICABLE')
        self.assertIn('I2C', undetected(plan)['object']['packages'])
        self.assertFalse(any(item['rule'] == 'SIG-E01'
                             for item in plan['checks']))

    def test_revision_history_rule_waits_for_both_inputs(self):
        waiting = build_review_plan(sample_db(), review_mode='revision')
        history = next(item for item in waiting['rule_plan']
                       if item['rule'] == 'REQ-H01')
        self.assertEqual(history['applicability'], 'APPLICABLE')
        self.assertEqual(history['readiness'], 'WAITING_EVIDENCE')
        self.assertEqual(history['required_inputs'],
                         ['missing-old-db', 'missing-old-plan', 'old_db', 'review_claims'])

        # Availability booleans cannot stand in for actual revision inputs.
        flags_only = build_review_plan(sample_db(), review_mode='revision',
            old_db_available=True, claims_available=True)
        self.assertEqual(next(r for r in flags_only['rule_plan'] if r['rule'] == 'REQ-H01')['readiness'],
                         'WAITING_EVIDENCE')

        ready = build_review_plan(
            sample_db(), review_mode='revision',
            old_db=sample_db(), old_plan=build_review_plan(sample_db()), claims_available=True)
        history = next(item for item in ready['rule_plan']
                       if item['rule'] == 'REQ-H01')
        self.assertEqual(history['readiness'], 'READY')

    def test_datasheet_audit_controls_each_component_readiness(self):
        message = ('找不到这颗物料的 datasheet：SOC-X（位号：U2）。'
                   '请提供该物料的原厂 datasheet。')
        audit = {
            'schema_version': 1,
            'summary': {
                'required_materials': 2,
                'available': 1,
                'needs_verification': 0,
                'missing': 0,
                'not_found': 1,
                'unresolved': 1,
                'all_required_available': False,
            },
            'materials': [
                {
                    'material_id': 'DS-REG-X',
                    'identity': 'REG-X',
                    'refdes': ['U1'],
                    'status': 'AVAILABLE',
                    'document': {
                        'identity_verified': True,
                        'source_kind': 'package',
                        'path': 'REG-X.pdf',
                        'document_model': 'REG-X',
                        'document_version': 'Rev.A',
                    },
                },
                {
                    'material_id': 'DS-SOC-X',
                    'identity': 'SOC-X',
                    'refdes': ['U2'],
                    'status': 'NOT_FOUND',
                    'message': message,
                    'searched_sources': [
                        'LCSC query SOC-X',
                        'manufacturer official website query SOC-X',
                    ],
                    'searched_at': '2026-09-02',
                },
            ],
            'agent_requests': [{
                'id': 'REQUEST-SOC-X',
                'action': 'REQUEST_USER_DATASHEET',
                'identity': 'SOC-X',
                'refdes': ['U2'],
                'message': message,
            }],
            'user_messages': [message],
            'diagnostics': [],
        }
        plan = build_review_plan(sample_db(), datasheet_audit=audit)
        checks = {
            item['object']['ref']: item
            for item in plan['checks']
            if item['rule'] == 'DEV-D01'
        }
        self.assertEqual(checks['U1']['readiness'], 'READY')
        self.assertEqual(checks['U2']['readiness'], 'WAITING_EVIDENCE')
        self.assertEqual(checks['U2']['required_inputs'], ['datasheet:SOC-X'])
        self.assertEqual(plan['summary']['datasheet_unresolved'], 1)
        self.assertEqual(plan['datasheet_audit']['user_messages'], [message])
        self.assertTrue(any(item['code'] == 'DATASHEET_NOT_FOUND'
                            for item in plan['diagnostics']))


    def test_board_rules_are_planned_once_with_material_readiness(self):
        plan = build_review_plan(sample_db())
        board = [x for x in plan['checks'] if x['object'].get('board') == 'BOARD']
        expected = {r.id for r in catalog.rules(source='board')} | {'DOC-T01', 'REQ-Q08'}
        self.assertEqual(sorted(x['rule'] for x in board), sorted(expected))
        by_rule = {x['rule']: x for x in board}
        self.assertEqual(by_rule['DOC-D01']['readiness'], 'READY')
        self.assertEqual(by_rule['DOC-V02']['required_inputs'], ['schematic_pdf'])
        self.assertEqual(by_rule['DOC-D01']['id'], 'DOC-D01.BOARD')
        intent = {'schema_version': 3, 'materials': {
            key: {'available': True, 'citation': 'synthetic material'}
            for key in ('requirements', 'datasheets', 'platform_checklist', 'schematic_pdf')}}
        ready = build_review_plan(sample_db(), intent)
        self.assertTrue(all(x['readiness'] == 'READY' for x in ready['checks']
                            if x['rule'] in BOARD_MATERIALS))

    def test_devices_and_connectors_get_individual_disposition_checks(self):
        plan = build_review_plan(sample_db())
        refs = {}
        for item in plan['checks']:
            if item['rule'] in ('DEV-D01', 'DEV-D03', 'DEV-D05', 'DEV-C05', 'PRO-D03'):
                refs.setdefault(item['rule'], []).append(item['object']['ref'])
        self.assertEqual(refs['DEV-D01'], ['U1', 'U2'])
        self.assertEqual(refs['DEV-C05'], ['U1', 'U2'])
        self.assertEqual(refs['DEV-D05'], ['J1', 'U1', 'U2'])
        self.assertEqual(refs['DEV-D03'], ['J1'])
        self.assertEqual(refs['PRO-D03'], ['J1'])
        conditions = next(x for x in plan['checks'] if x['id'] == 'DEV-C05.U1')
        self.assertEqual(conditions['required_inputs'], ['datasheets', 'requirements'])

    def test_package_members_expand_per_circuit_or_once_per_package(self):
        plan = build_review_plan(sample_db())
        usb = sorted(x['rule'] for x in plan['checks']
                     if x.get('package') == 'USB' and x['rule'] != 'REQ-Q07')
        self.assertEqual(usb, sorted(catalog.package('USB').rules))
        self.assertTrue(all(x['id'] == x['rule'] + '.USB' for x in plan['checks']
                            if x.get('package') == 'USB' and x['rule'] != 'REQ-Q07'))
        summary = get_feature(plan, 'USB')
        self.assertEqual(summary['role'], 'coverage_parent')
        for rule in catalog.package('USB').rules:
            self.assertIn(rule, summary['criterion'])
        intent = {'schema_version': 3, 'circuits': [
            {'id': 'PORT', 'type': 'USB', 'refs': ['J1'], 'states': ['host', 'unpowered'],
             'citation': 'synthetic port definition'}]}
        self.assertEqual(validate_intent(intent), [])
        plan = build_review_plan(sample_db(), intent)
        members = [x for x in plan['checks'] if x.get('package') == 'USB' and x['rule'] != 'REQ-Q07']
        self.assertEqual(len(members), 2 * len(catalog.package('USB').rules))
        self.assertEqual({x['object']['state'] for x in members}, {'host', 'unpowered'})
        self.assertIn('intent.circuits:synthetic port definition', get_feature(plan, 'USB')['trigger'])

    def test_declared_circuit_makes_package_applicable_and_conflicts_with_na(self):
        circuit = {'id': 'LDO', 'type': 'POWER_PROTECTION', 'refs': ['U1'], 'states': ['run'],
                   'citation': 'synthetic protection'}
        plan = build_review_plan(sample_db(), {'schema_version': 3, 'circuits': [circuit]})
        self.assertEqual(get_feature(plan, 'POWER_PROTECTION')['applicability'], 'APPLICABLE')
        intent = {'schema_version': 3, 'circuits': [circuit], 'features': {
            'POWER_PROTECTION': {'applicability': 'NOT_APPLICABLE', 'citation': 'synthetic'}}}
        plan = build_review_plan(sample_db(), intent)
        self.assertEqual(get_feature(plan, 'POWER_PROTECTION')['applicability'], 'UNDETERMINED')
        self.assertFalse([x for x in plan['checks'] if x.get('package') == 'POWER_PROTECTION'
                          and x['rule'] != 'REQ-Q07'])
        self.assertTrue(any(x['code'] == 'INTENT_NETLIST_CONFLICT' for x in plan['diagnostics']))

    def test_renamed_packages_and_unknown_circuit_types_are_rejected(self):
        errors = validate_intent({'schema_version': 3, 'features': {
            'RESET': {'applicability': 'APPLICABLE', 'citation': 'old name'}}})
        self.assertTrue(any('已改名为 STARTUP' in error for error in errors))
        errors = validate_intent({'schema_version': 3, 'circuits': [
            {'id': 'C1', 'type': 'USB_C', 'refs': ['J1'], 'states': ['run'], 'citation': 'old type'}]})
        self.assertTrue(any('已改名为 USB' in error for error in errors))
        self.assertTrue(validate_intent({'schema_version': 2}))

if __name__ == '__main__':
    unittest.main()

import pathlib
import sys
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import catalog
from board_intent import input_fingerprint
from plan_review import BOARD_MATERIALS, OWNED_PART_MATERIALS, SYSTEM_MATERIALS, build_review_plan, validate_intent


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


def threshold_db():
    """辅助绕组齐纳经电阻到 FAULT、NTC 接控制器 RT 脚、浪涌 NTC 只在功率路径、普通二极管。"""
    pins = {
        'D1': [('1', 'K', 'AUX'), ('2', 'A', 'D1_A')],
        'R1': [('1', '1', 'D1_A'), ('2', '2', 'FAULT')],
        'U1': [('1', 'FAULT', 'FAULT'), ('2', 'GND', 'PGND'), ('3', 'VCC', 'AUX')],
        'TH1': [('1', '1', 'TEMP'), ('2', '2', 'SGND')],
        'U2': [('1', 'RT', 'TEMP'), ('2', 'GND', 'SGND')],
        'TH2': [('1', '1', 'AC_L'), ('2', '2', 'AC_L_F')],
        'D2': [('1', 'A', 'AC_L_F'), ('2', 'K', 'AUX')],
    }
    parts = {'D1': ('BZT52H-B68', 'Device:D_Zener'), 'R1': ('1k', 'Device:R'),
             'U1': ('CTRL-A', 'Lib:CTRL-A'), 'U2': ('CTRL-B', 'Lib:CTRL-B'),
             'TH1': ('100k/B4250', 'Device:Thermistor_NTC'), 'TH2': ('5R/3A', 'Device:Thermistor_NTC'),
             'D2': ('US1M', 'Device:D')}
    db = {'nets': {}, 'pin2net': {}, 'pinname': {}, 'pintype': {}, 'pseudo_nets': [],
          'parts': {ref: {'part': v, 'value': v, 'prim': prim, 'jedec': '', 'nc': False}
                    for ref, (v, prim) in parts.items()}}
    for ref, rows in pins.items():
        for pin, name, net in rows:
            node = ref + '.' + pin
            db['nets'].setdefault(net, []).append(node)
            db['pin2net'][node] = net
            db['pinname'][node] = name
    db['ref2page'] = {ref: 1 for ref in parts}
    return db


def get_feature(plan, name):
    return next(item for item in plan['checks']
                if item['rule'] == 'REQ-Q07' and item['object'].get('circuit_type') == name)


def undetected(plan):
    return next(item for item in plan['checks'] if item['rule'] == 'REQ-Q08')


class ReviewPlanTests(unittest.TestCase):
    def test_first_pass_discovers_instances_without_inventing_na(self):
        plan = build_review_plan(sample_db())
        confirm = undetected(plan)
        self.assertIn('DDR', confirm['object']['circuit_types'])
        self.assertIn('intent.features.DDR', confirm['required_inputs'])
        self.assertEqual(confirm['applicability'], 'APPLICABLE')
        self.assertIsNone(confirm['review_result'])
        self.assertFalse(any(item['object'].get('circuit_type') == 'DDR' for item in plan['checks']))
        self.assertEqual(get_feature(plan, 'USB')['applicability'],
                         'UNDETERMINED')
        pair = next(item for item in plan['checks']
                    if item['rule'] == 'SIG-T01')
        self.assertFalse(pair['handoff']['required'])  # generic layout rules are not review output
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

    def test_name_hint_does_not_expand_package_members(self):
        plan = build_review_plan(sample_db())
        summary = get_feature(plan, 'USB')
        self.assertEqual(summary['applicability'], 'UNDETERMINED')
        self.assertIn('intent.features.USB', summary['required_inputs'])
        self.assertTrue(any(t.startswith('netlist:') for t in summary['trigger']))
        self.assertFalse([x for x in plan['checks'] if x.get('circuit_type') == 'USB'
                          and x['rule'] != 'REQ-Q07'])

    def test_cited_na_excludes_name_hint_without_inventing_conflict(self):
        intent = {'features': {'USB': {
            'applicability': 'NOT_APPLICABLE',
            'citation': 'synthetic mode map: named pins serve charging detection only'}}}
        plan = build_review_plan(sample_db(), intent)
        # the declaration is the REQ-Q08 row's basis, not a row of its own (R6 fix list B3)
        self.assertFalse([x for x in plan['checks'] if x.get('circuit_type') == 'USB'])
        self.assertFalse(any(x['code'] == 'INTENT_NETLIST_CONFLICT'
                             for x in plan['diagnostics']))
        summary = undetected(plan)
        self.assertIn('已声明不适用（features）的：USB', summary['criterion'])
        self.assertNotIn('intent.features.USB', summary['required_inputs'])
        self.assertIn('intent:synthetic mode map: named pins serve charging detection only', summary['trigger'])

    def test_explicit_na_requires_intent_and_citation(self):
        intent = {
            'schema_version': 5,
            'features': {
                'DDR': {
                    'applicability': 'NOT_APPLICABLE',
                    'citation': 'Requirements v1 section 2',
                }
            },
        }
        self.assertEqual(validate_intent(intent), [])
        plan = build_review_plan(sample_db(), intent)
        self.assertEqual([x['rule'] for x in plan['checks'] if x.get('circuit_type') == 'DDR'], [])
        summary = undetected(plan)
        self.assertIn('DDR', summary['object']['circuit_types'])          # still undetected, now with its declaration
        self.assertIn('已声明不适用（features）的：DDR', summary['criterion'])
        self.assertNotIn('intent.features.DDR', summary['required_inputs'])
        self.assertIn('intent:Requirements v1 section 2', summary['trigger'])

    def test_required_but_missing_feature_creates_ready_presence_check(self):
        intent = {
            'schema_version': 5,
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
                        and item['object']['circuit_type'] == 'BLUETOOTH')
        self.assertEqual(presence['readiness'], 'READY')
        custom = get_feature(plan, 'BLUETOOTH')
        self.assertEqual(custom['applicability'], 'APPLICABLE')
        self.assertIn('自定义功能 BLUETOOTH', custom['criterion'])
        self.assertTrue(any(x['code'] == 'REQUIRED_FEATURE_NOT_DETECTED'
                            for x in plan['diagnostics']))

    def test_intent_netlist_conflict_is_not_na(self):
        intent = {
            'schema_version': 5,
            'circuits': [{'id': 'PORT', 'type': 'USB', 'refs': ['U2', 'J1'],
                          'states': ['run'], 'citation': 'synthetic confirmed USB port'}],
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

    def test_enable_net_does_not_turn_passive_pins_into_checks(self):
        db = sample_db()
        db['pinname'].update({'R3.1': '1', 'R3.2': '2'})
        checks = [item for item in build_review_plan(db)['checks']
                  if item['rule'] == 'RST-E01']
        self.assertEqual([item['object']['node'] for item in checks],
                         ['U1.2'])

    def test_a_requirement_interpretation_is_not_the_requirement_text(self):
        # 2026-10-21: one reviewer copied all 19 requirement texts into criterion and then passed cost and size
        # targets; the other wrote what the schematic can be judged on and marked those NA with the text cited.
        text = '按 1 万台估算，整机物料目标 60 元/台；不含税、线缆、组装和认证。'
        from test_requirement_source import doc_for
        req = {'id': 'REQ-COST-001', 'status': 'CONFIRMED', 'categories': ['OPTIMIZATION'],
               'interpretation': '按1万台估算，整机物料目标60元/台；不含税、线缆、组装和认证'}
        src = doc_for({'REQ-COST-001': text})
        errors = validate_intent({'schema_version': 5, 'requirement_source': src, 'requirements': [req]})
        self.assertTrue(any('REQ-COST-001.interpretation 抄了需求原文' in e for e in errors), errors)
        req['interpretation'] = '成本目标由整机 BOM 报价核算，原理图没有判据'
        self.assertFalse(any('抄了需求原文' in e for e in validate_intent(
            {'schema_version': 5, 'requirement_source': src, 'requirements': [req]})))

    def test_intent_validation_rejects_unproven_na(self):
        errors = validate_intent({
            'schema_version': 5,
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
                         'UNDETERMINED')
        self.assertIn('I2C', undetected(plan)['object']['circuit_types'])
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
        # with no circuit every part is unowned: stress and precision are asked once for the board (no capacitor here)
        expected = {r.id for r in catalog.rules(source='board')} | {'DOC-T01', 'REQ-Q08', 'DEV-C01', 'DEV-C03'}
        self.assertEqual(sorted(x['rule'] for x in board), sorted(expected))
        by_rule = {x['rule']: x for x in board}
        self.assertEqual(by_rule['DOC-D01']['readiness'], 'READY')
        self.assertEqual(by_rule['DOC-V02']['required_inputs'], ['schematic_pdf'])
        self.assertEqual(by_rule['DOC-D01']['id'], 'DOC-D01.BOARD')
        intent = {'schema_version': 5, 'materials': {
            key: {'path': str(pathlib.Path(__file__).resolve())}
            for key in ('requirements', 'datasheets', 'platform_checklist', 'schematic_pdf')}}
        ready = build_review_plan(sample_db(), intent)
        self.assertTrue(all(x['readiness'] == 'READY' for x in ready['checks']
                            if x['rule'] in {**BOARD_MATERIALS, **OWNED_PART_MATERIALS, **SYSTEM_MATERIALS}))

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

    def test_threshold_protection_expands_both_window_sides(self):
        checks = {x['id']: x for x in build_review_plan(threshold_db())['checks'] if x['rule'] == 'PRO-C02'}
        self.assertEqual(sorted(checks), ['PRO-C02.NOTRIP.D1', 'PRO-C02.NOTRIP.U1-1',
                                          'PRO-C02.TRIP.D1', 'PRO-C02.TRIP.U1-1'])
        self.assertIn('不误动作侧', checks['PRO-C02.NOTRIP.D1']['criterion'])
        self.assertIn('峰值整流', checks['PRO-C02.NOTRIP.D1']['criterion'])
        self.assertIn('动作有效侧', checks['PRO-C02.TRIP.U1-1']['criterion'])
        self.assertEqual(checks['PRO-C02.TRIP.D1']['method'], 'C')
        self.assertIn('requirements', checks['PRO-C02.TRIP.D1']['required_inputs'])

    def test_gate_source_zener_may_clamp_in_normal_drive(self):
        # 真实反例：功率管的栅源稳压管正常驱动中允许限幅，不能要求永不导通。
        db = threshold_db()
        for ref, value, rows in (('Q9', 'NMOS', [('1', 'G', 'G9'), ('2', 'D', 'D9N'), ('3', 'S', 'S9')]),
                                 ('D9', 'MMSZ5248B', [('1', 'K', 'G9'), ('2', 'A', 'S9')])):
            db['parts'][ref] = {'part': value, 'value': value, 'prim': 'X', 'jedec': '', 'nc': False}
            db['ref2page'][ref] = 1
            for pin, name, net in rows:
                db['nets'].setdefault(net, []).append(ref + '.' + pin)
                db['pin2net'][ref + '.' + pin] = net
                db['pinname'][ref + '.' + pin] = name
        checks = {x['id']: x for x in build_review_plan(db)['checks'] if x['rule'] == 'PRO-C02'}
        self.assertIn('允许钳位', checks['PRO-C02.NOTRIP.D9']['criterion'])
        self.assertIn('gate-source-clamp:Q9', checks['PRO-C02.NOTRIP.D9']['trigger'])
        self.assertNotIn('允许钳位', checks['PRO-C02.NOTRIP.D1']['criterion'])
        self.assertIn('内部钳位', checks['PRO-C02.NOTRIP.U1-1']['criterion'])

    def test_a_follower_gate_bias_zener_gets_no_threshold_rows(self):
        # R7 acceptance 2026-10-25 (claude1 feedback): D404 holds Q401's gate for a source follower; it conducts by design.
        db = threshold_db()
        for ref, value, rows in (('Q9', 'NMOS', [('1', 'G', 'G9'), ('2', 'D', 'D9N'), ('3', 'S', 'S9')]),
                                 ('D9', 'BZT52H-B16', [('1', 'K', 'G9'), ('2', 'A', 'GND')]),
                                 ('R9', '100k', [('1', '1', 'D9N'), ('2', '2', 'G9')])):
            db['parts'][ref] = {'part': value, 'value': value, 'prim': 'X', 'jedec': '', 'nc': False}
            db['ref2page'][ref] = 1
            for pin, name, net in rows:
                db['nets'].setdefault(net, []).append(ref + '.' + pin)
                db['pin2net'][ref + '.' + pin] = net
                db['pinname'][ref + '.' + pin] = name
        plan = build_review_plan(db)
        self.assertFalse([x['id'] for x in plan['checks'] if x['rule'] == 'PRO-C02' and x['object'].get('ref') == 'D9'])
        self.assertIn({'ref': 'D9', 'switch': 'Q9'}, [{'ref': d['ref'], 'switch': d['switch']} for d in plan['diagnostics']
                                                      if d['code'] == 'GATE_BIAS_ZENER'])

    def test_sensor_rail_end_and_ic_supply_pins_are_not_sensing_inputs(self):
        # rf1 公开板：NTC 上端接 3V3 轨，轨上各 IC 的 VDD 脚曾各生成一条 ANA-C04。
        db = threshold_db()
        for node, net, name in (('TH1.2', 'V3V3', '2'), ('U2.3', 'V3V3', 'VDD'), ('U4.1', 'V3V3', 'VCC'),
                                ('U4.2', 'SGND', 'GND'), ('U9.1', 'V3V3', 'VO'), ('U9.2', 'SGND', 'GND')):
            old = db['pin2net'].get(node)
            if old:
                db['nets'][old].remove(node)
            db['nets'].setdefault(net, []).append(node); db['pin2net'][node] = net; db['pinname'][node] = name
        for ref, value in (('U4', 'ADC'), ('U9', 'LDO')):
            db['parts'][ref] = {'part': value, 'value': value, 'prim': 'X', 'jedec': '', 'nc': False}
            db['ref2page'][ref] = 1
        db['native_pintype'] = {'U2.3': 'power_in', 'U4.1': 'power_in', 'U9.1': 'power_out'}
        rows = [x['object']['node'] for x in build_review_plan(db)['checks'] if x['rule'] == 'ANA-C04']
        self.assertEqual(rows, ['U2.1'])

    def test_current_sense_pair_is_not_a_differential_link(self):
        # 真实反例：CS_P/CS_N 是电流采样对，不套差分数据链路规则。
        from plan_review import _differential_pairs
        db = {'nets': {'CS_P': [], 'CS_N': [], 'TX_P': [], 'TX_N': [], 'ISENSE+': [], 'ISENSE-': []}}
        self.assertEqual(_differential_pairs(db), [('TX_P', 'TX_N')])

    def test_regulator_without_u_prefix_is_found_by_native_power_pins(self):
        # rf1 公开板：Reg1/Reg2/Reg3（LM317M、MCP1703）曾因位号不是 U 而没有 DEV-D01/DEV-C05。
        db = threshold_db()
        for pin, name, net, kind in (('1', 'GND', 'PGND', 'power_in'), ('2', 'VO', 'V3V3', 'power_out'),
                                     ('3', 'VI', 'AUX', 'power_in')):
            node = 'Reg1.' + pin
            db['nets'].setdefault(net, []).append(node); db['pin2net'][node] = net; db['pinname'][node] = name
            db.setdefault('native_pintype', {})[node] = kind
        db['parts']['Reg1'] = {'part': 'MCP1703', 'value': 'MCP1703', 'prim': 'X', 'jedec': '', 'nc': False}
        db['ref2page']['Reg1'] = 1
        checks = build_review_plan(db)['checks']
        identity = next(x for x in checks if x['rule'] == 'DEV-D01' and x['object']['ref'] == 'Reg1')
        self.assertIn('native-power-pins:active-device', identity['trigger'])
        self.assertTrue(any(x['rule'] == 'DEV-C05' and x['object']['ref'] == 'Reg1' for x in checks))

    def test_connector_signal_esd_folds_into_connector_protection(self):
        db = threshold_db()
        extra = {'J1': [('1', '1', 'USB_DP'), ('2', '2', 'VBUS'), ('3', '3', 'PGND')],
                 'D3': [('1', 'K', 'USB_DP'), ('2', 'A', 'PGND')],
                 'D4': [('1', 'K', 'VBUS'), ('2', 'A', 'PGND')],
                 'D5': [('1', 'K', 'INT_SIG'), ('2', 'A', 'PGND')],
                 'U3': [('1', 'IO', 'INT_SIG'), ('2', 'GND', 'PGND')]}
        for ref, value in (('J1', 'USB_C'), ('D3', 'PESD5V0'), ('D4', 'SMAJ5.0A'),
                           ('D5', 'PESD5V0'), ('U3', 'MCU')):
            db['parts'][ref] = {'part': value, 'value': value, 'prim': 'X', 'jedec': '', 'nc': False}
            db['ref2page'][ref] = 1
        for ref, rows in extra.items():
            for pin, name, net in rows:
                db['nets'].setdefault(net, []).append(ref + '.' + pin)
                db['pin2net'][ref + '.' + pin] = net
                db['pinname'][ref + '.' + pin] = name
        checks = build_review_plan(db)['checks']
        refs = sorted({x['object']['ref'] for x in checks if x['rule'] == 'PRO-C02'})
        # 2026-10-26（方案 B）：跨网与地的防护钳位（信号线 D3、电源轨 D4、板内 IO 的 D5）只出 PRO-E02；
        # 串在门限链里的齐纳 D1 与门限脚 U1 仍是 PRO-C02 两侧窗口。
        self.assertEqual(refs, ['D1', 'U1'])
        connector = next(x for x in checks if x['rule'] == 'PRO-D03' and x['object']['ref'] == 'J1')
        self.assertNotIn('clamp_refs', connector)   # 2026-10-26: the connector row asks topology only
        from lint import Lint
        self.assertEqual(sorted(x['ref'] for x in Lint(db).run() if x['rule'] == 'PRO-E02'), ['D3', 'D4', 'D5'])

    def test_sensor_discrimination_is_planned_per_controller_pin(self):
        checks = [x for x in build_review_plan(threshold_db())['checks'] if x['rule'] == 'ANA-C04']
        # 浪涌 NTC 不接 IC 脚，地侧的 U2.GND 也不成项。
        self.assertEqual([x['id'] for x in checks], ['ANA-C04.TH1.U2-1'])
        self.assertEqual(checks[0]['object'], {'ref': 'TH1', 'node': 'U2.1', 'net': 'TEMP'})
        self.assertIn('偏置电流档', checks[0]['criterion'])
        self.assertEqual(checks[0]['readiness'], 'WAITING_EVIDENCE')

    def test_subjects_expand_per_circuit_or_once_per_circuit_type(self):
        plan = build_review_plan(sample_db(), {'features': {
            'USB': {'applicability': 'APPLICABLE', 'citation': 'synthetic USB function'}}})
        usb = sorted(x['rule'] for x in plan['checks']
                     if x.get('circuit_type') == 'USB' and x['rule'] != 'REQ-Q07')
        self.assertEqual(usb, sorted(catalog.circuit_type('USB').subjects))
        self.assertTrue(all(x['id'] == x['rule'] + '.USB' for x in plan['checks']
                            if x.get('circuit_type') == 'USB' and x['rule'] != 'REQ-Q07'))
        summary = get_feature(plan, 'USB')
        self.assertEqual(summary['role'], 'coverage_parent')
        for rule in catalog.circuit_type('USB').subjects:
            self.assertIn(rule, summary['criterion'])
        intent = {'schema_version': 5, 'circuits': [
            {'id': 'PORT', 'type': 'USB', 'refs': ['J1'], 'states': ['host', 'unpowered'],
             'citation': 'synthetic port definition'}]}
        self.assertEqual(validate_intent(intent), [])
        plan = build_review_plan(sample_db(), intent)
        members = [x for x in plan['checks'] if x.get('circuit_type') == 'USB' and x['rule'] != 'REQ-Q07']
        # SIG-T04/SIG-D07/SIG-D04 与工作态无关，每电路一行；其余电路检查项两个状态各一行。
        invariant = [r for r in catalog.circuit_type('USB').subjects if r in catalog.STATE_INVARIANT]
        self.assertEqual(len(members), 2 * (len(catalog.circuit_type('USB').subjects) - len(invariant)) + len(invariant))
        self.assertEqual({x['object']['state'] for x in members if x['rule'] not in invariant}, {'host', 'unpowered'})
        self.assertFalse([x for x in members if x['rule'] in invariant and 'state' in x['object']])
        self.assertIn('intent.circuits:synthetic port definition', get_feature(plan, 'USB')['trigger'])

    def test_level_shift_name_hit_is_candidate_until_circuit_is_declared(self):
        db = sample_db()
        db['parts']['U3'] = {'part': 'TXS0102DCUR', 'value': 'TXS0102', 'prim': 'TXS0102',
                             'jedec': 'VSSOP', 'nc': False}
        db['nets']['GPIO_LV'] = ['U2.6', 'U3.1']
        db['pin2net'].update({'U2.6': 'GPIO_LV', 'U3.1': 'GPIO_LV'})
        plan = build_review_plan(db)
        self.assertEqual(get_feature(plan, 'LEVEL_SHIFT')['applicability'], 'UNDETERMINED')
        self.assertFalse([x for x in plan['checks'] if x.get('circuit_type') == 'LEVEL_SHIFT'
                          and x['rule'] != 'REQ-Q07'])
        intent = {'schema_version': 5, 'circuits': [
            {'id': 'GPIO-XLAT', 'type': 'LEVEL_SHIFT', 'refs': ['U2', 'U3'],
             'states': ['both-powered', 'b-side-unpowered'], 'citation': 'synthetic translator link'}]}
        self.assertEqual(validate_intent(intent), [])
        plan = build_review_plan(db, intent)
        members = [x for x in plan['checks'] if x.get('circuit_type') == 'LEVEL_SHIFT' and x['rule'] != 'REQ-Q07']
        self.assertEqual(sorted({x['rule'] for x in members}), sorted(catalog.circuit_type('LEVEL_SHIFT').subjects))
        # SIG-T04（接口方向语义）与工作态无关，两个状态只问一次。
        self.assertEqual(len(members), 2 * len(catalog.circuit_type('LEVEL_SHIFT').subjects) - 1)

    def test_declared_circuit_makes_package_applicable_and_conflicts_with_na(self):
        circuit = {'id': 'LDO', 'type': 'POWER_PROTECTION', 'refs': ['U1'], 'states': ['run'],
                   'citation': 'synthetic protection'}
        plan = build_review_plan(sample_db(), {'schema_version': 5, 'circuits': [circuit]})
        self.assertEqual(get_feature(plan, 'POWER_PROTECTION')['applicability'], 'APPLICABLE')
        intent = {'schema_version': 5, 'circuits': [circuit], 'features': {
            'POWER_PROTECTION': {'applicability': 'NOT_APPLICABLE', 'citation': 'synthetic'}}}
        plan = build_review_plan(sample_db(), intent)
        self.assertEqual(get_feature(plan, 'POWER_PROTECTION')['applicability'], 'UNDETERMINED')
        self.assertFalse([x for x in plan['checks'] if x.get('circuit_type') == 'POWER_PROTECTION'
                          and x['rule'] != 'REQ-Q07'])
        self.assertTrue(any(x['code'] == 'INTENT_NETLIST_CONFLICT' for x in plan['diagnostics']))

    def test_unknown_circuit_type_names_are_rejected(self):
        errors = validate_intent({'schema_version': 5, 'features': {
            'RESET': {'applicability': 'APPLICABLE', 'citation': 'not a package'}}})
        self.assertTrue(any('不是功能电路名' in error for error in errors))
        errors = validate_intent({'schema_version': 5, 'circuits': [
            {'id': 'C1', 'type': 'USB_C', 'refs': ['J1'], 'states': ['run'], 'citation': 'not a package'}]})
        self.assertTrue(any('circuits.type 不支持' in error for error in errors))
        self.assertTrue(validate_intent({'schema_version': 2}))

    def test_declared_assemblies_and_pin_tables_feed_board_and_device_checks(self):
        db = sample_db()
        intent = {
            'schema_version': 5, 'input_sha256': input_fingerprint(db),
            'assemblies': [{'id': 'base', 'citation': 'BOM rev.B option table', 'population': {}},
                           {'id': 'no-usb', 'citation': 'BOM rev.B option table', 'population': {'J1': False}}],
            'devices': {
                'U1': {'mpn': 'REG-X-1', 'package': 'QFN-6', 'identity_citation': 'BOM row U1',
                       'citation': 'REG-X datasheet Rev.A table 1', 'pinout_complete': True,
                       'pins': {'1': {'name': 'FB', 'role': 'other'}, '2': {'name': 'EN', 'role': 'other'},
                                '3': {'name': 'GND', 'role': 'return'}, '4': {'name': 'VIN', 'role': 'power'},
                                '5': {'name': 'VOUT', 'role': 'power'}, '6': {'name': 'NC', 'role': 'nc'}}},
                'U2': {'mpn': 'SOC-X-1', 'package': 'BGA', 'identity_citation': 'BOM row U2',
                       'citation': 'SOC-X datasheet Rev.B partial table', 'pinout_complete': False,
                       'pins': {'1': {'name': 'BOOT0', 'role': 'nc'}}}},
            # an integrated circuit's role is a datasheet-verified kind like a discrete's type
            'device_kinds': {'U1': {'kind': 'regulator', 'page': 1, 'quote': 'Low Dropout Voltage Regulator'},
                             'U2': {'kind': 'mcu', 'page': 1, 'quote': '32-bit Microcontroller'}}}
        self.assertEqual(validate_intent(intent, db), [])
        audit = {'device_kinds': {ref: dict(item, status='VERIFIED', document='synthetic.pdf', document_sha256='a' * 64)
                                  for ref, item in intent['device_kinds'].items()}}
        plan = build_review_plan(db, intent, datasheet_audit=audit)
        self.assertEqual(sorted(x['id'] for x in plan['checks'] if x['rule'] == 'DOC-T01'),
                         ['DOC-T01.BASE', 'DOC-T01.NO-USB'])
        complete = next(x for x in plan['checks'] if x['id'] == 'DEV-D02.U1')
        self.assertEqual(complete['readiness'], 'READY')
        # the QFN-6 table is complete (the guard needs pins 1..6); the symbol draws only 1, 2 and 5
        self.assertEqual(complete['pin_difference'], {'official_only': ['U1.3', 'U1.4', 'U1.6'], 'symbol_only': []})
        self.assertEqual(next(x for x in plan['checks'] if x['id'] == 'DEV-D05.U1')['pin_disposition'],
                         {'unconnected': ['U1.3', 'U1.4', 'U1.6'], 'nc_connected': []})
        partial = next(x for x in plan['checks'] if x['id'] == 'DEV-D02.U2')
        self.assertEqual(partial['readiness'], 'WAITING_EVIDENCE')
        self.assertEqual(partial['required_inputs'],
                         ['intent.devices.U2: official full pinout + exact MPN/package'])
        self.assertEqual(partial['pin_difference']['symbol_only'], ['U2.2', 'U2.3', 'U2.4', 'U2.5'])
        self.assertEqual(next(x for x in plan['checks'] if x['id'] == 'DEV-D05.U2')['pin_disposition'],
                         {'unconnected': [], 'nc_connected': ['U2.1']})
        undeclared = next(x for x in plan['checks'] if x['id'] == 'DEV-D02.J1')
        self.assertEqual(undeclared['required_inputs'],
                         ['intent.devices.J1: official full pinout + exact MPN/package'])
        self.assertNotIn('pin_difference', undeclared)

    def test_two_terminal_diode_on_two_terminal_package_needs_no_pinout(self):
        def plan_with(ref, jedec, pins):
            db = sample_db()
            db['parts'][ref] = {'part': 'Green', 'value': 'Green', 'prim': 'Lib:LED', 'jedec': jedec, 'nc': False}
            for pin, name, net in pins:
                db['nets'].setdefault(net, []).append(f'{ref}.{pin}')
                db['pin2net'][f'{ref}.{pin}'] = net
                db['pinname'][f'{ref}.{pin}'] = name
            plan = build_review_plan(db, {'schema_version': 5, 'input_sha256': input_fingerprint(db)})
            return next(x for x in plan['checks'] if x['id'] == f'DEV-D02.{ref}')
        led = plan_with('D1', 'e-radionica.com footprinti:0402LED', [('1', 'A', 'VCC_3V3'), ('2', 'K', 'GND')])
        self.assertEqual(led['readiness'], 'READY')
        self.assertEqual(led['required_inputs'], [])
        self.assertIn('PCB-stage HANDOFF', led['pin_difference']['basis'])
        dotted = plan_with('D8', 'Diode_SMD:D_SMA', [('1.1', 'A', 'VCC_3V3'), ('1.2', 'K', 'GND')])
        self.assertEqual(dotted['readiness'], 'READY')
        self.assertEqual(dotted['required_inputs'], [])
        bidirectional = plan_with('D3', 'Diode_SMD:D_SMA', [('1', 'A1', 'VCC_3V3'), ('2', 'A2', 'GND')])
        self.assertEqual(bidirectional['readiness'], 'READY')
        self.assertIn('non-polar', bidirectional['pin_difference']['basis'])
        for ref, jedec, pins in (
                ('J7', 'TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2_1x02_P5.00mm_Horizontal',
                 [('1', 'Pin_1', 'VCC_3V3'), ('2', 'Pin_2', 'GND')]),
                ('J8', 'Connector_PinHeader_2.54mm:PinHeader_1x01_P2.54mm_Vertical', [('1', 'Pin_1', 'GND')])):
            with self.subTest(ref=ref):
                row = plan_with(ref, jedec, pins)
                self.assertEqual((row['readiness'], row['required_inputs']), ('READY', []))
                self.assertIn('single-row connector', row['pin_difference']['basis'])
        for ref, jedec, pins in (
                ('D2', 'Package_TO_SOT_SMD:SOT-23', [('1', 'A', 'VCC_3V3'), ('2', 'K', 'GND'), ('3', 'NC', 'GND')]),
                ('D3', 'Diode_SMD:D_SMA', [('1', 'A1', 'VCC_3V3'), ('2', 'X', 'GND')]),
                ('J3', 'Connector_JST:JST_PH_B4B-PH-K_1x04_P2.00mm_Vertical',
                 [('1', 'Pin_1', 'VCC_3V3'), ('2', 'Pin_2', 'GND')]),
                ('J4', 'Connector_JST:JST_SH_SM02B-SRSS-TB_1x02-1MP_P1.00mm_Horizontal',
                 [('1', 'Pin_1', 'VCC_3V3'), ('2', 'Pin_2', 'GND')]),
                ('J5', 'Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical',
                 [('1', 'Pin_1', 'VCC_3V3'), ('3', 'Pin_3', 'GND')]),
                ('D4', 'Custom:WEIRD', [('1', 'A', 'VCC_3V3'), ('2', 'K', 'GND')]),
                ('D5', 'LED_SMD:LED_WS2812B_PLCC4_5.0x5.0mm_P3.2mm', [('1', 'A', 'VCC_3V3'), ('2', 'K', 'GND')]),
                ('D6', 'LED_SMD:LED_Cree-XHP50_6V', [('1', 'A', 'VCC_3V3'), ('2', 'K', 'GND')]),
                ('D7', 'LED_THT:LED_D5.0mm-4_RGB', [('1', 'A', 'VCC_3V3'), ('2', 'K', 'GND')]),
                ('J9', 'Connector_Coaxial:SMA_Amphenol_132134', [('1', '+', 'VCC_3V3'), ('2', '-', 'GND')])):
            with self.subTest(ref=ref):
                self.assertEqual(plan_with(ref, jedec, pins)['readiness'], 'WAITING_EVIDENCE')

    def test_shared_declarations_require_a_current_netlist_binding(self):
        db = sample_db()
        intent = {'schema_version': 5,
                  'assemblies': [{'id': 'base', 'citation': 'BOM rev.B', 'population': {}}]}
        self.assertTrue(any('input_sha256 is required' in error
                            for error in validate_intent(intent, db)))
        intent['input_sha256'] = '0' * 64
        self.assertIn('stale input_sha256', validate_intent(intent, db))
        self.assertEqual(next(x for x in build_review_plan(db)['checks']
                              if x['rule'] == 'DOC-T01')['required_inputs'], ['intent.assemblies'])


def circuit_frames(plan):
    """The plan's circuit frames; interface frames (function tree, step 4) carry `interface` instead."""
    return [f for f in plan['functions'] if f.get('circuit')]


class FunctionFrameTests(unittest.TestCase):
    """计划 schema 5：每个 intent 电路一个功能框架，检查行带问题、function_id 和方面。"""

    def circuit(self, nets=('VCC_3V3',)):
        return {'id': 'REG-3V3', 'type': 'POWER_CONVERTER', 'refs': ['U1', 'R1'], 'nets': list(nets),
                'states': ['cold', 'hot'], 'citation': 'synthetic regulator'}

    def test_a_declared_circuit_gets_a_frame_and_bound_member_rows(self):
        intent = {'schema_version': 5, 'circuits': [self.circuit()],
                  'power_rails': {'VCC_3V3': {'voltage_v': {'min': 3.2, 'max': 3.4}, 'refs': ['U1'],
                                              'citation': 'synthetic rail'}}}
        plan = build_review_plan(sample_db(), intent)
        self.assertEqual(plan['schema_version'], 7)
        self.assertEqual([f['id'] for f in circuit_frames(plan)], ['FN-REG-3V3'])
        frame = circuit_frames(plan)[0]
        rules = catalog.circuit_type('POWER_CONVERTER').subjects
        members = [c for c in plan['checks'] if c['object'].get('circuit') == 'REG-3V3' and c.get('circuit_type')]
        self.assertEqual(len(members), 2 * len(rules))
        # the frame holds the circuit rows and, since 2026-10-25, every applicable row the circuit owns (device rows of U1/R1)
        owned = [c for c in plan['checks'] if (c.get('owner') or {}).get('id') == 'REG-3V3'
                 and c.get('applicability') != 'NOT_APPLICABLE']
        self.assertTrue({c['id'] for c in members} <= {m['check_id'] for m in frame['members']})
        self.assertEqual({m['check_id'] for m in frame['members']}, {c['id'] for c in owned})
        self.assertGreater(len(owned), len(members))
        self.assertIn('VCC_3V3 3.2–3.4 V', frame['question'])
        self.assertEqual(set(frame['blind_spots']), {c['rule'] for c in owned})
        self.assertEqual(frame['checklist'], list(catalog.BOUNDING_STEPS))
        self.assertEqual(frame['objects'], {'refs': ['U1', 'R1'], 'nets': ['VCC_3V3']})
        for row in members:
            with self.subTest(row['id']):
                self.assertEqual(row['function_id'], 'FN-REG-3V3')
                self.assertEqual(row['aspect'], catalog.title(row['rule']))
                self.assertIn(row['object']['state'] + ' 时 REG-3V3（U1、R1）', row['question'])
                self.assertNotIn('closure_contract', row)
        window = next(c for c in members if c['rule'] == 'PWR-C02')
        self.assertIn('VCC_3V3 3.2–3.4 V', window['question'])
        self.assertEqual(catalog.question_errors(plan), [])

    def test_state_invariant_rules_get_one_row_per_circuit(self):
        # 导通方向、接口语义这类答案不随工作态变化的规则，两个状态只问一次；其余电路检查项仍逐状态。
        circuit = {'id': 'IN-PROT', 'type': 'POWER_PROTECTION', 'refs': ['D1', 'Q1'], 'nets': ['VIN'],
                   'states': ['run', 'surge'], 'citation': 'synthetic input protection'}
        plan = build_review_plan(sample_db(), {'schema_version': 5, 'circuits': [circuit]})
        rules = catalog.circuit_type('POWER_PROTECTION').subjects
        invariant = [r for r in rules if r in catalog.STATE_INVARIANT]
        self.assertEqual(invariant, ['PWR-T05'])
        members = [c for c in plan['checks'] if c['object'].get('circuit') == 'IN-PROT' and c.get('circuit_type')]
        self.assertEqual(len(members), 2 * (len(rules) - 1) + 1)
        once = [c for c in members if c['rule'] == 'PWR-T05']
        self.assertEqual([c['id'] for c in once], ['PWR-T05.IN-PROT.D1'])
        self.assertNotIn('state', once[0]['object'])
        self.assertEqual(once[0]['question'], 'IN-PROT（D1、Q1）防反接电路的导通方向、体二极管朝向与栅极钳位是否正确')
        frame = circuit_frames(plan)[0]
        self.assertEqual(frame['states'], ['run', 'surge'])
        self.assertEqual([m['state'] for m in frame['members'] if m['rule'] == 'PWR-T05'], [None])
        self.assertEqual(len(frame['members']), len(members))
        for row in members:
            if row['rule'] != 'PWR-T05':
                self.assertIn(row['object']['state'] + ' 时 IN-PROT（D1、Q1）', row['question'])

    def test_no_rail_window_is_said_so_and_no_circuit_means_no_frame(self):
        plan = build_review_plan(sample_db(), {'schema_version': 5, 'circuits': [self.circuit(nets=())]})
        row = next(c for c in plan['checks'] if c['rule'] == 'PWR-C02' and c['object'].get('circuit'))
        self.assertIn(catalog.NO_WINDOW, row['question'])
        self.assertIn(catalog.NO_WINDOW, circuit_frames(plan)[0]['question'])
        bare = build_review_plan(sample_db())
        self.assertEqual(circuit_frames(bare), [])
        self.assertTrue(all(f.get('interface_kind') == 'EXTERNAL' or f.get('system') for f in bare['functions']))


if __name__ == '__main__':
    unittest.main()

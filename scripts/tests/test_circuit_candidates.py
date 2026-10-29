"""Circuit candidates are generated from the netlist, the verified device kinds and the checker inventories.

A candidate is a type plus the anchor it is built around (a role IC, or a discrete switch nobody drives); its
members each carry the path the walk took (`via`), which is a membership relation, not an electrical
conduction claim. The walk passes two-terminal parts only and stops at rail stops, grounds, other anchors
and barrier parts. Pages and names never decide membership; a part two candidates reach at the same
distance is listed in both as shared. The board is the isolated flyback of test_domains plus a buck
regulator, a Type-C port with its PD controller and VBUS switch, an input protection chain and a test point.
"""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import board_intent
import catalog
import circuit_candidates as cc
import test_inductive_load as fixture


def board():
    db = {'nets': {}, 'parts': {}, 'pin2net': {}, 'pinname': {}, 'pintype': {}, 'pseudo_nets': [], 'ref2page': {}}
    add = fixture.add
    # input protection: connector, fuse, varistor, inrush NTC, bridge, bulk capacitor
    add(db, 'J1', 'Connector:AC_IN', [('1', 'L', 'AC_L'), ('2', 'N', 'AC_N')])
    add(db, 'F1', 'FUSE-2A', [('1', '1', 'AC_L'), ('2', '2', 'L_F')])
    add(db, 'RV1', 'Device:Varistor', [('1', '1', 'L_F'), ('2', '2', 'AC_N')])
    add(db, 'TH1', 'Device:Thermistor_NTC', [('1', '1', 'L_F'), ('2', '2', 'L_NTC')])
    add(db, 'BR1', 'BRIDGE', [('1', 'AC1', 'L_NTC'), ('2', 'AC2', 'AC_N'), ('3', '+', 'RECT'), ('4', '-', 'PGND')])
    add(db, 'C1', '82uF', [('1', '1', 'RECT'), ('2', '2', 'PGND')])
    # flyback: controller, switch, sense resistor, transformer, aux rectifier, secondary rectifier and output cap
    add(db, 'U1', 'PWM-CTRL', [('1', 'VCC', 'VCC'), ('2', 'GND', 'PGND'), ('3', 'DRV', 'DRV'),
                               ('4', 'FB', 'FB'), ('5', 'HV', 'HV_IN'), ('6', 'CS', 'CS'), ('7', 'FAULT', 'FLT')])
    add(db, 'R41', '1M', [('1', '1', 'RECT'), ('2', '2', 'HV_IN')])            # HV start-up resistor
    # fault chain: the PD controller's GPIO drives an optocoupler whose output pulls the controller's FAULT pin
    add(db, 'R43', '470R', [('1', '1', 'FLT_DRV'), ('2', '2', 'FLT_A')])
    add(db, 'U9', 'PC817', [('1', 'A', 'FLT_A'), ('2', 'K', 'SGND'), ('3', 'C', 'FLT_C'), ('4', 'E', 'PGND')])
    add(db, 'R42', '10K', [('1', '1', 'FLT_C'), ('2', '2', 'FLT')])
    add(db, 'C41', '100nF', [('1', '1', 'FLT'), ('2', '2', 'PGND')])
    add(db, 'R1', '10R', [('1', '1', 'DRV'), ('2', '2', 'GATE')])
    add(db, 'Q1', 'MOSFET-N', [('1', 'G', 'GATE'), ('2', 'D', 'SW'), ('3', 'S', 'CS')])
    add(db, 'R3', '100K', [('1', '1', 'GATE'), ('2', '2', 'CS')])
    add(db, 'R2', '0R33', [('1', '1', 'CS'), ('2', '2', 'PGND')])
    add(db, 'T1', 'XFMR', [('1', '1', 'RECT'), ('2', '2', 'SW'), ('3', '3', 'AUX'), ('4', '4', 'PGND'),
                           ('5', '5', 'SEC_SW'), ('6', '6', 'SGND')])
    add(db, 'D3', 'DIODE', [('1', 'A', 'AUX'), ('2', 'K', 'VCC')])
    add(db, 'C4', '22uF', [('1', '1', 'VCC'), ('2', '2', 'PGND')])
    add(db, 'D2', 'SCHOTTKY', [('1', 'A', 'SEC_SW'), ('2', 'K', 'VOUT')])
    add(db, 'C3', '470uF', [('1', '1', 'VOUT'), ('2', '2', 'SGND')])
    # feedback: shunt reference, optocoupler, Y capacitor
    add(db, 'U3', 'PC817', [('1', 'A', 'FB_LED'), ('2', 'K', 'SGND'), ('3', 'C', 'FB'), ('4', 'E', 'PGND')])
    add(db, 'R7', '1K', [('1', '1', 'VOUT'), ('2', '2', 'FB_LED')])
    add(db, 'U4', 'TL431', [('1', 'REF', 'FB_DIV'), ('2', 'A', 'SGND'), ('3', 'K', 'FB_LED')])
    add(db, 'R5', '47K', [('1', '1', 'VOUT'), ('2', '2', 'FB_DIV')])
    add(db, 'R6', '10K', [('1', '1', 'FB_DIV'), ('2', '2', 'SGND')])
    add(db, 'CY1', '2.2nF', [('1', '1', 'PGND'), ('2', '2', 'SGND')])
    # port: PD controller with current sense, VBUS switch, Type-C receptacle with ESD clamps
    add(db, 'U5', 'PD-CTRL', [('1', 'VBUS_IN', 'VOUT'), ('2', 'GND', 'SGND'), ('3', 'CC1', 'CC1'),
                              ('4', 'VOUT', 'V5'), ('5', 'GATE', 'PORT_G'), ('6', 'CS+', 'ISNS_P'), ('7', 'CS-', 'ISNS_N'),
                              ('8', 'GPIO1', 'FLT_DRV')])
    add(db, 'R8', '10R', [('1', '1', 'PORT_G'), ('2', '2', 'VBUS_G')])
    add(db, 'Q2', 'MOSFET-N', [('1', 'G', 'VBUS_G'), ('2', 'D', 'VOUT'), ('3', 'S', 'VBUS')])
    add(db, 'R14', '10m', [('1', '1', 'ISNS_P'), ('2', '2', 'VBUS')])
    add(db, 'R15', '100R', [('1', '1', 'ISNS_N'), ('2', '2', 'SGND')])
    add(db, 'C6', '1uF', [('1', '1', 'V5'), ('2', '2', 'SGND')])
    add(db, 'J2', 'Connector:USB_C_Receptacle_USB2.0', [('A5', 'CC1', 'CC1'), ('A6', 'D+', 'DP'), ('A7', 'D-', 'DN'),
                                                        ('A4', 'VBUS', 'VBUS'), ('A1', 'GND', 'SGND')])
    add(db, 'D5', 'ESD5V3', [('1', '1', 'DP'), ('2', '2', 'SGND')])
    add(db, 'D6', 'ESD5V3', [('1', '1', 'DN'), ('2', '2', 'SGND')])
    add(db, 'C7', '10uF', [('1', '1', 'VBUS'), ('2', '2', 'SGND')])
    # buck regulator with integrated switch on the secondary
    add(db, 'U7', 'BUCK-3A', [('1', 'VIN', 'VOUT'), ('2', 'SW', 'BUCK_SW'), ('3', 'GND', 'SGND'), ('4', 'FB', 'BUCK_FB')])
    add(db, 'L2', 'IND-4U7', [('1', '1', 'BUCK_SW'), ('2', '2', 'V3V3')])
    add(db, 'C10', '22uF', [('1', '1', 'V3V3'), ('2', '2', 'SGND')])
    add(db, 'R11', '100K', [('1', '1', 'V3V3'), ('2', '2', 'BUCK_FB')])
    add(db, 'R12', '22K', [('1', '1', 'BUCK_FB'), ('2', '2', 'SGND')])
    # a test point and a bleeder nobody's walk reaches
    db['parts']['TP1'] = {'part': 'PCB test pad', 'value': 'V5', 'prim': 'Connector:TestPoint', 'jedec': '', 'nc': False}
    db['nets']['V5'].append('TP1.1'); db['pin2net']['TP1.1'] = 'V5'; db['pinname']['TP1.1'] = '1'
    add(db, 'R99', '10K', [('1', '1', 'V5'), ('2', '2', 'SGND')])
    db['pintype'].update({'U1.3': 'OUT', 'U5.5': 'OUT'})
    for i, ref in enumerate(sorted(db['parts'])):
        db['ref2page'][ref] = 2 + (i % 3)
    return db


KINDS = {'U1': 'pwm_controller', 'U3': 'opto', 'U9': 'opto', 'U4': 'shunt_reference', 'U5': 'pd_controller', 'U7': 'regulator',
         'BR1': 'bridge_rectifier', 'Q1': 'mosfet', 'Q2': 'mosfet', 'D5': 'tvs', 'D6': 'tvs'}
RAILS = {'PGND': {'voltage_v': {'min': 0, 'max': 0}, 'domain': 'PRI'},
         'SGND': {'voltage_v': {'min': 0, 'max': 0}, 'domain': 'SEC'},
         'VOUT': {'voltage_v': {'min': 19, 'max': 21}},
         'VCC': {'voltage_v': {'min': 10, 'max': 16}},
         'RECT': {'voltage_v': {'min': 120, 'max': 375}}}


def intent_for(db, kinds=KINDS, rails=RAILS):
    intent = {'schema_version': 5, 'input_sha256': board_intent.input_fingerprint(db), 'device_kinds': {},
              'power_rails': rails}
    audit = {'device_kinds': {}}
    for ref, kind in kinds.items():
        declaration = {'kind': kind, 'page': 1, 'quote': 'synthetic ' + kind}
        intent['device_kinds'][ref] = declaration
        audit['device_kinds'][ref] = dict(declaration, status='VERIFIED', document='synthetic.pdf',
                                          document_sha256='a' * 64)
    return intent, audit


def generate(db=None, **kw):
    db = db or board()
    intent, audit = intent_for(db, **kw)
    return cc.build(db, intent, audit)


def by_id(result):
    return {c['id']: c for c in result['candidates']}


def members(candidate):
    return sorted(m['ref'] for m in candidate['members'])


class CandidateTests(unittest.TestCase):
    def test_candidates_are_one_per_type_and_anchor_with_fixed_states(self):
        result = generate()
        self.assertEqual(sorted(by_id(result)),
                         ['ANALOG-U4', 'ANALOG-U5', 'DEBUG-BOARD', 'ISOLATION-PRI/SEC', 'POWER_CONVERTER-U1',
                          'POWER_CONVERTER-U7', 'POWER_PROTECTION-J1', 'POWER_PROTECTION-U1.FAULT', 'STARTUP-U1.HV', 'USB-J2'])
        for candidate in result['candidates']:
            self.assertEqual(candidate['states'], list(catalog.CANDIDATE_STATES[candidate['type']]))

    def test_the_flyback_candidate_holds_switch_sense_transformer_both_rectifiers_and_the_output_capacitor(self):
        flyback = by_id(generate())['POWER_CONVERTER-U1']
        self.assertEqual(flyback['anchor'], 'U1')
        self.assertEqual(members(flyback), ['C3', 'C4', 'D2', 'D3', 'Q1', 'R1', 'R2', 'R3', 'R7', 'T1', 'U1', 'U3'])
        roles = {m['ref']: m['role'] for m in flyback['members']}
        self.assertEqual((roles['Q1'], roles['T1'], roles['D2'], roles['C3']),
                         ('switch', 'inductive', 'rectifier', 'output_capacitor'))
        self.assertEqual(roles['U1'], 'anchor')
        self.assertNotIn('C1', members(flyback))      # the converter's input rail is a stop; the bulk cap is the input's
        # the optocoupler on the FB pin closes the loop: it and its LED-side resistor are the converter's
        self.assertEqual((roles['U3'], roles['R7']), ('feedback_opto', 'feedback_led_resistor'))
        self.assertNotIn('U9', members(flyback))      # the other optocoupler is a barrier on a protection chain

    def test_every_member_names_the_path_that_reached_it(self):
        flyback = by_id(generate())['POWER_CONVERTER-U1']
        via = {m['ref']: m['via'] for m in flyback['members']}
        self.assertEqual(via['R2'], 'walk U1.6 -> CS -> R2')
        self.assertEqual(via['D2'], 'walk T1.5 -> SEC_SW -> D2')
        self.assertTrue(via['Q1'].startswith('power_switch:'), via['Q1'])
        self.assertTrue(via['C3'].startswith('output_capacitor:'), via['C3'])

    def test_the_input_protection_walks_from_the_connector_to_the_first_storage_capacitor(self):
        inp = by_id(generate())['POWER_PROTECTION-J1']
        self.assertEqual(members(inp), ['BR1', 'C1', 'F1', 'J1', 'RV1', 'TH1'])
        self.assertEqual(inp['nets']['storage'], 'RECT')

    def test_isolation_holds_every_barrier_of_the_domain_pair(self):
        iso = by_id(generate())['ISOLATION-PRI/SEC']
        self.assertEqual(members(iso), ['CY1', 'T1', 'U3', 'U9'])
        self.assertTrue(iso['cross_cutting'])

    def test_the_port_holds_the_connector_its_clamps_the_pd_controller_and_the_vbus_switch(self):
        port = by_id(generate())['USB-J2']
        self.assertEqual(port['anchor'], 'J2')
        for ref in ('J2', 'D5', 'D6', 'U5', 'Q2', 'R8', 'C7'):
            self.assertIn(ref, members(port), ref)
        self.assertNotIn('U3', members(port))
        self.assertNotIn('T1', members(port))

    def test_analog_candidates_come_from_sense_pins_of_non_converter_anchors_only(self):
        result = by_id(generate())
        self.assertEqual(members(result['ANALOG-U5']), ['R14', 'R15', 'U5'])
        self.assertEqual(members(result['ANALOG-U4']), ['R5', 'R6', 'U4'])   # the shunt reference's divider; R7 is the loop's
        self.assertNotIn('ANALOG-U1', result)       # the controller's CS pin belongs to its converter
        self.assertNotIn('ANALOG-U7', result)

    def test_the_regulator_candidate_holds_inductor_output_capacitor_and_feedback(self):
        buck = by_id(generate())['POWER_CONVERTER-U7']
        self.assertEqual(members(buck), ['C10', 'L2', 'R11', 'R12', 'U7'])
        self.assertEqual(buck['nets']['output'], 'V3V3')

    def test_debug_holds_test_points_without_walking(self):
        debug = by_id(generate())['DEBUG-BOARD']
        self.assertEqual(members(debug), ['TP1'])
        self.assertEqual(debug['members'][0]['via'], 'testpoint on V5')

    def test_a_part_no_candidate_reaches_is_listed_unassigned(self):
        result = generate()
        self.assertEqual([u['ref'] for u in result['unassigned']], ['R99'])
        self.assertIn('V5', result['unassigned'][0]['nets'])

    def test_a_part_two_candidates_reach_at_the_same_distance_is_shared_not_adjudicated_by_page(self):
        db = board()
        fixture.add(db, 'U8', 'OPAMP', [('1', 'VDD', 'V5'), ('2', 'GND', 'SGND'), ('3', 'IN', 'SHARED_IN'), ('4', 'OUT', 'OPA_OUT')])
        fixture.add(db, 'R20', '1K', [('1', '1', 'SHARED_IN'), ('2', '2', 'ISNS_P')])   # one hop from U5 and from U8
        result = generate(db, kinds=dict(KINDS, U8='opamp_comparator'))
        shared = {s['ref']: s for s in result['shared']}
        self.assertEqual(sorted(shared), ['R20'])
        self.assertEqual(sorted(shared['R20']['candidates']), ['ANALOG-U5', 'ANALOG-U8'])
        for cid in ('ANALOG-U5', 'ANALOG-U8'):
            self.assertIn('R20', members(by_id(result)[cid]))

    def test_the_shorter_path_wins_a_part_two_candidates_reach(self):
        db = board()
        fixture.add(db, 'U8', 'OPAMP', [('1', 'VDD', 'V5'), ('2', 'GND', 'SGND'), ('3', 'IN', 'ISNS_N'), ('4', 'OUT', 'OPA_OUT')])
        result = generate(db, kinds=dict(KINDS, U8='opamp_comparator'))
        # R15 sits on ISNS_N: one hop from both U5.CS- and U8.IN; R14 is one hop from U5 but two from U8
        self.assertIn('R14', members(by_id(result)['ANALOG-U5']))
        self.assertNotIn('R14', members(by_id(result)['ANALOG-U8']))
        self.assertEqual([s['ref'] for s in result['shared']], ['R15'])

    def test_an_undeclared_ic_is_a_gap_and_anchors_nothing(self):
        kinds = {k: v for k, v in KINDS.items() if k != 'U7'}
        result = generate(kinds=kinds)
        self.assertNotIn('POWER_CONVERTER-U7', by_id(result))
        self.assertEqual([g['ref'] for g in result['gaps'] if g['kind'] == 'device-kind'], ['U7'])
        self.assertIn('L2', [u['ref'] for u in result['unassigned']])

    def test_a_switch_nobody_drives_anchors_its_own_candidate(self):
        db = board()
        fixture.add(db, 'Q9', 'MOSFET-N', [('1', 'G', 'BIAS_G'), ('2', 'D', 'VCC'), ('3', 'S', 'BIAS_OUT')])
        fixture.add(db, 'R30', '100K', [('1', '1', 'VCC'), ('2', '2', 'BIAS_G')])
        fixture.add(db, 'D9', 'ZENER-12V', [('1', 'A', 'PGND'), ('2', 'K', 'BIAS_G')])
        fixture.add(db, 'C30', '10uF', [('1', '1', 'BIAS_OUT'), ('2', '2', 'PGND')])
        result = generate(db, kinds=dict(KINDS, Q9='mosfet', D9='zener'))
        bias = by_id(result)['POWER_CONVERTER-Q9']
        self.assertEqual(bias['anchor'], 'Q9')
        # VCC is Q9's input: the aux winding's rectifier D3 and the capacitor C4 it charges are the bias circuit's
        self.assertEqual(members(bias), ['C30', 'C4', 'D3', 'D9', 'Q9', 'R30'])
        roles = {m['ref']: m['role'] for m in bias['members']}
        self.assertEqual((roles['D3'], roles['C4']), ('rectifier', 'input_capacitor'))
        self.assertNotIn('D3', members(by_id(result)['POWER_CONVERTER-U1']))

    def test_a_declared_switch_whose_driver_has_no_verified_role_anchors_its_own_converter(self):
        """The reviewer declared Q1 the flyback primary switch (power_switches, cited); the IC on its gate has no
        verified kind. The converter exists on the declaration: Q1 anchors it, holds the transformer and the
        rectifiers, and the unverified driver stays a device-kind gap outside it."""
        db = board()
        intent, audit = intent_for(db, kinds={k: v for k, v in KINDS.items() if k != 'U1'})
        intent['power_switches'] = {'schema_version': 2, 'switches': [
            {'id': 'QPRI', 'ref': 'Q1', 'role': 'flyback_primary', 'citation': 'schematic page 2: Q1 drain SW on T1.2',
             'source_return': {'ref': 'R2', 'ground_net': 'PGND', 'citation': 'schematic page 2: R2 CS to PGND'}}]}
        intent['inductive_loads'] = {'schema_version': 2, 'loads': [
            {'id': 'FLY', 'ref': 'T1', 'kind': 'flyback_transformer', 'citation': 'T1 datasheet page 1 winding table',
             'windings': [{'role': 'primary', 'pins': ['1', '2'], 'dot': '1'},
                          {'role': 'auxiliary', 'pins': ['3', '4'], 'dot': '3'},
                          {'role': 'secondary', 'pins': ['5', '6'], 'dot': '5'}]}]}
        result = cc.build(db, intent, audit)
        self.assertNotIn('POWER_CONVERTER-U1', by_id(result))
        flyback = by_id(result)['POWER_CONVERTER-Q1']
        self.assertEqual(flyback['anchor'], 'Q1')
        for ref in ('Q1', 'T1', 'R2', 'D2', 'D3'):
            self.assertIn(ref, members(flyback), ref)
        self.assertNotIn('U1', members(flyback))
        self.assertEqual([g['ref'] for g in result['gaps'] if g['kind'] == 'device-kind'], ['U1'])

    def test_a_walk_does_not_pass_a_barrier_part(self):
        """A Y capacitor from the primary switch node to the secondary output spans the two domains: the flyback
        walk stops in front of it instead of crossing into the secondary, and only ISOLATION lists it."""
        db = board()
        fixture.add(db, 'CY2', '1nF', [('1', '1', 'SW'), ('2', '2', 'VOUT')])
        result = generate(db)
        self.assertNotIn('CY2', members(by_id(result)['POWER_CONVERTER-U1']))
        self.assertIn('CY2', members(by_id(result)['ISOLATION-PRI/SEC']))
        self.assertNotIn('CY2', [s['ref'] for s in result['shared']])

    def test_a_startup_chain_runs_from_the_startup_pin_to_the_rail(self):
        chain = by_id(generate())['STARTUP-U1.HV']
        self.assertEqual(members(chain), ['R41', 'U1'])
        self.assertEqual(chain['nets'], {'pin': 'U1.5', 'net': 'HV_IN'})
        self.assertTrue(chain['cross_cutting'])
        self.assertNotIn('R41', members(by_id(generate())['POWER_CONVERTER-U1']))   # the pin seeds the chain, not the converter

    def test_a_protection_chain_crosses_the_optocoupler_and_ends_at_the_driving_anchor(self):
        chain = by_id(generate())['POWER_PROTECTION-U1.FAULT']
        self.assertEqual(members(chain), ['C41', 'R42', 'R43', 'U1', 'U5', 'U9'])
        roles = {m['ref']: m['role'] for m in chain['members']}
        self.assertEqual((roles['U9'], roles['U5']), ('optocoupler', 'endpoint'))
        self.assertEqual(chain['type'], 'POWER_PROTECTION')

    def test_a_pin_tied_straight_to_a_rail_makes_no_chain(self):
        db = board()
        fixture.add(db, 'U10', 'LDO', [('1', 'VIN', 'VOUT'), ('2', 'EN', 'VOUT'), ('3', 'VOUT', 'V1V8'), ('4', 'GND', 'SGND')])
        result = by_id(generate(db, kinds=dict(KINDS, U10='regulator')))
        self.assertNotIn('STARTUP-U10.EN', result)

    def test_generation_is_deterministic_under_part_order_and_page_changes(self):
        db = board()
        first = generate(db)
        shuffled = copy.deepcopy(db)
        shuffled['parts'] = dict(reversed(list(db['parts'].items())))
        shuffled['ref2page'] = {ref: 9 for ref in db['parts']}
        second = generate(shuffled)
        strip = lambda r: json.dumps({k: v for k, v in r.items() if k not in ('db_sha256', 'input_sha256')}, sort_keys=True)
        first_c = [dict(c, pages=None) for c in first['candidates']]
        second_c = [dict(c, pages=None) for c in second['candidates']]
        self.assertEqual(first_c, second_c)
        self.assertEqual(first['shared'], second['shared'])
        self.assertEqual(first['unassigned'], second['unassigned'])
        self.assertNotEqual(strip(first), strip(second))    # only the display pages differ

    def test_every_candidate_lives_in_one_domain_except_isolation(self):
        for candidate in generate()['candidates']:
            if candidate['type'] == 'ISOLATION':
                self.assertEqual(candidate['domain'], 'PRI/SEC')
            elif candidate['id'] == 'POWER_CONVERTER-U1':
                self.assertEqual(candidate['domain'], 'PRI')   # the anchor's domain; the secondary members cross it
            elif candidate['type'] != 'DEBUG':
                self.assertIn(candidate['domain'], ('PRI', 'SEC'))

    def test_cli_writes_the_candidate_file_bound_to_the_netlist(self):
        db = board()
        intent, audit = intent_for(db)
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / 'db.json').write_text(json.dumps(db), encoding='utf-8')
            (tmp / 'intent.json').write_text(json.dumps(intent), encoding='utf-8')
            (tmp / 'audit.json').write_text(json.dumps(audit), encoding='utf-8')
            code = cc.main([str(tmp / 'db.json'), '--intent', str(tmp / 'intent.json'),
                            '--datasheet-audit', str(tmp / 'audit.json'), '--json', str(tmp / 'circuit-candidates.json')])
            self.assertEqual(code, 0)
            out = json.loads((tmp / 'circuit-candidates.json').read_text(encoding='utf-8'))
        self.assertEqual(out['schema_version'], 2)
        self.assertEqual(out['db_sha256'], cc.db_fingerprint(db))
        self.assertEqual(sorted(c['id'] for c in out['candidates']), sorted(by_id(generate(db))))



class OwnershipTests(unittest.TestCase):
    """Every member says whether its candidate owns it (function-tree design, step 1). One candidate owns each part and
    the others only refer to it: a circuit's anchor first, then a circuit member, then a chain member, then the
    isolation band, then a chain's anchor or endpoint. Equal claims are left to a decision and listed as shared."""

    @staticmethod
    def owners(result):
        out = {}
        for cand in result['candidates']:
            for m in cand['members']:
                if m['owned']:
                    out.setdefault(m['ref'], []).append(cand['id'])
        return out

    def test_each_held_part_is_owned_by_exactly_one_candidate(self):
        result = generate()
        self.assertEqual(result['schema_version'], 2)
        owners = self.owners(result)
        held = {m['ref'] for cand in result['candidates'] for m in cand['members']}
        self.assertEqual(sorted(held), sorted(owners))
        self.assertEqual({ref: len(v) for ref, v in owners.items() if len(v) != 1}, {})
        self.assertTrue(all(m['owned'] in (True, False) for cand in result['candidates'] for m in cand['members']))

    def test_a_circuit_owns_its_anchor_and_its_members_before_a_chain_and_the_isolation_band(self):
        owners = {ref: v[0] for ref, v in self.owners(generate()).items()}
        self.assertEqual(owners['U1'], 'POWER_CONVERTER-U1')          # the converter's anchor anchors two chains too
        self.assertEqual(owners['U5'], 'ANALOG-U5')                   # an anchor; a chain's endpoint, the port's PD controller
        self.assertEqual(owners['T1'], 'POWER_CONVERTER-U1')          # the transformer is also a barrier of the band
        self.assertEqual(owners['U3'], 'POWER_CONVERTER-U1')          # the feedback optocoupler
        self.assertEqual(owners['R43'], 'USB-J2')                     # a port part a protection chain also walks
        self.assertEqual(owners['U9'], 'POWER_PROTECTION-U1.FAULT')   # the chain's optocoupler: the chain before the band
        self.assertEqual(owners['CY1'], 'ISOLATION-PRI/SEC')          # held by the band alone
        self.assertEqual(owners['R41'], 'STARTUP-U1.HV')

    def test_a_part_two_circuits_reach_at_the_same_distance_is_owned_by_neither_until_a_decision(self):
        db = board()
        fixture.add(db, 'U8', 'OPAMP', [('1', 'VDD', 'V5'), ('2', 'GND', 'SGND'), ('3', 'IN', 'SHARED_IN'), ('4', 'OUT', 'OPA_OUT')])
        fixture.add(db, 'R20', '1K', [('1', '1', 'SHARED_IN'), ('2', '2', 'ISNS_P')])
        result = generate(db, kinds=dict(KINDS, U8='opamp_comparator'))
        self.assertNotIn('R20', self.owners(result))
        self.assertEqual({s['ref']: s['candidates'] for s in result['shared']}, {'R20': ['ANALOG-U5', 'ANALOG-U8']})


if __name__ == '__main__':
    unittest.main()


class DrivenSwitchTests(unittest.TestCase):
    """R6 fix list B4 (2026-10-25): a small-signal transistor the circuit's own net drives at its gate belongs to the
    circuit, and the walk goes on from its drain; a power switch of the inventory is not crossed this way."""

    def board(self):
        db = board()
        add = fixture.add
        # the PD controller's GPIO drives Q8 directly (as R6's U601 drives Q202); its drain pulls EN_X, pulled up to VCC
        add(db, 'Q8', 'MOSFET-N', [('1', 'G', 'FLT_DRV'), ('2', 'D', 'EN_X'), ('3', 'S', 'SGND')])
        add(db, 'R45', '10K', [('1', '1', 'EN_X'), ('2', '2', 'VCC')])
        for ref in ('Q8', 'R45'):
            db['ref2page'][ref] = 2
        return db

    def test_a_driven_transistor_and_its_drain_load_join_the_driving_circuit(self):
        result = generate(self.board())
        port = by_id(result)['USB-J2']
        roles = {m['ref']: m['role'] for m in port['members']}
        self.assertEqual(roles.get('Q8'), 'driven_switch')
        self.assertNotIn('Q8', [u['ref'] for u in result['unassigned']])
        self.assertIn('Q8(gate)', next(m['via'] for m in port['members'] if m['ref'] == 'Q8'))

    def test_a_supervisor_driving_a_signal_transistor_is_no_converter(self):
        # R8 (2026-10-28): TPS3700 drove PNP Q406 into the flyback's FAULT pin and became POWER_CONVERTER-U406
        db = self.board()
        add = fixture.add
        add(db, 'U8', 'TPS3700', [('1', 'VDD', 'VCC'), ('2', 'GND', 'PGND'), ('3', 'INA+', 'MON'), ('4', 'OUTB', 'OVP_B')])
        add(db, 'R46', '10K', [('1', '1', 'VCC'), ('2', '2', 'OVP_B')])
        add(db, 'Q9', 'PNP', [('1', 'B', 'OVP_B'), ('2', 'E', 'VCC'), ('3', 'C', 'OVP_COL')])
        add(db, 'R47', '1K8', [('1', '1', 'OVP_COL'), ('2', '2', 'FLT')])
        add(db, 'R48', '100K', [('1', '1', 'AUX'), ('2', '2', 'MON')])
        add(db, 'R49', '10K', [('1', '1', 'MON'), ('2', '2', 'PGND')])
        db['pintype']['U8.4'] = 'OUT'
        for ref in ('U8', 'R46', 'Q9', 'R47', 'R48', 'R49'):
            db['ref2page'][ref] = 2
        result = generate(db, kinds=dict(KINDS, U8='supervisor', Q9='bjt'))
        self.assertNotIn('POWER_CONVERTER-U8', by_id(result))
        monitor = by_id(result)['ANALOG-U8']                 # the supervisor's own circuit holds the transistor
        self.assertTrue({'Q9', 'R46', 'R49'} <= set(members(monitor)), members(monitor))

    def test_the_power_switch_is_still_the_anchor_s_switch_not_a_driven_one(self):
        result = generate(self.board())
        flyback = by_id(result)['POWER_CONVERTER-U1']
        self.assertNotEqual(next(m['role'] for m in flyback['members'] if m['ref'] == 'Q1'), 'driven_switch')
        self.assertEqual(result['rules_version'], cc.RULES_VERSION)

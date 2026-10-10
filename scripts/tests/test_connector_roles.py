"""Connector-role calibration, including a real relay safety counterexample."""
import pathlib
import sys
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
for option in list(sys.argv):
    if option.startswith('--engine='):
        SCRIPTS = pathlib.Path(option.split('=', 1)[1]) / 'scripts'
        sys.argv.remove(option)
sys.path.insert(0, str(SCRIPTS))
from checkers.netgraph import classify, CONNECTOR, RELAY, JUMPER, IC
from checkers.inductive_load import build_inventory
from plan_review import build_review_plan
from lint import Lint


def add(db, ref, part, pins):
    db['parts'][ref] = {'part': part, 'value': part, 'prim': part, 'jedec': '', 'nc': False}
    for pin, name, net in pins:
        node = ref + '.' + pin
        db['nets'].setdefault(net, []).append(node)
        db['pin2net'][node] = net
        db['pinname'][node] = name


def board():
    db = {'nets': {}, 'parts': {}, 'pin2net': {}, 'pinname': {}, 'pseudo_nets': []}
    add(db, 'K1', 'TERMINAL_KF235-5.0-3P', [('1', 'B', 'B'), ('2', 'GND', 'GND'), ('3', 'A', 'A')])
    add(db, 'K2', 'HEADER_MALE_6X1', [(str(i), n, n) for i, n in enumerate(('D', 'DE', 'REn', 'R', '5V', 'GND'), 1)])
    return db


class ConnectorRoles(unittest.TestCase):
    def test_explicit_connector_names_override_arbitrary_refdes(self):
        for ref, name in [('K1', 'TERMINAL_KF235-5.0-3P'), ('K2', 'HEADER_MALE_6X1'),
                          ('X3', 'Connector_Generic:Conn_01x03'), ('U9', 'PinHeader_1x06'),
                          ('K7', 'TerminalBlock_1x03'), ('K8', 'HEADER_FEMALE_2X3')]:
            with self.subTest(ref=ref, name=name):
                self.assertEqual(classify(ref, {'part': name}, 3), (CONNECTOR, 'part-keyword'))

    def test_connector_plan_covers_all_roles_without_legacy_prefix(self):
        plan = build_review_plan(board())
        for ref in ('K1', 'K2'):
            rules = {c['rule'] for c in plan['checks'] if c['object'].get('ref') == ref}
            self.assertTrue({'DEV-E01', 'DEV-D03', 'DEV-D05', 'PRO-D03'} <= rules, (ref, rules))

    def test_connectors_do_not_create_coil_candidates(self):
        inventory = build_inventory(board())
        self.assertEqual([load for state in inventory['states'] for load in state['loads']], [])
        self.assertFalse([c for c in build_review_plan(board())['checks']
                          if c['rule'] in ('DRV-T01', 'DRV-C01')])

    def test_real_relay_missing_clamp_is_still_detected(self):
        db = {'nets': {}, 'parts': {}, 'pin2net': {}, 'pinname': {}, 'pseudo_nets': []}
        add(db, 'K1', 'RELAY-5V', [('1', 'COIL1', 'RELAY_DRV'), ('2', 'COIL2', 'V24')])
        add(db, 'Q1', 'AO3400', [('1', 'G', 'EN'), ('2', 'D', 'RELAY_DRV'), ('3', 'S', 'GND')])
        self.assertIn('K1', [load['ref'] for s in build_inventory(db)['states'] for load in s['loads']])
        self.assertIn('DRV-A01', [f['rule'] for f in Lint(db, '').run()])

    def test_relay_evidence_and_uncertain_k_are_not_masked(self):
        self.assertEqual(classify('K1', {'part': 'HEADER_MALE_6X1 RELAY'}, 6)[0], RELAY)
        self.assertEqual(classify('K1', {'part': 'HEADER_MALE_6X1'}, 6, declared=RELAY)[0], RELAY)
        for name in ('?', 'HEADER_CONTROL', 'TERMINAL_VOLTAGE_MONITOR'):
            self.assertEqual(classify('K1', {'part': name}, 3), (RELAY, 'refdes-prefix'))

    def test_two_pin_k_is_not_a_relay(self):
        # 两脚器件不可能同时有线圈和触点：部分库把电池座/连接器编为 K
        self.assertEqual(classify('K3', {'part': 'S2B-PH-K-S(LF)(SN)'}, 2)[0], 'unknown')

    def unnamed_relay(self, diode=None):
        db = {'nets': {}, 'parts': {}, 'pin2net': {}, 'pinname': {}, 'pseudo_nets': []}
        add(db, 'K1', 'SRD-05VDC-SL-C RELAY', [('1', None, 'COIL_HI'), ('2', None, 'COIL_LO'),
                                               ('3', None, 'NO'), ('4', None, 'COM'), ('5', None, 'NC')])
        add(db, 'R4', '10R', [('1', '1', 'COIL_HI'), ('2', '2', 'VCC')])
        add(db, 'Q1', 'NPN', [('1', 'B', 'BASE'), ('2', 'E', 'GND'), ('3', 'C', 'COIL_LO')])
        add(db, 'J1', 'TERMINAL_KF235-5.0-3P', [('1', '1', 'NO'), ('2', '2', 'COM'), ('3', '3', 'NC')])
        add(db, 'U1', 'LDO', [('1', 'VIN', 'VIN'), ('2', 'VOUT', 'VCC'), ('3', 'GND', 'GND')])
        if diode:
            add(db, 'D2', 'DIODE', [('1', 'A', diode[0]), ('2', 'K', diode[1])])
        db['pinname'] = {node: name for node, name in db['pinname'].items() if name}   # 符号无脚名
        return db

    def test_relay_coil_inferred_from_topology_when_symbol_has_no_pin_names(self):
        rules = lambda db: [f['rule'] for f in Lint(db, '').run() if f['rule'] in ('DRV-A01', 'DRV-A02')]
        self.assertEqual(rules(self.unnamed_relay()), ['DRV-A01'])
        self.assertEqual(rules(self.unnamed_relay(('COIL_HI', 'COIL_LO'))), ['DRV-A02'])
        self.assertEqual(rules(self.unnamed_relay(('COIL_LO', 'COIL_HI'))), [])
        loads = [l for s in build_inventory(self.unnamed_relay())['states'] for l in s['loads']]
        self.assertTrue(any(g.startswith('pin-roles-inferred:K1') for g in loads[0]['gaps']))

    def test_relay_coil_is_not_guessed_when_two_pins_reach_a_rail(self):
        db = self.unnamed_relay()
        db['nets']['COM'].remove('K1.4')
        db['nets']['VCC'].append('K1.4')
        db['pin2net']['K1.4'] = 'VCC'
        loads = [l for s in build_inventory(db)['states'] for l in s['loads']]
        self.assertIn('pin-roles:K1', loads[0]['gaps'])

    def test_slavic_optocoupler_pin_names_resolve_roles(self):
        from checkers.netgraph import NetGraph
        db = {'nets': {}, 'parts': {}, 'pin2net': {}, 'pinname': {}, 'pseudo_nets': []}
        add(db, 'U1', 'PC357_OPTO', [('1', 'anoda', 'IN'), ('2', 'katoda', 'GND'),
                                     ('3', 'emiter', 'GND'), ('4', 'kolektor', 'OUT')])
        graph = NetGraph(db)
        self.assertEqual([graph.role('U1.' + p) for p in '1234'],
                         ['led_anode', 'led_cathode', 'out_emitter', 'out_collector'])
        self.assertIn('PRO-A03', [f['rule'] for f in Lint(db, '').run()])

    def test_eagle_dimensioned_headers_override_jumper_prefix(self):
        for name in ('HEADER-1X10', 'microbuilder:HEADER-1X10:THICKER', 'HEADER_2X3'):
            with self.subTest(name=name):
                self.assertEqual(classify('JP1', {'part': name}, 10),
                                 (CONNECTOR, 'part-keyword'))

    def test_dimensioned_headers_expand_all_connector_roles(self):
        db = {'nets': {}, 'parts': {}, 'pin2net': {}, 'pinname': {}, 'pseudo_nets': []}
        add(db, 'JP1', 'HEADER-1X10', [(str(i), str(i), 'PORT_' + str(i)) for i in range(1, 11)])
        add(db, 'JP2', 'JUMPER', [('1', '1', 'A'), ('2', '2', 'B')])
        plan = build_review_plan(db)
        rules = {c['rule'] for c in plan['checks'] if c['object'].get('ref') == 'JP1'}
        self.assertTrue({'DEV-E01', 'DEV-D03', 'DEV-D05', 'PRO-D03'} <= rules)
        self.assertFalse([c for c in plan['checks']
                          if c['object'].get('ref') == 'JP2' and c['rule'] == 'PRO-D03'])
        self.assertEqual(classify('JP2', db['parts']['JP2'], 2)[0], JUMPER)

    def test_header_description_does_not_override_unrelated_devices(self):
        self.assertEqual(classify('U2', {'part': 'HEADER_CONTROL'}, 20)[0], IC)
        self.assertEqual(classify('K2', {'part': 'HEADER-1X10 RELAY'}, 10)[0], RELAY)
        self.assertEqual(classify('JP2', {'part': 'HEADER_CONTROL'}, 2)[0], JUMPER)

    def test_jst_battery_socket_with_k_refdes_is_a_connector(self):
        self.assertEqual(classify('K3', {'part': 'JST-2pin-SMD', 'prim': 'e-radionica.com schematics:JST-2pin-SMD'}, 2),
                         (CONNECTOR, 'part-keyword'))
        self.assertEqual(classify('K1', {'part': 'RELAY JST_COIL'}, 4)[0], RELAY)
        self.assertEqual(classify('U3', {'part': 'BQ24075', 'jedec': 'Custom:JST_STYLE_QFN'}, 16)[0], IC)

    def test_legacy_connector_prefix_still_expands(self):
        db = board()
        db['parts']['J3'] = {'part': '?', 'nc': False}
        rules = {c['rule'] for c in build_review_plan(db)['checks'] if c['object'].get('ref') == 'J3'}
        self.assertTrue({'DEV-E01', 'DEV-D03', 'DEV-D05', 'PRO-D03'} <= rules)


if __name__ == '__main__':
    unittest.main()

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
from checkers.netgraph import classify, CONNECTOR, RELAY
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

    def test_legacy_connector_prefix_still_expands(self):
        db = board()
        db['parts']['J3'] = {'part': '?', 'nc': False}
        rules = {c['rule'] for c in build_review_plan(db)['checks'] if c['object'].get('ref') == 'J3'}
        self.assertTrue({'DEV-E01', 'DEV-D03', 'DEV-D05', 'PRO-D03'} <= rules)


if __name__ == '__main__':
    unittest.main()

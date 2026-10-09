"""Based on design by Steven Casagrande / Galvant Industries (CC BY-SA 3.0).

Unused physical contacts do not require IC input bias. True input warnings
remain observable even with NC markings and misleading reference designators.
"""
import json
import pathlib
import sys
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
for option in list(sys.argv):
    if option.startswith('--engine='):
        SCRIPTS = pathlib.Path(option.split('=', 1)[1]) / 'scripts'
        sys.argv.remove(option)
sys.path.insert(0, str(SCRIPTS))
from lint import Lint
from checkers.netgraph import classify, CONNECTOR, IC, MOSFET


def contact(part='MICRO-B_USB', ref='U3', marked=True):
    node = ref + '.4'
    return {'parts': {ref: {'part': part, 'value': part, 'nc': False}},
            'nets': {'UNUSED': [node]}, 'pin2net': {node: 'UNUSED'},
            'pinname': {node: 'ID'}, 'pintype': {node: 'IN'},
            'pseudo_nets': ['UNUSED'] if marked else [],
            'no_connect_nodes': [node] if marked else []}


def inputs(db):
    return [f for f in Lint(db).run() if f['rule'] == 'NET-A07']


class ConnectorNcInputs(unittest.TestCase):
    def test_real_reduced_net_incidence_has_no_input_bias_obligation(self):
        fixture = pathlib.Path(__file__).parent / 'fixtures/galvant-usb-connector-nc/board.json'
        db = json.loads(fixture.read_text())
        self.assertEqual(len(db['pin2net']), 39)
        self.assertEqual(inputs(db), [])

    def test_connector_role_does_not_hide_unmarked_floating_contact(self):
        hits = inputs(contact(marked=False))
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]['kind'], 'FINDING')

    def test_ic_and_unknown_refdes_only_connector_remain_candidates(self):
        for part, ref in [('SOC', 'U3'), ('?', 'J3'), ('USB_PHY', 'U3'),
                          ('MICRO-B_USB_CONTROLLER', 'U3')]:
            with self.subTest(part=part, ref=ref):
                hits = inputs(contact(part, ref))
                self.assertEqual(len(hits), 1)
                self.assertEqual(hits[0]['kind'], 'CANDIDATE')

    def test_shared_nc_net_still_checks_ic_input(self):
        db = contact()
        db['parts']['U1'] = {'part': 'SOC', 'value': 'SOC', 'nc': False}
        db['nets']['UNUSED'].append('U1.1')
        db['pin2net']['U1.1'] = 'UNUSED'
        db['pinname']['U1.1'] = 'EN'
        db['pintype']['U1.1'] = 'IN'
        db['no_connect_nodes'].append('U1.1')
        hits = inputs(db)
        self.assertEqual(len(hits), 1)
        self.assertTrue(hits[0]['detail'].startswith('U1.1 '))

    def test_conflicting_identity_and_free_form_value_keep_input_warning(self):
        for fields in [
                {'part': 'USB_PHY', 'value': 'MICRO-B_USB'},
                {'part': 'SOC', 'value': 'MICRO-B_USB controller'},
                {'part': 'MICRO-B_USB', 'prim': 'Interface:USB_PHY', 'value': 'MICRO-B_USB'},
                {'part': 'MICRO-B_USB', 'value': 'USB_PHY'},
                {'value': 'MICRO-B_USB'},
                {'part': '?', 'value': 'MICRO-B_USB'}]:
            with self.subTest(fields=fields):
                db = contact()
                db['parts']['U3'] = dict(fields, nc=False)
                hits = inputs(db)
                self.assertEqual(len(hits), 1)
                self.assertEqual(hits[0]['kind'], 'CANDIDATE')

    def test_other_connector_keywords_cannot_bypass_identity_conflicts(self):
        for fields in [
                {'part': 'USB_PHY', 'prim': 'Connector:USB_C', 'value': 'USB_PHY'},
                {'part': 'USB_PHY', 'value': 'CONN_01X05'},
                {'part': 'SOC', 'value': 'PINHEADER_1X5'},
                {'part': '?', 'prim': 'Connector:MICRO-B_USB'},
                {'part': 'Connector:USB_C', 'value': 'USB_PHY'},
                {'part': 'Connector:USB_C', 'value': 'USB_PHY Connector:USB_C'},
                {'value': 'Connector:USB_C'},
                {'part': 'USB_PHY:Connector:USB_C', 'value': 'USB_PHY:Connector:USB_C'},
                {'part': 'Connector:USB_PHY', 'value': 'Connector:USB_PHY'},
                {'part': 'JST_PH', 'prim': '?', 'value': 'JST_PH'}]:
            with self.subTest(fields=fields):
                db = contact()
                db['parts']['U3'] = dict(fields, nc=False)
                hits = inputs(db)
                self.assertEqual(len(hits), 1)
                self.assertEqual(hits[0]['kind'], 'CANDIDATE')

    def test_active_pin_signature_is_not_proof_of_passive_contacts(self):
        for names in [('G', 'D', 'S'), ('B', 'C', 'E')]:
            with self.subTest(names=names):
                db = contact('Connector:CONN_01X03')
                db['pinname']['U3.4'] = names[0]
                for pin, name in zip(('2', '3'), names[1:]):
                    node = 'U3.' + pin
                    db['nets'][name] = [node]
                    db['pin2net'][node] = name
                    db['pinname'][node] = name
                    db['pintype'][node] = 'PASSIVE'
                hits = inputs(db)
                self.assertEqual(len(hits), 1)
                self.assertEqual(hits[0]['kind'], 'CANDIDATE')

    def test_package_conflicts_require_review_without_treating_package_as_mpn(self):
        for package in ['RF_Module:ESP32-WROOM-32', 'Package_SO:SOIC-14',
                        'Package_BGA:TFBGA-121', 'Transistor_FET:TO-220-3',
                        'UnresolvedCustomPackage']:
            with self.subTest(package=package):
                db = contact()
                db['parts']['U3']['jedec'] = package
                self.assertEqual(len(inputs(db)), 1)
        for package in ['MODULE', 'Connector_USB:USB_Micro-B']:
            with self.subTest(package=package):
                db = contact()
                db['parts']['U3']['jedec'] = package
                self.assertEqual(inputs(db), [])

    def test_consistent_connector_families_keep_unused_contact_exemption(self):
        for name in ['Connector:USB_C', 'CONN_01X05', 'PINHEADER_1X5', 'JST_PH']:
            with self.subTest(name=name):
                self.assertEqual(inputs(contact(name, ref='J3')), [])

    def test_complete_family_names_and_authoritative_active_kind(self):
        for name in ['MICRO-B_USB', 'usb_isolator-rescue:MICRO-B_USB', 'MINI-AB-USB']:
            with self.subTest(name=name):
                self.assertEqual(classify('U3', {'part': name}, 5),
                                 (CONNECTOR, 'part-keyword'))
                self.assertEqual(classify('U3', {'part': name}, 5, declared=IC),
                                 (IC, 'datasheet'))
        self.assertEqual(classify('U3', {'part': 'MICRO-B_USB MOSFET'}, 5)[0], MOSFET)


if __name__ == '__main__':
    unittest.main()

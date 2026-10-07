import os
import pathlib
import sys
import unittest

SCRIPTS = pathlib.Path(os.environ.get('SR_RELAY_TEST_SCRIPTS', pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(SCRIPTS))
from lint import Lint


def relay_board():
    nets = {'NC': ['K1.5', 'J1.1'], 'NO': ['K1.3', 'J1.3'],
            'COM': ['K1.4', 'J1.2'], 'COIL_P': ['K1.1'], 'COIL_N': ['K1.2']}
    pins = {node: net for net, members in nets.items() for node in members}
    return {'nets': nets, 'pin2net': pins,
            'parts': {'K1': {'value': 'SRD-05VDC-SL-C', 'part': 'RELAY', 'nc': False},
                      'J1': {'value': 'CONN_01X03', 'part': 'CONN_01X03', 'nc': False}},
            'pinname': {'K1.1': 'COIL+', 'K1.2': 'COIL-', 'K1.3': 'NO',
                        'K1.4': 'COM', 'K1.5': 'NC', 'J1.1': 'NC',
                        'J1.2': 'COM', 'J1.3': 'NO'},
            'pintype': {n: 'UNSPEC' for n in pins}, 'ref2page': {}, 'pseudo_nets': []}


def nc_findings(db):
    return [f for f in Lint(db).run() if f['rule'] == 'NET-A04']


class RelayNcContactTest(unittest.TestCase):
    def test_form_c_contact_net_is_not_no_connect_short(self):
        self.assertEqual(nc_findings(relay_board()), [])

    def test_mixed_semiconductor_nc_still_reports(self):
        d = relay_board()
        d['parts']['U1'] = {'part': 'IC', 'value': 'IC', 'nc': False}
        d['nets']['NC'].append('U1.7')
        d['pin2net']['U1.7'] = 'NC'
        d['pinname']['U1.7'] = 'NC'
        self.assertEqual([f['kind'] for f in nc_findings(d)], ['FINDING'])

    def test_connector_names_without_relay_do_not_exempt(self):
        d = relay_board()
        d['parts']['K1'] = {'part': 'CONNECTOR', 'value': 'CONN', 'nc': False}
        self.assertEqual([f['kind'] for f in nc_findings(d)], ['FINDING'])

    def test_missing_contact_roles_do_not_exempt(self):
        d = relay_board()
        d['pinname'].pop('K1.3')
        self.assertEqual([f['kind'] for f in nc_findings(d)], ['FINDING'])

    def test_reference_prefix_alone_does_not_exempt(self):
        d = relay_board()
        d['parts']['K1'] = {'part': '', 'value': '', 'nc': False}
        self.assertEqual([f['kind'] for f in nc_findings(d)], ['FINDING'])

    def test_unfitted_relay_does_not_exempt(self):
        d = relay_board()
        d['parts']['K1']['nc'] = True
        self.assertEqual([f['kind'] for f in nc_findings(d)], ['FINDING'])

    def test_nc_and_no_short_do_not_exempt(self):
        d = relay_board()
        d['nets']['NC'] += d['nets'].pop('NO')
        for n in d['nets']['NC']:
            d['pin2net'][n] = 'NC'
        self.assertEqual([f['kind'] for f in nc_findings(d)], ['FINDING'])

    def test_pseudo_export_nc_retains_info(self):
        d = relay_board()
        d['pseudo_nets'] = ['NC']
        self.assertEqual([f['kind'] for f in nc_findings(d)], ['INFO'])


if __name__ == '__main__':
    unittest.main()

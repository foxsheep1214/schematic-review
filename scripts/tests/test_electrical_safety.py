import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from audit_datasheets import build_datasheet_audit, validate_datasheet_audit
from electrical_contract import db_fingerprint
from electrical_fixtures import divider_model
from lint import Lint
from solve_dividers import Solver, parse_resistor
from test_solve_dividers import divider_db


def database(nets, values, pins=None):
    return {'nets': nets, 'parts': {ref: {'value': val, 'nc': False} for ref, val in values.items()},
            'pin2net': {node: net for net, nodes in nets.items() for node in nodes},
            'pinname': pins or {}, 'pintype': {}, 'ref2page': {}, 'pseudo_nets': []}


class ElectricalSafetyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def test_p01_tvs_shunt_does_not_power_a_load(self):
        db = database({'VCC_3V3': ['U1.1', 'D1.1', 'C1.1'],
                       'GND': ['U1.2', 'D1.2', 'C1.2']},
                      {'U1': 'LOAD', 'D1': 'SMBJ5.0A', 'C1': '100nF'},
                      {'U1.1': 'VDD', 'U1.2': 'VSS'})
        lint = Lint(db)
        self.assertFalse(lint.driven('VCC_3V3'))
        self.assertTrue(any(x['rule'] in ('PWR-A01', 'PWR-A02') for x in lint.run()))

    def test_source_path_through_fuse_ferrite_and_zero_ohm(self):
        db = database({'SOURCE': ['U1.1', 'F1.1'], 'MID1': ['F1.2', 'FB1.1'],
                       'MID2': ['FB1.2', 'R1.1'], 'VCC_3V3': ['R1.2', 'U2.1']},
                      {'U1': 'REG', 'U2': 'LOAD', 'F1': 'FUSE', 'FB1': 'FERRITE', 'R1': '0R'},
                      {'U1.1': 'VOUT', 'U2.1': 'VDD'})
        self.assertEqual(Lint(db).power_path('VCC_3V3')['path'], ['F1', 'FB1', 'R1'])
        db['parts']['R1']['nc'] = True
        self.assertFalse(Lint(db).driven('VCC_3V3'))

    def test_connector_is_only_source_in_declared_state(self):
        db = database({'VBUS': ['J1.1', 'U1.1']}, {'J1': 'CONN', 'U1': 'LOAD'}, {'U1.1': 'VDD'})
        intent = {'active_state': 'on', 'power_sources': [
            {'node': 'J1.1', 'states': ['on'], 'citation': 'Synthetic external supply spec'}]}
        self.assertFalse(Lint(db).driven('VBUS'))
        self.assertTrue(Lint(db, intent=intent).driven('VBUS'))
        intent['active_state'] = 'off'
        self.assertFalse(Lint(db, intent=intent).driven('VBUS'))

    def test_mos_requires_state_specific_directed_path(self):
        db = database({'VIN': ['J1.1', 'Q1.1'], 'VOUT': ['Q1.2', 'U1.1'], 'GATE': ['Q1.3']},
                      {'J1': 'CONN', 'Q1': 'MOS', 'U1': 'LOAD'}, {'U1.1': 'VDD'})
        intent = {'active_state': 'on', 'power_sources': [
            {'node': 'J1.1', 'states': ['on', 'off'], 'citation': 'source'}],
            'power_paths': [{'ref': 'Q1', 'from': 'VIN', 'to': 'VOUT', 'state': 'on', 'citation': 'gate condition'}]}
        self.assertTrue(Lint(db, intent=intent).driven('VOUT'))
        intent['active_state'] = 'off'
        self.assertFalse(Lint(db, intent=intent).driven('VOUT'))

    def test_p05_tvs_working_voltage_is_not_breakdown_or_burnout(self):
        db = database({'VCC_5V1': ['D1.1', 'J1.1'], 'GND': ['D1.2']},
                      {'D1': 'SMBJ5.0A', 'J1': 'CONN'})
        items = [x for x in Lint(db).run() if x['rule'] == 'PRO-A02']
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['kind'], 'CANDIDATE')
        self.assertNotIn('上电即', items[0]['detail'])

    def test_unresolved_resistor_depth_and_separate_grounds(self):
        db = divider_db(series_lower=True)
        self.assertEqual(Solver(db, max_depth=1).solve_net('FB_NET')['status'], 'ambiguous')
        db['parts']['R4']['value'] = 'UNKNOWN'
        self.assertEqual(Solver(db).solve_net('FB_NET')['status'], 'ambiguous')
        db = divider_db()
        db['parts']['R3'] = {'value': '10K/1%', 'nc': False}
        db['nets']['FB_NET'].append('R3.1')
        db['nets']['AGND'] = ['R3.2']
        db['pin2net'].update({'R3.1': 'FB_NET', 'R3.2': 'AGND'})
        self.assertEqual(Solver(db).solve_net('FB_NET')['status'], 'ambiguous')
        self.assertEqual(Solver(db, model=divider_model()).solve_net('FB_NET')['status'], 'ambiguous')

    def test_audit_expands_critical_passives_and_rejects_unknown_ref(self):
        db = divider_db()
        audit = build_datasheet_audit(db, required_refs=['R1'])
        self.assertEqual(validate_datasheet_audit(audit, db), [])
        self.assertTrue(any('R1' in x['refdes'] for x in audit['materials']))
        with self.assertRaises(ValueError):
            build_datasheet_audit(db, required_refs=['R404'])

    def test_resistor_garbage_suffix_is_not_a_numeric_guarantee(self):
        self.assertIsNone(parse_resistor('20Kwrong/1%'))
        self.assertIsNone(parse_resistor('20K', float('nan')))
        self.assertAlmostEqual(parse_resistor('20Kohm/1%')['kohm'], 20)

    def test_missing_vref_bounds_cli_preserves_only_nominal_estimate(self):
        from solve_dividers import _row
        result = Solver(divider_db()).solve_net('FB_NET')
        row = _row('U1', 'FB_NET', result, .8, None)
        self.assertEqual(row['review_result'], 'INSUFFICIENT')
        self.assertAlmostEqual(row['voltage_nominal'], 2.4)
        self.assertNotIn('voltage', row)

if __name__ == '__main__':
    unittest.main()

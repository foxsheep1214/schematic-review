"""Synthetic physical-array invariants, not real electrical acceptance."""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from board_intent import input_fingerprint
from i2c_topology import build_i2c_topology, validate_i2c_intent


def add(db, ref, value, pins):
    db['parts'][ref] = {'value': value, 'part': value, 'nc': False}
    for pin, name, net in pins:
        node = ref + '.' + pin
        db['nets'].setdefault(net, []).append(node)
        db['pin2net'][node] = net
        db['pinname'][node] = name


def fixture():
    db = {'parts': {}, 'nets': {}, 'pin2net': {}, 'pinname': {}}
    add(db, 'U1', 'SYN-I2C', [('1', 'SCL', 'SCL_LOW'), ('6', 'SDA', 'SDA_LOW')])
    add(db, 'Q2', 'SYN-BOUNDARY', [('1', 'S', 'SCL_LOW'), ('2', 'G', 'V3'),
                                ('3', 'D', 'SDA_HIGH'), ('4', 'S', 'SDA_LOW'),
                                ('5', 'G', 'V3'), ('6', 'D', 'SCL_HIGH')])
    add(db, 'R3', '10K', [('1', '1', 'VIN'), ('8', '2', 'SCL_HIGH'),
                         ('2', '1', 'V3'), ('7', '2', 'SCL_LOW'),
                         ('3', '1', 'VIN'), ('6', '2', 'SDA_HIGH'),
                         ('4', '1', 'V3'), ('5', '2', 'SDA_LOW')])
    cfg = {'schema_version': 2, 'buses': [
        {'id': 'LOW', 'sda': ['U1.6'], 'scl': ['U1.1'], 'citation': 'Synthetic pin map'}],
        'components': {
            'U1': {'kind': 'endpoint', 'citation': 'Synthetic pin map'},
            'Q2': {'kind': 'level_shifter', 'citation': 'Synthetic physical boundary',
                   'ports': [{'sda': 'Q2.3', 'scl': 'Q2.6'}, {'sda': 'Q2.4', 'scl': 'Q2.1'}]},
            'R3': {'kind': 'resistor', 'citation': 'Synthetic four independent equal10k branches',
                   'links': [['R3.1', 'R3.8'], ['R3.2', 'R3.7'], ['R3.3', 'R3.6'], ['R3.4', 'R3.5']]}},
        'rails': {'VIN': 'Synthetic supply', 'V3': 'Synthetic supply'}}
    intent = {'input_sha256': input_fingerprint(db), 'i2c_topology': cfg,
              'assemblies': [{'id': 'RUN', 'citation': 'Synthetic population',
                              'population': {ref: True for ref in db['parts']}}]}
    return db, intent


def regions(db, intent):
    return build_i2c_topology(db, intent)['states'][0]['regions']


class ResistorArrayTests(unittest.TestCase):
    def test_four_branches_remain_four_regions_with_real_values_and_nodes(self):
        db, intent = fixture()
        self.assertEqual(validate_i2c_intent(intent, db), [])
        rows = regions(db, intent)
        self.assertEqual(len(rows), 4)
        self.assertEqual({r['nets'][0] for r in rows}, {'SCL_LOW', 'SDA_LOW', 'SCL_HIGH', 'SDA_HIGH'})
        for row in rows:
            self.assertEqual(len(row['pullups']), 1)
            pull = row['pullups'][0]
            self.assertEqual(pull['ohms'], 10000)
            self.assertEqual(pull['signal_net'], row['nets'][0])
            self.assertEqual(pull['rail'], 'V3' if 'LOW' in row['nets'][0] else 'VIN')
            self.assertEqual(len(pull['nodes']), 2)
            self.assertNotIn('review_result', row)
            self.assertNotIn('equivalent_ohms', row)

    def test_missing_physical_pair_is_rejected(self):
        db, intent = fixture()
        intent['i2c_topology']['components']['R3']['links'].pop()
        self.assertTrue(any('cover every physical pin' in e for e in validate_i2c_intent(intent, db)))

    def test_foreign_self_and_reversed_duplicate_links_are_rejected(self):
        db, original = fixture()
        for bad in [['R3.1', 'U1.1'], ['R3.1', 'R3.1'], ['R3.8', 'R3.1']]:
            intent = copy.deepcopy(original)
            intent['i2c_topology']['components']['R3']['links'].append(bad)
            with self.subTest(bad=bad):
                self.assertTrue(validate_i2c_intent(intent, db))

    def test_unverified_model_citation_and_unsupported_kind_are_rejected(self):
        db, original = fixture()
        for field, value in [('citation', ''), ('kind', 'endpoint')]:
            intent = copy.deepcopy(original)
            intent['i2c_topology']['components']['R3'][field] = value
            self.assertTrue(validate_i2c_intent(intent, db))

    def test_array_not_fitted_has_no_pullups(self):
        db, intent = fixture()
        intent['assemblies'][0]['population']['R3'] = False
        self.assertTrue(all(not row['pullups'] for row in regions(db, intent)))

    def test_unknown_population_not_inferred_from_nc_false(self):
        db, intent = fixture()
        del intent['assemblies'][0]['population']['R3']
        for row in regions(db, intent):
            self.assertFalse(row['pullups'])
            self.assertIn('population-unverified:R3', row['gaps'])

    def test_unknown_resistance_stops_every_branch(self):
        db, intent = fixture()
        db['parts']['R3']['value'] = 'UNKNOWN'
        intent['input_sha256'] = input_fingerprint(db)
        for row in regions(db, intent):
            self.assertFalse(row['pullups'])
            self.assertIn('resistance-unparsed:R3', row['gaps'])

    def test_no_array_model_is_inferred_from_eight_pins(self):
        db, intent = fixture()
        del intent['i2c_topology']['components']['R3']
        for row in regions(db, intent):
            self.assertFalse(row['pullups'])
            self.assertIn('pin-role-or-model:R3', row['gaps'])

    def test_finite_series_path_uses_each_branch_signal_node(self):
        db, intent = fixture()
        add(db, 'R4', '33R', [('1', '1', 'SDA_LOW'), ('2', '2', 'REMOTE')])
        # Source maps the second low array resistor to REMOTE in this synthetic variation.
        db['nets']['SCL_LOW'].remove('R3.7')
        db['nets'].setdefault('REMOTE', []).append('R3.7')
        db['pin2net']['R3.7'] = 'REMOTE'
        intent['assemblies'][0]['population']['R4'] = True
        intent['input_sha256'] = input_fingerprint(db)
        row = next(r for r in regions(db, intent) if 'REMOTE' in r['nets'])
        self.assertEqual(len(row['segments']), 2)
        pulls = {p['signal_net']: p for p in row['pullups']}
        self.assertEqual(set(pulls), {'SDA_LOW', 'REMOTE'})
        self.assertEqual(pulls['REMOTE']['path'], ['R4'])
        self.assertEqual(pulls['SDA_LOW']['path'], [])
        self.assertEqual(row['edges'][0]['ohms'], 33)

    def test_source_mapped_shared_common_pin_is_not_flattened(self):
        db, intent = fixture()
        cfg = intent['i2c_topology']['components']['R3']
        # Distinct low branches share a source-proven common V3 pad.
        for node in ['R3.1', 'R3.8', 'R3.3', 'R3.6', 'R3.4']:
            db['nets'][db['pin2net'][node]].remove(node)
            del db['pin2net'][node]
            del db['pinname'][node]
        cfg['links'] = [['R3.2', 'R3.7'], ['R3.2', 'R3.5']]
        cfg['citation'] = 'Synthetic equal10k commonV3 pin; not independentarray assumption'
        intent['input_sha256'] = input_fingerprint(db)
        self.assertEqual(validate_i2c_intent(intent, db), [])
        low = [r for r in regions(db, intent) if any('LOW' in n for n in r['nets'])]
        self.assertEqual(len(low), 2)
        self.assertTrue(all(len(r['pullups']) == 1 and r['pullups'][0]['ohms'] == 10000 for r in low))

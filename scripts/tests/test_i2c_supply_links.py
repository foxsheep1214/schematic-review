"""Supply-side pullup discovery; synthetic fixtures do not prove electrical PASS."""
import copy
import unittest
from unittest.mock import patch
from test_i2c_topology import add, fixture, rebind, at, regions
from i2c_topology import build_i2c_topology


def supply_fixture(value='jumper', shared=False):
    db, intent = fixture()
    for i, role in enumerate(('SDA', 'SCL'), 1):
        node, net = f'R{i}.2', f'PULL_SUPPLY_{role}'
        db['nets']['VCC_3V3'].remove(node)
        db['nets'][net] = [node]
        db['pin2net'][node] = net
        if not shared:
            ref = f'JP{i}' if value == 'jumper' else f'R{i}0'
            add(db, ref, value, [('1', '1', net), ('2', '2', 'VCC_3V3')])
            intent['i2c_topology']['components'][ref] = {'kind': 'jumper' if value == 'jumper' else 'resistor', 'citation': 'synthetic supply link'}
            intent['assemblies'][0]['population'][ref] = True
            if value == 'jumper':
                intent['assemblies'][0]['jumpers'][ref] = 'closed'
    if shared:
        add(db, 'JP1', 'three-pad bridge', [('1', '1', 'PULL_SUPPLY_SDA'), ('2', '2', 'VCC_3V3'), ('3', '3', 'PULL_SUPPLY_SCL')])
        intent['i2c_topology']['components']['JP1'] = {'kind': 'jumper', 'citation': 'synthetic independent copper pairs', 'links': [['JP1.1', 'JP1.2'], ['JP1.2', 'JP1.3']]}
        intent['assemblies'][0]['population']['JP1'] = True
        intent['assemblies'][0]['jumpers']['JP1'] = 'closed'
    rebind(db, intent)
    return db, intent


class SupplyLinkTests(unittest.TestCase):
    def test_closed_supply_jumper_finds_real_resistor_and_rail_path(self):
        db, intent = supply_fixture()
        pull = at(build_i2c_topology(db, intent))['pullups']
        self.assertEqual([(p['ref'], p['rail'], p['ohms'], p['rail_path']) for p in pull], [('R1', 'VCC_3V3', 4700, ['JP1'])])
        self.assertEqual(pull[0]['signal_net'], 'I2C_SDA')
        self.assertEqual(pull[0]['path'], [])
        self.assertNotIn('equivalent_ohms', pull[0])

    def test_shared_three_pad_supply_does_not_merge_sda_and_scl(self):
        db, intent = supply_fixture(shared=True)
        result = build_i2c_topology(db, intent)
        sda, scl = at(result), at(result, 'I2C_SCL')
        self.assertNotEqual(sda['id'], scl['id'])
        self.assertEqual([p['ref'] for p in sda['pullups']], ['R1'])
        self.assertEqual([p['ref'] for p in scl['pullups']], ['R2'])
        self.assertEqual(sda['pullups'][0]['rail_path'], ['JP1:link:0'])
        self.assertEqual(scl['pullups'][0]['rail_path'], ['JP1:link:1'])
        self.assertTrue(all('VCC_3V3' not in r['nets'] for r in regions(result)))

    def test_open_supply_jumper_is_not_a_pullup(self):
        db, intent = supply_fixture()
        intent['assemblies'][0]['jumpers']['JP1'] = 'open'
        self.assertEqual(at(build_i2c_topology(db, intent))['pullups'], [])

    def test_unknown_and_dnp_supply_link_are_not_conductive(self):
        db, intent = supply_fixture()
        for present in (None, False):
            with self.subTest(present=present):
                item = copy.deepcopy(intent)
                if present is None:
                    del item['assemblies'][0]['population']['JP1']
                else:
                    item['assemblies'][0]['population']['JP1'] = present
                result = at(build_i2c_topology(db, item))
                self.assertFalse(result['pullups'])
                if present is None:
                    self.assertIn('population:JP1', result['gaps'])

    def test_unknown_jumper_state_does_not_infer_copper(self):
        db, intent = supply_fixture()
        del intent['assemblies'][0]['jumpers']['JP1']
        result = at(build_i2c_topology(db, intent))
        self.assertFalse(result['pullups'])
        self.assertIn('jumper-state-unverified:JP1', result['gaps'])

    def test_zero_ohm_supply_link_can_trace_but_finite_link_cannot(self):
        for value, expected in [('0R', ['R1']), ('33R', ['R10'])]:
            with self.subTest(value=value):
                db, intent = supply_fixture(value)
                result = at(build_i2c_topology(db, intent))
                self.assertEqual([p['ref'] for p in result['pullups']], expected)
                if value == '33R':
                    self.assertEqual(result['pullups'][0]['path'], ['R1'])
                    self.assertEqual(result['pullups'][0]['ohms'], 33)
                    self.assertNotIn('equivalent_ohms', result)
                else:
                    self.assertNotIn('zero-ohm-to-rail:R10', result['gaps'])

    def test_ground_is_not_a_pullup_rail(self):
        db, intent = supply_fixture()
        db['nets']['GND'] = db['nets'].pop('VCC_3V3')
        for node in db['nets']['GND']:
            db['pin2net'][node] = 'GND'
        intent['i2c_topology']['rails'] = {'GND': 'synthetic ground'}
        rebind(db, intent)
        self.assertFalse(at(build_i2c_topology(db, intent))['pullups'])

    def test_unconfirmed_rail_remains_a_gap(self):
        db, intent = supply_fixture()
        intent['i2c_topology']['rails'] = {}
        result = at(build_i2c_topology(db, intent))
        self.assertEqual(result['pullups'][0]['rail_basis'], 'name-hint')
        self.assertIn('rail-identity:VCC_3V3', result['gaps'])

    def test_supply_trace_limit_is_a_gap_not_a_discovered_rail(self):
        db, intent = supply_fixture()
        with patch('i2c_topology.MAX_TRACE_NETS', 1):
            result = build_i2c_topology(db, intent)
        self.assertTrue(result['states'][0]['gaps'])
        self.assertTrue(all(not r['pullups'] for r in regions(result)))

    def test_each_supply_state_stays_independent(self):
        db, intent = supply_fixture()
        item = copy.deepcopy(intent['assemblies'][0]);item['id'] = 'off';item['jumpers']['JP1'] = 'open'
        intent['assemblies'].append(item)
        result = build_i2c_topology(db, intent)
        self.assertTrue(at(result)['pullups'])
        self.assertFalse(at(result, state='off')['pullups'])

    def test_multiple_supply_paths_are_explicit_gap_not_single_rail(self):
        db, intent = supply_fixture()
        add(db, 'JP9', 'jumper', [('1', '1', 'PULL_SUPPLY_SDA'), ('2', '2', 'VDD_5V')])
        intent['i2c_topology']['components']['JP9'] = {'kind': 'jumper', 'citation': 'synthetic alternate source'}
        intent['i2c_topology']['rails']['VDD_5V'] = 'synthetic second supply'
        intent['assemblies'][0]['population']['JP9'] = True
        intent['assemblies'][0]['jumpers']['JP9'] = 'closed'
        rebind(db, intent)
        result = at(build_i2c_topology(db, intent))
        self.assertFalse(result['pullups'])
        self.assertIn('multiple-supply-paths:R1', result['gaps'])

    def test_one_known_rail_plus_trace_limit_is_not_confirmed_multiple_rails(self):
        db, intent = supply_fixture()
        previous = 'PULL_SUPPLY_SDA'
        for i in range(8):
            ref, net = f'JP9{i}', f'ZZ_TAIL_{i}'
            add(db, ref, 'jumper', [('1', '1', previous), ('2', '2', net)])
            intent['i2c_topology']['components'][ref] = {'kind': 'jumper', 'citation': 'synthetic unresolved-length tail'}
            intent['assemblies'][0]['population'][ref] = True
            intent['assemblies'][0]['jumpers'][ref] = 'closed'
            previous = net
        rebind(db, intent)
        with patch('i2c_topology.MAX_TRACE_NETS', 6):
            result = at(build_i2c_topology(db, intent))
        self.assertIn('supply-trace-net-limit:R1', result['gaps'])
        self.assertNotIn('multiple-supply-paths:R1', result['gaps'])
        self.assertFalse(result['pullups'])
        self.assertEqual(result['coverage'], 'INCOMPLETE')


if __name__ == '__main__':
    unittest.main()

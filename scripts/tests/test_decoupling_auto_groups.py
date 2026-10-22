"""Every official supply pin of a declared device is a decoupling group (fixed requirements, step 6).

On the R5 bench one reviewer declared a decoupling group on a startup controller's HV pin and the other did not, so
four rows existed in one plan only. Each reviewer's groups matched exactly the power-role pins of their own pin map:
the difference was the pin role, and the group list repeated it by hand. The inventory now makes one group per
declared device and supply net from the official pin map (pins of one device on one net merged); the reviewer writes,
per (ref, net), only the purpose, the datasheet clauses and, where the return pins sit on several nets, the return net.
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from plan_review import build_review_plan   # before decoupling: checkers import it
import decoupling
from decoupling import Inventory, build_decoupling_inventory, validate_decoupling_intent
from test_decoupling import fixture, rebind, state
from test_i2c_topology import add

FOUR = ('PWR-T03', 'PWR-D02', 'PWR-C09', 'PWR-C10')


def board(entries=True):
    """U1 with VDD (pin 1) and VDD2 (pin 4) on VCC_3V3 and AVDD (pin 5) on AVCC."""
    db, intent = fixture(('100nF',))
    db['parts'].pop('U1')
    for node in [n for n in db['pin2net'] if n.startswith('U1.')]:
        db['nets'][db['pin2net'].pop(node)].remove(node)
    add(db, 'U1', 'TEST-IC', [('1', 'VDD', 'VCC_3V3'), ('2', 'VSS', 'GND'), ('3', 'GPIO', 'U1_IO'),
                              ('4', 'VDD2', 'VCC_3V3'), ('5', 'AVDD', 'AVCC')])
    pins = intent['devices']['U1']['pins']
    pins.update({'4': {'name': 'VDD2', 'role': 'power'}, '5': {'name': 'AVDD', 'role': 'power'}})
    intent['devices']['U1']['package'] = 'TEST-PKG-5'
    if not entries:
        intent['decoupling']['groups'] = []
    rebind(db, intent)
    return db, intent


def errors(db, intent):
    return [e for e in validate_decoupling_intent(intent, db)]


class GroupingTests(unittest.TestCase):
    def test_each_supply_net_of_a_device_is_one_group_from_the_pin_map(self):
        db, intent = board(entries=False)
        self.assertEqual(errors(db, intent), [])
        groups = {g['declared_id']: g for g in state(build_decoupling_inventory(db, intent))['groups']}
        self.assertEqual(sorted(groups), ['U1:AVCC', 'U1:VCC_3V3'])
        self.assertEqual(groups['U1:VCC_3V3']['supply_nodes'], ['U1.1', 'U1.4'])
        self.assertEqual(groups['U1:AVCC']['supply_nodes'], ['U1.5'])
        self.assertEqual(groups['U1:VCC_3V3']['return_nodes'], ['U1.2'])
        self.assertTrue(all(g['origin'] == 'declared' for g in groups.values()))

    def test_a_group_entry_gives_the_clauses_of_its_ref_and_net(self):
        db, intent = board()
        group = next(g for g in state(build_decoupling_inventory(db, intent))['groups'] if g['declared_id'] == 'U1:VCC_3V3')
        self.assertEqual([r['kind'] for r in group['requirements']], ['connection', 'capacitance', 'rating'])

    def test_a_group_without_an_entry_still_asks_its_rows_and_waits_for_the_clauses(self):
        db, intent = board(entries=False)
        plan = build_review_plan(db, intent)
        rows = [c for c in plan['checks'] if c['rule'] in FOUR and c['object'].get('net') == 'AVCC']
        self.assertEqual(sorted(c['rule'] for c in rows), sorted(FOUR))
        for row in rows:
            if row['rule'] in ('PWR-C09', 'PWR-D02'):
                self.assertTrue(any(x.startswith('datasheet-requirement:') for x in row['required_inputs']), row['id'])

    def test_entries_do_not_change_which_rows_exist(self):
        keys = lambda db, intent: sorted(c['check_key'] for c in build_review_plan(db, intent)['checks'] if c['rule'] in FOUR)
        self.assertEqual(keys(*board()), keys(*board(entries=False)))

    def test_an_entry_names_a_supply_net_of_its_device_once_and_no_derived_field(self):
        for change, word in (({'net': 'U1_IO'}, 'U1_IO'), ({'id': 'U1-VDD'}, 'derived'),
                             ({'supply_nodes': ['U1.1']}, 'derived'), ({'ref': 'C1'}, 'ref')):
            db, intent = board()
            intent['decoupling']['groups'][0].update(change)
            self.assertTrue(any(word in e for e in errors(db, intent)), (change, errors(db, intent)))
        db, intent = board()
        intent['decoupling']['groups'].append(copy.deepcopy(intent['decoupling']['groups'][0]))
        self.assertTrue(any('twice' in e for e in errors(db, intent)))

    def test_a_part_of_a_kind_without_supply_pins_is_not_grouped(self):
        db, intent = board(entries=False)
        groups = Inventory(db, intent['decoupling'], intent['devices'], {'U1': {'kind': 'connector', 'citation': 'synthetic'}}).groups()
        self.assertFalse(any(g['ref'] == 'U1' and g['origin'] == 'declared' for g in groups))

    def test_the_section_is_schema_4(self):
        self.assertEqual(decoupling.SECTION_SCHEMA_VERSION, 4)


if __name__ == '__main__':
    unittest.main()

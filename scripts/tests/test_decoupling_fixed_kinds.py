"""A decoupling group asks a fixed set of checks; the agent states only the datasheet clause (pairing follow-up).

On the R5 bench the two reviewers declared the same five decoupling groups and still paired none of their 33
requirement rows: one stated connection and capacitance, the other also a rating; each named its requirements and
worded its criteria its own way, and both entered the row identity; three groups listed different return pins
(one ground pin against all of them with the exposed pad). Now every declared group asks PWR-T03 and one PWR-D02
(connection), PWR-C09 (capacitance) and PWR-C10 (rating) row with the catalog's question; the agent's datasheet clause,
at most one per kind with its citation, rides on the row as `clause`; the return pins are every pin the official pin
map gives the return role, and a group names `return_net` only where those pins sit on more than one net.
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from plan_review import build_review_plan   # imports the checkers before decoupling (they import each other)
from decoupling import SECTION_SCHEMA_VERSION, build_decoupling_inventory, validate_decoupling_intent
from test_decoupling import fixture, group
from test_i2c_topology import add

FIXED = {'PWR-T03', 'PWR-D02', 'PWR-C09', 'PWR-C10'}


def rows(plan, ref='U1'):
    return [c for c in plan['checks'] if c['rule'] in FIXED and c['object'].get('ref') == ref
            and 'decoupling_group' in c['object']]


class FixedKindTests(unittest.TestCase):
    def test_a_group_asks_one_row_of_each_kind_however_many_clauses_it_states(self):
        db, intent = fixture()
        for kept in (('connection', 'capacitance', 'rating'), ('connection',), ()):
            declared = copy.deepcopy(intent)
            declared['decoupling']['groups'][0]['requirements'] = [
                r for r in declared['decoupling']['groups'][0]['requirements'] if r['kind'] in kept]
            got = sorted(c['rule'] for c in rows(build_review_plan(db, declared)))
            self.assertEqual(got, sorted(FIXED), kept)

    def test_the_clause_rides_on_the_row_and_its_wording_does_not_split_the_check(self):
        db, intent = fixture()
        plan = build_review_plan(db, intent)
        cap = next(c for c in rows(plan) if c['rule'] == 'PWR-C09')
        self.assertEqual(cap['clause'], {'criterion': 'synthetic capacitance requirement',
                                         'citation': 'synthetic applicable specification section capacitance'})
        self.assertNotIn('synthetic capacitance requirement', cap['criterion'] or '')
        reworded = copy.deepcopy(intent)
        for req in reworded['decoupling']['groups'][0]['requirements']:
            req.update(criterion='another reviewer reads ' + req['kind'], citation='synthetic datasheet p9 ' + req['kind'])
        other = build_review_plan(db, reworded)
        self.assertEqual({c['check_key'] for c in rows(plan)}, {c['check_key'] for c in rows(other)})
        self.assertEqual({c['id'] for c in rows(plan)}, {c['id'] for c in rows(other)})

    def test_a_missing_clause_waits_for_the_datasheet_and_a_rating_falls_back_to_the_catalog(self):
        db, intent = fixture()
        intent['decoupling']['groups'][0]['requirements'] = []
        by_rule = {c['rule']: c for c in rows(build_review_plan(db, intent))}
        self.assertIn('datasheet-requirement:capacitance', by_rule['PWR-C09']['required_inputs'])
        self.assertIn('datasheet-requirement:connection', by_rule['PWR-D02']['required_inputs'])
        self.assertNotIn('datasheet-requirement:rating', by_rule['PWR-C10']['required_inputs'])
        self.assertNotIn('clause', by_rule['PWR-C09'])

    def test_a_clause_without_its_citation_two_of_one_kind_or_a_named_clause_is_refused(self):
        db, intent = fixture()
        reqs = intent['decoupling']['groups'][0]['requirements']
        for change, word in ((lambda r: r[0].pop('citation'), 'criterion/citation'),
                             (lambda r: r.append(dict(r[0])), 'one clause per kind'),
                             (lambda r: r[0].update(id='U1-VDD-CONN'), 'unsupported fields')):
            altered = copy.deepcopy(intent)
            change(altered['decoupling']['groups'][0]['requirements'])
            errors = validate_decoupling_intent(altered, db)
            self.assertTrue(any(word in e for e in errors), (word, errors))
        self.assertTrue(reqs)


class ReturnPinTests(unittest.TestCase):
    def test_the_return_pins_are_every_official_return_pin(self):
        db, intent = fixture()
        add(db, 'U1', 'TEST-IC', [('4', 'EP', 'GND')])
        intent['devices']['U1']['pins']['4'] = {'name': 'EP', 'role': 'return'}
        from test_decoupling import rebind
        rebind(db, intent)
        self.assertEqual(validate_decoupling_intent(intent, db), [])
        self.assertEqual(group(build_decoupling_inventory(db, intent))['return_nodes'], ['U1.2', 'U1.4'])

    def test_declared_return_pins_and_an_old_section_are_refused(self):
        db, intent = fixture()
        self.assertEqual(SECTION_SCHEMA_VERSION, 3)
        declared = copy.deepcopy(intent)
        declared['decoupling']['groups'][0]['return_nodes'] = ['U1.2']
        self.assertTrue(any('unsupported fields' in e for e in validate_decoupling_intent(declared, db)))
        old = copy.deepcopy(intent)
        old['decoupling']['schema_version'] = 2
        self.assertTrue(any('schema_version must be 3' in e for e in validate_decoupling_intent(old, db)))

    def split(self):
        db, intent = fixture()
        add(db, 'U1', 'TEST-IC', [('4', 'PGND', 'PGND')])
        intent['devices']['U1']['pins']['4'] = {'name': 'PGND', 'role': 'return'}
        from test_decoupling import rebind
        rebind(db, intent)
        return db, intent

    def test_return_pins_on_two_nets_need_the_group_to_name_its_return_net(self):
        db, intent = self.split()
        self.assertTrue(any('return_net' in e for e in validate_decoupling_intent(intent, db)))
        intent['decoupling']['groups'][0]['return_net'] = 'PGND'
        self.assertEqual(validate_decoupling_intent(intent, db), [])
        self.assertEqual(group(build_decoupling_inventory(db, intent))['return_nodes'], ['U1.4'])
        intent['decoupling']['groups'][0]['return_net'] = 'VCC_3V3'
        self.assertTrue(any('return_net' in e for e in validate_decoupling_intent(intent, db)))

    def test_a_return_net_on_a_part_whose_returns_share_one_net_is_refused(self):
        db, intent = fixture()
        intent['decoupling']['groups'][0]['return_net'] = 'GND'
        self.assertTrue(any('return_net' in e for e in validate_decoupling_intent(intent, db)))


class NoCapacitorTests(unittest.TestCase):
    def test_a_no_capacitor_group_states_the_reason_as_its_clause_not_in_its_criterion(self):
        db, intent = fixture(values=())
        cfg = intent['decoupling']['groups'][0]
        cfg['purpose'] = 'no_direct_capacitor'
        cfg['requirements'] = [{'kind': 'connection', 'criterion': 'HV pin needs no bypass capacitor',
                                'citation': 'synthetic datasheet p4 HV pin'}]
        na = [c for c in rows(build_review_plan(db, intent)) if c['applicability'] == 'NOT_APPLICABLE']
        self.assertEqual(sorted(c['rule'] for c in na), ['PWR-C09', 'PWR-C10'])
        for row in na:
            self.assertNotIn('synthetic datasheet p4 HV pin', row['criterion'])
            self.assertEqual(row['clause']['citation'], 'synthetic datasheet p4 HV pin')


if __name__ == '__main__':
    unittest.main()

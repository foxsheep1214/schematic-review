"""Every plan row belongs to one owner: a circuit, a system function or the board (function-tree design, step 2).

A circuit-level row belongs to its circuit; a row about one part belongs to the circuit that owns the part (step 1);
a row of a system rule (power tree, grounds, monitoring, pin map) belongs to that system function; everything else
belongs to the board. A circuit-level row is identified by the circuit's candidate ids and its state, never by the
member list or the net spellings, so two reviews of one board that draw the same circuits ask the same checks.
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import catalog
import check_key
import circuit_decisions as cd
import row_owner
from plan_review import build_review_plan
import test_circuit_decisions as dfx


def plan_for(decisions=None):
    db, intent, audit, candidates = dfx.setup()
    intent['circuit_decisions'] = decisions or dfx.accept_all(candidates)
    intent = cd.write_circuits(intent, candidates)
    return build_review_plan(db, intent, datasheet_audit=audit, candidates=candidates), candidates


class OwnerTests(unittest.TestCase):
    def setUp(self):
        self.plan, self.candidates = plan_for()
        self.rows = {c['id']: c for c in self.plan['checks']}

    def test_every_row_has_one_owner_of_a_known_kind(self):
        kinds = {c['owner']['kind'] for c in self.plan['checks']}
        self.assertLessEqual(kinds, {'CIRCUIT', 'SYSTEM', 'BOARD'})
        circuits = {f['circuit'] for f in self.plan['functions']}
        for row in self.plan['checks']:
            if row['owner']['kind'] == 'CIRCUIT':
                self.assertIn(row['owner']['id'], circuits, row['id'])
            if row['owner']['kind'] == 'SYSTEM':
                self.assertIn(row['owner']['id'], catalog.SYSTEM_FUNCTIONS, row['id'])

    def test_a_circuit_row_belongs_to_its_circuit(self):
        for row in self.plan['checks']:
            if (row.get('object') or {}).get('circuit'):
                self.assertEqual(row['owner'], {'kind': 'CIRCUIT', 'id': row['object']['circuit']}, row['id'])

    def test_a_part_row_belongs_to_the_circuit_that_owns_the_part(self):
        def owners(plan):
            out = {}
            for row in plan['checks']:
                obj = row.get('object') or {}
                if row['rule'] in ('DEV-D02', 'DEV-D05') and set(obj) == {'ref'}:
                    out.setdefault(obj['ref'], set()).add(tuple(sorted(row['owner'].items())))
            return out
        got = owners(self.plan)
        self.assertEqual(got['U1'], {(('id', 'POWER_CONVERTER-U1'), ('kind', 'CIRCUIT'))})   # the chains only refer to it
        self.assertEqual(got['U9'], {(('id', 'POWER_PROTECTION-U1.FAULT'), ('kind', 'CIRCUIT'))})
        self.assertEqual(got['J1'], {(('id', 'POWER_PROTECTION-J1'), ('kind', 'CIRCUIT'))})
        reject = {'candidate': 'USB-J2', 'decision': 'reject', 'reason': 'OUTSIDE_SCOPE',
                  'citation': 'requirement REQ-SCOPE-01: the USB port is not delivered'}
        plan, _ = plan_for(dfx.accept_all(self.candidates, **{'USB-J2': reject}))
        self.assertEqual(owners(plan)['J2'], {(('kind', 'BOARD'),)})                    # no circuit owns it

    def test_a_system_rule_row_belongs_to_its_system_function_and_a_document_row_to_the_board(self):
        by_rule = {}
        for row in self.plan['checks']:
            by_rule.setdefault(row['rule'], set()).add(tuple(sorted(row['owner'].items())))
        self.assertEqual(by_rule['PWR-T01'], {(('id', 'SYS-POWER'), ('kind', 'SYSTEM'))})
        self.assertEqual(by_rule['PWR-T06'], {(('id', 'SYS-GROUND'), ('kind', 'SYSTEM'))})
        self.assertEqual(by_rule['DOC-V02'], {(('kind', 'BOARD'),)})

    def test_the_plan_counts_rows_per_owner_and_lists_the_parts_each_circuit_owns(self):
        counts = {(o['kind'], o.get('id')): o['rows'] for o in self.plan['summary']['owners']}
        self.assertEqual(sum(counts.values()), len(self.plan['checks']))
        self.assertGreater(counts[('CIRCUIT', 'POWER_CONVERTER-U1')], 0)
        self.assertEqual(counts[('BOARD', None)], sum(1 for c in self.plan['checks'] if c['owner']['kind'] == 'BOARD'))
        parts = {o['id']: o['parts'] for o in self.plan['owners']}
        self.assertIn('U1', parts['POWER_CONVERTER-U1'])
        self.assertNotIn('U1', parts['STARTUP-U1.HV'])

    def test_the_validator_recomputes_owners_and_refuses_a_moved_row(self):
        self.assertEqual(row_owner.errors(self.plan), [])
        moved = copy.deepcopy(self.plan)
        row = next(c for c in moved['checks'] if c['rule'] == 'DEV-D02' and c['object'] == {'ref': 'U1'})
        row['owner'] = {'kind': 'BOARD'}
        self.assertTrue(any(row['id'] in e for e in row_owner.errors(moved)), row_owner.errors(moved))
        stolen = copy.deepcopy(self.plan)
        for entry in stolen['owners']:
            if entry['id'] == 'POWER_CONVERTER-U1':
                entry['parts'].remove('U1')
        self.assertTrue(any(c['id'] in ' '.join(row_owner.errors(stolen)) for c in stolen['checks']
                            if c['object'] == {'ref': 'U1'}))
        added = copy.deepcopy(self.plan)
        added['checks'].append({'id': 'DEV-C01.U1', 'rule': 'DEV-C01', 'object': {'ref': 'U1'}})   # a reviewer's split-out row
        self.assertEqual(row_owner.errors(added), [])

class CircuitRowIdentityTests(unittest.TestCase):
    """A circuit-level row asks the same check whatever the circuit is called and however its nets are spelled."""

    def setUp(self):
        self.plan, self.candidates = plan_for()
        self.row = next(c for c in self.plan['checks'] if (c.get('object') or {}).get('circuit') == 'POWER_CONVERTER-U1'
                        and c['object'].get('state') == 'run')

    def test_the_circuit_key_is_its_candidate_ids(self):
        self.assertEqual(self.row['object']['circuit_key'], 'POWER_CONVERTER-U1')
        merge = {'candidate': ['ANALOG-U5', 'ANALOG-U4'], 'decision': 'merge', 'id': 'SENSE',
                 'citation': 'schematic p4 06_Sense: one current and voltage sense function'}
        decisions = [d for d in dfx.accept_all(self.candidates) if d['candidate'] not in ('ANALOG-U4', 'ANALOG-U5')] + [merge]
        plan, _ = plan_for(decisions)
        sense = next(c for c in plan['checks'] if (c.get('object') or {}).get('circuit') == 'SENSE')
        self.assertEqual(sense['object']['circuit_key'], 'ANALOG-U4+ANALOG-U5')

    def test_members_nets_and_the_name_do_not_enter_the_identity_state_and_candidates_do(self):
        same = copy.deepcopy(self.row)
        same['object'].update(circuit='FLYBACK', refs=same['object']['refs'][:-1], nets=['/03_Flyback/' + n for n in same['object']['nets']],
                              ref='Q1')
        self.assertEqual(check_key.key(same), check_key.key(self.row))
        for field, value in (('state', 'fault'), ('circuit_key', 'POWER_CONVERTER-U7')):
            other = copy.deepcopy(self.row)
            other['object'][field] = value
            self.assertNotEqual(check_key.key(other), check_key.key(self.row), field)

    def test_a_renamed_circuit_asks_the_same_circuit_checks(self):
        renamed = dfx.accept_all(self.candidates, **{'POWER_CONVERTER-U1': {
            'candidate': 'POWER_CONVERTER-U1', 'decision': 'accept', 'id': 'FLYBACK'}})
        plan, _ = plan_for(renamed)
        keys = lambda p: {c['check_key'] for c in p['checks']}
        self.assertEqual(keys(plan), keys(self.plan))


if __name__ == '__main__':
    unittest.main()

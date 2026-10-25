"""intent.circuits is produced from candidate decisions, never drawn: accept, merge, split, reject or add.

Every candidate gets exactly one decision; merge and split keep every member accounted for; an added circuit
takes only parts no candidate holds and names the net each part sits on; an extra working state cites a
located clause; a part belongs to at most two circuits; every part a circuit
holds is owned by exactly one circuit, and a part two candidates claim equally is owned through an `own` decision. The planner
takes the derived circuits, so a frame's objects are the candidate's members by construction.
"""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import circuit_candidates as cc
import circuit_decisions as cd
from plan_review import build_review_plan, validate_intent
import test_circuit_candidates as fx


def setup():
    db = fx.board()
    intent, audit = fx.intent_for(db)
    candidates = cc.build(db, intent, audit)
    return db, intent, audit, candidates


def accept_all(candidates, **overrides):
    decisions = [{'candidate': c['id'], 'decision': 'accept'} for c in candidates['candidates']
                 if c['id'] not in overrides]
    for cid, decision in overrides.items():
        if decision is not None:
            decisions.append(decision)
    return decisions


class DeriveTests(unittest.TestCase):
    def setUp(self):
        self.db, self.intent, self.audit, self.candidates = setup()

    def test_accepting_every_candidate_derives_one_circuit_per_candidate(self):
        circuits, errors = cd.derive(self.candidates, accept_all(self.candidates))
        self.assertEqual(errors, [])
        self.assertEqual([c['id'] for c in circuits], [c['id'] for c in self.candidates['candidates']])
        flyback = next(c for c in circuits if c['id'] == 'POWER_CONVERTER-U1')
        cand = next(c for c in self.candidates['candidates'] if c['id'] == 'POWER_CONVERTER-U1')
        self.assertEqual(flyback['refs'], sorted(m['ref'] for m in cand['members']))
        self.assertEqual(flyback['states'], ['startup', 'run', 'fault'])
        self.assertEqual(flyback['type'], 'POWER_CONVERTER')
        self.assertEqual(flyback['candidate_ids'], ['POWER_CONVERTER-U1'])
        self.assertIn('SW', flyback['nets'])
        self.assertTrue(flyback['citation'].startswith('candidate:POWER_CONVERTER-U1'))

    def test_a_display_name_changes_the_id_not_the_identity(self):
        decisions = accept_all(self.candidates, **{'POWER_CONVERTER-U1': {'candidate': 'POWER_CONVERTER-U1', 'decision': 'accept', 'id': 'FLYBACK'}})
        circuits, errors = cd.derive(self.candidates, decisions)
        self.assertEqual(errors, [])
        flyback = next(c for c in circuits if c['id'] == 'FLYBACK')
        self.assertEqual(flyback['candidate_ids'], ['POWER_CONVERTER-U1'])

    def test_merge_unites_members_and_states_and_needs_a_located_citation(self):
        merge = {'candidate': ['STARTUP-U1.HV', 'POWER_PROTECTION-U1.FAULT'], 'decision': 'merge', 'id': 'START',
                 'citation': 'U1 datasheet p12 §7.3: HV start-up and fault latch are one sequence'}
        decisions = accept_all(self.candidates, **{'STARTUP-U1.HV': merge, 'POWER_PROTECTION-U1.FAULT': None})
        circuits, errors = cd.derive(self.candidates, decisions)
        self.assertEqual(errors, [])
        start = next(c for c in circuits if c['id'] == 'START')
        self.assertEqual(start['refs'], ['C41', 'R41', 'R42', 'R43', 'U1', 'U5', 'U9'])
        self.assertEqual(start['type'], 'STARTUP')          # the first candidate's type
        self.assertEqual(start['states'], ['power-on', 'restart', 'startup', 'run', 'fault'])
        self.assertTrue(start['cross_cutting'])
        unlocated = dict(merge, citation='they belong together')
        _, errors = cd.derive(self.candidates, accept_all(self.candidates, **{'STARTUP-U1.HV': unlocated, 'POWER_PROTECTION-U1.FAULT': None}))
        self.assertTrue(any('citation' in e and 'START' in e for e in errors), errors)

    def test_merge_refuses_a_circuit_candidate_with_a_cross_cutting_one(self):
        merge = {'candidate': ['POWER_CONVERTER-U1', 'STARTUP-U1.HV'], 'decision': 'merge', 'id': 'FLY',
                 'citation': 'U1 datasheet p12 §7.3'}
        _, errors = cd.derive(self.candidates, accept_all(self.candidates, **{'POWER_CONVERTER-U1': merge, 'STARTUP-U1.HV': None}))
        self.assertTrue(any('cross-cutting' in e for e in errors), errors)

    def test_split_needs_every_member_placed_and_each_part_anchored(self):
        split = {'candidate': 'POWER_CONVERTER-U1', 'decision': 'split', 'citation': 'schematic p4 04_Flyback: aux rectifier drawn as its own block',
                 'into': [{'id': 'FLYBACK', 'members': ['U1', 'Q1', 'R1', 'R2', 'R3', 'T1', 'D2', 'C3', 'U3', 'R7']},
                          {'id': 'AUX', 'members': ['D3', 'C4']}]}
        circuits, errors = cd.derive(self.candidates, accept_all(self.candidates, **{'POWER_CONVERTER-U1': split}))
        self.assertEqual(errors, [])
        aux = next(c for c in circuits if c['id'] == 'AUX')
        self.assertEqual((aux['refs'], aux['type'], aux['candidate_ids']), (['C4', 'D3'], 'POWER_CONVERTER', ['POWER_CONVERTER-U1']))
        short = copy.deepcopy(split); short['into'][1]['members'] = ['D3']
        _, errors = cd.derive(self.candidates, accept_all(self.candidates, **{'POWER_CONVERTER-U1': short}))
        self.assertTrue(any('C4' in e and 'split' in e for e in errors), errors)
        foreign = copy.deepcopy(split); foreign['into'][1]['members'] = ['D3', 'C4', 'R99']
        _, errors = cd.derive(self.candidates, accept_all(self.candidates, **{'POWER_CONVERTER-U1': foreign}))
        self.assertTrue(any('R99' in e for e in errors), errors)

    def test_reject_needs_a_reason_and_sends_the_members_to_discovery(self):
        reject = {'candidate': 'DEBUG-BOARD', 'decision': 'reject', 'reason': 'OUTSIDE_SCOPE',
                  'citation': 'requirement REQ-SCOPE-01: test points are not delivered'}
        circuits, errors = cd.derive(self.candidates, accept_all(self.candidates, **{'DEBUG-BOARD': reject}))
        self.assertEqual(errors, [])
        self.assertNotIn('DEBUG-BOARD', [c['id'] for c in circuits])
        self.assertEqual(cd.discovery_refs(self.candidates, accept_all(self.candidates, **{'DEBUG-BOARD': reject})), ['R99', 'TP1'])
        bad = dict(reject, reason='NOT_NEEDED')
        _, errors = cd.derive(self.candidates, accept_all(self.candidates, **{'DEBUG-BOARD': bad}))
        self.assertTrue(any('reason' in e for e in errors), errors)
        duplicate = {'candidate': 'ANALOG-U4', 'decision': 'reject', 'reason': 'DUPLICATE_OF', 'of': 'POWER_CONVERTER-U1',
                     'citation': 'schematic p4: the divider is the loop'}
        _, errors = cd.derive(self.candidates, accept_all(self.candidates, **{'ANALOG-U4': duplicate}))
        self.assertTrue(any('R5' in e and 'DUPLICATE_OF' in e for e in errors), errors)   # R5 is not in the named circuit

    def test_add_takes_only_unassigned_parts_and_names_their_nets(self):
        add = {'decision': 'add', 'id': 'BLEEDER', 'type': 'POWER_PROTECTION', 'members': ['R99'],
               'via': {'R99': 'V5 bleeder to SGND'}, 'citation': 'schematic p3 05_Output: discharge resistor'}
        circuits, errors = cd.derive(self.candidates, accept_all(self.candidates) + [add])
        self.assertEqual(errors, [])
        self.assertEqual(next(c for c in circuits if c['id'] == 'BLEEDER')['candidate_ids'], [])
        # a part an add decision placed is no longer asked about
        self.assertNotIn('R99', cd.discovery_refs(self.candidates, accept_all(self.candidates) + [add]))
        self.assertIn('R99', cd.discovery_refs(self.candidates, accept_all(self.candidates)))
        held = dict(add, members=['R99', 'C7'], via={'R99': 'V5', 'C7': 'VBUS'})
        _, errors = cd.derive(self.candidates, accept_all(self.candidates) + [held])
        self.assertTrue(any('C7' in e and 'USB-J2' in e for e in errors), errors)
        blind = dict(add, via={'R99': 'somewhere'})
        _, errors = cd.derive(self.candidates, accept_all(self.candidates) + [blind])
        self.assertTrue(any('via' in e and 'R99' in e for e in errors), errors)

    def test_every_candidate_needs_exactly_one_decision(self):
        decisions = accept_all(self.candidates)[1:]
        _, errors = cd.derive(self.candidates, decisions)
        self.assertTrue(any('no decision' in e for e in errors), errors)
        _, errors = cd.derive(self.candidates, accept_all(self.candidates) + [{'candidate': 'ANALOG-U5', 'decision': 'accept'}])
        self.assertTrue(any('two decisions' in e for e in errors), errors)
        _, errors = cd.derive(self.candidates, accept_all(self.candidates) + [{'candidate': 'NOPE-X1', 'decision': 'accept'}])
        self.assertTrue(any('NOPE-X1' in e for e in errors), errors)

    def test_an_extra_state_needs_a_located_citation(self):
        decisions = accept_all(self.candidates, **{'POWER_CONVERTER-U1': {
            'candidate': 'POWER_CONVERTER-U1', 'decision': 'accept', 'states_add': ['burst'],
            'citation': 'U1 datasheet p9 Table 4: burst mode below 10 % load'}})
        circuits, errors = cd.derive(self.candidates, decisions)
        self.assertEqual(errors, [])
        self.assertEqual(next(c for c in circuits if c['id'] == 'POWER_CONVERTER-U1')['states'], ['startup', 'run', 'fault', 'burst'])
        decisions = accept_all(self.candidates, **{'POWER_CONVERTER-U1': {
            'candidate': 'POWER_CONVERTER-U1', 'decision': 'accept', 'states_add': ['burst'], 'citation': 'it has burst mode'}})
        _, errors = cd.derive(self.candidates, decisions)
        self.assertTrue(any('burst' in e for e in errors), errors)

    def test_a_part_two_circuits_claim_equally_needs_an_owner_and_three_circuits_are_refused(self):
        add = {'decision': 'add', 'id': 'X', 'type': 'ANALOG', 'members': ['R99'], 'via': {'R99': 'V5'}, 'citation': 'p1'}
        twice = [dict(add), dict(add, id='Y')]
        _, errors = cd.derive(self.candidates, accept_all(self.candidates) + twice)
        self.assertTrue(any('R99' in e and 'claimed equally' in e for e in errors), errors)
        _, errors = cd.derive(self.candidates, accept_all(self.candidates) + twice + [dict(add, id='Z')])
        self.assertTrue(any('R99' in e and 'at most two' in e for e in errors), errors)



def owned_by(circuits):
    out = {}
    for circuit in circuits:
        for ref in circuit['owned']:
            out.setdefault(ref, []).append(circuit['id'])
    return out


def shared_board():
    db = fx.board()
    fx.fixture.add(db, 'U8', 'OPAMP', [('1', 'VDD', 'V5'), ('2', 'GND', 'SGND'), ('3', 'IN', 'SHARED_IN'), ('4', 'OUT', 'OPA_OUT')])
    fx.fixture.add(db, 'R20', '1K', [('1', '1', 'SHARED_IN'), ('2', '2', 'ISNS_P')])
    intent, audit = fx.intent_for(db, kinds=dict(fx.KINDS, U8='opamp_comparator'))
    return cc.build(db, intent, audit)


OWN_R20 = {'decision': 'own', 'ref': 'R20', 'candidate': 'ANALOG-U5',
           'citation': 'schematic p4 06_Sense: R20 sets the U5 sense gain'}


class OwnershipTests(unittest.TestCase):
    """A derived circuit lists what it owns (`owned`) beside every part it holds (`refs`); each held part has one owner."""

    def setUp(self):
        self.db, self.intent, self.audit, self.candidates = setup()

    def test_accepted_circuits_own_what_their_candidates_own(self):
        circuits, errors = cd.derive(self.candidates, accept_all(self.candidates))
        self.assertEqual(errors, [])
        owners = owned_by(circuits)
        self.assertEqual({ref: v for ref, v in owners.items() if len(v) != 1}, {})
        self.assertEqual(sorted({ref for c in circuits for ref in c['refs']}), sorted(owners))
        band = next(c for c in circuits if c['id'] == 'ISOLATION-PRI/SEC')
        self.assertEqual(band['owned'], ['CY1'])
        self.assertIn('T1', band['refs'])                       # held for the band's own judgement, owned by the converter
        self.assertEqual(owners['T1'], ['POWER_CONVERTER-U1'])

    def test_a_shared_part_is_owned_through_an_own_decision_with_a_located_citation(self):
        candidates = shared_board()
        _, errors = cd.derive(candidates, accept_all(candidates))
        self.assertTrue(any('R20' in e and 'own' in e for e in errors), errors)
        circuits, errors = cd.derive(candidates, accept_all(candidates) + [OWN_R20])
        self.assertEqual(errors, [])
        self.assertEqual(owned_by(circuits)['R20'], ['ANALOG-U5'])
        self.assertIn('R20', next(c for c in circuits if c['id'] == 'ANALOG-U8')['refs'])
        for bad, word in ((dict(OWN_R20, citation='it is closer'), 'citation'),
                          (dict(OWN_R20, candidate='USB-J2'), 'USB-J2'),
                          (dict(OWN_R20, ref='R14'), 'R14')):
            _, errors = cd.derive(candidates, accept_all(candidates) + [bad])
            self.assertTrue(any(word in e for e in errors), (bad, errors))
        _, errors = cd.derive(candidates, accept_all(candidates) + [OWN_R20, dict(OWN_R20, candidate='ANALOG-U8')])
        self.assertTrue(any('R20' in e and 'two' in e for e in errors), errors)

    def test_merge_and_split_keep_one_owner_per_part(self):
        merge = {'candidate': ['ANALOG-U4', 'ANALOG-U5'], 'decision': 'merge', 'id': 'SENSE',
                 'citation': 'schematic p4 06_Sense: one current and voltage sense function'}
        decisions = [d for d in accept_all(self.candidates) if d['candidate'] not in ('ANALOG-U4', 'ANALOG-U5')] + [merge]
        circuits, errors = cd.derive(self.candidates, decisions)
        self.assertEqual(errors, [])
        self.assertEqual(next(c for c in circuits if c['id'] == 'SENSE')['owned'], ['R14', 'R15', 'R5', 'R6', 'U4', 'U5'])
        split = {'candidate': 'POWER_CONVERTER-U7', 'decision': 'split', 'citation': 'U7 datasheet p12 Figure 9',
                 'into': [{'id': 'BUCK-POWER', 'members': ['U7', 'L2', 'C10']}, {'id': 'BUCK-FB', 'members': ['R11', 'R12']}]}
        circuits, errors = cd.derive(self.candidates, accept_all(self.candidates, **{'POWER_CONVERTER-U7': split}))
        self.assertEqual(errors, [])
        parts = {c['id']: c['owned'] for c in circuits if c['id'].startswith('BUCK-')}
        self.assertEqual(parts, {'BUCK-POWER': ['C10', 'L2', 'U7'], 'BUCK-FB': ['R11', 'R12']})

    def test_a_duplicate_hands_what_it_owns_to_the_circuit_it_duplicates(self):
        candidates = copy.deepcopy(self.candidates)
        converter = next(c for c in candidates['candidates'] if c['id'] == 'POWER_CONVERTER-U1')
        next(m for m in converter['members'] if m['ref'] == 'R1')['owned'] = False
        candidates['candidates'].append({'id': 'ANALOG-R1', 'type': 'ANALOG', 'anchor': 'R1', 'domain': 'PRI',
                                         'cross_cutting': False, 'nets': {}, 'states': ['run', 'fault'], 'pages': [],
                                         'members': [{'ref': 'R1', 'role': 'resistor', 'via': 'synthetic', 'owned': True}]})
        duplicate = {'candidate': 'ANALOG-R1', 'decision': 'reject', 'reason': 'DUPLICATE_OF', 'of': 'POWER_CONVERTER-U1',
                     'citation': 'schematic p2: R1 is the converter current sense'}
        circuits, errors = cd.derive(candidates, accept_all(candidates, **{'ANALOG-R1': duplicate}))
        self.assertEqual(errors, [])
        self.assertEqual(owned_by(circuits)['R1'], ['POWER_CONVERTER-U1'])

    def test_a_candidate_file_with_two_owners_or_no_ownership_is_refused(self):
        candidates = copy.deepcopy(self.candidates)
        band = next(c for c in candidates['candidates'] if c['id'] == 'ISOLATION-PRI/SEC')
        next(m for m in band['members'] if m['ref'] == 'T1')['owned'] = True
        _, errors = cd.derive(candidates, accept_all(candidates))
        self.assertTrue(any('T1' in e and 'owned by two' in e for e in errors), errors)
        old = copy.deepcopy(self.candidates)
        for cand in old['candidates']:
            for m in cand['members']:
                m.pop('owned')
        old['schema_version'] = 1
        self.assertTrue(any('schema_version 2' in e for e in cd.validate(cd.write_circuits(
            dict(self.intent, circuit_decisions=accept_all(old)), old), old, self.db)))

    def test_hand_written_ownership_that_differs_from_the_decisions_is_refused(self):
        intent = cd.write_circuits(dict(self.intent, circuit_decisions=accept_all(self.candidates)), self.candidates)
        band = next(c for c in intent['circuits'] if c['id'] == 'ISOLATION-PRI/SEC')
        band['owned'] = ['CY1', 'T1']
        errors = cd.validate(intent, self.candidates, self.db)
        self.assertTrue(any('ISOLATION-PRI/SEC' in e and 'owned' in e for e in errors), errors)


class IntentTests(unittest.TestCase):
    def setUp(self):
        self.db, self.intent, self.audit, self.candidates = setup()
        self.intent['circuit_decisions'] = accept_all(self.candidates)

    def test_write_fills_intent_circuits_and_validate_accepts_them(self):
        intent = cd.write_circuits(self.intent, self.candidates)
        self.assertEqual(len(intent['circuits']), len(self.candidates['candidates']))
        self.assertEqual(cd.validate(intent, self.candidates, self.db), [])
        self.assertEqual(validate_intent(intent, self.db, candidates=self.candidates), [])

    def test_hand_drawn_circuits_that_differ_from_the_decisions_are_refused(self):
        intent = cd.write_circuits(self.intent, self.candidates)
        intent['circuits'][0]['refs'].append('R99')
        errors = cd.validate(intent, self.candidates, self.db)
        self.assertTrue(any('R99' in e and intent['circuits'][0]['id'] in e for e in errors), errors)
        intent = cd.write_circuits(self.intent, self.candidates)
        del intent['circuits'][0]
        self.assertTrue(any('missing' in e for e in cd.validate(intent, self.candidates, self.db)))

    def test_circuits_without_decisions_or_a_stale_candidate_file_are_refused(self):
        intent = cd.write_circuits(self.intent, self.candidates)
        del intent['circuit_decisions']
        self.assertTrue(any('circuit_decisions' in e for e in cd.validate(intent, self.candidates, self.db)))
        stale = dict(self.candidates, db_sha256='0' * 64)
        self.assertTrue(any('db_sha256' in e for e in cd.validate(cd.write_circuits(self.intent, stale), stale, self.db)))
        self.assertTrue(any('circuit-candidates' in e for e in validate_intent(intent, self.db)))   # circuits need the file

    def test_the_plan_frames_each_derived_circuit_on_the_candidate_members(self):
        intent = cd.write_circuits(self.intent, self.candidates)
        plan = build_review_plan(self.db, intent, datasheet_audit=self.audit, candidates=self.candidates)
        frames = {f['circuit']: f for f in plan['functions'] if f.get('circuit')}
        cand = next(c for c in self.candidates['candidates'] if c['id'] == 'POWER_CONVERTER-U1')
        self.assertEqual(frames['POWER_CONVERTER-U1']['objects']['refs'], sorted(m['ref'] for m in cand['members']))
        self.assertEqual(plan['circuit_candidates']['unassigned'], ['R99'])
        discovery = next(x for x in plan['checks'] if x['rule'] == 'REQ-Q08')
        self.assertIn('R99', discovery['criterion'])
        self.assertEqual(discovery['object']['unassigned'], ['R99'])

    def test_cli_writes_circuits_into_the_intent_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / 'intent.json').write_text(json.dumps(self.intent), encoding='utf-8')
            (tmp / 'circuit-candidates.json').write_text(json.dumps(self.candidates), encoding='utf-8')
            code = cd.main([str(tmp / 'intent.json'), str(tmp / 'circuit-candidates.json'), '--write'])
            self.assertEqual(code, 0)
            written = json.loads((tmp / 'intent.json').read_text(encoding='utf-8'))
            self.assertEqual(len(written['circuits']), len(self.candidates['candidates']))
            self.assertEqual(cd.main([str(tmp / 'intent.json'), str(tmp / 'circuit-candidates.json')]), 0)


if __name__ == '__main__':
    unittest.main()


class OwnedMemberTests(unittest.TestCase):
    """R6 acceptance 2026-10-24, codex1 SR-02: a rejected STARTUP chain's controller is owned by its accepted converter
    and is not asked about again on REQ-Q08."""

    def test_a_rejected_candidate_member_held_by_an_accepted_one_is_not_unassigned(self):
        _, _, _, candidates = setup()
        anchor = next(c for c in candidates['candidates'] if c['id'] == 'POWER_CONVERTER-U1')
        shared = anchor['members'][0]['ref']
        extra = {'id': 'STARTUP-X', 'type': 'STARTUP', 'members': [{'ref': shared, 'role': 'anchor'}, {'ref': 'R77', 'role': 'sense'}],
                 'nets': [], 'states': ['run'], 'cross_cutting': False}
        candidates = dict(candidates, candidates=candidates['candidates'] + [extra])
        reject = {'candidate': 'STARTUP-X', 'decision': 'reject', 'reason': 'NOT_A_CIRCUIT', 'citation': 'schematic p2: the divider is the converter\'s own'}
        refs = cd.discovery_refs(candidates, accept_all(candidates, **{'STARTUP-X': reject}))
        self.assertIn('R77', refs)
        self.assertNotIn(shared, refs)

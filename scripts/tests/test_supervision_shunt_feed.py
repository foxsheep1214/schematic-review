"""Synthetic single resistive feed provenance; no real board or OEM document fixture."""
import copy
import hashlib
import json
import pathlib
import sys
import tempfile
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import board_intent
from checkers import supervision as sv
from checkers import states
from checkers.powertree import PowerTree
from checkers.netgraph import NetGraph
from plan_review import build_review_plan
from test_inductive_load import add
from electrical_fixtures import bound_intent


def board():
    db = {'parts': {}, 'nets': {}, 'pin2net': {}, 'pinname': {}, 'pintype': {},
          'pseudo_nets': ['unconnected-P1.4'], 'no_connect_nodes': ['P1.4']}
    add(db, 'P1', 'Connector:Conn_01x04', [('1', 'VIN', 'VBUS'), ('2', 'GND', 'GND'),
        ('3', 'VIN', 'VBUS'), ('4', 'UNUSED', 'unconnected-P1.4')])
    add(db, 'R1', 'RES', [('1', '1', 'VBUS'), ('2', '2', 'VDD')])
    db['parts']['R1']['value'] = '680R 1% 1W'
    add(db, 'U1', 'SYNTH-SHUNT', [('1', 'VDD', 'VDD'), ('2', 'GND', 'GND'), ('3', 'CTL', 'CTL')])
    complete(db)
    return db


def complete(db):
    db['native_pintype'] = {n: ('power_in' if n.startswith('U1.') and n[-1] in ('1', '2')
        else 'input' if n == 'U1.3' else 'passive') for n in db['pin2net']}
    db['declared_native_pintype'] = dict(db['native_pintype'])
    db['declared_pinname'] = dict(db['pinname'])
    db['pintype'] = {n: ('PWR' if t == 'power_in' else 'IN' if t == 'input' else 'UNSPEC')
                     for n, t in db['native_pintype'].items()}
    db['declared_pintype'] = dict(db['pintype'])


def make_intent(db, document):
    i = bound_intent(db, state='A')
    i['assemblies'].append(dict(copy.deepcopy(i['assemblies'][0]), id='B'))
    i['power_sources'] = [{'node': 'P1.1', 'states': ['A', 'B'], 'citation': 'Synthetic external source scope REV1'}]
    i['supervision'] = {'schema_version': 2, 'supervisors': [], 'rail_requirements': []}
    g = sv._Scan(board_intent.graph_db(db, i), states.resolve(db, i['assemblies'])[0], {}, set()).graph
    part = lambda ref: {k: db['parts'][ref].get(k, '') for k in sv.PART_IDENTITY_FIELDS}
    for state in ('A', 'B'):
        i['supervision']['rail_requirements'].append({'net': 'VDD', 'state': state, 'required': False,
            'criterion': 'Synthetic controlled requirement: operator checks source before use; no autonomous VDD monitor.',
            'citation': 'Synthetic requirements REV1 section4, this rail and assembly only',
            'identity': {'source_node': 'U1.1', 'source_role': 'internal_shunt_feed',
                'part': part('U1'), 'pin_name': 'VDD',
                'native_pintypes': {n: t for n, t in db['native_pintype'].items() if n.startswith('U1.')},
                'citation': 'Synthetic OEM shunt receiver mapping',
                'feed_provenance': {'upstream_node': 'P1.1', 'upstream_part': part('P1'),
                    'upstream_pins': sv._physical_snapshot(g, 'P1'),
                    'receiver_pins': sv._physical_snapshot(g, 'U1'),
                    'feed': {'ref': 'R1', 'from_node': 'R1.1', 'to_node': 'R1.2', 'part': part('R1'),
                        'pins': sv._physical_snapshot(g, 'R1'), 'resistance_ohm_exact': '680'},
                    'receiver_source': {'path': str(document), 'sha256': hashlib.sha256(document.read_bytes()).hexdigest(),
                        'format': 'text', 'publisher': 'Synthetic manufacturer fixture',
                        'source_url': 'https://example.test/synthetic-shunt', 'document_model': 'SYNTH-SHUNT',
                        'document_version': 'REV1', 'role_page': 1, 'pin_page': 1,
                        'identity_quote': 'SYNTH-SHUNT electrical characteristics',
                        'role_quote': 'Internal shunt regulated rail VDD',
                        'pin_quote': '1 VDD power input', 'citation': 'Synthetic source role and pin passages read'},
                    'citation': 'Actual single resistor feed, identity only'}}})
    return i


class ShuntFeedTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.doc = pathlib.Path(self.tmp.name) / 'synthetic-manufacturer.txt'
        self.doc.write_text('SYNTH-SHUNT electrical characteristics REV1\nInternal shunt regulated rail VDD\n1 VDD power input\n')
        self.db = board()
        self.intent = make_intent(self.db, self.doc)

    def errors(self):
        return sv.validate_supervision_intent(self.intent, self.db)

    def assert_rejected(self, reason):
        errors = self.errors()
        self.assertTrue(any(reason in x for x in errors), errors)
        inv = sv.build_inventory(self.db, self.intent)
        rails = [r for s in inv['states'] for r in s['rails'] if r['net'] == 'VDD']
        self.assertTrue(rails)
        self.assertTrue(all(not r.get('scope_qualified') for r in rails))

    def test_real_power_in_and_nonzero_feed_qualify_only_provenance(self):
        self.assertEqual(self.errors(), [])
        inv = sv.build_inventory(self.db, self.intent)
        for state in inv['states']:
            rail = next(r for r in state['rails'] if r['net'] == 'VDD')
            self.assertTrue(rail['scope_qualified'])
            self.assertEqual(rail['gaps'], [])
            self.assertIn('rail-identity:VDD', rail['observation_gaps'])
            self.assertIn('rail-unmonitored:VDD', rail['observation_gaps'])
            path = rail['source_path'][0]
            self.assertEqual(path['resistance_ohm_exact'], '680')
            self.assertEqual(path['receiver_native_type'], 'power_in')
            self.assertFalse(path['electrical_equivalence'])
            self.assertFalse(path['performance_guarantee'])
        self.assertEqual(sv.build_inventory(self.db, inv['context']), inv)
        graph = sv._Scan(self.db, states.resolve(self.db, self.intent['assemblies'])[0], {}, set()).graph
        self.assertIsNone(PowerTree(graph, self.intent).source_of('VDD'))
        plan = build_review_plan(self.db, self.intent)
        for check in plan['checks']:
            if check['rule'] == 'PWR-T04':
                self.assertEqual(check['readiness'], 'WAITING_EVIDENCE')
                self.assertIsNone(check.get('review_result'))
        self.assertEqual(self.db['native_pintype']['U1.1'], 'power_in')

    def test_same_connector_parallel_supply_contacts_are_not_independent_sources(self):
        self.intent['power_sources'].append({'node': 'P1.3', 'states': ['A', 'B'], 'citation': 'Same connector source contacts'})
        self.assertEqual(self.errors(), [])

    def test_required_monitor_and_other_state_not_waived(self):
        self.intent['supervision']['rail_requirements'][0]['required'] = True
        p = build_review_plan(self.db, self.intent)
        checks = {x['object']['state']: x for x in p['checks'] if x['rule'] == 'PWR-T04'}
        self.assertIn('rail-unmonitored:VDD', checks['A']['inventory_gaps'])
        self.assertNotIn('rail-unmonitored:VDD', checks['B']['inventory_gaps'])

    def test_source_document_changed_same_length_and_false_quotes_rejected(self):
        self.doc.write_text(self.doc.read_text().replace('shunt', 'other'))
        self.assert_rejected('hash mismatch')
        for item in self.intent['supervision']['rail_requirements']:
            item['identity']['feed_provenance']['receiver_source']['sha256'] = hashlib.sha256(self.doc.read_bytes()).hexdigest()
        self.assert_rejected('role quote')

    def test_receiver_document_identity_pin_page_and_metadata_mutations(self):
        for field, value, reason in [('identity_quote', 'ANOTHER-MODEL electrical characteristics', 'identity quote'),
                ('role_quote', 'Internal shunt regulated rail WRONG', 'role quote'),
                ('pin_quote', '2 VDD power input', 'physical pin quote'), ('pin_page', 2, 'physical pin quote'),
                ('citation', '', 'metadata'), ('document_version', '', 'metadata'), ('sha256', '0'*64, 'hash mismatch')]:
            with self.subTest(field=field):
                original = copy.deepcopy(self.intent)
                for item in self.intent['supervision']['rail_requirements']:
                    item['identity']['feed_provenance']['receiver_source'][field] = value
                self.assert_rejected(reason)
                self.intent = original

    def test_no_native_type_or_declaration_rewrite_can_promote_receiver(self):
        for fields in [('native_pintype',), ('declared_native_pintype',),
                       ('native_pintype', 'declared_native_pintype')]:
            with self.subTest(fields=fields):
                db = copy.deepcopy(self.db);i = copy.deepcopy(self.intent)
                for field in fields:
                    self.db[field]['U1.1'] = 'power_out'
                # Rebind all physical snapshots and the input, so rejection is
                # the real receiver role, not a stale snapshot shortcut.
                self.intent = make_intent(self.db, self.doc)
                self.assert_rejected('receiver')
                self.db, self.intent = db, i

    def test_complete_snapshot_wrong_name_pin_net_and_part(self):
        for key in ('upstream_part', 'upstream_pins', 'receiver_pins'):
            with self.subTest(key=key):
                original = copy.deepcopy(self.intent)
                for item in self.intent['supervision']['rail_requirements']:
                    item['identity']['feed_provenance'][key] = {}
                self.assert_rejected('mismatch' if key.startswith('upstream') else 'receiver')
                self.intent = original
        for item in self.intent['supervision']['rail_requirements']:
            item['identity']['source_node'] = 'U1.3'
        self.assert_rejected('receiver')

    def test_feed_value_exact_positive_and_full_native_text(self):
        for value in ('0R', '-1R', 'UNKNOWN', '680x', 'NaN', 'Inf', '680R junk 1W',
                      '0.' + '0'*400 + '1R'):
            with self.subTest(value=value):
                db, intent = copy.deepcopy(self.db), copy.deepcopy(self.intent)
                self.db['parts']['R1']['value'] = value
                self.intent = make_intent(self.db, self.doc)
                self.assert_rejected('resistance')
                self.db, self.intent = db, intent
        self.db['parts']['R1']['value'] = '1K2 1% 0.25W'
        self.intent = make_intent(self.db, self.doc)
        for item in self.intent['supervision']['rail_requirements']:
            item['identity']['feed_provenance']['feed']['resistance_ohm_exact'] = '1200'
        self.assertEqual(self.errors(), [])

    def test_dnp_source_receiver_feed_state_cannot_inherit(self):
        for ref in ('P1', 'U1', 'R1'):
            with self.subTest(ref=ref):
                original = copy.deepcopy(self.intent)
                self.intent['assemblies'][0]['population'][ref] = False
                self.assertTrue(any('DNP' in x or 'absent' in x for x in self.errors()))
                inv = sv.build_inventory(self.db, self.intent)
                b = next(x for x in inv['states'] if x['id'] == 'B')
                self.assertTrue(next(r for r in b['rails'] if r['net'] == 'VDD')['scope_qualified'])
                self.intent = original

    def test_stale_source_state_and_missing_citation(self):
        self.intent['power_sources'][0]['states'] = ['B']
        self.assertTrue(any('not declared in this state' in x for x in self.errors()))
        self.intent['power_sources'][0]['states'] = ['A', 'B']
        self.intent['input_sha256'] = 'stale'
        self.assert_rejected('stale')

    def test_nc_only_unused_contact_isolated_pseudo_with_complete_declaration(self):
        for mut in ('selected-NC', 'unused-real-net', 'missing-declared-pin'):
            with self.subTest(mut=mut):
                db, i = copy.deepcopy(self.db), copy.deepcopy(self.intent)
                if mut == 'selected-NC':
                    self.db['no_connect_nodes'].append('P1.1')
                elif mut == 'unused-real-net':
                    self.db['pin2net']['P1.4'] = 'VBUS'
                    self.db['nets']['unconnected-P1.4'].remove('P1.4')
                    self.db['nets']['VBUS'].append('P1.4')
                else:
                    self.db['declared_pinname'].pop('P1.4')
                self.intent = make_intent(self.db, self.doc)
                self.assert_rejected('upstream')
                self.db, self.intent = db, i

    def test_parallel_and_serial_bypass_and_independent_source_rejected(self):
        for mode in ('parallel', 'serial', 'source'):
            with self.subTest(mode=mode):
                db, intent = copy.deepcopy(self.db), copy.deepcopy(self.intent)
                if mode == 'source':
                    add(self.db, 'P2', 'Connector:Conn_01x02', [('1', 'VIN', 'VBUS'), ('2', 'GND', 'GND')])
                else:
                    add(self.db, 'R2', 'RES', [('1', '1', 'VBUS'), ('2', '2', 'VDD' if mode == 'parallel' else 'FEED_MID')])
                    self.db['parts']['R2']['value'] = '1K'
                    if mode == 'serial':
                        add(self.db, 'R3', 'RES', [('1', '1', 'FEED_MID'), ('2', '2', 'VDD')])
                        self.db['parts']['R3']['value'] = '2K'
                complete(self.db)
                self.intent = make_intent(self.db, self.doc)
                if mode == 'source':
                    self.intent['power_sources'].append({'node': 'P2.1', 'states': ['A', 'B'],
                        'citation': 'Synthetic controlled state: independent external source on second port'})
                self.assert_rejected('independently declared source' if mode == 'source' else 'bypass path')
                self.db, self.intent = db, intent

    def test_normal_receiver_load_branch_is_not_extra_feed(self):
        add(self.db, 'R2', 'RES', [('1', '1', 'VDD'), ('2', '2', 'CTL')])
        self.db['parts']['R2']['value'] = '47K'
        complete(self.db)
        self.intent = make_intent(self.db, self.doc)
        self.assertEqual(self.errors(), [])

    def test_output_connector_without_external_source_state_is_not_invented_multisource(self):
        add(self.db, 'P3', 'Connector:Conn_01x02', [('1', 'OUT', 'VDD'), ('2', 'GND', 'GND')])
        complete(self.db)
        self.intent = make_intent(self.db, self.doc)
        self.assertEqual(self.errors(), [])

    def test_mutually_equal_normalized_fields_still_cannot_conflict_with_native_role(self):
        for node, expected in [('P1.1', 'upstream'), ('U1.1', 'receiver')]:
            with self.subTest(node=node):
                db, i = copy.deepcopy(self.db), copy.deepcopy(self.intent)
                self.db['pintype'][node] = 'OUT'
                self.db['declared_pintype'][node] = 'OUT'
                self.intent = make_intent(self.db, self.doc)
                self.assert_rejected(expected)
                self.db, self.intent = db, i

    def test_missing_or_malformed_feed_provenance_never_crashes_or_qualifies(self):
        for value in (None, [], '', {}, {'upstream_node': []}):
            with self.subTest(value=value):
                i = copy.deepcopy(self.intent)
                for item in i['supervision']['rail_requirements']:
                    item['identity']['feed_provenance'] = value
                self.assertTrue(sv.validate_supervision_intent(i, self.db))
        for value in (None, [], '', {}, {'path': 'not-complete'}):
            with self.subTest(receiver_source=value):
                i = copy.deepcopy(self.intent)
                for item in i['supervision']['rail_requirements']:
                    item['identity']['feed_provenance']['receiver_source'] = value
                self.assertTrue(sv.validate_supervision_intent(i, self.db))

    def test_second_model_refs_and_positive_resistance_are_generic(self):
        def replace(obj):
            return json.loads(json.dumps(obj).replace('SYNTH-SHUNT', 'ALT-SHUNT-42')
                .replace('U1', 'U42').replace('P1', 'J8').replace('R1', 'R91')
                .replace('680R', '1K6').replace('"680"', '"1600"'))
        self.db, self.intent = replace(self.db), replace(self.intent)
        self.doc.write_text(self.doc.read_text().replace('SYNTH-SHUNT', 'ALT-SHUNT-42'))
        self.intent['input_sha256'] = board_intent.input_fingerprint(self.db)
        for item in self.intent['supervision']['rail_requirements']:
            item['identity']['feed_provenance']['receiver_source']['sha256'] = hashlib.sha256(self.doc.read_bytes()).hexdigest()
        self.assertEqual(self.errors(), [])
        inv = sv.build_inventory(self.db, self.intent)
        for state in inv['states']:
            rail = next(r for r in state['rails'] if r['net'] == 'VDD')
            self.assertEqual(rail['source_path'][0]['ref'], 'R91')
            self.assertEqual(rail['source_path'][0]['resistance_ohm_exact'], '1600')
            self.assertEqual(rail['source_path'][0]['receiver_node'], 'U42.1')

    def test_feed_endpoint_reversal_and_wrong_exact_resistance_rejected(self):
        for mode in ('reversed', 'wrong-resistance', 'wrong-source-net'):
            with self.subTest(mode=mode):
                i = copy.deepcopy(self.intent)
                for item in i['supervision']['rail_requirements']:
                    proof = item['identity']['feed_provenance']
                    if mode == 'reversed':
                        proof['feed']['from_node'], proof['feed']['to_node'] = 'R1.2', 'R1.1'
                    elif mode == 'wrong-resistance':
                        proof['feed']['resistance_ohm_exact'] = '681'
                    else:
                        proof['upstream_node'] = 'P1.2'
                self.assertTrue(sv.validate_supervision_intent(i, self.db))

    def test_unknown_upstream_source_state_or_citation_rejected_without_crash(self):
        for value in (None, {}, [{}], [{'node': 'P1.1', 'states': None, 'citation': 'unknown state'}],
                      [{'node': 'P1.1', 'states': ['A', 'B'], 'citation': ''}],
                      [{'node': 'P99.1', 'states': ['A', 'B'], 'citation': 'wrong node'}]):
            with self.subTest(value=value):
                i = copy.deepcopy(self.intent)
                i['power_sources'] = value
                self.assertTrue(sv.validate_supervision_intent(i, self.db))

    def test_legacy_roles_do_not_gain_new_passive_nc_or_nonzero_feed_exception(self):
        for role, node in [('external_supply', 'P1.1'), ('rail_driver', 'U1.1'),
                           ('upstream_external_supply', 'P1.1')]:
            i = copy.deepcopy(self.intent)
            for item in i['supervision']['rail_requirements']:
                identity = item['identity'];identity.pop('feed_provenance')
                ref = node.split('.')[0]
                identity.update(source_node=node, source_role=role, pin_name=self.db['pinname'][node],
                    part={k: self.db['parts'][ref].get(k, '') for k in sv.PART_IDENTITY_FIELDS},
                    native_pintypes={n: t for n, t in self.db['native_pintype'].items() if n.startswith(ref+'.')})
            self.assertTrue(sv.validate_supervision_intent(i, self.db))

    def test_remote_independent_source_through_finite_resistor_or_chain(self):
        for mode in ('resistor', 'chain', 'forward-diode', 'native-power-out', 'native-output'):
            with self.subTest(mode=mode):
                self.db = board()
                add(self.db, 'P2', 'Connector:Conn_01x02', [('1', 'VIN', 'VIN2'), ('2', 'GND', 'GND')])
                if mode == 'forward-diode':
                    add(self.db, 'D2', 'DIODE', [('1', 'A', 'VIN2'), ('2', 'K', 'VDD')])
                else:
                    add(self.db, 'R2', 'RES', [('1', '1', 'VIN2'), ('2', '2', 'MID' if mode == 'chain' else 'VDD')])
                    self.db['parts']['R2']['value'] = '330R'
                    if mode == 'chain':
                        add(self.db, 'D2', 'DIODE', [('1', 'A', 'MID'), ('2', 'K', 'VDD')])
                complete(self.db)
                if mode.startswith('native-'):
                    t = 'power_out' if mode == 'native-power-out' else 'output'
                    self.db['native_pintype']['P2.1'] = self.db['declared_native_pintype']['P2.1'] = t
                    self.db['pintype']['P2.1'] = self.db['declared_pintype']['P2.1'] = 'POWER_OUT' if t == 'power_out' else 'OUT'
                self.intent = make_intent(self.db, self.doc)  # actual changed graph, full rebound
                if not mode.startswith('native-'):
                    self.intent['power_sources'].append({'node': 'P2.1', 'states': ['A', 'B'], 'citation': 'Independent energized source'})
                self.assert_rejected('supported source' if mode.startswith('native-') else 'independently declared source')
                self.assertFalse(any('stale' in e for e in self.errors()))

    def test_remote_source_state_and_dnp_are_resolved_before_reachability(self):
        add(self.db, 'P2', 'Connector:Conn_01x02', [('1', 'VIN', 'VIN2'), ('2', 'GND', 'GND')])
        add(self.db, 'R2', 'RES', [('1', '1', 'VIN2'), ('2', '2', 'VDD')]);self.db['parts']['R2']['value'] = '330R'
        complete(self.db);self.intent = make_intent(self.db, self.doc)
        self.intent['power_sources'].append({'node': 'P2.1', 'states': ['A'], 'citation': 'Only assembly A energized'})
        inv = sv.build_inventory(self.db, self.intent)
        self.assertFalse(next(r for r in inv['states'][0]['rails'] if r['net'] == 'VDD')['scope_qualified'])
        self.assertTrue(next(r for r in inv['states'][1]['rails'] if r['net'] == 'VDD')['scope_qualified'])
        self.intent['assemblies'][0]['population']['R2'] = False
        self.assertEqual(self.errors(), [])

    def test_reverse_diode_and_unenergized_output_port_do_not_invent_source(self):
        add(self.db, 'P2', 'Connector:Conn_01x02', [('1', 'OUT', 'VIN2'), ('2', 'GND', 'GND')])
        add(self.db, 'D2', 'DIODE', [('1', 'A', 'VDD'), ('2', 'K', 'VIN2')])
        complete(self.db);self.intent = make_intent(self.db, self.doc)
        self.intent['power_sources'].append({'node': 'P2.1', 'states': ['A', 'B'], 'citation': 'Reverse blocking direction only'})
        self.assertEqual(self.errors(), [])

    def test_unknown_mos_switch_and_multicontact_bypass_rebound_reject(self):
        for mode in ('NMOS-passive-gate', 'NMOS-input-gate', 'SPDT', 'unknown-passive'):
            with self.subTest(mode=mode):
                self.db = board()
                if mode.startswith('NMOS'):
                    add(self.db, 'Q2', 'NMOS', [('1', 'G', 'CTL'), ('2', 'S', 'VBUS'), ('3', 'D', 'VDD')])
                else:
                    add(self.db, 'SW2' if mode == 'SPDT' else 'ZZ2', 'SW_SPDT' if mode == 'SPDT' else 'UNCLASSIFIED',
                        [('1', 'COM', 'VBUS'), ('2', 'ON', 'VDD'), ('3', 'OFF', 'OFF_NET')])
                complete(self.db)
                if mode == 'NMOS-input-gate':
                    self.db['native_pintype']['Q2.1'] = self.db['declared_native_pintype']['Q2.1'] = 'input'
                    self.db['pintype']['Q2.1'] = self.db['declared_pintype']['Q2.1'] = 'IN'
                self.intent = make_intent(self.db, self.doc)
                self.assert_rejected('bypass path')
                self.assertFalse(any('stale' in e for e in self.errors()))

    def test_mos_gate_is_not_a_conduction_terminal_and_ground_load_is_allowed(self):
        add(self.db, 'Q2', 'NMOS', [('1', 'G', 'VBUS'), ('2', 'S', 'GND'), ('3', 'D', 'VDD')])
        add(self.db, 'R2', 'RES', [('1', '1', 'VDD'), ('2', '2', 'GND')]);self.db['parts']['R2']['value'] = '47K'
        complete(self.db);self.intent = make_intent(self.db, self.doc)
        self.assertEqual(self.errors(), [])

    def test_remote_declared_source_through_unknown_mos_cannot_assume_off(self):
        add(self.db, 'P2', 'Connector:Conn_01x02', [('1', 'VIN', 'VIN2'), ('2', 'GND', 'GND')])
        add(self.db, 'Q2', 'NMOS', [('1', 'G', 'CTL'), ('2', 'S', 'VIN2'), ('3', 'D', 'VDD')])
        complete(self.db);self.intent = make_intent(self.db, self.doc)
        self.intent['power_sources'].append({'node': 'P2.1', 'states': ['A', 'B'], 'citation': 'Independent energized source'})
        self.assert_rejected('independently declared source')

    def test_exact_literal_pin_and_mpn_boundaries_after_rebinding_source_hash(self):
        for mode, wrong, field, reason in [('pin', '11 VDD power input', 'pin_quote', 'physical pin quote'),
                ('mpn', 'SYNTH-SHUNT-42 electrical characteristics', 'identity_quote', 'identity quote')]:
            with self.subTest(mode=mode):
                text = 'SYNTH-SHUNT electrical characteristics REV1\nInternal shunt regulated rail VDD\n1 VDD power input\n'
                old = '1 VDD power input' if mode == 'pin' else 'SYNTH-SHUNT electrical characteristics'
                self.doc.write_text(text.replace(old, wrong));self.intent = make_intent(self.db, self.doc)
                for item in self.intent['supervision']['rail_requirements']:
                    item['identity']['feed_provenance']['receiver_source'][field] = wrong
                self.assert_rejected(reason)
                self.assertFalse(any('hash mismatch' in e or 'stale' in e for e in self.errors()))

    def test_receiver_part_value_and_symbol_conflicts_cannot_rebind_to_valid_identity(self):
        for field in ('part', 'value', 'prim'):
            with self.subTest(field=field):
                self.db = board();self.db['parts']['U1'][field] = 'WRONG-DEVICE'
                self.intent = make_intent(self.db, self.doc)
                self.assert_rejected('identity conflict')
                self.assertFalse(any('stale' in e for e in self.errors()))

    def test_truncated_quotes_cannot_take_pin_or_mpn_prefix_out_of_actual_page(self):
        for mode in ('pin', 'model', 'correct-token-elsewhere'):
            with self.subTest(mode=mode):
                text = 'SYNTH-SHUNT electrical characteristics REV1\nInternal shunt regulated rail VDD\n1 VDD power input\n'
                if mode in ('pin', 'correct-token-elsewhere'):
                    text = text.replace('1 VDD', '11 VDD')
                    if mode == 'correct-token-elsewhere':
                        text += '\n1 unrelated index\n'
                else:
                    text = text.replace('SYNTH-SHUNT electrical', 'SYNTH-SHUNT-42 electrical')
                self.doc.write_text(text);self.intent = make_intent(self.db, self.doc)
                if mode == 'model':
                    for item in self.intent['supervision']['rail_requirements']:
                        # Prefix is a literal substring at the wrong raw location.
                        item['identity']['feed_provenance']['receiver_source']['identity_quote'] = 'SYNTH-SHUNT'
                self.assert_rejected('identity quote' if mode == 'model' else 'physical pin quote')
                self.assertFalse(any('hash mismatch' in e or 'stale' in e for e in self.errors()))

    def test_document_family_exact_variant_and_connector_descriptive_value_allowed(self):
        self.db['parts']['U1'].update(part='SYNTH-SHUNT', value='synth-shunt', prim='Synthetic:SYNTH-SHUNT')
        self.db['parts']['P1']['value'] = 'USB supply receptacle descriptive field'
        self.intent = make_intent(self.db, self.doc)
        for item in self.intent['supervision']['rail_requirements']:
            item['identity']['feed_provenance']['receiver_source']['document_model'] = 'SYNTH family'
        self.assertEqual(self.errors(), [])


    def test_receiver_native_part_equivalent_case_whitespace_namespace(self):
        cases = [
            ('synth-shunt', 'synth-shunt', 'synth-shunt'),
            (' Synth-Shunt ', ' SYNTH-SHUNT ', ' synth-shunt '),
            (' Lib:synth-shunt ', 'lib:SYNTH-SHUNT', 'Other:Synth-Shunt'),
            ('SYNTH-SHUNT', ' synth-shunt ', ' lib:synth-shunt '),
            (' lib:SYNTH-SHUNT ', ' SYNTH-SHUNT ', ''),
        ]
        for part, value, prim in cases:
            with self.subTest(part=part, value=value, prim=prim):
                self.db = board()
                self.db['parts']['U1'].update(part=part, value=value, prim=prim)
                self.intent = make_intent(self.db, self.doc)
                self.assertEqual(self.errors(), [])
                inv = sv.build_inventory(self.db, self.intent)
                self.assertEqual(sv.build_inventory(self.db, inv['context']), inv)
                for state in inv['states']:
                    rail = next(r for r in state['rails'] if r['net'] == 'VDD')
                    self.assertTrue(rail['scope_qualified'])
                    self.assertIn('rail-unmonitored:VDD', rail['observation_gaps'])
                    self.assertFalse(rail['source_path'][0]['performance_guarantee'])
                    self.assertFalse(rail['source_path'][0]['electrical_equivalence'])
                self.assertEqual(self.db['native_pintype']['U1.1'], 'power_in')

    def test_receiver_every_field_equivalent_expression_is_accepted(self):
        for field in ('part', 'value', 'prim'):
            for spelling in ('synth-shunt', 'Synth-Shunt', ' SYNTH-SHUNT ', ' lib:synth-shunt '):
                with self.subTest(field=field, spelling=spelling):
                    self.db = board()
                    self.db['parts']['U1'][field] = spelling
                    self.intent = make_intent(self.db, self.doc)
                    self.assertEqual(self.errors(), [])
                    self.assertTrue(all(r['scope_qualified'] for st in sv.build_inventory(
                        self.db, self.intent)['states'] for r in st['rails'] if r['net'] == 'VDD'))

    def test_equivalent_case_cannot_hide_field_conflicts_or_model_boundaries(self):
        for field in ('part', 'value', 'prim'):
            for wrong in (' OTHER-MODEL ', 'synth-shunt-42', 'xsynth-shunt',
                          'Lib:SYNTH-SHUNT_suffix', 'SYNTH-SHUNTx',
                          'Lib:SYNTH-SHUNT:OTHER', 'SYNTH SHUNT'):
                with self.subTest(field=field, wrong=wrong):
                    self.db = board()
                    self.db['parts']['U1'].update(part=' synth-shunt ',
                        value='Lib:Synth-Shunt', prim='lib:SYNTH-SHUNT')
                    self.db['parts']['U1'][field] = wrong
                    self.intent = make_intent(self.db, self.doc)
                    self.assert_rejected('identity conflict')
                    self.assertFalse(any('stale' in e or 'hash mismatch' in e for e in self.errors()))

    def test_consistent_wrong_model_cannot_borrow_original_source_quote(self):
        for wrong in ('SYNTH-SHUNT-42', 'XSYNTH-SHUNT', 'SYNTH-SHUNTX'):
            with self.subTest(wrong=wrong):
                self.db = board()
                self.db['parts']['U1'].update(part=' '+wrong.lower()+' ',
                    value=wrong, prim='Lib:'+wrong)
                self.intent = make_intent(self.db, self.doc)
                self.assert_rejected('identity quote')
                self.assertFalse(any('identity conflict' in e for e in self.errors()))

if __name__ == '__main__':
    unittest.main()

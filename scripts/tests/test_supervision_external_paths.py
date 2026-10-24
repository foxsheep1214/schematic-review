"""Synthetic external-contact and directed passive-path counterexamples."""
import copy
import pathlib
import sys
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import board_intent
from checkers import netgraph as ng
import part_words as pw
from checkers.supervision import SupervisionChecker, build_inventory, validate_supervision_intent
from test_supervision_requirements import board, requirement, intent_for, coverage
from test_inductive_load import add
from electrical_fixtures import bound_intent


def nc_pad(db):
    node, net = 'P1.NC1', 'unconnected-(P1-PadNC1)'
    db['pin2net'][node] = net
    db['pinname'][node] = 'NC1'
    db['pintype'][node] = 'NC'
    db['nets'][net] = [node]
    db['pseudo_nets'].append(net)
    db['no_connect_nodes'] = [node]
    db['native_pintype'][node] = 'no_connect'
    db['declared_native_pintype'][node] = 'no_connect'


def move(db, node, target):
    db['nets'][db['pin2net'][node]].remove(node)
    db['pin2net'][node] = target
    db['nets'].setdefault(target, []).append(node)


def source_board():
    db = board()
    nc_pad(db)
    move(db, 'P1.1', 'RAWOUT')
    add(db, 'D8', 'D_Schottky', [('1', 'A', 'RAWOUT'), ('2', 'K', 'VMID')])
    add(db, 'R8', '0', [('1', '1', 'VMID'), ('2', '2', 'VCC_A')])
    for node in ('D8.1', 'D8.2', 'R8.1', 'R8.2'):
        db['native_pintype'][node] = db['declared_native_pintype'][node] = 'passive'
    return db


def source_intent(db):
    intent = bound_intent(db, state='A')
    intent['assemblies'].append(dict(copy.deepcopy(intent['assemblies'][0]), id='B'))
    intent['supervision'] = {'schema_version': 2, 'supervisors': [], 'rail_requirements': [
        requirement(db, net, state, node, role=role) for state in ('A', 'B')
        for net, node, role in [('VCC_A', 'P1.1', 'upstream_external_supply'),
                                ('VCC_B', 'P2.1', 'external_supply')]]}
    return intent


class ExternalSupplyPathTests(unittest.TestCase):
    def assertBlocked(self, db, intent, state='A', net='VCC_A'):
        self.assertTrue(validate_supervision_intent(intent, db))
        _, checks = coverage(db, intent)
        self.assertIn('rail-unmonitored:' + net, checks[state]['inventory_gaps'])

    def test_isolated_nc_mechanical_pad_is_not_a_supply_contact(self):
        db = board()
        nc_pad(db)
        intent = intent_for(db)
        self.assertEqual(validate_supervision_intent(intent, db), [])
        plan, checks = coverage(db, intent)
        self.assertEqual(checks['A']['inventory_gaps'], [])
        self.assertEqual(checks['A']['applicability'], 'APPLICABLE')
        self.assertEqual(checks['A']['readiness'], 'WAITING_EVIDENCE')
        self.assertEqual(plan['supervision']['states'][0]['supervisors'], [])

    def test_nc_exception_requires_export_declaration_and_isolated_pseudo_net(self):
        for case in ('missing-declaration', 'missing-native', 'not-nc-index', 'not-pseudo',
                     'ground', 'real-rail', 'fake-ground-pseudo', 'fake-supply-pseudo',
                     'shared-nc', 'declaration-conflict', 'normalized-conflict'):
            with self.subTest(case=case):
                db = board()
                nc_pad(db)
                node = 'P1.NC1'
                if case == 'missing-declaration':
                    db.pop('declared_native_pintype')
                elif case == 'missing-native':
                    db['native_pintype'].pop(node)
                elif case == 'not-nc-index':
                    db['no_connect_nodes'] = []
                elif case == 'not-pseudo':
                    db['pseudo_nets'] = []
                elif case in ('ground', 'real-rail'):
                    move(db, node, 'GND' if case == 'ground' else 'VCC_A')
                elif case in ('fake-ground-pseudo', 'fake-supply-pseudo'):
                    target = 'AGND' if case == 'fake-ground-pseudo' else 'VIN_FALSE'
                    move(db, node, target)
                    db['pseudo_nets'].append(target)
                elif case == 'shared-nc':
                    db['nets'][db['pin2net'][node]].append('P2.2')
                elif case == 'declaration-conflict':
                    db['declared_native_pintype'][node] = 'passive'
                else:
                    db['pintype'][node] = 'IN'
                self.assertBlocked(db, intent_for(db))

    def test_source_itself_must_remain_native_passive(self):
        for pintype in ('no_connect', 'power_in', 'input', 'power_out', 'output', 'bidirectional'):
            with self.subTest(pintype=pintype):
                db = board()
                db['native_pintype']['P1.1'] = db['declared_native_pintype']['P1.1'] = pintype
                self.assertBlocked(db, intent_for(db))

    def test_complete_contact_reciprocity_and_consistent_pin_declarations(self):
        for case in ('source-normalized', 'source-name', 'other-contact-disconnected'):
            db = board()
            nc_pad(db)
            if case == 'source-normalized':
                db['pintype']['P1.1'] = 'IN'
            elif case == 'source-name':
                db['declared_pinname'] = {'P1.1': 'different'}
            else:
                db['nets']['GND'].remove('P1.2')
            self.assertBlocked(db, intent_for(db))

    def test_positive_external_source_forward_diode_zero_ohm_path(self):
        db, intent = source_board(), None
        intent = source_intent(db)
        self.assertEqual(validate_supervision_intent(intent, db), [])
        plan, checks = coverage(db, intent)
        self.assertTrue(all(c['inventory_gaps'] == [] for c in checks.values()))
        inventory = plan['supervision']
        rail = next(r for r in inventory['states'][0]['rails'] if r['net'] == 'VCC_A')
        self.assertEqual(rail['source_path'], [
            {'ref': 'D8', 'from_node': 'D8.1', 'from_net': 'RAWOUT', 'to_node': 'D8.2', 'to_net': 'VMID'},
            {'ref': 'R8', 'from_node': 'R8.1', 'from_net': 'VMID', 'to_node': 'R8.2', 'to_net': 'VCC_A'}])
        self.assertIsNone(rail['monitor'])
        self.assertIn('rail-unmonitored:VCC_A', rail['observation_gaps'])
        self.assertEqual(build_inventory(db, inventory['context']), inventory)
        self.assertEqual(inventory['states'][0]['supervisors'], [])

    def test_reverse_disconnected_dnp_open_and_nonzero_series_paths_block(self):
        for case in ('reversed', 'disconnected', 'dnp-source', 'dnp-diode', 'open-series',
                     'nonzero', 'active-series', 'missing-path-native', 'path-declaration-conflict',
                     'path-name-conflict'):
            with self.subTest(case=case):
                db = source_board()
                if case == 'reversed':
                    db['pinname']['D8.1'], db['pinname']['D8.2'] = 'K', 'A'
                elif case == 'disconnected':
                    move(db, 'D8.1', 'FLOATING')
                elif case == 'nonzero':
                    db['parts']['R8']['value'] = '10k'
                elif case == 'active-series':
                    db['native_pintype']['D8.1'] = db['declared_native_pintype']['D8.1'] = 'power_in'
                elif case == 'missing-path-native':
                    db['native_pintype'].pop('D8.2')
                elif case == 'path-declaration-conflict':
                    db['declared_native_pintype']['D8.2'] = 'input'
                elif case == 'path-name-conflict':
                    db['declared_pinname'] = {'D8.2': 'A'}
                intent = source_intent(db)
                if case.startswith('dnp-'):
                    intent['assemblies'][0]['population']['P1' if case == 'dnp-source' else 'D8'] = False
                elif case == 'open-series':
                    intent['assemblies'][0]['jumpers'] = {'R8': 'open'}
                self.assertBlocked(db, intent)
                if case.startswith('dnp-') or case == 'open-series':
                    _, checks = coverage(db, intent)
                    self.assertEqual(checks['B']['inventory_gaps'], [])

    def test_upstream_role_requires_nonempty_path_to_exact_rail(self):
        db = board()
        intent = intent_for(db)
        intent['supervision']['rail_requirements'][0]['identity']['source_role'] = 'upstream_external_supply'
        self.assertBlocked(db, intent)
        db = source_board()
        intent = source_intent(db)
        item = intent['supervision']['rail_requirements'][0]
        item['identity'] = requirement(db, 'VCC_A', 'A', 'P2.1', role='upstream_external_supply')['identity']
        self.assertBlocked(db, intent)

    def test_direct_role_cannot_claim_an_upstream_net(self):
        db = source_board()
        intent = source_intent(db)
        intent['supervision']['rail_requirements'][0]['identity']['source_role'] = 'external_supply'
        self.assertBlocked(db, intent)

    def test_active_input_and_passive_nonconnector_cannot_be_promoted(self):
        for source in ('U1.1', 'D8.1', 'R8.1'):
            db = source_board()
            intent = source_intent(db)
            intent['supervision']['rail_requirements'][0] = requirement(
                db, 'VCC_A', 'A', source, role='upstream_external_supply')
            self.assertBlocked(db, intent)

    def test_bound_identity_snapshot_state_citations_and_input_are_required(self):
        for case in ('part', 'pin', 'native', 'citation', 'requirement-citation', 'state', 'stale'):
            with self.subTest(case=case):
                db = source_board()
                intent = source_intent(db)
                item = intent['supervision']['rail_requirements'][0]
                if case == 'part':
                    item['identity']['part']['value'] = 'different'
                elif case == 'pin':
                    item['identity']['pin_name'] = 'wrong'
                elif case == 'native':
                    item['identity']['native_pintypes'].pop('P1.NC1')
                elif case == 'citation':
                    item['identity']['citation'] = ''
                elif case == 'requirement-citation':
                    item['citation'] = ''
                elif case == 'state':
                    item['state'] = 'foreign'
                else:
                    intent['input_sha256'] = '0' * 64
                    self.assertTrue(validate_supervision_intent(intent, db))
                    inventory = build_inventory(db, intent)
                    self.assertTrue(all(not r['scope_qualified'] for s in inventory['states'] for r in s['rails']))
                    continue
                self.assertBlocked(db, intent)

    def test_other_rail_state_and_required_true_are_not_exempted(self):
        db = source_board()
        intent = source_intent(db)
        intent['supervision']['rail_requirements'] = intent['supervision']['rail_requirements'][:1]
        _, checks = coverage(db, intent)
        self.assertIn('rail-unmonitored:VCC_B', checks['A']['inventory_gaps'])
        self.assertNotIn('rail-unmonitored:VCC_A', checks['A']['inventory_gaps'])
        self.assertIn('rail-unmonitored:VCC_A', checks['B']['inventory_gaps'])
        intent = source_intent(db)
        intent['supervision']['rail_requirements'][0]['required'] = True
        _, checks = coverage(db, intent)
        self.assertIn('rail-unmonitored:VCC_A', checks['A']['inventory_gaps'])
        self.assertEqual(checks['B']['inventory_gaps'], [])


def verified_series_fixture(ref, value, kind):
    """The production audit -> analysis-intent -> graph route, with synthetic citations."""
    db = source_board()
    old = 'R8'
    if ref != old:
        db['parts'][ref] = db['parts'].pop(old)
        for field in ('pin2net', 'pinname', 'pintype', 'native_pintype', 'declared_native_pintype'):
            for node in list(db.get(field, {})):
                if node.startswith(old + '.'):
                    db[field][ref + node[len(old):]] = db[field].pop(node)
        for net, nodes in db['nets'].items():
            db['nets'][net] = [ref + n[len(old):] if n.startswith(old + '.') else n for n in nodes]
    identity = 'Device:R' if kind == pw.RESISTOR else kind
    db['parts'][ref].update(part=identity, prim=identity, value=value)
    intent = source_intent(db)
    declaration = {'kind': kind, 'page': 1, 'quote': 'Synthetic manufacturer classification: ' + kind}
    intent['device_kinds'] = {ref: declaration}
    audit = {'device_kinds': {ref: dict(declaration, status='VERIFIED', document='synthetic-kind.pdf',
                                      document_sha256='a' * 64)}}
    return db, board_intent.with_verified_kinds(intent, audit)


class VerifiedSeriesPathTests(unittest.TestCase):
    def route(self, ref, value, kind):
        db, analysis = verified_series_fixture(ref, value, kind)
        graph = ng.NetGraph(board_intent.graph_db(db, analysis))
        self.assertEqual(graph.kind(ref), kind)
        self.assertEqual(graph.basis(ref), 'datasheet')
        plan, checks = coverage(db, analysis)
        check = checks['A']
        rail = next(r for r in plan['supervision']['states'][0]['rails'] if r['net'] == 'VCC_A')
        blockers = SupervisionChecker().pass_blockers(check['id'], check, check, plan['supervision'])
        return db, analysis, check, rail, blockers

    def test_verified_resistor_rejects_nonzero_unknown_wrong_units_and_underflow(self):
        invalid = ['10k', '1', '0.01R', 'R01', '1mOhm', '1mΩ', '0.001mOhm', '0K1',
                   '', None, 0, False, 'unknown', 'nan', 'inf', '-1', '-0', '-0R', '0uH', '0A',
                   '0V', '0R junk', '0 100%', '0 +/-100%', '0 ±-5%', '0e3', '1e-6',
                   '0 / 10% junk', '0 0V', '0.' + '0' * 330 + '1R', '0.' + '0' * 5000 + '1R']
        for ref in ('F8', 'L8', 'FB8'):
            for value in invalid:
                with self.subTest(ref=ref, value=value):
                    db, analysis, check, rail, blockers = self.route(ref, value, pw.RESISTOR)
                    self.assertTrue(validate_supervision_intent(analysis, db))
                    self.assertFalse(rail['scope_qualified'])
                    self.assertIsNone(rail['requirement'])
                    self.assertIn('rail-unmonitored:VCC_A', check['inventory_gaps'])
                    self.assertTrue(blockers)

    def test_verified_exact_zero_resistors_with_valid_units_remain_eligible(self):
        zero_values = ['0', '0R', '0Ω', '0 Ohm', '0ohm', '0mOhm', '0mΩ', '0kOhm', '0MOhm',
                       'R0', '0R0', '0.000R', '0 ±5%', '0 +/-5%', '0 / R0402']
        for ref in ('R8', 'F8', 'L8', 'FB8'):
            for value in zero_values:
                with self.subTest(ref=ref, value=value):
                    db, analysis, check, rail, blockers = self.route(ref, value, pw.RESISTOR)
                    self.assertEqual(validate_supervision_intent(analysis, db), [])
                    self.assertTrue(rail['scope_qualified'])
                    self.assertEqual(check['inventory_gaps'], [])
                    self.assertEqual(blockers, [])
                    self.assertEqual(check['applicability'], 'APPLICABLE')
                    self.assertEqual(check['readiness'], 'WAITING_EVIDENCE')
                    self.assertIn('rail-unmonitored:VCC_A', rail['observation_gaps'])
                    self.assertEqual([p['ref'] for p in rail['source_path']], ['D8', ref])

    def test_true_inductor_ferrite_and_fuse_keep_their_nonresistor_labels(self):
        for ref, value, kind in [('L8', '10uH', pw.INDUCTOR),
                                 ('FB8', '120R@100MHz', pw.FERRITE), ('F8', '2A', pw.FUSE)]:
            with self.subTest(ref=ref, kind=kind):
                db, analysis, check, rail, blockers = self.route(ref, value, kind)
                self.assertEqual(validate_supervision_intent(analysis, db), [])
                self.assertTrue(rail['scope_qualified'])
                self.assertEqual(check['inventory_gaps'], [])
                self.assertEqual(blockers, [])
                self.assertIsNone(rail['monitor'])
                self.assertIn('rail-unmonitored:VCC_A', rail['observation_gaps'])


if __name__ == '__main__':
    unittest.main()

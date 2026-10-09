"""Independent manual claims never replace generated coverage or source integrity."""
import copy
import hashlib
import tempfile
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_decoupling import fixture, ledger, mark_pass, move_pin, rebind
from test_i2c_topology import add
from plan_review import build_review_plan
from revision_impact import dependency_catalog
from validate_review import validate_review


def independent(plan, db, rule='PWR-T03'):
    row = copy.deepcopy(next(p for p in plan['checks'] if p['rule'] == rule))
    row.update(id=rule + '.MANUAL-LOCAL', object={'ref': 'U1', 'nodes': ['U1.1'],
        'return_nodes': ['U1.2'], 'state': 'run', 'manual_group': 'LOCAL-CLAIM'},
        criterion='Synthetic direct endpoint inventory; no electrical suitability claim',
        inventory_gaps=[], full_inventory_gaps=[], required_inputs=[], trigger=['synthetic independent endpoint audit'])
    plan['checks'].append(row)
    plan['check_dependencies'] = dependency_catalog(plan, db, plan['review_inputs'])
    return row


class ManualDecouplingTests(unittest.TestCase):
    def test_independent_trace_pass_and_generated_electrical_gaps_survive(self):
        db, intent = fixture()
        intent['decoupling']['groups'][0]['requirements'] = []
        plan = build_review_plan(db, intent)
        manual = independent(plan, db)
        report = ledger(plan, db)
        mark_pass(next(r for r in report['checks'] if r['id'] == manual['id']))
        result = validate_review(plan, report, db, require_bindings=True)
        self.assertTrue(result['valid'], result['errors'])
        self.assertEqual(result['release'], 'NO_GO')
        generated = next(p for p in plan['checks'] if p['rule'] == 'PWR-D02')
        mark_pass(next(r for r in report['checks'] if r['id'] == generated['id']))
        self.assertFalse(validate_review(plan, report, db)['valid'])

    def test_source_bound_manual_roles_without_generated_device_declaration(self):
        db, intent = fixture()
        intent['devices'] = {}; intent['decoupling']['groups'] = []
        plan = build_review_plan(db, intent)
        row = independent(plan, db)
        source = Path(self.enterContext(tempfile.TemporaryDirectory())) / 'official-pins.txt'
        source.write_text('Synthetic official pin table: 1 VDD power; 2 VSS return; 3 IO other.')
        row['object'].update(manual_pin_source={'path': str(source), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'locator': 'pin table'}, manual_pin_roles={'U1.1': 'power', 'U1.2': 'return'},
                             manual_pin_citation='synthetic independent official pin table 1')
        plan['check_dependencies'] = dependency_catalog(plan, db, plan['review_inputs'])
        report = ledger(plan, db)
        mark_pass(next(r for r in report['checks'] if r['id'] == row['id']))
        result = validate_review(plan, report, db)
        self.assertTrue(result['valid'], result['errors'])
        self.assertEqual(result['release'], 'NO_GO')
        del row['object']['manual_pin_citation']
        plan['check_dependencies'] = dependency_catalog(plan, db, plan['review_inputs'])
        self.assertFalse(validate_review(plan, ledger(plan, db), db)['valid'])

    def test_manual_roles_cannot_override_official_role(self):
        db, intent = fixture()
        plan = build_review_plan(db, intent)
        row = independent(plan, db)
        row['object'].update(nodes=['U1.3'], manual_pin_roles={'U1.3': 'power', 'U1.2': 'return'},
                             manual_pin_citation='synthetic conflicting manual roles')
        plan['check_dependencies'] = dependency_catalog(plan, db, plan['review_inputs'])
        self.assertFalse(validate_review(plan, ledger(plan, db), db)['valid'])

    def test_manual_fields_do_not_impersonate_generated_binding(self):
        db, intent = fixture()
        original = build_review_plan(db, intent)
        for field in ('decoupling_group', 'decoupling_scope', 'decoupling_inventory_digest'):
            plan = copy.deepcopy(original); manual = independent(plan, db)
            manual['object'][field] = original['checks'][-1].get('object', {}).get(field, 'forged')
            self.assertFalse(validate_review(plan, ledger(plan, db), db)['valid'], field)

    def test_incomplete_or_wrong_manual_physical_context_rejected(self):
        db, intent = fixture()
        original = build_review_plan(db, intent)
        for field, value in [('ref', 'U999'), ('nodes', ['U1.999']), ('state', 'ghost'), ('nodes', ['U1.3']), ('return_nodes', []), ('manual_group', '')]:
            plan = copy.deepcopy(original); independent(plan, db)['object'][field] = value
            self.assertFalse(validate_review(plan, ledger(plan, db), db)['valid'], field)

    def test_manual_pass_does_not_restore_failed_source_integrity(self):
        db, intent = fixture(); db['integrity'] = {'self_check_passed': False}; rebind(db, intent)
        plan = build_review_plan(db, intent); manual = independent(plan, db); report = ledger(plan, db)
        mark_pass(next(r for r in report['checks'] if r['id'] == manual['id']))
        result = validate_review(plan, report, db)
        self.assertTrue(result['valid'], result['errors'])
        self.assertEqual(result['release'], 'NO_GO')
        self.assertIn('input netlist failed integrity/export checks', result['blockers'])
        generated = next(p for p in plan['checks'] if p['rule'] == 'PWR-T03' and p['id'] != manual['id'])
        mark_pass(next(r for r in report['checks'] if r['id'] == generated['id']))
        self.assertFalse(validate_review(plan, report, db)['valid'])

    def test_ferrite_upstream_caps_are_not_local_caps_in_manual_trace(self):
        db, intent = fixture(('100nF',)); move_pin(db, 'U1.1', 'FILTERED')
        add(db, 'FB1', 'FERRITE', [('1','1','VCC_3V3'), ('2','2','FILTERED')])
        intent['decoupling']['components']['FB1']={'kind':'ferrite','citation':'synthetic BOM ferrite'}
        intent['assemblies'][0]['population']['FB1']=True; rebind(db,intent)
        plan=build_review_plan(db,intent); manual=independent(plan, db)
        group=next(g for g in plan['decoupling']['states'][0]['groups'] if g['ref']=='U1')
        self.assertEqual(group['fitted_capacitors'], [])
        self.assertTrue(group['boundaries'])
        report=ledger(plan,db);mark_pass(next(r for r in report['checks'] if r['id']==manual['id']))
        result=validate_review(plan,report,db)
        self.assertTrue(result['valid'],result['errors'])
        self.assertEqual(result['release'],'NO_GO')

"""Independent manual claims never replace generated coverage or source integrity. A manual claim is a rule gap the
reviewer registers (fixed requirements, step 7); the planner writes it and the decoupling checker still checks it."""
import hashlib
import tempfile
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_decoupling import fixture, ledger, mark_pass, move_pin, rebind
from test_i2c_topology import add
from plan_review import build_review_plan
from validate_review import validate_review


def independent(db, intent, rule='PWR-T03', **changes):
    """Plan with one manual endpoint audit registered as a rule gap; returns (plan, its row)."""
    obj = dict({'ref': 'U1', 'nodes': ['U1.1'], 'return_nodes': ['U1.2'], 'state': 'run', 'manual_group': 'LOCAL-CLAIM'},
               **changes)
    gap = {'id': 'MANUAL-LOCAL', 'rule': rule, 'object': obj,
           'criterion': 'Synthetic direct endpoint inventory; no electrical suitability claim',
           'missing': 'synthetic: no generated endpoint audit for this claim', 'basis': 'synthetic independent endpoint audit'}
    plan = build_review_plan(db, dict(intent, rule_gaps=[gap]))
    return plan, next(c for c in plan['checks'] if c.get('origin') == 'REVIEWER_ADDED')


class ManualDecouplingTests(unittest.TestCase):
    def test_independent_trace_pass_and_generated_electrical_gaps_survive(self):
        db, intent = fixture()
        intent['decoupling']['groups'][0]['requirements'] = []
        plan, manual = independent(db, intent)
        report = ledger(plan, db)
        mark_pass(report, plan, manual['id'])
        result = validate_review(plan, report, db, require_bindings=True)
        self.assertTrue(result['valid'], result['errors'])
        self.assertEqual(result['release'], 'NO_GO')
        generated = next(p for p in plan['checks'] if p['rule'] == 'PWR-D02')
        mark_pass(report, plan, generated['id'])
        self.assertFalse(validate_review(plan, report, db)['valid'])

    def test_source_bound_manual_roles_without_generated_device_declaration(self):
        db, intent = fixture()
        intent['devices'] = {}; intent['decoupling']['groups'] = []
        source = Path(self.enterContext(tempfile.TemporaryDirectory())) / 'official-pins.txt'
        source.write_text('Synthetic official pin table: 1 VDD power; 2 VSS return; 3 IO other.')
        roles = dict(manual_pin_source={'path': str(source), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'locator': 'pin table'}, manual_pin_roles={'U1.1': 'power', 'U1.2': 'return'})
        plan, row = independent(db, intent, manual_pin_citation='synthetic independent official pin table 1', **roles)
        report = ledger(plan, db)
        mark_pass(report, plan, row['id'])
        result = validate_review(plan, report, db)
        self.assertTrue(result['valid'], result['errors'])
        self.assertEqual(result['release'], 'NO_GO')
        plan, row = independent(db, intent, **roles)
        self.assertFalse(validate_review(plan, ledger(plan, db), db)['valid'])

    def test_manual_roles_cannot_override_official_role(self):
        db, intent = fixture()
        plan, row = independent(db, intent, nodes=['U1.3'], manual_pin_roles={'U1.3': 'power', 'U1.2': 'return'},
                                manual_pin_citation='synthetic conflicting manual roles')
        self.assertFalse(validate_review(plan, ledger(plan, db), db)['valid'])

    def test_manual_fields_do_not_impersonate_generated_binding(self):
        db, intent = fixture()
        original = build_review_plan(db, intent)
        for field in ('decoupling_group', 'decoupling_scope', 'decoupling_inventory_digest'):
            plan, manual = independent(db, intent, **{field: original['checks'][-1].get('object', {}).get(field, 'forged')})
            self.assertFalse(validate_review(plan, ledger(plan, db), db)['valid'], field)

    def test_incomplete_or_wrong_manual_physical_context_rejected(self):
        db, intent = fixture()
        for field, value in [('ref', 'U999'), ('nodes', ['U1.999']), ('state', 'ghost'), ('nodes', ['U1.3']), ('return_nodes', []), ('manual_group', '')]:
            plan, _ = independent(db, intent, **{field: value})
            self.assertFalse(validate_review(plan, ledger(plan, db), db)['valid'], field)

    def test_manual_pass_does_not_restore_failed_source_integrity(self):
        db, intent = fixture(); db['integrity'] = {'self_check_passed': False}; rebind(db, intent)
        plan, manual = independent(db, intent); report = ledger(plan, db)
        mark_pass(report, plan, manual['id'])
        result = validate_review(plan, report, db)
        self.assertTrue(result['valid'], result['errors'])
        self.assertEqual(result['release'], 'NO_GO')
        self.assertIn('input netlist failed integrity/export checks', result['blockers'])
        generated = next(p for p in plan['checks'] if p['rule'] == 'PWR-T03' and p['id'] != manual['id'])
        mark_pass(report, plan, generated['id'])
        self.assertFalse(validate_review(plan, report, db)['valid'])

    def test_ferrite_upstream_caps_are_not_local_caps_in_manual_trace(self):
        db, intent = fixture(('100nF',)); move_pin(db, 'U1.1', 'FILTERED'); intent['decoupling']['groups'][0]['net'] = 'FILTERED'
        add(db, 'FB1', 'FERRITE', [('1','1','VCC_3V3'), ('2','2','FILTERED')])
        intent['decoupling']['components']['FB1']={'kind':'ferrite','citation':'synthetic BOM ferrite'}
        intent['assemblies'][0]['population']['FB1']=True; rebind(db,intent)
        plan, manual = independent(db, intent)
        group=next(g for g in plan['decoupling']['states'][0]['groups'] if g['ref']=='U1')
        self.assertEqual(group['fitted_capacitors'], [])
        self.assertTrue(group['boundaries'])
        report=ledger(plan,db);mark_pass(report, plan, manual['id'])
        result=validate_review(plan,report,db)
        self.assertTrue(result['valid'],result['errors'])
        self.assertEqual(result['release'],'NO_GO')

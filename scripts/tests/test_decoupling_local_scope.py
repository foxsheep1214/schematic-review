"""Narrow source-bound connection gates retain full inventory and failure guards."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plan_review import build_review_plan
from validate_review import validate_review
from test_decoupling import fixture, rebind, ledger, mark_pass


def with_foreign_group_pin():
    db, intent = fixture(('100nF',))
    db['pin2net']['U1.4'] = 'OTHER_3V3'
    db['nets']['OTHER_3V3'] = ['U1.4']
    db['pinname']['U1.4'] = 'VDD'
    rebind(db, intent)
    return db, intent


def local_rows(plan):
    return [c for c in plan['checks'] if c['rule'] in ('PWR-T03', 'PWR-D02')
            and c['object'].get('nodes') == ['U1.1']]


class LocalConnectionScopeTests(unittest.TestCase):
    def test_source_proven_local_group_can_pass_with_other_group_difference_retained(self):
        db, intent = with_foreign_group_pin()
        plan = build_review_plan(db, intent)
        rows = local_rows(plan)
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertEqual(row['inventory_gaps'], [])
            self.assertIn('pin-not-in-official-map:U1.4', row['full_inventory_gaps'])
        self.assertIn('pin-not-in-official-map:U1.4', plan['decoupling']['discovery_gaps'])
        report = ledger(plan, db)
        selected = {r['id'] for r in rows}
        for row in report['checks']:
            if row['id'] in selected:
                mark_pass(row)
        gate = validate_review(plan, report, db, require_bindings=True)
        self.assertTrue(gate['valid'], gate['errors'])
        self.assertEqual(len([c for c in report['checks'] if c['review_result'] == 'PASS']), 2)

    def test_full_inventory_and_numeric_criteria_remain_blocked(self):
        db, intent = with_foreign_group_pin(); plan = build_review_plan(db, intent)
        for rule in ('PWR-D01', 'PWR-C09', 'PWR-C10'):
            report = ledger(plan, db)
            selected = next(c for c in plan['checks'] if c['rule'] == rule and
                            (rule == 'PWR-D01' or c['object'].get('nodes') == ['U1.1']))
            mark_pass(next(c for c in report['checks'] if c['id'] == selected['id']))
            gate = validate_review(plan, report, db)
            self.assertFalse(gate['valid'], rule)
            self.assertTrue(any('decoupling gaps' in e for e in gate['errors']), gate['errors'])

    def test_incomplete_official_pinout_cannot_borrow_local_pass(self):
        db, intent = with_foreign_group_pin(); intent['devices']['U1']['pinout_complete'] = False
        plan = build_review_plan(db, intent)
        for row in local_rows(plan):
            self.assertIn('official-full-pinout:U1', row['inventory_gaps'])
        report = ledger(plan, db)
        for row in report['checks']:
            if row['id'] in {c['id'] for c in local_rows(plan)}:
                mark_pass(row)
        self.assertFalse(validate_review(plan, report, db)['valid'])

    def test_missing_population_and_return_connection_remain_blocking(self):
        for problem in ('population', 'return'):
            with self.subTest(problem=problem):
                db, intent = with_foreign_group_pin()
                if problem == 'population':
                    del intent['assemblies'][0]['population']['U1']
                else:
                    db['nets']['GND'].remove('U1.2'); del db['pin2net']['U1.2']; rebind(db, intent)
                plan = build_review_plan(db, intent); report = ledger(plan, db)
                for row in report['checks']:
                    if row['id'] in {c['id'] for c in local_rows(plan)}:
                        mark_pass(row)
                self.assertFalse(validate_review(plan, report, db)['valid'])

    def test_discovered_unconfirmed_group_cannot_use_the_scope_exception(self):
        db, intent = with_foreign_group_pin(); plan = build_review_plan(db, intent)
        foreign = [c for c in plan['checks'] if c['rule'] == 'PWR-T03' and
                   c['object'].get('nodes') == ['U1.4']]
        self.assertEqual(len(foreign), 1)
        self.assertTrue(any('confirm-group-and-return' in g for g in foreign[0]['inventory_gaps']))
        report = ledger(plan, db)
        mark_pass(next(c for c in report['checks'] if c['id'] == foreign[0]['id']))
        self.assertFalse(validate_review(plan, report, db)['valid'])

    def test_missing_connection_requirement_and_export_integrity_still_block(self):
        for problem in ('requirement', 'export'):
            with self.subTest(problem=problem):
                db, intent = with_foreign_group_pin()
                if problem == 'requirement':
                    intent['decoupling']['groups'][0]['requirements'] = []
                else:
                    db['export_errors'] = ['Synthetic interrupted export']; rebind(db, intent)
                plan = build_review_plan(db, intent); report = ledger(plan, db)
                selected = next(c for c in local_rows(plan) if c['rule'] == 'PWR-D02')
                mark_pass(next(c for c in report['checks'] if c['id'] == selected['id']))
                self.assertFalse(validate_review(plan, report, db)['valid'])

    def test_full_gap_metadata_cannot_be_deleted_to_hide_inventory_difference(self):
        db, intent = with_foreign_group_pin(); plan = build_review_plan(db, intent)
        selected = local_rows(plan)[0]
        selected['full_inventory_gaps'] = []
        gate = validate_review(plan, ledger(plan, db), db)
        self.assertFalse(gate['valid'])
        self.assertTrue(any('generated criterion/object changed' in e for e in gate['errors']))


if __name__ == '__main__':
    unittest.main()

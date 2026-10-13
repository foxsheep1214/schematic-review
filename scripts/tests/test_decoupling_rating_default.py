"""A missing device rating clause falls back to the catalog voltage-rating criterion."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plan_review import build_review_plan
from test_decoupling import fixture


def rows_without(kind, rule):
    db, intent = fixture(('100nF',))
    group = intent['decoupling']['groups'][0]
    group['requirements'] = [r for r in group['requirements'] if r['kind'] != kind]
    plan = build_review_plan(db, intent)
    return [c for c in plan['checks'] if c['rule'] == rule]


class RatingDefaultCriterionTests(unittest.TestCase):
    def test_missing_rating_clause_does_not_block_rating_row(self):
        rows = rows_without('rating', 'PWR-C10')
        self.assertTrue(rows)
        for row in rows:
            self.assertNotIn('datasheet-requirement:rating', row['inventory_gaps'])

    def test_missing_capacitance_clause_still_blocks(self):
        rows = rows_without('capacitance', 'PWR-C09')
        self.assertTrue(rows)
        for row in rows:
            self.assertIn('datasheet-requirement:capacitance', row['inventory_gaps'])


if __name__ == '__main__':
    unittest.main()

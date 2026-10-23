"""A requirement is placed in fixed categories and asks each category's aspects (fixed requirements, step 2).

On the R5 bench the two reviewers agreed on every requirement id and status yet paired none of the 38 requirement
rows: each wrote its own criterion, one copying the text and the other rewriting it, and a rewrite often kept one or
two aspects (a temperature requirement checked only the parts' temperature grade, not derating or drift). Now the
reviewer picks the requirement's categories from a fixed table; each category asks a fixed set of aspects, the planner
writes one REQ-D01 row per (requirement, aspect) whose criterion comes from the aspect's template, and the reviewer's
reading of the requirement rides on the row as `interpretation`, outside the check identity.
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import catalog
import check_key
from plan_review import build_review_plan, validate_intent
from test_requirement_source import requirement_intent, write

DB = {'parts': {}, 'nets': {}, 'pin2net': {}}


def intent(categories=None, interpretations=None, path=None):
    return dict({'schema_version': 4}, **requirement_intent(path or write(), categories=categories,
                                                            interpretations=interpretations))


def rows(plan, rid=None):
    return [c for c in plan['checks'] if c['rule'] == 'REQ-D01' and rid in (None, c['object']['requirement_id'])]


class CategoryTableTests(unittest.TestCase):
    def test_the_category_table_is_fixed_and_every_aspect_has_a_template(self):
        self.assertEqual(list(catalog.REQUIREMENT_CATEGORIES), [
            'INPUT_RANGE', 'OUTPUT_SPEC', 'PROTOCOL', 'PROTECTION', 'ENVIRONMENT', 'SAFETY_ISOLATION', 'LIFETIME',
            'INDICATION', 'OPTIMIZATION', 'COMPLIANCE', 'EXCLUSION'])
        used = set()
        for key, category in catalog.REQUIREMENT_CATEGORIES.items():
            self.assertTrue(category.name and category.targets and category.aspects, key)
            used.update(category.aspects)
        self.assertEqual(used, set(catalog.REQUIREMENT_ASPECTS))
        for key, aspect in catalog.REQUIREMENT_ASPECTS.items():
            self.assertTrue(aspect.name and aspect.template, key)
            self.assertTrue(catalog.requirement_criterion(key).startswith(aspect.name))

    def test_aspects_of_several_categories_are_their_union_without_repeats(self):
        shared = [a for a in catalog.REQUIREMENT_CATEGORIES['SAFETY_ISOLATION'].aspects
                  if a in catalog.REQUIREMENT_CATEGORIES['COMPLIANCE'].aspects]
        self.assertTrue(shared)
        union = catalog.requirement_aspects(['SAFETY_ISOLATION', 'COMPLIANCE'])
        self.assertEqual(len(union), len(set(union)))
        self.assertEqual(set(union), set(catalog.REQUIREMENT_CATEGORIES['SAFETY_ISOLATION'].aspects) |
                         set(catalog.REQUIREMENT_CATEGORIES['COMPLIANCE'].aspects))

    def test_the_catalog_document_lists_the_categories(self):
        text = catalog.render_markdown()
        for category in catalog.REQUIREMENT_CATEGORIES.values():
            self.assertIn(category.name, text)
        for aspect in catalog.REQUIREMENT_ASPECTS.values():
            self.assertIn(aspect.name, text)


class IntentTests(unittest.TestCase):
    def errors(self, value):
        return [e for e in validate_intent(value) if 'requirement' in e]

    def test_a_requirement_names_known_categories_once_each_and_an_interpretation(self):
        self.assertEqual(self.errors(intent()), [])
        for categories, word in (([], 'categories'), (['TEMPERATURE'], 'TEMPERATURE'), (['ENVIRONMENT'] * 2, '重复')):
            value = intent()
            value['requirements'][1]['categories'] = categories
            self.assertTrue(any(word in e for e in self.errors(value)), (categories, self.errors(value)))
        value = intent()
        del value['requirements'][1]['interpretation']
        self.assertTrue(any('interpretation' in e for e in self.errors(value)))

    def test_a_free_criterion_is_refused(self):
        value = intent()
        value['requirements'][0]['criterion'] = 'input parts rated for the range'
        self.assertTrue(any('criterion' in e and '模板' in e for e in self.errors(value)))

    def test_an_interpretation_copied_from_the_original_text_is_refused(self):
        value = intent(interpretations={'REQ-IN-01': '工作输入 9–36 V DC；40 V 持续 100 ms 不损坏'})
        self.assertTrue(any('抄了需求原文' in e for e in self.errors(value)))


class PlanTests(unittest.TestCase):
    def test_one_row_per_requirement_and_aspect_with_the_template_criterion(self):
        plan = build_review_plan(DB, intent({'REQ-TEMP-01': ['ENVIRONMENT', 'LIFETIME']}))
        temp = rows(plan, 'REQ-TEMP-01')
        self.assertEqual(sorted(r['object']['aspect'] for r in temp), sorted(catalog.requirement_aspects(['ENVIRONMENT', 'LIFETIME'])))
        for row in temp:
            self.assertEqual(row['criterion'], catalog.requirement_criterion(row['object']['aspect']))
            self.assertEqual(row['interpretation'], 'synthetic reading of REQ-TEMP-01')
            self.assertEqual(row['source_text']['columns'][0]['text'], '工作环境温度 −20～+60°C')
        self.assertEqual(len({r['id'] for r in rows(plan)}), len(rows(plan)))
        self.assertEqual(len({r['check_key'] for r in rows(plan)}), len(rows(plan)))

    def test_the_interpretation_stays_out_of_the_check_identity(self):
        a = build_review_plan(DB, intent())
        b = build_review_plan(DB, intent(interpretations={k: 'another reading' for k in ('REQ-IN-01', 'REQ-TEMP-01', 'REQ-OPEN-01')}))
        self.assertEqual([r['check_key'] for r in rows(a)], [r['check_key'] for r in rows(b)])
        self.assertNotEqual([r['interpretation'] for r in rows(a)], [r['interpretation'] for r in rows(b)])
        for row in rows(a):
            self.assertEqual(row['check_key'], check_key.key(row, a['assemblies']))

    def test_another_category_asks_other_aspects(self):
        a = build_review_plan(DB, intent())
        b = build_review_plan(DB, intent({'REQ-TEMP-01': ['ENVIRONMENT', 'PROTECTION']}))
        extra = {r['check_key'] for r in rows(b)} - {r['check_key'] for r in rows(a)}
        self.assertEqual(len(extra), len(catalog.REQUIREMENT_CATEGORIES['PROTECTION'].aspects))


if __name__ == '__main__':
    unittest.main()

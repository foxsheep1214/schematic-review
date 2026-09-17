"""规则总表的一致性：编号、文档、代码引用与生成的计划项。"""
import pathlib
import re
import sys
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

import catalog
from checkers import REGISTRY_BY_ID
from lint import Lint
from plan_review import FEATURE_CATALOG, build_review_plan
from test_checkers_framework import whole_board

RULE_TOKEN = re.compile(r'(?<![A-Za-z0-9])[A-Z]{3}-[AETCDVQH]\d{2}(?![0-9])')
SOURCE_FILES = {
    'lint': ['lint.py'],
    'plan': ['plan_review.py', 'catalog.py'],
    'revision': ['revision_impact.py', 'diff_netlists.py', 'plan_review.py'],
}


def source_text(source):
    if source in REGISTRY_BY_ID:
        module = sys.modules[type(REGISTRY_BY_ID[source]).__module__]
        return pathlib.Path(module.__file__).read_text(encoding='utf-8')
    return ''.join((SCRIPTS / name).read_text(encoding='utf-8') for name in SOURCE_FILES[source])


class CatalogTest(unittest.TestCase):
    def test_numbers_are_contiguous_within_each_domain_and_method(self):
        groups = {}
        for rule in catalog.RULES:
            groups.setdefault(rule.id[:5], []).append(int(rule.id[5:]))
        for group, numbers in groups.items():
            with self.subTest(group):
                self.assertEqual(sorted(numbers), list(range(1, len(numbers) + 1)))

    def test_every_source_is_a_known_generator(self):
        generators = set(REGISTRY_BY_ID) | set(SOURCE_FILES) | {'manual'}
        self.assertEqual(set(catalog.SOURCES), generators)

    def test_generated_rules_are_implemented_where_the_catalog_says(self):
        tables = {rule for ids in catalog.CIRCUIT_TYPES.values() for rule in ids}
        tables |= set(catalog.COVERAGE_RULES.values())
        for rule in catalog.RULES:
            if rule.source == 'manual':
                continue
            with self.subTest(rule.id):
                if rule.source == 'plan' and rule.id in tables:
                    continue
                self.assertRegex(source_text(rule.source), re.escape("'%s'" % rule.id))

    def test_manual_rules_are_not_generated_by_scripts(self):
        manual = {rule.id for rule in catalog.rules(source='manual')}
        for path in sorted(SCRIPTS.glob('*.py')) + sorted((SCRIPTS / 'checkers').glob('*.py')):
            if path.name == 'catalog.py':
                continue
            with self.subTest(path.name):
                self.assertEqual(set(RULE_TOKEN.findall(path.read_text(encoding='utf-8'))) & manual, set())

    def test_every_rule_token_in_code_and_docs_is_registered(self):
        paths = sorted(SCRIPTS.glob('*.py')) + sorted((SCRIPTS / 'checkers').glob('*.py'))
        paths += sorted((ROOT / 'references').glob('*.md')) + [ROOT / 'SKILL.md']
        for path in paths:
            with self.subTest(path.name):
                unknown = set(RULE_TOKEN.findall(path.read_text(encoding='utf-8'))) - set(catalog.BY_ID)
                self.assertEqual(unknown, set())

    def test_reference_document_matches_catalog(self):
        path = ROOT / 'references' / 'check-catalog.md'
        text = path.read_text(encoding='utf-8')
        self.assertEqual(catalog.render_doc(text), text,
                         'run: python3 scripts/catalog.py --write-doc references/check-catalog.md')

    def test_feature_and_coverage_rules_are_coverage_audits(self):
        rules = [config['rule'] for config in FEATURE_CATALOG.values()] + list(catalog.COVERAGE_RULES.values())
        self.assertEqual({catalog.method_of(rule) for rule in rules}, {'Q'})

    def test_spec_errors_detect_mismatches(self):
        item = {'id': 'PWR-E01.U1-1', 'rule': 'PWR-E01', 'method': 'E', 'domain': 'PWR'}
        self.assertEqual(catalog.spec_errors(item), [])
        self.assertTrue(catalog.spec_errors(dict(item, method='C')))
        self.assertTrue(catalog.spec_errors(dict(item, id='U1-1')))
        self.assertTrue(catalog.spec_errors(dict(item, rule='Rule-08')))


class GeneratedOutputTest(unittest.TestCase):
    def test_plan_items_and_lint_outputs_use_registered_rules(self):
        db = whole_board()
        intent = {'schema_version': 2, 'expect': {'SOC': 1},
                  'features': {'CUSTOM': {'applicability': 'APPLICABLE', 'citation': 'synthetic requirement'}},
                  'requirements': [{'id': 'REQ-1', 'text': 'synthetic', 'citation': 'synthetic',
                                    'criterion': 'synthetic criterion'}],
                  'circuits': [{'id': 'C-' + name, 'type': name, 'refs': ['U1'], 'states': ['run'],
                                'citation': 'synthetic'} for name in catalog.CIRCUIT_TYPES]}
        plan = build_review_plan(db, intent)
        for item in plan['checks']:
            with self.subTest(item['id']):
                self.assertEqual(catalog.spec_errors(item), [])
                self.assertNotEqual(catalog.get(item['rule']).source, 'manual')
        generated = {item['rule'] for item in plan['checks']}
        for rules in catalog.CIRCUIT_TYPES.values():
            self.assertTrue(set(rules) <= generated)
        self.assertTrue(set(catalog.COVERAGE_RULES.values()) <= generated)
        self.assertIn('REQ-Q06', generated)
        self.assertIn('REQ-A02', generated)
        for row in plan['rule_plan']:
            self.assertTrue(catalog.known(row['rule']), row['rule'])
            self.assertEqual(row['name'], catalog.title(row['rule']))
        log = 'ERROR (ORCAP-1): export stopped\n"No_connect" property on Pin "U4.6" ignored ... net "WDI_NET"'
        lint = Lint(db, log, intent)
        for finding in lint.run():
            with self.subTest(finding['rule']):
                self.assertIn(catalog.method_of(finding['rule']), 'AE')
        self.assertTrue(all(catalog.known(rule) for rule, _, _ in lint.skipped))


if __name__ == '__main__':
    unittest.main()

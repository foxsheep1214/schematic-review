"""规则总表的一致性：文档、代码引用与生成的计划项。"""
import copy
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
from plan_review import BOARD_MATERIALS, build_review_plan
from revision_impact import _global_scope
from test_checkers_framework import whole_board

RULE_TOKEN = re.compile(r'(?<![A-Za-z0-9])[A-Z]{3}-[AETCDVQH]\d{2}(?![0-9])')
SOURCE_FILES = {
    'lint': ['lint.py', 'board_scans.py'],
    'plan': ['plan_review.py', 'catalog.py'],
    'revision': ['revision_impact.py', 'diff_netlists.py', 'plan_review.py'],
}
GENERIC_SOURCES = {'package', 'board'}


def source_text(source):
    if source in REGISTRY_BY_ID:
        module = sys.modules[type(REGISTRY_BY_ID[source]).__module__]
        return pathlib.Path(module.__file__).read_text(encoding='utf-8')
    return ''.join((SCRIPTS / name).read_text(encoding='utf-8') for name in SOURCE_FILES[source])


class CatalogTest(unittest.TestCase):
    def test_every_source_is_a_known_generator(self):
        generators = set(REGISTRY_BY_ID) | set(SOURCE_FILES) | GENERIC_SOURCES
        self.assertEqual(set(catalog.SOURCES), generators)

    def test_rules_are_implemented_where_the_catalog_says(self):
        tables = set(catalog.COVERAGE_RULES.values())
        for rule in catalog.RULES:
            if rule.source in GENERIC_SOURCES or (rule.source == 'plan' and rule.id in tables):
                continue
            with self.subTest(rule.id):
                self.assertRegex(source_text(rule.source), re.escape("'%s'" % rule.id))

    def test_scope_matches_how_rules_are_generated(self):
        for rule in catalog.RULES:
            with self.subTest(rule.id):
                if rule.source == 'board':
                    self.assertEqual(rule.scope, 'board')
                if rule.source == 'package':
                    self.assertIn(rule.scope, ('circuit', 'link'))
        self.assertTrue(set(BOARD_MATERIALS) <= {r.id for r in catalog.rules()
                                                  if r.scope == 'board' and r.id[4] != 'Q'})

    def test_packages_list_reviewer_rules_only(self):
        for package in catalog.PACKAGES:
            with self.subTest(package.name):
                self.assertTrue(package.rules)
                self.assertEqual(len(package.rules), len(set(package.rules)))
                self.assertTrue(all(catalog.method_of(rule) in 'TCDV' for rule in package.rules))
                self.assertTrue(set(package.materials) <= {'requirements', 'datasheets', 'platform_checklist'})
                self.assertIsInstance(package.handoff.get('required'), bool)
        members = {rule for package in catalog.PACKAGES for rule in package.rules}
        self.assertEqual({r.id for r in catalog.rules(source='package')} - members, set())

    def test_every_rule_token_in_code_and_docs_is_registered(self):
        paths = sorted(SCRIPTS.glob('*.py')) + sorted((SCRIPTS / 'checkers').glob('*.py'))
        paths += sorted((ROOT / 'references').glob('*.md')) + [ROOT / 'SKILL.md', ROOT / 'README.md']
        for path in paths:
            with self.subTest(path.name):
                unknown = set(RULE_TOKEN.findall(path.read_text(encoding='utf-8'))) - set(catalog.BY_ID)
                self.assertEqual(unknown, set())

    def test_reference_document_matches_catalog(self):
        path = ROOT / 'references' / 'check-catalog.md'
        text = path.read_text(encoding='utf-8')
        self.assertEqual(catalog.render_doc(text), text,
                         'run: python3 scripts/catalog.py --write-doc references/check-catalog.md')

    def test_summary_and_coverage_rules_are_coverage_audits(self):
        rules = ['REQ-Q07', 'REQ-Q08'] + list(catalog.COVERAGE_RULES.values())
        self.assertEqual({catalog.method_of(rule) for rule in rules}, {'Q'})

    def test_spec_errors_detect_mismatches(self):
        item = {'id': 'PWR-E01.U1-1', 'rule': 'PWR-E01', 'method': 'E', 'domain': 'PWR'}
        self.assertEqual(catalog.spec_errors(item), [])
        self.assertTrue(catalog.spec_errors(dict(item, method='C')))
        self.assertTrue(catalog.spec_errors(dict(item, id='U1-1')))
        self.assertTrue(catalog.spec_errors(dict(item, rule='Rule-08')))


class GeneratedOutputTest(unittest.TestCase):
    def board(self):
        db = whole_board()
        db['parts']['J9'] = {'value': 'HEADER', 'part': 'HEADER', 'nc': False}
        db['nets']['EXT_IO'] = ['J9.1', 'U4.9']
        db['pin2net'].update({'J9.1': 'EXT_IO', 'U4.9': 'EXT_IO'})
        db['pinname'].update({'J9.1': '1', 'U4.9': 'GPIO2'})
        db['ref2page'] = {ref: 1 for ref in db['parts']}
        return db

    def test_every_generated_rule_is_registered_and_every_planned_rule_is_reachable(self):
        db = self.board()
        intent = {'schema_version': 3, 'expect': {'SOC': 1},
                  'features': {'CUSTOM': {'applicability': 'APPLICABLE', 'citation': 'synthetic requirement'}},
                  'requirements': [{'id': 'REQ-1', 'text': 'synthetic', 'citation': 'synthetic',
                                    'criterion': 'synthetic criterion'}],
                  'circuits': [{'id': 'C-' + p.name, 'type': p.name, 'refs': ['U1'], 'states': ['run'],
                                'citation': 'synthetic'} for p in catalog.PACKAGES]}
        plans = [build_review_plan(db, intent), build_review_plan(self.board())]
        generated = set()
        for plan in plans:
            for item in plan['checks']:
                with self.subTest(item['id']):
                    self.assertEqual(catalog.spec_errors(item), [])
                    if item.get('package') and item['rule'] != 'REQ-Q07':
                        self.assertIn(item['rule'], catalog.package(item['package']).rules)
                generated.add(item['rule'])
            for row in plan['rule_plan']:
                self.assertTrue(catalog.known(row['rule']), row['rule'])
                self.assertEqual(row['name'], catalog.title(row['rule']))
        expected = {r.id for r in catalog.rules() if r.source in ('plan', 'package', 'board')}
        self.assertEqual(expected - generated, set())
        custom = next(x for x in plans[0]['checks'] if x['rule'] == 'REQ-Q07' and x['package'] == 'CUSTOM')
        self.assertIn('自定义功能 CUSTOM', custom['criterion'])
        log = 'ERROR (ORCAP-1): export stopped\n"No_connect" property on Pin "U4.6" ignored ... net "WDI_NET"'
        lint = Lint(db, log, intent)
        for finding in lint.run():
            with self.subTest(finding['rule']):
                self.assertIn(catalog.method_of(finding['rule']), 'AE')
        self.assertTrue(all(catalog.known(rule) for rule, _, _ in lint.skipped))

    def test_board_and_package_items_are_revision_global(self):
        plan = build_review_plan(self.board())
        for item in plan['checks']:
            obj = item['object']
            if obj.get('board') or obj.get('package'):
                with self.subTest(item['id']):
                    self.assertTrue(_global_scope(copy.deepcopy(item)))
        self.assertFalse(_global_scope(next(x for x in plan['checks'] if x['id'] == 'DEV-C05.U1')))


class ObjectiveAlignmentTest(unittest.TestCase):
    def test_every_active_rule_has_one_primary_objective(self):
        index = catalog.build_objective_index(catalog.BY_ID, catalog.OBJECTIVE_RULES)
        self.assertEqual(set(index), set(catalog.BY_ID))
        self.assertEqual(index, catalog.OBJECTIVE_BY_RULE)
        for package in catalog.PACKAGES:
            self.assertTrue(set(package.rules) <= set(index))

    def test_new_rule_without_alignment_is_rejected(self):
        with self.assertRaises(ValueError):
            catalog.build_objective_index(set(catalog.BY_ID) | {'NEW-RULE'}, catalog.OBJECTIVE_RULES)

    def test_duplicate_alignment_is_rejected(self):
        groups = copy.deepcopy(catalog.OBJECTIVE_RULES)
        groups['G2'] += (groups['G1'][0],)
        with self.assertRaises(ValueError):
            catalog.build_objective_index(catalog.BY_ID, groups)

    def test_unknown_alignment_is_rejected(self):
        groups = copy.deepcopy(catalog.OBJECTIVE_RULES)
        groups['G2'] += ('NET-A05',)
        with self.assertRaises(ValueError):
            catalog.build_objective_index(catalog.BY_ID, groups)

    def test_undefined_objective_is_rejected(self):
        groups = copy.deepcopy(catalog.OBJECTIVE_RULES)
        groups['UNDEFINED'] = groups.pop('G1')
        with self.assertRaises(ValueError):
            catalog.build_objective_index(catalog.BY_ID, groups)

    def test_empty_objective_cannot_hide_unassigned_rules(self):
        groups = copy.deepcopy(catalog.OBJECTIVE_RULES)
        groups['G2'] += groups['G1']
        groups['G1'] = ()
        with self.assertRaises(ValueError):
            catalog.build_objective_index(catalog.BY_ID, groups)


if __name__ == '__main__':
    unittest.main()

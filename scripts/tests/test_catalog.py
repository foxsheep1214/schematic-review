"""规则总表的一致性：稳定编号、文档、代码引用与生成的计划项。"""
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
LEDGER = pathlib.Path(__file__).with_name('issued_rule_ids.txt')
SOURCE_FILES = {
    'lint': ['lint.py'],
    'plan': ['plan_review.py', 'catalog.py'],
    'revision': ['revision_impact.py', 'diff_netlists.py', 'plan_review.py'],
}
GENERIC_SOURCES = {'package', 'board'}


def source_text(source):
    if source in REGISTRY_BY_ID:
        module = sys.modules[type(REGISTRY_BY_ID[source]).__module__]
        return pathlib.Path(module.__file__).read_text(encoding='utf-8')
    return ''.join((SCRIPTS / name).read_text(encoding='utf-8') for name in SOURCE_FILES[source])


def issued_ids():
    lines = LEDGER.read_text(encoding='utf-8').splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith('#')]


class StableNumberTest(unittest.TestCase):
    def test_published_numbers_are_never_dropped_or_added_silently(self):
        ledger = issued_ids()
        self.assertEqual(len(ledger), len(set(ledger)))
        issued = set(catalog.BY_ID) | set(catalog.RETIRED_BY_ID)
        self.assertEqual(set(ledger) - issued, set(), '已发布编号只能登记为废弃，不能删除')
        self.assertEqual(issued - set(ledger), set(),
                         '新编号接在所在组最大序号之后，并追加到 ' + LEDGER.name)

    def test_issued_numbers_are_contiguous_within_each_group(self):
        groups = {}
        for rule_id in list(catalog.BY_ID) + list(catalog.RETIRED_BY_ID):
            groups.setdefault(rule_id[:5], []).append(int(rule_id[5:]))
        for group, numbers in groups.items():
            with self.subTest(group):
                self.assertEqual(sorted(numbers), list(range(1, len(numbers) + 1)))

    def test_retired_numbers_point_to_active_rules(self):
        for item in catalog.RETIRED:
            with self.subTest(item.id):
                self.assertFalse(catalog.known(item.id))
                self.assertTrue(all(catalog.known(x) for x in item.replaced_by))
                with self.assertRaisesRegex(KeyError, '已废弃，改用 ' + item.replaced_by[0]):
                    catalog.get(item.id)
        errors = catalog.spec_errors({'id': 'NET-A05.X', 'rule': 'NET-A05', 'method': 'A', 'domain': 'NET'})
        self.assertEqual(errors, ['规则 NET-A05 已废弃，改用 NET-A04'])


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
        history = {'catalog.py', 'check-catalog.md'}
        for path in paths:
            with self.subTest(path.name):
                allowed = set(catalog.BY_ID)
                if path.name in history:
                    allowed |= set(catalog.RETIRED_BY_ID)
                unknown = set(RULE_TOKEN.findall(path.read_text(encoding='utf-8'))) - allowed
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


if __name__ == '__main__':
    unittest.main()

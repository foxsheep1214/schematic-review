"""The shared guideline rule library (G01–G09): the installed bundle is valid, its vocabulary is SR's circuit types
and device kinds, rules are selected by baseline and triggers, coverage sorts applicable rules, and ASG holds the
same three files (user 2026-10-31: 请开始执行这个方案).
"""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))

import catalog
import device_kinds
import guideline_rules as g

ASG = Path.home() / '.agents' / 'skills' / 'autonomous-schematic-generation'
SHARED = ('references/guideline-rules.json', 'references/guideline-rules.md', 'scripts/guideline_rules.py')


def rule(rid='G04-001', **changes):
    out = {'id': rid, 'title': 'RS-485 共模范围', 'spec': rid[:3], 'version': '0.1', 'status': 'active',
           'nature': 'shall', 'applies_when': {'circuit_types': ['RS485']}, 'inputs': [],
           'asg_action': '按共模范围选收发器', 'sr_check': '核对收发器共模范围覆盖工况',
           'source': [{'document': 'TI SLLA272', 'edition': 'C', 'clause': '§2', 'page': 3}],
           'closing_stage': 'schematic'}
    out.update(changes)
    return out


def bundle(*rules):
    base = copy.deepcopy(g.load())
    base['rules'] = sorted(rules, key=lambda r: r['id'])
    base['content_sha256'] = g.content_sha256(base['rules'])
    return base


class GuidelineRulesTests(unittest.TestCase):
    def test_installed_bundle_is_valid(self):
        self.assertEqual(g.bundle_errors(g.load()), [])

    def test_vocabulary_is_srs_circuit_types_and_device_kinds(self):
        vocabulary = g.load()['vocabulary']
        self.assertEqual(vocabulary['circuit_types'], [c.name for c in catalog.CIRCUIT_TYPES])
        self.assertEqual(vocabulary['device_kinds'], [k for k in device_kinds.KINDS if k != 'unknown'])
        self.assertEqual(g.load()['default_baseline'], 'industrial_telecom')

    def test_select_by_baseline_and_triggers(self):
        lib = bundle(rule('G04-001'),
                     rule('G05-001', applies_when={'device_kinds': ['fuse']}),
                     rule('G01-001', applies_when={'board': True}),
                     rule('G03-001', nature='project', applies_when={'board': True, 'baselines': ['aerospace']}),
                     rule('G04-002', status='draft'))
        pick = lambda **kw: [r['id'] for r in g.select(lib, **kw)]
        self.assertEqual(pick(), ['G01-001'])
        self.assertEqual(pick(circuit_types=['RS485'], device_kinds=['fuse']), ['G01-001', 'G04-001', 'G05-001'])
        self.assertEqual(pick(baseline='aerospace'), ['G01-001', 'G03-001'])

    def test_rule_card_refusals(self):
        cases = {
            'id must look like': rule('G3-005'),
            'spec must be': rule(spec='G05'),
            'public preview is not a source': rule(source=[{'document': 'IEC 60127-1 公开预览非全文', 'edition': '3.0',
                                                           'clause': '7', 'page': 9}]),
            'not in vocabulary': rule(applies_when={'circuit_types': ['RS-485']}),
            'needs board: true': rule(applies_when={'text': '总是'}),
            'project-specific rule': rule(nature='project', applies_when={'board': True}),
            'unknown fields': rule(extra=1),
            'names unknown rule': rule(relations={'primary': ['G01-099']}),
        }
        for words, card in cases.items():
            with self.subTest(words):
                self.assertTrue(any(words in e for e in g.bundle_errors(bundle(card))), g.bundle_errors(bundle(card)))
        stale = bundle(rule())
        stale['rules'][0]['title'] = '改了'
        self.assertIn('content_sha256 does not match the rules', g.bundle_errors(stale))

    def test_coverage_sorts_applicable_rules(self):
        lib = bundle(rule('G04-001'), rule('G04-002', closing_stage='pcb'), rule('G04-003'))
        result = g.coverage(lib, g.select(lib, circuit_types=['RS485']),
                            {'G04-001': ['C1'], 'G09-001': ['C2']}, {'G04-002': '无外部端口'})
        self.assertEqual(result['covered'], {'G04-001': ['C1']})
        self.assertEqual(result['not_applicable'], {'G04-002': '无外部端口'})
        self.assertEqual(result['uncovered'], ['G04-003'])
        self.assertEqual(result['downstream'], ['G04-002'])
        self.assertEqual(result['unknown_cited'], ['G09-001'])

    def test_scope_is_checked_against_the_vocabulary(self):
        lib = bundle(rule())
        scope = {'library_version': lib['library_version'], 'baseline': 'industrial_telecom',
                 'circuit_types': ['RS485'], 'device_kinds': ['fuse'], 'not_applicable': []}
        self.assertEqual(g.scope_errors(scope, lib), [])
        self.assertTrue(g.scope_errors(dict(scope, circuit_types=['RS-485']), lib))
        self.assertTrue(g.scope_errors(dict(scope, library_version='9.9'), lib))
        self.assertTrue(g.scope_errors(dict(scope, not_applicable=[{'id': 'G04-001'}]), lib))

    def test_build_gathers_registries(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = Path(tmp) / 'G04_信号与模拟链设计规范'
            spec.mkdir()
            (spec / 'G04_规则登记.json').write_text(json.dumps(
                {'spec': 'G04', 'version': '0.1', 'rules': [rule('G04-002'), rule('G04-001')]}), encoding='utf-8')
            built = g.build(tmp, g.load(), '0.1.0')
        self.assertEqual(g.bundle_errors(built), [])
        self.assertEqual([r['id'] for r in built['rules']], ['G04-001', 'G04-002'])
        self.assertEqual(built['specs'], {'G04': '0.1'})

    def test_the_library_is_part_of_the_engineering_identity(self):
        # a new library version reopens designs and reviews like any rule change (workflow-handoff.md)
        import skill_identity
        files = skill_identity.engineering_identity(ROOT)['files']
        self.assertTrue(set(SHARED) <= set(files), sorted(set(SHARED) - set(files)))
        self.assertNotIn('guideline-rules.json', skill_identity.NON_RULE_REFS)

    @unittest.skipUnless((ASG / SHARED[0]).is_file(), 'autonomous-schematic-generation without the rule library')
    def test_asg_holds_the_same_files(self):
        for name in SHARED:
            self.assertEqual((ASG / name).read_bytes(), (ROOT / name).read_bytes(), name)


if __name__ == '__main__':
    unittest.main()

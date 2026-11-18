"""The guideline rule library (G01–G09): the bundle assembled from the framework's registries is valid, SR's circuit types
and device kinds are names from its vocabulary, rules are selected by baseline and triggers, coverage sorts applicable rules,
and the identity names the framework files it was read from.
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
import guideline_criteria as g
import knowledge_source


def rule(rid='G04-001', **changes):
    out = {'id': rid, 'title': 'RS-485 共模范围', 'spec': rid[:3], 'status': 'active',
           'nature': 'shall', 'applies_when': {'circuit_types': ['RS485']}, 'inputs': [],
           'asg_action': '按共模范围选收发器', 'sr_check': '核对收发器共模范围覆盖工况',
           'source': [{'document': 'TI SLLA272', 'edition': 'C', 'clause': '§2', 'page': 3}],
           'closing_stage': 'schematic'}
    out.update(changes)
    return out


def bundle(*rules):
    base = copy.deepcopy(g.load())
    base['criteria'] = sorted(rules, key=lambda r: r['id'])
    return base


def unreachable_rules(library):
    """Active item rules with no SR check that can reach them: a rule triggered by circuit types needs a check of one of
    those types or one not tied to a type; a board rule needs a check not tied to a subject. REQ-Q09 holds the others."""
    held = {}
    for check, targets in catalog.BASIS.items():
        for target in targets:
            held.setdefault(target, []).append(check)
    out = []
    for card in library['criteria']:
        if card['status'] != 'active' or g.coverage_class(card) != 'item':
            continue
        checks = held.get(card['id'], [])
        types = set(card['applies_when'].get('circuit_types', ()))
        if types:
            reached = any(catalog.BY_ID[c].source != 'subject' or types & set(catalog.circuit_types_of(c)) for c in checks)
        elif card['applies_when'].get('board'):
            reached = any(catalog.BY_ID[c].source != 'subject' for c in checks)
        else:
            reached = bool(checks)
        if not reached:
            out.append(card['id'])
    return out


class GuidelineRulesTests(unittest.TestCase):
    def test_framework_bundle_is_valid(self):
        self.assertEqual(g.bundle_errors(g.load()), [])


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
        scope = {'baseline': 'industrial_telecom',
                 'circuit_types': ['RS485'], 'device_kinds': ['fuse'], 'not_applicable': []}
        self.assertEqual(g.scope_errors(scope, lib), [])
        self.assertTrue(g.scope_errors(dict(scope, circuit_types=['RS-485']), lib))
        self.assertTrue(g.scope_errors(dict(scope, not_applicable=[{'id': 'G04-001'}]), lib))

    def test_build_gathers_registries(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = Path(tmp)  # 构建只读直接子登记；历史子目录由发布测试验证不读
            (spec / 'G04_准则登记.json').write_text(json.dumps(
                {'spec': 'G04', 'criteria': [rule('G04-002'), rule('G04-001')]}), encoding='utf-8')
            built = g.build(tmp)
        self.assertEqual(g.bundle_errors(built), [])
        self.assertEqual([r['id'] for r in built['criteria']], ['G04-001', 'G04-002'])

    def test_engineering_values_are_gathered_checked_and_read(self):
        value = {'value': 0.3, 'applies': '只有典型值时的估算范围', 'basis': '工程判断', 'confirmed': '2026-11-01'}
        cites = rule('G02-001', asg_action='按 `typical_band` 估算，裕量取 g03_budget_margin')
        with tempfile.TemporaryDirectory() as tmp:
            for spec, values, rules in (('G02', {'typical_band': value}, [cites]),
                                        ('G03', {'g03_budget_margin': dict(value, value=0)}, [])):
                (Path(tmp) / ('%s_准则登记.json' % spec)).write_text(json.dumps(
                    {'spec': spec, 'criteria': rules, 'engineering_values': values}), encoding='utf-8')
            built = g.build(tmp)
            self.assertEqual(g.bundle_errors(built), [])
            self.assertEqual(built['engineering_values']['typical_band']['spec'], 'G02')
            self.assertEqual(g.engineering_value('g03_budget_margin', built), 0)
            # a cited name the bundle does not hold, and one name defined by two specs
            missing = copy.deepcopy(built)
            del missing['engineering_values']['g03_budget_margin']
            self.assertTrue(any('g03_budget_margin' in e for e in g.bundle_errors(missing)))
            (Path(tmp) / 'G03_准则登记.json').write_text(json.dumps(
                {'spec': 'G03', 'criteria': [], 'engineering_values': {'typical_band': value}}),
                encoding='utf-8')
            with self.assertRaises(ValueError):
                g.build(tmp)


    def test_the_coverage_field_is_checked_and_a_library_without_it_is_as_before(self):
        def field_errors(*rules):
            return [e for e in g.bundle_errors(bundle(*rules)) if ': coverage must' in e or 'a handoff rule closes' in e]
        self.assertEqual(field_errors(rule(), rule('G04-002', coverage='item'), rule('G04-003', coverage='project_input'),
                                      rule('G04-004', coverage='handoff', closing_stage='pcb')), [])
        self.assertEqual(len(field_errors(rule(coverage='batch'))), 1)
        self.assertEqual(len(field_errors(rule(coverage='handoff'))), 1)
        plain = bundle(rule(applies_when={'board': True}))
        self.assertNotIn('by_coverage', g.coverage(plain, plain['criteria'], {}))

    def test_coverage_lists_the_three_classes_and_only_an_answer_covers_a_project_input(self):
        rules = [rule('G04-001', applies_when={'board': True}),
                 rule('G04-002', applies_when={'board': True}, coverage='project_input'),
                 rule('G04-003', applies_when={'board': True}, coverage='handoff', closing_stage='pcb')]
        library = bundle(*rules)
        found = g.coverage(library, rules, {'G04-002': ['calc:C1'], 'G04-003': ['work:W1']})
        self.assertEqual(found['by_coverage'], {'item': ['G04-001'], 'project_input': ['G04-002'], 'handoff': ['G04-003']})
        self.assertEqual(found['uncovered'], ['G04-001', 'G04-002'])
        found = g.coverage(library, rules, {'G04-001': ['calc:C1']}, answered={'G04-002': 'R1'})
        self.assertEqual(found['covered']['G04-002'], ['baseline:R1'])
        self.assertEqual(found['uncovered'], ['G04-003'])


if __name__ == '__main__':
    unittest.main()

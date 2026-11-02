"""The shared guideline rule library (G01–G09): the installed bundle is valid, its vocabulary is SR's circuit types
and device kinds, rules are selected by baseline and triggers, coverage sorts applicable rules, and ASG holds the
same shared layer, byte for byte (user 2026-10-31: 请开始执行这个方案; 2026-11-02: 目录制).
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

ASG = Path.home() / '.agents' / 'skills' / 'autonomous-schematic-generation'
SHARED = g.SHARED_FILES


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
    base['criteria'] = sorted(rules, key=lambda r: r['id'])
    base['content_sha256'] = g.content_sha256(base['criteria'])
    return base


class GuidelineRulesTests(unittest.TestCase):
    def test_installed_bundle_is_valid(self):
        self.assertEqual(g.bundle_errors(g.load()), [])

    def test_srs_circuit_types_and_device_kinds_are_the_shared_vocabulary(self):
        # 2026-11-02 (user: 词表进共用层): vocabulary.json is the one place the names and titles live; the catalog and
        # the device-kind registry are checked against it, and the bundle carries a copy build() takes from it
        shared = json.loads(g.VOCABULARY_PATH.read_text(encoding='utf-8'))
        self.assertEqual([(x['name'], x['title']) for x in shared['circuit_types']], [(c.name, c.title) for c in catalog.CIRCUIT_TYPES])
        self.assertEqual([(x['name'], x['title']) for x in shared['device_kinds']],
                         [(k, v.title) for k, v in device_kinds.KINDS.items() if k != 'unknown'])
        self.assertEqual(shared['default_baseline'], 'industrial_telecom')
        self.assertEqual(g.load()['vocabulary'], g.vocabulary()['vocabulary'])
        self.assertEqual(g.load()['default_baseline'], g.vocabulary()['default_baseline'])
        stale = copy.deepcopy(g.load())
        stale['vocabulary']['circuit_types'] = stale['vocabulary']['circuit_types'][1:]
        self.assertTrue(any('vocabulary.json' in e for e in g.bundle_errors(stale)))

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
        stale['criteria'][0]['title'] = '改了'
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
            (spec / 'G04_准则登记.json').write_text(json.dumps(
                {'spec': 'G04', 'version': '0.1', 'criteria': [rule('G04-002'), rule('G04-001')]}), encoding='utf-8')
            built = g.build(tmp, '0.1.0')
        self.assertEqual(g.bundle_errors(built), [])
        self.assertEqual([r['id'] for r in built['criteria']], ['G04-001', 'G04-002'])
        self.assertEqual(built['specs'], {'G04': '0.1'})

    def test_engineering_values_are_gathered_checked_and_read(self):
        value = {'value': 0.3, 'applies': '只有典型值时的估算范围', 'basis': '工程判断', 'confirmed': '2026-11-01'}
        cites = rule('G02-001', asg_action='按 `typical_band` 估算，裕量取 g03_budget_margin')
        with tempfile.TemporaryDirectory() as tmp:
            for spec, values, rules in (('G02', {'typical_band': value}, [cites]),
                                        ('G03', {'g03_budget_margin': dict(value, value=0)}, [])):
                (Path(tmp) / ('%s_准则登记.json' % spec)).write_text(json.dumps(
                    {'spec': spec, 'version': '1.1', 'criteria': rules, 'engineering_values': values}), encoding='utf-8')
            built = g.build(tmp, '1.0.0')
            self.assertEqual(g.bundle_errors(built), [])
            self.assertEqual(built['engineering_values']['typical_band']['spec'], 'G02')
            self.assertEqual(g.engineering_value('g03_budget_margin', built), 0)
            # the hash covers the values: changing one without rebuilding is caught
            stale = copy.deepcopy(built)
            stale['engineering_values']['typical_band']['value'] = 0.5
            self.assertTrue(any('content_sha256' in e for e in g.bundle_errors(stale)))
            # a cited name the bundle does not hold, and one name defined by two specs
            missing = copy.deepcopy(built)
            del missing['engineering_values']['g03_budget_margin']
            missing['content_sha256'] = g.content_sha256(missing['criteria'], missing['engineering_values'])
            self.assertTrue(any('g03_budget_margin' in e for e in g.bundle_errors(missing)))
            (Path(tmp) / 'G03_准则登记.json').write_text(json.dumps(
                {'spec': 'G03', 'version': '1.1', 'criteria': [], 'engineering_values': {'typical_band': value}}),
                encoding='utf-8')
            with self.assertRaises(ValueError):
                g.build(tmp, '1.0.0')

    def test_every_active_rule_has_an_sr_check_that_can_reach_it(self):
        # user 2026-11-01: 一次做全 — no rule waits for a check. A rule triggered by circuit types is held by a check of
        # one of those types, or by a check that is not tied to a circuit type.
        library = g.load()
        self.assertEqual(catalog.basis_errors({r['id'] for r in library['criteria']}), [])
        held = {}
        for check, targets in catalog.BASIS.items():
            for target in targets:
                held.setdefault(target, []).append(check)
        for card in library['criteria']:
            if card['status'] != 'active':
                continue
            with self.subTest(card['id']):
                checks = held.get(card['id'], [])
                self.assertTrue(checks)
                types = set(card['applies_when'].get('circuit_types', ()))
                if types:
                    self.assertTrue(any(catalog.BY_ID[c].source != 'subject' or types & set(catalog.circuit_types_of(c))
                                        for c in checks), checks)
                elif card['applies_when'].get('board'):
                    self.assertTrue(any(catalog.BY_ID[c].source != 'subject' for c in checks), checks)

    def test_the_library_is_part_of_the_engineering_identity(self):
        # a new library version reopens designs and reviews like any rule change (workflow-handoff.md)
        import skill_identity
        files = skill_identity.engineering_identity(ROOT)['files']
        self.assertTrue(set(SHARED) <= set(files), sorted(set(SHARED) - set(files)))
        self.assertNotIn('guideline-criteria.json', skill_identity.NON_RULE_REFS)

    def test_the_shared_directory_holds_exactly_the_shared_files(self):
        # 2026-11-02 (user: 目录制): references/shared/ is the shared layer; a file there is shared or does not belong
        listed = {Path(n).name for n in SHARED if n.startswith('references/shared/')}
        self.assertEqual(sorted(p.name for p in g.SHARED_DIR.iterdir() if p.name != '__pycache__'), sorted(listed))
        self.assertIn('scripts/guideline_criteria.py', SHARED)
        self.assertEqual(len(g.shared_digest()), 64)
        self.assertEqual(g.shared_versions()['library_version'], g.load()['library_version'])
        self.assertRegex(g.shared_label(), r'^共用层 [0-9a-f]{12}，设计准则库 \S+，降额 v\d+$')

    def test_dc_24v_checks_its_declared_window_not_the_telecom_48v_one(self):
        subjects = {t.name: t.subjects for t in catalog.CIRCUIT_TYPES}['DC_24V']
        self.assertIn('PWR-C27', subjects)
        self.assertNotIn('PWR-C17', subjects)
        self.assertIn('DC_24V', catalog.EXTERNAL_INTERFACE_TYPES)
        mapped = {gid for rule in subjects for gid in catalog.BASIS[rule]}
        self.assertTrue({'G01-051', 'G01-052', 'G01-053', 'G01-054'} <= mapped)

    @unittest.skipUnless((ASG / SHARED[1]).is_file(), 'autonomous-schematic-generation without the rule library')
    def test_asg_holds_the_same_shared_layer(self):
        for name in SHARED:
            self.assertEqual((ASG / name).read_bytes(), (ROOT / name).read_bytes(), name)
        self.assertEqual(g.shared_digest(ASG), g.shared_digest())


if __name__ == '__main__':
    unittest.main()

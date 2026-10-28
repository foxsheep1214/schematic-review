"""The derating spec (I/II/III levels from T/CPSS 1013, GJB/Z 35 and T/CPSS 1006) is one file shared with
autonomous-schematic-generation: every rule names a device kind, a measure, a condition and a cited page, the levels
run from most to least derating, and both repositories hold the same bytes (user 2026-10-27).
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))

import device_kinds

REFS = ROOT / 'references'
SPEC = json.loads((REFS / 'derating-rules.json').read_text(encoding='utf-8'))
ASG = Path.home() / '.agents' / 'skills' / 'autonomous-schematic-generation' / 'references'
LEVELS = ('I', 'II', 'III')
RISING = {'ratio', 'pulse_ratio', 'tj_percent', 'max_c', 'max_rise_k', 'max_v'}
FALLING = {'margin_c', 'min_hours', 'min_years'}


class DeratingSpecTests(unittest.TestCase):
    def test_every_rule_names_a_device_kind_a_measure_and_a_cited_page(self):
        kinds = set(device_kinds.KINDS) | set(SPEC['extra_kinds'])
        self.assertEqual(SPEC['levels'], list(LEVELS))
        for rule in SPEC['rules']:
            self.assertTrue(set(rule['kinds']) <= kinds, rule['id'])
            self.assertIn(rule['measure'], SPEC['measures'], rule['id'])
            self.assertIn(rule['condition'], SPEC['conditions'], rule['id'])
            self.assertTrue(1 <= rule['page'] <= SPEC['sources'][rule['source']]['pages'], rule['id'])
            self.assertEqual(tuple(rule['values']), LEVELS, rule['id'])

    def test_a_kind_holding_several_technologies_names_each_rules_subtype(self):
        # R7 (Codex review 2026-10-27): silicon MOS, IGBT, GaN and SiC share the mosfet kind, a crystal and an
        # oscillator the crystal kind; the subtype keeps a GaN gate rule off a silicon MOSFET
        for rule in SPEC['rules']:
            mixed = [k for k in rule['kinds'] if k in SPEC['subtypes']]
            if mixed:
                self.assertIn(rule.get('subtype'), SPEC['subtypes'][mixed[0]], rule['id'])
            else:
                self.assertNotIn('subtype', rule, rule['id'])

    def test_levels_run_from_most_to_least_derating(self):
        for rule in SPEC['rules']:
            v = [rule['values'][k] for k in LEVELS]
            if rule['measure'] in RISING:
                self.assertEqual(v, sorted(v), rule['id'])
            elif rule['measure'] in FALLING:
                self.assertEqual(v, sorted(v, reverse=True), rule['id'])
            if not SPEC['sources'][rule['source']]['graded']:
                self.assertEqual(len(set(map(str, v))), 1, rule['id'])

    def test_the_document_lists_every_rule(self):
        text = (REFS / 'derating-rules.md').read_text(encoding='utf-8')
        listed = re.findall(r'^\| ([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+) \|', text, flags=re.M)
        self.assertEqual(sorted(listed), sorted(r['id'] for r in SPEC['rules']))

    @unittest.skipUnless((ASG / 'derating-rules.json').is_file(), 'autonomous-schematic-generation not installed')
    def test_asg_holds_the_same_files(self):
        for name in ('derating-rules.json', 'derating-rules.md', 'stress-spec.md'):
            self.assertEqual((ASG / name).read_bytes(), (REFS / name).read_bytes(), name)


if __name__ == '__main__':
    unittest.main()

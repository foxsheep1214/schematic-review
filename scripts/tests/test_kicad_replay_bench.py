"""KiCad replay bench: fixtures stay frozen and the current SR still meets every frozen answer."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / 'evals' / 'kicad_replay_bench'
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(BENCH))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_fixtures  # noqa: E402
import run  # noqa: E402
from parse_kicad import parse  # noqa: E402
from test_parse_kicad import comp, net, netlist  # noqa: E402

REQUIRED = {'parse.strict_exit', 'parse.strict_db_written', 'parse.self_check_passed',
            'parse.missing_functional_pins', 'lint.DOC-A01_executed', 'lint.DOC-A02_executed',
            'plan.DOC-Q01', 'plan.checks_total', 'plan.not_applicable', 'decoupling.discovery_gaps',
            'decoupling.pin_names_resolved_by_official_pinout', 'decoupling.group_gaps'}


def load(name):
    return json.loads((BENCH / name).read_text(encoding='utf-8'))


class FrozenInputsTests(unittest.TestCase):
    def test_fixtures_match_the_manifest_and_size_limit(self):
        sources = load('sources.json')
        for item in sources['sources'] + sources['intents']:
            entry = item.get('fixture', item)
            data = (BENCH / entry['path']).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), entry['sha256'], entry['path'])
            self.assertLessEqual(len(data), make_fixtures.LIMIT, entry['path'])
        for src in sources['sources']:
            self.assertTrue(src['upstream']['license'] and src['upstream']['commit'], src['id'])

    def test_every_case_has_a_complete_frozen_answer(self):
        cases, expected = load('cases.json')['cases'], load('expected.json')['cases']
        self.assertEqual({c['id'] for c in cases}, set(expected))
        for case in cases:
            self.assertTrue((BENCH / case['fixture']).exists(), case['id'])
            answer = expected[case['id']]
            self.assertLessEqual(REQUIRED, set(answer['fields']), case['id'])
            self.assertTrue(answer['verification'].strip(), case['id'])
            for field, known in answer.get('known_deviations', {}).items():
                self.assertNotEqual(known['observed'], answer['fields'][field], case['id'])
                self.assertTrue(known['reason'].strip())

    def test_slimming_keeps_the_parsed_db(self):
        xml = netlist(comp('U1', 'Regulator_Linear', 'LDO', 'X', fields='<field name="MPN">LDO-1</field>')
                      + comp('R1', 'Device', 'R', '10k', properties='<property name="dnp"/>'),
                      net('VIN', ('U1', '1', 'VIN_1', 'power_in'), ('R1', '1', '', 'passive'))
                      + net('VOUT', ('U1', '3', 'VOUT', 'power_out'), ('R1', '2', '', 'passive')))
        self.assertEqual(parse(make_fixtures.slim(xml)), parse(xml))


class JudgeTests(unittest.TestCase):
    EXPECTED = {'cases': {'c': {'fields': {'a': 1, 'b': True},
                                'known_deviations': {'b': {'observed': False, 'reason': 'pending fix'}}}}}

    def statuses(self, observed):
        return {r['field']: r['status'] for r in run.judge('c', observed, self.EXPECTED)}

    def test_match_known_and_mismatch(self):
        self.assertEqual(self.statuses({'a': 1, 'b': True}), {'a': 'MATCH', 'b': 'MATCH'})
        self.assertEqual(self.statuses({'a': 1, 'b': False}), {'a': 'MATCH', 'b': 'KNOWN'})
        self.assertEqual(self.statuses({'a': 2, 'b': None}), {'a': 'MISMATCH', 'b': 'MISMATCH'})

    def test_error_and_unknown_case_are_mismatches(self):
        self.assertEqual(self.statuses({'error': 'boom'}), {'error': 'MISMATCH'})
        self.assertEqual(run.judge('other', {}, self.EXPECTED)[0]['status'], 'MISMATCH')

    def test_compare_lists_changed_fields_only(self):
        diff = run.changes({'c': {'a': 1, 'b': [1]}, 'gone': {}}, {'c': {'a': 1, 'b': [2]}})
        self.assertEqual(diff['c'], {'b': {'before': [1], 'after': [2]}})
        self.assertIn('gone', diff)


class CurrentTreeTests(unittest.TestCase):
    def test_current_sr_has_no_mismatch(self):
        expected = load('expected.json')
        for case in load('cases.json')['cases']:
            with self.subTest(case=case['id']), tempfile.TemporaryDirectory() as tmp:
                observed = run.observe(ROOT, case, Path(tmp))
                bad = [r for r in run.judge(case['id'], observed, expected) if r['status'] == 'MISMATCH']
                self.assertEqual(bad, [])


if __name__ == '__main__':
    unittest.main()

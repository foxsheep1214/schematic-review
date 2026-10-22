"""Two reviews of one board are aligned by circuit, row, open item and finding, and their differences counted.

The pair is synthetic and shaped like the 2026-10-21 R5 records: the same bias circuit named BIAS by one reviewer
and BIAS-SUPPLY by the other with states in different case, one row passed by one and left open by the other, a
finding only one of them raised, and a requirement row one of them made stage NA.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import compare_reviews as cr

ASPECT = '变换器电压裕量'


def side(name, states, verdict_run, finding=False, stage_na=False):
    circuit = name
    states_rows = [(s, 'PWR-C02.%s-%s.Q2' % (circuit, s)) for s in states]
    plan = {'schema_version': 5, 'db_sha256': 'abc', 'checks': [
        dict(id=cid, rule='PWR-C02', object={'circuit': circuit, 'ref': 'Q2', 'state': s}) for s, cid in states_rows
    ] + [{'id': 'DEV-C05.U1', 'rule': 'DEV-C05', 'object': {'ref': 'U1'}},
         {'id': 'REQ-D01.REQ-TEMP', 'rule': 'REQ-D01', 'object': {'requirement_id': 'REQ-TEMP'}}],
        'functions': [{'id': 'FN-' + circuit, 'circuit': circuit, 'circuit_type': 'POWER_CONVERTER',
                       'objects': {'refs': ['Q2', 'D2', 'C3'], 'nets': ['VCC']}, 'states': states,
                       'members': [{'check_id': cid, 'rule': 'PWR-C02', 'aspect': ASPECT, 'state': s} for s, cid in states_rows]}]}
    checks = []
    for s, cid in states_rows:
        row = {'id': cid, 'applicability': 'APPLICABLE', 'review_result': 'PASS', 'function_id': 'FN-' + circuit, 'aspect': ASPECT}
        if s.lower() == 'run' and verdict_run != 'PASS':
            row.update(review_result=verdict_run, open_ref='FN-%s/AUX' % circuit)
        checks.append(row)
    checks.append({'id': 'DEV-C05.U1', 'applicability': 'APPLICABLE', 'review_result': 'FAIL' if finding else 'PASS',
                   **({'finding_id': 'F-001'} if finding else {})})
    checks.append({'id': 'REQ-D01.REQ-TEMP', 'applicability': 'APPLICABLE', 'review_result': 'NA' if stage_na else 'PASS',
                   **({'na_reason': 'OUTSIDE_SCHEMATIC_STAGE'} if stage_na else {})})
    fn = {'id': 'FN-' + circuit, 'verdict': 'PASS' if verdict_run == 'PASS' else 'OPEN',
          'open': [] if verdict_run == 'PASS' else [{'key': 'AUX', 'kind': 'DESIGN_VALUE', 'what': '辅助电压没定',
                                                     'decides': [{'aspect': ASPECT, 'states': [s for s in states if s.lower() == 'run']}],
                                                     'severity': {'level': 'P1'}}],
          'fails': []}
    results = {'schema_version': 4, 'functions': [fn], 'checks': checks,
               'findings': [{'id': 'F-001', 'title': 'U1 超压', 'severity': 'P1', 'kind': 'DEFECT',
                             'check_ids': ['DEV-C05.U1'], 'location': {'refs': ['U1']}}] if finding else []}
    return {'where': name, 'plan': plan, 'results': results}


class CompareTests(unittest.TestCase):
    def pair(self):
        a = side('BIAS', ['startup', 'run'], 'PASS', finding=True)
        b = side('BIAS-SUPPLY', ['STARTUP', 'RUN', 'FAULT'], 'INSUFFICIENT', stage_na=True)
        return cr.compare(a, b)

    def test_circuits_are_aligned_by_type_and_parts_whatever_their_names_and_state_case(self):
        report = self.pair()
        self.assertEqual([(c['A'], c['B']) for c in report['circuits']['matched']], [('FN-BIAS', 'FN-BIAS-SUPPLY')])
        self.assertEqual(report['rows']['shared'], 4)   # startup, run, DEV-C05.U1, REQ-D01.REQ-TEMP
        self.assertEqual(report['rows']['only_B'], ['PWR-C02|C0|fault|Q2'])

    def test_differences_are_grouped_by_kind_with_both_rows_named(self):
        report = self.pair()
        kinds = {k: [d['key'] for d in v] for k, v in report['differences'].items()}
        self.assertEqual(kinds, {'one FAIL': ['DEV-C05.U1'], 'PASS vs INSUFFICIENT': ['PWR-C02|C0|run|Q2'],
                                 'NA vs judged': ['REQ-D01.REQ-TEMP']})
        run = report['differences']['PASS vs INSUFFICIENT'][0]
        self.assertEqual((run['A']['id'], run['B']['id'], run['B']['open_ref']),
                         ('PWR-C02.BIAS-run.Q2', 'PWR-C02.BIAS-SUPPLY-RUN.Q2', 'FN-BIAS-SUPPLY/AUX'))
        self.assertEqual(report['rows']['agree'], 1)
        self.assertEqual(report['rows']['verdicts']['B']['NA_STAGE'], 1)

    def test_findings_and_open_items_only_one_side_raised_are_listed(self):
        report = self.pair()
        self.assertEqual([f['id'] for f in report['findings']['only_A']], ['F-001'])
        self.assertEqual(report['findings']['only_B'], [])
        self.assertEqual([i['ref'] for i in report['open_items']['only_B']], ['FN-BIAS-SUPPLY/AUX'])
        self.assertEqual(report['open_items']['kinds']['B'], {'DESIGN_VALUE/P1': 1})

    def test_matching_records_agree_everywhere(self):
        a = side('BIAS', ['startup', 'run'], 'PASS')
        b = side('BIAS', ['startup', 'run'], 'PASS')
        report = cr.compare(a, b)
        self.assertEqual((report['rows']['shared'], report['rows']['agree'], report['differences']), (4, 4, {}))

    def test_cli_writes_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            for name, s in (('a', side('BIAS', ['run'], 'PASS')), ('b', side('BIAS', ['run'], 'INSUFFICIENT'))):
                rec = tmp / name / 'record'
                rec.mkdir(parents=True)
                (rec / 'review-plan.json').write_text(json.dumps(s['plan']), encoding='utf-8')
                (rec / 'review-results.json').write_text(json.dumps(s['results']), encoding='utf-8')
            code = cr.main([str(tmp / 'a'), str(tmp / 'b'), '--json', str(tmp / 'c.json'), '--md', str(tmp / 'c.md')])
            self.assertEqual(code, 0)
            report = json.loads((tmp / 'c.json').read_text(encoding='utf-8'))
            self.assertTrue(report['same_netlist'])
            self.assertIn('PASS vs INSUFFICIENT（1 行）', (tmp / 'c.md').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()

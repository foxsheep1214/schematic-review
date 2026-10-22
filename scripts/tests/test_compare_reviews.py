"""Two reviews of one board: the formal numbers count only rows that ask the same check (merge plan of
2026-10-21, §5); circuit, row, open-item and finding alignment by overlap is a suggestion layer outside them.

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
        self.assertEqual([(c['A'], c['B']) for c in report['suggested']['circuits']['matched']], [('FN-BIAS', 'FN-BIAS-SUPPLY')])
        self.assertEqual(report['suggested']['rows']['shared'], 4)   # startup, run, DEV-C05.U1, REQ-D01.REQ-TEMP
        self.assertEqual(report['suggested']['rows']['only_B'], ['PWR-C02|C0|fault|Q2'])

    def test_differences_are_grouped_by_kind_with_both_rows_named(self):
        report = self.pair()
        kinds = {k: [d['key'] for d in v] for k, v in report['suggested']['differences'].items()}
        self.assertEqual(kinds, {'one FAIL': ['DEV-C05.U1'], 'PASS vs INSUFFICIENT': ['PWR-C02|C0|run|Q2'],
                                 'NA vs judged': ['REQ-D01.REQ-TEMP']})
        run = report['suggested']['differences']['PASS vs INSUFFICIENT'][0]
        self.assertEqual((run['A']['id'], run['B']['id'], run['B']['open_ref']),
                         ('PWR-C02.BIAS-run.Q2', 'PWR-C02.BIAS-SUPPLY-RUN.Q2', 'FN-BIAS-SUPPLY/AUX'))
        self.assertEqual(report['suggested']['rows']['agree'], 1)
        self.assertEqual(report['suggested']['rows']['verdicts']['B']['NA_STAGE'], 1)

    def test_findings_and_open_items_only_one_side_raised_are_listed(self):
        report = self.pair()
        self.assertEqual([f['id'] for f in report['suggested']['findings']['only_A']], ['F-001'])
        self.assertEqual(report['suggested']['findings']['only_B'], [])
        self.assertEqual([i['ref'] for i in report['suggested']['open_items']['only_B']], ['FN-BIAS-SUPPLY/AUX'])
        self.assertEqual(report['suggested']['open_items']['kinds']['B'], {'DESIGN_VALUE/P1': 1})

    def test_matching_records_agree_everywhere(self):
        a = side('BIAS', ['startup', 'run'], 'PASS')
        b = side('BIAS', ['startup', 'run'], 'PASS')
        report = cr.compare(a, b)
        self.assertEqual((report['suggested']['rows']['shared'], report['suggested']['rows']['agree'], report['suggested']['differences']), (4, 4, {}))

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
            self.assertEqual(report['baseline']['status'], 'SAME_INPUT')
            text = (tmp / 'c.md').read_text(encoding='utf-8')
            self.assertIn('PASS vs INSUFFICIENT（1 行）', text)
            self.assertLess(text.index('## 精确配对'), text.index('## 建议配对'))



class StrictIdentityTests(unittest.TestCase):
    """Merge plan §5: rows are paired by check key (rule and its revision, object without display names, criterion).
    Exact pairs and verified aliases enter the metrics; overlap suggestions, duplicates and missing answers are listed
    apart, and every denominator is shown."""

    def test_i1_a_renamed_circuit_asks_the_same_checks(self):
        a = side('BIAS', ['RUN'], 'PASS')
        b = side('BIAS-SUPPLY', ['RUN'], 'PASS')
        strict = cr.compare(a, b)['strict']
        self.assertEqual(strict['counts']['exact'], 3)   # the RUN row, DEV-C05.U1, REQ-D01.REQ-TEMP
        self.assertEqual(strict['metrics']['agreement'], 1.0)
        self.assertEqual(strict['unmatched'], {'A': [], 'B': []})

    def test_i1_a_shortened_net_or_another_state_spelling_is_another_check(self):
        a = side('BIAS', ['run'], 'PASS')
        b = side('BIAS', ['RUN'], 'PASS')
        report = cr.compare(a, b)
        self.assertEqual(report['strict']['unmatched'], {'A': ['PWR-C02.BIAS-run.Q2'], 'B': ['PWR-C02.BIAS-RUN.Q2']})
        # the overlap layer still pairs them, as a suggestion only
        self.assertEqual(report['strict']['suggested_pairs'], [{'A': 'PWR-C02.BIAS-run.Q2', 'B': 'PWR-C02.BIAS-RUN.Q2'}])
        self.assertEqual(report['strict']['counts']['M'], 2)
        a['plan']['checks'][1]['object'] = {'net': '/A/TEMP'}
        b['plan']['checks'][1]['object'] = {'net': 'TEMP'}
        self.assertIn('DEV-C05.U1', cr.compare(a, b)['strict']['unmatched']['A'])

    def test_i2_a_verified_alias_counts_and_is_disclosed_an_unverified_one_does_not(self):
        a = side('BIAS', ['run'], 'PASS')
        b = side('BIAS', ['RUN'], 'PASS')
        alias = [{'A': 'PWR-C02.BIAS-run.Q2', 'B': 'PWR-C02.BIAS-RUN.Q2', 'evidence': 'intent states table 2: run = RUN'}]
        strict = cr.compare(a, b, alias)['strict']
        self.assertEqual((strict['counts']['exact'], strict['counts']['verified_alias'], strict['counts']['M']), (2, 1, 3))
        strict = cr.compare(a, b, [dict(alias[0], evidence='same thing')])['strict']
        self.assertEqual(strict['counts']['verified_alias'], 0)
        self.assertEqual(strict['aliases_refused'][0]['reason'], 'evidence locates nothing')

    def test_i3_duplicates_and_missing_answers_are_listed_and_lower_completeness(self):
        a = side('BIAS', ['RUN'], 'PASS')
        b = side('BIAS', ['RUN'], 'PASS')
        b['results']['checks'] = [c for c in b['results']['checks'] if c['id'] != 'DEV-C05.U1']
        a['plan']['checks'].append(dict(a['plan']['checks'][1], id='DEV-C05.U1-COPY'))
        strict = cr.compare(a, b)['strict']
        self.assertEqual(strict['duplicates']['A'][0]['ids'], ['DEV-C05.U1', 'DEV-C05.U1-COPY'])
        self.assertEqual(strict['counts']['M'], 2)
        self.assertEqual([m['A'] for m in strict['missing_result']], [])
        a = side('BIAS', ['RUN'], 'PASS')
        strict = cr.compare(a, b)['strict']
        self.assertEqual([m['A'] for m in strict['missing_result']], ['DEV-C05.U1'])
        self.assertEqual((strict['counts']['M'], strict['counts']['C']), (3, 2))
        self.assertAlmostEqual(strict['metrics']['answered_completeness'], 2 / 3)

    def test_metrics_with_their_denominators_and_the_fail_pass_list(self):
        a = side('BIAS', ['RUN'], 'PASS', finding=True)
        b = side('BIAS', ['RUN'], 'INSUFFICIENT', stage_na=True)
        strict = cr.compare(a, b)['strict']
        c = strict['counts']
        self.assertEqual((c['N_A'], c['N_B'], c['M'], c['C'], c['same']), (3, 3, 3, 3, 0))
        self.assertEqual(strict['metrics'], {'alignment_coverage': 1.0, 'answered_completeness': 1.0, 'agreement': 0.0,
                                             'full_agreement': 0.0})
        self.assertEqual([d['A'] for d in strict['fail_vs_pass']], ['DEV-C05.U1'])
        self.assertEqual([d['A'] for d in strict['severe_disagreements']], ['DEV-C05.U1'])
        self.assertIn({'A': 'PASS', 'B': 'NA_STAGE', 'rows': 1}, strict['transitions'])
        empty = cr.compare({'where': 'a', 'plan': {'checks': []}, 'results': {}}, {'where': 'b', 'plan': {'checks': []}, 'results': {}})
        self.assertEqual(empty['strict']['metrics']['agreement'], 'N/A')

    def test_a_different_netlist_is_a_baseline_mismatch_and_legacy_plans_are_named(self):
        a = side('BIAS', ['RUN'], 'PASS')
        b = side('BIAS', ['RUN'], 'PASS'); b['plan']['db_sha256'] = 'other'
        report = cr.compare(a, b)
        self.assertEqual(report['baseline']['status'], 'BASELINE_MISMATCH')
        self.assertEqual(report['strict']['contract'], {'A': 'LEGACY_CONTRACT', 'B': 'LEGACY_CONTRACT'})
        import check_key
        for check in a['plan']['checks']:
            check['check_key'] = check_key.key(check)
        a['plan']['checks'][0]['check_key'] = 'stale'
        strict = cr.compare(a, b)['strict']
        self.assertEqual((strict['contract']['A'], strict['stale_keys']['A']), ('CURRENT', ['PWR-C02.BIAS-RUN.Q2']))


if __name__ == '__main__':
    unittest.main()

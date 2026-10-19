"""review-results schema 3: what a reviewer writes, what is refused, and what is derived."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import results_model as rm


def gap(**extra):
    out = {'what': 'R503 calibration error budget', 'scope': '0 to 5 A, full temperature range',
           'how_to_close': 'Enumerate ADC gain/offset and shunt drift; define the calibration readback',
           'closure_criterion': 'PPS current window holds at every corner',
           'severity': {'level': 'P1', 'class': 'PERFORMANCE_OR_LIFE', 'affects': 'R503 current measurement',
                        'consequence': 'PPS current window cannot be guaranteed'}}
    out.update(extra)
    return out


def ledger(*rows):
    return {'schema_version': 3, 'checks': list(rows)}


def insufficient(*gaps, cause='DESIGN_OPEN'):
    return {'id': 'ANA-C01.R503', 'review_result': 'INSUFFICIENT', 'gap_cause': cause,
            'rationale': 'Offset is equivalent to 0.25 A', 'gaps': list(gaps)}


class ShapeTests(unittest.TestCase):
    def test_schema_2_is_refused_whole(self):
        self.assertEqual(len(rm.shape_errors({'schema_version': 2, 'checks': []})), 1)

    def test_retired_fields_are_named_with_their_replacement(self):
        report = ledger(dict(insufficient(gap()), missing_inputs=['x'], potential_severity='P1'))
        report['workflow_version'] = 2
        errors = rm.shape_errors(report)
        self.assertTrue(any('missing_inputs' in e and 'gaps[].what' in e for e in errors), errors)
        self.assertTrue(any('potential_severity' in e for e in errors), errors)
        self.assertTrue(any('workflow_version' in e for e in errors), errors)

    def test_defaults_are_not_written(self):
        for field, value in (('blocking', True), ('evidence_confidence', 'C'), ('disposition', 'OPEN')):
            with self.subTest(field=field):
                self.assertTrue(rm.shape_errors(ledger(dict(insufficient(gap()), **{field: value}))))
        self.assertEqual(rm.shape_errors(ledger(dict(insufficient(gap()), blocking=False))), [])
        self.assertTrue(rm.shape_errors(ledger({'id': 'X', 'review_result': 'PASS', 'blocking': False})))
        self.assertEqual(rm.shape_errors(ledger({'id': 'X', 'review_result': 'PASS', 'evidence_confidence': 'A'})), [])

    def test_request_gaps_need_scope_route_and_criterion(self):
        self.assertEqual(rm.shape_errors(ledger(insufficient(gap()))), [])
        for field in ('scope', 'how_to_close', 'closure_criterion'):
            with self.subTest(field=field):
                broken = gap(); del broken[field]
                self.assertTrue(rm.shape_errors(ledger(insufficient(broken))))

    def test_graded_gaps_need_a_complete_severity(self):
        for field in ('level', 'class', 'affects', 'consequence'):
            with self.subTest(field=field):
                broken = gap(); del broken['severity'][field]
                self.assertTrue(rm.shape_errors(ledger(insufficient(broken))))

    def test_requirement_gap_is_not_graded(self):
        row = insufficient({'what': 'Maximum load current'}, cause='REQUIREMENT_OPEN')
        self.assertEqual(rm.shape_errors(ledger(row)), [])
        row['gaps'][0]['severity'] = gap()['severity']
        self.assertTrue(rm.shape_errors(ledger(row)))

    def test_gap_names_are_distinct_and_only_on_insufficient(self):
        self.assertTrue(rm.shape_errors(ledger(insufficient(gap(), gap()))))
        self.assertTrue(rm.shape_errors(ledger({'id': 'X', 'review_result': 'PASS', 'gaps': [gap()]})))


class ExpandTests(unittest.TestCase):
    def test_derived_fields(self):
        row = rm.expand(ledger(insufficient(gap())))['checks'][0]
        self.assertIs(row['blocking'], True)
        self.assertEqual((row['evidence_confidence'], row['disposition']), ('C', 'OPEN'))
        self.assertEqual(row['missing_inputs'], ['R503 calibration error budget'])
        request = row['input_requests']['R503 calibration error budget']
        self.assertEqual(request['why_decisive'], row['rationale'])
        self.assertEqual(request['impact_assessment']['blocking_reason'], 'PPS current window holds at every corner')
        self.assertEqual(row['potential_severity'], 'P1')

    def test_row_level_is_the_worst_gap(self):
        worse = gap(what='Short-circuit waveform')
        worse['severity'] = dict(worse['severity'], level='P0', **{'class': 'DAMAGE_OR_HAZARD'},
                                 hazard_path='PROTECTION_LOSS')
        row = rm.expand(ledger(insufficient(gap(), worse)))['checks'][0]
        self.assertEqual(row['potential_severity'], 'P0')
        self.assertEqual(row['impact_assessment']['hazard_path'], 'PROTECTION_LOSS')
        self.assertEqual({k: v['potential_severity'] for k, v in row['input_requests'].items()},
                         {'R503 calibration error budget': 'P1', 'Short-circuit waveform': 'P0'})

    def test_non_request_causes_carry_no_request(self):
        row = rm.expand(ledger(insufficient({'what': 'Trace U2 enable path', 'scope': 'power-up',
                                             'severity': gap()['severity']}, cause='REVIEW_INCOMPLETE')))['checks'][0]
        self.assertNotIn('input_requests', row)
        self.assertEqual(row['potential_severity'], 'P1')

    def test_closure_domain_travels_with_its_gap(self):
        row = rm.expand(ledger(insufficient(gap(closure_domain='loop_stability'))))['checks'][0]
        self.assertEqual(row['input_requests']['R503 calibration error budget']['closure_domain'], 'loop_stability')

    def test_expand_is_idempotent_and_leaves_the_record_alone(self):
        report = ledger(insufficient(gap()))
        before = copy.deepcopy(report)
        once = rm.expand(report)
        self.assertEqual(report, before)
        self.assertEqual(rm.expand(once), once)
        self.assertLess(len(json.dumps(before)), len(json.dumps(once)))


if __name__ == '__main__':
    unittest.main()

"""review-results schema 4: what a reviewer writes, what is refused, and what is derived."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import results_model as rm

E = [{'source': 'evidence/engineering.md', 'locator': '## CURRENT'}]


def open_item(**extra):
    out = {'key': 'ADC-CAL', 'kind': 'DESIGN_VALUE', 'what': 'RS1 calibration error budget',
           'scope': '0 to 5 A, full temperature range', 'spec': 'zero 15 mA, gain 1%, drift 0.5%', 'owner': 'firmware',
           'closure': 'CC current window holds at every corner', 'decides': [{'aspect': '电流检测'}],
           'severity': {'level': 'P1', 'class': 'PERFORMANCE_OR_LIFE', 'affects': 'RS1 current measurement',
                        'consequence': 'CC current window cannot be guaranteed'}}
    out.update(extra)
    return out


def function(*items, **extra):
    fn = {'id': 'FN-CURRENT', 'question': 'Does RS1 sensing meet the CC current window', 'objects': {'refs': ['RS1']},
          'conditions': [{'id': 'c1', 'source': 'evidence/ds/U2.txt', 'locator': 'p12', 'says': 'ADC ±6 LSB', 'use': 'error budget'}],
          'calculation': {'result': '5.5 A reads 1.572 V'}, 'verdict': 'OPEN' if items else 'PASS',
          'open': list(items), 'evidence': E}
    fn.update(extra)
    return fn


def row(**extra):
    out = {'id': 'ANA-C01.RS1', 'review_result': 'INSUFFICIENT', 'rationale': 'Offset is equivalent to 0.25 A',
           'function_id': 'FN-CURRENT', 'aspect': '电流检测', 'open_ref': 'FN-CURRENT/ADC-CAL'}
    out.update(extra)
    return out


def ledger(*rows, functions=None):
    return {'schema_version': 4, 'functions': [function(open_item())] if functions is None else functions,
            'checks': list(rows)}


class ShapeTests(unittest.TestCase):
    def test_older_schemas_are_refused_whole(self):
        for version in (2, 3):
            self.assertEqual(len(rm.shape_errors({'schema_version': version, 'checks': [], 'functions': []})), 1)

    def test_retired_fields_are_named_with_their_replacement(self):
        report = ledger(row(gaps=[{'what': 'x'}], gap_cause='DESIGN_OPEN', missing_inputs=['x']))
        report['work_items'] = []
        errors = rm.shape_errors(report)
        self.assertTrue(any('gaps' in e and 'open_ref' in e for e in errors), errors)
        self.assertTrue(any('gap_cause' in e and 'kind' in e for e in errors), errors)
        self.assertTrue(any('missing_inputs' in e for e in errors), errors)
        self.assertTrue(any('work_items' in e for e in errors), errors)

    def test_functions_list_is_required(self):
        report = ledger(row()); del report['functions']
        self.assertTrue(any('functions' in e for e in rm.shape_errors(report)))

    def test_defaults_are_not_written(self):
        for field, value in (('blocking', True), ('evidence_confidence', 'C'), ('disposition', 'OPEN')):
            with self.subTest(field=field):
                self.assertTrue(rm.shape_errors(ledger(row(**{field: value}))))
        self.assertEqual(rm.shape_errors(ledger(row(blocking=False))), [])
        self.assertTrue(rm.shape_errors(ledger({'id': 'X', 'review_result': 'PASS', 'blocking': False})))
        self.assertEqual(rm.shape_errors(ledger({'id': 'X', 'review_result': 'PASS', 'evidence_confidence': 'A'})), [])

    def test_insufficient_names_its_open_item(self):
        self.assertEqual(rm.shape_errors(ledger(row())), [])
        broken = row(); del broken['open_ref']
        self.assertTrue(any('open_ref' in e for e in rm.shape_errors(ledger(broken))))
        self.assertTrue(rm.shape_errors(ledger(row(open_ref='FN-CURRENT/NOPE'))))
        self.assertTrue(rm.shape_errors(ledger(row(function_id='FN-OTHER'))))   # ref belongs to FN-CURRENT

    def test_refs_only_on_the_result_they_belong_to(self):
        self.assertTrue(rm.shape_errors(ledger(row(review_result='PASS'))))
        self.assertTrue(rm.shape_errors(ledger({'id': 'X', 'review_result': 'PASS', 'fail_ref': 'FN-CURRENT/ADC-CAL'})))

    def test_a_bound_row_names_its_aspect(self):
        broken = row(); del broken['aspect']
        self.assertTrue(any('aspect' in e for e in rm.shape_errors(ledger(broken))))


class ExpandTests(unittest.TestCase):
    def test_gap_fields_derive_from_the_open_item(self):
        out = rm.expand(ledger(row()))['checks'][0]
        self.assertIs(out['blocking'], True)
        self.assertEqual((out['evidence_confidence'], out['disposition']), ('C', 'OPEN'))
        self.assertEqual(out['gap_cause'], 'DESIGN_OPEN')
        self.assertEqual(out['missing_inputs'], ['RS1 calibration error budget'])
        request = out['input_requests']['RS1 calibration error budget']
        self.assertEqual(request['why_decisive'], out['rationale'])
        self.assertEqual(request['acquisition'], '由firmware确定：zero 15 mA, gain 1%, drift 0.5%')
        self.assertEqual(request['impact_assessment']['blocking_reason'], 'CC current window holds at every corner')
        self.assertEqual(out['potential_severity'], 'P1')

    def test_vendor_datum_derives_external_data_and_its_acquisition(self):
        item = open_item(kind='VENDOR_DATUM', acquisition='the vendor: CC DAC code table', checked=['c1'],
                         why_insufficient='p12 gives the ADC, not the DAC code', worst_case={'result': '±0.3 A'})
        del item['spec'], item['owner']
        out = rm.expand(ledger(row(), functions=[function(item)]))['checks'][0]
        self.assertEqual(out['gap_cause'], 'EXTERNAL_DATA')
        self.assertEqual(out['input_requests']['RS1 calibration error budget']['acquisition'], 'the vendor: CC DAC code table')

    def test_non_request_kinds_carry_no_request(self):
        item = {'key': 'TRACE', 'kind': 'REVIEW_INCOMPLETE', 'what': 'Trace U2 enable path', 'scope': 'power-up',
                'decides': [{'aspect': '电流检测'}], 'severity': open_item()['severity']}
        out = rm.expand(ledger(row(open_ref='FN-CURRENT/TRACE'), functions=[function(item)]))['checks'][0]
        self.assertEqual(out['gap_cause'], 'REVIEW_INCOMPLETE')
        self.assertNotIn('input_requests', out)
        self.assertEqual(out['potential_severity'], 'P1')

    def test_work_items_derive_one_per_open_item(self):
        out = rm.expand(ledger(row(), row(id='ANA-C02.RS1')))
        self.assertEqual([t['id'] for t in out['work_items']], ['W-ADC-CAL'])
        task = out['work_items'][0]
        self.assertEqual(task['check_ids'], ['ANA-C01.RS1', 'ANA-C02.RS1'])
        self.assertEqual((task['root_cause'], task['due_stage']), ('RS1 calibration error budget', 'design_iteration'))
        self.assertEqual(task['reason'], 'CC current window cannot be guaranteed')

    def test_requirement_items_and_fail_items(self):
        req = {'key': 'LOAD', 'kind': 'REQUIREMENT', 'what': 'maximum load current', 'decides': [{'aspect': '需求'}]}
        fail = {'key': 'POL', 'finding_id': 'F-001', 'what': 'D1 reversed', 'decides': [{'aspect': '极性'}]}
        fns = [function(req, id='FN-REQ'), function(id='FN-POL', verdict='FAIL', open=[], fails=[fail])]
        out = rm.expand(ledger(row(id='REQ-D01.LOAD', function_id='FN-REQ', aspect='需求', open_ref='FN-REQ/LOAD'),
                               {'id': 'DOC-V01.D1', 'review_result': 'FAIL', 'severity': 'P1', 'finding_id': 'F-001',
                                'function_id': 'FN-POL', 'aspect': '极性', 'fail_ref': 'FN-POL/POL'}, functions=fns))
        self.assertEqual(out['checks'][0]['gap_cause'], 'REQUIREMENT_OPEN')
        self.assertEqual([t['id'] for t in out['work_items']], ['W-POL'])   # requirement questions are clarifications
        self.assertEqual(out['work_items'][0]['next_action'], '按发现项 F-001 的改法处理')

    def test_expand_is_idempotent_and_leaves_the_record_alone(self):
        report = ledger(row())
        before = copy.deepcopy(report)
        once = rm.expand(report)
        self.assertEqual(report, before)
        self.assertEqual(rm.expand(once), once)
        self.assertLess(len(json.dumps(before)), len(json.dumps(once)))


if __name__ == '__main__':
    unittest.main()

import copy
import unittest

from test_validate_review import fixture
from validate_review import validate_review
from review_summary import categorized_summary, validate_impact


def gap():
    return {'id': 'G1', 'review_result': 'INSUFFICIENT', 'gap_cause': 'EXTERNAL_DATA',
            'potential_severity': 'P2', 'blocking': True,
            'impact_assessment': {'affected_function': 'Auxiliary diagnostic signal',
                'operating_condition': 'Cold startup', 'consequence': 'Indication may be unavailable',
                'severity_reason': 'Local indication; independent protection is unaffected',
                'blocking_reason': 'The project requires this diagnostic before freeze'}}


class ImpactTests(unittest.TestCase):
    def test_every_impact_dimension_is_required(self):
        self.assertEqual(validate_impact(gap()), [])
        for field in gap()['impact_assessment']:
            row = gap(); row['impact_assessment'][field] = ' '
            self.assertTrue(validate_impact(row), field)
        row = gap(); row['potential_severity'] = 'unknown'
        self.assertTrue(validate_impact(row))

    def test_legacy_grade_is_visible_as_undocumented_and_history_is_excluded(self):
        row = gap(); del row['impact_assessment']
        history = copy.deepcopy(row); history['id'] = 'H1'
        out = categorized_summary({'G1': row, 'H1': history},
                                  {'H1': {'rule': 'REQ-H02'}}, {}, {})
        self.assertEqual(out['insufficient_impact']['undocumented'], 1)
        self.assertEqual(out['insufficient_impact']['by_potential_severity']['P2'], 1)
        self.assertEqual(out['insufficient_impact']['blocking'], 1)
        self.assertEqual(out['result_labels']['INSUFFICIENT'], '证据不足（INSUFFICIENT）')

    def test_requirement_open_is_unrated(self):
        row = gap(); row['gap_cause'] = 'REQUIREMENT_OPEN'
        del row['potential_severity']; del row['impact_assessment']
        self.assertEqual(validate_impact(row), [])
        out = categorized_summary({'G1': row}, {}, {}, {})['insufficient_impact']
        self.assertEqual(out['requirement_open'], 1)
        self.assertEqual(out['undocumented'], 0)

    def test_impact_is_always_enforced_without_changing_evidence_or_release(self):
        p, r, db = fixture()
        row = r['checks'][0]
        row.update(gap()); row['id'] = p['checks'][0]['id']
        row.update(evidence_confidence='C', missing_inputs=['Guaranteed diagnostic timing'],
                   input_requests={'Guaranteed diagnostic timing': {
                       'why_decisive': 'Timing decides whether the diagnostic is valid at cold startup',
                       'required_scope': 'Maximum delay at cold startup supply limits',
                       'acquisition': 'Read supplier timing table',
                       'closure_criterion': 'Compare maximum delay with the diagnostic window'}})
        out = validate_review(p, r, db)
        self.assertTrue(out['valid'], out['errors'])
        self.assertEqual(out['release'], 'NO_GO')  # P2 can independently block freeze.
        self.assertEqual(row['evidence_confidence'], 'C')
        del row['impact_assessment']
        self.assertFalse(validate_review(p, r, db)['valid'])  # No switch or version marker can skip it.


    def test_history_rows_are_not_required_to_carry_impact(self):
        p, r, db = fixture()
        p['checks'][0]['rule'] = 'REQ-H02'
        row = r['checks'][0]
        row.update(gap()); row['id'] = p['checks'][0]['id']
        row.update(evidence_confidence='C', missing_inputs=['Historical item evidence'])
        del row['impact_assessment']
        errors = validate_review(p, r, db)['errors']
        self.assertFalse([e for e in errors if 'impact_assessment' in e or 'input_requests' in e], errors)


if __name__ == '__main__':
    unittest.main()

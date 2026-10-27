import copy
import unittest

from test_validate_review import fixture
from validate_review import validate_review
from ledger4 import gap as open_gap, severity
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

    def test_the_summary_counts_documented_as_the_gate_does(self):
        # SR self-check of 2026-10-24, 3.7: the gate also checks the consequence class; the count follows it.
        row = gap()
        self.assertEqual(categorized_summary({'G1': row}, {}, {}, {})['insufficient_impact']['documented'], 1)
        out = categorized_summary({'G1': row}, {}, {}, {}, classes=2)['insufficient_impact']
        self.assertEqual((out['documented'], out['undocumented']), (0, 1))
        row['impact_assessment']['consequence_class'] = 'LOCAL_OR_DATA'
        out = categorized_summary({'G1': row}, {}, {}, {}, classes=2)['insufficient_impact']
        self.assertEqual(out['documented'], 1)

    def test_impact_is_always_enforced_without_changing_evidence_or_release(self):
        p, r, db = fixture()
        r['checks'][0]['rationale'] = 'Timing decides whether the diagnostic is valid at cold startup'
        item = open_gap(r, r['checks'][0]['id'], 'DIAG-TIMING', 'VENDOR_DATUM', plan=p,
                        what='Guaranteed diagnostic timing', scope='Maximum delay at cold startup supply limits',
                        acquisition='Read supplier timing table', closure='Compare maximum delay with the diagnostic window',
                        severity=severity('P2', affects='Auxiliary diagnostic signal', consequence='Indication may be unavailable'))
        out = validate_review(p, r, db)
        self.assertTrue(out['valid'], out['errors'])
        self.assertEqual(out['release'], 'NO_GO')  # P2 can independently block freeze.
        del item['severity']
        self.assertFalse(validate_review(p, r, db)['valid'])  # No switch or version marker can skip it.


    def test_history_rows_are_not_required_to_carry_impact(self):
        p, r, db = fixture()
        p['checks'][0]['rule'] = 'REQ-H02'
        row = r['checks'][0]
        row.update(review_result='INSUFFICIENT', rationale='Historical item evidence not in this round')
        row.pop('evidence_confidence')
        errors = validate_review(p, r, db)['errors']
        self.assertFalse([e for e in errors if 'impact_assessment' in e or 'input_requests' in e], errors)


if __name__ == '__main__':
    unittest.main()

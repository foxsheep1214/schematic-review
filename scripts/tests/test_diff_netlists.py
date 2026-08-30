import pathlib
import sys
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from diff_netlists import diff_databases, evaluate_claims, validate_claims


def db(part, net):
    return {
        'parts': {
            'U1': {
                'part': part, 'value': part, 'jedec': 'QFN',
                'prim': part, 'nc': False,
            }
        },
        'pin2net': {'U1.1': net},
        'nets': {net: ['U1.1']},
        'pseudo_nets': [],
    }


class DiffTests(unittest.TestCase):
    def test_claim_validation_rejects_duplicate_and_missing_fields(self):
        claims = {
            'schema_version': 1,
            'claims': [
                {
                    'id': 'F-01',
                    'expect': [{'kind': 'part_field_equals', 'ref': 'U1',
                                'field': 'unknown'}],
                },
                {
                    'id': 'F-01',
                    'expect': [{'kind': 'pin_net_equals', 'node': 'U1.1'}],
                },
            ],
        }
        errors = validate_claims(claims)
        self.assertTrue(any('重复' in error for error in errors))
        self.assertTrue(any('.value 缺失' in error for error in errors))
        self.assertTrue(any('.field 不支持' in error for error in errors))
        self.assertTrue(any('.net 缺失' in error for error in errors))

    def test_claim_validation_handles_non_string_schema_values(self):
        claims = {
            'schema_version': 1,
            'claims': [{'id': ['bad'], 'expect': [{'kind': ['bad']}]}],
        }
        self.assertTrue(validate_claims(claims))

    def test_diff_and_false_closure(self):
        old, new = db('OLD', 'NET_A'), db('NEW', 'NET_B')
        result = diff_databases(old, new)
        self.assertEqual(result['summary']['parts_changed'], 1)
        self.assertEqual(result['summary']['pins_changed'], 1)
        claims = {
            'schema_version': 1,
            'claims': [
                {
                    'id': 'F-01',
                    'description': 'part changed correctly',
                    'expect': [
                        {
                            'kind': 'part_field_equals',
                            'ref': 'U1',
                            'field': 'part',
                            'value': 'EXPECTED',
                        }
                    ],
                }
            ],
        }
        self.assertEqual(validate_claims(claims), [])
        evaluated, findings = evaluate_claims(old, new, claims)
        self.assertEqual(evaluated[0]['status'], 'FAIL')
        self.assertEqual(findings[0]['rule'], 'Rule-17')


if __name__ == '__main__':
    unittest.main()

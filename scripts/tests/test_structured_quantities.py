"""Item 2 of the 2026-10-26 SR review: the structured fields are the main path. Three hints on a function verdict —
UNIT_UNKNOWN, QUANTITY_IMPLAUSIBLE, RESULT_NARRATIVE — and the shared unit table in the parameter-claims audit.
R7: the two Codex records wrote 514/561 quantities into calculation.result (10/13 results over 300 characters)
against 111/96 margins; the Claude records 117/107 against 151/181.
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import review_functions
import validate_review as vr
from review_functions import RESULT_MAX_CHARS, RESULT_LOOSE_QUANTITIES, quantity_hints
from test_review_functions import bias_function, ledger


def codes(fn):
    return [h['code'] for h in quantity_hints([fn])]


class QuantityHintTests(unittest.TestCase):
    def test_the_bias_example_raises_none(self):
        self.assertEqual(codes(bias_function('PASS')), [])

    def test_an_unknown_margin_or_limit_unit_is_hinted_with_its_place(self):
        fn = bias_function('PASS')
        fn['calculation']['margin']['unit'] = 'volts'
        [h] = quantity_hints([fn])
        self.assertEqual((h['code'], h['function_id'], h['margin'], h['unit']), ('UNIT_UNKNOWN', 'FN-BIAS', 0, 'volts'))
        fn = bias_function('PASS')
        fn['conditions'][1]['limit']['unit'] = 'Vgs'
        [h] = quantity_hints([fn])
        self.assertEqual((h['code'], h['condition'], h['unit']), ('UNIT_UNKNOWN', 'c2', 'Vgs'))
        fn = bias_function('PASS')
        fn['calculation']['margin']['unit'] = 'kohm'      # a spelling the table maps
        self.assertEqual(codes(fn), [])

    def test_an_implausible_magnitude_is_hinted_on_limits_both_ways_and_on_margins_above_only(self):
        fn = bias_function('PASS')
        fn['conditions'][2]['limit']['max'] = 8.8e9       # 8.8 GV
        [h] = quantity_hints([fn])
        self.assertEqual((h['code'], h['condition'], h['value']), ('QUANTITY_IMPLAUSIBLE', 'c3', 8.8e9))
        self.assertIn('lost its µ', h['message'])
        fn = bias_function('PASS')
        fn['conditions'][2]['limit']['max'] = 1e-9        # 1 nV threshold
        self.assertEqual(codes(fn), ['QUANTITY_IMPLAUSIBLE'])
        fn = bias_function('PASS')
        fn['calculation']['margin']['value'] = 1e-9       # a tiny margin is a margin
        self.assertEqual(codes(fn), [])
        fn['calculation']['margin']['value'] = 8e8
        self.assertEqual(codes(fn), ['QUANTITY_IMPLAUSIBLE'])

    def test_a_narrating_result_is_hinted_by_length_or_by_loose_quantities(self):
        fn = bias_function('PASS')
        fn['calculation']['result'] = 'VCC_min = 9.6 V，' * 40
        [h] = quantity_hints([fn])
        self.assertEqual((h['code'], h['function_id']), ('RESULT_NARRATIVE', 'FN-BIAS'))
        self.assertGreater(h['length'], RESULT_MAX_CHARS)
        fn = bias_function('PASS')
        fn['calculation']['result'] = '；'.join('节点 %d 为 %d.5 V' % (i, i + 20) for i in range(RESULT_LOOSE_QUANTITIES + 1))
        [h] = quantity_hints([fn])
        self.assertEqual((h['code'], h['loose_quantities']), ('RESULT_NARRATIVE', RESULT_LOOSE_QUANTITIES + 1))
        self.assertLessEqual(h['length'], RESULT_MAX_CHARS)

    def test_quantities_a_margin_or_limit_carries_are_not_loose(self):
        fn = bias_function('PASS')
        margin, c3 = fn['calculation']['margin'], fn['conditions'][2]['limit']
        carried = ['%s V' % margin['value'], '%s V' % c3['max']]
        fn['calculation']['result'] = '；'.join(carried * ((RESULT_LOOSE_QUANTITIES + 2) // 2))   # many tokens, all carried
        self.assertEqual(codes(fn), [])

    def test_the_hints_reach_the_gate_screening_with_the_reviewers_field_names(self):
        fn = bias_function('PASS')
        fn['calculation']['margin']['unit'] = 'volts'
        p, r, db = ledger(fn)
        out = vr.validate_review(p, r, db)
        found = [c for c in out['quality_screening']['candidates'] if c['code'] == 'UNIT_UNKNOWN']
        self.assertEqual(len(found), 1, out['quality_screening']['candidates'])
        self.assertEqual(found[0]['check_ids'], [])


class ParameterClaimsUnitTests(unittest.TestCase):
    def test_the_audit_compares_through_the_shared_table_and_notes_an_implausible_row(self):
        import hashlib, tempfile
        from audit_parameter_claims import check
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp, 'table.txt'); src.write_text('R_DS(on) 4.5 mΩ max')
            design = Path(tmp, 'design.md'); design.write_text('4500 µΩ')
            row = dict(identity='SYN-MOS', parameter='rds_on', conditions={'vgs_v': 10, 'tj_c': 25}, basis='maximum',
                       unit='mΩ', value=4.5, source=str(src), locator='table 3', sha256=hashlib.sha256(src.read_bytes()).hexdigest())
            claimed = dict(row, source=str(design), unit='µΩ', value=4500); del claimed['sha256']
            rows, errors = check([{'id': 'RDS', 'claimed': claimed, 'reference': row}])
            self.assertEqual((errors, rows[0]['status']), ([], 'MATCH'))
            self.assertNotIn('plausibility', rows[0])
            claimed = dict(claimed, unit='MΩ', value=4.5)          # the prefix slipped
            rows, _ = check([{'id': 'RDS', 'claimed': claimed, 'reference': row}])
            self.assertEqual(rows[0]['status'], 'MISMATCH')
            claimed = dict(claimed, unit='kV', value=4.5e9)        # 4.5 TV
            reference = dict(row, unit='kV', value=4.5e9)
            rows, _ = check([{'id': 'V', 'claimed': claimed, 'reference': reference}])
            self.assertEqual(rows[0]['status'], 'MATCH')
            self.assertEqual(len(rows[0]['plausibility']), 2)
            self.assertIn('claimed: 4500000000.0 kV is beyond what a voltage can be', rows[0]['plausibility'][0])


if __name__ == '__main__':
    unittest.main()

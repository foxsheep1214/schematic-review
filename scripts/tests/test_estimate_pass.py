"""An estimate passes a required function or a performance when a prototype test is handed on (SR self-check 2.1,
user: 估算 + 样机移交可判通过).

The documents let a similar part's guaranteed range or typical ±30 % pass a required-function or performance row (P1
included) when the conclusion holds over the whole range and the prototype measurement is a required handoff; the gate
passed nothing on an ESTIMATE except a life row. An ESTIMATE margin that names the consequence class it is used for
(REQUIRED_FUNCTION or PERFORMANCE_OR_LIFE) and the function handoff that measures it on the prototype now passes its
row, and the row carries that handoff. Damage, overheating and protection still need a guaranteed bound: the rules
about them take no estimate.
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import derive_rows
import review_functions as rf
import validate_review as vr
from test_derive_rows import OTHER_ROW, two_frames
from test_review_functions import ASPECT
from validate_review import fingerprint

PROTOTYPE = {'receivers': ['样机试验'], 'constraint': 'Q9 偏置在 −10 °C、5 V 空载时 ≥ 8.8 V',
             'verification': '样机实测 Q9 偏置电压'}


def estimate(**extra):
    return dict({'kind': 'ESTIMATE', 'comparison': 'GT', 'conditions': ['c1', 'c2'],
                 'scope': '相似器件保证范围，−10..105 °C', 'consequence_class': 'REQUIRED_FUNCTION', 'handoff': 0},
                **extra)


def estimated(**extra):
    """The second frame's own row: no shared gap, the voltage margin is an estimate handed to the prototype."""
    p, r, db = two_frames()
    r['functions'][0]['open'][0]['decides'].pop()
    other = r['functions'][1]
    other['handoffs'] = [dict(PROTOTYPE)]
    margin = next(m for m in other['calculation']['margin'] if m.get('aspect') == ASPECT)
    margin.update(states=['STARTUP', 'RUN', 'LATCH'], basis=estimate(**extra))
    r['plan_digest'] = fingerprint(p)
    return p, r, db


def other_row(r):
    return next(c for c in r['checks'] if c['id'] == OTHER_ROW)


class EstimatePassTests(unittest.TestCase):
    def test_an_estimate_for_a_required_function_with_a_prototype_handoff_passes(self):
        p, r, db = estimated()
        r, _, errors = derive_rows.derive(p, r)
        self.assertEqual(errors, [])
        row = other_row(r)
        self.assertEqual(row['review_result'], 'PASS')
        self.assertIn('估算', row['rationale'])
        self.assertEqual(row['handoff'], dict(PROTOTYPE, required=True, state='OPEN'))
        out = vr.validate_review(p, r, db)
        self.assertTrue(out['valid'], out['errors'])

    def test_performance_passes_too(self):
        p, r, db = estimated(consequence_class='PERFORMANCE_OR_LIFE')
        r, _, errors = derive_rows.derive(p, r)
        self.assertEqual((errors, other_row(r)['review_result']), ([], 'PASS'))

    def test_without_the_class_or_the_handoff_an_estimate_still_decides_nothing(self):
        for extra in ({'consequence_class': None}, {'handoff': None}):
            p, r, db = estimated(**extra)
            basis = next(m for m in r['functions'][1]['calculation']['margin'] if m.get('aspect') == ASPECT)['basis']
            for k in [k for k, v in basis.items() if v is None]:
                del basis[k]
            _, _, errors = derive_rows.derive(p, r)
            self.assertTrue(any(OTHER_ROW in e and 'judges no' in e for e in errors), (extra, errors))

    def test_damage_or_protection_is_not_a_class_an_estimate_passes(self):
        for cls in ('COMPONENT_DAMAGE', 'DAMAGE_OR_HAZARD', 'CORE_LINK_LOSS', 'LOCAL_OR_DATA', 'NONE'):
            p, r, db = estimated(consequence_class=cls)
            out = vr.validate_review(p, r, db)
            self.assertTrue(any('FN-OTHER/margin' in e and 'REQUIRED_FUNCTION' in e for e in out['errors']),
                            (cls, out['errors']))

    def test_the_handoff_is_one_the_function_lists(self):
        for index in (2, -1, '0', True):   # two handoffs: True would index the second
            p, r, db = estimated(handoff=index)
            r['functions'][1]['handoffs'].append(dict(PROTOTYPE, verification='样机实测 Q9 温升'))
            out = vr.validate_review(p, r, db)
            self.assertTrue(any('FN-OTHER/margin' in e and 'handoffs' in e for e in out['errors']), (index, out['errors']))
        p, r, db = estimated()
        r['functions'][1]['handoffs'][0]['verification'] = ''
        out = vr.validate_review(p, r, db)
        self.assertTrue(any('FN-OTHER/margin' in e and 'handoffs' in e for e in out['errors']), out['errors'])

    def test_a_hand_filled_pass_on_an_estimate_carries_the_handoff(self):
        p, r, db = estimated()
        r, _, _ = derive_rows.derive(p, r)
        other_row(r)['handoff'] = {'required': False}
        out = vr.validate_review(p, r, db)
        self.assertTrue(any(OTHER_ROW in e and 'prototype' in e for e in out['errors']), out['errors'])

    def test_damage_overheating_and_protection_rules_take_no_estimate(self):
        _, r, _ = estimated()
        fn = r['functions'][1]
        self.assertIsNotNone(rf.prototype_estimate(fn, ASPECT, 'RUN', OTHER_ROW))
        for cid in ('DEV-C01.Q9', 'DEV-C04.J1', 'PWR-C03.OTHER-RUN.Q9', 'PWR-C06.OTHER-RUN.Q9',
                    'PWR-C10.C3', 'DRV-C01.D2', 'PRO-C01.TVS1', 'PRO-C02.F1'):
            self.assertIsNone(rf.prototype_estimate(fn, ASPECT, 'RUN', cid), cid)

    def test_a_proving_margin_needs_no_handoff(self):
        p, r, db = estimated()
        margin = next(m for m in r['functions'][1]['calculation']['margin'] if m.get('aspect') == ASPECT)
        margin['basis'] = copy.deepcopy(next(m for m in r['functions'][0]['calculation']['margin']
                                             if m.get('aspect') == ASPECT)['basis'])
        r, _, errors = derive_rows.derive(p, r)
        self.assertEqual((errors, other_row(r)['handoff']), ([], {'required': False}))


if __name__ == '__main__':
    unittest.main()

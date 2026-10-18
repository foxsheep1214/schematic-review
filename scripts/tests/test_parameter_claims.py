"""Synthetic manufacturer tables and engineering limits only."""
import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from audit_parameter_claims import check


class ParameterClaimTest(unittest.TestCase):
    def setUp(self):
        root = Path('/tmp/codex-work/sr-source-fixes-tests')
        root.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(self.tmp.cleanup)
        path = Path(self.tmp.name) / 'synthetic-source.txt'
        path.write_text('SYNTHETIC material saturation: 400 mT at 80 C, H=1000 A/m')
        design = Path(self.tmp.name) / 'design.md'
        design.write_text('SYNTHETIC claim: 300 mT')
        row = dict(identity='SYNTHETIC-MATERIAL', parameter='saturation_flux_density',
                   conditions={'temperature_c': 80, 'field_a_per_m': 1000}, basis='typical',
                   unit='mT', value=400, source=str(path), locator='table 1')
        self.claim = {'id': 'MATERIAL', 'claimed': dict(row, source=str(design), value=300),
                      'reference': dict(row, sha256=hashlib.sha256(path.read_bytes()).hexdigest())}

    def status(self):
        rows, errors = check([self.claim])
        self.assertFalse(errors)
        return rows[0]['status']

    def test_incorrect_attribution_is_mismatch_but_si_units_match(self):
        self.assertEqual(self.status(), 'MISMATCH')
        self.claim['claimed'].update(value=.4, unit='T')
        self.assertEqual(self.status(), 'MATCH')

    def test_engineering_limit_is_not_mislabeled_as_wrong_manufacturer_rating(self):
        self.claim['claimed']['basis'] = 'engineering_limit'
        self.assertEqual(self.status(), 'OUT_OF_SCOPE')

    def test_conditions_identity_statistic_and_units_must_agree(self):
        for key, value in [('conditions', {'temperature_c': 25}), ('identity', 'OTHER'),
                           ('basis', 'minimum'), ('unit', 'unrecognized')]:
            with self.subTest(key=key):
                saved = copy.deepcopy(self.claim)
                self.claim['claimed'][key] = value
                self.assertEqual(self.status(), 'NOT_COMPARABLE')
                self.claim = saved

    def test_hash_tampering_self_reference_and_nonfinite_values_fail(self):
        for key, value in [('sha256', '0'*64), ('value', float('nan'))]:
            saved = copy.deepcopy(self.claim)
            self.claim['reference'][key] = value
            self.assertEqual(self.status(), 'ERROR')
            self.claim = saved
        self.claim['claimed']['source'] = self.claim['reference']['source']
        self.assertEqual(self.status(), 'ERROR')

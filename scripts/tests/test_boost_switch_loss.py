import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from boost_switch_loss import boost_cycle, conditional_losses


class BoostLossTests(unittest.TestCase):
    def test_crm_matches_closed_form(self):
        c = boost_cycle(100, 250, 200e-6, 1)
        self.assertAlmostEqual(c['peak_A'], 2)
        self.assertAlmostEqual(c['ton_s'], 4e-6)
        self.assertAlmostEqual(c['frequency_Hz'], 150000)
        self.assertAlmostEqual(c['switch_mean_square_A2'], .8)

    def test_dead_time_requires_more_peak_current(self):
        a = boost_cycle(100, 250, 200e-6, 1)
        b = boost_cycle(100, 250, 200e-6, 1, 8e-6)
        self.assertGreater(b['peak_A'], a['peak_A'])
        self.assertLess(b['frequency_Hz'], a['frequency_Hz'])
        self.assertAlmostEqual(b['input_mean_A'], 1)

    def test_energy_and_input_current_for_correlated_cycles(self):
        for v in (1, 100, 300):
            for d in (0, 2e-6, 18e-6):
                c = boost_cycle(v, 410, 180e-6, .4, d)
                self.assertAlmostEqual(c['input_energy_J'], c['output_energy_J'], places=12)
                self.assertAlmostEqual(c['input_energy_J'] / c['period_s'], v * .4)

    def test_invalid_physics_rejected(self):
        for args in [(0, 400, .001, 1), (400, 400, .001, 1), (10, 400, 0, 1),
                     (10, 400, .001, 0), (10, 400, .001, 1, -1), (float('nan'), 400, .001, 1)]:
            with self.assertRaises(ValueError):
                boost_cycle(*args)

    def test_losses_separate_energy_terms_and_scale(self):
        c = boost_cycle(100, 250, 200e-6, 1)
        a = conditional_losses(c, 250, .5, 100e-9, 1e-6)
        b = conditional_losses(c, 250, 1, 200e-9, 2e-6)
        self.assertAlmostEqual(a['conduction_W'], .4)
        self.assertAlmostEqual(a['overlap_W'], 3.75)
        self.assertAlmostEqual(a['residual_eoss_W'], .15)
        for k in a:
            self.assertAlmostEqual(b[k], 2 * a[k])

    def test_no_automatic_verdict(self):
        c = boost_cycle(100, 250, 200e-6, 1)
        self.assertNotIn('verdict', c)
        with self.assertRaises(ValueError):
            conditional_losses(c, 250, .5, -1)

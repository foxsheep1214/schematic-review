"""One concept, one judgment (SR self-check of 2026-10-24, group 3).

Ground and rail names, the capacitor and part words (electrolytic, tantalum, NTC, varistor, LED), the rated voltage a
value writes, finite numbers and text compared without spacing each had several readings that disagreed (VSS a ground
in one module and not in another; `10uF/16V/25V` 16 V in one and unwritten in another; 10**400 raising in some). Each
is now read in one place, and every module asks it.
"""
import ast
import json
import math
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import electrical_contract as ec
from checkers import netgraph as ng
from checkers import passive_stress


# Pin names, reference designators and negative supplies are other questions than a net's ground or a part's words.
OTHER_QUESTIONS = ('_PIN_RE', 'REFDES_RE', '_LINK_RE', '_PACKAGE_RE')
OTHER_NAMES = {'NEGATIVE_NET_RE', 'ANALOG_NAME_RE',
               'KICAD_POLARIZED_RE'}   # the KiCad library's pin-1-is-plus convention, not a word


def own_patterns(words):
    """(file, name) of module-level patterns outside netgraph that hold one of these words."""
    found = []
    for p in sorted(SCRIPTS.glob('*.py')) + sorted(SCRIPTS.glob('checkers/*.py')):
        if p.name == 'netgraph.py':
            continue
        for name, pattern in module_regexes(p).items():
            if name.endswith(OTHER_QUESTIONS) or name in OTHER_NAMES:
                continue
            if any(w in pattern for w in words):
                found.append((str(p.relative_to(SCRIPTS)), name))
    return found


def module_regexes(path):
    """Module-level re.compile patterns of a source file."""
    tree = ast.parse(path.read_text(encoding='utf-8'))
    found = {}
    for node in tree.body:
        if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
                and getattr(node.value.func, 'attr', None) == 'compile' and node.value.args
                and isinstance(node.value.args[0], ast.Constant)):
            found[node.targets[0].id] = node.value.args[0].value
    return found


class GroundTests(unittest.TestCase):
    def test_vss_names_are_grounds(self):
        for name in ('VSS', 'AVSS', 'DVSS', 'VSSA', 'GND', 'SGND', 'PGND', 'GND_ISO', '0V'):
            self.assertTrue(ng.is_ground(name), name)
        for name in ('VSS_SENSE', 'GND_SENSE', 'VSSEN', 'GNDSW', 'VCC'):
            self.assertFalse(ng.is_ground(name), name)

    def test_no_module_keeps_its_own_ground_or_rail_name_pattern(self):
        self.assertEqual(own_patterns(('GND', 'VSS', 'VCC|', 'VDD|')), [])


class PartWordTests(unittest.TestCase):
    def test_one_vocabulary(self):
        words = {'NTC_RE', 'VARISTOR_RE', 'LED_RE', 'POLARIZED_SYMBOL_RE', 'ELECTROLYTIC_RE', 'TANTALUM_RE'}
        self.assertTrue(words <= set(module_regexes(SCRIPTS / 'checkers' / 'netgraph.py')))
        self.assertEqual(own_patterns(('NTC', 'VARISTOR', 'MOV', 'LED', 'TANT', 'ELECTROLYTIC', 'C_Polarized')), [])

    def test_electrolytic_tantalum_and_polarized(self):
        self.assertTrue(ng.ELECTROLYTIC_RE.search('EEU-FR1V101'))
        self.assertTrue(ng.ELECTROLYTIC_RE.search('100uF ELEC'))
        self.assertFalse(ng.ELECTROLYTIC_RE.search('CP_Elec_8x10'))       # a footprint name needs the voltage rule
        self.assertTrue(ng.TANTALUM_RE.search('TPSD107K010R0100'))
        self.assertFalse(ng.TANTALUM_RE.search('TPS54331'))
        for text in ('Device:C_Polarized', 'Device:CP_Small', 'ALUMINUM 100uF', '钽电容 10uF', 'TPSB106K016'):
            self.assertTrue(ng.is_polarized_capacitor(text), text)
        self.assertFalse(ng.is_polarized_capacitor('Device:C 100nF X7R'))

    def test_ntc_varistor_led(self):
        self.assertTrue(ng.NTC_RE.search('NTC10K'))
        self.assertTrue(ng.VARISTOR_RE.search('压敏电阻 14D471K'))
        self.assertTrue(ng.LED_RE.search('Device:LED'))
        self.assertTrue(ng.LED_RE.search('LEDS_RGB'))
        self.assertFalse(ng.LED_RE.search('SLED_DRIVER'))


    def test_an_ntc_or_varistor_by_its_words_is_a_protection_part(self):
        import plan_circuits
        self.assertTrue(plan_circuits.protection_text('压敏电阻 14D471K'))
        self.assertTrue(plan_circuits.protection_text('NTC 5D-9'))
        import circuit_candidates as cc
        import test_circuit_candidates as fx
        db = fx.board()
        db['parts']['TH1'].update(part='NTC_5D-9', value='NTC_5D-9', prim='NTC_5D-9')   # no "thermistor" in its text
        intent, audit = fx.intent_for(db)
        found = cc.build(db, intent, audit)
        inp = next(c for c in found['candidates'] if c['id'] == 'POWER_PROTECTION-J1')
        self.assertEqual(next(m['role'] for m in inp['members'] if m['ref'] == 'TH1'), 'protective')


class RatedVoltageTests(unittest.TestCase):
    def test_one_reading(self):
        self.assertEqual(passive_stress.rated_voltage('100nF/16V'), 16.0)
        self.assertEqual(passive_stress.rated_voltage('4.7uF 10V X5R'), 10.0)
        self.assertEqual(passive_stress.rated_voltage('10uF/16V/16V'), 16.0)
        self.assertIsNone(passive_stress.rated_voltage('10uF/16V/25V'))   # two ratings: not read
        self.assertIsNone(passive_stress.rated_voltage('LDO3V3'))
        import board_scans
        self.assertIs(board_scans.rated_voltage, passive_stress.rated_voltage)


class FiniteTests(unittest.TestCase):
    def test_a_huge_integer_is_not_finite_anywhere(self):
        import requirement_parameters, review_functions, design_preflight
        for check in (ec.finite, review_functions._finite, requirement_parameters._number, design_preflight.number):
            self.assertFalse(check(10 ** 400), check)
            self.assertFalse(check(True), check)
            self.assertTrue(check(1.5), check)

    def test_calc_reports_a_huge_integer(self):
        out = subprocess.run([sys.executable, '-B', str(SCRIPTS / 'calc.py'), 'bound_formulas.tempco_bound',
                              json.dumps({'p0': 10 ** 400, 't0': 25, 't': 85, 's_min': 0.001, 's_max': 0.002, 'side': 'UPPER'})],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 2, out.stderr)
        self.assertNotIn('Traceback', out.stderr)


class SqueezeTests(unittest.TestCase):
    def test_one_squeeze(self):
        self.assertEqual(ec.squeeze(' 10 μF '), '10µF')
        self.assertEqual(ec.squeeze_words('A，B（C）. '), 'ABC')
        import plan_review, review_functions, requirement_parameters
        self.assertIs(review_functions._squeeze, ec.squeeze)
        self.assertIs(requirement_parameters._squeeze, ec.squeeze)
        self.assertIs(plan_review._squeeze, ec.squeeze_words)


if __name__ == '__main__':
    unittest.main()

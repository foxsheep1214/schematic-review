"""Part words do not hit inside longer words (2026-10-26, found by the ASG part-kind audit of one design): the opto
family PS2[5-9]xx matched the PS2xxx inside an eFuse part number (TPS25940 holds PS2594), and the part became an optocoupler. A part-number
family now starts a token (device_kinds.family); a datasheet cue of three letters or fewer is read as a word, since
squashed "Supply Current vs" holds tvs and "Maximum Current" mcu (datasheet_kinds.named_by).
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import datasheet_kinds as dk
import device_kinds
import part_words as pw

# One placed example of every family device_kinds.family() anchors, by the kind it names.
FAMILY_EXAMPLES = {
    'opto': ('PC817', 'LTV-817', 'LTV357T', 'TLP291', '6N137', 'HCPL-3120', 'ACPL-217', 'FOD817', 'CNY17-3',
             'VO615A', 'SFH6186', 'EL817', 'PS2501-1', 'TCMT1107', 'KPC357', 'H11L1'),
    'tvs': ('SMAJ5.0A', 'SMBJ15CA', 'SMCJ24A', 'P6KE6.8A', '1.5KE200A', 'ESD5Z5.0', 'PESD5V0S1BA', 'DESD5V0U1BA-7',
            'SM712'),
    'zener': ('BZX84C5V1', 'BZT52C3V3', 'MMSZ5231B', '1N4733A'),
    'bjt': ('BC847B', 'BCX56', '2N3904', 'MMBT3904', 'PBSS4041PX', 'S8050'),
    'mosfet': ('IRF540N', 'AUIRF7341', 'IRLML6402', 'AO3400A', 'SI2302', 'BSS84', '2N7002', '2N7000'),
    'diode': ('SS14', 'BAT54', '1N4148', '1N5819'),
    'ferrite': ('BLM18PG221', 'MPZ1608S221A'),
}
PINS = {'bjt': 3, 'mosfet': 3, 'opto': 4}


def kind_hit(kind, text):
    return any(re.search(p, text, re.I) for p in device_kinds.KINDS[kind].words)


class PartNumberFamilyTests(unittest.TestCase):
    def test_an_efuse_holding_an_opto_family_is_not_an_optocoupler(self):
        part = {'part': 'TPS25940ARVCR', 'value': 'TPS25940ARVCR', 'prim': 'Power_Management:TPS25940'}
        self.assertEqual(pw.classify('U1', part, pin_count=20), (pw.IC, 'refdes-prefix'))
        self.assertNotEqual(pw.classify('U1', {'part': 'LTPS2501', 'value': 'x'}, pin_count=8)[0], pw.OPTO)

    def test_optocouplers_still_read_as_written(self):
        for value in ('PS2501', 'TLP291', 'LTV-817', 'SFH6186'):
            with self.subTest(value=value):
                self.assertEqual(pw.classify('U2', {'value': value}, pin_count=4), (pw.OPTO, 'part-keyword'))
        self.assertEqual(pw.classify('U3', {'prim': 'Isolator:PC817'}, pin_count=4), (pw.OPTO, 'part-keyword'))
        self.assertEqual(pw.classify('U4', {'value': '光耦PC817'}, pin_count=4), (pw.OPTO, 'part-keyword'))

    def test_every_family_starts_a_token_and_keeps_its_examples(self):
        for kind, examples in FAMILY_EXAMPLES.items():
            for example in examples:
                with self.subTest(kind=kind, example=example):
                    self.assertEqual(pw.classify('X1', {'value': example}, PINS.get(kind, 2))[0], kind)
                    for lead in ('Lib:', 'Q_', '光耦 ', 'x '):
                        self.assertTrue(kind_hit(kind, lead + example), lead)
                    self.assertFalse(kind_hit(kind, 'T' + example))
                    self.assertFalse(kind_hit(kind, '9' + example))

    def test_a_family_inside_a_word_falls_back_to_weaker_evidence(self):
        self.assertEqual(pw.classify('U5', {'value': 'AIRFLOW'}, 6), (pw.IC, 'refdes-prefix'))
        self.assertEqual(pw.classify('D9', {'value': 'XSS14'}, 2), (pw.DIODE, 'refdes-prefix'))

    def test_2n7000_and_2n7002_are_mosfets_not_bjts(self):
        for value in ('2N7002', '2N7002K', '2N7000'):
            with self.subTest(value=value):
                self.assertFalse(kind_hit('bjt', value))
                self.assertEqual(pw.classify('Q1', {'value': value}, 3), (pw.MOSFET, 'part-keyword'))
        self.assertEqual(pw.classify('Q2', {'value': '2N3904'}, 3), (pw.BJT, 'part-keyword'))

    def test_si_and_four_digits_names_no_part_with_an_ic_refdes(self):
        # Silicon Labs ICs share Vishay's Si#### MOSFET prefix and number range
        for value, pins in (('Si7021-A20', 6), ('Si8261BAC', 6), ('Si3402-B', 20), ('SI5351A-B-GT', 10)):
            with self.subTest(value=value):
                self.assertEqual(pw.classify('U3', {'value': value}, pins), (pw.IC, 'refdes-prefix'))
        self.assertEqual(pw.classify('Q3', {'value': 'Si7223DN'}, 8), (pw.MOSFET, 'part-keyword'))
        self.assertEqual(pw.classify('U7', {'value': 'SI4800BDY'}, 8), (pw.IC, 'refdes-prefix'))   # a gap, not a guess
        # nor does it contradict another transistor word on the same part
        self.assertEqual(pw.classify('U2', {'value': 'SI2302', 'prim': 'Transistor_BJT:Q_NPN_BEC'}, 3), (pw.BJT, 'part-keyword'))


class ShortCueTests(unittest.TestCase):
    def test_a_short_cue_is_read_as_a_word(self):
        self.assertEqual(dk.cues('Supply Current vs Temperature'), set())
        self.assertEqual(dk.cues('ABSOLUTE MAXIMUM CURRENT'), set())
        self.assertEqual(dk.cues('BidirectionalTVSDiode'), {'tvs'})
        self.assertEqual(dk.cues('32-bit MCUs with flash'), {'mcu'})
        self.assertEqual(dk.cues('two mcus on one board'), {'mcu'})
        self.assertEqual(dk.cues('NPNTransistor'), {'bjt'})
        self.assertEqual(dk.cues('N-ChannelMOSFET'), {'mosfet'})      # a long cue still reads squashed text

    def test_a_capital_short_cue_may_run_into_a_lowercase_word(self):
        self.assertEqual(dk.cues('TVSdiode array'), {'tvs'})
        self.assertEqual(dk.cues('MCUwith 64 KB flash'), {'mcu'})
        self.assertEqual(dk.cues('TVS3 pin'), set())
        self.assertEqual(dk.cues('maximumcurrent'), set())

    def test_a_curve_title_no_longer_conflicts_with_the_declared_kind(self):
        read = lambda path, page: 'N-Channel MOSFET\nMaximum Current 10 A'
        quote = 'N-Channel MOSFET Maximum Current 10 A'
        self.assertEqual(dk.verify({'kind': 'mosfet', 'page': 1, 'quote': quote}, 'x.pdf', read)['status'], 'VERIFIED')
        found = dk.candidates('x.pdf', read_page=read)
        self.assertEqual([(c['kind'], c['snippet']) for c in found], [('mosfet', 'N-Channel MOSFET')])


if __name__ == '__main__':
    unittest.main()

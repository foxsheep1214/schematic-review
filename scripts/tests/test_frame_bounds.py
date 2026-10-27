"""A circuit frame carries the bounding-table cells of its parts (bounding table proposal of 2026-10-23, section 七).

The reviewer follows the table for every part of the frame (decision A) without opening the document: the frame lists
each cell that applies, with the parts it applies to, the methods in order, their formulas and the fallback. A sensing
or inrush NTC is an NTC, not a resistor; an electrolytic capacitor takes the electrolytic cell, not the MLCC one.
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import catalog
from plan_review import build_review_plan
from test_plan_review import sample_db


def frame(db=None, refs=('U1', 'R1')):
    intent = {'schema_version': 5,
              'circuits': [{'id': 'REG-3V3', 'type': 'POWER_CONVERTER', 'refs': list(refs), 'nets': ['VCC_3V3'],
                            'states': ['cold', 'hot'], 'citation': 'synthetic regulator'}]}
    plan = build_review_plan(db or sample_db(), intent)
    return next(f for f in plan['functions'] if f.get('circuit') == 'REG-3V3')


def cells(found):
    return {b['cell']: b['refs'] for b in found['bounds']}


class FrameBoundsTests(unittest.TestCase):
    def test_each_part_brings_the_cells_of_its_class(self):
        found = frame()
        ic = [b.id for b in catalog.BOUNDS.values() if 'ic' in b.kinds]
        self.assertEqual([b['cell'] for b in found['bounds']], ['RES-POWER'] + ic)   # in table order
        self.assertEqual(cells(found)['RES-POWER'], ['R1'])
        self.assertTrue(all(refs == ['U1'] for cell, refs in cells(found).items() if cell != 'RES-POWER'))

    def test_a_cell_says_how_to_bound(self):
        entry = next(b for b in frame()['bounds'] if b['cell'] == 'IC-THRESHOLD')
        bound = catalog.BOUNDS['IC-THRESHOLD']
        self.assertEqual(entry, {'cell': 'IC-THRESHOLD', 'refs': ['U1'], 'parameter': bound.parameter,
                                 'side': bound.side, 'methods': ['G1', 'G4', 'G7'],
                                 'formulas': ['tempco_bound', 'ratio_extrapolation'], 'fallback': 'VENDOR_DATUM'})

    def test_an_ntc_is_bounded_as_an_ntc(self):
        db = sample_db()
        db['parts']['R1'] = dict(db['parts']['R1'], value='NTC 10K')
        self.assertEqual(set(cells(frame(db))) - set(cells(frame())), {'NTC-SENSE', 'NTC-INRUSH-HOT'})
        self.assertNotIn('RES-POWER', cells(frame(db)))

    def test_an_electrolytic_takes_the_electrolytic_cell(self):
        db = sample_db()
        db['parts']['C1'] = {'part': 'C', 'value': '100uF/25V', 'prim': 'Aluminum electrolytic', 'jedec': 'D8',
                             'nc': False}
        db['nets']['VCC_3V3'].append('C1.1')
        db['nets']['GND'].append('C1.2')
        db['pin2net'].update({'C1.1': 'VCC_3V3', 'C1.2': 'GND'})
        found = cells(frame(db, refs=('U1', 'R1', 'C1')))
        self.assertEqual(found['ECAP-ESR-RIPPLE'], ['C1'])
        self.assertNotIn('MLCC-EFFECTIVE-C', found)
        ceramic = copy.deepcopy(db)
        ceramic['parts']['C1'] = dict(db['parts']['C1'], value='1uF', prim='C')
        found = cells(frame(ceramic, refs=('U1', 'R1', 'C1')))
        self.assertEqual(found['MLCC-EFFECTIVE-C'], ['C1'])
        self.assertNotIn('ECAP-ESR-RIPPLE', found)


if __name__ == '__main__':
    unittest.main()

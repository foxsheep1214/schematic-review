"""Broad optical namespaces must not add isolation/CTR reviews to emitters."""
import pathlib
import sys
import unittest
SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from checkers.netgraph import classify, OPTO, BJT
from checkers.optocoupler import build_inventory
from plan_review import build_review_plan
from test_optocoupler import opto_board, optos_of, findings
from test_inductive_load import add

class OpticalNamespaceTest(unittest.TestCase):
    def test_smart_led_does_not_create_isolation_or_ctr_objects(self):
        db = {'nets': {}, 'parts': {}, 'pin2net': {}, 'pinname': {},
              'pintype': {}, 'pseudo_nets': [], 'ref2page': {}}
        add(db, 'D1', 'WS2812B', [('1', 'VDD', '+5V'), ('2', 'DOUT', 'OUT'),
                                ('3', 'VSS', 'GND'), ('4', 'DIN', 'IN')])
        db['parts']['D1']['prim'] = 'we-opto:WS2812B:'
        self.assertEqual(optos_of(build_inventory(db)), {})
        self.assertFalse(any(c['object'].get('optocoupler')
                             for c in build_review_plan(db)['checks']))

    def test_real_pc817_in_same_namespace_keeps_missing_current_limit(self):
        db = opto_board(led_resistor=False)
        db['parts']['OK1']['prim'] = 'we-opto:PC817:'
        self.assertIn('OK1', optos_of(build_inventory(db)))
        self.assertEqual([f['rule'] for f in findings(db)], ['PRO-A03'])
        self.assertEqual({c['rule'] for c in build_review_plan(db)['checks']
                          if c['object'].get('optocoupler')}, {'PRO-D01', 'PRO-E01'})

    def test_explicit_opto_symbol_still_creates_review_objects(self):
        for prim in ('OPTO', 'Custom:OPTO_TRANSISTOR:'):
            with self.subTest(prim=prim):
                db = opto_board()
                db['parts']['OK1'] = {'part': 'UNKNOWN', 'prim': prim, 'value': '', 'jedec': ''}
                self.assertIn('OK1', optos_of(build_inventory(db)))
                self.assertEqual({c['rule'] for c in build_review_plan(db)['checks']
                                  if c['object'].get('optocoupler')}, {'PRO-D01', 'PRO-E01'})

    def test_part_identity_keywords_are_preserved(self):
        for key in ('part', 'value', 'jedec'):
            with self.subTest(key=key):
                self.assertEqual(classify('X9', {key: 'OPTO_TRANSISTOR', 'prim': 'we-opto:GENERIC'}, 4),
                                 (OPTO, 'part-keyword'))

    def test_datasheet_declared_opto_keeps_authoritative_priority(self):
        self.assertEqual(classify('U9', {'part': 'CONTROLLED_DEVICE', 'prim': 'optical:unknown'},
                                  4, declared=OPTO), (OPTO, 'datasheet'))

    def test_specific_transistor_library_category_is_unchanged(self):
        self.assertEqual(classify('Q7', {'prim': 'Transistor_BJT:Custom'}, 3),
                         (BJT, 'part-keyword'))

if __name__ == '__main__':
    unittest.main()

"""物料与引脚层面的自动扫描：只按网表、BOM 值和引脚名判别，输出仍是疑似清单。"""
import pathlib
import sys
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import board_scans
from lint import Lint
from plan_review import COLD_RULE_INDEXES, build_review_plan


def board(parts, nets, pinname=None, pintype=None, **extra):
    db = {'parts': {ref: dict({'value': value, 'part': value, 'prim': value, 'nc': False})
                    for ref, value in parts.items()},
          'nets': nets, 'pinname': pinname or {}, 'pintype': pintype or {},
          'ref2page': {}, 'pseudo_nets': []}
    db['pin2net'] = {node: net for net, nodes in nets.items() for node in nodes}
    db.update(extra)
    return db


def scans(db, rule=None):
    lint = Lint(db)
    lint.run()
    return [f for f in lint.F if rule is None or f['rule'] == rule]


def subjects(hits):
    """每条命中的定位对象：detail 以“位号/节点: 说明”开头。"""
    return [hit['detail'].split(':')[0].split(' ')[0] for hit in hits]


class CapacitorTest(unittest.TestCase):
    def test_rating_below_the_rail_name_is_a_candidate(self):
        db = board({'C1': '10uF/16V', 'C2': '100nF/50V', 'C3': '1uF'},
                   {'VCC_24V': ['C1.1', 'C2.1', 'C3.1'], 'GND': ['C1.2', 'C2.2', 'C3.2']})
        hits = scans(db, 'DEV-A01')
        self.assertEqual(subjects(hits), ['C1'])
        self.assertEqual(hits[0]['kind'], 'CANDIDATE')
        self.assertIn('耐压 16V < VCC_24V 推断 24V', hits[0]['detail'])

    def test_unfitted_and_unnamed_rails_are_not_reported(self):
        db = board({'C1': '10uF/16V'}, {'VCC_24V': ['C1.1'], 'GND': ['C1.2']})
        db['parts']['C1']['nc'] = True
        self.assertEqual(scans(db, 'DEV-A01'), [])
        db = board({'C1': '10uF/16V'}, {'ANALOG_IN': ['C1.1'], 'GND': ['C1.2']})
        self.assertEqual(scans(db, 'DEV-A01'), [])

    def test_reversed_polarity_marking_is_a_finding(self):
        db = board({'C1': '100uF/35V'}, {'GND': ['C1.1'], 'VCC_24V': ['C1.2']},
                   pinname={'C1.1': '+', 'C1.2': '-'})
        hits = scans(db, 'DEV-A02')
        self.assertEqual([f['kind'] for f in hits], ['FINDING'])
        correct = board({'C1': '100uF/35V'}, {'VCC_24V': ['C1.1'], 'GND': ['C1.2']},
                        pinname={'C1.1': '+', 'C1.2': '-'})
        self.assertEqual(scans(correct, 'DEV-A02'), [])

    def test_unmarked_capacitor_stays_for_visual_review(self):
        db = board({'C1': '100uF/35V'}, {'GND': ['C1.1'], 'VCC_24V': ['C1.2']},
                   pinname={'C1.1': '1', 'C1.2': '2'})
        self.assertEqual(scans(db, 'DEV-A02'), [])


class LedTest(unittest.TestCase):
    def test_led_directly_across_rail_and_ground_is_a_finding(self):
        db = board({'D1': 'LED-RED', 'R1': '1K'},
                   {'VCC_3V3': ['D1.1'], 'GND': ['D1.2', 'R1.2'], 'NET1': ['R1.1']})
        self.assertEqual(subjects(scans(db, 'DEV-A03')), ['D1'])

    def test_series_resistor_or_driver_net_is_not_reported(self):
        db = board({'D1': 'LED-RED', 'R1': '1K'},
                   {'VCC_3V3': ['R1.1'], 'LED_A': ['R1.2', 'D1.1'], 'GND': ['D1.2']})
        self.assertEqual(scans(db, 'DEV-A03'), [])


class FloatingInputTest(unittest.TestCase):
    def test_declared_input_pins_without_a_real_net(self):
        db = board({'U1': 'SOC'}, {'GND': ['U1.4'], 'LONE': ['U1.2'], 'BUS': ['U1.3', 'U1.5']},
                   pinname={'U1.1': 'IN1', 'U1.2': 'IN2', 'U1.3': 'IN3'},
                   pintype={'U1.1': 'IN', 'U1.2': 'IN', 'U1.3': 'IN', 'U1.5': 'OUT'})
        hits = dict(zip(subjects(scans(db, 'NET-A07')),
                        [f['kind'] for f in scans(db, 'NET-A07')]))
        self.assertEqual(hits, {'U1.1': 'FINDING', 'U1.2': 'FINDING'})

    def test_declared_no_connect_input_stays_a_candidate(self):
        db = board({'U1': 'SOC'}, {'NC_1': ['U1.1']}, pintype={'U1.1': 'INPUT'},
                   pseudo_nets=['NC_1'], no_connect_nodes=['U1.1'])
        hits = scans(db, 'NET-A07')
        self.assertEqual([f['kind'] for f in hits], ['CANDIDATE'])

    def test_symbol_declared_types_are_used_when_the_netlist_has_none(self):
        db = board({'U1': 'SOC'}, {'BUS': ['U1.3', 'U1.5']},
                   declared_pintype={'U1.9': 'IN'})
        self.assertEqual(subjects(scans(db, 'NET-A07')), ['U1.9'])


class RefdesTest(unittest.TestCase):
    def test_unannotated_refdes_is_a_finding(self):
        db = board({'R?': '10K', 'R1': '10K', 'U1A': 'SOC'}, {'NET1': ['R1.1']})
        self.assertEqual(subjects(scans(db, 'DOC-A04')), ['R?'])


class RulePlanTest(unittest.TestCase):
    def test_new_scans_are_listed_in_the_rule_ledger(self):
        rules = {row['rule'] for row in build_review_plan(board({}, {}))['rule_plan']}
        self.assertTrue({'DEV-A01', 'DEV-A02', 'DEV-A03', 'NET-A07', 'DOC-A04'} <= rules)
        self.assertTrue({'DEV-A01', 'DEV-A02', 'DEV-A03', 'NET-A07', 'DOC-A04'} <= set(COLD_RULE_INDEXES))

    def test_module_only_reports_registered_rules(self):
        db = board({'C1': '10uF/16V', 'D1': 'LED', 'R?': '0R'},
                   {'VCC_24V': ['C1.1', 'D1.1'], 'GND': ['C1.2', 'D1.2']})
        lint = Lint(db)
        board_scans.run(lint)
        self.assertEqual({f['rule'] for f in lint.F},
                         {'DEV-A01', 'DEV-A03', 'DOC-A04'})


if __name__ == '__main__':
    unittest.main()

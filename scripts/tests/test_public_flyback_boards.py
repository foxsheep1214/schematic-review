"""Topology recognition on two public flyback boards (fixtures in evals/kicad_replay_bench).

rf1: Nicolboy/KICAD-C2000-float-flyback@29fb9d9 (CERN-OHL-S-2.0) - Q1 primary with R19 source
sense, MSD1514 coupled inductor, TVS leakage clamp D1, UCC24612 synchronous rectifier Q2.
rf2: newell/hv-flyback-converter@c3d49c9 (CERN-OHL-W-2.0) - LT3957A internal switch, ESD on
the input connector, 36 V zener across the switch node.
Expectations were read from the upstream schematics, not from SR output. Recognition never
proves ratings, timing or polarity; those stay pending.
"""
import json
import pathlib
import sys
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = SCRIPTS.parent / 'evals' / 'kicad_replay_bench' / 'fixtures'
sys.path.insert(0, str(SCRIPTS))
from checkers.inductive_load import build_inventory as loads
from checkers.power_switch import build_inventory as switches
from parse_kicad import parse
from parse_netlist import integrity_problems
from plan_review import build_review_plan


def board(name):
    db = parse((FIXTURES / (name + '.xml')).read_text(encoding='utf-8'))
    db['integrity'] = {'self_check_passed': not integrity_problems(db)}
    return db


def rows(plan, rule):
    return sorted(c['id'] for c in plan['checks'] if c['rule'] == rule)


class SynchronousFlybackBoardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = board('rf1-c2000-float-flyback')
        cls.intent = json.loads((FIXTURES / 'rf1-c2000-float-flyback.intent.json').read_text(encoding='utf-8'))
        cls.switches = {s['ref']: s for st in switches(cls.db, cls.intent)['states'] for s in st['switches']}
        cls.loads = {l['ref']: l for st in loads(cls.db, cls.intent)['states'] for l in st['loads']}
        cls.plan = build_review_plan(cls.db, cls.intent)

    def test_flyback_primary_and_tvs_leakage_clamp(self):
        t1 = self.loads['T1']
        self.assertEqual((t1['application'], t1['switch_ref'], t1['rail_net']), ('flyback_transformer', 'Q1', 'VIN'))
        self.assertEqual([(c['ref'], c['across']) for c in t1['clamps']], [('D1', 'switch')])
        # D_TVS 双向符号画单向 SMCJ43A：极性不能从网表证实。
        self.assertEqual(t1['gaps'], ['flyback-tvs-clamp-polarity:unknown:D1'])

    def test_primary_switch_is_low_side_through_sense_resistor(self):
        q1 = self.switches['Q1']
        self.assertEqual((q1['topology'], q1['source_return']['ref'], q1['source_return']['resistance_ohm']),
                         ('low-side', 'R19', 0.0075))  # R19='7m5'

    def test_synchronous_rectifier_is_derived_from_a_minimal_declaration(self):
        sr = self.switches['Q2']['synchronous_rectifier']
        self.assertEqual(self.switches['Q2']['topology'], 'low-side-local-return')
        self.assertEqual((sr['controller_ref'], sr['sense_node'], sr['return_node'], sr['output_net']),
                         ('U12', 'U12.5', 'U12.2', 'VOUT_P'))
        self.assertEqual(sr['secondary_dot_node'], 'T1.2')
        self.assertEqual(sr['output_capacitors'], ['C3', 'C4', 'C43', 'C44'])  # 330u x2, 100n, 1u
        self.assertEqual(sr['derived_fields'], ['output_net', 'return_node', 'sense_node', 'winding_nodes'])
        self.assertIn('not verified', sr['dynamic_status'])

    def test_threshold_rows_cover_switch_node_clamps_and_only_the_ntc_sense_pin(self):
        self.assertEqual(rows(self.plan, 'PRO-C02'), ['PRO-C02.NOTRIP.D1', 'PRO-C02.NOTRIP.D3', 'PRO-C02.NOTRIP.D4',
                                                      'PRO-C02.TRIP.D1', 'PRO-C02.TRIP.D3', 'PRO-C02.TRIP.D4'])
        # TH1 上端在 RAIL_3V3_PRI，只有 TEMP 上的 U8.2(INP) 是检测脚。
        self.assertEqual(rows(self.plan, 'ANA-C04'), ['ANA-C04.TH1.U8-2'])

    def test_negative_output_return_is_not_named_a_rail_without_intent(self):
        cold = {s['ref']: s for st in switches(self.db)['states'] for s in st['switches']}
        self.assertNotEqual(cold['Q2']['topology'], 'high-side')
        self.assertIsNone(cold['Q2']['synchronous_rectifier'])


class IntegratedSwitchFlybackBoardTest(unittest.TestCase):
    def test_connector_esd_folds_and_rail_clamps_keep_two_sided_rows(self):
        plan = build_review_plan(board('rf2-hv-flyback-lt3957a'))
        # D2 在 J1 的 HVEN 信号针上；D1 跨 +5V 轨，D3 齐纳跨开关节点。
        self.assertEqual(rows(plan, 'PRO-C02'), ['PRO-C02.NOTRIP.D1', 'PRO-C02.NOTRIP.D3',
                                                 'PRO-C02.TRIP.D1', 'PRO-C02.TRIP.D3'])
        connector = {c['object']['ref']: c.get('clamp_refs') for c in plan['checks'] if c['rule'] == 'PRO-D03'}
        self.assertEqual(connector, {'J1': None, 'J2': None})   # D2's clamp window is its own PRO-E02 row


if __name__ == '__main__':
    unittest.main()

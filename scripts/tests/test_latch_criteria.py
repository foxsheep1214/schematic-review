"""SR 不足 2.1、2.2、4.1、4.2 (user 2026-11-04: 修改SR不足): status pins of a protection IC driving an external latch
(PRO-A06 normal actions, PWR-A08 hot insertion; G05-098, G03-017), the declared port exposure and the clamp
initial-calculation table of PRO-E02. Synthetic boards copy the Matrix power-protection R2 channel (TPS26630, HCS00/02/74,
EN_DLY 470 kΩ/2.2 µF discharged through BAS21 and 100 Ω); the R2 and calibration-board caches are used when present."""
import copy
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'evals' / 'rule_contracts'))

import catalog
import contracts
import latch_criteria
import protective_clamps
from lint import Lint
from plan_review import lint_check, validate_intent

R2 = pathlib.Path.home() / '.cache/sr-boards/matrix--power-protection-r2/review'
CALIBRATION = pathlib.Path.home() / '.cache/sr-boards/calibration--industrial-io-rs485-can'


def channel(gated=False):
    """One R2 channel. gated=True is the proposed fix: Un = NAND3(EN_DLY, FLT, SHDN_G)."""
    parts = [
        {'ref': 'U1', 'value': 'TPS26630RGER', 'pins': [
            ['5', 'IN_SYS', '24V_BUS'], ['12', '~{SHDN}', 'SHDN1'], ['16', 'PGOOD', 'PG1'], ['14', '~{FLT}', 'FLT1'],
            ['15', 'PGTH', 'PGTH1'], ['10', 'ILIM', 'ILIM1'], ['9', 'dVdT', 'DVDT1'], ['17', 'OUT', '24V_OUT1'],
            ['8', 'GND', 'GND']]},
        {'ref': 'R1', 'value': '39k2/1%', 'pins': [['1', '', '24V_OUT1'], ['2', '', 'PGTH1']]},
        {'ref': 'R2', 'value': '10k/1%', 'pins': [['1', '', 'PGTH1'], ['2', '', 'GND']]},
        {'ref': 'R3', 'value': '9k09/1%', 'pins': [['1', '', 'ILIM1'], ['2', '', 'GND']]},
        {'ref': 'C1', 'value': '1u/100V', 'pins': [['1', '', '24V_OUT1'], ['2', '', 'GND']]},
        {'ref': 'C2', 'value': '150nF', 'pins': [['1', '', 'DVDT1'], ['2', '', 'GND']]},
        {'ref': 'R4', 'value': '10k', 'pins': [['1', '', '+3V3'], ['2', '', 'PG1']]},
        {'ref': 'R5', 'value': '10k', 'pins': [['1', '', '+3V3'], ['2', '', 'FLT1']]},
        {'ref': 'R8', 'value': '10k', 'pins': [['1', '', '+3V3'], ['2', '', 'EN_N1']]},
        {'ref': 'R9', 'value': '10k', 'pins': [['1', '', '+3V3'], ['2', '', 'COLD_INIT_N']]},
        {'ref': 'U2', 'value': 'SN74HCS02PWR', 'pins': [
            ['1', '1Y', 'SHDN_G1'], ['2', '1A', 'EN_N1'], ['3', '1B', 'SC_LOCK1'],
            ['8', '3A', 'U1N'], ['9', '3B', 'PG1'], ['10', '3Y', 'V1'], ['7', 'GND', 'GND'], ['14', 'VCC', '+3V3']]},
        {'ref': 'R6', 'value': '100R', 'pins': [['1', '', 'SHDN_G1'], ['2', '', 'SHDN1']]},
        {'ref': 'R7', 'value': '470k/1%', 'pins': [['1', '', 'SHDN1'], ['2', '', 'EN_DLY1']]},
        {'ref': 'D1', 'value': 'BAS21HT1G', 'pins': [['1', 'K', 'SHDN1'], ['2', 'A', 'EN_DLY1']]},
        {'ref': 'C3', 'value': '2.2uF', 'pins': [['1', '', 'EN_DLY1'], ['2', '', 'GND']]},
        {'ref': 'U4', 'value': 'SN74HCS74PWR', 'pins': [
            ['1', '~{1CLR}', 'COLD_INIT_N'], ['2', '1D', 'D1N'], ['3', '1CLK', 'CLR_REQ1'], ['4', '~{1PRE}', 'PRE_N1'],
            ['5', '1Q', 'SC_LOCK1'], ['6', '~{1Q}', 'SC_LOCKN1'], ['7', 'GND', 'GND'], ['14', 'VCC', '+3V3']]},
        {'ref': 'J1', 'value': 'CONN_2', 'pins': [['1', '1', '24V_OUT1'], ['2', '2', 'GND']]},
    ]
    if gated:
        parts.append({'ref': 'U3', 'value': 'SN74HCS10PWR', 'pins': [
            ['1', '1A', 'EN_DLY1'], ['2', '1B', 'FLT1'], ['13', '1C', 'SHDN_G1'], ['12', '1Y', 'U1N'],
            ['3', '2A', 'V1'], ['4', '2B', 'COLD_INIT_N'], ['5', '2C', 'COLD_INIT_N'], ['6', '2Y', 'PRE_N1'],
            ['7', 'GND', 'GND'], ['14', 'VCC', '+3V3']]})
    else:
        parts.append({'ref': 'U3', 'value': 'SN74HCS00PWR', 'pins': [
            ['1', '1A', 'EN_DLY1'], ['2', '1B', 'FLT1'], ['3', '1Y', 'U1N'], ['4', '2A', 'V1'], ['5', '2B', 'COLD_INIT_N'],
            ['6', '2Y', 'PRE_N1'], ['7', 'GND', 'GND'], ['14', 'VCC', '+3V3']]})
    return {'parts': parts}


def load_requirement(max_uf):
    return {'requirements': [{'id': 'REQ-HP', 'status': 'CONFIRMED', 'categories': ['PROTECTION'],
                              'interpretation': '热插入负载电容上限',
                              'parameters': [{'name': 'load_capacitance', 'max': max_uf, 'unit': 'µF'}]}]}


def hits(board, rule, intent=None):
    db = contracts.build_db(board)
    lint = Lint(db, None, intent or {})
    return [f for f in lint.run() if f['rule'] == rule and f['kind'] in ('FINDING', 'CANDIDATE')]


class NormalActionTests(unittest.TestCase):
    def test_command_off_presets_the_latch_with_datasheet_numbers(self):
        found = hits(channel(), 'PRO-A06')
        self.assertEqual([f['kind'] for f in found], ['FINDING'])
        detail = found[0]['detail']
        self.assertIn('U4.PRE1（PRE_N1，低有效）= NAND(NOR(NAND(EN_DLY1, FLT1), PG1), COLD_INIT_N)', detail)
        self.assertIn('约 1.51–2.76 V（高温曲线下限 1.32 V）', detail)   # V(SHUTF) 0.8–2.0 V + BAS21 at 8–20 mA
        self.assertIn('VT− 0.97–1.06 V 仍判高', detail)                 # SN74HCS00 interpolated at 3.3 V
        self.assertIn('R6×C3 = 220 µs', detail)
        self.assertIn('PG 在 5.5 µs 内变低', detail)
        self.assertIn('异步输入有效（锁存被置）', detail)
        self.assertIn('MCU 复位：命令输入取上下拉默认态、锁存未置，SHDN_G1 为低，等同命令关断', detail)
        self.assertIn('上电默认态：PG 低、延时电容未充、复位有效 → 异步输入无效', detail)
        self.assertIn('判据延时更长，开启不置锁', detail)

    def test_gating_the_criterion_with_the_command_clears_the_finding(self):
        self.assertEqual(hits(channel(gated=True), 'PRO-A06'), [])

    def test_status_pin_to_the_mcu_only_is_not_a_latch(self):
        board = channel()
        board['parts'] = [p for p in board['parts'] if p['ref'] != 'U4']
        self.assertEqual(hits(board, 'PRO-A06'), [])
        self.assertEqual(hits(board, 'PWR-A08'), [])

    def test_threshold_interpolation_and_logic_families(self):
        self.assertEqual(latch_criteria.logic_function({'part': 'SN74HCS00PWR'}), 'NAND')
        self.assertEqual(latch_criteria.logic_function({'part': 'SN74HCS02PWR'}), 'NOR')
        self.assertEqual(latch_criteria.logic_function({'part': 'SN74LVC3G17DCUR'}), 'BUF')
        self.assertEqual(latch_criteria.logic_function({'part': 'SN74HCS74PWR'}), 'DFF')
        self.assertIsNone(latch_criteria.logic_function({'part': 'TPS26630RGER'}))
        points = latch_criteria.INPUT_THRESHOLDS[0][1]
        self.assertAlmostEqual(latch_criteria._interp(points, 3.3, 1), 0.974, places=3)
        self.assertAlmostEqual(latch_criteria._interp(points, 3.3, 2), 1.055, places=3)

    def test_three_valued_evaluation(self):
        tree = ('NAND', 'X', 'U', [('LEAF', 'a'), ('LEAF', 'b')])
        self.assertEqual(latch_criteria.Model.evaluate(tree, {'a': 0}), 1)
        self.assertIsNone(latch_criteria.Model.evaluate(tree, {'a': 1}))
        self.assertEqual(latch_criteria.Model.evaluate(tree, {'a': 1, 'b': 1}), 0)
        nor = ('NOR', 'Y', 'U', [('LEAF', 'a'), ('LEAF', 'b')])
        self.assertEqual(latch_criteria.Model.evaluate(nor, {'b': 1}), 0)


class HotInsertTests(unittest.TestCase):
    def test_hot_insert_without_a_load_limit_presets_and_names_the_requirement_gap(self):
        found = hits(channel(), 'PWR-A08')
        self.assertEqual([f['kind'] for f in found], ['FINDING'])
        detail = found[0]['detail']
        self.assertIn('对应输出 5.36–5.66 V', detail)
        self.assertIn('负载电容大于约 3.24 µF–3.48 µF 就跌破 PG 门限', detail)
        self.assertIn('1.82–2.14 A', detail)
        self.assertIn('例 47 µF 跌到 0.50 V，约 116 µs', detail)
        self.assertIn('对 PG 下降消抖最大 4 µs', detail)
        self.assertIn('需求没有允许热插入的负载电容上限', detail)
        rows = found[0]['latch']['hot_insert']['recharge']
        self.assertAlmostEqual([r for r in rows if r['load_f'] == 47e-6][0]['time_s'], 1.157e-4, delta=2e-6)

    def test_a_load_limit_below_the_critical_capacitance_keeps_pg_up(self):
        self.assertEqual(hits(channel(), 'PWR-A08', load_requirement(2.2)), [])
        found = hits(channel(), 'PWR-A08', load_requirement(47))
        self.assertEqual(len(found), 1)
        self.assertIn('需求上限 47 µF', found[0]['detail'])
        self.assertNotIn('需求缺口', found[0]['detail'])

    def test_pwr_c13_asks_the_status_pin_question(self):
        self.assertIn('状态脚', catalog.BY_ID['PWR-C13'].criterion)
        self.assertEqual(catalog.BASIS['PWR-A08'], ('G03-017', 'G05-098'))
        self.assertEqual(catalog.BASIS['PRO-A06'], ('G05-098',))
        self.assertNotIn('G05-098', catalog.BASIS['PRO-C09'])


def clamp_board():
    return {'parts': [
        {'ref': 'J1', 'value': 'CONN_2', 'pins': [['1', '1', '12V_OUT'], ['2', '2', 'GND']]},
        {'ref': 'D1', 'value': 'SMBJ15A', 'pins': [['1', 'K', '12V_OUT'], ['2', 'A', 'GND']]},
        {'ref': 'U1', 'value': 'TPS259814LRPWR', 'pins': [['5', 'IN', '12V_IN'], ['6', 'OUT', '12V_OUT'], ['8', 'GND', 'GND']]},
    ]}


SURGE = {'requirements': [{'id': 'E-PROT-03', 'status': 'CONFIRMED', 'categories': ['PROTECTION'], 'interpretation': '浪涌',
                           'parameters': [{'name': 'surge_voltage', 'unit': 'kV', 'min': -1, 'max': 1, 'condition': '差模 ±1 kV'}]}]}


class ClampExposureTests(unittest.TestCase):
    def test_undeclared_port_is_marked_for_a_human_and_the_rated_point_is_tabled(self):
        found = hits(clamp_board(), 'PRO-E02', copy.deepcopy(SURGE))
        detail = found[0]['detail']
        self.assertIn('需人判：端口暴露等级（intent.interfaces 未声明 J1', detail)
        self.assertEqual(found[0]['needs_human'], ['port_exposure'])
        self.assertIn('VC 24.4 V @ IPP 24.6 A（10/1000 µs） 对 U1.6(OUT) 绝限 20 V：已超', detail)
        self.assertEqual(lint_check(found[0])['object']['needs_human'], ['端口暴露等级'])

    def test_out_of_box_port_takes_the_surge_source_impedance(self):
        intent = dict(copy.deepcopy(SURGE), interfaces={'J1': {'exposure': 'via_box_connector', 'citation': 'E-IF-01'}})
        detail = hits(clamp_board(), 'PRO-E02', intent)[0]['detail']
        self.assertIn('J1 声明经航插出箱：E-PROT-03 差模 ±1 kV 1000 V，源阻抗 2 Ω', detail)
        self.assertIn('E-PROT-03 1000 V / 2 Ω：IPP 约 438 A，钳位约 123.6 V（线性外推），超过 10/1000 µs 额定 24.6 A', detail)
        self.assertNotIn('需人判', detail)

    def test_in_box_port_takes_no_external_surge(self):
        intent = dict(copy.deepcopy(SURGE), interfaces={'J1': {'exposure': 'in_box', 'citation': '接口表'}})
        detail = hits(clamp_board(), 'PRO-E02', intent)[0]['detail']
        self.assertIn('J1 声明箱内：外部浪涌需求不到达', detail)
        self.assertNotIn('IPP 约', detail)

    def test_exposure_values_are_validated(self):
        errors = validate_intent({'schema_version': 5, 'interfaces': {'J1': {'exposure': 'outside'}}})
        self.assertTrue(any('interfaces.J1.exposure' in e for e in errors), errors)
        errors = validate_intent({'schema_version': 5, 'interfaces': {'J1': {'exposure': 'in_box'}}})
        self.assertTrue(any('interfaces.J1 须写 citation' in e for e in errors), errors)
        self.assertFalse([e for e in validate_intent({'schema_version': 5, 'interfaces': {
            'J1': {'exposure': 'exposed', 'citation': '需求 E-IF-01'}}}) if 'interfaces' in e])

    def test_surge_impedance_follows_the_coupling_words(self):
        cases = protective_clamps.surge_cases({'requirements': [{'id': 'R', 'parameters': [
            {'name': 'surge_voltage', 'unit': 'kV', 'max': 2, 'condition': '共模 ±2 kV'},
            {'name': 'surge_voltage', 'unit': 'V', 'max': 500, 'condition': 'line-line'}]}]})
        self.assertEqual([(c[2], c[3]) for c in cases], [(2000.0, 12.0), (500.0, 2.0)])


@unittest.skipUnless((R2 / 'db.json').is_file(), 'R2 reproduction cache not present')
class R2ReproductionTests(unittest.TestCase):
    """SR 技能不足 2.1/2.2 on the R2 first-review input: F-001 and F-002 come out of the cold scan."""

    @classmethod
    def setUpClass(cls):
        db = json.loads((R2 / 'db.json').read_text(encoding='utf-8'))
        intent = json.loads((R2 / 'intent.json').read_text(encoding='utf-8'))
        intent = {k: v for k, v in intent.items() if k not in ('circuits', 'circuit_decisions', 'circuit_candidates_sha256')}
        cls.findings = Lint(db, None, intent).run()

    def rows(self, rule):
        return [f for f in self.findings if f['rule'] == rule]

    def test_f001_every_channel_and_orin(self):
        rows = self.rows('PRO-A06')
        self.assertEqual(len(rows), 9)
        self.assertEqual({f['kind'] for f in rows}, {'FINDING'})
        orin = [f for f in rows if f['detail'].startswith('U802 ')][0]['detail']
        self.assertIn('约 1.60–1.64 V', orin)          # EN_ORIN at VUVLO(F) + BAS21 at 0.1 mA
        self.assertIn('PG 在 14 µs 内变低', orin)
        ch1 = [f for f in rows if f['detail'].startswith('U901 ')][0]['detail']
        self.assertIn('约 1.51–2.76 V', ch1)

    def test_f002_eight_channels(self):
        rows = self.rows('PWR-A08')
        self.assertEqual(len(rows), 8)
        self.assertTrue(all('例 47 µF 跌到 0.50 V，约 116 µs' in f['detail'] for f in rows))

    def test_thirteen_clamps_get_an_initial_table(self):
        rows = self.rows('PRO-E02')
        self.assertEqual(sum('初算（' in f['detail'] for f in rows), 14)
        d801 = [f for f in rows if f.get('ref') == 'D801'][0]['detail']
        self.assertIn('对 U802.6(OUT) 绝限 20 V：已超', d801)


@unittest.skipUnless((CALIBRATION / 'db.json').is_file(), 'calibration board cache not present')
class CalibrationNegativeTests(unittest.TestCase):
    def test_no_latch_finding_on_the_calibration_board(self):
        db = json.loads((CALIBRATION / 'db.json').read_text(encoding='utf-8'))
        found = [f for f in Lint(db, None, {}).run() if f['rule'] in ('PRO-A06', 'PWR-A08')]
        self.assertEqual(found, [])


if __name__ == '__main__':
    unittest.main()

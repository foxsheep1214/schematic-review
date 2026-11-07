"""Electrical known defects (评测集 已知缺陷/known_defects.json) that need a guard of their own.

HOT-mcu-pad: on OLIMEX ESP32-PoE-ISO Rev.N the CH340 RXD node is pulled to +5V_USB by R18 and reaches the ESP32 U0TXD
pad through the forward diode D7, so the pad is lifted above VDD+0.3 V whenever the ESP32 is in reset or unpowered
(hot-review pilot 2026-10-20, P1). Once the UART link and its diode-plus-pull-up level interface are declared, the plan
must ask the back-feed question (SIG-C08) on exactly that diode and pull-up.

R5-pfc-missed: on ASG 100W-PD R5 the NCP1623A CS/ZCD pin U201.6 reads the PFC drain through R209-R211 3x499k over
R208 22k (KCS 69.05); with the datasheet line range detection threshold 1.65/1.80/1.95 V the high-line entry falls
at 76-101 Vac (nominal 87.9), so 90 Vac can be taken for high line. Wherever an IC pin reads the boost input or
switch node through a high-ohm resistor chain, the plan asks the line-sense threshold window (PWR-C06.LINE-SENSE).
"""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import board_intent
from plan_review import build_review_plan
from test_single_fault_rows import add, empty

FIXTURE = Path(__file__).parent / 'fixtures/esp32-poe-iso-revn-calibration/variant-db.json'


def test_hot_mcu_pad_back_feed_through_diode_and_pull_up_is_asked():
    db = json.loads(FIXTURE.read_text())
    assert db['nets']['Net-(D7-A)'] == ['D7.2', 'R18.2', 'U1.9']          # CH340 RXD, pulled up by R18
    assert 'U6.35' in db['nets']['/GPIO1/U0TXD'] and 'D7.1' in db['nets']['/GPIO1/U0TXD']
    assert db['pin2net']['R18.1'] == '/+5V_USB'
    intent = {'circuits': [
        {'id': 'UART', 'type': 'UART', 'refs': ['U1'], 'citation': 'fixture boundary', 'states': ['run'], 'nets': []},
        {'id': 'LVL', 'type': 'LEVEL_SHIFT', 'refs': ['D7', 'R18', 'D6', 'R17', 'R19'], 'citation': 'fixture boundary',
         'states': ['run'], 'nets': []}], 'power_rails': {}}
    plan = build_review_plan(db, dict(intent, input_sha256=board_intent.input_fingerprint(db)))
    rows = [c for c in plan['checks'] if c['rule'] == 'SIG-C08' and c['object'].get('circuit') == 'LVL']
    assert rows and {'D7', 'R18'} <= set(rows[0]['object']['refs'])


def pfc_board(top='499k', sense_from='D'):
    db = empty()
    add(db, 'BR1', 'Bridge', [('1', 'AC1', 'AC_L'), ('2', 'AC2', 'AC_N'), ('3', '+', 'VIN'), ('4', '-', 'GND')])
    add(db, 'L1', '200uH', [('1', '1', 'VIN'), ('2', '2', 'D')])
    add(db, 'Q1', 'NMOS', [('1', 'G', 'G'), ('2', 'D', 'D'), ('3', 'S', 'S')])
    add(db, 'D1', 'DIODE', [('1', 'A', 'D'), ('2', 'K', 'BULK')])
    add(db, 'C1', '100uF', [('1', '1', 'BULK'), ('2', '2', 'GND')])
    add(db, 'RS', '0.1', [('1', '1', 'S'), ('2', '2', 'GND')])
    add(db, 'R1', top, [('1', '1', sense_from), ('2', '2', 'N1')])
    add(db, 'R2', top, [('1', '1', 'N1'), ('2', '2', 'N2')])
    add(db, 'R3', top, [('1', '1', 'N2'), ('2', '2', 'CS')])
    add(db, 'R4', '22k', [('1', '1', 'CS'), ('2', '2', 'S')])
    add(db, 'U1', 'NCP1623A', [('1', 'FB', 'FB'), ('2', 'VCC', 'VCC'), ('3', 'DRV', 'G'), ('4', 'GND', 'GND'),
                                ('6', 'CS/ZCD', 'CS')])
    return db


def line_rows(db):
    return [c for c in build_review_plan(db)['checks'] if c['id'].startswith('PWR-C06.LINE-SENSE')]


def test_r5_pfc_line_detect_threshold_is_asked_on_the_drain_sense_pin():
    found = line_rows(pfc_board())
    assert [(r['object']['node'], r['object']['source'], r['object']['chain']) for r in found] == [
        ('U1.6', 'D', ['R3', 'R2', 'R1'])]
    assert '高低线判别' in found[0]['criterion'] and '最低与最高输入' in found[0]['criterion']


def test_line_sense_on_the_rectified_input_is_asked_too():
    assert [r['object']['source'] for r in line_rows(pfc_board(sense_from='VIN'))] == ['VIN']


def test_a_low_ohm_chain_or_a_bulk_divider_is_no_line_sense():
    assert line_rows(pfc_board(top='1k')) == []           # 3 kΩ: a gate or filter resistor, not a line divider
    assert line_rows(pfc_board(sense_from='BULK')) == []  # the output divider is the feedback, not the line

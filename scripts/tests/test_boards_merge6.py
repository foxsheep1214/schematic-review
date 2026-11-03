"""boards-merge6: the industrial I/O calibration board (ASG-drawn, RS-485/CAN/8 DI/4 DO, 24 V input) false alarms and
misses, one block per finding id of evals/boards/calibration--industrial-io-rs485-can/findings.json."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import board_intent
from checkers.netgraph import NetGraph


def _one_pin_device(native, official, role='power'):
    from test_boards_merge2b_roles import empty
    from test_inductive_load import add
    db = empty()
    add(db, 'U1', 'IC', [('49', native, 'VCC')])
    intent = {'devices': {'U1': {'pinout_complete': True, 'citation': 'ST IPS4140HQ DS14694 p2 Table 1',
                                 'pins': {'49': {'name': official, 'role': role}}}}}
    return NetGraph(board_intent.graph_db(db, intent))


# F04: "VCC (TAB)" is the VCC pin (ST IPS4140HQ DS14694 p2 Table 1); the bracket names the copper, not a function
def test_bracketed_package_note_is_not_a_pin_name_conflict():
    for official in ('VCC (TAB)', 'VCC(TAB)', 'VCC (EP)', 'VCC (Exposed Pad)', 'VCC (PAD)'):
        assert not _one_pin_device('VCC', official).pin_conflicts, official


def test_package_note_does_not_hide_a_different_function():
    assert _one_pin_device('GND', 'VCC (TAB)').pin_conflicts
    assert _one_pin_device('VCC', 'OUT1 (TAB)').pin_conflicts
    assert _one_pin_device('VCC', 'VCC (SENSE)').pin_conflicts      # not a package note: compared as written


# F13: SN65HVS883 DB0/DB1 open select a debounce time (SLASEE6 p3 Pin Functions, p5 tDB rows "DB0 = DB1 = open")
def test_sn65hvs883_debounce_select_may_be_open():
    import part_words as pw
    from test_boards_merge5_minor import one_pin
    assert 'SLASEE6' in pw.unused_input_permission(one_pin('U601', 'SN65HVS883PWPR', '2', 'DB1'), 'U601.2')
    assert 'SLASEE6' in pw.unused_input_permission(one_pin('U601', 'SN65HVS883', '1', 'DB0'), 'U601.1')
    assert pw.unused_input_permission(one_pin('U601', 'SN65HVS883PWPR', '24', 'CE'), 'U601.24') is None
    assert pw.unused_input_permission(one_pin('U601', 'SN65HVS883PWPR', '3', 'DB1'), 'U601.3') is None   # name on the wrong pin
    assert pw.unused_input_permission(one_pin('U601', 'SN65HVS882', '2', 'DB1'), 'U601.2') is None       # another model


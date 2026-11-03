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


# F14: ISO6441 EN1/EN2 tied to VCC1/VCC2 is the datasheet hookup (TI ISO644x SLLSG01C p5: enabled when ENx is high or open)
def _iso(en2_name='EN2', en2_net='+5V_ISO', part='ISO6441FDWR'):
    from test_boards_merge2b_roles import empty
    from test_inductive_load import add
    db = empty()
    add(db, 'U602', part, [('1', 'VCC1', '+3V3'), ('2', 'GND1', 'GND'), ('7', 'EN1', '+3V3'), ('3', 'INA', 'TX'),
                           ('16', 'VCC2', '+5V_ISO'), ('15', 'GND2', 'FGND'), ('10', en2_name, en2_net), ('14', 'OUTA', 'TX_ISO')])
    add(db, 'C1', 'C', [('1', '', '+3V3'), ('2', '', 'GND')])
    add(db, 'C2', 'C', [('1', '', '+5V_ISO'), ('2', '', 'FGND')])
    return db


def _coupled(db):
    from checkers.power_up import build_inventory
    return [x['node'] for s in build_inventory(db)['states'] for x in s['coupled_loads']]


def test_isolator_output_enable_tied_to_its_own_side_supply_is_not_a_sequencing_candidate():
    assert _coupled(_iso()) == []


def test_isolator_enable_exemption_keeps_active_low_other_side_and_non_isolators():
    assert _coupled(_iso(en2_name='~EN2')) == ['U602.10']          # active low tied high disables the outputs
    assert _coupled(_iso(en2_net='+3V3')) == ['U602.10']             # EN2 on the other side's supply
    assert _coupled(_iso(part='TPS2116')) == ['U602.10', 'U602.7']   # not a digital isolator: unchanged


# F15: LM74910H-Q1 EN on VS with UVLO set by its own divider (SNOSDE6C typical application): no "EN without UVLO"
def _ideal_diode(uvlo=True):
    from test_boards_merge2b_roles import empty
    from test_inductive_load import add
    db = empty()
    add(db, 'U101', 'LM74910HQRGERQ1', [('22', 'VS', 'VS_N'), ('6', 'EN', 'VS_N'), ('4', 'UVLO', 'UVLO_N' if uvlo else 'VS_N'),
                                        ('15', 'OUT', '24V_BUS'), ('3', 'SW', 'VS_N'), ('13', 'GND', 'GND')])
    add(db, 'J1', 'Conn_01x02', [('1', '', 'VS_N'), ('2', '', 'GND')])
    add(db, 'C1', '10u', [('1', '', 'VS_N'), ('2', '', 'GND')])
    if uvlo:
        add(db, 'R105', '470k', [('1', '', 'VS_N'), ('2', '', 'UVLO_N')])
        add(db, 'R106', '33k', [('1', '', 'UVLO_N'), ('2', '', 'GND')])
    for ref in ('R105', 'R106'):
        if ref in db['parts']:
            db['parts'][ref].update(prim='Device:R', part='R')
    return db


def _rst_a03(db):
    from lint import Lint
    return [f for f in Lint(db).run() if f['rule'] == 'RST-A03']


def test_separate_uvlo_divider_closes_en_tied_to_input():
    from checkers.power_up import build_inventory
    item = build_inventory(_ideal_diode())['states'][0]['regulators'][0]
    assert item['enable_source'] == 'tied-to-input' and item['uvlo_pins'] == ['U101.4']
    assert _rst_a03(_ideal_diode()) == []


def test_en_tied_to_input_without_a_uvlo_divider_is_still_reported():
    assert _rst_a03(_ideal_diode(uvlo=False))


def test_uvlo_pin_needs_its_own_divider_and_rule_instances_agree():
    from checkers.power_up import PowerUpChecker, build_inventory
    db = _ideal_diode()
    for net in ('VS_N', 'UVLO_N'):     # R105 removed: UVLO only pulled down, no turn-on point from the input
        db['nets'][net] = [n for n in db['nets'][net] if not n.startswith('R105.')]
    del db['parts']['R105'], db['pin2net']['R105.1'], db['pin2net']['R105.2']
    assert _rst_a03(db)
    assert PowerUpChecker().rule_instances('RST-A03', build_inventory(_ideal_diode())) == []
    assert PowerUpChecker().rule_instances('RST-A03', build_inventory(db))


# F16–F18: datasheet title cues (TI TVS3300 SLVSDO2C p1, Bourns MF-R p1, ST IPS4140HQ DS14694 p1)
def test_surge_protection_device_title_names_a_tvs_but_not_over_a_varistor():
    import datasheet_kinds as dk
    assert dk.cues('TVS3300 33-V Flat-Clamp Surge Protection Device') == {'tvs'}
    assert dk.cues('SIOV metal oxide varistors, surge protection device') == {'varistor'}
    assert dk.cues('Bidirectional TVS diode and varistor array') == {'tvs', 'varistor'}


"""Boards merge 4 (2026-11-02): systematic false alarms and missed questions left after the 86-board run."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from checkers import passive_stress
import test_passive_stress as tps


# 1. Fractional power ratings (pslab: "1/16W 5%" read as 16 W, a false PASS).
def test_fractional_power_rating_is_one_token():
    assert passive_stress.bom_ratings({'Description': '1/16W 5%'}) == {'power_w': 0.0625}
    assert passive_stress.bom_ratings({'Spec': '1/10 W'}) == {'power_w': 0.1}
    assert passive_stress.bom_ratings({'Spec': '10V 1/8W'}) == {'voltage_v': 10.0, 'power_w': 0.125}
    assert passive_stress.bom_ratings({'Spec': '100k/1/4W'}) == {'power_w': 0.25}
    assert passive_stress.bom_ratings({'Spec': '2W'}) == {'power_w': 2.0}


def test_half_read_fraction_is_unknown_not_a_floor():
    for text in ('0.1/16W', '1/0W'):
        ratings = passive_stress.bom_ratings({'Spec': text})
        assert ratings == {'power_unread': True}


def test_one_sixteenth_watt_does_not_pass_half_a_watt():
    helper = tps.ProposalTests()
    db, intent = helper.unpackaged(r1='22R', c1='100n')   # 3.465^2 / 20.9 ohm = 0.57 W
    db['bom'] = {'parts': {'R1': {'Description': '1/16W 5%'}}}
    _, rows = tps.proposals(db, intent)
    calc = rows['R1']['proposal']['calculation']
    assert calc['p_floor_w'] == 0.0625 and rows['R1']['proposal']['result'] is None
    db['bom'] = {'parts': {'R1': {'Description': '0.1/16W 5%'}}}
    _, rows = tps.proposals(db, intent)
    assert rows['R1']['proposal']['result'] is None
    assert '读不出' in rows['R1']['proposal']['note']


# 2. A ground-named divider midpoint (openrefmic VGND, studio_mic GNDA) is no 0 V reference.
def _midpoint_board(rail=True):
    from test_boards_merge2b_roles import empty
    from test_inductive_load import add
    db = empty()
    add(db, 'U1', 'OPA4991', [('4', 'V+', 'AMP_VDD'), ('11', 'V-', 'GND'), ('5', '+', 'VGND'), ('6', '-', 'FB'), ('7', 'OUT', 'FB')])
    db['native_pintype'] = {'U1.4': 'power_in', 'U1.11': 'power_in', 'U1.5': 'input', 'U1.6': 'input', 'U1.7': 'output'}
    add(db, 'R20', '7.15k', [('1', '', 'AMP_VDD'), ('2', '', 'VGND')])
    add(db, 'R21', '7.15k', [('1', '', 'VGND'), ('2', '', 'GND')])
    add(db, 'C11', '22uF', [('1', '', 'VGND'), ('2', '', 'GND')])
    for ref in ('R20', 'R21'):
        db['parts'][ref]['jedec'] = 'Resistor_SMD:R_0603_1608Metric'
    db['parts']['C11']['jedec'] = 'Capacitor_SMD:C_0805_2012Metric'
    intent = {'power_rails': {'AMP_VDD': {'citation': 'fixture', 'voltage_v': {'min': 4.5, 'max': 5.5}}} if rail else {}}
    return db, intent


def test_divider_midpoint_named_like_ground_is_not_zero_volts():
    from checkers.netgraph import NetGraph
    db, intent = _midpoint_board()
    graph = NetGraph(db)
    assert passive_stress.midpoint_ground(graph, 'VGND')
    assert not passive_stress.midpoint_ground(graph, 'GND')
    bounds = passive_stress._Bounds(graph, passive_stress._declared_rails(intent))
    assert bounds._fixed('VGND') is None and bounds._fixed('GND') == (0.0, 0.0)
    window, basis, _ = bounds.window('VGND')
    assert window is not None and window[1] == 5.5
    assert 'VGND' not in sum(passive_stress.ground_domains(db, intent).values(), [])


def test_midpoint_without_declared_rail_leaves_a_dependency_not_a_pass():
    from checkers.netgraph import NetGraph
    db, intent = _midpoint_board(rail=False)
    bounds = passive_stress._Bounds(NetGraph(db), passive_stress._declared_rails(intent))
    window, gap, _ = bounds.window('VGND')
    assert window is None and gap


def test_a_real_ground_with_an_ic_return_pin_stays_zero():
    from checkers.netgraph import NetGraph
    db, intent = _midpoint_board()
    from test_inductive_load import add
    add(db, 'U2', 'LDO', [('2', 'GND', 'VGND'), ('1', 'VIN', 'AMP_VDD')])
    db['native_pintype']['U2.2'] = 'power_in'
    assert not passive_stress.midpoint_ground(NetGraph(db), 'VGND')


def test_divider_midpoint_is_no_reference_domain():
    from checkers.netgraph import NetGraph
    from checkers import domains
    db, intent = _midpoint_board()
    labels = domains.ground_labels(NetGraph(db), intent)
    assert 'GND' in labels and 'VGND' not in labels


def test_a_ground_bled_to_ground_is_still_a_ground():
    from checkers.netgraph import NetGraph
    from test_inductive_load import add
    db, intent = _midpoint_board()
    add(db, 'R99', '1M', [('1', '', 'CHASSIS_GND'), ('2', '', 'GND')])   # a bleed resistor, no divider
    assert not passive_stress.midpoint_ground(NetGraph(db), 'CHASSIS_GND')

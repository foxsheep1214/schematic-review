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


# 3. A bias/reference feed through a kilo-ohm resistor is a weak drive, not "no drive" (PCA9306 VREF2, phantom feed).
def _weak_board(resistor=True):
    from test_boards_merge2b_roles import empty
    from test_inductive_load import add
    db = empty()
    add(db, 'U2', 'LDO', [('1', 'VIN', '+12V'), ('2', 'VOUT', '+5V'), ('3', 'GND', 'GND')])
    add(db, 'U19', 'PCA9306', [('7', 'VREF2', 'NREF'), ('4', 'GND', 'GND')])
    add(db, 'J1', 'CONN_01X02', [('1', '', '+12V'), ('2', '', 'GND')])
    db['native_pintype'] = {'U19.7': 'power_in', 'U19.4': 'power_in', 'U2.1': 'power_in', 'U2.2': 'power_out'}
    if resistor:
        add(db, 'R63', '200k', [('1', '', '+5V'), ('2', '', 'NREF')])
    return db


def test_kilo_ohm_feed_is_a_weak_drive_with_its_resistor():
    from lint import Lint
    rows = [f for f in Lint(_weak_board()).run() if f['rule'] == 'PWR-A02' and 'U19.7' in f['detail']]
    assert rows and all(f['kind'] == 'INFO' for f in rows)
    assert '弱驱动，R=R63 200k' in rows[0]['detail']


def test_a_pin_with_no_feed_at_all_is_still_undriven():
    from lint import Lint
    rows = [f for f in Lint(_weak_board(resistor=False)).run() if f['rule'] == 'PWR-A02' and 'U19.7' in f['detail']]
    assert rows and rows[0]['kind'] == 'FINDING'


def test_weak_source_names_resistor_and_far_net():
    from checkers.netgraph import NetGraph
    from checkers.powertree import PowerTree
    found = PowerTree(NetGraph(_weak_board())).weak_source('NREF')
    assert found['resistor'] == 'R63' and found['via'] == '+5V' and found['ohm'] == 200000
    assert PowerTree(NetGraph(_weak_board())).weak_source('GND') is None


def test_rail_fed_only_through_a_resistor_is_weakly_driven():
    from lint import Lint
    from test_inductive_load import add
    db = _weak_board()
    add(db, 'R5', '2.2k', [('1', '', '+5V'), ('2', '', '+6V')])
    add(db, 'C5', '47uF', [('1', '', '+6V'), ('2', '', 'GND')])
    add(db, 'U1', 'OPA1652', [('8', 'V+', '+6V'), ('4', 'V-', 'GND')])
    db['native_pintype'].update({'U1.8': 'power_in', 'U1.4': 'power_in'})
    rows = [f for f in Lint(db).run() if f['rule'] == 'PWR-A01' and f['detail'].startswith('+6V')]
    assert rows and rows[0]['kind'] == 'INFO' and '弱驱动，R=R5 2.2k' in rows[0]['detail']


def test_a_resistor_to_an_undriven_net_is_no_weak_drive():
    from lint import Lint
    from test_inductive_load import add
    db = _weak_board(resistor=False)
    add(db, 'R64', '10k', [('1', '', 'NREF'), ('2', '', 'NOWHERE')])
    add(db, 'C64', '100n', [('1', '', 'NOWHERE'), ('2', '', 'GND')])
    rows = [f for f in Lint(db).run() if f['rule'] == 'PWR-A02' and 'U19.7' in f['detail']]
    assert rows and rows[0]['kind'] == 'FINDING'


# 4. Multi-output PMIC and integrated off-line switch ports (TPS65023 L1-L3/VDCDCx/VRTC, TOPSwitch DRAIN/CONTROL).
def _pmic_board():
    from test_boards_merge2b_roles import empty
    from test_inductive_load import add
    db = empty()
    add(db, 'U2', 'TPS65023BRSBT', [('6', 'VINDCDC1', 'VBUS'), ('7', 'L1', '/L1'), ('9', 'VDCDC1', '+1V0'),
                                    ('16', 'VRTC', '/VRTC'), ('20', 'VLDO1', 'GND'), ('8', 'PGND1', 'GND')])
    add(db, 'L1', '2.2uH', [('1', '', '/L1'), ('2', '', '+1V0')])
    add(db, 'C26', '22uF', [('1', '', '+1V0'), ('2', '', 'GND')])
    add(db, 'C23', '1uF', [('1', '', '/VRTC'), ('2', '', 'GND')])
    add(db, 'U1', 'FPGA', [('F8', 'VCCINT', '+1V0'), ('A1', 'GND', 'GND')])
    add(db, 'J1', 'USB', [('1', 'VBUS', 'VBUS'), ('2', 'GND', 'GND')])
    db['native_pintype'] = {'U2.16': 'power_in', 'U2.20': 'power_in', 'U2.6': 'power_in', 'U2.9': 'passive',
                            'U2.7': 'passive', 'U1.F8': 'power_in', 'U2.8': 'power_in'}
    return db


def test_pmic_output_ports_are_sources_and_switch_pins_feed_their_inductor():
    from checkers.netgraph import NetGraph
    from checkers.powertree import PowerTree
    tree = PowerTree(NetGraph(_pmic_board()))
    assert 'exact family pin table' in tree.source_of('+1V0')['basis']
    assert tree.source_of('/VRTC')['source'] == 'U2.16'


def test_pmic_rails_are_driven_and_a_grounded_output_port_is_only_a_candidate():
    from lint import Lint
    found = Lint(_pmic_board()).run()
    assert not [f for f in found if f['rule'] in ('PWR-A01', 'PWR-A02') and f['kind'] == 'FINDING'
                and ('+1V0' in f['detail'] or '/VRTC' in f['detail'])]
    grounded = [f for f in found if f['rule'] == 'PWR-A02' and 'U2.20' in f['detail']]
    assert grounded and grounded[0]['kind'] == 'CANDIDATE' and '输出端口' in grounded[0]['detail']


def test_each_pmic_output_gets_its_own_output_capacitor_question():
    from plan_review import build_review_plan
    rows = [c for c in build_review_plan(_pmic_board())['checks'] if c['rule'] == 'PWR-C04']
    assert {'U2.9', 'U2.16'} <= {r['object'].get('node') for r in rows}
    assert 'U2.20' not in {r['object'].get('node') for r in rows}   # a grounded port is no supply node


def test_topswitch_drain_and_control_satisfy_switch_and_feedback_preconditions():
    from checkers.netgraph import NetGraph
    from plan_circuits import subject_precondition
    from test_boards_merge2b_roles import empty
    from test_inductive_load import add
    db = empty()
    add(db, 'U1', 'TOP204YAI', [('1', 'C', 'CTRL'), ('2', 'S', 'GND'), ('3', 'D', 'DRAIN')])
    db['parts']['U1']['value'] = 'TOPSWITCH 12V'   # the part number names the family when the value does not
    graph = NetGraph(db)
    assert subject_precondition(graph, db['pinname'], 'SWITCH_PIN', ['U1'], [])[0] == ['U1']
    assert subject_precondition(graph, db['pinname'], 'FEEDBACK_PIN', ['U1'], [])[0] == ['U1']
    db['parts']['U1'].update(part='GENERIC3', value='GENERIC3')
    assert subject_precondition(NetGraph(db), db['pinname'], 'SWITCH_PIN', ['U1'], [])[0] == []


# 5. Isolated DC/DC modules keep two sides; their grounds are never merged (PEM1-S, B0505S, URB, ULT).
def _module(part, pins):
    from test_boards_merge2b_roles import empty
    from test_inductive_load import add
    db = empty()
    add(db, 'U102', part, pins)
    return db


def test_dual_output_module_sides_and_outputs_from_pin_names():
    from checkers.netgraph import NetGraph
    from checkers import isolation_sides
    db = _module('PEM1-S12-D12-S', [('1', 'VIN', 'VIN12'), ('2', 'GND', 'GND'), ('5', '-Vo', '-12V'), ('6', '0V', 'AGND'),
                                     ('7', '+Vo', '+12V')])
    side = isolation_sides.model(NetGraph(db), 'U102')
    assert side['mechanism'] == 'isolated_dcdc' and side['resolved']
    assert [s['nets'] for s in side['sides']] == [['GND', 'VIN12'], ['+12V', '-12V', 'AGND']]
    assert side['power_outputs'] == ['5', '7']


def test_single_output_module_minus_vout_is_a_return():
    from checkers.netgraph import NetGraph
    from checkers import isolation_sides
    from checkers.powertree import PowerTree
    db = _module('B0505S-3WR2', [('1', '+Vin', '+5V'), ('2', '-Vin', 'GND'), ('4', '-Vout', 'GND_ISO'), ('6', '+Vout', '+5V_ISO')])
    side = isolation_sides.model(NetGraph(db), 'U102')
    assert side['power_outputs'] == ['6']
    assert PowerTree(NetGraph(db)).source_of('+5V_ISO')['source'] == 'U102.6'


def test_module_grounds_stay_two_domains():
    from checkers.netgraph import NetGraph
    from checkers import domains
    db = _module('MORNSUN-URB2405YMD-6WR3', [('2', 'Vin', 'VIN24'), ('1', 'GND', 'PGND'), ('4', '0V', 'GND'), ('3', '+Vo', '+5V')])
    assert not domains.conducts(NetGraph(db), 'U102')
    db['parts']['U102'].update(part='LM7805', value='LM7805', prim='LM7805')
    from checkers import isolation_sides
    assert isolation_sides.model(NetGraph(db), 'U102') is None   # a regulator is not a module by its pin names


def test_module_pin_names_with_subscripts_are_read():
    from checkers.netgraph import NetGraph
    from checkers import isolation_sides
    db = _module('PDQE30-Q48-S5-D', [('1', 'CTRL', 'POE_ACTIVE'), ('2', 'GND', 'GNDD'), ('3', 'V_{IN}', 'VDD_POE_IN'),
                                      ('4', 'V_{O}', 'VO5V'), ('5', 'TRIM', 'TRIM'), ('6', '0V', 'GND')])
    side = isolation_sides.model(NetGraph(db), 'U102')
    assert side['sides'][0]['nets'] == ['GNDD', 'POE_ACTIVE', 'VDD_POE_IN'] and side['power_outputs'] == ['4']


# 6. Dual MOS per channel (FS8205A G1/S1/D12, G2/S2/D12) and lettered isolator sides (MAX14850 VCCA/GNDA, VCCB/GNDB).
def test_dual_mos_is_two_channels_sharing_the_drain():
    from test_boards_merge2b_roles import empty
    from test_inductive_load import add
    from checkers import power_switch
    db = empty()
    add(db, 'U2', 'FS8205A', [('1', 'D12', 'DRN'), ('2', 'S1', 'GND_ISO'), ('3', 'S1', 'GND_ISO'), ('4', 'G1', 'OD'),
                              ('5', 'G2', 'OC'), ('6', 'S2', 'GND'), ('7', 'S2', 'GND'), ('8', 'D12', 'DRN')])
    db['device_kinds'] = {'U2': {'kind': 'mosfet', 'citation': 'FS8205A datasheet p1'}}
    db['parts']['U2']['prim'] = 'Q_Dual_NMOS'
    inventory = power_switch.build_inventory(db)
    switches = [s for state in inventory['states'] for s in state['switches'] if s['ref'] == 'U2']
    by_gate = {s['gate_net']: s for s in switches}
    assert set(by_gate) == {'OD', 'OC'}
    assert by_gate['OD']['source_net'] == 'GND_ISO' and by_gate['OC']['source_net'] == 'GND'
    assert by_gate['OD']['drain_net'] == by_gate['OC']['drain_net'] == 'DRN'
    assert {s['channel'] for s in switches} == {'1', '2'}


def test_unindexed_dual_mos_channels_stay_unresolved():
    from test_boards_merge2b_roles import empty
    from test_inductive_load import add
    from checkers import power_switch
    db = empty()
    add(db, 'Q2', 'SiZ270DT', [('1', 'G', 'GA'), ('2', 'D', 'VMOT'), ('5', 'S', 'SRC'), ('8', 'G', 'GB'), ('9', 'S', 'PHASE')])
    db['device_kinds'] = {'Q2': {'kind': 'mosfet', 'citation': 'SiZ270DT datasheet p1'}}
    inventory = power_switch.build_inventory(db)
    switches = [s for state in inventory['states'] for s in state['switches'] if s['ref'] == 'Q2']
    assert {s['gate_net'] for s in switches} == {'GA', 'GB'}
    assert all('channel-pin-map:Q2' in s['gaps'] and s['source_net'] is None for s in switches)


def test_lettered_isolator_sides_follow_supply_letters_not_channel_digits():
    from test_boards_merge2b_roles import empty
    from test_inductive_load import add
    from checkers.netgraph import NetGraph
    from checkers import isolation_sides
    db = empty()
    add(db, 'U103', 'MAX14850', [('1', 'VCCA', '3V3'), ('8', 'GNDA', 'GND'), ('2', 'INA1', 'M-CLK'), ('4', 'OUTA1', 'M-MISO'),
                                 ('16', 'VCCB', 'VEE'), ('9', 'GNDB', 'AGND'), ('15', 'OUTB1', 'B1'), ('12', 'INB2', 'B2')])
    db['device_kinds'] = {'U103': {'kind': 'isolator', 'citation': 'MAX14850 p11'}}
    side = isolation_sides.model(NetGraph(db), 'U103')
    assert side['mechanism'] == 'digital_isolator'
    assert [s['nets'] for s in side['sides']] == [['3V3', 'GND', 'M-CLK', 'M-MISO'], ['AGND', 'B1', 'B2', 'VEE']]

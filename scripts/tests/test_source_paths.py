"""Source presence is not impedance equivalence or an electrical PASS."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import board_intent
import circuit_candidates as cc
from checkers import input_filter, power_up, power_switch, inductive_load
from checkers.netgraph import NetGraph
from plan_review import build_review_plan
from test_inductive_load import add, relay_board
import test_circuit_candidates as fx
from test_power_up import rail_board, regulators_of
from test_input_filter import converter, converters_of


def test_enable_drive_through_4k7_keeps_source_and_path_but_megohms_do_not():
    for value, expected in [('4k7', 'controlled'), ('10k', 'controlled'), ('1M', 'unknown'), ('2M', 'unknown')]:
        db = rail_board(enable=None)
        add(db, 'U9', 'SOC', [('1', 'GPIO', 'CTRL')])
        db.setdefault('pintype', {})['U9.1'] = 'OUT'
        add(db, 'R90', value, [('1', '1', 'CTRL'), ('2', '2', 'EN_3V3')])
        item = regulators_of(power_up.build_inventory(db))['U1']
        assert item['enable_source'] == expected
        if expected == 'controlled':
            assert item['enable_evidence'] == [{'node': 'U9.1', 'source': 'controller-output', 'via': ['R90']}]
        assert 'CTRL' not in NetGraph(db).low_resistance_peers('EN_3V3')


def test_ground_and_shared_rail_do_not_become_gate_drivers_through_bias_resistors():
    db = relay_board()
    add(db, 'R9', '4k7', [('1', '1', 'RELAY_EN'), ('2', '2', 'GND')])
    add(db, 'J9', 'Connector:Conn_01x02', [('1', '1', 'GND'), ('2', '2', 'V24')])
    inv = power_switch.build_inventory(db)
    switch = inv['states'][0]['switches'][0]
    assert not any(x['source'] == 'external' for x in switch['drivers'])


def test_signal_source_budget_is_total_and_never_crosses_megohm_or_unknown_value():
    db = {'parts': {}, 'nets': {}, 'pin2net': {}, 'pinname': {}, 'pintype': {}, 'pseudo_nets': []}
    for ref, a, b, value in [('R1', 'EN', 'MID', '4k7'), ('R2', 'MID', 'CTRL', '4k7'),
                              ('R3', 'CTRL', 'FAR', '4k7'), ('R4', 'EN', 'LEAK', '1M'),
                              ('R5', 'EN', 'UNKNOWN', 'R')]:
        add(db, ref, value, [('1', '1', a), ('2', '2', b)])
    peers = NetGraph(db).signal_source_peers('EN')
    assert peers['CTRL'] == ['R1', 'R2']
    assert not {'FAR', 'LEAK', 'UNKNOWN'} & peers.keys()


def test_upstream_buck_output_inductor_is_not_extra_input_filter():
    db = converter(series=None)
    # U1 consumes V12; L9 is the upstream U9 buck's output inductor, not a separate filter.
    add(db, 'U9', 'BUCK', [('1', 'VIN', 'V24'), ('2', 'SW', 'SW9'), ('3', 'GND', 'GND')])
    add(db, 'L9', 'IND-10uH', [('1', '1', 'SW9'), ('2', '2', 'VIN_12')])
    item = converters_of(input_filter.build_inventory(db))['U1']
    assert item['series_elements'] == []
    assert item['upstream_conversion'][0]['ref'] == 'L9'
    plan = build_review_plan(db)
    assert not any(x['rule'] in ('PWR-E03', 'PWR-C11') and x['object'].get('ref') == 'U1' for x in plan['checks'])
    assert any(x['code'] == 'CASCADED_CONVERTER' and x['ref'] == 'U1' for x in plan['diagnostics'])


def test_gpio_relay_driver_still_does_not_become_converter():
    db = relay_board()
    add(db, 'U9', 'MCU', [('1', 'GPIO', 'RELAY_EN'), ('2', 'VCC', 'V24'), ('3', 'GND', 'GND')])
    db.setdefault('pintype', {})['U9.1'] = 'OUT'
    i, a = fx.intent_for(db, kinds={'U9': 'mcu', 'Q1': 'mosfet', 'K1': 'relay'}, rails={})
    c = cc.build(db, i, a)
    assert not any(x['type'] == 'POWER_CONVERTER' for x in c['candidates'])
    assert inductive_load.build_inventory(db)['states'][0]['loads'][0]['switch_ref'] == 'Q1'


def test_bridged_jumpers_are_not_bridge_rectifiers_or_input_protection():
    db = {'parts': {}, 'nets': {}, 'pin2net': {}, 'pinname': {}, 'pintype': {}, 'pseudo_nets': []}
    add(db, 'J1', 'Connector:Conn_01x02', [('1', '1', 'PORT'), ('2', '2', 'GND')])
    add(db, 'JP1', 'Jumper:SolderJumper_2_Bridged', [('1', '1', 'PORT'), ('2', '2', 'VCC')])
    add(db, 'C1', '22uF', [('1', '1', 'VCC'), ('2', '2', 'GND')])
    assert not any(x['type'] == 'POWER_PROTECTION' for x in cc.build(db)['candidates'])


def test_verified_load_switch_has_enable_review_without_ldo_dropout():
    db = rail_board(enable='gpio')
    i, a = fx.intent_for(db, kinds={'U1': 'load_switch'}, rails={})
    plan = build_review_plan(db, i, datasheet_audit=a)
    item = plan['power_up']['states'][0]['regulators'][0]
    assert item['kind'] == 'load_switch'
    assert any(x['rule'] == 'RST-T01' and x['object'].get('ref') == 'U1' for x in plan['checks'])
    assert not any(x['rule'] == 'PWR-E02' and x['object'].get('ref') == 'U1' for x in plan['checks'])


def test_passive_balun_without_energy_switch_is_not_a_coil_load():
    db = {'parts': {}, 'nets': {}, 'pin2net': {}, 'pinname': {}, 'pintype': {}, 'pseudo_nets': []}
    add(db, 'T1', 'TRANSFORMER', [('1', 'PRI1', 'RF1'), ('2', 'PRI2', 'RF2'), ('3', 'SEC1', 'RF3')])
    assert inductive_load.build_inventory(db)['states'][0]['loads'] == []
    add(db, 'Q1', 'MOSFET-N', [('1', 'G', 'GATE'), ('2', 'D', 'RF1'), ('3', 'S', 'GND')])
    load = inductive_load.build_inventory(db)['states'][0]['loads'][0]
    assert 'pin-roles:T1' in load['gaps']   # a real switched magnetic part with unknown winding map stays open


def test_gate_source_protection_zener_does_not_make_a_load_switch_a_linear_regulator():
    db = {'parts': {}, 'nets': {}, 'pin2net': {}, 'pinname': {}, 'pintype': {}, 'pseudo_nets': []}
    add(db, 'Q1', 'MOSFET-P', [('1', 'G', 'GATE'), ('2', 'D', 'OUT'), ('3', 'S', 'VIN')])
    add(db, 'D1', 'ZENER-12V', [('1', 'A', 'GATE'), ('2', 'K', 'VIN')])
    add(db, 'R1', '100k', [('1', '1', 'GATE'), ('2', '2', 'VIN')])
    add(db, 'C1', '10uF', [('1', '1', 'VIN'), ('2', '2', 'GND')])
    i, a = fx.intent_for(db, kinds={'Q1': 'mosfet', 'D1': 'zener'}, rails={})
    assert not any(x['type'] == 'POWER_CONVERTER' for x in cc.build(db, i, a)['candidates'])


def test_isolated_amplifier_output_source_keeps_its_physical_side_across_a_ferrite():
    from test_isolation_sides import amc
    from checkers.powertree import PowerTree
    db = amc()
    add(db, 'FB1', 'FERRITE', [('1', '1', 'N1'), ('2', '2', 'N3')])
    source = PowerTree(NetGraph(db)).source_of('N3')
    assert source['source'] == 'U6.1' and source['path'] == ['FB1']
    assert source['side'] == '1' and 'Table 5-1' in source['basis']


def test_supply_bypass_reached_by_generic_walk_has_unlimited_reference_role():
    from test_boards_merge2a import three_bucks
    db, (i, a) = three_bucks()
    g = cc.Generator(db, i, a)
    g.new('A', 'ANALOG', 'U1', 'GND')
    g.add('A', 'C99', 'capacitor', 'walk U1.1 -> VCC -> C99', 1)
    assert g.candidates['A']['members']['C99']['role'] == 'decoupling'


def test_integrated_sw_pin_preserves_real_transformer_winding_review():
    db = {'parts': {}, 'nets': {}, 'pin2net': {}, 'pinname': {}, 'pintype': {}, 'pseudo_nets': []}
    add(db, 'T1', 'TRANSFORMER', [('1', 'PRI1', 'SW'), ('2', 'PRI2', 'VIN'), ('3', 'SEC1', 'OUT')])
    add(db, 'U1', 'LT3957', [('1', 'SW', 'SW'), ('2', 'VIN', 'VIN'), ('3', 'GND', 'GND')])
    load = inductive_load.build_inventory(db)['states'][0]['loads'][0]
    assert load['ref'] == 'T1' and 'pin-roles:T1' in load['gaps']


def test_fractional_watt_annotation_does_not_cut_a_real_2k_drive_path():
    from solve_dividers import parse_resistor
    parsed = parse_resistor('2k/1/8W')
    assert parsed['kohm'] == 2 and parsed['power_w'] == .125
    assert parse_resistor('2k/1%/1/8W')['tol'] == .01
    assert parse_resistor('2k/1/0W') is None
    assert parse_resistor('2k/1/8V') is None
    assert parse_resistor('2k/garbage/1/8W') is None
    db = relay_board()
    add(db, 'U9', 'MCU', [('1', 'GPIO', 'CTRL')])
    db.setdefault('pintype', {})['U9.1'] = 'OUT'
    add(db, 'R9', '2k/1/8W', [('1', '1', 'CTRL'), ('2', '2', 'RELAY_EN')])
    switch = power_switch.build_inventory(db)['states'][0]['switches'][0]
    assert any(x['node'] == 'U9.1' for x in switch['drivers'])


def test_enable_on_real_supply_output_is_not_unknown_when_own_supply_is_called_sup():
    db = {'parts': {}, 'nets': {}, 'pin2net': {}, 'pinname': {}, 'pintype': {}, 'pseudo_nets': []}
    add(db, 'U1', 'BUCK', [('1', 'SUP', 'FEED'), ('2', 'EN', 'FEED'), ('3', 'SW', 'SW'), ('4', 'GND', 'GND')])
    add(db, 'U9', 'EFUSE', [('1', 'IN', 'VIN'), ('2', 'OUT', 'FEED'), ('3', 'GND', 'GND')])
    item = regulators_of(power_up.build_inventory(db))['U1']
    assert item['enable_source'] == 'supplied'
    assert item['enable_evidence'] == [{'node': 'U9.2', 'source': 'supply-output', 'via': []}]
    from lint import Lint
    assert not any(x['rule'] == 'RST-A04' and x.get('ref') == 'U1' for x in Lint(db).run())

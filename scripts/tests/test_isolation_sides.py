"""Reference side models keep genuine shorts visible and preserve dry-contact/optical isolation objects."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import board_intent
import circuit_candidates as cc
import test_circuit_candidates as fx
from test_inductive_load import add
from checkers import domains, isolation_sides
from checkers.netgraph import NetGraph
from plan_review import build_review_plan


def empty():
    return {'parts': {}, 'nets': {}, 'pin2net': {}, 'pinname': {}, 'pintype': {}, 'pseudo_nets': []}


def amc():
    db = empty()
    names = ['DCDC_OUT', 'DCDC_HGND', 'HLDO_IN', 'NC', 'HLDO_OUT', 'IN', 'HGND', 'HGND',
             'GND', 'OUTN', 'OUTP', 'VDD', 'LDO_OUT', 'DIAG', 'DCDC_GND', 'DCDC_IN']
    add(db, 'U6', 'AMC3311DWER', [(str(n), name, 'HGND' if n in (2, 7, 8) else 'GND' if n in (9, 15) else f'N{n}')
                                 for n, name in enumerate(names, 1)])
    return db


def test_amc3311_keeps_both_references_despite_regulator_role():
    db = amc(); i, a = fx.intent_for(db, kinds={'U6': 'regulator'}, rails={})
    g = NetGraph(board_intent.graph_db(db, board_intent.with_verified_kinds(i, a)))
    d = domains.derive(g, i)
    assert d['nets']['N6'] == 'HGND'
    assert d['nets']['N12'] == 'GND'
    assert d['conflicts'] == []
    side = d['barriers'][0]
    assert side['mechanism'] == 'isolated_amplifier'
    assert side['sides'][0]['domains'] == ['HGND']
    assert side['sides'][1]['domains'] == ['GND']
    assert 'Table 5-1' in side['citation']
    add(db, 'R1', '0R', [('1', '1', 'HGND'), ('2', '2', 'GND')])
    g = NetGraph(board_intent.graph_db(db, board_intent.with_verified_kinds(i, a)))
    assert any(x['code'] == 'DOMAIN_MERGED' and x['via'] == ['R1'] for x in domains.derive(g, i)['conflicts'])


def test_isolated_dcdc_input_output_groups_do_not_merge():
    for part, in_pins, out_pins in [('REC15E-2405SZ', ['1', '2', '3'], ['4', '5', '6']),
                                   ('DP5305', ['1', '2', '3', '4'], ['5', '6', '7', '8'])]:
        db = empty()
        add(db, 'U1', part, [(p, 'VIN-' if p == '2' else 'VOUT-' if p == out_pins[0] else p,
                             'GND_IN' if p == '2' else 'GND_OUT' if p == out_pins[0] else f'N{p}')
                            for p in in_pins + out_pins])
        g = NetGraph(db); d = domains.derive(g)
        assert d['conflicts'] == []
        assert d['nets']['GND_IN'] != d['nets']['GND_OUT']
        assert d['barriers'][0]['resolved']
        assert d['barriers'][0]['basis'] == 'model-pin-rule'


def test_megohm_bleed_does_not_connect_reference_domains_but_zero_ohms_do():
    db = empty()
    add(db, 'R101', '1M', [('1', '1', 'GND1'), ('2', '2', 'SHIELD')])
    add(db, 'R102', '1M', [('1', '1', 'GND2'), ('2', '2', 'SHIELD')])
    d = domains.derive(NetGraph(db))
    assert d['conflicts'] == []
    assert d['nets']['GND1'] != d['nets']['GND2']
    for ref in ('R101', 'R102'): db['parts'][ref]['value'] = '0R'
    assert any(x['code'] == 'DOMAIN_MERGED' for x in domains.derive(NetGraph(db))['conflicts'])


def test_common_ground_opto_and_floating_dry_contacts_still_have_isolation_candidates():
    db = empty()
    add(db, 'U1', 'PC817', [('1', 'A', 'LED'), ('2', 'K', 'GND'), ('3', 'E', 'GND'), ('4', 'C', 'DRIVE')])
    add(db, 'K1', 'RELAY', [('1', 'COIL1', 'VCC'), ('2', 'COIL2', 'DRIVE'), ('3', 'COM', 'COM'), ('4', 'NO', 'NO')])
    c = cc.build(db)
    objects = {b['ref']: b for b in c['domains']['barriers']}
    assert objects['U1']['mechanism'] == 'optocoupler'
    assert objects['K1']['mechanism'] == 'relay'
    assert set(objects) == {'U1', 'K1'}
    assert sum(x['type'] == 'ISOLATION' for x in c['candidates']) == 2
    assert not any(x['code'] == 'DOMAIN_MERGED' for x in c['domains']['conflicts'])


def test_passive_transformer_isolation_does_not_invent_digital_default_rate_cmti():
    db = empty()
    add(db, 'T1', 'TRANSFORMER', [('1', 'PRI1', 'PRI'), ('2', 'PRI2', 'GND1'),
                                ('3', 'SEC1', 'SEC'), ('4', 'SEC2', 'GND2')])
    plan = build_review_plan(db, {'schema_version': 5, 'circuits': [
        {'id': 'ISO', 'type': 'ISOLATION', 'refs': ['T1'], 'states': ['run'], 'citation': 'p1 transformer', 'nets': []}]})
    asked = {x['rule'] for x in plan['checks'] if x.get('object', {}).get('circuit') == 'ISO'}
    assert {'PRO-D02', 'PRO-C03'} <= asked
    assert not {'SIG-C17', 'SIG-C13', 'SIG-C09', 'RST-T04', 'PRO-C01'} & asked


def test_hy931147c_cable_poe_side_remains_separate_from_phy_and_external_header_is_visible():
    db = empty()
    add(db, 'U1', 'HY931147C', [('P$1', 'RX+', 'RX_P'), ('P$2', 'RX-', 'RX_N'), ('P$3', 'RXCT', 'VCC'),
                               ('P$9', 'V+', 'POE_P'), ('P$10', 'V-', 'POE_N')])
    add(db, 'J3', 'Connector:Conn_01x04', [('1', '1', 'POE_P'), ('2', '2', 'POE_N'), ('3', '3', 'GND'), ('4', '4', 'VCC')])
    c = cc.build(db)
    b = next(x for x in c['domains']['barriers'] if x['ref'] == 'U1')
    assert b['mechanism'] == 'ethernet_magnetics' and b['resolved']
    assert b['sides'][1]['nets'] == ['POE_N', 'POE_P']
    iso = next(x for x in c['candidates'] if x['type'] == 'ISOLATION')
    assert {'U1', 'J3'} <= {m['ref'] for m in iso['members']}
    assert {'POE_P', 'POE_N', 'VCC'} <= set(iso['nets'].values())


def test_full_ground_net_domain_reference_is_an_alias_and_duplicate_leaf_names_stay_distinct():
    db = empty()
    add(db, 'U1', 'IC', [('1', 'VDD', 'V_A'), ('2', 'GND', '/ADC/GND')])
    add(db, 'U2', 'IC', [('1', 'VDD', 'V_B'), ('2', 'GND', '/RF/GND')])
    d = domains.derive(NetGraph(db), {'power_rails': {'V_A': {'domain': '/ADC/GND'}}})
    assert d['conflicts'] == []
    assert d['nets']['V_A'] == '/ADC/GND'
    assert d['nets']['V_B'] == '/RF/GND'


def test_a_domain_naming_the_full_ground_net_resolves_to_its_label():
    db = empty()
    add(db, 'U1', 'IC', [('1', 'VDD', 'V_A'), ('2', 'GND', '/ADC/GND')])
    d = domains.derive(NetGraph(db), {'power_rails': {'V_A': {'domain': '/ADC/GND'}}})
    assert d['nets']['V_A'] == 'GND'
    assert d['conflicts'] == []

"""Board-derived contracts: shared supply ownership, rejection release and converter topology."""
import copy
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import circuit_candidates as cc
import circuit_decisions as cd
import test_circuit_candidates as fx
from test_inductive_load import add, relay_board


def three_bucks():
    db = {'parts': {}, 'nets': {}, 'pin2net': {}, 'pinname': {}, 'pintype': {}, 'pseudo_nets': []}
    kinds = {}
    for i in range(1, 4):
        ref = f'U{i}'; kinds[ref] = 'regulator'
        add(db, ref, 'BUCK', [('1', 'VIN', 'VCC'), ('2', 'GND', 'GND'), ('3', 'SW', f'SW{i}'), ('4', 'FB', f'FB{i}')])
        add(db, f'L{i}', 'IND-4u7', [('1', '1', f'SW{i}'), ('2', '2', f'OUT{i}')])
        add(db, f'R{i}', '10k', [('1', '1', f'OUT{i}'), ('2', '2', f'FB{i}')])
        add(db, f'C{i}', '22uF', [('1', '1', f'OUT{i}'), ('2', '2', 'GND')])
    add(db, 'C99', '22uF', [('1', '1', 'VCC'), ('2', '2', 'GND')])
    return db, fx.intent_for(db, kinds=kinds, rails={'VCC': {'voltage_v': {'min': 12, 'max': 12}}})


def test_three_independent_bucks_share_input_caps_without_crossing_supply():
    db, (intent, audit) = three_bucks()
    intent['power_rails'] = {}   # physical shared VIN is a boundary before rail declarations are complete
    add(db, 'R88', '10k', [('1', '1', 'VCC'), ('2', '2', 'OTHER_CHANNEL')])
    add(db, 'C88', '100nF', [('1', '1', 'OTHER_CHANNEL'), ('2', '2', 'GND')])
    c = cc.build(db, intent, audit)
    bucks = [x for x in c['candidates'] if x['type'] == 'POWER_CONVERTER']
    assert len(bucks) == 3
    for i, b in enumerate(bucks, 1):
        refs = {m['ref'] for m in b['members']}
        assert 'C99' in refs
        assert 'R88' not in refs and 'C88' not in refs
        assert not ({'L1', 'L2', 'L3', 'R1', 'R2', 'R3'} - {f'L{i}', f'R{i}'}) & refs
    circuits, errors = cd.derive(c, [{'decision': 'accept', 'candidate': x['id']} for x in c['candidates']])
    assert errors == []
    assert sum('C99' in x['refs'] for x in circuits) == 3
    assert sum('C99' in x['owned'] for x in circuits) == 1


def test_relay_driver_and_declared_level_translation_are_not_converters():
    db = relay_board()
    intent, audit = fx.intent_for(db, kinds={'Q1': 'mosfet', 'K1': 'relay'}, rails={})
    intent['power_switches'] = {'schema_version': 2, 'switches': [
        {'id': 'DRIVE', 'ref': 'Q1', 'role': 'low_side_driver', 'citation': 'schematic p1 relay driver'}]}
    c = cc.build(db, intent, audit)
    assert not any(x['type'] == 'POWER_CONVERTER' for x in c['candidates'])
    assert any(x['ref'] == 'Q1' for x in c['unassigned'])
    intent['power_switches']['switches'][0]['role'] = 'level_shifter'
    assert not any(x['type'] == 'POWER_CONVERTER' for x in cc.build(db, intent, audit)['candidates'])


def rejected_fixture():
    member = {'ref': 'Q2', 'role': 'anchor', 'via': 'anchor: declared switch', 'nets': ['SDA_L', 'SDA_H'], 'owned': True}
    return {'schema_version': 2, 'candidates': [{'id': 'POWER_CONVERTER-Q2', 'anchor': 'Q2', 'type': 'POWER_CONVERTER',
        'cross_cutting': False, 'states': ['run'], 'nets': {}, 'members': [member]}], 'unassigned': []}


def test_reject_releases_then_add_reassigns_with_original_net_evidence():
    c = rejected_fixture()
    reject = {'decision': 'reject', 'candidate': 'POWER_CONVERTER-Q2', 'reason': 'NOT_A_CIRCUIT', 'citation': 'schematic p1 signal MOS'}
    addition = {'decision': 'add', 'id': 'I2C-SHIFT', 'type': 'LEVEL_SHIFT', 'members': ['Q2'], 'via': {'Q2': 'SDA_L'}, 'citation': 'schematic p1 SDA_L to SDA_H'}
    circuits, errors = cd.derive(c, [reject, addition])
    assert errors == []
    assert circuits[0]['owned'] == ['Q2']
    assert cd.discovery_refs(c, [reject, addition]) == []
    assert any('held' in e for e in cd.derive(c, [addition, reject])[1])
    bad = dict(addition, via={'Q2': 'invented'})
    assert any('via' in e for e in cd.derive(c, [reject, bad])[1])
    bad = dict(reject, citation='no locator')
    assert any('citation' in e for e in cd.derive(c, [bad, addition])[1])


def test_shared_reference_still_held_by_retained_candidate_cannot_be_stolen():
    c = rejected_fixture()
    other = copy.deepcopy(c['candidates'][0]); other.update(id='ANALOG-U2', anchor='U2', type='ANALOG')
    other['members'][0].update(role='member', owned=False)
    c['candidates'].append(other)
    ds = [{'decision': 'reject', 'candidate': 'POWER_CONVERTER-Q2', 'reason': 'NOT_A_CIRCUIT', 'citation': 'p1'},
          {'decision': 'accept', 'candidate': 'ANALOG-U2'},
          {'decision': 'add', 'id': 'SHIFT', 'type': 'LEVEL_SHIFT', 'members': ['Q2'], 'via': {'Q2': 'SDA_L'}, 'citation': 'p1'}]
    assert any('held' in e for e in cd.derive(c, ds)[1])


def test_connector_input_walk_does_not_expand_a_shared_supply_seed():
    db, (intent, audit) = three_bucks()
    # Small bypasses alone must not make the whole shared rail a connector's private input network.
    db['parts']['C99']['value'] = '100nF'
    for i in range(4, 9):
        add(db, f'J{i}', 'Connector:Conn_01x02', [('1', '1', 'VCC'), ('2', '2', 'GND')])
    add(db, 'D99', 'TVS', [('1', 'A', 'GND'), ('2', 'K', 'VCC')])
    c = cc.build(db, intent, audit)
    assert not any(x['id'].startswith('POWER_PROTECTION-J') for x in c['candidates'])

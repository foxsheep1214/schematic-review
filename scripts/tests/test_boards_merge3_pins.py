"""Official physical pin tables reach connectivity without changing native facts."""
from copy import deepcopy
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import board_intent
from checkers.netgraph import NetGraph
from checkers.optocoupler import build_inventory
from test_inductive_load import add


def fixture():
    db = {'parts': {}, 'nets': {}, 'pin2net': {}, 'pinname': {}, 'pintype': {}}
    add(db, 'Q1', 'MOSFET', [('1', '', 'GATE'), ('2', '', 'DRAIN'), ('3', '', 'GND')])
    add(db, 'U3', 'EL817', [('1', '', 'LED'), ('2', '', 'RET'), ('3', '', 'FB'), ('4', '', 'GND')])
    devices = {}
    for ref, names in [('Q1', ['G', 'D', 'S']), ('U3', ['A', 'K', 'E', 'C'])]:
        devices[ref] = {'mpn': db['parts'][ref]['part'], 'package': 'custom', 'pinout_complete': True,
                        'identity_citation': 'schematic p1', 'citation': 'manufacturer p1 pin diagram',
                        'pins': {str(i): {'name': n, 'role': 'other'} for i,n in enumerate(names, 1)}}
    return db, {'input_sha256': board_intent.input_fingerprint(db), 'devices': devices}


def test_physical_roles_and_sources_without_native_mutation():
    db, intent = fixture(); original = deepcopy(db)
    view = board_intent.graph_db(db, intent); graph = NetGraph(view)
    assert [graph.role('Q1.' + p) for p in ['1', '2', '3']] == ['gate', 'drain', 'source']
    assert graph.node_named('U3', 'out_collector') == 'U3.4'
    assert graph.node_named('U3', 'out_emitter') == 'U3.3'
    assert graph.pin_evidence['Q1.1']['citation'] == 'manufacturer p1 pin diagram'
    assert board_intent.input_fingerprint(view) == board_intent.input_fingerprint(db)
    assert db == original
    inv = build_inventory(view, intent)
    opto = inv['states'][0]['optocouplers'][0]
    assert opto['collector_net'] == 'GND' and opto['emitter_net'] == 'FB'
    assert inv['context']['devices'] == intent['devices']


def test_native_names_win_conflict_is_visible_and_uncited_table_is_unused():
    db, intent = fixture()
    db['pinname']['Q1.1'] = 'S'
    graph = NetGraph(board_intent.graph_db(db, intent))
    assert graph.role('Q1.1') == 'source'
    assert graph.pin_conflicts[0]['node'] == 'Q1.1'
    intent['devices']['Q1']['citation'] = ''
    assert NetGraph(board_intent.graph_db(db, intent)).role('Q1.2') is None
    intent['devices']['Q1']['citation'] = 'p1'
    intent['devices']['Q1']['pinout_complete'] = False
    assert NetGraph(board_intent.graph_db(db, intent)).role('Q1.2') is None


def test_exposed_pad_synonyms_are_not_pin_conflicts():
    db, intent = fixture()
    db['pinname']['U3.3'] = 'PAD'
    intent['devices']['U3']['pins']['3']['name'] = 'EP'
    assert not NetGraph(board_intent.graph_db(db, intent)).pin_conflicts

"""boards-merge5 still-missed probes: each site edits only its stated nodes against an unchanged paired baseline."""
import copy
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'evals/seeded_bench')]
import mutators


def board(*parts):
    db = {'parts': {}, 'nets': {}, 'pin2net': {}, 'pinname': {}, 'pintype': {}, 'pseudo_nets': []}
    for ref, model, value, pins in parts:
        db['parts'][ref] = {'part': model, 'value': value, 'nc': False}
        for pin, name, net in pins:
            db['pin2net'][ref + '.' + pin] = net
            db['pinname'][ref + '.' + pin] = name
    return mutators.rebuild(db)


def one(db):
    original = copy.deepcopy(db)
    found = list(mutators.merge5_mutations(db))
    assert db == original and len(found) == 1
    m = found[0]
    assert m.baseline == original and m.contract.get('source')
    assert mutators.rebuild(copy.deepcopy(m.db))['nets'] == m.db['nets']
    return m


def test_hbridge_reset_seed_drives_the_bridge_out_of_sleep():
    m = one(board(('U2', 'DRV8837', 'DRV8837', [('5', 'IN2', '/M_2'), ('6', 'IN1', '/M_1'), ('7', '~{SLEEP}', '/M_SLEEP'),
                                                 ('8', 'VCC', 'VCC'), ('4', 'GND', 'GND')])))
    assert (m.db['pin2net']['U2.7'], m.db['pin2net']['U2.6'], m.db['pin2net']['U2.5']) == ('VCC', 'VCC', 'GND')
    assert m.targets == ('RST-T04',)


def test_isolation_seeds_add_a_fitted_zero_ohm_across_the_barrier():
    m = one(board(('U1', 'ADM2582E', 'ADM2582E', [('1', 'GND1', 'GND'), ('11', 'GND2', '/GND3')])))
    assert {m.db['pin2net']['RSEED1.1'], m.db['pin2net']['RSEED1.2']} == {'GND', '/GND3'}
    assert m.db['parts']['RSEED1']['value'] == '0R' and not m.db['parts']['RSEED1']['nc']
    m = one(board(('U1', 'Trafo_1', '', [('4', None, 'GND'), ('7', None, '/E')])))
    assert set(m.db['nets']['GND']) >= {'RSEED1.1'} and 'RSEED1.2' in m.db['nets']['/E']


def test_adc_divider_seed_changes_only_the_bottom_leg():
    m = one(board(('R18', 'R', '10K', [('1', None, 'GND'), ('2', None, 'ANALOG_0_10V')])))
    assert m.db['parts']['R18']['value'] == '100K' and m.db['pin2net'] == m.baseline['pin2net']


def test_reverse_pmos_seed_swaps_drain_and_source():
    m = one(board(('Q1', 'Q_PMOS_GDS', 'SUD50P06', [('1', 'G', 'Net-(D2-A)'), ('2', 'D', 'Net-(J1-Pin_1)'),
                                                     ('3', 'S', 'Net-(D2-K)')])))
    assert (m.db['pin2net']['Q1.2'], m.db['pin2net']['Q1.3']) == ('Net-(D2-K)', 'Net-(J1-Pin_1)')
    assert m.db['pin2net']['Q1.1'] == 'Net-(D2-A)'


def test_ldo_startup_seed_grows_the_output_capacitor():
    m = one(board(('U2', 'SE5218', 'SE5218', [('5', 'VOUT', '3V3'), ('2', 'GND', 'GND')]),
                  ('C6', '0603C', '2.2uF', [('1', None, 'GND'), ('2', None, '3V3')])))
    assert m.db['parts']['C6']['value'] == '1000uF' and m.baseline['parts']['C6']['value'] == '2.2uF'


def test_seeds_need_their_exact_sites():
    assert list(mutators.merge5_mutations(board(('U2', 'DRV8837', 'DRV8837', [('7', '~{SLEEP}', 'X')])))) == []
    assert list(mutators.merge5_mutations({'parts': {}, 'pin2net': {}, 'nets': {}})) == []

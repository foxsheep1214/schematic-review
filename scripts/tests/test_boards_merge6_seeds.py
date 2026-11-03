"""boards-merge6 seeds on the industrial I/O calibration board: each edits only its stated parts against the unmutated board."""
import copy
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'evals/seeded_bench')]
import mutators


def mcu_board():
    db = {'parts': {}, 'nets': {}, 'pin2net': {}, 'pinname': {}, 'pintype': {}, 'pseudo_nets': []}
    rows = [('U301', 'STM32F103C8T6', 'Device:MCU', [('44', 'BOOT0', '/04_MCU/BOOT0'), ('5', 'PD0/OSC_IN', '/04_MCU/OSC_IN'),
                                                    ('6', 'PD1/OSC_OUT', '/04_MCU/OSC_OUT'), ('8', 'VSS', 'GND')]),
            ('R301', 'R', 'Device:R', [('1', '', 'GND'), ('2', '', '/04_MCU/BOOT0')]),
            ('Y301', 'Crystal', 'Device:Crystal', [('1', '1', '/04_MCU/OSC_IN'), ('2', '2', '/04_MCU/OSC_OUT')]),
            ('C308', 'C', 'Device:C', [('1', '', '/04_MCU/OSC_IN'), ('2', '', 'GND')]),
            ('C309', 'C', 'Device:C', [('1', '', '/04_MCU/OSC_OUT'), ('2', '', 'GND')])]
    for ref, model, prim, pins in rows:
        db['parts'][ref] = {'part': model, 'value': {'C308': '20pF', 'C309': '20pF', 'R301': '10k'}.get(ref, model),
                            'prim': prim, 'nc': False}
        for pin, name, net in pins:
            db['pin2net'][ref + '.' + pin] = net
            if name:
                db['pinname'][ref + '.' + pin] = name
    return mutators.rebuild(db)


def test_calibration_board_seeds_keep_the_original_as_baseline():
    db = mcu_board()
    original = copy.deepcopy(db)
    found = {m.defect: m for m in mutators.merge6_mutations(db)}
    assert db == original and sorted(found) == ['D-BOOT0-FLOAT', 'D-XTAL-LOAD']
    xtal, boot = found['D-XTAL-LOAD'], found['D-BOOT0-FLOAT']
    assert xtal.baseline == original and boot.baseline == original
    assert {xtal.db['parts'][c]['value'] for c in ('C308', 'C309')} == {'1uF'} and xtal.contract['cl_pf'] == 12
    assert 'R301' not in boot.db['parts'] and boot.db['nets']['/04_MCU/BOOT0'] == ['U301.44']
    assert boot.targets == ('RST-E02', 'NET-A01')


def test_merge6_board_is_registered_with_an_internal_license():
    data = json.loads((ROOT / 'evals/seeded_bench/boards-merge6.json').read_text(encoding='utf-8'))
    assert [b['id'] for b in data['boards']] == ['calibration--industrial-io-rs485-can']
    assert data['boards'][0]['source']['license'] == 'internal'

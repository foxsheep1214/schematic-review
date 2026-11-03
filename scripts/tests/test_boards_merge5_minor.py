"""boards-merge5 item 4: minor recognition patterns from the 86-board attributions, one block per pattern."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import part_words as pw


def one_pin(ref, model, pin, name, value=None, net=None):
    net = net or 'unconnected-(%s-%s-Pad%s)' % (ref, name, pin)
    return {'parts': {ref: {'part': model, 'value': value or model}}, 'pinname': {ref + '.' + pin: name},
            'pin2net': {ref + '.' + pin: net}, 'nets': {net: [ref + '.' + pin]}}


# 4a: device-level allowed-open clauses (manufacturer pages read from the board cache datasheets)
def test_tps54202_en_and_tmc2209_vref_may_float():
    assert 'Float the EN pin' in pw.unused_input_permission(one_pin('U3', 'TPS54308', '5', 'EN', value='TPS54202'), 'U3.5')
    assert 'VVREFO' in pw.unused_input_permission(one_pin('U2', 'TMC2209-LA', '17', 'VREF'), 'U2.17')


def test_allowed_open_needs_the_exact_model_pin_and_an_open_net():
    assert pw.unused_input_permission(one_pin('U3', 'TPS54308', '5', 'EN'), 'U3.5') is None
    assert pw.unused_input_permission(one_pin('U3', 'TPS54202', '4', 'EN'), 'U3.4') is None
    assert pw.unused_input_permission(one_pin('U2', 'TMC2208', '17', 'VREF'), 'U2.17') is None
    db = one_pin('U2', 'TMC2209-LA', '17', 'VREF', net='VREF')
    db['nets']['VREF'].append('R1.1')
    assert pw.unused_input_permission(db, 'U2.17') is None

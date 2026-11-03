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


# 4b: a cell or cell holder is a source (CeraCharge C25, CR1220 holder K2 with pins 1+/2-)
def test_cells_and_holders_under_other_prefixes_are_batteries():
    assert pw.classify('C25', {'value': '100uAH-1V8-4.4x3mm_LIon_batt', 'prim': 'TFT_capacitors:100uAH-1V8-4.4x3mm_LIon_batt'}, 2)[0] == pw.BATTERY
    assert pw.classify('K2', {'value': 'CR1220_HOLDER', 'part': 'CR1220_HOLDER'}, 2, [(None, '1+'), (None, '2-')])[0] == pw.BATTERY


def test_cell_words_do_not_capture_connectors_ics_or_plain_capacitors():
    assert pw.classify('J1', {'value': 'BATT', 'prim': 'Connector:Conn_01x02'}, 2)[0] == pw.CONNECTOR
    assert pw.classify('J1', {'value': 'BATT'}, 2)[0] == pw.CONNECTOR          # a battery connector is not the cell
    assert pw.classify('U1', {'value': 'BQ24075 Li-Ion charger'}, 16)[0] == pw.IC
    assert pw.classify('C1', {'value': '100uF', 'prim': 'Device:C'}, 2)[0] == pw.CAPACITOR
    assert pw.classify('R35', {'value': '2k', 'part': 'CR0402-FX-2001GLF'}, 2)[0] == pw.RESISTOR   # Bourns CR chip resistor
    assert pw.classify('R5', {'value': '100k BATT sense'}, 2)[0] == pw.RESISTOR                    # a resistor named for its job
    assert pw.classify('X1', {'value': '2k', 'part': 'CR0603-FX-2001ELF'}, 2)[0] != pw.BATTERY       # case size, not a coin cell

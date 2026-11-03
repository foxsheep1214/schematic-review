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


# 4c: a converter BOOT pin with only a capacitor to its own SW pin is a bootstrap supply, not a strap
def _boot_db(far_ref='U3', extra=()):
    nets = {'BOOTN': ['U3.6', 'C20.2', *extra], 'SWN': ['C20.1', 'L4.1', '%s.2' % far_ref]}
    pin2net = {n: k for k, v in nets.items() for n in v}
    return {'nets': nets, 'pin2net': pin2net, 'pinname': {'U3.6': 'BOOT', '%s.2' % far_ref: 'SW'}}


def test_bootstrap_boot_pin_is_not_a_strap():
    from plan_circuits import bootstrap_cap_pin
    assert bootstrap_cap_pin(_boot_db(), 'U3.6')
    assert not bootstrap_cap_pin(_boot_db(far_ref='U9'), 'U3.6')          # cap goes to another device: may be a strap
    assert not bootstrap_cap_pin(_boot_db(extra=('R5.1',)), 'U3.6')       # a resistor on BOOT: a real strap


def test_plan_asks_no_strap_row_for_a_bootstrap_boot_pin():
    from plan_review import build_review_plan
    from test_checkers_framework import whole_board
    db = whole_board()
    db['parts'].update({'U7': {'value': 'TPS54202', 'part': 'TPS54202', 'nc': False},
                        'C70': {'value': '100n', 'part': '100n', 'nc': False}})
    for node, name, net in (('U7.1', 'BOOT', 'U7_BOOT'), ('C70.1', '1', 'U7_BOOT'), ('C70.2', '2', 'U7_SW'), ('U7.6', 'SW', 'U7_SW')):
        db['nets'].setdefault(net, []).append(node)
        db['pin2net'][node], db['pinname'][node] = net, name
    db['ref2page'] = {ref: 1 for ref in db['parts']}
    ids = [c['id'] for c in build_review_plan(db)['checks'] if c['rule'] == 'RST-E02']
    assert not [i for i in ids if 'U7' in i]


# 4d: PoE jack centre taps V1+/V1- are a polarity-agnostic power input, not a differential data pair
def test_poe_centre_taps_are_not_a_differential_pair():
    from checkers.diff_levels import _Scan
    nets = {'/VC1P': ['J2.7', 'U4.15'], '/VC1N': ['J2.8', 'U4.2'], '/ETH_TXP': ['J2.1', 'U1.3'], '/ETH_TXN': ['J2.2', 'U1.4']}
    db = {'parts': {'J2': {'value': 'RJ45'}, 'U4': {'value': 'LT4321'}, 'U1': {'value': 'LAN9500A'}}, 'nets': nets,
          'pin2net': {n: k for k, v in nets.items() for n in v},
          'pinname': {'J2.7': 'V1+', 'J2.8': 'V1-', 'J2.1': 'TD+', 'J2.2': 'TD-', 'U4.15': 'IN12', 'U4.2': 'IN36',
                      'U1.3': 'TXP', 'U1.4': 'TXN'}}
    scan = _Scan(db, {'fitted': list(db['parts'])}, {}, set())
    assert [p[1] for p in scan._pairs()] == ['/ETH_TXP']

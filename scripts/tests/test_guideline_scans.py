"""Cold scans of machine-decidable design criteria (user 2026-11-04: 提高 SR 对设计准则的自动扫描覆盖).

Each test pair is the structure a criterion names and the nearest structure that must stay silent."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lint import Lint
import catalog
import guideline_scans as gs
from test_boards_merge2b_roles import empty
from test_inductive_load import add


def board(*parts, fields=None, native=None, bom=None, nc=()):
    db = empty()
    for ref, value, pins in parts:
        add(db, ref, value, pins, nc=ref in nc)
    for ref, values in (fields or {}).items():
        db['parts'][ref]['fields'] = values
    if native:
        db['native_pintype'] = native
    if bom:
        db['bom'] = bom
    return db


def rows(db, rule, intent=None):
    return [f for f in Lint(db, None, intent).run() if f['rule'] == rule]


def two(ref, value, a, b):
    return (ref, value, [('1', '', a), ('2', '', b)])


def details(found):
    return ' | '.join(f['detail'] for f in found)


# --- DEV-A04, G02-038 --------------------------------------------------------------------------------------------
def test_library_default_values_are_placeholders_by_kind():
    db = board(two('R1', 'R_Small', 'A', 'GND'), two('C1', 'C', 'A', 'GND'), two('D1', 'D_Schottky', 'A', 'B'), two('Y1', 'Crystal', 'A', 'B'),
               ('J1', 'Conn_01x02', [('1', '', 'A'), ('2', '', 'GND')]))
    [row] = rows(db, 'DEV-A04')
    assert row['kind'] == 'CANDIDATE'
    assert all(ref in row['detail'] for ref in ('R1', 'C1', 'D1', 'Y1')) and 'J1' not in row['detail']


def test_a_real_value_or_an_ordering_code_is_no_placeholder():
    assert not rows(board(two('R1', '10k', 'A', 'GND'), two('C1', '100n/50V', 'A', 'GND')), 'DEV-A04')
    assert not rows(board(two('C1', 'C', 'A', 'GND'), fields={'C1': {'MPN': 'GRM155'}}), 'DEV-A04')
    bom = {'parts': {'C1': {'MPN': 'GRM155'}}, 'not_in_bom': [], 'not_in_netlist': []}
    assert not rows(board(two('C1', 'C', 'A', 'GND'), bom=bom), 'DEV-A04')


def test_unfitted_parts_are_not_placeholders():
    assert not rows(board(two('R1', 'R', 'A', 'GND'), nc=('R1',)), 'DEV-A04')


def test_wildcards_and_bare_series_on_active_parts():
    for value in ('BZT52Bxx', 'BQ769x2', 'LM2596S-?', 'TPS7A*'):
        found = rows(board(('U1', value, [('1', 'VIN', 'VCC_5V'), ('2', 'GND', 'GND')])), 'DEV-A04')
        assert len(found) == 1, value
        assert '通配' in found[0]['detail']
    assert '缺电压档' in details(rows(board(two('D1', 'SMBJ', 'VCC_5V', 'GND')), 'DEV-A04'))


def test_an_x_inside_a_real_part_number_is_no_wildcard():
    for value in ('ESD9X12ST5G', 'STM32F103C8T6', 'MAX3485'):
        assert not rows(board(('U1', value, [('1', 'VIN', 'VCC_5V'), ('2', 'GND', 'GND')])), 'DEV-A04'), value


def test_undecided_words_on_any_part():
    for value in ('TBD', '10k TBR', '待定'):
        assert '未定词' in details(rows(board(two('R1', value, 'A', 'GND')), 'DEV-A04')), value
    assert not rows(board(two('R1', 'TBDX1', 'A', 'GND')), 'DEV-A04')


# --- DEV-A05, G02-036 --------------------------------------------------------------------------------------------
def test_a_resistor_written_as_capacitance_and_the_reverse():
    assert '容值' in details(rows(board(two('R1', '100nF', 'A', 'GND')), 'DEV-A05'))
    assert '阻值' in details(rows(board(two('C1', '10k', 'A', 'GND')), 'DEV-A05'))
    assert '阻值' in details(rows(board(two('C1', '2K', 'A', 'GND')), 'DEV-A05'))


def test_capacitor_codes_and_low_ohm_shunts_are_not_field_conflicts():
    assert not rows(board(two('C1', '225K', 'A', 'GND')), 'DEV-A05')
    assert not rows(board(two('C1', '225k/2.2uF', 'A', 'GND')), 'DEV-A05')
    assert not rows(board(two('R1', '1m 3W', 'A', 'GND')), 'DEV-A05')
    assert not rows(board(two('R1', '300µ', 'A', 'GND')), 'DEV-A05')
    assert not rows(board(two('R1', '10k', 'A', 'GND'), two('C1', '100n', 'A', 'GND')), 'DEV-A05')


def test_one_ordering_code_on_different_values():
    db = board(two('R1', '10k', 'A', 'GND'), two('R2', '10k', 'B', 'GND'), two('R3', '12k', 'D', 'GND'),
               fields={r: {'MPN': 'RR0816P-103-D'} for r in ('R1', 'R2', 'R3')})
    [row] = rows(db, 'DEV-A05')
    assert 'R3=12k' in row['detail'] and 'R1=' not in row['detail'] and row['ref'] == 'R3'
    same = board(two('R1', '10k', 'A', 'GND'), two('R2', '10K', 'B', 'GND'), fields={r: {'MPN': 'X'} for r in ('R1', 'R2')})
    assert not rows(same, 'DEV-A05')


def test_value_and_maker_code_of_different_models():
    def one(value, code, field='MPN'):
        return rows(board(('U1', value, [('1', 'VCC', 'VCC_5V'), ('2', 'GND', 'GND')]), fields={'U1': {field: code}}), 'DEV-A05')
    assert len(one('LM358', 'TL072CDR')) == 1
    for value, code in (('LM358', 'LM358DR'), ('74HC00', 'SN74HC00PWR'), ('LM62440-Q1', 'LMQ62440BPPQRJRRQ1'), ('6.8V', 'BZV55B6V8'),
                        ('LM1117-3.3', 'LM1117IMP-3.3')):
        assert not one(value, code), (value, code)
    assert not one('STM32F103C8T6', 'C8734', 'LCSC')   # a stock number names no model


# --- DOC-A05, G02-037 --------------------------------------------------------------------------------------------
def bom_board(not_in_bom=(), not_in_netlist=(), parts=None, fields=None):
    return board(two('R1', '10k', 'A', 'GND'), two('JP1', 'SolderJumper', 'A', 'GND'), two('TP1', 'TestPoint', 'A', 'GND'), fields=fields,
                 bom={'parts': parts or {'R1': {'Qty': '1'}}, 'not_in_bom': list(not_in_bom), 'not_in_netlist': list(not_in_netlist)})


def test_bom_set_differences():
    assert 'R1' in details(rows(bom_board(not_in_bom=['R1']), 'DOC-A05'))
    assert 'R9' in details(rows(bom_board(not_in_netlist=['R9']), 'DOC-A05'))


def test_bom_differences_that_say_nothing():
    assert not rows(bom_board(not_in_bom=['JP1', 'TP1']), 'DOC-A05')
    assert not rows(bom_board(not_in_netlist=['REF**', 'G***']), 'DOC-A05')
    assert not rows(board(two('R1', '10k', 'A', 'GND')), 'DOC-A05')    # no BOM read


def test_ordering_codes_compare_only_in_the_same_column():
    differ = bom_board(parts={'R1': {'MPN': 'RC0402'}}, fields={'R1': {'MPN': 'ERJ2'}})
    assert 'R1（图上 ERJ2，BOM RC0402）' in details(rows(differ, 'DOC-A05'))
    assert not rows(bom_board(parts={'R1': {'LCSC': 'C1'}}, fields={'R1': {'MPN': 'ERJ2'}}), 'DOC-A05')
    assert not rows(bom_board(parts={'R1': {'MPN': 'ERJ-2'}}, fields={'R1': {'MPN': 'ERJ 2'}}), 'DOC-A05')


# --- PWR-A09..A11, G03 -------------------------------------------------------------------------------------------
def ldo(vin, vout, value='AMS1117-3.3'):
    return board(('U1', value, [('1', 'VIN', vin), ('2', 'VOUT', vout), ('3', 'GND', 'GND')]), two('C1', '1u', vout, 'GND'))


def test_ldo_input_not_above_output():
    assert rows(ldo('VCC_3V3', 'VCC_3V3_A'), 'PWR-A09')
    assert rows(ldo('VCC_3V3', 'VCC_5V'), 'PWR-A09')
    assert not rows(ldo('VCC_5V', 'VCC_3V3'), 'PWR-A09')
    assert not rows(ldo('VIN_RAW', 'VCC_3V3'), 'PWR-A09')              # an unread voltage says nothing
    assert not rows(ldo('VCC_3V3', 'VCC_5V', 'TPS62160'), 'PWR-A09')   # no linear identity


def test_ldo_scan_reads_declared_voltages_first():
    intent = {'power_rails': {'VIN_RAW': {'voltage_v': {'max': 3.3}}}}
    assert rows(ldo('VIN_RAW', 'VCC_5V'), 'PWR-A09', intent)


def series_caps(*extra, top='VCC_48V', mid='MID', bottom='GND'):
    return board(('C1', 'C_Polarized 100u', [('1', '+', top), ('2', '-', mid)]), ('C2', 'C_Polarized 100u', [('1', '+', mid), ('2', '-', bottom)]), *extra)


def test_series_electrolytics_without_balancing():
    [row] = rows(series_caps(), 'PWR-A10')
    assert 'C1' in row['detail'] and 'C2' in row['detail'] and row['kind'] == 'CANDIDATE'
    assert rows(series_caps(two('R1', '100k', 'MID', 'GND')), 'PWR-A10')     # one resistor balances nothing


def test_balanced_or_used_midpoints_are_not_reported():
    assert not rows(series_caps(two('R1', '100k', 'VCC_48V', 'MID'), two('R2', '100k', 'MID', 'GND')), 'PWR-A10')
    assert not rows(series_caps(('U1', 'OPA', [('1', 'IN', 'MID')])), 'PWR-A10')
    plain = board(two('C1', '100n', 'VCC_48V', 'MID'), two('C2', '100n', 'MID', 'GND'))
    assert not rows(plain, 'PWR-A10')
    assert not rows(series_caps(bottom='VCC_48V'), 'PWR-A10')                # one rail twice: no series string across a voltage


def decoupled(value, fields=None):
    return board(two('C1', value, 'VCC_3V3', 'GND'), ('U1', 'MCU', [('1', 'VDD', 'VCC_3V3'), ('2', 'GND', 'GND')]), fields=fields)


def test_soft_dielectric_on_an_ic_supply():
    assert rows(decoupled('100n/Y5V'), 'PWR-A11')
    assert rows(decoupled('100n', {'C1': {'Specification': '100 nF Z5U'}}), 'PWR-A11')
    bom = board(two('C1', '100n', 'VCC_3V3', 'GND'), ('U1', 'MCU', [('1', 'VDD', 'VCC_3V3'), ('2', 'GND', 'GND')]),
                bom={'parts': {'C1': {'SelectedSpec': 'Y5U'}}, 'not_in_bom': [], 'not_in_netlist': []})
    assert rows(bom, 'PWR-A11')


def test_soft_dielectric_elsewhere_is_silent():
    assert not rows(decoupled('100n/X7R'), 'PWR-A11')
    assert not rows(decoupled('100n/XY5V'), 'PWR-A11')
    assert not rows(board(two('C1', '1n/Y5U', 'VCC_3V3', 'CHASSIS'), ('U1', 'MCU', [('1', 'VDD', 'VCC_3V3')])), 'PWR-A11')
    assert not rows(board(two('C1', '1n/Y5U', 'VIN', 'GND')), 'PWR-A11')    # no IC supply pin on it


def test_dev_a02_reads_two_positive_rails():
    def cap(plus, minus):
        return board(('C1', 'C_Polarized 10u', [('1', '+', plus), ('2', '-', minus)]))
    assert '3.3 V' in details(rows(cap('VCC_3V3', 'VCC_5V'), 'DEV-A02'))
    assert not rows(cap('VCC_5V', 'VCC_3V3'), 'DEV-A02')
    assert not rows(cap('VCC_5V', 'VEE_12V'), 'DEV-A02')                     # a negative rail keeps + on the upper net
    assert not rows(cap('VEE_3V3', 'VCC_5V'), 'DEV-A02')


# --- PRO-A07..A13, G05 -------------------------------------------------------------------------------------------
def test_tvs_standoff_against_the_net():
    assert '15 V' in details(rows(board(two('D1', 'SMBJ15A', '24V_BUS', 'GND')), 'PRO-A07'))
    assert rows(board(two('D1', 'PESD5V0L1BA', 'VCC_12V', 'GND')), 'PRO-A07')
    assert not rows(board(two('D1', 'SMBJ24A', '24V_BUS', 'GND')), 'PRO-A07')
    assert not rows(board(two('D1', 'SMBJ15A', 'VIN_RAW', 'GND')), 'PRO-A07')
    assert not rows(board(two('D1', 'TVS_ABC', '24V_BUS', 'GND')), 'PRO-A07')


def test_tvs_standoff_uses_the_declared_window():
    intent = {'power_rails': {'VIN_RAW': {'voltage_v': {'max': 28.0}}}}
    assert rows(board(two('D1', 'SMBJ24A', 'VIN_RAW', 'GND')), 'PRO-A07', intent)
    assert 'SMBJ88392' not in details(rows(board(two('D1', 'SMBJ15A', '24V_BUS', 'GND')), 'PRO-A07'))


def test_fuse_rating_against_the_rail():
    assert rows(board(two('F1', 'Fuse 1A/32V', 'VCC_48V', 'VOUT')), 'PRO-A08')
    assert rows(board(two('F1', 'PPTC 0.5A/6V', 'VOUT', 'VCC_12V')), 'PRO-A08')
    assert not rows(board(two('F1', 'Fuse 1A/63V', 'VCC_48V', 'VOUT')), 'PRO-A08')
    assert not rows(board(two('F1', 'Fuse 1A', 'VCC_48V', 'VOUT')), 'PRO-A08')
    assert not rows(board(two('R1', '1R/32V', 'VCC_48V', 'VOUT')), 'PRO-A08')
    assert rows(board(two('F1', '4A/T/32VDC', 'VCC_48V', 'VOUT')), 'PRO-A08')
    assert not rows(board(two('F1', '4A/T/125VDC', 'VCC_48V', 'VOUT')), 'PRO-A08')
    assert not rows(board(two('F1', '4A/T/32VAC', 'VCC_48V', 'VOUT')), 'PRO-A08')    # an AC rating says nothing about DC


def clamp_on(tvs, ic, name='IN'):
    return board(two('D1', tvs, 'VAUX', 'GND'), ('U1', ic, [('6', name, 'VAUX'), ('2', 'GND', 'GND')]))


def test_tabled_clamp_above_a_tabled_pin_on_its_net():
    [row] = rows(clamp_on('SMBJ15A', 'TPS25981A'), 'PRO-A09')
    assert '24.4 V' in row['detail'] and 'U1.6' in row['detail'] and '20 V' in row['detail']
    assert not rows(clamp_on('SMBJ15A', 'TPS26630RGER'), 'PRO-A09')    # 67 V pin
    assert not rows(clamp_on('SMBJ15A', 'LM1234'), 'PRO-A09')          # untabled pin
    assert not rows(clamp_on('SMBJ9A', 'TPS25981A'), 'PRO-A09')        # untabled clamp
    assert not rows(clamp_on('SMBJ15A', 'TPS25981A', 'EN'), 'PRO-A09')


def entry(tvs, connector='CONN_2P', *extra):
    return board(('J1', connector, [('1', '', 'VIN'), ('2', '', 'GND')]), two('D1', tvs, 'VIN', 'GND'), *extra)


def diode_block():
    return ('D2', 'SS34', [('1', 'A', 'VIN'), ('2', 'K', 'VOUT')])


def pfet_block():
    return ('Q1', 'Q_PMOS_GSD', [('1', 'G', 'GATE'), ('2', 'S', 'VOUT'), ('3', 'D', 'VIN')])


def test_unidirectional_tvs_ahead_of_a_reverse_block():
    for block in (diode_block(), pfet_block(), ('U1', 'LTC4359', [('1', 'IN', 'VIN'), ('2', 'OUT', 'VOUT')])):
        assert rows(entry('SMBJ24A', 'CONN_2P', block), 'PRO-A10'), block[0]
    behind_fuse = board(('J1', 'CONN_2P', [('1', '', 'VIN'), ('2', '', 'GND')]), two('F1', 'Fuse 1A', 'VIN', 'VF'), two('D1', 'SMBJ24A', 'VF', 'GND'),
                        ('D2', 'SS34', [('1', 'A', 'VF'), ('2', 'K', 'VOUT')]))
    assert rows(behind_fuse, 'PRO-A10')


def test_bidirectional_tvs_keyed_ports_and_no_block_are_silent():
    assert not rows(entry('SMBJ24CA', 'CONN_2P', diode_block()), 'PRO-A10')
    assert not rows(entry('SMBJ24A', 'CONN_2P'), 'PRO-A10')
    assert not rows(entry('SMBJ24A', 'USB_C_Receptacle', diode_block()), 'PRO-A10')
    assert not rows(board(two('D1', 'SMBJ24A', 'VIN', 'GND'), diode_block()), 'PRO-A10')    # no connector
    behind = entry('SMBJ24A', 'CONN_2P', ('U1', 'LM74700', [('6', 'ANODE', 'VSRC'), ('4', 'CATHODE', 'VIN')]))
    assert not rows(behind, 'PRO-A10')    # resonare-lcc: the clamp at the controller's cathode is behind the block
    assert rows(entry('SMBJ24A', 'CONN_2P', ('U1', 'LM74700', [('6', 'ANODE', 'VIN'), ('4', 'CATHODE', 'VOUT')])), 'PRO-A10')
    shunt = entry('SMBJ24A', 'CONN_2P', ('D2', 'SS34', [('1', 'A', 'VIN'), ('2', 'K', 'GND')]))
    assert not rows(shunt, 'PRO-A10')    # a diode to ground blocks nothing


def fet(value, gate, drain, source, *extra):
    return board(('J1', 'CONN_2P', [('1', '', 'VIN'), ('2', '', 'RTN')]), ('Q1', value, [('1', 'G', gate), ('2', 'D', drain), ('3', 'S', source)]), *extra)


def test_reverse_fet_with_its_body_diode_the_wrong_way():
    [row] = rows(fet('Q_PMOS_GDS', 'G1', 'VLOAD', 'VIN', two('R1', '10k', 'G1', 'GND'), two('D1', 'BZX84C12', 'G1', 'VIN')), 'PRO-A11')
    assert 'J1' in row['detail'] and row['kind'] == 'CANDIDATE'
    assert rows(fet('Q_PMOS_GDS', 'GND', 'VLOAD', 'VIN'), 'PRO-A11')
    assert rows(fet('Q_NMOS_GDS', 'G1', 'GND', 'RTN', two('R1', '10k', 'G1', 'VCC_12V')), 'PRO-A11')


def test_a_correct_or_driven_fet_is_silent():
    assert not rows(fet('Q_PMOS_GDS', 'G1', 'VIN', 'VLOAD', two('R1', '10k', 'G1', 'GND')), 'PRO-A11')        # drain at the input
    assert not rows(fet('Q_NMOS_GDS', 'G1', 'RTN', 'GND', two('R1', '10k', 'G1', 'VCC_12V')), 'PRO-A11')
    driven = fet('Q_PMOS_GDS', 'G1', 'VLOAD', 'VIN', two('R1', '10k', 'G1', 'GND'), ('U1', 'MCU', [('1', 'PA0', 'G1')]))
    assert not rows(driven, 'PRO-A11')                                                                        # a load switch
    assert not rows(fet('Si2301', 'GND', 'VLOAD', 'VIN'), 'PRO-A11')                                          # channel not written
    assert not rows(fet('Q_PMOS_NMOS_pair', 'GND', 'VLOAD', 'VIN'), 'PRO-A11')                                # both channels named: unread
    assert not rows(board(('Q1', 'Q_PMOS_GDS', [('1', 'G', 'GND'), ('2', 'D', 'VLOAD'), ('3', 'S', 'VIN')])), 'PRO-A11')  # no connector


def latch(clear, clock='GND'):
    return board(
        ('U1', 'TPS26630', [('1', 'IN', 'VCC_24V'), ('2', 'OUT', 'VOUT'), ('3', 'PG', 'PG1'), ('4', 'GND', 'GND')]),
        ('U2', 'SN74HCS00', [('1', '1A', 'PG1'), ('2', '1B', 'VCC_3V3'), ('3', '1Y', 'SET_N'), ('14', 'VCC', 'VCC_3V3'), ('7', 'GND', 'GND')]),
        ('U3', 'SN74HCS74', [('1', '~{1CLR}', clear), ('2', '1D', 'GND'), ('3', '1CLK', clock), ('4', '~{1PRE}', 'SET_N'), ('5', '1Q', 'LOCK'),
                             ('14', 'VCC', 'VCC_3V3'), ('7', 'GND', 'GND')]))


def test_a_status_latch_with_nothing_to_clear_it():
    [row] = rows(latch('VCC_3V3'), 'PRO-A12')
    assert 'U1' in row['detail'] and row['ref'] == 'U3'


def test_a_driven_clear_or_clock_is_a_reset_path():
    driven = latch('CLR_N')
    add(driven, 'U4', 'MCU', [('1', 'PA0', 'CLR_N')])
    driven['pintype']['U4.1'] = 'OUT'
    assert not rows(driven, 'PRO-A12')
    clocked = latch('VCC_3V3', 'CLK')
    add(clocked, 'U4', 'MCU', [('1', 'PA0', 'CLK')])
    clocked['pintype']['U4.1'] = 'OUT'
    assert not rows(clocked, 'PRO-A12')


def indicator(pull, receiver_supply='VCC_3V3'):
    return board(('U1', 'TPS26630', [('1', 'IN', 'VCC_24V'), ('2', 'OUT', 'VOUT'), ('3', 'FLT', 'FLT_N'), ('4', 'GND', 'GND')]),
                 two('R1', '10k', 'FLT_N', pull), ('U2', 'MCU', [('1', 'PA0', 'FLT_N'), ('2', 'VDD', receiver_supply)]))


def test_indicator_pulled_up_from_what_it_cuts():
    [row] = rows(indicator('VOUT'), 'PRO-A13')
    assert 'U1.3' in row['detail'] and 'U2.1' in row['detail']


def test_indicator_pull_up_elsewhere_or_a_receiver_that_falls_with_it():
    assert not rows(indicator('VCC_3V3'), 'PRO-A13')
    assert not rows(indicator('VOUT', 'VOUT'), 'PRO-A13')   # R2 U401→U402: PG sequences a regulator fed by the same output
    nobody = board(('U1', 'TPS26630', [('1', 'IN', 'VCC_24V'), ('2', 'OUT', 'VOUT'), ('3', 'FLT', 'FLT_N')]), two('R1', '10k', 'FLT_N', 'VOUT'))
    assert not rows(nobody, 'PRO-A13')
    other = board(('U1', 'MCU', [('2', 'OUT', 'VOUT'), ('3', 'FLT', 'FLT_N')]), two('R1', '10k', 'FLT_N', 'VOUT'), ('U2', 'MCU', [('1', 'PA0', 'FLT_N')]))
    assert not rows(other, 'PRO-A13')                       # no protection identity


# --- SIG-A07..A14, ANA, G04 --------------------------------------------------------------------------------------
def shifter(net, value='TXB0104', *extra):
    return board(('U1', value, [('1', 'A1', net), ('2', 'B1', 'OTHER'), ('3', 'VCCA', 'VCC_3V3')]), ('U2', 'MCU', [('1', 'PA0', net)]), *extra)


def test_txb_on_an_open_drain_bus():
    assert 'G04-012' in details(rows(shifter('I2C_SDA'), 'SIG-A07'))
    assert 'G04-012' in details(rows(shifter('ONEWIRE_DQ'), 'SIG-A07'))
    assert not rows(shifter('SPI_MOSI'), 'SIG-A07')
    assert not rows(shifter('I2C_SDA', 'TXS0102'), 'SIG-A07')
    spi_screen = board(('U1', 'TXB0104', [('1', 'A1', 'LCD_SDA')]), ('U2', 'LCD', [('1', 'MOSI', 'LCD_SDA')]))
    assert not rows(spi_screen, 'SIG-A07')


def test_txb_pull_below_its_limit():
    assert 'G04-013' in details(rows(shifter('DATA', 'TXB0104', two('R1', '10k', 'DATA', 'VCC_3V3')), 'SIG-A07'))
    assert not rows(shifter('DATA', 'TXB0104', two('R1', '100k', 'DATA', 'VCC_3V3')), 'SIG-A07')
    assert not rows(shifter('DATA', 'TXB0104', two('R1', '10k', 'DATA', 'SIGNAL')), 'SIG-A07')   # series, not a pull


def type_c(cc1='CC1', cc2='CC2', *extra):
    return board(('J1', 'USB_C_Receptacle', [('A5', 'CC1', cc1), ('B5', 'CC2', cc2), ('A4', 'VBUS', 'VBUS'), ('A1', 'GND', 'GND')]), *extra)


def test_type_c_cc_shared_floating_or_wrong_value():
    [row] = rows(type_c('CC', 'CC', two('R1', '5.1k', 'CC', 'GND')), 'SIG-A08')
    assert row['kind'] == 'FINDING' and '共用' in row['detail']
    found = rows(type_c('CC1', 'CC2', two('R1', '5.1k', 'CC1', 'GND')), 'SIG-A08')
    assert ['CC2' in f['detail'] for f in found] == [True]
    assert '1k' in details(rows(type_c('CC1', 'CC2', two('R1', '1k', 'CC1', 'GND'), two('R2', '5.1k', 'CC2', 'GND')), 'SIG-A08'))


def test_type_c_cc_correct_or_owned_by_a_controller():
    good = (two('R1', '5.1k', 'CC1', 'GND'), two('R2', '4.7k', 'CC2', 'GND'))
    assert not rows(type_c('CC1', 'CC2', *good), 'SIG-A08')
    assert not rows(type_c('CC1', 'CC2', two('R1', '56k', 'CC1', 'VBUS'), two('R2', '56k', 'CC2', 'VBUS')), 'SIG-A08')     # Rp, a source
    controller = ('U1', 'FUSB302', [('1', 'CC1', 'CC1'), ('2', 'CC2', 'CC2')])
    assert not rows(type_c('CC1', 'CC2', controller), 'SIG-A08')
    module = ('M1', 'CM5_Module', [('1', 'CC1', 'CC1'), ('2', 'CC2', 'CC2')])
    assert not rows(type_c('CC1', 'CC2', module), 'SIG-A08')
    micro = board(('J1', 'USB_B_Micro', [('1', 'VBUS', 'VBUS'), ('5', 'GND', 'GND')]))
    assert not rows(micro, 'SIG-A08')


def rs485(de, *extra, re_net='RE_N'):
    return board(('U1', 'MAX3485', [('1', 'RO', 'RX'), ('2', '~{RE}', re_net), ('3', 'DE', de), ('4', 'DI', 'TX'), ('6', 'A', 'BUS_A'), ('7', 'B', 'BUS_B'),
                                    ('8', 'VCC', 'VCC_3V3'), ('5', 'GND', 'GND')]), *extra)


def test_rs485_de_floating_fixed_or_pulled_active():
    assert '悬空' in details(rows(rs485('DE_LONE'), 'SIG-A09'))
    assert 'G04-066' in details(rows(rs485('VCC_3V3'), 'SIG-A09'))
    assert '上拉' in details(rows(rs485('DE1', two('R1', '10k', 'DE1', 'VCC_3V3'), ('U2', 'MCU', [('1', 'PA0', 'DE1')])), 'SIG-A09'))
    assert '没有驱动' in details(rows(rs485('DE1', two('R1', '10k', 'DE1', 'NOTHING')), 'SIG-A09'))


def test_rs485_de_from_a_connector_or_module_or_behind_a_resistor_pack():
    assert rows(rs485('DE1', ('J1', 'CONN', [('1', '', 'DE1')])), 'SIG-A09')[0]['needs_human']
    assert rows(rs485('DE1', two('R1', '0R', 'DE1', 'DIR'), ('M1', 'CM5_Module', [('1', 'GPIO1', 'DIR')])), 'SIG-A09')[0]['needs_human']
    assert not rows(rs485('DE1', ('RP1', 'R_PACK4', [('1', 'P1', 'DE1'), ('2', 'P2', 'X'), ('3', 'R1', 'Y'), ('4', 'R2', 'Z')])), 'SIG-A09')


def test_rs485_signature_reads_short_data_pin_names():
    db = board(('U1', 'ISOW3080P', [('1', 'R', 'RX'), ('2', '~{RE}', 'DE1'), ('3', 'DE', 'VDD_3V3'), ('4', 'D', 'TX'), ('6', 'A', 'BUS_A'), ('7', 'B', 'BUS_B')]))
    assert rows(db, 'SIG-A09')


def test_rs485_de_with_a_pull_down_or_only_a_driver():
    held = rs485('DE1', two('R1', '10k', 'DE1', 'GND'), ('U2', 'MCU', [('1', 'PA0', 'DE1')]))
    assert not rows(held, 'SIG-A09')
    [row] = rows(rs485('DE1', ('U2', 'MCU', [('1', 'PA0', 'DE1')])), 'SIG-A09')
    assert row['needs_human'] and row['kind'] == 'CANDIDATE'
    behind_r = rs485('DE1', two('R1', '100', 'DE1', 'DIR'), ('U2', 'MCU', [('1', 'PA0', 'DIR')]))
    assert rows(behind_r, 'SIG-A09')[0]['needs_human']       # a GPIO behind a series resistor is a driver
    tied_only = rs485('DE1', re_net='DE1')
    assert '没有驱动' in details(rows(tied_only, 'SIG-A09'))  # its own /RE on the net drives nothing
    assert not rows(board(('U1', 'TCAN1042', [('1', 'CANH', 'H'), ('2', 'CANL', 'L')])), 'SIG-A09')


def sensors(a1, a2, value='TMP102', *extra):
    return board(('U1', value, [('1', 'SDA', 'I2C_SDA'), ('2', 'SCL', 'I2C_SCL'), ('3', 'ADD0', a1), ('4', 'ALERT', 'A1')]),
                 ('U2', value, [('1', 'SDA', 'I2C_SDA'), ('2', 'SCL', 'I2C_SCL'), ('3', 'ADD0', a2), ('4', 'ALERT', 'A2')]),
                 two('R1', '4.7k', 'I2C_SDA', 'VCC_3V3'), two('R2', '4.7k', 'I2C_SCL', 'VCC_3V3'), *extra)


def test_same_model_same_straps_on_one_segment():
    [row] = rows(sensors('GND', 'GND'), 'SIG-A10')
    assert 'U1' in row['detail'] and 'U2' in row['detail']


def test_address_straps_differ_or_buses_differ():
    assert not rows(sensors('GND', 'VCC_3V3'), 'SIG-A10')
    assert not rows(sensors('GPIO1', 'GPIO2'), 'SIG-A10')    # a pin named like an address, on different nets
    other = board(('U1', 'TMP102', [('1', 'SDA', 'I2C_SDA'), ('2', 'SCL', 'I2C_SCL')]), ('U2', 'TMP102', [('1', 'SDA', 'I2C2_SDA'), ('2', 'SCL', 'I2C2_SCL')]))
    assert not rows(other, 'SIG-A10')
    mixed = board(('U1', 'TMP102', [('1', 'SDA', 'I2C_SDA'), ('2', 'SCL', 'I2C_SCL')]), ('U2', 'LM75B', [('1', 'SDA', 'I2C_SDA'), ('2', 'SCL', 'I2C_SCL')]))
    assert not rows(mixed, 'SIG-A10')
    rails = board(('U1', 'TMP102', [('1', 'SDA', 'I2C_SDA'), ('2', 'SCL', 'I2C_SCL'), ('3', 'VCC', 'V_A')]),
                  ('U2', 'TMP102', [('1', 'SDA', 'I2C_SDA'), ('2', 'SCL', 'I2C_SCL'), ('3', 'VCC', 'V_B')]),
                  two('R1', '1k', 'V_A', 'VCC_3V3'), two('R2', '1k', 'V_B', 'VCC_3V3'))
    assert not rows(rails, 'SIG-A10')    # static difference: separately fed parts are not called the same


def test_rs485_tvs_narrower_than_common_mode():
    found = rows(rs485('DE1', two('R1', '10k', 'DE1', 'GND'), two('D1', 'SMBJ5.0CA', 'BUS_A', 'GND')), 'SIG-A11')
    assert '5 V' in details(found)
    behind = rs485('DE1', two('R1', '10k', 'DE1', 'GND'), two('R9', '10R', 'BUS_A', 'PORT_A'), two('D1', 'PESD5V0L1BA', 'PORT_A', 'GND'))
    assert rows(behind, 'SIG-A11')
    assert not rows(rs485('DE1', two('R1', '10k', 'DE1', 'GND'), two('D1', 'SMBJ15CA', 'BUS_A', 'GND')), 'SIG-A11')
    assert not rows(rs485('DE1', two('R1', '10k', 'DE1', 'GND'), two('D1', 'SM712', 'BUS_A', 'GND')), 'SIG-A11')
    assert not rows(rs485('DE1', two('R1', '10k', 'DE1', 'GND'), two('D1', 'SMBJ5.0CA', 'VCC_5V', 'GND')), 'SIG-A11')


def split(r1, r2, *extra, cap='4n7'):
    return board(('U1', 'TCAN1042', [('6', 'CANL', 'L'), ('7', 'CANH', 'H')]), two('R1', r1, 'H', 'MID'), two('R2', r2, 'L', 'MID'), two('C1', cap, 'MID', 'GND'), *extra)


def test_split_termination_mismatch():
    assert '不相等' in details(rows(split('60R', '120R'), 'SIG-A12'))
    assert '5%' in details(rows(split('60R 5%', '60R 5%'), 'SIG-A12'))
    assert 'G04-076' in details(rows(split('60R', '120R'), 'SIG-A12'))
    rs = rs485('DE1', two('R3', '10k', 'DE1', 'GND'), two('R1', '60R', 'BUS_A', 'MID'), two('R2', '62R', 'BUS_B', 'MID'), two('C1', '4n7', 'MID', 'GND'))
    assert 'G04-064' in details(rows(rs, 'SIG-A12'))


def test_split_termination_that_matches_or_is_no_split():
    assert not rows(split('60R 1%', '60R 1%'), 'SIG-A12')
    plain = board(('U1', 'TCAN1042', [('6', 'CANL', 'L'), ('7', 'CANH', 'H')]), two('R1', '60R', 'H', 'MID'), two('R2', '120R', 'L', 'MID'))
    assert not rows(plain, 'SIG-A12')    # no capacitor to ground


def amp(plus, minus, out, *extra, value='OPA2277', supply='VCC_5V'):
    return board((('U1', value, [('1', 'OUT', out), ('2', 'IN-', minus), ('3', 'IN+', plus), ('8', 'V+', supply), ('4', 'V-', 'GND')])), *extra)


def test_amplifier_input_behind_only_a_capacitor():
    [row] = rows(amp('NP', 'OUTN', 'OUTN', two('C1', '100n', 'NP', 'SIG')), 'ANA-A01')
    assert 'U1.3' in row['detail'] and row['kind'] == 'FINDING'
    series = amp('NP', 'OUTN', 'OUTN', two('R1', '1k', 'NP', 'NQ'), two('C1', '100n', 'NQ', 'SIG'))
    assert rows(series, 'ANA-A01')


def test_amplifier_input_with_a_dc_path():
    assert not rows(amp('NP', 'OUTN', 'OUTN', two('C1', '100n', 'NP', 'SIG'), two('R1', '100k', 'NP', 'GND')), 'ANA-A01')
    assert not rows(amp('NP', 'OUTN', 'OUTN', two('C1', '100n', 'NP', 'SIG'), two('R1', '100k', 'NP', 'VCC_3V3')), 'ANA-A01')
    assert not rows(amp('NP', 'OUTN', 'OUTN', two('C1', '100n', 'NP', 'SIG'), two('R1', '1k', 'NP', 'NQ'), ('J1', 'CONN', [('1', '', 'NQ')])), 'ANA-A01')
    assert not rows(amp('NP', 'OUTN', 'OUTN', two('R1', '1k', 'NP', 'SIG')), 'ANA-A01')    # no capacitor at all: NET-A rules own the open pin
    other = board(('U1', 'SN74HC14', [('3', 'IN+', 'NP')]), two('C1', '100n', 'NP', 'SIG'))
    assert not rows(other, 'ANA-A01')


def test_the_second_input_of_a_kicad_dual_is_read():
    db = board(('U1', 'TL082', [('1', '', 'OA'), ('2', '-', 'OA'), ('3', '+', 'REF_2V5'), ('5', '+', 'NP'), ('6', '-', 'OB'), ('7', '', 'OB'), ('8', 'V+', 'VCC_5V'), ('4', 'V-', 'GND')]),
               two('C1', '100n', 'NP', 'SIG'))
    assert 'U1.5' in details(rows(db, 'ANA-A01'))


def test_the_open_loop_second_unit_of_a_kicad_dual_is_read():
    db = board(('U1', 'TL082', [('1', '', 'OA'), ('2', '-', 'OA'), ('3', '+', 'REF_2V5'), ('5', '+', 'SIG'), ('6', '-', 'REF'), ('7', '', 'OB'),
                                ('8', 'V+', 'VCC_5V'), ('4', 'V-', 'GND')]),
               two('R1', '10k', 'OB', 'LOAD'), native={'U1.1': 'output', 'U1.7': 'output'})
    assert 'U1.7' in details(rows(db, 'ANA-A02'))


def test_amplifier_with_no_feedback():
    [row] = rows(amp('SIG', 'REF', 'OUT1', two('R1', '10k', 'OUT1', 'LOAD')), 'ANA-A02')
    assert 'U1.1' in row['detail'] and row['kind'] == 'CANDIDATE'


def test_amplifier_feedback_composite_or_unused():
    assert not rows(amp('SIG', 'OUT1', 'OUT1'), 'ANA-A02')
    assert not rows(amp('SIG', 'FB', 'OUT1', two('R1', '10k', 'OUT1', 'FB')), 'ANA-A02')
    assert not rows(amp('SIG', 'FB', 'OUT1', two('C1', '1n', 'OUT1', 'FB')), 'ANA-A02')
    assert not rows(amp('FB', 'SIG', 'OUT1', two('R1', '1M', 'OUT1', 'FB')), 'ANA-A02')    # hysteresis is feedback; the wider review owns it
    assert not rows(amp('SIG', 'FB', 'OUT1', ('Q1', 'BC547', [('1', 'B', 'OUT1'), ('2', 'E', 'FB'), ('3', 'C', 'VCC_5V')])), 'ANA-A02')
    assert not rows(amp('GND', 'VCC_5V', 'OUT1', two('R1', '10k', 'OUT1', 'LOAD')), 'ANA-A02')
    assert not rows(amp('SIG', 'REF', 'OUT1', two('R1', '10k', 'OUT1', 'LOAD'), value='LM393'), 'ANA-A02')
    assert not rows(amp('SIG', 'REF', 'OUT1', two('R1', '10k', 'OUT1', 'LOAD'), value='Amplifier_Current:OPA191'), 'ANA-A02')


def test_amplifier_lone_output_by_symbol_type():
    db = board(('U1', 'OPA172', [('1', '', 'OUT1'), ('3', '+', 'SIG'), ('4', '-', 'REF'), ('5', 'V+', 'VCC_5V'), ('2', 'V-', 'GND')]), two('R1', '10k', 'OUT1', 'LOAD'),
               native={'U1.1': 'output', 'U1.3': 'input', 'U1.4': 'input'})
    assert rows(db, 'ANA-A02')


def adc(*extra, amp_supply='VCC_5V', adc_supply='VCC_3V3'):
    return amp('SIG', 'OUT1', 'OUT1', ('U2', 'STM32', [('1', 'PA0/ADC1_IN0', 'AN0'), ('2', 'VDD', adc_supply), ('3', 'VSS', 'GND')]), two('R1', '100R', 'OUT1', 'AN0'),
               *extra, supply=amp_supply)


def test_amplifier_supply_above_the_adc():
    [row] = rows(adc(), 'ANA-A03')
    assert '5 V' in row['detail'] and '3.3 V' in row['detail'] and 'U2.1' in row['detail']


def test_adc_path_with_a_clamp_a_divider_or_a_lower_supply():
    assert not rows(adc(amp_supply='VCC_3V3'), 'ANA-A03')
    assert not rows(adc(two('R2', '10k', 'AN0', 'GND')), 'ANA-A03')
    assert not rows(adc(('D1', 'BAT54', [('1', 'A', 'AN0'), ('2', 'K', 'VCC_3V3')])), 'ANA-A03')
    other = amp('SIG', 'OUT1', 'OUT1', ('U2', 'STM32', [('1', 'PA0', 'AN0'), ('2', 'VDD', 'VCC_3V3')]), two('R1', '100R', 'OUT1', 'AN0'))
    assert not rows(other, 'ANA-A03')


def domains(driver_supply='VCC_5V', receiver_supply='VCC_3V3', *extra, driver='SN74HC04', out='output', received='input'):
    return board(('U1', driver, [('1', 'Y', 'SIG1'), ('2', 'VCC', driver_supply), ('3', 'GND', 'GND')]),
                 ('U2', 'SN74LVC1G', [('1', 'A', 'SIG1'), ('2', 'VCC', receiver_supply), ('3', 'GND', 'GND')]), *extra,
                 native={'U1.1': out, 'U2.1': received})


def test_cross_domain_output_into_a_lower_input():
    [row] = rows(domains(), 'SIG-A13')
    assert 'U1.1' in row['detail'] and 'U2.1' in row['detail'] and row['ref'] == 'U2'


def test_cross_domain_near_misses():
    assert not rows(domains('VCC_3V3'), 'SIG-A13')
    assert not rows(domains(out='open_collector'), 'SIG-A13')
    assert not rows(domains(received='bidirectional'), 'SIG-A13')
    assert not rows(domains('VCC_5V', 'VCC_3V3', two('R1', '10k', 'SIG1', 'VCC_3V3')), 'SIG-A13')
    assert not rows(domains(driver='TLV1704'), 'SIG-A13')
    assert not rows(domains(driver='TL082'), 'SIG-A13')
    assert not rows(domains('VCC_12V', 'VREF'), 'SIG-A13')    # an unread supply


def can_chip(value='TJA1050', io=None, supply='VCC_5V', rxd='RX1'):
    pins = [('1', 'TXD', 'TX1'), ('2', 'GND', 'GND'), ('3', 'VCC', supply), ('4', 'RXD', rxd), ('6', 'CANL', 'L'), ('7', 'CANH', 'H')]
    if io:
        pins.append(('5', 'VIO', io))
    return board(('U1', value, pins), ('U2', 'STM32', [('1', 'PA11', rxd), ('2', 'VDD', 'VCC_3V3')]))


def three_v3_transceiver_into_1v8():
    return board(('U1', 'SN65HVD230', [('1', 'TXD', 'TX1'), ('2', 'GND', 'GND'), ('3', 'VCC', 'VCC_3V3'), ('4', 'RXD', 'RX1'), ('6', 'CANL', 'L'), ('7', 'CANH', 'H')]),
                 ('U2', 'STM32', [('1', 'PA11', 'RX1'), ('2', 'VDD', 'VCC_1V8')]))


def test_can_rxd_without_vio_into_a_lower_ic():
    [row] = rows(can_chip(), 'SIG-A13')
    assert row['needs_human'] and 'G04-033' in row['detail']
    assert not rows(can_chip(io='VCC_3V3'), 'SIG-A13')
    assert not rows(can_chip(supply='VCC_3V3'), 'SIG-A13')
    assert not rows(can_chip(io='VCC_5V'), 'SIG-A13')    # this rule's structure is no VIO pin at all
    assert not rows(three_v3_transceiver_into_1v8(), 'SIG-A13')    # only a 5 V transceiver is this rule's structure


def magjack(tct, *extra, value='HR911105A'):
    return board(('J1', value, [('1', 'TD+', 'TXP'), ('2', 'TCT', tct), ('3', 'TD-', 'TXN')]), *extra)


def test_center_tap_floating_or_grounded():
    assert '悬空' in details(rows(magjack('CT_LONE'), 'SIG-A14'))
    assert 'GND' in details(rows(magjack('GND'), 'SIG-A14'))
    assert not rows(magjack('CT1', two('C1', '100n', 'CT1', 'GND')), 'SIG-A14')
    assert not rows(magjack('CT_LONE', value='CONN_8P'), 'SIG-A14')


# --- DEV-A02, G03-037 --------------------------------------------------------------------------------------------
def polarised(plus, minus):
    return board(('C1', 'CP_100u', [('1', '+', plus), ('2', '-', minus)]))


def test_polarised_capacitor_between_two_positive_rails():
    [row] = rows(polarised('VCC_5V', 'VCC_12V'), 'DEV-A02')
    assert 'VCC_5V' in row['detail'] and 'VCC_12V' in row['detail']
    assert not rows(polarised('VCC_12V', 'VCC_5V'), 'DEV-A02')


def test_a_negative_rail_on_the_minus_pin_is_correct():
    assert not rows(polarised('VCC_5V', '-12V'), 'DEV-A02')
    assert not rows(polarised('-12V', 'VCC_5V'), 'DEV-A02')    # the two-positive-rails reading does not apply
    assert not rows(polarised('VCC_5V', 'VCC_-12V'), 'DEV-A02')
    assert not rows(polarised('VCC_5V', 'VCC_N12V'), 'DEV-A02')


# --- registration ------------------------------------------------------------------------------------------------
NEW_RULES = ('DEV-A04 DEV-A05 DOC-A05 PWR-A09 PWR-A10 PWR-A11 PRO-A07 PRO-A08 PRO-A09 PRO-A10 PRO-A11 PRO-A12 PRO-A13 '
             'SIG-A07 SIG-A08 SIG-A09 SIG-A10 SIG-A11 SIG-A12 SIG-A13 SIG-A14 ANA-A01 ANA-A02 ANA-A03').split()


def test_every_new_scan_maps_to_its_criteria_and_says_which():
    source = Path(gs.__file__).read_text(encoding='utf-8')
    for rule in NEW_RULES:
        assert catalog.BASIS[rule], rule
        assert "'%s'" % rule in source, rule
        for criterion in catalog.BASIS[rule]:
            assert criterion in catalog.BY_ID[rule].criterion, (rule, criterion)


def test_scans_stay_silent_on_a_board_with_nothing_to_read():
    assert not [f for f in Lint(board(two('R1', '10k', 'A', 'GND'))).run() if f['rule'] in NEW_RULES]


def test_no_scan_maps_to_a_criterion_classified_for_a_human():
    import json
    classes = json.loads((Path(__file__).resolve().parents[2] / 'docs' / 'proposals' / 'guideline-scan-classes-2026-11-04.json').read_text(encoding='utf-8'))['criteria']
    for rule, targets in catalog.BASIS.items():
        if catalog.method_of(rule) == 'A':
            for target in targets:
                assert classes[target]['class'] != 'human', (rule, target)

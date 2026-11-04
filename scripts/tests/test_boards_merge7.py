"""boards-merge7 (user 2026-11-03: 按建议执行): the HOLD_UP and SIGNAL_PROTECTION circuit types, their candidates, the
clamp-to-pin walk through one series resistor, and '/' as a word boundary of the circuit-type name cues."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import catalog
import guideline_criteria


# 1–2: the vocabulary and the catalog frame
def test_new_types_sit_between_isolation_and_debug_in_vocabulary_and_catalog():
    names = guideline_criteria.vocabulary()['vocabulary']['circuit_types']
    at = names.index('ISOLATION')
    assert names[at + 1:at + 4] == ['HOLD_UP', 'SIGNAL_PROTECTION', 'DEBUG']
    assert [t.name for t in catalog.CIRCUIT_TYPES][at + 1:at + 4] == ['HOLD_UP', 'SIGNAL_PROTECTION', 'DEBUG']
    # the two types arrived with 1.7.2; later libraries keep them (1.7.3 added HOLD_UP to G03-023/G05-090)
    version = guideline_criteria.load(guideline_criteria.BUNDLE_PATH)['library_version']
    assert tuple(int(x) for x in version.split('.')) >= (1, 7, 2), version


def test_hold_up_and_signal_protection_ask_existing_circuit_checks():
    hold, port = catalog.CIRCUIT_TYPE_BY_NAME['HOLD_UP'], catalog.CIRCUIT_TYPE_BY_NAME['SIGNAL_PROTECTION']
    assert (hold.title, hold.domain, hold.subjects) == ('掉电保持', 'PWR', ('PWR-C18', 'PWR-T05', 'PWR-C13'))
    assert (port.title, port.domain, port.subjects) == ('信号端口保护', 'PRO', ('PRO-C01', 'PRO-C05', 'PRO-C08'))
    for rule in hold.subjects + port.subjects:
        assert catalog.BY_ID[rule].scope == 'circuit', rule
    assert catalog.CANDIDATE_STATES['HOLD_UP'] == ('startup', 'run', 'power-down')
    assert catalog.CANDIDATE_STATES['SIGNAL_PROTECTION'] == ('run', 'fault')
    assert 'HOLD_UP' not in catalog.EXTERNAL_INTERFACE_TYPES and 'SIGNAL_PROTECTION' not in catalog.EXTERNAL_INTERFACE_TYPES


def test_hold_up_name_cue_reads_a_hold_rail_not_a_flash_hold_pin():
    import re
    cue = re.compile(catalog.CIRCUIT_TYPE_BY_NAME['HOLD_UP'].pattern, re.I)
    for hit in ('NET:24V_HOLD', 'NET:/03_Logic/24V_HOLD', 'NET:VHOLD', 'NET:HOLDUP_CAP', 'NET:V_HOLD_UP'):
        assert cue.search(hit), hit
    for miss in ('NET:FLASH_HOLD', 'NET:QSPI_IO3_HOLD', 'NET:~HOLD', 'NET:HOLD#', 'PIN:U3.7:HOLD'):
        assert not cue.search(miss), miss


def _resistor_channel(ptc):
    from test_boards_merge2b_roles import empty
    from test_inductive_load import add
    db = empty()
    add(db, 'J1', 'Conn', [('1', 'DI1', 'DI1'), ('2', 'GND', 'GND')])
    add(db, 'D1', 'SMAJ30CA', [('1', 'A1', 'DI1'), ('2', 'A2', 'GND')])
    add(db, 'F1' if ptc else 'R1', 'PTC 0.1A' if ptc else '1k', [('1', '1', 'DI1'), ('2', '2', 'IN1')])
    add(db, 'U1', 'MCU', [('1', 'PA0', 'IN1'), ('2', 'VSS', 'GND')])
    return db


def test_pptc_check_is_asked_of_a_port_with_a_pptc_and_not_of_a_resistor_only_port():
    from test_subject_requires import asked, not_asked, plan_of
    with_r = plan_of(_resistor_channel(False), 'SIGNAL_PROTECTION', ['J1', 'D1', 'R1'])
    assert asked(with_r, 'PRO-C08') == [] and not_asked(with_r)['PRO-C08'] == 'FUSE_PART'
    assert asked(with_r, 'PRO-C01') and asked(with_r, 'PRO-C05')
    with_ptc = plan_of(_resistor_channel(True), 'SIGNAL_PROTECTION', ['J1', 'D1', 'F1'])
    assert asked(with_ptc, 'PRO-C08') and 'PRO-C08' not in not_asked(with_ptc)


# 3: candidates. The calibration board's shapes on the merge6 I/O fixture: D201 holds 24V_HOLD for the buck U201, and
# the DI contact /07_DI/DI1 is clamped by D611 and limited by R611 (behind the forward diode D621) into U601 IP0.
def _io(hold=True, channel_diode=True):
    from test_boards_merge6 import _io_board
    from test_inductive_load import add
    db = _io_board()
    if hold:
        add(db, 'D201', 'STPS2L60', [('1', 'A', '24V_BUS'), ('2', 'K', '24V_HOLD')])
        add(db, 'C201', '330uF', [('1', '', '24V_HOLD'), ('2', '', 'GND')])
        add(db, 'U201', 'LM5160', [('1', 'VIN', '24V_HOLD'), ('2', 'SW', 'SW_N'), ('3', 'GND', 'GND'), ('4', 'FB', 'FB_N')])
        add(db, 'L201', '22uH', [('1', '', 'SW_N'), ('2', '', '+5V')])
        db['parts']['C201'].update(prim='Device:C_Polarized', part='C')
    add(db, 'U601', 'SN65HVS883PWPR', [('3', 'IP0', 'IP0'), ('14', 'V24', 'V24_F'), ('28', 'FGND', 'FGND')])
    if channel_diode:   # the calibration board puts 1N4007 D621 ahead of R611
        db['nets']['/07_DI/DI1'].remove('R611.1')
        db['pin2net']['R611.1'] = 'DI1_K'
        db['nets']['DI1_K'] = ['R611.1']
        add(db, 'D621', '1N4007', [('1', 'A', '/07_DI/DI1'), ('2', 'K', 'DI1_K')])
        db['parts']['R611']['value'] = '1.2k'
    return db


def _candidates(db):
    from test_boards_merge6 import IO_KINDS, IO_RAILS
    from test_circuit_candidates import intent_for
    import circuit_candidates as cc
    kinds = dict(IO_KINDS, U201='regulator', D201='diode', D621='diode')
    intent, audit = intent_for(db, kinds=kinds, rails=dict(IO_RAILS, **{'24V_HOLD': {'voltage_v': {'min': 19, 'max': 29}}}))
    return {c['id']: c for c in cc.build(db, intent, audit)['candidates']}


def _refs(candidate):
    return sorted(m['ref'] for m in candidate['members'])


def test_hold_up_diode_into_storage_ahead_of_a_regulator_is_a_hold_up_candidate():
    found = _candidates(_io())
    hold = found['HOLD_UP-D201']
    assert _refs(hold) == ['C201', 'D201'] and not hold['cross_cutting']
    assert hold['nets'] == {'input': '24V_BUS', 'storage': '24V_HOLD'}
    assert hold['states'] == ['startup', 'run', 'power-down']
    assert next(m for m in hold['members'] if m['ref'] == 'D201')['owned']


def test_reverse_polarity_or_ing_and_bridged_diodes_are_no_hold_up():
    from test_inductive_load import add
    db = _io()
    add(db, 'D202', 'STPS2L60', [('1', 'A', 'VAUX'), ('2', 'K', '24V_HOLD')])        # a second source ORed in
    assert not any(k.startswith('HOLD_UP') for k in _candidates(db))
    db = _io()
    add(db, 'Q201', 'PMOS', [('1', 'G', 'GND'), ('2', 'D', '24V_BUS'), ('3', 'S', '24V_HOLD')])   # ideal-diode pair
    assert not any(k.startswith('HOLD_UP') for k in _candidates(db))
    db = _io()                                                                      # anode straight on a connector
    add(db, 'J201', 'Conn_01x02', [('1', '', '24V_BUS'), ('2', '', 'GND')])
    assert not any(k.startswith('HOLD_UP') for k in _candidates(db))
    db = _io()
    db['parts']['C201']['value'] = '1uF'                                            # no storage behind the diode
    assert not any(k.startswith('HOLD_UP') for k in _candidates(db))


def test_clamped_and_limited_di_contact_into_an_ic_pin_is_a_signal_port_candidate():
    for channel_diode in (True, False):
        port = _candidates(_io(channel_diode=channel_diode))['SIGNAL_PROTECTION-J601']
        assert port['cross_cutting'] and port['nets'] == {'protected0': 'IP0'}
        roles = {m['ref']: m['role'] for m in port['members']}
        want = {'J601': 'connector', 'D611': 'clamp', 'R611': 'series_limiter'}
        if channel_diode:
            want['D621'] = 'series_diode'
        assert roles == want
        assert 'U601' not in roles and 'D602' not in roles      # the IC stays with its circuit; field power is not a channel


def test_a_channel_without_a_clamp_a_limiter_or_an_ic_pin_is_no_signal_port():
    db = _io(channel_diode=False)
    db['parts']['R611']['value'] = '0R'
    db['parts']['R611'].update(prim='Device:FerriteBead', part='FB')                # no limiter, a filter only
    from test_boards_merge6 import IO_KINDS
    found = _candidates(db)
    assert 'SIGNAL_PROTECTION-J601' not in found or 'R611' not in _refs(found['SIGNAL_PROTECTION-J601'])
    db = _io(channel_diode=False)
    for node in ('D611.1', 'D611.2'):                                               # no clamp
        db['nets'][db['pin2net'].pop(node)].remove(node)
    del db['parts']['D611']
    assert 'SIGNAL_PROTECTION-J601' not in _candidates(db)
    db = _io()                                                                      # D621 turned round: blocks the signal
    db['pinname']['D621.1'], db['pinname']['D621.2'] = 'K', 'A'
    assert 'SIGNAL_PROTECTION-J601' not in _candidates(db)


def test_a_zero_ohm_link_is_no_limiter():
    db = _io(channel_diode=False)
    db['parts']['R611']['value'] = '0R'
    assert 'SIGNAL_PROTECTION-J601' not in _candidates(db)


def test_a_port_channel_another_circuit_already_holds_is_not_taken():
    from test_boards_merge2b_roles import empty
    from test_inductive_load import add
    from test_circuit_candidates import intent_for
    import circuit_candidates as cc
    db = empty()
    add(db, 'J1', 'Conn_01x02', [('1', 'A', 'SIG'), ('2', 'GND', 'GND')])
    add(db, 'D1', 'PESD5V0S1BA', [('1', 'K', 'SIG'), ('2', 'A', 'GND')])
    add(db, 'R1', '1k', [('1', '', 'SIG'), ('2', '', 'IN')])
    add(db, 'U1', 'STM32G0', [('1', 'PA0', 'IN'), ('2', 'VSS', 'GND'), ('3', 'VDD', '+3V3')])
    rails = {'GND': {'voltage_v': {'min': 0, 'max': 0}}, '+3V3': {'voltage_v': {'min': 3.2, 'max': 3.4}}}
    intent, audit = intent_for(db, kinds={'D1': 'tvs', 'U1': 'mcu'}, rails=rails)
    found = {c['id']: c for c in cc.build(db, intent, audit)['candidates']}
    assert sorted(m['ref'] for m in found['SIGNAL_PROTECTION-J1']['members']) == ['D1', 'J1', 'R1']
    add(db, 'U2', 'OPA333', [('1', 'IN+', 'SIG'), ('2', 'V-', 'GND'), ('3', 'V+', '+3V3'), ('4', 'OUT', 'AOUT')])
    intent, audit = intent_for(db, kinds={'D1': 'tvs', 'U1': 'mcu', 'U2': 'opamp_comparator'}, rails=rails)
    found = {c['id']: c for c in cc.build(db, intent, audit)['candidates']}
    assert 'SIGNAL_PROTECTION-J1' not in found and 'D1' in [m['ref'] for m in found['ANALOG-U2']['members']]


# 4: PRO-E02 walks from the clamp's net through one series resistor or PTC, past forward series diodes, to the IC pin
def _di_channel(diode='forward', limiter=('R611', '1.2k'), clamp='SMAJ30CA', second=False):
    from test_boards_merge2b_roles import empty
    from test_inductive_load import add
    db = empty()
    add(db, 'J601', 'TERM_DI', [('2', 'DI1', '/07_DI/DI1'), ('10', 'FCOM', 'FGND')])
    add(db, 'D611', clamp, [('1', 'A1', '/07_DI/DI1'), ('2', 'A2', 'FGND')])
    ends = ('/07_DI/DI1', 'DI1_K') if diode == 'forward' else ('DI1_K', '/07_DI/DI1')
    add(db, 'D621', '1N4007', [('1', 'A', ends[0]), ('2', 'K', ends[1])])
    ref, value = limiter
    add(db, ref, value, [('1', '', 'DI1_K'), ('2', '', 'MID' if second else 'IP0')])
    if second:
        add(db, 'R699', '1k', [('1', '', 'MID'), ('2', '', 'IP0')])
    add(db, 'U601', 'SN65HVS883PWPR', [('3', 'IP0', 'IP0'), ('28', 'FGND', 'FGND')])
    return db


def _clamp_line(db, ref='D611'):
    from lint import Lint
    return next(x['detail'] for x in Lint(db).run() if x['rule'] == 'PRO-E02' and x.get('ref') == ref)


def test_clamp_line_compares_the_clamp_through_the_resistor_with_the_pin_limit():
    line = _clamp_line(_di_channel())
    assert 'IC 脚 U601.3(IP0) 经 D621、R611' in line
    assert '钳位 48.4 V（ST SMAJ DS1251 Rev 15 p2 Table 2' in line
    assert '经 D621（二极管压降不计）、R611 1.2 kΩ 到 U601.3(IP0) 绝限 36 V（TI SLASEE6' in line
    assert '钳位高出脚绝限 12.4 V，需注入 ≥ 10.3 mA' in line and '脚电压约 43.6 V，仍高于绝限' in line


def test_clamp_line_without_tabled_parts_names_what_to_read():
    line = _clamp_line(_di_channel(clamp='SMBJ30CA'))
    assert '钳位电压（读手册 VCL@IPP）经 D621（二极管压降不计）、R611 1.2 kΩ 到 U601.3(IP0) 绝限 36 V' in line
    assert '钳位高出' not in line
    db = _di_channel(limiter=('F611', 'PTC 0.05A'))
    assert 'F611（阻值未读出） 到 U601.3(IP0)' in _clamp_line(db)


def test_the_walk_goes_forward_through_diodes_and_through_one_limiter_only():
    assert '同网没有 IC 脚' in _clamp_line(_di_channel(diode='reverse'))
    assert '同网没有 IC 脚' in _clamp_line(_di_channel(second=True))
    from test_inductive_load import add
    db = _di_channel()
    add(db, 'U9', 'LM358', [('4', 'GND', 'IP0')])                                # a ground-named pin is no protected pin
    line = _clamp_line(db)
    assert 'U601.3(IP0)' in line and 'U9.4' not in line


def test_drop_check_words():
    import protective_clamps as pc
    assert pc.drop_check(30.0, 1000.0, (36.0, None, '')) == '钳位不高于脚绝限'
    assert pc.drop_check(48.4, 10000.0, (36.0, 4e-3, '')).endswith('脚电压约 8.4 V，不高于绝限')
    assert pc.clamp_rating({'part': 'SMAJ30A'})[0] == 48.4 and pc.clamp_rating({'part': 'SMAJ300CA'}) is None
    assert pc.pin_limit({'part': 'SN65HVS883'}, 'IP7')[0] == 36.0 and pc.pin_limit({'part': 'SN65HVS882'}, 'IP7') is None


# 5: a hierarchical net's leaf is a word for the name cues; a sheet name in the path and a pin's alternate functions are not
def _hits(kind, *blobs):
    import re
    cue = re.compile(catalog.CIRCUIT_TYPE_BY_NAME[kind].pattern, re.I)
    return [b for b in blobs if cue.search(b)]


def test_name_cues_read_the_leaf_of_a_hierarchical_net():
    assert _hits('I2C', 'NET:/SCL', 'NET:/nRF52840/SDA', 'NET:/CAN, RS485, UART/SCL') == [
        'NET:/SCL', 'NET:/nRF52840/SDA', 'NET:/CAN, RS485, UART/SCL']
    assert _hits('STARTUP', 'NET:/04_MCU/BOOT0') == ['NET:/04_MCU/BOOT0']
    assert _hits('POWER_CONVERTER', 'NET:/Power/FB', 'NET:/VOUT') == ['NET:/Power/FB', 'NET:/VOUT']
    assert _hits('ANALOG', 'NET:/AIN1', 'NET:/PoE/ISENSE') == ['NET:/AIN1', 'NET:/PoE/ISENSE']
    assert _hits('HOLD_UP', 'NET:/03_Logic/24V_HOLD') == ['NET:/03_Logic/24V_HOLD']


def test_a_sheet_name_or_a_pins_alternate_function_is_no_word():
    assert _hits('ANALOG', 'NET:/ADC/FOO', 'NET:/AIN/IN_P') == []                 # sheets named ADC, AIN
    assert _hits('STARTUP', 'PIN:U301.20:PB2/BOOT1', 'PIN:U4.A10:P0.29/BOOT') == []
    assert _hits('I2C', 'PIN:U1.6:P7/SCL/D5') == []
    assert _hits('DEBUG', 'NET:/DBG_LED', 'NET:/Debugger/FPGA_ADV') == []         # DEBUG keeps its form
    assert _hits('DEBUG', 'NET:DBG_LED') == ['NET:DBG_LED']                      # as before, without a path

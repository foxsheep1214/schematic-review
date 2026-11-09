"""boards-merge6: the industrial I/O calibration board (ASG-drawn, RS-485/CAN/8 DI/4 DO, 24 V input) false alarms and
misses, one block per finding id of evals/boards/calibration--industrial-io-rs485-can/findings.json."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import board_intent
from checkers.netgraph import NetGraph


def _one_pin_device(native, official, role='power'):
    from test_boards_merge2b_roles import empty
    from test_inductive_load import add
    db = empty()
    add(db, 'U1', 'IC', [('49', native, 'VCC')])
    intent = {'devices': {'U1': {'pinout_complete': True, 'citation': 'ST IPS4140HQ DS14694 p2 Table 1',
                                 'pins': {'49': {'name': official, 'role': role}}}}}
    return NetGraph(board_intent.graph_db(db, intent))


# F04: "VCC (TAB)" is the VCC pin (ST IPS4140HQ DS14694 p2 Table 1); the bracket names the copper, not a function
def test_bracketed_package_note_is_not_a_pin_name_conflict():
    for official in ('VCC (TAB)', 'VCC(TAB)', 'VCC (EP)', 'VCC (Exposed Pad)', 'VCC (PAD)'):
        assert not _one_pin_device('VCC', official).pin_conflicts, official


def test_package_note_does_not_hide_a_different_function():
    assert _one_pin_device('GND', 'VCC (TAB)').pin_conflicts
    assert _one_pin_device('VCC', 'OUT1 (TAB)').pin_conflicts
    assert _one_pin_device('VCC', 'VCC (SENSE)').pin_conflicts      # not a package note: compared as written


# F13: SN65HVS883 DB0/DB1 open select a debounce time (SLASEE6 p3 Pin Functions, p5 tDB rows "DB0 = DB1 = open")
def test_sn65hvs883_debounce_select_may_be_open():
    import part_words as pw
    from test_boards_merge5_minor import one_pin
    assert 'SLASEE6' in pw.unused_input_permission(one_pin('U601', 'SN65HVS883PWPR', '2', 'DB1'), 'U601.2')
    assert 'SLASEE6' in pw.unused_input_permission(one_pin('U601', 'SN65HVS883', '1', 'DB0'), 'U601.1')
    assert pw.unused_input_permission(one_pin('U601', 'SN65HVS883PWPR', '24', 'CE'), 'U601.24') is None
    assert pw.unused_input_permission(one_pin('U601', 'SN65HVS883PWPR', '3', 'DB1'), 'U601.3') is None   # name on the wrong pin
    assert pw.unused_input_permission(one_pin('U601', 'SN65HVS882', '2', 'DB1'), 'U601.2') is None       # another model


# F14: ISO6441 EN1/EN2 tied to VCC1/VCC2 is the datasheet hookup (TI ISO644x SLLSG01C p5: enabled when ENx is high or open)
def _iso(en2_name='EN2', en2_net='+5V_ISO', part='ISO6441FDWR'):
    from test_boards_merge2b_roles import empty
    from test_inductive_load import add
    db = empty()
    add(db, 'U602', part, [('1', 'VCC1', '+3V3'), ('2', 'GND1', 'GND'), ('7', 'EN1', '+3V3'), ('3', 'INA', 'TX'),
                           ('16', 'VCC2', '+5V_ISO'), ('15', 'GND2', 'FGND'), ('10', en2_name, en2_net), ('14', 'OUTA', 'TX_ISO')])
    add(db, 'C1', 'C', [('1', '', '+3V3'), ('2', '', 'GND')])
    add(db, 'C2', 'C', [('1', '', '+5V_ISO'), ('2', '', 'FGND')])
    return db


def _coupled(db):
    from checkers.power_up import build_inventory
    return [x['node'] for s in build_inventory(db)['states'] for x in s['coupled_loads']]


def test_isolator_output_enable_tied_to_its_own_side_supply_is_not_a_sequencing_candidate():
    assert _coupled(_iso()) == []


def test_isolator_enable_exemption_keeps_active_low_other_side_and_non_isolators():
    assert _coupled(_iso(en2_name='~EN2')) == ['U602.10']          # active low tied high disables the outputs
    assert _coupled(_iso(en2_net='+3V3')) == ['U602.10']             # EN2 on the other side's supply
    assert _coupled(_iso(part='TPS2116')) == ['U602.10', 'U602.7']   # not a digital isolator: unchanged


# F15: LM74910H-Q1 EN on VS with UVLO set by its own divider (SNOSDE6C typical application): no "EN without UVLO"
def _ideal_diode(uvlo=True):
    from test_boards_merge2b_roles import empty
    from test_inductive_load import add
    db = empty()
    add(db, 'U101', 'LM74910HQRGERQ1', [('22', 'VS', 'VS_N'), ('6', 'EN', 'VS_N'), ('4', 'UVLO', 'UVLO_N' if uvlo else 'VS_N'),
                                        ('15', 'OUT', '24V_BUS'), ('3', 'SW', 'VS_N'), ('13', 'GND', 'GND')])
    add(db, 'J1', 'Conn_01x02', [('1', '', 'VS_N'), ('2', '', 'GND')])
    add(db, 'C1', '10u', [('1', '', 'VS_N'), ('2', '', 'GND')])
    if uvlo:
        add(db, 'R105', '470k', [('1', '', 'VS_N'), ('2', '', 'UVLO_N')])
        add(db, 'R106', '33k', [('1', '', 'UVLO_N'), ('2', '', 'GND')])
    for ref in ('R105', 'R106'):
        if ref in db['parts']:
            db['parts'][ref].update(prim='Device:R', part='R')
    return db


def _rst_a03(db):
    from lint import Lint
    return [f for f in Lint(db).run() if f['rule'] == 'RST-A03']


def test_separate_uvlo_divider_closes_en_tied_to_input():
    from checkers.power_up import build_inventory
    item = build_inventory(_ideal_diode())['states'][0]['regulators'][0]
    assert item['enable_source'] == 'tied-to-input' and item['uvlo_pins'] == ['U101.4']
    assert _rst_a03(_ideal_diode()) == []


def test_en_tied_to_input_without_a_uvlo_divider_is_still_reported():
    assert _rst_a03(_ideal_diode(uvlo=False))


def test_uvlo_pin_needs_its_own_divider_and_rule_instances_agree():
    from checkers.power_up import PowerUpChecker, build_inventory
    db = _ideal_diode()
    for net in ('VS_N', 'UVLO_N'):     # R105 removed: UVLO only pulled down, no turn-on point from the input
        db['nets'][net] = [n for n in db['nets'][net] if not n.startswith('R105.')]
    del db['parts']['R105'], db['pin2net']['R105.1'], db['pin2net']['R105.2']
    assert _rst_a03(db)
    assert PowerUpChecker().rule_instances('RST-A03', build_inventory(_ideal_diode())) == []
    assert PowerUpChecker().rule_instances('RST-A03', build_inventory(db))


# F16–F18: datasheet title cues (TI TVS3300 SLVSDO2C p1, Bourns MF-R p1, ST IPS4140HQ DS14694 p1)
def test_surge_protection_device_title_names_a_tvs_but_not_over_a_varistor():
    import datasheet_kinds as dk
    assert dk.cues('TVS3300 33-V Flat-Clamp Surge Protection Device') == {'tvs'}
    assert dk.cues('SIOV metal oxide varistors, surge protection device') == {'varistor'}
    assert dk.cues('Bidirectional TVS diode and varistor array') == {'tvs', 'varistor'}


def test_efuse_is_read_as_a_word():
    import datasheet_kinds as dk
    assert dk.cues('MF-R Series - PTC Resettable Fuses') == {'fuse'}
    assert dk.cues('MF-R Series - PTC ResettableFuses') == {'fuse'}
    assert 'load_switch' in dk.cues('TPS2660x 60-V, 2-A Industrial eFuse')
    assert 'load_switch' in dk.cues('TPS25947 e-Fuse with reverse current blocking')


def test_high_side_smart_power_relay_is_a_load_switch_photomos_stays_a_relay():
    import datasheet_kinds as dk
    assert dk.cues('Quad high-side smart power solid-state relay in QFN48L 8x6 mm package') == {'load_switch'}
    assert dk.cues('PhotoMOS solid state relay') == {'relay'}


# F19, M01, M03, F21: circuit candidates on a small copy of the calibration board's shapes
def _io_board():
    from test_boards_merge2b_roles import empty
    from test_inductive_load import add
    db = empty()
    # 24 V entry: J101 -> F101 -> RV101 -> U101 (ideal diode / circuit breaker, EN tied to its VS supply)
    add(db, 'J101', 'Conn_01x03', [('1', '', '/02_Input/VIN_RAW'), ('2', '', 'GND'), ('3', '', 'CHASSIS')])
    add(db, 'F101', 'Fuse', [('1', '', '/02_Input/VIN_RAW'), ('2', '', 'VIN_F')])
    add(db, 'RV101', 'Varistor', [('1', '', 'VIN_F'), ('2', '', 'GND')])
    add(db, 'C113', '4.7nF', [('1', '', 'CHASSIS'), ('2', '', 'GND')])
    add(db, 'U101', 'LM74910', [('2', 'A', 'VIN_F'), ('22', 'VS', 'VS_N'), ('6', 'EN', 'VS_N'), ('15', 'OUT', '24V_BUS'),
                                ('13', 'GND', 'GND')])
    add(db, 'C104', '100nF', [('1', '', 'VS_N'), ('2', '', 'GND')])
    add(db, 'C110', '470uF', [('1', '', '24V_BUS'), ('2', '', 'GND')])
    # CAN connector with a PPTC termination branch behind a jumper header
    add(db, 'J501', 'TERM_CAN', [('1', '', '/06_CAN/CANH'), ('2', '', '/06_CAN/CANL'), ('3', '', 'GND')])
    add(db, 'R503', '110R', [('1', '', '/06_CAN/CANH'), ('2', '', 'TERM')])
    add(db, 'F501', 'MF-R005 Polyfuse', [('1', '', 'TERM'), ('2', '', 'JP_A')])
    add(db, 'JP501', 'Conn_01x02', [('1', '', 'JP_A'), ('2', '', '/06_CAN/CANL')])
    db['parts']['JP501']['prim'] = 'Connector_Generic:Conn_01x02'
    # DI connector: field power through a reverse diode to its storage capacitor, plus a clamped DI channel
    add(db, 'J601', 'TERM_DI', [('1', '', '/07_DI/FIELD_P'), ('2', '', '/07_DI/DI1'), ('10', '', 'FGND')])
    add(db, 'D601', 'Diode', [('1', 'A', '/07_DI/FIELD_P'), ('2', 'K', 'FIELD_K')])
    add(db, 'D602', 'SMAJ33CA', [('1', 'A1', '/07_DI/FIELD_P'), ('2', 'A2', 'FGND')])
    add(db, 'R601', '100R', [('1', '', 'FIELD_K'), ('2', '', 'V24_F')])
    add(db, 'C601', '22uF', [('1', '', 'V24_F'), ('2', '', 'FGND')])
    add(db, 'D611', 'SMAJ30CA', [('1', 'A1', '/07_DI/DI1'), ('2', 'A2', 'FGND')])
    add(db, 'R611', '3k3', [('1', '', '/07_DI/DI1'), ('2', '', 'IP0')])
    # MCU with BOOT0/BOOT1 strap pull-downs, reset capacitor and an 8 MHz crystal on OSC_IN/OSC_OUT
    add(db, 'U301', 'STM32F103C8T6', [('1', 'VDD', '+3V3'), ('8', 'VSS', 'GND'), ('7', 'NRST', 'NRST'),
                                      ('44', 'BOOT0', '/04_MCU/BOOT0'), ('20', 'PB2/BOOT1', '/04_MCU/BOOT1'),
                                      ('5', 'PD0/OSC_IN', '/04_MCU/OSC_IN'), ('6', 'PD1/OSC_OUT', '/04_MCU/OSC_OUT')])
    add(db, 'C307', '100nF', [('1', '', 'NRST'), ('2', '', 'GND')])
    add(db, 'R301', '10k', [('1', '', 'GND'), ('2', '', '/04_MCU/BOOT0')])
    add(db, 'R302', '10k', [('1', '', 'GND'), ('2', '', '/04_MCU/BOOT1')])
    add(db, 'Y301', 'Crystal 8MHz', [('1', '1', '/04_MCU/OSC_IN'), ('2', '2', '/04_MCU/OSC_OUT')])
    add(db, 'C308', '20pF', [('1', '', '/04_MCU/OSC_IN'), ('2', '', 'GND')])
    add(db, 'C309', '20pF', [('1', '', '/04_MCU/OSC_OUT'), ('2', '', 'GND')])
    add(db, 'C302', '100nF', [('1', '', '+3V3'), ('2', '', 'GND')])
    for ref in ('R503', 'R601', 'R611', 'R301', 'R302'):
        db['parts'][ref].update(prim='Device:R', part='R')
    for ref in ('C113', 'C104', 'C110', 'C601', 'C307', 'C308', 'C309', 'C302'):
        db['parts'][ref].update(prim='Device:C', part='C')
    return db


IO_KINDS = {'U101': 'load_switch', 'U301': 'mcu', 'F101': 'fuse', 'F501': 'fuse', 'RV101': 'varistor', 'D601': 'diode',
            'D602': 'tvs', 'D611': 'tvs'}
IO_RAILS = {'GND': {'voltage_v': {'min': 0, 'max': 0}}, 'FGND': {'voltage_v': {'min': 0, 'max': 0}, 'domain': 'FIELD'},
            'VS_N': {'voltage_v': {'min': 20, 'max': 29}}, '24V_BUS': {'voltage_v': {'min': 20, 'max': 29}},
            'V24_F': {'voltage_v': {'min': 20, 'max': 29}, 'domain': 'FIELD'}, '+3V3': {'voltage_v': {'min': 3.2, 'max': 3.4}}}


def _io_candidates(db=None, requirements=None):
    from test_circuit_candidates import intent_for
    import circuit_candidates as cc
    db = db or _io_board()
    intent, audit = intent_for(db, kinds=IO_KINDS, rails=IO_RAILS)
    if requirements:
        intent['requirements'] = requirements
    return {c['id']: c for c in cc.build(db, intent, audit)['candidates']}


def _refs(candidate):
    return sorted(m['ref'] for m in candidate['members'])


def test_input_candidates_keep_only_power_branches_and_skip_jumpers():
    found = _io_candidates()
    assert 'POWER_PROTECTION-J501' not in found and 'POWER_PROTECTION-JP501' not in found   # CAN termination PPTC
    assert _refs(found['POWER_PROTECTION-J601']) == ['C601', 'D601', 'D602', 'J601', 'R601']   # field power, no DI channel
    assert _refs(found['POWER_PROTECTION-J101']) == ['F101', 'J101']    # chassis Y-cap dropped; RV101 is nearer U101


def test_enable_tied_to_a_supply_is_no_startup_chain():
    found = _io_candidates()
    assert 'STARTUP-U101.EN' not in found
    assert 'STARTUP-U301.NRST' in found


def test_power_entry_evidence_without_a_storage_capacitor():
    from test_inductive_load import add
    db = _io_board()
    # AC inlet: fuse then a varistor across the line, the bulk sits behind a converter the walk cannot see
    add(db, 'J9', 'Conn_01x02', [('1', '', 'AC_L'), ('2', '', 'AC_N')])
    add(db, 'F9', 'Fuse', [('1', '', 'AC_L'), ('2', '', 'L_F')])
    add(db, 'RV9', 'Varistor', [('1', '', 'L_F'), ('2', '', 'AC_N')])
    # DC barrel jack into a PTC and a reverse-protection MOSFET (neotron-pico J1301/F1301/Q1301)
    add(db, 'J8', 'Jack-DC', [('1', '', 'JACK_P'), ('2', '', 'GND')])
    db['parts']['J8']['prim'] = 'Connector:Jack-DC'
    add(db, 'F8', 'Polyfuse', [('1', '', 'JACK_P'), ('2', '', 'Q_D')])
    add(db, 'Q8', 'PMOS', [('1', 'G', 'GND'), ('2', 'D', 'Q_D'), ('3', 'S', 'VJ')])
    found = _io_candidates(db)
    assert _refs(found['POWER_PROTECTION-J9']) == ['F9', 'J9', 'RV9']
    assert _refs(found['POWER_PROTECTION-J8']) == ['F8', 'J8']


def test_connector_pins_whose_branches_meet_are_one_power_branch():
    from test_inductive_load import add
    db = _io_board()
    add(db, 'J7', 'Conn_01x02', [('1', '', 'P_A'), ('2', '', 'P_B')])
    add(db, 'F7', 'Fuse', [('1', '', 'P_A'), ('2', '', 'X7')])
    add(db, 'R7', '0R', [('1', '', 'P_B'), ('2', '', 'X7')])
    add(db, 'C7', '22uF', [('1', '', 'X7'), ('2', '', 'GND')])
    db['parts']['R7'].update(prim='Device:R', part='R')
    db['parts']['C7'].update(prim='Device:C', part='C')
    assert _refs(_io_candidates(db)['POWER_PROTECTION-J7']) == ['C7', 'F7', 'J7', 'R7']


# F21: STM32 BOOT0/BOOT1 pulls are sampled at reset (DS5319 §2.3.8 boot modes): they join the MCU's reset chain
def test_mcu_boot_strap_pulls_join_the_reset_chain():
    found = _io_candidates()
    reset = found['STARTUP-U301.NRST']
    assert _refs(reset) == ['C307', 'R301', 'R302', 'U301']
    assert {'/04_MCU/BOOT0', '/04_MCU/BOOT1'} <= set(reset['nets'].values())


def test_boot_straps_without_a_reset_chain_form_their_own_startup_chain():
    db = _io_board()
    db['pin2net']['C307.1'] = 'GND'
    db['nets']['GND'].append('C307.1')
    db['nets']['NRST'].remove('C307.1')       # NRST left with the MCU pin only: no reset chain
    found = _io_candidates(db)
    assert 'STARTUP-U301.NRST' not in found
    assert _refs(found['STARTUP-U301.BOOT']) == ['R301', 'R302', 'U301']


def test_multifunction_boot1_pin_gets_a_strap_row():
    import plan_circuits
    assert plan_circuits.STRAP_RE.search('PB2/BOOT1') and plan_circuits.STRAP_RE.search('/04_MCU/BOOT1')
    assert not plan_circuits.STRAP_RE.search('/CONFIG/SDA')


# F20: the hold-up branch (D201 from 24V_BUS to the 24V_HOLD storage) is no eFuse and has one source. boards-merge7
# moved it from a POWER_PROTECTION trimming to its own circuit type, HOLD_UP, which asks neither (test_boards_merge7).
def _holdup():
    from test_boards_merge2b_roles import empty
    from test_inductive_load import add
    db = empty()
    add(db, 'D201', 'STPS2L60', [('1', 'A', '24V_BUS'), ('2', 'K', '24V_HOLD')])
    add(db, 'C201', '470uF', [('1', '', '24V_HOLD'), ('2', '', 'GND')])
    db['parts']['D201']['prim'] = 'Device:D_Schottky'
    return db


def test_holdup_circuit_frame_asks_no_efuse_or_dual_source_rows():
    from test_subject_requires import asked, plan_of
    plan = plan_of(_holdup(), 'HOLD_UP', ['D201', 'C201'])
    assert asked(plan, 'PRO-C07') == [] and asked(plan, 'PWR-C23') == []
    assert asked(plan, 'PWR-C18') and asked(plan, 'PWR-T05')



# M01: the fused, clamped 24 V entry is a DC_24V candidate by the requirement's input window or by its 24 V name
REQ_24V = [{'id': 'IIO-002', 'status': 'CONFIRMED', 'categories': ['INPUT_RANGE'], 'interpretation': '24 V input',
            'parameters': [{'name': 'input_voltage', 'unit': 'V', 'min': 20.4, 'max': 28.8}]}]


def test_dc24_candidate_from_the_declared_input_window():
    import catalog
    found = _io_candidates(requirements=REQ_24V)
    dc = found['DC_24V-J101']
    assert dc['cross_cutting'] and _refs(dc) == ['F101', 'J101', 'RV101'] and 'IIO-002' in dc['members'][1]['via']
    assert dc['states'] == list(catalog.CANDIDATE_STATES['DC_24V']) == ['startup', 'run', 'fault']
    assert 'POWER_PROTECTION-J101' in found                # the protection candidate stays; DC_24V only references
    assert 'DC_24V-J601' not in found                      # field power without a fuse: not the 24 V entry shape


def test_dc24_candidate_needs_a_window_or_a_name_and_the_fuse_clamp_shape():
    assert not any(k.startswith('DC_24V') for k in _io_candidates())
    db = _io_board()
    db['parts']['J101']['value'] = '24V_IN'
    assert 'DC_24V-J101' in _io_candidates(db)
    for node in ('RV101.1', 'RV101.2'):                                          # no clamp left on the branch
        db['nets'][db['pin2net'].pop(node)].remove(node)
    del db['parts']['RV101']
    found = _io_candidates(db, requirements=REQ_24V)
    assert 'DC_24V-J101' not in found
    wide = [dict(REQ_24V[0], parameters=[{'name': 'input_voltage', 'unit': 'V', 'min': 9, 'max': 60}])]
    assert 'DC_24V-J101' not in _io_candidates(requirements=wide)


# M03: an 8 MHz crystal on U301 OSC_IN/OSC_OUT with its load capacitors is a CLOCK candidate
def test_crystal_on_one_ics_oscillator_pins_is_a_clock_candidate():
    clock = _io_candidates()['CLOCK-Y301']
    assert _refs(clock) == ['C308', 'C309', 'Y301'] and not clock['cross_cutting']
    assert sorted(clock['nets'].values()) == ['/04_MCU/OSC_IN', '/04_MCU/OSC_OUT']


def test_crystal_through_a_series_resistor_and_not_on_two_oscillators():
    from test_inductive_load import add
    db = _io_board()
    db['nets']['/04_MCU/OSC_OUT'].remove('Y301.2')
    db['pin2net']['Y301.2'] = 'XO_R'
    db['nets']['XO_R'] = ['Y301.2']
    add(db, 'R309', '220R', [('1', '', 'XO_R'), ('2', '', '/04_MCU/OSC_OUT')])
    db['parts']['R309'].update(prim='Device:R', part='R')
    assert _refs(_io_candidates(db)['CLOCK-Y301']) == ['C308', 'C309', 'R309', 'Y301']
    db = _io_board()
    add(db, 'U302', 'STM32F103C8T6', [('5', 'OSC_IN', '/04_MCU/OSC_IN'), ('6', 'OSC_OUT', '/04_MCU/OSC_OUT')])
    assert 'CLOCK-Y301' not in _io_candidates(db)                     # shared crystal: CLK-A02's, not a candidate
    db = _io_board()
    db['pinname']['U301.6'] = 'PD1'                                   # one end on a plain GPIO
    assert 'CLOCK-Y301' not in _io_candidates(db)


# M02: a hierarchical path separator is a word boundary for the industrial DI name hint (/07_DI/DI1, /INPUT/DI0)
def test_industrial_di_name_hint_reads_hierarchical_nets():
    import catalog
    from plan_circuits import _feature_hits
    pattern = catalog.CIRCUIT_TYPE_BY_NAME['INDUSTRIAL_DI'].pattern
    db = {'nets': {'/07_DI/DI1': ['U601.3', 'R611.1'], '/07_DI/CLK_F': ['U601.25', 'R1.1']}, 'pinname': {}, 'pin2net': {},
          'parts': {}}
    assert _feature_hits(db, pattern) == ['NET:/07_DI/DI1']
    db['nets'] = {'/07_DI/CE_F': ['U601.24', 'R2.1'], '/SDCARD/DI': ['U5.2', 'J5.2']}
    assert _feature_hits(db, pattern) == []


def test_tvs_with_several_bare_k_pins_is_one_channel():
    from test_inductive_load import add
    from test_boards_merge2b_roles import empty
    import protective_clamps as pc
    db = empty()
    add(db, 'D1', 'TVS3300DRVR', [('1', 'A', 'GND'), ('2', 'A', 'GND'), ('3', 'A', 'GND'),
                                  ('4', 'K', '24V_BUS'), ('5', 'K', '24V_BUS'), ('6', 'K', '24V_BUS')])
    add(db, 'J1', 'CONN_01X01', [('1', '', '24V_BUS')])
    db['device_kinds'] = {'D1': {'kind': 'tvs', 'citation': 'TI TVS3300 p1'}}
    cs = pc.channels('D1', db['parts']['D1'], NetGraph(db))
    assert [c['pins'] for c in cs] == [['4', '5', '6']] and cs[0]['return_pins'] == ['1', '2', '3']
    add(db, 'D2', 'TVS2', [('1', 'A', 'GND'), ('2', 'K1', 'L1'), ('3', 'K2', 'L2')])
    db['device_kinds']['D2'] = {'kind': 'tvs', 'citation': 'synthetic'}
    assert len(pc.channels('D2', db['parts']['D2'], NetGraph(db))) == 2
    add(db, 'D3', 'NUP2105L', [('1', 'K', 'CAN_L'), ('2', 'K', 'CAN_H'), ('3', 'A', 'GND')])
    db['device_kinds']['D3'] = {'kind': 'tvs', 'citation': 'synthetic'}
    assert sorted(c['nets'] for c in pc.channels('D3', db['parts']['D3'], NetGraph(db))) == [['CAN_H'], ['CAN_L']]


# Pulse HX5164NL p1: a LAN transformer titled only "1Gigabit Magnetic Modules"
def test_lan_magnetic_module_title_names_a_transformer():
    import datasheet_kinds as dk
    assert dk.cues('1Gigabit Magnetic Modules') == {'transformer'}
    assert 'transformer' not in dk.cues('Magnetic shielded power inductor')


# Maker wordings from the knowledge library that named no kind before, Chinese titles and full-width text
def test_maker_wordings_and_chinese_titles_name_their_kind():
    import datasheet_kinds as dk
    assert dk.cues('SRF3216 Series - Common Mode Chip Inductors') == {'common_mode_choke'}
    assert dk.cues('WE-CNSW SMT Common Mode Line Filter') == {'common_mode_choke'}
    assert dk.cues('XTREME-GUARD™ ESD Suppressors') == {'tvs'}
    assert dk.cues('片 式 发 光 二 极 管') == {'diode'}
    assert dk.cues('稳压二极管') == {'zener'}
    assert dk.cues('贴片压敏电阻') == {'varistor'}
    assert dk.cues('ＴＲＡＮＳＦＯＲＭＥＲ') == {'transformer'}


def test_a_chinese_quote_must_be_on_the_page():
    import datasheet_kinds as dk
    page = lambda path, n: '片 式 发 光 二 极 管\nNCD0805R1'
    found = dk.verify({'kind': 'diode', 'page': 1, 'quote': '片式发光二极管'}, 'x.pdf', read_page=page)
    missing = dk.verify({'kind': 'zener', 'page': 1, 'quote': '稳压二极管'}, 'x.pdf', read_page=page)
    assert found['status'] != 'QUOTE_NOT_FOUND'
    assert missing['status'] == 'QUOTE_NOT_FOUND'

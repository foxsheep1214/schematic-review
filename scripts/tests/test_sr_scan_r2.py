"""Matrix power-and-protection R2 first review (2026-11-04): scanner false alarms F07–F12 and the missed scans F03/F04,
one block per item of the R2 record's SR技能不足.md (1.1–1.6, 2.3, 2.4)."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lint import Lint
import datasheet_kinds
import plan_review
from test_boards_merge2b_roles import empty
from test_inductive_load import add


def _rows(db, rule, intent=None, audit=None):
    return [f for f in Lint(db, None, intent, audit).run() if f['rule'] == rule]


def _kinds(rows):
    return sorted(f['kind'] for f in rows)


# 1.1 PWR-A03: LTC4359 VSS through 1 kΩ to ground is the datasheet's reverse-input hookup (Rev F Figure 4)
def _vss_island(quote):
    db = empty()
    add(db, 'U201', 'LTC4359HMS8', [('4', 'IN', 'VIN'), ('8', 'OUT', 'VOUT'), ('1', 'GATE', 'GATE'), ('6', 'VSS', 'VSS_IN')])
    add(db, 'R203', '1k', [('1', '', 'VSS_IN'), ('2', '', 'GND')])
    add(db, 'U1', 'MCU', [('1', 'VDD', 'VOUT'), ('2', 'GND', 'GND')])
    add(db, 'C1', '10u', [('1', '', 'VOUT'), ('2', '', 'GND')])
    from board_intent import input_fingerprint
    intent = {'device_kinds': {'U201': {'kind': 'load_switch', 'page': 1, 'quote': quote}},
              'input_sha256': input_fingerprint(db)}
    return db, intent


def test_ideal_diode_controller_ground_through_resistor_is_not_an_island():
    db, intent = _vss_island('Ideal Diode Controller with Reverse Input Protection')
    assert _kinds(_rows(db, 'PWR-A03', intent)) == ['INFO']


def test_other_ic_ground_through_resistor_is_still_an_island():
    db, intent = _vss_island('Low Dropout Linear Regulator')
    assert _kinds(_rows(db, 'PWR-A03', intent)) == ['FINDING']
    assert _kinds(_rows(db, 'PWR-A03')) == ['FINDING']                 # no declared title: no exemption


# 1.2 NET-A02: Q and ~{Q} of one flip-flop are two nets on purpose
def _flipflop(qbar_name):
    db = empty()
    add(db, 'U1301', 'SN74HCS74', [('5', '1Q', 'SC_LOCK_ORIN'), ('6', qbar_name, 'SC_LOCKN_ORIN'), ('14', 'VCC', '+3V3'),
                                   ('7', 'GND', 'GND')])
    add(db, 'U1302', 'SN74HCS02', [('3', '1A', 'SC_LOCK_ORIN'), ('5', '2A', 'SC_LOCKN_ORIN')])
    db['pintype'].update({'U1301.5': 'OUT', 'U1301.6': 'OUT', 'U1302.3': 'IN', 'U1302.5': 'IN'})
    return db


def test_complementary_flipflop_outputs_are_not_a_name_split():
    assert not _rows(_flipflop('~{1Q}'), 'NET-A02')
    assert not _rows(_flipflop('1QN'), 'NET-A02')


def test_two_unrelated_outputs_with_close_names_are_still_a_name_split():
    assert _kinds(_rows(_flipflop('2Q'), 'NET-A02')) == ['FINDING']


# 1.3 RST-A06: a flip-flop CLR is a reset input; buffers and open-drain drivers pass the reset on
def _reset(chain):
    db = empty()
    add(db, 'U601', 'TPS3808G33', [('1', '~{RESET}', 'RAW_N'), ('2', 'GND', 'GND'), ('3', '~{MR}', 'MR_N'),
                                   ('5', 'SENSE', '+3V3'), ('6', 'VDD', '+3V3')])
    db['pintype']['U601.1'] = 'OUT'
    add(db, 'R1', '10k', [('1', '', 'RAW_N'), ('2', '', '+3V3')])
    if chain == 'clear':
        add(db, 'U981', 'SN74HCS74', [('1', '~{1CLR}', 'RAW_N'), ('14', 'VCC', '+3V3'), ('7', 'GND', 'GND')])
        db['pintype']['U981.1'] = 'IN'
    else:
        add(db, 'U604', 'SN74LVC3G17', [('3', '2A', 'RAW_N'), ('5', '2Y', 'BUF'), ('8', 'VCC', '+3V3'), ('4', 'GND', 'GND')])
        add(db, 'U605', 'SN74LVC07A', [('3', '2A', 'BUF'), ('4', '2Y', 'OUT_NET'), ('14', 'VCC', '+3V3'), ('7', 'GND', 'GND')])
        db['pintype'].update({'U604.3': 'IN', 'U604.5': 'OUT', 'U605.3': 'IN', 'U605.4': 'OUT'})
        add(db, 'R2', '10k', [('1', '', 'OUT_NET'), ('2', '', '+3V3')])
        if chain == 'to-mcu':
            add(db, 'U1', 'MCU', [('7', 'NRST', 'OUT_NET'), ('1', 'VDD', '+3V3'), ('2', 'GND', 'GND')])
            db['pintype']['U1.7'] = 'IN'
        elif chain == 'named':
            for table in ('nets',):
                db[table]['SW_RESET_N'] = db[table].pop('OUT_NET')
            for node in db['nets']['SW_RESET_N']:
                db['pin2net'][node] = 'SW_RESET_N'
    return db


def test_flipflop_clear_counts_as_a_reset_input():
    assert not _rows(_reset('clear'), 'RST-A06')


def test_reset_through_buffer_and_open_drain_driver_reaches_the_reset_input():
    assert not _rows(_reset('to-mcu'), 'RST-A06')


def test_reset_buffered_onto_a_named_reset_net_leaving_the_drawing_is_info():
    assert _kinds(_rows(_reset('named'), 'RST-A06')) == ['INFO']


def test_buffered_reset_onto_an_ordinary_net_is_still_a_candidate():
    assert _kinds(_rows(_reset('plain'), 'RST-A06')) == ['CANDIDATE']


# 1.4/1.5 NET-A07 and RST-A04: TPS2663 MODE open = latch (SLVSE94G p8), SHDN open-circuit 2.48 V min > 2 V rising max (p7)
TPS2663_TEXT = """\
 V(SHDN)               Open circuit voltage                       I(SHDN) = 0.1 µA                              2.48      2.7      3.3     V
                       SHDN threshold voltage for low IQ
 V(SHUTF)                                                                                                        0.8                       V
 V(SHUTR)              SHDN threshold rising                                                                                        2      V
–40°C ≤ TA = TJ ≤ +125°C, V(SHDN) = 2 V, R(ILIM) = 30 kΩ, IMON = PGOOD = FLT = OPEN, C(dVdT) = OPEN
    MODE_SEL               Mode selection          MODE = Open                                               Latch
"""


def _efuse(tmp_path, text=TPS2663_TEXT):
    db = empty()
    add(db, 'U901', 'TPS26630RGER', [('1', 'IN', 'VIN'), ('17', 'OUT', 'VOUT'), ('8', 'GND', 'GND'),
                                     ('11', 'MODE', 'unconnected-(U901-MODE-Pad11)'),
                                     ('12', '~{SHDN}', 'unconnected-(U901-~{SHDN}-Pad12)'),
                                     ('15', 'PGTH', 'unconnected-(U901-PGTH-Pad15)')])
    db['pintype'].update({'U901.11': 'IN', 'U901.12': 'IN', 'U901.15': 'IN'})
    db['no_connect_nodes'] = ['U901.11', 'U901.12', 'U901.15']
    path = tmp_path / 'TI - TPS2663.txt'
    path.write_text(text, encoding='utf-8')
    audit = {'materials': [{'refdes': ['U901'], 'status': 'AVAILABLE',
                            'document': {'identity_verified': True, 'path': str(path), 'document_version': 'TI - TPS2663'}}]}
    return db, audit


def test_open_input_clause_reads_mode_and_open_circuit_voltage(tmp_path):
    _, audit = _efuse(tmp_path)
    path = audit['materials'][0]['document']['path']
    assert 'MODE = Open Latch' in datasheet_kinds.open_input_clause(path, ('MODE',))
    assert '2.48 V 高于上升门限最大 2 V' in datasheet_kinds.open_input_clause(path, ('~{SHDN}', 'SHDN'))
    assert datasheet_kinds.open_input_clause(path, ('PGTH',)) is None
    assert datasheet_kinds.open_input_clause(path, ('FLT',)) is None          # a test-condition header is no permission


def test_open_circuit_voltage_below_the_threshold_is_no_permission(tmp_path):
    _, audit = _efuse(tmp_path, TPS2663_TEXT.replace('2.48      2.7      3.3', '1.48      1.7      2.3'))
    assert datasheet_kinds.open_input_clause(audit['materials'][0]['document']['path'], ('SHDN',)) is None


def test_floating_inputs_the_datasheet_defines_are_info(tmp_path):
    db, audit = _efuse(tmp_path)
    rows = {f['detail'].split(':')[0].split(' ')[0]: f['kind'] for f in _rows(db, 'NET-A07', None, audit)}
    assert rows == {'U901.11': 'INFO', 'U901.12': 'INFO', 'U901.15': 'CANDIDATE'}
    assert _kinds(_rows(db, 'NET-A07')) == ['CANDIDATE'] * 3                  # without the verified datasheet


def test_user_confirmed_open_pin_is_info(tmp_path):
    db, _ = _efuse(tmp_path)
    intent = {'open_pins': [{'node': 'U901.15', 'state': 'PGTH 开路不用', 'citation': 'Q-09 用户 2026-11-03 确认'}]}
    row = next(f for f in _rows(db, 'NET-A07', intent) if f['detail'].startswith('U901.15'))
    assert row['kind'] == 'INFO' and 'Q-09' in row['detail']


def test_open_pins_and_boundary_nets_are_validated(tmp_path):
    db, _ = _efuse(tmp_path)
    good = {'open_pins': [{'node': 'U901.11', 'state': 'MODE 开路＝锁存', 'citation': 'Q-09'}],
            'boundary_nets': [{'net': 'VOUT', 'to': 'MCU 板', 'contract': '接口表.md'}]}
    assert plan_review.declared_list_errors(good, db) == []
    bad = {'open_pins': [{'node': 'U9.1', 'state': 'x', 'citation': 'y'}, {'node': 'U901.11', 'state': ''}],
           'boundary_nets': [{'net': 'NOPE', 'to': 'x', 'contract': 'y'}]}
    errors = plan_review.declared_list_errors(bad, db)
    assert len(errors) == 3 and any('U9.1' in e for e in errors) and any('NOPE' in e for e in errors)


def test_open_enable_with_datasheet_open_state_is_info(tmp_path):
    db, audit = _efuse(tmp_path)
    add(db, 'C1', '10u', [('1', '', 'VOUT'), ('2', '', 'GND')])
    rows = _rows(db, 'RST-A04', None, audit)
    assert _kinds(rows) == ['INFO'] and '2.48' in rows[0]['detail']
    assert _kinds(_rows(db, 'RST-A04')) == ['CANDIDATE']


# 1.6 PWR-A06: a wired-out PG/PGD/PGOOD pin watches its own device's output rail
def _monitored(pg_net):
    db = empty()
    add(db, 'U601', 'TPS3808G33', [('1', '~{RESET}', 'RST_N'), ('2', 'GND', 'GND'), ('5', 'SENSE', '+3V3'),
                                   ('6', 'VDD', '+3V3'), ('3', '~{MR}', 'MR_N')])
    db['pintype']['U601.1'] = 'OUT'
    add(db, 'U1', 'MCU', [('1', 'VDD', '+3V3'), ('2', 'GND', 'GND'), ('3', 'NRST', 'RST_N'), ('4', 'GPIO', 'BUS_PG')])
    add(db, 'U301', 'LM5069', [('2', 'VIN', 'VIN_P'), ('9', 'OUT', '24V_BUS'), ('8', 'PGD', pg_net), ('5', 'GND', 'GND')])
    add(db, 'U401', 'LMR60430', [('1', 'VIN', '24V_BUS'), ('3', 'SW', 'SW'), ('6', 'FB', '+3V3'), ('2', 'PGND', 'GND')])
    add(db, 'L1', '4u7', [('1', '', 'SW'), ('2', '', '+3V3')])
    add(db, 'U2', 'LOAD', [('1', 'VCC', '24V_BUS'), ('2', 'GND', 'GND')])
    add(db, 'J1', 'CONN', [('1', '', 'VIN_P'), ('2', '', 'GND')])
    add(db, 'R1', '10k', [('1', '', 'BUS_PG'), ('2', '', '+3V3')])
    return db


def _rails(db):
    from checkers.supervision import build_inventory
    return {r['net']: r['monitor'] for s in build_inventory(db)['states'] for r in s.get('rails', [])}


def test_power_good_pin_wired_out_monitors_its_output_rail():
    assert _rails(_monitored('BUS_PG'))['24V_BUS'] == 'power-good:U301'


def test_power_good_pin_left_open_monitors_nothing():
    assert _rails(_monitored('unconnected-(U301-PGD-Pad8)'))['24V_BUS'] is None


# 2.3 NET-A08: nets declared to leave the design need a global or hierarchical label
ROOT = ('(kicad_sch (sheet (property "Sheetname" "CH1") (property "Sheetfile" "ch1.kicad_sch"))'
        ' (text "MCU 接口网络（EN_N*、CLR_REQ1～2、复位输出等）另一端在综合控制板 MCU 页，见 设计资料/MCU接口.md" (at 1 1 0)))')


def _boundary(tmp_path, sub='(kicad_sch (label "EN_N1"))', table=None):
    db = empty()
    add(db, 'U902', 'SN74HCS02', [('2', '1A', '/CH1/EN_N1'), ('3', '1B', '/CH1/CLR_REQ2'), ('4', '2A', 'GLOBAL_OK'),
                                  ('5', '2B', '/CH1/LOCAL_ONLY'), ('6', '3A', '/CH1/FLT1')])
    add(db, 'R1', '10k', [('1', '', '/CH1/EN_N1'), ('2', '', '+3V3')])
    (tmp_path / 'sch').mkdir()
    (tmp_path / 'sch' / 'root.kicad_sch').write_text(ROOT, encoding='utf-8')
    (tmp_path / 'sch' / 'ch1.kicad_sch').write_text(sub, encoding='utf-8')
    if table:
        (tmp_path / '设计资料').mkdir()
        (tmp_path / '设计资料' / 'MCU接口.md').write_text(table, encoding='utf-8')
    db['export_meta'] = {'source': str(tmp_path / 'sch' / 'root.kicad_sch')}
    return db


def _named(rows):
    return sorted(n for f in rows for n in f['detail'].split('：', 1)[1].split(' 按 ')[0].split('、'))


def test_root_note_declares_wildcard_and_range_nets(tmp_path):
    rows = _rows(_boundary(tmp_path), 'NET-A08')
    assert _kinds(rows) == ['FINDING'] and _named(rows) == ['CLR_REQ2', 'EN_N1']


def test_interface_table_named_by_the_note_adds_its_nets(tmp_path):
    rows = _rows(_boundary(tmp_path, table='| 网络 | 说明 |\n|---|---|\n| FLT1～2 | 开漏 |\n'), 'NET-A08')
    assert _named(rows) == ['CLR_REQ2', 'EN_N1', 'FLT1']


def test_hierarchical_label_or_global_name_is_declared_enough(tmp_path):
    rows = _rows(_boundary(tmp_path, sub='(kicad_sch (hierarchical_label "EN_N1"))'), 'NET-A08')
    assert _named(rows) == ['CLR_REQ2']


def test_boundary_nets_declaration_without_a_schematic(tmp_path):
    db = _boundary(tmp_path)
    db['export_meta'] = {}
    intent = {'boundary_nets': [{'net': 'LOCAL_ONLY', 'to': 'MCU 板', 'contract': '接口表.md'},
                                {'net': 'GLOBAL_OK', 'to': 'MCU 板', 'contract': '接口表.md'}]}
    assert _named(_rows(db, 'NET-A08', intent)) == ['LOCAL_ONLY']
    assert not _rows(db, 'NET-A08')


# 2.4 DEV-D01: every footprint empty is a delivery-standard finding, not an electrical one
def test_all_footprints_empty_is_one_finding():
    db = _monitored('BUS_PG')
    for part in db['parts'].values():
        part['jedec'] = ''
    rows = _rows(db, 'DEV-D01')
    assert _kinds(rows) == ['FINDING'] and '不是电气缺陷' in rows[0]['detail']
    db['parts']['U1']['jedec'] = 'Package_QFP:LQFP-48'
    assert not _rows(db, 'DEV-D01')

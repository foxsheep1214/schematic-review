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
    assert guideline_criteria.load(guideline_criteria.BUNDLE_PATH)['library_version'] == '1.7.2'


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

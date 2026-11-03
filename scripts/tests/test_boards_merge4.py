"""Boards merge 4 (2026-11-02): systematic false alarms and missed questions left after the 86-board run."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from checkers import passive_stress
import test_passive_stress as tps


# 1. Fractional power ratings (pslab: "1/16W 5%" read as 16 W, a false PASS).
def test_fractional_power_rating_is_one_token():
    assert passive_stress.bom_ratings({'Description': '1/16W 5%'}) == {'power_w': 0.0625}
    assert passive_stress.bom_ratings({'Spec': '1/10 W'}) == {'power_w': 0.1}
    assert passive_stress.bom_ratings({'Spec': '10V 1/8W'}) == {'voltage_v': 10.0, 'power_w': 0.125}
    assert passive_stress.bom_ratings({'Spec': '100k/1/4W'}) == {'power_w': 0.25}
    assert passive_stress.bom_ratings({'Spec': '2W'}) == {'power_w': 2.0}


def test_half_read_fraction_is_unknown_not_a_floor():
    for text in ('0.1/16W', '1/0W'):
        ratings = passive_stress.bom_ratings({'Spec': text})
        assert ratings == {'power_unread': True}


def test_one_sixteenth_watt_does_not_pass_half_a_watt():
    helper = tps.ProposalTests()
    db, intent = helper.unpackaged(r1='22R', c1='100n')   # 3.465^2 / 20.9 ohm = 0.57 W
    db['bom'] = {'parts': {'R1': {'Description': '1/16W 5%'}}}
    _, rows = tps.proposals(db, intent)
    calc = rows['R1']['proposal']['calculation']
    assert calc['p_floor_w'] == 0.0625 and rows['R1']['proposal']['result'] is None
    db['bom'] = {'parts': {'R1': {'Description': '0.1/16W 5%'}}}
    _, rows = tps.proposals(db, intent)
    assert rows['R1']['proposal']['result'] is None
    assert '读不出' in rows['R1']['proposal']['note']

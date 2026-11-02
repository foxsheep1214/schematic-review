"""Explicit units disambiguate component prefixes; bare R330 keeps RKM semantics."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
from solve_dividers import parse_resistor
from decoupling import parse_capacitance
from checkers.passive_stress import rated_voltage,bom_ratings
from parse_kicad import parse
from test_parse_kicad import comp,net,netlist
from plan_review import build_review_plan


@pytest.mark.parametrize('raw,ohm',[('R10k',10000),('R2.2k',2200),('R_4K7',4700),('R47,5k',47500),('R330R',330)])
def test_prefixed_resistor_with_an_explicit_unit(raw,ohm):
    parsed=parse_resistor(raw)
    assert parsed['kohm']*1000==pytest.approx(ohm)
    assert parsed['method']=='component-prefix'


@pytest.mark.parametrize('raw,farad',[('C100nF',100e-9),('C_330nF',330e-9),('C4n7',4.7e-9),('C47,5uF',47.5e-6)])
def test_prefixed_capacitance_requires_a_real_unit(raw,farad):
    assert parse_capacitance(raw)==pytest.approx(farad)


def test_component_prefix_does_not_turn_ordering_codes_or_bare_numbers_into_values():
    for raw in ['C104','C1005X7R','C100nFjunk','CP2102N']:assert parse_capacitance(raw) is None
    assert parse_resistor('R330')['kohm']*1000==pytest.approx(.33)
    assert parse_resistor('R_0R001_0805')['method']=='packaged-RKM'
    assert parse_resistor('R10k_bad') is None


def style_board():
    cs=''.join(comp(f'R{i}','Device','R',v) for i,v in enumerate(['R10k','R2.2k','R100k','R330','R00'],1))
    ns=''.join(net('N'+str(i),(f'R{i}','1','','passive')) for i in range(1,6)) + net('GND',*((f'R{i}','2','','passive') for i in range(1,6)))
    return parse(netlist(cs,ns))


def test_board_style_marks_bare_prefix_rkm_ambiguity_without_choosing_a_value():
    db=style_board();part=db['parts']['R4']
    assert part['original_value']=='R330'
    assert part['value_provenance']['raw']=='R330' and part['value_provenance']['ohm'] is None
    assert part['value_provenance']['method']=='ambiguous-component-prefix'
    assert part['value_provenance']['candidates_ohm']==pytest.approx([.33,330])
    assert parse_resistor(part['value']) is None
    assert db['parts']['R5']['value']=='R00' and parse_resistor(db['parts']['R5']['value'])['kohm']==0
    plan=build_review_plan(db)
    assert any(d['code']=='RESISTOR_VALUE_AMBIGUOUS' for d in plan['diagnostics'])
    # An isolated R330 still has its standard 0.330-ohm reading.
    isolated=parse(netlist(comp('R1','Device','R','R330'),net('A',('R1','1','','passive'))+net('B',('R1','2','','passive'))))
    assert isolated['parts']['R1']['value']=='R330'


def test_european_decimal_rating_is_not_truncated_at_the_comma():
    assert rated_voltage('47uF/6,3V')==6.3
    assert rated_voltage('47uF/6,3V/10V') is None
    assert bom_ratings({'spec':'47uF/6,3V/10%'})['voltage_v']==6.3
    assert rated_voltage('47uF/16V,25V') is None

"""Real-board failure patterns, with small synthetic counterexamples."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
from solve_dividers import parse_resistor
from parse_kicad import parse
from test_parse_kicad import comp, net, netlist

@pytest.mark.parametrize('text,ohm', [('0R',0),('0R01',.01),('0R001',.001),('4K7',4700),('10R',10),('1M',1e6),('R_0R001_0805',.001),('R_0R_22.4A_0603',0),('R_4K7_0402',4700)])
def test_board_resistance(text, ohm):
    assert parse_resistor(text)['kohm'] * 1000 == pytest.approx(ohm)

@pytest.mark.parametrize('text', ['R_unknown_0402','R_0R_bad_0402','CR1206-J/-000ELF','R_0R001_9999'])
def test_unknown_resistance_stays_unknown(text):
    assert parse_resistor(text) is None

def test_native_val_and_all_fields_retained():
    xml=netlist(comp('R1','Device','R','R_0R_0402', fields='<field name="Val">0R01</field><field name="Voltage">50V</field><field name="Tolerance">1%</field><field name="MPN">X123</field>'),net('A',('R1','1','','passive'))+net('B',('R1','2','','passive')))
    part=parse(xml)['parts']['R1']
    assert part['value']=='0R01' and part['original_value']=='R_0R_0402'
    assert part['fields']=={'Val':'0R01','Voltage':'50V','Tolerance':'1%','MPN':'X123'}
    assert part['part']=='X123'
    assert part['value_provenance']=={'field':'Val','raw':'0R01','method':'literal-RKM','ohm':.01}
    unknown=parse(xml.replace('0R01','undecided'))['parts']['R1']
    assert unknown['value']=='undecided' and unknown['value_provenance']['ohm'] is None

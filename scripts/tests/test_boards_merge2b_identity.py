"""Native identities and document sections adjudicated across the board lanes."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import part_words as pw
import parse_kicad
import datasheet_kinds as dk
from audit_datasheets import _identity_for
from decoupling import Inventory


def test_population_fields_keep_their_source_and_respect_fitted_values():
    for field in ('Populate', 'Population', 'Fitted', 'Assembly', 'Stuffed'):
        evidence = parse_kicad.population_evidence({field: 'DNP'}, {})
        assert evidence == [{'source': 'field', 'field': field, 'raw': 'DNP', 'population': 'unfitted'}]
        assert not parse_kicad.population_evidence({field: 'yes'}, {})
    assert not parse_kicad.population_evidence({'DNP': 'false'}, {'exclude_from_bom': ''})
    xml = '''<export><components><comp ref="R55"><value>100K</value><libsource lib="Device" part="R"/>
    <fields><field name="Populate">DNP</field><field name="Mfgrpart">RC0201JR-07100KL</field></fields>
    </comp></components><nets><net name="GND"><node ref="R55" pin="1"/></net></nets></export>'''
    p = parse_kicad.parse(xml)['parts']['R55']
    assert p['nc'] and p['population_provenance'][0]['field'] == 'Populate'
    assert p['part'] == 'RC0201JR-07100KL'


def test_native_mpn_prevents_pmos_material_aliasing():
    for mpn in ('SIA483DJ-T1-GE3', 'YJL3401A'):
        assert _identity_for('Q1', {'value': 'PMOS', 'part': mpn, 'fields': {'MPN': mpn}}) == (mpn, 'part')
    assert _identity_for('Q1', {'value': 'PMOS', 'part': 'Q_PMOS'}) == ('PMOS', 'value')


def test_functional_symbols_outrank_labels_and_package_categories():
    for ref, part, expected in [
        ('K1', {'prim': 'e-radionica:EASYC', 'part': 'easyC'}, pw.CONNECTOR),
        ('P102', {'prim': 'tinkerforge:CONN_2', 'value': 'Relay'}, pw.CONNECTOR),
        ('H1', {'prim': 'Mechanical:MountingHole_Pad'}, pw.TESTPOINT),
        ('U2', {'prim': 'Oscillator:FT5HN', 'value': 'TCXO', 'jedec': 'Crystal:Crystal_SMD_2016'}, pw.IC),
        ('J10', {'prim': 'Connector_Generic:Conn_02x08_Counter_Clockwise', 'jedec': 'Button_Switch_SMD:SW_DIP_SPSTx08_Slide'}, pw.SWITCH),
    ]:
        assert pw.classify(ref, part, 4)[0] == expected
    assert pw.classify('K1', {'part': '?'}, 5)[0] == pw.RELAY


def test_native_passive_contacts_do_not_create_ic_decoupling_groups():
    for ref, prim in [('K1', 'vendor:EASYC'), ('J1', 'Connector:USB_B_Micro'), ('H1', 'Mechanical:MountingHole_Pad')]:
        db = {'parts': {ref: {'prim': prim, 'part': prim.split(':')[-1]}},
              'pin2net': {ref+'.1': 'VBUS', ref+'.2': 'GND'}, 'nets': {},
              'pinname': {ref+'.1': 'VBUS', ref+'.2': 'GND'}}
        assert Inventory(db, {}).groups() == []


def test_brand_and_application_words_never_become_title_kinds():
    assert dk.cues('DIODES Incorporated') == set()
    assert dk.cues('Diodes Incorporated MOSFET gate driver') == {'gate_driver'}
    assert dk.cues('Schottky diode') == {'diode'}
    text = 'XYZ123\nDIODES Incorporated\n1 Features\nPWM operation\n2 Applications\nLoad Switch\nbridge application\nTVS'
    read = lambda path, page: text if page == 1 else 'Gate driver application'
    assert dk.candidates('x', read_page=read) == []
    assert dk.kind_conflict('ic', 'x', read_page=read) is None
    text = 'XYZ\nFeatures\nPWM operation\n3 Description\nMOSFET gate driver\n4 Applications\nLoad Switch'
    assert dk.candidates('x', read_page=read)[0]['kind'] == 'gate_driver'


def test_pdf_title_geometry_ignores_footer_first_and_description_application_mechanisms(tmp_path):
    import pytest
    fitz=pytest.importorskip('fitz')
    import datasheet_kinds as dk
    p=tmp_path/'driver.pdf';doc=fitz.open();page=doc.new_page(width=612,height=792)
    # Content stream order deliberately starts with a footer, then the description, then the actual title.
    page.insert_text((40,755),'www.diodes.com DIODES Incorporated')
    page.insert_text((315,145),'Designed for PWM control and synchronous rectification.')
    page.insert_text((400,90),'DC Motor Driver',fontsize=18)
    page.insert_text((315,128),'DESCRIPTION',fontsize=12)
    page.insert_text((54,128),'FEATURES',fontsize=12)
    page.insert_text((54,180),'Load Switch application')
    doc.save(p);doc.close()
    assert dk.cues(dk.title_text(str(p)))=={'motor_driver'}
    assert dk.candidates(str(p))[0]['kind']=='motor_driver'

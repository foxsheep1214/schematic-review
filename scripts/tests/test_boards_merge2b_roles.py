"""Pin-policy, passive contact and actual gate-source regressions from board adjudications."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import part_words as pw
from lint import Lint
from test_inductive_load import add
from test_power_up import rail_board, regulators_of
from checkers import power_up, power_switch, diff_levels, inductive_load
from plan_review import build_review_plan


def empty():
    return {'parts': {}, 'nets': {}, 'pin2net': {}, 'pinname': {}, 'pintype': {}, 'pseudo_nets': [], 'ref2page': {}}


def test_numbered_relay_contacts_require_one_matching_channel_triple():
    db = empty()
    add(db, 'K2', 'SRD_RELAY_5V', [('1','A1','VCC'),('2','A2','COIL'),('3','','NO1'),('4','','COM1'),('5','','NC1')])
    add(db, 'K4', 'TERMINAL_KF235-5.0-3P', [('1','','NC1'),('2','','COM1'),('3','','NO1')])
    assert not [f for f in Lint(db).run() if f['rule']=='NET-A04' and f['kind']=='FINDING']
    db['pin2net']['K2.4']='COM2';db['nets']['COM1'].remove('K2.4');db['nets']['COM2']=['K2.4']
    assert [f for f in Lint(db).run() if f['rule']=='NET-A04' and f['kind']=='FINDING']


def test_unused_pin_permission_is_bound_to_model_pin_function_and_no_load():
    db = empty();add(db,'U4','CH340C',[('9','~{CTS}','unconnected-(U4-CTS-Pad9)')]);db['pintype']['U4.9']='IN'
    assert 'p4' in pw.unused_input_permission(db,'U4.9')
    assert not [f for f in Lint(db).run() if f['rule'] in ('NET-A01','NET-A06','NET-A07') and f['kind']!='INFO']
    db['parts']['U4']['part']='CH340X'
    assert not pw.unused_input_permission(db,'U4.9')
    assert any(f['rule']=='NET-A07' and f['kind']!='INFO' for f in Lint(db).run())
    db['parts']['U4']['part']='CH340C';add(db,'U1','MCU',[('1','RX','unconnected-(U4-CTS-Pad9)')]);db['pintype']['U1.1']='IN'
    assert not pw.unused_input_permission(db,'U4.9')
    assert any(f['rule']=='NET-A06' for f in Lint(db).run())


def test_mechanical_nc_pad_has_no_logic_input_obligation():
    db=empty();add(db,'H1','MountingHole_Pad',[('1','','OPEN')]);db['parts']['H1']['prim']='Mechanical:MountingHole_Pad';db['pintype']['H1.1']='IN'
    db['pseudo_nets']=['OPEN'];db['no_connect_nodes']=['H1.1']
    assert not [f for f in Lint(db).run() if f['rule']=='NET-A07']
    db['parts']['H1']['prim']='IC';db['parts']['H1']['part']='MCU'
    assert [f for f in Lint(db).run() if f['rule']=='NET-A07']


def test_enable_policies_do_not_turn_load_switches_into_ldos():
    db=rail_board(enable=None);db['parts']['U1']['part']='TPS70933DBVR';db['pinname']['U1.2']='NC'
    # Actual package EN is pin 3, so a mismatched pin table cannot authorize the input.
    assert not pw.unused_input_permission(db,'U1.2')
    db=empty();add(db,'U1','TPS70933DBVR',[('1','IN','VIN'),('2','GND','GND'),('3','EN','OPEN'),('5','OUT','VOUT')])
    item=regulators_of(power_up.build_inventory(db))['U1'];assert item['enable_source']=='internal-bias'
    assert not [f for f in Lint(db).run() if f['rule']=='RST-A04']
    for model in ('MIC94164','TPS27S100APWPR'):
        db=rail_board(enable='gpio');db['parts']['U1']['part']=model
        assert regulators_of(power_up.build_inventory(db))['U1']['kind']=='load-switch'
        plan=build_review_plan(db)
        assert not [c for c in plan['checks'] if c['rule']=='PWR-E02' and c['object'].get('ref')=='U1']


def test_ground_test_contacts_do_not_supply_the_gate_through_its_pulldown():
    db=empty();add(db,'Q1','2N7002',[('1','G','GATE'),('2','S','GND'),('3','D','LOAD')]);add(db,'R1','100k',[('1','','GATE'),('2','','GND')]);add(db,'J1','CONN_01X01',[('1','','GND')])
    state={'id':'built','fitted':list(db['parts']),'gaps':[]}
    scan=power_switch._Scan(db,state,{},set())
    assert not scan.drivers('GATE')
    add(db,'R2','33',[('1','','GATE'),('2','','DRV')]);add(db,'U1','DRIVER',[('1','OUT','DRV'),('2','GND','GND')])
    scan=power_switch._Scan(db,dict(state,fitted=list(db['parts'])),{},set())
    assert any(d['node']=='U1.1' and d['via']=='series:R2' for d in scan.drivers('GATE'))


def test_power_pairs_and_differential_shunts_are_not_ac_coupling():
    db=empty();add(db,'U1','RECTIFIER_MODULE',[('1','V+','V+'),('2','V-','V-')]);add(db,'J1','CONN_01X02',[('1','','V+'),('2','','V-')])
    assert not diff_levels.build_inventory(db)['states'][0]['pairs']
    db=empty();add(db,'U1','LVDS',[('1','OUTP','DP'),('2','OUTN','DN')]);add(db,'J1','CONN_01X02',[('1','','DP'),('2','','DN')]);add(db,'C62','100p',[('1','','DP'),('2','','DN')])
    pair=diff_levels.build_inventory(db)['states'][0]['pairs'][0]
    assert pair['coupling']=='dc' and all(not leg['series_caps'] for leg in pair['legs'])


def test_rf_balun_is_not_a_power_coil():
    db=empty();add(db,'T1','BALUN_2450FB15A050',[(str(i),'',str(i)) for i in range(1,7)])
    assert not inductive_load.build_inventory(db)['states'][0]['loads']


def test_manufacturer_package_is_not_a_diode_and_fb_value_is_a_bead():
    assert pw.classify('U3', {'part':'PI3USB102GZLEX','prim':'usb:TC7USB42MU','jedec':'mainboard:Diodes_10-TQFN_ZL'}, 10)[0]==pw.IC
    assert pw.classify('L101', {'value':'FB','prim':'vendor:L'}, 2)[0]==pw.FERRITE
    assert pw.classify('U1', {'value':'FB'}, 8)[0]==pw.IC
    assert 'VO' in pw.pin_aliases('+Vo','7')


def test_upstream_buck_output_inductor_is_not_the_downstream_input_filter():
    from checkers import input_filter
    db=empty();add(db,'U1','BUCK',[('1','VIN','VIN'),('2','SW','SW1')]);add(db,'L1','10uH',[('1','','SW1'),('2','','V5')]);add(db,'U2','BUCK',[('1','VIN','V5'),('2','SW','SW2')])
    inv=input_filter.build_inventory(db)
    downstream=next(x for x in inv['states'][0]['converters'] if x['ref']=='U2')
    assert downstream['series_elements']==[]
    add(db,'L2','FB',[('1','','V5'),('2','','PORT')])
    inv=input_filter.build_inventory(db)
    downstream=next(x for x in inv['states'][0]['converters'] if x['ref']=='U2')
    assert [x['ref'] for x in downstream['series_elements']]==['L2']

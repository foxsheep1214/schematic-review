"""Every physical external signal/power branch and ADC/regulator output remains reviewable."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import catalog
import interfaces
from plan_review import build_review_plan
from plan_circuits import subject_precondition
from checkers.netgraph import NetGraph
from test_inductive_load import add
from test_boards_merge2b_roles import empty


def checks(db, rule):
    return [c for c in build_review_plan(db)['checks'] if c['rule']==rule]


def test_external_signals_are_asked_even_without_a_known_peer_supply_or_owners():
    db=empty();add(db,'U1','MCU',[('1','VDD','+3V3'),('2','GND','GND'),('3','GPIO1','SIG')]);add(db,'J1','CONN_01X03',[('1','','SIG'),('2','','+3V3'),('3','','GND')])
    plan=build_review_plan(db)
    rows=[c for c in plan['checks'] if c['rule']=='SIG-C08' and c['object'].get('interface')=='EXT-J1']
    assert len(rows)==1 and rows[0]['object']['net']=='SIG' and rows[0]['object']['nodes']==['J1.1']
    assert '对端供电未知' in rows[0]['question']
    assert rows[0]['readiness']=='WAITING_EVIDENCE'
    assert not interfaces.coverage_errors(plan)
    plan['checks'].remove(rows[0]);assert any('SIG-C08' in e for e in interfaces.coverage_errors(plan))


def test_every_unprotected_external_power_pin_gets_its_branch_question():
    db=empty();add(db,'J1','CONN_01X03',[('1','VIN','V12'),('2','VOUT','V5'),('3','GND','GND')]);add(db,'U1','LDO',[('1','VIN','V12'),('2','OUT','V5'),('3','GND','GND')])
    rows=[r for r in checks(db,'PRO-C04') if r['object'].get('interface')=='EXT-J1']
    assert {r['object'].get('node') for r in rows}=={'J1.1','J1.2'}
    assert all('上游' in r['question'] for r in rows)


def test_relay_coil_distribution_keeps_four_separate_branch_questions():
    db=empty();add(db,'K1','vendor:EASYC',[('1','VIN','VCC'),('2','GND','GND')])
    for i in range(1,5):
        add(db,'R'+str(i),'10',[('1','','VCC'),('2','','COILV'+str(i))])
        add(db,'K'+str(i+1),'RELAY',[('1','A1','COILV'+str(i)),('2','A2','COILSW'+str(i))])
    rows=[r for r in checks(db,'PRO-C04') if r['object'].get('source_node')=='K1.1']
    assert {r['object']['ref'] for r in rows}=={'R1','R2','R3','R4'}


def test_usb_owned_fuse_still_gets_protection_coordination():
    db=empty();add(db,'J1','USB_C_Receptacle',[('1','VBUS','PORT_POWER'),('2','CC1','CC1'),('3','CC2','CC2'),('4','GND','GND')]);add(db,'F1','FUSE',[('1','','PORT_POWER'),('2','','VIN')]);add(db,'U1','LDO',[('1','VIN','VIN'),('2','OUT','+3V3'),('3','GND','GND')])
    plan=build_review_plan(db)
    for rule in ('PRO-C01','PRO-C05'):
        assert any(r['rule']==rule and r['object'].get('ref')=='F1' for r in plan['checks'])
    assert any(r['rule']=='PRO-C04' and r['object'].get('node')=='J1.1' for r in plan['checks'])
    assert not any(r['rule']=='SIG-C08' and r['object'].get('net')=='PORT_POWER' for r in plan['checks'])


def test_adc_and_fuel_gauge_sense_pins_get_individual_input_protection_questions():
    db=empty();add(db,'U1','MCU',[('1','PA0/ADC1_IN0','SENSE'),('2','VDD','VCC'),('3','GND','GND')]);add(db,'U2','BQ27441',[('1','BAT','BAT'),('7','SRN','LOAD'),('8','SRP','BAT'),('3','VSS','GND')])
    rows=checks(db,'ANA-C03')
    assert {'U1.1','U2.1','U2.7','U2.8'} <= {r['object'].get('node') for r in rows}
    for ref in ('U1','U2'):
        found,_=subject_precondition(NetGraph(db),db['pinname'],'ANALOG_PIN',[ref],[])
        assert ref in found


def test_pmic_ldo_and_mux_outputs_are_individually_asked():
    db=empty();add(db,'U4','BD71847AMWV',[('1','VIN','VIN'),('4','LDO5_VOUT','V1V8'),('55','MUXSW_VOUT','VSD'),('3','GND','GND')])
    rows=checks(db,'PWR-C04')
    assert {'U4.4','U4.55'} <= {r['object'].get('node') for r in rows}


def test_type_a_and_micro_b_do_not_acquire_cc_questions_but_type_c_keeps_them():
    for family, expected in [('USB_A',False),('USB_B_Micro',False),('MICRO-B_USB',False),('USB_C_Receptacle_USB2.0',True)]:
        db=empty();add(db,'J4',family,[('1','VBUS','VBUS'),('2','D+','DP'),('3','D-','DN'),('4','GND','GND')])
        found,unread=subject_precondition(NetGraph(db),db['pinname'],'USB_CC',['J4'],[])
        assert bool(found or unread)==expected
        intent={'schema_version':5,'circuits':[{'id':'PORT','type':'USB','refs':['J4'],'states':['attached'],'citation':'synthetic connector p1'}]}
        plan=build_review_plan(db,intent)
        assert any(c['rule']=='SIG-D04' for c in plan['checks'])==expected


def test_clock_preconditions_distinguish_tcxo_passive_crystal_and_rtc():
    db=empty();add(db,'U2','TCXO',[('1','VCC','VCC'),('2','GND','GND'),('3','OUT','CLK')]);db['parts']['U2']['prim']='Oscillator:FT5HN'
    assert subject_precondition(NetGraph(db),db['pinname'],'PASSIVE_CRYSTAL',['U2'],[])==([],[])
    assert subject_precondition(NetGraph(db),db['pinname'],'RTC_BACKUP',['U2'],[])==([],[])
    add(db,'Y1','Crystal',[('1','','XI'),('2','','XO')]);assert subject_precondition(NetGraph(db),db['pinname'],'PASSIVE_CRYSTAL',['Y1'],[])[0]==['Y1']


def test_i2s_sda_and_io_bank_power_do_not_create_i2c_regions():
    from i2c_topology import Inventory
    from board_scans import _is_i2c_net
    db=empty();add(db,'U1','CODEC',[('1','SDA','I2S_SDA'),('2','NVCC_I2C','VIO')]);add(db,'U2','CPU',[('1','SDA','I2S_SDA')])
    assert not _is_i2c_net('I2S_SDA')
    assert not Inventory(db,{'rails':{'VIO':'native power'}}).seeds()[0]
    assert not any(c['object'].get('net')=='I2S_SDA' for c in checks(db,'SIG-E01'))


def test_actual_soldered_connector_symbol_spellings_are_passive():
    import part_words as pw
    for name in ('easyC-SMD','NOVA_programmer_header'):
        assert pw.classify('K2',{'part':name,'value':name,'prim':'e-radionica.com schematics:'+name},4)[0]==pw.CONNECTOR
    assert pw.usb_connector_type({'part':'U262-161N-4BVC11'})=='Type-C'


def test_source_trace_uses_exact_feedthrough_and_common_cathode_maps():
    from checkers.powertree import PowerTree
    db=empty();add(db,'U1','REG',[('1','VIN','VIN'),('2','VOUT','V5')]);add(db,'EMI1','C_Feedthrough',[('1','1','V5'),('2','2','FILTERED'),('3','3','GND')]);db['parts']['EMI1']['prim']='Amiga-Library:C_Feedthrough'
    add(db,'D1','BAT54C',[('1','','FILTERED'),('2','','BACKUP'),('3','','CLKVCC')]);add(db,'U2','RTC',[('1','VDD','CLKVCC')])
    tree=PowerTree(NetGraph(db));trace=tree.source_of('CLKVCC')
    assert trace['source']=='U1.2' and trace['path']==['EMI1','D1']
    assert tree.source_of('BACKUP') is None and tree.source_of('GND') is None
    db['parts']['D1']['part']='BAT54A';assert PowerTree(NetGraph(db)).source_of('CLKVCC') is None
    db['parts']['D1']['part']='BAT54C';db['parts']['EMI1']['prim']='Device:C'
    assert PowerTree(NetGraph(db)).source_of('CLKVCC') is None


def test_tps5430_ph_is_an_actual_output_even_with_a_wrong_library_direction():
    from checkers.powertree import PowerTree
    db=empty();add(db,'U3','TPS5430DDAR',[('7','VIN','VIN'),('8','PH','PH'),('6','GND','GND')]);db['native_pintype']={'U3.8':'power_in'}
    assert PowerTree(NetGraph(db)).source_of('PH')['source']=='U3.8'
    db['parts']['U3']['part']='UNCONFIRMED'
    assert PowerTree(NetGraph(db)).source_of('PH') is None


def test_integrated_rj45_rectifier_power_is_not_data_but_mdi_pairs_remain():
    from checkers import diff_levels
    db=empty();add(db,'U1','HY931147C',[('P$9','','V+'),('P$10','','V-'),('P$1','','RD_P'),('P$2','','RD_N')]);add(db,'J3','CONN_01X04',[('1','','V+'),('2','','V-'),('3','','RD_P'),('4','','RD_N')])
    pairs=diff_levels.build_inventory(db)['states'][0]['pairs']
    assert len(pairs)==1 and pairs[0]['legs'][0]['net']=='RD_P'


def test_native_connector_pin_map_does_not_reintroduce_ic_bypass_obligations():
    from decoupling import Inventory
    db=empty();add(db,'K4','easyC-SMD',[('1','VCC','VCC'),('2','GND','GND'),('3','SDA','SDA'),('4','SCL','SCL')])
    devices={'K4':{'citation':'native connector drawing p1', 'pins':{'1':{'role':'power'},'2':{'role':'return'},'3':{'role':'other'},'4':{'role':'other'}}}}
    assert Inventory(db,{},devices).groups()==[]
    groups=Inventory(db,{'groups':[{'ref':'K4','net':'VCC','citation':'explicit port bulk-capacitor contract p1'}]},devices).groups()
    assert len(groups)==1 and groups[0]['ref']=='K4'


def test_regulator_output_group_binding_does_not_take_over_other_pwr_c04_rows():
    from checkers.decoupling import DecouplingChecker
    checker=DecouplingChecker()
    assert checker.binds({'rule':'PWR-C04','object':{'decoupling_group':'U1:VOUT'}})
    assert not checker.binds({'rule':'PWR-C04','object':{'circuit':'BUCK','ref':'U1'}})


def test_module_ext_adc_function_qualifies_but_adc_supply_pins_do_not():
    db=empty();add(db,'U1','Connector:Conn_01x04',[('73','EXT_ADC3','MEAS'),('1','ADC_VDD','VCC')]);db['native_pintype']={'U1.1':'power_in'}
    rows=checks(db,'ANA-C03');assert 'U1.73' in {r['object'].get('node') for r in rows}
    assert 'U1.1' not in {r['object'].get('node') for r in rows}
    assert subject_precondition(NetGraph(db),db['pinname'],'ANALOG_PIN',['U1'],[])[0]==['U1']


def test_gpio_divider_in_a_declared_analog_circuit_keeps_its_unconfirmed_mux_dependency():
    db=empty();add(db,'U1','MCU',[('1','PA4','MEAS'),('2','VDD','VCC'),('3','GND','GND')]);add(db,'R1','100k',[('1','','V12'),('2','','MEAS')]);add(db,'R2','10k',[('1','','MEAS'),('2','','GND')])
    intent={'schema_version':5,'circuits':[{'id':'ADC','type':'ANALOG','refs':['U1','R1','R2'],'states':['run'],'citation':'synthetic ADC path p1'}]}
    rows=[r for r in build_review_plan(db,intent)['checks'] if r['rule']=='ANA-C03' and r['object'].get('node')=='U1.1']
    assert len(rows)==1 and '是否作 ADC' in rows[0]['question'] and any('复用能力' in g for g in rows[0]['required_inputs'])


def test_parallel_vbus_contacts_do_not_duplicate_the_fuse_coordination_object():
    db=empty();add(db,'J1','USB_C_Receptacle',[('A4','VBUS','PORT'),('B4','VBUS','PORT'),('A5','CC1','CC1'),('B5','CC2','CC2')]);add(db,'F1','FUSE',[('1','','PORT'),('2','','VIN')]);add(db,'U1','REG',[('1','VIN','VIN'),('2','OUT','V3V3')])
    plan=build_review_plan(db)
    rows=[r for r in plan['checks'] if r['rule'] in ('PRO-C01','PRO-C05') and r['object'].get('interface')=='EXT-J1']
    assert len(rows)==2
    injection=[r for r in plan['checks'] if r['rule']=='SIG-C08' and r['object'].get('interface')=='EXT-J1']
    assert len({r['aspect'] for r in injection})==len(injection)

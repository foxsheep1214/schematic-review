"""The scan fixes found while adding five boards to the typical-circuit bench (typical-circuits-v3, 2026-10-26).

suntastic feeds a load switch through a three-way solder jumper (common C, choices A/B); the feed trace passed only
two-terminal parts, so the supply pin was reported unfed instead of fed through a jumper. usb-pd-power-manager names a
load switch's gate and source nets VLDO_VIN2_EN_G / _S, and rt-ihu writes CAN receive and transmit as DCAN1RX / DCAN1TX
inside one word; both read as a split net name. rt-ihu feeds a PA's VCC1 through an RF choke whose library pins are
typed input, which read as a net of inputs only.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lint import Lint, net_name_split
from test_electrical_safety import database


def found(db, rule):
    return [x for x in Lint(db).run() if x['rule'] == rule]


class ThreeWayJumperTests(unittest.TestCase):
    def test_a_supply_pin_behind_a_three_way_jumper_is_fed_through_it(self):
        db = database({'+5V': ['J1.1', 'JP1.1'], 'VBAK': ['JP1.3', 'C1.1'], 'SEL': ['JP1.2', 'U1.1'],
                       'GND': ['J1.2', 'U1.2', 'C1.2']},
                      {'J1': 'CONN', 'JP1': 'SolderJumper_3_Open', 'U1': 'TPS22917', 'C1': '100u'},
                      {'U1.1': 'VDD', 'U1.2': 'GND', 'JP1.1': 'A', 'JP1.2': 'C', 'JP1.3': 'B'})
        db['parts']['JP1']['prim'] = 'Jumper:SolderJumper_3_Open'
        rows = found(db, 'PWR-A02')
        self.assertEqual([x['kind'] for x in rows], ['CANDIDATE'], rows)
        self.assertIn('经跳线 JP1 才接到供电', rows[0]['detail'])


class NetNamePairTests(unittest.TestCase):
    def test_one_transistors_terminals_are_no_split(self):
        self.assertFalse(net_name_split('/VLDO_VIN2_EN_G', '/VLDO_VIN2_EN_S'))
        self.assertFalse(net_name_split('Q4_B', 'Q4_E'))

    def test_a_receive_transmit_pair_inside_one_word_is_no_split(self):
        self.assertFalse(net_name_split('PRI_DCAN1RX', 'PRI_DCAN1TX'))
        self.assertFalse(net_name_split('UART2MISO', 'UART2MOSI'))

    def test_a_real_spelling_split_still_reads_as_one(self):
        self.assertTrue(net_name_split('MOTOR_ENABLE', 'MOTOR_ENABEL'))


class InputOnlyNetTests(unittest.TestCase):
    def test_a_choke_typed_input_feeds_the_net(self):
        db = database({'PA_VCC': ['L1.1', 'U1.11'], 'RAIL': ['L1.2', 'U2.5'], 'GND': ['U1.2', 'U2.2']},
                      {'L1': '12n', 'U1': 'PA', 'U2': 'LDO'})
        db['pintype'] = {'L1.1': 'input', 'L1.2': 'input', 'U1.11': 'input', 'U1.2': 'power_in',
                         'U2.5': 'power_out', 'U2.2': 'power_in'}
        self.assertFalse([x for x in found(db, 'NET-A06') if 'PA_VCC' in x['detail']])
        db['nets']['PA_VCC'] = ['U1.11', 'U3.1']
        db['parts']['U3'] = {'value': 'MCU', 'nc': False}
        db['pin2net'].update({'U3.1': 'PA_VCC'})
        db['pin2net'].pop('L1.1')
        db['pintype']['U3.1'] = 'input'
        self.assertTrue([x for x in found(db, 'NET-A06') if 'PA_VCC' in x['detail']])


if __name__ == '__main__':
    unittest.main()

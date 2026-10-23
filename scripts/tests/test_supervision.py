import pathlib
import sys
import tempfile
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import catalog

from checkers.supervision import SupervisionChecker, build_inventory, validate_supervision_intent
from electrical_fixtures import bound_intent
from lint import Lint
from plan_review import build_review_plan
from test_inductive_load import add


def supervised_board(wdi='driven', reset='connected', extra_rail=False, pullup=True):
    """U3 是带看门狗的监控器，复位链与喂狗来源按参数变化。"""
    db = {'nets': {}, 'parts': {}, 'pin2net': {}, 'pinname': {}, 'pintype': {},
          'pseudo_nets': [], 'ref2page': {}}
    wdi_net = {'driven': 'WDI_NET', 'floating': 'WDI_NET', 'tied': 'VCC_3V3'}[wdi]
    add(db, 'U3', 'SUPERVISOR', [('1', 'VCC', 'VCC_3V3'), ('2', 'SENSE', 'SENSE_3V3'),
                                 ('3', 'WDI', wdi_net), ('4', 'RESET', 'SYS_RST_N'),
                                 ('5', 'GND', 'GND')])
    db['pintype']['U3.4'] = 'OUT'
    add(db, 'R7', '100K', [('1', '1', 'VCC_3V3'), ('2', '2', 'SENSE_3V3')])
    add(db, 'R8', '47K', [('1', '1', 'SENSE_3V3'), ('2', '2', 'GND')])
    if pullup:
        add(db, 'R9', '10K', [('1', '1', 'SYS_RST_N'), ('2', '2', 'VCC_3V3')])
    soc = [('1', 'VDD', 'VCC_3V3'), ('3', 'GND', 'GND')]
    soc.append(('2', 'NRST', 'SYS_RST_N') if reset == 'connected' else
               ('2', 'GPIO3', 'SYS_RST_N') if reset == 'gpio-only' else ('2', 'NRST', 'OTHER_RST'))
    add(db, 'U4', 'SOC', soc)
    db['pintype']['U4.2'] = 'IN'
    if wdi == 'driven':
        add(db, 'U5', 'MCU', [('1', 'GPIO1', 'WDI_NET'), ('2', 'VDD', 'VCC_3V3'),
                              ('3', 'GND', 'GND')])
        db['pintype']['U5.1'] = 'OUT'
    if extra_rail:
        add(db, 'U6', 'FPGA', [('1', 'VDD', 'VCC_1V8'), ('2', 'GND', 'GND')])
        add(db, 'U7', 'LDO', [('1', 'VOUT', 'VCC_1V8'), ('2', 'GND', 'GND')])
    return db


def supervisors_of(inventory, state='as-built'):
    entry = next(x for x in inventory['states'] if x['id'] == state)
    return {item['ref']: item for item in entry['supervisors']}


def rails_of(inventory, state='as-built'):
    entry = next(x for x in inventory['states'] if x['id'] == state)
    return {rail['net']: rail for rail in entry['rails']}


CHECKER_RULES = {rule.id for rule in catalog.rules(source='supervision')}


def findings(db, intent=None):
    return [f for f in Lint(db, '', intent).run() if f['rule'] in CHECKER_RULES]


class RecognitionTest(unittest.TestCase):
    def test_complete_supervision_has_no_findings(self):
        db = supervised_board()
        item = supervisors_of(build_inventory(db))['U3']
        self.assertEqual(item['monitored_nets'], ['SENSE_3V3'])
        self.assertEqual(item['watchdog_inputs'][0]['state'], 'driven')
        self.assertEqual([x['role'] for x in item['reset_outputs'][0]['destinations']],
                         ['reset-input'])
        self.assertEqual(item['reset_outputs'][0]['pulls'], ['VCC_3V3'])
        self.assertEqual(findings(db), [])

    def test_floating_watchdog_input_reports_sv01(self):
        db = supervised_board(wdi='floating')
        self.assertEqual(supervisors_of(build_inventory(db))['U3']['watchdog_inputs'][0]['state'],
                         'floating')
        hits = findings(db)
        self.assertEqual([f['rule'] for f in hits], ['RST-A05'])
        self.assertEqual(hits[0]['kind'], 'CANDIDATE')

    def test_watchdog_tied_to_a_rail_reports_sv01(self):
        self.assertEqual([f['rule'] for f in findings(supervised_board(wdi='tied'))], ['RST-A05'])

    def test_dangling_reset_output_reports_sv02_finding(self):
        db = supervised_board(reset='dangling', pullup=False)
        hits = findings(db)
        self.assertEqual([f['rule'] for f in hits], ['RST-A06'])
        self.assertEqual(hits[0]['kind'], 'FINDING')
        self.assertIn('复位链在此中断', hits[0]['detail'])

    def test_reset_reaching_only_a_gpio_is_a_candidate(self):
        hits = findings(supervised_board(reset='gpio-only'))
        self.assertEqual([f['rule'] for f in hits], ['RST-A06'])
        self.assertEqual(hits[0]['kind'], 'CANDIDATE')

    def test_unmonitored_rail_reports_sv03(self):
        db = supervised_board(extra_rail=True)
        rails = rails_of(build_inventory(db))
        self.assertEqual(rails['VCC_3V3']['monitor'], 'divider')
        self.assertIsNone(rails['VCC_1V8']['monitor'])
        hits = findings(db)
        self.assertEqual([f['rule'] for f in hits], ['PWR-A06'])
        self.assertIn('VCC_1V8', hits[0]['detail'])

    def test_board_without_a_supervisor_reports_nothing(self):
        db = supervised_board()
        db['parts']['U3']['nc'] = True
        self.assertEqual(supervisors_of(build_inventory(db)), {})
        self.assertEqual(findings(db), [])

    def test_soc_reset_input_is_not_a_supervisor(self):
        db = supervised_board()
        db['parts']['U3']['nc'] = True
        self.assertNotIn('U4', supervisors_of(build_inventory(db)))


    def test_reset_input_of_a_part_with_sense_pin_is_not_a_supervisor_output(self):
        # 名称启发式审计：LED 驱动器有 SENSE 脚和 RESET 输入，曾被当作监控器报“复位链中断”。
        db = {'nets': {}, 'parts': {}, 'pin2net': {}, 'pinname': {}, 'pintype': {},
              'pseudo_nets': [], 'ref2page': {}}
        add(db, 'U8', 'LED-DRIVER', [('1', 'VIN', 'V12'), ('2', 'SENSE', 'ISNS'),
                                     ('3', 'RESET', 'LED_RST'), ('4', 'GND', 'GND')])
        add(db, 'R1', '10K', [('1', '1', 'LED_RST'), ('2', '2', 'V12')])
        db['native_pintype'] = {'U8.1': 'power_in', 'U8.2': 'input', 'U8.3': 'input', 'U8.4': 'power_in'}
        self.assertNotIn('U8', supervisors_of(build_inventory(db)))
        self.assertEqual([f['rule'] for f in findings(db) if f['rule'] == 'RST-A06'], [])

class PlanTest(unittest.TestCase):
    def test_plan_covers_reset_path_pulse_and_rail_coverage(self):
        db = supervised_board(extra_rail=True)
        plan = build_review_plan(db)
        checks = {x['id'] for x in plan['checks'] if x['object'].get('supervision')}
        self.assertEqual(checks, {'RST-T02.U3.SYS-RST-N', 'RST-E03.U3.SYS-RST-N',
                                  'PWR-T04.AS-BUILT.SUPERVISION-RAILS'})
        coverage = next(x for x in plan['checks'] if x['rule'] == 'PWR-T04')
        self.assertIn('rail-unmonitored:VCC_1V8', coverage['inventory_gaps'])
        self.assertEqual(plan['supervision_version'], 1)

    def test_rule_instances_list_the_unmonitored_rails(self):
        plan = build_review_plan(supervised_board(extra_rail=True))
        rules = {row['rule']: row for row in plan['rule_plan']}
        self.assertEqual(rules['PWR-A06']['instances'], ['VCC_1V8'])
        self.assertEqual(rules['RST-A05']['instances'], ['U3'])

    def test_stale_object_binding_is_reported(self):
        plan = build_review_plan(supervised_board())
        item = next(x for x in plan['checks'] if x['object'].get('supervision'))
        stale = dict(item['object'], supervision_digest='0' * 64)
        self.assertEqual(SupervisionChecker().object_errors('X', stale, plan['supervision']),
                         ['X: stale supervision object binding'])

    def test_intent_validation_accepts_a_sound_section(self):
        db = supervised_board()
        section = {'schema_version': 2,
                   'supervisors': [{'id': 'u3', 'ref': 'U3', 'citation': 'reset scheme'}]}
        self.assertEqual(validate_supervision_intent(bound_intent(db, {'supervision': section}), db), [])


class HotRuleTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

if __name__ == '__main__':
    unittest.main()

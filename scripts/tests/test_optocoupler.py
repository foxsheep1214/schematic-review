import pathlib
import sys
import tempfile
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import catalog

from checkers.optocoupler import OptocouplerChecker, build_inventory, internal_pullup_errors, validate_optocoupler_intent
from electrical_fixtures import bound_intent
from lint import Lint
from plan_review import build_review_plan
from test_inductive_load import add


def opto_board(led_resistor=True, pullup=True):
    """U1 驱动 PC817 的 LED，输出侧上拉到 VCC_3V3。"""
    db = {'nets': {}, 'parts': {}, 'pin2net': {}, 'pinname': {}, 'pintype': {},
          'pseudo_nets': [], 'ref2page': {}}
    anode_net = 'LED_A' if led_resistor else 'V5_ISO'
    add(db, 'OK1', 'PC817', [('1', 'ANODE', anode_net), ('2', 'CATHODE', 'OPTO_DRV'),
                             ('3', 'EMITTER', 'GND'), ('4', 'COLLECTOR', 'OPTO_OUT')])
    add(db, 'U1', 'MCU', [('1', 'GPIO2', 'OPTO_DRV'), ('2', 'VDD', 'V5_ISO'),
                          ('3', 'GND', 'GND_ISO')])
    db['pintype']['U1.1'] = 'OUT'
    if led_resistor:
        add(db, 'R1', '1K', [('1', '1', 'V5_ISO'), ('2', '2', 'LED_A')])
    if pullup:
        add(db, 'R2', '10K', [('1', '1', 'OPTO_OUT'), ('2', '2', 'VCC_3V3')])
    add(db, 'U2', 'HOST', [('1', 'IN', 'OPTO_OUT'), ('2', 'VDD', 'VCC_3V3'),
                           ('3', 'GND', 'GND')])
    return db


def json_declared_opto_board():
    """手册核验过的 opto 声明经 JSON 读入：字符串相等但不是同一个对象。"""
    import json
    db = opto_board()
    db['parts']['OK1'].update(part='SFH-UNLISTED', value='SFH-UNLISTED', prim='Custom:Opto4')
    db['device_kinds'] = json.loads(json.dumps({'OK1': {'kind': ''.join(['op', 'to']), 'citation': 'p1'}}))
    return db


def optos_of(inventory, state='as-built'):
    entry = next(x for x in inventory['states'] if x['id'] == state)
    return {item['ref']: item for item in entry['optocouplers']}


CHECKER_RULES = {rule.id for rule in catalog.rules(source='optocoupler')}


def findings(db, intent=None):
    return [f for f in Lint(db, '', intent).run() if f['rule'] in CHECKER_RULES]


class RecognitionTest(unittest.TestCase):
    def internal_intent(self, db):
        return bound_intent(db, {'optocouplers': {'schema_version': 2, 'optocouplers': [
            {'id': 'opto', 'ref': 'OK1', 'drive': 'resistor', 'citation': 'synthetic circuit',
             'internal_pullup': {'node': 'U2.1', 'resistance_ohm': {'min': 17000, 'max': 23000},
                                 'bias_v': {'min': 3, 'max': 3.6}, 'states': ['run'],
                                 'citation': 'Synthetic receiver table p2, always enabled in run'}}]}})

    def test_internal_pullup_suppresses_only_missing_resistor_not_ctr_checks(self):
        db = opto_board(pullup=False)
        intent = self.internal_intent(db)
        self.assertEqual(validate_optocoupler_intent(intent, db), [])
        self.assertNotIn('PRO-A04', [f['rule'] for f in findings(db, intent)])
        plan = build_review_plan(db, intent=intent)
        self.assertTrue(any(c['rule'] == 'PRO-E01' and c['readiness'] != 'READY' for c in plan['checks']))

    def test_wrong_pin_state_invalid_bounds_or_missing_citation_never_clear_candidate(self):
        for field, value in [('node', 'U2.2'), ('states', ['off']), ('citation', ''),
                             ('resistance_ohm', {'min': 0, 'max': 20000})]:
            with self.subTest(field=field):
                db = opto_board(pullup=False)
                intent = self.internal_intent(db)
                intent['optocouplers']['optocouplers'][0]['internal_pullup'][field] = value
                item = optos_of(build_inventory(db, intent), 'run')['OK1']
                self.assertIsNone(item['internal_pullup'])

    def test_unpopulated_receiver_does_not_supply_internal_pullup(self):
        db = opto_board(pullup=False)
        intent = self.internal_intent(db)
        intent['assemblies'][0]['population']['U2'] = False
        self.assertIn('PRO-A04', [f['rule'] for f in findings(db, intent)])

    def test_complete_optocoupler_has_no_findings(self):
        db = opto_board()
        item = optos_of(build_inventory(db))['OK1']
        self.assertEqual(item['led_nets'], ['LED_A', 'OPTO_DRV'])
        self.assertEqual([x['ref'] for x in item['led_resistors']], ['R1'])
        self.assertEqual([x['node'] for x in item['led_drivers']], ['U1.1'])
        self.assertEqual(item['collector_net'], 'OPTO_OUT')
        self.assertEqual(item['output_pullups'], ['R2'])
        self.assertEqual(findings(db), [])

    def test_missing_series_resistor_reports_oc01(self):
        db = opto_board(led_resistor=False)
        hits = findings(db)
        self.assertEqual([f['rule'] for f in hits], ['PRO-A03'])
        self.assertEqual(hits[0]['kind'], 'FINDING')

    def test_declared_constant_current_drive_clears_oc01(self):
        db = opto_board(led_resistor=False)
        intent = bound_intent(db, {'optocouplers': {
            'schema_version': 2,
            'optocouplers': [{'id': 'ok1', 'ref': 'OK1', 'drive': 'constant-current',
                              'citation': 'constant current driver datasheet'}]}})
        self.assertEqual(findings(db, intent), [])

    def test_missing_pullup_reports_oc02(self):
        hits = findings(opto_board(pullup=False))
        self.assertEqual([f['rule'] for f in hits], ['PRO-A04'])
        self.assertEqual(hits[0]['kind'], 'CANDIDATE')

    def test_unknown_pin_roles_keep_a_gap(self):
        db = opto_board()
        for pin in ('1', '2', '3', '4'):
            db['pinname'].pop('OK1.' + pin)
        item = optos_of(build_inventory(db))['OK1']
        self.assertIn('pin-roles:OK1', item['gaps'])
        self.assertEqual(item['led_nets'], [])
        self.assertEqual(findings(db), [])

    def test_unpopulated_optocoupler_is_skipped(self):
        db = opto_board()
        db['parts']['OK1']['nc'] = True
        self.assertEqual(optos_of(build_inventory(db)), {})


class PlanTest(unittest.TestCase):
    def test_plan_covers_transfer_and_isolation(self):
        plan = build_review_plan(opto_board())
        checks = {(x['rule'], x['object']['optocoupler']) for x in plan['checks'] if x['object'].get('optocoupler')}
        self.assertEqual(checks, {('PRO-E01', 'OK1'), ('PRO-D01', 'OK1')})
        self.assertEqual(plan['optocoupler_version'], 1)
        rules = {row['rule']: row for row in plan['rule_plan']}
        self.assertEqual(rules['PRO-A03']['instances'], ['OK1'])

    def test_the_transfer_row_asks_no_project_decay_factor(self):
        # Consistency proposals of 2026-10-23, item 6: the end-of-life CTR is the life row's selection constraint.
        row = next(x for x in build_review_plan(opto_board())['checks'] if x['rule'] == 'PRO-E01')
        self.assertFalse([i for i in row['required_inputs'] if '衰减' in i], row['required_inputs'])

    def test_stale_object_binding_is_reported(self):
        plan = build_review_plan(opto_board())
        item = next(x for x in plan['checks'] if x['object'].get('optocoupler'))
        stale = dict(item['object'], optocoupler_digest='0' * 64)
        self.assertEqual(OptocouplerChecker().object_errors('X', stale, plan['optocoupler']),
                         ['X: stale optocoupler object binding'])

    def test_intent_validation_rejects_unknown_refs(self):
        db = opto_board()
        section = {'schema_version': 2, 'optocouplers': [{'id': 'x', 'ref': 'OK9', 'citation': 'y'}]}
        errors = validate_optocoupler_intent(
            bound_intent(db, {'optocouplers': section}, populated=False), db)
        self.assertTrue(any('optocoupler ref unknown: OK9' in error for error in errors), errors)


class HotRuleTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

if __name__ == '__main__':
    unittest.main()


class DeclaredKindIdentityTest(unittest.TestCase):
    def test_json_declared_opto_enters_the_inventory(self):
        # 真实反例：三颗已核验为光耦的器件，清单仍为空（kind 用 is 比较）。
        from checkers import netgraph as ng
        import part_words as pw
        db = json_declared_opto_board()
        self.assertIs(ng.NetGraph(db).kind('OK1'), pw.OPTO)
        self.assertIn('OK1', optos_of(build_inventory(db)))


class InternalPullupBoundsTest(unittest.TestCase):
    """R6 acceptance 2026-10-24, codex2 SR-01: a receiver pull-up biased to its own ground has bias_v min 0."""

    def test_bias_v_may_start_at_zero_the_resistance_may_not(self):
        pull = {'node': 'U2.1', 'resistance_ohm': {'min': 17000, 'max': 23000}, 'bias_v': {'min': 0, 'max': 3.6},
                'states': ['run'], 'citation': 'receiver table p2'}
        self.assertEqual(internal_pullup_errors(pull), [])
        self.assertTrue(internal_pullup_errors(dict(pull, bias_v={'min': -0.3, 'max': 3.6})))
        self.assertTrue(internal_pullup_errors(dict(pull, resistance_ohm={'min': 0, 'max': 23000})))

"""A programmable device's configuration is not reviewed (2026-10-26, user: 手册已有声明、配置表没有……判断为功能可达，
不需要再单独查验配置规则).

A capability the datasheet declares is reachable, so no configuration row (the former CFG-D01) is planned and a missing
configuration table is no gap. Hardware is judged over the configuration range the datasheet allows; a condition that
holds only at one setting names it (`setting{ref, group, value}`), and the gate lists those settings
(`configuration_settings`) for whoever writes the table, which the report shows under 交给后续环节的要求. The output
levels a device selects stay a hardware question: `intent.devices.<ref>.set_points` asks each list's accuracy (PWR-C02).
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import catalog
import results_model
import review_functions as rf
from board_intent import input_fingerprint
from plan_review import build_review_plan, validate_intent
from render_report import render
from test_inductive_load import add
from test_review_functions import bias_function, ledger
import validate_review as vr


def empty():
    return {'nets': {}, 'parts': {}, 'pin2net': {}, 'pinname': {}, 'pintype': {}, 'pseudo_nets': [], 'ref2page': {}}


PINS = [('1', 'VDD', 'V5'), ('2', 'CC1', 'CC1'), ('3', 'GND', 'GND')]


def board():
    db = empty()
    add(db, 'U1', 'PD-CTRL', PINS)
    add(db, 'J1', 'Connector:USB_C', [('1', 'CC1', 'CC1'), ('2', 'GND', 'GND')])
    return db


def device(**extra):
    return dict({'mpn': 'PD-CTRL-1', 'package': 'QFN', 'identity_citation': 'BOM row U1', 'citation': 'ds p3 pinout',
                 'pinout_complete': True,
                 'pins': {p: {'name': n, 'role': 'return' if n == 'GND' else 'other'} for p, n, _ in PINS}}, **extra)


def intent(**dev):
    out = {'schema_version': 5, 'device_kinds_verified': {'U1': {'kind': 'pd_controller', 'citation': 'ds p1'}}}
    if dev:
        out['devices'] = {'U1': device(**dev)}
        out['input_sha256'] = input_fingerprint(board())
    return out


LEVELS = [{'id': 'VBUS_LEVELS', 'citation': 'evidence/ds/U1.txt §8.2', 'points': ['5 V', '9 V', '15 V', '20 V']}]


class NoConfigurationReviewTests(unittest.TestCase):
    def test_no_configuration_rule_or_gap_kind_is_left(self):
        self.assertNotIn('CFG-D01', catalog.BY_ID)
        self.assertNotIn('DELIVERABLE_PENDING', results_model.OPEN_KINDS)

    def test_a_pd_controller_gets_no_configuration_row(self):
        plan = build_review_plan(board(), intent())
        self.assertFalse([c for c in plan['checks'] if c['rule'].startswith('CFG')])
        self.assertFalse([d for d in plan.get('diagnostics') or [] if d.get('code') == 'CONFIGURABLE_UNDECLARED'])

    def test_a_configurable_declaration_is_refused_and_says_what_to_write(self):
        value = intent(configurable=[{'group': 'CAPABILITY'}])
        errors = validate_intent(value, board())
        self.assertTrue(any('configurable is gone' in e and 'setting' in e and 'set_points' in e for e in errors), errors)

    def test_a_configuration_table_is_no_open_item(self):
        fn = bias_function('OPEN')
        fn['open'][0].update(kind='DELIVERABLE_PENDING', deliverable_kind='CONFIGURATION_TABLE', deliverable='U1 配置表',
                             owner='固件', assumed='按手册默认值', scope='配置值')
        errors = rf.function_errors({'functions': [fn]})
        self.assertTrue(any('no open item' in e for e in errors), errors)


class SetPointTests(unittest.TestCase):
    def test_declared_set_points_get_an_accuracy_row(self):
        plan = build_review_plan(board(), intent(set_points=LEVELS))
        rows = [c for c in plan['checks'] if c['id'].startswith('PWR-C02.SET-POINT')]
        self.assertEqual([(r['object']['ref'], r['object']['set_point_group']) for r in rows], [('U1', 'VBUS_LEVELS')])
        self.assertIn('9 V', rows[0]['criterion'])
        self.assertIn('§8.2', rows[0]['criterion'])

    def test_no_set_points_no_row(self):
        plan = build_review_plan(board(), intent())
        self.assertFalse([c for c in plan['checks'] if c['id'].startswith('PWR-C02.SET-POINT')])

    def test_a_set_point_list_needs_its_id_citation_and_levels(self):
        errors = validate_intent(intent(set_points=[{'id': 'out', 'points': []}]), board())
        for word in ('.id is an upper-case id', '.citation is missing', '.points lists'):
            self.assertTrue(any(word in e for e in errors), (word, errors))


class SettingTests(unittest.TestCase):
    def at_setting(self, setting):
        fn = bias_function('PASS')
        fn['conditions'][3]['setting'] = setting
        fn['conditions'][3]['refs'] = sorted(set(fn['conditions'][3]['refs']) | {setting['ref']})
        return fn

    def test_a_setting_names_device_item_and_value(self):
        fn = bias_function('PASS')
        fn['conditions'][3]['setting'] = {'ref': 'R1', 'group': 'GPIO'}
        self.assertTrue(any('setting is {ref, group, value}' in e for e in rf.function_errors({'functions': [fn]})))

    def test_the_gate_lists_each_setting_with_what_relies_on_it_and_the_report_hands_it_on(self):
        p, r, db = ledger(self.at_setting({'ref': 'R1', 'group': 'CAPABILITY', 'value': '20 V 档'}))
        out = vr.validate_review(p, r, db)
        self.assertFalse([e for e in out['errors'] if 'setting' in e], out['errors'])
        self.assertEqual([(s['ref'], s['group'], s['value'], s['used_in']) for s in out['configuration_settings']],
                         [('R1', 'CAPABILITY', '20 V 档', ['FN-BIAS/' + r['functions'][0]['conditions'][3]['id']])])
        text = render(p, r, out)
        section = text.split('<summary>配置表要写的设置</summary>')[1].split('</details>')[0]
        self.assertIn('| R1 | CAPABILITY | 20 V 档 |', section)


if __name__ == '__main__':
    unittest.main()

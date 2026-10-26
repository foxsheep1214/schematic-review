"""A programmable device is judged over the configuration range its datasheet allows, and its configuration is a row
of its own (consistency proposals of 2026-10-23, item 3; intent format 4).

Two reviews of one board split the configuration differently: one let a missing configuration table block 57 rows,
28 of which the other passed on the datasheet defaults with three configuration work items, and recorded on-chip
compensation once as a design value and once as passing on lab measurement. A device of a known programmable role now
gets one CFG-D01 row per fixed configuration group of that role (`catalog.CONFIG_GROUPS`), a programmable device
without fixed groups gets a row asking for its groups, and the reviewer declares each group in
`intent.devices[ref].configurable` (the datasheet section, the allowed range, the aspects it affects, the value a
requirement asks). Hardware is judged over the allowed range; a condition that holds only at one setting names it
(`setting{ref, group, value}`) and the configuration row lists it. A missing configuration table blocks only the
configuration rows and the requirement rows. A group that sets the output level also gets a row for the accuracy of
each set point (item 7's sixth trigger).
"""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import catalog
from board_intent import input_fingerprint
from plan_review import INTENT_SCHEMA_VERSION, build_review_plan, validate_intent
from test_inductive_load import add
from test_review_functions import ASPECT, STATES, bias_function, ledger
from test_validate_review import E, planned
from validate_review import fingerprint
import validate_review as vr


def empty():
    return {'nets': {}, 'parts': {}, 'pin2net': {}, 'pinname': {}, 'pintype': {}, 'pseudo_nets': [], 'ref2page': {}}


PINS = [('1', 'VDD', 'V5'), ('2', 'CC1', 'CC1'), ('3', 'GND', 'GND')]


def board():
    db = empty()
    add(db, 'U1', 'PD-CTRL', PINS)
    add(db, 'U2', 'MCU', [('1', 'VDD', 'V3'), ('2', 'NRST', 'NRST'), ('3', 'GND', 'GND')])
    add(db, 'J1', 'Connector:USB_C', [('1', 'CC1', 'CC1'), ('2', 'GND', 'GND')])
    return db


def device(**extra):
    return dict({'mpn': 'PD-CTRL-1', 'package': 'QFN', 'identity_citation': 'BOM row U1', 'citation': 'ds p3 pinout',
                 'pinout_complete': True,
                 'pins': {p: {'name': n, 'role': 'return' if n == 'GND' else 'other'} for p, n, _ in PINS}}, **extra)


def group(name='CAPABILITY', **extra):
    return dict({'group': name, 'citation': 'evidence/ds/U1.txt §8.2 能力发布寄存器',
                 'allowed': '5 V、9 V、15 V、20 V 档，每档电流 0.5–3 A', 'affects': ['变换器电压裕量'],
                 'required': '需求：5/9/15/20 V，3 A'}, **extra)


def intent(configurable=None, kinds=None):
    out = {'schema_version': 4,
           'device_kinds_verified': kinds if kinds is not None else {
               'U1': {'kind': 'pd_controller', 'citation': 'ds p1'}, 'U2': {'kind': 'mcu', 'citation': 'ds p1'}}}
    if configurable is not None:
        out['devices'] = {'U1': device(configurable=configurable)}
        out['input_sha256'] = input_fingerprint(board())
    return out


def declared(configurable):
    """What the reviewer writes: the verified kinds come from the datasheet audit, not the intent."""
    out = intent(configurable)
    del out['device_kinds_verified']
    return out


def cfg_rows(plan):
    return {c['id']: c for c in plan['checks'] if c['rule'] == 'CFG-D01'}


class FormatTests(unittest.TestCase):
    def test_the_intent_format_is_4_and_format_3_is_refused(self):
        self.assertEqual(INTENT_SCHEMA_VERSION, 4)
        self.assertTrue(any('schema_version' in e for e in validate_intent({'schema_version': 3})))

    def test_a_group_declares_its_section_range_and_affected_aspects(self):
        db = board()
        self.assertEqual(validate_intent(declared([group()]), db), [])
        for field in ('citation', 'allowed', 'affects'):
            bad = group(); del bad[field]
            self.assertTrue(any('configurable' in e for e in validate_intent(declared([bad]), db)), field)
        self.assertTrue(any('configurable' in e for e in validate_intent(declared([group('MYSTERY')]), db)))
        self.assertEqual(validate_intent(declared([group('MYSTERY', title='自定义组')]), db), [])
        self.assertTrue(any('configurable' in e for e in validate_intent(declared([group(), group()]), db)))


class FixedGroupTests(unittest.TestCase):
    def test_a_pd_controller_gets_one_row_per_fixed_group(self):
        plan = build_review_plan(board(), intent())
        rows = cfg_rows(plan)
        fixed = [g for g, _ in catalog.CONFIG_GROUPS['pd_controller']]
        self.assertEqual(sorted(r['object']['config_group'] for r in rows.values() if r['object']['ref'] == 'U1'),
                         sorted(fixed))
        row = rows['CFG-D01.CAPABILITY.U1']
        self.assertEqual(row['readiness'], 'WAITING_EVIDENCE')
        self.assertIn('intent.devices.U1.configurable', ' '.join(row['required_inputs']))
        self.assertNotIn('state', row['object'])

    def test_a_declared_group_is_ready_and_its_row_carries_the_range(self):
        plan = build_review_plan(board(), intent([group()]))
        row = cfg_rows(plan)['CFG-D01.CAPABILITY.U1']
        self.assertEqual(row['readiness'], 'READY')
        self.assertIn('5 V、9 V、15 V、20 V', row['configuration']['allowed'])
        self.assertIn('变换器电压裕量', row['configuration']['affects'])
        self.assertIn('U1 的能力发布', row['criterion'])

    def test_a_programmable_device_without_fixed_groups_is_asked_to_declare_them(self):
        plan = build_review_plan(board(), intent())
        self.assertIn('CFG-D01.DECLARE.U2', cfg_rows(plan))
        self.assertIn('intent.devices.U2.configurable', cfg_rows(plan)['CFG-D01.DECLARE.U2']['criterion'])

    def test_declared_groups_replace_the_request_to_declare(self):
        out = intent()
        out['devices'] = {'U2': dict(device(), pins={'1': {'name': 'VDD', 'role': 'power'}, '2': {'name': 'NRST', 'role': 'other'},
                                                     '3': {'name': 'GND', 'role': 'return'}},
                                     configurable=[group('BOOT', title='启动与看门狗选项')])}
        out['input_sha256'] = input_fingerprint(board())
        rows = cfg_rows(build_review_plan(board(), out))
        self.assertIn('CFG-D01.BOOT.U2', rows)
        self.assertNotIn('CFG-D01.DECLARE.U2', rows)

    def test_an_undeclared_programmable_device_is_a_plan_diagnostic(self):
        # R7 acceptance 2026-10-25 (A8): the CFG-D01 criterion follows the declaration, so two reviewers pair only when
        # both declared; the plan says so and 2.1's done mark asks for zero
        found = {d['ref']: d for d in build_review_plan(board(), intent())['diagnostics'] if d['code'] == 'CONFIGURABLE_UNDECLARED'}
        self.assertEqual(sorted(found), ['U1', 'U2'])
        self.assertEqual(found['U1']['groups'], [g for g, _ in catalog.CONFIG_GROUPS['pd_controller']])
        self.assertIn('intent.devices.U1.configurable', found['U1']['message'])
        every = [group(g) for g, _ in catalog.CONFIG_GROUPS['pd_controller']]
        found = [d for d in build_review_plan(board(), intent(every))['diagnostics'] if d['code'] == 'CONFIGURABLE_UNDECLARED']
        self.assertEqual([d['ref'] for d in found], ['U2'])

    def test_a_device_of_no_programmable_role_gets_no_configuration_row(self):
        plan = build_review_plan(board(), intent(kinds={}))
        self.assertEqual(cfg_rows(plan), {})


class SetPointTests(unittest.TestCase):
    """Item 7, sixth trigger: a group that sets the output level asks the accuracy of each set point."""

    def test_declared_set_points_get_an_accuracy_row(self):
        plan = build_review_plan(board(), intent([group(set_points=['5 V', '9 V', '15 V', '20 V'])]))
        rows = [c for c in plan['checks'] if c['id'].startswith('PWR-C02.SET-POINT')]
        self.assertEqual([(r['object']['ref'], r['object']['config_group']) for r in rows], [('U1', 'CAPABILITY')])
        self.assertIn('9 V', rows[0]['criterion'])

    def test_no_set_points_no_row(self):
        plan = build_review_plan(board(), intent([group()]))
        self.assertFalse([c for c in plan['checks'] if c['id'].startswith('PWR-C02.SET-POINT')])


def with_config_row(fn, settings=None):
    p, r, db = ledger(fn)
    p['checks'].append(dict(planned('CFG-D01.CAPABILITY.R1'), object={'ref': 'R1', 'config_group': 'CAPABILITY'},
                            criterion='config'))
    row = {'id': 'CFG-D01.CAPABILITY.R1', 'applicability': 'APPLICABLE', 'review_result': 'PASS', 'evidence': E,
           'evidence_confidence': 'A', 'rationale': '配置表写了 20 V 档', 'handoff': {'required': False}}
    if settings is not None:
        row['settings'] = settings
    r['checks'].append(row)
    r['plan_digest'] = fingerprint(p)
    return p, r, db


class SettingTests(unittest.TestCase):
    """3c: a condition that holds only at one setting names it, and the configuration row lists that setting."""

    def at_setting(self, setting):
        fn = bias_function('PASS')
        fn['conditions'][3]['setting'] = setting   # the mandatory clause holds at one setting
        return fn

    def test_a_setting_is_listed_in_its_configuration_row(self):
        setting = {'ref': 'R1', 'group': 'CAPABILITY', 'value': '20 V 档'}
        errors = vr.validate_review(*with_config_row(self.at_setting(setting)))['errors']
        self.assertTrue(any('setting' in e and 'CFG-D01.CAPABILITY.R1' in e for e in errors), errors)
        errors = vr.validate_review(*with_config_row(self.at_setting(setting),
                                                     [{'value': '20 V 档', 'function': 'FN-BIAS'}]))['errors']
        self.assertFalse([e for e in errors if 'setting' in e], errors)

    def test_a_group_id_with_an_underscore_finds_its_row(self):
        p, r, db = with_config_row(self.at_setting({'ref': 'R1', 'group': 'CABLE_VCONN', 'value': 'VCONN 关'}))
        p['checks'][-1].update(id='CFG-D01.CABLE-VCONN.R1', object={'ref': 'R1', 'config_group': 'CABLE_VCONN'})
        r['checks'][-1].update(id='CFG-D01.CABLE-VCONN.R1', settings=[{'value': 'VCONN 关', 'function': 'FN-BIAS'}])
        r['plan_digest'] = fingerprint(p)
        errors = vr.validate_review(p, r, db)['errors']
        self.assertFalse([e for e in errors if 'setting' in e], errors)

    def test_a_setting_of_a_group_the_plan_does_not_have_is_refused(self):
        errors = vr.validate_review(*with_config_row(self.at_setting({'ref': 'R1', 'group': 'GPIO', 'value': 'x'})))
        self.assertTrue(any('CFG-D01.GPIO.R1' in e and 'declare the group' in e for e in errors['errors']), errors['errors'])


class ConfigurationGapTests(unittest.TestCase):
    """3d: a missing configuration table blocks the configuration rows and the requirement rows, never hardware."""

    def table_gap(self):
        fn = bias_function('OPEN')
        item = fn['open'][0]
        item.update(kind='DELIVERABLE_PENDING', deliverable_kind='CONFIGURATION_TABLE', deliverable='U1 配置表',
                    owner='固件', assumed='按手册默认值', scope='配置值')
        for field in ('checked', 'why_insufficient', 'acquisition', 'worst_case', 'spec'):
            item.pop(field, None)
        return fn

    def test_a_configuration_table_does_not_block_a_hardware_row(self):
        errors = vr.validate_review(*ledger(self.table_gap()))['errors']
        self.assertTrue(any('configuration table' in e for e in errors), errors)

    def test_it_blocks_the_configuration_row(self):
        fn = self.table_gap()
        fn['open'][0]['decides'] = [{'aspect': catalog.title('CFG-D01'), 'states': list(STATES)}]
        p, r, db = with_config_row(fn)
        for row in r['checks']:
            if row['id'].startswith('PWR-C02.'):
                row.update(review_result='PASS'); row.pop('open_ref', None)
        r['checks'][-1].update(review_result='INSUFFICIENT', open_ref='FN-BIAS/' + fn['open'][0]['key'])
        errors = vr.validate_review(p, r, db)['errors']
        self.assertFalse([e for e in errors if 'configuration table' in e], errors)

    def test_a_setting_names_device_group_and_value(self):
        from review_functions import function_errors
        fn = bias_function('PASS')
        fn['conditions'][3]['setting'] = {'ref': 'R1', 'group': 'GPIO'}
        self.assertTrue(any('setting is {ref, group, value}' in e for e in function_errors({'functions': [fn]})))


if __name__ == '__main__':
    unittest.main()


class CriterionTests(unittest.TestCase):
    """R6 acceptance 2026-10-24: 7 CFG-D01 rows per pair did not pair because the criterion quoted the reviewer's
    citation and allowed range. The criterion names the device and the group; the declaration rides on the row."""

    def test_the_declaration_is_a_row_field_not_the_criterion(self):
        rows = {}
        for allowed in ('5 V、9 V、15 V、20 V 档，每档电流 0.5–3 A', 'PDO 5/9/15/20 V @ 3 A'):
            plan = build_review_plan(board(), intent=declared([group(allowed=allowed)]))
            rows[allowed] = next(c for c in plan['checks'] if c['id'] == 'CFG-D01.CAPABILITY.U1')
        a, b = rows.values()
        self.assertEqual(a['criterion'], b['criterion'])
        self.assertEqual(a['check_key'], b['check_key'])
        self.assertNotIn('§8.2', a['criterion'])
        self.assertEqual(a['configuration']['citation'], 'evidence/ds/U1.txt §8.2 能力发布寄存器')
        self.assertEqual(b['configuration']['allowed'], 'PDO 5/9/15/20 V @ 3 A')
        self.assertEqual(a['configuration']['affects'], ['变换器电压裕量'])
        self.assertEqual(a['configuration']['required'], '需求：5/9/15/20 V，3 A')

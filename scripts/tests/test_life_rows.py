"""Life and ageing are judged on one mission profile, and an electrolytic capacitor's endurance is an estimate written
as a BOM constraint (consistency proposals of 2026-10-23, items 6a, 6c and 6d; intent format 4).

Two reviews of one board read the same "10 years" two ways: one took 87600 h of full-time operation, the other
29200 h of daily full load, and one refused the 10 °C doubling rule and opened a vendor-data item while the other
used it and wrote a BOM constraint. The intent now carries one mission profile (`intent.mission_profile`: phases with
their share of the time, load and ambient, each citing the requirement), every life row is planned on it, an
electrolytic, solid or super capacitor is found by its symbol, its BOM part number or specification, or an aluminium
package with a stated voltage, and its endurance is estimated (vendor life formula or 10 °C doubling, both ESTIMATE)
into a BOM constraint "耐久 ≥ X h @T（估算，热点 ≤ Y °C）" with the hot spot handed to thermal design; no vendor-data
item is opened for it.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import catalog
import requirement_parameters
from plan_review import build_review_plan, validate_intent
from electrical_contract import IMPACT_CLASSES
from test_decoupling import add, rebind
from test_requirement_bindings import board as req_board
from test_requirement_source import DOC, source, write
from test_validate_review import E, fixture, planned
from validate_review import fingerprint
import validate_review as vr

LIFE_ROW = '| REQ-LIFE-9 | 设计寿命 10 年；每天充电 8 h，其余 16 h 待机 | 充电时环境 40°C，待机 25°C |\n'
DEV_C02 = catalog.title('DEV-C02')


def profile(**extra):
    return dict({'requirement': 'REQ-LIFE-9', 'phases': [
        {'name': '充电', 'share': 1 / 3, 'load': 1.0, 'ambient_c': 40, 'citation': '每天充电 8 h'},
        {'name': '待机', 'share': 2 / 3, 'load': 0.0, 'ambient_c': 25, 'citation': '其余 16 h 待机'}]}, **extra)


def life_board(mission=True, parts=(), lifetime=True):
    """The requirement board with a lifetime requirement, a mission profile and extra parts
    [(ref, prim, value, bom fields[, pins])], wired across VCC_3V3 and GND unless pins [(pin, name, net)] are given."""
    db, intent = req_board()
    if lifetime:
        intent['requirement_source'] = source(write(DOC.replace('| REQ-TEMP-01 |', LIFE_ROW + '| REQ-TEMP-01 |', 1)))
        intent['requirements'].append({'id': 'REQ-LIFE-9', 'categories': ['LIFETIME'], 'status': 'CONFIRMED',
                                       'interpretation': '按任务剖面算 10 年寿命',
                                       'parameters': [{'name': 'lifetime', 'unit': '年', 'min': 10}]})
    if mission and lifetime:
        intent['mission_profile'] = mission if isinstance(mission, dict) else profile()
    for ref, prim, value, bom, *pins in parts:
        add(db, ref, value, pins[0] if pins else [('1', '1', 'VCC_3V3'), ('2', '2', 'GND')])
        db['parts'][ref]['prim'] = prim
        if bom:
            db.setdefault('bom', {'parts': {}})['parts'][ref] = bom
    intent['assemblies'][0]['population'] = {r: True for r in db['parts']}
    rebind(db, intent)
    return db, intent


def life_rows(plan):
    return {c['object']['ref']: c for c in plan['checks'] if c['id'].startswith('DEV-C02.LIFE.')}


class ProfileTests(unittest.TestCase):
    """6d: one mission profile in the intent, every phase citing the requirement it comes from."""

    def errors(self, mission):
        db, intent = life_board(mission)
        return [e for e in validate_intent(intent, db) if 'mission_profile' in e]

    def test_a_profile_citing_its_requirement_is_accepted(self):
        self.assertEqual(self.errors(profile()), [])

    def test_shares_add_up_to_the_whole_time(self):
        bad = profile(); bad['phases'][1]['share'] = 0.5
        self.assertTrue(self.errors(bad))

    def test_load_is_a_fraction_of_the_rated_load_and_ambient_a_number(self):
        for field, value in (('load', 1.5), ('load', -0.1), ('ambient_c', 'hot'), ('share', 0)):
            bad = profile(); bad['phases'][0][field] = value
            self.assertTrue(self.errors(bad), (field, value))

    def test_a_citation_is_a_piece_of_the_requirement_text(self):
        bad = profile(); bad['phases'][0]['citation'] = '每天满载 24 h'
        self.assertTrue(any('citation' in e for e in self.errors(bad)))

    def test_the_profile_names_a_lifetime_requirement(self):
        self.assertTrue(self.errors(profile(requirement='REQ-NONE')))
        self.assertTrue(any('lifetime' in e for e in self.errors(profile(requirement='REQ-TEMP-01'))))

    def test_events_are_fixed_kinds_with_a_positive_count(self):
        good = {'event': 'power_cycles', 'count': 3650, 'citation': '每天充电 8 h'}
        self.assertEqual(self.errors(profile(events=[good])), [])
        for bad in (dict(good, event='sneezes'), dict(good, count=0), dict(good, refs=['NOPE'])):
            self.assertTrue(self.errors(profile(events=[bad])), bad)

    def test_the_profile_is_read_in_hours(self):
        _, intent = life_board()
        got = requirement_parameters.mission_profile(intent)
        self.assertEqual(got['hours'], 87600)
        self.assertEqual([round(p['hours']) for p in got['phases']], [29200, 58400])
        text = requirement_parameters.profile_text(got)
        for piece in ('REQ-LIFE-9', '87600 h', '29200 h', '40 °C', '25 °C'):
            self.assertIn(piece, text)


class CapacitorTests(unittest.TestCase):
    """6c: an electrolytic is found by its symbol, its BOM part number or specification, or an aluminium package."""

    def rows(self, parts, **kw):
        return life_rows(build_review_plan(*life_board(parts=parts, **kw)))

    def test_by_symbol_bom_specification_or_aluminium_package(self):
        rows = self.rows([
            ('C2', 'Device:C_Polarized', '47u/35V', None),
            ('C3', 'Device:C', '100u/450V', {'Electrical specification': '100µF/450V/105°C，12000h@105°C'}),
            ('C4', 'Device:C', '220u/25V', {'MPN': 'X-ALU-1', 'Electrical specification': '固态铝电解'}),
            ('C5', 'Device:C', '100u/35V', {'Footprint': 'Capacitor_SMD:CP_Elec_8x10'}),
            ('C6', 'Device:C', '10u/50V/X7R', {'Electrical specification': 'X7R MLCC'}),
            ('C7', 'Device:C', '2.2u/10V', None)])
        self.assertEqual(sorted(rows), ['C2', 'C3', 'C4', 'C5'])

    def test_a_tantalum_capacitor_is_no_electrolytic_life_part(self):
        rows = self.rows([('C2', 'Device:C_Polarized', '47u/16V', {'Electrical specification': '钽电容 TANTALUM'})])
        self.assertEqual(rows, {})

    def test_a_super_capacitor_also_derates_its_voltage(self):
        rows = self.rows([('C2', 'Device:C', '1F/5.5V', None)])
        self.assertIn('电压降额', rows['C2']['criterion'])

    def test_the_row_estimates_on_the_profile_and_hands_the_hot_spot_to_thermal_design(self):
        row = self.rows([('C2', 'Device:C_Polarized', '47u/35V', None)])['C2']
        for piece in ('87600 h', '40 °C', '10 °C', '估算', 'bom_constraint', '热点'):
            self.assertIn(piece, row['criterion'])
        self.assertEqual(row['readiness'], 'READY')
        self.assertTrue(row['handoff']['required'])
        self.assertIn('热设计', row['handoff']['receivers'])

    def test_without_a_profile_the_row_waits_for_it(self):
        row = self.rows([('C2', 'Device:C_Polarized', '47u/35V', None)], mission=False)['C2']
        self.assertEqual(row['readiness'], 'WAITING_EVIDENCE')
        self.assertIn('intent.mission_profile', row['required_inputs'])

    def test_no_lifetime_requirement_no_row(self):
        self.assertEqual(self.rows([('C2', 'Device:C_Polarized', '47u/35V', None)], lifetime=False), {})


def life_function(open_item=None, estimate=True):
    fn = {'id': 'FN-LIFE', 'circuit': 'BULK', 'question': 'R1 在任务剖面下 10 年所需的耐久等级',
          'objects': {'refs': ['R1'], 'nets': ['A']}, 'states': ['RUN'],
          'conditions': [{'id': 'c1', 'kind': 'NUMERIC_LIMIT', 'source': 'evidence/ds/R1.txt', 'locator': 'p2 Endurance',
                          'says': '耐久 4000 h @105 °C', 'limit': {'min': 4000, 'unit': 'h'}, 'regime': '105 °C',
                          'use': '额定耐久'}],
          'calculation': {'claim_ids': ['LIFE-R1'], 'inputs': ['mission_profile', 'endurance'],
                          'result': '按 10 °C 翻倍，所需耐久 3100 h @105 °C',
                          'margin': {'value': 900, 'unit': 'h', 'against': '耐久 4000 h @105 °C',
                                     'basis': {'kind': 'ESTIMATE' if estimate else 'GUARANTEED_BOUND', 'comparison': 'GE',
                                               'scope': '10 °C 翻倍估算，热点按环境 +10 °C', 'conditions': ['c1']}},
                          'aspect': DEV_C02},
          'verdict': 'OPEN' if open_item else 'PASS', 'fails': [], 'open': [open_item] if open_item else [],
          'evidence': [{'source': 'evidence/engineering.md', 'locator': '## LIFE'}]}
    return fn


def constraint(requirement='耐久 ≥ 3100 h @105 °C（估算，热点 ≤ 75 °C）'):
    return {'refs': ['R1'], 'requirement': requirement, 'basis': 'FN-LIFE 按任务剖面估算',
            'consequence_class': 'PERFORMANCE_OR_LIFE', 'level': IMPACT_CLASSES['PERFORMANCE_OR_LIFE'],
            'status': 'TO_WRITE'}


def life_ledger(fn, result='PASS', bom=True, requirement=None, key='DEV-C02.LIFE.R1'):
    p, r, db = fixture(key)
    p['checks'][0]['object'] = {'ref': 'R1'}
    row = r['checks'][0]
    row.update(review_result=result, function_id=fn['id'], aspect=fn['calculation']['aspect'], rationale='见 FN-LIFE')
    if result == 'INSUFFICIENT':
        row['open_ref'] = fn['id'] + '/' + fn['open'][0]['key']
    if bom:
        row['bom_constraint'] = constraint(requirement) if requirement else constraint()
    r['functions'] = [fn]
    r['plan_digest'] = fingerprint(p)
    return p, r, db


class EstimateTests(unittest.TestCase):
    """6a: the endurance is an estimate written as a BOM constraint; no vendor-data item is opened for it."""

    def errors(self, *args, **kw):
        return vr.validate_review(*life_ledger(*args, **kw))['errors']

    def test_anestimate_passes_as_a_bom_constraint(self):
        errors = self.errors(life_function())
        self.assertFalse([e for e in errors if 'DEV-C02.LIFE.R1' in e], errors)

    def test_an_estimate_short_of_its_target_does_not_pass(self):
        fn = life_function()
        fn['calculation']['margin']['value'] = -100
        errors = self.errors(fn)
        self.assertTrue(any(e.startswith('DEV-C02.LIFE.R1: function FN-LIFE judges no') for e in errors), errors)

    def test_an_estimate_without_a_bom_constraint_does_not_pass(self):
        errors = self.errors(life_function(), bom=False)
        self.assertTrue(any('DEV-C02.LIFE.R1' in e and 'bom_constraint' in e for e in errors), errors)

    def test_the_constraint_says_it_is_an_estimate(self):
        errors = self.errors(life_function(), requirement='耐久 ≥ 3100 h @105 °C')
        self.assertTrue(any('DEV-C02.LIFE.R1' in e and '估算' in e for e in errors), errors)

    def test_an_estimate_still_does_not_pass_another_calculation_row(self):
        fn = life_function()
        fn['calculation']['aspect'] = catalog.title('DEV-C01')
        errors = self.errors(fn, key='DEV-C01.R1')
        self.assertTrue(any(e.startswith('DEV-C01.R1: function FN-LIFE judges no') for e in errors), errors)
        self.assertTrue(any('decides nothing' in e for e in errors), errors)

    def test_no_vendor_datum_for_an_endurance(self):
        item = {'key': 'LIFE-MODEL', 'kind': 'VENDOR_DATUM', 'what': 'R1 系列没给寿命公式',
                'scope': '任务剖面', 'spec': '厂家寿命公式', 'owner': '采购', 'closure': '厂家给出寿命公式',
                'checked': ['c1'], 'why_insufficient': '手册只给 105 °C 耐久', 'acquisition': '厂家',
                'decides': [{'aspect': DEV_C02, 'via': {'condition': 'c1'},
                             'rationale': '寿命模型缺'}],
                'severity': {'level': 'P1', 'class': 'PERFORMANCE_OR_LIFE', 'consequence': '寿命不足'}}
        errors = self.errors(life_function(item), result='INSUFFICIENT', bom=False)
        self.assertTrue(any('VENDOR_DATUM' in e and '10 °C' in e for e in errors), errors)


if __name__ == '__main__':
    unittest.main()


class PhaseNameTests(unittest.TestCase):
    """R6 acceptance 2026-10-24: two reviewers named the same phases differently (0W-25C vs 0W-25C-带线待机) and 17 life
    rows per pair did not pair. The criterion carries the numbers only; the named profile rides on the row."""

    def test_renamed_phases_plan_the_same_row(self):
        renamed = profile()
        renamed['phases'][0]['name'], renamed['phases'][1]['name'] = 'charge@40C', 'standby-idle'
        renamed['phases'].reverse()
        parts = [('C2', 'Device:C_Polarized', '47u/35V', None)]
        a = life_rows(build_review_plan(*life_board(parts=parts)))['C2']
        b = life_rows(build_review_plan(*life_board(mission=renamed, parts=parts)))['C2']
        self.assertEqual(a['criterion'], b['criterion'])
        self.assertEqual(a['check_key'], b['check_key'])
        for name in ('充电', '待机', 'charge@40C'):
            self.assertNotIn(name, a['criterion'])
        for piece in ('33.3%', '29200 h', '40 °C', '66.7%', '25 °C'):
            self.assertIn(piece, a['criterion'])
        self.assertIn('充电', a['mission_profile'])
        self.assertIn('standby-idle', b['mission_profile'])


class ProfileNumbersTests(unittest.TestCase):
    """SR task loop 2026-10-25 (1.1): a requirement the mission profile cites is read by the profile; its hours, loads
    and ambients are not listed as unread numbers (R6: 31 numbers of REQ-LIFE-001 in every record)."""

    def unread(self, mission):
        plan = build_review_plan(*life_board(mission=mission))
        return [d for d in plan['diagnostics'] if d['code'] == 'REQUIREMENT_NUMBERS_UNREAD' and d['requirement'] == 'REQ-LIFE-9']

    def test_the_profiled_requirement_is_not_listed(self):
        self.assertEqual(self.unread(True), [])

    def test_without_a_profile_its_numbers_are_listed(self):
        found = self.unread(False)
        self.assertEqual(len(found), 1)
        self.assertIn('8 h', found[0]['values'])

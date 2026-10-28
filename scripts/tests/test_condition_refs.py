"""Results 7 (2026-10-26, user: 条款 refs 方案按文中四条推荐落地，一次提交): a condition from a datasheet or the BOM names
the parts it is about (`refs`); the gate checks them against the netlist and the datasheet audit the plan froze; the
report lists a per-part parameter sheet; compare_reviews aligns the two records' parameter references part by part.
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import compare_reviews as cr
import results_model
import review_functions as rf
import validate_review as vr
from render_report import render
from test_compare_reviews import side
from test_review_functions import bias_function, ledger

DS = 'evidence/ds/U1.txt'


def audit():
    """The datasheet audit as the plan freezes it: U1's and Q2's documents are known, D2 is not audited."""
    return {'materials': [
        {'material_id': 'DS-U1', 'identity': 'UCC28740', 'refdes': ['U1'],
         'document': {'path': '/docs/TI-UCC28740.pdf', 'document_model': 'UCC28740'}},
        {'material_id': 'DS-Q2', 'identity': 'AO3400', 'refdes': ['Q2'],
         'document': {'path': '/docs/AOS-AO3400.pdf', 'document_model': 'AO3400'}}]}


def limit(source=DS, **extra):
    return dict({'id': 'x1', 'kind': 'NUMERIC_LIMIT', 'source': source, 'locator': 'p7 Table 7', 'says': 'VCC(off) max 8.8 V',
                 'limit': {'max': 8.8, 'unit': 'V'}, 'regime': '全温', 'use': '判据'}, **extra)


def ref_errors(c, db=None, audit_=None):
    return [e for e in rf.condition_ref_errors('FN-X/conditions[x1]', c, db, audit_)]


class RefFieldTests(unittest.TestCase):
    def test_a_datasheet_or_bom_condition_needs_refs_a_standard_or_assumption_does_not(self):
        self.assertTrue(any('refs names the part' in e and 'datasheet' in e for e in ref_errors(limit())))
        self.assertTrue(any('refs names the part' in e for e in ref_errors(limit('ds/U9.txt'))))
        self.assertTrue(any('refs names the part' in e for e in ref_errors(limit('manuals/MCU.pdf'))))
        self.assertTrue(any('refs names the part' in e and 'BOM' in e for e in ref_errors(limit('BOM.csv'))))
        self.assertEqual(ref_errors(limit('std/IEC62368.txt')), [])
        self.assertEqual(ref_errors(limit('/需求/工程规格.md')), [])
        self.assertEqual(ref_errors({'id': 'a1', 'kind': 'ENGINEERING_ASSUMPTION', 'source': 'engineering.md', 'locator': '## x',
                                     'says': '取 10%', 'use': '估算'}), [])
        self.assertEqual(ref_errors(limit(refs=['U1'])), [])
        # a condition the datasheet audit knows the document of needs refs whatever its path
        self.assertTrue(any('refs names the part' in e for e in ref_errors(limit('/docs/TI-UCC28740.pdf'), None, audit())))

    def test_refs_is_a_list_of_distinct_netlist_or_bom_parts(self):
        for bad in ('U1', [], ['U1', ''], [1]):
            self.assertTrue(any('non-empty list' in e for e in ref_errors(limit(refs=bad))), bad)
        self.assertTrue(any('twice' in e for e in ref_errors(limit(refs=['U1', 'U1']))))
        db = {'parts': {'U1': {}}, 'bom': {'source': 'BOM.csv', 'parts': {'T1': {'Value': 'custom'}}}}
        self.assertTrue(any('U7 are not parts' in e for e in ref_errors(limit(refs=['U1', 'U7']), db)))
        self.assertEqual(ref_errors(limit(refs=['U1', 'T1']), db), [])    # a BOM part is a part
        self.assertEqual(ref_errors(limit(refs=['U7']), {'parts': {}}), [])  # no netlist to check against

    def test_a_setting_and_a_netlist_facts_pins_name_parts_among_the_refs(self):
        setting = {'ref': 'U1', 'group': 'CAPABILITY', 'value': '20 V'}
        self.assertTrue(any('refs names the part' in e for e in ref_errors(limit('engineering.md', setting=setting))))
        self.assertTrue(any('setting.ref U1 is not in refs' in e for e in ref_errors(limit(refs=['Q2'], setting=setting))))
        self.assertEqual(ref_errors(limit(refs=['Q2', 'U1'], setting=setting)), [])
        fact = {'id': 'n1', 'kind': 'NETLIST_FACT', 'source': 'db.json', 'locator': 'Q2.G', 'pins': ['Q2.G', 'D2.A'],
                'says': 'D2 阴极接 Q2 栅极', 'use': '路径'}
        self.assertEqual(ref_errors(fact), [])                                   # refs optional, the pins say it
        self.assertTrue(any('pins name D2' in e for e in ref_errors(dict(fact, refs=['Q2']))))
        self.assertEqual(ref_errors(dict(fact, refs=['Q2', 'D2'])), [])

    def test_the_function_checks_carry_the_refs_rules(self):
        fn = bias_function('PASS')
        del fn['conditions'][0]['refs']
        self.assertTrue(any('conditions[c1]' in e and 'refs names the part' in e for e in rf.function_errors({'functions': [fn]})))
        self.assertEqual(rf.function_errors({'functions': [bias_function('PASS')]}), [])


class AuditOwnershipTests(unittest.TestCase):
    """The first machine-checked mis-attribution: a ref whose audited datasheet is another document than the source."""

    def test_another_parts_datasheet_is_refused_the_right_part_and_an_unaudited_part_pass(self):
        found = ref_errors(limit(refs=['Q2']), None, audit())
        self.assertTrue(any('lists AOS-AO3400.pdf for Q2, not U1.txt' in e for e in found), found)
        self.assertEqual(ref_errors(limit(refs=['U1']), None, audit()), [])
        self.assertEqual(ref_errors(limit(refs=['D2']), None, audit()), [])     # D2 is not audited: nothing to compare
        self.assertEqual(ref_errors(limit(refs=['Q2'])), [])                     # no audit at hand

    def test_the_source_is_matched_by_refdes_identity_model_or_document_path(self):
        for source in ('evidence/ds/U1.txt', 'evidence/ds/UCC28740.txt', 'ds/TI-UCC28740.txt', '/docs/TI-UCC28740.pdf', 'ds/DS-U1.txt'):
            self.assertEqual(rf.material_of_source(audit(), source)['material_id'], 'DS-U1', source)
        self.assertIsNone(rf.material_of_source(audit(), 'evidence/ds/D2.txt'))
        self.assertIsNone(rf.material_of_source(None, DS))

    def test_the_gate_reads_the_audit_the_plan_froze(self):
        fn = bias_function('PASS')
        fn['conditions'][2]['refs'] = ['Q2']                     # U1's VCC(off) attributed to the MOSFET
        p, r, db = ledger(fn)
        checks = {c['id']: c for c in r['checks']}
        self.assertFalse([e for e in rf.validate_functions(p, r, checks, (), db) if 'AO3400' in e])   # no audit: not checked
        p['review_inputs'] = {'datasheet_audit': audit()}       # as lint.py freezes it (revision_impact.input_snapshot)
        self.assertIs(rf.plan_datasheet_audit(p), p['review_inputs']['datasheet_audit'])
        self.assertIsNone(rf.plan_datasheet_audit({'review_inputs': 'x'}))
        errors = rf.validate_functions(p, r, checks, (), db)   # validate_review hands the plan on
        self.assertTrue(any('conditions[c3]' in e and 'AOS-AO3400.pdf for Q2' in e for e in errors), errors)


class OutsideFunctionHintTests(unittest.TestCase):
    def test_a_ref_outside_the_function_is_a_hint_not_an_error(self):
        p, r, db = ledger(bias_function('PASS'))     # c3/c4 are about U1, which FN-BIAS's objects do not hold
        out = vr.validate_review(p, r, db)
        self.assertTrue(out['valid'], out['errors'])
        hints = [h for h in out['quality_screening']['candidates'] if h['code'] == 'CONDITION_REF_OUTSIDE_FUNCTION']
        self.assertEqual(sorted((h['key'], h['refs']) for h in hints), [('c3', ['U1']), ('c4', ['U1'])])
        self.assertIn('FN-BIAS/conditions[c3] is about U1', hints[0]['message'])

    def test_a_member_rows_part_is_inside_the_function(self):
        fn = bias_function('PASS')
        plan = {'checks': [{'id': 'DEV-C05.U1', 'object': {'ref': 'U1'}}],
                'functions': [{'id': 'FN-BIAS', 'members': [{'check_id': 'DEV-C05.U1'}]}]}
        self.assertEqual(rf.condition_ref_hints([fn], plan), [])
        self.assertEqual([h['key'] for h in rf.condition_ref_hints([fn], None)], ['c3', 'c4'])
        fn['objects'] = {'nets': ['VCC']}                  # a function about nets only: nothing to be outside of
        self.assertEqual(rf.condition_ref_hints([fn], None), [])


class ParameterSheetTests(unittest.TestCase):
    def test_the_sheet_has_one_row_per_part_with_its_documents_pages_kinds_and_uses(self):
        sheet = rf.parameter_sheet([bias_function('PASS')])
        self.assertEqual([row['ref'] for row in sheet], ['D2', 'Q2', 'U1'])
        u1 = sheet[2]
        self.assertEqual(u1['counts'], {'total': 2, 'guaranteed': 1, 'typical': 0, 'clauses': 1})
        self.assertEqual(u1['sources'], [{'source': DS, 'pages': [7, 9]}])
        self.assertEqual(u1['functions'], ['FN-BIAS'])
        vcc = u1['parameters'][0]
        self.assertEqual((vcc['condition'], vcc['parameter'], vcc['word'], vcc['limit'], vcc['unit'], vcc['used_in']),
                         ('c3', 'VCC(off) max 8.8 V', 'vcc(off)', {'max': 8.8}, 'V', ['余量：VCC(off) max 8.8 V']))
        self.assertEqual(sheet[0]['parameters'][0]['used_in'], ['余量：VCC(off) max 8.8 V'])   # c1 is a basis condition
        self.assertEqual(rf.parameter_sheet([{'id': 'FN-X', 'conditions': [limit()]}]), [])   # no refs, no row
        self.assertEqual(rf.pages_of('p13 Feedback, p21 补偿网络'), [13, 21])
        self.assertEqual(rf.pages_of('Fig. 5'), [])
        self.assertEqual(rf.parameter_word('VGS(th) 1.0–2.0 V @250 µA'), 'vgs(th)')

    def test_judgements_fails_and_gap_edges_count_as_uses(self):
        fn = bias_function('OPEN')
        fn['judgements'] = [{'aspect': '偏置路径连接', 'conditions': ['c4', 'c5'], 'says': 'x'}]
        uses = rf.condition_uses(fn)
        self.assertEqual(uses['c4'], ['判断：偏置路径连接'])
        self.assertEqual(uses['c3'], ['余量：VCC(off) max 8.8 V', '开放项：AUX-5V-MIN'])   # the gap's edge goes via c3

    def test_the_gate_and_the_report_carry_the_sheet(self):
        p, r, db = ledger(bias_function('PASS'))
        gate = vr.validate_review(p, r, db)
        self.assertEqual([row['ref'] for row in gate['parameter_sheet']], ['D2', 'Q2', 'U1'])
        compact = render(p, r, gate)
        self.assertIn('## 器件参数表', compact)
        self.assertIn('| U1 | U1.txt（p7–9） | 2 | 1 / 0 / 1 | FN-BIAS |', compact)
        self.assertNotIn('逐参数', compact)
        full = render(p, r, gate, detail='full')
        self.assertIn('| U1 | VCC(off) max 8.8 V | ≤ 8.8 V | −10..105 °C | 保证值 | U1.txt p7 Table 7 | 余量：VCC(off) max 8.8 V |', full)
        self.assertIn('| Q2 | VGS(th) 1.0–2.0 V @250 µA | 1.0–2.0 V |', full)
        self.assertIn('| 强制条款 |', full)
        without = copy.deepcopy(gate)
        without['parameter_sheet'] = []
        self.assertNotIn('器件参数表', render(p, r, without))

    def test_the_results_format_is_13_and_a_format_6_record_is_refused(self):
        self.assertEqual(results_model.SCHEMA_VERSION, 13)
        found = results_model.shape_errors({'schema_version': 6, 'functions': [], 'checks': []})
        self.assertTrue(any('schema_version must be 13' in e for e in found), found)


class CompareTests(unittest.TestCase):
    def pair(self):
        a, b = side('BIAS', ['RUN'], 'PASS'), side('BIAS', ['RUN'], 'PASS')
        fa, fb = bias_function('PASS'), bias_function('PASS')
        fb['conditions'][2]['limit']['max'] = 9.0                            # U1 VCC(off) read differently
        fb['conditions'][2]['says'] = 'VCC(off) max 9.0 V'
        del fb['conditions'][0]                                               # B never read D2's VF
        fb['conditions'].append(limit(id='d3', refs=['D3'], says='VRRM 100 V', limit={'max': 100, 'unit': 'V'}))
        a['results']['functions'], b['results']['functions'] = [fa], [fb]
        return a, b

    def test_parameters_are_aligned_by_part_word_and_unit(self):
        got = cr.parameter_refs(*self.pair())
        self.assertEqual((got['A'], got['B'], got['shared'], got['agree']), (3, 3, 2, 1))
        self.assertEqual([(d['ref'], d['parameter'], d['unit']) for d in got['differ']], [('U1', 'vcc(off)', 'v')])
        self.assertEqual((got['differ'][0]['A'][0]['limit'], got['differ'][0]['B'][0]['limit']), ({'max': 8.8}, {'max': 9.0}))
        self.assertEqual([(o['ref'], o['parameter']) for o in got['only_A']], [('D2', 'vf')])
        self.assertEqual([(o['ref'], o['parameter']) for o in got['only_B']], [('D3', 'vrrm')])

    def test_the_markdown_has_the_section(self):
        text = cr.markdown(cr.compare(*self.pair()))
        self.assertIn('## 逐器件参数引用', text)
        self.assertIn('两边都引的 2 个，其中限值相同 1 个、不同 1 个；只有一边读了的 A 1 个、B 1 个', text)
        self.assertIn('| U1 | vcc(off) v | max 8.8（FN-BIAS） | max 9.0（FN-BIAS） |', text)
        self.assertIn('只在 B 引用：D3 vrrm v', text)


if __name__ == '__main__':
    unittest.main()

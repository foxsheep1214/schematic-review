"""Requirements are transcribed by a tool, never retyped (fixed requirements, step 1).

On the R5 bench both reviewers took the same 19 requirement ids from one requirement table and agreed on every
status, yet not one transcribed text matched: the table has a requirement column and a boundary column, and each
reviewer joined, cut and punctuated them their own way. `requirements_extract.py` reads the table verbatim, each
column apart, with the section, a file:line locator and the file's digest; the intent names the source and states
for each requirement only what the reviewer decides. Every source requirement must be in the intent and every intent
requirement in the source. A requirement row's clauses split the original text; its criterion comes from the
category templates (test_requirement_categories).
"""
import copy
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import catalog
import requirements_extract as rx
from plan_review import build_review_plan, validate_intent

DOC = """# 产品需求

说明文字，不是需求。

## 当前已确认要求

| ID | 当前要求 | 适用边界 |
|---|---|---|
| REQ-IN-01 | 工作输入 9–36 V DC | 40 V 持续 100 ms 不损坏 |
| REQ-TEMP-01 | 工作环境温度 −20～+60°C | 自然散热 |

## 其他

| 版本 | 说明 |
|---|---|
| V1.2 | 修订记录：第一列不是需求编号，这张表不是需求表 |

## 待定

- REQ-OPEN-01：输出纹波限值待系统确定
"""


def write(text=DOC, root=None):
    root = Path(root or tempfile.mkdtemp(prefix='sr-req-'))
    path = root / 'requirements.md'
    path.write_text(text, encoding='utf-8')
    return path


def source(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


CATEGORIES = {'REQ-IN-01': ['INPUT_RANGE'], 'REQ-TEMP-01': ['ENVIRONMENT'], 'REQ-OPEN-01': ['OUTPUT_SPEC']}


def entries(categories=None, interpretations=None):
    categories, interpretations = dict(CATEGORIES, **(categories or {})), interpretations or {}
    return [{'id': rid, 'categories': categories[rid],
             'interpretation': interpretations.get(rid, 'synthetic reading of ' + rid), 'status': status}
            for rid, status in (('REQ-IN-01', 'CONFIRMED'), ('REQ-TEMP-01', 'CONFIRMED'), ('REQ-OPEN-01', 'OPEN'))]


def doc_for(texts):
    """requirement_source for a one-column requirement table {id: text} (used by other tests)."""
    rows = ''.join('| %s | %s |\n' % (rid, t) for rid, t in texts.items())
    return source(write('# 需求\n\n| ID | 要求 |\n|---|---|\n' + rows))


def requirement_intent(path=None, categories=None, interpretations=None):
    """The intent fields a synthetic board needs for its requirements (used by other tests)."""
    path = path or write()
    return {'requirement_source': source(path), 'requirements': entries(categories, interpretations)}


class ExtractTests(unittest.TestCase):
    def setUp(self):
        self.path = write()
        self.out = rx.extract(self.path)

    def test_a_table_is_read_verbatim_one_column_apart(self):
        self.assertEqual(self.out['errors'], [])
        first = self.out['items'][0]
        self.assertEqual(first['id'], 'REQ-IN-01')
        self.assertEqual(first['columns'], [{'name': '当前要求', 'text': '工作输入 9–36 V DC'},
                                            {'name': '适用边界', 'text': '40 V 持续 100 ms 不损坏'}])
        self.assertEqual(first['section'], '当前已确认要求')
        self.assertEqual(first['locator'], str(self.path) + ':9')
        self.assertEqual(self.out['sha256'], hashlib.sha256(self.path.read_bytes()).hexdigest())

    def test_only_tables_keyed_by_id_and_id_list_items_are_requirements(self):
        self.assertEqual([i['id'] for i in self.out['items']], ['REQ-IN-01', 'REQ-TEMP-01', 'REQ-OPEN-01'])
        listed = self.out['items'][2]
        self.assertEqual(listed['columns'], [{'name': 'text', 'text': '输出纹波限值待系统确定'}])
        self.assertEqual(listed['section'], '待定')

    def test_two_reads_are_identical_and_a_repeated_id_is_an_error(self):
        self.assertEqual(rx.extract(self.path), self.out)
        doubled = write(DOC + '\n- REQ-IN-01：重复的编号\n')
        self.assertTrue(any('REQ-IN-01' in e for e in rx.extract(doubled)['errors']))

    def test_the_original_text_is_the_columns_in_order(self):
        self.assertEqual(rx.text(self.out['items'][0]), '工作输入 9–36 V DC；40 V 持续 100 ms 不损坏')


class IntentTests(unittest.TestCase):
    def setUp(self):
        self.path = write()
        self.intent = dict({'schema_version': 4}, **requirement_intent(self.path))

    def errors(self, intent):
        return [e for e in validate_intent(intent) if 'requirement' in e]

    def test_a_complete_reference_is_accepted(self):
        self.assertEqual(self.errors(self.intent), [])

    def test_text_or_citation_written_in_the_intent_is_refused(self):
        for field in ('text', 'citation'):
            intent = copy.deepcopy(self.intent)
            intent['requirements'][0][field] = 'retyped'
            self.assertTrue(any(field in e and 'requirements_extract' in e for e in self.errors(intent)), field)

    def test_a_missing_or_stale_source_is_refused(self):
        intent = copy.deepcopy(self.intent)
        del intent['requirement_source']
        self.assertTrue(any('requirement_source' in e for e in self.errors(intent)))
        self.path.write_text(DOC.replace('9–36', '8–36'), encoding='utf-8')
        self.assertTrue(any('sha256' in e for e in self.errors(self.intent)))

    def test_every_source_requirement_is_in_the_intent_and_every_intent_requirement_in_the_source(self):
        dropped = copy.deepcopy(self.intent)
        dropped['requirements'] = dropped['requirements'][:2]
        self.assertTrue(any('REQ-OPEN-01' in e for e in self.errors(dropped)))
        invented = copy.deepcopy(self.intent)
        invented['requirements'].append({'id': 'REQ-NEW-01', 'categories': ['OUTPUT_SPEC'], 'interpretation': 'x',
                                         'status': 'CONFIRMED'})
        self.assertTrue(any('REQ-NEW-01' in e for e in self.errors(invented)))


class PlanRowTests(unittest.TestCase):
    def test_a_requirement_row_carries_its_source_text_and_locator(self):
        path = write()
        plan = build_review_plan({'parts': {}, 'nets': {}, 'pin2net': {}}, dict({'schema_version': 4}, **requirement_intent(path)))
        row = next(c for c in plan['checks'] if c['rule'] == 'REQ-D01' and c['object']['requirement_id'] == 'REQ-IN-01')
        self.assertEqual(row['source_text']['locator'], str(path) + ':9')
        self.assertEqual([c['text'] for c in row['source_text']['columns']], ['工作输入 9–36 V DC', '40 V 持续 100 ms 不损坏'])
        self.assertEqual(row['interpretation'], 'synthetic reading of REQ-IN-01')
        self.assertIn(str(path) + ':9', row['trigger'])

    def test_the_rule_says_clauses_split_the_original_text_and_the_criterion_is_not_a_copy(self):
        criterion = catalog.BY_ID['REQ-D01'].criterion
        self.assertNotIn('验收判据取需求原文', criterion)
        self.assertIn('拼接等于原文', criterion)
        self.assertIn('模板', criterion)


if __name__ == '__main__':
    unittest.main()

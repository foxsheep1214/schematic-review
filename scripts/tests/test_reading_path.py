"""Item 5 of the 2026-10-26 SR review: the reviewer's reading path. Every reference names its readers on its third line
(审查员 / SR 维护者 / 审查员与 SR 维护者), SKILL.md's 参考文件 table carries the same reader for every reference, the
execution flow (①–⑤) links no maintainer-only reference, and — since the split of 2026-10-26 — each step's linked
references do not grow past the recorded size (a ratchet per step: lower it when a document shrinks, never raise it
without saying why in the ledger). The step budget is what a reviewer loads at that step besides SKILL.md itself.
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
REFERENCES = sorted((ROOT / 'references').glob('*.md'))
SKILL = (ROOT / 'SKILL.md').read_text(encoding='utf-8')
READERS = ('审查员与 SR 维护者', 'SR 维护者', '审查员')
READER_RE = re.compile(r'^> 读者：(审查员与 SR 维护者|SR 维护者|审查员)(?:（[^）\n]*）)?。$', re.M)
# Bytes of the references each step of the execution flow links, measured 2026-10-26 after the split (see the ledger):
# ① 192321, ② 184974, ③ 220670, ④ 117517, ⑤ 54796. Before the split every step carried the whole 117 KB ledger
# document and the 131 KB rule table (685 KB in all); ① also carried the 70 KB checkers' document for its conventions.
STEP_MAX_BYTES = {'①': 193_000, '②': 185_000, '③': 224_000, '④': 119_000, '⑤': 55_000}


def section(text, title):
    start = text.index(title)
    end = text.find('\n## ', start + len(title))
    return text[start:end if end != -1 else None]


def reader_of(path):
    head = path.read_text(encoding='utf-8').split('\n', 4)
    found = [m.group(1) for line in head[:4] for m in [READER_RE.match(line)] if m]
    return found[0] if found else None


def skill_table():
    """{file: reader} from the 参考文件 table of SKILL.md."""
    out = {}
    for line in section(SKILL, '## 参考文件').splitlines():
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) != 3 or cells[0] in ('读者',) or set(cells[0]) <= set('-'):
            continue
        for name in re.findall(r'\(references/([a-z0-9-]+\.md)\)', cells[2]):
            out[name] = cells[0]
    return out


def step_links():
    """{step mark: sorted references the step's section of the execution flow links}."""
    out = {}
    for part in re.split(r'\n(?=### )', section(SKILL, '## 执行流程'))[1:]:
        mark = part[4:5]
        if mark in STEP_MAX_BYTES:
            out[mark] = sorted(set(re.findall(r'references/([a-z0-9-]+\.md)', part)))
    return out


class ReadingPathTests(unittest.TestCase):
    def test_every_reference_names_its_readers(self):
        missing = [p.name for p in REFERENCES if reader_of(p) is None]
        self.assertEqual(missing, [], 'add "> 读者：审查员 / SR 维护者 / 审查员与 SR 维护者。" under the title')

    def test_the_skill_table_lists_every_reference_once_with_the_same_reader(self):
        table = skill_table()
        self.assertEqual(sorted(table), [p.name for p in REFERENCES])
        for p in REFERENCES:
            self.assertEqual(table[p.name], reader_of(p), p.name)

    def test_the_execution_flow_links_no_maintainer_only_reference(self):
        maintainer_only = {p.name for p in REFERENCES if reader_of(p) == 'SR 维护者'}
        self.assertTrue(maintainer_only)
        linked = set(re.findall(r'references/([a-z0-9-]+\.md)', section(SKILL, '## 执行流程')))
        self.assertEqual(sorted(linked & maintainer_only), [])

    def test_every_step_links_something_and_the_links_resolve(self):
        links = step_links()
        self.assertEqual(sorted(links), sorted(STEP_MAX_BYTES))
        names = {p.name for p in REFERENCES}
        for mark, docs in links.items():
            self.assertTrue(docs, mark)
            self.assertEqual(sorted(set(docs) - names), [], mark)

    def test_no_step_grows_past_its_record(self):
        for mark, docs in step_links().items():
            size = sum((ROOT / 'references' / d).stat().st_size for d in docs)
            self.assertLessEqual(size, STEP_MAX_BYTES[mark],
                                 'step %s links %d bytes over %d documents (%s); shrink a document, link a smaller one, or '
                                 'say in the ledger why the record moves' % (mark, size, len(docs), ', '.join(docs)))


if __name__ == '__main__':
    unittest.main()

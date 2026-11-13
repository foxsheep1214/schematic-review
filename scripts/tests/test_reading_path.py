"""Item 5 of the 2026-10-26 SR review: the reviewer's reading path. Every reference names its readers on its third line
(审查员 / SR 维护者 / 审查员与 SR 维护者), SKILL.md's 参考文件 table carries the same reader for every reference, the
execution flow (①–⑤) links no maintainer-only reference, and each step's linked references stay within a fixed byte
budget (the step budget is what a reviewer loads at that step besides SKILL.md itself).
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
# The framework's files are not under references/: SKILL.md's 参考文件 table names them by their framework path, not as links
REFERENCES = sorted((ROOT / 'references').rglob('*.md'))


def rel(path):
    """A reference's path as SKILL.md links it: 'intent-format.md'."""
    return str(path.relative_to(ROOT / 'references'))
SKILL = (ROOT / 'SKILL.md').read_text(encoding='utf-8')
READERS = ('审查员与 SR 维护者', 'SR 维护者', '审查员')
READER_RE = re.compile(r'^> 读者：(审查员与 SR 维护者|SR 维护者|审查员)(?:（[^）\n]*）)?。$', re.M)
# Budget of the references each step of the execution flow links, in bytes: what a reviewer loads at that step besides
# SKILL.md. A fixed ceiling with headroom (2026-11-11, user: 按照上面的方向改): the former only-decrease ratchet made a
# correction that completes a list harder to land than leaving the list short, and nine of the 35 stale statements
# found that day were lists left short. Measured 2026-11-11: ① 179596, ② 161859, ③ 228703, ④ 125191, ⑤ 38175.
# Raising a budget is said in the ledger; the history of the old record is in the ledger and in git.
STEP_MAX_BYTES = {'①': 190_000, '②': 170_000, '③': 240_000, '④': 132_000, '⑤': 40_000}


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
        missing = [rel(p) for p in REFERENCES if reader_of(p) is None]
        self.assertEqual(missing, [], 'add "> 读者：审查员 / SR 维护者 / 审查员与 SR 维护者。" under the title')

    def test_the_skill_table_lists_every_reference_once_with_the_same_reader(self):
        table = skill_table()
        self.assertEqual(sorted(table), [rel(p) for p in REFERENCES])
        for p in REFERENCES:
            self.assertEqual(table[rel(p)], reader_of(p), rel(p))

    def test_the_execution_flow_links_no_maintainer_only_reference(self):
        maintainer_only = {rel(p) for p in REFERENCES if reader_of(p) == 'SR 维护者'}
        self.assertTrue(maintainer_only)
        linked = set(re.findall(r'references/([a-z0-9-]+\.md)', section(SKILL, '## 执行流程')))
        self.assertEqual(sorted(linked & maintainer_only), [])

    def test_every_step_links_something_and_the_links_resolve(self):
        links = step_links()
        self.assertEqual(sorted(links), sorted(STEP_MAX_BYTES))
        names = {rel(p) for p in REFERENCES}
        for mark, docs in links.items():
            self.assertTrue(docs, mark)
            self.assertEqual(sorted(set(docs) - names), [], mark)

    def test_no_step_exceeds_its_budget(self):
        for mark, docs in step_links().items():
            size = sum((ROOT / 'references' / d).stat().st_size for d in docs)
            self.assertLessEqual(size, STEP_MAX_BYTES[mark],
                                 'step %s links %d bytes over %d documents (%s); shrink a document, link a smaller one, or '
                                 'raise the budget and say why in the ledger' % (mark, size, len(docs), ', '.join(docs)))


if __name__ == '__main__':
    unittest.main()

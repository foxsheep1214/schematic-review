"""Item 5 of the 2026-10-26 SR review: the reviewer's reading path. Every reference names its readers on its third line
(审查员 / SR 维护者 / 审查员与 SR 维护者), SKILL.md's 参考文件 table carries the same reader for every reference, the
execution flow (①–⑤) links no maintainer-only reference, and the reviewer's path — SKILL.md plus the references a
reviewer reads — does not grow past the recorded size (a ratchet: lower it when a document shrinks, never raise it
without saying why in the ledger).
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
REVIEWER_PATH_MAX_BYTES = 683_000     # SKILL.md + the references a reviewer reads, measured 2026-10-26 (see the ledger)


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

    def test_the_reviewer_path_does_not_grow_past_the_record(self):
        docs = [p for p in REFERENCES if reader_of(p) != 'SR 维护者']
        size = len(SKILL.encode('utf-8')) + sum(p.stat().st_size for p in docs)
        self.assertLessEqual(size, REVIEWER_PATH_MAX_BYTES,
                             'the reviewer path is %d bytes over %d documents; shrink a document or say in the ledger why '
                             'the record moves' % (size, len(docs) + 1))


if __name__ == '__main__':
    unittest.main()

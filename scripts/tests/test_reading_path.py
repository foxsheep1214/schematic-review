"""Item 5 of the 2026-10-26 SR review: the reviewer's reading path. Every reference names its readers on its third line
(审查员 / SR 维护者 / 审查员与 SR 维护者), SKILL.md's 参考文件 table carries the same reader for every reference, the
execution flow (①–⑤) links no maintainer-only reference, and every step links references that exist. There is no size
limit on what a step links (user 2026-11-12: 取消这个定量的限制，但是在以后还是要保证skill逻辑清晰): the skill grows as its
ability grows, and clarity is kept by the reader marks and the single reading path these tests check, not by a byte count.
The flow is SKILL.md's step table plus one step file per step under references/ (step-1-intake.md …); a step's links
are the links its step file makes. pipeline-overview.md is read at every step with SKILL.md.
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
STEP_FILES = {'①': 'step-1-intake.md', '②': 'step-2-plan.md', '③': 'step-3-judge.md', '④': 'step-4-validate.md',
              '⑤': 'step-5-report.md'}
# A link a reference makes to a sibling reference: '](intent-format.md#…' (a link from SKILL.md carries 'references/').
SIBLING_LINK = re.compile(r'\]\(([a-z0-9-]+\.md)')
# Read at every step together with SKILL.md; not counted as a link of any one step.
EVERY_STEP = {'pipeline-overview.md'}


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


def step_text(mark):
    return (ROOT / 'references' / STEP_FILES[mark]).read_text(encoding='utf-8')


def step_links():
    """{step mark: sorted references the step's file links, the step file itself left out}."""
    return {mark: sorted(set(SIBLING_LINK.findall(step_text(mark))) - {name} - EVERY_STEP)
            for mark, name in STEP_FILES.items()}


def flow_links():
    """Every reference the execution flow links: SKILL.md's step table and the five step files."""
    linked = set(re.findall(r'references/([a-z0-9-]+\.md)', section(SKILL, '## 执行流程')))
    for mark in STEP_FILES:
        linked |= set(SIBLING_LINK.findall(step_text(mark)))
    return linked


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
        self.assertEqual(sorted(flow_links() & maintainer_only), [])

    def test_the_step_table_links_each_step_file_on_its_row(self):
        rows = [line for line in section(SKILL, '## 执行流程').splitlines() if line.startswith('| ')]
        for mark, name in STEP_FILES.items():
            self.assertTrue(any(line.startswith('| %s ' % mark) and '(references/%s)' % name in line for line in rows),
                            mark)
            self.assertTrue(step_text(mark).startswith('# %s ' % mark), name)

    def test_every_step_links_something_and_the_links_resolve(self):
        links = step_links()
        self.assertEqual(sorted(links), sorted(STEP_FILES))
        names = {rel(p) for p in REFERENCES}
        for mark, docs in links.items():
            self.assertTrue(docs, mark)
            self.assertEqual(sorted(set(docs) - names), [], mark)


if __name__ == '__main__':
    unittest.main()

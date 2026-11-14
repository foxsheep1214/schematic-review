"""The architecture SKILL.md and references/architecture.md state is the one the code has: every script sits in one
ring, the flow calls only entry scripts, and the file format versions named there are the code's."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
SCRIPTS = ROOT / 'scripts'
DOC = (ROOT / 'references' / 'architecture.md').read_text(encoding='utf-8')
SKILL = (ROOT / 'SKILL.md').read_text(encoding='utf-8')
NAME = re.compile(r'`(\w+\.py|checkers/)`')
# The review flow: SKILL.md's step table, the five step files, and the revision section of revision-review.md.
STEP_FILES = ('step-1-intake.md', 'step-2-plan.md', 'step-3-judge.md', 'step-4-validate.md', 'step-5-report.md')


def section(text, title):
    start = text.index(title)
    end = text.find('\n## ', start + len(title))
    return text[start:end if end != -1 else None]


def script_table():
    """{name: [(ring, column)]} from the table of section 二; columns are entry, tool, library."""
    out = {}
    for line in section(DOC, '## 二、').splitlines():
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) != 4 or not cells[0] or cells[0] in ('步骤',) or set(cells[0]) <= set('-'):
            continue
        for column, cell in zip(('entry', 'tool', 'library'), cells[1:]):
            for name in NAME.findall(cell):
                out.setdefault(name, []).append((cells[0], column))
    return out


class ArchitectureTests(unittest.TestCase):
    def test_every_script_sits_in_exactly_one_ring(self):
        table = script_table()
        present = {p.name for p in SCRIPTS.glob('*.py')} | {'checkers/'}
        self.assertEqual(sorted(present - set(table)), [], 'scripts not placed in references/architecture.md')
        self.assertEqual(sorted(set(table) - present), [], 'references/architecture.md lists scripts that do not exist')
        twice = {n: rings for n, rings in table.items() if len(rings) > 1}
        self.assertEqual(twice, {}, 'a script is placed twice')

    def test_the_review_flow_calls_only_entry_scripts(self):
        table = script_table()
        revision = (ROOT / 'references' / 'revision-review.md').read_text(encoding='utf-8')
        flow = [section(SKILL, '## 执行流程'), section(revision, '## 改版复审（H）')]
        flow += [(ROOT / 'references' / name).read_text(encoding='utf-8') for name in STEP_FILES]
        called = set(re.findall(r'python3 scripts/(\w+\.py)', '\n'.join(flow)))
        self.assertTrue(called)
        not_entry = sorted(n for n in called if table.get(n, [(None, None)])[0][1] != 'entry')
        self.assertEqual(not_entry, [], 'SKILL.md calls scripts that are not entry scripts')

    def test_format_versions_are_the_codes(self):
        import audit_datasheets
        import knowledge_checklist
        import circuit_candidates
        import electrical_contract
        import plan_review
        import requirements_extract
        import results_model
        files = {}
        for line in section(DOC, '## 一、').splitlines():
            cells = [c.strip() for c in line.strip().strip('|').split('|')]
            if len(cells) == 5 and cells[3].isdigit():
                files[cells[0]] = int(cells[3])
        self.assertEqual(files, {
            '`requirement_source`（需求原文抄录）': requirements_extract.SCHEMA_VERSION,
            '`datasheet-audit.json`': audit_datasheets.AUDIT_SCHEMA_VERSION,
            '`datasheet-resolution.json`': audit_datasheets.RESOLUTION_SCHEMA_VERSION,
            '`intent.json`': plan_review.INTENT_SCHEMA_VERSION,
            '`record/circuit-candidates.json`': circuit_candidates.SCHEMA_VERSION,
            '`review-plan.json`': electrical_contract.PLAN_SCHEMA_VERSION,
            '`review-results.json`': results_model.SCHEMA_VERSION,
            '`knowledge-checklist.json`': knowledge_checklist.SCHEMA_VERSION})

    def test_skill_opens_with_the_architecture_and_the_change_rule(self):
        self.assertLess(SKILL.index('## 架构'), SKILL.index('## 审查纪律'))
        arch = section(SKILL, '## 架构')
        for ring in ('① 读入', '② 出计划', '③ 判断', '④ 校验', '⑤ 出报告'):
            self.assertIn(ring, arch)
        self.assertIn('**改架构先问人**', arch)
        self.assertIn('references/architecture.md', arch)
        self.assertIn('references/pipeline-overview.md', arch)
        rule = section(DOC, '## 零、')    # the change rule's list is the maintainer's, in the architecture page
        self.assertIn('**改架构先问人**：修改 SR 本身时，下面任何一项都算架构调整', rule)
        overview = (ROOT / 'references' / 'pipeline-overview.md').read_text(encoding='utf-8')
        self.assertIn('**不变的决定**', section(overview, '## 不变的决定'))   # the reviewer reads them every review
        self.assertNotIn('**不变的决定**', DOC)


if __name__ == '__main__':
    unittest.main()

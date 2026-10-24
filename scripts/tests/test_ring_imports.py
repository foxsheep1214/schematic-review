"""A script imports nothing from a later ring (5.8 proposal, user: 做；并进 contract；单列新库；一次改完).

references/architecture.md puts every script in a ring, ① 读入 → ② 出计划 → ③ 判断 → ④ 校验 → ⑤ 出报告; an earlier ring
must not depend on a later one. The self-check of 2026-10-24 found twelve imports the other way (the plan importing the
gate's identifiers, the row derivation importing the gate's reading of a function verdict, the netlist parser importing
the checkers' part kinds). Revision review and SR maintenance stand outside the order.
"""
import ast
import re
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
ARCHITECTURE = SCRIPTS.parent / 'references' / 'architecture.md'
ORDER = ('① 读入', '② 出计划', '③ 判断', '④ 校验', '⑤ 出报告')
OUTSIDE = ('复审', '维护 SR')


def rings():
    """module name -> ring, from the script table of architecture.md (checkers/ is one module group)."""
    table = ARCHITECTURE.read_text(encoding='utf-8').split('## 二、')[1].split('\n## ')[0]
    out = {}
    for line in table.splitlines():
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if cells and cells[0] in ORDER + OUTSIDE:
            for cell in cells[1:]:
                for name in re.findall(r'`([a-z_0-9]+)\.py', cell):
                    out[name] = cells[0]
                if '`checkers/`' in cell:
                    out['checkers'] = cells[0]
    return out


def imported(path, known):
    """The SR modules a source file imports, at any depth (a late import is still a dependency)."""
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
        names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                 else [node.module] if isinstance(node, ast.ImportFrom) and node.module and not node.level else [])
        for name in names:
            head = name.split('.')[0]
            if head in known:
                found.add(head)
    return found


class RingImportTests(unittest.TestCase):
    def test_every_script_has_a_ring(self):
        ring = rings()
        self.assertEqual(sorted(p.stem for p in SCRIPTS.glob('*.py') if p.stem not in ring), [])

    def test_no_import_reaches_a_later_ring(self):
        ring = rings()
        rank = {r: i for i, r in enumerate(ORDER)}
        backward = []
        files = [(p.stem, p) for p in sorted(SCRIPTS.glob('*.py'))] + [('checkers', p) for p in sorted((SCRIPTS / 'checkers').glob('*.py'))]
        for name, path in files:
            if ring.get(name) not in rank:
                continue
            for other in sorted(imported(path, ring) - {name}):
                if ring[other] in rank and rank[ring[other]] > rank[ring[name]]:
                    backward.append('%s (%s) imports %s (%s)' % (path.relative_to(SCRIPTS), ring[name], other, ring[other]))
        self.assertEqual(backward, [])


if __name__ == '__main__':
    unittest.main()

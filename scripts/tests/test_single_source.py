"""Nothing is left behind (user 2026-11-11: 类似的，也检查修改SR技能，让SR的技能也简洁清晰明确).

The stale text found on 2026-11-11 was of two kinds: documents naming scripts and files that no longer exist
(workflow-handoff.md's contract.py and adapters.py), and code nobody uses. The reading-path test already keeps each
reference's readers and size; this one keeps the names in the documents and the code real.
"""
import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'scripts'
# Installed read-only from the design guidelines and the knowledge framework; not the skill's to edit.
SHARED = {'guideline_criteria.py', 'stress_check.py'}
INSTALLED = (ROOT / 'references' / 'knowledge', ROOT / 'references' / 'shared')
SCRIPT_NAME = re.compile(r'(?<![\w/.-])([a-z][a-z0-9_]*\.py)\b')
LINK = re.compile(r'\]\(([^)#\s]+)')
# ASG's scripts, named where the hand-off to ASG is described.
OTHER_SKILL = {'verify_schematic.py', 'pack_design.py', 'render_design_report.py', 'audit_design_closure.py'}


def docs():
    return [ROOT / 'README.md', ROOT / 'SKILL.md'] + sorted(
        p for p in (ROOT / 'references').rglob('*.md') if not any(d in p.parents for d in INSTALLED))


def sources():
    return sorted(p for p in SCRIPTS.rglob('*.py') if '__pycache__' not in p.parts and 'tests' not in p.parts)


def python_files():
    return sorted(p for d in (SCRIPTS, ROOT / 'evals') for p in d.rglob('*.py') if '__pycache__' not in p.parts)


class SingleSourceTests(unittest.TestCase):
    def test_every_script_a_document_names_exists(self):
        known = {p.name for p in python_files()} | OTHER_SKILL
        missing = []
        for path in docs():
            for n, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
                if '删' in line:      # the record of a removal names what was removed
                    continue
                missing += ['%s:%d %s' % (path.relative_to(ROOT), n, name)
                            for name in SCRIPT_NAME.findall(line) if name not in known]
        self.assertEqual([], missing, '文档提到的脚本不存在：改文档，或在记删除的那一行写“删”')

    def test_every_relative_link_opens(self):
        broken = []
        for path in docs():
            for n, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
                for target in LINK.findall(line):
                    if not re.match(r'[a-z]+:', target) and not (path.parent / target).exists():
                        broken.append('%s:%d %s' % (path.relative_to(ROOT), n, target))
        self.assertEqual([], broken)

    def test_every_script_is_imported_or_documented(self):
        text = ''.join(p.read_text(encoding='utf-8') for p in docs())
        code = {p: p.read_text(encoding='utf-8') for p in python_files()}
        unused = []
        for path in sources():
            if path.name == '__init__.py':
                continue
            word = re.compile(r'(?<!\w)%s(?!\w)' % re.escape(path.stem))
            if path.name not in text and not any(word.search(src) for other, src in code.items() if other != path):
                unused.append(str(path.relative_to(ROOT)))
        self.assertEqual([], unused, '没有脚本导入、文档也没提到的模块：删掉，或写明谁用它')

    def test_every_top_level_name_is_used_somewhere(self):
        code = {p: p.read_text(encoding='utf-8') for p in python_files()}
        unused = []
        for path in sources():
            if path.name in SHARED:
                continue
            for node in ast.parse(code[path]).body:
                names = []
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    names = [node.name]
                elif isinstance(node, ast.Assign):
                    names = [t.id for t in node.targets if isinstance(t, ast.Name)]
                for name in names:
                    word = re.compile(r'(?<!\w)%s(?!\w)' % re.escape(name))
                    if name != 'main' and not name.startswith('__') and sum(len(word.findall(s)) for s in code.values()) <= 1:
                        unused.append('%s %s' % (path.relative_to(ROOT), name))
        self.assertEqual([], unused, '只定义、没有任何脚本、评测或测试用到的函数或常量')


if __name__ == '__main__':
    unittest.main()

"""One planning entry (SR self-check 2.9, user: 删 plan_review.main，只留 lint.py，plan_review.py 改归为库).

plan_review.py and lint.py each had a main that wrote the review plan, and the two had drifted apart (which checks they
ran on the intent, what they printed). lint.py is now the only command that writes a plan; plan_review.py is a library.
"""
import ast
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))


class OneEntryTests(unittest.TestCase):
    def test_plan_review_is_a_library(self):
        tree = ast.parse((SCRIPTS / 'plan_review.py').read_text(encoding='utf-8'))
        names = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
        self.assertNotIn('main', names)
        self.assertFalse(any(isinstance(n, ast.If) and 'main' in ast.dump(n.test) for n in tree.body))
        imported = {a.name for n in tree.body if isinstance(n, ast.Import) for a in n.names}
        self.assertNotIn('argparse', imported)

    def test_no_document_runs_plan_review_as_a_command(self):
        skill = SCRIPTS.parent
        texts = [skill / 'SKILL.md'] + sorted((skill / 'references').glob('*.md'))
        runs = [str(p.relative_to(skill)) for p in texts if 'python3 scripts/plan_review.py' in p.read_text(encoding='utf-8')
                or 'plan_review.py db.json' in p.read_text(encoding='utf-8')]
        self.assertEqual(runs, [])


if __name__ == '__main__':
    unittest.main()

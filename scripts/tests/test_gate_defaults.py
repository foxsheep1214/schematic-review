"""The gate a reviewer runs is strict on its own (SR self-check of 2026-10-24, 2.7, user: 改成必填).

Lenient defaults (no bindings asked, a plan without its dependency record not re-derived) stay for tests that call the
library directly; the command line asks for both without a flag.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from test_validate_review import fixture
import validate_review as vr


def gate(plan, results, db, *flags):
    with tempfile.TemporaryDirectory() as root:
        paths = []
        for name, data in (('plan', plan), ('results', results), ('db', db)):
            path = Path(root) / (name + '.json')
            path.write_text(json.dumps(data), encoding='utf-8')
            paths.append(str(path))
        out = Path(root) / 'gate.json'
        proc = subprocess.run([sys.executable, '-B', str(SCRIPTS / 'validate_review.py'), paths[0], paths[1], '--db',
                               paths[2], *flags, '--json', str(out)], capture_output=True, text=True)
        return proc, json.loads(out.read_text(encoding='utf-8')) if out.exists() else None


class GateDefaultTests(unittest.TestCase):
    def test_a_plan_without_its_dependency_record_is_refused_by_the_gate(self):
        p, r, db = fixture()
        self.assertNotIn('dependency_version', p)
        self.assertFalse([e for e in vr.validate_review(p, r, db)['errors'] if 'dependency_version' in e])
        self.assertTrue(any('dependency_version' in e for e in
                            vr.validate_review(p, r, db, require_dependencies=True)['errors']))
        _, out = gate(p, r, db)
        self.assertTrue(any('dependency_version' in e for e in out['errors']), out['errors'])

    def test_the_gate_asks_for_bindings_without_a_flag(self):
        source = (SCRIPTS / 'validate_review.py').read_text(encoding='utf-8')
        self.assertNotIn('--require-bindings', source)
        self.assertIn('require_bindings=True', source)


if __name__ == '__main__':
    unittest.main()

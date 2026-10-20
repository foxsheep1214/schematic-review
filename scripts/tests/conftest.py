"""Test tiers for pytest (unittest discover ignores this file and still runs everything).

    python3 -m pytest scripts/tests -m contract -q    every change: rule contracts, validator invariants, parsers
    python3 -m pytest scripts/tests -m wording -q     report wording: golden snapshots plus legacy wording asserts
    SR_UPDATE_GOLDEN=1 python3 -m pytest scripts/tests/test_golden_reports.py   rewrite the golden reports

A test is `wording` when at least half of its assert calls are assertIn/assertNotIn on a literal containing
Chinese text, or it lives in WORDING_FILES. A test is `contract` when its file is in CONTRACT_FILES and it is
not `wording`.
"""
import ast
import re
from pathlib import Path

import pytest

CONTRACT_FILES = {
    # rule contracts
    'test_rule_contracts.py',
    # validator invariants
    'test_validate_review.py', 'test_review_v2.py', 'test_review_quality.py', 'test_checkers_framework.py',
    'test_import_integrity.py', 'test_catalog.py', 'test_review_functions.py', 'test_results_model.py',
    # parsers
    'test_parse_netlist.py', 'test_parse_kicad.py', 'test_page_inventory.py', 'test_kicad_declared_contacts.py',
    'test_dotted_physical_pins.py',
}
WORDING_FILES = {'test_golden_reports.py'}
CJK = re.compile('[\u4e00-\u9fff]')
_WORDING_CACHE = {}


def _wording_tests(path):
    """Names of test functions in `path` whose asserts are mostly assertIn/assertNotIn on a Chinese literal."""
    if path not in _WORDING_CACHE:
        names = set()
        for node in ast.walk(ast.parse(Path(path).read_text(encoding='utf-8'))):
            if not (isinstance(node, ast.FunctionDef) and node.name.startswith('test')):
                continue
            asserts = [call for call in ast.walk(node) if isinstance(call, ast.Call)
                       and isinstance(call.func, ast.Attribute) and call.func.attr.startswith('assert')]
            wording = [call for call in asserts if call.func.attr in ('assertIn', 'assertNotIn') and call.args
                       and any(isinstance(x, ast.Constant) and isinstance(x.value, str) and CJK.search(x.value)
                               for x in ast.walk(call.args[0]))]
            if wording and 2 * len(wording) >= len(asserts):
                names.add(node.name)
        _WORDING_CACHE[path] = names
    return _WORDING_CACHE[path]


def pytest_configure(config):
    config.addinivalue_line('markers', 'contract: fast gate run on every change')
    config.addinivalue_line('markers', 'wording: Chinese report wording; golden snapshots and legacy asserts')


def pytest_collection_modifyitems(config, items):
    for item in items:
        path = Path(str(item.fspath))
        name = getattr(item, 'originalname', None) or item.name.split('[')[0]
        wording = path.name in WORDING_FILES or name in _wording_tests(str(path))
        if wording:
            item.add_marker(pytest.mark.wording)
        elif path.name in CONTRACT_FILES:
            item.add_marker(pytest.mark.contract)

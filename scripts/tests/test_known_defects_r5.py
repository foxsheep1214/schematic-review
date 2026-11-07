"""Regression guard for known defect R5-hot-execution (both R5 reviews executed no automatic guaranteed-value check).

The automatic guaranteed-value path was retired on 2026-10-23 (ledger: "The automatic guaranteed-value path is retired
and the tests write function verdicts directly"): E rows are planned WAITING_EVIDENCE and the reviewer judges them in a
function verdict. This test keeps the retired machinery from coming back unnoticed.
"""
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]


def test_the_retired_automatic_guaranteed_value_path_stays_gone():
    for name in ('execution_audit.py', 'datasheet_facts.py', 'evidence.py'):
        assert not (SCRIPTS / name).exists(), name
    sources = [p for p in SCRIPTS.rglob('*.py') if 'tests' not in p.parts]
    offenders = [str(p.relative_to(SCRIPTS)) for p in sources
                 if 'def hot_check' in p.read_text(encoding='utf-8')]
    assert offenders == []

"""回放必须使用实际安装包，保留旧约定并只接受已核的两个批项差异。"""
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / 'evals/kicad_replay_bench'
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('installed_replay', BENCH / 'run.py')
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


def test_native_replay_does_not_inherit_ruleless_test_inputs(monkeypatch):
    monkeypatch.setenv('GUIDELINE_CRITERIA', '/testing/empty.json')
    monkeypatch.setenv('GUIDELINE_CRITERIA_TESTING', '1')
    captured = []
    monkeypatch.setattr(replay.subprocess, 'run', lambda *a, **kw: captured.append(kw['env']) or SimpleNamespace(returncode=0))
    assert replay._run(['script']).returncode == 0
    assert 'GUIDELINE_CRITERIA' not in captured[0]
    assert 'GUIDELINE_CRITERIA_TESTING' not in captured[0]


def test_current_contract_adds_only_existing_project_input_and_handoff_batches():
    manifest = json.loads(replay.contract_path('manifest.json').read_text())
    assert manifest['scope_check_ids'] == ['REQ-Q09.HANDOFF.BOARD', 'REQ-Q09.PROJECT-INPUT.BOARD']
    parent = BENCH / 'revisions/guideline-scans-v1'
    for name in ('cases.json', 'sources.json'):
        assert replay.contract_path(name).read_bytes() == (parent / name).read_bytes()
    old = json.loads((parent / 'expected.json').read_text())['cases']
    new = json.loads(replay.contract_path('expected.json').read_text())['cases']
    assert set(old) == set(new)
    assert len(manifest['field_changes']) == len(old) == 13
    for case in old:
        before, after = old[case]['fields'], new[case]['fields']
        assert after['plan.checks_total'] == before['plan.checks_total'] + 2
        assert {k: v for k, v in after.items() if k != 'plan.checks_total'} == {k: v for k, v in before.items() if k != 'plan.checks_total'}

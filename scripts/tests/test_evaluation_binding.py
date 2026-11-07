"""评测运行器的本地功能约定：显式绑定、记录身份、缺 E 单独 skip。"""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('bound_case_runner', ROOT / 'evals/circuit_cases/run.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_missing_external_set_is_reported_separately(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv('CIRCUIT_EVAL_SET', str(tmp_path / 'missing'))
    with pytest.raises(SystemExit) as stop:
        runner.tool()
    assert stop.value.code == 0
    report = json.loads(capsys.readouterr().out)
    assert report['status'] == 'skip'
    assert report['scope'] == 'external_evaluation'


def test_binding_receives_the_explicit_release_and_skill(monkeypatch):
    calls = []
    fake = SimpleNamespace(binding=SimpleNamespace(context=lambda *args: calls.append(args) or {'selected': 1}))
    monkeypatch.setattr(runner.eval_set, 'tool', lambda: fake)
    assert runner.eval_set.context(Path('/explicit/package'), ROOT) == {'selected': 1}
    assert calls == [(Path('/explicit/package'), runner.eval_set.root(), ROOT)]


def synthetic(monkeypatch, tmp_path):
    path = tmp_path / 'data' / 'case.json'
    path.parent.mkdir()
    (path.parent / '需求.md').write_text('只含需求', encoding='utf-8')
    case = dict(id='simple', title='simple', family='local', skills=['ASG', 'SR'],
                circuit_types=['CAN'], variants={'r1': {'netlist': 'r1.xml'}})
    identity = {'guidelines': {'library_version': 'test', 'shared_sha256': 'fixed', 'fingerprint_format': 'v2'},
                'eval_set': {'head': 'data-head', 'workspace_sha256': 'actual-dirty-data'},
                'skill': {'head': 'skill-head', 'workspace_sha256': 'actual-dirty-skill'}}
    fake = SimpleNamespace(load_cases=lambda: [(path, case)], check_case=lambda *args: [],
                           binding=SimpleNamespace(release_context=lambda release: ({}, identity['guidelines']),
                                                   case_inputs=lambda p: {'case.json': 'case-hash', '需求.md': 'req-hash'}))
    calls = []
    monkeypatch.setattr(runner, 'tool', lambda: fake)
    monkeypatch.setattr(runner.eval_set, 'context', lambda *args: calls.append(args) or identity.copy())
    return fake, identity, calls


def test_auto_keeps_raw_run_and_score_identity(monkeypatch, tmp_path):
    fake, identity, calls = synthetic(monkeypatch, tmp_path)
    def variant(case, name, variant, directory, commit, evaluation):
        return dict(case=case['id'], variant=name, skill='SR', skill_commit=commit,
                    results=[], criteria_not_in_plan={}, evaluation=evaluation)
    monkeypatch.setattr(runner, 'run_variant', variant)
    fake.score = lambda run, case: dict(counts={'not_run': 1}, evaluation=run['evaluation'])
    args = SimpleNamespace(case='simple', out=tmp_path / 'out', guideline_release=tmp_path / 'chosen')
    runner.cmd_auto(args)
    record = json.loads((args.out / 'simple.r1.run.json').read_text())
    report = json.loads((args.out / 'simple.r1.json').read_text())
    summary = json.loads((args.out / 'summary.json').read_text())
    assert record['evaluation'] == report['evaluation']
    assert record['evaluation']['case_inputs']['case.json'] == 'case-hash'
    assert summary['evaluation'] == identity
    assert record['skill_commit'] == summary['skill_commit'] == 'skill-head'
    assert calls == [(args.guideline_release, ROOT)]


def test_score_forwards_release_and_skill_root(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(runner, 'tool', lambda: SimpleNamespace(main=lambda args: calls.append(args) or 0))
    args = SimpleNamespace(run=tmp_path / 'run.json', guideline_release=tmp_path / 'chosen')
    assert runner.cmd_score(args) == 0
    assert calls == [['score', str(args.run), '--json', '--guideline-release', str(args.guideline_release), '--skill-root', str(ROOT)]]


def test_variant_clears_test_overrides_and_checks_actual_plan(monkeypatch, tmp_path):
    monkeypatch.setenv('GUIDELINE_CRITERIA', '/test/replacement.json')
    monkeypatch.setenv('GUIDELINE_CRITERIA_TESTING', '1')
    identity = dict(library_version='selected', shared_sha256='sha', fingerprint_format='v2')
    calls = []
    def process(argv, **kwargs):
        calls.append(kwargs['env'])
        (tmp_path / 'plan.json').write_text(json.dumps(dict(guidelines=identity)))
        (tmp_path / 'hits.json').write_text('{}')
    monkeypatch.setattr(runner.subprocess, 'run', process)
    case = dict(id='c', family='f', category='通信接口', test_points=[])
    result = runner.run_variant(case, 'v', {'netlist': 'v.xml'}, tmp_path, 'commit', {'guidelines': identity})
    assert result['evaluation']['guidelines'] == identity
    assert len(calls) == 2
    assert all('GUIDELINE_CRITERIA' not in e and 'GUIDELINE_CRITERIA_TESTING' not in e for e in calls)
    def wrong(argv, **kwargs):
        process(argv, **kwargs)
        (tmp_path / 'plan.json').write_text(json.dumps(dict(guidelines={})))
    monkeypatch.setattr(runner.subprocess, 'run', wrong)
    with pytest.raises(ValueError, match='plan did not use selected'):
        runner.run_variant(case, 'v', {'netlist': 'v.xml'}, tmp_path, 'commit', {'guidelines': identity})

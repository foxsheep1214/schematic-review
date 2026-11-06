"""电路评测集与 SR 的接口：路径定位、自动层跑通、误报只算点名的位号。"""
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'evals'))
sys.path.insert(0, str(ROOT / 'evals/circuit_cases'))
import eval_set  # noqa: E402
import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location('circuit_cases_run', ROOT / 'evals/circuit_cases/run.py')
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)
needs_set = pytest.mark.skipif(not eval_set.available(), reason='电路评测集不在本机')


def test_env_overrides_default(monkeypatch, tmp_path):
    monkeypatch.setenv('CIRCUIT_EVAL_SET', str(tmp_path))
    assert eval_set.root() == tmp_path
    assert not eval_set.available()
    (tmp_path / '工具').mkdir()
    (tmp_path / '工具/evalset.py').write_text('')
    assert eval_set.available()


def test_missing_set_is_a_clear_stop(monkeypatch, tmp_path):
    monkeypatch.setenv('CIRCUIT_EVAL_SET', str(tmp_path))
    with pytest.raises(SystemExit, match='电路评测集不在'):
        run.tool()


def test_raised_only_counts_named_rule_on_named_refs():
    hits = [dict(rule='A', ref='U1', kind='FINDING'), dict(rule='A', ref='U9', kind='FINDING'), dict(rule='B', ref='U1', kind='FINDING'),
            dict(rule='A', ref='U1', kind='INFO')]
    plan = {'checks': [dict(id='A.U1', rule='A', object=dict(refs=['U1'])), dict(id='A.U2', rule='A', object=dict(refs=['U2'])),
                       dict(id='A.BOARD', rule='A', object=dict(board='BOARD', refs=['U1']))]}
    assert run.raised(plan, hits, ['A'], ['U1']) == ['finding A U1', 'plan A.U1']
    assert run.raised({}, hits, ['C'], ['U1']) == []


def test_slash_separated_rules_are_split():
    assert run.rules_of(dict(sr_rule='PRO-C07/PWR-C23')) == ['PRO-C07', 'PWR-C23']
    assert run.rules_of({}) == []


@needs_set
def test_eval_set_is_valid():
    tool = eval_set.root() / '工具/evalset.py'
    result = subprocess.run([sys.executable, '-B', str(tool), 'check'], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout


@needs_set
def test_auto_runs_one_case_and_finds_no_stale_ids(tmp_path):
    result = subprocess.run([sys.executable, '-B', str(ROOT / 'evals/circuit_cases/run.py'), 'auto', '--out', str(tmp_path), '--case', 'iio-can'],
                            capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stderr
    report = json.loads((tmp_path / 'iio-can.r1.json').read_text(encoding='utf-8'))
    assert report['unknown_test_points'] == []
    assert report['counts'].get('hit', 0) >= 1

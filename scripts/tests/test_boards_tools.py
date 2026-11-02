"""Offline integration tests: real local git fetch and the real XML parser."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
TOOL = ROOT / 'evals/boards/_tools/fetch_board.py'
spec = importlib.util.spec_from_file_location('fetch_board', TOOL)
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


@pytest.fixture
def local_board(tmp_path):
    repo = tmp_path / 'origin'
    repo.mkdir()
    git(repo, 'init', '-q')
    (repo / 'root.kicad_sch').write_text('(kicad_sch (version 20250114))')
    git(repo, 'add', '.')
    git(repo, '-c', 'user.name=test', '-c', 'user.email=test@local', 'commit', '-qm', 'fixture')
    board = dict(id='local', repo=str(repo), commit=git(repo, 'rev-parse', 'HEAD'),
                 schematic='root.kicad_sch')
    return board


def exporter(tmp_path, *, malformed=False, count=15, missing_names=False, fail=False):
    components = ''.join('<comp ref="R%d"><value>10k</value><libsource lib="Device" part="R"/>'
                         '<sheetpath names="/" tstamps="/"/></comp>' % i for i in range(count))
    kind = 'input' if missing_names else 'passive'
    nodes = ''.join('<node ref="R%d" pin="1" pintype="%s"/>' % (i, kind) for i in range(count))
    xml = ('<export><design><source>root.kicad_sch</source><sheet number="1" name="/" tstamps="/"/></design>'
           '<components>' + components + '</components><libparts><libpart lib="Device" part="R">'
           '<pins><pin num="1" name="~" type="' + kind + '"/></pins></libpart></libparts>'
           '<nets><net code="1" name="GND">' + nodes + '</net></nets></export>')
    script = tmp_path / 'exporter'
    script.write_text('#!' + sys.executable + '\nimport sys\nfrom pathlib import Path\n'
                      + ('sys.exit(7)\n' if fail else
                         'Path(sys.argv[sys.argv.index("-o")+1]).write_text(' + repr('broken' if malformed else xml) + ')\n'))
    script.chmod(0o755)
    return script


def test_fetch_success_and_pinned_cache(tmp_path, local_board):
    cli = exporter(tmp_path)
    cache = tmp_path / 'cache'
    result = fetch.fetch_board(local_board, cache, cli)
    dest = cache / 'local'
    assert result['parts'] == 15
    assert result['strict']
    assert all((dest / p).is_file() for p in ('netlist.xml', 'db.json', 'fetch.log', 'verification.json'))
    assert git(dest / 'src', 'rev-parse', 'HEAD') == local_board['commit']
    (dest / 'src/root.kicad_sch').write_text('dirty')
    (dest / 'src/untracked').write_text('dirty')
    assert fetch.fetch_board(local_board, cache, cli)['db_sha256'] == result['db_sha256']
    assert not (dest / 'src/untracked').exists()


def test_fetch_failure_has_stage_and_no_stale_db(tmp_path, local_board):
    local_board['repo'] = str(tmp_path / 'missing-repo')
    dest = tmp_path / 'cache/local'
    dest.mkdir(parents=True)
    (dest / 'db.json').write_text('{}')
    with pytest.raises(fetch.FetchError, match='fetch: exit'):
        fetch.fetch_board(local_board, dest.parent, 'unused')
    assert 'FAIL fetch:' in (dest / 'fetch.log').read_text()
    assert not (dest / 'db.json').exists()


def test_parse_failure_reports_both_attempts(tmp_path, local_board):
    with pytest.raises(fetch.FetchError, match='parse --no-strict: exit'):
        fetch.fetch_board(local_board, tmp_path / 'cache', exporter(tmp_path, malformed=True))
    dest = tmp_path / 'cache/local'
    log = (dest / 'fetch.log').read_text()
    assert 'parse strict' in log and 'Reason:' in log and 'parse --no-strict' in log
    assert not (dest / 'db.json').exists()
    assert not (dest / 'verification.json').exists()


def test_strict_failure_falls_back_with_reason(tmp_path, local_board):
    result = fetch.fetch_board(local_board, tmp_path / 'cache', exporter(tmp_path, missing_names=True))
    assert not result['strict'] and result['strict_failure']
    assert 'Strict parse failed' in (tmp_path / 'cache/local/fetch.log').read_text()


def test_export_failure(tmp_path, local_board):
    with pytest.raises(fetch.FetchError, match='export: exit 7'):
        fetch.fetch_board(local_board, tmp_path / 'cache', exporter(tmp_path, fail=True))


def test_too_few_parts_rejected(tmp_path, local_board):
    with pytest.raises(fetch.FetchError, match='14 < 15'):
        fetch.fetch_board(local_board, tmp_path / 'cache', exporter(tmp_path, count=14))
    assert not (tmp_path / 'cache/local/db.json').exists()


def test_cli_unknown_board(tmp_path):
    catalog = tmp_path / 'catalog.json'
    catalog.write_text('{"boards": []}')
    result = subprocess.run([sys.executable, str(TOOL), 'unknown', '--catalog', str(catalog),
                             '--cache', str(tmp_path / 'cache')], capture_output=True, text=True)
    assert result.returncode == 1
    assert 'catalog: expected exactly one board: unknown' in result.stderr


@pytest.mark.parametrize('change', [dict(id='../escape'), dict(commit='main'), dict(schematic='../escape.kicad_sch')])
def test_catalog_path_and_pin_validation(tmp_path, local_board, change):
    local_board.update(change)
    with pytest.raises(fetch.FetchError, match='catalog:'):
        fetch.fetch_board(local_board, tmp_path / 'cache', 'unused')


def test_cli_success_with_local_repository(tmp_path, local_board):
    catalog = tmp_path / 'catalog.json'
    catalog.write_text(json.dumps({'boards': [local_board]}))
    result = subprocess.run([sys.executable, str(TOOL), 'local', '--catalog', str(catalog),
                             '--cache', str(tmp_path / 'cache'), '--kicad-cli', str(exporter(tmp_path))],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['parts'] == 15
    assert (tmp_path / 'cache/local/db.json').is_file()


def test_incomplete_cached_git_repository_is_refetched(tmp_path, local_board):
    src = tmp_path / 'cache/local/src'
    src.mkdir(parents=True)
    git(src, 'init', '-q')
    result = fetch.fetch_board(local_board, tmp_path / 'cache', exporter(tmp_path))
    assert result['parts'] == 15
    assert 'Incomplete cached checkout' in (src.parent / 'fetch.log').read_text()


def test_catalog_contains_100_distinct_pinned_qualified_boards():
    from collections import Counter
    import re
    boards = json.loads((ROOT / 'evals/boards/catalog.json').read_text())['boards']
    vocabulary = {t['name'] for t in json.loads((ROOT / 'references/shared/vocabulary.json').read_text())['circuit_types']}
    excluded = {b.get('repo', '').lower() for b in json.loads((ROOT / 'evals/seeded_bench/corpus.json').read_text())['boards']}
    assert len(boards) == len({b['id'] for b in boards}) == len({b['repo'].lower() for b in boards}) == 100
    assert not {b['repo'].lower() for b in boards} & excluded
    assert max(Counter(b['application'] for b in boards).values()) <= 5
    for board in boards:
        assert re.fullmatch('[0-9a-f]{40}', board['commit'])
        assert 1 <= len(board['types']) <= 4 and set(board['types']) <= vocabulary
        assert board['parts'] >= 15 and board['schema_version'] >= 20210000
        assert board['schematic'].endswith('.kicad_sch') and not Path(board['schematic']).is_absolute()
        assert board['license_evidence'] and board['note']
        assert all('/blob/' + board['commit'] + '/' in url for url in board['license_evidence'])
        if board['license'].startswith(('GPL', 'LGPL')):
            assert board['copyleft'] is True


def test_lanes_partition_catalog_and_spread_types_and_workload():
    from collections import Counter
    boards = {b['id']: b for b in json.loads((ROOT / 'evals/boards/catalog.json').read_text())['boards']}
    lanes = [json.loads((ROOT / ('evals/boards/_lanes/lane-%d.json' % i)).read_text()) for i in range(1, 5)]
    assert [lane['lane'] for lane in lanes] == ['lane-1', 'lane-2', 'lane-3', 'lane-4']
    assert all(len(lane['boards']) == 25 for lane in lanes)
    assigned = [bid for lane in lanes for bid in lane['boards']]
    assert len(set(assigned)) == 100 and set(assigned) == set(boards)
    types = Counter(t for b in boards.values() for t in b['types'])
    for tag, count in types.items():
        if count >= 4:
            assert all(any(tag in boards[bid]['types'] for bid in lane['boards']) for lane in lanes)
    loads = [sum(boards[bid]['parts'] for bid in lane['boards']) for lane in lanes]
    assert max(loads) - min(loads) < 100


def test_verification_covers_exact_catalog_pins_and_part_counts():
    boards = {b['id']: b for b in json.loads((ROOT / 'evals/boards/catalog.json').read_text())['boards']}
    verified = json.loads((ROOT / 'evals/boards/verification.json').read_text())['boards']
    assert len(verified) == 100 and {v['id'] for v in verified} == set(boards)
    for result in verified:
        board = boards[result['id']]
        for field in ('repo', 'commit', 'schematic', 'parts', 'schema_version', 'strict'):
            assert result[field] == board[field]
        assert len(result['db_sha256']) == 64
        assert bool(result['strict_failure']) is not result['strict']

#!/usr/bin/env python3
"""Fetch one pinned public board, export its complete hierarchy, and parse db.json.

Usage: fetch_board.py <board-id> --cache ~/.cache/sr-boards
Only the standard library is used. Third-party files never enter the skill tree.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
CATALOG = ROOT / 'evals/boards/catalog.json'


class FetchError(RuntimeError):
    """A fetch stage failed; fetch.log contains command output."""


def run(cmd, log, stage, **kwargs):
    log.write('\n[' + stage + '] ' + repr([str(x) for x in cmd]) + '\n')
    log.flush()
    try:
        result = subprocess.run([str(x) for x in cmd], capture_output=True,
                                text=True, timeout=600, **kwargs)
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.write(str(exc) + '\n')
        raise FetchError(stage + ': ' + str(exc)) from exc
    log.write(result.stdout + result.stderr)
    log.flush()
    if result.returncode:
        raise FetchError('%s: exit %s (see fetch.log)' % (stage, result.returncode))
    return result.stdout.strip()


def fetch_board(board, cache, kicad_cli, parser=None):
    """Return verification metadata, or raise FetchError with the failed stage.

    A local repo path is accepted for offline integration tests. Production catalog
    entries use owner/repo. KiCad exports child sheets recursively from the root.
    """
    bid = board['id']
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]*', bid):
        raise FetchError('catalog: unsafe board id')
    commit = board['commit']
    if not re.fullmatch(r'[0-9a-fA-F]{40}', commit):
        raise FetchError('catalog: commit must be a full SHA')
    schematic = Path(board['schematic'])
    if schematic.is_absolute() or '..' in schematic.parts:
        raise FetchError('catalog: schematic must be a relative path within source')
    dest = Path(cache).expanduser().resolve() / bid
    dest.mkdir(parents=True, exist_ok=True)
    src, xml, db = dest / 'src', dest / 'netlist.xml', dest / 'db.json'
    # Never let a previous success masquerade as the current attempt.
    for name in ('netlist.xml', 'db.json', 'verification.json'):
        (dest / name).unlink(missing_ok=True)
    with (dest / 'fetch.log').open('w', encoding='utf-8') as log:
        try:
            head = None
            if (src / '.git').exists():
                try:
                    head = run(['git', '-C', src, 'rev-parse', 'HEAD'], log, 'cache HEAD')
                except FetchError:
                    log.write('Incomplete cached checkout; refetching pinned commit.\n')
            if head != commit:
                if src.exists():
                    shutil.rmtree(src)
                src.mkdir()
                repo = board['repo']
                url = repo if Path(repo).is_absolute() else 'https://github.com/' + repo + '.git'
                run(['git', '-C', src, 'init', '-q'], log, 'init')
                # Fetch only needed blobs; all hierarchy and local symbol libraries remain available.
                (src / '.git/info/sparse-checkout').write_text(
                    '*.kicad_sch\n*.kicad_pro\n*.kicad_sym\n*sym-lib-table\n*LICENSE*\n*license*\n*COPYING*\n*README*\n*readme*\n', encoding='utf-8')
                run(['git', '-C', src, 'config', 'core.sparseCheckout', 'true'], log, 'sparse source')
                run(['git', '-C', src, 'fetch', '-q', '--filter=blob:none', '--depth', '1', url, commit], log, 'fetch')
                run(['git', '-C', src, 'checkout', '-q', 'FETCH_HEAD'], log, 'checkout')
            # Reset tracked files and remove untracked files so exports use the pin.
            run(['git', '-C', src, 'reset', '--hard', commit], log, 'reset')
            run(['git', '-C', src, 'clean', '-fdx'], log, 'clean')
            sch = src / schematic
            if not sch.resolve().is_relative_to(src.resolve()):
                raise FetchError('format: schematic escapes source')
            header = sch.read_text(encoding='utf-8')[:512]
            version = re.search(r'\(kicad_sch\s+\(version\s+(\d+)\)', header)
            if not version or int(version[1]) < 20210000:
                raise FetchError('format: KiCad 6+ .kicad_sch required')
            run([kicad_cli, 'sch', 'export', 'netlist', '--format', 'kicadxml',
                 '-o', xml, sch], log, 'export')
            cmd = [sys.executable, '-B', str(parser or ROOT / 'scripts/parse_kicad.py'),
                   str(xml), '-o', str(db)]
            strict, reason = True, None
            try:
                run(cmd, log, 'parse strict')
            except FetchError as exc:
                strict, reason = False, str(exc)
                log.write('\nStrict parse failed; retrying --no-strict. Reason: ' + reason + '\n')
                db.unlink(missing_ok=True)
                run(cmd + ['--no-strict'], log, 'parse --no-strict')
            parts = len(json.loads(db.read_text(encoding='utf-8'))['parts'])
            if parts < 15:
                raise FetchError('minimum parts: %s < 15' % parts)
            result = {'id': bid, 'repo': board['repo'], 'commit': commit,
                      'schematic': board['schematic'], 'schema_version': int(version[1]),
                      'parts': parts, 'strict': strict, 'strict_failure': reason,
                      'db_sha256': hashlib.sha256(db.read_bytes()).hexdigest()}
            (dest / 'verification.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
            log.write('\nPASS ' + json.dumps(result) + '\n')
            return result
        except (FetchError, OSError, ValueError, KeyError) as exc:
            db.unlink(missing_ok=True)
            log.write('\nFAIL ' + str(exc) + '\n')
            raise FetchError(str(exc)) from exc


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('board_id')
    ap.add_argument('--cache', type=Path, required=True)
    ap.add_argument('--catalog', type=Path, default=CATALOG)
    ap.add_argument('--kicad-cli', default=os.environ.get('KICAD_CLI') or shutil.which('kicad-cli')
                    or '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli')
    args = ap.parse_args(argv)
    try:
        matches = [b for b in json.loads(args.catalog.read_text(encoding='utf-8'))['boards']
                   if b['id'] == args.board_id]
        if len(matches) != 1:
            raise FetchError('catalog: expected exactly one board: ' + args.board_id)
        print(json.dumps(fetch_board(matches[0], args.cache, args.kicad_cli), ensure_ascii=False))
        return 0
    except (FetchError, OSError, ValueError, KeyError) as exc:
        print('fetch_board: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())

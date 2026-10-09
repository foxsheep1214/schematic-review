#!/usr/bin/env python3
"""Fetch corpus boards at their pinned commits and parse them into db.json files.

Third-party sources stay in the cache directory; nothing is copied into the repo.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def fetch(board, src):
    if (src / '.git').exists() and run(['git', '-C', str(src), 'rev-parse', 'HEAD']).stdout.strip() == board['commit']:
        return
    shutil.rmtree(src, ignore_errors=True)
    src.mkdir(parents=True)
    run(['git', '-C', str(src), 'init', '-q'])
    run(['git', '-C', str(src), 'fetch', '-q', '--depth', '1',
         'https://github.com/' + board['repo'] + '.git', board['commit']], timeout=600)
    run(['git', '-C', str(src), 'checkout', '-q', 'FETCH_HEAD'])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cache', type=Path, required=True)
    ap.add_argument('--kicad-cli', default=os.environ.get('KICAD_CLI') or shutil.which('kicad-cli')
                    or '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli')
    args = ap.parse_args()
    corpus = json.loads((HERE / 'corpus.json').read_text(encoding='utf-8'))
    (args.cache / 'db').mkdir(parents=True, exist_ok=True)
    manifest = []
    for board in corpus['boards']:
        out = args.cache / 'db' / (board['id'] + '.json')
        if 'fixture' in board:
            shutil.copyfile(ROOT / board['fixture'], out)
        else:
            src = args.cache / 'src' / board['id']
            fetch(board, src)
            xml = args.cache / 'db' / (board['id'] + '.xml')
            run([args.kicad_cli, 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', str(xml),
                 str(src / board['schematic'])])
            cmd = [sys.executable, '-B', str(ROOT / 'scripts' / 'parse_kicad.py'), str(xml), '-o', str(out)]
            if not board.get('strict', True):
                cmd.append('--no-strict')
            run(cmd)
        digest = hashlib.sha256(out.read_bytes()).hexdigest()
        parts = len(json.loads(out.read_text(encoding='utf-8'))['parts'])
        manifest.append({'id': board['id'], 'db': str(out), 'sha256': digest, 'parts': parts})
        print(board['id'], parts, 'parts', digest[:12])
    (args.cache / 'manifest.json').write_text(json.dumps(manifest, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()

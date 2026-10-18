#!/usr/bin/env python3
"""Install a private KiCad 9 kicad-cli without root, Docker or a system package change.

    python3 scripts/install_kicad_cli.py --prefix ~/.cache/kicad9 [--suite questing]
    export KICAD_CLI=~/.cache/kicad9/kicad-cli       # parse_kicad.py picks it up

KiCad 8/9 schematics (file version > 20230121) cannot be read by the KiCad 7 that
Ubuntu 24.04 ships. This downloads the kicad package of a newer Ubuntu release and
its complete dependency closure from archive.ubuntu.com, unpacks them into PREFIX,
and writes a launcher that runs kicad-cli through the unpacked glibc loader, so the
host system is untouched. Only what is needed to read schematics and export
netlists is exercised; the GUI is not supported.

KiCad 5 legacy .sch files load empty in every kicad-cli version; give parse_kicad.py
the project's KiCad 5 netlist (.net) instead.
"""
import argparse
import gzip
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request

ARCHIVE = 'http://archive.ubuntu.com/ubuntu/'
LAUNCHER = """#!/bin/sh
# KiCad {version} kicad-cli unpacked by scripts/install_kicad_cli.py; runs on its own glibc.
R={root}
L=$R/usr/lib/x86_64-linux-gnu:$R/lib/x86_64-linux-gnu:$R/usr/lib/kicad:$R/usr/lib
export XDG_CONFIG_HOME="${{KICAD_CONFIG_HOME:-{config}}}"
exec $R/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2 --library-path "$L" $R/usr/bin/kicad-cli "$@"
"""


def fetch(url):
    with urllib.request.urlopen(url, timeout=300) as response:
        return response.read()


def packages(suite):
    index = {}
    for component in ('main', 'universe'):
        data = gzip.decompress(fetch(ARCHIVE + 'dists/%s/%s/binary-amd64/Packages.gz' % (suite, component)))
        for block in data.decode('utf-8').split('\n\n'):
            fields = {}
            for line in block.split('\n'):
                if ':' in line and not line.startswith(' '):
                    key, value = line.split(':', 1)
                    fields[key] = value.strip()
            if 'Package' in fields:
                index.setdefault(fields['Package'], fields)
    return index


def closure(index, root='kicad'):
    provides = {}
    for name, fields in index.items():
        for item in fields.get('Provides', '').split(','):
            item = item.strip().split(' ')[0]
            if item:
                provides.setdefault(item, name)
    seen, stack = set(), [root]
    while stack:
        name = stack.pop()
        name = name if name in index else provides.get(name)
        if not name or name in seen:
            continue
        seen.add(name)
        for key in ('Depends', 'Pre-Depends'):
            for alternatives in index[name].get(key, '').split(','):
                first = alternatives.split('|')[0].strip().split(' ')[0].split(':')[0]
                if first:
                    stack.append(first)
    return sorted(seen)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--prefix', type=Path, required=True)
    parser.add_argument('--suite', default='questing', help='Ubuntu release with KiCad 9 (questing = 25.10)')
    args = parser.parse_args(argv)
    if not shutil.which('dpkg-deb'):
        print('ERROR: dpkg-deb is required to unpack the packages')
        return 2
    prefix = args.prefix.expanduser().resolve()
    root, debs = prefix / 'root', prefix / 'debs'
    debs.mkdir(parents=True, exist_ok=True)
    index = packages(args.suite)
    if 'kicad' not in index:
        print('ERROR: no kicad package in %s' % args.suite)
        return 2
    names = closure(index)
    print('kicad %s: %d packages' % (index['kicad']['Version'], len(names)))
    for name in names:
        target = debs / Path(index[name]['Filename']).name
        if not target.exists():
            target.write_bytes(fetch(ARCHIVE + index[name]['Filename']))
        subprocess.run(['dpkg-deb', '-x', str(target), str(root)], check=True)
    # kicad-cli looks for its .kiface modules next to the running executable (here the loader).
    for kiface in (root / 'usr/lib/kicad').glob('*.kiface'):
        link = root / 'usr/lib/x86_64-linux-gnu' / kiface.name
        if not link.exists():
            link.symlink_to(kiface)
    config = prefix / 'config'
    (config / 'kicad').mkdir(parents=True, exist_ok=True)
    launcher = prefix / 'kicad-cli'
    launcher.write_text(LAUNCHER.format(version=index['kicad']['Version'], root=root, config=config))
    launcher.chmod(0o755)
    version = subprocess.run([str(launcher), 'version'], capture_output=True, text=True)
    print('installed:', launcher, (version.stdout or version.stderr).strip().splitlines()[-1:])
    print('use: export KICAD_CLI=%s' % launcher)
    return 0 if version.returncode == 0 else 1


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""Frozen external netlist + structural mutations; no electrical accuracy score."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


def digest(data):
    return hashlib.sha256(data).hexdigest()


def graph(db):
    return {'values': {r: p['value'] for r, p in sorted(db['parts'].items())},
            'partitions': sorted(sorted(pins) for pins in db['nets'].values())}


def run(source, manifest, scripts):
    raw = Path(source).read_bytes()
    if digest(raw) != manifest['input_sha256']:
        raise ValueError('Input differs from frozen manifest')
    sys.path.insert(0, str(Path(scripts).resolve()))
    spec = importlib.util.spec_from_file_location('input_bench_parser', Path(scripts) / 'parse_kicad.py')
    parser = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(parser)
    root = ET.fromstring(raw)
    cases = [('original', raw, False)]
    empty = ET.fromstring(raw)
    empty.find('components').clear(); empty.find('nets').clear()
    cases.append(('empty-export', ET.tostring(empty), True))
    duplicate = ET.fromstring(raw)
    duplicate.find('components').append(ET.fromstring(ET.tostring(root.find('components/comp'))))
    cases.append(('duplicate-reference', ET.tostring(duplicate), True))
    conflict = ET.fromstring(raw)
    nets = conflict.findall('nets/net')
    if len(nets) < 2:
        raise ValueError('Benchmark needs at least two physical nets')
    nets[1].append(ET.fromstring(ET.tostring(nets[0].find('node'))))
    cases.append(('multiply-assigned-pin', ET.tostring(conflict), True))
    results = []
    for name, data, reject in cases:
        error, db = None, None
        try:
            db = parser.parse(data)
        except ValueError as exc:
            error = str(exc)
        ok = bool(error) if reject else db is not None and graph(db) == manifest['graph']
        results.append({'case': name, 'expected': 'REJECT' if reject else 'EXACT_GRAPH',
                        'passed': ok, 'error': error})
    return {'schema_version': 1, 'source': manifest['source'], 'input_sha256': digest(raw),
            'scope': 'Import integrity only; original is not an electrically qualified golden circuit.',
            'passed': sum(x['passed'] for x in results), 'total': len(results), 'results': results}


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--input', type=Path, required=True)
    cli.add_argument('--manifest', type=Path, required=True)
    cli.add_argument('--scripts', type=Path, default=Path(__file__).resolve().parents[2] / 'scripts')
    cli.add_argument('--out', type=Path, required=True)
    args = cli.parse_args()
    report = run(args.input, json.loads(args.manifest.read_text()), args.scripts)
    with args.out.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2); handle.write('\n')
    print('%d/%d structural cases passed' % (report['passed'], report['total']))
    raise SystemExit(0 if report['passed'] == report['total'] else 3)

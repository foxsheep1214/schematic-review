#!/usr/bin/env python3
"""Bounded ideal R/C evidence from physical netlist pins, with replay checks."""
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import re
import shutil
import subprocess

from decoupling import parse_capacitance
from solve_dividers import parse_resistor


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Expected a finite numeric parameter')
    return value


def bounded(item, low, high, positive=False):
    a, b = number(item[low]), number(item[high])
    if a > b or positive and a <= 0:
        raise ValueError('Invalid parameter bounds')
    return sorted(set([a, b]))


def prepare(db_path, spec_path):
    db, spec = json.loads(Path(db_path).read_text()), json.loads(Path(spec_path).read_text())
    required = {'schema_version', 'db_sha256', 'check_id', 'state', 'model', 'components', 'ground', 'source', 'analysis', 'window', 'excluded_nodes', 'assumptions', 'basis'}
    if not isinstance(spec, dict) or set(spec) != required or spec['schema_version'] != 1 or spec['model'] != 'ideal_linear_RC':
        raise ValueError('Unsupported model/spec fields')
    if sha(db_path) != spec['db_sha256']:
        raise ValueError('Stale netlist binding')
    for key in ['check_id', 'state', 'ground']:
        if not isinstance(spec[key], str) or not spec[key].strip():
            raise ValueError('Missing ' + key)
    if not isinstance(spec['assumptions'], list) or not spec['assumptions'] or any(not isinstance(x, str) or not x.strip() for x in spec['assumptions']):
        raise ValueError('Explicit idealization/state assumptions required')
    if not isinstance(spec['basis'], list) or not spec['basis']:
        raise ValueError('Parameter/state source evidence required')
    for item in spec['basis']:
        if set(item) != {'path', 'sha256', 'locator'} or not isinstance(item['locator'], str) or not item['locator'].strip():
            raise ValueError('Evidence needs path, SHA256 and locator')
        path = Path(item['path'])
        if not path.is_absolute():
            path = Path(spec_path).resolve().parent / path
        if sha(path) != item['sha256']:
            raise ValueError('Evidence source hash changed')
    components, params, modeled, nets = [], [], set(), set()
    if not isinstance(spec['components'], dict) or not spec['components']:
        raise ValueError('No modeled components')
    for ref, item in sorted(spec['components'].items()):
        if set(item) != {'kind', 'min_si', 'max_si'} or item['kind'] not in ('R', 'C'):
            raise ValueError('Only ideal R/C values are supported')
        part = db['parts'].get(ref)
        kind = item['kind']
        if not part or part.get('nc') or part.get('prim') not in ['Device:' + kind, 'Device:' + kind + '_Small']:
            raise ValueError('Missing, unpopulated or unsupported physical primitive: ' + ref)
        values = bounded(item, 'min_si', 'max_si', True)
        nominal = parse_resistor(part['value']) if kind == 'R' else parse_capacitance(part['value'])
        if kind == 'R':
            nominal = nominal['kohm'] * 1000 if nominal else None
        if nominal is None or not values[0] <= nominal <= values[-1]:
            raise ValueError('Schematic nominal outside declared SI bounds: ' + ref)
        pins = {p: n for p, n in db['pin2net'].items() if p.split('.', 1)[0] == ref}
        if set(pins) != {ref + '.1', ref + '.2'} or any(p not in db['nets'].get(n, []) for p, n in pins.items()):
            raise ValueError('Expected two mutually consistent physical pins: ' + ref)
        a, b = pins[ref + '.1'], pins[ref + '.2']
        if a == b:
            raise ValueError('Shorted modeled component: ' + ref)
        components.append((ref, kind, a, b)); params.append(values); nets.update([a, b]); modeled.update(pins)
    for net in nets:
        pins = db['nets'][net]
        if len(pins) != len(set(pins)) or any(db['pin2net'].get(pin) != net for pin in pins):
            raise ValueError('Inconsistent physical net membership')
    excluded = spec['excluded_nodes']
    required_exclusions = {p for n in nets for p in db['nets'][n]} - modeled
    if not isinstance(excluded, dict) or set(excluded) != required_exclusions or any(not isinstance(v, str) or not v.strip() for v in excluded.values()):
        raise ValueError('Every unmodeled physical pin on selected nets needs an explicit boundary assumption')
    source = spec['source']
    if set(source) != {'net', 'min_v', 'max_v'} or source['net'] not in nets or source['net'] == spec['ground'] or spec['ground'] not in nets:
        raise ValueError('Invalid source or ground')
    params.append(bounded(source, 'min_v', 'max_v'))
    analysis = spec['analysis']
    fields = {'kind', 'net'} if analysis.get('kind') == 'op' else {'kind', 'net', 'at_s', 'max_step_s', 'initial_v'}
    if set(analysis) != fields or analysis['kind'] not in ('op', 'tran') or analysis['net'] not in nets or analysis['net'] == spec['ground']:
        raise ValueError('Invalid voltage measurement')
    if analysis['kind'] == 'tran':
        at, step = number(analysis['at_s']), number(analysis['max_step_s'])
        number(analysis['initial_v'])
        if not 0 < step <= at / 100 or at / step > 1000000:
            raise ValueError('Transient step must resolve sample by >=100 steps and <=1e6 steps')
    if set(spec['window']) != {'min_v', 'max_v'}:
        raise ValueError('Voltage window needs min_v/max_v')
    bounded(spec['window'], 'min_v', 'max_v')
    corners = list(itertools.product(*params)) if math.prod(map(len, params)) <= 64 else []
    if not corners:
        raise ValueError('More than 64 endpoint corners; narrow model scope')
    nodes = {n: '0' if n == spec['ground'] else 'n%d' % i for i, n in enumerate(sorted(nets))}
    return db, spec, components, corners, nodes


def deck(spec, components, corner, nodes):
    lines = ['Bounded ideal RC physical subcircuit', '.options reltol=1e-9 abstol=1e-15 vntol=1e-10']
    for i, (ref, kind, a, b) in enumerate(components):
        lines.append('%s%d %s %s %.17g' % (kind, i + 1, nodes[a], nodes[b], corner[i]))
        if kind == 'C' and spec['analysis']['kind'] == 'tran':
            lines[-1] += ' ic=%.17g' % spec['analysis']['initial_v']
    lines.append('Vsource %s 0 %.17g' % (nodes[spec['source']['net']], corner[-1]))
    measurement = nodes[spec['analysis']['net']]
    if spec['analysis']['kind'] == 'op':
        operation = ['op', 'let actual = v(%s)' % measurement, 'print actual']
    else:
        a = spec['analysis']; at, step = a['at_s'], a['max_step_s']
        operation = ['tran %.17g %.17g 0 %.17g uic' % (step, at * 1.001, step),
                     'meas tran sample_voltage find v(%s) at=%.17g' % (measurement, at),
                     'let actual = sample_voltage', 'print actual']
    return '\n'.join(lines + ['.control', 'set noaskquit', 'set numdgt=15'] + operation + ['quit', '.endc', '.end', ''])


def measured(stdout, stderr, returncode):
    found = re.findall(r'^actual\s*=\s*([-+0-9.eE]+)', stdout, re.M | re.I)
    if returncode != 0 or len(found) != 1 or re.search(r'error|failed|singular matrix|timestep too small', stdout + stderr, re.I):
        raise ValueError('Solver did not produce one trustworthy finite measurement')
    result = float(found[0])
    if not math.isfinite(result):
        raise ValueError('Nonfinite solver measurement')
    return result


def summary(spec, values):
    low, high = min(values), max(values)
    inside = spec['window']['min_v'] <= low and high <= spec['window']['max_v']
    return {'status': 'WITHIN_SAMPLED_WINDOW' if inside else 'OUTSIDE_SAMPLED_WINDOW', 'min_v': low, 'max_v': high}


def run(db_path, spec_path, out, binary='ngspice'):
    _, spec, components, corners, nodes = prepare(db_path, spec_path)
    bound_db, bound_spec = sha(db_path), sha(spec_path)
    binary = shutil.which(binary) or (str(Path(binary).resolve()) if Path(binary).is_file() else None)
    if binary is None:
        raise ValueError('ngspice unavailable; no simulation evidence produced')
    out = Path(out); out.mkdir(parents=True, exist_ok=False)
    version = subprocess.run([binary, '--version'], capture_output=True, text=True, timeout=10)
    if version.returncode:
        raise ValueError('Cannot identify ngspice version')
    (out / 'version.txt').write_text(version.stdout + version.stderr)
    records, values = [], []
    for i, corner in enumerate(corners):
        name = 'corner-%02d' % i
        cir = out / (name + '.cir'); cir.write_text(deck(spec, components, corner, nodes))
        proc = subprocess.run([binary, '-n', '-b', str(cir.resolve())], cwd=out, capture_output=True, text=True, timeout=30)
        (out / (name + '.stdout')).write_text(proc.stdout); (out / (name + '.stderr')).write_text(proc.stderr)
        try:
            value = measured(proc.stdout, proc.stderr, proc.returncode)
        except ValueError as exc:
            (out / 'failure.json').write_text(json.dumps({'status': 'INSUFFICIENT', 'corner': i, 'error': str(exc), 'returncode': proc.returncode}) + '\n')
            raise
        values.append(value)
        records.append({'corner': list(corner), 'returncode': proc.returncode, 'value_v': value})
    # A concurrent edit must not bind old decks to a new specification.
    prepare(db_path, spec_path)
    if sha(db_path) != bound_db or sha(spec_path) != bound_spec:
        raise ValueError('Inputs changed during simulation; rerun in a new directory')
    report = {'schema_version': 1, 'db_sha256': bound_db, 'spec_sha256': bound_spec,
              'check_id': spec['check_id'], 'state': spec['state'], 'model': spec['model'],
              'scope': 'Ideal physical R/C subcircuit endpoint samples only; assumptions/source qualification require expert review. Not full-board PASS or guaranteed worst case between corners.',
              **summary(spec, values), 'corners': records,
              'artifacts': {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()}}
    (out / 'simulation.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def verify(db_path, spec_path, report_path):
    _, spec, components, corners, nodes = prepare(db_path, spec_path)
    report_path = Path(report_path); report = json.loads(report_path.read_text())
    if report['db_sha256'] != sha(db_path) or report['spec_sha256'] != sha(spec_path):
        raise ValueError('Simulation binding changed')
    required = {'version.txt'} | {f'corner-{i:02d}.{ext}' for i in range(len(corners)) for ext in ('cir', 'stdout', 'stderr')}
    if set(report['artifacts']) != required or len(report['corners']) != len(corners):
        raise ValueError('Incomplete corner artifacts')
    for name, expected in report['artifacts'].items():
        path = report_path.parent / name
        if path.is_symlink() or sha(path) != expected:
            raise ValueError('Simulation artifact changed: ' + name)
    values = []
    for i, (corner, record) in enumerate(zip(corners, report['corners'])):
        name = 'corner-%02d' % i
        if record['corner'] != list(corner) or (report_path.parent / (name + '.cir')).read_text() != deck(spec, components, corner, nodes):
            raise ValueError('Deck differs from bound physical model')
        value = measured((report_path.parent / (name + '.stdout')).read_text(), (report_path.parent / (name + '.stderr')).read_text(), record['returncode'])
        if record['value_v'] != value:
            raise ValueError('Summary differs from raw measurement')
        values.append(value)
    if any(report.get(k) != v for k, v in summary(spec, values).items()) or any(report.get(k) != spec[k] for k in ('check_id', 'state', 'model')) or report.get('schema_version') != 1:
        raise ValueError('Report identity or window verdict changed')
    return {'valid': True, 'status': report['status'], 'checked_corners': len(corners)}


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--db', type=Path, required=True)
    cli.add_argument('--spec', type=Path, required=True)
    cli.add_argument('--out', type=Path)
    cli.add_argument('--verify', type=Path, help='Replay bindings/decks/raw measurements without rerunning solver')
    cli.add_argument('--ngspice', default='ngspice')
    args = cli.parse_args()
    if bool(args.out) == bool(args.verify):
        cli.error('Choose exactly one of --out or --verify')
    try:
        result = verify(args.db, args.spec, args.verify) if args.verify else run(args.db, args.spec, args.out, args.ngspice)
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        cli.exit(2, 'INSUFFICIENT: ' + str(exc) + '\n')
    print(json.dumps({k: result[k] for k in ('valid', 'status', 'checked_corners', 'min_v', 'max_v') if k in result}))

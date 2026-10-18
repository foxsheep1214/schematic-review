#!/usr/bin/env python3
"""Typical-circuit bench: what SR reports on real single-module open-hardware boards.

    python3 -B evals/typical_circuits/run.py [--case ID] [--show] [--sut <other SR checkout>]

Each case is a small open-source KiCad board (one function: an LDO module, a CAN
transceiver, an H-bridge ...) exported to a KiCad XML netlist and stored under
fixtures/. SR runs cold (parse_kicad.py strict, then lint.py with an empty export
log). Every FINDING and CANDIDATE it reports must be classified in cases.json:

  expected            a real issue or a correct review lead; must still be reported
  known_false_alarms  reported today, wrong on this board; reason recorded, tracked until fixed
  fixed_false_alarms  was wrong and has been fixed; must not come back

A report matching none of them is UNCLASSIFIED and fails the bench, so every new
finding on a real board is read by a person once. Matching is by rule id plus a
substring of the detail text. INFO items are not judged.
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
JUDGED_KINDS = ('FINDING', 'CANDIDATE')


def run_sr(sut, case, work):
    scripts = sut / 'scripts'
    fixture = HERE / case['fixture']
    db = work / 'db.json'
    proc = subprocess.run([sys.executable, '-B', str(scripts / 'parse_kicad.py'), str(fixture), '-o', str(db)],
                          capture_output=True, text=True, timeout=600)
    strict = db.exists()
    if not strict:
        subprocess.run([sys.executable, '-B', str(scripts / 'parse_kicad.py'), str(fixture), '-o', str(db),
                        '--no-strict'], capture_output=True, text=True, timeout=600)
    if not db.exists():
        return None, 'parse_kicad wrote no db: ' + proc.stderr[-300:]
    log = work / 'export.log'
    log.write_text('', encoding='utf-8')
    out = work / 'lint.json'
    cmd = [sys.executable, '-B', str(scripts / 'lint.py'), str(db), '--log', str(log), '--json', str(out),
           '--plan-json', str(work / 'plan.json')]
    if case.get('intent'):
        cmd += ['--intent', str(HERE / case['intent'])]
    lint = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if not out.exists():
        return None, 'lint.py wrote no findings: ' + (lint.stderr or lint.stdout)[-300:]
    findings = json.loads(out.read_text(encoding='utf-8')).get('findings', [])
    return {'strict_parse': strict, 'findings': [f for f in findings if f.get('kind', 'FINDING') in JUDGED_KINDS]}, None


def matches(finding, entry):
    return finding.get('rule') == entry['rule'] and entry.get('match', '') in str(finding.get('detail', ''))


def judge(case, observed):
    rows, findings = [], observed['findings']
    claimed = set()
    for label in ('expected', 'known_false_alarms', 'fixed_false_alarms'):
        for entry in case.get(label, []):
            hit = [i for i, f in enumerate(findings) if matches(f, entry)]
            claimed.update(hit)
            if label == 'expected':
                status = 'DETECTED' if hit else 'MISSED'
            elif label == 'known_false_alarms':
                status = 'KNOWN_FALSE_ALARM' if hit else 'FALSE_ALARM_GONE'
            else:
                status = 'FALSE_ALARM_BACK' if hit else 'FIXED'
            rows.append({'status': status, 'rule': entry['rule'], 'match': entry.get('match', ''),
                         'why': entry.get('why', '')})
    for i, f in enumerate(findings):
        if i not in claimed:
            rows.append({'status': 'UNCLASSIFIED', 'rule': f.get('rule'), 'kind': f.get('kind'),
                         'match': str(f.get('detail', ''))[:160]})
    return rows


FAILING = {'MISSED', 'FALSE_ALARM_BACK', 'UNCLASSIFIED', 'FALSE_ALARM_GONE'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--sut', default=str(ROOT), help='SR checkout to test (default: this one)')
    parser.add_argument('--case', action='append', help='run only these case ids')
    parser.add_argument('--show', action='store_true', help='print every judged row, not only failures')
    parser.add_argument('--json', help='write all observations and verdicts here')
    args = parser.parse_args(argv)
    cases = json.loads((HERE / 'cases.json').read_text(encoding='utf-8'))['cases']
    if args.case:
        cases = [c for c in cases if c['id'] in args.case]
    totals, report = {}, {}
    for case in cases:
        with tempfile.TemporaryDirectory() as tmp:
            observed, error = run_sr(Path(args.sut), case, Path(tmp))
        rows = [{'status': 'ERROR', 'rule': '-', 'match': error}] if error else judge(case, observed)
        report[case['id']] = {'rows': rows, 'strict_parse': observed and observed['strict_parse']}
        counts = {}
        for row in rows:
            counts[row['status']] = counts.get(row['status'], 0) + 1
            totals[row['status']] = totals.get(row['status'], 0) + 1
        print('%-28s %-22s %s' % (case['id'], case['category'], json.dumps(counts, ensure_ascii=False)))
        for row in rows:
            if args.show or row['status'] in FAILING or row['status'] == 'ERROR':
                print('    %-18s %-8s %s %s' % (row['status'], row['rule'], row['match'],
                                               ('— ' + row['why']) if row.get('why') else ''))
    print('\ntotal:', json.dumps(totals, ensure_ascii=False))
    if args.json:
        Path(args.json).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 1 if any(totals.get(s) for s in FAILING | {'ERROR'}) else 0


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""KiCad native replay bench: frozen answers for SR's KiCad delivery layer.

For every case in cases.json, run the SR checkout under test on a frozen KiCad XML
fixture exactly as a reviewer would start a cold pass:
  parse_kicad.py (strict; --no-strict only to obtain a db when strict wrote none)
  lint.py --log <log> [--intent <intent>] --json --plan-json --decoupling-json
and compare the observed automatic results with expected.json:
  MATCH           observed == frozen answer
  KNOWN           observed == the recorded value of a known, documented deviation
  MISMATCH        anything else (a regression, or an unreviewed improvement)
This bench covers the input layer only; it says nothing about review verdicts.
"""
import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=600)


def _load(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None


def observe(sut, case, work):
    """Run SR on one case; return the observed field values (never raises on SR failure)."""
    scripts = sut / 'scripts'
    fixture = HERE / case['fixture']
    strict_db, db_path = work / 'db.strict.json', work / 'db.json'
    obs = {}
    proc = _run([sys.executable, '-B', str(scripts / 'parse_kicad.py'), str(fixture), '-o', str(strict_db)])
    obs['parse.strict_exit'] = proc.returncode
    obs['parse.strict_db_written'] = strict_db.exists()
    if strict_db.exists():
        strict_db.replace(db_path)
    else:
        loose = _run([sys.executable, '-B', str(scripts / 'parse_kicad.py'), str(fixture), '-o', str(db_path),
                      '--no-strict'])
        if not db_path.exists():
            obs['error'] = 'parse_kicad wrote no db: ' + (loose.stderr or proc.stderr)[-400:]
            return obs
    db = _load(db_path)
    obs['parse.self_check_passed'] = db.get('integrity', {}).get('self_check_passed')
    obs['parse.missing_functional_pins'] = db.get('pin_name_coverage', {}).get('missing_functional_pins')
    obs['parse.parts'] = len(db['parts'])
    obs['parse.nets'] = len(db['nets'])

    lint_json, plan_json, dec_json = work / 'lint.json', work / 'plan.json', work / 'decoupling.json'
    cmd = [sys.executable, '-B', str(scripts / 'lint.py'), str(db_path), '--json', str(lint_json),
           '--plan-json', str(plan_json), '--decoupling-json', str(dec_json)]
    if case['log'] == 'empty':
        log = work / 'netlist-export.log'
        log.write_text('', encoding='utf-8')   # kicad-cli prints nothing on a clean export
        cmd += ['--log', str(log)]
    elif case['log'] != 'none':
        raise ValueError('unknown log mode %r' % case['log'])
    if case.get('intent'):
        cmd += ['--intent', str(HERE / case['intent'])]
    proc = _run(cmd)
    obs['lint.exit'] = proc.returncode
    lint, plan, dec = _load(lint_json), _load(plan_json), _load(dec_json)
    if lint is None or plan is None or dec is None:
        obs['error'] = 'lint.py wrote no lint/plan/decoupling json: ' + (proc.stderr or proc.stdout)[-400:]
        return obs
    skipped = {item[0] for item in lint.get('skipped', [])}
    obs['lint.DOC-A01_executed'] = 'DOC-A01' not in skipped
    obs['lint.DOC-A02_executed'] = 'DOC-A02' not in skipped
    q01 = [c for c in plan['checks'] if c['rule'] == 'DOC-Q01']
    obs['plan.DOC-Q01'] = [{'id': c['id'], 'applicability': c['applicability'], 'readiness': c['readiness']}
                           for c in q01]
    obs['plan.checks_total'] = len(plan['checks'])
    obs['plan.not_applicable'] = sum(c['applicability'] == 'NOT_APPLICABLE' for c in plan['checks'])
    # .get: an older SR may lack a field; that is reported as a difference, not a crash.
    obs['decoupling.discovery_gaps'] = dec.get('discovery_gaps')
    obs['decoupling.pin_names_resolved_by_official_pinout'] = dec.get('pin_names_resolved_by_official_pinout')
    obs['decoupling.group_gaps'] = {'%s/%s' % (state['id'], group['declared_id']): group['gaps']
                                    for state in dec.get('states', []) for group in state['groups']}
    return obs


def judge(case_id, observed, expected):
    """Per-field verdicts for one case."""
    exp = expected['cases'].get(case_id)
    if exp is None:
        return [{'field': '*', 'status': 'MISMATCH', 'note': 'no frozen answer for this case'}]
    if 'error' in observed:
        return [{'field': 'error', 'status': 'MISMATCH', 'observed': observed['error']}]
    rows = []
    for field, want in exp['fields'].items():
        got = observed.get(field)
        known = exp.get('known_deviations', {}).get(field)
        if got == want:
            status = 'MATCH'
        elif known is not None and got == known['observed']:
            status = 'KNOWN'
        else:
            status = 'MISMATCH'
        row = {'field': field, 'status': status}
        if status != 'MATCH':
            row.update(expected=want, observed=got)
            if known is not None:
                row['note'] = known['reason']
        rows.append(row)
    return rows


def changes(old, new):
    """Fields whose observed value differs between two runs of this bench."""
    out = {}
    for case_id, obs in new.items():
        before = old.get(case_id, {})
        diff = {f: {'before': before.get(f), 'after': obs.get(f)}
                for f in sorted(set(before) | set(obs)) if before.get(f) != obs.get(f)}
        if diff:
            out[case_id] = diff
    for case_id in sorted(set(old) - set(new)):
        out[case_id] = {'*': 'case missing from this run'}
    return out


def _short(value, limit=160):
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return text if len(text) <= limit else text[:limit] + '…'


def report(verdicts, diff=None):
    lines = ['| 用例 | 字段数 | 一致 | 已知偏差 | 不一致 |', '|---|---|---|---|---|']
    totals = {'MATCH': 0, 'KNOWN': 0, 'MISMATCH': 0}
    for case_id, rows in verdicts.items():
        count = {k: sum(r['status'] == k for r in rows) for k in totals}
        for k in totals:
            totals[k] += count[k]
        lines.append('| %s | %d | %d | %d | %d |' % (case_id, len(rows), count['MATCH'], count['KNOWN'],
                                                      count['MISMATCH']))
    lines += ['', '合计：%d 个用例，%d 个字段；一致 %d，已知偏差 %d，不一致 %d。' % (
        len(verdicts), sum(totals.values()), totals['MATCH'], totals['KNOWN'], totals['MISMATCH'])]
    mismatch = [(c, r) for c, rows in verdicts.items() for r in rows if r['status'] == 'MISMATCH']
    if mismatch:
        lines += ['', '## 不一致（逐例）', '']
        for case_id, row in mismatch:
            lines.append('- `%s` %s：预期 %s，实际 %s' % (
                case_id, row['field'], _short(row.get('expected')), _short(row.get('observed'))))
    known = {}
    for case_id, rows in verdicts.items():
        for row in rows:
            if row['status'] == 'KNOWN':
                known.setdefault((row['field'], row['note']), []).append(case_id)
    if known:
        lines += ['', '## 已知偏差（仍等于记录的 main 现值）', '']
        for (field, note), cases in known.items():
            lines.append('- %s：%s。用例：%s' % (field, note, '、'.join(cases)))
    if diff is not None:
        lines += ['', '## 与旧结果对比', '']
        if not diff:
            lines.append('与旧 results.json 逐字段相同。')
        for case_id, fields in diff.items():
            if not isinstance(fields, dict):
                continue
            for field, change in fields.items():
                if isinstance(change, str):
                    lines.append('- `%s`：%s' % (case_id, change))
                else:
                    lines.append('- `%s` %s：%s → %s' % (case_id, field, _short(change['before']),
                                                        _short(change['after'])))
    return '\n'.join(lines) + '\n', totals


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--sut', type=Path, default=HERE.parents[1], help='SR checkout under test')
    ap.add_argument('--out', type=Path, help='directory for results.json and report.md')
    ap.add_argument('--compare', type=Path, help='earlier results.json; list every observed field that changed')
    ap.add_argument('--case', action='append', help='run only these case ids')
    args = ap.parse_args()
    cases = json.loads((HERE / 'cases.json').read_text(encoding='utf-8'))['cases']
    expected = json.loads((HERE / 'expected.json').read_text(encoding='utf-8'))
    if args.case:
        cases = [c for c in cases if c['id'] in args.case]
    sut = args.sut.resolve()
    start = time.time()
    observed, verdicts = {}, {}
    for case in cases:
        with tempfile.TemporaryDirectory(prefix='kicad-replay-') as tmp:
            observed[case['id']] = observe(sut, case, Path(tmp))
        verdicts[case['id']] = judge(case['id'], observed[case['id']], expected)
    diff = None
    if args.compare:
        diff = changes(json.loads(args.compare.read_text(encoding='utf-8'))['observed'], observed)
    text, totals = report(verdicts, diff)
    result = {'sut': str(sut), 'seconds': round(time.time() - start, 1), 'totals': totals,
              'observed': observed, 'verdicts': verdicts, 'changes': diff}
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / 'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding='utf-8')
        (args.out / 'report.md').write_text(text, encoding='utf-8')
    print(text + '用时 %.0f 秒' % result['seconds'])
    return 1 if totals['MISMATCH'] else 0


if __name__ == '__main__':
    sys.exit(main())

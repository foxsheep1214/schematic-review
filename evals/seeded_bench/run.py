#!/usr/bin/env python3
"""Seeded-defect bench: does lint/plan notice netlist defects planted in real boards?

For every board in the prepared cache and every applicable mutation site, run the
SR cold pass (lint + plan) on the original and on the mutant and record:
  auto     - a NEW lint finding of a target rule that names the mutated site
  other    - a NEW lint finding of any other rule that names the site
  pointed  - a per-object plan check (any rule) whose object names the site, i.e.
             expert review is at least directed to the mutated part
This measures the automatic tier only; it says nothing about expert review.
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import mutators  # noqa: E402


def offline_boards(directory):
    """Corpus boards whose netlist ships in the repo (evals/typical_circuits), parsed into `directory`.
    Boards that need a git fetch and kicad-cli are left to prepare.py."""
    corpus = json.loads((HERE / 'corpus.json').read_text(encoding='utf-8'))
    boards = []
    for board in corpus['boards']:
        if not board.get('fixture', '').endswith(('.xml', '.net')):
            continue
        out = Path(directory) / (board['id'] + '.json')
        cmd = [sys.executable, '-B', str(ROOT / 'scripts' / 'parse_kicad.py'), str(ROOT / board['fixture']), '-o', str(out)]
        subprocess.run(cmd if board.get('strict', True) else cmd + ['--no-strict'], check=True, capture_output=True)
        boards.append({'id': board['id'], 'db': str(out)})
    return boards


def below_baseline(summary, baseline):
    """Defect types whose automatic detections fell under the frozen baseline, or that now error."""
    worse = []
    for defect, want in baseline['auto'].items():
        row = summary.get(defect, {'auto': 0, 'errors': 0})
        if row['auto'] < want or row['errors']:
            worse.append('%s auto %d < %d (errors %d)' % (defect, row['auto'], want, row['errors']))
    return worse


def lint(sut, db, work, intent=None):
    dbp, lp, pp = work / 'db.json', work / 'lint.json', work / 'plan.json'
    dbp.write_text(json.dumps(db), encoding='utf-8')
    for p in (lp, pp):
        p.unlink(missing_ok=True)
    extra = []
    if intent is not None:
        import copy
        from board_intent import input_fingerprint
        from plan_review import rail_candidates
        bound = copy.deepcopy(intent)
        for net in rail_candidates(db, bound):
            bound.setdefault('power_rails', {}).setdefault(net, {'citation': 'SEED source topology; voltage unconfirmed'})
        bound['input_sha256'] = input_fingerprint(db)
        ip = work / 'intent.json'
        ip.write_text(json.dumps(bound), encoding='utf-8')
        extra = ['--intent', str(ip)]
    proc = subprocess.run([sys.executable, '-B', str(sut / 'scripts' / 'lint.py'), str(dbp),
                           '--json', str(lp), '--plan-json', str(pp)] + extra,
                          capture_output=True, text=True, timeout=120)
    if not lp.exists():
        return None, None, proc.stderr[-400:]
    plan = json.loads(pp.read_text(encoding='utf-8')) if pp.exists() else {'checks': []}
    return json.loads(lp.read_text(encoding='utf-8'))['findings'], plan['checks'], None


def located(text, tokens):
    return any(re.search(r'(?<![\w.])' + re.escape(t) + r'(?![\w])', text) for t in tokens)



def contract_guards(contract, checks):
    """Explicit probe obligations, separate from new automatic findings."""
    observations, errors = {}, []
    for ref in contract.get('guard_no_proposal_pass', []):
        rows = [c for c in checks if c['rule']=='DEV-C01' and c.get('object', {}).get('ref')==ref]
        observations[ref] = [c.get('proposal') for c in rows]
        if not rows or any(c.get('proposal', {}).get('result') is not None for c in rows):
            errors.append(ref + ': unknown supply must have a located unknown proposal')
        if rows and not any('power_rails.' in str(c.get('proposal', {}).get('bases', [])) + (c.get('proposal', {}).get('note') or '') for c in rows):
            errors.append(ref + ': unknown supply dependency is missing')
    for ref in contract.get('guard_no_pass', []):
        rows = [c for c in checks if c['rule']=='DEV-C01' and c.get('object', {}).get('ref')==ref]
        observations[ref] = [c.get('proposal') for c in rows]
        if not rows or any(c.get('proposal', {}).get('result') == 'PASS' for c in rows):
            errors.append(ref + ': the written rating must not pre-judge PASS')
    wanted = contract.get('min_channel_rows')
    if wanted:
        rows = [c for c in checks if c['rule']==wanted['rule'] and c.get('object', {}).get('ref')==wanted['ref']]
        observations['channel_objects'] = [c['object'] for c in rows]
        if len(rows) < wanted['count']:
            errors.append('array lost individual channel rows')
    prefix = contract.get('required_plan_prefix')
    if prefix:
        observations['fault_rows'] = [c['id'] for c in checks if c['id'].startswith(prefix)]
        if not observations['fault_rows']:
            errors.append('official opto map lost feedback-open fault row')
    return observations, errors


def compare_sites(records, before):
    """Reject losing any previous target at its physical site, even if another site compensates."""
    key = lambda r: (r['board'], r['defect'], r['site'])
    current = {key(r): r for r in records}
    errors = []
    for old in before.get('records', []):
        new = current.get(key(old))
        if new is None:
            errors.append('missing old site: ' + repr(key(old)))
        elif 'error' in new or not set(old.get('auto', [])) <= set(new.get('auto', [])):
            errors.append('old automatic target lost: ' + repr(key(old)))
    return errors


def evaluate(sut, boards):
    records, baselines = [], {}
    with tempfile.TemporaryDirectory(prefix='seeded-bench-') as tmp:
        work = Path(tmp)
        for board in boards:
            db = json.loads(Path(board['db']).read_text(encoding='utf-8'))
            base, _, err = lint(sut, db, work)
            if base is None:
                baselines[board['id']] = {'error': err}
                continue
            seen = {(f['rule'], f['detail']) for f in base}
            baselines[board['id']] = {'findings': len(base),
                                      'by_rule': dict(sorted(_count(f['rule'] for f in base).items()))}
            source = mutators.board_mutations(db) if board.get('board_seeds_only') else mutators.mutations(db)
            for m in source:
                paired_seen = seen
                if m.baseline is not None or m.intent is not None:
                    paired, _, error = lint(sut, m.baseline if m.baseline is not None else db, work, m.intent)
                    if paired is None:
                        records.append({'board': board['id'], 'defect': m.defect, 'site': m.site, 'error': 'paired baseline: ' + str(error)})
                        continue
                    paired_seen = {(f['rule'], f['detail']) for f in paired}
                findings, checks, err = lint(sut, m.db, work, m.intent)
                rec = {'board': board['id'], 'defect': m.defect, 'site': m.site, 'note': m.note,
                       'targets': list(m.targets)}
                if m.contract:
                    rec['contract'] = m.contract
                    rec['paired_baseline'] = m.baseline is not None
                if findings is None:
                    rec['error'] = err
                    records.append(rec)
                    continue
                tokens = m.refs + m.nets
                new = [f for f in findings if (f['rule'], f['detail']) not in paired_seen and located(f['detail'], tokens)]
                rec['auto'] = sorted({f['rule'] for f in new if f['rule'] in m.targets})
                rec['other'] = sorted({f['rule'] for f in new if f['rule'] not in m.targets})
                rec['pointed'] = sorted({c['rule'] for c in checks if 'board' not in c.get('object', {})
                                         and located(json.dumps(c.get('object', {}), ensure_ascii=False), tokens)})
                rec['planned_targets'] = sorted({c['rule'] for c in checks if c['rule'] in m.targets
                                                 and located(json.dumps(c.get('object', {}), ensure_ascii=False), tokens)})
                observations, errors = contract_guards(m.contract, checks)
                if observations:
                    rec['contract_guards'] = observations
                if errors:
                    rec['error'] = '; '.join(errors)
                records.append(rec)
    return records, baselines


def _count(items):
    out = defaultdict(int)
    for item in items:
        out[item] += 1
    return out


def summarize(records):
    table = {}
    for rec in records:
        row = table.setdefault(rec['defect'], {'sites': 0, 'boards': set(), 'auto': 0, 'any': 0,
                                               'pointed': 0, 'errors': 0})
        row['sites'] += 1
        row['boards'].add(rec['board'])
        if 'error' in rec:
            row['errors'] += 1
            continue
        row['auto'] += bool(rec['auto'])
        row['any'] += bool(rec['auto'] or rec['other'])
        row['pointed'] += bool(rec['pointed'])
    for row in table.values():
        row['boards'] = len(row['boards'])
    return dict(sorted(table.items()))


def report(summary, baselines, compare=None):
    lines = ['| 缺陷类型 | 电路数 | 位点 | 自动检出(目标规则) | 位点有任意新发现 | 计划有逐对象检查指向 | 运行错误 |',
             '|---|---|---|---|---|---|---|']
    for defect, row in summary.items():
        delta = ''
        if compare and defect in compare:
            delta = ' (前 %d)' % compare[defect]['auto']
        lines.append('| %s | %d | %d | %d%s | %d | %d | %d |' % (
            defect, row['boards'], row['sites'], row['auto'], delta, row['any'], row['pointed'], row['errors']))
    total = sum(r['sites'] for r in summary.values())
    auto = sum(r['auto'] for r in summary.values())
    lines += ['', '合计：%d 个位点，自动检出 %d（%.0f%%）。' % (total, auto, 100.0 * auto / max(total, 1)), '',
              '基线（未植入）发现数：' + '，'.join('%s %s' % (k, v.get('findings', 'ERR')) for k, v in baselines.items())]
    return '\n'.join(lines) + '\n'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cache', type=Path, help='directory written by prepare.py')
    ap.add_argument('--offline', action='store_true', help='use only the corpus boards stored in the repo')
    ap.add_argument('--gate', type=Path, help='baseline.json: exit 1 if any defect type detects fewer sites')
    ap.add_argument('--sut', type=Path, default=HERE.parents[1], help='SR checkout under test')
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--boards-cache', type=Path, help='append the adjudicated merge-board controlled pairs')
    ap.add_argument('--compare', type=Path, help='earlier results.json to show auto-detection deltas')
    args = ap.parse_args()
    if not args.offline and not args.cache:
        ap.error('--cache or --offline is required')
    start = time.time()
    with tempfile.TemporaryDirectory(prefix='seeded-db-') as dbdir:
        boards = (offline_boards(dbdir) if args.offline
                  else json.loads((args.cache / 'manifest.json').read_text(encoding='utf-8')))
        if args.boards_cache:
            manifest = {'boards': []}
            for name in ('boards-merge1.json', 'boards-merge2b.json', 'boards-merge3.json', 'boards-merge4.json',
                         'boards-merge5.json', 'boards-merge6.json'):
                manifest['boards'].extend(json.loads((HERE / name).read_text(encoding='utf-8'))['boards'])
            from parse_kicad import build
            from parse_netlist import integrity_problems
            for item in manifest['boards']:
                source = args.boards_cache / item['id'] / 'netlist.xml'
                db = build(str(source))
                db['integrity'] = {'self_check_passed': not integrity_problems(db)}
                target = Path(dbdir) / (item['id'] + '.json')
                target.write_text(json.dumps(db), encoding='utf-8')
                boards.append({'id': item['id'], 'db': str(target), 'board_seeds_only': True})
        records, baselines = evaluate(args.sut.resolve(), boards)
    summary = summarize(records)
    before = json.loads(args.compare.read_text(encoding='utf-8')) if args.compare else None
    compare = before['summary'] if before else None
    regressions = compare_sites(records, before) if before else []
    args.out.mkdir(parents=True, exist_ok=True)
    result = {'sut': str(args.sut), 'seconds': round(time.time() - start, 1), 'boards': boards,
              'baselines': baselines, 'summary': summary, 'records': records, 'site_regressions': regressions}
    (args.out / 'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding='utf-8')
    text = report(summary, baselines, compare)
    (args.out / 'report.md').write_text(text, encoding='utf-8')
    print(text + '用时 %.0f 秒' % result['seconds'])
    if args.gate:
        worse = below_baseline(summary, json.loads(args.gate.read_text(encoding='utf-8')))
        print('\n'.join(worse) or 'gate: no defect type below baseline')
        return 1 if worse else 0
    if regressions:
        print('\n'.join(regressions))
    return 1 if regressions or any('error' in row for row in records) or any('error' in row for row in baselines.values()) else 0


if __name__ == '__main__':
    sys.exit(main())

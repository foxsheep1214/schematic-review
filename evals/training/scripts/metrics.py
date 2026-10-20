#!/usr/bin/env python3
"""一轮训练的指标（README 第 4 节）→ runs/<round>/metrics.json。

能自动算的：fix_pair_recall_cold / _plan、seeded_recall、mature_cold_false_alarms、typical_gate、replay_gate。
要热审、批评 agent 或裁决才有的（fix_pair_recall_hot、p0_precision、misfile_rate、lookup_honesty）缺输入时记 null 并写明原因。
"""
import argparse, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
FAILING = ('MISSED', 'FALSE_ALARM_BACK', 'UNCLASSIFIED', 'FALSE_ALARM_GONE', 'ERROR')


def load(path):
    return json.load(open(path, encoding='utf-8')) if path.exists() else None


def locator(location):
    tokens = [t for t in location.get('refs', []) + location.get('nets', []) if t]
    pats = [re.compile(r'(?<![A-Za-z0-9_/.-])' + re.escape(t) + r'(?![A-Za-z0-9_])') for t in tokens]
    return lambda text: any(p.search(text or '') for p in pats)


def corpus(dirs, name, key):
    items = []
    for d in dirs:
        data = load(pathlib.Path(d) / f'{name}.json') or {}
        items += data.get(key, [])
    return items


def fix_pair_recall(round_dir, pairs):
    rows, cold, plan, hot = [], 0, 0, None
    hot_seen = 0
    for p in pairs:
        bdir = round_dir / 'reviews' / (p['id'] + '.before')
        lint, planj = load(bdir / 'lint.json'), load(bdir / 'plan.json')
        if lint is None or planj is None:
            rows.append({'pair': p['id'], 'reviewed': False}); continue
        at = locator(p['defect_location'])
        hits = [f'{f["rule"]}:{f.get("kind")}' for f in lint.get('findings', [])
                if f.get('kind') in ('FINDING', 'CANDIDATE') and (at(f.get('detail')) or at(f.get('ref')))]
        checks = [c['id'] for c in planj.get('checks', []) if at(json.dumps(c.get('object'), ensure_ascii=False))]
        hot_res = load(round_dir / 'hot' / (p['id'] + '.before') / 'review-results.json')
        hot_hit = None
        if hot_res is not None:
            hot_seen += 1
            hot_hit = any(r.get('verdict') in ('FAIL', 'INSUFFICIENT') and at(json.dumps(r, ensure_ascii=False))
                          for r in hot_res.get('results', hot_res if isinstance(hot_res, list) else []))
            hot = (hot or 0) + int(hot_hit)
        cold += bool(hits); plan += bool(checks)
        rows.append({'pair': p['id'], 'reviewed': True, 'cold_hits': hits, 'plan_rows': checks, 'hot_hit': hot_hit})
    n = sum(r['reviewed'] for r in rows)
    return {'pairs_total': len(pairs), 'pairs_reviewed': n,
            'fix_pair_recall_cold': round(cold / n, 3) if n else None,
            'fix_pair_recall_plan': round(plan / n, 3) if n else None,
            'fix_pair_recall_hot': round(hot / hot_seen, 3) if hot_seen else None,
            'fix_pair_recall_hot_reason': None if hot_seen else 'no hot review of a fix-pair before version this round',
            'per_pair': rows}


def mature_false_alarms(round_dir, boards, adjudications):
    findings, checks, per = 0, 0, []
    for b in boards:
        lint, planj = load(round_dir / 'reviews' / b['id'] / 'lint.json'), load(round_dir / 'reviews' / b['id'] / 'plan.json')
        if lint is None or planj is None:
            continue
        f = sum(1 for x in lint.get('findings', []) if x.get('kind') == 'FINDING')
        c = len(planj.get('checks', []))
        findings += f; checks += c; per.append({'board': b['id'], 'findings': f, 'checks': c})
    adjudicated = sum(1 for a in adjudications if a.get('decision') in ('OVER_STRICT', 'NOT_A_DEFECT')
                      and a.get('board') in {b['id'] for b in boards})
    return {'boards_reviewed': len(per), 'findings': findings, 'checks': checks,
            'mature_cold_false_alarms': round(100 * findings / checks, 2) if checks else None,
            'adjudicated_false_alarms': adjudicated, 'per_board': per}


def seeded_recall(round_dir):
    res = load(round_dir / 'seeded' / 'results.json')
    if not res:
        return {'seeded_recall': None, 'seeded_recall_reason': 'no seeded/results.json'}
    summ = res.get('summary', {})
    sites = sum(v.get('sites', 0) for v in summ.values()); auto = sum(v.get('auto', 0) for v in summ.values())
    return {'seeded_recall': round(auto / sites, 3) if sites else None, 'seeded_sites': sites, 'seeded_auto': auto,
            'seeded_per_defect': {k: round(v['auto'] / v['sites'], 3) for k, v in summ.items() if v.get('sites')}}


def gates(round_dir):
    typ = load(round_dir / 'typical.json') or {}
    counts = {s: 0 for s in FAILING}
    for board in typ.values():
        for r in board.get('rows', []):
            if r['status'] in counts:
                counts[r['status']] += 1
    rep = load(round_dir / 'replay' / 'results.json') or {}
    return {'typical_gate': counts, 'typical_boards': len(typ),
            'replay_gate': rep.get('totals', {}).get('MISMATCH'), 'replay_totals': rep.get('totals')}


def adjudication_items(adj_dir):
    items = []
    for f in sorted(pathlib.Path(adj_dir).glob('*.json')):
        if f.name == 'TEMPLATE.json':
            continue
        items += (load(f) or {}).get('items', [])
    return items


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--round', required=True)
    ap.add_argument('--corpus', action='append', default=[], help='语料目录，可重复（默认 evals/training/corpus）')
    ap.add_argument('--adjudications', default=str(ROOT / 'evals/training/adjudications'))
    ap.add_argument('--out')
    args = ap.parse_args()
    rd = pathlib.Path(args.round)
    dirs = args.corpus or [str(ROOT / 'evals/training/corpus')]
    adj = adjudication_items(args.adjudications)
    m = {'round': rd.name, 'corpus_dirs': dirs, 'adjudication_items': len(adj)}
    m.update(fix_pair_recall(rd, corpus(dirs, 'fix-pairs', 'pairs')))
    m.update(mature_false_alarms(rd, corpus(dirs, 'mature-boards', 'boards'), adj))
    m.update(seeded_recall(rd))
    m.update(gates(rd))
    hot_boards = sorted(p.name for p in (rd / 'hot').glob('*/review-results.json')) if (rd / 'hot').exists() else []
    critic = sorted(p.name for p in (rd / 'critic').glob('*.json')) if (rd / 'critic').exists() else []
    m['hot_reviews'] = len(hot_boards); m['critic_files'] = len(critic)
    p0 = [a for a in adj if a.get('level') == 'P0' or a.get('critic_verdict')]
    m['p0_precision'] = round(sum(a.get('decision') == 'TRUE_RISK' for a in p0) / len(p0), 3) if p0 else None
    m['p0_precision_reason'] = None if p0 else 'no adjudicated P0 items (needs hot review + critic + human)'
    mis = [a for a in adj if a.get('decision') in ('MISFILED_STAGE', 'MISFILED_CAUSE')]
    m['misfile_rate'] = None if not hot_boards else round(len(mis) / max(1, len(adj)), 3)
    m['misfile_rate_reason'] = None if hot_boards else 'no hot review this round'
    m['lookup_honesty'] = None; m['lookup_honesty_reason'] = 'needs critic agent spot checks of “已读 X 第 N 页” claims'
    out = pathlib.Path(args.out) if args.out else rd / 'metrics.json'
    json.dump(m, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    keys = ('fix_pair_recall_cold', 'fix_pair_recall_plan', 'fix_pair_recall_hot', 'seeded_recall',
            'mature_cold_false_alarms', 'p0_precision', 'misfile_rate', 'lookup_honesty', 'typical_gate', 'replay_gate')
    for k in keys:
        print(f'{k:28s} {m.get(k)}')
    print('->', out)
    return 0


if __name__ == '__main__':
    sys.exit(main())

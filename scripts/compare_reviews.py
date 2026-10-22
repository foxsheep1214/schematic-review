#!/usr/bin/env python3
"""Where two reviews of the same board disagree, row by row.

    python3 scripts/compare_reviews.py <review A> <review B> [--json compare.json] [--md compare.md]

Each argument is a review directory (holding record/) or its record/ directory. The two must have been made
from the same netlist (db_sha256); the tool still compares when they differ and says so.

What is aligned: intent circuits by type and shared parts (names and states differ between reviewers, so the
plan rows they expand into are keyed by rule, matched circuit, state and part rather than by id); rows by that
key; open items and findings by the rows they decide. What is reported: the rows both reviewed and how often
they agree, every row only one of them had, every row they judged differently (grouped by what kind of
difference it is), the open items and findings only one of them raised, and the function verdicts side by
side. The numbers measure how far two records of one method drift; they do not say which reviewer is right.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from electrical_contract import load_json
from review_stage_scope import outside_stage

MATCH_FLOOR = 0.25   # least share of parts two circuits of one type must have in common to be the same block
SIDES = ('A', 'B')


def load(where):
    where = Path(where)
    record = where if (where / 'review-plan.json').is_file() else where / 'record'
    plan = load_json(record / 'review-plan.json')
    results = load_json(record / 'review-results.json')
    return {'where': str(where), 'plan': plan, 'results': results}


def verdict(row):
    """One word per row: PASS / FAIL / INSUFFICIENT / NA / NA_STAGE / UNREVIEWED."""
    if not isinstance(row, dict):
        return 'UNREVIEWED'
    if outside_stage(row):
        return 'NA_STAGE'
    if row.get('applicability') == 'NOT_APPLICABLE' or row.get('review_result') == 'NA':
        return 'NA'
    return row.get('review_result') or 'UNREVIEWED'


def frames(plan):
    return [f for f in plan.get('functions') or [] if isinstance(f, dict) and f.get('id')]


def jaccard(a, b):
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if a | b else 0.0


def match_circuits(frames_a, frames_b):
    """Greedy best-overlap pairing of circuits of the same type; returns ([(frame a, frame b, overlap)], left a, left b)."""
    candidates = []
    for fa in frames_a:
        for fb in frames_b:
            if fa.get('circuit_type') != fb.get('circuit_type'):
                continue
            overlap = jaccard((fa.get('objects') or {}).get('refs') or [], (fb.get('objects') or {}).get('refs') or [])
            if overlap >= MATCH_FLOOR:
                candidates.append((overlap, fa, fb))
    pairs, used_a, used_b = [], set(), set()
    for overlap, fa, fb in sorted(candidates, key=lambda c: -c[0]):
        if fa['id'] in used_a or fb['id'] in used_b:
            continue
        pairs.append((fa, fb, overlap))
        used_a.add(fa['id'])
        used_b.add(fb['id'])
    return (pairs, [f for f in frames_a if f['id'] not in used_a], [f for f in frames_b if f['id'] not in used_b])


def row_key(check, circuit_alias):
    """How a row is matched across reviewers: a circuit row by rule, aligned circuit, state and part; any other by id."""
    obj = check.get('object') if isinstance(check.get('object'), dict) else {}
    circuit = obj.get('circuit')
    if circuit and circuit in circuit_alias:
        state = obj.get('state')
        return '%s|%s|%s|%s' % (check.get('rule'), circuit_alias[circuit],
                                state.lower() if isinstance(state, str) else '', obj.get('ref') or obj.get('net') or '')
    return check.get('id')


def keyed_rows(side, circuit_alias):
    plan_rows = {c['id']: c for c in side['plan'].get('checks') or [] if isinstance(c, dict) and c.get('id')}
    results = {c['id']: c for c in side['results'].get('checks') or [] if isinstance(c, dict) and c.get('id')}
    out = {}
    for cid, planned in plan_rows.items():
        key = row_key(planned, circuit_alias)
        row = results.get(cid)
        out[key] = {'id': cid, 'rule': planned.get('rule'), 'verdict': verdict(row),
                    'open_ref': (row or {}).get('open_ref'), 'fail_ref': (row or {}).get('fail_ref'),
                    'finding_id': (row or {}).get('finding_id'),
                    'rationale': ((row or {}).get('rationale') or '')[:160]}
    return out


def difference_kind(va, vb):
    if va == vb:
        return 'same'
    if 'FAIL' in (va, vb):
        return 'one FAIL'
    if 'INSUFFICIENT' in (va, vb) and 'PASS' in (va, vb):
        return 'PASS vs INSUFFICIENT'
    if va.startswith('NA') or vb.startswith('NA'):
        return 'NA vs judged'
    return 'other'


def open_items(side, rows_by_id):
    """Open and fail items with the row keys they decide (through open_ref / fail_ref)."""
    items = []
    for fn in side['results'].get('functions') or []:
        if not isinstance(fn, dict):
            continue
        for field in ('open', 'fails'):
            for item in fn.get(field) or []:
                if not isinstance(item, dict) or not item.get('key'):
                    continue
                ref = '%s/%s' % (fn.get('id'), item['key'])
                keys = {k for k, r in rows_by_id.items() if r.get('open_ref') == ref or r.get('fail_ref') == ref}
                items.append({'ref': ref, 'field': field, 'kind': item.get('kind') or 'FAIL',
                              'level': (item.get('severity') or {}).get('level') if isinstance(item.get('severity'), dict) else None,
                              'what': item.get('what'), 'aspects': len(item.get('decides') or []), 'rows': sorted(keys)})
    return items


def match_items(items_a, items_b):
    pairs, used = [], set()
    for ia in items_a:
        best = max(((jaccard(ia['rows'], ib['rows']), i) for i, ib in enumerate(items_b) if i not in used and ia['rows']),
                   default=(0.0, None))
        if best[1] is not None and best[0] >= MATCH_FLOOR:
            used.add(best[1])
            pairs.append((ia, items_b[best[1]], round(best[0], 2)))
    return pairs, [i for i in items_a if not any(i is p[0] for p in pairs)], [i for j, i in enumerate(items_b) if j not in used]


def findings(side, rows_by_id):
    out = []
    id_to_key = {r['id']: k for k, r in rows_by_id.items()}
    for f in side['results'].get('findings') or []:
        if isinstance(f, dict) and f.get('id'):
            out.append({'id': f['id'], 'title': f.get('title'), 'severity': f.get('severity'), 'kind': f.get('kind'),
                        'rows': sorted(id_to_key.get(c, c) for c in f.get('check_ids') or []),
                        'refs': sorted((f.get('location') or {}).get('refs') or [])})
    return out


def match_findings(fa, fb):
    pairs, used = [], set()
    for a in fa:
        for i, b in enumerate(fb):
            if i in used:
                continue
            if (set(a['rows']) & set(b['rows'])) or (set(a['refs']) & set(b['refs']) and
                                                       {r.split('|')[0].split('.')[0] for r in a['rows']}
                                                       & {r.split('|')[0].split('.')[0] for r in b['rows']}):
                pairs.append((a, b))
                used.add(i)
                break
    return pairs, [a for a in fa if not any(a is p[0] for p in pairs)], [b for j, b in enumerate(fb) if j not in used]


def function_verdicts(side):
    return {fn['id']: fn.get('verdict') for fn in side['results'].get('functions') or [] if isinstance(fn, dict) and fn.get('id')}


def compare(a, b):
    pairs, left_a, left_b = match_circuits(frames(a['plan']), frames(b['plan']))
    alias_a = {fa.get('circuit'): 'C%d' % i for i, (fa, fb, _) in enumerate(pairs)}
    alias_b = {fb.get('circuit'): 'C%d' % i for i, (fa, fb, _) in enumerate(pairs)}
    rows_a, rows_b = keyed_rows(a, alias_a), keyed_rows(b, alias_b)
    shared = sorted(set(rows_a) & set(rows_b))
    matrix = Counter((rows_a[k]['verdict'], rows_b[k]['verdict']) for k in shared)
    differences = {}
    for k in shared:
        kind = difference_kind(rows_a[k]['verdict'], rows_b[k]['verdict'])
        if kind != 'same':
            differences.setdefault(kind, []).append({'key': k, 'A': rows_a[k], 'B': rows_b[k]})
    items_a, items_b = open_items(a, rows_a), open_items(b, rows_b)
    item_pairs, items_only_a, items_only_b = match_items(items_a, items_b)
    find_a, find_b = findings(a, rows_a), findings(b, rows_b)
    find_pairs, find_only_a, find_only_b = match_findings(find_a, find_b)
    verdicts_a, verdicts_b = function_verdicts(a), function_verdicts(b)
    circuits = [{'A': fa['id'], 'B': fb['id'], 'overlap': round(o, 2),
                 'states': {'A': fa.get('states'), 'B': fb.get('states')},
                 'verdict': {'A': verdicts_a.get(fa['id']), 'B': verdicts_b.get(fb['id'])}} for fa, fb, o in pairs]
    agree = sum(n for (va, vb), n in matrix.items() if va == vb)
    return {
        'schema_version': 1,
        'inputs': {'A': a['where'], 'B': b['where']},
        'same_netlist': a['plan'].get('db_sha256') == b['plan'].get('db_sha256'),
        'circuits': {'matched': circuits, 'only_A': [f['id'] for f in left_a], 'only_B': [f['id'] for f in left_b]},
        'rows': {'A': len(rows_a), 'B': len(rows_b), 'shared': len(shared), 'agree': agree,
                 'agreement': round(agree / len(shared), 3) if shared else None,
                 'matrix': [{'A': va, 'B': vb, 'rows': n} for (va, vb), n in sorted(matrix.items(), key=lambda x: -x[1])],
                 'only_A': sorted(set(rows_a) - set(rows_b)), 'only_B': sorted(set(rows_b) - set(rows_a)),
                 'verdicts': {'A': dict(Counter(r['verdict'] for r in rows_a.values())),
                              'B': dict(Counter(r['verdict'] for r in rows_b.values()))}},
        'differences': {kind: rows for kind, rows in sorted(differences.items())},
        'open_items': {'matched': [{'A': ia['ref'], 'B': ib['ref'], 'overlap': o} for ia, ib, o in item_pairs],
                       'only_A': items_only_a, 'only_B': items_only_b,
                       'kinds': {'A': dict(Counter('%s/%s' % (i['kind'], i['level']) for i in items_a)),
                                 'B': dict(Counter('%s/%s' % (i['kind'], i['level']) for i in items_b))}},
        'findings': {'matched': [{'A': fa_['id'], 'B': fb_['id']} for fa_, fb_ in find_pairs],
                     'only_A': find_only_a, 'only_B': find_only_b},
        'functions': {'A': verdicts_a, 'B': verdicts_b},
    }


def markdown(report):
    rows = report['rows']
    lines = ['# 两份审查记录的差异', '',
             '| 项目 | A | B |', '|---|---|---|',
             '| 记录 | %s | %s |' % (report['inputs']['A'], report['inputs']['B']),
             '| 同一份网表 | %s | |' % ('是' if report['same_netlist'] else '否'),
             '| 计划行数 | %d | %d |' % (rows['A'], rows['B']),
             '| 两边都有的行 | %d | |' % rows['shared'],
             '| 两边结论相同 | %d（%s） | |' % (rows['agree'], ('%.0f%%' % (100 * rows['agreement'])) if rows['agreement'] is not None else '—'),
             '| 只在一边的行 | %d | %d |' % (len(rows['only_A']), len(rows['only_B'])),
             '| 结论分布 | %s | %s |' % (_counts(rows['verdicts']['A']), _counts(rows['verdicts']['B'])),
             '| 待办/失败项（类型/等级） | %s | %s |' % (_counts(report['open_items']['kinds']['A']), _counts(report['open_items']['kinds']['B'])),
             '| 只在一边的待办 | %d | %d |' % (len(report['open_items']['only_A']), len(report['open_items']['only_B'])),
             '| 发现的错误 | %d（只在本边 %d） | %d（只在本边 %d） |' % (
                 len(report['findings']['matched']) + len(report['findings']['only_A']), len(report['findings']['only_A']),
                 len(report['findings']['matched']) + len(report['findings']['only_B']), len(report['findings']['only_B'])),
             '', '## 电路对齐', '', '| A | B | 共同位号占比 | A 状态 | B 状态 | A 结论 | B 结论 |', '|---|---|---|---|---|---|---|']
    for c in report['circuits']['matched']:
        lines.append('| %s | %s | %s | %s | %s | %s | %s |' % (
            c['A'], c['B'], c['overlap'], '、'.join(c['states']['A'] or []), '、'.join(c['states']['B'] or []),
            c['verdict']['A'], c['verdict']['B']))
    if report['circuits']['only_A'] or report['circuits']['only_B']:
        lines.append('')
        lines.append('只在 A：%s；只在 B：%s' % ('、'.join(report['circuits']['only_A']) or '—', '、'.join(report['circuits']['only_B']) or '—'))
    lines += ['', '## 两边都审了、结论不同的行', '']
    for kind, items in report['differences'].items():
        lines.append('### %s（%d 行）' % (kind, len(items)))
        lines.append('')
        lines.append('| 行 | A | B |')
        lines.append('|---|---|---|')
        for d in items:
            lines.append('| %s | %s | %s |' % (d['key'], _cell(d['A']), _cell(d['B'])))
        lines.append('')
    lines += ['## 只有一边提出的发现', '']
    for side in SIDES:
        for f in report['findings']['only_' + side]:
            lines.append('- 只在 %s：%s %s（%s）行 %s' % (side, f['id'], f.get('title') or '', f.get('severity'), '、'.join(f['rows'])))
    lines += ['', '## 只有一边提出的待办', '']
    for side in SIDES:
        for i in report['open_items']['only_' + side]:
            lines.append('- 只在 %s：%s %s/%s，%d 个方面，%d 行：%s' % (side, i['ref'], i['kind'], i['level'], i['aspects'], len(i['rows']), i.get('what') or ''))
    return '\n'.join(lines) + '\n'


def _counts(counter):
    return '、'.join('%s %d' % (k, v) for k, v in sorted(counter.items()))


def _cell(row):
    ref = row.get('open_ref') or row.get('fail_ref') or ''
    return '%s %s %s' % (row['verdict'], ref, row['id']) if ref else '%s %s' % (row['verdict'], row['id'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('a')
    parser.add_argument('b')
    parser.add_argument('--json', help='write the full comparison here')
    parser.add_argument('--md', help='write the Markdown summary here')
    args = parser.parse_args(argv)
    report = compare(load(args.a), load(args.b))
    if args.json:
        Path(args.json).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    text = markdown(report)
    if args.md:
        Path(args.md).write_text(text, encoding='utf-8')
    rows = report['rows']
    print('行 A %d / B %d，共同 %d，结论相同 %d；只在一边的发现 A %d / B %d；只在一边的待办 A %d / B %d%s' % (
        rows['A'], rows['B'], rows['shared'], rows['agree'], len(report['findings']['only_A']),
        len(report['findings']['only_B']), len(report['open_items']['only_A']), len(report['open_items']['only_B']),
        '' if report['same_netlist'] else '；两份记录不是同一份网表'))
    return 0


if __name__ == '__main__':
    sys.exit(main())

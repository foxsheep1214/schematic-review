#!/usr/bin/env python3
"""Where two reviews of the same board disagree, row by row.

    python3 scripts/compare_reviews.py <review A> <review B> [--alias aliases.json] [--json compare.json] [--md compare.md]

Each argument is a review directory (holding record/) or its record/ directory.

The formal numbers (`strict`, merge plan of 2026-10-21 §5) count only rows that ask the same check: the same
rule at the same revision, the same physical object (display names aside, nets with their full path, state as
written) and the same criterion (`check_key.key`). A pair the keys do not make may enter only as a VERIFIED_ALIAS
from --alias ({A, B, evidence} per pair: same rule and criterion, same netlist, a located citation). Reported with
their denominators: alignment coverage 2M/(N_A+N_B), answered completeness C/M, agreement A/C over the pairs both
answered and full agreement 2A/(N_A+N_B); duplicate keys, unmatched rows, missing answers, FAIL against PASS and
disagreements on rows a P0/P1 finding names are listed. Two records of different netlists are BASELINE_MISMATCH: the
numbers are diagnostic only.

The overlap layer (`suggested`) aligns circuits by type and shared parts, rows by rule, aligned circuit, state and
part, and open items and findings by the rows they decide; it suggests pairs among the unmatched rows and never
enters a denominator. The numbers measure how far two records of one method drift; they do not say which is right.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from electrical_contract import load_json
from review_stage_scope import outside_stage
import check_key
import rule_gaps
from review_functions import located

MATCH_FLOOR = 0.25   # least share of parts two circuits of one type must have in common to be the same block
SIDES = ('A', 'B')
ANSWERS = ('PASS', 'FAIL', 'INSUFFICIENT', 'NA', 'NA_STAGE')
SEVERE = ('P0', 'P1')


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


def _ratio(num, den):
    return num / den if den else 'N/A'


def _keys(side):
    """{check key: [plan row ids]}, the rows whose stored key is stale, and whether the plan carries keys at all."""
    rows = [c for c in side['plan'].get('checks') or [] if isinstance(c, dict) and c.get('id')
            and c.get('origin') != rule_gaps.ORIGIN]   # fixed requirements, step 7: added rows are counted apart
    out, stale = {}, []
    for c in rows:
        key = check_key.key(c, side['plan'].get('assemblies'))
        out.setdefault(key, []).append(c['id'])
        if 'check_key' in c and c['check_key'] != key:
            stale.append(c['id'])
    contract = 'CURRENT' if rows and all('check_key' in c for c in rows) else 'LEGACY_CONTRACT'
    return out, sorted(stale), contract


def _severe_rows(side):
    return {cid for f in side['results'].get('findings') or [] if isinstance(f, dict) and f.get('severity') in SEVERE
            for cid in f.get('check_ids') or []}


def strict(a, b, aliases=(), same_netlist=True):
    """Pairs by check key and verified alias only; every count and denominator shown."""
    keys_a, stale_a, contract_a = _keys(a)
    keys_b, stale_b, contract_b = _keys(b)
    results = {side: {c['id']: c for c in s['results'].get('checks') or [] if isinstance(c, dict) and c.get('id')}
               for side, s in (('A', a), ('B', b))}
    plans = {side: {c['id']: c for c in s['plan'].get('checks') or [] if isinstance(c, dict) and c.get('id')}
             for side, s in (('A', a), ('B', b))}
    duplicates = {side: [{'key': k, 'ids': sorted(ids)} for k, ids in sorted(keys.items()) if len(ids) > 1]
                  for side, keys in (('A', keys_a), ('B', keys_b))}
    single_a = {k: ids[0] for k, ids in keys_a.items() if len(ids) == 1}
    single_b = {k: ids[0] for k, ids in keys_b.items() if len(ids) == 1}
    pairs = [{'key': k, 'A': single_a[k], 'B': single_b[k], 'match': 'EXACT'} for k in sorted(set(single_a) & set(single_b))]
    left_a = {single_a[k] for k in set(single_a) - set(single_b)}
    left_b = {single_b[k] for k in set(single_b) - set(single_a)}
    refused = []
    for alias in aliases or []:
        ia, ib = alias.get('A'), alias.get('B')
        pa, pb = plans['A'].get(ia), plans['B'].get(ib)
        reason = None
        if not (pa and pb):
            reason = 'row not in its plan'
        elif ia not in left_a or ib not in left_b:
            reason = 'row already paired or duplicated'
        elif pa.get('rule') != pb.get('rule') or pa.get('criterion') != pb.get('criterion'):
            reason = 'rule or criterion differs'
        elif not same_netlist:
            reason = 'different netlists'
        elif not located({'locator': alias.get('evidence')}):
            reason = 'evidence locates nothing'
        if reason:
            refused.append({'A': ia, 'B': ib, 'reason': reason})
            continue
        pairs.append({'key': None, 'A': ia, 'B': ib, 'match': 'VERIFIED_ALIAS', 'evidence': alias['evidence']})
        left_a.discard(ia)
        left_b.discard(ib)
    severe = _severe_rows(a) | _severe_rows(b)
    for pair in pairs:
        pair['A_verdict'] = verdict(results['A'].get(pair['A']))
        pair['B_verdict'] = verdict(results['B'].get(pair['B']))
    answered = [p for p in pairs if p['A_verdict'] in ANSWERS and p['B_verdict'] in ANSWERS]
    same = [p for p in answered if p['A_verdict'] == p['B_verdict']]
    n_a, n_b, m = len(keys_a), len(keys_b), len(pairs)
    transitions = Counter((p['A_verdict'], p['B_verdict']) for p in answered)
    return {
        'contract': {'A': contract_a, 'B': contract_b},
        'stale_keys': {'A': stale_a, 'B': stale_b},
        'counts': {'N_A': n_a, 'N_B': n_b, 'exact': sum(p['match'] == 'EXACT' for p in pairs),
                   'verified_alias': sum(p['match'] == 'VERIFIED_ALIAS' for p in pairs), 'M': m,
                   'C': len(answered), 'same': len(same)},
        'metrics': {'alignment_coverage': _ratio(2 * m, n_a + n_b), 'answered_completeness': _ratio(len(answered), m),
                    'agreement': _ratio(len(same), len(answered)), 'full_agreement': _ratio(2 * len(same), n_a + n_b)},
        'diagnostic_only': not same_netlist,
        'transitions': [{'A': va, 'B': vb, 'rows': n} for (va, vb), n in sorted(transitions.items(), key=lambda x: (-x[1], x[0]))],
        'pairs': pairs,
        'duplicates': duplicates,
        'unmatched': {'A': sorted(left_a), 'B': sorted(left_b)},
        'missing_result': [{'A': p['A'], 'B': p['B'], 'A_verdict': p['A_verdict'], 'B_verdict': p['B_verdict']}
                           for p in pairs if p not in answered],
        'aliases_refused': refused,
        'reviewer_added': {side: sorted(c['id'] for c in rule_gaps.added(s['plan'].get('checks') or []))
                           for side, s in (('A', a), ('B', b))},
        'fail_vs_pass': [p for p in answered if {p['A_verdict'], p['B_verdict']} == {'PASS', 'FAIL'}],
        'severe_disagreements': [p for p in answered if p['A_verdict'] != p['B_verdict'] and (p['A'] in severe or p['B'] in severe)],
    }


def compare(a, b, aliases=()):
    same_netlist = a['plan'].get('db_sha256') == b['plan'].get('db_sha256')
    report = {'schema_version': 2, 'inputs': {'A': a['where'], 'B': b['where']},
              'baseline': {'status': 'SAME_INPUT' if same_netlist else 'BASELINE_MISMATCH',
                           'db_sha256': {'A': a['plan'].get('db_sha256'), 'B': b['plan'].get('db_sha256')}},
              'strict': strict(a, b, aliases, same_netlist), 'suggested': suggested(a, b)}
    unmatched_a, unmatched_b = set(report['strict']['unmatched']['A']), set(report['strict']['unmatched']['B'])
    pairs = []
    for key in report['suggested']['rows']['shared_keys']:
        ia, ib = report['suggested']['rows']['ids'][key]
        if ia in unmatched_a and ib in unmatched_b:
            pairs.append({'A': ia, 'B': ib})
    report['strict']['suggested_pairs'] = pairs
    return report


def suggested(a, b):
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
        'circuits': {'matched': circuits, 'only_A': [f['id'] for f in left_a], 'only_B': [f['id'] for f in left_b]},
        'rows': {'A': len(rows_a), 'B': len(rows_b), 'shared': len(shared), 'agree': agree,
                 'agreement': round(agree / len(shared), 3) if shared else None,
                 'matrix': [{'A': va, 'B': vb, 'rows': n} for (va, vb), n in sorted(matrix.items(), key=lambda x: -x[1])],
                 'only_A': sorted(set(rows_a) - set(rows_b)), 'only_B': sorted(set(rows_b) - set(rows_a)),
                 'shared_keys': shared, 'ids': {k: (rows_a[k]['id'], rows_b[k]['id']) for k in shared},
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
    st, sug = report['strict'], report['suggested']
    c, m = st['counts'], st['metrics']

    def pct(x):
        return '%.1f%%' % (100 * x) if isinstance(x, float) else x

    lines = ['# 两份审查记录的差异', '',
             '| 项目 | A | B |', '|---|---|---|',
             '| 记录 | %s | %s |' % (report['inputs']['A'], report['inputs']['B']),
             '| 输入基线 | %s | |' % ('同一份网表' if report['baseline']['status'] == 'SAME_INPUT'
                                    else '不是同一份网表：下面的数字只作诊断'),
             '| 计划格式 | %s | %s |' % (st['contract']['A'], st['contract']['B']), '',
             '## 精确配对（只算同一项检查）', '',
             '| 计数 | 值 |', '|---|---|',
             '| 两边各自的检查项数 N_A / N_B | %d / %d |' % (c['N_A'], c['N_B']),
             '| 配对 M（同键 / 核实的别名） | %d（%d / %d） |' % (c['M'], c['exact'], c['verified_alias']),
             '| 两边都作答 C | %d |' % c['C'], '| 结论相同 | %d |' % c['same'], '',
             '| 指标 | 值 |', '|---|---|',
             '| 对齐覆盖率 2M/(N_A+N_B) | %s |' % pct(m['alignment_coverage']),
             '| 配对作答完整率 C/M | %s |' % pct(m['answered_completeness']),
             '| 作答配对的一致率 | %s |' % pct(m['agreement']),
             '| 全范围相同结论覆盖率 | %s |' % pct(m['full_agreement']), '',
             '| A 的结论 | B 的结论 | 行数 |', '|---|---|---|']
    lines += ['| %s | %s | %d |' % (t['A'], t['B'], t['rows']) for t in st['transitions']]
    for title, items in (('FAIL 对 PASS', st['fail_vs_pass']), ('P0/P1 发现所在行的分歧', st['severe_disagreements'])):
        if items:
            lines += ['', '### %s' % title, '']
            lines += ['- A %s %s，B %s %s' % (p['A'], p['A_verdict'], p['B'], p['B_verdict']) for p in items]
    for side in SIDES:
        if st['duplicates'][side]:
            lines.append('')
            lines.append('%s 有重复的检查项：%s' % (side, '；'.join('、'.join(d['ids']) for d in st['duplicates'][side])))
    lines += ['', '只在 A：%d 行；只在 B：%d 行；缺结论的配对：%d；被拒的别名：%d。' % (
        len(st['unmatched']['A']), len(st['unmatched']['B']), len(st['missing_result']), len(st['aliases_refused']))]
    lines += ['', '审查员补加（规则缺口，不计入配对）：A %d 行，B %d 行。' % (
        len(st['reviewer_added']['A']), len(st['reviewer_added']['B']))]
    rows = sug['rows']
    lines += ['', '## 建议配对（按电路与位号重合，不进入上面的指标）', '',
              '精确配对之外按重合度建议配对 %d 对，供人工核对是否同一项检查。' % len(st['suggested_pairs']), '',
              '| 项目 | A | B |', '|---|---|---|',
              '| 按重合度对齐的行 | %d | |' % rows['shared'],
              '| 只在一边的行 | %d | %d |' % (len(rows['only_A']), len(rows['only_B'])),
              '| 结论分布 | %s | %s |' % (_counts(rows['verdicts']['A']), _counts(rows['verdicts']['B'])),
              '| 待办/失败项（类型/等级） | %s | %s |' % (_counts(sug['open_items']['kinds']['A']), _counts(sug['open_items']['kinds']['B'])),
              '| 只在一边的待办 | %d | %d |' % (len(sug['open_items']['only_A']), len(sug['open_items']['only_B'])),
              '| 发现的错误 | %d（只在本边 %d） | %d（只在本边 %d） |' % (
                  len(sug['findings']['matched']) + len(sug['findings']['only_A']), len(sug['findings']['only_A']),
                  len(sug['findings']['matched']) + len(sug['findings']['only_B']), len(sug['findings']['only_B'])),
              '', '### 电路对齐', '', '| A | B | 共同位号占比 | A 状态 | B 状态 | A 结论 | B 结论 |', '|---|---|---|---|---|---|---|']
    for circuit in sug['circuits']['matched']:
        lines.append('| %s | %s | %s | %s | %s | %s | %s |' % (
            circuit['A'], circuit['B'], circuit['overlap'], '、'.join(circuit['states']['A'] or []),
            '、'.join(circuit['states']['B'] or []), circuit['verdict']['A'], circuit['verdict']['B']))
    if sug['circuits']['only_A'] or sug['circuits']['only_B']:
        lines.append('')
        lines.append('只在 A：%s；只在 B：%s' % ('、'.join(sug['circuits']['only_A']) or '—', '、'.join(sug['circuits']['only_B']) or '—'))
    lines += ['', '### 按重合度对齐、结论不同的行', '']
    for kind, items in sug['differences'].items():
        lines += ['#### %s（%d 行）' % (kind, len(items)), '', '| 行 | A | B |', '|---|---|---|']
        lines += ['| %s | %s | %s |' % (d['key'], _cell(d['A']), _cell(d['B'])) for d in items]
        lines.append('')
    lines += ['### 只有一边提出的发现', '']
    for side in SIDES:
        for f in sug['findings']['only_' + side]:
            lines.append('- 只在 %s：%s %s（%s）行 %s' % (side, f['id'], f.get('title') or '', f.get('severity'), '、'.join(f['rows'])))
    lines += ['', '### 只有一边提出的待办', '']
    for side in SIDES:
        for i in sug['open_items']['only_' + side]:
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
    parser.add_argument('--alias', help='JSON list of {A, B, evidence}: row pairs the keys do not make, with a located citation')
    parser.add_argument('--json', help='write the full comparison here')
    parser.add_argument('--md', help='write the Markdown summary here')
    args = parser.parse_args(argv)
    aliases = load_json(args.alias) if args.alias else []
    report = compare(load(args.a), load(args.b), aliases)
    if args.json:
        Path(args.json).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    text = markdown(report)
    if args.md:
        Path(args.md).write_text(text, encoding='utf-8')
    c, m = report['strict']['counts'], report['strict']['metrics']
    print('要求 A %d / B %d，配对 %d（别名 %d），两边作答 %d，结论相同 %d；对齐覆盖 %s，一致率 %s%s' % (
        c['N_A'], c['N_B'], c['M'], c['verified_alias'], c['C'], c['same'],
        m['alignment_coverage'] if m['alignment_coverage'] == 'N/A' else '%.3f' % m['alignment_coverage'],
        m['agreement'] if m['agreement'] == 'N/A' else '%.3f' % m['agreement'],
        '' if report['baseline']['status'] == 'SAME_INPUT' else '；两份记录不是同一份网表，只作诊断'))
    return 0


if __name__ == '__main__':
    sys.exit(main())

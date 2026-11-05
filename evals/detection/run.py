#!/usr/bin/env python3
"""Aggregate detection evidence by design criterion; standard library only."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import catalog  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import eval_set  # noqa: E402
KNOWN = eval_set.root() / '已知缺陷' / 'known_defects.json'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def criteria_for(rules, basis):
    return sorted({c for r in rules for c in basis.get(r, ())})


def seeded_rows(data, basis):
    rows = []
    for rec in data['records']:
        targets = rec['targets']
        criteria = criteria_for(targets, basis)
        ident = '/'.join((rec['board'], rec['defect'], rec['site']))
        # The unit is the planted defect, with alternative target rules. BASIS
        # supplies associations, not proof that every clause was exercised.
        status = ('error' if 'error' in rec else
                  'hit' if set(rec.get('auto', ())) & set(targets) else 'miss')
        rows.append(dict(id=ident, origin='seeded', criteria=criteria,
                         status=status, rules=targets, note=rec.get('note', '')))
    for board, baseline in data.get('baselines', {}).items():
        if 'error' in baseline:
            rows.append(dict(id=board, origin='seeded', criteria=[], status='error',
                             rules=[], note=baseline['error']))
    return rows


def typical_rows(data, basis):
    statuses = {'DETECTED': 'hit', 'MISSED': 'miss', 'KNOWN_FALSE_ALARM': 'fp',
                'FALSE_ALARM_BACK': 'fp', 'FALSE_ALARM_GONE': 'tn', 'FIXED': 'tn',
                'UNCLASSIFIED': 'unclassified', 'ERROR': 'error'}
    return [dict(id=f"{case}/{i}", origin='typical', criteria=criteria_for([r['rule']], basis),
                 status=statuses[r['status']], rules=[r['rule']], note=r.get('match', ''))
            for case, result in data.items() for i, r in enumerate(result['rows'])]


def validate_known(records, criteria, rules):
    seen = set()
    for rec in records:
        if rec['id'] in seen:
            raise ValueError('duplicate known defect: ' + rec['id'])
        seen.add(rec['id'])
        if type(rec['caught']) is not bool and rec['caught'] != 'unknown':
            raise ValueError('caught must be true/false/unknown: ' + rec['id'])
        if set(rec['criteria']) - set(criteria) or set(rec['sr_rules']) - set(rules):
            raise ValueError('unknown criterion/rule: ' + rec['id'])
        if rec['kind'] not in ('electrical', 'review_process', 'rule_audit'):
            raise ValueError('unknown evidence kind: ' + rec['id'])
        if not rec['source'] or not rec['note']:
            raise ValueError('missing provenance: ' + rec['id'])
        source, _, title = rec['source'].partition(' :: ')
        path = ROOT / source
        if not title or not path.is_file() or title not in path.read_text(encoding='utf-8'):
            raise ValueError('source title not found: ' + rec['id'])


def known_rows(records):
    return [dict(id=r['id'], origin='history', criteria=r['criteria'],
                 status='unknown' if r['caught'] == 'unknown' else 'hit' if r['caught'] else 'miss',
                 rules=r['sr_rules'], note=r['note'], kind=r['kind']) for r in records]


def aggregate(criteria, basis, rows):
    table = {c: dict(rules=sorted(r for r, cs in basis.items() if c in cs), counts=Counter(),
                     origins={o: Counter() for o in ('seeded', 'typical', 'history')}, real=Counter())
             for c in criteria}
    unmapped = []
    seen = set()
    for row in rows:
        # Exact identity only; no dedup across distinct benches or historical episodes.
        key = (row['origin'], row['id'])
        if key in seen:
            raise ValueError('duplicate observation: ' + str(key))
        seen.add(key)
        for c in set(row['criteria']):
            if c not in table:
                raise ValueError('unknown criterion: ' + c)
            cell = table[c]
            cell['counts'][row['status']] += 1
            cell['origins'][row['origin']][row['status']] += 1
            if row.get('kind') == 'electrical':
                cell['real'][row['status']] += 1
        if not row['criteria']:
            unmapped.append(row)
    return table, unmapped


def positive(counts):
    return sum(counts[s] for s in ('hit', 'miss', 'unknown', 'error'))


def render(criteria, table, rows, unmapped, provenance, auxiliary):
    totals = Counter()
    for cell in table.values():
        totals.update(cell['counts'])
    lines = ['# SR 按设计准则的检出力度量', '',
             '自动层为本次离线运行；历史清单为来源记载的当时结果，未重审。', '',
             f"准则 {len(table)} 条；有规则 {sum(bool(x['rules']) for x in table.values())} 条。",
             f"按准则归属计数：正例 {positive(totals)}，命中 {totals['hit']}，漏报 {totals['miss']}，"
             f"未知 {totals['unknown']}，运行错误 {totals['error']}，误报 {totals['fp']}；负例通过 {totals['tn']}，未分类 {totals['unclassified']}。", '',
             '**归属计数不是独立缺陷数，也不是逐条准则已验证的证明。** BASIS 是规则的粗映射；一条规则核多条准则，'
             '同一用例可出现在多行。典型 expected 含正确线索，不能合称真缺陷。', '',
             '| 来源 | 唯一正例/缺陷 | 命中 | 漏报 | 未知 | 错误 | 误报 | 负例通过 | 未分类 |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for origin in ('seeded', 'typical', 'history'):
        counts = Counter(r['status'] for r in rows if r['origin'] == origin)
        lines.append('| %s | %d | %s |' % (origin, positive(counts), ' | '.join(str(counts[s]) for s in
                     ('hit', 'miss', 'unknown', 'error', 'fp', 'tn', 'unclassified'))))
    lines += ['', '## 有已知缺陷或正例的准则', '',
              '历史真缺陷 H/M/? 只含清单 kind=electrical；其余历史项是审查过程缺陷或规则审计。', '',
              '| 准则 | 标题 | SR规则数 | 已知缺陷/正例 | 命中 | 漏报 | 未知 | 错误 | 误报 | 真缺陷 H/M/? |',
              '|---|---|---:|---:|---:|---:|---:|---:|---:|---|']
    for c, cell in table.items():
        n = cell['counts']
        if positive(n):
            real = cell['real']
            lines.append(f"| {c} | {criteria[c]['title']} | {len(cell['rules'])} | {positive(n)} | {n['hit']} | {n['miss']} | {n['unknown']} | {n['error']} | {n['fp']} | {real['hit']}/{real['miss']}/{real['unknown']} |")
    empty = [c for c, x in table.items() if not positive(x['counts'])]
    lines += ['', f'## 没有任何已知缺陷或正例：{len(empty)} 条（检出力完全未知）', '',
              '| 准则 | 标题 | SR规则数 | 已知缺陷/正例 | 命中 | 漏报 | 误报 |',
              '|---|---|---:|---:|---:|---:|---:|']
    for c in empty:
        lines.append(f"| {c} | {criteria[c]['title']} | {len(table[c]['rules'])} | 0 | 0 | 0 | {table[c]['counts']['fp']} |")
    never = [c for c, x in table.items() if x['rules'] and not (x['real']['hit'] or x['real']['miss'])]
    missed = [c for c, x in table.items() if x['real']['miss']]
    lines += ['', '## 真缺陷验证缺口与误报集中点', '',
              f"有检查但无已确认真缺陷检出结果：{len(never)} 条：" + '、'.join(never), '',
              f"历史真缺陷漏报过：{len(missed)} 条：" + ('、'.join(missed) or '无已确认记录'), '',
              '| 误报准则 | 数量 | SR规则 |', '|---|---:|---|']
    for c in sorted(table, key=lambda c: (-table[c]['counts']['fp'], c)):
        if table[c]['counts']['fp']:
            rules = sorted({r for row in rows if c in row['criteria'] and row['status'] == 'fp' for r in row['rules']})
            lines.append(f"| {c} | {table[c]['counts']['fp']} | {', '.join(rules)} |")
    fp_rules = Counter(r for row in rows if row['status'] == 'fp' for r in row['rules'])
    lines += ['', '全部观测误报按规则：' + ('，'.join(f'{r} {n}' for r, n in fp_rules.most_common()) or '无') +
              '。无 BASIS 映射的误报不强配准则；不能把准则表中的 0 误报解读为 SR 没有误报。']
    history = [r for r in rows if r['origin'] == 'history']
    kinds = Counter(r['kind'] for r in history)
    lines += ['', f"历史清单 {len(history)} 条：" + '，'.join(f'{k} {v}' for k, v in sorted(kinds.items())) +
              f"；准则留空 {sum(not r['criteria'] for r in history)} 条。", '',
              '## 尚未归到准则的观测', '',
              f'共 {len(unmapped)} 条；保留规则与数量，不静默丢弃。下表按来源、规则、状态分组。', '',
              '| 来源 | SR规则 | 状态 | 数量 |', '|---|---|---|---:|']
    groups = Counter((r['origin'], ', '.join(r['rules']) or '—', r['status']) for r in unmapped)
    lines += [f'| {o} | {r} | {s} | {n} |' for (o, r, s), n in sorted(groups.items())]
    lines += ['', '## 数据指纹与辅助基准', '', '| 输入 | SHA256 |', '|---|---|']
    lines += [f'| {name} | `{sha}` |' for name, sha in provenance]
    lines += ['', *auxiliary, '', '未知、错误、未分类均不充作漏报或误报。原板未被判定合格，种子基线发现数不算误报。',
              '本表不证明专家检出力、独立评测、适用工况覆盖或设计准出；不能据零样本删除规则。', '']
    return '\n'.join(lines)


def execute(script, args, work):
    env = dict(os.environ, TMPDIR=str(work), PYTHONDONTWRITEBYTECODE='1')
    proc = subprocess.run([sys.executable, '-B', str(ROOT / script), *map(str, args)],
                          cwd=ROOT, env=env, capture_output=True, text=True)
    # Bench exit 1 can mean genuine misses/false alarms, so keep its observations.
    if proc.returncode not in (0, 1):
        raise RuntimeError(f'{script}: {proc.stderr[-1000:]}')
    return proc.returncode


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--seeded', type=Path, help='reuse seeded results.json')
    ap.add_argument('--typical', type=Path, help='reuse typical --json output')
    ap.add_argument('--replay', type=Path, help='reuse KiCad replay results.json')
    ap.add_argument('--output', type=Path, default=HERE / 'RESULTS.md')
    ap.add_argument('--work', type=Path, default=Path('/tmp/codex-work/sr-detection'))
    args = ap.parse_args(argv)
    args.work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.work, prefix='run-') as tmp:
        work = Path(tmp)
        seeded = args.seeded or work / 'seeded/results.json'
        typical = args.typical or work / 'typical.json'
        replay = args.replay or work / 'replay/results.json'
        if not args.seeded:
            execute('evals/seeded_bench/run.py', ['--offline', '--out', seeded.parent], work)
        if not args.typical:
            execute('evals/typical_circuits/run.py', ['--json', typical], work)
        if not args.replay:
            execute('evals/kicad_replay_bench/run.py', ['--out', replay.parent], work)
        library = ROOT / 'references/shared/guideline-criteria.json'
        criteria = {c['id']: c for c in read(library)['criteria']}
        known = read(KNOWN)
        validate_known(known, criteria, [r.id for r in catalog.RULES])
        rows = seeded_rows(read(seeded), catalog.BASIS) + typical_rows(read(typical), catalog.BASIS) + known_rows(known)
        table, unmapped = aggregate(criteria, catalog.BASIS, rows)
        inputs = [('seeded results.json', seeded), ('typical results.json', typical), ('KiCad replay results.json', replay),
                  ('known_defects.json', KNOWN), ('catalog.py', ROOT / 'scripts/catalog.py'),
                  ('guideline-criteria.json', library), ('seeded corpus.json', ROOT / 'evals/seeded_bench/corpus.json'),
                  ('typical cases.json', ROOT / 'evals/typical_circuits/cases.json'),
                  ('improvement-ledger.md', ROOT / 'docs/improvement-ledger.md')]
        inputs += [(str(p.relative_to(ROOT)), p) for p in sorted((ROOT / 'docs/audits').glob('*.md'))]
        provenance = [(name, hashlib.sha256(path.read_bytes()).hexdigest()) for name, path in inputs]
        replay_data = read(replay)
        imported = read(ROOT / 'evals/input_bench/validation-2026-10-07.json')['import_after']
        auxiliary = [f"- KiCad 原生回放（本次/所给结果，约定 {replay_data['contract_revision']}）：{replay_data['totals']}。"
                     '字段一致性没有缺陷真值，不计入 H/M/FP。',
                     f"- input_bench：只读取 2026-10-07 历史记录 {imported['passed']}/{imported['total']}，未重新运行；"
                     '缺原作者输入，不把导入拒绝计作电气检出。',
                     '- consistency_bench：没有随仓库保存的评分结果，且只度量一致性，不判对错；未计分。',
                     '- mutation：代码测试门，不是设计缺陷检出，排除。规则合同是合成触发板，亦排除。']
        args.output.write_text(render(criteria, table, rows, unmapped, provenance, auxiliary), encoding='utf-8')
        print(args.output)
        return int(any(r['status'] in ('error', 'unclassified') for r in rows) or bool(replay_data['totals'].get('MISMATCH')))


if __name__ == '__main__':
    sys.exit(main())

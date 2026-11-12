#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""知识必答清单：每块电路对上知识包里的典型电路实现方案，方案的必算项和已知坑逐项要有审查结论。

  python3 knowledge_checklist.py find <关键词 ...>                               在典型电路里按文件名、标题、功能、方案名检索
  python3 knowledge_checklist.py build review-plan.json knowledge-checklist.json  按计划里的电路重写清单，保留已写的内容
  python3 knowledge_checklist.py check review-plan.json knowledge-checklist.json

清单是审查员在“判断”一步写的文件，放在 review-results.json 旁边：
  circuits  计划里每块电路（plan.owners）一条：`typical` 写 `<典型电路文件名>#<实现方案名>`，知识包里没有对应的写 `none` 并在 `reason` 写查过什么
  items     由 build 从所写方案里抽出，不手抄：该方案的每条必算项、每条已知坑。每项写 `disposition`：
            `checked`（`where` 列出核过它的检查项或功能的编号，必须是计划里的）或 `not_applicable`（`reason` 写理由）
必算项和已知坑只是该查什么的清单，不是判据：发现仍落到具体准则和证据上，不因没用某种典型电路判缺陷。
validate_review.py 和 pack_review.py 核对清单：电路都对上了、每项有处置、编号存在。
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

KNOWLEDGE = Path(__file__).resolve().parents[1] / 'references' / 'knowledge'
FILE = 'knowledge-checklist.json'
SCHEMA_VERSION = 1
KINDS = ('必算项', '已知坑')
NONE = 'none'
LINK = re.compile(r'\[([^\]]*)\]\([^)]*\)')


def text(value):
    return isinstance(value, str) and bool(value.strip())


def clean(line):
    return LINK.sub(r'\1', line).strip()


def implementations(body):
    """{implementation name: [(kind, item text)]} of one typical circuit: the bullets under 必算项 and 已知坑 of every
    「### 」 heading of its 「## 实现方案」 section."""
    out, current, kind, inside = {}, None, None, False
    for line in body.splitlines():
        if line.startswith('## '):
            inside, current = line.strip() == '## 实现方案', None
        elif not inside:
            continue
        elif line.startswith('### '):
            current, kind = out.setdefault(line[4:].strip(), []), None
        elif current is not None and line.startswith('- **'):
            kind = next((k for k in KINDS if line.startswith('- **%s**' % k)), None)
            rest = line.partition('：')[2].strip()
            if kind and rest and not rest.startswith('无'):      # the item written on the bullet's own line
                current.append((kind, clean(rest)))
        elif current is not None and kind and line.startswith('  - '):
            current.append((kind, clean(line[4:])))
    return out


def circuit_file(stem):
    hits = sorted((KNOWLEDGE / '典型电路').rglob(stem + '.md'))
    return hits[0] if len(hits) == 1 else None


def scheme_rows(circuit, typical):
    """Checklist rows of one circuit's declared scheme; None when the knowledge package has no such scheme."""
    stem, _, name = typical.partition('#')
    md = circuit_file(stem) if text(stem) and '/' not in stem else None
    pairs = implementations(md.read_text(encoding='utf-8')).get(name) if md else None
    if pairs is None:
        return None
    rows, seen = [], {}
    for kind, words in pairs:
        digest = hashlib.sha256(('%s\n%s' % (kind, words)).encode('utf-8')).hexdigest()[:10]
        seen[digest] = seen.get(digest, 0) + 1
        rows.append({'circuit': circuit, 'entry': md.relative_to(KNOWLEDGE).as_posix(), 'scheme': name, 'kind': kind,
                     'id': digest if seen[digest] == 1 else '%s-%d' % (digest, seen[digest]), 'text': words})
    return rows


def key(row):
    return tuple(row.get(k) for k in ('circuit', 'entry', 'scheme', 'kind', 'id'))


def plan_circuits(plan):
    return [o['id'] for o in (plan or {}).get('owners') or [] if isinstance(o, dict) and o.get('kind') == 'CIRCUIT' and text(o.get('id'))]


def plan_ids(plan):
    return {r.get('id') for name in ('checks', 'functions') for r in (plan or {}).get(name) or [] if isinstance(r, dict)}


def problems(plan, data):
    """What keeps the checklist from being answered; empty when the plan has no circuits or everything is answered."""
    circuits = plan_circuits(plan)
    if not circuits:
        return []
    if not isinstance(data, dict) or data.get('schema_version') != SCHEMA_VERSION:
        return ['%s 缺失或不是 schema_version %d：计划里有 %d 块电路，每块要对上典型电路的实现方案（knowledge_checklist.py build）'
                % (FILE, SCHEMA_VERSION, len(circuits))]
    declared = {c.get('circuit'): c for c in data.get('circuits') or [] if isinstance(c, dict)}
    written = {key(r): r for r in data.get('items') or [] if isinstance(r, dict)}
    known, found, missing = plan_ids(plan), [], 0
    for cid in circuits:
        typical = (declared.get(cid) or {}).get('typical')
        if not text(typical):
            found.append('必答清单 电路 %s：typical 写 <典型电路文件名>#<实现方案名>，知识包里没有对应的写 none' % cid)
            continue
        if typical == NONE:
            if not text(declared[cid].get('reason')):
                found.append('必答清单 电路 %s：typical 为 none 时在 reason 写查过哪些典型电路、为什么都不对应' % cid)
            continue
        rows = scheme_rows(cid, typical)
        if rows is None:
            found.append('必答清单 电路 %s：%s 在知识包的典型电路里找不到（knowledge_checklist.py find 检索）' % (cid, typical))
            continue
        for row in rows:
            answer = written.get(key(row))
            name = '电路 %s %s 的%s“%s”' % (cid, typical, row['kind'], row['text'] if len(row['text']) <= 40 else row['text'][:40] + '…')
            if answer is None:
                missing += 1
            elif answer.get('disposition') == 'not_applicable':
                if not text(answer.get('reason')):
                    found.append('必答清单 %s：不适用要在 reason 写理由' % name)
            elif answer.get('disposition') == 'checked':
                where = answer.get('where')
                if not (isinstance(where, list) and where and all(text(w) for w in where)):
                    found.append('必答清单 %s：checked 要在 where 列出核过它的检查项或功能编号' % name)
                elif [w for w in where if w not in known]:
                    found.append('必答清单 %s：where 的 %s 不是计划里的检查项或功能编号' % (name, '、'.join(w for w in where if w not in known)))
            else:
                found.append('必答清单 %s：还没有写处置（disposition 写 checked 或 not_applicable）' % name)
    if missing:
        found.append('%s 缺 %d 项（方案改了或知识条目变了）：重跑 knowledge_checklist.py build 后补写处置' % (FILE, missing))
    return found


def build(plan, old):
    """The checklist for this plan: one declaration per circuit and the items of every declared scheme; what was written stays."""
    old = old if isinstance(old, dict) else {}
    declared = {c.get('circuit'): c for c in old.get('circuits') or [] if isinstance(c, dict)}
    written = {key(r): r for r in old.get('items') or [] if isinstance(r, dict)}
    circuits, items = [], []
    for cid in plan_circuits(plan):
        row = declared.get(cid) or {}
        circuits.append({'circuit': cid, 'typical': row.get('typical', ''), 'reason': row.get('reason', '')})
        if text(row.get('typical')) and row['typical'] != NONE:
            for item in scheme_rows(cid, row['typical']) or []:
                answer = written.get(key(item), {})
                items.append(dict(item, disposition=answer.get('disposition', ''), where=answer.get('where', []),
                                  reason=answer.get('reason', '')))
    return {'schema_version': SCHEMA_VERSION, 'circuits': circuits, 'items': items}


def search(terms):
    hits = []
    for md in sorted((KNOWLEDGE / '典型电路').rglob('*.md')):
        if md.name == 'README.md':
            continue
        body = md.read_text(encoding='utf-8')
        head = ' '.join(l for l in body.splitlines() if l.startswith('# ') or l.startswith('功能：'))
        names = list(implementations(body))
        if all(t.lower() in (md.stem + ' ' + head + ' ' + ' '.join(names)).lower() for t in terms):
            hits.append((md.stem, names))
    return hits


def load(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('command', choices=('find', 'build', 'check'))
    ap.add_argument('args', nargs='+')
    args = ap.parse_args(argv)
    if args.command == 'find':
        for stem, names in search(args.args):
            print('\n'.join(['%s#%s' % (stem, n) for n in names] or [stem + '（只有指路，没有实现方案）']))
        return 0
    if len(args.args) != 2:
        ap.error('%s 要 review-plan.json 和 knowledge-checklist.json 两个路径' % args.command)
    plan, path = load(args.args[0]), Path(args.args[1])
    if not isinstance(plan, dict):
        print('读不出计划：%s' % args.args[0])
        return 1
    if args.command == 'build':
        data = build(plan, load(path))
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('电路 %d 块，其中 %d 块还没有写 typical；清单 %d 项' % (
            len(data['circuits']), sum(not text(c['typical']) for c in data['circuits']), len(data['items'])))
    found = problems(plan, load(path))
    print('\n'.join(found + ['FAIL' if found else 'PASS']))
    return 1 if found else 0


if __name__ == '__main__':
    sys.exit(main())

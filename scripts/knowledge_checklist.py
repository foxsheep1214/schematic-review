#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""知识必答清单：每块电路对上知识框架里的典型电路实现方案，方案的必算项和已知坑逐项要有审查结论。

  python3 knowledge_checklist.py find <关键词 ...>                               在典型电路里按文件名、标题、功能、方案名检索
  python3 knowledge_checklist.py build review-plan.json knowledge-checklist.json  按计划里的电路重写清单，保留已写的内容
  python3 knowledge_checklist.py check review-plan.json knowledge-checklist.json
  python3 knowledge_checklist.py entries review-plan.json | <电路类型或器件类别名称 ...>
                                                                              按条目头部的词表声明列出相关条目，按组件分组

清单是审查员在“判断”一步写的文件，放在 review-results.json 旁边：
  circuits  计划里每块电路（plan.owners）一条：`typical` 写 `<典型电路文件名>#<实现方案名>`，知识框架里没有对应的写 `none` 并在 `reason` 写查过什么
  items     由 build 从所写方案里抽出，不手抄：该方案的每条必算项、每条已知坑。每项写 `disposition`：
            `checked`（`where` 列出核过它的检查项或功能的编号，必须是计划里的）或 `not_applicable`（`reason` 写理由）
  entries   查阅记录（可选）：`entry` 写相对 知识/ 的条目路径，`disposition` 写 `read`（读过）或 `not_applicable`（`reason` 写理由）
  issues    对知识框架的反馈（可选）：审查中发现框架缺什么、哪个条目有问题，当场记一条。`component` 写框架的组件，
            `target` 写条目路径、准则编号或要查而没有的内容，`kind` 写 缺/错/不够/歧义/过严，`detail` 写问题是什么，
            `evidence` 写依据（手册页或本板上的实例）。它和 typical 为 none 的电路一起列在报告的“对知识框架的反馈”，
            打包时写成 record/knowledge-gaps.json，由框架的 工具/collect_feedback.py 归集；不影响审查结论
必算项和已知坑只是该查什么的清单，不是判据：发现仍落到具体准则和证据上，不因没用某种典型电路判缺陷。
validate_review.py 和 pack_review.py 核对清单：电路都对上了、每项有处置、编号存在。
build、check 和 validate_review.py 另给提示（不判失败）：本板有的电路类型、器件类别（计划 knowledge_scope 段记的），
知识框架里声明了它的条目既不是所写的典型电路、也不在 entries 里的，逐条列出，提示查阅或写明不适用。
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import knowledge_source

FILE = 'knowledge-checklist.json'
SCHEMA_VERSION = 1
KINDS = ('必算项', '已知坑')
NONE = 'none'
GAPS_FILE = 'knowledge-gaps.json'
ISSUE_KINDS = ('缺', '错', '不够', '歧义', '过严')
ISSUE_FIELDS = ('component', 'target', 'kind', 'detail', 'evidence')
FEEDBACK_COMPONENTS = knowledge_source.COMPONENTS + ('设计准则',)
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
    hits = sorted((knowledge_source.knowledge_dir() / '典型电路').rglob(stem + '.md'))
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
        rows.append({'circuit': circuit, 'entry': md.relative_to(knowledge_source.knowledge_dir()).as_posix(), 'scheme': name, 'kind': kind,
                     'id': digest if seen[digest] == 1 else '%s-%d' % (digest, seen[digest]), 'text': words})
    return rows


def key(row):
    return tuple(row.get(k) for k in ('circuit', 'entry', 'scheme', 'kind', 'id'))


def plan_circuits(plan):
    return [o['id'] for o in (plan or {}).get('owners') or [] if isinstance(o, dict) and o.get('kind') == 'CIRCUIT' and text(o.get('id'))]


def plan_ids(plan):
    return {r.get('id') for name in ('checks', 'functions') for r in (plan or {}).get(name) or [] if isinstance(r, dict)}


def issue_problems(data):
    """Problems of the `issues` rows: each names a framework component, what it is about, the kind, the problem and the evidence."""
    rows = data.get('issues') if isinstance(data, dict) else None
    if rows is None:
        return []
    if not isinstance(rows, list):
        return ['必答清单 issues 是数组：每项写 %s' % '、'.join(ISSUE_FIELDS)]
    found = []
    for index, row in enumerate(rows):
        label = '必答清单 issues[%d]' % index
        if not isinstance(row, dict) or [f for f in ISSUE_FIELDS if not text(row.get(f))]:
            found.append('%s：%s 都要写' % (label, '、'.join(ISSUE_FIELDS)))
        elif row['component'] not in FEEDBACK_COMPONENTS:
            found.append('%s：component 写知识框架的组件（%s）' % (label, '、'.join(FEEDBACK_COMPONENTS)))
        elif row['kind'] not in ISSUE_KINDS:
            found.append('%s：kind 写 %s 之一' % (label, '、'.join(ISSUE_KINDS)))
    return found


def gaps(data):
    """What this review feeds back to the knowledge framework, in the shape of ASG's knowledge-gaps.json: the circuits no
    typical circuit matches and the reviewer's `issues`."""
    data = data if isinstance(data, dict) else {}
    rows = [{'signal': 'no_typical_circuit', 'component': '典型电路', 'item': str(c.get('circuit')),
             'detail': str(c.get('reason') or ''), 'source': FILE}
            for c in data.get('circuits') or [] if isinstance(c, dict) and c.get('typical') == NONE]
    if not issue_problems(data):
        rows += [{'signal': 'knowledge_missing' if r['kind'] == '缺' else 'knowledge_issue', 'component': r['component'],
                  'item': r['target'], 'detail': '%s：%s（依据：%s）' % (r['kind'], r['detail'], r['evidence']), 'source': FILE}
                 for r in data.get('issues') or []]
    counts = {}
    for row in rows:
        counts[row['signal']] = counts.get(row['signal'], 0) + 1
    return {'schema_version': SCHEMA_VERSION, 'counts': counts, 'gaps': rows}


SECTION = '## 对知识框架的反馈（设计者不用处理）'
GAP_LABELS = {'no_typical_circuit': '典型电路没有对应方案', 'knowledge_missing': '知识框架查不到', 'knowledge_issue': '知识条目有问题'}


def render_gaps(data):
    """The report section 对知识框架的反馈; empty when the review has nothing to feed back."""
    rows = gaps(data)['gaps']
    if not rows:
        return []
    cell = lambda value: str(value).replace('|', '／').replace('\n', ' ')
    return ([SECTION, '',
             '审查中发现知识框架缺的内容和有问题的条目，共 %d 条，不影响审查结论；由知识框架的 `工具/collect_feedback.py` 归集后补进框架。'
             % len(rows), '', '| 组件 | 类别 | 对象 | 说明 |', '|---|---|---|---|']
            + ['| %s | %s | %s | %s |' % (r['component'], GAP_LABELS[r['signal']], cell(r['item']), cell(r['detail'])) for r in rows] + [''])


def problems(plan, data):
    """What keeps the checklist from being answered; empty when the plan has no circuits or everything is answered."""
    circuits = plan_circuits(plan)
    if not circuits:
        return issue_problems(data)
    if not isinstance(data, dict) or data.get('schema_version') != SCHEMA_VERSION:
        return ['%s 缺失或不是 schema_version %d：计划里有 %d 块电路，每块要对上典型电路的实现方案（knowledge_checklist.py build）'
                % (FILE, SCHEMA_VERSION, len(circuits))]
    declared = {c.get('circuit'): c for c in data.get('circuits') or [] if isinstance(c, dict)}
    written = {key(r): r for r in data.get('items') or [] if isinstance(r, dict)}
    known, found, missing = plan_ids(plan), issue_problems(data), 0
    for cid in circuits:
        typical = (declared.get(cid) or {}).get('typical')
        if not text(typical):
            found.append('必答清单 电路 %s：typical 写 <典型电路文件名>#<实现方案名>，知识框架里没有对应的写 none' % cid)
            continue
        if typical == NONE:
            if not text(declared[cid].get('reason')):
                found.append('必答清单 电路 %s：typical 为 none 时在 reason 写查过哪些典型电路、为什么都不对应' % cid)
            continue
        rows = scheme_rows(cid, typical)
        if rows is None:
            found.append('必答清单 电路 %s：%s 在知识框架的典型电路里找不到（knowledge_checklist.py find 检索）' % (cid, typical))
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
    built = {'schema_version': SCHEMA_VERSION, 'circuits': circuits, 'items': items, 'entries': old.get('entries') or []}
    return dict(built, issues=old['issues']) if old.get('issues') else built


def board_scope(plan):
    """(电路类型, 器件类别)：计划 knowledge_scope 段记的本板范围（旧计划没有它时取 guidelines 段的）；
    两段都没有时电路类型取检查项上的，器件类别为空。"""
    section = next((plan[k] for k in ('knowledge_scope', 'guidelines') if isinstance((plan or {}).get(k), dict)), None)
    if section is not None:
        return list(section.get('circuit_types') or []), list(section.get('device_kinds') or [])
    return sorted({c['circuit_type'] for c in (plan or {}).get('checks') or []
                   if isinstance(c, dict) and text(c.get('circuit_type'))}), []


def entries_by_component(circuit_types=(), device_kinds=()):
    """{组件: [(相对 知识/ 的条目路径, [命中的名称…])]}：头部声明了这些电路类型或器件类别中任一个的条目。"""
    grouped = {}
    for path, names in knowledge_source.entries_for(circuit_types, device_kinds).items():
        grouped.setdefault(path.split('/', 1)[0], []).append((path, names))
    return {name: grouped[name] for name in knowledge_source.COMPONENTS if name in grouped}


def consulted(data):
    """查阅记录里的条目：各电路所写典型电路的文件，和 entries 里读过或写明不适用的条目。"""
    data = data if isinstance(data, dict) else {}
    seen = set()
    for row in data.get('circuits') or []:
        stem = str((row or {}).get('typical') or '').partition('#')[0] if isinstance(row, dict) else ''
        md = circuit_file(stem) if text(stem) and stem != NONE and '/' not in stem else None
        if md:
            seen.add(md.relative_to(knowledge_source.knowledge_dir()).as_posix())
    for row in data.get('entries') or []:
        if isinstance(row, dict) and text(row.get('entry')) and (
                row.get('disposition') == 'read' or (row.get('disposition') == 'not_applicable' and text(row.get('reason')))):
            seen.add(row['entry'])
    return seen


def hints(plan, data):
    """提示（不判失败）：本板有的电路类型、器件类别，框架里声明了它的条目却不在查阅记录里的，每条一句。"""
    circuits, kinds = board_scope(plan)
    seen = consulted(data)
    return ['%s 声明了本板的 %s，查阅记录里没有：查阅后在 %s 的 entries 记 read，或记 not_applicable 写明理由'
            % (path, '、'.join(names), FILE)
            for rows in entries_by_component(circuits, kinds).values() for path, names in rows if path not in seen]


def search(terms):
    hits = []
    for md in sorted((knowledge_source.knowledge_dir() / '典型电路').rglob('*.md')):
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
    ap.add_argument('command', choices=('find', 'build', 'check', 'entries'))
    ap.add_argument('args', nargs='+')
    args = ap.parse_args(argv)
    if args.command == 'find':
        for stem, names in search(args.args):
            print('\n'.join(['%s#%s' % (stem, n) for n in names] or [stem + '（只有指路，没有实现方案）']))
        return 0
    if args.command == 'entries':
        if len(args.args) == 1 and args.args[0].endswith('.json'):
            plan = load(args.args[0])
            if not isinstance(plan, dict):
                print('读不出计划：%s' % args.args[0])
                return 1
            circuits, kinds = board_scope(plan)
        else:
            vocab = knowledge_source.vocabulary()
            unknown = [n for n in args.args if n not in vocab['circuit_types'] and n not in vocab['device_kinds']]
            if unknown:
                print('不在知识框架词表里：%s' % '、'.join(unknown))
                return 1
            circuits = [n for n in args.args if n in vocab['circuit_types']]
            kinds = [n for n in args.args if n in vocab['device_kinds']]
        grouped = entries_by_component(circuits, kinds)
        for component, rows in grouped.items():
            print(component)
            print('\n'.join('  %s  %s' % (path, '、'.join(names)) for path, names in rows))
        if not grouped:
            print('知识框架里没有条目声明 %s' % '、'.join(circuits + kinds or ['（本板没有电路类型和器件类别）']))
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
    found, notices = problems(plan, load(path)), hints(plan, load(path))
    if notices:   # 提示，不判失败
        print('提示:\n  - ' + '\n  - '.join(notices))
    print('\n'.join(found + ['FAIL' if found else 'PASS']))
    return 1 if found else 0


if __name__ == '__main__':
    sys.exit(main())

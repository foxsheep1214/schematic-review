#!/usr/bin/env python3
"""Render the one human-facing review report from the validated ledger.

Structure and numbers come only from review-plan / review-results / review-gate, so every
agent produces the same report for the same records. The agent adds plain-language text
through an optional notes file; it cannot change verdicts or counts here.

notes.json (optional):
  {"summary": "1-3 sentences for a hardware engineer",
   "items": {"<work item or finding id>": "one or two plain sentences"},
   "highlights": ["at most 8 short lines on what was actually verified"]}
"""
import argparse
import json
import sys
from collections import Counter, OrderedDict
from pathlib import Path

RELEASE = {'GO': '可以定稿', 'CONDITIONAL_GO': '可以有条件定稿', 'NO_GO': '还不能定稿'}
CAUSES = OrderedDict([('EXTERNAL_DATA', '缺资料'), ('DESIGN_OPEN', '设计没定'),
                      ('REQUIREMENT_OPEN', '需求没定'), ('REVIEW_INCOMPLETE', '审查没做完'),
                      ('USER_DEFERRED', '已暂缓')])
KINDS = OrderedDict([('FAIL', '电路错误'), ('REQUIREMENT_OPEN', '需求没定'), ('DESIGN_OPEN', '设计没定'),
                     ('EXTERNAL_DATA', '缺资料'), ('REVIEW_INCOMPLETE', '审查没做完'),
                     ('USER_DEFERRED', '已暂缓')])
SEVERITIES = ('P0', 'P1', 'P2', 'P3')
SEVERITY_WORDS = {'P0': '可能损坏器件或危及安全', 'P1': '必需功能可能不达标',
                  'P2': '局部或次要问题', 'P3': '可选优化'}
SEVERITY_LEGEND = '严重程度：P0 可能损坏器件或危及安全；P1 必需功能可能不达标；P2 局部或次要问题；P3 可选优化。'
HISTORY_RULE = 'REQ-H02'
RESULT_WORDS = (('PASS', '通过（PASS）'), ('FAIL', '发现错误（FAIL）'), ('INSUFFICIENT', '资料不足无法判断（INSUFFICIENT）'),
                ('NA', '与本产品无关（NA）'), ('NA_OUTSIDE_STAGE', '原理图阶段不判、交给后续环节'))
# Why the schematic cannot be finalised yet, in the order a reader should act on them.
BLOCKERS = (('fail', '%d 条检查发现的电路错误还没改'),
            ('gap', '%d 条检查缺资料或设计依据，对应下面列出的待办'),
            ('review', '%d 条检查审查人还没做完'),
            ('other', '%d 项其他定稿条件没满足'))


def cell(text):
    return str(text).replace('|', '\\|').replace('\n', ' ').strip()


def worst(levels):
    found = [s for s in SEVERITIES if s in levels]
    return found[0] if found else None


def blocker_counts(blockers):
    kinds = Counter()
    for b in blockers:
        if 'review work not completed' in b:
            kinds['review'] += 1
        elif 'P0 requires verified repair' in b or 'unresolved blocking FAIL' in b:
            kinds['fail'] += 1
        elif 'unresolved blocking INSUFFICIENT' in b:
            kinds['gap'] += 1
        else:
            kinds['other'] += 1
    return [text % kinds[key] for key, text in BLOCKERS if kinds[key]]


def item_kind(rows):
    kinds = {r.get('review_result') if r.get('review_result') == 'FAIL' else r.get('gap_cause') for r in rows}
    for key, label in KINDS.items():
        if key in kinds:
            return label
    return '待处理'


def unique(values):
    seen = []
    for v in values:
        if isinstance(v, str) and v.strip() and v.strip() not in seen:
            seen.append(v.strip())
    return seen


def task_level(task, checks):
    rows = [checks[c] for c in task.get('check_ids') or [] if c in checks]
    return worst({r.get('severity') or r.get('potential_severity') for r in rows})


def render_item(task, checks, notes):
    rows = [checks[c] for c in task.get('check_ids') or [] if c in checks]
    level = task_level(task, checks)
    head = '### %s　%s' % (task['id'], task.get('title') or task.get('root_cause') or '')
    meta = '类型：%s　可能后果：%s　涉及 %d 条检查' % (
        item_kind(rows), ('%s（%s）' % (SEVERITY_WORDS[level], level)) if level else '未定级', len(rows))
    lines = [head, '', meta, '']
    if notes.get(task['id']):
        lines += [notes[task['id']], '']
    requests = [req for r in rows for req in (r.get('input_requests') or {}).values() if isinstance(req, dict)]
    fields = [('缺什么', [task.get('root_cause')]),
              ('为什么要紧', [task.get('reason')]),
              ('需要提供的内容', [q.get('required_scope') for q in requests]),
              ('找谁、怎么拿', [q.get('acquisition') for q in requests] or [task.get('next_action')]),
              ('做到什么算解决', [q.get('closure_criterion') for q in requests])]
    option = task.get('design_option') or {}
    if option.get('status') == 'PROPOSED':
        fields.append(('建议的电路改法', [option.get('summary')]))
    for label, values in fields:
        values = unique(values)
        if values:
            lines.append('- **%s**：%s' % (label, '；'.join(values)))
    lines.append('')
    return lines


def render(plan, results, gate, notes=None, title=None):
    notes = notes or {}
    item_notes = notes.get('items') or {}
    checks = {c['id']: c for c in results.get('checks') or [] if isinstance(c, dict) and 'id' in c}
    current_rows = {k: c for k, c in checks.items() if k.split('.', 1)[0] != HISTORY_RULE}
    flow = gate.get('workflow') or {}
    tasks = flow.get('work_items') or []
    findings = results.get('findings') or []
    summary = gate.get('categorized_summary') or {}
    counts = (summary.get('current') or {}).get('results') or {}
    phase = flow.get('phase') or plan.get('review_phase') or 'schematic_freeze'
    release = gate.get('release', 'NO_GO')
    handoffs = [c for c in current_rows.values() if (c.get('handoff') or {}).get('required')]
    by_sev = (gate.get('summary') or {}).get('by_severity') or {}
    defects = sum(by_sev.get(s, 0) for s in SEVERITIES)

    out = ['# %s' % (title or '原理图审查报告'), '']
    if not gate.get('valid'):
        out += ['> **审查记录本身有错，这份报告的结论不可用。** 先改正记录再重新出报告：' +
                '；'.join(cell(e) for e in (gate.get('errors') or [])[:5]), '']
    out += ['## 结论', '']
    total = (summary.get('current') or {}).get('checks', len(current_rows))
    out.append('- **检查结果**：共 %d 条。%s。' % (total, '，'.join('%s %d 条' % (label, counts.get(key, 0))
               for key, label in RESULT_WORDS)))
    if defects:
        out.append('- **发现的电路错误**：%d 处（%s），见“电路错误”一节。' % (
            defects, '、'.join('%s %d 处' % (s, by_sev[s]) for s in SEVERITIES if by_sev.get(s))))
    else:
        out.append('- **发现的电路错误**：0 处。')
    reasons = blocker_counts(gate.get('blockers') or []) if release != 'GO' else []
    if reasons:
        out.append('- **能否定稿**：%s。还差：' % RELEASE.get(release, release))
        out += ['  %d. %s；' % (i, r) for i, r in enumerate(reasons, 1)]
        out[-1] = out[-1][:-1] + '。'
    else:
        out.append('- **能否定稿**：%s。' % RELEASE.get(release, release))
    if tasks:
        out.append('- **待办**：%d 件，按可能后果从重到轻列在“待办”一节。' % len(tasks))
    if phase == 'design_iteration':
        out.append('- 这次是设计过程中的检查，不是定稿审查；“能否定稿”只说明离定稿还差什么。')
    out.append('')
    if notes.get('summary'):
        out += [notes['summary'], '']

    if findings:
        out += ['## 电路错误', '', SEVERITY_LEGEND, '']
        for f in sorted(findings, key=lambda f: SEVERITIES.index(f['severity']) if f.get('severity') in SEVERITIES else 9):
            fix = f.get('remediation') or {}
            level = f.get('severity')
            out.append('### %s　%s（%s：%s）' % (f.get('id'), f.get('title') or '', level, SEVERITY_WORDS.get(level, '')))
            out.append('')
            if item_notes.get(f.get('id')):
                out += [item_notes[f['id']], '']
            where = f.get('location') or {}
            for label, value in (('位置', '、'.join(('第%s页' % x) for x in where.get('pages') or []) +
                                  ('　' + '、'.join(where.get('refs') or []) if where.get('refs') else '')),
                                 ('问题', f.get('observed')), ('后果', f.get('impact')),
                                 ('怎么改', f.get('recommendation')), ('改的目的', fix.get('purpose')),
                                 ('改完怎么验证', f.get('verification')),
                                 ('涉及的检查', '、'.join(f.get('check_ids') or []))):
                if value:
                    out.append('- **%s**：%s' % (label, value))
            for step in fix.get('steps') or []:
                out.append('- **改动**：%s：%s → %s' % (step.get('target', ''), step.get('before', ''), step.get('after', '')))
            out.append('')

    if tasks:
        out += ['## 待办', '']
        if not findings:
            out += [SEVERITY_LEGEND, '']
        rank = lambda t: (SEVERITIES.index(task_level(t, checks)) if task_level(t, checks) else len(SEVERITIES),
                          -len(t.get('check_ids') or []))
        for task in sorted(tasks, key=rank):
            out += render_item(task, checks, item_notes)

    if handoffs:
        out += ['## 交给后续环节的要求', '',
                '下面这些要求在原理图上做不了，要在 PCB、热设计、测试等后续环节落实，不算原理图的错误，'
                '也不影响原理图定稿。原理图交出时把这张表一起交给对应负责方即可。', '',
                '| 负责方 | 条数 | 要落实的要求 | 怎么验证 |', '|---|---:|---|---|']
        groups = OrderedDict()
        for c in handoffs:
            h = c['handoff']
            groups.setdefault('、'.join(h.get('receivers') or ['未指定']), []).append(h)
        for who, hs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            out.append('| %s | %d | %s | %s |' % (cell(who), len(hs),
                       cell('；'.join(unique(h.get('constraint') for h in hs))),
                       cell('；'.join(unique(h.get('verification') for h in hs)))))
        pending = (gate.get('stage_scope') or {}).get('requirements_pending_downstream') or []
        if pending:
            out += ['', '另有 %d 条需求要等样机或测试结果才能最终确认：%s。' % (len(pending), '、'.join(pending))]
        out.append('')

    if notes.get('highlights'):
        out += ['## 已核对的重点', ''] + ['- ' + h for h in notes['highlights'][:8]] + ['']

    tool_gaps = gate.get('sr_improvements') or []
    if tool_gaps:
        out += ['## 审查工具的不足（设计者不用处理）', '',
                '下面 %d 条检查，SR 的自动工具判断不了，审查人已经人工核对，结论按人工结果算。'
                '这里记录 SR 为什么做不到、该怎么改进 SR，留给 SR 维护。' % len(tool_gaps), '']
        for t in tool_gaps:
            out += ['### ' + t['check_id'], '',
                    '- **SR 为什么做不到**：' + cell(t.get('tool_limitation') or ''),
                    '- **建议怎么改进 SR**：' + cell(t.get('sr_improvement') or ''),
                    '- **这次人工怎么核对的**：' + cell(t.get('method') or ''), '']

    gaps = [c for c in current_rows.values() if c.get('review_result') == 'INSUFFICIENT']
    pot = Counter(c.get('potential_severity') for c in gaps)
    cause = Counter(c.get('gap_cause') for c in gaps)
    history = (summary.get('history') or {}).get('checks', 0)
    out += ['## 数字一览', '', '| 项目 | 数量 |', '|---|---|',
            '| 检查总数 | %d |' % (summary.get('current') or {}).get('checks', len(current_rows)),
            '| 通过 / 发现错误 / 资料不足无法判断 | %d / %d / %d |' % (counts.get('PASS', 0), counts.get('FAIL', 0), counts.get('INSUFFICIENT', 0)),
            '| 与本产品无关（NA） | %d |' % counts.get('NA', 0),
            '| 原理图阶段不判、交给后续环节 | %d |' % counts.get('NA_OUTSIDE_STAGE', 0),
            '| 电路错误，按严重程度 P0 / P1 / P2 / P3 | %s |' % ' / '.join(str(by_sev.get(s, 0)) for s in SEVERITIES),
            '| 资料不足的检查，可能的严重程度 P0 / P1 / P2 / P3 | %s |' % ' / '.join(str(pot.get(s, 0)) for s in SEVERITIES),
            '| 资料不足的原因：%s | %s |' % (' / '.join(CAUSES.values()), ' / '.join(str(cause.get(k, 0)) for k in CAUSES)),
            '| 交给后续环节的要求 | %d |' % len(handoffs),
            '| 上一版问题的处理记录（不计入上面各行） | %d |' % history, '',
            '“条”是检查条数，待办“件”按同一原因合并，两者不能相加。', '']
    out += ['## 详细记录', '',
            '每条检查的结论、依据和计算都在 `record/` 里：`review-results.json` 是逐条结论，`review-gate.json` 是校验结果和计数，'
            '`review-plan.json` 是检查清单，`manifest.json` 记录用到的原理图、手册、需求的位置和校验码，'
            '`evidence/` 是结论引用的计算和截图。', '']
    return '\n'.join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('plan')
    parser.add_argument('results')
    parser.add_argument('gate')
    parser.add_argument('--notes')
    parser.add_argument('--title')
    parser.add_argument('-o', '--out', required=True)
    args = parser.parse_args(argv)
    load = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
    text = render(load(args.plan), load(args.results), load(args.gate),
                  load(args.notes) if args.notes else None, args.title)
    Path(args.out).write_text(text, encoding='utf-8')
    print('wrote', args.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())

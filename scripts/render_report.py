#!/usr/bin/env python3
"""Render the one human-facing review report from the validated ledger.

Structure and numbers come only from review-plan / review-results / review-gate, so every
agent produces the same report for the same records. The agent adds plain-language text
through an optional notes file; it cannot change verdicts or counts here.

notes.json (optional):
  {"summary": "1-3 sentences for a hardware engineer",
   "items": {"<work item or finding id>": "one or two plain sentences"},
   "highlights": ["at most 8 short lines on what was actually verified"],
   "sr_feedback": [{"kind": "false_alarm|over_strict|missed|unclear", "rules": ["PRO-C02"],
                    "instance": "what happened on this board", "suggestion": "how SR should change"}]}
"""
import argparse
import json
import re
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
RESULT_WORDS = (('PASS', '通过（PASS）'), ('FAIL', '没通过（FAIL）'), ('INSUFFICIENT', '资料不足无法判断（INSUFFICIENT）'),
                ('NA', '与本产品无关（NA）'), ('NA_OUTSIDE_STAGE', '原理图阶段不判、交给后续环节'))
RESULT_SHORT = {'PASS': '通过', 'FAIL': '没通过', 'INSUFFICIENT': '资料不足', 'NA': '无关',
                'NA_OUTSIDE_STAGE': '交给后续环节'}
# Why the schematic cannot be finalised yet, in the order a reader should act on them.
BLOCKERS = (('fail', '%d 条检查发现的错误还没改'),
            ('gap', '%d 条检查缺资料或设计依据，对应下面列出的待办'),
            ('gap_tasks', '%d 件待办没解决（同一原因合并，涉及 %d 条缺资料或设计依据的检查）'),
            ('requirement', '%d 条需求还要用户拍板'),
            ('review', '%d 条检查审查还没做完'),
            ('grading', '%d 组资料不足的检查还没逐条判断后果'),
            ('netlist', '原理图导出的网表不完整或导出失败'))
IMPACT_CLASS_WORDS = OrderedDict((('DAMAGE_OR_HAZARD', '损坏或危险'), ('CORE_LINK_LOSS', '核心链路断开'),
                                  ('REQUIRED_FUNCTION', '必需功能'), ('PERFORMANCE_OR_LIFE', '性能或寿命'),
                                  ('LOCAL_OR_DATA', '局部或资料'), ('OPTIMIZATION', '可选优化')))
SCOPES = {'input_consistency': '输入资料一致性核对', 'requirements': '需求逐条覆盖核对',
          'chains': '功能链覆盖核对', 'states': '工作状态覆盖核对',
          'datasheets': '器件资料覆盖核对', 'history': '上一版问题处理核对'}
# Checks about drawings, BOM and library fields rather than the circuit itself.
DOCUMENT_RULES = {'DOC-A01', 'DOC-A02', 'DOC-A03', 'DOC-A04', 'DOC-T01', 'DOC-D01',
                  'DOC-V01', 'DOC-V02', 'DOC-Q01', 'DEV-D04'}
# Words readers found obscure; record text that reaches the report must not use them.
JARGON = ('冻结', '闸门', '原生', '下游', '移交', '接收方', '闭合', '绑定', '本行', '证据不足', '技能',
          'remediation', 'handoff', 'fit')


def cell(text):
    return str(text).replace('|', '\\|').replace('\n', ' ').strip()


def worst(levels):
    found = [s for s in SEVERITIES if s in levels]
    return found[0] if found else None


def rule_of(key):
    return key.split('.', 1)[0]


def is_document(check_ids):
    return bool(check_ids) and all(rule_of(k) in DOCUMENT_RULES for k in check_ids)


def blocker_reasons(blockers, results, tasks=None):
    """Every blocker in plain words; scope audits name the check and the finding behind them.
    Evidence gaps are counted by the work items (root causes) behind them when those are known."""
    kinds, scopes, unknown, gap_keys = Counter(), [], [], set()
    scope_checks = results.get('scope_checks') or {}
    checks = {c.get('id'): c for c in results.get('checks') or [] if isinstance(c, dict)}
    for b in blockers:
        if 'review work not completed' in b:
            kinds['review'] += 1
        elif 'P0 requires verified repair' in b or 'unresolved blocking FAIL' in b:
            kinds['fail'] += 1
        elif 'unresolved blocking INSUFFICIENT' in b:
            kinds['gap'] += 1
            gap_keys.add(b.split(': unresolved blocking', 1)[0])
        elif 'unresolved requirement decision' in b:
            kinds['requirement'] += 1
        elif 'need individual grading' in b:
            kinds['grading'] += 1
        elif 'input netlist failed' in b:
            kinds['netlist'] = 1
        elif b.startswith('scope ') and ': coverage audit not PASS' in b:
            dim = b[len('scope '):].split(':', 1)[0]
            key = scope_checks.get(dim, '')
            finding = (checks.get(key) or {}).get('finding_id')
            scopes.append('%s没通过（检查 %s%s）' % (SCOPES.get(dim, dim), key,
                                                  '，问题见 %s' % finding if finding else ''))
        else:
            unknown.append(b)
    owning = [t for t in tasks or [] if gap_keys & set(t.get('check_ids') or [])]
    if owning and gap_keys <= {k for t in owning for k in t.get('check_ids') or []}:
        kinds['gap_tasks'], kinds['gap'] = len(owning), 0
    out = [(text % ((kinds[key], len(gap_keys)) if key == 'gap_tasks' else kinds[key])) if '%d' in text else text
           for key, text in BLOCKERS if kinds[key]]
    out += scopes
    if unknown:
        out.append('另有 %d 项定稿条件没满足，原文见 record/review-gate.json 的 blockers：%s'
                   % (len(unknown), '；'.join(unknown[:3])))
    return out


def jargon_in(text):
    found = []
    for word in JARGON:
        pattern = r'(?<![A-Za-z])%s(?![A-Za-z])' % word if word.isascii() else re.escape(word)
        if re.search(pattern, text, re.I if word.isascii() else 0):
            found.append(word)
    return found


def item_kind(rows):
    kinds = {r.get('review_result') if r.get('review_result') == 'FAIL' else r.get('gap_cause') for r in rows}
    for key, label in KINDS.items():
        if key in kinds:
            if key == 'FAIL' and is_document([r.get('id', '') for r in rows if r.get('review_result') == 'FAIL']):
                return '文档错误'
            return label
    return '待处理'


def anchors(obj):
    """Refs and nets a planned check is about, for telling the reader where a requirement applies."""
    if not isinstance(obj, dict):
        return []
    def pick(one, many):
        return ([obj[one]] if isinstance(obj.get(one), str) else []) + \
            [x for x in obj.get(many) or [] if isinstance(x, str)]
    return pick('ref', 'refs') or pick('net', 'nets')


def unique(values):
    seen = []
    for v in values:
        if isinstance(v, str) and v.strip() and v.strip() not in seen:
            seen.append(v.strip())
    return seen


def task_level(task, checks):
    rows = [checks[c] for c in task.get('check_ids') or [] if c in checks]
    return worst({r.get('severity') or r.get('potential_severity') for r in rows})


FIELD_ITEMS_SHOWN = 3


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
            # 合并了很多检查的待办只列前几条，避免把每条检查的缺口拼成一长串。
            shown = values[:FIELD_ITEMS_SHOWN]
            more = len(values) - len(shown)
            lines.append('- **%s**：%s' % (label, '；'.join(shown)) +
                         ('（另有 %d 条，见涉及检查的资料需求）' % more if more else ''))
    lines.append('')
    return lines


def covered_by_findings(task, checks, findings):
    """待办只是“改正已列出的错误”：全部检查都是 FAIL 且已归入某个问题。"""
    ids = task.get('check_ids') or []
    owned = {k: f.get('id') for f in findings for k in f.get('check_ids') or []}
    if not ids or any((checks.get(k) or {}).get('review_result') != 'FAIL' or k not in owned for k in ids):
        return []
    return unique([owned[k] for k in ids])


SR_FEEDBACK_KINDS = (('false_alarm', '误报'), ('over_strict', '规则过严或关闭条件不合理'),
                     ('missed', '漏报'), ('unclear', '说明不清或互相矛盾'),
                     ('software_bug', '已复现的程序错误'), ('coverage_gap', '自动化覆盖或格式适配不足'))


def sr_feedback_errors(items):
    """notes.sr_feedback: [{kind, rules, instance, suggestion}]，每条都要点名规则和实例。"""
    if items is None:
        return []
    if not isinstance(items, list):
        return ['sr_feedback must be a list']
    errors = []
    kinds = dict(SR_FEEDBACK_KINDS)
    for i, item in enumerate(items):
        ok = (isinstance(item, dict) and set(item) == {'kind', 'rules', 'instance', 'suggestion'}
              and item.get('kind') in kinds and isinstance(item.get('rules'), list) and item['rules']
              and all(isinstance(r, str) and re.match(r'^[A-Z]{3}-[A-Z]\d{2}$', r) for r in item['rules'])
              and all(isinstance(item.get(k), str) and item[k].strip() for k in ('instance', 'suggestion')))
        if not ok:
            errors.append('sr_feedback[%d] needs kind (%s), rule IDs, instance and suggestion'
                          % (i, '/'.join(kinds)))
    return errors


def render_sr_feedback(items):
    """审查者对 SR 技能的反馈：误报、过严、漏报、说明不清，按类分组，给 SR 维护用。"""
    if not items or sr_feedback_errors(items):
        return []
    out = ['## 对 SR 技能的反馈（设计者不用处理）', '',
           '审查中发现的 SR 规则误报、过严、漏报或说明问题，逐条写明规则、本板实例和改进建议，留给 SR 维护。', '']
    for kind, label in SR_FEEDBACK_KINDS:
        rows = [i for i in items if i['kind'] == kind]
        if rows:
            out += ['### ' + label, '']
            out += ['%d. **%s**：%s 建议：%s' % (n, '、'.join(r['rules']), cell(r['instance']), cell(r['suggestion']))
                    for n, r in enumerate(rows, 1)]
            out.append('')
    return out


def same_text(a, b):
    """改的目的只是复述标题时不再单列。"""
    norm = lambda s: re.sub(r'[\s，。；、,.;:：]', '', str(s or ''))
    return bool(a) and bool(b) and (norm(a) == norm(b) or norm(a) in norm(b))


def failed_checks(rows, findings):
    """Name every failed check and the problem it belongs to, so the count can be traced."""
    owner = {}
    for f in findings:
        for k in f.get('check_ids') or []:
            owner.setdefault(k, f.get('id'))
    groups = {}
    for k, c in rows.items():
        if c.get('review_result') == 'FAIL':
            groups.setdefault(owner.get(k) or c.get('finding_id'), []).append(k)
    return '；'.join('%s → 问题 %s' % ('、'.join(ids), fid) if fid else '、'.join(ids) + ' → 未写成问题'
                    for fid, ids in groups.items())


EXPLANATION_LABELS = (('risk_if_omitted', '不查会漏掉什么'), ('closes_when', '关闭条件'),
                      ('false_alarms', '常见误报/合法结构'),
                      ('purpose', '在检查什么'), ('connections', '与其他检查怎样衔接'))  # 后两项为第 1 版记录


def render_check_explanations(plan, results):
    """只为没通过和资料不足的检查展开说明，不适用的写一句理由，通过项不展开。"""
    planned = {c['id']: c for c in plan.get('checks') or [] if isinstance(c, dict) and 'id' in c}
    reviewed = {c['id']: c for c in results.get('checks') or [] if isinstance(c, dict) and 'id' in c}
    keys = sorted(set(planned) | set(reviewed))
    shared = plan.get('check_explanations') if isinstance(plan.get('check_explanations'), dict) else {}
    if not shared and not any('check_explanation' in c for c in list(planned.values()) + list(reviewed.values())):
        return []  # Historical records stay historical; no live-catalog substitution.
    status = {k: (reviewed.get(k) or {}).get('review_result') for k in keys}
    parents = {child: k for k, r in reviewed.items() for child in (r.get('split_out') or [])
               if isinstance(child, str)}
    open_keys = [k for k in keys if status[k] in ('FAIL', 'INSUFFICIENT')]
    na_keys = [k for k in keys if status[k] == 'NA']
    out = ['## 逐项检查说明', '',
           '“不查会漏掉什么”是检查的理由，不代表已经发现该问题，也不决定风险等级。'
           '没通过和资料不足的检查逐项给出关闭条件；不适用的只写理由；其余 %d 项通过或未审结，不展开。'
           % (len(keys) - len(open_keys) - len(na_keys)), '']
    for key in open_keys:
        p, r = planned.get(key, {}), reviewed.get(key, {})
        rule = p.get('rule') or r.get('rule')
        base = p['check_explanation'] if 'check_explanation' in p else shared.get(rule)
        base = dict(base) if isinstance(base, dict) else {}
        override = r.get('check_explanation') if isinstance(r.get('check_explanation'), dict) else {}
        where = '、'.join(anchors(p.get('object'))) or '见检查对象'
        out += ['### %s（%s）' % (key, RESULT_SHORT[status[key]]), '', '- **对象**：' + cell(where)]
        for field, label in EXPLANATION_LABELS:
            if field in override:
                out.append('- **%s**（本次对象说明）：%s' % (label, cell(override[field])))
            elif base.get(field):
                out.append('- **%s**：%s' % (label, cell(base[field])))
        if not base and not override:
            out.append('- **说明**：记录未提供，不能据此推断本次风险')
        if key in parents:
            parent = parents[key]
            out.append('- **所属汇总项**：%s（其余对象%s）' % (
                parent, RESULT_SHORT.get(status.get(parent), '未审结')))
        out += ['- **本次结论依据**：' + cell(r.get('rationale') or '尚未形成结论'), '']
    if na_keys:
        out += ['### 不适用', '']
        out += ['- %s：%s' % (k, cell((reviewed.get(k) or {}).get('rationale') or '记录未写理由')) for k in na_keys]
        out.append('')
    return out


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
    defect_list = [f for f in findings if f.get('kind') == 'DEFECT']
    doc_defects = [f for f in defect_list if is_document(f.get('check_ids') or [])]
    defects = len(defect_list)

    out = ['# %s' % (title or '原理图审查报告'), '']
    if not gate.get('valid'):
        out += ['> **审查记录本身有错，这份报告的结论不可用。** 先改正记录再重新出报告：' +
                '；'.join(cell(e) for e in (gate.get('errors') or [])[:5]), '']
    out += ['## 结论', '']
    if defects:
        out.append('- **发现的错误**：电路错误 %d 处，文档错误 %d 处（%s），见“发现的错误”一节。' % (
            defects - len(doc_defects), len(doc_defects),
            '、'.join('%s %d 处' % (s, by_sev[s]) for s in SEVERITIES if by_sev.get(s))))
    else:
        out.append('- **发现的错误**：0 处。')
    gap_ids = {k for k, c in current_rows.items() if c.get('review_result') == 'INSUFFICIENT'}
    gap_tasks = [t for t in tasks if gap_ids.intersection(t.get('check_ids') or [])]
    if gap_ids:
        owned = {k for t in gap_tasks for k in t.get('check_ids') or []}
        p0 = sum(any(checks[k].get('potential_severity') == 'P0'
                     for k in gap_ids.intersection(t.get('check_ids') or [])) for t in gap_tasks)
        out.append('- **仍待确认**：%d 件事项，其中 %d 件可能涉及安全或损坏（P0）；资料不足不等于已发现缺陷。'
                   % (len(gap_tasks), p0))
        if gap_ids - owned:
            out.append('- **待办整理未完成**：另有 %d 条无法判断的检查尚未关联待办。' % len(gap_ids - owned))
    reasons = blocker_reasons(gate.get('blockers') or [], results, tasks) if release != 'GO' else []
    if reasons:
        out.append('- **能否定稿**：%s。还差：' % RELEASE.get(release, release))
        out += ['  %d. %s；' % (i, r) for i, r in enumerate(reasons, 1)]
        out[-1] = out[-1][:-1] + '。'
    else:
        out.append('- **能否定稿**：%s。' % RELEASE.get(release, release))
    if tasks:
        fixes = sum(bool(covered_by_findings(t, checks, findings)) for t in tasks)
        detail = ('（其中修正已列错误 %d 件、待确认 %d 件）' % (fixes, len(gap_tasks))) if fixes else ''
        out.append('- **待办**：%d 件%s，按可能后果从重到轻列在“待办”一节。' % (len(tasks), detail))
    if phase == 'design_iteration':
        out.append('- 这次是设计过程中的检查，不是定稿审查；“能否定稿”只说明离定稿还差什么。')
    if 'history_inputs' in results:
        history_inputs = [x for x in results.get('history_inputs') or [] if isinstance(x, str)]
        out.append('- **上一版审查材料**：%s' % (
            '本轮可见 %s；只用于“上一版问题”的复验，本轮结论按当前资料独立得出。' % '、'.join(
                '`%s`' % cell(x) for x in history_inputs[:4]) if history_inputs else '本轮没有使用。'))
    out.append('')
    if notes.get('summary'):
        out += [notes['summary'], '']

    if findings:
        out += ['## 发现的错误', '', SEVERITY_LEGEND, '']
        for f in sorted(findings, key=lambda f: SEVERITIES.index(f['severity']) if f.get('severity') in SEVERITIES else 9):
            fix = f.get('remediation') or {}
            level = f.get('severity')
            out.append('### %s　%s（%s：%s）' % (f.get('id'), f.get('title') or '', level, SEVERITY_WORDS.get(level, '')))
            out.append('')
            out.append('类型：%s' % ('文档错误' if f in doc_defects else '电路错误'))
            out.append('')
            if item_notes.get(f.get('id')):
                out += [item_notes[f['id']], '']
            where = f.get('location') or {}
            for label, value in (('位置', '、'.join(('第%s页' % x) for x in where.get('pages') or []) +
                                  ('　' + '、'.join(where.get('refs') or []) if where.get('refs') else '')),
                                 ('问题', f.get('observed')), ('后果', f.get('impact')),
                                 ('怎么改', f.get('recommendation')),
                                 ('改的目的', fix.get('purpose') if not same_text(fix.get('purpose'), f.get('title')) else None),
                                 ('改完怎么验证', f.get('verification')),
                                 ('涉及的检查', '、'.join(
                                     '%s（%s）' % (k, RESULT_SHORT.get((checks.get(k) or {}).get('review_result'), '记录中没有'))
                                     for k in f.get('check_ids') or []))):
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
            owners = covered_by_findings(task, checks, findings)
            if owners:
                out += ['### %s　%s' % (task['id'], task.get('title') or task.get('root_cause') or ''), '',
                        '按上文“发现的错误”中问题 %s 的改法处理，这里不重复。' % '、'.join(owners), '']
                continue
            out += render_item(task, checks, item_notes)

    if handoffs:
        out += ['## 交给后续环节的要求', '',
                '下面这些要求在原理图上做不了，要在 PCB、热设计、测试等后续环节落实，不算原理图的错误，'
                '也不影响原理图定稿。原理图交出时把这张表一起交给对应负责方即可。', '',
                '| 负责方 | 条数 | 涉及位号/网络 | 要落实的要求 | 怎么验证 |', '|---|---:|---|---|---|']
        planned = {c.get('id'): c for c in plan.get('checks') or [] if isinstance(c, dict)}
        groups = OrderedDict()
        for c in handoffs:
            groups.setdefault('、'.join(c['handoff'].get('receivers') or ['未指定']), []).append(c)
        for who, rows in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            hs = [c['handoff'] for c in rows]
            where = unique(x for c in rows for x in anchors((planned.get(c['id']) or {}).get('object')))
            shown = '、'.join(where[:12]) + ('等 %d 处' % len(where) if len(where) > 12 else '')
            out.append('| %s | %d | %s | %s | %s |' % (cell(who), len(hs), cell(shown or '整板'),
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
                '<details>', '<summary>展开工具限制及本轮核对方法</summary>', '',
                '下面 %d 条检查，SR 的自动检查工具判断不了，审查时改为逐项对照网表和原厂资料核对，结论按核对结果算。'
                '这里记录 SR 为什么做不到、该怎么改进 SR，留给 SR 维护。' % len(tool_gaps), '']
        same = OrderedDict()
        for t in tool_gaps:
            key = tuple(cell(t.get(f) or '') for f in ('tool_limitation', 'sr_improvement', 'method'))
            same.setdefault(key, []).append(t['check_id'])
        for (limit, improve, method), ids in same.items():
            out += ['### ' + '、'.join(ids), '',
                    '- **SR 为什么做不到**：' + limit,
                    '- **建议怎么改进 SR**：' + improve,
                    '- **这次怎么核对的**：' + method, '']
        out += ['</details>', '']

    feedback = render_sr_feedback(notes.get('sr_feedback'))
    if feedback:
        out += feedback[:2] + ['<details>', '<summary>展开 SR 维护反馈</summary>', ''] + feedback[2:] + ['</details>', '']

    gaps = [c for c in current_rows.values() if c.get('review_result') == 'INSUFFICIENT']
    pot = Counter(c.get('potential_severity') for c in gaps)
    cause = Counter(c.get('gap_cause') for c in gaps)
    classes = Counter((c.get('impact_assessment') or {}).get('consequence_class') for c in gaps
                      if isinstance(c.get('impact_assessment'), dict)
                      and c['impact_assessment'].get('consequence_class') in IMPACT_CLASS_WORDS)
    history = (summary.get('history') or {}).get('checks', 0)
    out += ['## 数字一览', '', '| 项目 | 数量 |', '|---|---|',
            '| 检查总数 | %d |' % (summary.get('current') or {}).get('checks', len(current_rows)),
            '| 通过 / 没通过 / 资料不足无法判断 | %d / %d / %d |' % (counts.get('PASS', 0), counts.get('FAIL', 0), counts.get('INSUFFICIENT', 0)),
            '| 与本产品无关（NA） | %d |' % counts.get('NA', 0),
            '| 原理图阶段不判、交给后续环节 | %d |' % counts.get('NA_OUTSIDE_STAGE', 0),
            '| 发现的错误，按严重程度 P0 / P1 / P2 / P3 | %s |' % ' / '.join(str(by_sev.get(s, 0)) for s in SEVERITIES),
            '| 其中文档错误 | %d |' % len(doc_defects),
            '| 待办（同一原因合并） | %d 件 |' % len(tasks),
            '| 资料不足的检查，可能的严重程度 P0 / P1 / P2 / P3 | %s |' % ' / '.join(str(pot.get(s, 0)) for s in SEVERITIES),
            '| 资料不足的原因：%s | %s |' % (' / '.join(CAUSES.values()), ' / '.join(str(cause.get(k, 0)) for k in CAUSES)),
            ] + (['| 资料不足的可能后果：%s | %s |' % (' / '.join(IMPACT_CLASS_WORDS.values()),
                                                  ' / '.join(str(classes.get(k, 0)) for k in IMPACT_CLASS_WORDS))]
                 if classes else []) + [
            '| 交给后续环节的要求 | %d |' % len(handoffs),
            '| 上一版问题的处理记录（不计入上面各行） | %d |' % history, '',
            '“条”是检查条数，待办“件”按同一原因合并，两者不能相加。', '']
    explanations = render_check_explanations(plan, results)
    if explanations:
        out += ['<details>', '<summary>展开逐项依据与关闭条件（完整保留）</summary>', ''] + explanations + ['</details>', '']
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
    notes = load(args.notes) if args.notes else None
    problems = sr_feedback_errors((notes or {}).get('sr_feedback'))
    if problems:
        print('notes.json: ' + '; '.join(problems), file=sys.stderr)
        return 2
    text = render(load(args.plan), load(args.results), load(args.gate), notes, args.title)
    Path(args.out).write_text(text, encoding='utf-8')
    print('wrote', args.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())

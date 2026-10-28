#!/usr/bin/env python3
"""Render the one human-facing review report from the validated ledger.

Structure and numbers come only from review-plan / review-results / review-gate, so every
agent produces the same report for the same records. The agent adds plain-language text
through an optional notes file; it cannot change verdicts or counts here.

notes.json (optional):
  {"summary": "1-3 sentences for a hardware engineer",
   "items": {"<work item or finding id>": "one or two plain sentences"},
   "sr_feedback": [{"kind": "false_alarm|over_strict|missed|unclear", "rules": ["PRO-C02"],
                    "instance": "what happened on this board", "suggestion": "how SR should change"}]}
"""
import results_model
import bom_constraints
import argparse
import json
import re
import sys
from collections import Counter, OrderedDict, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
import catalog
import function_reading
from electrical_contract import text
from review_functions import RESULT_MAX_CHARS, circuit_functions
from review_stage_scope import user_deferred
from task_scope import ownership, task_view
from report_html import to_html

SR_SECTION = '## 对 SR 的反馈（设计者不用处理）'
COUNTS_TITLE = '数字一览'   # the count table, folded in the appendix; its labels are fixed here
RECORD_INDEX = (('review-results.json', '每条检查的结论、依据、缺的资料和修改条件'),
                ('review-plan.json', '检查计划：全部检查项和覆盖范围'),
                ('review-gate.json', '校验结果：各项计数、定稿条件和自检提示明细'),
                ('db.json', '从原理图导出的网表数据'),
                ('intent.json', '审查依据：需求、电源轨、装配和器件声明'),
                ('lint-cold.json', '自动检查输出（只用网表）'),
                ('lint-hot.json', '自动检查输出（加上器件资料）'),
                ('evidence/', '引用的资料摘录、计算和图片'))
# REVIEW_INCOMPLETE is the reviewer's own unfinished work: render() refuses it, so no reader word exists for it;
# a check the user deferred is outside the review's scope (NA), not a gap (2026-10-27, user: A).
OPEN_CAUSE_WORDS = OrderedDict([('EXTERNAL_DATA', '缺资料')])
RELEASE = {'GO': '可以定稿', 'CONDITIONAL_GO': '可以有条件定稿', 'NO_GO': '还不能定稿'}
KINDS = OrderedDict([('FAIL', '电路错误'),
                     ('EXTERNAL_DATA', '缺资料')])
SEVERITIES = ('P0', 'P1', 'P2', 'P3')
SEVERITY_WORDS = {'P0': '可能损坏器件或危及安全', 'P1': '必需功能可能不达标',
                  'P2': '局部或次要问题', 'P3': '可选优化'}
SEVERITY_LEGEND = '严重程度：P0 可能损坏器件或危及安全；P1 必需功能可能不达标；P2 局部或次要问题；P3 可选优化。'
HISTORY_RULE = 'REQ-H02'
RESULT_SHORT = {'PASS': '合格', 'FAIL': '不合格', 'INSUFFICIENT': '资料不足', 'NA': '无关',
                'NA_OUTSIDE_STAGE': '交给后续环节', 'NA_DEFERRED': '用户暂缓，本次不审'}
# Why the schematic cannot be finalised yet, in the order a reader should act on them.
BLOCKERS = (('fail', '%d 条检查发现的错误还没改'),
            ('gap', '%d 条检查缺资料或设计依据，对应下面列出的待办'),
            ('gap_tasks', '%d 件待办阻塞定稿（同一原因合并，涉及 %d 条缺资料或设计依据的阻塞检查；不阻塞的待办不计在内）'),
            ('requirement', '%d 条需求还要用户拍板'),
            ('grading', '%d 组资料不足的检查还没逐条判断后果'),
            ('netlist', '原理图导出的网表不完整或导出失败'))
IMPACT_CLASS_WORDS = OrderedDict((('DAMAGE_OR_HAZARD', '损坏或危险'), ('CORE_LINK_LOSS', '核心链路断开'),
                                  ('COMPONENT_DAMAGE', '器件损坏（不致危险）'), ('REQUIRED_FUNCTION', '必需功能'), ('PERFORMANCE_OR_LIFE', '性能或寿命'),
                                  ('LOCAL_OR_DATA', '局部或资料'), ('OPTIMIZATION', '可选优化')))
SCOPES = {'input_consistency': '输入资料一致性核对', 'requirements': '需求逐条覆盖核对',
          'chains': '功能链覆盖核对', 'states': '工作状态覆盖核对',
          'datasheets': '器件资料覆盖核对', 'history': '上一版问题处理核对'}
# Checks about drawings, BOM and library fields rather than the circuit itself.
DOCUMENT_RULES = {'DOC-A01', 'DOC-A02', 'DOC-A03', 'DOC-A04', 'DOC-T01', 'DOC-D01',
                  'DOC-V01', 'DOC-V02', 'DOC-Q01', 'DEV-D04'}
# Words readers found obscure; record text that reaches the report must not use them.
JARGON = ('冻结', '闸门', '原生', '下游', '移交', '接收方', '闭合', '绑定', '本检查项', '证据不足', '技能',
          'remediation', 'handoff', 'fit')
CHECK_ID_RE = re.compile(r'\b[A-Z]{3}-[A-Z]\d{2}(?:\.[A-Za-z0-9_~-]+)+')


def cell(text):
    return str(text).replace('|', '\\|').replace('\n', ' ').strip()


def rule_of(key):
    return key.split('.', 1)[0]


def is_document(check_ids):
    return bool(check_ids) and all(rule_of(k) in DOCUMENT_RULES for k in check_ids)


def blocker_reasons(blockers, results, tasks=None, skip=()):
    """Every blocker in plain words; scope audits name the check and the finding behind them.
    Evidence gaps are counted by the work items (root causes) behind them when those are known."""
    kinds, scopes, unknown, gap_keys = Counter(), [], [], set()
    scope_checks = results.get('scope_checks') or {}
    checks = {c.get('id'): c for c in results.get('checks') or [] if isinstance(c, dict)}
    for b in blockers:
        if 'P0 requires verified repair' in b or 'unresolved blocking FAIL' in b:
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
           for key, text in BLOCKERS if kinds[key] and key not in skip]
    out += scopes
    if unknown:
        out.append('另有 %d 项定稿条件没满足，原文见 record/review-gate.json 的 blockers：%s'
                   % (len(unknown), '；'.join(unknown[:3])))
    return out


def jargon_in(text):
    text = CHECK_ID_RE.sub(' ', text)   # a check id the plan generated is a name, not wording
    found = []
    for word in JARGON:
        pattern = r'(?<![A-Za-z])%s(?![A-Za-z])' % word if word.isascii() else re.escape(word)
        if re.search(pattern, text, re.I if word.isascii() else 0):
            found.append(word)
    return found


def item_kind(rows):
    """FAIL names the item; otherwise the gap cause its checks carry (only missing data reaches a report)."""
    fails = [r.get('id', '') for r in rows if r.get('review_result') == 'FAIL']
    if fails:
        return '文档错误' if is_document(fails) else KINDS['FAIL']
    return KINDS['EXTERNAL_DATA'] if any(r.get('gap_cause') == 'EXTERNAL_DATA' for r in rows) else '待处理'


def anchors(obj):
    """Refs and nets a planned check is about, for telling the reader where a requirement applies."""
    if not isinstance(obj, dict):
        return []
    def pick(one, many):
        return ([obj[one]] if isinstance(obj.get(one), str) else []) + \
            [x for x in obj.get(many) or [] if isinstance(x, str)]
    return pick('ref', 'refs') or pick('net', 'nets')


REF_SLOT = '\x00'


def generic(text, refs):
    """The text with this check's own refs/nets blanked, so per-part copies of one requirement compare equal."""
    for ref in sorted(refs, key=len, reverse=True):
        text = re.sub(r'(?<![A-Za-z0-9–~-])%s(?![0-9–~-])' % re.escape(ref), REF_SLOT, text)
    return text


def unique(values):
    seen = []
    for v in values:
        if isinstance(v, str) and v.strip() and v.strip() not in seen:
            seen.append(v.strip())
    return seen


def join_statements(values):
    """Join prose without stacking a separator after a full stop."""
    out = ''
    for value in values:
        if out and not out.endswith(('。', '；', '！', '？', ';', '!', '?')):
            out += '；'
        out += value
    return out


def task_level(task, checks, owners=None, classes=False):
    return task_view(task, checks, owners, classes)['level']


def restates(short, long):
    """`short` says what `long` says: with page/section numbers and punctuation removed, 90% of
    `short` appears in `long` in the same order (seen in a delivered report: a work item's next_action and
    its gap's how_to_close differed only by page numbers, and both were printed)."""
    def plain(t):
        return re.sub(r'(?:p|P|第|§)?\d+(?:[–\-~/.,]\d+)*(?:页)?|[\s，、；;：:。.()（）/]+', '', t)
    a, b = plain(short), plain(long)
    if not a or len(a) > len(b):
        return False
    matched = sum(m.size for m in SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks())
    return matched >= 0.9 * len(a)


READ_RE = re.compile(r'^已读([^；;]*)[；;]?\s*(.*)$', re.S)


def split_read(values):
    """What was already read, said once; what is still to do, apart (seen in a delivered report: a work item and
    its gap each opened with the same "已读…手册 p3–7…" clause, and both were printed)."""
    read, todo = [], []
    for value in unique(values):
        m = READ_RE.match(value)
        if m:
            read.append(m.group(1).strip())
            value = m.group(2).strip()
        if value:
            todo.append(value)
    return drop_restated(read), drop_restated(todo)


def drop_restated(values):
    """Keep each statement once: drop one that a longer (or earlier, equally long) one already says."""
    values = unique(values)
    return [v for i, v in enumerate(values)
            if not any(j != i and restates(v, o) and (len(o) > len(v) or j < i) for j, o in enumerate(values))]


def render_item(task, checks, notes, owners=None, classes=False):
    """A gap card (user 2026-10-27: 报告太冗长、没有层次): what is missing, what it blocks, how to close it and the
    circuit change if it cannot be had. Why it matters is the level and the worst case; the reason stays in the
    record."""
    rows = [checks[c] for c in task.get('check_ids') or [] if c in checks]
    view = task_view(task, checks, owners, classes)
    level = view['level']
    head = '### %s　%s' % (task['id'], task.get('title') or task.get('root_cause') or '')
    # Count the owned branches by level so a P0 item cannot silently absorb P1 checks.
    owned = defaultdict(list)
    for cid, _, req in view['requests']:
        owned[cid].append(req.get('potential_severity'))
    branch_levels = Counter()
    for r in rows:
        if r.get('review_result') == 'FAIL':
            branch_levels[r.get('severity')] += 1
        elif r.get('review_result') == 'INSUFFICIENT':
            branch_levels.update(owned.get(r.get('id')) or [r.get('potential_severity')])
    breakdown = ''
    if len([k for k in branch_levels if k]) > 1:
        breakdown = '（%s）' % '、'.join('%s %d' % (k, branch_levels[k]) for k in SEVERITIES if branch_levels.get(k))
    sub = results_model.GAP_SUBCLASSES.get(task.get('subclass'))
    kind = item_kind(rows)
    meta = '**%s**　%s　涉及 %d 条检查%s' % (
        ('%s %s' % (level, SEVERITY_WORDS[level])) if level else '未定级',
        '%s（%s）' % (kind, sub) if sub and kind != KINDS['FAIL'] and sub != kind else kind, len(rows), breakdown)
    lines = [head, '', meta, '']
    if view['ambiguous_checks']:
        lines += ['风险和资料需求尚未按任务分清：' + '、'.join(view['ambiguous_checks']) +
                  '。相关检查的风险仍保留，不能把它们重复计为多个高风险根因。', '']
    requests = [req for _, _, req in view['requests']]
    names = [task.get(f).strip() for f in ('title', 'root_cause') if isinstance(task.get(f), str) and task[f].strip()]
    scopes = []
    for scope in unique([q.get('required_scope') for q in requests] + [task.get('required_scope')]):
        # A scope that only repeats the title/root cause adds nothing; show the remainder or nothing.
        rest = scope
        for name in names:
            rest = rest.replace(name, '')
        if re.sub(r'[\s，、；;：:。.()（）/]+', '', rest):
            scopes.append(scope)
    criteria = unique([q.get('closure_criterion') for q in requests] + [task.get('closure_criterion')])
    missing = unique([(task.get('root_cause') or '').strip()])
    if scopes:
        missing.append('适用范围：' + join_statements(scopes))
    action = (task.get('next_action') or '').strip()
    # Keep the acceptance text once, in its own field, if it is an exact suffix.
    for criterion in sorted(criteria, key=len, reverse=True):
        if action == criterion:
            action = ''
        elif action.endswith('；' + criterion):
            action = action[:-len(criterion)-1]
    acquisitions = unique(q.get('acquisition') for q in requests)
    if action and any(action in a or restates(action, a) for a in acquisitions):
        action = ''   # the request text already carries the action (verbatim or reworded with page numbers)
    read, todo = split_read([action] + acquisitions)
    option = task.get('design_option') or {}
    proposed = option.get('status') == 'PROPOSED'
    fields = [('缺什么', missing),
              ('最坏情况', [task.get('worst_case')]),
              ('影响哪些结论', fold_blocks(task.get('blocks') or [])),
              ('已查过', read),
              ('怎么补', todo),
              ('怎样算通过', criteria),
              ('拿不到时的改法', [option.get('summary')] if proposed else [])]
    for label, values in fields:
        values = unique(values)
        if values:
            # Repeated requests share one line; every distinct acceptance stays visible.
            lines.append('- **%s**：%s' % (label, join_statements(values)))
    if notes.get(task['id']):
        lines.append('- **审查员补充**：%s' % notes[task['id']])
    if proposed:
        lines += render_figures(option.get('figures'))
    lines.append('')
    return lines


FIGURE_WORDS = {'ACTUAL': '现状', 'REFERENCE': '原厂参考', 'AFTER': '改后', 'MECHANISM': '失效过程'}
LISTED_MAX = 6


def listed(items, unit):
    """Up to LISTED_MAX items in full, the rest as a count (a finding in R7 listed 11 check ids)."""
    items = [i for i in items if i]
    if len(items) <= LISTED_MAX:
        return '、'.join(items)
    return '、'.join(items[:LISTED_MAX]) + '等 %d %s' % (len(items), unit)


def page_word(page):
    """第5页 for a page number; a page named by the record (p5 05_Bias_Control) is printed as written."""
    text = str(page).strip()
    return '第%s页' % text if re.fullmatch(r'\d+', text) else text


def fold_blocks(blocks):
    """影响哪些结论: each blocked conclusion by its name only (a R8 work item explained three of them in 900
    characters; the explanation stays in the ledger), at most LISTED_MAX."""
    heads = unique(re.split(r'[：:，]', b.strip(), maxsplit=1)[0].strip() for b in blocks or [] if isinstance(b, str) and b.strip())
    return [listed(heads, '项')] if heads else []


RISK_SOURCE_WORDS = {'ESTIMATE': '按典型值估算', 'STRESS': '保证值在额定内、降额不足'}


def risk_rows(items):
    """One row per (function, margin): a margin reached by two rows of the same function was two rows (R8: three
    electrolytics listed twice, once under cell NONE; life rows left the list on 2026-10-28, two estimate rows remain). The row keeps every check and risk type; the entry
    it shows is the one with a table cell, else the one written without NONE."""
    rows = OrderedDict()
    for e in items or []:
        m = e.get('margin') or {}
        rows.setdefault((e.get('function_id'), m.get('value'), m.get('unit'), m.get('against')), []).append(e)
    out = []
    for entries in rows.values():
        rank = lambda e: 0 if e.get('cell') in catalog.BOUNDS else 2 if e.get('cell') == catalog.NO_CELL else 1
        shown = dict(min(entries, key=rank))
        shown['types'] = unique([t for e in entries for t in e.get('types') or ()])
        shown['check_ids'] = unique([e['check_id'] for e in entries if e.get('check_id')])
        out.append(shown)
    return out


def render_risks(items):
    """风险清单（2026-10-26，用户：三档结论加四类风险标签，只靠估算过关的角点标风险，风险不限制定稿只单列）：结论是
    “合格，但有风险”的余量，按风险类型分组，每行写哪个角点只靠估算、怎么估的、余量、怎么改进、样机要测什么。"""
    rows = risk_rows(items)
    if not rows:
        return []
    out = ['## 风险清单', '',
           '下面 %d 项结论是“合格，但有风险”（涉及 %d 条检查）：在额定和需求范围内过关，但有一个角点只能按典型值估算'
           '（或降额不足），实际批次、环境或寿命末期可能达不到。风险不影响定稿，按“怎么改进”一列处理即可消除。'
           % (len(rows), sum(len(e['check_ids']) for e in rows)), '']
    by_type = OrderedDict((t, []) for t in catalog.RISK_TYPES)
    for e in rows:
        for t in e['types']:
            by_type.setdefault(t, []).append(e)
    for t, entries in by_type.items():
        if not entries:
            continue
        out += ['### %s风险（%d 项）' % (catalog.RISK_TYPES.get(t, t), len(entries)), '',
                '| 功能 | 参数（定界表格） | 只靠估算的角点 | 怎么估的 | 余量 | 怎么改进 | 样机要测 | 涉及检查 |',
                '|---|---|---|---|---|---|---|---|']
        for e in entries:
            m = e.get('margin') or {}
            margin = '%s 对 %s' % (_quantity(m.get('value'), m.get('unit')), m.get('against') or '')
            factor = e.get('estimate_factor')
            how_text = (e.get('how') or RISK_SOURCE_WORDS.get(e.get('source'), '')) + (
                '（已按 ×%g 打折）' % factor if isinstance(factor, (int, float)) and not isinstance(factor, bool) else '')
            out.append('| %s | %s%s | %s | %s | %s | %s | %s | %s |' % (
                cell(e.get('function_id') or ''), cell(e.get('aspect') or ''),
                '（%s）' % cell(e['cell']) if e.get('cell') else '', cell(e.get('corner') or ''), cell(how_text),
                cell(margin), cell(e.get('improvement') or ''), cell(e.get('verification') or '—'),
                cell('、'.join(e['check_ids']))))
        out.append('')
    return out


CONDITION_KIND_WORDS = {'NUMERIC_LIMIT': '保证值', 'TYPICAL_REFERENCE': '典型值', 'MANDATORY_CLAUSE': '强制条款',
                        'NETLIST_FACT': '网表事实', 'ENGINEERING_ASSUMPTION': '工程假定', 'DESIGN_CONSTRAINT': '设计约束'}


def _page_span(pages):
    return '' if not pages else ('p%d' % pages[0] if len(pages) == 1 or pages[0] == pages[-1] else 'p%d–%d' % (pages[0], pages[-1]))


def _limit_text(parameter):
    limit, unit = parameter.get('limit') or {}, parameter.get('unit') or ''
    if 'min' in limit and 'max' in limit:
        return '%s–%s %s' % (_shown(limit['min']), _shown(limit['max']), unit)
    if 'max' in limit:
        return '≤ %s %s' % (_shown(limit['max']), unit)
    if 'min' in limit:
        return '≥ %s %s' % (_shown(limit['min']), unit)
    return '—'


def render_configuration_settings(settings):
    """The settings the hardware verdicts rely on, for whoever writes the configuration table (the configuration is
    not reviewed: a capability the datasheet declares is reachable)."""
    if not settings:
        return []
    out = ['### 配置表要写的设置', '',
           '本审查按手册声明的能力判功能可达，不审配置表。下面这些硬件结论只在所列设置下成立，配置表照写即可；'
           '改了设置，对应的结论要重判。', '',
           '| 位号 | 配置项 | 设置 | 出处 | 依赖它的结论 |', '|---|---|---|---|---|']
    for s in settings:
        out.append('| %s | %s | %s | %s | %s |' % (cell(s['ref']), cell(s['group']), cell(s['value']),
                   cell(' '.join(x for x in (s.get('source'), s.get('locator')) if x)), cell('、'.join(s['used_in']))))
    return out + ['']


def render_parameter_sheet(rows, detail='compact'):
    """器件参数表（结果格式 7，2026-10-26）：条款 `refs` 点名的每只器件一行——读了哪份资料哪几页、引了几个参数、其中保证值 /
    典型值 / 强制条款各几条、用在哪些功能；`--detail full` 再逐参数一行。只汇总条款，不另下结论。"""
    if not rows:
        return []
    out = ['## 器件参数表', '',
           '下面每只器件一行，汇总功能判定引用它资料的条款：读了哪份资料的哪几页、引了几个参数、其中保证值 / 典型值 / 强制条款各几条、'
           '用在哪些功能。这张表只汇总条款，不另下结论；参数怎么用、余量多少见各功能的判断。', '',
           '| 位号 | 资料（页） | 引用的参数 | 保证值 / 典型值 / 强制条款 | 用在哪些功能 |', '|---|---|---|---|---|']
    for row in rows:
        docs = '；'.join(('%s（%s）' % (Path(str(s['source'])).name, _page_span(s['pages']))) if s['pages'] else Path(str(s['source'])).name
                        for s in row['sources'])
        n = row['counts']
        out.append('| %s | %s | %d | %d / %d / %d | %s |' % (row['ref'], cell(docs), n['total'], n['guaranteed'], n['typical'],
                                                             n['clauses'], cell('、'.join(row['functions']))))
    if detail == 'full':
        out += ['', '逐参数：', '', '| 位号 | 参数 | 限值 | 工况 | 口径 | 出处 | 用在 |', '|---|---|---|---|---|---|---|']
        for row in rows:
            for p in row['parameters']:
                where = '%s %s' % (Path(str(p.get('source') or '')).name, p.get('locator') or '')
                out.append('| %s | %s | %s | %s | %s | %s | %s |' % (
                    row['ref'], cell(p.get('parameter') or ''), cell(_limit_text(p)), cell(p.get('regime') or '—'),
                    CONDITION_KIND_WORDS.get(p.get('kind'), p.get('kind') or ''), cell(where.strip()),
                    cell('；'.join(p.get('used_in') or []) or '%s（未被余量或判断引用）' % p.get('function_id'))))
    return out + ['']


def render_figures(figures):
    """Each figure as an image packed under record/evidence, with its kind and caption below it."""
    lines = []
    for f in figures if isinstance(figures, list) else []:
        if not (isinstance(f, dict) and isinstance(f.get('source'), str) and f['source'].strip()):
            continue
        caption = cell(f.get('caption') or '')
        alt = re.sub(r'[\[\]()]', '', caption).strip()   # brackets would end the image's alt text or link early
        word = FIGURE_WORDS.get(f.get('kind'), '示意')
        said = caption if re.match(r'%s\s*[：:。]' % re.escape(word), caption) else '%s。%s' % (word, caption)
        lines += ['', '![%s](%s/evidence/%s)' % (alt, 'record', f['source'].strip()), '', '图：' + said, '']
    return lines


VERDICT_WORDS = {'PASS': '合格', 'FAIL': '不合格', 'OPEN': '未定'}


def _shown(value):
    """A margin as a reader takes it: about four significant figures, whole numbers as written."""
    if isinstance(value, float) and value != int(value):
        return '%.0f' % value if abs(value) >= 1000 else '%.4g' % value   # no exponent for a large margin
    return value


BASE_UNITS = ('s', 'F', 'A', 'V', 'W', 'H', 'Ω', 'ohm', 'J', 'C')
PREFIXES = ((1e-3, 'm'), (1e-6, 'µ'), (1e-9, 'n'), (1e-12, 'p'))


def _quantity(value, unit):
    """A margin with its unit, a value under 0.01 in a base unit carried to its prefix (R8 printed 2e-07 s, 2.1e-06 F)."""
    unit = (unit or '').strip()
    if isinstance(value, (int, float)) and not isinstance(value, bool) and unit in BASE_UNITS and 0 < abs(value) < 0.01:
        scale, prefix = next(((f, p) for f, p in PREFIXES if abs(value) >= f), PREFIXES[-1])
        scaled = round(value / scale, 9)
        return '%s %s%s' % (_shown(int(scaled) if scaled == int(scaled) else scaled), prefix, unit)
    return ('%s %s' % (_shown(value), unit)).strip()


QUESTION_REFS_MAX = 8           # a parenthesised list of more designators than this reads as a count
TRAILING_NOTE_RE = re.compile(r'（[^（）]*）\s*$')


def first_sentence(text):
    m = re.search(r'[。；;]', text)
    return text[:m.start() + 1] if m and m.start() + 1 < len(text) else text


def decisive_margins(calc):
    """The margins a reader needs: per aspect the smallest one in each unit (the one that decided), and one line per
    distinct comparison — an against that differs only by a trailing note （应力）/（用途） is the same comparison
    (R7 claude reports said 余量 136 Vac 对 CY301 Y1 400 Vac three times in one cell)."""
    smallest = {}
    for m in function_reading.margins(calc):
        key = (m.get('aspect'), (m.get('unit') or '').strip())
        if key not in smallest or (isinstance(m['value'], (int, float)) and isinstance(smallest[key]['value'], (int, float))
                                   and m['value'] < smallest[key]['value']):
            smallest[key] = m
    out, seen = [], set()
    for m in smallest.values():
        against = TRAILING_NOTE_RE.sub('', str(m.get('against') or '')).strip()
        quantity = _quantity(m['value'], m.get('unit'))
        # a comparison that only adds a trailing clause after ；is the same one (R8: Q501 120 V printed twice)
        key = (quantity, re.split(r'[；;]', against)[0].strip())
        if key not in seen:
            seen.add(key)
            out.append('余量 %s 对 %s' % (quantity, against))
    return out


def short_question(text):
    """The function's question with a long designator list shown as a count (codex1 listed 32 parts in one cell)."""
    def collapse(m):
        refs = [x for x in re.split(r'[、,，\s]+', m.group(1)) if x]
        if len(refs) > QUESTION_REFS_MAX and all(re.fullmatch(r'[A-Za-z]{1,4}\d{1,4}[A-Za-z]?', x) for x in refs):
            return '（%d 个器件）' % len(refs)
        return m.group(0)
    return re.sub(r'（([^（）]+)）', collapse, str(text or ''))


def function_basis(fn, verdict=None):
    """What the verdict rests on, in one item (user 2026-10-27: 报告太冗长): a failing function its first failure,
    an open one its first open question, a passing one its decisive margin, else the computed result's first
    sentence or why nothing was computed; the rest is in the ledger."""
    items = [i for i in fn.get({'FAIL': 'fails', 'OPEN': 'open'}.get(verdict or fn.get('verdict'), '')) or []
             if isinstance(i, dict) and text(i.get('what'))]
    calc = fn.get('calculation') if isinstance(fn.get('calculation'), dict) else {}
    said = [i['what'].strip() for i in items] or sorted(decisive_margins(calc), key=lambda m: '余量 -' not in m)
    if said:
        return said[0] + ('（另 %d 项见台账）' % (len(said) - 1) if len(said) > 1 else '')
    if calc.get('result'):
        result = str(calc['result']).strip()
        return result if len(result) <= RESULT_MAX_CHARS else first_sentence(result) + '（其余见台账）'
    return fn.get('no_calculation_reason') or ''


# 报告按功能树的顺序（功能树设计 §3.7）：系统功能，功能电路，接口；计划里没有框架的功能（审查员另建）排最后。
TREE_GROUPS = (('system', '系统功能'), ('circuit', '功能电路'), ('interface', '接口'))
OTHER_GROUP = '审查员另建的功能'
OWNER_WORDS = {'SYSTEM': '系统功能', 'CIRCUIT': '功能电路', 'INTERFACE': '接口', 'BOARD': '全板与文档'}


def function_row(fn, effective=None):
    items = [i for i in fn.get('open') or [] if isinstance(i, dict)]
    items += [i for i in fn.get('fails') or [] if isinstance(i, dict)]
    verdict, delegated = effective or (fn.get('verdict'), [])
    ids = unique([results_model.work_item_id(i['key']) for i in items if isinstance(i.get('key'), str)] + delegated)
    return '| %s | %s | %s | %s | %s |' % (
        cell(fn.get('id', '')), cell(short_question(fn.get('question'))),
        VERDICT_WORDS.get(verdict, cell(verdict or '')),
        cell(function_basis(fn, verdict)), cell('、'.join(ids)) or '—')


def render_functions(functions, plan=None, checks=None):
    """各功能的判断：一行一个功能，读者要的是“偏置：能，余量 0.8 V”；不合格和未定的列出，合格的折叠
    （2026-10-27，用户：报告太冗长、没有层次）；计划有功能树的框架时按系统功能、电路、接口分组。"""
    rows = [fn for fn in functions or [] if isinstance(fn, dict)]
    if not rows:
        return []
    head = ['| 功能 | 问题 | 结论 | 余量或依据 | 待办编号 |', '|---|---|---|---|---|']
    frames = {f['id']: f for f in (plan or {}).get('functions') or [] if isinstance(f, dict) and f.get('id')}
    effective = results_model.effective_verdicts(rows, plan, checks)
    verdict = lambda fn: (effective.get(fn.get('id')) or (fn.get('verdict'),))[0]

    def group(fn):
        frame = frames.get(fn.get('id')) or {}
        return next((label for key, label in TREE_GROUPS if frame.get(key)), OTHER_GROUP)

    def table(members, level='###'):
        grouped = any(group(fn) != OTHER_GROUP for fn in members)
        out = []
        for label in [label for _, label in TREE_GROUPS] + [OTHER_GROUP]:
            part = sorted((fn for fn in members if group(fn) == label), key=lambda fn: str(fn.get('id', '')))
            if part:
                out += ([level + ' ' + label, ''] if grouped else []) + head + \
                       [function_row(fn, effective.get(fn.get('id'))) for fn in part] + ['']
        return out

    shown = [fn for fn in rows if verdict(fn) != 'PASS']
    passed = [fn for fn in rows if verdict(fn) == 'PASS']
    out = ['## 各功能的判断', '']
    out += table(shown) if shown else ['所有功能都合格。', '']
    if passed:
        out += fold('合格的 %d 个功能' % len(passed), table(passed, '####'))
    return out + not_asked_lines(plan)


def fold(summary, lines):
    """A part the reader opens when needed: <details> in both copies of the report."""
    return ['<details>', '<summary>%s</summary>' % summary, ''] + lines + ['</details>', '']


def demote(lines):
    """A section's headings one level down, for a section shown inside the appendix."""
    return ['#' + l if re.match(r'^#{2,3} ', l) else l for l in lines]


def not_asked_lines(plan):
    """The circuit rules the plan did not ask, and why (consistency proposals of 2026-10-23, item 2)."""
    lines = []
    for frame in (plan or {}).get('functions') or []:
        items = [i for i in (frame.get('not_asked') or []) if isinstance(i, dict)] if isinstance(frame, dict) else []
        if items:
            lines.append('- %s 未问：%s' % (frame.get('id'), '、'.join(unique(str(i.get('aspect') or i.get('rule') or '') for i in items))))
    if not lines:
        return []
    # the reasons are the plan's templates (电路里没有 MOSFET 或 BJT …): they stay in review-plan.json
    return ['电路里没有它问的机制、计划没有问的电路规则（理由见计划；漏问的经 intent.rule_gaps 补回）：', ''] + lines + ['']


def gap_subclass_counts(results, gaps):
    """One count line by the kind of gap each open row's item is (results_model.GAP_SUBCLASSES); none without any."""
    items = results_model.open_items(results)
    subs = Counter(results_model.gap_subclass(items[results_model.lead_ref(items, c['open_ref'])][1]) for c in gaps
                   if c.get('open_ref') in items)
    if not any(subs.get(k) for k in results_model.GAP_SUBCLASSES):
        return []
    names = results_model.GAP_SUBCLASSES
    return ['| 资料不足细分：%s | %s |' % (' / '.join(names.values()), ' / '.join(str(subs.get(k, 0)) for k in names))]


DEFERRED_SECTION = '本次不审的范围'


def render_deferred(plan, checks):
    """What the user took out of this review (2026-10-27, user: A): deferred requirements have no checks, deferred
    checks are NA with the user's instruction. Neither is a verdict on the circuit; a later review takes them up."""
    requirements = plan.get('deferred_requirements') or []
    rows = [c for c in checks.values() if user_deferred(c)]
    if not requirements and not rows:
        return []
    out = ['## ' + DEFERRED_SECTION, '',
           '用户明确暂缓、这次没有审的内容。它们不是合格也不是不合格，下次审查时补上。', '']
    asked = {r: c for c in plan.get('clarifications') or [] if isinstance(c, dict) and c.get('decision') == 'DEFERRED'
             for r in c.get('requirement_ids') or []}
    for rid in requirements:
        c = asked.get(rid) or {}
        said = '　'.join(x for x in (c.get('text'), c.get('by'), c.get('date')) if x)
        out.append('- 需求 %s：没有生成检查项%s' % (rid, '（%s，见“需求澄清记录” %s）' % (said, c['id']) if c.get('id') else ''))
    by_instruction = OrderedDict()
    for c in sorted(rows, key=lambda c: c.get('id', '')):
        said = '；'.join(' '.join(x for x in (e.get('source'), e.get('locator')) if x) for e in c.get('instruction') or [])
        by_instruction.setdefault(said, []).append(c.get('id', '?'))
    for said, keys in by_instruction.items():
        out.append('- 用户暂缓（%s）：%d 条检查——%s' % (said, len(keys), '、'.join(keys)))
    return out + ['']


CLARIFICATION_SECTION = '需求澄清记录'
CLARIFICATION_DECISIONS = {'DECIDED': '用户给定', 'ADOPTED_PROPOSAL': '采纳 SR 建议', 'DEFERRED': '用户暂缓'}


def render_clarifications(plan):
    """The requirement questions asked of the user during the review and how each was settled (2026-10-26, user:
    需求没定，那就需要及时和用户反馈 …): a settled answer joined the requirement list and was reviewed against."""
    rows = [c for c in plan.get('clarifications') or [] if isinstance(c, dict)]
    if not rows:
        return []
    out = ['## ' + CLARIFICATION_SECTION, '',
           '审查中发现需求没说清的地方，当场问了用户；定下的写进需求清单并按它审，暂缓的这一轮不审。', '']
    for c in rows:
        out += ['### %s' % c.get('id'), '']
        source = c.get('source') or {}
        for label, value in (('需求原文', c.get('requirement_text')), ('问题', c.get('question')),
                             ('答复', '%s：%s' % (CLARIFICATION_DECISIONS.get(c.get('decision'), c.get('decision') or ''),
                                                c.get('text') or '')),
                             ('谁答复的', '　'.join(x for x in (c.get('by'), c.get('date'),
                                                             ' '.join(x for x in (source.get('source'), source.get('locator')) if x))
                                                 if x)),
                             ('涉及的需求', '、'.join(c.get('requirement_ids') or []))):
            if value:
                out.append('- **%s**：%s' % (label, value))
        out.append('')
    return out


def render_bom_constraints(checks):
    """What the BOM must state for commodity parts (commodity-floors.md): not defects, not missing data."""
    rows = bom_constraints.constraints(checks)
    if not rows:
        return []
    out = ['## BOM 要写明的额定与规格', '',
           '这些是常规器件（电阻、电容、电感、二极管）按现在的 BOM 可能买错的地方：审查已算出最低要求，'
           '设计者把它写进 BOM 即可，不是电路错误，也不是资料不足。等级按买到与 BOM 已写字段相符的最弱常规件会怎样定。', '',
           '| 位号 | 要写明的要求 | 依据 | 买错会怎样（等级） | 状态 |', '|---|---|---|---|---|']
    for _, c in rows:
        cls = c.get('consequence_class')
        word = '误选件仍在额定内，只缺降额余量' if cls == 'OPTIMIZATION' else IMPACT_CLASS_WORDS.get(cls, cls or '')
        out.append('| %s | %s | %s | %s（%s） | %s |' % (
            cell('、'.join(c.get('refs') or [])), cell(c.get('requirement') or ''), cell(c.get('basis') or ''),
            cell(word), c.get('level') or '', '已写入' if c.get('status') == 'WRITTEN' else '待写入'))
    return out + ['']


# Plan diagnostics about how the design input is written: the designer rewrites these, so they reach the report.
INPUT_NOTES = {'RESISTOR_VALUE_UNREAD': '下面这些电阻的值读不出阻值，相关的应力和脚电流没有算；'
                                        '请改成 阻值[/公差][/额定功率][/额定电压][/封装] 的写法，或确认阻值。',
               'RESISTOR_VALUE_WORD': '下面这些电阻的阻值照读，值后面的词说不清要求（如 pulse）；'
                                      '请把它说的要求写成 BOM 规格（抗脉冲能量、额定电压等）：',
               'PASSIVE_PACKAGE_UNKNOWN': '下面这些电阻电容没有封装，也没有料号或原厂资料，按最小常用封装（0402）的额定预判，'
                                          '值里写了额定的按所写（有料号或原厂资料的按资料判，不在此列）；'
                                          '定了封装或在值里写明额定后重跑：'}


def render_input_notes(plan):
    out = []
    for diagnostic in (plan or {}).get('diagnostics') or []:
        if not isinstance(diagnostic, dict) or diagnostic.get('code') not in INPUT_NOTES:
            continue
        values = diagnostic.get('values') if isinstance(diagnostic.get('values'), dict) else {}
        refs = [r for r in diagnostic.get('refs') or [] if isinstance(r, str)]
        out += [INPUT_NOTES[diagnostic['code']], ''] + ['- %s：`%s`' % (ref, value) for ref, value in sorted(values.items())]
        out += ['、'.join(refs)] if refs else []
        out += ['']
    return ['## 设计输入要改的写法', ''] + out if out else []


def finding_owners(finding, plan):
    """“所属”一行：问题涉及的检查归哪些系统功能、电路、接口或全板，按树的顺序；计划检查项没有 owner 时为 None。"""
    planned = {c.get('id'): c for c in (plan or {}).get('checks') or [] if isinstance(c, dict)}
    owners = [planned[cid]['owner'] for cid in finding.get('check_ids') or []
              if isinstance(planned.get(cid), dict) and isinstance(planned[cid].get('owner'), dict)]
    if not owners:
        return None
    order = list(OWNER_WORDS)
    keys = sorted({(o.get('kind'), o.get('id') or '') for o in owners if o.get('kind') in OWNER_WORDS},
                  key=lambda k: (order.index(k[0]), k[1]))
    return '、'.join((OWNER_WORDS[kind] + ' ' + oid).strip() for kind, oid in keys)


def render_handoffs(plan, handoffs, gate):
    """交给后续环节的要求，按负责方分组、同一要求一行（2026-10-27，用户：报告太冗长）：检查编号在台账里。"""
    if not handoffs:
        return []
    out = ['## 交给后续环节的要求', '',
           '下面这些要求在原理图上做不了，要在 PCB、热设计、测试等后续环节落实，不算原理图的错误，'
           '也不影响原理图定稿。原理图交出时把对应的表交给负责方即可。', '']
    planned = {c.get('id'): c for c in plan.get('checks') or [] if isinstance(c, dict)}
    groups = OrderedDict()
    for c in handoffs:
        groups.setdefault('、'.join(c['handoff'].get('receivers') or ['未指定']), []).append(c)
    for who, rows in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        # One row per requirement: checks that ask the same thing of different parts share a row
        # (a delivered report gave three output capacitors three rows differing only in the refdes).
        same = OrderedDict()
        for c in sorted(rows, key=lambda c: c['id']):
            h = c['handoff']
            where = unique(anchors((planned.get(c['id']) or {}).get('object')))
            key = tuple(generic(h.get(f) or '', where) for f in ('constraint', 'verification'))
            if any(k.count(REF_SLOT) > 1 for k in key):
                # a requirement naming several parts cannot be read with every one replaced by 每只
                # (R7: "每只、每只、每只/每只 表面温度"): only identical texts share a row
                key = tuple(h.get(f) or '' for f in ('constraint', 'verification'))
            same.setdefault(key, []).append((c, where))
        out += ['### %s（%d 条）' % (who, len(same)), '',
                '| 涉及位号/网络 | 要落实的要求 | 怎么验证 |', '|---|---|---|']
        for (constraint, verification), group in same.items():
            where = unique(w for _, ws in group for w in ws)
            shown = '、'.join(where[:6]) + ('等 %d 处' % len(where) if len(where) > 6 else '')
            if len(group) == 1:
                h = group[0][0]['handoff']
                constraint, verification = h.get('constraint') or '', h.get('verification') or ''
            else:
                constraint, verification = (t.replace(REF_SLOT, '每只') for t in (constraint, verification))
            out.append('| %s | %s | %s |' % (cell(shown or '整板'), cell(constraint), cell(verification)))
        out.append('')
    pending = (gate.get('stage_scope') or {}).get('requirements_pending_downstream') or []
    if pending:
        out += ['另有 %d 条需求要等样机或测试结果才能最终确认：%s。' % (len(pending), '、'.join(pending)), '']
    return out


def finding_place(f, refs_max=None):
    """Pages and parts of a finding; the conclusion's one line shows the first refs_max parts."""
    where = f.get('location') or {}
    refs = where.get('refs') or []
    shown = '、'.join(refs[:refs_max]) + ('等 %d 个' % len(refs) if refs_max and len(refs) > refs_max else '')
    return '、'.join(page_word(x) for x in where.get('pages') or []) + ('　' + shown if refs else '')


def render_finding(f, plan, item_notes, doc_defects):
    """An error card (user 2026-10-27: 报告太冗长、没有层次；问题用图说明要保留): the problem (cause, mechanism and
    the value against its limit), the consequence, the figures, the fix with its changes, and how to check it."""
    fix = f.get('remediation') or {}
    level = f.get('severity')
    owners = finding_owners(f, plan)
    meta = '　'.join(x for x in ('**%s %s**' % (level, SEVERITY_WORDS.get(level, '')),
                                 '文档错误' if f in doc_defects else '电路错误' if f.get('kind') == 'DEFECT' else '改进建议',
                                 finding_place(f), owners) if x)
    out = ['### %s　%s' % (f.get('id'), f.get('title') or ''), '', meta, '']
    if item_notes.get(f.get('id')):
        out += [item_notes[f['id']], '']
    out += ['- **问题**：%s' % f.get('root_cause', ''), '- **后果**：%s' % f.get('consequence', '')]
    out += render_figures(f.get('figures'))
    out.append('- **怎么改**：%s' % f.get('fix', ''))
    steps = [x for x in fix.get('steps') or [] if isinstance(x, dict)]
    if steps:
        out += ['', '| 改哪里 | 现在 | 改成 |', '|---|---|---|'] + [
            '| %s | %s | %s |' % (cell(x.get('target', '')), cell(x.get('before', '')), cell(x.get('after', '')))
            for x in steps] + ['']
    checks_after = ['%s（应：%s）' % (v.get('method'), v.get('expected')) if v.get('expected')
                    and not same_text(v.get('expected'), f.get('fix')) else v.get('method')
                    for v in fix.get('verification') or [] if isinstance(v, dict) and v.get('method')]
    if checks_after:
        out.append('- **怎么验证**：%s' % '；'.join(checks_after))
    return out + ['']


def task_title(task, checks, findings):
    """A work item that only corrects one listed error carries that error's title: R8 called one divider
    "CS/ZCD分压过小" as the error and "漏极取样分压过小" as its work item."""
    owners = covered_by_findings(task, checks, findings)
    finding = next((f for f in findings if len(owners) == 1 and f.get('id') == owners[0] and f.get('title')), None)
    return finding['title'] if finding else task.get('title') or task.get('root_cause') or task['id']


def covered_by_findings(task, checks, findings):
    """待办只是“改正已列出的错误”：全部检查都是 FAIL 且已归入某个问题。"""
    ids = task.get('check_ids') or []
    owned = {k: f.get('id') for f in findings for k in f.get('check_ids') or []}
    if not ids or any((checks.get(k) or {}).get('review_result') != 'FAIL' or k not in owned for k in ids):
        return []
    return unique([owned[k] for k in ids])


SR_FEEDBACK_KINDS = (('false_alarm', '误报'), ('over_strict', '规则过严或关闭条件不合理'),
                     ('missed', '漏报'), ('unclear', '说明不清或互相矛盾'),
                     ('software_bug', '已复现的程序错误'), ('coverage_gap', '自动化覆盖或格式适配不足'),
                     ('cell_boundary', '定界表某一格的边界与手册实际不符'))
EXTENSION_SIGNALS = {'NEW_DEVICE_KIND': 'SR 认不出的器件（能力不足，待补）', 'NEW_BOUND_CELL': '有类别、没有格的参数',
                     'KEYWORD_KIND_CONFLICT': '型号栏或库名与手册类型不一致（词表待修）'}


SR_TALK_RE = re.compile(r'(?<![A-Za-z])SR(?![A-Za-z])|误报|改进效果|quality_screening|提示仍|技能')
# How the record was kept (screens worked through, files, ledger modes) is not news about the board
# (a delivered summary: "已逐条复核…条记录质量提示；…条位号与数值粘连已修复…history-handling.json…first").
# The summary adds what the first line cannot: what changed and what to do first. The verdict and
# how the review was run are not news (a delivered summary: "本次使用SR…重新导出、逐页读图和复算。当前仍不能定稿…").
SUMMARY_REPEAT_RE = re.compile(r'不能定稿|可以定稿|能否定稿|重新导出|逐页读图|重新审查|本轮复核'
                               r'|\d+\s*[项条]\s*(?:检查|通过|不通过|没通过|资料不|不适用|无关)')   # 数字一览 already has the counts
RECORD_TALK_RE = re.compile(r'质量提示|自检提示|粘连|\.json(?![A-Za-z])|REQ-H0\d|(?<![A-Za-z])(?:first|revision)(?![A-Za-z])')


def notes_errors(notes):
    """notes.summary/items speak to the designer; SR's own problems go to sr_feedback."""
    errors = []
    notes = notes or {}
    texts = [('summary', notes.get('summary'))]
    texts += [('items.' + k, v) for k, v in (notes.get('items') or {}).items()] if isinstance(notes.get('items'), dict) else []
    for where, text in texts:
        if isinstance(text, str) and SR_TALK_RE.search(text):
            errors.append('%s talks about SR itself (%s); move it to sr_feedback, the designer-facing text stays about the board'
                          % (where, SR_TALK_RE.search(text).group(0)))
        elif isinstance(text, str) and RECORD_TALK_RE.search(text):
            errors.append('%s talks about keeping the review record (%s); the designer-facing text stays about the board, '
                          'the record and its screens speak for themselves' % (where, RECORD_TALK_RE.search(text).group(0)))
        elif where == 'summary' and isinstance(text, str) and SUMMARY_REPEAT_RE.search(text):
            errors.append('summary repeats the verdict, the check counts or how the review was run (%s); the first line '
                          'and 数字一览 already say those, the summary says what changed and what to do first'
                          % SUMMARY_REPEAT_RE.search(text).group(0))
    return errors


def sr_feedback_errors(items):
    """notes.sr_feedback: [{kind, rules, instance, suggestion}]，每条都要点名规则和实例。"""
    if items is None:
        return []
    if not isinstance(items, list):
        return ['sr_feedback must be a list']
    errors = []
    kinds = dict(SR_FEEDBACK_KINDS)
    for i, item in enumerate(items):
        fields = {'kind', 'rules', 'instance', 'suggestion'} | ({'cell'} if isinstance(item, dict) and item.get('kind') == 'cell_boundary' else set())
        ok = (isinstance(item, dict) and set(item) == fields
              and item.get('kind') in kinds and isinstance(item.get('rules'), list) and item['rules']
              and all(isinstance(r, str) and re.match(r'^[A-Z]{3}-[A-Z]\d{2}$', r) for r in item['rules'])
              and all(isinstance(item.get(k), str) and item[k].strip() for k in ('instance', 'suggestion'))
              and (item.get('kind') != 'cell_boundary' or item.get('cell') in catalog.BOUNDS))
        if not ok:
            errors.append('sr_feedback[%d] needs kind (%s), rule IDs, instance and suggestion; a cell_boundary item also '
                          'names its bounding-table cell' % (i, '/'.join(kinds)))
    return errors


def render_extension_signals(signals):
    """器件类别与定界表要扩的（2026-10-26 决定 0）：审查里遇到了词表没有的器件类别，或有类别却没有格的参数。只告诉 SR
    维护者要扩表，不改本板结论。"""
    out = ['### 器件类别与定界表要扩的', '',
           '下面 %d 条是这块板上 SR 的器件类别词表或定界表没有覆盖的地方；本板的结论按已知的判了，不等这些。'
           '每条都要扩 SR 自己的表（新类别进词表，新格补齐可得性、允许的估算与倍数、失效后果、样机能否验、边界）。' % len(signals), '',
           '| 类型 | 位号 | 器件类别 / 线索 | 参数或出处 | 建议 |', '|---|---|---|---|---|']
    for s in signals:
        where = s.get('function_id') or ''
        if 'margin' in s:
            where += ' 余量[%s]' % s['margin']
        elif 'open' in s:
            where += ' 开放项 %s' % s['open']
        out.append('| %s | %s | %s | %s | %s |' % (
            EXTENSION_SIGNALS[s['kind']], cell('、'.join(s.get('refs') or [])),
            cell('、'.join(s.get('device_kinds') or []) or s.get('clue') or ''),
            cell((where + '：' if where else '') + (s.get('parameter') or '')), cell(s.get('suggestion') or '')))
    out.append('')
    return out


def render_sr_feedback(items):
    """审查者对 SR 的反馈：误报、过严、漏报、说明不清，按类分组，是“对 SR 的反馈”一节的一部分。"""
    if not items or sr_feedback_errors(items):
        return []
    out = []
    for kind, label in SR_FEEDBACK_KINDS:
        rows = [i for i in items if i['kind'] == kind]
        if rows:
            out += ['### ' + label, '']
            out += ['%d. **%s**：%s 建议：%s' % (n, '、'.join(r['rules']) + ('（格 %s）' % r['cell'] if r.get('cell') else ''),
                                               cell(r['instance']), cell(r['suggestion']))
                    for n, r in enumerate(rows, 1)]
            out.append('')
    return out


def same_text(a, b):
    """改的目的只是复述标题时不再单列。"""
    norm = lambda s: re.sub(r'[\s，。；、,.;:：]', '', str(s or ''))
    return bool(a) and bool(b) and (norm(a) == norm(b) or norm(a) in norm(b))



EXPLANATION_LABELS = (('risk_if_omitted', '不查会漏掉什么'), ('closes_when', '怎样算通过'),
                      ('false_alarms', '常见误报/合法结构'))


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
           '没通过和资料不足的检查逐项给出通过标准；不适用的只写理由；其余 %d 项通过或未审结，不展开。'
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


def owner_counts(plan):
    """One count row splitting the plan's checks by owner (function tree, step 2); none for a plan without owners."""
    owners = (plan.get('summary') or {}).get('owners')
    if not isinstance(owners, list) or not owners:
        return []
    rows = Counter()
    for entry in owners:
        if isinstance(entry, dict) and isinstance(entry.get('rows'), int):
            rows[entry.get('kind')] += entry['rows']
    circuits = sum(1 for e in owners if isinstance(e, dict) and e.get('kind') == 'CIRCUIT')
    return ['| 检查按所属：系统功能 / 功能电路 / 全板与文档 | %d / %d（%d 块电路） / %d |' % (
        rows['SYSTEM'], rows['CIRCUIT'], circuits, rows['BOARD'])]


class UnfinishedReview(ValueError):
    """The review is not done: there is no report yet, only the work list in the gate."""


def render(plan, results, gate, notes=None, title=None, detail='compact'):
    results = results_model.materialize(plan, results)[0]   # the ledger holds no derived rows; the gate reports derive errors
    unfinished = results_model.unfinished_checks(results, HISTORY_RULE)
    if unfinished:
        raise UnfinishedReview('review not finished, no report yet: finish reading/computing these checks, or record '
                               'manual_verification where only the SR tool is limited: ' + ', '.join(unfinished))
    revision = (plan or {}).get('review_mode') == 'revision'
    notes = notes or {}
    item_notes = notes.get('items') or {}
    checks = {c['id']: c for c in results.get('checks') or [] if isinstance(c, dict) and 'id' in c}
    current_rows = {k: c for k, c in checks.items() if k.split('.', 1)[0] != HISTORY_RULE}
    flow = gate.get('workflow') or {}
    tasks = flow.get('work_items') or []
    task_owners = ownership(tasks)
    classes = results_model.IMPACT_CLASS_VERSION
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
    gap_ids = {k for k, c in current_rows.items() if c.get('review_result') == 'INSUFFICIENT'}
    gap_tasks = [t for t in tasks if gap_ids.intersection(t.get('check_ids') or [])]
    level_of = lambda t: task_level(t, checks, task_owners, classes)
    p0 = sum(level_of(t) == 'P0' for t in gap_tasks)
    # The first paragraph answers the reader's question in plain words: can it be frozen, what is wrong,
    # what cannot be judged yet and why. Counts of checks and record-keeping prompts stay out of it.
    circuit = defects - len(doc_defects)
    levels = [s for s in SEVERITIES if by_sev.get(s)]
    grades = ('%s，%s' % (levels[0], SEVERITY_WORDS[levels[0]]) if len(levels) == 1
              else '、'.join('%s %d 处' % (s, by_sev[s]) for s in levels))
    if circuit and doc_defects:
        found = '电路有 %d 处错误，文档有 %d 处错误（%s）' % (circuit, len(doc_defects), grades)
    elif circuit:
        found = '电路有 %d 处错误（%s）' % (circuit, grades)
    elif doc_defects:
        found = '电路没有发现错误，文档有 %d 处错误（%s）' % (len(doc_defects), grades)
    else:
        found = '电路和文档都没有发现错误'
    if defects:
        found += '，见“发现的错误”'
    sentences = [found]
    if gap_tasks:
        causes = Counter(checks[k].get('gap_cause') for t in gap_tasks for k in t.get('check_ids') or []
                         if k in gap_ids)
        why = '或'.join(OPEN_CAUSE_WORDS[c] for c in OPEN_CAUSE_WORDS if causes.get(c)) or '依据不足'
        sentences.append('另有 %d 件事因为%s，现在还判断不了%s' % (
            len(gap_tasks), why, '，其中 %d 件%s（P0）' % (p0, SEVERITY_WORDS['P0']) if p0 else ''))
    constraints = gate.get('design_constraints') or []
    if constraints:
        sentences.append('有 %d 条设计约束由 SR 算出、交给后续设计，按约束判合格，见附录“交给后续环节的要求”' % len(constraints))
    deferred_rows = sum(user_deferred(c) for c in current_rows.values())
    if plan.get('deferred_requirements') or deferred_rows:
        sentences.append('用户暂缓的 %s 这次没有审，不算结论，见“%s”' % ('、'.join(x for x in (
            '%d 条需求' % len(plan['deferred_requirements']) if plan.get('deferred_requirements') else '',
            '%d 条检查' % deferred_rows if deferred_rows else '') if x), DEFERRED_SECTION))
    risky = risk_rows(gate.get('risks'))
    if risky:
        kinds = Counter(t for e in risky for t in e.get('types') or ())
        sentences.append('有 %d 项合格但有风险（%s），不影响定稿，见附录“风险清单”' % (
            len(risky), '、'.join('%s %d' % (catalog.RISK_TYPES.get(k, k), kinds[k]) for k in catalog.RISK_TYPES if kinds.get(k))))
    out += ['**%s。** %s。' % (RELEASE.get(release, release), '。'.join(sentences)), '']
    if notes.get('summary'):
        out += [notes['summary'], '']
    by_level = lambda f: SEVERITIES.index(f['severity']) if f.get('severity') in SEVERITIES else len(SEVERITIES)
    # Within a level a gap the public bound already shows short comes first: it is the one likeliest to need a change.
    rank = lambda t: (SEVERITIES.index(level_of(t)) if level_of(t) else len(SEVERITIES),
                      t.get('subclass') != 'PUBLIC_BOUND_SHORT', -len(t.get('check_ids') or []))
    # A work item that only corrects a listed error gets no card of its own (user 2026-10-27: 报告太冗长).
    gap_cards = sorted((t for t in tasks if not covered_by_findings(t, checks, findings)), key=rank)
    if defect_list:
        out.append('**必须改：**')
        out += ['- **%s**　%s%s（%s）' % (f.get('severity'), finding_place(f, 3) + '　' if finding_place(f) else '',
                                        f.get('title') or '', f.get('id')) for f in sorted(defect_list, key=by_level)]
        out.append('')
    if gap_cards:
        out.append('**要补的资料：**')
        out += ['- **%s**　%s（%s）' % (level_of(t) or '未定级', task_title(t, checks, findings), t['id'])
                for t in gap_cards]
        out.append('')
    functions = circuit_functions(results.get('functions'), results.get('checks'))
    effective = results_model.effective_verdicts(functions, plan, results.get('checks'))
    verdicts = Counter(effective.get(f.get('id'), (f.get('verdict'),))[0] for f in functions)
    settings = gate.get('configuration_settings') or []
    numbers = '检查 %d 条，资料不足 %d 条；交给后续环节 %d 条。' % (
        (summary.get('current') or {}).get('checks', len(current_rows)), counts.get('INSUFFICIENT', 0),
        len(handoffs) + len(settings))
    if functions:
        numbers = '功能 %d 个：合格 %d，不合格 %d，未定 %d；' % (
            len(functions), verdicts.get('PASS', 0), verdicts.get('FAIL', 0), verdicts.get('OPEN', 0)) + numbers
    out += [numbers, '']
    # Errors and open items are in the first paragraph; list only the other conditions.
    reasons = (blocker_reasons(gate.get('blockers') or [], results, tasks, skip=('fail', 'gap', 'gap_tasks'))
               if release != 'GO' else [])
    if gap_ids:
        ambiguous = [t for t in gap_tasks if task_view(t, checks, task_owners, classes)['ambiguous_checks']]
        owned = {k for t in gap_tasks for k in t.get('check_ids') or []}
        if ambiguous:
            reasons.append('%d 件待办尚不能独立定级：关联检查的高风险没有消除，暂不计入已明确的根因数' % len(ambiguous))
        if gap_ids - owned:
            reasons.append('另有 %d 条资料不足的检查还没归入待办' % len(gap_ids - owned))
    if reasons:
        out.append('**定稿还差：**')
        out += ['%d. %s。' % (i, r) for i, r in enumerate(reasons, 1)]
        out.append('')
    remarks = []
    if phase == 'design_iteration':
        remarks.append('这是设计中途的检查，“还不能定稿”说的是离定稿还差上面这些，不是否定设计。'
                       if release != 'GO' else '这是设计中途的检查。')
    screen = (gate.get('quality_screening') or {}).get('candidates') or []
    if 'history_inputs' in results:
        history_inputs = [x for x in results.get('history_inputs') or [] if isinstance(x, str)]
        # The reader needs which earlier review, not where it sat on the reviewer's machine.
        seen = '、'.join('`%s`' % cell(Path(x).name or x) for x in history_inputs[:4])
        unreconciled = [c for c in screen if isinstance(c, dict) and c.get('code') == 'HISTORY_FINDINGS_UNRECONCILED']
        if history_inputs and revision and unreconciled:
            remarks.append('对照了上一版审查（%s），但它记录的 %d 个问题（%s）还没有逐条写明已改、保留还是撤回。' % (
                seen, sum(len(c.get('finding_ids') or []) for c in unreconciled),
                '、'.join(fid for c in unreconciled for fid in (c.get('finding_ids') or [])[:6])))
        elif history_inputs and revision:
            remarks.append('上一版审查（%s）的问题已逐条复验，其余结论按现在的图纸和资料重新判断。' % seen)
        elif history_inputs:
            remarks.append('审查时看过上一版审查（%s），但结论都按现在的图纸和资料重新判断；上一版的问题没有逐条对照列出。' % seen)
    if remarks:
        out += [''.join(remarks), '']

    if findings:
        out += ['## 发现的错误', '', SEVERITY_LEGEND, '']
        for f in sorted(findings, key=by_level):
            out += render_finding(f, plan, item_notes, doc_defects)

    if gap_cards:
        out += ['## 待办', '']
        if not findings:
            out += [SEVERITY_LEGEND, '']
        for task in gap_cards:
            out += render_item(task, checks, item_notes, task_owners, classes)

    out += render_deferred(plan, current_rows)
    out += render_clarifications(plan)
    out += render_functions(functions, plan, results.get('checks'))

    # 附录：设计者要用、但不必先读的部分，各自折叠（2026-10-27，用户：报告太冗长、没有层次）
    appendix = []
    for section in (render_bom_constraints(checks), render_handoffs(plan, handoffs, gate),
                    render_configuration_settings(settings), render_risks(gate.get('risks')),
                    render_input_notes(plan), render_parameter_sheet(gate.get('parameter_sheet'), detail) if detail == 'full' else []):
        if section:
            appendix += fold(section[0].lstrip('# '), demote(section[2:]))
    gaps = [c for c in current_rows.values() if c.get('review_result') == 'INSUFFICIENT']
    pot = Counter(c.get('potential_severity') for c in gaps)
    classes = Counter((c.get('impact_assessment') or {}).get('consequence_class') for c in gaps
                      if isinstance(c.get('impact_assessment'), dict)
                      and c['impact_assessment'].get('consequence_class') in IMPACT_CLASS_WORDS)
    history = (summary.get('history') or {}).get('checks', 0)
    history_cell = str(history)
    if not history and any(isinstance(x, str) for x in results.get('history_inputs') or []):
        history_cell = '0（已声明上一版材料，但没有逐条复验检查项）' if revision else '0（首审不逐条登记）'
    counts_block = ['| 项目 | 数量 |', '|---|---|',
            '| 功能判定 合格 / 不合格 / 未定 | %d / %d / %d |' % (verdicts.get('PASS', 0), verdicts.get('FAIL', 0), verdicts.get('OPEN', 0)),
            '| 检查总数 | %d |' % (summary.get('current') or {}).get('checks', len(current_rows)),
            ] + owner_counts(plan) + [
            '| 合格 / 不合格 / 资料不足无法判断 | %d / %d / %d |' % (counts.get('PASS', 0), counts.get('FAIL', 0), counts.get('INSUFFICIENT', 0)),
            '| 与本产品无关（NA） | %d |' % counts.get('NA', 0),
            '| 原理图阶段不判、交给后续环节 | %d |' % counts.get('NA_OUTSIDE_STAGE', 0),
            ] + (['| 用户暂缓、本次不审（见“本次不审的范围”） | %d 条需求，%d 条检查 |' % (
                len(plan.get('deferred_requirements') or []), counts.get('NA_DEFERRED', 0))]
                 if plan.get('deferred_requirements') or counts.get('NA_DEFERRED') else []) + [
            '| 发现的错误，按严重程度 P0 / P1 / P2 / P3 | %s |' % ' / '.join(str(by_sev.get(s, 0)) for s in SEVERITIES),
            '| 其中文档错误 | %d |' % len(doc_defects),
            '| 待办（同一原因合并） | %d 件 |' % len(tasks),
            '| 资料不足的检查，可能的严重程度 P0 / P1 / P2 / P3 | %s |' % ' / '.join(str(pot.get(s, 0)) for s in SEVERITIES),
            ] + gap_subclass_counts(results, gaps) + (['| 资料不足的可能后果：%s | %s |' % (' / '.join(IMPACT_CLASS_WORDS.values()),
                                                  ' / '.join(str(classes.get(k, 0)) for k in IMPACT_CLASS_WORDS))]
                 if classes else []) + [
            '| 交给后续环节的要求 | %d |' % (len(handoffs) + len(settings))] + (
            ['| 合格但有风险（不影响定稿，见“风险清单”） | %d 项 |' % len(risky)] if risky else []) + [
            '| 审查记录自检提示（不计入结论，分类见“对 SR 的反馈”） | %d |' % len(screen),
            '| 上一版问题的处理记录（不计入上面各行） | %s |' % history_cell, '']
    appendix += fold(COUNTS_TITLE, counts_block)
    if appendix:
        out += ['## 附录', ''] + appendix
    # Everything about SR itself in one folded section, for its maintainers, at the end.
    sr = []
    signals = [t for t in gate.get('sr_improvements') or [] if isinstance(t, dict) and t.get('kind') in EXTENSION_SIGNALS]
    tool_gaps = [t for t in gate.get('sr_improvements') or [] if isinstance(t, dict) and t not in signals]
    if signals:
        sr += render_extension_signals(signals)
    if tool_gaps:
        sr += ['### 工具判断不了、已逐项手工核对的检查', '',
               '下面 %d 条检查，SR 的自动检查工具判断不了，审查时改为逐项对照网表和原厂资料核对，结论按核对结果算。'
               % len(tool_gaps), '']
        same = OrderedDict()
        for t in tool_gaps:
            key = tuple(cell(t.get(f) or '') for f in ('tool_limitation', 'sr_improvement', 'method', 'reviewer_kind'))
            key += ('、'.join(cell(g) for g in t.get('tool_gaps') or []),)
            same.setdefault(key, []).append(t['check_id'])
        for (limit, improve, method, reviewer, gaps), ids in same.items():
            sr += ['#### ' + '、'.join(ids), '']
            if gaps:
                sr.append('- **工具缺口**：' + gaps)
            sr += ['- **SR 为什么做不到**：' + limit,
                   '- **建议怎么改进 SR**：' + improve,
                   '- **这次怎么核对的**：' + ({'AI': 'AI 核对：', 'HUMAN': '人员核对：'}.get(reviewer, '')) + method, '']
    gaps = gate.get('rule_gaps') or []
    if gaps:   # fixed requirements, step 7: each gap goes to the improvement ledger and becomes a rule the tool writes
        sr += ['### 审查员补加的检查（规则缺口）', '',
               '下面 %d 条检查计划里原本没有，由审查员登记为规则缺口后补加，照常判过；每条记进改进台账，变成工具生成的规则。'
               % len(gaps), '', '| 检查 | 缺什么规则 | 依据 | 结论 |', '|---|---|---|---|']
        sr += ['| %s | %s | %s | %s |' % (cell(g.get('check_id') or ''), cell(g.get('missing') or ''),
                                          cell(g.get('basis') or ''), cell(g.get('result') or '未判')) for g in gaps]
        sr.append('')
    sr += render_sr_feedback(notes.get('sr_feedback'))
    if screen:
        sr += ['### 审查记录自检提示', '',
               '%d 条，只要求复核写法和依据，不改变结论：%s。明细在 record/review-gate.json 的 quality_screening。' % (
                   len(screen), '、'.join('%s %d' % kv for kv in
                                         Counter(c.get('code') for c in screen if isinstance(c, dict)).most_common())), '']
    if sr:
        out += [SR_SECTION, '', '<details>', '<summary>展开（给 SR 维护者）</summary>', ''] + sr + ['</details>', '']

    explanations = render_check_explanations(plan, results) if detail == 'full' else []
    if explanations:
        out += ['<details>', '<summary>展开逐项依据与通过标准（完整保留）</summary>', ''] + explanations + ['</details>', '']
    out += ['## 索引', '', '| 内容 | 文件 |', '|---|---|'] + [
        '| %s | [%s](record/%s) |' % (what, name, name) for name, what in RECORD_INDEX] + ['']
    return '\n'.join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('plan')
    parser.add_argument('results')
    parser.add_argument('gate')
    parser.add_argument('--notes')
    parser.add_argument('--detail', choices=('compact', 'full'), default='compact',
                        help='compact: tasks and linked ledger (default); full: also expand every non-pass check')
    parser.add_argument('--title')
    parser.add_argument('-o', '--out', required=True)
    args = parser.parse_args(argv)
    load = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
    notes = load(args.notes) if args.notes else None
    problems = sr_feedback_errors((notes or {}).get('sr_feedback')) + notes_errors(notes)
    if problems:
        print('notes.json: ' + '; '.join(problems), file=sys.stderr)
        return 2
    try:
        text = render(load(args.plan), load(args.results), load(args.gate), notes, args.title, args.detail)
    except UnfinishedReview as e:
        print(e, file=sys.stderr)
        return 2
    Path(args.out).write_text(text, encoding='utf-8')
    html_out = Path(args.out).with_suffix('.html')
    html_out.write_text(to_html(text), encoding='utf-8')
    print('wrote', args.out, 'and', html_out)
    return 0


if __name__ == '__main__':
    sys.exit(main())

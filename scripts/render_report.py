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
import function_reading
from review_functions import circuit_functions
from task_scope import ownership, task_view
from report_html import to_html

TOP_TASKS = 3
SR_SECTION = '## 对 SR 的反馈（设计者不用处理）'
RECORD_INDEX = (('review-results.json', '每条检查的结论、依据、缺的资料和修改条件'),
                ('review-plan.json', '检查计划：全部检查项和覆盖范围'),
                ('review-gate.json', '校验结果：各项计数、定稿条件和自检提示明细'),
                ('db.json', '从原理图导出的网表数据'),
                ('intent.json', '审查依据：需求、电源轨、装配和器件声明'),
                ('lint-cold.json', '自动检查输出（只用网表）'),
                ('lint-hot.json', '自动检查输出（加上器件资料）'),
                ('evidence/', '引用的资料摘录、计算和图片'))
OPEN_CAUSE_WORDS = OrderedDict([('EXTERNAL_DATA', '缺资料'), ('DESIGN_OPEN', '设计还没定'),
                                ('DELIVERABLE_PENDING', '等交付物'),
                                ('REQUIREMENT_OPEN', '需求还没定'), ('REVIEW_INCOMPLETE', '审查还没做完'),
                                ('USER_DEFERRED', '暂缓处理')])
RELEASE = {'GO': '可以定稿', 'CONDITIONAL_GO': '可以有条件定稿', 'NO_GO': '还不能定稿'}
CAUSES = OrderedDict([('EXTERNAL_DATA', '缺资料'), ('DESIGN_OPEN', '设计没定'), ('DELIVERABLE_PENDING', '等交付物'),
                      ('REQUIREMENT_OPEN', '需求没定'), ('REVIEW_INCOMPLETE', '审查没做完'),
                      ('USER_DEFERRED', '已暂缓')])
KINDS = OrderedDict([('FAIL', '电路错误'), ('REQUIREMENT_OPEN', '需求没定'), ('DESIGN_OPEN', '设计没定'),
                     ('EXTERNAL_DATA', '缺资料'), ('DELIVERABLE_PENDING', '等交付物'), ('REVIEW_INCOMPLETE', '审查没做完'),
                     ('USER_DEFERRED', '已暂缓')])
SEVERITIES = ('P0', 'P1', 'P2', 'P3')
SEVERITY_WORDS = {'P0': '可能损坏器件或危及安全', 'P1': '必需功能可能不达标',
                  'P2': '局部或次要问题', 'P3': '可选优化'}
SEVERITY_LEGEND = '严重程度：P0 可能损坏器件或危及安全；P1 必需功能可能不达标；P2 局部或次要问题；P3 可选优化。'
HISTORY_RULE = 'REQ-H02'
RESULT_SHORT = {'PASS': '通过', 'FAIL': '没通过', 'INSUFFICIENT': '资料不足', 'NA': '无关',
                'NA_OUTSIDE_STAGE': '交给后续环节'}
# Why the schematic cannot be finalised yet, in the order a reader should act on them.
BLOCKERS = (('fail', '%d 条检查发现的错误还没改'),
            ('gap', '%d 条检查缺资料或设计依据，对应下面列出的待办'),
            ('gap_tasks', '%d 件待办阻塞定稿（同一原因合并，涉及 %d 条缺资料或设计依据的阻塞检查；不阻塞的待办不计在内）'),
            ('requirement', '%d 条需求还要用户拍板'),
            ('review', '%d 条检查审查还没做完'),
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
JARGON = ('冻结', '闸门', '原生', '下游', '移交', '接收方', '闭合', '绑定', '本行', '证据不足', '技能',
          'remediation', 'handoff', 'fit')
CHECK_ID_RE = re.compile(r'\b[A-Z]{3}-[A-Z]\d{2}(?:\.[A-Za-z0-9_~-]+)+')


def cell(text):
    return str(text).replace('|', '\\|').replace('\n', ' ').strip()


def worst(levels):
    found = [s for s in SEVERITIES if s in levels]
    return found[0] if found else None


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
    """FAIL and open requirements name the item; otherwise the gap cause most of its checks carry,
    with the minority cause shown so one DESIGN_OPEN row cannot relabel thirteen data gaps."""
    kinds = Counter(r.get('review_result') if r.get('review_result') == 'FAIL' else r.get('gap_cause') for r in rows)
    for key in ('FAIL', 'REQUIREMENT_OPEN'):
        if kinds.get(key):
            if key == 'FAIL' and is_document([r.get('id', '') for r in rows if r.get('review_result') == 'FAIL']):
                return '文档错误'
            return KINDS[key]
    causes = [(n, list(KINDS).index(k)) for k, n in kinds.items() if k in KINDS]
    if not causes:
        return '待处理'
    ranked = sorted(((k, n) for k, n in kinds.items() if k in KINDS), key=lambda kn: (-kn[1], list(KINDS).index(kn[0])))
    label = KINDS[ranked[0][0]]
    if len(ranked) > 1:
        label += '（另 %s）' % '、'.join('%s %d 条' % (KINDS[k], n) for k, n in ranked[1:])
    return label


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


SHARED_REASON_MIN_TASKS = 3
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


def render_item(task, checks, notes, owners=None, classes=False, shared_reasons=()):
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
    meta = '类型：%s　可能后果：%s　涉及 %d 条检查%s' % (
        '%s（%s）' % (kind, sub) if sub and kind != KINDS['FAIL'] and sub != kind else kind,
        ('%s（%s）' % (SEVERITY_WORDS[level], level)) if level else '未定级', len(rows), breakdown)
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
    reason = (task.get('reason') or '').strip()
    # Old records sometimes put the scope in the impact field verbatim.
    # Remove only that exact duplicate, never infer equivalence from similarity.
    if reason in scopes or reason in ['本任务只关闭：' + scope for scope in scopes] or reason in shared_reasons:
        reason = ''
    root = (task.get('root_cause') or '').strip()
    if reason and root and (restates(reason, root) or restates(root, reason)):
        reason = ''   # "why it matters" that only re-says the gap
    missing = unique([root])
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
    fields = [('缺什么', missing),
              ('为什么要紧', [reason]),
              ('按什么假定判的', [task.get('assumed')]),
              ('公开资料界限下的最坏情况', [task.get('worst_case')]),
              ('这个缺口影响哪些判断', task.get('blocks') or []),
              ('已查过', read),
              ('还要做', todo),
              ('怎样算通过', criteria)]
    option = task.get('design_option') or {}
    if option.get('status') == 'PROPOSED':
        fields.append(('建议的电路改法', [option.get('summary')]))
    for label, values in fields:
        values = unique(values)
        if values:
            # Repeated requests share one line; every distinct acceptance stays visible.
            lines.append('- **%s**：%s' % (label, join_statements(values)))
    if notes.get(task['id']):
        lines.append('- **审查员补充**：%s' % notes[task['id']])
    if option.get('status') == 'PROPOSED':
        lines += render_figures(option.get('figures'))
    lines.append('')
    return lines


FIGURE_WORDS = {'ACTUAL': '现状', 'REFERENCE': '原厂参考', 'AFTER': '改后', 'MECHANISM': '失效过程'}


def render_figures(figures):
    """Each figure as an image packed under record/evidence, with its kind and caption below it."""
    lines = []
    for f in figures if isinstance(figures, list) else []:
        if not (isinstance(f, dict) and isinstance(f.get('source'), str) and f['source'].strip()):
            continue
        caption = cell(f.get('caption') or '')
        alt = re.sub(r'[\[\]()]', '', caption).strip()   # brackets would end the image's alt text or link early
        lines += ['', '![%s](%s/evidence/%s)' % (alt, 'record', f['source'].strip()),
                  '', '图：%s。%s' % (FIGURE_WORDS.get(f.get('kind'), '示意'), caption), '']
    return lines


VERDICT_WORDS = {'PASS': '通过', 'FAIL': '没通过', 'OPEN': '未定'}


def _shown(value):
    """A margin as a reader takes it: about four significant figures, whole numbers as written."""
    if isinstance(value, float) and value != int(value):
        return '%.0f' % value if abs(value) >= 1000 else '%.4g' % value   # no exponent for a large margin
    return value


def function_basis(fn):
    """What the verdict rests on: the computed result and its margin, else why nothing was computed."""
    calc = fn.get('calculation') if isinstance(fn.get('calculation'), dict) else {}
    parts = [calc.get('result')] if calc.get('result') else []
    for margin in function_reading.margins(calc):   # one margin written per aspect is stated once
        parts.append('余量 %s 对 %s' % (('%s %s' % (_shown(margin['value']), margin.get('unit') or '')).strip(),
                                       margin.get('against') or ''))
    parts = unique(parts)
    if not parts and fn.get('no_calculation_reason'):
        parts.append(fn['no_calculation_reason'])
    return '；'.join(parts)


# 报告按功能树的顺序（功能树设计 §3.7）：系统功能，功能电路，接口；计划里没有框架的功能（审查员另建）排最后。
TREE_GROUPS = (('system', '系统功能'), ('circuit', '功能电路'), ('interface', '接口'))
OTHER_GROUP = '审查员另建的功能'
OWNER_WORDS = {'SYSTEM': '系统功能', 'CIRCUIT': '功能电路', 'INTERFACE': '接口', 'BOARD': '全板与文档'}


def function_row(fn, effective=None):
    items = [i for i in fn.get('open') or [] if isinstance(i, dict) and i.get('kind') != 'REQUIREMENT']
    items += [i for i in fn.get('fails') or [] if isinstance(i, dict)]
    verdict, delegated = effective or (fn.get('verdict'), [])
    ids = unique([results_model.work_item_id(i['key']) for i in items if isinstance(i.get('key'), str)] + delegated)
    return '| %s | %s | %s | %s | %s |' % (
        cell(fn.get('id', '')), cell(fn.get('question') or ''),
        VERDICT_WORDS.get(verdict, cell(verdict or '')),
        cell(function_basis(fn)), cell('、'.join(ids)) or '—')


def render_functions(functions, plan=None, checks=None):
    """各功能的判断：一行一个功能，读者要的是“偏置：能，余量 0.8 V”；计划有功能树的框架时按系统功能、电路、接口分节。"""
    rows = [fn for fn in functions or [] if isinstance(fn, dict)]
    if not rows:
        return []
    head = ['| 功能 | 问题 | 结论 | 余量或依据 | 待办编号 |', '|---|---|---|---|---|']
    frames = {f['id']: f for f in (plan or {}).get('functions') or [] if isinstance(f, dict) and f.get('id')}
    effective = results_model.effective_verdicts(rows, plan, checks)

    def group(fn):
        frame = frames.get(fn.get('id')) or {}
        return next((label for key, label in TREE_GROUPS if frame.get(key)), OTHER_GROUP)

    if not any(group(fn) != OTHER_GROUP for fn in rows):
        return (['## 各功能的判断', ''] + head + [function_row(fn, effective.get(fn.get('id'))) for fn in rows] + ['']
                + not_asked_lines(plan))
    out = ['## 各功能的判断', '']
    for label in [label for _, label in TREE_GROUPS] + [OTHER_GROUP]:
        members = sorted((fn for fn in rows if group(fn) == label), key=lambda fn: str(fn.get('id', '')))
        if members:
            out += ['### ' + label, ''] + head + [function_row(fn, effective.get(fn.get('id'))) for fn in members] + ['']
    return out + not_asked_lines(plan)


def not_asked_lines(plan):
    """The circuit rules the plan did not ask, and why (consistency proposals of 2026-10-23, item 2)."""
    lines = []
    for frame in (plan or {}).get('functions') or []:
        items = [i for i in (frame.get('not_asked') or []) if isinstance(i, dict)] if isinstance(frame, dict) else []
        if items:
            lines.append('- %s 未问：%s' % (frame.get('id'), '；'.join(
                '%s（%s）' % (i.get('aspect') or i.get('rule'), i.get('why') or '') for i in items)))
    if not lines:
        return []
    return ['电路里没有它问的机制、计划没有问的电路规则（漏问的经 intent.rule_gaps 补回）：', ''] + lines + ['']


def gap_subclass_counts(results, gaps):
    """One count line by the kind of gap each open row's item is (results_model.GAP_SUBCLASSES); none without any."""
    items = results_model.open_items(results)
    subs = Counter(results_model.gap_subclass(items[results_model.lead_ref(items, c['open_ref'])][1]) for c in gaps
                   if c.get('open_ref') in items)
    if not any(subs.get(k) for k in results_model.GAP_SUBCLASSES):
        return []
    names = results_model.GAP_SUBCLASSES
    return ['| 资料不足细分：%s | %s |' % (' / '.join(names.values()), ' / '.join(str(subs.get(k, 0)) for k in names))]


CLARIFICATION_SECTION = '需求要说清楚的地方'
CLARIFICATION_KINDS = {'MISSING': '需求没写', 'AMBIGUOUS': '需求写得含糊', 'CONFLICTING': '需求前后矛盾',
                       'UNCONFIRMED': '需求还没确认'}
DECISION_DUE = {'BEFORE_DESIGN': '设计前定', 'BEFORE_FREEZE': '定稿前定', 'FOLLOW_UP': '后续确认'}


def render_clarifications(results):
    """Open requirement clarifications, one block each: what the requirement says, what to decide and add, who
    decides and by when (SR self-check 2.5, user: 单列一节)."""
    rows = [c for c in results.get('requirement_clarifications') or [] if isinstance(c, dict) and c.get('status') == 'OPEN']
    if not rows:
        return []
    out = ['## ' + CLARIFICATION_SECTION, '',
           '下面这些地方需求没有说清楚，审查判断不了，要需求负责方拍板并改进需求文件；不是原理图的错误。', '']
    for c in rows:
        blocks = '不定下来不能定稿' if c.get('freeze_impact') == 'BLOCKING' else '不影响定稿（各种可能都已核过）'
        out += ['### %s　%s' % (c.get('id'), c.get('title') or ''), '',
                '类型：%s　%s　%s　涉及 %d 条检查' % (CLARIFICATION_KINDS.get(c.get('kind'), c.get('kind') or ''),
                                              DECISION_DUE.get(c.get('decision_due'), c.get('decision_due') or ''),
                                              blocks, len(c.get('check_ids') or [])), '']
        for label, value in (('需求原文', c.get('requirement_text')), ('问题', c.get('question')),
                             ('要定什么', c.get('decision_needed')), ('建议写进需求', c.get('proposed_requirement')),
                             ('谁来定', c.get('owner')), ('为什么要紧', c.get('impact_reason')),
                             ('怎样算定了', c.get('closure_criteria')),
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
    """“所属”一行：问题涉及的检查归哪些系统功能、电路、接口或全板，按树的顺序；计划行没有 owner 时为 None。"""
    planned = {c.get('id'): c for c in (plan or {}).get('checks') or [] if isinstance(c, dict)}
    owners = [planned[cid]['owner'] for cid in finding.get('check_ids') or []
              if isinstance(planned.get(cid), dict) and isinstance(planned[cid].get('owner'), dict)]
    if not owners:
        return None
    order = list(OWNER_WORDS)
    keys = sorted({(o.get('kind'), o.get('id') or '') for o in owners if o.get('kind') in OWNER_WORDS},
                  key=lambda k: (order.index(k[0]), k[1]))
    return '、'.join((OWNER_WORDS[kind] + ' ' + oid).strip() for kind, oid in keys)


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


SR_TALK_RE = re.compile(r'(?<![A-Za-z])SR(?![A-Za-z])|误报|改进效果|quality_screening|提示仍|技能')
# How the record was kept (screens worked through, files, ledger modes) is not news about the board
# (a delivered summary: "已逐条复核…条记录质量提示；…条位号与数值粘连已修复…history-handling.json…first").
# The summary adds what the first line cannot: what changed and what to do first. The verdict and
# how the review was run are not news (a delivered summary: "本次使用SR…重新导出、逐页读图和复算。当前仍不能定稿…").
SUMMARY_REPEAT_RE = re.compile(r'不能定稿|可以定稿|能否定稿|重新导出|逐页读图|重新审查|本轮复核')
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
            errors.append('summary repeats the verdict or describes how the review was run (%s); the first line already '
                          'says whether it can be frozen, the summary says what changed and what to do first'
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
        ok = (isinstance(item, dict) and set(item) == {'kind', 'rules', 'instance', 'suggestion'}
              and item.get('kind') in kinds and isinstance(item.get('rules'), list) and item['rules']
              and all(isinstance(r, str) and re.match(r'^[A-Z]{3}-[A-Z]\d{2}$', r) for r in item['rules'])
              and all(isinstance(item.get(k), str) and item[k].strip() for k in ('instance', 'suggestion')))
        if not ok:
            errors.append('sr_feedback[%d] needs kind (%s), rule IDs, instance and suggestion'
                          % (i, '/'.join(kinds)))
    return errors


def render_sr_feedback(items):
    """审查者对 SR 的反馈：误报、过严、漏报、说明不清，按类分组，是“对 SR 的反馈”一节的一部分。"""
    if not items or sr_feedback_errors(items):
        return []
    out = []
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


def render(plan, results, gate, notes=None, title=None, detail='compact'):
    results = results_model.expand(results)
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
    counts_at = len(out)   # 数字一览 goes here, ahead of the conclusion, once its numbers are known
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
    out += ['**%s。** %s。' % (RELEASE.get(release, release), '。'.join(sentences)), '']
    if notes.get('summary'):
        out += [notes['summary'], '']
    if tasks:
        ordered = sorted(tasks, key=lambda t: (SEVERITIES.index(level_of(t)) if level_of(t) else len(SEVERITIES),
                                               -len(t.get('check_ids') or [])))
        top = ordered[:TOP_TASKS]
        out.append('**最先要解决的%s：**' % (' %d 件事' % len(top) if len(top) > 1 else '一件事'))
        for i, t in enumerate(top, 1):
            level = level_of(t)
            kind = item_kind([checks[k] for k in t.get('check_ids') or [] if k in checks]).split('（')[0]
            out.append('%d. %s（%s%s；待办 %s）' % (i, t.get('title') or t.get('root_cause') or t['id'],
                                                  level + '，' if level else '', kind, t['id']))
        fixes = sum(bool(covered_by_findings(t, checks, findings)) for t in tasks)
        out.append('')
        if len(tasks) > TOP_TASKS:
            out += ['全部 %d 件待办见“待办”一节%s。' % (
                len(tasks), '，其中 %d 件是改正上面列出的错误' % fixes if fixes else ''), '']
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

    functions = circuit_functions(results.get('functions'), results.get('checks'))
    out += render_functions(functions, plan, results.get('checks'))

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
            place = '、'.join(('第%s页' % x) for x in where.get('pages') or []) + \
                ('　' + '、'.join(where.get('refs') or []) if where.get('refs') else '')
            if place:
                out.append('- **位置**：%s' % place)
            owners = finding_owners(f, plan)
            if owners:
                out.append('- **所属**：%s' % owners)
            out += render_figures(f.get('figures'))
            harm = f.get('impact')
            if f.get('scenario') and not restates(f['scenario'], harm or '') and not restates(harm or '', f['scenario']):
                harm = join_statements([harm, f['scenario']])
            for label, value in (('根因', f.get('root_cause')),
                                 ('问题', f.get('observed')), ('可能的损害', harm),
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

    out += render_clarifications(results)

    if tasks:
        out += ['## 待办', '']
        if not findings:
            out += [SEVERITY_LEGEND, '']
        # Within a level a gap the public bound already shows short comes first: it is the one likeliest to need a change.
        rank = lambda t: (SEVERITIES.index(task_level(t, checks, task_owners, classes)) if task_level(t, checks, task_owners, classes) else len(SEVERITIES),
                          t.get('subclass') != 'PUBLIC_BOUND_SHORT', -len(t.get('check_ids') or []))
        # One reason sentence on many work items says nothing about any of them (a delivered report: 15 of 18).
        reason_count = Counter(t['reason'].strip() for t in tasks if isinstance(t.get('reason'), str))
        shared_reasons = {r for r, n in reason_count.items() if n >= SHARED_REASON_MIN_TASKS}
        for task in sorted(tasks, key=rank):
            if task.get('kind') == 'REQUIREMENT_CLARIFICATION':
                out += ['### %s　%s' % (task['id'], task.get('title') or ''), '',
                        '见上文“%s”，这里不重复。' % CLARIFICATION_SECTION, '']
                continue
            owners = covered_by_findings(task, checks, findings)
            if owners:
                out += ['### %s　%s' % (task['id'], task.get('title') or task.get('root_cause') or ''), '',
                        '按上文“发现的错误”中问题 %s 的改法处理，这里不重复。' % '、'.join(owners), '']
                continue
            out += render_item(task, checks, item_notes, task_owners, classes, shared_reasons)

    out += render_bom_constraints(checks)
    out += render_input_notes(plan)

    if handoffs:
        out += ['## 交给后续环节的要求', '',
                '下面这些要求在原理图上做不了，要在 PCB、热设计、测试等后续环节落实，不算原理图的错误，'
                '也不影响原理图定稿。原理图交出时把这张表一起交给对应负责方即可。', '',
                '| 负责方 | 检查 | 涉及位号/网络 | 要落实的要求 | 怎么验证 |', '|---|---|---|---|---|']
        planned = {c.get('id'): c for c in plan.get('checks') or [] if isinstance(c, dict)}
        groups = OrderedDict()
        for c in handoffs:
            groups.setdefault('、'.join(c['handoff'].get('receivers') or ['未指定']), []).append(c)
        # One row per requirement: checks that ask the same thing of different parts share a row
        # (a delivered report gave three output capacitors three rows differing only in the refdes).
        for who, rows in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            same = OrderedDict()
            for c in sorted(rows, key=lambda c: c['id']):
                h = c['handoff']
                where = unique(anchors((planned.get(c['id']) or {}).get('object')))
                key = tuple(generic(h.get(f) or '', where) for f in ('constraint', 'verification'))
                same.setdefault(key, []).append((c, where))
            for (constraint, verification), group in same.items():
                ids = [c['id'] for c, _ in group]
                where = unique(w for _, ws in group for w in ws)
                shown = '、'.join(where[:6]) + ('等 %d 处' % len(where) if len(where) > 6 else '')
                if len(group) == 1:
                    h = group[0][0]['handoff']
                    constraint, verification = h.get('constraint') or '', h.get('verification') or ''
                else:
                    constraint, verification = (t.replace(REF_SLOT, '每只') for t in (constraint, verification))
                out.append('| %s | %s | %s | %s | %s |' % (cell(who), cell('、'.join(ids)), cell(shown or '整板'),
                           cell(constraint), cell(verification)))
        pending = (gate.get('stage_scope') or {}).get('requirements_pending_downstream') or []
        if pending:
            out += ['', '另有 %d 条需求要等样机或测试结果才能最终确认：%s。' % (len(pending), '、'.join(pending))]
        out.append('')

    # Everything about SR itself in one folded section, for its maintainers.
    sr = []
    tool_gaps = gate.get('sr_improvements') or []
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

    gaps = [c for c in current_rows.values() if c.get('review_result') == 'INSUFFICIENT']
    pot = Counter(c.get('potential_severity') for c in gaps)
    cause = Counter(c.get('gap_cause') for c in gaps)
    classes = Counter((c.get('impact_assessment') or {}).get('consequence_class') for c in gaps
                      if isinstance(c.get('impact_assessment'), dict)
                      and c['impact_assessment'].get('consequence_class') in IMPACT_CLASS_WORDS)
    history = (summary.get('history') or {}).get('checks', 0)
    history_cell = str(history)
    if not history and any(isinstance(x, str) for x in results.get('history_inputs') or []):
        history_cell = '0（已声明上一版材料，但没有逐条复验行）' if revision else '0（首审不逐条登记）'
    effective = results_model.effective_verdicts(functions, plan, results.get('checks'))
    verdicts = Counter(effective.get(f.get('id'), (f.get('verdict'),))[0] for f in functions)
    counts_block = ['## 数字一览', '', '| 项目 | 数量 |', '|---|---|',
            '| 功能判定 通过 / 没通过 / 未定 | %d / %d / %d |' % (verdicts.get('PASS', 0), verdicts.get('FAIL', 0), verdicts.get('OPEN', 0)),
            '| 检查总数 | %d |' % (summary.get('current') or {}).get('checks', len(current_rows)),
            ] + owner_counts(plan) + [
            '| 通过 / 没通过 / 资料不足无法判断 | %d / %d / %d |' % (counts.get('PASS', 0), counts.get('FAIL', 0), counts.get('INSUFFICIENT', 0)),
            '| 与本产品无关（NA） | %d |' % counts.get('NA', 0),
            '| 原理图阶段不判、交给后续环节 | %d |' % counts.get('NA_OUTSIDE_STAGE', 0),
            '| 发现的错误，按严重程度 P0 / P1 / P2 / P3 | %s |' % ' / '.join(str(by_sev.get(s, 0)) for s in SEVERITIES),
            '| 其中文档错误 | %d |' % len(doc_defects),
            '| 待办（同一原因合并） | %d 件 |' % len(tasks),
            '| 资料不足的检查，可能的严重程度 P0 / P1 / P2 / P3 | %s |' % ' / '.join(str(pot.get(s, 0)) for s in SEVERITIES),
            '| 资料不足的原因：%s | %s |' % (' / '.join(CAUSES.values()), ' / '.join(str(cause.get(k, 0)) for k in CAUSES)),
            ] + gap_subclass_counts(results, gaps) + (['| 资料不足的可能后果：%s | %s |' % (' / '.join(IMPACT_CLASS_WORDS.values()),
                                                  ' / '.join(str(classes.get(k, 0)) for k in IMPACT_CLASS_WORDS))]
                 if classes else []) + [
            '| 交给后续环节的要求 | %d |' % len(handoffs),
            '| 审查记录自检提示（不计入结论，分类见“对 SR 的反馈”） | %d |' % len(screen),
            '| 上一版问题的处理记录（不计入上面各行） | %s |' % history_cell, '']
    out[counts_at:counts_at] = counts_block
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
    text = render(load(args.plan), load(args.results), load(args.gate), notes, args.title, args.detail)
    Path(args.out).write_text(text, encoding='utf-8')
    html_out = Path(args.out).with_suffix('.html')
    html_out.write_text(to_html(text), encoding='utf-8')
    print('wrote', args.out, 'and', html_out)
    return 0


if __name__ == '__main__':
    sys.exit(main())

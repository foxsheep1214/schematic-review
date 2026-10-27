"""Requirement clarifications: asked of the user at once, answered into the requirement list (2026-10-26).

A requirement that is missing, vague or conflicting where a judgement depends on it is not carried to the report as
an undecided requirement (user: 需求没定，那就需要及时和用户反馈，请用户澄清以后，马上修改需求清单，而不是放到最后).
The reviewer writes the question into `intent.clarifications` and asks the user; an unattended run reads the task
book's clarification answers. The answer is one of three (user: a 只允许采纳建议或明确暂缓):

- DECIDED: the user states the requirement;
- ADOPTED_PROPOSAL: the user adopts SR's proposed clause;
- DEFERRED: the user defers the requirement; the requirements it names are DEFERRED and their checks are not judged.

A DECIDED or ADOPTED_PROPOSAL answer is a requirement in its own right: its id joins the requirement list with the
answer's words as its original text, and the intent states what the reviewer reads from it like any other. A question
without an answer stops the review at step ①: the candidate generator, the planner with candidates, the gate and
the packer refuse it (user: b 无人值守时任务书附澄清答复，没覆盖的问题停在第①步).
"""
import re

import requirements_extract

ID_RE = re.compile(r'^CL-[A-Za-z0-9]+(?:[-_.][A-Za-z0-9]+)*$')
DECISIONS = ('DECIDED', 'ADOPTED_PROPOSAL', 'DEFERRED')
SECTION = '需求澄清'


def text(value):
    return isinstance(value, str) and bool(value.strip())


def rows(intent):
    value = intent.get('clarifications') if isinstance(intent, dict) else None
    return [c for c in value if isinstance(c, dict)] if isinstance(value, list) else []


def answer_of(row):
    answer = row.get('answer')
    return answer if isinstance(answer, dict) else None


def decides(row):
    """The answer makes a requirement (DECIDED or ADOPTED_PROPOSAL)."""
    answer = answer_of(row)
    return bool(answer) and answer.get('decision') in ('DECIDED', 'ADOPTED_PROPOSAL')


def requirement_items(intent):
    """Answered clarifications as requirement-document items: the answer's words are the requirement's original text,
    located at the answer's source."""
    out = []
    for row in rows(intent):
        if decides(row) and text(row.get('id')) and text(answer_of(row).get('text')):
            source = answer_of(row).get('source') or {}
            out.append({'id': row['id'], 'section': SECTION,
                        'columns': [{'name': 'text', 'text': answer_of(row)['text']}],
                        'locator': '%s %s' % (source.get('source', ''), source.get('locator', '')),
                        'clarification': row['id']})
    return out


def load(intent):
    """(extraction, errors) of intent.requirement_source with the answered clarifications appended as requirements."""
    source, errors = requirements_extract.load((intent or {}).get('requirement_source'))
    extra = requirement_items(intent)
    if not extra:
        return source, errors
    out = dict(source or {'items': []})
    out['items'] = list(out.get('items') or []) + extra
    return out, errors


def pending(intent):
    """Ids of clarifications the user has not answered."""
    return [row.get('id') for row in rows(intent) if answer_of(row) is None]


def pending_errors(intent):
    return ['需求澄清 %s 还没答复：审查停在第①步。把问题交给用户（无人值守时查任务书的澄清答复），'
            '用户给定、采纳建议或明确暂缓后写进 answer，再往下做' % cid for cid in pending(intent)]


def errors(intent, document_ids):
    """Shape of intent.clarifications against the requirement document ids and intent.requirements."""
    if not isinstance(intent, dict) or 'clarifications' not in intent:
        return []
    if not isinstance(intent['clarifications'], list):
        return ['clarifications 须为数组']
    out = []
    statuses = {r.get('id'): r.get('status', 'CONFIRMED') for r in intent.get('requirements') or [] if isinstance(r, dict)}
    seen = set()
    for row in intent['clarifications']:
        if not isinstance(row, dict) or not text(row.get('id')):
            out.append('clarifications[] 须为带 id 的 object')
            continue
        cid = row['id']
        label = 'clarifications.' + cid
        if not ID_RE.match(cid):
            out.append(label + ': id 写成 CL-<名字>（如 CL-SURGE）')
        if cid in seen or cid in document_ids:
            out.append(label + ': id 重复（与另一条澄清或需求文档里的编号相同）')
        seen.add(cid)
        for field in ('question', 'requirement_text', 'proposed_requirement'):
            if not text(row.get(field)):
                out.append(label + '.%s 缺失（question 写判断卡在哪里，requirement_text 引需求原文和位置或写“未提及”及查过的章节，'
                                   'proposed_requirement 写建议补进需求的条文）' % field)
        refs = row.get('requirement_ids')
        if not isinstance(refs, list) or not all(text(x) for x in refs):
            out.append(label + '.requirement_ids 须为需求编号数组（需求文档没提到时写 []）')
            refs = []
        for rid in refs:
            if rid not in document_ids:
                out.append(label + '.requirement_ids: %s 不在需求文档里' % rid)
        for field in sorted(set(row) - {'id', 'question', 'requirement_text', 'proposed_requirement', 'requirement_ids', 'answer'}):
            out.append(label + '.%s 不是澄清的字段' % field)
        if 'answer' not in row:
            continue
        answer = answer_of(row)
        if answer is None:
            out.append(label + '.answer 须为 object')
            continue
        decision = answer.get('decision')
        if decision not in DECISIONS:
            out.append(label + '.answer.decision 须为 DECIDED（用户给定）/ADOPTED_PROPOSAL（采纳建议）/DEFERRED（明确暂缓）')
            continue
        for field in ('text', 'by', 'date'):
            if not text(answer.get(field)):
                out.append(label + '.answer.%s 缺失（text 写用户定下的需求或暂缓的原话，by 写答复人，date 写日期）' % field)
        source = answer.get('source')
        if not isinstance(source, dict) or not text(source.get('source')) or not text(source.get('locator')):
            out.append(label + '.answer.source 须为 {source, locator}：对话记录或任务书澄清答复里能定位的一处')
        if decision == 'ADOPTED_PROPOSAL' and answer.get('text') != row.get('proposed_requirement'):
            out.append(label + '.answer.text 采纳建议时与 proposed_requirement 一字不差')
        if decision == 'DEFERRED':
            if not refs:
                out.append(label + ': 暂缓要点名暂缓的需求（requirement_ids）')
            for rid in refs:
                if statuses.get(rid) != 'DEFERRED':
                    out.append(label + ': 用户暂缓了 %s，intent.requirements 里它的 status 写 DEFERRED' % rid)
            if cid in statuses:
                out.append(label + ': 暂缓的澄清不成为需求，intent.requirements 不写 %s' % cid)
        elif cid not in statuses:
            out.append(label + ': 答复定下了需求，intent.requirements 加一项 %s（类别、理解、参数、承接电路）' % cid)
        elif statuses[cid] != 'CONFIRMED':
            out.append(label + ': 答复定下的需求 %s 已确认，status 写 CONFIRMED' % cid)
    return out


def records(intent):
    """Answered clarifications for the plan and the report: what was asked, how it was settled, by whom."""
    out = []
    for row in rows(intent):
        answer = answer_of(row)
        if answer is None:
            continue
        out.append({'id': row.get('id'), 'requirement_ids': list(row.get('requirement_ids') or []),
                    'question': row.get('question'), 'requirement_text': row.get('requirement_text'),
                    'decision': answer.get('decision'), 'text': answer.get('text'),
                    'by': answer.get('by'), 'date': answer.get('date'), 'source': answer.get('source')})
    return out

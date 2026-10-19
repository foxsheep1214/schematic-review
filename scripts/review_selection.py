#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""独立复核 ASG 的核心器件选型记录与审查意见归因。

ASG 交付的 record/selection.json 写了每个核心器件角色的决定性条件、候选和选中/淘汰依据；
record/review-responses.json 和 record/lessons.json 写了上一轮每条意见为什么没被技能自己拦住（归因）。
SR 不迁移这些结论：先用 worksheet 生成空白复核表，审查者逐角色独立给结论，再用 validate 校验
复核表是否完整、不同意时有没有给出 ASG 候选之外的型号或 ASG 淘汰理由里的具体错误。

    python3 review_selection.py worksheet <ASG交付目录或record目录> --out selection-review.json
    python3 review_selection.py validate selection-review.json --asg <ASG交付目录或record目录>
"""
import argparse
import json
import re
import sys
from pathlib import Path

VERDICTS = ('AGREE', 'DISAGREE', 'INSUFFICIENT')
CAUSES = ('rule_missing', 'rule_not_enforced', 'knowledge_missing', 'knowledge_wrong', 'judgment', 'none')
PAGE = re.compile(r'(p\.?\s?\d+|第\s?\d+\s?页|§\s?\S+)')


def text(v):
    return isinstance(v, str) and bool(v.strip())


def record_dir(path):
    path = Path(path)
    return path if path.name == 'record' else path / 'record'


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def worksheet(asg):
    rec = record_dir(asg)
    selection = load(rec / 'selection.json')
    roles = []
    for r in selection.get('roles') or []:
        cands = [c for c in r.get('candidates') or [] if isinstance(c, dict)]
        chosen = next((c.get('mpn') for c in cands if c.get('status') == 'selected'), None)
        roles.append({
            'role': r.get('role'), 'refs': r.get('refs') or [], 'asg_selected': chosen,
            'asg_decisive': [{k: d.get(k) for k in ('param', 'op', 'limit', 'unit') if k in d} for d in r.get('decisive') or [] if isinstance(d, dict)],
            'asg_candidates': [{'mpn': c.get('mpn'), 'status': c.get('status'), 'reject_kind': c.get('reject_kind')} for c in cands],
            'verdict': None, 'conditions_complete': None, 'missing_condition': '',
            'alternative_mpn': '', 'asg_error': '', 'basis': '', 'pages': ''})
    attribution = []
    responses_path = rec / 'review-responses.json'
    if responses_path.is_file():
        for item in load(responses_path).get('items') or []:
            if isinstance(item, dict) and text(item.get('id')):
                attribution.append({'id': item['id'], 'comment': item.get('comment'), 'asg_cause': item.get('cause'),
                                    'agree': None, 'cause': '', 'reason': ''})
    return {'schema_version': 1, 'asg_record': str(rec), 'roles': roles, 'attribution': attribution}


def validate(review, asg):
    rec = record_dir(asg)
    selection = load(rec / 'selection.json')
    errors = []
    if not isinstance(review, dict) or review.get('schema_version') != 1:
        return ['selection-review.json 必须是 schema_version 1 的对象']
    by_role = {r.get('role'): r for r in review.get('roles') or [] if isinstance(r, dict)}
    for r in selection.get('roles') or []:
        name = r.get('role')
        cands = {c.get('mpn') for c in r.get('candidates') or [] if isinstance(c, dict)}
        chosen = next((c.get('mpn') for c in r.get('candidates') or [] if isinstance(c, dict) and c.get('status') == 'selected'), None)
        entry = by_role.get(name)
        if entry is None:
            errors.append('角色“%s”没有复核结论' % name)
            continue
        verdict = entry.get('verdict')
        if verdict not in VERDICTS:
            errors.append('角色“%s”的 verdict 必须是 %s 之一' % (name, '/'.join(VERDICTS)))
            continue
        if entry.get('conditions_complete') not in (True, False):
            errors.append('角色“%s”要先判 ASG 的决定性条件是否完整（conditions_complete）' % name)
        elif entry.get('conditions_complete') is False and not text(entry.get('missing_condition')):
            errors.append('角色“%s”判决定性条件不完整，要写出缺的条件（missing_condition）' % name)
        if verdict == 'INSUFFICIENT':
            if not text(entry.get('basis')):
                errors.append('角色“%s”判 INSUFFICIENT 要写缺什么证据（basis）' % name)
            continue
        if not (text(entry.get('basis')) and PAGE.search(entry.get('basis', '') + ' ' + str(entry.get('pages') or ''))):
            errors.append('角色“%s”的结论要有依据和页码（basis/pages）' % name)
        if verdict == 'DISAGREE':
            alt, err = entry.get('alternative_mpn'), entry.get('asg_error')
            if text(alt):
                if alt == chosen:
                    errors.append('角色“%s”不同意却给出 ASG 已选定的 %s' % (name, alt))
            elif text(err):
                if not any(c and c in err for c in cands):
                    errors.append('角色“%s”的 asg_error 要点名 ASG 候选里的哪个型号被错误淘汰或错误选中' % name)
            else:
                errors.append('角色“%s”不同意时要给 ASG 候选之外的型号（alternative_mpn）或指出 ASG 淘汰理由的错误（asg_error）' % name)
    responses_path = rec / 'review-responses.json'
    items = {i.get('id'): i for i in (load(responses_path).get('items') or []) if isinstance(i, dict)} if responses_path.is_file() else {}
    by_id = {a.get('id'): a for a in review.get('attribution') or [] if isinstance(a, dict)}
    for key, item in items.items():
        if item.get('cause') is None:
            continue
        a = by_id.get(key)
        if a is None:
            errors.append('意见 %s 的归因没有复核' % key)
            continue
        if a.get('agree') not in (True, False):
            errors.append('意见 %s：agree 要写 true/false' % key)
        elif a.get('agree') is False:
            if a.get('cause') not in CAUSES or a.get('cause') == item.get('cause'):
                errors.append('意见 %s：不同意 ASG 的归因 %s 时要给出另一类归因（%s）' % (key, item.get('cause'), '/'.join(CAUSES)))
            if not text(a.get('reason')):
                errors.append('意见 %s：不同意归因要写理由' % key)
    return errors


def summary(review):
    roles = [r for r in review.get('roles') or [] if isinstance(r, dict)]
    counts = {v: sum(1 for r in roles if r.get('verdict') == v) for v in VERDICTS}
    attribution = [a for a in review.get('attribution') or [] if isinstance(a, dict)]
    disagreed = [a for a in attribution if a.get('agree') is False]
    lines = ['选型复核：%d 个角色，同意 %d、不同意 %d、证据不足 %d。' % (len(roles), counts['AGREE'], counts['DISAGREE'], counts['INSUFFICIENT'])]
    for r in roles:
        if r.get('verdict') == 'DISAGREE':
            lines.append('- %s：ASG 选 %s；%s' % (r.get('role'), r.get('asg_selected'),
                         ('改选 ' + r['alternative_mpn']) if text(r.get('alternative_mpn')) else ('淘汰理由有误：' + str(r.get('asg_error')))))
        if r.get('conditions_complete') is False:
            lines.append('- %s：决定性条件缺 %s' % (r.get('role'), r.get('missing_condition')))
    if attribution:
        lines.append('归因复核：%d 条意见，不同意 %d 条。' % (len(attribution), len(disagreed)))
        for a in disagreed:
            lines.append('- %s：ASG 归因 %s，应为 %s（%s）' % (a.get('id'), a.get('asg_cause'), a.get('cause'), a.get('reason')))
    return '\n'.join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    w = sub.add_parser('worksheet')
    w.add_argument('asg')
    w.add_argument('--out', type=Path, required=True)
    v = sub.add_parser('validate')
    v.add_argument('review', type=Path)
    v.add_argument('--asg', required=True)
    args = ap.parse_args(argv)
    if args.cmd == 'worksheet':
        args.out.write_text(json.dumps(worksheet(args.asg), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('wrote', args.out)
        return 0
    review = load(args.review)
    errors = validate(review, args.asg)
    for e in errors:
        print('ERROR:', e)
    print(summary(review) if not errors else 'FAIL')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())

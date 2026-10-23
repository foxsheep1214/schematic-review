#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""规则合同：每条自动规则一块必触发的最小合成板 + 一块不得触发的近似板。

    python3 evals/rule_contracts/contracts.py            逐条运行并打印结果，失败退出 1
    python3 evals/rule_contracts/contracts.py --gaps     列出缺合同的自动规则

合同文件 boards/<规则>.json：
    rule       规则编号
    runner     cold = 冷跑 Lint，看 FINDING/CANDIDATE（INFO 不算触发；近似板还要求本规则未被跳过）
               plan = 计划，触发板须有 APPLICABLE 计划项，近似板须没有（T、V 规则，E 规则的对象）
               rule_plan = 同上，但看计划的规则级 rule_plan 行（改版闭环 REQ-H01 只在这一层）
    trigger / near_miss   板：parts=[{ref, value, pins:[[脚号, 脚名, 网络]], nc?}]，
               可选 pintype、pseudo_nets、native_pintype、intent（bound=true 时套共享装配绑定）、
               log、ref2page、old（旧版板，计划按它另建旧计划，用于改版规则）
    note       两块板差在哪
    always     全板规则每块板都生成计划项、没有近似板时写明原因，near_miss 为 null
方式 C/D/Q 由审查者判定，不在代码合同范围内（OUT_OF_SCOPE_METHODS）。
"""
import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BOARDS = Path(__file__).resolve().parent / 'boards'
for extra in (ROOT / 'scripts', ROOT / 'scripts' / 'tests'):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import catalog  # noqa: E402

AUTOMATED_METHODS = 'AETVH'
OUT_OF_SCOPE_METHODS = 'CDQ'


def automated_rules():
    return [r.id for r in catalog.RULES if catalog.method_of(r.id) in AUTOMATED_METHODS]


def load_contracts():
    return {p.stem: json.loads(p.read_text(encoding='utf-8')) for p in sorted(BOARDS.glob('*.json'))}


def build_db(board):
    db = {'nets': {}, 'parts': {}, 'pin2net': {}, 'pinname': {}, 'pintype': dict(board.get('pintype', {})),
          'ref2page': {}, 'pseudo_nets': list(board.get('pseudo_nets', []))}
    for key in ('native_pintype', 'device_kinds', 'declared_pinname', 'ref2page'):
        if key in board:
            db[key] = copy.deepcopy(board[key])
    for part in board['parts']:
        ref, value = part['ref'], part['value']
        db['parts'][ref] = {'part': part.get('part', value), 'value': value, 'prim': part.get('prim', value),
                            'jedec': part.get('jedec', 'X'), 'nc': part.get('nc', False)}
        for pin, name, net in part.get('pins', []):
            node = ref + '.' + pin
            if net is not None:
                db['nets'].setdefault(net, []).append(node)
                db['pin2net'][node] = net
            if name:
                db['pinname'][node] = name
    return db


def build_intent(board, db):
    intent = copy.deepcopy(board.get('intent') or {})
    if intent.pop('bound', False):
        from electrical_fixtures import bound_intent
        intent = bound_intent(db, intent)
    return intent


def _rule_skipped(lint, rule):
    return any(entry[0] == rule for entry in lint.skipped)


def observe(rule, runner, board):
    """返回 (fired, executed, detail)。"""
    from lint import Lint
    db = build_db(board)
    intent = build_intent(board, db)
    if runner == 'cold':
        lint = Lint(db, board.get('log'), intent)
        hits = [f for f in lint.run() if f['rule'] == rule and f['kind'] in ('FINDING', 'CANDIDATE')]
        return bool(hits), not _rule_skipped(lint, rule), [f['detail'] for f in hits]
    if runner in ('plan', 'rule_plan'):
        from plan_review import build_review_plan
        kwargs = {}
        if 'old' in board:
            old_db = build_db(board['old'])
            kwargs.update(old_db=old_db, old_db_available=True,
                          old_plan=build_review_plan(old_db, build_intent(board['old'], old_db)))
        plan = build_review_plan(db, intent, **kwargs)
        rows = plan['checks'] if runner == 'plan' else plan['rule_plan']
        items = [c.get('id', c['rule']) for c in rows if c['rule'] == rule and c['applicability'] == 'APPLICABLE']
        return bool(items), True, items
    raise ValueError('unknown runner: %s' % runner)


def check_contract(contract):
    """返回错误列表；空表示合同成立。"""
    rule, runner = contract['rule'], contract['runner']
    errors = []
    fired, _, detail = observe(rule, runner, contract['trigger'])
    if not fired:
        errors.append('%s trigger board did not fire (%s)' % (rule, detail))
    if contract['near_miss'] is None:
        if not contract.get('always'):
            errors.append('%s has no near-miss board and no always reason' % rule)
        return errors
    fired, executed, detail = observe(rule, runner, contract['near_miss'])
    if fired:
        errors.append('%s near-miss board fired: %s' % (rule, detail))
    elif not executed:
        errors.append('%s near-miss board did not execute the rule (%s)' % (rule, detail))
    return errors


def gaps(contracts=None):
    contracts = load_contracts() if contracts is None else contracts
    return [rule for rule in automated_rules() if rule not in contracts]


def main():
    parser = argparse.ArgumentParser(description='运行规则合同（触发板/近似板）')
    parser.add_argument('--gaps', action='store_true', help='只列出缺合同的自动规则')
    parser.add_argument('rules', nargs='*', help='只跑这些规则')
    args = parser.parse_args()
    contracts = load_contracts()
    missing = gaps(contracts)
    if args.gaps:
        print('\n'.join(missing) or 'none')
        return 1 if missing else 0
    failed = 0
    for rule, contract in contracts.items():
        if args.rules and rule not in args.rules:
            continue
        errors = check_contract(contract)
        failed += bool(errors)
        print(('FAIL ' + '; '.join(errors)) if errors else 'ok   ' + rule)
    if missing:
        print('missing contracts: ' + ' '.join(missing))
    return 1 if failed or missing else 0


if __name__ == '__main__':
    sys.exit(main())

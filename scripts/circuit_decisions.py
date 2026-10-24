#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""审查员对电路候选的决定生成 intent.circuits；电路不再手画。

`intent.circuit_decisions` 每条对一个候选（或一组候选）做四种决定之一，外加一种补充：
- accept：原样接受，可给名称 `id`，可按手册模式名加工作态（`states_add` + 定位引用）；
- merge：几个候选合成一个功能（引用一条把它们描述成一个流程的条款）；电路候选不与跨电路候选合并；
- split：把一个候选拆成几部分（每部分成员是该候选成员的子集，所有成员都要有去处）；
- reject：不审这个候选（OUTSIDE_SCOPE / NOT_A_CIRCUIT / DUPLICATE_OF <电路>），成员进 REQ-Q08 复核；
- add：生成器没找到的功能（UNRESOLVED_CANDIDATE）：只能收没有任何候选持有的器件，每颗写它所在的网；
- own：同一级认领打平的器件（候选文件的 shared，或决定后两块电路打平）归哪一块电路，写 `ref`、`candidate` 和定位引用。
器件最多属于两个电路（核心器件与端点不计）。
每颗被电路持有的器件恰好由一块电路拥有（`owned`），其余持有它的电路只引用它：归属按 `circuit_candidates.claim_rank`
在决定后保留的电路之间判定，拒绝或合并之后由下一个认领者拥有；打平的由 own 决定裁定。
intent.circuits 若手写，必须与决定推出的电路逐个相等（类型、成员集合、工作态、候选编号）。
"""
import argparse
import json
import sys

import catalog
from circuit_candidates import SCHEMA_VERSION, best_claims, claim_rank
from electrical_contract import LOCATOR_IDS_RE, LOCATOR_WORDS_RE, db_fingerprint, load_json

DECISIONS = ('accept', 'merge', 'split', 'reject', 'add', 'own')
REJECT_REASONS = ('OUTSIDE_SCOPE', 'NOT_A_CIRCUIT', 'DUPLICATE_OF')
NET_KEYS_SKIPPED = ('pin', 'sense_pins', 'pd_controllers')
IDENTITY_ROLES = ('anchor', 'endpoint', 'connector', 'pd_controller')   # a circuit's identity, not a shared part


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def located(citation):
    return _text(citation) and bool(LOCATOR_WORDS_RE.search(citation) or LOCATOR_IDS_RE.search(citation))


def _nets(candidate):
    return sorted({v for k, v in (candidate.get('nets') or {}).items() if k not in NET_KEYS_SKIPPED and _text(v)})


def _circuit(cid, ctype, refs, nets, states, citation, candidate_ids, cross_cutting, anchors=(), claims=None):
    """A derived circuit; `claims` {ref: rank} decides ownership once every decision is read (`owned` is filled then)."""
    return {'id': cid, 'type': ctype, 'refs': sorted(set(refs)), 'nets': sorted(set(nets)), 'states': list(states),
            'citation': citation, 'candidate_ids': list(candidate_ids), 'cross_cutting': bool(cross_cutting),
            'anchors': sorted(set(anchors) & set(refs)), '_claims': dict(claims or {})}


def _claims(candidate, refs=None):
    return {m['ref']: claim_rank(candidate, m) for m in candidate['members'] if refs is None or m['ref'] in refs}


def _file_ownership_errors(by_id):
    """The candidate file's owned flags are the claim rule's: one owner per part, none for a tie."""
    if any('owned' not in m for c in by_id.values() for m in c['members']):
        return [f'circuit-candidates.json has no ownership (schema_version {SCHEMA_VERSION}); regenerate it with circuit_candidates.py']
    errors = []
    flagged = {}
    for cid, cand in by_id.items():
        for m in cand['members']:
            if m['owned']:
                flagged.setdefault(m['ref'], []).append(cid)
    for ref, cids in sorted(flagged.items()):
        if len(cids) > 1:
            errors.append(f'{ref} is owned by two candidates ({", ".join(sorted(cids))}) in circuit-candidates.json; regenerate it')
    winners = best_claims({cid: list(_claims(c).items()) for cid, c in by_id.items()})
    for ref, cids in sorted(winners.items()):
        want = cids if len(cids) == 1 else []
        if sorted(flagged.get(ref, [])) != want and len(flagged.get(ref, [])) <= 1:
            errors.append(f'{ref}: owned flags in circuit-candidates.json differ from the claim rule ({want or "a tie"}); regenerate it')
    return errors


def _anchors(members):
    return [ref for ref, m in members.items() if m.get('role') in IDENTITY_ROLES]


def derive(candidates, decisions):
    """(circuits, errors): the circuits the decisions produce, in decision order; errors leave a circuit out."""
    by_id = {c['id']: c for c in candidates.get('candidates', [])}
    members = {cid: {m['ref']: m for m in c['members']} for cid, c in by_id.items()}
    held = {ref for c in by_id.values() for ref in members[c['id']]}
    decided, circuits, errors, owns = {}, [], _file_ownership_errors(by_id), []
    if not isinstance(decisions, list):
        return [], ['circuit_decisions must be a list']
    for index, decision in enumerate(decisions):
        if not isinstance(decision, dict) or decision.get('decision') not in DECISIONS:
            errors.append(f'circuit_decisions[{index}]: decision must be one of {"/".join(DECISIONS)}')
            continue
        kind = decision['decision']
        if kind == 'own':
            owns.append(decision)
            continue
        targets = decision.get('candidate')
        targets = targets if isinstance(targets, list) else ([targets] if targets is not None else [])
        if kind != 'add':
            unknown = [t for t in targets if t not in by_id]
            if unknown or not targets:
                errors.append(f'circuit_decisions[{index}]: unknown candidate {unknown or "(none)"}')
                continue
            for t in targets:
                if t in decided:
                    errors.append(f'two decisions for candidate {t}')
                decided[t] = kind
        if kind == 'accept':
            cand = by_id[targets[0]]
            cid = decision.get('id') or cand['id']
            states = list(cand['states'])
            extra = decision.get('states_add') or []
            if extra and not located(decision.get('citation')):
                errors.append(f'{cid}: states_add {extra} needs a citation a reader can open (page, table, section, record id)')
            states += [s for s in extra if s not in states]
            circuits.append(_circuit(cid, cand['type'], members[cand['id']], _nets(cand), states,
                                     decision.get('citation') or f'candidate:{cand["id"]}', [cand['id']], cand['cross_cutting'],
                                     _anchors(members[cand['id']]), _claims(cand)))
        elif kind == 'merge':
            cands = [by_id[t] for t in targets]
            cid = decision.get('id')
            if not _text(cid):
                errors.append(f'circuit_decisions[{index}]: merge needs an id')
                cid = '+'.join(targets)
            if not located(decision.get('citation')):
                errors.append(f'{cid}: merge needs a citation a reader can open that describes the candidates as one function')
            if len({c['cross_cutting'] for c in cands}) > 1:
                errors.append(f'{cid}: a circuit candidate does not merge with a cross-cutting one ({", ".join(targets)})')
            refs, states, nets, claims = [], [], [], {}
            for c in cands:
                refs += list(members[c['id']])
                nets += _nets(c)
                states += [s for s in c['states'] if s not in states]
                for ref, rank in _claims(c).items():
                    claims[ref] = min(rank, claims.get(ref, rank))
            circuits.append(_circuit(cid, cands[0]['type'], refs, nets, states, decision.get('citation') or '',
                                     targets, all(c['cross_cutting'] for c in cands),
                                     [a for c in cands for a in _anchors(members[c['id']])], claims))
        elif kind == 'split':
            cand = by_id[targets[0]]
            parts = decision.get('into') or []
            if not isinstance(parts, list) or len(parts) < 2:
                errors.append(f'{cand["id"]}: split needs at least two parts in `into`')
                continue
            if not located(decision.get('citation')):
                errors.append(f'{cand["id"]}: split needs a citation a reader can open')
            placed = []
            for part in parts:
                refs = part.get('members') if isinstance(part, dict) else None
                pid = (part.get('id') if isinstance(part, dict) else None) or f'{cand["id"]}/{len(placed)}'
                if not isinstance(refs, list) or not refs:
                    errors.append(f'{pid}: split part needs members')
                    continue
                foreign = [r for r in refs if r not in members[cand['id']]]
                if foreign:
                    errors.append(f'{pid}: split members {foreign} are not members of {cand["id"]}')
                again = [r for r in refs if r in placed]
                if again:
                    errors.append(f'{pid}: split members {again} placed twice')
                placed += refs
                kept = [r for r in refs if r in members[cand['id']]]
                circuits.append(_circuit(pid, cand['type'], kept, _nets(cand),
                                         cand['states'], decision.get('citation') or '', [cand['id']], cand['cross_cutting'],
                                         _anchors(members[cand['id']]), _claims(cand, kept)))
            left = sorted(set(members[cand['id']]) - set(placed))
            if left:
                errors.append(f'{cand["id"]}: split leaves members {left} unplaced; every member goes to a part')
        elif kind == 'reject':
            cand = by_id[targets[0]]
            reason = decision.get('reason')
            if reason not in REJECT_REASONS:
                errors.append(f'{cand["id"]}: reject reason must be one of {"/".join(REJECT_REASONS)}')
            if not located(decision.get('citation')):
                errors.append(f'{cand["id"]}: reject needs a citation a reader can open')
            if reason == 'DUPLICATE_OF':
                other = decision.get('of')
                target = next((c for c in circuits if c['id'] == other), None)
                if target is None:
                    errors.append(f'{cand["id"]}: DUPLICATE_OF names {other!r}, which no earlier decision produced')
                else:
                    outside = sorted(set(members[cand['id']]) - set(target['refs']))
                    if outside:
                        errors.append(f'{cand["id"]}: DUPLICATE_OF {other} but {outside} are not in it')
        elif kind == 'add':
            cid = decision.get('id')
            if not _text(cid) or decision.get('type') not in catalog.CIRCUIT_TYPE_BY_NAME:
                errors.append(f'circuit_decisions[{index}]: add needs an id and a catalog circuit type')
                continue
            refs = decision.get('members') if isinstance(decision.get('members'), list) else []
            via = decision.get('via') if isinstance(decision.get('via'), dict) else {}
            if not refs:
                errors.append(f'{cid}: add needs members')
            for ref in refs:
                owner = next((k for k, m in members.items() if ref in m), None)
                if owner:
                    errors.append(f'{cid}: {ref} is held by candidate {owner}; split or merge instead of add')
                nets = candidates.get('unassigned_nets', {}).get(ref) or _unassigned_nets(candidates, ref)
                if not _text(via.get(ref)) or not any(net in via[ref] for net in nets):
                    errors.append(f'{cid}: add member {ref} needs a via naming a net it sits on ({", ".join(nets) or "none known"})')
            if not located(decision.get('citation')):
                errors.append(f'{cid}: add needs a citation a reader can open')
            states = decision.get('states') or list(catalog.CANDIDATE_STATES.get(decision['type'], ()))
            circuits.append(_circuit(cid, decision['type'], refs, [], states, decision.get('citation') or '', [], False,
                                     claims={ref: 1 for ref in refs}))
    for cid in by_id:
        if cid not in decided:
            errors.append(f'candidate {cid} has no decision (accept, merge, split or reject)')
    seen = {}
    for circuit in circuits:
        if circuit['id'] in seen:
            errors.append(f'circuit id {circuit["id"]} produced twice')
        seen[circuit['id']] = circuit
    owners = {}
    for circuit in circuits:
        for ref in circuit['refs']:
            if ref not in circuit['anchors']:       # an anchor or endpoint is the circuit's identity, not a shared part
                owners.setdefault(ref, []).append(circuit)
    for ref, holders in sorted(owners.items()):
        if len(holders) > 2:
            errors.append(f'{ref} belongs to {len(holders)} circuits ({", ".join(c["id"] for c in holders)}); at most two')
    errors += _assign_owners(circuits, owns)
    return circuits, errors


def _assign_owners(circuits, owns):
    """Fill each circuit's `owned`: the best claim among the circuits the decisions kept; a tie is settled by an own
    decision naming a candidate of one of the tied circuits, with a citation a reader can open."""
    errors = []
    winners = best_claims({i: list(c['_claims'].items()) for i, c in enumerate(circuits)})
    by_ref = {}
    for decision in owns:
        by_ref.setdefault(decision.get('ref'), []).append(decision)
    for ref, settling in sorted(by_ref.items(), key=lambda kv: str(kv[0])):
        tied = winners.get(ref, [])
        if len(tied) < 2:
            holder = ', '.join(circuits[i]['id'] for i in tied) or 'no circuit'
            errors.append(f'own {ref}: {ref} has an owner ({holder}); an own decision only settles a tie')
            continue
        if len(settling) > 1:
            errors.append(f'own {ref}: two own decisions for {ref}; one part has one owner')
            continue
        decision = settling[0]
        if not located(decision.get('citation')):
            errors.append(f'own {ref}: needs a citation a reader can open (page, table, section, record id)')
        chosen = [i for i in tied if decision.get('candidate') in circuits[i]['candidate_ids']]
        if not chosen:
            errors.append(f'own {ref}: candidate {decision.get("candidate")} is not one of the tied circuits '
                          f'({", ".join(circuits[i]["id"] for i in tied)})')
            continue
        winners[ref] = chosen
    for ref, tied in sorted(winners.items()):
        if len(tied) > 1:
            errors.append(f'{ref} is claimed equally by {", ".join(circuits[i]["id"] for i in tied)}; write an own decision '
                          '{decision: own, ref, candidate, citation} naming the circuit that owns it')
    for i, circuit in enumerate(circuits):
        circuit['owned'] = sorted(ref for ref, tied in winners.items() if tied == [i])
        del circuit['_claims']
    return errors


def _unassigned_nets(candidates, ref):
    for item in candidates.get('unassigned', []):
        if item['ref'] == ref:
            return item.get('nets') or []
    return []


def discovery_refs(candidates, decisions):
    """Parts REQ-Q08 asks about: unassigned parts and the members of rejected candidates (not duplicates), less the
    parts an add decision placed in a circuit."""
    by_id = {c['id']: c for c in candidates.get('candidates', [])}
    refs, added = {u['ref'] for u in candidates.get('unassigned', [])}, set()
    for decision in decisions if isinstance(decisions, list) else []:
        if isinstance(decision, dict) and decision.get('decision') == 'reject' and decision.get('reason') != 'DUPLICATE_OF':
            cand = by_id.get(decision.get('candidate'))
            if cand:
                refs |= {m['ref'] for m in cand['members']}
        elif isinstance(decision, dict) and decision.get('decision') == 'add' and isinstance(decision.get('members'), list):
            added |= {r for r in decision['members'] if isinstance(r, str)}
    return sorted(refs - added)


def validate(intent, candidates, db=None):
    """intent.circuits against the decisions and the candidate file; candidates bound to the netlist."""
    errors = []
    if not isinstance(candidates, dict) or candidates.get('schema_version') != SCHEMA_VERSION:
        return [f'circuit-candidates.json: schema_version {SCHEMA_VERSION} required; regenerate it with circuit_candidates.py']
    if db is not None and candidates.get('db_sha256') != db_fingerprint(db):
        errors.append('circuit-candidates.json db_sha256 does not match the netlist; regenerate it')
    decisions = intent.get('circuit_decisions')
    if decisions is None:
        return errors + ['intent.circuit_decisions missing: every candidate needs a decision; run circuit_decisions.py']
    circuits, derive_errors = derive(candidates, decisions)
    errors += derive_errors
    expected = {c['id']: c for c in circuits}
    written = {c['id']: c for c in intent.get('circuits', []) if isinstance(c, dict) and _text(c.get('id'))}
    for cid in sorted(set(expected) - set(written)):
        errors.append(f'intent.circuits missing {cid}, which the decisions produce (run circuit_decisions.py --write)')
    for cid in sorted(set(written) - set(expected)):
        errors.append(f'intent.circuits has {cid}, which no decision produces')
    for cid in sorted(set(expected) & set(written)):
        want, have = expected[cid], written[cid]
        if have.get('type') != want['type']:
            errors.append(f'{cid}: type {have.get("type")} differs from the decision ({want["type"]})')
        if sorted(set(have.get('refs') or [])) != want['refs']:
            extra = sorted(set(have.get('refs') or []) - set(want['refs']))
            missing = sorted(set(want['refs']) - set(have.get('refs') or []))
            errors.append(f'{cid}: refs differ from the decision (extra {extra}, missing {missing}); members come from candidates')
        if list(have.get('states') or []) != want['states']:
            errors.append(f'{cid}: states {have.get("states")} differ from the decision ({want["states"]})')
        if list(have.get('candidate_ids') or []) != want['candidate_ids']:
            errors.append(f'{cid}: candidate_ids must be {want["candidate_ids"]}')
        if sorted(have.get('owned') or []) != want['owned']:
            errors.append(f'{cid}: owned {sorted(have.get("owned") or [])} differs from the decisions ({want["owned"]}); '
                          'ownership comes from the claim rule and own decisions')
    return errors


def write_circuits(intent, candidates):
    """The intent with circuits derived from its decisions (a new dict); errors are not written."""
    circuits, errors = derive(candidates, intent.get('circuit_decisions') or [])
    out = dict(intent)
    if not errors:
        out['circuits'] = circuits
        out['circuit_candidates_sha256'] = candidates.get('db_sha256')
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description='由候选决定生成 intent.circuits，或校验已写的电路')
    parser.add_argument('intent')
    parser.add_argument('candidates')
    parser.add_argument('--db', help='db.json：核对候选文件与网表绑定')
    parser.add_argument('--write', action='store_true', help='把推出的电路写回 intent.json')
    args = parser.parse_args(argv)
    intent = load_json(args.intent)
    candidates = load_json(args.candidates)
    db = load_json(args.db) if args.db else None
    circuits, errors = derive(candidates, intent.get('circuit_decisions') or [])
    if errors:
        print('决定无效:\n  - ' + '\n  - '.join(errors))
        return 1
    if args.write:
        intent = write_circuits(intent, candidates)
        with open(args.intent, 'w', encoding='utf-8') as stream:
            json.dump(intent, stream, ensure_ascii=False, indent=1)
            stream.write('\n')
    errors = validate(intent, candidates, db)
    if errors:
        print('intent.circuits 与决定不一致:\n  - ' + '\n  - '.join(errors))
        return 1
    print(f'电路 {len(circuits)} 个（来自 {len(intent.get("circuit_decisions") or [])} 条决定）；REQ-Q08 复核器件 '
          f'{len(discovery_refs(candidates, intent.get("circuit_decisions") or []))} 颗')
    return 0


if __name__ == '__main__':
    sys.exit(main())

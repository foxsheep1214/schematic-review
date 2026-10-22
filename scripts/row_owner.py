#!/usr/bin/env python3
"""Which circuit, system function or the board each plan row belongs to (function-tree design §3.1, step 2).

A row about a circuit belongs to that circuit. A row of a system rule (catalog.SYSTEM_FUNCTIONS) belongs to that system
function. A row about parts belongs to the circuit that owns them (circuit_decisions writes `owned`; a hand-drawn
circuit owns the parts no other circuit lists). Everything else belongs to the board. The planner writes `owner` on
each row, the `owners` table (each circuit's parts) and the row counts in the summary; the validator recomputes the
owner from the table and refuses a row whose written owner differs. A row the reviewer adds later needs none.
"""
from collections import Counter

import catalog

KINDS = ('SYSTEM', 'CIRCUIT', 'BOARD')


def part_owners(circuits):
    """{ref: circuit id} for every part exactly one circuit owns."""
    if all('owned' in c for c in circuits):
        claims = [(ref, c['id']) for c in circuits for ref in c['owned']]
    else:
        claims = [(ref, c['id']) for c in circuits for ref in c.get('refs', [])]
    count = Counter(ref for ref, _ in claims)
    return {ref: cid for ref, cid in claims if count[ref] == 1}


def owner(check, parts):
    obj = check.get('object') if isinstance(check.get('object'), dict) else {}
    if obj.get('circuit'):
        return {'kind': 'CIRCUIT', 'id': obj['circuit']}
    system = catalog.SYSTEM_OF_RULE.get(check.get('rule'))
    if system:
        return {'kind': 'SYSTEM', 'id': system}
    refs = obj.get('refs') if isinstance(obj.get('refs'), list) and obj.get('refs') else [obj.get('ref')]
    held = {parts.get(ref) for ref in refs}
    if len(held) == 1 and None not in held:
        return {'kind': 'CIRCUIT', 'id': held.pop()}
    return {'kind': 'BOARD'}


def table(circuits, parts):
    """The plan's owner table: every circuit with the parts it owns."""
    return [{'kind': 'CIRCUIT', 'id': c['id'], 'parts': sorted(ref for ref, cid in parts.items() if cid == c['id'])}
            for c in sorted(circuits, key=lambda c: c['id'])]


def counts(checks):
    """Rows per owner, system functions first and the board last."""
    rows = Counter((c['owner']['kind'], c['owner'].get('id')) for c in checks)
    out = []
    for kind, oid in sorted(rows, key=lambda k: (KINDS.index(k[0]), k[1] or '')):
        entry = {'kind': kind, 'rows': rows[(kind, oid)]}
        if oid is not None:
            entry['id'] = oid
        out.append(entry)
    return out


def errors(plan):
    """Rows whose written owner is not the one the plan's owner table gives."""
    if plan.get('owners') is None:
        return []
    parts = {ref: e['id'] for e in plan['owners'] if e.get('kind') == 'CIRCUIT' for ref in e.get('parts', [])}
    out = []
    for check in plan.get('checks') or []:
        if isinstance(check, dict) and 'owner' in check and check['owner'] != owner(check, parts):
            out.append(f"{check.get('id')}: owner {check['owner']} is not {owner(check, parts)} "
                       f"(from the row object, its rule and the parts each circuit owns)")
    return out

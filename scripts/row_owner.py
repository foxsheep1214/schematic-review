#!/usr/bin/env python3
"""Which circuit, interface, system function or the board each plan row belongs to (function-tree design §3.1).

A row about a circuit belongs to that circuit, a row about an interface to that interface. A row of a system rule
(catalog.SYSTEM_FUNCTIONS) belongs to that system function. A row of an interface rule (catalog.INTERFACE_RULES)
whose nets all lie on one interface belongs to it; a net on a connector belongs to the connector's interface first,
then a chain's, a circuit pair's and a rail's. A row about parts belongs to the circuit that owns them (circuit_decisions writes `owned`; a hand-drawn
circuit owns the parts no other circuit lists). Everything else belongs to the board. The planner writes `owner` on
each row, the `owners` table (each circuit's parts) and the row counts in the summary; the validator recomputes the
owner from the table and refuses a row whose written owner differs. A row the reviewer adds later needs none.
"""
from collections import Counter

import catalog

KINDS = ('SYSTEM', 'CIRCUIT', 'INTERFACE', 'BOARD')
INTERFACE_ORDER = ('EXTERNAL', 'LINK', 'CIRCUIT_PAIR', 'SUPPLY')


def part_owners(circuits):
    """{ref: circuit id} for every part exactly one circuit owns."""
    if all('owned' in c for c in circuits):
        claims = [(ref, c['id']) for c in circuits for ref in c['owned']]
    else:
        claims = [(ref, c['id']) for c in circuits for ref in c.get('refs', [])]
    count = Counter(ref for ref, _ in claims)
    return {ref: cid for ref, cid in claims if count[ref] == 1}


def interface_nets(section):
    """{net: interface id} from the plan's interfaces section, a connector's interface first."""
    out = {}
    items = sorted((section or {}).get('interfaces') or [],
                   key=lambda i: (INTERFACE_ORDER.index(i['kind']) if i.get('kind') in INTERFACE_ORDER else 9, i['id']))
    for item in items:
        for entry in item.get('nets') or []:
            out.setdefault(entry['net'], item['id'])
    return out


def owner(check, parts, nets=None):
    obj = check.get('object') if isinstance(check.get('object'), dict) else {}
    if obj.get('circuit'):
        return {'kind': 'CIRCUIT', 'id': obj['circuit']}
    if obj.get('interface'):
        return {'kind': 'INTERFACE', 'id': obj['interface']}
    system = catalog.SYSTEM_OF_RULE.get(check.get('rule'))
    if system:
        return {'kind': 'SYSTEM', 'id': system}
    row_nets = obj.get('nets') if isinstance(obj.get('nets'), list) and obj.get('nets') else [obj.get('net')]
    if check.get('rule') in catalog.INTERFACE_RULES and nets:
        held = {nets.get(n) for n in row_nets}
        if len(held) == 1 and None not in held:
            return {'kind': 'INTERFACE', 'id': held.pop()}
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
    if not isinstance(plan.get('owners'), list):
        return ['plan.owners missing: plans before schema 6 carry no owner table; regenerate the plan']
    parts = {ref: e['id'] for e in plan['owners'] if e.get('kind') == 'CIRCUIT' for ref in e.get('parts', [])}
    nets = interface_nets(plan.get('interfaces'))
    out = []
    for check in plan.get('checks') or []:
        if isinstance(check, dict) and 'owner' in check and check['owner'] != owner(check, parts, nets):
            out.append(f"{check.get('id')}: owner {check['owner']} is not {owner(check, parts, nets)} "
                       f"(from the row object, its rule, the parts each circuit owns and the interface nets)")
    return out


def coverage_errors(plan, db):
    """Ownership coverage (REQ-Q08 extended, function-tree step 6): when the circuits come from candidates, every fitted
    part is owned by exactly one circuit or is on the REQ-Q08 list for review."""
    if not plan.get('circuit_candidates') or plan.get('owners') is None or not isinstance(db, dict):
        return []
    owned = Counter(ref for e in plan['owners'] if e.get('kind') == 'CIRCUIT' for ref in e.get('parts', []))
    listed = {ref for c in plan.get('checks') or [] if isinstance(c, dict) and c.get('rule') == 'REQ-Q08'
              for ref in (c.get('object') or {}).get('unassigned') or []}
    out = []
    for ref in sorted(r for r, part in (db.get('parts') or {}).items() if not (part or {}).get('nc')):
        if owned[ref] > 1:
            out.append(f'{ref}: owned by {owned[ref]} circuits; a part has one owning circuit')
        elif not owned[ref] and ref not in listed:
            out.append(f'{ref}: fitted part owned by no circuit and not on the REQ-Q08 list; '
                       f'decide which circuit takes it (circuit_decisions) or list it for review')
    return out

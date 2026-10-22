#!/usr/bin/env python3
"""What one plan row asks, independent of how the reviewer named things (merge plan of 2026-10-21, §5).

A check is identified by the rule at its semantic revision, the physical object (parts, nets with their full sheet path,
pins, state, assembly; a page where the rule is about the page) and the atomic criterion. A circuit's display name is
presentation, so a renamed circuit asks the same check; a net is never shortened to its last path segment, so
/A/TEMP and /B/TEMP stay two checks. The rule revision is a digest of the catalog entry: a reworded rule asks a
new check.
A circuit-level row names its circuit by `circuit_key` (the candidate ids it came from) and its state; the member list,
the core part and the net spellings are how that circuit was drawn, not what the row asks (function-tree design, step 2).
An assembly is named by what it is: the plan maps each intent.assemblies name to a key from its population and jumpers
(`assemblies`), and a checker row's state, or the assembly a row checks, is identified by that key. A checker's
inventory digest and its handle into the inventory are bookkeeping, not what the row asks, so they stay out.
"""
import hashlib
import json

import catalog

DISPLAY_FIELDS = ('circuit',)
DRAWING_FIELDS = ('ref', 'refs', 'nets')
# Handles into a checker's inventory (with the `<checker>_digest` fields): the validator rebinds them to the inventory.
INVENTORY_FIELDS = ('decoupling_group', 'diff_pair', 'i2c_region', 'inductive_load', 'input_filter', 'optocoupler',
                    'power_switch', 'power_up', 'supervision')


def _digest(value, n):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()[:n]


def rule_revision(rule):
    """Digest of the catalog entry and question template; 'unknown' for a rule the catalog does not have."""
    entry = catalog.BY_ID.get(rule)
    if entry is None:
        return 'unknown'
    return _digest({'rule': list(entry), 'question': catalog.QUESTIONS.get(rule)}, 12)


def canonical(value):
    if isinstance(value, dict):
        return {k: canonical(v) for k, v in sorted(value.items()) if k not in DISPLAY_FIELDS}
    if isinstance(value, list):
        return sorted((canonical(v) for v in value), key=lambda v: json.dumps(v, sort_keys=True, ensure_ascii=False))
    return value


def assembly_map(assemblies):
    """The plan's `assemblies`: each declared assembly's name and the key of its population and jumpers."""
    out = []
    for state in assemblies or []:
        if isinstance(state, dict) and state.get('id'):
            content = {'population': {ref: value is True for ref, value in (state.get('population') or {}).items()},
                       'jumpers': dict(state.get('jumpers') or {})}
            out.append({'id': state['id'], 'key': 'ASSEMBLY-' + _digest(content, 12)})
    return out


def identity(check, assemblies=None):
    rule = check.get('rule') or str(check.get('id', '')).split('.')[0]
    obj = check.get('object') if isinstance(check.get('object'), dict) else {}
    obj = {k: v for k, v in obj.items() if k not in INVENTORY_FIELDS and not k.endswith('_digest')}
    if 'circuit_key' in obj:
        obj = {k: v for k, v in obj.items() if k not in DRAWING_FIELDS}
    names = {e['id']: e['key'] for e in assemblies or [] if isinstance(e, dict) and isinstance(e.get('id'), str)}
    if names:   # a circuit row's state is a working state, never an assembly
        name = lambda v: names.get(v, v) if isinstance(v, str) else v
        if 'assembly' in obj:
            obj['assembly'] = name(obj['assembly'])
        if 'circuit_key' not in obj:
            if 'state' in obj:
                obj['state'] = name(obj['state'])
            if isinstance(obj.get('states'), list):
                obj['states'] = [name(v) for v in obj['states']]
    return {'rule': rule, 'rule_revision': rule_revision(rule), 'object': canonical(obj),
            'criterion': check.get('criterion')}


def key(check, assemblies=None):
    """The check key of a plan row (16 hex digits); `assemblies` is the plan's assembly map."""
    return _digest(identity(check, assemblies), 16)

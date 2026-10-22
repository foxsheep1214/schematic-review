#!/usr/bin/env python3
"""What one plan row asks, independent of how the reviewer named things (merge plan of 2026-10-21, §5).

A check is identified by the rule at its semantic revision, the physical object (parts, nets with their full sheet path,
pins, state, assembly; a page where the rule is about the page) and the atomic criterion. A circuit's display name is
presentation, so a renamed circuit asks the same check; a net is never shortened to its last path segment, so
/A/TEMP and /B/TEMP stay two checks. The rule revision is a digest of the catalog entry: a reworded rule asks a
new check.
"""
import hashlib
import json

import catalog

DISPLAY_FIELDS = ('circuit',)


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


def identity(check):
    rule = check.get('rule') or str(check.get('id', '')).split('.')[0]
    return {'rule': rule, 'rule_revision': rule_revision(rule),
            'object': canonical(check.get('object') if isinstance(check.get('object'), dict) else {}),
            'criterion': check.get('criterion')}


def key(check):
    """The check key of a plan row (16 hex digits)."""
    return _digest(identity(check), 16)

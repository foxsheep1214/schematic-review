"""Attribute requests and consequences to their owner, never by prose similarity.

workflow v2 uses task.request_keys[check_id] for shared input-gap rows. Each
request then carries its own consequence assessment. A compound row keeps the
worst branch, while a task receives only the branches it actually owns.
Legacy ambiguous rows stay visible and unallocated; they cannot manufacture
additional P0 roots or donate another task's acquisition instructions.
"""
from collections import Counter
from review_summary import validate_impact

LEVELS = ('P0', 'P1', 'P2', 'P3')


def worst(levels):
    return next((s for s in LEVELS if s in levels), None)


def ownership(tasks):
    owners = {}
    for task in tasks:
        for cid in task.get('check_ids') or []:
            owners.setdefault(cid, set()).add(task.get('id'))
    return owners


def selected_keys(task, cid, row, owners):
    requests = row.get('input_requests') or {}
    if not isinstance(requests, dict):
        return None
    if not requests:
        return []  # nothing to allocate: every owner keeps the row's own consequence
    explicit = task.get('request_keys')
    if isinstance(explicit, dict) and cid in explicit:
        keys = explicit[cid]
        if (isinstance(keys, list) and keys and all(isinstance(k, str) for k in keys)
                and len(keys) == len(set(keys)) and set(keys) <= set(requests)):
            return keys
        return None
    return list(requests) if len(owners.get(cid, {task.get('id')})) <= 1 else None


def task_view(task, checks, owners=None):
    """One shared projection used by scheduling, severity counts and report text."""
    owners = owners if owners is not None else ownership([task])
    levels, requests, ambiguous = [], [], []
    for cid in task.get('check_ids') or []:
        if cid not in checks:
            continue
        row = checks.get(cid, {})
        if row.get('review_result') == 'FAIL':
            levels.append(row.get('severity'))
            continue
        keys = selected_keys(task, cid, row, owners)
        if keys is None:
            ambiguous.append(cid)
            continue
        all_requests = row.get('input_requests') or {}
        partial = set(keys) != set(all_requests)
        branch_levels = []
        for key in keys:
            req = all_requests[key]
            if not isinstance(req, dict):
                ambiguous.append(cid)
                continue
            level = req.get('potential_severity')
            if level in LEVELS and not validate_impact({
                    **req, 'id': cid + '/' + key, 'review_result': 'INSUFFICIENT',
                    'gap_cause': row.get('gap_cause'), 'blocking': row.get('blocking')}, classes=True):
                branch_levels.append(level)
            elif partial:
                ambiguous.append(cid)
            requests.append((cid, key, req))
        if partial:
            levels.extend(branch_levels)
        else:
            # The complete row is owned: do not permit weaker request metadata
            # to hide its aggregate hazard, including legacy one-owner records.
            levels.append(row.get('potential_severity'))
    return {'level': worst(levels) if not ambiguous else None,
            'known_level': worst(levels), 'requests': requests,
            'ambiguous_checks': sorted(set(ambiguous))}


def validate_scopes(tasks, checks, strict=False):
    errors = []
    owners = ownership(tasks)
    by_id = {t['id']: t for t in tasks}
    for task in tasks:
        mapping = task.get('request_keys')
        if mapping is not None:
            if not isinstance(mapping, dict):
                errors.append(task['id'] + ': request_keys must map check IDs to exact missing-input keys')
                continue
            for cid in mapping:
                if cid not in task.get('check_ids', []) or not checks.get(cid, {}).get('input_requests'):
                    errors.append(task['id'] + ': request_keys names an unowned/non-request check ' + cid)
    for cid, tids in owners.items():
        row = checks.get(cid, {})
        requests = row.get('input_requests') or {}
        if not isinstance(requests, dict):
            continue  # The input-request validator reports malformed data.
        shared = len(tids) > 1 and row.get('review_result') == 'INSUFFICIENT'
        explicit = any(cid in (by_id[t].get('request_keys') or {}) for t in tids
                       if isinstance(by_id[t].get('request_keys', {}), dict))
        if not ((strict and shared and requests) or explicit):
            continue
        assigned = []
        for tid in sorted(tids):
            keys = selected_keys(by_id[tid], cid, row, owners)
            if keys is None:
                errors.append(f'{tid}/{cid}: shared gap requires explicit request_keys')
            else:
                assigned.extend(keys)
        counts = Counter(assigned)
        if set(counts) != set(requests) or any(n != 1 for n in counts.values()):
            errors.append(cid + ': each input request must have exactly one owning task (no omission/duplicate)')
        if shared:
            levels = []
            for key, req in requests.items():
                if not isinstance(req, dict):
                    errors.append(cid + ': malformed input request ' + key)
                    continue
                errors.extend(validate_impact({**req, 'id': cid + '/' + key,
                    'review_result': 'INSUFFICIENT', 'gap_cause': row.get('gap_cause'),
                    'blocking': row.get('blocking')}, classes=True))
                levels.append(req.get('potential_severity'))
            if worst(levels) != row.get('potential_severity'):
                errors.append(cid + ': request consequences must preserve the aggregate potential_severity')
    return errors

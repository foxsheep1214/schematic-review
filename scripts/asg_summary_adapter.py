"""Adapt ASG parent calculations and child preflight results without equating their counts.

Only an explicit contract citation establishes parentage; suffixes and equal counts do not.
The adapter reconciles declarations, not the truth of formulas or source parameters.
"""
from collections import Counter
from pathlib import Path

STATES = {'supported': 'SUPPORTED', 'conditional': 'CONDITIONAL', 'fail': 'FAIL'}


def adapt_asg(rows, checked, contract, inventory_path, preflight_path, contract_path, issue):
    inventory = {'schema_version': 1, 'calculations': []}
    parents, expected, coverage = {}, {}, Counter()
    for index, row in enumerate(rows):
        where = f'calculations[{index}]'
        if not isinstance(row, dict):
            inventory['calculations'].append(row)
            continue
        key = row.get('id')
        conclusion = row.get('conclusion')
        inventory['calculations'].append({'id': key, 'claim': STATES.get(conclusion) if isinstance(conclusion, str) else None})
        if not isinstance(key, str) or not key.strip():
            continue  # Core validator reports invalid/duplicate parent IDs.
        parents.setdefault(key, []).append(row)
        cov = row.get('coverage')
        if cov not in ('complete', 'partial'):
            issue('UNKNOWN_COVERAGE', f'{key}: unsupported coverage', inventory_path, where)
        else:
            coverage[cov] += 1
        checks = row.get('checks')
        names = [c.get('name') if isinstance(c, dict) else None for c in checks] if isinstance(checks, list) else []
        if not names or any(not isinstance(n, str) or not n.strip() for n in names) or len(set(names)) != len(names):
            issue('BAD_CHILD_INVENTORY', f'{key}: checks need unique names', inventory_path, where)
        else:
            expected[key] = set(names)
    meta = {'format': 'asg-parent-child-v1', 'parent_count': len(rows),
            'child_count': None, 'links': {},
            'coverage': dict(complete=coverage['complete'], partial=coverage['partial'])
            if sum(coverage.values()) == len(rows) and len(parents) == len(rows) else None}
    valid_contract = (isinstance(contract, dict) and type(contract.get('schema_version')) is int
                      and contract['schema_version'] == 1 and isinstance(contract.get('calculations'), list)
                      and bool(contract['calculations']))
    valid_results = (isinstance(checked, dict) and checked.get('status') in (*STATES.values(), 'PASS', 'INSUFFICIENT')
                     and isinstance(checked.get('calculations'), dict) and bool(checked['calculations']))
    if not valid_contract or not valid_results:
        issue('ASG_MAPPING_REQUIRED', 'ASG requires design-preflight contract and executed preflight calculations map',
              preflight_path, 'calculations')
        return inventory, None, meta
    results = checked['calculations']
    meta['child_count'] = len(results)
    if checked.get('errors'):
        issue('ASG_PREFLIGHT_ERRORS', 'preflight reported errors; inspect original results', preflight_path, 'errors')
    grouped = {}
    for child in contract['calculations']:
        key = child.get('id') if isinstance(child, dict) else None
        if not isinstance(key, str) or not key.strip():
            issue('INVALID_ID', 'invalid contract child ID', contract_path, 'calculations', True)
            continue
        grouped.setdefault(key, []).append(child)
    if set(grouped) != set(results):
        issue('CHILD_ID_SET_MISMATCH', 'contract and executed child IDs differ', preflight_path, 'calculations', True)
    linked, invalid = {}, set()
    for cid, entries in grouped.items():
        if len(entries) != 1:
            issue('DUPLICATE_ID', f'duplicate contract child {cid}', contract_path, 'calculations', True)
            continue
        child = entries[0]
        values = child.get('inputs')
        links = set()
        for value in values.values() if isinstance(values, dict) else []:
            evidence = value.get('evidence') if isinstance(value, dict) else None
            for ev in evidence if isinstance(evidence, list) else []:
                if not isinstance(ev, dict) or not isinstance(ev.get('source'), str):
                    continue
                source = Path(ev['source'])
                roots = [Path(contract_path).parent, Path(contract_path).parent.parent]
                matches = [source] if source.is_absolute() else [root / source for root in roots]
                if not any(p.resolve() == Path(inventory_path).resolve() for p in matches):
                    continue
                for parent, names in expected.items():
                    for name in names:
                        if ev.get('locator') == parent + ' / ' + name:
                            links.add((parent, name))
        if len(links) != 1:
            issue('UNMAPPED_CHILD', f'{cid}: requires one unambiguous parent/check citation', contract_path, cid)
            continue
        parent, name = next(iter(links))
        meta['links'][cid] = {'parent': parent, 'check': name}
        if name in linked.setdefault(parent, {}):
            invalid.add(parent)
            issue('DUPLICATE_CHILD_LINK', f'{parent} / {name} mapped more than once', contract_path, cid, True)
        result = results.get(cid)
        status = result.get('status') if isinstance(result, dict) else None
        if status not in STATES.values():
            invalid.add(parent)
            issue('UNKNOWN_STATUS', f'{cid}: unsupported/missing child status', preflight_path, cid)
        if child.get('claim') not in STATES.values():
            invalid.add(parent)
            issue('UNKNOWN_CLAIM', f'{cid}: unsupported child claim', contract_path, cid)
        elif status in STATES.values() and child['claim'] != status:
            issue('CHILD_STATUS_MISMATCH', f'{cid}: contract claim differs from result', preflight_path, cid, True)
        linked[parent][name] = status
    normalized = {}
    for parent, originals in parents.items():
        if len(originals) != 1:
            continue
        row = originals[0]
        child_rows = linked.get(parent, {})
        if not expected.get(parent) or set(child_rows) != expected[parent]:
            invalid.add(parent)
            issue('CHILD_COVERAGE_GAP', f'{parent}: child coverage incomplete', contract_path, parent)
        state = None
        if parent not in invalid and row.get('coverage') in ('complete', 'partial'):
            conditions = row.get('assumptions') or row.get('omitted_terms') or row['coverage'] == 'partial'
            state = ('FAIL' if 'FAIL' in child_rows.values() else
                     'CONDITIONAL' if conditions or 'CONDITIONAL' in child_rows.values() else 'SUPPORTED')
        normalized[parent] = {'status': state}
    return inventory, {'schema_version': 1, 'status': 'PASS', 'results': normalized}, meta

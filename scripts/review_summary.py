"""Keep present checks, historical dispositions and handoffs separately visible."""
from collections import Counter


def categorized_summary(checks, expected, findings, stage):
    def count(keys):
        return {'checks': len(keys), 'results': dict(Counter(checks[k].get('review_result') for k in keys if isinstance(checks[k].get('review_result'), str)))}
    history = {k for k in checks if expected.get(k, {}).get('rule') == 'REQ-H02'}
    current = set(checks) - history
    handoffs = {k: c['handoff'] for k, c in checks.items()
                if isinstance(c.get('handoff'), dict) and c['handoff'].get('required')}
    tasks = stage.get('tasks', [])
    return {'current': count(current), 'history': count(history),
            'unique_findings': len(findings), 'unique_work_items': len({t['id'] for t in tasks}),
            'work_item_check_links': len({k for t in tasks for k in t['check_ids']}),
            'required_handoffs': len(handoffs),
            'handoffs_by_state': dict(Counter(h.get('state') for h in handoffs.values() if isinstance(h.get('state'), str))),
            'scope_migrations': sum(bool(c.get('scope_migration')) for c in checks.values()),
            'note': 'Handoffs overlap checks; ACCEPTED means responsibility/constraints accepted, not physical verification.'}


def validate_migrations(report, checks, expected):
    errors = []
    for key, row in checks.items():
        migration = row.get('scope_migration')
        if migration is None:
            continue
        def error(message):
            errors.append(key + ': scope_migration ' + message)
        if expected.get(key, {}).get('rule') != 'REQ-H02' or not isinstance(migration, dict):
            error('requires a historical disposition object')
            continue
        if row.get('review_result') != 'NA' or row.get('applicability') != 'NOT_APPLICABLE':
            error('retires the mixed criterion as NA, not electrical PASS')
        if migration.get('kind') not in ('SPLIT', 'DOWNSTREAM_ONLY'):
            error('kind must be SPLIT or DOWNSTREAM_ONLY')
        if not isinstance(migration.get('reason'), str) or not migration['reason'].strip():
            error('needs a reason')
        evidence = migration.get('evidence')
        if not isinstance(evidence, list) or not evidence or not all(isinstance(e, dict) and
                all(isinstance(e.get(k), str) and e[k].strip() for k in ('source', 'locator')) for e in evidence):
            error('needs locatable evidence')
        replacements = migration.get('replacement_check_ids')
        if (not isinstance(replacements, list) or any(not isinstance(k, str) for k in replacements)
                or len(replacements) != len(set(replacements))):
            error('replacement_check_ids must be unique strings')
            continue
        if migration.get('kind') == 'SPLIT' and not replacements:
            error('SPLIT must preserve electrical checks')
        if migration.get('kind') == 'DOWNSTREAM_ONLY' and replacements:
            error('DOWNSTREAM_ONLY must have no electrical replacements')
        if any(k not in checks or expected.get(k, {}).get('rule') == 'REQ-H02' for k in replacements):
            error('replacement must be a current check, not history')
        handoff = row.get('handoff')
        if not isinstance(handoff, dict) or handoff.get('required') is not True:
            error('must retain the downstream handoff on this disposition')
    return errors

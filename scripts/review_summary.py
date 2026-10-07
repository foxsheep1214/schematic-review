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
            'note': 'Handoffs overlap checks; ACCEPTED means responsibility/constraints accepted, not physical verification.'}

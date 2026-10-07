"""Stage decisions and root-cause work items; never infer electrical PASS.

This is supplementary to validate_review's evidence and release checks.
Work-item grouping is explicit,
not a text-similarity claim that different electrical causes are equivalent.
"""
PHASES = ('design_iteration', 'schematic_freeze', 'prototype_verification')


def text(value):
    return isinstance(value, str) and bool(value.strip())


def evidence(value):
    return isinstance(value, list) and bool(value) and all(
        isinstance(x, dict) and text(x.get('source')) and text(x.get('locator')) for x in value)


def workflow(plan, report, checks, expected, clarifications=None):
    errors, tasks, owners = [], [], {}
    enabled = bool(clarifications and clarifications['tasks']) or 'review_phase' in plan or 'workflow_version' in report or 'work_items' in report
    phase = plan.get('review_phase', 'schematic_freeze')
    if not enabled:
        return {'enabled': False, 'phase': phase, 'errors': [], 'tasks': [],
                'downstream_ready': set(), 'current_work_items': []}
    if phase not in PHASES:
        errors.append('review_phase must be one of ' + '/'.join(PHASES))
    if type(report.get('workflow_version')) is not int or report['workflow_version'] != 1:
        errors.append('staged results require workflow_version: 1')
    items = report.get('work_items')
    if not isinstance(items, list):
        errors.append('work_items must be an array (use [] when no separate repair/evidence tasks)')
        items = []
    unresolved = {k for k, c in checks.items() if c.get('review_result') in ('FAIL', 'INSUFFICIENT')}
    if clarifications:
        tasks.extend(clarifications['tasks'])
        for task in tasks:
            for cid in task['check_ids']:
                owners.setdefault(cid, []).append(task)
    seen = {task['id'] for task in tasks}
    for item in items:
        if not isinstance(item, dict) or not text(item.get('id')):
            errors.append('work_items require objects with IDs')
            continue
        key = item['id']
        if key in seen:
            errors.append('duplicate work item: ' + key)
        seen.add(key)
        for field in ('title', 'root_cause', 'reason', 'next_action'):
            if not text(item.get(field)):
                errors.append(key + ': missing ' + field)
        stage = item.get('due_stage')
        if stage not in PHASES:
            errors.append(key + ': invalid due_stage')
        if not evidence(item.get('evidence')):
            errors.append(key + ': stage/grouping reason needs locatable evidence')
        linked = item.get('check_ids')
        if not (isinstance(linked, list) and linked and all(text(x) for x in linked)
                and len(linked) == len(set(linked)) and set(linked) <= unresolved):
            errors.append(key + ': check_ids must name unique unresolved checks')
            continue
        if any(checks[cid].get('gap_cause') == 'REQUIREMENT_OPEN' for cid in linked):
            errors.append(key + ': requirement gaps are managed by clarification records, not duplicate work_items')
            continue
        for cid in linked:
            owners.setdefault(cid, []).append(item)
        tasks.append({k: item[k] for k in ('id', 'title', 'root_cause', 'check_ids', 'due_stage', 'reason', 'next_action', 'evidence') if k in item})
    for cid in sorted(unresolved - set(owners)):
        errors.append(cid + ': unresolved check has no root-cause work item')
    downstream = set()
    for cid, groups in owners.items():
        row = checks[cid]
        # Blocking failures need current repair; minor issues may be scheduled.
        critical_failure = row.get('severity') in ('P0', 'P1') or row.get('blocking') is True
        if (row.get('review_result') == 'FAIL' and critical_failure
                and row.get('disposition') != 'ACCEPTED'
                and any(g.get('due_stage') != 'design_iteration' for g in groups)):
            errors.append(cid + ': confirmed FAIL must enter the current repair queue')
        if (row.get('review_result') == 'INSUFFICIENT' and row.get('potential_severity') == 'P0'
                and any(g.get('due_stage') != 'design_iteration' for g in groups)):
            errors.append(cid + ': potential P0 needs current investigation')
        if (row.get('review_result') == 'INSUFFICIENT' and row.get('gap_cause') == 'REQUIREMENT_OPEN'
                and any(g.get('due_stage') != 'design_iteration' for g in groups)):
            errors.append(cid + ': undefined requirement goes back to the designer in the current round')
        if (row.get('review_result') == 'INSUFFICIENT' and row.get('gap_cause') == 'REVIEW_INCOMPLETE'
                and any(g.get('due_stage') != 'design_iteration' for g in groups)):
            errors.append(cid + ': unfinished review must enter the current review queue')
        if not all(g.get('due_stage') == 'prototype_verification' for g in groups):
            continue
        h = row.get('handoff') or {}
        planned_handoff = expected.get(cid, {}).get('handoff') or {}
        if not isinstance(h, dict) or not isinstance(planned_handoff, dict):
            continue  # the main validator reports the malformed handoff
        prerequisite_ids = h.get('schematic_prerequisites')
        ready = (
            row.get('review_result') == 'INSUFFICIENT' and row.get('potential_severity') != 'P0'
            and row.get('gap_cause') in (None, 'DOWNSTREAM_VERIFICATION')
            and planned_handoff.get('required') is True
            and h.get('required') is True and h.get('scope') == 'downstream_verification'
            and h.get('state') in ('ACCEPTED', 'VERIFIED') and evidence(h.get('evidence'))
            and isinstance(prerequisite_ids, list) and bool(prerequisite_ids)
            and all(text(k) and k != cid and checks.get(k, {}).get('review_result') == 'PASS'
                    for k in prerequisite_ids)
            and len(prerequisite_ids) == len(set(prerequisite_ids)))
        if ready:
            downstream.add(cid)
    rank = PHASES.index(phase) if phase in PHASES else 0
    current = [t['id'] for t in tasks if t.get('due_stage') in PHASES
               and PHASES.index(t['due_stage']) <= rank]
    return {'enabled': True, 'phase': phase, 'errors': errors, 'tasks': tasks,
            'downstream_ready': downstream, 'current_work_items': current}


def decision(state, errors, release):
    if errors:
        status = 'REPAIR_REVIEW_RECORDS'
    elif state['phase'] == 'design_iteration':
        status = 'ADDRESS_CURRENT_ITEMS' if state['current_work_items'] else 'CONTINUE_DESIGN'
    elif state['phase'] == 'schematic_freeze':
        status = 'READY_FOR_LAYOUT' if release != 'NO_GO' else 'FREEZE_BLOCKED'
    else:
        status = 'FOLLOW_UP_EXTERNAL_VERIFICATION'
    return {'phase': state['phase'], 'status': status,
            'schematic_release': release,
            'current_work_items': state['current_work_items'],
            'work_items': state['tasks'],
            'check_count_in_work_items': len({k for t in state['tasks'] for k in t['check_ids']}),
            'unique_work_items': len(state['tasks']),
            'downstream_handoffs_ready': sorted(state['downstream_ready']),
            'scope': 'Continue design means analysis/redesign only; not permission to energize, fabricate or release hardware.'}

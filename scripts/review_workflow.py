"""Stage decisions and root-cause work items; never infer electrical PASS.

This is supplementary to validate_review's evidence and release checks.
Work-item grouping is explicit,
not a text-similarity claim that different electrical causes are equivalent.
"""
from electrical_contract import PHASES
import results_model
from task_scope import ownership, task_view, validate_scopes
# Gaps a schematic change can often remove: the reviewer must propose that change or say why none exists.
DESIGNABLE_GAPS = ('EXTERNAL_DATA',)
PREFERENCES = ('DESIGN_FIRST', 'EVIDENCE_FIRST', 'EITHER')


def text(value):
    return isinstance(value, str) and bool(value.strip())


def evidence(value):
    return isinstance(value, list) and bool(value) and all(
        isinstance(x, dict) and text(x.get('source')) and text(x.get('locator')) for x in value)


def design_option(key, value, unresolved, finding_ids):
    """Structure of a work item's schematic alternative; never proves the change is correct."""
    from validate_remediation import validate_remediation, validate_figures, changes_topology
    label = key + '.design_option'
    if not isinstance(value, dict) or value.get('status') not in ('PROPOSED', 'NONE'):
        return [label + ': status must be PROPOSED or NONE']
    if value['status'] == 'NONE':
        ok = text(value.get('reason')) and evidence(value.get('evidence'))
        return [] if ok else [label + ': NONE needs the reason no schematic change removes the gap, with evidence']
    errors = []
    if not text(value.get('summary')):
        errors.append(label + ': missing summary')
    if value.get('preference') not in PREFERENCES or not text(value.get('preference_reason')):
        errors.append(label + ': preference (' + '/'.join(PREFERENCES) + ') and preference_reason required')
    errors.extend(validate_remediation(label, value.get('remediation'), finding_ids, require_preflight=True))
    errors.extend(validate_figures(label, value.get('figures'), need_after=changes_topology(value.get('remediation'))))
    avoids = value.get('avoids')
    if not (isinstance(avoids, list) and avoids and all(isinstance(a, dict) for a in avoids)):
        errors.append(label + ': avoids must list the problems the changed circuit avoids')
        avoids = []
    for a in avoids:
        linked = a.get('check_ids')
        if not (text(a.get('problem')) and text(a.get('after_change'))):
            errors.append(label + ': each avoids entry needs problem and after_change')
        if not (isinstance(linked, list) and linked and all(text(x) for x in linked)
                and len(linked) == len(set(linked)) and set(linked) <= unresolved):
            errors.append(label + ': avoids.check_ids must name unique unresolved checks')
    tradeoffs = value.get('tradeoffs')
    if not (isinstance(tradeoffs, list) and tradeoffs and all(text(x) for x in tradeoffs)):
        errors.append(label + ': tradeoffs must state costs, new risks and what stays open')
    return errors


def workflow(plan, report, checks, require_design_options=False):
    errors, tasks, owners = [], [], {}
    enabled = 'review_phase' in plan or bool(report.get('functions'))
    phase = plan.get('review_phase', 'schematic_freeze')
    if not enabled:
        return {'enabled': False, 'phase': phase, 'errors': [], 'tasks': [],
                'current_work_items': []}
    if phase not in PHASES:
        errors.append('review_phase must be one of ' + '/'.join(PHASES))
    items = report.get('work_items') or []   # derived from the functions' open/fail items (results_model)
    unresolved = {k for k, c in checks.items() if c.get('review_result') in ('FAIL', 'INSUFFICIENT')}
    seen = set()
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
            errors.append(key + ': check_ids must name unique unresolved checks (stage-NA tests are tracked by their handoff)')
            continue
        designable = any(checks[cid].get('review_result') == 'INSUFFICIENT'
                         and checks[cid].get('gap_cause') in DESIGNABLE_GAPS for cid in linked)
        if 'design_option' in item or (require_design_options and designable):
            errors.extend(design_option(key, item.get('design_option'), unresolved,
                                        {f.get('id') for f in report.get('findings') or [] if isinstance(f, dict)}))
        for cid in linked:
            owners.setdefault(cid, []).append(item)
        tasks.append({k: item[k] for k in ('id', 'title', 'root_cause', 'check_ids', 'due_stage', 'reason', 'next_action', 'evidence', 'design_option', 'request_keys',
                                     'closure_criterion', 'worst_case', 'blocks', 'subclass')
                      if k in item})
    classes = results_model.IMPACT_CLASS_VERSION
    errors.extend(validate_scopes(tasks, checks, strict=True, classes=classes))
    task_owners = ownership(tasks)
    for cid in sorted(unresolved - set(owners)):
        errors.append(cid + ': unresolved check has no root-cause work item')
    for cid, groups in owners.items():
        row = checks[cid]
        # Blocking failures need current repair; minor issues may be scheduled.
        critical_failure = row.get('severity') in ('P0', 'P1') or row.get('blocking') is True
        if (row.get('review_result') == 'FAIL' and critical_failure
                and row.get('disposition') != 'ACCEPTED'
                and any(g.get('due_stage') != 'design_iteration' for g in groups)):
            errors.append(cid + ': confirmed FAIL must enter the current repair queue')
        if (row.get('review_result') == 'INSUFFICIENT' and row.get('potential_severity') == 'P0'
                and any(g.get('due_stage') != 'design_iteration'
                        and (task_view(g, {cid: row}, task_owners, classes)['known_level'] == 'P0'
                             or cid in task_view(g, {cid: row}, task_owners, classes)['ambiguous_checks'])
                        for g in groups)):
            errors.append(cid + ': potential P0 needs current investigation')
        if (row.get('review_result') == 'INSUFFICIENT' and row.get('gap_cause') == 'REVIEW_INCOMPLETE'
                and any(g.get('due_stage') != 'design_iteration' for g in groups)):
            errors.append(cid + ': unfinished review must enter the current review queue')
    rank = PHASES.index(phase) if phase in PHASES else 0
    current = [t['id'] for t in tasks if t.get('due_stage') in PHASES
               and PHASES.index(t['due_stage']) <= rank]
    return {'enabled': True, 'phase': phase, 'errors': errors, 'tasks': tasks,
            'current_work_items': current}


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
            'design_options': {s: sum(1 for t in state['tasks'] if (t.get('design_option') or {}).get('status') == s)
                               for s in ('PROPOSED', 'NONE')},
            'scope': 'Continue design means analysis/redesign only; not permission to energize, fabricate or release hardware.'}

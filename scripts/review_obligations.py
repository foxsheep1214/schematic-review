"""Small, typed closure contracts for easily lost schematic obligations.

These contracts prove coverage and request ownership, not electrical correctness.
Names/requirements are controlled by the rule, never inferred from prose.
"""
from review_stage_scope import REQUEST_CAUSES
from task_scope import ownership, task_view

CONTRACTS = {
    'PRO-C03': ('isolation_qualification', {
        'working_stress': '实际工作电压、重复峰值与频率',
        'qualification_match': '各跨隔离器件的资格与实际条件匹配',
    }),
    'PWR-C15': ('loop_stability', {
        'loop_model': '实际拓扑、工作点及反馈模型',
        'compensation_configuration': '实际补偿配置与适用条件',
        'stability_limits': '规定角点的稳定性与动态边界',
    }),
}
ORDER = {'NA': 0, 'PASS': 1, 'INSUFFICIENT': 2, 'FAIL': 3}


def contract(rule):
    if rule not in CONTRACTS:
        return None
    domain, obligations = CONTRACTS[rule]
    return {'closure_domain': domain, 'obligations': dict(obligations)}


def _text(x):
    return isinstance(x, str) and bool(x.strip())


def _state(x):
    return isinstance(x, str) and x in ORDER


def _evidence(x):
    return isinstance(x, list) and bool(x) and all(isinstance(e, dict) and
        _text(e.get('source')) and _text(e.get('locator')) for e in x)


def validate_obligations(expected, checks, tasks, classes=False):
    errors = []
    protected = set()
    for cid, planned in expected.items():
        spec = contract(planned.get('rule'))
        if not spec or cid not in checks:
            continue
        row = checks[cid]
        protected.add(cid)
        if row.get('na_reason') == 'OUTSIDE_SCHEMATIC_STAGE':
            errors.append(cid + ': electrical qualification/stability cannot be deferred as stage NA')
        parts = row.get('obligations')
        # A whole-row topology NA (no feedback loop, no barrier) may cite one inapplicability
        # basis for the row instead of repeating it under every obligation.
        if parts is None and row.get('review_result') == 'NA' and row.get('na_reason') != 'OUTSIDE_SCHEMATIC_STAGE':
            if not _text(row.get('inapplicability_basis')):
                errors.append(cid + ': NA needs actual topology/application inapplicability')
            continue
        if not isinstance(parts, dict) or set(parts) != set(spec['obligations']):
            errors.append(cid + ': obligations must cover the complete rule contract')
            continue
        used, statuses = set(), []
        for name, item in parts.items():
            key = cid + '/' + name
            if not isinstance(item, dict):
                errors.append(key + ': malformed obligation'); continue
            state = item.get('review_result')
            statuses.append(state)
            if not _state(state) or not _text(item.get('rationale')) or not _evidence(item.get('evidence')):
                errors.append(key + ': needs result, scoped rationale and source evidence')
            if item.get('na_reason') == 'OUTSIDE_SCHEMATIC_STAGE':
                errors.append(key + ': schematic obligation cannot be moved to physical testing')
            if state == 'NA' and not _text(item.get('inapplicability_basis')):
                errors.append(key + ': NA needs actual topology/application inapplicability')
            keys = item.get('request_keys', [])
            if not isinstance(keys, list) or any(not isinstance(k, str) for k in keys):
                errors.append(key + ': request_keys must be a list of exact input names'); continue
            # Requirement/user/round gaps carry no input request (see review_stage_scope).
            if state == 'INSUFFICIENT' and not keys and row.get('gap_cause') in REQUEST_CAUSES:
                errors.append(key + ': missing obligation needs its own decisive input')
            if state != 'INSUFFICIENT' and keys:
                errors.append(key + ': resolved/inapplicable obligation cannot own open input requests')
            for req in keys:
                value = (row.get('input_requests') or {}).get(req)
                if not isinstance(value, dict) or value.get('closure_domain') != spec['closure_domain']:
                    errors.append(key + ': request must address ' + spec['closure_domain'])
            used.update(keys)
        if all(_state(s) for s in statuses) and row.get('review_result') != max(statuses, key=ORDER.get):
            errors.append(cid + ': result must preserve the worst obligation, not just connectivity')
        if used != set(row.get('input_requests') or {}):
            errors.append(cid + ': every input request must belong to an actual obligation')
        # Every physical barrier member needs an explicit disposition. A single
        # isolation-test voltage is not an application qualification.
        if planned.get('rule') == 'PRO-C03':
            refs = set((planned.get('object') or {}).get('refs') or [])
            members = row.get('qualification_members')
            if not isinstance(members, dict) or set(members) != refs or (not refs and row.get('review_result') != 'INSUFFICIENT'):
                errors.append(cid + ': qualification_members must cover each actual barrier component')
            else:
                for ref, member in members.items():
                    if not isinstance(member, dict) or not _state(member.get('review_result')) or not all(
                            _text(member.get(k)) for k in ('working_basis', 'qualification_basis', 'comparison')) or not _evidence(member.get('evidence')):
                        errors.append(cid + '/' + ref + ': working basis, qualification and comparison required')
                    elif _state(row.get('review_result')) and ORDER[member['review_result']] > ORDER[row['review_result']]:
                        errors.append(cid + '/' + ref + ': unresolved component cannot be hidden by aggregate result')
    owners = ownership(tasks)
    for task in tasks:
        if not (set(task.get('check_ids') or []) & protected):
            continue
        domains = {CONTRACTS[expected[c]['rule']][0] for c in task.get('check_ids', []) if c in protected}
        loops = {(expected[c].get('object') or {}).get('circuit') or c
                 for c in task.get('check_ids', [])
                 if c in protected and expected[c]['rule'] == 'PWR-C15'}
        if len(loops) > 1:
            errors.append(task.get('id', '?') + ': distinct converter loops require separate closure tasks')
        view = task_view(task, checks, owners, classes)
        # FAIL-only repair tasks already have their own remediation contract.
        if not view['requests']:
            continue
        domain = task.get('closure_domain')
        if len(domains) != 1 or domain not in domains:
            errors.append(task.get('id', '?') + ': qualification/stability requires a separate closure_domain')
        for cid, key, request in view['requests']:
            if request.get('closure_domain') != domain:
                errors.append(task.get('id', '?') + '/' + cid + ': unrelated request cannot share this closure task: ' + key)
    return errors


def task_obligation_labels(task, checks):
    labels = []
    for cid in task.get('check_ids') or []:
        spec = contract(cid.split('.', 1)[0])
        if spec:
            for name in spec['obligations'].values():
                if name not in labels:
                    labels.append(name)
    return labels

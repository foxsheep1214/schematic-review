"""Validate unique requirement decisions separately from electrical defects.

This checks record consistency, not whether a requirement is actually ambiguous
or whether cited evidence proves coverage of every candidate requirement.
"""
from collections import Counter


def text(value):
    return isinstance(value, str) and bool(value.strip())


def evidence(value):
    return isinstance(value, list) and bool(value) and all(
        isinstance(x, dict) and text(x.get('source')) and text(x.get('locator')) for x in value)


def id_list(value, allow_empty=False):
    return (isinstance(value, list) and (allow_empty or bool(value))
            and all(text(x) for x in value) and len(value) == len(set(value)))


def validate_clarifications(report, checks, expected):
    out = {'errors': [], 'blockers': [], 'tasks': [], 'items': [], 'by_check': {}, 'summary': None}
    errors = out['errors']

    def require(ok, message):
        if not ok:
            errors.append(message)

    require(type(report.get('requirement_clarification_version')) is int
            and report['requirement_clarification_version'] == 1,
            'requirement_clarification_version must be 1')
    rows = report.get('requirement_clarifications')
    if not isinstance(rows, list):
        errors.append('requirement_clarifications must be an array')
        rows = []
    gaps = {cid for cid, c in checks.items()
            if c.get('review_result') == 'INSUFFICIENT' and c.get('gap_cause') == 'REQUIREMENT_OPEN'}
    known_requirements = {(x.get('object') or {}).get('requirement_id') for x in expected.values()} - {None}
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or not text(row.get('id')):
            errors.append('requirement_clarifications: invalid object/id')
            continue
        cid = row['id']
        require(cid not in seen, cid + ': duplicate clarification id')
        seen.add(cid)
        out['items'].append(row)
        for field in ('title', 'question', 'decision_needed', 'owner', 'closure_criteria', 'impact_reason'):
            require(text(row.get(field)), cid + ': missing ' + field)
        require(evidence(row.get('evidence')), cid + ': reviewed inputs and ambiguity need locatable evidence')
        require(row.get('kind') in ('MISSING', 'AMBIGUOUS', 'CONFLICTING', 'UNCONFIRMED'), cid + ': invalid clarification kind')
        require(row.get('decision_due') in ('BEFORE_DESIGN', 'BEFORE_FREEZE', 'FOLLOW_UP'), cid + ': invalid decision_due')
        require(row.get('status') in ('OPEN', 'RESOLVED', 'RETRACTED'), cid + ': invalid clarification status')
        require('severity' not in row and 'potential_severity' not in row, cid + ': clarification uses decision urgency, not defect severity')
        refs = row.get('requirement_ids', [])
        require(id_list(refs, allow_empty=True), cid + ': invalid requirement_ids')
        if id_list(refs, allow_empty=True):
            require(set(refs) <= known_requirements, cid + ': unknown requirement ID; add it to the plan or use an unnumbered question')
        else:
            refs = []
        linked = row.get('check_ids')
        if not id_list(linked) or not set(linked) <= set(checks):
            errors.append(cid + ': check_ids must name unique existing affected checks')
            continue
        linked_requirements = {(expected.get(key, {}).get('object') or {}).get('requirement_id') for key in linked} - {None}
        require(id_list(refs, allow_empty=True) and linked_requirements <= set(refs),
                cid + ': include requirement IDs of affected requirement checks')
        if row.get('status') == 'OPEN':
            require(set(linked) <= gaps, cid + ': open clarification links only REQUIREMENT_OPEN checks; keep independent defects separate')
            # The report must say plainly what the requirement document says (or omits) and what to add.
            require(text(row.get('requirement_text')),
                    cid + ': requirement_text must quote the requirement wording or state 未提及 and what was searched')
            require(text(row.get('proposed_requirement')),
                    cid + ': proposed_requirement must give the clause to add to the requirement document')
            impact = row.get('freeze_impact')
            require(impact in ('BLOCKING', 'COVERED'), cid + ': freeze_impact must be BLOCKING or COVERED')
            require((impact == 'COVERED' and row.get('decision_due') == 'FOLLOW_UP')
                    or (impact == 'BLOCKING' and row.get('decision_due') in ('BEFORE_DESIGN', 'BEFORE_FREEZE')),
                    cid + ': decision_due must agree with freeze impact')
            if impact == 'BLOCKING':
                out['blockers'].append(cid + ': unresolved requirement decision blocks freeze')
            if impact == 'COVERED':
                proof = row.get('coverage')
                require(isinstance(proof, dict), cid + ': COVERED needs coverage proof')
                if isinstance(proof, dict):
                    require(text(proof.get('candidate_scope')) and text(proof.get('rationale')) and evidence(proof.get('evidence')),
                            cid + ': coverage needs bounded candidates, reasoning and evidence')
                    proof_ids = proof.get('check_ids')
                    require(id_list(proof_ids) and all(k not in linked and checks.get(k, {}).get('review_result') == 'PASS'
                                                     for k in (proof_ids if id_list(proof_ids) else [])),
                            cid + ': coverage must cite separate PASS checks for all candidate requirements')
            for key in linked:
                out['by_check'].setdefault(key, []).append(row)
            out['tasks'].append({'id': cid, 'kind': 'REQUIREMENT_CLARIFICATION', 'title': row.get('title'),
                                 'root_cause': row.get('question'), 'check_ids': linked, 'due_stage': 'design_iteration',
                                 'reason': row.get('impact_reason'), 'next_action': row.get('decision_needed'),
                                 'owner': row.get('owner'), 'decision_due': row.get('decision_due'),
                                 'closure_criteria': row.get('closure_criteria'), 'evidence': row.get('evidence'),
                                 'requirement_text': row.get('requirement_text'),
                                 'proposed_requirement': row.get('proposed_requirement')})
        elif row.get('status') in ('RESOLVED', 'RETRACTED'):
            closure = row.get('closure')
            require(isinstance(closure, dict), cid + ': closed clarification needs closure record')
            if isinstance(closure, dict):
                for field in ('by', 'date', 'decision', 'requirement_revision'):
                    require(text(closure.get(field)), cid + ': closure missing ' + field)
                require(evidence(closure.get('evidence')), cid + ': closure needs decision/correction evidence')
                require(evidence(closure.get('reverification')), cid + ': closure needs affected-check re-review evidence')
            # No broad status rewrite: new plan and ordinary check validation still apply.
            for key in linked:
                obj = expected.get(key, {}).get('object') or {}
                if obj.get('requirement_id') in refs:
                    if row.get('status') == 'RESOLVED':
                        require(obj.get('requirement_status') == 'CONFIRMED', cid + ': resolved requirement must be CONFIRMED in current plan')
                    else:
                        require(obj.get('requirement_status') != 'OPEN', cid + ': retracted requirement remains OPEN in current plan')
    for key in sorted(gaps):
        owners = out['by_check'].get(key, [])
        require(bool(owners), key + ': requirement gap has no open clarification')
        row = checks[key]
        require('potential_severity' not in row, key + ': requirement gap uses clarification freeze impact, not potential_severity')
        require(row.get('disposition', 'OPEN') == 'OPEN', key + ': requirement decision cannot be closed by risk acceptance')
        if owners:
            require(row.get('blocking') is any(x.get('freeze_impact') == 'BLOCKING' for x in owners),
                    key + ': blocking must match linked clarification freeze impact')
    counts = Counter(row.get('status') for row in out['items'] if isinstance(row.get('status'), str))
    out['summary'] = {'total': len(out['items']), 'open': counts['OPEN'], 'resolved': counts['RESOLVED'],
                      'retracted': counts['RETRACTED'], 'affected_checks': len(out['by_check']),
                      'insufficient_from_requirements': len(gaps),
                      'blocking_open': sum(x.get('status') == 'OPEN' and x.get('freeze_impact') == 'BLOCKING' for x in out['items']),
                      'covered_open': sum(x.get('status') == 'OPEN' and x.get('freeze_impact') == 'COVERED' for x in out['items'])}
    return out

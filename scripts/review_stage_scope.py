"""Separate schematic evidence gaps from downstream test obligations.

Checks are structural guards, not proof that the declared scope is truthful.
Legacy ledgers stay readable; new reviews opt into version 1 explicitly.
"""

OUTSIDE_STAGE = 'OUTSIDE_SCHEMATIC_STAGE'
REQUEST_FIELDS = ('missing_input', 'why_decisive', 'required_scope', 'acquisition', 'closure_criterion')


def text(value):
    return isinstance(value, str) and bool(value.strip())


def outside_stage(row):
    return row.get('review_result') == 'NA' and row.get('na_reason') == OUTSIDE_STAGE


def validate_stage_scope(report, checks, expected, required=False):
    errors, blockers = [], []
    enabled = required or 'stage_scope_version' in report or any(
        c.get('na_reason') == OUTSIDE_STAGE or 'input_requests' in c or any(
            isinstance(clause, dict) and clause.get('na_reason') == OUTSIDE_STAGE
            for clause in (c.get('requirement_clauses') if isinstance(c.get('requirement_clauses'), list) else []))
        for c in checks.values())
    summary = {'enforced': enabled, 'outside_schematic_stage': [], 'other_na': [],
               'input_request_count': 0, 'legacy_insufficient_without_requests': []}
    if enabled and (type(report.get('stage_scope_version')) is not int or report['stage_scope_version'] != 1):
        errors.append('stage_scope_version must be 1 for stage exclusions and actionable input requests')
    for cid, row in checks.items():
        result = row.get('review_result')
        clauses = row.get('requirement_clauses')
        for clause in clauses if isinstance(clauses, list) else []:
            if not isinstance(clause, dict) or clause.get('na_reason') != OUTSIDE_STAGE:
                continue
            linked = clause.get('check_ids')
            if not (clause.get('result') == 'NA' and isinstance(linked, list) and linked
                    and all(text(k) and k != cid and k in expected and outside_stage(checks.get(k, {}))
                            for k in linked)):
                errors.append(cid + ': downstream NA clause must link separate stage-NA checks with retained handoffs')
        if result == 'NA':
            summary['outside_schematic_stage' if outside_stage(row) else 'other_na'].append(cid)
        if row.get('na_reason') == OUTSIDE_STAGE and not outside_stage(row):
            errors.append(cid + ': OUTSIDE_SCHEMATIC_STAGE requires NA')
        if outside_stage(row):
            if row.get('blocking') is not False or any(k in row for k in
                    ('missing_inputs', 'input_requests', 'gap_cause', 'potential_severity')):
                errors.append(cid + ': stage NA is not an evidence gap; keep prerequisite gaps in separate checks')
            h = row.get('handoff')
            if not isinstance(h, dict):
                h = {}
            if h.get('required') is not True or h.get('scope') != 'downstream_verification':
                errors.append(cid + ': stage NA requires a downstream_verification handoff')
            if h.get('product_requirement_status') != 'PENDING_VERIFICATION':
                errors.append(cid + ': stage NA must retain product_requirement_status PENDING_VERIFICATION')
            prerequisites = h.get('schematic_prerequisites')
            if not (isinstance(prerequisites, list) and all(text(k) for k in prerequisites)
                    and len(set(prerequisites)) == len(prerequisites)):
                errors.append(cid + ': schematic_prerequisites must list unique check IDs (or justified [])')
                continue
            if not prerequisites and not text(h.get('no_schematic_prerequisites_reason')):
                errors.append(cid + ': empty prerequisites need no_schematic_prerequisites_reason')
            for key in prerequisites:
                if key == cid or key not in expected or key not in checks or checks[key].get('review_result') == 'NA':
                    errors.append(cid + ': prerequisite must name a separate applicable schematic check: ' + key)
                elif checks[key].get('review_result') != 'PASS':
                    blockers.append(cid + ': schematic prerequisite unresolved: ' + key)
        if result != 'INSUFFICIENT':
            if 'input_requests' in row:
                errors.append(cid + ': input_requests only belongs to INSUFFICIENT')
            continue
        requests = row.get('input_requests')
        if not enabled:
            summary['legacy_insufficient_without_requests'].append(cid)
            continue
        if row.get('gap_cause') == 'DOWNSTREAM_VERIFICATION':
            errors.append(cid + ': split schematic prerequisites from downstream tests; pure tests use stage NA')
        if not isinstance(requests, list) or not requests or not all(isinstance(r, dict) for r in requests):
            errors.append(cid + ': INSUFFICIENT requires actionable input_requests')
            continue
        requested = []
        for request in requests:
            if not all(text(request.get(field)) for field in REQUEST_FIELDS):
                errors.append(cid + ': input request needs ' + '/'.join(REQUEST_FIELDS))
            if text(request.get('missing_input')):
                requested.append(request['missing_input'])
        missing = row.get('missing_inputs')
        if not isinstance(missing, list) or not all(text(x) for x in missing) or (
                len(requested) != len(set(requested)) or len(missing) != len(set(missing))
                or set(requested) != set(missing)):
            errors.append(cid + ': input_requests must cover each missing_inputs entry exactly once')
        summary['input_request_count'] += len(requests)
    return errors, blockers, summary

"""Separate schematic evidence gaps from downstream test obligations.

Checks are structural guards, not proof that the declared scope is truthful.
A pure downstream test stays applicable to the product: it is NA only for this stage,
keeps applicability APPLICABLE and a downstream handoff, and never blocks through its prerequisites
(each prerequisite is a separate check graded on its own).
"""

import catalog

OUTSIDE_STAGE = 'OUTSIDE_SCHEMATIC_STAGE'
GAP_CAUSES = ('EXTERNAL_DATA', 'DELIVERABLE_PENDING', 'REVIEW_INCOMPLETE', 'USER_DEFERRED')
# Only real input/design gaps need a request; requirement gaps use clarification records,
# unfinished review is done in this round, user deferral cites the user's instruction.
REQUEST_CAUSES = ('EXTERNAL_DATA',)
REQUEST_FIELDS = ('why_decisive', 'required_scope', 'acquisition', 'closure_criterion')


def text(value):
    return isinstance(value, str) and bool(value.strip())


def outside_stage(row):
    return row.get('review_result') == 'NA' and row.get('na_reason') == OUTSIDE_STAGE


def validate_stage_scope(checks, expected):
    errors = []
    summary = {'outside_schematic_stage': [], 'not_applicable': [],
               'requirements_pending_downstream': [], 'input_request_count': 0}
    for cid, row in checks.items():
        result = row.get('review_result')
        clauses = row.get('requirement_clauses')
        staged_clause = False
        for clause in clauses if isinstance(clauses, list) else []:
            if not isinstance(clause, dict) or clause.get('na_reason') != OUTSIDE_STAGE:
                continue
            staged_clause = True
            linked = clause.get('check_ids')
            if not (clause.get('result') == 'NA' and isinstance(linked, list) and linked
                    and all(text(k) and k != cid and k in expected and outside_stage(checks.get(k, {}))
                            for k in linked)):
                errors.append(cid + ': downstream NA clause must link separate stage-NA checks with retained handoffs')
        if staged_clause:
            summary['requirements_pending_downstream'].append(cid)
        if result == 'NA':
            summary['outside_schematic_stage' if outside_stage(row) else 'not_applicable'].append(cid)
        if row.get('na_reason') == OUTSIDE_STAGE and not outside_stage(row):
            errors.append(cid + ': OUTSIDE_SCHEMATIC_STAGE requires NA')
        if outside_stage(row):
            planned_object = (expected.get(cid) or {}).get('object') if isinstance(expected.get(cid), dict) else None
            if (isinstance(planned_object, dict) and text(planned_object.get('requirement_id'))
                    and planned_object.get('aspect') not in catalog.STAGE_ASPECTS):
                errors.append(cid + ': a requirement row judges its design obligations (requirement_clauses); a test '
                              'obligation is one clause marked NA/OUTSIDE_SCHEMATIC_STAGE linked to its own stage-NA '
                              'check, not the whole row (only a %s row is stage NA as a whole)'
                              % '/'.join(catalog.STAGE_ASPECTS))
            if row.get('applicability') != 'APPLICABLE':
                errors.append(cid + ': stage NA keeps applicability APPLICABLE; the product requirement still applies')
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
        if result != 'INSUFFICIENT':
            if 'input_requests' in row:
                errors.append(cid + ': input_requests only belongs to INSUFFICIENT')
            continue
        cause = row.get('gap_cause')
        if expected.get(cid, {}).get('rule') == 'REQ-H02':
            continue  # history dispositions are counted apart
        if cause not in GAP_CAUSES:
            errors.append(cid + ': INSUFFICIENT requires gap_cause ' + '/'.join(GAP_CAUSES))
            continue
        requests = row.get('input_requests')
        if cause not in REQUEST_CAUSES:
            if 'input_requests' in row:
                errors.append(cid + ': input_requests only belongs to ' + '/'.join(REQUEST_CAUSES))
            continue
        missing = row.get('missing_inputs')
        if not (isinstance(requests, dict) and requests and isinstance(missing, list)
                and all(text(x) for x in missing) and len(missing) == len(set(missing)) and set(requests) == set(missing)):
            errors.append(cid + ': input_requests must be an object keyed by each missing_inputs entry')
            continue
        for key, request in requests.items():
            if not (isinstance(request, dict) and all(text(request.get(f)) for f in REQUEST_FIELDS)):
                errors.append(cid + ': input_requests[' + key + '] needs ' + '/'.join(REQUEST_FIELDS))
        summary['input_request_count'] += len(requests)
    return errors, summary

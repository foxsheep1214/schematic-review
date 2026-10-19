"""Test-side bridge: the older test builders write rows in the expanded (validator) view; the
validator reads schema 3. `record` writes such a ledger the way a reviewer writes schema 3, so a
test still states its case in the fields it is about. Not used by SR itself."""
import copy

import results_model
import validate_review as _validate_review

DEFAULTS = {'PASS': 'B', 'FAIL': 'B', 'INSUFFICIENT': 'C'}


# Older builders predate consequence classes; give them the class their level already implies,
# so a test that is not about classes still states a consistent row. Tests about classes set one.
LEVEL_CLASS = {'P0': 'CORE_LINK_LOSS', 'P1': 'REQUIRED_FUNCTION', 'P2': 'LOCAL_OR_DATA', 'P3': 'OPTIMIZATION'}


def _severity(level, assessment):
    assessment = assessment if isinstance(assessment, dict) else {}
    if 'consequence_class' not in assessment and level in LEVEL_CLASS:
        assessment = dict(assessment, consequence_class=LEVEL_CLASS[level])
        if level == 'P0':
            assessment.setdefault('hazard_path', 'PROTECTION_LOSS')
    out = {'level': level, 'class': assessment.get('consequence_class'),
           'affects': assessment.get('affected_function'), 'consequence': assessment.get('consequence')}
    for key in ('hazard_path', 'exclusion'):
        if key in assessment:
            out[key] = assessment[key]
    return {k: v for k, v in out.items() if v is not None}


def _gaps(row):
    requests, missing = row.get('input_requests'), row.get('missing_inputs')
    if isinstance(requests, dict) and requests:
        keys = [k for k in missing if k in requests] if isinstance(missing, list) else list(requests)
        keys += [k for k in requests if k not in keys]
        gaps = []
        for key in keys:
            req = requests[key] if isinstance(requests[key], dict) else {}
            gap = {'what': key, 'scope': req.get('required_scope'), 'how_to_close': req.get('acquisition'),
                   'closure_criterion': req.get('closure_criterion'), 'closure_domain': req.get('closure_domain')}
            level = req.get('potential_severity', row.get('potential_severity'))
            assessment = req.get('impact_assessment', row.get('impact_assessment'))
            if level is not None or assessment is not None:
                gap['severity'] = _severity(level, assessment)
            gaps.append({k: v for k, v in gap.items() if v is not None})
        return gaps
    if not isinstance(missing, list):
        return None
    gaps = []
    for key in missing:
        gap = {'what': key}
        assessment = row.get('impact_assessment')
        if isinstance(assessment, dict) and assessment.get('operating_condition'):
            gap['scope'] = assessment['operating_condition']
        if row.get('potential_severity') is not None or isinstance(assessment, dict):
            gap['severity'] = _severity(row.get('potential_severity'), assessment)
        gaps.append(gap)
    return gaps


def record(report):
    if not isinstance(report, dict) or report.get('schema_version') == results_model.SCHEMA_VERSION:
        return report
    out = copy.deepcopy(report)
    if out.get('schema_version') == 2:
        out['schema_version'] = results_model.SCHEMA_VERSION
    for key in results_model.RETIRED_TOP_FIELDS:
        out.pop(key, None)
    for row in out.get('checks') or []:
        if not isinstance(row, dict):
            continue
        result = row.get('review_result')
        if row.get('blocking') is True or (row.get('blocking') is False and result not in ('FAIL', 'INSUFFICIENT')):
            row.pop('blocking')
        if row.get('evidence_confidence') == DEFAULTS.get(result if isinstance(result, str) else None) or (
                result == 'NA' and row.get('evidence_confidence') in (None, 'B', 'C')):
            row.pop('evidence_confidence', None)
        if row.get('disposition') == 'OPEN':
            row.pop('disposition')
        if result == 'INSUFFICIENT':
            gaps = _gaps(row)
            if gaps is not None:
                row['gaps'] = gaps
            for key in results_model.RETIRED_ROW_FIELDS:
                row.pop(key, None)
    return out


def _whole_clauses(plan, report):
    """Older builders predate requirement_clauses. A REQ-D01 row that never mentions them gets the
    requirement as one obligation with the row's own result; tests about clauses always set the key."""
    rules = {c.get('id'): c for c in (plan or {}).get('checks') or [] if isinstance(c, dict) and isinstance(c.get('id'), str)}
    for row in report.get('checks') or []:
        planned = rules.get(row.get('id')) if isinstance(row, dict) and isinstance(row.get('id'), str) else None
        if (planned and planned.get('rule') == 'REQ-D01' and 'requirement_clauses' not in row
                and row.get('review_result') in ('PASS', 'FAIL', 'INSUFFICIENT')):
            row['requirement_clauses'] = [{'text': planned.get('criterion'), 'kind': 'OBLIGATION',
                                           'result': row['review_result']}]


def as_sent(plan, report):
    """The schema 3 ledger these test helpers hand to validate_review."""
    report = record(report)
    if isinstance(report, dict):
        report = copy.deepcopy(report)
        _whole_clauses(plan, report)
    return report


def validate_review(plan, report, *args, **kwargs):
    return _validate_review.validate_review(plan, as_sent(plan, report), *args, **kwargs)

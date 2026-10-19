"""review-results.json schema 3: what the reviewer writes, and the view the validators read.

The record keeps only what a reviewer decides. Everything that follows from it is derived here:
  blocking             true for FAIL/INSUFFICIENT, false otherwise; write false only on a FAIL/INSUFFICIENT
                       that does not block (a P2/P3 the phase allows to stay open)
  evidence_confidence  B for PASS/FAIL, C for INSUFFICIENT; write it only to claim A
  disposition          OPEN; write it only for FIXED_VERIFIED / ACCEPTED / RETRACTED
  missing_inputs, input_requests, potential_severity, impact_assessment  from `gaps`

An INSUFFICIENT row lists its gaps. Each gap is one thing that is missing:
  what               the missing fact, in one sentence (also the key a work item's request_keys names)
  scope              the states/corners it must cover
  how_to_close       where it comes from or how to work it out   (EXTERNAL_DATA / DESIGN_OPEN)
  closure_criterion  what counts as closed                       (EXTERNAL_DATA / DESIGN_OPEN)
  severity           {level, class, affects, consequence[, hazard_path][, exclusion]}
                     (every cause except REQUIREMENT_OPEN; the row's level is the worst gap's)
  closure_domain     isolation_qualification / loop_stability, on PRO-C03 and PWR-C15 gaps
                     (closure-obligations.md)
"""
import copy

SCHEMA_VERSION = 3
LEVELS = ('P0', 'P1', 'P2', 'P3')
REQUEST_CAUSES = ('EXTERNAL_DATA', 'DESIGN_OPEN')
# Fields schema 3 derives; a record that still writes them would carry two answers to one question.
RETIRED_ROW_FIELDS = {
    'missing_inputs': 'gaps[].what', 'input_requests': 'gaps', 'potential_severity': 'gaps[].severity.level',
    'impact_assessment': 'gaps[].severity',
}
RETIRED_TOP_FIELDS = ('binding_version', 'remediation_version', 'workflow_version', 'impact_class_version',
                      'requirement_clauses_version', 'requirement_clarification_version',
                      # lint findings are plan checks with their own result rows
                      'lint_reviews')
# Schema 3 always means the newest contract of each retired switch: consequence classes v2,
# REQ-D01 clauses, staged work items. Bindings and actionable instructions are required by
# validate_review's --require-bindings/--require-actionable.
IMPACT_CLASS_VERSION = 2
GAP_TEXT = ('what', 'scope', 'how_to_close', 'closure_criterion')
SEVERITY_TEXT = ('affects', 'consequence')


def text(value):
    return isinstance(value, str) and bool(value.strip())


def shape_errors(report, history_ids=()):
    """Errors in the record as written, named in schema 3 terms. `history_ids` are REQ-H02 rows,
    which carry history dispositions instead of graded gaps."""
    if not isinstance(report, dict):
        return ['results must be an object']
    if report.get('schema_version') != SCHEMA_VERSION:
        return ['results.schema_version must be 3; a schema 2 ledger is not read, review again with this SR']
    errors = ['results.%s is retired in schema 3 (the newest meaning always applies)' % k
              for k in RETIRED_TOP_FIELDS if k in report]
    for row in report.get('checks') or []:
        if not isinstance(row, dict):
            continue
        key = str(row.get('id', '?'))
        for field, instead in RETIRED_ROW_FIELDS.items():
            if field in row:
                errors.append('%s: %s is retired in schema 3; write %s' % (key, field, instead))
        if 'blocking' in row and not (row['blocking'] is False and row.get('review_result') in ('FAIL', 'INSUFFICIENT')):
            errors.append(key + ': blocking is derived; write it only as false on a FAIL/INSUFFICIENT that does not block')
        if row.get('evidence_confidence') in ('B', 'C'):
            errors.append(key + ': evidence_confidence is derived; write it only to claim A')
        if row.get('disposition') == 'OPEN':
            errors.append(key + ': disposition OPEN is the default; omit it')
        if row.get('review_result') != 'INSUFFICIENT':
            if 'gaps' in row:
                errors.append(key + ': gaps only belong to INSUFFICIENT')
            continue
        gaps = row.get('gaps')
        if not (isinstance(gaps, list) and gaps and all(isinstance(g, dict) for g in gaps)):
            errors.append(key + ': INSUFFICIENT needs gaps, a non-empty list of objects')
            continue
        whats = [g.get('what') for g in gaps]
        if not all(text(w) for w in whats) or len(set(whats)) != len(whats):
            errors.append(key + ': each gap needs a distinct what')
        cause = row.get('gap_cause')
        graded = cause != 'REQUIREMENT_OPEN' and key not in history_ids
        for g in gaps:
            label = '%s/%s' % (key, g.get('what'))  # noqa: str() of any id
            need = GAP_TEXT[1:] if cause in REQUEST_CAUSES else (('scope',) if graded else ())
            missing = [f for f in need if not text(g.get(f))]
            if missing:
                errors.append('%s: gap needs %s' % (label, '/'.join(missing)))
            if cause not in REQUEST_CAUSES and ('how_to_close' in g or 'closure_criterion' in g):
                errors.append(label + ': how_to_close/closure_criterion only belong to EXTERNAL_DATA/DESIGN_OPEN')
            severity = g.get('severity')
            if not graded:
                if severity is not None and cause == 'REQUIREMENT_OPEN':
                    errors.append(label + ': a requirement the owner has not decided is not graded; omit severity')
                continue
            if not isinstance(severity, dict):
                errors.append(label + ': gap needs severity {level, class, affects, consequence}')
                continue
            if severity.get('level') not in LEVELS:
                errors.append(label + ': severity.level is one of P0/P1/P2/P3')
            if not text(severity.get('class')):
                errors.append(label + ': severity.class required')
            missing = [f for f in SEVERITY_TEXT if not text(severity.get(f))]
            if missing:
                errors.append('%s: severity needs %s' % (label, '/'.join(missing)))
    return errors


def _impact(gap):
    s = gap.get('severity') or {}
    out = {'affected_function': s.get('affects'), 'operating_condition': gap.get('scope'),
           'consequence': s.get('consequence'),
           # Retired prose fields: the consequence is the reason for the level, the criterion the reason it blocks.
           'severity_reason': s.get('consequence'),
           'blocking_reason': gap.get('closure_criterion') or s.get('consequence'),
           'consequence_class': s.get('class')}
    for key in ('hazard_path', 'exclusion'):
        if key in s:
            out[key] = s[key]
    return out


def _worst(gaps):
    graded = [g for g in gaps if isinstance(g.get('severity'), dict) and g['severity'].get('level') in LEVELS]
    return min(graded, key=lambda g: LEVELS.index(g['severity']['level'])) if graded else None


def expand(report):
    """The validators' view of a schema 3 record (call after shape_errors is clean)."""
    out = copy.deepcopy(report)
    out.setdefault('requirement_clarifications', [])
    for row in out.get('checks') or []:
        if not isinstance(row, dict):
            continue
        result = row.get('review_result')
        row.setdefault('blocking', result in ('FAIL', 'INSUFFICIENT'))
        if result in ('PASS', 'FAIL'):
            row.setdefault('evidence_confidence', 'B')
        elif result == 'INSUFFICIENT':
            row.setdefault('evidence_confidence', 'C')
        row.setdefault('disposition', 'OPEN')
        gaps = row.pop('gaps', None)
        if result != 'INSUFFICIENT' or not isinstance(gaps, list):
            continue
        gaps = [g for g in gaps if isinstance(g, dict)]
        row['missing_inputs'] = [g.get('what') for g in gaps]
        if row.get('gap_cause') in REQUEST_CAUSES:
            row['input_requests'] = {g.get('what'): {
                'why_decisive': row.get('rationale'), 'required_scope': g.get('scope'),
                'acquisition': g.get('how_to_close'), 'closure_criterion': g.get('closure_criterion'),
                'potential_severity': (g.get('severity') or {}).get('level'),
                'impact_assessment': _impact(g),
                **({'closure_domain': g['closure_domain']} if 'closure_domain' in g else {})} for g in gaps}
        worst = _worst(gaps)
        if worst is not None:
            row['potential_severity'] = worst['severity']['level']
            row['impact_assessment'] = _impact(worst)
    return out

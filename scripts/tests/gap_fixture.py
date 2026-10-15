"""Complete synthetic INSUFFICIENT rows with the always-required gap record.

Every evidence gap carries gap_cause, potential impact and, for real input/design gaps,
input_requests keyed by missing_inputs. Fixtures that test something else use this
so their gaps stay honest without repeating the boilerplate.
"""
IMPACT = {k: 'Synthetic ' + k.replace('_', ' ') for k in
          ('affected_function', 'operating_condition', 'consequence', 'severity_reason', 'blocking_reason')}
REQUEST = {'why_decisive': 'Synthetic decisive input', 'required_scope': 'Synthetic bounded scope',
           'acquisition': 'Synthetic source', 'closure_criterion': 'Synthetic recheck'}


def complete_gap(row, cause='REVIEW_INCOMPLETE', severity='P2'):
    if row.get('review_result') != 'INSUFFICIENT':
        return row
    row.setdefault('gap_cause', cause)
    if row['gap_cause'] != 'REQUIREMENT_OPEN':
        row.setdefault('potential_severity', severity)
        row.setdefault('impact_assessment', dict(IMPACT))
    if row['gap_cause'] in ('EXTERNAL_DATA', 'DESIGN_OPEN') and 'input_requests' not in row:
        row['input_requests'] = {m: dict(REQUEST) for m in row.get('missing_inputs') or [] if isinstance(m, str)}
    return row


def complete_gaps(report, **kw):
    for row in report.get('checks') or []:
        if isinstance(row, dict):
            complete_gap(row, **kw)
    return report


def validating(validate):
    """Validator wrapper for tests whose subject is not the gap record itself."""
    def run(plan, report, *args, **kwargs):
        if isinstance(report, dict):
            complete_gaps(report)
        return validate(plan, report, *args, **kwargs)
    return run

"""Keep present checks, historical dispositions and handoffs separately visible."""
from collections import Counter
from review_stage_scope import outside_stage

RESULT_LABELS = {'PASS': '通过（PASS）', 'FAIL': '不符合（FAIL）', 'INSUFFICIENT': '证据不足（INSUFFICIENT）',
                 'NA': '不适用（NA）', 'NA_OUTSIDE_STAGE': '本阶段不判，移交下游（NA）'}
IMPACT_FIELDS = ('affected_function', 'operating_condition', 'consequence',
                 'severity_reason', 'blocking_reason')


# Consequence class -> potential level (verdicts-and-release.md 等级边界). A damage/hazard or
# core-link class drops to P1 only with a written independent exclusion of that path.
# impact_class_version 2 separates COMPONENT_DAMAGE (a part may be destroyed, nothing else
# follows: P1) from DAMAGE_OR_HAZARD, which then must name the hazard path it opens.
IMPACT_CLASSES = {'DAMAGE_OR_HAZARD': 'P0', 'CORE_LINK_LOSS': 'P0',
                  'COMPONENT_DAMAGE': 'P1',
                  'REQUIRED_FUNCTION': 'P1', 'PERFORMANCE_OR_LIFE': 'P1',
                  'LOCAL_OR_DATA': 'P2', 'OPTIMIZATION': 'P3'}
V2_ONLY_CLASSES = {'COMPONENT_DAMAGE'}
HAZARD_PATHS = ('FIRE', 'SHOCK', 'INSULATION', 'HAZARDOUS_ENERGY', 'PORT_OVERVOLTAGE', 'PROTECTION_LOSS')


def impact_class_errors(key, assessment, severity, version=1):
    classes = {k: v for k, v in IMPACT_CLASSES.items() if version >= 2 or k not in V2_ONLY_CLASSES}
    cls = assessment.get('consequence_class')
    if cls not in classes:
        return [f'{key}: impact_assessment.consequence_class is one of {"/".join(classes)}']
    expected = classes[cls]
    errors = []
    if version >= 2 and expected == 'P0' and assessment.get('hazard_path') not in HAZARD_PATHS:
        errors.append(f'{key}: {cls} needs impact_assessment.hazard_path one of {"/".join(HAZARD_PATHS)}; '
                      'a part that may be destroyed without opening one of these paths is COMPONENT_DAMAGE (P1)')
    excluded = isinstance(assessment.get('exclusion'), str) and assessment['exclusion'].strip()
    if severity == expected or (expected == 'P0' and severity == 'P1' and excluded):
        return errors
    hint = '; P1 needs impact_assessment.exclusion naming the independent protection' if expected == 'P0' else ''
    return errors + [f'{key}: consequence_class {cls} sets potential_severity {expected}, not {severity}{hint}']


def validate_impact(item, classes=False):
    """Check impact documentation, never infer a severity from missing evidence."""
    if item.get('review_result') != 'INSUFFICIENT' or item.get('gap_cause') == 'REQUIREMENT_OPEN':
        return []
    key = item.get('id', '?')
    assessment = item.get('impact_assessment')
    if not isinstance(assessment, dict):
        return [f'{key}: impact_assessment required for 证据不足']
    errors = [f'{key}: impact_assessment.{field} required' for field in IMPACT_FIELDS
              if not isinstance(assessment.get(field), str) or not assessment[field].strip()]
    if item.get('potential_severity') not in ('P0', 'P1', 'P2', 'P3'):
        errors.append(f'{key}: potential_severity required for impact assessment')
    if not isinstance(item.get('blocking'), bool):
        errors.append(f'{key}: blocking must be boolean for impact assessment')
    if classes:
        errors += impact_class_errors(key, assessment, item.get('potential_severity'), int(classes))
    return errors


def categorized_summary(checks, expected, findings, stage):
    def count(keys):
        # Stage NA is counted apart: the product requirement still applies and awaits downstream verification.
        return {'checks': len(keys), 'results': dict(Counter(
            'NA_OUTSIDE_STAGE' if outside_stage(checks[k]) else checks[k].get('review_result')
            for k in keys if isinstance(checks[k].get('review_result'), str)))}
    history = {k for k in checks if expected.get(k, {}).get('rule') == 'REQ-H02'}
    current = set(checks) - history
    gaps = [checks[k] for k in current if checks[k].get('review_result') == 'INSUFFICIENT']
    graded = [c for c in gaps if c.get('gap_cause') != 'REQUIREMENT_OPEN']
    documented = sum(not validate_impact(c) for c in graded)
    impact = {'by_potential_severity': {p: sum(c.get('potential_severity') == p for c in graded)
                                      for p in ('P0', 'P1', 'P2', 'P3')},
              'requirement_open': len(gaps) - len(graded),
              'unrated': sum(c.get('potential_severity') not in ('P0', 'P1', 'P2', 'P3') for c in graded),
              'documented': documented, 'undocumented': len(graded) - documented,
              'blocking': sum(c.get('blocking') is True for c in gaps),
              'by_consequence_class': dict(Counter(
                  (c.get('impact_assessment') or {}).get('consequence_class') for c in graded
                  if isinstance(c.get('impact_assessment'), dict)
                  and (c['impact_assessment'].get('consequence_class') in IMPACT_CLASSES))),
              'note': 'Documentation coverage does not prove engineering correctness; potential impact is not a confirmed defect.'}
    handoffs = {k: c['handoff'] for k, c in checks.items()
                if isinstance(c.get('handoff'), dict) and c['handoff'].get('required')}
    tasks = stage.get('tasks', [])
    return {'current': count(current), 'history': count(history),
            'result_labels': dict(RESULT_LABELS), 'insufficient_impact': impact,
            'unique_findings': len(findings), 'unique_work_items': len({t['id'] for t in tasks}),
            'work_item_check_links': len({k for t in tasks for k in t['check_ids']}),
            'required_handoffs': len(handoffs),
            'handoffs_by_state': dict(Counter(h.get('state') for h in handoffs.values() if isinstance(h.get('state'), str))),
            'note': 'Handoffs overlap checks; ACCEPTED means responsibility/constraints accepted, not physical verification.'}

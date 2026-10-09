"""Advisory pattern screening; never certify electrical reasoning or evidence.

Exact reused prose and disjoint explicit component references are review leads,
not defects. Shared proofs and indirect dependencies can be legitimate.
"""
from collections import defaultdict
import json
import re

# Potential-impact grading: one grade covering nearly every graded gap suggests batch grading.
UNIFORM_GRADE_MIN_ROWS = 10
UNIFORM_GRADE_SHARE = 0.9
IMPACT_TEXT_FIELDS = ('consequence', 'severity_reason')


def analysis_text(text, check):
    """Remove exact scope/criterion echoes from advisory prose comparisons.

    A binding is useful metadata but does not establish the copied paragraph's
    causal reasoning. Other JSON (such as independent calculations) is kept.
    """
    if not isinstance(text, str):
        return ''
    decoder = json.JSONDecoder()
    obj, criterion = check.get('object'), check.get('criterion')
    out, cursor = [], 0
    while cursor < len(text):
        start = text.find('{', cursor)
        if start < 0:
            out.append(text[cursor:])
            break
        out.append(text[cursor:start])
        try:
            value, length = decoder.raw_decode(text[start:])
        except ValueError:
            out.append('{')
            cursor = start + 1
            continue
        if value != obj and value != {'object': obj, 'criterion': criterion}:
            out.append(text[start:start + length])
        cursor = start + length
    result = ''.join(out)
    return result.replace(criterion, '') if isinstance(criterion, str) and criterion else result


def field_text(value):
    return ' '.join(x for x in value if isinstance(x, str)) if isinstance(value, list) else value


def screen_quality(plan, report, db=None):
    output = {'status': 'NOT_RUN', 'scope': 'ADVISORY_PATTERN_SCREENING_ONLY',
              'candidate_count': 0, 'flagged_check_count': 0, 'candidates': []}
    if not isinstance(plan, dict) or not isinstance(report, dict):
        return output
    if not isinstance(plan.get('checks'), list) or not isinstance(report.get('checks'), list):
        return output
    expected = {x['id']: x for x in plan['checks']
                if isinstance(x, dict) and isinstance(x.get('id'), str)}
    parts = db.get('parts', {}) if isinstance(db, dict) else {}
    known = {x for x in parts if isinstance(x, str) and x} if isinstance(parts, dict) else set()
    pattern = (re.compile(r'(?<![A-Za-z0-9_])(?:' + '|'.join(
        re.escape(x) for x in sorted(known, key=lambda x: (-len(x), x)))
        + r')(?![A-Za-z0-9_])') if known else None)

    def refs(value):
        return set(pattern.findall(value)) if pattern and isinstance(value, str) else set()

    # Check explicit locators against named source pins, as review leads only:
    # exporters and official docs can use legitimate aliases requiring mapping.
    pin_names = defaultdict(set)
    source_names = db.get('pinname', {}) if isinstance(db, dict) else {}
    if isinstance(source_names, dict):
        for node, name in source_names.items():
            if isinstance(node, str) and isinstance(name, str) and name:
                pin_names[node.partition('.')[0]].add(name)
    actual_statuses = {r['id']: r.get('review_result') for r in report['checks']
                       if isinstance(r, dict) and isinstance(r.get('id'), str)}
    candidates = output['candidates']
    for row in report['checks']:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str) or row['id'] not in expected:
            continue
        check = expected[row['id']]
        text = row.get('rationale')
        if not isinstance(text, str):
            continue
        for ref, name in re.findall(r'(?<![A-Za-z0-9_])([A-Za-z]+[0-9]+)\.([A-Za-z][A-Za-z0-9_]*)', text):
            names = pin_names.get(ref)
            physical = ref + '.' + name
            composed = re.fullmatch(r'(.+?)([0-9]+)', name)
            # Both physical pad labels (S5/B4) and NAME+physical-pin shorthand
            # are common exact locators. Only flag a demonstrated conflicting
            # numbered name where the source contains the proposed base name.
            conflicting = (composed and composed.group(1) in (names or set())
                           and ref + '.' + composed.group(2) in source_names
                           and source_names[ref + '.' + composed.group(2)] != composed.group(1))
            if physical not in source_names and names and name not in names and conflicting:
                candidates.append({'code': 'PIN_NAME_LOCATOR_NOT_IN_SOURCE',
                    'check_ids': [row['id']], 'locator': ref + '.' + name,
                    'source_pin_names': sorted(names),
                    'message': 'Explicit pin name is absent from the source map; verify physical pin and document any alias.'})
        if check.get('rule') != 'REQ-Q07':
            continue
        for cid, verdict in actual_statuses.items():
            if cid == row['id']:
                continue
            match = re.search(re.escape(cid) + r'(?![A-Za-z0-9_.-])\s*(?:[:=：]|is)?\s*(PASS|FAIL|INSUFFICIENT|NA)\b', text)
            if match and match.group(1) != verdict:
                candidates.append({'code': 'AGGREGATE_CHILD_STATUS_MISMATCH',
                    'check_ids': [row['id']], 'child_id': cid,
                    'stated_status': match.group(1), 'final_status': verdict,
                    'message': 'Aggregate text names a child with a different final result; reconcile the final member results.'})

    groups = defaultdict(list)
    impact_groups = defaultdict(list)
    grades = defaultdict(list)
    candidates = output['candidates']
    for row in report['checks']:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str):
            continue
        check = expected.get(row['id'])
        if (check and check.get('rule') != 'REQ-H02' and row.get('review_result') == 'INSUFFICIENT'
                and row.get('gap_cause') != 'REQUIREMENT_OPEN'):
            grades[row.get('potential_severity')].append(row['id'])
            assessment = row.get('impact_assessment')
            scope = json.dumps([check.get('rule'), check.get('object'), check.get('criterion')],
                               sort_keys=True, ensure_ascii=False)
            for field in IMPACT_TEXT_FIELDS:
                value = assessment.get(field) if isinstance(assessment, dict) else None
                if isinstance(value, str) and value.strip():
                    impact_groups[(field, re.sub(r'\s+', ' ', value).strip())].append((row['id'], scope))
        if not check or check.get('method') not in ('T', 'C', 'D', 'E', 'V'):
            continue  # automatic/coverage/history boilerplate is intentionally excluded
        rationale = row.get('rationale')
        if isinstance(rationale, str) and rationale.strip():
            normalized = re.sub(r'\s+', ' ', rationale).strip()
            scope = json.dumps([check.get('rule'), check.get('object'), check.get('criterion')],
                               sort_keys=True, ensure_ascii=False)
            groups[(str(row.get('review_result')), normalized)].append((row['id'], scope))
        obj = check.get('object')
        obj = obj if isinstance(obj, dict) else {}
        wanted = refs(check.get('criterion')) | refs(obj.get('ref')) | refs(obj.get('node'))
        if isinstance(obj.get('refs'), list):
            for ref in obj['refs']:
                wanted.update(refs(ref))
        observed = refs(rationale)
        if isinstance(row.get('evidence'), list):
            for item in row['evidence']:
                if isinstance(item, dict):
                    observed.update(refs(item.get('locator')))
        if wanted and observed and wanted.isdisjoint(observed):
            candidates.append({'code': 'REFERENCED_OBJECT_OUTSIDE_SCOPE',
                'check_ids': [row['id']], 'expected_refs': sorted(wanted),
                'observed_refs': sorted(observed),
                'message': 'Check the source and dependency: explicit refs do not overlap the declared scope.'})
        # Inspect causal fields independently: a correct locator or scope echo
        # must not launder a consequence copied from an unrelated circuit.
        assessment = row.get('impact_assessment')
        for field in IMPACT_TEXT_FIELDS:
            text = assessment.get(field) if isinstance(assessment, dict) else None
            actual = refs(analysis_text(text, check))
            if wanted and actual and wanted.isdisjoint(actual):
                candidates.append({'code': 'IMPACT_REFERENCES_OUTSIDE_SCOPE',
                    'field': field, 'check_ids': [row['id']],
                    'expected_refs': sorted(wanted), 'observed_refs': sorted(actual),
                    'message': 'Trace this consequence independently of the rationale and evidence locator; shared dependencies need an explicit scope.'})
        if check.get('rule') == 'PWR-C10':
            targets = check.get('qualification_refs')
            if targets is None:  # Existing plans already bind the fitted material refs.
                materials = check.get('required_material_refs')
                targets = [r for r in materials if isinstance(r, str) and r != obj.get('ref')] if isinstance(materials, list) else []
            targets = {r for r in targets if isinstance(r, str)} & known if isinstance(targets, list) else set()
            actual = refs(analysis_text(field_text(row.get('missing_inputs')), check))
            if targets and actual and targets.isdisjoint(actual):
                candidates.append({'code': 'QUALIFICATION_INPUT_TARGET_MISMATCH',
                    'field': 'missing_inputs', 'check_ids': [row['id']],
                    'expected_refs': sorted(targets), 'observed_refs': sorted(actual),
                    'message': 'Capacitor rating evidence must qualify the fitted capacitors; connector/device identity is a separate claim.'})
        if check.get('rule') == 'SIG-T04' and check.get('package') == 'USB':
            text = analysis_text(rationale, check)
            other = re.search(r'(?<![A-Za-z0-9_])(?:UART|SPI|TXD\d*|RXD\d*|PICO|POCI)(?![A-Za-z0-9_])', text, re.I)
            usb = re.search(r'USB|D[+-]|(?<![A-Za-z0-9_])(?:DP|DM|Host|Device|Source|Sink)(?![A-Za-z0-9_])', text, re.I)
            if other and not usb:
                candidates.append({'code': 'INTERFACE_ANALYSIS_MODE_MISMATCH',
                    'field': 'rationale', 'check_ids': [row['id']],
                    'declared_package': 'USB',
                    'message': 'USB direction reasoning only names UART/SPI roles; verify the actual USB endpoint roles instead of the scope echo.'})
    for group in groups.values():
        if len({scope for _, scope in group}) > 1:
            candidates.append({'code': 'REUSED_RATIONALE_ACROSS_SCOPES',
                'check_ids': sorted({cid for cid, _ in group}),
                'message': 'Different scopes reuse identical reasoning; verify each criterion or document the shared proof.'})
    for (field, _), group in impact_groups.items():
        if len({scope for _, scope in group}) > 1:
            candidates.append({'code': 'REUSED_IMPACT_ACROSS_SCOPES', 'field': field,
                'check_ids': sorted({cid for cid, _ in group}),
                'message': 'Different criteria share identical impact text; trace each consequence path '
                           'or state how the shared analysis applies to each criterion.'})
    graded = sum(len(v) for v in grades.values())
    for grade, ids in grades.items():
        if graded >= UNIFORM_GRADE_MIN_ROWS and len(ids) >= UNIFORM_GRADE_SHARE * graded:
            candidates.append({'code': 'UNIFORM_POTENTIAL_SEVERITY', 'grade': grade,
                'check_ids': sorted(ids),
                'message': f'{len(ids)} of {graded} graded evidence gaps share one potential grade; '
                           'confirm each was graded from its own consequence path, not by default.'})
    candidates.sort(key=lambda x: (x['code'], x['check_ids']))
    output.update(status='NEEDS_SEMANTIC_REVIEW' if candidates else 'NO_PATTERN_DETECTED',
                  candidate_count=len(candidates),
                  flagged_check_count=len({cid for x in candidates for cid in x['check_ids']}))
    return output

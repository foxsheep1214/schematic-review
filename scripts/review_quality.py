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
# 定级模板：同一句带等级的话出现在多条不同规则的定级理由里，说明等级来自默认句而非本行后果路径。
TEMPLATE_MIN_ROWS, TEMPLATE_MIN_RULES = 10, 3
GRADE_RE = re.compile(r'P[0-3]')
# 同规则整批同级：本规则至少这么多行证据不足且全部同级时提示逐行定级。
RULE_UNIFORM_MIN_ROWS = 10
# 下游分流线索：缺口文字只指向样机/试验结果，或把优化目标记成阻断缺口。关键词只生成提示，不改结论。
DOWNSTREAM_RE = re.compile(r'实测|样机|样品|闭壳|温升测试|热测|EMC|传导|辐射|认证|一致性测试|兼容性测试|寿命试验|'
                           r'能效测试|整机测试|插墙|PCB寄生|实际寄生|实物波形|prototype|bench|compliance|certif', re.I)
DESIGN_GAP_RE = re.compile(r'未选|未定|缺少?手册|缺资料|无资料|未计算|未建模|未连接|未设计|改图|越限|超出额定|不满足')
OPTIMIZATION_RE = re.compile(r'优化目标|成本|体积|报价|尽量|cost|volume', re.I)
# 冻结阶段把以下两类提示当作“定级未完成”的放行阻断，不改变 valid。
FREEZE_BLOCKING_CODES = ('TEMPLATED_SEVERITY_REASON', 'UNIFORM_SEVERITY_WITHIN_RULE')
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
        # A missing temperature maximum is not a fault deadline. This is an
        # advisory only: prose may already cite a valid shared proof, so never
        # mutate verdicts or infer a numeric safety limit from keywords.
        if row.get('review_result') in ('FAIL', 'INSUFFICIENT'):
            assessment = row.get('impact_assessment') or {}
            severity = row.get('severity') or row.get('potential_severity')
            blocked = row.get('blocking') is True or severity in ('P0', 'P1')
            timing = re.search(r'关断|关闭|响应|延迟|时延|turn.?off|response|delay', text, re.I)
            corner = re.search(r'全温|最大时间|最大时|最大延|maximum|full.?temp', text, re.I)
            a = row.get('timing_assessment')
            fields = ('scenario', 'consequence', 'allowed_window', 'response_bound',
                      'margin', 'temperature_scope', 'closure_stage')
            direct = isinstance(a, dict) and all(isinstance(a.get(k), str) and a[k].strip() for k in fields)
            links = a.get('evidence') if isinstance(a, dict) else None
            linked = isinstance(links, list) and bool(links) and all(
                isinstance(e, dict) and all(isinstance(e.get(k), str) and e[k].strip()
                                          for k in ('source', 'locator')) for e in links)
            if blocked and timing and corner and not (direct or linked):
                candidates.append({'code': 'TIMING_BLOCK_WITHOUT_WINDOW',
                    'check_ids': [row['id']],
                    'message': 'Timing/temperature-max gap is used in a blocking judgment. '
                               'Locate the fault consequence, allowed window, response bound and margin; '
                               'UNKNOWN with a physical reason is valid. Review stage allocation manually; '
                               'this advisory neither waives a real protection gap nor certifies a supplied field.'})
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
        listed = set()
        for cid, verdict in actual_statuses.items():
            if cid == row['id']:
                continue
            match = re.search(re.escape(cid) + r'(?![A-Za-z0-9_.-])\s*(?:[:=：]|is)?\s*(PASS|FAIL|INSUFFICIENT|NA)\b', text)
            if match:
                listed.add(cid)
            if match and match.group(1) != verdict:
                candidates.append({'code': 'AGGREGATE_CHILD_STATUS_MISMATCH',
                    'check_ids': [row['id']], 'child_id': cid,
                    'stated_status': match.group(1), 'final_status': verdict,
                    'message': 'Aggregate text names a child with a different final result; reconcile the final member results.'})
        obj = check.get('object')
        package = check.get('package') or (obj.get('package') if isinstance(obj, dict) else None)
        if isinstance(package, str) and package and listed:
            def child_package(child):
                obj = child.get('object')
                return child.get('package') or (obj.get('package') if isinstance(obj, dict) else None)
            # Explicit plan scope only. Unpackaged physical dependencies cannot
            # be assigned by a shared rule prefix or a prose keyword.
            wrong = sorted(cid for cid in listed if cid in expected
                           and child_package(expected[cid])
                           and child_package(expected[cid]) != package)
            if wrong:
                candidates.append({'code': 'AGGREGATE_CHILD_PACKAGE_MISMATCH',
                    'check_ids': [row['id']], 'package': package, 'child_ids': wrong,
                    'message': 'Listed checks have another explicit package. Verify membership or document the real cross-package dependency; this advisory does not reject legitimate shared proofs.'})
            members = {cid for cid, child in expected.items()
                       if cid != row['id'] and child.get('rule') != 'REQ-Q07'
                       and child_package(child) == package}
            missing = sorted(members - listed)
            if missing:
                candidates.append({'code': 'AGGREGATE_PACKAGE_MEMBERS_MISSING',
                    'check_ids': [row['id']], 'package': package, 'child_ids': missing,
                    'message': 'An explicit child/status list omits checks bound to this package. Reconcile the complete plan scope; unbound electrical dependencies still require expert tracing.'})

    groups = defaultdict(list)
    impact_groups = defaultdict(list)
    grades = defaultdict(list)
    rule_grades, templates = defaultdict(list), defaultdict(list)
    downstream_ids, optimization_ids = [], []
    candidates = output['candidates']
    for row in report['checks']:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str):
            continue
        check = expected.get(row['id'])
        if (check and check.get('rule') != 'REQ-H02' and row.get('review_result') == 'INSUFFICIENT'
                and row.get('gap_cause') != 'REQUIREMENT_OPEN'):
            grades[row.get('potential_severity')].append(row['id'])
            cause = row.get('gap_cause')
            gap_text = ' '.join(x for x in (row.get('missing_inputs') or []) if isinstance(x, str))
            if cause in ('DESIGN_OPEN', 'EXTERNAL_DATA') and DOWNSTREAM_RE.search(gap_text) \
                    and not DESIGN_GAP_RE.search(gap_text):
                downstream_ids.append(row['id'])
            if OPTIMIZATION_RE.search(str(check.get('criterion') or '') + ' ' + str(row.get('rationale') or '')) \
                    and row.get('potential_severity') in ('P0', 'P1'):
                optimization_ids.append(row['id'])
            rule_grades[check.get('rule')].append((row['id'], row.get('potential_severity')))
            assessment = row.get('impact_assessment')
            reason = assessment.get('severity_reason') if isinstance(assessment, dict) else None
            if isinstance(reason, str):
                for sentence in {x.strip() for x in re.split(r'[。；;\n]', reason)}:
                    if GRADE_RE.search(sentence):
                        templates[sentence].append((row['id'], check.get('rule')))
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
    for sentence, group in templates.items():
        if len(group) >= TEMPLATE_MIN_ROWS and len({rule for _, rule in group}) >= TEMPLATE_MIN_RULES:
            candidates.append({'code': 'TEMPLATED_SEVERITY_REASON', 'field': 'severity_reason',
                'template': sentence[:120], 'check_ids': sorted({cid for cid, _ in group}),
                'message': f'{len(group)} evidence gaps across rules justify their grade with the same sentence; '
                           'grade each row from its own consequence path (P0/P1 need an object-specific path).'})
    if downstream_ids:
        candidates.append({'code': 'DOWNSTREAM_RECORDED_AS_DESIGN_GAP', 'check_ids': sorted(downstream_ids),
            'message': 'Missing inputs only name prototype/test results. Judge the schematic prerequisites in their own '
                       'checks; record the test obligation as DOWNSTREAM_VERIFICATION with a handoff, not DESIGN_OPEN.'})
    if optimization_ids:
        candidates.append({'code': 'OPTIMIZATION_TARGET_AS_BLOCKING_GAP', 'check_ids': sorted(optimization_ids),
            'message': 'A cost/volume/optimization target is graded P0/P1. If the requirement is a goal rather than a '
                       'mandatory limit, record it as IMPROVEMENT or P3 once mandatory requirements pass.'})
    tasks = report.get('work_items') if isinstance(report.get('work_items'), list) else []
    causes = {r['id']: r.get('gap_cause') for r in report['checks'] if isinstance(r, dict) and isinstance(r.get('id'), str)}
    for task in tasks:
        if isinstance(task, dict) and task.get('due_stage') == 'design_iteration' and isinstance(task.get('check_ids'), list):
            linked = [cid for cid in task['check_ids'] if causes.get(cid) == 'DOWNSTREAM_VERIFICATION']
            if linked:
                candidates.append({'code': 'DOWNSTREAM_IN_CURRENT_ITERATION', 'work_item': task.get('id'),
                    'check_ids': sorted(linked),
                    'message': 'Downstream-only gaps are scheduled into the current design iteration; move them to a '
                               'prototype_verification task so the design queue holds only design work.'})
    for rule, group in rule_grades.items():
        levels = {grade for _, grade in group}
        if len(group) >= RULE_UNIFORM_MIN_ROWS and len(levels) == 1:
            candidates.append({'code': 'UNIFORM_SEVERITY_WITHIN_RULE', 'rule': rule, 'grade': levels.pop(),
                'check_ids': sorted(cid for cid, _ in group),
                'message': f'All {len(group)} evidence gaps of {rule} share one potential grade; '
                           'objects of one rule (bypass cap vs. bulk high-voltage resistor) rarely share one consequence.'})
    candidates.sort(key=lambda x: (x['code'], x['check_ids']))
    output.update(status='NEEDS_SEMANTIC_REVIEW' if candidates else 'NO_PATTERN_DETECTED',
                  candidate_count=len(candidates),
                  flagged_check_count=len({cid for x in candidates for cid in x['check_ids']}))
    return output

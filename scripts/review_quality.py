"""Advisory pattern screening; never certify electrical reasoning or evidence.

Exact reused prose and disjoint explicit component references are review leads,
not defects. Shared proofs and indirect dependencies can be legitimate.
"""
from collections import defaultdict
from pathlib import Path
import results_model
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
                           r'能效测试|整机测试|PCB寄生|实际寄生|实物波形|prototype|bench|compliance|certif', re.I)
# “插墙”是应用场景不是下游验证（R3 的 F101 分断缺口因此被误标，R4 证实为 P0 缺陷）。
# 写明随后/留给下游的分句已把下游部分分出，只看其余文字；整条都是这种分句时仍按原文判。
DEFERRED_CLAUSE_RE = re.compile(r'[^；;，,。]*(?:随后|留给|留待|另行|后续|移交|交由|另验)[^；;，,。]*')
DESIGN_GAP_RE = re.compile(r'未选|未定|缺少?手册|缺资料|无资料|未计算|未建模|未连接|未设计|改图|越限|超出额定|不满足')
OPTIMIZATION_RE = re.compile(r'优化目标|成本|体积|报价|尽量|cost|volume', re.I)
# 冻结阶段把以下两类提示当作“定级未完成”的放行阻断，不改变 valid。
# Review records whose citation as evidence for a current conclusion suggests reuse of an earlier review.
REVIEW_ARTIFACTS = {'review-results.json', 'review-gate.json', '审查报告.md', 'review-ledger.json'}
RECORD_FIELD_NAMES = {'missing_inputs': 'gaps[].what', 'required_scope': 'gaps[].scope',
                      'acquisition': 'gaps[].how_to_close', 'closure_criterion': 'gaps[].closure_criterion',
                      'consequence': 'gaps[].severity.consequence', 'affected_function': 'gaps[].severity.affects',
                      'potential_severity': 'gaps[].severity.level'}
FREEZE_BLOCKING_CODES = ('TEMPLATED_SEVERITY_REASON', 'UNIFORM_SEVERITY_WITHIN_RULE')
# 资料获取方式/无改图理由模板：同一句话服务于多件待办时，说明没有按对象写出真实来源或真实替代方案。
ACQUISITION_MIN_TASKS = 3
DESIGN_OPTION_MIN_TASKS = 3
IMPACT_TEXT_FIELDS = ('consequence',)  # schema 3 derives severity_reason from it


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


def _decisive_part(what):
    """A gap text without the side clauses that already defer something downstream."""
    rest = DEFERRED_CLAUSE_RE.sub('', what)
    return rest if rest.strip(' ；;，,。') else what


def screen_quality(plan, report, db=None):
    if isinstance(report, dict):
        report = results_model.expand(report)
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
    # Suggest localization, never split or change a verdict without evidence.
    task_owners = defaultdict(set)
    for task in report.get('work_items') or []:
        if (isinstance(task, dict) and isinstance(task.get('id'), str)
                and isinstance(task.get('check_ids'), list)):
            for cid in task['check_ids']:
                if isinstance(cid, str):
                    task_owners[cid].add(task['id'])
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
        if (check and (check.get('object') or {}).get('board')
                and check.get('rule') in ('DEV-C01', 'DEV-C02', 'DEV-C03', 'DEV-C04')
                and row.get('review_result') in ('FAIL', 'INSUFFICIENT')
                and not row.get('split_out')):
            candidates.append({'code': 'BROAD_CHECK_NEEDS_LOCALIZATION',
                'check_ids': [row['id']], 'task_ids': sorted(task_owners[row['id']]),
                'message': 'Identify the actual refs and independent criteria; add each to the plan as a same-rule check ' + check['rule'] + '.<ref>[-<criterion>] and list it in this row\'s split_out. Keep the residual result evidence-based; never auto-PASS the board or duplicate equivalent children.'})
        if (check and check.get('rule') != 'REQ-H02' and row.get('review_result') == 'INSUFFICIENT'
                and row.get('gap_cause') != 'REQUIREMENT_OPEN'):
            grades[row.get('potential_severity')].append(row['id'])
            cause = row.get('gap_cause')
            gap_text = ' '.join(_decisive_part(x) for x in (row.get('missing_inputs') or []) if isinstance(x, str))
            if cause in ('DESIGN_OPEN', 'EXTERNAL_DATA') and DOWNSTREAM_RE.search(gap_text) \
                    and not DESIGN_GAP_RE.search(gap_text):
                downstream_ids.append(row['id'])
            if OPTIMIZATION_RE.search(str(check.get('criterion') or '') + ' ' + str(row.get('rationale') or '')) \
                    and row.get('potential_severity') in ('P0', 'P1'):
                optimization_ids.append(row['id'])
            rule_grades[check.get('rule')].append((row['id'], row.get('potential_severity')))
            assessment = row.get('impact_assessment')
            reason = assessment.get('consequence') if isinstance(assessment, dict) else None
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
        # Criteria that one work item owns outright share that item's root cause; the
        # same consequence sentence there is the task's analysis, not a copy across scopes.
        common = None
        for cid, _ in group:
            owners_of = task_owners.get(cid) or set()
            common = set(owners_of) if common is None else common & owners_of
        if len({scope for _, scope in group}) > 1 and not common:
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
            candidates.append({'code': 'TEMPLATED_SEVERITY_REASON', 'field': 'consequence',
                'template': sentence[:120], 'check_ids': sorted({cid for cid, _ in group}),
                'message': f'{len(group)} evidence gaps across rules justify their grade with the same sentence; '
                           'grade each row from its own consequence path (P0/P1 need an object-specific path).'})
    if downstream_ids:
        candidates.append({'code': 'DOWNSTREAM_RECORDED_AS_DESIGN_GAP', 'check_ids': sorted(downstream_ids),
            'message': 'Missing inputs only name prototype/test results. Judge the schematic prerequisites in their own '
                       'checks; record the pure test obligation as NA / OUTSIDE_SCHEMATIC_STAGE with a handoff. '
                       'Keep decisive schematic input gaps INSUFFICIENT with specific input requests.'})
    if optimization_ids:
        candidates.append({'code': 'OPTIMIZATION_TARGET_AS_BLOCKING_GAP', 'check_ids': sorted(optimization_ids),
            'message': 'A cost/volume/optimization target is graded P0/P1. If the requirement is a goal rather than a '
                       'mandatory limit, record it as IMPROVEMENT or P3 once mandatory requirements pass.'})
    for rule, group in rule_grades.items():
        levels = {grade for _, grade in group}
        if len(group) >= RULE_UNIFORM_MIN_ROWS and len(levels) == 1:
            candidates.append({'code': 'UNIFORM_SEVERITY_WITHIN_RULE', 'rule': rule, 'grade': levels.pop(),
                'check_ids': sorted(cid for cid, _ in group),
                'message': f'All {len(group)} evidence gaps of {rule} share one potential grade; '
                           'objects of one rule (bypass cap vs. bulk high-voltage resistor) rarely share one consequence.'})
    cited_reviews = sorted(
        row['id'] for row in report['checks'] if isinstance(row, dict) and isinstance(row.get('id'), str)
        and row['id'] in expected
        and expected[row['id']].get('rule') != 'REQ-H02'
        and any(isinstance(ev, dict) and isinstance(ev.get('source'), str)
                and ev['source'].replace('\\', '/').rsplit('/', 1)[-1] in REVIEW_ARTIFACTS
                for ev in row.get('evidence') or []))
    if cited_reviews:
        candidates.append({'code': 'CURRENT_CHECK_CITES_REVIEW_RECORD', 'check_ids': cited_reviews,
            'message': 'A current conclusion cites a review results/gate/report file. If it is an earlier review, '
                       're-derive the conclusion from current sources and declare the file in history_inputs.'})
    candidates.extend(templated_task_text(report, expected))
    candidates.extend(unreconciled_history(report, expected, (plan or {}).get("review_mode")))
    candidates.extend(work_item_consistency(report))
    candidates.extend(text_hygiene(report, expected, known))
    candidates.extend(port_overvoltage_grading(report))
    candidates.extend(scope_echoes_task(report))
    candidates.extend(templated_handoffs(report))
    candidates.extend(stage_and_cause_misfiles(report, expected))
    nets = db.get('nets', {}) if isinstance(db, dict) else {}
    candidates.extend(duplicate_work_items(report, known | {n.rsplit('/', 1)[-1] for n in nets if isinstance(n, str) and n} if isinstance(nets, dict) else known))
    for candidate in candidates:  # name fields the way a schema 3 record writes them
        if candidate.get('field') in RECORD_FIELD_NAMES:
            candidate['field'] = RECORD_FIELD_NAMES[candidate['field']]
    candidates.sort(key=lambda x: (x['code'], x['check_ids']))
    output.update(status='NEEDS_SEMANTIC_REVIEW' if candidates else 'NO_PATTERN_DETECTED',
                  candidate_count=len(candidates),
                  flagged_check_count=len({cid for x in candidates for cid in x['check_ids']}))
    return output


def unreconciled_history(report, expected, review_mode=None):
    """Earlier findings declared in history_inputs that no REQ-H02 row reconciles."""
    roots = [x for x in report.get('history_inputs') or [] if isinstance(x, str)]
    rows = [row for row in report.get('checks') or [] if isinstance(row, dict)]
    # A first review cannot hold REQ-H02 rows; earlier findings are re-verified by a revision review.
    if review_mode != 'revision' or not roots or any(expected.get(row.get('id'), {}).get('rule') == 'REQ-H02' for row in rows):
        return []
    found = []
    for root in roots:
        base = Path(root)
        source = next((c for c in (base, base / 'review-results.json', base / 'record' / 'review-results.json')
                       if c.name == 'review-results.json' and c.is_file()), None)
        if source is None:
            continue
        try:
            prior = json.loads(source.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        ids = sorted(f['id'] for f in (prior.get('findings') or []) if isinstance(prior, dict)
                     and isinstance(f, dict) and isinstance(f.get('id'), str))
        if ids:
            found.append({'code': 'HISTORY_FINDINGS_UNRECONCILED', 'check_ids': [], 'source': str(source),
                          'finding_ids': ids,
                          'message': '%d earlier finding(s) in a declared history input have no REQ-H02 row; '
                                     'record fixed/kept/withdrawn per finding, or state why none applies.' % len(ids)})
    return found


def _scope(check):
    return json.dumps([check.get('rule'), check.get('object')], sort_keys=True, ensure_ascii=False)


def _rows(report):
    return {r['id']: r for r in report.get('checks') or [] if isinstance(r, dict) and isinstance(r.get('id'), str)}


def _owned_branches(task, row):
    """(level, hazard_path) of every branch this task owns on one INSUFFICIENT row."""
    requests = row.get('input_requests') if isinstance(row.get('input_requests'), dict) else {}
    keys = (task.get('request_keys') or {}).get(row['id']) if isinstance(task.get('request_keys'), dict) else None
    picked = [requests[k] for k in keys if isinstance(requests.get(k), dict)] if isinstance(keys, list) else []
    if picked:
        return [(q.get('potential_severity'), (q.get('impact_assessment') or {}).get('hazard_path')
                 if isinstance(q.get('impact_assessment'), dict) else None) for q in picked]
    assessment = row.get('impact_assessment') if isinstance(row.get('impact_assessment'), dict) else {}
    return [(row.get('potential_severity'), assessment.get('hazard_path'))]


def work_item_consistency(report):
    """A work item is one root cause: its P0 branches share one hazard path and it does not
    present P1 checks under a P0 heading. Leads only; the item's level is still the worst branch."""
    found = []
    rows = _rows(report)
    for task in report.get('work_items') or []:
        if not isinstance(task, dict) or not isinstance(task.get('id'), str) or not isinstance(task.get('check_ids'), list):
            continue
        by_level, paths = defaultdict(list), defaultdict(set)
        for cid in task['check_ids']:
            row = rows.get(cid) if isinstance(cid, str) else None
            if not row or row.get('review_result') != 'INSUFFICIENT' or row.get('gap_cause') == 'REQUIREMENT_OPEN':
                continue
            for level, path in _owned_branches(task, row):
                by_level[level].append(cid)
                if level == 'P0':
                    paths[path].add(cid)
        lower = sorted({cid for level, ids in by_level.items() if level != 'P0' for cid in ids})
        if by_level.get('P0') and lower:
            found.append({'code': 'WORK_ITEM_MIXES_LEVELS', 'task_ids': [task['id']],
                          'check_ids': lower, 'p0_check_ids': sorted(set(by_level['P0'])),
                          'message': f"{task['id']} is headed P0 but owns {len(lower)} lower-level branch(es); "
                                     'give them their own item or state in the item why they share the P0 root cause.'})
        if len(paths) > 1:
            found.append({'code': 'WORK_ITEM_MIXES_HAZARD_PATHS', 'task_ids': [task['id']],
                          'check_ids': sorted({cid for ids in paths.values() for cid in ids}),
                          'hazard_paths': sorted(str(k) for k in paths),
                          'message': f"{task['id']} bundles P0 branches with different hazard paths "
                                     f"({', '.join(sorted(str(k) for k in paths))}); one root cause opens one path, split the item."})
    return found


# 位号后面直接粘着数值（R604100°C、C5021.1uF）：读者分不清位号和数值；这是写法问题，不改结论。
TOKEN_RE = re.compile(r'(?<![A-Za-z0-9_])([A-Z]{1,4})(\d+)(?![A-Za-z_])')
# 通过条件里的三位以上小数（257.121uA、.27647mA）是审查员算例的中间值，不是设计者能凑的判据。
OVERPRECISE_RE = re.compile(r'(?<![0-9.])\d*\.\d{3,}(?![\d.])')
# 缺资料请求至少写出查过哪份资料的哪一页/表/条款仍没有该数据。
LOOKUP_RE = re.compile(r'(?:(?<![A-Za-z])pp?\.?\s*\d+|(?<![A-Za-z])page\s*\d+|第\s*\d+\s*[页节条章]|\d+\s*页|表\s*[\dA-Z]|\bTable\s*\d|'
                       r'\bFig(?:ure)?\.?\s*\d|图\s*\d|§\s*\d|\d+\.\d+(?:\.\d+)*\s*[条节款]|条款\s*\d|\bRev\.?\s*[\dA-Z])', re.I)
ACQUIRE_RE = re.compile(r'^\s*(?:先?由|向|请|找|从|待)|取得|索取|提供|询|索要')


# 端口过压送到外部负载是 PORT_OVERVOLTAGE 危险路径（P0 类），不因“只坏负载”降为器件损坏或功能项。
PORT_OV_RE = re.compile(r'(?:端口|USB|VBUS|合同|负载)[^。；;]{0,16}过压|过压[^。；;]{0,16}(?:端口|负载|USB|VBUS)|负载损坏|port\s*over-?voltage', re.I)
# 否定/转交句（“未据此推断端口过压”“端口过压另由 W-OVP 核”）不是正向后果断言。
PORT_OV_NEGATED_RE = re.compile(r'(?:未|不|没有|并非|无法|不能|不会|非)[^。；;]{0,12}(?:推断|认定|构成|建立|导致|视为|判为|形成|证明)[^。；;]{0,24}过压'
                                r'|过压[^。；;]{0,16}(?:另|单独|由)[^。；;]{0,12}(?:核|列|审|处理)|不(?:涉及|属于)[^。；;]{0,8}过压')


def _asserts_port_overvoltage(text):
    for sentence in re.split(r'[。；;\n]', text or ''):
        if PORT_OV_RE.search(sentence) and not PORT_OV_NEGATED_RE.search(sentence):
            return True
    return False
P0_CLASSES = {'DAMAGE_OR_HAZARD', 'CORE_LINK_LOSS'}
# 移交表：同一句约束只换了检查编号，不是逐条可销项的要求。
HANDOFF_MIN_ROWS = 3


def port_overvoltage_grading(report):
    found = []
    for row in report.get('checks') or []:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str):
            continue
        if row.get('review_result') not in ('INSUFFICIENT', 'FAIL'):
            continue
        assessment = row.get('impact_assessment') if isinstance(row.get('impact_assessment'), dict) else {}
        if assessment.get('consequence_class') in P0_CLASSES or assessment.get('hazard_path') == 'PORT_OVERVOLTAGE':
            continue
        text = ' '.join(str(assessment.get(f) or '') for f in ('consequence', 'severity_reason', 'affected_function'))
        text += ' ' + str(row.get('rationale') or '')
        if _asserts_port_overvoltage(text):
            found.append({'code': 'PORT_OVERVOLTAGE_GRADED_BELOW_P0', 'check_ids': [row['id']],
                          'consequence_class': assessment.get('consequence_class'),
                          'message': 'The consequence text describes overvoltage reaching the port or its load, but the class '
                                     'hides that path: grade it DAMAGE_OR_HAZARD / PORT_OVERVOLTAGE; when a latched OVP with '
                                     'evidenced threshold is the reason it stays P1, keep that class and write the exclusion, '
                                     'not COMPONENT_DAMAGE or REQUIRED_FUNCTION.'})
    return found


def scope_echoes_task(report):
    """required_scope that only repeats the task title/root cause states no operating range."""
    found = []
    rows = _rows(report)
    for task in report.get('work_items') or []:
        if not isinstance(task, dict) or not isinstance(task.get('id'), str):
            continue
        names = [task.get(f) for f in ('title', 'root_cause') if isinstance(task.get(f), str) and task[f].strip()]
        if not names:
            continue
        echoed = set()
        for cid in task.get('check_ids') or []:
            row = rows.get(cid) if isinstance(cid, str) else None
            requests = (row or {}).get('input_requests')
            for q in requests.values() if isinstance(requests, dict) else []:
                scope = q.get('required_scope') if isinstance(q, dict) else None
                if not isinstance(scope, str):
                    continue
                rest = scope
                for name in names:
                    rest = rest.replace(name.strip(), '')
                if rest != scope and not re.sub(r'[\s，、；;：:。.()（）/]+', '', rest):
                    echoed.add(cid)
        if echoed:
            found.append({'code': 'REQUEST_SCOPE_ECHOES_TASK', 'task_ids': [task['id']], 'check_ids': sorted(echoed),
                          'message': 'The gap scope only repeats the task title/root cause; state the voltages, loads, '
                                     'states and temperatures the request must cover.'})
    return found


def templated_handoffs(report):
    groups = defaultdict(set)
    for row in report.get('checks') or []:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str):
            continue
        handoff = row.get('handoff')
        if not isinstance(handoff, dict) or not handoff.get('required'):
            continue
        for field in ('constraint', 'verification'):
            text = handoff.get(field)
            if not isinstance(text, str) or not text.strip():
                continue
            # Remove this check's own id and its requirement token so only the template remains.
            tokens = [row['id']] + [t for t in re.split(r'[.]', row['id']) if len(t) > 3]
            template = text
            for token in sorted(set(tokens), key=len, reverse=True):
                template = template.replace(token, '<id>')
            groups[(field, re.sub(r'\s+', ' ', template).strip())].add(row['id'])
    return [{'code': 'TEMPLATED_HANDOFF', 'field': field, 'template': template[:120], 'check_ids': sorted(ids),
             'message': f'{len(ids)} handoff rows share one {field} sentence with only the check id swapped; '
                        'write what each receiver must actually do and measure.'}
            for (field, template), ids in sorted(groups.items()) if len(ids) >= HANDOFF_MIN_ROWS]


# 固件镜像/烧录/读回/量产校准是固件与生产环节的产物；原理图阶段只判它们的前提（引脚、上拉、GPIO 冲突、配置表自洽）。
FIRMWARE_RE = re.compile(r'烧录|镜像|读回|回读|固件版本|编程(?:模式|接口|夹具)|量产(?:校准|编程)|寄存器(?:映射|编码)|配置工具|'
                         r'应用版本|firmware|image|readback', re.I)
SCHEMATIC_PREREQ_RE = re.compile(r'引脚|上拉|下拉|GPIO.{0,6}冲突|电平|接法|配置表|分压|阻值|网络|连接')
# “已读 X 第 N 页”后面只剩计算/建模动作、没有“缺/未给/只给”的，是审查没算，不是资料缺。
READ_RE = re.compile(r'已读|已核|已查|已取得')
CALC_RE = re.compile(r'计算|复算|核算|反算|积分|建立.{0,6}模型|建模|重算|推算|折算|枚举')
DATA_MISSING_RE = re.compile(r'缺|未给|没有|没给|无此|未找到|不覆盖|不保证|只给|只有.{0,6}(?:典型|25\s*°?C)|未公布|不公开|403|待厂家|向.{0,12}(?:取得|索取)')


def stage_and_cause_misfiles(report, expected):
    found = []
    firmware, calc = [], defaultdict(set)
    for row in report.get('checks') or []:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str) or row['id'] not in expected:
            continue
        if row.get('review_result') != 'INSUFFICIENT' or row.get('gap_cause') not in ('DESIGN_OPEN', 'EXTERNAL_DATA'):
            continue
        missing = ' '.join(x for x in (row.get('missing_inputs') or []) if isinstance(x, str))
        requests = row.get('input_requests') if isinstance(row.get('input_requests'), dict) else {}
        texts = [missing] + [k for k in requests] + [
            q.get(f) for q in requests.values() if isinstance(q, dict)
            for f in ('why_decisive', 'acquisition') if isinstance(q.get(f), str)]
        joined = ' '.join(texts)
        if FIRMWARE_RE.search(joined) and not SCHEMATIC_PREREQ_RE.search(missing + ' ' + ' '.join(requests)):
            firmware.append(row['id'])
        if row.get('gap_cause') == 'EXTERNAL_DATA':
            for key, q in requests.items():
                acq = q.get('acquisition') if isinstance(q, dict) else None
                if not isinstance(acq, str):
                    continue
                if READ_RE.search(acq) and CALC_RE.search(acq) and not DATA_MISSING_RE.search(acq + ' ' + key):
                    calc[key].add(row['id'])
    if firmware:
        found.append({'code': 'FIRMWARE_IMAGE_RECORDED_AS_DESIGN_GAP', 'check_ids': sorted(firmware),
                      'message': 'The missing input is a burned image, readback, programming mode or production calibration. '
                                 'Judge the schematic prerequisites (pins, pulls, GPIO conflicts, a self-consistent '
                                 'configuration table) in their own checks; the image itself is verified downstream: '
                                 'stage NA + handoff to firmware, not a freeze-blocking design gap.'})
    for key, ids in sorted(calc.items()):
        found.append({'code': 'CALCULATION_RECORDED_AS_DATA_GAP', 'check_ids': sorted(ids), 'request': key,
                      'message': 'how_to_close says the document was read and what remains is a calculation. '
                                 'That is review work (REVIEW_INCOMPLETE, finish it this round) or a design task for '
                                 'ASG, not EXTERNAL_DATA; name the datum that is actually absent if one is.'})
    return found


def _template(text, known):
    """Mask designators, net names (with their pin suffixes) and numbers; what is left is the method."""
    text = re.sub(r'\s+', ' ', text or '').strip()
    for ref in sorted((k for k in known if len(k) >= 2), key=lambda k: (-len(k), k)):
        text = re.sub(r'(?<![A-Za-z0-9_])' + re.escape(ref) + r'(?:\.[A-Za-z0-9_+\-]+)?(?![A-Za-z0-9_])', '<ref>', text)
    text = re.sub(r'\d+(?:\.\d+)?', '#', text)
    return text


def _request_owners(report):
    """(check id, request key) -> tasks answering for it: the tasks naming the key in
    request_keys, else every task owning the row when no task names any of its keys."""
    rows = _rows(report)
    named, whole = defaultdict(set), defaultdict(set)
    for task in report.get('work_items') or []:
        if not isinstance(task, dict) or not isinstance(task.get('id'), str):
            continue
        keyed = task.get('request_keys') if isinstance(task.get('request_keys'), dict) else {}
        for cid in task.get('check_ids') or []:
            if not isinstance(cid, str):
                continue
            if isinstance(keyed.get(cid), list):
                for key in keyed[cid]:
                    if isinstance(key, str):
                        named[(cid, key)].add(task['id'])
            else:
                whole[cid].add(task['id'])
    owners = {}
    for cid, row in rows.items():
        requests = row.get('input_requests') if isinstance(row.get('input_requests'), dict) else {}
        for key in requests:
            owners[(cid, key)] = named.get((cid, key)) or whole.get(cid, set())
    return owners


def duplicate_work_items(report, known):
    """Work items whose next_action or owned acquisition text is identical once refs and numbers
    are masked are one method applied to several objects (three optocoupler CTR items): merge them."""
    rows = _rows(report)
    owners = _request_owners(report)
    groups = defaultdict(set)
    for task in report.get('work_items') or []:
        if not isinstance(task, dict) or not isinstance(task.get('id'), str):
            continue
        if isinstance(task.get('next_action'), str) and len(task['next_action'].strip()) >= 12:
            groups[('next_action', _template(task['next_action'], known))].add(task['id'])
    for (cid, key), tids in owners.items():
        q = (rows[cid].get('input_requests') or {}).get(key)
        if isinstance(q, dict) and isinstance(q.get('acquisition'), str) and len(q['acquisition'].strip()) >= 12:
            for tid in tids:
                groups[('acquisition', _template(q['acquisition'], known))].add(tid)
    seen, found = set(), []
    for (field, template), ids in sorted(groups.items(), key=lambda kv: sorted(kv[1])):
        key = frozenset(ids)
        if len(ids) < 2 or key in seen:
            continue
        seen.add(key)
        found.append({'code': 'DUPLICATE_WORK_ITEMS', 'task_ids': sorted(ids), 'check_ids': [], 'field': field,
                      'template': template[:120],
                      'message': f'{len(ids)} work items share one {field} once designators and numbers are masked; '
                                 'one method applied to several objects is one item with several refs.'})
    return found


def _task_texts(task):
    for field in ('title', 'root_cause', 'reason', 'next_action'):
        if isinstance(task.get(field), str):
            yield field, task[field]
    option = task.get('design_option')
    if isinstance(option, dict) and isinstance(option.get('summary'), str):
        yield 'design_option.summary', option['summary']


def _request_texts(row):
    requests = row.get('input_requests')
    for key, q in (requests.items() if isinstance(requests, dict) else []):
        if not isinstance(q, dict):
            continue
        yield key, 'key', key
        for field in ('required_scope', 'acquisition', 'closure_criterion'):  # why_decisive is the row's rationale
            if isinstance(q.get(field), str):
                yield key, field, q[field]


def glued_refs(text, known):
    """Designators that run straight into a number: the token is not itself a known
    ref, but a known ref of the same prefix letters is a proper prefix of it."""
    hits = set()
    for letters, digits in TOKEN_RE.findall(text or ''):
        if letters + digits in known:
            continue
        for n in range(len(digits) - 1, 0, -1):
            if letters + digits[:n] in known:
                hits.add(letters + digits[:n])
                break
    return hits


def text_hygiene(report, expected, known):
    found = []
    known = set(known or ())
    rows = _rows(report)
    glued_hits = defaultdict(set)   # (owner, field) -> refs
    unlooked = defaultdict(set)     # request text -> check ids
    for task in report.get('work_items') or []:
        if isinstance(task, dict) and isinstance(task.get('id'), str):
            for field, text in _task_texts(task):
                hits = glued_refs(text, known)
                if hits:
                    glued_hits[('task:' + task['id'], field)] |= hits
    for cid, row in rows.items():
        if cid not in expected:
            continue
        texts = list(_request_texts(row))
        # Handoff and manual-verification text reach the report too (100W PD R5: "Q4011.50W", "U60111").
        for group, fields in (('handoff', ('constraint', 'verification')),
                              ('manual_verification', ('method', 'tool_limitation', 'sr_improvement'))):
            block = row.get(group)
            if isinstance(block, dict):
                texts += [(None, group + '.' + f, block[f]) for f in fields if isinstance(block.get(f), str)]
        assessment = row.get('impact_assessment')
        if isinstance(assessment, dict):
            texts += [(None, 'impact_assessment.' + f, assessment[f]) for f in IMPACT_TEXT_FIELDS if isinstance(assessment.get(f), str)]
        for key, field, text in texts:
            hits = glued_refs(text, known)
            if hits:
                glued_hits[(cid, field)] |= hits
            if field in ('closure_criterion', 'next_action') and OVERPRECISE_RE.search(text):
                found.append({'code': 'OVERPRECISE_CLOSURE_VALUE', 'check_ids': [cid], 'field': field,
                              'request': key, 'values': sorted(set(OVERPRECISE_RE.findall(text))),
                              'message': 'The acceptance criterion carries an intermediate value from the reviewer\'s own '
                                         'calculation; state the datasheet/standard bound and the condition, not the sample result.'})
        if row.get('review_result') == 'INSUFFICIENT' and row.get('gap_cause') == 'EXTERNAL_DATA':
            missing = ' '.join(x for x in (row.get('missing_inputs') or []) if isinstance(x, str))
            requests = row.get('input_requests') if isinstance(row.get('input_requests'), dict) else {}
            for key, q in requests.items():
                if not isinstance(q, dict) or not isinstance(q.get('acquisition'), str):
                    continue
                if not ACQUIRE_RE.search(q['acquisition']):
                    continue
                looked = ' '.join([key, missing, q['acquisition'], q.get('why_decisive') or '' if isinstance(q.get('why_decisive'), str) else ''])
                if not LOOKUP_RE.search(looked):
                    unlooked[key].add(cid)
    for key, ids in sorted(unlooked.items()):
        found.append({'code': 'ACQUISITION_WITHOUT_LOOKUP', 'check_ids': sorted(ids), 'request': key,
                      'message': 'This external-data request names no page/table/clause that was checked and lacks the '
                                 'datum. Quantities fixed by the applicable standard (prospective short-circuit current, '
                                 'pollution degree, altitude factor) and first-page datasheet ratings are read, not requested; '
                                 'write which document and where was looked up before asking the supplier.'})
    for (owner, field), refs in sorted(glued_hits.items()):
        found.append({'code': 'REF_GLUED_TO_VALUE', 'check_ids': [owner] if not owner.startswith('task:') else [],
                      'task_ids': [owner[5:]] if owner.startswith('task:') else [], 'field': field, 'refs': sorted(refs),
                      'message': 'A reference designator runs straight into a number (R604100°C); separate them so the '
                                 'designator and the value both stay readable.'})
    return found


def templated_task_text(report, expected):
    """Acquisition text, work-item reasons and NONE design-option reasons reused across work items.

    One acquisition sentence serving many tasks names no actual document, party or
    part; one NONE reason with only the missing-input name swapped is not a per-task
    statement that no schematic change removes the gap. Leads only; no verdict changes.
    """
    found = []
    tasks = [t for t in report.get('work_items') or []
             if isinstance(t, dict) and isinstance(t.get('id'), str) and isinstance(t.get('check_ids'), list)]
    owners = defaultdict(set)        # check id -> tasks that own the whole row
    key_owners = defaultdict(set)    # (check id, request key) -> tasks naming that key
    for task in tasks:
        keyed = task.get('request_keys') if isinstance(task.get('request_keys'), dict) else {}
        for cid in task['check_ids']:
            if not isinstance(cid, str):
                continue
            if isinstance(keyed.get(cid), list):
                for key in keyed[cid]:
                    if isinstance(key, str):
                        key_owners[(cid, key)].add(task['id'])
            else:
                owners[cid].add(task['id'])
    acquisitions = defaultdict(lambda: (set(), set(), set()))
    for row in report.get('checks') or []:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str) or row['id'] not in expected:
            continue
        requests = row.get('input_requests')
        for key, request in requests.items() if isinstance(requests, dict) else []:
            text = request.get('acquisition') if isinstance(request, dict) else None
            if isinstance(text, str) and text.strip():
                ids, scopes, task_ids = acquisitions[re.sub(r'\s+', ' ', text).strip()]
                ids.add(row['id']); scopes.add(_scope(expected[row['id']]))
                # A request belongs to the tasks that name its key; tasks that own the
                # whole row count only when no task names any key of that row.
                named = key_owners.get((row['id'], key)) or set()
                task_ids.update(named or owners.get(row['id'], ()))
    for text, (ids, scopes, task_ids) in acquisitions.items():
        if len(task_ids or scopes) >= ACQUISITION_MIN_TASKS:
            found.append({'code': 'BOILERPLATE_ACQUISITION', 'field': 'acquisition', 'template': text[:120],
                          'check_ids': sorted(ids), 'task_ids': sorted(task_ids),
                          'message': f'{len(task_ids or scopes)} tasks share one how_to_close sentence; name the actual '
                                     'document, supplier contact or measurement for each request.'})
    reasons = defaultdict(set)
    for task in tasks:
        option = task.get('design_option')
        reason = option.get('reason') if isinstance(option, dict) and option.get('status') == 'NONE' else None
        if not isinstance(reason, str) or not reason.strip():
            continue
        # Remove this task's own missing-input names; what remains is the template.
        names = set()
        for cid in task['check_ids']:
            row = next((r for r in report.get('checks') or [] if isinstance(r, dict) and r.get('id') == cid), None)
            requests = (row or {}).get('input_requests')
            if isinstance(requests, dict):
                names.update(k for k in requests if isinstance(k, str) and k.strip())
            for name in (row or {}).get('missing_inputs') or []:
                if isinstance(name, str) and name.strip():
                    names.add(name)
        for name in sorted(names, key=len, reverse=True):
            reason = reason.replace(name, '')
        reasons[re.sub(r'\s+', ' ', reason).strip()].add(task['id'])
    stage_reasons = defaultdict(set)
    for task in tasks:
        if isinstance(task.get('reason'), str) and task['reason'].strip():
            stage_reasons[re.sub(r'\s+', ' ', task['reason']).strip()].add(task['id'])
    for text, task_ids in stage_reasons.items():
        if len(task_ids) >= DESIGN_OPTION_MIN_TASKS:
            ids = sorted({cid for t in tasks if t['id'] in task_ids for cid in t['check_ids'] if isinstance(cid, str)})
            found.append({'code': 'TEMPLATED_WORK_ITEM_REASON', 'field': 'reason', 'template': text[:120],
                          'check_ids': ids, 'task_ids': sorted(task_ids),
                          'message': f'{len(task_ids)} work items give the same reason for their stage and grouping; '
                                     'say per item why it is due at that stage or why its checks belong together. '
                                     'The report leaves a shared reason out.'})
    for text, task_ids in reasons.items():
        if len(task_ids) >= DESIGN_OPTION_MIN_TASKS:
            ids = sorted({cid for t in tasks if t['id'] in task_ids for cid in t['check_ids'] if isinstance(cid, str)})
            found.append({'code': 'TEMPLATED_DESIGN_OPTION_REASON', 'field': 'design_option.reason',
                          'template': text[:120], 'check_ids': ids, 'task_ids': sorted(task_ids),
                          'message': f'{len(task_ids)} tasks decline a schematic change with the same sentence; '
                                     'state per task why no part change, value change or added circuit removes the gap, '
                                     'or propose one.'})
    return found


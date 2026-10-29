"""Advisory pattern screening; never certify electrical reasoning or evidence.

Exact reused prose and disjoint explicit component references are review leads,
not defects. Shared proofs and indirect dependencies can be legitimate.
"""
from collections import defaultdict
from pathlib import Path
import derating
import results_model
import review_functions
from checkers.netgraph import NetGraph
import json
import re

# Potential-impact grading: one grade covering nearly every graded gap suggests batch grading.
UNIFORM_GRADE_MIN_ROWS = 10
UNIFORM_GRADE_SHARE = 0.9
# 定级模板：同一句带等级的话出现在多条不同规则的定级理由里，说明等级来自默认句而非本检查项后果路径。
TEMPLATE_MIN_ROWS, TEMPLATE_MIN_RULES = 10, 3
GRADE_RE = re.compile(r'P[0-3]')
LIMIT_WORDS_RE = re.compile(r'≤|<=|上界|上限|最大值|不超过|\bmax\b', re.I)
# 同规则整批同级：本规则至少这么多行证据不足且全部同级时提示逐项定级。
RULE_UNIFORM_MIN_ROWS = 10
# 分出下游工作线索：缺口文字只指向样机/试验结果，或把优化目标记成阻断缺口。关键词只生成提示，不改结论。
DOWNSTREAM_RE = re.compile(r'实测|样机|样品|仿真|闭壳|温升测试|热测|EMC|传导|辐射|认证|一致性测试|兼容性测试|寿命试验|'
                           r'能效测试|整机测试|PCB寄生|实际寄生|实物波形|prototype|bench|compliance|certif', re.I)
# “插墙”是应用场景不是下游验证（一份台账曾把保险丝分断缺口因此标成下游项，下一轮证实为 P0 缺陷）。
# 写明随后/留给下游的分句已把下游部分分出，只看其余文字；整条都是这种分句时仍按原文判。
DEFERRED_CLAUSE_RE = re.compile(r'[^；;，,。]*(?:随后|留给|留待|另行|后续|移交|交由|另验)[^；;，,。]*')
DESIGN_GAP_RE = re.compile(r'未选|未定|缺少?手册|缺资料|无资料|未计算|未建模|未连接|未设计|改图|越限|超出额定|不满足')
OPTIMIZATION_RE = re.compile(r'优化目标|成本|体积|报价|尽量|cost|volume', re.I)
# 冻结阶段把以下两类提示当作“定级未完成”的放行阻断，不改变 valid。
# Review records whose citation as evidence for a current conclusion suggests reuse of an earlier review.
REVIEW_ARTIFACTS = {'review-results.json', 'review-gate.json', '审查报告.md', '审查报告.html'}
RECORD_FIELD_NAMES = {'missing_inputs': 'open[].what', 'required_scope': 'open[].scope',
                      'acquisition': 'open[].acquisition', 'closure_criterion': 'open[].closure', 'closure': 'open[].closure',
                      'consequence': 'open[].severity.consequence', 'affected_function': 'open[].severity.affects',
                      'potential_severity': 'open[].severity.level'}
FREEZE_BLOCKING_CODES = ('TEMPLATED_SEVERITY_REASON', 'UNIFORM_SEVERITY_WITHIN_RULE', 'TEMPLATED_PASS_RATIONALE')
# 资料获取方式/无改图理由模板：同一句话服务于多件待办时，说明没有按对象写出真实来源或真实替代方案。
ACQUISITION_MIN_TASKS = 3
DESIGN_OPTION_MIN_TASKS = 3
IMPACT_TEXT_FIELDS = ('consequence',)  # the derived row view takes severity_reason from it


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


CLOSURE_FIELDS = ('closure', 'acquisition', 'why_insufficient')
DATUM_KINDS = ('VENDOR_DATUM',)   # closed by a guaranteed datum, never by a measurement


def downstream_closures(functions, owners):
    """Step 4.2: a VENDOR_DATUM open item whose closing condition accepts a prototype measurement, a
    sample or a simulation. The datum and the measurement are two tiers; the measured part is a stage-NA row with a
    handoff, and the item names the datum (or spec) that really closes it. A deferred clause (随后/留给…) already splits
    the downstream part and is not read."""
    found = []
    for fn in functions or []:
        if not isinstance(fn, dict) or not isinstance(fn.get('id'), str):
            continue
        for item in fn.get('open') or []:
            if not isinstance(item, dict) or item.get('kind') not in DATUM_KINDS:
                continue
            for field in CLOSURE_FIELDS:
                value = item.get(field)
                if not isinstance(value, str) or not value:
                    continue
                rest = _decisive_part(value)
                hit = DOWNSTREAM_RE.search(rest)
                if hit and not DESIGN_GAP_RE.search(rest):
                    ref = '%s/%s' % (fn['id'], item.get('key'))
                    found.append({'code': 'DOWNSTREAM_RECORDED_AS_DESIGN_GAP', 'function_id': fn['id'], 'key': item.get('key'),
                                  'field': field, 'word': hit.group(0),
                                  'check_ids': sorted(c for c in owners.get(ref, ()) if c),
                                  'message': 'The %s of this %s accepts "%s" as the way to close it. A datum or design '
                                             'spec closes a %s; what only a prototype, sample or simulation can give is a '
                                             'stage-NA row with a handoff. Name the datum that closes the item, or split '
                                             'the measured part out' % (field, item['kind'], hit.group(0), item['kind'])})
                    break
    return found


TASK_TITLE_MAX = 60   # characters; a title is a line of the report's 最先要解决的 3 件事


HOLDS_RE = re.compile(r'(?<![不未])(?:成立|合格|满足|通过)')
FAILS_RE = re.compile(r'不(?:成立|合格|满足|能)|未(?:满足|通过)|缺少|失败|超过|不足|违反|矛盾|错误|误')


def screen_quality(plan, report, db=None, base_dir=None):
    if isinstance(report, dict):
        report = results_model.expand(report)
    output = {'status': 'NOT_RUN', 'scope': 'ADVISORY_PATTERN_SCREENING_ONLY',
              'candidate_count': 0, 'flagged_check_count': 0, 'candidates': []}
    if not isinstance(plan, dict) or not isinstance(report, dict):
        return output
    if not isinstance(plan.get('checks'), list) or not isinstance(report.get('checks'), list):
        return output
    frames = {f['id']: f for f in plan.get('functions') or [] if isinstance(f, dict) and isinstance(f.get('id'), str)}
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
    open_items = {'%s/%s' % (fn['id'], item.get('key')): item for fn in report.get('functions') or []
                  if isinstance(fn, dict) and isinstance(fn.get('id'), str)
                  for item in fn.get('open') or [] if isinstance(item, dict)}
    timing_items = defaultdict(list)   # a derived row's window lives on the open item it points to: judged once
    # Suggest localization, never split or change a verdict without evidence.
    task_owners = defaultdict(set)
    for task in report.get('work_items') or []:
        if (isinstance(task, dict) and isinstance(task.get('id'), str)
                and isinstance(task.get('check_ids'), list)):
            for cid in task['check_ids']:
                if isinstance(cid, str):
                    task_owners[cid].add(task['id'])
        # 5.1 (2026-10-26): the title names the part or loop; it is also the line of 最先要解决的 3 件事 (R7 claude2: 180 字)
        if isinstance(task, dict) and isinstance(task.get('title'), str) and len(task['title'].strip()) > TASK_TITLE_MAX:
            candidates.append({'code': 'TASK_TITLE_LONG', 'task_id': task.get('id'), 'check_ids': [],
                               'length': len(task['title'].strip()),
                               'message': 'work item title has %d characters (limit %d): name the part or loop and what it lacks, '
                                          'the details go to root_cause / the open item\'s what' % (len(task['title'].strip()), TASK_TITLE_MAX)})
    for fn in report.get('functions') or []:
        # the function table prints this result beside the verdict: a failing function whose result says it holds reads
        # as a contradiction (R8: FN-POWER-PROTECTION-J101 不合格, result “数值比较……成立”, the failure was RV101's BOM line)
        result = str(((fn.get('calculation') or {}) if isinstance(fn, dict) else {}).get('result') or '')
        if (isinstance(fn, dict) and fn.get('fails') and HOLDS_RE.search(result) and not FAILS_RE.search(result)):
            candidates.append({'code': 'FAILING_RESULT_SAYS_HOLDS', 'function_ids': [fn.get('id')], 'check_ids': [],
                               'message': 'This function has failures but its result says what holds and not what fails; the '
                                          'function table prints the result beside 不合格, so say what failed first'})
    graph = NetGraph(db) if isinstance(db, dict) and db.get('parts') else None
    kinds_of = lambda refs: sorted({graph.kind(r) for r in refs if r in graph.parts} - {'unknown'}) if graph else []
    identity_of = lambda refs: ' '.join(str((db['parts'].get(r) or {}).get(k) or '') for r in refs
                                        for k in ('part', 'value', 'prim')) if graph else ''
    for fn in report.get('functions') or []:
        # stress spec (user 2026-10-27: 统一到余量审核规则上来): a part-stress margin of a kind the derating spec covers
        # names its rule, so the gate checks it at the project's level; one that names none is a lead, not a refusal
        if not isinstance(fn, dict):
            continue
        conditions = {c.get('id'): c for c in fn.get('conditions') or [] if isinstance(c, dict)}
        for k, m in enumerate(review_functions._margin_items(fn)):
            for message in derating.fit_hints(m, conditions, identity_of):
                candidates.append({'code': 'DERATING_RULE_FIT', 'function_ids': [fn.get('id')], 'check_ids': [],
                                   'margin': k, 'message': message})
            kinds = derating.rule_hint(m, conditions, kinds_of)
            if kinds:
                candidates.append({'code': 'DERATING_RULE_AVAILABLE', 'function_ids': [fn.get('id')], 'check_ids': [],
                                   'margin': k, 'kinds': kinds,
                                   'message': 'This stress margin is on a %s; the derating spec has rules for it: name the '
                                              'one that fits in basis.derating_rule so the gate checks it at the '
                                              'project level' % '/'.join(kinds)})
        # R8 (2026-10-28): Rubycon's leakage I ≤ 3√(CV) µA was written TYPICAL_REFERENCE, then the item said no public
        # bound existed although it computed 396 mW from it; every gap of the record fell in 公开资料定不出界限
        for item in fn.get('open') or []:
            worst = item.get('worst_case') if isinstance(item, dict) else None
            if not (isinstance(worst, dict) and worst.get('not_boundable_reason')):
                continue
            checked = item.get('checked') if isinstance(item.get('checked'), list) else []
            cited = [conditions[c] for c in checked if isinstance(c, str) and isinstance(conditions.get(c), dict)]
            read_as_limit = [c['id'] for c in cited if c.get('kind') == 'TYPICAL_REFERENCE' and not c.get('curve')
                             and LIMIT_WORDS_RE.search(str(c.get('says') or ''))]
            if read_as_limit:
                candidates.append({'code': 'BOUND_RECORDED_AS_UNBOUNDABLE', 'function_ids': [fn.get('id')],
                                   'check_ids': [], 'open': item.get('key'),
                                   'message': 'Open item %s says no public bound exists, but %s reads as a datasheet '
                                              'limit (≤, max, 上限); a guaranteed limit is a NUMERIC_LIMIT: write '
                                              'worst_case.bound and its margin (按公开资料界限算不够), not '
                                              'not_boundable_reason' % (item.get('key'), '、'.join(read_as_limit))})
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
            if row.get('derived') and isinstance(row.get('open_ref'), str):
                item = open_items.get(row['open_ref']) or {}
                if blocked and timing and corner and not all(
                        isinstance(item.get(k), str) and item[k].strip() for k in ITEM_TIMING_FIELDS):
                    timing_items[row['open_ref']].append(row['id'])
                continue
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
        package = check.get('circuit_type') or (obj.get('circuit_type') if isinstance(obj, dict) else None)
        if isinstance(package, str) and package and listed:
            def child_package(child):
                obj = child.get('object')
                return child.get('circuit_type') or (obj.get('circuit_type') if isinstance(obj, dict) else None)
            # Explicit plan scope only. Unpackaged physical dependencies cannot
            # be assigned by a shared rule prefix or a prose keyword.
            wrong = sorted(cid for cid in listed if cid in expected
                           and child_package(expected[cid])
                           and child_package(expected[cid]) != package)
            if wrong:
                candidates.append({'code': 'AGGREGATE_CHILD_CIRCUIT_TYPE_MISMATCH',
                    'check_ids': [row['id']], 'circuit_type': package, 'child_ids': wrong,
                    'message': 'Listed checks belong to another circuit type. Verify membership or document the real cross-type dependency; this advisory does not reject legitimate shared proofs.'})
            members = {cid for cid, child in expected.items()
                       if cid != row['id'] and child.get('rule') != 'REQ-Q07'
                       and child_package(child) == package}
            missing = sorted(members - listed)
            if missing:
                candidates.append({'code': 'AGGREGATE_SUBJECTS_MISSING',
                    'check_ids': [row['id']], 'circuit_type': package, 'child_ids': missing,
                    'message': 'An explicit child/status list omits subjects bound to this circuit type. Reconcile the complete plan scope; unbound electrical dependencies still require expert tracing.'})

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
        if check and check.get('rule') != 'REQ-H02' and row.get('review_result') == 'INSUFFICIENT':
            gap_key = row['open_ref'] if row.get('derived') and isinstance(row.get('open_ref'), str) else row['id']
            grades[row.get('potential_severity')].append((row['id'], gap_key))   # an open item's rows are one graded gap
            cause = row.get('gap_cause')
            gap_text = ' '.join(_decisive_part(x) for x in (row.get('missing_inputs') or []) if isinstance(x, str))
            if cause == 'EXTERNAL_DATA' and DOWNSTREAM_RE.search(gap_text) \
                    and not DESIGN_GAP_RE.search(gap_text) and not row.get('derived'):   # derived: downstream_closures
                downstream_ids.append(row['id'])
            if OPTIMIZATION_RE.search(str(check.get('criterion') or '') + ' ' + str(row.get('rationale') or '')) \
                    and row.get('potential_severity') in ('P0', 'P1'):
                optimization_ids.append(row['id'])
            rule_grades[check.get('rule')].append((row['id'], row.get('potential_severity'), gap_key))
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
        # Rows bound to one function verdict cite it with one sentence; that is the proof, not a copy.
        if isinstance(rationale, str) and rationale.strip() and not row.get('function_id') and not row.get('derived'):
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
        frame = frames.get(check.get('function_id') or row.get('function_id'))
        if frame:
            # a row bound to a function is judged over the function's objects: a device row of the circuit's part may
            # name the circuit's other parts (R7 acceptance 2026-10-25: 57/66 hits on two records after the pre-binding)
            for ref in (frame.get('objects') or {}).get('refs') or []:
                wanted.update(refs(ref))
        observed = refs(rationale)
        if isinstance(row.get('evidence'), list):
            for item in row['evidence']:
                if isinstance(item, dict):
                    observed.update(refs(item.get('locator')))
        if wanted and observed and wanted.isdisjoint(observed) and not row.get('derived'):   # tool text names the item's objects
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
            if wanted and actual and wanted.isdisjoint(actual) and not row.get('derived'):   # the item's consequence
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
        if check.get('rule') == 'SIG-T04' and check.get('circuit_type') == 'USB':
            text = analysis_text(rationale, check)
            other = re.search(r'(?<![A-Za-z0-9_])(?:UART|SPI|TXD\d*|RXD\d*|PICO|POCI)(?![A-Za-z0-9_])', text, re.I)
            usb = re.search(r'USB|D[+-]|(?<![A-Za-z0-9_])(?:DP|DM|Host|Device|Source|Sink)(?![A-Za-z0-9_])', text, re.I)
            if other and not usb:
                candidates.append({'code': 'INTERFACE_ANALYSIS_MODE_MISMATCH',
                    'field': 'rationale', 'check_ids': [row['id']],
                    'declared_circuit_type': 'USB',
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
    graded = len({key for pairs in grades.values() for _, key in pairs})
    for grade, pairs in grades.items():
        keys = {key for _, key in pairs}
        if graded >= UNIFORM_GRADE_MIN_ROWS and len(keys) >= UNIFORM_GRADE_SHARE * graded:
            candidates.append({'code': 'UNIFORM_POTENTIAL_SEVERITY', 'grade': grade,
                'check_ids': sorted(cid for cid, _ in pairs),
                'message': f'{len(keys)} of {graded} graded evidence gaps (an open item and its rows count once) share '
                           'one potential grade; confirm each was graded from its own consequence path, not by default.'})
    for ref, ids in sorted(timing_items.items()):
        candidates.append({'code': 'TIMING_BLOCK_WITHOUT_WINDOW', 'check_ids': sorted(ids),
            'function_id': ref.split('/', 1)[0], 'key': ref.split('/', 1)[-1],
            'message': 'A timing/temperature-max gap blocks these rows; the open item they point to gives no scenario, '
                       'allowed_window and response_bound. Write them on the item (UNKNOWN with a physical reason is valid).'})
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
        levels = {grade for _, grade, _ in group}
        keys = {key for _, _, key in group}
        if len(keys) >= RULE_UNIFORM_MIN_ROWS and len(levels) == 1:
            candidates.append({'code': 'UNIFORM_SEVERITY_WITHIN_RULE', 'rule': rule, 'grade': levels.pop(),
                'check_ids': sorted(cid for cid, _, _ in group),
                'message': f'All {len(keys)} evidence gaps of {rule} (an open item and its rows count once) share one potential grade; '
                           'objects of one rule (bypass cap vs. bulk high-voltage resistor) rarely share one consequence.'})
    cited_reviews = sorted(
        row['id'] for row in report['checks'] if isinstance(row, dict) and isinstance(row.get('id'), str)
        and row['id'] in expected
        and expected[row['id']].get('rule') != 'REQ-H02' and not row.get('derived')   # aggregate rows cite this record
        and any(isinstance(ev, dict) and isinstance(ev.get('source'), str)
                and ev['source'].replace('\\', '/').rsplit('/', 1)[-1] in REVIEW_ARTIFACTS
                for ev in row.get('evidence') or []))
    if cited_reviews:
        candidates.append({'code': 'CURRENT_CHECK_CITES_REVIEW_RECORD', 'check_ids': cited_reviews,
            'message': 'A current conclusion cites a review results/gate/report file. If it is an earlier review, '
                       're-derive the conclusion from current sources and declare the file in history_inputs.'})
    candidates.extend(templated_task_text(report, expected))
    candidates.extend(templated_pass_rationale(report, expected))
    candidates.extend(unreconciled_history(report, expected, (plan or {}).get("review_mode")))
    candidates.extend(text_hygiene(report, expected, known))
    candidates.extend(port_overvoltage_grading(report))
    candidates.extend(scope_echoes_task(report))
    candidates.extend(finding_wording(report.get('findings') or []))
    candidates.extend(templated_handoffs(report))
    candidates.extend(stage_and_cause_misfiles(report, expected))
    nets = db.get('nets', {}) if isinstance(db, dict) else {}
    candidates.extend(duplicate_work_items(report, known | {n.rsplit('/', 1)[-1] for n in nets if isinstance(n, str) and n} if isinstance(nets, dict) else known))
    owners = defaultdict(set)
    for row in report['checks']:
        if isinstance(row, dict) and isinstance(row.get('open_ref'), str):
            owners[row['open_ref']].add(row.get('id'))
    for hint in review_functions.template_hints(report.get('functions'), base_dir):
        refs = hint.get('items') or ['%s/%s' % (hint.get('function_id'), hint.get('key'))]
        candidates.append(dict(hint, check_ids=sorted({c for ref in refs for c in owners.get(ref, ()) if c})))
    for hint in review_functions.condition_ref_hints(report.get('functions'), plan):   # results 7: a condition's refs
        candidates.append(dict(hint, check_ids=[]))
    candidates.extend(downstream_closures(report.get('functions'), owners))
    candidates.extend(misfiled_items(report.get('functions'), owners))
    for candidate in candidates:  # name fields the way the reviewer writes them (a function's open item)
        if candidate.get('field') in RECORD_FIELD_NAMES:
            candidate['field'] = RECORD_FIELD_NAMES[candidate['field']]
    candidates.sort(key=lambda x: (x['code'], x['check_ids']))
    output.update(status='NEEDS_SEMANTIC_REVIEW' if candidates else 'NO_PATTERN_DETECTED',
                  candidate_count=len(candidates),
                  flagged_check_count=len({cid for x in candidates for cid in x['check_ids']}))
    return output


# A PASS rationale reduced to its reasoning: without the "see function" prefix, an object echo and a basis tag, which
# made one paragraph look different on every row.
SEE_FUNCTION_RE = re.compile(r'^见功能判定 \S+?（[^）]*）：')
OBJECT_ECHO_RE = re.compile(r'；(对象|已核范围)\s*[：:]?\s*\{.*$', re.S)
BASIS_TAG_RE = re.compile(r'（依据 [^）]*）\s*$')
REQUIREMENT_ID_RE = re.compile(r'REQ-[A-Z]+-\d+')
TEMPLATE_MIN_CHARS = 30
# One part's identity, pin set and pin disposition are one question about one part; one paragraph may answer them.
DEVICE_FAMILY = {'DEV-D01': 'DEV-D', 'DEV-D02': 'DEV-D', 'DEV-D05': 'DEV-D'}


def pass_core(text):
    text = re.sub(r'\s+', ' ', str(text or '')).strip()
    text = BASIS_TAG_RE.sub('', OBJECT_ECHO_RE.sub('', SEE_FUNCTION_RE.sub('', text))).strip(' ；;。')
    return REQUIREMENT_ID_RE.sub('REQ', text)


def _question(cid, rule):
    """What a row asks, for the template screen: its rule, a requirement row's aspect, a device row's family."""
    if rule == 'REQ-D01':
        return '.'.join(cid.split('.')[:2])
    return DEVICE_FAMILY.get(rule, rule)


def templated_pass_rationale(report, expected):
    """PASS rows of different rules closed by one paragraph: each criterion asks its own question, so one text that
    answers several of them answers none (freeze-blocking)."""
    groups = defaultdict(list)
    for row in report.get('checks') or []:
        if not isinstance(row, dict) or row.get('review_result') != 'PASS' or row.get('derived'):
            continue   # a derived row's sentence is the tool's pointer at the function verdict, not a reviewer's paragraph
        core = pass_core(row.get('rationale'))
        if len(core) >= TEMPLATE_MIN_CHARS:
            rule = (expected.get(row.get('id')) or {}).get('rule') or str(row.get('id', '')).split('.')[0]
            groups[core].append((row['id'], _question(row['id'], rule)))
    return [{'code': 'TEMPLATED_PASS_RATIONALE', 'check_ids': sorted(cid for cid, _ in rows), 'template': core[:120],
             'message': '%d PASS rows asking %d different questions rest on one paragraph; write for each criterion '
                        'what was compared and against what' % (len(rows), len({q for _, q in rows}))}
            for core, rows in sorted(groups.items()) if len({q for _, q in rows}) > 1]


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


# 位号后面直接粘着数值（R12100°C、C71.1uF）：读者分不清位号和数值；这是写法问题，不改结论。
TOKEN_RE = re.compile(r'(?<![A-Za-z0-9_])([A-Z]{1,4})(\d+)(?![A-Za-z_])')
# 通过条件里的三位以上小数（257.121uA、.27647mA）是审查员算例的中间值，不是设计者能凑的判据。
OVERPRECISE_RE = re.compile(r'(?<![0-9.])\d*\.\d{3,}(?![\d.])')


# 端口过压送到外部负载是 PORT_OVERVOLTAGE 危险路径（P0 类），不因“只坏负载”降为器件损坏或功能项。
PORT_OV_RE = re.compile(r'(?:端口|USB|VBUS|合同|负载)[^。；;]{0,16}过压|过压[^。；;]{0,16}(?:端口|负载|USB|VBUS)|负载损坏|port\s*over-?voltage', re.I)
# 否定/转交句（“未据此推断端口过压”“端口过压另列待办核”）不是正向后果断言。
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


REMEDY_OPENING = re.compile(r'^\s*(?:缺(?!口|省)少?|未加|没加|没有|少了?)')


def finding_wording(findings):
    """A root cause that only names the missing part is the fix, not the cause (a delivered review wrote
    "缺串阻、缺芯片端 TVS" where the cause was a single TVS stage clamping above the pin rating)."""
    found = []
    for f in findings:
        if not isinstance(f, dict) or not isinstance(f.get('root_cause'), str):
            continue
        cause = f['root_cause'].strip()
        fix = (f.get('fix') or '').strip() if isinstance(f.get('fix'), str) else ''
        if REMEDY_OPENING.match(cause) or (cause and cause == fix):
            found.append({'code': 'ROOT_CAUSE_IS_REMEDY', 'finding_ids': [f.get('id')], 'check_ids': list(f.get('check_ids') or []),
                          'message': 'The root cause names the missing part or repeats the fix; say why the circuit fails '
                                     '(which quantity exceeds which limit, in which state) and leave the part to the fix.'})
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
        if not isinstance(handoff, dict) or not handoff.get('required') or row.get('derived'):
            continue   # derived rows carry their function's handoff by construction (R6: 38 of 46 flagged rows)
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
            for (field, template), ids in sorted(groups.items()) if len(ids) >= HANDOFF_MIN_ROWS] \
        + templated_function_handoffs(report) + restated_handoffs(report)


ID_TOKEN_RE = re.compile(r'[A-Z][A-Z0-9_]*(?:-[A-Z0-9_]+)*\d*|每只')


def templated_function_handoffs(report):
    """Function handoffs whose sentence differs only by a part or function id (R8, 2026-10-28: 按本功能实际位号…落实
    block-review.md中U601的定值… in dozens of functions): the derived rows carry it, so the row screen never sees it."""
    groups = defaultdict(set)
    for fn in report.get('functions') or []:
        if not isinstance(fn, dict) or not isinstance(fn.get('id'), str):
            continue
        for h in fn.get('handoffs') or []:
            text = h.get('verification') if isinstance(h, dict) else None
            if isinstance(text, str) and text.strip():
                groups[re.sub(r'\s+', ' ', ID_TOKEN_RE.sub('<id>', text)).strip()].add(fn['id'])
    return [{'code': 'TEMPLATED_HANDOFF', 'field': 'verification', 'template': template[:120], 'function_ids': sorted(ids),
             'check_ids': [], 'message': f'{len(ids)} functions hand on one verification sentence with only an id '
                                         'swapped; write what each receiver must measure and against what.'}
            for template, ids in sorted(groups.items()) if len(ids) >= HANDOFF_MIN_ROWS]


def restated_handoffs(report):
    """Handoffs whose verification is their constraint again (R8: 48 requirement rows handed on the requirement text
    twice): the handoff is what the schematic review worked out for this design, not the requirement restated."""
    norm = lambda s: re.sub(r'[\s，。；、,.;:：]', '', s)
    ids = sorted(row['id'] for row in report.get('checks') or [] if isinstance(row, dict) and isinstance(row.get('id'), str)
                 and isinstance(row.get('handoff'), dict) and row['handoff'].get('required')
                 and all(isinstance(row['handoff'].get(f), str) for f in ('constraint', 'verification'))
                 and len(norm(row['handoff']['verification'])) >= RESTATED_MIN_CHARS
                 and norm(row['handoff']['verification']) in norm(row['handoff']['constraint']))
    return [{'code': 'HANDOFF_RESTATES_REQUIREMENT', 'check_ids': ids,
             'message': f'{len(ids)} handoffs give their constraint again as the verification; hand on only what this '
                        'design needs and how the receiver closes it, not the requirement text.'}] if ids else []


RESTATED_MIN_CHARS = 20


# 固件镜像/烧录/读回/量产校准是固件与生产环节的产物；原理图阶段只判它们的前提（引脚、上拉、GPIO 冲突、配置表自洽）。
FIRMWARE_RE = re.compile(r'烧录|镜像|读回|回读|固件版本|编程(?:模式|接口|夹具)|量产(?:校准|编程)|寄存器(?:映射|编码)|配置工具|'
                         r'应用版本|firmware|image|readback', re.I)
SCHEMATIC_PREREQ_RE = re.compile(r'引脚|上拉|下拉|GPIO.{0,6}冲突|电平|接法|配置表|分压|阻值|网络|连接')
# “已读 X 第 N 页”后面只剩计算/建模动作、没有“缺/未给/只给”的，是审查没算，不是资料缺。
READ_RE = re.compile(r'已读|已核|已查|已取得')
CALC_RE = re.compile(r'计算|复算|核算|反算|积分|建立.{0,6}模型|建模|重算|推算|折算|枚举')
DATA_MISSING_RE = re.compile(r'缺|未给|没有|没给|无此|未找到|不覆盖|不保证|只给|只有.{0,6}(?:典型|25\s*°?C)|未公布|不公开|403|待厂家|向.{0,12}(?:取得|索取)')


ITEM_TIMING_FIELDS = ('scenario', 'allowed_window', 'response_bound')
MISFILE_KINDS = ('VENDOR_DATUM',)
ITEM_TEXT_FIELDS = ('what', 'acquisition', 'closure', 'why_insufficient')


def misfiled_items(functions, owners):
    """Step 4.2 on the open item (the row's missing_inputs is only the item's what, how_to_close rewrites a design value's
    acquisition, and the row's gap_cause is a map of the kind): a burned image, readback, programming fixture or production
    calibration recorded as a design value, a datum or a deliverable is a firmware/production handoff; a datum whose
    acquisition says the document was read and only a calculation remains is review work, not EXTERNAL_DATA."""
    found = []
    for fn in functions or []:
        if not isinstance(fn, dict) or not isinstance(fn.get('id'), str):
            continue
        for item in fn.get('open') or []:
            if not isinstance(item, dict) or item.get('kind') not in MISFILE_KINDS:
                continue
            ref = '%s/%s' % (fn['id'], item.get('key'))
            texts = {f: _decisive_part(item[f]) for f in ITEM_TEXT_FIELDS if isinstance(item.get(f), str) and item[f]}
            check_ids = sorted(c for c in owners.get(ref, ()) if c)
            prerequisites = ' '.join(texts.get(f, '') for f in ('what', 'acquisition'))
            hit = next(((f, FIRMWARE_RE.search(t)) for f, t in texts.items() if FIRMWARE_RE.search(t)), None)
            if hit and not SCHEMATIC_PREREQ_RE.search(prerequisites):
                found.append({'code': 'FIRMWARE_IMAGE_RECORDED_AS_DESIGN_GAP', 'function_id': fn['id'], 'key': item.get('key'),
                              'field': hit[0], 'word': hit[1].group(0), 'check_ids': check_ids,
                              'message': 'This %s is closed by a burned image, readback, programming mode or production '
                                         'calibration. Judge the schematic prerequisites (pins, pulls, GPIO conflicts, a '
                                         'self-consistent configuration table) in their own checks; the image itself is '
                                         'verified downstream: stage NA + handoff to firmware, not a freeze-blocking gap'
                                         % item['kind']})
            if item.get('kind') == 'VENDOR_DATUM':
                acquisition = ' '.join(texts.get(f, '') for f in ('acquisition', 'closure', 'why_insufficient'))
                if (READ_RE.search(acquisition) and CALC_RE.search(acquisition)
                        and not DATA_MISSING_RE.search(acquisition + ' ' + texts.get('what', ''))):
                    found.append({'code': 'CALCULATION_RECORDED_AS_DATA_GAP', 'function_id': fn['id'], 'key': item.get('key'),
                                  'request': ref, 'check_ids': check_ids,
                                  'message': 'The acquisition says the document was read and what remains is a calculation. '
                                             'That is review work (REVIEW_INCOMPLETE, finish it this round) or a design task '
                                             'for ASG, not a VENDOR_DATUM; name the datum that is actually absent if one is.'})
    return found


def stage_and_cause_misfiles(report, expected):
    found = []
    firmware, calc = [], defaultdict(set)
    for row in report.get('checks') or []:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str) or row['id'] not in expected:
            continue
        if row.get('review_result') != 'INSUFFICIENT' or row.get('gap_cause') != 'EXTERNAL_DATA':
            continue
        if row.get('derived'):   # a derived row's gap is its open item's: misfiled_items reads the item once
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


def _function_texts(fn):
    """(field, text) a function verdict puts in the report: its question, result, and its items' gaps and reasons."""
    if isinstance(fn.get('question'), str):
        yield 'question', fn['question']
    calc = fn.get('calculation') if isinstance(fn.get('calculation'), dict) else {}
    if isinstance(calc.get('result'), str):
        yield 'calculation.result', calc['result']
    for group in ('open', 'fails'):
        for item in fn.get(group) or []:
            if not isinstance(item, dict):
                continue
            label = '%s[%s]' % (group, item.get('key', '?'))
            if isinstance(item.get('what'), str):
                yield label + '.what', item['what']
            for i, edge in enumerate(item.get('decides') or []):
                if isinstance(edge, dict) and isinstance(edge.get('rationale'), str):
                    yield '%s.decides[%d].rationale' % (label, i), edge['rationale']


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


def refs_named(text, known):
    """Known designators a text names, glued or not: a token that is not itself a known ref names the longest known ref
    of the same letters that is a proper prefix of it (Q201650V names Q201)."""
    found = set()
    for letters, digits in TOKEN_RE.findall(text or ''):
        for n in range(len(digits), 0, -1):
            if letters + digits[:n] in known:
                found.add(letters + digits[:n])
                break
    return found


def text_hygiene(report, expected, known):
    found = []
    known = set(known or ())
    rows = _rows(report)
    glued_hits = defaultdict(set)   # (owner, field) -> refs
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
        # Handoff and manual-verification text reach the report too (a delivered report: "Q21.50W", "U111").
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
    for fn in report.get('functions') or []:   # the function table and work items print these as written
        if isinstance(fn, dict) and isinstance(fn.get('id'), str):
            for field, text in _function_texts(fn):
                hits = glued_refs(text, known)
                if hits:
                    glued_hits[('function:' + fn['id'], field)] |= hits
    for (owner, field), refs in sorted(glued_hits.items()):
        kind, _, name = owner.partition(':') if owner.startswith(('task:', 'function:')) else ('check', '', owner)
        found.append({'code': 'REF_GLUED_TO_VALUE', 'check_ids': [name] if kind == 'check' else [],
                      'task_ids': [name] if kind == 'task' else [], 'function_ids': [name] if kind == 'function' else [],
                      'field': field, 'refs': sorted(refs),
                      'message': 'A reference designator runs straight into a number (R12100°C); separate them so the '
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


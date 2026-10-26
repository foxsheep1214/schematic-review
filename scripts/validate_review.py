#!/usr/bin/env python3
"""Validate a completed review ledger; never infer electrical correctness from it.
Exit 0: valid ledger, 2: invalid; --require-release also returns 2 for NO_GO.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import catalog
import function_reading
import results_model
from review_workflow import workflow, decision
from review_quality import FREEZE_BLOCKING_CODES, screen_quality
from review_engine import validate_engine
from review_summary import categorized_summary, validate_impact
from requirement_clarifications import validate_clarifications
from checkers import REGISTRY, passive_stress, validate_inventories
from validate_remediation import validate_remediation, validate_figures, changes_topology, READINESS
from electrical_contract import LOCATOR_IDS_RE, PLAN_SCHEMA_VERSION, db_fingerprint, load_json, squeeze_words
from plan_review import LINT_REVIEW_KINDS, ReviewPlanner, lint_check, lint_check_id
from revision_impact import validate_metadata, validate_reverification, check_spec, digest as revision_digest
from page_inventory import validate_document_pages
from review_stage_scope import validate_stage_scope, outside_stage, GAP_CAUSES
from review_functions import estimated_passes, netlist_evidence_errors, validate_functions
import check_key
import row_owner
import interfaces
import requirement_bindings
import independence
import rule_gaps
import bom_constraints

RESULTS = {"PASS", "FAIL", "INSUFFICIENT", "NA"}
SEVERITIES = {"P0", "P1", "P2", "P3"}
APPLICABILITY = {"APPLICABLE", "NOT_APPLICABLE", "UNDETERMINED"}
# Optional INSUFFICIENT cause (evidence-proportionality.md); over-strict checks are re-judged, not tagged.
REQUIREMENT_GAP = {"OPEN": "REQUIREMENT_OPEN", "DEFERRED": "USER_DEFERRED"}
CLAUSE_KINDS = ("OBLIGATION", "PREMISE")
CLAUSE_ORDER = {"NA": 0, "PASS": 1, "INSUFFICIENT": 2, "FAIL": 3}


def source_text(planned):
    """A requirement row's original text: the transcribed columns in order (requirements_extract)."""
    columns = (planned.get("source_text") or {}).get("columns") if isinstance(planned.get("source_text"), dict) else None
    return "".join(c.get("text") or "" for c in columns or [] if isinstance(c, dict))


def requirement_clause_errors(key, item, criterion):
    """REQ-D01：需求全文按原文顺序拆成条款，只有要求条款带结论，检查项结论 = 要求条款中最差的结论。"""
    clauses = item.get("requirement_clauses")
    if not isinstance(clauses, list) or not clauses or not all(isinstance(c, dict) for c in clauses):
        return [f"{key}: REQ-D01 须给 requirement_clauses（按原文顺序拆分的条款，kind 为 OBLIGATION/PREMISE）"]
    errors = []
    texts = [c.get("text") if isinstance(c.get("text"), str) else "" for c in clauses]
    if squeeze_words("".join(texts)) != squeeze_words(criterion):
        errors.append(f"{key}: requirement_clauses 的 text 按顺序拼接须等于需求原文（不遗漏、不改写）")
    worst = None
    for i, clause in enumerate(clauses, 1):
        kind, result = clause.get("kind"), clause.get("result")
        if kind not in CLAUSE_KINDS:
            errors.append(f"{key}: 条款 {i} 的 kind 须为 OBLIGATION 或 PREMISE")
        elif kind == "PREMISE" and result is not None:
            errors.append(f"{key}: 条款 {i} 是前提（条件/方法/范围），不带结论")
        elif kind == "OBLIGATION":
            if result not in CLAUSE_ORDER:
                errors.append(f"{key}: 要求条款 {i} 须给 PASS/FAIL/INSUFFICIENT/NA 结论")
            elif worst is None or CLAUSE_ORDER[result] > CLAUSE_ORDER[worst]:
                worst = result
    if worst is None and not errors:
        errors.append(f"{key}: 至少一条要求条款；整条都是前提时按适用性改判 NA 并给依据")
    elif worst is not None and item.get("review_result") != worst:
        errors.append(f"{key}: 检查项结论须等于要求条款中最差的结论（{worst}）；前提条款与其他检查项的缺陷不连带本检查项")
    return errors
def _under(source, root):
    source, root = source.replace('\\', '/').rstrip('/'), root.replace('\\', '/').rstrip('/')
    return source == root or source.startswith(root + '/') or source.endswith('/' + root)


def history_citation_errors(report, checks, expected):
    """history_inputs：本轮能看到的旧审查材料；只有上一版问题复验检查项（REQ-H02）可以引用它们。"""
    if 'history_inputs' not in report:
        return []
    roots = report['history_inputs']
    if not (isinstance(roots, list) and all(text(x) for x in roots)):
        return ['history_inputs must list the earlier-review paths available to this review (may be empty)']
    errors = []
    for key, item in checks.items():
        if (expected.get(key) or {}).get('rule') == 'REQ-H02':
            continue
        for ev in item.get('evidence') or []:
            source = ev.get('source') if isinstance(ev, dict) else None
            hit = next((root for root in roots if text(source) and _under(source, root)), None)
            if hit:
                errors.append(f"{key}: evidence {source} is an earlier review ({hit}); judge from current "
                              "sources and cite earlier reviews only in REQ-H02 history rows")
    return errors


def split_out_errors(checks, expected):
    """split_out：汇总检查项的结论只覆盖拆出实例以外的对象；拆出实例同规则、各自给结论、只属一个汇总检查项。"""
    errors, owner = [], {}
    rule = lambda k: (expected.get(k) or checks.get(k) or {}).get('rule') or k.split('.', 1)[0]
    for key, item in checks.items():
        if 'split_out' not in item:
            continue
        split = item['split_out']
        if not ids(split) or len(set(split)) != len(split):
            errors.append(f"{key}: split_out must be a non-empty list of distinct check IDs")
            continue
        for child in split:
            if child == key or child not in checks:
                errors.append(f"{key}: split_out {child} is not another check in the results")
            elif rule(child) != rule(key):
                errors.append(f"{key}: split_out {child} belongs to another rule")
            elif 'split_out' in checks[child]:
                errors.append(f"{key}: split_out {child} is itself an aggregate; split one level only")
            elif child in owner:
                errors.append(f"{child}: split out of both {owner[child]} and {key}")
            else:
                owner[child] = key
    return errors


REQUIREMENT_LABEL = {"CONFIRMED": "已确认（CONFIRMED）", "PROPOSED": "提案（PROPOSED）",
                     "OPEN": "未定（OPEN）", "DEFERRED": "暂缓（DEFERRED）"}
SCOPE = set(catalog.COVERAGE_RULES)


# Why the automatic checker could not decide, and how the reviewer independently checked it.
MANUAL_FIELDS = ('tool_limitation', 'sr_improvement', 'method')
# Tool gaps the review closes itself by supplying an input (declaration, datasheet fact, evidence, requirement)
# and regenerating the plan. Only the rest — a model or topology the tool lacks — may be verified by hand.
INPUT_GAP_HEADS = ('intent', 'evidence', 'requirements', 'firmware', 'population', 'datasheet', 'datasheets',
                   'datasheet-requirement', 'datasheet-audit', 'unverified-device-pinout', 'official-full-pinout',
                   'rail-requirement', 'level-standard')


def input_gap(code):
    head = code.split(':', 1)[0].strip()
    return head in INPUT_GAP_HEADS or head.split('.', 1)[0] in INPUT_GAP_HEADS


def text(value):
    return isinstance(value, str) and bool(value.strip())


def evidence(value):
    return isinstance(value, list) and bool(value) and all(
        isinstance(x, dict) and text(x.get("source")) and text(x.get("locator"))
        for x in value)


def ids(value):
    return isinstance(value, list) and bool(value) and all(text(x) for x in value)


def fingerprint(data):
    encoded = json.dumps(data, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def primary_anchors(obj, db=None):
    """Declared primary targets, not every contextual ref/net in a circuit group."""
    refs, nets = set(), set()
    if text(obj.get('ref')):
        refs.add(obj['ref'])
    if text(obj.get('net')):
        nets.add(obj['net'])
    node = obj.get('node')
    if text(node):
        if '.' in node:
            refs.add(node.split('.', 1)[0])
        if isinstance(db, dict) and isinstance(db.get('pin2net'), dict):
            net = db['pin2net'].get(node)
            if text(net):
                nets.add(net)
    return refs, nets


def review_scope(plan, report, require):
    """results.review_scope = {functions: [plan frame ids], reason}: a ledger that answers only those
    frames (a training hot review of one circuit). Coverage is owed for their member rows only and the
    gate carries a blocker, so the record reconciles but never reads as a board verdict."""
    decl = report.get("review_scope")
    if decl is None:
        return None, set()
    frames = {f["id"]: f for f in plan.get("functions") or [] if isinstance(f, dict) and text(f.get("id"))}
    ok = (isinstance(decl, dict) and isinstance(decl.get("functions"), list) and bool(decl["functions"])
          and text(decl.get("reason")))
    require(ok, "review_scope needs functions (plan frame ids) and a reason")
    rows = set()
    if ok:
        for fid in decl["functions"]:
            require(fid in frames, f"review_scope: {fid} is not a plan frame")
            rows |= {m.get("check_id") for m in frames.get(fid, {}).get("members") or [] if isinstance(m, dict)}
    return (decl if ok else {"functions": [], "reason": ""}), rows


def validate_review(plan, report, db=None, lint_runs=None, require_actionable=False,
                    require_bindings=False, old_db=None, old_plan=None, require_revision=False, require_current_engine=False,
                    require_dependencies=False, base_dir=None):
    errors, blockers = [], []
    def require(ok, message):
        if not ok:
            errors.append(message)
    def index(items, label):
        out = {}
        if not isinstance(items, list):
            errors.append(f"{label} must be an array")
            return out
        for item in items:
            if not isinstance(item, dict) or not text(item.get("id")):
                errors.append(f"{label}: invalid object/id")
                continue
            key = item["id"]
            require(key not in out, f"{label}: duplicate id {key}")
            out[key] = item
        return out

    if not isinstance(plan, dict) or not isinstance(report, dict):
        return {"valid": False, "errors": ["plan/results must be objects"],
                "release": "NO_GO", "blockers": ["invalid input"],
                "quality_screening": screen_quality(plan, report, db, base_dir)}
    history_ids = {c.get('id') for c in plan.get('checks') or [] if isinstance(c, dict) and c.get('rule') == 'REQ-H02'}
    shape = results_model.shape_errors(report, history_ids)
    if report.get('schema_version') != results_model.SCHEMA_VERSION:
        return {"valid": False, "errors": shape, "release": "NO_GO", "blockers": ["results schema"],
                "quality_screening": screen_quality(plan, report, db, base_dir)}
    errors.extend(shape)
    written, report = report, results_model.expand(report)
    errors.extend(validate_engine(plan, require_current_engine))
    clauses_required = True  # REQ-D01 always splits its requirement into clauses
    impact_classes = results_model.IMPACT_CLASS_VERSION
    require(plan.get("schema_version") == PLAN_SCHEMA_VERSION,
            f"plan.schema_version must be {PLAN_SCHEMA_VERSION}; plans with retired check IDs must be regenerated")
    actionable = require_actionable
    require(report.get("plan_digest") == fingerprint(plan), "plan_digest mismatch")
    if db is not None:
        if db.get('integrity', {}).get('self_check_passed') is False or db.get('export_errors'):
            blockers.append('input netlist failed integrity/export checks')
        require(report.get("db_digest") == fingerprint(db), "db_digest mismatch")
    expected = index(plan.get("checks"), "plan.checks")
    asked = {}
    require(isinstance(plan.get('assemblies'), list),
            'plan.assemblies missing: the check keys name each assembly by its content; regenerate the plan')
    for cid, planned in expected.items():   # merge plan §5: one check is asked once (the key is recomputed, never trusted)
        asked.setdefault(check_key.key(planned, plan.get('assemblies')), []).append(cid)
    for key, cids in asked.items():
        require(len(cids) == 1, f"{', '.join(sorted(cids))}: the same check (rule, object, criterion) asked "
                                f"{len(cids)} times; keep one row, or split the object or criterion")
    for message in row_owner.errors(plan):   # function-tree step 2: the owner is recomputed from the owner table
        require(False, message)
    for message in row_owner.coverage_errors(plan, db) + interfaces.coverage_errors(plan):   # step 6: tree coverage
        require(False, message)
    for message in requirement_bindings.errors(plan):   # fixed requirements, step 4: requirement rows bound to tree rows
        require(False, message)
    document_pages, page_checks = None, {}
    if db is not None:
        try:
            document_pages, page_checks = validate_document_pages(plan, expected, db, require)
        except (ValueError, TypeError, KeyError) as error:
            require(False, 'invalid page inventory: ' + str(error))
    for key, item in expected.items():
        for message in catalog.spec_errors(item):
            require(False, f"{key}: {message}")
    for message in catalog.plan_explanation_errors(plan):
        require(False, message)
    for message in catalog.question_errors(plan):
        require(False, message)
    revision_errors, revision = validate_metadata(plan, db, old_db, old_plan, require_revision)
    errors.extend(revision_errors)
    if revision is not None:
        errors.extend(validate_reverification(plan, report, revision))
    if 'revision_impact_version' in report and revision is None:
        require(False, 'revision results require a valid revision-impact plan')
    if require_dependencies and db is not None and 'dependency_version' not in plan:
        require(False, 'plan.dependency_version is missing, so the automatic checks cannot be re-derived; regenerate the '
                       'plan with lint.py')
    if 'dependency_version' in plan and db is not None:
        # Recreate automatic checks from raw saved inputs, not the possibly
        # edited check list. Manual additions stay independently reviewable.
        try:
            inputs = plan['review_inputs']
            # The planner reads the candidate file only for the parts REQ-Q08 asks about, which the plan keeps.
            summary = plan.get('circuit_candidates')
            candidates = ({'candidates': [], 'unassigned': [{'ref': r} for r in summary.get('unassigned') or []]}
                          if isinstance(summary, dict) else None)
            planner = ReviewPlanner(db, inputs['intent'], plan.get('review_mode'),
                                    datasheet_audit=inputs['datasheet_audit'], candidates=candidates)
            planner.generate()
            planned_ids = {generated['id'] for generated in planner.checks}
            for cid, row in expected.items():   # fixed requirements, step 7: an added row is a registered rule gap
                require(cid in planned_ids or not rule_gaps.unwritten(row), rule_gaps.message(cid))
            for generated in planner.checks:
                actual = expected.get(generated['id'])
                require(actual is not None and revision_digest(check_spec(actual)) == revision_digest(check_spec(generated)),
                        generated['id'] + ': automatic check missing or changed from saved inputs')
            saved = plan.get('check_explanations') or {}
            for rule in sorted({generated['rule'] for generated in planner.checks}):
                require(rule in saved and saved[rule] == catalog.explanation(rule),
                        rule + ': automatic check explanation missing or changed from saved inputs')
        except (ValueError, TypeError, KeyError, AttributeError) as error:
            require(False, 'invalid generated-check inputs: ' + str(error))
    tool_gaps = {}
    gates = validate_inventories(REGISTRY, plan, expected, db, require,
                                 lambda context: ReviewPlanner(db, context), gaps=tool_gaps)
    checks = index(report.get("checks"), "results.checks")
    errors.extend(independence.evidence_errors(checks.values()))   # SR does not take the designer's documents
    errors.extend(requirement_bindings.coverage_errors(expected, checks))   # REQ-Q07 follows its circuit type's rows
    scope_errors, stage_scope = validate_stage_scope(checks, expected)
    errors.extend(scope_errors)
    findings = index(report.get("findings"), "findings")
    bindings = (require_bindings or revision is not None
                or any('binding' in x for x in checks.values()))
    bound_count = 0
    require(bool(expected), "empty review plan")
    scope_decl, scope_rows = review_scope(plan, report, require)
    in_scope = {k: v for k, v in expected.items() if k in scope_rows} if scope_decl else expected
    missing, unexpected = sorted(set(in_scope) - set(checks)), sorted(set(checks) - set(expected))
    require(not missing and not unexpected, f"check coverage mismatch: missing={missing}, unexpected={unexpected}")
    if scope_decl:
        blockers.append("review_scope: the ledger answers only %s; it is not a board verdict"
                        % ", ".join(scope_decl["functions"]))
    clarifications = validate_clarifications(report, checks, expected)
    errors.extend(clarifications['errors'])
    blockers.extend(clarifications['blockers'])
    stage = workflow(plan, report, checks, clarifications, require_design_options=actionable)
    errors.extend(stage['errors'])
    accepted = False
    # A row passing on an estimate is C-grade evidence (2026-10-26 decision 4): derive writes C on the row, the release
    # is capped at CONDITIONAL_GO below, and the report lists these rows apart.
    estimated = estimated_passes(expected, checks, report.get('functions'))
    estimated_ids = {e['check_id'] for e in estimated}
    pending = []   # INSUFFICIENT rows waiting for a deliverable (filled below)
    for cid in estimated_ids:
        if checks[cid].get('evidence_confidence') != 'C':
            errors.append(f"{cid}: a PASS on an estimate is C-grade evidence (derive writes it); it cannot claim "
                          f"{checks[cid].get('evidence_confidence')}")
    sr_improvements = []
    manual_methods = {}
    for key, item in checks.items():
        if bindings and key in expected:
            planned = expected[key]
            binding = item.get('binding')
            require(isinstance(planned.get('object'), dict) and text(planned.get('criterion')),
                    f'{key}: bound plan requires object and non-empty criterion')
            planned_object = planned.get('object')
            coordinates_ok = isinstance(planned_object, dict) and all(
                field not in planned_object or text(planned_object[field])
                for field in ('ref', 'node', 'net'))
            require(coordinates_ok, f'{key}: declared primary ref/node/net must be non-empty strings')
            require(isinstance(binding, dict), f'{key}: binding requires reviewed object and criterion')
            if isinstance(binding, dict):
                object_ok = coordinates_ok and isinstance(binding.get('object'), dict) and (
                    fingerprint(binding['object']) == fingerprint(planned['object']))
                criterion_ok = text(binding.get('criterion')) and binding['criterion'] == planned.get('criterion')
                require(object_ok, f'{key}: binding object differs from planned object/configuration/state')
                require(criterion_ok, f'{key}: binding criterion differs from planned criterion')
                bound_count += int(object_ok and criterion_ok)
        result, app = item.get("review_result"), item.get("applicability")
        manual = item.get('manual_verification')
        if 'manual_verification' in item:
            require(bool(gates.get(key)) and result in ('PASS', 'FAIL'),
                    f'{key}: manual_verification only applies to a PASS/FAIL that the tool cannot confirm')
            require(isinstance(manual, dict) and all(text(manual.get(f)) for f in MANUAL_FIELDS)
                    and evidence(manual.get('evidence')),
                    f'{key}: manual_verification needs ' + ', '.join(MANUAL_FIELDS) + ' and evidence')
            inputs = [c for c in tool_gaps.get(key, []) if input_gap(c)]
            require(not inputs, f'{key}: ' + ', '.join(inputs) + ' is an input the review supplies — declare it (intent, '
                    'datasheet facts, evidence) and regenerate the plan; manual_verification is only for a model the tool lacks')
            if isinstance(manual, dict) and text(manual.get('method')):
                obj = {k: v for k, v in ((expected.get(key) or {}).get('object') or {}).items() if k != 'state'}
                manual_methods.setdefault(manual['method'].strip(), {}).setdefault(
                    json.dumps(obj, sort_keys=True, ensure_ascii=False), []).append(key)
            if isinstance(manual, dict) and 'reviewer_kind' in manual:
                require(manual['reviewer_kind'] in ('AI', 'HUMAN'),
                        f'{key}: reviewer_kind must record the actual AI/HUMAN reviewer')
        if result in ('PASS', 'FAIL') and gates.get(key) and isinstance(manual, dict):
            # The reviewer's evidenced conclusion stands; the tool gap is an SR improvement, not design work.
            sr_improvements.append({'check_id': key, 'tool_messages': gates[key], 'tool_gaps': tool_gaps.get(key, []),
                                    **{f: manual.get(f) for f in MANUAL_FIELDS},
                                    **({'reviewer_kind': manual['reviewer_kind']} if 'reviewer_kind' in manual else {})})
        elif result == 'PASS':
            for message in gates.get(key, []):
                require(False, message + ' (or record manual_verification with an independent evidenced review)')
        proposal = expected.get(key, {}).get('proposal')
        if isinstance(proposal, dict) and proposal.get('result') == 'PASS' and result in ('FAIL', 'INSUFFICIENT'):
            errors.extend(passive_stress.override_errors(key, item))
        require(isinstance(result, str) and result in RESULTS, f"{key}: invalid result")
        require(isinstance(app, str) and app in APPLICABILITY, f"{key}: invalid applicability")
        if 'check_explanation' in item:
            errors.extend(f'{key}: {message}' for message in
                          catalog.explanation_errors(item['check_explanation'], partial=True))
        errors.extend(bom_constraints.constraint_errors(key, item))
        require(text(item.get("rationale")), f"{key}: missing rationale")
        require(evidence(item.get("evidence")), f"{key}: missing locatable evidence")
        require(isinstance(item.get("blocking"), bool), f"{key}: blocking must be boolean")
        if key in expected and app != expected[key].get("applicability"):
            require(evidence(item.get("applicability_evidence")),
                    f"{key}: applicability changed without evidence")
        if result == "NA" and not outside_stage(item):  # stage NA keeps APPLICABLE (review_stage_scope)
            require(app == "NOT_APPLICABLE", f"{key}: NA requires NOT_APPLICABLE")
            if (expected.get(key) or {}).get('requires'):
                errors.extend(netlist_evidence_errors(key, item.get('applicability_evidence'), db))
        elif app == "NOT_APPLICABLE":
            require(False, f"{key}: NOT_APPLICABLE requires NA")
        elif app == "UNDETERMINED":
            require(result == "INSUFFICIENT", f"{key}: unresolved applicability")
        confidence = item.get("evidence_confidence")
        if result in ("PASS", "FAIL"):
            require(confidence in ("A", "B") or (result == "PASS" and key in estimated_ids),
                    f"{key}: PASS/FAIL needs A/B evidence")
        if result == "INSUFFICIENT":
            if expected.get(key, {}).get('rule') != 'REQ-H02':
                errors.extend(validate_impact(item, impact_classes))  # history dispositions are counted apart
            require(confidence == "C", f"{key}: unresolved conclusion must remain C")
            require(ids(item.get("missing_inputs")), f"{key}: missing_inputs required")
            if item.get('gap_cause') != 'REQUIREMENT_OPEN':
                require(item.get("potential_severity") in tuple(SEVERITIES),
                        f"{key}: potential_severity required")
        if "gap_cause" in item:
            require(result == "INSUFFICIENT" and item["gap_cause"] in GAP_CAUSES,
                    f"{key}: gap_cause is one of {'/'.join(GAP_CAUSES)} and only on INSUFFICIENT")
        # A requirement the owner has not decided (OPEN) or has postponed (DEFERRED) cannot be judged.
        req_status = (expected.get(key, {}).get("object") or {}).get("requirement_status")
        if req_status in REQUIREMENT_GAP:
            require(result == "INSUFFICIENT" and item.get("gap_cause") == REQUIREMENT_GAP[req_status],
                    f"{key}: 需求状态为{REQUIREMENT_LABEL[req_status]}，结果须为 INSUFFICIENT 且 gap_cause 为 {REQUIREMENT_GAP[req_status]}")
        elif clauses_required and expected.get(key, {}).get("rule") == "REQ-D01" and result != "NA":
            derived = requirement_bindings.derived_result(expected[key], checks, function_reading.fail_filter(plan, report))
            if derived is None:
                errors.extend(requirement_clause_errors(key, item, source_text(expected[key])))
            else:   # the aspect is carried by tree rows; the requirement row is not judged again
                require(result == derived, f"{key}: 需求方面由绑定检查项承担（{'、'.join(expected[key]['bound_checks'])}），"
                                           f"结论须等于绑定检查项中最差的结论（{derived}）；用 derive_rows.py 写出")
        if result == "FAIL":
            require(item.get("severity") in tuple(SEVERITIES), f"{key}: invalid severity")
            fid = item.get("finding_id")
            require(text(fid) and fid in findings, f"{key}: FAIL needs finding_id")
            if text(fid) and fid in findings:
                require(findings[fid].get("severity") == item.get("severity"),
                        f"{key}: finding severity mismatch")
                require(key in findings[fid].get("check_ids", []),
                        f"{key}: finding link is not reciprocal")
        else:
            require(item.get("severity") is None, f"{key}: severity is only for FAIL")
        state = item.get("disposition", "OPEN")
        require(state in ("OPEN", "FIXED_VERIFIED", "ACCEPTED", "RETRACTED"),
                f"{key}: invalid disposition")
        if state in ("FIXED_VERIFIED", "RETRACTED"):
            require(result in ("PASS", "NA"), f"{key}: closed correction needs current PASS/NA")
            require(evidence(item.get("closure_evidence")), f"{key}: missing closure evidence")
        approval_ok = False
        if state == "ACCEPTED":
            approval = item.get("acceptance", {})
            approval_ok = isinstance(approval, dict) and all(text(approval.get(k)) for k in
                ("by", "date", "scope", "reason", "record"))
            require(approval_ok, f"{key}: acceptance needs by/date/scope/reason/record")
            require(result in ("FAIL", "INSUFFICIENT"), f"{key}: acceptance cannot manufacture PASS")
            accepted = True
        critical = item.get("severity") in ("P0", "P1") or (
            result == "INSUFFICIENT" and item.get("potential_severity") in ("P0", "P1"))
        if result == "INSUFFICIENT" and item.get("gap_cause") == "REVIEW_INCOMPLETE":
            blockers.append(f"{key}: review work not completed; finish the review before release")
        requirement_decision = item.get('gap_cause') == 'REQUIREMENT_OPEN'
        # A deliverable another stage owes (drawing, configuration table, firmware capability) is a condition of the
        # freeze, not a reason against it (2026-10-26, item 3): it caps the release at CONDITIONAL_GO and is listed
        # for the project manager under 等交付物, never a blocker.
        pending_deliverable = result == "INSUFFICIENT" and item.get("gap_cause") == "DELIVERABLE_PENDING"
        if pending_deliverable:
            pending.append(key)
        if result in ("FAIL", "INSUFFICIENT") and not requirement_decision and not pending_deliverable:
            if item.get("severity") == "P0":
                blockers.append(f"{key}: P0 requires verified repair")
            elif (critical or item.get("blocking")) and not approval_ok:
                blockers.append(f"{key}: unresolved blocking {result}")
        h = item.get("handoff", {"required": False})
        require(isinstance(h, dict), f"{key}: invalid handoff")
        if isinstance(h, dict):
            require(isinstance(h.get("required"), bool), f"{key}: handoff.required must be boolean")
        if isinstance(h, dict) and expected.get(key, {}).get('handoff', {}).get('required') and not h.get('required'):
            require(evidence(item.get('handoff_evidence')), f'{key}: required planned handoff removed without evidence')
        if isinstance(h, dict) and h.get("required"):
            require(h.get("state") in ("OPEN", "ACCEPTED", "VERIFIED"), f"{key}: invalid handoff state")
            require(ids(h.get("receivers")) and text(h.get("constraint")) and text(h.get("verification")),
                    f"{key}: handoff lacks receiver/constraint/verification")
            # Handoffs travel with the schematic as a list; acceptance never gates finalisation.
            if h.get("state") in ("ACCEPTED", "VERIFIED"):
                require(evidence(h.get("evidence")), f"{key}: handoff acceptance/verification needs record")

    for method, groups in manual_methods.items():
        if len(groups) > 1:
            rows_sharing = sorted(k for keys in groups.values() for k in keys)
            errors.append(', '.join(rows_sharing) + ': one manual_verification.method over different objects; say what was '
                          'checked on each row (its refs, nodes, values)')
    errors.extend(split_out_errors(checks, expected))
    errors.extend(history_citation_errors(report, checks, expected))
    errors.extend(validate_functions(plan, written, checks, history_ids, db))

    for fid, item in findings.items():
        if actionable or "remediation" in item:
            errors.extend(validate_remediation(fid, item.get("remediation"), set(findings), require_preflight=True))
        if actionable and item.get("kind") == "DEFECT" and item.get("severity") in ("P0", "P1"):
            errors.extend(validate_figures(fid, item.get("figures"), need_after=changes_topology(item.get("remediation"))))
        require(item.get("severity") in tuple(SEVERITIES), f"{fid}: invalid severity")
        require(item.get("kind") in ("DEFECT", "IMPROVEMENT"), f"{fid}: invalid finding kind")
        require(ids(item.get("check_ids")), f"{fid}: check_ids required")
        linked = item.get("check_ids") if ids(item.get("check_ids")) else []
        require(all(x in checks for x in linked), f"{fid}: unknown check link")
        for field in ("title", "observed", "criterion", "impact", "scenario", "root_cause",
                      "recommendation", "verification", "severity_reason"):
            require(text(item.get(field)), f"{fid}: missing {field}")
        location = item.get("location", {})
        require(isinstance(location, dict) and all(ids(location.get(k)) for k in ("pages", "refs", "nets")),
                f"{fid}: location needs pages/refs/nets (use explicit unresolved locator for missing data)")
        if item.get("kind") == "DEFECT":
            require(any(checks[x].get("review_result") == "FAIL" and checks[x].get("finding_id") == fid
                        for x in linked if x in checks), f"{fid}: orphan defect")
            if bindings:
                require(len(linked) == len(set(linked)), f'{fid}: duplicate check link')
                require(all(x in checks and checks[x].get('review_result') == 'FAIL' and
                            checks[x].get('finding_id') == fid for x in linked),
                        f'{fid}: every defect link must be its own FAIL check')
        else:
            require(item.get("severity") == "P3", f"{fid}: optional improvement must be P3")
            require(all(checks[x].get("review_result") == "PASS" for x in linked if x in checks),
                    f"{fid}: improvement requires compliant underlying check")
        if bindings and isinstance(location, dict):
            located_refs = set(location['refs']) if ids(location.get('refs')) else set()
            located_nets = set(location['nets']) if ids(location.get('nets')) else set()
            for key in linked:
                obj = expected.get(key, {}).get('object')
                if isinstance(obj, dict):
                    refs, nets = primary_anchors(obj, db)
                    require(refs.issubset(located_refs),
                            f'{fid}/{key}: finding location omits checked ref(s) {sorted(refs-located_refs)}')
                    require(nets.issubset(located_nets),
                            f'{fid}/{key}: finding location omits checked net(s) {sorted(nets-located_nets)}')

    scope = report.get("scope_checks", {})
    if scope_decl is None or "scope_checks" in report:
        require(isinstance(scope, dict) and set(scope) == SCOPE, "scope_checks must cover six audit dimensions")
    if isinstance(scope, dict):
        for dimension, key in scope.items():
            require(text(key) and key in checks, f"scope {dimension}: unknown check id")
            if text(key) and key in checks and checks[key].get("review_result") != "PASS":
                # A history audit may be NA for a documented first review.
                if not (dimension == "history" and checks[key].get("review_result") == "NA"):
                    blockers.append(f"scope {dimension}: coverage audit not PASS")

    coverage = report.get("coverage", {})
    require(isinstance(coverage, dict), "coverage must be an object")
    if scope_decl is not None and "coverage" not in report:
        coverage = None   # a scoped ledger owes no board-wide coverage map
    wanted = {"requirements": {str(x["object"]["requirement_id"]) for x in expected.values()
              if isinstance(x.get("object"), dict) and x["object"].get("requirement_id")}}
    if db is not None:
        wanted.update({
            "components": set(db.get("parts", {})),
            "pins": set(db.get("pin2net", {})) | set(db.get("declared_pinname", {})),
            "nets": set(db.get("nets", {})) - set(db.get("pseudo_nets", [])),
            "pages": {str(x['page']) for x in document_pages['pages']} if document_pages else set(),
        })
    if isinstance(coverage, dict):
        for dimension, objects in wanted.items():
            entries = coverage.get(dimension, {})
            require(isinstance(entries, dict), f"coverage.{dimension} must be object")
            if not isinstance(entries, dict):
                continue
            require(set(entries) == objects, f"coverage.{dimension}: missing={sorted(objects-set(entries))}, "
                    f"unexpected={sorted(set(entries)-objects)}")
            for obj, linked in entries.items():
                require(ids(linked) and all(x in checks for x in linked),
                        f"coverage.{dimension}.{obj}: missing/unknown check references")
                if dimension == 'pages' and obj in page_checks:
                    require(ids(linked) and page_checks[obj] in linked,
                            f'coverage.pages.{obj}: must link its own DOC-V01 page view')

    if lint_runs is not None:
        # Each automatic-scan finding is a check of its own in the final plan; its result row answers it.
        for run in lint_runs:
            digest = fingerprint(run)
            run_checks = {}
            if isinstance(run, dict) and 'review_plan' in run:
                run_plan = run['review_plan']
                require(isinstance(run_plan, dict), f'{digest}: invalid lint review_plan')
                if isinstance(run_plan, dict):
                    run_checks = index(run_plan.get('checks'), f'{digest}.review_plan.checks')
                    if db is not None and 'db_sha256' in run_plan:
                        require(run_plan['db_sha256'] == db_fingerprint(db),
                                f'{digest}: lint plan belongs to another netlist')
                    for key, planned in run_checks.items():
                        require(key in expected, f'{digest}: final plan omits lint check {key}')
                        if key in expected:
                            fields = ('rule', 'object', 'criterion')
                            require(all(planned.get(k) == expected[key].get(k) for k in fields),
                                    f'{key}: final plan changed the lint check identity/criterion')
            findings_list = run.get('findings', []) if isinstance(run, dict) else run
            if not isinstance(findings_list, list):
                require(False, 'invalid lint findings list')
                continue
            for number, finding in enumerate(findings_list):
                if not isinstance(finding, dict):
                    require(False, f'{digest}[{number}]: invalid lint finding')
                    continue
                if finding.get('kind') in LINT_REVIEW_KINDS:
                    key = lint_check_id(finding)
                    require(key in expected and expected[key].get('criterion') == lint_check(finding)['criterion'],
                            f'{digest}[{number}]: final plan omits the check for lint finding {key}')

    counts = dict(Counter(x.get("review_result") for x in checks.values()
                          if isinstance(x.get("review_result"), str)))
    severity_counts = {s: sum(x.get("severity") == s and x.get("kind") == "DEFECT"
                          for x in findings.values()) for s in sorted(SEVERITIES)}
    computed = {"checks": len(checks), "results": counts,
                "confirmed_defects": sum(severity_counts.values()), "by_severity": severity_counts,
                "improvements": sum(x.get("kind") == "IMPROVEMENT" for x in findings.values())}
    if "summary" in report:
        require(report["summary"] == computed, "summary does not match unique findings/check results")
    if plan.get("review_phase", "schematic_freeze") == "schematic_freeze":
        blockers.extend(bom_constraints.freeze_blockers(checks))
        for item in screen_quality(plan, report, db, base_dir)["candidates"]:
            if item["code"] in FREEZE_BLOCKING_CODES:
                blockers.append(f"{item['code']}: {len(item['check_ids'])} " + (
                    "PASS rows need their own comparison before freeze" if item['code'] == 'TEMPLATED_PASS_RATIONALE'
                    else "evidence gaps need individual grading before freeze"))
    release = release_for(errors, blockers, accepted, estimated, pending)
    if "release" in report:
        require(report["release"] == release, f"claimed release differs from computed {release}")
    gap_causes = dict(Counter(x.get("gap_cause", "UNSPECIFIED") for x in checks.values()
                              if x.get("review_result") == "INSUFFICIENT"))
    repair_counts = {state: sum(isinstance(x.get("remediation"), dict) and
                    x["remediation"].get("readiness") == state for x in findings.values())
                    for state in READINESS}
    sr_improvements.extend(extension_signals(report, db))
    return {"quality_screening": screen_quality(plan, report, db, base_dir),
            "estimated_passes": estimated,
            "pending_deliverables": sorted(pending),
            "scope": scope_decl,
            "valid": not errors, "errors": errors, "blockers": blockers,
            "release": "NO_GO" if errors else release, "summary": computed,
            "categorized_summary": categorized_summary(checks, expected, findings, stage, impact_classes),
            "insufficient_by_cause": gap_causes,
            "stage_scope": stage_scope,
            "sr_improvements": sr_improvements,
            "rule_gaps": rule_gaps.listing(plan, report),
            "requirement_clarification_summary": clarifications['summary'],
            "requirement_clarifications": clarifications['items'],
            # REQ-D01 results per requirement confirmation state: a PASS against PROPOSED is conditional on that proposal.
            "requirements_by_status": {st: dict(Counter(checks[k].get("review_result") for k, x in expected.items()
                                                        if k in checks and (x.get("object") or {}).get("requirement_status") == st))
                                       for st in sorted({(x.get("object") or {}).get("requirement_status") for x in expected.values()} - {None})},
            "workflow": decision(stage, errors, "NO_GO" if errors else release),
            "revision_validation": {"enforced": revision is not None,
                "required_checks": sum(e['required'] for e in revision['entries']) if revision else 0,
                "strategy": revision['strategy'] if revision else None},
            "binding_validation": {"enforced": bool(bindings), "bound_checks": bound_count},
            "remediation_validation": {"enforced": actionable, "by_readiness": repair_counts}}


def extension_signals(report, db):
    """2026-10-26 decision 0 (user: 器件类别是可以增长的): what the review met that the device-kind vocabulary or the
    bounding table does not cover, reported under 对 SR 的反馈 and never blocking. NEW_DEVICE_KIND: a fitted part the
    classifier calls unknown. NEW_BOUND_CELL: a margin or an unboundable datum written with cell NONE on a part whose kind
    is known — the table has no cell for that kind's parameter."""
    if not (isinstance(db, dict) and isinstance(db.get('parts'), dict) and db['parts']):
        return []
    from checkers.netgraph import NetGraph
    graph = NetGraph(db)
    out = []
    for ref in sorted(db['parts']):
        part = db['parts'][ref]
        if graph.kind(ref) == 'unknown' and not part.get('nc'):
            out.append({'kind': 'NEW_DEVICE_KIND', 'refs': [ref],
                        'clue': ' / '.join(str(part.get(k)) for k in ('part', 'value') if text(part.get(k))),
                        'suggestion': '按手册标题给这类器件一个类别名，补进 part_words 的词表和定界表（可得性、允许的估算与倍数、'
                                      '失效后果、样机能否验、边界）；本板按已知的判，结论不等它'})
    for fn in report.get('functions') or []:
        if not (isinstance(fn, dict) and text(fn.get('id'))):
            continue
        conditions = {c.get('id'): c for c in fn.get('conditions') or [] if isinstance(c, dict)}
        objects = [r for r in ((fn.get('objects') or {}).get('refs') or []) if text(r)]
        calc = fn.get('calculation') if isinstance(fn.get('calculation'), dict) else {}
        margin = calc.get('margin')
        margins = margin if isinstance(margin, list) else [margin] if margin is not None else []
        places = [('margin', k, m.get('basis'), ' '.join(str(x) for x in (
                      m.get('against'), m.get('aspect'), (conditions.get((m.get('basis') or {}).get('limit')) or {}).get('says'))
                      if text(x)))
                  for k, m in enumerate(margins) if isinstance(m, dict) and isinstance(m.get('basis'), dict)]
        for item in fn.get('open') or []:
            worst = item.get('worst_case') if isinstance(item, dict) else None
            tried = worst.get('monotonic_tried') if isinstance(worst, dict) else None
            if isinstance(tried, dict):
                places.append(('open', item.get('key'), tried, str(item.get('what') or '')))
        for where, index, basis, words in places:
            if basis.get('cell') != catalog.NO_CELL:
                continue
            refs = [r for r in LOCATOR_IDS_RE.findall(words) if r in db['parts']] or objects
            kinds = sorted({graph.kind(r) for r in refs if r in db['parts']} - {'unknown'})
            if kinds:
                out.append({'kind': 'NEW_BOUND_CELL', 'function_id': fn['id'], where: index, 'device_kinds': kinds,
                            'refs': sorted(set(refs)), 'parameter': words[:120],
                            'suggestion': '给 %s 的这个参数补一格：可得性、允许的估算与倍数、失效后果、样机能否验、边界；'
                                          '补格前本板按 NONE 的默认判' % '/'.join(kinds)})
    return out


def release_for(errors, blockers, accepted, estimated, pending=()):
    """GO needs no error, no blocker, nothing accepted by approval, nothing passing on an estimate and no deliverable
    outstanding; an accepted item, an estimate pass (confirmed only on the prototype) or a deliverable another stage
    owes caps the release at CONDITIONAL_GO."""
    if errors or blockers:
        return "NO_GO"
    return "CONDITIONAL_GO" if accepted or estimated or pending else "GO"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan")
    parser.add_argument("results")
    parser.add_argument("--db")
    parser.add_argument("--old-db")
    parser.add_argument("--old-plan")
    parser.add_argument("--require-revision-impact", action="store_true",
                        help="require current revision dependencies and re-verification records")
    parser.add_argument("--json")
    parser.add_argument("--lint", action="append", help="lint JSON of each scan run; repeat for each run")
    parser.add_argument("--require-release", action="store_true")
    parser.add_argument("--require-actionable", action="store_true",
                        help="require detailed repair instructions for every finding")
    args = parser.parse_args()
    try:
        read = load_json
        result = validate_review(read(args.plan), read(args.results), read(args.db) if args.db else None,
                                 [read(x) for x in args.lint] if args.lint else None,
                                 require_actionable=args.require_actionable,
                                 require_bindings=True, require_dependencies=True,   # the gate is strict without flags
                                 old_db=read(args.old_db) if args.old_db else None,
                                 old_plan=read(args.old_plan) if args.old_plan else None,
                                 require_revision=args.require_revision_impact,
                                 require_current_engine=True,
                                 base_dir=str(Path(args.results).resolve().parent))   # resolves conditions' sources
    except (ValueError, OSError, TypeError) as exc:
        result = {"quality_screening": screen_quality(None, None),
                  "valid": False, "release": "NO_GO", "errors": [str(exc)]}
    if args.json:
        Path(args.json).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["valid"] or (args.require_release and result["release"] == "NO_GO"):
        sys.exit(2)


if __name__ == "__main__":
    main()

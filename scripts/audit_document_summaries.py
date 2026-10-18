#!/usr/bin/env python3
"""Audit calculation-summary claims against inventory and preflight rows.

This is document reconciliation, not arithmetic or electrical qualification.
Only the documented summary formats are parsed; other prose needs review.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from asg_summary_adapter import adapt_asg

STATES = ("SUPPORTED", "CONDITIONAL", "FAIL")
CHINESE = re.compile(
    r"(?<![\w.+-])(\d+)项计算条件检查\s*(\d+)SUPPORTED\s*/\s*"
    r"(\d+)CONDITIONAL\s*/\s*(\d+)FAIL(?![\w.])")
ENGLISH = re.compile(
    r"Calculation summary:\s*total=(\d+);\s*SUPPORTED=(\d+);\s*"
    r"CONDITIONAL=(\d+);\s*FAIL=(\d+)\s*\.?\s*$")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key: " + key)
        result[key] = value
    return result


def _version_one(data):
    return (isinstance(data, dict) and type(data.get("schema_version")) is int
            and data["schema_version"] == 1)


def _valid_id(value):
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def _distribution(rows):
    counts = Counter(rows.values())
    return {"total": len(rows), **{s: counts[s] for s in STATES}}


ASG_SUMMARY = re.compile(r"^\s*\|\s*计算结论：满足 / 有条件满足 / 不满足\s*\|\s*(\d+)\s*/\s*(\d+)\s*/\s*(\d+)\s*\|\s*$")
ASG_COVERAGE = re.compile(r"^\s*\|\s*计算：上下界完整 / 只算了一部分\s*\|\s*(\d+)\s*/\s*(\d+)\s*\|\s*$")


def parse_summaries(text):
    """Return all supported literal declarations, plus unparsed anchors."""
    summaries, gaps = [], []
    for number, line in enumerate(text.splitlines(), 1):
        asg = ASG_SUMMARY.fullmatch(line)
        if asg:
            values = [int(v) for v in asg.groups()]
            summaries.append({"line": number, "literal": asg.group(0),
                              "counts": dict(zip(("total", *STATES), [sum(values), *values]))})
        elif "计算结论：" in line:
            gaps.append({"line": number, "reason": "unsupported ASG summary format"})
        matches = list(CHINESE.finditer(line))
        english = ENGLISH.fullmatch(line.strip())
        if english:
            matches.append(english)
        for match in matches:
            values = [int(v) for v in match.groups()]
            summaries.append({"line": number, "literal": match.group(0),
                              "counts": dict(zip(("total", *STATES), values))})
        # Every recognized anchor must have an independently complete parse.
        for marker in ("项计算条件检查", "Calculation summary:"):
            positions = [m.start() for m in re.finditer(re.escape(marker), line)]
            covered = sum(marker in m.group(0) for m in matches)
            if len(positions) != covered:
                gaps.append({"line": number, "reason": "incomplete or unsupported summary format"})
    return summaries, gaps


def audit(calculations=None, preflight=None, documents=(), preflight_contract=None):
    findings, inputs, declarations = [], {}, []

    def issue(code, message, source, locator, proven=False):
        findings.append({"code": code, "message": message, "source": str(source),
                         "locator": locator, "review_result": "FAIL" if proven else "INSUFFICIENT",
                         "severity": "P2" if proven else None})

    def read(path, label, as_json=True):
        if path is None:
            issue("MISSING_INPUT", "required input not supplied", label, "input")
            return None
        try:
            raw = Path(path).read_bytes()
            inputs[str(path)] = hashlib.sha256(raw).hexdigest()
            text = raw.decode("utf-8")
            return json.loads(text, object_pairs_hook=_unique_object) if as_json else text
        except (OSError, UnicodeError, ValueError) as exc:
            issue("UNREADABLE_INPUT", str(exc), path, "file")
            return None

    inventory = read(calculations, "calculations")
    checked = read(preflight, "preflight")
    adapter = None
    if isinstance(inventory, list) and inventory and any(isinstance(r, dict) and "conclusion" in r for r in inventory):
        contract = read(preflight_contract, "preflight-contract")
        inventory, checked, adapter = adapt_asg(inventory, checked, contract, calculations, preflight,
                                               preflight_contract, issue)
    claims, statuses = {}, {}
    inventory_ids, preflight_ids, ambiguous_ids = set(), set(), set()
    inventory_schema = (_version_one(inventory)
                        and isinstance(inventory.get("calculations"), list))
    preflight_schema = (_version_one(checked)
                        and isinstance(checked.get("results"), dict)
                        and checked.get("status") in ("PASS", "FAIL", "INSUFFICIENT"))
    inventory_ids_complete = inventory_states_complete = inventory_schema
    preflight_ids_complete = preflight_states_complete = preflight_schema
    if not inventory_schema:
        issue("BAD_SCHEMA", "expected schema_version=1 and calculations list", calculations, "calculations")
    else:
        if not inventory["calculations"]:
            issue("EMPTY_INVENTORY", "no calculation rows to reconcile", calculations, "calculations")
            inventory_ids_complete = inventory_states_complete = False
        grouped = {}
        for index, row in enumerate(inventory["calculations"]):
            locator = f"calculations[{index}]"
            if not isinstance(row, dict):
                issue("BAD_ROW", "calculation must be an object", calculations, locator)
                inventory_ids_complete = inventory_states_complete = False
                continue
            key, state = row.get("id"), row.get("claim")
            if not _valid_id(key):
                issue("INVALID_ID", "calculation ID is empty or not a canonical string", calculations, locator, True)
                inventory_ids_complete = inventory_states_complete = False
                continue
            if key in inventory_ids:
                issue("DUPLICATE_ID", f"duplicate calculation ID {key}", calculations, locator, True)
                ambiguous_ids.add(key)
                inventory_ids_complete = inventory_states_complete = False
            inventory_ids.add(key)
            grouped.setdefault(key, []).append(state)
            if state not in STATES:
                issue("UNKNOWN_CLAIM", f"unsupported claim for {key}", calculations, locator)
                inventory_states_complete = False
        # A duplicate is ambiguous even if its last row is well-formed. Never
        # choose a first/last value to manufacture a status contradiction.
        claims = {key: states[0] for key, states in grouped.items()
                  if len(states) == 1 and states[0] in STATES}
    if not preflight_schema:
        issue("BAD_SCHEMA", "expected schema_version=1, status and results map", preflight, "results")
    else:
        if not checked["results"]:
            issue("EMPTY_PREFLIGHT", "no preflight rows to reconcile", preflight, "results")
            preflight_ids_complete = preflight_states_complete = False
        for key, row in checked["results"].items():
            if not _valid_id(key):
                issue("INVALID_ID", "preflight ID is empty or not canonical", preflight, "results", True)
                preflight_ids_complete = preflight_states_complete = False
                continue
            preflight_ids.add(key)
            if not isinstance(row, dict) or row.get("status") not in STATES:
                issue("UNKNOWN_STATUS", f"unsupported preflight status for {key}", preflight, f"results.{key}")
                preflight_states_complete = False
                continue
            statuses[key] = row["status"]
    inventory_valid = inventory_ids_complete and inventory_states_complete
    preflight_valid = preflight_ids_complete and preflight_states_complete
    if inventory_ids_complete and preflight_ids_complete:
        missing, extra = sorted(inventory_ids - preflight_ids), sorted(preflight_ids - inventory_ids)
        if missing or extra:
            issue("ID_SET_MISMATCH", f"missing preflight IDs={missing}; extra preflight IDs={extra}", preflight, "results", True)
    # Each reliable unique pair is sufficient evidence independently of other
    # row gaps. A whole-file/schema parse failure leaves its reliable map empty.
    for key in sorted(claims.keys() & statuses.keys()):
        if claims[key] != statuses[key]:
            issue("ROW_STATUS_MISMATCH", f"{key}: claim={claims[key]}, preflight={statuses[key]}", preflight, f"results.{key}.status", True)
    documents = list(documents)
    if not documents:
        issue("MISSING_SUMMARY", "no README/report supplied", "documents", "input")
    for document in documents:
        text = read(document, "document", False)
        if text is None:
            continue
        if adapter is not None:
            for number, line in enumerate(text.splitlines(), 1):
                match = ASG_COVERAGE.fullmatch(line)
                if match and adapter["coverage"] is not None:
                    stated = dict(zip(("complete", "partial"), map(int, match.groups())))
                    if stated != adapter["coverage"]:
                        issue("COVERAGE_COUNT_MISMATCH", f"declared={stated}; inventory={adapter['coverage']}", document, f"line {number}", True)
                elif "计算：上下界完整" in line and not match:
                    issue("UNPARSED_SUMMARY", "unsupported ASG coverage table", document, f"line {number}")
        summaries, gaps = parse_summaries(text)
        for gap in gaps:
            issue("UNPARSED_SUMMARY", gap["reason"], document, f"line {gap['line']}")
        if not summaries:
            issue("MISSING_SUMMARY", "no complete supported calculation summary found", document, "document")
        for summary in summaries:
            summary["source"] = str(document)
            declarations.append(summary)
            counts, locator = summary["counts"], f"line {summary['line']}"
            if counts["total"] != sum(counts[s] for s in STATES):
                issue("SUMMARY_INTERNAL_MISMATCH", "summary total differs from its status sum", document, locator, True)
            for valid, rows, ids_complete, ids, name in (
                    (inventory_valid, claims, inventory_ids_complete, inventory_ids, "claims"),
                    (preflight_valid, statuses, preflight_ids_complete, preflight_ids, "preflight")):
                if valid and counts != _distribution(rows):
                    issue("SUMMARY_COUNT_MISMATCH", f"declared={counts}; {name}={_distribution(rows)}", document, locator, True)
                elif not valid and ids_complete and counts["total"] != len(ids):
                    issue("SUMMARY_TOTAL_MISMATCH", f"declared total={counts['total']}; {name} unique IDs={len(ids)}; full status distribution unavailable", document, locator, True)
    if len({json.dumps(d["counts"], sort_keys=True) for d in declarations}) > 1:
        issue("CONFLICTING_SUMMARIES", "supplied documents contain conflicting calculation summaries", "documents", "declarations", True)
    verdict = ("FAIL" if any(f["review_result"] == "FAIL" for f in findings)
               else "INSUFFICIENT" if findings else "PASS")
    return {"schema_version": 1, "check_id": "DOC-Q01.DERIVED-SUMMARY",
            "review_result": verdict, "severity": "P2" if verdict == "FAIL" else None,
            "scope": "Derived document calculation inventory and status consistency only; not formula or electrical approval",
            "inputs_sha256": inputs, "cache": {"enabled": False, "hits": 0, "reason": "fresh byte read and reconciliation on every invocation"},
            "actual": {"claims": _distribution(claims) if inventory_valid else None,
                       "preflight": _distribution(statuses) if preflight_valid else None},
            "calculation_ids": sorted(inventory_ids) if inventory_ids_complete else None,
            "preflight_ids": sorted(preflight_ids) if preflight_ids_complete else None,
            "reliability": {"inventory_schema": inventory_schema,
                            "preflight_schema": preflight_schema,
                            "inventory_ids_complete": inventory_ids_complete,
                            "preflight_ids_complete": preflight_ids_complete,
                            "inventory_states_complete": inventory_states_complete,
                            "preflight_states_complete": preflight_states_complete,
                            "ambiguous_calculation_ids": sorted(ambiguous_ids)},
            "reliable_rows": {"claims": dict(sorted(claims.items())),
                              "preflight": dict(sorted(statuses.items()))},
            "adapter": adapter, "declarations": declarations, "findings": findings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calculations", type=Path)
    parser.add_argument("--preflight", type=Path)
    parser.add_argument("--preflight-contract", type=Path, help="ASG design-preflight.json linking child checks to calculation rows")
    parser.add_argument("--document", action="append", type=Path, default=[])
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    result = audit(args.calculations, args.preflight, args.document, args.preflight_contract)
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0 if result["review_result"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())

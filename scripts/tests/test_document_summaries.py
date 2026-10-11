"""Self-authored minimal schema cases, no copied design expressions."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from audit_document_summaries import audit

FIXTURE = Path(__file__).parent / "fixtures" / "document-summaries"


class DocumentSummaryTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(os.environ.get("SR_DOCUMENT_SUMMARY_TMP", "/tmp/codex-work/sr-document-summary-tests"))
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="case-", dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inventory = json.loads((FIXTURE / "calculations.json").read_text())
        self.preflight = json.loads((FIXTURE / "preflight.json").read_text())
        self.summary = (FIXTURE / "README.md").read_text()

    def run_case(self, inventory=None, preflight=None, summary=None, more=()):
        paths = [self.root / name for name in ("calculations.json", "preflight.json", "README.md")]
        for path, data in zip(paths, (self.inventory if inventory is None else inventory,
                                     self.preflight if preflight is None else preflight,
                                     self.summary if summary is None else summary)):
            path.write_text(json.dumps(data) if path.suffix == ".json" else data)
        docs = [paths[2]]
        for index, text in enumerate(more):
            p = self.root / f"report-{index}.md"
            p.write_text(text)
            docs.append(p)
        return audit(*paths[:2], docs)

    def assert_code(self, result, verdict, code):
        self.assertEqual(verdict, result["review_result"])
        self.assertIn(code, {f["code"] for f in result["findings"]})

    def test_correct_english_and_chinese_summaries(self):
        for summary in (self.summary, "3项计算条件检查1SUPPORTED/1CONDITIONAL/1FAIL，不宣称电气放行。"):
            with self.subTest(summary=summary):
                result = self.run_case(summary=summary)
                self.assertEqual("PASS", result["review_result"])
                self.assertEqual({"total": 3, "SUPPORTED": 1, "CONDITIONAL": 1, "FAIL": 1}, result["actual"]["claims"])
                self.assertFalse(result["cache"]["enabled"])

    def test_summary_count_mismatch(self):
        self.assert_code(self.run_case(summary="4项计算条件检查1SUPPORTED/2CONDITIONAL/1FAIL。"), "FAIL", "SUMMARY_COUNT_MISMATCH")

    def test_duplicate_inventory_ids(self):
        self.inventory["calculations"].append(copy.deepcopy(self.inventory["calculations"][0]))
        self.assert_code(self.run_case(), "FAIL", "DUPLICATE_ID")

    def test_duplicate_id_remains_visible_with_invalid_claim(self):
        self.inventory["calculations"].append(copy.deepcopy(self.inventory["calculations"][0]))
        self.inventory["calculations"][0]["claim"] = "UNKNOWN"
        result = self.run_case()
        self.assert_code(result, "FAIL", "DUPLICATE_ID")
        self.assertIn("UNKNOWN_CLAIM", {f["code"] for f in result["findings"]})

    def test_invalid_ids_and_empty_preflight_id(self):
        for key in (None, "", " ", " A ", 3):
            with self.subTest(key=key):
                inventory = copy.deepcopy(self.inventory)
                inventory["calculations"][0]["id"] = key
                self.assert_code(self.run_case(inventory=inventory), "FAIL", "INVALID_ID")
        self.preflight["results"][""] = self.preflight["results"].pop("A")
        self.assert_code(self.run_case(), "FAIL", "INVALID_ID")

    def test_equal_count_different_id_sets(self):
        self.preflight["results"]["OTHER"] = self.preflight["results"].pop("A")
        result = self.run_case()
        self.assert_code(result, "FAIL", "ID_SET_MISMATCH")
        self.assertEqual(result["actual"]["claims"], result["actual"]["preflight"])

    def test_equal_distributions_different_row_statuses(self):
        self.preflight["results"]["A"]["status"], self.preflight["results"]["B"]["status"] = "CONDITIONAL", "SUPPORTED"
        result = self.run_case()
        self.assert_code(result, "FAIL", "ROW_STATUS_MISMATCH")
        self.assertEqual(result["actual"]["claims"], result["actual"]["preflight"])

    def test_reliable_swaps_survive_unrelated_unknown_claim_or_status(self):
        for side in ("claim", "status", "both"):
            with self.subTest(side=side):
                inv, pre = copy.deepcopy(self.inventory), copy.deepcopy(self.preflight)
                pre["results"]["A"]["status"], pre["results"]["B"]["status"] = "CONDITIONAL", "SUPPORTED"
                if side in ("claim", "both"):
                    inv["calculations"][2]["claim"] = "INVALID"
                if side in ("status", "both"):
                    pre["results"]["C"]["status"] = "INVALID"
                result = self.run_case(inv, pre)
                self.assert_code(result, "FAIL", "ROW_STATUS_MISMATCH")
                self.assertEqual(2, sum(f["code"] == "ROW_STATUS_MISMATCH" for f in result["findings"]))
                self.assertIn("UNKNOWN_CLAIM" if side == "claim" else "UNKNOWN_STATUS", {f["code"] for f in result["findings"]})
                self.assertIsNone(result["actual"]["claims" if side == "claim" else "preflight"])

    def test_reliable_consistency_plus_unknown_state_remains_insufficient(self):
        for side in ("claim", "status", "both"):
            with self.subTest(side=side):
                inv, pre = copy.deepcopy(self.inventory), copy.deepcopy(self.preflight)
                if side in ("claim", "both"):
                    inv["calculations"][2]["claim"] = "INVALID"
                if side in ("status", "both"):
                    pre["results"]["C"]["status"] = "INVALID"
                result = self.run_case(inv, pre)
                self.assertEqual("INSUFFICIENT", result["review_result"])
                self.assertNotIn("ROW_STATUS_MISMATCH", {f["code"] for f in result["findings"]})
                self.assertEqual(["A", "B", "C"], result["calculation_ids"])
                self.assertEqual(["A", "B", "C"], result["preflight_ids"])

    def test_unrelated_bad_row_does_not_hide_reliable_pair(self):
        for side in ("inventory", "preflight"):
            with self.subTest(side=side):
                inv, pre = copy.deepcopy(self.inventory), copy.deepcopy(self.preflight)
                pre["results"]["A"]["status"] = "CONDITIONAL"
                if side == "inventory":
                    inv["calculations"][2] = None
                else:
                    pre["results"]["C"] = None
                result = self.run_case(inv, pre)
                self.assert_code(result, "FAIL", "ROW_STATUS_MISMATCH")
                if side == "inventory":
                    self.assertIsNone(result["calculation_ids"])
                self.assertIsNone(result["actual"]["claims" if side == "inventory" else "preflight"])

    def test_complete_id_set_and_total_remain_known_with_unknown_states(self):
        self.inventory["calculations"][2]["claim"] = "UNKNOWN"
        self.preflight["results"]["C"]["status"] = "UNKNOWN"
        self.preflight["results"]["OTHER"] = self.preflight["results"].pop("C")
        result = self.run_case()
        self.assert_code(result, "FAIL", "ID_SET_MISMATCH")
        self.assertIsNone(result["actual"]["claims"])
        self.assertIsNone(result["actual"]["preflight"])
        result = self.run_case(summary="4项计算条件检查1SUPPORTED/2CONDITIONAL/1FAIL。")
        self.assert_code(result, "FAIL", "SUMMARY_TOTAL_MISMATCH")
        self.assertNotIn("SUMMARY_COUNT_MISMATCH", {f["code"] for f in result["findings"]})

    def test_duplicate_id_never_selects_first_or_last_status(self):
        for order in (0, 1):
            for alternative in ("CONDITIONAL", "UNKNOWN"):
                with self.subTest(order=order, alternative=alternative):
                    inv = copy.deepcopy(self.inventory)
                    duplicate = {"id": "A", "claim": alternative}
                    inv["calculations"].insert(0 if order == 0 else 3, duplicate)
                    result = self.run_case(inventory=inv)
                    self.assert_code(result, "FAIL", "DUPLICATE_ID")
                    self.assertNotIn("A", result["reliable_rows"]["claims"])
                    self.assertEqual(["A"], result["reliability"]["ambiguous_calculation_ids"])
                    self.assertIsNone(result["calculation_ids"])
                    self.assertIsNone(result["actual"]["claims"])
                    self.assertNotIn("ROW_STATUS_MISMATCH", {f["code"] for f in result["findings"]})

    def test_duplicate_id_does_not_suppress_other_unique_mismatch(self):
        self.inventory["calculations"].append({"id": "A", "claim": "FAIL"})
        self.preflight["results"]["B"]["status"] = "SUPPORTED"
        result = self.run_case()
        self.assert_code(result, "FAIL", "ROW_STATUS_MISMATCH")
        mismatches = [f for f in result["findings"] if f["code"] == "ROW_STATUS_MISMATCH"]
        self.assertEqual(1, len(mismatches))
        self.assertEqual("results.B.status", mismatches[0]["locator"])

    def test_whole_schema_failure_does_not_fabricate_pairs_sets_or_counts(self):
        for side in ("inventory", "preflight"):
            with self.subTest(side=side):
                inv, pre = copy.deepcopy(self.inventory), copy.deepcopy(self.preflight)
                pre["results"]["A"]["status"], pre["results"]["B"]["status"] = "CONDITIONAL", "SUPPORTED"
                if side == "inventory":
                    inv["schema_version"] = 99
                else:
                    pre["schema_version"] = 99
                result = self.run_case(inv, pre)
                self.assert_code(result, "INSUFFICIENT", "BAD_SCHEMA")
                codes = {f["code"] for f in result["findings"]}
                self.assertNotIn("ROW_STATUS_MISMATCH", codes)
                self.assertNotIn("ID_SET_MISMATCH", codes)
                self.assertNotIn("SUMMARY_TOTAL_MISMATCH", codes)
                self.assertEqual({}, result["reliable_rows"]["claims" if side == "inventory" else "preflight"])

    def test_subset_and_superset(self):
        self.preflight["results"].pop("C")
        self.assert_code(self.run_case(), "FAIL", "ID_SET_MISMATCH")
        self.preflight["results"]["D"] = {"status": "FAIL"}
        self.assert_code(self.run_case(), "FAIL", "ID_SET_MISMATCH")

    def test_unknown_status_claim_and_nonobject(self):
        for side in ("claim", "status", "row"):
            with self.subTest(side=side):
                inv, pre = copy.deepcopy(self.inventory), copy.deepcopy(self.preflight)
                if side == "claim":
                    inv["calculations"][0]["claim"] = "PASS"
                elif side == "status":
                    pre["results"]["A"]["status"] = "PASS"
                else:
                    inv["calculations"][0] = None
                self.assertEqual("INSUFFICIENT", self.run_case(inv, pre)["review_result"])

    def test_bad_schema_cannot_pass(self):
        for bad in ([], {}, {"schema_version": True, "calculations": []}, {"schema_version": 2, "calculations": []}, {"schema_version": 1, "calculations": {}}):
            with self.subTest(bad=bad):
                self.assert_code(self.run_case(inventory=bad), "INSUFFICIENT", "BAD_SCHEMA")
                self.assert_code(self.run_case(preflight=bad), "INSUFFICIENT", "BAD_SCHEMA")

    def test_incomplete_or_unsupported_summary_and_arbitrary_numbers(self):
        for text in ("3项计算条件检查1SUPPORTED/1CONDITIONAL", "3项计算条件检查1SUPPORTED/1CONDITIONAL/1FAILURE", "-3项计算条件检查1SUPPORTED/1CONDITIONAL/1FAIL", "3.0项计算条件检查1SUPPORTED/1CONDITIONAL/1FAIL", "Calculation summary: total=3; SUPPORTED=1; CONDITIONAL=1", "板上3个IC，1个电源。"):
            with self.subTest(text=text):
                self.assertEqual("INSUFFICIENT", self.run_case(summary=text)["review_result"])
        self.assert_code(self.run_case(summary=self.summary + "\n3项计算条件检查"), "INSUFFICIENT", "UNPARSED_SUMMARY")

    def test_internal_mismatch_and_conflicting_summaries(self):
        self.assert_code(self.run_case(summary="4项计算条件检查1SUPPORTED/1CONDITIONAL/1FAIL。"), "FAIL", "SUMMARY_INTERNAL_MISMATCH")
        bad = "4项计算条件检查1SUPPORTED/2CONDITIONAL/1FAIL。"
        self.assert_code(self.run_case(more=(bad,)), "FAIL", "CONFLICTING_SUMMARIES")
        self.assert_code(self.run_case(summary=self.summary + "\n" + bad), "FAIL", "CONFLICTING_SUMMARIES")
        self.assertEqual("PASS", self.run_case(more=(self.summary,))["review_result"])

    def test_empty_and_missing_inputs_cannot_pass(self):
        self.assertEqual("INSUFFICIENT", audit()["review_result"])
        self.assert_code(self.run_case(inventory={"schema_version": 1, "calculations": []}), "INSUFFICIENT", "EMPTY_INVENTORY")
        self.assert_code(self.run_case(preflight={"schema_version": 1, "status": "PASS", "results": {}}), "INSUFFICIENT", "EMPTY_PREFLIGHT")
        self.assert_code(audit(self.root / "absent", self.root / "also-absent", [self.root / "no-document"]), "INSUFFICIENT", "UNREADABLE_INPUT")

    def test_duplicate_json_keys_and_malformed_json(self):
        self.run_case()
        for text in ('{"schema_version":1,"results":{"A":{},"A":{}}}', '{broken'):
            (self.root / "preflight.json").write_text(text)
            self.assert_code(audit(self.root / "calculations.json", self.root / "preflight.json", [self.root / "README.md"]), "INSUFFICIENT", "UNREADABLE_INPUT")

    def test_hash_match_does_not_replace_reconciliation_and_repeated_read(self):
        result = self.run_case()
        bad = self.run_case(summary="4项计算条件检查1SUPPORTED/2CONDITIONAL/1FAIL。")
        self.assertEqual(result["inputs_sha256"][str(self.root / "calculations.json")], bad["inputs_sha256"][str(self.root / "calculations.json")])
        self.assert_code(bad, "FAIL", "SUMMARY_COUNT_MISMATCH")
        for replay in range(2):
            self.assertEqual("FAIL", audit(self.root / "calculations.json", self.root / "preflight.json", [self.root / "README.md"])["review_result"])

    def test_cli_exit_and_output(self):
        self.run_case()
        script = Path(__file__).parents[1] / "audit_document_summaries.py"
        out = self.root / "out.json"
        proc = subprocess.run([sys.executable, "-B", str(script), "--calculations", str(self.root / "calculations.json"), "--preflight", str(self.root / "preflight.json"), "--document", str(self.root / "README.md"), "--json", str(out)], capture_output=True, text=True)
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertEqual("PASS", json.loads(out.read_text())["review_result"])
        proc = subprocess.run([sys.executable, "-B", str(script)], capture_output=True, text=True)
        self.assertEqual(2, proc.returncode, proc.stderr)
        self.assertEqual("INSUFFICIENT", json.loads(proc.stdout)["review_result"])


if __name__ == "__main__":
    unittest.main()

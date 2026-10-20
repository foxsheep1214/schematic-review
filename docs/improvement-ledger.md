# 改进台账

Every entry ends with three lines the test suite checks
(`scripts/check_ledger.py`): `Event:` the review item, datasheet page, test
record or user correction that caused the change; `Causes:` how many items
fell in each cause class (rule_missing, rule_not_enforced, knowledge_missing,
knowledge_wrong, judgment); `Changed:` the files touched. Entries before this
file existed are in `docs/audits/`.

## Function verdicts as the unit of judgement, step 1: results schema 4 (2026-10-20)

The R5 re-review kept 142 rows INSUFFICIENT on 18 distinct gap texts; the
bias-supply record had computed VCC_min 10.24 V > 9.5 V and still waited for a
"full-temperature guaranteed value", and the HV-start row's criterion forbade
the conclusion before it was drawn. The row was the unit of judgement, so one
gap was pasted onto every row that touched the part and no gate asked whether
the analysis already decided it. Schema 4 makes the function verdict the unit:
`functions[]` carries the question, the datasheet clauses read, the calculation
with its margin, the verdict and the open/fail items; rows bind to it with
`function_id`/`aspect`/`open_ref`/`fail_ref` and `gaps`, `gap_cause`,
`work_items`, `request_keys` and `obligations` are derived or retired.
`review_functions.py` enforces F1–F7 (clauses first, design values specified
not requested, vendor requests name what was checked and the worst case, a
positive margin decides, rows follow their function, a changed verdict cites
a clause or number, one item does not undo a whole block unexplained). The R3
ledger replay (schema 3) is retired until the R5 re-review freezes a new one.

- Event: review:SR-20261019-R5-新版复审-2692b08/record/review-results.json (W-BIAS, W-HV), user:2026-10-20 (design docs/2026-10-20-function-verdicts-design.md)
- Causes: rule_not_enforced 3, judgment 2
- Changed: scripts/results_model.py, scripts/review_functions.py, scripts/validate_review.py, scripts/review_workflow.py, scripts/review_quality.py, scripts/review_obligations.py, scripts/tests/ledger_v3.py, scripts/tests/test_review_functions.py, scripts/tests/test_results_model.py, scripts/tests/test_review_stage_scope.py, scripts/tests/test_validate_review.py, scripts/tests/test_requirement_clarifications.py, scripts/tests/test_review_quality.py, scripts/tests/test_r4_review_gaps.py, scripts/tests/test_r5_report_gaps.py, scripts/tests/conftest.py, scripts/tests/fixtures/golden_reports/decisive.md, evals/mutation/RESULTS.md, SKILL.md, references/automation.md, docs/improvement-ledger.md

## Regression over delivered review records (2026-10-19)

The previous entry left SR without a regression set over its own
deliveries, so a validator change could silently break the ledgers already
delivered. `scripts/run_regression.py` registers real review folders in
`tests/regression/boards.json`, re-runs `validate_review` on each
`record/` read-only with the SKILL.md step 7 flags, counts validation
errors, PASS / FAIL / INSUFFICIENT / NA results and the release of the
fresh run against the release written in `review-gate.json`, and compares
with `tests/regression/baseline.json`: more errors or a worse release is
FAIL, a missing folder is skipped, `--update-baseline` accepts the current
numbers. First run: both registered R3/R4 records are schema 2 ledgers,
which the current validator refuses with one error each (release NO_GO
either way), so the baseline records that error, not a clean run.

- Event: user:2026-10-19 (ASG improvement plan stage 0/5, SR regression set), review:SR-20261019-R4-修改后复审-41f4ad3/review-gate.json
- Causes: rule_not_enforced 1
- Changed: scripts/run_regression.py, tests/regression/boards.json, tests/regression/baseline.json, scripts/tests/test_regression.py, docs/improvement-ledger.md, README.md

## Independent re-judgement of ASG's part selection and attribution (2026-10-19)

ASG improvement plan stage 5 (its `docs/improvement-plan.md`). ASG now
delivers `record/selection.json` (decisive conditions, candidates, values
with pages, rejection basis) and attributes every review comment to a cause
class in `review-responses.json` / `lessons.json`. SR had no step that read
either, so a wrong selection or a wrong attribution could stand unchallenged.
`scripts/review_selection.py` builds a blank worksheet from the ASG record
and validates the filled one: each role gets AGREE / DISAGREE /
INSUFFICIENT with a page-cited basis and a verdict on whether ASG's decisive
conditions are complete; DISAGREE must name a part outside ASG's choice or
the specific error in ASG's rejection reasoning; each attributed comment
gets agree/disagree with an alternative cause and reason. The summary feeds
the report's work-item list. Not done here: SR's own regression set over
the same deliveries (needs reproducible review runs; tracked in ASG's plan).

- Event: user:2026-10-19 (accepted ASG improvement plan, stage 5)
- Causes: rule_missing 1
- Changed: scripts/review_selection.py, scripts/tests/test_review_selection.py, scripts/check_ledger.py, scripts/tests/test_ledger.py, references/selection-review.md, references/workflow-handoff.md, SKILL.md, README.md

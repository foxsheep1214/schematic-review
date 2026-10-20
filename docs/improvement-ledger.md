# 改进台账

Every entry ends with three lines the test suite checks
(`scripts/check_ledger.py`): `Event:` the review item, datasheet page, test
record or user correction that caused the change; `Causes:` how many items
fell in each cause class (rule_missing, rule_not_enforced, knowledge_missing,
knowledge_wrong, judgment); `Changed:` the files touched. Entries before this
file existed are in `docs/audits/`.

## Function verdicts, step 6: benches guard the new gates (2026-10-20)

Steps 1–5 added gates that no mutation named: a vendor-ask in a design value,
a positive margin left open, a frame member bound elsewhere, rows derived
without their open items, a prohibition in a question, a plan without frames.
Six mutations (M13–M18) now break each one and are killed by one unit test
each; the gate is 18/18. The R3 ledger replay was retired in step 1 and its
killers (M2/M3/M5/M6/M8) already point at unit tests. `run_regression.py`
still matches its baseline (R3/R4 each refused on schema with one error,
release unchanged) and `bench_coverage.py` runs unchanged; neither needed a
new baseline.

- Event: user:2026-10-20 (design docs/2026-10-20-function-verdicts-design.md §11, step 6)
- Causes: rule_not_enforced 1
- Changed: evals/mutation/mutations.json, evals/mutation/RESULTS.md, evals/mutation/README.md, docs/improvement-ledger.md

## Function verdicts, step 5: the documents say what the scripts now enforce (2026-10-20)

Steps 1–4 changed what a reviewer writes; SKILL and the references still told
them to fill rows, hand-write work items, split gaps with `request_keys` and
keep obligation contracts for PRO-C03/PWR-C15. SKILL step 5 is now three
sub-steps (function verdicts from the plan frames, derive_rows, hand-filled
factual rows) and step 7 reviews functions instead of rows; plan-and-results
describes the three-layer ledger (functions → rows → derived work items), plan
schema 4 (question/function_id/aspect, frames) and results schema 4 with the
bias example and F1–F7, and its shared-gap example is one function with two
open items; verdicts-and-release derives work items from open items;
evidence-proportionality maps its gap causes to open-item kinds and notes that
the five bounding steps travel with each frame; closure-obligations.md is
merged into the function section (isolation qualification and loop stability
are aspects of a function) and removed.

- Event: user:2026-10-20 (design docs/2026-10-20-function-verdicts-design.md §8/§10, step 5)
- Causes: rule_not_enforced 1
- Changed: SKILL.md, references/plan-and-results.md, references/verdicts-and-release.md, references/evidence-proportionality.md, references/report-and-remediation.md, references/requirement-clarifications.md, docs/improvement-ledger.md

## Function verdicts, step 4: the report answers per function (2026-10-20)

The R5 report listed 17 work items and 142 open rows but nowhere said
"bias: works, 0.74 V to spare". The report now opens its count table with
"功能判定 通过 / 没通过 / 未定" and adds "各功能的判断" after the conclusion: one
row per function with its question, verdict, computed result and margin (or
why nothing was computed) and the work items its open/fail items derive to.
Work items and counts already derive from the open items (step 1); the
reused-rationale screen no longer flags rows bound to one function, since
several rows citing the same verdict is the proof, not a copy. Golden reports
now render the schema 4 record the validator saw.

- Event: user:2026-10-20 (design docs/2026-10-20-function-verdicts-design.md §9, step 4), review:SR-20261019-R5-新版复审-2692b08/审查报告.md
- Causes: judgment 1
- Changed: scripts/render_report.py, scripts/review_quality.py, scripts/tests/test_review_functions.py, scripts/tests/test_review_quality.py, scripts/tests/test_golden_reports.py, scripts/tests/fixtures/golden_reports/clean.md, scripts/tests/fixtures/golden_reports/decisive.md, scripts/tests/fixtures/golden_reports/defect.md, scripts/tests/fixtures/golden_reports/downstream.md, references/report-and-remediation.md, docs/improvement-ledger.md

## Function verdicts, step 3: rows derive from the verdict (2026-10-20)

With the frame bound (step 2) the reviewer still typed 15 rows for the R5
bias circuit and pasted the same gap text into each. `derive_rows.py` reads
`functions[]` and writes every bound row: a fail item whose `decides` covers
the row's aspect and state makes it FAIL with the finding, an open item makes
it INSUFFICIENT with `open_ref`, otherwise PASS with a rationale that cites the
verdict, its result and margin; evidence and a planned handoff come from the
function. Hand-filled rows are compared, never overwritten, and a disagreement
or a missing finding/handoff stops the write. On the bias example 15 rows
derive as 2 INSUFFICIENT (PWR-C02 STARTUP/RUN, DESIGN_OPEN) and 13 PASS, and
the validator accepts them with one work item W-AUX-5V-MIN.

- Event: user:2026-10-20 (design docs/2026-10-20-function-verdicts-design.md §5, step 3), review:SR-20261019-R5-新版复审-2692b08/record/review-results.json (PWR-C02..C15 BIAS rows)
- Causes: rule_not_enforced 1
- Changed: scripts/derive_rows.py, scripts/tests/test_derive_rows.py, scripts/tests/conftest.py, SKILL.md, references/automation.md, docs/improvement-ledger.md

## Function verdicts, step 2: the plan asks questions and frames each circuit (2026-10-20)

Step 1 made the function verdict the unit of judgement; the plan still handed
the reviewer a `criterion` per row that embedded the answer ("do not extrapolate
the test condition", "must have a guaranteed value") and no place to write one
verdict per circuit. Plan schema 4: the 48 package member rules carry a
`question` template in `catalog.py` (state, circuit, refs and the rail window
from `intent.power_rails` fill it; generic `criterion` stays as a hint), each
intent circuit becomes a frame in `plan.functions` (question, objects, states,
member rows with their aspect, one blind-spot line per rule, the five bounding
steps copied from evidence-proportionality.md), member rows carry
`question`/`function_id`/`aspect`, and `catalog.question_errors` refuses
prohibition phrasing in any question, reviewer-added rows included.
`review_functions.frame_errors` makes a reviewed member row bind to its frame
and every answered frame have a verdict. `closure_contract`/
`review_obligations.py` are gone: the frame is the contract. kicad_replay gets
revision function-frames-v1 (new field `plan.functions`, new case with three
declared circuits on the rf1 board: checks 298→326 = 5×2+6×2+6×1 member rows).
The R5 intent yields 12 frames and 129 bound member rows, all with an aspect.

- Event: user:2026-10-20 (design docs/2026-10-20-function-verdicts-design.md §6, step 2), review:SR-20261019-R5-新版复审-2692b08/record/review-plan.json (PWR-C02 HV-start criterion)
- Causes: rule_not_enforced 2, judgment 1
- Changed: scripts/catalog.py, scripts/plan_review.py, scripts/electrical_contract.py, scripts/review_functions.py, scripts/validate_review.py, scripts/tests/ledger_v3.py, scripts/tests/test_catalog.py, scripts/tests/test_plan_review.py, scripts/tests/test_review_functions.py, scripts/tests/test_kicad_replay_bench.py, scripts/tests/fixtures/execution-audit/synthetic.json, evals/kicad_replay_bench/run.py, evals/kicad_replay_bench/README.md, evals/kicad_replay_bench/fixtures/rf1-c2000-float-flyback.function-frames-v1.intent.json, evals/kicad_replay_bench/revisions/function-frames-v1/cases.json, evals/kicad_replay_bench/revisions/function-frames-v1/expected.json, evals/kicad_replay_bench/revisions/function-frames-v1/sources.json, evals/kicad_replay_bench/revisions/function-frames-v1/manifest.json, references/automation.md, docs/improvement-ledger.md

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

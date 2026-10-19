# 改进台账

Every entry ends with three lines the test suite checks
(`scripts/check_ledger.py`): `Event:` the review item, datasheet page, test
record or user correction that caused the change; `Causes:` how many items
fell in each cause class (rule_missing, rule_not_enforced, knowledge_missing,
knowledge_wrong, judgment); `Changed:` the files touched. Entries before this
file existed are in `docs/audits/`.

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

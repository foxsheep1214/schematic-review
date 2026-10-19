# 改进台账

Every entry ends with three lines the test suite checks
(`scripts/check_ledger.py`): `Event:` the review item, datasheet page, test
record or user correction that caused the change; `Causes:` how many items
fell in each cause class (rule_missing, rule_not_enforced, knowledge_missing,
knowledge_wrong, judgment); `Changed:` the files touched. Entries before this
file existed are in `docs/audits/`.

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

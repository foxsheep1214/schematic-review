# 改进台账

Every entry ends with three lines the test suite checks
(`scripts/check_ledger.py`): `Event:` the review item, datasheet page, test
record or user correction that caused the change; `Causes:` how many items
fell in each cause class (rule_missing, rule_not_enforced, knowledge_missing,
knowledge_wrong, judgment); `Changed:` the files touched. Entries before this
file existed are in `docs/audits/`.

## Two reviewers of one board: what the record let differ, now refused (2026-10-21)

Two reviews of the same R5 schematic (SR-20261021-R5-claude-fd6a6dd and
SR-20261021-R5-codex-fd6a6dd, same db_sha256, same skill commit) were
compared row by row. They shared 287 of 423 / 487 plan rows and agreed on
184 of them; one found a port ESD defect and a document error, the other a
PFC line-mode shortfall, and neither found the other's; one left 51 rows
undecided, the other 168, with 161 of those called "design not decided".
Both records were valid with zero errors. What the record had let through,
each now a hard error in `review_functions.py` / `review_stage_scope.py` /
`plan_review.py`: (1) every function's `conditions` were two working notes
("相关位号所有物理脚", "## BIAS", says "本轮原厂条款摘录") copied into all
eleven functions, and every judgement rested on them — a condition now
counts as a clause only when its locator names a place a reader can open
(page, table, section, a datasheet section title, a requirement or record
id, a designator, named nets/pins) and its says quotes a number; each
circuit function needs one (F1), each judgement rests on a located
condition (F9), the same unlocated condition in several functions or the
same reason sentence on several open items is a template (F10). (2) One
DESIGN_VALUE decided 10–12 aspects (28 rows each) behind a decides_reason
copied onto every item — a design value or vendor datum decides at most 3
aspects, no reason admits more (F7). (3) Function `objects` were widened past
the intent circuit so a bias gap made the PFC gate-driver and the controller
rows undecided — a frame's function keeps the frame's objects and a row the
reviewer binds to a function names one of its objects (F11). (4) The
connector row with four clamp parts was passed by hand with "各有一颗 TVS"
while the other reviewer computed 9 V clamp against the 6.5 V pin limit — a
PRO-D03 row with `clamp_refs` must be judged in a function (F12). (5) Two
requirement rows were stage NA whole (温度, 寿命) where the other reviewer
passed the temperature grades — a `REQ-D01.<id>` row is never stage NA as a
whole. (6) All 19 requirement criteria were the requirement text verbatim,
and cost/size targets then "passed" — intent refuses a criterion equal to its
text; optimization goals are NA with the text cited (verdicts-and-release).
(7) The delivery's sheets declared one file at a time escaped the delivery
re-judgement gate — pack_review now finds a delivery up to three folders
above any declared file. Replayed under the new rules the second record goes
from 0 to 52 errors in exactly these classes; the first stays at 0 (only the
engine fingerprint moves). `scripts/compare_reviews.py` (new) aligns two
records by circuit (type and shared parts, names and state case aside), keys
rows by rule, circuit, state and part, and lists the rows judged differently,
the findings and open items only one side raised, and the function verdicts
side by side; on the pair it aligns 296 rows with 222 agreeing (75 %).
Not changed: intent circuits are still the reviewer's to draw (the two records
had 10 and 11 with different names and states), so row ids still drift and
only the comparison tool bridges them; the kind chosen for a firmware
configuration (DELIVERABLE_PENDING vs DESIGN_VALUE) is documented, not
guarded. Mutations M44–M51; 1692 tests pass.

- Event: review:原理图审查结果/SR-20261021-R5-codex-fd6a6dd (对照 SR-20261021-R5-claude-fd6a6dd 的逐行差异), user:2026-10-21 (两份结果差异过大，要求让不同 agent 的审查趋同)
- Causes: rule_not_enforced 5, rule_missing 2
- Changed: scripts/review_functions.py, scripts/review_stage_scope.py, scripts/plan_review.py, scripts/pack_review.py, scripts/compare_reviews.py, scripts/tests/test_review_functions.py, scripts/tests/test_review_stage_scope.py, scripts/tests/test_plan_review.py, scripts/tests/test_render_and_pack.py, scripts/tests/test_compare_reviews.py, scripts/tests/conftest.py, scripts/tests/ledger_v3.py, evals/mutation/mutations.json, evals/mutation/README.md, evals/mutation/RESULTS.md, references/plan-and-results.md, references/verdicts-and-release.md, references/automation.md, SKILL.md, docs/improvement-ledger.md

## No aspect passes by default; exits are typed and shown (2026-10-20)

A delivered review record was replayed against the skill to ask what in the
skill let its weaknesses through; the answer was structural, not a missing
rule. (1) Rows passed by omission: `derive_rows.py` made every row PASS unless
an open or fail item covered its aspect, citing the function's one result, so
an aspect nobody judged passed (the replay: 101 of the record's PASS rows).
Now a row passes only on its own aspect's positive margin or a `judgements`
entry `{aspect, conditions, says[, states]}` citing the clauses; otherwise
derive_rows and the validator both refuse it (F9). (2) Every gate had a
free-text exit the reviewer certified alone: `manual_verification` could
override any tool gate, including gaps the reviewer closes by supplying an
input. Checkers now report the gap codes behind a block
(`Checker.blocking_gaps`); a code headed intent/evidence/requirements/
firmware/population/datasheet*/pinout/rail-requirement/level-standard cannot
be overridden (declare it and regenerate the plan); one `method` text over
different objects is refused; the report's SR section lists the gap codes.
(3) Kinds were labels with regex discriminators that phrasing defeats both
ways (a vendor-supplied firmware capability statement was refused, a vendor
datum rephrased slipped through): DELIVERABLE_PENDING now states
`deliverable_kind` (CUSTOM_PART_DRAWING / FIRMWARE_CAPABILITY /
CONFIGURATION_TABLE) and the who-based regex is gone; an unboundable
VENDOR_DATUM answers `operating_point_specified`, and `false` (the design
relies on operation the datasheet does not specify) must be a fail item with a
remediation, not a vendor request. (4) Exits were invisible to the reader: the
work item now shows the worst case under the public bound and why a margin
did not decide (with the loose clause). (5) One assumption sentence copied
into several functions is refused. Also kept from the first pass of this
entry: a pending deliverable requires `scope`, and the report shows its
`assumed`, scope and closure. Replayed under the new rules the record goes
from valid with 0 errors to 128 errors (101 unjudged aspects, 6 input gaps
overridden by hand, 1 shared manual method, 16 public-bound gaps, 1 shared
assumption, 1 loose bound, 2 stale engine). Not changed: report presentation
of handoff refs and requirement ids, NA reused-rationale screening noise.
Mutations M33 (rewritten), M36–M43; gate 43/43.

- Event: user:2026-10-20 (逐章分析交付的审查报告后要求先总结 SR 架构问题再修改：方面缺省通过、出口自证、标签归类、出口不可见)
- Causes: rule_not_enforced 3, rule_missing 2, judgment 1
- Changed: scripts/derive_rows.py, scripts/review_functions.py, scripts/validate_review.py, scripts/checkers/base.py, scripts/checkers/i2c.py, scripts/results_model.py, scripts/review_workflow.py, scripts/render_report.py, scripts/tests/test_derive_rows.py, scripts/tests/test_review_functions.py, scripts/tests/test_render_and_pack.py, scripts/tests/ledger_v3.py, evals/mutation/mutations.json, evals/mutation/README.md, evals/mutation/RESULTS.md, references/plan-and-results.md, references/evidence-proportionality.md, references/report-and-remediation.md, references/verdicts-and-release.md, SKILL.md, docs/improvement-ledger.md

## Open items stop being an exit: public bound first, shortfall means a fix, deliverables get their own kind (2026-10-20)

A review record could leave most of its open work items as VENDOR_DATUM
when, read against the datasheets already in its evidence folder, almost none
was a real data gap; they were quantities the public data already bounded (an
adjacent test point on a monotonic curve, a gate-charge table plus the
driver's own loss equation, a thermistor R-T table the vendor publishes), or
computed shortfalls the reviewer had written into `worst_case` prose rather
than into a fail item with the value change that clears them, or a firmware
capability and a magnetics drawing that no circuit datum answers. The F-rules
let all of that through because `worst_case` only had to be text. Four
tightenings, tests first: (1) F3 `worst_case` names the public bound used
(`bound{condition, value, basis}` with basis GUARANTEED_LIMIT /
ADJACENT_TEST_POINT / TYPICAL_CURVE / PUBLISHED_TABLE / APPLICATION_NOTE),
the result and a structured `margin`; that margin decides like a computed one:
positive concludes unless `margin_not_decisive_reason` says what the bound
misses, zero or negative is a fail item on the aspect. (2) F4 both ways: a
shortfall kept open names in `loose_bound` the condition id whose bound was
taken loose, and a shortfall recorded as a fail item points at a finding that
carries `remediation`. (3) A new open kind DELIVERABLE_PENDING for what
another stage owes (custom magnetics drawing with its insulation system,
firmware/OTP application capability, configuration table): `deliverable`,
`owner`, `assumed`, `closure`; its own gap cause, counted apart from 缺资料
and 设计没定 in the report, no vendor acquisition. (4) Lookup before asking:
calling a quantity unboundable requires `curves_checked` naming the datasheet
figures, published tables and application notes searched; the references
order the public bounds and say a request for "the vendor's guarantee at our
operating point" is unfinished lookup, not a data gap. Mutations M27–M32 guard
the six checks. The synthetic fixtures were updated to the structured
`worst_case`; no stored review record in the repository wrote the field.

- Event: user:2026-10-20 (独立审查复盘：VENDOR_DATUM 先给公开界最坏值、裕量≤0 默认 FAIL+修改建议、新增交付物待就绪类别、lookup 优先公开曲线表)
- Causes: rule_not_enforced 2, rule_missing 1, judgment 1
- Changed: scripts/review_functions.py, scripts/results_model.py, scripts/review_stage_scope.py, scripts/render_report.py, scripts/catalog.py, scripts/tests/test_review_functions.py, scripts/tests/ledger_v3.py, scripts/tests/test_render_and_pack.py, scripts/tests/fixtures/golden_reports/clean.md, scripts/tests/fixtures/golden_reports/decisive.md, scripts/tests/fixtures/golden_reports/defect.md, scripts/tests/fixtures/golden_reports/downstream.md, evals/mutation/mutations.json, evals/mutation/README.md, evals/mutation/RESULTS.md, references/plan-and-results.md, references/evidence-proportionality.md, references/verdicts-and-release.md, references/report-and-remediation.md, references/datasheets.md, SKILL.md, docs/improvement-ledger.md

## The pilot's three frictions fixed: a micro-injection floor, delegated frame rows, scoped ledgers (2026-10-20)

User asked that the three things the hot-review pilot exposed be improved,
not just recorded. (1) The VENDOR_DATUM the pilot raised for a bridge's
internal 3.3 V node that pulls an MCU input through 10 k had no engineering
weight: at most 0.1 V above VDD+0.3 and under 10 µA. `commodity-floors.md`
gains a "micro-injection pull-up" floor: a digital input pulled through
R >= 10 kR to a node whose stated worst-case bound exceeds VDD+0.3 V by at
most 0.3 V, with (bound - VDD_min - 0.3 V)/R <= 30 µA (three orders below the
JESD78 latch-up test current), passes SIG-C07/C08 at grade B with the bound,
R and current written out; analog inputs, datasheet injection limits and
explicit prohibitions are excluded. The pilot's open item is withdrawn under
it. (2) Two circuits declared over the same parts duplicated SIG-C07 rows and,
with open-item keys unique across functions, duplicated the open items;
`frame_errors` now lets a frame member bind to another frame's function when
that function's objects cover the row's refs and nets, so a shared subject is
judged once. (3) A ledger that answers one circuit could never validate
because coverage is owed for the whole board; `review-results.json` may now
declare `review_scope` {functions, reason}: coverage is owed for those
frames' rows only, `scope_checks`/`coverage` are not required, and the gate
reconciles while carrying a blocker that it is not a board verdict (release
stays NO_GO). Tests first for (2) and (3); mutations M25/M26 guard them. The
pilot ledger now validates (12 rows, 9 PASS, 3 FAIL, no quality candidates)
and is stored with the round. The 30 µA / 0.3 V floor is the agent's
proposal, applied once the user asked for the improvement; it is written as a
floor the human can tighten.

Found while gating this: the mutation runner's working copy dropped every
directory named `runs`, including the tracked training rounds that the
ledger's latest entry lists, so the ledger test failed in every copy and any
mutation whose guard test sorts after `test_ledger.py` was reported killed by
the wrong test (M25/M26 showed `test_ledger` as the first failure). The
runner now keeps `evals/training/runs` minus its untracked artefacts, runs the
unmutated copy first and refuses to score when that baseline fails; M25/M26
are killed by their own tests.

- Event: user:2026-10-20 (improve the three frictions the pilot exposed), review:evals/training/runs/2026-10-20-29b9856/hot/olimex-esp32-poe-iso-revN-revN1.before/review-gate.json
- Causes: judgment 2, rule_missing 1
- Changed: scripts/review_functions.py, scripts/validate_review.py, scripts/tests/test_review_functions.py, evals/mutation/run.py, evals/mutation/mutations.json, evals/mutation/README.md, evals/mutation/RESULTS.md, references/commodity-floors.md, references/plan-and-results.md, evals/training/README.md, evals/training/runs/2026-10-20-29b9856/hot/olimex-esp32-poe-iso-revN-revN1.before/review-results.json, evals/training/runs/2026-10-20-29b9856/hot/olimex-esp32-poe-iso-revN-revN1.before/notes.md, evals/training/runs/2026-10-20-29b9856/summary.md, docs/improvement-ledger.md

## Hot-review pilot on the admitted fix pair: the frame asks the right question (2026-10-20)

One hot review of the admitted fix pair's before version, limited to the two
circuits an intent declared (a UART link and its diode-plus-pull-up level
interface), to see whether a circuit-type frame asks about the defect the
author later fixed. It does: once the circuits are declared, the plan frames
SIG-C07 ("does the pull-up rail match every receiver's threshold and pin
limit") and SIG-C08 ("is the back-feed path through pull-ups or protection
diodes blocked") on exactly the pull-up, diode and MCU pin involved. Reading
the two datasheets corrected the mechanism recorded earlier in this ledger
and in the adjudication: the bridge runs in its 5 V mode and tolerates the
5 V node; the violation is on the MCU side, whose TX pad is lifted above
VDD+0.3 V through the forward diode whenever the MCU is in reset, which is
the case the bridge vendor's own application note covers with a series NMOS.
The verdict is one P1 COMPONENT_DAMAGE finding with a READY remediation, and
one VENDOR_DATUM open item (the bridge's internal 3.3 V node has no
guaranteed window in 5 V mode) that is a candidate for the over-strict queue.
The fix pair's `expected_rules` become SIG-C07/SIG-C08; the SIG-D04 written
before was a USB-C rule and an agent error.

Frictions recorded in the round: a partial ledger cannot pass
`validate_review.py` (coverage errors), so a hot review costs a whole board
even when one function is in question; two frames over the same objects
duplicate SIG-C07 rows and, since open-item keys are unique across
functions, duplicate the open items too (`DUPLICATE_WORK_ITEMS`); frame
members may not bind to another frame's function. `metrics.py` now scores
hot recall on a DEFECT finding whose location names the defect, not on any
row text at the location.

- Event: user:2026-10-20 (hot-review pilot requested), review:evals/training/runs/2026-10-20-29b9856/hot/olimex-esp32-poe-iso-revN-revN1.before/review-results.json
- Causes: knowledge_wrong 1, judgment 1
- Changed: evals/training/runs/2026-10-20-29b9856/hot/olimex-esp32-poe-iso-revN-revN1.before/review-results.json, evals/training/runs/2026-10-20-29b9856/hot/olimex-esp32-poe-iso-revN-revN1.before/notes.md, evals/training/runs/2026-10-20-29b9856/summary.md, evals/training/corpus/fix-pairs.json, evals/training/adjudications/2026-10-20.json, evals/training/scripts/metrics.py, evals/training/runs/.gitignore, docs/improvement-ledger.md

## Training round 1 adjudicated: two relaxations, one fix pair admitted (2026-10-20)

The ten-item queue of the first training round was adjudicated by the user
item by item in chat; the agent recorded the decisions in
`evals/training/adjudications/2026-10-20.json` and gave a circuit review of
each verdict afterwards, on which one verdict changed (the PG-to-EN resistor
pair is the reference EN delay plus an improvement, not a defect). Admitted
truth: one fix pair (a UART bridge's RXD pulled to 5 V inside a 3.3 V I/O
domain, class `pull`); rejected: two pairs whose author statements describe
improvements. Seven mature-board cold FINDINGs were judged: four over-strict
(unused modem lines on bidirectional pins, an input with an internal
pull-down, an input with an internal pull-up, a gate driven through a
three-resistor level-shift network), three true (a split reset label, a
controller VDD tied to ground, a reversed electrolytic). Eleven typical
`expected` rows whose `why` said "needs human confirmation" moved to
`known_false_alarms`: the typical bench's expected list is a regression
anchor, not truth.

Two rule relaxations, each allowed by an adjudication and each with its
failing test first: NET-A01 reports a single-node net on an IC's
bidirectional pin as CANDIDATE (inputs, outputs and power pins stay
FINDING, which keeps the split-reset-label defect); DRV-A03 reports a gate
with no direct driver or pull but a driver pin reachable through at most
three resistors as CANDIDATE instead of FINDING (`_Scan.chained_drivers`,
never entering ground or rails; the one-hop <= 1 kR rule for pulls is
unchanged). Mutations M23/M24 guard them; gate 24/24. Mature-board cold
false alarms went from 0.47 to 0.28 per 100 checks, seeded recall and both
gates unchanged. `metrics.py` now dedupes corpus entries by id across
directories so a round's drafts cannot double-count signed pairs.

- Event: user:2026-10-20 (adjudication of training round 1), test:evals/training/adjudications/2026-10-20.json
- Causes: judgment 4, knowledge_missing 1
- Changed: scripts/lint.py, scripts/checkers/power_switch.py, scripts/tests/test_board_scans.py, scripts/tests/test_power_switch.py, evals/mutation/mutations.json, evals/mutation/README.md, evals/mutation/RESULTS.md, evals/typical_circuits/cases.json, evals/training/adjudications/2026-10-20.json, evals/training/corpus/fix-pairs.json, evals/training/corpus/split.json, evals/training/scripts/metrics.py, evals/training/runs/.gitignore, evals/training/runs/2026-10-20-29b9856/summary.md, docs/improvement-ledger.md

## A computed shortfall is a fail item; document checks are not functions (2026-10-20)

A full re-review with function verdicts came back with 18 of 21 functions
open and no circuit defect, while its own calculations showed a required
LED compliance voltage above the guaranteed minimum, a linear pass device
whose thermal target the design admitted it could not meet, and a junction
temperature 0.2 °C under the absolute limit with no project derating. Each
was written as DESIGN_VALUE "设计没定". The rule was already in the
references (算出余量就下结论; 保证要求未满足 is FAIL), but F4 only looked at a
positive `calculation.margin`, and margin was optional: no function in that
record wrote one, so F4 never ran. Now F4 works both ways (a margin at or
below zero needs a fail item, or a `margin_not_decisive_reason` naming the
loose bound), `margin` may be a list with one entry per aspect, and F8 makes
a DESIGN_VALUE item in a function that computed something state the margin
on its aspects or say in `no_margin_reason` what the design has not chosen.
The references say DESIGN_VALUE is only for quantities the design has not
chosen, and that margins are taken against the limit with project derating.

The same record wrapped three document defects (a stale summary number, a
wrong rejection reason for a candidate part) into two self-made functions,
so the report counted two failed functions that are not circuits. A DOC-*
FAIL row bound to a function is now refused; a function whose rows are all
DOC-* (still needed as the entry for a DOC INSUFFICIENT row) is left out of
the function count and table. Mutations M20–M22 cover the new checks; M14
follows the rewritten F4.

- Event: user:2026-10-20 (re-review report: computed shortfalls kept open as design-open, document checks counted as failed functions)
- Causes: rule_not_enforced 1, rule_missing 1
- Changed: scripts/review_functions.py, scripts/results_model.py, scripts/render_report.py, scripts/derive_rows.py, scripts/tests/test_review_functions.py, scripts/tests/ledger_v3.py, references/plan-and-results.md, references/evidence-proportionality.md, references/verdicts-and-release.md, SKILL.md, evals/mutation/mutations.json, evals/mutation/RESULTS.md, docs/improvement-ledger.md

## First training round actually run: the loop was a specification (2026-10-20)

User asked for one round of the self-evolution loop in `evals/training/README.md`
to see whether it works and what it yields. It did not run as written: the
corpus had zero fix pairs and zero mature boards, none of the five scripts of
README §7 existed, no round had ever been recorded, and the README itself still
named one reviewed design and its review record. Done in this round, recorded
under `evals/training/runs/2026-10-20-29b9856/`: the three baseline benches
(typical 0 failing rows, replay 195/195, seeded gate passed, seeded recall
0.882), three draft fix pairs from one Olimex board's revision log (drafts in
the run folder, since corpus files are human-signed), the 42 typical boards as
mature-board proxies, `run_review.py` (cold mode and the hot input pack),
`metrics.py` and `compare.py`, a cold run over all of it, `metrics.json`, an
adjudication queue of ten items, and `summary.md`. No rule changed: README §0
forbids improvements without a human adjudication, and none exists yet.

Two measurement problems the round exposed. First, `fix_pair_recall_cold` as
defined (a FINDING/CANDIDATE that names any ref or net of the defect location)
reads 0.667 while no finding is about any of the three defects: the hits are a
generic EN pull-up candidate on the same net and an unrelated power-pin
finding on the same IC; `fix_pair_recall_plan` reads 1.0 for the same reason
(every IC has DEV rows). Location-based recall over-counts and the per-pair
list in `metrics.json` must be read by eye until a defect-question match is
defined. Second, the run folder's `.gitignore` dropped `metrics.json`, which
`compare.py` needs from the previous round; it now keeps metrics, drafts and
the adjudication queue.

Why cold runs miss all three defects: a missing TVS, a missing PG-to-EN
resistor and a missing pull-down are missing-part defects, and SR's per-object
rows are anchored on parts that exist; the subjects that would ask the
question (protection chain, enable source, level domain) live in circuit-type
frames, which the plan builds only from a declared intent. The round had no
intent for the Olimex board, so `plan.functions` was empty. Fix-pair recall
therefore measures the hot review, not the lint, and the hot review is the
part of the loop that needs a reviewer agent, a critic of another model family
and a human, none of which this round had.

- Event: user:2026-10-20 (run one training round and report), test:evals/training/runs/2026-10-20-29b9856/metrics.json
- Causes: rule_not_enforced 1, judgment 1
- Changed: evals/training/scripts/run_review.py, evals/training/scripts/metrics.py, evals/training/scripts/compare.py, scripts/tests/test_training_metrics.py, evals/training/README.md, evals/training/runs/.gitignore, evals/training/runs/2026-10-20-29b9856/summary.md, evals/training/runs/2026-10-20-29b9856/adjudication-queue.json, docs/improvement-ledger.md

## Functional packages become circuit types with review subjects (2026-10-20)

"功能包" read as a bundle of rules and "成员规则" as a membership, which
hid what they are: a kind of functional circuit and the subjects that
kind must pass. The catalog now defines `CIRCUIT_TYPES` (20 kinds, ids
unchanged: POWER_CONVERTER, RS485, …) with `subjects`; rule source
`package` is `subject`, scope `package` is `circuit_type`;
`catalog.circuit_type()`, `circuit_types_of()`, `circuit_type_criterion()`
replace the package lookups; plan rows and frames carry `circuit_type`
instead of `package`, REQ-Q07/REQ-A02 objects use `circuit_type`, REQ-Q08
lists `circuit_types`, triggers read `circuit-type:…`; the quality codes
are AGGREGATE_CHILD_CIRCUIT_TYPE_MISMATCH and AGGREGATE_SUBJECTS_MISSING.
Plan schema is 5 (plans with the old field are refused; results schema
stays 4). Reader-facing text says 功能电路 / 审查科目 / 科目行 throughout
SKILL, references, the generated catalog and the eval READMEs; dated
design documents and earlier ledger entries keep their wording. The
kicad_replay answers are unchanged (no observed field names the key), so
no new revision.

- Event: user:2026-10-20 (rename 功能包 → 功能电路, 成员规则 → 审查科目; old plans need not be read)
- Causes: judgment 1
- Changed: scripts/catalog.py, scripts/plan_review.py, scripts/review_quality.py, scripts/revision_impact.py, scripts/checkers/i2c.py, scripts/electrical_contract.py, scripts/tests/test_catalog.py, scripts/tests/test_plan_review.py, scripts/tests/test_aggregate_circuit_type_quality.py, scripts/tests/test_i2c_topology.py, scripts/tests/test_electrical_safety.py, scripts/tests/test_context_locators.py, scripts/tests/test_asg_review_scope.py, scripts/tests/test_derive_rows.py, scripts/tests/fixtures/execution-audit/synthetic.json, SKILL.md, README.md, references/check-catalog.md, references/plan-and-results.md, references/automation.md, references/evidence-proportionality.md, references/verdicts-and-release.md, references/revision-review.md, references/review-charter.md, references/datasheets.md, evals/mutation/README.md, evals/mutation/RESULTS.md, evals/rule_contracts/README.md, evals/kicad_replay_bench/README.md, evals/scenarios/array-light-sensor-boundary-cases.md, evals/scenarios/level-shift-cases.md, evals/workflow_guidance/state-and-procurement.md, references/workflow-handoff.md, scripts/tests/fixtures/execution-audit/README.md, docs/improvement-ledger.md

## State-invariant member rules ask once per circuit (2026-10-20)

Package member rules expanded as rules × declared states for every circuit,
so a reverse-polarity direction check or a USB role check was asked again
for each operating state although its answer cannot change with the state.
`catalog.STATE_INVARIANT` names the five rules whose answer is a property of
the topology or interface semantics (PWR-T05, ANA-D01, SIG-T04, SIG-D07,
SIG-D04); the plan generates one row per circuit for them, without `state`
in the object and without "{state} 时" in the question, and the frame lists
the member with `state: null`. PWR-C14 (ripple budget) and the converter
rules stay per state because load and mode change their numbers. Chosen by
what the rule asks, not by any board's results. kicad_replay revision
state-invariant-v1 (frames case 326→325 checks); mutation M19 re-expands the
five rules per state and is killed by the new plan test.

- Event: user:2026-10-20 (state-invariant rules once per circuit; PWR-C14 kept per state)
- Causes: judgment 1
- Changed: scripts/catalog.py, scripts/plan_review.py, scripts/tests/test_catalog.py, scripts/tests/test_plan_review.py, evals/kicad_replay_bench/run.py, evals/kicad_replay_bench/README.md, evals/kicad_replay_bench/revisions/state-invariant-v1/cases.json, evals/kicad_replay_bench/revisions/state-invariant-v1/expected.json, evals/kicad_replay_bench/revisions/state-invariant-v1/sources.json, evals/kicad_replay_bench/revisions/state-invariant-v1/manifest.json, evals/mutation/mutations.json, evals/mutation/README.md, evals/mutation/RESULTS.md, SKILL.md, references/plan-and-results.md, docs/improvement-ledger.md

## No project priors in the tests either (2026-10-20)

The previous entry left the test suite citing the same reviewed design: two
regression files named after its review rounds, docstrings and comments
opening with the project name, and fixtures built from its part numbers,
designators, nets, vendors and computed margins. Every such test now
describes the failure mechanism ("真实反例：…") and runs on synthetic names
(Q2/U1/T1, `evidence/ds/U1.txt`, PFC-A/PFC-B, invented but self-consistent
numbers); the two regression files are `test_rule_gaps_from_reviews.py` and
`test_report_gaps_from_reviews.py`. The ledger entries and the dated design
document keep their review-record citations as provenance.

- Event: user:2026-10-20 (SR must not carry prior information about any specific reviewed circuit; tests included)
- Causes: judgment 1
- Changed: scripts/tests/test_rule_gaps_from_reviews.py, scripts/tests/test_report_gaps_from_reviews.py, scripts/tests/test_review_functions.py, scripts/tests/test_derive_rows.py, scripts/tests/test_board_scans.py, scripts/tests/test_catalog.py, scripts/tests/test_circuit_bounds.py, scripts/tests/test_checkers_framework.py, scripts/tests/test_datasheet_kinds.py, scripts/tests/test_decoupling.py, scripts/tests/test_gap_inventory.py, scripts/tests/test_i2c_topology.py, scripts/tests/test_optocoupler.py, scripts/tests/test_lint.py, scripts/tests/test_ledger.py, scripts/tests/test_model_bounds.py, scripts/tests/test_plan_review.py, scripts/tests/test_power_switch.py, scripts/tests/test_render_and_pack.py, scripts/tests/test_results_model.py, scripts/tests/test_review_quality.py, scripts/tests/test_review_selection.py, scripts/tests/test_supervision_external_paths.py, scripts/tests/test_supervision_requirements.py, scripts/tests/test_validate_review.py, scripts/render_report.py, docs/improvement-ledger.md

## No project priors in the skill (2026-10-20)

The function-verdict examples in the references, two rail-name hints and
several script comments and one validator message were lifted from one
reviewed design: its part numbers, designators, nets, measured margins and
work-item ids. A reviewer reading them would carry that design's answers
into the next board, and the skill would look better on that design than
its method is. Every example is now synthetic and neutral (U1/Q1/T1,
`evidence/ds/U1.txt`, invented but self-consistent numbers), rail-name
hints use generic names, comments describe the failure mechanism without
naming the record, and the SKILL bench note no longer ties the ledger replay
to a particular review round. Test docstrings and fixtures that cite the
same design, and the dated design document, are unchanged here.

- Event: user:2026-10-20 (SR must not carry prior information about any specific reviewed circuit)
- Causes: judgment 1
- Changed: SKILL.md, references/plan-and-results.md, references/evidence-proportionality.md, references/verdicts-and-release.md, references/automation.md, references/report-and-remediation.md, scripts/render_report.py, scripts/review_quality.py, scripts/review_functions.py, scripts/plan_review.py, docs/improvement-ledger.md

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

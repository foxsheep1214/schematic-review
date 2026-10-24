# 改进台账

Every entry ends with three lines the test suite checks
(`scripts/check_ledger.py`): `Event:` the review item, datasheet page, test
record or user correction that caused the change; `Causes:` how many items
fell in each cause class (rule_missing, rule_not_enforced, knowledge_missing,
knowledge_wrong, judgment); `Changed:` the files touched. Entries before this
file existed are in `docs/audits/`.

## An estimate passes with a prototype handoff (SR self-check group 2, item 2.1, 2026-10-24)

The documents and the DEV-C05 and DRV-C02 criteria let a similar part's guaranteed range or typical ±30 % pass a
required-function or performance row (P1 included) when the conclusion holds over the whole range and the prototype
measurement is a required handoff; the gate passed nothing on an ESTIMATE except a life row, so following them was
refused. An ESTIMATE margin that names its `consequence_class` (REQUIRED_FUNCTION or PERFORMANCE_OR_LIFE) and in
`handoff` the complete function handoff that measures it on the prototype now passes its row, the derived row carries
that handoff, and a hand-filled row that drops it is refused. The rules about damage, overheating and protection
(DEV-C01, DEV-C04, PWR-C03, PWR-C06, PWR-C10, DRV-C01, all of PRO) take no estimate. Recorded in architecture.md.
Tests first; 2048 tests pass, contract 518, KiCad replay 195/195, typical circuits unchanged, mutations M513-M520
added, M397 re-pointed, all 143 on changed files killed.

- Event: user:2026-10-24 (SR self-check group 2, item 2.1: "估算 + 样机移交可判通过")
- Causes: rule_not_enforced 1
- Changed: SKILL.md, docs/improvement-ledger.md, evals/mutation/README.md, evals/mutation/mutations.json, references/architecture.md, references/evidence-proportionality.md, references/plan-and-results.md, scripts/derive_rows.py, scripts/review_functions.py, scripts/tests/test_estimate_pass.py

## Choices on what the rules say, first batch (SR self-check group 2, 2026-10-24)

Group 2 of the self-check listed places where the rules could be read two ways; the user chose how each reads. A
typical reference marks a curve with `curve: true`, and only a curve-type reference asks for an estimate of where the
board sits on it (a bool, checked by the gate). A row's `open_ref` may point to an open item of another function when
that item's edge names the row in `check_ids` and decides it; derive_rows finds such an item after the function's own
and before judged, and the function verdict still counts only its own items. The defaults that were lenient on the
real gate path are now required: `validate_review.py` always asks for the bindings and, given a database, for the
plan's dependency record (`--require-bindings` is gone). The intent takes only the fields it documents, suggests the
closest name for an unknown one and needs `schema_version` 4. verdicts-and-release.md says a confirmed P0 cannot be
accepted while a potential P0 can be accepted in writing, giving a conditional release. The late import of netgraph
in i2c_topology removes the circular import group 3 left. Recorded in architecture.md. Tests first; 2040 tests pass,
contract 518, KiCad replay 195/195, typical circuits unchanged, mutations M507-M512 added, M434 re-pointed, all 193 on changed files killed.

- Event: user:2026-10-24 (SR self-check group 2: "曲线标出来，只有曲线要估算", "允许指向别的功能的开项", "改成必填", "字段白名单 + 版本必填", "可以接受放行")
- Causes: rule_missing 3, rule_not_enforced 2
- Changed: SKILL.md, docs/improvement-ledger.md, evals/mutation/README.md, evals/mutation/mutations.json, references/architecture.md, references/evidence-proportionality.md, references/plan-and-results.md, references/revision-review.md, references/verdicts-and-release.md, references/workflow-handoff.md, scripts/derive_rows.py, scripts/i2c_topology.py, scripts/plan_review.py, scripts/results_model.py, scripts/review_functions.py, scripts/tests/test_decoupling.py, scripts/tests/test_derive_rows.py, scripts/tests/test_described_usage.py, scripts/tests/test_gate_defaults.py, scripts/tests/test_i2c_topology.py, scripts/tests/test_intent_fields.py, scripts/tests/test_plan_handoff.py, scripts/tests/test_remediation.py, scripts/tests/test_requirement_clarifications.py, scripts/tests/test_review_v2.py, scripts/tests/test_validate_review.py, scripts/validate_review.py

## One concept, one judgment (SR self-check group 3, 2026-10-24)

Group 3 of the self-check found concepts the code judged several ways that disagreed. A ground is now asked of
`netgraph.is_ground` everywhere (it also takes the VSS family: VSS, AVSS, DVSS, VSSA), and the I²C inventory and the
lint island scan ask netgraph for grounds and rails instead of their own patterns. The part words (electrolytic, with
the EEE/EEU series and the ALUM abbreviation; tantalum, with the TPS series; NTC; varistor; LED; the polarized symbol)
live in netgraph and every module uses them; the LED word is the one board_scans had, so parts named `0402LED` are
LEDs on the plan too (the KiCad replay gains three DEV-C05.PIN-LED rows on r02, new revision shared-part-words-v1;
circuit candidate rules 2026-10-24.1). A value's rated voltage is read by `passive_stress.rated_voltage` (a segment of
its own; two different voltages are not read), finite numbers by `electrical_contract.finite` (a huge integer no longer
raises in calc.py), text without spacing by `electrical_contract.squeeze` / `squeeze_words`. The 1 µF and 10 µF
capacitor thresholds and the per-part assembly fallback of decoupling and I²C differ on purpose and now say why; the
summary counts documented impacts with the consequence class, as the gate does. Tests first; 2030 tests pass,
contract 516, KiCad replay 195/195 on the new revision, typical circuits unchanged, mutations M498-M506 added, M227, M260 and M381 re-pointed, all 314 on changed files killed.

- Event: user:2026-10-24 (SR self-check, "先改1、3、4、5组"; group 3 of docs/2026-10-24-sr-consistency-audit.md)
- Causes: rule_not_enforced 7
- Changed: docs/improvement-ledger.md, evals/kicad_replay_bench/README.md, evals/kicad_replay_bench/run.py, evals/kicad_replay_bench/revisions/shared-part-words-v1/manifest.json, evals/kicad_replay_bench/revisions/shared-part-words-v1/expected.json, evals/kicad_replay_bench/revisions/shared-part-words-v1/cases.json, evals/kicad_replay_bench/revisions/shared-part-words-v1/sources.json, evals/mutation/README.md, evals/mutation/mutations.json, references/automation.md, scripts/audit_datasheets.py, scripts/audit_parameter_claims.py, scripts/board_scans.py, scripts/bound_formulas.py, scripts/checkers/input_filter.py, scripts/checkers/netgraph.py, scripts/checkers/passive_stress.py, scripts/circuit_bounds.py, scripts/circuit_candidates.py, scripts/decoupling.py, scripts/design_preflight.py, scripts/electrical_contract.py, scripts/fault_energy.py, scripts/flyback_stop.py, scripts/i2c_topology.py, scripts/lint.py, scripts/model_bounds.py, scripts/plan_circuits.py, scripts/plan_review.py, scripts/requirement_parameters.py, scripts/review_functions.py, scripts/review_summary.py, scripts/simulate_rc.py, scripts/tests/test_insufficient_impact.py, scripts/tests/test_one_judgment.py, scripts/tests/test_passive_stress.py, scripts/validate_review.py, scripts/zener_fault.py

## Stale text says what the code does now (SR self-check group 4, 2026-10-24)

Group 4 of the self-check listed text that had fallen behind the code. The hand-written head of check-catalog.md gives
the current format versions (intent 4, plan 7, results 6, candidates 2), drops the retired input manifest, and puts
the circuit candidates and decisions in the stage table; the functional-circuit text says circuits come from candidates
and decisions, and a level shifter the candidates miss takes an add decision. REQ-Q08 also confirms where each
unassigned part and each member of a rejected candidate goes; PRO-E01 no longer asks for a life factor (DEV-C06 does).
automation.md gives the candidate schema 2, the modules the planning functions live in and the resistor-capacitor
stress checker; inputs-and-coverage.md says the KiCad parser ships, drops the nested section numbers and no longer
treats designer material as something to check (it is not an input); the bounding table's sources point inside the
skill; quality prompts name the open-item fields the reviewer writes; the identity hash no longer lists files and
sections that do not exist. REQ-Q07 left unwritten when every bound row is NA, the life rows' thermal handoff, the
derived gap_cause and a retired CONDITIONAL value are written as the code has them; "审查审查要点" is "审查要点".
2020 tests pass, contract 516, KiCad replay 195/195, typical circuits unchanged; text only, no mutation added, all 49 on changed files killed.

- Event: user:2026-10-24 (SR self-check, "先改1、3、4、5组"; group 4 of docs/2026-10-24-sr-consistency-audit.md)
- Causes: knowledge_wrong 14
- Changed: docs/improvement-ledger.md, references/automation.md, references/bounding-table.md, references/check-catalog.md, references/execution-consistency.md, references/inputs-and-coverage.md, references/plan-and-results.md, references/review-charter.md, references/verdicts-and-release.md, scripts/catalog.py, scripts/results_model.py, scripts/review_quality.py, scripts/skill_identity.py, scripts/tests/test_asg_review_scope.py, scripts/validate_review.py

## Following the documents no longer runs into a refusal (SR self-check group 1, 2026-10-24)

The self-check of 2026-10-24 found fourteen places where doing what SR says either fails or is refused. The command
blocks now pass `--candidates` wherever the intent has circuit decisions, and SKILL.md step 2 is one numbered command
sequence (cold scan, datasheet audit, candidates, decisions, scan with candidates, request list, audit with the
resolution, merge scan) instead of a candidate command that needs a file two steps later. `lint.py` prints the plan's
prompts (unread resistor values, circuit types that ask almost nothing, rails without a voltage, ground domains,
unbounded nodes) from `plan_review.diagnostic_lines`, which `plan_review.main` also uses. The eight monotonic cells the
gate bounds by G2 now allow G2, and G10 says the board's load is no heavier than the reference circuit's (it said the
reverse). The three JSON examples of plan-and-results.md follow the current formats (circuit decisions instead of a
hand-written circuit list, derivation and corners, condition kinds, gap edges with via and rationale, monotonic_tried
with its cell, design_option NONE with evidence) and a test runs them through the gates. The report section of
report-and-remediation.md follows what render_report.py writes; five quality codes that do not exist are gone; the
TYPICAL_CURVE, intent schema 4, `materials.available`, own-function and add-decision texts match the code. Tests
first; 2020 tests pass, contract 516, KiCad replay 195/195, typical circuits unchanged, mutations M494-M497 added, all
43 on changed files killed.

- Event: user:2026-10-24 (SR self-check, "先改1、3、4、5组"; group 1 of docs/2026-10-24-sr-consistency-audit.md)
- Causes: knowledge_wrong 11, rule_not_enforced 3
- Changed: SKILL.md, docs/2026-10-24-sr-consistency-audit.md, docs/improvement-ledger.md, evals/mutation/README.md, evals/mutation/mutations.json, references/automation.md, references/bounding-table.md, references/datasheets.md, references/evidence-proportionality.md, references/plan-and-results.md, references/report-and-remediation.md, references/reviewed-declarations.md, references/revision-review.md, references/verdicts-and-release.md, scripts/catalog.py, scripts/lint.py, scripts/plan_review.py, scripts/tests/test_bounding_table.py, scripts/tests/test_doc_examples.py, scripts/tests/test_plan_diagnostic_lines.py

## A circuit frame carries the bounding-table cells of its parts (2026-10-24)

Decision A makes the bounding table binding, so the reviewer should not have to look it up: every circuit frame of
the plan now lists `bounds[]`, the table cells that apply to its parts in table order, each with the parts it applies
to, the parameter, the side, the methods in order, their formulas and the fallback. A part takes the cells of its
netlist class; an NTC (a resistor or fuse whose part text says NTC) takes the NTC cells, an electrolytic capacitor
(the 6c test) takes the electrolytic cell instead of the MLCC one, and an IC also takes those of its verified role.
Interface and board frames are unchanged; the plan format is not bumped. Tests first; 2011 tests pass, contract 516,
KiCad replay 195/195, typical circuits unchanged, mutations M487-M493 added, all 69 on changed files killed.

- Event: user:2026-10-23 (bounding table proposal, section 七 and implementation step 4: "做")
- Causes: rule_not_enforced 1
- Changed: docs/2026-10-23-bounding-table-proposal.md, docs/improvement-ledger.md, evals/mutation/README.md, evals/mutation/mutations.json, references/bounding-table.md, references/plan-and-results.md, scripts/catalog.py, scripts/plan_circuits.py, scripts/tests/test_frame_bounds.py

## The operating-point bounding table (2026-10-23)

The same datasheet table was "not boundable" in one review and bounded to a pass or a fail in the other; the
bounding principles sat in four references and a dozen rule criteria as prose, which the gate could not compare.
`catalog.BOUNDS` now registers 31 cells (zener and references, TVS, diodes and bridges, MOSFET and BJT, optocouplers,
NTC, passives, IC parameters), each with the device classes, the parameter, the side it bounds, what it varies with
and which way, the bounding methods in order (G1-G10, SOA, forced beta) with their formulas, and where it falls when
they all fail (VENDOR_DATUM, OUTSIDE_SPECIFIED or BOUNDED); `scripts/bound_formulas.py` holds the 16 formulas
(registered in `calc.py`) and `references/bounding-table.md` is generated from the table. A vendor datum called
unboundable names its cell (`monotonic_tried.cell`, or NONE): the cell's side must match, a BOUNDED cell is refused,
an OUTSIDE_SPECIFIED cell is a fail item, and a test point on the favourable side that gives that side's limit bounds
a monotonic parameter (G2). A margin naming its cell uses one of the cell's methods, a computed method writes
`basis.formula`, and the gate reruns it (0.5 % rounding). SOA by duration and starting case temperature with 100 % /
80 % by segment and the heatsink requirement handed to PCB design (B), NTC table or Beta model with tolerances as a
guarantee (C), forced beta k = 2 (D), hot inrush NTC at 0 ohm (E). Tests first; 2007 tests pass, contract 516, KiCad
replay 195/195, typical circuits unchanged, mutations M456-M486 added, M337 re-pointed, all 153 on changed files
killed.

- Event: user:2026-10-23 (bounding table proposal: "做"; A "必须按表"; B "B 热不稳定段按修订写法定：按持续时间选曲线、按开始壳温降额、降额后留 80%。"; C "有表用表，没表外推算保证"; D k = 2; E 0 Ω)
- Causes: rule_missing 1
- Changed: SKILL.md, docs/2026-10-23-bounding-table-proposal.md, docs/improvement-ledger.md, evals/mutation/README.md, evals/mutation/mutations.json, references/architecture.md, references/bounding-table.md, references/evidence-proportionality.md, references/plan-and-results.md, scripts/bound_formulas.py, scripts/calc.py, scripts/catalog.py, scripts/review_functions.py, scripts/tests/ledger4.py, scripts/tests/test_bound_formulas.py, scripts/tests/test_bounding_table.py, scripts/tests/test_one_sided_bounds.py, scripts/tests/test_review_functions.py

## A design value names what the design has not chosen (2026-10-23)

On the R5 acceptance re-review one review opened a design value for a fault clamp the board's own protection chain
sets, while it held the protection threshold open as a vendor datum; the other review computed the clamp and found a
P1. A design value now lists `undecided[{ref, parameter[, unit]}]`, and a parameter the part's BOM row already states
(its name, then a number in its unit) is refused: the board sets it, so it is computed. A quantity another open item
of the review decides is written `depends_on: <key>`, one level deep, onto an open item that exists; only a design
value carries these fields. A hung design value makes no work item of its own: its rows join the work item of the
item it hangs on, take that item's gap cause, and count under it in the report. Tests first; 1977 tests pass,
contract 516, KiCad replay 195/195, typical circuits unchanged, mutations M443-M455 added, all 143 on changed files
killed.

- Event: user:2026-10-23 (bounding consistency proposals, item 3: "做")
- Causes: rule_not_enforced 1
- Changed: SKILL.md, docs/2026-10-23-bounding-consistency-proposals.md, docs/improvement-ledger.md, evals/mutation/README.md, evals/mutation/mutations.json, references/architecture.md, references/plan-and-results.md, scripts/render_report.py, scripts/results_model.py, scripts/review_functions.py, scripts/tests/ledger4.py, scripts/tests/test_design_value_scope.py, scripts/tests/test_review_functions.py

## Where the datasheet describes the usage, not the test point that misses it (2026-10-23)

On the R5 acceptance re-review all 19 vendor-data items of one review named, as the clause where the datasheet
describes the usage, the very test-point limit that does not reach the operating point; the other review judged the
same points outside the specified region. `worst_case.specified_by` may no longer be one of
`monotonic_tried.test_points`; it names a clause or application text, or a typical curve with a regime, and with a
curve the item gives `worst_case.typical_estimate` (an ESTIMATE citing the curve). An estimate already short is a fail
item, whose margin may be a REACHABLE_CASE read off the typical curve; derivation TYPICAL_CURVE is allowed only for a
reachable case. Tests first; 1967 tests pass, contract 516, KiCad replay 195/195, mutations M433-M442 added, M316 and
M334 re-pointed, all 106 on changed files killed.

- Event: user:2026-10-23 (bounding consistency proposals, item 2 and decision 2-A: "2A，算。")
- Causes: rule_not_enforced 1
- Changed: SKILL.md, docs/2026-10-23-bounding-consistency-proposals.md, docs/improvement-ledger.md, evals/mutation/README.md, evals/mutation/mutations.json, references/evidence-proportionality.md, references/plan-and-results.md, scripts/review_functions.py, scripts/tests/ledger4.py, scripts/tests/test_bound_derivation.py, scripts/tests/test_described_usage.py, scripts/tests/test_review_functions.py

## An unboundable quantity is written in numbers (results format 6, 2026-10-23)

On the R5 acceptance re-review one review called 19 quantities unboundable, 16 with one sentence as the unfavourable
side and the not-boundable reason copied as why_not; one sat between two datasheet test points the other review
bounded from. `worst_case.monotonic_tried` is now {side UPPER/LOWER, quantity, operating_point{min, max, unit},
test_points[{condition in checked, at{value, unit}}], why_not other than the reason, other_side DECIDED (a margin on
the aspect) or NOT_DECISIVE (with a reason)}; a range within the test points is refused as unboundable, a range partly
within opens only open_range outside them and the part within is a margin, and each edge names the open side. A
format-5 record is not read. Tests first; 1958 tests pass, contract 516, KiCad replay 195/195, mutations M419-M432
added, M337 and M339 re-pointed, all 106 on changed files killed.

- Event: user:2026-10-23 (bounding consistency proposals, item 1: "做")
- Causes: rule_not_enforced 1
- Changed: SKILL.md, docs/2026-10-23-bounding-consistency-proposals.md, docs/improvement-ledger.md, evals/mutation/README.md, evals/mutation/mutations.json, references/architecture.md, references/plan-and-results.md, scripts/results_model.py, scripts/review_functions.py, scripts/tests/ledger4.py, scripts/tests/test_bound_derivation.py, scripts/tests/test_one_sided_bounds.py, scripts/tests/test_operating_point_tiers.py, scripts/tests/test_review_functions.py

## Three contradictions in the bounding guidance are settled (2026-10-23)

Moving the scattered bounding guidance into one table (bounding table proposal, section F) found three texts that
disagree. The end-of-life CTR was still "a project decay factor, INSUFFICIENT without it" in datasheets.md,
evidence-proportionality.md, automation.md and the optocoupler checker, which still put "intent: CTR 寿命衰减系数的项目规定"
on every PRO-E01 row, though consistency item 6 moved it to the life row DEV-C06 as a selection constraint; all now say
so and the row no longer asks it. A similar-part or typical ±30% estimate, and a typical-application path, were held to
P2 in DEV-C05, DRV-C02 and PWR-C04 but allowed for P1 functions with a prototype hand-off in
evidence-proportionality.md; the user chose the latter, never for damage, overheating or protection. The zener
guidance now says a slope between two rdif test points is bounded by the lower point's guaranteed rdif (1-A). Tests
first; 1946 tests pass, contract 516, KiCad replay 195/195, typical circuits unchanged, mutations M416-M418 added and
all 9 on changed files killed.

- Event: user:2026-10-23 (bounding table proposal, section F: "按建议")
- Causes: knowledge_wrong 3
- Changed: docs/improvement-ledger.md, evals/mutation/README.md, evals/mutation/mutations.json, references/automation.md, references/check-catalog.md, references/datasheets.md, references/evidence-proportionality.md, scripts/catalog.py, scripts/checkers/optocoupler.py, scripts/tests/test_catalog.py, scripts/tests/test_optocoupler.py

## The comparison counts one datasheet bound used two ways (2026-10-23)

The R5 acceptance re-review left 92 rows open on one side and passed on the other, mostly where the opening review
called a quantity unboundable from a datasheet table the other review bounded from. `compare_reviews.py` now counts,
per side, vendor-data items whose bounding is boilerplate (why_not copies the not-boundable reason, or several items
give one sentence as the unfavourable side) and items naming a test-point limit they read as the clause describing
the usage, and lists each disagreeing pair where the open item read a datasheet file the other side cited in the margin
or fail that decided the row (files, not pages: one reviewer's locators are sections and tables). R5 baseline: A 19 and
19, B 2 and 0; 37 rows on 12 open items. Tests first; 1945 tests pass, contract 516, mutations M407-M415 added and all
14 on the changed file killed.

- Event: user:2026-10-23 (bounding consistency proposals, item 4)
- Causes: rule_missing 1
- Changed: docs/improvement-ledger.md, docs/2026-10-23-bounding-consistency-proposals.md, evals/mutation/README.md, evals/mutation/mutations.json, scripts/compare_reviews.py, scripts/tests/test_compare_bounding_signals.py

## A frame whose rows are all NA needs no function verdict (2026-10-23)

After the B01-B05 fixes the Codex acceptance re-review of R5 met one more: a link frame judged NA throughout (an
analog high-voltage start-up pin has no logic receiver) had no function verdict, and derive_rows refused its rows
because the function lookup ran before the branch that keeps a reviewer's NA; the gate refused a row naming a function
nobody wrote. Both now leave an NA row that names its frame alone. Tests first; 1930 tests pass, contract 516, KiCad replay 195/195, mutations M405-M406 added and all 87 on changed files killed.

- Event: review:SR-20261023-R5-验收-codex-3cfce85/SR缺陷.md (SR-B06)
- Causes: judgment 1
- Changed: docs/improvement-ledger.md, evals/mutation/README.md, evals/mutation/mutations.json, scripts/derive_rows.py, scripts/review_functions.py, scripts/tests/test_derive_rows.py

## Five tool defects the first full acceptance re-review of R5 met (2026-10-23)

The Codex acceptance re-review of R5 judged all 548 rows and stopped at the gate on SR defects it recorded without
patching SR: the gate rebuilt the plan without the candidate file, so a REQ-Q08 row listing both undeclared circuit
types and unassigned parts was taken for a changed automatic row (B01); parts an add decision had placed stayed on
the add/reject list (B02); a limit quoted from the BOM Value column was refused because read_bom keeps that column
in db.parts (B03); derive_rows asked a function for PASS/FAIL/INSUFFICIENT on rows the reviewer judged NA or stage
NA, and re-deriving a row dropped its bom_constraint and requirement_clauses, which life rows and requirement rows
need (B04); and an inductor or transformer declared with an incomplete pin table and no supply pin put
official-full-pinout on the board's decoupling inventory, which no manual verification could clear (B05, the gate
blocker). The gate now rebuilds with the candidate summary the plan keeps, discovery leaves out added parts, the BOM
row includes its Value, derivation keeps a reviewer's NA and the two fields, and a part of a kind without supply pins
and no declared supply pin needs no full pin table for decoupling. Tests first; 1929 tests pass, contract 515, KiCad replay 195/195, typical circuits unchanged, mutations M399-M404 added and all 121 on changed files killed.

- Event: review:SR-20261023-R5-验收-codex-3cfce85/SR缺陷.md (SR-B01 to SR-B05)
- Causes: rule_not_enforced 1, judgment 4
- Changed: docs/improvement-ledger.md, evals/mutation/README.md, evals/mutation/mutations.json, scripts/circuit_decisions.py, scripts/decoupling.py, scripts/derive_rows.py, scripts/review_functions.py, scripts/validate_review.py, scripts/tests/test_circuit_decisions.py, scripts/tests/test_custom_part_spec.py, scripts/tests/test_decoupling_local_scope.py, scripts/tests/test_derive_rows.py, scripts/tests/test_tree_coverage.py

## A datasheet title naming a power factor controller verifies as a PWM controller (2026-10-23)

The first acceptance re-review of R5 stopped at the datasheet audit: a PFC controller's datasheet title says
"Power Factor Controller", the quote was found on the page, but the kind check answered QUOTE_LACKS_TYPE because the
PWM-controller cue words knew "PFC controller" and "power factor correction controller" only. The IC was then not a
verified anchor, its converter circuit was not built and its pin-table row waited for a declaration the reviewer
could not give without rewording the vendor's title. The cue words now include "power factor controller". Tests
first; mutation M398 added and killed.

- Event: review:SR-20261023-R5-验收-codex-6d74689/SR缺陷.md (SR-001, QUOTE_LACKS_TYPE on a verbatim title)
- Causes: knowledge_missing 1
- Changed: docs/improvement-ledger.md, evals/mutation/README.md, evals/mutation/mutations.json, scripts/datasheet_kinds.py, scripts/tests/test_ic_kinds.py

## Life and ageing are judged on one mission profile, and every wear-out part gets a fixed life row (2026-10-23)

Two independent R5 reviews read "10 years" two ways: one took 87600 h of full-time operation, the other 29200 h of
daily full load; one refused the 10 °C doubling rule and opened a vendor-data item for the bulk capacitors' life
model and another for "the project's CTR decay factor", while the other used the doubling rule and wrote a BOM
constraint and did not ask the optocouplers; life rows found only capacitors drawn with a polarized symbol, and no
other wearing part was asked. Intent format 4 now carries `mission_profile` (phases with their share of the design
life, load as a fraction of rated and ambient, counts of power cycles, surges, trips, actuations, matings, charge
cycles and writes, each citing the requirement text), and every life row is planned on it or waits for it. An
electrolytic, solid or super capacitor is found by its symbol, its BOM part number or specification, or an aluminium
package with a voltage and at least 1 µF (tantalum is none); its endurance is estimated with the vendor life formula or
the 10 °C doubling rule, passes as a bom_constraint that says 估算 and the hot spot it assumes, hands the hot spot to
thermal design and opens no VENDOR_DATUM. A new rule DEV-C06 asks each wear-out part (battery, optocoupler, LED,
varistor, fuse, inrush NTC, resettable fuse, relay, connector, switch, memory); a class judged on a count the profile
does not give is planned NA with that reason. The optocoupler row writes the CTR fraction the chain needs at end of
life; PRO-E01 asks no project decay factor. On R5 with a two-phase profile: the same eight capacitor life rows, four
time-based wear-out rows and five NA rows. Tests first; full suite, contract, KiCad replay 195/195 and typical circuits
unchanged, mutations M374-M397 added, M263 and M332 re-pointed, all 176 on changed files killed.

- Event: review:SR-20261023-R5-全新独立复审-1fe4df6/record/review-results.json and review:SR-20261023-R5-从头审查-claude-5802e8c/record/review-results.json (87600 h vs 29200 h, W-LIFE vendor item vs BOM constraint, optocoupler decay item on one side only), user:2026-10-23 (我同意：按“对寿命敏感的器件类型”表定检测范围)
- Causes: rule_missing 3, knowledge_wrong 1, judgment 1
- Changed: SKILL.md, docs/2026-10-23-review-consistency-proposals.md, docs/improvement-ledger.md, evals/mutation/README.md, evals/mutation/mutations.json, references/architecture.md, references/check-catalog.md, references/commodity-floors.md, references/plan-and-results.md, scripts/catalog.py, scripts/plan_circuits.py, scripts/plan_review.py, scripts/requirement_parameters.py, scripts/review_functions.py, scripts/tests/test_catalog.py, scripts/tests/test_life_rows.py, scripts/tests/test_wearout_rows.py

## A programmable device is judged over its allowed configuration range, and its configuration is a row of its own (2026-10-23)

Two independent R5 reviews split one PD controller's configuration three ways: one let a single "configuration table
not delivered" block 57 rows (28 of which the other passed) and recorded on-chip compensation as a design value; the
other passed on the datasheet defaults with three configuration work items and passed the loop on "gain measured on
the prototype"; the configuration table was written as FIRMWARE_CAPABILITY, CONFIGURATION_TABLE and, in the
references, DESIGN_OPEN. Intent format 4: a new domain CFG with rule CFG-D01 "配置值满足要求", one row per device and
configuration group, not repeated per state; a verified pd_controller gets SR's seven fixed groups (capability,
cable/VCONN, protection thresholds and actions, sensing, GPIO role/default/external timing, compensation, discharge and
sequencing), a programmable role without fixed groups (mcu) gets a row asking for its groups, and the reviewer declares
each group in intent.devices.<ref>.configurable {group, citation, allowed, affects[, title, required, set_points]}
(an undeclared group waits for that declaration). Hardware is judged over the allowed range; a condition that holds
only at one setting says setting{ref, group, value} and the device's CFG-D01 row lists it in settings[]; an open item
of kind CONFIGURATION_TABLE blocks only CFG-D01 rows and requirement rows; the references now say configuration tables
are DELIVERABLE_PENDING/CONFIGURATION_TABLE, factory options are identity (DEV-D01), and loop gain or phase margin is a
stage NA with a handoff. A group that lists output set points also gets PWR-C02.SET-POINT-<group>.<ref> for each set
point's accuracy (proposals item 7, sixth trigger). Format-3 intents are refused; the KiCad replay bench moves to
revision intent-format-4-v1 (three intent fixtures copied with schema_version 4, answers unchanged). On R5, with the
datasheet-verified roles, U601 gets the seven CFG-D01 rows, waiting for their declarations. Tests first; 1894 tests
pass, contract 513, KiCad replay 195/195, typical circuits no new unclassified, mutations M360-M373 added and the
mutations on changed files killed.

- Event: review:SR-20261023-R5-全新独立复审-1fe4df6/record/review-results.json and review:SR-20261023-R5-从头审查-claude-5802e8c/record/review-results.json (configuration gap blocks 57 rows vs 3 work items), user:2026-10-23 (第 3 条按建议定：3a–3f 都做，已知角色用 SR 固定的配置组，intent 格式升到 4。)
- Causes: rule_missing 3, knowledge_wrong 1
- Changed: SKILL.md, docs/2026-10-23-review-consistency-proposals.md, docs/improvement-ledger.md, evals/kicad_replay_bench/README.md, evals/kicad_replay_bench/run.py, evals/kicad_replay_bench/revisions/intent-format-4-v1/cases.json, evals/kicad_replay_bench/revisions/intent-format-4-v1/expected.json, evals/kicad_replay_bench/revisions/intent-format-4-v1/manifest.json, evals/kicad_replay_bench/revisions/intent-format-4-v1/sources.json, evals/kicad_replay_bench/fixtures/rh-ad8495-thermocouple.page-inventory-v1.intent-format-4-v1.intent.json, evals/kicad_replay_bench/fixtures/rf1-c2000-float-flyback.rail-confirmation-v1.intent-format-4-v1.intent.json, evals/kicad_replay_bench/fixtures/rf1-c2000-float-flyback.rail-confirmation-v1.frames.intent-format-4-v1.intent.json, evals/mutation/README.md, evals/mutation/mutations.json, references/architecture.md, references/automation.md, references/check-catalog.md, references/evidence-proportionality.md, references/plan-and-results.md, references/verdicts-and-release.md, scripts/board_intent.py, scripts/catalog.py, scripts/derive_rows.py, scripts/plan_circuits.py, scripts/plan_review.py, scripts/review_functions.py, scripts/tests/test_configurable_devices.py, scripts/tests/test_catalog.py, scripts/tests/test_circuit_candidates.py, scripts/tests/test_derived_declarations.py, scripts/tests/test_domains.py, scripts/tests/test_ic_kinds.py, scripts/tests/test_independent_review.py, scripts/tests/test_plan_review.py, scripts/tests/test_render_and_pack.py, scripts/tests/test_requirement_bindings.py, scripts/tests/test_requirement_categories.py, scripts/tests/test_requirement_parameters.py, scripts/tests/test_requirement_source.py, scripts/tests/test_review_v2.py, scripts/tests/test_rule_gaps.py, scripts/tests/test_rule_gaps_from_reviews.py, scripts/tests/test_source_variant_calibration.py, scripts/tests/test_tree_modules.py

## A circuit rule is asked only where its mechanism is on the netlist (2026-10-23)

Two independent R5 reviews wrote 42 rows NA on one side and PASS on the other with the same facts: the plan asked every
rule of a circuit type of every circuit of that type (a power-switch SOA of an AC input with no switch, a compensation
of a source follower or a synchronous rectifier with no loop, reset straps of a start-up circuit with no processor,
all six protection rules of a decoupling group typed as input protection), and took the circuit's first part as the
row object, so one review answered a bridge rectifier's surge rating under the switch SOA. Plan format 7: each
circuit-type rule may carry a precondition judged on the netlist (catalog.SUBJECT_REQUIRES, 17 type-rule pairs over 9
preconditions); a rule whose precondition fails is not asked, the frame lists it under not_asked and the report says
"未问：方面（电路里没有…）"; the row object is the part the precondition found and the row carries requires{id, found
[, unread]}. A precondition drops a rule only on netlist evidence: a part not in the netlist, of unknown kind (a
two-terminal part is no transistor or IC; a bridge, a thermistor or varistor symbol is identified) or an IC without
pin names keeps it; feedback and drive pins count on an IC outside the circuit wired to a circuit net or through a
circuit resistor (a power stage whose driver and output amplifier sit in other circuits keeps its loop rows); named
returns (_RTN) are grounds; an inrush thermistor is no sensor. A type that asks under half its rules of a circuit gets
a CIRCUIT_TYPE_MISFIT hint. A judgement that only says the aspect does not apply, with no netlist fact, is refused
(record NA), and an NA where the plan found the mechanism names the nets or pins that rule it out. On the KiCad replay
boards no row is dropped (the one declared flyback keeps PWR-C04 and PWR-C15 through its external gate driver and
output divider, after the first draft wrongly dropped them); on R5 the plan no longer asks the LED indicator's 9
analog rows, the follower's and the synchronous rectifier's compensation, the AC input's switch and reverse-polarity
rows, the fault latch's switch, inrush and reverse-polarity rows, the HV start-up's 8 reset rows and the decoupling
group's 16 rows, and hints at retyping the three circuits that keep none; every row it keeps names its found part.
Tests first; 1879 tests pass, contract 513, KiCad replay 195/195 (unchanged, revision single-fault-rows-v1), typical
circuits no new unclassified, mutations M340-M359 added, M113-M115 re-pointed to the format-6 plan, and the mutations
on changed files killed (179 with item 3).

- Event: review:SR-20261023-R5-全新独立复审-1fe4df6/record/review-results.json and review:SR-20261023-R5-从头审查-claude-5802e8c/record/review-results.json (42 NA-vs-PASS rows), user:2026-10-23 (第 2 条按建议定：2a–2d 都做，计划格式升到 7。)
- Causes: rule_missing 2, rule_not_enforced 2
- Changed: SKILL.md, docs/improvement-ledger.md, evals/mutation/README.md, evals/mutation/mutations.json, references/architecture.md, references/check-catalog.md, references/plan-and-results.md, scripts/catalog.py, scripts/electrical_contract.py, scripts/plan_circuits.py, scripts/plan_review.py, scripts/render_report.py, scripts/review_functions.py, scripts/validate_review.py, scripts/tests/test_subject_requires.py, scripts/tests/test_catalog.py, scripts/tests/test_plan_review.py, scripts/tests/test_review_v2.py, scripts/tests/test_tree_modules.py

## Two reviews of one board drift less: bounds say how they were derived, gaps block through numbers (2026-10-23)

Two independent R5 reviews (Codex at 1fe4df6, Claude at 5802e8c) agreed on 347 of 516 exactly paired rows. The
disagreements came from a few habits the record allowed: one review blocked 163 rows through clauses of the requirement
documents and wrote 3 margins in all, the other passed calculation rows on sentences, marked a bound on the unfavourable
side of a test point as guaranteed and took an NTC at its nominal value; one shortfall was copied into three identical
margins; a coverage row carried a defect the reviewer picked; a pin sinking an LED current the datasheet gives no
number for was a design defect in one review and absent from the other; and common single faults (port short, hot
restart through the inrush NTC, clamp resistor power, a pin driving an optocoupler, an enable across an optocoupler)
were asked by one side only. Results format 5: a decisive margin names how its bound was derived and the end of each
toleranced input it took, an unboundable quantity first says why the adjacent test point does not bound it, a
requirement clause blocks only the rows bound to that requirement (isolation is now a whole-board aspect), and a
calculation aspect passes only on a margin or the vendor's reference circuit. One margin is not copied onto another
aspect; REQ-Q07 is written by derive_rows.py as coverage and copies no member result; a datasheet's silence is judged in
four tiers (limit exceeded fails, the vendor's reference circuit with the same connection and a load no heavier passes,
a described usage without the number is a vendor datum, an undescribed usage fails outside the specified region with the
operating-condition and pin-description sections searched); a custom part's BOM specification is a design value and its
pending drawing lists only the parameters the BOM leaves out; five single-fault rows are planned on netlist features;
compare_reviews.py names the cause of each disagreement and counts the strict and loose signals per side. On the two
R5 records: 118 INSUFFICIENT-vs-PASS rows (112 through a requirement clause), 42 NA-vs-PASS, 9 with a FAIL; 1d refuses
117 edges in one record and 4 in the other, 1e refuses 32 and 70 calculation rows passed on a sentence; the R5 plan gets
all five single-fault kinds (Q701, TH101, R304/R305, the two U601 GPIO optocoupler drives, U202 to the U201 DIS pin) and
none on the PFC boost diode. Tests first; 1845 tests pass, contract 513, KiCad replay 195/195 under revision
single-fault-rows-v1 (r01, r05 +1 each: an MCP73831 STAT pin driving its LED), typical circuits no new unclassified,
mutations M311-M339 added and the 131 on changed files killed.

- Event: review:SR-20261023-R5-全新独立复审-1fe4df6/record/review-results.json and review:SR-20261023-R5-从头审查-claude-5802e8c/record/review-results.json (347/516 exact pairs agree), user:2026-10-23 (第 1 条按修正后的建议定：1a–1e 都做，1d 用“需求条款只能挡绑定该需求的行”，格式升到 5；首先可以用三分法加参考电路；我同意)
- Causes: rule_missing 3, rule_not_enforced 3, judgment 2
- Changed: SKILL.md, docs/2026-10-23-review-consistency-proposals.md, docs/improvement-ledger.md, evals/kicad_replay_bench/README.md, evals/kicad_replay_bench/run.py, evals/kicad_replay_bench/revisions/single-fault-rows-v1/cases.json, evals/kicad_replay_bench/revisions/single-fault-rows-v1/expected.json, evals/kicad_replay_bench/revisions/single-fault-rows-v1/manifest.json, evals/kicad_replay_bench/revisions/single-fault-rows-v1/sources.json, evals/mutation/README.md, evals/mutation/mutations.json, references/architecture.md, references/check-catalog.md, references/commodity-floors.md, references/evidence-proportionality.md, references/execution-consistency.md, references/plan-and-results.md, scripts/catalog.py, scripts/compare_reviews.py, scripts/plan_circuits.py, scripts/requirement_bindings.py, scripts/results_model.py, scripts/review_functions.py, scripts/validate_review.py, scripts/tests/ledger4.py, scripts/tests/test_bound_derivation.py, scripts/tests/test_calculation_aspects.py, scripts/tests/test_compare_causes.py, scripts/tests/test_coverage_rows.py, scripts/tests/test_custom_part_spec.py, scripts/tests/test_derive_rows.py, scripts/tests/test_i2c_topology.py, scripts/tests/test_operating_point_tiers.py, scripts/tests/test_requirement_bindings.py, scripts/tests/test_requirement_edges.py, scripts/tests/test_results_model.py, scripts/tests/test_review_functions.py, scripts/tests/test_single_fault_rows.py

## SR states its architecture, and an architecture change waits for a person's confirmation (2026-10-23)

SR had no single statement of how it is built: the flow in SKILL.md listed steps and commands, the script table in
automation.md still named two removed scripts and missed thirteen, and nothing said which changes to SR a person must
agree to first. SKILL.md now opens with an architecture section, before the review discipline: a five-ring pipeline
(read in, plan, judge, gate, report) with who does each ring, which file it writes, what the reviewer may not do there,
six standing decisions, and the rule that an architecture change (a ring or the files between rings, a format version,
who judges, the inputs or the delivery, a standing decision, a flow step or entry script) is proposed to a person and
waits for confirmation before code or docs change. references/architecture.md carries the files between rings with
their format versions, every script's ring and kind (it replaces the script table in automation.md) and the record of
architecture decisions. test_architecture.py (contract tier) fails when a script is not placed, a placed script does
not exist, the review flow calls a script that is not an entry, or a format version differs from the code's.
1768 tests pass, contract 507, replay bench 195/195.

- Event: user:2026-10-23 (整个SR技能应当有明确的架构……涉及到架构相关的调整，也应该和人进行交互确认)
- Causes: knowledge_missing 1
- Changed: SKILL.md, references/architecture.md, references/automation.md, scripts/tests/test_architecture.py, scripts/tests/conftest.py, docs/improvement-ledger.md

## The automatic guaranteed-value path is retired and the tests write function verdicts directly (2026-10-23)

Both R5 reviews executed none of the automatic E (guaranteed-value) checks: every E row stayed WAITING_EVIDENCE and was
answered through a function verdict, so evidence.json, the checkers' hot_check computations, datasheet_facts
materialisation, execution_audit and the hot bench served only the September synthetic benches. They are removed: the
E rows are still planned from the netlist or the checker inventories (WAITING_EVIDENCE) and the reviewer judges them
against both datasheets' guaranteed limits; DEV-E02 is retired (DEV-C05 covers it); the formula library (calc.py and its
modules, circuit_bounds, model_bounds, solve_dividers, hotmath number/span) stays for the reviewer's own calculations;
the second lint run only merges the datasheet audit into the final plan; the E rule contracts run on the plan runner
with new near-miss boards. The stopped evals (circuit_bench, hot_bench, prototypes, scenarios, training,
workflow_guidance) are archived in git history (last at 932eb1f) and bench_coverage.py counts A rules only. The test
bridge that turned schema 3 rows into function verdicts (ledger_v3, gap_fixture) is gone: 32 test files write
schema 4 directly through ledger4 (gap, defect, passed, judged, whole_clause). Writing them directly found two defects
the bridge hid: pack_review read gap_cause from the raw record, which schema 4 never writes, so an unfinished review
(REVIEW_INCOMPLETE open item) was packed; and an open item whose checked field was not a list of ids crashed the gate.
Both are fixed (M291-M293). The references drop the evidence.json conventions, the Vref fact reuse and the hot stage,
and datasheets.md states the E judgement points once. 1764 tests pass, replay bench 195/195, contracts all pass.

- Event: review:SR-20261021-R5-claude-fd6a6dd/record/review-results.json (hot_executed 0, 12 E rows WAITING_EVIDENCE), user:2026-10-22 (按照A/B/C/D的顺序，依次执行)
- Causes: rule_not_enforced 2, knowledge_wrong 1
- Changed: README.md, SKILL.md, evals/bench_coverage.py, evals/kicad_replay_bench/README.md, evals/mutation/mutations.json, evals/mutation/run.py, evals/rule_contracts/README.md, evals/rule_contracts/boards/DEV-E01.json, evals/rule_contracts/boards/DRV-E01.json, evals/rule_contracts/boards/PRO-E01.json, evals/rule_contracts/boards/PWR-E01.json, evals/rule_contracts/boards/PWR-E02.json, evals/rule_contracts/boards/PWR-E03.json, evals/rule_contracts/boards/RST-E01.json, evals/rule_contracts/boards/RST-E02.json, evals/rule_contracts/boards/RST-E03.json, evals/rule_contracts/boards/SIG-E01.json, evals/rule_contracts/boards/SIG-E02.json, evals/rule_contracts/contracts.py, evals/typical_circuits/README.md, references/automation.md, references/check-catalog.md, references/datasheets.md, references/evidence-proportionality.md, references/execution-consistency.md, references/plan-and-results.md, references/revision-review.md, references/verdicts-and-release.md, references/wca-formulas.md, scripts/audit_datasheets.py, scripts/catalog.py, scripts/checkers/__init__.py, scripts/checkers/base.py, scripts/checkers/diff_levels.py, scripts/checkers/hotmath.py, scripts/checkers/input_filter.py, scripts/checkers/optocoupler.py, scripts/checkers/power_switch.py, scripts/checkers/power_up.py, scripts/checkers/supervision.py, scripts/electrical_contract.py, scripts/lint.py, scripts/pack_review.py, scripts/plan_board.py, scripts/plan_circuits.py, scripts/plan_review.py, scripts/review_functions.py, scripts/revision_impact.py, scripts/tests/electrical_fixtures.py, scripts/tests/ledger4.py, scripts/tests/test_assembly_identity.py, scripts/tests/test_bom_constraints.py, scripts/tests/test_catalog.py, scripts/tests/test_check_explanations.py, scripts/tests/test_checkers_framework.py, scripts/tests/test_decoupling.py, scripts/tests/test_decoupling_local_scope.py, scripts/tests/test_derive_rows.py, scripts/tests/test_diff_levels.py, scripts/tests/test_electrical_safety.py, scripts/tests/test_esp32_poe_iso_calibration.py, scripts/tests/test_figures.py, scripts/tests/test_golden_reports.py, scripts/tests/test_i2c_topology.py, scripts/tests/test_independent_review.py, scripts/tests/test_input_filter.py, scripts/tests/test_insufficient_impact.py, scripts/tests/test_linear_feedback.py, scripts/tests/test_lint.py, scripts/tests/test_manual_decoupling.py, scripts/tests/test_optocoupler.py, scripts/tests/test_page_inventory.py, scripts/tests/test_passive_stress.py, scripts/tests/test_pin_feeds.py, scripts/tests/test_plan_handoff.py, scripts/tests/test_plan_review.py, scripts/tests/test_power_switch.py, scripts/tests/test_power_up.py, scripts/tests/test_remediation.py, scripts/tests/test_render_and_pack.py, scripts/tests/test_report_gaps_from_reviews.py, scripts/tests/test_requirement_bindings.py, scripts/tests/test_requirement_clarifications.py, scripts/tests/test_requirement_clauses.py, scripts/tests/test_review_evolution.py, scripts/tests/test_review_functions.py, scripts/tests/test_review_quality.py, scripts/tests/test_review_stage_scope.py, scripts/tests/test_review_v2.py, scripts/tests/test_reviewed_declarations.py, scripts/tests/test_revision_impact.py, scripts/tests/test_rule_gaps.py, scripts/tests/test_supervision.py, scripts/tests/test_tree_modules.py, scripts/tests/test_validate_review.py, scripts/validate_review.py, docs/improvement-ledger.md

## The review intent and row evidence do not draw on the designer's documents (2026-10-22)

After the designer-document tools were removed, what else from the designer could still reach a review was looked for
in the R5 records and in SR's own text. One record cited the design report as the reason a function does not apply,
and 8 row evidences on 6 rows came from the designer's calculation results, two self-check records, the design report
and the designer's replies; nothing refused a citation or an evidence by where it came from. SR's text also invited it:
intent.json was called the design intent (设计意图) in the docs, the catalog and the command help; the key-part counts
(REQ-A01) were to be taken from the schematic revision record, the required functions (REQ-A02) from the design intent,
a not-applicable reason from the design intent; the handoff said only the selection, calculation and attribution
records are not used, leaving the designer's electrical intent, requirement trace, device contracts, open items,
self-check and visual summaries, delivery evidence and downstream constraints unstated, and passed ASG's self-check
gaps to SR as they were; a review from scratch started from the design proposal. SR now reads four inputs only: the
requirements, the design results (schematic, netlist, BOM, schematic PDF), manufacturer and standards documents and its
own calculations. independence.py (new) names a designer document by a fixed set of words (design report, design
proposal file, calculation file, electrical intent, requirement trace, device contracts, delivery evidence, design
self-check, replies, selection and lessons records, visual review, downstream constraints, the designer's
record/calculations/); validate_intent refuses any string of the review intent that names one, and validate_review
refuses any row evidence whose source does (a folder named 设计方案/ holding the design results and SR's own
calculation-preflight are not designer documents). intent.json is the review intent everywhere; REQ-A01 takes its
key-part list from the requirements and REQ-A02 its functions from the requirements; the handoff lists the five roles
SR reads and states the rest are carried, not used. R5 bench: one record 1 intent citation and 8 evidences on 6 rows
refused, the other none. Tests first (test_independent_review, 4 new tests; a rule-gap test fixture that cited a design
report now cites a requirement and a datasheet), 1887 tests pass, contract 500, replay bench 195/195, mutations
M213-M219 added and killed.

- Event: review:SR-20261021-R5-claude-fd6a6dd/record/intent.json (features.I2C.citation), review:SR-20261021-R5-claude-fd6a6dd/record/review-results.json (8 evidences on 6 rows), user:2026-10-22 (除了数据之外还有没有利用设计报告中的信息)
- Causes: rule_not_enforced 2, knowledge_wrong 3
- Changed: scripts/independence.py, scripts/plan_review.py, scripts/validate_review.py, scripts/catalog.py, scripts/plan_board.py, scripts/plan_circuits.py, scripts/checkers/powertree.py, scripts/tests/test_independent_review.py, scripts/tests/test_rule_gaps.py, SKILL.md, references/automation.md, references/check-catalog.md, references/commodity-floors.md, references/plan-and-results.md, references/revision-review.md, references/workflow-handoff.md, evals/mutation/mutations.json, evals/mutation/RESULTS.md, evals/mutation/README.md, docs/improvement-ledger.md

## A resistor value with its rated power or voltage is read, and one still unreadable is reported (2026-10-22)

Measuring the per-pin rows on the R5 bench showed that the resistor parser read no resistance for 22 of the 47 fitted
resistors: the values carried a rated power or a rated voltage after the tolerance (1k5/1%/1W, 1M/1%/250V) or a word
(47R/1%/2W/pulse). The grammar took only value, tolerance and package and refused anything else, which is right for a
word it does not know but left every stress bound, divider window and pin current on those parts uncomputed, and
nothing told the reviewer or the user. The value grammar is now value[/tolerance][/rated power][/rated voltage]
[/package]: a rated power (W, mW) and a rated voltage (V), each at most once, are read and kept as power_w and
voltage_v; a rating given twice, a zero rating, a rating after the package or before the tolerance and any other word
still make the value unreadable. Every fitted resistor whose value is still unreadable is a plan diagnostic,
RESISTOR_VALUE_UNREAD, with each part and its value as written; the plan commands (plan_review.py, lint.py --plan-json)
print them, and SKILL.md asks the reviewer to tell the user at once, with the parts and their values, and not to guess
a resistance. R5 bench: unreadable values 22 -> 3 (the three with "pulse", now reported); the bus-sense pin row gets its
pin current (14.1 mA), rows and pairing unchanged (506 of 506 and 510). Tests first (5 parser tests, 2 reporting tests),
1885 tests pass, contract 500, replay bench 195/195, mutations M205-M212 added and killed, the parser and scan
mutations rerun and killed.

- Event: review:SR-20261021-R5-claude-fd6a6dd/record/db.json (22 resistor values unreadable), user:2026-10-22 (1k5 这种写法认不出就要及时反馈)
- Causes: rule_not_enforced 1, knowledge_missing 1
- Changed: scripts/solve_dividers.py, scripts/checkers/passive_stress.py, scripts/plan_review.py, scripts/lint.py, scripts/tests/test_native_resistor_value.py, scripts/tests/test_unread_values.py, SKILL.md, references/wca-formulas.md, evals/mutation/mutations.json, evals/mutation/RESULTS.md, evals/mutation/README.md, docs/improvement-ledger.md

## SR does not take the designer's documents as reference (2026-10-22)

The step-7 recheck proposed one DOC-Q01 row per figure the design report or calculation file claims, because on R5 one
reviewer recomputed two such figures and found both wrong and the other did not look. The user rejected it: referring
to the designer's calculated values lets the design documents set the review (which states, inputs and figures are
looked at), and SR is to be an independent review that derives every value from the schematic, the requirements and
the manufacturer datasheets. SR therefore no longer recomputes designer claims (calc_claims.py removed), audits the
designer's derived summaries (audit_document_summaries.py, asg_summary_adapter.py and document-summaries.md removed;
DOC-Q01 checks only input versions, hashes, export completeness and contradictions between netlist, PDF and BOM) or
re-judges the designer's selection and attribution records (review_selection.py and selection-review.md removed); the
pack no longer requires these for a declared ASG delivery; rail windows come from requirement parameters or the
regulator datasheets with SR's own calculation, not from design calculations. A fact only the design documents state
(a firmware threshold, a register setting) goes to the designer as a handoff and enters the review as a requirement or
input once confirmed. The step-7 entry and the design doc no longer count the two recalculation rows as gaps. Tests
first (test_independent_review: the tools and their docs are gone, no SR script or doc names them, DOC-Q01 does not
audit designer summaries; the pack test of an ASG delivery now packs without reviewing its records; the circuit and
model bound tests that went through calc_claims test the models directly), 1878 tests pass, contract 500, replay
bench 195/195, no mutation targeted the removed code and all 204 still match.

- Event: user:2026-10-22 (不应该去参考设计报告中的内容，SR 本来就应该是独立的审核过程)
- Causes: judgment 1
- Changed: scripts/pack_review.py, scripts/catalog.py, scripts/tests/test_independent_review.py, scripts/tests/test_render_and_pack.py, scripts/tests/test_circuit_bounds.py, scripts/tests/test_model_bounds.py, scripts/tests/test_ledger.py, SKILL.md, references/automation.md, references/check-catalog.md, references/inputs-and-coverage.md, references/plan-and-results.md, references/workflow-handoff.md, docs/2026-10-22-fixed-requirements-and-review-points.md, docs/improvement-ledger.md

## An IC pin fed through a resistor from a rail above the IC's lowest supply gets its own row (2026-10-22)

The first derivation gap from the step-7 recheck. On the R5 bench both reviewers added DEV-C01 rows by hand for the
discharge and bus-sense pins of one controller, each fed through one resistor from a rail above the controller's lowest
supply, where the resistor is the only limit on the pin current; the plan had one DEV-C01 row for the whole circuit,
although the DEV-C01 criterion asks for such pins one by one. The passive-stress inventory (version 3) now lists, per
assembly state, every IC pin that is not a power or return pin, whose net holds only that pin, series resistors and
capacitors with no resistor to ground, and where a resistor's far end is a declared rail above the lowest declared
supply of the IC (supplies from the official pin map, else the symbol's power inputs); each gets a DEV-C01.PIN row with
the source maximum, the resistor minimum and the worst pin current as a calculation and no proposed result. Pull-ups to
the IC's own supply, pins shared with another IC and divider taps get none. Measuring it found a bug from step 3: the
planner built the checkers from the intent before the rail windows a requirement gives were resolved (the netlist scan
already used the resolved ones), so a rail whose window came from a requirement had no window in any checker; the
planner now gives the checkers the resolved intent. R5 bench: both plans get the same two pin rows (2 of 2 paired, the
two hand-added rows of one reviewer and one of the other), no other row or proposal changes, whole plan 506 of 506 and
510; the R5 resistor values are written with power and pulse suffixes the resistor parser does not read, so the
current stays uncomputed there. Of the 7 hand rows that had only a whole-circuit row, 3 now have their pin row and the
other 4 (three switches and a sense pin behind a resistor network) stay rule gaps. Tests first (test_pin_feeds, 7
tests; one test that requirement windows reach the checkers), 1923 tests pass, contract 500, replay bench 195/195,
mutations M197-M204 added and killed, all 204 mutations rerun and killed.

- Event: review:SR-20261021-R5-claude-fd6a6dd/record/review-plan.json (2 hand-added pin rows), review:SR-20261021-R5-codex-fd6a6dd/record/review-plan.json (1 hand-added pin row), user:2026-10-22 (先修 1)
- Causes: rule_not_enforced 2
- Changed: scripts/checkers/passive_stress.py, scripts/plan_review.py, scripts/tests/test_pin_feeds.py, scripts/tests/test_requirement_parameters.py, references/commodity-floors.md, references/plan-and-results.md, evals/mutation/mutations.json, evals/mutation/RESULTS.md, evals/mutation/README.md, docs/improvement-ledger.md

## A row the reviewer adds is a rule gap (2026-10-22)

Step 7 of the fixed-requirements design. Recomputing the two R5 plans with the planner of that run, one reviewer had
added 6 rows by hand and the other 16, outside the automatic-scan rows; one object was added by both, with criteria
worded apart, so no key matched, and the next review would add others. A reviewer who thinks something is to be
checked that the plan does not ask now registers a rule gap in intent.rule_gaps (object, the catalog rule it is judged
under, criterion, what rule or derivation the tool lacks, basis; REQ-D01 refused, requirement rows come from the
requirement source; a part not in the netlist, an unknown rule or a repeated id refused). The planner writes each as
a row with origin REVIEWER_ADDED and its rule_gap, judged like any other; the plan counts them (summary.reviewer_added),
the comparison of two records lists them apart and leaves them out of the pairing rate, the gate lists each gap with
its result (rule_gaps) and the report shows them in the SR feedback section. A row the planner did not write, other
than automatic-scan rows and revision records, is refused when a previous plan is merged and when the gate rebuilds
the plan; the hand-written splits of a board-wide row become rule gaps too. R5 bench: 6 and 9 gaps accepted, 7
requirement rows written as tests refused; whole plan without the added rows 504 of 504 and 508 (alignment 99.6 %),
98.1 % if they were counted. The 15 gaps all sit under rules the catalog already has
(DEV-C01, DEV-C03, DEV-C04, DOC-Q01, DOC-D02, PRO-D03): what is missing is the derivation that puts a rule on a
given object, not the rule. Rechecked against the current planner by rule and part: 5 already have a row for the same
object (an IC's fault and high-voltage startup pins, connector current, an external port's protection, sampling
accuracy); 7 have only a whole-circuit row, not one per part or pin (the stress of three switches, the discharge and
sense pins of an IC fed through a resistor from a high-voltage node), and the derivation to add is a row per IC pin fed
through a resistor from a high-voltage node, which the DEV-C01 criterion already asks for; 3 have no row: 2 recalculate
a figure the design report or calculation file claims (no gap: SR does not refer to the designer's documents, see the
entry of the same day),
and 1, the PCB implementation handoff, was put under the wrong rule (DOC-D02 is test-node reservation) and is carried by
a row's handoff, so it is no gap. The recheck compared rule and part only; whether the 5 existing rows ask the same
question is still to be read row by row. The two-record comparison over steps 1-7 is in the design doc's
acceptance table: requirement rows 61 of 61 (0 of 38 before), whole plan 99.2 % (94.8 % before), rail and circuit
candidates equal, +9.1 % rows; category and parameter agreement between two agents is left for the next two-agent
run. Tests first (test_rule_gaps, 7 tests; the tests that carried manual rows through a previous plan register them as
gaps), 1915 tests pass, contract 500, replay bench 195/195, mutations M184-M196 added and killed, the mutations on the
touched files rerun.

- Event: review:SR-20261021-R5-claude-fd6a6dd/record/review-plan.json (6 hand-added rows), review:SR-20261021-R5-codex-fd6a6dd/record/review-plan.json (16 hand-added rows), user:2026-10-22 (分步完成第 1 到第 7 步)
- Causes: rule_not_enforced 10, judgment 1
- Changed: scripts/rule_gaps.py, scripts/plan_review.py, scripts/validate_review.py, scripts/compare_reviews.py, scripts/render_report.py, scripts/tests/test_rule_gaps.py, scripts/tests/test_manual_decoupling.py, scripts/tests/test_revision_impact.py, scripts/tests/test_check_explanations.py, scripts/tests/test_decoupling.py, scripts/tests/test_i2c_topology.py, scripts/tests/test_plan_handoff.py, SKILL.md, references/plan-and-results.md, references/automation.md, references/check-catalog.md, docs/2026-10-22-fixed-requirements-and-review-points.md, evals/mutation/mutations.json, evals/mutation/RESULTS.md, evals/mutation/README.md, docs/improvement-ledger.md

## Every official supply pin of a declared device is a decoupling group (2026-10-22)

Step 6 of the fixed-requirements design. On the R5 bench one reviewer declared a decoupling group on a startup
controller's HV pin and the other did not, so four rows existed in one plan only; each reviewer's group list matched
exactly the power-role pins of their own pin map, so the list repeated the pin map by hand and could drift from it.
Decoupling section schema 4: the inventory makes one group per declared device and supply net from the official pin
map (power pins of one device on one net merged, a power pin off the netlist its own group with its gap, a verified
connector, bridge or transformer grouped only by an explicit entry); a group entry names its (ref, net) and gives only
the purpose, the clauses and, where the return pins sit on several nets, the return net, and an entry on a net no
power pin of its device sits on, an entry given twice, or one writing id or supply_nodes is refused; reviewed
declarations merge entries by (ref, net). The other checker sections were not changed: on R5 their objects were
already equal (power switches 15, inductive loads 6, optocouplers 6, supervision 1 row), the optocoupler section only
carries values. R5 bench: groups equal each reviewer's power pins (5 and 6), decoupling rows 20 of 20 and 24, the
same with no entries at all; the remaining group is one pin-role reading (the HV pin power in one map, other in the
other), now visible only in the pin map. The replay bench gets contract decoupling-pin-map-v1: in
rh-ad8495-thermocouple-pinmap U201:VCC is a pin-map group instead of a candidate to confirm (one gap fewer). Tests first
(test_decoupling_auto_groups, 7 tests; the decoupling fixtures move to (ref, net) entries and the tests of hand-listed
supply nodes to pin-map groups), 1908 tests pass, contract 500, replay bench 195/195, mutations M177–M183 added and
killed, M126 and M127 retargeted to the rewritten code and killed, the other mutations on the touched files rerun.

- Event: review:SR-20261021-R5-claude-fd6a6dd/record/intent.json (decoupling, devices), review:SR-20261021-R5-codex-fd6a6dd/record/intent.json (decoupling, devices), user:2026-10-22 (分步完成第 1 到第 7 步)
- Causes: rule_not_enforced 1
- Changed: scripts/decoupling.py, scripts/reviewed_declarations.py, scripts/tests/test_decoupling_auto_groups.py, scripts/tests/test_decoupling.py, scripts/tests/test_decoupling_fixed_kinds.py, scripts/tests/test_manual_decoupling.py, scripts/tests/test_asg_review_scope.py, scripts/tests/test_plan_handoff.py, scripts/tests/test_reviewed_declarations.py, evals/kicad_replay_bench/run.py, evals/kicad_replay_bench/README.md, evals/kicad_replay_bench/revisions/decoupling-pin-map-v1/manifest.json, evals/kicad_replay_bench/revisions/decoupling-pin-map-v1/cases.json, evals/kicad_replay_bench/revisions/decoupling-pin-map-v1/expected.json, evals/kicad_replay_bench/revisions/decoupling-pin-map-v1/sources.json, SKILL.md, references/automation.md, references/plan-and-results.md, references/reviewed-declarations.md, docs/2026-10-22-fixed-requirements-and-review-points.md, evals/mutation/mutations.json, evals/mutation/RESULTS.md, evals/mutation/README.md, docs/improvement-ledger.md

## What decides which rows exist is derived, and the reviewer only confirms (2026-10-22)

Step 5 of the fixed-requirements design. On the R5 bench one reviewer declared a platform checklist available and
the other did not, which set rows waiting or ready; one listed seven circuit types as applicable that the candidates
had already found; both reached the same nine rails only because both happened to declare the same name-unlike supply
nets. A material is now available when the file `materials.<key>.path` names exists (requirements from the
requirement source, datasheets from the datasheet audit), and `available` is refused, as is a path that does not
exist; with circuits from candidates, `features` may not name a type intent.circuits has nor say APPLICABLE, so it
only explains why a catalog type the candidates did not find does not apply; `powertree.supply_candidates` scans every
net, and each one that behaves as a supply (a fitted IC draws supply from it, or 1 uF or more to ground) without a
rail name must be declared in power_rails or excluded with a reason in `rail_exclusions` (an exclusion of another net,
without a reason or of a declared net is refused); the plan lists them as `rail_candidates`. R5 bench: both reviewers
get the same 11 candidates (4 by name, 5 declared, 2 excluded), all rows 504 of 504 and 508 (99.2 %), paired rows
with the same readiness and inputs 492 of 504 (489 of 503 before); what remains is the load refs of nine rail
budgets, one connector pinout and one I2C not-applicable only one reviewer wrote. Rails are not identified from the
netlist alone (the R5 sets were already equal) and the window-source priority is not enforced (nothing machine-checks
it). The replay bench gets contract rail-confirmation-v1: the two rf1 cases with an intent use copies that exclude
VOUT_N, the isolated output return, and the frozen revisions keep their bytes. Tests first
(test_derived_declarations, 7 tests; material fixtures move to paths), 1901 tests pass, contract 500, replay bench
195/195, mutations M166–M176 added and killed (M168, M171, M174 survived first; their tests had another error or only
an existing file).

- Event: review:SR-20261021-R5-claude-fd6a6dd/record/intent.json (materials, features, power_rails), review:SR-20261021-R5-codex-fd6a6dd/record/intent.json (materials, features, power_rails), user:2026-10-22 (分步完成第 1 到第 7 步)
- Causes: rule_not_enforced 1
- Changed: scripts/checkers/powertree.py, scripts/plan_review.py, scripts/plan_board.py, scripts/tests/test_derived_declarations.py, scripts/tests/test_electrical_safety.py, scripts/tests/test_plan_review.py, evals/kicad_replay_bench/run.py, evals/kicad_replay_bench/README.md, evals/kicad_replay_bench/revisions/rail-confirmation-v1/manifest.json, evals/kicad_replay_bench/revisions/rail-confirmation-v1/cases.json, evals/kicad_replay_bench/revisions/rail-confirmation-v1/expected.json, evals/kicad_replay_bench/revisions/rail-confirmation-v1/sources.json, evals/kicad_replay_bench/fixtures/rf1-c2000-float-flyback.rail-confirmation-v1.intent.json, evals/kicad_replay_bench/fixtures/rf1-c2000-float-flyback.rail-confirmation-v1.frames.intent.json, SKILL.md, references/plan-and-results.md, docs/2026-10-22-fixed-requirements-and-review-points.md, evals/mutation/mutations.json, evals/mutation/RESULTS.md, evals/mutation/README.md, docs/improvement-ledger.md

## A requirement aspect a tree check already asks is bound to that check (2026-10-22)

Step 4 of the fixed-requirements design. After step 2 every (requirement, aspect) had its own REQ-D01 row, so an
aspect the tree already asks (the parts' temperature grade is the recommended-operating-condition rows, derating is
the stress rows, the lifetime basis is the capacitor-life rows) was judged twice, once in requirement prose that could
disagree with the tree rows. The catalog names, for 19 of the 26 aspects, the tree rules that carry it
(ASPECT_RULES, rendered in check-catalog.md), four of them aspects of the whole board; a requirement may name the
circuits, interfaces or system functions that implement it (`owners`). `requirement_bindings.py` (new) binds each
requirement row to the rows of its aspect's rules those owners own, or, for a board aspect with no owners, to every
row of those rules (`bound_checks`, outside the check identity); the validator recomputes the bindings and refuses an
owner that owns no row; a requirement row with a judged bound row takes the worst bound result (the validator
refuses another result, and such a row needs no clauses), and derive_rows.py writes it, carrying the failing row's
finding (and linking the requirement row from it) or the open item, and comparing, never overwriting, a hand-filled
row. R5 bench with one owner assignment for both reviewers: 41 of 61 requirement rows bound (299 bindings, 123
distinct tree rows), 20 judged on the requirement row, bindings 61/61 equal, check keys and row counts unchanged.
Tests first (test_requirement_bindings, 9 tests), 1894 tests pass, contract 500, replay bench 195/195, mutations
M156–M165 added and killed.

- Event: review:SR-20261021-R5-claude-fd6a6dd/record/intent.json (requirements), review:SR-20261021-R5-codex-fd6a6dd/record/intent.json (requirements), user:2026-10-22 (分步完成第 1 到第 7 步)
- Causes: rule_not_enforced 1
- Changed: scripts/requirement_bindings.py, scripts/catalog.py, scripts/plan_review.py, scripts/plan_board.py, scripts/validate_review.py, scripts/derive_rows.py, scripts/tests/test_requirement_bindings.py, scripts/tests/test_derive_rows.py, SKILL.md, references/plan-and-results.md, references/automation.md, references/check-catalog.md, docs/2026-10-22-fixed-requirements-and-review-points.md, evals/mutation/mutations.json, evals/mutation/RESULTS.md, evals/mutation/README.md, docs/improvement-ledger.md

## A requirement's numbers are read into fixed parameters that the plan uses (2026-10-22)

Step 3 of the fixed-requirements design. On the R5 bench the two reviewers' rail windows agreed on 3 of 13 shared
rails, and the requirement numbers (input range, output levels, ambient temperature, lifetime) stayed in requirement
prose that no row or calculation read. The catalog has a requirement parameter table (14 names, each with a canonical
unit and the spellings it accepts) rendered into check-catalog.md; `requirements[].parameters` holds
{name, min, max, unit, condition}, and `requirement_parameters.py` (new) refuses an unknown name or unit, a number
that does not appear in that requirement's original text (a ± number gives both signs; a dash right after a digit is a
range), a condition that is not a piece of the text, and min above max. The parameters, in canonical units, ride on
each requirement row outside the check identity; `power_rails.<net>.voltage_v: {"requirement": <id>}` takes that
requirement's voltage range in the planner, the lint and the intent check; the required input range reaches the
SYS-POWER frame (`requirement_windows` and its question), and the ambient temperature and lifetime reach the part
stress rows (DEV-C01/C02/C05 `conditions`, the plan's `conditions` listing each source). R5 bench: 20 parameters read
from 10 requirements, none refused against the real text, check keys identical to step 2, 54 stress rows carry the
conditions, the output rail's window taken from its requirement. Only the output rail corresponds to a requirement;
the other rails' windows are internal stress ranges whose derivation is step 5. Tests first
(test_requirement_parameters, 12 tests), 1885 tests pass, contract 500, replay bench 195/195, mutations M146–M155
added and killed (M155 survived first: the frame test checked only the number, now the whole phrase).

- Event: review:SR-20261021-R5-claude-fd6a6dd/record/intent.json (requirements, power_rails), review:SR-20261021-R5-codex-fd6a6dd/record/intent.json (requirements, power_rails), user:2026-10-22 (分步完成第 1 到第 7 步)
- Causes: rule_not_enforced 1
- Changed: scripts/requirement_parameters.py, scripts/catalog.py, scripts/plan_review.py, scripts/plan_board.py, scripts/plan_system.py, scripts/lint.py, scripts/tests/test_requirement_parameters.py, SKILL.md, references/plan-and-results.md, references/automation.md, references/check-catalog.md, docs/2026-10-22-fixed-requirements-and-review-points.md, evals/mutation/mutations.json, evals/mutation/RESULTS.md, evals/mutation/README.md, docs/improvement-ledger.md

## A requirement is placed in fixed categories and asks each category's aspects (2026-10-22)

Step 2 of the fixed-requirements design. After step 1 the R5 pair still paired none of the 38 requirement rows: both
took the same ids, texts and statuses, but each wrote its own criterion, one copying the text and the other rewriting
it, and a rewrite often kept one or two aspects (a temperature requirement checked only the temperature grade, not
derating or drift; a lifetime requirement only the electrolytic capacitors). The catalog now has a requirement
category table (11 categories, 26 aspects, each aspect with a criterion template, one aspect shared by two categories)
and renders it into check-catalog.md; each `requirements[]` entry names its `categories` and writes its reading as
`interpretation` (a free `criterion` is refused, an interpretation that copies the original text is refused, unknown
or repeated categories are refused); the planner writes one REQ-D01 row per (requirement, aspect), the aspect in the
row object and the template as the criterion, several categories asking the union of their aspects, and the
interpretation rides on the row outside the check identity. R5 bench with both intents in the category form (one
category assignment for both, each reviewer's old criterion as its interpretation): requirement rows 61/61 paired,
all rows 503 of 503 and 508 (99.0 %, acceptance 4 met), 42 more rows per plan than after step 1 (9.1 %, within the
15 % of acceptance 6), the rest being the decoupling group only one reviewer declared and one test point; the 19
interpretations that copy the text are refused. Category agreement between two agents (acceptance 2) cannot be read
from these records and waits for the next two-agent run; the section-to-status map and the column pre-split were not
done (statuses already agree 19/19 and requirement-clarifications.md asks for each source label to be split, not
mapped by section; clauses stay out of the check identity). Tests first (test_requirement_categories, 9 tests;
requirement fixtures move to categories and interpretation), 1873 tests pass, contract 500, replay bench 195/195,
mutations M139–M145 added and killed.

- Event: review:SR-20261021-R5-claude-fd6a6dd/record/intent.json (requirements), review:SR-20261021-R5-codex-fd6a6dd/record/intent.json (requirements), user:2026-10-22 (分步完成第 1 到第 7 步)
- Causes: rule_not_enforced 1
- Changed: scripts/catalog.py, scripts/plan_review.py, scripts/plan_board.py, scripts/tests/test_requirement_categories.py, scripts/tests/test_requirement_source.py, scripts/tests/test_requirement_clauses.py, scripts/tests/test_catalog.py, scripts/tests/test_plan_review.py, scripts/tests/test_review_v2.py, SKILL.md, references/plan-and-results.md, references/check-catalog.md, docs/2026-10-22-fixed-requirements-and-review-points.md, evals/mutation/mutations.json, evals/mutation/RESULTS.md, evals/mutation/README.md, docs/improvement-ledger.md

## Requirements are transcribed by a tool, never retyped (2026-10-22)

Step 1 of the fixed-requirements design. On the R5 bench the two reviewers took the same 19 requirement ids from one
requirement table and agreed on every status, yet not one transcribed text matched once punctuation was set aside:
the table has a requirement column and a boundary column, and each joined, cut and punctuated them its own way. The
rule, the clause check and the intent check also disagreed: the catalog said the acceptance criterion is the original
text, the clause error said the clauses must rebuild the original text, the clause check compared them with the
reviewer's criterion, and `validate_intent` refused a criterion that copies the text. `requirements_extract.py` (new)
reads Markdown tables keyed by an id column, and `- <ID>：<text>` list items, verbatim, each column apart, with the
section, a file:line locator and the file's sha256, and refuses a repeated id; the intent's `requirement_source` names
the file and digest, and each `requirements[]` entry holds only `id`, `criterion` and `status` (text and citation are
refused). The planner transcribes the file again when it builds the plan, every source id must be in the intent and
every intent id in the source, a changed file is refused until transcribed again, the REQ-D01 row carries the
transcription as `source_text`, its clauses must rebuild that original text, and the catalog entry now says the
criterion states what is judged on the schematic and is not a copy. R5 bench: the tool reads 19 requirements from the
document, exactly the ids both reviewers took, both columns apart, no errors. Tests first (test_requirement_source,
11 tests, and a clause test; fixtures move to a transcribed source), 1865 tests pass, contract 500, replay bench
195/195, mutations M131–M138 added and killed and the earlier mutations on the touched files rerun.

- Event: review:SR-20261021-R5-claude-fd6a6dd/record/intent.json (requirements), review:SR-20261021-R5-codex-fd6a6dd/record/intent.json (requirements), user:2026-10-22 (需求整理结果要相对固化；分步完成第 1 到第 7 步)
- Causes: rule_not_enforced 1, knowledge_wrong 1
- Changed: scripts/requirements_extract.py, scripts/plan_review.py, scripts/plan_board.py, scripts/validate_review.py, scripts/catalog.py, scripts/tests/test_requirement_source.py, scripts/tests/test_requirement_clauses.py, scripts/tests/ledger_v3.py, scripts/tests/test_catalog.py, scripts/tests/test_plan_review.py, scripts/tests/test_review_v2.py, scripts/tests/fixtures/execution-audit/synthetic.json, SKILL.md, references/plan-and-results.md, references/requirement-clarifications.md, references/automation.md, references/check-catalog.md, docs/2026-10-22-fixed-requirements-and-review-points.md, evals/mutation/mutations.json, evals/mutation/RESULTS.md, evals/mutation/README.md, docs/improvement-ledger.md

## A decoupling group asks a fixed set of checks and takes its return pins from the pin map (2026-10-22)

After the assembly keys the R5 pair paired 424 of 461 and 466 rows; 33 of the remaining non-requirement rows were
decoupling rows of five groups both reviewers had declared on the same supply pins. One reviewer stated connection
and capacitance clauses, the other also a rating; each named its clauses its own way (`U201-VCC-CAP` against
`U201-VCC-capacitance`) and worded them its own way, and both the name (in the row id) and the wording (as the row
criterion) entered the row; on three groups one listed a single ground pin and the other every ground pin with the
exposed pad. Now (decoupling section schema 3) every declared group asks PWR-T03 and exactly one PWR-D02, PWR-C09 and
PWR-C10 row with the catalog's question; the agent states at most one datasheet clause per kind, only `kind`,
`criterion` and `citation`, and the clause rides on its row as `clause` (outside the check identity, compared as a
generated field); a missing connection or capacitance clause keeps its row waiting for the datasheet, a missing rating
clause falls back to the catalog criterion and its proposal as before; the no-capacitor rows keep a fixed criterion
and carry the connection clause. The return pins are no longer written: they are every pin the official pin map gives
the return role, and only where those pins sit on more than one net does the group name `return_net`, which is
refused otherwise. Schema-2 sections, requirement ids and declared return pins are refused, also in reviewed
declaration snapshots. R5 bench, with both intents' decoupling sections rewritten in the new form (each keeping its own
clauses, without the clause ids and the hand-listed return pins): decoupling rows pair 20 of 20 and 24, all rows 442
of 461 and 466 (94.8 %; 98.9 % without requirement rows), row counts unchanged; what remains is 38 requirement rows,
the HV group only one reviewer declared (4 rows) and one debug test point. Tests first (test_decoupling_fixed_kinds,
9 tests; the shared decoupling fixture and four older fixtures move to schema 3), 1853 tests pass, contract 500,
replay bench 195/195, mutations M123–M130 added and killed.

- Event: review:SR-20261021-R5-claude-fd6a6dd/record/intent.json (decoupling groups), review:SR-20261021-R5-codex-fd6a6dd/record/intent.json (decoupling groups), user:2026-10-22 (去耦行：要求种类固定，返回脚由网表与官方脚表推出，Agent 只写判据与出处)
- Causes: rule_not_enforced 1
- Changed: scripts/decoupling.py, scripts/checkers/decoupling.py, scripts/reviewed_declarations.py, scripts/tests/test_decoupling_fixed_kinds.py, scripts/tests/test_decoupling.py, scripts/tests/test_asg_review_scope.py, scripts/tests/test_plan_handoff.py, scripts/tests/test_reviewed_declarations.py, references/automation.md, references/plan-and-results.md, references/reviewed-declarations.md, docs/2026-10-21-function-tree-design.md, evals/mutation/mutations.json, evals/mutation/RESULTS.md, evals/mutation/README.md, docs/improvement-ledger.md

## Check keys name an assembly by its content, not by the reviewer's name for it (2026-10-22)

After step 6 the R5 pair still paired 391 of 461 and 466 rows (83.9 %, acceptance 3 asks 90 %). Apart from the 38
requirement rows each intent states for itself, the largest group was 28 checker rows with the same id on both
sides whose objects differed only in the assembly state, which the two intents named "R5-BOM" and "R5" for one
assembly (125 parts fitted, no jumpers), and in the checker inventory digest computed from it; the assembly check,
the supervision coverage row (`rails-<state>`), the I2C region and three decoupling groups (hashed handles) followed.
`check_key.assembly_map` now gives each intent.assemblies name a key from its population and jumpers, the planner
writes it as the plan's `assemblies`, and the check key names a checker row's state, states and an assembly check's
assembly by that key (a circuit row's state is a working state and is left alone); a checker's inventory digest and
its handle into the inventory (`check_key.INVENTORY_FIELDS`) stay out of the identity, the parts, nets, nodes, state,
rule and criterion saying what is asked. The validator refuses a plan without `assemblies` and keys with it, and
`compare_reviews.py` keys each side with its own map. R5 bench: all rows pair 424 of 461 and 466 (91.0 %; 94.9 %
without requirement rows), circuit rows stay 157 of 157 and 158, and neither plan has a repeated key; what remains
is what the reviewers declared differently: 38 requirement rows, 33 decoupling requirement rows (own criteria and
requirement kinds, one extra group, different return pins on three groups) and one debug test point only one
declared. Tests first (test_assembly_identity, 8 tests), 1844 tests pass, contract 500, replay bench 195/195, mutations M116–M122 added and
killed and the earlier mutations on the touched files rerun.

- Event: review:SR-20261021-R5-claude-fd6a6dd/record/intent.json (assembly "R5-BOM"), review:SR-20261021-R5-codex-fd6a6dd/record/intent.json (assembly "R5"), user:2026-10-22 (剩下的配对缺口：装配状态名和清单摘要)
- Causes: rule_not_enforced 1
- Changed: scripts/check_key.py, scripts/plan_review.py, scripts/validate_review.py, scripts/compare_reviews.py, scripts/tests/test_assembly_identity.py, scripts/tests/test_validate_review.py, scripts/tests/fixtures/execution-audit/synthetic.json, references/plan-and-results.md, docs/2026-10-21-function-tree-design.md, evals/mutation/mutations.json, evals/mutation/RESULTS.md, evals/mutation/README.md, docs/improvement-ledger.md

## Function tree, step 7: the planner is laid out along the tree and old records are refused (2026-10-22)

Step 7 of the function-tree design splits `plan_review.py` (1506 lines) by tree level and ends the reading of
records made before the tree. `plan_review.py` (729 lines) keeps the flow: adding rows, merging the previous plan,
attaching scan findings and assembling the plan; `ReviewPlanner` mixes in `plan_circuits.CircuitPlanning` (circuit
types, circuit rows and frames, part and pin evidence, threshold windows, owned-part rows), `interfaces.
InterfacePlanning` (interface rows and frames), `plan_system.SystemPlanning` (system rows and frames) and
`plan_board.BoardPlanning` (board, document, requirement and coverage rows, device identity, rule ledger); the moved
constants and helpers live with their level and the names other modules import are re-exported. The plan schema
moves to 6 (rows carry owner and check_key, the plan carries the owner table and interfaces): a schema-5 plan is
refused by the validator, by `--merge-plan` and by `--old-plan`, and a plan without `owners` or `interfaces` is
refused instead of being read as one with nothing to check. The interface coverage audit no longer crashes on a
malformed row object. R5 bench: the code before and after the split builds identical plans from both intents but
for `schema_version` and the engine digest, so the pairing stays at 157 of 157 and 158 circuit rows and 391 of 461
and 466 rows; both R5 records are refused by the new validator (schema 5, no owner table, no interfaces). Fifteen
earlier mutations were retargeted to the module their code moved to and the whole gate was run again; M81 (a circuit row of a system rule) had survived since step 5 took RST-T03 out of the STARTUP type and is now killed by a direct test of `row_owner.owner`. Tests first
(test_tree_modules, 6 tests, and one owner test; the validator and execution-audit fixtures carry schema 6), 1836 tests pass, contract
500, replay bench 195/195, mutations M111–M115 added and killed, full mutation gate 115 of 115 killed.

- Event: user:2026-10-21 (迁移分 7 步逐步来做，每做完一步形成一份提交；第 7 步：拆分计划生成、旧记录拒绝), review:SR-20261021-R5-claude-fd6a6dd/record/review-plan.json (refused as schema 5), review:SR-20261021-R5-codex-fd6a6dd/record/review-plan.json (refused as schema 5)
- Causes: rule_not_enforced 1
- Changed: scripts/plan_review.py, scripts/plan_circuits.py, scripts/plan_system.py, scripts/plan_board.py, scripts/interfaces.py, scripts/row_owner.py, scripts/electrical_contract.py, scripts/tests/test_tree_modules.py, scripts/tests/test_row_owner.py, scripts/tests/test_catalog.py, scripts/tests/test_plan_review.py, scripts/tests/test_validate_review.py, scripts/tests/fixtures/execution-audit/synthetic.json, SKILL.md, references/plan-and-results.md, references/automation.md, docs/2026-10-21-function-tree-design.md, evals/mutation/mutations.json, evals/mutation/RESULTS.md, evals/mutation/README.md, docs/improvement-ledger.md

## Function tree, step 6: coverage over the tree and a report in tree order (2026-10-22)

Step 6 of the function-tree design turns ownership and interfaces into two machine-countable audits and lays the
report out along the tree. Before it, a fitted part that no circuit owned and that the candidate file did not list
could leave the plan unasked, and an interface could lose its rows or frame without the validator noticing.
`row_owner.coverage_errors` now refuses, when the circuits come from candidates, a fitted part owned by two circuits
or owned by none and missing from the REQ-Q08 list; the planner puts every fitted part no circuit owns on that list,
not only the candidate file's `unassigned`. `interfaces.coverage_errors` refuses an interface without the rows its
kind asks (catalog.INTERFACE_SUBJECTS, SIG-C08 on each cross-supply net, PWR-C14 on a rail a noise-sensitive
circuit draws from) or, unless it is a rail or a chain without nets, without its frame. `validate_review.py` runs
both. The report's function table, when the plan has tree frames, runs system functions, circuits, interfaces and
then the functions the reviewer added; every finding gains a line naming the owners of its checks. SKILL §2 and the
plan, automation references describe the tree in one place. R5 bench: both plans have 0 ownership and 0 interface
errors and 8 parts on the REQ-Q08 list (acceptance 1); circuit rows pair 157 of 157 and 158 (99.4 %, acceptance 3
first half); all rows pair 391 of 461 and 466 (83.9 %), short of the 90 % target: 38 unpaired rows are requirement
rows each intent states for itself, and 31 more pairs match once the assembly-state names and inventory digests in
the objects are set aside; those differences lie outside the tree and are left for a follow-up. Tests first
(test_tree_coverage, 10 tests), 1829 tests pass, contract 500, replay bench 195/195, mutations M104–M110 added and
killed.

- Event: user:2026-10-21 (迁移分 7 步逐步来做，每做完一步形成一份提交；第 6 步：全板与覆盖), review:SR-20261021-R5-claude-fd6a6dd/record/review-plan.json (ownership and interface coverage), review:SR-20261021-R5-codex-fd6a6dd/record/review-plan.json (ownership and interface coverage)
- Causes: rule_not_enforced 2
- Changed: scripts/row_owner.py, scripts/interfaces.py, scripts/plan_review.py, scripts/validate_review.py, scripts/render_report.py, scripts/tests/test_tree_coverage.py, SKILL.md, references/plan-and-results.md, references/automation.md, docs/2026-10-21-function-tree-design.md, evals/mutation/mutations.json, evals/mutation/RESULTS.md, evals/mutation/README.md, docs/improvement-ledger.md

## Function tree, step 5: system functions exist when their object does, and parts are asked by owning circuit (2026-10-22)

Step 5 of the function-tree design gives the board's system functions their own rows and frames and stops asking
part stress, capacitance and precision once for the whole board. Before it, PWR-T06, SIG-D13 and DEV-C01/C02/C03 were
one board row each on every board, whatever it held, and RST-T03 was asked per STARTUP circuit and state although
power-on order is the board's. Now (§7 decision: no object, no function) `plan_review.plan_system` asks PWR-T06 only
with two or more ground nets (SYS-GROUND), RST-T03 once for the board with two or more rails (SYS-SEQUENCE, its
object listing them; dropped from the STARTUP circuit type) and SIG-D13 only while some IC could be a controller
(verified as mcu or generic ic, or not verified; SYS-PINMAP); `plan_system_frames` builds one frame per system
function with rows, its objects the nets and parts its rows name or, where they name none (per-domain monitoring),
the board's rails. `plan_owned_parts` asks DEV-C01 (all owned parts but connectors and test points), DEV-C02
(capacitors) and DEV-C03 (resistors) once per circuit over the parts it owns, with `circuit_key` so a changed member
list asks the same check, and once for the board over the parts no circuit owns. The rule contracts for PWR-T06 and
RST-T03 now hold a trigger and a near-miss board. The shared test bridge (ledger_v3) binds a passed frame row to its
frame with a judgement citing a clause, as a reviewer would, before it decides which stray failed rows get a function.
R5 bench: 461 rows, +9.8 % over step 3's 420 (acceptance 4: at most 15 %); 4 system frames; system rows pair 20 of
21, the miss being the monitoring row whose object carries the assembly-state name each reviewer chose; all rows pair
391 of 461 and 466. The replay bench moves to `system-functions-v1`, every case's count change checked by rebuilding
its plan as the sum of the PWR-T06, SIG-D13, RST-T03 and owned-part row changes (195/195). Tests first
(test_system_functions, 7 tests; catalog, plan-review, electrical-safety and v2 tests now select circuit rows by
circuit type), 1819 tests pass, mutations M98–M103 added and killed.

- Event: user:2026-10-21 (迁移分 7 步逐步来做，每做完一步形成一份提交；第 5 步：系统级), review:SR-20261021-R5-claude-fd6a6dd/record/review-plan.json (system and board rows), review:SR-20261021-R5-codex-fd6a6dd/record/review-plan.json (system and board rows)
- Causes: rule_missing 1, rule_not_enforced 1
- Changed: scripts/catalog.py, scripts/plan_review.py, scripts/tests/test_system_functions.py, scripts/tests/ledger_v3.py, scripts/tests/test_catalog.py, scripts/tests/test_plan_review.py, scripts/tests/test_electrical_safety.py, scripts/tests/test_review_v2.py, references/check-catalog.md, evals/rule_contracts/boards/PWR-T06.json, evals/rule_contracts/boards/RST-T03.json, evals/kicad_replay_bench/run.py, evals/kicad_replay_bench/README.md, evals/kicad_replay_bench/revisions/system-functions-v1/, evals/mutation/mutations.json, evals/mutation/README.md, evals/mutation/RESULTS.md, SKILL.md, references/plan-and-results.md, references/automation.md, docs/2026-10-21-function-tree-design.md, docs/improvement-ledger.md

## Function tree, step 4: interface rules are asked once per interface (2026-10-22)

Step 4 of the function-tree design expands the interface rules over the plan's interfaces instead of leaving them
to hand-written rows: the R5 plan rebuilt from one candidate set after step 3 had 1 SIG-T04 row and 2 PWR-C14
rows, all tied to circuits, and no SIG-C07 or SIG-C08 row. `catalog` gains
INTERFACE_SUBJECTS (a circuit pair: SIG-T04 and SIG-C07; a chain: SIG-C07; a connector: DEV-D03, DEV-C04, PRO-D03;
a rail: PWR-C14), INTERFACE_NET_SUBJECTS (SIG-C08 on an interface net whose IC endpoints draw from different rails or
sit on different references, `cross_supply` in interfaces.py), INTERFACE_RULES (design appendix A) and question
templates; DEV-C04, DEV-D03, PRO-D03 and PWR-C14 move to source and scope `interface`. `plan_review.plan_interfaces`
writes the rows with object `interface` (gaps from the interface's role and source gaps and its ICs' datasheets) and
one frame per circuit pair, chain and connector (`interface`, `interface_kind`); a rail gets rows only. DEV-C04 is one
row per connector instead of one board row, PWR-C14 one row per rail a noise-sensitive circuit draws from instead of
one per ANALOG/CLOCK/RF circuit and state. row_owner gives interface rows to their interface and any other row of an
interface rule whose nets lie on one interface to it (a connector's interface first). Bus circuits declared by hand
still ask SIG-T04/C07/C08 inside themselves, and SIG-C09 stays with them, since nothing declares a timing requirement
on an interface yet. R5 bench: 420 → 434 rows (+3.3 %), 21 interface rows, all 21 paired between the two intents,
10 interface frames against acceptance 4's bound of 14, no cross-supply net. The replay bench moves to
`interface-rows-v1`: every case's count changes by its connectors minus one (one DEV-C04 per connector, the board row
gone), each connector a 3-member frame, other answers unchanged (195/195). Tests first (test_interface_rows, 7
tests; catalog, plan-review and rule-gap tests updated to the new placement), 1812 tests pass, mutations M91–M97
added and killed, M83 retargeted.

- Event: user:2026-10-21 (迁移分 7 步逐步来做，每做完一步形成一份提交；第 4 步：接口规则迁移), review:SR-20261021-R5-claude-fd6a6dd/record/review-plan.json (interface rows), review:SR-20261021-R5-codex-fd6a6dd/record/review-plan.json (interface rows)
- Causes: rule_missing 2
- Changed: scripts/catalog.py, scripts/plan_review.py, scripts/interfaces.py, scripts/row_owner.py, scripts/tests/test_interface_rows.py, scripts/tests/test_interfaces.py, scripts/tests/fixtures/interfaces-flyback-usb.json, scripts/tests/test_catalog.py, scripts/tests/test_plan_review.py, scripts/tests/test_circuit_decisions.py, scripts/tests/test_row_owner.py, scripts/tests/test_rule_gaps_from_reviews.py, references/check-catalog.md, evals/kicad_replay_bench/run.py, evals/kicad_replay_bench/README.md, evals/kicad_replay_bench/revisions/interface-rows-v1/, evals/mutation/mutations.json, evals/mutation/README.md, evals/mutation/RESULTS.md, SKILL.md, references/plan-and-results.md, references/automation.md, docs/2026-10-21-function-tree-design.md, docs/improvement-ledger.md

## Function tree, step 3: interfaces derived from ownership and the netlist (2026-10-21)

Step 3 of the function-tree design lists the interfaces between owners so that step 4 can expand interface rules
per interface: before it, the R5 records had 8 and 11 interface rows, all written by hand. `scripts/interfaces.py`
(new) treats a net joining pins of two owners as an interface net and joins the nets between one pair into one
interface; ground nets never are one. Kinds: CIRCUIT_PAIR `IF-<A>~<B>`, LINK `LINK-<chain>` (the chain's own parts
and every net reaching them; such a net does not also enter a circuit pair), SUPPLY `RAIL-<net>` and EXTERNAL
`EXT-<connector>` (all pins; a ground pin lists only the connector's own endpoint). Ids use the circuits' candidate
ids, so renaming keeps them. Each endpoint is `{owner, pin, role, basis, domain, supply}`, the role from the library
pin type, the part kind, the power tree or a pin name the module lists, and a pin none gives is a gap. A rail is a
net the power tree finds a source for or a declared rail that behaves as a supply, never a name alone; its source
is the power tree's when the pin is on the rail and not typed as an input (on R5 the power tree had picked a
controller's sense input as a rail's source), else the single owner of the rail's rectifiers, else a gap. The plan
carries the section as `interfaces`; no rule expands over it yet. R5 bench (one candidate set; both intents and a
third decision set renaming every circuit): identical interfaces, 19 in all (5 circuit pairs with 1–7 nets, 4
links, 8 rails, 2 connectors), 37 nets, 168 endpoints, 1 role gap, 5 of 8 rails without a source; acceptance 2
holds, and the interface count exceeds acceptance 4's bound (14) by the rails, a decision left to step 4. Tests
first (test_interfaces, 10 tests, with a reviewed golden file of the synthetic board), 1805 tests pass, mutations
M85–M90 added and killed.

- Event: user:2026-10-21 (迁移分 7 步逐步来做，每做完一步形成一份提交；第 3 步：接口识别), review:SR-20261021-R5-claude-fd6a6dd/record/review-plan.json (interface rows), review:SR-20261021-R5-codex-fd6a6dd/record/review-plan.json (interface rows)
- Causes: rule_missing 2
- Changed: scripts/interfaces.py, scripts/plan_review.py, scripts/tests/test_interfaces.py, scripts/tests/fixtures/interfaces-flyback-usb.json, evals/mutation/mutations.json, evals/mutation/README.md, evals/mutation/RESULTS.md, SKILL.md, references/plan-and-results.md, references/automation.md, docs/2026-10-21-function-tree-design.md, docs/improvement-ledger.md

## Function tree, step 2: every row has one owner and a circuit row is named by its candidates (2026-10-21)

Step 2 of the function-tree design gives every plan row an owner and stops circuit-level rows from drifting with
how a reviewer drew the circuit. On the R5 pair each reviewer's own circuits share none of the 107 and 163
circuit-level rows: the rows carried the member list, the core part and the net spellings in their identity.
`scripts/row_owner.py` (new) writes `owner` on each row when the plan is assembled: a row about a circuit belongs
to it, a row of a system rule (`catalog.SYSTEM_FUNCTIONS`: SYS-POWER, GROUND, MONITOR, SEQUENCE, PINMAP) to that
system function, a row about parts to the circuit that owns them (step 1's `owned`; several parts must share one
owner), the rest to the board. The plan lists each circuit's owned parts in `owners` and the rows per owner in
`summary.owners`; validate_review recomputes every written owner from `owners` and refuses a row whose owner
differs, a row the reviewer adds later needs none. Circuit-level row objects carry `circuit_key` (the candidate
ids, joined with `+` for a merge); with it, `check_key` leaves `ref`, `refs` and `nets` out of the identity.
Revision checks ignore `owner` as they ignore `check_key`. The report's count table gains one row splitting the
checks by owner (the tree order is step 6); circuit-expanded RST-T03 rows stay with their circuit until step 5.
R5 bench: once both intents accept one candidate set, 132 of 132 and 133 circuit-level rows pair (the extra one
is a debug port one reviewer judged applicable) and 350 of 420 and 425 rows overall; with every circuit drawn one
member short and its nets spelled with the sheet path on one side, the old identity pairs 0 and the new 132; 190
of 200 and 194 of 204 part rows go to a circuit; system 21 rows, circuits 322 and 327, board 77. Tests first
(test_row_owner, 9 tests, and a report case), 1795 tests pass, contract 500, prototypes 67, replay bench 195/195
unchanged, mutations M80–M84 added and killed.

- Event: user:2026-10-21 (迁移分 7 步逐步来做，每做完一步形成一份提交；第 2 步：行归属), review:SR-20261021-R5-claude-fd6a6dd/record/review-plan.json (circuit rows), review:SR-20261021-R5-codex-fd6a6dd/record/review-plan.json (circuit rows)
- Causes: rule_missing 1, rule_not_enforced 1
- Changed: scripts/row_owner.py, scripts/catalog.py, scripts/check_key.py, scripts/plan_review.py, scripts/validate_review.py, scripts/revision_impact.py, scripts/render_report.py, scripts/tests/test_row_owner.py, scripts/tests/test_render_and_pack.py, evals/mutation/mutations.json, evals/mutation/README.md, evals/mutation/RESULTS.md, SKILL.md, references/plan-and-results.md, references/automation.md, docs/2026-10-21-function-tree-design.md, docs/improvement-ledger.md

## Function tree, step 1: every part has one owning circuit (2026-10-21)

The function-tree design (docs/2026-10-21-function-tree-design.md) organizes the review as board, system
functions, circuits with their parts, and interfaces; interfaces can only be derived when each part belongs to
one circuit. Reviewer-drawn circuits had 9 (Claude) and 30 (Codex) parts in several circuits, and the generated
candidates still let a chain, the isolation band and a converter hold the same part. Candidate files move to
schema 2: every member carries `owned`, decided by `circuit_candidates.claim_rank` (a circuit's anchor 0, a
circuit member 1, a circuit's endpoint-type role such as the port's PD controller 2, a chain member 3, the
isolation band 4, a chain's anchor or endpoint 5); the strongest single claimant owns the part and the others
only refer to it, and a tie is owned by nobody and listed in `shared` (the old shared list built in adjudicate
is removed). `circuit_decisions.derive` recomputes ownership among the circuits the decisions keep, so a part a
rejected or duplicate candidate gave up goes to the next claimant; a new `own` decision (ref, candidate, located
citation) settles a tie and nothing else; derived circuits carry `owned` beside `refs`, validate compares it,
and a candidate file whose flags differ from the rule, that gives a part two owners, or that has no ownership
(schema 1) is refused. The old rule that a part held by two circuits needs one of them cross-cutting is dropped
(a reference is now explicit), the limit of two holders stays. R5 bench (four controller roles simulated as
verified): 12 candidates hold 117 parts, every one with exactly one owner, no ties, 8 unassigned; circuits own
105, the four chains 12. The replay bench moves to contract `circuit-owners-v1`: the rf1 frames case takes a
regenerated schema-2 candidate file (same candidates, members and paths) and its intent with `owned`; the
output connector, tied between two converters before, is owned by its own candidate and handed to PRI-FLYBACK
when that candidate is judged a duplicate; answers unchanged (195/195). Tests first (OwnershipTests in both
test files, 9 new), 1785 tests pass, mutations M73–M79 added and killed, M57 retargeted to the new shared list.

- Event: user:2026-10-21 (按设计稿实施第 1 步：器件归属唯一；七步逐步做，每做完一步提交一次), review:SR-20261021-R5-claude-fd6a6dd/record/intent.json (circuits), review:SR-20261021-R5-codex-fd6a6dd/record/intent.json (circuits)
- Causes: rule_missing 2
- Changed: scripts/circuit_candidates.py, scripts/circuit_decisions.py, scripts/tests/test_circuit_candidates.py, scripts/tests/test_circuit_decisions.py, evals/kicad_replay_bench/run.py, evals/kicad_replay_bench/README.md, evals/kicad_replay_bench/revisions/circuit-owners-v1/, evals/kicad_replay_bench/fixtures/rf1-c2000-float-flyback.circuit-owners-v1.candidates.json, evals/kicad_replay_bench/fixtures/rf1-c2000-float-flyback.circuit-owners-v1.intent.json, evals/mutation/mutations.json, evals/mutation/README.md, evals/mutation/RESULTS.md, SKILL.md, references/plan-and-results.md, references/automation.md, docs/2026-10-21-function-tree-design.md, docs/improvement-ledger.md

## Plain words for SR's coined terms (2026-10-21)

The user found "义务" (obligation) hard to read when the strict comparison
was explained, and asked that every such term in SR be replaced. Terms SR
had coined or borrowed as metaphors are now plain: 义务 is 检查项 where it
names one plan row (检查项标识 `check_key`, 同一项检查) and 要求 where it
names what a requirement asks (要求条款, 分项要求, 设计要求, 测试要求);
严格层/对齐率/作答率 are 精确配对/配对率/已答比例; 依赖边 is 影响条目;
the margin basis kinds read 保证最坏值, 确会出现的工况, 完整最坏范围 and
估算; 公开界/夹界 are 公开资料界限/夹出界限; 审查科目 is 电路检查项;
冷跑/热跑 are 网表扫描/证据扫描; 纲要 is 审查要点; 合同/契约 are 约定;
锚器件/停点/屏障 are 核心器件/截止网络/跨域器件; 参考域 is 参考地分区;
底账 is 明细. Words engineers already use (裕量, 角点, 盲区, 闭环, 口径,
开放项, 移交, 准出) are kept. `scripts/obligation.py` becomes
`scripts/check_key.py` and the row field `obligation_key` becomes
`check_key`; English API names that predate this work (the requirement
clause kind OBLIGATION, the execution audit's obligations fields) are kept.
The replacement covered SKILL.md, every reference (check-catalog.md
regenerated), the circuit-candidates design doc, the mutation and replay
bench READMEs and the Chinese text in scripts and tests; frozen bench
expectations, dated design docs, scenarios and this ledger's earlier entries
keep their words. Mechanical replacement produced a few doubled phrases
("功能电路电路检查项", "纯网表网表扫描规则"), fixed by hand; every in-document
anchor still resolves.

- Event: user:2026-10-21 (不要叫“义务”了，太难懂了。相应的SR里面如果有这种难懂的名词，都帮我改正)
- Causes: knowledge_wrong 1
- Changed: scripts/check_key.py, scripts/plan_review.py, scripts/validate_review.py, scripts/compare_reviews.py, scripts/revision_impact.py, scripts/review_functions.py, scripts/catalog.py, scripts/lint.py, scripts/render_report.py, scripts/review_quality.py, scripts/circuit_candidates.py, scripts/circuit_decisions.py, scripts/checkers/domains.py, scripts/checkers/base.py, scripts/checkers/hotmath.py, scripts/checkers/passive_stress.py, scripts/datasheet_facts.py, scripts/parse_kicad.py, scripts/solve_dividers.py, scripts/tests/test_compare_reviews.py, scripts/tests/test_validate_review.py, scripts/tests/test_review_functions.py, scripts/tests/test_catalog.py, scripts/tests/test_plan_review.py, scripts/tests/test_review_quality.py, scripts/tests/test_checkers_framework.py, scripts/tests/test_i2c_topology.py, scripts/tests/electrical_fixtures.py, scripts/tests/fixtures/execution-audit/README.md, evals/mutation/mutations.json, evals/mutation/README.md, evals/mutation/RESULTS.md, evals/kicad_replay_bench/README.md, SKILL.md, references/check-catalog.md, references/plan-and-results.md, references/automation.md, references/requirement-clarifications.md, references/verdicts-and-release.md, references/evidence-proportionality.md, references/report-and-remediation.md, references/review-charter.md, references/workflow-handoff.md, docs/2026-10-21-circuit-candidates-design.md, docs/improvement-ledger.md

## Merge plan §3–§5: dependency edges, evidence kinds and margin basis, strict check identity (2026-10-21)

The F7 cap (a DESIGN_VALUE or VENDOR_DATUM decides at most 3 aspects) and
the reason sentences around it were the wrong guard: one undecided number
can honestly enter many obligations, and a cap only pushed reviewers to
split or reword. Every `decides[]` entry is now an edge `{aspect, states?,
check_ids?, effect BLOCKS_PROOF|INFORMATION_ONLY, via, rationale}`; a gap in
a quantity names in `via` what the quantity enters (a condition of the
function, or a calculation claim and one of `calculation.inputs`) and in
`rationale` why the available bound does not decide it. More than 3 aspects
is a WIDE_GAP hint and a repeated reason a TEMPLATE_REASON hint, neither
refused; `decides_reason`, `margin_not_decisive_reason` and `loose_bound`
are retired and refused. A located citation and what it proves are now two
checks: every condition has a kind — NUMERIC_LIMIT (limit min/max with unit,
quoted, with its regime), MANDATORY_CLAUSE (a quoted normative sentence and
the precondition it applies under, no number needed, never a typical
application), NETLIST_FACT (named nets or REF.PIN pins, checked against the
netlist, a leaf name matching two nets is ambiguous), TYPICAL_REFERENCE,
ENGINEERING_ASSUMPTION — and every margin a basis: GUARANTEED_BOUND passes
when met and only fails to prove when missed, REACHABLE_CASE fails when
missed, EXACT_ENVELOPE decides both ways, ESTIMATE neither; GE lets a zero
margin pass and GT does not; a decisive basis names its NUMERIC_LIMIT, does
not rest on typical values or assumptions, and needs a conversion across
regimes. A judgement rests on a mandatory clause or a netlist fact and cites
no numeric limit; a fail rests on a proven shortfall or a violated mandatory
clause; PASS and FAIL evidence over one scope is EVIDENCE_CONFLICT; evidence
without `states` covers only stateless rows. Checks get an identity:
`scripts/check_key.py` (first written as obligation.py, renamed the same day) keys a row by rule, rule revision (catalog entry and
question template), the physical object without the circuit's display name,
and the criterion; the planner writes `check_key`, the validator
recomputes it and refuses a check asked twice. `compare_reviews.py`
now reports a strict layer first — exact keys plus `--alias` pairs that
share rule, criterion and netlist and cite a located place — with alignment
2M/(N_A+N_B), answer rate, agreement A/C and full agreement, fail-vs-pass
and P0/P1 disagreements, transitions, contract and baseline status; the old
circuit-overlap result is kept as `suggested`. On the two R5 records (both
LEGACY_CONTRACT): 423 and 487 obligations, 234 exact pairs, all answered,
193 agreeing (82.5 %, the same as Codex's own strict comparer), alignment
51.4 %, full agreement 42.4 %, 5 fail-vs-pass pairs, 5 severe
disagreements, 62 suggested pairs (the overlap layer had 296 shared rows,
222 agreeing). The work-item line "这个缺口影响哪些判断" lists the edges.
Tests first (EvidenceBasisTests, StrictIdentityTests, F4/F7/F9 cases,
duplicate obligation), 1776 tests pass, contract layer 491, prototypes 67,
replay bench 195/195; twelve mutations moved to the new code (M46 now
guards the edge's via, M47 a judgement citing a numeric limit) and
M62–M72 added, all killed.

- Event: user:2026-10-21 (Codex merge plan SR技能优化/20261021-双方合并方案 §3–§5), review:SR-20261021-R5-claude-fd6a6dd/record/review-results.json, review:SR-20261021-R5-codex-fd6a6dd/record/review-results.json
- Causes: rule_missing 3, rule_not_enforced 1
- Changed: scripts/review_functions.py, scripts/check_key.py, scripts/plan_review.py, scripts/validate_review.py, scripts/compare_reviews.py, scripts/derive_rows.py, scripts/results_model.py, scripts/render_report.py, scripts/review_workflow.py, scripts/review_quality.py, scripts/revision_impact.py, scripts/tests/test_review_functions.py, scripts/tests/test_derive_rows.py, scripts/tests/test_validate_review.py, scripts/tests/test_compare_reviews.py, scripts/tests/ledger_v3.py, scripts/tests/fixtures/golden_reports/decisive.md, evals/mutation/mutations.json, evals/mutation/README.md, evals/mutation/RESULTS.md, SKILL.md, references/plan-and-results.md, references/verdicts-and-release.md, references/evidence-proportionality.md, references/report-and-remediation.md, references/automation.md, docs/2026-10-21-circuit-candidates-design.md, docs/improvement-ledger.md

## Circuit candidates from the netlist, steps 3–7: generation, chains, decisions, bench, old records refused (2026-10-21)

The reviewer no longer draws `intent.circuits`. `scripts/circuit_candidates.py`
builds `record/circuit-candidates.json` from the netlist, the verified device
kinds and the checker inventories: a candidate is a type plus the anchor it
is built around (a role IC, a switch nobody drives, or a switch whose role
`power_switches` declares while its driver IC has no verified kind), its
members carry the path that reached them (`via`, a membership relation, not
a conduction claim) and their hop count, its states are fixed per type
(`catalog.CANDIDATE_STATES`). Walks pass two-terminal parts only and stop at
rail stops, grounds, other anchors and barrier parts; the stop set is the
domains' rail stops plus the inductive-load rail, output and return nets and
the input walk's first storage net (the step-2 finding). Rules, from the most
certain: input protection from a power connector to the first storage
capacitor, protection and startup chains from the named pins through
optocouplers to a stop or switch node (cross-cutting, built first so
converter walks are blocked from them), converters with their switches,
pulls, snubbers, inductive element and its other windings, the rectifiers
and output capacitors on them, the feedback opto (an aux rectifier goes to
the converter it feeds; an SR controller and a declared synchronous
rectifier keep no inductive part), isolation per domain pair, analog from
sense pins, USB from CC/D± pins with the PD controller and VBUS switch,
debug without a walk. Adjudication: the shorter path wins, ties are listed
in both as `shared`, anchors are never shared; parts no walk reaches are
`unassigned` and go to REQ-Q08, ICs without a verified role and inductive
parts without pin names are `gaps`. `intent.circuit_decisions` gives every
candidate exactly one decision (accept / merge / split / reject with
OUTSIDE_SCOPE, NOT_A_CIRCUIT or DUPLICATE_OF / add of unassigned parts only),
every change to membership carries a citation a reader can open;
`scripts/circuit_decisions.py --write` derives `intent.circuits` (with
`candidate_ids`, `cross_cutting`, `anchors`) and `circuit_candidates_sha256`,
a non-anchor part belongs to at most two circuits and then one is
cross-cutting; `validate_intent` with `--candidates` (lint, plan) and
`pack_review --circuit-candidates` refuse a hand-drawn list, a decision set
that differs from the circuits, or an intent with circuits and no candidate
file, so the two R5 records are refused as they stand. Measured on the R5 db
with the four controller kinds simulated as verified: 12 candidates, 0
shared, 8 unassigned, 2 pin-name gaps; coverage of the reviewers' circuits
at Jaccard ≥ 0.8 is 6 of 10 (Claude, mean 0.83) and 4 of 11 (Codex, mean
0.67), below the design's target of 9 of 10 — the rest are rule choices
(startup chains one per pin, the SR candidate without the transformer, a
port circuit the reviewer drew around the output shunt, circuits drawn by
page), not noise; two decision sets on the same candidates give plans that
share 410 of 420 rows, the 10 others being the unmerged HV startup chain.
The KiCad replay bench moves to contract `circuit-candidates-v1`: the rf1
frames case takes a frozen candidate file and four decisions (merge Q1+Q2
into PRI-FLYBACK, the Out1 walk a duplicate of it, Q3/Q4 a linear bias
stage), circuits 3→1, checks 325→313 (298 + 5 rules × 3 states). Tests
first (test_circuit_candidates, test_circuit_decisions, plan, lint, pack and
bench cases), 1760 tests pass, mutations M56–M61 killed (a Y capacitor
listed as a snubber survived M56 until barrier parts were kept out of the
inventory-sourced members). Not done: the Codex merge plan's §3–§5 (per-edge
dependency proof instead of the F7 cap, MANDATORY_CLAUSE and evidence basis
kinds, strict obligation identity with fuzzy comparison as a suggestion
layer), recorded in the design doc §6.

- Event: user:2026-10-21 (design docs/2026-10-21-circuit-candidates-design.md §4.7 steps 3–7; Codex merge plan SR技能优化/20261021-双方合并方案 §6, §8), review:SR-20261021-R5-claude-fd6a6dd/record/intent.json (circuits), review:SR-20261021-R5-codex-fd6a6dd/record/intent.json (circuits)
- Causes: rule_missing 3, rule_not_enforced 1
- Changed: scripts/circuit_candidates.py, scripts/circuit_decisions.py, scripts/catalog.py, scripts/plan_review.py, scripts/lint.py, scripts/pack_review.py, scripts/tests/test_circuit_candidates.py, scripts/tests/test_circuit_decisions.py, scripts/tests/test_plan_review.py, scripts/tests/test_render_and_pack.py, scripts/tests/conftest.py, evals/kicad_replay_bench/run.py, evals/kicad_replay_bench/README.md, evals/kicad_replay_bench/revisions/circuit-candidates-v1/, evals/kicad_replay_bench/fixtures/rf1-c2000-float-flyback.circuit-candidates-v1.intent.json, evals/kicad_replay_bench/fixtures/rf1-c2000-float-flyback.circuit-candidates-v1.candidates.json, evals/mutation/mutations.json, evals/mutation/README.md, evals/mutation/RESULTS.md, SKILL.md, references/automation.md, references/plan-and-results.md, references/inputs-and-coverage.md, docs/2026-10-21-circuit-candidates-design.md, docs/improvement-ledger.md

## Circuit candidates from the netlist, steps 1–2: IC role kinds, ground domains, barriers and rail stops (2026-10-21)

The two R5 first reviews still differed where the reviewer drew
`intent.circuits` by hand (10 circuits against 11, members of the same
converter apart by 5–8 parts, a startup chain with two parts in common), and
nothing in the record could refuse that; the design in
`docs/2026-10-21-circuit-candidates-design.md` makes the plan generate circuit
candidates from the netlist instead. This entry lands its first two steps,
which change no record format. Step 1: an integrated circuit declares the role
its datasheet title gives it, through the existing `intent.device_kinds`
(page + verbatim quote, verified by the datasheet audit): pwm_controller,
gate_driver, sr_controller, pd_controller, regulator, supervisor,
opamp_comparator, shunt_reference, mcu, transceiver, isolator, or the generic
`ic` when the quote names no role — a generic `ic` whose quote does name one is
QUOTE_CONFLICT; a role word in the same sentence as MOSFET or rectifier names
the controller, "microprocessor supervisor" is not an MCU and "optoisolator"
is an opto; the role classifies as IC for every checker and is read with
`NetGraph.role_kind`, `is_anchor` says whether it anchors a candidate; a
fitted U/M part without a verified kind is a DEV-D02 gap like a Q/D part
(both R5 records: exactly the four controller ICs). Step 2:
`checkers/domains.py` derives, into the plan's top-level `domains`, the
ground domains (nets that reach one ground through DC-conducting parts;
capacitors, transformers, optocouplers, relays, crystals, connectors, unknown
parts and verified isolators do not conduct), the barriers (fitted parts whose
pins touch two domains), the anchors and undeclared ICs, and the rail stops
where a candidate walk ends (grounds, IC-driven nets, declared rails that two
or more anchors reach directly or through one two-terminal part, never
through a ground); a conducting part joining two differently labelled grounds
is DOMAIN_MERGED with that part named, a declared `power_rails.<net>.domain`
the netlist contradicts is DOMAIN_CONFLICT, both plan diagnostics. Measured
on both R5 records: the derived domains agree with all 13 declared ones, the
barriers are the transformer, the three optocouplers and the Y capacitor,
there are no conflicts; with the four IC roles supplied, the stops are the
grounds, the two driven secondary rails, the controller supply and bias
rails and the PD supply, while the PFC output, the rectified input and the
port rail are not stops (no anchor reaches them within a hop) — step 3 must
add the inductive-load output nets to the stop set or the PFC walk crosses
into the flyback clamp. Tests first (test_ic_kinds, test_domains, both
contract), mutations M52–M55 added, 1722 tests pass. Not done: candidate
generation, reviewer decisions and the intent validator (steps 3–7).

- Event: user:2026-10-21 (design docs/2026-10-21-circuit-candidates-design.md §4.7 steps 1–2), review:SR-20261021-R5-claude-fd6a6dd/record/intent.json (circuits), review:SR-20261021-R5-codex-fd6a6dd/record/intent.json (circuits)
- Causes: rule_missing 2
- Changed: scripts/board_intent.py, scripts/datasheet_kinds.py, scripts/checkers/netgraph.py, scripts/checkers/domains.py, scripts/checkers/passive_stress.py, scripts/plan_review.py, scripts/tests/test_ic_kinds.py, scripts/tests/test_domains.py, scripts/tests/test_plan_review.py, scripts/tests/conftest.py, evals/mutation/mutations.json, evals/mutation/README.md, evals/mutation/RESULTS.md, SKILL.md, references/automation.md, references/plan-and-results.md, docs/2026-10-21-circuit-candidates-design.md, docs/improvement-ledger.md

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

# 改进台账

Every entry ends with three lines the test suite checks
(`scripts/check_ledger.py`): `Event:` the review item, datasheet page, test
record or user correction that caused the change; `Causes:` how many items
fell in each cause class (rule_missing, rule_not_enforced, knowledge_missing,
knowledge_wrong, judgment); `Changed:` the files touched. Entries before this
file existed are in `docs/audits/`.

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

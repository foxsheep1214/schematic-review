# Execution audit v1: reproducible controlled examples

`synthetic.json` contains a complete synthetic plan/results/native DB/sidecar envelope (26.5 KB). It contains no private circuit or historical score. The Python factory `test_execution_audit.fixture()` returns independent copies; `rebind(p, r, db, a)` recomputes plan/results/DB digests after an intentional change. Tests modify real result/remediation fields as well as the sidecar. The helper `without_execution_contract` removes the contract to exercise backward-compatible *current* structural validation; this is not an execution of an archived old SR version. A historical before/after comparison must actually invoke that version.

Run from the skill root:

```sh
/Users/skyfend/.local/bin/python3 -B -m unittest discover -s scripts/tests -p test_execution_audit.py -v
```

To extract an actual CLI example under the required scratch location, run from the skill root. Regenerate its engine identity after changing engineering source; do not carry a stale plan fingerprint across edits.

```sh
python3 -B - <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, 'scripts/tests')
from test_execution_audit import fixture, rebind
from review_engine import engine_identity
p, r, db, a = fixture()
p['review_engine'] = engine_identity()
rebind(p, r, db, a)
out = Path('/tmp/codex-work/sr-execution-improvement-20261013/implementation/cli-positive')
out.mkdir(parents=True, exist_ok=True)
for name, data in [('plan', p), ('results', r), ('board', db), ('execution-audit', a)]:
    (out / (name + '.json')).write_text(json.dumps(data, ensure_ascii=False, indent=2))
PY
```

Use the resulting absolute paths in the commands below. This fixture's release field reflects synthetic stipulated checks only; it is not a hardware release.

Integrated command (optional self-check; `--require-execution-audit` only when explicitly requested):

```sh
python3 -B scripts/validate_review.py plan.json results.json --db board.json \
  --execution-audit execution-audit.json --require-execution-audit \
  --require-actionable --require-bindings
```

The independent consistency CLI (no claim to validate the rest of the ledger):

```sh
python3 -B scripts/execution_audit.py plan.json results.json execution-audit.json \
  --db board.json --json execution-validation.json
```

Both commands reject execution contradictions with exit 2. The integrated validator continues its existing native/engine/remediation/coverage checks. Old records are not migrated. Adding a contract or supplying a sidecar automatically enforces it in the Python API; the explicit required flag also rejects its absence.

## Small contract

The plan has `execution_inputs`, containing controlled engineering excerpts with source evidence, and `execution_contract` version 1. It does not modify the established revision `review_inputs` snapshot. Every `basis` is an exact `{root: "plan", pointer: "/execution_inputs/..."}` JSON pointer; native DB pointers use root `db`. A contract cannot reference itself as its evidence. The sidecar has version 1 plus `plan_digest`, `results_digest`, `db_digest`, using sorted compact UTF-8 JSON SHA-256 (the same representation as `validate_review.fingerprint`). There are five required arrays and one optional array on both contract and sidecar:

| Section | Contract entry | Controlled basis | Sidecar entry |
|---|---|---|---|
| networks | id, check_id, basis | net, drivers, receivers, model, model_support, criterion_kind, cases | same id; calculations for every receiver × case |
| power | id, check_id, basis; optional finding_id | model, model_support, criterion_kind, rating_basis, power_rating, cases | same id; calculations for every case |
| aggregates | id, check_id, basis | kind, members, not_applicable; COVERAGE also review_incomplete; applicability + evidence for absent/undetermined packages | same id; member_results keyed by all required members |
| repairs | id, target_kind, target_id, basis | obligations, unresolved_obligations, physical_dependencies; optional design_decision_obligations | same id; dependencies indexed by actual array location |
| gaps | id, check_id, basis | required_inputs, available_inputs | same id; missing_inputs IDs equal the actual results row |
| handoffs | id, check_id, basis | actual object, receivers, constraint, verification; optional quantity | same id; object and receivers; quantity only when controlled scope declares it |

`numeric_scope` points to a controlled `{networks: [id...], power: [id...]}` inventory. Empty contract arrays cannot erase its known numerical obligations. All actual Q07 checks, actionable finding and work-item remedies, INSUFFICIENT rows, and required handoffs must also be reconciled. This does not automatically discover every unstated physical requirement: independently audit the controlled inventory before freezing the plan.

## Bounded numerical models

Only `criterion_kind: "GUARANTEE_REQUIRED"` is supported. These are checks of an explicit required guarantee, not general detection of a manufactured hardware failure from a conservative envelope.

Each numerical interval contains `min`, `max`, `unit`, and the existing calculation-source fields `basis`, `evidence`, `conditions`, `operating_conditions`. Empty guarantee conditions require `unconditional_basis`; a derived bound requires `derivation`. The shared `design_preflight.validate_calculations` condition rules are used unchanged. TYPICAL/ASSUMED/out-of-condition inputs produce INSUFFICIENT, never confirmed FAIL/PASS. Values must be finite, units match exactly, and positive R/C/rating intervals are required.

* `SINGLE_POLE_CHARGE`: each case has voltage V, initial V, resistance ohm, capacitance F, required_delay_s. Each receiver has a threshold V interval and threshold basis. The earliest crossing is recomputed at maximum source/initial voltage and minimum threshold/R/C. Every native input/bidirectional endpoint except identified drivers must appear; raw IN/OUT/BI and KiCad native roles are supported. `model_support` requires exact endpoint_roles, evidence, qualification SUPPORTED/UNRESOLVED, and excluded_branches. A SUPPORTED record needs DRIVER/HIGH_IMPEDANCE_RECEIVER/PASSIVE_RC roles on all actual endpoints and no unknown excluded branch. Unknown active/clamp/parallel paths make the simplified calculation INSUFFICIENT. An expert must establish the high impedance and physical model evidence; these words alone do not prove it.
* `RESISTOR_DC_POWER`: each actual case has resistor differential voltage V and resistance ohm; the controlled basis includes guaranteed power_rating W and rating_basis. Maximum squared absolute voltage divided by minimum resistance is recomputed. Supply voltage alone is not necessarily resistor differential voltage; the source derivation must establish that physical relation, including external supply and off-state paths. Supported model evidence must include continuous versus pulse and thermal/rating conditions where applicable.

Each sidecar calculation has case_id, value, unit, claim PASS/FAIL/INSUFFICIENT; network cells also have receiver. Missing cells, reusing another operating state's number, wrong corners, or wrong claims are errors. The narrowly bound actual check must equal the recomputed guarantee verdict. An optional linked finding cannot be READY while its numerical guarantee remains FAIL/INSUFFICIENT.

## Semantic boundaries

* REQ-Q07 is always COVERAGE. Complete member review can PASS despite electrical FAIL/INSUFFICIENT. `review_incomplete` makes coverage INSUFFICIENT. A distinct real functional/requirement check can be ELECTRICAL: FAIL takes priority over INSUFFICIENT, and PASS requires all applicable required members to pass. NA needs the controlled member applicability list.
* Repair targets include both `findings[].remediation` and `work_items[].design_option.remediation`. Each prerequisite, parameter, step and verification row has a dependency at `prerequisites/0`, `parameters/0`, `steps/0`, etc. A dependency binds a source record `{obligation, check_id}`, and must belong to the original task or a controlled real physical dependency. Free prose saying “physical_relation” is not accepted as a substitute. Pure naming/connection corrections do not acquire supplier/electrical/system obligations. Real electrical dependencies remain allowed. Readiness is derived from controlled unresolved obligations and design decisions. This reconciliation does not understand arbitrary contradictory free prose; semantic review of the actual instruction remains mandatory.
* An INSUFFICIENT row lists controlled missing input IDs, with prose explanation in rationale. Those IDs must exactly equal its own required-minus-available inputs. Missing U7 function names cannot be transferred into a local connectivity claim whose actual required inputs are independently available. Real Ceff, rating and threshold data gaps remain unresolved. Source-bound causal requirement assignment still needs expert review.
* Handoff templates bind actual objects and receivers; constraint and verification must match the controlled scope. A quantitative field is enforced only when that scope actually includes it. A nonnumeric wiring handoff does not acquire an artificial quantity requirement.

The output deliberately includes `scope: SOURCE_BOUND_EXECUTION_CONSISTENCY_ONLY` and `electrical_approval: false`. Source-bound agreement can catch execution contradictions. It cannot certify that the source basis is complete, that arbitrary prose matches it, that the physical model is valid, or that hardware is safe to energize.

Absent packages use source-qualified `applicability: NOT_APPLICABLE`, empty members/member_results, and retain NA. Undetermined package applicability stays INSUFFICIENT with a real feature-scope gap. Both match plan applicability and require source evidence; they cannot be used to waive an already applicable member.

## Honest missing information

A numerical parameter may be `null` only with a real source-bound gap on its own check and an INSUFFICIENT result. Its uncomputed cell uses `claim: INSUFFICIENT`, `value: null` and the output unit. Malformed/nonfinite data is still rejected. A missing receiver threshold or rating can use `basis`/`rating_basis: UNAVAILABLE`; this is allowed only when its bound is actually null and the own gap is present. Known V/R power remains reproducible even if the rating is unavailable. An unresolved model may omit a fictional curve value. The gap assignment and original missing evidence still require expert verification.

A pure passive RC net uses `drivers: []`, complete native receiver/endpoint roles and its upstream source path through a declared passive branch. The checker reconciles native adjacency; the expert must prove that this is the actual resistor/capacitor model and the case voltage. External sources, when needed, use real native `model_support.external_source_nodes`. An input pin cannot be disguised as a driver to drop it from the receiver inventory.

A null cell is accepted only when the formula is actually uncomputable or its physical model is unresolved. Known applicable V/R arithmetic remains required despite a missing rating.

For a multi-hop passive source, declare `model_support.source_branches: [["R1.1", "R1.2"], ["R2.1", "R2.2"]]` from the controlled physical model. Each edge names two real passive nodes on one component; the graph traverses the actual nets and checks reciprocal `pin2net`/`nets` membership at every declared/visited net. The existing directly evidenced single-branch case may omit this array. Arbitrary connectors/passive parts are not automatically shorted to discover further upstream sources. Native adjacency does not prove that an edge is actually a resistor or the effective model is applicable; the source proof and qualification remain mandatory expert work.

## Usage boundaries (moved from references/execution-consistency.md §5)

执行审计是可选自检，不是交付门槛；`--require-execution-audit` 仅在使用者明确要求时加。

- 使用时在两次扫描的计划范围确定后、专家结果录入前，固定 `plan.execution_inputs` 受控摘录和
  `plan.execution_contract`（v1）；它们独立于 revision `review_inputs`，不改原生连接。
  新声明的工况/物理模型、输入依赖及作用域须引用原始材料，不能从草稿结论生成“已证明”标志。
- 结果保存后生成单独 `execution-audit.json`，绑定最终 plan/results/db 的规范 JSON 摘要。
  有新工况、真实依赖或资料变化时更新受控范围并重跑；原始报告不迁移、不重标成绩。
- 无适用数值项可在受控库存中明确为空，不能用空清单删掉已识别的检查项。已确认不存在的功能电路保留有来源的 NA；
  功能范围未定的包保留 INS，不为填约定创造成员或改成 PASS。
- 数值工具仅复算有明确保证要求且已核模型的单极充电和电阻连续功耗；未知支路/越保证条件的输入
  不得借简化模型得 PASS/FAIL。其他拓扑仍须独立工程计算，库存写明其方法/边界。
- 实际参数不可得时用 `null`，并在本行 required-minus-available 输入中保留缺口；结果为 INS，未知计算单元
  `value: null`，不制造典型值或假曲线。V/R 已知、额定未知时保留功耗计算，仅额定判断为 INS。
- 单极 RC 网可以没有网内驱动脚：用被动支路到上游源的原生路径与模型证明，不把电阻或接收脚冒充驱动。
- 多跳被动供源在 `model_support.source_branches` 列出每条导电支路的两物理脚；图追踪逐网核
  `pin2net`/`nets` 互反。电阻/二极管/连接器的物理性质和等效模型仍由来源证明，不能把被动脚当内部短路。
- 一致性通过只证明声明间可对账，不证明全部适用的要求已发现、原始资料完整或模型正确。

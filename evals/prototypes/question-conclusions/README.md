# 问题 + 结论原型（设计第 1 步）

设计见 [docs/2026-10-20-question-conclusion-design.md](../../../docs/2026-10-20-question-conclusion-design.md)。
这里的脚本独立运行，不改主路径（`scripts/` 只被导入，不被修改）。

```sh
python3 plan_to_questions.py review-plan.json -o questions.json [--strict]
python3 conclusions_check.py questions.json clauses.json conclusions.json --db db.json [--evidence-root DIR] [-o out.json]
python3 -m pytest -q tests
```

## plan_to_questions.py

- 一个问题 = （对象，关注点）。功能电路的行按规则合成一题，状态并进 `conditions.states`；
  同一规则下器件与网络完全相同的几个电路合成一题（`subject.circuits`）；
  同一去耦组的 PWR-C09/C10/D02/T03 合成一题（`DECOUPLING`），同一器件的 DEV-D02/D05 合成一题（`PINS`）。
- 计划里 NA 的行不出题；其余每行恰好被一个问题的 `check_ids` 引用。UNDETERMINED 的行出题并标 `undetermined`。
- 工具观察：行的 `inventory_gaps` 与 I2C 区域缺口记为 `MISSING_INPUT`，审查者可补的输入标 `input: true`
  （判别沿用 `validate_review.input_gap`）；lint 行的 `lint_detail` 记为 `SUSPECT`。
- `--strict`：还有审查者可补的输入时退出 1（设计要求这些在出题前补齐）。

## conclusions_check.py

四类检查，错误带 `check`（COVERAGE / CONSISTENCY / TRACE / STRICTNESS）和 `code`：

| 检查 | code |
|---|---|
| 覆盖 | UNANSWERED、DUPLICATE_CONCLUSION、UNKNOWN_STATE、UNKNOWN_QUESTION、SUSPECT_UNANSWERED、MISSING_INPUT_UNDER_PASS、UNKNOWN_OBSERVATION |
| 一致 | PASS_NOT_PROVEN、ALREADY_DECIDED、FAIL_WITHOUT_FIX、FIX_SAME_AS_UNKNOWN、LOOSE_INPUT_UNKNOWN、NO_BOUND_NOT_SEARCHED、MISSING_INCOMPLETE、UNSPECIFIED_NOT_FAIL、NA_NOT_OPEN、SEVERITY_MISSING … |
| 可查 | UNKNOWN_CLAUSE、CLAUSE_INCOMPLETE、CLAUSE_SOURCE_MISSING、DB_VALUE_MISMATCH、DB_VALUE_UNREADABLE、RECOMPUTE_MISMATCH、RECOMPUTE_FAILED、UNIT_UNKNOWN、DIMENSION_MISMATCH、NON_MONOTONIC、FACT_FALSE、UNKNOWN_NODE … |
| 不过严 | FAIL_NOT_PROVEN、FAIL_ON_ASSUMED_LIMIT、FAIL_ON_ASSUMED_POINT、DUPLICATE_DEFECT、SEVERITY_ABOVE_CLASS、REQUIREMENT_GRADED、UNDECIDED_ON_PROCUREMENT、RECOMMENDED_NOT_VENDOR、ALREADY_RECOMMENDED、DUPLICATE_GAP |
| 判不了要有理由 | NO_FAILURE_PATH、BOUND_NOT_USED、MISSING_SAME_AS_UNKNOWN、RECOMMENDED_WITH_DEVIATION（一致）；ENGINEERING_TOO_NARROW、ENGINEERING_NOT_DATASHEET、QUANTITY_UNKNOWN、CONSTRAINT_INCOMPLETE（可查） |

- 数值结论：`basis = {kind: NUMERIC, criterion: {limit: 数 或 {min, max}, unit, direction, clause}, calc, inputs, result: {min, max}}`。
  每个输入写 `value` 或 `{min, max}`。机器在所有角点重算，得到结果范围，并推出结论：
  - 最不利角点余量 > 0 → 通过；
  - 最有利角点余量 ≤ 0 → 不通过；
  - 其余 → 判不了。

  写下的结论与推出的不一致即报错：写通过但推不出 → PASS_NOT_PROVEN；写不通过但推不出 → FAIL_NOT_PROVEN（过严）；
  写判不了但已能定 → ALREADY_DECIDED。输出的 `derived` 列出每条数值结论的范围和两端余量。
- 单位：输入按单位换算到国际单位计算，结果换回判据的单位再与 `result` 比，所以前缀写错（mA 写成 A）会表现为复算不符。
  受限算式还要过量纲检查：量纲按 (V, A, s) 的幂次推算，加减和 min/max 两边量纲必须相同，幂指数必须是数字，
  结果量纲要等于判据单位的量纲，否则报 DIMENSION_MISMATCH。字面量 0 可以配任何量纲（例如 `max(0, v)`）。
  不认识的单位报 UNIT_UNKNOWN。`calc.py` 函数按国际单位传参复算，但不做量纲检查。
- 单调：角点法要求算式对每个输入单调。机器对每个有范围的输入，在其余输入取各角点时，再取范围内 1/4、1/2、3/4 三个点计算；
  结果落到角点范围之外就报 NON_MONOTONIC，要求在转折点处把范围拆开。这是抽样，三个点之间的转折仍可能漏掉。
- 条款带 `kind`：DATASHEET / STANDARD / REQUIREMENT / PRACTICE / ASSUMPTION。不通过的限值不能来自 ASSUMPTION；
  来自 ASSUMPTION 的输入要写成范围，不能是一个点。
- 一个改法只算一个缺陷：第二条不通过写 `fix: {same_as: 问题 id}`。`summary.defects` 是缺陷数。
- 严重程度带 `class`，等级不能高于后果类的上限（沿用 `review_summary.IMPACT_CLASSES`）。
- `missing.from = REQUIREMENT` 的判不了不评级，也不阻塞定稿。
- 算式：`calc.py` 的函数名（加 `output` 取结果字段），或受限算式（四则、`**`、`min`/`max`/`abs`/`sqrt`，
  变量只能是输入名）；复算相对误差 1%。
- 网表输入：`{"db": {"ref": "R3", "parse": "resistance|capacitance|number"}}`，按单位换算到国际单位后与网表比，
  读不出的值报 DB_VALUE_UNREADABLE（改为引用条款），不猜。
- 按状态拆：结论可带 `states`，各状态结论不同时把一题拆成几条结论，合起来每个状态恰好一次；结论相同仍写一条结论。
- 定稿：有 P0/P1 的不通过，或 P0 的判不了 → `CANNOT_FREEZE`。

判不了这一侧（过严更常见的样子是大量没必要的判不了）：

- 工程界：输入可写 `{typical: v}` 或 `{at_25c: v 或 {min, max}}`（来源条款须为手册），机器按下限放宽：
  典型值两向乘除 3，25 °C 值两端各放宽 20%；`widen` 只能更宽。`searched` 里记了数值却不用，报 BOUND_NOT_USED。
  标了 `quantity` 的输入按该类的下限放宽：门电荷、正向压降、电源电流 ×2，阈值电压、电容、导通电阻、反向恢复电荷 ×2.5，
  漏电流典型值 ×1000、25 °C 值放到 ×64（下端不低于 0）；依据见 `2026-10-21/floors`（`scan.py` 与 `ratios.json`）。
- 每条判不了写 `failure_path {mechanism, state}`（需求未定的除外）。
- 料号未定不是判不了：写通过，依据 `CONSTRAINT {refs, requires}`，汇总在 `summary.constraints`。
- 推荐配置无偏离：写通过，依据 `RECOMMENDED {clause, facts, deviations: []}`。
- 同一缺口只计一次：`missing {same_as}`，`summary.gaps` 是缺口数；same_as 的结论仍写自己的失效路径。

## 与设计稿的出入（第 2 步前要人定）

1. **NA**：设计只有三种结论。计划里有 UNDETERMINED 的行，原型允许这类问题的结论写 `NA`，并要求事实依据；
   其他问题写 NA 报 NA_NOT_OPEN。
2. **后果类映射**：设计 4.2 第 4 条要求严重程度与问题的后果类一致。计划行没有后果类，原型改为让结论自带 `class`，
   只拦"等级高于后果类上限"（防过严），不要求等级与上限一致。
3. **问题数量**：原型板（Olimex ESP32-PoE-ISO Rev N，283 行计划）得到 196 个问题（跨电路合并后 194），只有 39 题合并了多行，
   远多于设计估计的 60–120。器件级规则（身份、推荐工作条件、封装）、需求条目和 I2C 区域仍是一行一题。
4. **缺输入**：同一计划有 394 条 MISSING_INPUT 观察、79 项审查者可补的输入（`--strict` 退出 1）。
   这份计划只为 UART 链路补过声明；对比前要么先补齐整板输入，要么第 2 步只做局部一期。

## 测试

`tests/test_plan_to_questions.py`（合成计划 + 原型板计划，原型板文件不在时跳过）、
`tests/test_conclusions_check.py`（合成板全部通过；设计 8.4 节十类注入错误各由对应检查拦下；区间推结论；四条防过严约束；规则与 CLI）。
原型阶段不进主路径的变异门禁；手工变异 8 处（复算、网表值、公开界、事实、疑点、正余量、覆盖、算式白名单）均被杀死；
跨电路合并与按状态拆结论另加 4 处（漏状态、未知状态、疑点按题、合并键），均被杀死。
区间推结论与防过严另加 12 处，11 处被杀死；剩下 1 处（定稿时跳过需求未定条目）是冗余条件：需求未定不许评级，本来就不会阻塞，已删去。
单位、量纲与单调检测另加 10 处，均被杀死。
判不了这一侧的五条规则另加 20 处，均被杀死。
一期对比结果见 [2026-10-20/summary.md](2026-10-20/summary.md)；
判不了一侧在 round-01 156 行证据不足上的实测见 [2026-10-21/round01/summary.md](2026-10-21/round01/summary.md)。

# 变异门：注入具名缺陷，单元测试必须杀死

[run.py](run.py) 把仓库复制到临时目录（不带 `.git`/`.claude`/`runs`），按 [mutations.json](mutations.json)
逐条把一段实现改坏，跑单元测试，记录 KILLED（有测试失败）/ SURVIVED（全部通过）。源仓库不改。

```sh
python3 evals/mutation/run.py                 # 全部变异 × 单元层与合同层，结果写 RESULTS.md
python3 evals/mutation/run.py --only M4       # 只跑某几条
python3 evals/mutation/run.py --tier unit     # 只跑单元层（门槛）
```

- **单元层**：`pytest scripts/tests -x`，去掉典型电路、种子基准与 KiCad 回放三块板级基准。
- **合同层**：同上加 `-m contract`（规则合同、校验器不变量、解析器），只报告，不设门槛。
- **门槛**：每条变异都必须被单元层杀死；有存活或模式没唯一命中时退出 1。

## 变异清单

M1–M8 来自 2026-10-19 的审计：板级基准（42 块典型板、种子基准、KiCad 回放）只杀死其中 2 条，
单元测试杀死 7 条，存活的是 M4（DEV-E02 只核上限、不核下限）。补了
`test_electrical_safety.py::test_operating_range_fails_when_the_rail_minimum_is_below_the_recommended_minimum`
和 DEV-E02 合同后 M4 被杀死。M9–M12 删掉建合同前从未被测试点名的四条 A 规则（NET-A03、PWR-A04、RST-A01、
REQ-A01）的报出，只有规则合同能杀死它们。
M13–M18（2026-10-20）守功能判定机制：F2（设计值不向厂家要）、F4（正余量必须下结论）、框架科目行绑定、
`derive_rows.py` 按开放项派生、问题禁止句检查、计划生成功能框架，各由 `test_review_functions.py`、
`test_derive_rows.py`、`test_catalog.py`、`test_plan_review.py` 的一条测试杀死。
M19（2026-10-20）把与工作态无关的审查科目（`catalog.STATE_INVARIANT`）重新按状态展开，由
`test_plan_review.py` 的科目行计数测试杀死（首个失败是 `ReviewPlanTests::test_level_shift_name_hit_is_candidate_until_circuit_is_declared`，
`FunctionFrameTests::test_state_invariant_rules_get_one_row_per_circuit` 同样失败）。

## 维护

- 改规则或检查器时，为新判据加一条变异：`old` 是实现里唯一出现的一段原文，`new` 是“判据失效”的改法。
  `old` 不唯一时运行器报 ERROR，不会悄悄改错位置。
- 某条变异存活 = 有一条判据没有任何测试守着；先补触发板/近似板或单元测试，再提交。
- 实现重写导致 `old` 找不到时，按新实现改写该条变异，不要删掉。

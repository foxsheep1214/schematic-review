# 原理图审查报告模板 V2.1

本页只规定展示顺序与字段映射。结果字段以 [review-results-schema.md](review-results-schema.md)
为准；分级与准出以 [severity-calibration.md](severity-calibration.md) 为准；逐项改法以
[remediation-guide.md](remediation-guide.md) 为准。报告、机器台账和引用的工程证据保存在项目审查目录。

## 1. 结论及版本

- 对象：板卡/原理图版本、装配配置、输入哈希清单、PDF/网表一致性及首审/复审基线。
- 从 `review-gate.json` 分别列台账是否有效、本轮待办（workflow）、原理图冻结状态（release）。
- 汇总唯一 finding 数、根因 work_item 数和受影响检查数；不要将台账行数称为独立缺陷数。
- 复审先展示本轮新增/修复/变化及复用范围；完整检查记录放附表。
- 列优先修改/补证项；仅 PDF、部分执行和覆盖限制在结论旁明示。准出只指原理图冻结进入 PCB Layout。

## 2. 全部发现总表与逐项明细

按 P0→P3 展示全部当前 `findings`，可选改善注明 `kind`；同一根因沿用一个 ID。

| ID | 等级/类型 | 页/位号/物理脚/网络 | 已确认偏离 | 触发条件/影响 | 建议摘要 | 复验摘要 | 状态 |
|---|---|---|---|---|---|---|---|

每个 ID 链接明细，或在正文按下表展开；摘要取 `recommendation`/`verification`，不能替代修改说明。

| 明细展示 | 数据来源 |
|---|---|
| ID、等级、标题、位置 | `findings.id/severity/title/location` |
| 结果、置信度、关闭状态、关联检查/REQ | `check_ids` 对应的 `checks` 及计划中的需求关联 |
| 观察、判据、根因、影响、工况、定级理由 | `observed/criterion/root_cause/impact/scenario/severity_reason` |
| 原始证据、推导与计算定位 | 对应 `checks.evidence/rationale` 和引用的计算、图形、文档 |
| 修改准备度、目的、前提、旧→新顺序步骤、参数表 | `remediation.readiness/purpose/prerequisites/steps/parameters` |
| 联动与验收 | `remediation.related_findings/impact_review/verification` |

## 3. 待核项

从 `work_items` 按根因展示待核任务；每个关联检查保留 INSUFFICIENT，未知后果不计为确认缺陷。
潜在 P0 与本轮设计任务前置，后接冻结前及样机阶段任务。旧报告无 work_items 时按证据人工归并展示，
保留原始检查映射，不改写历史记录。

| 任务 ID / 根因 | 缺失输入及已知事实 | 受影响检查 ID / 数量 | 关闭阶段 | 潜在影响及定级依据 | 下一步 / 关闭证据 |
|---|---|---|---|---|---|

## 4. 需求、覆盖与完整结果

| REQ ID / 来源 | 可检验要求及工况 | 实现电路 | 检查 ID | 结果 | 证据/偏离/接受记录 |
|---|---|---|---|---|---|

按 [coverage-protocol.md](coverage-protocol.md) 分维度列总数/完成/NA/不足/未执行；总数未知写 UNKNOWN。
从 `checks`、`coverage`、`scope_checks`、`lint_reviews` 及工程附表展示全量台账，可链接持久化附表：

| 检查 ID | 对象/判据 | 适用性/结果/置信度 | 证据/计算 | finding ID | HANDOFF |
|---|---|---|---|---|---|

冷/热每条候选链接最终处置与反证，按实例给 planned/executed/pending。

## 5. 计算、修改后复核与历史闭环

| 检查/位号 | 模型/路径/值 | 输入/公差/来源 | min/typ/max | 验收窗口/结果 | 修改后的窗口 |
|---|---|---|---|---|---|

| 历史 ID | 原意见/回复 | 当前证据/期望断言 | 已复验/复发/未闭环/接受/撤回 | 关联当前 ID |
|---|---|---|---|---|

表中链接实际计算、Diff 和复验记录；没有执行的复验保持待完成，错误结论保留反证和更正说明。

## 6. HANDOFF 与准出闸门

从各检查的 `handoff` 展示下游约束和接收记录：

| 来源检查 | 接收人/阶段 | 定量约束 | 验证方法 | 状态 | 接收/验证记录 |
|---|---|---|---|---|---|

附 `review-gate.json` 的路径、结果和未关闭项，说明校验只验证记录一致性。

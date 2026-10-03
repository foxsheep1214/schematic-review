# 原理图审查报告模板 V2.2

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

先按 [最小充分证据](evidence-proportionality.md) 复核每条待核项，区分真实资料缺口、设计未定、审查待完成。
复核后先给原因分布，数据取自 `insufficient_by_cause` 或人工归类；口径过严的项应已改判，不列入：

| 原因 | 条数 | 其中潜在 P0/P1 |
|---|---|---|
每项写具体缺什么、已知什么、影响哪一判断及最小关闭证据；不使用“缺完整手册/全部应力模型”套话。
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

## 6. 移交后续设计与准出闸门

从各检查的 `handoff` 明确后续 PCB、结构、固件或样机阶段的输入、约束和关闭方法。
OPEN 简洁写“待后续团队处理”；ACCEPTED 写“已接收，待验证”；VERIFIED 写“已验证”。
只有实际存在的接收/验证记录才引用，正文不重复防御性声明。
同一后续任务合并展示，保留全部来源检查：

| 来源检查 | 后续设计角色/阶段 | 所需输入/定量约束 | 关闭方法 | 状态 | 已有接收/验证记录 |
|---|---|---|---|---|---|

附 `review-gate.json` 的路径、结果和未关闭项，说明校验只验证记录一致性。

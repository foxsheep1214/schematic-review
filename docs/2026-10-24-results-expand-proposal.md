# 方案：校验和报告直接读功能判定，不再展开旧的行级形状（SR 自查 5.8 之一）

状态：草稿，等用户定。用户 2026-10-24 选“这次不动，另出方案”。

## 现状

结果格式 6 里，缺口和失败只写在功能判定上（`functions[].open[]`、`fails[]`），检查行只带 `open_ref` / `fail_ref`。
但校验、质量筛查和报告读的不是这个形状：`results_model.expand()` 先把记录复制一份，再按旧的行级格式补字段：

| 展开出的字段 | 从哪来 | 谁在读 |
|---|---|---|
| `gap_cause` | 开放项 `kind` 查 `KIND_CAUSE` | validate_review、review_summary、review_workflow、review_stage_scope、task_scope、render_report、review_quality、requirement_clarifications |
| `missing_inputs`、`input_requests` | 开放项的 `what`/`scope`/`acquisition`/`closure` 改名 | validate_review、review_stage_scope、task_scope、review_quality |
| `potential_severity`、`impact_assessment` | 开放项的 `severity` 改名 | validate_review、review_summary、review_workflow、review_stage_scope、task_scope、render_report、review_quality |
| `blocking`、`evidence_confidence`、`disposition` | 按结论给默认值 | validate_review、review_workflow、review_quality、revision_impact 等 |
| `work_items` | `derived_work_items()` 从开放项派生 | render_report、review_quality、review_workflow |

`expand()` 有三个调用者：validate_review.py:232、render_report.py:664、review_quality.py:85。

后果（第三组、第四组几条的根源）：

- 同一个量有两个名字：开放项写 `severity.class`，下游读 `impact_assessment.consequence_class`；写 `closure`，下游读
  `closure_criterion`。改一处的口径要记得改另一处的映射（第三组 3.x“summary 计数口径与门禁不同”就出在这里）。
- 文档要同时解释两套字段（第四组 4.x 里 `gap_cause`、CONDITIONAL 的说明）。
- 默认值在展开时悄悄补上（`blocking` 默认真、`evidence_confidence` 默认 B/C），记录里看不到，校验错误却按补上的值报。

## 建议

分三步，每步一个提交，行为不变：

1. **一个读口。** 在 results_model 里给每个下游要的量一个函数（`gap_cause(row, items)`、`severity_of(row, items)`、
   `requests_of(row, items)`……），直接从 `open_ref` 指向的开放项取；`expand()` 改成调这些函数，输出不变。测试锁住
   新旧两种读法在全部回放和典型电路上一致。
2. **下游逐个改读函数。** 按读者多少排：review_summary、review_workflow、task_scope、review_stage_scope、render_report、
   review_quality、validate_review。每改完一个模块，删掉它对展开字段的依赖；回放、典型电路、门禁计数逐个对照不变。
3. **删 `expand()`。** 最后一个读者改完后删除展开和 `REQUEST_CAUSES` 等只为展开存在的映射；默认值（`blocking`、
   `evidence_confidence`、`disposition`）改为读口函数里的显式规则，文档只描述功能判定一套字段。

不做的：不改结果格式（仍是 6），不改审查员写的任何字段，不改门禁结论。

## 动哪些文件

- 代码：`scripts/results_model.py`（读口函数；最后删 `expand`、`derived_work_items` 的旧形状部分）、
  `validate_review.py`、`render_report.py`、`review_quality.py`、`review_summary.py`、`review_workflow.py`、
  `task_scope.py`、`review_stage_scope.py`、`requirement_clarifications.py`。
- 测试：新增读口一致性测试；改动模块的现有测试只换读法，不改期望。
- 文档：`plan-and-results.md`、`verdicts-and-release.md` 删去对展开字段的说明；`architecture.md` 记一条决定。

## 架构

属于架构调整（④ 校验、⑤ 出报告的内部数据形状），按规矩要用户点头，并在 `architecture.md`“三、历次架构决定”记一行。
风险：第 2 步跨七个模块，回放和门禁计数是主要防线；改动量粗估几百行，未实测。

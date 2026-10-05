# 设计阶段、任务归并与证据复用

## 三个阶段，三个独立答案

`intent.review_phase` 会冻结到计划并在校验时与输入快照对账；不是按风险任意切换的放行开关。

| 值 | 本阶段目标 | 待核项处理 |
|---|---|---|
| `design_iteration` | 完成当前能做的设计、计算和修正 | 已确认且未接受的阻断 FAIL、潜在 P0 进入当前队列；非阻断 P2/P3 及其他缺口按依赖安排在本轮或冻结前 |
| `schematic_freeze` | 原理图证据齐全，可移交 PCB Layout | 执行原有严重度、覆盖、绑定、资料和 HANDOFF 闸门 |
| `prototype_verification` | 接收实物/布局证据，追踪整改 | 仍只审原理图与外部证据交接，不签署整机、EMC、寿命或生产准出 |

默认设计任务显式填 `design_iteration`；用户明确冻结时才切换到 `schematic_freeze`。
旧计划没有阶段时按保守的冻结语义校验；不用为了阅读历史报告补造字段。
阶段变更须重建计划及结果绑定；不能只改结果里的阶段。

`review-gate.json` 同时回答：

- `valid/errors`：记录是否有效，摘要、逐项覆盖、证据字段是否完整。
- `workflow.status/current_work_items`：本轮先做什么。设计迭代为 `ADDRESS_CURRENT_ITEMS`
  或 `CONTINUE_DESIGN`；冻结为 `FREEZE_BLOCKED` 或 `READY_FOR_LAYOUT`；样机阶段为
  `FOLLOW_UP_EXTERNAL_VERIFICATION`。记录无效一律 `REPAIR_REVIEW_RECORDS`。
- `release` / `workflow.schematic_release`：原理图冻结的 GO / CONDITIONAL_GO / NO_GO。

继续设计允许做分析、补证和整改；不代表可以上电、制板或生产。冻结 NO_GO 不能解释为
禁止继续完善设计。`--require-release` 仅在申请冻结时使用。

定阶段前按 [最小充分证据](evidence-proportionality.md) 核实缺口，AI 先完成现有资料支持的工作。
OPEN 后续事项不阻止日常设计继续；本轮报告用“移交后续设计”说明结构、PCB、固件或样机
阶段的约束。冻结闸门与实际接收记录仍按下文处理。

## 每个共同根因对应一次任务

分阶段结果新增 `workflow_version: 1` 和 `work_items`；每个 FAIL/INSUFFICIENT 至少关联一个任务，
其余 PASS/NA 不创建待办。没有未决项时填空数组。示例中的 ID 必须替换成实际检查 ID：

```json
{
  "workflow_version": 1,
  "work_items": [{
    "id": "W-MAG-001",
    "title": "取得磁件的受控规格",
    "root_cause": "当前资料包没有目标变压器的绕组及绝缘规格",
    "check_ids": ["<实际检查ID1>", "<实际检查ID2>"],
    "due_stage": "schematic_freeze",
    "reason": "缺口影响匝比及绝缘判断，冻结前须闭合；其他独立连接检查可继续",
    "next_action": "取得对应设计版本的磁件规格，再分别完成所关联的计算与条款核对",
    "evidence": [{"source": "input-manifest.json", "locator": "磁件规格缺失记录"}]
  }]
}
```

字段 `id/title/root_cause/check_ids/due_stage/reason/next_action/evidence` 必填。
同一任务可关联多个检查，一个检查也可能依赖多个任务。共享的只是补证或修改动作，
不是电气结论；各项仍保留自己的 missing_inputs、判据、严重度理由和证据。
合并依据写到 `root_cause/reason/evidence`；不能用“缺资料”把不相关问题揉成一项。
已有 finding 根因相同的 FAIL 共用一个任务，引用 finding 的详细改法，避免再写一份操作说明。

需求未定（`gap_cause: REQUIREMENT_OPEN`）的项反馈给设计者/需求方，关联任务必须放在 `design_iteration`；
需求确定后按新需求重判，不能用缺资料或后续阶段掩盖。
缺证不自动等于 P1。按实际受影响需求/失效条件填写 potential_severity，并在各项 rationale
说明理由；`blocking` 表示冻结影响，`due_stage` 表示工作安排，二者不能互相替代。
已确认阻断 FAIL（已有明确接受记录除外）和潜在 P0 不可推迟到后续阶段。
缺磁件、固件配置、补偿模型时可继续独立电路审查，但影响原理图正确性的前提须在冻结前补齐。

## 下游验证的严格边界

优先把判据拆清：原理图连接/额定值单独判定；实测温升、EMC、PCB 间距等独立移交。
不能把原理图就能判定的欠压、绝限、保护、绝缘器件或配置未知称为“等样机验证”。

若一个已计划的检查确实只缺下游验证，保持 INSUFFICIENT；以下条件**全部**成立时，
该项不额外阻断原理图冻结（不改变外部验证状态）：

1. 计划和结果的 `handoff.required` 都为 true，全部关联任务在 `prototype_verification` 关闭。
2. `handoff.scope` 为 `downstream_verification`，写明接收方、定量约束和验证方法。
3. HANDOFF 已 ACCEPTED/VERIFIED，且有真实接收/验证记录；Agent 不得代替接收方确认。
4. `handoff.schematic_prerequisites` 是非空、无重复的其他检查 ID，覆盖本项全部原理图前提，
   且当前均 PASS；各项证据确实证明相应前提，不能找任意 PASS 充数。
5. 本项不是 FAIL，potential_severity 不是 P0；全部其他记录校验仍通过。

这不是风险接受：只是已完成原理图前提后的阶段归属。固件/磁件/安全物料身份及参数缺失，
或原理图电气判据缺证，不满足上述语义，不能使用该路径。机器验证字段及状态，审查者
仍须核实前提与判据的语义关系。其余开放项沿用原闸门。

## 控制重复工作

首审建立完整台账；后续每轮仍执行解析、完整性及轻量自动扫描。
依赖影响范围外的手工阅读/计算可引用已有受控记录，见
[revision-impact-schema.md](revision-impact-schema.md)。先核对输入身份、条件和来源，
再保留当前结果及引用；不重复抄整篇手册，也不通过更新哈希掩盖未重算的电路变化。
正文只展示本轮变化、唯一缺陷和根因任务；完整检查台账作为附表。

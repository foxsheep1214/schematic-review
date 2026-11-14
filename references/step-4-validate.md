# ④ 校验

> 读者：审查员。

做本步前读 SKILL.md 和本文件；五个步骤的总览见 [SKILL.md 的执行流程](../SKILL.md#执行流程)。

结果独立保存为 `review-results.json`，绑定最终计划；批量脚本只录入已审结论。功能判定是判断单位，逐项检查是审计明细，
待办由功能判定的开放项派生（编号 W-<key>），见 [结果格式](results-format.md)。局部额定/寿命缺口用同规则 `split_out` 定位到实际对象；保留其余对象的已核范围，
不为降低条数合并独立电源级或补证动作。

## 4.1 对账前的功能复核

对账前先按 [功能复核](results-format.md#功能复核) 核每个功能的条款、计算、开放项的
`decides` 范围和手填检查项的对象、路径、因果、需求的分项要求（含多个分项要求的需求只有全部适用分项要求通过才 PASS）；校验的 F1–F11 和质量筛查零提示不能代替这一步。
复核的八个机器信号（`quality_screening` 的疑点）和处置方法见 [功能复核](results-format.md#功能复核)。
每条决定性余量写 `basis.cell`（表里没有的写 NONE），引了带公差输入的余量逐个列角点，门禁拒收缺的。

做完的标志：功能复核的八个信号每条按该节处置过，
决定性余量的 `cell` 为 NONE 的每条确认过表里没有这个参数，表里没有的已由门禁记为待扩项（`sr_improvements` 的 NEW_BOUND_CELL，进报告“对 SR 的反馈”）。

## 4.2 证据不足的分类

证据不足先按 [分出下游工作](verdicts-and-release.md#纯下游验证项) 分开样机/试验结果、优化目标和真实设计缺口；
批量脚本不能用一句固定兜底语给全部证据不足定级。分类落在开放项的 `kind` 上（VENDOR_DATUM），检查项由它派生：
关闭条件只写本阶段能拿到的东西——厂家保证值；实测、样机、仿真才能得到的部分不写进关闭条件，拆成阶段 NA 检查项加移交。
筛查对这类误记的提示（`DOWNSTREAM_RECORDED_AS_DESIGN_GAP`、`CALCULATION_RECORDED_AS_DATA_GAP`、`FIRMWARE_IMAGE_RECORDED_AS_DESIGN_GAP`、`UNOBTAINABLE_DATUM`、`DUPLICATE_WORK_ITEMS`、`TEMPLATE_REASON`）各自读哪些字段、怎么处置见 [功能复核](results-format.md#功能复核)。

做完的标志：每个开放项的 `kind` 定过，关闭条件里没有实测、样机、仿真；上述提示每条处置过（改 kind、拆阶段 NA 加移交、合并待办，或确认不是误记）。

## 4.3 跑校验与处置疑点

    python3 scripts/validate_review.py review-plan.json review-results.json --db db.json --lint lint-cold.json --lint lint-hot.json --require-actionable --json review-gate.json

- `valid` 只表示记录可对账；`quality_screening` 是疑点提示，确有错配才改结论。零提示不证明审完。
- 疑点落在手填检查项和功能判定/开放项上。派生检查项的措辞、对象、后果、缺口都是工具按开放项写的，筛查不逐项点它们：
  定级整批同级、下游/固件/计算误记、时序窗口这些疑点读开放项一次，`check_ids` 列它挡住的检查项（一条开放项和它的派生检查项算一个缺口）；处置时改开放项，派生检查项读取时重新派生。
- 已有资料尚未读算的项记 REVIEW_INCOMPLETE，本轮自己读算完；这是审查者自己的活，不是报告结论：有这种项时 `render_report.py` 不出报告、`pack_review.py` 拒绝打包，只在对话里交进度。
  只剩 SR 工具自身限制、已手工核完的写 `manual_verification`（什么算工具限制见 [单条检查](results-format.md#单条检查)）。
- 冻结时加 `--require-release`；非冻结阶段 `release` 不是总判定。

做完的标志：`review-gate.json` 的 `valid` 为真、`errors` 为空；`quality_screening` 的每条疑点看过，确有错配的改了记录；
REVIEW_INCOMPLETE 为 0，只剩工具限制的写了 `manual_verification`。

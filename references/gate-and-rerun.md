# 校验、门禁输出与重新审查

> 读者：审查员。

审查数据分四份文档：[intent 格式](intent-format.md)（`intent.json`，按需求和设计结果写，不抄设计方的意图文件）、[计划格式](plan-format.md)（`review-plan.json`）、[结果格式](results-format.md)（`review-results.json`）、[校验与重新审查](gate-and-rerun.md)（门禁输出与规则指纹）。计划只决定每项的规则、适用性和准备度，不提前制造 PASS/FAIL；结果另存，由 `validate_review.py` 对账。常规命令见 [SKILL.md](../SKILL.md)。

## 四、校验与门禁输出

    python3 scripts/validate_review.py review-plan.json review-results.json --db db.json --lint lint-cold.json --lint lint-hot.json --require-actionable --json review-gate.json

- 退出 0 表示台账有效（结论 NO_GO 也可正常交付）；2 表示台账有错。冻结门加 `--require-release`，NO_GO 也退出 2。
- 校验只证明记录一致，不验证来源文字真实、计算合理或判据穷尽。空计划、遗漏对象、C 写 PASS、NA 冲突、
  无位置/改法、虚假汇总、陈旧规则指纹均被拒绝。
- **自动扫描发现即计划检查**：冷检每条 FINDING/CANDIDATE 在计划里自成一项（id 形如
  `PWR-A01.AUX-DC-b17ec0`，判据为“规则名：发现原文”），像其他检查一样写结论；INFO 进计划
  `diagnostics`（`LINT_INFO`），不计疑点。两次 `--lint` 提供两次扫描的 JSON，
  校验核对每条发现都有计划检查项；结果不再写 `lint_reviews`。仅 PDF 模式明确 NA 并留依据。
- **输出**：`summary`（检查结果计数、唯一缺陷及 P0–P3）、`categorized_summary`（当前/历史检查、唯一缺陷、
  唯一任务、必需移交及其状态）、`insufficient_by_cause`、`requirement_clarification_summary`、`workflow`、
  `release`/`blockers`、`remediation_validation`、`binding_validation`；`parameter_sheet`（器件参数表：条款 `refs` 点名的每只器件
  引了哪些参数、出处与页、保证值 / 典型值 / 强制条款各几条、用在哪条余量或判断，报告据此出“器件参数表”一节）。
- **quality_screening** 提示理由/影响跨范围复用、位号与声明范围不相交，以及补证对象和接口模式错配。
  影响描述逐字段核对，不以正确的理由或证据位置替代因果核验；原样回显绑定对象/判据不能证明分析成立。
  PWR-C10 的 `qualification_refs` 指向实际已贴电容，连接器身份不能替代电容额定证明；USB 方向分析不能只复用 UART/SPI 的角色。
  仅作提示，不增添缺陷、不改变 release；共享依赖可明确加入对象范围并核对，零提示不证明审完。

## 五、规则指纹与重新审查

计划写入 `review_engine`：SKILL.md、`references/` 与 `scripts/` 的逐文件 SHA256 及总摘要（含未提交修改，
排除测试、缓存、隐藏文件、`.pyc` 和 `~` 备份）。任何规则文字修改都会改变指纹。

- 指纹变化后以当前输入重新生成计划并完整审查；旧 PASS、旧缺口列表不能代替本轮判断。
- 两次扫描的结果合并只接受同一指纹；CLI 校验要求当前指纹。
- 原始 datasheet、已验证模型和计算数据可复用，但先复核型号/版本、工况、保证条件和当前判据。

显式 `intent.devices` 中的关键器件按逐器件身份、工作条件与特殊脚检查展开，不能因位号不是 U/M 而遗漏；连接器仍走其专属检查，不重复生成未用脚项。声明只补覆盖，不替代身份、资料与结果审核。


### 保护时序审查附注

对以关断/响应时间不足为依据的结论，在本项证据或共享记录中给出故障后果、允许窗口、实际响应界、裕量、温度范围及关闭阶段。
可在结果检查项用可选`timing_assessment`对象记录上述同名英文字段（见最小充分证据）；或用`timing_assessment.evidence`
列出包含完整分析的共享文档定位。它是审查者工程证据，不替代缺口的 `severity`、HANDOFF或风险接受。
质量筛查的`TIMING_BLOCK_WITHOUT_WINDOW`只是需复核提示；补充一个字段不会使设计自动通过。

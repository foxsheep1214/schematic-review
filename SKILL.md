---
name: schematic-review
description: "审查硬件电路原理图的电气合理性和需求符合性，按严重度列出有证据的缺陷、修改建议和复验条件。用于首审、冻结前检查、改版 diff 和历史意见闭环；支持完整网表审查及明确受限的 PDF 审查。不签署 PCB 布局布线、SI/PI、EMC、热设计验收或生产准出。"
---

# 电路原理图系统审查

## 目的

依据当前需求、设计数据和器件保证条件，判断原理图在规定工况下能否实现预期功能；找出有证据的偏离，
给出可执行、可复验的修改建议，支持设计迭代及原理图冻结进入 PCB Layout。

## 架构

每次审查前先读这一节：SR 是五个步骤的流水线，每个步骤下有几个任务（1.1、1.2 …）；先弄清自己在哪一步、该写哪个文件、不能碰什么，再按“执行流程”逐个任务做。
步骤之间传的文件、格式版本、每个脚本属于哪一步，见 [架构说明](references/architecture.md)。

```
输入：需求 · 设计结果（原理图 / 网表 / BOM / 原理图 PDF） · 原厂与标准资料        设计方的报告、计算书等文档不进
  │
① 读入      工具     解析网表和 BOM，逐字抄录需求，审计资料是否齐          → db.json、datasheet-audit.json
  │         审查员   在 intent.json 写声明：需求理解、电源轨、器件类别、电路取舍
  ▼
② 出计划    工具     按规则总表展开功能树：系统功能 → 功能电路 → 接口 → 全板   → review-plan.json
  ▼
③ 判断      审查员   逐个功能写条件、自己的计算、余量、开放项 / 失败项         → review-results.json
  │         工具     由功能派生各检查项
  ▼
④ 校验      工具     对账：格式、出处、独立性、覆盖；只证明记录一致，不证明对   → review-gate.json
  ▼
⑤ 出报告    工具     只从台账生成报告并打包                                   → 审查报告.md / .html + record/
```

改版复审不是另一条路：在②和④两步加上旧网表和旧计划，按改动扩大复验范围（执行流程末尾）。

判断链、每步分工和**不变的决定**在 [流水线总览](references/pipeline-overview.md)，和本节一样每次审查前都要读。**改架构先问人**：修改 SR 本身前先把方案交给人确认，哪些算架构调整见 [架构说明](references/architecture.md#零改架构先问人)。

## 审查纪律

1. **事实与判据分开**：当前网表/BOM/图面证明实际连接和贴装；适用版本的官方 datasheet、errata、
   接口规范和受控需求证明应当怎样。矛盾时查版本、变体和适用条件。历史报告与 demo 只作线索。
2. **证据落到主张**：每项给页码、位号/物理脚号、网络和可定位出处。“不满足保证边界”不等于
   “实物必然失效”；未知后果单列，不降低已证实的违规。
3. **先读盲区、误报和关闭条件**：每项先看规则说明里朴素检查会漏掉什么、哪些合法结构会误触发，
   再按真实对象核；达到关闭条件即停，不归本项的交给说明里写的规则。见
   [每项检查的盲区与关闭条件](references/results-format.md#每项检查的盲区与关闭条件)。通用盲区不等于本次已发现风险，
   不能直接推出严重度、补证清单或阻断；说不清盲区或关闭条件的先复核规则合理性，不要求设计者为模板补材料。
4. **逐项覆盖**：需求、全部页面、器件/物理脚、电源轨、每路接口、检测/使能链、装配选项、运行状态和
   历史意见都进台账；按功能识别关键器件，不只查 U 前缀。READY、执行过一次、零命中都不等于完成；
   找到几项严重问题后也不停止其余适用审查。
5. **先算再判证据不足**：已有资料能回答的先读、先算、先定界；可信边界已违反就判 FAIL。
   只索取会改变本条判断的缺口，并分清缺外部资料、设计未定、需求未定和审查未完成。
   电阻、电容、电感、二极管等常规器件只排查风险：按最弱档定界，超出写 BOM 约束，需求有特殊要求（精度、宽温、寿命等）
   才提器件规格要求；寿命按 `intent.mission_profile` 一份任务剖面算，电解电容耐久写成估算的 BOM 约束，其他耗损件走 DEV-C06 固定检查项，
   次数没给记 NA（[寿命与耗损件](references/commodity-floors.md#寿命与耗损件)）；不因无料号、无 datasheet、无额定记证据不足，不向厂家要常规件数据，见
   [通用件最弱档基准](references/commodity-floors.md#常规器件只排查风险)。
   规则见 [最小充分证据](references/evidence-proportionality.md)。每项证据不足按
   [危险度分类原则](references/verdicts-and-release.md#证据不足的危险度分类原则) 评估有物理依据且尚未排除的最严重后果，
   不按“参数未知”、器件类别或整批默认值定级；等级、证据置信度和冻结影响分别记录。
   保护动态先按[动作窗口与裕量](references/wca-formulas.md#保护动作窗口与裕量)确定故障后果和允许窗口，
   再比较响应与裕量；不把缺全温最大参数本身设为冻结阻断。
6. **不通过必须可改**：每个 FAIL 给定位、旧→新、顺序操作、参数依据和通过标准；证据不足项写具体缺失输入，不能只写“待确认”；缺外部资料或设计未定的再给决定性影响、所需范围、取得方法及复审关闭条件。
   缺输入时给取得方法和条件方案，不编造料号、阻值或空闲 GPIO。能靠改原理图消除的证据不足，直接给电路改进建议；
   建议不改变本轮结论，改图并复审后才关闭。见 [报告与修改说明](references/report-and-remediation.md)。
   **用图说话**：P0/P1 错误和提出的电路改法配现状局部图，改连接时再配原厂参考或改后图；每处错误只写一遍问题（`root_cause`：哪个量越过哪个限值）、
   后果（`consequence`，一句）、怎么改（`fix`，一句），问题不写成“缺某器件”。见 [用图说话](references/report-and-remediation.md#用图说话)。
7. **守住范围**：准出对象是原理图；PCB、SI/PI、EMC、实测热和生产验证形成 HANDOFF，但原理图能判定的
   电气前提不能推给下游。分流只问一句：拿到这个数，今天能否在原理图上重判？能 → INSUFFICIENT（如实际负载、保护配置未知）；
   只能由样机/PCB/结构/试验产生 → 阶段 NA + HANDOFF，产品要求仍待验证。见 [纯下游验证项](references/verdicts-and-release.md#纯下游验证项)。

## 参考文件

每份参考文件的第三行写明读者：审查员读的是执行流程 ①–⑤ 会用到的；SR 维护者读的是改规则、改脚本时才用的；两者都读的，节里再分。
`scripts/tests/test_reading_path.py` 核对读者标记、本表和执行流程（含五个步骤文件）只引审查员文件。参考文件的篇幅不设上限；加内容时保持逻辑清晰：一件事只写在一处，每份文件的读者和用在哪一步是明确的，审查员按执行流程读下来不用来回找。

| 读者 | 何时读 | 文件 |
|---|---|---|
| 审查员 | 每一步都读：判断链、每步分工、不变的决定 | [pipeline-overview.md](references/pipeline-overview.md) |
| 审查员 | 做 ① 时 | [step-1-intake.md](references/step-1-intake.md) |
| 审查员 | 做 ② 时 | [step-2-plan.md](references/step-2-plan.md) |
| 审查员 | 做 ③ 时 | [step-3-judge.md](references/step-3-judge.md) |
| 审查员 | 做 ④ 时 | [step-4-validate.md](references/step-4-validate.md) |
| 审查员 | 做 ⑤ 时 | [step-5-report.md](references/step-5-report.md) |
| 审查员 | 规则编号、`intent.rule_gaps`、设计准则 | [rule-ids.md](references/rule-ids.md) |
| 审查员 | intent 里要写的名字：功能电路类型、器件角色、需求类别与参数名 | [review-vocabulary.md](references/review-vocabulary.md)（由 `scripts/catalog.py` 生成） |
| 审查员 | 判 NA/INSUFFICIENT、索取资料前 | [evidence-proportionality.md](references/evidence-proportionality.md) |
| 审查员 | 工作点和保证条件对不上时定界；估算判通过的边界 | [bounding-table.md](references/bounding-table.md)（由 `scripts/catalog.py` 生成） |
| 审查员 | 一条余量怎么判：合格、合格但有风险、不合格；无料号常规件的判定表 | [margin-verdicts.md](references/margin-verdicts.md) |
| 审查员 | BOM 缺具体料号、要给通用件额定定界时 | 方法见 [commodity-floors.md](references/commodity-floors.md)；最弱档的数值和依据见知识框架 `知识/设计准则/降额与应力/常规件最弱档.md` |
| 审查员 | 器件应力降额（降额规范）：I/II/III 级降额值、等级从哪来、取值规则 | 知识框架 `知识/设计准则/降额与应力/降额规范.md` |
| 审查员 | 器件应力怎么判（降额规范）：超额定不成立、超降额未超额定是应力风险、应力超幅单列、只审写出的应力余量 | 知识框架 `知识/设计准则/降额与应力/应力判法.md` |
| 审查员 | 结果、P0–P3（含 BOM 约束定级）、阶段、HANDOFF、准出 | [verdicts-and-release.md](references/verdicts-and-release.md) |
| 审查员 | 需求缺失/含糊/冲突：当场问用户，答复写进需求清单 | [requirement-clarifications.md](references/requirement-clarifications.md) |
| 审查员 | ① 写 intent.json：字段、输入声明、电路决定、需求参数 | [intent-format.md](references/intent-format.md) |
| 审查员 | ② 计划字段、展开规则、功能电路依赖与状态核对（含电平转换） | [plan-format.md](references/plan-format.md) |
| 审查员 | ③④ 结果字段：功能判定、条款、余量依据、开放项、单条检查、功能复核 | [results-format.md](references/results-format.md) |
| 审查员 | ④ 门禁输出怎么读 | [gate-and-rerun.md](references/gate-and-rerun.md) |
| 审查员 | 跨状态计算、局部/整体主张、父项与任务依赖 | [execution-consistency.md](references/execution-consistency.md) |
| 审查员 | 输入版本、覆盖与留档 | [inputs-and-coverage.md](references/inputs-and-coverage.md) |
| 审查员 | 跑解析器、各 EDA 字段映射、解析自检、PDF 提取与读图 | [input-parsing.md](references/input-parsing.md) |
| 审查员 | 资料补取、保证值核对 | [datasheets.md](references/datasheets.md) |
| 审查员 | 知识框架（运行时直接读，不在这里改）：需求要素、接口约定、计算方法、器件参数、失效与故障分析、典型电路的已知坑；判一条准则该要什么证据、怎样复算、保证值多少、器件怎样失效 | 框架 `知识/<组件>/`，位置见 [架构说明](references/architecture.md#四规则维护) |
| 审查员 | 复用上次核对过的器件角色与供电分组 | [reviewed-declarations.md](references/reviewed-declarations.md) |
| 审查员 | 工程计算公式；修改建议的计算预检查 | [wca-formulas.md](references/wca-formulas.md)、[calculation-preflight.md](references/calculation-preflight.md) |
| 审查员 | 需要有界 R/C 工作点或瞬态的仿真证据 | [simulation-evidence.md](references/simulation-evidence.md) |
| 审查员与 SR 维护者 | 写报告和修改说明 | [report-and-remediation.md](references/report-and-remediation.md)（“对 SR 的反馈”一节给维护者） |
| 审查员 | 复审、改版影响 | [revision-review.md](references/revision-review.md) |
| 审查员 | 自动扫描怎么跑、扫描提示怎么读、计算与厂家参数核对工具 | [scans-and-tools.md](references/scans-and-tools.md) |
| 审查员 | 检查器共同的识别与声明规则：轨身份、识别依据、器件类型核验、电路候选、装配状态、指纹绑定、缺口 | [checker-conventions.md](references/checker-conventions.md) |
| 审查员与 SR 维护者 | 各检查器查什么、intent 里怎么声明它 | [automation.md](references/automation.md)（检查器实现细节给维护者） |
| 审查员 | 被审对象是 ASG 的交付目录时 | [workflow-handoff.md](references/workflow-handoff.md) |
| SR 维护者 | 架构明细：步骤间文件、格式版本、脚本归属、历次架构决定、规则维护步骤 | [architecture.md](references/architecture.md) |
| SR 维护者 | 规则编号总表、判据、每项检查的盲区与常见误报（审查员用的名称表另出） | [check-catalog.md](references/check-catalog.md)（由 `scripts/catalog.py` 生成） |
| SR 维护者 | 改规则时：七项审查要点（要点1–7）、规则取舍的三问 | [review-charter.md](references/review-charter.md) |
| SR 维护者 | 设计准则库（规范 G01–G09；降额规范见上面两行）：设计准则、适用条件、覆盖、`catalog.BASIS`、更新步骤 | 知识框架 `知识/设计准则/工具/包说明/guideline-criteria.md` |
| SR 维护者 | 设计准则、降额数据和词表在框架里的位置、各文件的字段 | 知识框架 `知识/设计准则/工具/包说明/shared-layer.md` |

## 审查 ASG 交付的设计

被审对象是 ASG 的交付目录时，读 [审查 ASG 交付的设计](references/workflow-handoff.md)：只读其中的原理图、网表、PDF、BOM 和需求，独立取证、复算和审查，不迁移设计侧的通过结论。
受限 PDF 审查不得伪造网表来凑成完整输入。

## 规则编号

见 [规则编号](references/rule-ids.md)。

## 执行流程

大工程分批推进并保留进度，不缩小覆盖范围；身份或图形疑点立即前置。

做某一步前读 SKILL.md 和该步的细则文件。

| 步骤 | 做什么 | 输入 → 产出 | 关卡（做完的标志见细则） | 细则 |
|---|---|---|---|---|
| ① 读入 | 逐字抄录需求并在 `intent.json` 写声明；解析网表和 BOM；资料取证、核器件身份（1.1–1.3） | 需求、原理图/网表、BOM、资料目录 → `intent.json`、`db.json`、`datasheet-audit.json` | 导出日志无错误（DOC-A01）；冷扫 `lint.py` 的提示逐条处置 | [step-1-intake.md](references/step-1-intake.md) |
| ② 出计划 | 生成电路候选并逐个决定；出资料请求、重审计；合并扫描出唯一最终计划（2.1–2.3） | `db.json`、`intent.json`、`datasheet-audit.json` → `record/circuit-candidates.json`、`资料请求.md`、`review-plan.json`、`lint-cold.json`、`lint-hot.json` | `circuit_decisions.py --write` 无错误；合并扫描后扫描提示为空 | [step-2-plan.md](references/step-2-plan.md) |
| ③ 判断 | 逐个功能写判定、自己算数；由功能派生检查项；手填框架外检查项和图面目检（3.1–3.3） | `review-plan.json` → `review-results.json`、`knowledge-checklist.json` | `derive_rows.py` 无 ERROR；`knowledge_checklist.py check` 通过 | [step-3-judge.md](references/step-3-judge.md) |
| ④ 校验 | 对账前功能复核；给证据不足分类；跑校验、处置疑点（4.1–4.3） | 计划、结果、`db.json`、`lint-*.json` → `review-gate.json` | `validate_review.py … --require-actionable`：`valid` 为真、`errors` 为空、REVIEW_INCOMPLETE 为 0 | [step-4-validate.md](references/step-4-validate.md) |
| ⑤ 出报告 | 从台账渲染报告并补白话说明；打包交付三样（5.1–5.2） | 台账、`notes.json` → `审查报告.md`、`审查报告.html`、`record/` | `render_report.py` 出报告；`pack_review.py` 打包无拒绝 | [step-5-report.md](references/step-5-report.md) |
| 改版复审（H） | 在②和④加旧网表和旧计划，沿改动扩大复验 | `old-db.json`、旧计划、`review-claims.json` → `diff.json`、`revision-impact.json` | `diff_netlists.py … --fail-on-open-claims`；最终校验加 `--require-revision-impact` | [revision-review.md](references/revision-review.md#改版复审h) |

## 规则维护

加规则、字段、筛查、脚本、测试和变异的维护步骤在 [架构说明 四、规则维护](references/architecture.md#四规则维护)（SR 维护者读；审查员的流程到 ⑤ 为止）。

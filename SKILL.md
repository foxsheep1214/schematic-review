---
name: schematic-review
description: "审查硬件电路原理图的电气合理性和需求符合性，按严重度列出有证据的缺陷、修改建议和复验条件。用于首审、冻结前检查、改版 diff 和历史意见闭环；支持完整网表审查及明确受限的 PDF 审查。不签署 PCB 布局布线、SI/PI、EMC、热设计验收或生产准出。"
---

# 电路原理图系统审查

## 目的

依据当前需求、设计数据和器件保证条件，判断原理图在规定工况下能否实现预期功能；找出有证据的偏离，
给出可执行、可复验的修改建议，支持设计迭代及原理图冻结进入 PCB Layout。
审查按 [七项审查要点](references/review-charter.md) 组织：需求与功能、器件与连接、工况功能与性能、
参数裕量与应力、保护与异常响应、实施与下游约束、证据覆盖与复验闭环。

## 审查纪律

1. **事实与判据分开**：当前网表/BOM/图面证明实际连接和贴装；适用版本的官方 datasheet、errata、
   接口规范和受控需求证明应当怎样。矛盾时查版本、变体和适用条件。历史报告与 demo 只作线索。
2. **证据落到主张**：每项给页码、位号/物理脚号、网络和可定位出处。“不满足保证边界”不等于
   “实物必然失效”；未知后果单列，不降低已证实的违规。
3. **先读盲区、误报和关闭条件**：每项先看规则说明里朴素检查会漏掉什么、哪些合法结构会误触发，
   再按真实对象核；达到关闭条件即停，不归本项的交给说明里写的规则。见
   [每项检查的盲区与关闭条件](references/plan-and-results.md#每项检查的盲区与关闭条件)。通用盲区不等于本次已发现风险，
   不能直接推出严重度、补证清单或阻断；说不清盲区或关闭条件的先复核规则合理性，不要求设计者为模板补材料。
4. **逐项覆盖**：需求、全部页面、器件/物理脚、电源轨、每路接口、检测/使能链、装配选项、运行状态和
   历史意见都进台账；按功能识别关键器件，不只查 U 前缀。READY、执行过一次、零命中都不等于完成；
   找到几项严重问题后也不停止其余适用审查。
5. **先算再判证据不足**：已有资料能回答的先读、先算、先定界；可信边界已违反就判 FAIL。
   只索取会改变本条判断的缺口，并分清缺外部资料、设计未定、需求未定和审查未完成。
   规则见 [最小充分证据](references/evidence-proportionality.md)。每项证据不足按
   [危险度分类原则](references/verdicts-and-release.md#证据不足的危险度分类原则) 评估有物理依据且尚未排除的最严重后果，
   不按“参数未知”、器件类别或整批默认值定级；等级、证据置信度和冻结影响分别记录。
   保护动态先按[动作窗口与裕量](references/evidence-proportionality.md#保护动作窗口与裕量)确定故障后果和允许窗口，
   再比较响应与裕量；不把缺全温最大参数本身设为冻结阻断。
6. **不通过必须可改**：每个 FAIL 给定位、旧→新、顺序操作、参数依据和通过标准；证据不足项写具体缺失输入，不能只写“待确认”；缺外部资料或设计未定的再给决定性影响、所需范围、取得方法及复审关闭条件。
   缺输入时给取得方法和条件方案，不编造料号、阻值或空闲 GPIO。能靠改原理图消除的证据不足，直接给电路改进建议；
   建议不改变本轮结论，改图并复审后才关闭。见 [报告与修改说明](references/report-and-remediation.md)。
   **用图说话**：P0/P1 错误和提出的电路改法配现状局部图，改连接时再配原厂参考或改后图；文字按根因（哪个量越过哪个限值）→
   可能的损害 → 怎么改写，根因不写成“缺某器件”。见 [用图说话](references/report-and-remediation.md#用图说话)。
7. **守住范围**：准出对象是原理图；PCB、SI/PI、EMC、实测热和生产验证形成 HANDOFF，但原理图能判定的
   电气前提不能推给下游。分流只问一句：拿到这个数，今天能否在原理图上重判？能 → INSUFFICIENT（如实际负载、保护配置未知）；
   只能由样机/PCB/结构/试验产生 → 阶段 NA + HANDOFF，产品要求仍待验证。见 [纯下游验证项](references/verdicts-and-release.md#纯下游验证项)。

## 参考文件

| 何时读 | 文件 |
|---|---|
| 审查目的、七项审查要点、规则取舍 | [review-charter.md](references/review-charter.md) |
| 规则编号、判据、功能电路 | [check-catalog.md](references/check-catalog.md)（由 `scripts/catalog.py` 生成） |
| 判 NA/INSUFFICIENT、索取资料前 | [evidence-proportionality.md](references/evidence-proportionality.md) |
| BOM 缺具体料号、要给通用件额定定界时 | [commodity-floors.md](references/commodity-floors.md) |
| 结果、P0–P3、阶段、HANDOFF、准出 | [verdicts-and-release.md](references/verdicts-and-release.md) |
| 需求缺失/含糊/冲突 | [requirement-clarifications.md](references/requirement-clarifications.md) |
| intent、计划、结果字段与校验；功能电路展开边界（含电平转换） | [plan-and-results.md](references/plan-and-results.md) |
| 跨状态计算、局部/整体主张、父项与任务依赖 | [execution-consistency.md](references/execution-consistency.md) |
| 输入版本、解析、覆盖与留档 | [inputs-and-coverage.md](references/inputs-and-coverage.md) |
| 自动扫描与各检查器 | [automation.md](references/automation.md) |
| 资料补取、证据计算、Vref 复用 | [datasheets.md](references/datasheets.md) |
| 工程计算公式 | [wca-formulas.md](references/wca-formulas.md)；修改建议的计算预检查见 [calculation-preflight.md](references/calculation-preflight.md) |
| 写报告和修改说明 | [report-and-remediation.md](references/report-and-remediation.md) |
| 复审、改版影响 | [revision-review.md](references/revision-review.md) |
| ASG 交付带选型记录与意见归因 | [selection-review.md](references/selection-review.md) |

## 与 ASG 的有状态工作流交接

参与 ASG/SR 薄控制器流程时，读 [工作流交接约定 v1](references/workflow-handoff.md)。
接收受控 `task.json` 和 ASG 完整交付包；独立取证、复算、建计划和审查，不迁移设计侧的通过结论。
原生 intent/plan/results/gate 与修改任务保持本文格式；用控制器 `pack-result` 自动生成任务与文件绑定。
日常候选沿用当前版本，需求变化、重要电气改版和冻结才建立里程碑；状态查询默认不扫描历史。
控制器复跑原生校验器；有效的 NO_GO 报告用于整改，只有本版冻结审查可支持原理图冻结。
独立使用 SR（包括受限 PDF 审查）不依赖控制器；不得伪造网表来满足完整 ASG 交接约定。

## 规则编号

检查编号为 `内容域-方式序号`，如 `PWR-E01`（电源域的证据计算）。
内容域：DOC 图纸与数据、DEV 器件与引脚、NET 网络连接、PWR 电源、RST 启动与复位、CLK 时钟、
SIG 接口与信号、ANA 模拟与监测、PRO 防护与隔离、DRV 功率驱动、REQ 需求与闭环。
方式：A 自动扫描、E 证据计算、T 连接追踪、C 工程计算、D 条款核对、V 图面目检、Q 覆盖审计、H 版本比对。
方式字母只是标签，说明结论怎么得出；一条规则在哪次运行执行（网表扫描、证据扫描、专家审查、改版复审），由它在总表里声明的输入和执行者推出（`catalog.stage_of`），不由字母决定。
补查项也从总表选规则，ID 写成 `规则编号.自定义键`。

功能电路（DDR、USB、电源保护等）按 `intent.circuits` 逐电路×工况展开电路检查项；电路由候选文件与 `intent.circuit_decisions` 推出，不手画（第 2 步）；答案不随工作态变化的电路检查项（`catalog.STATE_INVARIANT`）每电路只问一次。REQ-Q07 只汇总，不能代替电路检查项；未检出也未声明的功能电路由 REQ-Q08 逐个确认。

## 执行流程

大工程分批推进并保留进度，不缩小覆盖范围；身份或图形疑点立即前置。

### 0. 基线与需求

从资料和对话提取功能/量化指标、接口角色与数量、输入范围/负载、温度、降额依据、保留/删除项，
写入 `intent.json`（字段见 [计划与结果台账](references/plan-and-results.md)）：每条要求有稳定 REQ ID、
判据和确认状态；装配配置写入 `intent.assemblies`；设 `review_phase`（日常设计 `design_iteration`，
用户明确要冻结才用 `schematic_freeze`）。需求缺失或冲突按 [需求澄清项](references/requirement-clarifications.md)
集中提出，先做不受影响的工作，不逐颗器件打断用户，也不自行接受风险。
录入前按 [需求原文到审查要求](references/requirement-clarifications.md#需求原文到审查要求) 分清确实待定、
客观设计要求、明确排除和下游工作；不能把源文件的 OPEN 标题机械变成责任方待决。
按 [输入与覆盖](references/inputs-and-coverage.md) 记录输入版本/哈希；PDF 与网表须核修订号证明同版。
仅有 PDF 时逐页读图并声明范围，不能声称网表/ERC/逐脚全量通过。缺工具先盘点现有能力，安装须另获授权。

### 1. 解析与完整性

    python3 scripts/parse_netlist.py <allegro目录> -o db.json
    python3 scripts/parse_kicad.py <文件.kicad_sch|kicadxml> -o db.json

核对重复归网、缺失 primitive、索引互反、符号声明脚与网表实有脚；导出日志有错误或中止（DOC-A01）先作为输入阻断。
NC 汇集伪网、No-connect 属性、DNP 不贴是三件事；不贴的串联通路视为断开，多配置分别分析。
原生输入受阻仍按 [受限输入中的独立主张](references/inputs-and-coverage.md#受限输入中的独立主张)
审查可读材料；记录具体资料矛盾或保证缺口，不用全板通用阻断代替逐项结论。
逐页提取 PDF 文本并建页码/页名/网表路径映射；极性、旋转不清时渲染局部放大。

### 2. 网表扫描：自动扫描与计划

    python3 scripts/lint.py db.json --log netlist.log --intent intent.json --plan-json review-plan-cold.json --json lint-cold.json

电路不手画：器件类别核验后生成候选，审查员只对候选做决定，再推出 `intent.circuits`，之后的两次扫描都带 `--candidates`：

    python3 scripts/circuit_candidates.py db.json --intent intent.json --datasheet-audit datasheet-audit.json --json record/circuit-candidates.json
    python3 scripts/circuit_decisions.py intent.json record/circuit-candidates.json --db db.json --write

候选 = 类型 + 核心器件（核验角色的 IC，或无人驱动 / 声明了角色的开关），成员带走到它的路径（`via`，是归属关系不是导通主张）；
决定每个候选恰一条：accept / merge / split / reject（OUTSIDE_SCOPE、NOT_A_CIRCUIT、DUPLICATE_OF）/ add（只收未归属器件），
merge、split、reject、add 和加工作态都要能定位的引用。每颗被持有的器件恰好归一块电路（`owned`），其余持有它的电路只引用它；
同一级打平的器件（候选的 `shared`）写 own 决定（`ref`、`candidate`、可定位引用）裁定归谁。
计划每行带所属对象 `owner`（电路、系统功能或全板），器件行归拥有该器件的电路；电路级行按候选编号与工作态识别，不随画法变。
计划的 `interfaces` 列出电路之间、链路、供电轨和连接器四种接口及端点角色；推不出的角色和轨源列为缺口。
接口规则逐接口问（电路对的方向与电平、链路两端电平、供电不同的网络的跨域注入、连接器的对端定义/载流/防护、敏感电路取电轨的噪声），
电路对、链路和连接器各有一个接口框架，与电路框架一样下功能判定。候选漏了器件不手加：记 REQ-Q08、改规则；
`unassigned` 与 `gaps`（没核验角色的 IC、缺引脚名）先清。
格式见 [计划与结果](references/plan-and-results.md#一intentjsonschema_version-3)，规则见 [自动检查](references/automation.md#二检查器)。

交付含计算库存、preflight 与 README/报告摘要时，网表扫描另执行 [派生摘要核对](references/document-summaries.md)；
证据扫描及报告定稿后用最终文件重放，候选按 DOC-Q01 单独入计划，不迁移局部输入资格 PASS。

网表扫描后先出资料请求：`python3 scripts/gap_inventory.py review-plan-cold.json --datasheet-audit datasheet-audit.json --md 资料请求.md`，按装配资料、器件资料、需求、图纸分组，每项写涉及位号和能解开的检查条数。把前几项一次发给设计方补齐再进入逐项审查，不要审完才发现几十条检查缺同一份资料；“审查者自行追踪”一组是自己的工作，不向设计方索取。

冷检的 FINDING/CANDIDATE 已各成计划一行，与其他检查一样作答。补齐命名启发式漏掉的对象/需求/工况，审查者补查项加入 `review-plan-cold.json`。排除候选须有反证，无特征不等于 NA。
检查器（I²C、去耦、感性负载、功率开关、输入滤波、上电、监控、差分电平、光耦等）每趟都跑；
名称线索只生成待复核候选，清单绑定输入指纹，不能编辑清单消缺口。见 [自动检查](references/automation.md)。
计划命令列出“未声明电压的轨”或“无界节点/跨域”时，先在 `intent.power_rails` 补轨压、节点窗口和参考地分区 `domain`
（由审查者按需求、稳压器/钳位手册和设计计算书自行定界，逐条写 `citation`），再证据扫描；空的 `power_rails` 会让全部阻容预判失效。见 [通用件定界](references/commodity-floors.md#计划预判dev-c01-逐颗行)。

### 3. 资料取证与器件身份（DEV-D01、DEV-D02）

    python3 scripts/audit_datasheets.py db.json --datasheet-dir <资料目录> --json datasheet-audit.json

- 先核 MPN、封装/温度/档位与 BOM/符号；关键采样电阻、保护/安规件、储能电容和磁件也按原厂订货表核对
  阻值/容量/耐压组合，不把系列范围当具体后缀的可订购范围。候选不代表身份成立。
- PART/VALUE 冲突或图面/BOM 与链接资料矛盾时，按 [身份冲突与身份分支](references/evidence-proportionality.md#身份冲突与身份分支)
  处理：不一致本身判 DEV-D04 FAIL，电气判据逐分支给条件结论，全部分支都违反才判电气 FAIL。
- 按实际用途读引脚、额定/推荐条件、相关 min/max、模式和 errata；“官方物理脚”指手册引脚定义的编号或名称，
  焊盘映射属于 PCB 阶段。核过的脚表写入 `intent.devices`，DEV-D02 差集和 DEV-D05 引脚处置据此列出。
- 器件类别写 `intent.device_kinds`（手册页码加原文，`audit_datasheets.py --intent` 核验）：分立半导体和连接器写
  类型，集成电路写手册标题给出的角色（pwm_controller、gate_driver、sr_controller、pd_controller、regulator、
  supervisor、opamp_comparator、shunt_reference、mcu、transceiver、isolator，都不是才写 ic）。没核验过的
  U/M 位号与 Q/D 位号一样是 DEV-D02 缺口；角色决定电路候选的核心器件，计划顶层 `domains` 据此列出参考地分区、
  跨域器件与截止网络（[自动检查](references/automation.md)）。
- AI 已逐端核对的器件角色和电源/返回分组按 [可复用声明](references/reviewed-declarations.md) 保存来源与输入指纹；
  下次先验证声明，输入变化则重新核对，不能只刷新摘要。`manual_*` 兼容字段不代表人员确认，核对者身份须如实记录。
- 资料缺失时按 [器件资料](references/datasheets.md) 补取（先 LCSC/立创，再原厂），仍取不到按逐参数补证；
  PDF 提取的关键数值对照渲染页核单位。证据计算所需保证值整理成 `evidence.json`。
- ASG 交付包带 `record/selection.json`（核心器件选型）和归因记录时，按 [选型与归因复核](references/selection-review.md)
  用 `scripts/review_selection.py` 生成复核表，逐角色独立给 AGREE/DISAGREE/INSUFFICIENT，不同意要给候选之外的型号或点名 ASG 理由的错误；
  复核摘要进报告处理清单。

### 4. 证据扫描：证据计算

    python3 scripts/audit_datasheets.py db.json --datasheet-dir <资料目录> --resolution datasheet-resolution.json --evidence evidence.json --intent intent.json --json datasheet-audit.json
    python3 scripts/lint.py db.json --log netlist.log --intent intent.json --evidence evidence.json --datasheet-audit datasheet-audit.json --merge-plan review-plan-cold.json --plan-json review-plan.json --json lint-hot.json

`review-plan.json` 是唯一最终计划。自动 E 只覆盖输入的具体对象；资料未 AVAILABLE、指纹过期或模型缺失时保持证据不足，
例外见 [自动证据计算的例外](references/evidence-proportionality.md#自动证据计算的例外)。

### 5. 专家审查：连接追踪（T）、工程计算（C）、条款核对（D）

判断的单位是**功能**，不是检查行。分三小步：

1. **功能判定**：按计划 `functions[]` 的框架逐个填写 `review-results.json` 的 `functions[]`（字段与 F1–F12 见
   [功能判定](references/plan-and-results.md#功能判定functions)）。框架自带问题、检查行、每条规则的盲区和五步核对单；
   审查员读手册和自己的计算，不翻规则书。先列手册里与这个功能有关的条件（`conditions`）：每条写页码/表号/节名或点名的网络、引脚，
   “见 engineering.md”不定位任何东西；再写它是哪种证据（`kind`）：数字限值 NUMERIC_LIMIT（`limit` 的 min/max 与单位、引出这个数、`regime`），
   强制条款 MANDATORY_CLAUSE（引出“必须/不得”句、`applies`；典型应用不算），网表事实 NETLIST_FACT（点名网络或 REF.PIN），
   典型参考 TYPICAL_REFERENCE，工程假设 ENGINEERING_ASSUMPTION；每条判断（`judgements`）至少引一条强制条款或网表事实，数字限值只在余量里比较；
   功能的 `objects` 就是电路（候选经决定）的位号和网络，要扩大先改决定（merge/split）或候选规则，再重生成候选与计划；再算（`calculation`），
   算出余量就按它的依据（`margin.basis.kind`）下结论：保证最坏值 GUARANTEED_BOUND 满足判 PASS，不满足只是没证明；确会出现的工况 REACHABLE_CASE
   不满足判 FAIL；完整最坏范围 EXACT_ENVELOPE 两头都判；估算 ESTIMATE 什么都不判。`comparison` 为 GE 时零余量算满足、GT 时不算；
   与限值的 `regime` 不同要写 `conversion`。证明不满足的余量记失败项且发现项带改法，设计里已有的值不记“设计没定”；
   余量、判断和影响条目不写 `states` 时只覆盖不带状态的行，不覆盖全部状态；
   本设计还没选定的量写成规格（DESIGN_VALUE，`spec`+`owner`）；另一阶段欠的交付物（磁件图纸、固件应用能力确认）记
   DELIVERABLE_PENDING（`deliverable`+`owner`+`assumed`）；只有厂家才知道、公开资料界限（保证限值、相邻测试点单调夹出的界限、
   公开特性表、典型曲线加余量、应用笔记公式）也兜不住的参数才记 VENDOR_DATUM，并写查过哪几条、为什么不够、
   公开资料界限下的最坏情况与余量（`worst_case.bound`/`margin`；没有界就列 `curves_checked`，手册没规定本工作点的是设计风险，记失败项）。
   没有数值的方面写 `judgements`（方面、条件、说明了什么）；行只有本方面本状态有证明通过的余量或 judgement 才 PASS，没人判过的方面不默认通过。
   开放项的 `decides` 每条是一条影响条目：方面、状态、`via`（缺的量进到哪条条件或哪个计算输入）和 `rationale`（现有的界为什么不够）；
   一个缺口挡几个方面不限数，超过 3 个只提示复看。
   框架外的功能（intent 没有声明的电路）自己加，同样校验。
   隔离器件的工作资格（PRO-C03）和反馈稳定（PWR-C15）是隔离/变换器功能的方面，在同一个功能判定里写条款与计算。
   文档检查（DOC-*）不是功能电路：文档错误直接在行上判 FAIL 并写 finding，不包成功能。
2. **行派生**：跑 `derive_rows.py`（见第 7 步）；绑定了功能的行不手填。
3. **手填剩余行**：图面目检、引脚表、器件身份、需求条款等事实性检查照下面的写法；这些行要判资料不足，也必须先建一个功能判定。

按 PWR → RST → CLK → SIG → ANA → PRO → DRV 推进，每条规则逐对象、逐状态给结果；全板项逐条给适用性和结果。
功能电路按实际 package/circuit/state/ref 归组并列必需检查项 ID，跨类型依赖说明真实路径；不能只按规则编号归组。
按 [功能电路依赖与状态核对](references/plan-and-results.md#功能电路依赖与状态核对) 核全部实际检查项、外围选值窗口与掉电路径。
遇到共享控制网、多供源/状态、功能父项或共享整改任务，先读 [执行一致性](references/execution-consistency.md)。
先按 [对象上下文录入](references/plan-and-results.md#对象上下文录入) 保存实际物理对象、状态、路径及出处、
已核范围和未知边界，再形成结论；噪声 NA 先完成 [噪声路径资格](references/evidence-proportionality.md#噪声路径资格)。

- **电源与状态**：每轨追到真实电源脚或明确外部源，再到全部负载（PWR-T01）；0Ω/磁珠/二极管不是独立电源。
  按装配、开关/体二极管方向、EN/PG、时序和地参考分析，建立断电、启动/复位、运行、待机、掉电、热插拔和故障状态表。
  跨轨上拉先列候选再查 Ioff/注入/掉电容忍（SIG-C08）；检测点须匹配被测量（ANA-T01），查“采样→判断→使能→供电”循环依赖；
  地网逐个列出并核连接方式（PWR-T06）；复位期间和固件接管前的 IO 默认态不得误动作（RST-T04）。
- **连接追踪**：逐跳记录 起点物理脚→网络→已贴器件→网络→终点物理脚，同时核返回路径；端口、时钟、复位、启动、
  编程救援、反馈/检测、使能/故障上报都要追。TX/RX、P/N、Host/Device 按两端官方语义复述并查对端针序（SIG-T04）。
- **工程计算**：按 [WCA 公式](references/wca-formulas.md) 先确认模型，再代入实际串并联、输入/温度/负载和公差角点；
  原厂已覆盖工况的 Min/Max 直接使用。区分设定目标与物理可达输出（FB 公式不代表升压能力、RC 不等于复位脉宽、
  有 TVS 不等于防护通过）。阈值型保护（齐纳、电源轨 TVS、门限脚）两侧都算（PRO-C02），连接器信号线 ESD 随 PRO-D03 核；传感器开短路按控制器实际偏置档与环境全范围判别（ANA-C04）。连续可调输出在全范围扫描应力。判“缺保护”前计入 IC 自带保护（寄存器设定的门限归固件任务）；改频率/阻值/保护管时连带复算。
- **复算设计给出的数值**：设计计算书、配置表、报告里决定结论的数值，逐条写成 claim（出处、`calc.py` 计算名、带出处的输入、所称结果）用 `python3 scripts/calc_claims.py claims.json --json evidence/calc-claims.json` 复算；`circuit_bounds.*`（分压、RC 跨阈、线性稳压热、逻辑电平裕量、电容纹波折算、电阻功耗、串阻电流）与 `model_bounds.*` 自行枚举公差角点。MISMATCH 是文档错误候选，读原文确认后才入 DOC-Q01/相关检查；约定格式有效不等于模型正确。
- **核对模型和原表**：CrM Boost 输出电容用 `model_bounds.crm_boost_capacitor_ripple` 独立核二极管导通相位，并按控制器实际母线模式分别算；不沿用设计脚本的公式证明自身。厂家参数引用用 `audit_parameter_claims.py` 对比独立摘录的原表，给料号/材料、文档哈希、页码、温度/激励条件、典型或保证值口径；工程设计限值另核裕量，不能当厂家额定值引用。工具不代替原表摘录核实，详见 [自动检查](references/automation.md)。
- **动态数值证据**：需要有界 R/C 工作点或瞬态时按 [仿真证据](references/simulation-evidence.md)；样本在窗口内不直接等于规则 PASS。
- **条款核对**：每颗 IC/模组核推荐工作条件（DEV-C05）和逐脚处置（DEV-D05）；连接器核对端定义（DEV-D03）和对外防护（PRO-D03）；
  主控引脚复用对照平台约束与固件配置（SIG-D13）。由参考设计派生的电路列出全部偏离并按本设计条件复核。

### 6. 图面目检（V）

所有页面留目检记录（DOC-V01），新页和变更区细读；极性、pin1/视图、选项表、同名端、NC 标记以图形为证据。
注释、遗留命名和图框版本按 DOC-V02，装配选项互斥与完整性按 DOC-T01。

### 7. 结果、报告与校验

结果独立保存为 `review-results.json`，绑定最终计划；批量脚本只录入已审结论。功能判定是判断单位，逐项检查是审计明细，
待办由功能判定的开放项派生（编号 W-<key>），见 [台账三层](references/plan-and-results.md)。局部额定/寿命缺口用同规则 `split_out` 定位到实际对象；保留其余对象的已核范围，
不为降低条数合并独立电源级或补证动作。录入前按 [功能复核](references/plan-and-results.md#功能复核) 核每个功能的条款、计算、开放项的
`decides` 范围和手填行的对象、路径、因果、需求的分项要求（含多个分项要求的需求只有全部适用分项要求通过才 PASS）；校验的 F1–F12 和质量筛查零提示不能代替这一步。
   审查员自己绑到功能的行必须是该功能对象上的行；需求行（REQ-D01.<需求 ID>）不整行记阶段 NA，
   测试要求只在它的条款上记 NA 并链接单独的阶段 NA 行；成本、体积、取舍优先级这类优化目标或范围说明的需求行记 NOT_APPLICABLE 并引需求原文，不写 PASS。
证据不足先按 [分出下游工作](references/verdicts-and-release.md#纯下游验证项) 分开样机/试验结果、优化目标和真实设计缺口；
批量脚本不能用一句固定兜底语给全部证据不足定级。
功能判定写完后先派生已绑定的行（结论、open_ref/fail_ref、rationale 都从功能来；手填的行只对账不覆盖），再手填框架外的行：

    python3 scripts/derive_rows.py review-plan.json review-results.json -o review-results.json

完成后对账：

    python3 scripts/validate_review.py review-plan.json review-results.json --db db.json --lint lint-cold.json --lint lint-hot.json --require-actionable --require-bindings --json review-gate.json

- 执行审计（`--execution-audit`）是可选自检，不是交付门槛；用法见 [执行一致性](references/execution-consistency.md#可选的机器自检)。
- `valid` 只表示记录可对账；`quality_screening` 是疑点提示，确有错配才改结论。零提示不证明审完。
- 已有资料尚未读算的项记 REVIEW_INCOMPLETE，本轮自己读算完；审查未完成时只交进度，`pack_review.py` 拒绝打包。
  只剩 SR 工具自身限制、审查时已对照网表和原厂资料核对完的，按核对结论判定并写 `manual_verification`，不记 REVIEW_INCOMPLETE；
  工具因缺输入（手册要求、intent 声明、证据）拦住的不是工具限制，补输入、重生成计划，`manual_verification` 覆盖不了。
- 进报告的文字（任务、finding、handoff、notes）用白话，不用 [写法要求](references/report-and-remediation.md) 列出的词；
  `pack_review.py` 会检查。
- 冻结时加 `--require-release`；非冻结阶段 `release` 不是总判定。
- **交付只有三样**：项目审查目录顶层只放 `审查报告.md`、`审查报告.html`（同一内容，图直接显示）和 `record/`，其余中间文件留在工作目录。
  报告由脚本从台账生成，agent 只在 `notes.json` 里补白话说明（格式见 [报告与修改说明](references/report-and-remediation.md)）：

      python3 scripts/render_report.py review-plan.json review-results.json review-gate.json --notes notes.json -o <审查目录>/审查报告.md   # 同时写出 审查报告.html
      python3 scripts/pack_review.py <审查目录> --review-plan … --review-results … --review-gate … --db … --intent … \
        --circuit-candidates record/circuit-candidates.json --lint-cold … --lint-hot … --evidence-root <工作目录> --input schematic=<工程> --input requirements=<需求> …

  默认简洁报告保留全部缺陷、任务、通过标准及计数，逐项依据链接到台账；需逐条展开时加 `--detail full`，不手改报告或删检查来缩短输出。
  `pack_review.py` 只复制结论引用的证据；原理图工程、手册、需求、旧审查按路径和 SHA-256 记入 `record/manifest.json`。绝对引用只核声明输入，不拼入归档路径；本轮证据用 `--evidence-root` 内的安全相对路径（优先于输入里同名的旧文件），不允许 `..` 或符号链接越界。打包成功前逐个重读 packed 路径和 SHA-256；报告相对链接须都能打开。
  顶层有其他文件或引用的证据找不到时打包失败。声明的输入里有 ASG 交付（交付目录、其 `record/` 或其中文件，或交付里的原理图目录）时，
  交付带 `selection.json` 要有通过 `review_selection.py validate` 的选型复核，带 `calculations/` 要有至少一条已复算的 `calc_claims.py` 结果，
  带 `preflight-delivery.json` 要有读过该文件当前字节的派生摘要核对结果；三者都须被检查引用而进 `record/evidence/`，缺一项就拒绝打包。不另写 README 或说明文档；HTML 只能是脚本生成的那份。冻结与后续补充按 [留档](references/inputs-and-coverage.md#留档)。
  公开仓库只放脱敏合成用例。

### 8. 改版复审（H）

网表扫描和证据扫描传同一 `--old-db`、`--old-plan`，与本版 `--merge-plan` 分开；沿变更的供电/控制/保护依赖扩展复验。
保留每个历史 ID，区分撤回、复发、接受、已修复；断言要证明期望的电气状态，“字段变了”不足以关闭（REQ-H01）；
旧项消失须独立处置（REQ-H02）。`reuse_candidate` 只推荐核对已有记录，不能盲迁旧 PASS。
最终校验传相同旧基线并加 `--require-revision-impact`。见 [改版复审](references/revision-review.md)。

    python3 scripts/diff_netlists.py old-db.json db.json --claims review-claims.json --json diff.json --fail-on-open-claims

## 规则维护

- 加字段、加质量筛查或加结论词之前，先查现有字段、规则或筛查能否表达；能表达就复用，新增时写明现有哪一项覆盖不了。
- 同一块板由两名审查员（或两次运行）各出一份记录时，用 `python3 scripts/compare_reviews.py <记录A> <记录B> --md compare.md` 对比：
  精确配对只按检查项标识（`check_key`：规则、规则版本、去掉电路名的对象、判据）配对，报配对率、已答比例和一致率，列出通过对失败和 P0/P1 分歧；
  按电路对齐的结果只作建议配对，确认后用 `--alias` 带位置引用加入精确配对。差异里反复出现的写法先找现有校验为什么放过，再加机器能数的护栏，不加措辞要求。
  2026-10-21 的基线：两份记录各有 423 / 487 项检查，精确配对 234 项，一致 193 项（82.5 %），配对率 51.4 %。
- 新脚本先归入 [脚本分类](references/automation.md#脚本分类)：入口（执行流程里直接调用）、专用工具（特定情形手动调用）、库（只被导入）。只有入口写进执行流程。
- 工程规则身份由 `scripts/review_engine.py` 与 `scripts/skill_identity.py` 计算：算法、常量、受控正文和规范判据变化要求按当前规则重新验证；说明/接口页、入口元数据、测试及 Python 注释变化只做兼容检查。未知规范文件仍按规则处理，不能自行把判据降为说明。
- 规则编号、判据、审查要点归属和功能电路只在 `scripts/catalog.py` 登记，改后运行
  `python3 scripts/catalog.py --write-doc references/check-catalog.md`。来源为“全板通用”“电路检查项”的新规则
  登记后即自动展开；来源为“计划逐对象生成”“Lint 内置”或检查器的规则，还要在 `plan_review.py`、`lint.py`
  或对应检查器里实现展开/扫描。新增或调整规则先回答 [审查要点中的三个问题](references/review-charter.md#用审查要点指导进化)。
- 测试分两层（[分层定义](scripts/tests/conftest.py)）：每次改动先跑约定测试 `python3 -m pytest scripts/tests -m contract -q`（[规则约定](evals/rule_contracts/README.md)、校验器不变量、解析器，几秒）；新增 A/E/T/V/H 规则须同时加触发板与近似板。措辞层 `-m wording` 是每个台账夹具一份 golden 报告，改报告措辞用 `SR_UPDATE_GOLDEN=1` 重写快照并审读 diff。改规则或检查器后跑[变异门](evals/mutation/README.md) `python3 evals/mutation/run.py`，清单里每条变异都要被单元测试杀死。
- 修改脚本后运行 `python3 -m unittest discover -s scripts/tests -q`（全量，含两层），必要时按
  [电路评测说明](evals/circuit_bench/README.md) 跑冻结基准；改导入器时同时跑 [真实来源导入回归](evals/input_bench/README.md)；改 KiCad 解析、自检、日志扫描、去耦清单或计划展开时跑 [KiCad 原生交付回放](evals/kicad_replay_bench/README.md)。改检查器或规则后跑 [典型电路基准](evals/typical_circuits/README.md)（42 块开源板，每条报出都要已归类，新出现的须逐条审读）和 [种子基准](evals/seeded_bench/README.md) 看自动层检出；改定级、汇总、待办或报告逻辑后跑台账回放（schema 3 台账已退役，待一份按功能判定方法冻结的真实审查记录重建）；`python3 evals/bench_coverage.py --seeded <注入基准 results.json>` 列出每条 A/E 规则在哪个基准有真实板正例、哪些还没有。审查方法的合成评价在 `evals/workflow_guidance/`、`evals/scenarios/`。提高审查能力、压掉过严判断的训练闭环（缺陷—修复对、成熟板、人工裁决三类真值）按 [训练工作流](evals/training/README.md) 执行。评测通过不等于任何真实电路审查通过。

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

审查员从头到尾只沿一条线走：计划的功能树（系统功能 → 功能电路 → 接口 → 全板）。判断逻辑是一条链，每一层只在一个地方定义，其他文件只链接：

```
对象（功能树，catalog.py）→ 问题（功能框架，catalog.py）→ 条件与余量（审查员自己算，plan-and-results.md）
→ 检查项（derive_rows.py 派生）→ 对账（validate_review.py）→ 报告（render_report.py 只读台账）
```

规则编号里的内容域和方式字母只是检查项上的标签，说明一条规则查什么、怎么查，不是审查的顺序；
七项审查要点 G1–G7 是改规则时回答“为什么有这条规则”的坐标（[审查要点](references/review-charter.md)），审查员不按它走。

| 步骤 | 任务 | 这一步的目的 | 审查员要做的 | 审查员不能做的 |
|---|---|---|---|---|
| ① 读入 | 1.1–1.3 | 把输入变成有出处的事实：图上实际是什么、需求原文说什么、资料有没有、每颗器件是谁 | 核器件身份和资料，在 `intent.json` 写有出处的声明。器件类别、电源轨电压这些声明是“决定查什么”的判断，错了的代价是漏查而不是误判，所以同样要出处、同样进台账 | 引用设计方文档；猜阻值、料号 |
| ② 出计划 | 2.1–2.3 | 把事实变成要回答的问题：从网表枚举对象，按规则总表展开功能树，每颗器件恰归一处、每个问题恰有一个所属 | 对候选电路逐个下决定（reject 掉的电路以后没人再问，决定要有能定位的引用），补齐电源轨后重生成计划 | 手画电路、手加计划检查项（该查没查的登记 `intent.rule_gaps`） |
| ③ 判断 | 3.1–3.3 | 回答问题：按功能给电气结论，决定结论的数值自己算，缺口和失败只写一次，检查项由功能派生 | 按功能写判定，数值全部自己算 | 逐项各写一套结论；让工具或设计文档替自己下结论 |
| ④ 校验 | 4 | 对账：格式、出处、独立性、覆盖，有定界表的余量按表重算。只证明记录一致，不证明判断正确 | 按错误改记录，按疑点复核 | 为了过校验改结论、删检查 |
| ⑤ 出报告 | 5 | 呈现：只从台账渲染，打包时重新渲染比对，输入和证据按哈希留档，交付可追溯 | 在 `notes.json` 补白话说明 | 手改报告；交三样以外的文件 |

改版复审不是另一条路：在②和④两步加上旧网表和旧计划，按改动扩大复验范围（执行流程末尾）。

**不变的决定**（每条都是架构的一部分，改动按下面“改架构先问人”办理）：

1. 只认四类输入：需求、设计结果、原厂与标准资料、SR 自己的计算。
2. 规则只在 `scripts/catalog.py` 登记；查什么由工具生成的计划决定，审查员不手加检查项。
3. 判断的单位是功能：缺口和失败只在功能判定里写一次，检查项由功能派生；计划电路的缺口写在计划功能里，不另建功能装它。
4. 每个决定结论的数值由审查员自己算；工具只定对象、提供公式和对账，不替审查员下电气结论。器件参数能不能定界、推不出记哪一档，按工作点定界表执行，门禁按表重算核对（2026-10-23）。
5. 校验只证明记录一致，不证明审查正确。
6. 报告只从台账生成（打包时按台账重新渲染比对，门禁须 valid）；交付只有报告两份和 `record/`。

**改架构先问人**：修改 SR 本身时，下面任何一项都算架构调整，动代码或文档之前先把方案交给人确认，确认后才改：

- 增删或合并一个步骤，或改变步骤之间传的文件；
- 改 `intent.json`、计划或结果的格式版本；
- 改变谁做判断（工具与审查员之间的分工），或增删整类机制（例如退役自动保证值计算）；
- 改变输入范围（四类输入、独立性边界）或交付物；
- 改动上面任一条“不变的决定”，或增删执行流程的步骤、入口脚本。

方案写清：现在怎样、要改成怎样、动哪几步和哪些文件、不改的话有什么替代。新增或调整单条规则、检查器的识别逻辑、
报告措辞和测试不算架构调整，照“规则维护”一节做。架构改完，同步改本节和 [架构说明](references/architecture.md)
的“历次架构决定”，台账条目写明确认的日期和原话。

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
   电阻、电容、电感、二极管等常规器件只排查风险：按最弱档定界，超出写 BOM 约束，需求有特殊要求（精度、宽温、寿命等）
   才提器件规格要求；寿命按 `intent.mission_profile` 一份任务剖面算，电解电容耐久写成估算的 BOM 约束，其他耗损件走 DEV-C06 固定检查项，
   次数没给记 NA（[寿命与耗损件](references/commodity-floors.md#寿命与耗损件)）；不因无料号、无 datasheet、无额定记证据不足，不向厂家要常规件数据，见
   [通用件最弱档基准](references/commodity-floors.md#常规器件只排查风险)。
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
| 架构明细：步骤间文件、格式版本、脚本归属、历次架构决定 | [architecture.md](references/architecture.md) |
| 改规则时：审查目的、七项审查要点、规则取舍 | [review-charter.md](references/review-charter.md) |
| 规则编号、判据、功能电路 | [check-catalog.md](references/check-catalog.md)（由 `scripts/catalog.py` 生成） |
| 判 NA/INSUFFICIENT、索取资料前 | [evidence-proportionality.md](references/evidence-proportionality.md) |
| BOM 缺具体料号、要给通用件额定定界时 | [commodity-floors.md](references/commodity-floors.md) |
| 结果、P0–P3、阶段、HANDOFF、准出 | [verdicts-and-release.md](references/verdicts-and-release.md) |
| 需求缺失/含糊/冲突 | [requirement-clarifications.md](references/requirement-clarifications.md) |
| intent、计划、结果字段与校验；功能电路展开边界（含电平转换） | [plan-and-results.md](references/plan-and-results.md) |
| 跨状态计算、局部/整体主张、父项与任务依赖 | [execution-consistency.md](references/execution-consistency.md) |
| 输入版本、解析、覆盖与留档 | [inputs-and-coverage.md](references/inputs-and-coverage.md) |
| 自动扫描与各检查器 | [automation.md](references/automation.md) |
| 资料补取、保证值核对 | [datasheets.md](references/datasheets.md) |
| 工程计算公式 | [wca-formulas.md](references/wca-formulas.md)；修改建议的计算预检查见 [calculation-preflight.md](references/calculation-preflight.md) |
| 写报告和修改说明 | [report-and-remediation.md](references/report-and-remediation.md) |
| 复审、改版影响 | [revision-review.md](references/revision-review.md) |

## 与 ASG 的有状态工作流交接

参与 ASG/SR 薄控制器流程时，读 [工作流交接约定 v1](references/workflow-handoff.md)。
接收受控 `task.json` 和 ASG 完整交付包；独立取证、复算、建计划和审查，不迁移设计侧的通过结论。
原生 intent/plan/results/gate 与修改任务保持本文格式；用控制器 `pack-result` 自动生成任务与文件绑定。
日常候选沿用当前版本，需求变化、重要电气改版和冻结才建立里程碑；状态查询默认不扫描历史。
控制器复跑原生校验器；有效的 NO_GO 报告用于整改，只有本版冻结审查可支持原理图冻结。
独立使用 SR（包括受限 PDF 审查）不依赖控制器；不得伪造网表来满足完整 ASG 交接约定。

## 规则编号

检查编号为 `内容域-方式序号`，如 `PWR-E01`（电源域的保证值核对）。
内容域：DOC 图纸与数据、DEV 器件与引脚、NET 网络连接、PWR 电源、RST 启动与复位、CLK 时钟、
SIG 接口与信号、ANA 模拟与监测、PRO 防护与隔离、DRV 功率驱动、REQ 需求与闭环、CFG 配置（可编程器件逐配置组，组写在 `intent.devices.<位号>.configurable`；硬件按允许的配置范围判，配置表缺口只挡 CFG-D01 项和需求检查项）。
方式：A 自动扫描、E 保证值核对、T 连接追踪、C 工程计算、D 条款核对、V 图面目检、Q 覆盖审计、H 版本比对。
方式字母只是标签，说明结论怎么得出；一条规则在哪次运行执行（网表扫描、专家审查、改版复审），由它在总表里声明的输入和执行者推出（`catalog.stage_of`），不由字母决定。
计划里没有、审查员认为该查的项不直接加检查项（直接加的被拒），登记到 `intent.rule_gaps`，写法和去向见 [intent 字段](references/plan-and-results.md#一intentjsonschema_version-4)。

功能电路（DDR、USB、电源保护等）按 `intent.circuits` 逐电路×工况展开电路检查项；电路由候选文件与 `intent.circuit_decisions` 推出，不手画（2.1）；答案不随工作态变化的电路检查项（`catalog.STATE_INVARIANT`）每电路只问一次。REQ-Q07 只汇总覆盖、由工具按同类电路各检查项写出，不能代替电路检查项；未检出也未声明的功能电路由 REQ-Q08 逐个确认。

## 执行流程

大工程分批推进并保留进度，不缩小覆盖范围；身份或图形疑点立即前置。

### ① 读入

#### 1.1 需求与基线

从资料和对话提取功能/量化指标、接口角色与数量、输入范围/负载、温度、降额依据、保留/删除项，
写入 `intent.json`（字段见 [计划与结果台账](references/plan-and-results.md)）：需求原文由
`requirements_extract.py` 从需求文档逐字抄录（`requirement_source` 写文件与 sha256；任务书给了几份需求文档就登记几项，写成列表，一份都不少），每条要求只写 REQ ID、类别（规则总表的需求类别表）、对需求的理解（`interpretation`）、从原文读出的数字（`parameters`）、承接它的电路（`owners`，承接电路：落实这条需求的功能电路、系统功能或接口；计划会列出可承接的电路，有就必须写，认定没有承接电路写 `[]` 加能定位的理由）和确认状态，审查方面由参数和类别推出（有参数的方面只在原文读出了那个数时才问，拿不准的类别多选），判据取方面模板，扫描会列出原文里没读进参数的数字；设 `review_phase`（日常设计 `design_iteration`，
用户明确要冻结才用 `schematic_freeze`）。其余 intent 字段在有它的输入的那个任务里写：装配配置 1.2，资料路径、脚表、器件类别 1.3，电源轨 2.1。需求缺失或冲突按 [需求澄清项](references/requirement-clarifications.md)
集中提出，先做不受影响的工作，不逐颗器件打断用户，也不自行接受风险。
录入前按 [需求原文到审查要求](references/requirement-clarifications.md#需求原文到审查要求) 分清确实待定、
客观设计要求、明确排除和下游工作；不能把源文件的 OPEN 标题机械变成责任方待决。
按 [输入与覆盖](references/inputs-and-coverage.md) 记录输入版本/哈希；PDF 与网表须核修订号证明同版。
仅有 PDF 时逐页读图并声明范围，不能声称网表/ERC/逐脚全量通过。缺工具先盘点现有能力，安装须另获授权。

做完的标志：`requirements` 每条有类别、理解、参数和承接电路（或 `[]` 加理由）；需求原文里带单位的数字都读进了参数，
或在理解里说明为什么不读；`requirement_source`、输入文件的版本与哈希已记录；`review_phase` 已设。

#### 1.2 解析与完整性

    python3 scripts/parse_netlist.py <allegro目录> -o db.json
    python3 scripts/parse_kicad.py <文件.kicad_sch|kicadxml> -o db.json
    python3 scripts/read_bom.py db.json <BOM.csv>        # 有装配 BOM 时必跑，在生成计划之前

BOM 里每个位号除位号、值以外的列原样进 db，计划把它们挂到功能框架（`bom_specs`）和器件检查项（`bom_fields`）上：
里面写的器件规格（额定、公差、漏感上限等器件必须满足的值）是设计结果，照用；写在那里的设计方计算值不用。

核对重复归网、缺失 primitive、索引互反、符号声明脚与网表实有脚；导出日志有错误或中止（DOC-A01）先作为输入阻断。
NC 汇集伪网、No-connect 属性、DNP 不贴是三件事；不贴的串联通路视为断开，多配置分别分析，装配配置（贴装、跳线）写入 `intent.assemblies`。
原生输入受阻仍按 [受限输入中的独立主张](references/inputs-and-coverage.md#受限输入中的独立主张)
审查可读材料；记录具体资料矛盾或保证缺口，不用全板通用阻断代替逐项结论。
逐页提取 PDF 文本并建页码/页名/网表路径映射；极性、旋转不清时渲染局部放大。

`db.json` 有了就跑一遍冷扫（命令同 2.1 清单的 ①）：

    python3 scripts/lint.py db.json --log netlist.log --intent intent.json --plan-json review-plan-cold.json --json lint-cold.json

它打印的提示是 ① 各任务做完的标志的来源：阻值读不出的电阻在这里当场告诉用户（写法见 2.1）；没核验类别的器件、
泛称 ic、脚表没有供电脚（`DEVICE_KIND_GENERIC`、`DEVICE_PINS_NO_SUPPLY`、DEV-D02 的类别缺口）归 1.3；需求原文没读进参数的
数字（`REQUIREMENT_NUMBERS_UNREAD`）归 1.1；未声明电压的轨和无界节点留给 2.1 的 `power_rails`。intent 每补一批就重跑。
这里写出的 `review-plan-cold.json` 是中间产物，② 的 ①、⑤ 会重写它；步骤之间传的仍是 `db.json`、`intent.json` 和
`datasheet-audit.json`。

做完的标志：`db.json` 生成，导出日志没有错误（有则 DOC-A01 阻断，先解决）；装配 BOM 已读入；装配配置已写；
PDF 与网表核过同版；页码映射建好；冷扫跑过，阻值读不出的电阻已告知用户。

#### 1.3 资料取证与器件身份（DEV-D01、DEV-D02）

    python3 scripts/audit_datasheets.py db.json --datasheet-dir <资料目录> --intent intent.json --json datasheet-audit.json   # 取证并核验 intent.device_kinds

这条命令在 2.1 的清单里是 ②：候选（③）要用核验过的器件类别，所以器件类别每补一批就重跑；资料补齐后的重审计是 ⑦（2.2）。
资料只在 intent 写路径（`materials.<名>.path`，文件在即可用）。

- 先核 MPN、封装/温度/档位与 BOM/符号；关键采样电阻、保护/安规件、储能电容和磁件也按原厂订货表核对
  阻值/容量/耐压组合，不把系列范围当具体后缀的可订购范围。候选不代表身份成立。
- PART/VALUE 冲突或图面/BOM 与链接资料矛盾时，按 [身份冲突与身份分支](references/evidence-proportionality.md#身份冲突与身份分支)
  处理：不一致本身判 DEV-D04 FAIL，电气判据逐分支给条件结论，全部分支都违反才判电气 FAIL。
- 按实际用途读引脚、额定/推荐条件、相关 min/max、模式和 errata；“官方物理脚”指手册引脚定义的编号或名称，
  焊盘映射属于 PCB 阶段。核过的脚表写入 `intent.devices`（声明抄全的脚表要含封装名说出的每个脚号），DEV-D02 差集和 DEV-D05 引脚处置据此列出；
  去耦组由官方脚表逐器件逐供电网推出，只按（位号，网）写用途与条款。
- 器件类别写 `intent.device_kinds`（手册页码加原文，`audit_datasheets.py --intent` 核验）：分立半导体和连接器写
  类型，集成电路写手册标题给出的角色（角色登记表见 [检查目录·器件角色](references/check-catalog.md#器件角色)，
  `catalog.DEVICE_ROLES`；标题没有任何登记角色的才写泛称 ic，计划把每个 ic 列成 `DEVICE_KIND_GENERIC` 诊断：这些器件
  不生成电路候选，累计清单是下一批角色的来源）。没核验过的 U/M 位号与 Q/D 位号一样是 DEV-D02 缺口；角色决定电路候选的
  核心器件和它生成的电路类型，计划顶层 `domains` 据此列出参考地分区、跨域器件与截止网络（[自动检查](references/automation.md)）。
- AI 已逐端核对的器件角色和电源/返回分组按 [可复用声明](references/reviewed-declarations.md) 保存来源与输入指纹；
  下次先验证声明，输入变化则重新核对，不能只刷新摘要。`manual_*` 兼容字段不代表人员确认，核对者身份须如实记录。
- 资料缺失时按 [器件资料](references/datasheets.md) 补取（先 LCSC/立创，再原厂），仍取不到按逐参数补证；
  PDF 提取的关键数值对照渲染页核单位。

做完的标志（看 1.2 那条冷扫重跑后的提示）：审计跑过，每颗 U/M、Q/D 位号的 `device_kinds` 核验 VERIFIED（DEV-D02 不再列器件类别缺口）；
`DEVICE_KIND_GENERIC` 列出的泛称 ic 逐颗看过标题；关键器件脚表 `pinout_complete`，`DEVICE_PINS_NO_SUPPLY` 逐颗看过；
资料没拿到的留给 2.2 的资料请求，不在这里卡住。

### ② 出计划

#### 2.1 冷扫、候选与决定

② 出计划的命令按这个顺序跑（② 是 1.3 的取证，⑦ 是 2.2 的重审计，穿插在中间）：

    python3 scripts/lint.py db.json --log netlist.log --intent intent.json --plan-json review-plan-cold.json --json lint-cold.json       # ① 冷扫：1.2 的命令，① 做完后带全部 intent 再跑；还没有电路决定
    python3 scripts/audit_datasheets.py db.json --datasheet-dir <资料目录> --intent intent.json --json datasheet-audit.json             # ② 1.3 的取证命令，器件类别补全后再跑一次
    python3 scripts/circuit_candidates.py db.json --intent intent.json --datasheet-audit datasheet-audit.json --json record/circuit-candidates.json   # ③ 候选
    python3 scripts/circuit_decisions.py intent.json record/circuit-candidates.json --db db.json --write                               # ④ 决定，推出 intent.circuits
    python3 scripts/lint.py db.json --log netlist.log --intent intent.json --datasheet-audit datasheet-audit.json --candidates record/circuit-candidates.json --plan-json review-plan-cold.json --json lint-cold.json   # ⑤ 带候选重跑冷扫
    python3 scripts/gap_inventory.py review-plan-cold.json --datasheet-audit datasheet-audit.json --md 资料请求.md                      # ⑥ 资料请求
    python3 scripts/audit_datasheets.py db.json --datasheet-dir <资料目录> --resolution datasheet-resolution.json --intent intent.json --json datasheet-audit.json   # ⑦ 补齐资料后重审计（2.2）
    python3 scripts/lint.py db.json --log netlist.log --intent intent.json --datasheet-audit datasheet-audit.json --candidates record/circuit-candidates.json --merge-plan review-plan-cold.json --plan-json review-plan.json --json lint-hot.json   # ⑧ 合并扫描，出最终计划

intent 一旦写了 `circuit_decisions`，每次扫描都要带 `--candidates`，否则直接报错。每次扫描都会打印计划要你先处理的提示（阻值读不出、电路类型问不到规则、未声明电压的轨、无界节点/跨域），这些提示也写在计划的 `diagnostics` 里。

电路不手画：器件类别核验后生成候选，审查员只对候选做决定，再推出 `intent.circuits`。

候选 = 类型 + 核心器件（核验角色的 IC，或无人驱动 / 声明了角色的开关），成员带走到它的路径（`via`，是归属关系不是导通主张）；
决定每个候选恰一条：accept / merge / split / reject（OUTSIDE_SCOPE、NOT_A_CIRCUIT、DUPLICATE_OF）/ add（只收未归属器件），
merge、split、reject、add 和加工作态都要能定位的引用。每颗被持有的器件恰好归一块电路（`owned`），其余持有它的电路只引用它；
同一级打平的器件（候选的 `shared`）写 own 决定（`ref`、`candidate`、可定位引用）裁定归谁。
计划按功能树组织，每个检查项恰有一个所属 `owner`：系统功能（电源树、地、监控、上电时序、主控引脚，有对象才生成）→ 功能电路 → 接口 → 全板与文档。
电路级检查项归电路，按候选编号与工作态识别，不随画法变；器件检查项归拥有该器件的电路，器件应力、电容和精度每块电路对它拥有的器件问一项，没人拥有的器件归全板一项。
计划的 `interfaces` 列出电路之间、链路、供电轨和连接器四种接口及端点角色，推不出的角色和轨源列为缺口；
接口规则逐接口问（电路对的方向与电平、链路两端电平、供电不同的网络的跨域注入、连接器的对端定义/载流/防护、敏感电路取电轨的噪声）。
系统功能、电路对、链路和连接器各有一个框架，与电路框架一样下功能判定；报告的功能表按系统功能、功能电路、接口分组，每个发现项写所属。
校验覆盖两条：每颗贴装器件恰归一块电路或列在 REQ-Q08 待审清单上，每个接口都有它的检查项和框架。候选漏了器件不手加计划检查项：
属于某块电路的写 add 决定（`intent.circuit_decisions`，`id` 给已有电路即并入）后重生成；有源件（mosfet / bjt / opto / ic，以及类别读不出、三个以上网的器件）不属于任何电路的写器件级 reject（`ref`、`reason`、`citation`），
两端件留在 REQ-Q08 清单上写原因；候选规则该认出而没认出的，另记改进台账改规则。
`features` 的 NOT_APPLICABLE 声明不生成检查项：候选没检出的类型都在 REQ-Q08 那一项里逐个确认，声明只作它的依据；REQ-Q07 只给检出或声明适用的类型。
`unassigned` 与 `gaps`（没核验角色的 IC、缺引脚名）先清。
格式见 [计划与结果](references/plan-and-results.md#一intentjsonschema_version-4)，规则见 [自动检查](references/automation.md#二检查器)。

SR 独立审查，只用四类输入：需求、设计结果（原理图、网表、BOM、原理图 PDF）、原厂与标准资料、SR 自己的计算。
设计方的设计报告、设计方案、计算书、选型记录、电气意图、需求追溯、器件约定、开放项、自检与目检记录、交付证据、下游约束
和对前轮意见的回复都不作参考，也不逐条复算其中所称的数值；审查意图（`intent.json`）的出处和结果检查项的证据引用这些文件时
校验拒收（`independence.py`）。每个数值都由 SR 从原理图、需求和原厂资料自己算。原理图上看不出、只写在设计文档里的事实（固件设定的门限、寄存器配置等），
写成移交项请设计方确认，确认后作为需求或输入进入审查，不直接引用设计文档。

冷检的 FINDING/CANDIDATE 已各成计划一项，与其他检查一样作答。补齐命名启发式漏掉的对象/工况，登记到 `intent.rule_gaps` 后重新生成计划。排除候选须有反证，无特征不等于 NA。
电路检查项只在网表上有它问的机制时生成（功能框架的 `not_asked` 列出没问的和原因）；扫描提示某电路类型问不到一半规则（`CIRCUIT_TYPE_MISFIT`）时换电路类型或不建该电路。
计划检查项带 `requires` 仍记 NA 的，`applicability_evidence` 写排除它的 `nets`/`pins`；只说“不适用”的通过被拒，改记 NA。
检查器（I²C、去耦、感性负载、功率开关、输入滤波、上电、监控、差分电平、光耦等）每趟都跑；
名称线索只生成待复核候选，清单绑定输入指纹，不能编辑清单消缺口。见 [自动检查](references/automation.md)。
扫描提示“未声明电压的轨”或“无界节点/跨域”时，先在 `intent.power_rails` 补轨压、节点窗口和参考地分区 `domain`
（由审查者按需求和稳压器/钳位手册自行定界，逐条写 `citation`），网表上像电源而名字不像轨的网逐条声明成轨或写进 `rail_exclusions`，再合并扫描；空的 `power_rails` 会让全部阻容预判失效。扫描提示“阻值读不出的电阻”时当场告诉用户：列出位号和原值，请设计方改成 `阻值[/公差][/额定功率][/额定电压][/封装]` 的写法或确认阻值，不自行猜阻值；未改之前这些电阻的预判和脚电流不算。值后面多一个说不清的词（如 `47R/1%/2W/pulse`）时阻值照读，诊断 `RESISTOR_VALUE_WORD` 只列这个词：它说的要求（抗脉冲能量、额定电压）是特殊要求，写成 BOM 约束，不开“阻值读不出”的待办。见 [通用件定界](references/commodity-floors.md#计划预判dev-c01-逐颗检查项)。

做完的标志：候选文件已生成，`circuit_decisions.py --write` 无错误（每个候选恰一条决定、未归属有源件 0、加的工作态都有 `state_requirements` 点名的需求、`intent.circuits` 已推出）；
带候选的冷扫（⑤）不再提示未声明电压的轨、无界节点/跨域、`CIRCUIT_TYPE_MISFIT`、阻值读不出；候选文件的 `gaps` 清零，
`DEVICE_KIND_GENERIC` 列的 ic 逐颗看过；`CONFIGURABLE_UNDECLARED` 为 0（可编程器件的配置组都已在 `devices.<位号>.configurable` 声明）；REQ-Q08 清单上只剩两端件。

#### 2.2 资料请求与重审计

命令是 2.1 清单的 ⑥、⑦。网表扫描后先出资料请求（⑥），按装配资料、器件资料、需求、图纸分组，每项写涉及位号和能解开的检查条数。把前几项一次发给设计方补齐再进入逐项审查，不要审完才发现几十条检查缺同一份资料；“审查者自行追踪”一组是自己的工作，不向设计方索取：普通阻容（R、C 位号）的专属手册归在这一组的一项里，按
[通用件定界](references/commodity-floors.md) 的保守档算，不逐颗向设计方要。资料补齐后重审计（⑦）。

做完的标志：`资料请求.md` 已出并一次发给设计方（设计方组每项写了位号与能解开的检查条数）；补齐后 ⑦ 跑过，
`datasheet-audit.json` 里能取得的材料都 AVAILABLE；取不到的留给 ③ 作证据缺口，不在这里卡住。

#### 2.3 合并扫描

命令是 2.1 清单的 ⑧。`review-plan.json` 是唯一最终计划。保证值核对（E）检查项由网表定出对象，审查者按两端规格书的保证 Min/Max 判定；
资料未 AVAILABLE 时判资料不足，例外见 [保证值核对的例外](references/evidence-proportionality.md#保证值核对的例外)。

做完的标志：`review-plan.json` 由 ⑧ 写出；扫描提示为空（或每条处置后重跑过）；`diagnostics` 里只剩信息类（`LINT_INFO`、`PASSIVE_PACKAGE_UNKNOWN`、
`REQUIREMENT_OWNER_OUTSIDE_CANDIDATES` 这类提示）；计划 `summary` 的检查项数与功能数看过一遍，与板子规模相称。

### ③ 判断

判断的单位是**功能**，不是检查项。分三个任务：先逐个功能写判定（3.1），再由工具派生绑定的检查项（3.2），最后手填框架外的检查项（3.3）。

#### 3.1 功能判定

按计划 `functions[]` 的框架逐个填写 `review-results.json` 的 `functions[]`；字段、条件的五种、余量依据和开放项
都按 [功能判定](references/plan-and-results.md#功能判定functions)。框架自带问题、检查项、每条规则的盲区和五步核对单，审查员读手册、自己算，不翻规则书。要点：

- 条件（`conditions`）先能定位，再写种类；判断（`judgements`）引强制条款或网表事实，数字限值只在余量里比较。
- `objects` 就是电路（候选经决定）的成员；要扩大或漏了电路，改 `intent.circuit_decisions` 后重生成。框架的 `members` 既有电路检查项，也有这块电路拥有的器件检查项（身份、引脚、应力、工况、它器件上的扫描发现）：
  都在这个功能里判，同一方面的几颗器件一条 judgement 可以合答，差别用 `check_ids` 分开。一个电路的缺口和失败写在它自己的功能里；
  跨电路的缺口只写一次，影响条目用 `check_ids` 点名另一电路的检查项。自建功能只装不属于任何框架的检查项；文档检查（DOC-*）在检查项上判，不包成功能。
- 余量按 `margin.basis.kind` 下结论（GUARANTEED_BOUND 满足才 PASS、REACHABLE_CASE 不满足才 FAIL、EXACT_ENVELOPE 两头都判、ESTIMATE 不判，
  例外见该节“估算判通过”）；器件参数按[工作点定界表](references/bounding-table.md)定界，门禁重算。
  典型值估算能不能判 PASS 由定界表那一格的[判决边界](references/bounding-table.md#判决边界)按后果类定（不按规则 id）：
  估算判 PASS 的余量写 `cell`、`method`（G7–G9）、`consequence_class`、`estimate_factor`（等于格给该后果类的倍数，余量按打折后的值算）和 `handoff`；
  格没有这个参数写 `cell: NONE`，按默认（只许功能/性能后果，损坏/过热/保护类规则不估算）。这种 PASS 是 C 级证据，准出最高有条件定稿。
- 缺口先按[判“证据不足”之前先定界](references/evidence-proportionality.md#判证据不足之前先定界)走完公开资料界限，再分 DESIGN_VALUE / DELIVERABLE_PENDING / VENDOR_DATUM；
  检查项只在本方面本状态有证明通过的余量或判断时 PASS，没人判过的方面不默认通过。

按计划 `functions[]` 的顺序推进：系统功能 → 功能电路 → 接口 → 全板；每个功能逐对象、逐状态给结果，全板项逐条给适用性和结果。
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
- **自己算关键数值**：决定结论的数值由 SR 按原理图、需求和原厂资料自己算，`circuit_bounds.*`（分压、RC 跨阈、线性稳压热、逻辑电平裕量、电容纹波折算、电阻功耗、串阻电流）与 `model_bounds.*` 自行枚举公差角点。不复算设计文档所称的数值，也不拿它当判据。
- **核对模型和原表**：CrM Boost 输出电容用 `model_bounds.crm_boost_capacitor_ripple` 独立核二极管导通相位，并按控制器实际母线模式分别算；不沿用设计脚本的公式证明自身。厂家参数引用用 `audit_parameter_claims.py` 对比独立摘录的原表，给料号/材料、文档哈希、页码、温度/激励条件、典型或保证值口径；工程设计限值另核裕量，不能当厂家额定值引用。工具不代替原表摘录核实，详见 [自动检查](references/automation.md)。
- **动态数值证据**：需要有界 R/C 工作点或瞬态时按 [仿真证据](references/simulation-evidence.md)；样本在窗口内不直接等于规则 PASS。
- **条款核对**：每颗 IC/模组核推荐工作条件（DEV-C05）和逐脚处置（DEV-D05）；连接器核对端定义（DEV-D03）和对外防护（PRO-D03）；
  主控引脚复用对照平台约束与固件配置（SIG-D13）。由参考设计派生的电路列出全部偏离并按本设计条件复核。

做完的标志：`review-results.json` 的 `functions[]` 与计划的 `functions[]` 一一对应，每个功能有 verdict 与 evidence；
开放项、失败项每条有 `key`、`kind`、`decides`，每条边只挡这类开放项能挡的检查项（[每类开放项能挡哪些检查项](references/plan-and-results.md#三层台账)）；要算数的功能有计算记录，不用算的写 `no_calculation_reason`；
框架里每个方面×状态都有判断或开放项（派生时 `derive_rows.py` 不报“未判”）。

#### 3.2 检查项派生

功能判定写完后先派生已绑定的检查项（结论、open_ref/fail_ref、rationale 都从功能来；手填的检查项只对账不覆盖）；
绑定了功能的检查项不手填，绑定了树上检查的需求检查项（`bound_checks`）取绑定检查项中最差的结论，也不手填：

    python3 scripts/derive_rows.py review-plan.json review-results.json -o review-results.json

做完的标志：命令无 ERROR 写出结果；打印的“手填保留”检查项都是框架外的检查项，没有一条“手填与功能不一致”。

#### 3.3 手填剩余检查项与图面目检（V）

框架外的检查项手填：图面目检、全板拥有的器件检查项、需求条款等事实性检查；这些检查项要判资料不足，也必须先建一个功能判定。
审查员自己绑到功能的检查项必须是该功能对象上的检查项；需求检查项（REQ-D01.<需求 ID>）不整项记阶段 NA，
测试要求只在它的条款上记 NA 并链接单独的阶段 NA 检查项；成本、体积、取舍优先级这类优化目标或范围说明的需求检查项记 NOT_APPLICABLE 并引需求原文，不写 PASS。
所有页面留目检记录（DOC-V01），新页和变更区细读；极性、pin1/视图、选项表、同名端、NC 标记以图形为证据。
注释、遗留命名和图框版本按 DOC-V02，装配选项互斥与完整性按 DOC-T01。

做完的标志：计划里没有 `function_id` 的 APPLICABLE 检查项每条有结论与证据；每页有 DOC-V01 目检记录；需求检查项的条款逐条有判断或链接的阶段 NA 检查项。

### ④ 校验

结果独立保存为 `review-results.json`，绑定最终计划；批量脚本只录入已审结论。功能判定是判断单位，逐项检查是审计明细，
待办由功能判定的开放项派生（编号 W-<key>），见 [台账三层](references/plan-and-results.md)。局部额定/寿命缺口用同规则 `split_out` 定位到实际对象；保留其余对象的已核范围，
不为降低条数合并独立电源级或补证动作。

#### 4.1 对账前的功能复核

对账前先按 [功能复核](references/plan-and-results.md#功能复核) 核每个功能的条款、计算、开放项的
`decides` 范围和手填检查项的对象、路径、因果、需求的分项要求（含多个分项要求的需求只有全部适用分项要求通过才 PASS）；校验的 F1–F12 和质量筛查零提示不能代替这一步。
复核有四个机器信号（见 [功能复核](references/plan-and-results.md#功能复核)）：`UNIT_GLYPH_SUSPECT`（条款引的文本层丢了 Ω/µ，ms、mA 可能是 µs、µA，对照渲染页后在 `says` 写明核过）、
`RATING_AT_TEST_TEMP`（功率/电流额定只在 25 °C 单点给出，要走降额曲线或说明不降额）、`BOUNDING_CELL_AVAILABLE`（余量写了 `cell: NONE` 而定界表有这个参数的格）、`TEMPLATE_REASON`；
每条决定性余量写 `basis.cell`（表里没有的写 NONE），引了带公差输入的余量逐个列角点，门禁拒收缺的。

做完的标志：功能复核的四个信号每条处置过（单位对照原图后写进 `says`，额定走了降额或说明不降额，该写格的写了格并带推法），
决定性余量的 `cell` 为 NONE 的每条确认过表里没有这个参数，表里没有的已由门禁记为待扩项（`sr_improvements` 的 NEW_BOUND_CELL，进报告“对 SR 的反馈”）。

#### 4.2 证据不足的分类

证据不足先按 [分出下游工作](references/verdicts-and-release.md#纯下游验证项) 分开样机/试验结果、优化目标和真实设计缺口；
批量脚本不能用一句固定兜底语给全部证据不足定级。分类落在开放项的 `kind` 上（DESIGN_VALUE、VENDOR_DATUM、DELIVERABLE_PENDING），检查项由它派生：
关闭条件只写本阶段能拿到的东西——厂家保证值、设计规格、交付物；实测、样机、仿真才能得到的部分不写进关闭条件，拆成阶段 NA 检查项加移交。
筛查的四个提示点最常漏的几种：`DOWNSTREAM_RECORDED_AS_DESIGN_GAP`（开放项的 `closure`/`acquisition`/`why_insufficient` 或检查项的缺口文字接受实测、样机、样品、仿真作为关闭路径；
“随后/留给……”的分句已把下游部分分出，不算）、`CALCULATION_RECORDED_AS_DATA_GAP`（VENDOR_DATUM 开放项的 `acquisition`/`closure` 写了已读某页、只剩复算，又没说缺哪个数据）、
`FIRMWARE_IMAGE_RECORDED_AS_DESIGN_GAP`（开放项的 `what`/`closure`/`deliverable` 里是烧录镜像、读回、编程模式、量产校准，而不是编程口电平、上拉这类原理图前提）、
`UNOBTAINABLE_DATUM`（VENDOR_DATUM 开放项向厂家索取的参数，定界表那一格的可得性是“行业不给”：索取关不掉，走该格允许的估算加样机移交，或换种类）、
`DUPLICATE_WORK_ITEMS` 与 `TEMPLATE_REASON`（同一方法套几个对象、同一句关闭条件或取得方式写在几个开放项上：是一件待办、多个位号）。

做完的标志：每个开放项的 `kind` 定过，关闭条件里没有实测、样机、仿真；上述提示每条处置过（改 kind、拆阶段 NA 加移交、合并待办，或确认不是误记）。

#### 4.3 跑校验与处置疑点

    python3 scripts/validate_review.py review-plan.json review-results.json --db db.json --lint lint-cold.json --lint lint-hot.json --require-actionable --json review-gate.json

- `valid` 只表示记录可对账；`quality_screening` 是疑点提示，确有错配才改结论。零提示不证明审完。
- 疑点落在手填检查项和功能判定/开放项上。派生检查项的措辞、对象、后果、缺口都是工具按开放项写的，筛查不逐项点它们：
  定级整批同级、下游/固件/计算误记、时序窗口这些疑点读开放项一次，`check_ids` 列它挡住的检查项（一条开放项和它的派生检查项算一个缺口）；处置时改开放项，派生检查项由 `expand` 重写。
- 已有资料尚未读算的项记 REVIEW_INCOMPLETE，本轮自己读算完；审查未完成时只交进度，`pack_review.py` 拒绝打包。
  只剩 SR 工具自身限制、已手工核完的写 `manual_verification`（什么算工具限制见 [单条检查](references/plan-and-results.md#单条检查)）。
- 冻结时加 `--require-release`；非冻结阶段 `release` 不是总判定。

做完的标志：`review-gate.json` 的 `valid` 为真、`errors` 为空；`quality_screening` 的每条疑点看过，确有错配的改了记录；
REVIEW_INCOMPLETE 为 0，只剩工具限制的写了 `manual_verification`。

### ⑤ 出报告

#### 5.1 渲染报告与白话说明

- 进报告的文字（任务、finding、handoff、notes）用白话，不用 [写法要求](references/report-and-remediation.md) 列出的词；
  `pack_review.py` 会检查。
- 报告由脚本从台账生成，agent 只在 `notes.json` 里补白话说明（格式见 [报告与修改说明](references/report-and-remediation.md)）：

      python3 scripts/render_report.py review-plan.json review-results.json review-gate.json --notes notes.json -o <审查目录>/审查报告.md   # 同时写出 审查报告.html

  默认简洁报告保留全部缺陷、任务、通过标准及计数，逐项依据链接到台账；需逐条展开时加 `--detail full`，不手改报告或删检查来缩短输出。
- 按典型值估算判通过的检查由门禁的 `estimated_passes` 渲染成“按典型值估算的结论”一节（功能、格、怎么估、余量、样机要测、涉及检查），结论段和数字一览各带一句；
  器件类别词表或定界表没覆盖的（`sr_improvements` 的 NEW_DEVICE_KIND / NEW_BOUND_CELL）渲染在“对 SR 的反馈”下“器件类别与定界表要扩的”，只告诉 SR 维护者要扩表。
- 等交付物（DELIVERABLE_PENDING 开放项挡住的检查项，门禁 `pending_deliverables`）不是审查发现：不是阻断项，不进待办和“最先要解决的 3 件事”，
  渲染成“等交付物”一节（交付物、负责方、类别、可能后果、等它的判断、按什么假定判的、怎样算交付）给项目经理催办，准出最高有条件定稿（2026-10-26 定）。

- 渲染只写读者要的量（5.1 审核 2026-10-26）：功能表每个方面只写决定性余量、`calculation.result` 超 300 字只取第一句、问题里超过 8 个位号写个数；
  交给后续环节的要求只在每个字段至多一个位号槽时合并成"每只"一行；图说不重复 caption 的"现状/改后"；"涉及的检查"和"影响哪些判断"超过 6 条写个数；
  "未问"段只列方面名。待办标题超过 60 字出 TASK_TITLE_LONG 提示（标题点名器件或环路，细节放缺什么）；summary 复述检查计数与复述"能否定稿"一样被拒。
做完的标志：`notes.json` 的 summary、items、sr_feedback 用白话且都进了报告（summary 不带检查计数）；报告里的相对链接都能打开；
TASK_TITLE_LONG 提示每条处置过；报告里没有"每只、每只"串接、图说不重复。

#### 5.2 打包与交付

- **交付只有三样**：项目审查目录顶层只放 `审查报告.md`、`审查报告.html`（同一内容，图直接显示）和 `record/`，其余中间文件留在工作目录。

      python3 scripts/pack_review.py <审查目录> --review-plan … --review-results … --review-gate … --db … --intent … \
        --circuit-candidates record/circuit-candidates.json --notes notes.json --lint-cold … --lint-hot … --evidence-root <工作目录> --input schematic=<工程> --input requirements=<需求> …

  `pack_review.py` 用打包的计划、结果、门禁和 `notes.json` 重新渲染报告，与 `审查报告.md` 不同（手改过，或台账改了没重出）就拒绝；渲染时用了 `--title`、`--detail` 的，打包时同样传。门禁不 valid、结果声明了 `review_scope` 都不打包。它只复制结论引用的证据；原理图工程、手册、需求、旧审查按路径和 SHA-256 记入 `record/manifest.json`。绝对引用只核声明输入，不拼入归档路径；本轮证据用 `--evidence-root` 内的安全相对路径（优先于输入里同名的旧文件），不允许 `..` 或符号链接越界。打包成功前逐个重读 packed 路径和 SHA-256；报告相对链接须都能打开。
  顶层有其他文件或引用的证据找不到时打包失败。不另写 README 或说明文档；HTML 只能是脚本生成的那份。冻结与后续补充按 [留档](references/inputs-and-coverage.md#留档)。
  公开仓库只放脱敏合成用例。
- 证据只放摘录（5.2 审核 2026-10-26）：引用台账文件的证据指向 `record/`，不复制；引用 SR 自己的 references 按 `skill_version` 解析，不声明为输入；
  手册和标准声明为输入（`--input datasheets=<原厂资料目录>`）按路径加页码引用，引用了 `ds/*.txt` 抽取而没有含 PDF 的输入打包失败；
  单个证据超过 300 KB 打包给 NOTE，处置是改为按输入引用或裁成摘录。

做完的标志：`pack_review.py` 打包成功（无拒绝），审查目录顶层只有 `审查报告.md`、`审查报告.html`、`record/`；
`record/evidence/` 里没有台账副本，输入里没有 SR 自身文档，打包的每条 NOTE 处置过（改引用或留下理由）。

### 改版复审（H）

网表扫描和合并扫描传同一 `--old-db`、`--old-plan`，与本版 `--merge-plan` 分开；沿变更的供电/控制/保护依赖扩展复验。
保留每个历史 ID，区分撤回、复发、接受、已修复；断言要证明期望的电气状态，“字段变了”不足以关闭（REQ-H01）；
旧项消失须独立处置（REQ-H02）。`reuse_candidate` 只推荐核对已有记录，不能盲迁旧 PASS。
最终校验传相同旧基线并加 `--require-revision-impact`。见 [改版复审](references/revision-review.md)。

    python3 scripts/diff_netlists.py old-db.json db.json --claims review-claims.json --json diff.json --fail-on-open-claims

## 规则维护

- 加字段、加质量筛查或加结论词之前，先查现有字段、规则或筛查能否表达；能表达就复用，新增时写明现有哪一项覆盖不了。
- 同一块板由两名审查员（或两次运行）各出一份记录时，用 `python3 scripts/compare_reviews.py <记录A> <记录B> --md compare.md` 对比：
  精确配对只按检查项标识（`check_key`：规则、规则版本、去掉电路名的对象、判据）配对，报配对率、已答比例和一致率，列出通过对失败和 P0/P1 分歧；
  按电路对齐的结果只作建议配对，确认后用 `--alias` 带位置引用加入精确配对；"电路决定与成员差"一节逐候选列两边的决定（accept / merge / split / reject 及去向）、
  对齐电路里只在一边的位号、未归属器件两边的处置（add 进电路还是留给 REQ-Q08），电路划分的差异在这里数，不混进配对率。
  差异里反复出现的写法先找现有校验为什么放过，再加机器能数的护栏，不加措辞要求。
- 新脚本先在 [架构说明](references/architecture.md#二每个脚本属于哪一步) 归到一步并分类：入口（执行流程里直接调用）、工具（特定情形手动调用）、库（只被导入）。只有入口写进执行流程；新增入口属于架构调整。
- 工程规则身份由 `scripts/electrical_contract.py`（`engine_identity`）与 `scripts/skill_identity.py` 计算：算法、常量、受控正文和规范判据变化要求按当前规则重新验证；说明/接口页、入口元数据、测试及 Python 注释变化只做兼容检查。未知规范文件仍按规则处理，不能自行把判据降为说明。
- 规则编号、判据、审查要点归属和功能电路只在 `scripts/catalog.py` 登记，改后运行
  `python3 scripts/catalog.py --write-doc references/check-catalog.md`。来源为“全板通用”“电路检查项”的新规则
  登记后即自动展开；来源为“计划逐对象生成”“Lint 内置”或检查器的规则，还要在计划生成的对应层（电路与器件 `plan_circuits.py`、接口 `interfaces.py`、
  系统功能 `plan_system.py`、全板与覆盖 `plan_board.py`；`plan_review.py` 只做汇总）、`lint.py` 或对应检查器里实现展开/扫描。新增或调整规则先回答 [审查要点中的三个问题](references/review-charter.md#用审查要点指导进化)。
- 测试分两层（[分层定义](scripts/tests/conftest.py)）：每次改动先跑约定测试 `python3 -m pytest scripts/tests -m contract -q`（[规则约定](evals/rule_contracts/README.md)、校验器不变量、解析器，几秒）；新增 A/E/T/V/H 规则须同时加触发板与近似板。措辞层 `-m wording` 是每个台账夹具一份 golden 报告，改报告措辞用 `SR_UPDATE_GOLDEN=1` 重写快照并审读 diff。改规则或检查器后跑[变异门](evals/mutation/README.md) `python3 evals/mutation/run.py --changed`（只跑落在改动文件上的变异，几分钟），提交前或发布前跑全量 `python3 evals/mutation/run.py`；每条变异都要被单元测试杀死。
- 修改脚本后运行 `python3 -m unittest discover -s scripts/tests -q`（全量，含两层）；改导入器时同时跑 [真实来源导入回归](evals/input_bench/README.md)；改 KiCad 解析、自检、日志扫描、去耦清单或计划展开时跑 [KiCad 原生交付回放](evals/kicad_replay_bench/README.md)。改检查器或规则后跑 [典型电路基准](evals/typical_circuits/README.md)（42 块开源板，每条报出都要已归类，新出现的须逐条审读）和 [种子基准](evals/seeded_bench/README.md) 看自动层检出；改定级、汇总、待办或报告逻辑后跑台账回放（schema 3 台账已退役，待一份按功能判定方法冻结的真实审查记录重建）；`python3 evals/bench_coverage.py --seeded <注入基准 results.json>` 列出每条 A 规则在哪个基准有真实板正例、哪些还没有。评测通过不等于任何真实电路审查通过。

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

## 架构

每次审查前先读这一节：SR 是一条五环的流水线，先弄清自己在哪一环、该写哪个文件、不能碰什么，再按“执行流程”逐步做。
环与环之间的文件、格式版本、每个脚本属于哪一环，见 [架构说明](references/architecture.md)。

```
输入：需求 · 设计结果（原理图 / 网表 / BOM / 原理图 PDF） · 原厂与标准资料        设计方的报告、计算书等文档不进
  │
① 读入      工具     解析网表和 BOM，逐字抄录需求，审计资料是否齐          → db.json、datasheet-audit.json
  │         审查员   在 intent.json 写声明：需求理解、电源轨、器件类别、电路取舍
  ▼
② 出计划    工具     按规则总表展开功能树：系统功能 → 功能电路 → 接口 → 全板   → review-plan.json
  ▼
③ 判断      审查员   逐个功能写条件、自己的计算、余量、开放项 / 失败项         → review-results.json
  │         工具     由功能派生各检查行
  ▼
④ 校验      工具     对账：格式、出处、独立性、覆盖；只证明记录一致，不证明对   → review-gate.json
  ▼
⑤ 出报告    工具     只从台账生成报告并打包                                   → 审查报告.md / .html + record/
```

| 环 | 执行流程步骤 | 审查员要做的 | 审查员不能做的 |
|---|---|---|---|
| ① 读入 | 0、1、3 | 核器件身份和资料，在 `intent.json` 写有出处的声明 | 引用设计方文档；猜阻值、料号 |
| ② 出计划 | 2、4 | 对候选电路逐个下决定，补齐电源轨后重生成计划 | 手画电路、手加计划行（该查没查的登记 `intent.rule_gaps`） |
| ③ 判断 | 5、6 | 按功能写判定，数值全部自己算 | 逐行各写一套结论；让工具或设计文档替自己下结论 |
| ④ 校验 | 7 | 按错误改记录，按疑点复核 | 为了过校验改结论、删检查 |
| ⑤ 出报告 | 7 | 在 `notes.json` 补白话说明 | 手改报告；交三样以外的文件 |

改版复审（第 8 步）不是另一条路：在②和④两环加上旧网表和旧计划，按改动扩大复验范围。

**不变的决定**（每条都是架构的一部分，改动按下面“改架构先问人”办理）：

1. 只认四类输入：需求、设计结果、原厂与标准资料、SR 自己的计算。
2. 规则只在 `scripts/catalog.py` 登记；查什么由工具生成的计划决定，审查员不手加行。
3. 判断的单位是功能：缺口和失败只在功能判定里写一次，检查行由功能派生；计划电路的缺口写在计划功能里，不另建功能装它。
4. 每个决定结论的数值由审查员自己算；工具只定对象、提供公式和对账，不替审查员下电气结论。器件参数能不能定界、推不出记哪一档，按工作点定界表执行，门禁按表重算核对（2026-10-23）。
5. 校验只证明记录一致，不证明审查正确。
6. 报告只从台账生成；交付只有报告两份和 `record/`。

**改架构先问人**：修改 SR 本身时，下面任何一项都算架构调整，动代码或文档之前先把方案交给人确认，确认后才改：

- 增删或合并一环，或改变环与环之间传的文件；
- 改 `intent.json`、计划或结果的格式版本；
- 改变谁做判断（工具与审查员之间的分工），或增删整类机制（例如退役自动保证值计算）；
- 改变输入范围（四类输入、独立性边界）或交付物；
- 改动上面任一条“不变的决定”，或增删执行流程的步骤、入口脚本。

方案写清：现在怎样、要改成怎样、动哪几环和哪些文件、不改的话有什么替代。新增或调整单条规则、检查器的识别逻辑、
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
   才提器件规格要求；寿命按 `intent.mission_profile` 一份任务剖面算，电解电容耐久写成估算的 BOM 约束，其他耗损件走 DEV-C06 固定行，
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
| 架构明细：环间文件、格式版本、脚本归属、历次架构决定 | [architecture.md](references/architecture.md) |
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
SIG 接口与信号、ANA 模拟与监测、PRO 防护与隔离、DRV 功率驱动、REQ 需求与闭环、CFG 配置（可编程器件逐配置组，组写在 `intent.devices.<位号>.configurable`；硬件按允许的配置范围判，配置表缺口只挡 CFG-D01 行和需求行）。
方式：A 自动扫描、E 保证值核对、T 连接追踪、C 工程计算、D 条款核对、V 图面目检、Q 覆盖审计、H 版本比对。
方式字母只是标签，说明结论怎么得出；一条规则在哪次运行执行（网表扫描、专家审查、改版复审），由它在总表里声明的输入和执行者推出（`catalog.stage_of`），不由字母决定。
计划里没有、审查员认为该查的项不直接加行，登记到 `intent.rule_gaps`（对象、按哪条规则判、判据、缺什么规则、依据），计划工具写成 `REVIEWER_ADDED` 行：照常判，单独计数，不计入两份记录的配对率；门禁列出每条缺口，记进改进台账，变成工具生成的规则。直接加进计划的行被拒。

功能电路（DDR、USB、电源保护等）按 `intent.circuits` 逐电路×工况展开电路检查项；电路由候选文件与 `intent.circuit_decisions` 推出，不手画（第 2 步）；答案不随工作态变化的电路检查项（`catalog.STATE_INVARIANT`）每电路只问一次。REQ-Q07 只汇总覆盖、由工具按同类电路各行写出，不能代替电路检查项；未检出也未声明的功能电路由 REQ-Q08 逐个确认。

## 执行流程

大工程分批推进并保留进度，不缩小覆盖范围；身份或图形疑点立即前置。

### 0. 基线与需求

从资料和对话提取功能/量化指标、接口角色与数量、输入范围/负载、温度、降额依据、保留/删除项，
写入 `intent.json`（字段见 [计划与结果台账](references/plan-and-results.md)）：需求原文由
`requirements_extract.py` 从需求文档逐字抄录（`requirement_source` 写文件与 sha256），每条要求只写 REQ ID、类别（规则总表的需求类别表）、对需求的理解（`interpretation`）、从原文读出的数字（`parameters`）、落实它的电路或系统功能（`owners`，可选）和确认状态，判据由类别的审查方面模板生成；资料只写路径（`materials.<名>.path`，文件在即可用），网表上像电源而名字不像轨的网逐条声明成轨或写进 `rail_exclusions`，候选流程下 `features` 只给候选没检出的类别写不适用依据；去耦组由官方脚表逐器件逐供电网推出，只按（位号，网）写用途与条款；装配配置写入 `intent.assemblies`；设 `review_phase`（日常设计 `design_iteration`，
用户明确要冻结才用 `schematic_freeze`）。需求缺失或冲突按 [需求澄清项](references/requirement-clarifications.md)
集中提出，先做不受影响的工作，不逐颗器件打断用户，也不自行接受风险。
录入前按 [需求原文到审查要求](references/requirement-clarifications.md#需求原文到审查要求) 分清确实待定、
客观设计要求、明确排除和下游工作；不能把源文件的 OPEN 标题机械变成责任方待决。
按 [输入与覆盖](references/inputs-and-coverage.md) 记录输入版本/哈希；PDF 与网表须核修订号证明同版。
仅有 PDF 时逐页读图并声明范围，不能声称网表/ERC/逐脚全量通过。缺工具先盘点现有能力，安装须另获授权。

### 1. 解析与完整性

    python3 scripts/parse_netlist.py <allegro目录> -o db.json
    python3 scripts/parse_kicad.py <文件.kicad_sch|kicadxml> -o db.json
    python3 scripts/read_bom.py db.json <BOM.csv>        # 有装配 BOM 时必跑，在生成计划之前

BOM 里每个位号除位号、值以外的列原样进 db，计划把它们挂到功能框架（`bom_specs`）和器件行（`bom_fields`）上：
里面写的器件规格（额定、公差、漏感上限等器件必须满足的值）是设计结果，照用；写在那里的设计方计算值不用。

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
计划按功能树组织，每行恰有一个所属 `owner`：系统功能（电源树、地、监控、上电时序、主控引脚，有对象才生成）→ 功能电路 → 接口 → 全板与文档。
电路级行归电路，按候选编号与工作态识别，不随画法变；器件行归拥有该器件的电路，器件应力、电容和精度每块电路对它拥有的器件问一行，没人拥有的器件归全板一行。
计划的 `interfaces` 列出电路之间、链路、供电轨和连接器四种接口及端点角色，推不出的角色和轨源列为缺口；
接口规则逐接口问（电路对的方向与电平、链路两端电平、供电不同的网络的跨域注入、连接器的对端定义/载流/防护、敏感电路取电轨的噪声）。
系统功能、电路对、链路和连接器各有一个框架，与电路框架一样下功能判定；报告的功能表按系统功能、功能电路、接口分组，每个发现项写所属。
校验覆盖两条：每颗贴装器件恰归一块电路或列在 REQ-Q08 待审清单上，每个接口都有它的行和框架。候选漏了器件不手加：记 REQ-Q08、改规则；
`unassigned` 与 `gaps`（没核验角色的 IC、缺引脚名）先清。
格式见 [计划与结果](references/plan-and-results.md#一intentjsonschema_version-3)，规则见 [自动检查](references/automation.md#二检查器)。

SR 独立审查，只用四类输入：需求、设计结果（原理图、网表、BOM、原理图 PDF）、原厂与标准资料、SR 自己的计算。
设计方的设计报告、设计方案、计算书、选型记录、电气意图、需求追溯、器件约定、开放项、自检与目检记录、交付证据、下游约束
和对前轮意见的回复都不作参考，也不逐条复算其中所称的数值；审查意图（`intent.json`）的出处和结果行的证据引用这些文件时
校验拒收（`independence.py`）。每个数值都由 SR 从原理图、需求和原厂资料自己算。原理图上看不出、只写在设计文档里的事实（固件设定的门限、寄存器配置等），
写成移交项请设计方确认，确认后作为需求或输入进入审查，不直接引用设计文档。

网表扫描后先出资料请求：`python3 scripts/gap_inventory.py review-plan-cold.json --datasheet-audit datasheet-audit.json --md 资料请求.md`，按装配资料、器件资料、需求、图纸分组，每项写涉及位号和能解开的检查条数。把前几项一次发给设计方补齐再进入逐项审查，不要审完才发现几十条检查缺同一份资料；“审查者自行追踪”一组是自己的工作，不向设计方索取。

冷检的 FINDING/CANDIDATE 已各成计划一行，与其他检查一样作答。补齐命名启发式漏掉的对象/工况，登记到 `intent.rule_gaps` 后重新生成计划。排除候选须有反证，无特征不等于 NA。
电路检查项只在网表上有它问的机制时生成（功能框架的 `not_asked` 列出没问的和原因）；计划提示 `CIRCUIT_TYPE_MISFIT` 时换电路类型或不建该电路。
计划行带 `requires` 仍记 NA 的，`applicability_evidence` 写排除它的 `nets`/`pins`；只说“不适用”的通过被拒，改记 NA。
检查器（I²C、去耦、感性负载、功率开关、输入滤波、上电、监控、差分电平、光耦等）每趟都跑；
名称线索只生成待复核候选，清单绑定输入指纹，不能编辑清单消缺口。见 [自动检查](references/automation.md)。
计划命令列出“未声明电压的轨”或“无界节点/跨域”时，先在 `intent.power_rails` 补轨压、节点窗口和参考地分区 `domain`
（由审查者按需求和稳压器/钳位手册自行定界，逐条写 `citation`），再合并扫描；空的 `power_rails` 会让全部阻容预判失效。计划命令列出“阻值读不出的电阻”时当场告诉用户：列出位号和原值，请设计方改成 `阻值[/公差][/额定功率][/额定电压][/封装]` 的写法或确认阻值，不自行猜阻值；未改之前这些电阻的预判和脚电流不算。值后面多一个说不清的词（如 `47R/1%/2W/pulse`）时阻值照读，诊断 `RESISTOR_VALUE_WORD` 只列这个词：它说的要求（抗脉冲能量、额定电压）是特殊要求，写成 BOM 约束，不开“阻值读不出”的待办。见 [通用件定界](references/commodity-floors.md#计划预判dev-c01-逐颗行)。

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
  PDF 提取的关键数值对照渲染页核单位。

### 4. 资料审计与计划合并

    python3 scripts/audit_datasheets.py db.json --datasheet-dir <资料目录> --resolution datasheet-resolution.json --intent intent.json --json datasheet-audit.json
    python3 scripts/lint.py db.json --log netlist.log --intent intent.json --datasheet-audit datasheet-audit.json --merge-plan review-plan-cold.json --plan-json review-plan.json --json lint-hot.json

`review-plan.json` 是唯一最终计划。保证值核对（E）行由网表定出对象，审查者按两端规格书的保证 Min/Max 判定；
资料未 AVAILABLE 时判资料不足，例外见 [保证值核对的例外](references/evidence-proportionality.md#保证值核对的例外)。

### 5. 专家审查：连接追踪（T）、工程计算（C）、条款核对（D）

判断的单位是**功能**，不是检查行。分三小步：

1. **功能判定**：按计划 `functions[]` 的框架逐个填写 `review-results.json` 的 `functions[]`（字段与 F1–F12 见
   [功能判定](references/plan-and-results.md#功能判定functions)）。框架自带问题、检查行、每条规则的盲区和五步核对单；
   审查员读手册和自己的计算，不翻规则书。先列手册里与这个功能有关的条件（`conditions`）：每条写页码/表号/节名或点名的网络、引脚，
   “见 engineering.md”不定位任何东西；再写它是哪种证据（`kind`）：数字限值 NUMERIC_LIMIT（`limit` 的 min/max 与单位、引出这个数、`regime`），
   强制条款 MANDATORY_CLAUSE（引出“必须/不得”句、`applies`；典型应用不算），网表事实 NETLIST_FACT（点名网络或 REF.PIN），
   典型参考 TYPICAL_REFERENCE，工程假设 ENGINEERING_ASSUMPTION；每条判断（`judgements`）至少引一条强制条款或网表事实，数字限值只在余量里比较；
   功能的 `objects` 就是电路（候选经决定）的位号和网络，要扩大先改决定（merge/split）或候选规则，再重生成候选与计划；
   一个电路的缺口和失败写在它自己的功能里（开放项、失败项），别的电路的行用 `open_ref` 指向它；计划电路的行（框架成员）挂到审查员自建的功能上，
   或从自建功能取 `open_ref`/`fail_ref`，校验拒收；跨电路的缺口写在拥有缺失量的框架里，其他框架的行用 `open_ref` 指向它。
   自建功能只装不属于任何框架的行（器件、检查器、全板行），对象（位号）全在某个电路框架里的拒收，改写进那个框架；
   计划漏了电路就在 `intent.circuit_decisions` 登记 add 决定后重生成计划；再算（`calculation`），
   算出余量就按它的依据（`margin.basis.kind`）下结论：保证最坏值 GUARANTEED_BOUND 满足判 PASS，不满足只是没证明；确会出现的工况 REACHABLE_CASE
   不满足判 FAIL；完整最坏范围 EXACT_ENVELOPE 两头都判；估算 ESTIMATE 什么都不判。`comparison` 为 GE 时零余量算满足、GT 时不算；
   与限值的 `regime` 不同要写 `conversion`。证明不满足的余量记失败项且发现项带改法，设计里已有的值不记“设计没定”；
   余量、判断和影响条目不写 `states` 时只覆盖不带状态的行，不覆盖全部状态；
   本设计还没选定的量写成规格（DESIGN_VALUE，`spec`+`owner`，`undecided` 列出没选的器件参数，BOM 已写的不算；由另一个开项决定的写 `depends_on`）；另一阶段欠的交付物（磁件图纸、固件应用能力确认）记
   DELIVERABLE_PENDING（`deliverable`+`owner`+`assumed`）；只有厂家才知道、公开资料界限（保证限值、相邻测试点单调夹出的界限、
   公开特性表、典型曲线加余量、应用笔记公式）也兜不住的参数才记 VENDOR_DATUM，并写查过哪几条、为什么不够、
   公开资料界限下的最坏情况与余量（`worst_case.bound`/`margin`；决定结论的余量写 `basis.derivation` 与 `basis.corners`，器件参数按[工作点定界表](references/bounding-table.md)的推法和公式定界（余量写 `basis.cell`/`method`/`formula`，门禁重算），判定不出界的先用数答 `monotonic_tried`（定界表的格、开着哪一侧、工作点范围、测试点数值，工作点在两个测试点之间就要定界）；没有界就列 `curves_checked`，手册写了这种用法只缺数值的写 `specified_by`（不能是没覆盖工作点的测试点；引典型曲线时写 `typical_estimate`，典型值都不够判失败），没写这种用法的是设计风险，记失败项；厂家参考电路同接法、负载不更重的可判通过）。
   没有数值的方面写 `judgements`（方面、条件、说明了什么）；行只有本方面本状态有证明通过的余量或 judgement 才 PASS，没人判过的方面不默认通过。
   开放项的 `decides` 每条是一条影响条目：方面、状态、`via`（缺的量进到哪条条件或哪个计算输入）和 `rationale`（现有的界为什么不够）；
   一个缺口挡几个方面不限数，超过 3 个只提示复看。
   框架外的功能（intent 没有声明的电路）自己加，同样校验。
   隔离器件的工作资格（PRO-C03）和反馈稳定（PWR-C15）是隔离/变换器功能的方面，在同一个功能判定里写条款与计算。
   文档检查（DOC-*）不是功能电路：文档错误直接在行上判 FAIL 并写 finding，不包成功能。
2. **行派生**：跑 `derive_rows.py`（见第 7 步）；绑定了功能的行不手填，绑定了树上检查的需求行（`bound_checks`）取绑定行中最差的结论，也不手填。
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
- **自己算关键数值**：决定结论的数值由 SR 按原理图、需求和原厂资料自己算，`circuit_bounds.*`（分压、RC 跨阈、线性稳压热、逻辑电平裕量、电容纹波折算、电阻功耗、串阻电流）与 `model_bounds.*` 自行枚举公差角点。不复算设计文档所称的数值，也不拿它当判据。
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
  顶层有其他文件或引用的证据找不到时打包失败。不另写 README 或说明文档；HTML 只能是脚本生成的那份。冻结与后续补充按 [留档](references/inputs-and-coverage.md#留档)。
  公开仓库只放脱敏合成用例。

### 8. 改版复审（H）

网表扫描和合并扫描传同一 `--old-db`、`--old-plan`，与本版 `--merge-plan` 分开；沿变更的供电/控制/保护依赖扩展复验。
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
- 新脚本先在 [架构说明](references/architecture.md#二每个脚本属于哪一环) 归环归类：入口（执行流程里直接调用）、工具（特定情形手动调用）、库（只被导入）。只有入口写进执行流程；新增入口属于架构调整。
- 工程规则身份由 `scripts/review_engine.py` 与 `scripts/skill_identity.py` 计算：算法、常量、受控正文和规范判据变化要求按当前规则重新验证；说明/接口页、入口元数据、测试及 Python 注释变化只做兼容检查。未知规范文件仍按规则处理，不能自行把判据降为说明。
- 规则编号、判据、审查要点归属和功能电路只在 `scripts/catalog.py` 登记，改后运行
  `python3 scripts/catalog.py --write-doc references/check-catalog.md`。来源为“全板通用”“电路检查项”的新规则
  登记后即自动展开；来源为“计划逐对象生成”“Lint 内置”或检查器的规则，还要在计划生成的对应层（电路与器件 `plan_circuits.py`、接口 `interfaces.py`、
  系统功能 `plan_system.py`、全板与覆盖 `plan_board.py`；`plan_review.py` 只做汇总）、`lint.py` 或对应检查器里实现展开/扫描。新增或调整规则先回答 [审查要点中的三个问题](references/review-charter.md#用审查要点指导进化)。
- 测试分两层（[分层定义](scripts/tests/conftest.py)）：每次改动先跑约定测试 `python3 -m pytest scripts/tests -m contract -q`（[规则约定](evals/rule_contracts/README.md)、校验器不变量、解析器，几秒）；新增 A/E/T/V/H 规则须同时加触发板与近似板。措辞层 `-m wording` 是每个台账夹具一份 golden 报告，改报告措辞用 `SR_UPDATE_GOLDEN=1` 重写快照并审读 diff。改规则或检查器后跑[变异门](evals/mutation/README.md) `python3 evals/mutation/run.py --changed`（只跑落在改动文件上的变异，几分钟），提交前或发布前跑全量 `python3 evals/mutation/run.py`；每条变异都要被单元测试杀死。
- 修改脚本后运行 `python3 -m unittest discover -s scripts/tests -q`（全量，含两层）；改导入器时同时跑 [真实来源导入回归](evals/input_bench/README.md)；改 KiCad 解析、自检、日志扫描、去耦清单或计划展开时跑 [KiCad 原生交付回放](evals/kicad_replay_bench/README.md)。改检查器或规则后跑 [典型电路基准](evals/typical_circuits/README.md)（42 块开源板，每条报出都要已归类，新出现的须逐条审读）和 [种子基准](evals/seeded_bench/README.md) 看自动层检出；改定级、汇总、待办或报告逻辑后跑台账回放（schema 3 台账已退役，待一份按功能判定方法冻结的真实审查记录重建）；`python3 evals/bench_coverage.py --seeded <注入基准 results.json>` 列出每条 A 规则在哪个基准有真实板正例、哪些还没有。评测通过不等于任何真实电路审查通过。

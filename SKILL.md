---
name: schematic-review
description: "审查硬件电路原理图的电气合理性和需求符合性，按严重度列出有证据的缺陷、修改建议和复验条件。用于首审、冻结前检查、改版 diff 和历史意见闭环；支持完整网表审查及明确受限的 PDF 审查。不签署 PCB 布局布线、SI/PI、EMC、热设计验收或生产准出。"
---

# 电路原理图系统审查

## 目的

依据当前需求、设计数据和器件保证条件，判断原理图在规定工况下能否实现预期功能；找出有证据的偏离，
给出可执行、可复验的修改建议，支持设计迭代及原理图冻结进入 PCB Layout。
审查按 [七项纲要](references/review-charter.md) 组织：需求与功能、器件与连接、工况功能与性能、
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
7. **守住范围**：准出对象是原理图；PCB、SI/PI、EMC、实测热和生产验证形成 HANDOFF，但原理图能判定的
   电气前提不能推给下游。分流只问一句：拿到这个数，今天能否在原理图上重判？能 → INSUFFICIENT（如实际负载、保护配置未知）；
   只能由样机/PCB/结构/试验产生 → 阶段 NA + HANDOFF，产品要求仍待验证。见 [纯下游验证项](references/verdicts-and-release.md#纯下游验证项)。

## 参考文件

| 何时读 | 文件 |
|---|---|
| 审查目的、七项纲要、规则取舍 | [review-charter.md](references/review-charter.md) |
| 规则编号、判据、功能包 | [check-catalog.md](references/check-catalog.md)（由 `scripts/catalog.py` 生成） |
| 判 NA/INSUFFICIENT、索取资料前 | [evidence-proportionality.md](references/evidence-proportionality.md) |
| BOM 缺具体料号、要给通用件额定定界时 | [commodity-floors.md](references/commodity-floors.md) |
| 结果、P0–P3、阶段、HANDOFF、准出 | [verdicts-and-release.md](references/verdicts-and-release.md) |
| 需求缺失/含糊/冲突 | [requirement-clarifications.md](references/requirement-clarifications.md) |
| intent、计划、结果字段与校验；功能包展开边界（含电平转换） | [plan-and-results.md](references/plan-and-results.md) |
| 跨状态计算、局部/整体主张、父项与任务依赖 | [execution-consistency.md](references/execution-consistency.md) |
| 输入版本、解析、覆盖与留档 | [inputs-and-coverage.md](references/inputs-and-coverage.md) |
| 自动扫描与各检查器 | [automation.md](references/automation.md) |
| 资料补取、证据计算、Vref 复用 | [datasheets.md](references/datasheets.md) |
| 工程计算公式 | [wca-formulas.md](references/wca-formulas.md)；修改建议的计算预检查见 [calculation-preflight.md](references/calculation-preflight.md) |
| 写报告和修改说明 | [report-and-remediation.md](references/report-and-remediation.md) |
| 复审、改版影响 | [revision-review.md](references/revision-review.md) |

## 与 ASG 的有状态工作流交接

参与 ASG/SR 薄控制器流程时，读 [工作流交接合同 v1](references/workflow-handoff.md)。
接收受控 `task.json` 和 ASG 完整交付包；独立取证、复算、建计划和审查，不迁移设计侧的通过结论。
原生 intent/plan/results/gate 与修改任务保持本文格式；用控制器 `pack-result` 自动生成任务与文件绑定。
日常候选沿用当前版本，需求变化、重要电气改版和冻结才建立里程碑；状态查询默认不扫描历史。
控制器复跑原生校验器；有效的 NO_GO 报告用于整改，只有本版冻结审查可支持原理图冻结。
独立使用 SR（包括受限 PDF 审查）不依赖控制器；不得伪造网表来满足完整 ASG 交接合同。

## 规则编号

检查编号为 `内容域-方式序号`，如 `PWR-E01`（电源域的证据计算）。
内容域：DOC 图纸与数据、DEV 器件与引脚、NET 网络连接、PWR 电源、RST 启动与复位、CLK 时钟、
SIG 接口与信号、ANA 模拟与监测、PRO 防护与隔离、DRV 功率驱动、REQ 需求与闭环。
方式：A 自动扫描、E 证据计算、T 连接追踪、C 工程计算、D 条款核对、V 图面目检、Q 覆盖审计、H 版本比对。
补查项也从总表选规则，ID 写成 `规则编号.自定义键`。

功能包（DDR、USB、电源保护等）在声明或拓扑确认后展开成员规则：把实际电路填入 `intent.circuits`
（`type` 取包名）即逐电路×工况展开。REQ-Q07 只汇总，不能代替成员检查；未检出也未声明的功能包由 REQ-Q08 逐个确认。

## 执行流程

大工程分批推进并保留进度，不缩小覆盖范围；身份或图形疑点立即前置。

### 0. 基线与需求

从资料和对话提取功能/量化指标、接口角色与数量、输入范围/负载、温度、降额依据、保留/删除项，
写入 `intent.json`（字段见 [计划与结果台账](references/plan-and-results.md)）：每条要求有稳定 REQ ID、
判据和确认状态；装配配置写入 `intent.assemblies`；设 `review_phase`（日常设计 `design_iteration`，
用户明确要冻结才用 `schematic_freeze`）。需求缺失或冲突按 [需求澄清项](references/requirement-clarifications.md)
集中提出，先做不受影响的工作，不逐颗器件打断用户，也不自行接受风险。
录入前按 [源条目到审查义务](references/requirement-clarifications.md#源条目到审查义务) 分清真实待决、
客观设计义务、明确排除和下游工作；不能把源文件的 OPEN 标题机械变成责任方待决。
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

### 2. 冷跑：自动扫描与计划

    python3 scripts/lint.py db.json --log netlist.log --intent intent.json --plan-json review-plan-cold.json --json lint-cold.json

交付含计算库存、preflight 与 README/报告摘要时，冷跑另执行 [派生摘要核对](references/document-summaries.md)；
热跑及报告定稿后用最终文件重放，候选按 DOC-Q01 单独入计划，不迁移局部输入资格 PASS。

冷跑后先出资料请求：`python3 scripts/gap_inventory.py review-plan-cold.json --datasheet-audit datasheet-audit.json --md 资料请求.md`，按装配资料、器件资料、需求、图纸分组，每项写涉及位号和能解开的检查条数。把前几项一次发给设计方补齐再进入逐项审查，不要审完才发现几十条检查缺同一份资料；“审查者自行追踪”一组是自己的工作，不向设计方索取。

补齐命名启发式漏掉的对象/需求/工况，审查者补查项加入 `review-plan-cold.json`。排除候选须有反证，无特征不等于 NA。
检查器（I²C、去耦、感性负载、功率开关、输入滤波、上电、监控、差分电平、光耦等）每趟都跑；
名称线索只生成待复核候选，清单绑定输入指纹，不能编辑清单消缺口。见 [自动检查](references/automation.md)。
计划命令列出“未声明电压的轨”或“无界节点/跨域”时，先在 `intent.power_rails` 补轨压、节点窗口和参考域 `domain`
（由审查者按需求、稳压器/钳位手册和设计计算书自行定界，逐条写 `citation`），再热跑；空的 `power_rails` 会让全部阻容预判失效。见 [通用件定界](references/commodity-floors.md#计划预判dev-c01-逐颗行)。

### 3. 资料取证与器件身份（DEV-D01、DEV-D02）

    python3 scripts/audit_datasheets.py db.json --datasheet-dir <资料目录> --json datasheet-audit.json

- 先核 MPN、封装/温度/档位与 BOM/符号；关键采样电阻、保护/安规件、储能电容和磁件也按原厂订货表核对
  阻值/容量/耐压组合，不把系列范围当具体后缀的可订购范围。候选不代表身份成立。
- PART/VALUE 冲突或图面/BOM 与链接资料矛盾时，按 [身份冲突与身份分支](references/evidence-proportionality.md#身份冲突与身份分支)
  处理：不一致本身判 DEV-D04 FAIL，电气判据逐分支给条件结论，全部分支都违反才判电气 FAIL。
- 按实际用途读引脚、额定/推荐条件、相关 min/max、模式和 errata；“官方物理脚”指手册引脚定义的编号或名称，
  焊盘映射属于 PCB 阶段。核过的脚表写入 `intent.devices`，DEV-D02 差集和 DEV-D05 引脚处置据此列出。
- AI 已逐端核对的器件角色和电源/返回分组按 [可复用声明](references/reviewed-declarations.md) 保存来源与输入指纹；
  下次先验证声明，输入变化则重新核对，不能只刷新摘要。`manual_*` 兼容字段不代表人员确认，核对者身份须如实记录。
- 资料缺失时按 [器件资料](references/datasheets.md) 补取（先 LCSC/立创，再原厂），仍取不到按逐参数补证；
  PDF 提取的关键数值对照渲染页核单位。证据计算所需保证值整理成 `evidence.json`。

### 4. 热跑：证据计算

    python3 scripts/audit_datasheets.py db.json --datasheet-dir <资料目录> --resolution datasheet-resolution.json --evidence evidence.json --intent intent.json --json datasheet-audit.json
    python3 scripts/lint.py db.json --log netlist.log --intent intent.json --evidence evidence.json --datasheet-audit datasheet-audit.json --merge-plan review-plan-cold.json --plan-json review-plan.json --json lint-hot.json

`review-plan.json` 是唯一最终计划。自动 E 只覆盖输入的具体对象；资料未 AVAILABLE、指纹过期或模型缺失时保持证据不足，
例外见 [自动证据计算的例外](references/evidence-proportionality.md#自动证据计算的例外)。

### 5. 专家审查：连接追踪（T）、工程计算（C）、条款核对（D）

按 PWR → RST → CLK → SIG → ANA → PRO → DRV 推进，每条规则逐对象、逐状态给结果；全板项逐条给适用性和结果。
功能包按实际 package/circuit/state/ref 归组并列必需成员 ID，跨包依赖说明真实路径；不能只按规则编号归组。
隔离器件能否用于实际工作条件、电源反馈是否稳定，按[隔离器件与电源反馈的检查要求](references/closure-obligations.md)记录。报告直接写器件或环路“缺什么、怎么补、怎样算通过”；同一对象、同一补充动作和通过标准可合并，不同环路保留各自标准。
按 [功能包依赖与状态核对](references/plan-and-results.md#功能包依赖与状态核对) 核全部实际成员、外围选值窗口与掉电路径。
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
- **复算设计给出的数值**：设计计算书、配置表、报告里决定结论的数值，逐条写成 claim（出处、`calc.py` 计算名、带出处的输入、所称结果）用 `python3 scripts/calc_claims.py claims.json --json evidence/calc-claims.json` 复算；`circuit_bounds.*`（分压、RC 跨阈、线性稳压热、逻辑电平裕量、电容纹波折算、电阻功耗、串阻电流）与 `model_bounds.*` 自行枚举公差角点。MISMATCH 是文档错误候选，读原文确认后才入 DOC-Q01/相关检查；合同格式有效不等于模型正确。
- **核对模型和原表**：CrM Boost 输出电容用 `model_bounds.crm_boost_capacitor_ripple` 独立核二极管导通相位，并按控制器实际母线模式分别算；不沿用设计脚本的公式证明自身。厂家参数引用用 `audit_parameter_claims.py` 对比独立摘录的原表，给料号/材料、文档哈希、页码、温度/激励条件、典型或保证值口径；工程设计限值另核裕量，不能当厂家额定值引用。工具不代替原表摘录核实，详见 [自动检查](references/automation.md)。
- **动态数值证据**：需要有界 R/C 工作点或瞬态时按 [仿真证据](references/simulation-evidence.md)；样本在窗口内不直接等于规则 PASS。
- **条款核对**：每颗 IC/模组核推荐工作条件（DEV-C05）和逐脚处置（DEV-D05）；连接器核对端定义（DEV-D03）和对外防护（PRO-D03）；
  主控引脚复用对照平台约束与固件配置（SIG-D13）。由参考设计派生的电路列出全部偏离并按本设计条件复核。

### 6. 图面目检（V）

所有页面留目检记录（DOC-V01），新页和变更区细读；极性、pin1/视图、选项表、同名端、NC 标记以图形为证据。
注释、遗留命名和图框版本按 DOC-V02，装配选项互斥与完整性按 DOC-T01。

### 7. 结果、报告与校验

结果独立保存为 `review-results.json`，绑定最终计划；批量脚本只录入已审结论。按有证据的共同根因归并任务，
不合并独立电气结论。局部额定/寿命缺口用同规则 `split_out` 定位到实际对象；保留其余对象的已核范围，
不为降低条数合并独立电源级或补证动作。复合检查涉及多个任务时用 [任务归属](references/verdicts-and-release.md#共同根因归并为任务)
的 `workflow_version: 2` 精确分配补证键和各自风险，整体仍保留最高后果。录入前按 [逐行语义复核](references/plan-and-results.md#逐行语义复核) 逐行核对象、路径、因果、
关闭范围和需求子义务（含多个子义务的需求只有全部适用子义务通过才 PASS）；绑定校验及质量筛查零提示不能代替这一步。
证据不足先按 [下游分流](references/verdicts-and-release.md#纯下游验证项) 分开样机/试验结果、优化目标和真实设计缺口；
批量脚本不能用一句固定兜底语给全部证据不足定级。
完成后对账：

    python3 scripts/validate_review.py review-plan.json review-results.json --db db.json --lint lint-cold.json --lint lint-hot.json --require-actionable --require-bindings --json review-gate.json

- 执行审计（`--execution-audit`）是可选自检，不是交付门槛；用法见 [执行一致性](references/execution-consistency.md#可选的机器自检)。
- `valid` 只表示记录可对账；`quality_screening` 是疑点提示，确有错配才改结论。零提示不证明审完。
- 已有资料尚未读算的项记 REVIEW_INCOMPLETE，本轮自己读算完；审查未完成时只交进度，`pack_review.py` 拒绝打包。
  只剩 SR 工具自身限制、审查时已对照网表和原厂资料核对完的，按核对结论判定并写 `manual_verification`，不记 REVIEW_INCOMPLETE。
- 进报告的文字（任务、finding、handoff、notes）用白话，不用 [写法要求](references/report-and-remediation.md) 列出的词；
  `pack_review.py` 会检查。
- 冻结时加 `--require-release`；非冻结阶段 `release` 不是总判定。
- **交付只有两样**：项目审查目录顶层只放 `审查报告.md` 和 `record/`，其余中间文件留在工作目录。
  报告由脚本从台账生成，agent 只在 `notes.json` 里补白话说明（格式见 [报告与修改说明](references/report-and-remediation.md)）：

      python3 scripts/render_report.py review-plan.json review-results.json review-gate.json --notes notes.json -o <审查目录>/审查报告.md
      python3 scripts/pack_review.py <审查目录> --review-plan … --review-results … --review-gate … --db … --intent … \
        --lint-cold … --lint-hot … --evidence-root <工作目录> --input schematic=<工程> --input requirements=<需求> …

  默认简洁报告保留全部缺陷、任务、通过标准及计数，逐项依据链接到台账；需逐条展开时加 `--detail full`，不手改报告或删检查来缩短输出。
  `pack_review.py` 只复制结论引用的证据；原理图工程、手册、需求、旧审查按路径和 SHA-256 记入 `record/manifest.json`。绝对引用只核声明输入，不拼入归档路径；本轮证据用 `--evidence-root` 内的安全相对路径（优先于输入里同名的旧文件），不允许 `..` 或符号链接越界。打包成功前逐个重读 packed 路径和 SHA-256；报告相对链接须都能打开。
  顶层有其他文件或引用的证据找不到时打包失败。不另写 README、说明文档或 HTML。冻结与后续补充按 [留档](references/inputs-and-coverage.md#留档)。
  公开仓库只放脱敏合成用例。

### 8. 改版复审（H）

冷/热跑传同一 `--old-db`、`--old-plan`，与本版 `--merge-plan` 分开；沿变更的供电/控制/保护依赖扩展复验。
保留每个历史 ID，区分撤回、复发、接受、已修复；断言要证明期望的电气状态，“字段变了”不足以关闭（REQ-H01）；
旧项消失须独立处置（REQ-H02）。`reuse_candidate` 只推荐核对已有记录，不能盲迁旧 PASS。
最终校验传相同旧基线并加 `--require-revision-impact`。见 [改版复审](references/revision-review.md)。

    python3 scripts/diff_netlists.py old-db.json db.json --claims review-claims.json --json diff.json --fail-on-open-claims

## 规则维护

- 工程规则身份由 `scripts/review_engine.py` 与 `scripts/skill_identity.py` 计算：算法、常量、受控正文和规范判据变化要求按当前规则重新验证；说明/接口页、入口元数据、测试及 Python 注释变化只做兼容检查。未知规范文件仍按规则处理，不能自行把判据降为说明。
- 规则编号、判据、纲要归属和功能包只在 `scripts/catalog.py` 登记，改后运行
  `python3 scripts/catalog.py --write-doc references/check-catalog.md`。来源为“全板通用”“功能包成员”的新规则
  登记后即自动展开；来源为“计划逐对象生成”“Lint 内置”或检查器的规则，还要在 `plan_review.py`、`lint.py`
  或对应检查器里实现展开/扫描。新增或调整规则先回答 [纲要中的三个问题](references/review-charter.md#用纲要指导进化)。
- 修改脚本后运行 `python3 -m unittest discover -s scripts/tests -q`，必要时按
  [电路评测说明](evals/circuit_bench/README.md) 跑冻结基准；改导入器时同时跑 [真实来源导入回归](evals/input_bench/README.md)；改 KiCad 解析、自检、日志扫描、去耦清单或计划展开时跑 [KiCad 原生交付回放](evals/kicad_replay_bench/README.md)。改检查器或规则后跑 [典型电路基准](evals/typical_circuits/README.md)（42 块开源板，每条报出都要已归类，新出现的须逐条审读）和 [种子基准](evals/seeded_bench/README.md) 看自动层检出；审查方法的合成评价在 `evals/workflow_guidance/`、`evals/scenarios/`。评测通过不等于任何真实电路审查通过。

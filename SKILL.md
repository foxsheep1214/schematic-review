---
name: schematic-review
description: "审查硬件电路原理图的电气合理性和需求符合性，按严重度列出有证据的缺陷、修改建议和复验条件。用于首审、冻结前检查、改版 diff 和历史意见闭环；支持完整网表审查及明确受限的 PDF 审查。不签署 PCB 布局布线、SI/PI、EMC、热设计验收或生产准出。"
---

# 电路原理图系统审查

## 目的与纲要

依据当前需求、设计数据和器件保证条件，判断原理图在规定工况下能否实现预期功能，
识别有证据的偏离并给出可执行、可复验的修改建议，支持设计迭代及原理图冻结进入 PCB Layout。
按 [SR 审查纲要](references/review-charter.md) 对齐七项：需求与功能、器件与连接、工况功能与性能、
参数裕量与应力、保护与异常响应、实施与下游约束、证据覆盖、改进建议与复验闭环。
规则总表为每条规则标明主纲要。维护规则先核对目的和适用范围，优先消除误判、漏检和重复工作；
不以增加规则或台账数量为进步，不以找到几项严重问题为由停止其余适用审查。

所有不通过项均须明确改进建议和复验条件；证据不足项给补证/设计路径，具体要求见纲要，不止于报错。

## 判定纪律

1. **设计事实与判据分开**：当前网表/BOM/图面证明实际连接和贴装；适用版本的官方
   datasheet、errata、接口规范和受控需求证明应当怎样。矛盾时查版本、变体及适用条件，
   不能用一个总优先级覆盖另一种证据。历史报告与 demo 只作线索。
2. **证据落实到主张**：每项给页码、位号/物理脚号、网络及可定位出处。确认“不满足保证
   边界”不等于确认“实物必然失效”；未知后果单列，不得降低已经证实的违规。
3. **逐项覆盖**：需求、全部页面、器件/物理脚、电源轨、每路接口、检测/使能链、装配选项、
   运行状态及历史意见均有台账。按功能识别关键器件，不能只查 U 前缀。
   READY、某条规则执行过一次、零命中都不表示完成。
4. **新手能按步骤修改**：每项发现按 [remediation-guide.md](references/remediation-guide.md)
   给修改准备度、定位、旧→新、顺序操作、参数依据和明确的通过标准。连线写到物理脚，
   明确哪些旧连接要断开；新增件给两端接法和规格，不能止于“加上拉/加保护/参考手册”。
   缺输入时给取得方法、计算/选择步骤及条件方案，不编造精确料号/阻值或空闲 GPIO。

## 适用性与证据尺度

生成计划和提出补证前读 [适用性与最小充分证据](references/evidence-proportionality.md)。
先核实际用途/模式/状态，再选择模型；名称命中只作候选。只索取会改变本条判断的缺口，
先完成已有资料支持的阅读和计算。区分真实缺资料、设计未定、审查未完成和后续设计任务。
模块本体、完整系统及制造核准的范围分别按该页确认；公开资料不全本身不是扩大审查范围的理由。
全温保证值直接复用，窄连接判据不承担完整应力/实测证明，软目标不自动成为 P1 硬门槛。
交付前逐条复核 INSUFFICIENT 的必要性；正文明确“移交后续设计”的输入、约束和关闭阶段。
热相关检查限于损耗、额定值、温度等级/参数保证条件、适用 SOA 及温度检测/保护的电气实现；输出散热约束，实际结温、
板上温升和散热实现按 [热相关审查边界](references/scope-boundary.md#热相关审查边界) 移交。
新计划不把这些下游验证混入原理图 PASS/FAIL 判据；缺热仿真/实测本身不生成电气缺陷或待核项。
判 INSUFFICIENT 前先在适用模型内计算和定界，记录外推范围、不利方向及误差/裕量依据。
足以支持本条判据的推导可判 PASS/FAIL(B)；模型不确定性可能改变结论时保留具体缺口。
保守上界越限本身不证明实际超限；区分已证实违反、明确保证要求未满足和尚不能排除超限，详见适用性与最小充分证据。
原定资料取不到时，按最小充分证据中的“逐参数补证与替代”：同型号其他原厂资料、受控规格、
反算要求、相似器件参考、实测或换件。逐参数区分事实与假设；仍影响结论的缺口保留待核，
相似资料不改变原器件资料覆盖状态或自动 E 的保证值门槛。

## 规则编号

全部检查按 [规则总表](references/check-catalog.md) 编号，格式为 `内容域-方式序号`，如 `PWR-E01`：

- **内容域（查什么）**：DOC 图纸与数据、DEV 器件与引脚、NET 网络连接、PWR 电源、RST 启动与复位、
  CLK 时钟、SIG 接口与信号、ANA 模拟与监测、PRO 防护与隔离、DRV 功率驱动、REQ 需求与闭环。
- **方式（怎么查）**：A 自动扫描、E 证据计算、T 连接追踪、C 工程计算、D 条款核对、V 图面目检、
  Q 覆盖审计、H 版本比对。

计划项 ID 以规则编号开头，并带与总表一致的 `rule`/`method`/`domain` 字段。计划按总表“来源”列
生成全部规则：全板通用规则每板一项，功能包成员随功能包展开，器件与连接器逐位号展开；审查者补查
时也从总表选用规则编号，ID 写成 `规则编号.自定义键`。规则只在 `scripts/catalog.py` 登记，总表中的
表格由它生成。编号发布后不改不复用：合并掉的编号列在总表“已废弃编号”，按“改用”列换成在用规则。
AC0、ER1～ER7、Rule-NN 与检查器前缀早已废弃，用旧编号生成的计划和证据须重新生成。

## 结果与分级

先读 [severity-calibration.md](references/severity-calibration.md)，统一使用其中的 P0–P3
分级、A/B/C 置信度和准出政策；机器字段见 [review-results-schema.md](references/review-results-schema.md)。
结果为 PASS / FAIL / INSUFFICIENT / NA；缺陷、潜在后果、关闭状态和 HANDOFF 分开记录。
待核项不能计入已确认缺陷，PASS/FAIL 不得以 C 为依据，P0 不能通过接受风险放行。
需求澄清是独立问题类别，按 [需求澄清项](references/requirement-clarifications.md) 记录唯一决定、
责任方、关闭条件和冻结影响；受影响检查仍用 INSUFFICIENT，不套电气缺陷等级。

## 审查阶段与任务归并

按 [设计迭代与关闭阶段](references/design-iteration.md) 设置 `intent.review_phase`：
日常设计/修改用 `design_iteration`，明确要求冻结时用 `schematic_freeze`，样机证据回流用
`prototype_verification`。它独立于首审/复审模式和冷跑/热跑的执行方式。
正文按实际阶段报告电气结论及本轮处理事项；只有申请冻结时才以冻结准出作总判定，不能用工具保留的 NO_GO 代替模块校准结论。记录校验作为内部工具检查，不另列一套“审查通过”。
不要把所有缺资料项批量定为 P1/本轮阻断，也不要通过降低严重度掩盖真实问题。

新分阶段结果用 `workflow_version: 1`、`work_items` 将电气 FAIL/其他 INSUFFICIENT 按有证据的共同根因
关联到一次补证/修改任务，标注关闭阶段。正文展示唯一任务与受影响检查数，完整逐项结果留在台账。
只有文字相似、同一器件或同一本手册不构成共同根因；不把一组缺项整体改成 PASS。

## 规则演进与本轮证据

新增或调整规则先按 [纲要中的进化准则](references/review-charter.md#用纲要指导进化) 说明其价值、适用条件和验证方式。

按 [规则演进与计算预检查](references/review-evolution.md) 执行：SR 规则指纹变化或旧版无指纹时，
以当前输入重新生成并完整审查；旧结果仅作历史线索，不批量沿用 PASS/INSUFFICIENT。
当前修改建议先校验计算条件和连带影响。正文分别展示当前检查、历史处置、唯一问题/任务和移交项。

## 执行流程

阶段按检查方式排列：冷跑执行 A，热跑再加 E，随后专家审查执行 T/C/D，图面目检 V、覆盖审计 Q，
复审另做版本比对 H（阶段表见规则总表）。保持依赖顺序，身份/图形疑点立即前置。
大工程分批继续并保留进度，不缩小覆盖范围。
经声明或拓扑确认的功能包（总表“功能包”）展开成员规则，逐成员再核适用性；纯名称候选先确认：把实际电路和适用状态填入
`intent.circuits`（`type` 取功能包名）即逐电路×工况展开，未声明电路时按功能包展开一次。
功能包汇总项（REQ-Q07）不能代替成员检查；未检出也未声明的功能包汇总到 REQ-Q08 逐个确认。
来源、条件导通和逐轨预算格式见 review-plan-schema。

### 0. 基线、需求、工况

从资料和对话提取功能/量化指标、接口角色/数量、输入范围/负载、温度、降额依据、保留/
删除项和不可改动项。写入 `intent.json`（`schema_version` 为 3），每条要求有稳定 REQ ID、
验收判据及关联电路。冲突/缺失标出，先做独立工作；允许集中提出关键缺口，不逐颗器件打断用户，
不自行接受风险。

按 [coverage-protocol.md](references/coverage-protocol.md) 建输入版本/哈希、装配配置和覆盖台账。
装配配置逐个写入 `intent.assemblies`（贴装、跳线与出处），全部检查器和 DOC-T01 共用这一份；
声明装配或器件脚表时意图须带顶层 `input_sha256` 绑定本版网表。
PDF 与网表时间接近不能证明同版，需核修订号和关键改动。仅 PDF 时逐页读图并声明范围，
不能声称网表/ERC/逐脚全量通过。缺工具先盘点现有能力，安装另获授权。

### 1. 解析与完整性

    python3 scripts/parse_netlist.py <allegro目录> -o db.json
    python3 scripts/parse_kicad.py <文件.kicad_sch|kicadxml> -o db.json

随附解析器实现 Cadence/OrCAD 三件套与 KiCad 网表（kicadxml）；其他 EDA 需生成同契约索引
并验证适配器。KiCad 输入把 No-connect 属性、真悬空引脚与 DNP 不贴分开记：声明 NC 的引脚
进伪网络并列入 `no_connect_nodes`，无标记的悬空引脚保持真实单节点网由 NET-A01 扫出，
`nc` 只认 dnp 属性或 VALUE 上的 NC 标记（`exclude_from_bom` 不是装配证据）。
读 [netlist-parsing.md](references/netlist-parsing.md)：核对重复归网、缺失 primitive、索引互反、
符号声明引脚和网表实有引脚。解析率不等于官方封装覆盖率；对官方 pinout 双向做差集（DEV-D02），
包括网表完全不存在的脚、EP、隐藏电源和多单元符号。
KiCad 的无名称 passive/free/no_connect 引脚按原生电气类型检查，不套用全板名称覆盖率；
功能脚缺名、类型缺失/未知和拓扑不完整仍报错，不能补造功能名来通过解析。

读导出日志；导出中止/错误（DOC-A01）先隔离为输入阻断，残留三件套不能证明当前版本有效。
NC 汇集伪网、No-connect 属性、DNP 不贴是三件事。`nc` 是解析标记，仍需核装配 BOM/
选项表；不贴串联通路视为断开，多配置分别分析。
逐页提取 PDF 文本，建 PDF 页码/页名/网表路径映射；错位、旋转、极性不清立即渲染局部，
放大至可辨，DPI 数字本身不构成方向证据。

### 2. 冷跑：自动扫描（A）与计划

    python3 scripts/lint.py db.json --log netlist.log --intent intent.json --plan-json review-plan-cold.json --json lint-cold.json

读 [review-plan-schema.md](references/review-plan-schema.md) 和 [auto-checks.md](references/auto-checks.md)。
补齐命名启发式未发现的对象/需求/工况。排除候选须有反证；无特征不等于 NA。
人工补查项加入 review-plan-cold.json；保留 lint-cold.json 中的原始快照。适用性变更记出处。

检查器注册表每趟都跑，读 [检查器契约](references/checkers.md)：识别依据分声明/拓扑/名称线索
三级，名称线索只生成待核项；清单绑输入指纹，改了输入要重新生成，不能编辑清单消缺口。
`--i2c-topology-json`、`--decoupling-json` 与通用 `--checker-json <id>=out.json` 可另存清单。

I²C（`intent.i2c_topology`，装配状态取 `intent.assemblies`）：只跨已确认贴装的两脚电阻和闭合跳线找远端上拉，串阻保留节点，
有源器件两侧不合并；名称、`nc=false`、默认 Bridged 都不是状态证据；外接模块未知或路径未覆盖
保持待核，连接覆盖（SIG-T02）不等于 SIG-E01 或 SIG-C01 电气通过。

去耦（`intent.decoupling` 分组 + `intent.devices` 脚表）：补完整官方脚表、分组/返回节点与逐状态装配；零电容、未知容量和
未连物理脚都要登记；不跨 0Ω/磁珠合并，不以同网共享或标称总容量证明本地去耦/有效容量合格，
位置与回路另交 PCB HANDOFF。

物料与引脚扫描（`scripts/board_scans.py`）按 BOM 值和引脚名判别电容耐压（DEV-A01）、极性电容
方向（DEV-A02）、LED 限流（DEV-A03）、声明输入脚悬空（NET-A07）与未标注位号（DOC-A04）：
轨压来自网名推断，降额与驱动方式仍按项目资料定判。

其余检查器（感性负载钳位、功率开关、输入滤波、上电使能与压差、监控看门狗、差分电平、光耦）
的规则见总表“来源”列。自动扫描只按连接关系报疑点，引脚角色缺失就只留缺口；证据计算规则
PWR-E02、PWR-E03、RST-E03、SIG-E02、PRO-E01、DRV-E01 只在各自适用模型内用带出处的保证值。
适用但缺必要参数时为 INSUFFICIENT；不适用模型改查实际电路。体电容比值与 CTR 寿命
衰减等系数不擅自默认；没有此类项目要求时不把模板系数当成通用验收条件。
DEV-E02 用资料保证的推荐工作电压窗口对照 `intent.power_rails` 的设计范围，缺一边保持待核。

### 3. 资料取证与器件身份（DEV-D01、DEV-D02）

先核 MPN、封装/温度/固定可调档、BOM/符号。关键采样电阻、保护/安规件、储能电容及磁件也须核对原厂订货表中的型号与阻值/容量/耐压组合；跨行或合并单元格按完整子型号对应行核对，不把系列总范围当成具体后缀的可订购范围；标为候选不代表身份已经成立。自动计划未展开的关键无源件补用 DEV-D01，不另造编号。PDF 文本提取会错字符（µ 显示成 m 等），
决定结论的数值对照渲染页核单位。PART/VALUE 冲突时建立身份分支，
可按 VALUE 候选继续分析，不得认定其为实际物料。一个可信原厂文档可确认器件类别，
库名和商城转引同一 PDF 不算两个独立证据；身份冲突必须解决。

按本器件实际用途读支持判据的章节：引脚、额定/推荐条件、相关电气 min/max、状态/模式、
应用计算及 errata；身份核订货变体。阅读记录可按文档集中复用，不为每条检查重复抄写。
“官方物理脚”指手册引脚定义给出的编号或名称；手册只按名称标注（如 Power 封装的 G/S1/S2/D）时，名称表就是完整的官方脚表。
焊盘编号、封装外形图和符号到封装焊盘的映射属于封装绑定与 PCB 阶段，移交下游，不作为原理图缺口。
核对过的官方物理脚表写入 `intent.devices`（准确 MPN/封装、逐脚名称与角色、出处），
DEV-D02 的双向差集与 DEV-D05 的引脚处置据此列出待核脚，去耦分组也用同一份脚表。
不能只读 Abs Max 或只追自动扫描命中的器件。按
[datasheet-resolution-schema.md](references/datasheet-resolution-schema.md) 先审资料包，
只有判据确需而当前资料包缺失时才补取，优先原厂、必要时用 LCSC/立创定位；核对 PDF 身份并记录结果。
搜索摘要/聚合参数只作线索；兄弟型号按逐参数替代流程使用。系列手册须订货表覆盖后缀，
不能仅凭文件名或相似资料判 AVAILABLE。

    python3 scripts/audit_datasheets.py db.json --datasheet-dir <资料目录> --json datasheet-audit.json

资料核对/补取完成并写出 `datasheet-resolution.json` 后，把证据计算需要的保证值整理成
`evidence.json`（`schema_version` 为 2，`rule` 取总表中方式为 E 的规则），格式见
[datasheet-evidence-schema.md](references/datasheet-evidence-schema.md)。
分立半导体（Q/D/ZD/TVS）的器件类型按手册填 `intent.device_kinds`（页码＋原文），由 `--intent` 核验原文后才进入分析，
见 [检查器](references/checkers.md)“器件类型以原厂手册为准”；未声明的器件，审计会给出首页候选类型供核对。
PWR-E01 需要复用已核对的 Vref 时，按 [Vref 参数复用](references/datasheet-facts-schema.md)
把事实保存在项目内，明确精确 MPN/封装和本次完整工况，先物化为 evidence 再热跑。
事实与电路结论分开；过期、条件不覆盖或多条适用保证均待核，不以 typ/置信度代替保证值。

### 4. 热跑：证据计算（E）

    python3 scripts/audit_datasheets.py db.json --datasheet-dir <资料目录> --resolution datasheet-resolution.json --evidence evidence.json --intent intent.json --json datasheet-audit.json
    python3 scripts/lint.py db.json --log netlist.log --intent intent.json --evidence evidence.json --datasheet-audit datasheet-audit.json --merge-plan review-plan-cold.json --plan-json review-plan.json --json lint-hot.json

自动结果只覆盖输入的具体对象与判据，未覆盖实例仍待查。证据须绑定当前网表/物料、装配及状态、
文档内容指纹；关键 R/C/L/F/Y/J 的参数按需纳入依赖。资料未 AVAILABLE、指纹过期、
公差/负载/采样模型缺失时，自动 E 的计划和执行均保持待核；人工 T/C/D 按具体主张另核证据。
合并后的 review-plan.json 是唯一最终计划：
保留冷计划和人工补查项，证据计算按状态展开子项。结果独立填写，旧结果不能自动传给新子项；
新增人工项继续加入最终计划。跨网表版本的旧计划不能自动合并，迁移规则见 review-plan-schema。

### 5. 专家审查：连接追踪（T）、工程计算（C）、条款核对（D）

按内容域推进（PWR → RST → CLK → SIG → ANA → PRO → DRV），每条规则逐对象、逐状态给结果。
全板通用项（对象为 `board`）逐条给适用性和结果，不适用须有依据；平台指南/checklist
拆成有出处的规则实例与下游约束，记录项见总表“方式要点”中的 D。

**电源与状态（PWR、RST）**：每轨追到真正电源引脚/明确外部源，再到全部负载（PWR-T01）；
0Ω/磁珠/二极管不是独立电源。按装配状态、开关/体二极管方向、EN/PG、时序和地参考分析。
核输入/输出/IO 电压与负载 min/max、峰值和启动预算（PWR-C01）；裕量取项目依据，缺负载不写 PASS。
建立断电、启动/复位、运行、待机、掉电/棕断、热插拔及需求内故障状态表。
跨轨上拉先列候选，再查 Ioff/注入限流/掉电容忍，跨轨不等于反灌（SIG-C08）。
检测点须匹配被测量（ANA-T01）：输入存在/申请电压可取源侧，输出有效/负载保护可取负载侧；
检查“采样→判断→使能→供电”的循环依赖。地网逐个列出，核连接点位置与方式（PWR-T06）。
复位期间和固件接管前的 IO 默认态不得误动作继电器、电源使能与驱动器（RST-T04）。

**连接追踪（T）**：逐跳记录起点物理脚→网络→已贴器件→网络→终点物理脚，同时核返回路径/参考地。
全部端口、时钟、复位、启动、编程救援、反馈/检测、使能/故障上报都要追。
TX/RX、P/N、Host/Device、Source/Sink 按两端官方语义复述，查对端连接器视图/线缆针序（SIG-T04）。
连通只证明导电路径，不证明带宽、逻辑极性或启动后能工作。

**工程计算（C）**：读 [wca-formulas.md](references/wca-formulas.md)。先确认模型（固定/可调、内置反馈、
负载效应），再代入实际串并联、输入/温度/负载、公差区间。`scripts/solve_dividers.py` CLI 用于探索；
PWR-E01 对已完整建模的共享支路可做有界线性节点分析，范围与角点限制见 wca-formulas。
不支持、超限或缺公差仍未判定；轨名电压仅为检索线索。
证据计算的分压模型明确源端、参考地、输入偏置及忽略支路依据；逻辑脚用采样窗口的保证电压
比较 VIH/VIL，单个上拉存在不能代替电平、时序和掉电状态验算。
区分设定目标与物理可达输出：LDO 的 FB 公式不代表升压能力；ADC FSR 不等于引脚耐压；
I²C 并联上拉须算等效值、VOL/IOL、上升时间；RC 不等于复位脉宽；有 TVS 不等于防护通过。
逻辑电平与驱动（SIG-C07）、时序裕量（SIG-C09）和敏感负载的纹波预算（PWR-C14）按适用的边界计算；
原厂已覆盖工况的 Min/Max 直接使用。关断/保护状态按其应达状态查，不要求正常调节性能。
连续可调输出（PPS/AVS、宽输入）在整个范围扫描应力和线性损耗，极值常在两路供电交接点，只核端点不能判 PASS。
判“缺保护”前先计入路径上 IC 自带的保护及其门限、延时；门限由寄存器设定的归固件任务。
改频率/阻值/保护管时复算 min on-time、电感、环路、掉电和额定值，不能只修一个数字。

**条款核对（D）**：关键 IC/模组/保护/接口器件核物理脚号与封装。每颗 IC/模组核推荐工作条件
（DEV-C05）和逐脚处置（DEV-D05，含未用脚）；连接器核对端定义（DEV-D03）、未用针与对外防护
（PRO-D03）；主控引脚复用对照平台约束与固件配置（SIG-D13）。沿用库只有同一 MPN/封装/
符号版本的验证记录才可复用（DEV-D04）；demo 一致不证明需求/贴装正确。
电路由参考设计派生时，列出全部偏离（拓扑或抽头改接、器件额定降低、控制器替换导致引脚耐压
或内置功能不同）并逐条按本设计条件复核。
PCB 阻抗/间距/回流和实测约束独立 HANDOFF，边界见 [scope-boundary.md](references/scope-boundary.md)。

### 6. 图面目检（V）

所有页面留目检记录（DOC-V01），新页/变更区细读；极性、pin1/视图、选项、同名端、NC 标记需
图形证据。页面注释、遗留命名与图框版本按 DOC-V02 核对；装配选项的互斥与完整性按 DOC-T01 核对。

### 7. 覆盖审计（Q）、报告与校验

按 [报告模板](references/report-template.md) 交付“结论、处理清单、证据附录”。
作出每项结论时核对对象、配置、工况、判据与原始证据；同一依据可共用引用，各项结论仍须适用。
批量脚本只录入已审结论，不按 ID 前缀/功能组默认赋值。错配时复核受影响项及依赖，
不另设一轮全报告语义审批；新证据、设计或规则变化的复审仍按相应协议执行。

最终结果独立保存为 `review-results.json`，绑定合并后的最终计划。
按 [结果契约](references/review-results-schema.md) 记录对象/判据、覆盖、唯一缺陷、需求澄清和待办；
字段与枚举只在契约中维护，不在正文逐项解释。按有证据的共同根因归并处理动作，
不合并独立电气结论，不将待核、移交或受影响检查数算作已确认缺陷。
修改建议按 [remediation-guide.md](references/remediation-guide.md) 给可执行的改法、参数依据和复验条件，
共用计算/操作说明只写一次并链接；未确定输入不编造精确参数。

完成判定后运行自动对账；修正发现的记录错误后再运行，正常交付不增加重复人工审查：

    python3 scripts/validate_review.py review-plan.json review-results.json --db db.json --lint lint-cold.json --lint lint-hot.json --require-actionable --require-bindings --json review-gate.json

`valid` 只供记录对账使用，不能代替证据支持的电气结论。`quality_screening` 是定位疑点的提示，
同一共享依据可一次核查并注明覆盖范围；确有错配才修改相关结论，不为每条提示新建任务或反复改措辞。
零提示不证明审完。已有资料尚未读算的项记 REVIEW_INCOMPLETE，完成前不放行；
下游移交不能豁免原理图电气前提。冻结时加 `--require-release`，准出条件见 severity-calibration。
仅有外部缺口时可交受限报告，明确未决项和冻结影响；审查未完成时只能交进度，不能声称已完成。

保存输入哈希、意图、计划、证据、结果、计算/关键裁图及 Diff 到项目审查目录；
全量逐项台账与工具诊断放附录，正文只列本轮结论、问题和行动。临时全文/大图放任务临时目录，
最终证据不得只留临时目录；公开仓库只放脱敏合成用例。

### 8. 改版复验（H）

复审比较前轮设计和模板基线，沿变更供电/控制/保护依赖扩展复验。保留每个历史 ID，
区分撤回、复发、接受、已修复；断言要证明期望电气状态，仅“字段变了”不足以关闭（REQ-H01）。
读 [改版影响与复验](references/revision-impact-schema.md)：冷/热跑传同一 `--old-db` 和
`--old-plan`，与本版 `--merge-plan` 分开；可用 `--revision-impact-json` 另存清单。
轻量自动扫描每轮全量执行。新计划的 `review_policy_version: 2` 将局部依赖缺口限制在该项及
其显式依赖者；未知全局变化或基线缺失仍全量复验。旧项消失须独立处置（REQ-H02），同一历史
ID 只保留一次并保存不同定义快照；改版覆盖由 REQ-Q05 汇总。
每个必需项记录本轮方法、证据和摘要。`reuse_candidate` 只推荐核对已有计算/证据；核实对象、
MPN、工况、判据、来源及依赖均适用后可引用原记录，重新确认本版结果，不能盲迁旧 PASS。最终校验传相同旧基线并加
`--require-revision-impact`；缺历史快照不补造。旧基线必须是按当前总表生成的计划。

    python3 scripts/diff_netlists.py old-db.json db.json --claims review-claims.json --json diff.json --fail-on-open-claims

## 工具维护时的回归评测

仅在维护检查脚本或评估工具升级时，按 [电路评测说明](evals/circuit_bench/README.md)
运行冻结用例和版本比较；这不是每次原理图审查的附加步骤。评测通过不等于全板审查通过，
不得以合成规格文档替代真实项目证据。V3.3 改变了候选适用性和清单生成，升级后重建计划/清单，
保留旧快照；旧项排除按实际出处留痕，不能把新版少生成的项静默当作关闭。增删规则或改判据只改 `scripts/catalog.py`，再运行
`python3 scripts/catalog.py --write-doc references/check-catalog.md` 同步总表。

热边界调整后重建受影响计划，保留旧计划和结果；按新判据重新审查，不仅改结果绑定来复用旧结论。
误混入的热验证按 scope-boundary 留更正依据与移交映射，已有真实电气 FAIL/缺口不得静默消失。

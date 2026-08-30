---
name: schematic-review
description: "当用户要审查电路原理图、判断原理图能否冻结并进入 PCB Layout、生成逐检查项执行计划、核验改版 diff 或历史意见闭环时使用。覆盖网表/ERC、datasheet、供电与电平、关键链路、原理图可确定的 WCA、平台原理图规则、图形和器件身份；不用于已布 PCB 的布局布线、SI/PI、EMC、热、DFM 或生产准出签核。"
---

# 电路原理图系统审查

> V1.4｜AC0 适用性发现 + 逐项执行计划 + 双维结果/HANDOFF + ER1 热跑 + 网表 Diff。

## 核心思想

原理图的电气本质是**网络表**，图形只是可视化。审查不依赖 EDA 软件：把导出网表解析成结构化数据，分两层执行——

- **AC0 Automated Check（自动检查）**：先做 Applicability Discovery，生成规则级与位号/网络级执行计划；再用机械、无歧义、可穷举的规则全量扫描，解决**覆盖率**。输出是疑似清单，合法结构（Bob-Smith、DNP 选项）由执行 agent 逐条排除。
- **ER1–ER7 Expert Review（专家审查）**（按执行序）：datasheet 核实 → 供电建图 → 链路追踪 → 参数验算 → 平台原理图规则 → 图形目检 → 器件身份/封装一致性，解决**正确性与风险**。

**检查标识中的数字即执行顺序**，且顺序本身是有依据的：先有 datasheet 才谈得上"违反"，先有电源树才有地图可走链路，先走通链路才知道该算哪些点。流程步骤（0～10）、检查标识（AC0/ER1–ER7）与规则身份（Rule-NN）是三个独立编号体系。

## 准出对象与边界

本 skill 只签署**原理图准出**：结论是“可冻结并进入 PCB Layout”，不是“整板可投板”。
原理图无法最终验证但必须由 PCB/测试/结构落实的事项写入独立 `handoff` 字段；完整边界矩阵见
references/scope-boundary.md。不得用缺少 PCB 证据作为原理图 FAIL，也不得把
“已传递约束”写成 SI/PI、EMC、热或 DFM 已通过。

## 三条铁律

1. **datasheet 原文 > 网表实测 > 页面注释**。注释是"待验证声明"（实例：注释写 V1=20V，实贴电阻算出 18.39V）。
2. **历史评审意见只作线索，必须独立复核**。"回复已修改"不构成闭环证据——逐条对网表验证（假闭环是高频事件）。
3. **每条结论必须有证据链**：refdes + 网络名 + datasheet 条款/页码/表号 + 置信度。没有证据链的发现不进报告。

## 证据置信度（与审查结果独立）

| 级别 | 含义 | 处置 |
|---|---|---|
| **A 网表实证** | 网表数据直接证明（断网、参数不符） | 可直接整改 |
| **B datasheet 已核** | 经官方 datasheet/规范核实 | 可直接整改 |
| **C 证据不足** | 信息不足或来源不可靠 | 对应检查项结果写 INSUFFICIENT，**严禁臆测** |

器件类别必须 ≥2 个独立证据源才允许定级 A/B（实例：浪涌器件凭库名误判为 TVS，原厂规格书证伪其为 MOSFET 结构件）。

**证据置信度 C 隔离（全自动流程强制）**：置信度 C 的材料不得作为推导 A/B 结论的依据。信息补齐前，依赖它的检查项结果一律为 INSUFFICIENT——不确定性只能向下传播，**不得被逐级洗白成确定结论**。

每个检查项的 `review_result` 只能是 PASS / FAIL / INSUFFICIENT / NA。HANDOFF 不是
审查结果，而是独立下游动作，可与 PASS、FAIL 或 INSUFFICIENT 并存；其状态单独使用
OPEN / ACCEPTED / VERIFIED。NA 只能表示经适用性判断并有依据地确认不适用。

关键 INSUFFICIENT 未补证据或未书面接受、HANDOFF 未形成可执行约束或无接收方，
都不得准出。PASS 不自动关闭 HANDOFF，HANDOFF 被接收也不反向证明 PASS。

## 严重度分级

| 级别 | 定义 | 处置 |
|---|---|---|
| 致命（BLOCKER） | 上电不工作/损坏器件或上游设备 | 必须修复后原理图准出 |
| 严重（Warning） | 功能失效风险高、违反强制规范、可靠性硬伤 | 必须修复或书面风险接受 |
| 建议（Info/Suggestion） | 提升可靠性/合规性 | 评估后决定 |
| 观察 | 需设计方确认的决策项 | 列入报告「待确认」节并跟踪 |

## 审查流程（0→10）

**检查标识中的数字即执行顺序。** AC0 是唯一的自动检查层，ER1–ER7 是需要工程判断的专家审查层。

```
0. 意图对齐（设计意图问卷）        5. ER3 关键链路逐条追踪
1. 数据解析（网表→结构化索引）     6. ER4 参数与边界验算（WCA）
2. AC0 适用性发现 + Lint 冷跑       7. ER5 平台原理图规则扫描
3. ER1 datasheet 核实 + AC0 热跑     8. ER6 图形化系统目检
4. ER2 供电系统审计（建电源树）     9. ER7 器件身份与封装一致性
                                  10. 输出分级报告 + 修复-复验闭环
```

**贯穿全程（不排队）**：文本层不可靠时**立即**渲染目检——扫描件、表格列错位、
水印插进数据行。等排到 ER6 再读图，前面的结论已经写错了（实测两次）。

**为什么 ER1 在最前**：Abs Max、强制条款、公式常量、引脚语义都来自 datasheet，
没有它们 Rule-16（strap 违反条款）判不了"什么叫违反"、ER4 算不出任何电压、
ER5 无规可对。**但不必在 AC0 之前读**——AC0 的纯网表规则先跑，它会告诉你
哪些器件有异常、该优先读谁的 datasheet，避免盲读几十份。

### 第 0 步：意图对齐（必须先做）
**由执行 agent 从输入材料（需求/规格书、原理图标题页与修订记录、历史评审记录）自行提取并成文留痕，不得中断流程向人询问。** 需提取：板卡功能一句话；电源链路与功耗预算；必须保留/删除的接口清单；环境约束（温度/振动/防护/EMC）；降额策略；不可更改项（认证、绑定芯片、平台强制规则）。**适用检查缺材料时结果标 INSUFFICIENT，并在报告头部声明「规格符合性判定受限」——不得凭空补全。**该意图清单是 Applicability Discovery、Rule-07 与 ER5 的判定输入，必须随报告留档：它错了，下游结论会连锁错。

### 第 1 步：数据解析
`python3 scripts/parse_netlist.py <allegro目录> -o db.json`。**该脚本自带自检闸门**：pinname 覆盖率过低会报错退出，而不是交出静默残缺的索引（否则 Rule-05/Rule-06 会扫出 0 条并被误读为「全部通过」）。同时自动识别工具伪网络。格式说明与其他 EDA 适配见 `references/netlist-parsing.md`。**别忘了 `netlist.log`——导出日志是免费证据**。同时 `pdftotext -layout` 逐页转文本（以页内 File: 字段为准建立实际页面清单，目录页常过期）；扫描件/错乱表格用 `pdftoppm -png -r 200` 渲染目检。

当前仓内只提供 Cadence/OrCAD pstxnet 三件套解析器。其他 EDA 必须先由项目适配器
生成相同 db.json 字段并通过覆盖自检；文档中的格式说明不等于已有可执行适配器。

### 第 2 步：AC0 适用性发现 + 自动检查
先根据网表、意图和已有 evidence 生成 `review-plan.json`：

    python3 scripts/plan_review.py db.json --intent intent.json --json review-plan.json

计划同时包含规则级 `rule_plan` 与逐位号/网络 `checks`。每项分别记录
`applicability`（APPLICABLE / NOT_APPLICABLE / UNDETERMINED）、`stage`、`readiness`
（READY / WAITING_EVIDENCE / NOT_SCHEDULED）、所缺输入及独立 handoff。**没有检测到
电路特征不等于 NA**；只有设计意图明确 NOT_APPLICABLE 且带出处时才可生成 NA。
格式见 references/review-plan-schema.md。

随后运行 `python3 scripts/lint.py db.json --log netlist.log --intent intent.json --plan-json review-plan.json`。规则库与判别式见 `references/lint-rules.md`。`FINDING` 逐条排除；`CANDIDATE` 是待 ER1 定夺的优先级清单。脚本末尾列出未执行规则及原因——0 条 ≠ 通过。

### 第 3 步：ER1 datasheet 核实（一切判断的前置）
新 IC 介入第一步先读 **Absolute Maximum Ratings**（实例：EN 脚耐压 5.5V 被上拉 24V）。
逐项落实四类信息，后续各层直接取用：

| 取什么 | 供给哪一层 |
|---|---|
| Absolute Maximum Ratings | ER2 电平域、ER7 选型 |
| **强制条款原文**（`must be pulled down` / `must be left floating` / 内部默认态），**原文用词必须保留** | Rule-16、ER5 —— 它是定级为 BLOCKER 的唯一依据 |
| 公式常量（VFB、Vref、限流/频率系数）、可调 vs 工厂固定档 | ER4 全部验算 |
| 引脚语义表（方向敏感信号、多封装变体） | ER3 链路追踪、Rule-14 符号审计 |

**回补 AC0（热跑）**：把 ER1 结论按 references/datasheet-evidence-schema.md 写成
evidence.json，再执行：

    python3 scripts/lint.py db.json --intent intent.json --evidence evidence.json --json lint-hot.json

Rule-08/09/12/14/16 只在存在对应结构化证据时执行；没有输入的规则必须保留 pending，
不得由 agent 凭阅读印象假装“已热跑”。

查不到 datasheet 的检查项结果标为 INSUFFICIENT 并列入待索取清单，**严禁凭印象补参数**；网络聚合页信息一律不可靠。表格列错位时先渲染目检再取值——工厂固定档被误读成可调档，会直接产出假缺陷。

### 第 4 步：ER2 供电审计
每轨三问：谁驱动（注意 0R 跳线选项，须追另一端找真实源）/谁负载/电平对不对。SoC 全部电源球有驱动、全部 VSS 球入 GND。电平域匹配：列出各 IO 域实际供电，核对相连两端域电平一致。每轨功率预算留 ≥20-30% 裕量——**此项网表给不出负载电流，需外部功耗数据**；拿不到时结果标 INSUFFICIENT 并索取，不得跳过后当作通过。反灌审计（**可执行判据**）：对每颗上拉/上拉性通路，比较「上拉源轨」与「被拉信号所属 IC 的供电轨」，**跨轨即候选**；再看两轨是否同时上电（同一稳压器、或有明确时序保证）。跨轨且无时序保证 = 该 IC 未上电时被倒灌。隔离域之间的任何跨轨上拉一律列为发现项。热与浪涌：高压分压电阻功耗、开关器件 I²R 耗散、热插拔浪涌 I=C·dV/dt。

本层只判断原理图可证明的拓扑、逻辑时序和电气应力。PCB 压降、PDN、布局后的
实际热路径不在本层定判；把大电流、去耦和散热要求写入独立 handoff。

**Rule-11 检测点选错轨在本层判**（已从 AC0 迁入）：判压/检测分压应取「源」侧而非「保护后内部轨」侧。判定要回答「谁是源、谁是保护后」，答案只存在于刚建好的电源树里——AC0 阶段无此上下文（实例：VBUS 判压分压错接输出侧 VOUT_24V）。详见 `references/methodology-v1.0.md` §5.7。

### 第 5 步：ER3 关键链路逐条追踪
对意图中的每个"连接对"从 A 逐跳走到 B（网络→元件→网络），断裂点即 bug。必查：电源输入→保护→各级电源→负载；每路数据链路双向；复位链；时钟链；启动配置；检测/反馈链取样点与终点；使能链（谁产生/谁接收/极性/电平域）。**方向敏感信号（TX/RX、差分 P/N）必须回官方引脚语义表逐字确认并做"发射端→接收端"复述，禁止凭感觉交叉。**

### 第 6 步：ER4 参数与边界验算（WCA）
scripts/solve_dividers.py 会穷举电阻路径，处理串联臂、可安全归并的并联支路，并输出
电阻与 Vref 公差叠加后的 min/typ/max；多源或共享支路等无法无歧义求解的拓扑标 INSUFFICIENT，
不再静默采用第一条路径。公式库见 references/wca-formulas.md。ER4 只计算原理图和
datasheet 能确定的阈值、限流、RC、上拉、无源功耗与额定值；依赖 PCB 热阻、寄生或
实测工况的要求写入独立 handoff。

### 第 7 步：ER5 平台原理图规则扫描
把平台官方 checklist/设计指南中**仅凭原理图可判定**的条目转成检查表逐条核对。
布局、SI/PI、EMC 实测、软件和结构约束不得冒充原理图结果，只写入独立 handoff；
是否适用仍由 applicability 单独记录。
通用域检查表见 references/review-checklist.md；平台专属规则库按项目构建。

### 第 8 步：ER6 图形化复核
网表覆盖不了的信息在图形里：渲染关键页读图（新增页全读），目检清单——二极管/TVS 阴极方向、LED/电解电容极性、连接器 pin1、变压器同名端、Option/NC 贴装表、strap 配置表。**多封装同页引脚图必须按标题逐张对应，禁止跨图引用**。比对 PDF 与网表的导出时间，防止拿旧图审新版。

### 第 9 步：ER7 器件身份与封装一致性
核对 MPN、符号、引脚号、封装字段、参数档位和替代料电气/封装兼容性；BOM 二义在此
收口。器件类别判定必须 ≥2 个独立证据源才允许定级 A/B。生命周期、单一来源和采购
风险属于独立供应链检查，不作为本 skill 的原理图准出结论。

### 第 10 步：输出报告 + 修复-复验闭环
骨架与发现项格式见 references/report-template.md。报告按逐检查项列出 PASS、FAIL、
INSUFFICIENT、NA，并单列可与结果并存的 HANDOFF；只给“原理图准出/有条件准出/不准出”结论。下游约束已传递不等于
PCB 已验证。

修复后重新导出网表 → 复跑 AC0/热跑 → 用 scripts/diff_netlists.py 比较新旧
db.json，并按 references/diff-claims-schema.md 核验历史意见。确认只改了该改的，
BLOCKER 清零、Warning 已关闭或书面接受、关键 INSUFFICIENT 已关闭/接受且 HANDOFF
至少形成可执行约束并被接收后，才输出
“原理图可进入 PCB Layout”。

    python3 scripts/diff_netlists.py old-db.json db.json \
      --claims review-claims.json --json diff.json --fail-on-open-claims

> **检查标识迁移（V1.2）**：`AC0` = Automated Check（原 `L0`），`ER1`～`ER7` = Expert Review（原 `L1`～`L7`）。旧报告可在一个迁移版本内写成 `AC0（原 L0）`、`ER1（原 L1）`；完整换算见 `references/methodology-v1.0.md` §0.2.1。
> **三个编号体系解耦**：步骤 0～10 只表示工作流位置；AC0/ER1–ER7 只表示检查模块与执行顺序；`Rule-01`～`Rule-20` 只表示规则身份，编号保持不变。

## 高频错误模式库（每轮强制自查）

- [ ] 网络名分裂（差下划线/后缀，同一轨两个名字互不相通）
- [ ] "NC" 被当成网络标号：所有"不用引脚"被短接成一张大网（OrCAD 经典陷阱）
- [ ] 多封装同页引脚图跨图误引（先确认实物封装再看对应图）
- [ ] "参照 demo 板"违反 datasheet 强制条款（must be pulled down / must be left floating / 默认态）
- [ ] 假闭环：以"已修改"回复代替网表验证
- [ ] 库符号引脚映射错（新建/定制符号必查；沿用成熟库可免检）
- [ ] 器件身份与外围参数不匹配（库名/封装/分压三者对不上）
- [ ] 检测点接错侧（判压接在保护后/负载侧）
- [ ] ESD 挂残网（防护在空网，活线裸奔）
- [ ] EN 脚超耐压/极性反（低有效上拉、高有效下拉）
- [ ] 钳位管/稳压管直接跨接超压轨
- [ ] 上拉电源域与信号域不一致/向上电未完的器件倒灌
- [ ] strap 采样电平被同节点 LED/上拉拖偏（复位采样窗口算分压）
- [ ] 同名不同域电源轨张冠李戴（VCC_3V3 ≠ VCC_3V3_SOM）
- [ ] 串联下臂被当成单电阻（分压比算错主因）
- [ ] 可调阈值只按 typ 算不给 min/max 范围
- [ ] 估算值当 datasheet 原文引用（功耗/电流数字标明来源）
- [ ] 网络命名与电平/功能不符误导后来者
- [ ] 扫描件/损坏文本层 datasheet 未渲染目检就下结论
- [ ] 把目录页当实际页面清单（以页内 File: 字段为准）

## 工作纪律

- 结论可被质疑：每条发现给出可复现核验路径（文件:行号/页码/表号）；被反驳时用证据复核，错了明确撤回并归档教训
- 更正前轮（含自己）结论写成"更正说明"，不悄悄改
- 报告写入项目目录；中间产物（页面文本、渲染图、底稿）放 /tmp；交付物只有报告本身
- **自己的分析工具也会错**：每个计算结果必须与一个独立信息源对撞（算出的轨压 vs 轨名、strap 判定 vs 同页对照引脚、解析结果 vs 器件数）。对不上时**先怀疑自己的脚本**，再怀疑板子——本 skill 的分压求解器就是靠这条抓出过递归终止 bug
- 展开网络节点时排除 GND/大电源网并设递归深度上限；一次 dump 一张挂上百节点的网会淹没有效信息
- 本 skill 的 scripts/、references/、examples/ 均为可执行资产，审查时按需取用，不必全量加载：
  - `scripts/parse_netlist.py`：三件套 → 结构化索引，**自带自检闸门**与伪网络识别
  - `scripts/lint.py`：AC0 冷跑 + ER1 证据驱动热跑 + PINUSE/ERC
  - `scripts/plan_review.py`：AC0 适用性发现、规则计划与逐项执行计划
  - `scripts/diff_netlists.py`：新旧 db.json Diff + Rule-17 历史闭环断言
  - `scripts/solve_dividers.py`：串/并联分压、公差窗口与轨名交叉校验
  - `references/methodology-v1.0.md`：方法论完整长文档（含 AC0/ER1–ER7 各章细节、平台规则库构建方法与模板、其他 AI 平台迁移指南）
  - `references/scope-boundary.md`：原理图可判定、HANDOFF 与范围外边界
  - `references/review-plan-schema.md`：意图扩展、适用性、准备度、结果与 handoff schema
  - `references/datasheet-evidence-schema.md` / `diff-claims-schema.md`：热跑和复审机器输入
  - `references/netlist-parsing.md` / `lint-rules.md` / `review-checklist.md` / `wca-formulas.md` / `report-template.md`：解析、规则库、通用检查表、验算公式、报告模板
  - `scripts/tests/`：确定性规则的标准库回归测试
  - `examples/`：报告范例，写报告时参照其详略与格式
    - `worked-example-industrial-gateway.md`：一份完整的合成范例报告（虚构板卡），涵盖准出判定表、BLOCKER/Warning/Info 分级、闭环三档、误报排除、计算留档等全部骨架

# 报告与修改说明

报告正文只写结论和需要处理的事项，详细台账与计算放可定位的附录；无内容不设空节。
结果字段以 [计划与结果台账](plan-and-results.md) 为准，分级与准出以 [结论与准出](verdicts-and-release.md) 为准。
报告、台账和证据保存在项目审查目录。

## 一、报告结构

### 1. 结论与范围

- 写明板卡/原理图版本、装配配置和首审/复审基线，链接输入清单，说明 PDF/网表同版核对结果。
- 按阶段给结论：非冻结阶段说明已证实功能、真实缺陷、仍影响本体判断的疑点和集成约束，以及本轮先做什么；
  申请冻结时给出可冻结、有条件冻结或不可冻结及主要原因，有条件冻结须有实际接受记录。
- `release` 是冻结闸门，非冻结阶段不能当作总判定，也不能反过来把真实电气阻断项改成 PASS；
  `valid=true` 只表示记录可对账，不作“审查通过”展示。
- 审查未完成时写明“审查进行中”，只交进度和剩余工作。仅 PDF、外部缺证等限制直接说明影响，不写长篇免责声明。
- 复审概括本轮新增、修复、撤回和仍开放的事项，历史数量不混入当前缺陷。

结论后固定列一组计数，每类单独一行，为 0 也写出（写“FAIL 0”，不写“无 FAIL”或省略）；
一行结论和 README 摘要重复同一组数字：

| 计数类别 | 取值 | 来源 |
|---|---|---|
| 检查结果 PASS / FAIL / INSUFFICIENT / NA | 各类检查行数 | `review-gate.json` 的 `summary.results` |
| 确认缺陷 P0 / P1 / P2 / P3 | 唯一缺陷数 | `summary.by_severity` |
| 待核项潜在等级 P0 / P1 / P2 / P3 | INSUFFICIENT 检查行数 | `review-results.json` 中 INSUFFICIENT 行的 `potential_severity` |
| 移交状态 OPEN / ACCEPTED / VERIFIED | 移交检查数 | `categorized_summary.handoffs_by_state` |
| 需求澄清 开放 / 其中阻断 / 其中已覆盖 / 已解决 / 已撤回 | 唯一澄清项数 | `requirement_clarification_summary` 的 open / blocking_open / covered_open / resolved / retracted |

工具输出省略的类别按 0 补齐。检查行数、唯一缺陷数、移交数和澄清项数口径不同，不相加。

### 2. 处理清单

按紧迫性列全部需处理事项。同一根因或独立决定一行，用“类别”区分：电气缺陷、需求澄清、
证据/设计缺口、审查待完成、下游移交、集成约束、可选改善。

| ID / 类别 | 位置、问题及依据 | 影响 / 冻结影响 | 建议及下一步 | 关闭条件 / 时点 / 状态 |
|---|---|---|---|---|

- **电气缺陷**标 P0–P3，写清不满足的判据、工况和影响，链接证据与计算，按下文“修改说明”给改法。
- **需求澄清**写已核输入、待决内容/建议、责任方和关闭依据，见 [需求澄清项](requirement-clarifications.md)；不套缺陷等级。
- **待核**写已知什么、具体缺什么、影响哪个判断、如何关闭；先完成现有资料支持的分析，同一补证动作只列一次。
- **下游移交/集成约束**写接收角色、定量约束、验证方法与阶段，引用真实接收记录。
- 同一问题关联多个检查只统计一次并保留关联 ID；不把检查行数或质量提示数称为缺陷数。

交付前确认每条不通过或待关闭事项都有明确建议与关闭条件；不能用“不通过/待验证/参考手册”代替动作。

### 3. 证据与追溯附录

可直接链接已有持久化文件，不必再造同内容表格：

- 输入版本/哈希、需求、装配与规则指纹；PDF 页码/页名/网表路径映射，未知标 UNKNOWN。
- 全量检查台账：对象、判据、结果、证据、计算，以及关联的 finding/澄清/任务/移交；冷热候选处置和覆盖统计。
- 实际计算、图面记录和修改明细；相似器件参数、反算要求与本器件事实分清。
- 复审的 Diff、历史 ID 到本轮结论的映射、关闭/撤回依据及复验证据；未执行的复验不能关闭。
- `review-gate.json`。质量提示的核查结果记在相应证据中，不另建“语义审查报告”。

## 二、修改说明（让硬件新手能执行）

目标是让读者能根据原理图定位并完成编辑，知道哪些参数已有依据、哪些仍要确定、用什么结果验收。
指导编辑不等于授权代改设计。真实位号/物理脚来自当前版本；新器件写“建议新增，位号待分配”，不伪称已有空闲位号。
待核/待决项同样给补证或设计动作和关闭条件，但不冒充已确认缺陷。

### 修改准备度

| readiness | 报告中文 | 适用条件 |
|---|---|---|
| READY | 可直接修改 | 连接、规格和前提已齐；无未决选型/输入 |
| CONDITIONAL | 条件满足后修改 | 拓扑方案已明确，参数或资料前提未齐；给取得及判断方法 |
| DESIGN_REQUIRED | 需要重新设计 | 架构、模式、控制脚或接口方案未定；先列设计步骤和选择依据 |

准备度与严重度、置信度、关闭状态彼此独立。READY 不表示可以直接上电或修改已验证。
不得用 CONDITIONAL/DESIGN_REQUIRED 逃避现有资料可完成的计算、连接核对和具体操作。

### 每项应说清的内容

1. **定位和目的**：PDF 实际页/页名、位号.物理脚、网络；用一句普通话解释应恢复的行为，
   例如“上拉电阻使控制脚在主控接管前保持高电平”，再说明该高电平对应开还是关。
2. **前后状态**：旧→新值/装配/网络；换源时先写断开哪条旧连接，再写新路径，路径写成
   `源物理脚 → 网 → 已贴器件.脚 → 网 → 接收物理脚`。仅加同名标签可能合并所有同名端，须列受影响成员。
3. **顺序操作**：定位 → 断旧/改件 → 连新 → 更新 BOM/装配 → 检查；只写实际必要步骤，不猜 EDA 菜单。
   分压、多级开关、二极管方向等需图形才能说清的给小图或连接表，标清脚号。
4. **规格与依据**：被动件给值/精度及相关功率、耐压、封装、贴装；保护/有源件给所需范围与物理脚定义，
   精确 MPN 须有原厂依据。给公式、实际输入、公差/温度边界、结果与验收窗；未知项说明取得处和选择方法，
   如“取得最大输入电压后按 P=V²/R 计算，再按温度降额曲线选额定”，不能只写“重算”。
5. **联动及验收**：指出需要一起解决的 ID 和改后受影响状态；每条验证写方法、测点/工况、预期结果。
   区分网表/计算验收与 PCB、固件、实物验证，不把待做测试写成已通过。

不能只写“接到合适 GPIO”“加 ESD”“参考典型应用”“复算环路”“加 10k 上拉”这样的终点句；
没有取得某颗 IC 的实际脚表就写清缺口，不为显得具体而编造脚号。选项较多时给推荐方案及选择条件。

### 三种修改的尺度（合成示例，数值不可复用）

**连接/装配已有唯一依据**：p2 的 R10 为已确认的 10 kΩ 上拉，`R10.1→3V3；R10.2→U2.4` 已接对，但装配为 DNP。
将 R10 改为贴装、导出 BOM 数量恢复为 1、阻值保持；规格 1%/0402/≥0.063 W，最坏 3.465 V、−1% 阻值时功耗约 1.22 mW。
验收：新网表/BOM 中 R10 为已贴，两端分别在 3V3 和 U2.4 所在网。

**方向明确但参数未定**：输出泄放。先画清 `VOUT → R_new → GND` 的并联支路；从受控要求取得
Vmax、Cmax、Vsafe、tmax、温度，按 `R ≤ tmax/[Cmax·ln(Vmax/Vsafe)]` 计算，再核 `Pmax = Vmax²/Rmin`、
公差及功率降额。只有条件算例时标“候选，不能据此定版”，并写明取得哪些输入后可改为已选。

**需要重新设计**：默认关断链。先列输入电源与控制电源有/无、主控复位/高阻/运行时的目标输出；
核 EN 极性与门限、内部默认拉阻、掉电耐受；推荐能覆盖状态表的拓扑，标出接入点，给电平/电流不等式和选型方法。
主控脚未分配时须取得 pinmux 表，不能臆造“空闲 GPIO”，也不能以“找专业人员处理”代替设计说明。

### 结构化字段

结果设 `remediation_version: 2`，每个 finding 带 `remediation`：

```json
{
  "remediation": {
    "readiness": "READY",
    "purpose": "使主控复位期间输入保持规定的高电平。",
    "prerequisites": [],
    "steps": [{
      "kind": "ASSEMBLY",
      "target": "PDF p2 R10",
      "before": "DNP，不贴装",
      "after": "贴装，BOM数量1；阻值10kΩ保持",
      "instruction": "在当前配置中启用R10贴装，并同步BOM装配选项。"
    }],
    "parameters": [{
      "target": "R10",
      "specification": "10kΩ，1%，0402，额定≥0.063W，贴装",
      "status": "SELECTED",
      "basis": [{"source": "synthetic-requirements.md", "locator": "SYN-R1 and power calculation"}]
    }],
    "related_findings": [],
    "impact_review": "核3V3存在而主控复位的默认态；输出灌电流按已列规格核算。",
    "verification": [{
      "stage": "NETLIST",
      "method": "导出本配置网表和BOM，逐端检查R10。",
      "expected": "R10已贴；R10.1在3V3，R10.2与U2.4同网。"
    }],
    "calculation_preflight": {"applicable": false, "reason": "恢复受控贴装，无数值推导", "evidence": [{"source": "synthetic-requirements.md", "locator": "SYN-R1"}]}
  }
}
```

- `steps` 按顺序执行，至少一项；`kind` 为 CONNECT / COMPONENT / ASSEMBLY / DOCUMENT / DESIGN，每步 target/before/after/instruction 非空。
  CONNECT 另给 `remove_connections`/`add_connections`（`{"from":"R1.2","to":"U1.3"}`），至少一侧非空。
- `parameters` 每条 target/specification/status/basis 非空；status 为 SELECTED / CANDIDATE / TBD，后两者另给 needed_input 和 selection_method。
  COMPONENT/ASSEMBLY 步骤至少有一条规格记录。
- `prerequisites` 每项含 input/reason/how_to_obtain/acceptance；READY 必须为空且不含候选参数或 DESIGN 步骤，其他准备度至少一项。
- `related_findings` 指向同报告其他 finding；`impact_review` 非空。
- `verification` 至少一项，stage 为 NETLIST / CALCULATION / DOCUMENT / BENCH / PCB，且至少一项属于前三类。
- `calculation_preflight`：有数值推导时给 calculations（合同见 [计算条件合同](calculation-preflight.md)），参数用 `calculation_ids` 关联依据；
  READY 必须有适用条件下成立的计算，不能依赖窄条件之外的保证值、典型值或未关闭假设。
  纯文档、恢复受控连接/贴装等无数值推导的修改可声明 `applicable: false`，给 reason 与可定位 evidence。

校验加 `--require-actionable`。校验器只检查结构和准备度矛盾，不能证明操作语义或计算正确；
交付前按这些步骤对照真实输入逐项演算一次。

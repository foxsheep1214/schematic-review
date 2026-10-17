# 计划与结果台账

审查数据分三份：`intent.json`（设计意图与输入声明）、`review-plan.json`（逐项检查计划）、
`review-results.json`（逐项结果）。计划只决定每项的规则、适用性和准备度，不提前制造 PASS/FAIL；
结果另存，由 `validate_review.py` 对账。常规命令见 [SKILL.md](../SKILL.md)。

## 一、intent.json（schema_version 3）

合成示例（数值仅说明结构）：

```json
{
  "schema_version": 3,
  "review_mode": "first",
  "review_phase": "design_iteration",
  "input_sha256": "填写 decoupling.py 候选清单里的 input_sha256",
  "assemblies": [{
    "id": "run-option-A", "citation": "装配 BOM Rev.B 选项 A；跳线表 Rev.C 第 2 行",
    "population": {"U1": true, "C1": true, "C2": false}, "jumpers": {"JP1": "closed"}
  }],
  "devices": {
    "U1": {
      "mpn": "REG-X-ADJ", "package": "QFN-16",
      "identity_citation": "BOM 订货码与官方订货表对应行",
      "citation": "REG-X datasheet Rev.A 第 3 页完整脚表", "pinout_complete": true,
      "pins": {"1": {"name": "VIN", "role": "power"}, "2": {"name": "GND", "role": "return"}}
    }
  },
  "requirements": [{
    "id": "REQ-USB", "text": "提供一路 USB 设备接口", "status": "CONFIRMED",
    "citation": "Requirements v1.2 section 4.1",
    "criterion": "PHY 与连接器双向链路、供电及外部带电状态满足接口条件"
  }],
  "circuits": [{
    "id": "USB-PORT", "type": "USB",
    "refs": ["U1", "J1"], "nets": ["USB_DP", "USB_DM", "VBUS"],
    "states": ["startup", "run", "external-power-only"],
    "citation": "Requirements v1.2 section 4.1; schematic page 2"
  }],
  "expect": {"USB_PHY": 1},
  "features": {
    "USB": {"applicability": "APPLICABLE", "citation": "Requirements v1.2 section 4.1"},
    "DDR": {"applicability": "NOT_APPLICABLE", "citation": "Requirements v1.2 section 2.3"}
  },
  "materials": {
    "requirements": {"available": true, "citation": "Requirements v1.2"},
    "schematic_pdf": {"available": true, "citation": "SCH-100 rev.B.pdf"},
    "datasheets": {"available": true, "citation": "datasheet-manifest.json 2026-08-31"},
    "platform_checklist": {"available": false}
  },
  "power_rails": {
    "VCC_3V3": {
      "voltage_v": {"min": 3.2, "max": 3.4}, "load_a": {"min": 0, "max": 0.5}, "available_a_min": 1.0,
      "refs": ["U1", "L1", "F1"], "state": "BOM B; stated Vin/load/temperature corners",
      "citation": "Load budget Rev.B table 2 and component guaranteed ratings"
    }
  }
}
```

- `review_mode`：`first` 或 `revision`。`review_phase` 取值见 [结论与准出](verdicts-and-release.md#5-审查阶段)。
- `features` 的键与 `circuits[].type` 取 [规则总表](check-catalog.md)“功能包”中的包名，否则拒绝；
  `applicability` 为 APPLICABLE / NOT_APPLICABLE / UNDETERMINED，前两者必须带 `citation`。
- 名称命中只生成 UNDETERMINED 候选，不展开成员；由电路声明、features 出处或已确认拓扑确认后再展开。
  带出处的不适用声明可排除误命中；与已确认拓扑冲突则保留证据不足。没搜到关键字不能推出 NOT_APPLICABLE。
- `materials.<name>.available=true` 必须带 `citation`。逐物料审计（`--datasheet-audit`）优先于这些全局布尔值。
- `assemblies`（1–32 个，各带 `id` 与 `citation`）是全部检查器共用的装配状态；`devices` 是按位号的官方脚表。
  声明二者或任一检查器段时须带顶层 `input_sha256`，过期即拒绝。
- `requirements[].status`：已确认（CONFIRMED）、提案（PROPOSED）、未定（OPEN）、暂缓（DEFERRED）。
  保留需求原文和源状态，先按 [源条目到审查义务](requirement-clarifications.md#源条目到审查义务)
  确定本次判据的实际确认状态，不省略真实未定项。OPEN 的 REQ-D01 必须 INSUFFICIENT + REQUIREMENT_OPEN；
  DEFERRED 必须 INSUFFICIENT + USER_DEFERRED；PROPOSED 可判定，但结论以提案为前提。
- `power_rails` 支撑 PWR-C01 与 DEV-E02：给电压/最大负载、源端最弱保证可供电流和条件；READY 不等于 PASS。
  片内稳压输出（如 MCU 的 1.1 V 内核轨）、仅板内使用的中间轨同样要声明电压：阻容预判按同簇器件的全部供电轨定界，缺一条就整簇不出预判。计划命令末尾会列出“未声明电压的轨”及受阻行数，能从稳压器手册或需求定出时补齐后重跑。
  隔离或多地设计给各轨与各地写 `domain`（如 PRI/SEC），地写 `voltage_v: {min: 0, max: 0}`；栅极/检测节点可按计算声明窗口。
  窗口由审查者独立定界：取需求输入范围、稳压器/钳位/保护门限的保证值和故障上限；设计计算书只作线索，逐条核出处后写 `citation`，不照抄设计方数值。
  热跑前 `power_rails` 仍为空却有 DEV-C01/PWR-C10 行，属审查准备未完成，先补齐再录结论。
- 条件导通另可声明 `power_sources`（某状态的供入节点）与 `power_paths`（某状态可导通的方向，不是理想短路或载流声明），
  不得把未上电的稳压器或端口标成 source 来消除告警。
- 各检查器的 intent 段（`i2c_topology`、`decoupling`、`device_kinds` 等）见 [自动检查](automation.md)。

## 二、review-plan.json（schema_version 3）

### 生成与合并

- 冷跑 `lint.py --plan-json review-plan-cold.json` 保存计划和候选；人工补查项加入该计划。
- 热跑 `--merge-plan review-plan-cold.json --plan-json review-plan.json` 产生**唯一最终计划**。
  合并要求 `db_sha256` 与当前输入一致且规则指纹相同，保留人工补查项；相同 ID 的对象/判据冲突时拒绝自动覆盖。
- 匹配证据后保留基础覆盖项，按 evidence ID 生成带 `parent_check_id` 的状态子项；基础项只汇总覆盖，不能代替子项结果。
- 计划合并不读取或迁移结果；后续补查先更新计划，再更新 digest 和逐项结果。
- 人工补查项从总表选规则，`id` 写成 `规则编号.自定义键`，并填与总表一致的 `rule`/`method`/`domain`、
  `object`、`criterion`、`applicability`、`readiness`、`handoff`。
- **拆分实例的命名**：一条规则需要逐对象或逐判据给出不同结果时，拆成多个补查实例，自定义键写成
  `<对象>[-<判据>]`，对象用位号、网络或电路 ID，判据用简短大写词。例如全板项 DEV-C01 逐颗判定时写
  `DEV-C01.C12`、`DEV-C01.Q3`；PWR-C02 拆窗口与调节能力时写 `PWR-C02.U1-WINDOW`、`PWR-C02.U1-REGULATION`。
  自动生成的原计划项（如 `DEV-C01.BOARD`）保持不变（校验会按保存的输入重建它），其结果在 rationale 中列出全部
  拆分实例 ID 作为覆盖依据；各对象的结论以拆分实例为准，原项不得报出比拆分实例更好的结果。

### 检查项字段

| 字段 | 含义 |
|---|---|
| `id` | `规则编号[.实例键].锚点`，如 `RST-T02.U3.SYS-RST-N` |
| `rule` / `method` / `domain` | 规则编号、方式代码、内容域代码，须与总表一致 |
| `object` | 对象：覆盖维度、功能包、全板、网络、位号、引脚或页码 |
| `criterion` | 本项判据 |
| `check_explanation` | 本项检查的目的、漏查风险及证据衔接；由规则说明生成并随计划保存 |
| `applicability` | APPLICABLE / NOT_APPLICABLE / UNDETERMINED |
| `readiness` | READY / WAITING_EVIDENCE / NOT_SCHEDULED |
| `required_inputs` | 当前缺失的输入 |
| `trigger` | 实例化该项的可复现依据 |
| `handoff` | 独立下游动作，可与任一结果并存 |

`rule_plan[]` 回答“这类规则要不要跑”，`checks[]` 回答“具体审哪一项”。

- APPLICABLE + READY：本轮执行；READY 不代表 PASS。
- APPLICABLE + WAITING_EVIDENCE：必须执行但缺材料，未补齐时为 INSUFFICIENT。
- UNDETERMINED：先补意图或解决意图/网表冲突，不得偷换成 NA。
- NOT_APPLICABLE：须有范围依据，结果为 NA。
- 需求要求某功能但网表未检出特征时，计划新增 REQ-A02 并报告 `REQUIRED_FEATURE_NOT_DETECTED`。

### 展开规则

- **全板通用**规则每板一项（`{"board": "BOARD"}`）；准备度按该规则所需资料判定。
  DOC-T01 逐 `intent.assemblies` 声明的装配状态一项。
- **逐位号**：每颗 IC/模组生成 DEV-C05 与 DEV-D05；每个连接器生成 DEV-D03、DEV-D05 与 PRO-D03。
  每颗齐纳、电源轨或板内 TVS 与每个保护门限脚（FAULT/OVP/UVLO/OCP/OTP 等）生成 PRO-C02 不误动作（NOTRIP）、动作有效（TRIP）两项；
  非地端全是信号网且直达连接器的 ESD/TVS 不另生成，记入该连接器 PRO-D03 的 `clamp_refs` 一并核对；
  热敏等传感器每个接到 IC 的检测脚生成 ANA-C04（开短路判别）。
  声明了 `intent.devices` 的位号，DEV-D02 带官方/符号双向差集，DEV-D05 带待复核引脚清单（不是结论）。
- **需求与覆盖**：每条需求实例化为 REQ-D01；另有六类覆盖审计项 DOC-Q01、REQ-Q01～Q04、DEV-Q01。
- **证据计算（E）**：READY 须当前网表指纹、文档指纹、准确型号/版本/定位、依赖物料 AVAILABLE 及必要模型输入齐全，
  否则 WAITING_EVIDENCE。每条匹配证据生成独立状态子项。
- **功能包**：汇总项 REQ-Q07 只汇总覆盖；功能包适用后生成成员规则，声明了电路时逐电路×工况，
  否则按功能包一次；各成员仍须按 [最小充分证据](evidence-proportionality.md) 核适用性。
  未检出也未声明的功能包汇总到一项 REQ-Q08，逐个确认不适用并给依据。
- **电平转换（LEVEL_SHIFT）**：用于独立转换模块和通用 GPIO 跨电压域互连。转换器位于已声明的 I²C/SPI/UART 等
  总线上时，把转换器列入该总线电路的 refs，不另声明 LEVEL_SHIFT，避免同一链路重复检查；此时 REQ-Q08 中的
  LEVEL_SHIFT 以“已并入 <电路 ID>”为依据关闭，不写成“不适用”。分立 MOSFET 转换器没有名称线索，须在 `intent.circuits`
  中声明；计算与规则归属见 [WCA 公式](wca-formulas.md#mosfet-双向开漏电平转换)。分立转换管会被功率开关检查器识别，
  它不是功率开关：在 `intent.power_switches` 中把它声明为 `role: "level_shifter"`（带出处），计划就不再生成
  DRV-E01、DRV-C02、DRV-D01 及 DRV-A03/A04 候选，其 VGS/RDS 改由电平转换电路的规则核对。
- **检查器**：清单写在同名顶层键并带 `<id>_version`，计划项 `object` 带 `<id>_digest` 绑定清单，
  `inventory_gaps` 保留缺口——有缺口不能判 PASS；最终校验会重建清单，不能编辑清单消缺口。

### 功能包依赖与状态核对

专家执行与 REQ-Q07 汇总先按最终计划的实际 `package`、`circuit`、`state`、`ref/refs` 核成员身份，
在现有 evidence/rationale 列出全部必需成员的准确 ID、所支持子义务和结果。规则编号相同不证明是同一电路；
未列 package 的计算或补查项按实际端点和判据判断是否必需，不机械纳入所有无包项，也不因无包而遗漏。
跨包成员只有在同一供电、信号、控制或保护路径构成真实依赖时才引用，并写逐跳路径及适用状态；
另一接口同名规则不能代替本接口电气检查。包内连接完成不代表电平、端接、供电或掉电成员已完成。

汇总先核成员适用性及实际违反：任一必需成员已确认 FAIL，父项不得因其他成员 INSUFFICIENT 改成
INSUFFICIENT；保留确认根因与其等级，再单列其余未知。没有确认 FAIL 而必需成员未闭合时才按具体
缺口给 INSUFFICIENT。纯覆盖审计项按自身覆盖判据评判，不能直接复制整个包的电气结论。

每颗关键器件从适用官方章节、表头及脚注逐脚列外围选值窗口，包括检测/配置电阻、时序、反馈、
电容、电感等实际使用项；按真实型号/档位、供电、模式、温度及容差角点验算 Min/Max。
外围器件自身耐压/功率通过不证明它满足 IC 的推荐选值窗口，标称值在窗内不证明全工况在窗内。
现有资料已证明越窗就按适用判据 FAIL；漏读适用参数属于执行覆盖缺失，不把正确计算器归为算术故障。

启动、运行和 OFF 分别画实际供能/信号路径，列独立外源是否仍在、默认脚态、非 failsafe 输入、
钳位/体二极管及受影响掉电域。启动时 Hi-Z、同一 3V3 供电、dead-battery 某脚行为不能证明全部
OFF 输入安全；反之，纯电池状态不能借不存在的外 5V 传播持续注入风险。每条排除依据限于其已证
工况，未证路径留具体缺口，不添加需求未承诺的零待机电流门槛。结果、父项、发现项和任务同步核
实际页码、型号、物理脚/网络与状态，避免把封装/文档错误误写为实体错连。

## 三、review-results.json（schema_version 2）

### 顶层字段

- `plan_digest` / `db_digest`：`validate_review.fingerprint()` 对 JSON 对象排序序列化后的 SHA-256（不是文件字节哈希）。
- `checks`：与最终计划 ID 集合完全一致的逐项结果。
- `findings`：唯一已确认缺陷/改善，一个根因可被多个检查引用。
- `scope_checks`：六个覆盖维度 `input_consistency`、`requirements`、`chains`、`states`、`datasheets`、`history`
  各指向对应覆盖审计项。表示覆盖审计完成，不是该域全部电气通过。
- `coverage`：各维度“对象→检查 ID 数组”的完整映射。有 `--db` 时机械检查 components、pins、nets、pages
  及 requirements 是否都关联至少一条检查；仅 PDF 时由页面/手工对象清单另审，不制作伪网表。
- `binding_version: 1`、`remediation_version: 2`（见 [报告与修改说明](report-and-remediation.md)）、
  `requirement_clarification_version: 1` 与 `requirement_clarifications`（无则 `[]`）、
  `workflow_version: 1` 与 `work_items`（见 [结论与准出](verdicts-and-release.md#共同根因归并为任务)）；
  关联 EXTERNAL_DATA/DESIGN_OPEN 证据不足项的任务带 `design_option`（见 [报告与修改说明](report-and-remediation.md#三证据不足项的电路改进建议)）。
- 复审另有 `revision_impact_version`、`revision_digest` 和必需项的 `reverification`，见 [改版复审](revision-review.md)。
- `summary` / `release` 可省略，由校验器计算；填了必须一致。

### 每项检查的目的与衔接

计划项的 `check_explanation` 由 `scripts/catalog.py` 逐规则生成并随计划保存，三个非空文本字段为：

| 字段 | 要回答的问题 |
|---|---|
| `purpose` | 本项具体在核实什么行为或能力？ |
| `risk_if_omitted` | 漏查后可能漏掉哪种错误或需求偏离？通过什么路径影响什么对象？ |
| `connections` | 复用哪些已核事实；本项产出给谁用；哪些相邻义务另查？ |

逐项执行时先读这三个说明，再用真实器件、物理路径、状态和需求确认适用范围。通用说明准确适用时可以复用；
拓扑专用、复合判据拆分、部分范围或 NA 等使通用说明不再准确时，在结果行同名 `check_explanation` 对象里
改写三个字段，不能改绑定的原判据。NA 说明为什么本机不暴露于该风险；纯下游说明本阶段可做什么及后续负责什么。
结果字段存在时必须完整非空；机器检查只能核结构，具体因果和检查合理性仍由审查者逐项确认。

实际证据依赖在已有 `rationale/evidence` 中写准确检查实例 ID、所用数值/事实、适用状态和边界。
只列规则编号、同一器件或“详见其他检查”不构成依赖证据。不适用的衔接不建立；独立检查可以说明直接来自
需求/手册、无其他检查前置。目录里的关系只是复用指引，不要求把列出的规则全部执行，也不要求堆成固定流程。
互相引用时注明各自产出的不同事实，不让两个尚未证明的结论相互担保。已有覆盖父子项与共同根因任务照常使用。

讲解和报告依次说明目的、漏查风险、本次核对方法、实际结果与最小后续动作。定义清楚可停止的范围：
连接项确认接法即完成其职责，不追加完整应力证明；计算有适用边界和足够裕量后不因没有实测继续索取参数。
“漏查可能损坏器件”不自动生成 P0；实际工况、保护协调及允许的永久安全失效仍按需求分别判断。

例如反激：DRV-T01 确认储能/送能及漏感吸收路径；DRV-C01 复用该路径计算吸收器件应力；
PRO-C02 给保护门限，PRO-C01 联合输入能量与耐受计算停能窗口；DRV-C02 复用峰压、驱动与工况核功率管。
保护与应力可能需要联合求解，共用一份计算并分别引用，不能把同一停能缺口报成多个独立严重故障。
此例只说明分工，不代表任何具体设计或历史报告已按新方法通过。

手工补查项同样复制当前规则说明，按实际对象在结果中细化。旧记录缺此字段时保持可读，并明确未补写说明；
不能渲染时偷偷取最新目录文字，让旧结果看起来已经按新规则重新审查。

### 对象上下文录入

结论录入前，在审查证据中记录实际物理脚、装配/工作状态、逐跳路径及出处、已核范围和未知边界，
由现有 `evidence` 定位引用，无需新 JSON 字段。供电、返回及旁路电容按实际节点重新配对，不能从邻近位号
或另一器件的记录猜对象；额定补证消费 `qualification_refs` 并核实际电容轨窗口，分组端身份不能代替资格。

同一 IC 有多个隔离电源/地域时，按原生供电网络与返回网络逐组配对，在 `intent.decoupling.groups`（schema v2）
声明官方供电脚、返回脚及各自直接电容；不要仅按芯片位号把两域返回脚池化。声明须有官方脚义与当前
归网依据，不能为避开候选而改地网、作用域或保证条件。

去耦逐组先列“实际供电脚→直接网络→已贴电容→直接返回网络→实际返回脚”，并列出本段电容为空、
容量不可解析与串联边界的事实。磁珠、0Ω、跳线或开关另一侧的电容只进入独立的供电/滤波分析，
不能计入本段普通旁路容量，也不能用普通旁路说明覆盖专用滤波/飞跨组。PWR-T03 可通过完整的零电容
清单核对；PWR-D02/C09 是否合格须另对本器件、本脚组、工况的条款判断。有适用替代接法/阻抗证明才可
据此放行；资料尚不能证明替代合规时记具体 INSUFFICIENT，不从“没有直接电容”统一判实物失效。

人工旁路补查必须保留自动生成项。`object` 用独立 `manual_group`，准确 `ref`、`nodes`、`return_nodes` 与
已声明 `state`；官方角色未在清单设备声明时，补 `manual_pin_roles`（物理节点→`power/return`）
与 `manual_pin_citation` 的独立官方脚表出处；`manual_pin_source` 用绝对 `path`、文件 `sha256` 和
`locator` 绑定原文。节点必须在当前原生输入存在；已有官方映射的冲突角色不能以人工声明覆盖。
不能以名称候选代替核验。确认非供电脚的候选
用 `manual_group_role: "excluded_candidate"` 与实际 `other` 脚角色记录；D/C 判 NA 仍须独立用途依据。不得带任何 `decoupling_*` 生成绑定字段。人工结论仅证明该独立判据，不恢复自动条款/资格
缺口，也不能解除输入完整性失败带来的全板 NO_GO。输入资格缺口只影响确实依赖该事实的行：
某器件缺功能名只影响该器件自身引脚角色，不改变网络连通，其他器件去耦组的电容、回流与边界照常审结；
不能把同一缺口复制成每个去耦行的 INS（见 [执行一致性](execution-consistency.md#2-局部-pass-不扩展为路径或系统-pass)）。
受影响的行引用原生导出逐端点比对；局部电气结论还须具体用途、原厂条款、状态及参数证明，不能仅从 XML 推断合格。
逐项证据记录取证来源、实际端点、装配及已核范围；工具验证绑定一致性，不代替手册条款核实。

接口按当前协议列实际端点、官方信号角色、各段串联/转换/隔离/保护器件、状态与外接/电缆边界。
USB 的 D+/D−、Host/Device 与供电 Source/Sink、CC/Rp/Rd 分别核相应条款，UART/SPI 按自身角色核。
窄的标准脚义/方向项可用标准及器件手册闭合；准确机械/焊盘视图与已指定对端的兼容保证另审，
未指定外卡/主机按 [本体与系统范围](evidence-proportionality.md#模块本体完整系统与制造核准) 处理。

`rationale`、`missing_inputs`、`impact_assessment` 每个字段和关闭任务分别核同一实际对象/状态/因果。
任务的 prerequisite、steps、impact_review、verification、avoids 不能借另一个根问题填充；输入取得方法与
验收须能关闭所关联的具体判据，不以“执行发现项说明”等通用指令替代。计算修订同步所有引用该值的结果与
结构化任务，核单位、公差及不利方向；正确理由、绑定或 locator 不证明其余字段正确。
物理脚说明同时核“位号、物理脚号、官方脚名、网络”；别名与符号编号差异注明映射依据，不把另一脚的
名称带入 locator/rationale。最终结果修改后，从最终子项 ID 与状态重新核父项的理由、缺口和汇总，
不得保留旧草稿的“子项证据不足”文字。已完成连接或计算子项不承担未解决的其他条款。
功能包汇总引用成员结果与现有任务，不重复收集同一材料；汇总等级注明最高可信后果对应的成员与条件，
不统一压低成员风险，也不将其复制给所有成员。

### 阵列与多单元器件的内部通道

追踪信号跨越电阻/电容阵列、分体或多单元器件前，先从完整原生缓存的各 unit 引脚定义与
原厂内部连接图确认物理 pin 的配对、元件类型和该装配的导通条件，再与每个外部 pin/net
逐端对账。保存各通道的两端物理 pin、所属 unit、数值/公差、实际源端与接收端和引用位置。
网表只列各引脚的外部网络，网络邻居不证明器件内部通道；编号相邻或图上排布也不证明配对。
缺内部映射时保留具体路径 INSUFFICIENT，不凭编号顺序推断跨阵列的端到端连接。

按确认的通道核正常态、启动与单域掉电的源/接收端供电和应力；整改方案、影响分析、条件
计算及下游移交必须指向同一真实通道。发现配对错误时保留旧记录，逐条修正受影响路径与
任务，重新对账父子结果；不把记录修正当作硬件已改动或新增已发生故障。硬件可实现某个
方向/PIO功能不证明实际固件 pinmux 或模式，配置与默认高阻/恢复顺序仍需独立受控证据。

### 逐行语义复核

录入与最终校验前，逐行用实际对象上下文对照 `rationale`、`missing_inputs`、影响评估及关联关闭任务：

- 对每条需求，将原文与本行 criterion 中并列的功能、工况前提、交付和范围排除分别列为子义务，
  在现有 evidence 定位每项实际证据、相关检查 ID 与状态。明确排除认证、实测或某种使用状态，
  只证明该排除子义务；不能据此让同条需求中的电气实现或保证前提一起 PASS。必要时按上文
  “拆分实例的命名”补查子义务，保留自动原项及完整覆盖关系。
- 需求整项只有全部适用子义务已 PASS（或有来源证明 NA）时才能 PASS。子义务有确认 FAIL 时
  整项按真实违反给 FAIL；没有确认 FAIL 但仍有必需证据不足时整项为 INSUFFICIENT，写明具体
  gap_cause、未知和关闭条件，blocking 按该义务现有准出依赖判断。最高潜在级仅引用实际相关
  子义务的可信物理后果与条件，确认缺陷和潜在风险分开；复用既有唯一根因任务，不重复计缺陷。
  纯范围排除项可独立 PASS，不能因为全板其他项未闭就自动传染 INSUFFICIENT；相反，复合项不能
  用范围 PASS 掩盖它明确依赖的本体义务。资料缺口不是需求待决，不改成 REQUIREMENT_OPEN。

- 将文字中的每个位号、物理脚、网络与本行对象/状态核对。额外对象只能作为有定位的供电、返回、保护或
  共同证明路径出现，说明其与本行的关系；从其他行继承而无因果关系的前缀、脚名、数值须删除或重写。
  旁路、储能等器件清单按本行所核电源脚及实际贴装变体的连接路径列出，避免把全板清单带入局部判据。
- 用“本行要判断的义务→已核路径/条款→剩余未知→补证或修改→复验判据”核闭环。接口防护的缺口须对应
  该接口的实际外接边界；另一个接口的浪涌、旁路或源许可不能独自关闭本行。无源触点的候选排除说明须
  引用其真实角色，不能借相邻 IC 的旁路说明代替。
- 共享的是可定位的证明，不是整段结论。确实共用同一路径/工况的对象可引用同一证据，分别说明它覆盖的
  范围；状态、对端、故障路径或关闭资料不同的项分别写。不要以禁止共享文字的机械规则制造重复工作。
- 修改理由或关联关系后重新核父项、澄清项和任务；已完成的板级窄判据与真实外部未知分别留记录。
- 运行态与掉电态分别核取证。正常运行接口项引用运行供电、输入电平/共模和对端边界；Ioff、掉电泄漏、
  UVLO/关断条件只支持其实际适用的状态与判据。某个字段写错状态时修正该字段及关联任务，仍保留
  本行真实未闭合的外部共模等缺口，不用掉电补证替代运行态证明，也不把整行自动改为 NA。
  原生绑定只核记录一致性，`quality_screening` 只提示疑点，两者都不能证明文字中的工程主张正确。

### 预交付的范围与必要性复核

最终台账与报告交付前，按 [交付前的必要性复核](evidence-proportionality.md#交付前的必要性复核) 逐条反查补证、澄清及移交的关闭条件。

### 单条检查

```json
{
  "id": "SIG-T04.PATH-U1-J1",
  "binding": {
    "object": {"refs": ["U1", "J1"], "nets": ["SENSE_A", "SENSE_B"], "state": "RUN"},
    "criterion": "RUN 时 U1.4 与 J1.1 必须导通"
  },
  "applicability": "APPLICABLE",
  "review_result": "FAIL",
  "evidence_confidence": "A",
  "evidence": [{"source": "db.json", "locator": "nets.SENSE_A; nets.SENSE_B"}],
  "rationale": "要求的检测端点不连通，见路径表 PATH-01。",
  "severity": "P1",
  "finding_id": "F-001",
  "blocking": true,
  "disposition": "OPEN",
  "handoff": {"required": false}
}
```

- `binding.object`/`binding.criterion` 是实际已审范围，与同 ID 计划的 object/criterion 完全一致；
  `evidence` 和 `rationale` 只支持这个对象、配置、工况和判据。复用结论前核对物理脚、网络及要求，
  不能因 ID 相似、同一 IC 或同一功能组就移用。
- 所有结果含非空 `rationale` 与可定位 `evidence`。PASS/FAIL 只能 A/B；INSUFFICIENT 必须 C 并给
  `missing_inputs` 和 `potential_severity`（REQUIREMENT_OPEN 除外）；非 FAIL 不填 severity。
- 每项证据不足（REQUIREMENT_OPEN 与 REQ-H02 历史处置除外）给 `impact_assessment` 的五项非空字段，校验始终强制；
  内容按 [危险度分类原则](verdicts-and-release.md#证据不足的危险度分类原则) 逐项判定；非空字段不等于危险度可靠。
  缺影响依据的旧报告校验不通过，须按当前规则重新分级，不改写旧结果或工程指纹来冒充新审查。
- 新报告写 `requirement_clauses_version: 1`：每个 REQ-D01（需求状态 OPEN/DEFERRED 与 NA 除外）给 `requirement_clauses`，
  把需求原文按顺序完整拆成条款（拼接后等于原文），逐条标类别：

  | 条款形式 | kind | 结论 |
  |---|---|---|
  | 规定本设计应达到的量值、功能或状态（=、≤、≥、±、须、不得、支持、保持、可靠进入） | OBLIGATION | `result` 取 PASS/FAIL/INSUFFICIENT/NA，可附 `check_ids` |
  | 工况与前提（允许…、输入…范围、给定的器件参数）、审查方法与输入取值（按…审查、公差取…、先读…再登记、移交下游）、范围说明 | PREMISE | 不带结论；作用于所有相关行 |

  格式：`[{"text": "原文片段", "kind": "OBLIGATION", "result": "PASS", "check_ids": [...]}, {"text": "原文片段", "kind": "PREMISE"}]`。
  行结论 = 义务条款中最差的结论（FAIL > INSUFFICIENT > PASS > NA），校验强制。前提条款里的要求由相关器件/电路行执行，
  其他行发现的缺陷不连带本行；需求原文把该缺陷写成义务（如“各连续受电元件不得超出持续功率额定”）时才在本行判。
- INSUFFICIENT 必填 `gap_cause`（校验始终强制）：REQUIREMENT_OPEN、EXTERNAL_DATA、DESIGN_OPEN、
  REVIEW_INCOMPLETE、USER_DEFERRED，含义见 [最小充分证据](evidence-proportionality.md#复核每条证据不足)。
  纯下游项不是 INSUFFICIENT，用阶段 NA。EXTERNAL_DATA / DESIGN_OPEN 另写以 missing_inputs 原文为键的
  `input_requests`（why_decisive / required_scope / acquisition / closure_criterion），其他原因不写。
- 计划行带 `proposal.result = PASS` 而结论为 FAIL/INSUFFICIENT 时，须给 `proposal_override`（code 与 reason），
  code 的封闭清单见 [通用件最弱档基准](commodity-floors.md#计划预判dev-c01-逐颗行)。
- 阶段 NA：`review_result: NA` + `na_reason: OUTSIDE_SCHEMATIC_STAGE`，`applicability` 保持 APPLICABLE，
  `handoff.product_requirement_status: PENDING_VERIFICATION`，不建 work_item；完整写法见 [纯下游验证项](verdicts-and-release.md#纯下游验证项)。
  复合义务不能整体 NA；测试义务条款写 `result: NA`、`na_reason: OUTSIDE_SCHEMATIC_STAGE`，
  `check_ids` 链接独立阶段 NA 检查，不得只改条款结果让测试消失。
- 普通 NA 必须 NOT_APPLICABLE；修改自动计划的适用性需 `applicability_evidence`。UNDETERMINED 只能落 INSUFFICIENT。
- `disposition`：FIXED_VERIFIED / RETRACTED 只用于当前 PASS/NA 并须 `closure_evidence`；ACCEPTED 保留
  FAIL/INSUFFICIENT，附 `acceptance`（by/date/scope/reason/record，来自真实授权记录）。P0/P1 潜在未知默认阻断。
- 必需 handoff 的 receivers/constraint/verification 不可空；ACCEPTED/VERIFIED 须有 evidence；
  取消计划中的必需 handoff 须 `handoff_evidence` 留据。handoff 随图交出，OPEN 不阻断冻结。
- `manual_verification`：自动工具因自身限制（映射不全、模型不支持等）不让某项判 PASS，而审查时已不靠该工具、
  逐项对照网表和原厂资料核对完时，按核对结论判 PASS/FAIL，附
  `manual_verification: {tool_limitation, sr_improvement, method, evidence}`：
  SR 为什么做不到（哪个检查器、缺什么映射或模型）、建议怎么改进 SR（具体到规则、别名或模型）、这次怎么核对的。
  这是审查者（通常是 agent）自己的核对，不写成“人工核对”，除非确实有人参与并留有记录。
  多条检查因同一限制、用同一核对方法时写相同文字，报告会合并显示。只能用在工具确实拦了的行上；
  这类行不算 REVIEW_INCOMPLETE、不建 work_item，gate 把工具限制列入 `sr_improvements`，不影响准出。
  资料或设计本身没给出的数值不是工具限制，仍按 EXTERNAL_DATA / DESIGN_OPEN 处理。

### 发现项

每个 `findings[]` 含 id、kind（DEFECT / IMPROVEMENT）、severity、check_ids 及非空的 `title`、`observed`、
`criterion`、`impact`、`scenario`、`root_cause`、`recommendation`、`verification`、`severity_reason`、`remediation`；
`location` 含 pages/refs/nets 字符串数组，缺图面时写“未定位：缺某版本 PDF”，不编造页码。

- DEFECT 与其 FAIL 检查双向引用；一个根因一个 ID。严格绑定下，DEFECT 的 check_ids 都必须是该 finding 的 FAIL。
- location 覆盖各被检查的主对象（计划 object.ref、object.node 所属位号、object.net），不用共同电源或宽泛功能组代替。
- IMPROVEMENT 仅 P3，关联判据必须已 PASS。
- 例：STRAP 缺陷不能挂到已满足的 EN 判据；装配/等效值与低电平/上升时间是独立判据，不能互相代判。

## 四、校验与门禁输出

    python3 scripts/validate_review.py review-plan.json review-results.json --db db.json --lint lint-cold.json --lint lint-hot.json --require-actionable --require-bindings --json review-gate.json

- 退出 0 表示台账有效（结论 NO_GO 也可正常交付）；2 表示台账有错。冻结门加 `--require-release`，NO_GO 也退出 2。
- 校验只证明记录一致，不验证来源文字真实、计算合理或判据穷尽。空计划、遗漏对象、C 写 PASS、NA 冲突、
  无位置/改法、虚假汇总、陈旧规则指纹均被拒绝。
- **自动扫描候选处置**：两次 `--lint` 提供冷/热 JSON；`lint_reviews` 每条含 `run_digest` 与
  `items`（finding 索引→结果检查 ID 数组），全部候选都要处置；证据计算候选须关联对应状态子项。
  无证据时也保存一次未带证据的热跑。仅 PDF 模式明确 NA 并留依据。
- **输出**：`summary`（检查结果计数、唯一缺陷及 P0–P3）、`categorized_summary`（当前/历史检查、唯一缺陷、
  唯一任务、必需移交及其状态）、`insufficient_by_cause`、`requirement_clarification_summary`、`workflow`、
  `release`/`blockers`、`remediation_validation`、`binding_validation`。
- **quality_screening** 提示理由/影响跨范围复用、位号与声明范围不相交，以及补证对象和接口模式错配。
  影响描述逐字段核对，不以正确的理由或证据位置替代因果核验；原样回显绑定对象/判据不能证明分析成立。
  PWR-C10 的 `qualification_refs` 指向实际已贴电容，连接器身份不能替代电容额定证明；USB 方向分析不能只复用 UART/SPI 的角色。
  仅作提示，不增添缺陷、不改变 release；共享依赖可明确加入对象范围并核对，零提示不证明审完。

## 五、规则指纹与重新审查

计划写入 `review_engine`：SKILL.md、`references/` 与 `scripts/` 的逐文件 SHA256 及总摘要（含未提交修改，
排除测试、缓存、隐藏文件、`.pyc` 和 `~` 备份）。任何规则文字修改都会改变指纹。

- 指纹变化后以当前输入重新生成计划并完整审查；旧 PASS、旧缺口列表不能代替本轮判断。
- 冷/热合并只接受同一指纹；CLI 校验要求当前指纹。
- 原始 datasheet、已验证模型和计算数据可复用，但先复核型号/版本、工况、保证条件和当前判据。

显式 `intent.devices` 中的关键器件按逐器件身份、工作条件与特殊脚检查展开，不能因位号不是 U/M 而遗漏；连接器仍走其专属检查，不重复生成未用脚项。声明只补覆盖，不替代身份、资料与结果审核。


### 保护时序审查附注

对以关断/响应时间不足为依据的结论，在本项证据或共享记录中给出故障后果、允许窗口、实际响应界、裕量、温度范围及关闭阶段。
可在结果行用可选`timing_assessment`对象记录上述同名英文字段（见最小充分证据）；或用`timing_assessment.evidence`
列出包含完整分析的共享文档定位。它是人工工程证据，不替代`impact_assessment`、HANDOFF或风险接受。
质量筛查的`TIMING_BLOCK_WITHOUT_WINDOW`只是需复核提示；补充一个字段不会使设计自动通过。

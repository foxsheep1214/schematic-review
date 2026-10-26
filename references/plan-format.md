# review-plan.json 格式

> 读者：审查员。

审查数据分四份文档：[intent 格式](intent-format.md)（`intent.json`，按需求和设计结果写，不抄设计方的意图文件）、[计划格式](plan-format.md)（`review-plan.json`）、[结果格式](results-format.md)（`review-results.json`）、[校验与重新审查](gate-and-rerun.md)（门禁输出与规则指纹）。计划只决定每项的规则、适用性和准备度，不提前制造 PASS/FAIL；结果另存，由 `validate_review.py` 对账。常规命令见 [SKILL.md](../SKILL.md)。

## 二、review-plan.json（schema_version 7）

检查项带 `owner`、`check_key` 和 `requires`，计划带所属表 `owners` 和接口 `interfaces`，功能框架带 `not_asked`；电路检查项只在网表上有它问的机制时生成
（见下文“电路规则的前提”）。更早格式的计划（含据它写的结果）不再读，
校验、合并（`--merge-plan`）和改版比对（`--old-plan`）都拒收，按当前规则重新生成计划、重新审。

### 生成与合并

- 网表扫描 `lint.py --plan-json review-plan-cold.json` 保存计划和候选；审查者要补的检查登记到 `intent.rule_gaps` 后重新生成，计划工具没写的检查项（自动扫描检查项与改版记录以外）在合并和校验时都被拒。
- intent 声明电路时两次扫描都带 `--candidates record/circuit-candidates.json`；计划顶层 `circuit_candidates` 记候选文件的 `db_sha256`、`rules_version`、候选编号、决定和未归属器件，
  功能框架的 objects 直接取电路（即候选经决定后的）成员；候选文件随计划一起打包（`pack_review.py --circuit-candidates`）。
- 合并扫描 `--merge-plan review-plan-cold.json --plan-json review-plan.json` 产生**唯一最终计划**。
  合并要求 `db_sha256` 与当前输入一致且规则指纹相同；相同 ID 的对象/判据冲突时拒绝自动覆盖。
- 匹配证据后保留基础覆盖项，按 evidence ID 生成带 `parent_check_id` 的状态子项；基础项只汇总覆盖，不能代替子项结果。
- 计划合并不读取或迁移结果；后续补查先更新计划，再更新 digest 和逐项结果。
- 补查项按 `intent.rule_gaps` 生成，`id` 为 `规则编号.GAP-<缺口编号>.锚点`，`rule`/`method`/`domain` 随总表。
- **拆分实例的命名**：一条规则需要逐对象或逐判据给出不同结果时，逐个登记规则缺口，缺口编号写成
  `<对象>[-<判据>]`，对象用位号、网络或电路 ID，判据用简短大写词。例如全板项 DEV-C01 逐颗判定时登记
  `C12`、`Q3`，IC 脚经串联电阻接高轨的脚工具已逐脚生成（`DEV-C01.PIN.<位号>-<脚号>`，见 [阻容应力](commodity-floors.md#计划预判dev-c01-逐颗检查项)），工具没覆盖的（如经齐纳链或多颗电阻）才登记，如 `U2-FAULT`（检查项 `DEV-C01.GAP-U2-FAULT.U2`）；PWR-C02 拆窗口与调节能力时登记 `U1-WINDOW`、`U1-REGULATION`。
  自动生成的原计划项（如 `DEV-C01.BOARD`）保持不变（校验会按保存的输入重建它），在结果检查项写
  `split_out: [拆分实例 ID…]`：原项的结论只覆盖拆出实例**以外**的对象，拆出的对象各自给结论。
  这样一颗 C201 缺规格只让 `DEV-C01.GAP-C201.C201` 资料不足，其余已核对象仍可让 `DEV-C01.BOARD` 通过，
  不会被一个对象拖成整板资料不足。拆出实例须同规则、只属于一个原项，且不再嵌套拆分（`validate_review.py` 检查）；
  原项 rationale 写清其余对象核到了哪些、依据是什么。报告在拆出实例下注明所属原项。
  对 DEV-C01/02/03/04 的整板待核项先定位实际器件、额定/寿命/精度判据，保留与原检查的显式映射。
  不另造同一对象/工况/判据的重复检查项；启动与运行只有检查内容不同才分开。不同控制器的功率级即使同级风险，
  仍按独立关闭条件分任务。筛查 `BROAD_CHECK_NEEDS_LOCALIZATION` 只提示定位，不自动把汇总项变PASS。

### 检查项字段

| 字段 | 含义 |
|---|---|
| `id` | `规则编号[.实例键].对象`，如 `RST-T02.U3.SYS-RST-N` |
| `rule` / `method` / `domain` | 规则编号、方式代码、内容域代码，须与总表一致 |
| `object` | 对象：覆盖维度、功能电路、全板、网络、位号、引脚或页码 |
| `criterion` | 本项判据 |
| `applicability` | APPLICABLE / NOT_APPLICABLE / UNDETERMINED |
| `readiness` | READY / WAITING_EVIDENCE / NOT_SCHEDULED |
| `required_inputs` | 当前缺失的输入 |
| `trigger` | 实例化该项的可复现依据 |
| `handoff` | 独立下游动作，可与任一结果并存；`constraint`/`verification` 逐条写接收方要做和要测的事，不写“执行 X 原文及其全部工况”这类只换编号的套话（`TEMPLATED_HANDOFF` 提示） |
| `question` / `function_id` / `aspect` | 电路检查项有：按规则模板填了电路、位号、状态和需求窗口的问题；所属功能框架；方面（= 规则标题）。电路拥有的器件检查项（器件身份、引脚、应力、工况、它某颗器件上的扫描发现）也预绑到该电路的框架（`function_id`、`aspect` = 规则标题，没有 `question`），在功能里按方面判，`judgements` / `open` 用 `check_ids` 可收窄到某颗器件的检查项；全板拥有的检查项不绑。问题里不许有禁止句（“不得…”“不把…外推”），校验 `question_errors` 拒绝，审查员补加的检查项同样受限 |
| `requires` | 带前提的电路检查项才有：`{id, found[, unread]}`，前提名（`catalog.SUBJECT_REQUIRES`）、网表上满足前提的器件、网表说不清的器件；检查项 `object.ref` 取 `found`（没有时取 `unread`）的第一个 |

`rule_plan[]` 回答“这类规则要不要跑”，`checks[]` 回答“具体审哪一项”，`functions[]` 是功能框架：
每个 intent 电路一条，含 `id`（`FN-<电路 id>`）、`question`（由成员问题归纳，审查员可改）、`objects`、`states`、
`members[]`（检查项 id、规则、方面、状态）、`blind_spots`（每条问了的电路检查项的盲区一句）、`not_asked[]`
（前提不成立、没有问的规则：`rule`、`aspect`、`requires`、`why`）、`checklist`
（判“证据不足”之前的五步原文）和 `bounds[]`（框架里器件对应的[工作点定界表](bounding-table.md)的格：`cell`、`refs`、`parameter`、
`side`、`methods`（按顺序）、`formulas`、`fallback`；NTC 按 NTC、电解按电解、IC 另按核实过的角色取格）。审查员照框架写功能判定，不翻规则书。

- APPLICABLE + READY：本轮执行；READY 不代表 PASS。
- APPLICABLE + WAITING_EVIDENCE：必须执行但缺材料，未补齐时为 INSUFFICIENT。
- UNDETERMINED：先补意图或解决意图/网表冲突，不得偷换成 NA。
- NOT_APPLICABLE：须有范围依据，结果为 NA。
- 需求要求某功能但网表未检出特征时，计划新增 REQ-A02 并报告 `REQUIRED_FEATURE_NOT_DETECTED`。

### 展开规则

- **全板通用**规则每板一项（`{"board": "BOARD"}`）；准备度按该规则所需资料判定。
  DOC-T01 逐 `intent.assemblies` 声明的装配状态一项。
- **逐位号**：每颗 IC/模组生成 DEV-C05 与 DEV-D05（位号不是 U/M、但有原生 power_in/out 脚、三脚以上且未归为
  分立器件或连接器的，如 Reg1 稳压器，也按有源器件生成）；每个连接器生成 DEV-D03、DEV-D05 与 PRO-D03。
  每颗齐纳、电源轨或板内 TVS 与每个保护门限脚（FAULT/OVP/UVLO/OCP/OTP 等）生成 PRO-C02 不误动作（NOTRIP）、动作有效（TRIP）两项；
  非地端全是信号网且直达连接器的 ESD/TVS 不另生成，记入该连接器 PRO-D03 的 `clamp_refs` 一并核对；
  热敏等传感器每个接到 IC 的检测脚生成 ANA-C04（开短路判别）；传感器接电源轨的一端和轨上 IC 的供电脚不算检测脚。
  声明了 `intent.devices` 的位号，DEV-D02 带官方/符号双向差集，DEV-D05 带待复核引脚清单（不是结论）。
- **需求与覆盖**：每条需求实例化为 REQ-D01；另有六类覆盖审计项 DOC-Q01、REQ-Q01～Q04、DEV-Q01。
- **保证值核对（E）**：网表或检查器定出对象，计划检查项一律 WAITING_EVIDENCE，审查者按两端规格书保证值经功能判定作答。
- **功能电路**：汇总项 REQ-Q07 只汇总覆盖，由工具写出：计划把它绑定到同类电路的全部适用检查项（`bound_checks`），各检查项都有结论且至少一项不是 NA 时 `derive_rows.py` 写它为 PASS（绑定检查项全为 NA 时脚本不写，由审查员填并写依据），不复制任何子项的结论；手填结论不同被拒绝；功能电路适用后生成电路检查项，声明了电路时逐电路×工况（答案不随工作态变化的电路检查项
  每电路一项，检查项的 `object` 不带 `state`，见 `catalog.STATE_INVARIANT`），否则按功能电路一次；各检查项仍须按 [最小充分证据](evidence-proportionality.md) 核适用性。
  未检出也未声明的功能电路汇总到一项 REQ-Q08，逐个确认不适用并给依据。
- **电路规则的前提**（一致性方案第 2 条）：`catalog.SUBJECT_REQUIRES` 给部分“类型 × 规则”一个由网表判断的前提，
  如 DRV-C02 要电路里有 MOSFET/BJT，PWR-C15 要电路或与它相接的 IC（经电路里的电阻接到开关栅极、或脚在电路网上）有
  反馈/补偿脚、电路里的 IC 有稳压输出脚，或有分压/光耦把输出送到 IC，RST-* 要有带复位、使能或启动配置脚的 IC；全表见
  [规则总表](check-catalog.md#功能电路)。前提不成立就不生成这一项，框架记 `not_asked`，报告在“各功能的判断”下列
  “FN-… 未问：方面（电路里没有…）”。地按网名和各域的参考地（`_RTN` 一类回流）认。网表说不清时照问：器件不在网表、
  类别未知（两脚件不算晶体管或 IC，整流桥和符号名出热敏/压敏的件不算未知）、IC 没有脚名。漏问的经 `intent.rule_gaps` 补回。
  一种类型对某电路问到的规则不到一半时，计划诊断 `CIRCUIT_TYPE_MISFIT` 并在计划命令输出里提示换类型，或不建这块电路、
  让器件走器件检查项。
- **电平转换（LEVEL_SHIFT）**：用于独立转换模块和通用 GPIO 跨电压域互连。转换器位于已声明的 I²C/SPI/UART 等
  总线上时，把转换器列入该总线电路的 refs，不另声明 LEVEL_SHIFT，避免同一链路重复检查；此时 REQ-Q08 中的
  LEVEL_SHIFT 以“已并入 <电路 ID>”为依据关闭，不写成“不适用”。分立 MOSFET 转换器没有名称线索，须在 `intent.circuits`
  中声明；计算与规则归属见 [WCA 公式](wca-formulas.md#mosfet-双向开漏电平转换)。分立转换管会被功率开关检查器识别，
  它不是功率开关：在 `intent.power_switches` 中把它声明为 `role: "level_shifter"`（带出处），计划就不再生成
  DRV-E01、DRV-C02、DRV-D01 及 DRV-A03/A04 候选，其 VGS/RDS 改由电平转换电路的规则核对。
- **检查器**：清单写在同名顶层键并带 `<id>_version`，计划项 `object` 带 `<id>_digest` 绑定清单，
  `inventory_gaps` 保留缺口——有缺口不能判 PASS；最终校验会重建清单，不能编辑清单消缺口。

### 功能电路依赖与状态核对

专家执行与 REQ-Q07 汇总先按最终计划的实际 `circuit_type`、`circuit`、`state`、`ref/refs` 核检查项归属，
在现有 evidence/rationale 列出全部必需检查项的准确 ID、所支持分项要求和结果。规则编号相同不证明是同一电路；
未列 `circuit_type` 的计算或补查项按实际端点和判据判断是否必需，不机械纳入所有未归类的项，也不因未归类而遗漏。
跨类型检查项只有在同一供电、信号、控制或保护路径构成真实依赖时才引用，并写逐跳路径及适用状态；
另一接口同名规则不能代替本接口电气检查。连接类检查项完成不代表电平、端接、供电或掉电检查项已完成。

汇总先核检查项适用性及实际违反：任一必需检查项已确认 FAIL，父项不得因其他检查项 INSUFFICIENT 改成
INSUFFICIENT；保留确认根因与其等级，再单列其余未知。没有确认 FAIL 而必需检查项未闭合时才按具体
缺口给 INSUFFICIENT。纯覆盖审计项按自身覆盖判据评判，不能直接复制整类电路的电气结论。

每颗关键器件从适用官方章节、表头及脚注逐脚列外围选值窗口，包括检测/配置电阻、时序、反馈、
电容、电感等实际使用项；按真实型号/档位、供电、模式、温度及容差角点验算 Min/Max。
外围器件自身耐压/功率通过不证明它满足 IC 的推荐选值窗口，标称值在窗内不证明全工况在窗内。
现有资料已证明越窗就按适用判据 FAIL；漏读适用参数属于执行覆盖缺失，不把正确计算器归为算术故障。

启动、运行和 OFF 分别画实际供能/信号路径，列独立外部来源是否仍在、默认脚态、非 failsafe 输入、
钳位/体二极管及受影响掉电域。启动时 Hi-Z、同一 3V3 供电、dead-battery 某脚行为不能证明全部
OFF 输入安全；反之，纯电池状态不能借不存在的外 5V 传播持续注入风险。每条排除依据限于其已证
工况，未证路径留具体缺口，不添加需求未承诺的零待机电流门槛。结果、父项、发现项和任务同步核
实际页码、型号、物理脚/网络与状态，避免把封装/文档错误误写为实体错连。

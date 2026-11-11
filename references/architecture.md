# SR 架构说明

> 读者：SR 维护者（审查员看 SKILL.md 的“架构”一节即可）。

SKILL.md 的“架构”一节是总图：五个步骤的流水线、每步谁做、不变的决定、改架构先问人。本页是它的明细：
步骤之间传哪些文件、每个文件的格式版本、每个脚本属于哪一步，以及历次架构决定。
本页的数据文件表和脚本表由 `scripts/tests/test_architecture.py` 对照代码检查：新增、删除脚本或改格式版本而不改本页，测试失败。

## 一、步骤之间传的文件

每一步只读前面各步写下的文件，自己只写下表里属于它的文件。审查员的声明集中在 `intent.json`，
它不是某一步的产物，是审查员给“读入”和“出计划”两步的输入。

| 文件 | 谁写 | 写在哪一步 | 格式版本 | 内容 |
|---|---|---|---|---|
| `db.json` | 工具 | ① 读入 | — | 网表、BOM 列、页、符号脚：图上实际是什么；KiCad 自定义字段、原始 Value、Val 优先的电气值及解码出处；同板 R 前缀歧义保留候选并阻止数值推断 |
| `requirement_source`（需求原文抄录） | 工具 | ① 读入 | 1 | 需求文档逐字抄录与 sha256 |
| `datasheet-audit.json` | 工具 | ① 读入 | — | 每颗物料的资料是否找到、是否核实 |
| `record/requirements.json` | 工具 | ① 读入 | — | `requirement_source` 的抄录输出，打包留档 |
| `review-plan-cold.json`、`lint-cold.json` | 工具 | ①② 冷扫 | — | 冷扫的中间计划与扫描输出；`lint-cold.json` 交 ④ 校验与 ⑤ 打包 |
| `资料请求.md`、`datasheet-resolution.json` | 工具 / 审查员 | ② 出计划 | — | 资料请求清单；补齐资料后的解析记录，供重审计 |
| `intent.json` | 审查员 | ①② 的输入 | 5 | 需求理解、需求澄清（问用户的问题与答复）、任务剖面、电源轨、器件类别与配置组、电路取舍、装配状态、规则缺口、产品基线（`guideline_baseline`） |
| `record/circuit-candidates.json` | 工具 | ② 出计划 | 2 | 候选及带物理网的成员、按角色持有/唯一所属、隔离侧别证据；接口附默认工作态（计划标“默认状态，未经需求确认”） |
| `review-plan.json` | 工具 | ② 出计划 | 8 | 功能树、每个检查项检查、功能框架、各检查器清单、接口；设计准则库有规则时另有 `guidelines`（适用的共用设计准则与覆盖） |
| `lint-hot.json` | 工具 | ② 合并扫描 | — | 合并扫描输出，交 ④ 校验与 ⑤ 打包 |
| `review-results.json` | 审查员 | ③ 判断 | 15 | 功能判定（条件及其位号 `refs`、计算、余量及其推法与公差端、开放项及其单侧定界、失败项）和手填的检查项；绑定功能的检查项不落盘，门禁、报告、打包、对比读取时由功能派生（`results_model.materialize`），审查员的绑定或注记只留 `{id, function_id, aspect}` / `{id, 注记}` 残根 |
| `review-gate.json` | 工具 | ④ 校验 | — | 对账结果、阻断项、待办 |
| `notes.json` | 审查员 | ⑤ 出报告 | — | 报告里的白话说明 |
| `审查报告.md` / `审查报告.html`、`record/` | 工具 | ⑤ 出报告 | — | 交付物：报告与留档 |

### 格式版本怎么升

2026-10-27 定（用户：按照你推荐的三种方式进行修改）：
- **版本号只记结构变化**：字段增删、字段含义拆并、开放项种类增删才升。只是换叫法（词表搬进 catalog、同义改名）不升版，
  在 `scripts/migrate_results.py` 加一条改名，门禁拒收旧词并点名这个脚本。改名按旧词本身识别，任何版本的文件都能跑，跑两次不再变。
- **一批改动最多升一次**：一张改单（一条台账条目）里涉及格式的改动合成一版，不逐项升。
- **结构变化写进迁移脚本的步骤表**：`STEPS` 记每一版改了什么；需要审查员重做的步骤脚本不迁移，只说明哪一步、要重做什么。

## 二、每个脚本属于哪一步

“入口”是执行流程里直接调用的命令，只有入口写进 SKILL.md 的执行流程；“工具”是特定情形手动调用的命令；
“库”只被导入。新脚本先在这里归到一步并分类，再写代码。

| 步骤 | 入口 | 工具 | 库 |
|---|---|---|---|
| ① 读入 | `parse_netlist.py`、`parse_kicad.py`、`read_bom.py`、`requirements_extract.py`、`audit_datasheets.py` | `install_kicad_cli.py` | `page_inventory.py`、`ordering_status.py`（订货表状态线索、库内候选筛选；不作电气判定）、`datasheet_kinds.py`、`electrical_contract.py`、`skill_identity.py`、`guideline_criteria.py`（本地发布包的词表与设计准则读取、校验、选用和覆盖）、`device_kinds.py`（器件类别登记表）、`part_words.py`（器件身份、PCB 铜与有出处的精确型号脚方向）、`solve_dividers.py`（电阻值解析）、`requirement_clarifications.py`（需求澄清：问题、答复、定下的需求） |
| ② 出计划 | `lint.py`、`circuit_candidates.py`、`circuit_decisions.py`、`gap_inventory.py` | `decoupling.py`、`i2c_topology.py`、`reviewed_declarations.py` | `plan_review.py`、`catalog.py`、`check_key.py`、`plan_circuits.py`、`protective_clamps.py`（防护钳位的共用判定）、`latch_criteria.py`（外部锁存判据：状态脚驱动的锁存树逐动作代入）、`guideline_scans.py`（把能由网表、BOM 字段和入表数据判定的设计准则做成冷扫描候选）、`plan_system.py`、`plan_board.py`、`interfaces.py`、`row_owner.py`、`board_intent.py`（原生事实不变，给 NetGraph 附完整有出处脚表的缺名解析与冲突）、`board_scans.py`、`requirement_parameters.py`、`requirement_bindings.py`、`rule_gaps.py`、`independence.py`、`derating.py`（降额等级与应力余量核对）、`stress_check.py`（共用应力核对：降额限值、应力判法、挑规则）（共用设计准则库：校验、选用、覆盖；与 ASG 同字节）、`checkers/` |
| ③ 判断 | `derive_rows.py` | `calc.py`、`simulate_rc.py`、`audit_parameter_claims.py` | `function_reading.py`、`circuit_bounds.py`、`model_bounds.py`、`bound_formulas.py`、`boost_switch_loss.py`、`flyback_stop.py`、`fault_energy.py`、`zener_fault.py`、`bom_constraints.py`、`design_preflight.py`、`units.py` |
| ④ 校验 | `validate_review.py` | `migrate_results.py` | `results_model.py`、`review_functions.py`、`review_quality.py`、`review_stage_scope.py`、`review_summary.py`、`review_workflow.py`、`task_scope.py`、`validate_remediation.py`、`review_engine.py` |
| ⑤ 出报告 | `render_report.py`、`pack_review.py` | — | `report_html.py` |
| 复审 | `diff_netlists.py` | — | `revision_impact.py` |
| 维护 SR | `catalog.py --write-doc` | `compare_reviews.py`、`check_ledger.py`、`render_commodity_floors.py` | — |

`catalog.py` 是规则的唯一登记处，既被出计划导入，维护时也用它重写规则总表。
`independence.py` 在出计划时拒收引用设计方文档的声明，在校验时拒收这样的证据，两步共用。

## 三、历次架构决定

改架构按 SKILL.md“改架构先问人”办理；确认后在这里加一行（日期、一句话决定、台账位置），确认的原话、理由和验收数字只写进台账。2026-11-07 前的决定原文在台账末尾“架构决定原文”一节。

| 日期 | 决定 | 台账位置 |
|---|---|---|
| 2026-11-07 | 删除待核清单 `design_checklist.py`；ASG→SR 交接只留 SR 实际读取的角色；审查要点改名要点1–7；应力超幅在风险清单单列；本表压成一句话 | 台账 2026-11-07“ASG/SR/规范源矛盾清理”条目 |
| 2026-11-06 | M4：计划格式 7→8，`guidelines` 记录共用层版本、`shared_sha256`、`fingerprint_format` | 台账“架构决定原文”第 1 行 |
| 2026-11-06 | M3：共用设计准则来自硬件设计规范发布包 | 台账“架构决定原文”第 2 行 |
| 2026-11-06 | M1：共用源收回硬件设计规范，使用确定性发布包安装到选定技能 worktree | 台账“架构决定原文”第 3 行 |
| 2026-11-03 | 合并步 7：词表加 `HOLD_UP`（掉电保持）与 `SIGNAL_PROTECTION`（信号端口保护），准则库 1.7.2 | 台账“架构决定原文”第 4 行 |
| 2026-11-03 | 准则库 1.7.3：G03-023、G05-090 的适用类型加 `HOLD_UP`（条目 1.0→1.1），条款文字不变 | 台账“架构决定原文”第 5 行 |
| 2026-11-04 | 准则库 1.7.4：G03-025 的适用类型加 `STARTUP`（条目 1.0→1.1），条款文字不变 | 台账“架构决定原文”第 6 行 |
| 2026-11-04 | 准则库 1.8.0：新增 G05-098 外部锁存判据在正常动作与允许负载下不成立 | 台账“架构决定原文”第 7 行 |
| 2026-11-04 | intent 加可选字段 `interfaces`（连接器位号 → `{exposure: in_box / via_box_connector / exposed, citation}`），按 `derating`… | 台账“架构决定原文”第 8 行 |
| 2026-11-02 | 合并步 6，候选生成：输入保护候选只留连接器带电脚的分支 | 台账“架构决定原文”第 9 行 |
| 2026-11-02 | 合并步 5：`validate_review` 要求只挂文档/订货一致性规则（DEV-D01/D02/D04、DOC-*）的缺陷写明有无电气后果，无电气后果的只能 P3 | 台账“架构决定原文”第 10 行 |
| 2026-11-02 | 合并步 4：读入层料号 NC 订货后缀不当 DNP | 台账“架构决定原文”第 11 行 |
| 2026-11-02 | 合并步 3：读入层只解明确单位和欧式小数，同板 R330 歧义保留原值与两种候选 | 台账“架构决定原文”第 12 行 |
| 2026-11-02 | 已核完整物理脚表贯通 NetGraph：原生有名优先、缺名补义、冲突显式记录 | 台账“架构决定原文”第 13 行 |
| 2026-11-02 | 按用户合并步 2A 授权，候选以磁性储能/控制或线性调整拓扑定分立变换级 | 台账“架构决定原文”第 14 行 |
| 2026-11-02 | 按用户合并步 1 授权，读入层保留 KiCad fields/原始 Value，以 Val 优先解电气值并记字段与方法，未知保留 unknown | 台账“架构决定原文”第 15 行 |
| 2026-10-20 | 判断的单位是功能，不是检查项 | 台账“架构决定原文”第 16 行 |
| 2026-10-21 | 计划按功能树组织，每个检查项恰有一个所属 | 台账“架构决定原文”第 17 行 |
| 2026-10-22 | 只认四类输入，设计方文档不进 | 台账“架构决定原文”第 18 行 |
| 2026-10-23 | 退役工具自动算保证值结论（evidence.json） | 台账“架构决定原文”第 19 行 |
| 2026-10-23 | 框架检查项只能委托给另一个计划框架（8a），跨电路的缺口写在拥有缺失量的框架里、其他框架的检查项用 open_ref 指向它（8b），审查员自建的功能只取没有电路框架完整包含的对象（8c） | 台账“架构决定原文”第 20 行 |
| 2026-10-23 | 结果格式 5：决定结论的余量写推界方式（`basis.derivation`，测试点外推须写 `monotonic`，温度系数须写 `tempco`，典型曲线只能是 ESTIMATE）和每个带公差输入取的哪一端（`b… | 台账“架构决定原文”第 21 行 |
| 2026-10-23 | 计划格式 7：电路检查项按“类型 × 规则”的网表前提（`catalog.SUBJECT_REQUIRES`）派检查项，前提不成立不派、功能框架记 `not_asked`、报告列“未问”，检查项对象取前提找到的器件（… | 台账“架构决定原文”第 22 行 |
| 2026-10-23 | intent 格式 4：可编程器件逐配置组核配置值（新规则“配置值满足要求”，新内容域 CFG | 台账“架构决定原文”第 23 行 |
| 2026-10-23 | intent 格式 4 加任务剖面 `mission_profile`：各时段时长占比、负载、环境温度和设计寿命内的次数，各引需求原文，所有寿命检查项按这一份剖面算（6d） | 台账“架构决定原文”第 24 行 |
| 2026-10-23 | 结果格式 6：判“定不出界”的缺厂家数据用数写定界尝试（`monotonic_tried{side: UPPER 或 LOWER, quantity, operating_point{min, max, unit},… | 台账“架构决定原文”第 25 行 |
| 2026-10-23 | 结果格式 6 加两处（定界一致性方案第 2、3 条）：缺厂家数据的 `specified_by` 不得是没覆盖工作点的测试点，引典型曲线时写 `typical_estimate`，估算已经不够记失败项、失败项余量可按… | 台账“架构决定原文”第 26 行 |
| 2026-10-23 | 工作点定界表：器件参数能不能定界、按什么推法和公式、推不出记哪一档，登记在 `catalog.BOUNDS`（每格：器件类别、参数、开着的一侧、随什么变和方向、按顺序的推法 G1–G10/SOA/强制 β 及其公式、… | 台账“架构决定原文”第 27 行 |
| 2026-10-24 | 8b 的做法定下来：跨电路的缺口只写在一个功能的开放项上，开放项的 `decides` 用 `check_ids` 点名另一电路受它挡住的检查项，`derive_rows.py` 让那些检查项的 `open_ref`… | 台账“架构决定原文”第 28 行 |
| 2026-10-24 | 删 `run_regression.py`（连同 `tests/regression/`） | 台账“架构决定原文”第 29 行 |
| 2026-10-24 | 出计划只有 `lint.py` 一个入口：`plan_review.py` 删去 `main`，归为库（SR 自查 2.9，用户选：“删 plan_review.main”：只留 lint.py，plan_revie… | 台账“架构决定原文”第 30 行 |
| 2026-10-24 | 打包强制“报告只从台账生成”：`pack_review.py` 用打包的计划、结果、门禁和 `notes.json`（按渲染时的 `--title`、`--detail`）重新渲染报告，与交付的不同就拒绝 | 台账“架构决定原文”第 31 行 |
| 2026-10-24 | 估算可以判通过：`ESTIMATE` 余量写 `consequence_class`（只能是 REQUIRED_FUNCTION 或 PERFORMANCE_OR_LIFE）和 `handoff`（本功能 `hand… | 台账“架构决定原文”第 32 行 |
| 2026-10-24 | intent 与计划、结果一样严：`schema_version` 必写，顶层只认 `INTENT_FIELDS` 与各检查器的段 | 台账“架构决定原文”第 33 行 |
| 2026-10-24 | 脚本的导入方向与步骤归属一致：共用的格式约定（`PHASES`、`text`、“能定位”的正则、后果分类表、`engine_identity`）并进 `electrical_contract.py` | 台账“架构决定原文”第 34 行 |
| 2026-10-24 | 执行只留一条线：审查员沿计划的功能树走，判断逻辑写成一条链（对象 → 问题 → 条件与余量 → 检查项 → 对账 → 报告），每层只在一处定义 | 台账“架构决定原文”第 35 行 |
| 2026-10-25 | 电路**拥有**的器件检查项（owner 为该电路、不是 NOT_APPLICABLE 的检查项）在出计划时就预绑到该电路的功能框架（`plan_review.bind_owned_rows`），`aspect` 取… | 台账“架构决定原文”第 36 行 |
| 2026-10-25 | 决定给电路加工作态（`states_add`）必须在 `state_requirements` 里逐态点名一条原文说到该态的需求 | 台账“架构决定原文”第 37 行 |
| 2026-10-25 | ④ 第一项（对账前的功能复核）拿到机器信号和门禁：决定性余量（GUARANTEED_BOUND、REACHABLE_CASE、EXACT_ENVELOPE）必写 `basis.cell`（定界表的格或 NONE），格… | 台账“架构决定原文”第 38 行 |
| 2026-10-26 | 审查者阅读路径按读者分层：每份参考文件第三行写读者（审查员 / SR 维护者 / 审查员与 SR 维护者），SKILL.md 的参考文件表加读者列并列全 20 份，执行流程 ①–⑤ 只引审查员读的文件，SKILL.m… | 台账“架构决定原文”第 39 行 |
| 2026-10-26 | 器件类别只登记一次：`device_kinds.KINDS`（名称、位号前缀、词、手册线索、两端件、链路件、保护件、由类别单独决定的磨损类、可否声明），`part_words` 的前缀表与关键词表、`board_in… | 台账“架构决定原文”第 40 行 |
| 2026-10-26 | 结构化字段是主路径：单位表 `scripts/units.py`（SI 前缀 × 电学基本单位，µ/u、Ω/ohm、²/2 同义，Vac/Arms/°C/%/ratio/A²s/mV/K 等专名，每个量纲的板级合理范… | 台账“架构决定原文”第 41 行 |
| 2026-10-26 | 派生检查项不落盘：台账只装功能判定和手填检查项，门禁、报告、打包、对比读取时由计划和功能派生（`results_model.materialize` = derive + expand），`derive_rows.p… | 台账“架构决定原文”第 42 行 |
| 2026-10-26 | 等交付物与审查发现分开：DELIVERABLE_PENDING 开放项挡住的 INSUFFICIENT 不是阻断项（`validate_review` 列进 `pending_deliverables`，`relea… | 台账“架构决定原文”第 43 行 |
| 2026-10-26 | ④ 疑点分层：派生检查项（`derived`，`open_ref`）的文字是 `expand` 按开放项写的，筛查对它们读开放项一次——定级整批同级按缺口数（开放项和它的检查项算一个）、时序窗口看开放项的 `scen… | 台账“架构决定原文”第 44 行 |
| 2026-10-26 | 5.2 打包与交付的严格审核：`pack_review` 把台账名的引用解析到 `record/`（不复制，`ledger_name`），SR 技能目录内的引用按 `skill_version` 解析并自动记 `sk… | 台账“架构决定原文”第 45 行 |
| 2026-10-26 | 5.1 渲染报告的严格审核：功能表每方面只写决定性余量、同一比较只写一次、`result` 超 300 字取第一句、问题里 >8 位号写个数（`decisive_margins` / `short_question`） | 台账“架构决定原文”第 46 行 |
| 2026-10-26 | 第一次扩表：词表加 `ntc`、`varistor` 两个器件类别（`part_words.NTC` / `VARISTOR`，按共用词和 Thermistor 符号，TH/RT/NTC 前缀最弱，RV 前缀不作依据… | 台账“架构决定原文”第 47 行 |
| 2026-10-26 | 判决边界按器件类型：定界表每格加可得性、允许的估算与倍数（按后果类）、失效后果、样机能否验、边界五列（`catalog.Bound`，`estimate_rule(cell, class)`），新增 CAP-SURG… | 台账“架构决定原文”第 48 行 |
| 2026-10-26 | 结果格式 7：条款加 `refs`——这条条款说的是板上哪几只器件 | 台账“架构决定原文”第 49 行 |
| 2026-10-26 | 参考文件按步骤拆分：`plan-and-results.md`（117 KB，①–④ 共用）拆成 `intent-format.md`（①）、`plan-format.md`（②）、`results-format.m… | 台账“架构决定原文”第 50 行 |
| 2026-10-26 | 检查器的共用约定（引脚名写法、电源轨身份、识别依据三级、器件类型核验、参考地分区、电路候选、装配状态、器件脚表、指纹绑定、清单与计划、缺口与结论）从 `automation.md` 分出成 `checker-conv… | 台账“架构决定原文”第 51 行 |
| 2026-10-26 | 接口网络带 `power_node`（电源轨、开关节点、变压器绕组、整流桥上的网络） | 台账“架构决定原文”第 52 行 |
| 2026-10-26 | 不审配置表：手册声明的能力判为功能可达，取消配置值检查规则、CFG 内容域、DELIVERABLE_PENDING / CONFIGURATION_TABLE 与 `intent.devices.<位号>.confi… | 台账“架构决定原文”第 53 行 |
| 2026-10-26 | 三条过严规则（用户逐项判定）：齐纳管 VZ 下界一格兜底改为超出规定区，最低测试电流以下又没有覆盖曲线时记失败项，不开缺厂家资料 | 台账“架构决定原文”第 54 行 |
| 2026-10-26 | 设计风险不记缺厂家资料：DIODE-SURGE、IC-IO-CURRENT、CAP-SURGE-V、MOS-DISCHARGE-I2T 四格兜底改为超出规定区，新增 IC-PIN-ABSMAX（脚上瞬态电压/注入电流… | 台账“架构决定原文”第 55 行 |
| 2026-10-26 | 钳位电压对被保护脚只问一次：钳位扫描改为窗口类 PRO-E02（逐器件，可写余量、定界格与开放项，含对外连接器信号线上的 ESD 钳位） | 台账“架构决定原文”第 56 行 |
| 2026-10-26 | 一只钳位件只由一条规则判：跨网与地、另一端不是开关节点（SW 类脚或非电源轨上的变压器绕组）且不是内部节点上基准/电平齐纳的防护钳位，只出 PRO-E02，判据按需求的浪涌或 ESD 波形取钳位电流、钳位电压对同网每… | 台账“架构决定原文”第 57 行 |
| 2026-10-26 | 防护钳位（`protective_clamps.protected_net` 认出的）不出 DEV-C05 工况行，只留身份与引脚行 | 台账“架构决定原文”第 58 行 |
| 2026-10-26 | 需求没定当场问用户：问题和答复写 `intent.clarifications`（intent 格式 5），答复只有用户给定、采纳 SR 建议、明确暂缓三种，定下的需求以澄清编号进需求清单 | 台账“架构决定原文”第 59 行 |
| 2026-10-26 | 结论三档加四类风险标签：只靠估算过关的角点判“合格，但有风险”，余量写 `basis.risk{types, corner, improvement}`（结果格式 9），类型取定界表那一格新加的“估算对应的风险”列（… | 台账“架构决定原文”第 60 行 |
| 2026-10-26 | 设计没定不再是“证据不足”：先反推这个值要满足的界，原理图或 BOM 本该写明的（器件值、额定、耐压、料号）记失败项，发现项的改法写反推出的值（甲） | 台账“架构决定原文”第 61 行 |
| 2026-10-26 | 等交付物并入乙：另一环节欠的交付物（定制件图纸、固件/OTP 能力）不再是开放项，要满足的条件写成 DESIGN_CONSTRAINT 交给负责方，没有单一数值的写成条款（不写 `limit`，由 `judgemen… | 台账“架构决定原文”第 62 行 |
| 2026-10-27 | 审查没做完只留在内部：REVIEW_INCOMPLETE 仍是审查过程中的开放项，门禁照常列为阻断，但 `render_report.py` 遇到它不出报告（`results_model.unfinished_che… | 台账“架构决定原文”第 63 行 |
| 2026-10-27 | 用户暂缓是审查范围的说明，不是结论：暂缓的需求不生成检查项（计划 `deferred_requirements`），用户说这轮不审的检查项写 NA + `na_reason: USER_DEFERRED` + `in… | 台账“架构决定原文”第 64 行 |
| 2026-10-27 | 一次只取一个瞬态或故障事件，叠在持续最坏工况上，两个独立的稀有事件不同时取，物理上同时发生的照叠 | 台账“架构决定原文”第 65 行 |
| 2026-10-27 | 器件类型的依据（A–C 逐项确认）：须有核验手册声明的器件按分类器读出的最终类型取，不再按 Q/… | 台账“架构决定原文”第 66 行 |
| 2026-10-27 | 器件自身发热的三格放开损坏类估算：DIODE-IR-HOT（×2，结温余量 ≥ 20 °C）、MOS-VGS-ON 功率开关（×2，结温余量 ≥ 20 °C）、ECAP-ESR-RIPPLE（×1.3，芯温余量 ≥ … | 台账“架构决定原文”第 67 行 |
| 2026-10-27 | 门禁合成一条 `pytest`（已含规则合同、KiCad 回放、典型电路），台账 Gates 只写测试条数与 `--changed` 结果 | 台账“架构决定原文”第 68 行 |
| 2026-10-27 | 门禁写入所读文件的指纹 `validated_files`（计划、结果按打包形态剥掉派生检查项、db、lint，规范化 JSON 的 SHA-256），`pack_review.py` 用将要打包的文件逐个核对，不符… | 台账“架构决定原文”第 69 行 |
| 2026-10-27 | 结果格式 13：余量为 0、应力只来自交出去的 DESIGN_CONSTRAINT 的被拒，这种“约束等于额定”的通过写成 `judgements` 引约束与额定 | 台账“架构决定原文”第 70 行 |
| 2026-10-27 | 降额接进审查，判法单列器件应力规范（与 ASG 共用，取代降额规范 R6）：等级写 `intent.derating{level, source: req:/clarification:}`，计划带 `derating` | 台账“架构决定原文”第 71 行 |
| 2026-10-27 | 报告分三层、结果格式 14：结论只列“必须改”和“要补的资料”各一行与一行关键数字 | 台账“架构决定原文”第 72 行 |
| 2026-10-27 | 规则按六个问题分阶段重理，第一阶段“余量怎么判”单列余量判定规则（SR 专用 | 台账“架构决定原文”第 73 行 |
| 2026-10-27 | 结果格式 15，第二阶段“限值从哪来”：界怎么得来只用定界表的推法一种叫法——决定性余量 `basis.method`（`cell: NONE` 也写，按定界表给的先后取，SOA、FORCED_BETA 只随格）、开… | 台账“架构决定原文”第 74 行 |
| 2026-10-27 | 第三阶段“怎么算”：计算口径都在 WCA——保护动作窗口与故障时间轴、器件参数定界口径（齐纳低电流、MOS 实际 VGS、单调外推、只有典型值、脉冲、检流、物理上限等）、功率开关栅压/损耗/SOA、假设与上界的证据门… | 台账“架构决定原文”第 75 行 |
| 2026-10-27 | 第四阶段“适不适用”：evidence-proportionality 只留适用性与最小充分证据（三个问题、受控范围、按用途选模型、本体与系统、转接板、证据够用、定界五步、身份分支、E 的例外、证据不足的写法与改图消缺） | 台账“架构决定原文”第 76 行 |
| 2026-10-27 | 第五阶段“定几级、能不能放行”：BOM 约束怎么定级从 commodity-floors 移进结论与准出，与后果类别、P0–P3 同处 | 台账“架构决定原文”第 77 行 |
| 2026-10-27 | 第六阶段“覆盖与改版”：inputs-and-coverage 只留输入基线、覆盖线、状态组合、阅读与结束条件、留档 | 台账“架构决定原文”第 78 行 |
| 2026-10-31 | 接入共用设计准则库（G01–G09）：设计准则库与脚本 `guideline_criteria.py` 与 ASG 同字节 | 台账“架构决定原文”第 79 行 |
| 2026-11-01 | 设计准则库 1.0.0（G01–G03，143 条）装入：新增 6 个对外接口电路类型 `DC_48V`、`AC_MAINS`、`INDUSTRIAL_DI`、`POE_PD`、`VEHICLE_28V`、`SHIP… | 台账“架构决定原文”第 80 行 |
| 2026-11-01 | 设计准则库 1.2.0（G01–G05，340 条，336 条 active）装入：G04、G05 转 active，G04-003、011、079 和 G05-026 待定项未定仍为 draft | 台账“架构决定原文”第 81 行 |
| 2026-11-02 | 设计准则库 1.3.0：G04-003、G04-011、G04-079、G05-026 转 active，340 条全部 active | 台账“架构决定原文”第 82 行 |
| 2026-11-02 | 共用层目录制：`guideline-criteria.json/.md`、`derating-rules.json/.md`、`stress-spec.md` 搬进 `references/shared/`，新增 `… | 台账“架构决定原文”第 83 行 |
| 2026-11-02 | 共用层第二轮：词表进共用层 `references/shared/vocabulary.json`（基线、电路类型、器件类别的名字与标题，设计准则库汇编从它取词表，`catalog.CIRCUIT_TYPES`、`d… | 台账“架构决定原文”第 84 行 |
| 2026-11-02 | 共用应力核对进共用层：`scripts/stress_check.py` 一份算降额限值、判一条应力（超额定 / 应力风险 / 合格）、按器件类别与量纲挑规则，两技能同字节并进共用层指纹 | 台账“架构决定原文”第 85 行 |
| 2026-11-02 | 正式电路用语：共用规范的单条要求改称“设计准则”、汇编改称“设计准则库”（文件 `guideline-criteria.json/.md`、模块 `guideline_criteria.py`、键 `criteria… | 台账“架构决定原文”第 86 行 |
| 2026-11-02 | 设计准则库 1.5.0（条数不变）：新增第 7 个对外接口电路类型 `DC_24V`（检查项 `PWR-C18`、`PWR-C13`、`PRO-C01`、`PWR-T05`，不含 −48 V 专用的 `PWR-C17`） | 台账“架构决定原文”第 87 行 |
| 2026-11-02 | 设计准则库 1.6.0（344 条）：新增 G01-051～054，由 `DC_24V` 触发 | 台账“架构决定原文”第 88 行 |
| 2026-11-02 | 设计准则库 1.6.1（344 条）：G01-053 按 GB/T 17626.29-2006 修订，要求项目写明选定的暂降与中断组合，中断分高阻抗和低阻抗，仍不设默认等级 | 台账“架构决定原文”第 89 行 |
| 2026-11-02 | 设计准则库 1.7.0（353 条）：86 块开源板归因后新增 G02-036～039（器件身份、文档一致、占位值、推荐工作条件）、G03-059（前馈电容窗）、G04-101～104（官方脚表、未用脚处置、USB … | 台账“架构决定原文”第 90 行 |

## 四、规则维护

（2026-10-26 从 SKILL.md 移来：这些是维护者的步骤，审查员的流程不读它们。）

- 加字段、加质量筛查或加结论词之前，先查现有字段、规则或筛查能否表达；能表达就复用，新增时写明现有哪一项覆盖不了。
- 同一块板由两名审查员（或两次运行）各出一份记录时，用 `python3 scripts/compare_reviews.py <记录A> <记录B> --md compare.md` 对比：
  精确配对只按检查项标识（`check_key`：规则、规则版本、去掉电路名的对象、判据）配对，报配对率、已答比例和一致率，列出通过对失败和 P0/P1 分歧；
  按电路对齐的结果只作建议配对，确认后用 `--alias` 带位置引用加入精确配对；"电路决定与成员差"一节逐候选列两边的决定（accept / merge / split / reject 及去向）、
  对齐电路里只在一边的位号、未归属器件两边的处置（add 进电路还是留给 REQ-Q08），电路划分的差异在这里数，不混进配对率；
  “逐器件参数引用”一节按位号、参数词、单位对齐两边带 `refs` 的数值限值条款，列出限值不同的和只有一边读了的。
  差异里反复出现的写法先找现有校验为什么放过，再加机器能数的护栏，不加措辞要求。
- 新脚本先在 [架构说明](#二每个脚本属于哪一步) 归到一步并分类：入口（执行流程里直接调用）、工具（特定情形手动调用）、库（只被导入）。只有入口写进执行流程；新增入口属于架构调整。
- 工程规则身份由 `scripts/electrical_contract.py`（`engine_identity`）与 `scripts/skill_identity.py` 计算：算法、常量、受控正文和规范判据变化要求按当前规则重新验证；说明/接口页、入口元数据、测试及 Python 注释变化只做兼容检查。未知规范文件仍按规则处理，不能自行把判据降为说明。
- 规则编号、判据、审查要点归属和功能电路只在 `scripts/catalog.py` 登记，改后运行
  `python3 scripts/catalog.py --write-doc references/check-catalog.md` 和 `--write-doc references/review-vocabulary.md`（审查员的三张名称表）。来源为“全板通用”“电路检查项”的新规则
  登记后即自动展开；来源为“计划逐对象生成”“Lint 内置”或检查器的规则，还要在计划生成的对应层（电路与器件 `plan_circuits.py`、接口 `interfaces.py`、
  系统功能 `plan_system.py`、全板与覆盖 `plan_board.py`；`plan_review.py` 只做汇总）、`lint.py` 或对应检查器里实现展开/扫描。新增或调整规则先回答 [审查要点中的三个问题](review-charter.md#用审查要点指导进化)。
- 共用层（`references/shared/` 全部文件与 `scripts/guideline_criteria.py`、`scripts/stress_check.py`）由硬件设计规范的 `工具/guideline_criteria.py` 统一发布，选定的 ASG/SR worktree 从同一正式包核清单后安装，技能内不得编辑或互相复制；`python3 scripts/guideline_criteria.py shared` 核各自已装指纹；哪些文件、各管什么、谁读、哪条测试守见[共用层](shared/shared-layer.md)，设计准则库的更新步骤见[共用设计准则库](shared/guideline-criteria.md#六更新设计准则库)。新增或调整 SR 规则时，若它核对某条设计准则，在 `catalog.BASIS` 登记映射；报告里“适用但还没有检查的共用设计准则”就是这里的待办。`test_guideline_criteria.py` 核对设计准则库词表与 `CIRCUIT_TYPES`、`device_kinds.KINDS` 一致，名字与标题由本地词表读取，分类线索及检查器归属在 SR 维护；本地安装包完整性由 test_installed_release.py 核对，配对字节验收由规范显式发布检查承担。
- 知识包（`references/knowledge/`，清单 `knowledge-release.json`）由硬件设计知识框架发布后整包安装，技能内不改、运行时不读框架目录；`test_knowledge_package.py` 核包与清单一致，计划 `guidelines` 段记它的版本与指纹（2026-11-10）。
- **门禁只有一条**（2026-10-27，用户：门禁合成一条 pytest）：每次改动跑 `python3 -m pytest scripts/tests -q`。它已经包含
  [规则合同](../evals/rule_contracts/README.md)（每条自动规则一块触发板、一块近似板）、[KiCad 原生交付回放](../evals/kicad_replay_bench/README.md)
  和 [典型电路基准](../evals/typical_circuits/README.md)（每条报出都要已归类，新出现的须逐条审读），不再单独跑、不再分行记。
  开发中可先跑几秒的约定层 `-m contract`；措辞层 `-m wording` 是 golden 报告，改报告措辞用 `SR_UPDATE_GOLDEN=1` 重写快照并审读 diff。
  新增 A/E/T/V/H 规则须同时加触发板与近似板；规则改变回放的冻结答案时另存一版约定（见回放 README）。
- **变异检查按需**（同日，用户：变异检查不再每次必加，提交前跑 --changed，定期全量跑并清理失效的）：提交前跑
  `python3 evals/mutation/run.py --changed`，确认改动文件上的现有变异仍被杀死、锚点仍命中；锚点因本次改动失效的就地重锚或删去。
  只有新加的判断逻辑没有直接测试守着时才补变异，不再每次必加。一批改动后或每周跑一次全量 `python3 evals/mutation/run.py`，
  把存活的补测试、失效的重锚或删去，记一条台账。
- **电路评测集**（2026-11-05，用户：把这些电路做成给 SR 和 ASG 评测和改进的专门评测集，放在电路设计规范里）：电路案例（按典型电路分类）、整板与公开板原件、已知缺陷在 `原理图设计规范/评测集/`（`evals/eval_set.py` 定位，`CIRCUIT_EVAL_SET` 可改）；运行结果与公开板审查记录在同级 `评测记录/`（2026-11-06 起，`CIRCUIT_EVAL_RECORDS` 可改），说明见它的 README。本仓库只留运行器和代码门禁固件（规则合同、回放、典型电路、种子基准、变异），评测集不在时门禁里读它的测试跳过。`python3 evals/circuit_cases/run.py auto --out <新目录> --guideline-release <选定发布包>` 跑自动层；现行说明在评测集 `发布绑定.md`。ID/状态来自显式包，包须与本技能安装件一致；子进程不用测试替代输入，实际计划身份另核。原始 run、成绩与汇总均记发布版/指纹/格式、E 提交及实际工作区身份、案例与原件哈希、技能提交及字节。缺 E 独立打印外部评测 skip，不当代码门或案例通过；历史无身份结果不自动补贴新版。
  2026-11-09 起原评测集停用（评测体系重建中），评测集与评测记录已于 2026-11-11 删除；`evals/eval_set.py` 的默认路径不再存在，`evals/circuit_cases`、`evals/detection` 读已知缺陷的部分和 `evals/boards_tools` 现在没有数据可跑，门禁里读它的测试照旧跳过。新评测体系定下后改这一条。
- 按需另跑：改导入器时跑 [真实来源导入回归](../evals/input_bench/README.md)；看自动层检出率跑 [种子基准](../evals/seeded_bench/README.md)；
  `python3 evals/bench_coverage.py --seeded <注入基准 results.json>` 列出每条 A 规则在哪个基准有真实板正例。评测通过不等于任何真实电路审查通过。

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
| `db.json` | 工具 | ① 读入 | — | 网表、BOM 列、页、符号脚：图上实际是什么 |
| `requirement_source`（需求原文抄录） | 工具 | ① 读入 | 1 | 需求文档逐字抄录与 sha256 |
| `datasheet-audit.json` | 工具 | ① 读入 | — | 每颗物料的资料是否找到、是否核实 |
| `intent.json` | 审查员 | ①② 的输入 | 4 | 需求理解、任务剖面、电源轨、器件类别与配置组、电路取舍、装配状态、规则缺口 |
| `record/circuit-candidates.json` | 工具 | ② 出计划 | 2 | 候选电路及成员 |
| `review-plan.json` | 工具 | ② 出计划 | 7 | 功能树、每个检查项检查、功能框架、各检查器清单、接口 |
| `review-results.json` | 审查员 | ③ 判断 | 7 | 功能判定（条件及其位号 `refs`、计算、余量及其推界方式与公差端、开放项及其单侧定界、失败项）和手填的检查项；绑定功能的检查项不落盘，门禁、报告、打包、对比读取时由功能派生（`results_model.materialize`），审查员的绑定或注记只留 `{id, function_id, aspect}` / `{id, 注记}` 残根 |
| `review-gate.json` | 工具 | ④ 校验 | — | 对账结果、阻断项、待办 |
| `审查报告.md` / `审查报告.html`、`record/` | 工具 | ⑤ 出报告 | — | 交付物：报告与留档 |

## 二、每个脚本属于哪一步

“入口”是执行流程里直接调用的命令，只有入口写进 SKILL.md 的执行流程；“工具”是特定情形手动调用的命令；
“库”只被导入。新脚本先在这里归到一步并分类，再写代码。

| 步骤 | 入口 | 工具 | 库 |
|---|---|---|---|
| ① 读入 | `parse_netlist.py`、`parse_kicad.py`、`read_bom.py`、`requirements_extract.py`、`audit_datasheets.py` | `install_kicad_cli.py` | `page_inventory.py`、`datasheet_kinds.py`、`electrical_contract.py`、`skill_identity.py`、`device_kinds.py`（器件类别登记表）、`part_words.py`、`solve_dividers.py`（电阻值解析） |
| ② 出计划 | `lint.py`、`circuit_candidates.py`、`circuit_decisions.py`、`gap_inventory.py` | `decoupling.py`、`i2c_topology.py`、`reviewed_declarations.py` | `plan_review.py`、`catalog.py`、`check_key.py`、`plan_circuits.py`、`plan_system.py`、`plan_board.py`、`interfaces.py`、`row_owner.py`、`board_intent.py`、`board_scans.py`、`requirement_parameters.py`、`requirement_bindings.py`、`rule_gaps.py`、`independence.py`、`checkers/` |
| ③ 判断 | `derive_rows.py` | `calc.py`、`simulate_rc.py`、`audit_parameter_claims.py` | `function_reading.py`、`circuit_bounds.py`、`model_bounds.py`、`bound_formulas.py`、`boost_switch_loss.py`、`flyback_stop.py`、`fault_energy.py`、`zener_fault.py`、`bom_constraints.py`、`design_preflight.py`、`units.py` |
| ④ 校验 | `validate_review.py` | — | `results_model.py`、`review_functions.py`、`review_quality.py`、`review_stage_scope.py`、`review_summary.py`、`review_workflow.py`、`task_scope.py`、`requirement_clarifications.py`、`validate_remediation.py`、`review_engine.py` |
| ⑤ 出报告 | `render_report.py`、`pack_review.py` | — | `report_html.py` |
| 复审 | `diff_netlists.py` | — | `revision_impact.py` |
| 维护 SR | `catalog.py --write-doc` | `compare_reviews.py`、`check_ledger.py` | — |

`catalog.py` 是规则的唯一登记处，既被出计划导入，维护时也用它重写规则总表。
`independence.py` 在出计划时拒收引用设计方文档的声明，在校验时拒收这样的证据，两步共用。

## 三、历次架构决定

改架构按 SKILL.md“改架构先问人”办理；确认后在这里加一行，台账条目写明确认的日期和原话。

| 日期 | 决定 | 为什么 |
|---|---|---|
| 2026-10-20 | 判断的单位是功能，不是检查项；结果格式 4：缺口只写在功能的开放项上一次，检查项由功能派生并用 `open_ref` 指向它 | 逐项判断让同一缺口抄在几十项，结论互相矛盾 |
| 2026-10-21 | 计划按功能树组织，每个检查项恰有一个所属；电路由候选和决定推出，不手画 | 两份记录对不上，配对率只有一半 |
| 2026-10-22 | 只认四类输入，设计方文档不进 | 审查要独立，不能让设计文档设定判据 |
| 2026-10-23 | 退役工具自动算保证值结论（evidence.json）；E 检查项由审查员按规格书判定，公式库留给审查员复算 | 两份 R5 审查都没用到，结论全走功能判定 |
| 2026-10-23 | 框架检查项只能委托给另一个计划框架（8a），跨电路的缺口写在拥有缺失量的框架里、其他框架的检查项用 open_ref 指向它（8b），审查员自建的功能只取没有电路框架完整包含的对象（8c）；只装不属于任何框架的检查项（用户确认：“拒收”；“第 8 条按建议定：8a–8c 都做，跨电路的缺口按 8b 写在拥有缺失量的框架里”） | 一次审查把每个缺口各建一个功能、把电路功能判通过再把检查项挂过去，报告里待办重复成功能，电路结论前后不一 |
| 2026-10-23 | 结果格式 5：决定结论的余量写推界方式（`basis.derivation`，测试点外推须写 `monotonic`，温度系数须写 `tempco`，典型曲线只能是 ESTIMATE）和每个带公差输入取的哪一端（`basis.corners`），判“定不出界”须答 `monotonic_tried`（1a–1c）；经需求文档条款的边只能挡绑定到该需求的检查项，隔离两个方面改为全板方面（1d）；工程计算（C）方面判通过须有证明它的余量，厂家参考电路例外（1e）；格式 4 的记录不读（用户确认：“第 1 条按修正后的建议定：1a–1e 都做，1d 用‘需求条款只能挡绑定该需求的检查项’，格式升到 5。”） | 两份 R5 审查一份 163 条边经需求条款挡检查项、只有 3 条余量，另一份把不利一侧的界标成保证界、按标称值取 NTC；同一电路的结论差在定界口径而不在电路 |
| 2026-10-23 | 计划格式 7：电路检查项按“类型 × 规则”的网表前提（`catalog.SUBJECT_REQUIRES`）派检查项，前提不成立不派、功能框架记 `not_asked`、报告列“未问”，检查项对象取前提找到的器件（2a）；类型对电路问到不到一半时计划提示换类型（2b）；只说不适用、不引网表事实的通过被拒（2c）；前提成立仍记 NA 的须引网表事实（2d）；格式 6 的计划不读（用户确认：“第 2 条按建议定：2a–2d 都做，计划格式升到 7。”） | 两份 R5 审查 42 项一边 NA 一边通过：计划对每块电路派该类型的全部规则，没有这个机制时写法各异 |
| 2026-10-23 | intent 格式 4：可编程器件逐配置组核配置值（新规则“配置值满足要求”，新内容域 CFG；2026-10-26 取消，见下），已知角色用 SR 固定的配置组（pd_controller 七组），没有固定组的可编程角色要求声明，组写在 `intent.devices.<位号>.configurable`（3a、3b）；硬件按手册允许的配置范围判，只在某个设置下成立的条件标 `setting{ref, group, value}` 并写进配置检查项（3c）；配置表缺口只挡 配置值检查 项和需求检查项（3d）；配置表统一记 DELIVERABLE_PENDING / CONFIGURATION_TABLE，工厂选项归 DEV-D01（3e）；只有样机能给的结论记阶段 NA 并移交（3f）；写了输出档位的组另问逐档精度（第 7 条第六类）；格式 3 的 intent 不读（用户确认：“第 3 条按建议定：3a–3f 都做，已知角色用 SR 固定的配置组，intent 格式升到 4。”） | 两份 R5 审查一份让一件“配置表未交付”挡 57 项（另一份判通过 28 项），把片内补偿记成设计没定；另一份按默认值判通过、补偿以“靠实测”判通过；交付物类型三种写法 |
| 2026-10-23 | intent 格式 4 加任务剖面 `mission_profile`：各时段时长占比、负载、环境温度和设计寿命内的次数，各引需求原文，所有寿命检查项按这一份剖面算（6d）；电解、固态与超级电容按符号、BOM 料号/规格或铝电容封装识别（6c），耐久按厂家寿命公式或 10 °C 翻倍估算写成 BOM 约束、热点移交热设计、不开 VENDOR_DATUM（6a）；光耦写寿命末所需 CTR 保留比例、不自编衰减系数（6b）；其他耗损件派固定检查项 DEV-C06，次数没给记 NA（6e）；随第 3 条的格式 4 一起，不再升版（用户确认：“我同意”，按“对寿命敏感的器件类型”表定检测范围） | 两份 R5 审查一份按 87600 h 全时、一份按 29200 h 满载算 10 年，一份不接受 10 °C 翻倍开了厂家数据项、另一份写成 BOM 约束，光耦寿命一份开项一份没问 |
| 2026-10-23 | 结果格式 6：判“定不出界”的缺厂家数据用数写定界尝试（`monotonic_tried{side: UPPER 或 LOWER, quantity, operating_point{min, max, unit}, test_points[{condition, at}], why_not, other_side}`）：工作点落在两个测试点之间就按相邻测试点定界，不准开项；只有一部分在测试点之外时只开外面那段（`open_range`），里面那段写余量；每条边写开着的一侧（`side`），另一侧写 DECIDED（有余量）或 NOT_DECISIVE（写理由）；`why_not` 不得照抄 `not_boundable_reason`；格式 5 的记录不读（定界一致性方案第 1 条；用户在逐项选择中对第 1 条选“做”） | R5 验收重审中一份审查的 19 条缺厂家数据，16 条把同一句话写成不利侧并照抄理由当 why_not；其中一处工作电流正好落在两个测试点之间，另一份审查据此定了界 |
| 2026-10-23 | 结果格式 6 加两处（定界一致性方案第 2、3 条）：缺厂家数据的 `specified_by` 不得是没覆盖工作点的测试点，引典型曲线时写 `typical_estimate`，估算已经不够记失败项、失败项余量可按典型曲线记 REACHABLE_CASE（第 2 条，2-A 用户原话“2A，算。”）；设计值写 `undecided[{ref, parameter[, unit]}]`，BOM 行已写的参数不算没定，由另一个开项决定的量写 `depends_on`（只挂一层），它挡的检查项在待办和报告里并到那个开项下（第 3 条；用户在逐项选择中对第 2、3 条选“做”） | 一份审查的 19 条缺厂家数据都拿没覆盖工作点的测试点当“写了这种用法”；反激故障钳位记成设计值，其实由板上保护链决定、另一份审查算出了 P1 |
| 2026-10-23 | 工作点定界表：器件参数能不能定界、按什么推法和公式、推不出记哪一档，登记在 `catalog.BOUNDS`（每格：器件类别、参数、开着的一侧、随什么变和方向、按顺序的推法 G1–G10/SOA/强制 β 及其公式、推不出时 VENDOR_DATUM / OUTSIDE_SPECIFIED / BOUNDED），公式在 `bound_formulas.py`，`references/bounding-table.md` 由表生成；表里有的必须按表（A，用户：“必须按表”），判“定不出界”写格（`monotonic_tried.cell`，表外写 NONE），门禁核对格的一侧、档位和单调方向，余量写 `basis.cell/method/formula` 时门禁重算；MOS 高温 SOA 按持续时间选曲线、按开始壳温降额、恒功率段 100%/热不稳定段 80%，允许壳温和散热要求交热设计与 PCB（B，“B 热不稳定段按修订写法定：按持续时间选曲线、按开始壳温降额、降额后留 80%。”“这里也可以给出散热结构设计上的要求，交给下游的PCB设计”）；检测用 NTC 有表用表、没表按 B 值加公差算保证（C，“有表用表，没表外推算保证”）；BJT 饱和按强制 β、k = 2（D）；浪涌限制 NTC 热态按 0 Ω 定结论（E）；不变的决定第 4 条补一句：定界按表执行、门禁按表重算核对，工具仍不自动出结论（用户在逐项选择中对定界表选“做”） | 同一张手册表，一份审查判“推不出”开项，另一份推出来判通过或失败；定界原则散在四份参考文档和十几条判据里，是文字不是公式，门禁比不了数 |
| 2026-10-24 | 8b 的做法定下来：跨电路的缺口只写在一个功能的开放项上，开放项的 `decides` 用 `check_ids` 点名另一电路受它挡住的检查项，`derive_rows.py` 让那些检查项的 `open_ref` 指向它；没点名的检查项仍只能取本功能的开放项，失败项不跨功能（SR 自查 2.6，用户选：“允许指向别的功能的开项”） | 8b 原先写成“其他框架的检查项用 open_ref 指向它”，校验却要求 open_ref 属于本检查项的功能，照着做被拒收，只能各抄一份缺口 |
| 2026-10-24 | 删 `run_regression.py`（连同 `tests/regression/`）；`solve_dividers.py` 只留电阻值解析，归 ① 读入的库，分压求解器、线性反馈窗口和命令行删去（SR 自查 5.7，用户选：“两个都删”） | 回归脚本对着已读不了的旧记录空转（两块板都 SKIPPED 却报 PASS）；求解器只剩测试在用，分压窗口由审查员按 wca-formulas 算、`calc.py` 复算 |
| 2026-10-24 | 出计划只有 `lint.py` 一个入口：`plan_review.py` 删去 `main`，归为库（SR 自查 2.9，用户选：“删 plan_review.main”：只留 lint.py，plan_review.py 改归为库） | 两个命令都写计划，对 intent 的检查和打印的诊断已经分叉，同一份输入两条路出的计划可能不同 |
| 2026-10-24 | 打包强制“报告只从台账生成”：`pack_review.py` 用打包的计划、结果、门禁和 `notes.json`（按渲染时的 `--title`、`--detail`）重新渲染报告，与交付的不同就拒绝；门禁 `valid` 不为真、结果声明 `review_scope` 不打包；`notes.json` 随台账进 `record/`（SR 自查 2.3，用户选：“重新渲染比对 + 要求 valid”） | 不变的决定第 6 条和文档都写手改报告打包失败、局部热审不打包，打包却只核 HTML 与 Markdown 一致、只记哈希；打包不重跑门禁，门禁结果本身是否最新仍由流程保证 |
| 2026-10-24 | 估算可以判通过：`ESTIMATE` 余量写 `consequence_class`（只能是 REQUIRED_FUNCTION 或 PERFORMANCE_OR_LIFE）和 `handoff`（本功能 `handoffs` 里样机实测那一条的序号），满足时检查项判 PASS，派生检查项带上这条移交；损坏、过热、保护类规则（DEV-C01、DEV-C04、PWR-C03、PWR-C06、PWR-C10、DRV-C01、全部 PRO）不走这条路（SR 自查 2.1，用户选：“估算 + 样机移交可判通过”） | 文档和 DEV-C05、DRV-C02 判据都写“相似器件或典型 ±30% 估算、结论不变就 PASS(B) 并移交样机”，门禁却对 ESTIMATE 什么都不判，照着做被拒收 |
| 2026-10-24 | intent 与计划、结果一样严：`schema_version` 必写，顶层只认 `INTENT_FIELDS` 与各检查器的段；门禁命令行总是要求绑定和计划的依赖记录（去掉 `--require-bindings`），宽松默认只留给直接调用库的测试（SR 自查 2.7、2.8，用户选：“改成必填”“字段白名单 + 版本必填”） | 拼错的顶层字段（`power_rail`）静默放行、全部轨没声明；真实计划都带这些键，缺了反而少查 |
| 2026-10-24 | 脚本的导入方向与步骤归属一致：共用的格式约定（`PHASES`、`text`、“能定位”的正则、后果分类表、`engine_identity`）并进 `electrical_contract.py`；功能判定的读法单列 `function_reading.py`（③ 的库），`review_functions.py` 只留校验；器件用词从 `checkers/netgraph.py` 移到 `part_words.py`（① 的库）；`skill_identity.py` 改记 ① 的库、`check_key.py` 改记 ② 的库；不留旧位置别名；`test_ring_imports.py` 按本表核每个脚本的导入，后环不得被前环导入（SR 自查 5.8，用户选：“做”“并进 contract”“单列新库”“一次改完”；check_key “改记 ② 的库”；engine_identity “并进 contract”） | 表把脚本按环排开，代码却有 8 处前环导入后环（读入取检查器的器件词、计划取校验的规则身份、派生检查项取校验的功能判定读法等），新脚本照表归环会被误导，改 ④ 会波及前面的环 |
| 2026-10-24 | 执行只留一条线：审查员沿计划的功能树走，判断逻辑写成一条链（对象 → 问题 → 条件与余量 → 检查项 → 对账 → 报告），每层只在一处定义；执行流程按步骤重编号为 1.1–1.3、2.1–2.3、3.1–3.3、4、5，图面目检并入 3.3，改版复审不占步骤号；“按 PWR → RST → … 推进”和 check-catalog.md 的“审查流程”表删去，审查要点 G1–G7 从 SKILL.md 目的段撤到 review-charter.md，只作改规则时的坐标（用户：“方案通过，直接按三条改 SKILL.md、check-catalog.md 和 architecture.md，步骤按环重编号。”） | 五套坐标里只有功能树参与出计划、校验和报告，审查要点、内容域、方式字母在代码里只是标签，文档却把同一条流程按三种坐标讲了三遍，环 ① 对应步骤 0、1、3 要来回查表 |
| 2026-10-25 | 电路**拥有**的器件检查项（owner 为该电路、不是 NOT_APPLICABLE 的检查项）在出计划时就预绑到该电路的功能框架（`plan_review.bind_owned_rows`），`aspect` 取规则标题，框架的成员与盲点随之扩大；全板拥有的检查项照旧手填 | R6 同一块板三份记录派生检查项 387 / 287 / 185：哪些器件检查项由功能派生是审查员自己选的，结论来源不同；用户 2026-10-25 "请继续刚才的修改" 定下预绑 |
| 2026-10-25 | 决定给电路加工作态（`states_add`）必须在 `state_requirements` 里逐态点名一条原文说到该态的需求；开放项按种类只能挡 `catalog.OPEN_ITEM_RULES` 给它的检查项（计算/窗口/需求检查项，交付物按其种类另加身份、信号或配置检查项）；PRO-A02 的判据写死为钳位电压对同网 IC 脚绝限比较 | R7 验收：一句泛引文给十块电路各加六个态（+130 项）、同一图纸缺口四份记录挡 62/16/29/14 项、USB ESD 钳位两份 FAIL 一份 PASS；用户 2026-10-25 "B 组 4 项都按 a 执行" |
| 2026-10-25 | ④ 第一项（对账前的功能复核）拿到机器信号和门禁：决定性余量（GUARANTEED_BOUND、REACHABLE_CASE、EXACT_ENVELOPE）必写 `basis.cell`（定界表的格或 NONE），格的推法带公式时门禁复算；`basis.conditions` 里 min≠max 的条款都要有角点，`no_corners_reason` 不再放行；筛查新增 `UNIT_GLYPH_SUSPECT`（条款引的文本层 kΩ 成 kW 且无 µ——1.3 审计记 `unit_glyphs: SYMBOL_FALLBACK`、诊断 `DATASHEET_UNIT_GLYPHS`——而单位是 ms/mA/mH/W）、`RATING_AT_TEST_TEMP`（功率/电流额定只在 ≤25 °C 单点给出却按 GUARANTEED_LIMIT 用）、`BOUNDING_CELL_AVAILABLE`（写了 NONE 而文字对上某格的参数词，`catalog.CELL_WORDS`）；门禁按结果文件所在目录解析条款 `source`。由 R7 四份记录定：claude1 的 P1 发现 F-FBOPEN 源于把 OVP 检测延时的 "ms" 当真（实为 µs），claude2 注明误码后结论相反；带公差输入写模板理由绕过角点的 14/6/28 条；25 °C 额定当保证界 3/0/7/9 条；539 条余量只有 1 条写了格。用户决定 A–E 全做（2026-10-25）。 |
| 2026-10-26 | 审查者阅读路径按读者分层：每份参考文件第三行写读者（审查员 / SR 维护者 / 审查员与 SR 维护者），SKILL.md 的参考文件表加读者列并列全 20 份，执行流程 ①–⑤ 只引审查员读的文件，SKILL.md 的“规则维护”一节移到本页“四、规则维护”；`scripts/tests/test_reading_path.py` 核对标记与表一致、流程不引维护者文件，并记录审查员阅读路径字节数的棘轮（`REVIEWER_PATH_MAX_BYTES`，只许减） | 改前 SKILL 57.9 KB + 20 份参考 662 KB 无读者标记，四份未进参考文件表；改后审查员路径 = SKILL 55.4 KB + 18 份 627 KB = 682.8 KB，维护者专读 architecture.md、review-charter.md 38 KB；大头仍是 check-catalog（131 KB）、plan-and-results（116 KB）、automation（87 KB），按步骤拆分留作后续。用户 2026-10-26：“剩下的优化你可以做” |
| 2026-10-26 | 器件类别只登记一次：`device_kinds.KINDS`（名称、位号前缀、词、手册线索、两端件、链路件、保护件、由类别单独决定的磨损类、可否声明），`part_words` 的前缀表与关键词表、`board_intent.DEVICE_KINDS`、`datasheet_kinds.KIND_CUES` 的分立部分、`plan_circuits.wearout_class` 的直接项、`circuit_candidates.PROTECTIVE_KINDS` 都是它的视图，`device_kinds.errors()` 自检（前缀锚定、词可编译、线索去空格小写、磨损类存在、链路件必两端、IC 角色不重登）；登记表顺序即关键词优先级，加类别只改一行 | 当天的 ntc/varistor 扩表改了五个模块七处清单；关键词表 21 条、前缀表 22 条、两端/链路/可声明集合与改前逐项相同，回放 195/195、典型电路 117/180/14 不变。用户 2026-10-26：“剩下的优化你可以做” |
| 2026-10-26 | 结构化字段是主路径：单位表 `scripts/units.py`（SI 前缀 × 电学基本单位，µ/u、Ω/ohm、²/2 同义，Vac/Arms/°C/%/ratio/A²s/mV/K 等专名，每个量纲的板级合理范围 `SPANS`），功能复核加三个提示（`review_functions.quantity_hints`）：UNIT_UNKNOWN（余量或限值单位表外）、QUANTITY_IMPLAUSIBLE（限值两端或余量上端换算后越出量纲范围）、RESULT_NARRATIVE（`calculation.result` 超 300 字或带超 8 个余量和限值都没承载的数字），`RESULT_MAX_CHARS` 由 review_functions 定义、报告引用；`audit_parameter_claims` 改用同一张单位表比较并给越出范围的行 `plausibility` 备注 | R7 四份记录 result 里的“数字 + 单位”117/107/514/561 个对余量 151/181/111/96 条，超 300 字的 result 0/0/10/13 个；新提示 RESULT_NARRATIVE 3/0/10/13，UNIT_UNKNOWN 0，QUANTITY_IMPLAUSIBLE 0（单位拼法 60 种全部入表）。用户 2026-10-26：“剩下的优化你可以做” |
| 2026-10-26 | 派生检查项不落盘：台账只装功能判定和手填检查项，门禁、报告、打包、对比读取时由计划和功能派生（`results_model.materialize` = derive + expand），`derive_rows.py` 只检查不写（去掉 `-o`），`pack_review` 打包时剥掉 `derived: true` 的检查项（`results_model.strip_derived`，注记和审查员自己的 `function_id` 绑定留残根，manifest NOTE 记条数），没有功能派生的残根门禁点名报错；手填检查项自带移交时不再要求功能列移交 | R7 四份记录 525/515/777/690 条检查里 453/436/634/582 条是派生副本，占记录 43–59 %（1.08→0.47、1.20→0.69、2.76→1.33、3.47→1.41 MB）；三份记录里 1/0/10 条副本的结论只存在于副本（当前规则不再派生它）、4/10/28 条注记残根没有功能派生——这些现在由门禁点名。用户 2026-10-26：“第三第四项也做” |
| 2026-10-26 | 等交付物与审查发现分开：DELIVERABLE_PENDING 开放项挡住的 INSUFFICIENT 不是阻断项（`validate_review` 列进 `pending_deliverables`，`release_for` 最高 CONDITIONAL_GO），待办仍派生（带 `deliverable{kind, owner, deliverable}`）但报告把它列进“等交付物”一节（编号、交付物、负责方、类别、可能后果、等它的判断、按什么假定判的、怎样算交付、涉及检查，`render_deliverables`），不进待办、不进最先要解决的 3 件事，结论段和数字一览各带一句 | R7 四份记录在等交付物的检查项 52/36/141/90 条（P0 0/4/14/16），阻断项 97→45、48→12、273→132、131→41；claude1 的 72 条资料不足里 52 条在等图纸或配置表，占满待办与前三件。用户 2026-10-26：“第三第四项也做” |
| 2026-10-26 | ④ 疑点分层：派生检查项（`derived`，`open_ref`）的文字是 `expand` 按开放项写的，筛查对它们读开放项一次——定级整批同级按缺口数（开放项和它的检查项算一个）、时序窗口看开放项的 `scenario`/`allowed_window`/`response_bound`、下游/固件/计算误记读开放项的 `what`/`acquisition`/`closure`/`why_insufficient`/`deliverable`/`spec`（`review_quality.misfiled_items`），对象越界、后果引外部位号、引用本记录只看手填检查项；疑点 `check_ids` 列开放项挡住的检查项 | R7 四份记录疑点点到的检查项 352 / 95 / 63 / 76，其中派生 253 / 50 / 63 / 63：codex2 的 13 条时序窗口疑点全指向一条已写好窗口的开放项，codex1 同规则整批同级 92 项来自 6 条开放项，对象/后果越界 18 项全是派生检查项；FIRMWARE/CALCULATION 两个提示只读检查项的派生字段（4.2 的另一会话提出迁到开放项）。用户 2026-10-25 “接着严格审核 4.3” |
| 2026-10-26 | 5.2 打包与交付的严格审核：`pack_review` 把台账名的引用解析到 `record/`（不复制，`ledger_name`），SR 技能目录内的引用按 `skill_version` 解析并自动记 `skill` 输入、声明为输入的只给 NOTE（`inside_skill`），单个证据超 300 KB 给 NOTE 并记 `evidence_bytes`，引用手册/标准文本抽取而无含 PDF 的输入时拒绝、抽取与输入 PDF 同名时 NOTE（`DATASHEET_TEXT_RE` / `input_pdfs`）；manifest 加 `notes`，main 打印 NOTE | R7 四份交付：台账副本 5/2/5/5 个（7.0/0.2/3.7/3.9 MB），证据 >200 KB 12/0/5/5 个，整本手册抽取 0/0/26/29 本，SR 自身文档被声明为输入 1/0/1/1 份，两份 Claude 记录没声明手册目录；用户：“5.2 的 A–F 全部执行” |
| 2026-10-26 | 5.1 渲染报告的严格审核：功能表每方面只写决定性余量、同一比较只写一次、`result` 超 300 字取第一句、问题里 >8 位号写个数（`decisive_margins` / `short_question`）；移交表只在每字段至多一个位号槽时合并（“每只、每只”串接消失）；图说不重复 caption 的“现状/改后”，`pages` 非数字按原文印，“涉及的检查”“影响哪些判断”超 6 条写个数、同一出处只写一次（`listed` / `page_word` / `fold_blocks`）；“未问”段只列方面名；`review_quality` 加 TASK_TITLE_LONG（> 60 字）；summary 复述检查计数被拒 | R7 四份报告量化：依据列最长 2419 字、重复余量句 3/4 行、“每只”错乱 2/0/2/2 行、图说重复 3、标题 > 60 字 8/0/16/10 件、影响句最长 1486 字、claude2 summary 带计数；用户：“5.1 的 A–G 全部执行” |
| 2026-10-26 | 第一次扩表：词表加 `ntc`、`varistor` 两个器件类别（`part_words.NTC` / `VARISTOR`，按共用词和 Thermistor 符号，TH/RT/NTC 前缀最弱，RV 前缀不作依据），声明词表、手册线索、磨损类、保护件判定随之读类别；定界表加 VAR-UC、VAR-VC、VAR-SURGE 三格（不估算） | R7 四份记录各 3 条 NEW_DEVICE_KIND（RV101、TH101、TH601）；用户：“先把 ntc 和压敏电阻两个器件类别补进 part_words 词表和定界表（五列齐）” |
| 2026-10-26 | 判决边界按器件类型：定界表每格加可得性、允许的估算与倍数（按后果类）、失效后果、样机能否验、边界五列（`catalog.Bound`，`estimate_rule(cell, class)`），新增 CAP-SURGE-V、MOS-DISCHARGE-I2T、IC-GATE-DRIVE-I；估算判 PASS 由 格 × 后果类 决定（`function_reading.estimate_passes`），规则 id 清单只在 `cell: NONE` 时作默认；余量写 `estimate_factor` 等于格的倍数、格给的余量下限要满足、DAMAGE_OR_HAZARD / CORE_LINK_LOSS 任何格不估算；估算 PASS 是 C 级证据，`release` 最高 CONDITIONAL_GO（`validate_review.release_for`），报告单列“按典型值估算的结论”；表可增长：门禁 `extension_signals` 记 NEW_DEVICE_KIND（分类器认不出的位号）与 NEW_BOUND_CELL（已知类别写了 NONE），`UNOBTAINABLE_DATUM` 提示向厂家索取行业不给的数，`sr_feedback` 加 `cell_boundary` | 用户 2026-10-26：“SR 不允许用典型值或 25 °C 单点额定判 PASS，没有保证界就只能开放，这个我觉得是目前比较大的问题……判决的边界应该按照器件类型来……这个器件类别也是可以增长的”；R7 四份记录光耦 CTR 四条、齐纳低电流三条按典型曲线算出 2–4 倍余量仍只能开放，因为落在 PRO-E01 / 损坏类规则下；六个待定点用户逐点判定取建议项（决定记录 docs/2026-10-26-cell-boundary.md） |
| 2026-10-26 | 结果格式 7：条款加 `refs`——这条条款说的是板上哪几只器件。手册来源（`ds/`、`datasheets/`、`manuals/` 下的抽取，或资料审计里某位号的那份文件）、BOM 行来源和带 `setting` 的条款必填且至少一个，需求、标准、工程假定选填，NETLIST_FACT 写了要含 `pins` 的位号；门禁核位号在网表或 BOM 里、不重复、`setting.ref` 在其中，并按计划冻结的资料审计核归属：位号的资料是另一份而条款 `source` 不是它即拒收（第一个能机器查的张冠李戴）；位号不在本功能对象里只提示 CONDITION_REF_OUTSIDE_FUNCTION；门禁输出 `parameter_sheet`，报告新节“器件参数表”（简洁版每器件一行，`--detail full` 逐参数），`compare_reviews` 新节“逐器件参数引用”；`margin` 不加位号（经 `basis` 指向条款）；格式 6 的记录不读（用户：“条款 refs 方案按文中四条推荐落地，一次提交”，决定记录 docs/2026-10-26-condition-refs.md） | R7 四份记录 1187 条条款里 68 / 201 / 187 / 112 条从文字认不出是哪只器件、多位号功能分不清；报告出不了逐器件参数表，资料审计知道每个位号的资料却核不了条款归属，两份记录无法逐器件对比参数引用 |
| 2026-10-26 | 参考文件按步骤拆分：`plan-and-results.md`（117 KB，①–④ 共用）拆成 `intent-format.md`（①）、`plan-format.md`（②）、`results-format.md`（③④）、`gate-and-rerun.md`（④），规则正文里的决定日期和验收数字移出（架构决定表和台账保存）；`automation.md` 的扫描流程与计算工具拆成 `scans-and-tools.md`（审查员），检查器留在 `automation.md`（审查员与维护者）；`check-catalog.md` 改为维护者文档，审查员在 intent 里要写的功能电路、器件角色、需求类别三张表由 `catalog.py --write-doc` 另生成 `review-vocabulary.md`（28 KB 代替 131 KB）；阅读路径的闸从总量（685 KB）改为按步骤计量（`test_reading_path.STEP_MAX_BYTES`：① 244 / ② 185 / ③ 221 / ④ 118 / ⑤ 55 KB，棘轮只许减）（用户：“按照你的建议来改”） | 审查员在每一步都把 117 KB 的台账文档整份带进上下文，③ 判断要读的 40 KB 埋在 intent 字段表和计划合并规则之间；总量闸量不出每步的实际负担；规则文字夹着“R7 验收 2026-10-25：……”这类来历，读规则的人要先分辨哪句是规则 |
| 2026-10-26 | 检查器的共用约定（引脚名写法、电源轨身份、识别依据三级、器件类型核验、参考地分区、电路候选、装配状态、器件脚表、指纹绑定、清单与计划、缺口与结论）从 `automation.md` 分出成 `checker-conventions.md`（审查员）；`automation.md` 只留各检查器查什么和 intent 里怎么声明它（审查员与维护者，② 仍读）；① 的链接从 70 KB 的检查器文档改为 19 KB 的约定（① 243567 → 192321 字节，② 不变）（用户：“如果对 SR 有价值就做”） | ① 1.3 为参考地分区和电路候选两段链接整份检查器文档；共用约定是审查员写 intent 时读的材料，和检查器实现放在一起读者分不开 |
| 2026-10-26 | 接口网络带 `power_node`（电源轨、开关节点、变压器绕组、整流桥上的网络）；电路对与链路只在其余网络上问 SIG-T04 方向和 SIG-C07 逻辑电平，只剩功率网络（且不跨供电域）的电路对不出检查项、不建框架，覆盖审计同样只要求这些（用户：“我同意这么做，请修改”） | R8 三份记录都为 AUX_AC（辅助绕组）、SR_D（同步整流漏极）、RECT（整流母线）各出一个接口框架和两行数字信号检查，审查员只能写“没有数字门限”判通过；codex1 的两个这种框架截断后同号 |
| 2026-10-26 | 不审配置表：手册声明的能力判为功能可达，取消配置值检查规则、CFG 内容域、DELIVERABLE_PENDING / CONFIGURATION_TABLE 与 `intent.devices.<位号>.configurable`（写了即拒收）；硬件按手册允许的配置范围判，只在某个设置下成立的条款仍标 `setting`，门禁汇总成 `configuration_settings`，报告在“交给后续环节的要求”下列“配置表要写的设置”；输出档位改由 `devices.<位号>.set_points` 声明，仍逐档核精度；“协议角色与能力”判据改为手册声明的能力；需求行上功能派生的更差结论不再被绑定行覆盖（用户：“这种器件手册已经有声明，但是配置表没有的情况，这种可以判断为功能可达，不需要再单独查验配置规则”） | R8 两份记录各把 U601 七组配置判 INSUFFICIENT 等配置表，codex3 另挡 8 行并把准出压到有条件定稿；codex1 用同一缺口挡 PD 协议需求行，被绑定的两行硬件 PASS 覆盖后无合规写法，停在 ③ |

## 四、规则维护

（2026-10-26 从 SKILL.md 移来：这些是维护者的步骤，审查员的流程不读它们。）

- 加字段、加质量筛查或加结论词之前，先查现有字段、规则或筛查能否表达；能表达就复用，新增时写明现有哪一项覆盖不了。
- 同一块板由两名审查员（或两次运行）各出一份记录时，用 `python3 scripts/compare_reviews.py <记录A> <记录B> --md compare.md` 对比：
  精确配对只按检查项标识（`check_key`：规则、规则版本、去掉电路名的对象、判据）配对，报配对率、已答比例和一致率，列出通过对失败和 P0/P1 分歧；
  按电路对齐的结果只作建议配对，确认后用 `--alias` 带位置引用加入精确配对；"电路决定与成员差"一节逐候选列两边的决定（accept / merge / split / reject 及去向）、
  对齐电路里只在一边的位号、未归属器件两边的处置（add 进电路还是留给 REQ-Q08），电路划分的差异在这里数，不混进配对率；
  “逐器件参数引用”一节按位号、参数词、单位对齐两边带 `refs` 的数值限值条款，列出限值不同的和只有一边读了的。
  差异里反复出现的写法先找现有校验为什么放过，再加机器能数的护栏，不加措辞要求。
- 新脚本先在 [架构说明](references/architecture.md#二每个脚本属于哪一步) 归到一步并分类：入口（执行流程里直接调用）、工具（特定情形手动调用）、库（只被导入）。只有入口写进执行流程；新增入口属于架构调整。
- 工程规则身份由 `scripts/electrical_contract.py`（`engine_identity`）与 `scripts/skill_identity.py` 计算：算法、常量、受控正文和规范判据变化要求按当前规则重新验证；说明/接口页、入口元数据、测试及 Python 注释变化只做兼容检查。未知规范文件仍按规则处理，不能自行把判据降为说明。
- 规则编号、判据、审查要点归属和功能电路只在 `scripts/catalog.py` 登记，改后运行
  `python3 scripts/catalog.py --write-doc references/check-catalog.md` 和 `--write-doc references/review-vocabulary.md`（审查员的三张名称表）。来源为“全板通用”“电路检查项”的新规则
  登记后即自动展开；来源为“计划逐对象生成”“Lint 内置”或检查器的规则，还要在计划生成的对应层（电路与器件 `plan_circuits.py`、接口 `interfaces.py`、
  系统功能 `plan_system.py`、全板与覆盖 `plan_board.py`；`plan_review.py` 只做汇总）、`lint.py` 或对应检查器里实现展开/扫描。新增或调整规则先回答 [审查要点中的三个问题](references/review-charter.md#用审查要点指导进化)。
- 测试分两层（[分层定义](scripts/tests/conftest.py)）：每次改动先跑约定测试 `python3 -m pytest scripts/tests -m contract -q`（[规则约定](evals/rule_contracts/README.md)、校验器不变量、解析器，几秒）；新增 A/E/T/V/H 规则须同时加触发板与近似板。措辞层 `-m wording` 是每个台账夹具一份 golden 报告，改报告措辞用 `SR_UPDATE_GOLDEN=1` 重写快照并审读 diff。改规则或检查器后跑[变异门](evals/mutation/README.md) `python3 evals/mutation/run.py --changed`（只跑落在改动文件上的变异，几分钟），提交前或发布前跑全量 `python3 evals/mutation/run.py`；每条变异都要被单元测试杀死。
- 修改脚本后运行 `python3 -m unittest discover -s scripts/tests -q`（全量，含两层）；改导入器时同时跑 [真实来源导入回归](evals/input_bench/README.md)；改 KiCad 解析、自检、日志扫描、去耦清单或计划展开时跑 [KiCad 原生交付回放](evals/kicad_replay_bench/README.md)。改检查器或规则后跑 [典型电路基准](evals/typical_circuits/README.md)（42 块开源板，每条报出都要已归类，新出现的须逐条审读）和 [种子基准](evals/seeded_bench/README.md) 看自动层检出；改定级、汇总、待办或报告逻辑后跑台账回放（schema 3 台账已退役，待一份按功能判定方法冻结的真实审查记录重建）；`python3 evals/bench_coverage.py --seeded <注入基准 results.json>` 列出每条 A 规则在哪个基准有真实板正例、哪些还没有。评测通过不等于任何真实电路审查通过。

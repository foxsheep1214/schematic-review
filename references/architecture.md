# SR 架构说明

SKILL.md 的“架构”一节是总图：五环流水线、各环谁做、不变的决定、改架构先问人。本页是它的明细：
环与环之间传哪些文件、每个文件的格式版本、每个脚本属于哪一环，以及历次架构决定。
本页的数据文件表和脚本表由 `scripts/tests/test_architecture.py` 对照代码检查：新增、删除脚本或改格式版本而不改本页，测试失败。

## 一、环与环之间的文件

每一环只读前面各环写下的文件，自己只写下表里属于它的文件。审查员的声明集中在 `intent.json`，
它不是某一环的产物，是审查员给“读入”和“出计划”两环的输入。

| 文件 | 谁写 | 写在哪一环 | 格式版本 | 内容 |
|---|---|---|---|---|
| `db.json` | 工具 | ① 读入 | — | 网表、BOM 列、页、符号脚：图上实际是什么 |
| `requirement_source`（需求原文抄录） | 工具 | ① 读入 | 1 | 需求文档逐字抄录与 sha256 |
| `datasheet-audit.json` | 工具 | ① 读入 | — | 每颗物料的资料是否找到、是否核实 |
| `intent.json` | 审查员 | ①② 的输入 | 4 | 需求理解、任务剖面、电源轨、器件类别与配置组、电路取舍、装配状态、规则缺口 |
| `record/circuit-candidates.json` | 工具 | ② 出计划 | 2 | 候选电路及成员 |
| `review-plan.json` | 工具 | ② 出计划 | 7 | 功能树、每行检查、功能框架、各检查器清单、接口 |
| `review-results.json` | 审查员 | ③ 判断 | 6 | 功能判定（条件、计算、余量及其推界方式与公差端、开放项及其单侧定界、失败项）和由它派生的行 |
| `review-gate.json` | 工具 | ④ 校验 | — | 对账结果、阻断项、待办 |
| `审查报告.md` / `审查报告.html`、`record/` | 工具 | ⑤ 出报告 | — | 交付物：报告与留档 |

## 二、每个脚本属于哪一环

“入口”是执行流程里直接调用的命令，只有入口写进 SKILL.md 的执行流程；“工具”是特定情形手动调用的命令；
“库”只被导入。新脚本先在这里归环归类，再写代码。

| 环 | 入口 | 工具 | 库 |
|---|---|---|---|
| ① 读入 | `parse_netlist.py`、`parse_kicad.py`、`read_bom.py`、`requirements_extract.py`、`audit_datasheets.py` | `install_kicad_cli.py` | `page_inventory.py`、`datasheet_kinds.py`、`electrical_contract.py` |
| ② 出计划 | `lint.py`、`circuit_candidates.py`、`circuit_decisions.py`、`gap_inventory.py` | `plan_review.py`、`decoupling.py`、`i2c_topology.py`、`reviewed_declarations.py` | `catalog.py`、`plan_circuits.py`、`plan_system.py`、`plan_board.py`、`interfaces.py`、`row_owner.py`、`board_intent.py`、`board_scans.py`、`requirement_parameters.py`、`requirement_bindings.py`、`rule_gaps.py`、`independence.py`、`checkers/` |
| ③ 判断 | `derive_rows.py` | `calc.py`、`solve_dividers.py`、`simulate_rc.py`、`audit_parameter_claims.py` | `circuit_bounds.py`、`model_bounds.py`、`bound_formulas.py`、`boost_switch_loss.py`、`flyback_stop.py`、`fault_energy.py`、`zener_fault.py`、`bom_constraints.py`、`design_preflight.py` |
| ④ 校验 | `validate_review.py` | — | `results_model.py`、`review_functions.py`、`review_quality.py`、`review_stage_scope.py`、`review_summary.py`、`review_workflow.py`、`task_scope.py`、`requirement_clarifications.py`、`validate_remediation.py`、`review_engine.py`、`skill_identity.py`、`check_key.py` |
| ⑤ 出报告 | `render_report.py`、`pack_review.py` | — | `report_html.py` |
| 复审 | `diff_netlists.py` | — | `revision_impact.py` |
| 维护 SR | `catalog.py --write-doc` | `compare_reviews.py`、`check_ledger.py`、`run_regression.py` | — |

`catalog.py` 是规则的唯一登记处，既被出计划导入，维护时也用它重写规则总表。
`independence.py` 在出计划时拒收引用设计方文档的声明，在校验时拒收这样的证据，两环共用。

## 三、历次架构决定

改架构按 SKILL.md“改架构先问人”办理；确认后在这里加一行，台账条目写明确认的日期和原话。

| 日期 | 决定 | 为什么 |
|---|---|---|
| 2026-10-20 | 判断的单位是功能，不是检查行；结果格式 4：缺口只写在功能的开放项上一次，行由功能派生并用 `open_ref` 指向它 | 逐行判断让同一缺口抄在几十行，结论互相矛盾 |
| 2026-10-21 | 计划按功能树组织，每行恰有一个所属；电路由候选和决定推出，不手画 | 两份记录对不上，配对率只有一半 |
| 2026-10-22 | 只认四类输入，设计方文档不进 | 审查要独立，不能让设计文档设定判据 |
| 2026-10-23 | 退役工具自动算保证值结论（evidence.json）；E 行由审查员按规格书判定，公式库留给审查员复算 | 两份 R5 审查都没用到，结论全走功能判定 |
| 2026-10-23 | 框架行只能委托给另一个计划框架（8a），跨电路的缺口写在拥有缺失量的框架里、其他框架的行用 open_ref 指向它（8b），审查员自建的功能只取没有电路框架完整包含的对象（8c）；只装不属于任何框架的行（用户确认：“拒收”；“第 8 条按建议定：8a–8c 都做，跨电路的缺口按 8b 写在拥有缺失量的框架里”） | 一次审查把每个缺口各建一个功能、把电路功能判通过再把行挂过去，报告里待办重复成功能，电路结论前后不一 |
| 2026-10-23 | 结果格式 5：决定结论的余量写推界方式（`basis.derivation`，测试点外推须写 `monotonic`，温度系数须写 `tempco`，典型曲线只能是 ESTIMATE）和每个带公差输入取的哪一端（`basis.corners`），判“定不出界”须答 `monotonic_tried`（1a–1c）；经需求文档条款的边只能挡绑定到该需求的行，隔离两个方面改为全板方面（1d）；工程计算（C）方面判通过须有证明它的余量，厂家参考电路例外（1e）；格式 4 的记录不读（用户确认：“第 1 条按修正后的建议定：1a–1e 都做，1d 用‘需求条款只能挡绑定该需求的行’，格式升到 5。”） | 两份 R5 审查一份 163 条边经需求条款挡行、只有 3 条余量，另一份把不利一侧的界标成保证界、按标称值取 NTC；同一电路的结论差在定界口径而不在电路 |
| 2026-10-23 | 计划格式 7：电路检查项按“类型 × 规则”的网表前提（`catalog.SUBJECT_REQUIRES`）派行，前提不成立不派、功能框架记 `not_asked`、报告列“未问”，行对象取前提找到的器件（2a）；类型对电路问到不到一半时计划提示换类型（2b）；只说不适用、不引网表事实的通过被拒（2c）；前提成立仍记 NA 的须引网表事实（2d）；格式 6 的计划不读（用户确认：“第 2 条按建议定：2a–2d 都做，计划格式升到 7。”） | 两份 R5 审查 42 行一边 NA 一边通过：计划对每块电路派该类型的全部规则，没有这个机制时写法各异 |
| 2026-10-23 | intent 格式 4：可编程器件逐配置组核配置值（新规则 CFG-D01，新内容域 CFG），已知角色用 SR 固定的配置组（pd_controller 七组），没有固定组的可编程角色要求声明，组写在 `intent.devices.<位号>.configurable`（3a、3b）；硬件按手册允许的配置范围判，只在某个设置下成立的条件标 `setting{ref, group, value}` 并写进配置行（3c）；配置表缺口只挡 CFG-D01 行和需求行（3d）；配置表统一记 DELIVERABLE_PENDING / CONFIGURATION_TABLE，工厂选项归 DEV-D01（3e）；只有样机能给的结论记阶段 NA 并移交（3f）；写了输出档位的组另问逐档精度（第 7 条第六类）；格式 3 的 intent 不读（用户确认：“第 3 条按建议定：3a–3f 都做，已知角色用 SR 固定的配置组，intent 格式升到 4。”） | 两份 R5 审查一份让一件“配置表未交付”挡 57 行（另一份判通过 28 行），把片内补偿记成设计没定；另一份按默认值判通过、补偿以“靠实测”判通过；交付物类型三种写法 |
| 2026-10-23 | intent 格式 4 加任务剖面 `mission_profile`：各时段时长占比、负载、环境温度和设计寿命内的次数，各引需求原文，所有寿命行按这一份剖面算（6d）；电解、固态与超级电容按符号、BOM 料号/规格或铝电容封装识别（6c），耐久按厂家寿命公式或 10 °C 翻倍估算写成 BOM 约束、热点移交热设计、不开 VENDOR_DATUM（6a）；光耦写寿命末所需 CTR 保留比例、不自编衰减系数（6b）；其他耗损件派固定行 DEV-C06，次数没给记 NA（6e）；随第 3 条的格式 4 一起，不再升版（用户确认：“我同意”，按“对寿命敏感的器件类型”表定检测范围） | 两份 R5 审查一份按 87600 h 全时、一份按 29200 h 满载算 10 年，一份不接受 10 °C 翻倍开了厂家数据项、另一份写成 BOM 约束，光耦寿命一份开项一份没问 |
| 2026-10-23 | 结果格式 6：判“定不出界”的缺厂家数据用数写定界尝试（`monotonic_tried{side: UPPER 或 LOWER, quantity, operating_point{min, max, unit}, test_points[{condition, at}], why_not, other_side}`）：工作点落在两个测试点之间就按相邻测试点定界，不准开项；只有一部分在测试点之外时只开外面那段（`open_range`），里面那段写余量；每条边写开着的一侧（`side`），另一侧写 DECIDED（有余量）或 NOT_DECISIVE（写理由）；`why_not` 不得照抄 `not_boundable_reason`；格式 5 的记录不读（定界一致性方案第 1 条；用户在逐项选择中对第 1 条选“做”） | R5 验收重审中一份审查的 19 条缺厂家数据，16 条把同一句话写成不利侧并照抄理由当 why_not；其中一处工作电流正好落在两个测试点之间，另一份审查据此定了界 |
| 2026-10-23 | 结果格式 6 加两处（定界一致性方案第 2、3 条）：缺厂家数据的 `specified_by` 不得是没覆盖工作点的测试点，引典型曲线时写 `typical_estimate`，估算已经不够记失败项、失败项余量可按典型曲线记 REACHABLE_CASE（第 2 条，2-A 用户原话“2A，算。”）；设计值写 `undecided[{ref, parameter[, unit]}]`，BOM 行已写的参数不算没定，由另一个开项决定的量写 `depends_on`（只挂一层），它挡的行在待办和报告里并到那个开项下（第 3 条；用户在逐项选择中对第 2、3 条选“做”） | 一份审查的 19 条缺厂家数据都拿没覆盖工作点的测试点当“写了这种用法”；反激故障钳位记成设计值，其实由板上保护链决定、另一份审查算出了 P1 |
| 2026-10-23 | 工作点定界表：器件参数能不能定界、按什么推法和公式、推不出记哪一档，登记在 `catalog.BOUNDS`（每格：器件类别、参数、开着的一侧、随什么变和方向、按顺序的推法 G1–G10/SOA/强制 β 及其公式、推不出时 VENDOR_DATUM / OUTSIDE_SPECIFIED / BOUNDED），公式在 `bound_formulas.py`，`references/bounding-table.md` 由表生成；表里有的必须按表（A，用户：“必须按表”），判“定不出界”写格（`monotonic_tried.cell`，表外写 NONE），门禁核对格的一侧、档位和单调方向，余量写 `basis.cell/method/formula` 时门禁重算；MOS 高温 SOA 按持续时间选曲线、按开始壳温降额、恒功率段 100%/热不稳定段 80%，允许壳温和散热要求交热设计与 PCB（B，“B 热不稳定段按修订写法定：按持续时间选曲线、按开始壳温降额、降额后留 80%。”“这里也可以给出散热结构设计上的要求，交给下游的PCB设计”）；检测用 NTC 有表用表、没表按 B 值加公差算保证（C，“有表用表，没表外推算保证”）；BJT 饱和按强制 β、k = 2（D）；浪涌限制 NTC 热态按 0 Ω 定结论（E）；不变的决定第 4 条补一句：定界按表执行、门禁按表重算核对，工具仍不自动出结论（用户在逐项选择中对定界表选“做”） | 同一张手册表，一份审查判“推不出”开项，另一份推出来判通过或失败；定界原则散在四份参考文档和十几条判据里，是文字不是公式，门禁比不了数 |
| 2026-10-24 | 8b 的做法定下来：跨电路的缺口只写在一个功能的开放项上，开放项的 `decides` 用 `check_ids` 点名另一电路受它挡住的行，`derive_rows.py` 让那些行的 `open_ref` 指向它；没点名的行仍只能取本功能的开放项，失败项不跨功能（SR 自查 2.6，用户选：“允许指向别的功能的开项”） | 8b 原先写成“其他框架的行用 open_ref 指向它”，校验却要求 open_ref 属于本行的功能，照着做被拒收，只能各抄一份缺口 |
| 2026-10-24 | 估算可以判通过：`ESTIMATE` 余量写 `consequence_class`（只能是 REQUIRED_FUNCTION 或 PERFORMANCE_OR_LIFE）和 `handoff`（本功能 `handoffs` 里样机实测那一条的序号），满足时行判 PASS，派生行带上这条移交；损坏、过热、保护类规则（DEV-C01、DEV-C04、PWR-C03、PWR-C06、PWR-C10、DRV-C01、全部 PRO）不走这条路（SR 自查 2.1，用户选：“估算 + 样机移交可判通过”） | 文档和 DEV-C05、DRV-C02 判据都写“相似器件或典型 ±30% 估算、结论不变就 PASS(B) 并移交样机”，门禁却对 ESTIMATE 什么都不判，照着做被拒收 |
| 2026-10-24 | intent 与计划、结果一样严：`schema_version` 必写，顶层只认 `INTENT_FIELDS` 与各检查器的段；门禁命令行总是要求绑定和计划的依赖记录（去掉 `--require-bindings`），宽松默认只留给直接调用库的测试（SR 自查 2.7、2.8，用户选：“改成必填”“字段白名单 + 版本必填”） | 拼错的顶层字段（`power_rail`）静默放行、全部轨没声明；真实计划都带这些键，缺了反而少查 |

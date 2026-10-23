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
| `intent.json` | 审查员 | ①② 的输入 | 3 | 需求理解、电源轨、器件类别、电路取舍、装配状态、规则缺口 |
| `record/circuit-candidates.json` | 工具 | ② 出计划 | 2 | 候选电路及成员 |
| `review-plan.json` | 工具 | ② 出计划 | 6 | 功能树、每行检查、功能框架、各检查器清单、接口 |
| `review-results.json` | 审查员 | ③ 判断 | 4 | 功能判定（条件、计算、余量、开放项、失败项）和由它派生的行 |
| `review-gate.json` | 工具 | ④ 校验 | — | 对账结果、阻断项、待办 |
| `审查报告.md` / `审查报告.html`、`record/` | 工具 | ⑤ 出报告 | — | 交付物：报告与留档 |

## 二、每个脚本属于哪一环

“入口”是执行流程里直接调用的命令，只有入口写进 SKILL.md 的执行流程；“工具”是特定情形手动调用的命令；
“库”只被导入。新脚本先在这里归环归类，再写代码。

| 环 | 入口 | 工具 | 库 |
|---|---|---|---|
| ① 读入 | `parse_netlist.py`、`parse_kicad.py`、`read_bom.py`、`requirements_extract.py`、`audit_datasheets.py` | `install_kicad_cli.py` | `page_inventory.py`、`datasheet_kinds.py`、`electrical_contract.py` |
| ② 出计划 | `lint.py`、`circuit_candidates.py`、`circuit_decisions.py`、`gap_inventory.py` | `plan_review.py`、`decoupling.py`、`i2c_topology.py`、`reviewed_declarations.py` | `catalog.py`、`plan_circuits.py`、`plan_system.py`、`plan_board.py`、`interfaces.py`、`row_owner.py`、`board_intent.py`、`board_scans.py`、`requirement_parameters.py`、`requirement_bindings.py`、`rule_gaps.py`、`independence.py`、`checkers/` |
| ③ 判断 | `derive_rows.py` | `calc.py`、`solve_dividers.py`、`simulate_rc.py`、`audit_parameter_claims.py` | `circuit_bounds.py`、`model_bounds.py`、`boost_switch_loss.py`、`flyback_stop.py`、`fault_energy.py`、`zener_fault.py`、`bom_constraints.py`、`design_preflight.py` |
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

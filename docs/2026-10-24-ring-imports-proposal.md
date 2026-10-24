# 方案：脚本的环归属与导入方向一致（SR 自查 5.8 之二）

状态：草稿，等用户定。用户 2026-10-24 选“这次不动，另出方案”。

## 现状

`references/architecture.md`“二、每个脚本属于哪一环”把脚本按 ① 读入 → ② 出计划 → ③ 判断 → ④ 校验 → ⑤ 出报告排开，
意思是前一环不该依赖后一环。按表核 `scripts/*.py` 的顶层导入（不含 checkers/ 内部、不含复审和维护两行），2026-10-24
自查时有 12 处反向；第五组把只剩电阻解析的 `solve_dividers.py` 归到 ① 读入的库，去掉了其中 4 处，还剩 8 处：

| 导入方（环） | 被导入（环） | 用到什么 | 性质 |
|---|---|---|---|
| `parse_netlist.py`（①） | `checkers/netgraph.py`（②） | `CONNECTOR`、`classify` | 器件分类词表放在了检查器里 |
| `plan_review.py`（②） | `check_key.py`（④） | 检查项标识 | 计划生成标识，校验重算；标识本来属于计划 |
| `plan_review.py`（②） | `review_engine.py`（④） | `engine_identity` | 规则身份，计划和校验都要 |
| `plan_review.py`（②） | `review_workflow.py`（④） | `PHASES` | 一个常量 |
| `circuit_decisions.py`（②） | `review_functions.py`（④） | `LOCATOR_IDS_RE`、`LOCATOR_WORDS_RE` | “能定位”的判定 |
| `derive_rows.py`（③） | `review_functions.py`（④） | `decides_row`、`edges`、`judged`、`prototype_estimate`、`unjudged_message` | 功能判定的读法 |
| `derive_rows.py`（③） | `results_model.py`（④） | `text` | 一个小工具函数 |
| `bom_constraints.py`（③） | `review_summary.py`（④） | `IMPACT_CLASSES`、`HAZARD_PATHS` | 后果分类表 |

这些都不是循环导入，代码能跑；问题是表说的和代码做的不一样，新脚本照表归环时会被误导，改 ④ 里的东西也会意外波及前面的环。

## 建议

两类处理，按“东西属于谁”定，不为了凑方向硬搬：

1. **把共用的定义挪到它真正属于的、更靠前的库。**
   - 器件分类词表（`CONNECTOR`、`classify`）和第三组已集中到 netgraph 的器件词，是读入和出计划共用的“这是什么器件”，
     挪到 ① 的一个库（例如 `part_words.py`），netgraph 从那里导入。
   - `check_key.py`、`engine_identity`、`PHASES`、后果分类表（`IMPACT_CLASSES`、`HAZARD_PATHS`）、`text`、“能定位”的正则
     都是格式约定，归到 `electrical_contract.py`（① 的库，已经放着各格式版本号）或在表里把 `check_key.py`、`review_engine.py` 改记为 ① 的库。
2. **把功能判定的读法单列一个库，归 ③。** `decides_row`、`edges`、`covers`、`scope`、`judged`、`margin_verdict`、
   `prototype_estimate`、`life_estimate` 等是“这份功能判定说明了什么”，derive_rows（③）和校验（④）都读；从
   `review_functions.py` 移到新库（例如 `function_reading.py`，③ 的库），`review_functions.py` 只留校验。

再加一条机器能数的护栏：测试按 architecture.md 的表核每个 `scripts/*.py` 的导入，后环不得被前环导入，表外的脚本报错。

## 动哪些文件

- 新库：`part_words.py`（或并入 `electrical_contract.py`）、`function_reading.py`。
- 改导入：`parse_netlist.py`、`checkers/netgraph.py`、`plan_review.py`、`circuit_decisions.py`、`derive_rows.py`、
  `bom_constraints.py`、`review_functions.py`、`review_summary.py`、`review_workflow.py`、`results_model.py`；
  旧位置保留别名一轮还是一次改完，由用户定（建议一次改完，SR 不留兼容层）。
- 测试：新增导入方向测试；现有测试只改 import 行。
- 文档：`architecture.md` 的脚本表和决定表各改一处；`automation.md` 里写到函数位置的句子。
- 变异：指向被搬函数的变异条目改 `file`。

## 架构

属于架构调整（脚本的环归属、增删库），要用户点头，并在 `architecture.md`“三、历次架构决定”记一行。
行为不变：回放 195/195、典型电路计数、门禁计数全部不变才算完成。可以与“校验直接读功能判定”的方案分开做，
但两者都动 `review_functions.py` 和 `results_model.py`，同时做会冲突，建议先做这一份（只搬家），再做那一份。

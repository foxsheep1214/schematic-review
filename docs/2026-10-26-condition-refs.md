# 功能条款加位号字段（`conditions[].refs`）——方案与决定

状态：2026-10-26 用户审定“条款 refs 方案按文中四条推荐落地，一次提交”，第五节四件事均取推荐项，同日一次提交实现（台账“条款加位号字段 refs”）。本文保留方案原文作决定记录。来源：2026-10-26 第 2 项（结构化字段是主路径）留下的缺口——报告出不了逐器件参数表，因为条款上没有结构化的位号。

## 一、现在怎样

**条款的字段。** 功能判定的 `conditions[]` 每条必填 `id` / `kind` / `source` / `locator` / `says` / `use`（`review_functions.CONDITION_FIELDS`），按 `kind` 另有：NUMERIC_LIMIT 的 `limit{min,max,unit}` 和 `regime`，MANDATORY_CLAUSE 的 `applies`，NETLIST_FACT 的 `pins` / `nets`，TYPICAL_REFERENCE 的 `reference_circuit` / `curve`；只有可编程器件的设置条款带位号：`setting{ref, group, value}`。

**位号只在文字里。** 器件是谁，写在 `says`、`use`、`locator` 的文字里，或者只在功能的 `objects.refs` 里。R7 四份记录的 1187 条条款：

| 记录 | 条款数 | 文字里认得出板上位号 | 认出多个位号 | 认不出 |
|---|---|---|---|---|
| claude1 | 328 | 260 | 73 | 68 |
| claude2 | 428 | 227 | 69 | 201 |
| codex1 | 257 | 70 | 31 | 187 |
| codex2 | 174 | 62 | 39 | 112 |

认不出的典型：`source: evidence/ds/ISC032N12LM6.txt`，`use: 结温上限` / `损耗估算用` / `脉冲电流额定`——是哪只 MOS 的，只有读了功能的 `objects.refs` 才知道；功能有 3–8 个位号时就分不清。

**由此做不到的三件事。**

1. 报告没有“器件参数表”：读者问“Q401 用了手册哪几个参数、哪页、保证值还是典型值”，要翻 `review-results.json` 逐功能找。
2. 门禁核不了归属：1.3 的资料审计（`datasheet-audit.json` 的 `materials[].refdes`）已经知道每个位号对应哪份资料，但条款侧没有位号，所以“条款引的手册是不是这只器件的手册”无法机器核对（张冠李戴只能靠人看）。
3. 两份记录对同一器件同一参数的引用无法逐器件对比（`compare_reviews` 只配对检查项和电路）。

余量的 `against`（“Q401 VGS 绝限 20 V”）同样是文字；但余量经 `basis.limit` / `basis.conditions` 指向条款，位号跟着条款走即可。

## 二、改成怎样（推荐）

**字段。** 每条条款可写 `refs: ["Q401", …]`——这条条款说的是板上哪几只器件。

| 条款的来源 | `refs` |
|---|---|
| 器件手册（`source` 在资料目录里，或与某位号的资料审计条目同一文件） | 必填，≥ 1 个 |
| BOM 行（`source` 含 bom） | 必填，就是那一行的位号 |
| 需求、标准条款、`commodity-floors.md`、工程假定 | 选填（通常为空） |
| NETLIST_FACT | 选填；已有 `pins`，位号可由 `pins` 推出，写了要一致 |
| 带 `setting{ref,…}` 的 | `setting.ref` 必须在 `refs` 里 |

**门禁（④，`review_functions._condition_errors`）。**

- `refs` 是位号列表，每个在 `db.parts` 里，不重复（错误）。
- 手册来源的条款没写 `refs`：错误，消息写明“这条条款说的是哪只器件”。
- `refs` 里的位号在资料审计里对应另一份资料（`datasheet_entry_for_ref`），而条款的 `source` 不是它：错误“条款引的手册不是该位号的资料”（这是归属核对，第一个能机器查的张冠李戴）。
- `refs` 有位号不在本功能的 `objects.refs` 或成员检查项的对象里：**提示**（质量筛查 `CONDITION_REF_OUTSIDE_FUNCTION`），不是错误——共享器件的条款允许写在一个功能里被另一个功能引用，但要让人看一眼。

**报告（⑤）。** 新节“器件参数表”：

- 简洁版每只器件一行：位号、资料（文件名 + 页码范围）、引用的参数个数、其中保证值 / 典型值 / 条款各几条、用在哪几个功能；
- `--detail full` 逐参数一行：位号、参数（`says` 第一句）、限值与单位、工况（`regime`）、口径（kind）、出处（source p 页）、用在哪条余量或判断。
- 表只汇总条款，不另下结论；没有带 `refs` 的条款时不出这一节。

**对比（`compare_reviews`）。** 新节“逐器件参数引用”：同一位号、同一单位、`says` 里同一参数词的条款两边对齐，列出限值不同或一边缺的。

**格式版本。** `review-results.json` 的 `schema_version` 6 → 7：手册条款必填 `refs` 是校验变化，旧记录读进来会报一堆“缺 refs”，不如按版本号一句话拒绝（与“不兼容旧记录，用户审定进步”一致）。`intent` 和计划格式不变。

**不改的部分。** 条款的其他字段、余量结构、派生规则、开放项都不动；`margin` 不加 `refs`（余量经 `basis.limit` / `basis.conditions` 指向条款，位号从条款取）。

## 三、动哪几步、哪些文件

| 步骤 | 文件 | 改什么 |
|---|---|---|
| ③ 判断（审查员写） | `SKILL.md` 3.1；`references/plan-and-results.md` 条款字段行与例子 | 条款表加 `refs` 列和填写规则；做完的标志加“手册条款都有位号” |
| ④ 校验 | `scripts/review_functions.py`（`_condition_errors`、新 `condition_ref_errors`）；`scripts/validate_review.py`（把资料审计传给条款校验，输出 `parameter_sheet`）；`scripts/review_quality.py`（`CONDITION_REF_OUTSIDE_FUNCTION`）；`scripts/results_model.py`（`SCHEMA_VERSION = 7`） | 字段形状、归属核对、提示、版本 |
| ⑤ 出报告 | `scripts/render_report.py`（`render_parameter_sheet`）；`references/report-and-remediation.md` 节表 | 新节，简洁/完整两档 |
| 对比 | `scripts/compare_reviews.py` | 逐器件参数引用一节 |
| 测试 | `scripts/tests/test_review_functions.py`（字段与归属规则）、`test_compare_reviews.py`、金样夹具 `test_derive_rows.bias_plan` 等给条款补 `refs`，八份金样重生成；`evals/mutation` 加 4–5 条 | — |
| 文档与台账 | `references/architecture.md`（格式版本 7 与决定行）、`docs/improvement-ledger.md`、`docs/2026-10-26-condition-refs-proposal.md` 改名为决定记录 | — |

量级：代码 6 个文件、文档 5 个，一次提交；金样全部重生成（条款加字段后文本不变，参数表新节会出现）。

## 四、不改的替代

1. **从文字识别位号，不加字段。** 用 `db.parts` 的位号正则扫 `says` / `use` / `locator`。R7 只认出 23–79 %，多位号条款分不清是谁的，认错不报错。只能当“提示你补字段”的辅助，不能当主路径。
2. **用功能的 `objects.refs` 推。** 功能只有一只器件时准确；R7 多数功能 3–8 只，推不出。
3. **维持现状，参数核对靠 1.3 的 `audit_parameter_claims`。** 它要审查员另写一份 claims 文件，R7 四份记录一份都没写；而条款是审查员本来就要写的，位号加在条款上不增加一份文件。

## 五、请定的四件事

1. 手册来源的条款 `refs` 必填、其他来源选填——还是全部选填只给提示？（推荐：前者，否则参数表残缺、归属核对形同虚设。）
2. `schema_version` 升到 7，旧记录一句话拒读——还是不升？（推荐：升。）
3. 参数表简洁版每器件一行计数、`--detail full` 逐参数——还是只在 full 出？（推荐：前者，读者至少看到每只器件被引用了几个参数。）
4. 位号只加在条款上，`margin` 不加——同意？（推荐：同意。）

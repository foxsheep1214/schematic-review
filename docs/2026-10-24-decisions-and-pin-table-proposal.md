# 方案：电路决定的差异要能数、脚表加护栏（SR 审查框架分析之三）

状态：用户 2026-10-24 已定："电路决定只做对比工具一节（A），脚表三条护栏都做，带原厂代号的封装名照读。"

实施记录：同日落地。护栏 2（U/M 位号抄全却没有 power/return 脚）按方案本是拒绝，实施时撞上 KiCad 回放夹具的 U202（SOT-23-3 基准，
脚角色只有 return 和 other，这是对的），改成计划诊断 `DEVICE_PINS_NO_SUPPLY`，不拒绝；护栏 1 的脚数只读能数脚的封装族，SOT-23 / TO-220
单独不算。单元夹具里 QFN-6 配四脚、声明抄全的那处补齐了 3、4 脚。

两条都是步骤 ①② 里审查员手填、下游全信的输入；按 SKILL.md"改架构先问人"，先出方案。

## 一、电路决定（步骤 ② 任务 2.1，`intent.circuit_decisions`）

### 目的

`circuits` 是整条执行线的对象：电路行、承接电路、对比配对都以它为单位。它由候选（机器）加决定（审查员）推出。
目标是审查员只在机器拿不准的地方做决定，决定的差异能被数出来。

### 现状（核对 `scripts/circuit_decisions.py` 后，纠正我口头说过的两点）

机器已经守住的（不用再做）：

- 每个候选必须有 accept / merge / split / reject 之一，漏一个计划拒绝；
- merge、split、reject、add、own 都要能定位的引用（`LOCATOR_WORDS_RE` / `LOCATOR_IDS_RE`）；
- add 只能收没有任何候选持有的器件，每颗要写它所在的网，类型要在功能电路表内；
- 认领打平的器件必须 own，own 只能裁打平的；
- `intent.circuits` 若手写，必须与决定推出的逐个相等；
- 未归属的器件进 REQ-Q08 一行，逐颗列出，`required_inputs` 要求 add 或 reject。

所以"漏决定"和"空电路"不是问题。剩下的审查员自由度，才是两份记录电路划分不同的来源：

| 自由度 | 后果 | 现在能不能看见 |
|---|---|---|
| accept 还是 merge / split：何时把两个候选合成一个功能、何时拆，没有规则，只要引用 | 电路数不同，所有电路行的对象不同；A 合成一块、B 两块时对比只能配上一块，另一块算"只在 B" | 对比报告有"电路对齐"表和"只在 A / 只在 B"，但不说是哪条决定造成的 |
| REQ-Q08 的未归属器件：一边 add 进电路，一边留在 Q08 里答 | 成员集合不同，一边多一块电路 | 看不见（Q08 是一行，add 是电路） |
| 决定给的 `id` 是自由文本 | 对比按别名 C0/C1 配，影响小 | 已处理 |
| 新增：`role-bus` 缺口要 add | 同第二行 | 看不见 |

### 建议

**A. 对比工具加"电路决定"一节（现在做）**。`compare_reviews.py` 目前只读 `record/review-plan.json` 和 `review-results.json`；
加读两边的 `intent.json`（`circuit_decisions`）和 `record/circuit-candidates.json`（没有就跳过这节并说明）。报三张小表：

1. 逐候选：两边的决定种类和去向（accept → 电路 id；merge → 合进哪块、和谁；split → 拆成几块；reject → 原因）。两边不同的单列。
2. 逐对齐电路（沿用现有的类型 + 共同位号配对）：成员集合差，只在 A 的位号、只在 B 的位号。
3. 未归属器件：两边各怎么处置（add 进了哪块 / reject / 留在 Q08）。

JSON 报告键 `circuit_decisions`，Markdown 节"## 电路决定与成员差"。这一步只量差异，不改任何判断。

**B. merge / split 的"何时"写成可数条件（不在这次做）**。候选写法：merge 只在两个候选共用同一感性件或同一输出轨、或一条需求条款把它们写成一个流程时；split 只在候选有两个核心器件或两个输出轨时。这改变审查员判断的边界，先用 A 在 R6 验收的两份记录上数出差异在哪种决定上，再决定要不要加、加哪条。

**C. 不动**：决定的种类、引用要求、归属规则、REQ-Q08。

### 动哪些文件

| 文件 | 改什么 |
|---|---|
| `scripts/compare_reviews.py` | `load()` 加读 intent 与候选文件；`circuit_decisions(a, b)`；报告键与 Markdown 节 |
| `scripts/tests/test_compare_reviews.py`（现有对比测试所在文件） | 两份记录决定不同（一边 merge 一边 accept；一边 add 一边留 Q08）→ 节里逐条列出；没有候选文件 → 节说明跳过 |
| `evals/mutation/mutations.json`、README | 决定不同不报 / 成员差不报，各一条 |
| `references/plan-and-results.md` 对比工具一段、`docs/improvement-ledger.md` | 一句 |

## 二、脚表护栏（步骤 ① 任务 1.3，`intent.devices.<位号>.pins`）

### 目的

`pins` 是审查员从手册抄的官方脚表，`pinout_complete: true` 是审查员自述"抄全了"。下游全信它：去耦组按脚表逐供电网推出
（`checkers/decoupling.py`）、DEV-D02 的官方/符号双向差集、DEV-D05 的逐脚处置、阻容预判的脚角色。抄漏一脚，去耦少一组、
D05 少一脚，没有任何机器信号。

### 现状

`board_intent.device_errors` 只查：字段齐（mpn、package、identity_citation、citation、pinout_complete、pins）、每脚有
name 和合法 role（power / return / nc / other）、pins 非空。`package` 字符串没有任何代码读。DEV-D02 行列官方/符号差集，
那是行内容不是校验。连 `plan-and-results.md` 的示例都是 `"package": "QFN-16"`、`pinout_complete: true`、只写了两脚。

### 建议：三条护栏，都在 `device_errors` 里，机器能数

1. **封装脚数**：`package` 名能读出脚数时（`MSOP-8`、`SOT-23-3`、`QFN-16`、`TSSOP-20`、`LQFP-48`、`DFN-10`、`SOIC-8`，
   正则取主体后的 `-(\d+)`；`SOT-23-3 (DBZ)` 这类带原厂代号的照读），`pinout_complete: true` 的脚表必须含编号 1..N 的每一个；
   缺的编号列出来拒绝。多出的脚（EP、PAD、17）允许——露铜焊盘手册常编成 N+1。读不出脚数的封装（`BGA`、`custom`、模组）不查。
2. **电源与返回**：U/M 位号且 `pinout_complete: true` 的脚表至少一个 `power` 和一个 `return`；否则拒绝（去耦组按这两种脚推，
   都没有就整颗器件无声地没有去耦组）。连接器、变压器等非 U/M 位号不查。
3. **示例改对**：文档示例改成 `SOT-23-3` 三脚稳压器，三脚齐全。

不做：符号脚不在官方脚表里（`symbol_only`）不拒绝——那正是 DEV-D02 要判的事实（符号多脚或脚表漏抄），拒绝会让审查员记不下这个发现；
`pinout_complete: false` 的部分脚表照旧允许，计划已把它列成 DEV-D02 缺口。

### 动哪些文件

| 文件 | 改什么 |
|---|---|
| `scripts/board_intent.py` | `package_pin_count(package)`；`device_errors` 加两条 |
| `scripts/tests/test_declared_device_coverage.py`（现有 devices 校验测试） | 缺编号被拒并列出缺的、EP 多脚放行、读不出脚数不查、没有 power/return 被拒、连接器不查 |
| `references/plan-and-results.md` | 示例改对；`devices` 一段加两句 |
| `evals/mutation/mutations.json`、README | 缺脚放行 / 没 power 放行，各一条 |
| `docs/improvement-ledger.md` | 一条 |

### 验证

- 单元测试如上；KiCad 回放的三个用例（`rh-ad8495-thermocouple`：MSOP-8 八脚、SOT-23-3 三脚，都齐）预期不变，跑一遍确认；
- 单元测试夹具里 `package` 写 `QFN-6`、`SO-4`、`TEST-PKG-3` 的几处，脚数不齐的会被新规则拒绝——逐个补齐或改成读不出脚数的名字，
  这本身就是对规则的一次校准，结果记进实施记录。

## 待你决定

1. 第一条只做 A（量差异），B 等 R6 数据——还是现在就定 merge / split 的条件？
2. 第二条的三条护栏是否都做；护栏 1 对带原厂代号的封装名是否照读。

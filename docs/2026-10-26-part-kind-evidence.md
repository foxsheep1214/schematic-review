# 器件类型的依据（2026-10-26 方案，待确认）

> 读者：SR 维护者。本稿只提方案，确认前不改代码。

用户 2026-10-26：“你识别器件的方式是什么样的？通过位号、符号库等方式来识别，都不是可靠的方式，通过品牌商品名来识别更不靠谱。”

A、B 两项改变“什么算定类证据、哪些器件必须有手册声明”，属于 SKILL.md“改架构先问人”里的“改变谁做判断”，确认后同步改
SKILL.md 架构节、`references/architecture.md` 的历次架构决定和台账。C 只加一项核对，不改分工。

## 一、现状

### 识别链

1. **手册声明（唯一能下结论的依据）**：审查员在 `intent.device_kinds.<位号>` 写类型、页码、原文；`audit_datasheets.py`
   读资料解析表按 BOM 确切料号绑给该位号的 PDF，核三点（原文在该页、原文写明该类型、原文不同时指向别的类型），VERIFIED
   才算 basis `datasheet`。身份链是：确切料号 → 那份手册 → 那一页原文。
2. **启发式（没有声明时）**：`part_words.classify` 依次读型号/符号库关键词（`part-keyword`）→ 符号引脚名（`pin-names`）
   → 位号前缀（`refdes-prefix`）。有声明时关键词只作交叉核对，矛盾判未知。

### 三处靠不住

| # | 问题 | 代码位置 | 实测 |
|---|---|---|---|
| 1 | **“哪些器件必须有手册声明”按位号定**：只有位号 Q/D/ZD/TVS/U/M 的器件，DEV-D02 才登记“缺手册器件类型”缺口。光耦编 OK1、变压器编 T/TR、继电器编 K/J、保险编 F、热敏编 TH/RT，都不要求声明 | `plan_board.py` DEV-D02 段（`re.match(r'^(Q\|D\|ZD\|TVS\|U\|M)\d', ref)`） | 59 份网表冷跑：现行集合 531 个位号；集合外被启发式认成需手册定类的器件 51 个，分布在 23 块板（保险 13、继电器 15、NTC 6、变压器 7、压敏 3、二极管/MOSFET/光耦/齐纳/BJT 7）。R7 四份记录（同一块板）：集合外 6 个，其中 5 个（2 只 NTC、保险、压敏、变压器）四份记录都没声明 |
| 2 | **`part-keyword` 在几处被当作与手册同级**：功率开关和监控检查器只对 `pin-names`/`refdes-prefix` 记 `datasheet-kind` 缺口；继电器常闭触点和连接器触点判断接受 `part-keyword` | `part_words.HEURISTIC_BASES`、`checkers/power_switch.py`、`checkers/supervision.py`、`lint.py` `_relay_nc_contact`、`checkers/netgraph.py` 连接器触点 | 59 份网表冷跑里需手册定类的器件 581 个：前缀 337、关键词 231、引脚名 13。R7：38 个里审查员声明了 33 个，没声明的 5 个全靠关键词 |
| 3 | **手册绑定了却没拿来反查启发式**：资料审计知道每个位号的 PDF，首页候选也读了，但不和启发式类型比对 | `datasheet_kinds.audit_kinds` 只给 UNDECLARED 位号列候选 | 被旧词表认成光耦的那颗 eFuse，手册首页标题读出 `load_switch`：比对过就当场露出 |

另：类型由 `graph.kind()` 在约 200 处使用（`plan_circuits` 39、`lint` 17、`circuit_candidates` 15……），绝大多数只用来**决定查哪些项**
（路由），不看依据；真正挡结论的是 DEV-D02 的类型缺口和上面四处。所以本方案不动这 200 处调用，只动“谁必须声明”和那四处。

## 二、方案

### A. 必须声明的器件按类型定，不按位号定

- **现在**：位号 Q/D/ZD/TVS/U/M 才要求手册声明。
- **改成**：任何一路信号（位号前缀、关键词、引脚名，以及 C 的手册首页）认为它属于**需手册定类的类别**，就要求核验过的声明，
  否则 DEV-D02 登记类型缺口。需手册定类的类别：mosfet、bjt、diode、tvs、zener、opto、relay、transformer、fuse、ntc、varistor、
  bridge_rectifier 和全部 IC 角色。启发式只负责把网撒大，不负责收口。现行位号集合保留（并集），`IC\d` 前缀并入。
- **要补的手册线索**：relay、fuse 现在没有线索词，声明了也过不了核验（QUOTE_LACKS_TYPE）。要加 `relay`；fuse 加 `fuse`、
  `resettablefuse`、`pptc`、`polyfuse`，但 `fuse` 去空格后命中 “eFuse”，要排除 `efuse`（另加一条规则或按词读）。
- **动的文件**：`plan_board.py`（DEV-D02 缺口条件）、`device_kinds.py`（类别加 `needs_datasheet` 标志与 relay/fuse 线索，
  `errors()` 自检“需手册定类的类别必须有线索”）、`datasheet_kinds.py`（efuse 排除）、`references/checker-conventions.md`
  （器件类型核验一节）、`references/intent-format.md`（哪些位号要写 device_kinds）、测试、变异、台账、架构决定行。
- **门禁影响（实测与预估）**：
  - 59 份网表冷跑：多出 51 个类型缺口（23 块板）。典型电路基准只判 lint 报出，预计不变；KiCad 回放里带计划的
    rf1/rf2 修订会多出 DEV-D02 缺口，预计要一个回放修订（未实跑，落地时核）。
  - R7 同一块板：多 5 个类型缺口，审查员各写一条声明可关；保险要等线索补上才关得了。
- **风险**：审查员多写声明（R7 每份 +5 条）。不会过严：一条手册原文就能关一个缺口，开放的缺口说明确实没核过类型。

### B. 关键词降为启发式，按后果分档

- **现在**：`HEURISTIC_BASES = ('pin-names', 'refdes-prefix')`，`part-keyword` 在功率开关、监控、继电器常闭、连接器触点四处等同手册。
- **改成**：需手册定类的类别（同 A），`part-keyword` 也是启发式：功率开关、监控检查器记 `datasheet-kind` 缺口，继电器常闭触点只认
  `datasheet`。连接器、测试点、电阻、电容、电感、磁珠、晶振、跳线、开关保持关键词即可路由：它们的检查项要的是额定值、
  触点数等另一类手册数据，不靠“它是什么”下结论；若改成全要声明，59 份网表里 245 个连接器（其中 224 个靠关键词）都会变成缺口，属于过严。
- **动的文件**：`part_words.py`（`kind_gap` 按类别判断）、`lint.py`（继电器常闭）、测试、变异；`netgraph.py` 连接器触点不改。
- **门禁影响**：有 A 时，B 新增的缺口只落在没声明的需定类器件上，与 A 的缺口是同一批器件（R7：同样 5 个，其中进入功率开关/监控
  检查器的 0 个）。冷跑基准里功率开关、监控检查器的报出会因缺口变 CANDIDATE，典型电路基准里涉及的行要逐条重新归类（未实跑，
  落地时核）。
- **不做 A 只做 B 不成立**：DEV-D02 的必声明集合仍按位号，B 只在四处补缺口，集合外的器件照样靠关键词。

### C. 手册首页标题反查启发式类型

- **现在**：资料审计只给没声明的位号列首页候选，作提示。
- **改成**：位号已绑定手册、类别有线索词、首页**标题行**（第 1 页前 6 个非空行）读出的类型里没有启发式类型时，审计记
  `KIND_CONFLICT`（附标题行与两边类型），计划把它写进该位号的 DEV-D02 缺口文字。只是提示和缺口说明，不改类型、不下结论；
  有 VERIFIED 声明的位号以声明为准，不比对。
- **为什么只读标题行**：在 R7 板上实测三种读法（启发式类型都与审查员的核验声明一致，即 0 处真错）——
  - 首两页按现行 `candidates`（特定类别压掉泛称）：45 个位号 6 处误报（MOSFET 手册首页写“load switch”“synchronous rectification”
    应用，保险手册没有自己的线索词）。
  - 首两页不压泛称：1 处误报（保险，没有线索词）。
  - 只读标题行：0 处误报，35 处一致，10 处读不出。被旧词表误认为光耦的 eFuse，标题行读出 `load_switch`，会报冲突。
- **动的文件**：`datasheet_kinds.py`（`title_cues`、`audit_kinds` 对已绑定位号比对）、`audit_datasheets.py`（写进审计）、
  `plan_board.py`（缺口文字带冲突）、`references/checker-conventions.md`、测试、变异、台账。
- **门禁影响**：冷跑基准没有绑定手册，不变；有资料审计的真实记录才会出 KIND_CONFLICT。

## 三、与 ASG 对齐

ASG 的 `part_classes.py` 抄了 SR 的类别名和线索，并有测试断言 ASG 的线索覆盖 SR 的。A 给 relay、fuse 加线索后，ASG 要同步加，
否则它的对齐测试会失败；B、C 只改 SR 内部的判断，ASG 不受影响。

## 四、待你决定

| # | 问题 | 建议 |
|---|---|---|
| 1 | 做哪几项 | A + B + C 一起做；只做一项就先做 C（不改分工，立刻能抓住同类误认） |
| 2 | 需手册定类的类别清单 | 按 A 列的 12 类加 IC 角色；晶振、电感、磁珠、连接器不进 |
| 3 | B 的分档 | 按 B 写的：半导体、光耦、继电器、变压器、保护件要声明；连接器等保持关键词路由 |
| 4 | C 的读法 | 只读标题行，报提示不报失败 |
| 5 | 保险的 efuse 排除 | `fuse` 线索命中前排除 `efuse` 整词 |

## 五、测量方法

数字来自本分支（eb41627）的分类器：59 份网表 = `evals/typical_circuits/fixtures`、`evals/kicad_replay_bench/fixtures`、
`scripts/tests/fixtures` 下全部 .xml/.net，经 `parse_kicad.py` 解析后对每个器件取 `NetGraph.kind/basis`（不带 intent）；
R7 = 四份验收记录的 `record/db.json`（去掉声明）与 `record/evidence/datasheet-audit.json`，手册按审计里的路径读第 1–2 页。
统计脚本在会话草稿区，未入库；落地时把用到的比对做成测试。

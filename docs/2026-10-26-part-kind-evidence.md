# 器件类型的依据（2026-10-26 方案，2026-10-27 逐项确认）

> 读者：SR 维护者。决定记录；2026-10-27 已落地（台账同日条目，KiCad 回放修订 `part-kind-evidence-v1`）。

用户 2026-10-26：“你识别器件的方式是什么样的？通过位号、符号库等方式来识别，都不是可靠的方式，通过品牌商品名来识别更不靠谱。”
2026-10-27 用户把 A、B、C 三项逐项拆开确认（“逐个点来和我讨论，我给你答案”），决定见第三节。

A、B 改变“什么算定类证据、哪些器件必须有手册声明”，属于 SKILL.md“改架构先问人”里的“改变谁做判断”：落地时同步改
SKILL.md 架构节、`references/architecture.md` 的历次架构决定和台账。C 加核对，不改分工。

## 一、现状

### 识别链

1. **手册声明（唯一能下结论的依据）**：审查员在 `intent.device_kinds.<位号>` 写类型、页码、原文；`audit_datasheets.py`
   读资料解析表按 BOM 确切料号绑给该位号的 PDF，核三点（原文在该页、原文写明该类型、原文不同时指向别的类型），VERIFIED
   才算 basis `datasheet`。身份链：确切料号 → 那份手册 → 那一页原文。
2. **启发式（没有声明时）**：`part_words.classify` 依次读型号/符号库关键词（`part-keyword`）→ 符号引脚名（`pin-names`）
   → 位号前缀（`refdes-prefix`），取第一路的结论。

### 靠不住的地方

| # | 问题 | 代码位置 | 实测 |
|---|---|---|---|
| 1 | “哪些器件必须有手册声明”按位号定（Q/D/ZD/TVS/U/M） | `plan_board.py` DEV-D02 段；`audit_datasheets.REQUIRED_REF_RE` | 59 份网表冷跑：现行集合 531 个位号；集合外被认成需定类的 51 个（23 块板）。R7（四份记录同一块板）：集合外 5 个四份都没声明（2 只 NTC、保险、压敏、变压器） |
| 2 | `part-keyword` 在四处等同手册：功率开关、监控检查器只对引脚名/位号记缺口；继电器常闭触点、连接器空触点接受关键词 | `part_words.HEURISTIC_BASES`、`checkers/power_switch.py`、`checkers/supervision.py`、`lint._relay_nc_contact`、`netgraph.qualified_connector_contact` | 冷跑需定类的 581 个器件：前缀 337、关键词 231、引脚名 13 |
| 3 | 手册绑定了却不反查启发式；声明核验只看所引原文，原文可取自任何一页 | `datasheet_kinds.audit_kinds`、`datasheet_kinds.verify` | 被旧词表认成光耦的 eFuse，首页标题读出 `load_switch` |
| 4 | 认不出的器件只出 NEW_DEVICE_KIND 反馈，不要手册、不挡结论 | `validate_review.extension_signals` | 冷跑 273 个：0–1 个网络的机械件 229；接 ≥2 个网络的 44，其中 13 个属于需定类的类别（7 颗 IC、2 个 DC-DC 模块、共模扼流圈、带变压器的 RJ45、2 颗 LED） |
| 5 | 电感不分功能：共模扼流圈、反激变压器只在感性负载声明里作“用途”，耦合电感没有表示 | `device_kinds.KINDS`、`checkers/inductive_load.py` | — |

类型由 `graph.kind()` 在约 200 处使用，绝大多数只决定查哪些项（路由）；挡结论的是 DEV-D02 的类型缺口和第 2 行的四处。

## 二、原则

- **只有核验过的手册声明能定类**；位号、符号库、型号/品牌词只负责把需要定类的器件找出来、给出候选，不负责收口。
- **类型按器件对外的功能定，内部构成不是类型**（用户 2026-10-27 就 eFuse 问“怎么处理更合适”后同意）：eFuse 对外是 VIN/VOUT/EN/ILIM，
  类型是负载开关；内部 N 沟道 MOSFET 的导通电阻、启动能力作为该 IC 的参数，在它带出的电源输入保护电路（DRV-C02、PWR-C13 等）
  里按 IC 手册的保证值判。同理：光耦是 opto，集成上下管的 DC-DC 是稳压器，智能高边开关是负载开关，只有对外露出 G/D/S 的才是 mosfet。
- **分类器认不出的器件首先是 SR 的能力不足**，要在后续补齐（用户 2026-10-27）；补齐之前由审查员归类，不让它悄悄漏过。

## 三、决定

| # | 问题 | 决定 | 用户原话 |
|---|---|---|---|
| A1 | 必须声明的类别 | mosfet、bjt、diode、tvs、zener、bridge_rectifier、opto、relay、transformer、fuse、ntc、varistor 共 12 类加全部 IC 角色，另加多绕组磁件（A1b）；电阻、电容、单绕组电感、磁珠、晶振、连接器、测试点、跳线、开关不进 | “12 类加 IC，但是电感你应该将其功能识别得更细，能分清到底是共模扼流圈，耦合电感还是变压器” |
| A1b | 电感细分 | 注册表新增 `common_mode_choke`、`coupled_inductor`，与 `inductor`、`transformer` 并列，各配线索；两个及以上绕组的磁件一律必须声明（引脚分不出三者）；单绕组两脚电感不进；网络拓扑（两绕组串在同一差分对、两端在开关节点、跨隔离域）只作提示 | “方案1” |
| A2 | 什么把器件拉进必须声明 | 按分类器的**最终类型**（关键词 → 引脚名 → 位号取第一路），不按任一信号的并集（并集会多拉 45 个，几乎全是 K 编号的排针/JST，排针多半没有手册，缺口关不掉） | “1” |
| A3 | 现行位号集合 Q/D/ZD/TVS/U/M | 取消，必须声明只看最终类型；位号前缀仍参与分类（没有更强证据时 U 仍给 ic）。语料影响 1 个（U 编号的 USB-C 座），R7 0 个 | “1” |
| A3b | 加 `IC`/`REG`/`PS` 前缀 | 不加，认不出的器件交给 A5 | “1” |
| A4 | 线索词 | relay：`relay`；fuse：`fuse`（**按整词读**，复数可读，Littelfuse 不命中）、`pptc`；common_mode_choke：`commonmodechoke`、`commonmodefilter`、`commonmodeinductor`、`commonmodecoil`；coupled_inductor：`coupledinductor`。另加两条压制：原文点到 IC 角色时压掉 fuse、relay（“Industrial eFuse”只算负载开关，“relay driver”只算驱动器）；点到 ntc 或 varistor 时压掉 fuse（TDK 手册首页的 ThermoFuse）。ASG 同步加这些线索 | “可以” |
| A5 | 认不出的器件 | 先作为 SR 能力不足列进“对 SR 的反馈”（NEW_DEVICE_KIND 写明“SR 能力不足，待补”，补词表登记进扩表记录）；接了 ≥2 个不同网络的，审查员必须归类：归到必须声明的类别就引手册按 A 核验，归到不需要手册的类别（跳线、net tie、电位器、连接器、开关按键、蜂鸣器等）写一句“它是什么、凭什么”即可关闭；0–1 个网络的机械件不管。语料 44 个，R7 0 个 | “分类器认不出的器件，首先要归类为SR的能力不足，在后续要不足这个能力。然后我建议按照2的方式来” |
| B1 | 检查器里的关键词 | 必须声明类别的器件，功率开关、监控检查器把 `part-keyword` 也当启发式：没有核验声明时这两个检查器的行带 `datasheet-kind` 缺口，不能判 PASS。R7 0 个；冷跑基准里这两个检查器的部分报出由确定变候选 | “同意” |
| B2a | 继电器常闭触点的 “NC” 网络（NET-A04 例外） | 继电器没有核验声明、只靠关键词时，不报“短接”缺陷，也不静默放过，降为候选提示“看起来是继电器常闭触点，类型待手册核验”；声明核验后不再提示 | “1” |
| B2b | 连接器空触点的放过 | 不改：连接器不在必须声明的类别里，现有条件已要求每个身份栏都是完整的连接器系列名 | “1” |
| B3 | 声明与关键词、引脚名矛盾 | 分开：引脚名矛盾（符号画成另一种晶体管）维持判未知并记缺口，提示“符号可能选错”；关键词矛盾以手册为准，出提示“型号栏或库名与手册类型不一致”，并计入 SR 能力不足（关键词表可能要修） | “1” |
| C1 | 反查读手册哪部分 | 先读标题区（第 1 页前 6 个非空行），读不出再读第 1 页全文，不读第 2 页。R7/R6 45 个绑定位号：标题区 0 误报、读出 35；加第 1 页 0 误报、读出 37；再加第 2 页读出 38 但 1 处误报 | “1，读不出的情况下再多读一些” |
| C2 | 启发式与标题矛盾时 | 资料审计记 `KIND_CONFLICT`（附标题原文和两边类型）；需定类且未声明的位号，把它写进 DEV-D02 缺口文字。不改分类、不单独挡结论 | “1” |
| C3 | 已核验的声明是否与标题比对 | 比对；不一致时声明暂不生效，审查员改引标题区原文，或写理由（如系列合订本标题是同系列另一型号、模块手册标题只有产品名）；**以内部构成为由不算理由**。R7 四份记录 134 条核验声明与标题区全部一致 | “同意，按照2加” |
| C4 | 位号前缀与最终类型不一致 | 不提示：语料 120 处（30 块板）、R7 14 处，全是命名习惯（D 泛指二极管家族、Q 泛指晶体管、斯拉夫库 K=连接器、德系 X=连接器/T=晶体管） | “1” |

## 四、落地要动的文件（预估）

- `scripts/device_kinds.py`：类别加 `needs_datasheet` 标志；新增 `common_mode_choke`、`coupled_inductor`；relay、fuse 与两类磁件的线索；
  `errors()` 自检“需定类的类别必须有线索”。
- `scripts/datasheet_kinds.py`：`fuse` 按整词读；两条压制；`title_cues`（标题区 → 第 1 页）；`audit_kinds` 对已绑定位号比对启发式（C2）、
  对已核验声明比对标题（C3，`kind_reason` 及其不得以构成为由的检查）。
- `scripts/plan_board.py`：DEV-D02 类型缺口按最终类型与多绕组磁件，取消位号集合；缺口文字带 KIND_CONFLICT；认不出且接 ≥2 网络的器件要求归类。
- `scripts/audit_datasheets.py`：`REQUIRED_REF_RE` 改为按最终类型取需定类的位号；写 KIND_CONFLICT。
- `scripts/part_words.py`：`kind_gap` 对需定类类别把 `part-keyword` 当启发式（B1）；声明与关键词矛盾以手册为准（B3）。
- `scripts/lint.py`：NET-A04 继电器常闭例外降为候选（B2a）。
- `scripts/board_intent.py`：认不出器件的归类写法（A5）与 `kind_reason`（C3）。
- `scripts/validate_review.py`：NEW_DEVICE_KIND 写成“SR 能力不足”，关键词矛盾计入。
- `scripts/checkers/inductive_load.py`：共模扼流圈、反激变压器读器件类别（声明的用途与类别一致）。
- 参考文档：`references/checker-conventions.md`（器件类型核验：原则、必须声明的类别、标题比对、归类）、`references/intent-format.md`、
  `references/architecture.md`（架构决定行）、SKILL.md 架构节；`references/check-catalog.md`、`review-vocabulary.md` 如有登记变化则重新生成。
- 测试、变异、台账；KiCad 回放带计划的修订（rf1/rf2）预计要一次回放修订；典型电路基准按 B1 逐条重新归类。
- ASG：`part_classes.py` 同步新类别名与线索（它的对齐测试要求覆盖 SR）。

## 五、测量方法

数字来自分支 `claude/sr-part-number-families`（eb41627）的分类器：59 份网表 = `evals/typical_circuits/fixtures`、`evals/kicad_replay_bench/fixtures`、
`scripts/tests/fixtures` 下全部 .xml/.net，经 `parse_kicad.py` 解析后对每个器件取 `NetGraph.kind/basis`（不带 intent）；
R6/R7 = 验收记录的 `record/db.json`（去掉声明）与 `record/evidence/datasheet-audit.json`，手册按审计里的路径读第 1–2 页。
统计脚本在会话草稿区，未入库；落地时把用到的比对做成测试。

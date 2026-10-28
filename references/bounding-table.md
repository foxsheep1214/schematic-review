# 工作点定界表

> 读者：审查员。

器件在板上的工作点和手册给保证的测试条件对不上时（齐纳管工作在测试电流以下、MOS 的 SOA 只给 25 °C 壳温、
NTC 只给 B25/50），按这张表定界：每类器件的每个参数随什么变、往哪个方向单调，允许哪几种推法、按什么顺序，
每种推法用哪个公式，推法用完仍推不出时落到哪一档。表登记在 `scripts/catalog.py` 的 `BOUNDS`，
公式在 `scripts/bound_formulas.py`（也可用 `python3 scripts/calc.py bound_formulas.<公式> '{…}'` 调用），
本文件的表格由 `python3 scripts/catalog.py --write-doc references/bounding-table.md` 生成，不手改。

## 怎么用

- **表里有的器件类别和参数，必须按表的推法和顺序走**（2026-10-23，用户：“必须按表”）。表里没有的，按推法 G1–G10 写，门禁只核写法。
- 审查员只负责两件事：从手册抄出测试点的数值（写页码、表号），用电路算出本板工作点的范围。能不能推出界、推不出记哪一档，由表决定。
- **余量**：每条决定性余量（GUARANTEED_BOUND、REACHABLE_CASE、EXACT_ENVELOPE）必写 `basis.cell`（2026-10-25 用户决定）：表里有格写格并写
  `basis.method`（须是这一格允许的推法），表里没有这个参数写 `NONE`；推法带公式时写 `basis.formula{name, inputs, value}`，门禁用同样的输入重算，
  差超过 0.5% 拒收。写了 `NONE` 而余量的文字对上某格的参数词时，筛查出 `BOUNDING_CELL_AVAILABLE` 提示。
- **判决边界（2026-10-26，用户：“判决的边界按器件类型来”）**：每格另有五列——可得性（厂家通常保证到哪）、允许的估算与倍数（按后果类，空为不估算）、
  失效后果、样机能否验、边界一句话。典型值估算能不能判 PASS 由格 × 后果类决定，不按规则 id：余量写 `cell`、估算推法、`consequence_class`、
  `estimate_factor`（等于格的倍数）、`handoff`，格给了余量下限的还要满足它；DAMAGE_OR_HAZARD、CORE_LINK_LOSS 任何格都不估算；`cell: NONE` 走默认（只许功能/性能后果，
  损坏/过热/保护类规则不估算）并记 NEW_BOUND_CELL 待扩项（`GUARANTEED_LIMIT`、点不出器件、该类器件已有格的不记）。可得性为“行业不给”的格，开放项写向厂家索取出 `UNOBTAINABLE_DATUM` 提示。
  表是可增长的：审查里遇到词表没有的器件类别（NEW_DEVICE_KIND）或有类别没有格的参数（NEW_BOUND_CELL），门禁记进 `sr_improvements`，报告在“对 SR 的反馈”下列出，
  扩表时补齐五列并加测试。决定记录见 docs/2026-10-26-cell-boundary.md。
- **风险标签（2026-10-26，用户：三档结论加四类风险标签，只靠估算过关的角点标风险，风险不限制定稿只单列，关键参数表在定界表上扩）**：
  本表兼作各类器件的关键参数表，先逐颗器件按格比参数再下功能结论。靠估算过关的角点是“合格，但有风险”，余量写 `risk{types, corner, improvement}`，
  `types` 取“估算对应的风险”列（`NONE` 任选环境适应性、寿命、一致性）。哪种余量判风险见[余量判定规则](margin-verdicts.md)，字段见结果格式。
- **判“定不出界”的缺厂家数据**：`worst_case.monotonic_tried.cell` 写格（表里没有这类参数写 `NONE`）。门禁按格核对：
  - 格的开着一侧（UPPER/LOWER）与 `monotonic_tried.side` 相同；
  - 落到 `BOUNDED` 的格总能定界，不开这种项；落到 `OUTSIDE_SPECIFIED` 的格记失败项（`fails[]` 写 `outside_specified`）；
  - 参数单调时，测试点在有利一侧且给了这一侧的限值（随 x 增大的参数：上界看 ≥ 工作点上端的测试点的 max，下界看 ≤ 工作点下端的测试点的 min；随 x 减小的反过来），这个测试点就给出了界（G2），不准开项。

## 几条口径（2026-10-23 用户确认）

- **齐纳管 VZ 下界**：两个测试点之间按较低电流一端的保证 rdif 最大值定界（1-A，“1A，可以”）；低于最低测试点时，典型曲线画到工作点按曲线估算，记缺厂家数据，典型值本身已不够判失败（2-A，“2A，算”）。
- **MOS 高温 SOA**：按持续时间选 25 °C 曲线（连续工作用直流线；单次瞬态用不短于实际时长的单脉冲线；重复瞬态另用 Zth(tp, D) 算结温），按开始壳温降额 P_allowed = P_curve·(Tjmax − Tc_start)/(Tjmax − 25)，恒功率段不超过降额后的 100%，热不稳定段不超过 80%；本板可达工况下超出判失败项。允许壳温和所需壳到环境热阻 Rθca ≤ (Tc_allowed − Ta_max)/P 交热设计和 PCB 设计（“B 热不稳定段按修订写法定：按持续时间选曲线、按开始壳温降额、降额后留 80%。”；“这里也可以给出散热结构设计上的要求，交给下游的PCB设计”）。80% 是工程取值，不是厂家保证，报告照此写明。
- **检测用 NTC**：能取到厂家逐度 R-T 表就按表插值（ln R 对 1/T）；取不到时按 B 值公式加 R25 和 B 的公差定界，算保证最坏值，不开项（“有表用表，没表外推算保证”）。
- **BJT 饱和开关**：按强制 β 设计，IB ≥ IC /（hFE_min / 2）（“强制 β，k = 2”）。
- **浪涌限制 NTC 热态重新接入**：NTC 按 0 Ω 算桥堆和电容的浪涌，过了判通过，不过判失败；需求不要求热态重接时不问这一项（“按 0 Ω 定结论”）。

<!-- bounds:begin（由 scripts/catalog.py --write-doc 生成，勿手改） -->

### 推法

| 编号 | 推法 | 得到的依据 |
|---|---|---|
| G1 | 保证限值直接覆盖：工作点在限值的测试条件内 | 保证最坏值 |
| G2 | 单调有利侧：参数随 x 单调，工作点在测试点的有利一侧 | 保证最坏值 |
| G3 | 两测试点之间的斜率界：取区间内斜率最大一端的保证上限 | 保证最坏值 |
| G4 | 温度系数：P(T) = P(T₀) + S·(T − T₀)，S 取不利一端 | 保证最坏值 |
| G5 | 公开特性表：表内插值，公差取表给的上下限 | 保证最坏值 |
| G6 | 物理约束：节点电压不超过供电轨或钳位保证值，电流不超过上游限流 | 保证最坏值 |
| G7 | 同一测试点比例外推：典型曲线 × 保证值 / 同点典型值 | 估算 |
| G8 | 典型曲线覆盖工作点：按曲线取值；典型值已不够判失败（可达的反例） | 估算 |
| G9 | 只有典型值：同类参数 min/max 比例、同系列保证范围或典型 ±30% | 估算 |
| G10 | 厂家参考电路同接法：接法相同、本板负载不重于参考电路，引图号 | 可判通过 |
| SOA | 按持续时间选 25 °C 曲线，按开始壳温降额，恒功率段留 100%、热不稳定段留 80% | 保证最坏值 |
| FORCED_BETA | 饱和开关按强制 β：IB ≥ IC /（hFE_min / 2） | 保证最坏值 |

### 推不出时

| 写法 | 意思 |
|---|---|
| `VENDOR_DATUM` | 缺厂家数据（第三档），按后果定级 |
| `OUTSIDE_SPECIFIED` | 超出规定区（第四档），记失败项 |
| `BOUNDED` | 总能定界，不开“定不出界”的项 |

### 逐格

| 格 | 器件类别 | 参数 | 开着的一侧 | 随什么变 / 方向 | 推法（公式） | 推不出时 | 出处 |
|---|---|---|---|---|---|---|---|
| `ZENER-VZ-UPPER` | zener | VZ 上界 | UPPER | 工作电流 IZ / INCREASING | G1；G2；G9 | `VENDOR_DATUM` | evidence-proportionality.md“齐纳管低电流” |
| `ZENER-VZ-LOWER` | zener | VZ 下界 | LOWER | 工作电流 IZ / INCREASING | G1；G2；G3（`slope_bound`）；G8 | `OUTSIDE_SPECIFIED` | evidence-proportionality.md“齐纳管低电流”；本表“几条口径”齐纳管 VZ 下界 |
| `ZENER-VZ-TEMP` | zener、shunt_reference | VZ / 基准电压随温度 | — | 温度 / NONMONOTONIC | G1；G4（`tempco_bound`）；G9 | `VENDOR_DATUM` | evidence-proportionality.md第 4 步“温度系数的 min/max” |
| `REF-IKA-MIN` | shunt_reference | 最小阴极电流 Ika | LOWER | 工作态 / — | G1 | `OUTSIDE_SPECIFIED` | 定界表决定（architecture.md 2026-10-23） |
| `TVS-STANDOFF` | tvs | 正常最大值不超过 VRWM | UPPER | 工作电压 / — | G1 | `OUTSIDE_SPECIFIED` | wca-formulas.md TVS 行 |
| `TVS-VC` | tvs | 钳位电压上界 | UPPER | 冲击电流 Ipp（同一波形） / INCREASING | G1；G2 | `VENDOR_DATUM` | wca-formulas.md TVS 行 |
| `TVS-LEAK-HOT` | tvs | 高温漏电 | UPPER | 温度 / INCREASING | G1；G2；G7（`ratio_extrapolation`） | `VENDOR_DATUM` | 定界表决定（architecture.md 2026-10-23） |
| `DIODE-VF` | diode、bridge_rectifier | VF 上界随电流 | UPPER | 正向电流 IF / INCREASING | G1；G2；G8 | `VENDOR_DATUM` | evidence-proportionality.md“单调外推” |
| `DIODE-VF-COLD` | diode、bridge_rectifier | VF 上界随温度（冷态最差） | UPPER | 温度 / DECREASING | G1；G2；G4（`tempco_bound`）；G7（`ratio_extrapolation`） | `VENDOR_DATUM` | evidence-proportionality.md“单调外推” |
| `DIODE-IR-HOT` | diode、bridge_rectifier、zener | 高温反向漏电 | UPPER | 温度 / INCREASING | G1；G2；G7（`ratio_extrapolation`） | `VENDOR_DATUM` | evidence-proportionality.md“二极管反向漏电” |
| `DIODE-SURGE` | diode、bridge_rectifier | 浪涌 IFSM 换算到其他脉宽 | UPPER | 脉宽 / DECREASING | G1；G2；G5（`half_sine_i2t`、`surge_current_at_width`） | `OUTSIDE_SPECIFIED` | evidence-proportionality.md“脉冲与浪涌” |
| `MOS-VGS-ON` | mosfet | 导通所需 VGS | UPPER | 漏极电流 ID / INCREASING | G1；G2；G7 | `VENDOR_DATUM` | wca-formulas.md VGS 三档 |
| `MOS-RDS-HOT` | mosfet | 高温 RDS(on) | UPPER | 结温 / INCREASING | G1；G2；G7（`ratio_extrapolation`） | `VENDOR_DATUM` | evidence-proportionality.md“MOS 热态 RDS” |
| `MOS-SOA-HOT` | mosfet | 高温 SOA | UPPER | 开始壳温 / DECREASING | SOA（`soa_allowed_power`、`soa_case_temperature`、`heatsink_requirement`、`zth_junction_temperature`） | `BOUNDED` | 本表“几条口径”MOS 高温 SOA |
| `MOS-LINEAR` | mosfet | 线性工作点的 VGS（源跟随、线性稳压） | — | 漏极电流与温度 / NONMONOTONIC | G1；G7（`ratio_extrapolation`）；G8 | `VENDOR_DATUM` | evidence-proportionality.md“按实际用途选模型” |
| `BJT-SAT` | bjt | 饱和导通所需基极电流 | LOWER | 集电极电流 IC / — | FORCED_BETA（`forced_beta_base_current`） | `BOUNDED` | 本表“几条口径”BJT 饱和开关 |
| `BJT-HFE` | bjt | 线性区 hFE | LOWER | 集电极电流与温度 / NONMONOTONIC | G1；G7（`ratio_extrapolation`） | `VENDOR_DATUM` | 定界表决定（architecture.md 2026-10-23） |
| `OPTO-CTR` | opto | CTR 随 IF 和温度 | LOWER | 输入电流 IF 与温度 / NONMONOTONIC | G1；G7（`ratio_extrapolation`） | `VENDOR_DATUM` | evidence-proportionality.md“身份冲突与身份分支”（取最低档） |
| `NTC-SENSE` | ntc | 检测用 NTC 的 R(T) | — | 温度 / DECREASING | G5（`ntc_table_bound`、`ntc_beta_bound`） | `BOUNDED` | 本表“几条口径”检测用 NTC；datasheets.md“公开曲线表先于索取” |
| `NTC-INRUSH-HOT` | ntc | 浪涌限制 NTC 热态重新接入 | LOWER | 热态 / — | G6（`inrush_peak_current`、`inrush_i2t`） | `BOUNDED` | 本表“几条口径”浪涌限制 NTC |
| `VAR-UC` | varistor | 最大持续工作电压 Uc | LOWER | 环境温度（额定温度以上降额） / DECREASING | G1；G2 | `VENDOR_DATUM` | docs/2026-10-26-cell-boundary.md 扩表记录 |
| `VAR-VC` | varistor | 钳位（残）电压上界 | UPPER | 浪涌电流（8/20 µs 同一波形） / INCREASING | G1；G2 | `VENDOR_DATUM` | docs/2026-10-26-cell-boundary.md 扩表记录 |
| `VAR-SURGE` | varistor | 最大浪涌电流 / 能量（按次数降额） | LOWER | 脉冲次数与波形 / DECREASING | G1；G2 | `VENDOR_DATUM` | docs/2026-10-26-cell-boundary.md 扩表记录 |
| `RES-POWER` | resistor | 电阻功率、脉冲、TCR 与耐压 | UPPER | 温度与脉宽 / — | G1；G5 | `VENDOR_DATUM` | commodity-floors.md 片式电阻 |
| `MLCC-EFFECTIVE-C` | capacitor | MLCC 有效容量（偏压、温度、老化） | LOWER | 直流偏压与温度 / DECREASING | G1；G2；G5（`table_interpolate`）；G8 | `VENDOR_DATUM` | commodity-floors.md MLCC；wca-formulas.md |
| `ECAP-ESR-RIPPLE` | electrolytic | 电解 ESR 与纹波电流（温度、频率系数表） | — | 温度与频率 / NONMONOTONIC | G1；G5（`table_interpolate`）；G9 | `VENDOR_DATUM` | commodity-floors.md 电解 |
| `IND-ISAT` | inductor、transformer、coupled_inductor、common_mode_choke | 电感 Isat（按资料定义取温度最坏值） | LOWER | 温度 / DECREASING | G1；G2；G5（`table_interpolate`）；G9（`typical_band`） | `VENDOR_DATUM` | commodity-floors.md 电感 |
| `FUSE-I2T` | fuse | 保险丝 I²t 与温度降额 | — | 脉宽与温度 / NONMONOTONIC | G1；G5（`table_interpolate`） | `VENDOR_DATUM` | commodity-floors.md |
| `IC-THRESHOLD` | ic 及各 IC 角色 | 门限、基准 | — | 温度 / NONMONOTONIC | G1；G4（`tempco_bound`）；G7（`ratio_extrapolation`） | `VENDOR_DATUM` | 定界表决定（architecture.md 2026-10-23） |
| `IC-QUIESCENT` | ic 及各 IC 角色 | 静态电流、按模式的功耗 | UPPER | 模式与温度 / — | G1；G9（`typical_band`） | `VENDOR_DATUM` | evidence-proportionality.md“只有典型值的参数” |
| `IC-TIMING` | ic 及各 IC 角色 | 时序参数（最小导通、延时、消隐） | — | 温度 / NONMONOTONIC | G1；G7（`ratio_extrapolation`） | `VENDOR_DATUM` | 定界表决定（architecture.md 2026-10-23） |
| `IC-IO-LEVEL` | ic 及各 IC 角色 | IO 的 VOH/VOL | — | 负载电流与 VDD / INCREASING | G1；G2；G9 | `VENDOR_DATUM` | 定界表决定（architecture.md 2026-10-23） |
| `IC-IO-CURRENT` | ic 及各 IC 角色 | IO 灌/拉电流超出规定 | UPPER | 负载电流 / — | G1；G10 | `OUTSIDE_SPECIFIED` | evidence-proportionality.md“手册的情况按四档判” |
| `IC-PIN-ABSMAX` | ic 及各 IC 角色 | 引脚瞬态电压/注入电流对绝对最大额定 | UPPER | 瞬态源与串联阻抗 / — | G1 | `OUTSIDE_SPECIFIED` | 钳位规则（architecture.md 2026-10-25，B3 a） |
| `IC-RECOMMENDED` | ic 及各 IC 角色 | 推荐工作条件（绝对最大额定只算损坏边界） | — | 工作条件 / — | G1 | `OUTSIDE_SPECIFIED` | DEV-C05 |
| `CAP-SURGE-V` | capacitor、electrolytic | 浪涌/瞬态时电容电压对额定电压 | UPPER | 浪涌电荷与回路阻抗 / INCREASING | G1；G2；G5；G6 | `OUTSIDE_SPECIFIED` | docs/2026-10-26-cell-boundary.md |
| `MOS-DISCHARGE-I2T` | mosfet | 短路放电峰流与 I²t 对脉冲能力 | UPPER | 回路阻抗 / DECREASING | G2；G5；G6 | `OUTSIDE_SPECIFIED` | docs/2026-10-26-cell-boundary.md |
| `IC-GATE-DRIVE-I` | mosfet | 栅极驱动平均电流 Qg·f 对偏置供给 | UPPER | 开关频率与 VGS / INCREASING | G1；G2；G9（`typical_band`） | `VENDOR_DATUM` | docs/2026-10-26-cell-boundary.md |

### 判决边界

可得性：`GUARANTEED` 全保证：工作范围内有 min/max；`TEST_POINT` 测试点保证：只在标称测试条件保证，别处靠单调性或斜率推；`INDUSTRY_NONE` 行业不给：全温、寿命、低电流等只给典型曲线，索取也拿不到；`TYPICAL_BY_DEFINITION` 定义即典型：参数定义本身就是典型值。
样机能否验：`MEASURABLE` 可测（常温或高低温箱）；`TYPE_TEST` 型式试验（浪涌、ESD、破坏性，样机阶段不做）；`NOT_VERIFIABLE` 不可（寿命衰减）。
后果类：`REQUIRED_FUNCTION` 功能、`PERFORMANCE_OR_LIFE` 性能/寿命、`COMPONENT_DAMAGE` 损坏、`DAMAGE_OR_HAZARD` 安全；`CORE_LINK_LOSS`、`DAMAGE_OR_HAZARD` 任何格都不估算。
倍数的意思：把估算值再按不利方向打这个折（电流增益 ÷2、阻值 ×1.2 都写 2 / 1.2）之后结论仍成立；“余量下限”是余量本身至少多少。

“估算对应的风险”见上文“风险标签”。

| 格 | 可得性 | 允许的估算（倍数 · 适用后果 · 余量下限） | 估算对应的风险 | 失效后果 | 样机能否验 | 边界 |
|---|---|---|---|---|---|---|
| `ZENER-VZ-UPPER` | `TEST_POINT` | ×1.5 · 功能/性能/寿命：只有典型 rdif 时：典型 rdif ×1.5 | 一致性 | 功能/损坏 | 可测 | 偏置用途允许估算；作钳位保护（下游过压→损坏）时不估算 |
| `ZENER-VZ-LOWER` | `INDUSTRY_NONE` | ×1.2 · 功能/性能/寿命：典型曲线 G8 在工作电流取值，再 ÷1.2（≈×0.85） | 一致性 | 功能 | 可测 | 典型曲线覆盖工作点时允许估算判 PASS；两测试点之间 G3 是保证值；最低测试点以下又没有覆盖它的曲线，是用在手册未规定的区间，记失败项（改法：把工作电流提到最低测试点以上），不向厂家索取（2026-10-26 定） |
| `ZENER-VZ-TEMP` | `TEST_POINT` | ×2 · 功能/性能/寿命：典型温漂 ×2 | 环境适应性 | 功能/性能/寿命 | 可测 | 并联基准多给 max 温漂（G4 保证）；普通齐纳只给典型温漂，允许估算（×2） |
| `REF-IKA-MIN` | `GUARANTEED` | 不估算 | — | 功能 | 可测 | 不估算：规格地板，低于 Ika(min) 即超出规定区，记失败 |
| `TVS-STANDOFF` | `GUARANTEED` | 不估算 | — | 损坏 | 可测 | 不估算 |
| `TVS-VC` | `TEST_POINT` | 不估算 | — | 损坏 | 型式试验 | 不估算；缺波形对应的保证值时按最坏（Ipp 处 VC max）判 |
| `TVS-LEAK-HOT` | `INDUSTRY_NONE` | ×2 · 功能/性能/寿命：典型温度曲线比例外推 G7，再 ×2 | 环境适应性 | 功能/性能/寿命 | 可测 | 允许估算（×2）：25 °C max 保证，高温只有典型曲线 |
| `DIODE-VF` | `TEST_POINT` | ×1.15 · 功能/性能/寿命：超出测试点需要典型曲线时 ×1.15<br>×1.15 · 损坏 · 余量 ≥ 20 °C：同上；用它判温升损坏时结温余量 ≥ 20 °C | 一致性 | 性能/寿命/损坏 | 可测 | 允许估算（×1.15）；判温升损坏时另要结温余量 ≥ 20 °C |
| `DIODE-VF-COLD` | `INDUSTRY_NONE` | ×1.15 · 功能/性能/寿命：典型温度曲线 ×1.15；物理温漂上界（约 −2 mV/°C）可作 G4 保证推法 | 环境适应性 | 功能 | 可测 | 允许估算（×1.15） |
| `DIODE-IR-HOT` | `TEST_POINT` | ×2 · 功能/性能/寿命：比例外推 G7，再 ×2<br>×2 · 损坏 · 余量 ≥ 20 °C：同上，结温余量 ≥ 20 °C | 环境适应性 | 功能/损坏 | 可测 | 允许估算（×2）；判反向功耗热失控（损坏）另要结温余量 ≥ 20 °C，记应力风险 |
| `DIODE-SURGE` | `TEST_POINT` | 不估算 | — | 损坏/安全 | 型式试验 | 不估算：I²t（√t）换算已是保守推法；手册没给 IFSM 的器件承受浪涌是用在规定区之外，记失败项（2026-10-26 定） |
| `MOS-VGS-ON` | `TEST_POINT` | ×2 · 功能/性能/寿命：小信号 / 电平转换：典型传输曲线的 RDS ×2<br>×2 · 损坏 · 余量 ≥ 20 °C：功率开关：典型曲线 RDS ×2 算导通损耗，结温余量 ≥ 20 °C | 一致性 | 功能/损坏 | 可测 | 允许估算（×2）；功率开关（损坏）另要结温余量 ≥ 20 °C，记应力风险 |
| `MOS-RDS-HOT` | `INDUSTRY_NONE` | ×1.2 · 功能/性能/寿命/损坏 · 余量 ≥ 20 °C：25 °C max × 典型温度比（G7），再 ×1.2；判损坏时结温余量 ≥ 20 °C | 环境适应性 | 性能/寿命/损坏 | 可测 | 允许估算判 PASS（×1.2 且结温余量 ≥ 20 °C）：全行业做法，hot max 行业不给 |
| `MOS-SOA-HOT` | `GUARANTEED` | 不估算 | — | 损坏 | 型式试验 | 按 SOA 推法降额后视作保证；不另估算 |
| `MOS-LINEAR` | `TEST_POINT` | ×1.4 · 功能/性能/寿命：典型传输曲线 gm ÷1.4（≈×0.7）；VGS(th) 的 min/max 是保证值 | 一致性、环境适应性 | 功能 | 可测 | 允许估算（÷1.4）；功耗/结温部分走 MOS-SOA-HOT |
| `BJT-SAT` | `GUARANTEED` | 不估算 | — | 损坏 | 可测 | 按 FORCED_BETA，不估算 |
| `BJT-HFE` | `TEST_POINT` | ×1.5 · 功能/性能/寿命：比例外推 G7，再 ÷1.5 | 一致性、环境适应性 | 功能 | 可测 | 允许估算（÷1.5）；饱和开关走 BJT-SAT |
| `OPTO-CTR` | `INDUSTRY_NONE` | ×2 · 功能/性能/寿命：25 °C 分档下限 × 典型温度曲线最低点（G7），再 ÷2（含寿命衰减） | 环境适应性、寿命、一致性 | 功能 | 可测、不可 | 允许估算判 PASS（÷2）；在保护环里也是阈值偏移，不是器件损坏。“索取全温 CTR”要提示 |
| `NTC-SENSE` | `GUARANTEED` | 不估算 | — | 功能 | 可测 | 按表推法，不估算 |
| `NTC-INRUSH-HOT` | `TYPICAL_BY_DEFINITION` | 不估算 | — | 损坏/安全 | 型式试验 | 不估算；热态阻值按 0 Ω（“按 0 Ω 定结论”） |
| `VAR-UC` | `GUARANTEED` | 不估算 | — | 安全 | 可测 | 不估算：母线最高持续电压（含容差、过压）不超过 Uc 保证值，超额定温度按降额曲线；长期超 Uc 是热失控的安全后果 |
| `VAR-VC` | `TEST_POINT` | 不估算 | — | 损坏 | 型式试验 | 不估算；缺本板浪涌电流对应的保证值时按额定电流处 Vc max 判下游耐受 |
| `VAR-SURGE` | `GUARANTEED` | 不估算 | — | 安全 | 型式试验 | 不估算：需求浪涌等级与次数对降额曲线取保证值；寿命走 DEV-C06 VARISTOR |
| `RES-POWER` | `GUARANTEED` | 不估算 | — | 损坏 | 可测 | 不估算：额定、降额与脉冲曲线按保证；商品地板见 commodity-floors.md |
| `MLCC-EFFECTIVE-C` | `TYPICAL_BY_DEFINITION` | ×1.25 · 功能/性能/寿命：典型偏压曲线 × (1 − 公差) × 老化 0.9，再 ÷1.25（≈×0.8）；补偿网络 ÷1.4 | 一致性、环境适应性、寿命 | 功能/性能/寿命 | 可测 | 允许估算判 PASS（÷1.25） |
| `ECAP-ESR-RIPPLE` | `TEST_POINT` | ×1.3 · 功能/性能/寿命：系数表外的频率：ESR ×1.3<br>×1.3 · 损坏 · 余量 ≥ 10 °C：同上，芯温余量 ≥ 10 °C | 环境适应性、一致性 | 性能/寿命/损坏 | 可测 | 表内按 G5（保证）；表外允许估算（×1.3），判纹波发热（损坏）另要芯温余量 ≥ 10 °C，记应力风险；寿命走 DEV-C02。“资料已读只剩折算”不是厂家数据缺口 |
| `IND-ISAT` | `TYPICAL_BY_DEFINITION` | ×1.3 · 功能/性能/寿命/损坏：典型 Isat 热态值 ÷1.3（峰流 ≤ Isat/1.3） | 环境适应性 | 损坏 | 可测 | 允许估算判 PASS（÷1.3）：损坏类但行业别无他法；不满足 1.3 倍就开放或失败 |
| `FUSE-I2T` | `GUARANTEED` | 不估算 | — | 安全/功能 | 型式试验 | 不估算：保护判 max 曲线，误动作判 min 曲线；缺的若是本板冷/热态 NTC 阻值，是原理图该写没写的值（失败项，改法写算出的阻值） |
| `IC-THRESHOLD` | `GUARANTEED` | ×2 · 功能/性能/寿命：只给 25 °C 加典型温漂时：典型温漂 ×2 | 环境适应性 | 功能/损坏 | 可测 | 功能用途允许（×2）；用门限判保护覆盖（OVP 上限对下游绝限，损坏）时要全温 min/max |
| `IC-QUIESCENT` | `TYPICAL_BY_DEFINITION` | ×1.3 · 功能/性能/寿命：典型 ×1.3（现行 G9）<br>×1.5 · 损坏：用它判偏置电阻功耗损坏时 ×1.5 | 一致性、环境适应性 | 功能/性能/寿命 | 可测 | 允许（功能 ×1.3，损坏用途 ×1.5） |
| `IC-TIMING` | `GUARANTEED` | ×2 · 功能/性能/寿命：只给典型的延时：典型 ×2，取不利方向 | 环境适应性、一致性 | 功能/损坏 | 可测 | 功能时序允许（×2）；用延时判过冲过压损坏时要 max，没有则不估算 |
| `IC-IO-LEVEL` | `TEST_POINT` | ×1.5 · 功能/性能/寿命：超测试电流：输出阻抗典型 ×1.5 | 一致性 | 功能 | 可测 | 允许估算（×1.5） |
| `IC-IO-CURRENT` | `GUARANTEED` | 不估算 | — | 损坏 | 可测 | 不估算：超出手册给的灌/拉电流即超出规定区，记失败项（2026-10-26 定） |
| `IC-PIN-ABSMAX` | `GUARANTEED` | 不估算 | — | 损坏 | 可测 | 不估算：脚上电压超绝对最大额定、手册又没给允许注入电流即超出规定区，记失败项；有串联阻抗时按算出的注入电流对手册允许值判（2026-10-26 定） |
| `IC-RECOMMENDED` | `GUARANTEED` | 不估算 | — | 功能/损坏 | 可测 | 不估算：超出即 OUTSIDE_SPECIFIED |
| `CAP-SURGE-V` | `GUARANTEED` | 不估算 | — | 损坏/安全 | 型式试验 | 不估算：瞬态比瞬态额定——电解按手册浪涌电压额定；MLCC 手册没给浪涌额定时，可靠性试验表的耐电压试验（如额定 ×1.5–2.5、规定秒数）作非重复瞬态的保证额定，瞬态不超过试验电压、持续不长于试验时间即可（2026-10-27，用户：A2 也改）；每个开关周期都出现的重复尖峰仍对额定电压；缺的是浪涌源与回路（设计量或标准条款）；两种额定都没给而超过额定电压即超出规定区，记失败项（2026-10-26 定）；电容爆裂是安全后果 |
| `MOS-DISCHARGE-I2T` | `TEST_POINT` | 不估算 | — | 损坏 | 可测 | 不估算：脉冲能力按手册单脉冲曲线（保证）判，工作点超出曲线范围或 IDM 即超出规定区，记失败项（2026-10-26 定）；回路阻抗按写明的最小值，交给后续环节 |
| `IC-GATE-DRIVE-I` | `TEST_POINT` | ×1.3 · 功能/性能/寿命：Qg 只有典型时 ×1.3 | 一致性 | 性能/寿命 | 可测 | 允许估算（×1.3）：Qg max 多数手册给（G1），只有典型时 ×1.3 |

<!-- bounds:end -->

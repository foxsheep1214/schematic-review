# 工作点定界表

器件在板上的工作点和手册给保证的测试条件对不上时（齐纳管工作在测试电流以下、MOS 的 SOA 只给 25 °C 壳温、
NTC 只给 B25/50），按这张表定界：每类器件的每个参数随什么变、往哪个方向单调，允许哪几种推法、按什么顺序，
每种推法用哪个公式，推法用完仍推不出时落到哪一档。表登记在 `scripts/catalog.py` 的 `BOUNDS`，
公式在 `scripts/bound_formulas.py`（也可用 `python3 scripts/calc.py bound_formulas.<公式> '{…}'` 调用），
本文件的表格由 `python3 scripts/catalog.py --write-doc references/bounding-table.md` 生成，不手改。

## 怎么用

- **表里有的器件类别和参数，必须按表的推法和顺序走**（2026-10-23，用户：“必须按表”）。表里没有的，按推法 G1–G10 写，门禁只核写法。
- 审查员只负责两件事：从手册抄出测试点的数值（写页码、表号），用电路算出本板工作点的范围。能不能推出界、推不出记哪一档，由表决定。
- **余量**：`basis.cell` 写格，`basis.method` 写推法编号（须是这一格允许的推法）；推法带公式时写
  `basis.formula{name, inputs, value}`，门禁用同样的输入重算，差超过 0.5% 拒收。
- **判“定不出界”的缺厂家数据**：`worst_case.monotonic_tried.cell` 写格（表里没有这类参数写 `NONE`）。门禁按格核对：
  - 格的开着一侧（UPPER/LOWER）与 `monotonic_tried.side` 相同；
  - 落到 `BOUNDED` 的格总能定界，不开这种项；落到 `OUTSIDE_SPECIFIED` 的格记失败项（`fails[]` 写 `outside_specified`）；
  - 参数单调时，测试点在有利一侧且给了这一侧的限值（随 x 增大的参数：上界看 ≥ 工作点上端的测试点的 max，下界看 ≤ 工作点下端的测试点的 min；随 x 减小的反过来），这个测试点就给出了界（G2），不准开项。

## 几条口径（2026-10-23 用户确认）

- **齐纳管 VZ 下界**：两个测试点之间按较低电流一端的保证 rdif 最大值定界（1-A，“1A，可以”）；低于最低测试点时，典型曲线画到工作点按曲线估算，记缺厂家数据，典型值本身已不够判失败（2-A，“2A，算”）。
- **MOS 高温 SOA**：按持续时间选 25 °C 曲线（连续工作用直流线；单次瞬态用不短于实际时长的单脉冲线；重复瞬态另用 Zth(tp, D) 算结温），按开始壳温降额 P_allowed = P_curve·(Tjmax − Tc_start)/(Tjmax − 25)，恒功率段不超过降额后的 100%，热不稳定段不超过 80%；本板可达工况下超出判失败项。允许壳温和所需壳到环境热阻 Rθca ≤ (Tc_allowed − Ta_max)/P 交热设计和 PCB 设计（“B 热不稳定段按修订写法定：按持续时间选曲线、按开始壳温降额、降额后留 80%。”；“这里也可以给出散热结构设计上的要求，交给下游的PCB设计”）。80% 是工程取值，不是厂家保证，报告照此写明。
- **检测用 NTC**：能取到厂家逐度 R-T 表就按表插值（ln R 对 1/T）；取不到时按 B 值公式加 R25 和 B 的公差定界，算保证最坏值，不开项（“有表用表，没表外推算保证”）。
- **BJT 饱和开关**：按强制 β 设计，IB ≥ IC /（hFE_min / 2）（“强制 β，k = 2”）。
- **浪涌限制 NTC 热态重新接入**：NTC 按 0 Ω 算桥堆和电容的浪涌，过了判通过，不过判失败；需求不要求热态重接时不问这一行（“按 0 Ω 定结论”）。

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
| `ZENER-VZ-UPPER` | zener | VZ 上界 | UPPER | 工作电流 IZ / INCREASING | G1；G2 | `VENDOR_DATUM` | evidence-proportionality.md“齐纳管低电流” |
| `ZENER-VZ-LOWER` | zener | VZ 下界 | LOWER | 工作电流 IZ / INCREASING | G1；G2；G3（`slope_bound`）；G8 | `VENDOR_DATUM` | evidence-proportionality.md“齐纳管低电流”；本表“几条口径”齐纳管 VZ 下界 |
| `ZENER-VZ-TEMP` | zener、shunt_reference | VZ / 基准电压随温度 | — | 温度 / NONMONOTONIC | G1；G4（`tempco_bound`） | `VENDOR_DATUM` | evidence-proportionality.md第 4 步“温度系数的 min/max” |
| `REF-IKA-MIN` | shunt_reference | 最小阴极电流 Ika | LOWER | 工作态 / — | G1 | `OUTSIDE_SPECIFIED` | 定界表决定（architecture.md 2026-10-23） |
| `TVS-STANDOFF` | tvs | 正常最大值不超过 VRWM | UPPER | 工作电压 / — | G1 | `OUTSIDE_SPECIFIED` | wca-formulas.md TVS 行 |
| `TVS-VC` | tvs | 钳位电压上界 | UPPER | 冲击电流 Ipp（同一波形） / INCREASING | G1；G2 | `VENDOR_DATUM` | wca-formulas.md TVS 行 |
| `TVS-LEAK-HOT` | tvs | 高温漏电 | UPPER | 温度 / INCREASING | G1；G2；G7（`ratio_extrapolation`） | `VENDOR_DATUM` | 定界表决定（architecture.md 2026-10-23） |
| `DIODE-VF` | diode、bridge_rectifier | VF 上界随电流 | UPPER | 正向电流 IF / INCREASING | G1；G2 | `VENDOR_DATUM` | evidence-proportionality.md“单调外推” |
| `DIODE-VF-COLD` | diode、bridge_rectifier | VF 上界随温度（冷态最差） | UPPER | 温度 / DECREASING | G1；G2；G4（`tempco_bound`）；G7（`ratio_extrapolation`） | `VENDOR_DATUM` | evidence-proportionality.md“单调外推” |
| `DIODE-IR-HOT` | diode、bridge_rectifier、zener | 高温反向漏电 | UPPER | 温度 / INCREASING | G1；G2；G7（`ratio_extrapolation`） | `VENDOR_DATUM` | evidence-proportionality.md“二极管反向漏电” |
| `DIODE-SURGE` | diode、bridge_rectifier | 浪涌 IFSM 换算到其他脉宽 | UPPER | 脉宽 / DECREASING | G1；G2；G5（`half_sine_i2t`、`surge_current_at_width`） | `VENDOR_DATUM` | evidence-proportionality.md“脉冲与浪涌” |
| `MOS-VGS-ON` | mosfet | 导通所需 VGS | UPPER | 漏极电流 ID / INCREASING | G1；G2；G7 | `VENDOR_DATUM` | wca-formulas.md VGS 三档 |
| `MOS-RDS-HOT` | mosfet | 高温 RDS(on) | UPPER | 结温 / INCREASING | G1；G2；G7（`ratio_extrapolation`） | `VENDOR_DATUM` | evidence-proportionality.md“MOS 热态 RDS” |
| `MOS-SOA-HOT` | mosfet | 高温 SOA | UPPER | 开始壳温 / DECREASING | SOA（`soa_allowed_power`、`soa_case_temperature`、`heatsink_requirement`、`zth_junction_temperature`） | `BOUNDED` | 本表“几条口径”MOS 高温 SOA |
| `MOS-LINEAR` | mosfet | 线性工作点的 VGS（源跟随、线性稳压） | — | 漏极电流与温度 / NONMONOTONIC | G1；G7（`ratio_extrapolation`）；G8 | `VENDOR_DATUM` | evidence-proportionality.md“按实际用途选模型” |
| `BJT-SAT` | bjt | 饱和导通所需基极电流 | LOWER | 集电极电流 IC / — | FORCED_BETA（`forced_beta_base_current`） | `BOUNDED` | 本表“几条口径”BJT 饱和开关 |
| `BJT-HFE` | bjt | 线性区 hFE | LOWER | 集电极电流与温度 / NONMONOTONIC | G1；G7（`ratio_extrapolation`） | `VENDOR_DATUM` | 定界表决定（architecture.md 2026-10-23） |
| `OPTO-CTR` | opto | CTR 随 IF 和温度 | LOWER | 输入电流 IF 与温度 / NONMONOTONIC | G1；G7（`ratio_extrapolation`） | `VENDOR_DATUM` | evidence-proportionality.md“身份冲突与身份分支”（取最低档） |
| `NTC-SENSE` | ntc | 检测用 NTC 的 R(T) | — | 温度 / DECREASING | G5（`ntc_table_bound`、`ntc_beta_bound`） | `BOUNDED` | 本表“几条口径”检测用 NTC；datasheets.md“公开曲线表先于索取” |
| `NTC-INRUSH-HOT` | ntc | 浪涌限制 NTC 热态重新接入 | LOWER | 热态 / — | G6（`inrush_peak_current`、`inrush_i2t`） | `BOUNDED` | 本表“几条口径”浪涌限制 NTC |
| `RES-POWER` | resistor | 电阻功率、脉冲、TCR 与耐压 | UPPER | 温度与脉宽 / — | G1；G5 | `VENDOR_DATUM` | commodity-floors.md 片式电阻 |
| `MLCC-EFFECTIVE-C` | capacitor | MLCC 有效容量（偏压、温度、老化） | LOWER | 直流偏压与温度 / DECREASING | G1；G2；G5（`table_interpolate`） | `VENDOR_DATUM` | commodity-floors.md MLCC；wca-formulas.md |
| `ECAP-ESR-RIPPLE` | electrolytic | 电解 ESR 与纹波电流（温度、频率系数表） | — | 温度与频率 / NONMONOTONIC | G1；G5（`table_interpolate`） | `VENDOR_DATUM` | commodity-floors.md 电解 |
| `IND-ISAT` | inductor、transformer | 电感 Isat（按资料定义取温度最坏值） | LOWER | 温度 / DECREASING | G1；G2；G5（`table_interpolate`） | `VENDOR_DATUM` | commodity-floors.md 电感 |
| `FUSE-I2T` | fuse | 保险丝 I²t 与温度降额 | — | 脉宽与温度 / NONMONOTONIC | G1；G5（`table_interpolate`） | `VENDOR_DATUM` | commodity-floors.md |
| `IC-THRESHOLD` | ic 及各 IC 角色 | 门限、基准 | — | 温度 / NONMONOTONIC | G1；G4（`tempco_bound`）；G7（`ratio_extrapolation`） | `VENDOR_DATUM` | 定界表决定（architecture.md 2026-10-23） |
| `IC-QUIESCENT` | ic 及各 IC 角色 | 静态电流、按模式的功耗 | UPPER | 模式与温度 / — | G1；G9（`typical_band`） | `VENDOR_DATUM` | evidence-proportionality.md“只有典型值的参数” |
| `IC-TIMING` | ic 及各 IC 角色 | 时序参数（最小导通、延时、消隐） | — | 温度 / NONMONOTONIC | G1；G7（`ratio_extrapolation`） | `VENDOR_DATUM` | 定界表决定（architecture.md 2026-10-23） |
| `IC-IO-LEVEL` | ic 及各 IC 角色 | IO 的 VOH/VOL | — | 负载电流与 VDD / INCREASING | G1；G2 | `VENDOR_DATUM` | 定界表决定（architecture.md 2026-10-23） |
| `IC-IO-CURRENT` | ic 及各 IC 角色 | IO 灌/拉电流超出规定 | UPPER | 负载电流 / — | G1；G10 | `VENDOR_DATUM` | evidence-proportionality.md“手册的情况按四档判” |
| `IC-RECOMMENDED` | ic 及各 IC 角色 | 推荐工作条件（绝对最大额定只算损坏边界） | — | 工作条件 / — | G1 | `OUTSIDE_SPECIFIED` | DEV-C05 |

<!-- bounds:end -->

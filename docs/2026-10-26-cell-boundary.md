# 定界表的判决边界（2026-10-26 决定记录）

用户 2026-10-26："判决的边界应该按照器件类型来。SR 技能里面本身应该抽象出来不同种类的器件，每一种元器件都应该由自身的特性，来判断规则边界。"
现状：定界表（references/bounding-table.md）已按"器件类别 × 参数"分 31 格，每格写了推法与推不出时的归类，但"典型值估算能不能判通过"由规则 id 一刀切
（DEV-C01、DEV-C04、PWR-C03、PWR-C06、PWR-C10、DRV-C01、全部 PRO 只认保证值）。本稿把这条边界搬进格里。

## 列的含义

| 列 | 含义 |
|---|---|
| 可得性 | 厂家手册对这个参数通常保证到哪。**全保证**：工作范围内有 min/max；**测试点保证**：只在标称测试条件保证，别处靠单调性或斜率推；**行业不给**：全温、寿命、低电流等只给典型曲线，索取也拿不到；**定义即典型**：参数定义本身就是典型值（电感 Isat、MLCC 偏压曲线） |
| 允许的估算与倍数 | 推法得到的是估算（G7–G9）时，还能不能判 PASS，条件是什么。倍数的意思：把估算值再按不利方向打这个折（电流增益 ÷2、电压 ×0.85、阻值 ×1.2……）之后结论仍然成立。"不估算"= 只认保证最坏值，推不出就开放或记失败 |
| 失效后果 | 参数超出时物理上发生什么，归四类：**功能**（不启动、阈值偏移、电平错）、**性能/寿命**（损耗、纹波、寿命缩短）、**损坏**（结温、过压、饱和导致器件坏）、**安全**（起火、爆裂、绝缘、触电） |
| 样机能否验 | 估算判 PASS 时移交的样机实测能不能真做：**可测**（常温/高低温箱）、**型式试验**（浪涌、ESD、破坏性，样机阶段不做）、**不可**（寿命衰减） |
| 边界 | 本稿建议：这一格的估算能不能判 PASS，什么条件 |

通用规则（对全部格）：
- 估算判 PASS 的余量写 `basis.kind: ESTIMATE`、`cell`、`consequence_class`、`handoff`（现有写法不变），证据记 C 级；记录里有这种 PASS 时 `release` 最高 CONDITIONAL_GO，报告单列"按典型值估算、待样机确认"。
- 后果写了 `hazard_path`（起火、爆裂、绝缘失效、触电）的判断，不论格怎么写都不估算。
- 可得性为"行业不给"的格，开放项写 VENDOR_DATUM 且 `acquisition` 是向厂家索取时出提示：索取不到，要么走本格允许的估算，要么换种类。
- 格没写边界时的默认：功能/性能后果允许估算（现行 2.1 口子），损坏/安全不估算（现行规则清单）。

## 逐格

| 格 | 器件 / 参数 | 可得性 | 允许的估算与倍数 | 失效后果 | 样机能否验 | 边界 | R7 |
|---|---|---|---|---|---|---|---|
| `ZENER-VZ-UPPER` | 齐纳 VZ 上界 | 测试点保证；高于 IZT 按保证 rdif 最大值推（G2 得保证值） | 只有典型 rdif 时：典型 rdif ×1.5 | 偏置电压偏高→功能；作钳位保护时下游过压→损坏 | 可测 | 偏置用途允许估算；钳位保护用途不估算 | |
| `ZENER-VZ-LOWER` | 齐纳 VZ 下界（低电流） | 两测试点之间 G3 斜率界是保证值；最低测试点以下**行业不给** | 典型曲线 G8 在工作电流取值 ×0.85 | 偏置不足→启动失败/维持不住，功能；作锁定阈值基准→阈值偏移，功能 | 可测（低温箱） | 允许估算判 PASS（×0.85）。开放项写"向厂家索取低电流保证值"要提示 | codex1 BIAS-LOW-CURRENT（挡 36 项）、FAULT-ZENER-LOW；codex2 BIAS-ZENER |
| `ZENER-VZ-TEMP` | 齐纳 / 并联基准 VZ 温漂 | 并联基准多给 max 温漂；普通齐纳只给典型温漂 | 典型温漂 ×2 | 阈值随温度漂移→功能/性能 | 高低温可测 | 允许估算（×2） | |
| `REF-IKA-MIN` | 并联基准最小阴极电流 | 全保证（规格下限） | 不适用：低于 Ika(min) 即超出规定区，记失败 | 基准失效→功能 | 可测 | 不估算（这是规格地板，不是分布） | |
| `TVS-STANDOFF` | TVS 工作电压 ≤ VRWM | 全保证 | 不适用 | 正常工作时 TVS 导通发热→损坏 | 可测 | 不估算 | |
| `TVS-VC` | TVS 钳位电压上界 | 标称 Ipp 波形下保证 max；低于 Ipp 按单调 G2 仍是保证值；别的波形只有典型 V-I 曲线 | 不估算 | 下游 IC 脚超绝限→损坏 | 型式试验（ESD/浪涌） | 不估算；缺的是波形对应的保证值时按最坏（Ipp 处 VC max）判 | codex1 J701-ESD-COORD（挡 5 项，PRO-A02） |
| `TVS-LEAK-HOT` | TVS 高温漏电 | 25 °C max 保证；高温只有典型曲线（**行业多数不给** hot max） | 典型温度曲线比例外推 G7 ×2 | 高阻节点电压偏移、待机功耗→功能/性能 | 高温可测 | 允许估算（×2） | |
| `DIODE-VF` | 二极管 VF 随电流 | 测试点保证；其他电流按单调 G2 得保证值 | 超出测试点需要典型曲线时 ×1.15 | 损耗/电平偏差→性能；温升边际时→损坏 | 可测 | 允许估算（×1.15）；用它判温升损坏时结温余量 ≥ 20 °C 才 PASS | |
| `DIODE-VF-COLD` | 二极管冷态 VF | 多数只给典型温度曲线；物理温漂上界（约 −2 mV/°C）可作保证推法 G4 | 典型曲线 ×1.15 | 冷态启动电压不足→功能 | 低温可测 | 允许估算（×1.15） | |
| `DIODE-IR-HOT` | 二极管 / 齐纳高温反向漏电 | 25 °C max 保证，部分给 100/125 °C max；否则典型曲线 | 比例外推 G7 ×2 | 高阻节点漏电→功能；高压整流反向功耗热失控→损坏 | 高温可测 | 功能用途允许（×2）；判高压整流反向功耗损坏时要 hot max，没有则不估算 | |
| `DIODE-SURGE` | 二极管 / 整流桥浪涌 IFSM 换算脉宽 | IFSM 在 8.3/10 ms 半正弦保证；其他脉宽按 I²t（√t）换算 G5，行业视作保证推法 | 不估算（换算本身已是保守推法） | 结损坏、整流桥开路→损坏/安全 | 型式试验 | 不估算；无 IFSM 的器件开放 | |
| `MOS-VGS-ON` | MOSFET 导通所需 VGS | RDS(on) 在各 VGS 测试点保证；低于最低测试点只有典型传输曲线 | 小信号 / 电平转换：典型曲线 RDS ×2；功率开关：不估算 | 导通不足→损耗温升→损坏（功率）；电平不到→功能（小信号） | 可测 | 功率开关要测试点覆盖工作 VGS；小信号开关允许估算（×2） | |
| `MOS-RDS-HOT` | MOSFET 热态 RDS(on) | 25 °C max 保证；温度曲线只有归一化典型（**行业不给** hot max） | 25 °C max × 典型温度比（G7），再 ×1.2 | 温升→损坏 | 可测（温升） | 允许估算判 PASS（×1.2 且结温余量 ≥ 20 °C）。这是全行业做法，现行"损坏类不估算"在这格过严 | |
| `MOS-SOA-HOT` | MOSFET 高温 SOA | SOA 曲线按 SOA 推法降额后视作保证（BOUNDED） | 不另估算 | 二次击穿→损坏 | 型式/专项 | 按 SOA 推法；不估算 | |
| `MOS-LINEAR` | MOSFET 线性工作点 VGS（源跟随、线性稳压） | VGS(th) min/max 保证；gm 与传输曲线典型 | 典型传输曲线 gm ×0.7 | 输出电压偏差→功能；线性稳压功耗走 SOA 格 | 可测 | 允许估算（×0.7）；功耗/结温部分走 `MOS-SOA-HOT` | |
| `BJT-SAT` | BJT 饱和驱动 | 强制 β 推法（BOUNDED） | 不适用 | 不饱和→损耗→损坏 | 可测 | 按 FORCED_BETA，不估算 | |
| `BJT-HFE` | BJT 线性区 hFE | 测试电流处 min 保证；其他电流/温度典型曲线 | 比例外推 G7 ×1.5（hFE ÷1.5） | 驱动不足→功能 | 可测 | 允许估算（÷1.5）；用于饱和开关时走 `BJT-SAT` | |
| `OPTO-CTR` | 光耦 CTR 随 IF 和温度 | 25 °C 分档 min 保证；温度、IF 曲线归一化典型；寿命衰减只有应用笔记（**行业不给**全温/寿命保证） | 分档下限 × 典型温度曲线最低点，再 ÷2（含寿命衰减） | 增益不足→反馈环增益低、锁定阈值偏移→功能 | 高低温可测；寿命不可 | 允许估算判 PASS（÷2）。不因它在保护环里改为不估算：后果是阈值偏移，不是器件损坏。开放项写"索取全温 CTR"要提示 | codex1 FAULT-LATCH-DRIVE；codex2 U202/U404/FAULT-CTR；claude1 OPTO-CTR ×3（已算 2–4 倍余量仍开放） |
| `NTC-SENSE` | 检测用 NTC R(T) | 表与公差保证（BOUNDED） | 不适用 | 温度读数偏差→功能 | 可测 | 按表推法 | |
| `NTC-INRUSH-HOT` | 浪涌限制 NTC 热态重接 | 热态阻值厂家给 "R at Imax" 典型；上游限流 G6 可定界 | 热态阻值不估算：按厂家 R@Imax 或取零 | 热态重接浪涌→保险/整流桥损坏→损坏/安全 | 型式试验 | 不估算；按最坏（热态阻值取厂家 R@Imax 的 50 % 或零）判 | claude1 INRUSH-I2T（热态 NTC 阻值进 I²t） |
| `RES-POWER` | 电阻功率、脉冲、TCR、耐压 | 额定与降额曲线保证；脉冲负载曲线厂家给作许用值（视作保证） | 不估算 | 过热开路、阻值漂移→损坏（高压分压开路→保护失效） | 可测（温升） | 不估算；商品地板见 commodity-floors.md | |
| `MLCC-EFFECTIVE-C` | MLCC 有效容量（偏压、温度、老化） | 公差保证；偏压曲线**定义即典型**；老化按材料经验 | 典型偏压曲线 × (1 − 公差) × 老化 ×0.9，再 ×0.8 | 容量不足→纹波、补偿、去耦→功能/性能 | 可测 | 允许估算判 PASS（×0.8）；补偿网络用 ×0.7 | |
| `ECAP-ESR-RIPPLE` | 电解 ESR 与纹波电流系数 | ESR max（120 Hz、20 °C）保证；频率/温度系数表厂家公布（视作保证 G5）；表外频率只有经验 | 表外频率 ESR ×1.3 | 寿命缩短→性能/寿命；长期过热鼓包→损坏 | 可测（温升） | 表内按 G5；表外允许估算（×1.3）；寿命走 DEV-C02 自己的路径。"资料已读只剩折算"不是厂家数据缺口 | |
| `IND-ISAT` | 电感 / 变压器 Isat | **定义即典型**（按 10–30 % 感量跌落定义），温度依赖典型 | 典型 Isat 热态 ÷1.3（峰流 ≤ Isat/1.3） | 饱和→峰流失控→开关损坏 | 可测（峰流、温升） | 允许估算判 PASS（÷1.3）。损坏类但行业别无他法；不满足 1.3 倍就开放或失败 | |
| `FUSE-I2T` | 保险丝 I²t 与温度降额 | min/max 熔断曲线与降额表保证 | 不估算 | 不熔断→安全；误熔断→功能 | 型式试验 | 不估算：保护判 max 曲线，误动作判 min 曲线。缺的若是本板的冷态/热态 NTC 阻值，种类是 DESIGN_VALUE 不是 VENDOR_DATUM | claude1 INRUSH-I2T |
| `IC-THRESHOLD` | IC 门限、基准 | 多数全温 min/max 保证；部分只给 25 °C 加典型温漂 | 典型温漂 ×2 | 门限偏移→功能；OVP/OCP 门限偏移改变保护覆盖→下游损坏 | 高低温可测 | 功能用途允许（×2）；用门限判保护覆盖（OVP 上限对下游绝限）时要全温 min/max，否则按偏移 ×2 后仍覆盖才 PASS | |
| `IC-QUIESCENT` | IC 静态电流、按模式功耗 | 典型为主，部分给 max | 典型 ×1.3（现行 G9） | 待机功耗、偏置电源负载→功能/性能 | 可测 | 允许（×1.3，现行）；用它判偏置电阻功耗损坏时 ×1.5 | codex1 STANDBY（部分） |
| `IC-TIMING` | IC 时序（最小导通、延时、消隐） | 多数 min/max 保证；部分延时只给典型 | 典型 ×2（延时取 ×2 不利方向） | 功能时序→功能；保护响应延时→过冲过压→损坏 | 可测 | 功能时序允许（×2）；用延时判过冲损坏时要 max，没有则 ×2 且峰值余量 ≥ 20 % 才 PASS | claude1 F-FBOPEN（OVP 延时，字形误码案） |
| `IC-IO-LEVEL` | IC IO 的 VOH/VOL | 测试电流处保证；更小电流按单调 G2 得保证值 | 超测试电流：输出阻抗典型 ×1.5 | 电平不到→功能 | 可测 | 允许估算（×1.5） | |
| `IC-IO-CURRENT` | IC IO 灌/拉电流 | 绝限保证；推荐值保证；G10 参考电路可判 | 不估算 | 超绝限→损坏 | 可测 | 不估算 | |
| `IC-RECOMMENDED` | IC 推荐工作条件 | 全保证 | 不适用：超出即 OUTSIDE_SPECIFIED | 超出推荐区→不保证功能；超绝限→损坏 | 可测 | 不估算 | |

## 汇总

| 边界 | 格 |
|---|---|
| 允许估算判 PASS（带倍数） | ZENER-VZ-LOWER、ZENER-VZ-TEMP、TVS-LEAK-HOT、DIODE-VF、DIODE-VF-COLD、MOS-RDS-HOT、MOS-LINEAR、BJT-HFE、OPTO-CTR、MLCC-EFFECTIVE-C、ECAP-ESR-RIPPLE（表外）、IND-ISAT、IC-QUIESCENT、IC-IO-LEVEL（14 格） |
| 按用途分：功能用途允许、损坏/保护用途要保证值或加条件 | ZENER-VZ-UPPER、DIODE-IR-HOT、MOS-VGS-ON、IC-THRESHOLD、IC-TIMING（5 格） |
| 不估算 | REF-IKA-MIN、TVS-STANDOFF、TVS-VC、DIODE-SURGE、NTC-INRUSH-HOT、RES-POWER、FUSE-I2T、IC-IO-CURRENT、IC-RECOMMENDED（9 格） |
| 已有保证推法（BOUNDED），不涉及 | MOS-SOA-HOT、BJT-SAT、NTC-SENSE（3 格） |

对 R7 的影响：光耦 CTR 四条（三份记录）和齐纳低电流三条（两份记录）可按本表判 PASS 并移交样机，共收回被挡检查项约 36 + 7 + 7 + 1 + 1 + 1 + 1 + 3 项；
保险 I²t、TVS 钳位、浪涌抬升保持开放或改种类；变压器图纸、固件能力、配置表（交付物缺口，挡项最多）不受本表影响。

## 器件类别是可增长的（用户 2026-10-26）

> 这个器件类别也是可以增长的。在 SR 审查的过程中，如果发现了新的器件类别，就应该在"SR 待改进的点"中增加这个，告诉用户发现了新的器件种类，需要扩增这个列表。

现状：器件类别词表在 `part_words.py`（resistor、capacitor、inductor、ferrite、diode、tvs、zener、mosfet、bjt、relay、opto、crystal、transformer、fuse、jumper、testpoint、switch、ic、connector、battery、bridge_rectifier，认不出的记 unknown），
IC 再按手册声明的角色分（`catalog.DEVICE_ROLES`）；定界表的 31 格只覆盖其中一部分类别的一部分参数。审查里遇到表外的东西现在有两条出口，都不够：
2.1 的"类别未知的三脚件要决定"只管网表扫描认不出的件（决定后类别还是 unknown，不会进任何格）；
余量写 `cell: NONE` 只说明"没有格"，不区分"这类器件有格但这个参数没有"和"这类器件根本没有格"。

建议的机制（三处信号，一个出口）：

| 信号 | 哪一步 | 条件 | 写进哪里 |
|---|---|---|---|
| 新器件类别 | ① 读入 / 2.1 | 位号被认成 `unknown`，或手册身份核出的类别不在词表里（继电器以外的机电件、压敏电阻、气体放电管、PTC、霍尔、光电、MEMS、模块……） | 门禁 `sr_improvements` 一条 `kind: NEW_DEVICE_KIND`：位号、认出的线索（符号名、手册标题）、建议的类别名 |
| 有类别没有格 | ③ 功能判定 / 4.1 | 决定性余量写了 `cell: NONE`，而对象的类别在词表里、参数词（`catalog.CELL_WORDS` 之外）能从 `against`/`aspect` 读出 | `sr_improvements` 一条 `kind: NEW_BOUND_CELL`：类别、参数、本板怎么判的（保证值 / 估算 / 开放）、建议的可得性与边界 |
| 有格、边界不对 | ④ 处置疑点 / ⑤ 反馈 | 审查员按格判了，但认为这一格的可得性或倍数与手册实际不符 | 现有 `notes.json` 的 `sr_feedback`，`kind: over_strict` 或新加 `cell_boundary`，必须点名格号和本板实例 |

三条都渲染进报告"对 SR 的反馈（设计者不用处理）"一节，单列小节"器件类别与定界表要扩的"，告诉用户：发现了新的器件种类或参数，需要扩这张表；不改本板结论。
扩表本身是 SR 的改动：新格要补齐本稿的五列（可得性、允许的估算与倍数、失效后果、样机能否验、边界），进 `catalog.BOUNDS`、bounding-table.md 和本表，并加一条测试。
门禁对这两种 `sr_improvements` 不阻断，但 4.1 的做完标志加一句："写了 `cell: NONE` 的余量，每条都确认过是表里没有，并且表里没有的已记为待扩项"。

与现行的关系：`BOUNDING_CELL_AVAILABLE`（写了 NONE 但文字对上某格的参数词）仍管"有格没用"；新加的两条管"没格"。
2.1 的未知类别决定照旧，决定的同时产生 NEW_DEVICE_KIND，这样决定不再是终点。

## 决定（用户 2026-10-26，逐点判定，均取建议项）

| 点 | 决定 |
|---|---|
| 0 扩表信号 | 三条信号汇到报告"对 SR 的反馈"小节；新类别的位号**只报不拦**，本板结论照常判 |
| 1 按用途分的 5 格 | **接受同一格两种边界**：格回答典型值可信到什么程度，用途由余量的 `consequence_class` 带进来，门禁按 格 × 后果类 查 |
| 2 Isat / 热态 RDS | **允许**典型值加倍数判 PASS（Isat ÷1.3；RDS 25 °C max × 典型温度比 ×1.2 且结温余量 ≥ 20 °C） |
| 3 倍数 | **逐格保留**，每格写出处，可逐格修 |
| 4 等级与准出 | 估算判 PASS 记 **C 级**，有它时 `release` 最高 **CONDITIONAL_GO**，报告**单列**"按典型值估算、待样机确认"；现行功能类估算 PASS（B 级）也改成这一套，两类估算一个写法 |
| 5 表外的量 | **补格**：这次先给 R7 碰到的三个量补格（CAP-SURGE-V、MOS-DISCHARGE-I2T、IC-GATE-DRIVE-I），以后由 NEW_BOUND_CELL 信号逐块板补；表外的量按现行规则级默认 |

## 实施计划（2026-10-26，用户放行："按这六步动手，步 1–3 完成后先提交一次"）

落点：现行"估算判 PASS"由两处决定——`function_reading.ESTIMATE_PASS_CLASSES`（只许 REQUIRED_FUNCTION / PERFORMANCE_OR_LIFE）和
`NO_ESTIMATE_PASS_RE`（DEV-C01、DEV-C04、PWR-C03、PWR-C06、PWR-C10、DRV-C01、PRO-* 一律不许）；`review_functions._basis_errors` 同样按这两处拒收。
定界表是 `catalog.Bound(id, kinds, parameter, side, varies_with, direction, methods, fallback, source)` 31 格，`render_bounds_markdown` 生成 bounding-table.md 的标记区间，
`test_bounding_table.py` 对照。准出 `release` 只有 `accepted`（已批准接受的 FAIL/INSUFFICIENT）一条路到 CONDITIONAL_GO；`expand` 给 PASS 一律 B 级。
报告"对 SR 的反馈"现在渲染 `sr_improvements`（工具判断不了的检查项）、`rule_gaps`、`sr_feedback`、自检提示四块。

| 步 | 做什么 | 验证 |
|---|---|---|
| 1 定界表加边界 | `Bound` 加五个字段：`availability`（GUARANTEED / TEST_POINT / INDUSTRY_NONE / TYPICAL_BY_DEFINITION）、`estimate`（None 不估算，或 {factor, applies: 后果类集合, note}，按用途分的格给两条）、`consequence`（功能/性能寿命/损坏/安全）、`prototype`（可测/型式试验/不可）、`boundary` 一句话；31 格按本表填；新增 CAP-SURGE-V（capacitor/electrolytic，瞬态电压对额定，G5/G6，不估算，安全）、MOS-DISCHARGE-I2T（mosfet，短路放电峰流与 I²t 对脉冲能力，G5，不估算，损坏）、IC-GATE-DRIVE-I（ic 驱动器角色，Qg×f 驱动电流对偏置供给，G9 ×1.3，性能）；`render_bounds_markdown` 加列，`--write-doc` 重写 bounding-table.md | `test_bounding_table.py`：每格五列齐、倍数为正、按用途分的格两条 applies 不重叠、文档区间与代码一致 |
| 2 门禁按格 × 后果类放行 | `estimate_passes` / `prototype_estimate` 改读 `basis.cell` 的格：格的 `estimate.applies` 含 `basis.consequence_class` 才算通过；`cell: NONE` 时退回现行规则清单（默认）；`_basis_errors`：ESTIMATE 带 `consequence_class` 时必须写 `estimate_factor`，等于格给该后果类的倍数，`hazard_path` 非空的功能拒绝；带 `formula` 的格复算时把倍数带入；`consequence_class` 词表与开放项 `severity.class` 统一（加 DEVICE_DAMAGE、SAFETY） | `test_review_functions.py`：OPTO-CTR 估算 ÷2 判通过、FUSE-I2T 估算被拒、MOS-VGS-ON 功能用途过/损坏用途拒、NONE 走旧清单、倍数不符被拒、hazard_path 拒；`test_bound_derivation.py` 复算含倍数 |
| 3 C 级 + CONDITIONAL_GO + 单列 | `derive_rows` 由估算判 PASS 的派生检查项写 `evidence_confidence: C`；`expand` 对手填 PASS 按所引余量同样定 C；`validate_review` 统计 `estimated_passes`（功能、格、倍数、移交、检查项），有则 `release` 最高 CONDITIONAL_GO，门禁输出新字段；`render_report` 首页数字一览加一行，新小节"按典型值估算、待样机确认"（每条：功能 / 参数与格 / 估算方法与倍数 / 样机实测项 / 挡的检查项）；`pack_review` 白话检查覆盖该节 | `test_derive_rows` / `test_results_model`：等级 C；`test_validate_review`：有估算 PASS 时 CONDITIONAL_GO、无则不变；golden 报告 `SR_UPDATE_GOLDEN=1` 重写后审读 diff |
| 4 三条扩表信号 | `validate_review` 生成两种新 `sr_improvements`：NEW_DEVICE_KIND（db 里 kind 为 unknown 的位号，或 2.1 决定写的类别不在 `part_words` 词表里；带位号、线索、建议类别）、NEW_BOUND_CELL（决定性余量 `cell: NONE` 且对象类别在词表里；带类别、`against`/`aspect`、本板怎么判的）；`sr_feedback` 加 `kind: cell_boundary`（必须点名格号）；`render_report` 在"对 SR 的反馈"下新小节"器件类别与定界表要扩的"；两种信号不阻断；现有 `BOUNDING_CELL_AVAILABLE` 不变 | `test_validate_review`：unknown 位号出信号、NONE+已知类别出信号、NONE+unknown 类别只出前者；`test_render_and_pack`：小节渲染、`cell_boundary` 缺格号被拒 |
| 5 文档 | bounding-table.md 散文（边界列的读法、倍数的意思）；plan-and-results.md"估算判通过"段改为按格、`estimate_factor` 字段、开放项"行业不给"提示；verdicts-and-release.md 准出语义（估算 PASS → CONDITIONAL_GO）与报告新节；evidence-proportionality.md"只有典型值的参数"指向格；SKILL 3.1（估算判 PASS 写格与倍数）、4.1（NONE 每条确认并记扩表）、4.2（行业不给的提示）、5.1（新节）；architecture.md 一行；本稿改名为 docs/2026-10-26-cell-boundary.md 作决定记录；台账一条 | `check_ledger.py`；`test_architecture.py`；文档与词表一致的测试 |
| 6 门与量化 | 全量单元、合同、KiCad 回放（fixtures 里有 ESTIMATE PASS 的要补 `estimate_factor`，可能出一个约定版本）、典型电路；变异 M640+（格查表、倍数核对、hazard_path、C 级、CONDITIONAL_GO、两种信号）从快照跑；R7 四份记录重跑门禁只量不改：光耦 CTR 四条、齐纳三条按新格能否关闭（记录缺 `estimate_factor`，量成"可关闭候选"），其余开放项不受影响；记进本稿 | 全部变异单元层杀死；R7 量化写进本稿与台账 |

提交：步 1–3 一次（表、门禁、准出、报告是一个语义），步 4–5 一次（信号与文档），步 6 的量化随第二次。两次都只含本会话的 hunks。
不动的：开放项的六种 kind、`OPEN_ITEM_RULES`、派生规则、规则目录；`cell: NONE` 的判断仍按现行清单，直到对应的格补上。

## 待你定的点（已全部判定，留作记录）

0. 上面的三条信号和出口是否就是你要的"SR 待改进的点"的形式；NEW_DEVICE_KIND 要不要同时拦住该位号的器件检查项判 PASS（我倾向不拦，只报）。

1. 五个"按用途分"的格：是否接受"同一格两种边界"，还是按你的原则一格只一种（那就要在功能用途和损坏用途之间选一边）。
2. `IND-ISAT` 和 `MOS-RDS-HOT` 属损坏后果却建议允许估算，理由是行业没有保证值、设计实践就是典型值加倍数；是否接受。
3. 倍数取值：本稿按工程惯例给了每格一个数，没有统计依据；是统一成两档（功能 1.3、损坏 2）还是保留逐格。
4. 估算判 PASS 的记录等级与准出：C 级 + CONDITIONAL_GO + 报告单列，还是沿用现行 B 级不影响 release。
5. 定界表现有 31 格之外的量（BULK 电容浪涌电压、Q701 短路放电、Qg 驱动电流）没有格，现在写 `cell: NONE`；是否要为它们补格，还是留在规则级默认。

# Top 50 漏报核对

逐条对照 Top50 正反例、原生 netlist/Val/DNP 与最终计划；确认证据不足时不制造漏报。

确认漏报 0 条；needs_human 不是通过，也不是漏报证明。

| 序号/准则 | 规则 | 状态 | 网表/资料证据与边界 |
|---|---|---|---|
| 01 G01-018 | PWR-C02 | not_applicable | 本板是 PoE/USB-C/正极性 DC Jack 载板，无受控 −48V 电信输入；PoE 的48V不是 −48V ETSI 电源，不套用该反例。 |
| 02 G01-019 | PWR-C02 | not_applicable | 本板是 PoE/USB-C/正极性 DC Jack 载板，无受控 −48V 电信输入；PoE 的48V不是 −48V ETSI 电源，不套用该反例。 |
| 03 G01-020 | PWR-C02 | not_applicable | 本板是 PoE/USB-C/正极性 DC Jack 载板，无受控 −48V 电信输入；PoE 的48V不是 −48V ETSI 电源，不套用该反例。 |
| 04 G01-021 | PWR-C02 | not_applicable | 本板是 PoE/USB-C/正极性 DC Jack 载板，无受控 −48V 电信输入；PoE 的48V不是 −48V ETSI 电源，不套用该反例。 |
| 05 G01-022 | PWR-C02 | not_applicable | 本板是 PoE/USB-C/正极性 DC Jack 载板，无受控 −48V 电信输入；PoE 的48V不是 −48V ETSI 电源，不套用该反例。 |
| 06 G01-023 | PWR-C02 | not_applicable | 本板是 PoE/USB-C/正极性 DC Jack 载板，无受控 −48V 电信输入；PoE 的48V不是 −48V ETSI 电源，不套用该反例。 |
| 07 G01-024 | PWR-C02 | not_applicable | 本载板无直接交流市电输入，J11 外部直流电源；不把 AC 适配器内部性能归给本板。 |
| 08 G01-025 | PWR-C02 | not_applicable | 本载板无直接交流市电输入，J11 外部直流电源；不把 AC 适配器内部性能归给本板。 |
| 09 G01-026 | PWR-C02 | needs_human | J10/Q16/U59/U60，USB-C VBUS 经开关到输入总线；J9 是调试 USB-C，VCC_USB/VREGIN 经 D6/D7 路径。未取得准确 PD 端点协议/线缆压降与负载窗，不以 5V 网络名证明 vSafe5V。 |
| 10 G01-027 | PWR-C01 | needs_human | J10 未见离散 PD 控制 IC，供电/协商功能与 U40 FT4232HP 相关；缺 HP 准确手册及 OTP/配置，不能把连接器数量或电源额定当作已协商可用电流。 |
| 11 G01-029 | PWR-C11 | needs_human | J10 入口 C231=100n/50V；Q16 前后须按附着/限流/隔离状态分别计算可见体电容。不能把全板大电容相加，也不能只看 C231 宣布小于100µF。 |
| 12 G01-030 | PWR-T05 | needs_human | U40 F_SOURCE.32 NC，VBUS 检测/反供逻辑须按 FT4232HP 配置判；缺准确手册与状态设定，未确认40ms及3.67V判据适用性和实现。 |
| 13 G01-031 | PRO-D04 | needs_human | U17 USB7016 → U16/U18 TPS2066TDGNRQ1 → U24/U29 USB-A，USB2_VBUS/USB4_VBUS 是受控供电端；缺控制默认态/准确开关数据和附件模式。 |
| 14 G03-003 | PWR-C15 | needs_human | U49-U55 AP62301；C211-C218/C223-C226=22u 标称，L3=2u2，L4-L9=1u；U38/U61 NCP730。已读 AP62301 p17-18 电感/输出电容选择与 NCP730 稳定性说明，仍缺偏压后有效容值/工作负载边界；不把标称44µF当保证有效44µF。 |
| 15 G03-004 | PWR-C15 | needs_human | 同上准确 MLCC 料号，电路无外置大 ESR 串阻；未获各输出电容温度/偏压/频率下 ESR 保证。检查项已在 PWR-C15，未证明违反窗口。 |
| 16 G03-016 | DRV-C02 | needs_human | Q6/Q16 串供电，U56-U58 理想二极管；缺源阻抗、启动负载和准确 MOS/SOA。零压差或稳态导通 Rds(on) 不能代替启动 SOA。 |
| 17 G03-018 | PWR-C04 | needs_human | U49-U55 AP62301 的 VIN 来自 DC_MAIN_BUS，直流插座 p4 标注6–15V；U58 LTC4358 的 VDD 为输出经 R148 100R。ADI p3 Operating Supply Range=9–26.5V，需确认低压标注是否承诺理想二极管功能及无其他输入时的母线窗口；这是待确认工况，PWR-C04/DEV-C05 已覆盖问题，不计已证漏报。 |
| 18 G03-019 | PWR-C04 | needs_human | DC_MAIN_BUS 共享多个 Buck 和载板，源负载/线缆/USB-PD 限流模式未给；无 Iload_max×Rsource 与 UVLO 滞回的保证比较。 |
| 19 G03-021 | PWR-C04 | needs_human | U49-U55 的 BST100n、输出22u组已连；多电源同时上电的总电容电流和 K26 动态负载不明，不能按单路3A额定总和判断。 |
| 20 G03-025 | RST-E01 | needs_human | U31/U32=TPS3840PH30DBVR，监控 PS_3V3/PL_3V3，复位驱动 Q8/Q9/U36；未取得所有 SoM/接口负载最低工作电压与掉电斜率，门限选项30不能独自证明掉电先复位。 |
| 21 G03-028 | RST-T03 | needs_human | VCCOEN_PS_M2C 控 U49/U51/U52，PS_CLK_EN 经 R127 0R 控 U50/U53，VCCOEN_PL_M2C 控 U54/U55；K26 管理/默认配置未给。 |
| 22 G03-032 | PWR-T05 | needs_human | SOM_5V0 经 Q6；USB 路径 D6/D7，三路 ORing U56-U58。故障/断电需连同体二极管与准确芯片反向规格核算，未按“有MOS”判通过。 |
| 23 G03-037 | PWR-T03 | not_applicable | 遍查装配电容的原生 MPN/符号：均为非极性 MLCC，C172-C179=22u/100V，C180/C181=47u/16V 也是陶瓷；没有已识别电解/钽/串联电解。电容耐压通用应力仍须别项核。 |
| 24 G03-038 | PWR-T03 | not_applicable | 遍查装配电容的原生 MPN/符号：均为非极性 MLCC，C172-C179=22u/100V，C180/C181=47u/16V 也是陶瓷；没有已识别电解/钽/串联电解。电容耐压通用应力仍须别项核。 |
| 25 G03-040 | PWR-T03 | not_applicable | 遍查装配电容的原生 MPN/符号：均为非极性 MLCC，C172-C179=22u/100V，C180/C181=47u/16V 也是陶瓷；没有已识别电解/钽/串联电解。电容耐压通用应力仍须别项核。 |
| 26 G04-005 | SIG-E02 | needs_human | U1/U33/U42/U43 74AVC4T245、U34/U44/U45 AVC2T245，两侧电源及 DIR/OE 必须按工作/掉电状态核；当前缺准确资料与模块 IO 标准。 |
| 27 G04-007 | SIG-T03 | needs_human | 上述转换器与 U12 PCA9306；不把 powered 标称兼容推广为 unpowered IOFF 资格，外卡/SoM 上电次序未定。 |
| 28 G04-009 | SIG-C15 | needs_human | U12 低侧 SoM、摄像头/PMOD PL_3V3 侧及 USB/DP 外接端；缺注入电流限值和回灌源边界，电平翻译与串阻不自动构成断电隔离。 |
| 29 G04-010 | RST-T04 | needs_human | Q8/Q9 由 TPS3840 推挽输出驱动可排除无驱动告警；Q19 HDA20、MIO31_SHUTDOWN 则依赖模块默认态。未把所有NC输入都判错误：U36.13 已以准确 CMOS 手册确认缺陷，但它不是关键输出状态的同一判据。 |
| 30 G04-017 | SIG-C01 | needs_human | U12 PCA9306；R34/R35=2k2、1%→PS_3V3，高侧两线；低侧 MIO24_I2C_SCK/MIO25_I2C_SDA 无载板拉阻。未获总 Cb、总线速率及内部上拉保证，无法给 tr 上界。两线均已在 SIG-C01 实例中，SCK 未单列 SIG-A03 不是整条规则漏报。 |
| 31 G04-018 | SIG-C01 | needs_human | 同一通道的两侧不可直接跨有源件并联；高侧 Rmin=2178Ω，名义3.3V、假定VOL0.4V时单侧1.33mA只是演示，未把该假定当接收端保证。缺实际 IOL/VOL 与低侧上拉规格。 |
| 32 G04-032 | SIG-C03 | not_applicable | catalog/README 与网表无 CAN 收发器及 CAN 端口，不借用差分 PCIe/以太网作 CAN 端接比较。 |
| 33 G04-040 | SIG-D11 | needs_human | PoE 初级 VDD_POE_IN/VSS_POE_IN/GNDD、PS1 隔离输出回 GND；以太网 J5 带磁性结构。未见原理图直接把 GNDD 与 GND 合并；缺模块隔离等级，不能把逻辑分网等同耐压/PCB安规验证。 |
| 34 G04-041 | ANA-C01 | not_applicable | 未发现载板分立运放信号链；TPS3840 是监控器，不能因被识别为 ANALOG 就套运放共模要求。 |
| 35 G04-054 | ANA-C01 | not_applicable | 载板未发现独立 ADC 模拟输入链，SoM 内部未纳入本次原理图，不能冒称已审核模块 ADC。 |
| 36 G04-078 | CLK-C01 | needs_human | Y7=ABM8G-12.000MHZ-18-D2Y-T，C154=C156=18pF 对 GND；串联等效为9pF+Cs，18pF后缀含义仍须准确订货表确认。无 Abracon 完整手册及 FT4232HP 振荡器边界，未确认电容选值错误；已有 CLK-C01.CLOCK 总项。 |
| 37 G04-079 | CLK-C01 | needs_human | Y7 驱动 U40 XIN/XOUT，晶体 ESR/gm/驱动功率保证缺失；有源 Y1-Y6 不套用 Pierce 晶体起振公式。 |
| 38 G04-082 | CLK-C01 | reviewed_no_confirmed_miss | db Y7.1 仅连 U40 XIN 与 C154，Y7.3 仅连 U40 XOUT 与 C156，未把同一无源晶体接给第二振荡器；Y1-Y6 为供电式时钟模块，另由 U7/U8 分配。 |
| 39 G05-019 | PRO-C01 | needs_human | PoE TPS2378 入口热插拔、USB 输出 U16/U18；DC Jack J11 只有 D27/去耦及 U58 ORing，未声明统一支路故障分类和额定，不能把 ORing 当限流器，也不因未见熔丝一律判缺陷。 |
| 40 G05-022 | PRO-C01 | needs_human | U16/U18 TPS2066 开关至 USB 连接器、Q6 SoM 供电；缺最大动作电流、连接器准确并针额定及铜路热边界。 |
| 41 G05-025 | PRO-C01 | needs_human | PoE IC1 热插拔与 PS1、USB 开关至端口；未获故障电流-时间上界和被保护对象耐受，不能用典型限流速度当保证。 |
| 42 G05-030 | PRO-E02 | needs_human | D2=PTVS5V0Z1USKPYL→PL_3V3；D10=SMAJ58A→PoE桥端，D26/D27=SMF4L15CA→USB-C/DC端。缺准确 VRWM 与持续最高电压窗；名称5V/58V不是钳位电压。 |
| 43 G05-031 | PRO-E02 | needs_human | D2 同网 U10.3/U32.2/U35.5，必须把 VC(Ipp) 与最低脚耐受比较；已有 D2 专项候选，未以TVS存在判通过。 |
| 44 G05-032 | PRO-E02 | needs_human | 外部端口波形/源阻抗/环境温度未给，缺 D2/D10/D26/D27 准确脉冲曲线；额定峰功率不能不分波形相加。 |
| 45 G05-040 | DRV-C02 | needs_human | Q6/Q16 通路及入口 ORing、Buck 支路均需故障路径区别；缺热插入阻抗和负载储能边界，不把运行导通功率算式当短路启动SOA。 |
| 46 G05-041 | DRV-C02 | needs_human | Q6/Q16 热态硬短路；无起始壳温和关断时间保证，缺数据不得写成已确认过热。 |
| 47 G05-048 | PRO-C01 | needs_human | 未发现装配熔断器 F*；电子开关保护不能替代熔断器分断能力。若系统另加上游保险，需要其具体规格，当前无该器件实例可作本条数值比较。 |
| 48 G05-054 | PWR-T05 | needs_human | J11 DC 输入经 U58，D21/D22 为抬地反接保护；LTC4358 p8 Figure3 可排除“地不接GND必错”，但还要核实际反接幅值及 D27 极性/电流。USB/PoE 接口按自身误接场景分别核。 |
| 49 G05-057 | PWR-T05 | reviewed_no_confirmed_miss | J11 前端 D27=SMF4L15CA 双向 TVS，非单向 TVS 反向当二极管短路的典型反例；PoE D10 位于桥后，极性由 D8/D9 整流。未发现该特定缺陷。 |
| 50 G05-087 | PWR-T05 | needs_human | U58 内置 MOS + D21/D22 逻辑按 LTC4358 Figure3；普通MOS Q6/Q16 不因自身存在就认为反接保护。需端口反接规范才可关闭全部场景。 |

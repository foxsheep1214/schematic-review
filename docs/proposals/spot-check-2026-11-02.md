# SR 86 板归因独立抽查（2026-11-02）

## 抽样方法与统计

- 数据源：`~/.cache/sr-boards/_summary/findings-all.json`（true_defects 201 条，false_alarm_patterns 1964 条）。逐板 findings.json 大部分已清理，只用汇总记录加各板 `db.json` / `netlist.xml` / `src` / `review/` 手册核对。
- 抽样：`random.Random(20261102)` 打乱下标，然后分三轮选：第一轮要求板和 sr_rule 都没出现过，第二轮只要求板没出现过，第三轮补足。每类抽 20 条，类内板和 sr_rule 字符串都不重复；两类合计 40 条覆盖 36 块板（4 块板两类各抽到一条）。清单见 `spotcheck-sample.json`，生成脚本是 `sample.py`。
- 核对方法：用 db.json 列出相关位号的逐脚网络和网络成员，必要时 grep netlist.xml / 原理图 PDF；手册条款用 review/datasheets（或 ds/）下的 PDF/TXT 原文核对，BQ76952 用的是 HardwareWiki 原件。

| 类别 | 同意 | 不同意 | 证据不足 |
|---|---|---|---|
| 真缺陷（20） | 19（其中 4 条附保留意见） | 0 | 1 |
| 误报（20） | 20（其中 1 条附保留意见） | 0 | 0 |

## 表一：真缺陷抽查

| # | 板 | 规则 | 位号/网 | Codex 结论（一句） | 我的结论 | 依据 |
|---|---|---|---|---|---|---|
| 1 | hasanberkdasar--bms-can-bus | SIG-T04 | U1(BQ76952) VC16/VC15，Net-(J3-Pin_1) | VC16 与 VC4–VC15、BAT 并在一起，顶节电芯没接到 VC16–VC15 | 同意 | db：U1.1–12、47、48 都在 Net-(J3-Pin_1)，VC1–VC3 接电芯阶梯。TI SLUSE13B p75 表 16-3 原文要求 cell 1、2、16 必须接实际电芯（VC16–VC15） |
| 2 | gorkemguven--12v-1a-isolated-flyback-smps | DEV-D04 | C12、R26、IC7 | Value、MPN 和封装三者冲突 | 同意 | C12 的 value 是 “1nF 100nF 25V smd1206”，MPN VJ1206Y104（100nF/1206），封装却是 C_0805。R26 的 value 是 “2.63k 2k”，MPN 是 CRCW12062K00（2k），直接决定 TL431 分压后的输出电压 |
| 3 | copperpilot--jetson-ai-cam-copperpilot | SIG-C05 | IC3(NCP380LSNAJA) ~EN，/USB/USBC_ID，IC7.27 | DFP 附着信号没接到负载开关 EN，VBUS 一直关着 | 同意 | IC7.27(ID) 为 unconnected；USBC_ID 只接 R47 上拉 5V、R49(0R) 到 IC3.3、R102 上拉，T7/R137/R68 都是 DNP。ncp380.pdf 订货表里 LSNAJA 的 EN 低有效，所以 EN 恒为高，开关恒关 |
| 4 | anthilla--anthc | SIG-D07 | U5.8 VBUS 检测，R47/R63，D3 | 检测分压取自 D3 之后的 +5V，boost 工作时拔掉 USB 仍为高 | 同意 | R47.1 接 +5V，D3 的阳极在连接器 VBUS、阴极在 +5V，U12 boost 经 D7 也供 +5V。电池供电时 U5.8 约 3.4V，检测失效 |
| 5 | solderedelectronics--io-expander-mcp23017 | DEV-D01/D04 | U2 “NMOS-DUAL”，U3 “SE5218” | 输出档位和完整型号没定 | 同意（保留） | db 中 U2/U3 没有任何字段；SE5218 有 A–G 多个输出档。缺陷成立，但属于订货码没写清，网名 3V3 已暗示 A 档，工程后果低 |
| 6 | rmingon--rs485-spy-injector | NET-A01 | J4.B5 CC2（A5 CC1 同样） | Type-C 的 CC 悬空、没有 Rd | 同意 | J4.A5/B5 都是单节点 unconnected，VBUS 接 +5V。按 Type-C 规范，没有 Rd 时合规电源不会输出 VBUS |
| 7 | tonydefilippis--poepico | PRO-E02 | D1 SMAJ24A，VDD | 24V TVS 跨在 PoE 48V 整流输出上 | 同意 | db：D1 跨 VDD/VSS，VDD 是 U4(LT4321).OUTP；D1 的 Comment 写明 24V/26.7V/38.9V。正常 37–57V 工作时 D1 会导通、过载 |
| 8 | badgineer--mp2-esc | DOC-Q01 | R43/R44/R55/R56 | 同一提交的 v0.6 PDF 标 6R8，原生图/BOM 为 4R7 | 同意（保留） | review/source-schematic.pdf 中这几个位号对应 6R8，db 中全是 4R7（MPN 0603WAF470K）。成立，但属于文档一致性问题 |
| 9 | fossasia--pslab-hardware | DOC-D01 | C5、C23 | 显示 10nF，订货码 104 是 100nF | 同意 | value=10nF，PartNumber=C0603C104J4RACTU（100nF）；Description 写 10%，订货码 J 是 5%，又一处不一致 |
| 10 | satya777777--esp32-industrial-io-controller | DEV-C05 | J2 VBUS、R6 22.1k、U2.7 VREGIN、D2 | USB VBUS 经 22.1k 才到 VBUS 网，同时供 VREGIN 和 SYS_5V | 同意 | VBUS 网 = D2.A + R6.2 + R9.2 + U2.7 + U2.8，连接器 VBUS 只经 R6 进来。USB 供电路径实际上被 22.1k 截断，VREGIN 接在检测分压上 |
| 11 | pionixpublic--reference-hardware | CLK-C01 | Y3 | Value=16MHz，订货码和描述都是 24MHz | 同意（保留） | Field6=ABM8-24.000MHZ…，Part Description 写 24MHz。频率契约冲突成立，本质也是值与订货码不一致 |
| 12 | antmicro--hdmi-mipi-bridge | DEV-D05 | U1/U4 A5(DAOUT)、A6(PFIL)，C2/C25 | 不用 APLL 时 100n 应接 PFIL，现在接到了 DAOUT | 同意 | db：C2/C25 接 A5=DAOUT，A6=PFIL 悬空。TC358743XBG.txt p10 规定 DAOUT “leave open”、PFIL “Connect to AVSS through 0.1µF”，引脚图 A5=DAOUT、A6=PFIL 与符号一致 |
| 13 | mlab-modules--solarmini01 | DEV-D01 | D2 | SMBJ5.0A 配 SMA 封装 | 同意 | value=SMBJ5.0A，footprint=D_SMA；SMBJ 系列是 DO-214AA(SMB)，焊盘不配套 |
| 14 | weirdgyn--driverino-shield | DEV-C01 | U1 MCT8316Z VM、C2、C3、+36V | 标注 36V 超出 35V 推荐值和电容额定 | 同意（保留） | +36V 网接 U1.9–11、C2(EEE-FKV121XSV 35V)、C3(GMK316 35V)。全仓库只有网名给出 36V，ReadMe 没写电压，结论完全建立在网名契约上 |
| 15 | blkburn--zigbee | DEV-D02 | U1 MX25R8035FM1IH1 pin7 | 符号标 RESET#，IH1 型号实际为 HOLD# | 同意，但应降级 | 手册 p84 订货表：M1IH1 是 HOLD#。pin7 悬空，p8 Note1 说明有内部上拉，没有电气后果。属于符号标注错，按 P2 偏重，应为 P3/文档 |
| 16 | newell--nixie-clock-esp32c3 | NET-A07 | U4–U11 pin10 ~SRCLR | 8 片 74HC595 的清零输入悬空 | 同意 | db 中 U4–U11.10 都是 no_connect 单节点，CMOS 输入悬空，可能随机清零 |
| 17 | antmicro--m2-smart-iot-module | PWR-T04 | U7 TLV803EF29 监控 1V8_CORAL | 2.93V 门限监控 1.8V 轨，复位一直有效 | 同意 | U7.3 V_IN=/CoralAccelerator/1V8_CORAL，U5=AP2120N-1.8。TLV803E 手册的门限档含 2.93V（29 档），正常 1.8V 永远低于门限 |
| 18 | prajyotdaphal--home_automation-module | PRO-C05 | F2，/AC | 保险丝两端接同一网，等于被短路 | 同意 | db：F2.1 和 F2.2 都在 /AC（与 J9.2、K6–K8.1、RV2 同网），保险丝不起作用；220V 交流侧，P0 合理 |
| 19 | gyrocopterllc--flatmcu | PWR-C04 | U2 AP1117-33 输出，C11/C19/C38/C39，FB1 后的 C41 | 本地输出电容 1.3µF，低于手册要求的 4.7µF | 证据不足 | 手册 2015 版 p6 确有 “minimum 4.7µF(0.15–0.5Ω)” 条款，名义上不满足。但 C41=4.7µF 只隔一颗 BLM18AG601 磁珠，磁珠在 LDO 环路频段（kHz–100kHz）阻抗很低，相当于额外的串联 ESR，有效 Cout 约 6µF，不一定失稳。Codex 不接受 C41 的理由同样缺少频域证据，应改判为需要样机或仿真确认的风险，而不是确证缺陷 |
| 20 | antmicro--sdi-mipi-bridge-hw | RST-T03 | U4 CrossLink VCCAUX(D5)=+3V3，VCC(E4/E6)=+1V2 来自 U1 | VCCAUX 先于 VCC 上电 | 同意 | U4.txt §4.5 第 3 条要求 “VCCAUX must be powered up at the same time or after VCC… at no point… higher than VCC”。+1V2 由 U1(MAX8902B) 从 +3V3 产生，必然后起 |

## 表二：误报抽查

| # | 板 | 规则 | 位号/网 | Codex 结论（一句） | 我的结论 | 依据 |
|---|---|---|---|---|---|---|
| 1 | leonardoward--dpp-architecture-pcb | DRV-E01/A03 | Q1 栅极，R2，J2/J3 | 把经 R2 到 GND 的连接器地脚当成栅驱动 | 同意 | Net-(Q1-G)=Q1.G+R1+R2；R1 接 U1(DGD0215).OUT*，真正的驱动是 U1；R2 100k 是下拉，J2/J3 只是 GND 网上的触点 |
| 2 | imike78--home-mini-v1-drop-in-pcb | NET-A07 | U2(MPR121).8 ELEC0，TP6 | 触摸电极端被当作悬空数字输入 | 同意 | 网 = U2.8 + TP6.1；TP6 是 “TOUCH_L” 2.5mm 焊盘，BOM 标 DNP 只是因为它是铜皮不用贴装 |
| 3 | s59mz--kicad-pmod_rs485 | REQ-Q07 | U1 ADM2582E | 符号库路径 Interface_UART 导致重复生成 UART 覆盖项 | 同意 | 全板只有 U1 一颗接口 IC（隔离 RS485），没有第二套 UART 电路 |
| 4 | antmicro--kria-k26-devboard | NET-A01 | J_SOM240_2.B45 /HDB13 | DNP 连接器的单节点标签被报悬空 | 同意 | J_SOM240_2 nc=True，它的 161 个网除 GND 外都是单节点，整组连接器在本设计中不装 |
| 5 | antmicro--m2-smart-iot-module | PWR-A02 | U4(nRF52840) E24 DEC6 / DEC4_6 | DEC4/DEC6 合网被当作无源电源脚 | 同意 | 网 = DEC4 + DEC6 + L3 + C42/C43/C55，正是 Nordic 参考设计里 DC/DC 输出合网的标准接法 |
| 6 | antmicro--stm32h7-hdmi-board | PWR-A01 | +5V，J9.1 | 说 +5V 只从连接器进板，实际有板内源 | 同意 | R12(0R) 连接 /Power/5V_OUT 与 +5V，板内有 5V 源，SR 的“板上无来源”不成立 |
| 7 | theushen--eegfrontier | DEV-C01 | R2/R3 “1kΩ” | 解析器读不出带 Ω 的值 | 同意 | value 原文为 “1kΩ”，含义明确 |
| 8 | newell--hv-flyback-converter | RST-T04 | TR1，J1 HVEN | 把变压器当成隔离屏障，派了 IO 默认态问题 | 同意 | 全板没有 MCU/逻辑 IO（U1 是 LT3957 控制器），HVEN 来自 J1 端子和 SW1，RST-T04 的对象不存在 |
| 9 | hirusha785--12v-5a-isolated-flyback-smps-kicad | PWR-C26 | D1 KBL408，F1 “IN AC -” | 桥式交流入口套用了 DC 防反接模板 | 同意 | 入口是 F1 加 KBL408 整流桥的交流输入，不存在正接/反接方向 |
| 10 | prajyotdaphal--home_automation-module | SIG-C07 | K6–K8 线圈/触点 | 对继电器触点要求数字 VOH/VIL 裕量 | 同意 | K6.1=/AC（触点）、K6.5 线圈由 Q6(BC547) 驱动，触点没有逻辑电平窗口可核 |
| 11 | antmicro--scalenode-cm4-baseboard | PWR-D02 | U3 TPS2373、U4 URB4805 | 给 DNP 器件展开了去耦组 | 同意 | U3/U4 都有 nc=True 和 DNP 字段，PoE 选装在默认装配中不装 |
| 12 | solderedelectronics--io-expander-mcp23017 | DEV-Q01/REQ-Q08 | FD1 | 光学定位点被列为“认不出的器件” | 同意 | FD1=FIDUCIAL，没有电气脚 |
| 13 | newell--nixie-clock-esp32c3 | REQ-Q08 | Q35 BSS138，C10 等 | 电平转换管被认成电源变换器，旁路电容被认成 RC 吸收 | 同意 | Q35 的 S=RGB、D 经 R52/R53 上拉，是典型 BSS138 电平转换；C10 是 +5V 对 GND 的 10µF 旁路 |
| 14 | greatscottgadgets--urti-mainboard | PWR-C10 | U15 LMV358 pin4 V− | 单电源运放的 V− 被当作需要去耦的电源脚 | 同意 | U15.4(V−)=GND、U15.8(V+)=3V3RX，单电源接法，V− 就是回流脚 |
| 15 | rmingon--chlinknet | SIG-T04 | Y1 晶振 / U28 CH32V307 | 门禁报文“没有条款支撑结论”，不是电路缺陷 | 同意（保留） | 报文本身是审查流程的证据门禁，确实不是电路问题。但 Y1 的 value 只有 “Crystal_GND24”，没有频率和 CL（C1/C2=10pf），起振和负载电容无法核实，应作为 DEV-D01/CLK-C01 资料缺失单独报出，不能因为放宽 F1 门禁就判通过 |
| 16 | scottbez1--faderbuddy | PWR-C04 | U2 DRV8837 | 电机驱动被当作稳压器，派了环路/补偿检查 | 同意 | U2 是 DRV8837 H 桥，OUT1/OUT2 接 MOTOR_A/B，没有反馈环 |
| 17 | tinkerforge--evse-v2-bricklet | DRV-A01 | L101 “FB” | 串联磁珠被要求续流管 | 同意 | L101 value=FB，0603，串在 5V 和 U110(TPS70933).IN 之间做滤波，不是开关感性负载 |
| 18 | cellkeeper-bms--cellkeeper-hardware | NET-A06 | H7 MountingHole_Pad | 单节点机械孔被报悬空 | 同意 | H1–H4、H7、H8 都是悬空的 MountingHole_Pad，属于机械件（H5/H6 有意接了网）。是否接机壳地属于设计选择，不是缺陷 |
| 19 | neotron-compute--neotron-pico | PWR-C09 | U201 Pico 3V3/ADC_VREF，HPGND | 模块输出脚和返回脚被生成去耦任务 | 同意 | U201.36 3V3、35 ADC_VREF 是 Pico 模块的输出且未引出，载板不需要给它们去耦 |
| 20 | antmicro--jetson-agx-thor-baseboard | DRV-A03 | Q24 栅极，U63 LTC4412 GATE | 说栅极无驱动，实际由理想二极管控制器驱动 | 同意 | Net-(Q24-G)=Q24.G+U63.5(GATE)，U63.5 的原生脚型就是 output，检查器连 output 都没认出来 |

## 对归因质量的判断

总体：40 条里没有一条需要改成相反结论。真缺陷的器件、网络和手册条款基本都对得上，引用的页码和条款在本地手册里能找到原文；误报的归因（指向检查器哪一处）也和网表事实一致。主要的系统性偏差有以下几点：

1. 真缺陷中“订货码/值/文档不一致”类占比高、严重度偏重。20 条里有 7 条（#2、5、8、9、11、13、15）本质是 Value、MPN、封装、PDF、符号脚名之间互相矛盾或没写清，不是电路接法错。事实都成立，但这些多按 P1/P2 计入真缺陷，会抬高“电气缺陷”的统计。#15 的引脚悬空且手册有内部上拉，没有电气后果，按 P2 明显偏重。#5 的情况，按“只有关键/特殊器件要料号、常规件按值加规格”的对齐口径，应区分“型号不唯一影响功能”（LDO 输出档）和“通用 NMOS 没写型号”。建议在汇总里给这类单独设一个子类（如 DOC/BOM-consistency），并按有无电气后果分级。

2. 真缺陷中有一部分过度依赖名义条款或网名，没有放到实际电路里看。#19 机械套用“本地 Cout ≥ 4.7µF”，忽略了只隔一颗磁珠的 4.7µF；#14 唯一依据是网名 “+36V”。这类按“条款偏离/契约不相容”处理可以，但不应和 #7、#16、#18 这种确定失效的缺陷放在同一档。

3. 误报归因基本可靠，但“流程门禁类误报”可能掩盖真正的资料缺口。误报几乎全部是检查器在识别器件角色、过滤 DNP、解析数值时出错，Codex 给出的修复位置合理。需要警惕 #15 这一类：SR 报的是证据门禁，Codex 判为误报并建议放宽门禁，但底层的晶振根本没写频率，放宽后可能直接判通过。建议门禁放宽的回归用例里，加一条“晶振无频率/CL 时仍须报资料缺失”。

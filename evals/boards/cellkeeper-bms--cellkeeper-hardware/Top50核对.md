# Top 50 逐条核对 — cellkeeper-bms--cellkeeper-hardware

50条均核对。漏报为3个检查对象覆盖缺口；G03-018/019共用M03，不重复计数。其余“已有检查待证据”不算漏报。未重新取得库内所引标准全文。

|序号|准则|结论|独立证据/边界|
|---:|---|---|---|
|1|G01-018 −48 V 输入的极性与回线接地方式按 ETSI 4.1|NOT_APPLICABLE|整页电源输入为J1 13–16V逻辑/接触器DC；未见−48V通信输入、RTN/NEG48或AC整流市电输入；相应ETSI/交流暂降示例不适用。|
|2|G01-019 −48 V 输入的工作电压范围与耐受范围|NOT_APPLICABLE|整页电源输入为J1 13–16V逻辑/接触器DC；未见−48V通信输入、RTN/NEG48或AC整流市电输入；相应ETSI/交流暂降示例不适用。|
|3|G01-020 −48 V 输入 0.1 s 中断后自恢复|NOT_APPLICABLE|整页电源输入为J1 13–16V逻辑/接触器DC；未见−48V通信输入、RTN/NEG48或AC整流市电输入；相应ETSI/交流暂降示例不适用。|
|4|G01-021 −48 V 输入承受 500 V 1.2/50 µs 浪涌|NOT_APPLICABLE|整页电源输入为J1 13–16V逻辑/接触器DC；未见−48V通信输入、RTN/NEG48或AC整流市电输入；相应ETSI/交流暂降示例不适用。|
|5|G01-022 −48 V 输入在 −40.5 V 下电流不大于 1.5 Im|NOT_APPLICABLE|整页电源输入为J1 13–16V逻辑/接触器DC；未见−48V通信输入、RTN/NEG48或AC整流市电输入；相应ETSI/交流暂降示例不适用。|
|6|G01-023 −48 V 输入的合闸浪涌电流不超过 ETSI 图 4|NOT_APPLICABLE|整页电源输入为J1 13–16V逻辑/接触器DC；未见−48V通信输入、RTN/NEG48或AC整流市电输入；相应ETSI/交流暂降示例不适用。|
|7|G01-024 交流输入 1 周期 0% 跌落不复位（判据 B）|NOT_APPLICABLE|整页电源输入为J1 13–16V逻辑/接触器DC；未见−48V通信输入、RTN/NEG48或AC整流市电输入；相应ETSI/交流暂降示例不适用。|
|8|G01-025 交流输入较长暂降与中断后自恢复（判据 C）|NOT_APPLICABLE|整页电源输入为J1 13–16V逻辑/接触器DC；未见−48V通信输入、RTN/NEG48或AC整流市电输入；相应ETSI/交流暂降示例不适用。|
|9|G01-026 USB 供电输入电压窗按 vSafe5V 并计线缆压降|CHECK_PRESENT_PENDING|J11/J19 VBUS经D44/D47到+LDO_IN，U25为TLV1117LV；未把源电压固定5V。需线缆压降、各USB负载和LDO压差的全包络；SIG-C05已按两口三状态展开。|
|10|G01-027 USB 可用电流按实际协商档取|CHECK_PRESENT_PENDING|J11/J19 CC1/CC2分别R79/R80与R138/R139=5.1k，只有Rd不能证明可取3A；无已确认USB枚举/电流预算，SIG-C05保留。J9 5V1A是专用HMI输出，不移植成USB输入预算。|
|11|G01-029 USB Sink 的 VBUS 体电容不超过 100 µF，超出须限流|CHECK_PRESENT_PENDING|J11 VBUS在Net-(D44-A)、J19在Net-(D47-A)，各经二极管进+LDO_IN；C5=22uF在二极管之后，C31=680uF在+5V被D50反向隔开，不能把680uF直接加到VBUS。SIG-C05/PWR-C13已问；缺装配容差与充电路径边界，不认定超100uF漏报。|
|12|G01-030 USB Sink 断开检测在 40 ms 内、5 V 时门限不高于 3.67 V|CHECK_PRESENT_PENDING|R78/R153与R155/R154=3.3k/5.1k，VBUS检测系数0.607143；静态分压不等于40ms断开检测，GPIO/固件/时序合同未给，SIG-D07/SIG-C05已问。|
|13|G01-031 USB Source 未连接时 VBUS 不带电，电容不超过表 4-2|NOT_APPLICABLE|图p1 API TTL RS232 HMI Interface和README明确J9不是电脑USB，D+/D−作UART；不能把该专用连接器宣称标准USB Source。供电/误插/端口保护仍保留，J9支路保护见M02。J11/J19是Sink。|
|14|G03-003 内补偿变换器与 LDO 的输出电容有效值在手册允许范围内|CHECK_PRESENT_PENDING|U25 OUT→C9=4.7uF/GND，U26 OUT→C60=4.7uF及C116=100nF/隔离地；TLV1117LV p13要求有效Cout>0.5uF。未见100nF替代或DNP导致本例硬缺陷；有效下界仍待温度/偏压/容差，PWR-C04已问。|
|15|G03-004 内补偿变换器与 LDO 的输出电容 ESR 在手册窗口内|CHECK_PRESENT_PENDING|U3 L3=22uH，C31=680uF聚合物并陶瓷输出；TPS5430 p15-18限定输出电容ESR零点与内补偿。TLV1117LV p13允许零ESR，不套AMS1117旧符号的ESR要求。PWR-C04/PWR-C15已问，缺准确ESR界。|
|16|G03-016 正常启动时通路 MOSFET 在降额后的 SOA 内|CHECK_PRESENT_PENDING|Q1–Q4是接触器低侧PWM；DRV-C02逐管存在。实际线圈L/R、壳温、启动PWM和准确MOS SOA未齐，不能把100V61A当SOA，也未找到可证越限的启动轨迹。|
|17|G03-018 变换器 UVLO 开启点低于输入窗下限|MISS|M03：U3.5=ENA且内部UVLO存在；FN-POWER-CONVERTER-U3.not_asked却以无UV/OV/ILIM/EN排除PWR-C06。准确手册p3,p9给出ENA/UVLO，缺源压/负载合同仅影响结论，不应取消检查对象。|
|18|G03-019 满载电流在源阻抗上的压降小于 UVLO 滞回|MISS|与M03同一覆盖根因，不另计：TPS5430内部UVLO/迟滞必须与J1→D15→V_in源/线阻核对；本板PWR-C06未绑定U3，实际源阻抗/启动负载未给。|
|19|G03-021 软启动充电电流加启动期负载低于器件限流下限|CHECK_PRESENT_PENDING|U3有内部slow-start，+5V含C31=680uF及其他陶瓷，且供给U25/隔离模块/HMI。PWR-D03/PWR-C13已有；实际最短充电时间/全部启动负载不齐，不用空载CΔV/t证明满配置。|
|20|G03-025 复位门限高于各负载最低工作电压，掉电先复位|CHECK_PRESENT_PENDING|主控/监督同3V3供电，有内部POR与RUN；SYS-MONITOR/PWR-T04存在，原图3.3/5/Vin/Vcont分压到U14。复位/欠压安全合同、掉电斜率和传播极值未给，不把任一RC当掉电先复位。|
|21|G03-028 上电时序在极值时间下满足约束|CHECK_PRESENT_PENDING|双RP2354B含3V3和各自1V1内部变换域，PWR-C24/RST-T03存在；USB/主输入与Shunt/CAN电源还可能异步。各轨极值及允许顺序窗不齐。|
|22|G03-032 稳压器反向电流在手册允许内或已阻断|CHECK_PRESENT_PENDING|+LDO_IN由D44/D47/D50 OR；不能据此关闭U25/U26及IO全部反向电流。PWR-C05和SIG-C08已展开，保留源组合/回灌分析。|
|23|G03-037 电解与钽电容不承受反压|CHECKED_TOPOLOGY|极性电容C1.1=V_in、C14.1=V_Contactor、C31.1=+5V，负端均GND，与p1正号一致；未见反接极性。本项只核当前图示极性，输入异常仍另审。|
|24|G03-038 电解与钽电容的直流加纹波峰值在降额内|CHECK_PRESENT_PENDING|C1/C14/C31在XML Voltage字段均35V Polymer；正常名义13–16V或约5.25V有裕量，仍缺纹波/浪涌及降额等级。DEV-C01对象含这些器件，不把未完成应力审查列为自动漏报。|
|25|G03-040 串联使用的电解电容有均压措施|NOT_APPLICABLE|实际板内未见串联电解组；C1/C14/C31均跨各自电源与GND，不能将板外电芯串联误当电解串联。|
|26|G04-005 输入信号不超接收端绝对最大值|CHECK_PRESENT_PENDING|外部USB/VBUS和分流/HV输入已保留SIG-C08/ANA-C03；两个5V非稳压供电的ISO1050推荐窗问题保留needs_human，不以“绝限6V未超”放行推荐4.75–5.25V。|
|27|G04-007 未上电接口承受正常或故障信号不损坏|CHECK_PRESENT_PENDING|SIG-C08逐I2C段和跨域接口已问掉电注入；U16隔离两侧不同电源，USB可先供电。缺实际通断组合与端点Ioff/残压，不因同源3V3的名义图推定无掉电风险。|
|28|G04-009 信号经保护二极管反灌未上电电源轨的电流与后果已判定|CHECK_PRESENT_PENDING|J11/J19检测3.3k/5.1k、多个外部/隔离控制端均有可能异步；SIG-C08存在。只算串阻最大电流不能证明浮置轨残压，缺关断负载/泄放边界。|
|29|G04-010 上电和复位期间关键输出有确定状态|CHECK_PRESENT_PENDING|Q1–Q4有各100k G/S泄放和输入5.1k下拉；CTR_EN有R144=5.1k，四EN典型并联50k。RST-T04/RST-E01已有；源态、内部弱拉保证界和系统安全态未确认，不把typ计算写PASS。|
|30|G04-017 I²C 上拉电阻不超上升时间决定的上限|CHECK_PRESENT_PENDING|R57/R66、R69/R72、R89/R90各段5.1k；SIG-C01六段完整。tr=0.8473RC，100pF算例432ns；实际总线电容/速率未给，不能判原板慢沿缺陷。|
|31|G04-018 I²C 上拉电阻不低于灌电流决定的下限|CHECK_PRESENT_PENDING|各段3.3V、VOL0.4V名义电流约0.569mA；弱端IOL/电源/电阻公差与隔离VOL须配对。SIG-C01/C07已有；没有把一侧上拉误并到另一侧。|
|32|G04-032 CAN 总线两端端接，总阻约 60 Ω|CHECK_PRESENT_PENDING|U5经FL1到CAN H/L，R31=120Ω由JP36开闭；U10的CAN2配置/两端节点另核。SIG-C03四电路已展开，FL1/FL2物理绕组脚、线束拓扑仍未知；单板120Ω不能证明整链60Ω，也没有发现H/L硬短接。|
|33|G04-040 隔离接口两侧的供电和地不被无意短接|MISS|M01：PRO-D02仅光耦组及U16；U5/U4 CAN隔离与TR1 isoSPI边界未绑定。U5两侧GND/GND CAN分离，U10明示非隔离。TR1次级经R145/R146=2MΩ到GND，必须明确跨接资格，不直接定原板失效。|
|34|G04-041 运放两个输入在最坏工况下不超共模范围|NOT_APPLICABLE|板内无独立通用运放；INA228/ADS1115的内部ADC通道范围仍在ANA-C01/C03核，不索取不存在的外置运放输出/共模模型。|
|35|G04-054 ADC 输入不超满量程和绝对最大值|CHECK_PRESENT_PENDING|每HV支路4×3M+24k、参考VSenHalf约1.65V，名义400V差值0.7984V。ADS1115 p4要求每AIN在GND..VDD，不能用±6.144V量程放行对地越界；ANA-C03存在，共模/故障条件未给。|
|36|G04-078 晶振负载电容与晶振规定 CL 相符|CHECK_PRESENT_PENDING|Y1/Y2准确ABM8-272-T3：12MHz、CL10pF、ESR≤50Ω；C39/C40及C70/C71均15pF→7.5pF+Cstray，需约2.5pF寄生。CLK-C01已有，未虚构寄生或拿家族CL判硬错。|
|37|G04-079 振荡器增益裕量足够起振|CHECK_PRESENT_PENDING|准确晶体ESR50Ω和RP2354B振荡器条件已取得；完整温压/负阻、限流1k R53/R92与驱动界仍待，CLK-C01存在，兼容推荐不能替代本板起振/驱动余量。|
|38|G04-082 一颗晶振只驱动一个器件|CHECKED_TOPOLOGY|Y1仅连U14 XIN30/XOUT31（经R53），Y2仅连U20对应脚（经R92），两晶体网络独立；没有两个有源振荡器共用同一无源晶体。|
|39|G05-019 每条配电支路在源侧有保护|MISS|M02：+5V→FB2→D42→J9 VBUS为对外HMI供电支路，最终PRO-C04只绑定J6接触器对象。上游U3限流可能覆盖但必须逐支路核，不能因无保险/eFuse不建检查。|
|40|G05-022 过流动作点上限下通路器件与连接器不超额定|CHECK_PRESENT_PENDING|接触器Q1–Q4/TVS/SS54和外接J6的动作/载流风险由DEV-C01/C04及DRV-C02保留；缺实际线圈/故障源/连接器保证，不由电流标签定缺陷。J9支路覆盖并M02。|
|41|G05-025 故障电流下的动作时间短于被保护对象的耐受时间|CHECK_PRESENT_PENDING|F3/F4在Overall HV Battery System Diagram中，属板外系统，缺准确熔断器/故障源合同，不按同名63A标签放行。板内U3限流对外配电支路的时域覆盖并M02；没有证据单列实板动作时间缺陷。|
|42|G05-030 TVS 工作电压不低于被钳节点最高工作电压|CHECK_PRESENT_PENDING|D1–D3、D4–D6、D24–D26各三只SMB6.8CA串堆，原图有13–16V输入；PRO-E02已对末端候选展开，但必须逐段与堆叠全窗口分析。缺准确供货手册与共享工作点，不能只拿单管VRWM比较整个输入。|
|43|G05-031 TVS 钳位电压不超被保护器件绝对最大值|CHECK_PRESENT_PENDING|D18/D21/D39/D40 SMCJ33CA到GND，C13/C15/C34/C35并在接触器开关节点；PRO-E02已有。缺实际箝位电流/波形与Q1–Q4同工况瞬态耐受，33V标称不是Vcl。|
|44|G05-032 TVS 浪涌能力按波形与温度折算后不小于浪涌电流|CHECK_PRESENT_PENDING|相同TVS/SS54的线圈重复PWM与单次关断磁能须分别核；源L/R、频率/温度及准确厂家脉冲曲线未齐。PRO-E02/DRV-C01保留，未将封面1.5kW当任意波形允许值。|
|45|G05-040 带短路启动时通路 MOSFET 在降额后的 SOA 内|CHECK_PRESENT_PENDING|Q1–Q4为低侧线圈驱动，DRV-C02逐管有对象；端口/线圈短路时需VDS×ID轨迹、U3或外源供电限流与持续时间，未据常规开机计算放行短路。|
|46|G05-041 热短路时通路 MOSFET 按开始壳温降额后在 SOA 内|CHECK_PRESENT_PENDING|同四只MOS热短路没有沿用25°C SOA；实际开始壳温、PWM损耗、外部供电链及故障切断条件未给，DRV-C02保留。|
|47|G05-048 熔断器分断能力不小于预期短路电流|CHECK_PRESENT_PENDING|F3=Pyro Fuse、F4=63A HV DC仅系统示意，无完整MPN、直流分断能力或最低电池内阻。不能把本PCB接触器驱动的保护与整包熔断器验收混为一项，保留系统合同缺口。|
|48|G05-054 每个对外电源接口的反接有明确处置|CHECK_PRESENT_PENDING|逻辑入口J1.4→D15→Vin，接触器入口J1.3经D11/D12/L2；正向串联SS54方向已核。PRO-D04/PWR-C26等存在，但反接所有返回/信号旁路及负压工况不齐，不能只看正端二极管放行。|
|49|G05-057 反接阻断之前没有单向 TVS 造成源短路|CHECKED_TOPOLOGY|输入防护为双向TVS符号的三串SMB6.8CA，没有在串联防反之前的单向TVS直接正向短路拓扑。正常/浪涌的三串工作和能量配合仍见42–44。|
|50|G05-087 MOSFET 防反接的体二极管方向和栅极接法使反接时不导通|NOT_APPLICABLE|输入防反用SS54二极管；Q1–Q4源接GND、漏接接触器低端，是驱动开关，不是高侧MOS防反。不能套PMOS体二极管方向示例。|

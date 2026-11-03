# Top 50逐条核对

用途为推断；本板无已确认硬件漏检，3项是计划/功能覆盖漏问，已补本轮rule_gaps。

|序号|准则|状态|本板证据与处理|
|---|---|---|---|
|1|G01-018|NA|本板没有通信−48V输入，JPWR1是正VBATT；不把OBD车载用途套−48V极性规范。|
|2|G01-019|NA|无−48V端口；TPS5430的5.5..36V工作窗不能当ETSI窗口。|
|3|G01-020|NA|无−48V恢复要求；实际VBATT恢复仍由PWR-C18/RST-T03待核。|
|4|G01-021|NA|无−48V的500V波形合同；未把示例波形当本板要求。|
|5|G01-022|NA|无−48V/Im定义；实际输入电流留PWR-C19。|
|6|G01-023|NA|无−48V合闸/ETSI图4适用合同；VBATT热插拔仍需真实源窗。|
|7|G01-024|NA|无交流整流/AC输入；不虚构一周期保持要求。|
|8|G01-025|NA|无交流暂降接口；实际输入恢复单列待核。|
|9|G01-026|plan_miss|M03：A1内置Micro-B USB有源，载板40脚悬空不代表无USB；原生无SIG-C05，本轮GAP-USB-MODULE补问电压窗。|
|10|G01-027|plan_miss|M03：USB-only时三路CAN和SD也由模组3V3供电，需实际主机资格/工作负载；无协商电流不能默认3A。|
|11|G01-029|plan_miss|M03：USB供电本体未展开。反证：本板C4=220µF位于D2阳极，USB→片内二极管→VSYS使D2反偏，不能把它直接计入VBUS。Micro-B具体限制按适用USB模式核，不盲套PD附着态100µF。|
|12|G01-030|NA|本图是Pico W内置Micro-B USB，未声明Type-C/PD Sink断开检测；不得套PD 40ms/3.67V。|
|13|G01-031|NA|USB-CDC用途推断为Device，未声明USB Source/Host，不能强制加Type-C VBUS Source开关。|
|14|G03-003|covered_pending|PWR-C04逐U4/状态已问；U4.8 PH经L1到C4.1，C4=220µF，仅名义值不能证明有效容量；F27。|
|15|G03-004|covered_pending|PWR-C04/PWR-C15已问；TPS5430 PDF p15要求ESR上下条件，C4技术/ESR未给；不能套5V Poscap例直接PASS。|
|16|G03-016|NA|无外置线性充电/热插拔通路MOS；U4片内开关按其电流/短路条件核，不借外管SOA例。|
|17|G03-018|covered_pending|PWR-C06/RST-T01已问U4内部UVLO，p5 rising max5.5V；缺VBATT下限，不把芯片允许窗当实际源窗。|
|18|G03-019|covered_pending|PWR-C06已问；p5迟滞仅typ0.35V，源/线阻和启动负载未知，未判无打嗝。|
|19|G03-021|covered_pending|PWR-D03已问；C4名义220µF、名义输出4.2735V、tSSmin5.4ms条件充电0.174106A，需再加容量公差与负载。|
|20|G03-025|covered_pending|PWR-T04/SYS-MONITOR已问；Pico内部复位/SMPS与TCAN UVLO须按实际电源斜率/安全态定界，缺系统合同。|
|21|G03-028|covered_pending|PWR-C24/RST-T03已问；外供U4→D2→VSYS→模组3V3，USB另源，不能只看8ms典型。|
|22|G03-032|covered_topology|PWR-C05已问；D2的A接U4输出/K接VSYS，Pico内部USB二极管OR为官方PDF pp15-16结构。USB-only阻止向C4/U4正常回充，故不报直接反灌；漏电/失效/动态仍待核。|
|23|G03-037|conditional_NA|C1–C4均Device:C无极性符号，C4封装1206；不能仅凭220µF认定电解/钽或反接，DEV-C01仍审额定。|
|24|G03-038|covered_pending|DEV-C01/DEV-C02覆盖C3输入、C4输出；缺采购额定和实际轨峰值，不能把名义电容当已满足。|
|25|G03-040|NA|C1/C3/C4各自对地，C2为BOOT-PH飞跨，无串联电解分压结构。|
|26|G04-005|plan_miss|M01：ADC分压进入A1.31但原生没有ANA-C03；CAN正常I/O同3V3的局部保证值已比，不能替代ADC/失电检查。|
|27|G04-007|plan_miss|M01：VBATT可先存在而Pico未供电/启动，GPIO26是标准模拟IO；GAP-ADC-VBATT补核。外部UART/CAN故障另PRO-D04。|
|28|G04-009|plan_miss|M01：R15/R14连接到GPIO26的模拟输入未被原生SIG-C08/ANA-C03覆盖；100k限流不等于已证明未供电轨不被抬高。|
|29|G04-010|covered_pending|RST-T04 CAN三电路均有；F26：三STB上拉与PicoGPIO6复位下拉竞争，手册0V IIL不能线性外推到阈值。|
|30|G04-017|NA|本载板没有SDA/SCL/I2C电阻网；SD/CAN/UART不是I2C；模组内无线接口不扩为载板I2C。|
|31|G04-018|NA|无I2C上拉段，不套IOL公式到SD的10k上拉。|
|32|G04-032|covered_pending|SIG-C03三路×idle/active已问；R1/R2/R5 120Ω各经外接跳帽，未闭帽时非120Ω跨H/L；现有两端加本板变40Ω是条件例，非既成缺陷。|
|33|G04-040|NA|无隔离器、隔离DC/DC或隔离要求；CAN并非天然需要电隔离；同地不报隔离失效。|
|34|G04-041|NA|无分立运放/比较器，ADC输入归G04-054；不得把ADC套运放共模。|
|35|G04-054|plan_miss|M01：GPIO26_ADC0接100k/10k VBATT分压，需满量程及绝限/掉电；±5%上界比0.0995261、3.3V条件VBATT上限33.157V。|
|36|G04-078|module_scope|无载板晶体；Pico W时钟已封装在模组，若复用其受控供电/温度与标准时钟能力，不要求载板添晶振CL；自定义频率仍按平台范围。|
|37|G04-079|module_scope|无外接无源晶体，不能要求其给载板负阻/ESR；原厂模组参考图PDF p21完整含内部12MHz回路。|
|38|G04-082|NA|载板无晶体，更无一晶驱两器件；Pico官方内部时钟结构不冒充载板未画引脚。|
|39|G05-019|plan_miss|M02：JPWR1源端直达C3/U4/R15，原生因无FUSE/TVS/保护核心没有PRO-C04；GAP-VBATT-SOURCE补问上游合同，不直接判缺保险。|
|40|G05-022|covered_pending|DEV-C01/C04以及PRO-D04问实际通路和接口；TPS5430峰值限流4..6A不能当输入连接器/磁件额定，无闭合负载与采购范围。|
|41|G05-025|covered_pending|源侧短路与容差动作窗口没有上游保护/源阻抗，PRO-D04与M02保留该边界；U4输出短路保护不能保护C3输入短路。|
|42|G05-030|NA_with_system_check|无TVS，不能凭缺TVS判故障；实际源/接口ESD与浪涌仍由PRO-D03/PRO-D04待合同；D1是续流肖特基，不是TVS。|
|43|G05-031|NA_with_system_check|无TVS钳位窗；TCAN片内±58V绝限及IEC额定不能覆盖任意车载波形。|
|44|G05-032|NA|无TVS脉冲能力对象，不套封面瓦数；若后续加TVS，需实际波形/温度。|
|45|G05-040|NA|无外置线性限流MOS；U4集成Buck开关按厂家短路/频率折返窗口，不套外MOS SOA。|
|46|G05-041|NA|无外置通路MOS热短路SOA；U4/二极管/电感实际温升与损耗仍待工作点并移交热验证。|
|47|G05-048|conditional_pending|本板无熔断器；上游系统保险及安装点预期故障电流未知，由M02源侧保护合同问，不能凭无F1推断分断不足。|
|48|G05-054|covered_pending|PRO-D04.JPWR1已有异常/误接问题；U4.7直接VBATT，D2在输出不是输入防反。未给反接允许条件/上游措施，所以F31待核，不报已损坏。|
|49|G05-057|NA|没有输入单向TVS或反接MOS组合；D1的A=GND/K=PH是Buck续流，不是TVS反并联入口。|
|50|G05-087|NA|无外置防反MOS，不能强制对D2套VGS/体二极管；D2方向按实际肖特基OR另核。|

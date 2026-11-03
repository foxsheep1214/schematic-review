# Top 50逐条漏报核对

基线industrial_telecom。覆盖catalog RF/CLOCK/POE_PD/ETHERNET，并补原图实际USB、稳压、保护、I2C、电平转换、模拟等。以下是适用性/证据核对，不是50项全通过。M01为自动层无提示（通用人工项存在），M02/M03为计划对象/模型漏问；三条均不升级成已确认原板硬件失效。

| 序号/准则 | 状态 | 对象、证据及边界 | 应报SR规则 |
|---|---|---|---|
| 1 / G01-018 | not_applicable | 本板PoE是44–57V浮动受电模块，DC_IN为正输入；无ETSI −48V输入，不将PoE的48V标称数值套ETSI条款。 | PWR-C17 |
| 2 / G01-019 | not_applicable | 本板PoE是44–57V浮动受电模块，DC_IN为正输入；无ETSI −48V输入，不将PoE的48V标称数值套ETSI条款。 | PWR-C17 |
| 3 / G01-020 | not_applicable | 本板PoE是44–57V浮动受电模块，DC_IN为正输入；无ETSI −48V输入，不将PoE的48V标称数值套ETSI条款。 | PWR-C18 |
| 4 / G01-021 | not_applicable | 本板PoE是44–57V浮动受电模块，DC_IN为正输入；无ETSI −48V输入，不将PoE的48V标称数值套ETSI条款。 | PRO-C01 |
| 5 / G01-022 | not_applicable | 本板PoE是44–57V浮动受电模块，DC_IN为正输入；无ETSI −48V输入，不将PoE的48V标称数值套ETSI条款。 | PWR-C19 |
| 6 / G01-023 | not_applicable | 本板PoE是44–57V浮动受电模块，DC_IN为正输入；无ETSI −48V输入，不将PoE的48V标称数值套ETSI条款。 | PWR-C13 |
| 7 / G01-024 | not_applicable | 无交流市电输入/一次侧整流或市电暂降要求；隔离模块不是交流输入声明。 | PWR-C18 |
| 8 / G01-025 | not_applicable | 无交流市电输入/一次侧整流或市电暂降要求；隔离模块不是交流输入声明。 | PWR-C18 |
| 9 / G01-026 | needs_human | J2/J4各CC1/CC2用5.1k Rd到GND，确为Sink；D4/D5+JP6/F1压降还需实际USB输入窗/源电流。不得从名义VBUS=5V放行。 | SIG-C05 |
| 10 / G01-027 | needs_human | OCXO暖机最大1.5A（Rakon p2）且与主板并用；两个口均只有Rd而无CC电流检测输入，接入源允许电流及优先级合同未给，不能假定两口各3A或可相加。 | SIG-C05 |
| 11 / G01-029 | automatic_miss M01 | J2→D4 / J4→D5→JP6(closed)→F1→VBUS，C6+3×1µF=103µF，本口另4.8µF，合计名义107.8µF；通用SIG-C05存在，缺沿二极管/PTC的自动提示，未证实过流波形。 | PWR-C13, SIG-C05 |
| 12 / G01-030 | needs_human | J2 VUSB直达U2.A8做USB存在检测；U1 ESP35/DeviceSense仅分3.3V，不是两USB-C各自断开检测。40ms/3.67V的协议适用与检测保证需核mosaic USB说明/接口角色，不能只看有分压即PASS。 | SIG-D07 |
| 13 / G01-031 | not_applicable | J2/J4双5.1k Rd均Sink；没有Type-C Source供电端。不能把二极管合路视作Source角色。 | SIG-C05 |
| 14 / G03-003 | local_fact_pending | U11 3.3V直接对地名义15.7µF，U5 3.3V_P 53.4µF；C21/C22各1µF不能单独判低于AP7361C p10要求2.2µF；Ceff/温度偏压/局部布局仍未给，通用PWR-C04已问。 | PWR-C04 |
| 15 / G03-004 | needs_human | AP7361C Rev5-2 p12 ESR vs IOUT稳定区随电流变化；C21/C22及同网MLCC未锁准确偏压/温度阻抗，不能套旧版10–300mΩ静态窗；PWR-C04已问，未证实ESR违规。 | PWR-C04 |
| 16 / G03-016 | needs_human | Q2–Q9 DMG2305UX背靠背，C65=100µF/20%、OCXO启动负载最高1.5A；SOA须结合LTC4418斜率/动作保证、源阻抗和开始壳温；已有DRV-C02八器件项，未报漏审。 | DRV-C02 |
| 17 / G03-018 | needs_human | U26/27各UV=200k/4.7k/47k三段，名义开启约4.868V；必须按1V阈值/公差/偏置/HYS及源输出窗核，产品输入窗口未给。PWR-C06已问。 | PWR-C06 |
| 18 / G03-019 | needs_human | J9 DC_IN经D8/U6，USB经D4/D5/PTC，源阻抗及带载压降未知；不能用LTC4418名义滞回替代全路径不打嗝证明。PWR-C06已有通用项。 | PWR-C06 |
| 19 / G03-021 | needs_human | LTC4418内部soft-start作用于VOCXO，不作用于二极管主VBUS；Q2–Q9/C65/OCXO启动最高1.5A需分别预算。PWR-C13/DRV-C02已有提问，缺实际状态与输入保证。 | PWR-D03 |
| 20 / G03-025 | needs_human | U1.EN R1=10k/C3=10µF名义RC=.1s；内部brownout及U2 reset不能由RC替代保证门限。PWR-T04/RST-C01已问，缺掉电斜率/复位有效条件。 | PWR-T04 |
| 21 / G03-028 | needs_human | U13 OCXO启动、暖机和长期稳定是不同时间尺度；Rakon p2–3注明start-up 1s与暖机分钟级。U2使用外部REF_I须确认冷启动及救援行为；RST-T03/CLK-D01已问。 | PWR-C24 |
| 22 / G03-032 | needs_human | U5/U11/U25同VBUS输入的独立LDO不证明不同输出掉电轨迹一致，C6/C65储能及跨接口反灌需按厂家允许路径核。PWR-C05已问，尚非已证过应力。 | PWR-C05 |
| 23 / G03-037 | local_fact_pending | 原图p2/p9 C6/C65正端分别VBUS/5V、负端GND，正供电标称方向正确；反接源窗、返回路径及故障允许负压未定，不把方向正确当全部反压工况通过。 | DEV-C01 |
| 24 / G03-038 | local_fact_pending | C6/C65符号25V/20%，正常标称约5V；受控最高电压、纹波峰值及降额等级/工况未给。未确认有25V越限；DEV-C02/C10待核。 | DEV-C01 |
| 25 / G03-040 | not_applicable | C6/C65为两个独立5V轨对地储能，非串联分压电解组；C9为1nF高压耦合，不是串联电解。 | DEV-C01 |
| 26 / G04-005 | needs_human | J9输入经74LVC2T45不同VCC域、D13/D14阵列；U17/U20/U23/U24实际共模和U2 REF_I 0.5–1.7Vpp还要极值计算。SIG-C08/ANA-C01已问，不凭网名认5V耐受。 | SIG-C08 |
| 27 / G04-007 | planning_gap M03 | U1↔U2多UART为两个独立LDO域直连，当前只有I2C与泛LEVEL_SHIFT的SIG-C08；未逐该UART接口生成单域掉电对象。74LVC2T45 p1的Ioff只可覆盖转换器，不能覆盖这些直连。 | PRO-D04, SIG-C08 |
| 28 / G04-009 | planning_gap M03 | 同一UART多路同时注入须合计到3.3V或3.3V_P残压；正常共地、名义同电压不足以关闭。是否发生和容许边界仍needs_human，未确认硬件损坏。 | SIG-C08 |
| 29 / G04-010 | needs_human | U26.CAS为输出→U27.EN合法级联；U26未用EN/SHDN与U27.SHDN虽内部3.2µA上拉，却未遵循未用接INTVCC条款。U1 reset/boot和U15CLR状态各须分别判断。 | RST-T04 |
| 30 / G04-017 | needs_human | 各段2.2k；若条件取400kHz/100pF，0.8473RC≈186ns，仅为算例非本机保证。Qwiic线缆Cb未知，OCXO文档literal 400Hz不可擅改400kHz。六段SIG-C01已问，不算确认漏报。 | SIG-C01 |
| 31 / G04-018 | planning_gap M02 | U19 pass-FET导通低态的双侧2.2k电流相加，VOL=.4V名义总3.409mA；最弱端IOL保证尚未锁。六段孤立检查缺耦合模型，不能据3mA示例断定原板违规。 | SIG-C01 |
| 32 / G04-032 | not_applicable | 无CAN/CANH/CANL收发器；J5 Ethernet端接、J1/J3/J8/J10 50Ω同轴不能套60Ω CAN判据。 | SIG-C03 |
| 33 / G04-040 | false_alarm F18 | U6隔离REC15E、U7隔离DP5305输入/输出分侧；GND-ISO、POE_RETURN、GND不是跨IC全部脚短接。domains.conducts捏造合域；实物隔离工作资格仍PRO-C03待核。 | PRO-D02 |
| 34 / G04-041 | needs_human | U17/U20/U23/U24为LMV7219比较器，不是可线性反馈运放；IN+/IN-通过1.8V分压和AC耦合接10MHz/PPS，各脚必须核共模和瞬态。ANA-C01已问，未确认越界。 | ANA-C01 |
| 35 / G04-054 | needs_human | U1.5 IA39用于相位/检测输入；需追C8/相位网络和ADC衰减/满量程允许配置，不能从供电3.3V推ADC满量程3.3V。ANA-C03已有通用项，未确认越限。 | ANA-C03 |
| 36 / G04-078 | not_applicable | 无板外两端无源晶体。U13有源OCXO→U16三路splitter，U2外部REF_I；U4外部50MHz，CH340C自带时钟。不把OCXO当晶体算CL。 | CLK-C01 |
| 37 / G04-079 | not_applicable | 同上，未用外部皮尔斯晶体；有源OCXO启动时间/输出工作窗仍在CLK-D01待核，不索取不存在的负阻模型。 | CLK-C01 |
| 38 / G04-082 | not_applicable | 分配的是U13主动输出，经U16/JPS-3-1+和独立比较器，不是两个片上振荡器并接同一无源晶体；不报晶体共享。 | CLK-C01 |
| 39 / G05-019 | needs_human | VBUS F1与OCXO F2各2A hold PPTC，J9可选JP15输出VCCIO、Qwiic3.3V对外也需源侧故障合同；不能见有F1即判所有输出受保护。PRO-C04已问。 | PRO-C04 |
| 40 / G05-022 | needs_human | F1/F2标4A是trip等级而非实时限流上限；Q2–Q9及J9/USB/电缆须按动作窗最大电流核。PRO-C05/C08已有通用项，不假设20V/4.2A标题为全部温度额定。 | DEV-C01, DEV-C04 |
| 41 / G05-025 | needs_human | PPTC时间电流和DC/DC/USB源限流互相影响；无源故障电流最小/最大与被保护对象耐受，不能只按4A推动作时间。PRO-C05已问。 | PRO-C05 |
| 42 / G05-030 | knowledge_gap F09 | PESD0402四颗准确身份未锁；D13/D14 DF5A5.6LFU在SW4=VBUS时还须核5V摆幅，不从5.6料号猜VRWM。PRO-E02已有D1/D15–17，D2/3/6 DT1042另列数值提问。 | PRO-E02 |
| 43 / G05-031 | knowledge_gap F09 | D15直接U10.7、D1直接U2.AC20；实际ESD脉冲下Vc与IC应力/注入界未齐。符号40VC不能独立证明器件在所有脉冲都40V或芯片必坏。 | PRO-E02 |
| 44 / G05-032 | knowledge_gap F09 | 同一端口单一威胁波形、电流、温度和前级残压未给；不能把器件ESD等级当系统浪涌能量保证。PRO-E02已有提问。 | PRO-E02 |
| 45 / G05-040 | needs_human | Q2–Q9带短路启动的源限流/定时/开关轨迹未锁，DRV-C02已有逐MOS对象；不能靠名义Q额定判SOA。 | DRV-C02 |
| 46 / G05-041 | needs_human | 热短路需先算开始壳温再对SOA降额；缺正常任务负载和壳温有据上界，不能把25℃SOA当热态。实际热实现后续验证，不把缺实测本身当电气FAIL。 | DRV-C02 |
| 47 / G05-048 | needs_human | F1/F2为PPTC而非传统熔丝，须核0ZCH系列Imax/Vmax及准确后缀；符号6V/2A/4A不提供安装点Isc。PRO-C08/PRO-C01有问，不假报1500A市电分断要求。 | PRO-C01 |
| 48 / G05-054 | local_fact_pending | J9 DC_IN+经SK34A D8→U6；D8方向可阻正端反接。PoE输入极性由MagJack/PD模块接法另核；USB为既定连接器角色。未锁全部反接源窗/旁路返回，不声称整板通过。 | PRO-D04, PWR-T05 |
| 49 / G05-057 | not_applicable_topology | 原图DC_IN/D8之前无单向对地TVS，D1/D15/D16/D17均在RF/信号路径；没有本条所指前置TVS反接短路结构。其他接口反接/ESD仍分别待核。 | PWR-C26 |
| 50 / G05-087 | local_fact_pending | Q2/Q3、Q4/Q5、Q6/Q7、Q8/Q9各共源背靠背，pin2=source共同VS，pin3=两端drain，gate共同G；与LTC4418 RevA p7/common-source定义相符。体二极管朝向局部已核；完整负压/短路/关断保证仍需源合同。 | PWR-T05 |

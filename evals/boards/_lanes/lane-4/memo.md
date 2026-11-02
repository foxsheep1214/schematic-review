- kria-k26-devboard：DNP J_SOM240_2产生160条NET-A01；贴装SoM备用脚仍单独待确认，不一概撤回。
- 原生Value可能是库名；先查XML Val/Tolerance。read_bom能保留字段，但检查器未必使用Val，0R/串阻会漏认。
- ETHERNET/LEVEL_SHIFT候选states=[]可由决定器接受、却被lint拒绝；无受控需求不要编状态，记录回退范围。
- results-format文档schema14、运行时15；用migrate_results再校验。needs_human不硬塞VENDOR_DATUM，REVIEW_INCOMPLETE阻止正式报告。
- 未用CMOS输入NC查准确手册：U36.13有p3注4反证；SCK已有SIG-C01、晶体CL缺证据，不制造漏报。
- angelnu--lorawansensor：SolderJumper_2_Bridged 的 BRIDGE 子串会生成假 POWER_PROTECTION 候选；拒绝后仍须另查 BT1→外接电源针的 PRO-C04 覆盖，不能把无保护件等同无支路。
- PU 值的 Device:R 可独立核两端脚差集，阻值仍待特定装配；battery_calculations.xlsx 不是完整 BOM，README 门磁例的 0R/10M 不代表所有变体。
- 无源 Y1 的 C1=C2=10pF 只得 CL=5pF+Cstray；NX3215SA 有6/9/12.5pF档，不套家族单一CL。RFM95W手册模块RESET=6与后文Pin7冲突，不据后文误改U2。
- 同源 U1/U2 的未知器件身份会扩成9条跨域检查；外部J1/J2/J3先供电风险另保留。SPI的NSS/RESET还须核RST-T04默认态，不因STARTUP未分组而漏掉。
- 本板134项台账均有结果，98项仍未完成；F1条款引用未齐时保留FAIL，render实际退出2。交付文件须明标执行记录，不冒充原生正式报告；add.states空数组仍是决定器/lint衔接坑。

- cellkeeper-bms--cellkeeper-hardware：1103项，357条归因，1真缺陷/50误报/15知识缺口/291待人工，3覆盖漏报；FAIL/NO_GO，802项未闭，原生renderer拒绝。
- 准确RP2354B手册PDFp17明确USB每脚27Ω；R70/R71/R127/R128=22Ω是已证条款偏离，不宣称实物必坏；主5V/非稳压隔离5V对ISO1050窗口另留待核。
- PH→L3应算真实电源；ENA别名/内部UVLO导致U3漏PWR-C06。跨类型隔离U5/U4/TR1与J9外供电支路分别补PRO-D02/PRO-C04对象，不能把漏对象当已证缺保护。
- C62是模拟差分并联滤波；AM26LV32E开路fail-safe；R6 25296nΩ=25.296µΩ，且位于系统示意。原图夹带系统/BMB示例，不当本PCB贴装。
- CAN/RS485 states=[]仍与lint冲突，分析run不等于产品合同；多地去耦return_net须group citation，U26输入C55在FB3之前不能算后段直接旁路；保留223条F1与277提示。


- rmingon--chlinknet：244项、84条归因（2真/19误/2准则/2知识/59待确认），PRO-C04/PRO-D02两项覆盖漏报；FAIL/NO_GO，原生renderer拒绝，记录勿称正式报告。
- README接口表必须与网表逐针核：本板J2.1/2实际3V3/GND，README反向；J3.4直3V3而文档有5V说法，JP1=BOOT1、JP2=BOOT0。不按README的RMII/25MHz替换实图身份。
- CH340 V3C p4未用I/O可悬空、R232内下拉；NET-A06/A07可排除但NET-A01未标NC处置仍留。HY931147C的V+/V−是整流电源，磁件RJ45不是有源PHY IC，图片手册NO_TEXT不等于缺资料。
- WCH官方CH32V30xSCH.pdf p9两CT共3V3+C14=0.1uF；G04-091不能无视千兆/集成磁件裁剪。Micro-B不能套PD/Type-C表4-2/4-3。TI LM1117输出电容/ESR在PDFp15，保护二极管在p13，勿记错页码。
- U4泛称ic候选漏UART须显式加，主控/跳线另归STARTUP再重扫；244项保留191未闭，纯晶体接口F1仍机械要求数值条款，不引用无关HSE频率凑通过。

- jasonsbeer--amiga-2000-eatx：2144项已登记、2050未完；82条归因=14真/12误/1准则/2知识/53待确认，2覆盖漏报；FAIL/NO_GO，renderer拒绝正式报告。
- 穿心EMI200/229有1-2直流通路，BAT54C为双阳极共阴极OR；勿把9条无来源提示当真实断电。HCT74/08/14 p4未用输入条款确认12脚悬空（4封装）。
- LF347物理5/12为+、6/13为-，本图标签反写但6-7实际反馈正确；总图J503电压表反写，网表1-2默认为5V、2-3为3.3V，勿指控默认板欠压。
- ShoppingList无位号，iBOM同版metadata核后还原611行可read_bom（缺RX1）；CLKVCC/负压/+VID/+AUD须定界，X1/X2和RTC互斥要列分支。
- AgnusCLK内SCLK和DIN5机械名会误触发SPI/工业DI；并行SRAM别套eMMC。DS1813无独立sense会漏对象；无保护件的风扇直供支路仍须PRO-C04枚举。

- solderedelectronics--4-channel-relay-board-hardware-design：199项，27条归因=0真/8误/0准则/2知识/17待确认，2覆盖漏报；40 PASS/22 NA/137未闭，FAIL，renderer退出2；交付为执行记录。
- NC1/COM1/NO1等同后缀干触点不是NC汇集；lint._relay_nc_contact仅认精确NC/COM/NO。继电器数字空脚名也影响隔离对象枚举，别凭浮接点无地名漏审。
- 声明Q的低侧继电器角色会被self_anchored误建POWER_CONVERTER并沿VCC收共享件；reject后仍held，不能再add这些件。保留DRV逐件检查并登记重归属缺口，不接受假变换器。
- 分号BOM先转换后read_bom，保留字段及原始摘要；PC357_OPTO家族角色可核，完整CTR档不可猜；100R在假设5V/VF1.2V时0.1444W，只是条件线索，不是实贴超额定证据。
- 光耦共GND与继电器触点隔离分开；PRO-C04仅输入LED小组不覆盖四个10R线圈支路。源保护、默认态和外部故障条件未定就留needs_human，不造VENDOR_DATUM；本板schema15且F1六项未闭。

- greatscottgadgets--urti-mainboard：1394项已登记、1277未闭；519条归因=0真/75误/0准则/41知识/403待人工，2覆盖漏报；FAIL，renderer拒绝，交执行记录。
- Q2双PNP门限/OVP被self_anchored建成变换器并带入177件；Q3/Q5仅负载开关。reject后187个held成员仍不能add回收，别靠接受假类型消缺口。
- Diodes Incorporated是厂商名；用准确标题kind_reason反证，不能改diode角色。U4固定33的ADJ/NC、MAX2120 ADDR允许悬空、HyperRAM B5/C5=RFU须核准确型号。
- EP/OGND/运放负端GND不应独立要求GND去耦；U9.17 VBUS经20k是检测脚。J4/J6支路缺PRO-C04、U15缺ANA-C01定位，已给覆盖种子。
- ECP5核心包络1.118579..1.178034V不保证1.155V推荐上限，图有意约1.15V超频；预算越界≠已证实物过压。LCSC错误PDF不记AVAILABLE，full-pinout/装配缺口不能用manual_verification绕过。

- solderedelectronics--load-cell-ampfilier-hx711-board-hardware-design：83项（76+7补查），26 PASS/7 NA/50未闭；26观察=4误报/3知识/19待人工，0真/0准则，6覆盖漏项；FAIL、valid=true、renderer退出2，交执行记录。
- 已核adc_dac不保证ANALOG_PIN通过：INNA-/INPA+/INNB-/INPB+别名令ANA-C01/C03缺实例；角色与物理通道应双重核，不能随“无ADC脚”跳过。
- HX711 BASE→PNP→AVDD/VFB属于复合稳压；C1/C2隔R5=10Ω不能当直接Cout，p6参考10u直AVDD。4.298780V仅标称；VBG保证窗缺失，未据3.3V假设指控原板。
- XI=GND时p2允许XO NC，三条输入悬空候选可排除；PWR-A01把桥激励K1.5反认外供源是INFO错误。PD_SCK高>60µs关桥激励，须另查外部主机默认态。
- 去耦components须显式确认C5/C6；分号BOM的Designation映射Value并保留原摘要；未知对端/受控输入不伪装厂家数据，普通阻容采购约束与真正稳定性资料缺口分开。

- satya777777--esp32-industrial-io-controller：376项、116条归因（3真/20误/0准则/4知识/89待定），4覆盖漏项；267未闭，FAIL，renderer退出2，交执行记录。
- 通用BCE/DGS符号与MMBT3904 BEC、TSM2309/BSS138 GSD不符；数字脚集合相同仍须核功能。1N5820=20V不适用于24V buck；USB22.1k检测节点勿作功率源。
- Q3防反和MCU→继电器被self_anchored误建变换器；reject后20件仍held，入口保护/ADC/继电器边界须独立补查，不接受假类型消归属。
- ADC2.45V是校准有效区，2.5/3V不直接判损坏；RO经2/3的3.5V保证下界仅2.333V，缺轻载保证先留待核。TVS A值/A1A2符号极性与采购分支须锁定。
- 非U位号Buck1/5-3V3需audit --require-ref；input指纹用board_intent；去耦库存改后先重冷扫。完整原厂PDF下载失败不可AVAILABLE，门禁错误与未闭项如实保留。

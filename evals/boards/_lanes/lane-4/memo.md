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

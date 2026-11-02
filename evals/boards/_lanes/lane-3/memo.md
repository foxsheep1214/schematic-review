# lane-3 逐板经验

- 2026-11-02 antmicro--rdimm-ddr4-tester：1660 项／148 发现／2 覆盖缺口，门禁 FAIL；strict 缺 U17/U24 共 8 个脚名不能用 no-strict 关闭。
- R_0R01_1206 等编码、IC1 位号及 SW_VPP/VTT 来源识别会连锁制造无驱动告警；先画路径，再判压降和额定，不全局静默。
- 电路所有权不等于规则适用范围：USB 内 Y2 仍需晶体检查；PAC1954 监测器兼有 ADC，不能因 ANALOG_PIN 未资格化就裁空。
- 原生 schema15 不能直接表达板评估 needs_human；明确保留格式 FAIL 与逐项待判，不冒充 VENDOR_DATUM，不据台账条目数声称电气证明完成。
- 桥式整流器局部符号脚号须经自定义 footprint 映射物理脚；PAC1954 地址脚及分流电阻 Value/MPN 须独立核，不信图注。

- 2026-11-02 solderedelectronics--1s-li-ion-battery-protection-hardware-design：95项／14归因（0真缺陷、5误报、0准则、5知识缺口、4待确认）／2漏报；门禁FAIL，不能将台账填全当作格式有效。
- DW01 TD允许留空；FS8205A的1/8是内部共漏极D12，NET-A01正确候选读手册后可消解，勿算检查器误报或要求外部短接。双MOS需逐通道，断OC(U2.5)不能只检查OD(U2.4)。
- R2=1k是CS保护串阻，OCP来自MOS导通压降；先取电芯/源阻抗/I(t)/温度，勿把4.35V动作点或6A器件标签当系统保证。
- 同电池焊盘/JST不是独立双源；CS不是数字接口；POWER_PROTECTION大类会误派eFuse却漏PRO-C05，battery_protector角色/资格应一起补。
- 分号BOM先无损转CSV；补C1类别/条款后重建清单并重审95项，旧lint摘要不能当当前绑定。schema15不承载needs_human/评估知识缺口时保留FAIL；纯拓扑与共享缺口的9条条款承载错误也要如实列出。

- 2026-11-02 greatscottgadgets--hackrf-pro：1632项／161归因（0真缺陷、11误报、0准则、36知识缺口、114待确认）／4覆盖漏报；37 PASS含10覆盖汇总，1561项待判，门禁FAIL。
- 排他所有权会吞晶体和输入MOS：拒绝错误POWER_CONVERTER后仍须补X2/X3 CLK-C01、Q4/Q5 PWR-T05/DRV-C02；FPGA CRESET/CDONE须进START_PIN资格。
- I2S*_SDA不是I2C；整组LED通道/Q7B三脚NC不能当悬空输入。Si5351C p23/p25明确XA外部注入时XB留空，合法候选关闭不计误报。
- 型号标题先于应用词：SN74LVC1G86的TVs不是TVS；资料分组按Value而非完整MPN时须保留后缀映射。网页摘录不等于本地完整PDF，同族XC6206不可擅换厂家。
- 先核D13符号/0Ω料号冲突和MAX5865的VDD≤3.3V、OVDD≤VDD供电边界；3.333V名义值不能替代实际压降/模式界。schema15不容needs_human时保留FAIL，不假造厂家依赖。

- 2026-11-02 solderedelectronics--fuel-gauge-bq27441-breakout-hardware-design：191项／18根因（2真、5误、0准则、4知识、7待定）／2覆盖漏报；47PASS含4覆盖汇总、127待判，门禁FAIL。
- BQ27441 BIN上拉只能到片内VDD；SDA/SCL/GPOUT推荐上拉≤3.6V，6V绝限不保证5V通信。JP1/JP2双桥与JP3默认接通须看PCB铜桥，JP4默认开路。
- K4/K5 easyC不能因K前缀成继电器；U2双MOS信号翻译不是功率管。错误POWER_CONVERTER候选reject后add改归仍被占用挡住；I2C区域已有SIG-C08，不能重复计掉电主题漏报，不编辑候选过关。
- fuel_gauge缺角色会使BAT/SRP/SRN的ADC量程被ANALOG_PIN资格漏掉；10mΩ对应±2.5A只是名义量程，BOM 1%与实际电流范围另核。
- 分号BOM无损转CSV；普通C4/JP4不是控制器手册依赖。保留schema15对needs_human/知识缺口及纯拓扑条款的FAIL，报告原样副本不等于可打包交付。

- 2026-11-02 greatscottgadgets--cynthion-hardware：1193项／319归因（0真、15误、0准则、33知识、271待判）／3目标规则覆盖漏报；144PASS+77NA、972未定，门禁FAIL。
- PMOS泛称把SIA483与YJL3401A混组；按准确MPN分组后再绑定手册。Diodes厂商名和SIA首页应用栏不能作器件标题角色，已留原件复现。
- USB3343 pin23 VDD18为片内输出；CLKOUT绑VDDIO选60MHz输入合法，13/14逻辑交换须核SwapDP/DM。HyperRAM B5/C5为RFU，别套缓存PSC输入；G/S稳压管合法双侧窗口仍须保留。
- XML字段可无损转CSV读BOM；本板13项自定义DNP，U15不贴、R54=0Ω供VCCRAM。TCR2EF115=1.15V而ECP5上限1.155V，±18mV测试VIN不同，先锁实际输出窗，勿直接报实物超压。
- PAC1954 ANALOG 0/7、Q9/Q12目标PWR-T05、FPGA配置期RST-T04是本轮覆盖缺口；CLOCK/SPI空states要有出处补run。schema15不能承载评估分类及部分声明/预判问题时如实FAIL，不编厂家参数或override。

- 2026-11-02 theushen--eegfrontier：148项／27归因（8真、6误、0准则、3知识、10待确认）／3覆盖漏报；strict成功，门禁FAIL，16个FAIL检查不是16个独立缺陷。
- XIAO模组内部USB/LDO供电须查官方整图，VBUS载板单节点不是断线；图框标题不能被内部二极管料号取代，泛称ic与复用别名会漏真正主控并把SPI锚到LED。
- ADS1299分清AVDD4.75–5.25V与DVDD1.8–3.6V，SCLK40/RESV1 31、CLKSEL52/CLK37逐物理脚核；VCAP1指定100µF、VREFP最小10µF，不能用其他网电容抵数。
- AVSS@1/@2需官方return映射；1kΩ字面明确但解析器拒读；单一地网不填decoupling.return_net，推断需求与事实文件分目录防误认。
- Top50补模块LDO有效Cout/ESR、USB Sink供电链和复位IO默认态；未实现通道终接、BIAS人体回路不确定时保留依赖。schema15不承载五类评估与部分局部约束，不能编厂家数据/条款换PASS。

- 2026-11-02 ben5049--switch-v4-hardware：1932项／200归因（3真、31误、0准则、17知识、149待定）／2类漏报；106PASS含10覆盖汇总，11FAIL归3根因，1810待判，门禁FAIL。
- SJA1105 RMII仅全双工对LAN8671仅半双工须核冲突契约；旧v4.0.0 errata的RMII接反/88Q strap在v4.1已标修复，不能继承成现版缺陷。00/01及3V3/3V9冲突须落XML实例Manufacturer_Part_Number/采购码，勿只读libsource。
- L401=U402.SW后的Buck输出电感，非5颗下游Buck的输入EMI滤波；4k7逻辑串阻不该裁断EN源。R101/R102各1MΩ经SHIELD仅2MΩ泄漏，不等于等势地，跨端口候选易过度持有；保留独立稳压级，不为过校验合并。
- MCU PF13/PF14及PA/PB的ADC复用需显式资格；TVS3301/Z前缀要逐件PRO-E02。三颗晶体已有CLK-C01；合法MODE/SHDN/BOOT/JTAG候选核原厂后关闭，不算误报。PoDL PSE≠PoE PD，VDDUSB≠USB口。
- schema15仅容VENDOR_DATUM/REVIEW_INCOMPLETE，评估needs_human/knowledge_gap及纯拓扑条款承载仍FAIL；空框图页不填虚构器件。全量派生对账成功与电气审结、格式有效、打包准出分别记。

- 2026-11-02 solderedelectronics--i2c-multiplexer-tca9548a-breakout-hardware-design：344项／26归因（0真、2误、0准则、1知识、23待定）／3覆盖缺口；71PASS+26NA、247未定，门禁FAIL。
- K前缀仍会把10个easyC当继电器：20条DRV钳位误派且40条端口专项漏掉；CLASSIFIED(reason)不能纠正已识别前缀，不能伪造继电器针表过关。
- TCA9548A缺I2C switch角色导致候选为空；用有出处add建I2C/LEVEL_SHIFT，完整PW24针表独立摘录；补POR窗口按G02-022，别误挂Top50 G03-025/PWR-T04。
- 下游16根无板载上拉不等于缺陷；10k±5%在400kHz的总Cb边界33.72pF，需计外接模块/选通并联。19个VCC供电脚共网，补PRO-C04但不机械要求每口保险丝；复位仅R4上拉，恢复可由外部电源循环。
- PWR-C09无厂商量化容量窗可NA并核接法；REQ-C01不能因做过条件算例就PASS全工况。schema15评估分类及无条款功能如实FAIL，报告快照不是有效打包/准出。

- 2026-11-02 danielmartensson--stm32-plc：1047项／78归因（1真、7误、0准则、12知识、58待定）／3类漏报、24补项；strict缺U3/U5六输出名，门禁FAIL。
- 先填明确的按图population再谈缺项：补齐后原生8 MOS+3 BJT的驱动/SOA已出现，不把审查输入没填全算检查器漏报；覆盖汇总PASS只指子项都有记录。
- 22颗ADC输入保护齐纳隔PTC/160Ω被误分功能钳位；D28三脚双路TVS被“两网”条件跳过。另20颗DI/编码器齐纳可能正常工作钳位，不能一起改判。
- D28四身份字段冲突先定料；0ZCM0001保持10mA、0ZCH0150保持1.5A/额定6V，别用30mA/Max2.5A图注保证持续20mA/2.2A。DAC100nF须分buffer ON/OFF，不能推无条件失效。
- L0/L1/L2是LED，PTC标题不含fuse不代表身份未知；普通Cout/旁路不索要无关寿命证据。schema15承载及本轮未满足的数值/条款结构错误如实留FAIL，不编厂家数据或改报告过关。

- 2026-11-02 solderedelectronics--usb-uart-ch340c-converter-board-hardware-design：175项（原生173+补2）／21归因（1真、5误、0准则、4知识、11待定）／2目标规则覆盖缺口；53PASS+20NA+2FAIL、100未定，门禁FAIL。
- CH340C 3V3模式V3必须与VCC同接3V3，单刀只切VCC不够；5V档输出VOH不是永远3V3。7/8是允许省略的NC/未用OUT，不能把差集直接报漏供电脚；批号4防反灌不可泛化旧板。
- K1/K3无源触点被生成IC去耦组，LED A/K两端空差集仍被datasheet-kind卡住；同源USB分支/排针不是独立双源。RXD串LED负载由外部TX灌，勿借U1输出能力关闭输入电平。
- 原厂SE5218需有效Cin/Cout≥1µF，2.2µF名义值要落实≥45.45%保留率；普通耐压另判。F1仅500mA不能证明PTC/熔断类型及I²t/分断；XKB针表B侧重复A号留资料歧义，不当板接反。schema15评估分类与局部结构不兼容如实FAIL。

- 2026-11-02 neotron-compute--neotron-pico：895项（5补项）／328归因（3真、77误、0准则、52知识、196待定）／5漏报对象；117PASS+3FAIL+64NA、711未定，门禁FAIL。
- NT901–NT912是DNP但有PCB铜的NetTie，不能当不贴器件断开；会制造24条地址脚告警。44条假去耦来自扩展槽、HPGND误作电源及Pico未引出的3V3/ADC_VREF输出；SPK_P/N是喇叭负载。
- Pico原厂p20有VBUS的R10/R1下拉，Q201无偏置是模组边界误报；Q1302 Ctrl驱动不应吸入全板38件RC snubber。Diodes厂名及STM32特性列表仍会误当角色标题。
- C1306 25V对30V声称窗、Q1302 PNP链到NPN资料、DS1307 0x6F旧注释分开归因。RTC 5V焊桥未证、AMS1117陶瓷稳定及BJT 30V应力未知，别硬定缺陷；ADC复用脚/codec/G-S齐纳逐对象补查。
- 无独立BOM时原生XML列可无损转CSV；strict缺U303.2/.4可手核A/Y但保留输入状态。schema15评估分类、局部条款/数值/对象范围不满足时原样FAIL，报告副本不是有效打包或准出。

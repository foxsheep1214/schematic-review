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

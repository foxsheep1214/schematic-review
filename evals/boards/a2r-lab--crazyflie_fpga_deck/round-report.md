# a2r-lab--crazyflie_fpga_deck / lane-1

Crazyflie Artix-7 100T MPC加速扩展板（用途据README推断）；三路buck PMIC、启动/配置、SPI、100MHz有源时钟，补核I2C/JTAG。MIT；固定提交 `a1405c1`；KiCad10.0.7 strict，75件/543节点，XML与db归网零差异，U1官方324球脚名全一致。

|项目|数量/结果|
|---|---:|
|计划项 / 功能框架|394（390自动+4补问）/18|
|局部已判 / 逐ID待核|82（77通过、5失败）/312|
|归因条目 / 原始警报候选|75/54|
|true_defect|2|
|false_alarm|52|
|criterion_issue|0|
|knowledge_gap|3|
|needs_human（根因，非待核项数）|18|
|Top50漏问 / 已证电气漏检|4/0|
|校验 / 报告|FAIL、NO_GO；仅诊断|

最重要的三条观察：
1. **真错须与合法接地区分**：U1.H10 VCCADC接GND违反UG480 Table1-1；未用VCCO Bank、VCCBATT及U2未用LDO接地各有允许条款。另一个真问题是X1图/BOM采购码与ASV资料链接冲突，未断言实装不兼容。
2. **合并步先修PMIC官方端口语义贯通**：VDCDCx、L1/L2/L3、DCDCx_EN、VRTC未正确进入源/开关/使能模型，造成大量无源误报、Cout和UVLO漏问；I2C SCLK/SDAT另漏上下拉计算。四处已以rule_gaps补问，未改检查器。
3. **不把名义值当保证**：三轨名义Cout为76.05/74.64/128.32µF，22µF是名义推荐而非硬最大；LM3880 EN电容是合法接法。源窗、Ceff、负载、掉电与host合同未知均留待核。

SR用法坑：CSV需映射Designator/Comment并独立对读；add并入电路丢nets/anchor可把C1或邻接U1选作PMIC主件。schema15不能表达needs_human/未完成功能；保留312逐ID与18功能旁账，绝不以报告“功能1/资料不足0”当审完。报告未有效打包，图片/record请从缓存索引打开；无效报告不作准出。UG480仅官方在线条款，Infineon完整PDF未取得，均未冒充本地全文。

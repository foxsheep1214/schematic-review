# RTC备份与外部总线的人工成对判例

来源：Sergey Kiselev `rpi_rtc_ds3231`，commit `e242486bdab0a8f3b1cf472a0b87f7bfa60f0d9c`，PCB V1.0（原SCH图框revision空），GPL3。原SCH/cache/作者网表/PCB为6器件29物理节点11网络；原厂DS3231 `19-5170 Rev10 3/15` p2–5、9–10、13–18。作者MPN为Possible sources，不能冒充核准实物。PiB Rev2 issue2.2_027 p2 R1/R2 nominal1k8；Pi4 reduced R21/R24是音频，不能移用为GPIO上拉值。

这些是已有判据的人工适用性案例，不新增型号豁免、统一寿命指标或自动打分器。使用原件/同冻结图表先判正确分支，再判明确标记的本地合成分支；未给全角资料的对象仍待核，不能以判例文案替代数据手册、逐项审查或实测。

|实际问题/已有判据|原件与可判正确范围|合成真实故障或真实缺证分支|
|---|---|---|
|名为NC的物理脚不能按名称决定悬空：DEV-D02/D05|U1.5–12全部GND，原厂要求mustground；32kHz1/RST4另各有原NoConn，32k未用可open，RST内部50k不额外加pull。|本地把5从GND改成悬空：FAIL具体NC5必接地条款；不能援引普通NC豁免。只看符号名字/缺脚表：INSUFFICIENT，不假定接地或悬空皆可。|
|备用/主供模式分别核去耦：PWR-D01/D02/T03/C09/C10|C1=100n名义VCC/GND；VBAT为CR2032backup，原厂明确无需电容，零电容组保留；其容量/额定项NA。|本地改为VBAT唯一primary供电且没有0.1–1µF低漏电容：按primary条款核缺失，不能复用backup的NA。名义0.1µF推荐不等于任意全角有效100nF保证阈值。|
|首次电池接入与已初始化备份不同：RST-T01/T03/T04、CLK-D03|首次只装cell有意等待VCC>VPF或合法I²C地址写入，不能报振荡器不启动缺陷；正常备份要EOSC0、有效VBAT并检查OSF。|本地令EOSC1却仍要求失主供计时：FAIL该配置；100nA保持电流是停振数据保持，不能当低功耗计时。ACK0x68不证明时刻可信。|
|外部上拉与保证总线窗口不同：SIG-T02/E01/C01/C07/D01|Pi GPIO2/3外部fixedpullup有官方证据，本体无上拉不等于漏焊。参考1k8±1%、400pF给tr约616ns，满足100k的1µs上升窗口；±1%仅有界模型不是Pi全型号保证。|本地要求400k且CB保证400pF、同Rp：616ns>300ns，FAIL该窗口；若actualhost/Rp容差/CB/frequency不确定则INSUFFICIENT，不能以芯片支持400k判全链PASS或FAIL。额外上拉必须计并联，不盲目加。|
|一次cell无充电支路与备用脉冲能力不同：CLK-D03、DEV-C05、PWR-C01|原BT1+/−正确、无VCC到VBAT外charger；原厂说明对primarylithium防反充。不能套其他DS3231模块的charging电路缺陷。|575µA温度转换脉冲下VBAT需≥2.3V；225mAh额定到2.0V/20°C/0.2mA和3µA平均相除不能证明保证年数。未提出寿命指标不造FAIL；实际温度/老化/cell+holder压降未绑定则局部INSUFFICIENT。|
|共享主机电源掉电斜率与小电容独占hold-up不同：RST-T03、REQ-D01|VCC直接接Pi共享3V3；DS要求2.70→2.45V最短300µs。缺host保证V(t)保留本地待核，不能按RTC µA负载单独算C1后宣布主机拔电保持。|本地有保证100µs下降：FAIL此时序；有保证500µs：此单判据PASS（不替代VBAT资格）。隔离+hold-up建议须按输入压差/门限/最大负载/充放路径重算，不能拍脑袋加C。|
|原生工具退出状态与导出完整性不同：DOC-Q01、G6/G7|本旧KiCad4输入在KiCad10导出exit0但零器件/网络、PDF无符号，严格导入拒绝；原图/cache/authornet/PCB交叉并只读适配有边界地恢复完整审查。|空导出不能作为clean ERC/全板PASS。适配若任一真实物理节点分区或值不同必须停止并核原件；不得用重命名NC网改变真连接，安装孔镀通属性也不能改述NPTH。|
|物理归网正确与库电气类型正确分别核：DEV-D04/DOC-V01|本版SCL16归网正确，但electrical type openCol不同于原厂Serial Clock Input；RST4仅input未表达开漏I/O：P2库类型数据错。shape C是合法Clock，I/CI才反相，不能误报图形缺陷；只读适配保持原类型。|本地新库SCL16改input/合法Clock、RST4开漏I/O说明，全部脚号和归网不变：复验可关闭资料缺陷；不能从Clock三角推硬件实际反相，也不偷改适配类型称原库PASS。|

保留价值：上述分支区分物理脚条款、使用模式、初始化状态、外部系统数据与工具输入质量，避免不必要加料、漏掉备份保持条件或把未知负载当失败。电气阈值未改；外端三条局部判据的PASS拦截策略改变，external-port及全部对象/工况仍保留。初审冻结台账逐项结论、valid和NO_GO前后回放等价，计划须按各引擎重生且指纹不同，不声称JSON字节等价，更正后的同一冻结台账旧引擎六个硬拒、新引擎valid且NO_GO；全量新台账重审和边界回归分别验证。初审漏检/不必要待核的人工纠正单独归因于证据审核，不能把允许有据局部判断、前后等价、回归或共识当自动准确率指标。

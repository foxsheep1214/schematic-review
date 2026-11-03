# Top 50 逐项漏报核对

按机制逐项核网表，覆盖、计划漏问与硬件缺陷分开。四个misses均通过intent.rule_gaps补问；没有将未知工况写成原板电气缺陷。

|序号|准则|结论|位号/网络与依据|
|---|---|---|---|
|1|G01-018|not_applicable|唯一源接口为低压deck J2.9 VBUS，U2为低压buck；无-48V/交流入口、整流桥或市电保持机制。industrial_telecom基线不能自动创造这些供电场景。|
|2|G01-019|not_applicable|唯一源接口为低压deck J2.9 VBUS，U2为低压buck；无-48V/交流入口、整流桥或市电保持机制。industrial_telecom基线不能自动创造这些供电场景。|
|3|G01-020|not_applicable|唯一源接口为低压deck J2.9 VBUS，U2为低压buck；无-48V/交流入口、整流桥或市电保持机制。industrial_telecom基线不能自动创造这些供电场景。|
|4|G01-021|not_applicable|唯一源接口为低压deck J2.9 VBUS，U2为低压buck；无-48V/交流入口、整流桥或市电保持机制。industrial_telecom基线不能自动创造这些供电场景。|
|5|G01-022|not_applicable|唯一源接口为低压deck J2.9 VBUS，U2为低压buck；无-48V/交流入口、整流桥或市电保持机制。industrial_telecom基线不能自动创造这些供电场景。|
|6|G01-023|not_applicable|唯一源接口为低压deck J2.9 VBUS，U2为低压buck；无-48V/交流入口、整流桥或市电保持机制。industrial_telecom基线不能自动创造这些供电场景。|
|7|G01-024|not_applicable|唯一源接口为低压deck J2.9 VBUS，U2为低压buck；无-48V/交流入口、整流桥或市电保持机制。industrial_telecom基线不能自动创造这些供电场景。|
|8|G01-025|not_applicable|唯一源接口为低压deck J2.9 VBUS，U2为低压buck；无-48V/交流入口、整流桥或市电保持机制。industrial_telecom基线不能自动创造这些供电场景。|
|9|G01-026|not_applicable|J1/J2为Crazyflie deck排针，J3为JTAG；无USB连接器、USB数据或PD端点。VBUS网络名本身不证明USB Sink/Source，不套100uF、40ms或vSafe5V。|
|10|G01-027|not_applicable|J1/J2为Crazyflie deck排针，J3为JTAG；无USB连接器、USB数据或PD端点。VBUS网络名本身不证明USB Sink/Source，不套100uF、40ms或vSafe5V。|
|11|G01-029|not_applicable|J1/J2为Crazyflie deck排针，J3为JTAG；无USB连接器、USB数据或PD端点。VBUS网络名本身不证明USB Sink/Source，不套100uF、40ms或vSafe5V。|
|12|G01-030|not_applicable|J1/J2为Crazyflie deck排针，J3为JTAG；无USB连接器、USB数据或PD端点。VBUS网络名本身不证明USB Sink/Source，不套100uF、40ms或vSafe5V。|
|13|G01-031|not_applicable|J1/J2为Crazyflie deck排针，J3为JTAG；无USB连接器、USB数据或PD端点。VBUS网络名本身不证明USB Sink/Source，不套100uF、40ms或vSafe5V。|
|14|G03-003|plan_miss_recovered / M01|三路内部补偿buck输出均有L/C，原生not_asked SWITCH_PIN漏C04；PWR-C09不是C04稳定窗口。已加PMIC-COUT，Ceff/ESR/负载未知故无已证电气漏检。|
|15|G03-004|plan_miss_recovered / M01|三路内部补偿buck输出均有L/C，原生not_asked SWITCH_PIN漏C04；PWR-C09不是C04稳定窗口。已加PMIC-COUT，Ceff/ESR/负载未知故无已证电气漏检。|
|16|G03-016|not_applicable|板上无离散通路/防反MOSFET与栅源网络；L1..L3是PMIC内部同步buck储能电感，不是外部线性通路FET。内部器件工作资格仍归U2工作条件/保护条款。|
|17|G03-018|plan_miss_recovered / M02|DCDCx_EN及内部UVLO应进入C06，原生not_asked PROTECTION_PART漏问；已加PMIC-UVLO。未知真实VBUS/线阻，尚不能确认阈值/滞回违反。|
|18|G03-019|plan_miss_recovered / M02|DCDCx_EN及内部UVLO应进入C06，原生not_asked PROTECTION_PART漏问；已加PMIC-UVLO。未知真实VBUS/线阻，尚不能确认阈值/滞回违反。|
|19|G03-021|plan_miss_recovered / M03|400..1000us的5%-95%软启动及76.05/74.64/128.32uF名义容量构成机制；原生没有PWR-D03，已补PMIC-START-CURRENT。平均电容电流演示不作为瞬时峰值或限流保证。|
|20|G03-025|covered_pending|PWR-T04.DRAWN.SUPERVISION-RAILS已问各轨监测；U1内部POR、U2RESPWRON未用、PROGRAM_B上拉已核。掉电斜率/复位意图未知；不是未问或缺监控器即硬错。|
|21|G03-028|covered_pending|原生PWR-C24.POWER-CONVERTER-U2.C1已问（主体C1误选另归工具），U4FLAG1/2/3顺序实际连接明确。按极值时间与掉电/再启动检查尚待host源轨迹，不新增重复漏报。|
|22|G03-032|covered_pending|PWR-C05 startup/run/fault已问反流和预偏置。J3.1可能是参考也可能外供，必须锁定工具方向；未知状态不等于已证明反灌损坏。|
|23|G03-037|not_applicable|本图C均为无极性Device:C及0402/0603封装，直接返回GND或EN到GND；没有串联极性电解/钽均压机制。准确采购档位/耐压另在DEV-C01/D04，不从符号推定实物已验收。|
|24|G03-038|not_applicable|本图C均为无极性Device:C及0402/0603封装，直接返回GND或EN到GND；没有串联极性电解/钽均压机制。准确采购档位/耐压另在DEV-C01/D04，不从符号推定实物已验收。|
|25|G03-040|not_applicable|本图C均为无极性Device:C及0402/0603封装，直接返回GND或EN到GND；没有串联极性电解/钽均压机制。准确采购档位/耐压另在DEV-C01/D04，不从符号推定实物已验收。|
|26|G04-005|covered_pending|原生SIG-C08逐J1/J2/J3以及跨电路接口已问掉电注入/绝限。内部PMIC I2C4k7路径计算另补C01，不把已有SIG-C08误报成全轮漏审。|
|27|G04-007|covered_pending|原生SIG-C08逐J1/J2/J3以及跨电路接口已问掉电注入/绝限。内部PMIC I2C4k7路径计算另补C01，不把已有SIG-C08误报成全轮漏审。|
|28|G04-009|covered_pending|原生SIG-C08逐J1/J2/J3以及跨电路接口已问掉电注入/绝限。内部PMIC I2C4k7路径计算另补C01，不把已有SIG-C08误报成全轮漏审。|
|29|G04-010|covered_pending|FPGA-CONFIG和SEQUENCER已有RST-T04 power-on/restart；PUDC_B直连高、EN有内部电流源+C31、FLAGS接EN且有100k上拉。实际外部host安全态和上电次序未知，保留待核。|
|30|G04-017|plan_miss_recovered / M04|外部/SDA/SCL已问C01；内部/SCLK_PWR与/SDAT_PWR因非SCL/SDA拼法未进入拓扑，实际U2.30/.29各4k7上拉。已补PMIC-I2C-RC，Cb/模式/IOL保证待定。|
|31|G04-018|plan_miss_recovered / M04|外部/SDA/SCL已问C01；内部/SCLK_PWR与/SDAT_PWR因非SCL/SDA拼法未进入拓扑，实际U2.30/.29各4k7上拉。已补PMIC-I2C-RC，Cb/模式/IOL保证待定。|
|32|G04-032|not_applicable|无CAN收发器、CAN_H/L或CAN端接网络；数字SPI/I2C不套60ohm。|
|33|G04-040|not_applicable|全板一个GND，无隔离器或隔离DC/DC；未用VCCO接地不构成跨隔离短接。|
|34|G04-041|not_applicable|无外部运放/比较器模拟反馈输入；LM3880内置EN比较器是启动门限对象，已由RST-E01/RST-C02承接，不能套外部运放共模。|
|35|G04-054|not_applicable|U1专用VP/VN与VREF均接地，没有用于外部测量的ADC输入分压；VCCADC错误已由PWR-A02/DEV-D05确认，属于专用脚供电接法，不冒充ADC满量程漏检。|
|36|G04-078|not_applicable|X1为4脚有源100MHz振荡器，OUT只接U1.P17 MRCC；无晶体两端/XI-XO和负载电容/多个Pierce有源回路。CLK-D01已问源的频率/电平；X1身份冲突另列真资料缺陷。|
|37|G04-079|not_applicable|X1为4脚有源100MHz振荡器，OUT只接U1.P17 MRCC；无晶体两端/XI-XO和负载电容/多个Pierce有源回路。CLK-D01已问源的频率/电平；X1身份冲突另列真资料缺陷。|
|38|G04-082|not_applicable|X1为4脚有源100MHz振荡器，OUT只接U1.P17 MRCC；无晶体两端/XI-XO和负载电容/多个Pierce有源回路。CLK-D01已问源的频率/电平；X1身份冲突另列真资料缺陷。|
|39|G05-019|covered_pending|最终原生PRO-C04已有J2.9主支路、经R26的VCC支路及J3.1分支；逐源保护是host能力合同待核，当前没有计划漏问。|
|40|G05-022|covered_pending|DEV-C01逐器件与DEV-C04逐连接器已问；PMIC额定/限流与host故障电流和连接器实际资格不能互代。电流合同未给，尚无已证过流漏检。|
|41|G05-025|not_applicable|无板上熔断器及离散通路FET时间电流/分断配合对象；上游源保护覆盖已由PRO-C04追问，不能凭不存在的F1要求板内TCC曲线。|
|42|G05-030|not_applicable|全器件清单无TVS/齐纳/反向阻断前单向TVS，D1..D3是串阻LED；接口ESD/误接边界仍由PRO-D03/D04保留，不能伪造一个TVS钳位/反向短路缺陷。|
|43|G05-031|not_applicable|全器件清单无TVS/齐纳/反向阻断前单向TVS，D1..D3是串阻LED；接口ESD/误接边界仍由PRO-D03/D04保留，不能伪造一个TVS钳位/反向短路缺陷。|
|44|G05-032|not_applicable|全器件清单无TVS/齐纳/反向阻断前单向TVS，D1..D3是串阻LED；接口ESD/误接边界仍由PRO-D03/D04保留，不能伪造一个TVS钳位/反向短路缺陷。|
|45|G05-040|not_applicable|板上无离散通路/防反MOSFET与栅源网络；L1..L3是PMIC内部同步buck储能电感，不是外部线性通路FET。内部器件工作资格仍归U2工作条件/保护条款。|
|46|G05-041|not_applicable|板上无离散通路/防反MOSFET与栅源网络；L1..L3是PMIC内部同步buck储能电感，不是外部线性通路FET。内部器件工作资格仍归U2工作条件/保护条款。|
|47|G05-048|not_applicable|无板上熔断器及离散通路FET时间电流/分断配合对象；上游源保护覆盖已由PRO-C04追问，不能凭不存在的F1要求板内TCC曲线。|
|48|G05-054|covered_pending|PRO-D04逐J1/J2/J3已问故障和误接；J2.9直入VBUS，需平台防误插/反接合同和上游覆盖才能判。未给需求不直接判板缺防反。|
|49|G05-057|not_applicable|全器件清单无TVS/齐纳/反向阻断前单向TVS，D1..D3是串阻LED；接口ESD/误接边界仍由PRO-D03/D04保留，不能伪造一个TVS钳位/反向短路缺陷。|
|50|G05-087|not_applicable|板上无离散通路/防反MOSFET与栅源网络；L1..L3是PMIC内部同步buck储能电感，不是外部线性通路FET。内部器件工作资格仍归U2工作条件/保护条款。|

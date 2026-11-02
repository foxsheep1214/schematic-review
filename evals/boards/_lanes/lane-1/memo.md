
- antmicro--jetson-agx-thor-baseboard：67候选/89决定→49电路，13个空states使候选重扫FATAL；保留失败intent，诊断回退不可声称完整计划，先修CANDIDATE_STATES契约。
- 封装化R_0R001/R_0R值未解析会切断电源树；SiC437从SW→L→毫欧R追源，VOUT pin18是sense；开漏PGOOD/FLG并联不要当推挽争用。
- DNP须按db.parts.nc排除实际断供；FMC+的B01/C01/E01不是BJT。MAX16013允许EN接VCC，supervisor→MOS→C→PB_IN可用于模拟按键，需分离功能与时序证明。
- Top50先核前提：CAN逻辑脚不要求物理总线端接，有源振荡器不套晶体CL；D2反接风险须锁接口合同。D54的3.6V工作窗与约5V按钮上拉不匹配已证；不要用6.7V典型击穿豁免。
- 原生results schema15无needs_human枚举；逐项保留pending_checks并让覆盖门禁FAIL，别伪造VENDOR_DATUM/PASS；用途推断及无BOM/无受控输入窗须写明。

- solderedelectronics--rs-485-transceiver-breakout-hardware-design：KiCad10.0.7 strict成功；76项逐项分流，16局部结论/60待人工，原生门禁FAIL；0确认硬件缺陷，7归因=3建议误触发+4观察，2漏问非确证硬件漏检。
- SN65176B标题仅Differential Bus Transceivers，role-bus需有据add；add默认空states会被lint拒绝，可用其正式states字段写手册工作态；add仍丢失nets/anchors，别手改生成circuits。
- 原生零脚FIDUCIAL/HOLE仍触发NEW_DEVICE_KIND三条；K2外部逻辑侧无SIG-C08，使G04-005/009未展开，不能拿A/B掉电低负载说明替代D/R/DE//RE的注入资格。
- 20k+120Ω偏置理想仅约15mV，外部bias未定保留needs_human；CAN60Ω条款不套RS485。分号CSV/Designation需可追溯转换再read_bom；普通阻容和指示LED不因无专属手册一律阻断。

- oresat--oresat-c3-hardware：13候选/27决定→24电路，CAN-U8/U39空states使带候选lint FATAL；保留原生失败，954项仅诊断回退，48局部结论/906待核，门禁FAIL。
- OSD335x-SM p7有内置4.7k上拉，p24允许未用VIN_BAT接BAT_SENSE，p25的SYS_VDD_1P8V是输出；SiP多物理球不能重复算独立缺陷。
- RF PA/LNA的输出偏置/匹配电感不套续流线圈；MAX941 SHDN接V+合法，TPS25962x物理8脚是可开路OVCSEL，别套63x OVLO。
- I2C_HINT不能吞整页层次名：本板多5个LED/电源/栅控伪段；title_text全首页把普通缓冲器ESD Protection误识为TVS。严格解析实际因21个功能脚无名，非全引脚名称比例。
- U1/U9 PART与VALUE的容量/温度档冲突是数据缺陷，不证明实物错误；radio域SPI掉电注入漏问需状态/Ioff合同，未给条件不把原板当种子正例。

- greatscottgadgets--amalthea-hardware：41器件/10 DNP、strict成功；catalog误标调试板，实为RF/SPI/LVDS夹层；162项，51局部判/111待人工，门禁FAIL，18根因=9误报+5知识缺口+4人工，3计划漏问非硬件漏检。
- RF Balun不套DRV续流、RF RFP/RFN不套数字共模/100Ω端接；AT86RF215 p23已有内部100Ω，TX两线各47Ω要按源阻抗/模式预算，不能见缺外置端接即FAIL。
- TCXO经0Ω入TCXO且XTAL2经0Ω接地符合AT86RF215 p68；C3/R1 DNP别算负载。U2被Crystal封装误归无源晶体，器件审计还漏掉其准确手册。
- 片内AVDD0/AVDD1/DVDD各1µF，p188允0.1–10µF，名义合窗不证明Ceff；输出稳定性、主机高阻默认态和外部信号掉电注入仍要专问。手册首页“3 female SMA connectors”描述评估板，别据全页识别成connector。
- schema15仍不能表达needs_human/未定需求：逐项pending与逐功能范围单独保留，原生报告统计仅已判，勿把“资料不足0”作审完；不为有效门禁编开项或功能PASS。

- sparkfun--sparkfun_gnssdo：353器件，30候选/70决定→37电路；8个CLOCK/ETHERNET/LEVEL_SHIFT空states阻断，824项仅诊断回退；83局部已判/741待核，21归因=2真+14误报工具+2知识+3人工，3分层漏问，门禁FAIL。
- A.1/B.1/C.1/D.1是合法点号ref；用XML独立ref/pin核1151节点零归网差异，别按首个点拆。KSZ8041 pin2是内部1.8V输出；LTC4418 pin9 CAS是输出，不是输入-only。
- U4 RMII未用TXD2/3（26/27）须接地，NC是已证接法偏离；AP7361C保证输出1A，1.5A是限流typ，图面Imax不得混用。输出LC不套DRV续流，PCA9306的200k VREF2/EN偏置不是缺供电。
- USB主VBUS二极管/PTC支路名义107.8µF绕过OCXO软启动；PCA9306双侧2.2k低态条件合计3.409mA，最弱IOL仍要保证。三脚JP和pass-FET未入I2C模型是自动模型缺口，通用人工条款已存在，别夸成整轮漏检。
- 隔离DC/DC不能把全部脚并查集合域；PoE返回与DC_IN回线分开。OCXO手册400Hz保持原文；LTC4418只有官方文本摘录时别声称完整PDF。schema15的pending要显式说明，资料不足0不代表741项审完。

- vadivelvaishnavi--transformer_less_power_supply_kicad_pcb_design_project：容降全桥7805，18件/9网；100项、31局部判/69待人工，10归因=1数据真缺陷+3误报+1资料+5人工，1源侧保护计划漏问，门禁FAIL。
- 无FUSE/MOV/NTC词且全件归POWER_CONVERTER，会漏PRO-C04逐源支路；add不能跨类型借已有owned，勿手改circuits或把缺上游合同直接判硬件FAIL，先修计划覆盖。
- Vishay 1N4001首页应用脚注bridge rectifier不是器件类型；DIN0207是电阻封装不是工业DI；Device:C/矩形封装不能直接推出MLCC或已确认薄膜技术。
- 稀疏检出可漏BOM，按固定commit另取到缓存；read_bom没保留Value时独立CSV对读。7805无需Cout稳定不等于大Cout反灌/输入短路已闭合，市电峰值也不能直接充当桥单管常态反压。
- schema15未支持needs_human时留逐ID pending并保留FAIL；资料不足0仅统计已判。D5/D6未给VZ/MPN是关键设计值缺失；家族手册AVAILABLE不能冒充采购温度/后缀资格。

- groupgets--kimchi-micro：311件/393网，KiCad10.0.7 strict；18电路/60框架，补U4完整针表后1337项，39局部已判/1298逐ID待核；36归因=2真+7误报+18知识+9人工，2分层漏问，门禁FAIL。
- LFS BOM/PDF须取真实对象并校验OID；BOM311件匹配不表示VALUE/Mfgrpart无内部冲突。U3显示256M32而采购512M32是数据真缺陷，缓存符号名本身不算。
- BD71847AMWV p110 MUXSW输出需有效11–33µF，本板NVCC_SD2仅1.22µF；卡VDD另接3V3，不能借卡电容补。BUCKx_FB/LDOx_VOUT/MUXSW_VOUT未展开PWR-C04；已有PWR-C09人工发现要与自动漏报分层。
- NVCC供电轨要同时声明i2c_topology.rails，否则四路SDA/SCL经4.7k上拉串成两区；NVCC_I2C仍误作信号。R55 Populate=DNP仍被扫成下拉；MIC94164是负载开关，别索取LDO dropout。
- schema15的pending不是原生INSUFFICIENT；原生报告会显示局部功能合格与资料不足0，必须显式列出全部未判ID和报告不可用状态。未核官方针表的PWR-T03不以XML自洽冒充完整分组PASS。

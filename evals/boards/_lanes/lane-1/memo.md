
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

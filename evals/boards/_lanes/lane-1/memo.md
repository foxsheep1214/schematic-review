
- antmicro--jetson-agx-thor-baseboard：67候选/89决定→49电路，13个空states使候选重扫FATAL；保留失败intent，诊断回退不可声称完整计划，先修CANDIDATE_STATES契约。
- 封装化R_0R001/R_0R值未解析会切断电源树；SiC437从SW→L→毫欧R追源，VOUT pin18是sense；开漏PGOOD/FLG并联不要当推挽争用。
- DNP须按db.parts.nc排除实际断供；FMC+的B01/C01/E01不是BJT。MAX16013允许EN接VCC，supervisor→MOS→C→PB_IN可用于模拟按键，需分离功能与时序证明。
- Top50先核前提：CAN逻辑脚不要求物理总线端接，有源振荡器不套晶体CL；D2反接风险须锁接口合同。D54的3.6V工作窗与约5V按钮上拉不匹配已证；不要用6.7V典型击穿豁免。
- 原生results schema15无needs_human枚举；逐项保留pending_checks并让覆盖门禁FAIL，别伪造VENDOR_DATUM/PASS；用途推断及无BOM/无受控输入窗须写明。

- solderedelectronics--rs-485-transceiver-breakout-hardware-design：KiCad10.0.7 strict成功；76项逐项分流，16局部结论/60待人工，原生门禁FAIL；0确认硬件缺陷，7归因=3建议误触发+4观察，2漏问非确证硬件漏检。
- SN65176B标题仅Differential Bus Transceivers，role-bus需有据add；add默认空states会被lint拒绝，可用其正式states字段写手册工作态；add仍丢失nets/anchors，别手改生成circuits。
- 原生零脚FIDUCIAL/HOLE仍触发NEW_DEVICE_KIND三条；K2外部逻辑侧无SIG-C08，使G04-005/009未展开，不能拿A/B掉电低负载说明替代D/R/DE//RE的注入资格。
- 20k+120Ω偏置理想仅约15mV，外部bias未定保留needs_human；CAN60Ω条款不套RS485。分号CSV/Designation需可追溯转换再read_bom；普通阻容和指示LED不因无专属手册一律阻断。

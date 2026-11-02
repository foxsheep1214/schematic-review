
- antmicro--jetson-agx-thor-baseboard：67候选/89决定→49电路，13个空states使候选重扫FATAL；保留失败intent，诊断回退不可声称完整计划，先修CANDIDATE_STATES契约。
- 封装化R_0R001/R_0R值未解析会切断电源树；SiC437从SW→L→毫欧R追源，VOUT pin18是sense；开漏PGOOD/FLG并联不要当推挽争用。
- DNP须按db.parts.nc排除实际断供；FMC+的B01/C01/E01不是BJT。MAX16013允许EN接VCC，supervisor→MOS→C→PB_IN可用于模拟按键，需分离功能与时序证明。
- Top50先核前提：CAN逻辑脚不要求物理总线端接，有源振荡器不套晶体CL；D2反接风险须锁接口合同。D54的3.6V工作窗与约5V按钮上拉不匹配已证；不要用6.7V典型击穿豁免。
- 原生results schema15无needs_human枚举；逐项保留pending_checks并让覆盖门禁FAIL，别伪造VENDOR_DATUM/PASS；用途推断及无BOM/无受控输入窗须写明。

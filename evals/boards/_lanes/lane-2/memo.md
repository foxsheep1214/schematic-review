
## antmicro--stm32h7-hdmi-board（2026-11-02）
- 原库 value 可是 R_0R_0402；真实 Val/Voltage 在原 XML 自定义字段。先核字段，不能把未解析 0Ω 供电桥当断供。
- 钳位注入路径须过滤 dnp；R150/R218/R333/R338 不贴时不构成到主电源的限流路径；单 IC 无测试点也不能推定有夹具。
- 候选沿公共电源收进错误接口时，先做合法 merge/own；本板剩 J2/J13 不能诚实归属，保留失败并明确无候选回退，别为过门禁乱选。
- Top50 要逐条留适用范围：SDR 不等于 DDR，PoE 不等于负48V；D22 9V TVS及C139/C140 10V MLCC均不满足图示15V模式，后者补作 M01。

## solderedelectronics--io-expander-mcp23017-breakout-hardware-design（2026-11-02）
- easyC-SMD的K1/K3会按K前缀误读relay；须核五脚与封装证据，漏掉EXT电源口/PRO-D04是覆盖遗漏，不能自动指控缺防反。
- U2电平转换仍会被建POWER_CONVERTER候选；reject后held不释放，勿为归属硬接受，保留U2/R1-R4独立审查。
- 自定义0603C先补decoupling.components和真实connection条款重扫；不要把输入缺声明写成去耦误报，EN=VIN供电LINK也不应套逻辑链。
- 10k双侧上拉要相加灌流并区分实际Cb/速率；DS20001952D针图在p11，GPA7/GPB7仅输出，旧页码/0.4V@3mA保证不能照搬。
- boards的needs_human与原生schema15终态不兼容：本轮显式扩展遭265条拒收，保留FAIL/无效报告，不伪造需求答复或厂家数据；38为逐报告项归因数，非38个硬件故障。

## antmicro--cm4-baseboard（2026-11-02）
- 公共VCC让C302–C307进入3个独立buck候选，own不解除held；35个“最多两电路”错误须保留，不能硬并电源级。无候选合并清单只能作明确受限记录。
- XML Val/DNP比Value封装串可靠：R3贴/R4不贴；R919=0Ω、FB902/FB903供源别漏。AP62600.9是内部VCC，TXB未用A/B匹配对同接地合法。
- I2C_ADR0/1不是SDA；未知IC扩散可带进RESET/FB/LED、电源和93AA66 Microwire，先核真实SDA/SCL端点再套框架。
- PWR-C26已问D301防反前TVS，CLK-C01已问晶体负载；源/寄生/手册不齐时保留未决，不把候选或教学参数计作缺陷/漏报。NEEDS_HUMAN原生仍拒收，FAIL报告不能交冻结。

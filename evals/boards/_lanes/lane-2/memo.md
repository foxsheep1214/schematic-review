
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

## leonardoward--dpp-architecture-pcb（2026-11-02）
- KiCad6 BOM先去元数据前导、Reference(s)改Reference并留转换记录；裸2200要按准确228CKS050MQW原表读成2200uF，不能猜单位。
- Q1清单把R2→GND上的J2/J3当地驱动却漏U1.4 OUT*→R1；同时D1+C1误叫RCD，须先锁真实供入轨与栅极输出脚义。
- 被动T1不能套数字隔离器默认态/码率/CMTI；5+6、7+8本就须并接，R3/R4=0ohm不构成短错绕组。M01是实际U1/Q1默认态对象/状态漏问，非已证烧毁。
- T1只取到原厂p1网页文字、完整PDF403，AVAILABLE不等于全针图齐；needs_human原生仍不支持，保留FAIL（本板109项），不编工况/安全态过门禁。

## rmingon--rs485-spy-injector（2026-11-02）
- RS485候选states=[]：决定器可成功，lint却拒空状态；先保留失败链，再明确受限回退，不造需求加run；合并步先补CANDIDATE_STATES。
- BSS138应用段MOSFET gate drivers会触发标题冲突；Q1.3漏极也被ESP32_EN网名当输入。先读G/D/S和四种RTS/DTR状态，3.3V不等于低于4.5V就失败。
- Conn_02x08配SW_DIP_SPSTx08是内部拨码，不能当4个独立外口；ETH1–8无PHY，不是以太网；仍须留触点配对/允许拨码表缺口。
- CH340 v3C p4允许未用I/O悬空；CC开路不能只补NC。10k/120ohm偏置19.68mV需结合外部偏置，不作全现场必错；needs_human/schema15冲突保留FAIL。

## nabucasa--yellow（2026-11-02）
- KiCad10 XML可把PCB独立+3V3/+3.3VP、GND/GNDS并网；先比固定PCB pad net，不把图板/版本语义矛盾判为原板短接；版本根因未锁。
- FE1.1 VS_PLL/VS_A是地，BAT54C要展开双二极管，M.2触点不是第二驱动器；CM4 SCL0/SDA0和HDMI DDC已有1.8k上拉。
- U25为DNP替代RTC且图面明确只装一颗；Y1/Y2仍应有CLK-C01，不能因被USB/I2C电路持有而吞掉时钟问题；Type-A不能套Type-C Source未附着断电。
- add可显式填有依据的run（勿伪造需求），默认空状态会被lint拒；needs_human/schema15、DEV-D05.M1重复及输入依赖保留FAIL，164为提示+任务归因，非硬件故障数。

## solderedelectronics--connect-programmer-hardware-design（2026-11-02）
- K1/K2被分类器识别为connector也可能产生IC去耦组；无源触点不能套本体去耦，入口电容/载流另审。
- Q1/Q2是RTS/DTR交叉发射极逻辑NPN；00/11释放、01拉IO0、10拉RESET。DRV-A03原提示已问高阻默认态，别因RST-T04只问LDO就重复算漏报。
- F1被USB候选收走后没有PRO-C01/PRO-C05；500mA标签既非USB取电许可，也非保证动作点/分断能力。外部UART未知供电域仍欠SIG-C08结构化计算。
- 同版OUTPUTS BOM/PDF需从固定提交另取；分号BOM转逗号、保留原始hash，25/25读入。CH340C允许未用I/O悬空且内置时钟，SE5218 EN=VIN合法。
- 原生needs_human/schema15仍拒收；本轮242记录错误如实FAIL，75为50报告项+25已关闭问题，唯一硬结论是P3电源符号编号，非电气硬故障。

## pionixpublic--cb-eval-board（2026-11-02）
- AMC3311同时有隔离放大/隔离DC-DC角色；domains把U6多地归并是假模型，别把DC_ISO_GND改接GND。按p3侧别、p26返回组补声明再审。
- TPS27S100 EN与171023801 ENABLE被当linear会错出10项PWR-E02且漏PWR-D03；内置SS不用外露SS脚也要问充电电流+启动负载。
- U1采购码是Amphenol座，ADC3真实功能在自定义模组脚；R25/R26需逐通道ANA-C03。+24V外引/可供入触点也要从轨枚举PRO-C04，别仅围已见保护IC查。
- U8 DNP、H孔、VBUS NC、PT1000桥和MDI磁性先分清；TMP100框图Diode/逻辑门ESD段不是标题。PT1000双臂加载须联立节点，不能直接串联分压。
- 同版BOM244件，两副本hash相同；PDF按图框Id非物理次序。原生不接NEEDS_HUMAN/未定级，FAIL如实保留；175条归因不是175个硬故障。

## mlab-modules--usbi2c01（2026-11-02）
- X前缀可把CP2112/USB_B/单脚M3安装孔全当晶体，P1 POJISTKA_1812保险被当外口；audit需显式--require-ref X1，否则现有手册也漏收。
- D4多通道SP1001有3活线+公共地+NC；protected_net要求整颗两网会错出PRO-C02且漏PRO-E02，改kind本身不能解；脉冲残压与直流绝限不能硬比。
- C4 VPP是编程泵节点，5.25V供电簇封顶错误，手册窗口可到7.2V；VDD网名3.3V实际3.3–3.6V，LDO100mA含芯片与LED，外部预算另算。
- SV1/SV3帽状态别猜；SDA/SCL无板内Rp也可能由外板供，GPIO复位默认输入须重配。BOM串接位号仅补分隔符后26/26；USB-B别套Type-C/PD限值。
- add/add同持有的own不能指向无candidate_ids电路且nets为空；NEEDS_HUMAN/schema15等记录限制保留FAIL。58是归因数、7是覆盖漏项、已证硬故障0；完整台账在缓存，报告未打包。

## newell--nixie-clock-esp32c3（2026-11-02）
- README硬件许可优先核：本板MIT仅软件、硬件CERN-OHL-W2；根图没有power.kicad_sch的HV变换器，J6是外接HV。
- 74HC595的SRCLR不能因NC就放行；C18/C19实际采购码100nF/50V/0805与470nF/1812/≥250V图注冲突，先核准确料号而非网名。
- Q35是RGB level_shifter却生POWER_CONVERTER、供电旁路误成snubber；SW3 SolderWire封装不是独立连接器，BTL扬声器不是数据差分对。
- R1/R2/R53的0 (1%)(NC)与nc=False并存要保留装配未知；input_sha256用board_intent.input_fingerprint；schema15终态不兼容如实FAIL，不造需求过门禁。
- Top50已问的HVEN默认态/RST-T04不重复记漏报；4项是USB、LDO启动、外引支路、RGB掉电的计划覆盖遗漏，不是4个已证硬件故障。


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

## solderedelectronics--capacitive-soil-sensor-hardware-design（2026-11-02）
- TLC555首页ESD额定会误判TVS；D1的AVAILABLE/text_extract不等于page_text能读txt，更不等于编号图已核。FD1/H1/H2零电气脚不应要求电气定界表。
- R8=TC33X-2-103E须按原厂code103=10k±25%核滑臂加载；R1被R5+R6+R7并联，C1的tau约0.13570s；约870kHz的555低频简式已越模型边界。
- 外源K1.2声明状态/出处后供电网逻辑链会消失；U2.5仍是power，去耦设regulator_output；LDO无SS脚也须问启动充电+负载/限流（M01）。
- 网表未列电极元件不证明传感断路：固定PCB有无net的F.Cu宽线；仅V2.0.0 BOM不能混入V1.2.2。20组共享依赖已合并，原生不接needs_human/未定级，保留FAIL；26条归因非26个硬件故障。

## antmicro--jetson-nano-baseboard（2026-11-02）
- XML的Val/DNP优先；SiC477原链接75786是另一族，准确77113的NC21/GL输出/VDRV内部电源不能套浮空或断供；FT232RQ与HD3SS3220也须按模式和内部偏置判。
- LED1 A/K同网在固定PCB亦成立；R43=470Ω直接加载NCP380 FLAG，不能扣LED压降。33V TVS对36V正常输入只判持续窗口，不拿VBR或脉冲DC绝限硬比。
- TPD4/TPD8/PESD多通道不能要求整颗仅两网；TPD4直通NC非保护通道。LDO启动、外引供电、SoM MDI专项另查；reject错误屏蔽隔离候选仍不释放J3，保留覆盖遗漏。
- 无独立BOM；strict的3个缺名地脚保留原状。1468项逐项记判，446条归因非446个故障；needs_human/schema15及其它记录限制保持FAIL，完整证据在缓存，未打包。

## newell--hv-flyback-converter（2026-11-02）
- LT3957A p7：SGND/SENSE1片内连GND且禁止外部短连；DA2032 p1四初级必须并联，别凭分网或多端同网指控断地/短绕组。
- 先声明有出处的FBX/SENSE正常节点窗再归因：R7/R9初扫2.461W/3.509W粗估可消除，本板未计误报；正常窗不能关闭掉电/故障保证。
- D1 5V VRWM不覆盖推断6V；D3错链BZT52B仅确认资料错配。R8/R9标称183.88V无允许误差不判错，TR1的3A不是绝对饱和额定。
- 被动TR1别套数字隔离器，SS电流源别套strap/复位；零脚H1–H4不是DEBUG。并联primary+内置开关模型仍须人工核，别伪造两脚磁件。
- 最终169项、36归因（2/14/0/2/18）、Top50漏报0；348条均为NEEDS_HUMAN/未定级格式拒收，保留FAIL/未打包。20根因共享证据逐边点名，普通缺输入不升成硬故障。

## antmicro--m2-smart-iot-module（2026-11-02）
- 四脚无源晶体的接地壳脚可标power_in；plan_concrete_checks不能据任一power_in就当有源振荡器：本板Y1/Y2/Y4漏CLK-C01。
- TLV803EF29DBZR末尾R是卷带，默认DBZ=GND1/RESET2；1.8V轨却选29门限；MIC2877-5.0固定版7脚须直连OUT，分压不能套可调版。
- U10.EN沿200k追到10k上拉/FTDI输出；U5 V_OUT/nRF内部DEC不是缺源。FTDI/nRF跨域经串阻时，逐网直接IC端点法会漏SIG-C08。
- DNP R45/R46决定Coral AON3.3V时49/50处置；MM8130是RF测试座，非配电支路；无独立BOM时按XML Val/MPN/DNP，不用可视化CSV冒充。
- 586项/108条归因（5/41/0/30/32）/6覆盖漏项；原生不接NEEDS_HUMAN，剩1786拒收均由此派生，FAIL未打包，完整台账在缓存。

## moelashmawi--flyback-ac-dc-converter（2026-11-02）
- 原生PWR_FLAG不创造电源；C5/R4、C8/R6两条12V网与D5/L1/J2输出实际失接，须看交点结点及XML，不能按同名电压合并。
- VIPer VDD接SOURCE=0V、C10开路及TL431 K/A同网均可独立判；EL817 C接VDD/E接FB是电流注入接法，别误判C/E方向。
- intent.devices的EL817共同脚表未进入NetGraph，输出清单null使FEEDBACK-OPEN漏问；先修脚义数据流，再加输出电容故障包络种子，不编16V超压。
- EE25骨架名不够证明绕组脚义；图示两次级各自同网先列需确认。1kV不等于Y、275VAC不等于X，0.5A保险与0.3A扼流圈不能直接判过载。
- ST官网可读不等于本地完整PDF到位；Mouser可返1页Access Denied PDF须验标题。改devices后先重冷扫再merge；needs_human/schema15冲突及其余记录错误如实FAIL。

## anthilla--anthc（2026-11-02）
- MCP3464RT-E/NC的/NC是UQFN封装，不是DNP；以原生DNP和BOM区分，R65真不贴。原始db保留，修正分析副本再冷/热扫。
- TPS54331 EN与TLV9054S SHDN允许浮空；只确认漏物理脚/采购封装错，勿报必不启动。CP2102N三脚同3V3可为合法旁路稳压。
- PESD3V3L2BT公共脚是3，SM712亦需逐通道；整颗三网不能跳过PRO-E02。无EN LDO仍需PWR-D03启动充电+负载检查。
- Ω串阻/RTS-DTR交叉发射极、boost储能L2、共享J3归属需人工追端；SS不是数字strap/救砖，VBUS检测不可取多源OR之后。
- 893项/100根因归因（7/11/0/18/64）、漏项2；schema15扩展及其它记录错误如实FAIL/未打包，原生报告警示保留，完整证据只在缓存。

## hasanberkdasar--bms-can-bus（2026-11-02）
- Q_NMOS_DGS的1=D/2=G；本板功率端接G、CHG/DSG接D；REGIN串100Ω不等于预稳压，BREG不用而REGIN用时须按BQ p75接REGIN。
- BQ低串数仍必须让VC1、VC2、VC16量实际电芯；未用TS3可浮空，CAN Vref亦可浮空，别把正确NC绘图提示都计误报。
- 两脚无源晶体不问有源OE、片内ADC不问运放输出；22pF没有CL/ESR不能判匹配，一个本地120Ω也不能判整网端接缺陷。
- J_PACK+1/J_PACK-1导致FN-EXT-J-PACK-1碰撞；原文4.7k ohm未解析及NEEDS_HUMAN/schema15冲突须保留。381项、30归因(5/4/1/1/19)、漏报0，FAIL未打包，完整证据仅在缓存。

## fossasia--pslab-hardware（2026-11-02）
- BOM `1/16W`会被bom_ratings斜线分段读成16W（27只、放大256倍）；SELECTED_PART_RATING注记又被DERIVED_ROW_KEPT丢掉，合并步首修这两处。
- L3接boost SW不是输入滤波；Q2/Q3射极供±6V、U17以−9V为地反相，D1/D2是持续齐纳参考，勿套无源/TVS模板；200k EN到VIN是MT1470手册允许接法。
- U16四脚三通道需PRO-E02逐通道；无EN/SS的U6/U21也要启动电流，PVS/PCS实际源输出还缺RST-T04默认态对象。NC的VSET/RSET有合法选项，R61=51k明确停用NTC。
- 固定BOM175件，原图198含标识/孔/TP；C5/C23、R22、F1、PGA链接、Q额定均有字段冲突，不能择一当实贴。ABS07-166别套通用CL；一页Access Denied不计手册到位。
- I2C顶层power_rails须显式同值写schema2 rails以免重建过期；914项/75归因(5/11/1/2/56)/3覆盖漏项。needs_human及派生限制保留FAIL，完整记录在外部缓存，未打包。


## prajyotdaphal--home_automation-module（2026-11-02）
- PS1 HLK-10M05的3=-Vo/4=+Vo在原图反接；F2.1/.2同/AC。别让0条lint或正向网名掩盖实际极性/保险旁路，原厂p12（印刷p10）核脚图。
- SANYOU继电器COM1、COIL2/5与PC817 1A/2K/3E/4C先分侧；交流J9返回和K1–K5 COM接低压GND，不把去耦返回混池当成另一个原板短接。
- DIN0309电阻封装会触发INDUSTRIAL_DI；零脚孔会触发DEBUG；薄膜/径向电容别默认MLCC，机械触点/光电晶体管别强索数字CMTI。
- 取板稀疏检出会漏BOM，先查git完整树；本板同版分号CSV/Designation列规范化后read_bom共91电气件，4孔未列、供货列全空；PC817输入330Ω+1kΩ，3.3V下IF≤2.481mA不能套5mA CTR。
- 476项/30根因（4/8/0/7/11）/3覆盖漏项；needs_human/schema15与其余证据格式拒收564条，保留FAIL/NO_GO未打包，完整记录和Top50在外部缓存。

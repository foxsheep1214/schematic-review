
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

- tinkerforge--evse-v2-bricklet：139件/125网，strict因F101/F102/L102六个无名脚失败，XML/db443节点一致；24电路/70框架/821项，53局部判/768逐ID待核，FAIL/NO_GO；37归因=1图面真+12误报+17资料+7人工，3分层漏问。
- TPS709 EN允许悬空；3V3全并联名义102.82µF对手册Ceff最大47µF，不能只看2.2µF，也不能把名义值当有效下界。HCPL2731的3.3V保证要按厂家分支核，不无条件借Broadcom4.5V下限定onsemi硬错。
- Diodes品牌/Load Switch应用/PWM及同步整流描述误导U103/Q102/U106标题定类；kind_reason要有真实标题/端点依据。P102名Relay实为2针连接器，L101/L103的FB是串联滤波，不套线圈续流。
- 对外SPI没有SIG-C08时要留掉电注入计划缺口；AC/DC模块L/N→V+/V-也要逐输入输出核隔离，不能只找GND1/GND2。RS485750Ω偏置单120Ω约0.244V，双120Ω约0.127V，未锁远端不判原板缺陷。
- schema15无needs_human/未完成功能格式：53局部事实留checks，全部70功能保留pending，不写完整功能PASS。原生报告只有诊断效力；P111与MCU31脚号真墨迹重叠可判P2，C128/16MHz仅邻近不另判。

- solderedelectronics--breadboard-power-supply-board-hardware-design：25件/24网；3候选+add→4电路/14框架/185项，39局部已判、146逐ID待核，FAIL/NO_GO；30归因=1资料真缺陷+13误报+3知识+13人工，Top50一处接口漏问。
- DC_JACK的K2被K前缀误作relay，伪线圈/去耦/无驱动并漏EXT-K2；合并步先修强角色优先级，用J→K别名变异验证PRO-D04/DEV-C04覆盖，别把原板直接当已证电气缺陷种子。
- Diodes页眉商标被识为diode；U2电路PWR-C04却anchor到邻接U1；机械触点不套半导体输入浮空，12V/VUSB电源边不套逻辑VIH/VIL，普通二极管不套eFuse。
- U1符号1IN/2OUT/3G与自定义封装成套编号，几何支持右输出/中央GND，缺受控映射不判实物接错；U2仅SE5218缺3.3V后缀才是明确资料缺陷。C4名义2.2µF不证明p6有效≥1µF，USB-only须单核U1反灌。
- strict因S1–S3十二触点缺名失败但XML/db70节点一致；分号CSV的Designation须显式转Value。schema15不支持needs_human/未判功能，旁账保留全部分母且门禁FAIL；DEV-D04非DOC前缀还不生成独立根因任务。

- antmicro--poe-usb-c-pd-converter：269件/782端点，strict仅U10.3缺名；20电路/55功能，补官方脚表794→725项，74局部判/651待核，31根因=3真+13误报+8资料+7人工，4模型漏问，FAIL/NO_GO。
- TPS2372-3的63.4Ω/90.9Ω宣告Class8与Type3能力不符；INA230 A0/A1八只strap全DNP确悬空；TPS65987D未用PP_HV1须接地，别当可悬空GPIO。
- IEA模块VIN-/VOUT-不能全脚并查集合域；TRIM未用应开路。补intent.devices后SW/RTN伪去耦消失；VOUT+/Vo(+)仍漏PWR-C04，厂家28V款外接电容0–470µF。
- LV14540 FB是0.750V、全温0.735–0.765V；200k/33k名义5.295V、1%极值5.101–5.495V，勿套常见0.8V。CD-MMBL110S的Battery chargers是应用不是器件类型；桥物理号映射无定论不判实物接反。
- 集成PD开关也要PORT-SHORT/储能放电，源保护逐支路问；IEA p21安全要求外部输入保险须核上游合同。schema15保留逐ID needs_human与FAIL，报告原生缺口计数不等于待核总数。

- s59mz--kicad-led-drv-pmod：19件/1页，KiCad10.0.7 strict；115项=112原生+3人工gap，26局部判/89待核，10归因=1数据真+2误阻断+2知识+5人工，门禁FAIL；3计划漏问、0已证硬件漏检。
- LTC3206是充电泵恒流驱动：CPO14→C4要求Ceff≥0.6µF/低ESR（3206f p12），CPO没被OUT/SW模型识别；ENRGB/S复合脚名也漏RST-T04，源侧PRO-C04不能只靠FUSE/MOV词触发。
- D1–D8两端LED已有空pin_difference仍卡kind资料；共阳四脚RGB D9没有IC供电返回对，不应阻IC去耦库存，但真实颜色针序/额定照审。12k名义20mA，不能把芯片100mA绝限当LED允许电流。
- J1自定义奇偶编号与Pmod镜像编号须按坐标/端面换算，不能见数字不等就判接错；下载的官方托管Pmod副本实际2011 Doc510-002，文件名不证明1.1.0；本轮LTC完整PDF未取得，只用在线文字。
- Designator/Comment CSV需可追溯改列名后read_bom，fetch原db不改；schema15对未定主机/采购/故障合同无needs_human枚举，逐项pending+逐功能范围保留，原生资料不足0不等于审完，不伪造VENDOR_DATUM或功能PASS。

- alia5--piccante：33件/52网，KiCad10.0.7 strict、XML/db136节点零差异；7电路/21框架/299项，55局部判/244逐ID待核；34归因=0真+7误报+0准则+1知识+26人工，3计划漏问，FAIL/NO_GO。
- Pico W的ADC_VREF内部已由3V3滤波供入，AGND在官方Fig12接公共地；别把载板外引脚悬空判模组断供。A1首次审计被unknown漏收时，--require-ref A1可恢复已有PDF核验。
- TPS5430 BOOT是C2跨PH的自举脚，不是strap；ENA绝限7V，直连VBATT只在源窗确认后按7V边界判，不套常见可直连VIN的EN。C2需≥10V；C4=220µF/1206不证明Poscap ESR或有效容量。
- STARTUP经VBATT分压吸入A1/R14/R15会漏独立ANA-C03；模组内USB与无保护核心的源侧PRO-C04也要展开。CAN120Ω经外接帽，三节点40Ω仅是闭帽条件例；D2反偏使USB不能直接充C4，别误加220µF到VBUS。
- schema15无needs_human/未定工况表达时留逐ID pending及逐功能旁账，不制造完整功能PASS；本轮原生functions为空，门禁FAIL且报告无效，资料不足0不等于244项已审结。

- mlab-modules--qfhmix01：235件/152网/3页，11电路/23框架/480项；94局部判、386逐ID待核，36归因=1资料真+23误+1知识+11人工，2计划漏问，门禁FAIL/NO_GO。
- 47uF/6,3V被rated_voltage读成3V；AD8343输出270nH+820nH是偏置扼流，不套DRV续流，LO内部50Ω/偏置见p22，RF输入经56nH+68Ω已给直流偏置。
- Si53322是外部输入fanout，不套晶体CL/起振；LT6604-5的2/4/10/12已给官方脚表仍被ANALOG前提漏掉。J1 DC输出经49R9到外部需细分掉电注入，不能拿PRO-D04泛问当SIG-C08全覆盖。
- 源旧CSV205件与当前235件有129值冲突，read_bom不保留Value须独立CSV对读；原生全235件显式dnp no可据此声明图面装配，不能把旧BOM当采购保证。source/db572节点零差异、孔M1–8不是IC。
- LTC3601等官方web文字可留text_extract，pdftotext有时错误把txt当PDF导致NO_TEXT；保留摘录原文及清洗映射、不改名PDF。schema15未判项写pending与逐功能范围，不用资料不足0/局部PASS表示审完。

- rapidanalysis--xerxes：58件/209网/516端点，strict仅U5.2/.4空名，XML/db零差异；12电路/34框架/600项，83局部判/517逐ID待核，60归因=2真+37误+1准则+3资料+17人工，4漏问（1候选已恢复+3人工补问），FAIL/NO_GO。
- CDDFN10-3324P四路TVS因多网/名称漏PRO-E02而出TRIP/NOTRIP；D6回PoE局部VIN-不是系统GND。feed-through NC6/7/9/10允许外部同网，别当DNU。
- AP3441 p9 Cff给10–470pF，本板C9=4.7nF越应用窗但不证明实测振荡；Cout40.1uF不因典型2x22uF就判缺容。J8 UART三针误标JTAG；R13下拉与CM5留空指南不同仍需例外依据。
- CM5 pin56/58内置1.8k与板2.2k并联约990Ω，3.465V/0.4V低态约3.11mA仍须外设IOL；U4/J5/J4 DNP不可自动装回。JLC匹配工作表保留Unconfirmed语义，别当批准替代料。
- 3V3轨须重复写入schema2 i2c_topology.rails以免重建漂移；原生schema15对部分功能/未定合同无needs_human，保留逐ID旁账和FAIL，资料不足0不等于审完；零脚Logo/INH绑电源不承担LED电流。

- badgineer--mp2-esc：216件/123网/550端点一致；621项=618原生+3补问，118局部判/503逐ID待核；27归因=3资料真+9误+5资料缺口+10人工，3计划漏问，FAIL/NO_GO。
- 官方G/D/S已写intent.devices仍未进入NetGraph，18只MOS全pin-roles未解；先修官方映射贯通，测QA1唯一栅阻R43 DNP后真悬空，别把L6498内部58–125k下拉漏算。
- 0.5mR解析器本身正确，parse_kicad._component仅^R数字位号调度导致SHA不取值；NetTie_2/Device:R也不能因特殊位号认未知IC。R100/R150需与采购100/150Ω分支留冲突，勿替设计改值。
- 同提交PDF仍可过时（6R8对当前4R7）；U4 NCS20034/COS724采购身份矛盾要先锁。U6共GND不自动是隔离缺陷；隔离DC/DC仍需PWR-C04，源侧保护不能只问J3.6。
- BOOT-OUT/VCC-GND须显式返回分组；schema15未知合同保留逐ID pending和29功能未完成旁账，原生资料不足0/电路无已证错误不等于审完，门禁FAIL如实交。

- blkburn--zigbee：39件strict；8电路/25框架/222项，15局部判、207逐ID needs_human；20归因=3数据真缺陷+9误报+1模型知识缺口+7人工，3计划漏问，门禁FAIL。
- MX25R8035FM1IH1 p84是HOLD#非RESET#；p8准许真正未外连WP#/HOLD#内部上拉。pspice:DIODE图形pin2阴极却名A、pin1却名K；先判库语义矛盾，别越界断言实物反接。
- D6经1k接J2的信号钳位不能按直接网归内部functional_clamp；复用port_connectors应出PRO-E02。CT/RESET合法add仍丢nets/anchors，ADC/复位0展开，优先修引用关系而非手补计划。
- RF-BM-2652B1完整原厂PDF可从B1_20240823 URL取得（内页May2023），产品页误链B2；模组脚36有内部上拉，别套裸片RESET说明。AHT10是连接器、BT1是座，不能猜上拉、电芯或供入方向。
- schema15保留pending并让覆盖FAIL；局部功能合格/资料不足0不是全板通过。NETLIST_FACT正则不收SW1.1'这类原生脚号；独立核XML/db，不改真实脚号去适配校验器。

- neumi--fastlogic：194件/207网/627端点，XML/db一致、KiCad10.0.7 strict；19电路/55框架，937=934原生+3补问，77局部判/860待核；91归因=6真(4电气+2图面)+20误+6资料+59人工，4模型缺口，FAIL/NO_GO。
- 源BOM在固定commit的production/bom.csv，稀疏检出不显示；read_bom丢Value须CSV独立对读。43个C前缀容量全None、41个R前缀阻值未解；R330/R120被作0.33/0.12Ω，按SKU消歧，别全局strip合法RKM。
- STM32F407 VCAP49/73须各2.2µF且ESR<2Ω；W5500 RSVD23须接地，VBG18须浮空、RSVD38–42为NC；CP2102N VBUS需分压/等效限流，VREGIN/VDD各需4.7µF并0.1µF。PE0/1无ADC，意图未锁先留人工。
- 共3V3不能把U13 PMODE43–45/U6 VREF+认成D18驱动；BSS138两侧上拉需低态合计(条件10k各侧约0.75mA)。本版PRO-C04与Y3 CLK-C01已有，漏项要核当前计划，别照搬旧memo。
- schema15没有needs_human/未定合同状态；逐ID pending与55功能未完成旁账必须保留，原生资料不足0/4失败功能不代表全量55框架已审。报告valid=false仅诊断；p1可作定位而page1本身不被locator regex识别。

- mlab-modules--solarmini01：28件/59端点/1页，157项=155自动+2补问；45局部结果/112逐ID人工，23归因=2数据真+10误+2知识+9人工，Top50两处计划漏问，FAIL/NO_GO。
- SPV1040为boost：PV→L→LX是输入，VOUT4/D1.K才是输出；不要把所有SW经电感的远端都当输出，C1输入47uF与输出直接57.1uF分开，C7隔0.47Ω。
- AN3319 p18明确0Ω把XSHUT并MPP-SET合法、外控应移除；XSHUT默认态和MPP-SET UVLO可能漏RST-T04/PWR-C06。J3 SIG-C08、J1/J4 PRO-C04本版已有，先查实际计划。
- R2=-不可自动DNP；SMBJ5.0A指定D_SMA是数据错。D2最小击穿6.4V>5.5V，但无电池轻载接入适用性须锁；FERROCORE DE表IDC4A不等于有定义的全温Isat。
- HOLE污染strict/手册/pinmux；add丢nets/anchors。源BOM截Individual再read_bom并独立核Value；schema15保留pending和完整功能分母，原生资料不足0不代表审完，未有效打包的报告索引须回缓存读。

- antmicro--hdmi-mipi-bridge：123件/4页strict；797项/34框架，108局部判+689逐ID人工；37归因=3真+22误+3知识+9人工，2计划漏问，FAIL/NO_GO。
- J6的16个标签单节点已有原生NC，NET-A01漏看no_connect_nodes；HPD/HPDI分别经两只0Ω到同一POWER，NET-A02须核多跳，不能只按名字判断网。
- PCA9517ATP HWSON8脚1/2/3/4/5/6/7/8=SDAA/GND/EN/SDAB/SCLB/VCCB/VCCA/SCLA，别套SO8；Toshiba未用APLL须PFIL接100n、DAOUT开路；7C有源XO规定15pF，直接47pF超规定区。
- IC前缀TLV733和Y前缀7C须--require-ref才能恢复准确手册审计；TLV733无需Cout稳定。含VCC的多通道TVS仍要PRO-E02，不能出TRIP/NOTRIP；桥RESETN接收端还需PWR-C24。
- schema15未定主机合同留needs_human旁账，不造完整功能PASS；本轮6失败框架已写，其余28未完成明确保留；报告valid=false只诊断，标准record索引未打包。

- brainsmoke--usb2_hub：95件/301端点/5页strict；19电路/45框架，688=683+5补问；101局部判/587逐ID人工，27归因=2真+11误+1准则+4知识+9人工，FAIL/NO_GO。
- FE1.1 VS_PLL10/VS_A25是返回地、OVCB[1..4]是输入；已给官方pins仍被native power_in/output误报。AP22652AW6的A是锁存，订货表在DS41186 p12。
- USBLC6六网馈通阵列漏PRO-E02，先修protective_clamps的型号正则+恰两网条件；J5直接50.5uF在非Attached超10uF已证，别拿Attached100uF豁免。
- 120uF原厂有每Hub口径，不盲判每口22.1uF；G01-031须保留传统Type-A默认VBUS例外。Wiki的ST - USBLC6-2SC6.pdf实际SC6Y，准确SC6在ST - USBLC62.pdf。
- R8括号1%会令2K7读失败；J6原生DNP不可装回构造反灌。schema15未知合同留逐ID pending及45框架分母，资料不足0不是587项审结，原生无效报告不打包。

- spirit532--studio_mic：58件/38网/1页，strict仅14功能脚缺名，XML/db131节点一致；154项=152自动+2gap，40局部判/114逐ID待核，25归因=1数据真+14误+1知识+9人工，2路径漏问，FAIL/NO_GO。
- 幻象J1双线各47Ω+2.2kΩ→D1、再200Ω→U1是有阻供电，四条无驱动误报；GNDA=47k/47k中点不是0V，不能把虚地当隔离域或理想地。
- 40106逻辑反相器无角色需add泵电路，不能套LDO稳定窗；12V理想全摆幅时飞跨C11–C16差压12至72V。两级100M/100nF慢极点52.36s，HT经C19耦到掉电U1输入应专问SIG-C08；源侧PRO-C04也要逐馈入支路。
- XLS范围位号先展开，read_bom丢Value需独立对读；BOM五只电解47uF/63V，J1 Qty0=外壳自带非DNP。HEF40106BT与74HC14符号针序兼容，错误在SN74HC14资料链接；SpiritsKiCADLib不是SPI，H1/H2孔不是测试点。
- 官方HEF完整PDF403但在线文字可核；text_extract仍被当PDF出NO_TEXT。schema15保留pending及功能分母，不伪造VENDOR_DATUM/PASS，原生资料不足0不代表全154项完成，报告valid=false仅诊断。

- a2r-lab--crazyflie_fpga_deck：75件/543节点/324球对读零差异；394=390自动+4补问，82局部判/312逐ID待核，75归因=2真+52误+3知识+18人工，4计划漏问，FAIL/NO_GO。
- U1.H10 VCCADC_0即使未用也不得接地（UG480 Table1-1）；未用Bank15/16/34/35全脚接地、VCCBATT接地及U2未用LDO接地各有原厂例外，不能整颗FPGA豁免PWR-A02。
- TPS65023B的L1/L2/L3、VDCDCx、DCDCx_EN、VRTC须贯通正式端口模型；否则无源误报、C04/C06漏问，SCLK/SDAT内部I2C还漏SIG-C01。PRO-C04当前已覆盖J2/J3，别重复列漏报。
- 三轨名义Cout76.05/74.64/128.32µF；22µF不是硬最大。LM3880 EN内部7µA+C31=470n合法，83.93ms只是典型；X1图C596959/BOM C496694/ASV链接冲突只证资料错。
- CSV Designator/Comment须显式改列并独立对值；add并入可丢nets/anchor。schema15留312逐ID与18框架旁账，不用报告功能1/资料不足0冒充审完；UG480仅官方在线条款、Infineon完整PDF未取到。

# 独立审查逐项依据

评测任务要求未能独立判定的记needs_human；原生schema15只接受PASS/FAIL/OPEN功能及严格VENDOR_DATUM，无法诚实表达缺受控工况/对端决定。仅保存已核局部结论和完整逐项pending，功能框架待补不伪造；原生门禁必须FAIL，不是整板审结/准出。

来源：b1027cf；单页Rev.r0.2；41器件，10 DNP。用途为实验SDR的推断，非受控产品要求。

## 独立计算与边界

- U1片内稳压三个1µF输出电容，名义值在p188的0.1–10µF窗口；名义下/上裕量0.9/9µF，Ceff未由此证明。
- +3V3同网C1/C2/C11–14=6µF；不包括三个1.8V输出电容，也不包括串RF的C9/C10。
- 假设TX驱动源阻抗为0、U1内部端接100Ω、两线47Ω：差分传递100/(100+47+47)=0.51546。仅展示预算变量，未证明对端实际违规。
- 50Ω负载下若端口输入10dBm，则Vrms=sqrt(0.01×50)=0.7071V，Vpk=1V；该例不限定可能的外部DC/ESD输入，不能直接判5V TVS充分。
- U1 p191最大CW输出在指定25°C/3V测试点：RF09=16dBm(39.81mW)、RF24=15.5dBm(35.48mW)，小于Balun1W；不能把此单点当全温故障功率界。
- U1 p68要求TCXO26MHz、0.6–1.6Vpp clipped sine、DC耦合且XTAL2接地；本板连接满足，U2输出制式/幅度未得。
- U1 POR p188上升1.55–1.65V低于1.8V最低推荐工作电压；这只说明POR不自动保证所有棕断状态，不能在缺对端合同下认定本板实际失效。

## 逐项判定

### CLK-C01.CLOCK-U2-RUN.C1
NA：U2.3→Net-(U2-OUT)→R19(0Ω)→Net-(U1-TCXO)→U1.17；U1.18→R2(0Ω)→GND；R1/C3均DNP。Atmel-42415E pp7–11 Table2-1/Figure3-1及p68 §6.4.3要求DC耦合且XTAL2接地。 有源TCXO模式，无板外两端无源晶体，CL/ESR/负阻检查不适用；幅度/频率仍在CLK-D01待核。

### CLK-D01.CLOCK-U2-RUN.C1
needs_human：CLK-D01.CLOCK-U2-RUN.C1：网表对象{"circuit": "CLOCK-U2", "circuit_key": "CLOCK-U2", "ref": "C1", "refs": ["C1", "R19", "R2", "U2"], "nets": [], "state": "run"}已核；尚无足以关闭本条判据的对端/工况或厂家独立界限，保留人工决定，不据名称判不适用。

### CLK-D03.CLOCK-U2-RUN.C1
NA：U2.3→Net-(U2-OUT)→R19(0Ω)→Net-(U1-TCXO)→U1.17；U1.18→R2(0Ω)→GND；R1/C3均DNP。Atmel-42415E pp7–11 Table2-1/Figure3-1及p68 §6.4.3要求DC耦合且XTAL2接地。 无RTC或备份供电，不套RTC启动/充电判据。

### DEV-C01.BOARD
NA：本项对象仅H1/H2，均为悬空安装孔焊盘，无负载电流、供电或电应力；其机械可靠性不由本条电应力判定。

### DEV-C01.C1
needs_human：对象C1：已按实际DNP与串/并联网络追踪；+3V3只有名义点，RF峰值/对端故障、环境和降额等级未受控，不能用3.3V或1.8V名义点的proposal当全窗应力PASS。普通阻容不因缺独立手册自动阻断；先确定本项实际应力包络。

### DEV-C01.C10
needs_human：对象C10：已按实际DNP与串/并联网络追踪；+3V3只有名义点，RF峰值/对端故障、环境和降额等级未受控，不能用3.3V或1.8V名义点的proposal当全窗应力PASS。普通阻容不因缺独立手册自动阻断；先确定本项实际应力包络。

### DEV-C01.C11
needs_human：对象C11：已按实际DNP与串/并联网络追踪；+3V3只有名义点，RF峰值/对端故障、环境和降额等级未受控，不能用3.3V或1.8V名义点的proposal当全窗应力PASS。普通阻容不因缺独立手册自动阻断；先确定本项实际应力包络。

### DEV-C01.C12
needs_human：对象C12：已按实际DNP与串/并联网络追踪；+3V3只有名义点，RF峰值/对端故障、环境和降额等级未受控，不能用3.3V或1.8V名义点的proposal当全窗应力PASS。普通阻容不因缺独立手册自动阻断；先确定本项实际应力包络。

### DEV-C01.C13
needs_human：对象C13：已按实际DNP与串/并联网络追踪；+3V3只有名义点，RF峰值/对端故障、环境和降额等级未受控，不能用3.3V或1.8V名义点的proposal当全窗应力PASS。普通阻容不因缺独立手册自动阻断；先确定本项实际应力包络。

### DEV-C01.C14
needs_human：对象C14：已按实际DNP与串/并联网络追踪；+3V3只有名义点，RF峰值/对端故障、环境和降额等级未受控，不能用3.3V或1.8V名义点的proposal当全窗应力PASS。普通阻容不因缺独立手册自动阻断；先确定本项实际应力包络。

### DEV-C01.C2
needs_human：对象C2：已按实际DNP与串/并联网络追踪；+3V3只有名义点，RF峰值/对端故障、环境和降额等级未受控，不能用3.3V或1.8V名义点的proposal当全窗应力PASS。普通阻容不因缺独立手册自动阻断；先确定本项实际应力包络。

### DEV-C01.C4
needs_human：对象C4：已按实际DNP与串/并联网络追踪；+3V3只有名义点，RF峰值/对端故障、环境和降额等级未受控，不能用3.3V或1.8V名义点的proposal当全窗应力PASS。普通阻容不因缺独立手册自动阻断；先确定本项实际应力包络。

### DEV-C01.C5
needs_human：对象C5：已按实际DNP与串/并联网络追踪；+3V3只有名义点，RF峰值/对端故障、环境和降额等级未受控，不能用3.3V或1.8V名义点的proposal当全窗应力PASS。普通阻容不因缺独立手册自动阻断；先确定本项实际应力包络。

### DEV-C01.C6
needs_human：对象C6：已按实际DNP与串/并联网络追踪；+3V3只有名义点，RF峰值/对端故障、环境和降额等级未受控，不能用3.3V或1.8V名义点的proposal当全窗应力PASS。普通阻容不因缺独立手册自动阻断；先确定本项实际应力包络。

### DEV-C01.C7
needs_human：对象C7：已按实际DNP与串/并联网络追踪；+3V3只有名义点，RF峰值/对端故障、环境和降额等级未受控，不能用3.3V或1.8V名义点的proposal当全窗应力PASS。普通阻容不因缺独立手册自动阻断；先确定本项实际应力包络。

### DEV-C01.C8
needs_human：对象C8：已按实际DNP与串/并联网络追踪；+3V3只有名义点，RF峰值/对端故障、环境和降额等级未受控，不能用3.3V或1.8V名义点的proposal当全窗应力PASS。普通阻容不因缺独立手册自动阻断；先确定本项实际应力包络。

### DEV-C01.C9
needs_human：对象C9：已按实际DNP与串/并联网络追踪；+3V3只有名义点，RF峰值/对端故障、环境和降额等级未受控，不能用3.3V或1.8V名义点的proposal当全窗应力PASS。普通阻容不因缺独立手册自动阻断；先确定本项实际应力包络。

### DEV-C01.CLOCK-U2
needs_human：对象CLOCK-U2：已按实际DNP与串/并联网络追踪；+3V3只有名义点，RF峰值/对端故障、环境和降额等级未受控，不能用3.3V或1.8V名义点的proposal当全窗应力PASS。普通阻容不因缺独立手册自动阻断；先确定本项实际应力包络。

### DEV-C01.IQ-J1
needs_human：对象IQ-J1：已按实际DNP与串/并联网络追踪；+3V3只有名义点，RF峰值/对端故障、环境和降额等级未受控，不能用3.3V或1.8V名义点的proposal当全窗应力PASS。普通阻容不因缺独立手册自动阻断；先确定本项实际应力包络。

### DEV-C01.R10
needs_human：对象R10：已按实际DNP与串/并联网络追踪；+3V3只有名义点，RF峰值/对端故障、环境和降额等级未受控，不能用3.3V或1.8V名义点的proposal当全窗应力PASS。普通阻容不因缺独立手册自动阻断；先确定本项实际应力包络。

### DEV-C01.R13
needs_human：对象R13：已按实际DNP与串/并联网络追踪；+3V3只有名义点，RF峰值/对端故障、环境和降额等级未受控，不能用3.3V或1.8V名义点的proposal当全窗应力PASS。普通阻容不因缺独立手册自动阻断；先确定本项实际应力包络。

### DEV-C01.R16
needs_human：对象R16：已按实际DNP与串/并联网络追踪；+3V3只有名义点，RF峰值/对端故障、环境和降额等级未受控，不能用3.3V或1.8V名义点的proposal当全窗应力PASS。普通阻容不因缺独立手册自动阻断；先确定本项实际应力包络。

### DEV-C01.R19
needs_human：对象R19：已按实际DNP与串/并联网络追踪；+3V3只有名义点，RF峰值/对端故障、环境和降额等级未受控，不能用3.3V或1.8V名义点的proposal当全窗应力PASS。普通阻容不因缺独立手册自动阻断；先确定本项实际应力包络。

### DEV-C01.R2
needs_human：对象R2：已按实际DNP与串/并联网络追踪；+3V3只有名义点，RF峰值/对端故障、环境和降额等级未受控，不能用3.3V或1.8V名义点的proposal当全窗应力PASS。普通阻容不因缺独立手册自动阻断；先确定本项实际应力包络。

### DEV-C01.R7
needs_human：对象R7：已按实际DNP与串/并联网络追踪；+3V3只有名义点，RF峰值/对端故障、环境和降额等级未受控，不能用3.3V或1.8V名义点的proposal当全窗应力PASS。普通阻容不因缺独立手册自动阻断；先确定本项实际应力包络。

### DEV-C01.RF-U1
needs_human：对象RF-U1：已按实际DNP与串/并联网络追踪；+3V3只有名义点，RF峰值/对端故障、环境和降额等级未受控，不能用3.3V或1.8V名义点的proposal当全窗应力PASS。普通阻容不因缺独立手册自动阻断；先确定本项实际应力包络。

### DEV-C02.CLOCK-U2
needs_human：CLOCK-U2 电容均为0402无极性MLCC，非电解耐久件；名义1uF/1.8pF可读。需确定各自电源/RF节点的持续/脉冲工作窗及温度，再按最弱档/所选MLCC核有效容量和耐压，不虚构寿命或厂家参数。

### DEV-C02.RF-U1
needs_human：RF-U1 电容均为0402无极性MLCC，非电解耐久件；名义1uF/1.8pF可读。需确定各自电源/RF节点的持续/脉冲工作窗及温度，再按最弱档/所选MLCC核有效容量和耐压，不虚构寿命或厂家参数。

### DEV-C03.CLOCK-U2
needs_human：CLOCK-U2中R2/R19是0Ω连接，不是精密分压；其时钟负载/瞬态电流仍需U2精确规格。

### DEV-C03.IQ-J1
needs_human：IQ-J1中TX两对47Ω串联电阻相等，接收器内置100Ω；差分摆幅经100/(100+94)=0.515名义传递（忽略源阻抗），不是已证明违例；需驱动源阻抗/实际模式与R公差核预算。

### DEV-C04.J1
needs_human：J1：J1.15/.16供+3V3；J1.2/.14/.17/.29返回；同版Cynthion对端针序、源限流/载流窗未提供，物料10132797原厂图403。

### DEV-C04.J2
needs_human：J2：SMA中心接RF、外壳接GND，选用CONSMA003.062；准确连接器原厂图403，外部天线/偏置器最大功率/DC与误接工况未提供。

### DEV-C04.J3
needs_human：J3：SMA中心接RF、外壳接GND，选用CONSMA003.062；准确连接器原厂图403，外部天线/偏置器最大功率/DC与误接工况未提供。

### DEV-C05.T1
needs_human：DEV-C05对象T1：U1 p187允许VDD1.8–3.6V、−40..85°C；p203–204各状态电流多为典型，双频同时工作和U2电流/上游能力未知。+3V3仅名义3.3V，不能据此保证供电/温度/噪声或启动全过程。

### DEV-C05.T2
needs_human：DEV-C05对象T2：U1 p187允许VDD1.8–3.6V、−40..85°C；p203–204各状态电流多为典型，双频同时工作和U2电流/上游能力未知。+3V3仅名义3.3V，不能据此保证供电/温度/噪声或启动全过程。

### DEV-C05.U1
needs_human：DEV-C05对象U1：U1 p187允许VDD1.8–3.6V、−40..85°C；p203–204各状态电流多为典型，双频同时工作和U2电流/上游能力未知。+3V3仅名义3.3V，不能据此保证供电/温度/噪声或启动全过程。

### DEV-C05.U2
needs_human：DEV-C05对象U2：U1 p187允许VDD1.8–3.6V、−40..85°C；p203–204各状态电流多为典型，双频同时工作和U2电流/上游能力未知。+3V3仅名义3.3V，不能据此保证供电/温度/噪声或启动全过程。

### DEV-D01.T1
PASS：原图PART 2450FB15A050与Johanson同型号Ver2.0 p1一致；0805六端RF Balun；封装复用0896BM15A0001仅为名称，尺寸/焊盘最终由PCB核，不据名字断言错料。

### DEV-D01.T2
PASS：原图PART 0896BM15E0025与Johanson Ver2.0 p1一致，适用AT86RF215IQ、863–928MHz六端Balun；未以封装库名字替代器件身份。

### DEV-D01.U1
PASS：原图PART AT86RF215IQ-ZU与p224 §14订货表一致，QFN48、裸焊盘、双频IQ变体；p3 §1.1确认IQ变体不含baseband，未误用AT86RF215M限制。

### DEV-D01.U2
needs_human：U2准确物料/脚义尚需原厂资料：原图part=6TG2600001、symbol=Oscillator:FT5HN；网表连接可读但不能把库符号当独立厂商脚表。

### DEV-D02.D1
needs_human：D1准确物料/脚义尚需原厂资料：原图part=ESDSLC5V0LBS、symbol=Device:D_TVS；网表连接可读但不能把库符号当独立厂商脚表。

### DEV-D02.D2
needs_human：D2准确物料/脚义尚需原厂资料：原图part=ESDSLC5V0LBS、symbol=Device:D_TVS；网表连接可读但不能把库符号当独立厂商脚表。

### DEV-D02.J1
needs_human：J1准确物料/脚义尚需原厂资料：原图part=10132797-033100LF、symbol=Connector_Generic_MountingPin:Conn_02x15_Counter_Clockwise_MountingPin；网表连接可读但不能把库符号当独立厂商脚表。

### DEV-D02.J2
needs_human：J2准确物料/脚义尚需原厂资料：原图part=CONSMA003.062、symbol=Connector:Conn_Coaxial；网表连接可读但不能把库符号当独立厂商脚表。

### DEV-D02.J3
needs_human：J3准确物料/脚义尚需原厂资料：原图part=CONSMA003.062、symbol=Connector:Conn_Coaxial；网表连接可读但不能把库符号当独立厂商脚表。

### DEV-D02.T1
PASS：T1=2450FB15A050 p1:1不平衡、2/5地、3/4平衡、6NC；T2=0896BM15E0025 p1:1不平衡、2/5/6地、3/4平衡。两者为RF Balun，非开关续流线圈。 本位号1..6与原图物理脚逐一对应。只核官方脚义，不证明PCB footprint映射。

### DEV-D02.T2
PASS：T1=2450FB15A050 p1:1不平衡、2/5地、3/4平衡、6NC；T2=0896BM15E0025 p1:1不平衡、2/5/6地、3/4平衡。两者为RF Balun，非开关续流线圈。 本位号1..6与原图物理脚逐一对应。只核官方脚义，不证明PCB footprint映射。

### DEV-D02.U1
PASS：Atmel-42415E pp7–11 Table2-1/Figure3-1逐项对照1..48和49裸焊盘无差集；14/47为AVDD0/1输出，37为DVDD输出；15/46 EVDD与21/29/39 DEVDD供入；全部14地脚含49接GND。

### DEV-D02.U2
needs_human：U2准确物料/脚义尚需原厂资料：原图part=6TG2600001、symbol=Oscillator:FT5HN；网表连接可读但不能把库符号当独立厂商脚表。

### DEV-D03.J1
needs_human：J1：J1.15/.16供+3V3；J1.2/.14/.17/.29返回；同版Cynthion对端针序、源限流/载流窗未提供，物料10132797原厂图403。

### DEV-D03.J2
needs_human：J2：SMA中心接RF、外壳接GND，选用CONSMA003.062；准确连接器原厂图403，外部天线/偏置器最大功率/DC与误接工况未提供。

### DEV-D03.J3
needs_human：J3：SMA中心接RF、外壳接GND，选用CONSMA003.062；准确连接器原厂图403，外部天线/偏置器最大功率/DC与误接工况未提供。

### DEV-D04.BOARD
needs_human：原图有真实PART，未发现已证身份冲突；但U2 TCXO与FT5HN符号的精确映射、T1/T2复用footprint及各RF通用件的指定性能尚未完全独立核实。KIND_CONFLICT T1→connector属手册文字识别误触发，不能据此报错料。

### DEV-D05.J1
PASS：J1未用1/6/7/22/23/24/25/30及MP均明确NC，其他触点均接供电/返回或IQ/SPI/RSTN；这些为无源触点，不存在片内偏置要求。只关闭图上未用触点处置，Cynthion对端定义另在DEV-D03。

### DEV-D05.J2
PASS：J2.1为SMA中心信号，J2.2为壳/外导体接GND，两物理端均使用，无悬空有源输入。仅核使用处置，对端规格另判。

### DEV-D05.J3
PASS：J3.1为SMA中心信号，J3.2为壳/外导体接GND，两物理端均使用，无悬空有源输入。仅核使用处置，对端规格另判。

### DEV-D05.T1
PASS：T1=2450FB15A050 p1:1不平衡、2/5地、3/4平衡、6NC；T2=0896BM15E0025 p1:1不平衡、2/5/6地、3/4平衡。两者为RF Balun，非开关续流线圈。 T1.6已NC，T1.2/.5接地；T2.2/.5/.6均接GND，其他端各进对应RF路径，无未处置输入脚。

### DEV-D05.T2
PASS：T1=2450FB15A050 p1:1不平衡、2/5地、3/4平衡、6NC；T2=0896BM15E0025 p1:1不平衡、2/5/6地、3/4平衡。两者为RF Balun，非开关续流线圈。 T1.6已NC，T1.2/.5接地；T2.2/.5/.6均接GND，其他端各进对应RF路径，无未处置输入脚。

### DEV-D05.U1
PASS：U1全部49物理脚已核：供电/地均入正确网，RF/SPI/IQ/RSTN均使用；未用CLKO U1.22、FEA24/FEB24 U1.1/.2和FEA09/FEB09 U1.11/.12为输出且已NC。Atmel p12建议未用CLKO在初始化关闭，作为配置移交；不把未用输出当悬空输入。仅关闭引脚处置，主机高阻期RSTN/SELN默认态另待M03。

### DEV-D05.U2
needs_human：U2准确物料/脚义尚需原厂资料：原图part=6TG2600001、symbol=Oscillator:FT5HN；网表连接可读但不能把库符号当独立厂商脚表。

### DEV-E01.J1
needs_human：J1准确物料/脚义尚需原厂资料：原图part=10132797-033100LF、symbol=Connector_Generic_MountingPin:Conn_02x15_Counter_Clockwise_MountingPin；网表连接可读但不能把库符号当独立厂商脚表。

### DEV-E01.J2
needs_human：J2符号1中心/2壳与原图SMA角色一致，但CONSMA003.062原厂图下载403，尚不能独立确认精确料号的物理引脚/封装映射。

### DEV-E01.J3
needs_human：J3符号1中心/2壳与原图SMA角色一致，但CONSMA003.062原厂图下载403，尚不能独立确认精确料号的物理引脚/封装映射。

### DEV-Q01.DATASHEETS
needs_human：当前审计required=4个物料身份，U1/T1/T2已绑定原厂PDF，D_TVS仍缺本地文件；更关键的是U2因Crystal封装被分类为crystal而未入必需手册清单，6TG2600001数据仍需补。

### DOC-D01.BOARD
PASS：逐值核对：C1/C2/C4/C5/C6/C9/C10/C11–14=1uF，C7/C8=1.8pF，L1=5.6nH；R2/R19=0Ω、R7/R10/R13/R16=47Ω。占位R仅存在DNP偏置选件，不是已贴阻值缺失；未见4.7F等量级异常。

### DOC-D02.BOARD
needs_human：J1各SPI/IQ/RSTN及SMA可作电气观察点，板上无独立TP；缺测试/夹具策略，无法判应增加哪些测试节点，不能按“没有TP位号”直接报缺陷。

### DOC-Q01.INPUT-CONSISTENCY
PASS：源提交b1027cf固定；根图SHA256与catalog一致；KiCad10.0.7导网表strict=true、41器件、1页；本次直接导出的PDF与网表同源，原生DNP保留。完整git tree仅电路/库/README/LICENSE等，无独立BOM；没有声称BOM与实物核验。

### DOC-T01.NATIVE
PASS：仅按原生native装配：C3/R1及8只未定值偏置R8/R9/R11/R12/R14/R15/R17/R18不贴；R2/R19=0、R7/R10/R13/R16=47Ω贴；TCXO供入及TX四路串阻各完整，不将DNP R当上拉或短路。

### DOC-V01.1
PASS：已目检本次KiCad10.0.7导出单页PDF全页和TCXO/RF/TX区：NC、DNP红叉、RF24/RF09、R2接地、T1/T2端号与图框Rev.r0.2可辨；无已证实遮挡/极性错误。导出显示器版本10.0.7不冒充源设计KiCad7版本。

### DOC-V02.BOARD
PASS：图框Amalthea/r0.2/2023-03-25与源图一致；RF09/24、PICO/POCI、TX/RX语义和U1脚义一致。catalog“调试适配器”是评测目录元数据错误，不是原图遗留命名缺陷。

### DRV-C01.T1-UNRESOLVED.T1
NA：T1=2450FB15A050 p1:1不平衡、2/5地、3/4平衡、6NC；T2=0896BM15E0025 p1:1不平衡、2/5/6地、3/4平衡。两者为RF Balun，非开关续流线圈。 无直流开关磁化/关断储能机制，不适用续流钳位拓扑及其额定审查。

### DRV-C01.T2-UNRESOLVED.T2
NA：T1=2450FB15A050 p1:1不平衡、2/5地、3/4平衡、6NC；T2=0896BM15E0025 p1:1不平衡、2/5/6地、3/4平衡。两者为RF Balun，非开关续流线圈。 无直流开关磁化/关断储能机制，不适用续流钳位拓扑及其额定审查。

### DRV-T01.T1-UNRESOLVED.T1
NA：T1=2450FB15A050 p1:1不平衡、2/5地、3/4平衡、6NC；T2=0896BM15E0025 p1:1不平衡、2/5/6地、3/4平衡。两者为RF Balun，非开关续流线圈。 无直流开关磁化/关断储能机制，不适用续流钳位拓扑及其额定审查。

### DRV-T01.T2-UNRESOLVED.T2
NA：T1=2450FB15A050 p1:1不平衡、2/5地、3/4平衡、6NC；T2=0896BM15E0025 p1:1不平衡、2/5/6地、3/4平衡。两者为RF Balun，非开关续流线圈。 无直流开关磁化/关断储能机制，不适用续流钳位拓扑及其额定审查。

### NET-A07.H1-1-21d5b9
NA：H1.1是Mechanical:MountingHole_Pad单焊盘，原图p1明确为MountingHole且NC；没有逻辑输入或片内偏置要求。符号electrical_type=input不能赋予安装孔有源脚义。

### NET-A07.H2-1-fac3b9
NA：H2.1是Mechanical:MountingHole_Pad单焊盘，原图p1明确为MountingHole且NC；没有逻辑输入或片内偏置要求。符号electrical_type=input不能赋予安装孔有源脚义。

### PRO-D03.J1
needs_human：J1：D1跨/RF24-GND、D2跨/RF09-GND，经C9/C10和Balun连接U1。原图手册链接404；官网可检索Rev1.1 PDF预览（未成功本地下载），未锁定系统RF/DC偏置及ESD波形/源阻抗、匹配网络对残压的传递。不能拿5V VRWM或14V典型TLP钳位直接证明U1±模拟脚安全；需按实际事件比较。

### PRO-D03.J2
needs_human：J2：D1跨/RF24-GND、D2跨/RF09-GND，经C9/C10和Balun连接U1。原图手册链接404；官网可检索Rev1.1 PDF预览（未成功本地下载），未锁定系统RF/DC偏置及ESD波形/源阻抗、匹配网络对残压的传递。不能拿5V VRWM或14V典型TLP钳位直接证明U1±模拟脚安全；需按实际事件比较。

### PRO-D03.J3
needs_human：J3：D1跨/RF24-GND、D2跨/RF09-GND，经C9/C10和Balun连接U1。原图手册链接404；官网可检索Rev1.1 PDF预览（未成功本地下载），未锁定系统RF/DC偏置及ESD波形/源阻抗、匹配网络对残压的传递。不能拿5V VRWM或14V典型TLP钳位直接证明U1±模拟脚安全；需按实际事件比较。

### PRO-D04.J1
needs_human：J1：D1跨/RF24-GND、D2跨/RF09-GND，经C9/C10和Balun连接U1。原图手册链接404；官网可检索Rev1.1 PDF预览（未成功本地下载），未锁定系统RF/DC偏置及ESD波形/源阻抗、匹配网络对残压的传递。不能拿5V VRWM或14V典型TLP钳位直接证明U1±模拟脚安全；需按实际事件比较。

### PRO-D04.J2
needs_human：J2：D1跨/RF24-GND、D2跨/RF09-GND，经C9/C10和Balun连接U1。原图手册链接404；官网可检索Rev1.1 PDF预览（未成功本地下载），未锁定系统RF/DC偏置及ESD波形/源阻抗、匹配网络对残压的传递。不能拿5V VRWM或14V典型TLP钳位直接证明U1±模拟脚安全；需按实际事件比较。

### PRO-D04.J3
needs_human：J3：D1跨/RF24-GND、D2跨/RF09-GND，经C9/C10和Balun连接U1。原图手册链接404；官网可检索Rev1.1 PDF预览（未成功本地下载），未锁定系统RF/DC偏置及ESD波形/源阻抗、匹配网络对残压的传递。不能拿5V VRWM或14V典型TLP钳位直接证明U1±模拟脚安全；需按实际事件比较。

### PRO-D05.BOARD
needs_human：无受控FMEA范围/关键功能清单；已识别J1误接/掉电注入、D1/D2开短和U2失钟到RF功能的路径，但“实验SDR”推断不能替代损坏/可接受后果和恢复时间要求。

### PRO-D06.BOARD
needs_human：无受控FMEA范围/关键功能清单；已识别J1误接/掉电注入、D1/D2开短和U2失钟到RF功能的路径，但“实验SDR”推断不能替代损坏/可接受后果和恢复时间要求。

### PRO-E02.D1-02c212
needs_human：D1：D1跨/RF24-GND、D2跨/RF09-GND，经C9/C10和Balun连接U1。原图手册链接404；官网可检索Rev1.1 PDF预览（未成功本地下载），未锁定系统RF/DC偏置及ESD波形/源阻抗、匹配网络对残压的传递。不能拿5V VRWM或14V典型TLP钳位直接证明U1±模拟脚安全；需按实际事件比较。

### PRO-E02.D2-235b1c
needs_human：D2：D1跨/RF24-GND、D2跨/RF09-GND，经C9/C10和Balun连接U1。原图手册链接404；官网可检索Rev1.1 PDF预览（未成功本地下载），未锁定系统RF/DC偏置及ESD波形/源阻抗、匹配网络对残压的传递。不能拿5V VRWM或14V典型TLP钳位直接证明U1±模拟脚安全；需按实际事件比较。

### PWR-C01.3V3
needs_human：PWR-C01对象+3V3：U1 p187允许VDD1.8–3.6V、−40..85°C；p203–204各状态电流多为典型，双频同时工作和U2电流/上游能力未知。+3V3仅名义3.3V，不能据此保证供电/温度/噪声或启动全过程。

### PWR-C09.DECAP-191AC03515D7BF7DBFBB.NET-U1-AVDD1
needs_human：U1 C4/C5/C6各名义1uF；p188 Table10-4允许100nF–10000nF，名义值在窗内（下界裕量900nF、上界9000nF），但实际温度/偏压下Ceff与稳定性要按本料号和工作窗核，不把名义裕量当保证。

### PWR-C09.DECAP-1F14371D2C473775C9EB.3V3
needs_human：U1外供电旁路C2+C11–14名义5uF，U2处C1=1uF，同+3V3网合计6uF；U1 p11只给每脚Cdec接法，未给外供电组强制总容量。缺源阻抗/脉冲负载与U2手册，不能将同网总和当动态裕量。

### PWR-C09.DECAP-628A077E270C9A7FD1E2.NET-U1-DVDD
needs_human：U1 C4/C5/C6各名义1uF；p188 Table10-4允许100nF–10000nF，名义值在窗内（下界裕量900nF、上界9000nF），但实际温度/偏压下Ceff与稳定性要按本料号和工作窗核，不把名义裕量当保证。

### PWR-C09.DECAP-9034B6404C9FDD63F76C.3V3
needs_human：U1外供电旁路C2+C11–14名义5uF，U2处C1=1uF，同+3V3网合计6uF；U1 p11只给每脚Cdec接法，未给外供电组强制总容量。缺源阻抗/脉冲负载与U2手册，不能将同网总和当动态裕量。

### PWR-C09.DECAP-CE5540BFB0C92787AA88.NET-U1-AVDD0
needs_human：U1 C4/C5/C6各名义1uF；p188 Table10-4允许100nF–10000nF，名义值在窗内（下界裕量900nF、上界9000nF），但实际温度/偏压下Ceff与稳定性要按本料号和工作窗核，不把名义裕量当保证。

### PWR-C10.DECAP-191AC03515D7BF7DBFBB.NET-U1-AVDD1
needs_human：U1 电容均为0402无极性MLCC，非电解耐久件；名义1uF/1.8pF可读。需确定Net-(U1-AVDD1)的持续/脉冲工作窗及温度，再按最弱档/所选MLCC核有效容量和耐压，不虚构寿命或厂家参数。

### PWR-C10.DECAP-1F14371D2C473775C9EB.3V3
needs_human：U2 电容均为0402无极性MLCC，非电解耐久件；名义1uF/1.8pF可读。需确定+3V3的持续/脉冲工作窗及温度，再按最弱档/所选MLCC核有效容量和耐压，不虚构寿命或厂家参数。

### PWR-C10.DECAP-628A077E270C9A7FD1E2.NET-U1-DVDD
needs_human：U1 电容均为0402无极性MLCC，非电解耐久件；名义1uF/1.8pF可读。需确定Net-(U1-DVDD)的持续/脉冲工作窗及温度，再按最弱档/所选MLCC核有效容量和耐压，不虚构寿命或厂家参数。

### PWR-C10.DECAP-9034B6404C9FDD63F76C.3V3
needs_human：U1 电容均为0402无极性MLCC，非电解耐久件；名义1uF/1.8pF可读。需确定+3V3的持续/脉冲工作窗及温度，再按最弱档/所选MLCC核有效容量和耐压，不虚构寿命或厂家参数。

### PWR-C10.DECAP-CE5540BFB0C92787AA88.NET-U1-AVDD0
needs_human：U1 电容均为0402无极性MLCC，非电解耐久件；名义1uF/1.8pF可读。需确定Net-(U1-AVDD0)的持续/脉冲工作窗及温度，再按最弱档/所选MLCC核有效容量和耐压，不虚构寿命或厂家参数。

### PWR-C14.3V3
needs_human：PWR-C14对象+3V3：U1 p187允许VDD1.8–3.6V、−40..85°C；p203–204各状态电流多为典型，双频同时工作和U2电流/上游能力未知。+3V3仅名义3.3V，不能据此保证供电/温度/噪声或启动全过程。

### PWR-C19.BOARD
needs_human：PWR-C19对象全板：U1 p187允许VDD1.8–3.6V、−40..85°C；p203–204各状态电流多为典型，双频同时工作和U2电流/上游能力未知。+3V3仅名义3.3V，不能据此保证供电/温度/噪声或启动全过程。

### PWR-D01.DECOUPLING-INVENTORY
needs_human：U1已按官方全49脚分为外部+3V3与三个独立片内输出组；U2尚无6TG2600001准确脚表，符号FT5HN的GND/NC不能替代原厂依据。T1/T2不是需去耦有源IC。

### PWR-D02.DECAP-191AC03515D7BF7DBFBB.NET-U1-AVDD1
PASS：Atmel-42415E pp7–11 Table2-1/Figure3-1以及p75 §6.6：C4/C5/C6分别跨独立片内输出到GND，输出彼此不短接、无外供负载，符合专用补偿连接。

### PWR-D02.DECAP-1F14371D2C473775C9EB.3V3
needs_human：PWR-D02.DECAP-1F14371D2C473775C9EB.3V3：网表对象{"ref": "U2", "nodes": ["U2.4"], "return_nodes": ["U2.1", "U2.2"], "nets": ["+3V3"], "return_nets": ["GND"], "state": "native", "decoupling_group": "DECAP-1f14371d2c473775c9eb", "decoupling_inventory_digest": "44919cb9e92a1de67266ff7f4fbb75cab700504d70630aa9088a22ce5280ca39", "net": "+3V3"}已核；尚无足以关闭本条判据的对端/工况或厂家独立界限，保留人工决定，不据名称判不适用。

### PWR-D02.DECAP-628A077E270C9A7FD1E2.NET-U1-DVDD
PASS：Atmel-42415E pp7–11 Table2-1/Figure3-1以及p75 §6.6：C4/C5/C6分别跨独立片内输出到GND，输出彼此不短接、无外供负载，符合专用补偿连接。

### PWR-D02.DECAP-9034B6404C9FDD63F76C.3V3
PASS：Atmel-42415E pp7–11 Table2-1/Figure3-1以及p75 §6.6：EVDD/DEVDD五个供电脚同接+3V3，C2/C11–14接GND，本图满足同电位和并联旁路电气接法；物理距离/回路交PCB。

### PWR-D02.DECAP-CE5540BFB0C92787AA88.NET-U1-AVDD0
PASS：Atmel-42415E pp7–11 Table2-1/Figure3-1以及p75 §6.6：C4/C5/C6分别跨独立片内输出到GND，输出彼此不短接、无外供负载，符合专用补偿连接。

### PWR-D04.BOARD
needs_human：PWR-D04对象全板：U1 p187允许VDD1.8–3.6V、−40..85°C；p203–204各状态电流多为典型，双频同时工作和U2电流/上游能力未知。+3V3仅名义3.3V，不能据此保证供电/温度/噪声或启动全过程。

### PWR-T01.3V3
PASS：供入路径J1.15与J1.16均→+3V3→U1.15/.21/.29/.39/.46、U2.4及所有贴装3V3旁路；返回J1.2/.14/.17/.29→GND。片内AVDD0/AVDD1/DVDD各仅接1uF不与外轨短接。只关闭原图电源树，供电能力/窗口另判。

### PWR-T03.DECAP-191AC03515D7BF7DBFBB.NET-U1-AVDD1
PASS：U1.47→Net-(U1-AVDD1)→C4.1→GND→U1地脚；全部贴装，无串联隔断。

### PWR-T03.DECAP-1F14371D2C473775C9EB.3V3
needs_human：图上U2.4/C1.1在+3V3，C1.2/U2.1/.2在GND；这是可读连通事实，但6TG2600001精确脚表未得，不能确认官方供电/返回分组。保留局部拓扑，不把FT5HN库符号当准确型号证据。

### PWR-T03.DECAP-628A077E270C9A7FD1E2.NET-U1-DVDD
PASS：U1.37→Net-(U1-DVDD)→C6.1→GND→U1地脚；全部贴装，无串联隔断。

### PWR-T03.DECAP-9034B6404C9FDD63F76C.3V3
PASS：U1.15→+3V3→C2/C11–C14→GND→U1地脚；全部贴装，无串联隔断。

### PWR-T03.DECAP-CE5540BFB0C92787AA88.NET-U1-AVDD0
PASS：U1.14→Net-(U1-AVDD0)→C5.1→GND→U1地脚；全部贴装，无串联隔断。

### PWR-T04.NATIVE.SUPERVISION-RAILS
needs_human：U1 p13–14含POR，p188上升阈值1.55–1.65V、下降1.45–1.55V，最低工作1.8V；不能从有POR推保证棕断复位。J1.26直接到RSTN，需对端复位/供电斜率/阈值与时序合同；不因缺外置监控器直接判缺陷。

### REQ-C01.BOARD
needs_human：REQ-C01：README仅证明实验SDR用途推断，无带编号受控需求/环境/接口/故障范围；不得把catalog或本次分析假设写成客户要求。本项需要设计者确定本条输入或适用范围。

### REQ-D02.BOARD
needs_human：REQ-D02：README仅证明实验SDR用途推断，无带编号受控需求/环境/接口/故障范围；不得把catalog或本次分析假设写成客户要求。本项需要设计者确定本条输入或适用范围。

### REQ-D03.BOARD
needs_human：REQ-D03：README仅证明实验SDR用途推断，无带编号受控需求/环境/接口/故障范围；不得把catalog或本次分析假设写成客户要求。本项需要设计者确定本条输入或适用范围。

### REQ-D04.BOARD
needs_human：REQ-D04：README仅证明实验SDR用途推断，无带编号受控需求/环境/接口/故障范围；不得把catalog或本次分析假设写成客户要求。本项需要设计者确定本条输入或适用范围。

### REQ-D05.BOARD
needs_human：无受控FMEA范围/关键功能清单；已识别J1误接/掉电注入、D1/D2开短和U2失钟到RF功能的路径，但“实验SDR”推断不能替代损坏/可接受后果和恢复时间要求。

### REQ-Q01.REQUIREMENTS
needs_human：REQ-Q01：README仅证明实验SDR用途推断，无带编号受控需求/环境/接口/故障范围；不得把catalog或本次分析假设写成客户要求。本项需要设计者确定本条输入或适用范围。

### REQ-Q02.CHAINS
needs_human：REQ-Q02：README仅证明实验SDR用途推断，无带编号受控需求/环境/接口/故障范围；不得把catalog或本次分析假设写成客户要求。本项需要设计者确定本条输入或适用范围。

### REQ-Q03.STATES
needs_human：REQ-Q03：README仅证明实验SDR用途推断，无带编号受控需求/环境/接口/故障范围；不得把catalog或本次分析假设写成客户要求。本项需要设计者确定本条输入或适用范围。

### REQ-Q04.HISTORY
NA：首次审查固定提交，无提供的旧审查意见、改版闭环要求或可验证历史基线；不借其他板历史作本板结论。

### REQ-Q07.ANALOG
NA：本板模拟RF端由RF-U1功能持有，无独立运放/ADC/通用模拟采样电路；不能把RF收发器内部ADC当板外ANALOG电路。

### REQ-Q07.CLOCK
needs_human：REQ-Q07：README仅证明实验SDR用途推断，无带编号受控需求/环境/接口/故障范围；不得把catalog或本次分析假设写成客户要求。本项需要设计者确定本条输入或适用范围。

### REQ-Q07.HSSERIAL
needs_human：REQ-Q07：README仅证明实验SDR用途推断，无带编号受控需求/环境/接口/故障范围；不得把catalog或本次分析假设写成客户要求。本项需要设计者确定本条输入或适用范围。

### REQ-Q07.RF
needs_human：REQ-Q07：README仅证明实验SDR用途推断，无带编号受控需求/环境/接口/故障范围；不得把catalog或本次分析假设写成客户要求。本项需要设计者确定本条输入或适用范围。

### REQ-Q07.SPI
needs_human：U1.41/42/43/44与J1.4/5/28/27构成实际SPI；当前RF/HSSERIAL成员覆盖了物理互连，却未生成SPI专属功能/掉电注入问题。需显式建模多接口IC，不能因候选0或UART命名就判无SPI。

### REQ-Q07.UART
NA：核p1 U1.25–36为LVDS IQ，U1.41–44为SPI，无UART RX/TX或RS232收发器；TXD/RXD命名属于RF基带IQ，不能按UART套用。

### REQ-Q08.BOARD
PASS：全41项中10个原生DNP不参与通路；29个电气器件归RF/CLOCK/IQ，H1/H2明确为无电气功能安装孔。无USB、CAN、I2C、隔离、DC48/AC/工业输入等器件；U1是RF/SPI/LVDS多功能端点。此处只审未归属清单，不关闭SPI遗漏。

### SIG-C07.IF-CLOCK-U2-RF-U1
needs_human：U2.3→Net-(U2-OUT)→R19(0Ω)→Net-(U1-TCXO)→U1.17；U1.18→R2(0Ω)→GND；R1/C3均DNP。Atmel-42415E pp7–11 Table2-1/Figure3-1及p68 §6.4.3要求DC耦合且XTAL2接地。 接收端p68要求26MHz clipped-sine、600–1600mVpp；6TG2600001准确手册未得，不能由TCXO名称推输出幅度/电源/使能。

### SIG-C07.IF-IQ-J1-RF-U1
needs_human：U1 p22–23为128Mb/s IQ、64MHz时钟，可选0.2V共模SLVDS或1.2V共模IEEE模式；p205–207给两类驱动/接收窗口，TX每线47Ω。未提供Cynthion端电压模式/收发驱动/端接/时序，无法完成双端预算。

### SIG-C13.CLOCK-U2.C1
needs_human：U2.3→Net-(U2-OUT)→R19(0Ω)→Net-(U1-TCXO)→U1.17；U1.18→R2(0Ω)→GND；R1/C3均DNP。Atmel-42415E pp7–11 Table2-1/Figure3-1及p68 §6.4.3要求DC耦合且XTAL2接地。 接收端p68要求26MHz clipped-sine、600–1600mVpp；6TG2600001准确手册未得，不能由TCXO名称推输出幅度/电源/使能。

### SIG-C13.IQ-J1.J1
needs_human：U1 p22–23为128Mb/s IQ、64MHz时钟，可选0.2V共模SLVDS或1.2V共模IEEE模式；p205–207给两类驱动/接收窗口，TX每线47Ω。未提供Cynthion端电压模式/收发驱动/端接/时序，无法完成双端预算。

### SIG-D12.RF-U1-RECEIVE.C10
needs_human：RF-U1的receive状态：U1 p3为双频IQ、p75列内部AVDD/DVDD开关状态；T2 p1仅保证863–928MHz，T1 p1为2400–2500MHz，均有匹配/滤波接口。板上C7/C8=1.8pF/L1=5.6nH及C9/C10=1uF路径已追；没有受控目标频带、输出功率/增益/噪声/睡眠预算和Cynthion接口模式，不能把U1覆盖389.5–510MHz等芯片能力当本板全频带性能保证。无需实测才能写出的系统指标先由设计者锁定；射频匹配实现交PCB/样机。

### SIG-D12.RF-U1-SLEEP.C10
needs_human：RF-U1的sleep状态：U1 p3为双频IQ、p75列内部AVDD/DVDD开关状态；T2 p1仅保证863–928MHz，T1 p1为2400–2500MHz，均有匹配/滤波接口。板上C7/C8=1.8pF/L1=5.6nH及C9/C10=1uF路径已追；没有受控目标频带、输出功率/增益/噪声/睡眠预算和Cynthion接口模式，不能把U1覆盖389.5–510MHz等芯片能力当本板全频带性能保证。无需实测才能写出的系统指标先由设计者锁定；射频匹配实现交PCB/样机。

### SIG-D12.RF-U1-TRANSMIT.C10
needs_human：RF-U1的transmit状态：U1 p3为双频IQ、p75列内部AVDD/DVDD开关状态；T2 p1仅保证863–928MHz，T1 p1为2400–2500MHz，均有匹配/滤波接口。板上C7/C8=1.8pF/L1=5.6nH及C9/C10=1uF路径已追；没有受控目标频带、输出功率/增益/噪声/睡眠预算和Cynthion接口模式，不能把U1覆盖389.5–510MHz等芯片能力当本板全频带性能保证。无需实测才能写出的系统指标先由设计者锁定；射频匹配实现交PCB/样机。

### SIG-D14.IQ-J1-RUN.J1
needs_human：U1 p22–23为128Mb/s IQ、64MHz时钟，可选0.2V共模SLVDS或1.2V共模IEEE模式；p205–207给两类驱动/接收窗口，TX每线47Ω。未提供Cynthion端电压模式/收发驱动/端接/时序，无法完成双端预算。

### SIG-E02.RF09.RF09-P
NA：T1=2450FB15A050 p1:1不平衡、2/5地、3/4平衡、6NC；T2=0896BM15E0025 p1:1不平衡、2/5/6地、3/4平衡。两者为RF Balun，非开关续流线圈。 ['/RF09_N', '/RF09_P']是U1双向RF模拟端口，按p9 §2.2.1的RF负载/匹配要求审；不是LVDS数字链路，不比较数字接收共模或100Ω数字端接。

### SIG-E02.RF24.RF24-P
NA：T1=2450FB15A050 p1:1不平衡、2/5地、3/4平衡、6NC；T2=0896BM15E0025 p1:1不平衡、2/5/6地、3/4平衡。两者为RF Balun，非开关续流线圈。 ['/RF24_N', '/RF24_P']是U1双向RF模拟端口，按p9 §2.2.1的RF负载/匹配要求审；不是LVDS数字链路，不比较数字接收共模或100Ω数字端接。

### SIG-E02.RXCLK.RXCLK-P
needs_human：U1 p22–23为128Mb/s IQ、64MHz时钟，可选0.2V共模SLVDS或1.2V共模IEEE模式；p205–207给两类驱动/接收窗口，TX每线47Ω。未提供Cynthion端电压模式/收发驱动/端接/时序，无法完成双端预算。

### SIG-E02.RXD09.RXD09-P
needs_human：U1 p22–23为128Mb/s IQ、64MHz时钟，可选0.2V共模SLVDS或1.2V共模IEEE模式；p205–207给两类驱动/接收窗口，TX每线47Ω。未提供Cynthion端电压模式/收发驱动/端接/时序，无法完成双端预算。

### SIG-E02.RXD24.RXD24-P
needs_human：U1 p22–23为128Mb/s IQ、64MHz时钟，可选0.2V共模SLVDS或1.2V共模IEEE模式；p205–207给两类驱动/接收窗口，TX每线47Ω。未提供Cynthion端电压模式/收发驱动/端接/时序，无法完成双端预算。

### SIG-E02.TXCLK.TXCLK-P
needs_human：U1 p22–23为128Mb/s IQ、64MHz时钟，可选0.2V共模SLVDS或1.2V共模IEEE模式；p205–207给两类驱动/接收窗口，TX每线47Ω。未提供Cynthion端电压模式/收发驱动/端接/时序，无法完成双端预算。

### SIG-E02.TXD.TXD-P
needs_human：U1 p22–23为128Mb/s IQ、64MHz时钟，可选0.2V共模SLVDS或1.2V共模IEEE模式；p205–207给两类驱动/接收窗口，TX每线47Ω。未提供Cynthion端电压模式/收发驱动/端接/时序，无法完成双端预算。

### SIG-T01.IQ-J1-RUN.J1
needs_human：J1五对IQ已逐路核板内P/N与47Ω串阻，尚无Cynthion对端精确版本/脚表，完整高速链路未能关闭。

### SIG-T01.RF09-P
PASS：U1.8/RFP09→/RF09_P→T2.4；U1.9/RFN09→/RF09_N→T2.3；T2.1经C10到J3中心。Johanson T2 p1定义3/4平衡端，未发现P/N配对断路；不是LVDS电平放行。

### SIG-T01.RF24-P
PASS：U1.4/RFP24→C8(1.8pF)→T1.4、U1.5/RFN24→C7(1.8pF)→T1.3；L1=5.6nH跨T1.3/.4；T1.1经C9到J2中心；T1.2/.5接GND、.6NC。仅核RF两支路拓扑，不证明匹配/带宽。

### SIG-T01.RXCLK-P
PASS：J1.11→U1.34 RXCLKP；J1.10→U1.33 RXCLKN；原图J1标签与U1物理脚极性一致。只关闭板内拓扑，尚无Cynthion对端脚表，不能证明整机端到端。

### SIG-T01.RXD09-P
PASS：J1.13→U1.31 RXDP09；J1.12→U1.30 RXDN09；原图J1标签与U1物理脚极性一致。只关闭板内拓扑，尚无Cynthion对端脚表，不能证明整机端到端。

### SIG-T01.RXD24-P
PASS：J1.9→U1.36 RXDP24；J1.8→U1.35 RXDN24；原图J1标签与U1物理脚极性一致。只关闭板内拓扑，尚无Cynthion对端脚表，不能证明整机端到端。

### SIG-T01.TXCLK-P
PASS：J1.18→R10=47Ω→U1.26 TXCLKP；J1.19→R7=47Ω→U1.25 TXCLKN；原图J1标签与U1物理脚极性一致。只关闭板内拓扑，尚无Cynthion对端脚表，不能证明整机端到端。

### SIG-T01.TXD-P
PASS：J1.20→R16=47Ω→U1.28 TXDP；J1.21→R13=47Ω→U1.27 TXDN；原图J1标签与U1物理脚极性一致。只关闭板内拓扑，尚无Cynthion对端脚表，不能证明整机端到端。

### SIG-T03.RF09.RF09-P
NA：T1=2450FB15A050 p1:1不平衡、2/5地、3/4平衡、6NC；T2=0896BM15E0025 p1:1不平衡、2/5/6地、3/4平衡。两者为RF Balun，非开关续流线圈。 ['/RF09_N', '/RF09_P']是U1双向RF模拟端口，按p9 §2.2.1的RF负载/匹配要求审；不是LVDS数字链路，不比较数字接收共模或100Ω数字端接。

### SIG-T03.RF24.RF24-P
NA：T1=2450FB15A050 p1:1不平衡、2/5地、3/4平衡、6NC；T2=0896BM15E0025 p1:1不平衡、2/5/6地、3/4平衡。两者为RF Balun，非开关续流线圈。 ['/RF24_N', '/RF24_P']是U1双向RF模拟端口，按p9 §2.2.1的RF负载/匹配要求审；不是LVDS数字链路，不比较数字接收共模或100Ω数字端接。

### SIG-T03.RXCLK.RXCLK-P
needs_human：SIG-T03.RXCLK.RXCLK-P：网表对象{"net": "/RXCLK_P", "state": "native", "nets": ["/RXCLK_N", "/RXCLK_P"], "diff_pair": "RXCLK", "diff_levels_digest": "1585c6d9f34a4532a61357dd2d1331b95e60045d4f27de7495f1bfeba1b95b84"}已核；尚无足以关闭本条判据的对端/工况或厂家独立界限，保留人工决定，不据名称判不适用。

### SIG-T03.RXD09.RXD09-P
needs_human：SIG-T03.RXD09.RXD09-P：网表对象{"net": "/RXD09_P", "state": "native", "nets": ["/RXD09_N", "/RXD09_P"], "diff_pair": "RXD09", "diff_levels_digest": "1585c6d9f34a4532a61357dd2d1331b95e60045d4f27de7495f1bfeba1b95b84"}已核；尚无足以关闭本条判据的对端/工况或厂家独立界限，保留人工决定，不据名称判不适用。

### SIG-T03.RXD24.RXD24-P
needs_human：SIG-T03.RXD24.RXD24-P：网表对象{"net": "/RXD24_P", "state": "native", "nets": ["/RXD24_N", "/RXD24_P"], "diff_pair": "RXD24", "diff_levels_digest": "1585c6d9f34a4532a61357dd2d1331b95e60045d4f27de7495f1bfeba1b95b84"}已核；尚无足以关闭本条判据的对端/工况或厂家独立界限，保留人工决定，不据名称判不适用。

### SIG-T03.TXCLK.TXCLK-P
needs_human：Atmel p23 §4.5.2明确U1内部含100Ω差分端接与开路fail-safe；R7/R10/R13/R16为47Ω串阻，DNP偏置不计入。无需以“缺外置100Ω”报错，但需Cynthion驱动模式/幅度/源阻抗核串阻衰减。

### SIG-T03.TXD.TXD-P
needs_human：Atmel p23 §4.5.2明确U1内部含100Ω差分端接与开路fail-safe；R7/R10/R13/R16为47Ω串阻，DNP偏置不计入。无需以“缺外置100Ω”报错，但需Cynthion驱动模式/幅度/源阻抗核串阻衰减。

### SIG-T04.IF-CLOCK-U2-RF-U1
PASS：U2.3→Net-(U2-OUT)→R19(0Ω)→Net-(U1-TCXO)→U1.17；U1.18→R2(0Ω)→GND；R1/C3均DNP。Atmel-42415E pp7–11 Table2-1/Figure3-1及p68 §6.4.3要求DC耦合且XTAL2接地。 方向为U2 OUT到U1输入，R2不承载时钟输出；幅度规格不由方向关闭。

### SIG-T04.IF-IQ-J1-RF-U1
needs_human：板内SPI方向：J1.28→U1.43 MOSI，U1.44 MISO→J1.27，J1.4→U1.41 SCLK，J1.5→U1.42 SELN，U1.40 IRQ→J1.3，J1.26→U1.13 RSTN；尚无对端同版针序，PICO/POCI名称本身不能证明整链语义。

## 逐功能范围

### FN-CLOCK-U2
CLOCK-U2（C1、R19、R2、U2）在 run 各状态下，晶体/有源时钟/RTC 是否按料号条件起振并满足负载与噪声要求
已核局部 2 项；待判 16 项。完整ID列表见function-review.json。

### FN-EXT-J1
连接器 EXT-J1 的针定义、载流与对外防护是否成立
已核局部 0 项；待判 4 项。完整ID列表见function-review.json。

### FN-EXT-J2
连接器 EXT-J2 的针定义、载流与对外防护是否成立
已核局部 0 项；待判 4 项。完整ID列表见function-review.json。

### FN-EXT-J3
连接器 EXT-J3 的针定义、载流与对外防护是否成立
已核局部 0 项；待判 4 项。完整ID列表见function-review.json。

### FN-IF-CLOCK-U2-RF-U1
IF-CLOCK-U2~RF-U1（CLOCK-U2、RF-U1）之间的网络 Net-(U1-TCXO)、Net-(U1-XTAL2)，方向、电平与跨域注入是否都成立
已核局部 1 项；待判 1 项。完整ID列表见function-review.json。

### FN-IF-IQ-J1-RF-U1
IF-IQ-J1~RF-U1（IQ-J1、RF-U1）之间的网络 /IRQ、/PICO、/POCI、/RXCLK_N、/RXCLK_P、/RXD09_N、/RXD09_P、/RXD24_N、/RXD24_P、/SCLK、/~{RSTN}、/~{SELN}、Net-(U1-TXCLKN)、Net-(U1-TXCLKP)、Net-(U1-TXDN)、Net-(U1-TXDP)，方向、电平与跨域注入是否都成立
已核局部 0 项；待判 2 项。完整ID列表见function-review.json。

### FN-IQ-J1
IQ-J1（J1、R10、R13、R16、R7）在 run 各状态下，高速链路的耦合、映射、边带与差分连通是否按规范
已核局部 1 项；待判 11 项。完整ID列表见function-review.json。

### FN-RF-U1
RF-U1（C10、C11、C12、C13、C14、C2、C4、C5、C6、C7、C8、C9、D1、D2、J2、J3、L1、T1、T2、U1）在 receive/transmit/sleep 各状态下，天线路径、供电与噪声预算是否满足模组要求
已核局部 23 项；待判 34 项。完整ID列表见function-review.json。

### FN-SYS-MONITOR
需求要求监测的电源域（+3V3）是否都有监测点、阈值与动作
已核局部 0 项；待判 1 项。完整ID列表见function-review.json。

### FN-SYS-POWER
电源树（+3V3）每条轨的源、负载、电压窗口与功率预算是否成立，有没有无驱动或同基名混淆的轨
已核局部 1 项；待判 1 项。完整ID列表见function-review.json。

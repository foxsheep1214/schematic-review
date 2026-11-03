# 独立证据与归因说明

板：`vadivelvaishnavi--transformer_less_power_supply_kicad_pcb_design_project`；固定源 `60cf01ee9ff44718fd258eeae0f71823e3685706`；MIT。用途为推断，产品审查基线按任务指定industrial_telecom。

本轮不是准出结论。原生计划100项：31项有局部判定（21 PASS、2 FAIL、8 NA），69项按任务逐项分流needs_human，见[完整逐项表](check-disposition.json)。原生schema15没有needs_human及未定需求状态，故不编造VENDOR_DATUM或全板PASS；门禁保留FAIL。10条归因是不同根因/观察，不是10个硬件缺陷。

## 输入与核验

- KiCad10.0.7原生strict成功；18器件、9网、37物理端点，XML独立重建ref.pin→net与db逐点一致。
- 稀疏缓存未检出BOM/预览，按固定commit读取原始CSV后read_bom，18/18位号匹配；另独立对比Value/Footprint，未继承read_bom忽略Value列的盲区。
- 从当前原理图原生导出SVG并目检单页；源仓库旧截图仅作交叉线索，不替代当前渲染。图形、原始BOM、源电路和原厂PDF均只保留缓存。
- HardwareWiki只读find_parts检索；完整取得Vishay88503（p1/2）、onsemi MC7800/D Rev29（p1），另取TI SNOSBT0L（p1/3/4/6/13/17）及Microchip DS00954A（p1/2）。没有把Wiki二手实体页当手册保证。

## 电源与返回路径

J1.2 → C4（R3=1M并联）→ Net-(D1-A) → D1/D2桥臂；J1.1 → Net-(D3-A) → D3/D4桥臂。D1/D3阴极并到Net-(D1-K)，C1=0.1uf/C2=1000uf跨该母线与GND；U1.1入、.2地、.3到/5V与J2.1，C3=470uf跨/5V与J2.2=GND。D5/D6阴极到母线，阳极分别经R1/R2=20k回GND；R4=2.2k/D7 LED为另一母线负载。

所有GND为局部热地，0V声明只是本地参考，不是PE/安全隔离。18件全部按BOM空DNP贴装，唯一供电链包含全部器件；无数字总线、晶体、运放、MOSFET、变压器、独立保险丝或MOV。

## 有条件的独立算例（不作为已确认缺陷）

只为定位下一步需要确认的量：假定C4=2.2uF（225k常见标码解释，源文未确认），桥与负载工作正常，正弦源，无外部额外钳位，桥母线在35V附近缓慢变化；每只正向管按1.1V保守扣除。理想全波容降每周期移送电荷给平均供流 `I≈4*f*C*(sqrt(2)*Vac−Vbus−2*Vf)`。这是本轮独立电荷模型，不移植AN954的半波公式；没有源阻抗/相位/残压/实际二极管曲线，不能用它作波形或WCA保证。

在Vbus=35V时，齐纳即使VZ=0，两20k支路合计不超过3.5mA；LED即使Vf=0，2.2k支路不超过15.909mA；加TI家族IQ上界8.5mA和J2外部5mA，合计32.909mA。IQ的保证温度/输入条件仍须与实际工作点配对，此处仅为正常家族器件条件分支。

| 条件输入（非受控需求） | 2.2uF名义平均供流 | C4取1.98uF时 | 与32.909mA负载上界比较 |
|---|---:|---:|---|
| 115Vac/60Hz | 66.229mA | 59.607mA | 条件模型中仍有充电余流，35V不能维持电荷平衡 |
| 230Vac/50Hz | 126.750mA | 114.075mA | 条件模型中仍有充电余流，35V不能维持电荷平衡 |

这说明不能将两路“齐纳+20k”直接视为可靠母线钳位。只有确认真实输入、C4值、最小负载和外部钳位后才可将结论升级为电气FAIL。1N4001的VRRM=50V是桥端反向限制；桥正常工作时反压与实际桥端/母线有关，不能只见市电即把sqrt(2)*230V当作每只二极管常态反压。

C3在5V的储能为5.875mJ；C4若2.2uF，在230Vac峰值的能量约0.116J。前者不自动证明U1必坏，后者不等于实际浪涌全部耗在某只二极管；必须分别核故障状态、时域波形和准确器件/源阻抗。R3泄放的条件RC=2.2s；从325.27V到任意示例60V约3.72s；60V不是本项目或适用标准的已确认安全阈值，故不据此判放电合格/不合格。

## 逐条根因

### F01 · true_defect · D5/D6关键稳压值未定义（设计数据缺陷）

固定commit原图page1和原始BOM中两件Value=D_Zener、Datasheet=~，没有VZ/公差/MPN；两支路分别经R1/R2=20k到GND。类别已知不等于关键选值可实施。只确认设计数据不完整，不宣称已证实硬件过压；按SKILL③3.1及references/evidence-proportionality.md“复核每条证据不足”甲的缺设计值分支。

### F02 · false_alarm · 1N4001单二极管被手册标题核验提示为bridge_rectifier

audit首次4个TITLE_MISMATCH，补kind_reason后VERIFIED=5但仍留4个KIND_CONFLICT。Vishay88503 Rev29-Apr-2020 p1标题General Purpose Plastic Rectifier，Circuit configuration=Single，DO-41两端；bridge rectifier仅在额定表脚注For device using on bridge rectifier application。标题六行未命中时回退全页把应用脚注当角色。正确：diode；不能把四颗整流器分别认成封装整流桥。

### F03 · false_alarm · 电阻封装DIN0207误触发INDUSTRIAL_DI

最终计划REQ-Q07.INDUSTRIAL-DI的trigger逐条为R1-R4的R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal；catalog工业DI正则DIN?数字在完整part文本中命中封装。全板只有容降、整流、线性稳压和电源端子，没有24V DI接收器/传感器接口。正确应无该候选，当前项NA；非误判硬件失效。

### F04 · false_alarm · 通用非极性串联降压电容被套入MLCC有效容量格

FN-POWER-CONVERTER-U1.bounds的MLCC-EFFECTIVE-C列refs=C1,C4。C4的prim=Device:C、Value=225k、Footprint=C_Rect...FKS3_FKP3，位于J1.2与整流桥交流端之间，型号/介质并未核验；不能从“非电解”推出MLCC。封装只是薄膜候选线索，也不能反向冒充已选定FKS3。正确先留技术未知、核容降AC使用资格和容量，不自动索取MLCC直流偏压曲线。

### F05 · knowledge_gap · U1家族资料可核功能，采购厂家和温度档尚未锁定

原图/BOM=LM7805_TO220，链接为onsemi MC7800-D。TI SNOSBT0L p3及onsemi MC7800/D Rev29 p1均1输入/2地/3输出，均35V绝限；已取得两份完整PDF并核页。资料审计U1 AVAILABLE仅表示可读LM7805功能家族资料，不能证明采购onsemi或TI哪一温度后缀。需要厂家/完整订货码之后才核温度、精度及反向故障资格；没有把库符号链接不同本身判成采购冲突。

### F06 · needs_human · 市电输入、负载与中断目标缺少受控窗口

用途仅由固定README Overview与图面推断；没有用户需求文件。未给AC电压/频率容差、最小最大负载、温度、源阻抗、浪涌、上游保护、跌落测量点/保持目标。catalog和本轮指定industrial_telecom是审查基线，不自动变成230V额定或输出1A要求。Top50 G01-024/025有3个PWR-C18计划项，均需这些输入才能算C2/C3保持和恢复。

### F07 · needs_human · 空载母线可能高于7805耐压，条件算例尚不等于确认缺陷

C4=225k未受控；若按常见三位pF标码解释为2.2uF±10%，J2只取5mA，则在115Vac/60Hz及230Vac/50Hz条件下，母线35V时理想全波串容供流分别约66.24mA/126.75mA；两齐纳支路即使VZ=0最大仅3.5mA，R4支路上界15.91mA，再加IQ上界8.5mA和5mA外负载，合计32.91mA。两算例均不能在35V维持电荷平衡。模型、最弱容量支路及假设详见evidence-notes.md，非产品WCA或动态仿真。因真实输入、225k含义、负载/外部钳位均未确认，保持needs_human。桥后正常反压由桥端差分及母线决定，不能直接将325V线路峰值当每只1N4001的正常反压；先核母线。

### F08 · needs_human · 串容输入的峰值接入和上游切断配合未闭合

J1.2→C4→桥→C2，另一交流腿J1.1直接入桥；R3=1M跨C4，是并联泄放而非串联浪涌限流。全板没有F/NTC/MOV/串联限流电阻。Microchip AN954 DS00954A p2说明串阻用于浪涌限制；Vishay88503 p1的30A仅8.3ms半正弦单次条件，不能套任意尖峰。C4若2.2uF，在230Vac峰值时存能约0.116J（条件算例，不是额定值）；需接入相位、热重接/残压、回路阻抗和上游保护合同。未凭“没有熔丝”断言严重短路后果必然成立。

### F09 · needs_human · J2为非隔离热地输出，接触和对外设备边界未确定

J2.2直接到D2/D4阳极GND，J2.1为U1.3输出；全板无变压器或隔离器。Microchip AN954 p1明确无线路隔离；因此5V仅为本地差模名义输出，不能称SELV/安全可触及。源README已声明教育/仿真且非隔离，不存在有证据的隔离要求违约；只有在确认外露用户/接地仪器/第三方设备连接边界后才能确定电击/外发故障结论。PCB爬电/电气间隙与实物试验另属下游。

### F10 · needs_human · 470uF输出储能经7805反向释放的故障适用性待判

C3=470uF，5V时能量0.5*C*V²=5.875mJ；无输出阳极→输入阴极的外部保护二极管。TI SNOSBT0L p13 §8.1.1/Fig15仅说明Cout≤10uF通常可免保护，输入短地时大Cout可能经片内通路放电；p17 §10.2给外接二极管建议。C1/C2短路可使U1.1塌陷；但普通断输入时C2=1000uF、外接负载/采购变体未知，不能据“C3>10uF且无二极管”直接判全场景器件损坏。原生PWR-C05三态已问，非漏报；需原设计者锁输入短路/外供预偏置要求及准确器件资格。

## Top50漏报核对

50条逐条前提与网表对照见[top50-audit.json](top50-audit.json)。M01仅为PRO-C04逐源支路保护的计划漏问。G03-003/004按7805手册前提限定；G03-032已有PWR-C05；G03-037/038已有通用应力/极性检查及两组PWR-C10，不重复记漏检；无USB/总线/晶体/隔离器/MOSFET的条款排除其对象。

## 原厂定位

- [Vishay 88503](https://www.vishay.com/docs/88503/1n4001.pdf)：缓存为29-Apr-2020修订，p1 Single/DO-41/1N4001的VRRM=50V，p2电气/脉冲条件。在线文档可能已更新，本轮以缓存PDF哈希为准。
- [TI SNOSBT0L](https://www.ti.com/lit/ds/symlink/lm7800.pdf)：p3三脚；p4 35V绝限；p6保证条件；p13 §8.1.1和Fig15输入短路/输出储能；p17 §10.2反向保护。
- [Microchip DS00954A](https://ww1.microchip.com/downloads/en/Appnotes/00954A.pdf)：p1无线路隔离；p2串容供电及浪涌串阻；本板为全桥，不直接套半波公式。

## 记录边界与SR用法

输入轨只声明身份和HOT参考域，没有假填工作电压。AC_MAINS与POWER_PROTECTION的物理事实已明确，但原生候选只生成POWER_CONVERTER；在不改脚本、不手画circuits的限制下，features保留UNDETERMINED用于显示建模不足，绝不表示该板的市电身份有疑问。

原生结果不支持needs_human/未定需求，69项逐项记录在pending_checks及独立逐项表；不要把渲染的“资料不足0”理解为69项通过。未完成框架没有虚造OPEN或PASS结果。F01作为关键选值缺陷独立保留，原生功能fail只接受强制条款/数值越限证明，故对这类数据缺陷的证明承载仍有门禁错误；没有将方法要求冒充原厂电气限值。完整门禁错误保留缓存。

质量筛查另有1组重复理由提示，覆盖PRO-C02的D5/D6各NOTRIP/TRIP共4项。已分别追两条支路：D5.A仅接R1.1，D6.A仅接R2.1；二者都没有采样/比较/使能执行链，也不是栅极限幅或跨开关能量钳位。因此四项共享不适用前提有拓扑依据；连续负载/钳位意图仍由PWR-C06/DEV-C01待判，不将筛查提示转成电气发现。

# 独立审查证据与边界：rmingon--chlinknet

本记录由本轮网表、原生原理图和逐份手册独立整理，不继承 lane 前板结论。缓存内的原始资料与字节哈希见 source-provenance.json，第三方原图/README/手册没有复制入 SR 仓库。

## 来源与方法

固定 rmingon/CHLinkNet@b2318d1130624ca1c122ba834d3767eae5a984eb；CERN-OHL-S-2.0，目录许可证证据与源README相符。完整 git ls-tree 只有图片、README、licence.md 和 KiCad 项目/PCB/原理图，没有 BOM/装配表，因此不运行无输入的 read_bom.py。原作者 README 称 KiCad9.0.3，本轮 KiCad Eeschema10.0.7导出且 parse_kicad strict=true，21器件；导出日志 fetch.log。原生PDF唯一页已目读，与当前源图和网络逐项对照。不存在本轮ERC=0的结论。

用途“CH32V307以太网/USB串口调试开发板，预留外部PoE模块”为推断；industrial_telecom是审查方法基线，不是产品已承诺工业温度、认证、具体负载或协议。catalog ETHERNET/USB/DEBUG，按实际网络补POWER_CONVERTER/CLOCK/UART/STARTUP。7个功能电路；run是静态分析态推断，不替代复位、掉电及实际装配合同。未把UART或STARTUP的未建候选伪装成完整覆盖。

## 已确认的设计与文档缺陷

1. R1/R2=R_Small，C3/C4/C5/C6=C，Y1=Crystal_GND24，无源树BOM覆盖，七个位号的装配/计算输入未定义。按DOC-D01记录P2设计定义缺陷。不能把C4-C6看成0，也不能因C7=100nF就声称LDO仅有100nF。
2. 同提交README Programming Header表写J2.1=GND/.2=3V3，但网表正好相反；实际.3=未用、.4=RST、.5=RX-PROG、.6=TX-PROG、.7=SWCLK、.8=SWDIO。这属于发布接口文档冲突，P1可信损坏后果，不是实物损坏判定。README多处称J3为5V模块接口，网表J3.4直接接3V3；另有一处提3.3V，文档本身亦不一致。JP1实际BOOT1、JP2实际BOOT0，README反向命名。README称RMII，但网表U28.37/38/39/40直接接网变RX/TX；真实链路为片内MDI。Y1的25MHz仅README描述，与通用Value不构成已定义晶体采购值。

## 独立计算与拓扑核对

- 晶体：C1=C2=10pF，两端对地，CL=10×10/(10+10)+Cstray=5pF+Cstray。WCH V3.9 PDFp66（印刷64）Table4-12给HSE3–25MHz，建议晶体ESR≤80Ω，CL按晶体原厂，CL1=CL2；典型gm=17mA/V不能假充负阻保证。未知Y1准确CL/ESR/驱动/频率和寄生，不能得出起振裕量。两端仅U28一个振荡器；CH340C使用片内时钟，不需要再接外晶体。
- 指示灯R54：R=1.2k；若采购容差≤5%，Rmin=1140Ω。在TI LM1117正常稳压的条件窗Vout≤3.432V下，不借LED典型VF，I≤3.432/1140=3.010526mA，P≤3.432²/1140=0.010332126W。该式是条件上界，不关闭实际采购容差/轨故障或MCU驱动额定检查。R1/R2未知，不能同样计算网口LED电流。
- U3：IN3=5V，OUT2=3V3，GND1接地；固定版无ADJ脚悬空。LM1117与AMS1117库名不同不单独证明采购冲突。TI SNOS412Q PDFp15 §9.2.2.1.3：钽电容基准Cout至少10µF，ESR0.3–22Ω。AMS1117 PDFp4使用22µF固体钽保证说明，两种分支不混用；C4-C6的有效容量/ESR均未定义。TI输出3.168–3.432V是其p7额定条件下的稳态规格，不是所有故障态保证。
- 热与供电：假定输入最高5.25V、输出最低3.168V，则P=(5.25−3.168)Iout+5.25Iq=2.082Iout+5.25Iq。800mA时通路损耗1.6656W只作灵敏度示例；负载没有被证明为800mA。环境温度/铜面积未知，不声称SOT223过热。输入4.75–5.25V为推断分析窗；USB Micro-B线缆远端最小电压需重新定，不能套USB-PD vSafe5V并放行。
- UART：U4.2 TXD→TX-PROG→U28.43 PA10/USART1_RX；U28.42 PA9/USART1_TX→RX-PROG→U4.3 RXD，方向正确。U4.4 V3与.16 VCC同接3V3，符合3.3V模式。CH340 V3C p9 §6.3 VCC3.1–3.6V且TA=25℃；VIH≥1.9V、VIL≤0.8V、VOH≥VCC−0.6V@2mA、VOL≤0.5V@4mA，不能不核全温MCU窗口便放行所有工况。USB UD+/UD−接J1.3/.2，CH340 p3要求直接连接且不串电阻，片内有USB上拉。
- 悬空：CH340 V3C p4明确未用I/O可悬空，R232内置下拉；U4.9/10/11/12/15的NET-A06/A07各5条按电气误报排除。NET-A01另是未有NC标记的绘图确认，45条仍保留，包括上述合法悬空脚；二者不互相抵消。U4.7/8已No-connect；新版8脚OUT#而库标NC，空接合法，但批次脚表定义留知识缺口。
- 以太网：HanRun HY931147C REV.A/1 PDFp1：RX1/2、CT3，TX5/6、CT4，V+9/V−10为线缆侧整流输出；p1隔离试验1500Vrms/1min，变比1CT:1、OCL≥350µH@100kHz/100mV/8mADC。网表U28.37/38/39/40→U1.1/2/5/6，CT3/4同接3V3且C4-C7并到GND。官方WCH CH32V30xSCH.pdf p9的HR911105A两CT4/5也共接3V3且C14=0.1µF，是“中心抽头一概不能并联”的反证；不同磁件不能据此宣布HY全参数兼容。WCH手册§4.3.20数字MAC时序不能补出片内10M MDI完整模拟磁件资格，保留知识缺口。
- V+/V−不是高速差分数据对；3条SIG-E02/SIG-T01/SIG-T03在该对象上不适用。U1是被动带磁件RJ45/整流桥/LED，不是有源PHY IC；J1同为被动连接器，其VBUS入口电容仍应核，IC专属去耦4条不应套到J1。U1图片PDF人工核过，自动NO_TEXT不是没有取得原厂图纸。
- 复位/默认：NRST U28.7仅到J2.4。WCH V3.9 PDFp15-16有内部POR/PDR；p71-72 Table4-25有NRST内部30–50k上拉，缺外置复位IC或上拉不是自动缺陷。JP1/2的桥接装配未知。U28.36 PB15与.41 PA8硬接GND，若固件推挽高会短路，但可保持允许输入；无实际固件/默认配置不能判必然损坏。
- 外部模块：J3.1/2分别V−/V+（线缆侧），J3.3/4分别GND/3V3（逻辑侧）。外部PoE模块必须连同实际隔离/供电方向一起核；当前网表不存在V−直接短到GND的证据。J2.1/J3.4均在U3.OUT同一轨，无独立源侧支路保护器件；U3或系统限流能否覆盖须确认，不能从“没有保险丝”直接定缺陷。

## Top50和归因计数边界

Top50逐条登记在top50-audit.json。两条漏报是PRO-C04支路覆盖对象、PRO-D02磁件/外接模块隔离边界覆盖对象缺失，均为应生成检查而未生成，不是两项已证电气不合格。STARTUP/UART已在最终计划补声明，不再将其重复计漏报。TVS/MOS/熔断器及CAN/I2C/ADC的不存在对象不机械计为漏报；未知MCU复用脚不等于正在使用ADC/CAN/I2C。

## 门禁、报告与后续

review-results保存244个逐项判断；INSUFFICIENT对应的知识或本板条件缺口如实保留，均是本次缺少受控输入/资格的未闭事项，不是请求用户补齐所有参数的厂家待办。外部完整合同、跳线配置、晶体与电容值没有被编造。REVIEW_INCOMPLETE不能变成VENDOR_DATUM来强行通过。

原生validate退出2、valid=false、NO_GO；除了未闭项和两项设计/文档缺陷，还保留一项F1机械限制：纯晶体连接方向功能已有网表事实和NA判断，但没有参与该连接结论的数值限值/强制条款；不为消错引用无关HSE频率作通过证明。原生renderer因此且因REVIEW_INCOMPLETE拒绝出正式报告。仓库“审查报告.md”是明确标注的执行与归因记录，不冒充正式报告。

quality_screening为启发式建议。逐个对象的证据保存在plan-judgements；共享输入组不证明各条已关闭，跨功能同源条目保留检查ID。重复文字/跨范围提示保留给维护者复看，不自动当电气错误，不批量豁免，也不据其得出审查完成或生产准出。

# 电阻阵列、光传感器与应用状态边界

人工边界案例，不是自动判决。来源：[当前TSL2591板22be4c7](https://github.com/adafruit/Adafruit-TSL2591-Breakout-PCB/tree/22be4c7b8d53155dacedc18f3373ba8dbf95dc23)、[固定库a857bf](https://github.com/adafruit/Adafruit_TSL2591_Library/tree/a857bf93c10b5d60d02928c7a6c364e67ff5e0f3)、[厂商2023手册](https://look.ams-osram.com/m/c901de8e97608f8/original/TSL2591-DS000338.pdf)、[作者2013手册](https://cdn-shop.adafruit.com/datasheets/TSL25911_Datasheet_EN_v1.pdf)、[AP2112](https://www.diodes.com/datasheet/download/AP2112.pdf)。案例不替代版本、全部物理脚与适用条件审查。

| 实例与反例 | 应有的审查分界 |
|---|---|
| 同位号四组独立10k有原始gate/pad配对；反例只由8脚猜全共端或伪造四个位号 | 用实际1–8/2–7/3–6/4–5映射，保留四支路与finite10k。内部未知不自动填；共端阵列另按有据共端映射。模型拒绝已知配对是工具表达缺口，不是电路缺少四只上拉。 |
| 两上拉所在节点经33Ω相连；反例把第二数组支路归到第一节点/path=[] | 每支路按实际端子所在信号网和可复现路径归属，33Ω两侧仍两个segment，不直接并成5k。不贴/未知装配、未知阻值仍停，不从nc=false推已贴。 |
| 双管六脚SOT363 VALUE只BSS138，候选BSS138PS针序相合；反例按三脚单管名字判错料或赋予候选实装身份 | 先核D/S/G实际拓扑，再锁双管完整型号及低VGS/电流/温度/Ioff最低规格。候选5V下RDS不能充当3.3V保证，Vth也不是低RDS保证。 |
| Vin3–5、3vo nominal3.3输出另可取100mA；反例在Vin3仍宣称升压3.3或用轻载电流取代外载预算 | 按真实全部负载/低Vin/dropout及输出精度条件核传感器2.7–3.6窗口。1–30mA/4.3V精度不能自动扩到零负载；接受厂家有条件的over-temperature design guarantee，不能因未逐颗温测就否定保证。热估计不是实际热签署。 |
| INT开漏直出且polling不使用；反例因I2C已转换就让INT接5V上拉 | 未用可不装pullup；使用时单独核rail/host阈值/3.8V绝限/掉电条件，不编VDD+.3条款。未选host给具体集成约束，不捏造实际5V误接。 |
| current库demo300ms、guide/构造100ms；反例只判65535而100ms满量程更低 | 保留2013=37888/2023=36863与≥200ms=65535版本/模式；零ch0除法NaN、NACK未传播分别核有效性，不把数字结果错误报成硬件连接坏或精密lux验收失败。原样函数/寄存器复现不是Arduino板测。 |
| registerInterrupt设置ALS阈值/persist但enable同时开NPIEN，NP阈值留0；反例以API存在证明阈值唤醒成立 | 按两个比较通道/掩码/清中断/持续enable核真实状态。窗口内数据也可触发NP；若选该模式，应修掩码或NP配置并测第1/第N周期。不依赖INT的polling硬件不能因此判P1。 |
| C1局部0.1u、C3同轨10u；反例仅加名义10.1u就批准近脚1u低ESR要求 | 定位本地推荐偏离，提出C1有效≥1u低ESR/短return的条件方案或有据验证现C3路径。PCB中心距不单独决定电气失败，推荐也不变为无出处的强制缺陷。 |

沿当前实际判据审：全部地网检查不是UVLO，主控pinmux不是传感器增益寄存器，ADC积分等待不是两端建立/保持保证；功能包汇总不能盖过成员未知。共用方案可以合并，逐件应力、缺参数与通过标准仍须定位。

本例数组入口支持与支路归属是模型能力改进；不扩大SIG-E01直接等效模型、不自动判电气PASS。同冻结无links输入的自动提示可不变；完整links输入的旧拒绝/新合法另记，不能称八个电气误报消除。人工案例数、提交数和一致率不是成绩。

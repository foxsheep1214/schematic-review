# 检查器共用约定

> 读者：审查员。

所有检查器共同遵守的识别与声明规则，各检查器的说明不再重复；声明段的字段见 [检查器](automation.md)。


**引脚名写法**先归一化再匹配：上划线 `~{RESET}`、导出器附加的脚号 `EN_12`、序号 `G1`/`VDD_1`、
多功能合写 `PB6/SCL` 都还原成功能名，原文优先、逐个候选试。**低有效标记不动**——`NRST`、
`RESET_N` 的极性是判据，不是写法噪声。

**电源轨身份**由 `powertree` 统一推导，与 PWR-A01/PWR-A02 的来源判定共用同一套逻辑：

| 依据 | 含义 |
|---|---|
| `declared` | intent 的 `power_sources` 声明，带出处 |
| `driver` | 网上（或经已装配的串联无源件回溯到）有输出脚候选 |
| `name-hint` | 只有轨名像电源，无来源可推 |

轨名提示（`name-hint`）按 VCC/VDD/VIN/VOUT/VBAT/VBUS/V<数字>/<数字>V/HV 开头识别，可带 `RAIL_` 前缀（RAIL_3V3_PRI）。
以 `_N/_NEG/_RTN/_RET/-` 结尾的是回流（VOUT_N、VIN-），含 `_FB/_FBACK/_SENSE/_SNS` 段的是反馈或检测线，
HVEN/HV_EN 是使能，均不算轨。这些规则来自公开反激板回放（`evals/kicad_replay_bench` 的 rf1/rf2）。
轨名不像电源的供电网（BULK、HVDC、PRI_AUX）在 `intent.power_rails` 声明后同样进入 PWR-A01 扫描和 PWR-T01/PWR-C01 计划（触发 `declared-rail:<网>`）；条件是该网给已贴 IC 的供电脚供电，或经 ≥1µF 电容回到地/声明窗口不高于 0V 的回流网。只声明电压窗口的信号网（ZCD、CC1、栅极驱动）不因此变成轨；PWR_FLAG 不是来源，自供电（如 NCP4307 从 CS 取电）要在 `power_sources` 写出处。

带 `SW/LX/PH/BOOT/BST` 类引脚的网是**开关节点，不算直流轨**——它经储能电感能回溯到输出脚，
但本身不是可监测、可挂负载的轨。只有 `name-hint` 的轨登记 `rail-identity:<net>` 缺口；
来源候选仍需 PWR-T01 核实功能与上游供电，推导出来不等于这条轨合格。

**识别依据**分三级，随对象一并记录：

| 依据 | 来源 | 可产生 |
|---|---|---|
| `declared` | intent 明确声明并带出处 | 自动扫描发现、计划项、保证值核对 |
| `topology` | 连接关系加引脚角色成立 | 自动扫描发现、计划项、保证值核对 |
| `name-hint` | 只有网名/型号线索 | 计划项（`UNDETERMINED`，需 intent 确认） |

名称线索、`nc=false`、库名 `Bridged`、焊盘默认图形不能证明装配或功能模式。
去耦清单可使用已解析的标准 KiCad Device:C 等符号确认无源类别，仅证明类别，不证明实际料号、
容量额定或贴装；显式类别声明优先，自定义/未知符号仍需确认。无法分类的器件记为未知并形成
缺口，不按名称推定不适用。

**器件类型以原厂手册为准，由工具核验原文。**

第一步，审查者读手册，在 `intent.device_kinds.<ref>` 写下声明：`kind`、`page`、`quote`。
- `kind`：bjt/mosfet/diode/zener/tvs/opto/bridge_rectifier/transformer/connector/ntc/varistor 等（`board_intent.DEVICE_KINDS`，即器件类别登记表 `device_kinds.KINDS` 里可声明的类别加 IC 角色），与检查器的器件类别一致：分立器件的类别、位号前缀、词、手册线索、两端/链路/保护/磨损属性只登记在 `device_kinds.py` 一行里，各模块读视图。
  集成电路声明它的**角色**，角色登记表是 `catalog.DEVICE_ROLES`（[审查词表·器件角色](review-vocabulary.md#器件角色)：每个角色的
  手册标题词、它作核心器件时生成的电路类型、ANALOG 走线从哪些脚出发；`board_intent.IC_KINDS`、`part_words.IC_ROLES`、
  `datasheet_kinds.KIND_CUES` 都从这张表读，加角色只改这一行）。手册标题没有任何登记角色的才写泛称 `ic`；计划把每个 `ic`
  列成 `DEVICE_KIND_GENERIC` 诊断，这些器件不生成电路候选。角色决定哪些 IC 是电路候选的核心器件（`ANCHOR_KINDS`：登记表里有
  电路类型的角色，isolator 与 ic 除外），所以 U/M 位号与 Q/D 位号一样，没有核验过的类别就在 DEV-D02 登记 `intent.device_kinds.<ref>` 缺口。
  核验通过的 bridge_rectifier/transformer/connector 没有需要 IC 旁路的供电脚，不再留 PWR-D01 的 `unverified-device-pinout` 缺口；
  极性、绕组、额定、绝缘与针表仍由各自检查核对。
- `page`：手册页码，从 1 开始。
- `quote`：该页上写明器件类型的原文，例如 BCX56-16TX 写 `{"kind":"bjt","page":1,"quote":"80 V, 1 A NPN power bipolar transistors"}`。

第二步，`audit_datasheets.py --intent intent.json` 读取 datasheet 解析表绑定给该位号的那份 PDF，用 pdftotext 抽取该页文本（没装 poppler 时用 PyMuPDF，两者都没有才记 NO_TEXT）。比较时只保留字母和数字（PDF 常丢空格），逐条核验三点：
- 原文确实在该页上；
- 原文本身写明了所声明的类型，例如 NPN/bipolar、MOSFET/N-channel、Zener、TVS/ESD protection、rectifier/diode/Schottky、bridge rectifier、transformer、connector/receptacle/terminal block；
- 原文没有同时指向别的类型，例如把 “ESD Protection Diode” 声明为普通二极管，判为 QUOTE_CONFLICT。
  IC 角色由标题词判定（PWM/PFC/flyback/current-mode controller、gate driver、synchronous rectifier controller、
  USB PD / Type-C controller、voltage regulator / LDO / DC-DC converter、supervisor / voltage monitor / watchdog、
  operational amplifier / comparator、shunt regulator / voltage reference、microcontroller、transceiver / PHY、
  digital isolator）；角色词同句里的 MOSFET、rectifier 是它驱动的负载，不算冲突；“microprocessor supervisor”
  不是 MCU，“optoisolator” 是光耦不是隔离器。声明为泛称 `ic` 的原文若写明了某个角色，判 QUOTE_CONFLICT，
  要求改声明为该角色。

核验结果写入审计的 `device_kinds` 段：
- 状态为 VERIFIED / QUOTE_NOT_FOUND / QUOTE_LACKS_TYPE / QUOTE_CONFLICT / NO_DOCUMENT / NO_TEXT。
- 通过时附手册 SHA-256。
- 未声明的分立半导体和集成电路标 UNDECLARED，附首页候选类型和所在行，只作提示。

只有 VERIFIED 的声明会进入分析（basis `datasheet`），并随清单上下文保存为 `device_kinds_verified`。该字段由工具生成，intent 中手写会被拒绝。未核验、核验失败或抽取不到文本时，一律按缺口处理，不会因为抽取出错得出结论。

型号/符号库关键字和符号引脚名（B/C/E、G/D/S）只作交叉核对，与手册矛盾时记为未知并形成缺口，因为这说明可能选错了符号或填错了型号。没有核验过的声明时，才按以下顺序退回启发式：
1. 关键字（basis `part-keyword`）；型号族（PS2、SS、IRF 等）只在一个型号的开头命中，不在更长型号中间命中（TPS25940 不是光耦）；
2. 引脚名（basis `pin-names`）；
3. 位号前缀（basis `refdes-prefix`）。

依据为后两种时不能作为结论：
- 功率开关登记 `datasheet-kind:<ref>` 缺口，在补上并重生成计划之前不得判 PASS；
- Q/D/ZD/TVS/U/M 位号的 DEV-D02 登记缺口，缺口文字带审计状态和候选类型。
  例外：D/ZD/TVS/LED 位号的符号恰有一阳一阴两脚、封装名是两端封装（0402/0603…、SOD、SMA/SMB/SMC、DO、MELF、两引脚 LED_D3/D5mm）时，脚集合由封装决定，DEV-D02 直接就绪，不要求原厂全脚表、确切料号或类型声明；焊盘与阴/阳极标记的对应移交 PCB 阶段。双向两脚（A1/A2 或 1/2）同样按两端封装就绪，实际是单向还是双向由类型/功能检查判定，不属于脚集差。1/2 位单排连接器（封装名含 1x01/1x02，符号脚号恰为 1..N，封装无安装/屏蔽焊盘）同理就绪，脚义由 DEV-D03/DEV-E01 核对。三脚及以上、多焊盘 LED 封装（PLCC、RGB、散热焊盘、带脚数后缀）、带安装或屏蔽焊盘的连接器，或封装名看不出两端时仍登记缺口。

工具不从 PDF 抽数值参数，数值仍按 datasheet-facts 的审查者核对流程处理。

**参考地分区、跨域器件与截止网络**（`checkers/domains.py`，写入 `review-plan.json` 顶层 `domains`，schema 1）：
电路候选的边界不由审查员画，按连接关系推导。
- 地 = 名字是地或回流（GND 族、`_RTN`/`_RETURN`、`GND_<域>`）或 `power_rails` 窗口 min = max = 0 的网；
  域标签取 `power_rails.<地>.domain`，未声明的地按网名各成一域，两个地写同一标签就是一个域。
- 域 = 经直流导通的器件能到达同一个地的网络集合。电容、变压器、光耦、继电器、晶振、连接器、测试点、
  电池、未分类器件和核验为 isolator 的 IC 不导通；其余器件在它的全部引脚之间导通。
  只经电容相连、到不了任何地的网列在 `unreferenced`。
- 跨域器件（`barriers`）= 引脚跨两个域的已贴器件，带类别和两侧域名：变压器、光耦、Y 电容、数字隔离器。
- 核心器件（`anchors`）= 角色在 `ANCHOR_KINDS` 的已贴 IC；没有核验角色的 IC 列在 `undeclared_ics`。
- 截止网络（`rail_stops`）= 候选从核心器件向外走时停下的网：地（`ground`）、IC 输出脚驱动的网
  （`driver`，沿用 powertree 的来源推导）、声明轨中被两个以上核心器件直接或经一颗两端件到达的网
  （`anchors:<位号,...>`，经地或伪网的那一跳不算）。只被一个核心器件用的声明轨是那个电路的内部节点，
  不是截止网络；开关节点永远不是。
- 冲突只记录，不改声明：导通器件把两个不同标签的地连到一起记 `DOMAIN_MERGED`（带那颗器件），
  `power_rails.<网>.domain` 与推导不一致记 `DOMAIN_CONFLICT`；两者都进计划的 `diagnostics`。

**电路候选**（`scripts/circuit_candidates.py db.json --intent intent.json --datasheet-audit datasheet-audit.json --json record/circuit-candidates.json`，
schema 2，带 `rules_version`，绑定 `db_sha256` 与 intent 的 `input_sha256`）：电路不由审查员画，由网表、已核实的器件类别和检查器库存生成，
审查员只做决定（见[计划与结果](intent-format.md#一intentjsonschema_version-4)）。
- 候选 = 类型 + 核心器件，编号 `<类型>-<核心器件>`（链为 `<类型>-<核心器件>.<脚>`），工作态按类型固定（`catalog.CANDIDATE_STATES`：
  变换器和输入保护 startup/run/fault，USB unattached/attached/fault，ANALOG run/fault，ISOLATION run，STARTUP power-on/restart，DEBUG run）。
  成员各带 `role`、`via`（走到它的路径，是归属关系，不是导通主张）和 `hops`；页码只作显示，不决定归属。
- 走线只经两端件（电阻、电容、电感、二极管、保险、压敏、NTC），最多 4 跳（ANALOG 2 跳、输入走线 6 跳），
  到截止网络、地、其他核心器件、跨域器件即停；截止网络 = `domains.rail_stops` ∪ 地 ∪ 感性负载库存的轨/输出/回流网 ∪ 输入走线的首个储能网，无人驱动的开关算作核心器件重算截止网络。
- 规则按确定性从高到低：输入保护 `POWER_PROTECTION-<连接器>`（从电源连接器走到首个储能电容或变换器输入轨，桥和四脚共模扼流圈直通，至少含一件保护件）；
  链 `POWER_PROTECTION-<核心器件>.<脚>` / `STARTUP-<核心器件>.<脚>`（保护脚、启动脚沿两端件和光耦走到截止网络或开关节点，另一核心器件作终点，跨电路）；
  变换器 `POWER_CONVERTER-<核心器件>`（核心器件 = 登记表里靶 POWER_CONVERTER 的角色（pwm_controller / sr_controller / regulator / gate_driver / charger / motor_driver）的 IC，或无人驱动、或 `power_switches` 声明了角色而驱动 IC 没有核验角色的开关：
  所属开关、栅极下拉、吸收网络、感性件与它的其他绕组、绕组上的整流和输出电容、反馈光耦；辅助绕组的整流归它供电的变换器；sr_controller 与声明的同步整流管不收感性件）；
  隔离 `ISOLATION-<域A>/<域B>`（该域对的全部跨域器件，跨电路）；`ANALOG-<核心器件>`（pd_controller / supervisor / mcu / transceiver 的检测脚，运放、基准的全部信号脚；
  两地之间的分流电阻）；`USB-<连接器>`（CC/D± 脚一跳、PD 控制器及其 VBUS 开关与钳位）；接口 `<类型>-<核心器件>`（登记表里靶接口电路的角色：
  transceiver、memory、oscillator、level_shifter、load_switch 等，全部信号脚走两跳，到达的网上的连接器作成员；一个角色靶多种总线的按手册标题
  `catalog.BUS_CUES` 挑一种，挑不出记 `role-bus` 缺口，由审查员写 `circuit_decisions` add）；`DEBUG-BOARD`（测试点、调试连接器，不走线）。
- 裁决：一件器件两个电路候选都走到，路径短的得；同距离留在两者里；核心器件不共享；跨电路候选不参与。
- 归属（schema 2）：每个成员带 `owned`。认领强弱 `claim_rank`：电路的核心器件 0、电路成员 1、电路里的端点类角色 2、链路成员 3、
  隔离带 4、链路的核心器件与端点 5；最强的唯一认领者拥有它，其余候选只引用它。打平的器件谁也不拥有，列入 `shared`，由 own 决定裁定。
  谁都没走到的已贴器件进 `unassigned`（REQ-Q08 逐颗列出），没核验角色的 IC 和缺引脚名的感性件进 `gaps`。
- 生成对器件顺序和页码变化是确定的；候选文件随记录打包，改了 db 或 intent 的输入指纹就重新生成、重新决定。
- 计划生成按功能树分模块：`plan_review.py` 只管加检查项、合并、挂接扫描发现和汇总，电路与器件的检查项在 `plan_circuits.py`，接口的检查项与框架在
  `interfaces.py`，系统功能在 `plan_system.py`，全板、文档、需求与覆盖在 `plan_board.py`（`ReviewPlanner` 混入这四个模块的方法）。
- 检查项归属（`scripts/row_owner.py`）：计划汇总时给每个检查项写 `owner`，按检查项对象、规则和各电路拥有的器件推出，写入计划的 `owners`；
  `validate_review.py` 按 `owners` 重算，写错的检查项被拒绝。
- 接口（`scripts/interfaces.py`）：从各电路拥有的器件和网表推电路对、链路、供电、对外四种接口及端点角色、参考地分区、供电，写入计划 `interfaces`。
  轨 = 电源树找到源的网，或 intent.power_rails 声明且有 IC 取电或大容量储能电容的网；名字像电源轨不算。
  源 = 轨上电源树的源脚（库类型不是输入），否则轨上整流管（二极管阴极、整流桥 + 脚）的唯一所属；都没有记缺口。
- 接口检查项：`interfaces.py` 的 `plan_interfaces` 按 `catalog.INTERFACE_SUBJECTS` / `INTERFACE_NET_SUBJECTS` 逐接口出检查项并建接口框架；
  `catalog.INTERFACE_RULES` 的其余检查项（检查器、扫描）网络都落在一个接口上时由 `row_owner` 归该接口，连接器的接口优先。
- 系统功能：`plan_system.py` 的 `plan_system` 按触发生成 PWR-T06（地网 ≥ 2）、RST-T03（电源轨 ≥ 2）、SIG-D13（有可能是主控的 IC），
  `plan_system_frames` 给每个有检查项的系统功能建框架；`plan_circuits.py` 的 `plan_owned_parts` 按各电路拥有的器件生成 DEV-C01/C02/C03。
- 覆盖审计：`row_owner.coverage_errors(plan, db)` 查每颗贴装器件恰归一块电路或在 REQ-Q08 清单上，`interfaces.coverage_errors(plan)` 查每个接口有它的检查项和框架；两条都由 `validate_review.py` 执行，归属审计只在电路来自候选时启用。

**装配状态**：全部检查器共用 `intent.assemblies`，只写一次：1–32 个唯一状态，每项必须有 `id`
与 `citation`。`population` 只接受 JSON `true/false`，缺项表示未知；`jumpers` 按位号填
`closed/open/unknown`，跳线还需 `population=true` 才导通。经核对的状态声明可以覆盖解析器的
`nc` 标记，输出保留原标记，并在 citation 说明变体依据。未声明时按网表 `nc` 形成"按图状态"，
同时登记 `assembly state unverified` 缺口。
去耦覆盖与 I²C 连接覆盖不同：它们不把网表 `nc` 当装配证据，未声明时每颗器件的贴装状态都是未知
（`population:<位号>` / `population-unverified`），覆盖记 INCOMPLETE，资料请求按位号列出要补的装配状态。检查器段里写 `states` 会被拒绝。

**器件脚表**：`intent.devices` 按位号声明准确 MPN/封装、身份解释与完整官方物理脚表，供去耦分组、
官方物理脚差集（DEV-D02）与引脚处置（DEV-D05）共用。

**指纹绑定**：声明了 `assemblies`、`devices` 或任一检查器段时，意图必须带顶层 `input_sha256`
（覆盖电气指纹、符号声明脚、伪网与输入完整性），旧声明不得静默用于新网表。取值：候选清单输出
的 `input_sha256` 字段，或 `python3 scripts/decoupling.py db.json --json candidates.json`。

**清单与计划**：`lint.py` 每次重新生成清单并嵌入 `review-plan.json` 的
对应顶层键，不读取旧清单当事实。另存清单：

```sh
python3 scripts/lint.py db.json --checker-json <checker-id>=inventory.json
```

**缺口与结论**：`coverage` 的 `DISCOVERED`/`INCOMPLETE` 都不是电气 PASS；清单里"有这颗器件"
不触发自动通过。缺口必须补齐或保持 `INSUFFICIENT`；带缺口的对象不能写 PASS。电气判据初始
一律 `WAITING_EVIDENCE`，需专家提供适用规格、工况计算与逐项结论。

**保证值核对**：检查器的保证值核对规则（方式 E）由检查器定出对象，计划行为 WAITING_EVIDENCE，
审查者按 [datasheets.md](datasheets.md#二保证值核对方式-e) 的判据要点判定。只接受带出处的保证值：
缺任一项即 INSUFFICIENT，不用典型值顶替；比值与寿命系数必须来自项目规定。PASS 的 scope
写明未判定的部分，计算角点保留在 calculation。

**校验**：`validate_review.py --db` 重建清单并逐项对比，拒绝被删检查、改写判据、被篡改的
摘要/缺口与过期绑定。审查者补查项（`intent.rule_gaps`）必须使用独立对象，不得复用生成项的对象。摘要只绑定被审
输入，不验证引用文字真实，也不替代工程审查。

**规则编号**：检查器的规则与其他规则共用[规则总表](check-catalog.md)的编号（`内容域-方式序号`），
在 `scripts/catalog.py` 以检查器 id 为来源登记；检查器类只引用编号，自动扫描（A）与保证值核对（E）
规则由 `cold_rules`/`e_rules` 从总表取出。下文各节列出每个检查器使用的规则。

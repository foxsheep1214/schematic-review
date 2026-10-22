# 自动检查：扫描、证据计算与检查器

自动扫描（A）与证据计算（E）只按连接关系和带出处的保证值产生候选与计算结果；最终结论由审查者复核，映射见 [结论与准出](verdicts-and-release.md#1-四种检查结果)。

## 一、自动扫描与证据计算

本文说明方式 A（自动扫描）与方式 E（证据计算）怎么执行、输出怎么读。规则编号、名称和判据要点
以 [check-catalog.md](check-catalog.md) 为准，本文不再重复规则表。

### 两次运行

一条规则算不算自动规则，看结论是“算出来的”还是“推出来的”：能由输入复现、可穷举的走脚本；
需要工程判断的交专家审查（方式 T/C/D）。自动规则在哪次运行执行，由输入决定：

| 运行 | 输入 | 执行 |
|---|---|---|
| 网表扫描 | `db.json`，可选 `--intent`、`--log` | 全部 A 规则；REQ-A01 需要意图中的 `expect`；DOC-A01/DOC-A02 需要导出日志，未给 `--log` 时二者列入“本趟未执行”；给了但内容为空（kicad-cli 导出成功时就是空的）按零命中执行，导出是否成功仍以命令退出码为准；日志按中英文分级：导出错误/中止记 FINDING，批注（位号）错误记 CANDIDATE，其他告警记 INFO，退出码 0 不等于没有告警 |
| 证据扫描 | 网表扫描输入 + `evidence.json` + `datasheet-audit.json` | 全部 A 规则 + 已提供证据的 E 规则 |
| 改版比对 | 旧/新 `db.json`、旧计划、历史意见断言 | REQ-H01（`diff_netlists.py`）与改版影响清单 |

**输出分三类**：`FINDING` 是疑似缺陷，逐条排除；`CANDIDATE` 是待资料取证定夺的优先级清单，直接
决定先读哪几份 datasheet；`INFO` 是提示，不计入疑点，但准出前仍要核实（如 NET-A04 判为工具伪网络的
NC 网）。FINDING/CANDIDATE 各成审查计划的一行检查，与其他检查一样作答；INFO 进计划 `diagnostics`。同一条规则可同时产出多类，例如 PRO-A02 按型号或轨名推断的电压只作候选。
E 规则的每条结果另记 `check_results`（PASS/FAIL/INSUFFICIENT）与 `passes`。

**未执行不等于通过**：`lint.py` 每次在末尾列出本次没执行的规则及原因（缺 `--intent`、未提供证据）。
扫出 0 条与根本没扫，输出必须能区分。

**命名检出不等于功能适用**：名称候选先确认实际角色/模式，再展开电路检查项；
已有资料尚未阅读或计算时列审查待完成，补证尺度见 [最小充分证据](evidence-proportionality.md)。

**未检出特征不等于不适用**：网表检测不到 DDR/RF 等关键字时，对应功能电路列入 REQ-Q08 待确认；
只有设计意图给出可引用的不适用依据，功能电路才标 `NOT_APPLICABLE` 并最终写 NA。适用但缺材料写
`INSUFFICIENT`。

自动扫描的输出是疑似清单，不是判决。合法结构（Bob-Smith 终端、补偿网络、DNP 选项、有意单端
测试点）由审查者逐条排除，排除依据写入报告附录；不能按规则批量排除。

### 典型案例

| 规则 | 典型案例 |
|---|---|
| NET-A01 | `EFUSE2_EN_L` 只挂一颗电阻的一端，24V 输出永远无法开通 |
| NET-A02 | `VCC_5V0_SYS` 与 `VCC5V0_SYS` 分裂，5V 主轨断开，PMIC 无电 |
| NET-A04 | 164 个引脚被 “NC” 网络标号短成一张网，含晶振脚、MII 输出脚与 6 个外部连接器 pin1 |
| NET-A04（提示） | 357 个引脚挂在导出器的 No-Connect 汇集网上，看似隔离栅被跨接，实为工具产物 |
| NET-A06 | 解析器已有 PINUSE：多个 OUT 直连报疑点，合法开漏/三态仍须排除 |
| PWR-A01 | 跳线本身不是电源；受控路径仍需 PWR-T01 按状态核实 |
| PWR-A02 | SoC 357 个电源球全扫，`MIPI_DCPHY_AVDD→NC` 由此暴露（后经平台规范裁定合法） |
| PWR-A03 | 268 个地球只抓到 1 个例外，且与参考设计一致 |
| PWR-A03（地名网孤岛） | 充电 IC 地脚与补偿电容接到 `GNDA`，`GNDA` 与 `GND` 之间无任何已装配连接件，芯片失去供电回流与检测基准；电容、不贴的 0 Ω 不算连接；孤岛上有连接器、光耦/变压器/隔离器或 SENSE 遥测线时不报；同一 IC 的 AGND 在孤岛、PGND 在主地这类跨接只给候选，按手册核片内是否连通 |
| PWR-A04 | 监控芯片 V2 看 SOM 轨、V4 看底板轨，判定前先分清 `VCC_3V3` 与 `VCC_3V3_SOM` |
| PRO-A01 | ESD 器件挂在废弃的 `USB_DP/DM` 空网上，活线没有防护 |
| REQ-A01 | TPS16530 应有 2 颗实有 1 颗，输入保护缺失 |
| RST-E01 | TPS16530 EN 低有效却被上拉至 24V VIN（耐压 5.5V） |
| RST-E02 | RTL8208 TEST[3:0] 被上拉（要求下拉）；`EN_PWRDWN` 上拉导致上电即掉电 |
| DEV-E01 | 45 针连接器符号引脚号与实物不符 |
| DEV-A01 | 24V 输入轨上贴了 16V 耐压电容（耐压写在 BOM 值里，轨压按网名推断） |
| DEV-A02 | 电解电容 + 脚接地、- 脚接 24V，方向反接 |
| DEV-A03 | 指示 LED 直接跨在 3V3 与 GND 之间，通路上没有串联电阻 |
| NET-A07 | 声明为输入的脚没有网络或只在单节点网上，输入悬空 |
| DOC-A04 | 位号仍是 `R?`，无法定位与对账 |
| REQ-H01 | 回复“已改 RTL8326BI”后，新版网表仍是 RTL8326B-CG |

### NC 网络判别（NET-A04 执行前必做）

名为 `NC` 的多节点网络有两种截然不同的成因，判反了后果严重：误判为伪网会漏掉真短路。

| | 真短路（NET-A04 疑点） | 工具伪网络（NET-A04 提示，非缺陷） |
|---|---|---|
| 成因 | 设计者把 “NC” 当网络标号写在不用的引脚上 | 导出器把带 No-Connect 属性且无连线的引脚统一汇集 |
| `C_SIGNAL` | 带层次路径 `@<设计>(SCH_1):NC` | 裸字面量 `'NC'` |
| 实例行 | 带层次路径 | 裸字面量 |

1. 取该网的 `C_SIGNAL` 与实例行，核对已验证的导出格式；没有层次路径本身不能证明是伪网。
   解析器只对满足 NC 命名约定的平面汇集网给出候选分类，普通平面网络仍参与电气检查。
2. 辅助核对（不能单独决定）：取导出日志中全部 DOC-A02 告警，逐条比对被连接的网。若这些引脚
   一律落在真实网络、没有落入该 NC 网，只说明告警不反驳伪网解释；仍需已验证的导出格式或
   图面/属性证据。

`parse_netlist.py` 把启发式分类放进 `pseudo_nets`，`lint.py` 据此把 NET-A04 降为提示。审查者仍须用
图面或属性确认分类，不能用该字段自证。

### 驱动源判定（PWR-A01/PWR-A02 的前提）

从负载沿已装配的电感、磁珠、保险丝和 0Ω 向上游追踪；这些元件本身不产生电能。终点是实际电源
输出脚或 `intent.power_sources` 指定的外部来源。二极管/MOS 仅按 `intent.power_paths` 中当前
`active_state` 的有向导通模型跨越；并联 TVS、连接器和未装配器件不能自行成为源。不同地网不自动
合并。输出脚名称仍只是候选，PWR-T01 还要核对上游供电、导通条件、额定载流及每个工作/故障状态。

### 关键器件计数（REQ-A01）

REQ-A01 的输入不是网表，而是阶段 0 的意图清单：从需求/规格书、原理图修订记录、历史评审记录中
提取，写入 `intent.json` 随报告留档。扩展字段见 [plan-and-results.md](plan-and-results.md)。

```json
{
  "schema_version": 3,
  "expect": {
    "TPS16530": 2,
    "RTL8326B-CG": 0
  }
}
```

`expect` 的键按子串匹配 `part`/`value`/`prim`（不区分大小写），值为期望数量：该有的写 ≥1，
该删的写 0。标了不贴的实例不计入。缺 `expect` 时 REQ-A01 不执行，并列入“本趟未执行”。
这份清单错了会连锁影响功能电路的判定，必须留痕、可复核。

### 符号引脚映射（DEV-E01）

1. 从 pstchip.dat 提取需核验符号的引脚名/号映射（`'<PINNAME>': PIN_NUMBER='(<num>)'`）。
2. 与该器件官方 datasheet 引脚定义逐脚比对，写成 `expected` 证据。
3. 先确认实物封装变体，再看对应封装的引脚图；多封装同页时按标题逐张对应，禁止跨图引用
   （曾把 QFN-20 脚位当 TSSOP-20 判读，产生整页误报后撤回）。
4. 封装变体间的差异点（NC 位置、功能脚位移）是高频坑，逐脚核对而不是抽样。

DEV-E01 只核证据中列出的引脚；完整物理脚差集由 DEV-D02 负责。

### strap 与配置脚（RST-E02）

1. 从 pstxprt/pstchip 还原每个 strap 的实装状态（实例级不贴标记只在这里）。
2. 对照 datasheet 引脚表逐脚确认默认态（内部上/下拉）、强制条款（must 类原文）与功能真值表。
3. 上/下拉对（一贴一不贴）属合法设计；实装了与强制方向相反的电阻才是问题。
4. strap 节点上同时挂 LED 或其他上拉时，按复位采样窗口计算分压（例：1K 下拉 + 220Ω 串 LED 至
   3.3V，采样电压超过 VIL(max)，不能保证低电平；不直接断言实物读到哪一位）。

### 物料与引脚扫描（DEV-A01～DEV-A03、SIG-A03、NET-A07、DOC-A04）

`scripts/board_scans.py` 只用网表、BOM 值字段和引脚名/类型做确定性判别，不读 PDF、不猜降额：

| 规则 | 判别依据 | 不判什么 |
|---|---|---|
| DEV-A01 | BOM 值里写明的耐压（`10uF/16V`）低于按网名推断的电压 | 降额比例、纹波与温度（DEV-C01/DEV-C02）；值里没写耐压就不报 |
| DEV-A02 | `+`/`-` 脚名判别的极性电容：+ 接已知地、- 接命名轨 | 无极性脚名的器件（转图面目检 DOC-V01）；二极管方向按所在电路另判 |
| DEV-A03 | LED 两脚直接跨命名轨与已知地 | 恒流驱动、PWM 驱动与亮度（需资料或声明证据） |
| SIG-A03 | 网名含 SDA/SCL 记号、≥2 节点且有 IC 脚的网上没有任何接到非地网的电阻（候选） | 主机侧/片内上拉是否存在、阻值与上升时间（SIG-C01）；有串阻即不报 |
| NET-A07 | 引脚类型为输入且无网络/单节点网（标了 No-Connect 的作候选） | 内部上下拉是否足够（需资料） |
| DOC-A04 | 位号含 `?` 或缺序号 | 位号编排规范与 BOM 对账结论 |

不贴装（解析器 `nc`）的器件不报；其他装配变体的差异由审查者按 `intent.assemblies` 排除。

### 推荐工作条件验算（DEV-E02）

kind=operating_range，给 `ref`、所接轨 `net` 与资料保证的 `supply_v.min/max`；设计工况取
`intent.power_rails.<net>.voltage_v` 的 min/max。两边都齐才计算裕量：设计窗口越界为 FAIL，
缺设计窗口保持 CANDIDATE/INSUFFICIENT，不用推荐范围反推设计。温度、负载、频率与瞬态仍由
DEV-C05 逐项核。

### 覆盖补充

- `hot_executed` 只说明规则被调用；`hot_uncovered_instances` 列出计划中证据缺失、过期或模型未就绪
  的证据计算实例。审查者仍需复核计划完整性与最终结果，它不是全板覆盖证明。
- RST-E01/RST-E02 用包含负载与采样时序的保证电压窗口比较门限；缺模型时为 CANDIDATE，不能拿
  上拉电源电压直接当分压后的脚压。
- DOC-A01 提示导出错误或中止；DOC-A02 的 No-Connect 告警须逐项核，不能与真实导出失败等同。
- 单独另存某个检查器的清单：`python3 scripts/lint.py db.json --checker-json <检查器id>=out.json`；
  各检查器的识别依据、intent 字段与缺口语义见 [automation.md](automation.md)。

## 二、检查器

检查器从现有 `db.json` 发现对象、登记逐状态清单并生成审查计划。它们不是 EDA 解析器、
不是电气求解器，也不产生准出结论。加一个检查器只需新增模块并登记到
`scripts/checkers/__init__.py` 的 `REGISTRY`，计划、lint 与校验都按注册表遍历。

### 共用约定

以下规则对所有检查器一致，各节不再重复。

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
| `declared` | intent 明确声明并带出处 | 自动扫描发现、计划项、证据计算 |
| `topology` | 连接关系加引脚角色成立 | 自动扫描发现、计划项、证据计算 |
| `name-hint` | 只有网名/型号线索 | 计划项（`UNDETERMINED`，需 intent 确认） |

名称线索、`nc=false`、库名 `Bridged`、焊盘默认图形不能证明装配或功能模式。
去耦清单可使用已解析的标准 KiCad Device:C 等符号确认无源类别，仅证明类别，不证明实际料号、
容量额定或贴装；显式类别声明优先，自定义/未知符号仍需确认。无法分类的器件记为未知并形成
缺口，不按名称推定不适用。

**器件类型以原厂手册为准，由工具核验原文。**

第一步，审查者读手册，在 `intent.device_kinds.<ref>` 写下声明：`kind`、`page`、`quote`。
- `kind`：bjt/mosfet/diode/zener/tvs/opto/bridge_rectifier/transformer/connector 等，与检查器的器件类别一致。
  集成电路声明它的**角色**（`board_intent.IC_KINDS`）：pwm_controller、gate_driver、sr_controller、pd_controller、
  regulator、supervisor、opamp_comparator、shunt_reference、mcu、transceiver、isolator；手册标题没有这些角色的才写
  泛称 `ic`。角色决定哪些 IC 是电路候选的核心器件（`ANCHOR_KINDS`：除 isolator 与 ic 之外的全部角色），
  所以 U/M 位号与 Q/D 位号一样，没有核验过的类别就在 DEV-D02 登记 `intent.device_kinds.<ref>` 缺口。
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
1. 关键字（basis `part-keyword`）；
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
schema 1，`rules_version` 2026-10-21.1，绑定 `db_sha256` 与 intent 的 `input_sha256`）：电路不由审查员画，由网表、已核实的器件类别和检查器库存生成，
审查员只做决定（见[计划与结果](plan-and-results.md#一intentjsonschema_version-3)）。
- 候选 = 类型 + 核心器件，编号 `<类型>-<核心器件>`（链为 `<类型>-<核心器件>.<脚>`），工作态按类型固定（`catalog.CANDIDATE_STATES`：
  变换器和输入保护 startup/run/fault，USB unattached/attached/fault，ANALOG run/fault，ISOLATION run，STARTUP power-on/restart，DEBUG run）。
  成员各带 `role`、`via`（走到它的路径，是归属关系，不是导通主张）和 `hops`；页码只作显示，不决定归属。
- 走线只经两端件（电阻、电容、电感、二极管、保险、压敏、NTC），最多 4 跳（ANALOG 2 跳、输入走线 6 跳），
  到截止网络、地、其他核心器件、跨域器件即停；截止网络 = `domains.rail_stops` ∪ 地 ∪ 感性负载库存的轨/输出/回流网 ∪ 输入走线的首个储能网，无人驱动的开关算作核心器件重算截止网络。
- 规则按确定性从高到低：输入保护 `POWER_PROTECTION-<连接器>`（从电源连接器走到首个储能电容或变换器输入轨，桥和四脚共模扼流圈直通，至少含一件保护件）；
  链 `POWER_PROTECTION-<核心器件>.<脚>` / `STARTUP-<核心器件>.<脚>`（保护脚、启动脚沿两端件和光耦走到截止网络或开关节点，另一核心器件作终点，跨电路）；
  变换器 `POWER_CONVERTER-<核心器件>`（核心器件 = pwm_controller / sr_controller / regulator / gate_driver 的 IC，或无人驱动、或 `power_switches` 声明了角色而驱动 IC 没有核验角色的开关：
  所属开关、栅极下拉、吸收网络、感性件与它的其他绕组、绕组上的整流和输出电容、反馈光耦；辅助绕组的整流归它供电的变换器；sr_controller 与声明的同步整流管不收感性件）；
  隔离 `ISOLATION-<域A>/<域B>`（该域对的全部跨域器件，跨电路）；`ANALOG-<核心器件>`（pd_controller / supervisor / mcu / transceiver 的检测脚，运放、基准的全部信号脚；
  两地之间的分流电阻）；`USB-<连接器>`（CC/D± 脚一跳、PD 控制器及其 VBUS 开关与钳位）；`DEBUG-BOARD`（测试点、调试连接器，不走线）。
- 裁决：一件器件两个电路候选都走到，路径短的得；同距离留在两者里；核心器件不共享；跨电路候选不参与。
- 归属（schema 2）：每个成员带 `owned`。认领强弱 `claim_rank`：电路的核心器件 0、电路成员 1、电路里的端点类角色 2、链路成员 3、
  隔离带 4、链路的核心器件与端点 5；最强的唯一认领者拥有它，其余候选只引用它。打平的器件谁也不拥有，列入 `shared`，由 own 决定裁定。
  谁都没走到的已贴器件进 `unassigned`（REQ-Q08 逐颗列出），没核验角色的 IC 和缺引脚名的感性件进 `gaps`。
- 生成对器件顺序和页码变化是确定的；候选文件随记录打包，改了 db 或 intent 的输入指纹就重新生成、重新决定。
- 计划生成按功能树分模块：`plan_review.py` 只管加行、合并、挂接扫描发现和汇总，电路与器件的行在 `plan_circuits.py`，接口的行与框架在
  `interfaces.py`，系统功能在 `plan_system.py`，全板、文档、需求与覆盖在 `plan_board.py`（`ReviewPlanner` 混入这四个模块的方法）。
- 行归属（`scripts/row_owner.py`）：计划汇总时给每行写 `owner`，按行对象、规则和各电路拥有的器件推出，写入计划的 `owners`；
  `validate_review.py` 按 `owners` 重算，写错的行被拒绝。
- 接口（`scripts/interfaces.py`）：从各电路拥有的器件和网表推电路对、链路、供电、对外四种接口及端点角色、参考地分区、供电，写入计划 `interfaces`。
  轨 = 电源树找到源的网，或 intent.power_rails 声明且有 IC 取电或大容量储能电容的网；名字像电源轨不算。
  源 = 轨上电源树的源脚（库类型不是输入），否则轨上整流管（二极管阴极、整流桥 + 脚）的唯一所属；都没有记缺口。
- 接口检查项：`plan_review.plan_interfaces` 按 `catalog.INTERFACE_SUBJECTS` / `INTERFACE_NET_SUBJECTS` 逐接口出行并建接口框架；
  `catalog.INTERFACE_RULES` 的其余行（检查器、扫描）网络都落在一个接口上时由 `row_owner` 归该接口，连接器的接口优先。
- 系统功能：`plan_review.plan_system` 按触发生成 PWR-T06（地网 ≥ 2）、RST-T03（电源轨 ≥ 2）、SIG-D13（有可能是主控的 IC），
  `plan_system_frames` 给每个有行的系统功能建框架；`plan_owned_parts` 按各电路拥有的器件生成 DEV-C01/C02/C03。
- 覆盖审计：`row_owner.coverage_errors(plan, db)` 查每颗贴装器件恰归一块电路或在 REQ-Q08 清单上，`interfaces.coverage_errors(plan)` 查每个接口有它的行和框架；两条都由 `validate_review.py` 执行，归属审计只在电路来自候选时启用。

**装配状态**：全部检查器共用 `intent.assemblies`，只写一次：1–32 个唯一状态，每项必须有 `id`
与 `citation`。`population` 只接受 JSON `true/false`，缺项表示未知；`jumpers` 按位号填
`closed/open/unknown`，跳线还需 `population=true` 才导通。经核对的状态声明可以覆盖解析器的
`nc` 标记，输出保留原标记，并在 citation 说明变体依据。未声明时按网表 `nc` 形成"按图状态"，
同时登记 `assembly state unverified` 缺口。检查器段里写 `states` 会被拒绝。

**器件脚表**：`intent.devices` 按位号声明准确 MPN/封装、身份解释与完整官方物理脚表，供去耦分组、
官方物理脚差集（DEV-D02）与引脚处置（DEV-D05）共用。

**指纹绑定**：声明了 `assemblies`、`devices` 或任一检查器段时，意图必须带顶层 `input_sha256`
（覆盖电气指纹、符号声明脚、伪网与输入完整性），旧声明不得静默用于新网表。取值：候选清单输出
的 `input_sha256` 字段，或 `python3 scripts/decoupling.py db.json --json candidates.json`。

**清单与计划**：`plan_review.py` / `lint.py` 每次重新生成清单并嵌入 `review-plan.json` 的
对应顶层键，不读取旧清单当事实。另存清单：

```sh
python3 scripts/lint.py db.json --checker-json <checker-id>=inventory.json
```

**缺口与结论**：`coverage` 的 `DISCOVERED`/`INCOMPLETE` 都不是电气 PASS；清单里"有这颗器件"
不触发自动通过。缺口必须补齐或保持 `INSUFFICIENT`；带缺口的对象不能写 PASS。电气判据初始
一律 `WAITING_EVIDENCE`，需专家提供适用规格、工况计算与逐项结论。

**证据计算**：检查器的证据计算规则（方式 E）走同一条 `evidence.json` 管线（字段见
[datasheets.md](datasheets.md)）。输入只接受带出处的保证值：
缺任一项即 INSUFFICIENT，不用典型值顶替；比值与寿命系数必须来自项目规定。PASS 的 scope
写明未判定的部分，计算角点保留在 calculation。

**校验**：`validate_review.py --db` 重建清单并逐项对比，拒绝被删检查、改写判据、被篡改的
摘要/缺口与过期绑定。审查者补查项必须使用独立对象，不得复用生成项的对象。摘要只绑定被审
输入，不验证引用文字真实，也不替代工程审查。

**规则编号**：检查器的规则与其他规则共用[规则总表](check-catalog.md)的编号（`内容域-方式序号`），
在 `scripts/catalog.py` 以检查器 id 为来源登记；检查器类只引用编号，自动扫描（A）与证据计算（E）
规则由 `cold_rules`/`hot_rules` 从总表取出。下文各节列出每个检查器使用的规则。

### I²C 连接覆盖（`i2c_topology`）

维护范围：发现 I²C 端点、上拉、串阻路径和边界，生成逐状态审查计划。

不提供配置时按 SDA/SCL 引脚名、网名生成候选，`SCLK` 不独立触发 I²C，未识别的接口不能判 NA。
显式传入的 intent 根值必须是 object，`null`/数组会报输入错误；畸形 db 容器在入口拒绝。

```json
{
  "input_sha256": "填写候选清单里的 input_sha256",
  "assemblies": [{"id": "run-option-A", "citation": "装配 BOM Rev.B 选项 A；跳线配置表 Rev.C 第 2 行",
                  "population": {"U1": true, "JP1": true}, "jumpers": {"JP1": "closed"}}],
  "i2c_topology": {
    "schema_version": 2,
    "buses": [{"id": "CONTROL", "sda": ["U1.5"], "scl": ["U1.6"],
               "citation": "已核对的 U1 物理脚表与原理图页 2"}],
    "components": {"U1": {"kind": "endpoint", "citation": "U1 接口角色核对记录"},
                   "JP1": {"kind": "jumper", "citation": "JP1 两脚跳线定义"}},
    "rails": {"VCC_3V3": "本版电源树节点 A"}
  }
}
```

- `buses`：每组唯一 `id`，`sda/scl` 为非空、去重的物理节点数组并给角色证据。可包含同一逻辑
  总线不同侧的已核对端点；工具不会把隔离器或有源器件两侧短接。不熟悉的引脚命名用显式物理
  节点补齐，直接把不明节点加进数组不能替代查引脚功能。
- `components`：可选类型声明（`resistor/jumper/endpoint/connector/level_shifter/isolator/switch`），
  各带出处。R、JP、J/P/CN 前缀只提供候选类型，其他无源位号需显式声明。未声明 `links` 时导通边
  只支持恰好两个物理脚；多脚电阻/跳线必须有原件逐对配对出处，不能把 IC 当无源桥接。
- `rails`：按网络名声明已核对的供电域及出处，只确认身份，不提供轨压或供电能力证据；轨名推断
  的供电域保留 `rail-identity` 缺口。
- 电平转换器/隔离器/开关可加 `ports`，每对 ports 单独提供 SDA/SCL 种子；端口未映射时记
  `boundary-port-map` 缺口，不猜另一侧引脚。各侧永远单独追踪；内部传输、EN/RESET、方向、掉电
  与漏电行为留给电气检查。

单独生成清单：`python3 scripts/i2c_topology.py db.json --intent intent.json --json i2c-topology.json`。

| 字段 | 含义 |
|---|---|
| `buses` | 声明/端口/名称候选，以及 SDA/SCL 所属连接区域 |
| `regions` | 仅经已确认导通的物理无源支路可达的网络集合，不跨有源器件 |
| `regions[].edges` | 位号、物理脚、两端网、串阻值/公差、装配与模型出处 |
| `regions[].segments` | 仅由 0Ω/闭合跳线相连的拓扑段；非零串阻两侧仍是不同段 |
| `regions[].pullups` | 每条已确认贴装上拉支路只出现一次，含物理脚、供电域、阻值与可复现路径 |
| `path_origin_net` / `pullups[].path` | 路径起点网及依序经过的边位号；不是电压传递模型 |
| `pullups[].rail_path` | 上拉供电端到供电域依序经过的已贴装 0Ω/闭合跳线边；直接接轨为空数组 |
| `endpoints` / `boundaries` | 物理端点、串联断点、未知器件、有源器件或外接端口 |
| `gaps` | 未核装配/角色/供电域、未映射边界、未知外接模块、输入错误或追踪上限 |

有限串阻允许追踪到远端上拉，但不做理想短接或跨串阻直接并联。断开/不贴的选件不连接两个区域。
供侧跳线也需逐状态核装配和闭合证据；上拉经闭合跳线接轨可以发现，但不会通过公共电源把
SDA/SCL 合并。供侧有限电阻、开关/有源边界不被短接；发现串联支路仍须按完整路径计算，不能将
最后一只电阻值当总上拉。多供电可达或追踪上限保留缺口。库存发现不等于门限、时序或掉电保证。
`components.<ref>.links` 可用于有原件配对出处的电阻阵列或多脚跳线，逐对声明同一位号的两个物理脚，
覆盖该位号全部物理脚；不从脚数或位号推断内部连接。电阻阵列限各支路具有同一已核名义阻值，
沿用该器件值字段逐支路保留有限阻值、装配状态和路径；混合值或未知内部结构不能用此模型冒充已知。
例如四个隔离电阻的声明是 `[["R3.1","R3.8"],["R3.2","R3.7"],["R3.3","R3.6"],["R3.4","R3.5"]]`，
kind 仍为 resistor；共端阵列须由原件证明共端，不能把所有焊盘短接。每条上拉按其实际信号网归属，
经有限串阻相连的不同节点仍保留各自路径。此声明不扩大 SIG-E01 直接等效计算，不产生电气 PASS。
多焊盘跳线的连接对（如 `[["JP7.1","JP7.2"],["JP7.2","JP7.3"]]`）须引用实际封装铜桥/原件；每对只在该装配
`population` 为 true 且 `jumpers[ref]=closed` 时导通，open 时全部断开，不表示独立切桥变体（后者需另建能表达实际连接的输入）。
未声明多脚模型仍有缺口，不按 `NC_TRACE` 猜铜桥。清单给每对唯一 `edge_id`，保留实际位号/节点/边界，不跨供电轨合并 SDA/SCL；
经铜桥到轨的偏置仍须沿实际 R→铜桥→轨审查者复算，不自动给上拉等效值或电气 PASS。整链 SIG-C01/SIG-C07 未指定外端时
按模块范围判适用性，不能把单个接收器自身的 VOL 与 VIL 比较当完整双端匹配；窄本体能力另绑明确判据/状态，保留 INT。
连接器后的外部上拉一律未知，需取得模块/线缆网表或另留专家证据。追踪用去重队列处理环路；
每状态最多 1024 个候选网络，达上限记录缺口及 `unvisited_seed_nets/unvisited_frontier_nets`。
`segments` 是连接分组，不证明 0Ω/跳线无压降或无限带宽。

计划：每状态、每连接区域新增 1 项连接覆盖检查（SIG-T02），并逐区域展开 I²C 功能电路的电气判据（SIG-C01
灌电流/上升时间、SIG-C07 电平与驱动、SIG-C08 掉电与跨域注入、SIG-D01 地址/复用/装配状态），
不再按功能电路重复生成一套。有限串阻各段保留节点做关联分析，有源器件两侧另查传输条件。
不能由"有一只上拉"生成 PASS。本清单与 SIG-E01 的直接连接/直接并联计算并存，不扩大后者模型，
也不自动把清单或 state population 注入证据计算；不同装配变体需各自的 db 与绑定该 db/状态的 evidence。

**外部端口**：`external-port:*` 保留在清单、`required_inputs` 和 WAITING_EVIDENCE 中，不伪装成已建模端点。
SIG-T02 连接覆盖、SIG-D01 地址/选件和 SIG-C08 掉电路径可依据已绑定原图、端口定义、适用工况和约束审查者判局部 PASS，
不因外部系统未建模而强制判证据不足；局部判据自身无证据时仍 INSUFFICIENT。这不证明外端电气合格，也不放过未审的
掉电源、地址冲突或隐藏连接。SIG-C01 数量/上升窗口与 SIG-C07 电平/驱动仍因外端缺口不能 PASS；装配未知、未辨器件/
角色/rail、跨 SDA/SCL 短接、搜索截断等其他拓扑缺口对全部判据都阻止 PASS。

### 去耦覆盖（`decoupling`）

AI 已核对的角色和电源/返回分组可用 [可复用声明](reviewed-declarations.md) 保存并供后续检查读取；
文件、网表、装配或工况变化会拒绝旧记录，须重新核对。声明复用不迁移电气结论。

维护范围：逐器件、物理电源脚、直接供电/返回网络、装配状态与电容清单。不是 PDN 求解器，
也不判定去耦是否合格。

不传 intent 时按物理脚名称/类型发现候选，并纳入符号声明但未连的脚；未核器件另列
`unverified_device_refs`，不能因没有常见 VDD/VCC 名称便判不适用。官方脚表中网表完全不存在的
电源脚也会生成候选，不能只检查网表实有脚。
两端器件（二极管/齐纳/TVS/LED、热敏/压敏电阻、保险丝等）不需要供电，也没有供电/返回脚对可去耦，
不论符号库或脚名，都列入 `two_terminal_no_supply_refs` 而不产生 `unverified-device-pinout` 缺口；它们按极性
与方向设计，由极性、连接追踪和图面目检规则核对。解析器列出了全部符号脚（`declared_pinname`）时，没有引脚的符号（安装孔、基准点）同样列入该清单。单脚器件和三脚及以上器件（含双二极管、桥堆）仍按未核器件处理，单脚可能是解析残缺的多脚器件。

```sh
python3 scripts/decoupling.py db.json --json decoupling-candidates.json
python3 scripts/decoupling.py db.json --intent intent.json --json decoupling-inventory.json
```

顶层 `input_sha256` 取候选清单输出中的同名字段，它包含电气指纹及 `declared_pinname/declared_pintype`、
伪网、输入完整性/导出状态；只绑 `db_sha256` 不足以覆盖符号未连接脚。本模块不修改 db、BOM
或任何电路。

```json
{
  "input_sha256": "替换为候选清单的 input_sha256",
  "assemblies": [{"id": "run-option-A", "citation": "装配 BOM Rev.B 选项 A 与运行工况表第 2 行",
                  "population": {"U1": true, "C1": true, "C2": false}}],
  "devices": {"U1": {"mpn": "TEST-IC-EXACT", "package": "TEST-PKG-3",
                     "identity_citation": "BOM 订货码/封装与官方订货表对应行核对记录",
                     "citation": "准确型号完整物理脚表 Rev.A 第 3 页", "pinout_complete": true,
                     "pins": {"1": {"name": "VDD", "role": "power"},
                              "2": {"name": "VSS", "role": "return"},
                              "3": {"name": "IO", "role": "other"}}}},
  "decoupling": {
    "schema_version": 3,
    "components": {"C1": {"kind": "capacitor", "citation": "BOM/符号确认 C1 为两脚电容"}},
    "groups": [{"id": "U1-VDD", "ref": "U1", "supply_nodes": ["U1.1"],
                "citation": "准确器件电源分组要求 Rev.A 第 8 页",
                "requirements": [{"kind": "connection",
                                  "criterion": "填写本组实际适用的电容接法条款，不用通用每脚一颗规则",
                                  "citation": "官方适用条款版本/页码/表号"}]}]
  }
}
```

- `intent.devices`：准确 MPN/封装、身份解释、完整官方物理脚表及出处。脚表取手册引脚定义的编号或名称；手册只用名称标注时
  名称即脚号（与符号脚号一致），不另要焊盘编号图。`pins` 含全部物理脚，角色为
  `power/return/nc/other`，脚号是字符串，支持 BGA/EP。`pinout_complete=false` 保持缺口。这是有出处的
  审查者声明，脚本不读 PDF 验证真实性，也不因字段齐全自动判通过。器件类型另写在 `intent.device_kinds`，
  由手册审计核验原文，见上文“器件类型以原厂手册为准，由工具核验原文”。声明后计划项 DEV-D02 附双向差集、
  DEV-D05 附未接网脚与"标 nc 却接了网"的脚，仍由审查者逐脚定判。
- 官方脚表与符号/网表脚表做双向差集，各自记录多出的脚（`official_only_nodes/symbol_only_nodes` 保留完整差集）；去耦缺口只对电源/地角色的差异脚计入，其他功能脚的差异由 DEV-D02 逐脚处置。官方 power 脚未入 group 时自动列候选。
  不得为消除缺口把缺失电源脚改成 `other`。
- `groups`：按器件具体条款划分，不要求每个电源脚单独一颗电容。供电脚必须属于该器件官方 power 角色，
  不能重复分组；每组只支持一个直接供电网。返回脚不写：取官方脚表里该器件全部 return 角色的脚；这些脚落在
  不止一个网上时，组写 `return_net`（其中一个网，出处写在组的 `citation`），只取这个网上的返回脚；只有一个返回网时写
  `return_net` 被拒绝。跨网分组不合并，保持缺口。
  飞跨/bootstrap/补偿以及内部稳压输出端的必需外接电容按专用条款另审；
  组可加 `purpose`：默认 `bypass`；`no_direct_capacitor` 表示按原厂条款该脚不需要直接电容（如高压启动/检测脚 HV），
  图上也没有直接电容时 PWR-C09/PWR-C10 记不适用，PWR-T03/PWR-D02 仍核接法；`regulator_output` 表示片内稳压器
  输出电容（如 V5/VCAP/REG）。两者都必须有带出处的 `connection` 条款。
  声明组只需本组供电/返回脚在 `intent.devices.pins` 里有角色和出处：整颗器件脚表不完整时
  `official-full-pinout` 只留在 PWR-D01，不再挡这一组；本组器件上未核实的供电脚差异仍挡本组。
从官方逐脚外围要求核这些对象，不因符号输出类型或没有 VDD/VCC 名称而漏掉，也不从"连到电容"推断属于普通组。
- `components`：支持 `capacitor/resistor/ferrite/inductor/jumper/switch/bridge_rectifier/transformer/other`，都要有出处。
  C/R/L/FB/JP 前缀仅为候选类型；计入确认容量前需核类型与装配。`other` 是有证据的类别排除，
  不是规避官方电源脚审查的通用开关。
- `requirements`：手册条款，每类（`connection/capacitance/rating`）至多一条，只写 `kind`、`criterion`、`citation`，不写编号。
  每组固定问 PWR-T03 和三类各一行（PWR-D02 连接、PWR-C09 容量、PWR-C10 额定），问题用规则总表的判据；
  条款挂在对应行的 `clause` 上，不进检查项标识，所以两人措辞不同仍是同一项检查。缺连接或容量条款的行等手册
  （`datasheet-requirement:<类>`），不默认 NA；额定没有条款时按总表默认判据预判。条款对声明的全部 states 适用，
  状态相关的限值必须在条款中写清条件。

| 字段 | 含义 |
|---|---|
| `groups[].capacitors` | 两端直接匹配本组供电/返回网络的电容，含不贴/未知候选 |
| `fitted_capacitors/fitted_count` | 类型、两脚连接与本状态贴装均确认的唯一位号/数量 |
| `known_nominal_subtotal_f` | 已贴电容中可解析标称值的已知小计，可为部分数据 |
| `nominal_total_f` | 仅当连接/覆盖/装配及容量均无缺口时给出，否则 null；不是有效容量 |
| `rejected_capacitors` | 接到供电侧但不匹配本组两端连接的电容 |
| `boundaries` | 供电网边缘的电阻/磁珠/电感/跳线/开关；始终 `crossed=false` |
| `gaps/capacitance_gaps` | 身份/脚表/连接/装配缺口与容量解析缺口分别记录 |

PWR-T03 与连接型 PWR-D02 只审本组供电/返回连接；在完整官方脚表与显式分组角色均已核对时，别组的同器件脚差集不阻止本组局部结论。完整差集保留在原清单、`full_inventory_gaps` 和全局 PWR-D01；本组脚图/归网、装配、来源身份、返回或条款缺口仍不能 PASS，局部结论不证明整器件、容量/额定或全板覆盖通过。
所有串联元件均不跨越，包括 0Ω 和闭合跳线；上游储能电容不计入下游本段。不同地网不因名字相近
而合并。同网共享电容不是每颗 IC 本地去耦充分的证据；各组容量不能相加成整板总量。实际距离、
回路、ESL/PDN/布局由 PCB 阶段验证。

标称值只解析有明确单位的首项（100nF、4.7u/10%/16V、4n7、1e-6F），不猜 104 等裸编码；无法解析的
已贴电容保留数量与缺口，不当作 0，不猜耐压/介质，不自动估算 ESR 或降容系数。
手册指定的标称旁路值、允许范围和有效容量下限分别记录；只有原文规定下限时才作大于等于比较。
容量更大或同器件另一电源脚的电容不构成替代批准；未有适用替代依据时保留该局部符合性待核，不能据此断言实际功能失效。

计划：清单完整性项（PWR-D01）+ 逐状态逐组连接覆盖项（PWR-T03），随后分开审查接法（PWR-D02）、
数量/容量（PWR-C09）与额定值（PWR-C10）；`requirements` 的三类 `kind` 依次对应这三条规则。电气行的
`required_material_refs` 列出目标器件与本组已确认贴装的电容，供资料取证时按需
`audit_datasheets.py --require-ref C1`；按实际判据绑定受控电容规格，依赖具体偏压/ESR/寿命特性时核准确订货码，不能用一般
`datasheets.available` 代替适用参数。容量缺口不自动否定另一个
已证实的窄连接结论。标准无源符号类别不再重复索取 components 声明；power_in 只生成候选，
HV 启动/检测或端口储能等角色须按实际器件条款确认，不能由该类型强制本地去耦。

### 感性负载续流与钳位（`inductive_load`）

维护范围：识别继电器线圈、由开关驱动的电感/绕组、经连接器外接的感性负载，登记每个装配状态下
的钳位路径。只回答"有没有、接法对不对、缺什么证据"；额定值是否足够由 DRV-C01 按器件资料判定。

识别与排除：

- 线圈/绕组两端分别为开关节点与电源轨时成立；开关可以是分立 MOSFET/BJT（按引脚角色）或驱动
  芯片输出脚。
- 继电器符号没有脚名时，恰好一个脚网是开关节点、其余脚网中恰好一个是电源轨或经单个二端无源件
  （如线圈串联电阻）接到电源轨，才把这两网当线圈端，并登记 `pin-roles-inferred` 缺口要求按手册核对；
  条件不唯一时不猜，保留 `pin-roles` 缺口。只凭 `K` 位号识别、只有两脚的器件不当继电器（部分库把连接器编为 K）。
- 斯拉夫语库的脚名（ANODA/KATODA/KOLEKTOR/EMITER/BAZA）与英文脚名等价。
- 开关节点上出现 `SW/LX/PH/VSW/BOOT/BST` 类引脚名时判为开关电源储能电感，不属于本检查器。
- 对外置 MOS 的低边升压形状，按实际引脚连接生成 `boost_converter` 候选：电感输入端有输入电容，
  另一端连接唯一 MOS 漏极和二极管；二极管另一端有输出电容，两侧电容共用返回网，MOS 源极直接
  或经最多三只已贴电阻/跳线返回该网，栅/漏/源及二极管阳/阴极角色明确。多个二极管输出候选、
  并联开关、缺脚名或缺贴装路径时保留原待核，不能凭 PFC/BOOST 网名豁免。此识别局限于局部连接，
  不证明 MOS 沟道极性、稳压功能、工作模式或上下游供电条件。
  清单保留导通 `输入→电感→MOS→采样电阻→返回` 和关断 `输入→电感→升压二极管→输出` 路径，
  输出电容分别作为返回支路；关断路径不穿过 MOS 主通道，输入供电回路闭合须另核。
  保留 DRV-T01/DRV-C01 两项并改用升压用途判据，不再索取线圈电阻，也不删除额定审查：T 核路径、
  方向、贴装与工作状态；C 独立核二极管反压/重复峰值/平均/RMS/损耗、MOS、电感及母线电容应力。
  识别出拓扑不自动 PASS；非重复浪涌额定不能替代重复工作保证。反向升压二极管仍报 DRV-A02，
  二极管不贴或不存在时仍保留缺路径检查；装配缺口仍阻止 PASS。
- 两绕组共模输入滤波器可在 `loads` 中声明 `kind: common_mode_input_filter`，同时提供有出处的用途及
  **物理脚配对** `windings`（恰好两对、四个不同引脚，覆盖全部实际引脚）。检查器核对四端为不同的
  非地、非伪网、非 NC 网络；已有原生脚型必须为 passive。再沿已贴装的二端串联无源路径检查
  MOSFET/BJT 或 IC 驱动/SW 引脚的矛盾证据。有缺口、重复声明或矛盾时保留待核，不能仅凭名称排除。
  配对和用途来自引用资料，检查器不会自行从四个引脚猜绕组，也不向共享图添加绕组边或合并 L/N。
  满足上述条件时，清单保留出处与配对，DRV-T01/DRV-C01 计划为 `NOT_APPLICABLE` / `NA`，
  不再要求普通被切换线圈的钳位计算；这仅是适用性判断，不证明载流、绝缘、温升或 EMI 合格，
  也不覆盖未知器件内部的驱动行为。首次遇到此类器件仍需审查员核实用途和配对后再作声明。
- 多绕组反激可声明 `kind: flyback_transformer`，`windings` 每项为
  `{"role":"primary", "pins":["1","2"], "dot":"1"}`；其他项的 role 为 secondary/auxiliary。
  须有当前受控绕组图出处；恰好一个初级、至少一个次级、配对覆盖全部已连接物理脚且不重复（只有 NC 或单节点网上的空脚可不列），
  每绕组两个不同的非伪网/非NC端点，dot 是其中一个脚；已有原生脚型应为 passive。
  初次级同网会报输入错误，绕组配对不向共享图添加导电边；这不代替其他路径和制造绝缘审查。
  当前支持初级同名端接供入、另一端有唯一已识别开关节点的常见低边反激，反向同名端或不明角色保留缺口。
  RCD 按 `开关节点→二极管→钳位节点`、该节点经已贴电容及并联电阻返回初级供入网识别，
  供入网除电感/继电器另一端和已声明的反激初级外，也取开关节点上未声明变压器的其他端子中带 ≥1µF 对地储能或本身是轨的网（BULK）；次级/辅助端子没有储能不算供入，绕组角色仍由声明核。
  支持多只并联阻容并保留实际贴装清单；缺件、未知/反向二极管或多条不明支路不能当作拓扑通过。
  没有 RCD 时，跨开关或跨初级的 TVS/齐纳按漏感钳位登记（`leakage_clamp`）；钳位电压须高于输入加反射电压、
  低于 MOS 耐压，由 C 计算核对。符号分不出阳极/阴极（如单向 SMCJ 画成双向 D_TVS）时保留
  `flyback-tvs-clamp-polarity:unknown:<位号>`。
  每个绕组当前只能声明两个物理脚；多脚并联引出的绕组（如 Coilcraft DA2032 的 3–6/7–10）暂不支持，保留缺口，
  不按脚号猜配对。
  T 清单区分导通磁化储能、关断向次级/辅助绕组的耦合送能候选和独立的漏感吸收路径；
  次级整流、同名端及返回仍需审查，不把RCD当作全部磁化能量的去向。
  C 单独要求漏感/峰流/频率/反射电压与正常/保护状态，算钳位纹波、MOS峰压、阻容和二极管应力。
  有RCD支路不自动PASS，不用 `0.5*Lm*Ipk^2` 代替漏感能量；
  `0.5*Llk*Ipk^2*f` 也只是漏感释放功率，实际RCD耗散还受反射电压和钳位区间影响。
  对返回输入母线的RCD、三角漏感电流及近似恒定钳位电压，先用
  `K=0.5*Llk*Ipk^2*f`、`Vc=(Vr+sqrt(Vr^2+4*K*Req))/2`、`PR=Vc^2/Req`
  复算平均值；Vc 是钳位电容相对母线的电压，不是 MOS 漏源绝对峰值。
  再核 `tclamp≈Llk*Ipk/(Vc−Vr)`、`ΔVc≈Ipk*tclamp/(2*Ceff)` 与阻容公差；
  MOS 峰压还含母线、钳位峰值、二极管正向和寄生过冲。纹波不可忽略时用有条件的逐周期模型，
  并说明保护动作期间是否达到周期稳态；不能只算平均值或把任意振铃预算当保证。
  普通料可导出有效容量、电压、平均/脉冲功率等采购下限，不因缺准确MPN自动判不通过。
- 网名含 `MOTOR/SOLENOID/VALVE/COIL/RELAY/PUMP/BRAKE/FAN/ACTUATOR` 且经连接器外接的负载只作
  `name-hint` 候选，计划项为 `UNDETERMINED`，不产生自动扫描发现。
- 钳位识别：负载两端的续流二极管（按阳极/阴极角色判方向）、开关两端的 TVS/齐纳、跨负载或跨开关
  的 RC，以及驱动芯片 `COM/CLAMP/VS` 类引脚接电源轨形成的"集成钳位候选"（需资料证据）。
  引脚角色缺失时方向记 `unknown` 并形成缺口，不推定方向。

```json
{
  "input_sha256": "填写当前 db_fingerprint(db) 的 64 位哈希",
  "assemblies": [{"id": "run", "citation": "装配 BOM Rev.B 选项 A",
                  "population": {"K1": true, "D1": true, "Q1": true, "L1": true}}],
  "inductive_loads": {
    "schema_version": 2,
    "loads": [{"id": "K1-COIL", "ref": "K1", "kind": "relay",
               "switch_net": "RELAY_DRV", "rail_net": "V24",
               "citation": "继电器线圈参数与驱动方式核对记录"},
              {"id": "AC-CMC", "ref": "L1", "kind": "common_mode_input_filter",
               "windings": [["1", "2"], ["3", "4"]],
               "citation": "当前输入滤波设计记录及对应器件官方绕组脚表，注明版本/页码"}],
    "exclusions": [{"ref": "L7", "citation": "已另行按变压器条款审查"}]
  }
}
```

自动扫描规则：

| 规则 | 触发 |
|---|---|
| `DRV-A01` | 已识别负载在该状态下没有任何钳位路径（含钳位器件不贴）；驱动器内部钳位需资料证据 |
| `DRV-A02` | 续流二极管方向接反：阴极在开关节点、阳极在电源轨 |

计划项（逐负载、逐状态）：钳位拓扑与方向（DRV-T01）；钳位额定（DRV-C01）——反向耐压不低于电源最高电压，峰值/重复电流不低于线圈关断
瞬间电流，齐纳/TVS 钳位时开关器件耐压需覆盖电源电压加钳位电压，并核重复频率下的耗散。

### 功率开关 `power_switch`

维护范围：按引脚角色识别分立 MOSFET/BJT/IGBT，登记栅极驱动源、栅源下拉、开关节点上的
感性元件与吸收网络。引脚角色缺失时只登记缺口（`pin-roles:REF`），不推定拓扑。

- 驱动源：栅极网上的驱动输出脚（引脚名 HO/LO/OUT/DRV/GATE 或引脚类型为输出）、经串联
  电阻/磁珠一跳到达的同类脚、前级开关管漏极、连接器（外部驱动）。
- 高/低边由源极所在网判定：地=低边，电源轨=高边（记 `source_rail_basis`），其余=浮地/半桥；
  自举高边开关的源极坐在开关节点上，按浮地记。
- 吸收/钳位：开关节点到地、源或电源轨之间的电容、TVS/齐纳/二极管、RC（漏→电阻→中间节点→
  电容→目标网）。跨负载接到电源轨的续流二极管同样计入，不只看漏源之间。
- 开关节点证据：节点上的电感/变压器/继电器、对管源极、`SW/LX/PH/HS/LS` 类引脚。

intent 段 `power_switches`（`switches[]`: `id/ref/role/gate_net/citation/source_return`）声明实际角色及出处；
装配共用顶层 assemblies；未声明时按图扫描并保留 `assembly state unverified` 缺口。
带出处的 role 可用 `linear/source_follower/emitter_follower` 明确线性用途：不生成 RDS(on)
开关驱动窗口，改查实际工作点/驱动/额定；感性节点的钳位候选仍保留，按实际拓扑确认。BJT 不生成 MOS 的 DRV-E01；
共用图坐标 gate/drain/source 对应 B/C/E，仅用于追踪。角色未知仍保留证据不足，不按浮地位置猜用途。
`role: "level_shifter"` 用于栅极接低侧轨的双向开漏电平转换管：它不是功率开关，不生成 DRV-E01、DRV-C02、DRV-D01
及 DRV-A03/A04，改按电平转换电路审查，见 [计划与结果台账](plan-and-results.md) 的“电平转换（LEVEL_SHIFT）”与
[WCA 公式](wca-formulas.md#mosfet-双向开漏电平转换)。

源极经单只采样电阻回地时，可声明 `source_return: {"ref":"R201","ground_net":"PGND","citation":"图纸/采样用途出处"}`。
只在该电阻实际贴装、二端确实连接源网与地、阻值可解析且源网不是电源轨时登记低边；DNP、开路跳线或错误返回保留缺口。
不从任意接地电阻自动猜用途，不把高边负载电阻当源极参考。当前有意只支持单电阻路径；复杂返回保留待核。
清单保留原源网、阻值和 `Vs=Is*R`，不会合并地网或据此放行VGS/SOA。
器件类型沿用前述 `device_kinds` 的准确PDF/页码/原文审计；仅经核验的声明才清除 `datasheet-kind`，不按料号白名单补齐。

DRV-C02 的MOS开关计划分别要求关断峰压、导通损耗、转换期间VDS(t)-ID(t)轨迹以及正常/启动/故障的重复率。
SOA须对照壳温、脉宽和单次/重复条件，不能用单脉冲曲线放行重复工作，也不能把整段低VDS导通时间当作高压线性脉冲。
典型Qg、tr/tf只可作估算；实际驱动/栅阻不同须给适用模型、容差或可验证的设计约束。重复损耗按Zth/温度边界推导允许散热条件，
原理图阶段可给明确下游约束；不把无PCB/无实测本身变成FAIL，也不自动产生PASS。

低侧N沟道反激同步整流可声明 `role: "synchronous_rectifier"`，并附同名字段：
必填 `controller_ref/channel:"n"/citation`；`sense_node/return_node/winding_nodes(两个物理节点)/output_net` 可省略，
省略时按网表唯一候选推出（控制器在漏/源网上各只有一个脚；有多个时按官方脚名 VD/CS 或 VS/GND 取唯一者；同名端接漏极的已声明次级只有一个），推出的字段记入
`derived_fields`；候选不唯一或推出后连接不一致时保留缺口，不猜。
其中绕组必须匹配 `inductive_loads` 已校验的有出处反激次级/同名端；控制器的驱动须实际到达栅极，
CS接漏极、返回脚接源极，次级同名端接漏极、另一端接输出，输出电容返回源网；所有并联S/D/G脚也须一致。
不贴、NC、反接、错误检测/返回、缺绕组或输出电容都保留缺口，角色声明不能代替真实连接。
清单绑定用于复现的绕组声明上下文，绕组/装配改变使旧绑定失效。清单记 `low-side-local-return` 和实际参考网，不把SEC_RTN等名称全局视为地，不跨隔离添加导电边。
当前只支持上述有出处的低侧N沟道反激结构；其他SR结构保留待核，不按位号猜拓扑。
DRV-C02据此追加次级峰值/RMS与S到D导通、体二极管区间、初级导通反向阻断、控制器准确后缀的
CS/触发/消隐/最小导通及关断关联条件。核CrM/DCM/CCM和故障的可达I-V-t-f组合，输出平均电流不是MOS峰流；
按电流/电压象限选择适用SOA，不把正向偏置曲线直接套到整个S到D整流周期；门极电荷或驱动连接正确不等于重复损耗通过。TRIG接低不自行判错，应按该后缀允许模式与CS换流核对。

自动扫描：`DRV-A03` 栅极既无驱动源也无下拉/上拉（上电与驱动高阻时状态不确定）；
`DRV-A04` 开关节点接感性元件或半桥中点但无吸收/钳位（CANDIDATE）。

证据计算 `DRV-E01`（`gate_drive`）仅适用需要保证导通能力的 MOS 开关：最小栅源驱动不低于 `vgs_rds_on_v`，且驱动窗口不超
栅源绝限。`vgs_rds_on_v` 取 RDS(on) 保证条件的 VGS，或取本型号输出/转移曲线在实际电流与温度下证明导通够用的栅压
（引用曲线页码并说明是典型还是保证值）；测试 VGS 本身不是硬门槛，见证据尺度文档的“功率开关：实际栅压”。P 沟道按量纲翻转后比较。PASS 不覆盖开关速度、米勒导通、SOA 与热。

计划项：栅源驱动（DRV-E01）、安全工作区与降额（DRV-C02，结温按实际散热
路径核算）、开关节点吸收与驱动器条款（DRV-D01，仅在有开关节点证据时生成）。

### 开关电源输入滤波 `input_filter`

维护范围：识别同时具备 `VIN/PVIN` 与 `SW/LX/PH/BOOT` 类引脚的开关稳压器，登记其输入网上的
串联电感/磁珠、两侧对地电容、RC 阻尼支路与体电容候选。线性稳压器不进入本检查器。

- 串联元件只认两端元件；共模扼流等多端器件记 `series-element-topology:REF` 缺口，不猜接法。
- 体电容候选按型号/值中的 ELEC/ALUM/TANT/POLYMER 等线索给出，仅为候选，ESR 仍须资料证据。
- 电容标称值沿用去耦模块的解析规则：只解析带明确单位的首项，裸编码不猜。

自动扫描：`PWR-A05` 输入经串联 L/磁珠滤波但既无 RC 阻尼支路也无体电容候选（CANDIDATE）。

证据计算 `PWR-E03`（`input_filter_damping`）：|R<sub>IN</sub>| = V<sub>IN,min</sub>²/P<sub>IN,max</sub>；
判据为 ESR<sub>bulk,max</sub> < |R<sub>IN</sub>|、ESR<sub>bulk,min</sub> > L<sub>max</sub>/(C<sub>bulk,min</sub>·|R<sub>IN</sub>|)、
C<sub>bulk,min</sub>/C<sub>in,max</sub> ≥ 项目规定比值。**这是一阶判据**：全频输入阻抗裕量、
阶跃响应与温度角仍需仿真或实测，PASS 的 scope 已写明。

计划项：阻尼判据（PWR-E03）、滤波元件饱和/压降/衰减需求（PWR-C11）。

### 上电过程 `power_up`

维护范围：识别带使能脚且有输出/开关脚的稳压器，归类使能来源，并登记使能/复位与自身供电轨
同网的负载。时序是否满足需求由 RST-T01 按需求与器件条款判定。

使能来源形态按连接关系归类，不按名称：`tied-to-input`（与自身输入网同网）、`uvlo-divider`
（到轨与到地各有电阻）、`rc-delay`（到轨电阻加对地电容）、`sequenced`（PG/PGOOD 类输出驱动）、
`controlled`（控制器输出脚）、`pulled`、`unknown`。

识别要求器件同时具备使能脚与输出/开关/反馈脚；反馈脚只用于认出稳压器，不计入输出轨。

自动扫描：`RST-A02` 器件的使能/复位输入与其自身供电脚同网（稳压器自身的直连由 RST-A03 覆盖，不重复
登记）；`RST-A03` 稳压器使能直连输入网且无分压/RC（CANDIDATE）；`RST-A04` 使能网上既无驱动源也无
分压/RC/上下拉——悬空或来源不明（CANDIDATE；器件内部上/下拉需资料证据）。

证据计算 `PWR-E02`（`dropout`）：V<sub>IN,min</sub> − V<sub>dropout,max</sub>(声明温度与负载范围)
≥ 负载要求的 V<sub>OUT,min</sub>。PASS 不覆盖负载瞬态、启动过程与热关断。

计划项：使能来源与 UVLO/时序（RST-T01）、线性轨的
压差（PWR-E02）、同步变换器的预偏置启动与软启动（PWR-D03，需资料证据）。

专家按装配/工作状态补成“实际来源/拉阻/有源控制/外接分支→EN 物理脚→自身输出→受供物理负载”的
因果记录并附出处。清单的 `enable_node/source/input/output/coupled_loads` 是追踪入口，同网或电阻桥
不证明有源、多跳、外接控制已穷尽，也不证明门限和时序合格。按该链独立写 EN 缺口、影响及任务；
下游 MCU RESET 另核自身链路、脉宽与 strap，不能代替上游 EN 来源、门限和输出恢复保证。

### 监控与看门狗 `supervision`

维护范围：识别监控器/看门狗（需同时具备 WDI/SENSE/MR 类引脚与复位类输出脚），登记喂狗输入
状态、被监测网、复位输出的去向与上拉，以及给 IC 供电的电源轨及其监测覆盖。只有复位输入脚的
主控不是监控器。

型号专用角色要求已放置的 `part` 和 `value` 均非空且一致确认精确型号；非空 `prim` 只作相符交叉核，
不能补齐缺失的已放置身份。仅有 part、value 或 prim 的单一提示均不启用；prim 缺失但 part/value
精确一致时可启用。允许首尾空白、大小写和有效库命名空间的等价写法，不从 footprint 或 datasheet 链接猜型号：
TPL5010 的 DONE4 是喂狗输入、RST6 是开漏复位输出（TI SNAS651A，2018-09，p4）；
ESP32-C3-MINI-1-N4 的 EN8 是复位接收输入（模组 datasheet v2.2，Table 3-1、§4.3）。
普通 MCU/LDO 的 DONE/EN 不继承这些角色。物理脚号、名称或方向不符、DNP 时不启用模型。
复位名用共享 `pin_aliases` 识别（包括原生 `~{RST}`）；接收端还须有明确 input/bidirectional
电气方向。native、归一及声明类型冲突、未知或纯输出（含 open-collector/tri-state）不算真实接收端。

- 喂狗输入状态：`tied`（直接坐在电源/地上）、`driven`（有其他 IC/连接器脚驱动）、
  `pulled-only`（仅有上/下拉）、`floating`。
- 轨的监测覆盖分 `sense-pin`、`divider`（经电阻到 sense 网）、`supervisor-supply`（仅供电给监控器，
  是否等于被监测需资料证据）与未监测。轨本身按电源树识别（见共用约定），逐条记 `basis`；
  只靠轨名认出的轨另记 `rail-identity` 缺口。

自动扫描：`RST-A05` 喂狗输入悬空或固定电平（CANDIDATE）；`RST-A06` 复位/看门狗输出未到任何复位输入
（网上无其他器件=FINDING，只接到其他脚=CANDIDATE）；`PWR-A06` 在已识别监控器的前提下列出未被
监测的轨（CANDIDATE）。**没有任何监控器时不报 PWR-A06**：全板是否需要监控属需求问题，由计划中的
逐电源域覆盖项（PWR-T04）承接。

证据计算 `RST-E03`（`reset_pulse`）：复位输出最小脉宽不低于目标复位输入要求；`output_type=open_drain`
时还要求该网上存在到电源轨的上拉电阻（由网表核实）。PASS 不覆盖阈值精度、迟滞与喂狗时序。

计划项：复位链逐跳与喂狗策略（RST-T02）、复位脉宽（RST-E03）、逐电源域监控覆盖（PWR-T04，逐状态一项，
未监测的轨写进 `inventory_gaps`）。

#### 逐电源轨的监控要求与来源身份

PWR-T04 按需求决定哪些域必须监控。`supervision.schema_version=2` 可增加
`rail_requirements` 数组；每项只绑定一个实际 `net` 和一个 `intent.assemblies` 的 `state`，
写 `required`（真布尔）、`criterion`（明确监控要求或不要求的范围依据）、`citation`（受控出处），
以及 `identity`；可选 `internal_monitor`：`{"node": "U1.8", "function": "VCC UVLO 及迟滞", "citation": "手册页码/章节"}`，
表示负载 IC 片内的 UVLO/欠压/掉电检测监测本轨（节点须是该轨上已贴装 IC 的脚）。声明有效时本轨按已监测计，
PWR-T04 不再报 `rail-unmonitored`；门限、迟滞与动作是否满足需求仍由 PWR-C06/RST-T03 另核。若 `internal_monitor.node` 是本轨上已贴装负载 IC 的供电脚（VCC/VDD/VIN 等），可省略 `identity`：源跟随、自供或串阻供电等写不成来源身份的轨照样能声明，负载自身的 UVLO 即确认本轨身份；监测脚不是供电脚时仍须写 `identity`。`identity` 字段：

- `source_node`：该轨实际来源的物理节点；`source_role` 为 `external_supply`、`upstream_external_supply` 或 `rail_driver`。
- `part`：实际来源器件的 `part`、`prim`、`value`、`jedec` 四字段快照（空字段保留空字符串）。
- `pin_name`：该来源脚的实际名称；`native_pintypes`：来源器件全部原生节点/类型的快照，无此原生索引时写空对象。
- `citation`：该来源角色与物理身份的定位出处。

声明须绑定当前 `input_sha256`，来源须在本装配实际已贴，名称与完整身份快照吻合。
`external_supply` 与 `rail_driver` 的来源节点须位于该真实电源轨。
外供源须有已核连接器触点身份，或书面外供角色加完整原生 passive 触点结构；选中的供入节点
始终须为实际 passive 触点且互反归网，不能是地、伪网、NC 或 active 脚。全部原生节点须完整，
原生/声明类型须一致；仅允许真实导出 no_connect、声明一致、NC 索引一致且位于独占 NC 伪网的
非供电脚。无声明对照的 NC、实体电源网/地上的 NC 都不例外。只靠 J 位号或把 IC 的 power_in/input、
二极管端或有源器件声明成外供源不成立。
`upstream_external_supply` 允许同样已资格的外供触点位于真正上游网：用 PowerTree 从目标轨回溯，
必须到达该来源且有非空路径，再逐跳核两端真实 passive、互反归网、已贴状态与非伪网/非地；
只接受 PowerTree 已支持的 0Ω/电感/磁珠/保险串联路径和身份有依据的正向二极管。
逐跳按实际已核器件 kind 判定：若为 resistor，其值必须能精确解析为严格 0Ω，不以 F/L/FB 位号
代替电阻数值；未知、缺值、负值、错单位及浮点下溢的非零电阻均不成立。真正的电感/磁珠/保险
保留自己的非零参数标签，不按电阻单位重新解释。
反向、DNP、断开、open、非零串联电阻、有源/NC 路径、同网空路径都不成立；生成的 `source_path`
保留逐跳物理脚与网络。此可选资格不修改共享 PowerTree，也不证明二极管压降、供电能力或动态保证。
板内 `rail_driver` 必须匹配 PowerTree 实际回溯的来源节点；已有原生类型时须为输出。
这些资格只证明书面声明与原生结构相符，不证明出处语义真实、精确机械变体、额定值、阈值、动作或 UVLO；
原厂资料与受控需求仍须审查者逐项核实，其他身份 OPEN 不因本声明关闭。

清单保留 `observation_gaps` 原始发现，另存 `scope_qualified` 与有效 `requirement`，按新上下文重建
清单摘要与计划。有效 `required=false` 只解除该轨×装配状态的未监测阻断；有效来源身份只解除该轨的
名称线索身份缺口。`required=true` 无监测、数组模式下未声明/UNKNOWN、缺出处、来源不存在/DNP、
身份不完整/错配、过期绑定或其他装配缺口仍阻止 PASS。重复声明不能任选一条，其他轨和状态不继承。
PWR-T04 仍适用且等待审查者审查，声明不自动产生 PASS；已有监控器不豁免其他轨，内部 UVLO 不伪装为
SENSE/RESET 拓扑。没有 `rail_requirements` 的旧配置保持原扫描与阻断行为，`exclusions` 不排除轨覆盖。

#### 内部并联稳压器的非零电阻供入来源

可选 `identity.source_role: internal_shunt_feed` 仅表达已核的来源身份：外供连接器触点经一颗
严格正值、有限的实际电阻供入原厂明确内部并联稳压器的实际 `power_in` 物理脚。
它不加入共享 PowerTree 的等价连通，不改变原生脚型，不把接收脚改成 `power_out`，
也不证明 VDD、最小偏置、ICC、PG、UVLO、门限、动作、时序或原生零 ERC。
原有三种来源角色及 0Ω 上游路径的资格保持原约定。

新角色保留已有完整来源器件 `part/prim/value/jedec`、脚名、全原生脚型与出处字段，
并增加唯一 `feed_provenance` 对象：

- `upstream_node`、`upstream_part`、`upstream_pins`：真实外供 passive 触点、源器件四字段身份和
  全物理脚快照；该源须在当前装配状态的 `intent.power_sources` 有非空受控出处。
- `receiver_pins`：内部并联稳压器的全物理脚快照，实际接收脚须是 `power_in`，位于目标轨且非 NC。
  接收 IC 的实际 part/value 和非空 symbol prim 须在两端先去首尾空白、忽略大小写，并去除可选单层库名前缀后证明同一精确型号；
  来源引用匹配也使用正规化后的实际 PART 型号，型号内部字符、前后缀及引用位置边界仍严格保留；
  重新绑定完整快照不能使互相矛盾的型号成立。连接器的描述性 Value 不受此 IC 型号等式限制。
- `feed`：`ref/from_node/to_node/part/pins/resistance_ohm_exact`，只接受一颗已贴的实际 passive
  resistor，两端直接分别归到供入网和目标网；严格精确解析非零正欧姆值。原生 Value 可附一项明确
  十进制 `W/mW` 功率标签，其原文仍完整保存，标签不证明功率资格。未知、零、负值、无穷、
  错单位、非零数值下溢、串联链或额外并联/串联 bypass 不成立。
- `receiver_source`：本器件原厂来源 `path/sha256/format/publisher/source_url/document_model/
  document_version/role_page/pin_page/identity_quote/role_quote/pin_quote/citation`。
  `path` 为存在的绝对本地路径，格式 `pdf/text`；文本来源页为 1。每次读取源字节重核 SHA，
  PDF 必须 `%PDF`，从实际页提取文字；精确型号声明和含实际脚名的 shunt/并联稳压角色原文须在
  `role_page`，物理脚号与脚名原文须在 `pin_page`。引用按 Unicode NFKC、忽略空白与标点核实际页原文，
  型号/脚号本身另按保留分隔符的标识符边界核对：物理 1 不匹配 11，型号 MPN 不匹配 MPN-42。
  此边界须在实际原页的引用所在位置成立；调用者截短 quote 不可从 11 或 MPN-42 内取出
  所需子串，原页其他位置出现正确 token 也不支持错误引用位置。
  文档可覆盖型号 family，但 identity_quote 必须包含本接收器精确变体；
  不因同型号其他器件/章节出现一个词就自动认定当前角色适用。
- `citation`：该供入路径与身份声明的受控出处；监控 `required/criterion/citation` 仍逐轨逐状态独立声明。

全物理脚快照键是各真实 `ref.pin`；每脚保留 `pin2net/pinname/native_pintype/declared_native_pintype/
pintype/declared_pintype/declared_pinname/no_connect`。脚集合、互反归网、原生与声明必须完整一致。
仅本角色允许未选供入的 passive 触点带真实 NC marker：它须位于独占 NC 伪网且全声明一致。
选中的供入触点不得 NC、地、伪网或 active；实体电源网的 NC、不完整或冲突声明不成立。
同一外供连接器的多个并联供电触点不当作独立多源；另一有受控外供状态声明的连接器/独立来源
或原生输出源经当前已贴非零电阻、正向二极管及供入链可达目标域也拒绝本单来源约定，
不局限于源触点直接位于供入/目标网；装配状态及源带电状态逐一生效。
额外 MOS/BJT 的 S/D（E/C）及多接点开关可能导通的 bypass 也拒绝，未知控制不等于关断。
gate/base、继电器线圈、普通 IC 信号脚不当作导通端；未解析的多端 passive 器件跨域可能通路
保守拒绝资格，待审查者补核，工具不模拟其控制或电气性能。不从连接器的存在推断外部带电；未声明为
外供的输出接口和正常目标轨负载分支不当作额外供入路径，本资格也不证明它们的反灌安全。

文件哈希、型号/脚位原文和快照核对只证明资料与原生身份绑定；原厂语义、变体、引用所在表/图的
适用范围及本轮受控监控要求仍由专家逐项读核，任意字段字符串或引用匹配不能替代此步。
资格成立时 `source_path` 保留原非零值、实际 receiver `power_in` 与来源 SHA，明确
`electrical_equivalence=false/performance_guarantee=false`；原 `observation_gaps` 留档。
清单上下文额外保存实际 `power_sources` 以便重建与过期拒绝，不改变旧角色上下文。
这仅解除来源身份及明确 `required=false` 的书面监控要求对应缺口，PWR-T04 仍等待审查者核验；
`required=true` 无实际监控、其他轨/状态、调节与 PG 等独立缺口仍保留，绝不自动形成电气 PASS。

### 高速差分电平 `diff_levels`

维护范围：按网名成对（`_P/_N`、`_DP/_DN`、`_DP/_DM`、`P/N`、`+/-`）且**两条腿上出现同一个
器件**识别差分对，登记耦合方式、串联耦合电容、端接与偏置、方向。交流耦合的链路按电容两侧
各成一对登记，不把两侧短接成一个对象。

- 电平标准来自 intent 声明（按对象 id 或任一条腿网名落位）或名称/型号线索；只有声明依据能让
  计划项 `APPLICABLE`，名称线索一律 `UNDETERMINED` 并保留 `level-standard:*` 缺口。
- 方向按引脚类型判定；两侧都未知时记 `pair-direction:*` 缺口，相关自动扫描规则不触发。

自动扫描：`SIG-A01` 仅对 LVPECL/PECL 类电流型电平成立——交流耦合且发送侧无到地/到轨直流通路
（声明依据=FINDING，名称线索=CANDIDATE）；`SIG-A02` 交流耦合接收侧既无端接也无偏置（CANDIDATE）。

证据计算 `SIG-E02`（`diff_level`）：直流耦合用发送端共模、交流耦合用偏置后共模，须落在接收端共模
范围内；发送摆幅须落在接收端差分输入范围内。PASS 不覆盖抖动、低频截止、阻抗与回流。

计划项：电平兼容（SIG-E02）、端接与偏置（SIG-T03）。

### 光耦 `optocoupler`

维护范围：识别光耦器件与其 LED 回路（限流电阻、驱动源）和输出侧（集电极网、上拉电阻、发射极
参考）。引脚角色缺失时只登记 `pin-roles:REF` 缺口。隔离耐压、爬电距离与安规等级不在本检查器
定判，走计划项。

自动扫描：`PRO-A03` LED 两条腿上都没有串联电阻且未声明恒流驱动（intent 中 `drive: constant-current`
并给出处才可免除）；`PRO-A04` 集电极网上无到电源轨的上拉（CANDIDATE）。

接收端内部上拉可在 `intent.optocouplers.optocouplers[]` 的 `internal_pullup` 记录：
`{"node":"U2.1","resistance_ohm":{"min":17000,"max":23000},"bias_v":{"min":3,"max":3.6},"states":["run"],"citation":"准确料号手册页码、引脚、启用条件"}`。
以上数值仅为合成格式示例。必须落在已贴接收 IC 的实际集电极同网脚，并适用于当前状态；错误引脚、未贴装、
缺出处或无效范围均不能消除候选。只消除“没找到上拉”的候选，内部上拉、电压、并联负载仍纳入 PRO-E01 的最坏负载计算；
`bias_v` 可省略：已证有内部上拉时不因尚缺偏置电压而继续报缺外部电阻；偏置电压缺口留给传输能力计算。
掉电、高阻及动态 CTR 不自动通过。该模型随 intent/装配/网表摘要进入库存绑定。

证据计算 `PRO-E01`（`opto_ctr`）：
I<sub>F,min</sub> = (V<sub>drive,min</sub> − V<sub>F,max</sub> − V<sub>drop,max</sub>)/R<sub>LED,max</sub>，
I<sub>C,可用</sub> = I<sub>F,min</sub>·CTR<sub>min</sub>·寿命衰减系数，
需满足 I<sub>C,可用</sub> ≥ (V<sub>pullup,max</sub> − V<sub>OL,要求</sub>)/R<sub>pullup,min</sub>，
同时 I<sub>F,max</sub> 不超额定。寿命衰减系数必须来自项目规定，缺规定即 INSUFFICIENT。
PASS 不覆盖开关速度、温度角与隔离耐压。

计划项：传输能力（PRO-E01）、隔离归属与耐压（PRO-D01）。

## 条件性故障能量工具

以下各函数都可在命令行调用：`python3 scripts/calc.py <模块.函数> '<JSON 关键字参数>'`（参数也可写 `@文件` 或 `-`），
`--list` 列出可用计算。输出原样回显输入并给出结果，便于贴入本项证据；缺参数、量纲越界或阶段用错时退出码 2，不补默认值。

`fault_energy.packet_bound()` 与 `capacitor_energy_window()` 用于已限定起点的反激停能分析，
输出能量、电压和允许事件数；所有输出标记为 `CONDITIONAL_ON_CALLER_BOUNDS`，不生成电气结论。
输入的储能单列，时间为零也不自动抹掉已有磁能。使用范围与证据责任见
[故障停能与器件耐受的同一时间轴](evidence-proportionality.md#故障停能与器件耐受的同一时间轴)。

### 条件 boost 开关损耗

`scripts/boost_switch_loss.py` 提供 `boost_cycle` 与 `conditional_losses`：按输入平均电流、母线、L 和死区联解三角周期的峰流/频率/RMS，再分列导通、线性重叠和残余 Coss 能量。调用者须核实际控制模式、脉宽、限流和输入适用性；工具不生成 SOA、严重度或通过结论。见[实际栅压与关联损耗](evidence-proportionality.md#功率开关实际栅压关联损耗和-soa)。

### 反激停能后的电容电压与整流管阶段

`scripts/flyback_stop.py` 的 `post_stop_capacitor_bound` 按已停能时的电容电压、有效容量和可达输出的全部剩余能量求条件边界；`primary_on_sr_platform` 只接受同一初级导通事件的输入，拒绝用于停能后的状态。未知值不按0处理，两者都不自动生成实际尖峰或审查结论。见[假设与故障证据门槛](evidence-proportionality.md#假设上界与实际故障的证据门槛)。

### 模型角点与适用区间

`scripts/model_bounds.py` 用来复算设计脚本里容易写反的模型，不判通过：`ntc_resistance_bounds` 对 R25 与 B 的四个公差角逐一计算，
给出 R(T) 最小/最大值及所用角点（25°C 以上最小阻值是 R25min+Bmax），超出 B 值拟合区间或额定温区只标记、不外推；
`cc_discharge_with_tail` 把恒流放电在合规交界 I×(串阻+尾段电阻) 处切成恒流段与 RC 尾段，尾段电阻须取自器件 I-V 资料。
DOC-Q01 重放计算约定只说明格式与输入可追溯，**约定有效不等于模型正确**：温度单调方向、公差角点和分段模型的适用区间要另行复算。

`model_bounds.crm_boost_capacitor_ripple` 核理想 CrM Boost：输入有效值 `input_rms_v`、恒定母线 `bus_v`、
功率 `power_w`，以及原厂给出的高频相对两倍工频纹波额定系数 `hf_ripple_factor`（默认 1，不给高频增益）。
输出总电容 RMS、两倍工频/开关分量和折算 RMS。二极管导通比例为瞬时输入/母线，不能用 MOS 导通比例；
按控制器的 follower/稳压/限流/跳周期实际模式选模型，输入峰值高于母线时拒算。
该模型不包含母线纹波、损耗、跳周期和负载动态；其 MATCH 不证明这些条件已成立。

功率开关扫描识别低边 Boost 的正向主整流二极管及输出轨/储能回路后，不再报“无吸收/钳位”。
主整流路径与 RC/RCD 分开记录；DRV-C02/DRV-D01 的寄生尖峰、耐压和安全工作区检查照常保留。

### 常用电路的最坏角点与设计数值复算

`scripts/circuit_bounds.py` 覆盖各类板子都有的计算：`divider_bounds`（普通/反馈分压窗口及上臂功耗）、`rc_crossing_time`
（RC 节点跨阈值窗口的最短/最长时间）、`linear_regulator_thermal`（线性稳压功耗与结温）、`logic_level_margins`
（VIH 按电源比例给出时取接收端电源最大值，VIL 取最小值）、`capacitor_ripple_capability`（按手册频率/温度系数表取
较低的相邻系数、表外不外推）、`resistor_power`、`series_resistor_current`（LED/光耦串阻电流）。每项输出注明取了哪个角点。

`scripts/calc_claims.py` 把设计文档里的数值写成 claim 逐条复算：每条给 `id/source/locator/calculation/inputs/claimed`
与可选 `rel_tol`（默认 1%），输出 MATCH / MISMATCH / NOT_COMPUTED / ERROR 及相对差，可直接存为证据。
MISMATCH 只说明在 SR 的模型下所称数值不能由所称输入推出，确认原文和模型适用后才记文档错误。

### 厂家参数引用核对

`python3 scripts/audit_parameter_claims.py parameter-claims.json --json parameter-audit.json`
读取 list，每项含 `id`、`claimed`、`reference`。两侧各有 `identity/parameter/conditions/basis/unit/value/source/locator`，
reference 另给原厂文件 `sha256`；source 是本地文件路径，locator 精确到版本、页码和表行。
先独立阅读原厂表格并核温度、H/f、典型/最小/最大口径，再录入 reference，不能从设计报告复制引用值作基准。
`conditions` 为键值对象，字段与单位统一；`basis` 为 `typical/minimum/maximum/engineering_limit`。
工具验证参考文件哈希，在相同材料/料号、参数、试验条件、口径和可换算单位下比较数值；
输出 MATCH/MISMATCH，条件或单位不兼容为 NOT_COMPARABLE，工程限值为 OUT_OF_SCOPE，缺字段/哈希错误为 ERROR。
支持 T/mT、V/mV、A/mA、ohm/kohm，其他单位不猜。工具不自动理解 PDF，也不证明摘录准确或资料是真正原厂。
设计采用较低磁通限值可以合理，但不能把该设计限值冒充特定温度下的厂家饱和磁通。

### 齐纳门限与锁定保持计算

`scripts/zener_fault.py`只接受调用者已建立适用性的数值界限：`trip_drive`联解内部吸流及充电余量，`no_trip_budget`求正常时可容许的外部注入，`hold_charge`核供电缺口期间的电荷余量。无默认尖峰、温度、延迟或电容公差；负余量不等于实际故障已经发生，须复核输入是否是可达轨迹或仅充分条件。

## 脚本分类

新脚本先归入下表；只有入口写进 SKILL.md 的执行流程。

| 类别 | 脚本 |
|---|---|
| 入口：执行流程里按顺序调用 | `parse_kicad.py`、`parse_netlist.py`、`lint.py`（网表扫描和证据扫描，同时生成计划）、`audit_datasheets.py`、`gap_inventory.py`、`calc_claims.py`、`derive_rows.py`（功能判定写完后派生已绑定的行）、`validate_review.py`、`render_report.py`、`pack_review.py`、`diff_netlists.py`；维护时 `catalog.py --write-doc` |
| 专用工具：特定情形手动调用 | `compare_reviews.py`（两份同板记录先按检查项标识严格配对，报配对率、已答比例、一致率、通过对失败和严重分歧；按电路对齐的结果只作建议配对，`--alias` 加入经核实的别名）、`plan_review.py`（单独重建计划，日常由 `lint.py` 代办）、`calc.py`、`simulate_rc.py`、`solve_dividers.py`（仅探索）、`decoupling.py`、`i2c_topology.py`、`datasheet_facts.py`、`electrical_contract.py`、`reviewed_declarations.py`、`audit_document_summaries.py`、`audit_parameter_claims.py`、`execution_audit.py`（可选自检）、`install_kicad_cli.py` |
| 库：只被导入 | `results_model.py`、计划生成的各层（`plan_circuits.py`、`plan_system.py`、`plan_board.py`）、`interfaces.py`、`row_owner.py`、`review_functions.py`（功能判定校验 F1–F12）、`review_engine.py`、`skill_identity.py`、`board_intent.py`、`board_scans.py`、`page_inventory.py`、`datasheet_kinds.py`、`design_preflight.py`、`review_quality.py`、`review_stage_scope.py`、`review_summary.py`、`review_workflow.py`、`revision_impact.py`、`requirement_clarifications.py`、`task_scope.py`、`validate_remediation.py`、`asg_summary_adapter.py`、计算模块（`circuit_bounds.py`、`model_bounds.py`、`boost_switch_loss.py`、`flyback_stop.py`、`fault_energy.py`、`zener_fault.py`）、`checkers/` |

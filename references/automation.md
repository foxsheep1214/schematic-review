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
| 冷跑 | `db.json`，可选 `--intent`、`--log` | 全部 A 规则；REQ-A01 需要意图中的 `expect`；DOC-A01/DOC-A02 需要导出日志，缺日志时二者列入“本趟未执行” |
| 热跑 | 冷跑输入 + `evidence.json` + `datasheet-audit.json` | 全部 A 规则 + 已提供证据的 E 规则 |
| 改版比对 | 旧/新 `db.json`、旧计划、历史意见断言 | REQ-H01（`diff_netlists.py`）与改版影响清单 |

**输出分三类**：`FINDING` 是疑似缺陷，逐条排除；`CANDIDATE` 是待资料取证定夺的优先级清单，直接
决定先读哪几份 datasheet；`INFO` 是提示，不计入疑点，但准出前仍要核实（如 NET-A04 判为工具伪网络的
NC 网）。同一条规则可同时产出多类，例如 PRO-A02 按型号或轨名推断的电压只作候选。
E 规则的每条结果另记 `check_results`（PASS/FAIL/INSUFFICIENT）与 `passes`。

**未执行不等于通过**：`lint.py` 每次在末尾列出本次没执行的规则及原因（缺 `--intent`、未提供证据）。
扫出 0 条与根本没扫，输出必须能区分。

**命名检出不等于功能适用**：名称候选先确认实际角色/模式，再展开功能包成员；
已有资料尚未阅读或计算时列审查待完成，补证尺度见 [最小充分证据](evidence-proportionality.md)。

**未检出特征不等于不适用**：网表检测不到 DDR/RF 等关键字时，对应功能包列入 REQ-Q08 待确认；
只有设计意图给出可引用的不适用依据，功能包才标 `NOT_APPLICABLE` 并最终写 NA。适用但缺材料写
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
这份清单错了会连锁影响功能包的判定，必须留痕、可复核。

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

### 物料与引脚扫描（DEV-A01～DEV-A03、NET-A07、DOC-A04）

`scripts/board_scans.py` 只用网表、BOM 值字段和引脚名/类型做确定性判别，不读 PDF、不猜降额：

| 规则 | 判别依据 | 不判什么 |
|---|---|---|
| DEV-A01 | BOM 值里写明的耐压（`10uF/16V`）低于按网名推断的电压 | 降额比例、纹波与温度（DEV-C01/DEV-C02）；值里没写耐压就不报 |
| DEV-A02 | `+`/`-` 脚名判别的极性电容：+ 接已知地、- 接命名轨 | 无极性脚名的器件（转图面目检 DOC-V01）；二极管方向按所在电路另判 |
| DEV-A03 | LED 两脚直接跨命名轨与已知地 | 恒流驱动、PWM 驱动与亮度（需资料或声明证据） |
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

### 共用契约

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
- `kind`：bjt/mosfet/diode/zener/tvs/opto 等，与检查器的器件类别一致。
- `page`：手册页码，从 1 开始。
- `quote`：该页上写明器件类型的原文，例如 BCX56-16TX 写 `{"kind":"bjt","page":1,"quote":"80 V, 1 A NPN power bipolar transistors"}`。

第二步，`audit_datasheets.py --intent intent.json` 读取 datasheet 解析表绑定给该位号的那份 PDF，用 pdftotext 抽取该页文本。比较时只保留字母和数字（PDF 常丢空格），逐条核验三点：
- 原文确实在该页上；
- 原文本身写明了所声明的类型，例如 NPN/bipolar、MOSFET/N-channel、Zener、TVS/ESD protection、rectifier/diode/Schottky；
- 原文没有同时指向别的类型，例如把 “ESD Protection Diode” 声明为普通二极管，判为 QUOTE_CONFLICT。

核验结果写入审计的 `device_kinds` 段：
- 状态为 VERIFIED / QUOTE_NOT_FOUND / QUOTE_LACKS_TYPE / QUOTE_CONFLICT / NO_DOCUMENT / NO_TEXT。
- 通过时附手册 SHA-256。
- 未声明的分立半导体标 UNDECLARED，附首页候选类型和所在行，只作提示。

只有 VERIFIED 的声明会进入分析（basis `datasheet`），并随清单上下文保存为 `device_kinds_verified`。该字段由工具生成，intent 中手写会被拒绝。未核验、核验失败或抽取不到文本时，一律按缺口处理，不会因为抽取出错得出结论。

型号/符号库关键字和符号引脚名（B/C/E、G/D/S）只作交叉核对，与手册矛盾时记为未知并形成缺口，因为这说明可能选错了符号或填错了型号。没有核验过的声明时，才按以下顺序退回启发式：
1. 关键字（basis `part-keyword`）；
2. 引脚名（basis `pin-names`）；
3. 位号前缀（basis `refdes-prefix`）。

依据为后两种时不能作为结论：
- 功率开关登记 `datasheet-kind:<ref>` 缺口，在补上并重生成计划之前不得判 PASS；
- Q/D/ZD/TVS 位号的 DEV-D02 登记缺口，缺口文字带审计状态和候选类型。

工具不从 PDF 抽数值参数，数值仍按 datasheet-facts 的人工核对流程处理。

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
摘要/缺口与过期绑定。人工补查项必须使用独立对象，不得复用生成项的对象。摘要只绑定被审
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
审查跳线供侧路径或 ADS1x15 正向示例时，参照[条件边界判例](../evals/scenarios/adc-jumper-boundary-cases.md)，
其中软件判例需人工原件证据，不能当成工具已自动检出的缺陷。
`components.<ref>.links` 可用于有原件配对出处的电阻阵列或多脚跳线，逐对声明同一位号的两个物理脚，
覆盖该位号全部物理脚；不从脚数或位号推断内部连接。电阻阵列限各支路具有同一已核名义阻值，
沿用该器件值字段逐支路保留有限阻值、装配状态和路径；混合值或未知内部结构不能用此模型冒充已知。
例如四个隔离电阻的声明是 `[["R3.1","R3.8"],["R3.2","R3.7"],["R3.3","R3.6"],["R3.4","R3.5"]]`，
kind 仍为 resistor；共端阵列须由原件证明共端，不能把所有焊盘短接。每条上拉按其实际信号网归属，
经有限串阻相连的不同节点仍保留各自路径。此声明不扩大 SIG-E01 直接等效计算，不产生电气 PASS。
连接器后的外部上拉一律未知，需取得模块/线缆网表或另留专家证据。追踪用去重队列处理环路；
每状态最多 1024 个候选网络，达上限记录缺口及 `unvisited_seed_nets/unvisited_frontier_nets`。
`segments` 是连接分组，不证明 0Ω/跳线无压降或无限带宽。

计划：每状态、每连接区域新增 1 项连接覆盖检查（SIG-T02），并逐区域展开 I²C 功能包的电气判据（SIG-C01
灌电流/上升时间、SIG-C07 电平与驱动、SIG-C08 掉电与跨域注入、SIG-D01 地址/复用/装配状态），
不再按功能包重复生成一套。有限串阻各段保留节点做关联分析，有源器件两侧另查传输条件。
不能由"有一只上拉"生成 PASS。本清单与 SIG-E01 的直接连接/直接并联计算并存，不扩大后者模型，
也不自动把清单或 state population 注入证据计算；不同装配变体需各自的 db 与绑定该 db/状态的 evidence。

### 去耦覆盖（`decoupling`）

维护范围：逐器件、物理电源脚、直接供电/返回网络、装配状态与电容清单。不是 PDN 求解器，
也不判定去耦是否合格。

不传 intent 时按物理脚名称/类型发现候选，并纳入符号声明但未连的脚；未核器件另列
`unverified_device_refs`，不能因没有常见 VDD/VCC 名称便判不适用。官方脚表中网表完全不存在的
电源脚也会生成候选，不能只检查网表实有脚。
两端器件（二极管/齐纳/TVS/LED、热敏/压敏电阻、保险丝等）不需要供电，也没有供电/返回脚对可去耦，
不论符号库或脚名，都列入 `two_terminal_no_supply_refs` 而不产生 `unverified-device-pinout` 缺口；它们按极性
与方向设计，由极性、连接追踪和图面目检规则核对。三脚及以上器件（含双二极管、桥堆）仍按未核器件处理。

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
    "schema_version": 2,
    "components": {"C1": {"kind": "capacitor", "citation": "BOM/符号确认 C1 为两脚电容"}},
    "groups": [{"id": "U1-VDD", "ref": "U1", "supply_nodes": ["U1.1"], "return_nodes": ["U1.2"],
                "citation": "准确器件电源分组与返回节点要求 Rev.A 第 8 页",
                "requirements": [{"id": "VDD-CONNECTION", "kind": "connection",
                                  "criterion": "填写本组实际适用的电容接法条款，不用通用每脚一颗规则",
                                  "citation": "官方适用条款版本/页码/表号"}]}]
  }
}
```

- `intent.devices`：准确 MPN/封装、身份解释、完整官方物理脚表及出处。脚表取手册引脚定义的编号或名称；手册只用名称标注时
  名称即脚号（与符号脚号一致），不另要焊盘编号图。`pins` 含全部物理脚，角色为
  `power/return/nc/other`，脚号是字符串，支持 BGA/EP。`pinout_complete=false` 保持缺口。这是有出处的
  人工声明，脚本不读 PDF 验证真实性，也不因字段齐全自动判通过。器件类型另写在 `intent.device_kinds`，
  由手册审计核验原文，见上文“器件类型以原厂手册为准，由工具核验原文”。声明后计划项 DEV-D02 附双向差集、
  DEV-D05 附未接网脚与"标 nc 却接了网"的脚，仍由审查者逐脚定判。
- 官方脚表与符号/网表脚表做双向差集，各自记录多出的脚（`official_only_nodes/symbol_only_nodes` 保留完整差集）；去耦缺口只对电源/地角色的差异脚计入，其他功能脚的差异由 DEV-D02 逐脚处置。官方 power 脚未入 group 时自动列候选。
  不得为消除缺口把缺失电源脚改成 `other`。
- `groups`：按器件具体条款划分，不要求每个电源脚单独一颗电容。节点必须属于该器件对应官方角色，
  供电脚不能重复分组；每组只支持一个直接供电网和一个明确返回网。跨网分组不合并，保持缺口。
  飞跨/bootstrap/补偿电容按专用条款另审，不从"连到电容"推断属于本组。
- `components`：支持 `capacitor/resistor/ferrite/inductor/jumper/switch/other`，都要有出处。
  C/R/L/FB/JP 前缀仅为候选类型；计入确认容量前需核类型与装配。`other` 是有证据的类别排除，
  不是规避官方电源脚审查的通用开关。
- `requirements`：唯一 `id`、`kind`（`connection/capacitance/rating`）、`criterion`、`citation`，
  每条单独入计划；缺某类时生成判据未补齐的检查项，不默认 NA。数组对声明的全部 states 适用，状态相关的
  限值必须在条款中写清条件。

| 字段 | 含义 |
|---|---|
| `groups[].capacitors` | 两端直接匹配本组供电/返回网络的电容，含不贴/未知候选 |
| `fitted_capacitors/fitted_count` | 类型、两脚连接与本状态贴装均确认的唯一位号/数量 |
| `known_nominal_subtotal_f` | 已贴电容中可解析标称值的已知小计，可为部分数据 |
| `nominal_total_f` | 仅当连接/覆盖/装配及容量均无缺口时给出，否则 null；不是有效容量 |
| `rejected_capacitors` | 接到供电侧但不匹配本组两端连接的电容 |
| `boundaries` | 供电网边缘的电阻/磁珠/电感/跳线/开关；始终 `crossed=false` |
| `gaps/capacitance_gaps` | 身份/脚表/连接/装配缺口与容量解析缺口分别记录 |

所有串联元件均不跨越，包括 0Ω 和闭合跳线；上游储能电容不计入下游本段。不同地网不因名字相近
而合并。同网共享电容不是每颗 IC 本地去耦充分的证据；各组容量不能相加成整板总量。实际距离、
回路、ESL/PDN/布局由 PCB 阶段验证。

标称值只解析有明确单位的首项（100nF、4.7u/10%/16V、4n7、1e-6F），不猜 104 等裸编码；无法解析的
已贴电容保留数量与缺口，不当作 0，不猜耐压/介质，不自动估算 ESR 或降容系数。

计划：清单完整性项（PWR-D01）+ 逐状态逐组连接覆盖项（PWR-T03），随后分开审查接法（PWR-D02）、
数量/容量（PWR-C09）与额定值（PWR-C10）；`requirements` 的三类 `kind` 依次对应这三条规则。电气行的
`required_material_refs` 列出目标器件与本组已确认贴装的电容，供资料取证时按需
`audit_datasheets.py --require-ref C1`；按实际判据绑定受控电容规格，依赖具体偏压/ESR/寿命特性时核准确订货码，不能用一般
`datasheets.available` 代替适用参数。接法行独立形成 PCB HANDOFF。容量缺口不自动否定另一个
已证实的窄连接结论。标准无源符号类别不再重复索取 components 声明；power_in 只生成候选，
HV 启动/检测或端口储能等角色须按实际器件条款确认，不能由该类型强制本地去耦。

### 感性负载续流与钳位（`inductive_load`）

维护范围：识别继电器线圈、由开关驱动的电感/绕组、经连接器外接的感性负载，登记每个装配状态下
的钳位路径。只回答"有没有、接法对不对、缺什么证据"；额定值是否足够由 DRV-C01 按器件资料判定。

识别与排除：

- 线圈/绕组两端分别为开关节点与电源轨时成立；开关可以是分立 MOSFET/BJT（按引脚角色）或驱动
  芯片输出脚。
- 开关节点上出现 `SW/LX/PH/VSW/BOOT/BST` 类引脚名时判为开关电源储能电感，不属于本检查器。
- 网名含 `MOTOR/SOLENOID/VALVE/COIL/RELAY/PUMP/BRAKE/FAN/ACTUATOR` 且经连接器外接的负载只作
  `name-hint` 候选，计划项为 `UNDETERMINED`，不产生自动扫描发现。
- 钳位识别：负载两端的续流二极管（按阳极/阴极角色判方向）、开关两端的 TVS/齐纳、跨负载或跨开关
  的 RC，以及驱动芯片 `COM/CLAMP/VS` 类引脚接电源轨形成的"集成钳位候选"（需资料证据）。
  引脚角色缺失时方向记 `unknown` 并形成缺口，不推定方向。

```json
{
  "inductive_loads": {
    "schema_version": 1,
    "db_sha256": "填写当前 db_fingerprint(db) 的 64 位哈希",
    "states": [{"id": "run", "citation": "装配 BOM Rev.B 选项 A",
                "population": {"K1": true, "D1": true, "Q1": true}}],
    "loads": [{"id": "K1-COIL", "ref": "K1", "kind": "relay",
               "switch_net": "RELAY_DRV", "rail_net": "V24",
               "citation": "继电器线圈参数与驱动方式核对记录"}],
    "exclusions": [{"ref": "L7", "citation": "已另行按变压器条款审查"}]
  }
}
```

自动扫描规则：

| 规则 | 触发 |
|---|---|
| `DRV-A01` | 已识别负载在该状态下没有任何钳位路径（含钳位器件不贴）；驱动器内部钳位需资料证据 |
| `DRV-A02` | 续流二极管方向接反：阴极在开关节点、阳极在电源轨 |

计划项（逐负载、逐状态）：钳位拓扑与方向（DRV-T01，带 PCB HANDOFF：钳位器件靠近负载与开关、
续流回路面积最小）；钳位额定（DRV-C01）——反向耐压不低于电源最高电压，峰值/重复电流不低于线圈关断
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

intent 段 `power_switches`（`switches[]`: `id/ref/role/gate_net/citation`）声明实际角色及出处；
装配共用顶层 assemblies；未声明时按图扫描并保留 `assembly state unverified` 缺口。
带出处的 role 可用 `linear/source_follower/emitter_follower` 明确线性用途：不生成 RDS(on)
开关驱动窗口，改查实际工作点/驱动/额定；感性节点的钳位候选仍保留，按实际拓扑确认。BJT 不生成 MOS 的 DRV-E01；
共用图坐标 gate/drain/source 对应 B/C/E，仅用于追踪。角色未知仍保留证据不足，不按浮地位置猜用途。
`role: "level_shifter"` 用于栅极接低侧轨的双向开漏电平转换管：它不是功率开关，不生成 DRV-E01、DRV-C02、DRV-D01
及 DRV-A03/A04，改按电平转换电路审查，见 [计划与结果台账](plan-and-results.md) 的“电平转换（LEVEL_SHIFT）”与
[WCA 公式](wca-formulas.md#mosfet-双向开漏电平转换)。

自动扫描：`DRV-A03` 栅极既无驱动源也无下拉/上拉（上电与驱动高阻时状态不确定）；
`DRV-A04` 开关节点接感性元件或半桥中点但无吸收/钳位（CANDIDATE）。

证据计算 `DRV-E01`（`gate_drive`）仅适用需要该 RDS(on) 保证的 MOS 开关：最小栅源驱动不低于 RDS(on) 保证条件的 VGS，且驱动窗口不超
栅源绝限；P 沟道按量纲翻转后比较。PASS 不覆盖开关速度、米勒导通、SOA 与热。

计划项：栅源驱动（DRV-E01）、安全工作区与降额（DRV-C02，HANDOFF 给热与版图：结温按实际散热
路径，栅极与换流回路面积最小）、开关节点吸收与驱动器条款（DRV-D01，仅在有开关节点证据时生成，
HANDOFF 给版图）。

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

计划项：阻尼判据（PWR-E03）、滤波元件饱和/压降/衰减需求（PWR-C11，HANDOFF 给版图与 EMC）。

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

计划项：使能来源与 UVLO/时序（RST-T01，HANDOFF 给测试：上电/掉电单调性与台阶需实测）、线性轨的
压差（PWR-E02）、同步变换器的预偏置启动与软启动（PWR-D03，需资料证据）。

### 监控与看门狗 `supervision`

维护范围：识别监控器/看门狗（需同时具备 WDI/SENSE/MR 类引脚与复位类输出脚），登记喂狗输入
状态、被监测网、复位输出的去向与上拉，以及给 IC 供电的电源轨及其监测覆盖。只有复位输入脚的
主控不是监控器。

- 喂狗输入状态：`tied`（直接坐在电源/地上）、`driven`（有其他 IC/连接器脚驱动）、
  `pulled-only`（仅有上/下拉）、`floating`。
- 轨的监测覆盖分 `sense-pin`、`divider`（经电阻到 sense 网）、`supervisor-supply`（仅供电给监控器，
  是否等于被监测需资料证据）与未监测。轨本身按电源树识别（见共用契约），逐条记 `basis`；
  只靠轨名认出的轨另记 `rail-identity` 缺口。

自动扫描：`RST-A05` 喂狗输入悬空或固定电平（CANDIDATE）；`RST-A06` 复位/看门狗输出未到任何复位输入
（网上无其他器件=FINDING，只接到其他脚=CANDIDATE）；`PWR-A06` 在已识别监控器的前提下列出未被
监测的轨（CANDIDATE）。**没有任何监控器时不报 PWR-A06**：全板是否需要监控属需求问题，由计划中的
逐电源域覆盖项（PWR-T04）承接。

证据计算 `RST-E03`（`reset_pulse`）：复位输出最小脉宽不低于目标复位输入要求；`output_type=open_drain`
时还要求该网上存在到电源轨的上拉电阻（由网表核实）。PASS 不覆盖阈值精度、迟滞与喂狗时序。

计划项：复位链逐跳与喂狗策略（RST-T02）、复位脉宽（RST-E03）、逐电源域监控覆盖（PWR-T04，逐状态一项，
未监测的轨写进 `inventory_gaps`）。

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

计划项：电平兼容（SIG-E02）、端接与偏置（SIG-T03，HANDOFF 给版图/SI：差分阻抗、等长、间距、
参考平面连续与端接就近）。

### 光耦 `optocoupler`

维护范围：识别光耦器件与其 LED 回路（限流电阻、驱动源）和输出侧（集电极网、上拉电阻、发射极
参考）。引脚角色缺失时只登记 `pin-roles:REF` 缺口。隔离耐压、爬电距离与安规等级不在本检查器
定判，走计划项与结构/版图 HANDOFF。

自动扫描：`PRO-A03` LED 两条腿上都没有串联电阻且未声明恒流驱动（intent 中 `drive: constant-current`
并给出处才可免除）；`PRO-A04` 集电极网上无到电源轨的上拉（CANDIDATE）。

证据计算 `PRO-E01`（`opto_ctr`）：
I<sub>F,min</sub> = (V<sub>drive,min</sub> − V<sub>F,max</sub> − V<sub>drop,max</sub>)/R<sub>LED,max</sub>，
I<sub>C,可用</sub> = I<sub>F,min</sub>·CTR<sub>min</sub>·寿命衰减系数，
需满足 I<sub>C,可用</sub> ≥ (V<sub>pullup,max</sub> − V<sub>OL,要求</sub>)/R<sub>pullup,min</sub>，
同时 I<sub>F,max</sub> 不超额定。寿命衰减系数必须来自项目规定，缺规定即 INSUFFICIENT。
PASS 不覆盖开关速度、温度角与隔离耐压。

计划项：传输能力（PRO-E01）、隔离归属与耐压（PRO-D01，HANDOFF 给版图与结构）。

# 准则库修订草案：86 块实板暴露的问题（2026-11-02）

> 状态：**草案，未入库**。本文件与同名 JSON 只提议改动；`references/shared/`、HardwareWiki 登记表、`scripts/`、`SKILL.md` 都没有动。入库须用户确认（纲要/准则改动先给草案）。

输入：`~/.cache/sr-boards/_summary/findings-all.json`（86 块板；true_defects 201、criterion_issues 14、misses 224、knowledge_gaps 1143）。基线：准则库 1.6.1（344 条，G01 54 / G02 35 / G03 58 / G04 100 / G05 97）。

校验：把 JSON 补丁套到登记表副本（草稿目录，不碰原件），`guideline_criteria.py build --library-version 1.7.0` 汇编并 `check` 通过：353 条，specs G01 1.5、G02 1.3、G03 1.5、G04 1.2、G05 1.2。

## 一、变更摘要与建议版本

建议库版本 **1.7.0**（新增条目，次版本号进一）。
- 修订 12 条（字段级 39 处，含各条 version 1.0→1.1）：G01-026、G01-029、G01-030、G01-031、G03-005（仅 relations）、G04-010、G04-036、G04-037、G04-039、G04-091、G05-030、G05-031。
- 新增 9 条：G02-036～039、G03-059、G04-101～104。
- 归工具/SR、不改准则的 8 项，见第五节；需要人判的 5 项，见第七节。
- 新增条目里 `basis/confirmed/evidence/placement_note` 只是草案附注，入库时去掉（登记表的 criteria 没有这些字段，出处写在 `source`）。凡 `edition/page` 写“待核”的厂家出处取自实板 findings 引文，入库前要对原件核。

## 二、14 条 criterion_issue 逐条裁决

| # | 板 / 条目 | 引用准则 | 裁决 | 依据与改法 |
|---|---|---|---|---|
| 1 | brainsmoke--usb2_hub F27 | G01-031 | 准则确有问题 | J1–J4 是 Standard-A Source；Type-C R2.5 §4.4.2 p152 原文豁免传统连接器默认供 VBUS 的主机/充电器（已对 PDF 原页核）。改 G01-031 title/applies_when.text/not_applicable/sr_check，限定 Type-C Source/DRP 并写入例外。 |
| 2 | rapidanalysis--xerxes F60 | G03-005 | 准则确有问题（缺条目） | G03-005 只承接手册给 LC/穿越频率式的情形，G03-006～009 是外补偿；AP3441 p9 的 Cff 10–470 pF 窗没有条目承接。G03-005 不改适用条件，新增 G03-059，relations 互指。 |
| 3 | fossasia--pslab-hardware CI-HUMAN-RESULT | G01-001/002 | 准则没问题，归工具 | 结果 schema 只有 VENDOR_DATUM/REVIEW_INCOMPLETE，装不下“作者输入待定”。归 `results_model.py` 与 `results-format.md`。 |
| 4 | hasanberkdasar--bms-can-bus CI-RESULT-CONTRACT | G01-001/002 | 准则没问题，归工具 | 同上；另要允许“官方脚义 + 连接图”证明结构性失败。 |
| 5 | mlab-modules--usbi2c01 F058 | G01-026/029/030 | 准则确有问题 | USB-B、无 CC/PD，却被套上 vSafe5V 5.5 V、100 µF、40 ms/3.67 V。三条都在 applies_when.text/not_applicable 写入连接器与协商前提。 |
| 6 | nabucasa--yellow F164 | G01-031 | 准则确有问题 | J4 是双 Type-A Source（AP2191 控制），没有 CC 附着。改法同第 1 条。 |
| 7 | pionixpublic--cb-eval-board F044 | G04-036/037/039 | 检查器误用（准则顺带补写） | SIG-C17 把泛 ISOLATION 展开到隔离高压输入的磁珠 FB1，属对象展开错误。准则顺带补写：G04-036/037 的 not_applicable 排除模拟隔离放大器、隔离电源、磁性隔离；G04-039 适用面扩到隔离放大器（AMC3311 也有 CMTI 要求）。 |
| 8 | antmicro--scalenode-cm4-baseboard F127 | G01-029 | 准则确有问题 | PD 表 4.7 的 100 µF（cSnkBulkPd）只在协商成功后适用，Type-C 表 4-3 未附着时是 10 µF，sr_check 却只核 100 µF。sr_check 改为分三态，Micro-B 另核。 |
| 9 | pionixpublic--reference-hardware F013 | G01-029/030/031 | 准则确有问题 | J2 是 USB-A、J1 是 Micro-B。三条一并按连接器与状态限定。 |
| 10 | copperpilot--jetson-ai-cam F53 | G05-030～034 | G05-031 准则确有问题；030/032/033/034 检查器误用 | G05-031 的“被保护器件”没说清，按同网取会漏掉 FB1/FB3 后面的 LMQ62440/SiC477。修订 inputs/sr_check：沿实际低阻/滤波路径追到后级，计入路径阻抗、限流和次级钳位，缺事件不捏造。其余四条管 TVS 自身窗口，与后级无关，是 PRO-E02 把整组挂上。 |
| 11 | jasonsbeer--amiga-2000-eatx F080 | —（SIG-D10） | 需要人判 | 没有引用 G 准则。问题在 SR 的 SIG-D10 问句（eMMC CMD 上拉）和共用词表 STORAGE 标题“eMMC/SD”。改标题属共用层；并行 SRAM/EPROM 也还没有准则出处。 |
| 12 | rmingon--chlinknet F082 | G04-091 | 准则确有问题 | tailoring 写的是“面向千兆 PHY”，sr_check 却是通用禁止句；WCH 官方参考图里 CT 共接 3V3 是直接反证。改 title/applies_when.text/sr_check，并在 source 补 WCH 参考图。 |
| 13 | rmingon--chlinknet F083 | G01-026/029/030/031 | 准则确有问题 | Micro-B + CH340C，没有 CC/PD。改法同第 5、6 条；线缆压降、负载预算、反灌照样核。 |
| 14 | tonydefilippis--poepico F49 | G01-026/029/030/031 | 准则确有问题 | Micro-B 直挂 55 µF，不能拿“<100 µF”放行，也不能拿 40 ms 判错。改法同上；G01-029 的 sr_check 补上非附着分支（asg_action 原本就有）。 |

合计：准则确有问题 9 条（USB 七条为同一根因），检查器误用 1 条（cb-eval，另附带补写），G05 一条拆开判（G05-031 改，其余四条检查器误用），工具 2 条（REQ-D03），需要人判 1 条（amiga）。

### 2.1 字段级修订（old→new 全文见 JSON `amend`）

| 条目 | 字段 | 新值要点 | 证据板 |
|---|---|---|---|
| G01-026 | title | USB Type-C/PD 供电输入电压窗按 vSafe5V 并计线缆压降 | mlab-modules--usbi2c01, rmingon--chlinknet, tonydefilippis--poepico |
| G01-026 | applies_when.text | VBUS 取电的 USB Type-C 插座端口（含 PD 协商）；传统 USB 连接器（Standard-A/B、Mini/Micro-B，无 CC/PD）不套本条数值 | mlab-modules--usbi2c01, rmingon--chlinknet, tonydefilippis--poepico |
| G01-026 | not_applicable | USB 只作数据接口、VBUS 不取电时不适用；无 CC/PD 的传统 USB 连接器不套 vSafe5V 数值，源端窗口按 USB 2.0/USB 3.2 规范或所接电源规格另核（Type-C R2.5 §4.4.2 p152：传统 USB 连接器（Standard-A、… | mlab-modules--usbi2c01, antmicro--scalenode-cm4-baseboard, pionixpublic--reference-hardware 等 |
| G01-026 | sr_check | 先定端口连接器类型（Type-C/传统）与是否 PD 协商；Type-C 端口核对输入窗按源端范围减线缆压降计算，下游转换器在最低值下能工作；传统连接器不按本条数值判，记“按 USB 2.0/3.2 另核”，取不到适用规范的记资料不足。 | mlab-modules--usbi2c01, antmicro--scalenode-cm4-baseboard, pionixpublic--reference-hardware 等 |
| G01-029 | title | USB Type-C/PD Sink 的 VBUS 电容按附着与协商状态分档，协商后超过 100 µF 须限流 | antmicro--scalenode-cm4-baseboard, tonydefilippis--poepico |
| G01-029 | applies_when.text | Type-C 插座作 Sink 或 DRP（含 PD）；按未附着、附着后首次显式协商前、PD 协商成功后三态分别核 | antmicro--scalenode-cm4-baseboard, tonydefilippis--poepico, mlab-modules--usbi2c01 |
| G01-029 | not_applicable | 端口不作 Sink 时不适用；无 CC/PD 的传统 USB 连接器（Micro-B、USB-B 等）不套本条数值，入口电容与浪涌按 USB 2.0/USB 3.2 规范另核。 | mlab-modules--usbi2c01, antmicro--scalenode-cm4-baseboard, pionixpublic--reference-hardware 等 |
| G01-029 | sr_check | 先定连接器、角色与状态：Type-C 未 Attached.SNK 时 VBUS 电容不超过 10 µF（Type-C 表 4-3）；附着后首次显式协商前按 PD 表 4.7 的 cSnkBulk；仅 PD 协商成功后按 cSnkBulkPd 不超过 100 µF，超出须有… | antmicro--scalenode-cm4-baseboard, tonydefilippis--poepico, brainsmoke--usb2_hub |
| G01-030 | applies_when.text | Type-C 插座作 Sink 或 DRP 时（断开判定按 Type-C 表 4-3）；传统 USB 设备的 VBUS 检测与 D+/D− 上拉撤除按 USB 2.0 与控制器手册另核 | mlab-modules--usbi2c01, pionixpublic--reference-hardware, rmingon--chlinknet 等 |
| G01-030 | not_applicable | 端口不作 Sink 时不适用；无 CC 的传统 USB 连接器不套 40 ms/3.67 V 数值。 | mlab-modules--usbi2c01, antmicro--scalenode-cm4-baseboard, pionixpublic--reference-hardware 等 |
| G01-031 | title | USB Type-C Source 未连接时 VBUS 不带电，电容不超过表 4-2 | brainsmoke--usb2_hub, nabucasa--yellow, pionixpublic--reference-hardware |
| G01-031 | applies_when.text | Type-C 插座作 Source 或 DRP 时；传统 USB 连接器（Standard-A、Micro-B 等）默认供 VBUS 的主机/充电器端口按 Type-C R2.5 §4.4.2 豁免 | brainsmoke--usb2_hub, nabucasa--yellow, pionixpublic--reference-hardware |
| G01-031 | not_applicable | 端口不作 Source 时不适用；Standard-A、Micro-B 等传统连接器默认供 VBUS 的端口不适用（Type-C R2.5 §4.4.2 p152：传统 USB 连接器（Standard-A、Micro-B 等）默认供 VBUS 的主机/充电器豁免“未附着不… | brainsmoke--usb2_hub, nabucasa--yellow, pionixpublic--reference-hardware 等 |
| G01-031 | sr_check | 先确认端口是 Type-C 插座且作 Source/DRP；核对源端口有 VBUS 开关和放电路径、未附着时不带电，端口电容不超过表 4-2。传统连接器端口不按本条判。关闭条件：比较通过。 | brainsmoke--usb2_hub, nabucasa--yellow, pionixpublic--reference-hardware |
| G03-005 | relations | {"reuses": ["G03-010"], "related": ["G03-003", "G03-004", "G03-059"]} | rapidanalysis--xerxes |
| G04-036 | not_applicable | 模拟隔离放大器、隔离电源模块、以太网等无源磁性隔离不适用本条（其故障输出、失电状态按各自手册另核，不因没有数字默认态而放行）。 | pionixpublic--cb-eval-board |
| G04-037 | not_applicable | 模拟隔离放大器、隔离电源模块、无源磁性隔离不适用（无数据速率指标）。 | pionixpublic--cb-eval-board |
| G04-039 | applies_when.text | 有数字隔离器、隔离放大器或其他带 CMTI 指标的隔离接口时（绝缘等级归 G06） | pionixpublic--cb-eval-board |
| G04-091 | title | 以太网中心抽头不并联（所选 PHY/磁件原厂未许可时） | rmingon--chlinknet |
| G04-091 | applies_when.text | 用分立以太网变压器或集成磁性 RJ45 时；千兆 PHY 无原厂许可时适用；所选 PHY/磁件原厂手册或参考设计明确允许中心抽头共偏置的按原厂 | rmingon--chlinknet |
| G04-091 | sr_check | 按所选 PHY/磁件的原厂手册与参考设计核中心抽头接法：原厂明确允许共偏置的（如 WCH CH32V30x 10/100 内置 PHY 参考图 HR911105A 的 CT 共接 3V3 加 0.1 µF）按原厂关闭；千兆 PHY 无原厂许可而多个中心抽头直接或经扼流圈并联… | rmingon--chlinknet |
| G04-091 | source | [{"document": "Microchip ENT-AN0098 Magnetics Guide（原 Microsemi，面向其 PHY）", "edition": "Rev.2.2", "clause": "§3.5", "page": "6（印刷 4）"}, {"… | rmingon--chlinknet |
| G05-030 | sr_check | 独立复核；多通道 TVS/ESD 阵列逐通道按各自所接节点的最高工作电压核 VRWM；低于判不成立（漏电或误导通）；只比 VBR 的判方法错误。关闭条件：每个通道比较通过。 | antmicro--hdmi-mipi-bridge, brainsmoke--usb2_hub, newell--hv-flyback-converter |
| G05-031 | inputs | ["G07 端口浪涌等级与源阻抗（得到浪涌电流和波形）", "钳位电压（对应电流、波形、温度）或 RDYN", "被保护器件绝对最大值（含瞬态额定）：包括同网器件，以及经磁珠、小电阻、保险等直流低阻或滤波支路能到达的后级器件"] | copperpilot--jetson-ai-cam-copperpilot |
| G05-031 | sr_check | 独立复算（含温度系数）；被保护对象沿同一事件的实际低阻/滤波路径追到后级脚，计入该路径在事件频段的阻抗、限流与次级钳位后比较；多通道阵列逐通道比较；超过判不成立；手册没有该波形数据的只能定界并标估算，不放行损坏判据；G07 未给浪涌等级记资料不足，不捏造事件。关闭条件：比较… | copperpilot--jetson-ai-cam-copperpilot, antmicro--hdmi-mipi-bridge |
| G04-010 | applies_when.circuit_types | ["I2C", "SPI", "UART", "LEVEL_SHIFT", "CAN", "RS485", "USB", "ETHERNET", "CLOCK", "HSSERIAL", "DEBUG", "ISOLATION", "STARTUP"] | mlab-modules--batdatunit01 |
| G04-010 | applies_when.text | 有板间、对外或跨电源域的数字接口时；或控制器 GPIO 直接驱动使能、片选、驱动器输入等关键控制脚时 | mlab-modules--batdatunit01 |

词表只有 `USB` 一类，所以连接器类型与协商前提写在 `applies_when.text`、`not_applicable`、`sr_check`，`circuit_types` 不动（G04-010 例外：加 `STARTUP`，词表内已有）。是否新增 `USB_TYPEC` 类型见第七节。

## 三、201 条真缺陷聚类与准则空白

### 3.1 按 SR 规则

| SR 规则 | 条数 | 板数 | criteria 为空 | 引用的准则（次数） |
|---|---:|---:|---:|---|
| DEV-D04 | 40 | 31 | 39 | G05-030×1, G05-031×1 |
| NET-A07 | 22 | 9 | 21 | G04-010×1 |
| DEV-D05 | 13 | 10 | 13 | — |
| DEV-D01 | 11 | 7 | 11 | — |
| DOC-V02 | 10 | 10 | 10 | — |
| DEV-C01 | 9 | 9 | 0 | G02-027×9, G02-007×8, G02-028×8, G03-037×7, G03-038×7, G03-040×7, G05-022×7 |
| DEV-D02 | 8 | 6 | 7 | G05-087×2, G01-038×1, G01-052×1, G05-054×1, G05-055×1, G04-005×1 |
| DEV-C05 | 7 | 6 | 5 | G02-023×1, G04-003×1, G04-004×1, G04-016×1, G01-026×1, G01-027×1, G01-028×1, G01-029×1, G01-031×1 |
| DOC-Q01 | 7 | 7 | 0 | G02-026×7 |
| PRO-E02 | 6 | 6 | 0 | G05-030×6, G05-031×4, G05-032×4, G05-033×4, G05-034×4 |
| DOC-D01 | 6 | 6 | 6 | — |
| SIG-C05 | 5 | 5 | 1 | G01-029×3, G01-026×2, G01-027×2, G01-028×2, G01-031×2, G04-007×1, G04-009×1 |
| DOC-V01 | 5 | 5 | 5 | — |
| PWR-D02 | 5 | 4 | 3 | G03-003×2 |
| NET-A01 | 5 | 4 | 5 | — |
| PWR-C09 | 4 | 3 | 0 | G03-036×4, G03-003×2 |
| SIG-D07 | 4 | 4 | 1 | G01-030×3 |
| PWR-A02 | 2 | 2 | 2 | — |
| PWR-C15 | 2 | 2 | 1 | G03-005×1, G03-006×1, G03-007×1, G03-008×1, G03-009×1, G03-026×1, G03-044×1, G03-045×1, G03-046×1 |
| PWR-C04 | 2 | 2 | 0 | G03-003×2, G03-004×2 |
| 其余 28 个规则各 1 条 | 28 | — | 12 | 见 JSON 源 |

201 条里 142 条 `criteria` 为空。按缺陷性质重新归类（脚本按规则名加关键词初分，再逐条人工改判，结果见 JSON `add[].evidence.items`）：

| 缺陷类 | 条数 | criteria 为空 | 板数 | 承接 |
|---|---:|---:|---:|---|
| 未用/保留/专用脚处置 | 41 | 40 | 19 | 新 G04-102 |
| 器件身份（值/料号/厂家/资料/封装）冲突 | 39 | 37 | 28 | 新 G02-036 |
| 图面标注（DOC-V01/V02） | 15 | 15 | 14 | 不起草（见第七节） |
| 占位值、未定档 | 14 | 13 | 10 | 新 G02-038 |
| 原理图↔BOM 不一致 | 8 | 8 | 3 | 新 G02-037 |
| 脚表/脚号与官方不符 | 8 | 7 | 6 | 新 G04-101 |
| 其他（已有准则或纯连线错误） | 55 | 7 | 36 | 已有准则；7 条纯连线错误（断线、短接、反接）靠 SR 连通性规则，不需设计准则 |
| 超推荐工作条件 | 7 | 5 | 6 | 新 G02-039 |
| 符号脚电气类型/极性错 | 3 | 3 | 3 | 新 G04-101 |
| 去耦（PWR-D02） | 5 | 3 | 4 | 已有 G03-035，SR 补 BASIS |
| Type-C CC 端接 | 3 | 3 | 1 | 新 G04-104 |
| USB 数据线外围 | 3 | 1 | 3 | 新 G04-103 |

**准则缺失最多的三类**：未用/保留/专用脚处置（40 条为空）、器件身份冲突（37）、图面标注（15，不起草）；第四是占位值（13）。

### 3.2 去重核对（题目列的候选逐个查过）

- 料号↔封装↔手册三者一致：库中无条目（G02-003 只要求“取准确料号的手册值”，不管身份字段本身）→ 新 G02-036。
- 符号脚类型与官方脚表一致：无条目 → 并入新 G04-101（脚集合、脚号、类型一条管，避免拆出一条出处薄弱的“脚类型”）。
- BOM 与原理图一致：G02-026 只绑定分析证据与原理图版本 → 新 G02-037；DOC-Q01 原先挂 G02-026 的 7 条一并改挂。
- 占位值不得进交付：无条目；与 G01-007（TBR 登记）衔接 → 新 G02-038。
- 未用输入脚按手册处置：G04 没有覆盖（G04-010 只管上电/复位时的**输出**状态）→ 新 G04-102；出处 ECSS-E-ST-20C Rev.2 §4.2.4h（PDF p38，已核原页）。
- 多通道 TVS/ESD 阵列逐通道核工作窗：G05-030～032 已管窗口，只缺“逐通道”→ 不新增，修订 G05-030/031 的 sr_check。
- IC 旁路/输出电容按手册最小值：G03-035（去耦齐全）、G03-003/004（输出电容/ESR）已覆盖 → 不新增；PWR-D02 没有 BASIS，交 SR 补映射到 G03-035。
- USB 串阻按 MCU 手册：无条目（SIG-D07 只映射 G01-030 断开检测）→ 新 G04-103。
- 晶体负载/壳脚：CL 归 G04-078～085；壳脚按官方脚表处置归新 G04-101/102 → 不另立；有源振荡器输出负载归新 G02-039。
- 隔离返回路径不得被无源支路跨越：G04-040（1.1 版已含电容、电阻、Y 电容跨接）已覆盖 → 不新增；PRO-D02 漏问 13 条是 SR 没把隔离 DC/DC、AC/DC 模块当隔离对象。
- 另发现：G01-030 写“协议与 CC 逻辑交 G04”，但 G04 里没有 CC 条目 → 新 G04-104（Type-C R2.5 表 4-28 p245，已核原页）。

## 四、新准则草案全文

遵守既有约定：只有关键/特殊器件要料号，常规件按值加规格（G02-036、G02-038 的条文都写明了）。适用条件全部取自 `vocabulary.json` 词表。

### G02-036 器件身份唯一：值、料号、厂家、资料与封装指向同一订货型号

- 性质 `shall`；关闭阶段 `schematic`；适用：`{"board": true, "text": "所有进 BOM 的器件；关键/特殊器件以完整订货料号为身份，常规件（片阻、MLCC 等）以值加规格（容差、耐压/功率、介质、封装）为身份"}`
- 输入：实例的 Value、料号/采购码、厂家、资料链接、封装字段；原厂订货信息（后缀与封装、电压/输出档的对应）
- ASG：每个实例的值、料号、厂家、资料链接与封装字段指向同一订货型号：后缀对应的封装、输出档、温度档与所用手册一致；常规件不强求料号，但值、规格与封装字段互不矛盾（如图面 470 nF/1812/≥250 V 与采购码 100 nF/0805/50 V 不得并存）。证据：身份对照表（实例字段 → 原厂订货信息页）。
- SR：逐实例比对字段与原厂订货信息；两个字段指向不同型号、后缀与封装不对应、资料链接指向别的器件（含同系列不同后缀）的判不成立；只是库缓存来源名不同不报；缺原厂订货页记资料不足。关闭条件：每个关键/特殊器件身份唯一且与所引手册一致，常规件值、规格、封装字段一致。
- 出处：ECSS-Q-HB-30-01A 最坏工况分析，2011-01-14，5.1.1.1、5.1.1.2，p15；TOR-2013-00297 Rev.A 电气设计最坏工况分析指南与标准草案，2013-06-03，3.C，p28–29（14–15）；TI SN74HC164 数据手册（作厂家订货信息示例），SCLS115G，Table 5 订货信息（D=SOIC、N=PDIP、PW=TSSOP），p3；Diodes DFLS1100 数据手册（作厂家订货信息示例），版次待核（abhishek-xi 实板引用），Ordering Information / Mechanical Data（PowerDI123），p1
- 关系：{"related": ["G02-003", "G02-037", "G02-038", "G04-101"]}
- 实板证据：真缺陷 39 条（criteria 为空 37），28 块板；首次出现 **a2r-lab--crazyflie_fpga_deck**。DEV-D04/DEV-D01 等身份冲突 39 条（37 条 criteria 为空，28 块板）；G02-003 要求“准确料号”的手册保证值，但没有一条要求身份字段本身唯一。
- 放置说明：放 G02 是因为它是 G02-003“准确料号”的前提；G09（制造与可测试性）成文后可迁移，编号不复用。
- 板：a2r-lab--crazyflie_fpga_deck, abhishek-xi--isolated-flyback-converter, anthilla--anthc, antmicro--jetson-nano-baseboard, antmicro--rdimm-ddr4-tester, badgineer--mp2-esc, ben5049--switch-v4-hardware, danielmartensson--stm32-plc, fossasia--pslab-hardware, g-pereira--greenmobi-bms, gorkemguven--12v-1a-isolated-flyback-smps, groupgets--kimchi-micro, hirusha785--12v-5a-isolated-flyback-smps-kicad, imike78--home-mini-v1-drop-in-pcb, loredati-svg--tpa3116d2-class-d-amplifier, mlab-modules--batdatunit01, mlab-modules--solarmini01, moelashmawi--flyback-ac-dc-converter, neotron-compute--neotron-pico, newell--hv-flyback-converter, newell--nixie-clock-esp32c3, oresat--oresat-c3-hardware, pionixpublic--reference-hardware, protocentral--protocentral_ads1293, s59mz--kicad-led-drv-pmod, spirit532--studio_mic, teapotlaboratories--feather-rak3172, weirdgyn--driverino-shield

### G02-037 原理图、BOM 与发布图纸同版一致

- 性质 `shall`；关闭阶段 `schematic`；适用：`{"board": true, "text": "交付或审查的原理图、BOM（含装配/采购表）与发布 PDF/README 接口表"}`
- 输入：同一版本的原生原理图、BOM、发布 PDF 与接口说明
- ASG：交付前把 BOM、发布图与原生原理图按位号逐项对齐：位号集合、Value、料号、封装、贴/不贴状态一致；README 或图注里的接口针表与网表一致。证据：对齐报告与版本/哈希。
- SR：按位号做双向差集与字段比对；同一提交内 BOM 与图指定不同器件（如 OPA4991↔OPA1664、STM32G431↔STM32G473）、贴装状态矛盾、BOM 漏列图上贴装件、发布针表与网表错位的判不成立；只有格式差异不报。关闭条件：差集为空或每处差异有书面依据。
- 出处：ECSS-Q-HB-30-01A 最坏工况分析，2011-01-14，4.5，p14；TOR-2013-00297 Rev.A 电气设计最坏工况分析指南与标准草案，2013-06-03，附录 A.5.A.1、A.7，p76；86
- 关系：{"related": ["G02-026", "G02-036"]}
- 实板证据：真缺陷 15 条（criteria 为空 8），10 块板；首次出现 **loudifier--openrefmic**。DEV-D04 图纸/BOM 一致性 8 条（3 块板）criteria 为空；另有 DOC-Q01 7 条引用 G02-026，但 G02-026 只要求分析证据绑定原理图版本，不要求 BOM 与图本身一致。
- 放置说明：标准级出处借用 G02-026 已核条目（证据绑定构型）；制造数据包一致性的专门条款待 G09 成文时补。
- 板：badgineer--mp2-esc, copperpilot--jetson-ai-cam-copperpilot, gyrocopterllc--flatmcu, loudifier--openrefmic, mlab-modules--batdatunit01, mlab-modules--qfhmix01, rmingon--chlinknet, solderedelectronics--gnss-gps-l86-m33-breakout-hardware-design, tonydefilippis--poepico, weirdgyn--driverino-shield

### G02-038 交付的器件值不得为占位值或未定档

- 性质 `shall`；关闭阶段 `schematic`；适用：`{"board": true, "text": "交付或冻结的原理图与 BOM"}`
- 输入：实例 Value 与规格字段；未定值的 TBR 登记（G01）
- ASG：交付图中每个贴装器件给出可采购、可复算的值或料号：不留库默认名（R_Small、C、Crystal_GND24）、通配后缀（BZT52Bxx、BQ769x2、xx）、只写类别（TVS、PMOS、NPN）或缺电压/输出档的系列名；确未定的按 G01 TBR 登记估计值、理由、责任方与关闭条件，并在图上标 TBR。证据：占位值清单为空或全部有 TBR 编号。
- SR：扫描 Value/料号字段的库默认名、通配符、纯类别名与缺档系列名；决定电压、时序或钳位的占位值判不成立，其余判风险；有 TBR 登记的记输入缺口不判缺陷。关闭条件：无未登记占位值。
- 出处：NASA SP-2016-6105 Rev.2 系统工程手册，Rev.2 2016，附录 C.3，p250（印刷 237）；ECSS-Q-HB-30-01A 最坏工况分析，2011-01-14，5.1.1.1、5.1.1.2，p15
- 关系：{"related": ["G01-007", "G02-003", "G02-036"]}
- 实板证据：真缺陷 14 条（criteria 为空 13），10 块板；首次出现 **blkburn--zigbee**。DOC-D01/DEV-D01/ANA-D01/RST-A01 等占位值 14 条（13 条 criteria 为空，10 块板）。
- 放置说明：放 G02：占位值使 G02-003 的参数无从取值；与 G01-007 TBR 机制衔接。
- 板：blkburn--zigbee, g-pereira--greenmobi-bms, hasanberkdasar--bms-can-bus, mlab-modules--solarmini01, moelashmawi--flyback-ac-dc-converter, rmingon--chlinknet, rmingon--rs485-spy-injector, solderedelectronics--breadboard-power-supply-board-hardware-design, solderedelectronics--io-expander-mcp23017-breakout-hardware-design, vadivelvaishnavi--transformer_less_power_supply_kicad_pcb_design_project

### G02-039 器件工作在手册推荐工作条件内

- 性质 `shall`；关闭阶段 `schematic`；适用：`{"device_kinds": ["ic", "crystal"], "text": "集成电路与有源振荡器：供电、输入电平与跃迁时间、外接定时/设定元件、负载、频率、温度等级"}`
- 输入：准确料号手册的推荐工作条件表与外接元件允许范围；实际电路的电压、边沿、负载与外接元件值
- ASG：逐项核器件在推荐工作条件内：标准 CMOS 输入的跃迁率（如 ≤5 ns/V）不被慢 RC 边沿破坏、输入电平/上拉电压不超推荐范围、定时或设定电阻在允许区间、振荡器输出负载不超手册测试负载。证据：推荐条件对照行。
- SR：按手册推荐工作条件表逐项比较；超出且手册不保证功能的判不成立；只超典型值不报；在绝对最大额定内但超推荐条件的不能以“未损坏”放行；缺推荐条件表记资料不足。关闭条件：逐项落在保证条件内。
- 出处：TOR-2013-00297 Rev.A 电气设计最坏工况分析指南与标准草案，2013-06-03，3.C，p28–29（14–15）；TI SN74HC 系列数据手册（标准 CMOS 输入跃迁率，作厂家示例），SCES224S，推荐工作条件 Δt/Δv，p5；TXC 7C 系列振荡器数据手册（输出负载条件，作厂家示例），Rev1.05-a，Electrical Characteristics CL=15 pF，p1
- 关系：{"related": ["G02-003", "G02-004", "G02-023"]}
- 实板证据：真缺陷 7 条（criteria 为空 5），6 块板；首次出现 **antmicro--hdmi-mipi-bridge**。DEV-C05 7 条（5 条 criteria 为空，6 块板）：慢边沿进标准 CMOS、定时电阻越界、I²C 上拉到 5 V、振荡器 47 pF 对 15 pF 负载。
- 放置说明：放 G02：与 G02-003/004“保证限值与测试条件”同属参数保证口径。
- 板：antmicro--hdmi-mipi-bridge, antmicro--jetson-nano-baseboard, gorkemguven--12v-1a-isolated-flyback-smps, pionixpublic--reference-hardware, satya777777--esp32-industrial-io-controller, solderedelectronics--fuel-gauge-bq27441-breakout-hardware-design

### G03-059 内补偿变换器的外部前馈电容与反馈网络在手册给定窗内

- 性质 `method`；关闭阶段 `schematic`；适用：`{"circuit_types": ["POWER_CONVERTER"], "text": "内补偿开关变换器，手册给出外部前馈电容（Cff）或反馈网络的取值窗、推荐值"}`
- 输入：准确料号手册的 Cff/反馈电阻取值窗与推荐例；实际 FB 网络的元件值
- ASG：按手册给定窗选 Cff 与反馈电阻；区分手册的推荐例值、给定范围与保证边界。证据：FB 网络对照行（手册页）。
- SR：按手册核 Cff 与反馈电阻在给定窗内；越出手册给定范围判不成立（如 AP3441 给 10–470 pF 而用 4.7 nF）；只偏离推荐例值、仍在范围内的不报；手册未给窗口且无环路数据的记资料不足，不自动断言不稳定。关闭条件：在手册给定窗内。
- 出处：Diodes AP3441 数据手册（内补偿降压，作厂家示例），DS39754 Rev.3-2，Setting the Output Voltage / Figure 1（前馈电容 10–470 pF），p9（PDF）
- 关系：{"related": ["G03-005", "G03-006"]}
- 实板证据：真缺陷 1 条（criteria 为空 1），1 块板；首次出现 **rapidanalysis--xerxes**。criterion_issue rapidanalysis--xerxes F60 与真缺陷 F34：G03-005 只承接手册给 LC/穿越频率式的情形，G03-006～009 是外补偿；厂家给定 Cff 窗无条目承接。
- 板：rapidanalysis--xerxes

### G04-101 符号脚集合、脚号与电气类型按准确订货封装的官方脚表

- 性质 `shall`；关闭阶段 `schematic`；适用：`{"device_kinds": ["ic", "diode", "tvs", "bridge_rectifier", "crystal"], "text": "有封装变体或自建符号的器件"}`
- 输入：准确订货封装的官方脚表（含 EP、隐藏电源脚、变体专用脚）；符号脚号、脚名与电气类型
- ASG：按准确订货封装（非同系列别的封装）的官方脚表建符号：脚集合双向一致（不缺 VDD2、EP，不多脚）、脚号对应、变体专用脚名正确（如 RESET#/HOLD#）、电气类型与方向同官方（输出不声明为输入，开漏标开漏，二极管极性与脚名一致）。证据：脚表双向差集与类型对照。
- SR：官方脚与符号脚双向差集，加脚号/脚名/类型逐脚比对；脚号错位或缺电源/EP 脚判不成立；只影响电气类型的判风险（会误导 ERC 与驱动推断）；缺准确封装脚表记资料不足。关闭条件：差集为空或每处差异有依据。
- 出处：NXP PCA9517A 数据手册（封装变体脚序不同，作厂家示例），版次待核（hdmi-mipi-bridge 实板引用），Fig.4、Table 3 HWSON8 脚位，p3–4；TI DRV8353R 数据手册（输出/开漏脚类型，作厂家示例），SLVSDY6A，引脚功能表，p8–9
- 关系：{"related": ["G02-036", "G04-102"]}
- 实板证据：真缺陷 11 条（criteria 为空 10），8 块板；首次出现 **antmicro--hdmi-mipi-bridge**。DEV-D02 脚表差集 8 条、自建符号脚类型/极性 3 条（共 11 条，10 条 criteria 为空，8 块板）。
- 板：anthilla--anthc, antmicro--hdmi-mipi-bridge, antmicro--m2-smart-iot-module, blkburn--zigbee, gyrocopterllc--flatmcu, jasonsbeer--amiga-2000-eatx, satya777777--esp32-industrial-io-controller, solderedelectronics--gnss-gps-l86-m33-breakout-hardware-design

### G04-102 未用脚、保留脚与专用脚按手册处置

- 性质 `shall`；关闭阶段 `schematic`；适用：`{"device_kinds": ["ic"], "text": "有未用输入、NC/DNU/RSVD 脚、配置脚、片内稳压旁路脚或模拟专用脚的集成电路"}`
- 输入：官方脚表对每脚（含未用时）的处置要求；网表中该脚的实际连接
- ASG：逐脚按手册处置：未用 CMOS 输入接固定电平或手册允许的上下拉，不悬空；RSVD/DNU 按手册接地或悬空；配置脚、检测脚按所选变体接（固定输出版不接可调分压）；VCAP/REXT/PFIL 等专用脚的外接元件按手册值；电源脚即使功能未用也按手册接（如 FPGA VCCADC 不得接地）。证据：逐脚处置表。
- SR：按官方脚表逐脚核；悬空的 CMOS 输入、按手册必须接地/接电源却悬空或反接、专用脚外接元件偏离手册要求的判不成立；手册允许悬空或片内有保证上下拉的不报；缺脚表记资料不足。关闭条件：每脚处置都有手册依据。
- 出处：ECSS-E-ST-20C Rev.2 Electrical and electronic，2022-04-08，4.2.4 h（未用电路不产生也不受工作噪声影响；航天 shall，默认基线下作方法依据），p38；TI SN74HC595 数据手册（未用输入处置，作厂家示例），SCLS041J，§6.3 注 1；§11，p4、15；TI ADS1299 数据手册（未用 GPIO 与专用脚，作厂家示例），手册版次待核（Wiki raw/Datasheet 现存版），引脚功能表 GPIO1–4；§9.3.2.3，p6、27
- 关系：{"related": ["G03-035", "G04-010", "G04-101"]}
- 实板证据：真缺陷 41 条（criteria 为空 40），19 块板；首次出现 **a2r-lab--crazyflie_fpga_deck**。NET-A07 22、DEV-D05 13 等引脚处置 41 条（40 条 criteria 为空，19 块板）；G04-010 只管上电/复位时的关键输出，没有条目管输入与专用脚。
- 板：a2r-lab--crazyflie_fpga_deck, antmicro--hdmi-mipi-bridge, antmicro--kria-k26-devboard, antmicro--m2-smart-iot-module, antmicro--poe-usb-c-pd-converter, copperpilot--jetson-ai-cam-copperpilot, hasanberkdasar--bms-can-bus, imike78--home-mini-v1-drop-in-pcb, jasonsbeer--amiga-2000-eatx, moelashmawi--flyback-ac-dc-converter, neumi--fastlogic, newell--nixie-clock-esp32c3, prajyotdaphal--home_automation-module, solderedelectronics--fuel-gauge-bq27441-breakout-hardware-design, solderedelectronics--soldered-inkplate-6-motion-hardware-design, sparkfun--sparkfun_gnssdo, theushen--eegfrontier, tonydefilippis--poepico, weirdgyn--driverino-shield

### G04-103 USB 数据线外围按所选控制器手册

- 性质 `shall`；关闭阶段 `schematic`；适用：`{"circuit_types": ["USB"], "text": "USB 控制器/桥接芯片的 D+/D− 串阻、上拉、REXT 与 VBUS 检测脚外围"}`
- 输入：所选控制器手册对串阻、上拉（阻值、上拉电压）、REXT、VBUS 检测脚分压/限流的要求
- ASG：D+/D− 串阻、全速 D+ 上拉、REXT 与 VBUS 检测脚分压按所选控制器手册取值，不照搬别的平台（如 RP2350 要求 27 Ω、STM32F103 全速 D+ 1.5 kΩ 上拉）。证据：外围对照行。
- SR：按手册核阻值与接法；偏离手册明确要求的判不成立；手册只给推荐范围的按范围判；缺手册记资料不足。关闭条件：比较通过。
- 出处：ST STM32F103 数据手册（全速 D+ 上拉，作厂家示例），DS5319 Rev.20，Table 45 注 2，p73（PDF）；Raspberry Pi RP2350 数据手册（USB 串联端接，作厂家示例），版次待核（cellkeeper 实板引用），Table 2 USB DM/DP 27 Ω，p17（PDF）
- 关系：{"related": ["G01-030", "G04-005"]}
- 实板证据：真缺陷 3 条（criteria 为空 1），3 块板；首次出现 **neumi--fastlogic**。SIG-D07 串阻/上拉 2 条与 SIG-C08 CP2102N VBUS 检测脚直连 1 条（3 块板）；SIG-D07 的 BASIS 只映射 G01-030（Type-C 断开检测），与这类缺陷不对题。
- 板：bondus--klippertoolboard, cellkeeper-bms--cellkeeper-hardware, neumi--fastlogic

### G04-104 USB Type-C 端口 CC 按端口角色端接

- 性质 `shall`；关闭阶段 `schematic`；适用：`{"circuit_types": ["USB"], "text": "Type-C 插座；无 CC 控制器、靠电阻声明角色的端口"}`
- 输入：端口角色（Sink/Source/DRP）；CC1、CC2 的端接网络
- ASG：Sink 端口 CC1、CC2 各自独立接 Rd（5.1 kΩ 到 GND，±20% 只作默认、要检测供电能力用 ±10%）；Source 端口各接 Rp；不并接、不悬空。证据：CC 端接对照。
- SR：按角色核 CC1/CC2 端接；Sink 缺 Rd 或两 CC 共用一只电阻判不成立；CC 悬空或只标 NC 判不成立；有 CC/PD 控制器的按其手册。关闭条件：比较通过。
- 出处：USB Type-C Cable and Connector Specification，R2.5 2026-03，表 4-28 Sink CC Termination (Rd)，p245；USB Type-C Cable and Connector Specification，R2.5 2026-03，4.4.2（VBUS 按 USB 2.0/3.2；传统连接器例外），p152
- 关系：{"related": ["G01-029", "G01-030", "G01-031"]}
- 实板证据：真缺陷 3 条（criteria 为空 3），1 块板；首次出现 **rmingon--rs485-spy-injector**。rmingon--rs485-spy-injector SIG-D04/NET-A01 3 条：J4 CC 无 Rd。G01-030 写“协议与 CC 逻辑交 G04”，但 G04 没有 CC 条目。
- 板：rmingon--rs485-spy-injector

## 五、归工具/SR、不改准则

| 项 | 引用 | 裁决 | 去处 | 内容 |
|---|---|---|---|---|
| fossasia--pslab-hardware CI-HUMAN-RESULT REQ-D03 | G01-001, G01-002 | 准则没问题，归工具 | scripts/results_model.py OPEN_KINDS/KIND_CAUSE；references/results-format.md | 结果 schema 只有 VENDOR_DATUM/REVIEW_INCOMPLETE，缺“作者/系统输入待确认”种类与逐对象关闭清单 |
| hasanberkdasar--bms-can-bus CI-RESULT-CONTRACT REQ-D03 | G01-001, G01-002 | 准则没问题，归工具 | scripts/results_model.py；scripts/review_functions.py；references/results-format.md | 同上；另允许以官方脚义+连接图证明结构性失败，无需伪造 shall 句 |
| pionixpublic--cb-eval-board F044 SIG-C17 | G04-036, G04-037, G04-039 | 检查器误用（附带准则补 not_applicable） | scripts/catalog.py SIG-C17 对象展开 | 泛 ISOLATION 展开到隔离高压输入的磁珠 FB1；按数字/模拟/磁性/隔离电源分子判据 |
| copperpilot--jetson-ai-cam F53 PRO-E02（G05-030/032/033/034 部分） | G05-030, G05-032, G05-033, G05-034 | 检查器误用 | scripts/catalog.py PRO-E02 判据 | 这四条是 TVS 自身窗口，与后级耐受无关；“同网最低耐受”是 PRO-E02 的实现口径 |
| jasonsbeer--amiga-2000-eatx F080 SIG-D10 | — | 需要人判（词表） | scripts/catalog.py CIRCUIT_TYPES STORAGE/SIG-D10；references/shared/vocabulary.json STORAGE 标题 | STORAGE 标题“eMMC/SD”与 SR 按用途归类不一致；并行 SRAM/EPROM 子型与问句归 SR |
| PWR-D02 去耦接法（5 条真缺陷，3 条 criteria 为空） | G03-035 | 准则已有，SR 未映射 | scripts/catalog.py BASIS 增 PWR-D02→G03-035 | G03-035“手册要求的电源脚去耦齐全”正对题 |
| SIG-D07 USB 物理层 | G01-030 | SR 映射不全 | scripts/catalog.py BASIS SIG-D07 增 G04-103（新） | 串阻/上拉缺陷被挂到 Type-C 断开检测 |
| DEV-D01/D02/D04/D05、NET-A07、DEV-C05 等无 BASIS | — | 准则入库后 SR 补映射 | scripts/catalog.py BASIS | DEV-D01/D04→G02-036，DOC-Q01 增 G02-037，DOC-D01/D02/ANA-D01→G02-038，DEV-C05→G02-039，DEV-D02→G04-101，DEV-D05/NET-A07/PWR-A02/CLK-D01→G04-102，SIG-D04→G04-104，PWR-C15 增 G03-059 |

## 六、224 条漏问按引用准则

224 条都带准则引用，`proposed_fix.owner` 全是 checker，没有一条是“准则缺失”。一条漏问引用多条准则时每条各计一次，所以下表合计大于 224。下表就是交 SR 的落实清单；其中 6 条准则的漏问会顺带用到本草案的修订（标在“归类”列）。

| 准则 | 漏问条数 | 板数 | 涉及 SR 规则 | 归类 |
|---|---:|---:|---|---|
| G04-010 | 28 | 27 | RST-T04 | 准则存在；另修订 applies_when 加 STARTUP（EN 直驱） |
| G05-019 | 27 | 27 | PRO-C04, PRO-D04/PWR-T05 | 准则存在，SR 没落实 |
| G03-003 | 19 | 18 | PWR-C04 | 准则存在，SR 没落实 |
| G05-030 | 17 | 15 | PRO-E02 | 准则存在 SR 没落实；另修订 sr_check 写明阵列逐通道 |
| G04-054 | 17 | 16 | ANA-C01, ANA-C03 | 准则存在，SR 没落实 |
| G05-031 | 16 | 14 | PRO-E02 | 同上，并修订“被保护器件”含滤波后级 |
| G03-021 | 15 | 14 | PWR-D03 | 准则存在，SR 没落实 |
| G04-009 | 15 | 15 | ANA-C03, SIG-C08 | 准则存在，SR 没落实 |
| G05-032 | 14 | 12 | PRO-E02 | 准则存在，SR 没落实 |
| G04-040 | 14 | 13 | DOC-D01, PRO-D02 | 准则存在，SR 没落实 |
| G04-007 | 13 | 13 | ANA-C03, PRO-D04, SIG-C08 | 准则存在，SR 没落实 |
| G04-005 | 11 | 11 | ANA-C03, SIG-C08 | 准则存在，SR 没落实 |
| G03-004 | 8 | 7 | PWR-C04 | 准则存在，SR 没落实 |
| G03-018 | 7 | 7 | PWR-C06 | 准则存在，SR 没落实 |
| G04-078 | 7 | 5 | CLK-C01, PWR-C04 | 准则存在，SR 没落实 |
| G05-025 | 6 | 6 | PRO-C05 | 准则存在，SR 没落实 |
| G04-079 | 5 | 3 | CLK-C01 | 准则存在，SR 没落实 |
| G04-082 | 5 | 3 | CLK-C01 | 准则存在，SR 没落实 |
| G04-041 | 4 | 4 | ANA-C01 | 准则存在，SR 没落实 |
| G01-029 | 4 | 4 | PWR-C04, PWR-C13, SIG-C05 | 准则存在；随 USB 修订分态 |
| G05-054 | 4 | 4 | PRO-D04, PRO-D04/PWR-T05 | 准则存在，SR 没落实 |
| G05-087 | 4 | 4 | PWR-T05 | 准则存在，SR 没落实 |
| G03-016 | 4 | 4 | DRV-C02 | 准则存在，SR 没落实 |
| G04-018 | 3 | 3 | SIG-C01 | 准则存在，SR 没落实 |
| G01-027 | 3 | 3 | SIG-C05 | 准则存在，SR 没落实 |
| G03-028 | 3 | 3 | PWR-C24 | 准则存在，SR 没落实 |
| G05-040 | 3 | 3 | DRV-C02 | 准则存在，SR 没落实 |
| G03-032 | 3 | 3 | DOC-D01, PWR-C05 | 准则存在，SR 没落实 |
| G03-019 | 2 | 2 | PWR-C06 | 准则存在，SR 没落实 |
| G04-017 | 2 | 2 | SIG-C01 | 准则存在，SR 没落实 |
| G01-026 | 2 | 2 | SIG-C05 | 随 USB 修订 |
| G01-030 | 2 | 2 | SIG-C05, SIG-D07 | 随 USB 修订 |
| G05-022 | 2 | 2 | DEV-C04, PRO-D04 | 准则存在，SR 没落实 |
| G02-027 | 2 | 2 | DEV-A01 / DEV-C01 / DEV-C02, DRV-C01 | 准则存在，SR 没落实 |
| G03-038 | 2 | 2 | PRO-C01 | 准则存在，SR 没落实 |
| G05-041 | 2 | 2 | DRV-C02 | 准则存在，SR 没落实 |
| G04-055 | 2 | 2 | ANA-C02 | 准则存在，SR 没落实 |
| G04-087 | 1 | 1 | SIG-D11 | 准则存在，SR 没落实 |
| G05-057 | 1 | 1 | PWR-C26 | 准则存在，SR 没落实 |
| G05-048 | 1 | 1 | PRO-C01 | 准则存在，SR 没落实 |
| G04-068 | 1 | 1 | PRO-D02 | 准则存在，SR 没落实 |
| G05-036 | 1 | 1 | PRO-C02 | 准则存在，SR 没落实 |
| G02-022 | 1 | 1 | RST-C02 | 准则存在，SR 没落实 |
| G03-001 | 1 | 1 | PWR-C01 | 准则存在，SR 没落实 |
| G03-006 | 1 | 1 | PWR-C15 | 准则存在，SR 没落实 |
| G03-013 | 1 | 1 | PWR-C13 | 准则存在，SR 没落实 |
| G03-025 | 1 | 1 | PWR-T04 | 准则存在，SR 没落实 |
| G04-003 | 1 | 1 | SIG-C07 | 准则存在，SR 没落实 |

漏问里揭示准则措辞问题的只有三处，已并入第二节修订：PRO-E02 阵列逐通道（G05-030/031，17 块板）；RST-T04 中控制器 GPIO 直驱 EN 不在 G04-010 的触发类型里（加 STARTUP）；USB 入口电容按 Micro-B 误判（G01-029）。

## 七、需要人判

- **G01-028 USB Sink 承受 24 V VBUS**：出处 PD 表 4.7 vSprMax，同样只对 PD 端口成立；本轮 14 条未直接点名，建议同批把 applies_when.text/not_applicable 限定为 PD/Type-C，待确认后再写入 amend
- **是否在 vocabulary.json 新增 USB_TYPEC 电路类型**：本草案只用 text/not_applicable/sr_check 限定连接器类型（词表不动）；若要选规则阶段就排除传统 USB，须改共用层词表与 SR/ASG 的类型推断
- **STORAGE 词表标题与范围**：“eMMC/SD”与 SR 按用途归 STORAGE（含并行 SRAM/EPROM）不一致；改标题属共用层词表，且并行存储器尚无准则出处
- **新准则放 G02/G04 还是等 G09 成文**：G02-036～038 本质是制造数据包/构型一致，G09 尚无登记表；草案放 G02 以便本版可用，迁移时编号不复用
- **图面标注类缺陷（DOC-V01/V02 15 条）不起草准则**：属图纸卫生与可读性（ASG 可读性检查、未来 G09），不是电气设计准则；如需入库请指示

## 八、资料待收集清单（知识缺口按器件聚合，前 30）

方法：1143 条知识缺口中，661 条的文字里有能在该板 db.json 找到的位号；跳过一句点名 4 个以上位号的条目（69 条，多为全板泛问），再按位号的 Value 聚合。没有位号的泛句（如“PWR-D02：器件/接口保证资料待补”）不计入。

| # | 型号/值 | 缺口条数 | 板数 | 主要 SR 规则 | 应收集 |
|---:|---|---:|---:|---|---|
| 1 | HERMAPHRODITIC_MOLEX_203456-0003_CUSTOM_JETSON_AGX_THOR_H8MM | 25 | 1 | NET-A07×25 | NVIDIA Jetson AGX Thor 模组针表/载板设计指南（非器件手册） |
| 2 | 74LVC1G17 | 22 | 1 | SIG-C07×12, DEV-D01×10 | 准确料号原厂数据手册（含订货信息、完整脚表、推荐工作条件） |
| 3 | MAX3051EKA | 18 | 1 | SIG-C07×15, RST-E01×1, RST-T04×1 | 准确料号原厂数据手册（含订货信息、完整脚表、推荐工作条件） |
| 4 | TPS27S100ARRKR | 18 | 1 | PWR-C09×9, SIG-C07×9 | 准确料号原厂数据手册（含订货信息、完整脚表、推荐工作条件） |
| 5 | BSS138PW | 16 | 1 | DEV-D01×8, DRV-C02×8 | 准确料号原厂数据手册（含订货信息、完整脚表、推荐工作条件） |
| 6 | USB-MICRO-B_MOLEX_473460001 | 12 | 2 | DEV-D02×3, SIG-C07×3, DEV-E01×2 | 准确料号原厂数据手册（含订货信息、完整脚表、推荐工作条件） |
| 7 | NCP380LSNAJAAT1G | 11 | 1 | SIG-C07×4, DEV-D02×2, RST-C01×2 | 准确料号原厂数据手册（含订货信息、完整脚表、推荐工作条件） |
| 8 | GS2971A | 9 | 1 | SIG-E02×3, SIG-T03×3, PWR-D01×1 | 准确料号原厂数据手册（含订货信息、完整脚表、推荐工作条件） |
| 9 | XMC1404 | 8 | 1 | PRO-E02×7, DEV-D01×1 | 准确料号原厂数据手册（含订货信息、完整脚表、推荐工作条件） |
| 10 | JST_SH_1X4_SM04B-SRSS-TB-LF-SN | 8 | 1 | DEV-D02×2, DEV-E01×2, DEV-D03×2 | 所接 Qwiic/STEMMA 外设约定 |
| 11 | 74LVC1G07QW5-7 | 8 | 1 | DEV-C01×2, DEV-C02×2, DEV-D02×1 | 准确料号原厂数据手册（含订货信息、完整脚表、推荐工作条件） |
| 12 | PESD3V3L1BA | 7 | 1 | PRO-E02×7 | 准确料号原厂数据手册（含订货信息、完整脚表、推荐工作条件） |
| 13 | 1206FUSE-500MA | 7 | 2 | DEV-C01×5, DEV-D04×1, PRO-C08×1 | 准确料号原厂数据手册（含订货信息、完整脚表、推荐工作条件） |
| 14 | MAX2831 | 7 | 1 | NET-A07×7 | 准确料号原厂数据手册（含订货信息、完整脚表、推荐工作条件） |
| 15 | MOLEX-93628-3721 | 7 | 1 | SIG-C19×1, ANA-C03×1, DEV-C01×1 | 所接模块针表 |
| 16 | BUS_M.2_2199230-2 | 6 | 1 | NET-A07×6 | 所插 M.2 模块规格（PCI-SIG M.2） |
| 17 | SMF4L13CA | 6 | 2 | PRO-E02×6 | 准确料号原厂数据手册（含订货信息、完整脚表、推荐工作条件） |
| 18 | USB-C_WE_632723300011 | 6 | 1 | SIG-C07×2, DEV-D02×1, DEV-E01×1 | 准确料号原厂数据手册（含订货信息、完整脚表、推荐工作条件） |
| 19 | TPS7A0518P_SOT23-5 | 6 | 1 | RST-E01×2, RST-T01×2, SIG-C07×2 | 准确料号原厂数据手册（含订货信息、完整脚表、推荐工作条件） |
| 20 | SIC477ED-T1-GE3 | 6 | 1 | DEV-D02×1, PWR-A05×1, PWR-C09×1 | 准确料号原厂数据手册（含订货信息、完整脚表、推荐工作条件） |
| 21 | NRF52840 | 6 | 1 | SIG-C07×5, ANA-C03×1 | 准确料号原厂数据手册（含订货信息、完整脚表、推荐工作条件） |
| 22 | INA333AIDGKR | 6 | 1 | SIG-C07×4, ANA-C03×2 | 准确料号原厂数据手册（含订货信息、完整脚表、推荐工作条件） |
| 23 | AP22804AW5-7 | 6 | 1 | DEV-C01×1, DEV-C02×1, DEV-D01×1 | 准确料号原厂数据手册（含订货信息、完整脚表、推荐工作条件） |
| 24 | 690-008-221-904 | 6 | 1 | DEV-C01×1, DEV-C02×1, DEV-D01×1 | 连接器原厂图 |
| 25 | USB2514_48PIN | 6 | 1 | DEV-C01×1, DEV-C02×1, DEV-D01×1 | 准确料号原厂数据手册（含订货信息、完整脚表、推荐工作条件） |
| 26 | SDINBDG4-8G | 5 | 1 | NET-A01×4, PWR-A01×1 | 准确料号原厂数据手册（含订货信息、完整脚表、推荐工作条件） |
| 27 | IMX8MM | 5 | 1 | NET-A07×3, PRO-E02×2 | 准确料号原厂数据手册（含订货信息、完整脚表、推荐工作条件） |
| 28 | PESD2USB5UV-TR | 5 | 1 | DEV-D01×5 | 准确料号原厂数据手册（含订货信息、完整脚表、推荐工作条件） |
| 29 | 1N4148WS | 5 | 1 | DEV-D02×5 | 准确料号原厂数据手册（含订货信息、完整脚表、推荐工作条件） |
| 30 | BUS_DDR4_SODIMM_CUSTOM_JETSON-NANO-H9.2MM-SOCKET | 5 | 1 | DEV-D02×1, DEV-E01×1, NET-A07×1 | Jetson Nano 模组针表/载板设计指南 |
| + | USB 2.0 / USB 3.2 规范 | — | 8 | SIG-C05 | 标准原文：USB 修订后“另核”的依据 |

这些缺口应进 `datasheets-to-collect`，不进准则：判据已有（脚表一致、推荐条件、钳位窗口等），缺的是该料号的原厂数据。以下几类不是缺资料：
- 载板/模组连接器（Jetson AGX Thor B2B、Jetson Nano SODIMM、M.2、CM4 DF40）缺的是模组针表与载板设计指南，不是连接器手册。
- `1206FUSE-500MA`，以及 `6.2±2%`、`D_TVS`、`TVS`、`NPN-SOT-23-3`、`PMOS`、`NMOS-DUAL` 等纯类别值：属于占位值，归新 G02-038，补料号后才谈得上找手册。
- 前 10 中 9 个只出现在 1 块板（cb-eval、jetson-nano-baseboard、jetson-agx-thor 三块大板集中），跨板重复的只有 Micro-B Molex 473460001、SM04B 等少数。

## 九、入库步骤（确认后）

1. 按 JSON `amend` 改 HardwareWiki 各 `G0x_准则登记.json`（逐字段核 old），`add[].entry` 追加到对应登记表，登记表 version 按 `spec_versions` 进一；把“待核”的出处对原件核完。
2. 同步 G0x 正文 md 的条目章节（本草案未改正文）。
3. `guideline_criteria.py build --library-version 1.7.0`，复制共用层到 ASG/SR 两边，跑全量测试。
4. SR：按第五节补 BASIS；SIG-C05/SIG-D07 带连接器类型实例化；PRO-E02 逐通道；SIG-C17 按隔离子型展开。ASG：设计准则按新条目留证据（身份对照、逐脚处置、BOM 对齐）。

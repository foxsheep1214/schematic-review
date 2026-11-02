# 合并步 2B：原生器件身份、物理脚角色与逐端点计划（2026-11-02）

实现提交为 `3a2d4ec`（身份/标题）、`7eacc80`（脚角色）、`661c632`（逐端点计划/种子）。本次从 `boards-program` 的 `7b2ce7d` 出发，只在 `boards-merge2b` 工作树改动。基线与修改版均从相同固定提交的原生 XML 重解析；共回放 20 块题列板，包含全部七块必选板。下面的冷扫数是非 INFO 的工具发现/候选数，不是真缺陷数；计划条数是专家待问项，不是自动电气结论。

`SKILL.md`、`references/shared/`、`scripts/guideline_criteria.py`、`scripts/stress_check.py` 未改。候选持有/重归代码 `circuit_candidates.py`、`circuit_decisions.py` 未改；`plan_circuits.py` 只改资格与逐物理对象检查，未修改原有成员遍历/持有模型。`lint.py` 只改继电器触点及未用输入政策；`powertree.py` 仅 `_search` 增加限定的供电路径，没有改隔离域或并查集。所有源板、lane 证据只读，没有 push。

## 逐项修法

1. **手册标题与厂商名**：型号、原生值/符号、位号和脚表参与启发式；删除品牌 `Diodes` 的二极管暗示，用完整词匹配类型，只从首面标题或有界 Description 取标题候选，优先按 PDF 文本块位置排除页脚、Features/Applications 与工作描述。
2. **原生接口/机械身份**：easyC（含 `easyC-SMD`）、NOVA programmer header、明确 Conn 符号优先于 K/P 位号；安装孔、孔焊盘、测试点不作为隐含 IC 去耦组；DIP 封装的实际开关不因 J 位号成为外部接口，明确声明的端口分组仍保留。
3. **继电器触点**：在同一继电器内按相同数字后缀核完整 NC/COM/NO 三组且各一条不同网络，支持仅线圈有脚名的符号；没有资料核验的继电器保留定类候选，不全局豁免 `NC1`。
4. **装配与物料身份**：支持 Populate/Population/Fitted/Assembly/Stuffed 等字段与 DNP 值，保留字段/属性出处，遵守 false/yes；原生 `Mfgrpart` 进入型号，存在 MPN 时按 MPN 分手册物料，原始 Value 与所有字段仍保留，不能把两个 `PMOS` 值绑成同一型号。
5. **磁性件/时钟/差分角色**：FB 值二端件按磁珠处理，RF Balun 不套续流线圈，Buck 储能电感不套下游输入 EMI；有源 TCXO 不问无源晶体负载，定类仅因自定义 `Oscillator_SMD` 包名不升为有源器件；差分跨线电容不当串联 AC 耦合，HY931147C 的整流 P$9/P$10 与真实电源 V+/V− 不建数字差分对，仍保留 RD/TD 数据对。
6. **I²C**：I2S_SDA 等音频字样不能起一个 I²C 候选，声明电源轨是上拉拓扑的停止边界，防止不同总线通过 NVCC 合并；显式总线声明仍须审查。
7. **使能与未用输入**：MIC94164/TPS27S100 及已核验 load_switch 走开关/保护项，移除其 LDO 压差资格；TPS709 EN 与 TPS5430 ENA 的允许开路以精确型号/物理脚加条款处理，EN 直连供电保留已有 source=rail 路径；CH340C/G 的指定未用输入向 NET-A01/A06/A07 提供带页码许可，未知型号、其他脚及实际接负载的网络不豁免。
8. **栅极驱动与供电追源**：沿串阻找真实驱动输出，但不穿地网把下拉后的测试针当源；仅对明确穿心电容 1↔2、接地 shunt3、BAT54C 共阴极方向及 TPS5430 PH 输出脚增加供电搜索，不把任意三端件短接。
9. **外部信号掉电注入**：每个外部非电源信号脚都有 SIG-C08；对端未知时明确写“对端供电未知，按注入电流/串阻问”，保存逐针 aspect，避免多针判断折叠；mains L/N 仍按电源端口处理。
10. **外接电源支路**：即使没有保险丝/MOV/NTC，每个可供电外引脚仍问 PRO-C04，直接无源分支到继电器/IC 电源另逐支路问；四跳内的保险丝逐对象问 PRO-C01/C05，不因 USB 候选收走器件而消失，重复 VBUS 并联针不重复计同一保险丝。
11. **ADC 输入**：SRP/SRN/SENSE/INnP/N、明确燃料计 BAT 与原生 ADC 复用脚进 ANA-C03，模组/连接器的明确 ADC 端口同样保留；显式 ANALOG 电路中分压接到不明 GPIO 时只派“是否用于 ADC，若是……”的条件问句，留下用途/复用证据缺口。
12. **USB 与 PMIC**：SIG-D04 要求实际 Type-C 连接器，Type-A/Micro-B 不派 CC 项；按每个 PMIC/LDO 输出脚或转换器反馈输出网生成 PWR-C04，regulator_output 去耦组也绑定该项，MUXSW 单独可定位，CLK-C01/CLK-D03 分别限定到无源晶体/RTC。

未用输入依据：WCH CH340DS1 V3C pp.3–4（p4 未用 I/O 说明）、TI TPS709 SBVS186H p3 Table5-1/p13 §7.4、TPS5430 SLVS632L p3 Table4-1/p9 §6.3.3。BAT54C 路由按 [Nexperia Rev6 原厂手册 p1 Table2](https://assets.nexperia.com/documents/data-sheet/BAT54C.pdf) 的物理针义；只增加搜索候选，不宣称压降、功率或动态供电能力合格。

## 回放方法与证据边界

before 为 `git archive 7b2ce7d` 的独立临时快照；不能用边改边跑的工作副本当 before。中途不完整/受版本变动影响的尝试已弃用。最终结果根为 `~/.cache/sr-boards/_merge2b/{before,after}/`，每板保存 db、冷扫、候选、决定日志、合并计划、输入与文件指纹；补充 JSON 登记逐规则数和匹配的归因条目。

```sh
python3 -B scripts/parse_kicad.py <fixed-netlist.xml> --no-strict -o <db.json>
python3 -B scripts/lint.py <db.json> --intent <intent-cold.json> --plan-json <plan-cold.json> --json <lint-cold.json>
python3 -B scripts/circuit_candidates.py <db.json> --intent <intent-cold.json> --datasheet-audit <audit.json> --json <candidates.json>
python3 -B scripts/circuit_decisions.py <intent.json> <candidates.json> --db <db.json> --write
python3 -B scripts/lint.py <db.json> --intent <intent.json> --datasheet-audit <audit.json> --candidates <candidates.json> --plan-json <plan-candidates.json> --json <lint-candidates.json>
python3 -B scripts/lint.py <db.json> --intent <intent.json> --datasheet-audit <audit.json> --candidates <candidates.json> --merge-plan <plan-candidates.json> --plan-json <plan-full.json> --json <lint-full.json>
```

两侧均保留 `--no-strict` 诊断，并对未声明的供电网络仅添加来自脚表的轨身份，不添加电压或产品要求；冷扫 intent 去掉旧电路/旧决定并绑定当前 db 指纹。rs485 原 intent 没有决定，双方使用同一个 `intent-with-decisions.json`。after 的手册审计按新物料组重建，只复用同身份文档，不把旧 PMOS 或旧 Value 的手册强绑到新 MPN。旧候选决定若失配，额外记录原失败与数据层重放：删除退役/DNP/已持有的旧 add，再生成覆盖探测用决定；新边界和所有权均标记未确认。没有通过的候选链只交付冷扫+冷计划合并，不冒称完整审查成功，也不为跑通回放改 2A 模型。

## before / after 数据

| 板（完整 ID 见附加 JSON） | 冷扫 before→after | 已归因误报行 before→after | 完整候选合并 before→after |
|---|---:|---:|---|
| amalthea-hardware | 4→2 | 2→0 | 通过→阻塞 |
| kimchi-micro | 26→31 | 3→2 | 通过→阻塞 |
| sparkfun_gnssdo | 56→51 | 27→22 | 通过→通过 |
| evse-v2-bricklet | 20→17 | 6→3 | 通过→通过 |
| transformer_less_power_supply_kicad_pcb_design_project | 0→0 | 0→0 | 通过→通过 |
| dpp-architecture-pcb | 0→0 | 0→0 | 通过→通过 |
| yellow | 62→62 | 47→47 | 通过→阻塞 |
| cb-eval-board | 29→25 | 11→7 | 通过→通过 |
| rs485-spy-injector | 47→32 | 5→0 | 通过→通过 |
| connect-programmer-hardware-design | 9→4 | 7→2 | 通过→通过 |
| switch-v4-hardware | 61→56 | 15→10 | 通过→阻塞 |
| cynthion-hardware | 17→17 | 4→4 | 阻塞→阻塞 |
| hackrf-pro | 33→33 | 8→8 | 通过→阻塞 |
| fuel-gauge-bq27441-breakout-hardware-design | 2→2 | 1→1 | 阻塞→通过 |
| eegfrontier | 13→13 | 1→1 | 通过→通过 |
| cellkeeper-hardware | 195→193 | 30→28 | 通过→通过 |
| urti-mainboard | 14→14 | 2→2 | 通过→阻塞 |
| amiga-2000-eatx | 75→66 | 10→1 | 阻塞→阻塞 |
| chlinknet | 55→40 | 10→0 | 通过→通过 |
| 4-channel-relay-board-hardware-design | 4→4 | 4→0 | 通过→通过 |

20 板合计冷扫 722→662，同口径已归因误报内容 193→138。完整候选合并 17/20→12/20；after 的 12 块包括 7 块使用明确标记为未确认的数据层决定重放，另 8 块阻塞，不能算全链通过。20/20 冷扫及其冷计划合并完成。

| 板 | SIG-C08 | PRO-C04 | ANA-C03 | PWR-C04 |
|---|---:|---:|---:|---:|
| amalthea-hardware | 0→18 | 0→2 | 0→0 | 0→3 |
| kimchi-micro | 9→140 | 0→35 | 0→3 | 0→12 |
| sparkfun_gnssdo | 6→43 | 0→16 | 0→0 | 0→0 |
| evse-v2-bricklet | 0→29 | 0→9 | 0→0 | 0→0 |
| transformer_less_power_supply_kicad_pcb_design_project | 0→2 | 0→1 | 0→0 | 0→1 |
| dpp-architecture-pcb | 0→2 | 0→4 | 0→0 | 0→0 |
| yellow | 12→87 | 0→24 | 0→0 | 0→0 |
| cb-eval-board | 2→44 | 0→14 | 0→3 | 0→0 |
| rs485-spy-injector | 0→29 | 0→5 | 0→0 | 0→0 |
| connect-programmer-hardware-design | 0→11 | 0→9 | 0→0 | 0→1 |
| switch-v4-hardware | 0→5 | 0→34 | 2→2 | 0→0 |
| cynthion-hardware | 6→70 | 0→27 | 0→8 | 0→0 |
| hackrf-pro | 6→69 | 0→12 | 0→8 | 0→0 |
| fuel-gauge-bq27441-breakout-hardware-design | 4→13 | 0→6 | 0→3 | 0→2 |
| eegfrontier | 1→7 | 0→0 | 1→9 | 1→1 |
| cellkeeper-hardware | 6→136 | 0→20 | 0→24 | 0→0 |
| urti-mainboard | 2→52 | 0→11 | 0→0 | 0→0 |
| amiga-2000-eatx | 0→904 | 0→107 | 0→0 | 0→0 |
| chlinknet | 0→21 | 0→9 | 0→16 | 0→0 |
| 4-channel-relay-board-hardware-design | 0→17 | 0→5 | 0→0 | 0→0 |

上表为同口径冷计划条数；SIG-C08 同时含原有内部跨域项。每条的物理 node/net、aspect 与全部规则的发现/计划数均保存在附加 JSON 及缓存计划中。并行 VBUS 针逐针 PRO-C04，保险丝同对象去重；条数增加不代表板子新增电气缺陷。

完整计划可比较的定点效果：cb-eval 的 PWR-E02 总数 10→1，U13–U21 九颗 TPS27S100 均不再套 LDO，保留的是 U37；connect-programmer 的 F1 PRO-C01/C05 各 0→1；chlinknet Micro-B 的 SIG-D04 1→0，rs485 Type-C 仍为 1；Kimchi 冷计划新增 U4 十二个输出的 PWR-C04，含 U4.55，旧完整计划的六项仅落在其他转换器电路，不能替代这十二个输出。

| after 完整候选阻塞板 | 最终阻塞原因（详见日志） |
|---|---|
| amalthea | 原发现 feature DEBUG 与已有 circuits 的输入资格冲突，未擅删需求/声明。 |
| kimchi | U13/U4 没有最终持有电路，需重新确认 add/所属电路。 |
| yellow | FL1/U12 等有源角色没有最终持有决定。 |
| switch-v4 | U302/U602 等有源器件没有最终持有决定。 |
| cynthion | C1/C10 等被三个候选同时持有，违反最多两电路的现行模型。 |
| hackrf-pro | U19/U20 等有源器件没有最终持有决定。 |
| urti | Q6/Q8 等有源器件没有最终持有决定。 |
| amiga-2000 | C204/C210 等被三个候选同时持有。 |

误报统计仅对 lane `false_alarm` 已归因内容做同规则、同实际网络/位号匹配，去重到一条冷扫行；部分 lane 的 refs/nets 列表不含正文中的未用脚，以正文精确节点补定位。NET-A02 等无 ref 的发现按网络定位。继电器 NET-A04 还复核内容已不再断言短接。兄弟规则未逐条归因的行不扩算，新增行未裁决不计真缺陷。此口径只用于同板 before/after，不是全面误报率；完整计划的误派另用逐对象资格检查和测试证明。

Kimchi R55 的错误下拉提示消失，但两项已归因 NET-A02 近名提示仍在；MPN 从旧 Value 改为订货字段后，一些电源/默认态判断暴露新的资料需求，故非 INFO 数上升。cb-eval 的剩余隔离域相关内容留给 2A。connect-programmer 的两个 SBU 未用脚标注候选仍在；没有泛化 Type-C 未用脚的电气豁免。

Cynthion 的旧 PMOS 手册组含 Q1/Q12/Q2/Q4/Q5/Q6/Q7/Q9，修后拆为 SIA483ADJ-T1-GE3（Q1/Q2/Q4/Q5/Q6/Q7）与 YJL3401A（Q12/Q9），不再互绑。Cellkeeper 的 C62 原在两个 Shunt Sense ± leg 中记作 series_caps、coupling=ac，修后不在任一 series_caps 中；原器件/连接未删。

实际 EVSE 三份相同哈希 PDF 的定类探针另列 `kind-probes.json`：DMMT5401 从 diode 误候选回到 bjt，Si2305CDS 从 load_switch/regulator 回到 mosfet，A5950 从 pwm_controller/sr_controller 回到 motor_driver；修后均不再有同类标题冲突。冷扫不含手册时不产生这些标题行，不能将此效果虚加到冷扫数字。

## 真缺陷保留

20 板 lane 的 42 条 `true_defect` 记录（含同缺陷多规则记录，不代表 42 个独立故障）的所有引用位号仍存在，原生 Value 均未改变；两侧 XML 哈希一致。题列证据逐项检查，见附加 JSON 的 `true_preservation`：

- Kimchi U3 的 Value=MT53E256M32… 与 Mfgrpart=MT53D512M32… 容量冲突保留；U4.55/NVCC_SD2、C113=1uF、C54=.22uF 的 1.22µF 名义值和接点保留，PWR-C04/C09 可逐输出定位。Ceff 的全工况保证仍依赖 ROHM Rev003 p110 Table5-36。
- chlinknet R1/R2、C3–C6、Y1 占位值保留；同提交 README 的 J2 针序、J3 供电、JP1/JP2 名称矛盾保留在固定源。后者是文档比对，未声称网表自动检出。
- rs485-spy 的 J4.A5/B5 单节点且无 Rd，NET-A01 仍报，Type-C 的 SIG-D04 仍具资格；14 只无值 C/R 的原值不变，ESP32 EN 的缺值不被 CH340 许可覆盖。
- cellkeeper 四只 USB 串阻 R70/R71/R127/R128=22Ω 原样保留，与 RP2350 p17 Table2 的 27Ω 要求仍可定位比对，不宣称实测失效。
- transformerless D5/D6 仍为 D_Zener，缺 VZ/MPN 的设计完整性缺口没有用默认选值掩盖。
- EVSE P111/U101.31 的视觉重叠来自固定原图；没有修改源图，也没有把网表正常当成图面可读性合格。
- BQ27441 的 BIN 上拉 R7=1.8M 接 VSYS、R5 下拉，以及 I²C 经默认跳线拉到 5V 的原始接法均保留；新增 ADC 资格不改变这些条款偏离的定位。

## 新种子、变异与门禁

登记四类、四个位点的真实板受控配对：Amalthea 外部信号旁路限流、connect-programmer 保险丝旁路、BQ27441 SRP/SRN 分流电阻增大、Kimchi MUXSW 输出容量不足。前两种及 ADC 探针的参数合同明确标为合成测试工况；没有把注入电流、钳位或差分窗口冒称器件保证。PMIC 基线是名义容量合成替代，不证明全温/偏压 Ceff 已合格。

`planned_targets` 单独记录目标 C 规则的逐对象计划命中；`auto` 仍只数新出现的目标规则发现，两者不混计。仅出现任意泛化 DEV 行不能算目标计划命中。

- 全量单测：三组实现阶段分别 2581、2591、最终 2612 passed；最终 3 skipped、5 项 PyMuPDF 弃用警告。最终源码/台账复验为 2612 passed, 3 skipped，241.44s。
- 变异：前两组 `--changed --tier unit` 56/56、116/116；最终主运行 224 条，另对新增的手册审计文件变动及 M130 独立复验 4 条，合计覆盖本组 227 个唯一选中变异，全部 KILLED、无失效锚点或存活。新增 M960–M999 共 40 条全部受门禁覆盖。M130 在台账编辑中间态复制的那次记录弃用，最终采用重跑记录；没有拿台账无效造成的失败充作行为杀死。
- 种子：冻结 7b2ce7d 基线 254 位点/225 自动/0 错误，逐位点无丢失或目标自动命中退化；新增四位点均有目标计划、自动 0，最终 258/225/0。不是历史 merge1 报告的旧 A 规则计数，而是本次实际基线。
- 典型电路：198 DETECTED、190 FIXED、14 KNOWN_FALSE_ALARM；无 MISSED、FALSE_ALARM_BACK、ERROR、UNCLASSIFIED。五个合法 CH340 未用输入由 expected 转为有证据的 fixed_false_alarms，不声称检出五个新缺陷。
- KiCad 原生回放：boards-merge2b-v1，195 MATCH、0 MISMATCH。
- 按要求独立运行 `python3 -B evals/detection/run.py`（仅指定本任务临时 work 路径），随后复用本次 258 位点、典型和原生回放结果重生成 `evals/detection/RESULTS.md`；退出 0。表中保留新 C 种子的 4 个自动层缺口。
- 台账检查 PASS，原始条款库/受限代码字节差异为零，`git diff --check` 通过。pytest 的共用层比较使用真实历史配对 ASG 提交 5e7c969 的只读快照；安装版 ASG 有历史版本漂移，本次没有修改/复制共用层来消除差异。

门禁和回放日志归档至 `~/.cache/sr-boards/_merge2b/gates/`、`metrics/`、`seeded/`；每板链的重放脚本、精确归因输入也在 `_merge2b/`。

新建 KiCad 回放约定 `boards-merge2b-v1`，保存父约定哈希，旧约定不改。typical 中原来把 CH340 五只合法未用输入当 expected 的条目改成有原厂依据的 fixed_false_alarms；未删除真实输入偏置反例。重锚 M793（有界 Description）、M887（字段装配来源）、M91（内部接口资格）；新变异从 M960 起，含原生身份/资料段落、脚角色和计划资格。每次门的无变异基线先通过再计杀死；中断或锚点失效的运行不计通过。

第一步阅读量上限仅增加 266 字节（170810→171076），对应生成词表新增的三个资格条件；没有放宽其他步骤，没有删减规则来过阅读门。

## 准则问题，留给人工处理

1. G04-091 通用句不应直接否定 WCH 共偏置中心抽头，须先限定准确 PHY/网络拓扑和原厂接法（chlinknet）。
2. USB-PD/Type-C 数值与条款不能直接套 Micro-B（chlinknet）；本次只修 SIG-D04 的 CC 资格，SIG-A05 外包络及其他通用 USB 项的数值/准则依据没有擅改。
3. G01-031 只登记 USB 却引用 Type-C 适用条款（Yellow 的 J4 Type-A），准则登记的适用性应另修；本次连接器物理型别可阻止该端口派 CC 问句，不能据此宣称准则库已修正。

## 没有闭合的模式

- 带点位号：节点键以 `ref.pin` 串联，全面支持需要同时改 parser、NetGraph 和候选成员解析；后两处与 2A 负责范围交叠，未做会使旧键悄悄分裂的局部改名。GNSSDO 仍保留导入诊断及原始图定位。
- 模组内部电源/主控：未建立精确 ESP32 模组内部 USB→LDO→3V3 的电源/角色模型；Würth 171023801 这类内部开关节点未外引的电源模组也未建立专用模型，cb-eval U37 仍有线性启动/压差候选（已明确列入未闭合项）；没有把普通芯片家族猜成具体模组，EEGFrontier 的内部电源与 SPI 锚点问题仍留缺口。
- 外部分支：当前覆盖物理外引电源针与直接无源分配支路、四跳内保险丝；任意深度的多路有源分配、可逆电源和其他二极管阵列仍需模型/证据，不把遍历拓展成全图导通。
- ADC：没有明确 ADC 脚表/用途且不在已声明 ANALOG 分压电路的普通 GPIO，不凭网络名字断言采样用途；不明 ADC 复用只保留条件问题。
- 未用输入许可：只登记已取得条款的精确 CH340C/G、TPS709、TPS5430；其他器件需提交准确型号与条款页。Type-C SBU 的备用标注候选没有一刀切关闭。
- 候选持有/隔离域：没有修改 2A 代码来强行通过旧决定；当前阻塞板与原因逐板记录。新定类后需重新确认候选所有权，不能把覆盖用重放当用户批准的电路定界。
- 准则适用性和特定手册参数没有泛化推断；本次计划资格改进不构成专家数值审查、布局/SI/PI/热/EMC 或生产准出。

## 文件清单

共 51 个文件（含新回放约定及自有证据数据）：

- `docs/improvement-ledger.md`
- `docs/proposals/boards-merge-2b-2026-11-02.json`
- `docs/proposals/boards-merge-2b-2026-11-02.md`
- `evals/detection/RESULTS.md`
- `evals/kicad_replay_bench/revisions/boards-merge2b-v1/cases.json`
- `evals/kicad_replay_bench/revisions/boards-merge2b-v1/expected.json`
- `evals/kicad_replay_bench/revisions/boards-merge2b-v1/manifest.json`
- `evals/kicad_replay_bench/revisions/boards-merge2b-v1/sources.json`
- `evals/kicad_replay_bench/run.py`
- `evals/mutation/README.md`
- `evals/mutation/mutations.json`
- `evals/seeded_bench/README.md`
- `evals/seeded_bench/boards-merge2b-results.json`
- `evals/seeded_bench/boards-merge2b.json`
- `evals/seeded_bench/mutators.py`
- `evals/seeded_bench/run.py`
- `evals/typical_circuits/cases.json`
- `references/check-catalog.md`
- `references/checker-conventions.md`
- `references/review-vocabulary.md`
- `scripts/audit_datasheets.py`
- `scripts/board_scans.py`
- `scripts/catalog.py`
- `scripts/checkers/decoupling.py`
- `scripts/checkers/diff_levels.py`
- `scripts/checkers/inductive_load.py`
- `scripts/checkers/input_filter.py`
- `scripts/checkers/power_switch.py`
- `scripts/checkers/power_up.py`
- `scripts/checkers/powertree.py`
- `scripts/datasheet_kinds.py`
- `scripts/decoupling.py`
- `scripts/i2c_topology.py`
- `scripts/interfaces.py`
- `scripts/lint.py`
- `scripts/parse_kicad.py`
- `scripts/part_words.py`
- `scripts/plan_circuits.py`
- `scripts/tests/fixtures/interfaces-flyback-usb.json`
- `scripts/tests/ledger4.py`
- `scripts/tests/test_boards_merge2b_coverage.py`
- `scripts/tests/test_boards_merge2b_identity.py`
- `scripts/tests/test_boards_merge2b_roles.py`
- `scripts/tests/test_boards_merge2b_seeds.py`
- `scripts/tests/test_catalog.py`
- `scripts/tests/test_circuit_decisions.py`
- `scripts/tests/test_interface_rows.py`
- `scripts/tests/test_optical_library.py`
- `scripts/tests/test_part_kind_evidence.py`
- `scripts/tests/test_part_number_families.py`
- `scripts/tests/test_reading_path.py`

# 电路候选由网表生成：消掉审查员画电路这一层差异的方案

状态：4.7 节的步 1–7 已全部实施（2026-10-21，见改进台账两条 2026-10-21 条目）；第 6 节记录与 Codex 合并方案的对照和已做的决定。
实施与设计稿不同处：决定多了一种 `add`（4.4 节），`intent.circuits` 由 `circuit_decisions.py --write` 写出而不是 `plan_review --from-candidates`，
校验在 `circuit_decisions.validate` 并由 `validate_intent(--candidates)` 与 `pack_review` 调用；验收 2 未达标（6/10 与 4/11，见 4.6 节）。基线：SR main 6f59d0e；案例：R5 两份首审
（SR-20261021-R5-claude-fd6a6dd 与 -codex-fd6a6dd，同一网表、同一技能版本）。

## 0. 一页摘要

两份记录经 6f59d0e 的 F1–F12 守卫之后，剩下的行差异几乎全部来自 `intent.circuits`：
电路是审查员手画的，名字、成员、工作态三样都自由，计划再把每个电路 × 工作态展开成行，
于是 10 个电路对 11 个电路、同一个电路的成员相差 5–8 颗器件、工作态一个写 `fault` 一个不写，
compare_reviews 对不上的 74 行里大多数就从这里来。

改造：计划不再读审查员画的电路，而是先从网表、器件类别和检查器已有的库存**生成候选电路**
（`record/circuit-candidates.json`），每个候选有确定的编号（类型 + 核心器件）、成员（每颗器件带
“怎么走到的”路径）、工作态（按类型固定）。审查员对候选只做**接受 / 合并 / 拆分 / 拒绝**四种
决定，每个决定要引用；`intent.circuits` 由决定生成，不再手写。校验拒绝任何不对应候选的电路。

试算（第 2 节）：用现有库存加一个“从核心器件引脚向外走过两端器件”的规则，不写任何新检查器，
R5 的 10 个 Claude 电路里 4 个已能以 Jaccard ≥ 0.6 复现，PFC 和 SENSE 到 0.88；没复现的 6 个
各有一条可写成规则的原因（第 2.2 节），没有一个需要审查员的判断。

预期：两份 R5 记录重新生成意图后，电路对齐 ≥ 9/10 且 Jaccard ≥ 0.8，行对齐 ≥ 95 %（现在 75 %）。

## 1. 差异在哪一层（R5 的数字）

| 现象 | Claude | Codex | 后果 |
|---|---|---|---|
| 电路个数 | 10 | 11 | 多出的 OUTPUT-FAULT / CONFIG 各带一组行，对面没有 |
| 同一电路的成员 | FLYBACK 27 颗 | FLYBACK 25 颗，其中 6 颗对面没有 | 行的 part 不同，键对不上 |
| 启动电路的成员 | START：U402、U403、C403、R403 等 8 颗 | SEQUENCE：U201、U402、U404、R406 等 11 颗 | 同名类型 STARTUP，交集 2 颗 |
| 输出保护 | 并入 USB-PORT 与 FLYBACK | 单列 OUTPUT-FAULT（C503–C505、D403、D405、D706） | 一边 28 行一边 0 行 |
| 工作态 | INPUT 三态，SR 两态 | INPUT 三态，SR 两态，PORT 三态 | 大体一致，但 `fault` 的有无由人定 |
| 名字 | PFC / BIAS / ISO / SENSE | PFC / BIAS / BARRIER / MONITOR | compare_reviews 已按类型+成员对齐，名字本身不再是问题 |

两边的 `device_kinds`（28 颗，带手册页码和原文引用）**完全一致**：凡是要求引用的输入，两个
agent 就不漂。电路成员没有这个要求，所以漂。

## 2. 试算：现有库存能生成多少

### 2.1 已经确定、可直接用的输入

| 输入 | 来源 | 确定性 |
|---|---|---|
| 网表 `nets / pin2net / pinname / parts` | db.json | 完全 |
| 页面划分 `ref2page / page_inventory`（8 页，按功能分图） | db.json | 完全；但不能当成员规则，分图是绘图习惯 |
| 器件类别 `device_kinds`（diode/zener/tvs/mosfet/opto/bridge_rectifier/bjt/connector） | intent，带引用 | 两份记录一致；**集成电路没有类别** |
| 开关管库存：开关、驱动引脚、栅极上下拉、吸收、开关节点证据 | plan.power_switch | 两份一致 |
| 电感负载库存：拓扑（boost_converter）、输出/回流网络、输入输出电容 | plan.inductive_load | 变压器和共模电感因 `pin-roles` 缺口 UNRESOLVED |
| 光耦库存：LED 驱动引脚、集电极/发射极网络、上拉 | plan.optocoupler | 两份一致 |
| 钳位件 `clamp_refs` | plan.checks PRO-D03 | 两份一致 |
| 电源轨及其域 | intent.power_rails | 审查员声明，两份一致但范围偏宽（见 2.2） |
| 引脚电气类型 `pintype` | db.json | 340 脚里 271 脚 UNSPEC，**不能依赖** |

### 2.2 试算规则与结果

试算脚本（本会话临时，不入库）：核心器件 = 有驱动引脚的控制 IC 或开关管本身；成员 = 从核心器件
各引脚出发，经两端器件（电阻、电容、二极管）向外走 3 跳，遇到声明电源轨、地、别的核心器件停；
另加开关管库存里的栅极上下拉、吸收、电感负载及其电容。隔离候选 = 引脚跨两个域的器件。
USB 候选 = 带 CC 脚的连接器向外走一跳加钳位件。输入保护 = 连接器沿串联链走到第一条电源轨。
模拟候选 = 核心器件名为 CS/NTC/TEMP 的引脚向外走两跳。调试候选 = 测试点及其网络上的器件。

| 审查员电路（Claude / Codex） | 最佳候选 | Jaccard | 没对上的原因（都能写成规则） |
|---|---|---|---|
| PFC / PFC | POWER_CONVERTER-U201 | 0.88 / 0.82 | 候选多了输入电容 C101（电感负载库存把它算作输入电容），少了 C206、D202（第 4 跳） |
| SENSE / MONITOR | ANALOG-U601 | 0.88 / 0.88 | 只差 R503（在 SR 页，审查员按“监测”归类） |
| SR / SR | POWER_CONVERTER-U501 | 0.67 / 0.50 | 输出电容 C501–C506 的归属：一边给 SR 一边给 FLYBACK；候选多了 T301 |
| ISO / BARRIER | ISOLATION-PRI/SEC | 0.60 / 0.60 | 光耦 U202、U403 只有一个域可判，因为声明的电源轨里没有它们的集电极网络；按地连通性判域即可 |
| INPUT / INPUT | POWER_PROTECTION-J101 | 0.50 / 0.33 | 试算在 RECT 轨停了，EMI 滤波器和 BR101 后的 C101 被截掉；规则应走到第一个储能电容 |
| FLYBACK / FLYBACK | POWER_CONVERTER-U402 | 0.52 / 0.50 | 候选把 U402 偏置侧的 C404–C407、D403、D405 收进来，审查员把二次侧整流 D302、D303、C503–C505 和 Q302 收进来：次级归属和 VCC 侧边界各需一条规则 |
| BIAS / BIAS | POWER_CONVERTER-Q401 | 0.44 / 0.44 | 核心器件是分立管，AUX_DC、BIAS15 被声明成电源轨，走到那里就停，D401、D402、C402–C405 漏掉：只有两个以上核心器件共用的网络才算“轨” |
| USB-PORT / PORT | USB-U601 | 0.45 / 0.68 | 候选从 U601 出发穿过光耦 LED 电阻走到了 U202、U403、T301：光耦是跨域器件，走到即停 |
| OVP-LATCH / OUTPUT-FAULT | 无 | — | 跨电路的保护链（U402 的 OVP/LATCH 脚、U601 的 FAULT 脚）：按“核心器件保护类引脚的输入通路”单独成候选 |
| START / SEQUENCE | 无 | — | 启动与使能链（HV 启动电阻、U404 到 U402 的使能、U201 到 U402 的时序）：按“核心器件启动类引脚的通路”单独成候选 |
| — / CONFIG | DEBUG-TP | 0.20 | 试算把测试点所在网络的全部器件收进来；调试候选只收测试点和它接触的引脚 |

结论：成员差异的来源不是网表信息不够，是**边界规则没写下来**（什么算轨、跨域器件停不停、次级归谁、
跨电路的保护和启动链算不算一个电路）。每条写下来，两个 agent 就得到同一个答案。

## 3. 目标与不变的部分

目标

- 电路的编号、成员、工作态由脚本从网表生成，审查员只做带引用的决定，两份记录生成同一组候选。
- 候选里每颗成员都带“怎么走到的”（路径或库存来源），校验能核，报告能引。
- 对新板型不卡死：规则生成不了的功能走拒绝/新建路径，但要引用，并计入 REQ-Q08。

不变

- 规则目录（CIRCUIT_TYPES、subjects、QUESTIONS、BOUNDING_STEPS）、功能判定 F1–F12、行派生、打包。
- `plan_subjects` 展开电路 × 工作态为行、建功能框架的方式；只是电路列表的来源换了。
- 不在 SR 里存任何项目先验：候选规则按器件类别和引脚名写，测试夹具用合成板（memory：sr-no-project-priors）。

## 4. 设计

### 4.1 候选文件 `record/circuit-candidates.json`（schema 1）

```json
{"schema_version": 1, "db_sha256": "…", "intent_inputs_sha256": "…",
 "domains": {"PRI": ["PGND"], "SEC": ["SGND", "SEC_RTN"]},
 "rails": ["BULK", "VCC", "VBUS", "V5"],
 "barriers": ["T301", "U202", "U403", "U404", "CY301"],
 "candidates": [
  {"id": "POWER_CONVERTER-U402", "type": "POWER_CONVERTER", "anchor": "U402", "domain": "PRI",
   "members": [
     {"ref": "Q301", "role": "switch", "via": "power_switch:driver-pin U402.7"},
     {"ref": "R301", "role": "gate", "via": "walk U402.7 -> R301 -> Q301.G"},
     {"ref": "T301", "role": "inductive", "via": "power_switch:switch_node_evidence inductive:T301"},
     {"ref": "D302", "role": "rectifier", "via": "secondary T301.5 -> D302 (no SR anchor claims it)"}],
   "nets": {"switch": "SW_FLY", "output": "VRAW", "return": "SEC_RTN", "supply": "VCC"},
   "states": ["startup", "run", "fault"], "pages": [4, 6]},
  {"id": "STARTUP-U402.HV", "type": "STARTUP", "anchor": "U402", "pin": "U402.8", "pin_name": "HV", …},
  {"id": "PROTECTION-U402.OVP", "type": "POWER_PROTECTION", "anchor": "U402", "pin": "U402.3", …}],
 "unassigned": [{"ref": "R213", "nets": ["…"], "reason": "no anchor within 3 hops"}],
 "gaps": [{"ref": "L101", "kind": "pin-roles", "need": "datasheet pin table for a 4-pin common-mode choke"}]}
```

编号规则固定：`<TYPE>-<anchor>`；同一核心器件按引脚组再分的，加 `.<PIN_NAME>`；板级唯一的
（输入保护、隔离）用 `-<connector>` 或 `-<domainA>/<domainB>`。编号由脚本产生，审查员不改。

### 4.2 生成规则（按确定性从高到低）

**A. 域与轨（netgraph/powertree 扩展）**

- 地网络来自 intent.power_rails 里 `kind: ground` 的声明（已有）；域 = 从地出发经非跨域器件可达的
  网络集合。跨域器件 = 引脚跨两个域的器件（变压器、光耦、Y 电容、数字隔离器），由器件类别和
  “引脚分属两个地连通分量”共同判定。R5 两份记录声明的 PRI/SEC 应当被这条规则完整复现（验收 1）。
- 轨 = powertree 已判的轨 ∪ 声明轨中**被两个以上核心器件引脚直接或经一颗两端器件到达**的网络
  （那一跳不经过地：接地旁路电容不让地上的每颗 IC 都“到达”该网）。
  只被一个核心器件用的声明轨（BIAS 的 AUX_DC）是那个电路的内部节点，不作截止网络。
  步 2 在 R5 上的测量：截止网络 = 三个地、两条 IC 驱动的次级轨、VCC、BIAS15、PD_VDD；BULK、RECT、VBUS 不是截止网络
  （一跳内没有核心器件到达）。**步 3 要把电感负载库存的输出/回流网（BULK、VBUS）加入截止网络**，否则 PFC 的
  walk 经 BULK 走进反激的 RCD 钳位。

**B. 核心器件**

- 核心器件 = 带类别的集成电路（见 4.3，`pwm_controller / gate_driver / sr_controller / pd_controller /
  regulator / supervisor / opamp_comparator / mcu / transceiver`）、power_switch 库存里有驱动引脚的
  开关管、以及没有驱动 IC 的分立开关（BIAS 的 Q401：开关管库存标 `driver: none`）。
- 一颗分立开关若其驱动引脚来自某 IC，归那 IC 的候选；否则自成候选，核心器件是开关管本身。

**C. 成员闭包（walk）**

从核心器件每个非电源、非地引脚出发，经**两端器件**（电阻、电容、电感、二极管、TVS、稳压管、保险、
压敏、NTC，按 pin 数 = 2 或器件类别）向外走，上限 4 跳；停在：轨、地、别的核心器件引脚、跨域器件
引脚（跨域器件本身作为成员收进，但不穿过）。每颗成员记录完整路径作为 `via`。三端器件（BJT、小信号
MOSFET、三端稳压）只有在 power_switch/optocoupler 库存里已有角色时才收，并带库存来源。

被两个候选同时走到的器件：归路径更短的候选；相等时归核心器件在同一页的候选；仍相等的记入
`shared`，两边都列、两边的 via 都写。审查员不裁。

**D. 各类型的专门规则**

| 类型 | 候选 | 成员来源 | 边界规则（本次试算暴露的） |
|---|---|---|---|
| POWER_CONVERTER | 每个（控制 IC, 开关, 电感负载）三元组一个 | power_switch + inductive_load 库存 + walk | 电感负载的次级整流和输出电容归该变换器，**除非**有 `sr_controller` 核心器件驱动该整流管，则整流管、其驱动件归 SR 候选，输出电容仍归变换器；核心 IC 的 VCC/偏置侧网络若与另一核心器件（BIAS）相连，以轨为界 |
| POWER_PROTECTION（输入） | 每个交流/直流输入连接器一个 | 连接器沿串联链（保险、压敏、NTC、共模电感、X 电容、泄放电阻、整流桥）走到**第一个储能电容**（电感负载库存的 input_capacitors 或该网络上容量最大的电容）为止 | 不以轨为截止网络；整流后的 RECT 节点不是边界 |
| POWER_PROTECTION（保护链） | 每个核心器件的保护类引脚组一个：`PROTECTION-<anchor>.<PIN>` | 引脚名匹配 `OVP|UVP|OCP|OTP|LATCH|FAULT|BO|BROWNOUT|PROT` 的引脚向外 walk，含光耦（作为跨域器件成员）到对侧的驱动件 | 跨电路：成员可与变换器候选重叠，记 shared |
| STARTUP | 每个核心器件的启动类引脚组一个：`STARTUP-<anchor>.<PIN>` | 引脚名匹配 `HV|VSTART|EN|ENABLE|INH|UVLO|SS|SOFT|RUN|DELAY` 的引脚向外 walk 到轨/核心器件/跨域器件 | 两份记录的 START/SEQUENCE 都成为 STARTUP-U402.HV 和 STARTUP-U402.EN（经 U404）两个候选，再由审查员决定合并 |
| ISOLATION | 每对域一个 | 全部跨域器件 + 跨域的 Y 电容/放电电阻 | 光耦按地连通性判域，不依赖声明轨 |
| USB | 每个带 CC/D+/D- 引脚的连接器一个 | 连接器引脚 walk 一跳 + PRO-D03 clamp_refs + 驱动 VBUS 开关的 PD 控制器及其 power_switch 库存 | 光耦是跨域器件，不穿过（试算穿到 U202/U403 的根源） |
| ANALOG | 每个核心器件一个，成员按引脚分组 | 引脚名匹配 `CS|ISNS|ISENSE|VSNS|FB|NTC|TEMP|RT|ZCD|AIN` 的引脚向外 walk 两跳（分压、采样电阻、滤波） | 不走到别的候选的开关节点 |
| DEBUG | 板级一个 | 测试点、烧录/调试连接器及其直接接触的引脚 | **不** walk：测试点所在网络的其他器件不是成员 |
| I2C/SPI/UART/CAN/RS485/ETHERNET/DDR/STORAGE/RF/HSSERIAL/AV/LEVEL_SHIFT/CLOCK | 每条总线/每个收发器一个 | 现有 i2c_topology、diff_levels 库存；其余按核心器件类别 `transceiver/mcu` 与引脚名 | 本案例不触发，规则先占位，用合成夹具测 |

**E. 工作态**

每种类型一组固定工作态，写进 catalog（POWER_CONVERTER `startup/run/fault`，POWER_PROTECTION
`startup/run/fault`，USB `unattached/attached/fault`，ANALOG `run/fault`，ISOLATION `run`，
STARTUP `power-on/restart`，DEBUG 无态）。候选按类型带态；审查员增减一个态必须引用手册里的
模式名（像 F1 的条款那样定位到页/表），否则校验拒绝。R5 两份记录的态差异（SR 两态 vs 三态、
INPUT 的 fault）由此消失。

### 4.3 集成电路也要类别

现在 `device_kinds` 只覆盖分立件和连接器，4 颗控制类 IC（PFC、反激、同步整流、PD 控制器）没有类别，光耦已有，而核心器件规则依赖它。扩展词表
（`pwm_controller, gate_driver, sr_controller, pd_controller, regulator, supervisor,
opamp_comparator, mcu, transceiver, isolator, other_ic`），要求与现在相同：手册页码 + 原文引用；
缺了是现有的 `intent.device_kinds.<ref>` 缺口，不是新机制。两份 R5 记录各补 4 条即可。

引脚名来自符号（`db.pinname`）；符号引脚名只有数字的 IC（库里常见），候选生成记 `pin-roles`
缺口，要求手册引脚表（和 inductive_load 对 L101/T301 的处理相同），这颗 IC 的候选标
`incomplete`，计划生成 REVIEW_INCOMPLETE 开放项，不猜。

### 4.4 审查员的决定与 `intent.circuits` 的生成

`intent.circuit_decisions`（新字段，schema 4）：

```json
[{"candidate": "POWER_CONVERTER-U402", "decision": "accept"},
 {"candidate": ["STARTUP-U402.HV", "STARTUP-U402.EN"], "decision": "merge", "id": "START",
  "citation": "U402 手册 p12 §7.3 启动时序把 HV 启动与 EN 使能列为一个流程"},
 {"candidate": "POWER_CONVERTER-U501", "decision": "split", "into": [{"id": "SR", "members": ["U501", "Q501", "R501", "R502"]}],
  "citation": "…"},
 {"candidate": "DEBUG-BOARD", "decision": "reject", "reason": "OUTSIDE_SCOPE", "citation": "需求 REQ-xx：测试点不交付"}]
```

- 四种决定：accept（原样）、merge（引用一条把它们描述成一个功能的条款）、split（成员必须是候选
  成员的子集，且每个子集仍含核心器件或开关之一）、reject（理由枚举：OUTSIDE_SCOPE / NOT_A_CIRCUIT /
  DUPLICATE_OF，引用）。
- 改成员只能通过 split/merge；**不能**向候选加入它没走到的器件。审查员认为漏了器件 → 那是规则
  或网表的缺口，记 `unassigned` 复核项（REQ-Q08 一行），改规则而不是改记录。
- 名字：`id` 可以自定（PFC、FLYBACK），但 compare_reviews 已不靠名字对齐；候选编号保留在电路上
  （`candidate_id`），行和框架用它。
- `intent.circuits` 由 `python3 scripts/circuit_decisions.py intent.json record/circuit-candidates.json --db db.json --write` 生成（实施时改用独立脚本），
  同时写 `circuit_candidates_sha256`；电路带 `candidate_ids`、`cross_cutting`、`anchors`。
- 实施时加了第五种决定 `add`：生成器没找到的功能（设计稿里的 UNRESOLVED_CANDIDATE 出口），只能收 `unassigned` 中的器件，
  每颗写它所在的网（`via`），类型取规则总表包名，引用可定位。它仍不是“向候选手加成员”的通道。
- 实施时还让 `power_switches` 声明了角色、而驱动它的 IC 没有核验角色的开关自己作核心器件（变换器按声明存在，未核验的驱动 IC 留在缺口里）：
  KiCad 回放台架的 rf1 板没有资料审计，否则声明的反激主开关无候选。

### 4.5 校验

实施为 `circuit_decisions.validate`，由 `plan_review.validate_intent(..., candidates=...)`（lint/plan 的 `--candidates`）和 `pack_review`（`--circuit-candidates`）调用：

1. 候选文件的 `db_sha256` 等于当前 db；每个决定引用的候选存在；每个候选恰有一个决定（没有 → 错误，
   不是 UNDETERMINED）。
2. 每个 intent 电路对应一个决定；成员集合与决定推出的集合相等；态与类型固定态一致或多出的态带定位引用。
3. 一颗器件最多属于两个电路，属于两个时其中一个是跨电路类型（ISOLATION / STARTUP / 保护链）。
4. `unassigned` 中每个带核心器件三跳内的器件都在 REQ-Q08 行里列出。
5. 功能框架的 objects 直接取候选成员，F11 由构造保证。

### 4.6 验收指标

- 验收 1（域）：R5 db 上算出的 PRI/SEC 域与两份记录声明的 13 条轨的域一致，光耦三颗判为跨域器件。
- 验收 2（候选）：对 R5 两份记录的 10/11 个电路，候选（经各自记录中决定）与原电路 Jaccard ≥ 0.8
  的 ≥ 9 个；没有候选的审查员电路 = 0。
- 验收 3（收敛）：两份记录用同一候选文件重走 intent → plan，`compare_reviews` 行对齐 ≥ 95 %
  （基线 75 %，296 行）；电路 matched 全部、only_A/only_B 为空。
- 验收 4（不过严）：合成夹具上一块数字板（MCU + 两路 LDO + I²C + 调试口）生成的候选不多于
  实际功能数 + 1，拒绝率可计数。
- 验收 5：全部现有测试通过，M44–M51 仍被杀；新增变异 M52–M56（轨截止网络、跨域器件穿越、次级归属、
  合并引用、态引用）各被杀。

实测（2026-10-21，R5 两份记录作台架，四颗控制 IC 的类别按两份记录的声明模拟核验）：
- 验收 1 通过（步 2）。
- 验收 2 **未达标**：12 个候选、0 件 shared、8 件未归属、2 条引脚名缺口（L101、T301）；与审查员电路 Jaccard ≥ 0.8 的 Claude 6/10（均值 0.83）、
  Codex 4/11（均值 0.67）。差在规则选择而不是噪声：启动链按脚各成一条（审查员合成一个 START/SEQUENCE）、同步整流候选不收变压器、
  Codex 的 PORT 把 USB 与输出分流写在一起、OUTPUT-FAULT/CONFIG 是审查员按页面划的。候选规则不为迁就某一份记录改。
- 验收 3 的前半（同一候选、两套决定）：两套决定下的计划 420/410 行，410 行相同，只多的 10 行是没合并的 STARTUP-U402.HV；
  电路对齐 10/11。两份记录重走 intent → plan 的后半没做：记录的其余段落（轨、库存声明）本就不同，不是候选层的差异。
- 验收 4：合成夹具（反激 + buck + PD/USB + 链 + 测试点）生成 11 个候选对 10 个功能，`test_circuit_candidates.py`。
- 验收 5：1760 个测试通过，约定层 475；M44–M55 仍被杀；新增 M56–M61（跨域器件穿越、同距共享、无决定、拆分漏成员、手画电路、无候选文件打包）全部被杀。
- KiCad 回放台架新约定 `circuit-candidates-v1`：rf1 frames 用例改用候选文件与 4 条决定，电路 3→1、检查数 325→313。

### 4.7 实施顺序（每步一次提交，测试先行）

| 步 | 改动 | 测试/度量 |
|---|---|---|
| 1（已做） | `board_intent.IC_KINDS` / `ANCHOR_KINDS`，`datasheet_kinds` 角色词核验，`NetGraph.role_kind` / `is_anchor`；U/M 位号无核验类别即 DEV-D02 缺口 | 两份 R5 记录各出 4 条缺口（四颗控制 IC）；`test_ic_kinds.py` |
| 2（已做） | `checkers/domains.py`：地连通域、跨域器件、核心器件、截止网络，写入计划 `domains`，冲突进 diagnostics | 验收 1 通过（13 条声明域一致、5 件跨域器件、0 冲突）；`test_domains.py` 合成双域反激 |
| 3（已做） | `scripts/circuit_candidates.py`：walk、shared 裁决、POWER_CONVERTER / 输入保护 / ISOLATION / USB / ANALOG / DEBUG 规则，写候选文件；CLI 与 `--json` | 合成夹具黄金文件；R5 db 作台架测量（不作夹具）：表 2.2 的 7 个可对齐电路 Jaccard ≥ 0.8 |
| 4（已做） | STARTUP、保护链、总线类规则 | 表 2.2 的 4 个“无候选”电路有候选；合成数字板验收 4 |
| 5（已做） | `intent.circuit_decisions`、`plan_review --from-candidates`、`validate_candidates`；框架 objects 取候选成员；SKILL 第 2/3 步、plan-and-results、inputs-and-coverage 改写 | 约定测试；mutations M52–M56 |
| 6（已做，验收 2 未达标） | 台架：两份 R5 记录各写决定、重生成 intent 与 plan，`compare_reviews` 记录到 ledger；改进台账 | 验收 2、3 |
| 7（已做） | 旧记录：schema 3 意图没有候选文件 → `validate_intent` 报 `CANDIDATES_MISSING`，`pack_review` 拒绝；没有兼容层（memory：sr-training-no-old-result-compat） | 两份 R5 记录在步 6 前被拒 |

步 1–4 不改记录格式，可以先合入；步 5 改 schema，与步 6 同批合入。总量估计：脚本约 600 行，
测试约 900 行，文档改动四处。

## 5. 风险与取舍

- **pintype 不可用**（80 % UNSPEC）：所有规则只用 `pin2net`、`pinname`、器件类别和库存，不碰 pintype。
- **引脚名依赖符号质量**：PD100 库的 IC 有名字（试算已匹配 CS/NTC），通用符号可能只有数字；
  走 `pin-roles` 缺口，不猜。这是对审查员最可能的新负担，但它换来的是两份记录同一组核心器件。
- **跨电路链（STARTUP、保护链）成员与变换器重叠**：允许且记 shared，F11 的“行的器件属于函数对象”
  仍成立，因为两个框架都列了它。compare_reviews 的 jaccard 对齐不受影响。
- **规则生成不了的功能**：reject/NOT_A_CIRCUIT 和 `unassigned` → REQ-Q08 是出口，不会卡住一块新板，
  但拒绝率和未归属器件数要进台账，作为规则库的欠账。
- **过严**：候选只增加“必须决定”的事项，不增加行；决定是四选一加引用，每个候选一条，R5 约 14 条。
- **不做的**：不用页面划分当成员规则（分图是绘图习惯，不同画法同一电路），只作 shared 裁决的次级
  依据；不做自动命名；不给审查员“手加成员”的通道。

## 6. 与 Codex 合并方案的对照（2026-10-21）

Codex 的《SR双方修改合并方案》（SR技能优化/20261021-双方合并方案）在本设计实施中途送到，逐节的处理：

- **§6 候选电路方案的接入边界：已按它实施。** 候选编号用核心器件不用页码；页码只作显示；走线是归属关系，`via` 不是导通主张；
  同距离共享记 `shared`，跨电路候选可与电路重叠；生成器找不到的功能走 `add` 决定（只收未归属器件、逐颗写网），
  不给“向候选手加成员”的通道。
- **§3 取消“缺口最多影响 3 个方面”的硬限制，改逐项依赖证明：已合并（2026-10-21）。** `decides[]` 每条是影响条目
  `{aspect, states?, check_ids?, effect, via, rationale}`，DESIGN_VALUE/VENDOR_DATUM/DELIVERABLE_PENDING 的边都写 `via`
  （本功能的条件，或计算的 claim 与 `calculation.inputs` 里的输入）和 `rationale`；超过 3 个方面只出 WIDE_GAP 提示，
  同一句理由只出 TEMPLATE_REASON 提示；`decides_reason`、`margin_not_decisive_reason`、`loose_bound` 退役，写了报错。
- **§4 “可定位引用”与“有效判定依据”分开：已合并。** 条件分五种（NUMERIC_LIMIT / MANDATORY_CLAUSE / NETLIST_FACT /
  TYPICAL_REFERENCE / ENGINEERING_ASSUMPTION），各有必需字段；余量写依据 `basis`（GUARANTEED_BOUND / REACHABLE_CASE /
  EXACT_ENVELOPE / ESTIMATE，GE/GT，跨 regime 要 `conversion`）；判断只靠强制条款或网表事实，不引数字限值；
  同一范围通过与失败并存是 EVIDENCE_CONFLICT；不写 `states` 只覆盖无状态行。本设计的决定引用仍只用“可定位”这一层。
- **§5 模糊匹配不进正式一致率：已合并。** 检查项标识取规则、规则版本（目录条目与问题模板的摘要）、去掉 `circuit` 名称的物理对象和判据，
  没有放候选编号：候选编号随核心器件和生成规则变，而物理对象已经确定检查项；`plan_review` 写键，校验器重算并拒绝同一项检查问两次。
  `compare_reviews` 先做精确配对（精确键 + 经核实的 `--alias`），按电路对齐降为 `suggested`。R5 两份旧记录（LEGACY_CONTRACT）
  精确配对：423 / 487 项检查精确配对 234 个，一致 193 个（82.5 %，与 Codex 自测的 82.48 % 相同），配对率 51.4 %，总一致率 42.4 %，
  通过对失败 5 对，P0/P1 分歧 5 处，建议配对 62 个。
- **§8 新旧记录：按它做。** 旧记录只读（`compare_reviews` 可读），`validate_intent(--candidates)` 与 `pack_review` 拒绝再发布
  手画电路的 intent；库内调用不受影响（不传候选时不校验）。
- **§7 文件级合并清单、§9 验证计划：** 候选层与 §3–§5 的文件均已落地；验证为全量测试、约定测试、账本检查、原型测试、
  KiCad 回放基准与变异门（M62–M72 新增，M46/M47 改守影响条目的 via 与判断不引数字限值），全部通过。


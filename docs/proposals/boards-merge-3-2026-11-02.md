# 合并步 3：真实板反复误报与漏问根因（2026-11-02）

本次处理题列第 1–8 项，实际去重为 **20 块板**。基线是 boards-program@dcd33fd；所有修改仅在 boards-merge3 工作树，未 push。SKILL.md、references/shared/、guideline_criteria.py、stress_check.py 与设计准则库原字节不变。

冷扫非 INFO 发现 **454 → 546**，原归因中能按同规则与实际位号/网络匹配的冷扫误报 **158 → 107**。总数增加主要是 **PRO-E02 +82** 个通道/器件提示与 **DEV-D02 +59** 个脚名差异提示；它们不是新增已证实硬件缺陷。已归因真缺陷 60 条全部仍可定位：9 条有同目标规则的冷扫发现，24 条有同规则逐对象计划，27 条只有相关器件计划与原始证据，不能称为自动检出。

## 复现与证据边界

- before：在修改前对全部 20 板执行原生 XML 重解析、冷扫、候选、决定、候选扫描和合并计划，记录退出码；原始结果保存在 ~/.cache/sr-boards/_merge3/before/。
- after：同链重跑，输出 ~/.cache/sr-boards/_merge3/after/；使用冻结 before intent 和电源参数，重绑当前原生输入指纹；资料审计只重用精确身份已有证据。候选边界重放只为检查覆盖，不确认产品需求或电气结论。
- Fastlogic 原 intent 有 note-only review_sources 条目，不满足结构要求；两侧均省略同样条目并保留 input-normalization.json。Batdat 的 NT1/NT2 旧 OTHER 占位声明因本次已能原生识别为铜跳接而退出派生输入，原声明与退出理由保留在 retired-native-copper-kind.json；物理连接未变。
- 20 份 lane findings、20 份原 intent、20 份 XML 的 SHA256 均与初始锁定相同；所有板 pin2net、nets、原生 pinname/pintype 与 original_value 全相同。R330 的有效分析值可以变为 unknown，原值仍保留。
- after 的 107 个匹配行中，106 行与 before 已匹配误报的诊断原文一致；另 1 行是同一 GND 输入节点列表缩短，仍对应 Inkplate 原 F040，未把新增 59 条脚名差异套入旧误报。
- 本表误报只计原归因可匹配行，不把新增提示自动判成真缺陷，也不声称剩余 107 行已经关闭。计划里的既有 GAP 补问与自动发现分开计数。同名 JSON 保存逐规则、逐对象与匹配行；完整日志留在指定缓存。

## 八项修法

1. **多通道 TVS**：按精确官方物理脚表把活线、公共返回与 NC 布线脚分开，每通道生成独立 PRO-E02，真实 USBLC6 直通端保留两端网络，浮置双端钳位按差分窗核对；工作窗、残压和能量仍由审查员按通道判断。
2. **已核脚表**：仅把完整有出处的官方脚义补到原生缺名脚，原生有名优先，冲突记录原生/官方/来源；连接图、候选和各清单上下文都携带这些资料，MOS G/D/S 与光耦 A/K/E/C 得以贯通。
3. **DNP 与铜**：NT 位号、NetTie 封装和测试焊盘的 PCB 铜不因不采购而消失；真实可拆 0 Ω 电阻仍受 DNP 控制，显式跳线断开仍有效，电源与信号路径使用同一身份判断。
4. **未知供电**：供电来源缺电压窗时应力预判保留 unknown 与 power_rails 依赖，接地不能推出 0 V/PASS；proposal_override 经派生、物化、剥离和读回保留，额定组不继承错误 PASS。
5. **数值**：明确单位的 C100nF/R10k 可解码，欧式 6,3V 读为 6.3 V；R330 保持标准 RKM 默认解释，但同板多数明确 R 前缀写法使其产生歧义时，保留两候选与出处并阻止数值推断，采购码本身不冒充厂商阻值证据。
6. **晶体与串阻接口**：接地 CASE/power_in 不构成有源晶振供电，串阻后沿至多三段、总计不超过 10 kΩ 的拟合路径收集真实 IC 端点，并优先显式 I/O 电源域，保留路径和未知条件。
7. **机械件与方向**：原生机械封装/身份及零电气脚不派 DEBUG、工业 DI 或空应力对象，TF/FPC 插座不因 K 前缀变继电器；MC14093B 精确型号用 onsemi 官方方向表作分析覆盖，原生数据与差异出处保留。
8. **磁件**：TRAFO 等原生身份即使使用 U 位号也按磁件处理，有官方绕组表时按表建侧，无表保持 unresolved，纯被动隔离对象不套数字默认态、速率或 CMTI 项。

补充两项直接来自 after 的边界修正：Pionix D9 所接以太网信号变压器不是功率开关证据，只有相关 SW/LX 或晶体管开关端证据才保留能量钳位窗；MP2 恢复 18 只 MOS 脚义后，共用 DC 母线电容改作共享输入电容引用，母线电压分压支路不能被三个桥臂各当作 RC 吸收，完整决定与合并链恢复。I²C 清单重放同时保留 power_rails 上下文。

## 逐板 before / after

“发现”为冷扫 FINDING/CANDIDATE 的合计，排除 INFO；“误报”为上述原归因匹配口径。计划误派项另见下表，不能从冷扫数字推断是否修好。

| 板 | 发现 before → after | 已归因误报 before → after |
|---|---:|---:|
| blkburn--zigbee | 2 → 7 | 0 → 0 |
| neumi--fastlogic | 70 → 68 | 12 → 8 |
| rapidanalysis--xerxes | 30 → 52 | 21 → 21 |
| mlab-modules--qfhmix01 | 21 → 20 | 18 → 14 |
| badgineer--mp2-esc | 2 → 24 | 1 → 1 |
| antmicro--jetson-nano-baseboard | 21 → 61 | 12 → 12 |
| antmicro--m2-smart-iot-module | 38 → 41 | 12 → 12 |
| moelashmawi--flyback-ac-dc-converter | 4 → 5 | 0 → 0 |
| newell--hv-flyback-converter | 3 → 3 | 1 → 1 |
| mlab-modules--usbi2c01 | 0 → 3 | 0 → 0 |
| danielmartensson--stm32-plc | 11 → 33 | 0 → 0 |
| mlab-modules--batdatunit01 | 12 → 16 | 2 → 2 |
| neotron-compute--neotron-pico | 42 → 21 | 27 → 3 |
| gorkemguven--12v-1a-isolated-flyback-smps | 4 → 1 | 2 → 0 |
| pionixpublic--reference-hardware | 69 → 81 | 1 → 1 |
| protocentral--protocentral_ads1293 | 0 → 2 | 0 → 0 |
| solderedelectronics--soldered-inkplate-6-motion-hardware-design | 79 → 74 | 17 → 12 |
| imike78--home-mini-v1-drop-in-pcb | 40 → 28 | 28 → 16 |
| abhishek-xi--isolated-flyback-converter | 3 → 3 | 2 → 2 |
| solderedelectronics--stepper-motor-driver-drv8825-board-hardware-design | 3 → 3 | 2 → 2 |
| **合计** | **454 → 546** | **158 → 107** |

### 根因的逐对象变化

| 对象/模式 | before | after |
|---|---|---|
| USBI2C D4 | 0 个通道项 | 3 个活线通道 |
| STM32-PLC D28 | 0 个通道项 | 2 个通道（全板 E02 0→22） |
| Jetson 10 颗阵列 | 0 个阵列通道；另有 3 个双端件 | 新增 36 个通道，全板 3→39 |
| Xerxes U7/U8 与 D6 | 0 个 E02；6 个错误 TRIP/NOTRIP 方向项 | 4+4+1 个 E02，相关 PRO-C02 不再派；未移除真实功率钳位 |
| Batdat U2 | 0 个通道项 | 3 个活线通道 |
| Pionix 7 颗 VERIFIED TVS | 自动 E02=0，只有 7 条手填 GAP | 自动 13 个通道，七颗均覆盖；原 GAP 仍单独列出 |
| MP2 / Gorkem Q2 / flyback U3 | 原生缺名阻断 G/D/S 或 E/C | 有出处的脚义、角色与输出网可解；U3 恢复 FEEDBACK-OPEN |
| Neotron NT901–NT912 | 铜被按采购 DNP 断开，24 条地址脚悬空 | 24 条相关假悬空消失；冷扫 42→21 |
| Home-mini DNP 测试铜 | 测试焊盘从图移除 | 保留铜端点；冷扫 40→28 |
| Abhishek C12/VCC、C13/SS | 0 V/PASS 并传到额定组 | result=null、calculation={}，依赖 /VIN 电压窗，PWR-C10 不给 PASS |
| Fastlogic 值 | C/R 前缀读不出；R330=0.33 Ω | 43 个 C 前缀可解；R9 保留 [0.33,330] Ω 歧义，原值/采购字段不改 |
| QFHMIX 电容额定 | 47uF/6,3V 被截成 3 V | 6.3 V，相关错误低耐压提示退出 |
| M2 Y1/Y2/Y4 | 接地壳脚导致漏 CLK-C01 | 三颗均有逐晶体 CLK-C01 |
| M2 FTDI/nRF | 仅直连端点，串阻后漏跨域对象 | R53/R71/R72/R73/R74 等路径带真实端点与 I/O 域生成 SIG-C08；不以核心电源差异代替 I/O 判据 |
| 安装孔/FD/卡座 | 假 DEBUG、工业 DI、继电器或空应力项 | Protocentral 只保留真实 TP1；Newell/Blkburn 安装孔退出；Stepper FD1 与 Inkplate FD1–4 退出 DEBUG；卡座按连接器 |
| Inkplate MC14093 U9 | 原生全脚 output（题述为 input，实际 XML 为 output） | 输出 3/4/10/11，电源 7/14，其余输入；10 个方向修正有原厂出处 |
| Newell 被动 TR1 | SIG-C17 默认态/速率/CMTI | 此项不派；连接和隔离资格仍审 |
| Gorkem U1 三绕组 | IC 全脚互通，错误并域 | 磁件阻断跨绕组短接；未知脚表不猜两侧 |

### 冷扫逐规则计数

| 规则 | before | after |
|---|---:|---:|
| DEV-A01 | 4 | 0 |
| DEV-D02 | 0 | 59 |
| DRV-A01 | 4 | 4 |
| DRV-A03 | 8 | 4 |
| NET-A01 | 161 | 143 |
| NET-A02 | 4 | 4 |
| NET-A06 | 47 | 42 |
| NET-A07 | 129 | 114 |
| PRO-A04 | 1 | 4 |
| PRO-E02 | 7 | 89 |
| PWR-A01 | 24 | 21 |
| PWR-A02 | 21 | 18 |
| PWR-A05 | 4 | 4 |
| RST-A01 | 12 | 12 |
| RST-A02 | 2 | 2 |
| RST-A03 | 4 | 4 |
| RST-A04 | 3 | 3 |
| SIG-A02 | 10 | 10 |
| SIG-A03 | 8 | 8 |
| SIG-A05 | 1 | 1 |

## 真缺陷保留

同名 JSON 列出全部 60 条原 true_defect 的 before/after 自动发现与计划 ID；这里列用户特别点名者。没有把规则提示当成已完成专家判定。

| 真缺陷 | after 的保留与定位 |
|---|---|
| flyback U1 VDD 接地、C10 开路、反馈电源断开 | PWR-A02.U1、NET-A01 的 C10 开路网、两条 +12V 的 PWR-A01 仍直接报；原生连接未改 |
| flyback TL431 A/K 短接 | 原 U2 两脚同网仍在，PWR-C15.FLYBACK 的 run/fault 对象及 DEV-D05.U2 可定位，须专家判断 |
| Fastlogic VCAP 无电容 | U6.49/.73 与两个 unconnected VCAP 网仍有单独 PWR-D02/PWR-C09 对象；未因值解析修复而给缺电容 PASS |
| Fastlogic W5500 RSVD 悬空 | U13.23 的原生开路与 DEV-D05.U13 保留，资料条款仍由专家核 |
| Batdat CLDO/VBUS 电容、EN 无偏置 | /CLDO 与 VBUS 的 PWR-C09 组、U16/U17 EN 的 RST-T04 对象仍在；PMID 电容不冒充 VBUS 直连电容 |
| Pionix U8 电平裕量、Y3 频率冲突 | DEV-C05.U8、CLK-C01.Y3 与原值/Field6 全保留 |
| M2 U7 脚对调 | DEV-D02 明确记录原生与官方脚名冲突，原始接地/复位网络未替换 |
| Neotron C1306 25 V | DEV-C01.C1306 与原始 10u/25V 保留；本次不改变 8–30V 设计条件或宣布合格 |

完整候选与合并链 after 成功 **18/20**。Jetson 仍有 IC15/IC4/T3/U1/U2/U5 未被原决定持有，Neotron 仍有 Q1001/Q1301/Q1302/Q201/U402 需显式 add/reject；保留失败退出码与冷扫合并 fallback，不用自动认领掩盖边界缺口。MP2 的新共享母线问题已修复，恢复完整链。

## 新增四个种子

| 类型 | 物理变异与契约 | 自动层/计划层结果 |
|---|---|---|
| D-ARRAY-TVS-LOW-VRWM | U7 精确兼容脚表的 5.5V TVS→3.3V TVS，合成正常窗 4.75–5.25V | 4 个通道 PRO-E02；自动目标仅表示取证提示，不等于越限判决 |
| D-OFFICIAL-MOS-GATE-OPEN | QA1 两侧均缺原生脚名，仅给完整官方 G/D/S；变异侧断开栅极 | 新 DRV-A03 自动目标 |
| D-OFFICIAL-OPTO-FEEDBACK-OPEN | EL817 A/K/E/C 表贯通，断开 R4 LED 供电 | FEEDBACK-OPEN 逐对象问题仍存在，自动目标不计命中 |
| D-UNKNOWN-SUPPLY-NO-PASS | C12 16V→4V，显式锁定装配，只让 VIN/VCC 窗未知；外部测试真值按 TI 指定条件 | 预判必须 unknown 且留依赖，不计自动检出 |

已用 dcd33fd 与当前代码对锁定装配的同一个 C12 种子直接复现：旧代码为 0 V/PASS，当前代码为 unknown 且装配缺口为空，因此不是由装配未核屏蔽错误。

最终 **262 位点、227 自动目标、0 运行错误**。原有 **258 位点全部保留、225 自动目标全部保留，原计划目标也无丢失**；compare 按位点检查，新增命中不能抵消旧位点丢失。TVS 的一个种子覆盖四通道，不能把它计成四个位点。来源 commit/许可证在 boards-merge3.json；本仓库不新增第三方整板原文件。

## 门禁、提交与回放约定

| 批次 | pytest | changed 变异（单位层） | 回放 |
|---|---:|---:|---:|
| 官方脚表贯通 | 2641 passed | 79 全杀 | 195/195 |
| TVS 通道 | 2646 passed | 77 全杀 | 195/195 |
| 未知供电/override | 2649 passed | 57 个保留变异全杀 | 195/195 |
| 铜连接/I²C 上下文 | 2652 passed | 70 全杀 | 195/195 |
| 磁件/被动隔离 | 2658 passed | 109 全杀 | 195/195 |
| 值解析 | 2670 passed | 105 全杀 | 195/195 |
| 机械件/方向/插座 | 2683 passed | 271 全杀（M1033 负例补验） | 195/195 |
| 晶体/串阻接口 | 2687 passed | 101 全杀（M1033 负例补验） | 195/195 |
| 最终补充/种子/共享母线 | 2695 passed | 51 全杀 | 195/195 |

所有门禁使用 Python 3.13、任务专用 TMPDIR、PYTHONDONTWRITEBYTECODE=1，以及 SR_ASG_SHARED_ROOT=/tmp/codex-work/boards-merge-1/asg-5e7c969 这一与前三步对应的只读历史 ASG 共用层快照；没有改共用层，也不声称核验了现装 ASG 的漂移版本。上述全量 pytest 均另有 3 skipped。单位层是 mutation README 的正式杀死门，合同层不冒充全杀。M251 因脚表上下文已全局贯通而退役，M403/M715 等保留原始运行并以有效锚点/负例补验；M1033 的原始 SURVIVED 如实保留，新增真正零电气脚 MCU 占位件负例后，在两个对应源码快照的干净基线均通过、变异均 KILLED。运行中发生的失败与中断日志不算通过证据。最终原生工作树逐批门禁为准；临时副本的源路径绑定失败记录不计成功门。

新约定 boards-merge3-v1 通过父 manifest 链保留 boards-merge2-v1、boards-merge3-copper-v1 与 boards-merge3-mechanical-v1 原字节：r03 DNP TP3/TP4 测试铜使 440→436；r02 卡座更正使 384→388，再因 X1 接地壳脚正确派 CLK-C01 使 388→389。变更行均对照原生 XML 与完整行差核对，未重写历史答案，也未把回放一致当电气结论。

检测汇总先执行 detection 默认完整命令，再以最终 seeded/typical/replay 结果生成 RESULTS.md；典型电路为 215 DETECTED、190 FIXED、14 KNOWN_FALSE_ALARM，无未归因新提示。check_ledger 必须 PASS；保护文件的基线字节差为 0。

## 未处理与不能推断的模式

- 次要项只完成 I²C 上下文；solarmini 的升压输入/输出方向需整流/反馈位置联合模型，add 的核心锚点需功能边界而非把全部成员当锚点，未做通用猜测。
- motor_driver 独立功能对象会牵涉共用类型与职责，本步禁止改共用层；没有通过本地私造类型绕过限制。稳压管正常限幅的工程窗语义仍需单独定义，不一律套门限关闭。
- 任意未知阵列没有完整物理脚表时仍保留器件/端口资料缺口；Gorkem U1 没有已核绕组脚表时只阻止错误 IC 全通，不编造主副边映射。
- 新的 59 条 DEV-D02 是字面脚名/功能名差异候选；部分已做严格有边界别名兼容，其他同义名称、极性后缀与编号功能仍需逐型号核，不能全局消音而漏掉 U7 脚交换。
- 光耦射随/集电极直连轨等输出模式仍沿既有模型产生上拉提示；新增 PRO-A04 需按实际输出模式归因，未把它们宣称为新真缺陷或已关闭误报。
- Jetson/Neotron 的决定缺口、其余已归因误报及动态/热/PCB/EMC/生产准出仍未关闭。本步是工具识别与派问改进，不是重新完成 20 板独立专家审查。

## 修改文件

完整清单（相对 dcd33fd，含本报告与台账）：

- docs/improvement-ledger.md
- docs/proposals/boards-merge-3-2026-11-02.json
- docs/proposals/boards-merge-3-2026-11-02.md
- evals/detection/RESULTS.md
- evals/kicad_replay_bench/README.md
- evals/kicad_replay_bench/revisions/boards-merge3-copper-v1/cases.json
- evals/kicad_replay_bench/revisions/boards-merge3-copper-v1/expected.json
- evals/kicad_replay_bench/revisions/boards-merge3-copper-v1/manifest.json
- evals/kicad_replay_bench/revisions/boards-merge3-copper-v1/sources.json
- evals/kicad_replay_bench/revisions/boards-merge3-mechanical-v1/cases.json
- evals/kicad_replay_bench/revisions/boards-merge3-mechanical-v1/expected.json
- evals/kicad_replay_bench/revisions/boards-merge3-mechanical-v1/manifest.json
- evals/kicad_replay_bench/revisions/boards-merge3-mechanical-v1/sources.json
- evals/kicad_replay_bench/revisions/boards-merge3-v1/cases.json
- evals/kicad_replay_bench/revisions/boards-merge3-v1/expected.json
- evals/kicad_replay_bench/revisions/boards-merge3-v1/manifest.json
- evals/kicad_replay_bench/revisions/boards-merge3-v1/sources.json
- evals/kicad_replay_bench/run.py
- evals/mutation/mutations.json
- evals/seeded_bench/README.md
- evals/seeded_bench/boards-merge3.json
- evals/seeded_bench/mutators.py
- evals/seeded_bench/run.py
- evals/typical_circuits/cases.json
- references/architecture.md
- scripts/board_intent.py
- scripts/checkers/isolation_sides.py
- scripts/checkers/netgraph.py
- scripts/checkers/passive_stress.py
- scripts/checkers/power_up.py
- scripts/checkers/powertree.py
- scripts/checkers/states.py
- scripts/circuit_candidates.py
- scripts/decoupling.py
- scripts/derive_rows.py
- scripts/i2c_topology.py
- scripts/interfaces.py
- scripts/lint.py
- scripts/parse_kicad.py
- scripts/part_words.py
- scripts/plan_circuits.py
- scripts/plan_review.py
- scripts/protective_clamps.py
- scripts/results_model.py
- scripts/solve_dividers.py
- scripts/tests/fixtures/interfaces-flyback-usb.json
- scripts/tests/test_boards_merge.py
- scripts/tests/test_boards_merge3_clamps.py
- scripts/tests/test_boards_merge3_copper.py
- scripts/tests/test_boards_merge3_interfaces.py
- scripts/tests/test_boards_merge3_magnetics.py
- scripts/tests/test_boards_merge3_mechanical.py
- scripts/tests/test_boards_merge3_pins.py
- scripts/tests/test_boards_merge3_seeds.py
- scripts/tests/test_boards_merge3_shared_bus.py
- scripts/tests/test_boards_merge3_stress.py
- scripts/tests/test_boards_merge3_values.py
- scripts/tests/test_interfaces.py
- scripts/tests/test_plan_review.py

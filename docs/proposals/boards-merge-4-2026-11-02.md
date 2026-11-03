# 合并步 4：86 块板跑完后仍剩的系统性误报与漏问（2026-11-02）

用户原话：把这86块板子上找到的问题，在规则库、ASG和SR技能中进行改进。

本步在 SR 分支 `boards-merge4` 上做（从 `boards-merge3` 5d19609 分出）。共用层（`references/shared/`、`scripts/guideline_criteria.py`、`scripts/stress_check.py`）、`SKILL.md` 和设计准则库条款都没有改。证据来自 `~/.cache/sr-boards/_summary/findings-all.json`（误报模式 1964 条、漏检 224 条），以及逐板的 findings。原始电路只放在只读缓存里，没有复制进仓库。

## 一、逐项修法

| # | 根因 | 修法 | 主要文件 | 提交 |
|---|---|---|---|---|
| 1 | BOM 里的 `1/16W`、`1/10W` 被读成 16 W、10 W，产生方向性错误的 PASS | 分数额定功率作为一个整体解析。只读到一半的分数（例如分子丢失）记 `power_unread`。BOM 功率读不出、值里也没有功率时，DEV-C01 的预判写 `calc.bom_power='unread'`，不给 PASS | `checkers/passive_stress.py` | edc0e76 |
| 2 | 名字像地的分压中点（VGND/GNDA）被当成 0 V，并被划为参考地 | 新增 `midpoint_ground`，同时满足下面三条才算中点：不接连接器；不接任何 IC 的电源、返回或地脚；既有大于 1 Ω 的电阻接到另一张地网，又有电阻接到非地网。中点不按 0 V 定界，判不出就保留电源依赖，`domains.ground_labels` 也不再把它当参考地（声明了零伏窗口的除外） | `checkers/passive_stress.py`、`checkers/domains.py` | e7e30c5 |
| 3 | 经 kΩ 电阻接到轨的偏置或上拉路径被报“无驱动” | 新增 `PowerTree.weak_source`：穿过一颗已装配、阻值可读的电阻（大于 1 Ω）追到有来源的网。PWR-A01/A02 改报 INFO“电源轨/电源脚经电阻弱驱动”，并写明 R 位号、阻值和来源 | `checkers/powertree.py`、`lint.py` | 71d25c4 |
| 4 | 多输出 PMIC（TPS6502x）的 VDCDCx/Lx/VLDO/VRTC，以及 TOPSwitch 的 DRAIN/CONTROL，没有端口语义 | `part_words.SUPPLY_PORT_RULES` 按型号脚表登记开关、输出和反馈端口，均附手册出处。电源追踪把输出端口当作来源；开关端口要经储能电感到达才算来源。每个输出逐一派 PWR-C04。输出端口接地时给 CANDIDATE | `part_words.py`、`checkers/powertree.py`、`plan_circuits.py`、`lint.py` | d458e0e |
| 5 | 隔离 DC/DC 模块（B0505S、PDQE 等）被当成稳压器，两侧地被合并 | `isolation_sides` 识别隔离模块身份，按脚名建输入侧和输出侧，两侧地不合并。-Vo 只在存在 0V/COM 脚时才算输出 | `checkers/isolation_sides.py` | 9e6201d |
| 6 | 双 MOS 的 G1/G2 被合成一个对象；MAX14850 按通道号而非侧别分 | `power_switch.channels` 按栅极序号把双 MOS 拆成通道，D/S 按序号对应，共漏 D12 归两个通道；无序号的脚名留缺口 `channel-pin-map`。开关对象 ID 带 `-CH<n>`。数字隔离器同时有 VCCA 和 VCCB 时按 A/B 分侧。补充提交里 MAX14850 按身份识别为隔离器，去耦候选组只取本侧返回 | `checkers/power_switch.py`、`checkers/isolation_sides.py`、`decoupling.py` | 2a5be87、105cde9 |
| 7 | NET-A01 不认原生 NC 标记；料号的 `/NC` 订货后缀被当成 DNP | NET-A01 只在两种情况下对原生 no-connect 单节点网降为 INFO：连接器或测试点触点；原生脚型为 output、bidirectional、tri_state、open_collector、open_emitter 或 no_connect。输入脚即使带 NC 标记，仍要问。解析时 `_not_part_number` 把料号里的 NC 后缀排除在 DNP 判断之外，DNP 仍只认 DNP 与 Populate 一类字段 | `lint.py`、`parse_kicad.py` | d853caf |
| 8 | `J_PACK+1` 和 `J_PACK-1` 规整后撞成同一个功能 ID；带 function_id 的框架成员为空 | `frame_slug` 把 `+` 转成 `-PLUS-`，转换可逆，不再碰撞。`bind_owned_rows` 按合并计划带来的 function_id 重建电路框架成员；FN- ID 指向不存在的框架时抛出内部错误，不再静默 | `checkers/planutil.py`、`plan_review.py` | 2516f4c |

第 9 项（次要模式）本步没有做，原因见第五节。

## 二、点名板 before/after

做法沿用合并步 1 的复现链：原生 XML 重解析 → 冷扫 → 候选 → 原决定 → 候选扫描 → 合并计划。before 用 5d19609，after 用最终代码，两边使用同一份 BOM 行和原 intent。输出在 `~/.cache/sr-boards/_merge4/{before,after}/<id>/`，对照数据在 `compare-before-after.json`。表中“误报”指能匹配到已归因误报模式的冷扫非 INFO 发现。

| 板 | 冷扫非 INFO before→after | 已归因误报 before→after | 计划检查项 before→after | 真缺陷 |
|---|---|---|---|---|
| a2r-lab--crazyflie_fpga_deck | 62→38 | 48→24 | 328→308 | 2/2 |
| antmicro--hdmi-mipi-bridge | 126→110 | 18→2 | 665→649 | 3/3 |
| anthilla--anthc | 53→49 | 8→4 | 636→636 | 7/7 |
| loudifier--openrefmic | 12→10 | 2→1 | 117→114 | 1/1 |
| spirit532--studio_mic | 11→9 | 6→4 | 121→118 | 1/1 |
| antmicro--cm4-baseboard | 49→47 | 20→18 | 1501→1499 | 0/0 |
| antmicro--kria-k26-devboard | 105→104 | 9→8 | 1645→1644 | 1/1 |
| sparkfun--sparkfun_gnssdo | 69→68 | 22→21 | 776→776 | 2/2 |
| tinkerforge--evse-v2-bricklet | 21→20 | 3→2 | 392→391 | 1/1 |
| antmicro--scalenode-cm4-baseboard | 97→96 | 84→83 | 740→739 | 2/2 |
| motordynamicslab--leviathanext | 25→25 | 7→7 | 559→575 | 2/2 |
| solderedelectronics--1s-li-ion-battery-protection | 4→5 | 0→0 | 86→89 | 0/0 |
| 其余 10 块（pslab、stm32h7-hdmi、xerxes、nabucasa-yellow、mp2-esc、evse-bricklet、12v-5a-flyback、flyback-ac-dc、rs485-spy、bms-can-bus） | 不变 | 不变 | 不变 | 全部保留 |
| **合计 22 块** | **1020→967** | **327→274** | — | **54/54** |

按规则统计（冷扫非 INFO）：

| 规则 | before→after |
|---|---|
| NET-A01 | 258→237 |
| PWR-A02 | 92→66 |
| PWR-A01 | 37→31 |
| PWR-A03 | 6→5 |
| DRV-A03 | 11→12 |

DRV-A03 增加 1 条，是 1S 保护板 FS8205A 的第二个通道被拆出后，该通道独立报出栅极问题。leviathan 的 DRV-C02 从 14 行增加到 22 行，也是双 MOS 按通道派项的结果，属于该问的项，不是误报。

全量计划中未绑定的功能检查项从 413 降到 0。逐项落点：

| 项 | 板 | 结果 |
|---|---|---|
| 1 | pslab | 16 W 下限上的 DEV-C01 PASS 从 22 条降到 0。其中 21 条按 0.0625 W 重新预判为 PASS，2 条读不全的不给 PASS |
| 2 | openrefmic | R21 从“PASS(0V)”变为 unknown，并带 AMP_VDD 依赖 |
| 4 | crazyflie | TPS65023 的 U2.2/9/33/16 每个输出各有一行 PWR-C04 |
| 5 | evse-v2 | +12V 的 PWR-A01 消失 |
| 5 | scalenode | 新增 PDQE 的 ISOLATION 两侧候选 |

用原 reviewer 决定重放时，结果有三处变化：

- crazyflie：PMIC 电容现在自动归 PMIC 所有，原决定需要重新对账。
- scalenode：新增的隔离候选需要原决定重新对账。
- anthc：原决定的重放由失败变为成功。

前两处是新模型产生的合法候选，需要审查员补决定，不是回退。

## 三、真缺陷保留

点名板上已归因的 54 条真缺陷，after 全部仍被报出，或能逐器件定位到计划行。原来能自动检出的 14 条，after 仍全部自动检出。flyback-ac-dc 的 B01（PWR-A02）和 B02（NET-A01）都保留，说明弱驱动与 NC 两项修改没有吞掉真正的无驱动和悬空。

## 四、新增种子

种子 4 个，来源登记在 `evals/seeded_bench/boards-merge4.json`：

| 种子 | 对应项 | 位点 | 判据 |
|---|---|---|---|
| D-FRACTION-POWER-NO-PASS | 第 1 项 | pslab R29（47 Ω，合成 5 V 窗；额定值 2W 改为 1/16W） | 新增 guard `guard_no_pass` |
| D-MIDPOINT-GROUND-NO-PASS | 第 2 项 | openrefmic R20/R21 中点 VGND，配对基线命名为 VMID | `guard_no_proposal_pass` |
| D-BIAS-FEED-REMOVED | 第 3 项 | gnssdo PCA9306 U19 的 200k 偏置 R63 被删去 | 自动 PWR-A02 |
| D-NC-FLAG-REMOVED | 第 7 项 | hdmi-mipi J6.38 的原生 NC 标记被去掉 | 自动 NET-A01 |

seeded bench 对照（`--offline --boards-cache ~/.cache/sr-boards --compare`）：

| 代码 | 位点 | 自动检出 | guard 错误 |
|---|---|---|---|
| 5d19609 加上新种子 | 266 | 227 | 2（两个 no-PASS guard 失败，即修复前确有 PASS 或 0 V 预判） |
| 最终代码 | 266 | 229 | 0 |

旧的 262 个位点逐点保留，没有位点退化。

## 五、没有处理的模式

| 模式 | 规模 | 为什么没做 |
|---|---|---|
| scalenode CM4 板对板连接器上的 NET-A01 | 80 条 | 未接的 CM4 信号脚没有原生 NC 标记，判定需要模块级的允许悬空脚表，属于第 9 项的器件条款库 |
| nabucasa M.2 插座 NC 的 NET-A07 | 36 条 | 网表里连接器身份丢失（被识别成非连接器），需要先改器件类别识别 |
| xerxes 模块脚 NET-A07 | — | 同上 |
| crazyflie FPGA 未用 bank 的 VCCO 接地 | — | 需要 FPGA bank 级脚表与手册条款 |
| pslab BJT 和反相 buck 的来源追踪 | — | 需要分立变换级拓扑，超出本步的单电阻弱驱动范围 |
| gnssdo 带点号的位号 `A.1` | — | 属于解析层位号语法，影响面需单独评估 |
| TOPSwitch 的 DRV-C01/PWR-D03/PWR-C06/PRO-C01 | — | 本步只建端口语义，没有新增逐端口检查项。增加检查项属于规则库范围，需另行确认 |
| J_PACK± 在当前回放里被识别为测试点类 | — | 碰撞只由单元测试覆盖，没有板级重现 |
| 第 9 项各次要模式 | 各 1–2 块板 | I²C 上拉源、BGA 枚举、“Microprocessor Crystal”标题、电池座极性、器件级允许悬空条款、SPI 别名、BOOT 脚、DIN 封装名、安装孔等，彼此独立、证据少，本步没有把握逐项做对，留待下一步 |

## 六、门禁

每次提交都单独跑了门禁：pytest 全绿；`mutation/run.py --changed 5d19609 --tier unit` 全杀（逐提交 35、47、89、193、199、206、214、256、276，最终 292，含种子的 M1130/M1131）；pytest 最终 2730 passed、1 skipped；KiCad 回放 195/195。

回放新建约定 `boards-merge4-v1`，冻结答案有三处变化：

- rf1 的 plan.checks_total 368→367，带 frames 的用例 393→392。
- r02 的 plan.checks_total 389→391。
- rf1 的 `decoupling.group_gaps` 随本侧返回而变。

`evals/typical_circuits` 结果为 216 DETECTED / 197 FIXED / 7 KNOWN：FS8205A 开路通道新增期望 DRV-A03；CH344Q 的 7 条 NET-A01 从“已知”移到“已修”。

变异编号 M1100–M1131，其中 M1109 与其他变异等价，已删去。

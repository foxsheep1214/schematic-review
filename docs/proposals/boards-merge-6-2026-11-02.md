# 合并步 6：工业 I/O 校准板的 11 条误报与 3 条漏问（2026-11-02）

分支 `boards-merge6`，从 main `e3be29e` 分出。共用层（`references/shared/`、`scripts/guideline_criteria.py`、`scripts/stress_check.py`）、`SKILL.md` 和设计准则库条款都没有改，`git diff e3be29e` 在这些路径上为空。

before 用 `e3be29e` 的快照 `~/.cache/sr-boards/_merge6/sut-before`，after 用本分支终版。板级输出都在 `~/.cache/sr-boards/_merge6/`：

- `before/`、`after/`：78 块板
- `calib-before/`、`calib-after/`：校准板

校准板的输入从只读的设计记录复制到 `~/.cache/sr-boards/calibration--industrial-io-rs485-can/`。设计记录目录里没有写入任何文件。

## 一、误报（11 条，修 10 条）

| 条 | 规则 | 根因 | 修法 | commit |
|---|---|---|---|---|
| F04 | DEV-D02 | 官方脚名带封装注释 `VCC (TAB)`，与原生 `VCC` 逐字比较 | 比较前去掉尾部的括号封装注释（TAB/EP/PAD/DAP/SLUG）；功能不同的仍报 | 8d1c7ec |
| F13 | NET-A07 | SN65HVS883 的 DB0/DB1 去抖选择脚按手册可悬空 | 精确型号许可，出处 SLASEE6 p3/p5，降为 INFO | 6505fd8 |
| F14 | RST-A02 | ISO644x 高有效 EN 接本侧电源，被当成随电源建立的使能 | 只放过数字隔离器、名字是 EN/ENx/VEx、与同侧供电脚同网的；低有效、跨侧、非隔离器照报 | ad1b89f |
| F15 | RST-A03 | LM74930 EN 直连输入，但它另有接了分压的 UVLO 脚 | 器件另有 UVLO 脚且该脚接分压时，冷扫与规则实例都不报 RST-A03 | 2bde9dd |
| F16 | DEV-Q01 | 标题 "Surge Protection Device" 没认成 TVS | tvs 线索加 `surgeprotectiondevice`；同时命中压敏电阻时仍判为压敏 | 488fc8b |
| F17 | DEV-Q01 | "Resettable Fuses" 的 PPTC 因含 efuse 被判为负载开关 | efuse 按整词读 | 3142eba |
| F18 | DEV-Q01 | 高边智能功率开关（high-side smart power SSR）没认成负载开关 | load_switch 加 `highsidesmartpower` 线索；PhotoMOS 仍是继电器 | 293562d |
| F19 | 候选 | ① 输入保护候选把连接器所有脚的分支都收进来，包括 CAN 端接、DI 通道、机壳 Y 电容；② EN 接本器件电源也出 STARTUP 链 | ① 只留带电的脚分支：脚网是电源，或走到储能电容、截止网、功率级锚、隔离屏障或整流/NTC/压敏；同一连接器上相通的分支合并判断。② 起动脚接本器件供电时不成链 | 4cb027a |
| F20 | PRO-C07、PWR-C23 | 保持类电路（串联二极管加储能）被套上 eFuse 与双源切换 | `POWER_PROTECTION` 按成员裁剪：没有通路开关或带 ILIM/IMON/DVDT 脚的 IC 时不问 PRO-C07；没有第二路电源（第二个连接器、阴极汇合的两只二极管、两颗通路开关）时不问 PWR-C23 | 7a75065 |
| F21 | DEV-C01、DEV-C03 | MCU 的 BOOT0 下拉成了无主电阻 | BOOT 下拉并入该 MCU 的复位链 `STARTUP-<mcu>.NRST`，在 RST-E02 上按复位采样问；没有复位链时单独成 `STARTUP-<mcu>.BOOT`；PB2/BOOT1 这类多功能脚也出 strap 行 | 2a5f884 |
| F05 | PRO-E02 | 见下 | **未修** | — |

**F05 不做**。findings 提的修法是“intent.devices 已给 TVS 参数时直接比较并关闭候选”。intent 现在没有结构化的 TVS 参数字段（VRWM、VC、IPP），要做就得：

- 改 intent 格式并升版本；
- 让工具凭审查者自己填的数字关闭一条 E 规则。

这两点都越过了“E 规则由审查者判定”的边界。所以继续由审查者在结果里关闭，是否加这个字段请人定。

**跟进 F16（3b71e45）**。F16 把 TVS3300 认成 TVS 之后，原生脚名路径把三只裸 K 脚（4/5/6）各算成一个通道，PRO-E02 从 1 行变成 3 行。改为同一网上的裸 K 脚合成一个通道；不同网的裸 K（NUP2105L 的 CAN_H/CAN_L）仍分开。中间版本跑典型电路基准时，bms-c1 的 D8 两通道曾被合并而丢失，暴露了这个问题，已加回归测试。

## 二、漏问（3 条，全修）

| 条 | 规则 | 修法 | commit |
|---|---|---|---|
| M01 | PWR-C27、PWR-C18、PWR-T05 | 输入入口满足下面两点时，另出跨电路的 `DC_24V-<连接器>` 候选，引用输入保护的成员；`DC_24V` 默认态为 startup/run/fault：<br>① 分支里有保险和钳位（TVS 或压敏）；<br>② 有确认过的需求声明 input_voltage 窗（上限 24–36 V、下限 ≤24 V），或连接器/网名含 24V。<br>只有名字、没有保险加钳位的不出候选 | 9ae0ee4 |
| M02 | INDUSTRIAL_DI 线索 | 网名线索把层次路径的 `/` 也当词边界（`/07_DI/DI1`） | b5469d2 |
| M03 | CLK-C01 | 无源晶体两端（直接或经一颗串联电阻）都接到同一颗 IC 的振荡脚时，出 `CLOCK-<晶体>` 候选，成员是晶体、两端负载电容和串联电阻；接到两颗 IC 的交给 CLK-A02 | 29e482a |

**种子（d7d6ad7）**。`boards-merge6.json` 登记校准板（license internal），新增 2 个位点：

| 种子 | 位点 | 变异 | 目标规则 | 自动检出 |
|---|---|---|---|---|
| `D-XTAL-LOAD` | Y301/C308/C309 | 负载电容改 1 µF，CL 记 12 pF | — | 1/1 |
| `D-BOOT0-FLOAT` | MCU BOOT0 | 删去 R301 下拉 | RST-E02、NET-A01 | 1/1 |

## 三、校准板 before/after

详见 `evals/boards/calibration--industrial-io-rs485-can/round-report.md`。

| 指标 | before | after |
|---|---:|---:|
| 冷扫非 INFO | 27 | 19 |
| 合并非 INFO | 25 | 19 |
| 计划检查项 | 837 | 808 |

- 10 条已修误报和 3 条漏问在终版上都不再报。F15 只剩 U202 的 2 行 INFO，它没有独立的 UVLO 脚。
- 真缺陷：F01 照报；F03 剩的那一行就是 F04 那行，改版网表上已经没有别的冲突。

## 四、78 块板 before/after

| 项 | before | after |
|---|---:|---:|
| 冷扫非 INFO 行 | 2271 | 2271 |
| 其中匹配已归因误报 | 543 | 543 |
| 冷扫合并计划检查项 | 37547 | 37572（+25） |
| 真缺陷仍能定位 | 172/172 | 172/172 |
| 真缺陷自动报出 | 37 | 37 |

- **计划 +25 全是 RST-E02**：多功能 BOOT 脚新出的 strap 行，分布在 9 块板，例如 switch-v4 +6、gnssdo +5、rdimm +4。
- **候选**：
  - 去掉 18 个假的 POWER_PROTECTION/STARTUP 候选，其中包括 stm32-plc 的 J1/J14/J15：它们是 DI/AI 信号通道上的 PTC 加齐纳，不是电源入口；
  - 新增 31 个 CLOCK 或 STARTUP.BOOT 候选；
  - 公开板上没有新出 DC_24V。
- **6 块板的已存决定对不上新候选**：anthc、sdi-mipi-bridge、klippertoolboard、usb2_hub、stm32-plc、poepico。
  - 在这 6 块板上，候选扫描以“候选没有决定”或“器件已被候选占用”拒绝，after 的完整合并计划从 25 块降到 19 块。
  - 其中 sdi-mipi-bridge、usb2_hub、poepico 的审查员原先手工 add 的 CLOCK 电路，成员和新候选完全一致。
  - 这是缓存里的决定过时了，不是退化。按 README，重审时重新决定即可。
- **两块板前后都失败，与本步无关**：mlab batdatunit01、neumi fastlogic，cold=1、merge=2。

## 五、门禁

- pytest 2783 通过，未设 `SR_ASG_SHARED_ROOT`。
- `mutation/run.py --changed e3be29e --tier unit`：见台账，新增 M1300–M1334 共 35 条，全部杀死。
- kicad_replay 195/195。
- seeded 274 位点、自动 231、0 错误，`--compare` 对 before 没有退化。
- `evals/detection/run.py` 已更新 RESULTS.md。
- check_ledger PASS。
- 不 push。
- 字节棘轮 ① 171683、② 158590，每次上调都在 `test_reading_path.py` 写了理由。

## 六、没做的，需人定

1. **F05**：要不要在 intent 里加结构化的 TVS 参数字段，并让工具据此关闭 PRO-E02。这要改格式，并越过“E 规则由审查者判”的边界。
2. **HOLD_UP 电路类型**：保持类电路现在只能在 POWER_PROTECTION 里按成员裁剪。要加独立类型，得改共用词表。
3. **其他电路类型的网名线索**：它们都还不把 `/` 当词边界，本步只改了 INDUSTRIAL_DI（M02）。逐条放开会改变 78 块板上的名称线索，需要先评估。
4. **F11**（needs_human，有 checker 修法）：穿过串联电阻找被保护的 IC 脚（SN65HVS883 IPx），按电阻压降比较。这是新的检查能力，不在本步 14 条之内。
5. **信号通道保护**：DI/AI 通道上的 PTC 加齐纳不再归入 POWER_PROTECTION，器件级检查行照旧。要不要另立“信号端口保护”候选，请人定。

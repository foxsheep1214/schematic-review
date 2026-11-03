# 合并步 5：两块未归因板、224 条漏问核对、抽查反馈、次要模式（2026-11-02）

分支 `boards-merge5`，从 main `1cd885b` 分出。共用层（`references/shared/`、`scripts/guideline_criteria.py`、`scripts/stress_check.py`）、`SKILL.md` 和设计准则库条款都没有改。before 是 `1cd885b` 的快照 `~/.cache/sr-boards/_merge5/sut-before`，after 是本分支终版。板级输出都在 `~/.cache/sr-boards/_merge5/`，其中 `before/`、`after/` 各 78 块板，`newboards/` 是两块新板。

## 一、两块未归因板（commit e113761）

| 板 | 计划项 | 归因 | 真缺陷 | 误报 | 知识缺口 | 需人判 | 漏问 |
|---|---:|---:|---:|---:|---:|---:|---|
| scottbez1--faderbuddy（lane-1） | 242 | 15 | 0 | 7 | 2 | 6 | RST-T04、SIG-C08、PRO-C05 |
| the-flame-trench--singularity（lane-4） | 612 | 17 | 1 | 10 | 3 | 3 | CLK-D03 |

- **faderbuddy**：误报集中在两处：
  - DRV8837 电机驱动被当成稳压器，按 POWER_CONVERTER 套了 PWR-C04 和 PWR-C14；
  - "有 ADC"触发了 ANA-C05、ANA-D01。

  H 桥复位安全态（RST-T04）自动 0 行，本步已落成种子。F01（安装孔进 DEBUG）已被前几步修掉。
- **singularity**：唯一的真缺陷是 F11（CLK-D01，P1，证据 B）：TCXO X2 输出 0.8 Vpp 削顶正弦，直流耦合进 TMS570 的 OSCIN；SPNS192B p62 要求该脚"toggling 0 V to 3.3 V"。误报主要来自：
  - CR1220 电池座和 CeraCharge 电池没认成电源（本步 4b 已修）；
  - 隔离/多轨 PMIC 的域划分。
- 缓存补件只在缓存里，没有进仓库：singularity 的 `review/intent.json` 补了 `device_kinds`（逐页逐字摘引手册标题）和 16 条候选决定，`datasheet-resolution.json`、`datasheet-audit.json` 重建。

## 二、224 条漏问核对（commit 5c969b3）

在 before 上重跑每块板的冷扫和合并计划，逐条判定。判定口径：审查员 rule_gaps 补出的 `GAP-` 行不算"已报出"。逐条结果见 `boards-merge-5-2026-11-02.json`。

| 准则 | 规则 | 漏问 | 现已报出 | 仍漏 | 需人判 | 新种子 |
|---|---|---:|---:|---:|---:|---:|
| G04-010 | RST-T04 | 28 | 0 | 27 | 1 | 1 |
| G05-019 | PRO-C04 | 26 | 18 | 3 | 5 | 0 |
| G03-003 | PWR-C04 | 18 | 4 | 9 | 5 | 0 |
| G04-054 | ANA-C01、ANA-C03 | 18 | 7 | 8 | 3 | 1 |
| G03-021 | PWR-D03 | 15 | 2 | 8 | 5 | 1 |
| G04-040 | DOC-D01、PRO-D02 | 14 | 0 | 13 | 1 | 2 |
| G05-030 | PRO-E02 | 12 | 9 | 1 | 2 | 0 |
| G04-007 | PRO-D04、SIG-C08 | 8 | 5 | 0 | 3 | 0 |
| G03-018 | PWR-C06 | 7 | 0 | 5 | 2 | 0 |
| G04-009 | SIG-C08 | 6 | 5 | 0 | 1 | 0 |
| G04-078 | CLK-C01 | 6 | 6 | 0 | 0 | 0 |
| G05-025 | PRO-C05 | 6 | 2 | 4 | 0 | 0 |
| G05-031 | PRO-E02 | 6 | 3 | 0 | 3 | 0 |
| G01-029 | PWR-C13、SIG-C05 | 4 | 0 | 3 | 1 | 0 |
| G04-041 | ANA-C01 | 4 | 1 | 2 | 1 | 0 |
| G05-054 | PRO-D04、PWR-T05 | 4 | 2 | 1 | 1 | 0 |
| G05-087 | PWR-T05 | 4 | 0 | 4 | 0 | 1 |
| G03-016 | DRV-C02 | 3 | 2 | 0 | 1 | 0 |
| G03-028 | PWR-C24 | 3 | 1 | 1 | 1 | 0 |
| G03-032 | DOC-D01、PWR-C05 | 3 | 0 | 2 | 1 | 0 |
| G04-005 | SIG-C08 | 3 | 3 | 0 | 0 | 0 |
| 其余 21 条准则 | — | 21 | 8 | 12 | 5 | 0 |
| **合计** | | **224** | **79** | **103** | **42** | **6** |

"其余 21 条准则"每条只有 1–2 条漏问，逐条明细在 JSON 里。

新种子 6 个，登记在 `evals/seeded_bench/boards-merge5.json`，变异编号 M1200–M1205：

| 种子 | 板 | 植入 |
|---|---|---|
| D-HBRIDGE-RESET-UNSAFE | faderbuddy U2 | IN2 拉离安全态 |
| D-ISO-BRIDGE | pmod_rs485 | GND↔/GND3 加 0R |
| D-ISO-BRIDGE | 12v-1a flyback | GND↔/E 加 0R |
| D-MCU-ADC-DIVIDER | satya R18 | 10K→100K |
| D-REVERSE-PMOS-DS | leviathan Q1 | D/S 对调 |
| D-LDO-STARTUP-COVERAGE | soil-sensor C6 | →1000 µF |

这 6 个位点当前自动检出都是 0，作为下一步的靶子。ADM2582E 那一处只侧报 PWR-A03，原因是 PRO-A05 的型号表里没有隔离 RS-485 收发器。

after 终版重跑同一批漏问，结果仍是 79 / 103 / 42。本步的修改针对抽查反馈和误报模式，没有覆盖这些漏问。仍漏的 103 条里，RST-T04（27 条）和 DOC-D01/PRO-D02（13 条）最多，应作为下一步的重点。

## 三、抽查反馈三条（commit 8b2f7b9）

| 项 | 修法 | before → after |
|---|---|---|
| (a) 文档/订货一致性定级 | `validate_review.doc_consistency_errors`：一条 DEFECT 若只挂 DEV-D01/D02/D04 或 DOC-*，证据里必须写"无电气后果"（此时严重度只能是 P3），或写明"电气后果"（保持原档）；两者都没写就报错。`references/verdicts-and-release.md` 加"文档/订货一致性怎么定级"一节 | 以前不检查；现在缺这句的发现会被拒收 |
| (b) 网名推定电压 | `passive_stress`：电压窗口只由网名推出（min = max = 网名电压，且没有 requirement）时，记 `rail_basis: 按网名推定`，不给 PASS，并加注。检查器版本 5→6 | 78 块板的计划里，带"按网名推定"的行 0 → 697（13 块板） |
| (c) SIG-T04 门禁与晶体资料 | `review_functions`：只有连接追踪（方法 T）的功能，引用了网表事实加已定位的官方脚表即算有据，不必再引数值条款。`plan_circuits.crystal_data_gaps`：Value 和字段里没有频率、或没有 CL（也查不到订货码）的晶体，CLK-C01 行置 `WAITING_EVIDENCE` 并要资料。回归测试见 `test_boards_merge5_spotcheck.py`（7 条） | CLK-C01 行要晶体资料的 0 → 25 |

## 四、次要模式（合并步 4 第 9 项）

每项一个 commit，测试都在 `scripts/tests/test_boards_merge5_minor.py`。

| 项 | commit | 修法 | 板上效果（before → after） | 变异 |
|---|---|---|---|---|
| 4a 器件级允许悬空 | 1fbb7fc | `unused_input_permission` 加两条：TPS54202 EN（p3 脚表、p9 §7.3 "Float the EN pin to enable"，型号也认 Value，例如 TPS54308 符号配 TPS54202 值）；TMC2209(-LA) VREF（Rev1.08 p53/p79）。CH340 未用 I/O 以前已经有 | klippertoolboard NET-A07 2→0、NET-A06 1→0、RST-A04 2→0 | M1213–M1214 |
| 4b 电池/电池座作电源 | def80c9 | `CELL_RE`：BATT、Li-Ion、LiPo、CeraCharge、mAh/µAh、纽扣电池型号 CR1216…CR2477、"电池"。只在 ≤3 脚、位号不是 U/M/IC/J/P/CN/TP/BT/B/R 时生效。不用 `CR\d{4}`，因为它会把 Bourns CR0402 贴片电阻当成电池 | 新认出的有 singularity C25、K2，gnss K2、jetson-nano BAT1、copperpilot BAT1、cellkeeper Cell1–3、rtc K19；singularity 的 PWR-A02 消失 | M1215–M1216、M1225–M1226 |
| 4c BOOT 自举脚 | 64e2a01 | `bootstrap_cap_pin`：BOOT 网上只有电容，且电容另一端接本片的另一个脚（SW/PH/LX）时，判为自举供电，不派 RST-E02 | RST-E02 全量 114→103（tpa3116、piccante、bondus U3、poe-usb-c、stm32h7、yellow 等） | M1217–M1218 |
| 4d PoE 中心抽头 | 5c7ca9e | 同一器件上 `V<n>+`/`V<n>-` 两脚分别正好落在这对网上时，不当差分对。PoE 中心抽头极性不定，后接整流桥 | poepico SIG-E02、SIG-T03 各 6→4（ETH/USB 仍在） | M1219 |
| 4e SPI 的 SDA/SCL 别名 | a16d50b | `i2c_topology.spi_wired`：双模脚名（SDI/SDIO/SCLK…）所在器件的片选由别的器件驱动、且不接轨时，按 SPI 处理，不出 I²C 名称线索。依据 ADXL345 Rev0 p8 "In SPI mode, the CS pin is controlled by the bus master" | klippertoolboard SIG-C01 4→0 | M1220–M1221 |
| 4f 未用 I2S 时钟 | 3306947 | `_database_blobs`：KiCad 自动命名的 `unconnected-(…)` 单脚网不参与功能电路识别。有名字的单脚网照旧参与，REQ-A02 的近似反例合约不变 | tpa3116 的 REQ-Q07.SPI、REQ-Q07.CLOCK 消失；全量 REQ-Q07 588→568 | M1222–M1223 |
| 4g "Microprocessor Crystal" | 85e8045 | `datasheet_kinds.cues`：标题里 microprocessor/microcontroller 紧跟 crystal 时，不推出 mcu | sdi-mipi Y1 的 KIND_CONFLICT 在 before 已是 0 行（前几步的类别判定已绕开），这里补上手册标题这一层 | M1224 |

after 与 before 相比，78 块板合计：
- 冷扫非 INFO 2281→2275（-6）；
- 计划项 40415→40344（-71）；
- 归因真缺陷所在的规则行没有减少（miss_check 的已报出数保持 79）。

### 没做的，及原因

| 模式 | 原因 |
|---|---|
| 带点位号 `A.1`（gnssdo） | 节点 `ref.pin` 按第一个点拆位号，散布在 32 个文件的 163 处。要改成按已知位号最长前缀解析，属于读入层语法的统一改造，影响面需要单独评估，本步没有把握 |
| CM4 / M.2 允许悬空脚表 | 缓存里有 CM4 手册，但要逐脚摘出"可悬空"条款，涉及几百个脚、跨多章；M.2 那一处还要先修连接器身份识别。一次做不全就会留下"部分脚有据"的假确定 |
| TMC2209 DECAY / DRV8825 DECAY | TMC2209 没有 DECAY 脚；DRV8825 在缓存里没有手册，按规定不凭记忆写条款 |
| 升压方向（solarmini PV+） | 需要按 LX/VOUT 脚义加整流路径判定 buck/boost 的输入和输出，改的是 PowerTree 的方向推断，影响所有变换级，不是单点识别 |
| 3 脚 CAN TVS、稳压管正常限幅 | 86 块板的归因里没有找到能复现的实例，没有证据不做 |
| DIN965/DIN0309/DIN0207、安装孔/FD/Logo | 前几步已修：DIN 封装名在 `_database_blobs` 里剥掉，机械件不进识别；before 上已是 0 行，无需再改 |

## 五、门禁

- pytest：2754 passed（含新增种子测试 6 条、抽查测试 7 条、次要模式测试 10 条）。`test_guideline_criteria.py::test_asg_holds_the_same_shared_layer` 不设环境变量时失败，原因是 ASG main（162a38e）已把共用层升到 1.7.1，而本分支不许动共用层。门禁一律设 `SR_ASG_SHARED_ROOT` 指向 ASG b3df8f8（1.7.0）的副本运行，合并前需要先把共用层同步到 1.7.1。
- `test_reading_path.py` 的 ④ 字节棘轮：124 000 → 124 430，原因是 `verdicts-and-release.md` 新增了定级小节。
- mutation：
  - item 3：`--changed 1cd885b` 321 条全杀。M44 因 `review_functions.py` 改写而失配，已按新源码更新 old/new 后杀掉；
  - 次要模式：每个 commit 前只跑新增变异，全杀；
  - 终版：`--changed 1cd885b` 共 391 条（27 个文件），全部杀掉（`~/.cache/sr-boards/_merge5/mut-final.log`）。
- kicad_replay_bench：每个 commit 都是 195/195，冻结答案不变，没有新建约定。
- seeded_bench：item 2 为 272 位点、自动 229、0 错误；item 3 对比 item 2 没有退化；终版对比 item 3 仍是 272 位点、自动 229、0 错误，逐位点没有退化（`seeded-final.log`）。
- check_ledger：PASS。

## 六、缓存侧改动（不在仓库里）

- `solderedelectronics--gnss-gps-l86-m33-breakout-hardware-design/review/intent.json`：删掉 K2 的 `{kind: connector, reason: …}`。4b 之后分类器能认出 K2 是电池，而带 reason 的声明只给认不出的器件用，不删 SR 会拒收这份 intent。原件备份为 `intent-before-merge5-battery.json`。
- singularity 的审查输入：见第一节。

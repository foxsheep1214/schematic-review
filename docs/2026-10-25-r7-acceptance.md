# R7 验收：四份独立首审的对比（2026-10-25）

SR 提交 660f790（审查期间没有改动）。板子仍是 ASG-20261023-100W-PD-R6；四位审查员互不可见，独立性规则同 R6。
用户要求（2026-10-25）："提交完之后，再重新分法4个agent（两个sol6.1 medium + 两个opus5.5 medium），对R6的100W PD电路版进行审查，判断改进以后SR的能力。"
与 R6 的不同：Codex 两路这次按用户要求跑 medium（R6 是 high）；任务书把 SR缺陷.md 放到了工作目录（R6 §六 C）；
两路 Claude 在 ③ 中途因会话额度中断，额度恢复后从各自工作目录的现有文件续做（计划没有重生成，功能框架不变）。

| 记录 | 模型 | 结果 | 行数 | PASS / FAIL / INSUFFICIENT / NA | 派生行 | 确认缺陷 | 开放项 |
|---|---|---|---|---|---|---|---|
| codex1 | gpt-6.1-sol medium | valid，NO_GO | 777 | 410 / 5 / 268 / 94 | 634 | P2 1（R506 最小导通） | 17 |
| codex2 | gpt-6.1-sol medium | valid，NO_GO | 690 | 489 / 0 / 131 / 70 | 582 | 0 | 13 |
| claude1 | opus 5.5 medium | valid，NO_GO | 525 | 396 / 25 / 72 / 32 | 453 | P1 2（反馈开路 VRAW、USB ESD 钳位）、P2 2、P3 1 | 14 |
| claude2 | opus 5.5 medium | valid，NO_GO | 515 | 438 / 6 / 42 / 29 | 436 | P1 1（USB ESD 钳位） | 8 |

记录在 原理图审查结果/SR-20261025-R7-验收-{codex1,codex2,claude1,claude2}-660f790/；SR缺陷.md 在各自工作目录
（/tmp/codex-work/sr-r7-accept-codex*-660f790/、/tmp/sr-r7-accept-claude*-660f790/）。

## 一、数字

| 对 | 行数 A/B | 配对 | 对齐覆盖率 | 一致率 | FAIL 对 PASS | P0/P1 分歧 | R6 同一对 |
|---|---|---|---|---|---|---|---|
| codex1–codex2（同模型） | 777/690 | 589 | 80.3 % | 70.8 % | 2 | 0 | 81.9 %（high） |
| claude1–claude2（同模型） | 525/515 | 477 | 91.7 % | 87.6 % | 16 | 5 | 83.7 % |
| codex1–claude1 | 777/525 | 506 | 77.7 % | 71.9 % | 8 | 12 | 82.6 % |
| codex1–claude2 | 777/515 | 464 | 71.8 % | 71.8 % | 2 | 6 | 79.4 % |
| codex2–claude1 | 690/525 | 505 | 83.1 % | 79.4 % | 9 | 12 | 82.1 % |
| codex2–claude2 | 690/515 | 473 | 83.7 %* | 83.7 % | 5 | 6 | 75.5 % |

\* codex2–claude2 的对齐覆盖率是 78.5 %，一致率 83.7 %。目标 85 %。

读法：
- Claude 同模型对第一次过线（87.6 %，对齐 91.7 %）；它的分歧 59 处里 49 处是派生行对派生行，也就是功能判定本身的不同，不再是"谁绑了哪些行"。
- Codex 同模型对从 81.9 % 掉到 70.8 %。两个原因都查得到：codex1 用 `states_add` 给全部十块电路加了六个状态（下文 §三），
  以及 codex1 用四个开放项（T301-INCREMENTAL、FAULT-AUX-TRANSFER、BIAS-LOW-CURRENT、ANALOG-TEMP-ERROR）挡住了 160 行，INSUFFICIENT 268 行对 codex2 的 131 行。
  这次 Codex 是 medium，R6 是 high，数字不能直接当成退步；但这两种自由度是规则留下的，与模型无关。
- 跨模型 71.8–83.7 %，和 R6 的 75.5–82.6 % 同一水平；最高的一对（codex2–claude2）是两份状态数、开放项数都少的记录。

## 二、哪几层已经收敛

四份记录 **0 处差异** 的层（与 R6 相同，预绑后多了一层）：

- 器件角色 `device_kinds`：33 颗相同；两份 Claude 多核了 J701 为 connector，Codex 没写它。
- 候选决定：10 accept、2 reject 四份相同（STARTUP-U201.DIS、STARTUP-U402.HV 都是 NOT_A_CIRCUIT）；add 1–3 条（Q202/Q402/U202 这类走线穿过的小信号件归属），claude2 用了一次 merge。
- 电路成员：十块电路成员集合相同，唯一例外是 codex1 把 C102/D101/R103–R105 也 add 进了 J101 输入保护（15 对 10）。
- 任务剖面：14 个相位四份完全相同。
- **计划预绑的行**：四份记录的派生行 634 / 582 / 453 / 436，各占全部行的 82–86 %，差额全来自行数本身（状态数、需求数），不再来自审查员选绑哪些器件行
  （R6 是 387 / 287 / 185，占 67 / 50 / 35 %）。手填只剩全板行、文档行和图面目检。

## 三、配不上的行落在哪（对齐损失）

| 来源 | 行数 | 哪几份 | 根因 |
|---|---|---|---|
| 需求行 REQ-D01 | codex2 对任一 Claude 172 行配不上，codex1 92 行 | 四份需求条数 53 / 80 / 24 / 24 | 工程规格.md 的要求表表头是"工程ID"，`requirements_extract.ID_HEADERS` 不认，29 条 E-* 一条都没抄到（四位审查员都报了，见 §五）。codex1 手抄了 E-*；codex2 还把 §7 的 27 条 D-* 工程决定也抄成需求；两份 Claude 把 E-* 并进对应 REQ-* 的 interpretation。同一文档出了三种需求集合。 |
| 电路行 PWR-C02/C03/C05/C04/PRO-C01/PWR-C06/C15/ANA-T01 | codex1 对任一其他记录 ~130 行 | 只有 codex1 | codex1 的十条 accept 决定都带 `states_add: [off, startup, standby, power_down, hotplug, short_circuit]`，引文是一句"需求 工程规格 §2、§3、§4.1和§6.2"。规则只要求 states_add 带能打开的引文，没要求引文说出哪个状态；每多一个状态，每块变换器就多一整套 PWR-C* 行。 |
| CFG-D01 7 行 | claude1–claude2、codex2–claude2 | claude2 | 七条 CFG-D01.<组>.U601 两边 id 相同却配不上：claude1 在 `intent.devices.U601.configurable` 写了配置声明，判据文字随声明变（出处、允许范围进了 criterion），claude2 没写、判据是"先写声明"的提示版，`check_key` 不同。声明与否是审查员的选择。 |
| DEV-C01 / DEV-D02 / DRV-C02 零散 2–4 行 | 各对 | — | devices 声明不同（17 / 36 / 37 / 33 颗），个别预判行跟着声明走。 |

## 四、配上的行里不一致落在哪（一致率损失）

六对的分歧 59–172 处，其中派生行对派生行占 83–88 %：预绑之后，不一致几乎都在功能判定里，可以按开放项和发现项点名。

**1. 开放项挡住的范围（INSUFFICIENT 对 PASS）**——最大的一块。

| 记录 | 挡行最多的开放项（种类，挡住的行数） |
|---|---|
| codex1 | T301-INCREMENTAL（交付物，62）、FAULT-AUX-TRANSFER（交付物，37）、BIAS-LOW-CURRENT（原厂值，36）、ANALOG-TEMP-ERROR（原厂值，25） |
| codex2 | FW-CAPABILITY（交付物，34）、AUX-TRACK（交付物，32）、PORT-SHORT（设计值，19）、T301-INSULATION（交付物，16） |
| claude1 | T301-DWG（交付物，29）、U601-CFG（交付物，7）、L101-DWG（6）、J101-DWG（6） |
| claude2 | T301-DRAWING（交付物，14）、U601-CONFIG（交付物，8）、L101-DRAWING（7）、BULK-SURGE（原厂值，5） |

同一个缺口（T301 变压器图纸没交付）四份都开了，挡的行数 62 / 16 / 29 / 14：开放项的 `decides` 写多宽是审查员定的。
codex1 还开了 BIAS-LOW-CURRENT、ANALOG-TEMP-ERROR 两个原厂值缺口（各挡 36 / 25 行），其他三份对同样的行判了 PASS。

**2. FAIL 对 PASS**——三处真正的技术分歧，都值得记：

- **USB 口 ESD 钳位**（PRO-A02.D702–D705、PRO-D03.J701）：两份 Claude 都判 FAIL（PESD5V0L1UA 钳位 9–12 V 直接并在 U601 CC/D± 脚上，高于 6.5 V 绝对最大额定，无串联限流），
  codex2 判 PASS（"器件峰值钳位必须与实际脉宽、源阻抗及芯片内部 ESD 共同评估，不能把数据表另一波形的峰值与静态 6.5 V 直接相减"），codex1 开了原厂值缺口。
  这是判据分歧：PRO-A02 的"钳位器件窗口"该不该按原厂钳位电压对脚绝限直接比较。
- **反馈开路时的 VRAW 峰值**（PRO-C01.FEEDBACK-OPEN.U402-3、PRO-C02.TRIP.U402-1、PWR-C02.FLYBACK-FAULT.C301）：claude1 算出 FAULT 锁定前 VRAW 升到 38 V 以上（P1），
  claude2 算出 33.14 V、对 35 V 余量 1.86 V 判 PASS；两份 Codex 都把它挂在"T301 辅助绕组跟随关系未规定"的开放项上。同一条链四个答案，差在 FAULT 锁定延迟（22.5–37.5 ms）期间的上升量怎么算。
- **U501 最小导通时间**（PWR-C05.…C507、PWR-C04.…U501）：codex1 和 claude1 判 FAIL（R506 设的 1 µs 最小导通长于 20 V 轻载时 Q501 的实际导通），codex2 和 claude2 判 PASS。

**3. 需求行**：配上的 REQ-D01 行里分歧 19–67 处，大半是同一需求一边绑到树上派生、一边自判，或 codex2 把 D-* 决定当需求后承接方面不同。

## 五、审查员报的 SR 缺陷与反馈

四份 SR缺陷.md 共 10 条，去重后 6 项；都已对照代码核实。

| # | 报告者 | 缺陷 | 核实 |
|---|---|---|---|
| 1 | 四份都报 | `requirements_extract.ID_HEADERS` 不含"工程ID"；首列"D-01 标题"形式和带斜杠的列表编号（`A.2.2.1/A.2.3`）也匹配不上 | 成立：`ID_HEADERS = {'id','编号','需求编号','req','需求 id','需求id'}`；表头规则只认整格为 ID 的表头 |
| 2 | codex1 | `pinout_complete` 对缺脚封装误拒：NCP1343 CASE 751BP 的物理脚是 1–8 和 10，`missing_package_pins` 按 SOIC-9 期待 1..9 | 成立：`board_intent.missing_package_pins` 生成 1..N |
| 3 | codex1 | 跨功能共享开放项（另一功能用 `check_ids` 点名本行）不被余量校验承认，局部 ESTIMATE 余量被报"decides nothing" | 成立：`review_functions` 的 deciding 集合只收本功能的 opens/fails/judgements |
| 4 | codex1 | 去耦扫描把按关键字识别为变压器、但没声明的 T301 列为"未核 IC 供电脚" | 成立：`decoupling.py` 候选过滤只排除 classify 为 CONNECTOR 和核验类别在 NO_SUPPLY_KINDS 的器件 |
| 5 | codex1 | 功能汇总不继承 `open_ref` 指向别的功能的本功能行：FN-SYS-SEQUENCE 显示 PASS，RST-T03.SYS-SEQUENCE 是 INSUFFICIENT | 成立：`results_model.effective_verdicts` 跳过 `function_id` 等于本功能的行 |
| 6 | codex2 | `REQUIREMENT_NUMBERS_UNREAD` 不读 interpretation 里对无参数槽数字的说明 | 成立，诊断是提示不是错误；10-25 巡检已给每个数列出能收它的参数 |
| 7 | claude2 | 手册没有去耦条款时，去耦行仍要先在 `intent.decoupling` 写条款才能 PASS，且不允许 `manual_verification` | 成立，是设计：条款要审查员从手册读出；手册没有条款时写"手册未给条款"也算一条——文档要说清 |

反馈（notes.sr_feedback，6 条）：DEV-C01 预判把 HV 启动串阻 R403 按 RECT 全压算成 30 W（claude1，过严：HV 脚是受控电流源 ≤5 mA）；
PRO-C02 给栅极稳压基准 D404 派了 NOTRIP 行（claude1，误报：它正常就一直导通）；passive_stress 没把与 C102 并联的 LED D101 正向压降当钳位（claude2，误报）；
REQ-Q07 质量筛查把本轮的 review-results 当成历史记录（codex2，误报）；其余两条与缺陷 1、7 重复。
质量筛查这次 72 / 30 / 80 / 80 条，两份 Claude 各 57 / 66 条是 REFERENCED_OBJECT_OUTSIDE_SCOPE（开放项后果句点到了功能对象之外的位号）——预绑后功能对象多了，这个筛查的范围定义要跟着看。

## 六、修法清单

### A. 规则维护（不改架构，不改格式）

1. `requirements_extract`：表头加"工程id"；表格首列"ID 标题"形式取首个 ID；列表项 `A.2.2.1/A.2.3` 形式按斜杠拆成两个 ID 或整体收下。四位审查员因此各手抄一版需求，是本轮最大的对齐损失。
2. `board_intent.missing_package_pins`：脚表允许标明物理缺脚（如 `"9": {"name": "ABSENT", "role": "absent"}`），或按表中最大脚号推断非连续编号时只核表内脚号——定一种。
3. `review_functions`：余量"decides nothing"检查的 deciding 集合加入其他功能用 `check_ids` 点名本功能行的开放项（与 `derive_rows.named_elsewhere` 同一规则）。
4. `decoupling.py`：候选过滤同时排除 `classify` 为 NO_SUPPLY_PARTS（变压器、电感等）的未声明器件。
5. `results_model.effective_verdicts`：本功能的行若 `open_ref`/`fail_ref` 指向别的功能，也向本功能继承 OPEN/FAIL。
6. DEV-C01 预判：HV 启动脚（已有 feed-tree 的 HV start-up 识别）串阻的功耗按控制器启动电流算，不按全压；PRO-C02 不给栅极偏置齐纳（阳极接栅极/源跟随器的 BZT/BZX）派 NOTRIP 行——与 10-25 的 `_functional_clamp` 同口径；passive_stress 把并联 LED 当钳位（`clamp_voltage` 认 LED 正向压降）。
7. 质量筛查 REFERENCED_OBJECT_OUTSIDE_SCOPE / IMPACT_REFERENCES_OUTSIDE_SCOPE：范围取功能对象 ∪ 成员行对象（预绑后成员行有自己的位号）。
8. 核验为可配置器件（pd_controller 等）而没有 `devices.<ref>.configurable` 声明时，计划出诊断并在 2.1 做完的标志里要求补上：CFG-D01 的判据和键不再随"写没写声明"变。
9. references/plan-and-results.md 去耦段：写明手册没有去耦条款时条款怎么写（引脚定义页 + "手册未给条款"），以及为什么不开 manual_verification。

### B. 要你定的（改输入规则或行的生成）

1. **`states_add` 的边界**：现在一句引文可以给每块电路加六个状态（codex1：+130 行）。
   a. 每个加的状态必须由需求参数或条款点名（standby 要有 standby_power/quiescent_current 需求；hotplug 要有热插拔需求……），引文落在那条需求上；
   b. 取消 states_add，状态只来自候选（类型固定表）；
   c. 保持现状。
2. **开放项挡行的宽度**：同一个 T301 图纸缺口四份挡了 62 / 16 / 29 / 14 行。
   a. 规则层给每类开放项（交付物 / 原厂值 / 设计值）一张"能挡的方面"表，`decides` 超出表的行报错；
   b. 只在 ④ 筛查里报 WIDE_GAP（现状）；
   c. 开放项按器件绑定：缺 T301 图纸只能挡对象含 T301 的行。
3. **PRO-A02 钳位窗口的判据**：原厂钳位电压直接对脚绝限比较（两份 Claude 的 FAIL），还是允许"按脉宽/源阻抗/芯片内部 ESD 综合评估"的 PASS（codex2）？
   a. 规则写死：钳位电压 > 被保护脚绝限即 FAIL，除非线上有串联阻抗且审查员算出注入电流在芯片给的范围内；
   b. 保持开放，由审查员判。
4. **需求文档的 D-* 决定是不是需求**：codex2 把 §7 工程决定抄成 27 条需求，其他三份没有。
   a. 提取器只认 ID 表头的表（修 A1 后 E-* 进来、D-* 不进来），决定类表格由文档作者改成 ID 表才算需求；
   b. 首列以 ID 开头的任何表都算。

### C. 验收流程

- 两路 Claude 因会话额度在 ③ 中断过一次，续做前没有重生成计划；下次验收前确认额度窗口，或把 Claude 两路错开启动。
- Codex 的推理档位要和 R6 一致才能比同模型上限；本轮按用户要求是 medium。

## 七、结论

预绑把"哪些行派生"从审查员手里拿走了：四份记录派生行占 82–86 %，分歧集中到功能判定本身，Claude 同模型对 87.6 % 第一次过了 85 %。
剩下的差异有三个清楚的来源——需求提取器漏读整份工程规格（A1）、`states_add` 和开放项宽度两个没有边界的自由度（B1、B2）、
以及三处真正的技术判据分歧（USB ESD 钳位、反馈开路 VRAW、U501 最小导通）。前两类修掉后再看 Codex 对和跨模型对能到哪。

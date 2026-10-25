# R6 验收：四份独立首审的对比（2026-10-24）

SR 提交 05c8ae7（审查期间 HEAD 变为 f0ca5ad，只改 compare_reviews.py；两份 Claude 记录为保持 review_engine 一致在 f0ca5ad 上重生成了计划）。
板子 ASG-20261023-100W-PD-R6；四位审查员互不可见，独立性规则同 R5。

| 记录 | 模型 | 结果 | 行数 | PASS / FAIL / INSUFFICIENT / NA | 确认缺陷 |
|---|---|---|---|---|---|
| codex1 | gpt-6.1-sol high | 停在 ④（2 条门禁错误，SR-03） | 771 | 510 / 0 / 245 / 16 | — |
| codex2 | gpt-6.1-sol high | valid，NO_GO | 552 | 425 / 1 / 93 / 33 | P1 1（R506 最小导通） |
| claude1 | opus 5.5 medium | valid，NO_GO | 578 | 501 / 2 / 52 / 23 | P1 1（空载功耗）、P2 1（R506） |
| claude2 | opus 5.5 medium | valid，NO_GO | 534 | 394 / 15 / 100 / 25 | P1 2（空载功耗、D404 低电流 VZ） |

## 一、数字

| 对 | 行数 A/B | 配对 | 对齐覆盖率 | 一致率 | FAIL 对 PASS | P0/P1 分歧 |
|---|---|---|---|---|---|---|
| codex1–codex2（同模型） | 767/550 | 514 | 78.1 % | 81.9 % | 1 | 1 |
| claude1–claude2（同模型） | 578/534 | 498 | 89.6 % | 83.7 % | 9 | 13 |
| codex2–claude1 | 550/578 | 502 | 89.0 % | 82.1 % | 0 | 1 |
| codex2–claude2 | 550/534 | 490 | 90.4 % | 75.5 % | 4 | 16 |
| codex1–claude1 | 767/578 | 501 | 74.5 % | 82.6 % | 1 | 1 |
| codex1–claude2 | 767/534 | 490 | 75.3 % | 79.4 % | 1 | 15 |

R5（10-23，Codex 对 Claude sonnet）：对齐 91.1 %，一致率 69.2 %，FAIL 对 PASS 5。目标 85 %。

读法：同模型两对给上限——Codex 81.9 %、Claude 83.7 %，都没到 85 %；跨模型 75.5–82.6 %，比 R5 高 6–13 点。
上限本身不到 85 %，说明剩下的差异大头不在模型，在规则留给审查员的空间。

## 二、哪几层已经收敛

四份记录比对，**0 处差异**的层：

- 器件角色（`device_kinds`）：四份角色集合相同，没有一颗 ic。
- 电路候选与决定：12 条候选决定逐条相同（10 accept、2 reject）；claude1 另加两条 add（见下）。
- 电路成员：对齐的电路成员集合相同（claude1 add 出的两块除外）。
- 任务剖面：14 个相位的占比、负载、温度四份完全相同。

这些就是 10-21 到 10-24 加的候选、决定、角色、需求按量分解机制覆盖的层。

## 三、配不上的行落在哪（对齐损失）

| 层 | 行数（最大一对） | 哪几份 | 根子 |
|---|---|---|---|
| 需求集合 | 195 | codex1 对其余三份 | `requirement_source` 只收一个文档，任务书给了两份；codex1 自己合并成 75 条（sha 是自建文件的），其余三份只抄 用户需求.md 的 19 条 |
| 任务剖面相位名进了判据 | 17（DEV-C02.LIFE 8 + DEV-C06 9） | 每一对 | 数字相同，相位名 `0W-25C` / `0W-25C-带线待机` / `standby@25C` 各不同，判据文本含名字，check_key 不同 |
| 配置组引用进了判据 | 7（CFG-D01） | 每一对 | 判据内嵌审查员写的 citation 与 allowed 原文 |
| 普通二极管声明 `intent.devices` | 21（DEV-C05/D01/D05 ×7） | codex2、claude1 声明了 7 颗普通二极管，claude2 没有 | 规则"普通二极管声明了才生成"，声不声明是自由 |
| `features` 不适用声明 | 13（REQ-Q07） | claude1、claude2 给没检出的类型逐个写了 NOT_APPLICABLE，Codex 没写 | 每个声明各生成一行 REQ-Q07 |
| add 决定 | 11 SIG-C07 + 7 SIG-T04 + 4 SIG-C08 + 4 SIG-C09 | claude1 把未归属的 Q202、Q402 add 成两块电路（PFC-EN-DRV、LATCH-DRV），其余三份留在 REQ-Q08 | add 对 Q08 两种处置都合法；新电路带出接口行 |
| 承接电路对比 | — | — | 对比工具按电路名比承接电路，命名差异淹没了实质；要按候选编号比 |

## 四、配上的行里不一致落在哪（一致率损失）

三份 valid 记录两两：

| 对 | 不一致 | 资料不足对通过（数值限值） | 资料不足对通过（其他边） | NA 对通过 | 一边没通过 |
|---|---|---|---|---|---|
| claude1–claude2 | 81 | 60 | 6 | 1 | 14 |
| codex2–claude1 | 90 | 49 | 22 | 17 | 1 |
| codex2–claude2 | 120 | 75 | 13 | 15 | 16 |

主项是"一边资料不足、一边通过，开项的边经过数值限值"：同一个数（T301 磁参数、RT7209 配置、L101 图纸、CC 电容、齐纳低电流 VZ）
一边开成待办挡住一片行，另一边按典型值或保守档判了通过。这是步骤 ③ 的判断层，本轮没有改它的规则。

FAIL 对 PASS：D404 低电流 VZ（claude2 判 FAIL，另两份 PASS）、PWR-C04 U501（codex2 FAIL，Claude PASS）、空载功耗（两份 Claude FAIL，codex2 没算到）。
三个都是真实的工程分歧，不是记录格式问题。

## 五、审查员报的 SR 缺陷与反馈

| 来源 | 内容 | 性质 |
|---|---|---|
| codex1 SR-01 | `gap_inventory.py` 把普通阻容逐颗列为供应商资料缺口（93 项） | 过严 |
| codex1 SR-02 | 拒绝 STARTUP-U201.DIS / U402.HV 链后，REQ-Q08 把链的核心器件 U201、U402 列为未归属 | 缺陷 |
| codex1 SR-03 | `review_functions._monotonic_errors` 要求 `test_points` 非空，原厂完全没有该量数值点时无法如实记录 VENDOR_DATUM；阻断 ④ | 缺陷，阻断 |
| codex2 SR-01 | `optocouplers.internal_pullup.bias_v` 不接受 min=0 | 过严 |
| codex2 SR-02 | 纯测试方面的需求行写 NA + OUTSIDE_SCHEMATIC_STAGE 被拒 | 缺陷 |
| codex2 SR-03 | 打包拒绝顶层 SR缺陷.md | 任务书与打包布局冲突，下次把 SR缺陷.md 放输出目录外 |
| claude1 | PWR-A02 把 BIAS15、HV、VCC、SEC_RTN 报成"电源轨无驱动" | 误报 |
| claude1、claude2 | PRO-A02 把常态导通的功能齐纳 D303 / D404 当防护件要浪涌参数 | 过严 |
| claude1 | REQ-D01 DOWNSTREAM-HANDOFF 方面：整行不能记阶段 NA，条款上的阶段 NA 又没有可链接的行 | 与 codex2 SR-02 同一处 |
| claude2 | DEV-C01 预判把整条高压轨加在被钳位的支路上（C102、R403） | 过严 |
| claude2 | TEMPERATURE-GRADE、CONVERTER-INPUT-RANGE 需求行从 DEV-C05 继承了 F-BIAS15 的 FAIL，而缺陷是工作电流区问题 | 派生过宽 |
| claude2 | 手册没有去耦容量条款时仍须写一条"未规定"的条款才能解除缺口 | 可简化 |

## 六、修法清单

### A. 规则维护（不改架构，不改格式）

状态：用户 2026-10-25 定“先做 A 组”，10 条同日落地（台账条目 "R6 fix list A: ten rule-maintenance items"）。实施偏差：
A10 的过滤按失败边经过的条件判——经需求文档条款或经本方面参数单位的限值才继承，别的量的失败留在器件行（量过三份
valid 记录：派生 FAIL 4 处，3 处是 °C 方面继承了 V 的失败，改后不继承；CONVERTER_INPUT_RANGE 继承齐纳 VZ（同为 V）的
1 处仍在，单位分不开）。A9 还把 GND/EP 落在返回网上的脚排除。另：05c8ae7 没挪的冷扫这次按用户问的方向挪进了 1.2
（命令同 2.1 的 ①，1.2/1.3 的做完标志都来自它的提示；步骤之间传的文件不变）。

1. 任务剖面相位名不进判据：DEV-C02.LIFE / DEV-C06 的判据按（占比、负载、温度）排序生成，名字只作显示。
2. CFG-D01 判据用固定模板（位号 + 配置组），citation / allowed 放行字段。
3. `compare_reviews` 的承接电路一节按候选编号（`circuit_key`）比，不按电路名。
4. codex1 SR-02：REQ-Q08 的未归属清单减去已被电路拥有的器件。
5. codex1 SR-03：VENDOR_DATUM 允许 `test_points: []` 加 `no_test_points_reason`（手册哪一页查过、没有该量的任何数值点）。
6. codex2 SR-01：`bias_v.min` 允许 0。
7. codex2 SR-02 / claude1：纯测试方面的需求行允许整行阶段 NA（方面没有原理图判据时），handoff 齐全即可。
8. codex1 SR-01：`gap_inventory` 把普通阻容的"专属手册"缺口归到"审查者自行追踪"，不进设计方清单。
9. claude1：PWR-A02 对由变换器/绕组产生的轨不报"无驱动"（BIAS15、HV、VCC、SEC_RTN）。
10. claude2：需求行派生只取方面相关的行——TEMPERATURE-GRADE 不继承 DEV-C05 的工作点 FAIL（派生时按方面过滤规则，或按失败项的 cause 过滤）。

### B. 要你定的（改输入规则或行的生成）

状态：用户 2026-10-25 逐条定了 a 并同日落地（台账条目 "R6 fix list B"）：B1 `requirement_source` 收列表；B2 器件行只跟核验过的
kind 走，`devices` 声明不生成行（"审哪些器件"的准则写进 commodity-floors.md）；B3 NOT_APPLICABLE 声明不生成 REQ-Q07 行，只作
REQ-Q08 那一行的依据；B4 未归属有源件须 add 或器件级 reject，add 可并入已有电路，候选走线从电路自己的网穿过门极被驱动的小信号管
（R6 记录重生成后 Q202/Q402 落进驱动它们的 USB-J701，未归属有源件 0）；B5-1 PRO-A02 跳过内部节点上的功能齐纳（TVS 照旧），
B5-2 DEV-C01 预判按钳位电压定被钳位网的上界。实施偏差：B4 不穿 BJT 以外的器件，也不从漏极反向穿到门极（R6 两例都从门极进）。

1. **需求源多文档**：`requirement_source` 接受列表（每个文件 path + sha256），抄录逐文件做、id 跨文件唯一；任务书列几份需求文档就抄几份。
   不改的话：三份记录只抄了 用户需求.md，工程规格.md 里 E-xx / D-xx 的量化要求整个没进审查。
2. **普通件声明**：两条选一——(a) 两端普通二极管即使声明了 `intent.devices` 也不生成 DEV-C05 / D01 / D05 行（器件行只给固定生成的那几类）；(b) 计划列出"该声明而没声明"的器件（三脚以上半导体、变压器、连接器）并拒绝出计划。a 消掉 21 行差异，b 同时把漏声明变成缺口。
3. **`features` 不适用声明**：NOT_APPLICABLE 的声明不再各生成一行 REQ-Q07（没检出的类型已在 REQ-Q08 汇总行里）；或者反过来，计划对每个没检出的类型都要一条声明。前者消掉 13 行差异且少写。
4. **add 对 Q08**：候选 `unassigned` 里有角色或三脚以上的半导体（Q202、Q402 这类）要求必须决定——add 进某块电路或 reject 写原因，留在 Q08 不算答完；两端件照旧留 Q08。
5. **过严两处**：PRO-A02 功能齐纳（常态导通、不在防护位置）不问浪涌参数；DEV-C01 预判对被钳位支路按钳位电压算。都是放松，按"避免过严"的目标做，但改变行的判法，列出来请你确认。

### C. 验收流程

- 验收期间不提交任何改动（本轮 f0ca5ad 让两份 Claude 记录重生成了计划）。
- 任务书里 SR缺陷.md 的位置改到输出目录之外。

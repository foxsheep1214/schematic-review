# KiCad Replay Bench：KiCad 原生交付层的冻结答案回放

SR 现在主要审 ASG 生成的 KiCad 工程。`circuit_bench` 只覆盖 PWR-E01/SIG-E01/RST-E02 计算、输入是合成的
Cadence 网表；`seeded_bench` 统计真实电路植入缺陷的网表扫描检出率。两者都不测 **KiCad 原生交付这一层**：
严格解析能不能产出 db、缺名脚怎么记、导出日志怎么算、去耦清单在缺口下怎么分组。本基准用 ASG 已冻结的
真实交付回放这一层，每个字段都有人工核对后冻结的预期答案。每次改 SR 都应跑一次，几秒即可。

## 运行

当前候选的页面库存行为使用独立 `page-inventory-v1` 约定，位于
`revisions/page-inventory-v1/`。原 `expected.json`、`cases.json`、`sources.json`、
原脚表 intent 和所有原 XML 夹具保持原字节；`manifest.json` 同时绑定历史父项
与新派生项的 SHA256。独立读取原有公开 XML 的 sheet 声明与组件路径，确认
6 种回放模式遗漏真实空根页；新约定只使它们的 DOC-V01 检查数加 1，
其他电气/完整性冻结字段不变。脚表声明仅绑定新输入指纹，不迁移旧审查结果。
`--contract legacy` 用于重放历史约定，
新模型对历史检查数的差异仍会明确报出，不能当作历史 checksum 一致。

当前默认约定是 `fixed-device-rows-v1`（`revisions/fixed-device-rows-v1/`，2026-10-22）：晶体管、光耦、稳压/TVS 二极管、整流桥、变压器与定制电感不经 intent.devices 声明也生成身份、引脚处置与工况行，普通二极管与普通电感只在声明时生成；r02 +6，rf1 三例各 +27，rf2 +12，每颗器件 3 行，其余答案不变。

此前的默认约定是 `decoupling-pin-map-v1`（`revisions/decoupling-pin-map-v1/`，2026-10-22）：去耦组按官方脚表成组，每个已声明器件、每个供电网一组，审查员只按（位号，网）写用途、条款与回流网；rh-ad8495-thermocouple-pinmap 的 U201:VCC 由待确认的候选组变为脚表组，少一项 `confirm-group-and-return` 缺口，其余答案不变。

此前的默认约定是 `rail-confirmation-v1`（`revisions/rail-confirmation-v1/`，2026-10-22）：网表上像电源（有 IC 从它取电或大电容到地）而名字不像轨的网须在 intent 里声明成轨或在 `rail_exclusions` 写依据；rf1 两个带 intent 的用例改用加了 VOUT_N（隔离输出回流网）排除依据的 intent 副本，其余输入、用例与答案不变。

更早的默认约定是 `system-functions-v1`（`revisions/system-functions-v1/`，2026-10-22）：系统功能有对象才生成——两个以上地网才问 PWR-T06，两条以上电源轨才问 RST-T03（全板一行），有可能是主控的 IC 才问 SIG-D13；DEV-C01/C02/C03 每块电路对自有器件一行、未归属器件全板一行；每个有行的系统功能一个框架（FN-SYS-*）。逐例重建计划核对检查数变化等于这几项之和，其余答案不变。

更早的默认约定是 `interface-rows-v1`（`revisions/interface-rows-v1/`，2026-10-22）：连接器的对端定义、载流、对外防护三行改挂对外接口 `EXT-<连接器>`，DEV-C04 由全板一行改为每个连接器一行，每个连接器一个接口框架（3 个成员）；各用例检查数的变化逐例等于连接器数减 1（没识别出连接器的 r04 两例减 1），其余答案不变；用例里没有两块以上电路，电路对、链路与供电接口的行不出现。

此前的默认约定是 `circuit-owners-v1`（`revisions/circuit-owners-v1/`，2026-10-21）：候选文件升到 schema 2，每个成员带 `owned`，每颗被持有的器件恰好归一块电路，intent.circuits 新增 `owned`；rf1-c2000-float-flyback-frames 换用重新生成的候选与 intent 夹具（候选、成员与路径不变，输出连接器由其被判为重复的候选让给 PRI-FLYBACK），答案不变。

此前的默认约定是 `circuit-candidates-v1`（`revisions/circuit-candidates-v1/`，2026-10-21）：intent 的电路由 `circuit_candidates.py` 生成的候选文件与 `intent.circuit_decisions` 推出，lint 对声明电路的 intent 必须带 `--candidates`（用例新增 `candidates` 字段），手画电路列表被拒绝；只有 rf1-c2000-float-flyback-frames 受影响：生成器在没有已核实 IC 类别的夹具上给出 5 个候选，4 条决定（Q1+Q2 合并为 PRI-FLYBACK、Out1 走线为其重复、Q3/Q4 不是电路）推出 1 个三态电路，检查数 325→313（298 + 5 条规则 × 3 态），FN-PRI-FLYBACK 成员 10→15；其余答案不变。

此前的默认约定是 `state-invariant-v1`（`revisions/state-invariant-v1/`，2026-10-20）：与工作态无关的电路检查项（`catalog.STATE_INVARIANT`：PWR-T05、ANA-D01、SIG-T04、SIG-D07、SIG-D04）每电路只生成一行，object 不带 state；只有 rf1-c2000-float-flyback-frames 受影响（PWR-T05 两态并成一行，检查数 326→325，FN-HV-CLAMP 成员 12→11），其余答案不变。

此前的默认约定是 `function-frames-v1`（`revisions/function-frames-v1/`，2026-10-20）：计划 schema 4，intent 声明的每个电路生成一个功能框架（新增观测字段 `plan.functions`：框架 id、成员数、状态；父用例的 intent 都没有 circuits，全为空），检查行带 question/function_id/aspect。新增用例 rf1-c2000-float-flyback-frames（同板 intent 再声明反激变换器、TVS 钳位、NTC 检测 3 个电路，检查数 298→326 = 5×2+6×2+6×1 条检查行），其余答案不变。

此前的默认约定是 `lint-checks-v1`（`revisions/lint-checks-v1/`，2026-10-19）：冷检规则的 FINDING/CANDIDATE 发现各成一项计划检查（lint_reviews 退役），检查数只增加该例冷检发现数（r01 178→192、r02 200→216、r03 313→365、r04 50→54、rf1 286→298、rf2 74→78），其余答案不变。

此前的默认约定是 `typical-boards-v1`（`revisions/typical-boards-v1/`，2026-10-18）：K 位号超过 8 脚不当继电器、VBUS+CC1+CC2 脚组认作 USB-C 连接器；r02 检查数 198→200，其余答案不变。

此前的默认约定是 `name-heuristics-v1`（`revisions/name-heuristics-v1/`，2026-10-18）：统一地名与轨名判定、原生 power_out 脚作为电源来源；r03 检查数 311→313（VSYS 识别为轨），r05 64→65（PWR-T04），其余答案不变。

此前的默认约定是 `testpoint-kind-v1`（`revisions/testpoint-kind-v1/`，2026-10-18）：库条目名为 TestPoint 的符号（`Connector:TestPoint`、`SparkFun-Connector:TestPoint_1.0mm`）按测试点归类、不再套连接器检查，只把 r01 的检查数由 186 改为 178，其余答案不变。

此前的默认约定是 `real-flyback-v1`（`revisions/real-flyback-v1/`，2026-10-17）：在 `threshold-window-v1` 的 9 个用例上
新增两块公开反激板的 3 个用例，父版本答案逐字段不变。上游为 KiCad 10/8 格式，降级与导出步骤及独立核对工具见
`tools/`：`downgrade.mjs`（调用 HubertHQH/kicad-version-converter，GPL-3.0，不随仓库分发）、`k7_power_pins.py`、
`conn_compare.py`（降级前后连接相关内容逐项比对）、`geo_netlist.py`（在原始文件上自算连通并与导出网表比对）、
`indep_check.py`（不调用 SR，直接读 XML 重算器件/网数、缺名脚与去耦组，输入为 `run.py --out` 的 results.json）。

此前的默认约定是 `name-gap-scope-v1`（`revisions/name-gap-scope-v1/`，2026-10-13）：严格自检仅因缺功能名失败、
且缺名脚没有完整官方脚表时，缺口只记在缺名器件自身的去耦组和 `discovery_gaps`（`pin-name-unresolved:<脚>`），
不再给每个去耦组加整网缺口 `netlist-integrity/export`。缺名只改变该器件引脚角色，不改变网络连通。
其余字段与 `page-inventory-v1` 相同；后者文件保持原字节，可用 `--contract page-inventory-v1` 重放。

```sh
python3 -B evals/kicad_replay_bench/run.py [--sut <另一个 SR 副本>] [--out <输出目录>] [--compare <旧 results.json>] [--case <用例>]
```

- 每个用例按审查员网表扫描的方式执行：`parse_kicad.py`（严格模式；严格模式没写出 db 时，另用 `--no-strict`
  取得 db 供后续步骤使用，并把“没写出”记为观测值），再执行
  `lint.py --log <日志> [--intent <intent>] --json --plan-json --decoupling-json`。
- 每个字段判为 **一致**（等于冻结答案）、**已知偏差**（等于 `known_deviations` 记录的 main 现值，原因已登记）
  或 **不一致**（回退，或未经核对的变化）。有不一致时退出码为 1。
- `--compare` 逐例列出与旧 `results.json` 相比变化的观测字段，不论是否符合预期。改规则前后各跑一次，
  每条变化都要说明原因。
- `scripts/tests/test_kicad_replay_bench.py` 在全量回归中跑全部用例，有不一致就失败。

## 用例

| 用例 | 来源 | 主要锁定的行为 |
|---|---|---|
| r01-thingplus-esp32s3 | ASG 第 01 轮最终导出 | 严格自检通过；SparkFun 电容库不按位号推断种类（component-kind 缺口） |
| r02-dasduino-coreplus | ASG 第 02 轮最终导出 | 晶振 X1 缺名脚算功能缺名；三焊盘跳线触点不算；缺名缺口只落在 X1 自身去耦组（name-gap-scope-v1） |
| r03-nrf9151-feather | ASG 第 03 轮最终导出（6 页） | 单个缺名控制脚 U8.4；29 个去耦组；DNP 件在网表扫描中的缺口 |
| r04-host-usb-pmod | ASG 第 04 轮最终导出 | 小板基线 |
| r04-c1-return-moved | 第 04 轮门禁反例（C1 回流脚改接 +3V3） | 电容离开直连供电/回流对后从去耦组消失 |
| r05-lipo-charger | ASG 第 05 轮最终导出 | 回流在 BAT_NEG 的保护芯片去耦组；连接器 VBUS 候选组 |
| rh-ad8495-thermocouple | 2026-10-10 Claude 演练板 | AD8494 库符号 OUT 脚无名 → 严格自检失败；空导出日志 |
| rh-ad8495-thermocouple-nolog | 同上，不给 `--log` | 没有导出证据时 DOC-A01/A02 必须跳过 |
| rh-ad8495-thermocouple-pinmap | 同上，intent 只含官方脚表 | 缺名脚由完整官方脚表解决（5fa6d3b），去耦不再带整网缺口 |
| rf1-c2000-float-flyback | 公开同步整流反激板（CERN-OHL-S-2.0） | 4 子图 85 器件；Reg 位号稳压器按原生电源脚识别；RAIL_/HV 轨名、VOUT_N 回流、VOUT_FBACK 反馈线；TVS 开关节点钳位保留 PRO-C02；NTC 只在检测脚生成 ANA-C04 |
| rf1-c2000-float-flyback-intent | 同上 + 带出处 intent | 反激绕组映射与 TVS 漏感钳位、R19 源极采样回地、UCC24612 同步整流最小声明 |
| rf2-hv-flyback-lt3957a | 公开 LT3957A 高压反激板（CERN-OHL-W-2.0） | 连接器信号针 ESD 归入 PRO-D03；电源轨 TVS 与开关节点齐纳保留 PRO-C02；HV 输出按轨审查 |
| rf1-c2000-float-flyback-frames | 同上 + 候选文件与 4 条决定推出 1 个电路的 intent | 每个电路一个功能框架；检查行数 = 随状态的包电路检查项 × 状态 + 与状态无关的规则各 1 行（function-frames-v1、state-invariant-v1）；电路不手画，来自候选与决定（circuit-candidates-v1） |

日志模式 `empty` 指给 `--log` 但文件为空，这是 kicad-cli 干净导出时的实际情况；`none` 指不给 `--log`。

## 每例冻结的字段

`parse.strict_exit`、`parse.strict_db_written`、`parse.self_check_passed`、`parse.missing_functional_pins`、
`parse.parts`/`parse.nets`（夹具身份），`lint.DOC-A01_executed`/`lint.DOC-A02_executed`、
`plan.DOC-Q01`（applicability/readiness）、`plan.checks_total`、`plan.not_applicable`、`plan.functions`（框架 id/成员数/状态）、
`decoupling.discovery_gaps`、`decoupling.pin_names_resolved_by_official_pinout`、
`decoupling.group_gaps`（键为 `状态/declared_id`，值为该组 gaps）。

## 答案怎么来的

候选值由 SR main@5fa6d3b 生成，然后逐项核对后冻结（2026-10-10），答案不由被测工具自己决定：

- 缺名脚：不经 SR 代码，直接读原始 XML，列出非无源/非 no_connect、`pinfunction` 和库引脚名都为空的节点，
  再按 DOC-Q01 的口径去掉连接器和跳线触点。
- 去耦组：从原始 XML 自算每组供电网与地网之间的两端电容，55 个组逐组一致；组上的缺口按规则逐条核对
  （自检失败→`netlist-integrity/export`，无回流网→`need-one-explicit-return-net`，非 Device 库电容→`component-kind`）。
- 器件清单、检查数、NA 数、DOC-Q01：对照方法文档逐行审读（小板逐项看过计划清单；网表扫描没有 intent 声明，
  NA 必为 0）。
- 每例的核对记录写在 `expected.json` 的 `verification` 字段。

最初在 main@5fa6d3b 核对时，有两类字段记为已知偏差（原因见交接说明“二之一”和 `sr-rehearsal-fixes.patch`）：

1. 严格自检失败时应照写 db（`self_check_passed=false`），退出码仍为 2；main 不写 db。
2. 给了 `--log` 但日志为空时应按零命中执行 DOC-A01/A02；main 当成没给日志并跳过。

把该补丁应用到 main 副本上跑 `--sut`，全部 126 个字段一致；用 5fa6d3b 之前的 cde1054 跑，
pinmap 用例的去耦字段和各例的 `pin_names_resolved_by_official_pinout` 报出 11 处不一致。
这两项已在 main@03b6fde 发布。第08轮独立复核确认后退役其21条
`known_deviations`，126个冻结字段的预期值、夹具和来源均不变；不是重新生成答案。
当前严格失败仍写db且退出2，提供空日志仍执行两项扫描；不提供日志继续跳过。
只保留未修复问题的已知偏差，修复发布后必须退役相应允许值并加入退化拒绝测试。
`test_replay_retired_invariants.py` 验证必需的db保留和日志扫描回退会判MISMATCH。
用当前基准配旧5fa6d3b三份解析/扫描脚本的隔离退化探针，会有21处MISMATCH并退出1；
保留旧允许值时该探针曾以105 MATCH /21 KNOWN /0 MISMATCH错误退出0。

## 覆盖范围与不能推断的内容

- 只测**自动层的输入与计划结构**：解析、自检、日志扫描是否执行、去耦清单的缺口和分组、计划的检查数和 NA 数。
  不测任何检查结论（PASS/FAIL）、发现内容、严重度、报告或准出判定，也不测专家审查。
- 去耦字段只锁定**清单**（哪些电容归哪组、缺什么证据），不是 PDN 或电气判决。网表扫描里的保守分组
  （开关节点 SW、连接器 VBUS、无脚表时把 -VS 所在的 GND 当供电组）按约定是候选组、必须由审查者对照资料核对（通常由 AI 完成，不代表人员确认），
  冻结它们不表示这些分组在工程上正确。
- 检查数和 NA 数是回归锁：核对的是合理性，不是逐条独立推导的数目。规则表或展开方式有意改动时，
  这两个数会变，需要逐条说明后更新答案。
- 只有 6 块板、9 个用例，全部来自 ASG 2026-10 批次与一次演练，器件库以 KiCad 官方库、SparkFun、
  e-radionica 为主。没有覆盖的情形：kicad-cli 导出报错的日志、带 No_connect 被忽略告警的日志、
  `.kicad_sch` 直接输入（本基准只用已导出的 XML，不依赖 kicad-cli）、多装配状态、带完整 intent 的证据扫描、
  I²C 拓扑及其他检查器清单、改版对比。
- `known_deviations` 只说明“这个值是已知问题”，不说明问题已修。

## 夹具与来源

- `sources.json`：每个夹具的上游仓库、commit、许可证、原始导出在 ASG 批次目录中的路径和 SHA256，
  以及精简夹具的 SHA256。第三方原始导出不复制进仓库。
- `fixtures/*.xml`：`make_fixtures.py` 生成的精简网表（均小于 200 KB）。只删去 `parse_kicad.py` 不读的元素；
  脚本要求精简前后解析出的 db 与自检结论完全相同，否则拒绝写出。许可证见 `fixtures/LICENSES.md`。
- 重建夹具：`python3 -B evals/kicad_replay_bench/make_fixtures.py [--batch-root <ASG 批次目录>]`。
  演练板的原始导出在会话临时目录，不保证保留，需要时用 `--override rh-ad8495-thermocouple=<路径>` 指定，
  SHA256 不符会拒绝。
- 新增用例：在 `sources.json` 登记来源，生成夹具，在 `cases.json` 加用例，跑出候选值后**独立核对**，
  再写入 `expected.json` 并附 `verification`。不要直接把候选值抄成答案。

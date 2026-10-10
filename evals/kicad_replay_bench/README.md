# KiCad Replay Bench：KiCad 原生交付层的冻结答案回放

SR 现在主要审 ASG 生成的 KiCad 工程。`circuit_bench` 只覆盖 PWR-E01/SIG-E01/RST-E02 计算、输入是合成的
Cadence 网表；`seeded_bench` 统计真实电路植入缺陷的冷跑检出率。两者都不测 **KiCad 原生交付这一层**：
严格解析能不能产出 db、缺名脚怎么记、导出日志怎么算、去耦清单在缺口下怎么分组。本基准用 ASG 已冻结的
真实交付回放这一层，每个字段都有人工核对后冻结的预期答案。每次改 SR 都应跑一次，几秒即可。

## 运行

```sh
python3 -B evals/kicad_replay_bench/run.py [--sut <另一个 SR 副本>] [--out <输出目录>] [--compare <旧 results.json>] [--case <用例>]
```

- 每个用例按审查员冷跑的方式执行：`parse_kicad.py`（严格模式；严格模式没写出 db 时，另用 `--no-strict`
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
| r02-dasduino-coreplus | ASG 第 02 轮最终导出 | 晶振 X1 缺名脚算功能缺名；三焊盘跳线触点不算；自检失败给每个去耦组加整网缺口 |
| r03-nrf9151-feather | ASG 第 03 轮最终导出（6 页） | 单个缺名控制脚 U8.4；29 个去耦组；DNP 件在冷跑中的缺口 |
| r04-host-usb-pmod | ASG 第 04 轮最终导出 | 小板基线 |
| r04-c1-return-moved | 第 04 轮门禁反例（C1 回流脚改接 +3V3） | 电容离开直连供电/回流对后从去耦组消失 |
| r05-lipo-charger | ASG 第 05 轮最终导出 | 回流在 BAT_NEG 的保护芯片去耦组；连接器 VBUS 候选组 |
| rh-ad8495-thermocouple | 2026-10-10 Claude 演练板 | AD8494 库符号 OUT 脚无名 → 严格自检失败；空导出日志 |
| rh-ad8495-thermocouple-nolog | 同上，不给 `--log` | 没有导出证据时 DOC-A01/A02 必须跳过 |
| rh-ad8495-thermocouple-pinmap | 同上，intent 只含官方脚表 | 缺名脚由完整官方脚表解决（5fa6d3b），去耦不再带整网缺口 |

日志模式 `empty` 指给 `--log` 但文件为空，这是 kicad-cli 干净导出时的实际情况；`none` 指不给 `--log`。

## 每例冻结的字段

`parse.strict_exit`、`parse.strict_db_written`、`parse.self_check_passed`、`parse.missing_functional_pins`、
`parse.parts`/`parse.nets`（夹具身份），`lint.DOC-A01_executed`/`lint.DOC-A02_executed`、
`plan.DOC-Q01`（applicability/readiness）、`plan.checks_total`、`plan.not_applicable`、
`decoupling.discovery_gaps`、`decoupling.pin_names_resolved_by_official_pinout`、
`decoupling.group_gaps`（键为 `状态/declared_id`，值为该组 gaps）。

## 答案怎么来的

候选值由 SR main@5fa6d3b 生成，然后逐项核对后冻结（2026-10-10），答案不由被测工具自己决定：

- 缺名脚：不经 SR 代码，直接读原始 XML，列出非无源/非 no_connect、`pinfunction` 和库引脚名都为空的节点，
  再按 DOC-Q01 的口径去掉连接器和跳线触点。
- 去耦组：从原始 XML 自算每组供电网与地网之间的两端电容，55 个组逐组一致；组上的缺口按规则逐条核对
  （自检失败→`netlist-integrity/export`，无回流网→`need-one-explicit-return-net`，非 Device 库电容→`component-kind`）。
- 器件清单、检查数、NA 数、DOC-Q01：对照方法文档逐行审读（小板逐项看过计划清单；冷跑没有 intent 声明，
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
- 去耦字段只锁定**清单**（哪些电容归哪组、缺什么证据），不是 PDN 或电气判决。冷跑里的保守分组
  （开关节点 SW、连接器 VBUS、无脚表时把 -VS 所在的 GND 当供电组）按合同是候选组、必须人工确认，
  冻结它们不表示这些分组在工程上正确。
- 检查数和 NA 数是回归锁：核对的是合理性，不是逐条独立推导的数目。规则表或展开方式有意改动时，
  这两个数会变，需要逐条说明后更新答案。
- 只有 6 块板、9 个用例，全部来自 ASG 2026-10 批次与一次演练，器件库以 KiCad 官方库、SparkFun、
  e-radionica 为主。没有覆盖的情形：kicad-cli 导出报错的日志、带 No_connect 被忽略告警的日志、
  `.kicad_sch` 直接输入（本基准只用已导出的 XML，不依赖 kicad-cli）、多装配状态、带完整 intent 的热跑、
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

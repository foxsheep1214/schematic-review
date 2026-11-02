# 候选持有、重归与隔离两侧模型：板子合并步 2A（2026-11-02）

基线 `7b2ce7d`，工作树 `boards-merge2a`；未 push。只读四条 lane 的归因、原 XML、db、手册和审查工作文件。
未改 SKILL.md、references/shared/、scripts/guideline_criteria.py、scripts/stress_check.py；未改 part_words.py、board_scans.py、parse_kicad.py 或 catalog.py。

## 修法

- 变换器候选必须有磁性储能与控制/反馈证据，或有齐纳基准和偏置的线性调整拓扑；开关声明本身不足。继电器低侧驱动、RF 负载开关与检测管不自动归为变换器，仍由驱动/器件检查覆盖。
- 候选从共享供电轨或地截止，物理共享 VIN 在未完成轨声明时也是边界；输入走线从共享轨起步同样截止。转换级显式引用其直接输入电容。
- 输入/输出/储能/去耦电容的持有引用不限，仍只有一个确定的记账所有者；开关与电感只属于一个独立功能，链和隔离对象的引用不抢所有权。其余平级冲突保留 own 决定。
- reject 先释放该候选，保留原决定与出处；同一成员仍被别的保留候选持有时不能被 add 取走。后续 add 用原成员物理网络/路径提供 via，不修改候选文件。
- 隔离器件侧别独立于单一器件角色，分别保存 mechanism、physical pins、nets、domain、basis、citation、unmapped_pins；AMC3311、REC15E、DP5305、HY931147C 用限定型号针表，其余用官方针表名称/绕组声明。缺侧别保留未知，不跨器件合并参考域。
- 光耦共地和继电器干触点没有地网均不消除隔离对象；同时触及两侧网的连接器进入隔离端点，例如 HY931147C 与 J3。纯无源/非数字隔离对象不套数字隔离器默认态/速率/CMTI，隔离连接与工作资格仍询问。
- 参考域中 ≥1 MΩ 及未知阻值不建立参考连接，地网等势键只过 ≤1 Ω；保留 0 Ω 真短接反例。域声明若点名实际地网，按其标签解析；不同页面同叶名地不因名字相同合域。
- EN/驱动的来源追踪另设 ≤10 kΩ 总串阻、最多三段；它是包含真实 4.7 kΩ（含容差）的发现包络，不是门限、漏电、时序或驱动能力的保证。原 ≤1 Ω 低阻等势路径不变。更高但 <1 MΩ 的三级栅极路径只作 CANDIDATE，MΩ 级不穿；不穿共享电源/地去搜其他输出。
- 已有真实上游输出供给 EN 时保存 supply-output 物理来源，不依赖本器件把供电脚命名为 VIN；排除自身伪输出来源。新增分数功率标注 `2k/1/8W` 的有界解析，避免实际 2 kΩ MCU 驱动路径被裁断，未知尾串仍拒绝。
- 上游 Buck 的 SW→输出电感不再作为下一级的额外输入滤波器；真实独立磁珠/电感滤波仍保留；记录级联源，逐轨供电和环路检查仍在，级联阻抗未完成电气闭环。
- 重复模式：已核 load_switch 不套 LDO dropout；没有受控储能开关的 RF 巴伦/共模磁件不套继电器式续流；Bridged 焊桥不凭 BRIDGE 子串生成输入保护。保持真实继电器、驱动磁件与保护支路反例。


侧别型号规则依据：TI AMC3311 SBASAQ5A p3 Table 5-1；RECOM REC15E-Z Rev3/2026 p7 单输出针表；SDAPO DP5300/5400/5500 2025 p3 §1.2；HanRun HY931147C REV.A/1 p1 电路图（图片型页已人工渲染核对）。限定型号规则和引用写进每个隔离对象的证据，原文件路径/哈希见同名 JSON。

## before / after 与口径

冷扫统计所有非 INFO 行（FINDING + CANDIDATE），不是缺陷数；已归因误报只匹配 lane 的 false_alarm 原错误内容。新的未裁决行保持未归因，不当成真缺陷。
候选数量和成员数分别列出；成员数是各候选引用数之和，包含合法共享引用，并非独立器件数。
before 冻结源码在 `/tmp/codex-work/boards-merge2a/baseline-sr`（git archive 7b2ce7d），原 db 不重解析。所有临时文件在 `/tmp/codex-work/boards-merge2a/`；受控结果在 `~/.cache/sr-boards/_merge2a/`。

| 板（完整 id 见附表 JSON） | 冷扫 before→after | 已归因冷扫误报 before→after | 候选数 before→after | 成员引用 before→after | 计划项 before→after |
|---|---:|---:|---:|---:|---:|
| cb-eval | 29→22 | 12→9 | 24→26 | 101→117 | 1555→1539 |
| urti | 14→14 | 5→5 | 13→15 | 338→179 | 1394→1462 |
| relay | 4→4 | 4→4 | 4→8 | 60→8 | 199→303 |
| cm4 | 49→49 | 20→20 | 31→18 | 445→169 | 1279→1839 |
| switch-v4 | 61→52 | 24→15 | 41→42 | 500→767 | 1932→1944 |
| gnssdo | 56→56 | 27→27 | 30→31 | 243→256 | 1407→1406 |
| bq27441 | 2→2 | 1→1 | 2→4 | 10→13 | 143→202 |
| hackrf-pro | 33→33 | 10→10 | 21→19 | 492→304 | 1644→1711 |
| dpp | 0→0 | 0→0 | 3→2 | 16→10 | 109→122 |
| chlinknet | 55→55 | 10→10 | 2→3 | 7→9 | 244→253 |

总冷扫 303→287，已归因冷扫误报 113→101；本批带审计合并扫描的非 INFO 行数与冷扫相同。域诊断单列：cb-eval 10→0，gnssdo 4→0，switch-v4 1→0；cm4 2→2 保留。计划项数的增减包括合法共享、隔离对象与重归，不是缺陷变化。

逐规则冷扫数（各格 before→after；没有变化也列出）：

| 板 | 规则计数 |
|---|---|
| cb-eval | NET-A01 4→4; NET-A07 4→4; PWR-A01 4→0; PWR-A02 2→0; PWR-A03 1→0; RST-A01 10→10; RST-A02 2→2; SIG-A03 2→2 |
| urti | DRV-A03 1→1; NET-A01 2→2; NET-A07 9→9; PRO-E02 2→2 |
| relay | NET-A04 4→4 |
| cm4 | NET-A01 9→9; NET-A06 4→4; NET-A07 6→6; PRO-E02 13→13; PWR-A01 7→7; PWR-A02 5→5; PWR-A03 1→1; RST-A01 4→4 |
| switch-v4 | DRV-A01 2→2; NET-A01 7→7; NET-A02 7→7; NET-A07 21→21; PRO-E02 2→2; PWR-A01 3→3; PWR-A05 5→0; RST-A01 6→6; RST-A03 2→2; RST-A04 6→2 |
| gnssdo | DOC-A04 4→4; DRV-A01 2→2; NET-A01 7→7; NET-A06 1→1; NET-A07 15→15; PRO-E02 4→4; PWR-A01 2→2; PWR-A02 14→14; RST-A01 2→2; RST-A04 4→4; SIG-A05 1→1 |
| bq27441 | PWR-A01 1→1; PWR-A02 1→1 |
| hackrf-pro | DRV-A03 1→1; NET-A02 1→1; NET-A07 17→17; PRO-E02 5→5; PWR-A05 1→1; RST-A01 2→2; SIG-A02 2→2; SIG-A03 4→4 |
| dpp | 无非 INFO 行 |
| chlinknet | NET-A01 45→45; NET-A06 5→5; NET-A07 5→5 |

关键模型复核：relay 的四个伪 POWER_CONVERTER 归零，新增四个光耦和四个继电器隔离对象；URTI 的 Q2/Q3/Q5 不再作为变换器（Q2 原候选 177 个成员），成员总引用 338→179。CM4 三 Buck 对 C302–C307 合法共享，bq27441 的 U2 可 reject 后 add。原 CM4、bq27441 的决定步骤为 exit 1，回退合并为 0；after 十板各五步全为 0。dpp 的 T1 不套数字隔离器专属项，chlinknet 的 U1/J3 同入 PRO-D02 端点对象。并非宣称 URTI lane 原 75 条归因全部消失：它们包含人工审查/计划对象，不能与这里冷扫 14 行等同。

before 的原决定链失败保留为失败，回退到带同一资料审计的无候选热扫合并，不冒充完整候选计划。after 每板的候选变化均重放决定：退休候选/已被新候选吸收的 add 去掉，新产生的物理隔离对象接受，释放的有源器件按原功能/实际节点重归，新增供电声明仅登记身份，不加电压。共享平级所有权按原所有者优先、否则稳定次序记账并明确“功能边界未确认”。独立功能未建立的泛称 IC 仅拒绝功能分组，仍保留全板 DEV 逐器件检查。所有这些调整见各板 decision-replay-notes.json、rail-identity-replay.json，不当作需求或电气 PASS。

## 真缺陷保留

14 条机器断言记录在 `after/true-defect-preservation.json`，表中“可定位”与“自动报出”分别核对：

| 板 | 保留证据 | 边界 |
|---|---|---|
| cb-eval、urti、relay、cm4 | 原归因 true_defect 都为 0；未新增缺陷结论 | 仍有待审/误报，不代表整板通过 |
| switch-v4 | U901/U1601 的 SIG-D11 及 CRSDV/TXEN/时钟三组物理连接保留；U302/U602 TPS26600 vs TPS26601、Z2201/Z2202 C3V3 vs C3V9 的 DEV-D01 与全板 DEV-D04 保留 | 双工不相容和两组料号冲突仍可定位 |
| gnssdo | U4.26 TXD2、U4.27 TXD3 的 NET-A07 仍报出；AP7361C U5/U11 的 DEV-D01 和 DOC-V02 保留，原 PDF 哈希不变 | 图上 1.5 A 注解与器件 1 A 能力仍需视觉/手册核对，没有新增自动额定值判决 |
| bq27441 | U1.10 BIN–R7(1.8 MΩ)–VSYS、R5 下拉的节点和 DEV-D05 保留；SDA/SCL 经 R2/R3 10 kΩ、默认双焊桥 JP1 到 5 V 的节点、装配与 DEV-C05 保留 | BIN 与 I²C 风险仍可定位，没有把工作窗未知改成通过 |
| hackrf-pro | Q4/Q5 重新归入保护后均有 PWR-T05/DRV-C02；U16 CRESET/CDONE 的原 RST-T04 rule_gap 保留 | U16 正常 STARTUP 项资格属于 2B，本轮不声称自动恢复 |

十板原 db SHA-256、原 voltage_v 窗口、assemblies 逐项不变。供电新增声明只有轨身份与网表引用，无电压猜测。

## 重复模式和保留项

处理了重复的 load_switch→LDO dropout（kimchi F30/F31）、无源 RF balun/choke→续流负载（amalthea F06/F07 与 URTI FL/T 多项）、Bridged 焊桥→整流保护，以及已供电 EN 仍判来源未知（switch U702/MAX941 类）。真实受控储能磁件、0 Ω 两地短接、≥1 MΩ 反例仍有测试。

未处理或只保留定位的模式：

| 模式 | 原因/处置 |
|---|---|
| relay NC1–NC4 的四条 NET-A04；各板器件定类、MCU/模块未用脚、计划资格 | 属于并行 2B 的脚义/分类/资格边界；保留原诊断，不越界修改分类文件或 catalog |
| cm4 的 GND/GNDD/VSS 两条参考域诊断 | 路径含 U403/R414，非已核隔离器的跨侧误并；域/装配关系尚不足，保留待核 |
| U16 CRESET/CDONE 的正常 STARTUP 覆盖 | 保留明确 rule_gap 指向，正常资格交 2B |
| 三端穿心电容、BAT54C 双二极管源路径（Amiga 多条） | 需要器件多单元针表与有向导通模型，不属于本轮候选持有/隔离边界；不能把全部电容/三脚封装短接来消提示，未改 |
| PCA9306 200 kΩ 偏置、LTC4418 原生方向、单例内部调压输出/HX711 串联 PNP 等 | 单例或准确脚义/模式证据未闭合，保留报告；不以放宽源定义掩盖 |
| 不明变压器绕组、未映射磁件屏蔽/LED 脚 | 两侧对象保留 unresolved/unmapped，不猜测端子；HY931147C 只绑定已核 PHY 与整流 PoE 两侧 |
| 输入级联源/负载阻抗 | 移除伪额外输入滤波后留 CASCADED_CONVERTER 诊断；稳定性、动态/PCB/EMC 没有被判通过 |

本轮没有宣称所有 false_alarm 已关闭；其余冷扫误报保留在附表 JSON 的逐行匹配和 lane 原归因中。新增未裁决行也未自动归为真缺陷。

归因输入索引包含 35 个已完成板记录；十个重放板的归因哈希均未变。期间非重放板 poe-usb-c-pd-converter 的记录继续更新，同名 JSON 单列其初始/复核哈希，不用于本表数值。

## 门禁、提交和复现

- 全量单元/合同/板级测试：`python3 -m pytest scripts/tests -q`，2604 passed、2 skipped；运行使用任务 TMPDIR、禁写 pyc/cache。
- 逐批变异门（门槛为 unit 全杀）：A 32/32、B 116/116；最终 C 53/53。新增 M912–M938 共 27 条，不占用 M960 起的 2B 编号。M914/M921 因新等价路径/重复匹配重锚；M205/M206/M208 随解析式结构更新锚点，原功率/电压反例保留。最终未变异副本先通过 unit 基线；中途工程变动中的结果不作门禁证据。
- 种子：同一冻结 7b2ce7d 基线，254 个位点、225 自动、0 错误，after 逐位点目标自动规则无退化；真实板缓存参与的四板种子与 32 个离线典型板均保留。原准则库 1.6.1 的自动层与计划提示分开统计。
- 典型电路：203 DETECTED / 185 FIXED / 14 KNOWN_FALSE_ALARM，0 未分类；原生回放 195/195、0 MISMATCH。
- 原生约定新增 `boards-merge2a-v1`，只把 rf2-hv-flyback-lt3957a 的检查数 97→95：删掉没有独立输入滤波器的 PWR-E03.U1-5V.5V、PWR-C11.U1-5V.5V。真实 SW/TR1 的 DRV 对象保留，历史 XML、intent、各旧约定字节不改；manifest 绑定父版本与新文件哈希。
- `evals/detection/RESULTS.md` 按最终结果重生成；台账 Event 用用户原文，`python3 scripts/check_ledger.py` PASS。
- 临时预览和过程日志只在 `/tmp/codex-work/boards-merge2a/`；最终门禁日志、重放脚本和 SHA 在 `~/.cache/sr-boards/_merge2a/after/gates/` 与报告同名 JSON，未 push。

复现冷扫与候选链（`DB` 为原缓存 db，`AUDIT` 为原资料审计，`OUT` 为对应 before/after 板目录）：

```sh
python3 -B scripts/lint.py "$DB" --intent "$OUT/intent-cold.json" --plan-json "$OUT/plan-cold.json" --json "$OUT/lint-cold.json"
python3 -B scripts/circuit_candidates.py "$DB" --intent "$OUT/intent-input.json" --datasheet-audit "$AUDIT" --json "$OUT/candidates.json"
python3 -B scripts/circuit_decisions.py "$OUT/intent.json" "$OUT/candidates.json" --db "$DB" --write
python3 -B scripts/lint.py "$DB" --intent "$OUT/intent.json" --datasheet-audit "$AUDIT" --candidates "$OUT/candidates.json" --plan-json "$OUT/plan-candidates.json" --json "$OUT/lint-candidates.json"
python3 -B scripts/lint.py "$DB" --intent "$OUT/intent.json" --datasheet-audit "$AUDIT" --candidates "$OUT/candidates.json" --merge-plan "$OUT/plan-candidates.json" --plan-json "$OUT/plan.json" --json "$OUT/lint.json"
```

before 第二步使用 intent-cold，原决定失败的两板保留失败日志并按前述回退。完整重放及迁移步骤在 `after/gates/replay.py`、`migrate_replay.py`；从目标 SUT 工作目录执行，before 须使用冻结 7b2ce7d 源码。所有原输入和输出清单、各阶段 exit、逐规则统计、资料哈希、14 条真缺陷/定位记录见同名 JSON 及缓存。

```sh
TMPDIR=/tmp/codex-work/boards-merge2a PYTHONDONTWRITEBYTECODE=1 python3 -m pytest scripts/tests -q -p no:cacheprovider
TMPDIR=/tmp/codex-work/boards-merge2a PYTHONDONTWRITEBYTECODE=1 python3 evals/mutation/run.py --changed --tier unit --jobs 5
TMPDIR=/tmp/codex-work/boards-merge2a python3 -B evals/seeded_bench/run.py --offline --boards-cache ~/.cache/sr-boards --compare ~/.cache/sr-boards/_merge2a/before/seeded/results.json --out ~/.cache/sr-boards/_merge2a/after/seeded
python3 -B evals/detection/run.py --seeded ~/.cache/sr-boards/_merge2a/after/seeded/results.json --typical ~/.cache/sr-boards/_merge2a/after/gates/typical-current.json --replay ~/.cache/sr-boards/_merge2a/after/gates/native-results.json --work /tmp/codex-work/boards-merge2a/detection
python3 scripts/check_ledger.py
```

实现提交：`1587346`（候选/持有/释放）、`ec350aa`（隔离两侧）、`af12641`（源路径/输入滤波/重复模式）。文档与结果另作本地提交；不 push。


## 文件清单

- `docs/improvement-ledger.md`
- `docs/proposals/boards-merge-2a-2026-11-02.json`
- `docs/proposals/boards-merge-2a-2026-11-02.md`
- `evals/detection/RESULTS.md`
- `evals/kicad_replay_bench/README.md`
- `evals/kicad_replay_bench/revisions/boards-merge2a-v1/cases.json`
- `evals/kicad_replay_bench/revisions/boards-merge2a-v1/expected.json`
- `evals/kicad_replay_bench/revisions/boards-merge2a-v1/manifest.json`
- `evals/kicad_replay_bench/revisions/boards-merge2a-v1/sources.json`
- `evals/kicad_replay_bench/run.py`
- `evals/mutation/mutations.json`
- `references/architecture.md`
- `references/checker-conventions.md`
- `references/intent-format.md`
- `scripts/checkers/domains.py`
- `scripts/checkers/inductive_load.py`
- `scripts/checkers/input_filter.py`
- `scripts/checkers/isolation_sides.py`
- `scripts/checkers/netgraph.py`
- `scripts/checkers/power_switch.py`
- `scripts/checkers/power_up.py`
- `scripts/checkers/powertree.py`
- `scripts/circuit_candidates.py`
- `scripts/circuit_decisions.py`
- `scripts/lint.py`
- `scripts/plan_circuits.py`
- `scripts/solve_dividers.py`
- `scripts/tests/test_boards_merge2a.py`
- `scripts/tests/test_circuit_candidates.py`
- `scripts/tests/test_circuit_decisions.py`
- `scripts/tests/test_domains.py`
- `scripts/tests/test_inductive_load.py`
- `scripts/tests/test_isolation_sides.py`
- `scripts/tests/test_render_and_pack.py`
- `scripts/tests/test_source_paths.py`

原因按 15 个机制计数：持有角色、reject 释放、共享轨截止、隔离对象保留、跨侧端点覆盖五项为 rule_not_enforced；变换器拓扑、侧别针表、泄放参考、数字隔离专属项、驱动源阻抗、上游储能、load_switch dropout、无源磁件、Bridged 子串九项为 knowledge_wrong；分数功率标注解析为 knowledge_missing。不是按诊断行数计数。

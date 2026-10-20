# SR 训练工作流：用真值闭环提高审查能力，压掉过严判断

执行者：任意 agent（Codex、Claude 等）。本文件是完整的作业指令；人只在第 5 阶段裁决，以及决定是否提交。
目标只有两个，且代价不对称：**找到真正的风险点**（漏掉一条绝缘/端口过压类真风险 ≫ 多报一条 P0），
**不出现过严判断**（在已量产多年的板上把普通缺资料顶成 P0/FAIL）。

## 0. 原则（违反任何一条即停止本轮）

1. **只有真值能当奖励信号。** 真值只有三类：作者修复过的真缺陷（第 1.1 节）、已量产成熟板上的报出（第 1.2 节）、
   人的裁决（第 5 节）。另一个 agent 对报告的"读后感"不是真值，只能产生候选问题。
2. **改 SR 必须带证据。** 每放宽一条规则，同时提交一块它曾过严的板和一块它仍必须报出的板；每条改动先写失败的测试。
3. **真值文件 agent 不能改。** `evals/training/corpus/*.json`、`evals/training/adjudications/*`、
   `evals/typical_circuits/cases.json` 的 `expected`、`evals/kicad_replay_bench/revisions/*/expected.json`、
   `evals/scenarios/*.md` 只能由人写或签。改进 agent 把 `known_false_alarms` 移到 `fixed_false_alarms` 可以，删 `expected` 不行。
4. **训练集与留出集分开。** 改进只能看训练集；留出集的数字只在人说"评估"时算一次，不反馈给改进 agent。
5. **方法文档也是训练对象。** 过严往往来自 `references/verdicts-and-release.md` 一类的分级表和填表要求，不只是代码。

## 目录

```
evals/training/
  README.md                 本文件
  critic/rubric.md          批评 agent 的逐条评分清单（盲评）
  corpus/
    fix-pairs.json          真值 A：缺陷—修复对（人签）
    mature-boards.json      真值 B：已量产成熟板（人签）
    split.json              训练/留出划分，按仓库划分（人签）
  adjudications/
    YYYY-MM-DD.json         真值 C：人工裁决
    TEMPLATE.json
  runs/
    YYYY-MM-DD-<sr-sha>/    每轮产物：reviews/、critic/、metrics.json、summary.md（不进 git，summary.md 进）
  scripts/                  由执行 agent 按第 7 节接口实现
```

## 1. 语料建设（阶段 1）

### 1.1 缺陷—修复对（fix pairs）

来源，按优先级：
1. **Olimex**（github.com/OLIMEX）：多数仓库 `HARDWARE/` 下按 Rev 存 KiCad 工程，README 的 changelog 逐版写
   "Rev X: fixed …"。先扫已在 `evals/typical_circuits`/`seeded_bench` 用过的仓库（ESP32-POE-ISO、ESP32-C3-DevKit-Lipo、
   RVPC、iCE40HX1K-EVB…），再扫其余 KiCad 6+ 仓库。
2. **SparkFun / Adafruit / Soldered / CoreElectronics** 的 Rev 说明与 issue 里的硬件勘误。
3. GitHub 提交历史：`.kicad_sch` 改动且提交信息含 fix / wrong / reversed / missing / swapped / pull-up / polarity 的 commit，
   前后两个 commit 就是一对。用 `scripts/diff_netlists.py <old db> <new db>` 定位改动的网/脚。

收录条件：KiCad 6+（kicad-cli 10 能导出；KiCad 5 `.sch` 不收）、许可证明确、缺陷是**电气**的（连接、极性、缺件、值、
上下拉、保护）而不是丝印/封装/布局、作者原话能证明那是缺陷而非改进。目标 20–30 对，先 10 对就可开始。

`corpus/fix-pairs.json` 每条：

```json
{"id": "olimex-esp32-poe-iso-revH-revI",
 "repo": "https://github.com/OLIMEX/ESP32-POE-ISO", "license": "CERN-OHL-S-2.0 (README)",
 "before": {"commit": "<40 位>", "schematic": "HARDWARE/Rev.H/ESP32-PoE-ISO_Rev_H.kicad_sch"},
 "after":  {"commit": "<40 位>", "schematic": "HARDWARE/Rev.I/ESP32-PoE-ISO_Rev_I.kicad_sch"},
 "author_statement": "README changelog 原话，带 URL 与日期",
 "defect_class": "connectivity|polarity|missing-part|value|pull|protection|power-sequence",
 "defect_location": {"refs": ["R12"], "nets": ["/EN"]},
 "expected_rules": ["RST-A01"],
 "hazard": "none|component|function|safety",
 "split": "train|holdout"}
```

`expected_rules` 与 `hazard` 由人填（第 5 节）；agent 只填其余字段，并在 `author_statement` 里保留出处。
`defect_location` 用 `diff_netlists.py` 的差异网与作者原话交叉确认，差异里与缺陷无关的改动不写进去。

### 1.2 成熟板（mature boards）

已量产多年、仍在售的开源板。从 `evals/typical_circuits/sources.json` 起步，每块补 `production_evidence`
（在售页面 URL、首发年份、当前 Rev），再按 1.1 的来源补到 40 块以上。`corpus/mature-boards.json` 每条：
`{"id", "repo", "commit", "schematic", "license", "production_evidence", "years_in_production", "split"}`。
这些板上 SR 报出的每一条 FAIL 和潜在 P0 都是**误报嫌疑**，由批评 agent 和人逐条判。

### 1.3 划分

`corpus/split.json` 按**仓库**（不是按板）分训练/留出，约 70/30；同一仓库的所有板只进一边。人签。

## 2. 基线（阶段 2，每轮开始时跑一次）

对当前 SR（记录 `git rev-parse HEAD`）：

```sh
python3 -B evals/typical_circuits/run.py --json runs/<round>/typical.json
python3 -B evals/seeded_bench/run.py --cache <缓存> --out runs/<round>/seeded
python3 -B evals/kicad_replay_bench/run.py --out runs/<round>/replay
python3 -B evals/training/scripts/run_review.py --corpus fix-pairs,mature-boards --split train --mode cold --out runs/<round>/reviews
```

冷跑（parse + lint + plan）每块几秒，全语料都跑。**热审**（带 intent、原厂资料、由审查 agent 按 SKILL.md 完整做出
review-results / gate / 报告）每轮只做 3 块：1 块 fix pair 的 before 版、2 块成熟板，轮换选取，产物与真实审查同格式。
只有热审能产生 P0/待办，所以过严率的主要来源是这 3 块；冷跑产生 FINDING/CANDIDATE，用来算召回与冷跑误报。
fix pair 的 before 版可以只热审缺陷所在的功能电路：intent 只声明这些电路，`review-results.json` 写 `review_scope`
（见 [计划与结果台账](../../references/plan-and-results.md#顶层字段)），校验只要求这些框架的行；这样一对的热审成本是一个功能而不是整板，
但它不是整板结论，`fix_pair_recall_hot` 只看其中位置点名缺陷的 DEFECT finding。

## 3. 批评 agent（阶段 3，盲评）

- **模型家族必须不同于审查 agent**（例如审查用 Claude，批评用 GPT 系，反之亦然）。
- **盲评**：输入是原理图 PDF/网表 db、该板的原厂资料目录、以及**一条**发现（规则、对象、结论、等级）；
  **不给**审查员的 rationale、缺口的 severity 说明、report 正文。目的是让它独立判断，而不是被说服。
- 逐条按 [critic/rubric.md](critic/rubric.md) 打分，输出 `runs/<round>/critic/<board>.json`，每条：

```json
{"check_id": "PRO-C01.AC-INPUT.F1", "stated_level": "P0",
 "hazard_path_named": false, "protection_present": "F101 为 IEC 60127 H 型 1500 A 分断熔断器（BOM/库名）",
 "data_actually_available": "Littelfuse 3831 系列规格书第 2 页给出分断能力",
 "verdict": "OVER_STRICT|TRUE_RISK|UNDERGRADED|CANNOT_TELL",
 "proposed_level": "P1", "reason": "……", "evidence": [{"source": "...", "locator": "..."}]}
```

- 批评 agent **不改 SR、不改报告**，只产清单。它的 `OVER_STRICT`/`UNDERGRADED` 不是结论，是送人裁决的候选。
- 对 fix pair 的漏检不用批评 agent：`metrics.py` 直接按 `defect_location` 判有没有发现/检查指到那里。

## 4. 指标（阶段 4，`scripts/metrics.py` 产 `runs/<round>/metrics.json`）

| 指标 | 定义 | 方向 |
|---|---|---|
| `fix_pair_recall_cold` | before 版冷跑中，有 FINDING/CANDIDATE 点名 `defect_location` 任一 ref/net 的对数 / 总对数 | ↑ |
| `fix_pair_recall_plan` | 计划里有逐对象检查指向该位置的对数 / 总对数（同 seeded 的"计划指向"列） | ↑ |
| `fix_pair_recall_hot` | 热审过的 before 版中，FAIL 或阻断 INSUFFICIENT 点名该位置的比例 | ↑ |
| `seeded_recall` | `seeded_bench` 自动检出 / 位点 | ↑，不得降 |
| `mature_cold_false_alarms` | 成熟板冷跑每 100 条检查的 FINDING（不含 CANDIDATE）数；其中经裁决为误报的另计 | ↓ |
| `mature_hot_p0_per_100` | 成熟板热审每 100 条检查的潜在 P0 + FAIL 数 | ↓ |
| `p0_precision` | 热审潜在 P0 中，人裁决为 TRUE_RISK（能说出 FIRE/SHOCK/INSULATION/HAZARDOUS_ENERGY/PORT_OVERVOLTAGE/PROTECTION_LOSS 路径）的比例 | ↑ |
| `todo_density` | 热审每 100 条检查的待办件数；`external_data_share` = 缺资料原因占 INSUFFICIENT 的比例 | ↓ |
| `misfile_rate` | 阻塞冻结的 INSUFFICIENT 中，经裁决应为“阶段 NA/移交”（固件镜像、实测）或“审查没算完/设计任务”（资料已读只差计算）的比例；先用 `FIRMWARE_IMAGE_RECORDED_AS_DESIGN_GAP` / `CALCULATION_RECORDED_AS_DATA_GAP` 粗算，再抽样裁决 | ↓ |
| `duplicate_item_share` | `DUPLICATE_WORK_ITEMS` 命中的待办 / 总待办 | ↓ |
| `lookup_honesty` | 批评 agent 抽查“已读 X 第 N 页”声明（每板 ≥5 条）中，该页确实含所述内容的比例 | 必须 ≥ 0.9 |
| `closure_rate` | 同一块板连续两轮（SR → ASG 处理 → SR）之间，上一轮待办在下一轮被关闭（PASS 或 NA/移交且前提 PASS）的比例；只对真实设计迭代算 | ↑ |
| `consistency` | `evals/consistency_bench` 跨 agent 一致率 | ↑ |
| `typical_gate` | `typical_circuits/run.py` 的 MISSED/UNCLASSIFIED/FALSE_ALARM_BACK 计数 | 必须 0 |
| `replay_gate` | `kicad_replay_bench` MISMATCH 计数 | 必须 0 |

`compare.py` 对比上一轮：任何 ↑ 指标下降、任何门指标非 0，改进 agent 的改动不得进入 summary 的"通过"栏。
召回先于过严：同一轮里 `fix_pair_recall_*` 或 `seeded_recall` 下降，不论过严率改善多少都算失败。

### 4.1 2026-10-18/19 两轮真实板审查暴露的度量盲区

- **提示可以被“写法”绕过**：加了 `ACQUISITION_WITHOUT_LOOKUP` 后，下一轮每条请求都带上“已读 X 第 N 页”，提示归零但缺口没变。
  所以提示数不是指标；`lookup_honesty` 抽查声明是否属实，才是。任何新加的筛查，上线后第一轮都要看它是被解决了还是被绕过了。
- **阶段错放比过严更常见**：一次真实板审查的 35 件待办里约 8 件（约 75 条检查）是固件配置/烧录，约 7 件是“资料已读只差计算”；
  它们把原理图冻结卡住，但既不是过严判级也不是真缺口。`misfile_rate` 单列，裁决模板的 `decision` 增加 `MISFILED_STAGE` 和 `MISFILED_CAUSE`。
- **同一块板反复审查看不出 SR 进步**：同一真实板三轮待办 22 → 22 → 35，数字无法比较，因为计划、器件声明和审查员都在变。
  进步只能在固定语料（fix pairs、成熟板）上量；真实板只用来算 `closure_rate`，并且必须有 ASG 处理过的中间版本。

## 5. 人工裁决（阶段 5，每轮 ≤ 10 条）

送裁决队列的只有三类：批评 agent 判 `OVER_STRICT`/`UNDERGRADED` 的条目；fix pair 漏检；改进 agent 申请放宽规则时附的
"曾过严"与"仍须报出"两块板。按 [adjudications/TEMPLATE.json](adjudications/TEMPLATE.json) 写，每条给出：
裁决（TRUE_RISK / OVER_STRICT / UNDERGRADED / NOT_A_DEFECT / DEFECT_MISSED / MISFILED_STAGE / MISFILED_CAUSE）、理由、硬件依据（规格书页码或标准条款）、
**落到哪**：`scenarios/*.md` 判例、`typical_circuits/cases.json` 的 `expected`/`known_false_alarms`、
fix-pairs 的 `expected_rules`/`hazard`、或 `references/*.md` 的边界例子。裁决一经写入即为真值，后续轮次不再重判。

## 6. 改进 agent（阶段 6）

可见输入：训练集上的 critic 清单、裁决、`metrics.json`、`known_false_alarms`。不可见：留出集的任何产物。

每条改动的硬要求：
1. 先写一个在当前代码上失败的单测（合成小板，放 `scripts/tests/`），再改代码或方法文档。
2. **放宽**（少报、降级）必须同时附：一块它曾过严的板（成为 `fixed_false_alarms`）+ 一块它仍必须报出的板
   （`expected` 仍 DETECTED，或 seeded 位点仍检出）。只有前者的放宽不接受。
3. **收紧**（多报、升级）必须附至少一对 fix pair 或 seeded 位点作为它抓到的东西，并在成熟板上跑一遍看新增 FINDING，
   新增的每条要么是 `expected`（有理由）要么立即判为误报并修正。
4. 改分级/方法文档（`references/verdicts-and-release.md`、`plan-and-results.md`、`report-and-remediation.md`）时，
   在 `runs/<round>/summary.md` 写明哪条裁决支持这条改动。
5. 改完跑第 4 节全部门指标 + 两层测试与变异门：合同层 `python3 -m pytest scripts/tests -m contract -q` 先过（改了规则判据就同步改 `evals/rule_contracts/boards/` 的触发板/近似板，新规则必须新增合同）；全量 `python3 -m unittest discover -s scripts/tests -q`（含措辞层 golden 报告，措辞改动用 `SR_UPDATE_GOLDEN=1` 重写并在 summary 里说明）；`python3 evals/mutation/run.py --tier unit` 每条变异 KILLED，改了的判据要在 `evals/mutation/mutations.json` 加对应变异。
6. 不碰第 0 节第 3 条列的真值文件；需要改 `expected` 就写进裁决队列等人。
7. 不默认加字段、筛查或结论词：先查现有的能否表达，能就复用；确需新增，在 `summary.md` 写明现有哪一项覆盖不了。新脚本按 [脚本分类](../../references/automation.md#脚本分类) 归类。

产物：代码/文档 diff、`summary.md` 的"改动—证据—指标变化"表。是否提交由人决定。

## 7. 要实现的脚本接口（`evals/training/scripts/`）

| 脚本 | 输入 | 输出 |
|---|---|---|
| `build_fix_pairs.py --repo URL [--rev-dir HARDWARE]` | 仓库、两个 commit/Rev | 拉取到缓存、kicad-cli 导出前后 XML、`parse_kicad.py` 得 db、`diff_netlists.py` 差异、生成待人填的 fix-pairs 条目草稿 |
| `run_review.py --corpus … --split … --mode cold|hot --out DIR` | 语料、SR 检出 | 每板 `db.json`、`lint.json`、`plan.json`；hot 模式只准备输入包（db、intent 草稿、资料目录清单），审查本身由审查 agent 按 SKILL.md 完成 |
| `critic_pack.py --review DIR --out DIR` | 一次审查的记录 | 每条 FAIL/潜在 P0 一个盲评输入包（原理图、资料、该条发现；剥掉 rationale） |
| `metrics.py --round DIR --corpus … --adjudications DIR` | 本轮产物 | `metrics.json`，按第 4 节定义 |
| `compare.py A/metrics.json B/metrics.json` | 两轮 | 增减表 + 门指标判定，退出码 1 表示有退步 |

第三方文件只留缓存目录（`--cache`），进仓库的只有导出后去掉本机路径的 XML 夹具与许可证记录，
格式同 `evals/typical_circuits/fixtures/LICENSES.md`。

## 8. 一轮的完整顺序

1. 记 SR sha，建 `runs/<date>-<sha>/`。
2. 跑第 2 节基线（冷跑全语料 + 3 块热审）。
3. 批评 agent 盲评 3 块热审的全部 FAIL/潜在 P0；`metrics.py` 算 fix pair 召回。
4. 生成裁决队列（≤ 10 条），**停下等人**。
5. 拿到裁决后，改进 agent 按第 6 节改，跑门指标，写 `summary.md`。
6. 人看 summary 决定提交；提交后下一轮换 3 块热审板。
7. 每 5 轮：人宣布一次留出集评估，只算数字，不反馈细节给改进 agent；留出集数字不升说明在过拟合训练集，回到第 1 节扩语料。

## 9. 前三轮的具体安排

- **第 1 轮**：建 10 对 fix pairs（Olimex 优先）+ 给现有 42 块 typical 板补 `production_evidence`；热审真实板 before 版无需做，
  改用 `flyback-viper22a`（已知 3 处真缺陷）、`moteus-c1`、`bms-c1`。批评 agent 先在一份已有人工裁决的真实板报告上试跑，看它能否独立指出其中已判过严与已判合理的条目——能，才启用。
- **第 2 轮**：fix pairs 到 20 对；首次算 `p0_precision`；改进 agent 只允许改 `known_false_alarms` 对应的规则。
- **第 3 轮**：开放方法文档改动；首次留出集评估。

## 10. 不做的事

- 审查 agent 不评价 SR：报告的 summary/items 只说这块板，SR 的问题写 `sr_feedback`；
  “本次 SR 改进效果对照”是另一个任务（回归评估），由改进 agent 在固定语料上做，不混进设计者报告。
- 审查 agent 看不到上一轮 SR 改了什么（不给 diff、不给 commit message），否则它会按改动点“表演”合规。

- 不用 agent 互评的分数当指标；不让审查 agent 看批评结果后重写同一份报告再评。
- 不为了让 `p0_precision` 好看把真风险降级：绝缘屏障、保护件额定、端口过压这三类一律保持 P0 候选，由人裁。
- 不把 `evals/typical_circuits` 的 `expected` 当缺陷真值——它们多数是审查线索；缺陷真值只来自 fix pairs、seeded 位点和裁决。
- 不在同一批板上既训练又评估。
- 不把“提示数下降”当成改进证据；提示是给人看的线索，改进只以第 4 节的召回/精度/错放率说话。

## 11. 与 ASG 的闭环（真实板）

真实板走 SR → ASG → SR：
1. SR 出报告；ASG 按其 `review-comments.md` 逐条登记处理方式（REDESIGN / DESIGN / OBTAIN_DATA / HANDOFF / DECLINE）。
2. ASG 交付新版（含设计报告、design-closure.json、配置表、BOM 约束），SR 以新版为输入重审，`history_inputs` 声明上一版报告。
3. 算 `closure_rate`，并逐件看“没关闭”的原因：ASG 没做（设计侧欠账）、ASG 做了 SR 不认（SR 的关闭条件不可达，回到裁决）、
   ASG 用 DECLINE 顶回（看依据是否成立，成立就是 SR 过严的判例）。
4. 连续两轮 ASG 的 DECLINE 被裁决为成立的规则，进改进 agent 的放宽队列；连续两轮 ASG 没做的项，进 ASG 的“设计闭合项”清单
   （`requirements-to-intent.md` 第 4 节），让下一次设计一次算清。


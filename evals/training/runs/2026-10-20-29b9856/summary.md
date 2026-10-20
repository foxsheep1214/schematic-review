# 训练第 1 轮 · 2026-10-20 · SR 29b9856

状态：**停在第 8 节第 4 步（裁决队列已生成，等人）**。没有任何规则改动进入本轮。

## 跑了什么

| 步骤 | 结果 |
|---|---|
| 基线 typical_circuits（42 块） | DETECTED 128 / FIXED 180 / KNOWN_FALSE_ALARM 3；MISSED、UNCLASSIFIED、FALSE_ALARM_BACK 均 0 |
| 基线 kicad_replay（state-invariant-v1） | 195 MATCH / 0 MISMATCH |
| 基线 seeded_bench | 门通过；`seeded_recall` 0.882（自动检出/位点），低于 1 的缺陷类：D-I2C-PU 0.69、D-GND-PIN 0.70、D-EN-FLOAT 0.79、D-RAIL-SPLIT 0.79、D-CAP-POL 0.82 |
| 语料 | 签过的 fix pairs 0 对、成熟板 0 块。本轮起草 3 对（Olimex ESP32-PoE-ISO Rev M→M1、M1→N、N→N1），42 块 typical 板充当成熟板代理；都在 `corpus-draft/`，未入 `corpus/` |
| 冷跑 | 45 块板全部 parse + lint + plan（`reviews/`，不入库） |
| 热审 3 块 | **未做**（需要审查 agent 按 SKILL.md 完整审 3 块板，每块带 intent 与原厂资料） |
| 批评 agent | **未做**（README 要求另一模型家族；本会话只有同家族） |
| 裁决 | 队列 10 条已生成（`adjudication-queue.json`），等人 |
| 改进 agent | 未启动（README §0：没有裁决就不许改规则） |

## 指标（`metrics.json`）

| 指标 | 本轮 | 怎么读 |
|---|---|---|
| fix_pair_recall_cold | 0.667（名义） | **实际 0/3**。两处“命中”是同网/同器件上的无关条目：M1→N 对命中的是 RST-A01 对 /ESP_EN 上拉的泛候选，N→N1 对命中的是 U1 另一个电源脚的 PWR-A02。按位置点名的定义会高估 |
| fix_pair_recall_plan | 1.0（名义） | **实际 0/3**。任何 IC 都有 DEV 行，所以“计划里有行指向该器件”恒真。没有一行问到缺陷本身（输出钳位、PG→EN、电平域） |
| fix_pair_recall_hot | null | 没有热审 |
| seeded_recall | 0.882 | 基线 |
| mature_cold_false_alarms | 0.47 /100 行 | 22 条 FINDING / 4657 行；NET-A01 占 12（7 条在同一块板的未用调制解调器线上），NET-A07 3，PWR-A01/A02 各 2 |
| p0_precision / misfile_rate / lookup_honesty | null | 都要热审 + 批评 agent + 裁决 |
| typical_gate / replay_gate | 0 / 0 | 通过 |

## 三对缺陷为什么冷跑一条都抓不到

三处都是**缺件**（少 TVS、少 PG→EN 电阻、少下拉）。SR 的逐对象行挂在**存在的**器件上，能问“这件东西对不对”，问不出“这里该有而没有”。会问这类问题的科目（防护链 PRO-C01、使能来源 RST-T01、电平域 SIG-D04/T04）都在功能电路框架里，而框架只从声明的 intent 生成；本轮 Olimex 板没有 intent，`plan.functions` 为空。
两条附带观察：before 版 M1 的 `power_up` 抽取已经记录了 U7 的 PG 脚悬空（`unconnected-(U7-PG-Pad6)`），只是没有规则把“稳压器 PG 没用而下游有 EN”变成一行；N 版 Net-(D7-A) 上 D7/R18/U1.9 的结构在 as-built 状态下没有任何行覆盖。

## 过程中发现的问题

1. **循环只是规格**：README 第 7 节五个脚本一个都不存在，`corpus/` 全空，`runs/` 没有历史轮。本轮补了 `run_review.py`（cold + hot 输入包）、`metrics.py`、`compare.py`；`build_fix_pairs.py`、`critic_pack.py` 仍缺。
2. **召回指标定义会高估**（见上表）。要么改为“命中行的科目/规则在 `expected_rules` 内”（需要人先填 expected_rules），要么把位置命中降为“计划触达”辅助列。
3. **`runs/.gitignore` 把 `metrics.json` 也忽略了**，而 `compare.py` 要上一轮的 metrics；已改为保留 `metrics.json`、`corpus-draft/*.json`、`adjudication-queue.json`。
4. **收录条件难以机械判定**：3 对里只有 N→N1（“prevent accidental overvoltage”）明确是缺陷；M→M1（“increase reliability”）、M1→N（“works better … suggested by a customer”）措辞像改进。Olimex 的 changelog 里真正说“fixed”的多数是布局/封装。10 对的第 1 轮目标靠 Olimex 一家难凑齐。
5. **Olimex 全部 Rev 在同一 commit 的不同目录下**，fix-pairs 模板里 before/after 两个 commit 字段退化为同一个 sha；模板应允许“同 commit 不同路径”。
6. **成熟板语料缺 `production_evidence`**，42 块 typical 板只能当代理；`split.json` 按仓库划分也还没人签。
7. **热审是整个循环的成本中心也是唯一的 P0 来源**，但 README 没写热审的 intent 从哪来（成熟板没有需求文档）。没有 intent 就没有功能电路框架，热审会退化成冷跑加人读图。
8. **批评 agent 的“另一模型家族”在当前工具链里没有现成入口**，需要人接外部模型或先放宽为同家族盲评并记录。
9. README §4.1/§9/§11 与 §3 示例里残留了一块已审设计的轮次与记录号，违反“SR 内容不带项目先验”的约束，本轮已中性化。
10. 解析侧：Olimex 板 FET1–3 缺引脚名使 `parse_kicad` 严格自检退出码 2（db 仍写出）；training 冷跑按 README 记录 `parse_exit` 不中断，但 42 块代理板里也有 resonare-lcc、moteus-c1 等退出 2，成熟板语料入库前要先过严格解析。

## 进化效果

**本轮为零**：没有裁决，README §0 不允许任何规则改动，`compare.py` 也没有上一轮可比。本轮的产出是让下一轮能跑起来的脚手架、三对待签样本、十条待裁决项，以及两处度量定义问题。真正能衡量“SR 进步”的数字要等：人签 fix pairs 并填 `expected_rules`（召回才能按规则算）、做 3 块热审（才有 P0 与过严率）。

## 等人做的事

- 裁决 `adjudication-queue.json` 的 10 条（3 条 fix pair 收录与期望规则，7 条成熟板冷跑 FINDING）。
- 决定是否把 `corpus-draft/` 的 3 对合入 `corpus/fix-pairs.json`，并签 `split.json`。
- 决定批评 agent 用哪个外部模型，以及热审 3 块板（README §9 建议 flyback-viper22a、moteus-c1、bms-c1）的 intent 来源。

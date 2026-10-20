# 训练第 1 轮 · 2026-10-20 · SR 29b9856 → 本轮改动

状态：**走完第 8 节 1–5 步**（基线、冷跑、裁决、改进、门指标），热审与批评 agent 两步缺席（见“问题”）。

## 跑了什么

| 步骤 | 结果 |
|---|---|
| 基线 typical_circuits（42 块） | 改动前 DETECTED 128 / FIXED 180 / KNOWN_FALSE_ALARM 3；改动后 117 / 180 / 14（11 条按裁决从 expected 移到 known_false_alarms）；失败行始终 0 |
| 基线 kicad_replay（state-invariant-v1） | 改动前后都 195 MATCH / 0 MISMATCH |
| 基线 seeded_bench | 门通过；`seeded_recall` 0.882 不变。低于 1 的缺陷类：D-I2C-PU 0.69、D-GND-PIN 0.70、D-EN-FLOAT 0.79、D-RAIL-SPLIT 0.79、D-CAP-POL 0.82 |
| 语料 | 起草 3 对（Olimex ESP32-PoE-ISO Rev M→M1、M1→N、N→N1，草稿在 `corpus-draft/fix-pairs-draft.json`）。裁决后 **1 对入库**（N→N1，CH340X RXD 被 5 V 上拉进 3.3 V I/O 域，defect_class pull）；M→M1（buck 输出加 TVS）与 M1→N（PG 门控 EN）判为改进不收录，后者初判收录、经 agent 电路复核后改判。42 块 typical 板充当成熟板代理（`corpus-draft/mature-boards.json`，`production_evidence` 未补） |
| 冷跑 | 45 块板 parse + lint + plan（`reviews/`，不入库） |
| 热审 3 块 | 做了 **1 块局部试点**：fix pair before 版，只审声明的 UART/LEVEL_SHIFT 两个功能电路（12 行 + 2 个功能判定，`review_scope` 台账，校验通过），见 `hot/` 与下文 |
| 批评 agent | **未做**（README 要求另一模型家族） |
| 裁决 | 队列 10 条，人在对话中逐项裁定，agent 记录到 `adjudications/2026-10-20.json`：3 条 fix pair（1 收 2 拒）、4 条 OVER_STRICT、3 条 TRUE_RISK（P2、P1、P1） |
| 改进 agent | 按裁决的 `sr_change_allowed` 做了两条放宽，均先写失败测试再改：NET-A01 对 IC 双向脚的单节点网降 CANDIDATE；DRV-A03 对经 ≤3 级电阻可达驱动脚的栅极降 CANDIDATE。变异 M23/M24 守住，变异门 24/24 杀死 |

## 指标（`metrics-baseline.json` → `metrics.json`）

| 指标 | 改动前 | 改动后 | 怎么读 |
|---|---|---|---|
| mature_cold_false_alarms | 0.47 /100 行（22/4657） | **0.28**（13/4657） | 少掉的 9 条就是裁决为 OVER_STRICT 的 CH344Q ×7、Q10、以及 QON 的 NET-A01（QON 仍以 NET-A07 报，规则未改）。这是本轮唯一可比的进步 |
| fix_pair_recall_cold | 0.667（3 对） | 1.0（1 对） | **不可比也不可信**：入库的那一对“命中”的是 U1 另一脚的 PWR-A02（V3 脚，本身是误报），与缺陷无关。按位置点名的定义会高估，见问题 2 |
| fix_pair_recall_plan | 1.0 | 1.0 | 同上，IC 总有 DEV 行 |
| seeded_recall | 0.882 | 0.882 | 不降 |
| typical_gate / replay_gate | 0 / 0 | 0 / 0 | 通过 |
| fix_pair_recall_hot | null | 1.0（1 对） | 热审试点的 finding F-001 位置点名 R18/D7/Net-(D7-A)，与作者修法同病因 |
| p0_precision / misfile_rate / lookup_honesty | null | null | 要批评 agent + 裁决（试点没有 P0） |

## 热审试点：声明电路后 SIG-C07 能否问出缺陷

能。给 before 版写了 intent（UART-DBG、UART-XLAT 两个电路，状态 run / esp-reset），计划立刻生成两个框架，
SIG-C07 行的问题是"上拉轨对各接收端门限与耐压是否匹配"，SIG-C08 是"经上拉、ESD 结构或保护二极管的反灌路径是否被堵住"，
正对着 R18→D7→U6.35 这条路。读手册后结论与作者修法同病因，但机理与此前的猜测不同：
CH340X 由 USB 5 V 供电，按手册在 5 V 模式，RXD 允许到 VCC+0.5，**CH340 本身不过压**；过压在 ESP32 侧——
U6 复位或 3.3 V 未建立时，R18 10 k 从 5 V 经 D7 正向把 U0TXD 抬到 4.65–5.25 V（上限 VDD33+0.3），WCH 手册 §7.7 正是为此要求在该支路串 NMOS，
Rev O 的 FET4 就是这个管。判定：F-001 P1（COMPONENT_DAMAGE），SIG-C07/C08 的 esp-reset 行 FAIL，run 行 PASS 或开放。
试点暴露三件事，本轮都改了：(a) 疑似过严开放项 V3-WINDOW（CH340 5 V 模式 V3 无保证窗口，最坏 +0.1 V、≤10 µA）→
`commodity-floors.md` 新增“微注入上拉”底线（R ≥ 10 k、超出 ≤ 0.3 V、注入 ≤ 30 µA 判 PASS(B)），试点按此撤销开放项；
(b) 同一组对象声明两个框架时 SIG-C07 重复、开放项 key 全局唯一导致复制 → 校验允许一个框架的行绑到对象覆盖它的另一框架功能（M25 守）；
(c) 局部台账过不了 validate → 台账可声明 `review_scope`，覆盖类校验只对范围内的行，gate 有效但带“不是整板结论”阻断（M26 守）。
改后试点台账 `valid: true`，12 行 PASS 9 / FAIL 3，质量筛查零提示。

## 缺陷为什么冷跑抓不到

三处候选都是**缺件**（少 TVS、少 PG→EN 电阻、少下拉/分压）。SR 的逐对象行挂在存在的器件上，问不出“这里该有而没有”；会问这类问题的科目（防护链 PRO-C01、使能来源 RST-T01、电平域 SIG-D04）在功能电路框架里，而框架只从声明的 intent 生成，本轮 Olimex 板没有 intent，`plan.functions` 为空。入库的 N→N1 对要靠热审声明 LEVEL_SHIFT/UART 电路后由 SIG-D04 问出“5 V 上拉进 3.3 V 域”。

## 过程中发现的问题

1. **循环只是规格**：第 7 节五个脚本一个都不存在，`corpus/` 全空。本轮补了 `run_review.py`（cold + hot 输入包）、`metrics.py`、`compare.py`；`build_fix_pairs.py`、`critic_pack.py` 仍缺。
2. **召回指标定义会高估**：按“点名 defect_location 任一 ref/net”算，无关条目也算命中。应改为“命中行的规则在 `expected_rules` 内”，这要求人先填 expected_rules（本轮入库对已填 SIG-D04，agent 提议）。
3. **`runs/.gitignore` 原本把 `metrics.json` 也忽略**，而 `compare.py` 要上一轮的 metrics；已改为保留 `metrics*.json`、`corpus-draft/*.json`、`adjudication-queue.json`。
4. **收录条件难以机械判定**：3 对里只有 1 对的作者原话明确是缺陷；Olimex changelog 里真正写“fixed”的多数是布局/封装。靠 Olimex 一家凑不齐第 1 轮 10 对的目标。
5. **Olimex 全部 Rev 同在一个 commit 的不同目录**，模板的 before/after 两个 commit 退化为同一 sha；模板应允许“同 commit 不同路径”。
6. **typical 基准的 expected 里混着“SR 当时报了、人没核过”的条目**：本轮 10 条队列里 11 条 expected 行被人改判为误报（why 字段原本就写着“需人工确认”）。typical 的 expected 不是真值，只是回归锚；成熟板语料要另立真值。
7. **人工裁决本身会错**：第 2 条初判收录，agent 复核电路后改判。裁决模板应允许 agent 附一栏“电路复核意见”，人看完再签。
8. **热审是成本中心也是唯一的 P0 来源**，README 没写成熟板热审的 intent 从哪来；没有 intent 就没有功能电路框架。
9. **批评 agent 的“另一模型家族”在当前工具链里没有入口**。
10. README §3/§4.1/§9/§11 残留一块已审设计的轮次与记录号，已中性化。
11. 解析侧：Olimex 板 FET1–3 缺引脚名、typical 的 resonare-lcc/moteus-c1 等，`parse_kicad` 严格自检退出码 2（db 仍写出）；成熟板语料入库前要先过严格解析。
12. 下一轮过严候选：CH340X 5 V 供电时 V3 是 LDO 输出，PWR-A02 把它报成“电源脚所在轨无驱动”是误报。

## 进化效果

规则侧：两条放宽，成熟板冷跑误报每百行 0.47 → 0.28，召回类指标不降，三条门全过。真值侧：1 对 fix pair、10 条裁决、typical 11 行改标。能衡量“SR 能不能抓住真缺陷”的数字（热审召回、P0 精度）本轮仍为空。

## 等人做的事

- 决定热审 3 块板的 intent 来源与批评 agent 用哪个外部模型。
- 给 42 块代理成熟板补 `production_evidence`，签 `split.json`（目前只有 Olimex 一个仓库在 train）。
- 确认入库对的 `expected_rules`（SIG-D04 为 agent 提议）。

# calibration--industrial-io-rs485-can / 合并步 6

ASG 自绘的工业 I/O 校准板（24 V 输入、RS-485、CAN、8 路 DI、4 路 DO，STM32F103），设计记录在 `~/Documents/ASG-calibration/industrial-io-rs485-can/`（只读），license `internal`。复现输入复制到 `~/.cache/sr-boards/calibration--industrial-io-rs485-can/`。网表是设计记录改版后的版本（D501 料号已改等），所以 db 与原审查的 db 不同。intent 的隔离边界名照改版网表改了（ISOLATION-FIELD/GND），新候选的决定另存为 `review/intent-after.json`。

before 用 e3be29e，after 用终版，两边都跑同一链路：原生 XML 重解析、冷扫、候选、决定、候选扫、合并计划。

| 项目 | e3be29e | 终版 |
|---|---:|---:|
| 冷扫非 INFO 行 | 27 | 19 |
| 合并后非 INFO 行 | 25 | 19 |
| 计划检查项 | 837 | 808 |
| 候选电路 / 未归属器件 | 16 / 48 | 15 / 70 |

22 条发现和 3 条漏问在两版上是否还报（数字为命中的行或候选数）：

| 条目 | 结论 | e3be29e | 终版 | 修在 |
|---|---|---:|---:|---|
| F01 | true_defect | 1 | 1 | 设计方改料号；改版后审计仍是 D501 NO_DOCUMENT |
| F02 | true_defect | 0 | 0 | 改版网表已改 |
| F03 | true_defect | 1 | 0 | 剩的 1 行与 F04 是同一行 U701.49 |
| F04 | false_alarm | 1 | 0 | 8d1c7ec |
| F05 | false_alarm | 1 | 1 | 未修，需人定 |
| F06 | needs_human | 1 | 1 | — |
| F07–F11 | needs_human / knowledge_gap | 2/2/4/1/8 | 2/2/4/1/8 | — |
| F12 | needs_human | 未跑 | 未跑 | 缓存里没有导出日志 |
| F13 | false_alarm | 1 | 0 | 6505fd8 |
| F14 | false_alarm | 4 | 0 | ad1b89f |
| F15 | false_alarm | 4 | 2 | 2bde9dd；剩 U202 的 2 行 INFO，它没有独立 UVLO 脚，按设计保留 |
| F16 | false_alarm | 1 | 0 | 488fc8b |
| F17 | false_alarm | 1 | 0 | 3142eba |
| F18 | false_alarm | 2 | 0 | 293562d |
| F19 | false_alarm | 4 | 0 | 4cb027a |
| F20 | false_alarm | 2 | 0 | 7a75065 |
| F21 | false_alarm | 3 | 0 | 2a5f884 |
| F22 | knowledge_gap | 0 | 0 | — |
| M01 | 漏问 | 1 | 0 | 9ae0ee4，新出 DC_24V-J101 |
| M02 | 漏问 | 1 | 0 | b5469d2 |
| M03 | 漏问 | 1 | 0 | 29e482a，新出 CLOCK-Y301 |

F06 在中间版本里曾从 1 行变成 3 行：F16 让 TVS3300 被认作 TVS 后，原生脚名路径把三只裸 K 脚各算一个通道。已在 protective_clamps 里修成同名裸 K 合为一个通道，终版回到 1 行。

### 最重要的三条观察

1. **会在别的板上重复的误报模式**：输入保护候选把连接器所有脚的分支都收进来，包括 CAN 端接、DI 通道和机壳 Y 电容（F19）；MCU 的 BOOT 下拉单独成为未归属电阻（F21）。78 块板上，这两类共去掉 18 个假的 POWER_PROTECTION/STARTUP 候选，新增 31 个 CLOCK 或 STARTUP.BOOT 候选。
2. **最该先修的漏问**：24 V 工业输入没有自己的候选（M01），窗口、保持时间和反接这些接口问题全落在 REQ 名称线索上。现在要求同时有保险、钳位，以及需求窗或 24V 名称，才出候选；78 块公开板上一个都没有新出。
3. **写不可判的地方**：F05 要“intent 给了 TVS 参数就直接比较”，但 intent 没有结构化的 TVS 参数字段，交审查者在结果里关闭。保持类电路（串联二极管加储能）在词表里没有 HOLD_UP 类型，只能在 POWER_PROTECTION 里按成员裁剪方面。

SR 用法上的坑：设计记录是改版前审的，网表已改，复现必须把 intent 的隔离边界名对上新网表，否则候选决定全部失配。

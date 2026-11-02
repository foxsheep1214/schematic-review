# HackRF Pro · lane-3 本轮记录

固定源 `greatscottgadgets/hackrf-pro@359b98f2451395408bc25dae64efa9fc518e93d0`，CERN-OHL-P-2.0；KiCad 10.0.7。宽带 SDR 用途为推断，基线 industrial_telecom。目录类型 RF/CLOCK/USB/POWER_CONVERTER，另核 ANALOG/SPI/I2C/STARTUP/DEBUG/POWER_PROTECTION。

| 项目 | 数量 / 状态 |
|---|---:|
| 输入 | 577 器件、490 网络、12 页 |
| 最终计划 / 逐项处置 | 1632 / 1632 |
| PASS / NA / 待判 | 37 / 34 / 1561 |
| 归因条目 | 161 |
| true_defect / false_alarm | 0 / 11 |
| criterion_issue / knowledge_gap / needs_human | 0 / 36 / 114 |
| Top 50 已核 / 覆盖漏报 | 50 / 4 |
| 原生门禁 / 准出 | FAIL / NO_GO |

37 PASS 含 10 项覆盖汇总；填完台账不是全部电气关闭。161 条为 30 条未关闭扫描提示、128 个功能开放项及 3 条修正前工具诊断，存在共享原因。3 条合法候选经核验关闭，另有 2 条 INFO，均不凑作误报。

1. **合并步先修对象覆盖。** 排他所有权和资格裁空漏了 X2/X3 晶体、Q4/Q5 反接与 SOA、U16 CRESET/CDONE；本轮通过有出处的候选补充及 rule_gap 补回。这是覆盖缺口，尚非已证电气缺陷；种子注明缺少的参数契约，不声称已执行。
2. **误报需要角色和通道语义。** I2S 的 SDA 字样不能建立 I²C；LED 整通道、Q7B 整组三脚 NC 不等于悬空 CMOS 输入。Si5351C 外部 XA 驱动时 XB 悬空符合 p23/p25，属于合法候选关闭，不算误报。
3. **硬件优先补两处边界。** D13 的二极管符号/TSLP 封装与 0Ω 电阻料号冲突；MAX5865 p2 上限 3.3V、OVDD≤VDD，而上游名义 3.333V 经不同开关/磁珠到两域，须求公差与压降边界。均保留待确认，不把名义值变成确定故障。

用法坑：schema15 不承载 needs_human，且保证条款、条件轨窗预判的处置仍有门禁错误；如实保留 FAIL，未伪造 VENDOR_DATUM。strict 回退有 33 个空功能脚名；已对照 12 颗 IC 的官方脚表作局部差集，仍不宣称全板逐脚通过。无独立装配 BOM；完整 PDF、网页摘录和未绑定的同族资料不能互换。

逐项依据、Top50、源哈希和原生 gate 留在 [缓存 review](/Users/skyfend/.cache/sr-boards/greatscottgadgets--hackrf-pro/review/record/source-lock.json)；[归因 JSON](findings.json) 记录全部路径及文件哈希。[审查报告](审查报告.md) 由 renderer 原样生成，保留“记录未通过校验”的告示。

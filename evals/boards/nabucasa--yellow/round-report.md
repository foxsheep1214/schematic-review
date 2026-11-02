# nabucasa--yellow · lane-2

Home Assistant CM4 主板（按固定提交 README **推断**），catalog 类型为 ETHERNET / RF / STORAGE / POWER_CONVERTER，另核 USB、I²C、音频、PCIe、保护、启动与晶体。基线 industrial_telecom。309 器件、11 页；CERN-OHL-W-2.0。

| 数字 | 结果 |
|---|---:|
| 计划项 | 1605 |
| 已判 PASS / NA；未决 | 67 / 17；1521 |
| 归因记录 | 164 |
| true_defect / false_alarm | 0 / 28 |
| criterion_issue / knowledge_gap / needs_human | 1 / 10 / 125 |
| 漏项：输入守卫 / 计划 / 已证实硬件 | 2 / 1 / 0 |
| 门禁 | **FAIL，记录不可用于冻结** |

164 的口径是 66 条非 INFO 提示 + 97 条报告依赖任务 + 1 条准则问题，**不是 164 个硬件故障**。Top 50 全部逐条核对；条目及证据见 findings.json，全部检查的脚网与未知边界见缓存 item-assessments.json。

1. **合并步先补输入一致性守卫。** 同提交 PCB 分开 +3V3/+3.3VP、GND/GNDS，当前 KiCad 10.0.7 导出却分别合网。1214 个 pad 对照定位 U19.5/U26.5、U23.23/T1.6；版本变化还是图板不同步尚未查明，不能指控原板短接。
2. **28 条误报有可复用模式。** FE1.1 的 VS_PLL/VS_A 是地；BAT54C 双二极管、DNP U25、M.2 无源触点与 CM4 内建 1.8k 上拉均须先核真实脚义和装配。
3. **时钟计划与 Source 准则各缺一环。** Y1/Y2 没有 CLK-C01；负载/寄生未知应留依赖。G01-031 仅登记 USB，却引用 Type-C 条款，不能直接要求 Type-A J4 按 CC 未附着断电。

用法坑：7 个 add 类型默认空状态会被 lint 拒，本轮显式写有出处的推断 run，未造需求。schema15 不支持 boards 的 needs_human，亦不能把身份/作者输入冒充厂家参数；另生成 DEV-D05.M1 重复项。derive_rows 零错误，validate_review 保留 3315 条错误，包含上述不兼容与未闭合记录；未改门禁、未打包、未提交。报告由脚本生成并复制，record 链接依赖本机缓存，不是可移植交付。

来源 `NabuCasa/yellow@c3d51b80e40ea01e34ef65c7d0aecc16a37980d4`；完整工作记录：`~/.cache/sr-boards/nabucasa--yellow/review/`。

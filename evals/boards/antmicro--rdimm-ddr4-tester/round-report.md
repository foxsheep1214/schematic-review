# lane-3 · antmicro--rdimm-ddr4-tester

固定源 `e7c85ebc9eb3`，Apache-2.0；KiCad 10.0.7。用途推断：Kintex-7 RDIMM DDR4 测试板，含 GbE／PoE、USB 调试、电源及监测；基线 industrial_telecom。

| 项目 | 数量 |
|---|---|
| 最终计划 | 1660 |
| 独立判定 PASS／FAIL／NA | 160／3／32 |
| 未关闭 INSUFFICIENT | 1465 |
| 发现总数 | 148 |
| true_defect | 2 |
| false_alarm | 133 |
| criterion_issue | 0 |
| knowledge_gap | 2 |
| needs_human | 11 |
| 漏报／覆盖缺口 | 2 |
| Top50 对照 | 50 |
| 门禁 | FAIL；valid=false |

1. **先合并来源追踪修复。** 112 条 PWR-A01/A02 误告警暴露 `R_0R01_1206` 等阻值字段未识别、IC1／SW_VPP／VTT 来源未贯通。应保守解析并沿已核低阻／电感追踪，保留断路反例；撤回无来源断言不能代替电压／负载检查。另有 7 个错误去耦组展开 28 项，单列一条根因，未膨胀发现数。
2. **两处确证，均 P2。** R199=5mΩ 图示却配 Bourns CR1206 `000` 跳线（仅保证≤50mΩ、2A）；U19/U20 的 ADDRSEL 都接 VDD，实际同为 0x1F，U20 图注 0x10 不成立。已给配对 seed；3 个 FAIL 项对应 2 个根因。
3. **最先补的覆盖是 Y2。** USB 所有权遮蔽 12MHz 无源晶体负载检查；PAC1954 也缺 ADC 模拟输入检查。两项为 coverage miss，不是已证不起振／超量程；未发现可独立确证的准则问题，不凑数。

用法坑：strict 缺 U17/U24 的 8 个脚名，no-strict 不能变输入完整 PASS；无独立 BOM，未制造。原生 schema15 不接收板评估 needs_human 扩展，保留 validator FAIL（4940 errors），非有效准出记录。桥符号脚号须追到自定义封装再比厂家物理脚号；不能直接判错。PAC1954 完整原厂文档来自镜像，未冒称官网下载。全部 1660 项均有处置，1465 项仍不能独立关闭。第三方文件只留缓存，未改共用规则、未提交。

产物：[审查报告](审查报告.md)、[逐条归因](findings.json)；完整计划／证据／门禁留 `~/.cache/sr-boards/antmicro--rdimm-ddr4-tester/review/`。

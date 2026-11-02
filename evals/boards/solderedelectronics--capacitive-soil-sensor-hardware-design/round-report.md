# 电容土壤传感器 · lane-2 本轮记录

源：`SolderedElectronics/Capacitive-soil-sensor-hardware-design` @ `edd7f63a876ae5a7199bb925879c3737e4ba1dc5`；TAPR-OHL-1.0；根图 `CAD/V1.2.2/Capacitive_soil_sensor.kicad_sch`。ANALOG / POWER_CONVERTER，29 器件；KiCad 10.0.7 strict 导出成功。用途从 README/图面**推断**，基线 industrial_telecom。

| 项目 | 数量/结论 |
|---|---:|
| 计划项 / 已逐项录入 | 115 / 115 |
| 原生 PASS / NA / 未决 | 32 / 3 / 80 |
| 归因发现（20组待办＋6条反馈） | 26 |
| true_defect / false_alarm | 0 / 6 |
| criterion_issue / knowledge_gap / needs_human | 0 / 2 / 18 |
| Top 50 核对 / 漏报 | 50 / 1 |
| 门禁 | **FAIL / valid=false / NO_GO** |

1. **对象资格误用最易复现。** TLC555 首页 ESD 额定被认作 TVS；D1 官方文字摘录被当 PDF 读取而报 NO_TEXT；普通模拟链被问温度传感器；FD1/H1/H2 无电气脚却被要求扩电气定界表。六条均有定位和 proposed_fix；供电跳线/RESET直连VDD的正常待核提示核完关闭，没有冒充误报。
2. **须按实际加载算。** R8 是 10k±25% 电位器；中点源阻 2.5k 使传感增益约11.947，而非理想参考下14.7。C1 被 R1||(R5+R6+R7) 加载，标称 τ≈0.13570s；555 简式给约870kHz，已越过该式<100kHz适用范围。均未借这些标称结果指控实际测量不合格。PCB 电极包含无 net 属性的 F.Cu 图形，网表没有独立传感器件不等于开路。
3. **合并步先处理未决终态契约，再补 M01。** 原生只接受 VENDOR_DATUM/REVIEW_INCOMPLETE，无法诚实承载未确认产品要求的 needs_human；本轮保留 351 条记录错误，未编造需求或后果等级。M01 是 U2 无 SS 脚时漏问启动充电＋负载/限流；已有 proposed_fix 与仅检计划覆盖的 seed，未证明启动过流。

用法坑：U2.5须声明 power 并设 regulator_output 专用电容组；外源 K1.2须有带状态/出处的 power_sources，供电网才不会误成逻辑链。固定提交仅有 V2.0.0 BOM/PDF，未混入V1.2.2；D1/TC33仅取得官方网页摘录，未声称完整PDF。重复输入任务已合并，质量提示逐条留处置。报告由脚本生成，明确标注记录无效；未执行通过打包。完整台账和可用索引在[缓存报告](/Users/skyfend/.cache/sr-boards/solderedelectronics--capacitive-soil-sensor-hardware-design/review/审查报告.md)，仓库内为原样报告副本；[逐条归因](findings.json)内含50条核对。

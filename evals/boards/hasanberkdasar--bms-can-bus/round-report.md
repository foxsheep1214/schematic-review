# hasanberkdasar--bms-can-bus · lane-2

固定源 `hasanberkdasar/BMS-Can-Bus@c14c2829e0f1`，MIT；KiCad 10.0.7 严格导出/解析，59 器件。用途**推断**为4S BMS（BQ76952＋STM32F103＋SN65HVD230）；基线 industrial_telecom。类型 CAN / POWER_CONVERTER / POWER_PROTECTION，补 ANALOG / CLOCK / I2C / STARTUP。

| 项目 | 数量 |
|---|---:|
| 最终计划／逐项已裁决 | 381 / 381 |
| PASS / FAIL / INSUFFICIENT / NA | 73 / 27 / 270 / 11 |
| 归因条目 | 30 |
| true_defect / false_alarm | 5 / 4 |
| criterion_issue / knowledge_gap / needs_human | 1 / 1 / 19 |
| Top50核对／确认漏报 | 50 / 0 |
| proposed_fix / seed | 6 / 5 |
| 门禁 | FAIL；valid=false，release=NO_GO |

归因30条＝5个确认根因＋19个作者待确认任务＋6条SR反馈；不是30个硬件错误。27个FAIL检查归并为5个根因。

1. **先核真实脚义。** Q1/Q2/Q7/Q8 的G接BAT+/PACK+、D接CHG/DSG；REGIN经100Ω直连电池且BREG浮空；VC16/VC15同网违背低串数接法。依据BQ手册pp4–7、46–47、75；C3–C6未定容量、关键MOS/晶体无型号另按源设计缺失处理。
2. **可重复误报有边界。** TS3允许未用时悬空；两脚无源晶体不问有源OE，片内ADC不问外置运放输出。Vref悬空有厂家许可，NET-A01的“确认后补NC”只是正确绘图提示，未把它计成误报。
3. **合并步优先修函数ID碰撞。** `J_PACK+1` 与 `J_PACK-1` 的接口均变成 `FN-EXT-J-PACK-1`，引发相互超范围。先给ID稳定转义/去重并加正负端口回归，再补BQ专用模型；手工计划已覆盖的问题不冒充整套SR漏报。

用法坑：原生schema15不接NEEDS_HUMAN；通用电容预判覆盖码、I2C原文“4.7k ohm”解析和纯拓扑失败证据也有契约限制。580条校验错误归为5类原由，原始门禁未改；52条质量提示已逐条处置。无BOM、无受控电池/负载/固件配置，未声称实测/准出。三份原厂PDF、原生文件、381项端点台账、Top50逐条表、门禁及原图局部仅在[审查缓存](</Users/skyfend/.cache/sr-boards/hasanberkdasar--bms-can-bus/review/>)；仓库报告图片相对路径使用缓存目录，未复制第三方电路。未改共用规则/检查器，未提交。

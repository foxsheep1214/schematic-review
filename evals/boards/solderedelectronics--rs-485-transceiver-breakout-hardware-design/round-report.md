# RS-485 转接板 V1.0.0 · lane-1

固定来源 `SolderedElectronics/RS-485-Transceiver-breakout-hardware-design@22fb2d67`；TAPR-OHL-1.0。用途**推断**：5V、非隔离半双工 RS485 模块，基线 `industrial_telecom`。KiCad **10.0.7 strict** 导出、解析成功，15 器件；同版 BOM/PDF 已核。

| 项目 | 数量/结果 |
|---|---:|
| 计划项 / 已形成局部结论 / 待人工或资料 | 76 / 16 / 60 |
| 自动电气命中 / 原生确认缺陷 | 0 / 0 |
| 归因条目（3条非阻断能力建议＋4条审查观察） | 7 |
| true_defect / false_alarm / criterion_issue | 0 / 3 / 0 |
| knowledge_gap / needs_human | 1 / 3 |
| Top50 核对 / 漏问判据 / 确证硬件漏检 | 50 / 2 / 0 |
| 原生门禁 / 准出 | **FAIL / NO_GO** |

1. **重复误报**：FD1、H1、H2 的原生符号均零电气脚，仍逐个产生 NEW_DEVICE_KIND，要求补电气类别/定界表。应按原生完整性＋零脚机械/图形身份排除；这是建议误触发，不是电气缺陷。
2. **最该补的漏问**：K2 的 D/R/DE//RE 直连 5V 收发器逻辑侧，却未展开 SIG-C08；G04-005、G04-009 被记“未展开”。应逐外部逻辑引脚给绝限、失电注入与集成窗口问题；主机未指定，不能指控实际超压/反灌。PRO-D04 已问的通用故障不重复计漏报。
3. **不得误判的实数**：R1/R4=20kΩ、JP2闭合、R2=120Ω时，理想空闲 VAB≈14.96mV；TI SLLS101I p6/p13 给200mV门限及小差分未定义状态。外部强偏置可改变结论，F04保留 needs_human。本轮未证实准则本身有错；普通无源件缺专属手册也不直接定罪。

**用法坑**：BOM为分号CSV且值列名Designation，read_bom原件失败；仅转换分隔符/列标题后导入，原件保留。U1手册标题无RS485，候选role-bus需有据add；默认add推出空states而lint拒绝，可用正式支持的states字段写厂家工作态，但add还丢失nets/anchors。原生schema15没有needs_human；未伪装成VENDOR_DATUM或整功能PASS，保留缺60结果、缺完整功能/覆盖的门禁错误，报告是**无效记录草稿**。

[76项独立依据与计算](/Users/skyfend/.cache/sr-boards/solderedelectronics--rs-485-transceiver-breakout-hardware-design/review/engineering-review.md) · [原生台账](/Users/skyfend/.cache/sr-boards/solderedelectronics--rs-485-transceiver-breakout-hardware-design/review/review-results.json) · [门禁](/Users/skyfend/.cache/sr-boards/solderedelectronics--rs-485-transceiver-breakout-hardware-design/review/review-gate.json)；全部工作文件留在板级缓存review。复制报告的默认record索引未随源网表/原厂文件打包，以这些缓存入口为准。Top50逐条核对和全部修改建议已写入 findings.json；没有可在当前单板输入下证实的缺陷种子，seed均为null。未改共用代码/准则，未提交、未推送。

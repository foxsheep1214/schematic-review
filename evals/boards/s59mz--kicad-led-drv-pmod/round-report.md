# s59mz--kicad-led-drv-pmod · lane-1

固定来源 `s59mz/kicad-led-drv-pmod@5a58cd064f7c3e82e2d972e7fd3380619fbcc566`，GPL-3.0；KiCad 10.0.7 strict 成功，19 件、73 节点、1 页。用途**推断**：LTC3206 充电泵恒流 LED Pmod，8 单色＋共阳 RGB；catalog 的 ANALOG 已核，设定电阻归驱动器，补 I²C，无独立模拟前端。基线 `industrial_telecom`。

| 指标 | 数量 |
|---|---:|
| 最终计划（原生＋审查者补项） | 115（112＋3） |
| 局部已判／逐项 needs_human | 26／89 |
| 已判结果 PASS／NA／FAIL | 19／6／1 |
| 归因发现（按根因，自动疑点 0） | 10 |
| true_defect | 1（制造商数据错误；确认电气缺陷 0） |
| false_alarm | 2 |
| criterion_issue | 0 |
| knowledge_gap | 2 |
| needs_human | 5 |
| Top 50 漏问／确认硬件漏检 | 3／0 |
| 原生门禁 | **FAIL**（valid=false，63 条记录/覆盖错误） |

1. **优先补 CPO 输出模型。** U1.14→C4=2.2µF→GND 是闭环输出；3206f p12 要求全条件有效容量≥0.6µF、低 ESR，原计划却因没有常规 OUT/SW 脚略过 PWR-C04。另漏问 ENRGB 默认态、J1 源侧保护边界；三项均经 `intent.rule_gaps` 补入，不能把待核条件当原板硬件缺陷。
2. **两项误阻断可复现。** D1–D8 已有两端子空差集，DEV-D02 仍索类型手册；四脚共阳 RGB D9 又被当作未知 IC 阻去耦库存。分别给脚集合快速通道和明确多结 LED 的非 IC 排除条件，保留额定、颜色针序的独立核对。
3. **已证字段错误与性能边界分开。** U1 的 MANUFACTURER=Microchip，与 LTC3206 原厂身份冲突；只证数据错误。12k 设定名义20mA/通道、11结220mA；10k 上拉在300ns条件下只容名义35.407pF。无实际 LED/C4 采购范围和主机条件，不能签全温、400kHz或电源能力通过。

用法坑：BOM 用 `Designator/Comment`，需原值保留转换后 `read_bom.py`；原始 fetch db 与 BOM 审查 db 分别锁哈希。LTC3206 仅取得原厂在线文字，完整 PDF 下载失败；Pmod 官方托管副本实际为 **2011 Doc510-002**，不是 1.1.0。schema15 无诚实的未定需求枚举：89 项逐项保留 pending、7 个功能范围另存，6 个框架无完整结论；原生“资料不足0”不表示审完。已运行校验/派生/渲染，保留 FAIL，未打包。

报告见[审查报告.md](审查报告.md)，归因及全部50条核对见[findings.json](findings.json)。原生报告的 `record/` 索引需查[缓存审查工作目录](/Users/skyfend/.cache/sr-boards/s59mz--kicad-led-drv-pmod/review/)中的同名台账；第三方输入、完整证据均留缓存。未改检查器/准则/种子，未提交。

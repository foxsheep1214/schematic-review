# angelnu--lorawansensor · lane-4

推断用途：电池供电STM32 LoRaWAN通用传感节点；RF / SPI / CLOCK；industrial_telecom。MIT，源提交333d283c，KiCad 10.0.7 strict成功，35器件/37网络/1页。

| 指标 | 数量/结果 |
|---|---:|
| 计划项 / 已判 / 未完成 | 134 / 36（含3覆盖记录） / 98 |
| 原生结果 PASS / NA / INSUFFICIENT | 21 / 15 / 98 |
| 归因发现 | 39（按对象/独立根因，非原生FAIL数） |
| true_defect / false_alarm / criterion_issue | 0 / 23 / 0 |
| knowledge_gap / needs_human | 2 / 14 |
| 漏报 | 2个检查覆盖缺口，实板缺陷未定 |
| 门禁 / 正式报告 | FAIL、NO_GO / renderer退出2拒绝生成 |

最重要的3条观察：

1. **类型误识别会放大**：Bridged铜桥匹配BRIDGE，生成2条假保护候选；铜桥/PU电阻索脚表10条；同源U1/U2因身份未知展开9条跨域检查。外部接口风险仍保留，不能全部消音。
2. **合并步优先补PRO-C04分支枚举**：BT1.1直接到J1.1/J2.1却没有保护覆盖检查；无保护器件不能成为不展开检查的理由。另有NSS/RESET的RST-T04默认态检查未展开。两项均附候选种子，缺故障源/安全态合同不能断言实板缺陷。
3. **准确手册不等于准确物料**：C1/C2各10pF→5pF+Cstray，NDK家族有多种CL；RFM95W官方p11/110模块RESET=6，后文写Pin7，不能据此误改U2。没有足够证据证明准则本身错误，criterion_issue=0。

SR用法坑：当前schema15；add电路须显式states，否则决定器可接受而lint拒收（run仅分析状态）。功能条款绑定仍有13条F1错误；98项REVIEW_INCOMPLETE使render拒绝，未用虚构参数或手动PASS绕过；审查报告.md明确为未完成执行记录。源树battery_calculations.xlsx非完整装配BOM，PU不套门磁示例值。详见[逐条归因](逐条归因.md)、[Top50核对](Top50核对.md)和[审查执行记录](审查报告.md)。

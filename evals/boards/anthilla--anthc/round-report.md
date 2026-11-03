# anthilla--anthc · lane-2 · 2026-11-02

固定源 `e123f339e36dd42c7e4ccec27813b0dd504a98d2`；CERN-OHL-W-2.0。推断为 ESP32-S3 工业采集/控制板，catalog 类型 RS485、ANALOG、POWER_CONVERTER、USB；补 CLOCK、I2C、LEVEL_SHIFT、STARTUP、DEBUG、POWER_PROTECTION。基线 industrial_telecom。

| 指标 | 数量/结果 |
|---|---:|
| 原生器件 / 网络 / 页 | 210 / 173 / 2 |
| 最终计划 / 逐项判定 | 893 / 893 |
| PASS / FAIL / INSUFFICIENT / NA | 102 / 36 / 736 / 19 |
| 去重归因总数 | 100 |
| true_defect / false_alarm / criterion_issue | 7 / 11 / 0 |
| knowledge_gap / needs_human | 18 / 64 |
| Top50核对 / 独立漏报 | 50 / 2 |
| 原生门禁 / 准出 | FAIL / NO_GO |

发现口径：7个确认根因、82个开放根因、11类SR误报反馈；36条FAIL共享7个根因。另有86条记录质量建议逐条留存，不算板故障。7个确认项包含资料/库一致性问题，未声称全部造成实物失效。

1. **先修解析器的贴装判据。** U10的`/NC`是UQFN后缀，原生非DNP且BOM空DNP；误删导致三条悬空误报并丢掉ADC覆盖。原始db保留，分析副本仅恢复U10并锁hash；R65真实DNP不变。
2. **电路问题有独立证据。** J5父子页VDD/+VDD断开，U2缺VDD2；U1 DR与PowerPAD不符，U9缺SHDN脚，U10错链非R手册，12颗PESD公共脚2/3错义，USB检测取D3后多源5V。允许EN/SHDN浮空与正常的3V3旁路模式均已排除误判。
3. **漏项先补多通道TVS。** 三网器件被两网条件跳过，PESD/SM712未生成逐通道PRO-E02；另有无EN的U3漏PWR-D03启动电流专项。两个均为覆盖漏项，未凭缺负载/波形断言烧毁；没有足够证据另判准则本身有问题。

用法坑：KiCad10.0.7；strict因U9输出缺名回退。BOM仅13IC。Ω值解析、boost储能电感误当输入滤波、SS套数字启动、共享J3错误归RTC均有修改材料。schema15不接NEEDS_HUMAN/未定级；还存在I2C绑定、证明条款、通用预判与NA证据等记录错误，共3194条，不能全部归咎扩展字段；原生报告保留“记录不可用”警示，不作正式放行。未打包；报告的record相对链接未随单MD复制，完整台账/原厂资料与逐项证据在 `/Users/skyfend/.cache/sr-boards/anthilla--anthc/review`。U5/U11/PESD只核在线原厂页，本地完整PDF未取得，不冒充下载成功。

详见 [findings.json](findings.json)（含50条核对、归因、proposed_fix、seed）及 [审查报告.md](审查报告.md)。未改检查器/准则/HardwareWiki，未提交。

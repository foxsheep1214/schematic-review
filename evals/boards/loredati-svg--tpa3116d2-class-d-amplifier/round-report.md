# lane-1｜TPA3116D2 蓝牙功放

固定源 `916c1696c967864a303baea76b7474cd7fa3ded0`，CERN-OHL-P-2.0；指定 BT 根图，非 README 的 USB 版。用途推断：24V 蓝牙立体声 BTL 功放；AV/ANALOG/POWER_CONVERTER，补 UART、24V 输入及模组 RF 边界，基线 industrial_telecom。

| 指标 | 数量/结果 |
|---|---:|
| 器件 / 网 / 原生页 / XML端点 | 73 / 75 / 5 / 223 |
| 计划项 / 功能框架 | 268（265自动＋3补问） / 18 |
| 局部已判 / needs_human | 62（44 PASS＋15 NA＋3 FAIL） / 206 |
| 归因发现 / 原生确认缺陷 | 24 / 2 |
| true_defect / false_alarm / criterion_issue | 2 / 9 / 0 |
| knowledge_gap / needs_human（归因根因） | 4 / 9 |
| Top50逐条核对 / miss | 50 / 3（计划漏问，均已补回） |
| 门禁 / 准出 | FAIL，valid=false（421条校验错误） / NO_GO |

1. **合并步先贯通官方脚义与供源/电源域。** IC4 SW8→L5→3.3V、VCC6→C43仍被报无驱动；BOOT误当strap、FAULTZ误当门限、未用I2S SCLK0误触SPI/CLOCK。修识别并回放真正断供反例。
2. **两处真缺陷均为设计数据问题。** IC4 Value=A、制造商/Mouser=B，频率400/1400kHz；五页图末两页仍6/5、7/5。未证明实物焊错或烧毁。USB目录CSV经read_bom副本核对后隔离，不能覆盖BT图。
3. **三处漏问是两个启动对象和板内模拟掉电链。** IC2 MUTE/SDZ、IC3 MFB/EAN/P2_0漏RST-T04；四只1uF耦合链漏SIG-C08。已有入口PRO-C04、棕断PWR-T04及外部端口C08未重复计漏报；新增已证硬件漏检0处。

用法坑：IC前缀用`--require-ref`；TPA标题可能混入内部时钟措辞，按正式标题核角色；CHF1/CIN1用`kind+reason`定类。模型限制与可补输入分开，逐对象写manual_verification。schema15未能合法闭合未定合同及部分功能，保留206项pending和功能条款链错误，不能改成VENDOR_DATUM/完整功能PASS；报告“资料不足0”不代表审完。本报告仅诊断、未有效打包。

[审查报告](审查报告.md) · [逐条归因、修改材料、种子与Top50全表](findings.json)。原生记录/手册/独立计算在 `~/.cache/sr-boards/loredati-svg--tpa3116d2-class-d-amplifier/review/`。strict通过、XML/db零差异、源db哈希未变；Würth全文仅web端可读，本地直取403。未改共用规则、未写Wiki、未提交。

# ben5049--switch-v4-hardware · lane-3

固定提交 `0ca26bd573db7c48d221fdf4aa53ff780d888f71`，GPL-3.0；SJA1105 SPE交换机，3路PoDL PSE、双DC输入、隔离控制、SMI电平转换及多路时钟。用途为README/图面推断，基线industrial_telecom。

| 项目 | 数量/结果 |
|---|---:|
| 计划项 | 1,932（自动1,926＋人工补问6） |
| 发现/归因 | 200（原始未决扫描23条另存并关联待办，不重复计数） |
| true_defect / false_alarm / criterion_issue | 3 / 31 / 0 |
| knowledge_gap / needs_human | 17 / 149 |
| Top 50核对 / 漏报 | 50 / 2类（涉及4条准则、6个补问对象） |
| 逐项结果 | 106 PASS、11 FAIL、5 NA、1,810待判 |
| 门禁 | FAIL；valid=false，release=NO_GO |

1. **先解决真实相容性**：端口3 U901↔U1601直连RMII。NXP Rev2 p12只支持全双工；Microchip DS60001573K p28要求半双工MAC从CRSDV/TXEN判冲突。另两项是U302/U602实例00/01采购码冲突、Z2201/Z2202实例3V3/3V9冲突；不是仅凭库名断言贴错。11个FAIL归这3个问题。
2. **误报有可复现的物理原因**：L401是上游Buck输出电感却连报5条输入滤波；4k7 EN串阻裁断驱动源；CLK/CTL和IMON/VMON为独立信号；R101/R102的2MΩ屏蔽泄漏不能合并成等势地。有限阻抗、源语义与角色应分开。
3. **合并步优先补MCU ADC资格**：PF13/PF14、PA/PB检测脚被ANALOG_PIN资格漏掉；另漏TVS3301与Z前缀钳位窗口。已留2个proposed_fix、条件种子和人工rule_gaps；三颗晶体已有CLK-C01，不重复计漏报。

**使用边界/坑**：strict仅L801.1/.2脚名缺失，编号/归网存在；26页中3页仅层次/框图。无独立BOM，采购字段取XML实例。PoDL PSE不能套PoE PD，VDDUSB不是USB端口。原生schema15不支持两种评估待判分类；门禁另有条款承载、空框图条件及D01字段修正误判改线图等格式错误（共3,934条，不是电气缺陷数）。未造VENDOR_DATUM，也未打包。106 PASS含10个覆盖汇总；填满不代表电气审结。

[生成报告镜像](审查报告.md) · [机器归因与50条核对](findings.json) · [完整缓存报告](/Users/skyfend/.cache/sr-boards/ben5049--switch-v4-hardware/review/审查报告.md)。镜像原样复制，图/逐项记录留在缓存；不得作准出报告。未改共用代码、未commit/push。

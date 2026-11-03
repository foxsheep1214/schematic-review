# weirdgyn--driverino-shield · lane-3

固定源 `ef166bb6`，SR `9546b0bf`；56件、单页。推断为 Arduino UNO 有霍尔 BLDC 扩展板：功率变换/保护/模拟/SPI；基线 industrial_telecom。LICENSE为GPL-3.0，README的CERN-OHL-P说法冲突；仅引用必要事实。

| 数字 | 本轮 |
|---|---:|
| 计划项（原生+补项） | 267（265+2） |
| 已记录 / 已审结 / 待判 | 267 / 83 / 184 |
| PASS / NA / FAIL | 30 / 43 / 10 |
| 根因发现 | 41 |
| true_defect / false_alarm | 4 / 13 |
| criterion_issue / knowledge_gap / needs_human | 0 / 7 / 17 |
| 漏报（Top50 / 延伸） | 2（1 / 1） |
| 原生门禁 / 准出 | FAIL / NO_GO |

30 PASS含7条覆盖对账；10 FAIL共4根因（2电气、2文档），不是10处独立缺陷。

1. **确定的边界问题**：U1.26 AGND孤立；源TI p6要求接系统地。原图标注36V，而U1推荐工作上限、C2/C3额定均35V；只判标注契约冲突，真实输入未给，不能说U1超过40V绝限。C4另有DNF和0402/0603采购声明矛盾。
2. **可重复误报**：10个闲置UNO触点不等于断线/掉电注入/配电支路；D2是并联指示LED，非反接管/eFuse；SENSE的36V是被测母线，非敏感IC取电轨。13根因覆盖32个误派检查，均给修法。
3. **最先补覆盖**：motor_driver应展开RST-T04（G04-010），并用片内偏置正反例防止新误报；源TI p36已有下拉，未证“缺外部偏置”缺陷。A1另补ANA-C02：8.611kΩ/100nF，tau0.861ms，实际ADC采样合同未知。

用法坑：稀疏取板漏了BOM与随板手册，须从固定commit补取并用read_bom.py无损读入。源SLVSF18为预量产且推荐10nF，不能套新版47nF；PMCT变体仍待确认。R4准确ESR03现版0.33W，不能用普通0603档把0.2567W上界当必烧。严格解析缺F1两脚名保留。原生schema15不承载两类待判，另有条款/对象绑定、降额等级缺失等结构错误（门禁499条），如实FAIL；功能派生零错误不等于valid。报告原样生成并保留无效警告，未打包。

完整原生记录：`~/.cache/sr-boards/weirdgyn--driverino-shield/review/`；50条对照、全部check/task到归因映射、修复材料和6个种子定义见 findings.json。未改共用代码/准则，未复制第三方电路文件，未commit/push。

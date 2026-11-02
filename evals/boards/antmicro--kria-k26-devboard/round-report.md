# lane-4：antmicro--kria-k26-devboard

固定源9ead4dfc5b29fa9308206ccdfe013dd8f6d93b67，Apache-2.0；推断为Kria K26开发载板。目录类型：POE_PD / ETHERNET / HSSERIAL / POWER_CONVERTER；补充USB/I2C/时钟等，准则基线industrial_telecom。

| 项目 | 数量/状态 |
|---|---:|
| 逐对象最终计划 / 已登记 | 1957 / 1957 |
| 独立正式判断 / 未完成 | 206 / 1751 |
| 去重非INFO提示（含候选） | 244 |
| true_defect / false_alarm | 1 / 191 |
| criterion_issue / knowledge_gap / needs_human | 0 / 7 / 45 |
| Top50确认新增漏报 | 0 |
| 门禁 / 正式报告器 | FAIL（valid=false）/ 拒绝输出 |

最重要3条观察：

1. **合并步先修候选空状态契约。** 36候选经52决定推出37电路，但ETHERNET-U30/LEVEL_SHIFT-U12默认states=[]，lint要求非空；无受控需求不能捏造新增状态依据。本轮只完成逐对象回退计划，未完成完整SR。
2. **DNP与原生字段决定信噪比。** J_SOM240_2 DNP产生160/185条NET-A01，贴装SoM另25条仍待确认。原生Val/Tolerance存在（R33=200k/1%、R127=0R），解析丢字段后163颗阻值读不出，连带漏认Buck/EN供电路径。
3. **有手册才定缺陷。** U36.13未用输入NC违反74LCX07 p3注4，列P2并给接地复验和种子。Top50逐条50项未新增可确认漏报：SCK已有SIG-C01，Y7的9pF+Cs仍缺证据，不凭型号后缀报错值。

用法坑：strict因24处功能脚名缺失回退，不代表取板失败或针表完整；无单独BOM，所读表是同版XML原生字段。文档示例schema14、运行时15，已正式迁移再校验。1751项保留REVIEW_INCOMPLETE，报告器确实拒绝；[审查报告.md](审查报告.md)是明确标注的执行记录，台账错误数不是电气缺陷数。详见[findings.json](findings.json)、[Top50](top50-audit.md)、[运行记录](run-record.json)。未修改检查器/准则/源设计，未提交。

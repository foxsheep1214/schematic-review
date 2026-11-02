# antmicro--hdmi-mipi-bridge · lane-1

固定源 `6c683289a3191ee6c92cf4f9065ca9b6cb2c0784`，Apache-2.0；SR `3ec558fc`、准则库1.6.1。用途**推断**：双路HDMI→各四lane CSI-2视频附件。123器件、54电容、4页；KiCad10.0.7 strict成功，XML/db 530端点零归网差异。无采购BOM；6个准确原厂手册族已取得。

| 指标 | 数量 |
|---|---:|
| 计划 / 功能框架 | 797 / 34 |
| 局部已判 / 逐ID needs_human | 108 / 689 |
| 已判 PASS / FAIL / NA | 78 / 8 / 22 |
| 归因条目 | 37 |
| true_defect / false_alarm | 3 / 22 |
| criterion_issue / knowledge_gap / needs_human | 0 / 3 / 9 |
| Top50漏问根因 / 已确认硬件漏检 | 2 / 0 |
| 门禁 | **FAIL，valid=false / NO_GO** |

1. **先合并：NET-A01尊重原生NC。** J6的16条悬空全有NC十字；另两条HPD/HPDI误报经已贴两只0Ω到同源导通，不能只看相邻网名。应以带/去NC、断开0Ω的配对回归保留检出能力。
2. **真实问题来自逐脚核查。** PCA9517ATP为HWSON8，符号却采用SO8编号；PCB编号未补偿。APLL的100nF接DAOUT、PFIL却NC，须移到PFIL。7C有源XO直挂47pF已超手册15pF负载条件；这是规定区偏离，不宣称实测失效。三根因均有原厂页码/图面和可表达种子。
3. **自动计划漏问两处。** TPD8S009有VCC的8路ESD阵列被问成4条TRIP/NOTRIP，漏PRO-E02；桥G5复位/参考时钟的接收端极值依赖未问PWR-C24。已用rule_gaps补2项；钳位配合/复位仍缺系统或厂家保证，不能拿原板当已证电气故障种子。

**用法坑：** IC前缀LDO和Y前缀XO须`--require-ref`才取得准确手册审计；有源XO不套晶体CL。schema15不能表达未定外部合同的needs_human：只填6个已证失败功能，其余28框架保留旁账；不造完整PASS或VENDOR_DATUM。报告由原脚本生成，门禁保留FAIL，**仅诊断，不是整板可用审查结论**；未打包。689项均有具体ID/对象/待核输入，不能把原生“资料不足0”当已审完。

[生成报告](审查报告.md) · [逐条归因及50条核对](findings.json) · [完整台账](/Users/skyfend/.cache/sr-boards/antmicro--hdmi-mipi-bridge/review/review-results.json)。报告标准record索引未打包；原图、PDF、db、手册与图证只留缓存，未复制第三方电路到本仓库。

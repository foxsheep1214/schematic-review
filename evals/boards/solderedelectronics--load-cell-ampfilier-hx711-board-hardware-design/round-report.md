# HX711 称重采集板 · lane-4

固定源 `3440ad0996cce887954f5af0fb2dc2d8b4fc5d51`；TAPR-OHL-1.0；ANALOG、POWER_CONVERTER（用途推断）。KiCad 10.0.7 strict通过，19器件、1页；同版BOM已读，HardwareWiki只读。

| 指标 | 数值 |
|---|---:|
| 计划：原生 + 补查 = 最终 | 76 + 7 = 83 |
| 结果 PASS / NA / 未闭 | 26 / 7 / 50 |
| 归因观察（含候选排除及1条INFO纠错） | 26 |
| true_defect / false_alarm / criterion_issue | 0 / 4 / 0 |
| knowledge_gap / needs_human | 3 / 19 |
| Top50核对 / 覆盖漏项 | 50 / 6 |
| 门禁 / 记录对账 / 正式渲染 | FAIL / valid=true、errors=0 / 退出2拒绝 |

1. **最应先修ADC对象过滤。** 已核U1为adc_dac，INNA/INPA/INNB/INPB仍被ANALOG_PIN漏认，原计划称“无ADC脚”；ANA-C01与ANA-C03均不展开。先补角色/通道别名及覆盖种子，避免核心称重输入范围整段漏审。
2. **内置稳压不是独立料号才能查。** BASE→Q1.B、AVDD→R3/R4→VFB已形成明确调节链；C1/C2却隔10Ω，缺PWR-C04/C05对象。标称AVDD=4.298780V不等于全温保证；未确认3.3V承诺，未据此报硬件缺陷。桥激励支路另缺PRO-C04，不能因无保护件不枚举。
3. **合法NC及源方向需模式证据。** XO在XI=GND的片内时钟模式允许不接，排除3条扫描候选；AVDD的INFO把K1.5负载反向认成外部供电源，已按K3→Q1→AVDD纠正。PD_SCK高>60µs能关闭ADC/桥，另补默认态项。

**用法坑：** BOM为分号且值列名Designation，转换后read_bom保留原始摘要；非电气G***/REF**行不作器件。去耦C/R前缀仍须声明components，AVDD零直接电容清单可完整但不等于合格；Diodes厂商名误提示diode，准确标题+kind_reason核回PNP。schema文档14/运行15；原生无needs_human类型，不能虚造VENDOR_DATUM换取报告。台账全部83项有记录，50项外部边界/资料未闭；交付《审查报告.md》明确是执行记录，不能冒充正式审结。种子用于对象覆盖，未绑定电气契约的不得宣称FAIL。

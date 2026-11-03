# bondus--klippertoolboard · lane-4

固定源：`bondus/KlipperToolboard@56c97f0f4dc59ec77bf3df63bd031cea49c12c7d`；GPL-3.0；126器件，KiCad10.0.7严格解析。用途推断：Klipper工具头，CAN/USB、步进电机、双风扇/加热、热敏ADC、SPI加速度计。

|计划/有记录|完成判定/未终判|观察|真缺陷|误报|准则问题|知识缺口|待人工|覆盖漏报|
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|572/572|114/458|43|1|16|0|4|22|5|

**FAIL / NO_GO，valid=false，原生门禁78错误；renderer退出2。** PASS62/NA51/FAIL1；交付“审查报告.md”明确为执行记录，不是原生正式报告。观察含全部11条扫描输出及根因归并项，不能读作43个电气缺陷。

1. **已证偏离**：R27=2.2k上拉USB D+；ST DS5319 Rev20 PDFp73 Table45脚注2指定1.5k。建议1.5k/1%并同步BOM；未推断实物必然枚举失败。
2. **重复误报模式**：TPS54202 EN允许悬空；TMC2209 VREF允许开路；SPI的SDA/SCL别名误建I2C、自举BOOT误作strap、未用Micro-B VBUS误作IC去耦。Q3替代JSM7788已写在图中，不指控为未说明错采购。
3. **优先合并**：先修真实物理端点枚举：热敏ANA-C03不能落在U1；其次内部5VOUT输出电容/UVLO、三脚CAN TVS与集成OCP计时。5项都是覆盖漏问，未证明5个板级失效。

用法坑：JP3未知会污染无关阻容，改为开/闭两装配；三脚JP1/2切桥仍需逐对映射。R38“120 100mW”语义明确但解析器拒绝，保留原文；Comment列不要映射成会被read_bom丢弃的Value。缺对端/受控工况不伪装VENDOR_DATUM；未闭项/F1/预判约束如实留FAIL。详见 findings.json、审查报告.md、top50-audit.md。

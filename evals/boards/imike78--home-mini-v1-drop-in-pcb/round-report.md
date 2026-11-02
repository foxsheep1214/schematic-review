# imike78--home-mini-v1-drop-in-pcb · lane-4

固定提交 `b912ebd`；CERN-OHL-S-2.0；241器件/6页。用途推断：ESP32-S3＋XMOS语音音箱主板；catalog AV/USB/RF/POWER_CONVERTER，并补I2C/SPI/STARTUP/POWER_PROTECTION。KiCad CLI 10.0.7；strict因AE1.1缺名回退。

|计划|确定判断|未闭|归因总数|真缺陷|误报|准则问题|知识缺口|待人工|漏报|
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|815|65（63 PASS/2 FAIL）|750|46|2|30|0|2|12|2|

**门禁 FAIL / NO_GO**，179条校验错误；renderer退出2，拒绝正式报告。交付的《审查报告.md》明确为执行记录，未打包；815项均有登记，750项尚未审完，不能称“完整审查已通过”。46条仅计40条扫描、5条独立观察和1条软件误报。

1. **优先合并修清单重放上下文**：I2C context漏power_rails，同db从6段变10段；补回原声明后主体完全一致。F46给文件/函数与复现实验；不能靠改inventory消掉过期错误。
2. **两条确认问题有独立证据**：R2=200k，MPR121 Rev4 PDFp2要求75kΩ/1%（P1）；U5 Datasheet写AP2112、采购ME6211（P2数据引用错误）。C17局部下界17.6µF虽低于TPS62827要求20µF，磁珠后容量未定界，保持待确认。
3. **误报/漏问均落到对象**：MPR121电极/铜测试点不是无驱动数字输入，XU316 JTAG有准确PU/PD，QSPI D/HD是不同脚；D4入口TPD钳位漏PRO-E02、U6→U14功放控制漏RST-T04。两个漏报是覆盖问题，未伪称电气违规。

用法坑：DNP测试铜不能按DNP元件消失；非标准轨名必须显式声明但context未保全；AV器件标题落泛称ic须手工补功能；C/D/T已在计划但未审完不再计自动漏报；F1条款要求与剩余审查分开，REVIEW_INCOMPLETE不能改名VENDOR_DATUM。无独立BOM，原生MPN/Description仍需逐字段核；13个IC手册已取，HardwareWiki只读，全部Top50对照见缓存top50-crosscheck.json。

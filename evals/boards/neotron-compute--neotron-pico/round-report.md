# neotron-compute--neotron-pico · lane-3

源：`Neotron-Compute/Neotron-Pico@f078d9977104968c83bb603bdcde0fd8731324a7`，CC-BY-SA-4.0。Pico复古计算机：VGA、音频、SPI/SD、BMC、RTC、稳压及USB双源。KiCad 10.0.7，242器件/13页。

| 项目 | 数量 |
|---|---:|
| 最终计划（含5补项） | 895 |
| 已关闭/已证：PASS / FAIL / NA | 117 / 3 / 64 |
| 保留未定的检查项 | 711 |
| 归因条目总数 | 328 |
| true_defect / false_alarm | 3 / 77 |
| criterion_issue / knowledge_gap / needs_human | 0 / 52 / 196 |
| 漏报对象 / Top50核对 | 5 / 已核对50条 |
| 原生门禁 | **FAIL · valid=false · NO_GO** |

1. **合并步先修铜桥语义**：NT901–NT912不采购但保留PCB铜；按DNP断开造成24条地址脚悬空。另44条去耦误派来自配电连接器、HPGND及模组输出；SPK_P/N也不是差分数据。
2. **实证与未知分开**：C1306=25V跨VDC却声称30V输入；Q1302的PNP字段指NPN资料；DS1307图注0x6F应为0x68。RTC焊桥、AMS1117陶瓷稳定性及30V下BJT应力仍待确认。
3. **漏问是具体对象**：PA0/PA1监测ADC、Codec ADC、Pico复位期OE、Ctrl齐纳及G/S齐纳补5项；晶体已有CLK-C01，不能重复计漏。

坑：原生schema15不能承载本评估的两种待判分类，另有条款/数值结构和对象范围错误（2893条），**报告不可用于定稿**；不是有效打包交付。strict缺U303.2/.4名保留，TI脚图手核未改db；无独立BOM，XML列转表读取不冒充独立物料表。Pico完整PDF已取得；DS1307仅官方摘录，其他准确手册的下载失败已登记。

计数按报告开放任务、已证根因和逐条误派归因，非328个电气缺陷；Top50“覆盖”不等于通过。[归因及50条证据](findings.json)；[报告原样副本](审查报告.md)。完整台账/证据在 `/Users/skyfend/.cache/sr-boards/neotron-compute--neotron-pico/review`（未将第三方电路文件入库，报告的record链接需在缓存查阅）。

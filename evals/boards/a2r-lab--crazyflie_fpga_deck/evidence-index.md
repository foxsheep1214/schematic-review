# 审查证据索引与计数边界

该目录只放自主编写的审查/归因材料；第三方工程、XML/db、BOM、手册和图面留在缓存。本报告由render_report.py生成后逐字节复制；gate valid=false、release=NO_GO，未打包。报告内默认record/索引和图片链接依赖打包流程，此次不构成可发布审查包；使用下面的实际缓存路径。

- [完整计划](/Users/skyfend/.cache/sr-boards/a2r-lab--crazyflie_fpga_deck/review/review-plan.json)：394项，18功能框架。
- [局部结果](/Users/skyfend/.cache/sr-boards/a2r-lab--crazyflie_fpga_deck/review/review-results.json)：82项局部独立判断，77 PASS/5 FAIL；2个唯一已确认缺陷。没有完整功能PASS。
- [每个计划ID的状态](/Users/skyfend/.cache/sr-boards/a2r-lab--crazyflie_fpga_deck/review/item-review.json)、[312项needs_human及原因](/Users/skyfend/.cache/sr-boards/a2r-lab--crazyflie_fpga_deck/review/pending-checks.json)、[18个功能框架完整未完范围](/Users/skyfend/.cache/sr-boards/a2r-lab--crazyflie_fpga_deck/review/pending-functions.json)。
- [原生校验](/Users/skyfend/.cache/sr-boards/a2r-lab--crazyflie_fpga_deck/review/review-gate.json)：FAIL / valid=false / NO_GO；380个格式/覆盖错误，包括未判方面与缺功能记录。既有局部判断不会令全板通过。
- [缓存中的生成报告](/Users/skyfend/.cache/sr-boards/a2r-lab--crazyflie_fpga_deck/review/审查报告.md)、[HTML](/Users/skyfend/.cache/sr-boards/a2r-lab--crazyflie_fpga_deck/review/审查报告.html)。
- [原图新导出PDF](/Users/skyfend/.cache/sr-boards/a2r-lab--crazyflie_fpga_deck/review/current-schematic.pdf)、[U1供电现状局部](/Users/skyfend/.cache/sr-boards/a2r-lab--crazyflie_fpga_deck/review/evidence/fpga-power.png)、[建议改接](/Users/skyfend/.cache/sr-boards/a2r-lab--crazyflie_fpga_deck/review/evidence/vccadc-after.svg)。
- [独立计算与逐条依据](/Users/skyfend/.cache/sr-boards/a2r-lab--crazyflie_fpga_deck/review/evidence/engineering.md)、[逐组直接电容](/Users/skyfend/.cache/sr-boards/a2r-lab--crazyflie_fpga_deck/review/evidence/direct-capacitors.json)、[源锁和归网核对](/Users/skyfend/.cache/sr-boards/a2r-lab--crazyflie_fpga_deck/review/source-lock.json)、[U1官方针表对读](/Users/skyfend/.cache/sr-boards/a2r-lab--crazyflie_fpga_deck/review/pinmap-u1.json)。
- [资料审计](/Users/skyfend/.cache/sr-boards/a2r-lab--crazyflie_fpga_deck/review/datasheet-audit.json)：DS181、TPS65023B、LM3880和ASE分支为本地PDF；ASE资料不证明X1真实采购身份。UG480仅核官方在线Table1-1，完整PDF未取得；Infineon全文下载受WAF阻挡，不能据空文件声明AVAILABLE。
- [官方UG480条款](https://docs.amd.com/r/en-US/ug480_7Series_XADC/XADC-Pinout-Requirements)、[Infineon准确产品](https://www.infineon.com/part/S25FL128SAGNFI000)。

`findings.json`的75条是逐条扫描警报/候选与工具、资料、人工根因的归因条目，不是75处板级电气缺陷；四处misses是原生计划/模型漏问，均已补问，0处已确认原板电气漏检。相同根因多物理脚告警保留逐条记录。用户要求只评估一块板，未对驱动脚本/技能实现作改动。

报告SHA-256：`8c7ce47801d1e199a187872c13b56497b05dccee4b1b41c0a81fdcf4872f4b43`。

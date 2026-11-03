# the-flame-trench--singularity · lane-4（合并步 5 补做）

用途**推断**：PocketQube 星载计算机 OBC-1，TMS570LS1227 锁步 MCU（U11）、两路 TPS62850 经 LTC4353 理想二极管 OR 成 1V25 核心轨、三路 SN65HVD230 CAN、SPI FRAM/Flash、RV-3032 RTC 带 CeraCharge 备份电池；CERN-OHL-S-2.0，源锁 `014e988`，SR `1cd885b`。lane-4 当时因模型容量退出，本轮从资料取证起全部重做。

| 项目 | 数量 |
|---|---:|
| 器件 / 页 / 计划项 | 121 / 12 / 612 |
| 手册可用 | 5/9（TPS62850、SN65HVD230M、TMS570、TMP100、TPS3813；另有 TCXO 与 CeraCharge 规格） |
| 电路 | 14 块（候选 8 个、决定 16 条） |
| 冷扫非 INFO | 156（NET-A01 145） |
| 归因发现 | 17 |
| true_defect / false_alarm | 1 / 10 |
| criterion_issue / knowledge_gap / needs_human | 0 / 3 / 3 |
| 漏问 | 1（CLK-D03） |
| 门禁 | not_run |

最重要的三条观察：
1. **真缺陷：削顶正弦 TCXO 直连 OSCIN**。X2 输出 0.8 Vpp 削顶正弦、无隔直，TMS570 手册 §6.6.1.1 要求外部时钟 0–3.3 V 摆幅。计划里 CLK-D01 问到了这一点，自动层不会报。
2. **NET-A01 逐脚淹没**：TMS570 的 141 个未用球逐条 CANDIDATE，手册写明内部上下拉允许悬空；真正该看的 ADREFHI/ADREFLO、nERROR 埋在里面。需要器件级允许悬空条款库（合并步 5 第 4 项）。
3. **识别缺口串起来的误报**：CeraCharge 电池被当电容（PWR-A02 无驱动、CLK-D03 漏问），nPORRST 不认作复位输入（RST-A06），有源 TCXO/RTC 模块被问晶体 CL（CLK-C01），理想二极管 OR 被套 eFuse/防反接模板。

用法上的坑：custom TFT 库的 IC 没有 device_kinds 时整板只出 DEBUG 一个候选；CAN 收发器的 quote 在手册 p2，不在 p1。S70FL01GS 的 PDF 无文本层（本机无 pdftotext），WP# 内部上拉未能核。

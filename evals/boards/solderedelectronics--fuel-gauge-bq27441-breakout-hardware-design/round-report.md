# BQ27441 电量计板：lane-3 本轮审查

来源：`SolderedElectronics/Fuel-gauge-BQ27441-breakout-hardware-design@82e9af6d5458`，V1.0.0，TAPR-OHL-1.0；KiCad 10.0.7 strict成功。用途为据README/图面推断；industrial_telecom基线。

| 计划项 | 已处置 | 发现根因 | 真缺陷 | 误报 | 准则问题 | 知识缺口 | 待人工确认 | 漏报 | 门禁 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 191 | 191 | 18 | 2 | 5 | 0 | 4 | 7 | 2 | FAIL |

47 PASS（含4个覆盖汇总）、5 FAIL（对应2根因）、12 NA、127待判；“已处置”不等于已证明电气正确。

1. **真实偏离分两件**：R7=1.8M将BIN拉到VSYS，违反TI SLUSBH1C p4“仅接VDD”；JP1默认铜桥使R2/R3=10k把U1 SDA/SCL拉到5V，超p5推荐上限3.6V，不能以6V绝限放行。R8/GPOUT的VSYS上限未给，单列待确认。
2. **先修对象与归属**：K4/K5 easyC因K前缀误作继电器；U2双MOS翻译误作功率候选，reject后又被add占用限制挡住重归。合并步优先修强符号角色识别及拒绝后重归，并补双通道测试；不全局屏蔽K器件或MOS告警。
3. **Top50已50/50核对**：2个覆盖漏报是U1 BAT/SRP/SRN ADC量程（ANA-C03）、K4/K5外部电源/信号故障（PRO-D04）；U2已有I2C区域SIG-C08，重归失败不重复计为该主题漏报。未把缺上游保护/负载条件当已证硬件缺陷。

**用法坑**：分号BOM须无损转逗号再read_bom；跳线状态取同版PCB实体铜桥，不靠TRACE名字猜。普通C4/JP4不应被索取为控制器手册；U1内部VDD输出不是无驱动。schema15不能承载本任务要求的needs_human/知识缺口，另有9条纯拓扑/共享缺口的条款承载限制：273条格式错误如实留在门禁，报告标明不可作有效SR交付；不打包、不改检查器、不提交。

[完整审查记录](/Users/skyfend/.cache/sr-boards/solderedelectronics--fuel-gauge-bq27441-breakout-hardware-design/review)；[完整报告](/Users/skyfend/.cache/sr-boards/solderedelectronics--fuel-gauge-bq27441-breakout-hardware-design/review/审查报告.md)。仓库报告为脚本原样副本，其record/索引依赖缓存目录；来源与所有哈希见缓存input-lock.json，逐条归因/修复建议/种子见同目录findings.json。

# lane-3：单节锂离子电池保护板

来源：[SolderedElectronics 固定提交75ca4de](https://github.com/SolderedElectronics/1S-Li-Ion-battery-protection-hardware-design/tree/75ca4de501076beb9bc9f8208005bc9ee2de2a59)；V1.0.0；TAPR-OHL-1.0。用途从README/文件名**推断**，类型 POWER_PROTECTION、ANALOG；准则基线 industrial_telecom。KiCad 10.0.7 strict导出/解析成功，15器件；同版BOM及原理图PDF均已核。

| 计划项 | 已逐项判断 | 归因事项 | 真缺陷 | 误报 | 准则问题 | 知识缺口 | 待人工/设计者确认 | 漏报 | 门禁 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 95 | 95 | 14 | 0 | 5 | 0 | 5 | 4 | 2 | **FAIL** |

独立台账：PASS 28、INSUFFICIENT 54、NA 13；“14”是合并同因后的归因事项，不是14处电气故障。5项知识缺口包含3个本轮已解决的悬空脚候选，未把正确CANDIDATE冒充检查器误判。原生confirmed_defects=0。Top50逐条核对50/50，按根因合并为2个漏报。

1. **先补双MOS通道覆盖（M01）**：FS8205A第二栅U2.5/OC未被枚举；只断OC的网表变异后仍只生成U2.4检查。合并步优先逐通道生成驱动/SOA检查，加第二栅开路回归种子。U2内部D12共漏极不需要外部短接，不能把U2.1/8空脚判主通路断开。
2. **保护类型过宽与资格过窄同时出现**：同一电池的焊盘/JST触发3项双源切换，普通C1触发eFuse，CS模拟采样触发数字电平；反而DW01的过流/短路动作时间PRO-C05没生成（M02）。过流检测用MOS导通压降，R2=1k只是CS保护串阻。
3. **缺范围不等于电路坏**：DW01过充动作4.25–4.35V并非电芯许可界；FS8205A标称6A并非本板保证电流。缺电芯、源阻抗、I(t)、温度、端口物料与反接合同，不能从条件算例判损坏或安全。没有证据支持本轮修改准则正文。

**用法与边界**：HardwareWiki只读检索无DW01/FS8205命中，已取Fortune原厂完整PDF并核p3–7/14–15。BOM为分号CSV，转换分隔符后read_bom；两种地是开关前后负端，不是安全隔离。补C1类别/应用条款后清单摘要变化，必须重新生成并逐项重审，旧冷扫仅留档。schema15只接受VENDOR_DATUM/REVIEW_INCOMPLETE；本轮忠实保留needs_human/评估知识缺口，**不伪写厂家独占参数**。最终125条校验错误（108条开放原因映射、8条种类、9条功能条款承载）未关闭，生成报告保留“结论不可用”横幅，未打包或声称有效审查准出。

可复核入口：[findings.json](findings.json)（含全部归因、7条修改提案/1个可网表化种子及50项核对）；[生成报告](审查报告.md)。完整网表、BOM、手册哈希、95项独立理由、计算与门禁错误在 `/Users/skyfend/.cache/sr-boards/solderedelectronics--1s-li-ion-battery-protection-hardware-design/review/record/` 与 `evidence/`；第三方文件仅留缓存，公共代码未改，未提交。

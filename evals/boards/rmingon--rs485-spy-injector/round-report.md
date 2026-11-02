# rmingon--rs485-spy-injector · lane-2

**受限审查，门禁 FAIL / valid=false，报告不可作冻结依据。** 源 commit `6825846c45c09ddbdd03d043de9759f304b46edb`，CERN-OHL-S-2.0 已从固定提交核实。KiCad 10.0.7 严格解析 44 件；SR `04c6b5e`。用途从 README 推断为 ESP32 双路 RS485 监听/注入、USB 编程板；工业通信基线。catalog 的 LEVEL_SHIFT 已排除：Q1/Q2 是同 3V3 下载互锁；补入 LDO、启动和 UART。

| 项目 | 数量 |
|---|---:|
| 最终受限计划 / 独立可判 / needs_human 计划项 | 278 / 127 / 151 |
| 原生台账 PASS / FAIL / NA / INSUFFICIENT | 50 / 24 / 53 / 151 |
| 报告及扫描逐条归因 | 112 |
| true_defect / false_alarm / criterion_issue | 5 / 21 / 0 |
| knowledge_gap / needs_human / misses | 0 / 86 / 0 |
| 独立确认根因 / Top50逐条核对 | 2 / 50 |

计数按报告根因、待办、非 INFO 扫描项及对象误识别逐条计；true_defect 的 5 条含同根因的重复报告，**仅 2 个独立根因**。关联见 findings.json 的 root_cause/check_ids，不是 112 个硬件故障。

1. **先修候选状态合同。** 5 候选/9 决定/0 未归属，但 RS485-U4/U5 的 states=[] 被后续扫描拒收。保留失败证据后才生成无候选回退计划，没有造需求补运行态。合并步先补 `catalog.CANDIDATE_STATES` 并回归两路 accept→冷/热扫描；此问题会影响其他总线板。
2. **确认问题与条件风险分开。** J4.CC1/CC2 无 Rd；7 只 R_Small 和 C1–C7 无数值且无 BOM，构成两类源设计问题。10k/120Ω 本地偏置仅 19.68mV；GPIO15 默认上拉接 U5.DE；J1/J4 共 +5V。后三者缺外部偏置/允许状态/双源约束，未指控必然现场失效。
3. **误识别可重复。** 5 个 CH340 未用输入有原厂允许悬空条款；J8–J11 是 DIP，产生 12 条外接口误问；Q1 漏极误当 EN；BSS138 应用段被误当 gate-driver 标题。另 1 条候选状态问题，合计 21 条误报归因。Top50：14 条适用或条件适用已有检查/缺值发现，36 条结构不适用；无证据确立额外漏报，不把 C/D 规则无自动命中算漏报。

**用法坑：** boards 的 needs_human 与 schema15 仅允许 VENDOR_DATUM/REVIEW_INCOMPLETE 不兼容；如实扩展记录导致 350 条派生拒收（48 个原作者/实贴依赖），没有伪装成厂家缺参或已答需求。报告由 render_report 原生生成并原样复制；未打包准出。MAX3485 原厂直链超时，完整 Rev0 从 DigiKey 取得，关键表与 ADI Rev2 在线页核对；不是只拿到预览。完整台账、手册哈希、50条核对和算例在审查缓存，仓库不含第三方电路文件。

[逐条归因与Top50](findings.json) · [原生无效报告](审查报告.md) · [审查缓存](/Users/skyfend/.cache/sr-boards/rmingon--rs485-spy-injector/review/)

# antmicro--sdi-mipi-bridge-hw · lane-3

SDI→双MIPI CSI-2桥（GS2971A＋CrossLink），含SDI环出、27 MHz晶体、1.2 V LDO及I²C/SPI控制。用途为推断；基线 industrial_telecom。固定提交 `0d08a865`，Apache-2.0，KiCad 10.0.7严格解析186件；24件DNP。

| 指标 | 数量 |
|---|---:|
| 最终计划／已有明确判断／未定 | 509／80／429 |
| PASS／NA／FAIL检查 | 53／25／2 |
| 归因条目（根因或待补输入） | 201 |
| true_defect／false_alarm | 2／8 |
| criterion_issue／knowledge_gap／needs_human | 0／28／163 |
| Top 50覆盖漏报 | 2 |
| 门禁 | FAIL（valid=false） |

1. **先修I²C上下文重建。** 同一db与库存自带context重建，两个上拉的来源从declared退回name-hint，造成库存摘要变化与49项对象校验连锁错误；差异仅5处，已有独立复现。不能删检查或忽略摘要。
2. **确证偏离与合法结构分开。** D01：U4.D5辅助3.3 V早于U1建立核心1.2 V，违反CrossLink p30顺序；D02：USER_SCL/SDA命名互换及J4误标I²C。LB_CONT浮空、BYP接OUT、VCO的105 Ω均有原厂依据，不改成“常见接法”。
3. **两项是目标规则覆盖缺口。** FPGA配置期关键输出漏RST-T04；BYP软启动漏PWR-D03。晶体CLK-C01、I²C上拉SIG-C01已有对象，缺数据不重复算漏报。Top 50全部逐条登记；未发现准则本身不可判的证据。

用法坑：BGA被按1–80枚举，ABM7的Microprocessor Crystal被认作MCU；未启用上拉岛/备用触点仍展开活动I²C义务。默认装配R89不贴，不能误读为复位硬接地。原生schema15不承载NEEDS_HUMAN；门禁还含本轮条款/绑定记录未满足项，不全归咎工具。完整原始FAIL保留，报告不可用于准出，未打包。

工作记录：[台账](/Users/skyfend/.cache/sr-boards/antmicro--sdi-mipi-bridge-hw/review/review-results.json)、[门禁](/Users/skyfend/.cache/sr-boards/antmicro--sdi-mipi-bridge-hw/review/review-gate.json)、[缓存带图报告](/Users/skyfend/.cache/sr-boards/antmicro--sdi-mipi-bridge-hw/review/审查报告.html)。仓库MD是脚本报告原样副本，相对证据依赖缓存；本地取得4份PDF，U1/U2仅在线相关章节已读，U3/LED完整资料未取得。

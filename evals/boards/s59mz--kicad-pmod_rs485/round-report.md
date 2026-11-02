# lane-3｜s59mz--kicad-pmod_rs485

| 数字 | 本轮 |
|---|---:|
| 类型 / 输入 | RS485、ISOLATION、POWER_CONVERTER；31器件/25网，strict通过 |
| 最终计划 | 137（原生133 + rule_gaps补4） |
| 逐项结果 | 35 PASS / 6 NA / 2 FAIL / 94待判；137项均有记录 |
| 发现归因（根因/报告任务） | 25 |
| true_defect / false_alarm / criterion_issue | 1 / 4 / 0 |
| knowledge_gap / needs_human | 3 / 17 |
| 漏报 | 3（目标规则覆盖缺口，非3个新增电气缺陷） |
| 门禁 | FAIL，valid=false；217错误=208分类承载错误+9条款承载错误 |

1. **优先合并复合器件的隔离/电源能力模型。** U1核验为transceiver后仅识别RS485，域推导反把芯片所有脚视为导通；GND/隔离侧被误合并。用官方屏障/侧别同时驱动domains和候选，补PRO-D02/C03、PWR-C04/C06；不能改角色丢掉RS485或编辑候选过关。
2. **确有1处旁路结构问题。** U1.12对11/14直接只有C6=100n，C8=10u在FB1/FB2外；Rev.H p17要求多频并联组合。两FAIL归同一D01，非两个缺陷；整改是在两珠器件侧增10u级储能。终端则为(120+120)∥(120+120)=120Ω，未误判30/60Ω；J3/Tx、J4/Rx须先确认视角。
3. **误报/未知不能升级成硬错。** D1/D2空脚差集仍卡资料、J2短路帽误作外部口、库名多派UART。HBM≠系统ESD；没第三根参考线≠已证共模越界；FB=600无频率/DCR是资料缺口。未确认准则本身不可判，criterion_issue=0。

用法坑：`input_sha256`须用board_intent.input_fingerprint，不能替换成文件哈希；先读入固定commit CSV再建计划。`features`无法补被候选漏掉的两类，已记录失败尝试，改用rule_gaps；实际电压窗未知就留空并保留诊断，不能把3.3V名义/典型值写成保证。schema15只容VENDOR_DATUM/REVIEW_INCOMPLETE，不支持本任务五类评估中的待确认；本轮不伪造厂家数据或无关强制条款，因此保留FAIL。本地完整手册仅Rev.0用于身份/脚号，电气按官方Rev.H在线相关页；不冒称新版全文下载成功。

产物：`审查报告.md`为原样生成快照，非可打包准出报告；完整台账/哈希/图面与证据留[审查缓存](/Users/skyfend/.cache/sr-boards/s59mz--kicad-pmod_rs485/review)。本仓库不复制第三方图纸或手册，快照中的打包式相对图链需在缓存查看对应证据。Top50共50条逐条核对见`top50-audit.md`。未改SR源码/准则、未写HardwareWiki、未commit/push。

# antmicro--cm4-baseboard · lane-2

固定源 `d248c2921e8e`，Apache-2.0；KiCad 10.0.7 strict 导出，506器件/9页。用途推断：CM4/CM5载板，PoE PD、Ethernet、USB、多路电源及扩展接口。

| 项目 | 数量/结果 |
|---|---:|
| 计划项（受限合并清单，完整候选未展开） | 1286 |
| 已逐项记录 / 独立审结（PASS+NA） / 未决 | 1286 / 271 / 1015 |
| 报告归因条目（不是硬件故障数） | 299 |
| true_defect / false_alarm / criterion_issue | 0 / 40 / 0 |
| knowledge_gap / needs_human | 112 / 147 |
| Top50核对 / 确认漏报 | 50 / 0 |
| 候选 / 候选归属错误 / 原生门禁 | 33 / 35 / FAIL，NO_GO |

1. **合并步先修候选共享模型**：C302–C307同接VCC，三个独立buck合法共享输入，却被“最多两个持有”拒绝；大量端口沿+3V3/+5V带走无关器件。保留决定与失败日志，未硬并电源级。当前1286项清单不是完整候选计划。
2. **可复现的误提示**：AP62600.9是内部VCC；TXB0104未用匹配对同接GND合法；100k/15k VBUS检测分压必须分网。XML的Val、DNP和真实引脚角色应先于电源/冲突判定。I2C还扩散到地址绑带、Microwire、RESET/FB和电源，先修Inventory.seeds/state_inventory。
3. **未决与漏报分开**：D301确在防反器件前，但反接源/上游切断未给，PWR-C26已经提问；晶体负载已算5pF/9pF加寄生，缺原厂/脚电容边界，不伪造失配。Top50未发现可独立确认且没有被问到的电气问题。

**用法坑**：input_sha256是board_intent.input_fingerprint，不是文件字节哈希或db_fingerprint；无独立装配BOM，原XML自定义字段另存证据。11种完整PDF已核，17种资料未绑定；网页摘录不是本地全文。任务允许needs_human，原生schema15不接受，本轮显式保留后门禁拒收（3698条记录错误），报告醒目标明不可用于冻结；没有伪造厂家数据/用户答复或把它改成PASS。全部台账在 `/Users/skyfend/.cache/sr-boards/antmicro--cm4-baseboard/review`。

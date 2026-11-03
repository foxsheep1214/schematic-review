# antmicro--m2-smart-iot-module · lane-2

来源 `antmicro/m2-smart-iot-module@c986781e695ddd2d98287446182a0243d5538d26`，Apache-2.0；SR `1300d9e`。用途由README推断：M.2 nRF52840无线/Coral AI实验模块，含PCIe-USB、SPI/Microwire、I²C与低压电源；基线industrial_telecom。212件、7页；无独立BOM，按XML的MPN/Val/DNP审查。

| 项目 | 数量 |
|---|---:|
| 最终计划 / 已逐项判定 | 586 / 586 |
| PASS / FAIL / NA / 资料不足 | 109 / 12 / 34 / 431 |
| 归因条目 | 108 |
| true_defect / false_alarm / criterion_issue | 5 / 41 / 0 |
| knowledge_gap / needs_human | 30 / 32 |
| Top50逐条核对 / 覆盖漏项 | 50 / 6 |
| 原始扫描逐条归因 | 38 / 38 |
| 原生门禁 / 打包 | FAIL / 未打包 |

计数口径：108含5个确认缺陷根因、62个报告开放任务、25个已排除扫描和16个计划范围/角色误报；不是108个硬件故障。12个FAIL归属5个根因。所有缺陷有seed，41条误报与6条漏项均有proposed_fix；覆盖种子不冒充原板已证故障。

1. **准确变体能改变结论**：U7默认DBZ的GND1/RESET2被对调，且2.93V门限不适用1.8V轨；U10固定5V的VOUTS7误接可调分压；U1 PWREN#54硬接地；Coral AON3.3V而49/50接地电阻DNP。前3处接线用同提交PCB焊盘复核。未把27.75V形式反推值说成实际过压。
2. **合并步优先修晶体枚举**：Y1/Y2/Y4接地壳脚的`power_in`被当作有源供电脚，三颗均漏CLK-C01；仅Y3被问。另有U5/U9无EN脚遗漏充电电流比较，以及FTDI/nRF经串阻遗漏SIG-C08。六项均是明确对象的覆盖缺失，参数不足未升级为电气故障。
3. **来源/角色须逐端核**：U5/U10/nRF片内输出不是缺供电，Y4无源端不是第二驱动，U10.EN经R33/R62有偏置，J1为RF测试口而非配电口。buck/boost regulator标题词形也会漏核角色。

用法坑：strict仅因Y3/Y4六脚缺名而回退；I²C库存的全局完整性阻断已用局部原生端点/手册复核解释。原生schema15没有任务所需NEEDS_HUMAN；62个开放项及其派生字段共1786条拒收，其他结构错误已处理，未编造需求、厂家保证或潜在等级求PASS。报告由render_report生成并原样复制，属于失败诊断件，不支持定稿。完整台账、50条核对、手册来源/哈希、计算和校验位于 `~/.cache/sr-boards/antmicro--m2-smart-iot-module/review/`；报告中的record相对链接须从该缓存查阅，未制作有效交付包。

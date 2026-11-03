# newell--nixie-clock-esp32c3 · lane-2 单轮审查

固定源 `49bbd6b3f39c`；SR `d439e9e04f81`；KiCad 10.0.7 strict成功，236器件/7页。用途推断：ESP32-C3辉光时钟，AV/CLOCK/POWER_CONVERTER/RF；新增保护、启动、USB、RGB电平转换边界。硬件实际CERN-OHL-W-2.0，catalog MIT对应软件，未改目录。

| 项目 | 数量 |
|---|---:|
| 计划项 / 已判项 | 788 / 788 |
| 归因发现（根因/任务/错误提示，不等于故障数） | 94 |
| true_defect | 2 |
| false_alarm | 17 |
| criterion_issue | 0 |
| knowledge_gap | 12 |
| needs_human | 63 |
| misses | 4 |
| 原生门禁 | FAIL；记录无效，未打包 |

1. **确认两根因**：U4–U11.10清零输入NC，违反TI未用输入固定电平条款；C18/C19的100nF/50V/0805采购码与470nF/1812/≥250V图示要求冲突。17个失败检查归并为2个P1根因，不声称实物已损坏。
2. **可复用识别错误**：Q35 RGB转换被当电源、旁路被当snubber；SW3焊线封装触发连接器；BTL OUTP/N被当差分数据；LDO/TVS入口误套电感/eFuse/保险/切换模型。17个错误项均留应判依据和定位修法。
3. **合并步先统一未决终态契约**：schema15与boards的needs_human/knowledge_gap不兼容，不能用伪造需求/等级/厂家数据过门禁；再优先补USB许可/电压/电容、LDO启动、外引配电支路和RGB掉电4类对象覆盖。未确认设计准则本身错误。

**用法坑**：input_sha256要用board_intent.input_fingerprint，不是db字节hash；partial population会给不相关去耦组带全局缺口。Q35已声明level_shifter仍生成变换器，reject后held不能改类型；保留真实拒绝和遗漏。BOM未提供，不编装配；R1/R2/R53的“NC”不等于DNP。HardwareWiki只读搜到的近型号不能替代。原生格式/去耦声明/条款记录门禁未闭，报告带无效警示；完整台账在板级缓存，报告为脚本原样副本。

# 面包板电源板 · lane-1 本轮记录

来源：SolderedElectronics/Breadboard-power-supply-board-hardware-design，`970af8857240ab5aab04054266a666bf0eb6cb30`，V1.1.1，TAPR-OHL-1.0。25件/24网；POWER_CONVERTER、POWER_PROTECTION，补USB；industrial_telecom。用途为从README/图面推断。

| 指标 | 数量/结果 |
|---|---:|
| 最终计划 / 功能框架 | 185 / 14 |
| 局部已判 / 逐ID待核 | 39 / 146 |
| 归因观察总数 | 30 |
| true_defect | 1 |
| false_alarm | 13 |
| criterion_issue | 0 |
| knowledge_gap | 3 |
| needs_human | 13 |
| Top50漏问 | 1 |
| 原生门禁 / release | FAIL / NO_GO |

1. **合并步先修K2角色识别**：DC_JACK被K前缀当relay，产生伪线圈、伪去耦、伪无驱动，同时漏掉EXT-K2的PRO-D04/DEV-C04等接口问题（M01）。先修强类型优先级，再用J→K等价别名变异验证；漏问不代表已证原板硬件失效。
2. **分开真实资料缺陷和自定义针号**：U2仅给SE5218，厂家p2有多个固定输出档，未唯一指定3V3，确认P2设计身份缺失F24；U1的符号/封装成套自定义2/3号，几何支持正确用途，尚缺受控映射，不能判实物接反。
3. **双源状态不能靠轨名放行**：USB-only时U1.OUT被供电而IN无外部源；两家手册未给足反向耐受。C4名义2.2µF也不证明厂家≥1µF有效要求。保留具体输入/负载/采购或厂家依赖，不编真缺陷或PASS。

用法上的坑：KiCad10.0.7 strict因S1–S3共12个触点缺名失败，宽松解析后独立核XML/db全部70节点一致；分号BOM需先将Designation显式映射Value再read_bom。schema15不接受needs_human/未判功能，因此逐项旁账保留146项、全部14功能未作整体结论，原生FAIL如实保留。渲染报告的“检查39/资料不足0”只是局部统计；DEV-D04独立FAIL还触发无根因任务的格式缺陷。未正式打包，报告不能用于定稿。

50条逐条适用性/反例核对、全部185项处置、修法与种子提案见[findings.json](findings.json)。完整原始资料、计划和门禁只留[缓存审查目录](/Users/skyfend/.cache/sr-boards/solderedelectronics--breadboard-power-supply-board-hardware-design/review/)。没有修改技能、Wiki或第三方电路，没有提交。

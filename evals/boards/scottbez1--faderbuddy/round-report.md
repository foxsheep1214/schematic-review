# scottbez1--faderbuddy · lane-1（合并步 5 补做）

用途**推断**：电动推子控制板，ATtiny1616（U1）读推子滑臂、DRV8837（U2）H 桥驱动推子电机，I²C 级联；Apache-2.0，源锁 `931ed66`，SR `1cd885b`。
lane-1 当时 codex 因模型容量退出，没有交付 findings；缓存里留有中间审查文件。本轮在当前 SR 上重跑原生 XML→冷扫→候选→原决定→候选扫描→合并计划，逐条复核后重写归因。

| 项目 | 数量 |
|---|---:|
| 器件 / 计划项 | 32 / 242 |
| 冷扫非 INFO | 3（全是 DEV-D02 脚名候选） |
| 归因发现 | 15 |
| true_defect / false_alarm | 0 / 7 |
| criterion_issue / knowledge_gap / needs_human | 0 / 2 / 6 |
| 漏问 | 3（RST-T04、SIG-C08、PRO-C05） |
| 门禁 | not_run（未写 schema 15 台账） |

最重要的三条观察：
1. **电机驱动被当稳压器**：DRV8837 按 `motor_driver` 进 POWER_CONVERTER 候选后，PWR-C04（3 行）、PWR-C14（电机输出当轨）照稳压器模板展开；ANA-C05/ANA-D01 被“有 ADC”触发。这是 `subject_precondition` 没看核心器件角色，别的电机板也会重复。
2. **H 桥复位安全态仍然漏问**：RST-T04 在当前 SR 上自动 0 行，只有审查员 rule_gaps 补的那一行；本板按 TI 内部下拉判为安全，但规则该自动问。已落成种子 D-HBRIDGE-RESET-UNSAFE。
3. **F01（安装孔进 DEBUG）已被前几步修掉**：H1/H2 不再进 DEBUG-BOARD；脚名同义（VCC/VDD、GND/THERMAL_PAD）仍报 PIN_NAME_CONFLICT 候选。

用法上的坑：重放用原 intent 时 rule_gaps 会生成 `GAP-` 行，判断“是否已自动报出”要排除这类行。

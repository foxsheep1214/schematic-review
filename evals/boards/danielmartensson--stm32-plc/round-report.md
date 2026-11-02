# STM32 PLC · lane-3 本轮记录

固定源 `dfeea117c864`，MIT；270 器件、9 页，KiCad 10.0.7。用途推断：STM32 混合工业 I/O（ADC/DAC、PWM、CAN、USB、SPI、SWD/RTC）。

| 项目 | 数量/结果 |
|---|---:|
| 最终计划／逐项留记录 | 1047／1047 |
| PASS／NA／FAIL／未定检查 | 141／161／1／744 |
| 归因记录（含开放项与 SR 反馈） | 78 |
| true_defect／false_alarm | 1／7 |
| criterion_issue／knowledge_gap／needs_human | 0／12／58 |
| 漏报类型／补查计划项 | 3／24 |
| Top 50 核对 | 50／50 |
| 门禁 | FAIL（valid=false） |

1. **先修保护钳位枚举**：22 颗模拟保护齐纳隔着 PTC/160Ω 被错当内部参考，双通道 D28 又因三网络漏掉。对应 3 类漏报中的 2 类；应先合并 `PRO-E02` 识别修正和覆盖种子。另 20 颗数字钳位用途未定，不能一律套此归因。
2. **D28 四身份冲突可直接整改**：符号 NUP2105L、Value PESD5V0L2BT、资料 AQ05-02HTG、采购 MMBZ6V8AL 不一致。只确认数据缺陷，未断言实装器件或所有分支均电气失败。
3. **不把条件问题硬判缺陷**：输入 PTC 保持 10mA／PWM PTC 保持 1.5A，不能以动作值证明持续 20mA／2.2A；DAC 的 100nF 对 buffer-on 50pF 超限，但 buffer-off 是独立分支。工况与模式仍需确认。

用法坑：必须显式填按图装配 `population` 再谈覆盖；本次补齐后原生 8 MOS+3 BJT 的驱动/SOA 项已出现，故未算漏报。strict 缺 U3/U5 六个输出名，回退不消除限制。无独立装配 BOM，XML 字段已读。门禁仍有五类评估开放项与 schema15 的承载冲突，以及未满足的条款/数值结构要求，均保留；报告为原样渲染快照，未打包/冻结。完整工作记录：`/Users/skyfend/.cache/sr-boards/danielmartensson--stm32-plc/review`。

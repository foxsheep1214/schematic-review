# lane-4 · DRV8825 步进电机驱动板

固定源21ce6419…，V1.1.1，TAPR-OHL-1.0；24件、KiCad 10.0.7 strict导出。类型POWER_CONVERTER / POWER_PROTECTION（后者待定），用途由README推断；industrial_telecom基线。

| 项目 | 数量/状态 |
|---|---:|
| 计划/已判 | 95/95（基线91+补查4） |
| PASS / NA / 未闭 / FAIL | 20 / 11 / 64 / 0 |
| 观察总数 | 75 |
| true_defect / false_alarm | 0 / 11 |
| criterion_issue / knowledge_gap / needs_human | 0 / 1 / 63 |
| 覆盖漏项 | 4（Top50三项+扩展一项） |
| 校验 / 放行 | valid=true / NO_GO；run.gate=FAIL |

1. **合并步优先：建立motor_driver的真实功能对象。** 目前固定电压输出模板把输入C1当变换器对象；UVLO、桥输出默认态和VMM旁路保护未展开。已补PWR-C06、RST-T04、PRO-C04，另补外部DIR/STEP的SIG-C07；先加覆盖种子，再修对象/接口展开。
2. **以准确物理脚语义排除误报。** DECAY合法开路为mixed，V3P3OUT是输出，MODE不是BOOT，VCP的1MΩ回VM为原厂泄放；安装孔和FD1不该产生电气应力/调试对象。11条误报均有建议位置、依据；本轮不改检查器。
3. **定量风险不等于已证缺陷。** Rs=0.2Ω±2%、0.1W，对应≤70°C RMS约≤0.700A；满端设定可超过3A，但缺真实相电流/模式。R7高压功耗只是条件上界，不能拿芯片45V当本板额定。0个确认缺陷也不代表可放行。

用法坑：schema15功能台账的未闭项不能伪装厂家数据；同版分号BOM须先保真规范化。普通C6采购约束与实际MPN身份分开。64个REVIEW_INCOMPLETE使renderer退出2，故《审查报告》明确是执行记录，不冒充原生正式报告；17条质量模式提示另有人工处置。75观察含64未闭项、10个计划内误候选及1个拒绝候选，非75个坏板点。第三方原件只在缓存/临时目录。

# cellkeeper-bms--cellkeeper-hardware · lane-4

推断用途：双RP2354B电池包BMS；CAN / RS485(isoSPI) / ISOLATION / ANALOG，含电源、USB和接触器。industrial_telecom；GPL-3.0；固定提交2f5c80b6，494器件/430网络，KiCad10.0.7 strict成功。

|指标|结果|
|---|---:|
|计划 / 有明确结果 / 未闭|1103 / 301（含11覆盖项） / 802|
|原生PASS / NA / FAIL|209 / 90 / 2|
|归因发现|357（包含待核候选/开放根因，不是357个电路故障）|
|true_defect / false_alarm / criterion_issue|1 / 50 / 0|
|knowledge_gap / needs_human|15 / 291|
|漏报|3个检查对象覆盖缺口|
|门禁 / 正式报告|FAIL、NO_GO / renderer退出2拒绝|

1. **确定偏离与未证明分开**：四只USB串阻22Ω违反准确RP2354B每脚27Ω要求，1根因/2项FAIL；主5V设定与非稳压隔离5V对ISO1050的4.75–5.25V窗尚无全包络保证，保留待确认，不写必然失效。
2. **合并步先修PH/ENA脚义与内部UVLO展开**：PH→L3的真实电源被报无驱动，ENA允许悬空却报来源未知；U3更被PWR-C06排除（M03）。另M01漏CAN/isoSPI隔离边界，M02漏J9外供电支路，均给改法/条件种子，不断言实板缺保护。
3. **不能用器件名替代功能**：C62并联差分滤波被认AC耦合，AM26LV32E被首页TVS字样误定类，机械/非标准测试点被误报。系统示意/均衡示例混入494器件；R6 nΩ可精确换算，不是未知值。

SR用法坑：CAN/RS485候选states=[]与lint矛盾；本轮分析run不是产品状态合同。原生schema15、na/decides要逐状态；多地去耦须return_net加group citation。802项保留REVIEW_INCOMPLETE，223条证据/格式错误、277条质量提示均保留，未造厂家缺数过门禁。完整证据与计数见[执行记录](审查报告.md)和[逐条归因](逐条归因.md)。

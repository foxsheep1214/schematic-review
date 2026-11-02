# lane-4 · 市电隔离反激电源审查回合

板：`hirusha785--12v-5a-isolated-flyback-smps-kicad`；来源固定 `7c828241`，MIT，37件/1页，严格导出通过。用途推断220Vac→12V/5A/60W；基线工业通信，补ANALOG、POWER_PROTECTION。

|项目|数量|
|---|---:|
|计划（122原项＋9补查）|131|
|有结果记录 / 已终判 / 未终判|131 / 51 / 80|
|PASS / NA / FAIL|28 / 17 / 6|
|归因观察（非lint命中，非电气缺陷数）|30|
|true_defect / false_alarm|4 / 16|
|criterion_issue / knowledge_gap / needs_human|0 / 1 / 9|
|漏报（计划覆盖缺口）|9|
|Top50逐条对照|50/50|
|门禁 / 正式渲染|FAIL / 退出2|

最重要的三条观察：

1. **先合并修集成离线开关的物理脚角色。** TOP227 DRAIN/CONTROL未满足SW/FB前提，漏时序、反馈补偿、UVLO、反馈断开、RCD和启动充电；按已核官方脚和光耦实际路径补对象，配覆盖种子，不按MPN白名单给PASS。
2. **电源焊盘须有真实端口角色。** H1–H4被当DEBUG，随后漏入口浪涌、外供支路及异常反供。DIN0207误作工业DI、AC/DC正负误作差分、模拟光耦误作数字链同样可复现；全NA误框架又触发F1两条错误。
3. **四个确定问题不能被零lint掩盖。** U3/R8阳极返回未接输出负端；5A串联L2仅3A；D1 KBL料号配KBPC1封装；替换Value后手册字段未同步。TI/onsemi TL431的1/3脚不同，不能将数据冲突说成全部实物分支均接反。

用法坑：optocouplers为schema2、results运行时15；官方光耦针表已核仍未进入optocoupler匿名脚识别。CONTROL的47uF隔68Ω，直接容量是0但不能自动判缺去耦。资料/工况未定没有伪造VENDOR_DATUM；80项保留REVIEW_INCOMPLETE，原生renderer拒绝，`审查报告.md`明确为执行记录。2条F1与64条质量提示均保留，不声称正式封包或电气审完。源码/手册仅在缓存，仓库只留自主归因；无核心文件改动、无commit/push。

# moelashmawi--flyback-ac-dc-converter · lane-2

用途推断：230Vac/50Hz→12Vdc隔离反激；类型 AC_MAINS、ISOLATION、POWER_CONVERTER，补入 POWER_PROTECTION。源 `e49dd6d442a6` / MIT，SR `faffed6cf3ea`，KiCad 10.0.7 strict；34器件、24网、86物理节点。README仅作用途线索，未采用其设计正确性/计算结论；无独立装配BOM。

| 计划项 | 已判 | 发现归因 | true_defect | false_alarm | criterion_issue | knowledge_gap | needs_human | 漏报 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 152 | 152 | 36 | 6 | 14 | 0 | 2 | 14 | 1 |

23 PASS、25 FAIL、84 INSUFFICIENT、20 NA；36项=6缺陷根因（4处功能连接、2处设计标注/身份）+15未决待办+14不适用计划提示+1格式阻断；漏报M01单列。Top50全部50条逐条留在findings.json的top50_audit。**门禁 FAIL / valid=false，198条错误，报告不可用于定稿，未打包。** 失败包括needs_human终态不兼容、资料/去耦声明及功能条款、部分失败项与待办结构，不能全部归为格式冲突。

1. **确定连接错误不能被资料不足淹没。** U1.4 VDD与SOURCE同GND1，0V低于最低启动门限13V；C10另一端开路；两张12V反馈网无源；U2.1 K/U2.3 A短接。PWR_FLAG不供电；TL431DBZ脚图正确，错在外线。C11缺容量/封装与D15 KBP206/W01G/WOG资料串用也分别登记。
2. **合并步先修已核脚表到连接图的数据流。** intent.devices已有EL817共同A/K/E/C脚表，但光耦清单两输出网为null，U3.3→U1.3 FB漏生成PRO-C01.FEEDBACK-OPEN。M01按G03-038核对输出16V电容的故障包络，只报漏问，不假定实际过压；附覆盖种子。14条误报主要是模拟光耦套数字隔离/逻辑链、市电链套VIH/VIL、被动保护套eFuse/双源/直流防反。
3. **磁件与安规不猜。** T1图示10–9及6–7各自同网，但EE25缺绕组脚图，不当成实物必短；C3的1kV不等于Y类，C1的275VAC不等于X类；F1 0.5A与FL1 0.3A不能单凭大小比较就判实际过载。均列具体取得/重判条件。

SR用法坑：R3 `100K-1W`解析失败，图面100kΩ/1W单独核而不改db。修改devices后须重跑候选冷扫再merge，旧去耦摘要不能直接合并。ST官网页可读而本地PDF超时/403；Mouser的1页Access Denied PDF已排除，TL431完整85页、EL817-G完整12页取得，后者只支持共同脚图。schema15不能忠实记录本任务needs_human，保留失败，不编需求答复。完整台账/原厂资料及图在 `/Users/skyfend/.cache/sr-boards/moelashmawi--flyback-ac-dc-converter/review`；仓库仅复制工具生成的Markdown，record相对图片/台账链接未打包，应在缓存报告中查看；不复制第三方电路，不改检查器/准则/种子库，不提交。

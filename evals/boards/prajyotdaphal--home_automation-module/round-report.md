# home_automation-module · lane-2 本轮审查

来源 `PrajyotDaphal/Home_Automation-Module@52018c0`，GPL-3.0；KiCad 10.0.7 严格导出成功。用途由固定README及单页原图**推断**：230VAC八路光耦/继电器控制及风扇调速。基线 industrial_telecom；原图95器件；同版BOM 91电气件已读入，4机械孔未列，供货型号全空。

| 指标 | 数量/状态 |
|---|---:|
| 最终计划 / 已逐项登记 | 476 / 476 |
| PASS / FAIL / NA / 未决检查 | 89 / 39 / 55 / 293 |
| 报告归因根因 | 30 |
| true_defect / false_alarm / criterion_issue | 4 / 8 / 0 |
| knowledge_gap / needs_human | 7 / 11 |
| Top50核对 / 漏项 | 50 / 3 |
| 门禁 / 发布结论 | FAIL / NO_GO |

1. **先修结构性错误。** PS1.3负输出接/VCC、.4正输出接GND；F2两端=/AC而失去断流作用；交流负载公共回路与控制GND共网；PC817输入返回和输出NPN也共地，所称完整隔离不成立。4个根因各有网表证据、原厂脚图/条款与合成种子建议。**合并步首做F2旁路检查及D-FUSE-BYPASS种子**，不依赖未知现场电流即可识别这一确定拓扑错误。
2. **0条lint不代表没有缺陷。** 8种噪声涉及零脚孔→DEBUG、继电器/光电晶体管→数字CMTI、交流干接点→逻辑接口、PS1跨隔离返回混池、薄膜/径向电容→MLCC、DIN0309封装→工业DI、额定功率尾缀阻值拒读。均写明正确适用条件；R27/R29的`2.2u/1/2W`仍保留歧义。
3. **3个漏项均是覆盖问题。** 封装ACDC启动、交流触点输出支路源侧保护、PS1本身隔离角色；没有把缺资料或已问的默认态/保持重复记为电气漏报。PC817回路实为330Ω+1kΩ，3.3V时IF上界2.481mA低于保证CTR测试5mA，不能照搬50%CTR判通过。

用法坑：`features`在候选流程不能写APPLICABLE，要用有出处的add；取板稀疏检出漏BOM，须先查完整git树；分号CSV及Designation列规范化后read_bom；91件逐值核图一致。`input_sha256`取board_intent.input_fingerprint，状态边须带state。当前schema15不能完整收下needs_human/知识终态，另有供应商定界及纯拓扑证据字段未满足校验，共564条记录错误，原样保留FAIL，未打包。30是4个缺陷+8个关闭噪声+18个未决根因，非30个硬件故障。

完整台账、源锁、原厂资料、50条核对及门禁原文：[外部审查目录](/Users/skyfend/.cache/sr-boards/prajyotdaphal--home_automation-module/review)；根因和改进材料：[findings.json](findings.json)。复制的[审查报告](审查报告.md)保留记录无效警示；其中record相对链接是打包入口，因门禁未过未生成record，不视作有效交付包。第三方电路未复制进本仓库。

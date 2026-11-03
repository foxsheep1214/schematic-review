# CONNECT programmer / lane-2 本轮归因

固定源`f3d34ebe`，TAPR-OHL-1.0；KiCad10.0.7 strict成功，25器件/28网。同版V1.1.1 BOM读入25/25，PDF及3份厂家资料锁hash。用途为README推断的ESP USB串口下载器；industrial_telecom基线，USB/DEBUG/UART，补LDO/EN链。

| 指标 | 结果 |
|---|---:|
| 计划 / 已记录 | 162 / 162 |
| PASS / NA / FAIL / 未决检查 | 49 / 23 / 1 / 89 |
| 归因总数 | 75 |
| true_defect / false_alarm / criterion_issue | 1 / 25 / 0 |
| knowledge_gap / needs_human | 23 / 26 |
| Top50核对 / 漏报 | 50 / 3 |
| 原生报告项 / 关闭候选与不适用项 | 50 / 25 |
| 门禁 / 记录错误 | FAIL / 242 |

**三条观察**
1. K1/K2无源连接器生成8项IC去耦问题；U2 EN=VIN生成6项strap/复位/默认态问题。先修对象资格，入口电容和载流仍独立审。
2. 合并步先修**F1保护链生成**：USB收走F1后漏PRO-C01分断能力、PRO-C05时间协调；外接UART另漏SIG-C08。3项均是结构化漏问，未证实原板电气违规，M01–M03已附修改/变异材料。
3. 唯一true_defect是两个`#PWR?`的P3编号问题，电气硬故障0。DRV-A03原提示已问Q1/Q2启动/高阻态；缺目标上拉/RC应未决，不能重复算RST-T04漏报。

**用法坑**：分号BOM先转换并存原始hash；`find_parts.py`在ASG目录；input_sha256取decoupling清单。原生schema15不接受任务授权的needs_human：178条gap_cause+49条kind拒收；另12条缺条款、3条输入/去耦绑定限制，共242。64条质量候选保留（主要重复与跨范围复用），未宣称筛查完成或有效打包。75条归因含重复任务，不能当75个硬件故障。

证据/逐项账/Top50及原生JSON在该板缓存`review/`；报告内record索引须结合该缓存，本轮不产有效交付包。第三方文件未入SR仓库，2项PCB/生产移交；未改规则、未提交。

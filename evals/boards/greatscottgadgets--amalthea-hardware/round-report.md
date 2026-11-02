# Amalthea · lane-1 本轮记录

来源 `greatscottgadgets/amalthea-hardware@b1027cf`，CERN-OHL-P-2.0；KiCad **10.0.7 strict成功**，41器件/1页（10 DNP）。依据README与U1/两SMA推断为**双频实验SDR夹层**，实际RF/CLOCK/HSSERIAL/SPI。catalog三标签与本版实图不符；未修改目录或工具。

|指标|数量|
|---|---:|
|最终计划项 / 功能框架|162 / 10|
|局部已判（PASS / NA）|51（35 / 16）|
|逐项 needs_human|111|
|归因发现（按根因，含5条lint提示）|18|
|true_defect / false_alarm / criterion_issue|0 / 9 / 0|
|knowledge_gap / needs_human（根因）|5 / 4|
|Top50漏问 / 已证硬件漏检|3 / 0|
|原生校验 / release|FAIL（130错误） / NO_GO|

最重要的三条观察：
1. **先补外部信号口的掉电注入问题（M01）**：J1→U1的SPI/RSTN直接连接、IQ经47Ω，最终无SIG-C08；跨域识别只看已知两端供电会漏掉外部未知端点。先加此类计划/种子资格，再谈具体硬件违例。
2. **必须按功能对象分辨名称**：安装孔被当输入、RF Balun被当续流线圈、RF P/N被当数字差分、TCXO被套无源晶体/RTC；9条误报均给明确反证与修改位置。T1“connector”还来自手册评估板附件文字。
3. **片内电源与启动也要问**：C4/C5/C6各1µF，名义在0.1–10µF窗口内；M02补内部稳压输出稳定性/ESR适用性，M03补主机高阻期默认态。两者均非已证硬件缺陷；准确TCXO资料/对端模式/源工况仍未定。

用法坑：`input_sha256`取decoupling库存指纹，不能用db文件哈希；`add`要显式states且生成电路丢失nets/anchors。精确PART可能被VALUE覆盖（BALUN09/D_TVS），用resolution绑定同型号资料。schema15没有needs_human或待定需求类，保留逐项pending及逐功能范围，**没有编造VENDOR_DATUM/功能PASS**；因此50余项局部结论不能代替整板覆盖。生成报告顶部明确记录无效；其“资料不足0”只统计原生结果，真实待判111见台账，勿当完成。

[归因/修改材料](findings.json) · [Top50逐条核对](top50-checklist.md) · [原生生成报告](审查报告.md) · [逐项依据](record/engineering-review.md)。报告所链`record/db.json`明确为缓存指针；未复制第三方网表/图面/手册，未运行成功打包、未提交。

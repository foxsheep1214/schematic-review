# lane-2：MCP23017 GPIO扩展板

固定来源：`1d614e5f49013931a2c1fd8460bf48e1b3790c36`，`CAD/V1.2.1`，TAPR-OHL-1.0；KiCad 10.0.7 strict导出，30器件/43网络。用途为README/文件名**推断**：I²C GPIO扩展＋双NMOS电平转换＋3.3V LDO；基线industrial_telecom。catalog的POWER_PROTECTION不等于实际存在独立保护级。

| 计划/逐项记录 | 发现归因 | true_defect | false_alarm | criterion_issue | knowledge_gap | needs_human | 漏报 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 181/181 | 38 | 1 | 7 | 0 | 3 | 27 | 1 |

计数按报告项而非根因：1条原生缺陷＋29项未决＋4条工具反馈＋3条非电气类别提示＋1条流程说明；同根因在不同功能重复保留。原生逐项为PASS51/NA9/FAIL3/INS118；3个FAIL共用D01。冷/热扫自动确认缺陷均0。38条归因覆盖所有发现/待办/反馈，M01另计。

**最重要的3条观察**
1. **先修easyC端口识别。** K1/K3被K前缀识别成relay，衍生6项无关检查；同时漏掉两个EXT电源口的G05-054/PRO-D04询问（M01）。合并步优先补同网多端口回归，不把无板载防反直接判坏。
2. **确认的是公开设计定义缺陷。** U2仅NMOS-DUAL、U3仅SE5218，同版无BOM；SE5218 p2有七档，3.3V为A。D01/seed只针对可制造定义不唯一，不指控实装损坏。10k上拉需Cb≤118pF@100k/35.4pF@400k的条件窗口；未知Cb/速率不能当错阻值。
3. **未确认准则本身不可判（0条）。** 50例均有逐条适用性记录。C3/C4有效容量、地址焊接档、外部负载/故障边界必须有真实输入；不能将这些问题、未规定的反灌工作区或后续试验混成厂家缺参。MCP新手册GPA7/GPB7仅输出限制保留用途确认。

**SR用法与门禁**：**FAIL，valid=false，release=NO_GO**。原生schema15不接受任务要求的needs_human终态；本轮显式NEEDS_HUMAN扩展使29个开放项产生265条格式错误（118×2＋29），故没有形成有效原生SR台账/准出包，报告首行已标无效。不能把265当板上265个故障，也不能伪造厂家数据或需求答复消除它。保留记录质量提示48条，未冒充已关闭。

先填写自定义0603C的`decoupling.components`和已查手册条款再重扫；这属于输入补全，不是检查器误报。U2错误候选拒绝后仍held，合法add会被挡，须保留未归属复核；不乱选归属来过门禁。实际脚本schema15与格式文档标题14有差异；D版手册针图在p11，不能沿用C版页码。未改共用代码/准则、未写Wiki、未提交。工作文件在`~/.cache/sr-boards/solderedelectronics--io-expander-mcp23017-breakout-hardware-design/review/`，未打包，报告`record/...`索引应在该缓存读。详见[逐条归因](findings.json)、[Top50](top50-audit.md)、[独立证据](evidence.md)。

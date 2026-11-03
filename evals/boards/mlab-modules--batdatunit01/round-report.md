# BATDATUNIT01 · lane-3 本轮记录

固定源 `mlab-modules/BATDATUNIT01@28e6b25f1db0ad54fe10bc592267599cd20bc116`，GPL-3.0；KiCad 10.0.7。用途**推断**为并联锂电充电/测量、SD记录及USB数据模块；基线 industrial_telecom。

| 指标 | 数量/状态 |
|---|---:|
| 计划项 / 已记逐项处置 | 1060 / 1060 |
| 独立发现/待判事项 | 78 |
| true_defect / false_alarm | 5 / 6 |
| criterion_issue / knowledge_gap / needs_human | 0 / 4 / 63 |
| 漏报（规则覆盖缺口） | 3 |
| PASS / FAIL / NA / 待判检查 | 72 / 9 / 29 / 950 |
| 原生门禁 / release | FAIL / NO_GO |

1. **确认问题5项**：U1.CLDO的C2=100n而原厂要求1u；U13.VBUS仅C5=1n，厂家最小1u，PMID的10u不能跨内部开关借用；R73/R74 DNP使U16/U17 EN在MCU复位高阻时无偏置；U14身份/封装不一致；BOM遗漏原生已贴R71。前3项P1，后2项P2，未声称实物已失效。
2. **6个误报根因覆盖26检查**：控制网被当供电/I2C，ADDR子串触发DDR，共轨LED把电源/strap误当LED驱动点，CLK输出被符号标input。U6.nRESET内置上拉、U9双CSB内部连接属于有效候选经原厂消解，未计误报。
3. **合并优先补ON默认态**：U18.ON应有RST-T04，保留PC3的JTAG上拉/普通GPIO分支并加种子；另补充电器U13.TS的ANA-C03与多脚ESD阵列U2的PRO-E02。3条都是具体覆盖缺口，不能称3个已证板缺陷。

用法坑：两份“nogroup”/普通BOM实际都拼接位号，73行经数量校验后无损拆分，覆盖201件；不能把未在BOM的所有器件都当DNP。U2的Wiki同名PDF实为SC6Y，未冒充SC6保证。strict仅缺U18.9名称，原厂核为接地EP，仍保留原输入FAIL记录。I2C顶层轨声明须同时写进schema2清单rails，否则重建169条过期错误；已用合法声明绕开。原生schema15不承载人判/知识缺口及未定严重度，另有纯拓扑条款、条件预判等记录约束，门禁4030条错误如实留存，不是4030个电气缺陷，不强填VENDOR_DATUM。

审查报告由脚本渲染后原样复制；完整图证、HTML、逐项台账、50条对照、输入哈希与门禁保存在 [`review/`](/Users/skyfend/.cache/sr-boards/mlab-modules--batdatunit01/review/审查报告.html)。本轮是评估记录，未形成格式有效的整板准出报告。

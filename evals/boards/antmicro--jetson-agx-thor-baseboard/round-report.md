# AGX Thor 载板审查回合（lane-1）

结论：**FAIL / NO_GO；完整 SR 受阻**。用途由源 README 推断为 Jetson AGX Thor T5000 高速计算载板；catalog 类型 HSSERIAL / ETHERNET / USB / POWER_CONVERTER，补核供电保护、启动、电平转换与控制总线；基线 industrial_telecom。来源 `d966e9ca4049ae58b77bbc25bd75b074588b6484`，Apache-2.0；1170 器件、1366 网络、15 页，KiCad 10.0.7 导出。

| 指标 | 本轮 |
|---|---:|
| 合并诊断计划（并非完整候选计划） | 2714 |
| 原生已判 / needs_human 待判 | 124 / 2590 |
| 原生已判构成 PASS / FAIL / NA | 120 / 1 / 3 |
| 自动发现去重总数 | 167 |
| true_defect / false_alarm | 1 / 61 |
| criterion_issue / knowledge_gap / needs_human | 0 / 79 / 26 |
| 已确认漏报 / Top50未决 / 不适用 / 已报真缺陷 | 0 / 31 / 18 / 1 |

最重要的三条观察：

1. **D54 为真实 P2 工作范围不匹配**：R288=47k 将 PWR_BTN 拉至 +5V_AON；U75 经 L8/R366 供电，R312/R313 设定约 4.992V，超过 TPD1E0B04 手册 p4/p5 的 ±3.6V 推荐/VRWM。已有 PRO-E02 候选，故不是漏报。提供工作窗变异种子和有前置条件的改料约束，不宣称已损坏。
2. **供电值解析会放大误报**：`R_0R001_0805` 等封装化 Value 未解析，真实源跨毫欧电阻后丢失，造成六条 PWR-A01 与34条已贴器件 PWR-A02误报。SiC437 pin18 是 VOUT sense，真实源为 SW→电感→采样电阻；不能靠改脚类型“修复”。另有开漏并联、多页相似网名、FMC+矩阵脚误识别等逐项反证，61条均有 proposed_fix。
3. **合并步优先修电路状态契约**：67候选、89决定写出49电路，但13电路 states=[] 被 lint 拒绝（含 I2C/SPI/UART/HSSERIAL/LEVEL_SHIFT）；应补齐 catalog.CANDIDATE_STATES 并回归“决定→写出→重扫”，不能虚构产品运行态或删真实电路过关。Top50没有确认新增漏报；D2虽是阻断前单向TVS，反接合同尚不明，按G05-054/057留未决。

SR 用法坑：strict 因19个TPD4ESD功能脚缺名失败，只能 --no-strict 留 db；没有装配BOM或受控产品需求。原生 schema15 无 needs_human 枚举，2590行以 review-results.json 的 pending_checks 扩展逐条保留；原生门禁因覆盖、输入完整性及未关闭功能保持 FAIL，绝不是完成2714项审查。无 circuits 的回退计划与带候选失败日志均保留；检查器的 READY 不是审结。MAX16013 p5明确允许EN接VCC、有源振荡器不是无源晶体、CAN DIN/DOUT不是CANH/CANL，套规则前先核实际对象。

交付：[逐条归因](findings.json)、[Top50核对](top50-audit.md)、[原生报告](审查报告.md)、[运行证据索引](pipeline-attempts.json)。完整工作底稿位于 `~/.cache/sr-boards/antmicro--jetson-agx-thor-baseboard/review/`；第三方源/PDF仅留缓存或指定临时目录。未改检查器/准则，未写HardwareWiki，未提交。

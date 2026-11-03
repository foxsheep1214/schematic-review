# lane-3：gorkemguven--12v-1a-isolated-flyback-smps

MIT，固定源提交 `36a78f3d4086a58e2786bb3a77145fbbc47d9f21`；49件strict成功。用途推断为85–265 Vac→12 V/1 A隔离反激，基线industrial_telecom；另补ANALOG/POWER_PROTECTION。

| 指标 | 数量 |
|---|---:|
| 最终计划（原生＋补项） | 198（196＋2） |
| 归因发现 | 24 |
| true_defect / false_alarm | 2 / 9 |
| criterion_issue / knowledge_gap / needs_human | 0 / 2 / 11 |
| 漏报 | 1类隔离对象覆盖 |
| PASS / NA / FAIL / 待判 | 29 / 28 / 5 / 136 |
| 原生门禁 / 报告生成 | FAIL（14错误）、NO_GO / 退出2拒绝 |

1. **先合并对象/针表修复。** U1三绕组磁件被当IC全脚互通，导致假隔离地合并及pinmux；Q2已核G/D/S也未入共享图，Z2正常限幅被套阈值不导通模型。修模型后保留真实跨域短接阳性种子，别统一静默。
2. **确实的2个根因。** R36=3.3kΩ违反TI p4 RT≥5kΩ；R26=2.63k/料号2k、C12=1nF/料号100nF且0805/1206、IC7厂牌/资料、C12/C13漏BOM存在交付数据矛盾。5个FAIL不是5个独立故障。
3. **保留有数值的边界。** R33跨主母线，320V条件下2.179W>2W且超300V；D15直接跨主绕组、300k启动链低线仅0.342mA。真实母线/磁件未定，均留needs_human。Top50逐50条为32无对象、16已有待判、1局部已核、1覆盖漏报；Z2已有合法PRO-C02分支，不另算PRO-E02漏报。

**用法坑：** 普通阻值后加空格功率被拒读；补器件类别后要先重审计，再冷扫/合并，避免库存摘要变化。COMP有内部电流源，PRO-A04正确候选关闭不算误报。schema15用REVIEW_INCOMPLETE保留未判，不虚构VENDOR_DATUM；原生渲染器因此拒绝报告，`审查报告.md`明确只是评估快照。14个事实条款/失败承载格式错误原样保留，未打包准出。

全部逐项、归因和Top50在[findings.json](findings.json)；完整[审查缓存](/Users/skyfend/.cache/sr-boards/gorkemguven--12v-1a-isolated-flyback-smps/review)。只读HardwareWiki；未改共用代码/准则/种子库，未commit/push。

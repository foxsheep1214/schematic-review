# CH340C USB-UART — lane-3 本轮评估

来源：`SolderedElectronics/USB-UART-CH340C-converter-board-hardware-design@c50925abc7d2`，`CAD/V1.1.1/USB-UART_converter.kicad_sch`，TAPR-OHL-1.0。用途由README/图面**推断**；产品基线 `industrial_telecom` 由本轮任务指定，不表示原板承诺工业环境。

| 项目 | 数量 |
|---|---:|
| 计划项（原生 + 补项） | 175（173 + 2） |
| PASS / NA / FAIL / 待判 | 53 / 20 / 2 / 100 |
| 发现归因（根因/模式） | 21 |
| true_defect / false_alarm / criterion_issue | 1 / 5 / 0 |
| knowledge_gap / needs_human | 4 / 11 |
| 漏报（目标规则覆盖缺口） | 2（均已补进计划） |
| 门禁 / 严格解析 | FAIL（236项记录错误）/ 回退no-strict |

1. **已确认接法错误只有1个根因**：S1选3V3后U1.16降至3V3，U1.4仍仅接C2；CH340 3C p3/5要求V3/VCC同接3V3。2个FAIL不是2个缺陷。5V档VOH测试点≥4.4V也反证README“UART总为3V3”，但对端未指定，不能据此声称已损坏外设。
2. **最先合并的通用改进**：登记USB-UART桥角色并为UART外露端点生成`SIG-C08`及`RST-T04`，覆盖掉电注入、枚举前配置和复位弱驱动；先加对照种子。Top50全部50条逐项记录于`findings.json.top50_audit`，同一M01对应三条准则不重复算漏报。
3. **误报与证据边界**：连接器被生成IC去耦组；同一USB源的K3/K4引出被当双源；两脚LED空差集仍被手册类型卡住。SE5218有效Cout至少1µF、F1动作/分断身份、外端先供电和批号分别留依赖，不因缺资料硬判器件坏或准则有错。

用法坑：KiCad 10.0.7严格解析仅报S1三脚无名；BOM分号无损转CSV后用`read_bom.py`，图纸/BOM均取同一commit的V1.1.1。候选F1被三电路持有会拒绝，EN=VIN按原厂参考处置为非独立启动电路，U1启动检查另补。schema15不承载评估所需的`needs_human`/知识缺口，纯拓扑条款和部分局部C类结构也未过门禁；没有改规则、改判据或造厂家数据凑PASS。报告为原样生成的无效门禁评估快照，未打包/不可准出；原生台账及图在[缓存审查目录](/Users/skyfend/.cache/sr-boards/solderedelectronics--usb-uart-ch340c-converter-board-hardware-design/review)，第三方电路文件只留缓存。

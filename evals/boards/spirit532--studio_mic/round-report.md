# spirit532--studio_mic · lane-1

用途**推断**：正向幻象供电的电容话筒前端，OPA1652缓冲/平衡输出、HEF40106BT六级二极管倍压；类型ANALOG/AV/POWER_CONVERTER，基线industrial_telecom。MIT；源锁`8ffc29b48432c2658af3b84805d227cce29ce538`，SR `5e7f42c6748982359326fb9f4351b5bb34848ac3`。

| 项目 | 数量/结果 |
|---|---:|
| 器件 / 网络 / 页 / 电路 / 框架 | 58 / 38 / 1 / 3 / 11 |
| 最终计划 | 154（152自动 + 2人工gap） |
| 局部已判 / 逐ID needs_human | 40 / 114 |
| 归因发现合计 | 25（5个扫描疑点及后续根因归并；不是电气缺陷总数） |
| true_defect / false_alarm | 1 / 14 |
| criterion_issue / knowledge_gap / needs_human | 0 / 1 / 9 |
| Top50漏问 / 已证硬件漏检 | 2 / 0 |
| 原生门禁 / 准出 | FAIL / NO_GO（valid=false；报告仅诊断） |

最重要的三条观察：
1. **先修有阻供电追源**：J1两线各经47Ω+2.2kΩ供D1，R5=200Ω再供U1；四条“无驱动”均不能成立。不要为了消警把电阻短接或拿网名电压作保证。源侧PRO-C04也漏问（M01）。
2. **虚地与储能状态必须分开**：GNDA是47k/47k中点，不是0V。两级100MΩ/100nF在忽略负载模型下慢时间常数52.36s；HT→R13→C19→U1.3掉电注入漏问（M02）。两漏问已通过intent.rule_gaps补入，未证明原板电气越界。
3. **已证问题是资料关联错误**：U2实际HEF40106BT，链接却是SN74HC14；两者借用针序兼容，不据此指控实物错装。BOM给五只电解47µF/63V；不能只看图面无耐压误报。泵C11–C16也不能都按12V应力。

用法上的坑：KiCad10.0.7成功导出，strict因14个无名功能脚失败；XML/db的131端点归网零差异，官方表补核脚义。源XLS范围位号先展开再read_bom（58件齐），Value列须另存对读；J1 Qty0注释为外壳自带，非电气DNP。`SpiritsKiCADLib`假SPI已声明NA；安装孔假DEBUG已拒绝。官方HEF资料只有在线文字、完整PDF403，审计把txt当PDF出NO_TEXT。schema15无needs_human/未定合同/部分功能格式，逐ID留在results.pending_checks、全部11框架保留未完成范围，未伪造VENDOR_DATUM或功能PASS；原生“资料不足0”不代表已审结。早期7组共用证明提示已在缓存逐组复核；补齐功能绑定后原生提示为0，仍未完成整板功能判定。

证据入口：[逐条归因](findings.json)、[Top50逐条核对](top50-audit.json)、[原生报告](审查报告.md)；完整台账、条件计算及手册在`/Users/skyfend/.cache/sr-boards/spirit532--studio_mic/review`。无有效打包；报告相对record索引不可作完整证据包使用，回缓存原始文件复核。未复制第三方电路进仓库、未改检查器/准则/HardwareWiki、未提交或推送。

# newell--hv-flyback-converter · lane-2

固定源 `c3d49c944baf41014a985d0d2453a905761e3e3e`；CERN-OHL-W-2.0；KiCad 10.0.7 strict 成功。32 器件 / 20 网 / 94 端点。用途**推断**为 LT3957A 4–6 V→180 V 非隔离高压反激；类型：POWER_CONVERTER / POWER_PROTECTION / ANALOG（反馈），补 ISOLATION（磁件）/ STARTUP。无独立 BOM。

| 计划 / 已逐项记判 | 归因记录 | true_defect | false_alarm | criterion_issue | knowledge_gap | needs_human | Top50 漏报 | 门禁 |
|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 169 / 169 | 36 | 2 | 14 | 0 | 2 | 18 | 0 | FAIL |

结果项：PASS 53 / FAIL 6 / INSUFFICIENT 82 / NA 28。6 个 FAIL 归并为 D1 同一根因 5 项及 D3 资料 1 项；36 是归因数，不是 36 处硬件故障。Top50 逐条记录在 findings.json.top50_audit；0 漏报只指最终计划覆盖，未定项不算通过。

1. **两处确认问题有边界**：D1 VRWM=5 V 不覆盖推断 6 V 持续上限（Nexperia p4）；D3 的 MMSZ5258B 链接却指 BZT52B 系列，只确认资料错配。183.88 V 是 R8/R9 标称计算，180 V 无容差，不指控输出必错；3 A 是 TR1 感量测试点，不当饱和绝限。
2. **14 组误判提示可复用**：安装孔被当 DEBUG；被动功率变压器被套默认态/码率/CMTI/协议规则；SS 恒流充电被当 strap/复位/逻辑链；没有实际 eFuse/保险/双源却生成相应机制问题。每组都有函数定位与修改建议，未改公共文件。
3. **合并步先补终态表达**：348 条剩余拒收均属 NEEDS_HUMAN/未定级不被 schema15 接受。20 件待决已按根因合并，没有伪造需求答复、厂家单调界或 P 级；当前报告保留记录无效提示，不支持定稿，未打包。

用法坑：SGND 与 GND 在 U1 内部相连且手册禁止外部短接；TR1 四初级必须并联，现 flyback 声明无法诚实容纳，按原厂图人工核。R7/R9 初扫多瓦粗估在补正常节点窗后消失，**未计误报**；有效 C7≥4.7 µF 不能用标称相等代替。源目录无装配 BOM，不从 LTSpice 借设计方结论。

[生成报告](审查报告.md) / [逐条归因](findings.json)。仓库报告是脚本输出原样副本；相对 record 图片/台账以[缓存完整审查](/Users/skyfend/.cache/sr-boards/newell--hv-flyback-converter/review/审查报告.md)为准，第三方文件均留缓存。准则原文未证实不可判，criterion_issue=0。

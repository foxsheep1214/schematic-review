# OreSat C3 · lane-1 本轮记录

`oresat/oresat-c3-hardware@738a430a2270f489b3ff0aad043578f60fcf075e`，CERN-OHL-S-2.0。**用途推断**：卫星OBC/遥测/命令控制卡。CAN、STORAGE、RF、POWER_CONVERTER；任务指定基线 `industrial_telecom`。KiCad 10.0.7，504器件、547网、11页。

| 项目 | 数量 / 结果 |
|---|---:|
| 原生候选 / 决定 / 推出电路 | 13 / 27 / 24 |
| 诊断计划 / 局部判定 / needs_human待核 | 954 / 48 / 906 |
| 非INFO扫描提示 / 全部归因 | 53 / 63 |
| true_defect / false_alarm / criterion_issue | 1 / 36 / 0 |
| knowledge_gap / needs_human（归因条目） | 5 / 21 |
| Top50核对 / 漏问 / 确证电气硬件漏检 | 50 / 1 / 0 |
| 原生门禁 / 准出 | **FAIL / NO_GO** |

1. **合并步先修CAN工作态契约。** CAN-U8/U39均由工具生成空states，决定脚本成功后lint反而FATAL。失败intent保留；954项是类型级诊断回退，**不是完整逐电路最终计划**。门禁101条记录/覆盖错误保留，未编造整功能结论。
2. **误报来自器件语义。** SiP内置输出/上拉、未用BAT接法、TCAN内部下拉、RF偏置/匹配电感、MAX941 SHDN接V+均有据。I²C多出5个LED/电源/控制伪段；普通缓冲器的ESD能力被误当TVS身份。36条误触发不是36处硬件错误。
3. **数据缺陷与漏问分开。** 1个采购一致性根因涉及U1（512M/1G、B/I档）及U9（64GB/16GB），不证明实物装错。M01漏问可关断radio域SPI失电注入，尚未证实电气违规；种子含必需状态/Ioff前提。Top50均有逐条记录，未证实准则本身有错。

**用法坑：** strict失败直接因21个功能脚无名，不是65.41%的全引脚名称比例；no-strict不代表输入完整。R31=`10 (1206)`读不出，未猜值。无同版冻结BOM/输入工况；普通阻容缺专属手册不直接定罪。schema15无needs_human，906项保存在pending_checks/plan-dispositions，覆盖门禁如实FAIL；2条筛查提示已处置。复制报告是脚本生成的无效记录草稿，未打包，默认record索引不构成交付包。

[逐项依据、Top50、原生台账及门禁所在缓存](/Users/skyfend/.cache/sr-boards/oresat--oresat-c3-hardware/review/engineering-review.md)。未改共用代码/准则，未提交、未推送。

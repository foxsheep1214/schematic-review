# rapidanalysis--xerxes · lane-1

CM4/CM5载板（用途推断），含USB、Ethernet、SD、M.2、PoE及扩展接口；Apache-2.0；源提交43abf573。KiCad 10.0.7，58件/209网/516节点；XML与db逐节点零差异，strict仅因U5.2/.4缺逻辑名回退。

| 项目 | 数量/结论 |
|---|---:|
| 电路 / 功能框架 | 12 / 34 |
| 计划项 | 600（原生初始575 + 分类恢复22 + 人工补问3） |
| 局部已判 / needs_human待核 | 83 / 517 |
| 归因发现（含候选、INFO与工具根因） | 60 |
| true_defect | 2 |
| false_alarm | 37 |
| criterion_issue | 1 |
| knowledge_gap | 3 |
| needs_human（归因根因数） | 17 |
| 漏报 | 4（1处候选遗漏已恢复，3处人工补问；非已证硬件漏检） |
| 门禁 | FAIL；valid=false / NO_GO；未打包 |

1. **合并步先修TVS多通道/局部返回识别。** U7/U8是四路TVS，D6跨PoE局部正负轨；原生0个PRO-E02、6个错误TRIP/NOTRIP项。M04给准确窗口证据与VRWM变异，修后须逐通道回归。
2. **两条真问题须分层描述。** C9=4700pF超AP3441 p9的10–470pF应用窗（未证实物振荡）；J8只有UART三针却标JTAG。G03-005只写LC/穿越频率公式，不能冒充Cff准则；R13接地例外尚拿不准，留人工。
3. **输入边界决定审查范围。** U4/J5/J4原生DNP；51-ref JLC配单是未确认匹配，不是批准BOM。I²C须计CM5内置1.8k与外置2.2k并联约990Ω；PoE准确型号、卡/外设负载和状态窗未锁，不判整板通过。

用法坑：泛化逻辑缓冲器角色、零脚Logo和“VIN-”会误导类型/去耦；NC feed-through不等于DNU。顶层power_rails还须显式写入schema2 i2c_topology.rails，才避免原生门禁重建不一致。schema15无原生needs_human/完整未定输入表达；**资料不足0不表示517项审完**。原生报告保留无效警示与全部错误，局部记录不能当有效审查包；台账和逐功能范围在缓存review/，findings.json列其绝对路径。Top50已逐条核50项，全部修改仅为建议/种子，未改公共脚本和准则。

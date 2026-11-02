# antmicro--scalenode-cm4-baseboard · lane-3

固定源 `77f5bf281d13e43154cac9645f7cc22a82e56971`，Apache-2.0；KiCad 10.0.7 strict成功，146器件/7页。由README推断为CM4机架计算载板：PoE PD、以太网、隔离电源，含NVMe、USB、SD和扩展接口。基线 `industrial_telecom`。

| 项目 | 数量 |
|---|---:|
| 最终计划（原生893 + 补审7） | 900 |
| 已审结 PASS / NA / FAIL | 155 / 128 / 2 |
| 仍待判计划项 | 615 |
| 逐条归因发现 | 154 |
| true_defect / false_alarm | 2 / 124 |
| criterion_issue / knowledge_gap / needs_human | 1 / 14 / 13 |
| Top50核对 / 原生目标覆盖漏项 | 50 / 6 |
| 门禁 / 准出 | FAIL / NO_GO |

发现条数含同根因不同对象/规则的误报症状和26件共享待判事项，**不等于154个板上缺陷**。6条漏项均已通过`rule_gaps`补查，含U7/L3隔离、D2/D3 ESD、BOOT默认态、U8内置MOS SOA；只有R34局部子项是已有分组检查的细化，不计漏报。真缺陷为R34功率额定与J8未用DSI网的标注。

1. **先合并修隔离侧别和等势图。** U7的输入GNDD/输出GND被短接推导，R33/LED有限支路又合并参考地；既造成误报，也抑制R34功耗预判。R34=15k/CR0603，48V耗散0.1536W>0.1W；建议按最大输入/环境选≥0.5W候选档后复核，未替用户改板。
2. **模块边界及多通道角色要先核。** M1是零电气脚外形，J7/J8才是CM4接口；未用输出/带内部偏置的脚、DNP测试焊盘不能报断线。D3三个ESD通道等效，D+/D−互换/ID留空合法；D2/D3仍须逐通道保护审查。U3/U4均DNP，无双模块并联缺陷。
3. **准则须绑定协议与状态。** G01-029把100µF泛用于USB Sink，原出处PD Table4.7的100µF只在成功协商后；J5是Micro-B，直接名义电容仅1.2µF。本板未证实过量，但准则的协议/附着状态前提需补。

用法坑：`datasheet-resolution`网络条目必须有`retrieved_at`；补资料/角色后重审计、重建候选与决定，不能用旧摘要。FT234XD官网403后取得RS镜像v1.1全文，PTC取得Littelfuse 2023全文；**不称最新版或把镜像链接存在当读取完成**。无独立BOM，仅使用原图实例MPN/容差。schema15不能表达本任务`needs_human/knowledge_gap`，另有纯拓扑条款与旁路声明格式限制；原生1306条格式错误如实保留，报告带无效警告。它是评估原样副本，非有效打包/准出；底稿：`/Users/skyfend/.cache/sr-boards/antmicro--scalenode-cm4-baseboard/review`。

# fossasia--pslab-hardware · lane-2

固定源 `fossasia/pslab-hardware@404aae216963ea0708e15bb84bde670a94ad3d83`，Apache-2.0；SR `b1fcac44422cc531cbd5c10981a3c16f5f1d21ff`，KiCad 10.0.7。用途**推断**：PIC24 便携测量/波形/可编程源仪器；ANALOG、USB、CLOCK、POWER_CONVERTER，补 I2C/SPI/LEVEL_SHIFT/DEBUG。`industrial_telecom` 仅评测基线。

| 计划项 | 逐项裁决 | 唯一归因项 | true_defect | false_alarm | criterion_issue | knowledge_gap | needs_human | 漏报 | 门禁 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
|914|914|75|5|11|1|2|56|3|FAIL / NO_GO|

归因项为5个已证**源数据/文档矛盾**、56个功能待确认任务、14条SR反馈；不是75个已证硬件故障。Top50逐条结果内嵌于 findings.json，27条非INFO扫描提示都有归因映射。原生报告按检查编号将其中两项归为“电路错误”，其证据只证明字段冲突，不能解释为已证实物电气失效。

1. **合并步首修分数功率解析**：`1/16W` 被 `bom_ratings` 按斜线拆成16W，27只电阻的额定预判放大256倍；R54/R55的粗界1.769W也获PASS。实际耗散未证，不能据粗界反控原板过载。派生模型还丢掉已填的 `proposal_override`，须一并加端到端回归。
2. **按真实作用认电路**：Q2/Q3射极供出±6V、U17反相供出−9V；L3是boost储能，D1/D2是持续齐纳基准。误报之外，U16三通道ESD未展开PRO-E02；U6/U21启动电流与PVS/PCS复位默认态是另两条计划覆盖漏项，尚非已证故障。
3. **保留身份分支**：C5/C23的10nF与104采购码100nF、R22的12k与103码10k、F1的1A与250mA保持冲突；PGA资料错链降压器、MMBT3906额定描述写大。没有选择某分支假装实贴，也未套通用ABS07表认定ABS07-166的CL。

用法坑：175件同提交BOM仅把表头References改为Reference后读入；原始198件含标识/安装/测试点。strict因24个功能脚缺名回退，连通关系与官方脚义分开核。I2C上下文漏顶层轨，用schema2显式rails同值重扫可复现消除过期错误。最终3321条门禁错误为NEEDS_HUMAN/未定级契约及61条预判改判记录限制；74条质量提示已记录，宽范围/重复依赖等限制保留，未宣称全部关闭。

[自动生成报告](审查报告.md)保留“记录无效”警示。完整台账、50项核对、哈希、门禁分组和可用相对记录链接见[外部缓存报告](/Users/skyfend/.cache/sr-boards/fossasia--pslab-hardware/review/审查报告.md)。未通过打包/冻结；仓库只放本轮三项产物，未复制第三方电路文件，未改检查器、未提交。

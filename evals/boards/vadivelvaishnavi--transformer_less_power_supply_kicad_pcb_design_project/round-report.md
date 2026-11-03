# lane-1 单板回路：容降非隔离电源

板：`vadivelvaishnavi--transformer_less_power_supply_kicad_pcb_design_project`。由固定 README/图面**推断**为市电串容→全桥→7805 教育电源；类型 AC_MAINS / POWER_CONVERTER / POWER_PROTECTION，基线 industrial_telecom。源提交 `60cf01ee9ff44718fd258eeae0f71823e3685706`，MIT；KiCad 10.0.7 strict 成功，18 件/9 网/37 端点。

| 计划项 | 局部已判 PASS/FAIL/NA | 待人工项 | 归因发现 | 真缺陷 | 误报 | 准则问题 | 资料缺口 | 待人工发现 | 漏报 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 100 | 31（21/2/8） | 69 | 10 | 1 | 3 | 0 | 1 | 5 | 1 |

门禁 **FAIL / valid=false / NO_GO**。2 个 FAIL 条目合为 1 个设计数据根因；55 条门禁错误主要来自未闭合覆盖，不是 55 个电路缺陷。

1. **优先修 M01 源侧保护漏问。** 没有 FUSE/MOV/NTC 反而不生成保护候选，元件又已归 POWER_CONVERTER，无法合法跨类型复用。应对已确认入口展开 PRO-C04/G05-019，逐支路问保护或系统接受理由。已有通用保护检查，故只记计划漏问；给出覆盖回归种子，不预设硬件 FAIL。
2. **三种可推广误报。** 1N4001 的 bridge application 脚注被当成器件类型；DIN0207 电阻封装触发工业 DI；通用 C4 被默认 MLCC。修复材料分别限定标题语义区、字段资格和技术证据。
3. **确定缺陷与条件风险分开。** D5/D6 图面及 BOM 只有 D_Zener，无 VZ/MPN，关键选值缺失并给种子。输入/负载和“225k”未受控；线路峰值不能直接作桥单管常态反压，470µF 无反向二极管也不自动证明 7805 必坏。Top50 全部核前提，无准则正文问题证据。

用法坑：schema15 无 needs_human，69 项逐 ID 留 pending；原生“资料不足0”不等于审完。稀疏检出漏 BOM，须从固定 commit 取缓存；read_bom 未保留 Value，另做 18/18 对读。家族手册 AVAILABLE 不等于采购后缀合格；旧截图不替代当前原生渲染。4 项重复理由筛查已核共享拓扑前提。

产出：[原生报告](审查报告.md)、[归因/修复/种子](findings.json)、[逐项表](check-disposition.json)、[Top50](top50-audit.json)、[证据](evidence-notes.md)、[哈希与命令](run-manifest.json)。第三方文件仅在缓存；未改检查器/准则/技能，未提交。
